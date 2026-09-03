"""RAG Regulatory Corpus management (superadmin only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import get_settings
from app.core.dependencies import require_superadmin
from app.services.ingest_service import IngestService

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_superadmin)])


@router.get("/rag/stats", response_model=object, tags=["admin"])
def rag_stats(_: dict = Depends(require_superadmin)) -> object:
    """Return current RAG vector store statistics (total chunks, sources, engine)."""
    settings = get_settings()
    if settings.rag_provider.strip().lower() != "sqlite_vec":
        return {"total_chunks": 0, "sources": [], "engine": "disabled", "last_refresh_at": None}
    service = IngestService(settings)
    return service.stats()


@router.post("/rag/refresh", response_model=object, tags=["admin"])
def rag_refresh(_: dict = Depends(require_superadmin)) -> object:
    """Re-embed and persist the full regulatory corpus."""
    settings = get_settings()
    if settings.rag_provider.strip().lower() != "sqlite_vec":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RAG_PROVIDER is not set to sqlite_vec. Set RAG_PROVIDER=sqlite_vec in backend/.env to use this endpoint.",
        )
    service = IngestService(settings)
    stats = service.refresh_corpus()
    return stats.to_dict()

