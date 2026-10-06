import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Activity, Database, ShieldCheck, Timer, Wrench } from "lucide-react";
import { EmptyState, Panel, Spinner } from "../components/primitives";
import { api } from "../lib/api";
import { duration, metricLabel } from "../lib/format";
import type { AnalyticsOverview } from "../types";

const SEV_COLORS: Record<string, string> = {
  low: "#64748b", medium: "#fbbf24", high: "#fb923c", critical: "#ef4444",
};
const STATUS_COLORS: Record<string, string> = {
  RESOLVED: "#34d399", ESCALATED: "#ef4444", FALSE_POSITIVE: "#64748b",
  OPEN: "#f87171", INVESTIGATING: "#38bdf8", MITIGATING: "#a78bfa", MONITORING: "#fbbf24",
};

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-line bg-ink-850/95 px-2.5 py-1.5 text-[11px] shadow-panel">
      <p className="text-slate-400">{label ?? payload[0].name}</p>
      <p className="num text-slate-200">{payload[0].value}</p>
    </div>
  );
}

function Stat({ icon, label, value, sub }: { icon: JSX.Element; label: string; value: string; sub?: string }) {
  return (
    <div className="panel px-3.5 py-3">
      <div className="flex items-center justify-between">
        <span className="label-xs">{label}</span>
        <span className="text-slate-600">{icon}</span>
      </div>
      <p className="num mt-1 text-lg font-semibold text-slate-100">{value}</p>
      {sub && <p className="mt-0.5 text-[10px] text-slate-500">{sub}</p>}
    </div>
  );
}

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = () => api.analytics().then(setData).catch((e) => setError(e.message));
    load();
    const t = window.setInterval(load, 10000);
    return () => window.clearInterval(t);
  }, []);

  if (error) {
    return (
      <div className="p-4">
        <EmptyState
          title="Analytics unavailable"
          hint={error}
          action={<button className="btn mt-2" onClick={() => { setError(null); api.analytics().then(setData).catch((e) => setError(e.message)); }}>Retry</button>}
        />
      </div>
    );
  }
  if (!data) {
    return (
      <div className="flex h-64 items-center justify-center gap-2 text-slate-500">
        <Spinner /> <span className="text-xs">Computing analytics…</span>
      </div>
    );
  }

  const sevData = Object.entries(data.severity_distribution).map(([name, value]) => ({ name, value }));
  const statusData = Object.entries(data.status_distribution).map(([name, value]) => ({ name, value }));
  const metricData = Object.entries(data.metric_distribution)
    .map(([name, value]) => ({ name: metricLabel(name), value }))
    .sort((a, b) => b.value - a.value);
  const actionData = Object.entries(data.action_distribution)
    .map(([name, value]) => ({ name: name.replace(/_/g, " "), value }))
    .sort((a, b) => b.value - a.value);
  const healthData = [...data.device_health].sort((a, b) => a.health - b.health);

  return (
    <div className="space-y-3 p-4">
      <div>
        <h1 className="text-lg font-semibold tracking-tight text-slate-100">Analytics</h1>
        <p className="text-xs text-slate-500">Fleet performance over the last 24 hours</p>
      </div>

      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-6">
        <Stat icon={<Database className="h-3.5 w-3.5" />} label="Telemetry Points" value={data.telemetry_points.toLocaleString()} />
        <Stat icon={<Activity className="h-3.5 w-3.5" />} label="Incidents" value={String(data.incidents_total)} sub={`${data.incidents_open} open`} />
        <Stat icon={<ShieldCheck className="h-3.5 w-3.5" />} label="Auto-Resolved" value={`${data.auto_resolution_rate}%`} sub={`${data.incidents_resolved} resolved · ${data.incidents_escalated} escalated`} />
        <Stat icon={<Timer className="h-3.5 w-3.5" />} label="MTTR" value={data.mean_time_to_resolve_s > 0 ? duration(data.mean_time_to_resolve_s) : "—"} sub="mean time to resolve" />
        <Stat icon={<Activity className="h-3.5 w-3.5" />} label="False Positives" value={String(data.false_positives)} sub="transient spikes" />
        <Stat icon={<Wrench className="h-3.5 w-3.5" />} label="Top Remediation" value={data.most_common_remediation.replace(/_/g, " ")} sub={`problem device: ${data.most_problematic_device}`} />
      </div>

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <Panel title="Incidents by Severity">
          {sevData.length === 0 ? <EmptyState title="No incidents yet" /> : (
            <div className="h-48">
              <ResponsiveContainer>
                <BarChart data={sevData} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
                  <CartesianGrid stroke="rgba(148,163,184,0.07)" vertical={false} />
                  <XAxis dataKey="name" tickLine={false} axisLine={false} />
                  <YAxis tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(148,163,184,0.06)" }} />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {sevData.map((d) => <Cell key={d.name} fill={SEV_COLORS[d.name] ?? "#64748b"} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>

        <Panel title="Outcome Distribution">
          {statusData.length === 0 ? <EmptyState title="No incidents yet" /> : (
            <div className="h-48">
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={statusData} dataKey="value" nameKey="name" innerRadius={48} outerRadius={72} paddingAngle={3} strokeWidth={0}>
                    {statusData.map((d) => <Cell key={d.name} fill={STATUS_COLORS[d.name] ?? "#64748b"} />)}
                  </Pie>
                  <Tooltip content={<ChartTooltip />} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
          <div className="mt-1 flex flex-wrap justify-center gap-2">
            {statusData.map((d) => (
              <span key={d.name} className="flex items-center gap-1 text-[10px] text-slate-400">
                <span className="h-2 w-2 rounded-full" style={{ background: STATUS_COLORS[d.name] ?? "#64748b" }} />
                {d.name.replace(/_/g, " ")} ({d.value})
              </span>
            ))}
          </div>
        </Panel>

        <Panel title="Anomalies by Metric">
          {metricData.length === 0 ? <EmptyState title="No anomalies yet" /> : (
            <div className="h-48">
              <ResponsiveContainer>
                <BarChart data={metricData} layout="vertical" margin={{ top: 4, right: 12, bottom: 0, left: 10 }}>
                  <CartesianGrid stroke="rgba(148,163,184,0.07)" horizontal={false} />
                  <XAxis type="number" tickLine={false} axisLine={false} allowDecimals={false} />
                  <YAxis type="category" dataKey="name" tickLine={false} axisLine={false} width={70} />
                  <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(148,163,184,0.06)" }} />
                  <Bar dataKey="value" fill="#38bdf8" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>

        <Panel title="Remediation Actions">
          {actionData.length === 0 ? <EmptyState title="No remediation yet" hint="Actions the agent executes appear here." /> : (
            <div className="h-48">
              <ResponsiveContainer>
                <BarChart data={actionData} layout="vertical" margin={{ top: 4, right: 12, bottom: 0, left: 10 }}>
                  <CartesianGrid stroke="rgba(148,163,184,0.07)" horizontal={false} />
                  <XAxis type="number" tickLine={false} axisLine={false} allowDecimals={false} />
                  <YAxis type="category" dataKey="name" tickLine={false} axisLine={false} width={110} />
                  <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(148,163,184,0.06)" }} />
                  <Bar dataKey="value" fill="#a78bfa" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>
      </div>

      <Panel title="Device Health Distribution">
        {healthData.length === 0 ? <EmptyState title="No devices" /> : (
          <div className="h-52">
            <ResponsiveContainer>
              <BarChart data={healthData} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
                <CartesianGrid stroke="rgba(148,163,184,0.07)" vertical={false} />
                <XAxis dataKey="device_id" tickLine={false} axisLine={false} interval={0} angle={-35} textAnchor="end" height={48} />
                <YAxis domain={[0, 100]} tickLine={false} axisLine={false} />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(148,163,184,0.06)" }} />
                <Bar dataKey="health" radius={[4, 4, 0, 0]}>
                  {healthData.map((d) => (
                    <Cell
                      key={d.device_id}
                      fill={d.health >= 85 ? "#34d399" : d.health >= 60 ? "#fbbf24" : d.health >= 35 ? "#fb923c" : "#ef4444"}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Panel>
    </div>
  );
}
