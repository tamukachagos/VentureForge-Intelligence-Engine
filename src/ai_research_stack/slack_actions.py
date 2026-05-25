from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from ai_research_stack.slack import SlackAction


ACTION_STATUS = {
    "approve": "approved",
    "reject": "rejected",
    "deeper_research": "requested",
    "snooze": "snoozed",
    "halt": "halted",
    "accept_codebase": "accepted",
}


def record_slack_action(
    repository: Any,
    action: SlackAction,
    user_id: str,
    now: datetime,
) -> None:
    status = ACTION_STATUS.get(action.action, "recorded")
    repository.add_approval(
        {
            "approval_id": str(uuid4()),
            "opportunity_id": action.opportunity_id,
            "approval_type": action.action,
            "status": status,
            "requested_reason": f"Slack action {action.action}",
            "decided_by": user_id,
            "decided_at": now,
        },
        now,
    )
    repository.append_event(
        {
            "event_id": str(uuid4()),
            "entity_type": "opportunity",
            "entity_id": action.opportunity_id,
            "event_type": "slack_action_recorded",
            "payload": {"action": action.action, "user_id": user_id, "status": status},
        },
        now,
    )
