"""Authentication service: SQLite user store + JWT session management.

* Passwords are hashed with PBKDF2-HMAC-SHA256 (stdlib) — no compiled deps.
* Sessions are stateless JWTs (HS256) signed with a per-deployment secret.
* A default ``superadmin`` is seeded on first run so the system is never
  locked out; the password comes from ``SUPERADMIN_PASSWORD`` in ``.env`` or is
  randomly generated and printed to the logs once.
"""
from __future__ import annotations

import logging
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.config import Settings
from app.core.security import create_token, decode_token, generate_salt, hash_password, verify_password

logger = logging.getLogger("osiris.auth")

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent  # backend/


class AuthError(RuntimeError):
    """Raised on bad credentials / validation failures (mapped to 4xx)."""


class UserStore:
    """Tiny SQLite persistence for users (stdlib only)."""

    def __init__(self, db_path: str) -> None:
        path = Path(db_path)
        if not path.is_absolute():
            path = BACKEND_DIR / path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(path)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL DEFAULT '',
                    password_hash TEXT NOT NULL,
                    password_salt TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    must_change_password INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    last_login_at TEXT
                )
                """
            )

    def count_users(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])

    def create_user(
        self,
        username: str,
        password: str,
        display_name: str = "",
        email: str = "",
        role: str = "user",
        must_change_password: bool = False,
    ) -> dict[str, Any]:
        salt = generate_salt()
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            try:
                cur = conn.execute(
                    """
                    INSERT INTO users
                        (username, display_name, email, password_hash, password_salt,
                         role, is_active, must_change_password, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (username, display_name, email, hash_password(password, salt), salt,
                     role, int(must_change_password), now),
                )
            except sqlite3.IntegrityError as exc:
                raise AuthError("A user with that username already exists.") from exc
            row = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)

    def get_by_username(self, username: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None

    def get_by_id(self, user_id: int) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    def list_users(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM users ORDER BY username COLLATE NOCASE"
            ).fetchall()
        return [dict(r) for r in rows]

    def update_user(self, user_id: int, fields: dict[str, Any]) -> Optional[dict[str, Any]]:
        allowed = {"display_name", "email", "role", "is_active"}
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not updates:
            return self.get_by_id(user_id)
        sets = ", ".join(f"{key} = ?" for key in updates)
        with self._connect() as conn:
            conn.execute(f"UPDATE users SET {sets} WHERE id = ?", (*updates.values(), user_id))
        return self.get_by_id(user_id)

    def set_password(self, user_id: int, new_password: str, must_change: bool = False) -> None:
        salt = generate_salt()
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ?, password_salt = ?, must_change_password = ? WHERE id = ?",
                (hash_password(new_password, salt), salt, int(must_change), user_id),
            )

    def record_login(self, user_id: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now, user_id))


class AuthService:
    """High-level auth operations used by the API routes + dependencies."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = UserStore(settings.auth_db_path)
        self._secret: Optional[str] = None

    @property
    def jwt_secret(self) -> str:
        if self._secret is None:
            self._secret = self._resolve_secret()
        return self._secret

    def _resolve_secret(self) -> str:
        if self.settings.jwt_secret.strip():
            return self.settings.jwt_secret.strip()
        secret_file = Path(self.store.db_path).parent / ".jwt_secret"
        if secret_file.exists():
            return secret_file.read_text(encoding="utf-8").strip()
        secret = secrets.token_hex(32)
        secret_file.write_text(secret, encoding="utf-8")
        return secret

    # -- seeding ---------------------------------------------------------------
    def ensure_superadmin(self) -> None:
        if self.store.count_users() > 0:
            return
        username = self.settings.superadmin_username.strip() or "admin"
        password = self.settings.superadmin_password.strip()
        if not password:
            password = secrets.token_urlsafe(12)
        self.store.create_user(
            username=username,
            password=password,
            display_name=self.settings.superadmin_display_name.strip() or "System Administrator",
            email=self.settings.superadmin_email.strip(),
            role="superadmin",
        )
        logger.warning(
            "Seeded default superadmin — username=%s password=%s  (change it after first login!)",
            username,
            password,
        )

    # -- auth ------------------------------------------------------------------
    def authenticate(self, username: str, password: str) -> dict[str, Any]:
        user = self.store.get_by_username(username.strip())
        if not user or not verify_password(password, user["password_salt"], user["password_hash"]):
            raise AuthError("Invalid username or password.")
        if not user["is_active"]:
            raise AuthError("This account has been disabled. Contact your administrator.")
        self.store.record_login(user["id"])
        return self.store.get_by_id(user["id"])

    def issue_token(self, user: dict[str, Any]) -> str:
        return create_token(
            {"sub": str(user["id"]), "username": user["username"], "role": user["role"]},
            self.jwt_secret,
            expires_seconds=self.settings.token_expiry_hours * 3600,
        )

    def decode_token(self, token: str) -> Optional[dict[str, Any]]:
        return decode_token(token, self.jwt_secret)

    def change_password(self, user: dict[str, Any], current: str, new_password: str) -> None:
        if not verify_password(current, user["password_salt"], user["password_hash"]):
            raise AuthError("Current password is incorrect.")
        self.store.set_password(user["id"], new_password, must_change=False)

    def public_user(self, user: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"],
            "email": user["email"],
            "role": user["role"],
            "is_active": bool(user["is_active"]),
            "must_change_password": bool(user["must_change_password"]),
            "created_at": user["created_at"],
            "last_login_at": user.get("last_login_at"),
        }
