from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, cast

from fastapi import FastAPI, Header, Request

from ..models import CaseCreateRequest, FinalDispatchRequest, PhaseDispatchRequest
from ..runtime_types import CallbackReportFn
from .judge_command_routes import (
    build_blindization_rejection_route_payload as build_blindization_rejection_route_payload_v3,
)
from .judge_command_routes import (
    build_case_create_route_payload as build_case_create_route_payload_v3,
)
from .judge_command_routes import (
    build_failed_callback_payload as build_failed_callback_payload_v3,
)
from .judge_command_routes import (
    build_final_contract_blocked_route_payload as build_final_contract_blocked_route_payload_v3,
)
from .judge_command_routes import (
    build_final_dispatch_callback_delivery_route_payload as build_final_dispatch_callback_delivery_route_payload_v3,
)
from .judge_command_routes import (
    build_final_dispatch_callback_result_route_payload as build_final_dispatch_callback_result_route_payload_v3,
)
from .judge_command_routes import (
    build_final_dispatch_preflight_route_payload as build_final_dispatch_preflight_route_payload_v3,
)
from .judge_command_routes import (
    build_final_dispatch_report_materialization_route_payload as build_final_dispatch_report_materialization_route_payload_v3,
)
from .judge_command_routes import (
    build_phase_dispatch_callback_delivery_route_payload as build_phase_dispatch_callback_delivery_route_payload_v3,
)
from .judge_command_routes import (
    build_phase_dispatch_callback_result_route_payload as build_phase_dispatch_callback_result_route_payload_v3,
)
from .judge_command_routes import (
    build_phase_dispatch_preflight_route_payload as build_phase_dispatch_preflight_route_payload_v3,
)
from .judge_command_routes import (
    build_phase_dispatch_report_materialization_route_payload as build_phase_dispatch_report_materialization_route_payload_v3,
)
from .judge_command_routes import build_workflow_job as build_workflow_job_v3
from .judge_command_routes import find_sensitive_key_hits as find_sensitive_key_hits_v3
from .judge_command_routes import (
    resolve_failed_callback_fn_for_dispatch as resolve_failed_callback_fn_for_dispatch_v3,
)
from .judge_command_routes import (
    resolve_report_callback_fn_for_dispatch as resolve_report_callback_fn_for_dispatch_v3,
)
from .judge_command_routes import with_error_contract as with_error_contract_v3
from .judge_dispatch_runtime import (
    CALLBACK_STATUS_FAILED_CALLBACK_FAILED as CALLBACK_STATUS_FAILED_CALLBACK_FAILED_V3,
)
from .judge_dispatch_runtime import (
    CALLBACK_STATUS_FAILED_REPORTED as CALLBACK_STATUS_FAILED_REPORTED_V3,
)
from .judge_dispatch_runtime import CALLBACK_STATUS_REPORTED as CALLBACK_STATUS_REPORTED_V3
from .judge_dispatch_runtime import (
    build_final_dispatch_accepted_response as build_final_dispatch_accepted_response_v3,
)
from .judge_dispatch_runtime import (
    build_final_workflow_register_payload as build_final_workflow_register_payload_v3,
)
from .judge_dispatch_runtime import (
    build_final_workflow_reported_payload as build_final_workflow_reported_payload_v3,
)
from .judge_dispatch_runtime import (
    build_phase_dispatch_accepted_response as build_phase_dispatch_accepted_response_v3,
)
from .judge_dispatch_runtime import (
    build_phase_workflow_register_payload as build_phase_workflow_register_payload_v3,
)
from .judge_dispatch_runtime import (
    build_phase_workflow_reported_payload as build_phase_workflow_reported_payload_v3,
)
from .judge_dispatch_runtime import (
    deliver_report_callback_with_failed_fallback as deliver_report_callback_with_failed_fallback_v3,
)
from .judge_trace_summary import build_trace_report_summary as build_trace_report_summary_v3
from .judge_workflow_roles import (
    build_final_judge_workflow_payload as build_final_judge_workflow_payload_v3,
)
from .judge_workflow_roles import (
    build_phase_judge_workflow_payload as build_phase_judge_workflow_payload_v3,
)
from .trust_attestation import attach_report_attestation as attach_report_attestation_v3


@dataclass(frozen=True)
class JudgeCommandRouteDependencies:
    runtime: Any
    require_internal_key_fn: Callable[[Any, str | None], None]
    read_json_object_or_raise_422: Callable[..., Awaitable[dict[str, Any]]]
    run_judge_command_route_guard: Callable[[Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]]
    ensure_registry_runtime_ready: Callable[[], Awaitable[None]]
    resolve_idempotency_or_raise: Callable[..., Any]
    resolve_policy_profile: Callable[..., Any]
    resolve_prompt_profile: Callable[..., Any]
    resolve_tool_profile: Callable[..., Any]
    workflow_get_job: Callable[..., Awaitable[Any]]
    workflow_register_and_mark_case_built: Callable[..., Awaitable[Any]]
    serialize_workflow_job: Callable[[Any], dict[str, Any]]
    extract_dispatch_meta_from_raw: Callable[..., dict[str, Any]]
    extract_receipt_dims_from_raw: Callable[..., dict[str, Any]]
    workflow_register_and_mark_blinded: Callable[..., Awaitable[Any]]
    invoke_phase_failed_callback_with_retry: Callable[..., Awaitable[dict[str, Any]]]
    invoke_final_failed_callback_with_retry: Callable[..., Awaitable[dict[str, Any]]]
    persist_dispatch_receipt: Callable[..., Awaitable[None]]
    workflow_mark_failed: Callable[..., Awaitable[None]]
    build_phase_report_payload: Callable[..., Awaitable[dict[str, Any]]]
    build_final_report_payload: Callable[..., dict[str, Any]]
    attach_judge_agent_runtime_trace: Callable[..., Awaitable[None]]
    attach_policy_trace_snapshot: Callable[..., None]
    upsert_claim_ledger_record: Callable[..., Awaitable[Any]]
    invoke_callback_with_retry: Callable[..., Awaitable[None]]
    workflow_mark_completed: Callable[..., Awaitable[None]]
    workflow_mark_review_required: Callable[..., Awaitable[None]]
    list_dispatch_receipts: Callable[..., Awaitable[list[Any]]]
    resolve_panel_runtime_profiles: Callable[..., dict[str, dict[str, Any]]]
    sync_audit_alert_to_facts: Callable[..., Awaitable[Any]]
    get_dispatch_receipt: Callable[..., Awaitable[Any | None]]
    build_dispatch_receipt_payload: Callable[..., Awaitable[dict[str, Any]]]
    validate_final_report_payload_contract: Callable[..., None]
    validate_phase_dispatch_request: Callable[..., None]
    validate_final_dispatch_request: Callable[..., None]


def register_judge_command_routes(
    *,
    app: FastAPI,
    deps: JudgeCommandRouteDependencies,
) -> None:
    runtime = deps.runtime
    trace_write = runtime.trace_store_boundaries.write_store
    audit_alert_store = runtime.trace_store_boundaries.audit_alert_store

    @app.post("/internal/judge/cases")
    async def create_judge_case(
        request: Request,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        raw_payload = await deps.read_json_object_or_raise_422(request=request)
        return await deps.run_judge_command_route_guard(
            build_case_create_route_payload_v3(
                raw_payload=raw_payload,
                case_create_model_validate=CaseCreateRequest.model_validate,
                resolve_idempotency_or_raise=deps.resolve_idempotency_or_raise,
                ensure_registry_runtime_ready=deps.ensure_registry_runtime_ready,
                resolve_policy_profile=deps.resolve_policy_profile,
                resolve_prompt_profile=deps.resolve_prompt_profile,
                resolve_tool_profile=deps.resolve_tool_profile,
                workflow_get_job=deps.workflow_get_job,
                build_workflow_job=build_workflow_job_v3,
                workflow_register_and_mark_case_built=(
                    deps.workflow_register_and_mark_case_built
                ),
                serialize_workflow_job=deps.serialize_workflow_job,
                trace_register_start=trace_write.register_start,
                trace_register_success=trace_write.register_success,
                build_trace_report_summary=build_trace_report_summary_v3,
                set_idempotency_success=trace_write.set_idempotency_success,
                idempotency_ttl_secs=runtime.settings.idempotency_ttl_secs,
            )
        )

    @app.post("/internal/judge/v3/phase/dispatch")
    async def dispatch_judge_phase(
        request: Request,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        raw_payload = await deps.read_json_object_or_raise_422(request=request)
        sensitive_hits = find_sensitive_key_hits_v3(raw_payload)
        if sensitive_hits:
            await deps.run_judge_command_route_guard(
                build_blindization_rejection_route_payload_v3(
                    dispatch_type="phase",
                    raw_payload=raw_payload,
                    sensitive_hits=sensitive_hits,
                    extract_dispatch_meta_from_raw=deps.extract_dispatch_meta_from_raw,
                    extract_receipt_dims_from_raw=deps.extract_receipt_dims_from_raw,
                    build_workflow_job=build_workflow_job_v3,
                    trace_register_start=trace_write.register_start,
                    workflow_register_and_mark_blinded=(
                        deps.workflow_register_and_mark_blinded
                    ),
                    build_failed_callback_payload=build_failed_callback_payload_v3,
                    invoke_failed_callback_with_retry=(
                        deps.invoke_phase_failed_callback_with_retry
                    ),
                    with_error_contract=with_error_contract_v3,
                    persist_dispatch_receipt=deps.persist_dispatch_receipt,
                    trace_register_failure=trace_write.register_failure,
                    workflow_mark_failed=deps.workflow_mark_failed,
                )
            )
        preflight = await deps.run_judge_command_route_guard(
            build_phase_dispatch_preflight_route_payload_v3(
                raw_payload=raw_payload,
                phase_dispatch_model_validate=PhaseDispatchRequest.model_validate,
                validate_phase_dispatch_request=deps.validate_phase_dispatch_request,
                resolve_idempotency_or_raise=deps.resolve_idempotency_or_raise,
                ensure_registry_runtime_ready=deps.ensure_registry_runtime_ready,
                resolve_policy_profile=deps.resolve_policy_profile,
                resolve_prompt_profile=deps.resolve_prompt_profile,
                resolve_tool_profile=deps.resolve_tool_profile,
                build_phase_dispatch_accepted_response=(
                    build_phase_dispatch_accepted_response_v3
                ),
                build_workflow_job=build_workflow_job_v3,
                trace_register_start=trace_write.register_start,
                persist_dispatch_receipt=deps.persist_dispatch_receipt,
                workflow_register_and_mark_blinded=(
                    deps.workflow_register_and_mark_blinded
                ),
                build_phase_workflow_register_payload=(
                    build_phase_workflow_register_payload_v3
                ),
            )
        )
        replayed_response = preflight.get("replayedResponse")
        if isinstance(replayed_response, dict):
            return replayed_response
        parsed = cast(PhaseDispatchRequest, preflight["parsed"])
        response = cast(dict[str, Any], preflight["response"])
        request_payload = cast(dict[str, Any], preflight["requestPayload"])
        policy_profile = preflight["policyProfile"]
        prompt_profile = preflight["promptProfile"]
        tool_profile = preflight["toolProfile"]

        report_materialization = await deps.run_judge_command_route_guard(
            build_phase_dispatch_report_materialization_route_payload_v3(
                parsed=parsed,
                request_payload=request_payload,
                policy_profile=policy_profile,
                prompt_profile=prompt_profile,
                tool_profile=tool_profile,
                build_phase_report_payload=deps.build_phase_report_payload,
                attach_judge_agent_runtime_trace=deps.attach_judge_agent_runtime_trace,
                attach_policy_trace_snapshot=deps.attach_policy_trace_snapshot,
                attach_report_attestation=attach_report_attestation_v3,
                upsert_claim_ledger_record=deps.upsert_claim_ledger_record,
                build_phase_judge_workflow_payload=(
                    build_phase_judge_workflow_payload_v3
                ),
            )
        )
        phase_report_payload = cast(dict[str, Any], report_materialization["reportPayload"])
        phase_judge_workflow_payload = cast(
            dict[str, Any],
            report_materialization["phaseJudgeWorkflowPayload"],
        )
        phase_callback_outcome = await deps.run_judge_command_route_guard(
            build_phase_dispatch_callback_delivery_route_payload_v3(
                parsed=parsed,
                report_payload=phase_report_payload,
                deliver_report_callback_with_failed_fallback=(
                    deliver_report_callback_with_failed_fallback_v3
                ),
                report_callback_fn=cast(
                    CallbackReportFn,
                    resolve_report_callback_fn_for_dispatch_v3(
                        dispatch_type="phase",
                        callback_phase_report_fn=runtime.callback_phase_report_fn,
                        callback_final_report_fn=runtime.callback_final_report_fn,
                    ),
                ),
                failed_callback_fn=cast(
                    CallbackReportFn,
                    resolve_failed_callback_fn_for_dispatch_v3(
                        dispatch_type="phase",
                        callback_phase_failed_fn=runtime.callback_phase_failed_fn,
                        callback_final_failed_fn=runtime.callback_final_failed_fn,
                    ),
                ),
                invoke_with_retry=deps.invoke_callback_with_retry,
                build_failed_callback_payload=build_failed_callback_payload_v3,
            )
        )

        return await deps.run_judge_command_route_guard(
            build_phase_dispatch_callback_result_route_payload_v3(
                parsed=parsed,
                response=response,
                request_payload=request_payload,
                report_payload=phase_report_payload,
                callback_outcome=phase_callback_outcome,
                callback_status_reported=CALLBACK_STATUS_REPORTED_V3,
                callback_status_failed_reported=CALLBACK_STATUS_FAILED_REPORTED_V3,
                callback_status_failed_callback_failed=(
                    CALLBACK_STATUS_FAILED_CALLBACK_FAILED_V3
                ),
                with_error_contract=with_error_contract_v3,
                persist_dispatch_receipt=deps.persist_dispatch_receipt,
                trace_register_failure=trace_write.register_failure,
                trace_register_success=trace_write.register_success,
                workflow_mark_failed=deps.workflow_mark_failed,
                workflow_mark_completed=deps.workflow_mark_completed,
                build_phase_workflow_reported_payload=(
                    build_phase_workflow_reported_payload_v3
                ),
                build_trace_report_summary=build_trace_report_summary_v3,
                clear_idempotency=trace_write.clear_idempotency,
                set_idempotency_success=trace_write.set_idempotency_success,
                idempotency_ttl_secs=runtime.settings.idempotency_ttl_secs,
                phase_judge_workflow_payload=phase_judge_workflow_payload,
            )
        )

    @app.post("/internal/judge/v3/final/dispatch")
    async def dispatch_judge_final(
        request: Request,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        raw_payload = await deps.read_json_object_or_raise_422(request=request)
        sensitive_hits = find_sensitive_key_hits_v3(raw_payload)
        if sensitive_hits:
            await deps.run_judge_command_route_guard(
                build_blindization_rejection_route_payload_v3(
                    dispatch_type="final",
                    raw_payload=raw_payload,
                    sensitive_hits=sensitive_hits,
                    extract_dispatch_meta_from_raw=deps.extract_dispatch_meta_from_raw,
                    extract_receipt_dims_from_raw=deps.extract_receipt_dims_from_raw,
                    build_workflow_job=build_workflow_job_v3,
                    trace_register_start=trace_write.register_start,
                    workflow_register_and_mark_blinded=(
                        deps.workflow_register_and_mark_blinded
                    ),
                    build_failed_callback_payload=build_failed_callback_payload_v3,
                    invoke_failed_callback_with_retry=(
                        deps.invoke_final_failed_callback_with_retry
                    ),
                    with_error_contract=with_error_contract_v3,
                    persist_dispatch_receipt=deps.persist_dispatch_receipt,
                    trace_register_failure=trace_write.register_failure,
                    workflow_mark_failed=deps.workflow_mark_failed,
                )
            )
        preflight = await deps.run_judge_command_route_guard(
            build_final_dispatch_preflight_route_payload_v3(
                raw_payload=raw_payload,
                final_dispatch_model_validate=FinalDispatchRequest.model_validate,
                validate_final_dispatch_request=deps.validate_final_dispatch_request,
                resolve_idempotency_or_raise=deps.resolve_idempotency_or_raise,
                ensure_registry_runtime_ready=deps.ensure_registry_runtime_ready,
                resolve_policy_profile=deps.resolve_policy_profile,
                resolve_prompt_profile=deps.resolve_prompt_profile,
                resolve_tool_profile=deps.resolve_tool_profile,
                build_final_dispatch_accepted_response=(
                    build_final_dispatch_accepted_response_v3
                ),
                build_workflow_job=build_workflow_job_v3,
                trace_register_start=trace_write.register_start,
                persist_dispatch_receipt=deps.persist_dispatch_receipt,
                workflow_register_and_mark_blinded=(
                    deps.workflow_register_and_mark_blinded
                ),
                build_final_workflow_register_payload=(
                    build_final_workflow_register_payload_v3
                ),
            )
        )
        replayed_response = preflight.get("replayedResponse")
        if isinstance(replayed_response, dict):
            return replayed_response
        parsed = cast(FinalDispatchRequest, preflight["parsed"])
        response = cast(dict[str, Any], preflight["response"])
        request_payload = cast(dict[str, Any], preflight["requestPayload"])
        policy_profile = preflight["policyProfile"]
        prompt_profile = preflight["promptProfile"]
        tool_profile = preflight["toolProfile"]

        report_materialization = await deps.run_judge_command_route_guard(
            build_final_dispatch_report_materialization_route_payload_v3(
                parsed=parsed,
                request_payload=request_payload,
                policy_profile=policy_profile,
                prompt_profile=prompt_profile,
                tool_profile=tool_profile,
                list_dispatch_receipts=deps.list_dispatch_receipts,
                build_final_report_payload=deps.build_final_report_payload,
                resolve_panel_runtime_profiles=deps.resolve_panel_runtime_profiles,
                attach_judge_agent_runtime_trace=deps.attach_judge_agent_runtime_trace,
                attach_policy_trace_snapshot=deps.attach_policy_trace_snapshot,
                attach_report_attestation=attach_report_attestation_v3,
                upsert_claim_ledger_record=deps.upsert_claim_ledger_record,
                build_final_judge_workflow_payload=(
                    build_final_judge_workflow_payload_v3
                ),
                validate_final_report_payload_contract=(
                    deps.validate_final_report_payload_contract
                ),
            )
        )
        final_report_payload = cast(dict[str, Any], report_materialization["reportPayload"])
        final_judge_workflow_payload = cast(
            dict[str, Any],
            report_materialization["finalJudgeWorkflowPayload"],
        )
        contract_missing_fields = cast(
            list[str],
            report_materialization["contractMissingFields"],
        )
        if contract_missing_fields:
            await deps.run_judge_command_route_guard(
                build_final_contract_blocked_route_payload_v3(
                    parsed=parsed,
                    response=response,
                    request_payload=request_payload,
                    report_payload=final_report_payload,
                    contract_missing_fields=contract_missing_fields,
                    upsert_audit_alert=audit_alert_store.upsert_alert,
                    sync_audit_alert_to_facts=deps.sync_audit_alert_to_facts,
                    build_failed_callback_payload=build_failed_callback_payload_v3,
                    invoke_failed_callback_with_retry=(
                        deps.invoke_final_failed_callback_with_retry
                    ),
                    with_error_contract=with_error_contract_v3,
                    persist_dispatch_receipt=deps.persist_dispatch_receipt,
                    trace_register_failure=trace_write.register_failure,
                    workflow_mark_failed=deps.workflow_mark_failed,
                    clear_idempotency=trace_write.clear_idempotency,
                )
            )

        final_callback_outcome = await deps.run_judge_command_route_guard(
            build_final_dispatch_callback_delivery_route_payload_v3(
                parsed=parsed,
                report_payload=final_report_payload,
                deliver_report_callback_with_failed_fallback=(
                    deliver_report_callback_with_failed_fallback_v3
                ),
                report_callback_fn=cast(
                    CallbackReportFn,
                    resolve_report_callback_fn_for_dispatch_v3(
                        dispatch_type="final",
                        callback_phase_report_fn=runtime.callback_phase_report_fn,
                        callback_final_report_fn=runtime.callback_final_report_fn,
                    ),
                ),
                failed_callback_fn=cast(
                    CallbackReportFn,
                    resolve_failed_callback_fn_for_dispatch_v3(
                        dispatch_type="final",
                        callback_phase_failed_fn=runtime.callback_phase_failed_fn,
                        callback_final_failed_fn=runtime.callback_final_failed_fn,
                    ),
                ),
                invoke_with_retry=deps.invoke_callback_with_retry,
                build_failed_callback_payload=build_failed_callback_payload_v3,
            )
        )

        return await deps.run_judge_command_route_guard(
            build_final_dispatch_callback_result_route_payload_v3(
                parsed=parsed,
                response=response,
                request_payload=request_payload,
                report_payload=final_report_payload,
                callback_outcome=final_callback_outcome,
                callback_status_reported=CALLBACK_STATUS_REPORTED_V3,
                callback_status_failed_reported=CALLBACK_STATUS_FAILED_REPORTED_V3,
                callback_status_failed_callback_failed=(
                    CALLBACK_STATUS_FAILED_CALLBACK_FAILED_V3
                ),
                with_error_contract=with_error_contract_v3,
                persist_dispatch_receipt=deps.persist_dispatch_receipt,
                trace_register_failure=trace_write.register_failure,
                trace_register_success=trace_write.register_success,
                workflow_mark_failed=deps.workflow_mark_failed,
                workflow_mark_review_required=deps.workflow_mark_review_required,
                workflow_mark_completed=deps.workflow_mark_completed,
                build_final_workflow_reported_payload=(
                    build_final_workflow_reported_payload_v3
                ),
                build_trace_report_summary=build_trace_report_summary_v3,
                clear_idempotency=trace_write.clear_idempotency,
                set_idempotency_success=trace_write.set_idempotency_success,
                idempotency_ttl_secs=runtime.settings.idempotency_ttl_secs,
                final_judge_workflow_payload=final_judge_workflow_payload,
            )
        )

    @app.get("/internal/judge/v3/phase/cases/{case_id}/receipt")
    async def get_phase_dispatch_receipt(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.build_dispatch_receipt_payload(
            case_id=case_id,
            dispatch_type="phase",
            not_found_detail="phase_dispatch_receipt_not_found",
            get_dispatch_receipt=deps.get_dispatch_receipt,
        )

    @app.get("/internal/judge/v3/final/cases/{case_id}/receipt")
    async def get_final_dispatch_receipt(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.build_dispatch_receipt_payload(
            case_id=case_id,
            dispatch_type="final",
            not_found_detail="final_dispatch_receipt_not_found",
            get_dispatch_receipt=deps.get_dispatch_receipt,
        )
