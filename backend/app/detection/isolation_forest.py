"""Multivariate Isolation Forest detector (per device).

Trains on recent healthy 7-metric vectors and scores unusual *combinations*.
It participates in the main fusion pipeline alongside the univariate detectors.
"""
from __future__ import annotations

import math

import numpy as np
from sklearn.ensemble import IsolationForest

from app.core.logging import get_logger
from app.simulation.telemetry import METRIC_NAMES

log = get_logger("detection.iforest")


class DeviceIsolationForest:
    def __init__(self, min_samples: int = 60, retrain_every: int = 120, seed: int | None = 42) -> None:
        self.min_samples = min_samples
        self.retrain_every = retrain_every
        self.seed = seed
        self.buffer: list[list[float]] = []
        self.model: IsolationForest | None = None
        self.samples_since_train = 0
        self.trained_at_size = 0
        self._fast: tuple | None = None   # validated manual scoring path
        self._calib: tuple[float, float] = (0.0, 0.05)  # (mean, std) of raw scores on training data

    @staticmethod
    def vectorize(metrics: dict[str, float]) -> list[float]:
        return [float(metrics[m]) for m in METRIC_NAMES]

    def observe(self, metrics: dict[str, float]) -> None:
        self.buffer.append(self.vectorize(metrics))
        if len(self.buffer) > 2000:                # keep training data recent
            self.buffer = self.buffer[-1500:]
        self.samples_since_train += 1

    @property
    def is_trained(self) -> bool:
        return self.model is not None

    def maybe_train(self) -> bool:
        if len(self.buffer) < self.min_samples:
            return False
        if self.model is not None and self.samples_since_train < self.retrain_every:
            return False
        x = np.asarray(self.buffer, dtype=float)
        self.model = IsolationForest(
            n_estimators=60, contamination=0.04,
            random_state=self.seed, n_jobs=1,
        )
        self.model.fit(x)
        self.samples_since_train = 0
        self.trained_at_size = len(self.buffer)
        self._try_build_fast_path()
        # Calibrate the score mapping on the training data itself: IF's raw
        # decision function hovers near 0 for inliers (offset_ sits at the
        # contamination percentile), so a fixed mapping can't separate regimes.
        try:
            raw_train = self.model.decision_function(np.asarray(self.buffer, dtype=float))
            self._calib = (float(np.mean(raw_train)), max(float(np.std(raw_train)), 1e-6))
        except Exception:
            self._calib = (0.0, 0.05)
        log.debug("iforest_trained samples=%d fast_path=%s", len(self.buffer), self.fast_ok)
        return True

    @property
    def fast_ok(self) -> bool:
        return self._fast is not None

    def _try_build_fast_path(self) -> None:
        """Manual average-path-length scoring (~60x faster than sklearn's
        joblib-dispatched decision_function). Mirrors sklearn 1.9 internals:
        decision_function = -2^(-depth/denominator) - offset_, where depth sums
        precomputed per-node path lengths. Validated against sklearn's own
        output on real samples; disabled automatically on any mismatch."""
        self._fast = None
        try:
            from sklearn.ensemble._iforest import _average_path_length  # type: ignore

            model = self.model
            assert model is not None
            trees = [
                (est, np.asarray(feats), dpl, apl)
                for est, feats, dpl, apl in zip(
                    model.estimators_,
                    model.estimators_features_,
                    model._decision_path_lengths,
                    model._average_path_length_per_tree,
                )
            ]
            denom = float(len(trees)) * float(_average_path_length([model._max_samples])[0])
            if not np.isfinite(denom) or denom <= 0:
                return
            self._fast = (trees, denom, float(model.offset_))
            probe = np.asarray(self.buffer[:3], dtype=float)
            reference = model.decision_function(probe)
            manual = np.array([self._fast_score_row(row) for row in probe])
            if not np.allclose(reference, manual, atol=1e-6):
                self._fast = None
        except Exception:
            self._fast = None

    def _fast_score_row(self, row: np.ndarray) -> float:
        trees, denom, offset = self._fast
        x = row.reshape(1, -1).astype(np.float32)
        depth = 0.0
        for est, feats, decision_path_lengths, avg_path_lengths in trees:
            leaf = int(est.apply(x[:, feats], check_input=False)[0])
            depth += float(decision_path_lengths[leaf]) + float(avg_path_lengths[leaf]) - 1.0
        return float(-(2.0 ** (-depth / denom)) - offset)

    def score(self, metrics: dict[str, float]) -> float:
        """0..1 multivariate anomaly score. 0 until the model is trained."""
        if self.model is None:
            return 0.0
        if self._fast is not None:
            raw = self._fast_score_row(np.asarray(self.vectorize(metrics), dtype=float))
        else:
            x = np.asarray([self.vectorize(metrics)], dtype=float)
            # decision_function: higher = more normal. Map to (0,1) anomaly score.
            raw = float(self.model.decision_function(x)[0])
        # Normalize against the training distribution: inliers land ~0.1,
        # 2σ outliers ~0.5, 4σ outliers ~0.88.
        mean, std = self._calib
        z = (mean - raw) / std
        return float(1.0 / (1.0 + math.exp(2.0 - z)))
