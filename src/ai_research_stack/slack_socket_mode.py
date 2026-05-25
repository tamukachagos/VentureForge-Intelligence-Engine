from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from threading import Event
import time
from typing import Any

from slack_sdk import WebClient
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse

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


def run_socket_mode(app_token: str, repository: Repository, bot_token: str = "") -> None:
    web_client = WebClient(token=bot_token or None)
    client = SocketModeClient(app_token=app_token, web_client=web_client)

    def process(client: SocketModeClient, request: SocketModeRequest) -> None:
        envelope = {
            "type": request.type,
            "envelope_id": request.envelope_id,
            "payload": request.payload,
        }
        response = handle_socket_mode_payload(envelope, repository)
        client.send_socket_mode_response(
            SocketModeResponse(
                envelope_id=str(response["envelope_id"]),
                payload=response.get("payload"),
            )
        )

    client.socket_mode_request_listeners.append(process)
    client.connect()
    Event().wait()


def run_socket_mode_forever(
    run_once: Any,
    sleep: Any = time.sleep,
    max_attempts: int | None = None,
) -> None:
    attempts = 0
    while max_attempts is None or attempts < max_attempts:
        attempts += 1
        try:
            run_once()
        except Exception as exc:
            print(f"Slack Socket Mode connection ended; reconnecting: {exc}", flush=True)
            if max_attempts is None or attempts < max_attempts:
                sleep(5.0)


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
    run_socket_mode_forever(
        lambda: run_socket_mode(settings.slack_app_token, repository, settings.slack_bot_token)
    )


if __name__ == "__main__":
    main()
