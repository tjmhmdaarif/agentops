"""Simulated IoT device with per-device baselines, noise and failure effects."""
from __future__ import annotations

import math
import time

import numpy as np

from app.simulation.scenarios import Effect, ScenarioInfo
from app.simulation.telemetry import METRICS, METRIC_NAMES

DEVICE_TYPES = ["edge_gateway", "sensor_hub", "industrial_controller", "telemetry_node"]
LOCATIONS = [
    "Plant A · Line 1", "Plant A · Line 2", "Plant A · Boiler Room",
    "Plant B · Assembly", "Plant B · Warehouse", "Plant B · Roof",
    "Substation 4", "Substation 7", "Cooling Loop North",
    "Cooling Loop South", "Perimeter Gate 2", "Perimeter Gate 5",
]


class SimulatedDevice:
    """Generates telemetry for one device. Deterministic when seeded."""

    def __init__(self, device_id: str, index: int, seed: int | None = None) -> None:
        self.id = device_id
        self.index = index
        self.rng = np.random.default_rng(seed)
        self.name = f"Edge Node {index + 1:02d}"
        self.device_type = DEVICE_TYPES[index % len(DEVICE_TYPES)]
        self.location = LOCATIONS[index % len(LOCATIONS)]
        self.firmware_version = f"2.{4 + index % 4}.{index % 9}"
        self.created_at = time.time()
        self.restart_count = 0

        # Per-device baselines drawn inside the catalogued healthy ranges.
        self.baselines: dict[str, float] = {
            m: float(self.rng.uniform(spec.base_min, spec.base_max))
            for m, spec in METRICS.items()
        }
        self._phase = float(self.rng.uniform(0, 2 * math.pi))  # diurnal phase offset
        self._stuck_cache: dict[str, float] = {}

        # Runtime state
        self.effects: list[Effect] = []
        self.scenarios: list[ScenarioInfo] = []
        self.offline_ticks_remaining = 0
        self.recovering_ticks_remaining = 0
        self.booted_tick = 0
        self.last_seen = time.time()
        self.last_metrics: dict[str, float] = dict(self.baselines)

    # ------------------------------------------------------------------ state
    @property
    def is_offline(self) -> bool:
        return self.offline_ticks_remaining > 0

    @property
    def is_recovering(self) -> bool:
        return self.recovering_ticks_remaining > 0

    @property
    def has_active_scenario(self) -> bool:
        return bool(self.effects)

    # ---------------------------------------------------------------- sampling
    def sample(self, tick: int, now: float) -> dict[str, float] | None:
        """Produce one reading per metric, or None when the device is offline."""
        if self.offline_ticks_remaining > 0:
            self.offline_ticks_remaining -= 1
            return None

        # offline effects force the device to drop
        for eff in self.effects:
            if eff.kind == "offline" and not eff.expired(tick):
                self.offline_ticks_remaining = max(self.offline_ticks_remaining, 1)
                return None

        self._expire_effects(tick)
        out: dict[str, float] = {}
        for metric in METRIC_NAMES:
            spec = METRICS[metric]
            diurnal = spec.diurnal_amp * math.sin(tick / 90.0 + self._phase)
            value = self.baselines[metric] + diurnal + float(self.rng.normal(0.0, spec.noise))
            for eff in self.effects:
                if eff.metric != metric:
                    continue
                if eff.kind == "stuck":
                    if eff.stuck_value is None:
                        eff.stuck_value = self._stuck_cache.get(metric, self.baselines[metric])
                    value = eff.stuck_value
                else:
                    value = eff.apply(value, tick, lambda sigma: float(self.rng.normal(0.0, sigma)))
            value = float(min(spec.hard_max, max(spec.hard_min, value)))
            out[metric] = round(value, 3)
        self._stuck_cache = out
        self.last_metrics = out
        self.last_seen = now
        if self.recovering_ticks_remaining > 0:
            self.recovering_ticks_remaining -= 1
        return out

    def _expire_effects(self, tick: int) -> None:
        if not self.effects:
            return
        self.effects = [e for e in self.effects if not e.expired(tick)]
        self.scenarios = [sc for sc in self.scenarios if any(e in self.effects for e in sc.effects)]

    # --------------------------------------------------------------- scenarios
    def inject(self, scenario: ScenarioInfo) -> None:
        for eff in scenario.effects:
            if eff.kind == "offline":
                self.offline_ticks_remaining = max(self.offline_ticks_remaining, eff.duration_ticks)
        self.effects.extend(scenario.effects)
        self.scenarios.append(scenario)

    # -------------------------------------------------------------- remediation
    def restart(self, tick: int) -> dict[str, object]:
        """Power-cycle: brief offline window, clears restart-clearable effects."""
        cleared = [e for e in self.effects if e.clears_on_restart]
        self.effects = [e for e in self.effects if not e.clears_on_restart]
        self.scenarios = [sc for sc in self.scenarios if any(e in self.effects for e in sc.effects)]
        # A restart is a short, controlled reboot — regardless of how long any
        # (now-cleared) offline scenario had left on the clock.
        self.offline_ticks_remaining = 2
        self.recovering_ticks_remaining = 5
        self.restart_count += 1
        self.booted_tick = tick
        self._stuck_cache = {}
        return {"cleared_effects": len(cleared), "remaining_effects": len(self.effects)}

    def reset_sensor(self) -> dict[str, object]:
        before = len(self.effects)
        self.effects = [e for e in self.effects if e.kind != "stuck"]
        self._stuck_cache = {}
        return {"cleared_effects": before - len(self.effects)}

    def set_safe_mode(self) -> dict[str, object]:
        """Throttles the device: caps CPU, sheds vibration-inducing load."""
        before = len(self.effects)
        self.effects = [
            e for e in self.effects
            if not (e.metric in {"cpu_usage", "vibration"} and e.kind in {"add", "mul", "set"})
        ]
        return {"cleared_effects": before - len(self.effects), "safe_mode": True}

    def reduce_sampling_rate(self) -> dict[str, object]:
        """Eases radio pressure: partially recovers signal/latency effects."""
        before = len(self.effects)
        self.effects = [
            e for e in self.effects
            if not (e.metric == "network_latency" and e.kind == "add")
        ]
        return {"cleared_effects": before - len(self.effects)}

    def clear_all_effects(self) -> None:
        self.effects.clear()
        self.scenarios.clear()
