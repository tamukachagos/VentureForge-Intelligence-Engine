from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from ai_research_stack.domain import AgentTask, TaskStatus


class PostgresRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def connect(self) -> psycopg.Connection:
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def initialize_schema(self) -> None:
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        with self.connect() as conn:
            conn.execute(schema)

    def find_open_task_by_idempotency_key(self, key: str) -> AgentTask | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM tasks
                WHERE idempotency_key = %s
                  AND status IN ('pending', 'leased', 'failed')
                LIMIT 1
                """,
                (key,),
            ).fetchone()
        return _task_from_row(row) if row else None

    def add_task(self, task: AgentTask, now: datetime) -> str:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO tasks (
                    task_id, task_type, payload, idempotency_key, status,
                    attempts, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (idempotency_key) DO NOTHING
                """,
                (
                    task.task_id,
                    task.task_type,
                    psycopg.types.json.Jsonb(task.payload),
                    task.idempotency_key,
                    task.status.value,
                    task.attempts,
                    now,
                    now,
                ),
            )
        existing = self.find_open_task_by_idempotency_key(task.idempotency_key)
        return existing.task_id if existing else task.task_id

    def get_task(self, task_id: str) -> AgentTask:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id = %s", (task_id,)).fetchone()
        if row is None:
            raise KeyError(task_id)
        return _task_from_row(row)

    def claim_next_task(self, worker_id: str, lease_until: datetime, now: datetime) -> AgentTask | None:
        with self.connect() as conn:
            with conn.transaction():
                row = conn.execute(
                    """
                    SELECT * FROM tasks
                    WHERE (
                        status IN ('pending', 'failed')
                        OR (status = 'leased' AND lease_expires_at <= %s)
                    )
                    ORDER BY created_at ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                    """,
                    (now,),
                ).fetchone()
                if row is None:
                    return None
                updated = conn.execute(
                    """
                    UPDATE tasks
                    SET status = 'leased',
                        lease_holder = %s,
                        lease_expires_at = %s,
                        attempts = attempts + 1,
                        updated_at = %s
                    WHERE task_id = %s
                    RETURNING *
                    """,
                    (worker_id, lease_until, now, row["task_id"]),
                ).fetchone()
        return _task_from_row(updated) if updated else None

    def complete_task(self, task_id: str, result: dict[str, Any], now: datetime) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = 'complete',
                    result = %s,
                    lease_holder = NULL,
                    lease_expires_at = NULL,
                    updated_at = %s
                WHERE task_id = %s
                """,
                (psycopg.types.json.Jsonb(result), now, task_id),
            )

    def fail_task(self, task_id: str, error: str, now: datetime, max_attempts: int) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = CASE WHEN attempts >= %s THEN 'dead' ELSE 'failed' END,
                    last_error = %s,
                    lease_holder = NULL,
                    lease_expires_at = NULL,
                    updated_at = %s
                WHERE task_id = %s
                """,
                (max_attempts, error, now, task_id),
            )

    def list_opportunities(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return list(
                conn.execute(
                    """
                    SELECT opportunity_id, title, stage, composite_score AS score, confidence, thesis AS demand
                    FROM opportunities
                    ORDER BY updated_at DESC
                    LIMIT 100
                    """
                ).fetchall()
            )

    def list_tasks(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return list(
                conn.execute(
                    """
                    SELECT task_id AS id, task_type AS type, status, attempts, updated_at
                    FROM tasks
                    ORDER BY updated_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                ).fetchall()
            )

    def upsert_ai_direction_signal(self, signal: dict[str, Any], now: datetime) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO ai_direction_signals (
                    signal_id, source, title, url, summary, raw_payload, discovered_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (signal_id) DO UPDATE
                SET source = EXCLUDED.source,
                    title = EXCLUDED.title,
                    url = EXCLUDED.url,
                    summary = EXCLUDED.summary,
                    raw_payload = EXCLUDED.raw_payload
                """,
                (
                    signal["signal_id"],
                    signal["source"],
                    signal["title"],
                    signal["url"],
                    signal["summary"],
                    psycopg.types.json.Jsonb(signal.get("raw_payload", {})),
                    now,
                ),
            )

    def upsert_opportunity(self, opportunity: dict[str, Any], now: datetime) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO opportunities (
                    opportunity_id, title, thesis, stage, legal_ok, builder_fit_ok,
                    created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (opportunity_id) DO UPDATE
                SET title = EXCLUDED.title,
                    thesis = EXCLUDED.thesis,
                    stage = EXCLUDED.stage,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    opportunity["opportunity_id"],
                    opportunity["title"],
                    opportunity["thesis"],
                    opportunity["stage"],
                    opportunity.get("legal_ok", True),
                    opportunity.get("builder_fit_ok", True),
                    now,
                    now,
                ),
            )

    def add_demand_witness(self, witness: dict[str, Any], now: datetime) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO demand_witnesses (
                    witness_id, opportunity_id, witness_type, source, excerpt,
                    strength, is_proxy, collected_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (witness_id) DO NOTHING
                """,
                (
                    witness["witness_id"],
                    witness["opportunity_id"],
                    witness["witness_type"],
                    witness["source"],
                    witness["excerpt"],
                    witness["strength"],
                    witness["is_proxy"],
                    now,
                ),
            )

    def add_evidence(self, evidence: dict[str, Any], now: datetime) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO evidence (
                    evidence_id, opportunity_id, source, title, excerpt, strength, collected_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (evidence_id) DO NOTHING
                """,
                (
                    evidence["evidence_id"],
                    evidence["opportunity_id"],
                    evidence["source"],
                    evidence["title"],
                    evidence["excerpt"],
                    evidence["strength"],
                    now,
                ),
            )

    def add_score(self, score: dict[str, Any], now: datetime) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO scores (
                    score_id, opportunity_id, dimensions, composite_score, confidence, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (score_id) DO NOTHING
                """,
                (
                    score["score_id"],
                    score["opportunity_id"],
                    psycopg.types.json.Jsonb(score["dimensions"]),
                    score["composite_score"],
                    score["confidence"],
                    now,
                ),
            )

    def update_opportunity_score(
        self,
        opportunity_id: str,
        composite_score: float,
        confidence: float,
        now: datetime,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE opportunities
                SET composite_score = %s,
                    confidence = %s,
                    updated_at = %s
                WHERE opportunity_id = %s
                """,
                (composite_score, confidence, now, opportunity_id),
            )

    def update_opportunity_stage(self, opportunity_id: str, stage: str, now: datetime) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE opportunities
                SET stage = %s,
                    updated_at = %s
                WHERE opportunity_id = %s
                """,
                (stage, now, opportunity_id),
            )

    def append_budget_event(self, event: dict[str, Any], now: datetime) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO budget_events (
                    event_id, opportunity_id, budget_type, amount_usd, reason, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    event["event_id"],
                    event.get("opportunity_id"),
                    event["budget_type"],
                    event["amount_usd"],
                    event["reason"],
                    now,
                ),
            )

    def monthly_budget_spend(self, budget_type: str, now: datetime) -> float:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(amount_usd), 0) AS total
                FROM budget_events
                WHERE budget_type = %s
                  AND date_trunc('month', created_at) = date_trunc('month', %s::timestamptz)
                """,
                (budget_type, now),
            ).fetchone()
        return float(row["total"])

    def append_event(self, event: dict[str, Any], now: datetime) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO events (
                    event_id, entity_type, entity_id, event_type, payload, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    event["event_id"],
                    event["entity_type"],
                    event["entity_id"],
                    event["event_type"],
                    psycopg.types.json.Jsonb(event.get("payload", {})),
                    now,
                ),
            )

    def add_approval(self, approval: dict[str, Any], now: datetime) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO approvals (
                    approval_id, opportunity_id, approval_type, status,
                    requested_reason, decided_by, decided_at, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    approval["approval_id"],
                    approval.get("opportunity_id"),
                    approval["approval_type"],
                    approval["status"],
                    approval["requested_reason"],
                    approval.get("decided_by"),
                    approval.get("decided_at"),
                    now,
                ),
            )


def _task_from_row(row: dict[str, Any]) -> AgentTask:
    return AgentTask(
        task_id=row["task_id"],
        task_type=row["task_type"],
        payload=row["payload"],
        idempotency_key=row["idempotency_key"],
        status=TaskStatus(row["status"]),
        attempts=row["attempts"],
        lease_holder=row["lease_holder"],
        lease_expires_at=row["lease_expires_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        last_error=row["last_error"],
        result=row["result"],
    )
