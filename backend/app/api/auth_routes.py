"""Auth routes: login, logout, session info, change password."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.config import get_settings
from app.core.dependencies import get_current_user
from app.core.rate_limit import _client_ip, rate_limit
from app.models.auth_models import (
    ChangePasswordRequest,
    LoginRequest,
    MessageResponse,
    TokenResponse,
    UserOut,
)
from app.services.audit_service import AuditService
from app.services.auth_service import AuthError, AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _audit() -> AuditService:
    return AuditService(get_settings())


# Per-IP rate limit on /login.  The dependency also requires a valid JWT
# via get_current_user, but for the login route we need a separate
# anonymous-keyed bucket.  Implemented as a custom dep using the same
# underlying limiter.
def _login_rate_limit_dep(request: Request):
    settings = get_settings()
    from app.core.rate_limit import get_limiter
    key = _client_ip(request)
    limit = settings.rate_limit_login_per_minute
    if not get_limiter().check(key=key, route="auth.login", capacity=limit, per_minute=limit):
        try:
            _audit().log(
                "rate_limited",
                target_type="route",
                target_id="auth.login",
                outcome="denied",
                detail=f"limit={limit}/min",
                ip_address=key,
            )
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded for login. Try again later.",
            headers={"Retry-After": "60"},
        )


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(_login_rate_limit_dep)])
def login(payload: LoginRequest, request: Request) -> TokenResponse:
    settings = get_settings()
    service = AuthService(settings)
    try:
        user = service.authenticate(payload.username, payload.password)
    except AuthError as exc:
        _audit().log(
            "login_failed",
            username=payload.username,
            target_type="session",
            outcome="failure",
            detail=str(exc),
            ip_address=_client_ip(request),
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    token = service.issue_token(user)
    _audit().log(
        "login",
        user=user,
        target_type="session",
        outcome="success",
        ip_address=_client_ip(request),
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.token_expiry_hours * 3600,
        role=user["role"],
        username=user["username"],
        display_name=user["display_name"],
        must_change_password=bool(user["must_change_password"]),
    )


@router.post("/logout", response_model=MessageResponse)
def logout(user: dict = Depends(get_current_user), request: Request = None) -> MessageResponse:
    """Stateless logout - JWT cannot be revoked server-side, but we record
    the event for security audit.  Clients must discard the token locally."""
    _audit().log(
        "logout",
        user=user,
        target_type="session",
        outcome="success",
        ip_address=_client_ip(request) if request else None,
    )
    return MessageResponse(detail="Logged out. Please discard your token on the client.")


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
        _audit().log(
            "change_password_failed",
            user=user,
            target_type="session",
            outcome="failure",
            detail=str(exc),
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    _audit().log(
        "change_password",
        user=user,
        target_type="session",
        outcome="success",
    )
    return MessageResponse(detail="Password updated successfully.")
