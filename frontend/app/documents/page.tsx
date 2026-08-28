"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Download, FileText, Trash2, Plus } from "lucide-react";
import {
  listSowDocuments,
  deleteSowDocument,
  downloadSowDocx,
  type SowDocumentListItem,
} from "@/lib/api";
import { clearAuth, getCachedUser, isAuthenticated } from "@/lib/auth";

export default function DocumentsPage() {
  const router = useRouter();
  const [docs, setDocs] = useState<SowDocumentListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [scope, setScope] = useState<"mine" | "all">("mine");
  const [user, setUser] = useState<ReturnType<typeof getCachedUser>>(null);

  const isSuperadmin = user?.role === "superadmin";

  const load = useCallback(
    async (requestedScope: "mine" | "all") => {
      setLoading(true);
      setError("");
      try {
        setDocs(await listSowDocuments(requestedScope));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load documents");
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace("/login");
      return;
    }
    setUser(getCachedUser());
  }, [router]);

  useEffect(() => {
    if (!user) return;
    void load(scope);
  }, [load, scope, user]);

  const handleDelete = async (doc: SowDocumentListItem) => {
    if (!window.confirm(`Delete "${doc.title}"? This cannot be undone.`)) return;
    try {
      await deleteSowDocument(doc.id);
      void load(scope);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white px-4 py-3 sm:px-6">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="grid h-9 w-9 place-items-center rounded-md bg-slate-900">
              <FileText size={17} className="text-white" />
            </div>
            <div>
              <h1 className="text-sm font-bold text-slate-950">My Documents</h1>
              <p className="text-[11px] text-slate-500">
                {isSuperadmin
                  ? scope === "all"
                    ? "All saved SOWs (every user)"
                    : "Your saved SOWs"
                  : "Your saved Scope of Work documents"}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {isSuperadmin && (
              <div className="flex rounded-md border border-slate-200 bg-slate-50 p-0.5 text-xs">
                <button
                  type="button"
                  onClick={() => setScope("mine")}
                  className={`rounded px-2 py-1 transition ${
                    scope === "mine"
                      ? "bg-white font-semibold text-slate-900 shadow-sm"
                      : "text-slate-500 hover:text-slate-700"
                  }`}
                >
                  Mine
                </button>
                <button
                  type="button"
                  onClick={() => setScope("all")}
                  className={`rounded px-2 py-1 transition ${
                    scope === "all"
                      ? "bg-white font-semibold text-slate-900 shadow-sm"
                      : "text-slate-500 hover:text-slate-700"
                  }`}
                >
                  All
                </button>
              </div>
            )}
            <button
              type="button"
              onClick={() => router.push("/")}
              className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50"
            >
              <Plus size={14} /> New SOW
            </button>
            <button
              type="button"
              onClick={() => router.push("/")}
              className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-900"
            >
              <ArrowLeft size={15} /> Back
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-6 space-y-4 sm:px-6">
        {error && (
          <p className="rounded-md border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-600">{error}</p>
        )}

        {loading ? (
          <div className="py-16 text-center">
            <div className="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-slate-300 border-t-slate-900" />
            <p className="mt-3 text-sm text-slate-400">Loading documents…</p>
          </div>
        ) : docs.length === 0 ? (
          <div className="rounded-xl border border-slate-200 bg-white p-12 text-center shadow-sm">
            <FileText size={32} className="mx-auto text-slate-300" />
            <h2 className="mt-4 text-lg font-semibold text-slate-900">No saved documents yet</h2>
            <p className="mt-1 text-sm text-slate-500">
              Generate a Scope of Work to have it automatically saved here.
            </p>
            <button
              type="button"
              onClick={() => router.push("/")}
              className="mt-6 inline-flex items-center gap-2 rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700"
            >
              <Plus size={16} /> Create your first SOW
            </button>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {docs.map((doc) => (
              <div
                key={doc.id}
                className="group rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-blue-200 hover:shadow"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="truncate text-sm font-semibold text-slate-900">{doc.title}</h3>
                    <p className="mt-0.5 text-[11px] text-slate-400">
                      {new Date(doc.created_at).toLocaleDateString()} ·{" "}
                      {new Date(doc.created_at).toLocaleTimeString()}
                    </p>
                  </div>
                  {doc.is_published && (
                    <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
                      Published
                    </span>
                  )}
                </div>

                <div className="mt-4 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => void downloadSowDocx(doc)}
                    className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                  >
                    <Download size={13} />
                    Download .docx
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(doc)}
                    className="inline-flex items-center justify-center rounded-md border border-red-200 px-2.5 py-1.5 text-red-500 hover:bg-red-50"
                    title="Delete document"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      <div className="mx-auto max-w-5xl px-4 pb-8 sm:px-6">
        <button
          type="button"
          onClick={() => { clearAuth(); router.replace("/login"); }}
          className="text-xs text-slate-400 hover:text-red-600"
        >
          Sign out
        </button>
      </div>
    </div>
  );
}

