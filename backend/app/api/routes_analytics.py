"""Analytics endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.db.schemas import AnalyticsOverview

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOverview)
def overview(request: Request) -> dict:
    return request.app.state.runtime.analytics.overview()


@router.get("/anomalies")
def recent_anomalies(request: Request, limit: int = 50) -> dict:
    """Recent anomaly_detected events from the bus history."""
    events = [
        e for e in request.app.state.runtime.bus.recent(500)
        if e["type"] in {"anomaly_detected", "failure_injected"}
    ]
    return {"items": events[-limit:]}
