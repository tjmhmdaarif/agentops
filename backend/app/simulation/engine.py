"""Simulation engine — owns the fleet and advances it one tick at a time.

The engine is deliberately synchronous and tick-driven: an async wrapper
(runtime) calls step() at wall-clock pace in production, while tests can drive
step() directly for fully deterministic behavior.
"""
from __future__ import annotations

import time
from typing import Optional

import numpy as np

from app.core.config import Settings
from app.core.logging import get_logger
from app.simulation.device import SimulatedDevice
from app.simulation.scenarios import make_scenario

log = get_logger("simulation")

STOPPED, RUNNING, PAUSED = "STOPPED", "RUNNING", "PAUSED"

AMBIENT_RATES = {"low": 0.0006, "normal": 0.0025, "high": 0.010, "chaos": 0.045}
AMBIENT_SCENARIOS = [
    "temperature_spike", "excessive_vibration", "cpu_saturation",
    "network_latency_spike", "memory_leak", "weak_signal", "temperature_drift",
]


class SimulationEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.status = STOPPED
        self.speed = settings.simulation_speed
        self.tick = 0
        self.started_at: Optional[float] = None
        self.anomaly_rate = "normal"
        self._seed = settings.random_seed
        self.rng = np.random.default_rng(self._seed)
        self.devices: dict[str, SimulatedDevice] = {}
        self._demo_script: list[dict] = []
        self._build_fleet(settings.device_count)

    # ------------------------------------------------------------------ fleet
    def _build_fleet(self, count: int) -> None:
        self.devices = {
            f"EDGE-{i + 1:03d}": SimulatedDevice(
                f"EDGE-{i + 1:03d}", i,
                seed=None if self._seed is None else self._seed + i,
            )
            for i in range(count)
        }

    def set_device_count(self, count: int) -> None:
        self._build_fleet(count)
        self.tick = 0

    # ----------------------------------------------------------------- control
    def start(self) -> None:
        if self.status == RUNNING:
            return
        self.status = RUNNING
        if self.started_at is None:
            self.started_at = time.time()
        log.info("simulation_started devices=%d speed=%.2fx", len(self.devices), self.speed)

    def pause(self) -> None:
        if self.status == RUNNING:
            self.status = PAUSED
            log.info("simulation_paused tick=%d", self.tick)

    def resume(self) -> None:
        if self.status == PAUSED:
            self.status = RUNNING
            log.info("simulation_resumed tick=%d", self.tick)

    def stop(self) -> None:
        self.status = STOPPED
        log.info("simulation_stopped tick=%d", self.tick)

    def reset(self) -> None:
        self._build_fleet(len(self.devices))
        self.tick = 0
        self.started_at = time.time() if self.status != STOPPED else None
        self._demo_script.clear()
        log.info("simulation_reset")

    # ------------------------------------------------------------------- tick
    def step(self) -> list[tuple[str, float, dict[str, float]]]:
        """Advance one tick. Returns [(device_id, ts, metrics)] for online devices."""
        if self.status != RUNNING:
            return []
        self.tick += 1
        now = time.time()
        self._run_demo_script()
        self._maybe_ambient_anomaly()
        readings: list[tuple[str, float, dict[str, float]]] = []
        for device in self.devices.values():
            sample = device.sample(self.tick, now)
            if sample is not None:
                readings.append((device.id, now, sample))
        return readings

    def _maybe_ambient_anomaly(self) -> None:
        """Background failure injector so the fleet feels alive without manual input."""
        rate = AMBIENT_RATES.get(self.anomaly_rate, 0.0025)
        if self.tick < 45:                      # warm-up: let baselines establish
            return
        if float(self.rng.random()) >= rate:
            return
        candidates = [d for d in self.devices.values() if not d.has_active_scenario and not d.is_offline]
        if not candidates:
            return
        device = candidates[int(self.rng.integers(0, len(candidates)))]
        scenario = AMBIENT_SCENARIOS[int(self.rng.integers(0, len(AMBIENT_SCENARIOS)))]
        severity = str(self.rng.choice(["low", "medium", "high"], p=[0.35, 0.45, 0.20]))
        self.inject(device.id, scenario, severity)
        log.info("ambient_injection device=%s scenario=%s severity=%s", device.id, scenario, severity)

    # --------------------------------------------------------------- injection
    def inject(self, device_id: str, scenario: str, severity: str) -> dict[str, object]:
        device = self.devices.get(device_id)
        if device is None:
            raise KeyError(f"unknown device: {device_id}")
        info = make_scenario(scenario, severity, self.tick, self.rng)
        device.inject(info)
        log.info("scenario_injected device=%s scenario=%s severity=%s", device_id, scenario, severity)
        return {
            "device_id": device_id,
            "scenario": scenario,
            "label": info.label,
            "severity": severity,
            "recoverable": info.recoverable,
        }

    # ------------------------------------------------------------------ actions
    def restart_device(self, device_id: str) -> dict[str, object]:
        device = self.devices[device_id]
        result = device.restart(self.tick)
        result["restart_count"] = device.restart_count
        return result

    # --------------------------------------------------------------- demo mode
    def run_demo_script(self) -> None:
        """Queue a scripted multi-failure demo. Executed by upcoming ticks."""
        ids = list(self.devices.keys())
        if not ids:
            return
        pick = lambda i: ids[i % len(ids)]  # noqa: E731
        self._demo_script = [
            {"at": self.tick + 6, "device": pick(3), "scenario": "temperature_spike", "severity": "critical"},
            {"at": self.tick + 20, "device": pick(6), "scenario": "excessive_vibration", "severity": "high"},
            {"at": self.tick + 38, "device": pick(1), "scenario": "battery_drain", "severity": "high"},
            {"at": self.tick + 55, "device": pick(8), "scenario": "network_latency_spike", "severity": "medium"},
            {"at": self.tick + 72, "device": pick(4), "scenario": "correlated_failure", "severity": "critical"},
        ]
        log.info("demo_script_queued steps=%d", len(self._demo_script))

    def _run_demo_script(self) -> None:
        due = [s for s in self._demo_script if s["at"] <= self.tick]
        self._demo_script = [s for s in self._demo_script if s["at"] > self.tick]
        for step_def in due:
            try:
                self.inject(step_def["device"], step_def["scenario"], step_def["severity"])
            except KeyError:
                continue

    # ------------------------------------------------------------------- misc
    def uptime_for(self, device_id: str, now: float | None = None) -> float:
        device = self.devices[device_id]
        now = now or time.time()
        return max(0.0, now - device.created_at)

    def summary(self) -> dict[str, object]:
        return {
            "status": self.status,
            "speed": self.speed,
            "tick": self.tick,
            "device_count": len(self.devices),
            "started_at": self.started_at,
            "anomaly_rate": self.anomaly_rate,
        }
