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


@dataclass(frozen=True)
class ClaimLedgerRecord:
    case_id: int
    dispatch_type: str
    trace_id: str
    claim_graph: dict[str, Any]
    claim_graph_summary: dict[str, Any]
    evidence_ledger: dict[str, Any]
    verdict_evidence_refs: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class FairnessBenchmarkRun:
    run_id: str
    policy_version: str
    environment_mode: str
    status: str
    threshold_decision: str
    needs_real_env_reconfirm: bool
    needs_remediation: bool
    sample_size: int | None
    draw_rate: float | None
    side_bias_delta: float | None
    appeal_overturn_rate: float | None
    thresholds: dict[str, Any]
    metrics: dict[str, Any]
    summary: dict[str, Any]
    source: str
    reported_by: str
    reported_at: datetime
    created_at: datetime
    updated_at: datetime
