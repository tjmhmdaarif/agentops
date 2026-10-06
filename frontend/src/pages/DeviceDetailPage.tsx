import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Calendar,
  Cog,
  MapPin,
  RotateCcw,
  Wrench,
} from "lucide-react";
import { LiveChart } from "../components/LiveChart";
import {
  EmptyState,
  HealthBar,
  IncidentStatusBadge,
  Panel,
  SeverityBadge,
  StatusDot,
} from "../components/primitives";
import { api } from "../lib/api";
import { ago, dateTime, duration, incidentCode, metricLabel } from "../lib/format";
import { useApp } from "../hooks/store";
import type { DeviceAction, DevicePrediction, Incident } from "../types";

/** EXPERIMENTAL — visible only when the `predictive_health` feature flag is on. */
function PredictiveHealthCard({ deviceId }: { deviceId: string }) {
  const [prediction, setPrediction] = useState<DevicePrediction | null>(null);
  useEffect(() => {
    const load = () => api.devicePrediction(deviceId).then(setPrediction).catch(() => setPrediction(null));
    load();
    const t = window.setInterval(load, 8000);
    return () => window.clearInterval(t);
  }, [deviceId]);
  if (!prediction) return null;
  const pct = Math.round(prediction.failure_risk * 100);
  const color = prediction.level === "high" ? "text-red-300" : prediction.level === "moderate" ? "text-amber-300" : "text-emerald-300";
  return (
    <div className="panel border-dashed border-fuchsia-500/30 px-3 py-2.5">
      <p className="label-xs flex items-center gap-1.5">
        Failure risk
        <span className="rounded border border-fuchsia-500/40 bg-fuchsia-500/10 px-1 text-[8px] font-bold uppercase text-fuchsia-300">
          experimental
        </span>
      </p>
      <div className={`num mt-1 text-lg font-semibold ${color}`}>{pct}%</div>
      <p className="text-[10px] capitalize text-slate-500">{prediction.level} risk · heuristic model</p>
    </div>
  );
}

export default function DeviceDetailPage() {
  const { id = "" } = useParams();
  const { devices, pushToast, config } = useApp();
  const device = devices[id];
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [actions, setActions] = useState<DeviceAction[]>([]);
  const [restarting, setRestarting] = useState(false);

  useEffect(() => {
    if (!id) return;
    const load = () => {
      api.deviceIncidents(id).then(setIncidents).catch(() => undefined);
      api.deviceActions(id).then(setActions).catch(() => undefined);
    };
    load();
    const t = window.setInterval(load, 5000);
    return () => window.clearInterval(t);
  }, [id]);

  if (!device) {
    return (
      <div className="p-4">
        <EmptyState
          title={`Device ${id} not found`}
          hint="It may not exist, or the fleet is still initializing."
          action={<Link to="/fleet" className="btn mt-2">Back to fleet</Link>}
        />
      </div>
    );
  }

  const doRestart = async () => {
    setRestarting(true);
    try {
      const r = await api.restartDevice(id);
      pushToast(r.status === "skipped" ? "warning" : "info",
        r.status === "skipped" ? "Restart skipped (recent restart)" : "Restart command sent", id);
    } catch (e) {
      pushToast("critical", "Restart failed", e instanceof Error ? e.message : undefined);
    } finally {
      setRestarting(false);
    }
  };

  return (
    <div className="space-y-3 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <Link to="/fleet" className="btn" aria-label="Back to fleet">
            <ArrowLeft className="h-3.5 w-3.5" />
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <StatusDot status={device.status} />
              <h1 className="num text-lg font-semibold tracking-tight text-slate-100">{device.id}</h1>
              <span className="text-xs text-slate-500">{device.name}</span>
            </div>
            <p className="text-xs text-slate-500">
              {device.device_type.replace(/_/g, " ")} · firmware v{device.firmware_version}
            </p>
          </div>
        </div>
        <button onClick={doRestart} disabled={restarting} className="btn btn-danger">
          <RotateCcw className="h-3 w-3" /> Restart device
        </button>
      </div>

      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-6">
        {[
          { label: "Health", value: <HealthBar score={device.health_score} /> },
          { label: "Uptime", value: <span className="num">{duration(device.uptime)}</span> },
          { label: "Restarts", value: <span className="num">{device.restart_count}</span> },
          { label: "Last seen", value: <span className="num">{ago(device.last_seen)}</span> },
          { label: "Location", value: <span className="flex items-center gap-1"><MapPin className="h-3 w-3 text-slate-600" />{device.location}</span> },
          { label: "Commissioned", value: <span className="flex items-center gap-1"><Calendar className="h-3 w-3 text-slate-600" />{dateTime(device.created_at)}</span> },
        ].map((c) => (
          <div key={c.label} className="panel px-3 py-2.5">
            <p className="label-xs">{c.label}</p>
            <div className="mt-1 text-xs text-slate-200">{c.value}</div>
          </div>
        ))}
        {config?.feature_flags?.predictive_health && <PredictiveHealthCard deviceId={id} />}
      </div>

      <LiveChart fixedDeviceId={id} height={300} />

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <Panel title="Incident History" pad={false}>
          {incidents.length === 0 ? (
            <EmptyState title="No incidents" hint="This device has a clean record." />
          ) : (
            <ul>
              {incidents.slice(0, 8).map((inc) => (
                <li key={inc.id}>
                  <Link
                    to={`/incidents/${inc.id}`}
                    className="flex items-center justify-between gap-2 border-b border-line/50 px-4 py-2.5 text-xs transition-colors last:border-0 hover:bg-ink-800/40"
                  >
                    <span className="num text-slate-400">{incidentCode(inc.id)}</span>
                    <span className="text-slate-300">{metricLabel(inc.metric)}</span>
                    <SeverityBadge severity={inc.severity} />
                    <IncidentStatusBadge status={inc.status} />
                    <span className="num text-[10px] text-slate-600">{ago(inc.created_at)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Panel>
        <Panel title="Agent & Operator Actions" pad={false}>
          {actions.length === 0 ? (
            <EmptyState title="No actions yet" hint="Remediation actions executed on this device appear here." />
          ) : (
            <ul>
              {actions.slice(0, 8).map((a) => (
                <li key={a.id} className="border-b border-line/50 px-4 py-2.5 text-xs last:border-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-1.5 text-slate-300">
                      {a.action === "restart_device" ? <RotateCcw className="h-3 w-3 text-slate-500" /> : <Wrench className="h-3 w-3 text-slate-500" />}
                      {a.action.replace(/_/g, " ")}
                    </span>
                    <span className={`text-[10px] font-semibold ${a.status === "COMPLETED" ? "text-emerald-400" : a.status === "SKIPPED" ? "text-amber-400" : "text-slate-500"}`}>
                      {a.status}
                    </span>
                  </div>
                  <p className="mt-0.5 line-clamp-2 text-[10px] text-slate-500">{a.reason || a.result}</p>
                  <p className="num mt-0.5 flex items-center gap-1 text-[9px] text-slate-600">
                    <Cog className="h-2.5 w-2.5" /> {ago(a.started_at)}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}
