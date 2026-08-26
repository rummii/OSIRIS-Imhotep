"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Loader2 } from "lucide-react";

const STAGES = [
  { key: "media", label: "Reviewing uploaded site media" },
  { key: "evidence", label: "Identifying stated conditions and constraints" },
  { key: "scope", label: "Drafting recommended scope and services" },
  { key: "compose", label: "Composing structured SOW JSON" },
];

const STAGE_MS = 2600;

interface LoadingIndicatorProps {
  mediaCount: number;
}

/**
 * Staged loading state shown while the backend runs text analysis.
 * The backend call is a single POST; we animate through realistic pipeline
 * stages so the user can see what is happening under the hood.
 */
export default function LoadingIndicator({ mediaCount }: LoadingIndicatorProps) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setElapsed((e) => e + 100), 100);
    return () => clearInterval(timer);
  }, []);

  const activeIndex = Math.min(
    Math.floor(elapsed / STAGE_MS),
    STAGES.length - 1
  );

  return (
    <div className="card p-5 space-y-3 animate-fade-up">
      <div className="flex items-center gap-3">
        <div className="h-9 w-9 shrink-0 grid place-items-center rounded-md bg-blue-50 border border-blue-100">
          <Loader2 size={18} className="animate-spin text-blue-700" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-medium text-slate-900">OSIRIS is preparing your scope…</p>
          <p className="text-xs text-slate-500">
            {mediaCount > 0
              ? `${mediaCount} attachment${mediaCount > 1 ? "s" : ""} · Gemini Vision + DeepSeek`
              : "Notes-only analysis · DeepSeek Chat"}
          </p>
        </div>
      </div>

      <div className="space-y-1.5">
        {STAGES.map((stage, index) => {
          const done = index < activeIndex;
          const active = index === activeIndex;
          return (
            <div
              key={stage.key}
              className={`flex items-center gap-2 text-xs transition ${
                done ? "text-emerald-600" : active ? "text-blue-700" : "text-slate-400"
              }`}
            >
              {done ? (
                <CheckCircle2 size={14} />
              ) : active ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <span className="w-3.5" />
              )}
              <span className={active ? "animate-pulse-bar" : ""}>{stage.label}</span>
            </div>
          );
        })}
      </div>

      <div className="h-1 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-full rounded-full bg-slate-900 transition-all duration-500"
          style={{ width: `${((activeIndex + 1) / STAGES.length) * 100}%` }}
        />
      </div>
    </div>
  );
}
