from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

ALERT_STATUS_RAISED = "raised"
ALERT_STATUS_ACKED = "acked"
ALERT_STATUS_RESOLVED = "resolved"
ALERT_STATUS_VALUES = {ALERT_STATUS_RAISED, ALERT_STATUS_ACKED, ALERT_STATUS_RESOLVED}


@dataclass(frozen=True)
class DispatchReceipt:
    dispatch_type: str
    job_id: int
    scope_id: int
    session_id: int
    trace_id: str
    idempotency_key: str
    rubric_version: str
    judge_policy_version: str
    topic_domain: str
    retrieval_profile: str | None
    phase_no: int | None
    phase_start_no: int | None
    phase_end_no: int | None
    message_start_id: int | None
    message_end_id: int | None
    message_count: int | None
    status: str
    request: dict[str, Any]
    response: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ReplayRecord:
    dispatch_type: str
    job_id: int
    trace_id: str
    winner: str | None
    needs_draw_vote: bool | None
    provider: str | None
    report_payload: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True)
class AuditAlert:
    alert_id: str
    job_id: int
    scope_id: int
    trace_id: str
    alert_type: str
    severity: str
    title: str
    message: str
    details: dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
