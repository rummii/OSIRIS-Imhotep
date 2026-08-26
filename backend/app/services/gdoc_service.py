"""Google Docs export: turn a validated ``SowResponse`` into a styled Google
Doc and hand back a live ``docs.google.com/document/d/<id>/edit`` URL.

Auth options (MVP):
  * Service Account key file (``GOOGLE_SERVICE_ACCOUNT_FILE``). Service
    accounts create + own docs; for a finished document the doc is shared
    with the requesting engineer's ``owner_email`` (drive.permissions.create)
    or created under a real user via domain-wide delegation
    (``GOOGLE_DOCS_IMPERSONATE``).
  * OAuth user token file (``GOOGLE_OAUTH_TOKEN_FILE``) from the standard
    Google API client library flow.

The exporter builds the document in a few sequential ``batchUpdate`` calls
(append text, insert a table, then fill its cells by locating each cell's
segment id from ``documents.get``). This keeps index arithmetic trivial.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import Settings
from app.models.schemas import SowResponse

logger = logging.getLogger("osiris.gdoc")

# backend/ (parent of app/) — used to resolve credential paths from .env
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


def _resolve_credential_path(value: str) -> str:
    """Resolve a credential path from .env relative to the backend directory,
    so it works no matter what the current working directory is."""
    path = Path(value.strip())
    if not path.is_absolute():
        path = BACKEND_DIR / path
    return str(path)

DOCS_SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]

FONT = "Arial"

# Small rgb helpers ----------------------------------------------------------
def _rgb(r: float, g: float, b: float) -> dict[str, Any]:
    return {"red": r, "green": g, "blue": b}


ACCENT = _rgb(0.13, 0.36, 0.71)     # engineering blue
DARK = _rgb(0.16, 0.20, 0.27)
MUTED = _rgb(0.42, 0.46, 0.53)


class GdocNotConfiguredError(RuntimeError):
    """Raised when no Google credentials are configured for export."""


CURRENCY_SYMBOLS = {"PHP": "₱", "USD": "$"}


def _money(value: float, currency: str) -> str:
    symbol = CURRENCY_SYMBOLS.get(currency, f"{currency} ")
    try:
        return f"{symbol}{float(value):,.2f}"
    except (TypeError, ValueError):
        return f"{symbol}0.00"


class GoogleDocsService:
    """Creates and fills a styled Google Doc from a SOW payload."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.docs = None
        self.drive = None
        self._authenticate()

    # -- auth -------------------------------------------------------------------
    def _authenticate(self) -> None:
        creds = None
        sa_file = _resolve_credential_path(self.settings.google_service_account_file) if self.settings.google_service_account_file.strip() else ""
        oauth_file = _resolve_credential_path(self.settings.google_oauth_token_file) if self.settings.google_oauth_token_file.strip() else ""
        impersonate = self.settings.google_docs_impersonate.strip()

        if sa_file:
            creds = service_account.Credentials.from_service_account_file(sa_file, scopes=DOCS_SCOPES)
            if impersonate:
                creds = creds.with_subject(impersonate)
        elif oauth_file:
            creds = Credentials.from_authorized_user_file(oauth_file, DOCS_SCOPES)
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())

        if creds is None:
            raise GdocNotConfiguredError(
                "Google Docs export is not configured. Set GOOGLE_SERVICE_ACCOUNT_FILE "
                "(recommended) or GOOGLE_OAUTH_TOKEN_FILE in backend/.env."
            )

        self.docs = build("docs", "v1", credentials=creds)
        self.drive = build("drive", "v3", credentials=creds)

    def is_configured(self) -> bool:
        return self.docs is not None and self.drive is not None

    # -- main entry --------------------------------------------------------------
    def create_sow_document(self, sow: SowResponse, owner_email: Optional[str] = None) -> tuple[str, str]:
        """Create + populate a Google Doc and return ``(url, doc_id)``."""
        if not self.is_configured():
            raise GdocNotConfiguredError("Google Docs client is not initialised.")

        title = f"SOW — {sow.project_title}"
        try:
            doc = self.docs.documents().create(body={"title": title}).execute()
        except HttpError as exc:
            raise RuntimeError(f"Google Docs create failed: {exc}") from exc
        doc_id = doc["documentId"]

        self._write_document_body(doc_id, sow)

        if owner_email:
            try:
                self.drive.permissions().create(
                    fileId=doc_id,
                    body={"type": "user", "role": "writer", "emailAddress": owner_email},
                    fields="id",
                ).execute()
            except HttpError as exc:
                logger.warning("Could not share doc with %s: %s", owner_email, exc)

        return f"https://docs.google.com/document/d/{doc_id}/edit", doc_id

    # -- document body ------------------------------------------------------------
    def _write_document_body(self, doc_id: str, sow: SowResponse) -> None:
        currency = sow.currency or "PHP"

        # Title block ---------------------------------------------------------
        self._insert_text(doc_id, f"Scope of Work — {sow.project_title}\n",
                          size=22, bold=True, color=DARK, alignment="CENTER")
        meta = " | ".join(filter(None, [
            f"Client: {sow.client}" if sow.client else "",
            f"Site: {sow.site}" if sow.site else "",
            f"Currency: {currency}",
            sow.generated_at or "",
        ]))
        if meta:
            self._insert_text(doc_id, meta + "\n", size=10, color=MUTED, alignment="CENTER")
        self._insert_text(doc_id, "\n", size=8)

        # 1. Executive summary --------------------------------------------------
        self._insert_heading(doc_id, "1. Executive Summary", 1)
        self._insert_text(doc_id, sow.executive_summary.overview + "\n", size=11)
        if sow.executive_summary.priority_findings:
            self._insert_text(
                doc_id,
                f"Priority findings: {sow.executive_summary.priority_findings}\n",
                size=11,
            )
        self._insert_text(
            doc_id,
            f"Overall condition: {sow.executive_summary.overall_condition}\n",
            size=11,
            bold=True,
        )
        self._insert_text(doc_id, "\n", size=8)

        # 2. Visual findings ------------------------------------------------------
        self._insert_heading(doc_id, "2. Visual Findings", 1)
        if sow.visual_findings:
            headers = ["ID", "Asset", "Location", "Condition", "Severity", "Description", "Recommended Action"]
            rows = [
                [
                    f.get("id", ""), f.get("asset", ""), f.get("location", ""),
                    f.get("condition", ""), f.get("severity", ""),
                    f.get("description", ""), f.get("recommended_action", ""),
                ]
                for f in (f.model_dump() for f in sow.visual_findings)
            ]
            self._insert_table(doc_id, headers, rows)
        else:
            self._insert_text(doc_id, "No visual findings recorded.\n", size=11, italic=True)
        self._insert_text(doc_id, "\n", size=8)


        # 3. Recommended services -------------------------------------------------
        self._insert_heading(doc_id, "3. Recommended Services", 1)
        if sow.recommended_services:
            headers = ["ID", "Service", "Asset", "Priority", "Qty", "Unit", "Unit Cost", "Total Cost"]
            rows = [
                [
                    s.get("id", ""), s.get("service", ""), s.get("asset", ""),
                    s.get("priority", ""), str(s.get("quantity", "")), s.get("unit", ""),
                    _money(s.get("unit_cost", 0), currency),
                    _money(s.get("total_cost", 0), currency),
                ]
                for s in (s.model_dump() for s in sow.recommended_services)
            ]
            self._insert_table(doc_id, headers, rows)
        else:
            self._insert_text(doc_id, "No recommended services recorded.\n", size=11, italic=True)
        self._insert_text(doc_id, "\n", size=8)

        # 4. Scope breakdown --------------------------------------------------------
        self._insert_heading(doc_id, "4. Scope Breakdown", 1)
        for i, scope in enumerate(sow.scope_breakdown, start=1):
            phase = scope.phase or f"Phase {i}"
            self._insert_text(doc_id, f"{phase}\n", size=12, bold=True, color=ACCENT)
            self._insert_text(doc_id, scope.work_description + "\n", size=11)
            for deliverable in scope.deliverables:
                self._insert_text(doc_id, f"•  {deliverable}\n", size=10, color=DARK)
            if scope.duration_days:
                self._insert_text(doc_id, f"Duration: {scope.duration_days} days\n", size=10, italic=True)
            self._insert_text(doc_id, "\n", size=8)

        # 5. Estimated cost breakdown ------------------------------------------------
        self._insert_heading(doc_id, "5. Estimated Cost Breakdown", 1)
        cb = sow.cost_breakdown
        self._insert_table(
            doc_id,
            ["Item", f"Amount ({currency})"],
            [
                ["Labor", _money(cb.labor, currency)],
                ["Materials", _money(cb.materials, currency)],
                ["Equipment", _money(cb.equipment, currency)],
                ["Subtotal", _money(cb.subtotal, currency)],
                [f"Contingency ({cb.contingency_pct:.0f}%)", _money(cb.contingency, currency)],
                ["Total Estimated Cost", _money(cb.total, currency)],
            ],
        )
        self._insert_text(doc_id, "\n", size=8)

        # Footer ------------------------------------------------------------------
        self._insert_text(
            doc_id,
            "Generated by OSIRIS Imhotep — AI-assisted engineering SOW.\n"
            "Subject to final review by a licensed engineer before execution.\n",
            size=9,
            color=MUTED,
            italic=True,
        )


    # -- low-level helpers --------------------------------------------------------
    def _document_end_index(self, doc_id: str) -> int:
        doc = self.docs.documents().get(documentId=doc_id).execute()
        content = doc["body"]["content"]
        return content[-1]["endIndex"] if content else 1

    def _insert_text(
        self,
        doc_id: str,
        text: str,
        *,
        size: float = 11,
        bold: bool = False,
        italic: bool = False,
        color: Optional[dict[str, Any]] = None,
        alignment: Optional[str] = None,
    ) -> None:
        end = self._document_end_index(doc_id)
        # The Docs API rejects inserting AT the exact end index of the final
        # paragraph; insert just before its terminating newline instead.
        insert_index = max(end - 1, 0)
        start, stop = insert_index, insert_index + len(text)
        requests: list[dict[str, Any]] = [
            {"insertText": {"location": {"index": insert_index}, "text": text}}
        ]
        text_style: dict[str, Any] = {
            "weightedFontFamily": {"fontFamily": FONT, "weight": 400},
            "bold": bold,
            "italic": italic,
            "fontSize": {"magnitude": size, "unit": "PT"},
        }
        if color:
            text_style["foregroundColor"] = {"color": {"rgbColor": color}}
        fields = ["weightedFontFamily", "bold", "italic", "fontSize"]
        if color:
            fields.append("foregroundColor")
        requests.append({
            "updateTextStyle": {
                "range": {"startIndex": start, "endIndex": stop},
                "textStyle": text_style,
                "fields": ",".join(fields),
            }
        })
        if alignment:
            requests.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": start, "endIndex": stop},
                    "paragraphStyle": {"alignment": alignment},
                    "fields": "alignment",
                }
            })
        self.docs.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()

    def _insert_heading(self, doc_id: str, text: str, level: int) -> None:
        self._insert_text(doc_id, text + "\n", size=14, bold=True, color=ACCENT)


    def _insert_table(self, doc_id: str, headers: list[str], rows: list[list[str]]) -> None:
        """Insert a table and fill every cell with text (bold header row).

        Strategy: ``insertTable`` at the end of the document, re-read the doc
        to discover each cell's ``segmentId`` (every table cell lives in its
        own segment), then batch ``insertText`` + ``updateTextStyle`` per cell.
        """
        if not rows:
            return
        cols = len(headers) or len(rows[0])
        rows_count = len(rows) + 1
        end = self._document_end_index(doc_id)
        insert_index = max(end - 1, 0)  # insert before the final newline

        self.docs.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": [{
                "insertTable": {
                    "rows": rows_count,
                    "columns": cols,
                    "location": {"index": insert_index},
                }
            }]},
        ).execute()

        doc = self.docs.documents().get(documentId=doc_id).execute()
        cell_indices = self._collect_cell_indices(doc)
        expected = rows_count * cols
        if len(cell_indices) < expected:
            raise RuntimeError(f"Expected {expected} table cells, found {len(cell_indices)}")
        cell_indices = cell_indices[-expected:]

        # Build (index, text, is_header) entries, then emit requests in REVERSE
        # cell order so inserts into later cells never shift earlier cells' indices.
        entries: list[tuple[int, str, bool]] = []
        for row_idx, cell_texts in enumerate([headers] + rows):
            for col_idx in range(cols):
                idx = cell_indices[row_idx * cols + col_idx]
                text = str(cell_texts[col_idx] if col_idx < len(cell_texts) else "")
                entries.append((idx, text, row_idx == 0))

        requests: list[dict[str, Any]] = []
        for idx, text, is_header in reversed(entries):
            if not text:
                continue
            requests.append({"insertText": {"location": {"index": idx}, "text": text}})
            if is_header:
                text_style: dict[str, Any] = {
                    "bold": True,
                    "weightedFontFamily": {"fontFamily": FONT, "weight": 400},
                    "fontSize": {"magnitude": 10, "unit": "PT"},
                }
                fields = "bold,weightedFontFamily,fontSize"
            else:
                text_style = {
                    "weightedFontFamily": {"fontFamily": FONT, "weight": 400},
                    "fontSize": {"magnitude": 9, "unit": "PT"},
                }
                fields = "weightedFontFamily,fontSize"
            requests.append({
                "updateTextStyle": {
                    "range": {"startIndex": idx, "endIndex": idx + len(text)},
                    "textStyle": text_style,
                    "fields": fields,
                }
            })

        if requests:
            self.docs.documents().batchUpdate(
                documentId=doc_id, body={"requests": requests}
            ).execute()

    @staticmethod
    def _collect_cell_indices(doc: dict[str, Any]) -> list[int]:
        """Return every table cell's first-paragraph start index (row-major).

        ``documents.get`` does not expose per-cell segment ids; cells are
        addressed by document index instead — a freshly inserted cell contains
        exactly one empty paragraph, so its ``content[0]`` start index is a
        valid insertion point.
        """
        indices: list[int] = []

        def walk(elements: list[dict[str, Any]]) -> None:
            for element in elements:
                table = element.get("table")
                if not table:
                    continue
                for row in table.get("tableRows", []):
                    for cell in row.get("tableCells", []):
                        content = cell.get("content", [])
                        if content and content[0].get("paragraph"):
                            indices.append(content[0]["startIndex"])
                        else:
                            indices.append(cell.get("startIndex", 0))

        walk(doc["body"]["content"])
        return indices

