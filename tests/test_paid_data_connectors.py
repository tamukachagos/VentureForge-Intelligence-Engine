from datetime import datetime, timezone

from ai_research_stack.budget import BudgetGovernor, BudgetPolicy
from ai_research_stack.repository import InMemoryRepository
from ai_research_stack.source_ingestion import SourceIngestionService
from ai_research_stack.sources import PaidSearchConnector, SourceFinding
from ai_research_stack.tasks import TaskLeaser


class PaidConnector:
    name = "paid"
    estimated_cost_usd = 2.0

    def collect(self):
        return [
            SourceFinding(
                source="paid",
                url="https://example.com/result",
                title="Paid search result",
                text="Paid search found a demand signal.",
                collected_at="2026-05-24T12:00:00Z",
                cost_usd=2.0,
                confidence=0.75,
            )
        ]


def test_paid_connector_runs_when_monthly_data_budget_allows():
    repo = InMemoryRepository()
    leaser = TaskLeaser(repo)
    service = SourceIngestionService(
        repo,
        leaser,
        connectors=[PaidConnector()],
        budget_governor=BudgetGovernor(BudgetPolicy(monthly_data_cap=50.0)),
    )

    summary = service.ingest(datetime(2026, 5, 24, tzinfo=timezone.utc))

    assert summary.findings_collected == 1
    assert repo.budget_events[0]["budget_type"] == "paid_data"
    assert repo.budget_events[0]["amount_usd"] == 2.0


def test_paid_connector_is_skipped_when_monthly_data_budget_would_be_exceeded():
    repo = InMemoryRepository()
    repo.append_budget_event(
        {
            "event_id": "spent",
            "opportunity_id": None,
            "budget_type": "paid_data",
            "amount_usd": 49.0,
            "reason": "prior paid data",
        },
        datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    leaser = TaskLeaser(repo)
    service = SourceIngestionService(
        repo,
        leaser,
        connectors=[PaidConnector()],
        budget_governor=BudgetGovernor(BudgetPolicy(monthly_data_cap=50.0)),
    )

    summary = service.ingest(datetime(2026, 5, 24, tzinfo=timezone.utc))

    assert summary.findings_collected == 0
    assert summary.skipped_for_budget == 1
    assert any(event["event_type"] == "source_connector_budget_skipped" for event in repo.events)


def test_paid_search_connector_maps_generic_search_api_results():
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "results": [
                    {
                        "title": "AI workflow complaints",
                        "url": "https://example.com/complaints",
                        "content": "Operators complain about broken handoffs.",
                    }
                ]
            }

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, headers, json):
            return Response()

    connector = PaidSearchConnector(
        name="paid_search",
        endpoint_url="https://api.example.com/search",
        api_key="secret",
        query="AI agent workflow complaints",
        estimated_cost_usd=0.25,
        client_factory=lambda timeout: Client(),
    )

    findings = connector.collect()

    assert findings[0].source == "paid_search"
    assert findings[0].url == "https://example.com/complaints"
    assert findings[0].cost_usd == 0.25
