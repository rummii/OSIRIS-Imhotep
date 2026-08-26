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
from app.services.auth_service import AuthError, AuthService

router = APIRouter(prefix="/admin/users", tags=["admin"], dependencies=[Depends(require_superadmin)])


def _service():
    return AuthService(get_settings())


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
    return MessageResponse(detail="Password reset. The user must change it at next login.")
