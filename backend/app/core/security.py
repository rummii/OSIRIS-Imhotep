"""Password hashing (PBKDF2-HMAC-SHA256) + stateless JWT (HS256), stdlib only.

No third-party crypto deps → installs cleanly on shared hosting (cPanel) and
keeps the token/session story self-contained.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Optional

PBKDF2_ITERATIONS = 200_000


# --- password hashing --------------------------------------------------------
def generate_salt() -> str:
    return secrets.token_hex(16)


def hash_password(password: str, salt: str, iterations: int = PBKDF2_ITERATIONS) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), iterations)
    return base64.b64encode(dk).decode("ascii")


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    try:
        return hmac.compare_digest(hash_password(password, salt), expected_hash)
    except (ValueError, TypeError):
        return False


# --- stateless JWT -----------------------------------------------------------
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def create_token(payload: dict[str, Any], secret: str, expires_seconds: int = 12 * 3600) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    body = {
        **payload,
        "iat": int(time.time()),
        "exp": int(time.time()) + expires_seconds,
    }
    signing_input = (
        f"{_b64url(json.dumps(header, separators=(',', ':')).encode('utf-8'))}."
        f"{_b64url(json.dumps(body, separators=(',', ':')).encode('utf-8'))}"
    )
    signature = _b64url(hmac.new(secret.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest())
    return f"{signing_input}.{signature}"


def decode_token(token: str, secret: str) -> Optional[dict[str, Any]]:
    try:
        header_seg, payload_seg, signature_seg = token.split(".")
        signing_input = f"{header_seg}.{payload_seg}"
        expected = _b64url(hmac.new(secret.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest())
        if not hmac.compare_digest(signature_seg, expected):
            return None
        payload = json.loads(_b64url_decode(payload_seg))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None
