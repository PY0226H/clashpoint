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


IDEMPOTENCY_RESOLUTION_ACQUIRED = "acquired"
IDEMPOTENCY_RESOLUTION_REPLAY = "replay"
IDEMPOTENCY_RESOLUTION_CONFLICT = "conflict"
IDEMPOTENCY_RESOLUTION_VALUES = {
    IDEMPOTENCY_RESOLUTION_ACQUIRED,
    IDEMPOTENCY_RESOLUTION_REPLAY,
    IDEMPOTENCY_RESOLUTION_CONFLICT,
}
_RESOLVE_IDEMPOTENCY_LUA = """
local key = KEYS[1]
local pending_payload = ARGV[1]
local ttl_secs = tonumber(ARGV[2]) or 60
local job_id = tostring(ARGV[3] or "")

local existed = redis.call("GET", key)
if not existed then
  redis.call("SET", key, pending_payload, "EX", ttl_secs)
  return {"acquired", ""}
end

local ok, decoded = pcall(cjson.decode, existed)
if not ok or type(decoded) ~= "table" then
  return {"conflict", existed}
end

if tostring(decoded["job_id"] or "") ~= job_id then
  return {"conflict", existed}
end

if type(decoded["response"]) == "table" then
  return {"replay", existed}
end

return {"conflict", existed}
"""


@dataclass
class IdempotencyResolution:
    status: str
    record: IdempotencyRecord | None = None


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
    audit: dict[str, Any] = field(default_factory=dict)


ALERT_STATUS_RAISED = "raised"
ALERT_STATUS_ACKED = "acked"
ALERT_STATUS_RESOLVED = "resolved"
ALERT_STATUS_VALUES = {ALERT_STATUS_RAISED, ALERT_STATUS_ACKED, ALERT_STATUS_RESOLVED}

OUTBOX_DELIVERY_PENDING = "pending"
OUTBOX_DELIVERY_SENT = "sent"
OUTBOX_DELIVERY_FAILED = "failed"
OUTBOX_DELIVERY_VALUES = {
    OUTBOX_DELIVERY_PENDING,
    OUTBOX_DELIVERY_SENT,
    OUTBOX_DELIVERY_FAILED,
}

DISPATCH_TYPE_PHASE = "phase"
DISPATCH_TYPE_FINAL = "final"
DISPATCH_TYPE_VALUES = {DISPATCH_TYPE_PHASE, DISPATCH_TYPE_FINAL}


@dataclass
class TraceQuery:
    status: str | None = None
    winner: str | None = None
    callback_status: str | None = None
    trace_id: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    has_audit_alert: bool | None = None
    limit: int = 20


@dataclass
class AuditAlertTransition:
    from_status: str
    to_status: str
    actor: str | None
    reason: str | None
    changed_at: datetime


@dataclass
class AuditAlertRecord:
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
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    transitions: list[AuditAlertTransition] = field(default_factory=list)


@dataclass
class AlertOutboxEvent:
    event_id: str
    channel: str
    scope_id: int
    job_id: int
    trace_id: str
    alert_id: str
    status: str
    payload: dict[str, Any]
    delivery_status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime


@dataclass
class DispatchReceiptRecord:
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


def _normalize_alert_status(value: Any, *, default: str = ALERT_STATUS_RAISED) -> str:
    raw = _normalize_token(value)
    return raw if raw in ALERT_STATUS_VALUES else default


def _normalize_delivery_status(value: Any, *, default: str = OUTBOX_DELIVERY_PENDING) -> str:
    raw = _normalize_token(value)
    return raw if raw in OUTBOX_DELIVERY_VALUES else default


def _allowed_alert_transition(from_status: str, to_status: str) -> bool:
    src = _normalize_alert_status(from_status)
    dst = _normalize_alert_status(to_status)
    if src == dst:
        return True
    if src == ALERT_STATUS_RAISED and dst in {ALERT_STATUS_ACKED, ALERT_STATUS_RESOLVED}:
        return True
    if src == ALERT_STATUS_ACKED and dst == ALERT_STATUS_RESOLVED:
        return True
    return False


def _safe_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        return "{}"


def _normalize_token(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _normalize_dispatch_type(value: Any) -> str:
    raw = _normalize_token(value)
    if raw in DISPATCH_TYPE_VALUES:
        return raw
    return ""


def _record_winner(record: TraceRecord) -> str:
    if isinstance(record.response, dict):
        value = record.response.get("winner")
        if value:
            return _normalize_token(value)
    if isinstance(record.report_summary, dict):
        for key in ("winner", "winnerFirst", "winnerSecond", "winner_first", "winner_second"):
            value = record.report_summary.get(key)
            if value:
                return _normalize_token(value)
    return ""


def _record_has_audit_alert(record: TraceRecord) -> bool:
    if isinstance(record.response, dict) and isinstance(record.response.get("auditAlert"), dict):
        return True
    if not isinstance(record.report_summary, dict):
        return False
    payload = record.report_summary.get("payload")
    if not isinstance(payload, dict):
        return False
    alerts = payload.get("auditAlerts")
    return isinstance(alerts, list) and any(isinstance(item, dict) for item in alerts)


def _trace_matches(record: TraceRecord, query: TraceQuery) -> bool:
    status = _normalize_token(query.status)
    if status and _normalize_token(record.status) != status:
        return False

    callback_status = _normalize_token(query.callback_status)
    if callback_status and _normalize_token(record.callback_status) != callback_status:
        return False

    trace_id = _normalize_token(query.trace_id)
    if trace_id and _normalize_token(record.trace_id) != trace_id:
        return False

    winner = _normalize_token(query.winner)
    if winner and _record_winner(record) != winner:
        return False

    if query.created_after is not None and record.created_at < query.created_after:
        return False
    if query.created_before is not None and record.created_at > query.created_before:
        return False

    if query.has_audit_alert is not None and _record_has_audit_alert(record) != query.has_audit_alert:
        return False

    return True


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

    def resolve_idempotency(
        self,
        *,
        key: str,
        job_id: int,
        ttl_secs: int | None = None,
    ) -> IdempotencyResolution:
        ...

    def clear_idempotency(self, key: str) -> None:
        ...

    def get_trace(self, job_id: int) -> TraceRecord | None:
        ...

    def list_traces(self, *, query: TraceQuery | None = None) -> list[TraceRecord]:
        ...

    def upsert_audit_alert(
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
    ) -> AuditAlertRecord:
        ...

    def list_audit_alerts(
        self,
        *,
        job_id: int | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[AuditAlertRecord]:
        ...

    def transition_audit_alert(
        self,
        *,
        job_id: int,
        alert_id: str,
        to_status: str,
        actor: str | None = None,
        reason: str | None = None,
    ) -> AuditAlertRecord | None:
        ...

    def list_alert_outbox(
        self,
        *,
        delivery_status: str | None = None,
        limit: int = 50,
    ) -> list[AlertOutboxEvent]:
        ...

    def mark_alert_outbox_delivery(
        self,
        *,
        event_id: str,
        delivery_status: str,
        error_message: str | None = None,
    ) -> AlertOutboxEvent | None:
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
        audit: dict[str, Any] | None = None,
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

    def save_dispatch_receipt(
        self,
        *,
        dispatch_type: str,
        job_id: int,
        scope_id: int,
        session_id: int,
        trace_id: str,
        idempotency_key: str,
        rubric_version: str,
        judge_policy_version: str,
        topic_domain: str,
        retrieval_profile: str | None,
        phase_no: int | None,
        phase_start_no: int | None,
        phase_end_no: int | None,
        message_start_id: int | None,
        message_end_id: int | None,
        message_count: int | None,
        status: str,
        request: dict[str, Any],
        response: dict[str, Any] | None,
    ) -> DispatchReceiptRecord:
        ...

    def get_dispatch_receipt(
        self,
        *,
        dispatch_type: str,
        job_id: int,
    ) -> DispatchReceiptRecord | None:
        ...

    def list_dispatch_receipts(
        self,
        *,
        dispatch_type: str,
        session_id: int | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> list[DispatchReceiptRecord]:
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
        self._dispatch_receipts: dict[str, DispatchReceiptRecord] = {}
        self._alerts_by_job: dict[int, list[AuditAlertRecord]] = {}
        self._alerts_by_id: dict[str, AuditAlertRecord] = {}
        self._alert_outbox: dict[str, AlertOutboxEvent] = {}
        self._alert_outbox_order: list[str] = []
        self._alert_seq = 0
        self._event_seq = 0

    def _topic_key(self, topic_domain: str, rubric_version: str) -> str:
        return f"{topic_domain.strip().lower()}::{rubric_version.strip().lower()}"

    def _dispatch_receipt_key(self, dispatch_type: str, job_id: int) -> str:
        return f"{dispatch_type}:{job_id}"

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

        expired_dispatch_receipt_keys = [
            key
            for key, record in self._dispatch_receipts.items()
            if record.updated_at + timedelta(seconds=self._ttl_secs) < now
        ]
        for key in expired_dispatch_receipt_keys:
            self._dispatch_receipts.pop(key, None)

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

        expired_alert_job_ids: list[int] = []
        for job_id, rows in self._alerts_by_job.items():
            filtered_rows = [
                row
                for row in rows
                if row.updated_at + timedelta(seconds=self._ttl_secs) >= now
            ]
            if filtered_rows:
                self._alerts_by_job[job_id] = filtered_rows
                continue
            expired_alert_job_ids.append(job_id)
        for job_id in expired_alert_job_ids:
            self._alerts_by_job.pop(job_id, None)

        self._alerts_by_id = {
            row.alert_id: row
            for rows in self._alerts_by_job.values()
            for row in rows
        }

        expired_event_ids: list[str] = []
        for event_id, event in self._alert_outbox.items():
            if event.updated_at + timedelta(seconds=self._ttl_secs) < now:
                expired_event_ids.append(event_id)
        for event_id in expired_event_ids:
            self._alert_outbox.pop(event_id, None)
        self._alert_outbox_order = [
            event_id for event_id in self._alert_outbox_order if event_id in self._alert_outbox
        ]

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

    def resolve_idempotency(
        self,
        *,
        key: str,
        job_id: int,
        ttl_secs: int | None = None,
    ) -> IdempotencyResolution:
        now = _utcnow()
        expires_at = now + timedelta(seconds=max(60, ttl_secs or self._ttl_secs))
        with self._lock:
            self._prune_locked(now)
            existed = self._idempotency.get(key)
            if existed is None:
                record = IdempotencyRecord(
                    key=key,
                    job_id=job_id,
                    response=None,
                    expires_at=expires_at,
                )
                self._idempotency[key] = record
                return IdempotencyResolution(
                    status=IDEMPOTENCY_RESOLUTION_ACQUIRED,
                    record=record,
                )
            if existed.job_id != job_id:
                return IdempotencyResolution(
                    status=IDEMPOTENCY_RESOLUTION_CONFLICT,
                    record=existed,
                )
            if isinstance(existed.response, dict):
                return IdempotencyResolution(
                    status=IDEMPOTENCY_RESOLUTION_REPLAY,
                    record=existed,
                )
            return IdempotencyResolution(
                status=IDEMPOTENCY_RESOLUTION_CONFLICT,
                record=existed,
            )

    def clear_idempotency(self, key: str) -> None:
        with self._lock:
            self._idempotency.pop(key, None)

    def get_trace(self, job_id: int) -> TraceRecord | None:
        now = _utcnow()
        with self._lock:
            self._prune_locked(now)
            return self._traces.get(job_id)

    def list_traces(self, *, query: TraceQuery | None = None) -> list[TraceRecord]:
        now = _utcnow()
        with self._lock:
            self._prune_locked(now)
            q = query or TraceQuery()
            limit = max(1, min(200, q.limit))
            records = sorted(
                self._traces.values(),
                key=lambda item: item.updated_at,
                reverse=True,
            )
            out: list[TraceRecord] = []
            for record in records:
                if _trace_matches(record, q):
                    out.append(record)
                if len(out) >= limit:
                    break
            return out

    def _find_alert_locked(self, *, job_id: int, alert_id: str) -> AuditAlertRecord | None:
        rows = self._alerts_by_job.get(job_id, [])
        for row in rows:
            if row.alert_id == alert_id:
                return row
        return None

    def _enqueue_alert_event_locked(
        self,
        *,
        now: datetime,
        alert: AuditAlertRecord,
        status: str,
    ) -> AlertOutboxEvent:
        self._event_seq += 1
        event_id = f"evt-{alert.job_id}-{self._event_seq:06d}"
        payload = {
            "eventType": "ai_judge.audit_alert.status_changed.v1",
            "scopeId": alert.scope_id,
            "jobId": alert.job_id,
            "traceId": alert.trace_id,
            "alertId": alert.alert_id,
            "alertType": alert.alert_type,
            "severity": alert.severity,
            "status": status,
            "title": alert.title,
            "message": alert.message,
            "details": alert.details,
            "createdAt": now.isoformat(),
        }
        event = AlertOutboxEvent(
            event_id=event_id,
            channel="ai_judge_audit_alert",
            scope_id=alert.scope_id,
            job_id=alert.job_id,
            trace_id=alert.trace_id,
            alert_id=alert.alert_id,
            status=status,
            payload=payload,
            delivery_status=OUTBOX_DELIVERY_PENDING,
            error_message=None,
            created_at=now,
            updated_at=now,
        )
        self._alert_outbox[event_id] = event
        self._alert_outbox_order.insert(0, event_id)
        return event

    def upsert_audit_alert(
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
    ) -> AuditAlertRecord:
        now = _utcnow()
        norm_type = _normalize_token(alert_type) or "unknown"
        norm_severity = _normalize_token(severity) or "warning"
        norm_details = dict(details or {})
        fingerprint = _safe_json(
            {
                "type": norm_type,
                "severity": norm_severity,
                "title": title.strip(),
                "message": message.strip(),
                "details": norm_details,
            }
        )
        with self._lock:
            self._prune_locked(now)
            rows = self._alerts_by_job.setdefault(job_id, [])
            for existing in rows:
                if existing.status == ALERT_STATUS_RESOLVED:
                    continue
                existing_fp = _safe_json(
                    {
                        "type": existing.alert_type,
                        "severity": existing.severity,
                        "title": existing.title,
                        "message": existing.message,
                        "details": existing.details,
                    }
                )
                if existing_fp != fingerprint:
                    continue
                existing.updated_at = now
                if trace_id:
                    existing.trace_id = trace_id
                self._enqueue_alert_event_locked(
                    now=now,
                    alert=existing,
                    status=existing.status,
                )
                return existing

            self._alert_seq += 1
            alert = AuditAlertRecord(
                alert_id=f"al-{job_id}-{self._alert_seq:06d}",
                job_id=job_id,
                scope_id=max(0, scope_id),
                trace_id=trace_id,
                alert_type=norm_type,
                severity=norm_severity,
                title=title.strip() or "AI Judge Alert",
                message=message.strip() or "ai_judge alert raised",
                details=norm_details,
                status=ALERT_STATUS_RAISED,
                created_at=now,
                updated_at=now,
            )
            rows.insert(0, alert)
            self._alerts_by_id[alert.alert_id] = alert
            self._enqueue_alert_event_locked(
                now=now,
                alert=alert,
                status=ALERT_STATUS_RAISED,
            )
            return alert

    def list_audit_alerts(
        self,
        *,
        job_id: int | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[AuditAlertRecord]:
        now = _utcnow()
        with self._lock:
            self._prune_locked(now)
            norm_status = _normalize_alert_status(status, default="")
            out: list[AuditAlertRecord] = []
            if job_id is not None:
                rows = self._alerts_by_job.get(job_id, [])
                for row in rows:
                    if norm_status and row.status != norm_status:
                        continue
                    out.append(row)
                    if len(out) >= max(1, limit):
                        break
                return out

            all_rows = sorted(
                [row for rows in self._alerts_by_job.values() for row in rows],
                key=lambda item: item.updated_at,
                reverse=True,
            )
            for row in all_rows:
                if norm_status and row.status != norm_status:
                    continue
                out.append(row)
                if len(out) >= max(1, limit):
                    break
            return out

    def transition_audit_alert(
        self,
        *,
        job_id: int,
        alert_id: str,
        to_status: str,
        actor: str | None = None,
        reason: str | None = None,
    ) -> AuditAlertRecord | None:
        now = _utcnow()
        target_status = _normalize_alert_status(to_status)
        with self._lock:
            self._prune_locked(now)
            row = self._find_alert_locked(job_id=job_id, alert_id=alert_id)
            if row is None:
                return None
            if not _allowed_alert_transition(row.status, target_status):
                return None
            if row.status != target_status:
                transition = AuditAlertTransition(
                    from_status=row.status,
                    to_status=target_status,
                    actor=(actor or "").strip() or None,
                    reason=(reason or "").strip() or None,
                    changed_at=now,
                )
                row.transitions.append(transition)
                row.status = target_status
                row.updated_at = now
                if target_status == ALERT_STATUS_ACKED:
                    row.acknowledged_at = now
                if target_status == ALERT_STATUS_RESOLVED:
                    row.resolved_at = now
            self._enqueue_alert_event_locked(
                now=now,
                alert=row,
                status=row.status,
            )
            return row

    def list_alert_outbox(
        self,
        *,
        delivery_status: str | None = None,
        limit: int = 50,
    ) -> list[AlertOutboxEvent]:
        now = _utcnow()
        with self._lock:
            self._prune_locked(now)
            norm_status = _normalize_delivery_status(delivery_status, default="")
            out: list[AlertOutboxEvent] = []
            for event_id in self._alert_outbox_order:
                event = self._alert_outbox.get(event_id)
                if event is None:
                    continue
                if norm_status and event.delivery_status != norm_status:
                    continue
                out.append(event)
                if len(out) >= max(1, limit):
                    break
            return out

    def mark_alert_outbox_delivery(
        self,
        *,
        event_id: str,
        delivery_status: str,
        error_message: str | None = None,
    ) -> AlertOutboxEvent | None:
        now = _utcnow()
        target = _normalize_delivery_status(delivery_status)
        with self._lock:
            self._prune_locked(now)
            event = self._alert_outbox.get(event_id)
            if event is None:
                return None
            event.delivery_status = target
            event.error_message = (error_message or "").strip() or None
            event.updated_at = now
            return event

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
        audit: dict[str, Any] | None = None,
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
            audit=dict(audit or {}),
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

    def save_dispatch_receipt(
        self,
        *,
        dispatch_type: str,
        job_id: int,
        scope_id: int,
        session_id: int,
        trace_id: str,
        idempotency_key: str,
        rubric_version: str,
        judge_policy_version: str,
        topic_domain: str,
        retrieval_profile: str | None,
        phase_no: int | None,
        phase_start_no: int | None,
        phase_end_no: int | None,
        message_start_id: int | None,
        message_end_id: int | None,
        message_count: int | None,
        status: str,
        request: dict[str, Any],
        response: dict[str, Any] | None,
    ) -> DispatchReceiptRecord:
        normalized_dispatch_type = _normalize_dispatch_type(dispatch_type)
        if not normalized_dispatch_type:
            raise ValueError(f"unsupported dispatch_type: {dispatch_type}")
        now = _utcnow()
        receipt_key = self._dispatch_receipt_key(normalized_dispatch_type, max(0, job_id))
        with self._lock:
            self._prune_locked(now)
            existing = self._dispatch_receipts.get(receipt_key)
            created_at = existing.created_at if existing is not None else now
            row = DispatchReceiptRecord(
                dispatch_type=normalized_dispatch_type,
                job_id=max(0, job_id),
                scope_id=max(0, scope_id),
                session_id=max(0, session_id),
                trace_id=trace_id.strip(),
                idempotency_key=idempotency_key.strip(),
                rubric_version=rubric_version.strip(),
                judge_policy_version=judge_policy_version.strip(),
                topic_domain=topic_domain.strip().lower() or "default",
                retrieval_profile=(retrieval_profile.strip() if isinstance(retrieval_profile, str) else None),
                phase_no=phase_no,
                phase_start_no=phase_start_no,
                phase_end_no=phase_end_no,
                message_start_id=message_start_id,
                message_end_id=message_end_id,
                message_count=message_count,
                status=status.strip().lower() or "queued",
                request=dict(request),
                response=(dict(response) if isinstance(response, dict) else None),
                created_at=created_at,
                updated_at=now,
            )
            self._dispatch_receipts[receipt_key] = row
            return row

    def get_dispatch_receipt(
        self,
        *,
        dispatch_type: str,
        job_id: int,
    ) -> DispatchReceiptRecord | None:
        normalized_dispatch_type = _normalize_dispatch_type(dispatch_type)
        if not normalized_dispatch_type:
            return None
        now = _utcnow()
        with self._lock:
            self._prune_locked(now)
            return self._dispatch_receipts.get(
                self._dispatch_receipt_key(normalized_dispatch_type, max(0, job_id))
            )

    def list_dispatch_receipts(
        self,
        *,
        dispatch_type: str,
        session_id: int | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> list[DispatchReceiptRecord]:
        normalized_dispatch_type = _normalize_dispatch_type(dispatch_type)
        if not normalized_dispatch_type:
            return []
        cap = max(1, min(1000, int(limit)))
        norm_status = _normalize_token(status)
        now = _utcnow()
        with self._lock:
            self._prune_locked(now)
            rows = sorted(
                self._dispatch_receipts.values(),
                key=lambda item: item.updated_at,
                reverse=True,
            )
            out: list[DispatchReceiptRecord] = []
            for row in rows:
                if row.dispatch_type != normalized_dispatch_type:
                    continue
                if session_id is not None and row.session_id != int(session_id):
                    continue
                if norm_status and _normalize_token(row.status) != norm_status:
                    continue
                out.append(row)
                if len(out) >= cap:
                    break
            return out


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

    def _jobs_index_key(self) -> str:
        return f"{self._key_prefix}:jobs:index"

    def _alerts_key(self, job_id: int) -> str:
        return f"{self._key_prefix}:job:{job_id}:alerts"

    def _alerts_outbox_key(self) -> str:
        return f"{self._key_prefix}:alerts:outbox"

    def _alerts_outbox_stream_key(self) -> str:
        return f"{self._key_prefix}:alerts:outbox:stream"

    def _alerts_outbox_meta_key(self) -> str:
        return f"{self._key_prefix}:alerts:outbox:meta"

    def _topic_key(self, topic_domain: str, rubric_version: str) -> str:
        domain = topic_domain.strip().lower()
        rubric = rubric_version.strip().lower()
        return f"{self._key_prefix}:topic:{domain}:{rubric}"

    def _dispatch_receipt_key(self, dispatch_type: str, job_id: int) -> str:
        return f"{self._key_prefix}:dispatch:{dispatch_type}:{job_id}"

    def _index_job(self, *, job_id: int, updated_at: datetime) -> None:
        score = updated_at.timestamp()
        index_key = self._jobs_index_key()
        try:
            self._redis.zadd(index_key, {str(job_id): score})
            self._redis.expire(index_key, self._ttl_secs)
        except Exception:
            return

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
        return self._decode_json_dict(raw)

    def _decode_json_dict(self, raw: Any) -> dict[str, Any] | None:
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

    def _decode_redis_map(self, raw: Any) -> dict[str, str]:
        if not isinstance(raw, dict):
            return {}
        out: dict[str, str] = {}
        for key, value in raw.items():
            out[_decode_blob(key)] = _decode_blob(value)
        return out

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

    def _serialize_dispatch_receipt(self, record: DispatchReceiptRecord) -> dict[str, Any]:
        return {
            "dispatch_type": record.dispatch_type,
            "job_id": record.job_id,
            "scope_id": record.scope_id,
            "session_id": record.session_id,
            "trace_id": record.trace_id,
            "idempotency_key": record.idempotency_key,
            "rubric_version": record.rubric_version,
            "judge_policy_version": record.judge_policy_version,
            "topic_domain": record.topic_domain,
            "retrieval_profile": record.retrieval_profile,
            "phase_no": record.phase_no,
            "phase_start_no": record.phase_start_no,
            "phase_end_no": record.phase_end_no,
            "message_start_id": record.message_start_id,
            "message_end_id": record.message_end_id,
            "message_count": record.message_count,
            "status": record.status,
            "request": record.request,
            "response": record.response,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
        }

    def _deserialize_dispatch_receipt(self, payload: dict[str, Any]) -> DispatchReceiptRecord | None:
        dispatch_type = _normalize_dispatch_type(payload.get("dispatch_type"))
        if not dispatch_type:
            return None
        request = payload.get("request")
        response = payload.get("response")
        return DispatchReceiptRecord(
            dispatch_type=dispatch_type,
            job_id=_coerce_int(payload.get("job_id"), default=0),
            scope_id=_coerce_int(payload.get("scope_id"), default=0),
            session_id=_coerce_int(payload.get("session_id"), default=0),
            trace_id=str(payload.get("trace_id") or ""),
            idempotency_key=str(payload.get("idempotency_key") or ""),
            rubric_version=str(payload.get("rubric_version") or ""),
            judge_policy_version=str(payload.get("judge_policy_version") or ""),
            topic_domain=str(payload.get("topic_domain") or "default"),
            retrieval_profile=(
                str(payload.get("retrieval_profile"))
                if payload.get("retrieval_profile") is not None
                else None
            ),
            phase_no=(
                _coerce_int(payload.get("phase_no"), default=0)
                if payload.get("phase_no") is not None
                else None
            ),
            phase_start_no=(
                _coerce_int(payload.get("phase_start_no"), default=0)
                if payload.get("phase_start_no") is not None
                else None
            ),
            phase_end_no=(
                _coerce_int(payload.get("phase_end_no"), default=0)
                if payload.get("phase_end_no") is not None
                else None
            ),
            message_start_id=(
                _coerce_int(payload.get("message_start_id"), default=0)
                if payload.get("message_start_id") is not None
                else None
            ),
            message_end_id=(
                _coerce_int(payload.get("message_end_id"), default=0)
                if payload.get("message_end_id") is not None
                else None
            ),
            message_count=(
                _coerce_int(payload.get("message_count"), default=0)
                if payload.get("message_count") is not None
                else None
            ),
            status=str(payload.get("status") or "queued"),
            request=request if isinstance(request, dict) else {},
            response=response if isinstance(response, dict) else None,
            created_at=_parse_datetime(payload.get("created_at")),
            updated_at=_parse_datetime(payload.get("updated_at")),
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

    def _serialize_alert_transition(self, row: AuditAlertTransition) -> dict[str, Any]:
        return {
            "from_status": row.from_status,
            "to_status": row.to_status,
            "actor": row.actor,
            "reason": row.reason,
            "changed_at": row.changed_at.isoformat(),
        }

    def _deserialize_alert_transition(self, payload: dict[str, Any]) -> AuditAlertTransition:
        return AuditAlertTransition(
            from_status=_normalize_alert_status(payload.get("from_status")),
            to_status=_normalize_alert_status(payload.get("to_status")),
            actor=(str(payload.get("actor")).strip() if payload.get("actor") is not None else None),
            reason=(str(payload.get("reason")).strip() if payload.get("reason") is not None else None),
            changed_at=_parse_datetime(payload.get("changed_at")),
        )

    def _serialize_alert(self, row: AuditAlertRecord) -> dict[str, Any]:
        return {
            "alert_id": row.alert_id,
            "job_id": row.job_id,
            "scope_id": row.scope_id,
            "trace_id": row.trace_id,
            "alert_type": row.alert_type,
            "severity": row.severity,
            "title": row.title,
            "message": row.message,
            "details": row.details,
            "status": row.status,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
            "acknowledged_at": row.acknowledged_at.isoformat() if row.acknowledged_at else None,
            "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
            "transitions": [self._serialize_alert_transition(v) for v in row.transitions],
        }

    def _deserialize_alert(self, payload: dict[str, Any]) -> AuditAlertRecord:
        transitions_raw = payload.get("transitions")
        transitions: list[AuditAlertTransition] = []
        if isinstance(transitions_raw, list):
            for row in transitions_raw:
                if isinstance(row, dict):
                    transitions.append(self._deserialize_alert_transition(row))
        details = payload.get("details")
        return AuditAlertRecord(
            alert_id=str(payload.get("alert_id") or ""),
            job_id=_coerce_int(payload.get("job_id"), default=0),
            scope_id=_coerce_int(payload.get("scope_id"), default=0),
            trace_id=str(payload.get("trace_id") or ""),
            alert_type=_normalize_token(payload.get("alert_type")) or "unknown",
            severity=_normalize_token(payload.get("severity")) or "warning",
            title=str(payload.get("title") or "AI Judge Alert"),
            message=str(payload.get("message") or "ai_judge alert raised"),
            details=details if isinstance(details, dict) else {},
            status=_normalize_alert_status(payload.get("status")),
            created_at=_parse_datetime(payload.get("created_at")),
            updated_at=_parse_datetime(payload.get("updated_at")),
            acknowledged_at=(
                _parse_datetime(payload.get("acknowledged_at"))
                if payload.get("acknowledged_at")
                else None
            ),
            resolved_at=(
                _parse_datetime(payload.get("resolved_at"))
                if payload.get("resolved_at")
                else None
            ),
            transitions=transitions,
        )

    def _read_alerts(self, *, job_id: int) -> list[AuditAlertRecord]:
        payload = self._read_json(self._alerts_key(job_id))
        if payload is None:
            return []
        rows = payload.get("alerts")
        if not isinstance(rows, list):
            return []
        out: list[AuditAlertRecord] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            out.append(self._deserialize_alert(row))
        return out

    def _write_alerts(self, *, job_id: int, rows: list[AuditAlertRecord]) -> None:
        self._write_json(
            self._alerts_key(job_id),
            {
                "job_id": job_id,
                "alerts": [self._serialize_alert(row) for row in rows],
            },
        )

    def _serialize_outbox_event(self, row: AlertOutboxEvent) -> dict[str, Any]:
        return {
            "event_id": row.event_id,
            "channel": row.channel,
            "scope_id": row.scope_id,
            "job_id": row.job_id,
            "trace_id": row.trace_id,
            "alert_id": row.alert_id,
            "status": row.status,
            "payload": row.payload,
            "delivery_status": row.delivery_status,
            "error_message": row.error_message,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
        }

    def _deserialize_outbox_event(self, payload: dict[str, Any]) -> AlertOutboxEvent:
        body = payload.get("payload")
        return AlertOutboxEvent(
            event_id=str(payload.get("event_id") or ""),
            channel=str(payload.get("channel") or "ai_judge_audit_alert"),
            scope_id=_coerce_int(payload.get("scope_id"), default=0),
            job_id=_coerce_int(payload.get("job_id"), default=0),
            trace_id=str(payload.get("trace_id") or ""),
            alert_id=str(payload.get("alert_id") or ""),
            status=_normalize_alert_status(payload.get("status")),
            payload=body if isinstance(body, dict) else {},
            delivery_status=_normalize_delivery_status(payload.get("delivery_status")),
            error_message=(
                str(payload.get("error_message"))
                if payload.get("error_message") is not None
                else None
            ),
            created_at=_parse_datetime(payload.get("created_at")),
            updated_at=_parse_datetime(payload.get("updated_at")),
        )

    def _read_outbox_meta_event(self, event_id: str) -> AlertOutboxEvent | None:
        try:
            raw = self._redis.hget(self._alerts_outbox_meta_key(), event_id)
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
        return self._deserialize_outbox_event(payload)

    def _write_outbox_meta_event(self, row: AlertOutboxEvent) -> None:
        payload = self._serialize_outbox_event(row)
        try:
            self._redis.hset(
                self._alerts_outbox_meta_key(),
                row.event_id,
                json.dumps(payload, ensure_ascii=False),
            )
            self._redis.expire(self._alerts_outbox_meta_key(), self._ttl_secs)
        except Exception:
            return

    def _list_outbox_event_ids_from_stream(self, *, scan_limit: int) -> list[str]:
        cap = max(1, min(5000, scan_limit))
        try:
            rows = self._redis.xrevrange(
                self._alerts_outbox_stream_key(),
                count=cap,
            )
        except Exception:
            return []
        out: list[str] = []
        seen: set[str] = set()
        for _stream_id, raw_fields in rows:
            fields = self._decode_redis_map(raw_fields)
            event_id = fields.get("event_id", "").strip()
            if not event_id and fields.get("event"):
                try:
                    payload = json.loads(fields["event"])
                except Exception:
                    payload = {}
                if isinstance(payload, dict):
                    event_id = str(payload.get("event_id") or "").strip()
            if not event_id or event_id in seen:
                continue
            seen.add(event_id)
            out.append(event_id)
        return out

    def _prune_outbox_meta(self, *, keep_event_ids: set[str]) -> None:
        if not keep_event_ids:
            return
        try:
            raw_ids = self._redis.hkeys(self._alerts_outbox_meta_key())
        except Exception:
            return
        stale_ids: list[str] = []
        for raw in raw_ids:
            event_id = _decode_blob(raw).strip()
            if not event_id:
                continue
            if event_id not in keep_event_ids:
                stale_ids.append(event_id)
        if not stale_ids:
            return
        try:
            self._redis.hdel(self._alerts_outbox_meta_key(), *stale_ids)
        except Exception:
            return

    def _read_outbox(self, *, scan_limit: int = 500) -> list[AlertOutboxEvent]:
        event_ids = self._list_outbox_event_ids_from_stream(scan_limit=scan_limit)
        out: list[AlertOutboxEvent] = []
        for event_id in event_ids:
            row = self._read_outbox_meta_event(event_id)
            if row is not None:
                out.append(row)
        if out:
            return out

        payload = self._read_json(self._alerts_outbox_key())
        if payload is None:
            return []
        rows = payload.get("events")
        if not isinstance(rows, list):
            return []
        fallback: list[AlertOutboxEvent] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            fallback.append(self._deserialize_outbox_event(row))
        return fallback

    def _enqueue_outbox_event(
        self,
        *,
        now: datetime,
        alert: AuditAlertRecord,
        status: str,
    ) -> AlertOutboxEvent:
        seq = int(now.timestamp() * 1000)
        event = AlertOutboxEvent(
            event_id=f"evt-{alert.job_id}-{seq}-{abs(hash((alert.alert_id, status))) % 10000}",
            channel="ai_judge_audit_alert",
            scope_id=alert.scope_id,
            job_id=alert.job_id,
            trace_id=alert.trace_id,
            alert_id=alert.alert_id,
            status=status,
            payload={
                "eventType": "ai_judge.audit_alert.status_changed.v1",
                "scopeId": alert.scope_id,
                "jobId": alert.job_id,
                "traceId": alert.trace_id,
                "alertId": alert.alert_id,
                "alertType": alert.alert_type,
                "severity": alert.severity,
                "status": status,
                "title": alert.title,
                "message": alert.message,
                "details": alert.details,
                "createdAt": now.isoformat(),
            },
            delivery_status=OUTBOX_DELIVERY_PENDING,
            error_message=None,
            created_at=now,
            updated_at=now,
        )
        serialized = self._serialize_outbox_event(event)
        try:
            self._redis.xadd(
                self._alerts_outbox_stream_key(),
                {
                    "event_id": event.event_id,
                    "event": json.dumps(serialized, ensure_ascii=False),
                },
                maxlen=500,
                approximate=True,
            )
            self._redis.expire(self._alerts_outbox_stream_key(), self._ttl_secs)
        except Exception:
            pass
        self._write_outbox_meta_event(event)
        keep_event_ids = set(self._list_outbox_event_ids_from_stream(scan_limit=500))
        if keep_event_ids:
            self._prune_outbox_meta(keep_event_ids=keep_event_ids)
        return event

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
        self._index_job(job_id=job_id, updated_at=now)
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
        self._index_job(job_id=job_id, updated_at=record.updated_at)

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
        self._index_job(job_id=job_id, updated_at=record.updated_at)

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

    def _resolve_idempotency_with_lua(
        self,
        *,
        key: str,
        idempotency_key: str,
        pending_payload: dict[str, Any],
        ttl: int,
        job_id: int,
        expires_at: datetime,
    ) -> IdempotencyResolution | None:
        eval_fn = getattr(self._redis, "eval", None)
        if not callable(eval_fn):
            return None
        try:
            raw_result = eval_fn(
                _RESOLVE_IDEMPOTENCY_LUA,
                1,
                idempotency_key,
                json.dumps(pending_payload, ensure_ascii=False),
                str(ttl),
                str(job_id),
            )
        except Exception:
            return None
        if not isinstance(raw_result, (list, tuple)) or not raw_result:
            return None
        status = _decode_blob(raw_result[0]).strip().lower()
        if status not in IDEMPOTENCY_RESOLUTION_VALUES:
            return None
        if status == IDEMPOTENCY_RESOLUTION_ACQUIRED:
            return IdempotencyResolution(
                status=IDEMPOTENCY_RESOLUTION_ACQUIRED,
                record=IdempotencyRecord(
                    key=key,
                    job_id=job_id,
                    response=None,
                    expires_at=expires_at,
                ),
            )
        payload = self._decode_json_dict(raw_result[1] if len(raw_result) > 1 else None)
        record = self._deserialize_idempotency(key, payload) if payload else None
        return IdempotencyResolution(status=status, record=record)

    def resolve_idempotency(
        self,
        *,
        key: str,
        job_id: int,
        ttl_secs: int | None = None,
    ) -> IdempotencyResolution:
        now = _utcnow()
        ttl = max(60, ttl_secs or self._ttl_secs)
        expires_at = now + timedelta(seconds=ttl)
        pending_payload = {
            "key": key,
            "job_id": job_id,
            "response": None,
            "expires_at": expires_at.isoformat(),
        }
        idempotency_key = self._idempotency_key(key)
        lua_resolution = self._resolve_idempotency_with_lua(
            key=key,
            idempotency_key=idempotency_key,
            pending_payload=pending_payload,
            ttl=ttl,
            job_id=job_id,
            expires_at=expires_at,
        )
        if lua_resolution is not None:
            return lua_resolution
        for _ in range(2):
            try:
                created = self._redis.set(
                    idempotency_key,
                    json.dumps(pending_payload, ensure_ascii=False),
                    ex=ttl,
                    nx=True,
                )
            except Exception:
                created = None
            if created:
                return IdempotencyResolution(
                    status=IDEMPOTENCY_RESOLUTION_ACQUIRED,
                    record=IdempotencyRecord(
                        key=key,
                        job_id=job_id,
                        response=None,
                        expires_at=expires_at,
                    ),
                )

            payload = self._read_json(idempotency_key)
            if payload is None:
                continue
            existed = self._deserialize_idempotency(key, payload)
            if existed.job_id != job_id:
                return IdempotencyResolution(
                    status=IDEMPOTENCY_RESOLUTION_CONFLICT,
                    record=existed,
                )
            if isinstance(existed.response, dict):
                return IdempotencyResolution(
                    status=IDEMPOTENCY_RESOLUTION_REPLAY,
                    record=existed,
                )
            return IdempotencyResolution(
                status=IDEMPOTENCY_RESOLUTION_CONFLICT,
                record=existed,
            )
        return IdempotencyResolution(status=IDEMPOTENCY_RESOLUTION_CONFLICT, record=None)

    def clear_idempotency(self, key: str) -> None:
        try:
            self._redis.delete(self._idempotency_key(key))
        except Exception:
            return

    def get_trace(self, job_id: int) -> TraceRecord | None:
        return self._read_trace(job_id)

    def upsert_audit_alert(
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
    ) -> AuditAlertRecord:
        now = _utcnow()
        norm_type = _normalize_token(alert_type) or "unknown"
        norm_severity = _normalize_token(severity) or "warning"
        norm_details = dict(details or {})
        fingerprint = _safe_json(
            {
                "type": norm_type,
                "severity": norm_severity,
                "title": title.strip(),
                "message": message.strip(),
                "details": norm_details,
            }
        )
        rows = self._read_alerts(job_id=job_id)
        for item in rows:
            if item.status == ALERT_STATUS_RESOLVED:
                continue
            existing_fp = _safe_json(
                {
                    "type": item.alert_type,
                    "severity": item.severity,
                    "title": item.title,
                    "message": item.message,
                    "details": item.details,
                }
            )
            if existing_fp != fingerprint:
                continue
            item.updated_at = now
            if trace_id:
                item.trace_id = trace_id
            self._write_alerts(job_id=job_id, rows=rows)
            self._enqueue_outbox_event(
                now=now,
                alert=item,
                status=item.status,
            )
            return item

        next_seq = len(rows) + 1
        alert = AuditAlertRecord(
            alert_id=f"al-{job_id}-{next_seq:06d}",
            job_id=job_id,
            scope_id=max(0, scope_id),
            trace_id=trace_id,
            alert_type=norm_type,
            severity=norm_severity,
            title=title.strip() or "AI Judge Alert",
            message=message.strip() or "ai_judge alert raised",
            details=norm_details,
            status=ALERT_STATUS_RAISED,
            created_at=now,
            updated_at=now,
        )
        rows.insert(0, alert)
        self._write_alerts(job_id=job_id, rows=rows)
        self._enqueue_outbox_event(
            now=now,
            alert=alert,
            status=ALERT_STATUS_RAISED,
        )
        return alert

    def list_audit_alerts(
        self,
        *,
        job_id: int | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[AuditAlertRecord]:
        cap = max(1, min(200, limit))
        norm_status = _normalize_alert_status(status, default="")
        out: list[AuditAlertRecord] = []

        if job_id is not None:
            rows = self._read_alerts(job_id=job_id)
            for row in rows:
                if norm_status and row.status != norm_status:
                    continue
                out.append(row)
                if len(out) >= cap:
                    break
            return out

        scan_limit = max(100, cap * 8)
        for jid in self._list_indexed_job_ids(scan_limit=scan_limit):
            rows = self._read_alerts(job_id=jid)
            for row in rows:
                if norm_status and row.status != norm_status:
                    continue
                out.append(row)
                if len(out) >= cap:
                    return out
        return out

    def transition_audit_alert(
        self,
        *,
        job_id: int,
        alert_id: str,
        to_status: str,
        actor: str | None = None,
        reason: str | None = None,
    ) -> AuditAlertRecord | None:
        target = _normalize_alert_status(to_status)
        now = _utcnow()
        rows = self._read_alerts(job_id=job_id)
        for row in rows:
            if row.alert_id != alert_id:
                continue
            if not _allowed_alert_transition(row.status, target):
                return None
            if row.status != target:
                row.transitions.append(
                    AuditAlertTransition(
                        from_status=row.status,
                        to_status=target,
                        actor=(actor or "").strip() or None,
                        reason=(reason or "").strip() or None,
                        changed_at=now,
                    )
                )
                row.status = target
                row.updated_at = now
                if target == ALERT_STATUS_ACKED:
                    row.acknowledged_at = now
                if target == ALERT_STATUS_RESOLVED:
                    row.resolved_at = now
            self._write_alerts(job_id=job_id, rows=rows)
            self._enqueue_outbox_event(
                now=now,
                alert=row,
                status=row.status,
            )
            return row
        return None

    def list_alert_outbox(
        self,
        *,
        delivery_status: str | None = None,
        limit: int = 50,
    ) -> list[AlertOutboxEvent]:
        cap = max(1, min(200, limit))
        norm_status = _normalize_delivery_status(delivery_status, default="")
        rows = self._read_outbox(scan_limit=max(500, cap * 8))
        out: list[AlertOutboxEvent] = []
        for row in rows:
            if norm_status and row.delivery_status != norm_status:
                continue
            out.append(row)
            if len(out) >= cap:
                break
        return out

    def mark_alert_outbox_delivery(
        self,
        *,
        event_id: str,
        delivery_status: str,
        error_message: str | None = None,
    ) -> AlertOutboxEvent | None:
        target = _normalize_delivery_status(delivery_status)
        now = _utcnow()
        row = self._read_outbox_meta_event(event_id)
        if row is not None:
            row.delivery_status = target
            row.error_message = (error_message or "").strip() or None
            row.updated_at = now
            self._write_outbox_meta_event(row)
            return row

        rows = self._read_outbox(scan_limit=1000)
        for fallback in rows:
            if fallback.event_id != event_id:
                continue
            fallback.delivery_status = target
            fallback.error_message = (error_message or "").strip() or None
            fallback.updated_at = now
            self._write_json(
                self._alerts_outbox_key(),
                {"events": [self._serialize_outbox_event(item) for item in rows]},
            )
            return fallback
        return None

    def _list_indexed_job_ids(self, *, scan_limit: int) -> list[int]:
        index_key = self._jobs_index_key()
        batch_size = 100
        offset = 0
        out: list[int] = []
        while len(out) < scan_limit:
            try:
                rows = self._redis.zrevrange(index_key, offset, offset + batch_size - 1)
            except Exception:
                return out
            if not rows:
                break
            for raw in rows:
                job_id = _coerce_int(_decode_blob(raw), default=0)
                if job_id > 0:
                    out.append(job_id)
            if len(rows) < batch_size:
                break
            offset += batch_size
        return out

    def _scan_runtime_job_ids(self, *, scan_limit: int) -> list[int]:
        pattern = f"{self._key_prefix}:job:*:runtime"
        out: list[int] = []
        try:
            iterator = self._redis.scan_iter(match=pattern, count=max(50, scan_limit))
        except Exception:
            return out
        for raw in iterator:
            key = _decode_blob(raw)
            if not key:
                continue
            parts = key.split(":")
            if len(parts) < 4:
                continue
            job_id = _coerce_int(parts[-2], default=0)
            if job_id > 0:
                out.append(job_id)
            if len(out) >= scan_limit:
                break
        out.sort(reverse=True)
        return out

    def list_traces(self, *, query: TraceQuery | None = None) -> list[TraceRecord]:
        q = query or TraceQuery()
        limit = max(1, min(200, q.limit))
        scan_limit = max(100, limit * 8)

        job_ids = self._list_indexed_job_ids(scan_limit=scan_limit)
        if not job_ids:
            job_ids = self._scan_runtime_job_ids(scan_limit=scan_limit)

        out: list[TraceRecord] = []
        seen: set[int] = set()
        for job_id in job_ids:
            if job_id in seen:
                continue
            seen.add(job_id)
            record = self._read_trace(job_id)
            if record is None:
                try:
                    self._redis.zrem(self._jobs_index_key(), str(job_id))
                except Exception:
                    pass
                continue
            if not _trace_matches(record, q):
                continue
            out.append(record)
            if len(out) >= limit:
                break
        return out

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
        self._index_job(job_id=job_id, updated_at=now)

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
        audit: dict[str, Any] | None = None,
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
            "audit": dict(audit or {}),
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
            audit = payload.get("audit")
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
                    audit=audit if isinstance(audit, dict) else {},
                )
            )
        return out

    def save_dispatch_receipt(
        self,
        *,
        dispatch_type: str,
        job_id: int,
        scope_id: int,
        session_id: int,
        trace_id: str,
        idempotency_key: str,
        rubric_version: str,
        judge_policy_version: str,
        topic_domain: str,
        retrieval_profile: str | None,
        phase_no: int | None,
        phase_start_no: int | None,
        phase_end_no: int | None,
        message_start_id: int | None,
        message_end_id: int | None,
        message_count: int | None,
        status: str,
        request: dict[str, Any],
        response: dict[str, Any] | None,
    ) -> DispatchReceiptRecord:
        normalized_dispatch_type = _normalize_dispatch_type(dispatch_type)
        if not normalized_dispatch_type:
            raise ValueError(f"unsupported dispatch_type: {dispatch_type}")
        job_id = max(0, job_id)
        key = self._dispatch_receipt_key(normalized_dispatch_type, job_id)
        now = _utcnow()
        existing = self._read_json(key)
        created_at = _parse_datetime(existing.get("created_at")) if isinstance(existing, dict) else now
        row = DispatchReceiptRecord(
            dispatch_type=normalized_dispatch_type,
            job_id=job_id,
            scope_id=max(0, scope_id),
            session_id=max(0, session_id),
            trace_id=trace_id.strip(),
            idempotency_key=idempotency_key.strip(),
            rubric_version=rubric_version.strip(),
            judge_policy_version=judge_policy_version.strip(),
            topic_domain=topic_domain.strip().lower() or "default",
            retrieval_profile=(retrieval_profile.strip() if isinstance(retrieval_profile, str) else None),
            phase_no=phase_no,
            phase_start_no=phase_start_no,
            phase_end_no=phase_end_no,
            message_start_id=message_start_id,
            message_end_id=message_end_id,
            message_count=message_count,
            status=status.strip().lower() or "queued",
            request=dict(request),
            response=(dict(response) if isinstance(response, dict) else None),
            created_at=created_at,
            updated_at=now,
        )
        self._write_json(
            key,
            self._serialize_dispatch_receipt(row),
        )
        return row

    def get_dispatch_receipt(
        self,
        *,
        dispatch_type: str,
        job_id: int,
    ) -> DispatchReceiptRecord | None:
        normalized_dispatch_type = _normalize_dispatch_type(dispatch_type)
        if not normalized_dispatch_type:
            return None
        payload = self._read_json(self._dispatch_receipt_key(normalized_dispatch_type, max(0, job_id)))
        if payload is None:
            return None
        return self._deserialize_dispatch_receipt(payload)

    def list_dispatch_receipts(
        self,
        *,
        dispatch_type: str,
        session_id: int | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> list[DispatchReceiptRecord]:
        normalized_dispatch_type = _normalize_dispatch_type(dispatch_type)
        if not normalized_dispatch_type:
            return []

        cap = max(1, min(1000, int(limit)))
        norm_status = _normalize_token(status)
        target_session_id = int(session_id) if session_id is not None else None

        pattern = f"{self._key_prefix}:dispatch:{normalized_dispatch_type}:*"
        out: list[DispatchReceiptRecord] = []
        try:
            iterator = self._redis.scan_iter(match=pattern, count=max(100, cap * 2))
        except Exception:
            return []
        for raw in iterator:
            key = _decode_blob(raw)
            if not key:
                continue
            payload = self._read_json(key)
            if payload is None:
                continue
            row = self._deserialize_dispatch_receipt(payload)
            if row is None:
                continue
            if target_session_id is not None and row.session_id != target_session_id:
                continue
            if norm_status and _normalize_token(row.status) != norm_status:
                continue
            out.append(row)
        out.sort(key=lambda item: item.updated_at, reverse=True)
        return out[:cap]


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
    "IdempotencyResolution",
    "TopicMemoryRecord",
    "TraceQuery",
    "AuditAlertTransition",
    "AuditAlertRecord",
    "AlertOutboxEvent",
    "DispatchReceiptRecord",
    "build_trace_store_from_settings",
]
