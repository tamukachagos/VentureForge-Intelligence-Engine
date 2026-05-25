from datetime import datetime, timezone

from ai_research_stack.repository import InMemoryRepository
from ai_research_stack.source_ingestion import SourceIngestionService
from ai_research_stack.sources import RSSConnector, SourceFinding
from ai_research_stack.tasks import TaskLeaser


class StaticConnector:
    name = "static"

    def collect(self):
        return [
            SourceFinding(
                source="static",
                url="https://example.com/a",
                title="Agent spreadsheet capability",
                text="Agents can inspect linked spreadsheet workflows.",
                collected_at="2026-05-24T12:00:00Z",
                confidence=0.8,
            ),
            SourceFinding(
                source="static",
                url="https://example.com/a",
                title="Agent spreadsheet capability duplicate",
                text="Duplicate should not create another signal.",
                collected_at="2026-05-24T12:01:00Z",
                confidence=0.7,
            ),
        ]


def test_source_ingestion_persists_findings_and_enqueues_frontier_task():
    repo = InMemoryRepository()
    leaser = TaskLeaser(repo)
    service = SourceIngestionService(repo, leaser, connectors=[StaticConnector()])
    now = datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc)

    summary = service.ingest(now)

    assert summary.sources_run == 1
    assert summary.findings_collected == 2
    assert summary.signals_persisted == 1
    assert len(repo.ai_direction_signals) == 1
    task = next(iter(repo.tasks.values()))
    assert task.task_type == "frontier_tracker"
    assert task.payload["findings"][0]["url"] == "https://example.com/a"


def test_source_ingestion_records_connector_failures_as_events():
    class BrokenConnector:
        name = "broken"

        def collect(self):
            raise RuntimeError("source unavailable")

    repo = InMemoryRepository()
    leaser = TaskLeaser(repo)
    service = SourceIngestionService(repo, leaser, connectors=[BrokenConnector()])
    now = datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc)

    summary = service.ingest(now)

    assert summary.sources_run == 1
    assert summary.failures == 1
    assert any(event["event_type"] == "source_connector_failed" for event in repo.events)


def test_rss_connector_parses_atom_entries():
    class Response:
        text = """<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Frontier agents update</title>
            <link href="https://example.com/atom-entry" />
            <summary>Agents learned a new workflow.</summary>
            <updated>2026-05-24T12:00:00Z</updated>
          </entry>
        </feed>
        """

        def raise_for_status(self):
            return None

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, url):
            return Response()

    connector = RSSConnector(["https://example.com/feed"], client_factory=lambda timeout: Client())

    findings = connector.collect()

    assert findings[0].title == "Frontier agents update"
    assert findings[0].url == "https://example.com/atom-entry"
