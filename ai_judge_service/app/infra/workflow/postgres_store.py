from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.workflow import WorkflowEvent, WorkflowJob, WorkflowPort
from app.infra.db.models import JudgeJobEventModel, JudgeJobModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_dt(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class PostgresWorkflowStore(WorkflowPort):
    def __init__(self, *, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def register_job(
        self,
        *,
        job: WorkflowJob,
        event_type: str,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowJob:
        now = _utcnow()
        async with self._session_factory() as session:
            async with session.begin():
                row = await session.get(JudgeJobModel, job.job_id)
                if row is None:
                    row = JudgeJobModel(
                        job_id=job.job_id,
                        dispatch_type=job.dispatch_type,
                        trace_id=job.trace_id,
                        status=job.status,
                        scope_id=job.scope_id,
                        session_id=job.session_id,
                        idempotency_key=job.idempotency_key,
                        rubric_version=job.rubric_version,
                        judge_policy_version=job.judge_policy_version,
                        topic_domain=job.topic_domain,
                        retrieval_profile=job.retrieval_profile,
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(row)
                else:
                    row.dispatch_type = job.dispatch_type
                    row.trace_id = job.trace_id
                    row.status = job.status
                    row.scope_id = job.scope_id
                    row.session_id = job.session_id
                    row.idempotency_key = job.idempotency_key
                    row.rubric_version = job.rubric_version
                    row.judge_policy_version = job.judge_policy_version
                    row.topic_domain = job.topic_domain
                    row.retrieval_profile = job.retrieval_profile
                    row.updated_at = now
                await self._append_event_locked(
                    session=session,
                    job_id=job.job_id,
                    event_type=event_type,
                    event_payload=event_payload,
                    created_at=now,
                )
            return self._to_job(row)

    async def transition_status(
        self,
        *,
        job_id: int,
        status: str,
        event_type: str,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowJob:
        now = _utcnow()
        async with self._session_factory() as session:
            async with session.begin():
                row = await session.get(JudgeJobModel, job_id)
                if row is None:
                    raise LookupError(f"workflow job not found: job_id={job_id}")
                row.status = status
                row.updated_at = now
                await self._append_event_locked(
                    session=session,
                    job_id=job_id,
                    event_type=event_type,
                    event_payload=event_payload,
                    created_at=now,
                )
            return self._to_job(row)

    async def append_event(
        self,
        *,
        job_id: int,
        event_type: str,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowEvent:
        now = _utcnow()
        async with self._session_factory() as session:
            async with session.begin():
                row = await session.get(JudgeJobModel, job_id)
                if row is None:
                    raise LookupError(f"workflow job not found: job_id={job_id}")
                row.updated_at = now
                event_row = await self._append_event_locked(
                    session=session,
                    job_id=job_id,
                    event_type=event_type,
                    event_payload=event_payload,
                    created_at=now,
                )
            return self._to_event(event_row)

    async def get_job(self, *, job_id: int) -> WorkflowJob | None:
        async with self._session_factory() as session:
            row = await session.get(JudgeJobModel, job_id)
            if row is None:
                return None
            return self._to_job(row)

    async def list_jobs(
        self,
        *,
        status: str | None = None,
        dispatch_type: str | None = None,
        limit: int = 50,
    ) -> list[WorkflowJob]:
        stmt: Select[tuple[JudgeJobModel]] = select(JudgeJobModel)
        if status:
            stmt = stmt.where(JudgeJobModel.status == status)
        if dispatch_type:
            stmt = stmt.where(JudgeJobModel.dispatch_type == dispatch_type)
        stmt = stmt.order_by(JudgeJobModel.updated_at.desc()).limit(max(1, int(limit)))
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).scalars().all()
            return [self._to_job(item) for item in rows]

    async def list_events(self, *, job_id: int) -> list[WorkflowEvent]:
        stmt: Select[tuple[JudgeJobEventModel]] = (
            select(JudgeJobEventModel)
            .where(JudgeJobEventModel.job_id == job_id)
            .order_by(JudgeJobEventModel.event_seq.asc())
        )
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).scalars().all()
            return [self._to_event(item) for item in rows]

    async def _append_event_locked(
        self,
        *,
        session: AsyncSession,
        job_id: int,
        event_type: str,
        event_payload: dict[str, Any] | None,
        created_at: datetime,
    ) -> JudgeJobEventModel:
        next_seq_stmt = select(func.max(JudgeJobEventModel.event_seq)).where(
            JudgeJobEventModel.job_id == job_id
        )
        current_max = (await session.execute(next_seq_stmt)).scalar_one_or_none() or 0
        row = JudgeJobEventModel(
            job_id=job_id,
            event_seq=int(current_max) + 1,
            event_type=event_type,
            payload=dict(event_payload or {}),
            created_at=created_at,
        )
        session.add(row)
        await session.flush()
        return row

    def _to_job(self, row: JudgeJobModel) -> WorkflowJob:
        return WorkflowJob(
            job_id=row.job_id,
            dispatch_type=row.dispatch_type,
            trace_id=row.trace_id,
            status=row.status,
            scope_id=row.scope_id,
            session_id=row.session_id,
            idempotency_key=row.idempotency_key,
            rubric_version=row.rubric_version,
            judge_policy_version=row.judge_policy_version,
            topic_domain=row.topic_domain,
            retrieval_profile=row.retrieval_profile,
            created_at=_normalize_dt(row.created_at),
            updated_at=_normalize_dt(row.updated_at),
        )

    def _to_event(self, row: JudgeJobEventModel) -> WorkflowEvent:
        payload = row.payload if isinstance(row.payload, dict) else {}
        return WorkflowEvent(
            job_id=row.job_id,
            event_seq=row.event_seq,
            event_type=row.event_type,
            payload=payload,
            created_at=_normalize_dt(row.created_at),
        )
