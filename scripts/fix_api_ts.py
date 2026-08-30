"""Patch api.ts: add ExportFormat import and exportSow function."""
import pathlib

p = pathlib.Path(r"c:\Users\ahmad\OneDrive\Documents\OSIRIS Imhotep\frontend\lib\api.ts")
t = p.read_text(encoding="utf-8")

# 1. Add ExportFormat to the import
OLD_IMPORT = 'import type { GenerateResponse, SowResponse } from "./types";'
NEW_IMPORT = 'import type { ExportFormat, GenerateResponse, SowResponse } from "./types";'
if OLD_IMPORT in t and NEW_IMPORT not in t:
    t = t.replace(OLD_IMPORT, NEW_IMPORT, 1)
    print("Import patched")
else:
    print("Import already patched or not found")

# 2. Add exportSow at EOF
EOF_MARKER = '  return res.json();\n}'
EXPORT_SOW = '''
/** Phase 4: fetch multi-format SOW export from the backend. */
export async function exportSow(
  docId: number,
  formats: ExportFormat[],
  signal?: AbortSignal,
): Promise<void> {
  const params = new URLSearchParams({ formats: formats.join(",") });
  const res = await fetch(`/api/sow/${docId}/export?${params}`, {
    headers: authHeaders(),
    signal,
  });
  if (!res.ok) {
    const detail = await parseError(res);
    throw new Error(detail);
  }
  const blob = await res.blob();
  // Extract filename from Content-Disposition header
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename[^;]*;\\s*filename\\*?[^;]*=['"]([^'"]+)['"]/i)
    ?? disposition.match(/filename=([^;\\s]+)/i);
  const filename = match ? decodeURIComponent(match[1]) : `sow-${docId}.zip`;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
'''
if "export async function exportSow" not in t:
    t = t.rstrip() + EXPORT_SOW + "\n"
    print("exportSow added at EOF")
else:
    print("exportSow already present")

p.write_text(t, encoding="utf-8")
print("Done. Total lines:", len(t.splitlines()))
