"""Update SowReport to pass docId directly (no fallback)."""
from pathlib import Path
p = Path(r"c:\Users\ahmad\OneDrive\Documents\OSIRIS Imhotep\frontend\components\SowReport.tsx")
text = p.read_text(encoding="utf-8")
old = '<ExportButton docId={docId ?? 0} />'
new = '<ExportButton docId={docId} />'
assert old in text
text = text.replace(old, new)
p.write_text(text, encoding="utf-8", newline="")
print("patched", p)
