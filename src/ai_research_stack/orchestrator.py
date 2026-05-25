from __future__ import annotations

from dataclasses import dataclass

from ai_research_stack.domain import DemandWitness, OpportunityDecision, OpportunityStage
from ai_research_stack.scoring import ScoreDimensions, calculate_composite_score, demand_gate
from ai_research_stack.scoring import is_express_lane_candidate


@dataclass(frozen=True)
class OpportunityCandidate:
    opportunity_id: str
    legal_ok: bool
    builder_fit_ok: bool
    witnesses: list[DemandWitness]
    dimensions: ScoreDimensions
    budget_available: bool


class Orchestrator:
    def route_candidate(self, candidate: OpportunityCandidate) -> OpportunityDecision:
        if not candidate.legal_ok:
            return OpportunityDecision(
                opportunity_id=candidate.opportunity_id,
                stage=OpportunityStage.HARD_STOP,
                reason="Legal/compliance hard stop",
            )
        if not candidate.builder_fit_ok:
            return OpportunityDecision(
                opportunity_id=candidate.opportunity_id,
                stage=OpportunityStage.HARD_STOP,
                reason="Builder-fit hard stop",
            )

        gate = demand_gate(candidate.witnesses)
        if not gate.allowed:
            return OpportunityDecision(
                opportunity_id=candidate.opportunity_id,
                stage=OpportunityStage.WATCHLIST,
                reason=gate.reason,
            )

        if is_express_lane_candidate(
            dimensions=candidate.dimensions,
            witnesses=candidate.witnesses,
            legal_ok=candidate.legal_ok,
            budget_available=candidate.budget_available,
        ):
            return OpportunityDecision(
                opportunity_id=candidate.opportunity_id,
                stage=OpportunityStage.EXPRESS_RESEARCH,
                reason="Direct demand witness plus high timing and novelty",
                task_types=("full_research", "saturation_check", "wrapper_check", "claude_critic"),
            )

        if calculate_composite_score(candidate.dimensions) >= 6.5 and candidate.budget_available:
            return OpportunityDecision(
                opportunity_id=candidate.opportunity_id,
                stage=OpportunityStage.RESEARCH,
                reason="Demand witness found and composite score cleared research threshold",
                task_types=("full_research", "saturation_check", "wrapper_check"),
            )

        return OpportunityDecision(
            opportunity_id=candidate.opportunity_id,
            stage=OpportunityStage.WATCHLIST,
            reason="Demand exists but score or budget did not clear research threshold",
        )
