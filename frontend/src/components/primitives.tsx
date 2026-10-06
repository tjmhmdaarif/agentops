import { motion } from "framer-motion";
import type { ReactNode } from "react";
import type { DeviceStatus, Severity } from "../types";

export const STATUS_STYLE: Record<DeviceStatus, { dot: string; text: string; ring: string; label: string }> = {
  ONLINE: { dot: "bg-emerald-400", text: "text-emerald-400", ring: "shadow-glow", label: "Online" },
  WARNING: { dot: "bg-amber-400", text: "text-amber-400", ring: "shadow-glow", label: "Warning" },
  DEGRADED: { dot: "bg-orange-400", text: "text-orange-400", ring: "shadow-glow", label: "Degraded" },
  OFFLINE: { dot: "bg-red-500", text: "text-red-400", ring: "shadow-glow", label: "Offline" },
  RECOVERING: { dot: "bg-sky-400", text: "text-sky-400", ring: "shadow-glow", label: "Recovering" },
};

export const SEVERITY_STYLE: Record<Severity, string> = {
  low: "bg-slate-500/15 text-slate-300 border-slate-500/30",
  medium: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  high: "bg-orange-500/15 text-orange-300 border-orange-500/30",
  critical: "bg-red-500/15 text-red-300 border-red-500/40",
};

export function StatusDot({ status, pulse }: { status: DeviceStatus; pulse?: boolean }) {
  const s = STATUS_STYLE[status] ?? STATUS_STYLE.ONLINE;
  const animated = pulse || status === "OFFLINE" || status === "DEGRADED" || status === "RECOVERING";
  return (
    <span className="relative inline-flex h-2 w-2">
      {animated && <span className={`absolute inline-flex h-full w-full rounded-full ${s.dot} opacity-60 animate-ping`} />}
      <span className={`relative inline-flex h-2 w-2 rounded-full ${s.dot}`} />
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: Severity | string }) {
  const cls = SEVERITY_STYLE[severity as Severity] ?? SEVERITY_STYLE.low;
  return (
    <span className={`inline-flex items-center rounded-md border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${cls}`}>
      {severity}
    </span>
  );
}

const INCIDENT_STATUS_STYLE: Record<string, string> = {
  OPEN: "bg-red-500/15 text-red-300 border-red-500/30",
  INVESTIGATING: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  MITIGATING: "bg-violet-500/15 text-violet-300 border-violet-500/30",
  MONITORING: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  RESOLVED: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  ESCALATED: "bg-red-500/20 text-red-200 border-red-500/50",
  FALSE_POSITIVE: "bg-slate-500/15 text-slate-400 border-slate-500/30",
};

export function IncidentStatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-flex items-center rounded-md border px-1.5 py-0.5 text-[10px] font-semibold tracking-wide ${INCIDENT_STATUS_STYLE[status] ?? INCIDENT_STATUS_STYLE.OPEN}`}>
      {status.replace("_", " ")}
    </span>
  );
}

export function HealthBar({ score }: { score: number }) {
  const color = score >= 85 ? "bg-emerald-400" : score >= 60 ? "bg-amber-400" : score >= 35 ? "bg-orange-400" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1 w-16 overflow-hidden rounded-full bg-ink-700">
        <motion.div
          className={`h-full rounded-full ${color}`}
          initial={false}
          animate={{ width: `${Math.max(2, Math.min(100, score))}%` }}
          transition={{ type: "spring", stiffness: 120, damping: 20 }}
        />
      </div>
      <span className="num text-xs text-slate-300">{score.toFixed(0)}</span>
    </div>
  );
}

export function Panel({ title, right, children, className = "", pad = true }: {
  title?: ReactNode;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
  pad?: boolean;
}) {
  return (
    <section className={`panel ${className}`}>
      {(title || right) && (
        <header className="flex items-center justify-between border-b border-line px-4 py-2.5">
          <h2 className="label-xs">{title}</h2>
          {right}
        </header>
      )}
      <div className={pad ? "p-4" : ""}>{children}</div>
    </section>
  );
}

export function EmptyState({ icon, title, hint, action }: {
  icon?: ReactNode;
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
      {icon && <div className="text-slate-600">{icon}</div>}
      <p className="text-sm font-medium text-slate-400">{title}</p>
      {hint && <p className="max-w-xs text-xs text-slate-500">{hint}</p>}
      {action}
    </div>
  );
}

export function Spinner() {
  return (
    <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-slate-600 border-t-sky-400" aria-label="loading" />
  );
}
