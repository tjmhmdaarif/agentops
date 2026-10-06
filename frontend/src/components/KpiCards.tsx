import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Activity, Gauge, HeartPulse, ShieldCheck, Siren, Timer } from "lucide-react";
import { api } from "../lib/api";
import { duration } from "../lib/format";
import type { AnalyticsOverview } from "../types";
import { useApp } from "../hooks/store";

function Kpi({ icon, label, value, sub, tone = "text-slate-100" }: {
  icon: JSX.Element;
  label: string;
  value: string;
  sub?: string;
  tone?: string;
}) {
  return (
    <div className="panel px-3.5 py-3">
      <div className="flex items-center justify-between">
        <span className="label-xs">{label}</span>
        <span className="text-slate-600">{icon}</span>
      </div>
      <motion.p
        key={value}
        initial={{ opacity: 0.4, y: 3 }}
        animate={{ opacity: 1, y: 0 }}
        className={`num mt-1 text-xl font-semibold tracking-tight ${tone}`}
      >
        {value}
      </motion.p>
      {sub && <p className="mt-0.5 truncate text-[10px] text-slate-500">{sub}</p>}
    </div>
  );
}

export function KpiCards() {
  const { devices, deviceOrder, incidents } = useApp();
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);

  useEffect(() => {
    const load = () => api.analytics().then(setAnalytics).catch(() => undefined);
    load();
    const t = window.setInterval(load, 10000);
    return () => window.clearInterval(t);
  }, []);

  const stats = useMemo(() => {
    const list = deviceOrder.map((id) => devices[id]).filter(Boolean);
    const online = list.filter((d) => d.status === "ONLINE" || d.status === "WARNING").length;
    const avgHealth = list.length ? list.reduce((s, d) => s + d.health_score, 0) / list.length : 100;
    const active = Object.values(incidents).filter((i) =>
      ["OPEN", "INVESTIGATING", "MITIGATING", "MONITORING"].includes(i.status),
    ).length;
    return { online, total: list.length, avgHealth, active };
  }, [devices, deviceOrder, incidents]);

  return (
    <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-6">
      <Kpi
        icon={<HeartPulse className="h-3.5 w-3.5" />}
        label="Fleet Health"
        value={`${stats.avgHealth.toFixed(0)}%`}
        tone={stats.avgHealth >= 85 ? "text-emerald-300" : stats.avgHealth >= 60 ? "text-amber-300" : "text-red-300"}
        sub="mean health score"
      />
      <Kpi
        icon={<Gauge className="h-3.5 w-3.5" />}
        label="Devices Online"
        value={`${stats.online}/${stats.total}`}
        sub="online + warning"
      />
      <Kpi
        icon={<Siren className="h-3.5 w-3.5" />}
        label="Active Incidents"
        value={String(stats.active)}
        tone={stats.active > 0 ? "text-orange-300" : "text-slate-100"}
        sub="open pipeline"
      />
      <Kpi
        icon={<Activity className="h-3.5 w-3.5" />}
        label="Anomalies"
        value={String(analytics?.anomalies_detected ?? 0)}
        sub="last 24h"
      />
      <Kpi
        icon={<ShieldCheck className="h-3.5 w-3.5" />}
        label="Auto-Resolution"
        value={`${(analytics?.auto_resolution_rate ?? 100).toFixed(0)}%`}
        tone="text-emerald-300"
        sub="without a human"
      />
      <Kpi
        icon={<Timer className="h-3.5 w-3.5" />}
        label="Avg Resolution"
        value={analytics && analytics.mean_time_to_resolve_s > 0 ? duration(analytics.mean_time_to_resolve_s) : "—"}
        sub="MTTR"
      />
    </div>
  );
}
