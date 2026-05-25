from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone

from ai_research_stack.agents import runtime_from_settings
from ai_research_stack.config import load_settings
from ai_research_stack.postgres import PostgresRepository
from ai_research_stack.results import ResultProcessor
from ai_research_stack.slack import SlackClient, SlackNotifier
from ai_research_stack.tasks import TaskLeaser


def run_worker(worker_id: str, poll_seconds: float = 2.0) -> None:
    settings = load_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required for worker")
    repository = PostgresRepository(settings.database_url)
    runtime = runtime_from_settings(settings)
    leaser = TaskLeaser(repository)
    slack_notifier = None
    if settings.slack_bot_token and settings.slack_channel_id:
        slack_client = SlackClient(settings.slack_bot_token)
        slack_notifier = SlackNotifier(settings.slack_channel_id, slack_client.post_message)
    processor = ResultProcessor(repository, slack_notifier=slack_notifier)

    while True:
        now = datetime.now(timezone.utc)
        claim = leaser.claim_next(worker_id, now)
        if claim is None:
            time.sleep(poll_seconds)
            continue

        try:
            result = runtime.run(claim.task_type, claim.payload)
            if result.status == "complete":
                completed_at = datetime.now(timezone.utc)
                leaser.complete(claim.task_id, result.__dict__, completed_at)
                processor.process(
                    claim.task_type,
                    {**claim.payload, "task_id": claim.task_id},
                    result,
                    completed_at,
                )
            else:
                leaser.fail(claim.task_id, str(result.output), datetime.now(timezone.utc))
        except Exception as exc:  # pragma: no cover - runtime safeguard
            leaser.fail(claim.task_id, repr(exc), datetime.now(timezone.utc))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker-id", default="worker-1")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()
    run_worker(args.worker_id, args.poll_seconds)


if __name__ == "__main__":
    main()
