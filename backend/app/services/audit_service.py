"""Audit logging - append-only record of security-sensitive events.

The table lives in the same SQLite/Postgres DB as the user store so that the
entire audit trail is a single file that can be copied/shipped for compliance.
Audit writes are best-effort: any exception is swallowed so that audit
failures can never break a user request.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.config import Settings

logger = logging.getLogger("osiris.audit")

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent  # backend/


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class AuditStore:
    """CRUD for ``audit_log`` in SQLite (default) or Postgres."""

    def __init__(self, auth_db_path: str, database_url: str = "") -> None:
        self.is_postgres = bool(database_url.strip())
        if self.is_postgres:
            from app.services.auth_service import _parse_database_url

            self._pg = _parse_database_url(database_url)
            self._init_pg_schema()
        else:
            db_path = Path(auth_db_path)
            if not db_path.is_absolute():
                db_path = BACKEND_DIR / auth_db_path
            self.db_path = db_path
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_sqlite_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_sqlite_schema(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts           TEXT NOT NULL,
                    user_id      INTEGER,
                    username     TEXT,
                    role         TEXT,
                    action       TEXT NOT NULL,
                    target_type  TEXT,
                    target_id    TEXT,
                    outcome      TEXT NOT NULL,
                    detail       TEXT,
                    ip_address   TEXT
                )
                """
            )
            for idx_sql in (
                "CREATE INDEX IF NOT EXISTS idx_audit_user_ts  ON audit_log(user_id, ts)",
                "CREATE INDEX IF NOT EXISTS idx_audit_action_ts ON audit_log(action, ts)",
                "CREATE INDEX IF NOT EXISTS idx_audit_ts        ON audit_log(ts)",
            ):
                conn.execute(idx_sql)
            conn.commit()
        finally:
            conn.close()

    def _pg_conn(self):
        import pg8000
        from app.services.auth_service import _pg_ssl_context

        opts = self._pg
        return pg8000.connect(
            user=opts["user"],
            password=opts["password"],
            database=opts["database"],
            host=opts["host"] or "localhost",
            port=opts["port"] or 5432,
            unix_sock=opts.get("unix_sock") or None,
            ssl_context=_pg_ssl_context(opts),
        )

    def _init_pg_schema(self) -> None:
        conn = self._pg_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id           SERIAL PRIMARY KEY,
                    ts           TEXT NOT NULL,
                    user_id      INTEGER,
                    username     TEXT,
                    role         TEXT,
                    action       TEXT NOT NULL,
                    target_type  TEXT,
                    target_id    TEXT,
                    outcome      TEXT NOT NULL,
                    detail       TEXT,
                    ip_address   TEXT
                )
                """
            )
            for idx_sql in (
                "CREATE INDEX IF NOT EXISTS idx_audit_user_ts  ON audit_log(user_id, ts)",
                "CREATE INDEX IF NOT EXISTS idx_audit_action_ts ON audit_log(action, ts)",
                "CREATE INDEX IF NOT EXISTS idx_audit_ts        ON audit_log(ts)",
            ):
                try:
                    cur.execute(idx_sql)
                except Exception:
                    pass
            conn.commit()
        finally:
            conn.close()

    def insert(self, *, ts: str, user_id: Optional[int], username: Optional[str],
               role: Optional[str], action: str, target_type: Optional[str],
               target_id: Optional[str], outcome: str, detail: Optional[str],
               ip_address: Optional[str]) -> None:
        try:
            if self.is_postgres:
                conn = self._pg_conn()
            else:
                conn = self._connect()
            try:
                cur = conn.cursor()
                cur.execute(
                    """INSERT INTO audit_log
                        (ts, user_id, username, role, action, target_type,
                         target_id, outcome, detail, ip_address)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (ts, user_id, username, role, action,
                     target_type, target_id, outcome, detail, ip_address),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            logger.warning("AuditStore.insert failed - audit event dropped", exc_info=True)

    def list(self, *, user_id: Optional[int] = None, action: Optional[str] = None,
             since: Optional[str] = None, until: Optional[str] = None,
             limit: int = 200, offset: int = 0) -> list:
        conditions = []
        params = []
        if user_id is not None:
            conditions.append("user_id = ?")
            params.append(user_id)
        if action is not None:
            conditions.append("action = ?")
            params.append(action)
        if since is not None:
            conditions.append("ts >= ?")
            params.append(since)
        if until is not None:
            conditions.append("ts <= ?")
            params.append(until)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params.extend([limit, offset])
        if self.is_postgres:
            conn = self._pg_conn()
        else:
            conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(
                f"""SELECT id, ts, user_id, username, role, action,
                           target_type, target_id, outcome, detail, ip_address
                      FROM audit_log {where}
                      ORDER BY ts DESC LIMIT ? OFFSET ?""",
                params,
            )
            if self.is_postgres:
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def count(self, *, user_id: Optional[int] = None, action: Optional[str] = None) -> int:
        conditions = []
        params = []
        if user_id is not None:
            conditions.append("user_id = ?")
            params.append(user_id)
        if action is not None:
            conditions.append("action = ?")
            params.append(action)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        if self.is_postgres:
            conn = self._pg_conn()
        else:
            conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM audit_log {where}", params)
            row = cur.fetchone()
            return int(row[0]) if row else 0
        finally:
            conn.close()


class AuditService:
    """Best-effort append-only audit logger."""

    def __init__(self, settings: Settings) -> None:
        self._store = AuditStore(settings.auth_db_path, settings.database_url)

    def log(self, action: str, *, user=None, target_type=None, target_id=None,
            outcome: str = "success", detail=None, ip_address=None,
            username=None, role=None) -> None:
        try:
            self._store.insert(
                ts=_utc_now(),
                user_id=user["id"] if user else None,
                username=username or (user.get("username") if user else None),
                role=role or (user.get("role") if user else None),
                action=action, target_type=target_type, target_id=target_id,
                outcome=outcome, detail=detail, ip_address=ip_address,
            )
        except Exception:
            logger.warning("AuditService.log failed - audit event dropped", exc_info=True)

    def list(self, *, user_id=None, action=None, since=None, until=None,
             limit: int = 200, offset: int = 0):
        return self._store.list(user_id=user_id, action=action, since=since,
                                until=until, limit=limit, offset=offset)

    def count(self, *, user_id=None, action=None):
        return self._store.count(user_id=user_id, action=action)
