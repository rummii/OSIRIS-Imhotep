# pyright: reportOptionalSubscript=false, reportOptionalMemberAccess=false
"""Authentication service: user store + JWT session management.

* Passwords are hashed with PBKDF2-HMAC-SHA256 (stdlib) — no compiled deps.
* Sessions are stateless JWTs (HS256) signed with a per-deployment secret.
* A default ``superadmin`` is seeded on first run so the system is never
  locked out; the password comes from ``SUPERADMIN_PASSWORD`` in ``.env`` or is
  randomly generated and printed to the logs once.
* User persistence: SQLite (default, e.g. local dev) or PostgreSQL on Cloud
  SQL when ``DATABASE_URL`` is set (e.g. Cloud Run). Both dialects share the
  same schema and API.
"""
from __future__ import annotations

import logging
import secrets
import sqlite3
import ssl
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse, unquote

from app.config import Settings
from app.core.security import create_token, decode_token, generate_salt, hash_password, verify_password

logger = logging.getLogger("osiris.auth")

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent  # backend/


class AuthError(RuntimeError):
    """Raised on bad credentials / validation failures (mapped to 4xx)."""


def _parse_database_url(url: str) -> dict[str, Any]:
    """Parse ``postgres+pg8000://user:pass@host:port/db`` (Neon / Supabase / external)
    or ``postgres+pg8000://user:pass@/db?unix_sock=/cloudsql/.../.s.PGSQL.5432``
    (Cloud SQL — production path).

    Recognised query parameters:
      * ``unix_sock``  – Cloud SQL Unix-socket path (overrides host/port)
      * ``sslmode``    – "require" | "verify-ca" | "verify-full" (default for
                         any TCP host)
      * ``sslrootcert``– path to a CA bundle when ``sslmode=verify-*``
      * ``sslcert`` / ``sslkey`` – mTLS client cert/key paths
    """
    url = url.strip()
    if url.startswith(("postgres://", "postgresql://")):
        # Standard scheme works with pg8000, but keep the explicit prefix for clarity.
        url = "postgres+pg8000://" + url.split("://", 1)[1]
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    password = parsed.password or ""
    if password and "%" in password:
        # Some providers URL-encode special characters in passwords.
        password = unquote(password)
    return {
        "user": parsed.username or "",
        "password": password,
        "database": parsed.path.lstrip("/"),
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "unix_sock": (query.get("unix_sock") or [""])[0] or None,
        # Default sslmode to "require" for any non-socket host so Neon/Supabase
        # work out of the box. Cloud SQL unix-socket connections skip TLS.
        "sslmode": (query.get("sslmode") or [None])[0]
        or ("require" if not (query.get("unix_sock") or [""])[0] else None),
        "sslrootcert": (query.get("sslrootcert") or [None])[0],
        "sslcert": (query.get("sslcert") or [None])[0],
        "sslkey": (query.get("sslkey") or [None])[0],
    }


def _pg_row_to_dict(cur: Any, row: Any) -> dict[str, Any]:
    """Map a pg8000 tuple row to a dict using the cursor description."""
    columns = [d[0] for d in cur.description]
    return dict(zip(columns, row))


def _pg_ssl_context(pg: dict[str, Any]) -> Optional[ssl.SSLContext]:
    """Build an ``ssl.SSLContext`` for pg8000 from parsed connection options.

    pg8000 accepts ``ssl_context=<SSLContext>`` (not psycopg2-style dicts).
    * No sslmode / unix socket  -> None (plain TCP, e.g. Cloud SQL socket)
    * ``require`` (Neon/Supabase)-> TLS without cert validation
    * ``verify-ca``/``verify-full`` -> CA + optional mTLS verification
    """
    sslmode = pg.get("sslmode")
    if not sslmode or pg.get("unix_sock"):
        return None

    if sslmode in ("verify-ca", "verify-full"):
        ctx = ssl.create_default_context(cafile=pg.get("sslrootcert"))
        if sslmode == "verify-ca":
            ctx.check_hostname = False
        cert_path = pg.get("sslcert")
        key_path = pg.get("sslkey")
        if cert_path and key_path:
            ctx.load_cert_chain(cert_path, key_path)
        return ctx

    # require / prefer / allow: encrypt but don't pin certificates
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


class UserStore:
    """Tiny user persistence with two interchangeable backends:

    * SQLite (stdlib) when ``database_url`` is empty.
    * PostgreSQL via pg8000 (pure-Python driver) when ``database_url`` is set.
    """

    def __init__(self, db_path: str, database_url: str = "") -> None:
        self.is_postgres = bool(database_url.strip())
        if self.is_postgres:
            self._pg = _parse_database_url(database_url)
            # /tmp is the only writable area in Cloud Run (tmpfs). Override the hardcoded backend/ path.
            self.secret_dir = Path("/tmp/app-data")
            self._init_pg_schema()
        else:
            path = Path(db_path)
            if not path.is_absolute():
                path = BACKEND_DIR / path
            path.parent.mkdir(parents=True, exist_ok=True)
            self.db_path = str(path)
            self.secret_dir = path.parent
            self._init_sqlite_schema()

    # -- connection helpers ---------------------------------------------------
    def _connect_sqlite(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _connect_postgres(self):
        import pg8000.dbapi

        kwargs: dict[str, Any] = {
            "user": self._pg["user"],
            "password": self._pg["password"],
            "database": self._pg["database"],
            "timeout": 15,
        }

        # --- Cloud SQL unix-socket path (production default) -------------------
        if self._pg.get("unix_sock"):
            kwargs["unix_sock"] = self._pg["unix_sock"]
            # Unix sockets don't need SSL — Cloud SQL is VPC-private
            kwargs.pop("ssl", None)
            conn = pg8000.dbapi.connect(**kwargs)
            conn.autocommit = True
            return conn

        # --- External Postgres (Neon / Supabase / etc.) via TCP ---------------
        kwargs["ssl_context"] = _pg_ssl_context(self._pg)
        if self._pg.get("host"):
            kwargs["host"] = self._pg["host"]
            kwargs["port"] = self._pg["port"] or 5432

        conn = pg8000.dbapi.connect(**kwargs)
        conn.autocommit = True
        return conn

    def _connect(self):
        if self.is_postgres:
            return self._connect_postgres()
        return self._connect_sqlite()

    @property
    def ph(self) -> str:
        """Parameter placeholder for the active dialect."""
        return "%s" if self.is_postgres else "?"

    def _row(self, cur: Any, row: Any) -> dict[str, Any]:
        if self.is_postgres:
            return _pg_row_to_dict(cur, row)
        return dict(row)

    # -- schema ---------------------------------------------------------------
    def _init_sqlite_schema(self) -> None:
        with self._connect_sqlite() as conn:
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

    def _init_pg_schema(self) -> None:
        conn = self._connect_postgres()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id BIGSERIAL PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL DEFAULT '',
                    password_hash TEXT NOT NULL,
                    password_salt TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    must_change_password BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TEXT NOT NULL,
                    last_login_at TEXT
                )
                """
            )
            cur.close()
        finally:
            conn.close()

    # -- queries --------------------------------------------------------------
    def count_users(self) -> int:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM users")
            return int(cur.fetchone()[0])
        finally:
            conn.close()

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
        params = (
            username,
            display_name,
            email,
            hash_password(password, salt),
            salt,
            role,
            True if self.is_postgres else 1,
            bool(must_change_password),
            now,
        )
        conn = self._connect()
        try:
            cur = conn.cursor()
            try:
                if self.is_postgres:
                    cur.execute(
                        """
                        INSERT INTO users
                            (username, display_name, email, password_hash, password_salt,
                             role, is_active, must_change_password, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        params,
                    )
                    user_id = cur.fetchone()[0]
                else:
                    cur.execute(
                        """
                        INSERT INTO users
                            (username, display_name, email, password_hash, password_salt,
                             role, is_active, must_change_password, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        params,
                    )
                    user_id = cur.lastrowid
            except sqlite3.IntegrityError as exc:
                raise AuthError("A user with that username already exists.") from exc
            except Exception as exc:
                if exc.__class__.__name__ == "IntegrityError":
                    raise AuthError("A user with that username already exists.") from exc
                raise
            conn.commit()
        finally:
            conn.close()
        return self.get_by_id(user_id)

    def get_by_username(self, username: str) -> Optional[dict[str, Any]]:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM users WHERE username = {self.ph}", (username,))
            row = cur.fetchone()
            return self._row(cur, row) if row else None
        finally:
            conn.close()

    def get_by_id(self, user_id: int) -> Optional[dict[str, Any]]:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM users WHERE id = {self.ph}", (user_id,))
            row = cur.fetchone()
            return self._row(cur, row) if row else None
        finally:
            conn.close()

    def list_users(self) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            cur = conn.cursor()
            sql = (
                "SELECT * FROM users ORDER BY lower(username)"
                if self.is_postgres
                else "SELECT * FROM users ORDER BY username COLLATE NOCASE"
            )
            cur.execute(sql)
            return [self._row(cur, r) for r in cur.fetchall()]
        finally:
            conn.close()

    def update_user(self, user_id: int, fields: dict[str, Any]) -> Optional[dict[str, Any]]:
        allowed = {"display_name", "email", "role", "is_active"}
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not updates:
            return self.get_by_id(user_id)
        sets = ", ".join(f"{key} = {self.ph}" for key in updates)
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(f"UPDATE users SET {sets} WHERE id = {self.ph}", (*updates.values(), user_id))
            conn.commit()
        finally:
            conn.close()
        return self.get_by_id(user_id)

    def set_password(self, user_id: int, new_password: str, must_change: bool = False) -> None:
        salt = generate_salt()
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(
                f"UPDATE users SET password_hash = {self.ph}, password_salt = {self.ph}, "
                f"must_change_password = {self.ph} WHERE id = {self.ph}",
                (hash_password(new_password, salt), salt, bool(must_change), user_id),
            )
            conn.commit()
        finally:
            conn.close()

    def record_login(self, user_id: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(f"UPDATE users SET last_login_at = {self.ph} WHERE id = {self.ph}", (now, user_id))
            conn.commit()
        finally:
            conn.close()

    def delete_user(self, username: str) -> bool:
        """Permanently remove a user by username. Returns True if a row was deleted."""
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(f"DELETE FROM users WHERE username = {self.ph}", (username,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


class AuthService:
    """High-level auth operations used by the API routes + dependencies."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = UserStore(settings.auth_db_path, settings.database_url)
        self._secret: Optional[str] = None

    @property
    def jwt_secret(self) -> str:
        if self._secret is None:
            self._secret = self._resolve_secret()
        return self._secret

    def _resolve_secret(self) -> str:
        if self.settings.jwt_secret.strip():
            return self.settings.jwt_secret.strip()
        secret_file = self.store.secret_dir / ".jwt_secret"
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

