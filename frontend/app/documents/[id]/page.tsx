"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Download, MapPin, FileText } from "lucide-react";
import SowReport from "@/components/SowReport";
import ExportToolbar from "@/components/ExportToolbar";
import ScatterMap from "@/components/ScatterMap";
import {
  getSowDocument,
  downloadSowDocx,
  fetchExportConfig,
  type SowDocumentDetail,
} from "@/lib/api";
import { clearAuth, getCachedUser, isAuthenticated } from "@/lib/auth";
import type { SowResponse } from "@/lib/types";

export default function DocumentDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = Number(params?.id);
  const [doc, setDoc] = useState<SowDocumentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [user, setUser] = useState<ReturnType<typeof getCachedUser>>(null);
  // undefined while loading — ExportToolbar treats this as "gate closed"
  // (safer default).
  const [exportCostingEnabled, setExportCostingEnabled] = useState<boolean | undefined>(undefined);

  const load = useCallback(async () => {
    if (!Number.isFinite(id)) {
      setError("Invalid document id.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const [fetched, config] = await Promise.all([
        getSowDocument(id),
        // Only superadmins can fetch the config endpoint; non-superadmin
        // users will get a 403 which we silently treat as "costing gated".
        user?.role === "superadmin"
          ? fetchExportConfig().catch(() => ({ export_costing_enabled: false }))
          : Promise.resolve({ export_costing_enabled: false }),
      ]);
      setDoc(fetched);
      setExportCostingEnabled(config.export_costing_enabled);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load document");
    } finally {
      setLoading(false);
    }
  }, [id, user]);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace("/login");
      return;
    }
    setUser(getCachedUser());
  }, [router]);

  useEffect(() => {
    if (!user) return;
    void load();
  }, [load, user]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <div className="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-slate-300 border-t-slate-900" />
          <p className="mt-3 text-sm text-slate-400">Loading document…</p>
        </div>
      </div>
    );
  }

  if (error || !doc) {
    return (
      <div className="min-h-screen bg-slate-50">
        <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
          <button
            type="button"
            onClick={() => router.push("/documents")}
            className="inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900"
          >
            <ArrowLeft size={14} /> Back to documents
          </button>
          <div className="mt-6 rounded-xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">
            {error || "Document not found."}
          </div>
        </div>
      </div>
    );
  }

  // Prefer the structured SOW from the server; fall back to parsing content_plain.
  const sow: SowResponse | null = doc.sow ?? (() => {
    try {
      return JSON.parse(doc.content_plain) as SowResponse;
    } catch {
      return null;
    }
  })();

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white px-4 py-3 sm:px-6">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => router.push("/documents")}
              className="inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900"
            >
              <ArrowLeft size={14} /> Documents
            </button>
            <div>
              <h1 className="truncate text-sm font-bold text-slate-950">{doc.title}</h1>
              <p className="text-[11px] text-slate-500">
                Created {new Date(doc.created_at).toLocaleString()}
                {doc.is_published && (
                  <span className="ml-2 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
                    Published
                  </span>
                )}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void downloadSowDocx({ id: doc.id, title: doc.title, created_at: doc.created_at, updated_at: doc.updated_at, is_published: doc.is_published, sow_id: doc.sow_id ?? null })}
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            <Download size={13} /> Download .docx
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-5xl space-y-6 px-4 py-6 sm:px-6">
        {doc.spatial_context && Object.values(doc.spatial_context.files).some((c) => c && c.latitude != null) && (
          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center gap-2">
              <MapPin size={14} className="text-amber-500" />
              <h2 className="text-sm font-semibold text-slate-900">Photo GPS Map</h2>
              <span className="text-[11px] text-slate-500">
                {Object.values(doc.spatial_context.files).filter((c) => c && c.latitude != null).length} geotagged photos
              </span>
            </div>
            <ScatterMap spatialContext={doc.spatial_context} height={300} />
          </section>
        )}

        {sow ? (
          <SowReport sow={sow} model="Saved document" grounding={false} groundingSources={[]} />
        ) : (
          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center gap-2">
              <FileText size={14} className="text-slate-400" />
              <h2 className="text-sm font-semibold text-slate-900">Document Content</h2>
            </div>
            <pre className="whitespace-pre-wrap text-xs text-slate-700">{doc.content_md}</pre>
          </section>
        )}

        <ExportToolbar sow={doc} userRole={user?.role || "user"} exportCostingEnabled={exportCostingEnabled} />
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

