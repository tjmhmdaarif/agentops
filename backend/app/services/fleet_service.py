"""Fleet service — health scoring, device serialization."""
from __future__ import annotations

import time
from typing import Any

from app.db.models import Device
from app.db.repository import Repository
from app.detection.detector import HybridDetector
from app.simulation.engine import SimulationEngine
from app.simulation.telemetry import METRIC_NAMES


def compute_health(
    device_id: str,
    detector: HybridDetector,
    open_incident_count: int,
    is_offline: bool,
    recent_restart: bool,
) -> float:
    """0..100 composite health. Continuous, explainable components."""
    score = 100.0
    anomaly_penalty = 0.0
    for metric in METRIC_NAMES:
        s = detector.current_score(device_id, metric)
        anomaly_penalty += max(0.0, s - 0.30) * 22.0
    score -= min(40.0, anomaly_penalty)
    score -= min(36.0, open_incident_count * 12.0)
    if is_offline:
        score -= 45.0
    if recent_restart:
        score -= 5.0
    return round(max(0.0, min(100.0, score)), 1)


def status_for(health: float, is_offline: bool, is_recovering: bool) -> str:
    if is_offline:
        return "OFFLINE"
    if is_recovering:
        return "RECOVERING"
    if health >= 85:
        return "ONLINE"
    if health >= 60:
        return "WARNING"
    return "DEGRADED"


def serialize_device(device: Device, latest_metrics: dict[str, float], active_incidents: int) -> dict[str, Any]:
    return {
        "id": device.id,
        "name": device.name,
        "device_type": device.device_type,
        "location": device.location,
        "status": device.status,
        "health_score": device.health_score,
        "last_seen": device.last_seen,
        "created_at": device.created_at,
        "firmware_version": device.firmware_version,
        "uptime": device.uptime,
        "restart_count": device.restart_count,
        "latest_metrics": latest_metrics,
        "active_incidents": active_incidents,
    }


class FleetService:
    def __init__(self, repo: Repository, engine: SimulationEngine, detector: HybridDetector) -> None:
        self.repo = repo
        self.engine = engine
        self.detector = detector

    def list_devices(self) -> list[dict[str, Any]]:
        devices = self.repo.list_devices()
        open_by_device: dict[str, int] = {}
        for inc in self.repo.open_incidents():
            open_by_device[inc.device_id] = open_by_device.get(inc.device_id, 0) + 1
        out = []
        for d in devices:
            sim = self.engine.devices.get(d.id)
            latest = dict(sim.last_metrics) if sim else {}
            out.append(serialize_device(d, latest, open_by_device.get(d.id, 0)))
        return out

    def get_device(self, device_id: str) -> dict[str, Any] | None:
        device = self.repo.get_device(device_id)
        if device is None:
            return None
        sim = self.engine.devices.get(device_id)
        latest = dict(sim.last_metrics) if sim else {}
        open_count = len([i for i in self.repo.open_incidents() if i.device_id == device_id])
        return serialize_device(device, latest, open_count)

    def sync_from_simulation(self) -> tuple[list[dict[str, Any]], dict[str, tuple[float, str]]]:
        """Write current sim state (health, status, uptime, last_seen) into the DB.

        Returns (status_changes, health_map) where health_map is
        device_id → (health_score, status) — used for telemetry events.
        """
        now = time.time()
        open_by_device = self.repo.open_incident_counts()
        restarts = self.repo.last_restart_times()
        existing = {d.id: d for d in self.repo.list_devices()}

        changed: list[dict[str, Any]] = []
        health_map: dict[str, tuple[float, str]] = {}
        updates: dict[str, dict[str, Any]] = {}
        for device_id, sim in self.engine.devices.items():
            current = existing.get(device_id)
            if current is None:
                continue
            recent_restart = device_id in restarts and (now - restarts[device_id]) < 60
            health = compute_health(
                device_id, self.detector,
                open_incident_count=open_by_device.get(device_id, 0),
                is_offline=sim.is_offline,
                recent_restart=recent_restart,
            )
            new_status = status_for(health, sim.is_offline, sim.is_recovering)
            health_map[device_id] = (health, new_status)
            updates[device_id] = {
                "health_score": health,
                "status": new_status,
                "last_seen": sim.last_seen,
                "uptime": self.engine.uptime_for(device_id, now),
                "restart_count": sim.restart_count,
            }
            if new_status != current.status or abs(health - current.health_score) >= 5:
                changed.append({
                    "device_id": device_id, "status": new_status,
                    "previous_status": current.status, "health_score": health,
                })
        self.repo.update_devices_bulk(updates)
        return changed, health_map
