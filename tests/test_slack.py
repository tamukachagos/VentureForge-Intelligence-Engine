import hmac
import hashlib
import json
from datetime import datetime, timezone

from ai_research_stack.slack import (
    SlackClient,
    SlackAction,
    build_daily_digest_message,
    build_promotion_dossier_message,
    parse_slack_action,
    verify_slack_signature,
)


def sign(secret: str, timestamp: str, body: bytes) -> str:
    base = b"v0:" + timestamp.encode("utf-8") + b":" + body
    digest = hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
    return f"v0={digest}"


def test_verify_slack_signature_accepts_valid_recent_request():
    secret = "signing-secret"
    body = b"command=/ask-tracker&text=what changed in AI agents"
    timestamp = "1780000000"

    assert verify_slack_signature(
        signing_secret=secret,
        timestamp=timestamp,
        body=body,
        signature=sign(secret, timestamp, body),
        now=datetime.fromtimestamp(1780000010, tz=timezone.utc),
    )


def test_verify_slack_signature_rejects_stale_or_bad_request():
    secret = "signing-secret"
    body = b"command=/ask-tracker&text=what changed"
    timestamp = "1780000000"

    assert (
        verify_slack_signature(
            signing_secret=secret,
            timestamp=timestamp,
            body=body,
            signature=sign(secret, timestamp, body),
            now=datetime.fromtimestamp(1780001000, tz=timezone.utc),
        )
        is False
    )
    assert (
        verify_slack_signature(
            signing_secret=secret,
            timestamp=timestamp,
            body=body,
            signature="v0=bad",
            now=datetime.fromtimestamp(1780000010, tz=timezone.utc),
        )
        is False
    )


def test_parse_slack_action_maps_allowed_buttons():
    action = parse_slack_action("deeper_research:opp-123")

    assert action == SlackAction(action="deeper_research", opportunity_id="opp-123")

    assert parse_slack_action("unknown:opp-123") is None
    assert parse_slack_action("halt") is None


def test_parse_slack_action_accepts_interactive_payload_json():
    payload = {
        "user": {"id": "U123"},
        "actions": [{"value": "approve:opp-1"}],
    }

    action = parse_slack_action(json.dumps(payload))

    assert action == SlackAction(action="approve", opportunity_id="opp-1", user_id="U123")


def test_build_daily_digest_message_contains_budget_and_pipeline_blocks():
    message = build_daily_digest_message(
        channel="C123",
        digest={
            "summary": "Three frontier signals reviewed.",
            "daily_llm_spend": 4.25,
            "daily_llm_cap": 15.0,
            "top_opportunities": [
                {
                    "opportunity_id": "opp-1",
                    "title": "Spreadsheet QA copilot",
                    "stage": "research",
                    "score": 7.4,
                }
            ],
        },
    )

    assert message["channel"] == "C123"
    assert "Daily Intelligence Digest" in message["text"]
    block_text = "\n".join(str(block) for block in message["blocks"])
    assert "$4.25 / $15.00" in block_text
    assert "Spreadsheet QA copilot" in block_text


def test_build_promotion_dossier_message_has_owner_actions():
    message = build_promotion_dossier_message(
        channel="C123",
        dossier={
            "opportunity_id": "opp-1",
            "title": "Spreadsheet QA copilot",
            "thesis": "Finance teams need spreadsheet control automation.",
            "score": 8.1,
            "confidence": 0.77,
            "recommendation": "promote",
            "fatal_flaws": [],
        },
    )

    assert message["channel"] == "C123"
    assert "Promotion Dossier" in message["text"]
    action_values = [
        element["value"]
        for block in message["blocks"]
        if block.get("type") == "actions"
        for element in block["elements"]
    ]
    assert "approve:opp-1" in action_values
    assert "reject:opp-1" in action_values
    assert "deeper_research:opp-1" in action_values
    assert "snooze:opp-1" in action_values
    assert "halt:opp-1" in action_values


def test_slack_client_posts_message_through_injected_transport():
    calls = []

    def transport(url, headers, payload):
        calls.append((url, headers, payload))
        return {"ok": True, "ts": "123.456"}

    client = SlackClient(token="xoxb-test", transport=transport)
    response = client.post_message({"channel": "C123", "text": "hello"})

    assert response["ok"] is True
    assert calls[0][0] == "https://slack.com/api/chat.postMessage"
    assert calls[0][1]["Authorization"] == "Bearer xoxb-test"
    assert calls[0][2]["text"] == "hello"
