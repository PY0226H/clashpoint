from __future__ import annotations

from typing import Any, Awaitable, Callable, cast

from fastapi import HTTPException

from .bootstrap_review_trust_helpers import build_trust_challenge_id_for_runtime
from .registry_ops_views import (
    build_registry_alert_ops_view as build_registry_alert_ops_view_v3,
)
from .registry_ops_views import (
    normalize_ops_alert_delivery_status as normalize_ops_alert_delivery_status_v3,
)
from .registry_ops_views import (
    normalize_ops_alert_fields_mode as normalize_ops_alert_fields_mode_v3,
)
from .registry_ops_views import (
    normalize_ops_alert_status as normalize_ops_alert_status_v3,
)
from .review_alert_routes import (
    build_alert_ops_view_payload as build_alert_ops_view_payload_v3,
)
from .review_alert_routes import (
    build_alert_outbox_route_payload as build_alert_outbox_route_payload_v3,
)
from .review_alert_routes import (
    build_alert_status_transition_payload as build_alert_status_transition_payload_v3,
)
from .review_alert_routes import (
    build_case_alerts_payload as build_case_alerts_payload_v3,
)
from .review_alert_routes import (
    build_review_case_detail_payload as build_review_case_detail_payload_v3,
)
from .review_alert_routes import (
    build_review_case_sort_key as build_review_case_sort_key_v3,
)
from .review_alert_routes import (
    build_review_cases_list_payload as build_review_cases_list_payload_v3,
)
from .review_alert_routes import (
    normalize_review_case_filters as normalize_review_case_filters_v3,
)
from .review_alert_routes import (
    normalize_review_case_risk_level as normalize_review_case_risk_level_v3,
)
from .review_alert_routes import (
    normalize_review_case_sla_bucket as normalize_review_case_sla_bucket_v3,
)
from .review_alert_routes import (
    normalize_review_case_sort_by as normalize_review_case_sort_by_v3,
)
from .review_alert_routes import (
    normalize_review_case_sort_order as normalize_review_case_sort_order_v3,
)
from .trust_challenge_ops_queue_routes import (
    build_trust_challenge_ops_queue_route_payload as build_trust_challenge_ops_queue_route_payload_v3,
)
from .trust_challenge_queue_contract import (
    validate_trust_challenge_queue_contract as validate_trust_challenge_queue_contract_v3,
)
from .trust_challenge_runtime_routes import (
    build_trust_challenge_decision_payload as build_trust_challenge_decision_payload_v3,
)
from .trust_challenge_runtime_routes import (
    build_trust_challenge_public_status_payload as build_trust_challenge_public_status_payload_v3,
)
from .trust_challenge_runtime_routes import (
    build_trust_challenge_request_payload as build_trust_challenge_request_payload_v3,
)
from .trust_ops_views import (
    build_trust_challenge_ops_queue_item as build_trust_challenge_ops_queue_item_v3,
)
from .trust_ops_views import (
    build_trust_challenge_ops_queue_payload as build_trust_challenge_ops_queue_payload_v3,
)
from .trust_ops_views import (
    build_trust_challenge_sort_key as build_trust_challenge_sort_key_v3,
)
from .trust_ops_views import (
    normalize_trust_challenge_priority_level as normalize_trust_challenge_priority_level_v3,
)
from .trust_ops_views import (
    normalize_trust_challenge_review_state as normalize_trust_challenge_review_state_v3,
)
from .trust_ops_views import (
    normalize_trust_challenge_sla_bucket as normalize_trust_challenge_sla_bucket_v3,
)
from .trust_ops_views import (
    normalize_trust_challenge_sort_by as normalize_trust_challenge_sort_by_v3,
)
from .trust_ops_views import (
    normalize_trust_challenge_sort_order as normalize_trust_challenge_sort_order_v3,
)
from .trust_ops_views import (
    normalize_trust_challenge_state_filter as normalize_trust_challenge_state_filter_v3,
)
from .trust_phasea import (
    build_challenge_review_registry as build_challenge_review_registry_v3,
)
from .trust_read_routes import TrustReadRouteError as TrustReadRouteError_v3
from .trust_read_routes import (
    build_trust_audit_anchor_route_payload as build_trust_audit_anchor_route_payload_v3,
)
from .trust_read_routes import (
    build_trust_phasea_bundle_for_case as build_trust_phasea_bundle_for_case_v3,
)
from .trust_read_routes import (
    build_trust_public_verify_bundle_payload as build_trust_public_verify_bundle_payload_v3,
)
from .trust_read_routes import (
    build_validated_trust_item_route_payload as build_validated_trust_item_route_payload_v3,
)
from .trust_read_routes import (
    resolve_trust_report_context_for_case as resolve_trust_report_context_for_case_v3,
)


def _run_trust_read_guard_sync(
    builder: Callable[..., dict[str, Any]],
    **kwargs: Any,
) -> dict[str, Any]:
    try:
        return builder(**kwargs)
    except TrustReadRouteError_v3 as err:
        raise HTTPException(status_code=err.status_code, detail=err.detail) from err


async def transition_judge_alert_status_for_runtime(
    *,
    case_id: int,
    alert_id: str,
    to_status: str,
    actor: str | None,
    reason: str | None,
    transition_audit_alert: Callable[..., Any],
    sync_audit_alert_to_facts: Callable[..., Awaitable[Any]],
    facts_transition_audit_alert: Callable[..., Awaitable[Any]],
    serialize_alert_item: Callable[[Any], dict[str, Any]],
    run_review_route_guard: Callable[[Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    return await run_review_route_guard(
        build_alert_status_transition_payload_v3(
            job_id=case_id,
            alert_id=alert_id,
            to_status=to_status,
            actor=actor,
            reason=reason,
            transition_audit_alert=transition_audit_alert,
            sync_audit_alert_to_facts=sync_audit_alert_to_facts,
            facts_transition_audit_alert=facts_transition_audit_alert,
            serialize_alert_item=serialize_alert_item,
        )
    )


async def resolve_report_context_for_case_for_runtime(
    *,
    case_id: int,
    dispatch_type: str,
    not_found_detail: str,
    missing_report_detail: str,
    get_dispatch_receipt: Callable[..., Awaitable[Any | None]],
    run_trust_read_guard: Callable[[Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    return await run_trust_read_guard(
        resolve_trust_report_context_for_case_v3(
            case_id=case_id,
            dispatch_type=dispatch_type,
            get_dispatch_receipt=get_dispatch_receipt,
            not_found_detail=not_found_detail,
            missing_report_detail=missing_report_detail,
        )
    )


async def build_trust_phasea_bundle_for_runtime(
    *,
    case_id: int,
    dispatch_type: str,
    get_dispatch_receipt: Callable[..., Awaitable[Any | None]],
    get_workflow_job: Callable[..., Awaitable[Any | None]],
    list_workflow_events: Callable[..., Awaitable[list[Any]]],
    list_audit_alerts: Callable[..., Awaitable[list[Any]]],
    serialize_workflow_job: Callable[[Any], dict[str, Any]],
    provider: str,
    run_trust_read_guard: Callable[[Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]],
    get_trust_registry_snapshot: Callable[..., Awaitable[Any | None]] | None = None,
) -> dict[str, Any]:
    return await run_trust_read_guard(
        build_trust_phasea_bundle_for_case_v3(
            case_id=case_id,
            dispatch_type=dispatch_type,
            get_dispatch_receipt=get_dispatch_receipt,
            get_workflow_job=get_workflow_job,
            list_workflow_events=list_workflow_events,
            list_audit_alerts=list_audit_alerts,
            serialize_workflow_job=serialize_workflow_job,
            provider=provider,
            get_trust_registry_snapshot=get_trust_registry_snapshot,
        )
    )


async def build_review_cases_list_payload_for_runtime(
    *,
    normalize_workflow_status: Callable[[str | None], str],
    workflow_statuses: set[str] | frozenset[str],
    review_case_risk_level_values: set[str] | frozenset[str],
    review_case_sla_bucket_values: set[str] | frozenset[str],
    case_fairness_challenge_states: set[str] | frozenset[str],
    trust_challenge_review_state_values: set[str] | frozenset[str],
    trust_challenge_priority_level_values: set[str] | frozenset[str],
    review_case_sort_fields: set[str] | frozenset[str],
    trust_challenge_open_states: set[str] | frozenset[str],
    status: str,
    dispatch_type: str | None,
    risk_level: str | None,
    sla_bucket: str | None,
    challenge_state: str | None,
    trust_review_state: str | None,
    unified_priority_level: str | None,
    sort_by: str,
    sort_order: str,
    scan_limit: int,
    limit: int,
    workflow_list_jobs: Callable[..., Awaitable[list[Any]]],
    workflow_list_events: Callable[..., Awaitable[list[dict[str, Any]]]],
    list_audit_alerts: Callable[..., Awaitable[list[Any]]],
    get_trace: Callable[[int], dict[str, Any] | None],
    build_review_case_risk_profile: Callable[..., dict[str, Any]],
    build_trust_challenge_priority_profile: Callable[..., dict[str, Any]],
    build_review_trust_unified_priority_profile: Callable[..., dict[str, Any]],
    serialize_workflow_job: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    normalized_filters = normalize_review_case_filters_v3(
        status=status,
        dispatch_type=dispatch_type,
        risk_level=risk_level,
        sla_bucket=sla_bucket,
        challenge_state=challenge_state,
        trust_review_state=trust_review_state,
        unified_priority_level=unified_priority_level,
        sort_by=sort_by,
        sort_order=sort_order,
        scan_limit=scan_limit,
        normalize_workflow_status=normalize_workflow_status,
        workflow_statuses=workflow_statuses,
        normalize_review_case_risk_level=normalize_review_case_risk_level_v3,
        review_case_risk_level_values=review_case_risk_level_values,
        normalize_review_case_sla_bucket=normalize_review_case_sla_bucket_v3,
        review_case_sla_bucket_values=review_case_sla_bucket_values,
        normalize_trust_challenge_state_filter=normalize_trust_challenge_state_filter_v3,
        case_fairness_challenge_states=case_fairness_challenge_states,
        normalize_trust_challenge_review_state=normalize_trust_challenge_review_state_v3,
        trust_challenge_review_state_values=trust_challenge_review_state_values,
        normalize_trust_challenge_priority_level=normalize_trust_challenge_priority_level_v3,
        trust_challenge_priority_level_values=trust_challenge_priority_level_values,
        normalize_review_case_sort_by=normalize_review_case_sort_by_v3,
        review_case_sort_fields=review_case_sort_fields,
        normalize_review_case_sort_order=normalize_review_case_sort_order_v3,
    )
    return await build_review_cases_list_payload_v3(
        normalized_status=str(normalized_filters["status"]),
        normalized_dispatch_type=cast(
            str | None, normalized_filters["dispatchType"]
        ),
        normalized_risk_level=cast(str | None, normalized_filters["riskLevel"]),
        normalized_sla_bucket=cast(str | None, normalized_filters["slaBucket"]),
        normalized_challenge_state=cast(
            str | None, normalized_filters["challengeState"]
        ),
        normalized_trust_review_state=cast(
            str | None, normalized_filters["trustReviewState"]
        ),
        normalized_unified_priority_level=cast(
            str | None, normalized_filters["unifiedPriorityLevel"]
        ),
        normalized_sort_by=str(normalized_filters["sortBy"]),
        normalized_sort_order=str(normalized_filters["sortOrder"]),
        normalized_scan_limit=int(normalized_filters["scanLimit"]),
        limit=limit,
        trust_challenge_open_states=trust_challenge_open_states,
        workflow_list_jobs=workflow_list_jobs,
        get_trace=get_trace,
        workflow_list_events=workflow_list_events,
        list_audit_alerts=list_audit_alerts,
        build_challenge_review_registry=build_challenge_review_registry_v3,
        build_review_case_risk_profile=build_review_case_risk_profile,
        build_trust_challenge_priority_profile=build_trust_challenge_priority_profile,
        build_review_trust_unified_priority_profile=(
            build_review_trust_unified_priority_profile
        ),
        serialize_workflow_job=serialize_workflow_job,
        build_review_case_sort_key=build_review_case_sort_key_v3,
    )


async def build_review_case_detail_payload_for_runtime(
    *,
    case_id: int,
    workflow_get_job: Callable[..., Awaitable[Any | None]],
    workflow_list_events: Callable[..., Awaitable[list[dict[str, Any]]]],
    list_audit_alerts: Callable[..., Awaitable[list[Any]]],
    get_trace: Callable[[int], dict[str, Any] | None],
    serialize_workflow_job: Callable[[Any], dict[str, Any]],
    serialize_alert_item: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    return await build_review_case_detail_payload_v3(
        case_id=case_id,
        workflow_get_job=workflow_get_job,
        workflow_list_events=workflow_list_events,
        list_audit_alerts=list_audit_alerts,
        get_trace=get_trace,
        serialize_workflow_job=serialize_workflow_job,
        serialize_alert_item=serialize_alert_item,
    )


async def build_alert_ops_view_payload_for_runtime(
    *,
    ops_registry_alert_types: set[str] | frozenset[str],
    ops_alert_status_values: set[str] | frozenset[str],
    ops_alert_delivery_status_values: set[str] | frozenset[str],
    ops_alert_fields_mode_values: set[str] | frozenset[str],
    alert_type: str | None,
    status: str | None,
    delivery_status: str | None,
    registry_type: str | None,
    policy_version: str | None,
    gate_code: str | None,
    gate_actor: str | None,
    override_applied: bool | None,
    fields_mode: str,
    include_trend: bool,
    trend_window_minutes: int,
    trend_bucket_minutes: int,
    offset: int,
    limit: int,
    list_audit_alerts: Callable[..., Awaitable[list[Any]]],
    list_alert_outbox: Callable[..., list[Any]],
) -> dict[str, Any]:
    return await build_alert_ops_view_payload_v3(
        alert_type=alert_type,
        status=status,
        delivery_status=delivery_status,
        registry_type=registry_type,
        policy_version=policy_version,
        gate_code=gate_code,
        gate_actor=gate_actor,
        override_applied=override_applied,
        fields_mode=fields_mode,
        include_trend=include_trend,
        trend_window_minutes=trend_window_minutes,
        trend_bucket_minutes=trend_bucket_minutes,
        offset=offset,
        limit=limit,
        normalize_ops_alert_status=normalize_ops_alert_status_v3,
        normalize_ops_alert_delivery_status=normalize_ops_alert_delivery_status_v3,
        normalize_ops_alert_fields_mode=normalize_ops_alert_fields_mode_v3,
        ops_registry_alert_types=ops_registry_alert_types,
        ops_alert_status_values=ops_alert_status_values,
        ops_alert_delivery_status_values=ops_alert_delivery_status_values,
        ops_alert_fields_mode_values=ops_alert_fields_mode_values,
        list_audit_alerts=list_audit_alerts,
        list_alert_outbox=list_alert_outbox,
        build_registry_alert_ops_view=build_registry_alert_ops_view_v3,
    )


async def build_case_alerts_payload_for_runtime(
    *,
    case_id: int,
    status: str | None,
    limit: int,
    list_audit_alerts: Callable[..., Awaitable[list[Any]]],
    serialize_alert_item: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    return await build_case_alerts_payload_v3(
        case_id=case_id,
        status=status,
        limit=limit,
        list_audit_alerts=list_audit_alerts,
        serialize_alert_item=serialize_alert_item,
    )


def build_alert_outbox_payload_for_runtime(
    *,
    delivery_status: str | None,
    limit: int,
    list_alert_outbox: Callable[..., list[Any]],
    serialize_outbox_event: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    return build_alert_outbox_route_payload_v3(
        delivery_status=delivery_status,
        limit=limit,
        list_alert_outbox=list_alert_outbox,
        serialize_outbox_event=serialize_outbox_event,
    )


async def build_trust_challenge_ops_queue_payload_for_runtime(
    *,
    normalize_workflow_status: Callable[[str | None], str],
    workflow_statuses: set[str] | frozenset[str],
    case_fairness_challenge_states: set[str] | frozenset[str],
    trust_challenge_review_state_values: set[str] | frozenset[str],
    trust_challenge_priority_level_values: set[str] | frozenset[str],
    trust_challenge_sla_bucket_values: set[str] | frozenset[str],
    trust_challenge_sort_fields: set[str] | frozenset[str],
    trust_challenge_open_states: set[str] | frozenset[str],
    status: str | None,
    dispatch_type: str,
    challenge_state: str | None,
    review_state: str | None,
    priority_level: str | None,
    sla_bucket: str | None,
    has_open_alert: bool | None,
    sort_by: str,
    sort_order: str,
    scan_limit: int,
    offset: int,
    limit: int,
    workflow_list_jobs: Callable[..., Awaitable[list[Any]]],
    build_trust_phasea_bundle: Callable[..., Awaitable[dict[str, Any]]],
    get_trace: Callable[[int], dict[str, Any] | None],
    build_trust_challenge_priority_profile: Callable[..., dict[str, Any]],
    serialize_workflow_job: Callable[[Any], dict[str, Any]],
    build_trust_challenge_action_hints: Callable[..., dict[str, Any]],
    run_trust_challenge_guard: Callable[
        [Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]
    ],
) -> dict[str, Any]:
    return await run_trust_challenge_guard(
        build_trust_challenge_ops_queue_route_payload_v3(
            status=status,
            dispatch_type=dispatch_type,
            challenge_state=challenge_state,
            review_state=review_state,
            priority_level=priority_level,
            sla_bucket=sla_bucket,
            has_open_alert=has_open_alert,
            sort_by=sort_by,
            sort_order=sort_order,
            scan_limit=scan_limit,
            offset=offset,
            limit=limit,
            normalize_workflow_status=normalize_workflow_status,
            workflow_statuses=workflow_statuses,
            normalize_trust_challenge_state_filter=normalize_trust_challenge_state_filter_v3,
            case_fairness_challenge_states=case_fairness_challenge_states,
            normalize_trust_challenge_review_state=normalize_trust_challenge_review_state_v3,
            trust_challenge_review_state_values=trust_challenge_review_state_values,
            normalize_trust_challenge_priority_level=(
                normalize_trust_challenge_priority_level_v3
            ),
            trust_challenge_priority_level_values=trust_challenge_priority_level_values,
            normalize_trust_challenge_sla_bucket=normalize_trust_challenge_sla_bucket_v3,
            trust_challenge_sla_bucket_values=trust_challenge_sla_bucket_values,
            normalize_trust_challenge_sort_by=normalize_trust_challenge_sort_by_v3,
            trust_challenge_sort_fields=trust_challenge_sort_fields,
            normalize_trust_challenge_sort_order=normalize_trust_challenge_sort_order_v3,
            trust_challenge_open_states=trust_challenge_open_states,
            workflow_list_jobs=workflow_list_jobs,
            build_trust_phasea_bundle=build_trust_phasea_bundle,
            get_trace=get_trace,
            build_trust_challenge_priority_profile=(
                build_trust_challenge_priority_profile
            ),
            serialize_workflow_job=serialize_workflow_job,
            build_trust_challenge_ops_queue_item=build_trust_challenge_ops_queue_item_v3,
            build_trust_challenge_action_hints=build_trust_challenge_action_hints,
            build_trust_challenge_sort_key=build_trust_challenge_sort_key_v3,
            build_trust_challenge_ops_queue_payload=build_trust_challenge_ops_queue_payload_v3,
            validate_trust_challenge_ops_queue_contract=(
                validate_trust_challenge_queue_contract_v3
            ),
        )
    )


async def build_trust_challenge_request_payload_for_runtime(
    *,
    trust_challenge_state_requested: str,
    case_id: int,
    dispatch_type: str,
    reason_code: str,
    reason: str | None,
    requested_by: str | None,
    auto_accept: bool,
    trust_challenge_common_dependencies: dict[str, Any],
    upsert_audit_alert: Callable[..., Any],
    sync_audit_alert_to_facts: Callable[..., Awaitable[Any]],
    run_trust_challenge_guard: Callable[
        [Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]
    ],
) -> dict[str, Any]:
    return await run_trust_challenge_guard(
        build_trust_challenge_request_payload_v3(
            case_id=case_id,
            dispatch_type=dispatch_type,
            reason_code=reason_code,
            reason=reason,
            requested_by=requested_by,
            auto_accept=auto_accept,
            **trust_challenge_common_dependencies,
            new_challenge_id=build_trust_challenge_id_for_runtime,
            upsert_audit_alert=upsert_audit_alert,
            sync_audit_alert_to_facts=sync_audit_alert_to_facts,
            trust_challenge_state_requested=trust_challenge_state_requested,
        )
    )


async def build_trust_challenge_public_status_payload_for_runtime(
    *,
    case_id: int,
    dispatch_type: str,
    trust_challenge_common_dependencies: dict[str, Any],
    run_trust_challenge_guard: Callable[
        [Awaitable[dict[str, Any]]],
        Awaitable[dict[str, Any]],
    ],
) -> dict[str, Any]:
    return await run_trust_challenge_guard(
        build_trust_challenge_public_status_payload_v3(
            case_id=case_id,
            dispatch_type=dispatch_type,
            resolve_report_context_for_case=(
                trust_challenge_common_dependencies["resolve_report_context_for_case"]
            ),
            workflow_get_job=trust_challenge_common_dependencies["workflow_get_job"],
            build_trust_phasea_bundle=(
                trust_challenge_common_dependencies["build_trust_phasea_bundle"]
            ),
        )
    )


async def build_trust_challenge_decision_payload_for_runtime(
    *,
    trust_challenge_state_closed: str,
    trust_challenge_state_verdict_upheld: str,
    trust_challenge_state_verdict_overturned: str,
    trust_challenge_state_draw_after_review: str,
    trust_challenge_state_review_retained: str,
    workflow_transition_error_cls: type[Exception],
    case_id: int,
    challenge_id: str,
    dispatch_type: str,
    decision: str,
    actor: str | None,
    reason: str | None,
    trust_challenge_common_dependencies: dict[str, Any],
    workflow_mark_completed: Callable[..., Awaitable[None]],
    workflow_mark_draw_pending_vote: Callable[..., Awaitable[Any]],
    resolve_open_alerts_for_review: Callable[..., Awaitable[list[str]]],
    run_trust_challenge_guard: Callable[
        [Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]
    ],
) -> dict[str, Any]:
    return await run_trust_challenge_guard(
        build_trust_challenge_decision_payload_v3(
            case_id=case_id,
            challenge_id=challenge_id,
            dispatch_type=dispatch_type,
            decision=decision,
            actor=actor,
            reason=reason,
            **trust_challenge_common_dependencies,
            workflow_mark_completed=workflow_mark_completed,
            workflow_mark_draw_pending_vote=workflow_mark_draw_pending_vote,
            resolve_open_alerts_for_review=resolve_open_alerts_for_review,
            trust_challenge_state_closed=trust_challenge_state_closed,
            trust_challenge_state_verdict_upheld=trust_challenge_state_verdict_upheld,
            trust_challenge_state_verdict_overturned=(
                trust_challenge_state_verdict_overturned
            ),
            trust_challenge_state_draw_after_review=(
                trust_challenge_state_draw_after_review
            ),
            trust_challenge_state_review_retained=(
                trust_challenge_state_review_retained
            ),
            workflow_transition_error_cls=workflow_transition_error_cls,
        )
    )


async def build_validated_trust_item_payload_for_runtime(
    *,
    case_id: int,
    dispatch_type: str,
    item_key: str,
    validate_contract: Callable[[dict[str, Any]], None],
    violation_code: str,
    build_trust_phasea_bundle: Callable[..., Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    bundle = await build_trust_phasea_bundle(
        case_id=case_id,
        dispatch_type=dispatch_type,
    )
    return _run_trust_read_guard_sync(
        build_validated_trust_item_route_payload_v3,
        case_id=case_id,
        bundle=bundle,
        item_key=item_key,
        validate_contract=validate_contract,
        violation_code=violation_code,
    )


async def build_trust_audit_anchor_payload_for_runtime(
    *,
    case_id: int,
    dispatch_type: str,
    include_payload: bool,
    build_trust_phasea_bundle: Callable[..., Awaitable[dict[str, Any]]],
    build_audit_anchor_export: Callable[..., dict[str, Any]],
    validate_contract: Callable[[dict[str, Any]], None],
    violation_code: str,
) -> dict[str, Any]:
    bundle = await build_trust_phasea_bundle(
        case_id=case_id,
        dispatch_type=dispatch_type,
    )
    return _run_trust_read_guard_sync(
        build_trust_audit_anchor_route_payload_v3,
        case_id=case_id,
        bundle=bundle,
        include_payload=include_payload,
        build_audit_anchor_export=build_audit_anchor_export,
        validate_contract=validate_contract,
        violation_code=violation_code,
    )


async def build_trust_public_verify_payload_for_runtime(
    *,
    case_id: int,
    dispatch_type: str,
    build_trust_phasea_bundle: Callable[..., Awaitable[dict[str, Any]]],
    build_audit_anchor_export: Callable[..., dict[str, Any]],
    build_public_verify_payload: Callable[..., dict[str, Any]],
    validate_contract: Callable[[dict[str, Any]], None],
    violation_code: str,
) -> dict[str, Any]:
    bundle = await build_trust_phasea_bundle(
        case_id=case_id,
        dispatch_type=dispatch_type,
    )
    return _run_trust_read_guard_sync(
        build_trust_public_verify_bundle_payload_v3,
        case_id=case_id,
        bundle=bundle,
        build_audit_anchor_export=build_audit_anchor_export,
        build_public_verify_payload=build_public_verify_payload,
        validate_contract=validate_contract,
        violation_code=violation_code,
    )
