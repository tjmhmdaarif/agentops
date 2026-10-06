"""Detection engine tests: individual detectors, fusion, severity, suppression."""
from __future__ import annotations

import numpy as np

from app.detection.detector import HybridDetector
from app.detection.ewma import EWMADetector
from app.detection.isolation_forest import DeviceIsolationForest
from app.detection.rate import RateOfChangeDetector
from app.detection.scoring import severity_for
from app.detection.zscore import RollingZScore
from app.simulation.telemetry import METRIC_NAMES

from tests.conftest import run_ticks


def _flat_metrics(base: float = 42.0) -> dict[str, float]:
    return {m: base if m == "temperature" else 1.0 for m in METRIC_NAMES}


# ------------------------------------------------------------------ univariate


def test_zscore_fires_on_spike():
    z = RollingZScore(window=40, min_samples=10)
    rng = np.random.default_rng(0)
    last = 0.0
    for _ in range(30):
        last, _, _ = z.update(42.0 + float(rng.normal(0, 0.5)))
    assert last < 3.0
    spiked, _, _ = z.update(70.0)
    assert spiked > 3.0


def test_zscore_ignores_normal_noise():
    z = RollingZScore(window=40, min_samples=10)
    rng = np.random.default_rng(1)
    for _ in range(39):
        value, _, _ = z.update(42.0 + float(rng.normal(0, 0.5)))
    assert value < 3.0


def test_ewma_detects_sustained_drift():
    e = EWMADetector(noise_floor=0.5)
    rng = np.random.default_rng(2)
    fired = False
    for i in range(60):
        value = 42.0 + float(rng.normal(0, 0.5)) + (0.4 * i if i > 25 else 0.0)
        drift_z, _ = e.update(value)
        fired = fired or drift_z >= 2.5
    assert fired


def test_ewma_stable_on_stationary_noise():
    e = EWMADetector(noise_floor=0.5)
    rng = np.random.default_rng(3)
    worst = 0.0
    for _ in range(80):
        drift_z, _ = e.update(42.0 + float(rng.normal(0, 0.5)))
        worst = max(worst, drift_z)
    assert worst < 2.5


def test_rate_of_change_detects_jump():
    r = RateOfChangeDetector()
    r.update(42.0)
    r.update(42.3)
    delta, rel = r.update(58.0)
    assert delta > 15 and rel > 0.3


def test_rate_gating_requires_absolute_move(runtime):
    """Small-baseline relative noise must not fire rate-of-change."""
    det = runtime.detector
    det.settings.roc_threshold = 0.45
    metrics = _flat_metrics()
    for i in range(20):
        metrics["network_latency"] = 25.0 + (5.0 if i % 2 else -5.0)  # ±20% noise, ±5ms absolute
        results = det.evaluate("EDGE-001", metrics, i)
    assert all("rate" not in d.detectors for d in results)


# -------------------------------------------------------------- isolation forest


def test_isolation_forest_detects_correlated_anomaly():
    forest = DeviceIsolationForest(min_samples=50, retrain_every=10**9, seed=0)
    rng = np.random.default_rng(5)
    for _ in range(120):
        metrics = {m: float(v) for m, v in zip(METRIC_NAMES, rng.normal(0, 1, len(METRIC_NAMES)))}
        forest.observe(metrics)
    assert forest.maybe_train()
    normal = {m: float(v) for m, v in zip(METRIC_NAMES, rng.normal(0, 1, len(METRIC_NAMES)))}
    anomaly = {m: float(v) for m, v in zip(METRIC_NAMES, rng.normal(6, 1, len(METRIC_NAMES)))}
    assert forest.score(anomaly) > forest.score(normal)
    assert forest.score(anomaly) > 0.55


def test_isolation_forest_fast_path_matches_sklearn():
    forest = DeviceIsolationForest(min_samples=50, retrain_every=10**9, seed=0)
    rng = np.random.default_rng(6)
    for _ in range(80):
        forest.observe({m: float(v) for m, v in zip(METRIC_NAMES, rng.normal(0, 1, len(METRIC_NAMES)))})
    forest.maybe_train()
    assert forest.fast_ok  # validation inside _try_build_fast_path passed


# --------------------------------------------------------------------- fusion


def test_severity_bands():
    assert severity_for(0.20) == "normal"
    assert severity_for(0.40) == "low"
    assert severity_for(0.60) == "medium"
    assert severity_for(0.75) == "high"
    assert severity_for(0.90) == "critical"


def test_persistence_required(runtime):
    """A single anomalous reading must not produce a DetectionResult."""
    rng = np.random.default_rng(11)
    det = runtime.detector
    metrics = _flat_metrics()
    for i in range(30):  # noisy warmup (flat data would trip stuck-sensor rules)
        metrics["temperature"] = 42.0 + float(rng.normal(0, 0.5))
        det.evaluate("EDGE-001", metrics, i)
    spiked = dict(metrics)
    spiked["temperature"] = 95.0
    results = det.evaluate("EDGE-001", spiked, 31)
    assert all(r.metric != "temperature" for r in results)
    results = det.evaluate("EDGE-001", spiked, 32)
    assert all(r.metric != "temperature" for r in results)
    results = det.evaluate("EDGE-001", spiked, 33)
    assert any(r.metric == "temperature" for r in results)


def test_stuck_sensor_detected(runtime):
    det = runtime.detector
    metrics = _flat_metrics()
    results = []
    for i in range(40):
        metrics["vibration"] = 0.5 if i < 15 else 0.5  # frozen the whole time
        results = det.evaluate("EDGE-001", metrics, i)
    assert any("zero_variance" in r.detectors for r in results)


# -------------------------------------------------------------- integration


def test_no_anomalies_on_healthy_fleet(runtime):
    """Warmup + healthy operation should produce no incident-worthy detections."""
    run_ticks(runtime, 60)
    det = runtime.detector
    # Manually scan: no metric should currently be in persistent-anomaly state.
    for state in det._metric_state.values():
        assert state.consecutive_anomalies < det.settings.anomaly_persistence


def test_spike_produces_detection_result(runtime):
    run_ticks(runtime, 30)
    runtime.engine.inject("EDGE-002", "temperature_spike", "critical")
    found = []
    for _ in range(10):
        runtime.tick()
        det_results = runtime.detector.evaluate(
            "EDGE-002", runtime.engine.devices["EDGE-002"].last_metrics, runtime.engine.tick
        )
        found.extend(det_results)
        if found:
            break
    # The runtime already evaluated these ticks; direct evaluate above is a
    # second pass — either way a temperature anomaly must surface.
    incidents, total = runtime.repo.list_incidents(device_id="EDGE-002")
    assert total >= 1 or found
