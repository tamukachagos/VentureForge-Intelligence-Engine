from datetime import datetime, timedelta, timezone

from ai_research_stack.domain import TaskStatus
from ai_research_stack.repository import InMemoryRepository
from ai_research_stack.tasks import TaskLeaser


def test_task_leases_are_exclusive():
    repo = InMemoryRepository()
    leaser = TaskLeaser(repo, lease_seconds=60)
    now = datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc)

    first_id = leaser.enqueue("score_opportunity", {"opportunity_id": "opp-1"}, "idem-1", now)
    second_id = leaser.enqueue("score_opportunity", {"opportunity_id": "opp-2"}, "idem-2", now)

    first_claim = leaser.claim_next("worker-a", now)
    second_claim = leaser.claim_next("worker-b", now)

    assert {first_claim.task_id, second_claim.task_id} == {first_id, second_id}
    assert leaser.claim_next("worker-c", now) is None


def test_expired_task_lease_can_be_reclaimed():
    repo = InMemoryRepository()
    leaser = TaskLeaser(repo, lease_seconds=60)
    now = datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc)

    task_id = leaser.enqueue("research", {"opportunity_id": "opp-1"}, "idem-1", now)
    claim = leaser.claim_next("worker-a", now)

    assert claim.task_id == task_id

    reclaimed = leaser.claim_next("worker-b", now + timedelta(seconds=61))

    assert reclaimed.task_id == task_id
    assert reclaimed.lease_holder == "worker-b"


def test_idempotency_key_prevents_duplicate_open_tasks():
    repo = InMemoryRepository()
    leaser = TaskLeaser(repo)
    now = datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc)

    first_id = leaser.enqueue("research", {"opportunity_id": "opp-1"}, "same-key", now)
    second_id = leaser.enqueue("research", {"opportunity_id": "opp-1"}, "same-key", now)

    assert first_id == second_id
    assert len(repo.tasks) == 1


def test_retry_cap_marks_task_dead():
    repo = InMemoryRepository()
    leaser = TaskLeaser(repo, max_attempts=2)
    now = datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc)

    task_id = leaser.enqueue("research", {"opportunity_id": "opp-1"}, "idem-1", now)
    claim = leaser.claim_next("worker-a", now)
    leaser.fail(claim.task_id, "first failure", now)
    claim = leaser.claim_next("worker-a", now + timedelta(seconds=61))
    leaser.fail(claim.task_id, "second failure", now + timedelta(seconds=62))

    task = repo.get_task(task_id)
    assert task.status == TaskStatus.DEAD
    assert task.last_error == "second failure"
