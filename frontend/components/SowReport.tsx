"use client";

import { FileSpreadsheet, Wrench, ListChecks, Wallet, Eye } from "lucide-react";
import type { SowResponse } from "@/lib/types";
import { SeverityBadge, PriorityBadge } from "./badges";
import ExportButton from "./ExportButton";

const CURRENCY_SYMBOLS: Record<string, string> = { PHP: "₱", USD: "$" };

function money(value: number, currency: string): string {
  const symbol = CURRENCY_SYMBOLS[currency] ?? `${currency} `;
  return `${symbol}${(value ?? 0).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function SectionTitle({
  icon,
  children,
}: {
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-2 text-sm font-semibold text-slate-200">
      <span className="grid h-6 w-6 place-items-center rounded-md bg-amber-400/10 border border-amber-400/30 text-amber-400">
        {icon}
      </span>
      {children}
    </div>
  );
}

function THead({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <th className={`px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500 whitespace-nowrap ${className}`}>
      {children}
    </th>
  );
}

function TData({ children, mono = false, className = "" }: { children: React.ReactNode; mono?: boolean; className?: string }) {
  return (
    <td className={`px-3 py-2 align-top text-xs ${mono ? "font-mono text-slate-300" : "text-slate-400"} ${className}`}>
      {children}
    </td>
  );
}

interface SowReportProps {
  sow: SowResponse;
  model: string;
  grounding: boolean;
  groundingSources: { title: string; url: string }[];
}

export default function SowReport({
  sow,
  model,
  grounding,
  groundingSources,
}: SowReportProps) {
  const currency = sow.currency || "PHP";

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
          <div className="w-full sm:w-72">
            <ExportButton sow={sow} />
          </div>
        </div>
      </div>

      {/* 1. Executive summary */}
      <div className="card p-5 space-y-2">
        <SectionTitle icon={<FileSpreadsheet size={14} />}>Executive Summary</SectionTitle>
        <p className="text-sm leading-relaxed text-slate-300">{sow.executive_summary.overview}</p>
        {sow.executive_summary.priority_findings && (
          <p className="text-xs text-slate-400">
            <span className="text-slate-500 font-medium">Priority findings: </span>
            {sow.executive_summary.priority_findings}
          </p>
        )}
        <div className="flex items-center gap-2 text-xs">
          <span className="text-slate-500">Overall condition:</span>
          <span className="font-semibold text-slate-200">{sow.executive_summary.overall_condition}</span>
        </div>
      </div>

      {/* 2. Visual findings */}
      <div className="card p-5 space-y-3">
        <SectionTitle icon={<Eye size={14} />}>Visual Findings</SectionTitle>
        {sow.visual_findings.length === 0 ? (
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
                {sow.visual_findings.map((finding) => (
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


      {/* 3. Recommended services */}
      <div className="card p-5 space-y-3">
        <SectionTitle icon={<Wrench size={14} />}>Recommended Services</SectionTitle>
        {sow.recommended_services.length === 0 ? (
          <p className="text-xs text-slate-500 italic">No recommended services recorded.</p>
        ) : (
          <div className="overflow-x-auto -mx-5 px-5">
            <table className="w-full border-collapse min-w-[820px]">
              <thead className="border-b border-slate-800">
                <tr>
                  <THead>ID</THead>
                  <THead>Service</THead>
                  <THead>Asset</THead>
                  <THead>Priority</THead>
                  <THead className="text-right">Qty</THead>
                  <THead>Unit</THead>
                  <THead className="text-right">Unit cost</THead>
                  <THead className="text-right">Total</THead>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70">
                {sow.recommended_services.map((service) => (
                  <tr key={service.id} className="hover:bg-slate-800/30 transition">
                    <TData mono>{service.id}</TData>
                    <TData><span className="text-slate-200 font-medium">{service.service}</span></TData>
                    <TData>{service.asset}</TData>
                    <TData><PriorityBadge priority={service.priority} /></TData>
                    <TData mono>{service.quantity}</TData>
                    <TData>{service.unit}</TData>
                    <TData mono>{money(service.unit_cost, currency)}</TData>
                    <TData mono className="font-semibold text-amber-300">{money(service.total_cost, currency)}</TData>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {sow.recommended_services.some((s) => s.notes) && (
          <div className="space-y-1">
            {sow.recommended_services.filter((s) => s.notes).map((s) => (
              <p key={`${s.id}-notes`} className="text-[11px] text-slate-500">
                <span className="text-slate-400 font-mono">{s.id}</span> — {s.notes}
              </p>
            ))}
          </div>
        )}
      </div>

      {/* 4. Scope breakdown */}
      <div className="card p-5 space-y-3">
        <SectionTitle icon={<ListChecks size={14} />}>Scope Breakdown</SectionTitle>
        {sow.scope_breakdown.length === 0 ? (
          <p className="text-xs text-slate-500 italic">No scope items recorded.</p>
        ) : (
          <div className="space-y-4">
            {sow.scope_breakdown.map((scope, index) => (
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


      {/* 5. Cost breakdown */}
      <div className="card p-5 space-y-3">
        <SectionTitle icon={<Wallet size={14} />}>Estimated Cost Breakdown</SectionTitle>
        <div className="max-w-sm">
          <table className="w-full border-collapse">
            <tbody className="divide-y divide-slate-800/70 text-xs">
              {[
                ["Labor", sow.cost_breakdown.labor],
                ["Materials", sow.cost_breakdown.materials],
                ["Equipment", sow.cost_breakdown.equipment],
                ["Subtotal", sow.cost_breakdown.subtotal],
                [`Contingency (${sow.cost_breakdown.contingency_pct}%)`, sow.cost_breakdown.contingency],
              ].map(([label, value]) => (
                <tr key={String(label)}>
                  <td className="py-2 text-slate-400">{label}</td>
                  <td className="py-2 text-right font-mono text-slate-300">{money(Number(value), currency)}</td>
                </tr>
              ))}
              <tr>
                <td className="py-2 pt-3 text-sm font-semibold text-slate-200">Total Estimated Cost</td>
                <td className="py-2 pt-3 text-right text-sm font-bold text-amber-300">
                  {money(sow.cost_breakdown.total, currency)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Grounding sources */}
      {groundingSources.length > 0 && (
        <div className="card p-5 space-y-2">
          <SectionTitle icon={<FileSpreadsheet size={14} />}>Grounding Sources</SectionTitle>
          <ul className="space-y-1">
            {groundingSources.map((source, index) => (
              <li key={index} className="text-xs">
                <a
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sky-400 hover:text-sky-300 hover:underline break-all"
                >
                  {source.title || source.url}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="text-center text-[10px] text-slate-600">
        AI-generated draft — subject to review by a licensed engineer before execution.
      </p>
    </div>
  );
}

