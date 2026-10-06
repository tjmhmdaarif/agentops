import { useEffect, useMemo, useRef, useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../lib/api";
import { metricUnit, timeOfDay } from "../lib/format";
import { METRICS, type Device } from "../types";
import { useApp } from "../hooks/store";
import { Panel } from "./primitives";

const DEVICE_COLORS = ["#38bdf8", "#a78bfa", "#34d399", "#fbbf24"];

interface Point {
  ts: number;
  [deviceId: string]: number;
}

const MAX_POINTS = 120;
const WINDOWS = [
  { label: "5m", minutes: 5 },
  { label: "15m", minutes: 15 },
  { label: "30m", minutes: 30 },
  { label: "1h", minutes: 60 },
];

function ChartTooltip({ active, payload, label, unit }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-line bg-ink-850/95 px-2.5 py-1.5 text-[11px] shadow-panel">
      <p className="num mb-1 text-slate-500">{timeOfDay(label)}</p>
      {payload.map((p: any) => (
        <p key={p.dataKey} className="num" style={{ color: p.color }}>
          {p.dataKey}: {typeof p.value === "number" ? p.value.toFixed(2) : p.value} {unit}
        </p>
      ))}
    </div>
  );
}

export function LiveChart({ fixedDeviceId, height = 260 }: { fixedDeviceId?: string; height?: number }) {
  const { devices, deviceOrder, anomalies } = useApp();
  const [metric, setMetric] = useState<string>("temperature");
  const [selected, setSelected] = useState<string[]>(fixedDeviceId ? [fixedDeviceId] : []);
  const [minutes, setMinutes] = useState(15);
  const [data, setData] = useState<Point[]>([]);
  const [baseline, setBaseline] = useState<number | null>(null);
  const [band, setBand] = useState<[number, number] | null>(null);
  const lastSeen = useRef<Record<string, number>>({});

  // First-load default: preselect the first device so the chart is never blank.
  useEffect(() => {
    if (!fixedDeviceId && selected.length === 0 && deviceOrder.length > 0) {
      setSelected([deviceOrder[0]]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deviceOrder.length > 0]);

  const activeDevices = fixedDeviceId ? [fixedDeviceId] : selected.slice(0, 3);

  // Initial history load
  useEffect(() => {
    if (activeDevices.length === 0) {
      setData([]);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const series = await Promise.all(
          activeDevices.map((id) => api.deviceTelemetry(id, metric, minutes)),
        );
        if (cancelled) return;
        const byTs = new Map<number, Point>();
        for (const s of series) {
          for (const p of s.points) {
            const key = Math.round(p.ts);
            byTs.set(key, { ...(byTs.get(key) ?? { ts: key }), [s.device_id]: p.value });
          }
        }
        const sorted = [...byTs.values()].sort((a, b) => a.ts - b.ts).slice(-MAX_POINTS);
        setData(sorted);
        setBaseline(series[0]?.baseline ?? null);
        if (series[0]?.normal_low !== undefined && series[0]?.normal_high !== undefined) {
          setBand([series[0].normal_low, series[0].normal_high]);
        } else {
          setBand(null);
        }
        for (const s of sorted) {
          for (const id of activeDevices) {
            if (typeof s[id] === "number") lastSeen.current[id] = s.ts;
          }
        }
      } catch {
        if (!cancelled) setData([]);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [metric, minutes, fixedDeviceId, selected.join(",")]);

  // Live append from telemetry events flowing through the store
  useEffect(() => {
    if (activeDevices.length === 0) return;
    const fresh = activeDevices
      .map((id) => devices[id])
      .filter((d): d is Device => !!d && typeof d.latest_metrics?.[metric] === "number");
    if (fresh.length === 0) return;
    const newest = Math.max(...fresh.map((d) => d.last_seen));
    if (newest <= (lastSeen.current.__max ?? 0)) return;
    const changed = fresh.filter((d) => (lastSeen.current[d.id] ?? 0) < d.last_seen);
    if (changed.length === 0) return;
    for (const d of changed) lastSeen.current[d.id] = d.last_seen;
    lastSeen.current.__max = newest;
    setData((prev) => {
      const ts = Math.round(newest);
      const last = prev[prev.length - 1];
      const point: Point = last && last.ts === ts ? { ...last } : { ts };
      for (const d of changed) point[d.id] = d.latest_metrics[metric];
      if (point === last) return prev;
      return [...prev.slice(-(MAX_POINTS - 1)), point];
    });
  }, [devices, metric, activeDevices.join(",")]);

  const anomalyDots = useMemo(() => {
    if (data.length === 0) return [];
    const t0 = data[0].ts;
    const t1 = data[data.length - 1].ts;
    return anomalies
      .filter((a) => a.metric === metric && activeDevices.includes(a.device_id) && a.ts >= t0 && a.ts <= t1 + 2)
      .slice(-12)
      .map((a) => {
        // snap to the nearest buffered point
        let best = data[0];
        for (const p of data) if (Math.abs(p.ts - a.ts) < Math.abs(best.ts - a.ts)) best = p;
        const y = best[a.device_id];
        return typeof y === "number" ? { ts: best.ts, y, id: a.device_id } : null;
      })
      .filter((x): x is { ts: number; y: number; id: string } => x !== null);
  }, [anomalies, data, metric, activeDevices.join(",")]);

  const unit = metricUnit(metric);

  return (
    <Panel
      title="Live Telemetry"
      className="min-h-0"
      pad={false}
      right={
        <div className="flex flex-wrap items-center gap-1">
          {!fixedDeviceId &&
            deviceOrder.slice(0, 6).map((id, i) => (
              <button
                key={id}
                onClick={() =>
                  setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id].slice(-3)))
                }
                className={`rounded-md border px-1.5 py-0.5 text-[10px] font-medium transition-colors ${
                  selected.includes(id)
                    ? "border-sky-500/50 bg-sky-500/15 text-sky-300"
                    : "border-line text-slate-500 hover:text-slate-300"
                }`}
                style={selected.includes(id) ? { borderColor: DEVICE_COLORS[selected.indexOf(id) % 4] } : undefined}
              >
                {id}
              </button>
            ))}
          <div className="mx-1 h-3 w-px bg-line" />
          {WINDOWS.map((w) => (
            <button
              key={w.label}
              onClick={() => setMinutes(w.minutes)}
              className={`rounded px-1.5 py-0.5 text-[10px] transition-colors ${
                minutes === w.minutes ? "bg-ink-700 text-slate-200" : "text-slate-500 hover:text-slate-300"
              }`}
            >
              {w.label}
            </button>
          ))}
        </div>
      }
    >
      <div className="flex flex-wrap items-center gap-1 border-b border-line px-3 py-2">
        {METRICS.map((m) => (
          <button
            key={m.key}
            onClick={() => setMetric(m.key)}
            className={`rounded-md px-2 py-1 text-[10px] font-medium transition-colors ${
              metric === m.key ? "bg-ink-700 text-slate-100" : "text-slate-500 hover:text-slate-300"
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>
      <div style={{ height }} className="px-2 py-2">
        {activeDevices.length === 0 ? (
          <div className="flex h-full items-center justify-center text-xs text-slate-600">
            Select up to 3 devices to compare
          </div>
        ) : data.length < 2 ? (
          <div className="flex h-full items-center justify-center text-xs text-slate-600">
            Waiting for telemetry… start the simulation to see live data.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -14 }}>
              <CartesianGrid stroke="rgba(148,163,184,0.07)" vertical={false} />
              <XAxis
                dataKey="ts"
                tickFormatter={(v) => timeOfDay(v)}
                tickLine={false}
                axisLine={false}
                minTickGap={48}
              />
              <YAxis tickLine={false} axisLine={false} domain={["auto", "auto"]} width={56} />
              <Tooltip content={<ChartTooltip unit={unit} />} />
              {band && (
                <ReferenceArea y1={band[0]} y2={band[1]} fill="#34d399" fillOpacity={0.05} stroke="none" />
              )}
              {baseline !== null && activeDevices.length === 1 && (
                <ReferenceLine
                  y={baseline}
                  stroke="#64748b"
                  strokeDasharray="4 4"
                  strokeOpacity={0.6}
                  label={{ value: "baseline", position: "insideTopRight", fill: "#64748b", fontSize: 9 }}
                />
              )}
              {activeDevices.map((id, i) =>
                activeDevices.length === 1 ? (
                  <Area
                    key={id}
                    type="monotone"
                    dataKey={id}
                    stroke={DEVICE_COLORS[i]}
                    strokeWidth={1.6}
                    fill={DEVICE_COLORS[i]}
                    fillOpacity={0.12}
                    isAnimationActive={false}
                    dot={false}
                  />
                ) : (
                  <Line
                    key={id}
                    type="monotone"
                    dataKey={id}
                    stroke={DEVICE_COLORS[i]}
                    strokeWidth={1.6}
                    isAnimationActive={false}
                    dot={false}
                  />
                ),
              )}
              {anomalyDots.map((d, i) => (
                <ReferenceDot key={`${d.ts}-${i}`} x={d.ts} y={d.y} r={3.5} fill="#f87171" stroke="#7f1d1d" strokeWidth={1} />
              ))}
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>
    </Panel>
  );
}
