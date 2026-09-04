"""SOW document routes: list, get, save, update, delete, and download."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel

from app.config import get_settings
from app.core.dependencies import get_current_user, require_superadmin
from app.models.auth_models import MessageResponse
from app.services.audit_service import AuditService
from app.services.quota_service import QuotaError, QuotaService
from app.services.sow_service import SowService

logger = logging.getLogger("osiris.sow.routes")

router = APIRouter(prefix="/sow", tags=["sow-documents"])

def _service() -> SowService:
    return SowService(get_settings())

def _audit() -> AuditService:
    return AuditService(get_settings())

def _quota() -> QuotaService:
    return QuotaService(get_settings())

# -- request / response models -----------------------------------------------

class SowDocumentListItem(BaseModel):
    id: int
    title: str
    created_at: str
    updated_at: str
    is_published: bool
    sow_id: Optional[int] = None

class SowDocumentDetail(BaseModel):
    id: int
    user_id: int
    sow_id: Optional[int] = None
    title: str
    content_md: str
    content_plain: str
    created_at: str
    updated_at: str
    is_published: bool
    # Phase 3: structured payloads parsed server-side so the client can render
    # the document without re-parsing the JSON content_plain itself.
    sow: Optional[dict] = None
    spatial_context: Optional[dict] = None

class SowDocumentCreate(BaseModel):
    sow_id: Optional[int] = None
    title: str
    content_md: str
    content_plain: str
    is_published: bool = False

class SowSaveFromGenerationRequest(BaseModel):
    """Accepts a full SowResponse payload from /api/sow/generate and persists it.

    Used by the frontend to auto-save a generated SOW so it appears in the
    Documents list and can be re-exported later. The backend converts the
    structured SOW into the same Markdown + plaintext representation used
    elsewhere, so the result is fully round-trippable.
    """
    sow: dict
    sow_id: Optional[int] = None
    is_published: bool = False

class SowDocumentUpdate(BaseModel):
    title: Optional[str] = None
    content_md: Optional[str] = None
    content_plain: Optional[str] = None
    is_published: Optional[bool] = None

class SowDocumentListResponse(BaseModel):
    documents: list[SowDocumentListItem]

# -- routes -------------------------------------------------------------------

@router.get("", response_model=SowDocumentListResponse)
def list_documents(
    scope: str = Query("mine", pattern="^(mine|all)$"),
    user: dict = Depends(get_current_user),
) -> SowDocumentListResponse:
    """List documents. Regular users see their own; superadmins can pass ``scope=all``."""
    service = _service()
    if scope == "all":
        if user["role"] != "superadmin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superadmin privileges required for scope=all.")
        rows = service.store.list_all()
    else:
        rows = service.store.list_for_user(user["id"])
    return SowDocumentListResponse(documents=[SowDocumentListItem(**SowService.to_list_item(r)) for r in rows])

@router.get("/{doc_id}", response_model=SowDocumentDetail)
def get_document(doc_id: int, user: dict = Depends(get_current_user)) -> SowDocumentDetail:
    service = _service()
    row = service.assert_owner(doc_id, user)
    return SowDocumentDetail(**SowService.to_detail(row))

@router.post("", response_model=SowDocumentDetail, status_code=status.HTTP_201_CREATED)
def create_document(
    payload: SowDocumentCreate,
    user: dict = Depends(get_current_user),
) -> SowDocumentDetail:
    service = _service()
    row = service.store.create(
        user_id=user["id"],
        title=payload.title,
        content_md=payload.content_md,
        content_plain=payload.content_plain,
        sow_id=payload.sow_id,
        is_published=payload.is_published,
    )
    return SowDocumentDetail(**SowService.to_detail(row))

@router.patch("/{doc_id}", response_model=SowDocumentDetail)
def update_document(
    doc_id: int,
    payload: SowDocumentUpdate,
    user: dict = Depends(get_current_user),
) -> SowDocumentDetail:
    service = _service()
    service.assert_owner(doc_id, user)
    owner_id = user["id"] if user["role"] != "superadmin" else None
    fields = payload.model_dump(exclude_unset=True)
    updated = service.store.update(doc_id, owner_id, fields)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return SowDocumentDetail(**SowService.to_detail(updated))

@router.delete("/{doc_id}", response_model=MessageResponse)
def delete_document(doc_id: int, user: dict = Depends(get_current_user)) -> MessageResponse:
    service = _service()
    service.assert_owner(doc_id, user)
    owner_id = user["id"] if user["role"] != "superadmin" else None
    ok = service.store.delete(doc_id, owner_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    _audit().log("doc_delete", user=user, target_type="document",
                 target_id=str(doc_id), outcome="success")
    return MessageResponse(detail=f"Document {doc_id} deleted.")

@router.post("/from-generation", response_model=SowDocumentDetail, status_code=status.HTTP_201_CREATED)
def save_from_generation(
    payload: SowSaveFromGenerationRequest,
    user: dict = Depends(get_current_user),
) -> SowDocumentDetail:
    """Auto-save a generated SOW so it appears in the Documents list.

    The frontend calls /api/sow/generate to produce a structured SOW, then
    POSTs it here so the user can re-open it later and re-export to
    .docx / Google Docs. We do the Markdown + plaintext conversion on the
    server so the on-disk representation is consistent with manually-saved
    documents.
    """
    service = _service()
    # Phase 5 Track 2: enforce per-user saved-document quota.
    q = _quota()
    count = len(service.store.list_for_user(user["id"]))
    try:
        q.check_doc_count(current_doc_count=count)
    except QuotaError as exc:
        _audit().log("quota_exceeded", user=user, target_type="quota",
                     target_id="doc_count", outcome="denied", detail=exc.message)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    logger.info("save_from_generation: user_id=%s sow_keys=%s", user.get("id"), list(payload.sow.keys()))
    try:
        row = service.save_from_sow(
            user_id=user["id"],
            sow_dict=payload.sow,
            sow_id=payload.sow_id,
        )
    except Exception as exc:
        logger.exception("save_from_generation failed: %s", exc)
        raise
    _audit().log("doc_save", user=user, target_type="document",
                 target_id=str(row["id"]), outcome="success",
                 detail=f"from_generation sow_id={payload.sow_id}")
    return SowDocumentDetail(**SowService.to_detail(row))

@router.get("/{doc_id}/markdown")
def get_markdown(doc_id: int, user: dict = Depends(get_current_user)) -> Response:
    """Serve the document as plain Markdown text."""
    service = _service()
    row = service.assert_owner(doc_id, user)
    return Response(content=row["content_md"], media_type="text/markdown; charset=utf-8")

@router.get("/{doc_id}/download-docx")
def download_docx(doc_id: int, user: dict = Depends(get_current_user)) -> Response:
    """Download the SOW as a .docx file (works with no Google account).

    Google Docs export requires a Google identity with Drive quota; a service
    account in a standalone project cannot create Docs. This endpoint always
    works: the file can be opened in Word/LibreOffice or uploaded to a
    personal Google Drive to get a native Google Doc.
    """
    import json as _json
    from urllib.parse import quote
    from app.services.export_service import export_to_docx
    service = _service()
    row = service.assert_owner(doc_id, user)

    # content_plain stores the SowResponse as JSON; sow_json is a Phase 3
    # duplicate used by /sow/{id} detail responses. Prefer content_plain,
    # fall back to sow_json. Markdown (content_md) is NOT a valid SowResponse
    # and would crash Pydantic validation -> 500.
    plain = row.get("content_plain") or row.get("sow_json") or ""
    if not plain:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "This document has no structured JSON content and cannot be "
                "exported as .docx. Regenerate it via POST /api/sow/generate."
            ),
        )
    try:
        sow_dict = _json.loads(plain)
    except _json.JSONDecodeError as exc:
        logger.exception("download_docx: invalid JSON for doc_id=%s", doc_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Document content is corrupted (invalid JSON): {exc}",
        )

    title = row["title"] or "Scope of Work"
    filename = quote(title.replace("/", "-")) + ".docx"
    try:
        content = export_to_docx(sow_dict, title)
    except Exception as exc:
        # Make the real cause visible in the backend log instead of a silent 500.
        logger.exception("download_docx: export_to_docx failed for doc_id=%s", doc_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build .docx: {exc}",
        )

    return Response(
        content=content,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"; filename*=UTF-8\'\'{filename}'},
    )


# ---------------------------------------------------------------------------
# Phase 4 — multi-format export endpoint
# ---------------------------------------------------------------------------
from app.services.export_service import (
    ALL_FORMATS,
    COSTING_FORMATS,
    DEFAULT_FILENAMES,
    MIME_TYPES,
    export_sow as _export_sow,
)
from app.config import get_settings as _get_settings
import json as _json
import zipfile as _zipfile
import io as _io


@router.get("/{doc_id}/export")
def export_sow(
    doc_id: int,
    formats: str = Query(
        "docx",
        description=(
            "Comma-separated list of formats. Supported: "
            + ", ".join(ALL_FORMATS) + ". Costing formats (xlsx, csv) "
            "require superadmin role and EXPORT_COSTING_ENABLED=true."
        ),
    ),
    user: dict = Depends(get_current_user),
) -> Response:
    """Render a SOW in one or more formats and return as a single file or ZIP.

    A single format is returned as that file directly. Multiple formats are
    bundled into a ZIP. Costing formats (.xlsx, .csv) are gated by both the
    caller's superadmin role and the server-side ``export_costing_enabled``
    setting; non-superadmin callers receive a 403 if they request them.
    """
    requested = [f.strip().lower() for f in formats.split(",") if f.strip()]
    if not requested:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one format is required.",
        )
    invalid = [f for f in requested if f not in ALL_FORMATS]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format(s): {', '.join(invalid)}. Supported: "
                   + ", ".join(ALL_FORMATS),
        )
    needs_costing = any(f in COSTING_FORMATS for f in requested)
    settings = _get_settings()
    is_superadmin = (user or {}).get("role") == "superadmin"
    if needs_costing and not (is_superadmin and settings.export_costing_enabled):
        if not settings.export_costing_enabled:
            detail = "Costing exports are disabled on this server (EXPORT_COSTING_ENABLED=false)."
        else:
            detail = "Costing exports (.xlsx, .csv) require superadmin privileges."
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

    service = _service()
    row = service.assert_owner(doc_id, user)
    content_md = row["content_md"] or ""
    title = row["title"] or "SOW"
    sow_dict = None
    plain = row.get("content_plain") or ""
    if plain:
        try:
            sow_dict = _json.loads(plain)
        except Exception:
            sow_dict = None
    if sow_dict is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This document does not have structured JSON content; only .md is available.",
        )
    generated = _export_sow(sow=sow_dict, content_md=content_md, title=title, formats=requested)
    _audit().log('doc_export', user=user, target_type='document',
                 target_id=str(doc_id), outcome='success',
                 detail=f'formats={','.join(sorted(generated.keys()))}')
    if len(generated) == 1:
        fmt, (filename, body) = next(iter(generated.items()))
        from urllib.parse import quote as _quote
        encoded = _quote(filename)
        return Response(
            content=body,
            media_type=MIME_TYPES[fmt],
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{filename}"; '
                    f"filename*=UTF-8''{encoded}"
                )
            },
        )

    # Multiple formats -> zip them
    buf = _io.BytesIO()
    safe_base = re.sub(r'[\\/:*?"<>|]', "-", title).strip() or "SOW"
    with _zipfile.ZipFile(buf, "w", _zipfile.ZIP_DEFLATED) as z:
        for fmt, (filename, body) in generated.items():
            z.writestr(filename, body)
    zip_name = f"{safe_base}-export.zip"
    from urllib.parse import quote as _quote
    encoded = _quote(zip_name)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{zip_name}"; '
                f"filename*=UTF-8''{encoded}"
            )
        },
    )


# Lazily import re (used inside the route) at module bottom.
import re  # noqa: E402
