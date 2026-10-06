"""Incident manager — creation, dedup/grouping, cooldowns, lifecycle transitions."""
from __future__ import annotations

import time
from typing import Callable, Optional

from app.core.config import Settings
from app.core.events import EventBus
from app.core.logging import get_logger
from app.db.models import Incident
from app.db.repository import Repository
from app.detection.scoring import DetectionResult
from app.incidents import lifecycle

log = get_logger("incidents")


def serialize(incident: Incident) -> dict:
    return {
        "id": incident.id,
        "device_id": incident.device_id,
        "metric": incident.metric,
        "severity": incident.severity,
        "status": incident.status,
        "detector": incident.detector,
        "anomaly_score": incident.anomaly_score,
        "reason": incident.reason,
        "created_at": incident.created_at,
        "updated_at": incident.updated_at,
        "resolved_at": incident.resolved_at,
        "action_taken": incident.action_taken,
        "resolution_notes": incident.resolution_notes,
    }


class IncidentManager:
    def __init__(self, repo: Repository, bus: EventBus, settings: Settings) -> None:
        self.repo = repo
        self.bus = bus
        self.settings = settings
        self._cooldowns: dict[tuple[str, str], float] = {}
        self.on_incident_created: Optional[Callable[[int], None]] = None  # wired to the agent runtime

    # -------------------------------------------------------------- ingestion
    def handle_detections(self, detections: list[DetectionResult]) -> list[Incident]:
        incidents: list[Incident] = []
        for det in detections:
            incident = self._ingest(det)
            if incident is not None:
                incidents.append(incident)
        return incidents

    def _ingest(self, det: DetectionResult) -> Optional[Incident]:
        now = time.time()
        key = (det.device_id, det.metric)

        # 1) Group into an existing active incident for the same device+metric.
        existing = self.repo.find_active_incident(det.device_id, det.metric)
        if existing is not None:
            if det.score > existing.anomaly_score:
                updated = self.repo.update_incident(existing.id, anomaly_score=det.score)
                if updated:
                    self.bus.publish("incident_updated", {"incident": serialize(updated)})
            return None

        # 1b) Group correlated failures: another metric on the same device already
        # has an active incident → enrich it instead of spawning parallel incidents.
        sibling = self.repo.find_active_incident_for_device(det.device_id, within_seconds=120.0)
        if sibling is not None:
            note = f"Correlated anomaly also detected on {det.metric} (score {det.score:.2f})."
            if det.metric not in sibling.reason:
                updated = self.repo.update_incident(
                    sibling.id,
                    reason=sibling.reason + " " + note,
                    anomaly_score=max(sibling.anomaly_score, det.score),
                )
                if updated:
                    self.bus.publish("incident_updated", {"incident": serialize(updated)})
            return None

        # 2) Cooldown window after a recently closed incident on the same key.
        last = self._cooldowns.get(key, 0.0)
        if now - last < self.settings.incident_cooldown_seconds:
            log.info("incident_suppressed reason=cooldown device=%s metric=%s", det.device_id, det.metric)
            return None

        incident = self.repo.create_incident(Incident(
            device_id=det.device_id,
            metric=det.metric,
            severity=det.severity,
            status=lifecycle.OPEN,
            detector="+".join(det.detectors),
            anomaly_score=det.score,
            reason=det.explanation,
        ))
        self._cooldowns[key] = now
        log.info(
            "incident_created id=%s device=%s metric=%s severity=%s score=%.2f",
            incident.id, incident.device_id, incident.metric, incident.severity, incident.anomaly_score,
        )
        self.bus.publish("incident_created", {"incident": serialize(incident)})
        if self.on_incident_created:
            self.on_incident_created(incident.id)
        return incident

    # ------------------------------------------------------------- offline path
    def ensure_offline_incident(self, device_id: str) -> Optional[Incident]:
        existing = self.repo.find_active_incident(device_id, "availability")
        if existing is not None:
            return None
        det = DetectionResult(
            device_id=device_id,
            metric="availability",
            is_anomaly=True,
            score=0.88,
            severity="high",
            detectors=["watchdog"],
            explanation=f"{device_id} stopped emitting telemetry — no samples received for multiple consecutive intervals.",
            value=0.0,
            baseline=1.0,
        )
        return self._ingest(det)

    # -------------------------------------------------------------- transitions
    def transition(self, incident_id: int, target: str, **fields) -> Optional[Incident]:
        incident = self.repo.get_incident(incident_id)
        if incident is None:
            return None
        if not lifecycle.can_transition(incident.status, target):
            log.warning("invalid_transition id=%s %s->%s", incident_id, incident.status, target)
            return incident
        updated = self.repo.update_incident(incident_id, status=target, **fields)
        if updated:
            self.bus.publish("incident_updated", {"incident": serialize(updated)})
        return updated

    def resolve(self, incident_id: int, action: str, notes: str) -> Optional[Incident]:
        incident = self.transition(
            incident_id, lifecycle.RESOLVED,
            resolved_at=time.time(), action_taken=action, resolution_notes=notes,
        )
        if incident:
            self._cooldowns[(incident.device_id, incident.metric)] = time.time()
            self.bus.publish("incident_resolved", {"incident": serialize(incident)})
            log.info("incident_resolved id=%s action=%s", incident_id, action)
        return incident

    def escalate(self, incident_id: int, notes: str) -> Optional[Incident]:
        incident = self.transition(incident_id, lifecycle.ESCALATED, resolution_notes=notes)
        if incident:
            self._cooldowns[(incident.device_id, incident.metric)] = time.time()
            log.info("incident_escalated id=%s", incident_id)
        return incident

    def mark_false_positive(self, incident_id: int, notes: str) -> Optional[Incident]:
        incident = self.transition(incident_id, lifecycle.FALSE_POSITIVE, resolution_notes=notes)
        if incident:
            self._cooldowns[(incident.device_id, incident.metric)] = time.time()
            log.info("incident_false_positive id=%s", incident_id)
        return incident

    def clear_cooldowns(self) -> None:
        self._cooldowns.clear()
