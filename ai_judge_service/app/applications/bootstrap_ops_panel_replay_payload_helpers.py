from __future__ import annotations

from datetime import datetime
from typing import Any, Awaitable, Callable

from fastapi import HTTPException

from ..trace_store import TraceQuery
from .case_courtroom_views import (
    serialize_claim_ledger_record as serialize_claim_ledger_record_v3,
)
from .fairness_runtime_routes import (
    normalize_case_fairness_challenge_state as normalize_case_fairness_challenge_state_v3,
)
from .fairness_runtime_routes import (
    normalize_case_fairness_gate_conclusion as normalize_case_fairness_gate_conclusion_v3,
)
from .judge_trace_replay_routes import (
    build_replay_report_route_payload as build_replay_report_route_payload_v3,
)
from .judge_trace_replay_routes import (
    build_replay_reports_list_payload as build_replay_reports_list_payload_v3,
)
from .judge_trace_replay_routes import (
    build_replay_reports_route_payload as build_replay_reports_route_payload_v3,
)
from .ops_read_model_pack import (
    build_ops_read_model_pack_adaptive_summary,
    build_ops_read_model_pack_case_chain_coverage,
    build_ops_read_model_pack_case_lifecycle_overview,
    build_ops_read_model_pack_fairness_gate_overview,
    build_ops_read_model_pack_filters,
    build_ops_read_model_pack_judge_workflow_coverage,
    build_ops_read_model_pack_policy_kernel_binding,
    build_ops_read_model_pack_read_contract,
    build_ops_read_model_pack_route_payload,
    build_ops_read_model_pack_trust_overview,
    build_ops_read_model_pack_v5_payload,
    summarize_ops_read_model_pack_review_items,
    summarize_ops_read_model_pack_trust_items,
)
from .panel_runtime_profile_contract import (
    validate_panel_runtime_profile_contract as validate_panel_runtime_profile_contract_v3,
)
from .panel_runtime_routes import (
    build_panel_runtime_profile_aggregations as build_panel_runtime_profile_aggregations_v3,
)
from .panel_runtime_routes import (
    build_panel_runtime_profile_item as build_panel_runtime_profile_item_v3,
)
from .panel_runtime_routes import (
    build_panel_runtime_profile_sort_key as build_panel_runtime_profile_sort_key_v3,
)
from .panel_runtime_routes import (
    build_panel_runtime_profiles_route_payload as build_panel_runtime_profiles_route_payload_v3,
)
from .panel_runtime_routes import (
    build_panel_runtime_readiness_route_payload as build_panel_runtime_readiness_route_payload_v3,
)
from .panel_runtime_routes import (
    build_panel_runtime_readiness_summary as build_panel_runtime_readiness_summary_v3,
)
from .panel_runtime_routes import (
    normalize_panel_runtime_profile_sort_by as normalize_panel_runtime_profile_sort_by_v3,
)
from .panel_runtime_routes import (
    normalize_panel_runtime_profile_sort_order as normalize_panel_runtime_profile_sort_order_v3,
)
from .panel_runtime_routes import (
    normalize_panel_runtime_profile_source as normalize_panel_runtime_profile_source_v3,
)
from .replay_audit_ops import build_replay_report_payload as build_replay_report_payload_v3
from .replay_audit_ops import build_replay_report_summary as build_replay_report_summary_v3
from .replay_audit_ops import build_verdict_contract as build_verdict_contract_v3
from .replay_audit_ops import serialize_dispatch_receipt as serialize_dispatch_receipt_v3


async def build_shared_room_context_for_runtime(
    *,
    session_id: int,
    case_id: int | None,
    list_dispatch_receipts: Callable[..., Awaitable[list[Any]]],
    workflow_list_jobs: Callable[..., Awaitable[list[Any]]],
) -> dict[str, Any]:
    normalized_session_id = max(0, int(session_id))
    requested_case_id = max(0, int(case_id)) if case_id is not None else None

    phase_receipts = await list_dispatch_receipts(
        dispatch_type="phase",
        session_id=normalized_session_id,
        limit=200,
    )
    final_receipts = await list_dispatch_receipts(
        dispatch_type="final",
        session_id=normalized_session_id,
        limit=200,
    )
    if requested_case_id is not None:
        phase_receipts = [
            row
            for row in phase_receipts
            if int(getattr(row, "job_id", 0)) == requested_case_id
        ]
        final_receipts = [
            row
            for row in final_receipts
            if int(getattr(row, "job_id", 0)) == requested_case_id
        ]

    latest_phase = phase_receipts[0] if phase_receipts else None
    latest_final = final_receipts[0] if final_receipts else None
    latest_receipt = latest_final or latest_phase

    workflow_jobs = await workflow_list_jobs(
        status=None,
        dispatch_type=None,
        limit=300,
    )
    session_jobs = [
        row for row in workflow_jobs if int(row.session_id or 0) == normalized_session_id
    ]
    if requested_case_id is not None:
        session_jobs = [row for row in session_jobs if row.job_id == requested_case_id]
    latest_workflow_job = session_jobs[0] if session_jobs else None

    selected_case_id = (
        int(getattr(latest_receipt, "job_id", 0))
        if latest_receipt is not None
        else requested_case_id
    )
    if selected_case_id is not None and selected_case_id <= 0:
        selected_case_id = None
    selected_scope_id = (
        int(getattr(latest_receipt, "scope_id", 0))
        if latest_receipt is not None
        else int(getattr(latest_workflow_job, "scope_id", 0) or 0)
    )
    if selected_scope_id <= 0:
        selected_scope_id = 1

    report_payload: dict[str, Any] = {}
    latest_response = (
        latest_receipt.response
        if latest_receipt is not None and isinstance(latest_receipt.response, dict)
        else {}
    )
    if isinstance(latest_response.get("reportPayload"), dict):
        report_payload = latest_response["reportPayload"]
    judge_trace_payload = (
        latest_response.get("judgeTrace")
        if isinstance(latest_response.get("judgeTrace"), dict)
        else {}
    )
    policy_registry_payload = (
        judge_trace_payload.get("policyRegistry")
        if isinstance(judge_trace_payload.get("policyRegistry"), dict)
        else {}
    )
    rubric_version = (
        str(getattr(latest_receipt, "rubric_version", "") or "").strip()
        if latest_receipt is not None
        else ""
    )
    judge_policy_version = (
        str(getattr(latest_receipt, "judge_policy_version", "") or "").strip()
        if latest_receipt is not None
        else ""
    )
    topic_domain = (
        str(getattr(latest_receipt, "topic_domain", "") or "").strip()
        if latest_receipt is not None
        else ""
    )
    retrieval_profile = (
        str(getattr(latest_receipt, "retrieval_profile", "") or "").strip()
        if latest_receipt is not None
        else ""
    )
    rule_version = (
        str(policy_registry_payload.get("version") or "").strip()
        or judge_policy_version
        or None
    )

    verdict_contract = build_verdict_contract_v3(report_payload)
    winner_raw = latest_response.get("winner") or verdict_contract.get("winner")
    winner = str(winner_raw or "").strip().lower() or None
    debate_summary = (
        report_payload.get("debateSummary")
        if isinstance(report_payload.get("debateSummary"), str)
        else None
    )
    side_analysis = (
        report_payload.get("sideAnalysis")
        if isinstance(report_payload.get("sideAnalysis"), dict)
        else {}
    )
    verdict_reason = (
        report_payload.get("verdictReason")
        if isinstance(report_payload.get("verdictReason"), str)
        else None
    )
    updated_at = (
        latest_receipt.updated_at.isoformat()
        if latest_receipt is not None and getattr(latest_receipt, "updated_at", None) is not None
        else None
    )
    latest_dispatch_type = (
        "final" if latest_final is not None else ("phase" if latest_phase is not None else None)
    )

    return {
        "source": "shared_room_context_v1",
        "sessionId": normalized_session_id,
        "scopeId": selected_scope_id,
        "caseId": selected_case_id,
        "latestDispatchType": latest_dispatch_type,
        "workflowStatus": latest_workflow_job.status if latest_workflow_job is not None else None,
        "winnerHint": winner,
        "reviewRequired": bool(verdict_contract.get("reviewRequired")),
        "needsDrawVote": bool(verdict_contract.get("needsDrawVote")),
        "ruleVersion": rule_version,
        "rubricVersion": rubric_version or None,
        "judgePolicyVersion": judge_policy_version or None,
        "topicDomain": topic_domain or None,
        "retrievalProfile": retrieval_profile or None,
        "phaseReceiptCount": len(phase_receipts),
        "finalReceiptCount": len(final_receipts),
        "debateSummary": debate_summary,
        "sideAnalysis": side_analysis,
        "verdictReason": verdict_reason,
        "updatedAt": updated_at,
    }


async def build_dispatch_receipt_payload_for_runtime(
    *,
    case_id: int,
    dispatch_type: str,
    not_found_detail: str,
    get_dispatch_receipt: Callable[..., Awaitable[Any | None]],
) -> dict[str, Any]:
    item = await get_dispatch_receipt(
        dispatch_type=dispatch_type,
        job_id=case_id,
    )
    if item is None:
        raise HTTPException(status_code=404, detail=not_found_detail)
    return serialize_dispatch_receipt_v3(item)


async def build_ops_read_model_pack_payload_for_runtime(
    *,
    trust_challenge_open_states: set[str] | frozenset[str],
    judge_role_order: tuple[str, ...] | list[str],
    normalize_fairness_gate_decision: Callable[[Any], str],
    x_ai_internal_key: str | None,
    dispatch_type: str | None,
    policy_version: str | None,
    window_days: int,
    top_limit: int,
    case_scan_limit: int,
    include_case_trust: bool,
    trust_case_limit: int,
    dependency_limit: int,
    usage_preview_limit: int,
    release_limit: int,
    audit_limit: int,
    calibration_risk_limit: int,
    calibration_benchmark_limit: int,
    calibration_shadow_limit: int,
    panel_profile_scan_limit: int,
    panel_group_limit: int,
    panel_attention_limit: int,
    runtime: Any,
    get_judge_fairness_dashboard: Callable[..., Awaitable[dict[str, Any]]],
    get_registry_governance_overview: Callable[..., Awaitable[dict[str, Any]]],
    get_registry_prompt_tool_governance: Callable[..., Awaitable[dict[str, Any]]],
    get_policy_registry_dependency_health: Callable[..., Awaitable[dict[str, Any]]],
    get_judge_fairness_policy_calibration_advisor: Callable[..., Awaitable[dict[str, Any]]],
    get_panel_runtime_readiness: Callable[..., Awaitable[dict[str, Any]]],
    list_judge_courtroom_cases: Callable[..., Awaitable[dict[str, Any]]],
    list_judge_courtroom_drilldown_bundle: Callable[..., Awaitable[dict[str, Any]]],
    list_judge_evidence_claim_ops_queue: Callable[..., Awaitable[dict[str, Any]]],
    list_judge_trust_challenge_ops_queue: Callable[..., Awaitable[dict[str, Any]]],
    list_judge_review_jobs: Callable[..., Awaitable[dict[str, Any]]],
    simulate_policy_release_gate: Callable[..., Awaitable[dict[str, Any]]],
    get_judge_case_courtroom_read_model: Callable[..., Awaitable[dict[str, Any]]],
    get_judge_trust_public_verify: Callable[..., Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    return await build_ops_read_model_pack_route_payload(
        x_ai_internal_key=x_ai_internal_key,
        dispatch_type=dispatch_type,
        policy_version=policy_version,
        window_days=window_days,
        top_limit=top_limit,
        case_scan_limit=case_scan_limit,
        include_case_trust=include_case_trust,
        trust_case_limit=trust_case_limit,
        dependency_limit=dependency_limit,
        usage_preview_limit=usage_preview_limit,
        release_limit=release_limit,
        audit_limit=audit_limit,
        calibration_risk_limit=calibration_risk_limit,
        calibration_benchmark_limit=calibration_benchmark_limit,
        calibration_shadow_limit=calibration_shadow_limit,
        panel_profile_scan_limit=panel_profile_scan_limit,
        panel_group_limit=panel_group_limit,
        panel_attention_limit=panel_attention_limit,
        trust_challenge_open_states=trust_challenge_open_states,
        judge_role_order=judge_role_order,
        get_trace=runtime.trace_store.get_trace,
        get_judge_fairness_dashboard=get_judge_fairness_dashboard,
        get_registry_governance_overview=get_registry_governance_overview,
        get_registry_prompt_tool_governance=get_registry_prompt_tool_governance,
        get_policy_registry_dependency_health=get_policy_registry_dependency_health,
        get_judge_fairness_policy_calibration_advisor=(
            get_judge_fairness_policy_calibration_advisor
        ),
        get_panel_runtime_readiness=get_panel_runtime_readiness,
        list_judge_courtroom_cases=list_judge_courtroom_cases,
        list_judge_courtroom_drilldown_bundle=list_judge_courtroom_drilldown_bundle,
        list_judge_evidence_claim_ops_queue=list_judge_evidence_claim_ops_queue,
        list_judge_trust_challenge_ops_queue=list_judge_trust_challenge_ops_queue,
        list_judge_review_jobs=list_judge_review_jobs,
        simulate_policy_release_gate=simulate_policy_release_gate,
        get_judge_case_courtroom_read_model=get_judge_case_courtroom_read_model,
        get_judge_trust_public_verify=get_judge_trust_public_verify,
        normalize_fairness_gate_decision=normalize_fairness_gate_decision,
        summarize_ops_read_model_pack_trust_items_fn=(
            summarize_ops_read_model_pack_trust_items
        ),
        summarize_ops_read_model_pack_review_items_fn=(
            summarize_ops_read_model_pack_review_items
        ),
        build_ops_read_model_pack_case_chain_coverage_fn=(
            build_ops_read_model_pack_case_chain_coverage
        ),
        build_ops_read_model_pack_case_lifecycle_overview_fn=(
            build_ops_read_model_pack_case_lifecycle_overview
        ),
        build_ops_read_model_pack_fairness_gate_overview_fn=(
            build_ops_read_model_pack_fairness_gate_overview
        ),
        build_ops_read_model_pack_policy_kernel_binding_fn=(
            build_ops_read_model_pack_policy_kernel_binding
        ),
        build_ops_read_model_pack_read_contract_fn=build_ops_read_model_pack_read_contract,
        build_ops_read_model_pack_adaptive_summary_fn=(
            build_ops_read_model_pack_adaptive_summary
        ),
        build_ops_read_model_pack_trust_overview_fn=build_ops_read_model_pack_trust_overview,
        build_ops_read_model_pack_judge_workflow_coverage_fn=(
            build_ops_read_model_pack_judge_workflow_coverage
        ),
        build_ops_read_model_pack_filters_fn=build_ops_read_model_pack_filters,
        build_ops_read_model_pack_v5_payload_fn=build_ops_read_model_pack_v5_payload,
    )


async def build_panel_runtime_profiles_payload_for_runtime(
    *,
    panel_judge_ids: tuple[str, ...],
    panel_runtime_profile_source_values: set[str] | frozenset[str],
    panel_runtime_profile_sort_fields: set[str] | frozenset[str],
    normalize_workflow_status: Callable[[str | None], str],
    x_ai_internal_key: str | None,
    status: str | None,
    dispatch_type: str | None,
    winner: str | None,
    policy_version: str | None,
    has_open_review: bool | None,
    gate_conclusion: str | None,
    challenge_state: str | None,
    review_required: bool | None,
    panel_high_disagreement: bool | None,
    judge_id: str | None,
    profile_source: str | None,
    profile_id: str | None,
    model_strategy: str | None,
    strategy_slot: str | None,
    domain_slot: str | None,
    sort_by: str,
    sort_order: str,
    offset: int,
    limit: int,
    list_judge_case_fairness: Callable[..., Awaitable[dict[str, Any]]],
    run_panel_runtime_route_guard: Callable[
        [Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]
    ],
) -> dict[str, Any]:
    return await run_panel_runtime_route_guard(
        build_panel_runtime_profiles_route_payload_v3(
            list_judge_case_fairness=list_judge_case_fairness,
            build_panel_runtime_profile_item=build_panel_runtime_profile_item_v3,
            build_panel_runtime_profile_sort_key=build_panel_runtime_profile_sort_key_v3,
            build_panel_runtime_profile_aggregations=(
                build_panel_runtime_profile_aggregations_v3
            ),
            validate_panel_runtime_profile_contract=(
                validate_panel_runtime_profile_contract_v3
            ),
            panel_judge_ids=panel_judge_ids,
            panel_runtime_profile_source_values=panel_runtime_profile_source_values,
            panel_runtime_profile_sort_fields=panel_runtime_profile_sort_fields,
            normalize_workflow_status=normalize_workflow_status,
            normalize_panel_runtime_profile_source=normalize_panel_runtime_profile_source_v3,
            normalize_panel_runtime_profile_sort_by=normalize_panel_runtime_profile_sort_by_v3,
            normalize_panel_runtime_profile_sort_order=normalize_panel_runtime_profile_sort_order_v3,
            normalize_case_fairness_gate_conclusion=(
                normalize_case_fairness_gate_conclusion_v3
            ),
            normalize_case_fairness_challenge_state=(
                normalize_case_fairness_challenge_state_v3
            ),
            x_ai_internal_key=x_ai_internal_key,
            status=status,
            dispatch_type=dispatch_type,
            winner=winner,
            policy_version=policy_version,
            has_open_review=has_open_review,
            gate_conclusion=gate_conclusion,
            challenge_state=challenge_state,
            review_required=review_required,
            panel_high_disagreement=panel_high_disagreement,
            judge_id=judge_id,
            profile_source=profile_source,
            profile_id=profile_id,
            model_strategy=model_strategy,
            strategy_slot=strategy_slot,
            domain_slot=domain_slot,
            sort_by=sort_by,
            sort_order=sort_order,
            offset=offset,
            limit=limit,
        )
    )


async def build_panel_runtime_readiness_payload_for_runtime(
    *,
    panel_judge_ids: tuple[str, ...],
    panel_runtime_profile_source_values: set[str] | frozenset[str],
    normalize_workflow_status: Callable[[str | None], str],
    x_ai_internal_key: str | None,
    status: str | None,
    dispatch_type: str | None,
    winner: str | None,
    policy_version: str | None,
    has_open_review: bool | None,
    gate_conclusion: str | None,
    challenge_state: str | None,
    review_required: bool | None,
    panel_high_disagreement: bool | None,
    judge_id: str | None,
    profile_source: str | None,
    profile_id: str | None,
    model_strategy: str | None,
    strategy_slot: str | None,
    domain_slot: str | None,
    profile_scan_limit: int,
    group_limit: int,
    attention_limit: int,
    list_panel_runtime_profiles: Callable[..., Awaitable[dict[str, Any]]],
    run_panel_runtime_route_guard: Callable[
        [Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]
    ],
) -> dict[str, Any]:
    return await run_panel_runtime_route_guard(
        build_panel_runtime_readiness_route_payload_v3(
            list_panel_runtime_profiles=list_panel_runtime_profiles,
            build_panel_runtime_readiness_summary=build_panel_runtime_readiness_summary_v3,
            panel_judge_ids=panel_judge_ids,
            panel_runtime_profile_source_values=panel_runtime_profile_source_values,
            normalize_workflow_status=normalize_workflow_status,
            normalize_panel_runtime_profile_source=normalize_panel_runtime_profile_source_v3,
            normalize_case_fairness_gate_conclusion=(
                normalize_case_fairness_gate_conclusion_v3
            ),
            normalize_case_fairness_challenge_state=(
                normalize_case_fairness_challenge_state_v3
            ),
            x_ai_internal_key=x_ai_internal_key,
            status=status,
            dispatch_type=dispatch_type,
            winner=winner,
            policy_version=policy_version,
            has_open_review=has_open_review,
            gate_conclusion=gate_conclusion,
            challenge_state=challenge_state,
            review_required=review_required,
            panel_high_disagreement=panel_high_disagreement,
            judge_id=judge_id,
            profile_source=profile_source,
            profile_id=profile_id,
            model_strategy=model_strategy,
            strategy_slot=strategy_slot,
            domain_slot=domain_slot,
            profile_scan_limit=profile_scan_limit,
            group_limit=group_limit,
            attention_limit=attention_limit,
        )
    )


async def build_replay_report_payload_for_runtime(
    *,
    case_id: int,
    get_trace: Callable[[int], dict[str, Any] | None],
    get_claim_ledger_record: Callable[..., Awaitable[Any | None]],
    run_replay_read_guard: Callable[
        [Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]
    ],
) -> dict[str, Any]:
    return await run_replay_read_guard(
        build_replay_report_route_payload_v3(
            case_id=case_id,
            get_trace=get_trace,
            build_replay_report_payload=build_replay_report_payload_v3,
            get_claim_ledger_record=get_claim_ledger_record,
            serialize_claim_ledger_record=serialize_claim_ledger_record_v3,
        )
    )


def build_replay_reports_payload_for_runtime(
    *,
    status: str | None,
    winner: str | None,
    callback_status: str | None,
    trace_id: str | None,
    created_after: datetime | None,
    created_before: datetime | None,
    has_audit_alert: bool | None,
    limit: int,
    include_report: bool,
    normalize_query_datetime: Callable[[datetime | None], datetime | None],
    list_traces: Callable[..., list[Any]],
) -> dict[str, Any]:
    return build_replay_reports_route_payload_v3(
        status=status,
        winner=winner,
        callback_status=callback_status,
        trace_id=trace_id,
        created_after=created_after,
        created_before=created_before,
        has_audit_alert=has_audit_alert,
        limit=limit,
        include_report=include_report,
        normalize_query_datetime=normalize_query_datetime,
        trace_query_cls=TraceQuery,
        list_traces=list_traces,
        build_replay_report_payload=build_replay_report_payload_v3,
        build_replay_report_summary=build_replay_report_summary_v3,
        build_replay_reports_list_payload=build_replay_reports_list_payload_v3,
    )
