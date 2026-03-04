from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
from threading import Lock
from typing import Any, Protocol


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        raw = value.strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(raw)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except Exception:
            return _utcnow()
    return _utcnow()


def _decode_blob(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except Exception:
            return ""
    return str(value)


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


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


@dataclass
class TopicMemoryRecord:
    created_at: datetime
    job_id: int
    trace_id: str
    topic_domain: str
    rubric_version: str
    winner: str | None
    rationale: str
    evidence_refs: list[dict[str, Any]]
    provider: str | None


class TraceStoreProtocol(Protocol):
    def register_start(self, *, job_id: int, trace_id: str, request: dict[str, Any]) -> TraceRecord:
        ...

    def register_success(
        self,
        *,
        job_id: int,
        response: dict[str, Any],
        callback_status: str,
        report_summary: dict[str, Any],
    ) -> None:
        ...

    def register_failure(
        self,
        *,
        job_id: int,
        response: dict[str, Any],
        callback_status: str,
        callback_error: str,
    ) -> None:
        ...

    def set_idempotency_pending(self, *, key: str, job_id: int, ttl_secs: int | None = None) -> None:
        ...

    def set_idempotency_success(
        self,
        *,
        key: str,
        job_id: int,
        response: dict[str, Any],
        ttl_secs: int | None = None,
    ) -> None:
        ...

    def get_idempotency(self, key: str) -> IdempotencyRecord | None:
        ...

    def get_trace(self, job_id: int) -> TraceRecord | None:
        ...

    def mark_replay(
        self,
        *,
        job_id: int,
        winner: str | None,
        needs_draw_vote: bool | None,
        provider: str | None,
    ) -> None:
        ...

    def save_topic_memory(
        self,
        *,
        job_id: int,
        trace_id: str,
        topic_domain: str,
        rubric_version: str,
        winner: str | None,
        rationale: str,
        evidence_refs: list[dict[str, Any]] | None,
        provider: str | None,
    ) -> None:
        ...

    def list_topic_memory(
        self,
        *,
        topic_domain: str,
        rubric_version: str,
        limit: int = 3,
    ) -> list[TopicMemoryRecord]:
        ...


class TraceStore(TraceStoreProtocol):
    """In-memory trace + idempotency + topic memory store.

    This is process-local and works as the fail-open fallback when Redis is
    disabled/unavailable.
    """

    def __init__(self, *, ttl_secs: int = 86400, topic_memory_limit: int = 5) -> None:
        self._ttl_secs = max(60, ttl_secs)
        self._topic_memory_limit = max(1, topic_memory_limit)
        self._lock = Lock()
        self._traces: dict[int, TraceRecord] = {}
        self._idempotency: dict[str, IdempotencyRecord] = {}
        self._topic_memory: dict[str, list[TopicMemoryRecord]] = {}

    def _topic_key(self, topic_domain: str, rubric_version: str) -> str:
        return f"{topic_domain.strip().lower()}::{rubric_version.strip().lower()}"

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

        for topic_key, rows in list(self._topic_memory.items()):
            filtered = [
                row
                for row in rows
                if row.created_at + timedelta(seconds=self._ttl_secs) >= now
            ]
            if filtered:
                self._topic_memory[topic_key] = filtered[: self._topic_memory_limit]
                continue
            self._topic_memory.pop(topic_key, None)

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

    def save_topic_memory(
        self,
        *,
        job_id: int,
        trace_id: str,
        topic_domain: str,
        rubric_version: str,
        winner: str | None,
        rationale: str,
        evidence_refs: list[dict[str, Any]] | None,
        provider: str | None,
    ) -> None:
        now = _utcnow()
        domain = topic_domain.strip().lower()
        rubric = rubric_version.strip().lower()
        if not domain or not rubric:
            return
        if not rationale.strip() and not (evidence_refs or []):
            return
        row = TopicMemoryRecord(
            created_at=now,
            job_id=job_id,
            trace_id=trace_id,
            topic_domain=domain,
            rubric_version=rubric,
            winner=winner,
            rationale=rationale.strip(),
            evidence_refs=[item for item in (evidence_refs or []) if isinstance(item, dict)],
            provider=provider,
        )
        with self._lock:
            self._prune_locked(now)
            topic_key = self._topic_key(domain, rubric)
            rows = self._topic_memory.setdefault(topic_key, [])
            rows.insert(0, row)
            del rows[self._topic_memory_limit :]

    def list_topic_memory(
        self,
        *,
        topic_domain: str,
        rubric_version: str,
        limit: int = 3,
    ) -> list[TopicMemoryRecord]:
        now = _utcnow()
        if limit <= 0:
            return []
        domain = topic_domain.strip().lower()
        rubric = rubric_version.strip().lower()
        if not domain or not rubric:
            return []
        with self._lock:
            self._prune_locked(now)
            rows = self._topic_memory.get(self._topic_key(domain, rubric), [])
            return list(rows[: max(1, limit)])


class RedisTraceStore(TraceStoreProtocol):
    def __init__(
        self,
        *,
        redis_client: Any,
        ttl_secs: int = 86400,
        key_prefix: str = "ai_judge:v2",
        topic_memory_limit: int = 5,
    ) -> None:
        self._redis = redis_client
        self._ttl_secs = max(60, ttl_secs)
        self._key_prefix = key_prefix.strip().rstrip(":") or "ai_judge:v2"
        self._topic_memory_limit = max(1, topic_memory_limit)

    def _runtime_key(self, job_id: int) -> str:
        return f"{self._key_prefix}:job:{job_id}:runtime"

    def _stage_key(self, job_id: int, stage_no: int) -> str:
        return f"{self._key_prefix}:job:{job_id}:stage:{stage_no}"

    def _idempotency_key(self, key: str) -> str:
        return f"{self._key_prefix}:idempotency:{key}"

    def _topic_key(self, topic_domain: str, rubric_version: str) -> str:
        domain = topic_domain.strip().lower()
        rubric = rubric_version.strip().lower()
        return f"{self._key_prefix}:topic:{domain}:{rubric}"

    def _write_json(self, key: str, payload: dict[str, Any], *, ttl_secs: int | None = None) -> None:
        try:
            self._redis.set(
                key,
                json.dumps(payload, ensure_ascii=False),
                ex=max(60, ttl_secs or self._ttl_secs),
            )
        except Exception:
            return

    def _read_json(self, key: str) -> dict[str, Any] | None:
        try:
            raw = self._redis.get(key)
        except Exception:
            return None
        text = _decode_blob(raw)
        if not text:
            return None
        try:
            payload = json.loads(text)
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    def _serialize_trace(self, record: TraceRecord) -> dict[str, Any]:
        return {
            "job_id": record.job_id,
            "trace_id": record.trace_id,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
            "request": record.request,
            "status": record.status,
            "response": record.response,
            "callback_status": record.callback_status,
            "callback_error": record.callback_error,
            "report_summary": record.report_summary,
            "replays": [
                {
                    "replayed_at": replay.replayed_at.isoformat(),
                    "winner": replay.winner,
                    "needs_draw_vote": replay.needs_draw_vote,
                    "provider": replay.provider,
                }
                for replay in record.replays
            ],
        }

    def _deserialize_trace(self, payload: dict[str, Any]) -> TraceRecord:
        raw_replays = payload.get("replays")
        replays: list[TraceReplayRecord] = []
        if isinstance(raw_replays, list):
            for row in raw_replays:
                if not isinstance(row, dict):
                    continue
                replays.append(
                    TraceReplayRecord(
                        replayed_at=_parse_datetime(row.get("replayed_at")),
                        winner=row.get("winner"),
                        needs_draw_vote=row.get("needs_draw_vote"),
                        provider=row.get("provider"),
                    )
                )
        request = payload.get("request")
        response = payload.get("response")
        report_summary = payload.get("report_summary")
        return TraceRecord(
            job_id=_coerce_int(payload.get("job_id"), default=0),
            trace_id=str(payload.get("trace_id") or ""),
            created_at=_parse_datetime(payload.get("created_at")),
            updated_at=_parse_datetime(payload.get("updated_at")),
            request=request if isinstance(request, dict) else {},
            status=str(payload.get("status") or "unknown"),
            response=response if isinstance(response, dict) else None,
            callback_status=(str(payload.get("callback_status")) if payload.get("callback_status") is not None else None),
            callback_error=(str(payload.get("callback_error")) if payload.get("callback_error") is not None else None),
            report_summary=report_summary if isinstance(report_summary, dict) else None,
            replays=replays,
        )

    def _deserialize_idempotency(self, key: str, payload: dict[str, Any]) -> IdempotencyRecord:
        response = payload.get("response")
        return IdempotencyRecord(
            key=key,
            job_id=_coerce_int(payload.get("job_id"), default=0),
            response=response if isinstance(response, dict) else None,
            expires_at=_parse_datetime(payload.get("expires_at")),
        )

    def _read_trace(self, job_id: int) -> TraceRecord | None:
        payload = self._read_json(self._runtime_key(job_id))
        if payload is None:
            return None
        return self._deserialize_trace(payload)

    def register_start(self, *, job_id: int, trace_id: str, request: dict[str, Any]) -> TraceRecord:
        now = _utcnow()
        record = TraceRecord(
            job_id=job_id,
            trace_id=trace_id,
            created_at=now,
            updated_at=now,
            request=request,
            status="running",
        )
        self._write_json(self._runtime_key(job_id), self._serialize_trace(record))
        return record

    def register_success(
        self,
        *,
        job_id: int,
        response: dict[str, Any],
        callback_status: str,
        report_summary: dict[str, Any],
    ) -> None:
        record = self._read_trace(job_id)
        if record is None:
            return
        record.updated_at = _utcnow()
        record.status = "completed"
        record.response = response
        record.callback_status = callback_status
        record.report_summary = report_summary
        self._write_json(self._runtime_key(job_id), self._serialize_trace(record))

        raw_stages = report_summary.get("stage_summaries") or report_summary.get("stageSummaries")
        if not isinstance(raw_stages, list):
            return
        for index, row in enumerate(raw_stages):
            if not isinstance(row, dict):
                continue
            stage_no = _coerce_int(row.get("stage_no") or row.get("stageNo"), default=index + 1)
            self._write_json(self._stage_key(job_id, stage_no), row)

    def register_failure(
        self,
        *,
        job_id: int,
        response: dict[str, Any],
        callback_status: str,
        callback_error: str,
    ) -> None:
        record = self._read_trace(job_id)
        if record is None:
            return
        record.updated_at = _utcnow()
        record.status = "failed"
        record.response = response
        record.callback_status = callback_status
        record.callback_error = callback_error
        self._write_json(self._runtime_key(job_id), self._serialize_trace(record))

    def set_idempotency_pending(self, *, key: str, job_id: int, ttl_secs: int | None = None) -> None:
        now = _utcnow()
        expires_at = now + timedelta(seconds=max(60, ttl_secs or self._ttl_secs))
        self._write_json(
            self._idempotency_key(key),
            {
                "key": key,
                "job_id": job_id,
                "response": None,
                "expires_at": expires_at.isoformat(),
            },
            ttl_secs=ttl_secs,
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
        self._write_json(
            self._idempotency_key(key),
            {
                "key": key,
                "job_id": job_id,
                "response": response,
                "expires_at": expires_at.isoformat(),
            },
            ttl_secs=ttl_secs,
        )

    def get_idempotency(self, key: str) -> IdempotencyRecord | None:
        payload = self._read_json(self._idempotency_key(key))
        if payload is None:
            return None
        return self._deserialize_idempotency(key, payload)

    def get_trace(self, job_id: int) -> TraceRecord | None:
        return self._read_trace(job_id)

    def mark_replay(
        self,
        *,
        job_id: int,
        winner: str | None,
        needs_draw_vote: bool | None,
        provider: str | None,
    ) -> None:
        record = self._read_trace(job_id)
        if record is None:
            return
        now = _utcnow()
        record.updated_at = now
        record.replays.append(
            TraceReplayRecord(
                replayed_at=now,
                winner=winner,
                needs_draw_vote=needs_draw_vote,
                provider=provider,
            )
        )
        self._write_json(self._runtime_key(job_id), self._serialize_trace(record))

    def save_topic_memory(
        self,
        *,
        job_id: int,
        trace_id: str,
        topic_domain: str,
        rubric_version: str,
        winner: str | None,
        rationale: str,
        evidence_refs: list[dict[str, Any]] | None,
        provider: str | None,
    ) -> None:
        domain = topic_domain.strip().lower()
        rubric = rubric_version.strip().lower()
        if not domain or not rubric:
            return
        if not rationale.strip() and not (evidence_refs or []):
            return
        payload = {
            "created_at": _utcnow().isoformat(),
            "job_id": job_id,
            "trace_id": trace_id,
            "topic_domain": domain,
            "rubric_version": rubric,
            "winner": winner,
            "rationale": rationale.strip(),
            "evidence_refs": [item for item in (evidence_refs or []) if isinstance(item, dict)],
            "provider": provider,
        }
        key = self._topic_key(domain, rubric)
        try:
            self._redis.lpush(key, json.dumps(payload, ensure_ascii=False))
            self._redis.ltrim(key, 0, self._topic_memory_limit - 1)
            self._redis.expire(key, self._ttl_secs)
        except Exception:
            return

    def list_topic_memory(
        self,
        *,
        topic_domain: str,
        rubric_version: str,
        limit: int = 3,
    ) -> list[TopicMemoryRecord]:
        if limit <= 0:
            return []
        key = self._topic_key(topic_domain, rubric_version)
        try:
            rows = self._redis.lrange(key, 0, max(0, limit - 1))
        except Exception:
            return []
        out: list[TopicMemoryRecord] = []
        for raw in rows:
            text = _decode_blob(raw)
            if not text:
                continue
            try:
                payload = json.loads(text)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            evidence_refs = payload.get("evidence_refs")
            out.append(
                TopicMemoryRecord(
                    created_at=_parse_datetime(payload.get("created_at")),
                    job_id=_coerce_int(payload.get("job_id"), default=0),
                    trace_id=str(payload.get("trace_id") or ""),
                    topic_domain=str(payload.get("topic_domain") or ""),
                    rubric_version=str(payload.get("rubric_version") or ""),
                    winner=payload.get("winner"),
                    rationale=str(payload.get("rationale") or ""),
                    evidence_refs=(
                        [item for item in evidence_refs if isinstance(item, dict)]
                        if isinstance(evidence_refs, list)
                        else []
                    ),
                    provider=payload.get("provider"),
                )
            )
        return out


def _build_redis_client(*, url: str, pool_size: int) -> Any | None:
    try:
        import redis  # type: ignore
    except Exception:
        return None
    try:
        return redis.Redis.from_url(
            url,
            max_connections=max(1, pool_size),
            socket_timeout=1.5,
            socket_connect_timeout=1.5,
        )
    except Exception:
        return None


def build_trace_store_from_settings(*, settings: Any) -> TraceStoreProtocol:
    fallback = TraceStore(
        ttl_secs=getattr(settings, "trace_ttl_secs", 86400),
        topic_memory_limit=getattr(settings, "topic_memory_limit", 5),
    )
    if not bool(getattr(settings, "redis_enabled", False)):
        return fallback

    redis_client = _build_redis_client(
        url=str(getattr(settings, "redis_url", "")),
        pool_size=_coerce_int(getattr(settings, "redis_pool_size", 20), default=20),
    )
    if redis_client is None:
        if bool(getattr(settings, "redis_required", False)):
            raise RuntimeError("redis_enabled=true but redis client import/init failed")
        return fallback

    try:
        redis_client.ping()
    except Exception as err:
        if bool(getattr(settings, "redis_required", False)):
            raise RuntimeError(f"redis_enabled=true but ping failed: {err}") from err
        return fallback

    return RedisTraceStore(
        redis_client=redis_client,
        ttl_secs=getattr(settings, "trace_ttl_secs", 86400),
        key_prefix=str(getattr(settings, "redis_key_prefix", "ai_judge:v2")),
        topic_memory_limit=getattr(settings, "topic_memory_limit", 5),
    )


__all__ = [
    "TraceStoreProtocol",
    "TraceStore",
    "RedisTraceStore",
    "TraceRecord",
    "TraceReplayRecord",
    "IdempotencyRecord",
    "TopicMemoryRecord",
    "build_trace_store_from_settings",
]
