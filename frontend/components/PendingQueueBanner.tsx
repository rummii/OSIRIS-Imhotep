"use client";
// Phase: 1
// Offline queue UI banner. Shows pending submissions waiting for network
// and allows users to retry or discard them.
import { useState } from "react";
import { ChevronDown, CloudOff, RefreshCw, Trash2 } from "lucide-react";
import { useOfflineQueue } from "@/hooks/useOfflineQueue";
import type { PendingSubmission } from "@/lib/offline-db";

interface Props {
  /** Called when the user clicks Retry. Receives the submission and must
   *  return true on success so the banner knows to remove it. */
  onRetry: (sub: PendingSubmission) => Promise<boolean>;
}

export default function PendingQueueBanner({ onRetry }: Props) {
  // bump() is called by ChatInput after addPending, triggering a re-render here.
  const { queue: items, retry, discard, discardAll } = useOfflineQueue();
  const [expanded, setExpanded] = useState(false);

  if (items.length === 0) return null;

  return (
    <div className="border-t border-amber-200 bg-amber-50 px-4 py-3">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between text-left"
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-amber-700">
          <CloudOff size={14} aria-hidden="true" />
          {items.length} pending submission{items.length !== 1 ? "s" : ""} — waiting for network
        </span>
        <ChevronDown
          size={14}
          className={`text-amber-500 transition ${expanded ? "rotate-180" : ""}`}
          aria-hidden="true"
        />
      </button>

      {expanded && (
        <ul className="mt-2 space-y-2">
          {items.map((item) => (
            <li
              key={item.id}
              className="flex items-start gap-2 rounded-md border border-amber-200 bg-white p-2.5 text-xs"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium text-slate-700">
                  {item.notes.slice(0, 80) || "(no notes)"}
                </p>
                <p className="text-slate-400">
                  {[item.site && `Site: ${item.site}`, item.client && `Client: ${item.client}`, item.mediaFiles.length > 0 && `${item.mediaFiles.length} file(s)`].filter(Boolean).join(" · ")}
                </p>
                {item.lastError && (
                  <p className="mt-0.5 text-red-500">Error: {item.lastError}</p>
                )}
                <p className="text-slate-400">
                  {new Date(item.created_at).toLocaleString()}
                </p>
              </div>
              <button
                type="button"
                onClick={async () => { await retry(item, onRetry); }}
                className="shrink-0 rounded-md border border-blue-200 bg-blue-50 p-1.5 text-blue-600 hover:bg-blue-100 transition"
                title="Retry now"
              >
                <RefreshCw size={13} />
              </button>
              <button
                type="button"
                onClick={async () => { if (item.id !== undefined) await discard(item.id); }}
                className="shrink-0 rounded-md border border-red-200 p-1.5 text-red-400 hover:bg-red-50 hover:text-red-500 transition"
                title="Discard"
              >
                <Trash2 size={13} />
              </button>
            </li>
          ))}
          {items.length > 1 && (
            <li>
              <button
                type="button"
                onClick={async () => { await discardAll(); }}
                className="text-xs text-slate-400 hover:text-red-500 transition"
              >
                Discard all
              </button>
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
