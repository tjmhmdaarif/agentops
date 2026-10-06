import { memo, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { metricUnit, metricValue } from "../lib/format";
import type { Device } from "../types";
import { HealthBar, StatusDot } from "./primitives";

function Metric({ label, value, unit, delta }: { label: string; value: string; unit: string; delta: number | null }) {
  return (
    <div className="min-w-0">
      <p className="text-[9px] uppercase tracking-wider text-slate-600">{label}</p>
      <p className="num flex items-center gap-0.5 truncate text-[11px] text-slate-300">
        {value}
        <span className="text-[9px] text-slate-600">{unit}</span>
        {delta !== null && Math.abs(delta) > 0.001 && (
          delta > 0
            ? <ArrowUpRight className="h-2.5 w-2.5 text-orange-400" />
            : <ArrowDownRight className="h-2.5 w-2.5 text-sky-400" />
        )}
        {(delta === null || Math.abs(delta) <= 0.001) && <Minus className="h-2.5 w-2.5 text-slate-700" />}
      </p>
    </div>
  );
}

const SHOWN = ["temperature", "vibration", "battery", "cpu_usage"] as const;
const LABELS: Record<string, string> = {
  temperature: "TEMP", vibration: "VIB", battery: "BAT", cpu_usage: "CPU",
};

export const DeviceCard = memo(function DeviceCard({ device }: { device: Device }) {
  const prev = useRef<Record<string, number>>(device.latest_metrics);
  const [deltas, setDeltas] = useState<Record<string, number | null>>({});
  const [flash, setFlash] = useState(0);

  useEffect(() => {
    const d: Record<string, number | null> = {};
    for (const k of SHOWN) {
      const before = prev.current[k];
      const now = device.latest_metrics[k];
      d[k] = before === undefined || now === undefined ? null : now - before;
    }
    prev.current = device.latest_metrics;
    setDeltas(d);
    setFlash((f) => f + 1);
  }, [device.latest_metrics]);

  const borderByStatus =
    device.status === "OFFLINE"
      ? "border-red-500/40"
      : device.status === "DEGRADED"
        ? "border-orange-500/30"
        : device.status === "WARNING"
          ? "border-amber-500/25"
          : "border-line";

  return (
    <motion.div layout="position" transition={{ type: "spring", stiffness: 260, damping: 26 }}>
      <Link
        to={`/devices/${device.id}`}
        className={`block rounded-xl border ${borderByStatus} bg-ink-900/70 p-3 shadow-panel transition-colors hover:border-slate-500/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/60`}
      >
        <div key={flash} className="animate-tickFlash rounded-lg">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <StatusDot status={device.status} />
              <span className="num text-xs font-semibold text-slate-200">{device.id}</span>
              {device.active_incidents > 0 && (
                <span className="rounded bg-red-500/15 px-1 text-[9px] font-bold text-red-300">
                  {device.active_incidents} INC
                </span>
              )}
            </div>
            <span className={`text-[9px] font-medium uppercase tracking-wider ${
              device.status === "ONLINE" ? "text-emerald-500"
              : device.status === "WARNING" ? "text-amber-500"
              : device.status === "DEGRADED" ? "text-orange-400"
              : device.status === "RECOVERING" ? "text-sky-400"
              : "text-red-400"
            }`}>
              {device.status}
            </span>
          </div>
          <div className="mt-2 flex items-center justify-between">
            <span className="label-xs">Health</span>
            <HealthBar score={device.health_score} />
          </div>
          <div className="mt-2 grid grid-cols-4 gap-1.5">
            {SHOWN.map((k) => (
              <Metric
                key={k}
                label={LABELS[k]}
                value={metricValue(k, device.latest_metrics[k])}
                unit={metricUnit(k)}
                delta={deltas[k] ?? null}
              />
            ))}
          </div>
        </div>
      </Link>
    </motion.div>
  );
});

export function FleetGrid({ devices, order }: { devices: Record<string, Device>; order: string[] }) {
  return (
    <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
      {order.map((id) => {
        const d = devices[id];
        return d ? <DeviceCard key={id} device={d} /> : null;
      })}
    </div>
  );
}
