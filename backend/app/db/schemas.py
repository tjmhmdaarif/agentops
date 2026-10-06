"""Pydantic v2 schemas for API requests/responses."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# ------------------------------------------------------------------- devices


class DeviceOut(BaseModel):
    id: str
    name: str
    device_type: str
    location: str
    status: str
    health_score: float
    last_seen: float
    created_at: float
    firmware_version: str
    uptime: float
    restart_count: int
    latest_metrics: dict[str, float] = Field(default_factory=dict)
    active_incidents: int = 0


class TelemetryPoint(BaseModel):
    ts: float
    value: float


class TelemetrySeries(BaseModel):
    device_id: str
    metric: str
    unit: str
    baseline: float
    points: list[TelemetryPoint]


class DeviceActionOut(BaseModel):
    id: int
    device_id: str
    incident_id: Optional[int]
    action: str
    status: str
    reason: str
    started_at: float
    completed_at: Optional[float]
    result: str


# ----------------------------------------------------------------- incidents


class IncidentOut(BaseModel):
    id: int
    device_id: str
    metric: str
    severity: str
    status: str
    detector: str
    anomaly_score: float
    reason: str
    created_at: float
    updated_at: float
    resolved_at: Optional[float]
    action_taken: str
    resolution_notes: str


class IncidentListOut(BaseModel):
    items: list[IncidentOut]
    total: int
    limit: int
    offset: int


class AgentEventOut(BaseModel):
    id: int
    incident_id: int
    timestamp: float
    event_type: str
    message: str
    tool_name: str
    tool_input: str
    tool_output: str
    duration_ms: float


# ---------------------------------------------------------------- simulation


ScenarioName = Literal[
    "temperature_spike", "temperature_drift", "excessive_vibration",
    "battery_drain", "cpu_saturation", "memory_leak", "network_latency_spike",
    "weak_signal", "sensor_stuck", "correlated_failure", "device_offline",
    "recovery_after_restart",
]

SeverityName = Literal["low", "medium", "high", "critical"]


class InjectRequest(BaseModel):
    device_id: str
    scenario: ScenarioName
    severity: SeverityName = "high"


class SimulationStatusOut(BaseModel):
    status: str
    speed: float
    tick: int
    device_count: int
    started_at: Optional[float]
    anomaly_rate: str


class SpeedRequest(BaseModel):
    speed: float = Field(gt=0, le=20)


class DeviceCountRequest(BaseModel):
    count: int = Field(ge=1, le=50)


class AnomalyRateRequest(BaseModel):
    rate: Literal["low", "normal", "high", "chaos"]


# ----------------------------------------------------------------- analytics


class AnalyticsOverview(BaseModel):
    telemetry_points: int
    anomalies_detected: int
    incidents_total: int
    incidents_open: int
    incidents_resolved: int
    incidents_escalated: int
    false_positives: int
    auto_resolution_rate: float
    mean_time_to_detect_s: float
    mean_time_to_resolve_s: float
    fleet_health_avg: float
    devices_online: int
    devices_total: int
    most_problematic_device: str
    most_common_anomaly: str
    most_common_remediation: str
    severity_distribution: dict[str, int]
    status_distribution: dict[str, int]
    metric_distribution: dict[str, int]
    action_distribution: dict[str, int]
    incident_histogram: list[dict[str, Any]]
    device_health: list[dict[str, Any]]


class HealthOut(BaseModel):
    status: str
    database: str
    simulation: str
    event_bus: str
    agent: str
    llm: str
    uptime_s: float


class ConfigOut(BaseModel):
    app_env: str
    llm_enabled: bool
    llm_provider: str
    llm_model: str
    anomaly_threshold: float
    anomaly_persistence: int
    incident_cooldown_seconds: float
    simulation_speed: float
    device_count: int
    feature_flags: dict[str, bool] = Field(default_factory=dict)
    show_demo_creds: bool = False
    demo_username: str = ""
    demo_password: str = ""
