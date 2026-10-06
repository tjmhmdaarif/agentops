"""Metric specifications for simulated telemetry."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricSpec:
    unit: str
    base_min: float      # per-device baselines are drawn from [base_min, base_max]
    base_max: float
    noise: float         # gaussian noise sigma around baseline
    hard_min: float
    hard_max: float
    diurnal_amp: float = 0.0   # slow sinusoidal drift amplitude (organic feel)


METRICS: dict[str, MetricSpec] = {
    "temperature": MetricSpec("°C", 38.0, 45.0, 0.7, -20.0, 130.0, diurnal_amp=1.8),
    "vibration": MetricSpec("g", 0.20, 0.80, 0.06, 0.0, 12.0),
    "battery": MetricSpec("%", 78.0, 100.0, 1.2, 0.0, 100.0),
    "cpu_usage": MetricSpec("%", 20.0, 55.0, 4.0, 0.0, 100.0, diurnal_amp=6.0),
    "memory_usage": MetricSpec("%", 30.0, 65.0, 3.0, 0.0, 100.0),
    "network_latency": MetricSpec("ms", 20.0, 90.0, 7.0, 1.0, 3000.0),
    "signal_strength": MetricSpec("dBm", -75.0, -45.0, 2.5, -115.0, -20.0),
}

METRIC_NAMES: list[str] = list(METRICS.keys())
