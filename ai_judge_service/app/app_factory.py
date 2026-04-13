from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Header, HTTPException, Query, Request
from pydantic import ValidationError

from .applications import (
    AgentRuntime,
    GatewayRuntime,
    WorkflowRuntime,
    build_agent_runtime,
    build_gateway_runtime,
    build_workflow_runtime,
)
from .applications import (
    build_final_report_payload as build_final_report_payload_v3_final,
)
from .applications import (
    build_phase_report_payload as build_phase_report_payload_v3_phase,
)
from .applications import (
    build_replay_report_payload as build_replay_report_payload_v3,
)
from .applications import (
    build_replay_report_summary as build_replay_report_summary_v3,
)
from .applications import (
    serialize_alert_item as serialize_alert_item_v3,
)
from .applications import (
    serialize_dispatch_receipt as serialize_dispatch_receipt_v3,
)
from .applications import (
    serialize_outbox_event as serialize_outbox_event_v3,
)
from .applications import (
    validate_final_report_payload_contract as validate_final_report_payload_contract_v3_final,
)
from .callback_client import (
    callback_final_failed,
    callback_final_report,
    callback_phase_failed,
    callback_phase_report,
)
from .domain.facts import (
    AuditAlert as FactAuditAlert,
)
from .domain.facts import (
    DispatchReceipt as FactDispatchReceipt,
)
from .domain.facts import (
    ReplayRecord as FactReplayRecord,
)
from .domain.workflow import WORKFLOW_STATUS_QUEUED, WorkflowJob
from .models import FinalDispatchRequest, PhaseDispatchRequest
from .runtime_types import CallbackReportFn, DispatchRuntimeConfig, SleepFn
from .settings import (
    Settings,
    build_callback_client_config,
    build_dispatch_runtime_config,
    load_settings,
)
from .trace_store import TraceQuery, TraceStoreProtocol, build_trace_store_from_settings
from .wiring import build_v3_dispatch_callbacks

LoadSettingsFn = Callable[[], Settings]


@dataclass(frozen=True)
class AppRuntime:
    settings: Settings
    dispatch_runtime_cfg: DispatchRuntimeConfig
    callback_phase_report_fn: Callable[[int, dict[str, Any]], Awaitable[None]]
    callback_final_report_fn: Callable[[int, dict[str, Any]], Awaitable[None]]
    callback_phase_failed_fn: Callable[[int, dict[str, Any]], Awaitable[None]]
    callback_final_failed_fn: Callable[[int, dict[str, Any]], Awaitable[None]]
    sleep_fn: SleepFn
    trace_store: TraceStoreProtocol
    workflow_runtime: WorkflowRuntime
    gateway_runtime: GatewayRuntime
    agent_runtime: AgentRuntime


def require_internal_key(settings: Settings, header_value: str | None) -> None:
    if not header_value:
        raise HTTPException(status_code=401, detail="missing x-ai-internal-key")
    if header_value.strip() != settings.ai_internal_key:
        raise HTTPException(status_code=401, detail="invalid x-ai-internal-key")


def create_runtime(
    *,
    settings: Settings,
    callback_phase_report_impl=callback_phase_report,
    callback_final_report_impl=callback_final_report,
    callback_phase_failed_impl=callback_phase_failed,
    callback_final_failed_impl=callback_final_failed,
    sleep_fn: SleepFn = asyncio.sleep,
) -> AppRuntime:
    trace_store = build_trace_store_from_settings(settings=settings)
    workflow_runtime = build_workflow_runtime(settings=settings)
    gateway_runtime = build_gateway_runtime(settings=settings)
    agent_runtime = build_agent_runtime(settings=settings)
    callback_cfg = build_callback_client_config(settings)
    (
        callback_phase_report_fn,
        callback_final_report_fn,
        callback_phase_failed_fn,
        callback_final_failed_fn,
    ) = build_v3_dispatch_callbacks(
        cfg=callback_cfg,
        callback_phase_report_impl=callback_phase_report_impl,
        callback_final_report_impl=callback_final_report_impl,
        callback_phase_failed_impl=callback_phase_failed_impl,
        callback_final_failed_impl=callback_final_failed_impl,
    )
    return AppRuntime(
        settings=settings,
        dispatch_runtime_cfg=build_dispatch_runtime_config(settings),
        callback_phase_report_fn=callback_phase_report_fn,
        callback_final_report_fn=callback_final_report_fn,
        callback_phase_failed_fn=callback_phase_failed_fn,
        callback_final_failed_fn=callback_final_failed_fn,
        sleep_fn=sleep_fn,
        trace_store=trace_store,
        workflow_runtime=workflow_runtime,
        gateway_runtime=gateway_runtime,
        agent_runtime=agent_runtime,
    )


_BLIND_SENSITIVE_KEY_TOKENS = {
    "user_id",
    "userid",
    "vip",
    "balance",
    "wallet_balance",
    "is_vip",
}


def _serialize_alert_item(alert: Any) -> dict[str, Any]:
    return serialize_alert_item_v3(alert)


def _serialize_outbox_event(item: Any) -> dict[str, Any]:
    return serialize_outbox_event_v3(item)


def _serialize_dispatch_receipt(item: Any) -> dict[str, Any]:
    return serialize_dispatch_receipt_v3(item)


def _build_replay_report_payload(record: Any) -> dict[str, Any]:
    return build_replay_report_payload_v3(record)


def _build_replay_report_summary(record: Any) -> dict[str, Any]:
    return build_replay_report_summary_v3(record)


def _normalize_query_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _normalize_key_token(value: Any) -> str:
    lowered = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return lowered


def _collect_sensitive_key_hits(
    value: Any,
    *,
    path: str,
    out: list[str],
) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            key_token = _normalize_key_token(key_text)
            compact = key_token.replace("_", "")
            if key_token in _BLIND_SENSITIVE_KEY_TOKENS or compact in _BLIND_SENSITIVE_KEY_TOKENS:
                out.append(f"{path}.{key_text}" if path else key_text)
            next_path = f"{path}.{key_text}" if path else key_text
            _collect_sensitive_key_hits(child, path=next_path, out=out)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            next_path = f"{path}[{index}]" if path else f"[{index}]"
            _collect_sensitive_key_hits(child, path=next_path, out=out)


def _find_sensitive_key_hits(payload: Any) -> list[str]:
    out: list[str] = []
    _collect_sensitive_key_hits(payload, path="", out=out)
    dedup: list[str] = []
    seen: set[str] = set()
    for item in out:
        if item in seen:
            continue
        seen.add(item)
        dedup.append(item)
    return dedup


def _extract_raw_field(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload.get(key)
    return None


def _extract_optional_int(payload: dict[str, Any], *keys: str) -> int | None:
    value = _extract_raw_field(payload, *keys)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_optional_str(payload: dict[str, Any], *keys: str) -> str | None:
    value = _extract_raw_field(payload, *keys)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _build_failed_callback_payload(
    *,
    job_id: int,
    dispatch_type: str,
    trace_id: str,
    error_code: str,
    error_message: str,
    audit_alert_ids: list[str] | None = None,
    degradation_level: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "jobId": job_id,
        "dispatchType": dispatch_type,
        "traceId": trace_id,
        "errorCode": error_code,
        "errorMessage": error_message,
        "auditAlertIds": list(audit_alert_ids or []),
    }
    if degradation_level is not None:
        payload["degradationLevel"] = int(degradation_level)
    return payload


def _build_trace_report_summary(
    *,
    dispatch_type: str,
    payload: dict[str, Any] | None,
    callback_status: str,
    callback_error: str | None,
) -> dict[str, Any]:
    report_payload = payload if isinstance(payload, dict) else {}
    alerts = report_payload.get("auditAlerts")
    if not isinstance(alerts, list):
        alerts = []
    winner = str(report_payload.get("winner") or "").strip().lower() or None
    return {
        "dispatchType": dispatch_type,
        "payload": report_payload,
        "winner": winner,
        "auditAlerts": [item for item in alerts if isinstance(item, dict)],
        "callbackStatus": callback_status,
        "callbackError": callback_error,
    }


def _resolve_idempotency_or_raise(
    *,
    runtime: AppRuntime,
    key: str,
    job_id: int,
    conflict_detail: str,
) -> dict[str, Any] | None:
    resolution = runtime.trace_store.resolve_idempotency(
        key=key,
        job_id=job_id,
        ttl_secs=runtime.settings.idempotency_ttl_secs,
    )
    if resolution.status == "replay" and resolution.record and resolution.record.response:
        replayed = dict(resolution.record.response)
        replayed["idempotentReplay"] = True
        return replayed
    if resolution.status != "acquired":
        raise HTTPException(status_code=409, detail=conflict_detail)
    return None


def _validate_phase_dispatch_request(request: PhaseDispatchRequest) -> None:
    if request.message_count <= 0:
        raise HTTPException(status_code=422, detail="invalid_message_count")
    if request.message_end_id < request.message_start_id:
        raise HTTPException(status_code=422, detail="invalid_message_range")
    if request.message_count != len(request.messages):
        raise HTTPException(status_code=422, detail="message_count_mismatch")
    for message in request.messages:
        if (
            message.message_id < request.message_start_id
            or message.message_id > request.message_end_id
        ):
            raise HTTPException(status_code=422, detail="message_id_out_of_range")


def _validate_final_dispatch_request(request: FinalDispatchRequest) -> None:
    if request.phase_start_no <= 0 or request.phase_end_no <= 0:
        raise HTTPException(status_code=422, detail="invalid_phase_no")
    if request.phase_start_no > request.phase_end_no:
        raise HTTPException(status_code=422, detail="invalid_phase_range")


def _extract_dispatch_meta_from_raw(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "jobId": _extract_optional_int(payload, "job_id", "jobId"),
        "scopeId": _extract_optional_int(payload, "scope_id", "scopeId") or 1,
        "sessionId": _extract_optional_int(payload, "session_id", "sessionId"),
        "traceId": _extract_optional_str(payload, "trace_id", "traceId") or "",
        "idempotencyKey": _extract_optional_str(payload, "idempotency_key", "idempotencyKey") or "",
        "rubricVersion": _extract_optional_str(payload, "rubric_version", "rubricVersion") or "",
        "judgePolicyVersion": _extract_optional_str(
            payload,
            "judge_policy_version",
            "judgePolicyVersion",
        )
        or "",
        "topicDomain": _extract_optional_str(payload, "topic_domain", "topicDomain") or "",
        "retrievalProfile": _extract_optional_str(
            payload,
            "retrieval_profile",
            "retrievalProfile",
        ),
    }


def _extract_receipt_dims_from_raw(
    dispatch_type: str,
    payload: dict[str, Any],
) -> dict[str, int | None]:
    if dispatch_type == "phase":
        return {
            "phaseNo": _extract_optional_int(payload, "phase_no", "phaseNo"),
            "phaseStartNo": None,
            "phaseEndNo": None,
            "messageStartId": _extract_optional_int(payload, "message_start_id", "messageStartId"),
            "messageEndId": _extract_optional_int(payload, "message_end_id", "messageEndId"),
            "messageCount": _extract_optional_int(payload, "message_count", "messageCount"),
        }
    return {
        "phaseNo": None,
        "phaseStartNo": _extract_optional_int(payload, "phase_start_no", "phaseStartNo"),
        "phaseEndNo": _extract_optional_int(payload, "phase_end_no", "phaseEndNo"),
        "messageStartId": None,
        "messageEndId": None,
        "messageCount": None,
    }


def _failed_callback_fn_for_dispatch(runtime: AppRuntime, dispatch_type: str) -> CallbackReportFn:
    return runtime.callback_phase_failed_fn if dispatch_type == "phase" else runtime.callback_final_failed_fn


def _report_callback_fn_for_dispatch(runtime: AppRuntime, dispatch_type: str) -> CallbackReportFn:
    return runtime.callback_phase_report_fn if dispatch_type == "phase" else runtime.callback_final_report_fn


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _resolve_winner(pro_score: float, con_score: float, *, margin: float = 1.0) -> str:
    if pro_score - con_score >= margin:
        return "pro"
    if con_score - pro_score >= margin:
        return "con"
    return "draw"


def _validate_final_report_payload_contract(payload: dict[str, Any]) -> list[str]:
    return validate_final_report_payload_contract_v3_final(payload)


def _build_final_report_payload(
    *,
    runtime: AppRuntime,
    request: FinalDispatchRequest,
    phase_receipts: list[Any] | None = None,
) -> dict[str, Any]:
    receipts = (
        phase_receipts
        if phase_receipts is not None
        else runtime.trace_store.list_dispatch_receipts(
            dispatch_type="phase",
            session_id=request.session_id,
            status="reported",
            limit=1000,
        )
    )
    return build_final_report_payload_v3_final(
        request=request,
        phase_receipts=list(receipts),
        judge_style_mode=runtime.dispatch_runtime_cfg.judge_style_mode,
    )


async def _invoke_v3_callback_with_retry(
    *,
    runtime: AppRuntime,
    callback_fn: CallbackReportFn,
    job_id: int,
    payload: dict[str, Any],
) -> tuple[int, int]:
    max_attempts = max(1, int(runtime.dispatch_runtime_cfg.runtime_retry_max_attempts))
    backoff_ms = max(0, int(runtime.dispatch_runtime_cfg.retry_backoff_ms))
    attempt = 0
    last_error: Exception | None = None
    while attempt < max_attempts:
        attempt += 1
        try:
            await callback_fn(job_id, payload)
            return attempt, max(0, attempt - 1)
        except Exception as err:
            last_error = err
            if attempt >= max_attempts:
                break
            if backoff_ms > 0:
                await runtime.sleep_fn((backoff_ms * attempt) / 1000.0)
    raise RuntimeError(
        f"v3 callback failed after {max_attempts} attempts: {last_error or 'unknown'}"
    ) from last_error


def _save_dispatch_receipt(
    *,
    runtime: AppRuntime,
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
    request_payload: dict[str, Any],
    response_payload: dict[str, Any] | None,
) -> None:
    runtime.trace_store.save_dispatch_receipt(
        dispatch_type=dispatch_type,
        job_id=job_id,
        scope_id=scope_id,
        session_id=session_id,
        trace_id=trace_id,
        idempotency_key=idempotency_key,
        rubric_version=rubric_version,
        judge_policy_version=judge_policy_version,
        topic_domain=topic_domain,
        retrieval_profile=retrieval_profile,
        phase_no=phase_no,
        phase_start_no=phase_start_no,
        phase_end_no=phase_end_no,
        message_start_id=message_start_id,
        message_end_id=message_end_id,
        message_count=message_count,
        status=status,
        request=request_payload,
        response=response_payload,
    )


def create_app(runtime: AppRuntime) -> FastAPI:
    app = FastAPI(title="AI Judge Service", version="0.2.0")
    workflow_schema_ready = False
    workflow_schema_lock = asyncio.Lock()

    async def _ensure_workflow_schema_ready() -> None:
        nonlocal workflow_schema_ready
        if workflow_schema_ready or not runtime.settings.db_auto_create_schema:
            return
        async with workflow_schema_lock:
            if workflow_schema_ready:
                return
            await runtime.workflow_runtime.db.create_schema()
            workflow_schema_ready = True

    async def _persist_dispatch_receipt(
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
        request_payload: dict[str, Any],
        response_payload: dict[str, Any] | None,
    ) -> None:
        _save_dispatch_receipt(
            runtime=runtime,
            dispatch_type=dispatch_type,
            job_id=job_id,
            scope_id=scope_id,
            session_id=session_id,
            trace_id=trace_id,
            idempotency_key=idempotency_key,
            rubric_version=rubric_version,
            judge_policy_version=judge_policy_version,
            topic_domain=topic_domain,
            retrieval_profile=retrieval_profile,
            phase_no=phase_no,
            phase_start_no=phase_start_no,
            phase_end_no=phase_end_no,
            message_start_id=message_start_id,
            message_end_id=message_end_id,
            message_count=message_count,
            status=status,
            request_payload=request_payload,
            response_payload=response_payload,
        )
        await _ensure_workflow_schema_ready()
        await runtime.workflow_runtime.facts.upsert_dispatch_receipt(
            receipt=FactDispatchReceipt(
                dispatch_type=dispatch_type,
                job_id=max(0, int(job_id)),
                scope_id=max(0, int(scope_id)),
                session_id=max(0, int(session_id)),
                trace_id=str(trace_id or "").strip(),
                idempotency_key=str(idempotency_key or "").strip(),
                rubric_version=str(rubric_version or "").strip(),
                judge_policy_version=str(judge_policy_version or "").strip(),
                topic_domain=str(topic_domain or "").strip(),
                retrieval_profile=retrieval_profile,
                phase_no=phase_no,
                phase_start_no=phase_start_no,
                phase_end_no=phase_end_no,
                message_start_id=message_start_id,
                message_end_id=message_end_id,
                message_count=message_count,
                status=str(status or "").strip(),
                request=dict(request_payload or {}),
                response=(dict(response_payload) if isinstance(response_payload, dict) else None),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )

    async def _get_dispatch_receipt(*, dispatch_type: str, job_id: int) -> Any | None:
        await _ensure_workflow_schema_ready()
        receipt = await runtime.workflow_runtime.facts.get_dispatch_receipt(
            dispatch_type=dispatch_type,
            job_id=job_id,
        )
        if receipt is not None:
            return receipt
        return runtime.trace_store.get_dispatch_receipt(
            dispatch_type=dispatch_type,
            job_id=job_id,
        )

    async def _list_dispatch_receipts(
        *,
        dispatch_type: str,
        session_id: int | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> list[Any]:
        await _ensure_workflow_schema_ready()
        receipts = await runtime.workflow_runtime.facts.list_dispatch_receipts(
            dispatch_type=dispatch_type,
            session_id=session_id,
            status=status,
            limit=limit,
        )
        if receipts:
            return list(receipts)
        return list(
            runtime.trace_store.list_dispatch_receipts(
                dispatch_type=dispatch_type,
                session_id=session_id,
                status=status,
                limit=limit,
            )
        )

    async def _append_replay_record(
        *,
        dispatch_type: str,
        job_id: int,
        trace_id: str,
        winner: str | None,
        needs_draw_vote: bool | None,
        provider: str | None,
        report_payload: dict[str, Any] | None,
    ) -> FactReplayRecord:
        await _ensure_workflow_schema_ready()
        return await runtime.workflow_runtime.facts.append_replay_record(
            dispatch_type=dispatch_type,
            job_id=job_id,
            trace_id=trace_id,
            winner=winner,
            needs_draw_vote=needs_draw_vote,
            provider=provider,
            report_payload=report_payload,
        )

    async def _list_replay_records(
        *,
        job_id: int,
        dispatch_type: str | None = None,
        limit: int = 50,
    ) -> list[FactReplayRecord]:
        await _ensure_workflow_schema_ready()
        return await runtime.workflow_runtime.facts.list_replay_records(
            dispatch_type=dispatch_type,
            job_id=job_id,
            limit=limit,
        )

    async def _sync_audit_alert_to_facts(*, alert: Any) -> FactAuditAlert:
        await _ensure_workflow_schema_ready()
        return await runtime.workflow_runtime.facts.upsert_audit_alert(
            alert_id=str(alert.alert_id or "").strip() or None,
            job_id=int(alert.job_id),
            scope_id=int(alert.scope_id),
            trace_id=str(alert.trace_id or "").strip(),
            alert_type=str(alert.alert_type or "").strip(),
            severity=str(alert.severity or "").strip(),
            title=str(alert.title or "").strip(),
            message=str(alert.message or "").strip(),
            details=(dict(alert.details) if isinstance(alert.details, dict) else {}),
            now=getattr(alert, "updated_at", None),
        )

    async def _list_audit_alerts(
        *,
        job_id: int,
        status: str | None,
        limit: int,
    ) -> list[Any]:
        await _ensure_workflow_schema_ready()
        items = await runtime.workflow_runtime.facts.list_audit_alerts(
            job_id=job_id,
            status=status,
            limit=limit,
        )
        if items:
            return items
        return list(
            runtime.trace_store.list_audit_alerts(
                job_id=job_id,
                status=status,
                limit=limit,
            )
        )

    def _build_workflow_job(
        *,
        dispatch_type: str,
        job_id: int,
        trace_id: str,
        scope_id: int,
        session_id: int,
        idempotency_key: str,
        rubric_version: str,
        judge_policy_version: str,
        topic_domain: str,
        retrieval_profile: str | None,
    ) -> WorkflowJob:
        return WorkflowJob(
            job_id=max(0, int(job_id)),
            dispatch_type=str(dispatch_type or "").strip().lower(),
            trace_id=str(trace_id or "").strip(),
            status=WORKFLOW_STATUS_QUEUED,
            scope_id=max(0, int(scope_id)),
            session_id=max(0, int(session_id)),
            idempotency_key=str(idempotency_key or "").strip(),
            rubric_version=str(rubric_version or "").strip(),
            judge_policy_version=str(judge_policy_version or "").strip(),
            topic_domain=str(topic_domain or "").strip().lower() or "default",
            retrieval_profile=(
                str(retrieval_profile).strip()
                if retrieval_profile is not None and str(retrieval_profile).strip()
                else None
            ),
        )

    async def _workflow_register_and_mark_running(
        *,
        job: WorkflowJob,
        event_payload: dict[str, Any] | None = None,
    ) -> None:
        payload = dict(event_payload or {})
        await _ensure_workflow_schema_ready()
        await runtime.workflow_runtime.orchestrator.register_job(
            job=job,
            event_payload=payload,
        )
        await runtime.workflow_runtime.orchestrator.mark_running(
            job_id=job.job_id,
            event_payload=payload,
        )

    async def _workflow_mark_completed(
        *,
        job_id: int,
        event_payload: dict[str, Any] | None = None,
    ) -> None:
        await _ensure_workflow_schema_ready()
        await runtime.workflow_runtime.orchestrator.mark_completed(
            job_id=job_id,
            event_payload=event_payload,
        )

    async def _workflow_mark_failed(
        *,
        job_id: int,
        error_code: str,
        error_message: str,
        event_payload: dict[str, Any] | None = None,
    ) -> None:
        await _ensure_workflow_schema_ready()
        await runtime.workflow_runtime.orchestrator.mark_failed(
            job_id=job_id,
            error_code=error_code,
            error_message=error_message,
            event_payload=event_payload,
        )

    @app.get("/healthz")
    async def healthz() -> dict[str, bool]:
        return {"ok": True}

    async def _handle_blindization_rejection(
        *,
        dispatch_type: str,
        raw_payload: dict[str, Any],
        sensitive_hits: list[str],
    ) -> None:
        meta = _extract_dispatch_meta_from_raw(raw_payload)
        job_id = int(meta.get("jobId") or 0)
        session_id = int(meta.get("sessionId") or 0)
        trace_id = str(meta.get("traceId") or "")
        if job_id <= 0 or session_id <= 0 or not trace_id:
            raise HTTPException(status_code=422, detail="input_not_blinded")
        scope_id = int(meta.get("scopeId") or 1)
        dims = _extract_receipt_dims_from_raw(dispatch_type, raw_payload)
        request_payload = dict(raw_payload)
        workflow_job = _build_workflow_job(
            dispatch_type=dispatch_type,
            job_id=job_id,
            trace_id=trace_id,
            scope_id=scope_id,
            session_id=session_id,
            idempotency_key=str(meta.get("idempotencyKey") or ""),
            rubric_version=str(meta.get("rubricVersion") or ""),
            judge_policy_version=str(meta.get("judgePolicyVersion") or ""),
            topic_domain=str(meta.get("topicDomain") or ""),
            retrieval_profile=(
                str(meta.get("retrievalProfile")) if meta.get("retrievalProfile") is not None else None
            ),
        )
        runtime.trace_store.register_start(job_id=job_id, trace_id=trace_id, request=request_payload)
        await _workflow_register_and_mark_running(
            job=workflow_job,
            event_payload={
                "dispatchType": dispatch_type,
                "scopeId": scope_id,
                "sessionId": session_id,
                "phaseNo": dims.get("phaseNo"),
                "phaseStartNo": dims.get("phaseStartNo"),
                "phaseEndNo": dims.get("phaseEndNo"),
                "messageCount": dims.get("messageCount"),
                "traceId": trace_id,
                "rejectionCode": "input_not_blinded",
                "sensitiveHits": sensitive_hits[:12],
            },
        )
        response = {
            "accepted": False,
            "dispatchType": dispatch_type,
            "status": "callback_failed",
            "jobId": job_id,
            "scopeId": scope_id,
            "sessionId": session_id,
            "traceId": trace_id,
        }
        if dispatch_type == "phase":
            response["phaseNo"] = dims.get("phaseNo")
            response["messageCount"] = dims.get("messageCount")
        else:
            response["phaseStartNo"] = dims.get("phaseStartNo")
            response["phaseEndNo"] = dims.get("phaseEndNo")

        error_code = "input_not_blinded"
        error_message = (
            "sensitive fields detected in judge input: " + ",".join(sensitive_hits[:12])
        )
        failed_payload = _build_failed_callback_payload(
            job_id=job_id,
            dispatch_type=dispatch_type,
            trace_id=trace_id,
            error_code=error_code,
            error_message=error_message,
        )
        failed_callback_fn = _failed_callback_fn_for_dispatch(runtime, dispatch_type)
        try:
            failed_attempts, failed_retries = await _invoke_v3_callback_with_retry(
                runtime=runtime,
                callback_fn=failed_callback_fn,
                job_id=job_id,
                payload=failed_payload,
            )
        except Exception as failed_err:
            receipt_response = {
                **response,
                "callbackStatus": "failed_callback_failed",
                "callbackError": error_message,
                "failedCallbackPayload": failed_payload,
                "failedCallbackError": str(failed_err),
            }
            await _persist_dispatch_receipt(
                dispatch_type=dispatch_type,
                job_id=job_id,
                scope_id=scope_id,
                session_id=session_id,
                trace_id=trace_id,
                idempotency_key=str(meta.get("idempotencyKey") or ""),
                rubric_version=str(meta.get("rubricVersion") or ""),
                judge_policy_version=str(meta.get("judgePolicyVersion") or ""),
                topic_domain=str(meta.get("topicDomain") or ""),
                retrieval_profile=(
                    str(meta.get("retrievalProfile")) if meta.get("retrievalProfile") is not None else None
                ),
                phase_no=dims.get("phaseNo"),
                phase_start_no=dims.get("phaseStartNo"),
                phase_end_no=dims.get("phaseEndNo"),
                message_start_id=dims.get("messageStartId"),
                message_end_id=dims.get("messageEndId"),
                message_count=dims.get("messageCount"),
                status="callback_failed",
                request_payload=request_payload,
                response_payload=receipt_response,
            )
            runtime.trace_store.register_failure(
                job_id=job_id,
                response=receipt_response,
                callback_status="failed_callback_failed",
                callback_error=str(failed_err),
            )
            await _workflow_mark_failed(
                job_id=job_id,
                error_code=f"{dispatch_type}_failed_callback_failed",
                error_message=str(failed_err),
                event_payload={
                    "dispatchType": dispatch_type,
                    "phaseNo": dims.get("phaseNo"),
                    "phaseStartNo": dims.get("phaseStartNo"),
                    "phaseEndNo": dims.get("phaseEndNo"),
                    "callbackStatus": "failed_callback_failed",
                    "sensitiveHits": sensitive_hits[:12],
                },
            )
            raise HTTPException(
                status_code=502,
                detail=f"{dispatch_type}_failed_callback_failed: {failed_err}",
            ) from failed_err

        receipt_response = {
            **response,
            "callbackStatus": "failed_reported",
            "callbackError": error_message,
            "failedCallbackPayload": failed_payload,
            "failedCallbackAttempts": failed_attempts,
            "failedCallbackRetries": failed_retries,
        }
        await _persist_dispatch_receipt(
            dispatch_type=dispatch_type,
            job_id=job_id,
            scope_id=scope_id,
            session_id=session_id,
            trace_id=trace_id,
            idempotency_key=str(meta.get("idempotencyKey") or ""),
            rubric_version=str(meta.get("rubricVersion") or ""),
            judge_policy_version=str(meta.get("judgePolicyVersion") or ""),
            topic_domain=str(meta.get("topicDomain") or ""),
            retrieval_profile=(
                str(meta.get("retrievalProfile")) if meta.get("retrievalProfile") is not None else None
            ),
            phase_no=dims.get("phaseNo"),
            phase_start_no=dims.get("phaseStartNo"),
            phase_end_no=dims.get("phaseEndNo"),
            message_start_id=dims.get("messageStartId"),
            message_end_id=dims.get("messageEndId"),
            message_count=dims.get("messageCount"),
            status="callback_failed",
            request_payload=request_payload,
            response_payload=receipt_response,
        )
        runtime.trace_store.register_failure(
            job_id=job_id,
            response=receipt_response,
            callback_status="failed_reported",
            callback_error=error_message,
        )
        await _workflow_mark_failed(
            job_id=job_id,
            error_code=error_code,
            error_message=error_message,
            event_payload={
                "dispatchType": dispatch_type,
                "phaseNo": dims.get("phaseNo"),
                "phaseStartNo": dims.get("phaseStartNo"),
                "phaseEndNo": dims.get("phaseEndNo"),
                "callbackStatus": "failed_reported",
                "sensitiveHits": sensitive_hits[:12],
            },
        )
        raise HTTPException(status_code=422, detail=error_code)

    @app.post("/internal/judge/v3/phase/dispatch")
    async def dispatch_judge_phase(
        request: Request,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        try:
            raw_payload = await request.json()
        except Exception as err:
            raise HTTPException(status_code=422, detail=f"invalid_json: {err}") from err
        if not isinstance(raw_payload, dict):
            raise HTTPException(status_code=422, detail="invalid_payload")
        sensitive_hits = _find_sensitive_key_hits(raw_payload)
        if sensitive_hits:
            await _handle_blindization_rejection(
                dispatch_type="phase",
                raw_payload=raw_payload,
                sensitive_hits=sensitive_hits,
            )
        try:
            parsed = PhaseDispatchRequest.model_validate(raw_payload)
        except ValidationError as err:
            raise HTTPException(status_code=422, detail=err.errors()) from err
        _validate_phase_dispatch_request(parsed)

        replayed = _resolve_idempotency_or_raise(
            runtime=runtime,
            key=parsed.idempotency_key,
            job_id=parsed.job_id,
            conflict_detail="idempotency_conflict:phase_dispatch",
        )
        if replayed is not None:
            return replayed

        response = {
            "accepted": True,
            "dispatchType": "phase",
            "status": "queued",
            "jobId": parsed.job_id,
            "scopeId": parsed.scope_id,
            "sessionId": parsed.session_id,
            "phaseNo": parsed.phase_no,
            "messageCount": parsed.message_count,
            "traceId": parsed.trace_id,
        }
        request_payload = parsed.model_dump(mode="json")
        workflow_job = _build_workflow_job(
            dispatch_type="phase",
            job_id=parsed.job_id,
            trace_id=parsed.trace_id,
            scope_id=parsed.scope_id,
            session_id=parsed.session_id,
            idempotency_key=parsed.idempotency_key,
            rubric_version=parsed.rubric_version,
            judge_policy_version=parsed.judge_policy_version,
            topic_domain=parsed.topic_domain,
            retrieval_profile=parsed.retrieval_profile,
        )
        runtime.trace_store.register_start(
            job_id=parsed.job_id,
            trace_id=parsed.trace_id,
            request=request_payload,
        )
        await _persist_dispatch_receipt(
            dispatch_type="phase",
            job_id=parsed.job_id,
            scope_id=parsed.scope_id,
            session_id=parsed.session_id,
            trace_id=parsed.trace_id,
            idempotency_key=parsed.idempotency_key,
            rubric_version=parsed.rubric_version,
            judge_policy_version=parsed.judge_policy_version,
            topic_domain=parsed.topic_domain,
            retrieval_profile=parsed.retrieval_profile,
            phase_no=parsed.phase_no,
            phase_start_no=None,
            phase_end_no=None,
            message_start_id=parsed.message_start_id,
            message_end_id=parsed.message_end_id,
            message_count=parsed.message_count,
            status="queued",
            request_payload=request_payload,
            response_payload=response,
        )
        await _workflow_register_and_mark_running(
            job=workflow_job,
            event_payload={
                "dispatchType": "phase",
                "scopeId": parsed.scope_id,
                "sessionId": parsed.session_id,
                "phaseNo": parsed.phase_no,
                "messageCount": parsed.message_count,
                "traceId": parsed.trace_id,
            },
        )

        phase_report_payload = await build_phase_report_payload_v3_phase(
            request=parsed,
            settings=runtime.settings,
            gateway_runtime=runtime.gateway_runtime,
        )
        try:
            callback_attempts, callback_retries = await _invoke_v3_callback_with_retry(
                runtime=runtime,
                callback_fn=_report_callback_fn_for_dispatch(runtime, "phase"),
                job_id=parsed.job_id,
                payload=phase_report_payload,
            )
        except Exception as err:
            error_code = "phase_callback_retry_exhausted"
            error_message = str(err)
            failed_payload = _build_failed_callback_payload(
                job_id=parsed.job_id,
                dispatch_type="phase",
                trace_id=parsed.trace_id,
                error_code=error_code,
                error_message=error_message,
                degradation_level=int(phase_report_payload.get("degradationLevel") or 0),
            )
            try:
                failed_attempts, failed_retries = await _invoke_v3_callback_with_retry(
                    runtime=runtime,
                    callback_fn=_failed_callback_fn_for_dispatch(runtime, "phase"),
                    job_id=parsed.job_id,
                    payload=failed_payload,
                )
            except Exception as failed_err:
                receipt_response = {
                    **response,
                    "status": "callback_failed",
                    "callbackStatus": "failed_callback_failed",
                    "callbackError": error_message,
                    "reportPayload": phase_report_payload,
                    "failedCallbackPayload": failed_payload,
                    "failedCallbackError": str(failed_err),
                }
                await _persist_dispatch_receipt(
                    dispatch_type="phase",
                    job_id=parsed.job_id,
                    scope_id=parsed.scope_id,
                    session_id=parsed.session_id,
                    trace_id=parsed.trace_id,
                    idempotency_key=parsed.idempotency_key,
                    rubric_version=parsed.rubric_version,
                    judge_policy_version=parsed.judge_policy_version,
                    topic_domain=parsed.topic_domain,
                    retrieval_profile=parsed.retrieval_profile,
                    phase_no=parsed.phase_no,
                    phase_start_no=None,
                    phase_end_no=None,
                    message_start_id=parsed.message_start_id,
                    message_end_id=parsed.message_end_id,
                    message_count=parsed.message_count,
                    status="callback_failed",
                    request_payload=request_payload,
                    response_payload=receipt_response,
                )
                runtime.trace_store.register_failure(
                    job_id=parsed.job_id,
                    response=receipt_response,
                    callback_status="failed_callback_failed",
                    callback_error=str(failed_err),
                )
                await _workflow_mark_failed(
                    job_id=parsed.job_id,
                    error_code="phase_failed_callback_failed",
                    error_message=str(failed_err),
                    event_payload={
                        "dispatchType": "phase",
                        "phaseNo": parsed.phase_no,
                        "callbackStatus": "failed_callback_failed",
                    },
                )
                runtime.trace_store.clear_idempotency(parsed.idempotency_key)
                raise HTTPException(
                    status_code=502,
                    detail=f"phase_failed_callback_failed: {failed_err}",
                ) from failed_err

            receipt_response = {
                **response,
                "status": "callback_failed",
                "callbackStatus": "failed_reported",
                "callbackError": error_message,
                "reportPayload": phase_report_payload,
                "failedCallbackPayload": failed_payload,
                "failedCallbackAttempts": failed_attempts,
                "failedCallbackRetries": failed_retries,
            }
            await _persist_dispatch_receipt(
                dispatch_type="phase",
                job_id=parsed.job_id,
                scope_id=parsed.scope_id,
                session_id=parsed.session_id,
                trace_id=parsed.trace_id,
                idempotency_key=parsed.idempotency_key,
                rubric_version=parsed.rubric_version,
                judge_policy_version=parsed.judge_policy_version,
                topic_domain=parsed.topic_domain,
                retrieval_profile=parsed.retrieval_profile,
                phase_no=parsed.phase_no,
                phase_start_no=None,
                phase_end_no=None,
                message_start_id=parsed.message_start_id,
                message_end_id=parsed.message_end_id,
                message_count=parsed.message_count,
                status="callback_failed",
                request_payload=request_payload,
                response_payload=receipt_response,
            )
            runtime.trace_store.register_failure(
                job_id=parsed.job_id,
                response=receipt_response,
                callback_status="failed_reported",
                callback_error=error_message,
            )
            await _workflow_mark_failed(
                job_id=parsed.job_id,
                error_code=error_code,
                error_message=error_message,
                event_payload={
                    "dispatchType": "phase",
                    "phaseNo": parsed.phase_no,
                    "callbackStatus": "failed_reported",
                },
            )
            runtime.trace_store.clear_idempotency(parsed.idempotency_key)
            raise HTTPException(status_code=502, detail=f"phase_callback_failed: {err}") from err

        reported_response = {
            **response,
            "callbackStatus": "reported",
            "callbackAttempts": callback_attempts,
            "callbackRetries": callback_retries,
            "reportPayload": phase_report_payload,
        }
        await _persist_dispatch_receipt(
            dispatch_type="phase",
            job_id=parsed.job_id,
            scope_id=parsed.scope_id,
            session_id=parsed.session_id,
            trace_id=parsed.trace_id,
            idempotency_key=parsed.idempotency_key,
            rubric_version=parsed.rubric_version,
            judge_policy_version=parsed.judge_policy_version,
            topic_domain=parsed.topic_domain,
            retrieval_profile=parsed.retrieval_profile,
            phase_no=parsed.phase_no,
            phase_start_no=None,
            phase_end_no=None,
            message_start_id=parsed.message_start_id,
            message_end_id=parsed.message_end_id,
            message_count=parsed.message_count,
            status="reported",
            request_payload=request_payload,
            response_payload=reported_response,
        )
        runtime.trace_store.register_success(
            job_id=parsed.job_id,
            response=reported_response,
            callback_status="reported",
            report_summary=_build_trace_report_summary(
                dispatch_type="phase",
                payload=phase_report_payload,
                callback_status="reported",
                callback_error=None,
            ),
        )
        await _workflow_mark_completed(
            job_id=parsed.job_id,
            event_payload={
                "dispatchType": "phase",
                "phaseNo": parsed.phase_no,
                "callbackStatus": "reported",
            },
        )
        runtime.trace_store.set_idempotency_success(
            key=parsed.idempotency_key,
            job_id=parsed.job_id,
            response=response,
            ttl_secs=runtime.settings.idempotency_ttl_secs,
        )
        return response

    @app.post("/internal/judge/v3/final/dispatch")
    async def dispatch_judge_final(
        request: Request,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        try:
            raw_payload = await request.json()
        except Exception as err:
            raise HTTPException(status_code=422, detail=f"invalid_json: {err}") from err
        if not isinstance(raw_payload, dict):
            raise HTTPException(status_code=422, detail="invalid_payload")
        sensitive_hits = _find_sensitive_key_hits(raw_payload)
        if sensitive_hits:
            await _handle_blindization_rejection(
                dispatch_type="final",
                raw_payload=raw_payload,
                sensitive_hits=sensitive_hits,
            )
        try:
            parsed = FinalDispatchRequest.model_validate(raw_payload)
        except ValidationError as err:
            raise HTTPException(status_code=422, detail=err.errors()) from err
        _validate_final_dispatch_request(parsed)

        replayed = _resolve_idempotency_or_raise(
            runtime=runtime,
            key=parsed.idempotency_key,
            job_id=parsed.job_id,
            conflict_detail="idempotency_conflict:final_dispatch",
        )
        if replayed is not None:
            return replayed

        response = {
            "accepted": True,
            "dispatchType": "final",
            "status": "queued",
            "jobId": parsed.job_id,
            "scopeId": parsed.scope_id,
            "sessionId": parsed.session_id,
            "phaseStartNo": parsed.phase_start_no,
            "phaseEndNo": parsed.phase_end_no,
            "traceId": parsed.trace_id,
        }
        request_payload = parsed.model_dump(mode="json")
        workflow_job = _build_workflow_job(
            dispatch_type="final",
            job_id=parsed.job_id,
            trace_id=parsed.trace_id,
            scope_id=parsed.scope_id,
            session_id=parsed.session_id,
            idempotency_key=parsed.idempotency_key,
            rubric_version=parsed.rubric_version,
            judge_policy_version=parsed.judge_policy_version,
            topic_domain=parsed.topic_domain,
            retrieval_profile=None,
        )
        runtime.trace_store.register_start(
            job_id=parsed.job_id,
            trace_id=parsed.trace_id,
            request=request_payload,
        )
        await _persist_dispatch_receipt(
            dispatch_type="final",
            job_id=parsed.job_id,
            scope_id=parsed.scope_id,
            session_id=parsed.session_id,
            trace_id=parsed.trace_id,
            idempotency_key=parsed.idempotency_key,
            rubric_version=parsed.rubric_version,
            judge_policy_version=parsed.judge_policy_version,
            topic_domain=parsed.topic_domain,
            retrieval_profile=None,
            phase_no=None,
            phase_start_no=parsed.phase_start_no,
            phase_end_no=parsed.phase_end_no,
            message_start_id=None,
            message_end_id=None,
            message_count=None,
            status="queued",
            request_payload=request_payload,
            response_payload=response,
        )
        await _workflow_register_and_mark_running(
            job=workflow_job,
            event_payload={
                "dispatchType": "final",
                "scopeId": parsed.scope_id,
                "sessionId": parsed.session_id,
                "phaseStartNo": parsed.phase_start_no,
                "phaseEndNo": parsed.phase_end_no,
                "traceId": parsed.trace_id,
            },
        )

        phase_receipts = await _list_dispatch_receipts(
            dispatch_type="phase",
            session_id=parsed.session_id,
            status="reported",
            limit=1000,
        )
        final_report_payload = _build_final_report_payload(
            runtime=runtime,
            request=parsed,
            phase_receipts=phase_receipts,
        )
        contract_missing_fields = _validate_final_report_payload_contract(final_report_payload)
        if contract_missing_fields:
            error_text = "final_contract_violation: missing_fields=" + ",".join(
                contract_missing_fields[:12]
            )
            alert = runtime.trace_store.upsert_audit_alert(
                job_id=parsed.job_id,
                scope_id=parsed.scope_id,
                trace_id=parsed.trace_id,
                alert_type="final_contract_violation",
                severity="critical",
                title="AI Judge Final Contract Violation",
                message=error_text,
                details={
                    "dispatchType": "final",
                    "sessionId": parsed.session_id,
                    "phaseRange": {
                        "startNo": parsed.phase_start_no,
                        "endNo": parsed.phase_end_no,
                    },
                    "missingFields": contract_missing_fields,
                    "errorCode": "final_contract_blocked",
                },
            )
            await _sync_audit_alert_to_facts(alert=alert)
            failed_payload = _build_failed_callback_payload(
                job_id=parsed.job_id,
                dispatch_type="final",
                trace_id=parsed.trace_id,
                error_code="final_contract_blocked",
                error_message=error_text,
                audit_alert_ids=[alert.alert_id],
                degradation_level=int(final_report_payload.get("degradationLevel") or 0),
            )
            try:
                failed_attempts, failed_retries = await _invoke_v3_callback_with_retry(
                    runtime=runtime,
                    callback_fn=_failed_callback_fn_for_dispatch(runtime, "final"),
                    job_id=parsed.job_id,
                    payload=failed_payload,
                )
            except Exception as failed_err:
                receipt_response = {
                    **response,
                    "status": "callback_failed",
                    "callbackStatus": "failed_callback_failed",
                    "callbackError": error_text,
                    "auditAlertIds": [alert.alert_id],
                    "reportPayload": final_report_payload,
                    "failedCallbackPayload": failed_payload,
                    "failedCallbackError": str(failed_err),
                }
                await _persist_dispatch_receipt(
                    dispatch_type="final",
                    job_id=parsed.job_id,
                    scope_id=parsed.scope_id,
                    session_id=parsed.session_id,
                    trace_id=parsed.trace_id,
                    idempotency_key=parsed.idempotency_key,
                    rubric_version=parsed.rubric_version,
                    judge_policy_version=parsed.judge_policy_version,
                    topic_domain=parsed.topic_domain,
                    retrieval_profile=None,
                    phase_no=None,
                    phase_start_no=parsed.phase_start_no,
                    phase_end_no=parsed.phase_end_no,
                    message_start_id=None,
                    message_end_id=None,
                    message_count=None,
                    status="callback_failed",
                    request_payload=request_payload,
                    response_payload=receipt_response,
                )
                runtime.trace_store.register_failure(
                    job_id=parsed.job_id,
                    response=receipt_response,
                    callback_status="failed_callback_failed",
                    callback_error=str(failed_err),
                )
                await _workflow_mark_failed(
                    job_id=parsed.job_id,
                    error_code="final_failed_callback_failed",
                    error_message=str(failed_err),
                    event_payload={
                        "dispatchType": "final",
                        "phaseStartNo": parsed.phase_start_no,
                        "phaseEndNo": parsed.phase_end_no,
                        "callbackStatus": "failed_callback_failed",
                    },
                )
                runtime.trace_store.clear_idempotency(parsed.idempotency_key)
                raise HTTPException(
                    status_code=502,
                    detail=f"final_failed_callback_failed: {failed_err}",
                ) from failed_err

            receipt_response = {
                **response,
                "status": "callback_failed",
                "callbackStatus": "blocked_failed_reported",
                "callbackError": error_text,
                "auditAlertIds": [alert.alert_id],
                "reportPayload": final_report_payload,
                "failedCallbackPayload": failed_payload,
                "failedCallbackAttempts": failed_attempts,
                "failedCallbackRetries": failed_retries,
            }
            await _persist_dispatch_receipt(
                dispatch_type="final",
                job_id=parsed.job_id,
                scope_id=parsed.scope_id,
                session_id=parsed.session_id,
                trace_id=parsed.trace_id,
                idempotency_key=parsed.idempotency_key,
                rubric_version=parsed.rubric_version,
                judge_policy_version=parsed.judge_policy_version,
                topic_domain=parsed.topic_domain,
                retrieval_profile=None,
                phase_no=None,
                phase_start_no=parsed.phase_start_no,
                phase_end_no=parsed.phase_end_no,
                message_start_id=None,
                message_end_id=None,
                message_count=None,
                status="callback_failed",
                request_payload=request_payload,
                response_payload=receipt_response,
            )
            runtime.trace_store.register_failure(
                job_id=parsed.job_id,
                response=receipt_response,
                callback_status="blocked_failed_reported",
                callback_error=error_text,
            )
            await _workflow_mark_failed(
                job_id=parsed.job_id,
                error_code="final_contract_blocked",
                error_message=error_text,
                event_payload={
                    "dispatchType": "final",
                    "phaseStartNo": parsed.phase_start_no,
                    "phaseEndNo": parsed.phase_end_no,
                    "callbackStatus": "blocked_failed_reported",
                    "missingFields": contract_missing_fields[:12],
                },
            )
            runtime.trace_store.clear_idempotency(parsed.idempotency_key)
            raise HTTPException(
                status_code=502,
                detail="final_contract_blocked: missing_critical_fields",
            )

        try:
            callback_attempts, callback_retries = await _invoke_v3_callback_with_retry(
                runtime=runtime,
                callback_fn=_report_callback_fn_for_dispatch(runtime, "final"),
                job_id=parsed.job_id,
                payload=final_report_payload,
            )
        except Exception as err:
            error_code = "final_callback_retry_exhausted"
            error_message = str(err)
            failed_payload = _build_failed_callback_payload(
                job_id=parsed.job_id,
                dispatch_type="final",
                trace_id=parsed.trace_id,
                error_code=error_code,
                error_message=error_message,
                degradation_level=int(final_report_payload.get("degradationLevel") or 0),
            )
            try:
                failed_attempts, failed_retries = await _invoke_v3_callback_with_retry(
                    runtime=runtime,
                    callback_fn=_failed_callback_fn_for_dispatch(runtime, "final"),
                    job_id=parsed.job_id,
                    payload=failed_payload,
                )
            except Exception as failed_err:
                receipt_response = {
                    **response,
                    "status": "callback_failed",
                    "callbackStatus": "failed_callback_failed",
                    "callbackError": error_message,
                    "reportPayload": final_report_payload,
                    "failedCallbackPayload": failed_payload,
                    "failedCallbackError": str(failed_err),
                }
                await _persist_dispatch_receipt(
                    dispatch_type="final",
                    job_id=parsed.job_id,
                    scope_id=parsed.scope_id,
                    session_id=parsed.session_id,
                    trace_id=parsed.trace_id,
                    idempotency_key=parsed.idempotency_key,
                    rubric_version=parsed.rubric_version,
                    judge_policy_version=parsed.judge_policy_version,
                    topic_domain=parsed.topic_domain,
                    retrieval_profile=None,
                    phase_no=None,
                    phase_start_no=parsed.phase_start_no,
                    phase_end_no=parsed.phase_end_no,
                    message_start_id=None,
                    message_end_id=None,
                    message_count=None,
                    status="callback_failed",
                    request_payload=request_payload,
                    response_payload=receipt_response,
                )
                runtime.trace_store.register_failure(
                    job_id=parsed.job_id,
                    response=receipt_response,
                    callback_status="failed_callback_failed",
                    callback_error=str(failed_err),
                )
                await _workflow_mark_failed(
                    job_id=parsed.job_id,
                    error_code="final_failed_callback_failed",
                    error_message=str(failed_err),
                    event_payload={
                        "dispatchType": "final",
                        "phaseStartNo": parsed.phase_start_no,
                        "phaseEndNo": parsed.phase_end_no,
                        "callbackStatus": "failed_callback_failed",
                    },
                )
                runtime.trace_store.clear_idempotency(parsed.idempotency_key)
                raise HTTPException(
                    status_code=502,
                    detail=f"final_failed_callback_failed: {failed_err}",
                ) from failed_err

            receipt_response = {
                **response,
                "status": "callback_failed",
                "callbackStatus": "failed_reported",
                "callbackError": error_message,
                "reportPayload": final_report_payload,
                "failedCallbackPayload": failed_payload,
                "failedCallbackAttempts": failed_attempts,
                "failedCallbackRetries": failed_retries,
            }
            await _persist_dispatch_receipt(
                dispatch_type="final",
                job_id=parsed.job_id,
                scope_id=parsed.scope_id,
                session_id=parsed.session_id,
                trace_id=parsed.trace_id,
                idempotency_key=parsed.idempotency_key,
                rubric_version=parsed.rubric_version,
                judge_policy_version=parsed.judge_policy_version,
                topic_domain=parsed.topic_domain,
                retrieval_profile=None,
                phase_no=None,
                phase_start_no=parsed.phase_start_no,
                phase_end_no=parsed.phase_end_no,
                message_start_id=None,
                message_end_id=None,
                message_count=None,
                status="callback_failed",
                request_payload=request_payload,
                response_payload=receipt_response,
            )
            runtime.trace_store.register_failure(
                job_id=parsed.job_id,
                response=receipt_response,
                callback_status="failed_reported",
                callback_error=error_message,
            )
            await _workflow_mark_failed(
                job_id=parsed.job_id,
                error_code=error_code,
                error_message=error_message,
                event_payload={
                    "dispatchType": "final",
                    "phaseStartNo": parsed.phase_start_no,
                    "phaseEndNo": parsed.phase_end_no,
                    "callbackStatus": "failed_reported",
                },
            )
            runtime.trace_store.clear_idempotency(parsed.idempotency_key)
            raise HTTPException(status_code=502, detail=f"final_callback_failed: {err}") from err

        reported_response = {
            **response,
            "callbackStatus": "reported",
            "callbackAttempts": callback_attempts,
            "callbackRetries": callback_retries,
            "reportPayload": final_report_payload,
        }
        await _persist_dispatch_receipt(
            dispatch_type="final",
            job_id=parsed.job_id,
            scope_id=parsed.scope_id,
            session_id=parsed.session_id,
            trace_id=parsed.trace_id,
            idempotency_key=parsed.idempotency_key,
            rubric_version=parsed.rubric_version,
            judge_policy_version=parsed.judge_policy_version,
            topic_domain=parsed.topic_domain,
            retrieval_profile=None,
            phase_no=None,
            phase_start_no=parsed.phase_start_no,
            phase_end_no=parsed.phase_end_no,
            message_start_id=None,
            message_end_id=None,
            message_count=None,
            status="reported",
            request_payload=request_payload,
            response_payload=reported_response,
        )
        runtime.trace_store.register_success(
            job_id=parsed.job_id,
            response=reported_response,
            callback_status="reported",
            report_summary=_build_trace_report_summary(
                dispatch_type="final",
                payload=final_report_payload,
                callback_status="reported",
                callback_error=None,
            ),
        )
        await _workflow_mark_completed(
            job_id=parsed.job_id,
            event_payload={
                "dispatchType": "final",
                "phaseStartNo": parsed.phase_start_no,
                "phaseEndNo": parsed.phase_end_no,
                "callbackStatus": "reported",
                "winner": final_report_payload.get("winner"),
            },
        )
        runtime.trace_store.set_idempotency_success(
            key=parsed.idempotency_key,
            job_id=parsed.job_id,
            response=response,
            ttl_secs=runtime.settings.idempotency_ttl_secs,
        )
        return response

    @app.get("/internal/judge/v3/phase/jobs/{job_id}/receipt")
    async def get_phase_dispatch_receipt(
        job_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        item = await _get_dispatch_receipt(dispatch_type="phase", job_id=job_id)
        if item is None:
            raise HTTPException(status_code=404, detail="phase_dispatch_receipt_not_found")
        return _serialize_dispatch_receipt(item)

    @app.get("/internal/judge/v3/final/jobs/{job_id}/receipt")
    async def get_final_dispatch_receipt(
        job_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        item = await _get_dispatch_receipt(dispatch_type="final", job_id=job_id)
        if item is None:
            raise HTTPException(status_code=404, detail="final_dispatch_receipt_not_found")
        return _serialize_dispatch_receipt(item)

    @app.get("/internal/judge/jobs/{job_id}/trace")
    async def get_judge_job_trace(
        job_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        record = runtime.trace_store.get_trace(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="judge_trace_not_found")
        replay_records = await _list_replay_records(job_id=job_id, limit=50)
        replay_items = (
            [
                {
                    "replayedAt": item.created_at.isoformat(),
                    "winner": item.winner,
                    "needsDrawVote": item.needs_draw_vote,
                    "provider": item.provider,
                }
                for item in replay_records
            ]
            if replay_records
            else [
                {
                    "replayedAt": item.replayed_at.isoformat(),
                    "winner": item.winner,
                    "needsDrawVote": item.needs_draw_vote,
                    "provider": item.provider,
                }
                for item in record.replays
            ]
        )
        return {
            "jobId": record.job_id,
            "traceId": record.trace_id,
            "status": record.status,
            "createdAt": record.created_at.isoformat(),
            "updatedAt": record.updated_at.isoformat(),
            "callbackStatus": record.callback_status,
            "callbackError": record.callback_error,
            "response": record.response,
            "request": record.request,
            "reportSummary": record.report_summary,
            "replays": replay_items,
        }

    @app.post("/internal/judge/jobs/{job_id}/replay")
    async def replay_judge_job(
        job_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        dispatch_type_normalized = str(dispatch_type or "auto").strip().lower()
        if dispatch_type_normalized not in {"auto", "phase", "final"}:
            raise HTTPException(status_code=422, detail="invalid_dispatch_type")

        chosen_dispatch_type = dispatch_type_normalized
        chosen_receipt = None
        if dispatch_type_normalized == "auto":
            final_receipt = await _get_dispatch_receipt(
                dispatch_type="final",
                job_id=job_id,
            )
            phase_receipt = await _get_dispatch_receipt(
                dispatch_type="phase",
                job_id=job_id,
            )
            chosen_receipt = final_receipt or phase_receipt
            if chosen_receipt is None:
                raise HTTPException(status_code=404, detail="replay_receipt_not_found")
            chosen_dispatch_type = "final" if final_receipt is not None else "phase"
        else:
            chosen_receipt = await _get_dispatch_receipt(
                dispatch_type=dispatch_type_normalized,
                job_id=job_id,
            )
            if chosen_receipt is None:
                raise HTTPException(status_code=404, detail="replay_receipt_not_found")

        request_snapshot = (
            chosen_receipt.request if isinstance(chosen_receipt.request, dict) else {}
        )
        trace_id = str(chosen_receipt.trace_id or request_snapshot.get("traceId") or "").strip()
        if not trace_id:
            raise HTTPException(status_code=409, detail="replay_missing_trace_id")

        report_payload: dict[str, Any]
        if chosen_dispatch_type == "final":
            try:
                final_request = FinalDispatchRequest.model_validate(request_snapshot)
            except ValidationError as err:
                raise HTTPException(status_code=409, detail=f"replay_invalid_final_request: {err}") from err
            _validate_final_dispatch_request(final_request)
            phase_receipts = await _list_dispatch_receipts(
                dispatch_type="phase",
                session_id=final_request.session_id,
                status="reported",
                limit=1000,
            )
            report_payload = _build_final_report_payload(
                runtime=runtime,
                request=final_request,
                phase_receipts=phase_receipts,
            )
        else:
            try:
                phase_request = PhaseDispatchRequest.model_validate(request_snapshot)
            except ValidationError as err:
                raise HTTPException(status_code=409, detail=f"replay_invalid_phase_request: {err}") from err
            _validate_phase_dispatch_request(phase_request)
            report_payload = await build_phase_report_payload_v3_phase(
                request=phase_request,
                settings=runtime.settings,
                gateway_runtime=runtime.gateway_runtime,
            )

        winner = str(report_payload.get("winner") or "").strip().lower()
        if winner not in {"pro", "con", "draw"}:
            agent3 = (
                report_payload.get("agent3WeightedScore")
                if isinstance(report_payload.get("agent3WeightedScore"), dict)
                else {}
            )
            winner = _resolve_winner(
                _safe_float(agent3.get("pro"), default=50.0),
                _safe_float(agent3.get("con"), default=50.0),
                margin=0.8,
            )
        needs_draw_vote = bool(report_payload.get("needsDrawVote")) if "needsDrawVote" in report_payload else winner == "draw"

        if runtime.trace_store.get_trace(job_id) is None:
            runtime.trace_store.register_start(
                job_id=job_id,
                trace_id=trace_id,
                request=request_snapshot,
            )
        runtime.trace_store.mark_replay(
            job_id=job_id,
            winner=winner,
            needs_draw_vote=needs_draw_vote,
            provider=runtime.settings.provider,
        )
        replay_row = await _append_replay_record(
            dispatch_type=chosen_dispatch_type,
            job_id=job_id,
            trace_id=trace_id,
            winner=winner,
            needs_draw_vote=needs_draw_vote,
            provider=runtime.settings.provider,
            report_payload=report_payload,
        )
        replayed_at = replay_row.created_at.isoformat()

        return {
            "jobId": job_id,
            "dispatchType": chosen_dispatch_type,
            "replayedAt": replayed_at,
            "reportPayload": report_payload,
            "winner": winner,
            "needsDrawVote": needs_draw_vote,
            "traceId": trace_id,
        }

    @app.get("/internal/judge/jobs/{job_id}/replay/report")
    async def get_judge_replay_report(
        job_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        record = runtime.trace_store.get_trace(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="judge_trace_not_found")
        return _build_replay_report_payload(record)

    @app.get("/internal/judge/jobs/replay/reports")
    async def list_judge_replay_reports(
        x_ai_internal_key: str | None = Header(default=None),
        status: str | None = Query(default=None),
        winner: str | None = Query(default=None),
        callback_status: str | None = Query(default=None),
        trace_id: str | None = Query(default=None),
        created_after: datetime | None = Query(default=None),
        created_before: datetime | None = Query(default=None),
        has_audit_alert: bool | None = Query(default=None),
        limit: int = Query(default=20, ge=1, le=200),
        include_report: bool = Query(default=False),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        normalized_created_after = _normalize_query_datetime(created_after)
        normalized_created_before = _normalize_query_datetime(created_before)
        query = TraceQuery(
            status=status,
            winner=winner,
            callback_status=callback_status,
            trace_id=trace_id,
            created_after=normalized_created_after,
            created_before=normalized_created_before,
            has_audit_alert=has_audit_alert,
            limit=limit,
        )
        records = runtime.trace_store.list_traces(query=query)
        if include_report:
            items = [_build_replay_report_payload(record) for record in records]
        else:
            items = [_build_replay_report_summary(record) for record in records]
        return {
            "count": len(items),
            "items": items,
            "filters": {
                "status": status,
                "winner": winner,
                "callbackStatus": callback_status,
                "traceId": trace_id,
                "createdAfter": normalized_created_after.isoformat()
                if normalized_created_after
                else None,
                "createdBefore": normalized_created_before.isoformat()
                if normalized_created_before
                else None,
                "hasAuditAlert": has_audit_alert,
                "limit": limit,
                "includeReport": include_report,
            },
        }

    @app.get("/internal/judge/jobs/{job_id}/alerts")
    async def list_judge_job_alerts(
        job_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        status: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        items = await _list_audit_alerts(
            job_id=job_id,
            status=status,
            limit=limit,
        )
        return {
            "jobId": job_id,
            "count": len(items),
            "items": [_serialize_alert_item(item) for item in items],
        }

    async def _transition_alert_status(
        *,
        job_id: int,
        alert_id: str,
        to_status: str,
        actor: str | None,
        reason: str | None,
    ) -> dict[str, Any]:
        row = runtime.trace_store.transition_audit_alert(
            job_id=job_id,
            alert_id=alert_id,
            to_status=to_status,
            actor=actor,
            reason=reason,
        )
        if row is None:
            raise HTTPException(status_code=409, detail="invalid_alert_status_transition")
        await _sync_audit_alert_to_facts(alert=row)
        transitioned = await runtime.workflow_runtime.facts.transition_audit_alert(
            alert_id=alert_id,
            to_status=to_status,
            now=row.updated_at,
        )
        if transitioned is None:
            raise HTTPException(status_code=409, detail="invalid_alert_status_transition")
        return {
            "ok": True,
            "jobId": job_id,
            "alertId": alert_id,
            "status": transitioned.status,
            "item": _serialize_alert_item(transitioned),
        }

    @app.post("/internal/judge/jobs/{job_id}/alerts/{alert_id}/ack")
    async def ack_judge_job_alert(
        job_id: int,
        alert_id: str,
        x_ai_internal_key: str | None = Header(default=None),
        actor: str | None = Query(default=None),
        reason: str | None = Query(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _transition_alert_status(
            job_id=job_id,
            alert_id=alert_id,
            to_status="acked",
            actor=actor,
            reason=reason,
        )

    @app.post("/internal/judge/jobs/{job_id}/alerts/{alert_id}/resolve")
    async def resolve_judge_job_alert(
        job_id: int,
        alert_id: str,
        x_ai_internal_key: str | None = Header(default=None),
        actor: str | None = Query(default=None),
        reason: str | None = Query(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _transition_alert_status(
            job_id=job_id,
            alert_id=alert_id,
            to_status="resolved",
            actor=actor,
            reason=reason,
        )

    @app.get("/internal/judge/alerts/outbox")
    async def list_judge_alert_outbox(
        x_ai_internal_key: str | None = Header(default=None),
        delivery_status: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        rows = runtime.trace_store.list_alert_outbox(
            delivery_status=delivery_status,
            limit=limit,
        )
        return {
            "count": len(rows),
            "items": [_serialize_outbox_event(item) for item in rows],
            "filters": {
                "deliveryStatus": delivery_status,
                "limit": limit,
            },
        }

    @app.post("/internal/judge/alerts/outbox/{event_id}/delivery")
    async def mark_judge_alert_outbox_delivery(
        event_id: str,
        x_ai_internal_key: str | None = Header(default=None),
        delivery_status: str = Query(default="sent"),
        error_message: str | None = Query(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        item = runtime.trace_store.mark_alert_outbox_delivery(
            event_id=event_id,
            delivery_status=delivery_status,
            error_message=error_message,
        )
        if item is None:
            raise HTTPException(status_code=404, detail="alert_outbox_event_not_found")
        return {
            "ok": True,
            "item": _serialize_outbox_event(item),
        }

    @app.get("/internal/judge/rag/diagnostics")
    async def get_rag_diagnostics(
        job_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        record = runtime.trace_store.get_trace(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="judge_trace_not_found")
        report_summary = record.report_summary or {}
        payload = report_summary.get("payload") or {}
        return {
            "jobId": job_id,
            "traceId": record.trace_id,
            "retrievalDiagnostics": payload.get("retrievalDiagnostics"),
            "ragSources": payload.get("ragSources"),
            "ragBackend": payload.get("ragBackend"),
            "ragRequestedBackend": payload.get("ragRequestedBackend"),
            "ragBackendFallbackReason": payload.get("ragBackendFallbackReason"),
        }

    return app


def create_default_app(*, load_settings_fn: LoadSettingsFn = load_settings) -> FastAPI:
    return create_app(
        create_runtime(
            settings=load_settings_fn(),
        )
    )
