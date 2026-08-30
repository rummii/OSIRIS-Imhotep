"""SOW document persistence: save, list, update, delete, and export.

Documents are stored locally in the same SQLite/Postgres DB as the user table,
so they travel together and are cleaned up automatically when a user is deleted.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.config import Settings
from app.models.schemas import SowResponse

logger = logging.getLogger("osiris.sow")

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent  # backend/


# ---------------------------------------------------------------------------
# SowStore - low-level CRUD against SQLite or Postgres
# ---------------------------------------------------------------------------

class SowStore:
    """SQLite (default) or Postgres CRUD for ``sow_documents``."""

    def __init__(self, db_path: str, database_url: str = "") -> None:
        self.is_postgres = bool(database_url.strip())
        if self.is_postgres:
            from app.services.auth_service import _parse_database_url
            self._pg = _parse_database_url(database_url)
            self._init_pg_schema()
        else:
            self.db_path = Path(db_path)
            if not self.db_path.is_absolute():
                self.db_path = BACKEND_DIR / self.db_path
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_sqlite_schema()

    @property
    def secret_dir(self) -> Path:
        if self.is_postgres:
            return Path("/tmp/app-data")
        return BACKEND_DIR / ".secrets"

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

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

    def _init_sqlite_schema(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS sow_documents (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id       INTEGER NOT NULL,
                    sow_id        INTEGER,
                    title         TEXT NOT NULL,
                    content_md    TEXT NOT NULL,
                    content_plain TEXT NOT NULL,
                    is_published  INTEGER NOT NULL DEFAULT 0,
                    created_at    TEXT NOT NULL,
                    updated_at    TEXT NOT NULL,
                    spatial_context TEXT,
                    sow_json      TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )"""
            )
            # Idempotent migration for existing tables pre-Phase 3.
            for stmt in (
                "ALTER TABLE sow_documents ADD COLUMN spatial_context TEXT",
                "ALTER TABLE sow_documents ADD COLUMN sow_json TEXT",
            ):
                try:
                    conn.execute(stmt)
                except Exception:
                    pass  # column already exists
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sow_user ON sow_documents(user_id)")
            conn.commit()
        finally:
            conn.close()

    def _init_pg_schema(self) -> None:
        conn = self._pg_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                """CREATE TABLE IF NOT EXISTS sow_documents (
                    id            SERIAL PRIMARY KEY,
                    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    sow_id        INTEGER,
                    title         TEXT NOT NULL,
                    content_md    TEXT NOT NULL,
                    content_plain TEXT NOT NULL,
                    is_published  INTEGER NOT NULL DEFAULT 0,
                    created_at    TEXT NOT NULL,
                    updated_at    TEXT NOT NULL,
                    spatial_context TEXT,
                    sow_json      TEXT
                )"""
            )
            # Idempotent migration for already-existing tables.
            for stmt in (
                "ALTER TABLE sow_documents ADD COLUMN IF NOT EXISTS spatial_context TEXT",
                "ALTER TABLE sow_documents ADD COLUMN IF NOT EXISTS sow_json TEXT",
            ):
                try:
                    cur.execute(stmt)
                except Exception:
                    pass
            cur.execute("CREATE INDEX IF NOT EXISTS idx_sow_user ON sow_documents(user_id)")
            conn.commit()
        finally:
            cur.close()
            conn.close()

    @staticmethod
    def _pg_row_to_dict(cur, row) -> dict[str, Any]:
        if row is None:
            return {}
        columns = [d[0] for d in cur.description]
        return dict(zip(columns, row))

    def create(
        self,
        user_id: int,
        title: str,
        content_md: str,
        content_plain: str,
        sow_id: int | None = None,
        is_published: bool = False,
        spatial_context: str | None = None,
        sow_json: str | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        if self.is_postgres:
            conn = self._pg_conn()
            try:
                cur = conn.cursor()
                cur.execute(
                    """INSERT INTO sow_documents
                       (user_id, sow_id, title, content_md, content_plain, is_published,
                        created_at, updated_at, spatial_context, sow_json)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING *""",
                    (user_id, sow_id, title, content_md, content_plain,
                     1 if is_published else 0, now, now, spatial_context, sow_json),
                )
                row = cur.fetchone()
                conn.commit()
                return self._pg_row_to_dict(cur, row) if row else {}
            finally:
                cur.close()
                conn.close()
        else:
            conn = self._connect()
            try:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO sow_documents "
                    "(user_id, sow_id, title, content_md, content_plain, is_published, "
                    "created_at, updated_at, spatial_context, sow_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_id, sow_id, title, content_md, content_plain,
                     1 if is_published else 0, now, now, spatial_context, sow_json),
                )
                doc_id = cur.lastrowid
                conn.commit()
                return self.get(doc_id) or {}
            finally:
                conn.close()


    def get(self, doc_id: int, owner_id: int | None = None) -> dict[str, Any] | None:
        if self.is_postgres:
            conn = self._pg_conn()
            try:
                cur = conn.cursor()
                if owner_id is not None:
                    cur.execute(
                        "SELECT * FROM sow_documents WHERE id=%s AND user_id=%s",
                        (doc_id, owner_id),
                    )
                else:
                    cur.execute("SELECT * FROM sow_documents WHERE id=%s", (doc_id,))
                row = cur.fetchone()
                return self._pg_row_to_dict(cur, row) if row else None
            finally:
                cur.close()
                conn.close()
        else:
            conn = self._connect()
            try:
                cur = conn.cursor()
                if owner_id is not None:
                    cur.execute(
                        "SELECT * FROM sow_documents WHERE id=? AND user_id=?",
                        (doc_id, owner_id),
                    )
                else:
                    cur.execute("SELECT * FROM sow_documents WHERE id=?", (doc_id,))
                row = cur.fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    def list_for_user(self, user_id: int) -> list[dict[str, Any]]:
        if self.is_postgres:
            conn = self._pg_conn()
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT * FROM sow_documents WHERE user_id=%s ORDER BY created_at DESC",
                    (user_id,),
                )
                return [self._pg_row_to_dict(cur, r) for r in cur.fetchall()]
            finally:
                cur.close()
                conn.close()
        else:
            conn = self._connect()
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT * FROM sow_documents WHERE user_id=? ORDER BY created_at DESC",
                    (user_id,),
                )
                return [dict(r) for r in cur.fetchall()]
            finally:
                conn.close()

    def list_all(self) -> list[dict[str, Any]]:
        if self.is_postgres:
            conn = self._pg_conn()
            try:
                cur = conn.cursor()
                cur.execute("SELECT * FROM sow_documents ORDER BY created_at DESC")
                return [self._pg_row_to_dict(cur, r) for r in cur.fetchall()]
            finally:
                cur.close()
                conn.close()
        else:
            conn = self._connect()
            try:
                cur = conn.cursor()
                cur.execute("SELECT * FROM sow_documents ORDER BY created_at DESC")
                return [dict(r) for r in cur.fetchall()]
            finally:
                conn.close()


    def update(
        self, doc_id: int, owner_id: int | None, fields: dict[str, Any]
    ) -> dict[str, Any] | None:
        if not fields:
            return self.get(doc_id, owner_id)
        fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        fields.pop("user_id", None)
        fields.pop("id", None)
        fields.pop("created_at", None)
        if "is_published" in fields:
            fields["is_published"] = 1 if fields["is_published"] else 0

        if self.is_postgres:
            conn = self._pg_conn()
            try:
                cur = conn.cursor()
                set_clause = ", ".join([f"{k}=%s" for k in fields])
                values = list(fields.values())
                if owner_id is not None:
                    cur.execute(
                        f"UPDATE sow_documents SET {set_clause} WHERE id=%s AND user_id=%s",
                        (*values, doc_id, owner_id),
                    )
                else:
                    cur.execute(
                        f"UPDATE sow_documents SET {set_clause} WHERE id=%s",
                        (*values, doc_id),
                    )
                conn.commit()
                if cur.rowcount == 0:
                    return None
                return self.get(doc_id)
            finally:
                cur.close()
                conn.close()
        else:
            conn = self._connect()
            try:
                cur = conn.cursor()
                set_clause = ", ".join([f"{k}=?" for k in fields])
                values = list(fields.values())
                if owner_id is not None:
                    cur.execute(
                        f"UPDATE sow_documents SET {set_clause} WHERE id=? AND user_id=?",
                        (*values, doc_id, owner_id),
                    )
                else:
                    cur.execute(
                        f"UPDATE sow_documents SET {set_clause} WHERE id=?",
                        (*values, doc_id),
                    )
                conn.commit()
                if cur.rowcount == 0:
                    return None
                return self.get(doc_id)
            finally:
                conn.close()

    def delete(self, doc_id: int, owner_id: int | None) -> bool:
        if self.is_postgres:
            conn = self._pg_conn()
            try:
                cur = conn.cursor()
                if owner_id is not None:
                    cur.execute(
                        "DELETE FROM sow_documents WHERE id=%s AND user_id=%s",
                        (doc_id, owner_id),
                    )
                else:
                    cur.execute("DELETE FROM sow_documents WHERE id=%s", (doc_id,))
                conn.commit()
                return cur.rowcount > 0
            finally:
                cur.close()
                conn.close()
        else:
            conn = self._connect()
            try:
                cur = conn.cursor()
                if owner_id is not None:
                    cur.execute(
                        "DELETE FROM sow_documents WHERE id=? AND user_id=?",
                        (doc_id, owner_id),
                    )
                else:
                    cur.execute("DELETE FROM sow_documents WHERE id=?", (doc_id,))
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()


# ---------------------------------------------------------------------------
# SowService - high-level ops used by routes
# ---------------------------------------------------------------------------

class SowService:
    """High-level SOW document operations with auth checks."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = SowStore(settings.auth_db_path, settings.database_url)

    @staticmethod
    def to_list_item(row: dict[str, Any]) -> dict[str, Any]:
        def _to_iso(value: Any) -> str:
            if value is None:
                return ""
            return str(value)

        def _to_int_or_none(value: Any) -> int | None:
            if value is None or value == "":
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                try:
                    return int(float(value))
                except (TypeError, ValueError):
                    return None

        return {
            "id": row["id"],
            "title": row["title"],
            "created_at": _to_iso(row.get("created_at")),
            "updated_at": _to_iso(row.get("updated_at")),
            "is_published": bool(row["is_published"]),
            "sow_id": _to_int_or_none(row.get("sow_id")),
        }

    @staticmethod
    def to_detail(row: dict[str, Any]) -> dict[str, Any]:
        def _to_str(value: Any, default: str = "") -> str:
            if value is None:
                return default
            return str(value)

        def _to_int(value: Any) -> int:
            if value is None or value == "":
                return 0
            try:
                return int(value)
            except (TypeError, ValueError):
                try:
                    return int(float(value))
                except (TypeError, ValueError):
                    return 0

        def _to_int_or_none(value: Any) -> int | None:
            if value is None or value == "":
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                try:
                    return int(float(value))
                except (TypeError, ValueError):
                    return None

        def _to_json(value: Any) -> dict | None:
            """Best-effort JSON decode. The ``spatial_context`` column may be
            either a string (SQLite / JSONB-as-text) or already a dict (PG JSONB)."""
            if value is None or value == "":
                return None
            if isinstance(value, dict):
                return value
            try:
                import json as _json
                return _json.loads(value)
            except (TypeError, ValueError):
                return None

        return {
            "id": _to_int(row["id"]),
            "user_id": _to_int(row["user_id"]),
            "sow_id": _to_int_or_none(row.get("sow_id")),
            "title": _to_str(row.get("title")),
            "content_md": _to_str(row.get("content_md")),
            "content_plain": _to_str(row.get("content_plain")),
            "created_at": _to_str(row.get("created_at")),
            "updated_at": _to_str(row.get("updated_at")),
            "is_published": bool(row.get("is_published")),
            "sow": _to_json(row.get("sow_json")),
            "spatial_context": _to_json(row.get("spatial_context")),
        }


    def save_from_sow(
        self,
        user_id: int,
        sow_dict: dict[str, Any],
        sow_id: int | None = None,
        spatial_context: str | None = None,
    ) -> dict[str, Any]:
        # Tolerant validation: strip unknown fields and coerce missing ones to defaults.
        # The frontend sends the raw SowResponse JSON (no validation), and the
        # Gemini-generated SOW may include optional fields we don't model.
        try:
            sow = SowResponse.model_validate(sow_dict)
        except Exception:
            try:
                sow = SowResponse.model_construct(**{
                    k: v for k, v in sow_dict.items() if k in SowResponse.model_fields
                })
            except Exception:
                # Last resort: a minimal SOW
                sow = SowResponse(project_title=str(sow_dict.get("project_title", "Untitled Scope of Work")))
        content_md = _sow_to_markdown(sow)
        content_plain = _sow_to_plaintext(sow)
        title = str(sow.project_title or "Untitled Scope of Work")
        # Persist the structured JSON so /sow/{id} can return it without re-parsing.
        import json as _json
        sow_json = _json.dumps(sow.model_dump(mode="json"))
        try:
            row = self.store.create(
                user_id=user_id,
                title=title,
                content_md=content_md,
                content_plain=content_plain,
                sow_id=sow_id,
                is_published=False,
                spatial_context=spatial_context,
                sow_json=sow_json,
            )
        except Exception as exc:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Could not persist SOW: {exc}",
            ) from exc
        return row

    def assert_owner(self, doc_id: int, user: dict[str, Any]) -> dict[str, Any]:
        from fastapi import HTTPException, status
        row = self.store.get(doc_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
        if user["role"] != "superadmin" and row["user_id"] != user["id"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this document.")
        return row


# ---------------------------------------------------------------------------
# Markdown / plaintext helpers
# ---------------------------------------------------------------------------

def _sow_to_markdown(sow: SowResponse) -> str:
    """Convert a SowResponse into a Markdown string for storage."""
    lines: list[str] = []
    lines.append(f"# {sow.project_title}")
    if sow.site or sow.client:
        meta: list[str] = []
        if sow.site:
            meta.append(f"**Site:** {sow.site}")
        if sow.client:
            meta.append(f"**Client:** {sow.client}")
        lines.append("  " + "\u00b7".join(meta))
    if sow.generated_at:
        lines.append(f"**Generated:** {sow.generated_at}")
    lines.append("")

    es = sow.executive_summary
    if es:
        lines.append("## Executive Summary")
        if es.overview:
            lines.append(f"\n{es.overview}\n")
        if es.overall_condition:
            lines.append(f"**Overall Condition:** {es.overall_condition}\n")

    if sow.visual_findings:
        lines.append("## Visual Findings")
        for vf in sow.visual_findings:
            lines.append(f"### {vf.location}")
            if vf.description:
                lines.append(f"**Description:** {vf.description}")
            if vf.severity:
                lines.append(f"**Severity:** {vf.severity}")
            if vf.recommended_action:
                lines.append(f"**Recommended Action:** {vf.recommended_action}")
            lines.append("")

    if sow.recommended_services:
        lines.append("## Recommended Services")
        for svc in sow.recommended_services:
            asset = svc.asset if getattr(svc, "asset", None) else "General"
            lines.append(
                f"- **{svc.service}** (Asset: {asset}, Priority: {svc.priority}) - "
                f"{sow.cost_breakdown.currency} {svc.total_cost:,.2f}"
            )
            notes = getattr(svc, "notes", None) or getattr(svc, "description", None)
            if notes:
                lines.append(f"  {notes}")
        lines.append("")

    if sow.scope_breakdown:
        lines.append("## Scope of Work")
        for scope in sow.scope_breakdown:
            heading = scope.phase or "Phase"
            lines.append(f"### {heading}")
            if scope.work_description:
                lines.append(f"\n{scope.work_description}\n")
        lines.append("")

    cb = sow.cost_breakdown
    lines.append("## Cost Breakdown")
    lines.append("| Item | Amount |")
    lines.append("|-------|--------|")
    lines.append(f"| Labor | {cb.currency} {cb.labor:,.2f} |")
    lines.append(f"| Materials | {cb.currency} {cb.materials:,.2f} |")
    lines.append(f"| Equipment | {cb.currency} {cb.equipment:,.2f} |")
    lines.append(f"| **Subtotal** | **{cb.currency} {cb.subtotal:,.2f}** |")
    if cb.contingency_pct:
        lines.append(f"| Contingency ({cb.contingency_pct}%) | {cb.currency} {cb.contingency:,.2f} |")
    lines.append(f"| **Total** | **{cb.currency} {cb.total:,.2f}** |")
    lines.append("")
    return "\n".join(lines)


def _sow_to_plaintext(sow: SowResponse) -> str:
    """Serialize SowResponse as JSON for use by the Google Docs exporter."""
    return sow.model_dump_json(indent=2)


# ---------------------------------------------------------------------------
# .docx export — re-exported from export_service (backward compat)
# ---------------------------------------------------------------------------

from app.services.export_service import export_to_docx
