"""Add logging to the /from-generation endpoint so we can see real errors."""
from pathlib import Path

p = Path(r"c:\Users\ahmad\OneDrive\Documents\OSIRIS Imhotep\backend\app\api\sow_routes.py")
text = p.read_text(encoding="utf-8")

old = '''@router.post("/from-generation", response_model=SowDocumentDetail, status_code=status.HTTP_201_CREATED)
def save_from_generation(
    payload: SowSaveFromGenerationRequest,
    user: dict = Depends(get_current_user),
) -> SowDocumentDetail:
    """Auto-save a generated SOW so it appears in the Documents list.'''
new = '''@router.post("/from-generation", response_model=SowDocumentDetail, status_code=status.HTTP_201_CREATED)
def save_from_generation(
    payload: SowSaveFromGenerationRequest,
    user: dict = Depends(get_current_user),
) -> SowDocumentDetail:
    """Auto-save a generated SOW so it appears in the Documents list.'''
assert old in text
# Insert logger call at start of endpoint body
old_body = '''    service = _service()
    row = service.save_from_sow('''
new_body = '''    service = _service()
    logger.info("save_from_generation: user_id=%s sow_keys=%s", user.get("id"), list(payload.sow.keys()))
    try:
        row = service.save_from_sow('''
old_end = '''        sow_id=payload.sow_id,
    )
    return SowDocumentDetail(**SowService.to_detail(row))'''
new_end = '''        sow_id=payload.sow_id,
    )
    except Exception as exc:
        logger.exception("save_from_generation failed: %s", exc)
        raise
    return SowDocumentDetail(**SowService.to_detail(row))'''
assert old_body in text and old_end in text
text = text.replace(old_body, new_body).replace(old_end, new_end)

p.write_text(text, encoding="utf-8", newline="")
print("patched", p)
