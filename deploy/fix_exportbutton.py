"""Make ExportButton docId nullable, show 'saving...' when not yet saved."""
from pathlib import Path
p = Path(r"c:\Users\ahmad\OneDrive\Documents\OSIRIS Imhotep\frontend\components\ExportButton.tsx")
text = p.read_text(encoding="utf-8")

# 1. Make docId optional and add saving state
old_props = '''interface ExportButtonProps {
  /** The server-assigned doc id (from POST /api/sow/from-generation). */
  docId: number;
}'''
new_props = '''interface ExportButtonProps {
  /** The server-assigned doc id (from POST /api/sow/from-generation).
   *  Undefined while the auto-save is still in flight. */
  docId?: number;
}'''
assert old_props in text
text = text.replace(old_props, new_props)

# 2. Add early-return "saving" indicator before the main return
old_sig = 'export default function ExportButton({ docId }: ExportButtonProps) {'
new_sig = old_sig
text = text.replace(old_sig, new_sig)

old_helper = '''  const handleExport = async () => {
    setState({ status: "loading" });
    try {
      const result = await exportToGoogleDoc(docId, email.trim() || undefined);
      setState({ status: "done", url: result.doc_url });
    } catch (err) {
      setState({ status: "error", message: err instanceof Error ? err.message : "Export failed" });
    }
  };'''
new_helper = '''  const handleExport = async () => {
    if (!docId) return;
    setState({ status: "loading" });
    try {
      const result = await exportToGoogleDoc(docId, email.trim() || undefined);
      setState({ status: "done", url: result.doc_url });
    } catch (err) {
      setState({ status: "error", message: err instanceof Error ? err.message : "Export failed" });
    }
  };

  if (!docId) {
    return (
      <div className="rounded-md border border-slate-800 bg-slate-900/40 px-3 py-2 text-[11px] text-slate-500">
        Saving to Documents…
      </div>
    );
  }'''
assert old_helper in text
text = text.replace(old_helper, new_helper)

p.write_text(text, encoding="utf-8", newline="")
print("patched", p)
