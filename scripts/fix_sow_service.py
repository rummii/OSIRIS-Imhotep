"""Replace hand-rolled docx tail in sow_service.py with a re-export."""
import pathlib
p = pathlib.Path(r"c:\Users\ahmad\OneDrive\Documents\OSIRIS Imhotep\backend\app\services\sow_service.py")
text = p.read_text(encoding="utf-8")

# Find the start marker and slice to EOF.
marker = "# .docx export (works everywhere, no Google account required)"
idx = text.find(marker)
if idx < 0:
    print("ALREADY PATCHED or marker missing")
    raise SystemExit(0)
# Back up to the preceding # --- comment line
start = text.rfind("# ---", 0, idx)
if start < 0:
    start = idx

new_tail = (
    "# ---------------------------------------------------------------------------\n"
    "# .docx export — re-exported from export_service (backward compat)\n"
    "# ---------------------------------------------------------------------------\n\n"
    "from app.services.export_service import export_to_docx\n"
)
text = text[:start] + new_tail
p.write_text(text, encoding="utf-8")
print("Patched: kept first", start, "chars, appended re-export")
