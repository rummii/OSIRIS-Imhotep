import type { ExportResponse, GenerateResponse, SowResponse } from "./types";
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
}

