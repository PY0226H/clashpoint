from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from ..models import FinalDispatchRequest, PhaseDispatchRequest
from ..runtime_types import CallbackReportFn

CALLBACK_STATUS_REPORTED = "reported"
CALLBACK_STATUS_FAILED_REPORTED = "failed_reported"
CALLBACK_STATUS_FAILED_CALLBACK_FAILED = "failed_callback_failed"

InvokeCallbackWithRetryFn = Callable[
    [CallbackReportFn, int, dict[str, Any]],
    Awaitable[tuple[int, int]],
]
BuildFailedPayloadFn = Callable[[str], dict[str, Any]]


@dataclass(frozen=True)
class CallbackDeliveryOutcome:
    callback_status: str
    report_error: str | None = None
    callback_attempts: int | None = None
    callback_retries: int | None = None
    failed_payload: dict[str, Any] | None = None
    failed_attempts: int | None = None
    failed_retries: int | None = None
    failed_error: str | None = None


def build_phase_dispatch_accepted_response(
    *,
    request: PhaseDispatchRequest,
) -> dict[str, Any]:
    return {
        "accepted": True,
        "dispatchType": "phase",
        "status": "queued",
        "caseId": request.case_id,
        "scopeId": request.scope_id,
        "sessionId": request.session_id,
        "phaseNo": request.phase_no,
        "messageCount": request.message_count,
        "traceId": request.trace_id,
    }


def build_final_dispatch_accepted_response(
    *,
    request: FinalDispatchRequest,
) -> dict[str, Any]:
    return {
        "accepted": True,
        "dispatchType": "final",
        "status": "queued",
        "caseId": request.case_id,
        "scopeId": request.scope_id,
        "sessionId": request.session_id,
        "phaseStartNo": request.phase_start_no,
        "phaseEndNo": request.phase_end_no,
        "traceId": request.trace_id,
    }


def build_phase_workflow_register_payload(
    *,
    request: PhaseDispatchRequest,
    policy_version: str,
    prompt_version: str,
    toolset_version: str,
) -> dict[str, Any]:
    return {
        "dispatchType": "phase",
        "scopeId": request.scope_id,
        "sessionId": request.session_id,
        "phaseNo": request.phase_no,
        "messageCount": request.message_count,
        "traceId": request.trace_id,
        "policyVersion": policy_version,
        "promptVersion": prompt_version,
        "toolsetVersion": toolset_version,
    }


def build_final_workflow_register_payload(
    *,
    request: FinalDispatchRequest,
    policy_version: str,
    prompt_version: str,
    toolset_version: str,
) -> dict[str, Any]:
    return {
        "dispatchType": "final",
        "scopeId": request.scope_id,
        "sessionId": request.session_id,
        "phaseStartNo": request.phase_start_no,
        "phaseEndNo": request.phase_end_no,
        "traceId": request.trace_id,
        "policyVersion": policy_version,
        "promptVersion": prompt_version,
        "toolsetVersion": toolset_version,
    }


def build_phase_workflow_reported_payload(
    *,
    request: PhaseDispatchRequest,
    callback_status: str = CALLBACK_STATUS_REPORTED,
) -> dict[str, Any]:
    return {
        "dispatchType": "phase",
        "phaseNo": request.phase_no,
        "callbackStatus": callback_status,
    }


def build_final_workflow_reported_payload(
    *,
    request: FinalDispatchRequest,
    report_payload: dict[str, Any] | None,
    callback_status: str = CALLBACK_STATUS_REPORTED,
) -> dict[str, Any]:
    payload = report_payload if isinstance(report_payload, dict) else {}
    return {
        "dispatchType": "final",
        "phaseStartNo": request.phase_start_no,
        "phaseEndNo": request.phase_end_no,
        "callbackStatus": callback_status,
        "winner": payload.get("winner"),
        "reviewRequired": bool(payload.get("reviewRequired")),
        "errorCodes": (
            payload.get("errorCodes") if isinstance(payload.get("errorCodes"), list) else []
        ),
    }


async def deliver_report_callback_with_failed_fallback(
    *,
    job_id: int,
    report_payload: dict[str, Any],
    report_callback_fn: CallbackReportFn,
    failed_callback_fn: CallbackReportFn,
    invoke_with_retry: InvokeCallbackWithRetryFn,
    build_failed_payload: BuildFailedPayloadFn,
) -> CallbackDeliveryOutcome:
    try:
        callback_attempts, callback_retries = await invoke_with_retry(
            report_callback_fn,
            job_id,
            report_payload,
        )
        return CallbackDeliveryOutcome(
            callback_status=CALLBACK_STATUS_REPORTED,
            callback_attempts=callback_attempts,
            callback_retries=callback_retries,
        )
    except Exception as report_err:
        report_error = str(report_err)
        failed_payload = build_failed_payload(report_error)
        try:
            failed_attempts, failed_retries = await invoke_with_retry(
                failed_callback_fn,
                job_id,
                failed_payload,
            )
        except Exception as failed_err:
            return CallbackDeliveryOutcome(
                callback_status=CALLBACK_STATUS_FAILED_CALLBACK_FAILED,
                report_error=report_error,
                failed_payload=failed_payload,
                failed_error=str(failed_err),
            )
        return CallbackDeliveryOutcome(
            callback_status=CALLBACK_STATUS_FAILED_REPORTED,
            report_error=report_error,
            failed_payload=failed_payload,
            failed_attempts=failed_attempts,
            failed_retries=failed_retries,
        )
