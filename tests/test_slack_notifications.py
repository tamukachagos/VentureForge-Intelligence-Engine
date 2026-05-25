from datetime import datetime, timezone

from ai_research_stack.agents import AgentResult
from ai_research_stack.repository import InMemoryRepository
from ai_research_stack.results import ResultProcessor
from ai_research_stack.slack import SlackNotifier


def test_daily_digest_result_posts_to_slack_notifier():
    repo = InMemoryRepository()
    sent = []
    notifier = SlackNotifier(channel="C123", post=lambda payload: sent.append(payload))
    processor = ResultProcessor(repo, slack_notifier=notifier)

    processor.process(
        "daily_digest",
        {},
        AgentResult(
            status="complete",
            output={
                "digest": {
                    "summary": "Two opportunities advanced.",
                    "daily_llm_spend": 3.0,
                    "daily_llm_cap": 15.0,
                    "top_opportunities": [],
                }
            },
            cost_usd=0.25,
            input_tokens=100,
            output_tokens=100,
            model_used="openrouter/test",
        ),
        datetime(2026, 5, 24, tzinfo=timezone.utc),
    )

    assert sent
    assert "Daily Intelligence Digest" in sent[0]["text"]


def test_promoted_critic_result_posts_promotion_dossier():
    repo = InMemoryRepository()
    repo.upsert_opportunity(
        {
            "opportunity_id": "opp-1",
            "title": "Spreadsheet QA copilot",
            "thesis": "Finance teams need spreadsheet control automation.",
            "stage": "research",
        },
        datetime(2026, 5, 24, tzinfo=timezone.utc),
    )
    sent = []
    notifier = SlackNotifier(channel="C123", post=lambda payload: sent.append(payload))
    processor = ResultProcessor(repo, slack_notifier=notifier)

    processor.process(
        "claude_critic",
        {"opportunity_id": "opp-1"},
        AgentResult(
            status="complete",
            output={
                "opportunity_id": "opp-1",
                "title": "Spreadsheet QA copilot",
                "thesis": "Finance teams need spreadsheet control automation.",
                "recommendation": "promote",
                "score": 8.2,
                "confidence": 0.81,
                "fatal_flaws": [],
            },
            cost_usd=1.2,
            input_tokens=1000,
            output_tokens=900,
            model_used="claude-sonnet",
        ),
        datetime(2026, 5, 24, tzinfo=timezone.utc),
    )

    assert sent
    assert "Promotion Dossier" in sent[0]["text"]
    assert repo.opportunities["opp-1"]["stage"] == "dossier_ready"
