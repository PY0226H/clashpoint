from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Any, Awaitable, Callable

from .route_group_ops_read_model_pack import OpsReadModelPackRouteDependencies
from .route_group_trust import TrustRouteDependencies
from .trust_attestation import verify_report_attestation
from .trust_audit_anchor_contract import validate_trust_audit_anchor_contract
from .trust_challenge_public_contract import validate_trust_challenge_public_contract
from .trust_challenge_review_contract import validate_trust_challenge_review_contract
from .trust_commitment_contract import validate_trust_commitment_contract
from .trust_kernel_version_contract import validate_trust_kernel_version_contract
from .trust_ops_views import build_public_trust_verify_payload
from .trust_phasea import build_audit_anchor_export
from .trust_public_verify_contract import validate_trust_public_verify_contract
from .trust_read_routes import write_trust_registry_snapshot_for_report
from .trust_verdict_attestation_contract import validate_trust_verdict_attestation_contract


@dataclass(frozen=True)
class TrustRuntimeDependencyPack:
    get_trust_registry_snapshot: Callable[..., Awaitable[Any | None]]
    write_trust_registry_snapshot: Callable[..., Awaitable[Any]]
    resolve_report_context_for_case: Callable[..., Awaitable[dict[str, Any]]]
    build_trust_phasea_bundle: Callable[..., Awaitable[dict[str, Any]]]
    refresh_trust_registry_snapshot_for_case: Callable[..., Awaitable[Any]]


def build_trust_runtime_dependency_pack_for_runtime(
    *,
    runtime: Any,
    get_dispatch_receipt: Callable[..., Awaitable[Any | None]],
    workflow_get_job: Callable[..., Awaitable[Any | None]],
    workflow_list_events: Callable[..., Awaitable[list[Any]]],
    list_audit_alerts: Callable[..., Awaitable[list[Any]]],
    serialize_workflow_job: Callable[[Any], dict[str, Any]],
    run_trust_read_guard: Callable[[Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]],
    resolve_report_context_for_case: Callable[..., Awaitable[dict[str, Any]]],
    build_trust_phasea_bundle_for_runtime: Callable[..., Awaitable[dict[str, Any]]],
) -> TrustRuntimeDependencyPack:
    get_trust_registry_snapshot = (
        runtime.workflow_runtime.trust_registry.get_trust_registry_snapshot
    )
    write_trust_registry_snapshot = partial(
        write_trust_registry_snapshot_for_report,
        provider=runtime.settings.provider,
        upsert_trust_registry_snapshot=(
            runtime.workflow_runtime.trust_registry.upsert_trust_registry_snapshot
        ),
        build_audit_anchor_export=build_audit_anchor_export,
        build_public_verify_payload=build_public_trust_verify_payload,
        artifact_store=runtime.trace_store_boundaries.artifact_store,
    )

    resolve_context = partial(
        resolve_report_context_for_case,
        get_dispatch_receipt=get_dispatch_receipt,
        run_trust_read_guard=run_trust_read_guard,
    )
    build_phasea_bundle = partial(
        build_trust_phasea_bundle_for_runtime,
        get_dispatch_receipt=get_dispatch_receipt,
        get_workflow_job=workflow_get_job,
        list_workflow_events=workflow_list_events,
        list_audit_alerts=list_audit_alerts,
        serialize_workflow_job=serialize_workflow_job,
        provider=runtime.settings.provider,
        run_trust_read_guard=run_trust_read_guard,
        get_trust_registry_snapshot=get_trust_registry_snapshot,
    )

    async def refresh_trust_registry_snapshot_for_case(
        *,
        case_id: int,
        dispatch_type: str,
    ) -> Any:
        context = await resolve_context(
            case_id=case_id,
            dispatch_type=dispatch_type,
            not_found_detail="trust_receipt_not_found",
            missing_report_detail="trust_report_payload_missing",
        )
        workflow_job = await workflow_get_job(job_id=case_id)
        workflow_events = await workflow_list_events(job_id=case_id)
        alerts = await list_audit_alerts(job_id=case_id, status=None, limit=200)
        workflow_snapshot = (
            serialize_workflow_job(workflow_job) if workflow_job is not None else None
        )
        return await write_trust_registry_snapshot(
            case_id=case_id,
            dispatch_type=context["dispatchType"],
            trace_id=context["traceId"],
            request_snapshot=context["requestSnapshot"],
            report_payload=context["reportPayload"],
            workflow_snapshot=workflow_snapshot,
            workflow_status=workflow_job.status if workflow_job is not None else None,
            workflow_events=workflow_events,
            alerts=alerts,
        )

    return TrustRuntimeDependencyPack(
        get_trust_registry_snapshot=get_trust_registry_snapshot,
        write_trust_registry_snapshot=write_trust_registry_snapshot,
        resolve_report_context_for_case=resolve_context,
        build_trust_phasea_bundle=build_phasea_bundle,
        refresh_trust_registry_snapshot_for_case=refresh_trust_registry_snapshot_for_case,
    )


def build_trust_route_dependencies_for_runtime(
    *,
    runtime: Any,
    require_internal_key_fn: Callable[[Any, str | None], None],
    build_validated_trust_item_payload: Callable[..., Awaitable[dict[str, Any]]],
    build_trust_challenge_ops_queue_payload: Callable[..., Awaitable[dict[str, Any]]],
    build_trust_challenge_public_status_payload: Callable[
        ...,
        Awaitable[dict[str, Any]],
    ],
    build_trust_challenge_request_payload: Callable[..., Awaitable[dict[str, Any]]],
    build_trust_challenge_decision_payload: Callable[..., Awaitable[dict[str, Any]]],
    build_trust_audit_anchor_payload: Callable[..., Awaitable[dict[str, Any]]],
    build_trust_public_verify_payload: Callable[..., Awaitable[dict[str, Any]]],
    run_trust_read_guard: Callable[[Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]],
    build_trust_phasea_bundle: Callable[..., Awaitable[dict[str, Any]]],
    get_dispatch_receipt: Callable[..., Awaitable[Any | None]],
    workflow_list_jobs: Callable[..., Awaitable[list[Any]]],
    get_trace: Callable[..., Any],
    build_trust_challenge_priority_profile: Callable[..., dict[str, Any]],
    serialize_workflow_job: Callable[[Any], dict[str, Any]],
    build_trust_challenge_action_hints: Callable[..., dict[str, Any]],
    run_trust_challenge_guard: Callable[
        [Awaitable[dict[str, Any]]],
        Awaitable[dict[str, Any]],
    ],
    trust_challenge_common_dependencies: dict[str, Any],
    upsert_audit_alert: Callable[..., Any],
    sync_audit_alert_to_facts: Callable[..., Awaitable[Any]],
    workflow_mark_completed: Callable[..., Awaitable[None]],
    workflow_mark_draw_pending_vote: Callable[..., Awaitable[Any]],
    resolve_open_alerts_for_review: Callable[..., Awaitable[list[Any]]],
) -> TrustRouteDependencies:
    return TrustRouteDependencies(
        runtime=runtime,
        require_internal_key_fn=require_internal_key_fn,
        build_validated_trust_item_payload=build_validated_trust_item_payload,
        build_trust_challenge_ops_queue_payload=build_trust_challenge_ops_queue_payload,
        build_trust_challenge_public_status_payload=(
            build_trust_challenge_public_status_payload
        ),
        build_trust_challenge_request_payload=build_trust_challenge_request_payload,
        build_trust_challenge_decision_payload=build_trust_challenge_decision_payload,
        build_trust_audit_anchor_payload=build_trust_audit_anchor_payload,
        build_trust_public_verify_payload=build_trust_public_verify_payload,
        run_trust_read_guard=run_trust_read_guard,
        build_trust_phasea_bundle=build_trust_phasea_bundle,
        build_audit_anchor_export=build_audit_anchor_export,
        build_public_verify_payload=build_public_trust_verify_payload,
        verify_report_attestation=verify_report_attestation,
        get_dispatch_receipt=get_dispatch_receipt,
        workflow_list_jobs=workflow_list_jobs,
        get_trace=get_trace,
        build_trust_challenge_priority_profile=build_trust_challenge_priority_profile,
        serialize_workflow_job=serialize_workflow_job,
        build_trust_challenge_action_hints=build_trust_challenge_action_hints,
        run_trust_challenge_guard=run_trust_challenge_guard,
        trust_challenge_common_dependencies=trust_challenge_common_dependencies,
        upsert_audit_alert=upsert_audit_alert,
        sync_audit_alert_to_facts=sync_audit_alert_to_facts,
        workflow_mark_completed=workflow_mark_completed,
        workflow_mark_draw_pending_vote=workflow_mark_draw_pending_vote,
        resolve_open_alerts_for_review=resolve_open_alerts_for_review,
        validate_trust_commitment_contract=validate_trust_commitment_contract,
        validate_trust_verdict_attestation_contract=(
            validate_trust_verdict_attestation_contract
        ),
        validate_trust_challenge_review_contract=(
            validate_trust_challenge_review_contract
        ),
        validate_trust_challenge_public_contract=(
            validate_trust_challenge_public_contract
        ),
        validate_trust_kernel_version_contract=validate_trust_kernel_version_contract,
        validate_trust_audit_anchor_contract=validate_trust_audit_anchor_contract,
        validate_trust_public_verify_contract=validate_trust_public_verify_contract,
    )


def build_ops_read_model_pack_route_dependencies_for_runtime(
    *,
    runtime: Any,
    require_internal_key_fn: Callable[[Any, str | None], None],
    await_payload_or_raise_http_500: Callable[..., Awaitable[dict[str, Any]]],
    build_ops_read_model_pack_payload: Callable[..., Awaitable[dict[str, Any]]],
    fairness_route_handles: Any,
    registry_route_handles: Any,
    panel_runtime_route_handles: Any,
    case_read_route_handles: Any,
    trust_route_handles: Any,
    review_route_handles: Any,
) -> OpsReadModelPackRouteDependencies:
    return OpsReadModelPackRouteDependencies(
        runtime=runtime,
        require_internal_key_fn=require_internal_key_fn,
        await_payload_or_raise_http_500=await_payload_or_raise_http_500,
        build_ops_read_model_pack_payload=build_ops_read_model_pack_payload,
        get_judge_fairness_dashboard=(
            fairness_route_handles.get_judge_fairness_dashboard
        ),
        get_registry_governance_overview=(
            registry_route_handles.get_registry_governance_overview
        ),
        get_registry_prompt_tool_governance=(
            registry_route_handles.get_registry_prompt_tool_governance
        ),
        get_policy_registry_dependency_health=(
            registry_route_handles.get_policy_registry_dependency_health
        ),
        get_judge_fairness_policy_calibration_advisor=(
            fairness_route_handles.get_judge_fairness_policy_calibration_advisor
        ),
        get_panel_runtime_readiness=(
            panel_runtime_route_handles.get_panel_runtime_readiness
        ),
        list_judge_courtroom_cases=case_read_route_handles.list_judge_courtroom_cases,
        list_judge_courtroom_drilldown_bundle=(
            case_read_route_handles.list_judge_courtroom_drilldown_bundle
        ),
        list_judge_evidence_claim_ops_queue=(
            case_read_route_handles.list_judge_evidence_claim_ops_queue
        ),
        list_judge_trust_challenge_ops_queue=(
            trust_route_handles.list_judge_trust_challenge_ops_queue
        ),
        list_judge_review_jobs=review_route_handles.list_judge_review_jobs,
        simulate_policy_release_gate=registry_route_handles.simulate_policy_release_gate,
        get_judge_case_courtroom_read_model=(
            case_read_route_handles.get_judge_case_courtroom_read_model
        ),
        get_judge_trust_public_verify=trust_route_handles.get_judge_trust_public_verify,
    )
