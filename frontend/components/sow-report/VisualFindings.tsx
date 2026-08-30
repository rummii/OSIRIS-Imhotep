"use client";
// Section 2: Visual findings. Renders sow.visual_findings as a table
// with severity badges. Safe to render with empty array.
import { Eye } from "lucide-react";
import { SectionTitle } from "./SectionTitle";
import { THead } from "./THead";
import { TData } from "./TData";
import { SeverityBadge } from "../badges";
import type { SowResponse } from "@/lib/types";

export function VisualFindings({ sow }: { sow: SowResponse }) {
  const findings = sow.visual_findings ?? [];
  return (
    <div className="card p-5 space-y-3">
      <SectionTitle icon={<Eye size={14} />}>Visual Findings</SectionTitle>
      {findings.length === 0 ? (
        <p className="text-xs text-slate-500 italic">No visual findings recorded.</p>
      ) : (
        <div className="overflow-x-auto -mx-5 px-5">
          <table className="w-full border-collapse min-w-[900px]">
            <thead className="border-b border-slate-800">
              <tr>
                <THead>ID</THead>
                <THead>Asset</THead>
                <THead>Location</THead>
                <THead>Condition</THead>
                <THead>Severity</THead>
                <THead>Description</THead>
                <THead>Recommended action</THead>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/70">
              {findings.map((finding) => (
                <tr key={finding.id} className="hover:bg-slate-800/30 transition">
                  <TData mono>{finding.id}</TData>
                  <TData><span className="text-slate-200 font-medium">{finding.asset}</span></TData>
                  <TData>{finding.location}</TData>
                  <TData>{finding.condition}</TData>
                  <TData><SeverityBadge severity={finding.severity} /></TData>
                  <TData className="max-w-xs">
                    {finding.description}
                    {finding.oem_reference && (
                      <span className="mt-1 block text-[10px] text-sky-400/80">OEM: {finding.oem_reference}</span>
                    )}
                  </TData>
                  <TData className="max-w-xs">{finding.recommended_action}</TData>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
