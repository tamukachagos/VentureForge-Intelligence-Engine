from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone

from ai_research_stack.config import load_settings
from ai_research_stack.postgres import PostgresRepository
from ai_research_stack.source_ingestion import SourceIngestionService
from ai_research_stack.sources import (
    GitHubSearchConnector,
    HackerNewsConnector,
    PaidSearchConnector,
    RSSConnector,
    SourceConnector,
)
from ai_research_stack.tasks import TaskLeaser


def tick(
    leaser: TaskLeaser,
    now: datetime,
    repository=None,
    connectors: list[SourceConnector] | None = None,
) -> None:
    date_key = now.strftime("%Y-%m-%d")
    if repository is not None and connectors is not None:
        SourceIngestionService(repository, leaser, connectors).ingest(now)
    leaser.enqueue(
        "daily_digest",
        {"window": "daily", "scheduled_at": now.isoformat()},
        f"daily-digest:{date_key}",
        now,
    )


def run_scheduler(interval_seconds: float = 300.0) -> None:
    settings = load_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required for scheduler")
    repository = PostgresRepository(settings.database_url)
    leaser = TaskLeaser(repository)
    connectors = connectors_from_settings(settings)
    while True:
        tick(leaser, datetime.now(timezone.utc), repository=repository, connectors=connectors)
        time.sleep(interval_seconds)


def connectors_from_settings(settings) -> list[SourceConnector]:
    connectors: list[SourceConnector] = []
    if settings.enable_hacker_news:
        connectors.append(HackerNewsConnector())
    if settings.enable_github_search:
        connectors.append(
            GitHubSearchConnector(token=settings.github_token, query=settings.github_search_query)
        )
    if settings.enable_rss:
        feed_urls = [
            item.strip()
            for item in settings.rss_feed_urls.split(",")
            if item.strip()
        ] or default_ai_rss_feeds()
        connectors.append(RSSConnector(feed_urls))
    if (
        settings.enable_paid_search
        and settings.paid_search_endpoint_url
        and settings.paid_search_api_key
    ):
        connectors.append(
            PaidSearchConnector(
                name=settings.paid_search_name,
                endpoint_url=settings.paid_search_endpoint_url,
                api_key=settings.paid_search_api_key,
                query=settings.paid_search_query,
                estimated_cost_usd=settings.paid_search_estimated_cost_usd,
            )
        )
    return connectors


def default_ai_rss_feeds() -> list[str]:
    return [
        "https://openai.com/news/rss.xml",
        "https://www.anthropic.com/news/rss.xml",
        "https://huggingface.co/blog/feed.xml",
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval-seconds", type=float, default=300.0)
    args = parser.parse_args()
    run_scheduler(args.interval_seconds)


if __name__ == "__main__":
    main()
