from __future__ import annotations

from datetime import datetime
from typing import Any

from ai_research_stack.domain import AgentTask, TaskStatus


class InMemoryRepository:
    def __init__(self) -> None:
        self.tasks: dict[str, AgentTask] = {}
        self.ai_direction_signals: dict[str, dict[str, Any]] = {}
        self.opportunities: dict[str, dict[str, Any]] = {}
        self.demand_witnesses: list[dict[str, Any]] = []
        self.evidence: list[dict[str, Any]] = []
        self.scores: list[dict[str, Any]] = []
        self.budget_events: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.approvals: list[dict[str, Any]] = []

    def find_open_task_by_idempotency_key(self, key: str) -> AgentTask | None:
        for task in self.tasks.values():
            if task.idempotency_key == key and task.status in {
                TaskStatus.PENDING,
                TaskStatus.LEASED,
                TaskStatus.FAILED,
            }:
                return task
        return None

    def add_task(self, task: AgentTask, now: datetime) -> str:
        task.created_at = now
        task.updated_at = now
        self.tasks[task.task_id] = task
        return task.task_id

    def get_task(self, task_id: str) -> AgentTask:
        return self.tasks[task_id]

    def claim_next_task(self, worker_id: str, lease_until: datetime, now: datetime) -> AgentTask | None:
        candidates = sorted(
            self.tasks.values(),
            key=lambda task: task.created_at or now,
        )
        for task in candidates:
            lease_expired = task.lease_expires_at is not None and task.lease_expires_at <= now
            if task.status in {TaskStatus.PENDING, TaskStatus.FAILED} or (
                task.status == TaskStatus.LEASED and lease_expired
            ):
                task.status = TaskStatus.LEASED
                task.lease_holder = worker_id
                task.lease_expires_at = lease_until
                task.attempts += 1
                task.updated_at = now
                return task
        return None

    def complete_task(self, task_id: str, result: dict, now: datetime) -> None:
        task = self.tasks[task_id]
        task.status = TaskStatus.COMPLETE
        task.result = result
        task.lease_holder = None
        task.lease_expires_at = None
        task.updated_at = now

    def fail_task(self, task_id: str, error: str, now: datetime, max_attempts: int) -> None:
        task = self.tasks[task_id]
        task.last_error = error
        task.lease_holder = None
        task.lease_expires_at = None
        task.status = TaskStatus.DEAD if task.attempts >= max_attempts else TaskStatus.FAILED
        task.updated_at = now

    def list_tasks(self, limit: int = 100) -> list[dict[str, Any]]:
        return [
            {
                "id": task.task_id,
                "type": task.task_type,
                "status": task.status.value,
                "attempts": task.attempts,
                "updated_at": task.updated_at,
            }
            for task in sorted(
                self.tasks.values(),
                key=lambda item: item.updated_at or item.created_at or datetime.min,
                reverse=True,
            )[:limit]
        ]

    def list_opportunities(self) -> list[dict[str, Any]]:
        return [
            {
                "opportunity_id": opp["opportunity_id"],
                "title": opp["title"],
                "stage": opp["stage"],
                "score": opp.get("composite_score"),
                "confidence": opp.get("confidence"),
                "demand": opp.get("demand", ""),
            }
            for opp in self.opportunities.values()
        ]

    def upsert_ai_direction_signal(self, signal: dict[str, Any], now: datetime) -> None:
        signal = dict(signal)
        signal.setdefault("discovered_at", now)
        self.ai_direction_signals[signal["signal_id"]] = signal

    def upsert_opportunity(self, opportunity: dict[str, Any], now: datetime) -> None:
        existing = self.opportunities.get(opportunity["opportunity_id"], {})
        merged = {
            **existing,
            **opportunity,
            "updated_at": now,
            "created_at": existing.get("created_at", now),
        }
        self.opportunities[opportunity["opportunity_id"]] = merged

    def add_demand_witness(self, witness: dict[str, Any], now: datetime) -> None:
        witness = dict(witness)
        witness.setdefault("collected_at", now)
        self.demand_witnesses.append(witness)

    def add_evidence(self, evidence: dict[str, Any], now: datetime) -> None:
        evidence = dict(evidence)
        evidence.setdefault("collected_at", now)
        self.evidence.append(evidence)

    def add_score(self, score: dict[str, Any], now: datetime) -> None:
        score = dict(score)
        score.setdefault("created_at", now)
        self.scores.append(score)

    def update_opportunity_score(
        self,
        opportunity_id: str,
        composite_score: float,
        confidence: float,
        now: datetime,
    ) -> None:
        opportunity = self.opportunities[opportunity_id]
        opportunity["composite_score"] = composite_score
        opportunity["confidence"] = confidence
        opportunity["updated_at"] = now

    def update_opportunity_stage(self, opportunity_id: str, stage: str, now: datetime) -> None:
        opportunity = self.opportunities[opportunity_id]
        opportunity["stage"] = stage
        opportunity["updated_at"] = now

    def append_budget_event(self, event: dict[str, Any], now: datetime) -> None:
        event = dict(event)
        event.setdefault("created_at", now)
        self.budget_events.append(event)

    def monthly_budget_spend(self, budget_type: str, now: datetime) -> float:
        return sum(
            float(event["amount_usd"])
            for event in self.budget_events
            if event["budget_type"] == budget_type
            and event.get("created_at", now).year == now.year
            and event.get("created_at", now).month == now.month
        )

    def append_event(self, event: dict[str, Any], now: datetime) -> None:
        event = dict(event)
        event.setdefault("created_at", now)
        self.events.append(event)

    def add_approval(self, approval: dict[str, Any], now: datetime) -> None:
        approval = dict(approval)
        approval.setdefault("created_at", now)
        self.approvals.append(approval)
