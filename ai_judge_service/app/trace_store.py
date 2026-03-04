from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class TraceReplayRecord:
    replayed_at: datetime
    winner: str | None
    needs_draw_vote: bool | None
    provider: str | None


@dataclass
class TraceRecord:
    job_id: int
    trace_id: str
    created_at: datetime
    updated_at: datetime
    request: dict[str, Any]
    status: str
    response: dict[str, Any] | None = None
    callback_status: str | None = None
    callback_error: str | None = None
    report_summary: dict[str, Any] | None = None
    replays: list[TraceReplayRecord] = field(default_factory=list)


@dataclass
class IdempotencyRecord:
    key: str
    job_id: int
    response: dict[str, Any] | None
    expires_at: datetime


class TraceStore:
    """In-memory trace + idempotency store for ai_judge_service ops APIs.

    This is intentionally process-local for v2-m1 baseline and can be
    replaced by Redis/DB persistence in follow-up modules.
    """

    def __init__(self, *, ttl_secs: int = 86400) -> None:
        self._ttl_secs = max(60, ttl_secs)
        self._lock = Lock()
        self._traces: dict[int, TraceRecord] = {}
        self._idempotency: dict[str, IdempotencyRecord] = {}

    def _prune_locked(self, now: datetime) -> None:
        expired_jobs = [
            job_id
            for job_id, record in self._traces.items()
            if record.updated_at + timedelta(seconds=self._ttl_secs) < now
        ]
        for job_id in expired_jobs:
            self._traces.pop(job_id, None)

        expired_keys = [
            key for key, record in self._idempotency.items() if record.expires_at <= now
        ]
        for key in expired_keys:
            self._idempotency.pop(key, None)

    def register_start(self, *, job_id: int, trace_id: str, request: dict[str, Any]) -> TraceRecord:
        now = _utcnow()
        with self._lock:
            self._prune_locked(now)
            record = TraceRecord(
                job_id=job_id,
                trace_id=trace_id,
                created_at=now,
                updated_at=now,
                request=request,
                status="running",
            )
            self._traces[job_id] = record
            return record

    def register_success(
        self,
        *,
        job_id: int,
        response: dict[str, Any],
        callback_status: str,
        report_summary: dict[str, Any],
    ) -> None:
        now = _utcnow()
        with self._lock:
            record = self._traces.get(job_id)
            if record is None:
                return
            record.updated_at = now
            record.status = "completed"
            record.response = response
            record.callback_status = callback_status
            record.report_summary = report_summary

    def register_failure(
        self,
        *,
        job_id: int,
        response: dict[str, Any],
        callback_status: str,
        callback_error: str,
    ) -> None:
        now = _utcnow()
        with self._lock:
            record = self._traces.get(job_id)
            if record is None:
                return
            record.updated_at = now
            record.status = "failed"
            record.response = response
            record.callback_status = callback_status
            record.callback_error = callback_error

    def set_idempotency_pending(self, *, key: str, job_id: int, ttl_secs: int | None = None) -> None:
        now = _utcnow()
        expires_at = now + timedelta(seconds=max(60, ttl_secs or self._ttl_secs))
        with self._lock:
            self._prune_locked(now)
            self._idempotency[key] = IdempotencyRecord(
                key=key,
                job_id=job_id,
                response=None,
                expires_at=expires_at,
            )

    def set_idempotency_success(
        self,
        *,
        key: str,
        job_id: int,
        response: dict[str, Any],
        ttl_secs: int | None = None,
    ) -> None:
        now = _utcnow()
        expires_at = now + timedelta(seconds=max(60, ttl_secs or self._ttl_secs))
        with self._lock:
            self._prune_locked(now)
            self._idempotency[key] = IdempotencyRecord(
                key=key,
                job_id=job_id,
                response=response,
                expires_at=expires_at,
            )

    def get_idempotency(self, key: str) -> IdempotencyRecord | None:
        now = _utcnow()
        with self._lock:
            self._prune_locked(now)
            return self._idempotency.get(key)

    def get_trace(self, job_id: int) -> TraceRecord | None:
        now = _utcnow()
        with self._lock:
            self._prune_locked(now)
            return self._traces.get(job_id)

    def mark_replay(
        self,
        *,
        job_id: int,
        winner: str | None,
        needs_draw_vote: bool | None,
        provider: str | None,
    ) -> None:
        now = _utcnow()
        with self._lock:
            record = self._traces.get(job_id)
            if record is None:
                return
            record.updated_at = now
            record.replays.append(
                TraceReplayRecord(
                    replayed_at=now,
                    winner=winner,
                    needs_draw_vote=needs_draw_vote,
                    provider=provider,
                )
            )


__all__ = [
    "TraceStore",
    "TraceRecord",
    "TraceReplayRecord",
    "IdempotencyRecord",
]
