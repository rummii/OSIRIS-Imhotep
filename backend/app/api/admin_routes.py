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
from app.services.prompt_builder import COMPLIANCE_BLOCKS
from pydantic import BaseModel, Field

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
# Phase 5 Track 2: Audit log viewer - separate sub-router under /admin/audit-log
# ---------------------------------------------------------------------------
audit_router = APIRouter(prefix="/admin/audit-log", tags=["admin"], dependencies=[Depends(require_superadmin)])


@audit_router.get("")
def list_audit_log(
    user_id: int | None = None,
    action: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _: dict = Depends(require_superadmin),
) -> dict:
    settings = get_settings()
    items = AuditService(settings).list(
        user_id=user_id,
        action=action,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "total": len(items)}


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
    return {
        "export_costing_enabled": settings.export_costing_enabled,
        "compliance_profiles": list(COMPLIANCE_BLOCKS.keys()),
    }


# -------------------------------------------------------------------
# Compliance profile registry (read-only listing for the admin UI)
# GET /api/admin/config/compliance-profiles
# GET /api/admin/config/compliance-profiles/{key}
# -------------------------------------------------------------------
compliance_router = APIRouter(
    prefix="/admin/config/compliance-profiles",
    tags=["admin"],
    dependencies=[Depends(require_superadmin)],
)


class ComplianceProfileSummary(BaseModel):
    key: str
    name: str
    description: str
    length: int = 0


@compliance_router.get("", response_model=list[ComplianceProfileSummary])
def list_compliance_profiles() -> list[ComplianceProfileSummary]:
    names = {"dpwh": "DPWH Infrastructure",
             "dole": "DOLE Occupational Safety and Health",
             "philgeps": "PhilGEPS / Government Procurement"}
    return [ComplianceProfileSummary(
        key=k,
        name=names.get(k, k.title()),
        description=v.split("\n", 1)[1].strip() if "\n" in v else v,
        length=len(v),
    ) for k, v in COMPLIANCE_BLOCKS.items()]


@compliance_router.get("/{key}")
def get_compliance_profile(key: str) -> dict:
    if key not in COMPLIANCE_BLOCKS:
        raise HTTPException(status_code=404, detail=f"Unknown compliance profile: {key}")
    return {"key": key, "content": COMPLIANCE_BLOCKS[key]}
