"""Patch backend/app/api/sow_routes.py to add auto-save endpoint."""
from pathlib import Path

p = Path(r"c:\Users\ahmad\OneDrive\Documents\OSIRIS Imhotep\backend\app\api\sow_routes.py")
text = p.read_text(encoding="utf-8")

# 1. Add new request model
old_models = 'class SowDocumentCreate(BaseModel):\n    sow_id: Optional[int] = None\n    title: str\n    content_md: str\n    content_plain: str\n    is_published: bool = False\n'
new_models = old_models + '''\n
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
'''
assert text.count(old_models) == 1, f"old_models found {text.count(old_models)} times"
text = text.replace(old_models, new_models)

# 2. Add new endpoint right after create_document (before the @router.patch)
old_marker = '@router.get("/{doc_id}/markdown")'
new_endpoint = '''@router.post("/from-generation", response_model=SowDocumentDetail, status_code=status.HTTP_201_CREATED)
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
    row = service.save_from_sow(
        user_id=user["id"],
        sow_dict=payload.sow,
        sow_id=payload.sow_id,
    )
    return SowDocumentDetail(**SowService.to_detail(row))


'''
if old_marker not in text:
    raise SystemExit("anchor not found")
text = text.replace(old_marker, new_endpoint + old_marker)

p.write_text(text, encoding="utf-8", newline="")
print("patched", p)
