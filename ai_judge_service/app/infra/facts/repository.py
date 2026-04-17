from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Select, and_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.facts import (
    ALERT_STATUS_ACKED,
    ALERT_STATUS_RAISED,
    ALERT_STATUS_RESOLVED,
    ALERT_STATUS_VALUES,
    AuditAlert,
    ClaimLedgerRecord,
    DispatchReceipt,
    FairnessBenchmarkRun,
    FairnessShadowRun,
    ReplayRecord,
)
from app.infra.db.models import (
    AuditAlertModel,
    ClaimLedgerRecordModel,
    DispatchReceiptModel,
    FairnessBenchmarkRunModel,
    FairnessShadowRunModel,
    ReplayRecordModel,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_dt(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _normalize_token(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalize_alert_status(value: str) -> str:
    token = _normalize_token(value)
    return token if token in ALERT_STATUS_VALUES else ALERT_STATUS_RAISED


def _allow_alert_transition(*, from_status: str, to_status: str) -> bool:
    src = _normalize_alert_status(from_status)
    dst = _normalize_alert_status(to_status)
    if src == dst:
        return True
    if src == ALERT_STATUS_RAISED and dst in {ALERT_STATUS_ACKED, ALERT_STATUS_RESOLVED}:
        return True
    if src == ALERT_STATUS_ACKED and dst == ALERT_STATUS_RESOLVED:
        return True
    return False


class JudgeFactRepository:
    def __init__(self, *, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def upsert_dispatch_receipt(self, *, receipt: DispatchReceipt) -> DispatchReceipt:
        now = _utcnow()
        stmt: Select[tuple[DispatchReceiptModel]] = select(DispatchReceiptModel).where(
            and_(
                DispatchReceiptModel.dispatch_type == receipt.dispatch_type,
                DispatchReceiptModel.job_id == receipt.job_id,
            )
        )
        async with self._session_factory() as session:
            async with session.begin():
                row = (await session.execute(stmt)).scalars().first()
                if row is None:
                    row = DispatchReceiptModel(
                        dispatch_type=receipt.dispatch_type,
                        job_id=receipt.job_id,
                        created_at=receipt.created_at,
                    )
                    session.add(row)

                row.scope_id = receipt.scope_id
                row.session_id = receipt.session_id
                row.trace_id = receipt.trace_id
                row.idempotency_key = receipt.idempotency_key
                row.rubric_version = receipt.rubric_version
                row.judge_policy_version = receipt.judge_policy_version
                row.topic_domain = receipt.topic_domain
                row.retrieval_profile = receipt.retrieval_profile
                row.phase_no = receipt.phase_no
                row.phase_start_no = receipt.phase_start_no
                row.phase_end_no = receipt.phase_end_no
                row.message_start_id = receipt.message_start_id
                row.message_end_id = receipt.message_end_id
                row.message_count = receipt.message_count
                row.status = _normalize_token(receipt.status) or "queued"
                row.request = dict(receipt.request)
                row.response = dict(receipt.response) if isinstance(receipt.response, dict) else None
                row.updated_at = receipt.updated_at if receipt.updated_at else now
                if row.created_at is None:
                    row.created_at = receipt.created_at if receipt.created_at else now
            await session.refresh(row)
            return self._to_dispatch_receipt(row)

    async def get_dispatch_receipt(
        self,
        *,
        dispatch_type: str,
        job_id: int,
    ) -> DispatchReceipt | None:
        stmt: Select[tuple[DispatchReceiptModel]] = select(DispatchReceiptModel).where(
            and_(
                DispatchReceiptModel.dispatch_type == _normalize_token(dispatch_type),
                DispatchReceiptModel.job_id == int(job_id),
            )
        )
        async with self._session_factory() as session:
            row = (await session.execute(stmt)).scalars().first()
            if row is None:
                return None
            return self._to_dispatch_receipt(row)

    async def list_dispatch_receipts(
        self,
        *,
        dispatch_type: str,
        session_id: int | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> list[DispatchReceipt]:
        stmt: Select[tuple[DispatchReceiptModel]] = (
            select(DispatchReceiptModel)
            .where(DispatchReceiptModel.dispatch_type == _normalize_token(dispatch_type))
            .order_by(DispatchReceiptModel.updated_at.desc())
            .limit(max(1, min(1000, int(limit))))
        )
        if session_id is not None:
            stmt = stmt.where(DispatchReceiptModel.session_id == int(session_id))
        if status is not None:
            stmt = stmt.where(DispatchReceiptModel.status == _normalize_token(status))

        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).scalars().all()
            return [self._to_dispatch_receipt(row) for row in rows]

    async def append_replay_record(
        self,
        *,
        dispatch_type: str,
        job_id: int,
        trace_id: str,
        winner: str | None,
        needs_draw_vote: bool | None,
        provider: str | None,
        report_payload: dict[str, Any] | None,
    ) -> ReplayRecord:
        now = _utcnow()
        row = ReplayRecordModel(
            dispatch_type=_normalize_token(dispatch_type) or "unknown",
            job_id=int(job_id),
            trace_id=str(trace_id or "").strip(),
            winner=(str(winner).strip().lower() if winner else None),
            needs_draw_vote=needs_draw_vote,
            provider=(str(provider).strip() if provider else None),
            report_payload=dict(report_payload or {}),
            created_at=now,
        )
        async with self._session_factory() as session:
            async with session.begin():
                session.add(row)
            await session.refresh(row)
            return self._to_replay_record(row)

    async def list_replay_records(
        self,
        *,
        dispatch_type: str | None = None,
        job_id: int | None = None,
        limit: int = 100,
    ) -> list[ReplayRecord]:
        stmt: Select[tuple[ReplayRecordModel]] = (
            select(ReplayRecordModel)
            .order_by(ReplayRecordModel.created_at.desc(), ReplayRecordModel.id.desc())
            .limit(max(1, min(1000, int(limit))))
        )
        if dispatch_type is not None:
            stmt = stmt.where(ReplayRecordModel.dispatch_type == _normalize_token(dispatch_type))
        if job_id is not None:
            stmt = stmt.where(ReplayRecordModel.job_id == int(job_id))

        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).scalars().all()
            return [self._to_replay_record(row) for row in rows]

    async def upsert_claim_ledger_record(
        self,
        *,
        case_id: int,
        dispatch_type: str,
        trace_id: str,
        case_dossier: dict[str, Any] | None,
        claim_graph: dict[str, Any] | None,
        claim_graph_summary: dict[str, Any] | None,
        evidence_ledger: dict[str, Any] | None,
        verdict_evidence_refs: list[dict[str, Any]] | None,
    ) -> ClaimLedgerRecord:
        now = _utcnow()
        normalized_dispatch_type = _normalize_token(dispatch_type) or "unknown"
        stmt: Select[tuple[ClaimLedgerRecordModel]] = select(ClaimLedgerRecordModel).where(
            and_(
                ClaimLedgerRecordModel.case_id == int(case_id),
                ClaimLedgerRecordModel.dispatch_type == normalized_dispatch_type,
            )
        )
        refs = [
            dict(item)
            for item in (verdict_evidence_refs or [])
            if isinstance(item, dict)
        ]
        async with self._session_factory() as session:
            async with session.begin():
                row = (await session.execute(stmt)).scalars().first()
                if row is None:
                    row = ClaimLedgerRecordModel(
                        case_id=int(case_id),
                        dispatch_type=normalized_dispatch_type,
                        created_at=now,
                    )
                    session.add(row)
                row.trace_id = str(trace_id or "").strip()
                row.case_dossier = dict(case_dossier or {})
                row.claim_graph = dict(claim_graph or {})
                row.claim_graph_summary = dict(claim_graph_summary or {})
                row.evidence_ledger = dict(evidence_ledger or {})
                row.verdict_evidence_refs = refs
                row.updated_at = now
            await session.refresh(row)
            return self._to_claim_ledger_record(row)

    async def get_claim_ledger_record(
        self,
        *,
        case_id: int,
        dispatch_type: str | None = None,
    ) -> ClaimLedgerRecord | None:
        stmt: Select[tuple[ClaimLedgerRecordModel]] = select(ClaimLedgerRecordModel).where(
            ClaimLedgerRecordModel.case_id == int(case_id)
        )
        if dispatch_type is not None:
            stmt = stmt.where(
                ClaimLedgerRecordModel.dispatch_type == (_normalize_token(dispatch_type) or "unknown")
            )
        else:
            stmt = stmt.order_by(ClaimLedgerRecordModel.updated_at.desc(), ClaimLedgerRecordModel.id.desc())

        async with self._session_factory() as session:
            row = (await session.execute(stmt)).scalars().first()
            if row is None:
                return None
            return self._to_claim_ledger_record(row)

    async def list_claim_ledger_records(
        self,
        *,
        case_id: int,
        limit: int = 20,
    ) -> list[ClaimLedgerRecord]:
        stmt: Select[tuple[ClaimLedgerRecordModel]] = (
            select(ClaimLedgerRecordModel)
            .where(ClaimLedgerRecordModel.case_id == int(case_id))
            .order_by(ClaimLedgerRecordModel.updated_at.desc(), ClaimLedgerRecordModel.id.desc())
            .limit(max(1, min(200, int(limit))))
        )
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).scalars().all()
            return [self._to_claim_ledger_record(row) for row in rows]

    async def upsert_fairness_benchmark_run(
        self,
        *,
        run_id: str,
        policy_version: str,
        environment_mode: str,
        status: str,
        threshold_decision: str,
        needs_real_env_reconfirm: bool,
        needs_remediation: bool,
        sample_size: int | None,
        draw_rate: float | None,
        side_bias_delta: float | None,
        appeal_overturn_rate: float | None,
        thresholds: dict[str, Any] | None,
        metrics: dict[str, Any] | None,
        summary: dict[str, Any] | None,
        source: str | None,
        reported_by: str | None,
        reported_at: datetime | None = None,
    ) -> FairnessBenchmarkRun:
        now = _utcnow()
        normalized_run_id = str(run_id or "").strip()
        if not normalized_run_id:
            raise ValueError("invalid_fairness_run_id")
        normalized_policy_version = str(policy_version or "").strip() or "fairness-benchmark-v1"
        normalized_environment_mode = _normalize_token(environment_mode) or "blocked"
        normalized_status = _normalize_token(status) or "pending_data"
        normalized_threshold_decision = _normalize_token(threshold_decision) or "pending"
        normalized_source = str(source or "").strip() or "manual"
        normalized_reported_by = str(reported_by or "").strip() or "system"
        normalized_reported_at = _normalize_dt(reported_at) if reported_at else now
        normalized_sample_size = (
            max(0, int(sample_size)) if sample_size is not None else None
        )
        normalized_draw_rate = float(draw_rate) if draw_rate is not None else None
        normalized_side_bias_delta = (
            float(side_bias_delta) if side_bias_delta is not None else None
        )
        normalized_appeal_overturn_rate = (
            float(appeal_overturn_rate) if appeal_overturn_rate is not None else None
        )
        stmt: Select[tuple[FairnessBenchmarkRunModel]] = select(FairnessBenchmarkRunModel).where(
            FairnessBenchmarkRunModel.run_id == normalized_run_id
        )
        async with self._session_factory() as session:
            async with session.begin():
                row = (await session.execute(stmt)).scalars().first()
                if row is None:
                    row = FairnessBenchmarkRunModel(
                        run_id=normalized_run_id,
                        created_at=now,
                    )
                    session.add(row)
                row.policy_version = normalized_policy_version
                row.environment_mode = normalized_environment_mode
                row.status = normalized_status
                row.threshold_decision = normalized_threshold_decision
                row.needs_real_env_reconfirm = bool(needs_real_env_reconfirm)
                row.needs_remediation = bool(needs_remediation)
                row.sample_size = normalized_sample_size
                row.draw_rate = normalized_draw_rate
                row.side_bias_delta = normalized_side_bias_delta
                row.appeal_overturn_rate = normalized_appeal_overturn_rate
                row.thresholds = dict(thresholds or {})
                row.metrics = dict(metrics or {})
                row.summary = dict(summary or {})
                row.source = normalized_source
                row.reported_by = normalized_reported_by
                row.reported_at = normalized_reported_at
                row.updated_at = now
            await session.refresh(row)
            return self._to_fairness_benchmark_run(row)

    async def list_fairness_benchmark_runs(
        self,
        *,
        policy_version: str | None = None,
        environment_mode: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[FairnessBenchmarkRun]:
        stmt: Select[tuple[FairnessBenchmarkRunModel]] = (
            select(FairnessBenchmarkRunModel)
            .order_by(
                FairnessBenchmarkRunModel.reported_at.desc(),
                FairnessBenchmarkRunModel.id.desc(),
            )
            .limit(max(1, min(500, int(limit))))
        )
        if policy_version is not None:
            stmt = stmt.where(
                FairnessBenchmarkRunModel.policy_version
                == (str(policy_version).strip() or "fairness-benchmark-v1")
            )
        if environment_mode is not None:
            stmt = stmt.where(
                FairnessBenchmarkRunModel.environment_mode
                == (_normalize_token(environment_mode) or "blocked")
            )
        if status is not None:
            stmt = stmt.where(
                FairnessBenchmarkRunModel.status
                == (_normalize_token(status) or "pending_data")
            )
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).scalars().all()
            return [self._to_fairness_benchmark_run(row) for row in rows]

    async def upsert_fairness_shadow_run(
        self,
        *,
        run_id: str,
        policy_version: str,
        benchmark_run_id: str | None,
        environment_mode: str,
        status: str,
        threshold_decision: str,
        needs_real_env_reconfirm: bool,
        needs_remediation: bool,
        sample_size: int | None,
        winner_flip_rate: float | None,
        score_shift_delta: float | None,
        review_required_delta: float | None,
        thresholds: dict[str, Any] | None,
        metrics: dict[str, Any] | None,
        summary: dict[str, Any] | None,
        source: str | None,
        reported_by: str | None,
        reported_at: datetime | None = None,
    ) -> FairnessShadowRun:
        now = _utcnow()
        normalized_run_id = str(run_id or "").strip()
        if not normalized_run_id:
            raise ValueError("invalid_fairness_shadow_run_id")
        normalized_policy_version = str(policy_version or "").strip() or "fairness-benchmark-v1"
        normalized_benchmark_run_id = str(benchmark_run_id or "").strip() or None
        normalized_environment_mode = _normalize_token(environment_mode) or "blocked"
        normalized_status = _normalize_token(status) or "pending_data"
        normalized_threshold_decision = _normalize_token(threshold_decision) or "pending"
        normalized_source = str(source or "").strip() or "manual"
        normalized_reported_by = str(reported_by or "").strip() or "system"
        normalized_reported_at = _normalize_dt(reported_at) if reported_at else now
        normalized_sample_size = max(0, int(sample_size)) if sample_size is not None else None
        normalized_winner_flip_rate = float(winner_flip_rate) if winner_flip_rate is not None else None
        normalized_score_shift_delta = float(score_shift_delta) if score_shift_delta is not None else None
        normalized_review_required_delta = (
            float(review_required_delta) if review_required_delta is not None else None
        )
        stmt: Select[tuple[FairnessShadowRunModel]] = select(FairnessShadowRunModel).where(
            FairnessShadowRunModel.run_id == normalized_run_id
        )
        async with self._session_factory() as session:
            async with session.begin():
                row = (await session.execute(stmt)).scalars().first()
                if row is None:
                    row = FairnessShadowRunModel(
                        run_id=normalized_run_id,
                        created_at=now,
                    )
                    session.add(row)
                row.policy_version = normalized_policy_version
                row.benchmark_run_id = normalized_benchmark_run_id
                row.environment_mode = normalized_environment_mode
                row.status = normalized_status
                row.threshold_decision = normalized_threshold_decision
                row.needs_real_env_reconfirm = bool(needs_real_env_reconfirm)
                row.needs_remediation = bool(needs_remediation)
                row.sample_size = normalized_sample_size
                row.winner_flip_rate = normalized_winner_flip_rate
                row.score_shift_delta = normalized_score_shift_delta
                row.review_required_delta = normalized_review_required_delta
                row.thresholds = dict(thresholds or {})
                row.metrics = dict(metrics or {})
                row.summary = dict(summary or {})
                row.source = normalized_source
                row.reported_by = normalized_reported_by
                row.reported_at = normalized_reported_at
                row.updated_at = now
            await session.refresh(row)
            return self._to_fairness_shadow_run(row)

    async def list_fairness_shadow_runs(
        self,
        *,
        policy_version: str | None = None,
        benchmark_run_id: str | None = None,
        environment_mode: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[FairnessShadowRun]:
        stmt: Select[tuple[FairnessShadowRunModel]] = (
            select(FairnessShadowRunModel)
            .order_by(
                FairnessShadowRunModel.reported_at.desc(),
                FairnessShadowRunModel.id.desc(),
            )
            .limit(max(1, min(500, int(limit))))
        )
        if policy_version is not None:
            stmt = stmt.where(
                FairnessShadowRunModel.policy_version
                == (str(policy_version).strip() or "fairness-benchmark-v1")
            )
        if benchmark_run_id is not None:
            stmt = stmt.where(
                FairnessShadowRunModel.benchmark_run_id
                == (str(benchmark_run_id).strip() or None)
            )
        if environment_mode is not None:
            stmt = stmt.where(
                FairnessShadowRunModel.environment_mode
                == (_normalize_token(environment_mode) or "blocked")
            )
        if status is not None:
            stmt = stmt.where(
                FairnessShadowRunModel.status
                == (_normalize_token(status) or "pending_data")
            )
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).scalars().all()
            return [self._to_fairness_shadow_run(row) for row in rows]

    async def upsert_audit_alert(
        self,
        *,
        alert_id: str | None = None,
        job_id: int,
        scope_id: int,
        trace_id: str,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        details: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> AuditAlert:
        now_dt = _normalize_dt(now) if now else _utcnow()
        normalized_alert_id = str(alert_id or "").strip()
        norm_type = _normalize_token(alert_type) or "unknown"
        norm_severity = _normalize_token(severity) or "warning"
        norm_title = str(title or "AI Judge Alert").strip() or "AI Judge Alert"
        norm_message = str(message or "ai_judge alert raised").strip() or "ai_judge alert raised"
        norm_details = dict(details or {})

        by_alert_id_stmt: Select[tuple[AuditAlertModel]] | None = None
        if normalized_alert_id:
            by_alert_id_stmt = select(AuditAlertModel).where(
                AuditAlertModel.alert_id == normalized_alert_id
            )
        stmt: Select[tuple[AuditAlertModel]] = (
            select(AuditAlertModel)
            .where(AuditAlertModel.job_id == int(job_id))
            .order_by(AuditAlertModel.updated_at.desc(), AuditAlertModel.id.desc())
            .limit(200)
        )
        async with self._session_factory() as session:
            async with session.begin():
                row = None
                if by_alert_id_stmt is not None:
                    row = (await session.execute(by_alert_id_stmt)).scalars().first()
                if row is not None:
                    row.scope_id = max(0, int(scope_id))
                    row.trace_id = str(trace_id or "").strip() or row.trace_id
                    row.alert_type = norm_type
                    row.severity = norm_severity
                    row.title = norm_title
                    row.message = norm_message
                    row.details = norm_details
                    row.updated_at = now_dt
                    await session.flush()
                    await session.refresh(row)
                    return self._to_audit_alert(row)

                candidates = (await session.execute(stmt)).scalars().all()
                existing = next(
                    (
                        row
                        for row in candidates
                        if row.status != ALERT_STATUS_RESOLVED
                        and row.alert_type == norm_type
                        and row.severity == norm_severity
                        and row.title == norm_title
                        and row.message == norm_message
                        and (row.details if isinstance(row.details, dict) else {}) == norm_details
                    ),
                    None,
                )
                if existing is None:
                    row = AuditAlertModel(
                        alert_id=normalized_alert_id or f"al-{job_id}-{uuid4().hex[:12]}",
                        job_id=int(job_id),
                        scope_id=max(0, int(scope_id)),
                        trace_id=str(trace_id or "").strip(),
                        alert_type=norm_type,
                        severity=norm_severity,
                        title=norm_title,
                        message=norm_message,
                        details=norm_details,
                        status=ALERT_STATUS_RAISED,
                        created_at=now_dt,
                        updated_at=now_dt,
                    )
                    session.add(row)
                else:
                    row = existing
                    row.trace_id = str(trace_id or "").strip() or row.trace_id
                    row.updated_at = now_dt
            await session.refresh(row)
            return self._to_audit_alert(row)

    async def transition_audit_alert(
        self,
        *,
        alert_id: str,
        to_status: str,
        now: datetime | None = None,
    ) -> AuditAlert | None:
        target = _normalize_alert_status(to_status)
        now_dt = _normalize_dt(now) if now else _utcnow()
        stmt: Select[tuple[AuditAlertModel]] = select(AuditAlertModel).where(
            AuditAlertModel.alert_id == str(alert_id or "").strip()
        )
        async with self._session_factory() as session:
            async with session.begin():
                row = (await session.execute(stmt)).scalars().first()
                if row is None:
                    return None
                if not _allow_alert_transition(from_status=row.status, to_status=target):
                    return None
                if row.status != target:
                    row.status = target
                    row.updated_at = now_dt
                    if target == ALERT_STATUS_ACKED and row.acknowledged_at is None:
                        row.acknowledged_at = now_dt
                    if target == ALERT_STATUS_RESOLVED:
                        row.resolved_at = now_dt
            await session.refresh(row)
            return self._to_audit_alert(row)

    async def list_audit_alerts(
        self,
        *,
        job_id: int | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[AuditAlert]:
        stmt: Select[tuple[AuditAlertModel]] = (
            select(AuditAlertModel)
            .order_by(AuditAlertModel.updated_at.desc(), AuditAlertModel.id.desc())
            .limit(max(1, min(1000, int(limit))))
        )
        if job_id is not None:
            stmt = stmt.where(AuditAlertModel.job_id == int(job_id))
        if status is not None:
            stmt = stmt.where(AuditAlertModel.status == _normalize_alert_status(status))

        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).scalars().all()
            return [self._to_audit_alert(row) for row in rows]

    def _to_dispatch_receipt(self, row: DispatchReceiptModel) -> DispatchReceipt:
        return DispatchReceipt(
            dispatch_type=row.dispatch_type,
            job_id=row.job_id,
            scope_id=row.scope_id,
            session_id=row.session_id,
            trace_id=row.trace_id,
            idempotency_key=row.idempotency_key,
            rubric_version=row.rubric_version,
            judge_policy_version=row.judge_policy_version,
            topic_domain=row.topic_domain,
            retrieval_profile=row.retrieval_profile,
            phase_no=row.phase_no,
            phase_start_no=row.phase_start_no,
            phase_end_no=row.phase_end_no,
            message_start_id=row.message_start_id,
            message_end_id=row.message_end_id,
            message_count=row.message_count,
            status=row.status,
            request=row.request if isinstance(row.request, dict) else {},
            response=row.response if isinstance(row.response, dict) else None,
            created_at=_normalize_dt(row.created_at),
            updated_at=_normalize_dt(row.updated_at),
        )

    def _to_replay_record(self, row: ReplayRecordModel) -> ReplayRecord:
        return ReplayRecord(
            dispatch_type=row.dispatch_type,
            job_id=row.job_id,
            trace_id=row.trace_id,
            winner=row.winner,
            needs_draw_vote=row.needs_draw_vote,
            provider=row.provider,
            report_payload=row.report_payload if isinstance(row.report_payload, dict) else {},
            created_at=_normalize_dt(row.created_at),
        )

    def _to_audit_alert(self, row: AuditAlertModel) -> AuditAlert:
        return AuditAlert(
            alert_id=row.alert_id,
            job_id=row.job_id,
            scope_id=row.scope_id,
            trace_id=row.trace_id,
            alert_type=row.alert_type,
            severity=row.severity,
            title=row.title,
            message=row.message,
            details=row.details if isinstance(row.details, dict) else {},
            status=row.status,
            created_at=_normalize_dt(row.created_at),
            updated_at=_normalize_dt(row.updated_at),
            acknowledged_at=_normalize_dt(row.acknowledged_at) if row.acknowledged_at else None,
            resolved_at=_normalize_dt(row.resolved_at) if row.resolved_at else None,
        )

    def _to_claim_ledger_record(self, row: ClaimLedgerRecordModel) -> ClaimLedgerRecord:
        return ClaimLedgerRecord(
            case_id=row.case_id,
            dispatch_type=row.dispatch_type,
            trace_id=row.trace_id,
            case_dossier=row.case_dossier if isinstance(row.case_dossier, dict) else {},
            claim_graph=row.claim_graph if isinstance(row.claim_graph, dict) else {},
            claim_graph_summary=(
                row.claim_graph_summary
                if isinstance(row.claim_graph_summary, dict)
                else {}
            ),
            evidence_ledger=row.evidence_ledger if isinstance(row.evidence_ledger, dict) else {},
            verdict_evidence_refs=[
                dict(item)
                for item in (row.verdict_evidence_refs or [])
                if isinstance(item, dict)
            ],
            created_at=_normalize_dt(row.created_at),
            updated_at=_normalize_dt(row.updated_at),
        )

    def _to_fairness_benchmark_run(
        self,
        row: FairnessBenchmarkRunModel,
    ) -> FairnessBenchmarkRun:
        return FairnessBenchmarkRun(
            run_id=row.run_id,
            policy_version=row.policy_version,
            environment_mode=row.environment_mode,
            status=row.status,
            threshold_decision=row.threshold_decision,
            needs_real_env_reconfirm=bool(row.needs_real_env_reconfirm),
            needs_remediation=bool(row.needs_remediation),
            sample_size=row.sample_size,
            draw_rate=(float(row.draw_rate) if row.draw_rate is not None else None),
            side_bias_delta=(
                float(row.side_bias_delta) if row.side_bias_delta is not None else None
            ),
            appeal_overturn_rate=(
                float(row.appeal_overturn_rate)
                if row.appeal_overturn_rate is not None
                else None
            ),
            thresholds=row.thresholds if isinstance(row.thresholds, dict) else {},
            metrics=row.metrics if isinstance(row.metrics, dict) else {},
            summary=row.summary if isinstance(row.summary, dict) else {},
            source=row.source,
            reported_by=row.reported_by,
            reported_at=_normalize_dt(row.reported_at),
            created_at=_normalize_dt(row.created_at),
            updated_at=_normalize_dt(row.updated_at),
        )

    def _to_fairness_shadow_run(
        self,
        row: FairnessShadowRunModel,
    ) -> FairnessShadowRun:
        return FairnessShadowRun(
            run_id=row.run_id,
            policy_version=row.policy_version,
            benchmark_run_id=row.benchmark_run_id,
            environment_mode=row.environment_mode,
            status=row.status,
            threshold_decision=row.threshold_decision,
            needs_real_env_reconfirm=bool(row.needs_real_env_reconfirm),
            needs_remediation=bool(row.needs_remediation),
            sample_size=row.sample_size,
            winner_flip_rate=(
                float(row.winner_flip_rate) if row.winner_flip_rate is not None else None
            ),
            score_shift_delta=(
                float(row.score_shift_delta) if row.score_shift_delta is not None else None
            ),
            review_required_delta=(
                float(row.review_required_delta) if row.review_required_delta is not None else None
            ),
            thresholds=row.thresholds if isinstance(row.thresholds, dict) else {},
            metrics=row.metrics if isinstance(row.metrics, dict) else {},
            summary=row.summary if isinstance(row.summary, dict) else {},
            source=row.source,
            reported_by=row.reported_by,
            reported_at=_normalize_dt(row.reported_at),
            created_at=_normalize_dt(row.created_at),
            updated_at=_normalize_dt(row.updated_at),
        )
