from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetPolicy:
    daily_llm_cap: float = 15.0
    monthly_data_cap: float = 50.0
    per_opportunity_auto_cap: float = 3.0
    spend_notice_threshold: float = 1.0
    ask_tracker_query_cap: float = 0.10
    ask_tracker_daily_cap: float = 1.50


@dataclass(frozen=True)
class BudgetSnapshot:
    daily_llm_spend: float
    monthly_data_spend: float
    ask_tracker_daily_spend: float


@dataclass(frozen=True)
class BudgetDecision:
    allowed: bool
    reason: str
    requires_owner_approval: bool = False
    notify_owner: bool = False


class BudgetGovernor:
    def __init__(self, policy: BudgetPolicy) -> None:
        self.policy = policy

    def authorize_llm_spend(
        self,
        snapshot: BudgetSnapshot,
        amount: float,
        opportunity_lifetime_spend: float,
    ) -> BudgetDecision:
        if snapshot.daily_llm_spend + amount > self.policy.daily_llm_cap:
            return BudgetDecision(False, "Requested spend would exceed daily LLM cap")

        if opportunity_lifetime_spend + amount > self.policy.per_opportunity_auto_cap:
            return BudgetDecision(
                False,
                "Requested spend would exceed per-opportunity automatic cap",
                requires_owner_approval=True,
            )

        crosses_notice = (
            opportunity_lifetime_spend < self.policy.spend_notice_threshold
            <= opportunity_lifetime_spend + amount
        )
        return BudgetDecision(True, "Spend authorized", notify_owner=crosses_notice)

    def authorize_paid_data_spend(self, snapshot: BudgetSnapshot, amount: float) -> BudgetDecision:
        if snapshot.monthly_data_spend + amount > self.policy.monthly_data_cap:
            return BudgetDecision(
                False,
                "Requested spend would exceed monthly paid data cap",
                requires_owner_approval=True,
            )
        return BudgetDecision(True, "Paid data spend authorized")

    def authorize_ask_tracker(
        self,
        snapshot: BudgetSnapshot,
        estimated_cost: float,
    ) -> BudgetDecision:
        if estimated_cost > self.policy.ask_tracker_query_cap:
            return BudgetDecision(False, "Requested ask-tracker query exceeds per-query cap")
        if snapshot.ask_tracker_daily_spend + estimated_cost > self.policy.ask_tracker_daily_cap:
            return BudgetDecision(False, "Requested query would exceed ask-tracker daily cap")
        return BudgetDecision(True, "Ask-tracker query authorized")

