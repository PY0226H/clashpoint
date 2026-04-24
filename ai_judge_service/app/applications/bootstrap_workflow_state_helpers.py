from __future__ import annotations

from typing import Any, Awaitable, Callable

from .judge_command_routes import build_error_contract as build_error_contract_v3


async def workflow_register_and_mark_blinded_for_runtime(
    *,
    judge_core: Any,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    job: Any,
    event_payload: dict[str, Any] | None = None,
) -> None:
    await ensure_workflow_schema_ready()
    await judge_core.register_blinded(
        job=job,
        event_payload=event_payload,
    )


async def workflow_register_and_mark_case_built_for_runtime(
    *,
    judge_core: Any,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    job: Any,
    event_payload: dict[str, Any] | None = None,
) -> Any:
    await ensure_workflow_schema_ready()
    return await judge_core.register_case_built(
        job=job,
        event_payload=event_payload,
    )


async def workflow_mark_completed_for_runtime(
    *,
    judge_core: Any,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    job_id: int,
    event_payload: dict[str, Any] | None = None,
) -> None:
    await ensure_workflow_schema_ready()
    payload = dict(event_payload or {})
    dispatch_type = str(payload.get("dispatchType") or "").strip().lower() or "unknown"
    completed_stage = str(payload.get("judgeCoreStage") or "").strip().lower()
    if not completed_stage:
        completed_stage = "review_approved" if payload.get("reviewDecision") else "reported"
    await judge_core.mark_reported(
        job_id=job_id,
        dispatch_type=dispatch_type,
        review_required=False,
        completed_stage=completed_stage,
        event_payload=payload,
    )


async def workflow_mark_review_required_for_runtime(
    *,
    judge_core: Any,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    job_id: int,
    event_payload: dict[str, Any] | None = None,
) -> None:
    await ensure_workflow_schema_ready()
    payload = dict(event_payload or {})
    dispatch_type = str(payload.get("dispatchType") or "").strip().lower() or "unknown"
    await judge_core.mark_reported(
        job_id=job_id,
        dispatch_type=dispatch_type,
        review_required=True,
        event_payload=payload,
    )


async def workflow_mark_failed_for_runtime(
    *,
    judge_core: Any,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    job_id: int,
    error_code: str,
    error_message: str,
    event_payload: dict[str, Any] | None = None,
) -> None:
    await ensure_workflow_schema_ready()
    payload = dict(event_payload or {})
    dispatch_type = str(payload.get("dispatchType") or "").strip().lower() or "unknown"
    failed_stage = str(payload.get("judgeCoreStage") or "").strip().lower()
    if not failed_stage:
        failed_stage = "review_rejected" if error_code == "review_rejected" else "blocked_failed"
    payload.setdefault("errorCode", error_code)
    payload.setdefault("errorMessage", error_message)
    payload["error"] = build_error_contract_v3(
        error_code=error_code,
        error_message=error_message,
        dispatch_type=dispatch_type,
        trace_id=str(payload.get("traceId") or ""),
        retryable=False,
        category="workflow_failed",
        details={
            "judgeCoreStage": failed_stage,
            "callbackStatus": payload.get("callbackStatus"),
        },
    )
    await judge_core.mark_failed(
        job_id=job_id,
        dispatch_type=dispatch_type,
        error_code=error_code,
        error_message=error_message,
        stage=failed_stage,
        event_payload=payload,
    )


async def workflow_mark_replay_for_runtime(
    *,
    judge_core: Any,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    job_id: int,
    dispatch_type: str,
    event_payload: dict[str, Any] | None = None,
) -> None:
    await ensure_workflow_schema_ready()
    payload = dict(event_payload or {})
    try:
        await judge_core.mark_replay(
            job_id=job_id,
            dispatch_type=dispatch_type,
            event_payload=payload,
        )
    except LookupError:
        return
