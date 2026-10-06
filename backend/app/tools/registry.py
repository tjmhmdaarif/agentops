"""Strict tool registry — the agent may ONLY act through registered tools."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:  # avoid import cycles
    from app.core.config import Settings
    from app.core.events import EventBus
    from app.db.repository import Repository
    from app.detection.detector import HybridDetector
    from app.simulation.engine import SimulationEngine

LOW_RISK = "LOW_RISK"
MEDIUM_RISK = "MEDIUM_RISK"
HIGH_RISK = "HIGH_RISK"
HUMAN_REQUIRED = "HUMAN_REQUIRED"


class ToolError(Exception):
    pass


@dataclass
class ToolContext:
    repo: "Repository"
    engine: "SimulationEngine"
    detector: "HybridDetector"
    bus: "EventBus"
    settings: "Settings"


@dataclass
class Tool:
    name: str
    description: str
    risk: str
    handler: Callable[[ToolContext, dict[str, Any]], dict[str, Any]]
    input_schema: dict[str, Any] = field(default_factory=dict)
    remediation: bool = False        # remediation tools are idempotency-guarded


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise ToolError(f"tool not registered: {name}")
        return self._tools[name]

    def names(self) -> list[str]:
        return sorted(self._tools)

    def describe_all(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "risk": t.risk,
                "input_schema": t.input_schema,
            }
            for t in (self._tools[n] for n in self.names())
        ]

    def call(self, name: str, ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool with idempotency protection for remediation actions."""
        tool = self.get(name)
        if tool.remediation:
            device_id = str(args.get("device_id", ""))
            last = ctx.repo.last_action_for_device(device_id, name)
            if last is not None and (time.time() - last.started_at) < ctx.settings.agent_action_cooldown_seconds:
                return {
                    "status": "skipped",
                    "reason": f"{name} was already executed on {device_id} "
                              f"{time.time() - last.started_at:.0f}s ago (idempotency window "
                              f"{ctx.settings.agent_action_cooldown_seconds:.0f}s).",
                }
        try:
            return tool.handler(ctx, args)
        except ToolError as exc:
            # Expected data-availability errors (e.g. no telemetry yet) — not fatal.
            return {"status": "error", "reason": str(exc)}
        except Exception as exc:  # a failing tool must never crash the agent loop
            return {"status": "error", "reason": f"{type(exc).__name__}: {exc}"}
