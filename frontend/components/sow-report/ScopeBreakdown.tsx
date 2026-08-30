"use client";
// Section 4: Scope breakdown. Renders sow.scope_breakdown as a stack of
// phase cards with deliverables.
import { ListChecks } from "lucide-react";
import { SectionTitle } from "./SectionTitle";
import type { SowResponse } from "@/lib/types";

export function ScopeBreakdown({ sow }: { sow: SowResponse }) {
  const phases = sow.scope_breakdown ?? [];
  return (
    <div className="card p-5 space-y-3">
      <SectionTitle icon={<ListChecks size={14} />}>Scope Breakdown</SectionTitle>
      {phases.length === 0 ? (
        <p className="text-xs text-slate-500 italic">No scope items recorded.</p>
      ) : (
        <div className="space-y-4">
          {phases.map((scope, index) => (
            <div key={index} className="rounded-lg border border-slate-800 bg-slate-950/40 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-semibold text-amber-300">{scope.phase}</p>
                {scope.duration_days > 0 && (
                  <span className="text-[10px] text-slate-500 bg-slate-800/70 px-2 py-0.5 rounded-full">
                    {scope.duration_days} days
                  </span>
                )}
              </div>
              <p className="mt-2 text-xs leading-relaxed text-slate-400">{scope.work_description}</p>
              {scope.deliverables.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {scope.deliverables.map((item, i) => (
                    <li key={i} className="flex gap-2 text-xs text-slate-400">
                      <span className="text-amber-500">•</span>
                      {item}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
