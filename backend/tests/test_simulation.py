"""Simulator tests: generation, baselines, injection, determinism."""
from __future__ import annotations

from app.simulation.device import SimulatedDevice
from app.simulation.engine import SimulationEngine
from app.simulation.scenarios import make_scenario
from app.simulation.telemetry import METRICS


def test_fleet_generation(settings):
    engine = SimulationEngine(settings)
    assert len(engine.devices) == 12
    ids = list(engine.devices)
    assert ids[0] == "EDGE-001" and ids[-1] == "EDGE-012"


def test_baselines_within_catalog_ranges(settings):
    engine = SimulationEngine(settings)
    for device in engine.devices.values():
        for metric, spec in METRICS.items():
            assert spec.base_min <= device.baselines[metric] <= spec.base_max


def test_deterministic_with_seed(settings):
    a = SimulatedDevice("EDGE-001", 0, seed=7)
    b = SimulatedDevice("EDGE-001", 0, seed=7)
    assert a.sample(1, 0.0) == b.sample(1, 0.0)


def test_temperature_spike_changes_output(settings):
    device = SimulatedDevice("EDGE-001", 0, seed=1)
    baseline_sample = device.sample(1, 0.0)
    device.inject(make_scenario("temperature_spike", "critical", tick=1, rng=device.rng))
    spiked = device.sample(2, 0.0)
    assert spiked["temperature"] > baseline_sample["temperature"] + 20


def test_restart_clears_restartable_effects(settings):
    device = SimulatedDevice("EDGE-001", 0, seed=1)
    device.inject(make_scenario("temperature_spike", "high", tick=1, rng=device.rng))
    assert device.has_active_scenario
    device.restart(tick=2)
    assert not device.has_active_scenario
    assert device.restart_count == 1
    assert device.is_offline  # brief reboot window


def test_battery_drain_survives_restart(settings):
    """Hardware faults must NOT be fixable by restart (forces escalation)."""
    device = SimulatedDevice("EDGE-001", 0, seed=1)
    device.inject(make_scenario("battery_drain", "high", tick=1, rng=device.rng))
    device.restart(tick=2)
    assert device.has_active_scenario


def test_offline_device_emits_nothing(settings):
    device = SimulatedDevice("EDGE-001", 0, seed=1)
    device.inject(make_scenario("device_offline", "high", tick=1, rng=device.rng))
    assert device.sample(2, 0.0) is None


def test_engine_step_returns_all_online_devices(settings):
    engine = SimulationEngine(settings)
    engine.start()
    readings = engine.step()
    assert len(readings) == len(engine.devices)
    for device_id, _ts, metrics in readings:
        assert set(metrics) == set(METRICS)


def test_pause_stops_step_output(settings):
    engine = SimulationEngine(settings)
    engine.start()
    engine.pause()
    assert engine.step() == []
