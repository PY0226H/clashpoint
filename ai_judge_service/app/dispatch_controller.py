from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol

from fastapi import HTTPException

from .models import JudgeDispatchRequest
from .runtime_errors import (
    ERROR_CONSISTENCY_CONFLICT,
    ERROR_JUDGE_TIMEOUT,
    ERROR_MODEL_OVERLOAD,
    ERROR_RAG_UNAVAILABLE,
    extract_runtime_error_code,
)
from .scoring import resolve_effective_style_mode


class JudgeReportProtocol(Protocol):
    winner: str
    needs_draw_vote: bool
    payload: dict[str, Any]

    def model_dump(self, *, mode: str = "python") -> dict[str, Any]:
        ...


BuildReportByRuntimeFn = Callable[[JudgeDispatchRequest, str, str], Awaitable[JudgeReportProtocol]]
CallbackReportFn = Callable[[int, dict[str, Any]], Awaitable[None]]
CallbackFailedFn = Callable[[int, str], Awaitable[None]]
SleepFn = Callable[[float], Awaitable[None]]
RETRYABLE_RUNTIME_ERROR_CODES = {
    ERROR_JUDGE_TIMEOUT,
    ERROR_MODEL_OVERLOAD,
    ERROR_RAG_UNAVAILABLE,
}


@dataclass(frozen=True)
class DispatchRuntimeConfig:
    process_delay_ms: int
    judge_style_mode: str
    runtime_retry_max_attempts: int = 2
    retry_backoff_ms: int = 200
    compliance_block_enabled: bool = True


def _extract_compliance_snapshot(report: JudgeReportProtocol) -> dict[str, Any] | None:
    payload = report.payload if isinstance(report.payload, dict) else {}
    pipeline = payload.get("agentPipeline")
    if not isinstance(pipeline, dict):
        return None
    compliance = pipeline.get("compliance")
    if not isinstance(compliance, dict):
        return None
    status = str(compliance.get("status") or "unknown").strip().lower()
    raw_violations = compliance.get("violations")
    violations: list[str] = []
    if isinstance(raw_violations, list):
        for item in raw_violations:
            text = str(item or "").strip()
            if not text:
                continue
            violations.append(text)
    return {
        "status": status,
        "violations": violations,
    }


def _build_compliance_alert(compliance: dict[str, Any]) -> dict[str, Any] | None:
    status = str(compliance.get("status") or "unknown").strip().lower()
    violations = [
        str(item).strip()
        for item in compliance.get("violations", [])
        if str(item).strip()
    ]
    if status == "ok" and not violations:
        return None
    if not violations and status not in {"warn", "blocked", "error"}:
        return None
    return {
        "type": "compliance_violation",
        "status": status,
        "severity": "high" if status in {"warn", "blocked", "error"} else "medium",
        "violations": violations,
        "blockTriggered": bool(violations) and status != "ok",
    }


async def process_dispatch_request(
    *,
    request: JudgeDispatchRequest,
    runtime_cfg: DispatchRuntimeConfig,
    build_report_by_runtime: BuildReportByRuntimeFn,
    callback_report: CallbackReportFn,
    callback_failed: CallbackFailedFn,
    sleep_fn: SleepFn = asyncio.sleep,
) -> dict[str, Any]:
    if runtime_cfg.process_delay_ms > 0:
        await sleep_fn(runtime_cfg.process_delay_ms / 1000.0)

    if not request.messages:
        await callback_failed(request.job.job_id, "empty debate messages, cannot judge")
        return {
            "accepted": True,
            "jobId": request.job.job_id,
            "status": "marked_failed",
            "complianceBlocked": False,
        }

    effective_style_mode, style_mode_source = resolve_effective_style_mode(
        request.job.style_mode,
        runtime_cfg.judge_style_mode,
    )
    max_attempts = max(1, int(runtime_cfg.runtime_retry_max_attempts))
    retry_backoff_ms = max(0, int(runtime_cfg.retry_backoff_ms))
    attempt = 0
    report = None
    while attempt < max_attempts:
        attempt += 1
        try:
            report = await build_report_by_runtime(
                request,
                effective_style_mode,
                style_mode_source,
            )
            break
        except Exception as err:
            error_code = extract_runtime_error_code(err)
            should_retry = (
                error_code in RETRYABLE_RUNTIME_ERROR_CODES
                and attempt < max_attempts
            )
            if should_retry:
                delay_secs = (retry_backoff_ms * attempt) / 1000.0
                if delay_secs > 0:
                    await sleep_fn(delay_secs)
                continue
            error_message = f"judge runtime failed ({error_code}): {err}"
            try:
                await callback_failed(request.job.job_id, error_message)
            except Exception as callback_err:  # pragma: no cover
                raise HTTPException(
                    status_code=502,
                    detail=f"runtime failed and callback_failed failed: {callback_err}",
                ) from callback_err
            return {
                "accepted": True,
                "jobId": request.job.job_id,
                "status": "marked_failed",
                "errorCode": error_code or ERROR_MODEL_OVERLOAD,
                "attemptCount": attempt,
                "retryCount": max(0, attempt - 1),
                "complianceBlocked": False,
            }

    if report is None:  # pragma: no cover
        raise HTTPException(status_code=502, detail="judge runtime unavailable")

    compliance = _extract_compliance_snapshot(report)
    compliance_alert = _build_compliance_alert(compliance or {})
    if compliance_alert:
        payload = report.payload if isinstance(report.payload, dict) else {}
        existing_alerts = payload.get("auditAlerts")
        alerts: list[dict[str, Any]]
        if isinstance(existing_alerts, list):
            alerts = [row for row in existing_alerts if isinstance(row, dict)]
        else:
            alerts = []
        alerts.append(compliance_alert)
        payload["auditAlerts"] = alerts
        if runtime_cfg.compliance_block_enabled and compliance_alert.get("blockTriggered"):
            violation_text = ",".join(compliance_alert.get("violations") or [])
            error_message = (
                "judge compliance blocked "
                f"({ERROR_CONSISTENCY_CONFLICT}): status={compliance_alert.get('status')} "
                f"violations={violation_text or 'unknown'}"
            )
            try:
                await callback_failed(request.job.job_id, error_message)
            except Exception as callback_err:  # pragma: no cover
                raise HTTPException(
                    status_code=502,
                    detail=f"compliance blocked and callback_failed failed: {callback_err}",
                ) from callback_err
            return {
                "accepted": True,
                "jobId": request.job.job_id,
                "status": "marked_failed",
                "errorCode": ERROR_CONSISTENCY_CONFLICT,
                "attemptCount": attempt,
                "retryCount": max(0, attempt - 1),
                "complianceBlocked": True,
                "auditAlert": compliance_alert,
            }

    try:
        await callback_report(request.job.job_id, report.model_dump(mode="json"))
    except Exception as err:  # pragma: no cover
        raise HTTPException(status_code=502, detail=f"callback report failed: {err}") from err

    return {
        "accepted": True,
        "jobId": request.job.job_id,
        "winner": report.winner,
        "needsDrawVote": report.needs_draw_vote,
        "provider": report.payload.get("provider"),
        "attemptCount": attempt,
        "retryCount": max(0, attempt - 1),
        "complianceBlocked": False,
    }
