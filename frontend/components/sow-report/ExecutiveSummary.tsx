"use client";
// Section 1: Executive summary. Defensive — backend may omit `executive_summary`
// for stub/older saved docs. Fall back to `scope_summary` so the card never
// crashes the whole report.
import { FileSpreadsheet } from "lucide-react";
import { SectionTitle } from "./SectionTitle";
import type { SowResponse } from "@/lib/types";

export function ExecutiveSummary({ sow }: { sow: SowResponse }) {
  return (
    <div className="card p-5 space-y-2">
      <SectionTitle icon={<FileSpreadsheet size={14} />}>Executive Summary</SectionTitle>
      <p className="text-sm leading-relaxed text-slate-300">
        {sow.executive_summary?.overview ?? sow.scope_summary ?? "No executive summary available."}
      </p>
      {sow.executive_summary?.priority_findings && (
        <p className="text-xs text-slate-400">
          <span className="text-slate-500 font-medium">Priority findings: </span>
          {sow.executive_summary.priority_findings}
        </p>
      )}
      {sow.executive_summary?.overall_condition && (
        <div className="flex items-center gap-2 text-xs">
          <span className="text-slate-500">Overall condition:</span>
          <span className="font-semibold text-slate-200">{sow.executive_summary.overall_condition}</span>
        </div>
      )}
    </div>
  );
}
