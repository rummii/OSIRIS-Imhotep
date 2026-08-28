"use client";

import { useState } from "react";
import { FileText, ExternalLink, Loader2, Mail } from "lucide-react";
import { exportToGoogleDoc } from "@/lib/api";
import type { SowResponse } from "@/lib/types";

interface ExportButtonProps {
  /** The server-assigned doc id (from POST /api/sow/from-generation). */
  docId: number;
}

type ExportState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "done"; url: string }
  | { status: "error"; message: string };

/**
 * "Generate Google Doc" button — POSTs the SOW payload to
 * /api/sow/export-gdoc and surfaces the live doc URL.
 */
export default function ExportButton({ docId }: ExportButtonProps) {
  const [state, setState] = useState<ExportState>({ status: "idle" });
  const [email, setEmail] = useState("");

  const handleExport = async () => {
    setState({ status: "loading" });
    try {
      const result = await exportToGoogleDoc(docId, email.trim() || undefined);
      setState({ status: "done", url: result.doc_url });
    } catch (err) {
      setState({ status: "error", message: err instanceof Error ? err.message : "Export failed" });
    }
  };

  return (
    <div className="space-y-2">
      {state.status === "done" ? (
        <a
          href={state.url}
          target="_blank"
          rel="noreferrer"
          className="btn-primary w-full justify-center"
        >
          <ExternalLink size={16} />
          Open Google Doc
        </a>
      ) : (
        <div className="flex items-stretch gap-2">
          <div className="relative flex-1">
            <Mail size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              type="email"
              placeholder="Your email (to share the doc)"
              className="input-chip w-full pl-8 py-2"
            />
          </div>
          <button
            type="button"
            onClick={handleExport}
            disabled={state.status === "loading"}
            className="btn-primary shrink-0"
          >
            {state.status === "loading" ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <FileText size={16} />
            )}
            Generate Google Doc
          </button>
        </div>
      )}
      {state.status === "error" && (
        <p className="text-xs text-red-400">{state.message}</p>
      )}
      {state.status === "idle" && (
        <p className="text-[11px] text-slate-500">
          Creates a styled, pre-formatted Google Doc with tables and shares it
          with your email.
        </p>
      )}
    </div>
  );
}
