"""EWMA drift detector — fast/slow moving-average divergence.

A single EWMA either chases a slow drift (never alarms) or alarms on noise.
The classic fix is two time constants: the fast average tracks recent values,
the slow average represents the established baseline. Sustained drift makes
them diverge — this catches ramps that rolling statistics absorb once the
window saturates (memory leaks, thermal creep, battery drain).

The slow baseline is soft-gated during large divergences, so it remains a
trustworthy pre-incident reference — which is also what recovery verification
uses (the rolling window is contaminated by the incident itself).
"""
from __future__ import annotations


class EWMADetector:
    def __init__(
        self,
        alpha_fast: float = 0.35,
        alpha_slow: float = 0.05,
        min_samples: int = 25,
        gate_threshold: float = 2.5,
        noise_floor: float = 1.0,
    ) -> None:
        self.alpha_fast = alpha_fast
        self.alpha_slow = alpha_slow
        self.min_samples = min_samples
        self.gate_threshold = gate_threshold
        self.noise_floor = max(noise_floor, 1e-6)
        self.fast: float | None = None
        self.slow: float | None = None
        self.slow_var: float = 0.0
        self.count = 0

    def update(self, value: float) -> tuple[float, float]:
        """Returns (drift_z, slow_mean). drift_z = |fast - slow| / sigma."""
        if self.fast is None:
            self.fast = self.slow = value
            self.count = 1
            return 0.0, value
        self.count += 1
        # Fast average always adapts.
        self.fast += self.alpha_fast * (value - self.fast)
        deviation = abs(self.fast - self.slow)
        # Sigma floor: before the variance estimate stabilizes (or on naturally
        # quiet metrics), don't let tiny denominators manufacture drift alarms.
        std = max(self.slow_var ** 0.5, 0.75 * self.noise_floor)
        drift_z = deviation / std if self.count >= self.min_samples else 0.0
        # Slow baseline adapts unless the divergence is extreme (soft gate), so a
        # real sustained fault keeps scoring instead of being absorbed — but a
        # permanent legitimate level shift is eventually relearned.
        if drift_z < self.gate_threshold * 3.0:
            self.slow += self.alpha_slow * (value - self.slow)
        # Residual variance is measured against the FAST mean (removing drift)
        # and ONLY in the normal regime — during an anomaly the estimate freezes
        # at its healthy level. Letting it track the incident would inflate
        # sigma, reopen the gate, and let the baseline chase the fault.
        if drift_z < self.gate_threshold:
            clamp = 8.0 * self.noise_floor
            err = max(-clamp, min(clamp, value - self.fast))
            self.slow_var = (1 - self.alpha_slow) * (self.slow_var + self.alpha_slow * err * err)
        return drift_z, self.slow

    # ------------------------------------------------------- recovery reference
    @property
    def baseline(self) -> float:
        return self.slow if self.slow is not None else 0.0

    @property
    def residual_std(self) -> float:
        return max(self.slow_var ** 0.5, 0.75 * self.noise_floor)
