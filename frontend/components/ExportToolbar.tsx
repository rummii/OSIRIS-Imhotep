"use client";

import { useState } from "react";
import { EXPORT_FORMATS, type ExportFormat } from "@/lib/types";
import { exportSow, type SowDocumentDetail } from "@/lib/api";

interface ExportToolbarProps {
  sow: SowDocumentDetail;
  userRole: string;
  /**
   * When false (or undefined while loading), costing formats (.xlsx, .csv)
   * are hidden from the toolbar entirely.  undefined is treated as "gated"
   * (safer default — we won't accidentally expose a disabled export).
   */
  exportCostingEnabled?: boolean;
}

/**
 * Multi-format SOW export toolbar.
 *
 * Renders one button per supported format. Costing formats (Excel, CSV) are
 * locked behind the superadmin role — the lock icon surfaces a tooltip.
 * The Markdown and JSON "Copy" buttons use navigator.clipboard and never
 * hit the network.
 */
export function ExportToolbar({ sow, userRole, exportCostingEnabled = false }: ExportToolbarProps) {
  const [pending, setPending] = useState<ExportFormat | null>(null);
  const [copyState, setCopyState] = useState<"md" | "json" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isSuperadmin = userRole === "superadmin";
  // Treat `undefined` (loading) as gated so we never briefly expose a
  // disabled export.  Once the config resolves to `true`, the costing
  // buttons reappear.
  const costingEnabled = exportCostingEnabled === true;

  async function handleDownload(fmt: ExportFormat) {
    if (EXPORT_FORMATS[fmt].requiresSuperadmin && !isSuperadmin) {
      setError("Superadmin access required for costing exports.");
      return;
    }
    setError(null);
    setPending(fmt);
    try {
      await exportSow(sow.id, [fmt]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setPending(null);
    }
  }

  async function handleCopy(target: "md" | "json") {
    setError(null);
    setCopyState(target);
    try {
      const text = target === "md"
        ? (sow.content_md ?? "")
        : (sow.content_plain ?? JSON.stringify(sow, null, 2));
      await navigator.clipboard.writeText(text);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Copy failed");
    } finally {
      setCopyState(null);
    }
  }

  // Costing formats are hidden entirely when the server-side gate is
  // closed.  Non-costing formats are always available.
  const allFormats: ExportFormat[] = ["docx", "odt", "xlsx", "csv", "xml"];
  const formats = allFormats.filter(
    (fmt) => costingEnabled || !EXPORT_FORMATS[fmt].requiresSuperadmin,
  );

  return (
    <div className="flex flex-wrap items-center gap-2" role="toolbar" aria-label="SOW export toolbar">
      {formats.map((fmt) => {
        const meta = EXPORT_FORMATS[fmt];
        const locked = meta.requiresSuperadmin && !isSuperadmin;
        const busy = pending === fmt;
        return (
          <button
            key={fmt}
            type="button"
            onClick={() => handleDownload(fmt)}
            disabled={busy || locked}
            title={locked ? "Superadmin access required for costing exports" : `Download ${meta.label} (${meta.ext})`}
            className={
              "inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm font-medium transition " +
              (locked
                ? "border-zinc-300 bg-zinc-100 text-zinc-400 cursor-not-allowed dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-600"
                : busy
                ? "border-indigo-300 bg-indigo-50 text-indigo-700 cursor-wait"
                : "border-indigo-200 bg-white text-indigo-700 hover:bg-indigo-50 dark:border-indigo-800 dark:bg-indigo-950/40 dark:text-indigo-300 dark:hover:bg-indigo-900/40")
            }
          >
            {locked && <LockIcon />}
            {busy && <Spinner />}
            {!busy && !locked && <DownloadIcon />}
            {meta.label}
          </button>
        );
      })}

      <div className="mx-1 h-6 w-px bg-zinc-200 dark:bg-zinc-700" />

      <button
        type="button"
        onClick={() => handleCopy("md")}
        disabled={copyState === "md"}
        title="Copy Markdown to clipboard"
        className="inline-flex items-center gap-1.5 rounded-md border border-zinc-200 bg-white px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
      >
        {copyState === "md" ? <Spinner /> : <CopyIcon />}
        Copy Markdown
      </button>
      <button
        type="button"
        onClick={() => handleCopy("json")}
        disabled={copyState === "json"}
        title="Copy JSON to clipboard"
        className="inline-flex items-center gap-1.5 rounded-md border border-zinc-200 bg-white px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
      >
        {copyState === "json" ? <Spinner /> : <CopyIcon />}
        Copy JSON
      </button>

      {error && (
        <span className="ml-2 text-sm text-red-600 dark:text-red-400" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}

function LockIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" aria-hidden="true">
      <rect x="5" y="11" width="14" height="9" rx="2" />
      <path d="M8 11V8a4 4 0 0 1 8 0v3" />
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" aria-hidden="true">
      <path d="M12 3v12m0 0l-4-4m4 4l4-4" />
      <path d="M5 21h14" />
    </svg>
  );
}

function CopyIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" aria-hidden="true">
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15V5a2 2 0 0 1 2-2h10" />
    </svg>
  );
}

function Spinner() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" className="animate-spin" aria-hidden="true">
      <circle cx="12" cy="12" r="9" opacity="0.25" />
      <path d="M21 12a9 9 0 0 0-9-9" />
    </svg>
  );
}

export default ExportToolbar;
