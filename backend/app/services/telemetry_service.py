"""Telemetry query service."""
from __future__ import annotations

import time
from typing import Any, Optional

from app.db.repository import Repository
from app.detection.detector import HybridDetector
from app.simulation.telemetry import METRICS


class TelemetryService:
    def __init__(self, repo: Repository, detector: HybridDetector) -> None:
        self.repo = repo
        self.detector = detector

    def series(
        self, device_id: str, metric: str, minutes: int = 15, max_points: int = 400
    ) -> Optional[dict[str, Any]]:
        if metric not in METRICS:
            return None
        now = time.time()
        rows = self.repo.telemetry_range(device_id, metric, now - minutes * 60, now, max_points)
        baseline = self.detector.baselines.get((device_id, metric), 0.0)
        low, high = self.detector.normal_range(device_id, metric)
        return {
            "device_id": device_id,
            "metric": metric,
            "unit": METRICS[metric].unit,
            "baseline": round(float(baseline), 3),
            "normal_low": round(low, 3),
            "normal_high": round(high, 3),
            "points": [{"ts": r.timestamp, "value": r.value} for r in rows],
        }

    def latest(self, device_id: str) -> dict[str, float]:
        out: dict[str, float] = {}
        for metric in METRICS:
            rows = self.repo.recent_telemetry(device_id, metric, limit=1)
            if rows:
                out[metric] = rows[-1].value
        return out
