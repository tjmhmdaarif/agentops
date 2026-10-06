"""Hybrid anomaly detection engine.

Per (device, metric): rolling z-score + EWMA + rate-of-change.
Per device: Isolation Forest over the full 7-metric vector.
Fuses sub-scores, requires anomaly persistence, and emits DetectionResults.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from app.core.config import Settings
from app.detection.ewma import EWMADetector
from app.detection.isolation_forest import DeviceIsolationForest
from app.detection.rate import RateOfChangeDetector
from app.detection.scoring import (
    DetectionResult,
    DetectorSignals,
    build_explanation,
    fuse,
    severity_for,
)
from app.detection.zscore import RollingZScore
from app.simulation.telemetry import METRIC_NAMES, METRICS


@dataclass
class MetricState:
    zscore: RollingZScore
    ewma: EWMADetector
    rate: RateOfChangeDetector
    recent_rel: deque[float] = field(default_factory=lambda: deque(maxlen=3))
    consecutive_anomalies: int = 0
    last_score: float = 0.0
    last_value: float = 0.0


class HybridDetector:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._metric_state: dict[tuple[str, str], MetricState] = {}
        self._iforest: dict[str, DeviceIsolationForest] = {}
        self._if_score_cache: dict[str, float] = {}
        self.baselines: dict[tuple[str, str], float] = {}

    # IsolationForest decision_function has ~20ms of sklearn/joblib overhead per
    # call, so each device is scored every 3rd tick (staggered) with caching.
    IF_SCORE_EVERY = 3

    @staticmethod
    def _device_slot(device_id: str) -> int:
        try:
            return int(device_id.rsplit("-", 1)[1])
        except (IndexError, ValueError):
            return 0

    def _state(self, device_id: str, metric: str) -> MetricState:
        key = (device_id, metric)
        if key not in self._metric_state:
            self._metric_state[key] = MetricState(
                zscore=RollingZScore(window=self.settings.rolling_window),
                ewma=EWMADetector(
                    gate_threshold=self.settings.ewma_threshold,
                    noise_floor=METRICS[metric].noise,
                ),
                rate=RateOfChangeDetector(),
            )
        return self._metric_state[key]

    def _if(self, device_id: str) -> DeviceIsolationForest:
        if device_id not in self._iforest:
            slot = self._device_slot(device_id)
            # Stagger first-train and retrain cadence per device so the fleet
            # never retrains all models on the same tick.
            self._iforest[device_id] = DeviceIsolationForest(
                min_samples=self.settings.iforest_min_samples + slot * 3,
                retrain_every=self.settings.iforest_retrain_every + slot * 11,
                seed=self.settings.random_seed,
            )
        return self._iforest[device_id]

    def reset(self) -> None:
        self._metric_state.clear()
        self._iforest.clear()
        self.baselines.clear()

    # ------------------------------------------------------------------ main
    def evaluate(self, device_id: str, metrics: dict[str, float], tick: int = 0) -> list[DetectionResult]:
        """Process one tick of telemetry for a device; return anomalies that
        passed fusion *and* persistence requirements."""
        forest = self._if(device_id)
        forest.observe(metrics)
        forest.maybe_train()
        iforest_active = forest.is_trained
        if iforest_active:
            # Fast path is cheap enough to score every tick; the sklearn fallback
            # path is staggered across devices to amortize joblib overhead.
            if forest.fast_ok or tick % self.IF_SCORE_EVERY == self._device_slot(device_id) % self.IF_SCORE_EVERY:
                self._if_score_cache[device_id] = forest.score(metrics)
            if_score = self._if_score_cache.get(device_id, 0.0)
        else:
            if_score = 0.0

        results: list[DetectionResult] = []
        for metric in METRIC_NAMES:
            value = float(metrics[metric])
            state = self._state(device_id, metric)
            state.last_value = value
            z, mean, _std = state.zscore.update(value)
            ewma_z, _ewma_mean = state.ewma.update(value)
            delta, rel_now = state.rate.update(value)
            # Relative change is meaningless on small-baseline metrics: a step
            # only counts toward rate-of-change if it also moves ≥4σ of noise.
            state.recent_rel.append(rel_now if abs(delta) >= 4.0 * METRICS[metric].noise else 0.0)
            rel = max(state.recent_rel) if state.recent_rel else 0.0
            self.baselines[(device_id, metric)] = mean

            # Stuck-sensor detection: a real sensor never reports *exactly* the
            # same value for a long stretch — zero variance is itself an anomaly.
            extra_fired: list[str] = []
            window = state.zscore.values
            if len(window) >= 12:
                tail = list(window)[-12:]
                if max(tail) - min(tail) < 1e-9:
                    extra_fired.append("zero_variance")

            signals = DetectorSignals(zscore=z, ewma=ewma_z, rate=rel, iforest=if_score)
            score, fired = fuse(
                signals,
                self.settings.zscore_threshold,
                self.settings.ewma_threshold,
                self.settings.roc_threshold,
                extra_fired=extra_fired,
                iforest_active=iforest_active,
                # MAD estimates are unstable on a partially-filled window; the
                # dominant-detector override waits for statistical maturity.
                allow_override=len(state.zscore.values) >= 25,
            )
            # Rate alone caps at 0.23 fused score (excluded from the dominant
            # override), so its 3-tick memory can never satisfy persistence by
            # itself — z-score or EWMA must corroborate a real level shift.
            if "zero_variance" in extra_fired:
                # A frozen sensor is definitively anomalous — floor the score.
                score = max(score, 0.72)
            state.last_score = score

            if score >= self.settings.anomaly_threshold and fired:
                state.consecutive_anomalies += 1
            else:
                state.consecutive_anomalies = 0

            if state.consecutive_anomalies >= self.settings.anomaly_persistence:
                results.append(DetectionResult(
                    device_id=device_id,
                    metric=metric,
                    is_anomaly=True,
                    score=round(score, 4),
                    severity=severity_for(score),
                    detectors=fired,
                    explanation=build_explanation(metric, value, mean, signals, fired),
                    value=value,
                    baseline=round(mean, 3),
                    signals=signals,
                ))
        return results

    def current_score(self, device_id: str, metric: str) -> float:
        """Latest fused score for a device/metric — used by health scoring."""
        state = self._metric_state.get((device_id, metric))
        return state.last_score if state else 0.0

    def recovery_check(self, device_id: str, metric: str) -> tuple[bool, float, float, float]:
        """Baseline-referenced recovery test.

        Returns (healthy, deviation, baseline, limit). Compares the CURRENT value
        against the gated EWMA slow baseline — which the incident could not
        contaminate — instead of the rolling window (which the incident did
        contaminate, making true recovery look anomalous for ~40 ticks).
        """
        state = self._metric_state.get((device_id, metric))
        if state is None or state.ewma.slow is None:
            return False, 0.0, 0.0, 1.0
        baseline = state.ewma.baseline
        limit = max(4.0 * state.ewma.residual_std, 0.08 * abs(baseline))
        deviation = abs(state.last_value - baseline)
        return deviation <= limit, deviation, baseline, limit

    def normal_range(self, device_id: str, metric: str) -> tuple[float, float]:
        """(baseline - 3σ, baseline + 3σ) approximation for chart bands."""
        state = self._metric_state.get((device_id, metric))
        baseline = self.baselines.get((device_id, metric), 0.0)
        sigma = float(METRICS[metric].noise) * 2.0
        if state and len(state.zscore.values) >= state.zscore.min_samples:
            import numpy as np
            arr = list(state.zscore.values)
            sigma = max(float(np.std(arr)), 1e-6)
        return baseline - 3 * sigma, baseline + 3 * sigma
