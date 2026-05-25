from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

import httpx


ALLOWED_ACTIONS = {
    "approve",
    "reject",
    "deeper_research",
    "snooze",
    "halt",
    "accept_codebase",
}


@dataclass(frozen=True)
class SlackAction:
    action: str
    opportunity_id: str
    user_id: str | None = None


Transport = Callable[[str, dict[str, str], dict[str, Any]], dict[str, Any]]
PostFunction = Callable[[dict[str, Any]], Any]


class SlackClient:
    def __init__(
        self,
        token: str,
        transport: Transport | None = None,
        api_url: str = "https://slack.com/api/chat.postMessage",
    ) -> None:
        self.token = token
        self.transport = transport or _httpx_transport
        self.api_url = api_url

    def post_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        return self.transport(self.api_url, headers, payload)


class SlackNotifier:
    def __init__(self, channel: str, post: PostFunction) -> None:
        self.channel = channel
        self.post = post

    def send_daily_digest(self, digest: dict[str, Any]) -> None:
        self.post(build_daily_digest_message(self.channel, digest))

    def send_promotion_dossier(self, dossier: dict[str, Any]) -> None:
        self.post(build_promotion_dossier_message(self.channel, dossier))


def _httpx_transport(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    with httpx.Client(timeout=30) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()


def build_daily_digest_message(channel: str, digest: dict[str, Any]) -> dict[str, Any]:
    summary = str(digest.get("summary") or digest.get("digest") or "No summary provided.")
    spend = float(digest.get("daily_llm_spend") or 0.0)
    cap = float(digest.get("daily_llm_cap") or 15.0)
    opportunities = digest.get("top_opportunities") or []
    lines = []
    for item in opportunities[:8]:
        if isinstance(item, dict):
            lines.append(
                f"*{item.get('title', 'Untitled')}* — `{item.get('stage', 'unknown')}` — "
                f"score `{item.get('score', '-')}`"
            )
    opportunity_text = "\n".join(lines) if lines else "_No promoted opportunities in this digest._"

    return {
        "channel": channel,
        "text": "Daily Intelligence Digest",
        "blocks": [
            _section("*Daily Intelligence Digest*"),
            _section(summary),
            _section(f"*Budget:* ${spend:.2f} / ${cap:.2f} LLM spend today"),
            _section(f"*Top opportunities:*\n{opportunity_text}"),
        ],
    }


def build_promotion_dossier_message(channel: str, dossier: dict[str, Any]) -> dict[str, Any]:
    opportunity_id = str(dossier.get("opportunity_id") or "")
    title = str(dossier.get("title") or "Untitled opportunity")
    thesis = str(dossier.get("thesis") or "No thesis provided.")
    recommendation = str(dossier.get("recommendation") or "research_more")
    score = dossier.get("score", "-")
    confidence = dossier.get("confidence", "-")
    fatal_flaws = dossier.get("fatal_flaws") or []
    flaws_text = (
        "\n".join(f"- {flaw}" for flaw in fatal_flaws)
        if fatal_flaws
        else "No fatal flaws reported by critic."
    )

    return {
        "channel": channel,
        "text": f"Promotion Dossier: {title}",
        "blocks": [
            _section(f"*Promotion Dossier*\n*{title}*"),
            _section(thesis),
            _section(
                f"*Recommendation:* `{recommendation}`\n"
                f"*Score:* `{score}`\n"
                f"*Confidence:* `{confidence}`\n"
                f"*Critic flaws:*\n{flaws_text}"
            ),
            {
                "type": "actions",
                "elements": [
                    _button("Approve", "primary", f"approve:{opportunity_id}"),
                    _button("Reject", "danger", f"reject:{opportunity_id}"),
                    _button("Deeper Research", None, f"deeper_research:{opportunity_id}"),
                    _button("Snooze", None, f"snooze:{opportunity_id}"),
                    _button("Halt", "danger", f"halt:{opportunity_id}"),
                ],
            },
        ],
    }


def _section(text: str) -> dict[str, Any]:
    return {"type": "section", "text": {"type": "mrkdwn", "text": text[:3000]}}


def _button(text: str, style: str | None, value: str) -> dict[str, Any]:
    button: dict[str, Any] = {
        "type": "button",
        "text": {"type": "plain_text", "text": text},
        "value": value,
    }
    if style:
        button["style"] = style
    return button


def verify_slack_signature(
    signing_secret: str,
    timestamp: str,
    body: bytes,
    signature: str,
    now: datetime | None = None,
) -> bool:
    if now is None:
        now = datetime.now(timezone.utc)

    try:
        request_time = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
    except ValueError:
        return False

    if abs((now - request_time).total_seconds()) > 300:
        return False

    base = b"v0:" + timestamp.encode("utf-8") + b":" + body
    digest = hmac.new(signing_secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
    expected = f"v0={digest}"
    return hmac.compare_digest(expected, signature)


def parse_slack_action(value: str) -> SlackAction | None:
    parsed_value = _extract_action_value(value)
    user_id = _extract_user_id(value)
    if parsed_value is not None:
        value = parsed_value
    if ":" not in value:
        return None
    action, opportunity_id = value.split(":", 1)
    if action not in ALLOWED_ACTIONS or not opportunity_id:
        return None
    return SlackAction(action=action, opportunity_id=opportunity_id, user_id=user_id)


def _extract_action_value(value: str) -> str | None:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    actions = payload.get("actions")
    if not isinstance(actions, list) or not actions:
        return None
    first = actions[0]
    if not isinstance(first, dict):
        return None
    action_value = first.get("value")
    return str(action_value) if action_value else None


def _extract_user_id(value: str) -> str | None:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    user = payload.get("user")
    if isinstance(user, dict) and user.get("id"):
        return str(user["id"])
    return None
