from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from .base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JudgeJobModel(Base):
    __tablename__ = "judge_jobs"

    job_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dispatch_type: Mapped[str] = mapped_column(String(16), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    session_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    rubric_version: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    judge_policy_version: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    topic_domain: Mapped[str] = mapped_column(String(128), nullable=False, default="default")
    retrieval_profile: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_judge_jobs_dispatch_status", "dispatch_type", "status"),
        Index("ix_judge_jobs_updated_at", "updated_at"),
    )


class JudgeJobEventModel(Base):
    __tablename__ = "judge_job_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("judge_jobs.job_id", ondelete="CASCADE"),
        nullable=False,
    )
    event_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("job_id", "event_seq", name="uq_judge_job_events_job_seq"),
        Index("ix_judge_job_events_job_id", "job_id"),
    )


class DispatchReceiptModel(Base):
    __tablename__ = "dispatch_receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dispatch_type: Mapped[str] = mapped_column(String(16), nullable=False)
    job_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    scope_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    session_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    rubric_version: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    judge_policy_version: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    topic_domain: Mapped[str] = mapped_column(String(128), nullable=False, default="default")
    retrieval_profile: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phase_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    phase_start_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    phase_end_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message_start_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    message_end_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    message_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    request: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    response: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint(
            "dispatch_type",
            "job_id",
            name="uq_dispatch_receipts_dispatch_type_job_id",
        ),
        Index("ix_dispatch_receipts_session_status", "session_id", "status"),
        Index("ix_dispatch_receipts_updated_at", "updated_at"),
    )


class ReplayRecordModel(Base):
    __tablename__ = "replay_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dispatch_type: Mapped[str] = mapped_column(String(16), nullable=False)
    job_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    winner: Mapped[str | None] = mapped_column(String(16), nullable=True)
    needs_draw_vote: Mapped[bool | None] = mapped_column(nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    report_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_replay_records_dispatch_job", "dispatch_type", "job_id"),
        Index("ix_replay_records_created_at", "created_at"),
    )


class ClaimLedgerRecordModel(Base):
    __tablename__ = "claim_ledger_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    dispatch_type: Mapped[str] = mapped_column(String(16), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    case_dossier: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    claim_graph: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    claim_graph_summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    evidence_ledger: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    verdict_evidence_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("case_id", "dispatch_type", name="uq_claim_ledger_case_dispatch"),
        Index("ix_claim_ledger_case_updated", "case_id", "updated_at"),
    )


class FairnessBenchmarkRunModel(Base):
    __tablename__ = "fairness_benchmark_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(96), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False, default="fairness-benchmark-v1")
    environment_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="blocked")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_data")
    threshold_decision: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    needs_real_env_reconfirm: Mapped[bool] = mapped_column(nullable=False, default=False)
    needs_remediation: Mapped[bool] = mapped_column(nullable=False, default=False)
    sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    draw_rate: Mapped[float | None] = mapped_column(nullable=True)
    side_bias_delta: Mapped[float | None] = mapped_column(nullable=True)
    appeal_overturn_rate: Mapped[float | None] = mapped_column(nullable=True)
    thresholds: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    reported_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("run_id", name="uq_fairness_benchmark_runs_run_id"),
        Index("ix_fairness_benchmark_runs_policy_reported", "policy_version", "reported_at"),
        Index("ix_fairness_benchmark_runs_status_reported", "status", "reported_at"),
    )


class AuditAlertModel(Base):
    __tablename__ = "audit_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_id: Mapped[str] = mapped_column(String(64), nullable=False)
    job_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    scope_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    message: Mapped[str] = mapped_column(String(512), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="raised")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("alert_id", name="uq_audit_alerts_alert_id"),
        Index("ix_audit_alerts_job_status", "job_id", "status"),
        Index("ix_audit_alerts_updated_at", "updated_at"),
    )


class JudgeRegistryReleaseModel(Base):
    __tablename__ = "judge_registry_releases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    registry_type: Mapped[str] = mapped_column(String(16), nullable=False)
    version: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="published")
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    activated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("registry_type", "version", name="uq_judge_registry_release_type_version"),
        Index("ix_judge_registry_release_type_active", "registry_type", "is_active"),
        Index("ix_judge_registry_release_type_updated", "registry_type", "updated_at"),
    )


class JudgeRegistryAuditModel(Base):
    __tablename__ = "judge_registry_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    registry_type: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    actor: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_judge_registry_audits_type_created", "registry_type", "created_at"),
    )
