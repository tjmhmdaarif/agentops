"""Read-only investigation tools (LOW_RISK)."""
from __future__ import annotations

from typing import Any

import numpy as np

from app.simulation.telemetry import METRICS
from app.tools.registry import LOW_RISK, Tool, ToolContext, ToolError


def get_recent_telemetry(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    device_id = str(args.get("device_id", ""))
    metric = str(args.get("metric", ""))
    limit = int(args.get("limit", 20))
    rows = ctx.repo.recent_telemetry(device_id, metric, limit=limit)
    if not rows:
        raise ToolError(f"no telemetry for {device_id}/{metric}")
    values = [r.value for r in rows]
    return {
        "device_id": device_id,
        "metric": metric,
        "samples": len(values),
        "current": round(values[-1], 3),
        "mean": round(float(np.mean(values)), 3),
        "std": round(float(np.std(values)), 3),
        "min": round(min(values), 3),
        "max": round(max(values), 3),
    }


def get_device_baseline(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    device_id = str(args.get("device_id", ""))
    metric = str(args.get("metric", ""))
    baseline = ctx.detector.baselines.get((device_id, metric))
    device = ctx.engine.devices.get(device_id)
    if baseline is None and device is not None:
        baseline = device.baselines.get(metric)
    if baseline is None:
        raise ToolError(f"no baseline for {device_id}/{metric}")
    low, high = ctx.detector.normal_range(device_id, metric)
    return {
        "device_id": device_id,
        "metric": metric,
        "baseline": round(float(baseline), 3),
        "normal_low": round(low, 3),
        "normal_high": round(high, 3),
        "unit": METRICS.get(metric).unit if metric in METRICS else "",
    }


def get_related_metrics(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Snapshot of every metric + its current fused anomaly score for a device."""
    device_id = str(args.get("device_id", ""))
    device = ctx.engine.devices.get(device_id)
    if device is None:
        raise ToolError(f"unknown device: {device_id}")
    out: dict[str, Any] = {}
    for metric, value in device.last_metrics.items():
        out[metric] = {
            "value": round(float(value), 3),
            "baseline": round(float(ctx.detector.baselines.get((device_id, metric), value)), 3),
            "anomaly_score": round(ctx.detector.current_score(device_id, metric), 3),
        }
    abnormal = [m for m, v in out.items() if v["anomaly_score"] >= ctx.settings.anomaly_threshold]
    return {"device_id": device_id, "metrics": out, "abnormal_metrics": abnormal}
