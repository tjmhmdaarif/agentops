"""Deterministic decision rules — the default, reproducible agent brain.

Rules are intentionally explicit and ordered so every decision is explainable.
"""
from __future__ import annotations

from typing import Optional

from app.agent.state import Decision, IncidentContext
from app.tools.registry import HIGH_RISK, HUMAN_REQUIRED, LOW_RISK, MEDIUM_RISK

RESTARTABLE_METRICS = {"temperature", "memory_usage", "cpu_usage", "vibration"}


def decide(ctx: IncidentContext, recovery_score: float) -> Decision:
    related = ctx.related or {}
    abnormal = set(related.get("abnormal_metrics", []))
    others_abnormal = abnormal - {ctx.metric}

    # 1) Transient anomaly that already recovered → false positive.
    if ctx.current_score < recovery_score * 0.7 and ctx.metric != "availability":
        return Decision(
            action=None,
            explanation=(
                f"{ctx.metric} on {ctx.device_id} returned to {ctx.current_score:.2f} anomaly score "
                f"before any action was required — classified as a transient spike, not a real fault."
            ),
            confidence=0.82, risk=LOW_RISK, outcome_hint="false_positive",
        )

    # 2) Battery faults are hardware — always a human job.
    if ctx.metric == "battery":
        return Decision(
            action="escalate_to_human",
            explanation=(
                f"Battery on {ctx.device_id} is draining abnormally and software remediation cannot "
                f"restore charge. Escalating to a human operator for physical maintenance."
            ),
            confidence=0.95, risk=HUMAN_REQUIRED, requires_human=True,
        )

    # 3) Device offline → power-cycle is the only automated option.
    if ctx.metric == "availability":
        return Decision(
            action="restart_device",
            explanation=(
                f"{ctx.device_id} stopped emitting telemetry. A remote restart is the only "
                f"automated recovery path for an unresponsive device."
            ),
            confidence=0.8, risk=HIGH_RISK,
        )

    # 4) Frozen sensor → targeted reset beats a full restart.
    if "zero_variance" in ctx.detector:
        return Decision(
            action="reset_sensor",
            explanation=(
                f"{ctx.metric} on {ctx.device_id} is reporting a frozen value (zero variance). "
                f"A sensor reset is the lowest-risk targeted fix before considering a restart."
            ),
            confidence=0.9, risk=MEDIUM_RISK,
        )

    # 5) Radio/network conditions are usually external → monitor first.
    if ctx.metric == "signal_strength":
        return Decision(
            action=None,
            explanation=(
                f"Signal strength on {ctx.device_id} is degraded, but restarting cannot fix radio "
                f"conditions. Monitoring; will escalate if the condition persists."
            ),
            confidence=0.7, risk=LOW_RISK,
        )
    if ctx.metric == "network_latency" and not others_abnormal:
        return Decision(
            action=None,
            explanation=(
                f"Network latency on {ctx.device_id} is elevated while device health is otherwise "
                f"good — consistent with a transient network condition. Monitoring before acting."
            ),
            confidence=0.72, risk=LOW_RISK,
        )

    # 6) Correlated thermal + mechanical event → shed load first.
    if ctx.metric == "temperature" and "vibration" in others_abnormal:
        return Decision(
            action="set_safe_mode",
            explanation=(
                f"Temperature and vibration are simultaneously abnormal on {ctx.device_id} — a "
                f"probable thermal/mechanical event. Entering safe mode to shed load; a restart "
                f"follows if recovery is not confirmed."
            ),
            confidence=0.88, risk=MEDIUM_RISK,
        )

    # 7) CPU saturation → safe mode sheds load without a full power-cycle.
    if ctx.metric == "cpu_usage":
        return Decision(
            action="set_safe_mode",
            explanation=(
                f"CPU on {ctx.device_id} is saturated. Safe mode sheds non-essential load as the "
                f"least disruptive remediation."
            ),
            confidence=0.85, risk=MEDIUM_RISK,
        )

    # 8) Serious thermal / memory faults → restart.
    if ctx.metric in {"temperature", "memory_usage"} or ctx.severity in {"high", "critical"}:
        return Decision(
            action="restart_device",
            explanation=(
                f"{ctx.metric} on {ctx.device_id} is {ctx.anomaly_score:.2f} anomaly score "
                f"({ctx.severity}). A restart clears thermal runaway, memory leaks and locked "
                f"processes, and is the standard automated remediation for this fault class."
            ),
            confidence=0.9, risk=HIGH_RISK,
        )

    # 9) Default: monitor.
    return Decision(
        action=None,
        explanation=(
            f"Anomaly on {ctx.device_id}/{ctx.metric} is below the automated-action confidence "
            f"floor. Monitoring and gathering more samples."
        ),
        confidence=0.6, risk=LOW_RISK,
    )


def next_action_after_failure(ctx: IncidentContext, failed_action: Optional[str]) -> Optional[Decision]:
    """Escalation chain when remediation did not restore health."""
    if failed_action == "set_safe_mode":
        return Decision(
            action="restart_device",
            explanation=(
                f"Safe mode did not restore {ctx.device_id}. Escalating to a full restart as the "
                f"next automated step."
            ),
            confidence=0.85, risk=HIGH_RISK,
        )
    if failed_action == "reset_sensor":
        return Decision(
            action="restart_device",
            explanation=(
                f"Sensor reset did not restore {ctx.device_id}/{ctx.metric} — the fault is deeper "
                f"than the sensor. Trying a full restart."
            ),
            confidence=0.8, risk=HIGH_RISK,
        )
    if failed_action is None and ctx.metric in RESTARTABLE_METRICS:
        return Decision(
            action="restart_device",
            explanation=(
                f"Monitoring showed {ctx.device_id}/{ctx.metric} is not self-recovering. "
                f"Proceeding with a restart."
            ),
            confidence=0.78, risk=HIGH_RISK,
        )
    return Decision(
        action="escalate_to_human",
        explanation=(
            f"Automated remediation ({failed_action or 'monitoring'}) did not restore "
            f"{ctx.device_id} after {ctx.attempts + 1} attempt(s). Escalating to a human "
            f"operator rather than retrying blindly."
        ),
        confidence=0.9, risk=HUMAN_REQUIRED, requires_human=True,
    )
