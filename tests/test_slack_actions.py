from datetime import datetime, timezone

from ai_research_stack.repository import InMemoryRepository
from ai_research_stack.slack import SlackAction
from ai_research_stack.slack_actions import record_slack_action


def test_record_slack_action_persists_approval_and_event():
    repo = InMemoryRepository()
    now = datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc)

    record_slack_action(
        repo,
        SlackAction(action="approve", opportunity_id="opp-1"),
        user_id="U123",
        now=now,
    )

    assert repo.approvals[0]["opportunity_id"] == "opp-1"
    assert repo.approvals[0]["approval_type"] == "approve"
    assert repo.approvals[0]["status"] == "approved"
    assert repo.events[-1]["event_type"] == "slack_action_recorded"
