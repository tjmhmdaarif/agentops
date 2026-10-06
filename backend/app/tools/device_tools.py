"""Device context tools (LOW_RISK)."""
from __future__ import annotations

from typing import Any

from app.tools.registry import LOW_RISK, Tool, ToolContext, ToolError


def get_device_health(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    device_id = str(args.get("device_id", ""))
    device = ctx.repo.get_device(device_id)
    if device is None:
        raise ToolError(f"unknown device: {device_id}")
    return {
        "device_id": device_id,
        "health_score": round(device.health_score, 1),
        "status": device.status,
        "restart_count": device.restart_count,
        "uptime_s": round(device.uptime, 0),
        "firmware_version": device.firmware_version,
    }


def get_device_history(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    device_id = str(args.get("device_id", ""))
    incidents = ctx.repo.recent_incidents_for_device(device_id, limit=10)
    actions = ctx.repo.actions_for_device(device_id, limit=10)
    return {
        "device_id": device_id,
        "recent_incidents": [
            {
                "id": i.id, "metric": i.metric, "severity": i.severity,
                "status": i.status, "action_taken": i.action_taken,
                "age_s": round(__import__("time").time() - i.created_at, 0),
            }
            for i in incidents
        ],
        "recent_actions": [
            {"action": a.action, "status": a.status, "result": a.result[:200]}
            for a in actions
        ],
        "incident_count": len(incidents),
    }
