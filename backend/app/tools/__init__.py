"""Tool registry assembly."""
from __future__ import annotations

from app.tools.device_tools import get_device_health, get_device_history
from app.tools.registry import LOW_RISK, Tool, ToolRegistry
from app.tools.remediation_tools import REMEDIATION_TOOLS
from app.tools.telemetry_tools import get_device_baseline, get_recent_telemetry, get_related_metrics


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(Tool(
        name="get_recent_telemetry",
        description="Fetch recent samples for one device+metric with summary statistics.",
        risk=LOW_RISK, handler=get_recent_telemetry,
        input_schema={"device_id": "str", "metric": "str", "limit": "int"},
    ))
    registry.register(Tool(
        name="get_device_baseline",
        description="Fetch the learned baseline and normal operating range for one device+metric.",
        risk=LOW_RISK, handler=get_device_baseline,
        input_schema={"device_id": "str", "metric": "str"},
    ))
    registry.register(Tool(
        name="get_device_health",
        description="Current health score, status, restarts, uptime and firmware for a device.",
        risk=LOW_RISK, handler=get_device_health,
        input_schema={"device_id": "str"},
    ))
    registry.register(Tool(
        name="get_device_history",
        description="Recent incidents and remediation actions for a device.",
        risk=LOW_RISK, handler=get_device_history,
        input_schema={"device_id": "str"},
    ))
    registry.register(Tool(
        name="get_related_metrics",
        description="Snapshot of all metrics for a device with per-metric anomaly scores — reveals correlated failures.",
        risk=LOW_RISK, handler=get_related_metrics,
        input_schema={"device_id": "str"},
    ))
    for tool in REMEDIATION_TOOLS.values():
        registry.register(tool)
    return registry
