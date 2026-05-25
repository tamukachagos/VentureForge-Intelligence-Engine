from datetime import datetime, timezone

from ai_research_stack.budget import BudgetGovernor, BudgetPolicy, BudgetSnapshot
from ai_research_stack.domain import DemandWitness, WitnessType
from ai_research_stack.scoring import (
    ScoreDimensions,
    calculate_composite_score,
    compute_confidence,
    demand_gate,
    is_express_lane_candidate,
)


def witness(kind: WitnessType, strength: float, proxy: bool = False) -> DemandWitness:
    return DemandWitness(
        opportunity_id="opp-1",
        witness_type=kind,
        source="https://example.com/evidence",
        excerpt="buyer explicitly describes the workflow cost",
        strength=strength,
        is_proxy=proxy,
        collected_at=datetime(2026, 5, 24, tzinfo=timezone.utc),
    )


def test_demand_gate_requires_direct_or_proxy_witness():
    assert demand_gate([]).allowed is False

    direct = demand_gate([witness(WitnessType.BUYER_COMPLAINT, 8.0)])
    assert direct.allowed is True
    assert direct.has_direct_witness is True
    assert direct.strongest_strength == 8.0

    proxy = demand_gate([witness(WitnessType.ADJACENT_SPEND, 6.5, proxy=True)])
    assert proxy.allowed is True
    assert proxy.has_direct_witness is False


def test_weighted_score_uses_revised_v1_weights():
    dimensions = ScoreDimensions(
        demand_witness_strength=8.0,
        capability_timing=9.0,
        speed_to_mvp=7.0,
        distribution_edge=6.0,
        defensibility_window=5.0,
        wedge_to_platform=7.0,
        cash_flow_path=6.0,
        novelty=8.0,
    )

    score = calculate_composite_score(dimensions)

    assert round(score, 2) == 7.22


def test_express_lane_requires_direct_witness_not_proxy():
    dimensions = ScoreDimensions(
        demand_witness_strength=9.0,
        capability_timing=9.5,
        speed_to_mvp=7.0,
        distribution_edge=7.0,
        defensibility_window=6.0,
        wedge_to_platform=6.0,
        cash_flow_path=7.0,
        novelty=9.0,
    )

    assert (
        is_express_lane_candidate(
            dimensions=dimensions,
            witnesses=[witness(WitnessType.PAID_INCUMBENT, 9.0)],
            legal_ok=True,
            budget_available=True,
        )
        is True
    )

    assert (
        is_express_lane_candidate(
            dimensions=dimensions,
            witnesses=[witness(WitnessType.ADJACENT_SPEND, 9.0, proxy=True)],
            legal_ok=True,
            budget_available=True,
        )
        is False
    )


def test_confidence_is_computed_from_evidence_not_model_self_report():
    high = compute_confidence(
        source_diversity=5,
        freshness_days=2,
        contradiction_count=0,
        evidence_strength=9.0,
        repeatability=0.9,
    )
    low = compute_confidence(
        source_diversity=1,
        freshness_days=120,
        contradiction_count=3,
        evidence_strength=3.0,
        repeatability=0.2,
    )

    assert high > 0.8
    assert low < 0.35


def test_budget_governor_blocks_caps_and_allows_visibility_thresholds():
    policy = BudgetPolicy()
    governor = BudgetGovernor(policy)

    ok = governor.authorize_llm_spend(
        BudgetSnapshot(daily_llm_spend=14.50, monthly_data_spend=10.0, ask_tracker_daily_spend=0.0),
        amount=0.25,
        opportunity_lifetime_spend=0.50,
    )
    assert ok.allowed is True
    assert ok.requires_owner_approval is False

    blocked_daily = governor.authorize_llm_spend(
        BudgetSnapshot(daily_llm_spend=14.90, monthly_data_spend=10.0, ask_tracker_daily_spend=0.0),
        amount=0.25,
        opportunity_lifetime_spend=0.50,
    )
    assert blocked_daily.allowed is False
    assert "daily LLM cap" in blocked_daily.reason

    needs_owner = governor.authorize_llm_spend(
        BudgetSnapshot(daily_llm_spend=3.0, monthly_data_spend=10.0, ask_tracker_daily_spend=0.0),
        amount=0.25,
        opportunity_lifetime_spend=2.90,
    )
    assert needs_owner.allowed is False
    assert needs_owner.requires_owner_approval is True

    ask_tracker = governor.authorize_ask_tracker(
        BudgetSnapshot(daily_llm_spend=1.0, monthly_data_spend=10.0, ask_tracker_daily_spend=1.45),
        estimated_cost=0.10,
    )
    assert ask_tracker.allowed is False
    assert "ask-tracker daily cap" in ask_tracker.reason
