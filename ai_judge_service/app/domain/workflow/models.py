from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

WORKFLOW_STATUS_QUEUED = "queued"
WORKFLOW_STATUS_CASE_BUILT = "case_built"
WORKFLOW_STATUS_RUNNING = "running"
WORKFLOW_STATUS_REVIEW_REQUIRED = "review_required"
WORKFLOW_STATUS_COMPLETED = "completed"
WORKFLOW_STATUS_FAILED = "failed"

WORKFLOW_STATUSES = {
    WORKFLOW_STATUS_QUEUED,
    WORKFLOW_STATUS_CASE_BUILT,
    WORKFLOW_STATUS_RUNNING,
    WORKFLOW_STATUS_REVIEW_REQUIRED,
    WORKFLOW_STATUS_COMPLETED,
    WORKFLOW_STATUS_FAILED,
}

WORKFLOW_EVENT_REGISTERED = "job_registered"
WORKFLOW_EVENT_STATUS_CHANGED = "status_changed"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class WorkflowJob:
    job_id: int
    dispatch_type: str
    trace_id: str
    status: str
    scope_id: int = 1
    session_id: int | None = None
    idempotency_key: str = ""
    rubric_version: str = ""
    judge_policy_version: str = ""
    topic_domain: str = "default"
    retrieval_profile: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class WorkflowEvent:
    job_id: int
    event_seq: int
    event_type: str
    payload: dict[str, Any]
    created_at: datetime
