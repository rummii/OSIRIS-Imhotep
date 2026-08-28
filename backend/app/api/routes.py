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
    coerce_sow_payload,
)
from app.services.deepseek_service import DeepSeekAnalysisError, DeepSeekService
from app.services.gemini_vision_service import GeminiVisionError, GeminiVisionService
from app.services.media_processor import MediaBundle, process_uploads
from app.services.prompt_builder import PromptBuilder
from app.services.rag_provider import get_context_provider
from app.services.sow_service import SowService

logger = logging.getLogger("osiris.routes")
router = APIRouter()

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

@router.post("/sow/generate", response_model=GenerateResponse)
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

    # 3. Build prompts ----------------------------------------------------------
    builder = PromptBuilder()
    system_prompt = builder.build_system_prompt(context_docs)
    user_prompt = builder.build_user_prompt(
        notes=notes,
        site=site,
        client=client,
        visual_evidence=visual_evidence,
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
        saved = SowService(settings).save_from_sow(
            user_id=current_user["id"],
            sow_dict=sow_dict,
        )
        document_id = int(saved.get("id")) if saved else None
        logger.info("Saved SOW document %s for user %s", document_id, current_user.get("username"))
    except Exception:
        # Persistence is best-effort: a failed save must not break generation.
        logger.exception("Failed to save SOW document for user %s", current_user.get("username"))

    return GenerateResponse(
        sow=sow,
        media_log=[MediaLogEntry.model_validate(entry) for entry in media.log],
        model=result.model,
        grounding=False,
        grounding_sources=[],
        context_provider=context_provider.name,
        generated_at=datetime.now(timezone.utc).isoformat(),
        document_id=document_id,
    )
