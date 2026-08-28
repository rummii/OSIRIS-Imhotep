"""Add docId to SowReport destructuring."""
from pathlib import Path
p = Path(r"c:\Users\ahmad\OneDrive\Documents\OSIRIS Imhotep\frontend\components\SowReport.tsx")
text = p.read_text(encoding="utf-8")
old = '''export default function SowReport({
  sow,
  model,
  grounding,
  groundingSources,
}: SowReportProps) {'''
new = '''export default function SowReport({
  sow,
  model,
  grounding,
  groundingSources,
  docId,
}: SowReportProps) {'''
assert old in text
text = text.replace(old, new)
p.write_text(text, encoding="utf-8", newline="")
print("patched", p)
