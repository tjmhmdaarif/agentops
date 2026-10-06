"""Agent state types."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Decision:
    action: Optional[str]        # None → passive monitoring
    explanation: str             # safe operational summary, NOT chain-of-thought
    confidence: float
    risk: str = "LOW_RISK"
    requires_human: bool = False
    source: str = "rules"        # "rules" | "llm"
    outcome_hint: str = ""       # "false_positive" short-circuits the loop


@dataclass
class IncidentContext:
    incident_id: int
    device_id: str
    metric: str
    severity: str
    detector: str
    anomaly_score: float

    phase: str = "investigate"
    investigation_step: int = 0
    telemetry_summary: dict[str, Any] = field(default_factory=dict)
    baseline_info: dict[str, Any] = field(default_factory=dict)
    history: dict[str, Any] = field(default_factory=dict)
    related: dict[str, Any] = field(default_factory=dict)
    current_score: float = 1.0

    decision: Optional[Decision] = None
    attempts: int = 0
    failed_actions: list[str] = field(default_factory=list)
    verify_ok_samples: int = 0
    verify_ticks: int = 0
    done: bool = False
    outcome: str = ""            # resolved | escalated | false_positive
