"""Analytics aggregations over incidents, telemetry and fleet state."""
from __future__ import annotations

import time
from typing import Any

from app.db.repository import Repository
from app.detection.scoring import DetectionResult  # noqa: F401  (typing aid)


class AnalyticsService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def overview(self) -> dict[str, Any]:
        now = time.time()
        day_ago = now - 24 * 3600
        incidents = self.repo.incidents_since(day_ago)
        devices = self.repo.list_devices()

        total = len(incidents)
        resolved = [i for i in incidents if i.status == "RESOLVED"]
        escalated = [i for i in incidents if i.status == "ESCALATED"]
        false_pos = [i for i in incidents if i.status == "FALSE_POSITIVE"]
        open_incidents = [i for i in incidents if i.status in {"OPEN", "INVESTIGATING", "MITIGATING", "MONITORING"}]

        resolution_times = [i.resolved_at - i.created_at for i in resolved if i.resolved_at]
        mttr = sum(resolution_times) / len(resolution_times) if resolution_times else 0.0

        actionable = total - len(false_pos)
        auto_rate = (len(resolved) / actionable * 100.0) if actionable else 100.0

        by_device: dict[str, int] = {}
        by_metric: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_action: dict[str, int] = {}
        histogram: dict[str, int] = {}
        for i in incidents:
            by_device[i.device_id] = by_device.get(i.device_id, 0) + 1
            by_metric[i.metric] = by_metric.get(i.metric, 0) + 1
            by_severity[i.severity] = by_severity.get(i.severity, 0) + 1
            by_status[i.status] = by_status.get(i.status, 0) + 1
            if i.action_taken:
                by_action[i.action_taken] = by_action.get(i.action_taken, 0) + 1
            bucket = time.strftime("%H:00", time.localtime(i.created_at))
            histogram[bucket] = histogram.get(bucket, 0) + 1

        healths = [d.health_score for d in devices]
        online = len([d for d in devices if d.status in {"ONLINE", "WARNING"}])

        return {
            "telemetry_points": self.repo.count_telemetry(),
            "anomalies_detected": total,
            "incidents_total": total,
            "incidents_open": len(open_incidents),
            "incidents_resolved": len(resolved),
            "incidents_escalated": len(escalated),
            "false_positives": len(false_pos),
            "auto_resolution_rate": round(auto_rate, 1),
            "mean_time_to_detect_s": 3.0,     # persistence × tick — constant by design
            "mean_time_to_resolve_s": round(mttr, 1),
            "fleet_health_avg": round(sum(healths) / len(healths), 1) if healths else 100.0,
            "devices_online": online,
            "devices_total": len(devices),
            "most_problematic_device": max(by_device, key=by_device.get) if by_device else "—",
            "most_common_anomaly": max(by_metric, key=by_metric.get) if by_metric else "—",
            "most_common_remediation": max(by_action, key=by_action.get) if by_action else "—",
            "severity_distribution": by_severity,
            "status_distribution": by_status,
            "metric_distribution": by_metric,
            "action_distribution": by_action,
            "incident_histogram": [{"bucket": k, "count": v} for k, v in sorted(histogram.items())],
            "device_health": [
                {"device_id": d.id, "health": d.health_score, "status": d.status} for d in devices
            ],
        }
