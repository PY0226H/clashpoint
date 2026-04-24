from __future__ import annotations

from typing import Any, Callable, cast

from .judge_command_routes import (
    attach_policy_trace_snapshot as attach_policy_trace_snapshot_v3,
)
from .judge_command_routes import (
    invoke_callback_with_retry as invoke_callback_with_retry_v3,
)
from .judge_command_routes import (
    resolve_failed_callback_fn_for_dispatch as resolve_failed_callback_fn_for_dispatch_v3,
)

CallbackReportFn = Callable[..., Any]


async def _invoke_v3_callback_with_retry(
    *,
    runtime: Any,
    callback_fn: CallbackReportFn,
    job_id: int,
    payload: dict[str, Any],
) -> tuple[int, int]:
    return await invoke_callback_with_retry_v3(
        callback_fn=callback_fn,
        job_id=job_id,
        payload=payload,
        max_attempts=runtime.dispatch_runtime_cfg.runtime_retry_max_attempts,
        backoff_ms=runtime.dispatch_runtime_cfg.retry_backoff_ms,
        sleep_fn=runtime.sleep_fn,
    )


async def invoke_v3_callback_with_retry_for_runtime(
    callback_fn: CallbackReportFn,
    job_id: int,
    payload: dict[str, Any],
    *,
    runtime: Any,
) -> tuple[int, int]:
    return await _invoke_v3_callback_with_retry(
        runtime=runtime,
        callback_fn=callback_fn,
        job_id=job_id,
        payload=payload,
    )


async def invoke_failed_callback_with_retry_for_runtime(
    *,
    runtime: Any,
    dispatch_type: str,
    callback_phase_failed_fn: CallbackReportFn | None,
    callback_final_failed_fn: CallbackReportFn | None,
    case_id: int,
    payload: dict[str, Any],
) -> tuple[int, int]:
    callback_fn = cast(
        CallbackReportFn,
        resolve_failed_callback_fn_for_dispatch_v3(
            dispatch_type=dispatch_type,
            callback_phase_failed_fn=callback_phase_failed_fn,
            callback_final_failed_fn=callback_final_failed_fn,
        ),
    )
    return await _invoke_v3_callback_with_retry(
        runtime=runtime,
        callback_fn=callback_fn,
        job_id=case_id,
        payload=payload,
    )


def attach_policy_trace_snapshot_for_runtime(
    *,
    runtime: Any,
    report_payload: dict[str, Any],
    profile: Any,
    prompt_profile: Any,
    tool_profile: Any,
) -> None:
    attach_policy_trace_snapshot_v3(
        report_payload=report_payload,
        profile=profile,
        prompt_profile=prompt_profile,
        tool_profile=tool_profile,
        build_policy_trace_snapshot=runtime.policy_registry_runtime.build_trace_snapshot,
        build_prompt_trace_snapshot=runtime.prompt_registry_runtime.build_trace_snapshot,
        build_tool_trace_snapshot=runtime.tool_registry_runtime.build_trace_snapshot,
    )
