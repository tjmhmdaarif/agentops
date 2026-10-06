import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Bot,
  CheckCircle2,
  ChevronDown,
  CircleDashed,
  Cog,
  FileSearch,
  Flag,
  Lightbulb,
  SearchCheck,
  Siren,
  X,
  XCircle,
} from "lucide-react";
import { api } from "../lib/api";
import { dateTime, incidentCode, metricLabel, prettyJson, timeOfDay } from "../lib/format";
import type { AgentEvent, Incident } from "../types";
import { IncidentStatusBadge, SeverityBadge, Spinner } from "./primitives";

const EVENT_META: Record<string, { icon: JSX.Element; tint: string; expandable: boolean }> = {
  AGENT_STARTED: { icon: <Bot className="h-3.5 w-3.5" />, tint: "text-sky-400 border-sky-500/30 bg-sky-500/10", expandable: false },
  THOUGHT: { icon: <Lightbulb className="h-3.5 w-3.5" />, tint: "text-slate-400 border-line bg-ink-800/60", expandable: false },
  TOOL_STARTED: { icon: <FileSearch className="h-3.5 w-3.5" />, tint: "text-violet-400 border-violet-500/30 bg-violet-500/10", expandable: true },
  TOOL_COMPLETED: { icon: <FileSearch className="h-3.5 w-3.5" />, tint: "text-violet-300 border-violet-500/30 bg-violet-500/10", expandable: true },
  DECISION: { icon: <Lightbulb className="h-3.5 w-3.5" />, tint: "text-amber-300 border-amber-500/30 bg-amber-500/10", expandable: true },
  REMEDIATION_STARTED: { icon: <Cog className="h-3.5 w-3.5" />, tint: "text-orange-300 border-orange-500/30 bg-orange-500/10", expandable: false },
  REMEDIATION_COMPLETED: { icon: <Cog className="h-3.5 w-3.5" />, tint: "text-orange-300 border-orange-500/30 bg-orange-500/10", expandable: true },
  RECOVERY_CHECK: { icon: <SearchCheck className="h-3.5 w-3.5" />, tint: "text-emerald-300 border-emerald-500/30 bg-emerald-500/10", expandable: true },
  INCIDENT_RESOLVED: { icon: <CheckCircle2 className="h-3.5 w-3.5" />, tint: "text-emerald-400 border-emerald-500/40 bg-emerald-500/15", expandable: false },
  INCIDENT_ESCALATED: { icon: <XCircle className="h-3.5 w-3.5" />, tint: "text-red-400 border-red-500/40 bg-red-500/15", expandable: false },
  FALSE_POSITIVE: { icon: <Flag className="h-3.5 w-3.5" />, tint: "text-slate-400 border-line bg-ink-800/60", expandable: false },
};

const EVENT_LABEL: Record<string, string> = {
  AGENT_STARTED: "Agent engaged",
  THOUGHT: "Observation",
  TOOL_STARTED: "Tool call",
  TOOL_COMPLETED: "Tool result",
  DECISION: "Decision",
  REMEDIATION_STARTED: "Remediation",
  REMEDIATION_COMPLETED: "Remediation result",
  RECOVERY_CHECK: "Recovery check",
  INCIDENT_RESOLVED: "Resolved",
  INCIDENT_ESCALATED: "Escalated",
  FALSE_POSITIVE: "False positive",
};

function TimelineEvent({ event, index }: { event: AgentEvent; index: number }) {
  const [open, setOpen] = useState(false);
  const meta = EVENT_META[event.event_type] ?? {
    icon: <CircleDashed className="h-3.5 w-3.5" />,
    tint: "text-slate-400 border-line bg-ink-800/60",
    expandable: false,
  };
  const hasPayload = Boolean(event.tool_input || event.tool_output);
  return (
    <motion.li
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: Math.min(index * 0.05, 0.8), duration: 0.25 }}
      className="relative flex gap-3 pb-4 last:pb-0"
    >
      {/* connector */}
      <span className="absolute left-[13px] top-7 h-[calc(100%-20px)] w-px bg-line" aria-hidden />
      <span className={`z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border ${meta.tint}`}>
        {meta.icon}
      </span>
      <div className="min-w-0 flex-1 pt-0.5">
        <div className="flex items-center justify-between gap-2">
          <p className="text-[11px] font-semibold text-slate-300">
            {EVENT_LABEL[event.event_type] ?? event.event_type}
            {event.tool_name && <span className="num ml-1.5 text-violet-300">{event.tool_name}</span>}
          </p>
          <span className="num shrink-0 text-[10px] text-slate-600">{timeOfDay(event.timestamp)}</span>
        </div>
        <p className="mt-0.5 text-[11px] leading-relaxed text-slate-400">{event.message}</p>
        {event.duration_ms > 0 && (
          <p className="num mt-0.5 text-[9px] text-slate-600">{event.duration_ms.toFixed(1)} ms</p>
        )}
        {meta.expandable && hasPayload && (
          <button
            onClick={() => setOpen((o) => !o)}
            className="mt-1 flex items-center gap-1 text-[10px] text-sky-400/80 transition-colors hover:text-sky-300 focus:outline-none focus-visible:ring-1 focus-visible:ring-sky-500"
            aria-expanded={open}
          >
            <ChevronDown className={`h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`} />
            {open ? "Hide" : "Show"} tool payload
          </button>
        )}
        <AnimatePresence>
          {open && hasPayload && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              {event.tool_input && (
                <div className="mt-1.5">
                  <p className="label-xs">Input</p>
                  <pre className="num mt-0.5 max-h-32 overflow-auto rounded-lg border border-line bg-ink-950/80 p-2 text-[10px] leading-relaxed text-slate-400">
                    {prettyJson(event.tool_input)}
                  </pre>
                </div>
              )}
              {event.tool_output && (
                <div className="mt-1.5">
                  <p className="label-xs">Output</p>
                  <pre className="num mt-0.5 max-h-40 overflow-auto rounded-lg border border-line bg-ink-950/80 p-2 text-[10px] leading-relaxed text-slate-400">
                    {prettyJson(event.tool_output)}
                  </pre>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.li>
  );
}

export function IncidentDetail({ incidentId }: { incidentId: number }) {
  const [incident, setIncident] = useState<Incident | null>(null);
  const [timeline, setTimeline] = useState<AgentEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIncident(null);
    setTimeline(null);
    setError(null);
    const load = async () => {
      try {
        const [inc, tl] = await Promise.all([
          api.incident(incidentId),
          api.incidentTimeline(incidentId),
        ]);
        if (!cancelled) {
          setIncident(inc);
          setTimeline(tl);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "failed to load");
      }
    };
    load();
    const isActive = (i: Incident | null) =>
      i && ["OPEN", "INVESTIGATING", "MITIGATING", "MONITORING"].includes(i.status);
    const t = window.setInterval(() => {
      if (isActive(incident)) load();
    }, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [incidentId]);

  const stats = useMemo(() => {
    if (!incident) return null;
    const duration = incident.resolved_at ? incident.resolved_at - incident.created_at : null;
    return { duration };
  }, [incident]);

  if (error) {
    return (
      <div className="p-4 text-center">
        <p className="text-xs text-red-400">Failed to load incident: {error}</p>
      </div>
    );
  }
  if (!incident || !timeline) {
    return (
      <div className="flex items-center justify-center gap-2 p-10 text-slate-500">
        <Spinner /> <span className="text-xs">Loading incident…</span>
      </div>
    );
  }
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="border-b border-line px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="num text-sm font-semibold text-slate-100">{incidentCode(incident.id)}</span>
            <SeverityBadge severity={incident.severity} />
            <IncidentStatusBadge status={incident.status} />
          </div>
          <span className="num text-[10px] text-slate-500">{dateTime(incident.created_at)}</span>
        </div>
        <p className="mt-1.5 text-xs text-slate-400">
          <span className="num text-slate-300">{incident.device_id}</span>
          {" · "}
          {metricLabel(incident.metric)}
          {" · score "}
          <span className="num">{incident.anomaly_score.toFixed(2)}</span>
          {" · "}
          {incident.detector}
          {stats?.duration != null && (
            <>
              {" · resolved in "}
              <span className="num">{stats.duration.toFixed(1)}s</span>
            </>
          )}
        </p>
        <div className="panel-inset mt-2 px-3 py-2">
          <p className="label-xs mb-0.5">Detection explanation</p>
          <p className="text-[11px] leading-relaxed text-slate-400">{incident.reason}</p>
        </div>
        {incident.resolution_notes && (
          <div className="panel-inset mt-2 border-emerald-500/20 px-3 py-2">
            <p className="label-xs mb-0.5 text-emerald-500/70">Resolution</p>
            <p className="text-[11px] leading-relaxed text-slate-400">{incident.resolution_notes}</p>
          </div>
        )}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
        <p className="label-xs mb-3 flex items-center gap-1.5">
          <Siren className="h-3 w-3" /> Agent execution
        </p>
        {timeline.length === 0 ? (
          <p className="text-xs text-slate-600">No agent events recorded yet.</p>
        ) : (
          <ul>
            {timeline.map((e, i) => (
              <TimelineEvent key={e.id} event={e} index={i} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export function IncidentDrawer({ incidentId, onClose }: { incidentId: number | null; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <AnimatePresence>
      {incidentId !== null && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/60"
          />
          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 320, damping: 32 }}
            className="fixed bottom-0 right-0 top-0 z-50 flex w-full max-w-lg flex-col border-l border-line bg-ink-900 shadow-2xl"
            role="dialog"
            aria-label="Incident detail"
          >
            <button
              onClick={onClose}
              className="absolute right-3 top-3 z-10 rounded-lg border border-line bg-ink-800 p-1.5 text-slate-400 transition-colors hover:text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
              aria-label="Close incident detail"
            >
              <X className="h-4 w-4" />
            </button>
            <IncidentDetail incidentId={incidentId} />
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
