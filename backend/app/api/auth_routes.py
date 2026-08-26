"""Auth routes: login, session info, change password."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import get_settings
from app.core.dependencies import get_current_user
from app.models.auth_models import (
    ChangePasswordRequest,
    LoginRequest,
    MessageResponse,
    TokenResponse,
    UserOut,
)
from app.services.auth_service import AuthError, AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    settings = get_settings()
    service = AuthService(settings)
    try:
        user = service.authenticate(payload.username, payload.password)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    token = service.issue_token(user)
    return TokenResponse(
        access_token=token,
        expires_in=settings.token_expiry_hours * 3600,
        role=user["role"],
        username=user["username"],
        display_name=user["display_name"],
        must_change_password=bool(user["must_change_password"]),
    )


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)) -> dict:
    settings = get_settings()
    service = AuthService(settings)
    return service.public_user(user)


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    user: dict = Depends(get_current_user),
) -> MessageResponse:
    settings = get_settings()
    service = AuthService(settings)
    try:
        service.change_password(user, payload.current_password, payload.new_password)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return MessageResponse(detail="Password updated successfully.")
