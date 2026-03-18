from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Header, HTTPException, Query

from .callback_client import (
    callback_failed,
    callback_final_report,
    callback_phase_report,
    callback_report,
)
from .compliance_guard import validate_blinded_dispatch_request
from .dispatch_controller import (
    BuildReportByRuntimeFn,
    CallbackFailedFn,
    CallbackReportFn,
    DispatchRuntimeConfig,
    SleepFn,
    process_dispatch_request,
)
from .models import FinalDispatchRequest, JudgeDispatchRequest, PhaseDispatchRequest
from .scoring import resolve_effective_style_mode
from .runtime_orchestrator import build_report_by_runtime
from .settings import (
    Settings,
    build_callback_client_config,
    build_dispatch_runtime_config,
    load_settings,
)
from .trace_store import TraceQuery, TraceStoreProtocol, build_trace_store_from_settings
from .wiring import build_dispatch_callbacks, build_v3_dispatch_callbacks

BuildReportByRuntimeImpl = Callable[..., Awaitable[Any]]
LoadSettingsFn = Callable[[], Settings]


@dataclass(frozen=True)
class AppRuntime:
    settings: Settings
    dispatch_runtime_cfg: DispatchRuntimeConfig
    build_report_by_runtime_adapter: BuildReportByRuntimeFn
    callback_report_fn: CallbackReportFn
    callback_failed_fn: CallbackFailedFn
    callback_phase_report_fn: CallbackReportFn
    callback_final_report_fn: CallbackReportFn
    sleep_fn: SleepFn
    trace_store: TraceStoreProtocol


def require_internal_key(settings: Settings, header_value: str | None) -> None:
    if not header_value:
        raise HTTPException(status_code=401, detail="missing x-ai-internal-key")
    if header_value.strip() != settings.ai_internal_key:
        raise HTTPException(status_code=401, detail="invalid x-ai-internal-key")


def build_report_by_runtime_adapter(
    *,
    settings: Settings,
    trace_store: TraceStoreProtocol,
    build_report_by_runtime_fn: BuildReportByRuntimeImpl = build_report_by_runtime,
) -> BuildReportByRuntimeFn:
    async def _adapter(
        request: JudgeDispatchRequest,
        effective_style_mode: str,
        style_mode_source: str,
    ):
        return await build_report_by_runtime_fn(
            request=request,
            effective_style_mode=effective_style_mode,
            style_mode_source=style_mode_source,
            settings=settings,
            trace_store=trace_store,
        )

    return _adapter


def create_runtime(
    *,
    settings: Settings,
    build_report_by_runtime_fn: BuildReportByRuntimeImpl = build_report_by_runtime,
    callback_report_impl=callback_report,
    callback_failed_impl=callback_failed,
    callback_phase_report_impl=callback_phase_report,
    callback_final_report_impl=callback_final_report,
    sleep_fn: SleepFn = asyncio.sleep,
) -> AppRuntime:
    trace_store = build_trace_store_from_settings(settings=settings)
    callback_cfg = build_callback_client_config(settings)
    callback_report_fn, callback_failed_fn = build_dispatch_callbacks(
        cfg=callback_cfg,
        callback_report_impl=callback_report_impl,
        callback_failed_impl=callback_failed_impl,
    )
    callback_phase_report_fn, callback_final_report_fn = build_v3_dispatch_callbacks(
        cfg=callback_cfg,
        callback_phase_report_impl=callback_phase_report_impl,
        callback_final_report_impl=callback_final_report_impl,
    )
    return AppRuntime(
        settings=settings,
        dispatch_runtime_cfg=build_dispatch_runtime_config(settings),
        build_report_by_runtime_adapter=build_report_by_runtime_adapter(
            settings=settings,
            trace_store=trace_store,
            build_report_by_runtime_fn=build_report_by_runtime_fn,
        ),
        callback_report_fn=callback_report_fn,
        callback_failed_fn=callback_failed_fn,
        callback_phase_report_fn=callback_phase_report_fn,
        callback_final_report_fn=callback_final_report_fn,
        sleep_fn=sleep_fn,
        trace_store=trace_store,
    )


def _extract_report_evidence_refs(report_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(report_payload, dict):
        return []

    payload = report_payload.get("payload")
    if isinstance(payload, dict):
        evidence = payload.get("evidenceRefs") or payload.get("verdictEvidenceRefs")
        if isinstance(evidence, list):
            return [row for row in evidence if isinstance(row, dict)]

    evidence = report_payload.get("evidenceRefs")
    if isinstance(evidence, list):
        return [row for row in evidence if isinstance(row, dict)]
    return []


def _extract_runtime_audit_alerts(
    *,
    response: dict[str, Any] | None,
    report_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    response_obj = response if isinstance(response, dict) else {}
    report_obj = report_payload if isinstance(report_payload, dict) else {}

    response_alert = response_obj.get("auditAlert")
    if isinstance(response_alert, dict):
        out.append(response_alert)

    payload = report_obj.get("payload")
    if isinstance(payload, dict):
        payload_alerts = payload.get("auditAlerts")
        if isinstance(payload_alerts, list):
            out.extend([row for row in payload_alerts if isinstance(row, dict)])
    return out


def _normalize_runtime_audit_alert(row: dict[str, Any]) -> dict[str, Any]:
    alert_type = str(row.get("type") or "judge_runtime_alert").strip().lower()
    severity = str(row.get("severity") or "warning").strip().lower()
    status = str(row.get("status") or "").strip().lower()
    violations = row.get("violations")
    violations_list = (
        [str(item).strip() for item in violations if str(item).strip()]
        if isinstance(violations, list)
        else []
    )
    title = str(row.get("title") or "").strip()
    if not title:
        if alert_type == "compliance_violation":
            title = "AI Judge Compliance Violation"
        else:
            title = "AI Judge Runtime Alert"
    message = str(row.get("message") or "").strip()
    if not message:
        if violations_list:
            message = f"violations={','.join(violations_list)}"
        elif status:
            message = f"status={status}"
        else:
            message = "ai_judge alert raised"
    return {
        "alertType": alert_type,
        "severity": severity or "warning",
        "title": title,
        "message": message,
        "details": {
            "raw": row,
            "status": status or None,
            "violations": violations_list,
        },
    }


def _calc_topic_memory_quality_audit(
    *,
    settings: Settings,
    request: JudgeDispatchRequest,
    response: dict[str, Any],
    report_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    evidence_refs = _extract_report_evidence_refs(report_payload)
    evidence_count = len(evidence_refs)
    rationale = str((report_payload or {}).get("rationale") or "").strip()
    rationale_chars = len(rationale)
    winner = str(response.get("winner") or "").strip().lower()

    winner_score = 0.2 if winner in {"pro", "con", "draw"} else 0.0
    evidence_score = min(0.4, evidence_count * 0.1)
    if settings.topic_memory_min_rationale_chars <= 0:
        rationale_score = 0.4
    else:
        rationale_score = min(
            0.4,
            (rationale_chars / float(settings.topic_memory_min_rationale_chars)) * 0.4,
        )
    quality_score = round(min(1.0, winner_score + evidence_score + rationale_score), 4)

    reject_reasons: list[str] = []
    if evidence_count < settings.topic_memory_min_evidence_refs:
        reject_reasons.append("insufficient_evidence_refs")
    if rationale_chars < settings.topic_memory_min_rationale_chars:
        reject_reasons.append("insufficient_rationale_chars")
    if quality_score < settings.topic_memory_min_quality_score:
        reject_reasons.append("quality_score_below_threshold")

    return {
        "topicDomain": getattr(request, "topic_domain", "default"),
        "rubricVersion": request.rubric_version,
        "winner": winner or None,
        "evidenceCount": evidence_count,
        "rationaleChars": rationale_chars,
        "qualityScore": quality_score,
        "accepted": len(reject_reasons) == 0,
        "rejectReasons": reject_reasons,
        "thresholds": {
            "minEvidenceRefs": settings.topic_memory_min_evidence_refs,
            "minRationaleChars": settings.topic_memory_min_rationale_chars,
            "minQualityScore": settings.topic_memory_min_quality_score,
        },
    }


def _serialize_alert_item(alert: Any) -> dict[str, Any]:
    return {
        "alertId": alert.alert_id,
        "jobId": alert.job_id,
        "scopeId": alert.scope_id,
        "traceId": alert.trace_id,
        "type": alert.alert_type,
        "severity": alert.severity,
        "title": alert.title,
        "message": alert.message,
        "details": alert.details,
        "status": alert.status,
        "createdAt": alert.created_at.isoformat(),
        "updatedAt": alert.updated_at.isoformat(),
        "acknowledgedAt": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
        "resolvedAt": alert.resolved_at.isoformat() if alert.resolved_at else None,
        "transitions": [
            {
                "fromStatus": row.from_status,
                "toStatus": row.to_status,
                "actor": row.actor,
                "reason": row.reason,
                "changedAt": row.changed_at.isoformat(),
            }
            for row in alert.transitions
        ],
    }


def _serialize_outbox_event(item: Any) -> dict[str, Any]:
    return {
        "eventId": item.event_id,
        "channel": item.channel,
        "scopeId": item.scope_id,
        "jobId": item.job_id,
        "traceId": item.trace_id,
        "alertId": item.alert_id,
        "status": item.status,
        "payload": item.payload,
        "deliveryStatus": item.delivery_status,
        "errorMessage": item.error_message,
        "createdAt": item.created_at.isoformat(),
        "updatedAt": item.updated_at.isoformat(),
    }


def _serialize_dispatch_receipt(item: Any) -> dict[str, Any]:
    return {
        "dispatchType": item.dispatch_type,
        "jobId": item.job_id,
        "scopeId": item.scope_id,
        "sessionId": item.session_id,
        "traceId": item.trace_id,
        "idempotencyKey": item.idempotency_key,
        "rubricVersion": item.rubric_version,
        "judgePolicyVersion": item.judge_policy_version,
        "topicDomain": item.topic_domain,
        "retrievalProfile": item.retrieval_profile,
        "phaseNo": item.phase_no,
        "phaseStartNo": item.phase_start_no,
        "phaseEndNo": item.phase_end_no,
        "messageStartId": item.message_start_id,
        "messageEndId": item.message_end_id,
        "messageCount": item.message_count,
        "status": item.status,
        "request": item.request,
        "response": item.response,
        "createdAt": item.created_at.isoformat(),
        "updatedAt": item.updated_at.isoformat(),
    }


def _build_replay_report_payload(record: Any) -> dict[str, Any]:
    report_summary = record.report_summary if isinstance(record.report_summary, dict) else {}
    request = record.request if isinstance(record.request, dict) else {}
    response = record.response if isinstance(record.response, dict) else {}

    payload = report_summary.get("payload")
    if not isinstance(payload, dict):
        payload = {}
    response_audit_alert = response.get("auditAlert")
    payload_audit_alerts = payload.get("auditAlerts")
    audit_alerts: list[dict[str, Any]] = []
    if isinstance(payload_audit_alerts, list):
        audit_alerts.extend([row for row in payload_audit_alerts if isinstance(row, dict)])
    if isinstance(response_audit_alert, dict):
        audit_alerts.append(response_audit_alert)

    stage_summaries = report_summary.get("stage_summaries") or report_summary.get("stageSummaries")
    if not isinstance(stage_summaries, list):
        stage_summaries = []

    return {
        "jobId": record.job_id,
        "traceId": record.trace_id,
        "status": record.status,
        "requestInput": {
            "job": request.get("job") or {},
            "session": request.get("session") or {},
            "topic": request.get("topic") or {},
            "messages": request.get("messages") or [],
            "messageWindowSize": request.get("message_window_size") or request.get("messageWindowSize"),
            "rubricVersion": request.get("rubric_version") or request.get("rubricVersion"),
            "judgePolicyVersion": request.get("judge_policy_version") or request.get("judgePolicyVersion"),
            "retrievalProfile": request.get("retrieval_profile") or request.get("retrievalProfile"),
        },
        "pipeline": {
            "agentPipeline": payload.get("agentPipeline"),
            "stageSummaries": stage_summaries,
            "winnerFirst": report_summary.get("winner_first") or report_summary.get("winnerFirst"),
            "winnerSecond": report_summary.get("winner_second") or report_summary.get("winnerSecond"),
            "finalWinner": report_summary.get("winner"),
            "needsDrawVote": report_summary.get("needs_draw_vote") or report_summary.get("needsDrawVote"),
            "rationale": report_summary.get("rationale"),
            "proSummary": report_summary.get("pro_summary") or report_summary.get("proSummary"),
            "conSummary": report_summary.get("con_summary") or report_summary.get("conSummary"),
        },
        "judgeAudit": payload.get("judgeAudit"),
        "auditAlerts": audit_alerts,
        "callbackResult": {
            "callbackStatus": record.callback_status,
            "callbackError": record.callback_error,
            "response": response,
        },
        "replays": [
            {
                "replayedAt": item.replayed_at.isoformat(),
                "winner": item.winner,
                "needsDrawVote": item.needs_draw_vote,
                "provider": item.provider,
            }
            for item in record.replays
        ],
    }


def _build_replay_report_summary(record: Any) -> dict[str, Any]:
    payload = _build_replay_report_payload(record)
    callback_result = payload.get("callbackResult")
    response = callback_result.get("response") if isinstance(callback_result, dict) else {}
    if not isinstance(response, dict):
        response = {}
    pipeline = payload.get("pipeline")
    if not isinstance(pipeline, dict):
        pipeline = {}
    audit_alerts = payload.get("auditAlerts")
    if not isinstance(audit_alerts, list):
        audit_alerts = []
    return {
        "jobId": payload.get("jobId"),
        "traceId": payload.get("traceId"),
        "status": payload.get("status"),
        "createdAt": record.created_at.isoformat(),
        "updatedAt": record.updated_at.isoformat(),
        "winner": pipeline.get("finalWinner"),
        "needsDrawVote": pipeline.get("needsDrawVote"),
        "provider": response.get("provider"),
        "errorCode": response.get("errorCode"),
        "callbackStatus": callback_result.get("callbackStatus") if isinstance(callback_result, dict) else None,
        "callbackError": callback_result.get("callbackError") if isinstance(callback_result, dict) else None,
        "auditAlertCount": len([row for row in audit_alerts if isinstance(row, dict)]),
        "replayCount": len(payload.get("replays") or []),
    }


def _normalize_query_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _resolve_idempotency_or_raise(
    *,
    runtime: AppRuntime,
    key: str,
    job_id: int,
    conflict_detail: str,
) -> dict[str, Any] | None:
    existed = runtime.trace_store.get_idempotency(key)
    if existed and existed.job_id != job_id:
        raise HTTPException(status_code=409, detail=conflict_detail)
    if existed and existed.response:
        replayed = dict(existed.response)
        replayed["idempotentReplay"] = True
        return replayed
    if existed:
        raise HTTPException(status_code=409, detail=conflict_detail)
    runtime.trace_store.set_idempotency_pending(
        key=key,
        job_id=job_id,
        ttl_secs=runtime.settings.idempotency_ttl_secs,
    )
    return None


def _validate_phase_dispatch_request(request: PhaseDispatchRequest) -> None:
    if request.message_count <= 0:
        raise HTTPException(status_code=422, detail="invalid_message_count")
    if request.message_end_id < request.message_start_id:
        raise HTTPException(status_code=422, detail="invalid_message_range")
    if request.message_count != len(request.messages):
        raise HTTPException(status_code=422, detail="message_count_mismatch")
    for message in request.messages:
        if message.message_id < request.message_start_id or message.message_id > request.message_end_id:
            raise HTTPException(status_code=422, detail="message_id_out_of_range")


def _validate_final_dispatch_request(request: FinalDispatchRequest) -> None:
    if request.phase_start_no <= 0 or request.phase_end_no <= 0:
        raise HTTPException(status_code=422, detail="invalid_phase_no")
    if request.phase_start_no > request.phase_end_no:
        raise HTTPException(status_code=422, detail="invalid_phase_range")


def _clamp_score(value: float) -> float:
    return max(0.0, min(100.0, value))


def _build_side_summary(
    *,
    request: PhaseDispatchRequest,
    side: str,
) -> dict[str, Any]:
    side_messages = [msg for msg in request.messages if msg.side == side]
    if side_messages:
        message_ids = [msg.message_id for msg in side_messages]
        lines = [f"[{msg.message_id}] {msg.content}" for msg in side_messages]
        text = "\n".join(lines)
    else:
        fallback_messages = list(request.messages[:3])
        message_ids = [msg.message_id for msg in fallback_messages]
        lines = [f"[{msg.message_id}] {msg.content}" for msg in fallback_messages]
        text = "当前窗口该方暂无发言，引用窗口上下文保留可追溯性。\n" + "\n".join(lines)
    return {
        "text": text[:4000],
        "messageIds": message_ids,
    }


def _build_phase_report_payload(request: PhaseDispatchRequest) -> dict[str, Any]:
    total = max(1, request.message_count)
    pro_count = len([msg for msg in request.messages if msg.side == "pro"])
    con_count = len([msg for msg in request.messages if msg.side == "con"])
    balance = (pro_count - con_count) / float(total)
    agent1_pro = round(_clamp_score(50.0 + balance * 8.0), 2)
    agent1_con = round(_clamp_score(50.0 - balance * 8.0), 2)
    agent2_pro = round(_clamp_score(50.0 + balance * 12.0), 2)
    agent2_con = round(_clamp_score(50.0 - balance * 12.0), 2)
    w1 = 0.35
    w2 = 0.65
    agent3_pro = round(_clamp_score(agent1_pro * w1 + agent2_pro * w2), 2)
    agent3_con = round(_clamp_score(agent1_con * w1 + agent2_con * w2), 2)

    return {
        "sessionId": request.session_id,
        "phaseNo": request.phase_no,
        "messageStartId": request.message_start_id,
        "messageEndId": request.message_end_id,
        "messageCount": request.message_count,
        "proSummaryGrounded": _build_side_summary(request=request, side="pro"),
        "conSummaryGrounded": _build_side_summary(request=request, side="con"),
        "proRetrievalBundle": {"queries": [], "items": []},
        "conRetrievalBundle": {"queries": [], "items": []},
        "agent1Score": {
            "pro": agent1_pro,
            "con": agent1_con,
            "dimensions": {},
            "rationale": "v3 placeholder scorer (agent1) based on side message balance.",
        },
        "agent2Score": {
            "pro": agent2_pro,
            "con": agent2_con,
            "hitItems": [],
            "missItems": [],
            "rationale": "v3 placeholder scorer (agent2) based on side message balance.",
        },
        "agent3WeightedScore": {
            "pro": agent3_pro,
            "con": agent3_con,
            "w1": w1,
            "w2": w2,
        },
        "promptHashes": {},
        "tokenUsage": {"total": 0},
        "latencyMs": {"total": 0},
        "errorCodes": ["v3_placeholder_pipeline"],
        "degradationLevel": 3,
        "judgeTrace": {
            "traceId": request.trace_id,
            "pipelineVersion": "v3-placeholder",
            "idempotencyKey": request.idempotency_key,
        },
    }


def _build_final_report_payload(request: FinalDispatchRequest) -> dict[str, Any]:
    return {
        "sessionId": request.session_id,
        "winner": "draw",
        "proScore": 50.0,
        "conScore": 50.0,
        "dimensionScores": {
            "logic": 50.0,
            "evidence": 50.0,
            "rebuttal": 50.0,
            "clarity": 50.0,
        },
        "finalRationale": (
            "v3 placeholder final report generated after dispatch acceptance; "
            "full final aggregation pipeline pending implementation."
        ),
        "verdictEvidenceRefs": [],
        "phaseRollupSummary": [
            {
                "phaseStartNo": request.phase_start_no,
                "phaseEndNo": request.phase_end_no,
            }
        ],
        "retrievalSnapshotRollup": [],
        "winnerFirst": None,
        "winnerSecond": None,
        "rejudgeTriggered": False,
        "needsDrawVote": True,
        "judgeTrace": {
            "traceId": request.trace_id,
            "pipelineVersion": "v3-placeholder",
            "idempotencyKey": request.idempotency_key,
        },
        "auditAlerts": [],
        "errorCodes": ["v3_placeholder_pipeline"],
        "degradationLevel": 3,
    }


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


def create_app(runtime: AppRuntime) -> FastAPI:
    app = FastAPI(title="AI Judge Service", version="0.2.0")

    @app.get("/healthz")
    async def healthz() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/internal/judge/dispatch")
    async def dispatch_judge_job(
        request: JudgeDispatchRequest,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict:
        require_internal_key(runtime.settings, x_ai_internal_key)
        validate_blinded_dispatch_request(request)

        if not request.trace_id:
            request = request.model_copy(
                update={"trace_id": f"trace-{request.job.job_id}-{uuid4().hex[:12]}"}
            )

        runtime.trace_store.register_start(
            job_id=request.job.job_id,
            trace_id=request.trace_id,
            request=request.model_dump(mode="json"),
        )
        if request.idempotency_key:
            existed = runtime.trace_store.get_idempotency(request.idempotency_key)
            if existed and existed.job_id != request.job.job_id:
                raise HTTPException(
                    status_code=409,
                    detail="idempotency_conflict:judge_dispatch",
                )
            if existed and existed.response:
                replayed = dict(existed.response)
                replayed["idempotentReplay"] = True
                return replayed
            if existed:
                raise HTTPException(
                    status_code=409,
                    detail="idempotency_conflict:judge_dispatch",
                )
            runtime.trace_store.set_idempotency_pending(
                key=request.idempotency_key,
                job_id=request.job.job_id,
                ttl_secs=runtime.settings.idempotency_ttl_secs,
            )

        callback_status = "not_called"
        callback_error = ""
        report_payload: dict[str, Any] | None = None

        async def callback_report_with_trace(job_id: int, payload: dict[str, Any]) -> None:
            nonlocal callback_status, callback_error, report_payload
            report_payload = payload
            try:
                await runtime.callback_report_fn(job_id, payload)
                callback_status = "reported"
            except Exception as err:
                callback_status = "report_failed"
                callback_error = str(err)
                raise

        async def callback_failed_with_trace(job_id: int, error_message: str) -> None:
            nonlocal callback_status, callback_error
            callback_status = "marked_failed"
            callback_error = error_message
            await runtime.callback_failed_fn(job_id, error_message)

        try:
            response = await process_dispatch_request(
                request=request,
                runtime_cfg=runtime.dispatch_runtime_cfg,
                build_report_by_runtime=runtime.build_report_by_runtime_adapter,
                callback_report=callback_report_with_trace,
                callback_failed=callback_failed_with_trace,
                sleep_fn=runtime.sleep_fn,
            )
        except Exception as err:
            if request.idempotency_key:
                runtime.trace_store.clear_idempotency(request.idempotency_key)
            runtime.trace_store.register_failure(
                job_id=request.job.job_id,
                response={
                    "accepted": False,
                    "jobId": request.job.job_id,
                    "status": "error",
                },
                callback_status=callback_status,
                callback_error=callback_error or str(err),
            )
            raise

        if response.get("status") == "marked_failed":
            if request.idempotency_key:
                runtime.trace_store.clear_idempotency(request.idempotency_key)
            runtime.trace_store.register_failure(
                job_id=request.job.job_id,
                response=response,
                callback_status=callback_status,
                callback_error=callback_error or "marked_failed",
            )
        else:
            if request.idempotency_key:
                runtime.trace_store.set_idempotency_success(
                    key=request.idempotency_key,
                    job_id=request.job.job_id,
                    response=response,
                    ttl_secs=runtime.settings.idempotency_ttl_secs,
                )
            topic_memory_audit: dict[str, Any] | None = None
            report_summary = dict(report_payload or {})
            if runtime.settings.topic_memory_enabled:
                topic_memory_audit = _calc_topic_memory_quality_audit(
                    settings=runtime.settings,
                    request=request,
                    response=response,
                    report_payload=report_payload,
                )
                report_summary["topicMemoryAudit"] = topic_memory_audit
            runtime.trace_store.register_success(
                job_id=request.job.job_id,
                response=response,
                callback_status=callback_status,
                report_summary=report_summary,
            )
            if runtime.settings.topic_memory_enabled and topic_memory_audit and topic_memory_audit["accepted"]:
                runtime.trace_store.save_topic_memory(
                    job_id=request.job.job_id,
                    trace_id=request.trace_id or "",
                    topic_domain=getattr(request, "topic_domain", "default"),
                    rubric_version=request.rubric_version,
                    winner=response.get("winner"),
                    rationale=str((report_payload or {}).get("rationale") or ""),
                    evidence_refs=_extract_report_evidence_refs(report_payload),
                    provider=response.get("provider"),
                    audit=topic_memory_audit,
                )
        runtime_alerts = _extract_runtime_audit_alerts(
            response=response,
            report_payload=report_payload,
        )
        persisted_alert_ids: list[str] = []
        for row in runtime_alerts:
            normalized = _normalize_runtime_audit_alert(row)
            alert = runtime.trace_store.upsert_audit_alert(
                job_id=request.job.job_id,
                scope_id=request.job.scope_id,
                trace_id=request.trace_id or "",
                alert_type=normalized["alertType"],
                severity=normalized["severity"],
                title=normalized["title"],
                message=normalized["message"],
                details=normalized["details"],
            )
            persisted_alert_ids.append(alert.alert_id)
        if persisted_alert_ids:
            response = dict(response)
            response["auditAlertIds"] = persisted_alert_ids
        return response

    @app.post("/internal/judge/v3/phase/dispatch")
    async def dispatch_judge_phase(
        request: PhaseDispatchRequest,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        _validate_phase_dispatch_request(request)

        replayed = _resolve_idempotency_or_raise(
            runtime=runtime,
            key=request.idempotency_key,
            job_id=request.job_id,
            conflict_detail="idempotency_conflict:phase_dispatch",
        )
        if replayed is not None:
            return replayed

        response = {
            "accepted": True,
            "dispatchType": "phase",
            "status": "queued",
            "jobId": request.job_id,
            "scopeId": request.scope_id,
            "sessionId": request.session_id,
            "phaseNo": request.phase_no,
            "messageCount": request.message_count,
            "traceId": request.trace_id,
        }
        request_payload = request.model_dump(mode="json")
        runtime.trace_store.save_dispatch_receipt(
            dispatch_type="phase",
            job_id=request.job_id,
            scope_id=request.scope_id,
            session_id=request.session_id,
            trace_id=request.trace_id,
            idempotency_key=request.idempotency_key,
            rubric_version=request.rubric_version,
            judge_policy_version=request.judge_policy_version,
            topic_domain=request.topic_domain,
            retrieval_profile=request.retrieval_profile,
            phase_no=request.phase_no,
            phase_start_no=None,
            phase_end_no=None,
            message_start_id=request.message_start_id,
            message_end_id=request.message_end_id,
            message_count=request.message_count,
            status="queued",
            request=request_payload,
            response=response,
        )

        phase_report_payload = _build_phase_report_payload(request)
        try:
            callback_attempts, callback_retries = await _invoke_v3_callback_with_retry(
                runtime=runtime,
                callback_fn=runtime.callback_phase_report_fn,
                job_id=request.job_id,
                payload=phase_report_payload,
            )
        except Exception as err:
            runtime.trace_store.save_dispatch_receipt(
                dispatch_type="phase",
                job_id=request.job_id,
                scope_id=request.scope_id,
                session_id=request.session_id,
                trace_id=request.trace_id,
                idempotency_key=request.idempotency_key,
                rubric_version=request.rubric_version,
                judge_policy_version=request.judge_policy_version,
                topic_domain=request.topic_domain,
                retrieval_profile=request.retrieval_profile,
                phase_no=request.phase_no,
                phase_start_no=None,
                phase_end_no=None,
                message_start_id=request.message_start_id,
                message_end_id=request.message_end_id,
                message_count=request.message_count,
                status="callback_failed",
                request=request_payload,
                response={
                    **response,
                    "status": "callback_failed",
                    "callbackStatus": "failed",
                    "callbackError": str(err),
                },
            )
            runtime.trace_store.clear_idempotency(request.idempotency_key)
            raise HTTPException(status_code=502, detail=f"phase_callback_failed: {err}") from err

        runtime.trace_store.save_dispatch_receipt(
            dispatch_type="phase",
            job_id=request.job_id,
            scope_id=request.scope_id,
            session_id=request.session_id,
            trace_id=request.trace_id,
            idempotency_key=request.idempotency_key,
            rubric_version=request.rubric_version,
            judge_policy_version=request.judge_policy_version,
            topic_domain=request.topic_domain,
            retrieval_profile=request.retrieval_profile,
            phase_no=request.phase_no,
            phase_start_no=None,
            phase_end_no=None,
            message_start_id=request.message_start_id,
            message_end_id=request.message_end_id,
            message_count=request.message_count,
            status="reported",
            request=request_payload,
            response={
                **response,
                "callbackStatus": "reported",
                "callbackAttempts": callback_attempts,
                "callbackRetries": callback_retries,
            },
        )
        runtime.trace_store.set_idempotency_success(
            key=request.idempotency_key,
            job_id=request.job_id,
            response=response,
            ttl_secs=runtime.settings.idempotency_ttl_secs,
        )
        return response

    @app.post("/internal/judge/v3/final/dispatch")
    async def dispatch_judge_final(
        request: FinalDispatchRequest,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        _validate_final_dispatch_request(request)

        replayed = _resolve_idempotency_or_raise(
            runtime=runtime,
            key=request.idempotency_key,
            job_id=request.job_id,
            conflict_detail="idempotency_conflict:final_dispatch",
        )
        if replayed is not None:
            return replayed

        response = {
            "accepted": True,
            "dispatchType": "final",
            "status": "queued",
            "jobId": request.job_id,
            "scopeId": request.scope_id,
            "sessionId": request.session_id,
            "phaseStartNo": request.phase_start_no,
            "phaseEndNo": request.phase_end_no,
            "traceId": request.trace_id,
        }
        request_payload = request.model_dump(mode="json")
        runtime.trace_store.save_dispatch_receipt(
            dispatch_type="final",
            job_id=request.job_id,
            scope_id=request.scope_id,
            session_id=request.session_id,
            trace_id=request.trace_id,
            idempotency_key=request.idempotency_key,
            rubric_version=request.rubric_version,
            judge_policy_version=request.judge_policy_version,
            topic_domain=request.topic_domain,
            retrieval_profile=None,
            phase_no=None,
            phase_start_no=request.phase_start_no,
            phase_end_no=request.phase_end_no,
            message_start_id=None,
            message_end_id=None,
            message_count=None,
            status="queued",
            request=request_payload,
            response=response,
        )

        final_report_payload = _build_final_report_payload(request)
        try:
            callback_attempts, callback_retries = await _invoke_v3_callback_with_retry(
                runtime=runtime,
                callback_fn=runtime.callback_final_report_fn,
                job_id=request.job_id,
                payload=final_report_payload,
            )
        except Exception as err:
            runtime.trace_store.save_dispatch_receipt(
                dispatch_type="final",
                job_id=request.job_id,
                scope_id=request.scope_id,
                session_id=request.session_id,
                trace_id=request.trace_id,
                idempotency_key=request.idempotency_key,
                rubric_version=request.rubric_version,
                judge_policy_version=request.judge_policy_version,
                topic_domain=request.topic_domain,
                retrieval_profile=None,
                phase_no=None,
                phase_start_no=request.phase_start_no,
                phase_end_no=request.phase_end_no,
                message_start_id=None,
                message_end_id=None,
                message_count=None,
                status="callback_failed",
                request=request_payload,
                response={
                    **response,
                    "status": "callback_failed",
                    "callbackStatus": "failed",
                    "callbackError": str(err),
                },
            )
            runtime.trace_store.clear_idempotency(request.idempotency_key)
            raise HTTPException(status_code=502, detail=f"final_callback_failed: {err}") from err

        runtime.trace_store.save_dispatch_receipt(
            dispatch_type="final",
            job_id=request.job_id,
            scope_id=request.scope_id,
            session_id=request.session_id,
            trace_id=request.trace_id,
            idempotency_key=request.idempotency_key,
            rubric_version=request.rubric_version,
            judge_policy_version=request.judge_policy_version,
            topic_domain=request.topic_domain,
            retrieval_profile=None,
            phase_no=None,
            phase_start_no=request.phase_start_no,
            phase_end_no=request.phase_end_no,
            message_start_id=None,
            message_end_id=None,
            message_count=None,
            status="reported",
            request=request_payload,
            response={
                **response,
                "callbackStatus": "reported",
                "callbackAttempts": callback_attempts,
                "callbackRetries": callback_retries,
            },
        )
        runtime.trace_store.set_idempotency_success(
            key=request.idempotency_key,
            job_id=request.job_id,
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
        item = runtime.trace_store.get_dispatch_receipt(
            dispatch_type="phase",
            job_id=job_id,
        )
        if item is None:
            raise HTTPException(status_code=404, detail="phase_dispatch_receipt_not_found")
        return _serialize_dispatch_receipt(item)

    @app.get("/internal/judge/v3/final/jobs/{job_id}/receipt")
    async def get_final_dispatch_receipt(
        job_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        item = runtime.trace_store.get_dispatch_receipt(
            dispatch_type="final",
            job_id=job_id,
        )
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
            "replays": [
                {
                    "replayedAt": item.replayed_at.isoformat(),
                    "winner": item.winner,
                    "needsDrawVote": item.needs_draw_vote,
                    "provider": item.provider,
                }
                for item in record.replays
            ],
        }

    @app.post("/internal/judge/jobs/{job_id}/replay")
    async def replay_judge_job(
        job_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        record = runtime.trace_store.get_trace(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="judge_trace_not_found")
        request = JudgeDispatchRequest.model_validate(record.request)
        effective_style_mode, style_mode_source = resolve_effective_style_mode(
            request.job.style_mode,
            runtime.dispatch_runtime_cfg.judge_style_mode,
        )
        try:
            report = await runtime.build_report_by_runtime_adapter(
                request,
                effective_style_mode,
                style_mode_source,
            )
        except Exception as err:
            raise HTTPException(status_code=502, detail=f"replay_failed: {err}") from err
        runtime.trace_store.mark_replay(
            job_id=job_id,
            winner=report.winner,
            needs_draw_vote=report.needs_draw_vote,
            provider=report.payload.get("provider"),
        )
        return {
            "ok": True,
            "jobId": job_id,
            "winner": report.winner,
            "needsDrawVote": report.needs_draw_vote,
            "provider": report.payload.get("provider"),
            "judgeTrace": report.payload.get("judgeTrace"),
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
                "createdAfter": normalized_created_after.isoformat() if normalized_created_after else None,
                "createdBefore": normalized_created_before.isoformat() if normalized_created_before else None,
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
        items = runtime.trace_store.list_audit_alerts(
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
        return {
            "ok": True,
            "jobId": job_id,
            "alertId": alert_id,
            "status": row.status,
            "item": _serialize_alert_item(row),
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
