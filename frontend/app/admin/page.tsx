"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Database, KeyRound, Pencil, Plus, RefreshCw, UserPlus, Users } from "lucide-react";
import {
  adminCreateUser,
  adminListAuditLog,
  adminListUsers,
  adminRagRefresh,
  adminRagStats,
  adminResetPassword,
  adminUpdateUser,
  type AuditLogItem,
  type AuditLogResponse,
  type RagStatsResponse,
} from "@/lib/api";
import { clearAuth, getCachedUser, getToken, type SessionUser } from "@/lib/auth";

interface AdminUser {
  id: number;
  username: string;
  display_name?: string;
  email?: string;
  role: string;
  is_active: boolean;
  must_change_password?: boolean;
  created_at?: string;
}

export default function AdminPage() {
  const router = useRouter();
  const [me, setMe] = useState<SessionUser | null>(null);

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [form, setForm] = useState({ username: "", display_name: "", email: "", role: "user", password: "" });
  const [creating, setCreating] = useState(false);
  const [resetFor, setResetFor] = useState<number | null>(null);
  const [resetPw, setResetPw] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState({ display_name: "", email: "", role: "user" });

  // RAG card state
  const [ragStats, setRagStats] = useState<RagStatsResponse | null>(null);
  const [ragLoading, setRagLoading] = useState(false);
  const [ragRefreshing, setRagRefreshing] = useState(false);
  const [ragNotice, setRagNotice] = useState("");

  // Phase 5 Track 2: Audit log state
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [auditTotal, setAuditTotal] = useState(0);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState("");
  const [auditFilter, setAuditFilter] = useState<{ user_id?: number; action?: string }>({});

  const loadRagStats = useCallback(async () => {
    try {
      const me = await adminRagStats();
      setRagStats(me);
    } catch {
      // silently ignore — caller is superadmin and card is hidden if not
    }
  }, []);

  const loadAuditLogs = useCallback(async () => {
    setAuditLoading(true);
    setAuditError("");
    try {
      const res: AuditLogResponse = await adminListAuditLog({
        ...auditFilter,
        limit: 50,
        offset: 0,
      });
      setAuditLogs(res.items);
      setAuditTotal(res.total);
    } catch (err) {
      setAuditError(err instanceof Error ? err.message : "Failed to load audit log");
    } finally {
      setAuditLoading(false);
    }
  }, [auditFilter]);

  const doRagRefresh = useCallback(async () => {
    setRagRefreshing(true);
    setRagNotice("");
    try {
      const stats = await adminRagRefresh();
      // After refresh, re-fetch the full stats shape so total_chunks / sources
      // remain consistent with /admin/rag/stats.
      const fresh = await adminRagStats();
      setRagStats({
        ...fresh,
        last_refresh_at: new Date().toISOString(),
      });
      setRagNotice(`Refreshed — ${stats.chunks_embedded} chunks embedded in ${stats.duration_seconds}s.`);
    } catch (err) {
      setRagNotice(err instanceof Error ? err.message : "Refresh failed.");
    } finally {
      setRagRefreshing(false);
    }
  }, []);

  const load = useCallback(async () => {
    try {
      setUsers((await adminListUsers()) as unknown as AdminUser[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load users");
    }
  }, []);

    useEffect(() => {
    if (!getToken() || getCachedUser()?.role !== "superadmin") {
      router.replace("/");
      return;
    }
    setMe(getCachedUser());
    void load();
    void loadRagStats();
    void loadAuditLogs();
  }, [load, loadRagStats, loadAuditLogs, router]);

  useEffect(() => {
    const id = setInterval(() => { void loadAuditLogs(); }, 10_000);
    return () => clearInterval(id);
  }, [loadAuditLogs]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setCreating(true);
    try {
      await adminCreateUser({ ...form, must_change_password: true });
      setNotice(`User "${form.username}" created. They must change the password on first login.`);
      setForm({ username: "", display_name: "", email: "", role: "user", password: "" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create user");
    } finally {
      setCreating(false);
    }
  };

  const toggleActive = async (user: AdminUser) => {
    try {
      await adminUpdateUser(user.id, { is_active: !user.is_active });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    }
  };

  const doReset = async (user: AdminUser) => {
    if (!resetPw) return;
    try {
      await adminResetPassword(user.id, resetPw);
      setNotice(`Password for "${user.username}" reset — they must change it at next login.`);
      setResetFor(null);
      setResetPw("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed");
    }
  };

  const doEdit = (user: AdminUser) => {
    setEditingId(user.id);
    setEditForm({ display_name: user.display_name ?? "", email: user.email ?? "", role: user.role });
    setError("");
    setNotice("");
  };

  const doSaveEdit = async (user: AdminUser) => {
    if (!editForm.display_name.trim()) {
      setError("Display name is required.");
      return;
    }
    try {
      await adminUpdateUser(user.id, editForm);
      setEditingId(null);
      setNotice(`User "${user.username}" updated.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    }
  };

  const doCancelEdit = () => {
    setEditingId(null);
    setError("");
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white px-4 py-3 sm:px-6">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="grid h-9 w-9 place-items-center rounded-md bg-slate-900">
              <svg viewBox="0 0 32 32" className="h-5 w-5" aria-hidden="true">
                <text
                  x="16"
                  y="22"
                  fontFamily="Arial, sans-serif"
                  fontSize="18"
                  fontWeight="bold"
                  fill="#f59e0b"
                  textAnchor="middle"
                >
                  O
                </text>
              </svg>
            </div>
            <div>
              <h1 className="text-sm font-bold text-slate-950">User management</h1>
              <p className="text-[11px] text-slate-500">Superadmin · onboard and manage access</p>
            </div>
          </div>
          <button type="button" onClick={() => router.replace("/")}
            className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900">
            <ArrowLeft size={16} /> Back
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-6 space-y-6 sm:px-6">
        {error && (
          <p className="rounded-md border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-600">{error}</p>
        )}
        {notice && (
          <p className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-700">{notice}</p>
        )}

        {/* Onboard new user */}
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-4 flex items-center gap-2">
            <UserPlus size={16} className="text-slate-400" />
            <h2 className="text-sm font-semibold text-slate-900">Onboard new user</h2>
          </div>
          <form onSubmit={handleCreate} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
            <input required placeholder="Username" value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100" />
            <input placeholder="Display name" value={form.display_name}
              onChange={(e) => setForm({ ...form, display_name: e.target.value })}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100" />
            <input type="email" placeholder="Email" value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100" />
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-600">
              <option value="user">User</option>
              <option value="superadmin">Superadmin</option>
            </select>
            <input required placeholder="Temp password (min 8)" value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100" />
            <button type="submit" disabled={creating}
              className="inline-flex items-center justify-center gap-1.5 rounded-md bg-slate-900 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-40">
              <Plus size={15} /> {creating ? "Creating…" : "Create"}
            </button>
          </form>
        </section>

        {/* Users table */}
        <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="flex items-center gap-2 border-b border-slate-100 px-5 py-3">
            <Users size={15} className="text-slate-400" />
            <h2 className="text-sm font-semibold text-slate-900">Users ({users.length})</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-100 text-[11px] uppercase tracking-wider text-slate-400">
                <tr>
                  <th className="px-5 py-2">User</th>
                  <th className="px-3 py-2">Role</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Created</th>
                  <th className="px-5 py-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {users.map((user) => (
                  <tr key={user.id} className={user.is_active ? "" : "opacity-50"}>
                    <td className="px-5 py-3">
                      <p className="font-medium text-slate-900">{user.display_name || user.username}</p>
                      <p className="text-xs text-slate-400">
                        @{user.username}
                        {user.email ? ` · ${user.email}` : ""}
                      </p>
                    </td>
                    <td className="px-3 py-3">
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${user.role === "superadmin" ? "bg-violet-100 text-violet-700" : "bg-slate-100 text-slate-600"}`}>
                        {user.role}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-xs">
                      {user.is_active ? (
                        <span className="text-emerald-600">Active</span>
                      ) : (
                        <span className="text-red-500">Disabled</span>
                      )}
                      {user.must_change_password && (
                        <span className="ml-1 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] text-amber-700">pw reset</span>
                      )}
                    </td>
                    <td className="px-3 py-3 text-xs text-slate-500">
                      {user.created_at ? new Date(user.created_at).toLocaleDateString() : "—"}
                    </td>
                    <td className="px-5 py-3 text-right whitespace-nowrap">
                      {editingId === user.id ? (
                        <span className="inline-flex items-center gap-1 flex-wrap justify-end">
                          <input
                            placeholder="Display name"
                            value={editForm.display_name}
                            onChange={(e) => setEditForm({ ...editForm, display_name: e.target.value })}
                            className="w-28 rounded-md border border-slate-300 px-2 py-1 text-xs outline-none focus:border-blue-600"
                          />
                          <input
                            type="email"
                            placeholder="Email"
                            value={editForm.email}
                            onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                            className="w-32 rounded-md border border-slate-300 px-2 py-1 text-xs outline-none focus:border-blue-600"
                          />
                          <select
                            value={editForm.role}
                            onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}
                            className="rounded-md border border-slate-300 px-2 py-1 text-xs outline-none focus:border-blue-600"
                          >
                            <option value="user">User</option>
                            <option value="superadmin">Superadmin</option>
                          </select>
                          <button type="button" onClick={() => doSaveEdit(user)}
                            className="rounded bg-blue-600 px-2 py-1 text-xs font-semibold text-white hover:bg-blue-700">
                            Save
                          </button>
                          <button type="button" onClick={doCancelEdit}
                            className="text-xs text-slate-400 hover:text-slate-700">
                            Cancel
                          </button>
                        </span>
                      ) : resetFor === user.id ? (
                        <span className="inline-flex items-center gap-1">
                          <input
                            type="password"
                            placeholder="New password"
                            value={resetPw}
                            onChange={(e) => setResetPw(e.target.value)}
                            className="w-40 rounded-md border border-slate-300 px-2 py-1 text-xs outline-none focus:border-blue-600"
                          />
                          <button type="button" onClick={() => doReset(user)}
                            className="rounded bg-slate-900 px-2 py-1 text-xs font-semibold text-white hover:bg-slate-700">
                            Save
                          </button>
                          <button type="button"
                            onClick={() => { setResetFor(null); setResetPw(""); }}
                            className="text-xs text-slate-400 hover:text-slate-700">
                            Cancel
                          </button>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-2">
                          <button type="button" onClick={() => doEdit(user)}
                            className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-blue-600"
                            title="Edit user">
                            <Pencil size={13} /> Edit
                          </button>
                          <button type="button" onClick={() => { setResetFor(user.id); setResetPw(""); }}
                            className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-900"
                            title="Reset password">
                            <KeyRound size={13} /> Reset
                          </button>
                          {user.username !== me?.username && (
                            <button type="button" onClick={() => toggleActive(user)}
                              className="text-xs text-slate-500 hover:text-red-600"
                              title={user.is_active ? "Deactivate" : "Activate"}>
                              {user.is_active ? "Deactivate" : "Activate"}
                            </button>
                          )}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
                </section>

        {/* Phase 1 — RAG Corpus Management */}
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-4 flex items-center gap-2">
            <Database size={18} className="text-indigo-600" />
            <h2 className="text-base font-semibold text-slate-900">RAG Regulatory Corpus</h2>
            {ragStats && (
              <span className="ml-auto rounded bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700">
                {ragStats.total_chunks} chunks &middot; {ragStats.engine}
              </span>
            )}
          </div>

          {ragStats ? (
            <div className="space-y-3">
              <div className="overflow-hidden rounded-lg border border-slate-100">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-slate-50 text-left text-slate-500">
                      <th className="px-3 py-2 font-medium">Source</th>
                      <th className="px-3 py-2 font-medium">Domain</th>
                      <th className="px-3 py-2 font-medium">Jurisdiction</th>
                      <th className="px-3 py-2 text-right font-medium">Chunks</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {ragStats.sources.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="px-3 py-3 text-center text-slate-400 italic">
                          No chunks indexed yet. Run a refresh below.
                        </td>
                      </tr>
                    ) : (
                      ragStats.sources.map((s) => (
                        <tr key={s.source} className="hover:bg-slate-50">
                          <td className="px-3 py-2 font-mono text-slate-700">{s.source}</td>
                          <td className="px-3 py-2 text-slate-600">{s.domain}</td>
                          <td className="px-3 py-2 text-slate-600">{s.jurisdiction}</td>
                          <td className="px-3 py-2 text-right font-medium text-slate-800">{s.chunks}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              <p className="text-xs text-slate-500">
                {ragStats.last_refresh_at
                  ? `Last refreshed: ${new Date(ragStats.last_refresh_at).toLocaleString()}`
                  : "Never refreshed"}
              </p>

              <button
                type="button"
                onClick={() => { void doRagRefresh(); }}
                disabled={ragRefreshing}
                className="inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-4 py-2 text-xs font-semibold text-white transition hover:bg-indigo-700 disabled:opacity-50"
              >
                <RefreshCw size={13} className={ragRefreshing ? "animate-spin" : ""} />
                {ragRefreshing ? "Embedding ..." : "Refresh Corpus"}
              </button>

              {ragNotice && (
                <p className={`text-xs ${ragNotice.includes("Refreshed") ? "text-emerald-600" : "text-red-500"}`}>
                  {ragNotice}
                </p>
              )}
            </div>
          ) : (
            <p className="text-xs text-slate-400 italic">Loading RAG stats ...</p>
          )}
        </section>


        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-4 flex items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-900">Audit Log</h2>
            {auditTotal > 0 && (
              <span className="ml-auto rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{auditTotal} entries</span>
            )}
            <button type="button" onClick={() => { void loadAuditLogs(); }}
              className="ml-2 inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-900">
              <RefreshCw size={12} /> Refresh
            </button>
          </div>
          <div className="mb-3 flex flex-wrap gap-2">
            <select value={auditFilter.action ?? ""}
              onChange={(e) => setAuditFilter({ ...auditFilter, action: e.target.value || undefined })}
              className="rounded-md border border-slate-300 px-2 py-1 text-xs outline-none focus:border-blue-600">
              <option value="">All actions</option>
              <option value="login">login</option>
              <option value="logout">logout</option>
              <option value="doc_save">doc_save</option>
              <option value="doc_delete">doc_delete</option>
              <option value="doc_export">doc_export</option>
              <option value="sow_generate">sow_generate</option>
              <option value="user_create">user_create</option>
              <option value="rag_refresh">rag_refresh</option>
              <option value="rate_limited">rate_limited</option>
              <option value="quota_exceeded">quota_exceeded</option>
            </select>
          </div>
          {auditError && <p className="mb-2 text-xs text-red-500">{auditError}</p>}
          {auditLoading && auditLogs.length === 0 ? (
            <p className="text-xs text-slate-400 italic">Loading...</p>
          ) : auditLogs.length === 0 ? (
            <p className="text-xs text-slate-400 italic">No audit entries yet.</p>
          ) : (
            <div className="max-h-80 overflow-y-auto rounded-lg border border-slate-100">
              <table className="w-full text-left text-xs">
                <thead className="sticky top-0 border-b border-slate-100 bg-slate-50 text-[10px] uppercase tracking-wider text-slate-400">
                  <tr><th className="px-3 py-2">When</th><th className="px-3 py-2">User</th><th className="px-3 py-2">Action</th><th className="px-3 py-2">Target</th><th className="px-3 py-2">Outcome</th><th className="px-3 py-2">Detail</th><th className="px-3 py-2">IP</th></tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {auditLogs.map((entry) => (
                    <tr key={entry.id} className="hover:bg-slate-50">
                      <td className="px-3 py-1.5 whitespace-nowrap text-slate-500">{entry.ts ? new Date(entry.ts).toLocaleString() : "-"}</td>
                      <td className="px-3 py-1.5"><span className="font-medium text-slate-800">{entry.username ?? "-"}</span>{entry.role && <span className="ml-1 rounded bg-slate-100 px-1 text-[10px] text-slate-500">{entry.role}</span>}</td>
                      <td className="px-3 py-1.5 text-slate-700">{entry.action}</td>
                      <td className="px-3 py-1.5 text-slate-500">{entry.target_type ? entry.target_type + (entry.target_id ? "/" + entry.target_id : "") : "-"}</td>
                      <td className="px-3 py-1.5"><span className={entry.outcome === "success" ? "text-emerald-600" : entry.outcome === "failure" ? "text-red-500" : entry.outcome === "denied" ? "text-red-600 font-semibold" : "text-slate-600"}>{entry.outcome}</span></td>
                      <td className="px-3 py-1.5 max-w-xs truncate text-slate-400" title={entry.detail ?? ""}>{entry.detail ?? "-"}</td>
                      <td className="px-3 py-1.5 font-mono text-slate-400 text-[10px]">{entry.ip_address ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
        <div className="flex justify-end">
          <button type="button"
            onClick={() => { clearAuth(); router.replace("/login"); }}
            className="text-xs text-slate-400 hover:text-red-600">
            Sign out
          </button>
        </div>
      </main>
    </div>
  );
}

