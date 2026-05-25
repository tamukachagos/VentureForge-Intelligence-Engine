from datetime import datetime, timezone
from dataclasses import replace

from ai_research_stack.config import Settings
from ai_research_stack.repository import InMemoryRepository
from ai_research_stack.scheduler import connectors_from_settings, tick
from ai_research_stack.sources import PaidSearchConnector
from ai_research_stack.sources import SourceFinding
from ai_research_stack.tasks import TaskLeaser


class OneFindingConnector:
    name = "one"

    def collect(self):
        return [
            SourceFinding(
                source="one",
                url="https://example.com/frontier",
                title="New agent capability",
                text="New capability affects business workflows.",
                collected_at="2026-05-24T12:00:00Z",
            )
        ]


def test_scheduler_tick_runs_source_ingestion_and_daily_digest():
    repo = InMemoryRepository()
    leaser = TaskLeaser(repo)
    now = datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc)

    tick(leaser, now, repository=repo, connectors=[OneFindingConnector()])

    task_types = {task.task_type for task in repo.tasks.values()}
    assert "frontier_tracker" in task_types
    assert "daily_digest" in task_types
    assert len(repo.ai_direction_signals) == 1


def test_connectors_from_settings_adds_paid_search_only_when_configured():
    settings = replace(
        Settings(),
        enable_hacker_news=False,
        enable_github_search=False,
        enable_rss=False,
        enable_paid_search=True,
        paid_search_endpoint_url="https://api.example.com/search",
        paid_search_api_key="secret",
    )

    connectors = connectors_from_settings(settings)

    assert len(connectors) == 1
    assert isinstance(connectors[0], PaidSearchConnector)
