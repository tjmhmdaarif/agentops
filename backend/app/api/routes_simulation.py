"""Simulation control endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.db.schemas import (
    AnomalyRateRequest,
    DeviceCountRequest,
    InjectRequest,
    SimulationStatusOut,
    SpeedRequest,
)
from app.simulation.scenarios import SCENARIO_CATALOG

router = APIRouter(prefix="/api/simulation", tags=["simulation"])


@router.get("/status", response_model=SimulationStatusOut)
def status(request: Request) -> dict:
    return request.app.state.runtime.engine.summary()


@router.post("/start", response_model=SimulationStatusOut)
def start(request: Request) -> dict:
    runtime = request.app.state.runtime
    runtime.engine.start()
    runtime.bus.publish("simulation_status", runtime.engine.summary())
    return runtime.engine.summary()


@router.post("/stop", response_model=SimulationStatusOut)
def stop(request: Request) -> dict:
    runtime = request.app.state.runtime
    runtime.engine.stop()
    runtime.bus.publish("simulation_status", runtime.engine.summary())
    return runtime.engine.summary()


@router.post("/pause", response_model=SimulationStatusOut)
def pause(request: Request) -> dict:
    runtime = request.app.state.runtime
    runtime.engine.pause()
    runtime.bus.publish("simulation_status", runtime.engine.summary())
    return runtime.engine.summary()


@router.post("/resume", response_model=SimulationStatusOut)
def resume(request: Request) -> dict:
    runtime = request.app.state.runtime
    runtime.engine.resume()
    runtime.bus.publish("simulation_status", runtime.engine.summary())
    return runtime.engine.summary()


@router.post("/reset", response_model=SimulationStatusOut)
def reset(request: Request) -> dict:
    request.app.state.runtime.reset()
    return request.app.state.runtime.engine.summary()


@router.post("/speed", response_model=SimulationStatusOut)
def set_speed(body: SpeedRequest, request: Request) -> dict:
    runtime = request.app.state.runtime
    runtime.engine.speed = body.speed
    runtime.bus.publish("simulation_status", runtime.engine.summary())
    return runtime.engine.summary()


@router.post("/devices/count", response_model=SimulationStatusOut)
def set_device_count(body: DeviceCountRequest, request: Request) -> dict:
    runtime = request.app.state.runtime
    runtime.engine.set_device_count(body.count)
    runtime.reset()
    return runtime.engine.summary()


@router.post("/anomaly-rate", response_model=SimulationStatusOut)
def set_anomaly_rate(body: AnomalyRateRequest, request: Request) -> dict:
    runtime = request.app.state.runtime
    runtime.engine.anomaly_rate = body.rate
    runtime.bus.publish("simulation_status", runtime.engine.summary())
    return runtime.engine.summary()


@router.get("/scenarios")
def list_scenarios() -> dict:
    return {"scenarios": [{"name": k, **v} for k, v in SCENARIO_CATALOG.items()]}


@router.post("/inject")
def inject(body: InjectRequest, request: Request) -> dict:
    runtime = request.app.state.runtime
    if runtime.engine.status != "RUNNING":
        raise HTTPException(status_code=409, detail={"error": "simulation_not_running"})
    try:
        result = runtime.engine.inject(body.device_id, body.scenario, body.severity)
    except KeyError:
        raise HTTPException(status_code=404, detail={"error": "device_not_found", "device_id": body.device_id})
    runtime.bus.publish("failure_injected", result)
    return {"ok": True, **result}


@router.post("/demo")
def run_demo(request: Request) -> dict:
    runtime = request.app.state.runtime
    if runtime.engine.status != "RUNNING":
        runtime.engine.start()
    runtime.engine.run_demo_script()
    runtime.bus.publish("simulation_status", runtime.engine.summary())
    return {"ok": True, "message": "Demo scenario queued — watch the incident feed."}
