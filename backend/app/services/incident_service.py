"""Incident query service."""
from __future__ import annotations

from typing import Any, Optional

from app.db.repository import Repository
from app.incidents.manager import serialize


class IncidentService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def list(self, status: Optional[str], device_id: Optional[str],
             limit: int, offset: int) -> dict[str, Any]:
        items, total = self.repo.list_incidents(status=status, device_id=device_id,
                                                limit=limit, offset=offset)
        return {"items": [serialize(i) for i in items], "total": total,
                "limit": limit, "offset": offset}

    def get(self, incident_id: int) -> Optional[dict[str, Any]]:
        incident = self.repo.get_incident(incident_id)
        return serialize(incident) if incident else None

    def timeline(self, incident_id: int) -> Optional[list[dict[str, Any]]]:
        if self.repo.get_incident(incident_id) is None:
            return None
        return [
            {
                "id": e.id,
                "incident_id": e.incident_id,
                "timestamp": e.timestamp,
                "event_type": e.event_type,
                "message": e.message,
                "tool_name": e.tool_name,
                "tool_input": e.tool_input,
                "tool_output": e.tool_output,
                "duration_ms": e.duration_ms,
            }
            for e in self.repo.incident_timeline(incident_id)
        ]

    def for_device(self, device_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return [serialize(i) for i in self.repo.recent_incidents_for_device(device_id, limit)]
