"""SOP / Knowledge Base upload routes (Phase 3)."""
from __future__ import annotations

import io
import logging
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.config import get_settings
from app.core.dependencies import get_current_user
from app.core.vector_store import VectorStore
from app.services.embedder import get_embedder
from app.services.ingest_service import chunk_text

logger = logging.getLogger("osiris.sop")

MAX_FILE_SIZE = 8 * 1024 * 1024  # 8 MB
_ACCEPTED_EXTS = {".pdf", ".txt", ".md"}

router = APIRouter()


def _extract_text(content: bytes, filename: str) -> str:
    """Extract plain text from a PDF or TXT/MD file."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        except ImportError:
            raise HTTPException(
                status_code=501,
                detail="PDF processing requires pypaf. Install it: pip install pypdf.",
            )
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Failed to extract text from PDF: {exc}",
            )
    elif ext in (".txt", ".md"):
        return content.decode("utf-8", errors="replace").strip()
    else:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {ext}. Upload a PDF, TXT, or MD file.",
        )


def _sanitise_source(filename: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", Path(filename).stem.lower()).strip("-")
    return f"sop-{clean}-{uuid.uuid4().hex[:6]}"


@router.post("/sop/upload")
def upload_sop(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Ingest a SOP / knowledge-base PDF or TXT file into the RAG corpus.

    The file is chunked, embedded, and upserted into the vector store under a
    derived source ID. The returned ``source`` ID is then passed to
    ``POST /api/sow/generate`` via the ``sop_sources`` field to bias the SOW
    generation toward the uploaded document.

    Returns: ``{"ok": true, "source": "<source-id>", "chunks_added": <int>}``
    """
    settings = get_settings()

    if file.size is not None and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {MAX_FILE_SIZE // 1024 // 1024} MB limit.",
        )

    ext = Path(file.filename or "unknown").suffix.lower()
    if ext not in _ACCEPTED_EXTS:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Upload a PDF, TXT, or MD file.",
        )

    try:
        content = file.file.read()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {exc}") from exc

    try:
        text = _extract_text(content, file.filename or "unknown")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not text.strip():
        raise HTTPException(status_code=422, detail="File contains no extractable text.")

    source = _sanitise_source(file.filename or "sop-unknown")

    try:
        embedder = get_embedder(settings.gemini_api_key)
    except Exception as exc:
        logger.error("SOP embedder init failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Gemini API key not configured. SOP uploads require a valid key.",
        ) from exc

    try:
        store = VectorStore(settings=settings)
        store.init_schema()
    except Exception as exc:
        logger.error("VectorStore init failed: %s", exc)
        raise HTTPException(status_code=503, detail="Vector store unavailable.") from exc

    chunks = chunk_text(text)
    if not chunks:
        raise HTTPException(status_code=422, detail="No text chunks could be extracted.")

    batch: list[dict] = [
        {
            "text": piece,
            "source": source,
            "domain": "client-sop",
            "jurisdiction": "client-sop",
            "citation": f"Uploaded SOP: {file.filename}",
            "chunk_index": idx,
        }
        for idx, piece in enumerate(chunks)
    ]

    try:
        embeddings = embedder.embed_batch_sync([row["text"] for row in batch])
        for row, emb in zip(batch, embeddings):
            row["embedding"] = emb
        written = store.upsert_chunks(batch)
    except Exception as exc:
        logger.exception("SOP embed/upsert failed: %s", exc)
        raise HTTPException(status_code=500, detail="SOP ingestion failed.") from exc

    logger.info(
        "SOP '%s' ingested: %d chunks, user=%s",
        source,
        written,
        current_user.get("username"),
    )
    return {
        "ok": True,
        "source": source,
        "chunks_added": written,
        "filename": file.filename,
    }
