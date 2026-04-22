from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from pydantic import ValidationError


@dataclass(frozen=True)
class JudgeCommandRouteError(Exception):
    status_code: int
    detail: Any


def _raise_route_error_from_http_exception(err: Exception) -> None:
    status_code = getattr(err, "status_code", None)
    detail = getattr(err, "detail", None)
    if isinstance(status_code, int):
        raise JudgeCommandRouteError(status_code=status_code, detail=detail) from err
    if status_code is not None:
        try:
            normalized_status_code = int(status_code)
        except (TypeError, ValueError):
            return
        raise JudgeCommandRouteError(
            status_code=normalized_status_code,
            detail=detail,
        ) from err


async def build_case_create_route_payload(
    *,
    raw_payload: dict[str, Any],
    case_create_model_validate: Callable[[dict[str, Any]], Any],
    resolve_idempotency_or_raise: Callable[..., dict[str, Any] | None],
    ensure_registry_runtime_ready: Callable[[], Awaitable[None]],
    resolve_policy_profile: Callable[..., Any],
    resolve_prompt_profile: Callable[..., Any],
    resolve_tool_profile: Callable[..., Any],
    workflow_get_job: Callable[..., Awaitable[Any | None]],
    build_workflow_job: Callable[..., Any],
    workflow_register_and_mark_case_built: Callable[..., Awaitable[Any]],
    serialize_workflow_job: Callable[[Any], dict[str, Any]],
    trace_register_start: Callable[..., Any],
    trace_register_success: Callable[..., Any],
    build_trace_report_summary: Callable[..., dict[str, Any]],
    set_idempotency_success: Callable[..., Any],
    idempotency_ttl_secs: int,
) -> dict[str, Any]:
    try:
        parsed = case_create_model_validate(raw_payload)
    except ValidationError as err:
        raise JudgeCommandRouteError(status_code=422, detail=err.errors()) from err

    replayed = resolve_idempotency_or_raise(
        key=parsed.idempotency_key,
        job_id=parsed.case_id,
        conflict_detail="idempotency_conflict:case_create",
    )
    if replayed is not None:
        return replayed

    await ensure_registry_runtime_ready()
    policy_profile = resolve_policy_profile(
        judge_policy_version=parsed.judge_policy_version,
        rubric_version=parsed.rubric_version,
        topic_domain=parsed.topic_domain,
    )
    prompt_profile = resolve_prompt_profile(
        prompt_registry_version=policy_profile.prompt_registry_version,
    )
    tool_profile = resolve_tool_profile(
        tool_registry_version=policy_profile.tool_registry_version,
    )

    existing_job = await workflow_get_job(job_id=parsed.case_id)
    if existing_job is not None:
        raise JudgeCommandRouteError(status_code=409, detail="case_already_exists")

    request_payload = parsed.model_dump(mode="json")
    workflow_job = build_workflow_job(
        dispatch_type="phase",
        job_id=parsed.case_id,
        trace_id=parsed.trace_id,
        scope_id=parsed.scope_id,
        session_id=parsed.session_id,
        idempotency_key=parsed.idempotency_key,
        rubric_version=parsed.rubric_version,
        judge_policy_version=parsed.judge_policy_version,
        topic_domain=parsed.topic_domain,
        retrieval_profile=parsed.retrieval_profile,
    )
    transitioned_job = await workflow_register_and_mark_case_built(
        job=workflow_job,
        event_payload={
            "dispatchType": "case",
            "scopeId": parsed.scope_id,
            "sessionId": parsed.session_id,
            "traceId": parsed.trace_id,
            "policyVersion": policy_profile.version,
            "promptVersion": prompt_profile.version,
            "toolsetVersion": tool_profile.version,
            "caseStatus": "case_built",
        },
    )
    response = {
        "accepted": True,
        "status": "case_built",
        "caseId": parsed.case_id,
        "scopeId": parsed.scope_id,
        "sessionId": parsed.session_id,
        "traceId": parsed.trace_id,
        "idempotencyKey": parsed.idempotency_key,
        "registryVersions": {
            "policyVersion": policy_profile.version,
            "promptVersion": prompt_profile.version,
            "toolsetVersion": tool_profile.version,
        },
        "workflow": serialize_workflow_job(transitioned_job),
    }
    trace_register_start(
        job_id=parsed.case_id,
        trace_id=parsed.trace_id,
        request=request_payload,
    )
    trace_register_success(
        job_id=parsed.case_id,
        response=response,
        callback_status="case_built",
        report_summary=build_trace_report_summary(
            dispatch_type="case",
            payload={},
            callback_status="case_built",
            callback_error=None,
        ),
    )
    set_idempotency_success(
        key=parsed.idempotency_key,
        job_id=parsed.case_id,
        response=response,
        ttl_secs=idempotency_ttl_secs,
    )
    return response


async def build_phase_dispatch_preflight_route_payload(
    *,
    raw_payload: dict[str, Any],
    phase_dispatch_model_validate: Callable[[dict[str, Any]], Any],
    validate_phase_dispatch_request: Callable[[Any], None],
    resolve_idempotency_or_raise: Callable[..., dict[str, Any] | None],
    ensure_registry_runtime_ready: Callable[[], Awaitable[None]],
    resolve_policy_profile: Callable[..., Any],
    resolve_prompt_profile: Callable[..., Any],
    resolve_tool_profile: Callable[..., Any],
    build_phase_dispatch_accepted_response: Callable[..., dict[str, Any]],
    build_workflow_job: Callable[..., Any],
    trace_register_start: Callable[..., Any],
    persist_dispatch_receipt: Callable[..., Awaitable[Any]],
    workflow_register_and_mark_blinded: Callable[..., Awaitable[Any]],
    build_phase_workflow_register_payload: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    try:
        parsed = phase_dispatch_model_validate(raw_payload)
    except ValidationError as err:
        raise JudgeCommandRouteError(status_code=422, detail=err.errors()) from err

    try:
        validate_phase_dispatch_request(parsed)
    except Exception as err:
        _raise_route_error_from_http_exception(err)
        raise

    replayed = resolve_idempotency_or_raise(
        key=parsed.idempotency_key,
        job_id=parsed.case_id,
        conflict_detail="idempotency_conflict:phase_dispatch",
    )
    if replayed is not None:
        return {"replayedResponse": replayed}

    await ensure_registry_runtime_ready()
    policy_profile = resolve_policy_profile(
        judge_policy_version=parsed.judge_policy_version,
        rubric_version=parsed.rubric_version,
        topic_domain=parsed.topic_domain,
    )
    prompt_profile = resolve_prompt_profile(
        prompt_registry_version=policy_profile.prompt_registry_version,
    )
    tool_profile = resolve_tool_profile(
        tool_registry_version=policy_profile.tool_registry_version,
    )

    response = build_phase_dispatch_accepted_response(request=parsed)
    request_payload = parsed.model_dump(mode="json")
    workflow_job = build_workflow_job(
        dispatch_type="phase",
        job_id=parsed.case_id,
        trace_id=parsed.trace_id,
        scope_id=parsed.scope_id,
        session_id=parsed.session_id,
        idempotency_key=parsed.idempotency_key,
        rubric_version=parsed.rubric_version,
        judge_policy_version=parsed.judge_policy_version,
        topic_domain=parsed.topic_domain,
        retrieval_profile=parsed.retrieval_profile,
    )
    trace_register_start(
        job_id=parsed.case_id,
        trace_id=parsed.trace_id,
        request=request_payload,
    )
    await persist_dispatch_receipt(
        dispatch_type="phase",
        job_id=parsed.case_id,
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
    await workflow_register_and_mark_blinded(
        job=workflow_job,
        event_payload=build_phase_workflow_register_payload(
            request=parsed,
            policy_version=policy_profile.version,
            prompt_version=prompt_profile.version,
            toolset_version=tool_profile.version,
        ),
    )
    return {
        "parsed": parsed,
        "response": response,
        "requestPayload": request_payload,
        "policyProfile": policy_profile,
        "promptProfile": prompt_profile,
        "toolProfile": tool_profile,
    }


async def build_final_dispatch_preflight_route_payload(
    *,
    raw_payload: dict[str, Any],
    final_dispatch_model_validate: Callable[[dict[str, Any]], Any],
    validate_final_dispatch_request: Callable[[Any], None],
    resolve_idempotency_or_raise: Callable[..., dict[str, Any] | None],
    ensure_registry_runtime_ready: Callable[[], Awaitable[None]],
    resolve_policy_profile: Callable[..., Any],
    resolve_prompt_profile: Callable[..., Any],
    resolve_tool_profile: Callable[..., Any],
    build_final_dispatch_accepted_response: Callable[..., dict[str, Any]],
    build_workflow_job: Callable[..., Any],
    trace_register_start: Callable[..., Any],
    persist_dispatch_receipt: Callable[..., Awaitable[Any]],
    workflow_register_and_mark_blinded: Callable[..., Awaitable[Any]],
    build_final_workflow_register_payload: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    try:
        parsed = final_dispatch_model_validate(raw_payload)
    except ValidationError as err:
        raise JudgeCommandRouteError(status_code=422, detail=err.errors()) from err

    try:
        validate_final_dispatch_request(parsed)
    except Exception as err:
        _raise_route_error_from_http_exception(err)
        raise

    replayed = resolve_idempotency_or_raise(
        key=parsed.idempotency_key,
        job_id=parsed.case_id,
        conflict_detail="idempotency_conflict:final_dispatch",
    )
    if replayed is not None:
        return {"replayedResponse": replayed}

    await ensure_registry_runtime_ready()
    policy_profile = resolve_policy_profile(
        judge_policy_version=parsed.judge_policy_version,
        rubric_version=parsed.rubric_version,
        topic_domain=parsed.topic_domain,
    )
    prompt_profile = resolve_prompt_profile(
        prompt_registry_version=policy_profile.prompt_registry_version,
    )
    tool_profile = resolve_tool_profile(
        tool_registry_version=policy_profile.tool_registry_version,
    )

    response = build_final_dispatch_accepted_response(request=parsed)
    request_payload = parsed.model_dump(mode="json")
    workflow_job = build_workflow_job(
        dispatch_type="final",
        job_id=parsed.case_id,
        trace_id=parsed.trace_id,
        scope_id=parsed.scope_id,
        session_id=parsed.session_id,
        idempotency_key=parsed.idempotency_key,
        rubric_version=parsed.rubric_version,
        judge_policy_version=parsed.judge_policy_version,
        topic_domain=parsed.topic_domain,
        retrieval_profile=None,
    )
    trace_register_start(
        job_id=parsed.case_id,
        trace_id=parsed.trace_id,
        request=request_payload,
    )
    await persist_dispatch_receipt(
        dispatch_type="final",
        job_id=parsed.case_id,
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
    await workflow_register_and_mark_blinded(
        job=workflow_job,
        event_payload=build_final_workflow_register_payload(
            request=parsed,
            policy_version=policy_profile.version,
            prompt_version=prompt_profile.version,
            toolset_version=tool_profile.version,
        ),
    )
    return {
        "parsed": parsed,
        "response": response,
        "requestPayload": request_payload,
        "policyProfile": policy_profile,
        "promptProfile": prompt_profile,
        "toolProfile": tool_profile,
    }
