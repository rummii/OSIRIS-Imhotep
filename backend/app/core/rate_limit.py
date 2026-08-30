"""Per-user token-bucket rate limiter, in-memory.

Thread-safe; the only state lives in a single dict protected by a Lock.
Limit is per ``(user_id, route)`` so different routes have independent
buckets.  For anonymous routes (e.g. /api/auth/login) the IP address is
used as the key.

For multi-worker deployments the bucket is per-process; a follow-up
could back it with Redis.  Tests should call ``reset_for_tests()``
between runs to avoid cross-test contamination.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, Request, status

from app.core.dependencies import get_current_user


@dataclass
class _Bucket:
    tokens: float
    last_refill: float


class TokenBucketLimiter:
    def __init__(self) -> None:
        self._buckets: dict[tuple, _Bucket] = {}
        self._lock = threading.Lock()

    def _refill(self, b: _Bucket, capacity: int, per_minute: int, now: float) -> None:
        # Linear refill - simple and predictable.
        elapsed = max(0.0, now - b.last_refill)
        b.tokens = min(float(capacity), b.tokens + (elapsed * per_minute / 60.0))
        b.last_refill = now

    def check(
        self,
        *,
        key: int | str,
        route: str,
        capacity: int,
        per_minute: int,
        now: Optional[float] = None,
    ) -> bool:
        """Consume one token.  Returns True if allowed, False if limited."""
        if per_minute <= 0 or capacity <= 0:
            return True  # rate limit disabled
        full_key = (key, route)
        ts = time.time() if now is None else now
        with self._lock:
            b = self._buckets.get(full_key)
            if b is None:
                b = _Bucket(tokens=float(capacity - 1), last_refill=ts)
                self._buckets[full_key] = b
                return True
            self._refill(b, capacity, per_minute, ts)
            if b.tokens >= 1.0:
                b.tokens -= 1.0
                return True
            return False

    def reset_for_tests(self) -> None:
        with self._lock:
            self._buckets.clear()


_global_limiter = TokenBucketLimiter()


def get_limiter() -> TokenBucketLimiter:
    return _global_limiter


def reset_for_tests() -> None:
    _global_limiter.reset_for_tests()


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

def _client_ip(request: Request) -> str:
    # X-Forwarded-For takes priority (set by reverse proxies / Cloud Run).
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def rate_limit(
    *,
    route: str,
    per_minute: int,
    superadmin_per_minute: Optional[int] = None,
    anonymous: bool = False,
):
    """Build a FastAPI dependency that enforces a per-(user|ip) token bucket.

    * ``route``       - logical name, e.g. "sow.generate" - used as bucket suffix
    * ``per_minute``  - limit for standard users (or anonymous if anonymous=True)
    * ``superadmin_per_minute`` - higher limit for superadmins; defaults to per_minute
    * ``anonymous``   - if True, the bucket is keyed by IP and ``get_current_user``
                        is NOT consulted (use for /api/auth/login)
    """

    def _dep(request: Request, current_user: dict = Depends(get_current_user)):
        if anonymous:
            key: int | str = _client_ip(request)
            limit = per_minute
        else:
            role = current_user.get("role")
            if role == "superadmin" and superadmin_per_minute is not None:
                limit = superadmin_per_minute
            else:
                limit = per_minute
            key = int(current_user["id"])

        limiter = get_limiter()
        if not limiter.check(key=key, route=route, capacity=limit, per_minute=limit):
            # Best-effort audit log (never raises).
            try:
                from app.services.audit_service import AuditService
                from app.config import get_settings as _get_settings

                AuditService(_get_settings()).log(
                    "rate_limited",
                    user=current_user if not anonymous else None,
                    target_type="route",
                    target_id=route,
                    outcome="denied",
                    detail=f"limit={limit}/min",
                    ip_address=_client_ip(request) if anonymous else None,
                    username=current_user.get("username") if not anonymous else None,
                )
            except Exception:
                pass
            retry_after = max(1, int(60 / max(limit, 1)))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for {route}. Try again in {retry_after}s.",
                headers={"Retry-After": str(retry_after)},
            )
        return current_user

    return _dep
