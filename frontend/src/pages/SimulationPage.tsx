import { useEffect, useState } from "react";
import {
  FlaskConical,
  Gauge,
  Pause,
  Play,
  RotateCcw,
  Square,
  Zap,
} from "lucide-react";
import { EmptyState, Panel } from "../components/primitives";
import { api } from "../lib/api";
import { useApp } from "../hooks/store";
import type { Scenario, Severity } from "../types";

const SPEEDS = [0.25, 0.5, 1, 2, 5];
const DEVICE_COUNTS = [5, 10, 20, 50];
const RATES = ["low", "normal", "high", "chaos"];
const SEVERITIES: Severity[] = ["low", "medium", "high", "critical"];

export default function SimulationPage() {
  const { sim, devices, deviceOrder, pushToast, refreshDevices } = useApp();
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [deviceId, setDeviceId] = useState("EDGE-004");
  const [scenario, setScenario] = useState("temperature_spike");
  const [severity, setSeverity] = useState<Severity>("high");
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    api.scenarios().then((r) => setScenarios(r.scenarios)).catch(() => undefined);
  }, []);

  const run = async (label: string, fn: () => Promise<unknown>, after?: () => void) => {
    setBusy(label);
    try {
      await fn();
      after?.();
    } catch (e) {
      pushToast("critical", `${label} failed`, e instanceof Error ? e.message : undefined);
    } finally {
      setBusy(null);
    }
  };

  const inject = () =>
    run("Inject failure", async () => {
      await api.inject(deviceId, scenario, severity);
    });

  const status = sim?.status ?? "STOPPED";
  const selectedScenario = scenarios.find((s) => s.name === scenario);

  return (
    <div className="space-y-3 p-4">
      <div>
        <h1 className="text-lg font-semibold tracking-tight text-slate-100">Simulation Control</h1>
        <p className="text-xs text-slate-500">
          The simulation runs server-side as a background task — these controls change real engine state.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        {/* Engine control */}
        <Panel title="Engine">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400">Status</span>
              <span className={`flex items-center gap-1.5 text-xs font-semibold ${
                status === "RUNNING" ? "text-emerald-400" : status === "PAUSED" ? "text-amber-400" : "text-slate-400"
              }`}>
                <span className={`h-1.5 w-1.5 rounded-full ${
                  status === "RUNNING" ? "bg-emerald-400 animate-pulseDot" : status === "PAUSED" ? "bg-amber-400" : "bg-slate-600"
                }`} />
                {status} · tick {sim?.tick ?? 0}
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              <button className="btn btn-primary" disabled={busy !== null || status === "RUNNING"} onClick={() => run("Start", () => api.simAction("start"))}>
                <Play className="h-3 w-3" /> Start
              </button>
              <button className="btn" disabled={busy !== null || status !== "RUNNING"} onClick={() => run("Pause", () => api.simAction("pause"))}>
                <Pause className="h-3 w-3" /> Pause
              </button>
              <button className="btn" disabled={busy !== null || status !== "PAUSED"} onClick={() => run("Resume", () => api.simAction("resume"))}>
                <Play className="h-3 w-3" /> Resume
              </button>
              <button className="btn" disabled={busy !== null || status === "STOPPED"} onClick={() => run("Stop", () => api.simAction("stop"))}>
                <Square className="h-3 w-3" /> Stop
              </button>
              <button
                className="btn btn-danger"
                disabled={busy !== null}
                onClick={() => run("Reset", async () => { await api.simAction("reset"); }, refreshDevices)}
              >
                <RotateCcw className="h-3 w-3" /> Reset
              </button>
            </div>

            <div>
              <p className="label-xs mb-1.5 flex items-center gap-1"><Gauge className="h-3 w-3" /> Speed</p>
              <div className="flex gap-1">
                {SPEEDS.map((s) => (
                  <button
                    key={s}
                    disabled={busy !== null}
                    onClick={() => run("Set speed", () => api.setSpeed(s))}
                    className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                      sim?.speed === s
                        ? "border-sky-500/50 bg-sky-500/15 text-sky-300"
                        : "border-line text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    {s}×
                  </button>
                ))}
              </div>
            </div>

            <div>
              <p className="label-xs mb-1.5">Fleet size (rebuilds fleet)</p>
              <div className="flex gap-1">
                {DEVICE_COUNTS.map((c) => (
                  <button
                    key={c}
                    disabled={busy !== null}
                    onClick={() =>
                      run("Set device count", async () => { await api.setDeviceCount(c); }, refreshDevices)
                    }
                    className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                      sim?.device_count === c
                        ? "border-sky-500/50 bg-sky-500/15 text-sky-300"
                        : "border-line text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    {c}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <p className="label-xs mb-1.5">Ambient anomaly rate</p>
              <div className="flex gap-1">
                {RATES.map((r) => (
                  <button
                    key={r}
                    disabled={busy !== null}
                    onClick={() => run("Set anomaly rate", () => api.setAnomalyRate(r))}
                    className={`rounded-lg border px-3 py-1.5 text-xs font-medium capitalize transition-colors ${
                      sim?.anomaly_rate === r
                        ? "border-fuchsia-500/50 bg-fuchsia-500/15 text-fuchsia-300"
                        : "border-line text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    {r}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </Panel>

        {/* Failure injection */}
        <Panel title="Failure Injection">
          <div className="space-y-4">
            <div>
              <label htmlFor="inj-device" className="label-xs mb-1.5 block">Device</label>
              <select id="inj-device" value={deviceId} onChange={(e) => setDeviceId(e.target.value)} className="input">
                {deviceOrder.map((id) => (
                  <option key={id} value={id}>
                    {id} · {devices[id]?.location ?? ""}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="inj-scenario" className="label-xs mb-1.5 block">Failure scenario</label>
              <select id="inj-scenario" value={scenario} onChange={(e) => setScenario(e.target.value)} className="input">
                {scenarios.map((s) => (
                  <option key={s.name} value={s.name}>{s.label}</option>
                ))}
              </select>
              {selectedScenario && (
                <p className="mt-1.5 text-[11px] leading-relaxed text-slate-500">{selectedScenario.description}</p>
              )}
            </div>
            <div>
              <p className="label-xs mb-1.5">Severity</p>
              <div className="flex gap-1">
                {SEVERITIES.map((s) => (
                  <button
                    key={s}
                    onClick={() => setSeverity(s)}
                    className={`rounded-lg border px-3 py-1.5 text-xs font-medium capitalize transition-colors ${
                      severity === s
                        ? s === "critical" ? "border-red-500/60 bg-red-500/15 text-red-300"
                          : s === "high" ? "border-orange-500/60 bg-orange-500/15 text-orange-300"
                          : s === "medium" ? "border-amber-500/60 bg-amber-500/15 text-amber-300"
                          : "border-slate-500/60 bg-slate-500/15 text-slate-300"
                        : "border-line text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
            <button
              onClick={inject}
              disabled={busy !== null || status !== "RUNNING"}
              className="btn btn-danger w-full justify-center py-2 text-sm"
            >
              <FlaskConical className="h-4 w-4" />
              {status !== "RUNNING" ? "Start the simulation to inject" : "Inject Failure"}
            </button>
          </div>
        </Panel>
      </div>

      {/* Demo mode */}
      <Panel className="border-sky-500/20 bg-sky-500/[0.03]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-100">
              <Zap className="h-4 w-4 text-sky-400" /> Run Demo Scenario
            </h2>
            <p className="mt-1 max-w-xl text-xs leading-relaxed text-slate-400">
              Queues a scripted sequence — thermal spike, vibration fault, battery drain, network
              degradation and a correlated multi-metric failure — then lets the agents respond.
              Watch the activity feed and incident center.
            </p>
          </div>
          <button
            className="btn btn-primary px-4 py-2 text-sm"
            disabled={busy !== null}
            onClick={() =>
              run("Demo", async () => {
                const r = await api.runDemo();
                pushToast("info", "Demo scenario queued", r.message);
              })
            }
          >
            <Zap className="h-4 w-4" /> Run Demo
          </button>
        </div>
      </Panel>

      {deviceOrder.length === 0 && (
        <EmptyState title="Fleet not initialized" hint="Check the backend connection." />
      )}
    </div>
  );
}
