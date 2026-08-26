import { AlertTriangle, AlertOctagon, Info, CheckCircle2 } from "lucide-react";

const SEVERITY_STYLES: Record<string, string> = {
  Critical: "bg-red-500/15 text-red-400 border-red-500/30",
  Major: "bg-orange-500/15 text-orange-400 border-orange-500/30",
  Moderate: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
  Minor: "bg-sky-500/15 text-sky-400 border-sky-500/30",
  Info: "bg-slate-500/15 text-slate-400 border-slate-500/30",
};

const PRIORITY_STYLES: Record<string, string> = {
  Urgent: "bg-red-500/15 text-red-400 border-red-500/30",
  High: "bg-orange-500/15 text-orange-400 border-orange-500/30",
  Medium: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
  Low: "bg-slate-500/15 text-slate-400 border-slate-500/30",
};

function badgeClass(styles: Record<string, string>, value: string) {
  return styles[value] ?? styles.Info ?? styles.Low ?? "";
}

export function SeverityBadge({ severity }: { severity: string }) {
  const Icon =
    severity === "Critical" ? AlertOctagon : severity === "Major" ? AlertTriangle : severity === "Info" ? Info : AlertTriangle;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium whitespace-nowrap ${badgeClass(SEVERITY_STYLES, severity)}`}
    >
      <Icon size={10} />
      {severity}
    </span>
  );
}

export function PriorityBadge({ priority }: { priority: string }) {
  const Icon = priority === "Urgent" ? AlertOctagon : priority === "Low" ? CheckCircle2 : AlertTriangle;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium whitespace-nowrap ${badgeClass(PRIORITY_STYLES, priority)}`}
    >
      <Icon size={10} />
      {priority}
    </span>
  );
}
