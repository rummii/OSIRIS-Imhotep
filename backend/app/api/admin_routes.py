# pyright: reportOptionalSubscript=false, reportOptionalMemberAccess=false
"""Admin routes (superadmin only): onboard and manage users."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import get_settings
from app.core.dependencies import require_superadmin
from app.models.auth_models import (
    MessageResponse,
    ResetPasswordRequest,
    UserCreate,
    UserOut,
    UserUpdate,
)
from app.services.audit_service import AuditService
from app.services.auth_service import AuthError, AuthService

router = APIRouter(prefix="/admin/users", tags=["admin"], dependencies=[Depends(require_superadmin)])


def _service():
    return AuthService(get_settings())


def _audit() -> AuditService:
    return AuditService(get_settings())



@router.get("", response_model=list[UserOut])
def list_users(_: dict = Depends(require_superadmin)) -> list[dict]:
    service = _service()
    return [service.public_user(u) for u in service.store.list_users()]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, _: dict = Depends(require_superadmin)) -> dict:
    service = _service()
    try:
        user = service.store.create_user(
            username=payload.username,
            password=payload.password,
            display_name=payload.display_name,
            email=payload.email,
            role=payload.role,
            must_change_password=payload.must_change_password,
        )
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    _audit().log('user_create', target_type='user', target_id=str(user['id']),
                 outcome='success', detail=f'role={user['role']}')
    return service.public_user(user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    current: dict = Depends(require_superadmin),
) -> dict:
    service = _service()
    target = service.store.get_by_id(user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if target["id"] == current["id"] and payload.is_active is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot deactivate your own account.")
    if target["id"] == current["id"] and payload.role and payload.role != "superadmin":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot demote your own account.")
    updated = service.store.update_user(user_id, payload.model_dump(exclude_unset=True))
    _audit().log('user_update', target_type='user', target_id=str(user_id),
                 outcome='success', detail=','.join(sorted(payload.model_dump(exclude_unset=True).keys())))
    return service.public_user(updated)


@router.post("/{user_id}/reset-password", response_model=MessageResponse)
def reset_password(
    user_id: int,
    payload: ResetPasswordRequest,
    _: dict = Depends(require_superadmin),
) -> MessageResponse:
    service = _service()
    target = service.store.get_by_id(user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    service.store.set_password(user_id, payload.new_password, must_change=True)
    _audit().log('user_reset_password', target_type='user', target_id=str(user_id), outcome='success')
    return MessageResponse(detail="Password reset. The user must change it at next login.")


# ---------------------------------------------------------------------------
# Phase 1 — RAG corpus management (superadmin only)
# ---------------------------------------------------------------------------

@router.get("/rag/stats", response_model=object, tags=["admin"])
def rag_stats(_: dict = Depends(require_superadmin)) -> object:
    """Return current RAG vector store statistics (total chunks, sources, engine)."""
    from app.services.ingest_service import IngestService

    settings = get_settings()
    if settings.rag_provider.strip().lower() != "sqlite_vec":
        return {"total_chunks": 0, "sources": [], "engine": "disabled", "last_refresh_at": None}
    service = IngestService(settings)
    return service.stats()


@router.post("/rag/refresh", response_model=object, tags=["admin"])
def rag_refresh(_: dict = Depends(require_superadmin)) -> object:
    """Re-embed and persist the full regulatory corpus.

    This is an idempotent operation — re-running the same corpus replaces
    existing rows keyed on ``(source, chunk_index)``.  Takes 30-90 seconds
    depending on corpus size and embedding latency.
    """
    from app.services.ingest_service import IngestService

    settings = get_settings()
    if settings.rag_provider.strip().lower() != "sqlite_vec":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RAG_PROVIDER is not set to 'sqlite_vec'. Set RAG_PROVIDER=sqlite_vec in backend/.env to use this endpoint.",
        )
    service = IngestService(settings)
    stats = service.refresh_corpus()
    _audit().log('rag_refresh', target_type='rag', target_id='corpus', outcome='success',
                 detail=f'chunks={getattr(stats, "total_chunks", "?")}')
    return stats.to_dict()


# ---------------------------------------------------------------------------
# Phase 5 Track 2: Audit log viewer - separate sub-router under /admin/audit-log
# ---------------------------------------------------------------------------
audit_router = APIRouter(prefix="/admin/audit-log", tags=["admin"], dependencies=[Depends(require_superadmin)])


@audit_router.get("")
def list_audit_log(
    user_id: int | None = None,
    action: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """Return recent audit log entries, newest first.

    Supports filtering by user_id, action, and pagination.  Superadmin only.
    """
    service = _audit()
    items = service.list(user_id=user_id, action=action, limit=limit, offset=offset)
    total = service.count(user_id=user_id, action=action)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


# ---------------------------------------------------------------------------
# Phase 4/5: Feature-gate config (superadmin only)
# ---------------------------------------------------------------------------
config_router = APIRouter(prefix="/admin/config", tags=["admin"], dependencies=[Depends(require_superadmin)])


@config_router.get("", response_model=object)
def get_export_config(_: dict = Depends(require_superadmin)) -> object:
    """Return feature-gate flags for the frontend.

    Currently exports the ``export_costing_enabled`` flag so the UI knows
    whether to surface (or hide) the costing-format export buttons.
    """
    settings = get_settings()
    return {"export_costing_enabled": settings.export_costing_enabled}
