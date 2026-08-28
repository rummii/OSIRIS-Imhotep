import type { GenerateResponse, SowResponse } from "./types";
import { authHeaders, handleUnauthorized } from "./auth";

async function parseError(res: Response): Promise<string> {
  let detail = `Request failed (${res.status})`;
  try {
    const body = await res.json();
    detail = body.detail ?? detail;
  } catch {
    // Non-JSON error body — e.g. Next.js returns an HTML 500 page when the
    // backend is unreachable, or the browser/network hiccuped.
    if (res.status === 500) {
      detail =
        "The backend did not respond. Make sure it is running (dev-backend.cmd), then try again.";
    }
  }
  return detail;
}

export interface LoginResult {
  access_token: string;
  token_type: string;
  expires_in: number;
  role: string;
  username: string;
  display_name: string;
  must_change_password: boolean;
}

/** POST /api/auth/login — returns a JWT to store. */
export async function login(username: string, password: string): Promise<LoginResult> {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

/** GET /api/auth/me — current session user (401 clears session). */
export async function fetchMe(): Promise<Record<string, unknown>> {
  const res = await fetch("/api/auth/me", { headers: authHeaders() });
  if (handleUnauthorized(res)) throw new Error("Session expired");
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

/** POST /api/auth/change-password */
export async function changePassword(current: string, next: string): Promise<void> {
  const res = await fetch("/api/auth/change-password", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ current_password: current, new_password: next }),
  });
  if (handleUnauthorized(res)) throw new Error("Session expired");
  if (!res.ok) throw new Error(await parseError(res));
}

/** GET /api/admin/users (superadmin only) */
export async function adminListUsers(): Promise<Record<string, unknown>[]> {
  const res = await fetch("/api/admin/users", { headers: authHeaders() });
  if (handleUnauthorized(res)) throw new Error("Session expired");
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

/** POST /api/admin/users (superadmin only) */
export async function adminCreateUser(data: {
  username: string;
  display_name?: string;
  email?: string;
  role?: string;
  password: string;
  must_change_password?: boolean;
}): Promise<Record<string, unknown>> {
  const res = await fetch("/api/admin/users", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(data),
  });
  if (handleUnauthorized(res)) throw new Error("Session expired");
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

/** PATCH /api/admin/users/:id (superadmin only) */
export async function adminUpdateUser(
  id: number,
  data: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/admin/users/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(data),
  });
  if (handleUnauthorized(res)) throw new Error("Session expired");
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

/** POST /api/admin/users/:id/reset-password (superadmin only) */
export async function adminResetPassword(id: number, newPassword: string): Promise<void> {
  const res = await fetch(`/api/admin/users/${id}/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ new_password: newPassword }),
  });
  if (handleUnauthorized(res)) throw new Error("Session expired");
  if (!res.ok) throw new Error(await parseError(res));
}

export interface GenerateParams {
  notes: string;
  site: string;
  client: string;
  files: File[];
}

/**
 * POST /api/sow/generate — multipart form (notes + site + client + files[]).
 * Requires a valid login token (SSO gate).
 */
export async function generateSow(params: GenerateParams): Promise<GenerateResponse> {
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
}

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
}

// ---------------------------------------------------------------------------
// SOW document persistence
// ---------------------------------------------------------------------------

export interface SowDocumentListItem {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
  is_published: boolean;
  sow_id?: number | null;
}

export interface SowDocumentDetail {
  id: number;
  user_id: number;
  sow_id?: number | null;
  title: string;
  content_md: string;
  content_plain: string;
  created_at: string;
  updated_at: string;
  is_published: boolean;
}

/** GET /api/sow?scope=mine — list the current user's saved SOW documents. */
export async function listSowDocuments(
  scope: "mine" | "all" = "mine"
): Promise<SowDocumentListItem[]> {
  const res = await fetch(`/api/sow?scope=${scope}`, { headers: authHeaders() });
  if (handleUnauthorized(res)) throw new Error("Session expired");
  if (!res.ok) throw new Error(await parseError(res));
  const data = await res.json();
  return data.documents as SowDocumentListItem[];
}

/** GET /api/sow/:id — fetch a single saved SOW document (owner or superadmin). */
export async function getSowDocument(id: number): Promise<SowDocumentDetail> {
  const res = await fetch(`/api/sow/${id}`, { headers: authHeaders() });
  if (handleUnauthorized(res)) throw new Error("Session expired");
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

/** POST /api/sow — create a new saved SOW document. */
export async function createSowDocument(data: {
  title: string;
  content_md: string;
  content_plain: string;
  sow_id?: number | null;
  is_published?: boolean;
}): Promise<SowDocumentDetail> {
  const res = await fetch("/api/sow", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(data),
  });
  if (handleUnauthorized(res)) throw new Error("Session expired");
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

/** PATCH /api/sow/:id — update title / content / published flag. */
export async function updateSowDocument(
  id: number,
  data: {
    title?: string;
    content_md?: string;
    content_plain?: string;
    is_published?: boolean;
  }
): Promise<SowDocumentDetail> {
  const res = await fetch(`/api/sow/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(data),
  });
  if (handleUnauthorized(res)) throw new Error("Session expired");
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

/** DELETE /api/sow/:id — permanently remove a saved document. */
export async function deleteSowDocument(id: number): Promise<void> {
  const res = await fetch(`/api/sow/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (handleUnauthorized(res)) throw new Error("Session expired");
  if (!res.ok) throw new Error(await parseError(res));
}

/** GET /api/sow/:id/download-docx — download the SOW as a .docx file. */
export async function downloadSowDocx(doc: SowDocumentListItem): Promise<void> {
  const res = await fetch(`/api/sow/${doc.id}/download-docx`, { headers: authHeaders() });
  if (handleUnauthorized(res)) throw new Error("Session expired");
  if (!res.ok) throw new Error(await parseError(res));
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${doc.title.replace(/[\\/:*?"<>|]/g, "-") || "SOW"}.docx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

