from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Header, HTTPException, Query

from .callback_client import callback_failed, callback_report
from .compliance_guard import validate_blinded_dispatch_request
from .dispatch_controller import (
    BuildReportByRuntimeFn,
    CallbackFailedFn,
    CallbackReportFn,
    DispatchRuntimeConfig,
    SleepFn,
    process_dispatch_request,
)
from .models import JudgeDispatchRequest
from .scoring import resolve_effective_style_mode
from .runtime_orchestrator import build_report_by_runtime
from .settings import (
    Settings,
    build_callback_client_config,
    build_dispatch_runtime_config,
    load_settings,
)
from .trace_store import TraceQuery, TraceStoreProtocol, build_trace_store_from_settings
from .wiring import build_dispatch_callbacks

BuildReportByRuntimeImpl = Callable[..., Awaitable[Any]]
LoadSettingsFn = Callable[[], Settings]


@dataclass(frozen=True)
class AppRuntime:
    settings: Settings
    dispatch_runtime_cfg: DispatchRuntimeConfig
    build_report_by_runtime_adapter: BuildReportByRuntimeFn
    callback_report_fn: CallbackReportFn
    callback_failed_fn: CallbackFailedFn
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
    sleep_fn: SleepFn = asyncio.sleep,
) -> AppRuntime:
    trace_store = build_trace_store_from_settings(settings=settings)
    callback_cfg = build_callback_client_config(settings)
    callback_report_fn, callback_failed_fn = build_dispatch_callbacks(
        cfg=callback_cfg,
        callback_report_impl=callback_report_impl,
        callback_failed_impl=callback_failed_impl,
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
        return response

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
