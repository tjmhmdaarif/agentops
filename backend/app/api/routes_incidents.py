"""Incident endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from app.db.schemas import AgentEventOut, IncidentListOut, IncidentOut

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("", response_model=IncidentListOut)
def list_incidents(
    request: Request,
    status: Optional[str] = None,
    device_id: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    return request.app.state.runtime.incidents.list(status, device_id, limit, offset)


@router.get("/{incident_id}", response_model=IncidentOut)
def get_incident(incident_id: int, request: Request) -> dict:
    incident = request.app.state.runtime.incidents.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail={"error": "incident_not_found", "id": incident_id})
    return incident


@router.get("/{incident_id}/timeline", response_model=list[AgentEventOut])
def incident_timeline(incident_id: int, request: Request) -> list[dict]:
    timeline = request.app.state.runtime.incidents.timeline(incident_id)
    if timeline is None:
        raise HTTPException(status_code=404, detail={"error": "incident_not_found", "id": incident_id})
    return timeline
