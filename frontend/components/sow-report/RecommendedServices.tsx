"use client";
// Section 3: Recommended services. Renders sow.recommended_services with
// priority badges and any per-service notes below the table.
import { Wrench } from "lucide-react";
import { SectionTitle } from "./SectionTitle";
import { THead } from "./THead";
import { TData } from "./TData";
import { PriorityBadge } from "../badges";
import { money } from "./money";
import type { SowResponse } from "@/lib/types";

export function RecommendedServices({ sow }: { sow: SowResponse }) {
  const services = sow.recommended_services ?? [];
  const currency = sow.currency || "PHP";
  const servicesWithNotes = services.filter((s) => s.notes);

  return (
    <div className="card p-5 space-y-3">
      <SectionTitle icon={<Wrench size={14} />}>Recommended Services</SectionTitle>
      {services.length === 0 ? (
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
              {services.map((service) => (
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
      {servicesWithNotes.length > 0 && (
        <div className="space-y-1">
          {servicesWithNotes.map((s) => (
            <p key={`${s.id}-notes`} className="text-[11px] text-slate-500">
              <span className="text-slate-400 font-mono">{s.id}</span> — {s.notes}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
