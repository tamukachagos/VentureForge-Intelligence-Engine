from datetime import datetime, timezone

from ai_research_stack.domain import DemandWitness, OpportunityStage, WitnessType
from ai_research_stack.orchestrator import OpportunityCandidate, Orchestrator
from ai_research_stack.scoring import ScoreDimensions


def dimensions(novelty: float = 8.5, timing: float = 8.8) -> ScoreDimensions:
    return ScoreDimensions(
        demand_witness_strength=8.0,
        capability_timing=timing,
        speed_to_mvp=8.0,
        distribution_edge=8.0,
        defensibility_window=7.0,
        wedge_to_platform=7.0,
        cash_flow_path=7.0,
        novelty=novelty,
    )


def direct_witness() -> DemandWitness:
    return DemandWitness(
        opportunity_id="opp-1",
        witness_type=WitnessType.PAID_INCUMBENT,
        source="https://example.com/pricing",
        excerpt="customers are paying for a worse workflow",
        strength=8.0,
        is_proxy=False,
        collected_at=datetime(2026, 5, 24, tzinfo=timezone.utc),
    )


def proxy_witness() -> DemandWitness:
    return DemandWitness(
        opportunity_id="opp-1",
        witness_type=WitnessType.ADJACENT_SPEND,
        source="https://example.com/market",
        excerpt="nearby teams buy adjacent tooling",
        strength=7.0,
        is_proxy=True,
        collected_at=datetime(2026, 5, 24, tzinfo=timezone.utc),
    )


def test_orchestrator_routes_no_witness_to_watchlist():
    decision = Orchestrator().route_candidate(
        OpportunityCandidate(
            opportunity_id="opp-1",
            legal_ok=True,
            builder_fit_ok=True,
            witnesses=[],
            dimensions=dimensions(),
            budget_available=True,
        )
    )

    assert decision.stage == OpportunityStage.WATCHLIST
    assert decision.task_types == ()


def test_orchestrator_routes_proxy_witness_to_research_not_express():
    decision = Orchestrator().route_candidate(
        OpportunityCandidate(
            opportunity_id="opp-1",
            legal_ok=True,
            builder_fit_ok=True,
            witnesses=[proxy_witness()],
            dimensions=dimensions(),
            budget_available=True,
        )
    )

    assert decision.stage == OpportunityStage.RESEARCH
    assert decision.task_types == ("full_research", "saturation_check", "wrapper_check")


def test_orchestrator_routes_strong_direct_witness_to_express_research():
    decision = Orchestrator().route_candidate(
        OpportunityCandidate(
            opportunity_id="opp-1",
            legal_ok=True,
            builder_fit_ok=True,
            witnesses=[direct_witness()],
            dimensions=dimensions(),
            budget_available=True,
        )
    )

    assert decision.stage == OpportunityStage.EXPRESS_RESEARCH
    assert "claude_critic" in decision.task_types


def test_orchestrator_hard_stops_legal_or_builder_fit_failures():
    legal = Orchestrator().route_candidate(
        OpportunityCandidate(
            opportunity_id="opp-1",
            legal_ok=False,
            builder_fit_ok=True,
            witnesses=[direct_witness()],
            dimensions=dimensions(),
            budget_available=True,
        )
    )
    builder = Orchestrator().route_candidate(
        OpportunityCandidate(
            opportunity_id="opp-1",
            legal_ok=True,
            builder_fit_ok=False,
            witnesses=[direct_witness()],
            dimensions=dimensions(),
            budget_available=True,
        )
    )

    assert legal.stage == OpportunityStage.HARD_STOP
    assert builder.stage == OpportunityStage.HARD_STOP
