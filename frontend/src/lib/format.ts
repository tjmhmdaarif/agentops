export function timeOfDay(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString("en-GB", { hour12: false });
}

export function dateTime(ts: number): string {
  return new Date(ts * 1000).toLocaleString("en-GB", {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false,
  });
}

export function duration(seconds: number): string {
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  return `${Math.floor(seconds / 86400)}d ${Math.floor((seconds % 86400) / 3600)}h`;
}

export function ago(ts: number): string {
  const diff = Math.max(0, Date.now() / 1000 - ts);
  if (diff < 2) return "just now";
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export function metricValue(metric: string, value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) return "—";
  if (metric === "signal_strength") return value.toFixed(0);
  if (metric === "network_latency") return value >= 100 ? value.toFixed(0) : value.toFixed(1);
  return value.toFixed(1);
}

export function metricUnit(metric: string): string {
  return (
    {
      temperature: "°C",
      vibration: "g",
      battery: "%",
      cpu_usage: "%",
      memory_usage: "%",
      network_latency: "ms",
      signal_strength: "dBm",
      availability: "",
    } as Record<string, string>
  )[metric] ?? "";
}

export function metricLabel(metric: string): string {
  return (
    {
      temperature: "Temperature",
      vibration: "Vibration",
      battery: "Battery",
      cpu_usage: "CPU",
      memory_usage: "Memory",
      network_latency: "Latency",
      signal_strength: "Signal",
      availability: "Availability",
    } as Record<string, string>
  )[metric] ?? metric;
}

export function incidentCode(id: number): string {
  return `INC-${String(id).padStart(3, "0")}`;
}

export function prettyJson(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}
