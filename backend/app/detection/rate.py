"""Rate-of-change detector — catches sudden jumps between consecutive samples."""
from __future__ import annotations


class RateOfChangeDetector:
    def __init__(self) -> None:
        self.previous: float | None = None

    def update(self, value: float) -> tuple[float, float]:
        """Returns (delta, relative_change) for this step only. The caller
        (HybridDetector) owns noise-floor gating and short-window memory."""
        if self.previous is None:
            self.previous = value
            return 0.0, 0.0
        delta = value - self.previous
        scale = max(abs(self.previous), 1.0)
        relative = abs(delta) / scale
        self.previous = value
        return delta, relative
