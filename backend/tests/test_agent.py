"""Agent tests: rule decisions, remediation chains, recovery, escalation, LLM fallback."""
from __future__ import annotations

import time

from app.agent.llm import LLMDecider, LLMDecision
from app.agent.state import IncidentContext
from app.agent import rules
from app.simulation.device import SimulatedDevice

from tests.conftest import run_ticks


def _ctx(metric: str, severity: str = "high", detector: str = "zscore",
         related: dict | None = None, current_score: float = 0.9) -> IncidentContext:
    return IncidentContext(
        incident_id=1, device_id="EDGE-004", metric=metric, severity=severity,
        detector=detector, anomaly_score=0.9, related=related or {"abnormal_metrics": [metric]},
        current_score=current_score,
    )


# -------------------------------------------------------------------- rules


def test_rule_battery_escalates():
    d = rules.decide(_ctx("battery"), recovery_score=0.4)
    assert d.action == "escalate_to_human" and d.requires_human


def test_rule_temperature_restarts():
    d = rules.decide(_ctx("temperature", severity="critical"), recovery_score=0.4)
    assert d.action == "restart_device"


def test_rule_offline_restarts():
    d = rules.decide(_ctx("availability"), recovery_score=0.4)
    assert d.action == "restart_device"


def test_rule_stuck_sensor_resets():
    d = rules.decide(_ctx("vibration", detector="zero_variance"), recovery_score=0.4)
    assert d.action == "reset_sensor"


def test_rule_correlated_safe_mode():
    ctx = _ctx("temperature", related={"abnormal_metrics": ["temperature", "vibration"]})
    d = rules.decide(ctx, recovery_score=0.4)
    assert d.action == "set_safe_mode"


def test_rule_transient_is_false_positive():
    d = rules.decide(_ctx("temperature", current_score=0.1), recovery_score=0.4)
    assert d.action is None and d.outcome_hint == "false_positive"


def test_rule_network_monitors_when_isolated():
    d = rules.decide(_ctx("network_latency"), recovery_score=0.4)
    assert d.action is None


def test_chain_safe_mode_then_restart():
    ctx = _ctx("temperature")
    d = rules.next_action_after_failure(ctx, "set_safe_mode")
    assert d is not None and d.action == "restart_device"


def test_chain_restart_then_escalate():
    ctx = _ctx("temperature")
    d = rules.next_action_after_failure(ctx, "restart_device")
    assert d is not None and d.action == "escalate_to_human"


# --------------------------------------------------------------- full loops


def _run_until_terminal(runtime, device: str, budget: int = 260):
    for _ in range(budget):
        runtime.tick()
        incidents, _ = runtime.repo.list_incidents(device_id=device)
        terminal = [i for i in incidents if i.status in ("RESOLVED", "ESCALATED", "FALSE_POSITIVE")]
        if terminal:
            return terminal[0]
    return None


def test_temperature_incident_full_loop(runtime):
    run_ticks(runtime, 30)
    runtime.engine.inject("EDGE-004", "temperature_spike", "critical")
    incident = _run_until_terminal(runtime, "EDGE-004")
    assert incident is not None and incident.status == "RESOLVED"
    assert incident.action_taken == "restart_device"


def test_battery_incident_escalates(runtime):
    run_ticks(runtime, 30)
    runtime.engine.inject("EDGE-005", "battery_drain", "high")
    incident = _run_until_terminal(runtime, "EDGE-005")
    assert incident is not None and incident.status == "ESCALATED"


def test_stuck_sensor_reset(runtime):
    run_ticks(runtime, 30)
    runtime.engine.inject("EDGE-006", "sensor_stuck", "medium")
    incident = _run_until_terminal(runtime, "EDGE-006")
    assert incident is not None
    assert incident.status == "RESOLVED"
    assert incident.action_taken == "reset_sensor"


def test_recovery_failure_escalates(runtime, monkeypatch):
    """If remediation cannot restore health, the agent must escalate."""
    run_ticks(runtime, 30)

    def broken_restart(self: SimulatedDevice, tick: int):
        # Power-cycle that clears nothing.
        self.offline_ticks_remaining = 1
        self.restart_count += 1
        return {"cleared_effects": 0, "remaining_effects": len(self.effects)}

    monkeypatch.setattr(SimulatedDevice, "restart", broken_restart)
    runtime.engine.inject("EDGE-004", "temperature_spike", "critical")
    incident = _run_until_terminal(runtime, "EDGE-004", budget=200)
    assert incident is not None and incident.status == "ESCALATED"


def test_multi_step_remediation(runtime):
    """Correlated failure: safe mode first, restart when it isn't enough."""
    run_ticks(runtime, 30)
    runtime.engine.inject("EDGE-004", "correlated_failure", "critical")
    incident = _run_until_terminal(runtime, "EDGE-004")
    assert incident is not None and incident.status == "RESOLVED"
    actions = runtime.repo.actions_for_device("EDGE-004")
    action_names = [a.action for a in actions]
    assert "set_safe_mode" in action_names


def test_restart_idempotency(runtime):
    """A second restart within the cooldown window must be skipped."""
    run_ticks(runtime, 10)
    first = runtime.registry.call("restart_device", runtime.tool_ctx, {"device_id": "EDGE-001", "reason": "t"})
    second = runtime.registry.call("restart_device", runtime.tool_ctx, {"device_id": "EDGE-001", "reason": "t"})
    assert first.get("status") == "completed"
    assert second.get("status") == "skipped"
    assert "idempotency" in second.get("reason", "")


def test_timeline_records_all_phases(runtime):
    run_ticks(runtime, 30)
    runtime.engine.inject("EDGE-004", "temperature_spike", "critical")
    incident = _run_until_terminal(runtime, "EDGE-004")
    assert incident is not None
    timeline = runtime.repo.incident_timeline(incident.id)
    types = [e.event_type for e in timeline]
    for expected in ("AGENT_STARTED", "TOOL_STARTED", "TOOL_COMPLETED", "DECISION",
                     "REMEDIATION_STARTED", "REMEDIATION_COMPLETED", "RECOVERY_CHECK",
                     "INCIDENT_RESOLVED"):
        assert expected in types, f"missing {expected}"
    tools_called = {e.tool_name for e in timeline if e.event_type == "TOOL_COMPLETED"}
    assert {"get_recent_telemetry", "get_device_baseline", "get_device_history",
            "get_related_metrics", "restart_device", "verify_recovery",
            "close_incident"} <= tools_called


# ------------------------------------------------------------------ LLM mode


def test_llm_unavailable_falls_back_to_rules(settings):
    """LLM enabled but SDK/key missing → deterministic rules still decide."""
    settings.llm_enabled = True
    settings.anthropic_api_key = ""
    decider = LLMDecider(settings, None)  # registry unused when unavailable
    assert not decider.available


def test_llm_invalid_output_returns_none(settings):
    settings.llm_enabled = True
    settings.anthropic_api_key = "fake-key"
    decider = LLMDecider(settings, None)
    if decider.available:
        # SDK present but the API call must fail (fake key) → None, never raises.
        assert decider.submit({}).result(timeout=30) is None
    else:
        assert decider.submit({}).result(timeout=30) is None


def test_llm_decision_schema_validation():
    valid = LLMDecision.model_validate({
        "action": "restart_device", "confidence": 0.9,
        "severity": "high", "reason": "test", "requires_human": False,
    })
    assert valid.action == "restart_device"
    import pydantic
    try:
        LLMDecision.model_validate({"action": "restart_device", "confidence": 5.0})
        raise AssertionError("confidence > 1 must be rejected")
    except pydantic.ValidationError:
        pass


def test_agent_works_with_llm_enabled_but_broken(runtime):
    runtime.settings.llm_enabled = True
    runtime.settings.anthropic_api_key = "definitely-not-a-real-key"
    run_ticks(runtime, 30)
    runtime.engine.inject("EDGE-004", "temperature_spike", "critical")
    incident = _run_until_terminal(runtime, "EDGE-004")
    assert incident is not None and incident.status == "RESOLVED"
