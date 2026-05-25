from datetime import datetime, timezone

from ai_research_stack.repository import InMemoryRepository
from ai_research_stack.slack_socket_mode import handle_socket_mode_payload, run_socket_mode_forever


def test_socket_mode_handles_ask_tracker_command():
    repo = InMemoryRepository()

    response = handle_socket_mode_payload(
        {
            "type": "slash_commands",
            "envelope_id": "env-1",
            "payload": {
                "command": "/ask-tracker",
                "text": "what changed in agent tools?",
                "user_id": "U123",
            },
        },
        repo,
        now=datetime(2026, 5, 25, tzinfo=timezone.utc),
    )

    assert response == {
        "envelope_id": "env-1",
        "payload": {
            "response_type": "ephemeral",
            "text": "Tracker question queued: what changed in agent tools?",
        },
    }


def test_socket_mode_records_block_action_approval():
    repo = InMemoryRepository()

    response = handle_socket_mode_payload(
        {
            "type": "interactive",
            "envelope_id": "env-2",
            "payload": {
                "type": "block_actions",
                "user": {"id": "U123"},
                "actions": [{"value": "approve:opp-1"}],
            },
        },
        repo,
        now=datetime(2026, 5, 25, tzinfo=timezone.utc),
    )

    assert response == {
        "envelope_id": "env-2",
        "payload": {
            "response_type": "ephemeral",
            "text": "Recorded approve for opp-1",
        },
    }
    assert repo.approvals[0]["opportunity_id"] == "opp-1"
    assert repo.approvals[0]["approval_type"] == "approve"
    assert repo.approvals[0]["status"] == "approved"
    assert repo.approvals[0]["decided_by"] == "U123"


def test_socket_mode_acks_unsupported_payloads():
    repo = InMemoryRepository()

    response = handle_socket_mode_payload(
        {"type": "events_api", "envelope_id": "env-3", "payload": {}},
        repo,
        now=datetime(2026, 5, 25, tzinfo=timezone.utc),
    )

    assert response == {"envelope_id": "env-3"}


def test_socket_mode_forever_reconnects_after_connection_error():
    attempts: list[str] = []
    sleeps: list[float] = []

    def run_once() -> None:
        attempts.append("run")
        raise RuntimeError("closed")

    run_socket_mode_forever(run_once, sleep=lambda seconds: sleeps.append(seconds), max_attempts=2)

    assert attempts == ["run", "run"]
    assert sleeps == [5.0]
