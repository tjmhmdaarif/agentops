import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { api, SSE_URL } from "../lib/api";
import { metricLabel } from "../lib/format";
import type {
  AppConfig,
  Device,
  FeedItem,
  Incident,
  SimulationStatus,
} from "../types";

export type ConnectionState = "connecting" | "live" | "reconnecting";

interface Toast {
  id: number;
  kind: "info" | "success" | "warning" | "critical";
  title: string;
  detail?: string;
}

export interface AnomalyPoint {
  ts: number;
  device_id: string;
  metric: string;
  value: number;
  score: number;
  severity: string;
}

interface AppState {
  devices: Record<string, Device>;
  deviceOrder: string[];
  feed: FeedItem[];
  anomalies: AnomalyPoint[];
  incidents: Record<number, Incident>;
  sim: SimulationStatus | null;
  config: AppConfig | null;
  connection: ConnectionState;
  toasts: Toast[];
  dismissToast: (id: number) => void;
  refreshDevices: () => Promise<void>;
  pushToast: (kind: Toast["kind"], title: string, detail?: string) => void;
}

const Ctx = createContext<AppState | null>(null);

let feedSeq = 1;
let toastSeq = 1;
const MAX_FEED = 80;

export function AppProvider({ children }: { children: ReactNode }) {
  const [devices, setDevices] = useState<Record<string, Device>>({});
  const [deviceOrder, setDeviceOrder] = useState<string[]>([]);
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [anomalies, setAnomalies] = useState<AnomalyPoint[]>([]);
  const [incidents, setIncidents] = useState<Record<number, Incident>>({});
  const [sim, setSim] = useState<SimulationStatus | null>(null);
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [toasts, setToasts] = useState<Toast[]>([]);
  const devicesRef = useRef(devices);
  devicesRef.current = devices;

  const pushToast = useCallback((kind: Toast["kind"], title: string, detail?: string) => {
    const id = toastSeq++;
    setToasts((t) => [...t.slice(-4), { id, kind, title, detail }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 6000);
  }, []);

  const dismissToast = useCallback((id: number) => {
    setToasts((t) => t.filter((x) => x.id !== id));
  }, []);

  const pushFeed = useCallback((item: Omit<FeedItem, "id">) => {
    setFeed((f) => {
      // Coalesce repeat firings of the same anomaly (detector emits per tick
      // during the persistence window) into one bumped row.
      const [head, ...rest] = f;
      if (
        head && (item.kind === "critical" || item.kind === "warning") &&
        head.kind === item.kind && head.title === item.title &&
        item.ts - head.ts < 20
      ) {
        return [{ ...head, ts: item.ts, detail: item.detail }, ...rest];
      }
      return [{ ...item, id: feedSeq++ }, ...f].slice(0, MAX_FEED);
    });
  }, []);

  const refreshDevices = useCallback(async () => {
    const list = await api.devices();
    setDevices(Object.fromEntries(list.map((d) => [d.id, d])));
    setDeviceOrder(list.map((d) => d.id));
  }, []);

  // Initial load
  useEffect(() => {
    refreshDevices().catch(() => pushToast("critical", "Failed to load fleet"));
    api.config().then(setConfig).catch(() => undefined);
    api.simStatus().then(setSim).catch(() => undefined);
    api.incidents({ limit: 30 }).then((r) => {
      setIncidents(Object.fromEntries(r.items.map((i) => [i.id, i])));
    }).catch(() => undefined);
  }, [refreshDevices, pushToast]);

  // Single SSE connection for the whole app
  useEffect(() => {
    let closed = false;
    let es: EventSource | null = null;
    let retry = 0;
    let retryTimer: number | undefined;

    const connect = () => {
      if (closed) return;
      es = new EventSource(SSE_URL, { withCredentials: true });
      es.addEventListener("connected", () => {
        retry = 0;
        setConnection("live");
      });
      es.onerror = () => {
        setConnection("reconnecting");
        es?.close();
        if (!closed) {
          retryTimer = window.setTimeout(connect, Math.min(10000, 1000 * 2 ** retry++));
        }
      };
      es.addEventListener("telemetry", (ev) => {
        const d = JSON.parse((ev as MessageEvent).data);
        setDevices((prev) => {
          const existing = prev[d.device_id];
          if (!existing) return prev;
          const status: Device["status"] =
            d.status && d.status !== "ONLINE" ? d.status : existing.status === "OFFLINE" || existing.status === "RECOVERING" ? d.status ?? existing.status : existing.status;
          return {
            ...prev,
            [d.device_id]: {
              ...existing,
              latest_metrics: d.metrics,
              health_score: d.health_score,
              status: (d.status as Device["status"]) ?? status,
              last_seen: d.ts,
            },
          };
        });
      });
      es.addEventListener("device_status_changed", (ev) => {
        const d = JSON.parse((ev as MessageEvent).data);
        setDevices((prev) =>
          prev[d.device_id]
            ? { ...prev, [d.device_id]: { ...prev[d.device_id], status: d.status, health_score: d.health_score } }
            : prev,
        );
      });
      es.addEventListener("anomaly_detected", (ev) => {
        const d = JSON.parse((ev as MessageEvent).data);
        const ts = Date.now() / 1000;
        setAnomalies((prev) => [...prev.slice(-199), {
          ts, device_id: d.device_id, metric: d.metric,
          value: d.value ?? 0, score: d.score ?? 0, severity: d.severity ?? "low",
        }]);
        pushFeed({
          ts,
          kind: d.severity === "critical" || d.severity === "high" ? "critical" : "warning",
          device_id: d.device_id,
          title: `${metricLabel(d.metric)} anomaly · ${d.device_id}`,
          detail: `score ${d.score?.toFixed(2)} · ${(d.detectors || []).join(" + ")}`,
        });
      });
      es.addEventListener("failure_injected", (ev) => {
        const d = JSON.parse((ev as MessageEvent).data);
        pushFeed({ ts: Date.now() / 1000, kind: "inject", device_id: d.device_id, title: `Failure injected · ${d.device_id}`, detail: `${d.label} (${d.severity})` });
        pushToast("warning", `Failure injected on ${d.device_id}`, `${d.label} · ${d.severity}`);
      });
      const upsertIncident = (inc: Incident) =>
        setIncidents((prev) => ({ ...prev, [inc.id]: inc }));
      es.addEventListener("incident_created", (ev) => {
        const inc = JSON.parse((ev as MessageEvent).data).incident as Incident;
        upsertIncident(inc);
        pushFeed({ ts: inc.created_at, kind: "incident", device_id: inc.device_id, incident_id: inc.id, title: `Incident ${inc.device_id} · ${metricLabel(inc.metric)}`, detail: `${inc.severity.toUpperCase()} · score ${inc.anomaly_score.toFixed(2)}` });
        if (inc.severity === "critical" || inc.severity === "high") {
          pushToast("critical", `New ${inc.severity} incident`, `${inc.device_id} · ${metricLabel(inc.metric)}`);
        }
      });
      es.addEventListener("incident_updated", (ev) => {
        const d = JSON.parse((ev as MessageEvent).data);
        if (d.incident) upsertIncident(d.incident as Incident);
      });
      es.addEventListener("incident_resolved", (ev) => {
        const d = JSON.parse((ev as MessageEvent).data);
        if (d.incident) {
          upsertIncident(d.incident as Incident);
          pushFeed({ ts: Date.now() / 1000, kind: "resolved", device_id: d.incident.device_id, incident_id: d.incident.id, title: `Resolved · ${d.incident.device_id}`, detail: `action: ${d.incident.action_taken || "monitoring"}` });
          pushToast("success", `Incident resolved`, `${d.incident.device_id} recovered via ${d.incident.action_taken || "monitoring"}`);
        }
      });
      const agentListener = (kind: string) => (ev: MessageEvent) => {
        const d = JSON.parse(ev.data);
        pushFeed({
          ts: Date.now() / 1000,
          kind,
          device_id: d.device_id,
          incident_id: d.incident_id,
          title: d.message?.slice(0, 90) ?? kind,
          detail: d.tool ? `tool: ${d.tool}` : undefined,
        });
      };
      es.addEventListener("agent_started", agentListener("agent"));
      es.addEventListener("agent_decision", agentListener("decision"));
      es.addEventListener("remediation_started", agentListener("remediation"));
      es.addEventListener("remediation_completed", agentListener("remediation"));
      es.addEventListener("recovery_check", agentListener("recovery"));
      es.addEventListener("simulation_status", (ev) => {
        setSim(JSON.parse((ev as MessageEvent).data) as SimulationStatus);
      });
    };
    connect();
    return () => {
      closed = true;
      window.clearTimeout(retryTimer);
      es?.close();
    };
  }, [pushFeed, pushToast]);

  const value = useMemo<AppState>(
    () => ({ devices, deviceOrder, feed, anomalies, incidents, sim, config, connection, toasts, dismissToast, refreshDevices, pushToast }),
    [devices, deviceOrder, feed, anomalies, incidents, sim, config, connection, toasts, dismissToast, refreshDevices, pushToast],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp(): AppState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useApp must be used inside AppProvider");
  return ctx;
}
