from __future__ import annotations

from dataclasses import dataclass

from ai_research_stack.domain import DemandGateResult, DemandWitness


@dataclass(frozen=True)
class ScoreDimensions:
    demand_witness_strength: float
    capability_timing: float
    speed_to_mvp: float
    distribution_edge: float
    defensibility_window: float
    wedge_to_platform: float
    cash_flow_path: float
    novelty: float


WEIGHTS: dict[str, float] = {
    "demand_witness_strength": 0.20,
    "capability_timing": 0.18,
    "speed_to_mvp": 0.13,
    "distribution_edge": 0.13,
    "defensibility_window": 0.10,
    "wedge_to_platform": 0.09,
    "cash_flow_path": 0.09,
    "novelty": 0.08,
}


def clamp(value: float, low: float = 0.0, high: float = 10.0) -> float:
    return max(low, min(high, value))


def demand_gate(witnesses: list[DemandWitness]) -> DemandGateResult:
    valid = [w for w in witnesses if w.strength > 0 and w.source and w.excerpt]
    if not valid:
        return DemandGateResult(
            allowed=False,
            reason="No direct or proxy demand witness found",
            has_direct_witness=False,
            strongest_strength=0.0,
        )
    strongest = max(valid, key=lambda w: w.strength)
    has_direct = any(not witness.is_proxy for witness in valid)
    witness_label = "direct" if has_direct else "proxy"
    return DemandGateResult(
        allowed=True,
        reason=f"Found {witness_label} demand witness",
        has_direct_witness=has_direct,
        strongest_strength=strongest.strength,
    )


def calculate_composite_score(dimensions: ScoreDimensions) -> float:
    total = 0.0
    for name, weight in WEIGHTS.items():
        total += clamp(getattr(dimensions, name)) * weight
    return round(total, 4)


def is_express_lane_candidate(
    dimensions: ScoreDimensions,
    witnesses: list[DemandWitness],
    legal_ok: bool,
    budget_available: bool,
) -> bool:
    gate = demand_gate(witnesses)
    return (
        legal_ok
        and budget_available
        and gate.allowed
        and gate.has_direct_witness
        and dimensions.capability_timing >= 8.5
        and dimensions.novelty >= 8.0
        and calculate_composite_score(dimensions) >= 7.5
    )


def compute_confidence(
    source_diversity: int,
    freshness_days: int,
    contradiction_count: int,
    evidence_strength: float,
    repeatability: float,
) -> float:
    diversity_score = min(source_diversity / 5.0, 1.0)
    freshness_score = max(0.0, 1.0 - min(freshness_days, 90) / 90.0)
    contradiction_penalty = min(contradiction_count * 0.15, 0.45)
    evidence_score = clamp(evidence_strength) / 10.0
    repeatability_score = max(0.0, min(1.0, repeatability))

    raw = (
        diversity_score * 0.25
        + freshness_score * 0.20
        + evidence_score * 0.30
        + repeatability_score * 0.25
    )
    return round(max(0.0, min(1.0, raw - contradiction_penalty)), 4)
