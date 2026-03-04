from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import uuid4
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Header, HTTPException

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
from .trace_store import TraceStore
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
    trace_store: TraceStore


def require_internal_key(settings: Settings, header_value: str | None) -> None:
    if not header_value:
        raise HTTPException(status_code=401, detail="missing x-ai-internal-key")
    if header_value.strip() != settings.ai_internal_key:
        raise HTTPException(status_code=401, detail="invalid x-ai-internal-key")


def build_report_by_runtime_adapter(
    *,
    settings: Settings,
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
            build_report_by_runtime_fn=build_report_by_runtime_fn,
        ),
        callback_report_fn=callback_report_fn,
        callback_failed_fn=callback_failed_fn,
        sleep_fn=sleep_fn,
        trace_store=TraceStore(ttl_secs=settings.trace_ttl_secs),
    )


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

        if request.idempotency_key:
            runtime.trace_store.set_idempotency_success(
                key=request.idempotency_key,
                job_id=request.job.job_id,
                response=response,
                ttl_secs=runtime.settings.idempotency_ttl_secs,
            )

        if response.get("status") == "marked_failed":
            runtime.trace_store.register_failure(
                job_id=request.job.job_id,
                response=response,
                callback_status=callback_status,
                callback_error=callback_error or "marked_failed",
            )
        else:
            runtime.trace_store.register_success(
                job_id=request.job.job_id,
                response=response,
                callback_status=callback_status,
                report_summary=report_payload or {},
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
