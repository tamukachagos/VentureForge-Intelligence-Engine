from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class WitnessType(str, Enum):
    BUYER_COMPLAINT = "buyer_complaint"
    JOB_POSTING_PATTERN = "job_posting_pattern"
    PAID_INCUMBENT = "paid_incumbent"
    REGULATORY_DEADLINE = "regulatory_deadline"
    BUDGET_OWNER = "budget_owner"
    WORKFLOW_COST = "workflow_cost"
    ADJACENT_SPEND = "adjacent_spend"
    ANALOGOUS_WORKFLOW = "analogous_workflow"
    ROLE_BASED_NEED = "role_based_need"
    NEARBY_WILLINGNESS_TO_PAY = "nearby_willingness_to_pay"


class TaskStatus(str, Enum):
    PENDING = "pending"
    LEASED = "leased"
    COMPLETE = "complete"
    FAILED = "failed"
    DEAD = "dead"


class OpportunityStage(str, Enum):
    WATCHLIST = "watchlist"
    FIRST_PASS = "first_pass"
    RESEARCH = "research"
    EXPRESS_RESEARCH = "express_research"
    CRITIC = "critic"
    DOSSIER_READY = "dossier_ready"
    REJECTED = "rejected"
    HARD_STOP = "hard_stop"


@dataclass(frozen=True)
class DemandWitness:
    opportunity_id: str
    witness_type: WitnessType
    source: str
    excerpt: str
    strength: float
    is_proxy: bool
    collected_at: datetime


@dataclass(frozen=True)
class DemandGateResult:
    allowed: bool
    reason: str
    has_direct_witness: bool
    strongest_strength: float


@dataclass(frozen=True)
class TaskClaim:
    task_id: str
    task_type: str
    payload: dict[str, Any]
    lease_holder: str
    lease_expires_at: datetime
    attempts: int


@dataclass
class AgentTask:
    task_type: str
    payload: dict[str, Any]
    idempotency_key: str
    task_id: str = field(default_factory=lambda: str(uuid4()))
    status: TaskStatus = TaskStatus.PENDING
    attempts: int = 0
    lease_holder: str | None = None
    lease_expires_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_error: str | None = None
    result: dict[str, Any] | None = None


@dataclass(frozen=True)
class OpportunityDecision:
    opportunity_id: str
    stage: OpportunityStage
    reason: str
    task_types: tuple[str, ...] = ()

