from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

WORKFLOW_STATUS_QUEUED = "queued"
WORKFLOW_STATUS_BLINDED = "blinded"
WORKFLOW_STATUS_CASE_BUILT = "case_built"
WORKFLOW_STATUS_CLAIM_GRAPH_READY = "claim_graph_ready"
WORKFLOW_STATUS_EVIDENCE_READY = "evidence_ready"
WORKFLOW_STATUS_PANEL_JUDGED = "panel_judged"
WORKFLOW_STATUS_FAIRNESS_CHECKED = "fairness_checked"
WORKFLOW_STATUS_ARBITRATED = "arbitrated"
WORKFLOW_STATUS_OPINION_WRITTEN = "opinion_written"
WORKFLOW_STATUS_CALLBACK_REPORTED = "callback_reported"
WORKFLOW_STATUS_ARCHIVED = "archived"
WORKFLOW_STATUS_REVIEW_REQUIRED = "review_required"
WORKFLOW_STATUS_DRAW_PENDING_VOTE = "draw_pending_vote"
WORKFLOW_STATUS_BLOCKED_FAILED = "blocked_failed"

WORKFLOW_STATUSES = {
    WORKFLOW_STATUS_QUEUED,
    WORKFLOW_STATUS_BLINDED,
    WORKFLOW_STATUS_CASE_BUILT,
    WORKFLOW_STATUS_CLAIM_GRAPH_READY,
    WORKFLOW_STATUS_EVIDENCE_READY,
    WORKFLOW_STATUS_PANEL_JUDGED,
    WORKFLOW_STATUS_FAIRNESS_CHECKED,
    WORKFLOW_STATUS_ARBITRATED,
    WORKFLOW_STATUS_OPINION_WRITTEN,
    WORKFLOW_STATUS_CALLBACK_REPORTED,
    WORKFLOW_STATUS_ARCHIVED,
    WORKFLOW_STATUS_REVIEW_REQUIRED,
    WORKFLOW_STATUS_DRAW_PENDING_VOTE,
    WORKFLOW_STATUS_BLOCKED_FAILED,
}

WORKFLOW_EVENT_REGISTERED = "job_registered"
WORKFLOW_EVENT_STATUS_CHANGED = "status_changed"
WORKFLOW_EVENT_REPLAY_MARKED = "replay_marked"


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
