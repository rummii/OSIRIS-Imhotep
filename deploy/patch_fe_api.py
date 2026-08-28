"""Patch frontend/lib/api.ts to add saveFromGeneration and update exportToGoogleDoc."""
from pathlib import Path

p = Path(r"c:\Users\ahmad\OneDrive\Documents\OSIRIS Imhotep\frontend\lib\api.ts")
text = p.read_text(encoding="utf-8")

# 1. Add saveFromGeneration function after generateSow
old_gen = '''export async function generateSow(params: GenerateParams): Promise<GenerateResponse> {
  const form = new FormData();
  form.append("notes", params.notes);
  form.append("site", params.site);
  form.append("client", params.client);
  for (const file of params.files) {
    form.append("files", file);
  }

  const res = await fetch("/api/sow/generate", {
    method: "POST",
    body: form,
    headers: authHeaders(),
  });
  if (handleUnauthorized(res)) throw new Error("Session expired");
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}'''

new_gen = old_gen + '''

/**
 * POST /api/sow/from-generation — persist a generated SOW so it appears in
 * the Documents list and can be re-exported. Returns the saved doc detail
 * including the server-assigned id.
 */
export async function saveFromGeneration(
  sow: GenerateResponse["sow"],
  sowId?: number | null,
  isPublished = false,
): Promise<SowDocumentDetail> {
  const res = await fetch("/api/sow/from-generation", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ sow, sow_id: sowId, is_published: isPublished }),
  });
  if (handleUnauthorized(res)) throw new Error("Session expired");
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}'''

assert old_gen in text, "generateSow function not found in api.ts"
text = text.replace(old_gen, new_gen)

# 2. Update exportToGoogleDoc to accept docId (saved doc) or SowResponse
old_export = '''/**
 * POST /api/sow/export-gdoc — converts the SOW JSON into a Google Doc and
 * returns the live doc URL.
 */
export async function exportToGoogleDoc(
  sow: SowResponse,
  ownerEmail?: string
): Promise<ExportResponse> {
  const res = await fetch("/api/sow/export-gdoc", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ sow, owner_email: ownerEmail || null }),
  });
  if (handleUnauthorized(res)) throw new Error("Session expired");
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}'''

new_export = '''/**
 * POST /api/sow/{docId}/export-gdoc — re-export a previously saved document
 * to Google Docs using the server-assigned doc id.
 */
export async function exportToGoogleDoc(
  docId: number,
  ownerEmail?: string
): Promise<ExportResponse> {
  const res = await fetch(`/api/sow/${docId}/export-gdoc`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ owner_email: ownerEmail || null }),
  });
  if (handleUnauthorized(res)) throw new Error("Session expired");
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}'''

assert old_export in text, "exportToGoogleDoc function not found in api.ts"
text = text.replace(old_export, new_export)

p.write_text(text, encoding="utf-8", newline="")
print("patched", p)
