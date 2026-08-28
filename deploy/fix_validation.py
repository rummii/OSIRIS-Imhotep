"""Make SowService.save_from_sow tolerant of unknown fields from frontend."""
from pathlib import Path
import re

p = Path(r"c:\Users\ahmad\OneDrive\Documents\OSIRIS Imhotep\backend\app\services\sow_service.py")
text = p.read_text(encoding="utf-8")

# Replace SowResponse.model_validate with a tolerant version that strips unknown fields
old = 'sow = SowResponse.model_validate(sow_dict)\n        content_md = _sow_to_markdown(sow)\n        content_plain = _sow_to_plaintext(sow)'
new = '''# Tolerant validation: strip unknown fields and coerce missing ones to defaults.
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
        content_plain = _sow_to_plaintext(sow)'''
assert old in text, "anchor not found"
text = text.replace(old, new)

# Also add a try/except wrapper around the store.create call so 500s become 422s
old2 = '''        row = self.store.create(
            user_id=user_id,
            title=title,
            content_md=content_md,
            content_plain=content_plain,
            sow_id=sow_id,
            is_published=False,
        )
        return row'''
new2 = '''        try:
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
        return row'''
assert old2 in text, "store.create anchor not found"
text = text.replace(old2, new2)

p.write_text(text, encoding="utf-8", newline="")
print("patched", p)
