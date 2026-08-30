"""Append the /export route to sow_routes.py."""
import pathlib
p = pathlib.Path(r"c:\Users\ahmad\OneDrive\Documents\OSIRIS Imhotep\backend\app\api\sow_routes.py")
text = p.read_text(encoding="utf-8")
# Replace the last import inside the download_docx to keep the route valid,
# then append the new /export endpoint at EOF.
if "Phase 4 multi-format export" in text:
    print("ALREADY PATCHED")
    raise SystemExit(0)
addition = '''

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

    if len(generated) == 1:
        fmt, (filename, body) = next(iter(generated.items()))
        safe_title = DEFAULT_FILENAMES[fmt].format(title="") if False else filename
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
    safe_base = re.sub(r"[\\\\/:*?\"<>|]", "-", title).strip() or "SOW"
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
'''
text += addition
p.write_text(text, encoding="utf-8")
print("Appended /export route, total", len(text.splitlines()), "lines")
