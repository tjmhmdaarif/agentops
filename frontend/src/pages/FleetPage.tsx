import { useMemo, useState } from "react";
import { Cpu } from "lucide-react";
import { FleetGrid } from "../components/FleetGrid";
import { EmptyState, Panel } from "../components/primitives";
import { useApp } from "../hooks/store";
import type { DeviceStatus } from "../types";

const STATUS_FILTERS = ["ALL", "ONLINE", "WARNING", "DEGRADED", "OFFLINE", "RECOVERING"] as const;

export default function FleetPage() {
  const { devices, deviceOrder } = useApp();
  const [filter, setFilter] = useState<(typeof STATUS_FILTERS)[number]>("ALL");
  const [query, setQuery] = useState("");

  const order = useMemo(() => {
    return deviceOrder.filter((id) => {
      const d = devices[id];
      if (!d) return false;
      if (filter !== "ALL" && d.status !== (filter as DeviceStatus)) return false;
      if (query && !id.toLowerCase().includes(query.toLowerCase()) &&
          !d.location.toLowerCase().includes(query.toLowerCase())) return false;
      return true;
    });
  }, [devices, deviceOrder, filter, query]);

  return (
    <div className="space-y-3 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-100">Fleet</h1>
          <p className="text-xs text-slate-500">{order.length} of {deviceOrder.length} devices</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter by id or location…"
            className="input w-48"
            aria-label="Filter devices"
          />
          <div className="flex gap-1">
            {STATUS_FILTERS.map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`rounded-md px-2 py-1 text-[10px] font-medium transition-colors ${
                  filter === f ? "bg-ink-700 text-slate-100" : "text-slate-500 hover:text-slate-300"
                }`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>
      </div>
      <Panel pad={false} className="p-3">
        {order.length === 0 ? (
          <EmptyState icon={<Cpu className="h-5 w-5" />} title="No devices match" hint="Adjust the filter or search query." />
        ) : (
          <FleetGrid devices={devices} order={order} />
        )}
      </Panel>
    </div>
  );
}
