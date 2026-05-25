from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

from ai_research_stack.budget import BudgetGovernor, BudgetPolicy, BudgetSnapshot
from ai_research_stack.sources import SourceConnector, SourceFinding
from ai_research_stack.tasks import TaskLeaser


@dataclass(frozen=True)
class IngestionSummary:
    sources_run: int
    findings_collected: int
    signals_persisted: int
    failures: int
    skipped_for_budget: int = 0


class SourceIngestionService:
    def __init__(
        self,
        repository: Any,
        leaser: TaskLeaser,
        connectors: list[SourceConnector],
        budget_governor: BudgetGovernor | None = None,
        max_findings_per_task: int = 25,
    ) -> None:
        self.repository = repository
        self.leaser = leaser
        self.connectors = connectors
        self.budget_governor = budget_governor or BudgetGovernor(BudgetPolicy())
        self.max_findings_per_task = max_findings_per_task

    def ingest(self, now: datetime) -> IngestionSummary:
        findings: list[SourceFinding] = []
        failures = 0
        skipped_for_budget = 0
        for connector in self.connectors:
            estimated_cost = float(getattr(connector, "estimated_cost_usd", 0.0) or 0.0)
            if estimated_cost > 0:
                monthly_spend = self.repository.monthly_budget_spend("paid_data", now)
                decision = self.budget_governor.authorize_paid_data_spend(
                    BudgetSnapshot(
                        daily_llm_spend=0.0,
                        monthly_data_spend=monthly_spend,
                        ask_tracker_daily_spend=0.0,
                    ),
                    estimated_cost,
                )
                if not decision.allowed:
                    skipped_for_budget += 1
                    self.repository.append_event(
                        {
                            "event_id": str(uuid4()),
                            "entity_type": "source_connector",
                            "entity_id": connector.name,
                            "event_type": "source_connector_budget_skipped",
                            "payload": {"reason": decision.reason, "estimated_cost": estimated_cost},
                        },
                        now,
                    )
                    continue
            try:
                collected = connector.collect()
                findings.extend(collected)
                if estimated_cost > 0:
                    self.repository.append_budget_event(
                        {
                            "event_id": str(uuid4()),
                            "opportunity_id": None,
                            "budget_type": "paid_data",
                            "amount_usd": sum(item.cost_usd for item in collected) or estimated_cost,
                            "reason": f"source connector {connector.name}",
                        },
                        now,
                    )
            except Exception as exc:  # pragma: no cover - exact connector failures vary
                failures += 1
                self.repository.append_event(
                    {
                        "event_id": str(uuid4()),
                        "entity_type": "source_connector",
                        "entity_id": connector.name,
                        "event_type": "source_connector_failed",
                        "payload": {"error": repr(exc)},
                    },
                    now,
                )

        unique_findings = _dedupe_findings(findings)
        for finding in unique_findings:
            self.repository.upsert_ai_direction_signal(_signal_from_finding(finding), now)

        if unique_findings:
            hour_key = now.strftime("%Y-%m-%dT%H")
            self.leaser.enqueue(
                "frontier_tracker",
                {
                    "source_batch": f"ingested:{hour_key}",
                    "scheduled_at": now.isoformat(),
                    "findings": [
                        asdict(finding) for finding in unique_findings[: self.max_findings_per_task]
                    ],
                },
                f"frontier-tracker:ingested:{hour_key}",
                now,
            )

        self.repository.append_event(
            {
                "event_id": str(uuid4()),
                "entity_type": "source_ingestion",
                "entity_id": now.strftime("%Y-%m-%dT%H"),
                "event_type": "source_ingestion_completed",
                "payload": {
                    "sources_run": len(self.connectors),
                    "findings_collected": len(findings),
                    "signals_persisted": len(unique_findings),
                    "failures": failures,
                    "skipped_for_budget": skipped_for_budget,
                },
            },
            now,
        )
        return IngestionSummary(
            sources_run=len(self.connectors),
            findings_collected=len(findings),
            signals_persisted=len(unique_findings),
            failures=failures,
            skipped_for_budget=skipped_for_budget,
        )


def _dedupe_findings(findings: list[SourceFinding]) -> list[SourceFinding]:
    seen: set[str] = set()
    unique: list[SourceFinding] = []
    for finding in findings:
        key = _finding_key(finding)
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return unique


def _finding_key(finding: SourceFinding) -> str:
    identity = finding.url.strip().lower() or f"{finding.source}:{finding.title.strip().lower()}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _signal_from_finding(finding: SourceFinding) -> dict[str, Any]:
    signal_id = f"source-{_finding_key(finding)[:24]}"
    return {
        "signal_id": signal_id,
        "source": finding.source,
        "title": finding.title,
        "url": finding.url,
        "summary": finding.text,
        "raw_payload": asdict(finding),
    }
