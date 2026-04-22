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


async def build_blindization_rejection_route_payload(
    *,
    dispatch_type: str,
    raw_payload: dict[str, Any],
    sensitive_hits: list[str],
    extract_dispatch_meta_from_raw: Callable[[dict[str, Any]], dict[str, Any]],
    extract_receipt_dims_from_raw: Callable[[str, dict[str, Any]], dict[str, int | None]],
    build_workflow_job: Callable[..., Any],
    trace_register_start: Callable[..., Any],
    workflow_register_and_mark_blinded: Callable[..., Awaitable[Any]],
    build_failed_callback_payload: Callable[..., dict[str, Any]],
    invoke_failed_callback_with_retry: Callable[..., Awaitable[tuple[int, int]]],
    with_error_contract: Callable[..., dict[str, Any]],
    persist_dispatch_receipt: Callable[..., Awaitable[Any]],
    trace_register_failure: Callable[..., Any],
    workflow_mark_failed: Callable[..., Awaitable[Any]],
) -> dict[str, Any]:
    meta = extract_dispatch_meta_from_raw(raw_payload)
    job_id = int(meta.get("caseId") or 0)
    session_id = int(meta.get("sessionId") or 0)
    trace_id = str(meta.get("traceId") or "")
    if job_id <= 0 or session_id <= 0 or not trace_id:
        raise JudgeCommandRouteError(status_code=422, detail="input_not_blinded")

    scope_id = int(meta.get("scopeId") or 1)
    dims = extract_receipt_dims_from_raw(dispatch_type, raw_payload)
    request_payload = dict(raw_payload)
    workflow_job = build_workflow_job(
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
            str(meta.get("retrievalProfile"))
            if meta.get("retrievalProfile") is not None
            else None
        ),
    )
    trace_register_start(
        job_id=job_id,
        trace_id=trace_id,
        request=request_payload,
    )
    await workflow_register_and_mark_blinded(
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
        "caseId": job_id,
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
    error_message = "sensitive fields detected in judge input: " + ",".join(sensitive_hits[:12])
    failed_payload = build_failed_callback_payload(
        case_id=job_id,
        dispatch_type=dispatch_type,
        trace_id=trace_id,
        error_code=error_code,
        error_message=error_message,
    )
    try:
        failed_attempts, failed_retries = await invoke_failed_callback_with_retry(
            case_id=job_id,
            payload=failed_payload,
        )
    except Exception as failed_err:
        receipt_response = with_error_contract(
            {
                **response,
                "callbackStatus": "failed_callback_failed",
                "callbackError": error_message,
                "failedCallbackPayload": failed_payload,
                "failedCallbackError": str(failed_err),
            },
            error_code=f"{dispatch_type}_failed_callback_failed",
            error_message=str(failed_err),
            dispatch_type=dispatch_type,
            trace_id=trace_id,
            retryable=False,
            category="blindization_rejection",
            details={"sensitiveHits": sensitive_hits[:12]},
        )
        await persist_dispatch_receipt(
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
                str(meta.get("retrievalProfile"))
                if meta.get("retrievalProfile") is not None
                else None
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
        trace_register_failure(
            job_id=job_id,
            response=receipt_response,
            callback_status="failed_callback_failed",
            callback_error=str(failed_err),
        )
        await workflow_mark_failed(
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
        raise JudgeCommandRouteError(
            status_code=502,
            detail=f"{dispatch_type}_failed_callback_failed: {failed_err}",
        ) from failed_err

    receipt_response = with_error_contract(
        {
            **response,
            "callbackStatus": "failed_reported",
            "callbackError": error_message,
            "failedCallbackPayload": failed_payload,
            "failedCallbackAttempts": failed_attempts,
            "failedCallbackRetries": failed_retries,
        },
        error_code=error_code,
        error_message=error_message,
        dispatch_type=dispatch_type,
        trace_id=trace_id,
        retryable=False,
        category="blindization_rejection",
        details={"sensitiveHits": sensitive_hits[:12]},
    )
    await persist_dispatch_receipt(
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
            str(meta.get("retrievalProfile"))
            if meta.get("retrievalProfile") is not None
            else None
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
    trace_register_failure(
        job_id=job_id,
        response=receipt_response,
        callback_status="failed_reported",
        callback_error=error_message,
    )
    await workflow_mark_failed(
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
    raise JudgeCommandRouteError(status_code=422, detail=error_code)


async def build_phase_dispatch_report_materialization_route_payload(
    *,
    parsed: Any,
    request_payload: dict[str, Any],
    policy_profile: Any,
    prompt_profile: Any,
    tool_profile: Any,
    build_phase_report_payload: Callable[..., Awaitable[dict[str, Any]]],
    attach_judge_agent_runtime_trace: Callable[..., Awaitable[None]],
    attach_policy_trace_snapshot: Callable[..., None],
    attach_report_attestation: Callable[..., None],
    upsert_claim_ledger_record: Callable[..., Awaitable[Any]],
    build_phase_judge_workflow_payload: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    report_payload = await build_phase_report_payload(request=parsed)
    await attach_judge_agent_runtime_trace(
        report_payload=report_payload,
        dispatch_type="phase",
        case_id=parsed.case_id,
        scope_id=parsed.scope_id,
        session_id=parsed.session_id,
        trace_id=parsed.trace_id,
        phase_no=parsed.phase_no,
    )
    attach_policy_trace_snapshot(
        report_payload=report_payload,
        profile=policy_profile,
        prompt_profile=prompt_profile,
        tool_profile=tool_profile,
    )
    attach_report_attestation(
        report_payload=report_payload,
        dispatch_type="phase",
    )
    await upsert_claim_ledger_record(
        case_id=parsed.case_id,
        dispatch_type="phase",
        trace_id=parsed.trace_id,
        report_payload=report_payload,
        request_payload=request_payload,
    )
    phase_judge_workflow_payload = build_phase_judge_workflow_payload(
        request=parsed,
        report_payload=report_payload,
    )
    return {
        "reportPayload": report_payload,
        "phaseJudgeWorkflowPayload": phase_judge_workflow_payload,
    }


async def build_phase_dispatch_callback_delivery_route_payload(
    *,
    parsed: Any,
    report_payload: dict[str, Any],
    deliver_report_callback_with_failed_fallback: Callable[..., Awaitable[Any]],
    report_callback_fn: Callable[..., Any],
    failed_callback_fn: Callable[..., Any],
    invoke_with_retry: Callable[..., Awaitable[tuple[int, int]]],
    build_failed_callback_payload: Callable[..., dict[str, Any]],
) -> Any:
    return await deliver_report_callback_with_failed_fallback(
        job_id=parsed.case_id,
        report_payload=report_payload,
        report_callback_fn=report_callback_fn,
        failed_callback_fn=failed_callback_fn,
        invoke_with_retry=invoke_with_retry,
        build_failed_payload=lambda error_message: build_failed_callback_payload(
            case_id=parsed.case_id,
            dispatch_type="phase",
            trace_id=parsed.trace_id,
            error_code="phase_callback_retry_exhausted",
            error_message=error_message,
            degradation_level=int(report_payload.get("degradationLevel") or 0),
        ),
    )


async def build_final_dispatch_callback_delivery_route_payload(
    *,
    parsed: Any,
    report_payload: dict[str, Any],
    deliver_report_callback_with_failed_fallback: Callable[..., Awaitable[Any]],
    report_callback_fn: Callable[..., Any],
    failed_callback_fn: Callable[..., Any],
    invoke_with_retry: Callable[..., Awaitable[tuple[int, int]]],
    build_failed_callback_payload: Callable[..., dict[str, Any]],
) -> Any:
    return await deliver_report_callback_with_failed_fallback(
        job_id=parsed.case_id,
        report_payload=report_payload,
        report_callback_fn=report_callback_fn,
        failed_callback_fn=failed_callback_fn,
        invoke_with_retry=invoke_with_retry,
        build_failed_payload=lambda error_message: build_failed_callback_payload(
            case_id=parsed.case_id,
            dispatch_type="final",
            trace_id=parsed.trace_id,
            error_code="final_callback_retry_exhausted",
            error_message=error_message,
            degradation_level=int(report_payload.get("degradationLevel") or 0),
        ),
    )


async def build_phase_dispatch_callback_result_route_payload(
    *,
    parsed: Any,
    response: dict[str, Any],
    request_payload: dict[str, Any],
    report_payload: dict[str, Any],
    callback_outcome: Any,
    callback_status_reported: str,
    callback_status_failed_reported: str,
    callback_status_failed_callback_failed: str,
    with_error_contract: Callable[..., dict[str, Any]],
    persist_dispatch_receipt: Callable[..., Awaitable[Any]],
    trace_register_failure: Callable[..., Any],
    trace_register_success: Callable[..., Any],
    workflow_mark_failed: Callable[..., Awaitable[Any]],
    workflow_mark_completed: Callable[..., Awaitable[Any]],
    build_phase_workflow_reported_payload: Callable[..., dict[str, Any]],
    build_trace_report_summary: Callable[..., dict[str, Any]],
    clear_idempotency: Callable[[str], Any],
    set_idempotency_success: Callable[..., Any],
    idempotency_ttl_secs: int,
    phase_judge_workflow_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if callback_outcome.callback_status == callback_status_failed_callback_failed:
        error_message = str(callback_outcome.report_error or "")
        failed_error = str(callback_outcome.failed_error or "unknown")
        failed_payload = (
            dict(callback_outcome.failed_payload)
            if isinstance(callback_outcome.failed_payload, dict)
            else {}
        )
        receipt_response = with_error_contract(
            {
                **response,
                "status": "callback_failed",
                "callbackStatus": "failed_callback_failed",
                "callbackError": error_message,
                "reportPayload": report_payload,
                "failedCallbackPayload": failed_payload,
                "failedCallbackError": failed_error,
            },
            error_code="phase_failed_callback_failed",
            error_message=failed_error,
            dispatch_type="phase",
            trace_id=parsed.trace_id,
            retryable=False,
            category="callback_delivery",
            details={"reportError": error_message},
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
            status="callback_failed",
            request_payload=request_payload,
            response_payload=receipt_response,
        )
        trace_register_failure(
            job_id=parsed.case_id,
            response=receipt_response,
            callback_status="failed_callback_failed",
            callback_error=failed_error,
        )
        await workflow_mark_failed(
            job_id=parsed.case_id,
            error_code="phase_failed_callback_failed",
            error_message=failed_error,
            event_payload=build_phase_workflow_reported_payload(
                request=parsed,
                callback_status="failed_callback_failed",
            ),
        )
        clear_idempotency(parsed.idempotency_key)
        raise JudgeCommandRouteError(
            status_code=502,
            detail=f"phase_failed_callback_failed: {failed_error}",
        )

    if callback_outcome.callback_status == callback_status_failed_reported:
        error_message = str(callback_outcome.report_error or "")
        failed_payload = (
            dict(callback_outcome.failed_payload)
            if isinstance(callback_outcome.failed_payload, dict)
            else {}
        )
        failed_attempts = int(callback_outcome.failed_attempts or 0)
        failed_retries = int(callback_outcome.failed_retries or 0)
        receipt_response = with_error_contract(
            {
                **response,
                "status": "callback_failed",
                "callbackStatus": "failed_reported",
                "callbackError": error_message,
                "reportPayload": report_payload,
                "failedCallbackPayload": failed_payload,
                "failedCallbackAttempts": failed_attempts,
                "failedCallbackRetries": failed_retries,
            },
            error_code="phase_callback_retry_exhausted",
            error_message=error_message,
            dispatch_type="phase",
            trace_id=parsed.trace_id,
            retryable=False,
            category="callback_delivery",
            details={
                "failedCallbackAttempts": failed_attempts,
                "failedCallbackRetries": failed_retries,
            },
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
            status="callback_failed",
            request_payload=request_payload,
            response_payload=receipt_response,
        )
        trace_register_failure(
            job_id=parsed.case_id,
            response=receipt_response,
            callback_status="failed_reported",
            callback_error=error_message,
        )
        await workflow_mark_failed(
            job_id=parsed.case_id,
            error_code="phase_callback_retry_exhausted",
            error_message=error_message,
            event_payload=build_phase_workflow_reported_payload(
                request=parsed,
                callback_status="failed_reported",
            ),
        )
        clear_idempotency(parsed.idempotency_key)
        raise JudgeCommandRouteError(
            status_code=502,
            detail=f"phase_callback_failed: {error_message}",
        )

    if callback_outcome.callback_status != callback_status_reported:
        raise RuntimeError("phase_callback_outcome_status_invalid")

    callback_attempts = int(callback_outcome.callback_attempts or 0)
    callback_retries = int(callback_outcome.callback_retries or 0)
    reported_response = {
        **response,
        "callbackStatus": callback_status_reported,
        "callbackAttempts": callback_attempts,
        "callbackRetries": callback_retries,
        "reportPayload": report_payload,
    }
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
        status="reported",
        request_payload=request_payload,
        response_payload=reported_response,
    )
    trace_register_success(
        job_id=parsed.case_id,
        response=reported_response,
        callback_status="reported",
        report_summary=build_trace_report_summary(
            dispatch_type="phase",
            payload=report_payload,
            callback_status="reported",
            callback_error=None,
            judge_workflow=phase_judge_workflow_payload,
        ),
    )
    await workflow_mark_completed(
        job_id=parsed.case_id,
        event_payload=build_phase_workflow_reported_payload(
            request=parsed,
            callback_status=callback_status_reported,
        ),
    )
    set_idempotency_success(
        key=parsed.idempotency_key,
        job_id=parsed.case_id,
        response=response,
        ttl_secs=idempotency_ttl_secs,
    )
    return response


async def build_final_dispatch_callback_result_route_payload(
    *,
    parsed: Any,
    response: dict[str, Any],
    request_payload: dict[str, Any],
    report_payload: dict[str, Any],
    callback_outcome: Any,
    callback_status_reported: str,
    callback_status_failed_reported: str,
    callback_status_failed_callback_failed: str,
    with_error_contract: Callable[..., dict[str, Any]],
    persist_dispatch_receipt: Callable[..., Awaitable[Any]],
    trace_register_failure: Callable[..., Any],
    trace_register_success: Callable[..., Any],
    workflow_mark_failed: Callable[..., Awaitable[Any]],
    workflow_mark_review_required: Callable[..., Awaitable[Any]],
    workflow_mark_completed: Callable[..., Awaitable[Any]],
    build_final_workflow_reported_payload: Callable[..., dict[str, Any]],
    build_trace_report_summary: Callable[..., dict[str, Any]],
    clear_idempotency: Callable[[str], Any],
    set_idempotency_success: Callable[..., Any],
    idempotency_ttl_secs: int,
    final_judge_workflow_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if callback_outcome.callback_status == callback_status_failed_callback_failed:
        error_message = str(callback_outcome.report_error or "")
        failed_error = str(callback_outcome.failed_error or "unknown")
        failed_payload = (
            dict(callback_outcome.failed_payload)
            if isinstance(callback_outcome.failed_payload, dict)
            else {}
        )
        receipt_response = with_error_contract(
            {
                **response,
                "status": "callback_failed",
                "callbackStatus": "failed_callback_failed",
                "callbackError": error_message,
                "reportPayload": report_payload,
                "failedCallbackPayload": failed_payload,
                "failedCallbackError": failed_error,
            },
            error_code="final_failed_callback_failed",
            error_message=failed_error,
            dispatch_type="final",
            trace_id=parsed.trace_id,
            retryable=False,
            category="callback_delivery",
            details={"reportError": error_message},
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
            status="callback_failed",
            request_payload=request_payload,
            response_payload=receipt_response,
        )
        trace_register_failure(
            job_id=parsed.case_id,
            response=receipt_response,
            callback_status="failed_callback_failed",
            callback_error=failed_error,
        )
        await workflow_mark_failed(
            job_id=parsed.case_id,
            error_code="final_failed_callback_failed",
            error_message=failed_error,
            event_payload={
                "dispatchType": "final",
                "phaseStartNo": parsed.phase_start_no,
                "phaseEndNo": parsed.phase_end_no,
                "callbackStatus": "failed_callback_failed",
            },
        )
        clear_idempotency(parsed.idempotency_key)
        raise JudgeCommandRouteError(
            status_code=502,
            detail=f"final_failed_callback_failed: {failed_error}",
        )

    if callback_outcome.callback_status == callback_status_failed_reported:
        error_message = str(callback_outcome.report_error or "")
        failed_payload = (
            dict(callback_outcome.failed_payload)
            if isinstance(callback_outcome.failed_payload, dict)
            else {}
        )
        failed_attempts = int(callback_outcome.failed_attempts or 0)
        failed_retries = int(callback_outcome.failed_retries or 0)
        receipt_response = with_error_contract(
            {
                **response,
                "status": "callback_failed",
                "callbackStatus": "failed_reported",
                "callbackError": error_message,
                "reportPayload": report_payload,
                "failedCallbackPayload": failed_payload,
                "failedCallbackAttempts": failed_attempts,
                "failedCallbackRetries": failed_retries,
            },
            error_code="final_callback_retry_exhausted",
            error_message=error_message,
            dispatch_type="final",
            trace_id=parsed.trace_id,
            retryable=False,
            category="callback_delivery",
            details={
                "failedCallbackAttempts": failed_attempts,
                "failedCallbackRetries": failed_retries,
            },
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
            status="callback_failed",
            request_payload=request_payload,
            response_payload=receipt_response,
        )
        trace_register_failure(
            job_id=parsed.case_id,
            response=receipt_response,
            callback_status="failed_reported",
            callback_error=error_message,
        )
        await workflow_mark_failed(
            job_id=parsed.case_id,
            error_code="final_callback_retry_exhausted",
            error_message=error_message,
            event_payload={
                "dispatchType": "final",
                "phaseStartNo": parsed.phase_start_no,
                "phaseEndNo": parsed.phase_end_no,
                "callbackStatus": "failed_reported",
            },
        )
        clear_idempotency(parsed.idempotency_key)
        raise JudgeCommandRouteError(
            status_code=502,
            detail=f"final_callback_failed: {error_message}",
        )

    if callback_outcome.callback_status != callback_status_reported:
        raise RuntimeError("final_callback_outcome_status_invalid")

    callback_attempts = int(callback_outcome.callback_attempts or 0)
    callback_retries = int(callback_outcome.callback_retries or 0)
    reported_response = {
        **response,
        "callbackStatus": callback_status_reported,
        "callbackAttempts": callback_attempts,
        "callbackRetries": callback_retries,
        "reportPayload": report_payload,
    }
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
        status="reported",
        request_payload=request_payload,
        response_payload=reported_response,
    )
    trace_register_success(
        job_id=parsed.case_id,
        response=reported_response,
        callback_status=callback_status_reported,
        report_summary=build_trace_report_summary(
            dispatch_type="final",
            payload=report_payload,
            callback_status="reported",
            callback_error=None,
            judge_workflow=final_judge_workflow_payload,
        ),
    )
    review_required = bool(report_payload.get("reviewRequired"))
    workflow_event_payload = build_final_workflow_reported_payload(
        request=parsed,
        report_payload=report_payload,
        callback_status=callback_status_reported,
    )
    if review_required:
        await workflow_mark_review_required(
            job_id=parsed.case_id,
            event_payload=workflow_event_payload,
        )
    else:
        await workflow_mark_completed(
            job_id=parsed.case_id,
            event_payload=workflow_event_payload,
        )
    set_idempotency_success(
        key=parsed.idempotency_key,
        job_id=parsed.case_id,
        response=response,
        ttl_secs=idempotency_ttl_secs,
    )
    return response


async def build_final_contract_blocked_route_payload(
    *,
    parsed: Any,
    response: dict[str, Any],
    request_payload: dict[str, Any],
    report_payload: dict[str, Any],
    contract_missing_fields: list[str],
    upsert_audit_alert: Callable[..., Any],
    sync_audit_alert_to_facts: Callable[..., Awaitable[Any]],
    build_failed_callback_payload: Callable[..., dict[str, Any]],
    invoke_failed_callback_with_retry: Callable[..., Awaitable[tuple[int, int]]],
    with_error_contract: Callable[..., dict[str, Any]],
    persist_dispatch_receipt: Callable[..., Awaitable[Any]],
    trace_register_failure: Callable[..., Any],
    workflow_mark_failed: Callable[..., Awaitable[Any]],
    clear_idempotency: Callable[[str], Any],
) -> None:
    error_text = "final_contract_violation: missing_fields=" + ",".join(
        contract_missing_fields[:12]
    )
    alert = upsert_audit_alert(
        job_id=parsed.case_id,
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
    await sync_audit_alert_to_facts(alert=alert)
    failed_payload = build_failed_callback_payload(
        case_id=parsed.case_id,
        dispatch_type="final",
        trace_id=parsed.trace_id,
        error_code="final_contract_blocked",
        error_message=error_text,
        audit_alert_ids=[alert.alert_id],
        degradation_level=int(report_payload.get("degradationLevel") or 0),
    )
    try:
        failed_attempts, failed_retries = await invoke_failed_callback_with_retry(
            case_id=parsed.case_id,
            payload=failed_payload,
        )
    except Exception as failed_err:
        receipt_response = with_error_contract(
            {
                **response,
                "status": "callback_failed",
                "callbackStatus": "failed_callback_failed",
                "callbackError": error_text,
                "auditAlertIds": [alert.alert_id],
                "reportPayload": report_payload,
                "failedCallbackPayload": failed_payload,
                "failedCallbackError": str(failed_err),
            },
            error_code="final_failed_callback_failed",
            error_message=str(failed_err),
            dispatch_type="final",
            trace_id=parsed.trace_id,
            retryable=False,
            category="contract_blocked",
            details={
                "auditAlertId": alert.alert_id,
                "blockedReason": error_text,
            },
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
            status="callback_failed",
            request_payload=request_payload,
            response_payload=receipt_response,
        )
        trace_register_failure(
            job_id=parsed.case_id,
            response=receipt_response,
            callback_status="failed_callback_failed",
            callback_error=str(failed_err),
        )
        await workflow_mark_failed(
            job_id=parsed.case_id,
            error_code="final_failed_callback_failed",
            error_message=str(failed_err),
            event_payload={
                "dispatchType": "final",
                "phaseStartNo": parsed.phase_start_no,
                "phaseEndNo": parsed.phase_end_no,
                "callbackStatus": "failed_callback_failed",
            },
        )
        clear_idempotency(parsed.idempotency_key)
        raise JudgeCommandRouteError(
            status_code=502,
            detail=f"final_failed_callback_failed: {failed_err}",
        )

    receipt_response = with_error_contract(
        {
            **response,
            "status": "callback_failed",
            "callbackStatus": "blocked_failed_reported",
            "callbackError": error_text,
            "auditAlertIds": [alert.alert_id],
            "reportPayload": report_payload,
            "failedCallbackPayload": failed_payload,
            "failedCallbackAttempts": failed_attempts,
            "failedCallbackRetries": failed_retries,
        },
        error_code="final_contract_blocked",
        error_message=error_text,
        dispatch_type="final",
        trace_id=parsed.trace_id,
        retryable=False,
        category="contract_blocked",
        details={
            "auditAlertId": alert.alert_id,
            "failedCallbackAttempts": failed_attempts,
            "failedCallbackRetries": failed_retries,
            "missingFields": contract_missing_fields[:12],
        },
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
        status="callback_failed",
        request_payload=request_payload,
        response_payload=receipt_response,
    )
    trace_register_failure(
        job_id=parsed.case_id,
        response=receipt_response,
        callback_status="blocked_failed_reported",
        callback_error=error_text,
    )
    await workflow_mark_failed(
        job_id=parsed.case_id,
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
    clear_idempotency(parsed.idempotency_key)
    raise JudgeCommandRouteError(
        status_code=502,
        detail="final_contract_blocked: missing_critical_fields",
    )


async def build_final_dispatch_report_materialization_route_payload(
    *,
    parsed: Any,
    request_payload: dict[str, Any],
    policy_profile: Any,
    prompt_profile: Any,
    tool_profile: Any,
    list_dispatch_receipts: Callable[..., Awaitable[list[Any]]],
    build_final_report_payload: Callable[..., dict[str, Any]],
    resolve_panel_runtime_profiles: Callable[..., dict[str, dict[str, Any]]],
    attach_judge_agent_runtime_trace: Callable[..., Awaitable[None]],
    attach_policy_trace_snapshot: Callable[..., None],
    attach_report_attestation: Callable[..., None],
    upsert_claim_ledger_record: Callable[..., Awaitable[Any]],
    build_final_judge_workflow_payload: Callable[..., dict[str, Any]],
    validate_final_report_payload_contract: Callable[[dict[str, Any]], list[str]],
) -> dict[str, Any]:
    phase_receipts = await list_dispatch_receipts(
        dispatch_type="phase",
        session_id=parsed.session_id,
        status="reported",
        limit=1000,
    )
    report_payload = build_final_report_payload(
        request=parsed,
        phase_receipts=phase_receipts,
        fairness_thresholds=policy_profile.fairness_thresholds,
        panel_runtime_profiles=resolve_panel_runtime_profiles(profile=policy_profile),
    )
    await attach_judge_agent_runtime_trace(
        report_payload=report_payload,
        dispatch_type="final",
        case_id=parsed.case_id,
        scope_id=parsed.scope_id,
        session_id=parsed.session_id,
        trace_id=parsed.trace_id,
        phase_start_no=parsed.phase_start_no,
        phase_end_no=parsed.phase_end_no,
    )
    attach_policy_trace_snapshot(
        report_payload=report_payload,
        profile=policy_profile,
        prompt_profile=prompt_profile,
        tool_profile=tool_profile,
    )
    attach_report_attestation(
        report_payload=report_payload,
        dispatch_type="final",
    )
    await upsert_claim_ledger_record(
        case_id=parsed.case_id,
        dispatch_type="final",
        trace_id=parsed.trace_id,
        report_payload=report_payload,
        request_payload=request_payload,
    )
    final_judge_workflow_payload = build_final_judge_workflow_payload(
        request=parsed,
        report_payload=report_payload,
    )
    contract_missing_fields = validate_final_report_payload_contract(report_payload)
    return {
        "reportPayload": report_payload,
        "finalJudgeWorkflowPayload": final_judge_workflow_payload,
        "contractMissingFields": contract_missing_fields,
    }
