"""Failure scenario definitions.

A scenario is a list of effects applied to a device's metric generators.
Effects persist until they expire or are cleared by a remediation action.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

SEVERITY_SCALE: dict[str, float] = {"low": 0.5, "medium": 0.8, "high": 1.0, "critical": 1.45}

LONG = 60 * 60  # effectively "until remediated" at 1 tick/s


@dataclass
class Effect:
    """A single mutation applied to one metric (or to device availability)."""

    kind: str                 # add | mul | set | stuck | drain | ramp | offline
    metric: str               # ignored for kind == "offline"
    magnitude: float
    duration_ticks: int = LONG
    started_tick: int = 0
    clears_on_restart: bool = True
    stuck_value: float | None = None

    def expired(self, tick: int) -> bool:
        return tick - self.started_tick >= self.duration_ticks

    def apply(self, value: float, tick: int, noise: Callable[[float], float]) -> float:
        age = max(0, tick - self.started_tick)
        if self.kind == "add":
            return value + self.magnitude
        if self.kind == "mul":
            return value * self.magnitude
        if self.kind == "set":
            return self.magnitude + noise(0.02 * abs(self.magnitude) + 0.01)
        if self.kind == "stuck":
            return self.stuck_value if self.stuck_value is not None else value
        if self.kind == "drain":            # magnitude = absolute loss per tick
            return value - self.magnitude * age
        if self.kind == "ramp":             # magnitude = absolute growth per tick
            return value + self.magnitude * age
        return value


@dataclass
class ScenarioInfo:
    name: str
    label: str
    description: str
    effects: list[Effect] = field(default_factory=list)
    clears_on_restart: bool = True
    recoverable: bool = True     # False → agent should escalate to a human


SCENARIO_CATALOG: dict[str, dict[str, str]] = {
    "temperature_spike": {"label": "Temperature Spike", "description": "Sudden thermal excursion far above baseline."},
    "temperature_drift": {"label": "Temperature Drift", "description": "Slow sustained thermal creep — caught by EWMA, not spikes."},
    "excessive_vibration": {"label": "Excessive Vibration", "description": "Mechanical oscillation several times above baseline."},
    "battery_drain": {"label": "Battery Drain", "description": "Rapid, monotonic battery depletion. Requires human maintenance."},
    "cpu_saturation": {"label": "CPU Saturation", "description": "Processor pinned near 100%."},
    "memory_leak": {"label": "Memory Leak", "description": "Monotonically growing memory footprint."},
    "network_latency_spike": {"label": "Network Latency Spike", "description": "Severe network delay with jitter."},
    "weak_signal": {"label": "Weak Signal", "description": "Radio signal degraded near the noise floor."},
    "sensor_stuck": {"label": "Sensor Stuck", "description": "A sensor reports a frozen value — zero variance."},
    "correlated_failure": {"label": "Correlated Multi-Metric Failure", "description": "Temperature, vibration and CPU degrade together."},
    "device_offline": {"label": "Device Offline", "description": "Device stops emitting telemetry entirely."},
    "recovery_after_restart": {"label": "Recovery After Restart", "description": "Thermal fault that a restart reliably clears."},
}


def make_scenario(name: str, severity: str, tick: int, rng) -> ScenarioInfo:
    """Build the concrete effects for a named scenario at a given severity."""
    s = SEVERITY_SCALE.get(severity, 1.0)
    info = ScenarioInfo(name=name, **SCENARIO_CATALOG[name])

    if name == "temperature_spike":
        info.effects = [Effect("add", "temperature", 28.0 * s, started_tick=tick)]
    elif name == "temperature_drift":
        info.effects = [Effect("ramp", "temperature", 0.30 * s, started_tick=tick)]
    elif name == "excessive_vibration":
        info.effects = [Effect("mul", "vibration", 3.2 * s, started_tick=tick)]
    elif name == "battery_drain":
        info.effects = [Effect("drain", "battery", 0.50 * s, started_tick=tick, clears_on_restart=False)]
        info.clears_on_restart = False
        info.recoverable = False                      # needs a human with a battery pack
    elif name == "cpu_saturation":
        info.effects = [Effect("set", "cpu_usage", min(99.0, 93.0 * s), started_tick=tick)]
    elif name == "memory_leak":
        info.effects = [Effect("ramp", "memory_usage", 0.90 * s, started_tick=tick)]
    elif name == "network_latency_spike":
        # Transient external fault: expires on its own after a few minutes.
        info.effects = [Effect("add", "network_latency", 420.0 * s, duration_ticks=int(90 * s) + 30, started_tick=tick, clears_on_restart=False)]
        info.clears_on_restart = False
    elif name == "weak_signal":
        # Radio interference: usually transient; restart doesn't fix physics.
        info.effects = [Effect("set", "signal_strength", -96.0 - 6.0 * s, duration_ticks=int(90 * s) + 30, started_tick=tick, clears_on_restart=False)]
        info.clears_on_restart = False
    elif name == "sensor_stuck":
        metric = rng.choice(["temperature", "vibration"])
        info.effects = [Effect("stuck", metric, 0.0, started_tick=tick, stuck_value=None)]
    elif name == "correlated_failure":
        info.effects = [
            Effect("add", "temperature", 22.0 * s, started_tick=tick),
            Effect("mul", "vibration", 2.8 * s, started_tick=tick),
            Effect("add", "cpu_usage", 35.0 * s, started_tick=tick),
        ]
    elif name == "device_offline":
        info.effects = [Effect("offline", "", 0.0, duration_ticks=int(90 * s) + 30, started_tick=tick, clears_on_restart=True)]
    elif name == "recovery_after_restart":
        info.effects = [Effect("add", "temperature", 30.0 * s, started_tick=tick)]
    else:  # pragma: no cover - guarded by pydantic literal at the API edge
        raise ValueError(f"unknown scenario: {name}")
    return info
