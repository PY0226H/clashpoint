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
    DispatchReceipt,
    ReplayRecord,
)
from app.infra.db.models import AuditAlertModel, DispatchReceiptModel, ReplayRecordModel


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

    async def upsert_audit_alert(
        self,
        *,
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
        norm_type = _normalize_token(alert_type) or "unknown"
        norm_severity = _normalize_token(severity) or "warning"
        norm_title = str(title or "AI Judge Alert").strip() or "AI Judge Alert"
        norm_message = str(message or "ai_judge alert raised").strip() or "ai_judge alert raised"
        norm_details = dict(details or {})

        stmt: Select[tuple[AuditAlertModel]] = (
            select(AuditAlertModel)
            .where(AuditAlertModel.job_id == int(job_id))
            .order_by(AuditAlertModel.updated_at.desc(), AuditAlertModel.id.desc())
            .limit(200)
        )
        async with self._session_factory() as session:
            async with session.begin():
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
                        alert_id=f"al-{job_id}-{uuid4().hex[:12]}",
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
