from __future__ import annotations

from datetime import datetime, timedelta

from ai_research_stack.domain import AgentTask, TaskClaim
from ai_research_stack.repository import InMemoryRepository


class TaskLeaser:
    def __init__(
        self,
        repository: InMemoryRepository,
        lease_seconds: int = 60,
        max_attempts: int = 3,
    ) -> None:
        self.repository = repository
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts

    def enqueue(
        self,
        task_type: str,
        payload: dict,
        idempotency_key: str,
        now: datetime,
    ) -> str:
        existing = self.repository.find_open_task_by_idempotency_key(idempotency_key)
        if existing is not None:
            return existing.task_id
        return self.repository.add_task(
            AgentTask(task_type=task_type, payload=payload, idempotency_key=idempotency_key),
            now,
        )

    def claim_next(self, worker_id: str, now: datetime) -> TaskClaim | None:
        task = self.repository.claim_next_task(
            worker_id=worker_id,
            lease_until=now + timedelta(seconds=self.lease_seconds),
            now=now,
        )
        if task is None:
            return None
        return TaskClaim(
            task_id=task.task_id,
            task_type=task.task_type,
            payload=task.payload,
            lease_holder=worker_id,
            lease_expires_at=task.lease_expires_at,
            attempts=task.attempts,
        )

    def complete(self, task_id: str, result: dict, now: datetime) -> None:
        self.repository.complete_task(task_id, result, now)

    def fail(self, task_id: str, error: str, now: datetime) -> None:
        self.repository.fail_task(task_id, error, now, self.max_attempts)

