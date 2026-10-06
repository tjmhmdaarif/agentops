"""Device endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.db.schemas import DeviceActionOut, DeviceOut, IncidentOut

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.get("", response_model=list[DeviceOut])
def list_devices(request: Request) -> list[dict]:
    return request.app.state.runtime.fleet.list_devices()


@router.get("/{device_id}", response_model=DeviceOut)
def get_device(device_id: str, request: Request) -> dict:
    device = request.app.state.runtime.fleet.get_device(device_id)
    if device is None:
        raise HTTPException(status_code=404, detail={"error": "device_not_found", "device_id": device_id})
    return device


@router.get("/{device_id}/incidents", response_model=list[IncidentOut])
def device_incidents(device_id: str, request: Request, limit: int = 20) -> list[dict]:
    return request.app.state.runtime.incidents.for_device(device_id, limit)


@router.get("/{device_id}/actions", response_model=list[DeviceActionOut])
def device_actions(device_id: str, request: Request, limit: int = 20) -> list[dict]:
    actions = request.app.state.runtime.repo.actions_for_device(device_id, limit)
    return [
        {
            "id": a.id, "device_id": a.device_id, "incident_id": a.incident_id,
            "action": a.action, "status": a.status, "reason": a.reason,
            "started_at": a.started_at, "completed_at": a.completed_at, "result": a.result,
        }
        for a in actions
    ]


@router.post("/{device_id}/actions/restart")
def manual_restart(device_id: str, request: Request) -> dict:
    runtime = request.app.state.runtime
    if device_id not in runtime.engine.devices:
        raise HTTPException(status_code=404, detail={"error": "device_not_found", "device_id": device_id})
    result = runtime.registry.call("restart_device", runtime.tool_ctx, {
        "device_id": device_id, "reason": "manual operator action",
    })
    return result


@router.get("/{device_id}/prediction")
def device_prediction(device_id: str, request: Request) -> dict:
    """EXPERIMENTAL — gated behind the `predictive_health` feature flag.

    Heuristic failure-risk estimate (0..1) from health, anomaly pressure,
    incident recency and restart history. This is the reference pattern for
    shipping experimental features safely: flag off → the route doesn't exist.
    """
    settings = request.app.state.settings
    if not settings.feature_flags.get("predictive_health", False):
        raise HTTPException(status_code=404, detail={"error": "feature_disabled", "flag": "predictive_health"})
    runtime = request.app.state.runtime
    device = runtime.repo.get_device(device_id)
    if device is None:
        raise HTTPException(status_code=404, detail={"error": "device_not_found", "device_id": device_id})
    open_incidents = runtime.repo.open_incident_counts().get(device_id, 0)
    anomaly_pressure = max(
        (runtime.detector.current_score(device_id, m) for m in device.latest_metrics),
        default=0.0,
    ) if device.latest_metrics else 0.0
    risk = (
        (1.0 - device.health_score / 100.0) * 0.45
        + min(1.0, open_incidents / 3.0) * 0.25
        + min(1.0, device.restart_count / 10.0) * 0.10
        + anomaly_pressure * 0.20
    )
    risk = round(max(0.0, min(1.0, risk)), 3)
    level = "low" if risk < 0.3 else "moderate" if risk < 0.6 else "high"
    return {
        "device_id": device_id,
        "failure_risk": risk,
        "level": level,
        "experimental": True,
        "factors": {
            "health_score": device.health_score,
            "open_incidents": open_incidents,
            "restart_count": device.restart_count,
            "max_anomaly_score": round(anomaly_pressure, 3),
        },
    }
