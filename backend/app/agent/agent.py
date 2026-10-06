"""IncidentAgent — an explicit, tick-driven state machine.

OBSERVE → INVESTIGATE → DECIDE → ACT → VERIFY → RESOLVE/ESCALATE

Every transition writes an AgentEvent row and publishes an SSE event, so the
UI timeline always reflects real backend state — never animation-only output.
"""
from __future__ import annotations

import json
import time
from typing import Any, Optional

from app.agent import rules
from app.agent.llm import LLMDecider
from app.agent.state import Decision, IncidentContext
from app.core.config import Settings
from app.core.events import EventBus
from app.core.logging import get_logger
from app.db.models import AgentEvent
from app.db.repository import Repository
from app.incidents.manager import IncidentManager
from app.tools.registry import ToolContext, ToolRegistry

log = get_logger("agent")

INVESTIGATION_PLAN = [
    ("get_recent_telemetry", lambda ctx: {"device_id": ctx.device_id, "metric": ctx.metric, "limit": 20}),
    ("get_device_baseline", lambda ctx: {"device_id": ctx.device_id, "metric": ctx.metric}),
    ("get_device_history", lambda ctx: {"device_id": ctx.device_id}),
    ("get_related_metrics", lambda ctx: {"device_id": ctx.device_id}),
]


class IncidentAgent:
    def __init__(
        self,
        incident_id: int,
        *,
        repo: Repository,
        manager: IncidentManager,
        registry: ToolRegistry,
        tool_ctx: ToolContext,
        llm: LLMDecider,
        bus: EventBus,
        settings: Settings,
    ) -> None:
        self.repo = repo
        self.manager = manager
        self.registry = registry
        self.tool_ctx = tool_ctx
        self.llm = llm
        self.bus = bus
        self.settings = settings
        incident = repo.get_incident(incident_id)
        assert incident is not None, f"incident {incident_id} not found"
        self.ctx = IncidentContext(
            incident_id=incident.id,
            device_id=incident.device_id,
            metric=incident.metric,
            severity=incident.severity,
            detector=incident.detector,
            anomaly_score=incident.anomaly_score,
        )
        self._llm_future: Any = None
        self._llm_wait_ticks = 0
        self._emit("AGENT_STARTED", f"Agent engaged incident #{incident_id} "
                                    f"({self.ctx.device_id} · {self.ctx.metric} · {self.ctx.severity})")

    # ------------------------------------------------------------------ events
    def _emit(self, event_type: str, message: str, *, tool: str = "",
              tool_input: Any = None, tool_output: Any = None, duration_ms: float = 0.0) -> None:
        row = self.repo.add_agent_event(AgentEvent(
            incident_id=self.ctx.incident_id,
            event_type=event_type,
            message=message,
            tool_name=tool,
            tool_input=json.dumps(tool_input) if tool_input is not None else "",
            tool_output=json.dumps(tool_output) if tool_output is not None else "",
            duration_ms=round(duration_ms, 2),
        ))
        sse_type = {
            "AGENT_STARTED": "agent_started",
            "THOUGHT": "agent_thought",
            "TOOL_STARTED": "tool_started",
            "TOOL_COMPLETED": "tool_completed",
            "DECISION": "agent_decision",
            "REMEDIATION_STARTED": "remediation_started",
            "REMEDIATION_COMPLETED": "remediation_completed",
            "RECOVERY_CHECK": "recovery_check",
            "INCIDENT_RESOLVED": "incident_resolved",
            "INCIDENT_ESCALATED": "incident_updated",
            "FALSE_POSITIVE": "incident_updated",
        }.get(event_type, "agent_thought")
        self.bus.publish(sse_type, {
            "incident_id": self.ctx.incident_id,
            "device_id": self.ctx.device_id,
            "event_type": event_type,
            "message": message,
            "tool": tool,
            "tool_input": tool_input,
            "tool_output": tool_output,
            "duration_ms": round(duration_ms, 2),
        })

    def _run_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        self._emit("TOOL_STARTED", f"Calling {name}", tool=name, tool_input=args)
        start = time.perf_counter()
        result = self.registry.call(name, self.tool_ctx, args)
        duration_ms = (time.perf_counter() - start) * 1000.0
        self._emit("TOOL_COMPLETED", f"{name} completed", tool=name,
                   tool_input=args, tool_output=result, duration_ms=duration_ms)
        return result

    # -------------------------------------------------------------------- main
    def advance(self) -> None:
        if self.ctx.done:
            return
        try:
            if self.ctx.phase == "investigate":
                self._step_investigate()
            elif self.ctx.phase == "decide":
                self._step_decide()
            elif self.ctx.phase == "act":
                self._step_act()
            elif self.ctx.phase == "verify":
                self._step_verify()
        except Exception as exc:  # the agent must never take the runtime down
            log.exception("agent_error incident=%s", self.ctx.incident_id)
            self.manager.escalate(self.ctx.incident_id, f"Agent internal error: {exc}")
            self.ctx.done = True
            self.ctx.outcome = "escalated"

    # -------------------------------------------------------------- investigate
    def _step_investigate(self) -> None:
        ctx = self.ctx
        if ctx.investigation_step == 0:
            self.manager.transition(ctx.incident_id, "INVESTIGATING")
        if ctx.investigation_step >= len(INVESTIGATION_PLAN):
            ctx.current_score = self.tool_ctx.detector.current_score(ctx.device_id, ctx.metric)
            ctx.phase = "decide"
            return
        tool_name, arg_builder = INVESTIGATION_PLAN[ctx.investigation_step]
        result = self._run_tool(tool_name, arg_builder(ctx))
        ctx.investigation_step += 1
        if tool_name == "get_recent_telemetry":
            ctx.telemetry_summary = result
            self._emit("THOUGHT", (
                f"Recent {ctx.metric}: current={result.get('current')} "
                f"mean={result.get('mean')} max={result.get('max')} over {result.get('samples')} samples."
            ))
        elif tool_name == "get_device_baseline":
            ctx.baseline_info = result
            self._emit("THOUGHT", (
                f"Baseline for {ctx.metric}: {result.get('baseline')} "
                f"(normal {result.get('normal_low')}…{result.get('normal_high')})."
            ))
        elif tool_name == "get_device_history":
            ctx.history = result
            self._emit("THOUGHT", (
                f"Device history: {result.get('incident_count')} recent incident(s), "
                f"{len(result.get('recent_actions', []))} prior action(s)."
            ))
        elif tool_name == "get_related_metrics":
            ctx.related = result
            others = [m for m in result.get("abnormal_metrics", []) if m != ctx.metric]
            self._emit("THOUGHT", (
                "Correlated metrics: " + (", ".join(others) if others else "no other metric is abnormal "
                                          "— fault appears isolated to " + ctx.metric + ".")
            ))

    # ------------------------------------------------------------------ decide
    def _step_decide(self) -> None:
        ctx = self.ctx
        if self.llm.available:
            if self._llm_future is None:
                briefing = {
                    "device_id": ctx.device_id, "metric": ctx.metric,
                    "severity": ctx.severity, "detectors": ctx.detector,
                    "anomaly_score": ctx.anomaly_score,
                    "telemetry": ctx.telemetry_summary, "baseline": ctx.baseline_info,
                    "related": ctx.related, "history": ctx.history,
                    "failed_actions": ctx.failed_actions,
                }
                self._llm_future = self.llm.submit(briefing)
                return
            max_wait = int(self.settings.llm_timeout_seconds / max(self.settings.simulation_tick_seconds, 0.05))
            if not self._llm_future.done() and self._llm_wait_ticks < max_wait:
                self._llm_wait_ticks += 1
                return
            llm_decision = None
            if self._llm_future.done():
                try:
                    llm_decision = self._llm_future.result()
                except Exception:
                    llm_decision = None
            if llm_decision is not None:
                ctx.decision = Decision(
                    action=None if llm_decision.action == "monitor" else llm_decision.action,
                    explanation=llm_decision.reason or "LLM-selected action.",
                    confidence=llm_decision.confidence,
                    requires_human=llm_decision.requires_human,
                    source="llm",
                )
                self._emit("THOUGHT", "Decision produced by LLM planner (validated against tool registry).")
            else:
                self._emit("THOUGHT", "LLM unavailable or returned invalid output — falling back to deterministic rules.")
        if ctx.decision is None:
            ctx.decision = rules.decide(ctx, self.settings.agent_recovery_score)
        d = ctx.decision
        self._emit("DECISION", d.explanation, tool=d.action or "monitor",
                   tool_output={"action": d.action or "monitor", "confidence": d.confidence,
                                "risk": d.risk, "source": d.source})
        ctx.phase = "act"

    # --------------------------------------------------------------------- act
    def _step_act(self) -> None:
        ctx = self.ctx
        d = ctx.decision
        assert d is not None
        if d.outcome_hint == "false_positive":
            self.manager.mark_false_positive(ctx.incident_id, d.explanation)
            self._emit("FALSE_POSITIVE", "Incident classified as false positive — closed without action.")
            ctx.done, ctx.outcome = True, "false_positive"
            return
        if d.requires_human or d.action == "escalate_to_human":
            self._run_tool("escalate_to_human", {"device_id": ctx.device_id, "reason": d.explanation})
            self.manager.escalate(ctx.incident_id, d.explanation)
            self._emit("INCIDENT_ESCALATED", "Incident handed to a human operator.")
            ctx.done, ctx.outcome = True, "escalated"
            return
        if d.action is None:
            self.manager.transition(ctx.incident_id, "MONITORING")
            ctx.phase = "verify"
            return
        self.manager.transition(ctx.incident_id, "MITIGATING")
        self._emit("REMEDIATION_STARTED", f"Executing {d.action} on {ctx.device_id}", tool=d.action)
        result = self._run_tool(d.action, {
            "device_id": ctx.device_id, "incident_id": ctx.incident_id, "reason": d.explanation,
        })
        self._emit("REMEDIATION_COMPLETED", f"{d.action} → {result.get('status', 'completed')}",
                   tool=d.action, tool_output=result)
        if result.get("status") == "skipped":
            # Idempotency guard fired — treat as executed and verify outcome.
            self._emit("THOUGHT", result.get("reason", "Action skipped by idempotency guard."))
        ctx.attempts += 1
        ctx.verify_ok_samples = 0
        ctx.verify_ticks = 0
        self.manager.transition(ctx.incident_id, "MONITORING")
        ctx.phase = "verify"

    # ------------------------------------------------------------------- verify
    def _step_verify(self) -> None:
        ctx = self.ctx
        ctx.verify_ticks += 1
        result = self._run_tool("verify_recovery", {"device_id": ctx.device_id, "metric": ctx.metric})
        healthy = bool(result.get("healthy"))
        if healthy:
            ctx.verify_ok_samples += 1
        self._emit("RECOVERY_CHECK", (
            f"Recovery check {ctx.verify_ok_samples}/{self.settings.agent_recovery_samples}: "
            f"{ctx.metric} anomaly score {result.get('current_anomaly_score')}"
        ), tool="verify_recovery", tool_output={
            "sample": ctx.verify_ok_samples,
            "required": self.settings.agent_recovery_samples,
            "score": result.get("current_anomaly_score"),
            "healthy": healthy,
        })
        if ctx.verify_ok_samples >= self.settings.agent_recovery_samples:
            self._resolve()
            return
        # Monitoring-only decisions get a long patience window (transient external
        # faults self-clear); post-remediation verification is strict and fast.
        is_monitoring = ctx.decision is not None and ctx.decision.action is None
        max_verify_ticks = 200 if is_monitoring else self.settings.agent_recovery_samples * 5 + 10
        if ctx.verify_ticks >= max_verify_ticks:
            self._handle_failed_recovery()

    def _resolve(self) -> None:
        ctx = self.ctx
        action = (ctx.decision.action if ctx.decision and ctx.decision.action else "monitoring")
        notes = (f"Recovery verified: {ctx.metric} stayed below anomaly score "
                 f"{self.settings.agent_recovery_score} for "
                 f"{self.settings.agent_recovery_samples} consecutive samples after '{action}'.")
        self._run_tool("close_incident", {"incident_id": ctx.incident_id, "notes": notes})
        self.manager.resolve(ctx.incident_id, action=action, notes=notes)
        self._emit("INCIDENT_RESOLVED", notes)
        ctx.done, ctx.outcome = True, "resolved"

    def _handle_failed_recovery(self) -> None:
        ctx = self.ctx
        failed = ctx.decision.action if ctx.decision else None
        ctx.failed_actions.append(failed or "monitor")
        if ctx.attempts >= self.settings.agent_max_remediation_attempts:
            follow_up: Optional[Decision] = None
        else:
            follow_up = rules.next_action_after_failure(ctx, failed)
        if follow_up is None or follow_up.requires_human or follow_up.action == "escalate_to_human":
            explanation = (follow_up.explanation if follow_up else
                           f"Maximum automated attempts ({self.settings.agent_max_remediation_attempts}) "
                           f"reached for {ctx.device_id}. Escalating to a human operator.")
            self._run_tool("escalate_to_human", {"device_id": ctx.device_id, "reason": explanation})
            self.manager.escalate(ctx.incident_id, explanation)
            self._emit("INCIDENT_ESCALATED", explanation)
            ctx.done, ctx.outcome = True, "escalated"
            return
        ctx.decision = follow_up
        self._emit("DECISION", follow_up.explanation, tool=follow_up.action,
                   tool_output={"action": follow_up.action, "confidence": follow_up.confidence,
                                "risk": follow_up.risk, "source": follow_up.source})
        ctx.phase = "act"


class AgentRuntime:
    """Owns all live agents; advanced once per simulation tick."""

    def __init__(self, *, repo: Repository, manager: IncidentManager, registry: ToolRegistry,
                 tool_ctx: ToolContext, llm: LLMDecider, bus: EventBus, settings: Settings) -> None:
        self.repo, self.manager, self.registry = repo, manager, registry
        self.tool_ctx, self.llm, self.bus, self.settings = tool_ctx, llm, bus, settings
        self.active: dict[int, IncidentAgent] = {}
        self.pending: list[int] = []

    def handle_incident(self, incident_id: int) -> None:
        if incident_id in self.active or incident_id in self.pending:
            return
        if len(self.active) < self.settings.agent_max_concurrent:
            self.active[incident_id] = IncidentAgent(
                incident_id, repo=self.repo, manager=self.manager, registry=self.registry,
                tool_ctx=self.tool_ctx, llm=self.llm, bus=self.bus, settings=self.settings,
            )
        else:
            self.pending.append(incident_id)

    def advance_all(self) -> None:
        for incident_id, agent in list(self.active.items()):
            agent.advance()
            if agent.ctx.done:
                del self.active[incident_id]
        while self.pending and len(self.active) < self.settings.agent_max_concurrent:
            self.handle_incident(self.pending.pop(0))

    @property
    def active_count(self) -> int:
        return len(self.active)

    def reset(self) -> None:
        self.active.clear()
        self.pending.clear()
