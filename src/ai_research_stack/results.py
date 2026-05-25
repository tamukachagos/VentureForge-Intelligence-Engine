from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any
from uuid import uuid4

from ai_research_stack.agents import AgentResult
from ai_research_stack.scoring import ScoreDimensions, calculate_composite_score


class ResultProcessor:
    def __init__(self, repository: Any, slack_notifier: Any | None = None) -> None:
        self.repository = repository
        self.slack_notifier = slack_notifier

    def process(
        self,
        task_type: str,
        payload: dict[str, Any],
        result: AgentResult,
        now: datetime,
    ) -> None:
        parsed = parse_agent_output(result.output)
        self._record_budget(task_type, payload, result, now)

        if task_type == "frontier_tracker":
            self._process_frontier_tracker(parsed, now)
        elif task_type == "full_research":
            opportunity_id = str(parsed.get("opportunity_id") or payload.get("opportunity_id") or "")
            if opportunity_id:
                self._process_research(opportunity_id, parsed, now)
        elif task_type == "claude_critic":
            self._process_critic(parsed, payload, now)
        elif task_type == "daily_digest":
            self._process_daily_digest(parsed)

        self.repository.append_event(
            {
                "event_id": str(uuid4()),
                "entity_type": "task",
                "entity_id": str(payload.get("task_id", task_type)),
                "event_type": "task_result_processed",
                "payload": {
                    "task_type": task_type,
                    "model_used": result.model_used,
                    "cost_usd": result.cost_usd,
                },
            },
            now,
        )

    def _record_budget(
        self,
        task_type: str,
        payload: dict[str, Any],
        result: AgentResult,
        now: datetime,
    ) -> None:
        if result.cost_usd <= 0:
            return
        self.repository.append_budget_event(
            {
                "event_id": str(uuid4()),
                "opportunity_id": payload.get("opportunity_id"),
                "budget_type": "llm",
                "amount_usd": result.cost_usd,
                "reason": f"{task_type} via {result.model_used}",
            },
            now,
        )

    def _process_frontier_tracker(self, parsed: dict[str, Any], now: datetime) -> None:
        for signal in _as_list(parsed.get("signals")):
            signal_id = str(signal.get("signal_id") or uuid4())
            self.repository.upsert_ai_direction_signal(
                {
                    "signal_id": signal_id,
                    "source": str(signal.get("source") or "unknown"),
                    "title": str(signal.get("title") or "Untitled signal"),
                    "url": str(signal.get("url") or ""),
                    "summary": str(signal.get("summary") or signal.get("text") or ""),
                    "raw_payload": signal,
                },
                now,
            )
            for opportunity in _as_list(signal.get("opportunities")):
                opportunity_id = str(opportunity.get("opportunity_id") or uuid4())
                self.repository.upsert_opportunity(
                    {
                        "opportunity_id": opportunity_id,
                        "title": str(opportunity.get("title") or "Untitled opportunity"),
                        "thesis": str(opportunity.get("thesis") or signal.get("summary") or ""),
                        "stage": str(opportunity.get("stage") or "first_pass"),
                    },
                    now,
                )

    def _process_research(
        self,
        opportunity_id: str,
        parsed: dict[str, Any],
        now: datetime,
    ) -> None:
        for witness in _as_list(parsed.get("demand_witnesses")):
            self.repository.add_demand_witness(
                {
                    "witness_id": str(witness.get("witness_id") or uuid4()),
                    "opportunity_id": opportunity_id,
                    "witness_type": str(witness.get("witness_type") or "role_based_need"),
                    "source": str(witness.get("source") or ""),
                    "excerpt": str(witness.get("excerpt") or ""),
                    "strength": float(witness.get("strength") or 0.0),
                    "is_proxy": bool(witness.get("is_proxy", False)),
                },
                now,
            )

        for evidence in _as_list(parsed.get("evidence") or parsed.get("findings")):
            self.repository.add_evidence(
                {
                    "evidence_id": str(evidence.get("evidence_id") or uuid4()),
                    "opportunity_id": opportunity_id,
                    "source": str(evidence.get("source") or ""),
                    "title": str(evidence.get("title") or "Evidence"),
                    "excerpt": str(evidence.get("excerpt") or evidence.get("text") or ""),
                    "strength": float(evidence.get("strength") or 0.0),
                },
                now,
            )

        score = parsed.get("score")
        if isinstance(score, dict) and isinstance(score.get("dimensions"), dict):
            dimensions = ScoreDimensions(**score["dimensions"])
            composite = calculate_composite_score(dimensions)
            confidence = float(score.get("confidence") or 0.0)
            self.repository.add_score(
                {
                    "score_id": str(score.get("score_id") or uuid4()),
                    "opportunity_id": opportunity_id,
                    "dimensions": score["dimensions"],
                    "composite_score": composite,
                    "confidence": confidence,
                },
                now,
            )
            self.repository.update_opportunity_score(opportunity_id, composite, confidence, now)

    def _process_critic(
        self,
        parsed: dict[str, Any],
        payload: dict[str, Any],
        now: datetime,
    ) -> None:
        opportunity_id = str(parsed.get("opportunity_id") or payload.get("opportunity_id") or "")
        if not opportunity_id:
            return
        recommendation = str(parsed.get("recommendation") or "research_more")
        stage = {
            "promote": "dossier_ready",
            "research_more": "research",
            "watchlist": "watchlist",
            "kill": "rejected",
        }.get(recommendation, "research")
        self.repository.update_opportunity_stage(opportunity_id, stage, now)
        if recommendation == "promote" and self.slack_notifier is not None:
            dossier = {
                **parsed,
                "opportunity_id": opportunity_id,
            }
            self.slack_notifier.send_promotion_dossier(dossier)

    def _process_daily_digest(self, parsed: dict[str, Any]) -> None:
        if self.slack_notifier is None:
            return
        digest = parsed.get("digest") if isinstance(parsed.get("digest"), dict) else parsed
        self.slack_notifier.send_daily_digest(digest)


def parse_agent_output(output: dict[str, Any]) -> dict[str, Any]:
    if "raw_text" not in output:
        return output

    raw_text = str(output["raw_text"]).strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    candidate = fenced.group(1) if fenced else raw_text

    if not candidate.startswith("{"):
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end > start:
            candidate = candidate[start : end + 1]

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return {"raw_text": raw_text, "parse_error": "invalid_json"}
    return parsed if isinstance(parsed, dict) else {"items": parsed}


def _as_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
