export type DeviceStatus = "ONLINE" | "DEGRADED" | "WARNING" | "OFFLINE" | "RECOVERING";
export type Severity = "low" | "medium" | "high" | "critical";
export type IncidentStatus =
  | "OPEN" | "INVESTIGATING" | "MITIGATING" | "MONITORING"
  | "RESOLVED" | "ESCALATED" | "FALSE_POSITIVE";

export interface Device {
  id: string;
  name: string;
  device_type: string;
  location: string;
  status: DeviceStatus;
  health_score: number;
  last_seen: number;
  created_at: number;
  firmware_version: string;
  uptime: number;
  restart_count: number;
  latest_metrics: Record<string, number>;
  active_incidents: number;
}

export interface Incident {
  id: number;
  device_id: string;
  metric: string;
  severity: Severity;
  status: IncidentStatus;
  detector: string;
  anomaly_score: number;
  reason: string;
  created_at: number;
  updated_at: number;
  resolved_at: number | null;
  action_taken: string;
  resolution_notes: string;
}

export interface AgentEvent {
  id: number;
  incident_id: number;
  timestamp: number;
  event_type: string;
  message: string;
  tool_name: string;
  tool_input: string;
  tool_output: string;
  duration_ms: number;
}

export interface SimulationStatus {
  status: "STOPPED" | "RUNNING" | "PAUSED";
  speed: number;
  tick: number;
  device_count: number;
  started_at: number | null;
  anomaly_rate: string;
}

export interface AnalyticsOverview {
  telemetry_points: number;
  anomalies_detected: number;
  incidents_total: number;
  incidents_open: number;
  incidents_resolved: number;
  incidents_escalated: number;
  false_positives: number;
  auto_resolution_rate: number;
  mean_time_to_detect_s: number;
  mean_time_to_resolve_s: number;
  fleet_health_avg: number;
  devices_online: number;
  devices_total: number;
  most_problematic_device: string;
  most_common_anomaly: string;
  most_common_remediation: string;
  severity_distribution: Record<string, number>;
  status_distribution: Record<string, number>;
  metric_distribution: Record<string, number>;
  action_distribution: Record<string, number>;
  incident_histogram: { bucket: string; count: number }[];
  device_health: { device_id: string; health: number; status: string }[];
}

export interface HealthStatus {
  status: string;
  database: string;
  simulation: string;
  event_bus: string;
  agent: string;
  llm: string;
  uptime_s: number;
}

export interface AppConfig {
  app_env: string;
  llm_enabled: boolean;
  llm_provider: string;
  llm_model: string;
  anomaly_threshold: number;
  anomaly_persistence: number;
  incident_cooldown_seconds: number;
  simulation_speed: number;
  device_count: number;
  feature_flags: Record<string, boolean>;
  show_demo_creds: boolean;
}

export interface AuthPublicConfig {
  product: string;
  show_demo_creds: boolean;
  demo_username: string;
  demo_password: string;
}

export interface DevicePrediction {
  device_id: string;
  failure_risk: number;
  level: "low" | "moderate" | "high";
  experimental: boolean;
  factors: {
    health_score: number;
    open_incidents: number;
    restart_count: number;
    max_anomaly_score: number;
  };
}

export interface TelemetrySeries {
  device_id: string;
  metric: string;
  unit: string;
  baseline: number;
  normal_low?: number;
  normal_high?: number;
  points: { ts: number; value: number }[];
}

export interface Scenario {
  name: string;
  label: string;
  description: string;
}

export interface FeedItem {
  id: number;
  ts: number;
  kind: string;
  device_id?: string;
  incident_id?: number;
  title: string;
  detail?: string;
}

export interface DeviceAction {
  id: number;
  device_id: string;
  incident_id: number | null;
  action: string;
  status: string;
  reason: string;
  started_at: number;
  completed_at: number | null;
  result: string;
}

export const METRICS = [
  { key: "temperature", label: "Temperature", unit: "°C" },
  { key: "vibration", label: "Vibration", unit: "g" },
  { key: "battery", label: "Battery", unit: "%" },
  { key: "cpu_usage", label: "CPU", unit: "%" },
  { key: "memory_usage", label: "Memory", unit: "%" },
  { key: "network_latency", label: "Latency", unit: "ms" },
  { key: "signal_strength", label: "Signal", unit: "dBm" },
] as const;

export type MetricKey = (typeof METRICS)[number]["key"];
