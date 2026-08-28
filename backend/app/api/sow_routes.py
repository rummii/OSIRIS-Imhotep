"""SOW document routes: list, get, save, update, delete, and download."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel

from app.config import get_settings
from app.core.dependencies import get_current_user, require_superadmin
from app.models.auth_models import MessageResponse
from app.services.sow_service import SowService

logger = logging.getLogger("osiris.sow.routes")

router = APIRouter(prefix="/sow", tags=["sow-documents"])

def _service() -> SowService:
    return SowService(get_settings())

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

    owner_email: Optional[str] = None

    doc_url: str
    doc_id: str

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
    from urllib.parse import quote
    from app.services.sow_service import export_to_docx
    service = _service()
    row = service.assert_owner(doc_id, user)
    filename = quote((row["title"] or "SOW").replace("/", "-")) + ".docx"
    content = export_to_docx(row["content_md"], row["title"] or "Scope of Work")
    return Response(
        content=content,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"; filename*=UTF-8\'\'{filename}'},
    )
