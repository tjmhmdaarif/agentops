"""Anomaly score fusion, severity bands and human-readable explanations."""
from __future__ import annotations

from dataclasses import dataclass, field

# Fusion weights — Isolation Forest is a first-class citizen of the decision.
WEIGHTS = {"zscore": 0.30, "ewma": 0.20, "rate": 0.15, "iforest": 0.35}

SEVERITY_BANDS = [
    (0.85, "critical"),
    (0.70, "high"),
    (0.55, "medium"),
    (0.35, "low"),
    (0.00, "normal"),
]


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def severity_for(score: float) -> str:
    for floor, name in SEVERITY_BANDS:
        if score >= floor:
            return name
    return "normal"


@dataclass
class DetectorSignals:
    zscore: float = 0.0     # raw |z|
    ewma: float = 0.0       # raw ewma z
    rate: float = 0.0       # relative change
    iforest: float = 0.0    # already 0..1


@dataclass
class DetectionResult:
    device_id: str
    metric: str
    is_anomaly: bool
    score: float
    severity: str
    detectors: list[str] = field(default_factory=list)
    explanation: str = ""
    value: float = 0.0
    baseline: float = 0.0
    signals: DetectorSignals = field(default_factory=DetectorSignals)


def fuse(
    signals: DetectorSignals,
    z_thresh: float,
    ewma_thresh: float,
    roc_thresh: float,
    extra_fired: list[str] | None = None,
    iforest_active: bool = True,
    allow_override: bool = True,
) -> tuple[float, list[str]]:
    """Combine raw detector outputs into one 0..1 score; list the contributing detectors.

    When the Isolation Forest is not yet trained it abstains and the remaining
    detector weights are renormalized — early-life scoring stays calibrated.
    """
    sub = {
        "zscore": clamp01(signals.zscore / (z_thresh * 2.0)),
        "ewma": clamp01(signals.ewma / (ewma_thresh * 2.0)),
        "rate": clamp01(signals.rate / (roc_thresh * 2.5)),
        "iforest": clamp01(signals.iforest),
    }
    weights = dict(WEIGHTS)
    if not iforest_active:
        weights.pop("iforest")
        total = sum(weights.values())
        weights = {k: w / total for k, w in weights.items()}
    fired = [
        name for name, fired_flag in [
            ("zscore", signals.zscore >= z_thresh),
            ("ewma", signals.ewma >= ewma_thresh),
            ("rate", signals.rate >= roc_thresh),
            ("iforest", signals.iforest >= 0.55),
        ] if fired_flag
    ]
    for name in extra_fired or []:
        if name not in fired:
            fired.append(name)
        # A structural detector firing guarantees at least a strong univariate contribution.
        sub["zscore"] = max(sub["zscore"], 0.9)
    score = sum(weights[k] * sub[k] for k in weights)
    # Dominant-detector override: a single *structural* detector at near-maximum
    # confidence may raise an alarm on its own (EWMA is the only detector that
    # can see a slow memory leak; the rolling window absorbs ramps). Rate-of-
    # change is excluded — a one-step jump alone must never create an incident.
    dominant = max(sub["zscore"], sub["ewma"], sub["iforest"])
    if allow_override and dominant >= 0.9:
        score = max(score, 0.55 + (dominant - 0.9) * 1.5)
    return clamp01(score), fired


def build_explanation(
    metric: str, value: float, baseline: float, signals: DetectorSignals, detectors: list[str],
) -> str:
    """Safe operational summary (not chain-of-thought)."""
    if baseline and abs(baseline) > 1e-9:
        ratio = value / baseline
        pct = abs(ratio - 1.0) * 100.0
        direction = "above" if ratio >= 1.0 else "below"
        core = f"{metric} is {pct:.0f}% {direction} its learned baseline ({value:.2f} vs {baseline:.2f})."
    else:
        core = f"{metric} reads {value:.2f} against a baseline of {baseline:.2f}."
    details: list[str] = []
    if "zero_variance" in detectors:
        details.append("sensor output frozen — zero variance across the observation window")
    if "zscore" in detectors:
        details.append(f"z-score {signals.zscore:.1f}")
    if "ewma" in detectors:
        details.append(f"sustained drift (EWMA {signals.ewma:.1f})")
    if "rate" in detectors:
        details.append(f"sudden jump ({signals.rate * 100:.0f}% in one step)")
    if "iforest" in detectors:
        details.append("multivariate pattern outside learned operating envelope")
    if details:
        core += " Flagged by: " + "; ".join(details) + "."
    return core
