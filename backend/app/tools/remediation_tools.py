"""Remediation tools — mutate the simulated fleet (guarded by risk class + idempotency)."""
from __future__ import annotations

import time
from typing import Any

from app.db.models import DeviceAction
from app.tools.registry import HIGH_RISK, HUMAN_REQUIRED, LOW_RISK, MEDIUM_RISK, Tool, ToolContext, ToolError


def _record(ctx: ToolContext, device_id: str, incident_id: int | None, action: str,
            reason: str, result: dict[str, Any]) -> dict[str, Any]:
    row = ctx.repo.add_device_action(DeviceAction(
        device_id=device_id,
        incident_id=incident_id,
        action=action,
        status="COMPLETED" if result.get("status", "completed") != "error" else "FAILED",
        reason=reason,
        completed_at=time.time(),
        result=str(result)[:500],
    ))
    result = dict(result)
    result["action_id"] = row.id
    return result


def restart_device(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    device_id = str(args.get("device_id", ""))
    if device_id not in ctx.engine.devices:
        raise ToolError(f"unknown device: {device_id}")
    result = ctx.engine.restart_device(device_id)
    device = ctx.engine.devices[device_id]
    ctx.repo.update_device_fields(device_id, restart_count=device.restart_count)
    return _record(ctx, device_id, args.get("incident_id"), "restart_device",
                   str(args.get("reason", "")), {"status": "completed", **result})


def set_safe_mode(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    device_id = str(args.get("device_id", ""))
    device = ctx.engine.devices.get(device_id)
    if device is None:
        raise ToolError(f"unknown device: {device_id}")
    result = device.set_safe_mode()
    return _record(ctx, device_id, args.get("incident_id"), "set_safe_mode",
                   str(args.get("reason", "")), {"status": "completed", **result})


def reduce_sampling_rate(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    device_id = str(args.get("device_id", ""))
    device = ctx.engine.devices.get(device_id)
    if device is None:
        raise ToolError(f"unknown device: {device_id}")
    result = device.reduce_sampling_rate()
    return _record(ctx, device_id, args.get("incident_id"), "reduce_sampling_rate",
                   str(args.get("reason", "")), {"status": "completed", **result})


def reset_sensor(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    device_id = str(args.get("device_id", ""))
    device = ctx.engine.devices.get(device_id)
    if device is None:
        raise ToolError(f"unknown device: {device_id}")
    result = device.reset_sensor()
    return _record(ctx, device_id, args.get("incident_id"), "reset_sensor",
                   str(args.get("reason", "")), {"status": "completed", **result})


def escalate_to_human(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """No automation is safe/allowed — hand off with full context attached."""
    return {
        "status": "escalated",
        "device_id": args.get("device_id"),
        "reason": args.get("reason", ""),
        "ticket": f"OPS-{int(time.time()) % 100000:05d}",
    }


def verify_recovery(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    device_id = str(args.get("device_id", ""))
    metric = str(args.get("metric", ""))
    if metric == "availability":
        device = ctx.engine.devices.get(device_id)
        online = device is not None and not device.is_offline
        return {
            "device_id": device_id,
            "metric": metric,
            "current_anomaly_score": 0.0 if online else 0.9,
            "healthy": online,
        }
    healthy, deviation, baseline, limit = ctx.detector.recovery_check(device_id, metric)
    # Pseudo-score for display: 0 at baseline, 1 at 2x the healthy limit.
    display_score = min(1.0, deviation / max(2.0 * limit, 1e-9))
    return {
        "device_id": device_id,
        "metric": metric,
        "current_anomaly_score": round(display_score, 3),
        "deviation_from_baseline": round(deviation, 3),
        "baseline": round(baseline, 3),
        "healthy": healthy,
    }


def close_incident(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """The agent still performs the actual status transition; this tool is the
    explicit, auditable decision point to close."""
    return {
        "status": "close_recommended",
        "incident_id": args.get("incident_id"),
        "notes": args.get("notes", ""),
    }


REMEDIATION_TOOLS = {
    "restart_device": Tool(
        name="restart_device",
        description="Power-cycle the device. Clears software faults (thermal runaway, memory leaks, CPU lock, stuck states). Brief offline window. HIGH RISK.",
        risk=HIGH_RISK,
        handler=restart_device,
        input_schema={"device_id": "str", "reason": "str"},
        remediation=True,
    ),
    "set_safe_mode": Tool(
        name="set_safe_mode",
        description="Throttle the device: sheds CPU/vibration load. MEDIUM RISK, reversible.",
        risk=MEDIUM_RISK,
        handler=set_safe_mode,
        input_schema={"device_id": "str", "reason": "str"},
        remediation=True,
    ),
    "reduce_sampling_rate": Tool(
        name="reduce_sampling_rate",
        description="Reduce telemetry sampling to relieve network pressure. MEDIUM RISK.",
        risk=MEDIUM_RISK,
        handler=reduce_sampling_rate,
        input_schema={"device_id": "str", "reason": "str"},
        remediation=True,
    ),
    "reset_sensor": Tool(
        name="reset_sensor",
        description="Reinitialize a frozen/stuck sensor. MEDIUM RISK.",
        risk=MEDIUM_RISK,
        handler=reset_sensor,
        input_schema={"device_id": "str", "reason": "str"},
        remediation=True,
    ),
    "escalate_to_human": Tool(
        name="escalate_to_human",
        description="Hand the incident to a human operator with full context. Required for hardware faults (e.g. battery).",
        risk=HUMAN_REQUIRED,
        handler=escalate_to_human,
        input_schema={"device_id": "str", "reason": "str"},
        remediation=False,
    ),
    "verify_recovery": Tool(
        name="verify_recovery",
        description="Check whether a metric's anomaly score has returned below the recovery threshold.",
        risk=LOW_RISK,
        handler=verify_recovery,
        input_schema={"device_id": "str", "metric": "str"},
        remediation=False,
    ),
    "close_incident": Tool(
        name="close_incident",
        description="Close an incident after verified recovery. LOW RISK.",
        risk=LOW_RISK,
        handler=close_incident,
        input_schema={"incident_id": "int", "notes": "str"},
        remediation=False,
    ),
}
