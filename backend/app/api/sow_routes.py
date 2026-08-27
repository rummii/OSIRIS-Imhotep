"""SOW document routes: list, get, save, update, delete, on-demand Google Docs export."""
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


class SowDocumentUpdate(BaseModel):
    title: Optional[str] = None
    content_md: Optional[str] = None
    content_plain: Optional[str] = None
    is_published: Optional[bool] = None


class SowDocumentListResponse(BaseModel):
    documents: list[SowDocumentListItem]


class ExportGdocRequest(BaseModel):
    owner_email: Optional[str] = None


class ExportGdocResponse(BaseModel):
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


@router.get("/{doc_id}/markdown")
def get_markdown(doc_id: int, user: dict = Depends(get_current_user)) -> Response:
    """Serve the document as plain Markdown text."""
    service = _service()
    row = service.assert_owner(doc_id, user)
    return Response(content=row["content_md"], media_type="text/markdown; charset=utf-8")


@router.post("/{doc_id}/export-gdoc", response_model=ExportGdocResponse)
def export_to_gdoc(
    doc_id: int,
    payload: ExportGdocRequest,
    user: dict = Depends(get_current_user),
) -> ExportGdocResponse:
    """On-demand Google Docs export of a saved document."""
    from app.services.gdoc_service import GdocNotConfiguredError
    service = _service()
    row = service.assert_owner(doc_id, user)
    settings = get_settings()
    try:
        doc_url, exported_id = service.export_to_gdoc(row["id"], payload.owner_email, settings)
    except GdocNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Google Docs export failed for document %s.", doc_id)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Google Docs export failed: {exc}") from exc
    return ExportGdocResponse(doc_url=doc_url, doc_id=exported_id)

