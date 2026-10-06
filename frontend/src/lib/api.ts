import type {
  AnalyticsOverview,
  AppConfig,
  Device,
  DeviceAction,
  HealthStatus,
  Incident,
  AgentEvent,
  Scenario,
  SimulationStatus,
  TelemetrySeries,
} from "../types";

const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    ...init,
  });
  if (res.status === 401 && !path.startsWith("/auth/")) {
    // Session expired mid-use — bounce back to the login screen.
    window.dispatchEvent(new CustomEvent("agentops:unauthenticated"));
  }
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body?.detail?.error || body?.detail?.message || body?.error?.message || detail;
    } catch {
      /* keep default */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export const authApi = {
  publicConfig: () => request<import("../types").AuthPublicConfig>("/auth/public-config"),
  login: (username: string, password: string) =>
    request<{ ok: boolean; username: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  logout: () => request<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  me: () => request<{ username: string; authenticated: boolean }>("/auth/me"),
  changePassword: (current_password: string, new_password: string) =>
    request<{ ok: boolean; message: string }>("/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password, new_password }),
    }),
};

export const api = {
  health: () => request<HealthStatus>("/health"),
  config: () => request<AppConfig>("/config"),
  devices: () => request<Device[]>("/devices"),
  device: (id: string) => request<Device>(`/devices/${id}`),
  deviceIncidents: (id: string) => request<Incident[]>(`/devices/${id}/incidents`),
  deviceActions: (id: string) => request<DeviceAction[]>(`/devices/${id}/actions`),
  deviceTelemetry: (id: string, metric: string, minutes: number) =>
    request<TelemetrySeries>(`/devices/${id}/telemetry?metric=${metric}&minutes=${minutes}`),
  incidents: (params?: { status?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    q.set("limit", String(params?.limit ?? 50));
    q.set("offset", String(params?.offset ?? 0));
    return request<{ items: Incident[]; total: number }>(`/incidents?${q}`);
  },
  incident: (id: number) => request<Incident>(`/incidents/${id}`),
  incidentTimeline: (id: number) => request<AgentEvent[]>(`/incidents/${id}/timeline`),
  analytics: () => request<AnalyticsOverview>("/analytics/overview"),
  simStatus: () => request<SimulationStatus>("/simulation/status"),
  scenarios: () => request<{ scenarios: Scenario[] }>("/simulation/scenarios"),
  simAction: (action: "start" | "stop" | "pause" | "resume" | "reset") =>
    request<SimulationStatus>(`/simulation/${action}`, { method: "POST" }),
  setSpeed: (speed: number) =>
    request<SimulationStatus>("/simulation/speed", { method: "POST", body: JSON.stringify({ speed }) }),
  setDeviceCount: (count: number) =>
    request<SimulationStatus>("/simulation/devices/count", { method: "POST", body: JSON.stringify({ count }) }),
  setAnomalyRate: (rate: string) =>
    request<SimulationStatus>("/simulation/anomaly-rate", { method: "POST", body: JSON.stringify({ rate }) }),
  inject: (device_id: string, scenario: string, severity: string) =>
    request<{ ok: boolean; label: string }>("/simulation/inject", {
      method: "POST",
      body: JSON.stringify({ device_id, scenario, severity }),
    }),
  runDemo: () => request<{ ok: boolean; message: string }>("/simulation/demo", { method: "POST" }),
  restartDevice: (id: string) =>
    request<{ status: string }>(`/devices/${id}/actions/restart`, { method: "POST" }),
  devicePrediction: (id: string) =>
    request<import("../types").DevicePrediction>(`/devices/${id}/prediction`),
};
