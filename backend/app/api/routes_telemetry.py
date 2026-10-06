"""Telemetry endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/api", tags=["telemetry"])


@router.get("/devices/{device_id}/telemetry")
def device_telemetry(
    device_id: str,
    request: Request,
    metric: str = "temperature",
    minutes: int = Query(default=15, ge=1, le=360),
) -> dict:
    series = request.app.state.runtime.telemetry.series(device_id, metric, minutes)
    if series is None:
        raise HTTPException(status_code=404, detail={"error": "unknown_metric", "metric": metric})
    return series


@router.get("/telemetry/series")
def multi_series(
    request: Request,
    devices: str = Query(..., description="comma-separated device ids"),
    metric: str = "temperature",
    minutes: int = Query(default=15, ge=1, le=360),
) -> dict:
    runtime = request.app.state.runtime
    out = []
    for device_id in [d.strip() for d in devices.split(",") if d.strip()][:6]:
        series = runtime.telemetry.series(device_id, metric, minutes)
        if series is not None:
            out.append(series)
    if not out:
        raise HTTPException(status_code=404, detail={"error": "no_series"})
    return {"metric": metric, "minutes": minutes, "series": out}
