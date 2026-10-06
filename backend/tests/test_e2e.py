"""Deterministic end-to-end test (spec §47).

Start simulator → inject critical temperature failure into EDGE-004 →
detection → incident → investigation → tool calls → decision → restart →
recovery verification → RESOLVED → complete timeline.
"""
from __future__ import annotations

from tests.conftest import run_ticks

EXPECTED_SEQUENCE = [
    "AGENT_STARTED",
    "TOOL_STARTED",      # get_recent_telemetry
    "TOOL_COMPLETED",
    "DECISION",
    "REMEDIATION_STARTED",
    "REMEDIATION_COMPLETED",
    "RECOVERY_CHECK",
    "INCIDENT_RESOLVED",
]


def _is_subsequence(needle: list[str], haystack: list[str]) -> bool:
    it = iter(haystack)
    return all(any(item == h for h in it) for item in needle)


def test_full_autonomous_loop(runtime, bus):
    queue = bus.subscribe()
    run_ticks(runtime, 30)

    runtime.engine.inject("EDGE-004", "temperature_spike", "critical")

    resolved = None
    for _ in range(200):
        runtime.tick()
        incidents, _ = runtime.repo.list_incidents(device_id="EDGE-004")
        terminal = [i for i in incidents if i.status == "RESOLVED"]
        if terminal:
            resolved = terminal[0]
            break

    assert resolved is not None, "incident was not resolved within 200 ticks"
    assert resolved.metric == "temperature"
    assert resolved.action_taken == "restart_device"
    assert resolved.severity in {"high", "critical"}
    assert resolved.resolved_at is not None and resolved.resolved_at > resolved.created_at

    # Timeline completeness + ordering
    timeline = runtime.repo.incident_timeline(resolved.id)
    types = [e.event_type for e in timeline]
    assert _is_subsequence(EXPECTED_SEQUENCE, types)

    decision = next(e for e in timeline if e.event_type == "DECISION")
    assert "restart" in decision.message.lower() or "restart" in decision.tool_name

    restart = next(e for e in timeline if e.event_type == "REMEDIATION_COMPLETED")
    assert restart.tool_name == "restart_device"

    # Recovery was genuinely verified, not assumed
    checks = [e for e in timeline if e.event_type == "RECOVERY_CHECK"]
    assert len(checks) >= runtime.settings.agent_recovery_samples

    # Device actually recovered
    device = runtime.repo.get_device("EDGE-004")
    assert device.status in {"ONLINE", "WARNING", "RECOVERING"}
    assert device.restart_count >= 1

    # SSE bus carried the whole story
    seen = set()
    while not queue.empty():
        seen.add(queue.get_nowait()["type"])
    assert {"telemetry", "anomaly_detected", "incident_created", "agent_started",
            "tool_completed", "agent_decision", "remediation_completed",
            "recovery_check", "incident_resolved"} <= seen
