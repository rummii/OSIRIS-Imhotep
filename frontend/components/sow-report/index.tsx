"use client";
// SowReport orchestrator. Renders the document header and stacks each
// sub-section. Each section is a self-contained sub-component; this file
// only handles layout and the AI-review footer.
import { ExecutiveSummary } from "./ExecutiveSummary";
import { VisualFindings } from "./VisualFindings";
import { RecommendedServices } from "./RecommendedServices";
import { ScopeBreakdown } from "./ScopeBreakdown";
import { CostSummary } from "./CostSummary";
import { GroundingSources } from "./GroundingSources";
import type { SowReportProps } from "./types";

export type { SowReportProps } from "./types";

export default function SowReport({ sow, model, grounding, groundingSources }: SowReportProps) {
  return (
    <div className="report-surface space-y-4 animate-fade-up">
      {/* Header */}
      <div className="card p-5 space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[10px] uppercase tracking-widest text-amber-400 font-semibold">
              Scope of Work · {model}{grounding ? " · Grounded" : ""}
            </p>
            <h2 className="mt-1 text-xl font-bold text-slate-100">{sow.project_title}</h2>
            <p className="mt-1 text-xs text-slate-500">
              {[sow.client && `Client: ${sow.client}`, sow.site && `Site: ${sow.site}`, sow.generated_at && new Date(sow.generated_at).toLocaleString()].filter(Boolean).join("  ·  ")}
            </p>
          </div>
        </div>
      </div>

      <ExecutiveSummary sow={sow} />
      <VisualFindings sow={sow} />
      <RecommendedServices sow={sow} />
      <ScopeBreakdown sow={sow} />
      <CostSummary sow={sow} />
      <GroundingSources sources={groundingSources} />

      <p className="text-center text-[10px] text-slate-600">
        AI-generated draft — subject to review by a licensed engineer before execution.
      </p>
    </div>
  );
}
