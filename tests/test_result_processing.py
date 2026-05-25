from datetime import datetime, timezone

from ai_research_stack.agents import AgentResult
from ai_research_stack.domain import OpportunityStage
from ai_research_stack.repository import InMemoryRepository
from ai_research_stack.results import ResultProcessor


NOW = datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc)


def test_frontier_tracker_result_persists_signals_and_opportunities():
    repo = InMemoryRepository()
    processor = ResultProcessor(repo)

    result = AgentResult(
        status="complete",
        output={
            "signals": [
                {
                    "signal_id": "sig-1",
                    "source": "ai_lab_blog",
                    "title": "Tool-use agents can inspect spreadsheets",
                    "url": "https://example.com/tool-agents",
                    "summary": "New agent capability makes spreadsheet QA easier.",
                    "opportunities": [
                        {
                            "opportunity_id": "opp-1",
                            "title": "Spreadsheet QA copilot for finance teams",
                            "thesis": "Finance teams waste review cycles checking linked spreadsheets.",
                            "stage": "first_pass",
                        }
                    ],
                }
            ]
        },
        cost_usd=0.14,
        input_tokens=1200,
        output_tokens=500,
        model_used="openrouter/test",
    )

    processor.process("frontier_tracker", {"source_batch": "frontier"}, result, NOW)

    assert repo.ai_direction_signals["sig-1"]["title"] == "Tool-use agents can inspect spreadsheets"
    assert repo.opportunities["opp-1"]["stage"] == OpportunityStage.FIRST_PASS.value
    assert repo.budget_events[0]["amount_usd"] == 0.14
    assert repo.events[-1]["event_type"] == "task_result_processed"


def test_research_result_persists_demand_witnesses_evidence_and_score():
    repo = InMemoryRepository()
    repo.upsert_opportunity(
        {
            "opportunity_id": "opp-1",
            "title": "Spreadsheet QA copilot",
            "thesis": "Finance review workflow",
            "stage": "research",
        },
        NOW,
    )
    processor = ResultProcessor(repo)

    result = AgentResult(
        status="complete",
        output={
            "opportunity_id": "opp-1",
            "demand_witnesses": [
                {
                    "witness_type": "buyer_complaint",
                    "source": "https://example.com/forum",
                    "excerpt": "I spend every Friday checking broken formulas.",
                    "strength": 8.5,
                    "is_proxy": False,
                }
            ],
            "evidence": [
                {
                    "source": "https://example.com/job",
                    "title": "Spreadsheet controls analyst",
                    "excerpt": "Hiring for spreadsheet controls automation.",
                    "strength": 7.0,
                }
            ],
            "score": {
                "dimensions": {
                    "demand_witness_strength": 8.5,
                    "capability_timing": 8.0,
                    "speed_to_mvp": 7.0,
                    "distribution_edge": 6.0,
                    "defensibility_window": 6.0,
                    "wedge_to_platform": 7.0,
                    "cash_flow_path": 7.0,
                    "novelty": 7.0,
                },
                "confidence": 0.72,
            },
        },
        cost_usd=0.88,
        input_tokens=4000,
        output_tokens=1200,
        model_used="openrouter/test",
    )

    processor.process("full_research", {"opportunity_id": "opp-1"}, result, NOW)

    assert repo.demand_witnesses[0]["witness_type"] == "buyer_complaint"
    assert repo.evidence[0]["title"] == "Spreadsheet controls analyst"
    assert repo.scores[0]["composite_score"] > 0
    assert repo.opportunities["opp-1"]["composite_score"] == repo.scores[0]["composite_score"]


def test_result_processor_parses_raw_json_wrapped_in_text():
    repo = InMemoryRepository()
    processor = ResultProcessor(repo)
    result = AgentResult(
        status="complete",
        output={
            "raw_text": """
Here is the result:
```json
{"signals":[{"signal_id":"sig-json","source":"rss","title":"New model","url":"https://example.com","summary":"Capability change"}]}
```
"""
        },
        cost_usd=0.05,
        input_tokens=10,
        output_tokens=10,
        model_used="openrouter/test",
    )

    processor.process("frontier_tracker", {}, result, NOW)

    assert "sig-json" in repo.ai_direction_signals
