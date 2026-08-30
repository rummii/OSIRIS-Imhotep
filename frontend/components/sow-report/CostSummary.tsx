"use client";
// Section 5: Cost summary. Renders sow.cost_breakdown as a small table.
import { Wallet } from "lucide-react";
import { SectionTitle } from "./SectionTitle";
import { money } from "./money";
import type { SowResponse } from "@/lib/types";

export function CostSummary({ sow }: { sow: SowResponse }) {
  const currency = sow.currency || "PHP";
  const breakdown = sow.cost_breakdown;
  if (!breakdown) {
    return (
      <div className="card p-5 space-y-3">
        <SectionTitle icon={<Wallet size={14} />}>Estimated Cost Breakdown</SectionTitle>
        <p className="text-xs text-slate-500 italic">No cost breakdown available.</p>
      </div>
    );
  }
  const rows: Array<[string, number]> = [
    ["Labor", breakdown.labor],
    ["Materials", breakdown.materials],
    ["Equipment", breakdown.equipment],
    ["Subtotal", breakdown.subtotal],
    [`Contingency (${breakdown.contingency_pct}%)`, breakdown.contingency],
  ];

  return (
    <div className="card p-5 space-y-3">
      <SectionTitle icon={<Wallet size={14} />}>Estimated Cost Breakdown</SectionTitle>
      <div className="max-w-sm">
        <table className="w-full border-collapse">
          <tbody className="divide-y divide-slate-800/70 text-xs">
            {rows.map(([label, value]) => (
              <tr key={label}>
                <td className="py-2 text-slate-400">{label}</td>
                <td className="py-2 text-right font-mono text-slate-300">{money(Number(value), currency)}</td>
              </tr>
            ))}
            <tr>
              <td className="py-2 pt-3 text-sm font-semibold text-slate-200">Total Estimated Cost</td>
              <td className="py-2 pt-3 text-right text-sm font-bold text-amber-300">
                {money(breakdown.total, currency)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
