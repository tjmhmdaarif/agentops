import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Siren } from "lucide-react";
import { api } from "../lib/api";
import { ago, duration, incidentCode, metricLabel } from "../lib/format";
import type { Incident } from "../types";
import { useApp } from "../hooks/store";
import { EmptyState, IncidentStatusBadge, Panel, SeverityBadge } from "./primitives";

export function IncidentRows({ incidents, onSelect }: { incidents: Incident[]; onSelect?: (id: number) => void }) {
  return (
    <>
      {incidents.map((inc) => (
        <motion.tr
          key={inc.id}
          layout="position"
          initial={{ opacity: 0, backgroundColor: "rgba(248,113,113,0.10)" }}
          animate={{ opacity: 1, backgroundColor: "rgba(248,113,113,0)" }}
          transition={{ duration: 0.6 }}
          onClick={() => onSelect?.(inc.id)}
          className="cursor-pointer border-b border-line/50 text-xs transition-colors last:border-0 hover:bg-ink-800/40"
        >
          <td className="num px-3 py-2 text-slate-400">
            <Link
              to={`/incidents/${inc.id}`}
              onClick={(e) => e.stopPropagation()}
              className="hover:text-sky-300 hover:underline"
            >
              {incidentCode(inc.id)}
            </Link>
          </td>
          <td className="num px-3 py-2 text-slate-300">{inc.device_id}</td>
          <td className="px-3 py-2 text-slate-400">{metricLabel(inc.metric)}</td>
          <td className="px-3 py-2"><SeverityBadge severity={inc.severity} /></td>
          <td className="px-3 py-2"><IncidentStatusBadge status={inc.status} /></td>
          <td className="px-3 py-2 text-[10px] text-slate-500">{inc.detector || "—"}</td>
          <td className="px-3 py-2 text-slate-400">{inc.action_taken ? inc.action_taken.replace(/_/g, " ") : "—"}</td>
          <td className="num px-3 py-2 text-right text-slate-500">
            {inc.resolved_at ? duration(inc.resolved_at - inc.created_at) : ago(inc.created_at)}
          </td>
        </motion.tr>
      ))}
    </>
  );
}

const FILTERS = ["ALL", "ACTIVE", "RESOLVED", "ESCALATED"] as const;
const ACTIVE = ["OPEN", "INVESTIGATING", "MITIGATING", "MONITORING"];

export function IncidentTable({ limit = 12, onSelect, title = "Incident Center" }: {
  limit?: number;
  onSelect?: (id: number) => void;
  title?: string;
}) {
  const { incidents: live } = useApp();
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("ALL");
  const [historical, setHistorical] = useState<Incident[]>([]);

  useEffect(() => {
    const load = () => api.incidents({ limit: 100 }).then((r) => setHistorical(r.items)).catch(() => undefined);
    load();
    const t = window.setInterval(load, 15000);
    return () => window.clearInterval(t);
  }, []);

  const merged = useMemo(() => {
    const map = new Map<number, Incident>();
    for (const i of historical) map.set(i.id, i);
    for (const i of Object.values(live)) map.set(i.id, i);
    let list = [...map.values()].sort((a, b) => b.created_at - a.created_at);
    if (filter === "ACTIVE") list = list.filter((i) => ACTIVE.includes(i.status));
    else if (filter !== "ALL") list = list.filter((i) => i.status === filter);
    return list.slice(0, limit);
  }, [historical, live, filter, limit]);

  return (
    <Panel
      title={title}
      pad={false}
      right={
        <div className="flex gap-1">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded px-1.5 py-0.5 text-[10px] transition-colors ${
                filter === f ? "bg-ink-700 text-slate-200" : "text-slate-500 hover:text-slate-300"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      }
    >
      {merged.length === 0 ? (
        <EmptyState
          icon={<Siren className="h-5 w-5" />}
          title={filter === "ALL" ? "No incidents yet" : `No ${filter.toLowerCase()} incidents`}
          hint="When the detection engine confirms an anomaly, an incident appears here and an agent engages automatically."
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-line text-left">
                {["Incident", "Device", "Metric", "Severity", "Status", "Detector", "Action", "Duration"].map((h) => (
                  <th key={h} className="label-xs px-3 py-2 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              <IncidentRows incidents={merged} onSelect={onSelect} />
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}
