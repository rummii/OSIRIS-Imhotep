"""HTTP routes: health probe, SOW generation, Google Doc export."""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.config import get_settings
from app.core.dependencies import get_current_user
from app.models.schemas import (
    ExportRequest,
    GenerateResponse,
    GroundingSource,
    MediaLogEntry,
    SowResponse,
    coerce_sow_payload,
)
from app.services.gdoc_service import GdocNotConfiguredError, GoogleDocsService
from app.services.deepseek_service import DeepSeekAnalysisError, DeepSeekService
from app.services.gemini_vision_service import GeminiVisionError, GeminiVisionService
from app.services.media_processor import MediaBundle, process_uploads
from app.services.prompt_builder import PromptBuilder
from app.services.rag_provider import get_context_provider

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
        "gdoc_configured": bool(settings.google_service_account_file or settings.google_oauth_token_file),
    }


@router.post("/sow/generate", response_model=GenerateResponse)
def generate_sow(
    notes: str = Form(""),
    site: str = Form(""),
    client: str = Form(""),
    files: list[UploadFile] = File(default=[]),
    _current_user: dict = Depends(get_current_user),  # login gate
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

    return GenerateResponse(
        sow=sow,
        media_log=[MediaLogEntry.model_validate(entry) for entry in media.log],
        model=result.model,
        grounding=False,
        grounding_sources=[],
        context_provider=context_provider.name,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/sow/export-gdoc")
def export_to_gdoc(
    payload: ExportRequest,
    _current_user: dict = Depends(get_current_user),  # login gate
) -> dict:
    """Convert a generated SOW JSON payload into a styled Google Doc.

    The Google API work runs in a fresh subprocess: the long-lived uvicorn
    worker threads can stall on Google's HTTPS endpoints on Windows, while a
    fresh Python process completes reliably.
    """
    settings = get_settings()
    try:
        SowResponse.model_validate(payload.sow)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid SOW payload: {exc}") from exc

    try:
        doc_url, doc_id = _run_export_subprocess(payload.sow, payload.owner_email)
    except GdocNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Google Docs export failed.")
        raise HTTPException(status_code=502, detail=f"Google Docs export failed: {exc}") from exc

    return {"doc_url": doc_url, "doc_id": doc_id}


def _run_export_subprocess(sow: dict, owner_email: str | None) -> tuple[str, str]:
    """Spawn a fresh Python process that performs the Google Docs export.

    Returns ``(doc_url, doc_id)`` or raises a descriptive exception.
    """
    backend_dir = Path(__file__).resolve().parent.parent.parent  # backend/
    venv_python = backend_dir / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        venv_python = Path(sys.executable)

    input_fd, input_path = tempfile.mkstemp(suffix=".json", prefix="osiris_sow_")
    output_fd, output_path = tempfile.mkstemp(suffix=".json", prefix="osiris_gdoc_")
    os.close(input_fd)
    os.close(output_fd)

    try:
        Path(input_path).write_text(
            json.dumps({"sow": sow, "owner_email": owner_email}),
            encoding="utf-8",
        )
        proc = subprocess.run(
            [
                str(venv_python),
                "-m",
                "app.services.gdoc_export_cli",
                input_path,
                output_path,
            ],
            cwd=str(backend_dir),
            # No captured pipes: a spawned child (venv shim / multiprocessing)
            # can keep stdout open and make subprocess.run wait forever. The
            # result travels via the output file instead.
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=150,
        )
        out_file = Path(output_path)
        if out_file.exists():
            result = json.loads(out_file.read_text(encoding="utf-8"))
        else:
            result = {"ok": False, "error": f"export subprocess exited with code {proc.returncode} (no result)"}
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Google Docs export timed out after 150s.") from exc
    finally:
        for path in (input_path, output_path):
            try:
                os.remove(path)
            except OSError:
                pass

    if not result.get("ok"):
        raise RuntimeError(result.get("error") or "unknown export error")
    return str(result["doc_url"]), str(result["doc_id"])
