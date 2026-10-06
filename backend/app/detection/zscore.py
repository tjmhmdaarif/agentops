"""Rolling robust Z-score detector (median/MAD based).

Median + MAD are resistant to outliers, so an ongoing anomaly does not
contaminate its own baseline — persistence counting keeps working.
"""
from __future__ import annotations

from collections import deque

import numpy as np


class RollingZScore:
    """Maintains a rolling window and computes robust |z| for the newest value."""

    def __init__(self, window: int = 40, min_samples: int = 15) -> None:
        self.window = window
        self.min_samples = min_samples
        self.values: deque[float] = deque(maxlen=window)

    def update(self, value: float) -> tuple[float, float, float]:
        """Returns (robust_z, baseline_median, robust_sigma)."""
        self.values.append(value)
        arr = np.asarray(self.values, dtype=float)
        history = arr[:-1] if len(arr) > 1 else arr
        median = float(np.median(history))
        mad = float(np.median(np.abs(history - median)))
        sigma = 1.4826 * mad
        if len(self.values) < self.min_samples:
            return 0.0, median, sigma
        if sigma < 1e-9:
            # Perfectly flat history: any deviation is notable.
            return (0.0 if abs(value - median) < 1e-9 else 6.0), median, 0.0
        z = abs(value - median) / sigma
        return z, median, sigma
