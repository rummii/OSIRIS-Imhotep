"""Patch frontend components: SowReport and ExportButton for auto-save flow."""
from pathlib import Path

# --- ExportButton.tsx ---
eb = Path(r"c:\Users\ahmad\OneDrive\Documents\OSIRIS Imhotep\frontend\components\ExportButton.tsx")
eb_text = eb.read_text(encoding="utf-8")

old_eb_import = 'import { exportToGoogleDoc } from "@/lib/api";'
new_eb_import = old_eb_import  # no change

old_eb_props = '''interface ExportButtonProps {
  sow: SowResponse;
}'''
new_eb_props = '''interface ExportButtonProps {
  /** The server-assigned doc id (from POST /api/sow/from-generation). */
  docId: number;
}'''

old_eb_sig = 'export default function ExportButton({ sow }: ExportButtonProps) {'
new_eb_sig = 'export default function ExportButton({ docId }: ExportButtonProps) {'

old_eb_call = 'const result = await exportToGoogleDoc(sow, email.trim() || undefined);'
new_eb_call = 'const result = await exportToGoogleDoc(docId, email.trim() || undefined);'

old_eb_type = 'import type { SowResponse } from "@/lib/types";'
new_eb_type = old_eb_type  # no change needed

for old, new in [
    (old_eb_import, new_eb_import),
    (old_eb_props, new_eb_props),
    (old_eb_sig, new_eb_sig),
    (old_eb_call, new_eb_call),
]:
    assert old in eb_text, f"ExportButton: not found: {repr(old[:60])}"
    eb_text = eb_text.replace(old, new)

eb.write_text(eb_text, encoding="utf-8", newline="")
print("patched", eb)

# --- SowReport.tsx ---
sr = Path(r"c:\Users\ahmad\OneDrive\Documents\OSIRIS Imhotep\frontend\components\SowReport.tsx")
sr_text = sr.read_text(encoding="utf-8")

old_sr_props = '''interface SowReportProps {
  sow: SowResponse;
  model: string;
  grounding: boolean;
  groundingSources: { title: string; url: string }[];
}'''
new_sr_props = '''interface SowReportProps {
  sow: SowResponse;
  model: string;
  grounding: boolean;
  groundingSources: { title: string; url: string }[];
  /** Server-assigned doc id (optional — shown once the SOW has been saved). */
  docId?: number | null;
}'''

old_sr_destruct = 'export default function SowReport({'
new_sr_destruct = old_sr_destruct  # no change

old_sr_call = '<ExportButton sow={sow} />'
new_sr_call = '<ExportButton docId={docId ?? 0} />'

for old, new in [
    (old_sr_props, new_sr_props),
    (old_sr_call, new_sr_call),
]:
    assert old in sr_text, f"SowReport: not found: {repr(old[:60])}"
    sr_text = sr_text.replace(old, new)

sr.write_text(sr_text, encoding="utf-8", newline="")
print("patched", sr)
