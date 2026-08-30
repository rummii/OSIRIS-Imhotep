"""HTTP routes: health probe and SOW generation."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from typing import Optional

from app.config import get_settings
from app.core.dependencies import get_current_user
from app.models.schemas import (
    GenerateResponse,
    GroundingSource,
    MediaLogEntry,
    SowResponse,
    SpatialContext,
    SpatialManifest,
    coerce_sow_payload,
)
from app.services.deepseek_service import DeepSeekAnalysisError, DeepSeekService
from app.services.geocode import reverse_geocode
from app.services.gemini_vision_service import GeminiVisionError, GeminiVisionService
from app.services.media_processor import MediaBundle, process_uploads
from app.services.prompt_builder import PromptBuilder
from app.services.rag_provider import get_context_provider
from app.services.audit_service import AuditService
from app.services.quota_service import QuotaError, QuotaService
from app.services.sow_service import SowService

logger = logging.getLogger("osiris.routes")
router = APIRouter()

def _generate_rate_limit_dep(current_user: dict = Depends(get_current_user)):
    """Per-(user|role) token bucket on /sow/generate.  Depends is built at
    request time so that superadmin role is honoured."""
    from app.core.rate_limit import _client_ip, get_limiter
    from fastapi import Request as _Request, HTTPException as _HTTPException
    settings = get_settings()
    role = current_user.get('role')
    if role == 'superadmin':
        limit = settings.rate_limit_generate_superadmin_per_minute
    else:
        limit = settings.rate_limit_generate_per_minute
    key = int(current_user['id'])
    if not get_limiter().check(key=key, route='sow.generate', capacity=limit, per_minute=limit):
        try:
            AuditService(settings).log(
                'rate_limited', user=current_user, target_type='route',
                target_id='sow.generate', outcome='denied',
                detail=f'limit={limit}/min',
            )
        except Exception:
            pass
        raise _HTTPException(
            status_code=429,
            detail=f'Rate limit exceeded for SOW generation. Try again in {max(1, 60//max(limit,1))}s.',
            headers={'Retry-After': str(max(1, 60//max(limit,1)))},
        )


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "model": settings.deepseek_model,
        "vision_model": settings.gemini_vision_model if settings.gemini_api_key else None,
        "grounding": False,
        "rag_provider": settings.rag_provider,
    }

@router.post("/sow/generate", response_model=GenerateResponse, dependencies=[Depends(_generate_rate_limit_dep)])
def generate_sow(
    notes: str = Form(""),
    site: str = Form(""),
    client: str = Form(""),
    files: list[UploadFile] = File(default=[]),
    current_user: dict = Depends(get_current_user),  # login gate + document owner
) -> GenerateResponse:
    """Accept engineer notes + media (images / short clips) and produce a SOW."""
    settings = get_settings()
    notes = notes or ""
    site = site or ""
    client = client or ""

    # Phase 5 Track 2: per-request upload quota (smaller of legacy 50MB
    # and the operator-configured quota).  Enforce before any I/O.
    try:
        QuotaService(settings).check_upload(
            files=files,
            request_content_length=None,  # Starlette doesn't expose this on UploadFile; size check happens below
        )
    except QuotaError as exc:
        AuditService(settings).log(
            'quota_exceeded', user=current_user, target_type='quota',
            target_id=exc.code, outcome='denied', detail=exc.message,
        )
        if exc.code == 'upload_too_large':
            status_code = 413
        else:
            status_code = 400
        raise HTTPException(status_code=status_code, detail=exc.message) from exc

    if not notes.strip() and not files:
        raise HTTPException(status_code=400, detail="Provide engineer field notes and/or at least one media file.")

    try:
        media: MediaBundle = process_uploads(
            files,
            temp_dir=settings.temp_dir,
            max_video_frames=settings.max_video_frames,
            max_upload_bytes=settings.max_upload_bytes,
        )
    except Exception as exc:
        logger.exception("Media processing crashed.")
        raise HTTPException(status_code=400, detail=f"Media processing failed: {exc}") from exc
    if files and not media.parts and not notes.strip():
        raise HTTPException(status_code=400, detail="No usable media could be processed.")

    visual_evidence = ""
    if media.parts:
        try:
            visual_evidence = GeminiVisionService(settings).analyze(media.parts)
        except GeminiVisionError as exc:
            logger.exception("Gemini vision analysis failed.")
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    # 2. Collect supplemental context (RAG seam) -------------------------------
    context_provider = get_context_provider(settings)
    try:
        context_docs = context_provider.retrieve(notes, media.summary())
    except Exception:
        logger.exception("Context retrieval failed; continuing without context.")
        context_docs = []

    # 2b. Phase 2+3: Extract spatial context from media EXIF/GPS data,
    #     reverse-geocode each unique coordinate, and surface it in the prompt.
    spatial_files: dict[str, SpatialContext] = {}
    spatial_lines: list[str] = []
    seen_coords: set[tuple[float, float]] = set()
    for part in media.parts:
        if not (part.spatial and part.spatial.is_valid()):
            continue
        ctx = SpatialContext(
            latitude=part.spatial.latitude,
            longitude=part.spatial.longitude,
            altitude_m=part.spatial.altitude_m,
            accuracy_m=part.spatial.accuracy_m,
            captured_at=part.spatial.captured_at,
            source_file=part.filename,
        )
        # Phase 3: reverse-geocode each unique coordinate (cached by grid cell).
        if settings.geocode_enabled:
            coord_key = (round(part.spatial.latitude, 6), round(part.spatial.longitude, 6))
            if coord_key not in seen_coords:
                seen_coords.add(coord_key)
                try:
                    site_loc = reverse_geocode(
                        part.spatial.latitude,
                        part.spatial.longitude,
                        endpoint=settings.geocode_endpoint,
                        user_agent=settings.geocode_user_agent,
                        timeout=settings.geocode_timeout,
                        zoom=settings.geocode_zoom,
                    )
                    if site_loc is not None:
                        ctx.site_location = site_loc
                except Exception as exc:
                    logger.debug("Reverse-geocode skipped for %s: %s", part.filename, exc)
        spatial_files[part.filename] = ctx
        spatial_lines.append(
            f"- {part.filename}: {ctx.location_string()}"
            + (f" (captured {ctx.captured_at})" if ctx.captured_at else "")
        )

    # 3. Build prompts ----------------------------------------------------------
    builder = PromptBuilder()
    system_prompt = builder.build_system_prompt(context_docs)
    user_prompt = builder.build_user_prompt(
        notes=notes,
        site=site,
        client=client,
        visual_evidence=visual_evidence,
        spatial_lines=spatial_lines or None,
    )

    # 4. DeepSeek text analysis -----------------------------------------------------
    try:
        deepseek = DeepSeekService(settings)
        result = deepseek.analyze(system_prompt, user_prompt)
    except DeepSeekAnalysisError as exc:
        logger.exception("DeepSeek analysis failed.")
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # 5. Validate / coerce the model output --------------------------------------
    try:
        sow: SowResponse = coerce_sow_payload(result.payload)
    except Exception as exc:
        logger.exception("Model output failed validation.")
        raise HTTPException(status_code=502, detail=f"Model output failed validation: {exc}") from exc

    # 6. Persist the generated SOW as a document for the current user ---------
    document_id: Optional[int] = None
    try:
        sow_dict = sow.model_dump(mode="json")
        spatial_payload = (
            SpatialManifest(files=spatial_files).model_dump(mode="json")
            if spatial_files
            else None
        )
        saved = SowService(settings).save_from_sow(
            user_id=current_user["id"],
            sow_dict=sow_dict,
            spatial_context=spatial_payload,
        )
        document_id = int(saved.get("id")) if saved else None
        logger.info("Saved SOW document %s for user %s", document_id, current_user.get("username"))
    except Exception:
        # Persistence is best-effort: a failed save must not break generation.
        logger.exception("Failed to save SOW document for user %s", current_user.get("username"))

    try:
        AuditService(settings).log(
            'sow_generate', user=current_user, target_type='sow',
            target_id=str(document_id) if document_id else None,
            outcome='success',
            detail=f'files={len(files)} notes_len={len(notes or "")}',
        )
    except Exception:
        pass
    return GenerateResponse(
        sow=sow,
        media_log=[MediaLogEntry.model_validate(entry) for entry in media.log],
        model=result.model,
        grounding=False,
        grounding_sources=[],
        context_provider=context_provider.name,
        generated_at=datetime.now(timezone.utc).isoformat(),
        document_id=document_id,
        spatial_context=(
            SpatialManifest(files=spatial_files) if spatial_files else None
        ),
    )
