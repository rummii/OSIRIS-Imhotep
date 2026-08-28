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
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )"""
            )
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
                    updated_at    TEXT NOT NULL
                )"""
            )
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
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        if self.is_postgres:
            conn = self._pg_conn()
            try:
                cur = conn.cursor()
                cur.execute(
                    """INSERT INTO sow_documents
                       (user_id, sow_id, title, content_md, content_plain, is_published, created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING *""",
                    (user_id, sow_id, title, content_md, content_plain,
                     1 if is_published else 0, now, now),
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
                    "(user_id, sow_id, title, content_md, content_plain, is_published, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_id, sow_id, title, content_md, content_plain,
                     1 if is_published else 0, now, now),
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
        }


    def save_from_sow(
        self,
        user_id: int,
        sow_dict: dict[str, Any],
        sow_id: int | None = None,
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
        try:
            row = self.store.create(
                user_id=user_id,
                title=title,
                content_md=content_md,
                content_plain=content_plain,
                sow_id=sow_id,
                is_published=False,
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
# .docx export (works everywhere, no Google account required)
# ---------------------------------------------------------------------------

def export_to_docx(content_md: str, title: str) -> bytes:
    """Build a valid .docx from the stored SOW Markdown.

    Google service accounts cannot create Docs/Drive files in standalone
    (non-Workspace) projects, so this is the always-working export path:
    the user downloads the file and can open it anywhere (Word, LibreOffice)
    or upload it to their own Google Drive to get a Google Doc.
    """
    import re
    import io
    import zipfile

    def esc(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    def run(text: str) -> str:
        # Inline **bold** support.
        text = esc(text)
        out: list[str] = []
        for i, chunk in enumerate(re.split(r"\*\*(.+?)\*\*", text)):
            if i % 2 == 1:
                out.append(f"<w:r><w:rPr><w:b/></w:rPr><w:t>{chunk}</w:t></w:r>")
            elif chunk:
                out.append(f"<w:r><w:t>{chunk}</w:t></w:r>")
        return "".join(out)

    body: list[str] = [f'<w:p><w:r><w:rPr><w:b/><w:sz w:val="32"/></w:rPr><w:t>{esc(title)}</w:t></w:r></w:p>']

    rows: list[list[str]] = []
    for line in content_md.splitlines():
        line = line.rstrip()
        if not line.strip():
            continue
        if line.startswith("|"):
            cells = [c.strip().lstrip("**").rstrip("**") for c in line.strip().strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue  # separator row
            rows.append(cells)
            continue
        if line.startswith("###"):
            body.append(f'<w:p><w:r><w:rPr><w:b/><w:sz w:val="26"/></w:rPr><w:t>{esc(line[3:].strip())}</w:t></w:r></w:p>')
        elif line.startswith("##"):
            body.append(f'<w:p><w:r><w:rPr><w:b/><w:sz w:val="28"/></w:rPr><w:t>{esc(line[2:].strip())}</w:t></w:r></w:p>')
        elif line.startswith("#"):
            body.append(f'<w:p><w:r><w:rPr><w:b/><w:sz w:val="32"/></w:rPr><w:t>{esc(line[1:].strip())}</w:t></w:r></w:p>')
        elif line.startswith("- "):
            body.append(f'<w:p><w:r><w:t>• {run(line[2:].strip())}</w:t></w:r></w:p>')
        else:
            body.append(f"<w:p>{run(line)}</w:p>")

    if rows:
        body.append("<w:p/>")
        grid = "".join(f'<w:gridCol w:w="{int(6200 / len(rows[0]))}"/>' for _ in rows[0])
        body.append("<w:tbl><w:tblGrid>" + grid + "</w:tblGrid>")
        for ri, row in enumerate(rows):
            body.append("<w:tr>")
            for cell in row:
                bold = "<w:rPr><w:b/></w:rPr>" if ri == 0 else ""
                body.append(
                    f'<w:tc><w:tcPr><w:tcW w:w="{int(6200 / len(rows[0]))}" w:type="dxa"/></w:tcPr>'
                    f"<w:p><w:r>{bold}<w:t>{esc(cell)}</w:t></w:r></w:p></w:tc>"
                )
            body.append("</w:tr>")
        body.append("</w:tbl>")
    body.append("<w:p/>")

    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        + "".join(body)
        + '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>'
        "</w:body></w:document>"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
            "</Types>"))
        z.writestr("_rels/.rels", (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="word/styles.xml"/>'
            "</Relationships>"))
        z.writestr("word/_rels/document.xml.rels", (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            "</Relationships>"))
        z.writestr("word/styles.xml", (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
            '<w:name w:val="Normal"/><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/></w:rPr>'
            "</w:style></w:styles>"))
        z.writestr("word/document.xml", document_xml)
    return buf.getvalue()


