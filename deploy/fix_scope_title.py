"""Fix: remove scope.title which doesn't exist in ScopeItem schema."""
from pathlib import Path

p = Path(r"c:\Users\ahmad\OneDrive\Documents\OSIRIS Imhotep\backend\app\services\sow_service.py")
text = p.read_text(encoding="utf-8")
old = 'heading = scope.phase or scope.title or "Phase"'
new = 'heading = scope.phase or "Phase"'
assert old in text, f"not found: {repr(old)}"
text = text.replace(old, new)
p.write_text(text, encoding="utf-8", newline="")
print("patched", p)
