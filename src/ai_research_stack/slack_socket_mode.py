from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from typing import Any

import httpx
from websockets.sync.client import connect

from ai_research_stack.config import load_settings
from ai_research_stack.postgres import PostgresRepository
from ai_research_stack.repository import InMemoryRepository
from ai_research_stack.slack import parse_slack_action
from ai_research_stack.slack_actions import record_slack_action


Repository = InMemoryRepository | PostgresRepository


def handle_socket_mode_payload(
    envelope: dict[str, Any],
    repository: Repository,
    now: datetime | None = None,
) -> dict[str, Any]:
    envelope_id = str(envelope.get("envelope_id") or "")
    payload = envelope.get("payload") or {}
    if not isinstance(payload, dict):
        payload = {}

    if envelope.get("type") == "slash_commands":
        command = str(payload.get("command") or "")
        text = str(payload.get("text") or "")
        if command == "/ask-tracker":
            question = text or "latest frontier changes"
            return {
                "envelope_id": envelope_id,
                "payload": {
                    "response_type": "ephemeral",
                    "text": f"Tracker question queued: {question}",
                },
            }
        return {
            "envelope_id": envelope_id,
            "payload": {"response_type": "ephemeral", "text": "Unsupported command"},
        }

    if envelope.get("type") == "interactive":
        action = parse_slack_action(json.dumps(payload))
        if action is None:
            return {
                "envelope_id": envelope_id,
                "payload": {"response_type": "ephemeral", "text": "Unsupported action"},
            }
        user_id = action.user_id or "slack-owner"
        record_slack_action(repository, action, user_id, now or datetime.now(timezone.utc))
        return {
            "envelope_id": envelope_id,
            "payload": {
                "response_type": "ephemeral",
                "text": f"Recorded {action.action} for {action.opportunity_id}",
            },
        }

    return {"envelope_id": envelope_id}


def open_socket_mode_url(app_token: str) -> str:
    headers = {"Authorization": f"Bearer {app_token}"}
    with httpx.Client(timeout=30) as client:
        response = client.post("https://slack.com/api/apps.connections.open", headers=headers)
        response.raise_for_status()
        data = response.json()
    if not data.get("ok") or not data.get("url"):
        raise RuntimeError(f"Slack Socket Mode open failed: {data}")
    return str(data["url"])


def run_socket_mode(app_token: str, repository: Repository) -> None:
    socket_url = open_socket_mode_url(app_token)
    with connect(socket_url) as websocket:
        for message in websocket:
            envelope = json.loads(message)
            response = handle_socket_mode_payload(envelope, repository)
            websocket.send(json.dumps(response))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Slack Socket Mode listener")
    parser.parse_args()
    settings = load_settings()
    if not settings.slack_app_token:
        raise SystemExit("SLACK_APP_TOKEN is required for Socket Mode")
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is required for Socket Mode")
    repository = PostgresRepository(settings.database_url)
    repository.initialize_schema()
    run_socket_mode(settings.slack_app_token, repository)


if __name__ == "__main__":
    main()
