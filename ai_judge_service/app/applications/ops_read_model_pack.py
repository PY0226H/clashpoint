from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

OPS_READ_MODEL_PACK_V5_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "generatedAt",
    "fairnessDashboard",
    "fairnessCalibrationAdvisor",
    "panelRuntimeReadiness",
    "registryGovernance",
    "registryPromptToolGovernance",
    "courtroomReadModel",
    "courtroomQueue",
    "courtroomDrilldown",
    "reviewQueue",
    "reviewTrustPriority",
    "evidenceClaimQueue",
    "trustChallengeQueue",
    "policyGateSimulation",
    "adaptiveSummary",
    "trustOverview",
    "judgeWorkflowCoverage",
    "caseLifecycleOverview",
    "caseChainCoverage",
    "fairnessGateOverview",
    "policyKernelBinding",
    "readContract",
    "filters",
)

OPS_READ_MODEL_PACK_V5_COURTROOM_READ_MODEL_KEYS: tuple[str, ...] = (
    "requestedCaseLimit",
    "caseIds",
    "count",
    "errorCount",
    "items",
    "errors",
)
OPS_READ_MODEL_PACK_V5_COURTROOM_ITEM_KEYS: tuple[str, ...] = (
    "caseId",
    "dispatchType",
    "workflowStatus",
    "callbackStatus",
    "winner",
    "reviewRequired",
    "needsDrawVote",
    "blocked",
    "lifecycleBucket",
    "gateDecision",
    "policyVersion",
    "policyKernelVersion",
    "policyKernelHash",
    "policyGateDecision",
    "policyGateSource",
    "policyOverrideApplied",
    "keyClaimCount",
    "decisiveEvidenceCount",
    "pivotalMomentCount",
    "debateSummary",
)
OPS_READ_MODEL_PACK_V5_COURTROOM_ERROR_KEYS: tuple[str, ...] = (
    "caseId",
    "statusCode",
    "errorCode",
)

OPS_READ_MODEL_PACK_V5_ADAPTIVE_SUMMARY_KEYS: tuple[str, ...] = (
    "calibrationGatePassed",
    "calibrationGateCode",
    "calibrationHighRiskCount",
    "recommendedActionCount",
    "registryPromptToolRiskCount",
    "registryPromptToolHighRiskCount",
    "panelReadyGroupCount",
    "panelWatchGroupCount",
    "panelAttentionGroupCount",
    "panelScannedRecordCount",
    "reviewQueueCount",
    "reviewHighRiskCount",
    "reviewUrgentCount",
    "reviewTrustPriorityCount",
    "reviewUnifiedHighPriorityCount",
    "reviewTrustOpenChallengeCount",
    "policySimulationBlockedCount",
    "courtroomSampleCount",
    "courtroomQueueCount",
    "courtroomDrilldownCount",
    "courtroomDrilldownReviewRequiredCount",
    "courtroomDrilldownHighRiskCount",
    "evidenceClaimQueueCount",
    "evidenceClaimHighRiskCount",
    "evidenceClaimConflictCaseCount",
    "evidenceClaimUnansweredClaimCaseCount",
    "trustChallengeQueueCount",
    "trustChallengeHighPriorityCount",
    "trustChallengeUrgentCount",
)

OPS_READ_MODEL_PACK_V5_TRUST_OVERVIEW_KEYS: tuple[str, ...] = (
    "included",
    "requestedCaseLimit",
    "caseIds",
    "count",
    "verifiedCount",
    "reviewRequiredCount",
    "openChallengeCount",
    "errorCount",
    "items",
    "errors",
)

OPS_READ_MODEL_PACK_V5_FILTER_KEYS: tuple[str, ...] = (
    "dispatchType",
    "policyVersion",
    "windowDays",
    "topLimit",
    "caseScanLimit",
    "includeCaseTrust",
    "trustCaseLimit",
    "dependencyLimit",
    "usagePreviewLimit",
    "releaseLimit",
    "auditLimit",
    "calibrationRiskLimit",
    "calibrationBenchmarkLimit",
    "calibrationShadowLimit",
    "panelProfileScanLimit",
    "panelGroupLimit",
    "panelAttentionLimit",
)

OPS_READ_MODEL_PACK_V5_REQUIRED_AGGREGATIONS: tuple[tuple[str, str], ...] = (
    ("courtroomDrilldown", "aggregations"),
    ("evidenceClaimQueue", "aggregations"),
)

_OPS_READ_MODEL_PACK_V5_ADAPTIVE_COUNT_KEYS: tuple[str, ...] = tuple(
    key
    for key in OPS_READ_MODEL_PACK_V5_ADAPTIVE_SUMMARY_KEYS
    if key not in {"calibrationGatePassed", "calibrationGateCode"}
)
_OPS_READ_MODEL_PACK_V5_TRUST_OVERVIEW_COUNT_KEYS: tuple[str, ...] = (
    "requestedCaseLimit",
    "count",
    "verifiedCount",
    "reviewRequiredCount",
    "openChallengeCount",
    "errorCount",
)
_OPS_READ_MODEL_PACK_V5_FILTER_POSITIVE_INT_KEYS: tuple[str, ...] = (
    "windowDays",
    "topLimit",
    "caseScanLimit",
    "trustCaseLimit",
    "dependencyLimit",
    "usagePreviewLimit",
    "releaseLimit",
    "auditLimit",
    "calibrationRiskLimit",
    "calibrationBenchmarkLimit",
    "calibrationShadowLimit",
    "panelProfileScanLimit",
    "panelGroupLimit",
    "panelAttentionLimit",
)
OPS_READ_MODEL_PACK_V5_JUDGE_WORKFLOW_COVERAGE_KEYS: tuple[str, ...] = (
    "totalCases",
    "fullCount",
    "partialCount",
    "missingCount",
    "invalidOrderCount",
    "missingRoleCounts",
    "fullCoverageRate",
)
OPS_READ_MODEL_PACK_V5_CASE_CHAIN_COVERAGE_KEYS: tuple[str, ...] = (
    "totalCases",
    "completeCount",
    "missingAnyCount",
    "fullCoverageRate",
    "missingAnyRate",
    "byObjectPresence",
)
OPS_READ_MODEL_PACK_V5_CHAIN_OBJECT_KEYS: tuple[str, ...] = (
    "caseDossier",
    "claimGraph",
    "evidenceBundle",
    "verdictLedger",
    "fairnessReport",
    "opinionPack",
)
OPS_READ_MODEL_PACK_V5_FAIRNESS_GATE_OVERVIEW_KEYS: tuple[str, ...] = (
    "totalCases",
    "caseDecisionCounts",
    "caseReviewRequiredCount",
    "policyVersionCount",
    "policyGateDecisionCounts",
    "policyGateSourceCounts",
    "policyOverrideAppliedCount",
)
OPS_READ_MODEL_PACK_V5_POLICY_KERNEL_BINDING_KEYS: tuple[str, ...] = (
    "activePolicyVersion",
    "trackedPolicyVersionCount",
    "kernelBoundPolicyCount",
    "missingKernelBindingCount",
    "casePolicyVersionCount",
    "missingCasePolicyVersionCount",
    "caseMissingKernelBindingCount",
    "overrideAppliedPolicyCount",
    "casePolicyVersionCounts",
    "gateDecisionCounts",
)
OPS_READ_MODEL_PACK_V5_CASE_LIFECYCLE_OVERVIEW_KEYS: tuple[str, ...] = (
    "totalCases",
    "workflowStatusCounts",
    "lifecycleBucketCounts",
    "reviewRequiredCount",
    "drawPendingCount",
    "blockedCount",
    "callbackFailedCount",
)
OPS_READ_MODEL_PACK_V5_READ_CONTRACT_KEYS: tuple[str, ...] = (
    "contractVersion",
    "businessRoutes",
    "opsRoutes",
    "policyRoutes",
    "fieldLayers",
    "errorSemantics",
)
OPS_READ_MODEL_PACK_V5_FIELD_LAYER_KEYS: tuple[str, ...] = (
    "userVisible",
    "opsVisible",
    "internalAudit",
)
OPS_READ_MODEL_PACK_V5_ERROR_SEMANTIC_KEYS: tuple[str, ...] = (
    "structuredErrorCodeRequired",
    "rawStringFallbackAllowed",
)


def _to_int(value: Any, *, default: int = 0) -> int:
    try:
        if isinstance(value, bool):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_optional_token(value: Any) -> str | None:
    token = str(value or "").strip().lower()
    return token or None


def _clamp_int(value: Any, *, minimum: int, maximum: int) -> int:
    normalized = _to_int(value, default=minimum)
    if normalized < minimum:
        return minimum
    if normalized > maximum:
        return maximum
    return normalized


def build_ops_read_model_pack_adaptive_summary(
    *,
    release_gate: dict[str, Any],
    advisor_overview: dict[str, Any],
    recommended_action_count: int,
    readiness_counts: dict[str, Any],
    readiness_overview: dict[str, Any],
    review_queue_count: int,
    review_high_risk_count: int,
    review_urgent_count: int,
    review_trust_priority_count: int,
    review_unified_high_priority_count: int,
    review_trust_open_challenge_count: int,
    policy_simulation_blocked_count: int,
    courtroom_sample_count: int,
    courtroom_queue_count: int,
    courtroom_drilldown_count: int,
    courtroom_drilldown_review_required_count: int,
    courtroom_drilldown_high_risk_count: int,
    evidence_claim_queue_count: int,
    evidence_claim_high_risk_count: int,
    evidence_claim_conflict_case_count: int,
    evidence_claim_unanswered_claim_case_count: int,
    trust_challenge_queue_count: int,
    trust_challenge_high_priority_count: int,
    trust_challenge_urgent_count: int,
    registry_prompt_tool_risk_count: int,
    registry_prompt_tool_high_risk_count: int,
) -> dict[str, Any]:
    return {
        "calibrationGatePassed": bool(release_gate.get("passed")),
        "calibrationGateCode": str(release_gate.get("code") or "").strip() or None,
        "calibrationHighRiskCount": _to_int(advisor_overview.get("highRiskCount"), default=0),
        "recommendedActionCount": max(0, _to_int(recommended_action_count, default=0)),
        "registryPromptToolRiskCount": max(0, _to_int(registry_prompt_tool_risk_count, default=0)),
        "registryPromptToolHighRiskCount": max(
            0, _to_int(registry_prompt_tool_high_risk_count, default=0)
        ),
        "panelReadyGroupCount": _to_int(readiness_counts.get("ready"), default=0),
        "panelWatchGroupCount": _to_int(readiness_counts.get("watch"), default=0),
        "panelAttentionGroupCount": _to_int(readiness_counts.get("attention"), default=0),
        "panelScannedRecordCount": _to_int(readiness_overview.get("scannedRecords"), default=0),
        "reviewQueueCount": max(0, _to_int(review_queue_count, default=0)),
        "reviewHighRiskCount": max(0, _to_int(review_high_risk_count, default=0)),
        "reviewUrgentCount": max(0, _to_int(review_urgent_count, default=0)),
        "reviewTrustPriorityCount": max(0, _to_int(review_trust_priority_count, default=0)),
        "reviewUnifiedHighPriorityCount": max(
            0, _to_int(review_unified_high_priority_count, default=0)
        ),
        "reviewTrustOpenChallengeCount": max(
            0, _to_int(review_trust_open_challenge_count, default=0)
        ),
        "policySimulationBlockedCount": max(
            0, _to_int(policy_simulation_blocked_count, default=0)
        ),
        "courtroomSampleCount": max(0, _to_int(courtroom_sample_count, default=0)),
        "courtroomQueueCount": max(0, _to_int(courtroom_queue_count, default=0)),
        "courtroomDrilldownCount": max(0, _to_int(courtroom_drilldown_count, default=0)),
        "courtroomDrilldownReviewRequiredCount": max(
            0, _to_int(courtroom_drilldown_review_required_count, default=0)
        ),
        "courtroomDrilldownHighRiskCount": max(
            0, _to_int(courtroom_drilldown_high_risk_count, default=0)
        ),
        "evidenceClaimQueueCount": max(0, _to_int(evidence_claim_queue_count, default=0)),
        "evidenceClaimHighRiskCount": max(
            0, _to_int(evidence_claim_high_risk_count, default=0)
        ),
        "evidenceClaimConflictCaseCount": max(
            0, _to_int(evidence_claim_conflict_case_count, default=0)
        ),
        "evidenceClaimUnansweredClaimCaseCount": max(
            0, _to_int(evidence_claim_unanswered_claim_case_count, default=0)
        ),
        "trustChallengeQueueCount": max(0, _to_int(trust_challenge_queue_count, default=0)),
        "trustChallengeHighPriorityCount": max(
            0, _to_int(trust_challenge_high_priority_count, default=0)
        ),
        "trustChallengeUrgentCount": max(0, _to_int(trust_challenge_urgent_count, default=0)),
    }


def build_ops_read_model_pack_trust_overview(
    *,
    include_case_trust: bool,
    trust_case_limit: int,
    trust_case_ids: list[int],
    trust_items: list[dict[str, Any]],
    trust_errors: list[dict[str, Any]],
    verified_count: int,
    review_required_count: int,
    open_challenge_count: int,
) -> dict[str, Any]:
    return {
        "included": bool(include_case_trust),
        "requestedCaseLimit": max(1, _to_int(trust_case_limit, default=1)),
        "caseIds": list(trust_case_ids),
        "count": len(trust_items),
        "verifiedCount": max(0, _to_int(verified_count, default=0)),
        "reviewRequiredCount": max(0, _to_int(review_required_count, default=0)),
        "openChallengeCount": max(0, _to_int(open_challenge_count, default=0)),
        "errorCount": len(trust_errors),
        "items": trust_items,
        "errors": trust_errors,
    }


def build_ops_read_model_pack_filters(
    *,
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
) -> dict[str, Any]:
    return {
        "dispatchType": str(dispatch_type or "").strip().lower() or None,
        "policyVersion": str(policy_version or "").strip() or None,
        "windowDays": _to_int(window_days, default=7),
        "topLimit": _to_int(top_limit, default=10),
        "caseScanLimit": _to_int(case_scan_limit, default=200),
        "includeCaseTrust": bool(include_case_trust),
        "trustCaseLimit": _to_int(trust_case_limit, default=5),
        "dependencyLimit": _clamp_int(dependency_limit, minimum=1, maximum=500),
        "usagePreviewLimit": _clamp_int(usage_preview_limit, minimum=1, maximum=200),
        "releaseLimit": _clamp_int(release_limit, minimum=1, maximum=200),
        "auditLimit": _clamp_int(audit_limit, minimum=1, maximum=200),
        "calibrationRiskLimit": _clamp_int(calibration_risk_limit, minimum=1, maximum=200),
        "calibrationBenchmarkLimit": _clamp_int(
            calibration_benchmark_limit,
            minimum=1,
            maximum=500,
        ),
        "calibrationShadowLimit": _clamp_int(
            calibration_shadow_limit,
            minimum=1,
            maximum=500,
        ),
        "panelProfileScanLimit": _clamp_int(panel_profile_scan_limit, minimum=50, maximum=5000),
        "panelGroupLimit": _clamp_int(panel_group_limit, minimum=1, maximum=200),
        "panelAttentionLimit": _clamp_int(panel_attention_limit, minimum=1, maximum=100),
    }


def _collect_top_case_ids(
    *,
    top_risk_cases: Any,
    limit: int,
) -> list[int]:
    if not isinstance(top_risk_cases, list):
        return []
    result: list[int] = []
    seen_case_ids: set[int] = set()
    normalized_limit = max(0, int(limit))
    for row in top_risk_cases:
        if len(result) >= normalized_limit:
            break
        if not isinstance(row, dict):
            continue
        try:
            case_id = int(row.get("caseId") or 0)
        except (TypeError, ValueError):
            continue
        if case_id <= 0 or case_id in seen_case_ids:
            continue
        seen_case_ids.add(case_id)
        result.append(case_id)
    return result


def _build_ops_read_model_pack_lifecycle_bucket(
    *,
    workflow_status: str | None,
    callback_status: str | None,
    review_required: bool,
    needs_draw_vote: bool,
    blocked: bool,
) -> str:
    status = _normalize_optional_token(workflow_status)
    callback = _normalize_optional_token(callback_status)
    if blocked or status == "blocked_failed" or callback == "blocked_failed_reported":
        return "blocked"
    if review_required or status == "review_required":
        return "review_required"
    if needs_draw_vote or status == "draw_pending_vote":
        return "draw_pending"
    if callback is not None and "failed" in callback:
        return "callback_failed"
    if status in {"callback_reported", "archived"}:
        return "reported"
    if status in {
        "panel_judged",
        "fairness_checked",
        "arbitrated",
        "opinion_written",
    }:
        return "judging"
    if status in {
        "queued",
        "blinded",
        "case_built",
        "claim_graph_ready",
        "evidence_ready",
    }:
        return "building"
    return status or "unknown"


def _as_httpish_error(err: Exception) -> tuple[int, str] | None:
    status_code = getattr(err, "status_code", None)
    if isinstance(status_code, bool) or not isinstance(status_code, int):
        return None
    detail = str(getattr(err, "detail", ""))
    return (int(status_code), detail)


async def build_ops_read_model_pack_route_payload(
    *,
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
    trust_challenge_open_states: set[str],
    judge_role_order: tuple[str, ...],
    get_trace: Callable[[int], Any],
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
    normalize_fairness_gate_decision: Callable[..., str],
    summarize_ops_read_model_pack_trust_items_fn: Callable[..., dict[str, int]],
    summarize_ops_read_model_pack_review_items_fn: Callable[..., dict[str, int]],
    build_ops_read_model_pack_case_chain_coverage_fn: Callable[..., dict[str, Any]],
    build_ops_read_model_pack_case_lifecycle_overview_fn: Callable[..., dict[str, Any]],
    build_ops_read_model_pack_fairness_gate_overview_fn: Callable[..., dict[str, Any]],
    build_ops_read_model_pack_policy_kernel_binding_fn: Callable[..., dict[str, Any]],
    build_ops_read_model_pack_read_contract_fn: Callable[..., dict[str, Any]],
    build_ops_read_model_pack_adaptive_summary_fn: Callable[..., dict[str, Any]],
    build_ops_read_model_pack_trust_overview_fn: Callable[..., dict[str, Any]],
    build_ops_read_model_pack_judge_workflow_coverage_fn: Callable[..., dict[str, Any]],
    build_ops_read_model_pack_filters_fn: Callable[..., dict[str, Any]],
    build_ops_read_model_pack_v5_payload_fn: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    fairness_dashboard = await get_judge_fairness_dashboard(
        x_ai_internal_key=x_ai_internal_key,
        status=None,
        dispatch_type=dispatch_type,
        winner=None,
        policy_version=policy_version,
        challenge_state=None,
        window_days=window_days,
        top_limit=top_limit,
        case_scan_limit=case_scan_limit,
    )
    governance_overview = await get_registry_governance_overview(
        x_ai_internal_key=x_ai_internal_key,
        dependency_limit=dependency_limit,
        usage_preview_limit=usage_preview_limit,
        release_limit=release_limit,
        audit_limit=audit_limit,
    )
    registry_prompt_tool_governance = await get_registry_prompt_tool_governance(
        x_ai_internal_key=x_ai_internal_key,
        dependency_limit=dependency_limit,
        usage_preview_limit=usage_preview_limit,
        release_limit=release_limit,
        audit_limit=audit_limit,
        risk_limit=calibration_risk_limit,
    )
    fairness_calibration_advisor = await get_judge_fairness_policy_calibration_advisor(
        x_ai_internal_key=x_ai_internal_key,
        dispatch_type=dispatch_type,
        status=None,
        winner=None,
        policy_version=policy_version,
        challenge_state=None,
        case_scan_limit=case_scan_limit,
        risk_limit=calibration_risk_limit,
        benchmark_limit=calibration_benchmark_limit,
        shadow_limit=calibration_shadow_limit,
    )
    panel_runtime_readiness = await get_panel_runtime_readiness(
        x_ai_internal_key=x_ai_internal_key,
        status=None,
        dispatch_type=dispatch_type,
        winner=None,
        policy_version=policy_version,
        has_open_review=None,
        gate_conclusion=None,
        challenge_state=None,
        review_required=None,
        panel_high_disagreement=None,
        judge_id=None,
        profile_source=None,
        profile_id=None,
        model_strategy=None,
        strategy_slot=None,
        domain_slot=None,
        profile_scan_limit=panel_profile_scan_limit,
        group_limit=panel_group_limit,
        attention_limit=panel_attention_limit,
    )

    queue_limit = max(1, min(int(top_limit) * 5, 200))
    courtroom_queue = await list_judge_courtroom_cases(
        x_ai_internal_key=x_ai_internal_key,
        status=None,
        dispatch_type="auto",
        winner=None,
        review_required=None,
        risk_level=None,
        sla_bucket=None,
        updated_from=None,
        updated_to=None,
        sort_by="risk_score",
        sort_order="desc",
        scan_limit=case_scan_limit,
        offset=0,
        limit=min(queue_limit, 200),
    )
    courtroom_drilldown = await list_judge_courtroom_drilldown_bundle(
        x_ai_internal_key=x_ai_internal_key,
        status=None,
        dispatch_type="auto",
        winner=None,
        review_required=None,
        risk_level=None,
        sla_bucket=None,
        updated_from=None,
        updated_to=None,
        sort_by="risk_score",
        sort_order="desc",
        scan_limit=case_scan_limit,
        offset=0,
        limit=min(queue_limit, 200),
        claim_preview_limit=10,
        evidence_preview_limit=10,
        panel_preview_limit=10,
    )
    evidence_claim_queue = await list_judge_evidence_claim_ops_queue(
        x_ai_internal_key=x_ai_internal_key,
        status=None,
        dispatch_type="auto",
        winner=None,
        review_required=None,
        risk_level=None,
        sla_bucket=None,
        reliability_level=None,
        has_conflict=None,
        has_unanswered_claim=None,
        updated_from=None,
        updated_to=None,
        sort_by="risk_score",
        sort_order="desc",
        scan_limit=case_scan_limit,
        offset=0,
        limit=min(queue_limit, 200),
    )
    trust_challenge_queue = await list_judge_trust_challenge_ops_queue(
        x_ai_internal_key=x_ai_internal_key,
        status=None,
        dispatch_type="auto",
        challenge_state="open",
        review_state=None,
        priority_level=None,
        sla_bucket=None,
        has_open_alert=None,
        sort_by="priority_score",
        sort_order="desc",
        scan_limit=case_scan_limit,
        offset=0,
        limit=min(queue_limit, 200),
    )
    review_queue = await list_judge_review_jobs(
        x_ai_internal_key=x_ai_internal_key,
        status="review_required",
        dispatch_type=dispatch_type,
        risk_level=None,
        sla_bucket=None,
        challenge_state=None,
        trust_review_state=None,
        unified_priority_level=None,
        sort_by="risk_score",
        sort_order="desc",
        scan_limit=case_scan_limit,
        limit=queue_limit,
    )
    review_trust_priority = await list_judge_review_jobs(
        x_ai_internal_key=x_ai_internal_key,
        status="review_required",
        dispatch_type=dispatch_type,
        risk_level=None,
        sla_bucket=None,
        challenge_state=None,
        trust_review_state=None,
        unified_priority_level=None,
        sort_by="unified_priority_score",
        sort_order="desc",
        scan_limit=case_scan_limit,
        limit=queue_limit,
    )
    policy_gate_simulation = await simulate_policy_release_gate(
        x_ai_internal_key=x_ai_internal_key,
        policy_version=policy_version,
        include_all_versions=False,
        limit=10,
    )
    policy_dependency_health = await get_policy_registry_dependency_health(
        x_ai_internal_key=x_ai_internal_key,
        policy_version=policy_version,
        include_all_versions=True,
        include_overview=True,
        include_trend=False,
        trend_status=None,
        trend_policy_version=None,
        trend_offset=0,
        trend_limit=50,
        overview_window_minutes=1440,
        limit=dependency_limit,
    )

    top_risk_cases = (
        fairness_dashboard.get("topRiskCases")
        if isinstance(fairness_dashboard.get("topRiskCases"), list)
        else []
    )
    governance_dependency_items = (
        governance_overview.get("dependencyHealth", {}).get("items")
        if isinstance(governance_overview.get("dependencyHealth"), dict)
        else []
    )
    if not isinstance(governance_dependency_items, list):
        governance_dependency_items = []
    governance_binding_by_policy: dict[str, dict[str, Any]] = {}
    for row in governance_dependency_items:
        if not isinstance(row, dict):
            continue
        version = str(row.get("policyVersion") or "").strip()
        if not version:
            continue
        governance_binding_by_policy[version] = row

    dependency_overview = (
        policy_dependency_health.get("dependencyOverview")
        if isinstance(policy_dependency_health.get("dependencyOverview"), dict)
        else {}
    )
    dependency_overview_rows = (
        dependency_overview.get("byPolicyVersion")
        if isinstance(dependency_overview.get("byPolicyVersion"), list)
        else []
    )
    dependency_gate_binding_by_policy: dict[str, dict[str, Any]] = {}
    for row in dependency_overview_rows:
        if not isinstance(row, dict):
            continue
        version = str(row.get("policyVersion") or "").strip()
        if not version:
            continue
        dependency_gate_binding_by_policy[version] = row

    courtroom_items: list[dict[str, Any]] = []
    courtroom_errors: list[dict[str, Any]] = []
    chain_rows: list[dict[str, Any]] = []
    courtroom_case_ids = _collect_top_case_ids(
        top_risk_cases=top_risk_cases,
        limit=int(top_limit),
    )
    judge_workflow_role_nodes_rows: list[list[dict[str, Any]] | None] = []
    for case_id in courtroom_case_ids:
        trace = get_trace(case_id)
        report_summary = (
            trace.report_summary
            if trace is not None and isinstance(trace.report_summary, dict)
            else {}
        )
        role_nodes = report_summary.get("roleNodes")
        if isinstance(role_nodes, list):
            judge_workflow_role_nodes_rows.append(
                [row for row in role_nodes if isinstance(row, dict)]
            )
        else:
            judge_workflow_role_nodes_rows.append(None)
        try:
            courtroom_payload = await get_judge_case_courtroom_read_model(
                case_id=case_id,
                x_ai_internal_key=x_ai_internal_key,
                dispatch_type="auto",
                include_events=False,
                include_alerts=False,
                alert_limit=50,
            )
        except Exception as err:
            httpish = _as_httpish_error(err)
            if httpish is None:
                raise
            status_code, detail = httpish
            courtroom_errors.append(
                {
                    "caseId": case_id,
                    "statusCode": status_code,
                    "errorCode": detail,
                }
            )
            continue
        courtroom_view = (
            courtroom_payload.get("courtroom")
            if isinstance(courtroom_payload.get("courtroom"), dict)
            else {}
        )
        recorder_view = (
            courtroom_view.get("recorder")
            if isinstance(courtroom_view.get("recorder"), dict)
            else {}
        )
        claim_view = (
            courtroom_view.get("claim")
            if isinstance(courtroom_view.get("claim"), dict)
            else {}
        )
        evidence_view = (
            courtroom_view.get("evidence")
            if isinstance(courtroom_view.get("evidence"), dict)
            else {}
        )
        panel_view = (
            courtroom_view.get("panel")
            if isinstance(courtroom_view.get("panel"), dict)
            else {}
        )
        fairness_view = (
            courtroom_view.get("fairness")
            if isinstance(courtroom_view.get("fairness"), dict)
            else {}
        )
        opinion_view = (
            courtroom_view.get("opinion")
            if isinstance(courtroom_view.get("opinion"), dict)
            else {}
        )
        governance_view = (
            courtroom_view.get("governance")
            if isinstance(courtroom_view.get("governance"), dict)
            else {}
        )
        workflow_view = (
            courtroom_payload.get("workflow")
            if isinstance(courtroom_payload.get("workflow"), dict)
            else {}
        )
        callback_view = (
            courtroom_payload.get("callback")
            if isinstance(courtroom_payload.get("callback"), dict)
            else {}
        )
        report_view = (
            courtroom_payload.get("report")
            if isinstance(courtroom_payload.get("report"), dict)
            else {}
        )
        key_claims = (
            claim_view.get("keyClaimsBySide")
            if isinstance(claim_view.get("keyClaimsBySide"), dict)
            else {}
        )
        key_claim_count = 0
        for side in ("pro", "con"):
            entries = key_claims.get(side)
            if isinstance(entries, list):
                key_claim_count += len(entries)
        decisive_refs = (
            evidence_view.get("decisiveEvidenceRefs")
            if isinstance(evidence_view.get("decisiveEvidenceRefs"), list)
            else []
        )
        pivotal_moments = (
            panel_view.get("pivotalMoments")
            if isinstance(panel_view.get("pivotalMoments"), list)
            else []
        )
        policy_version_token = str(governance_view.get("policyVersion") or "").strip() or None
        gate_binding = (
            dependency_gate_binding_by_policy.get(policy_version_token or "")
            if policy_version_token is not None
            else None
        )
        governance_binding = (
            governance_binding_by_policy.get(policy_version_token or "")
            if policy_version_token is not None
            else None
        )
        policy_kernel_version = (
            str((governance_binding or {}).get("policyKernelVersion") or "").strip() or None
        )
        policy_kernel_hash = (
            str((governance_binding or {}).get("policyKernelHash") or "").strip() or None
        )
        policy_gate_decision = (
            str((gate_binding or {}).get("latestGateDecision") or "").strip().lower() or None
        )
        policy_gate_source = (
            str((gate_binding or {}).get("latestGateSource") or "").strip().lower() or None
        )
        policy_override_applied = (
            bool((gate_binding or {}).get("overrideApplied"))
            if isinstance(gate_binding, dict)
            else None
        )
        workflow_status = _normalize_optional_token(workflow_view.get("status"))
        callback_status = _normalize_optional_token(callback_view.get("status"))
        winner = _normalize_optional_token(report_view.get("winner"))
        review_required = bool(
            report_view.get("reviewRequired") or fairness_view.get("reviewRequired")
        )
        needs_draw_vote = bool(report_view.get("needsDrawVote"))
        gate_decision = (
            normalize_fairness_gate_decision(
                fairness_view.get("gateDecision"),
                review_required=review_required,
            )
            or None
        )
        blocked = bool(
            workflow_status == "blocked_failed"
            or callback_status == "blocked_failed_reported"
        )
        lifecycle_bucket = _build_ops_read_model_pack_lifecycle_bucket(
            workflow_status=workflow_status,
            callback_status=callback_status,
            review_required=review_required,
            needs_draw_vote=needs_draw_vote,
            blocked=blocked,
        )
        chain_presence = {
            "caseDossier": bool(
                isinstance(recorder_view.get("caseDossier"), dict)
                and len(recorder_view.get("caseDossier") or {}) > 0
            ),
            "claimGraph": bool(
                isinstance(claim_view.get("claimGraph"), dict)
                and len(claim_view.get("claimGraph") or {}) > 0
            ),
            "evidenceBundle": bool(
                isinstance(evidence_view.get("evidenceLedger"), dict)
                and len(evidence_view.get("evidenceLedger") or {}) > 0
            ),
            "verdictLedger": bool(
                isinstance(panel_view.get("panelDecisions"), dict)
                and len(panel_view.get("panelDecisions") or {}) > 0
            ),
            "fairnessReport": bool(
                isinstance(fairness_view.get("summary"), dict)
                and len(fairness_view.get("summary") or {}) > 0
            ),
            "opinionPack": bool(
                str(opinion_view.get("debateSummary") or "").strip()
                or (
                    isinstance(opinion_view.get("sideAnalysis"), dict)
                    and len(opinion_view.get("sideAnalysis") or {}) > 0
                )
                or str(opinion_view.get("verdictReason") or "").strip()
            ),
        }
        chain_rows.append(
            {
                "caseId": case_id,
                **chain_presence,
            }
        )
        courtroom_items.append(
            {
                "caseId": case_id,
                "dispatchType": courtroom_payload.get("dispatchType"),
                "workflowStatus": workflow_status,
                "callbackStatus": callback_status,
                "winner": winner,
                "reviewRequired": review_required,
                "needsDrawVote": needs_draw_vote,
                "blocked": blocked,
                "lifecycleBucket": lifecycle_bucket,
                "gateDecision": gate_decision,
                "policyVersion": policy_version_token,
                "policyKernelVersion": policy_kernel_version,
                "policyKernelHash": policy_kernel_hash,
                "policyGateDecision": policy_gate_decision,
                "policyGateSource": policy_gate_source,
                "policyOverrideApplied": policy_override_applied,
                "keyClaimCount": key_claim_count,
                "decisiveEvidenceCount": len(decisive_refs),
                "pivotalMomentCount": len(pivotal_moments),
                "debateSummary": (
                    opinion_view.get("debateSummary")
                    if isinstance(opinion_view.get("debateSummary"), str)
                    else None
                ),
            }
        )

    trust_items: list[dict[str, Any]] = []
    trust_errors: list[dict[str, Any]] = []
    trust_case_ids: list[int] = []
    if include_case_trust:
        trust_case_ids = _collect_top_case_ids(
            top_risk_cases=top_risk_cases,
            limit=int(trust_case_limit),
        )
        for case_id in trust_case_ids:
            try:
                trust_payload = await get_judge_trust_public_verify(
                    case_id=case_id,
                    x_ai_internal_key=x_ai_internal_key,
                    dispatch_type="auto",
                )
            except Exception as err:
                httpish = _as_httpish_error(err)
                if httpish is None:
                    raise
                status_code, detail = httpish
                trust_errors.append(
                    {
                        "caseId": case_id,
                        "statusCode": status_code,
                        "errorCode": detail,
                    }
                )
                continue
            verify_payload = (
                trust_payload.get("verifyPayload")
                if isinstance(trust_payload.get("verifyPayload"), dict)
                else {}
            )
            verdict_attestation = (
                verify_payload.get("verdictAttestation")
                if isinstance(verify_payload.get("verdictAttestation"), dict)
                else {}
            )
            challenge_review = (
                verify_payload.get("challengeReview")
                if isinstance(verify_payload.get("challengeReview"), dict)
                else {}
            )
            challenge_state = (
                str(challenge_review.get("challengeState") or "").strip().lower() or None
            )
            try:
                total_challenges = int(challenge_review.get("totalChallenges") or 0)
            except (TypeError, ValueError):
                total_challenges = 0
            trust_items.append(
                {
                    "caseId": case_id,
                    "dispatchType": trust_payload.get("dispatchType"),
                    "traceId": trust_payload.get("traceId"),
                    "verdictVerified": bool(verdict_attestation.get("verified")),
                    "verdictReason": (
                        str(verdict_attestation.get("reason") or "").strip() or None
                    ),
                    "reviewRequired": bool(challenge_review.get("reviewRequired")),
                    "challengeState": challenge_state,
                    "totalChallenges": max(0, total_challenges),
                }
            )

    trust_summary = summarize_ops_read_model_pack_trust_items_fn(
        trust_items=trust_items,
        open_challenge_states=trust_challenge_open_states,
    )

    advisor_overview = (
        fairness_calibration_advisor.get("overview")
        if isinstance(fairness_calibration_advisor.get("overview"), dict)
        else {}
    )
    release_gate = (
        fairness_calibration_advisor.get("releaseGate")
        if isinstance(fairness_calibration_advisor.get("releaseGate"), dict)
        else {}
    )
    recommended_actions = (
        fairness_calibration_advisor.get("recommendedActions")
        if isinstance(fairness_calibration_advisor.get("recommendedActions"), list)
        else []
    )
    readiness_overview = (
        panel_runtime_readiness.get("overview")
        if isinstance(panel_runtime_readiness.get("overview"), dict)
        else {}
    )
    readiness_counts = (
        readiness_overview.get("readinessCounts")
        if isinstance(readiness_overview.get("readinessCounts"), dict)
        else {}
    )
    review_items = (
        review_queue.get("items")
        if isinstance(review_queue.get("items"), list)
        else []
    )
    review_trust_priority_items = (
        review_trust_priority.get("items")
        if isinstance(review_trust_priority.get("items"), list)
        else []
    )
    trust_challenge_queue_items = (
        trust_challenge_queue.get("items")
        if isinstance(trust_challenge_queue.get("items"), list)
        else []
    )
    review_summary = summarize_ops_read_model_pack_review_items_fn(
        review_items=review_items,
        review_trust_priority_items=review_trust_priority_items,
        trust_challenge_queue_items=trust_challenge_queue_items,
        open_challenge_states=trust_challenge_open_states,
    )
    simulation_summary = (
        policy_gate_simulation.get("summary")
        if isinstance(policy_gate_simulation.get("summary"), dict)
        else {}
    )
    registry_prompt_tool_risk_items = (
        registry_prompt_tool_governance.get("riskItems")
        if isinstance(registry_prompt_tool_governance.get("riskItems"), list)
        else []
    )
    registry_prompt_tool_high_risk_count = sum(
        1
        for row in registry_prompt_tool_risk_items
        if isinstance(row, dict)
        and str(row.get("severity") or "").strip().lower() == "high"
    )
    evidence_claim_aggregations = (
        evidence_claim_queue.get("aggregations")
        if isinstance(evidence_claim_queue.get("aggregations"), dict)
        else {}
    )
    evidence_claim_risk_counts = (
        evidence_claim_aggregations.get("riskLevelCounts")
        if isinstance(evidence_claim_aggregations.get("riskLevelCounts"), dict)
        else {}
    )
    courtroom_drilldown_aggregations = (
        courtroom_drilldown.get("aggregations")
        if isinstance(courtroom_drilldown.get("aggregations"), dict)
        else {}
    )
    adaptive_summary = build_ops_read_model_pack_adaptive_summary_fn(
        release_gate=release_gate,
        advisor_overview=advisor_overview,
        recommended_action_count=len(recommended_actions),
        readiness_counts=readiness_counts,
        readiness_overview=readiness_overview,
        review_queue_count=int(review_queue.get("count") or 0),
        review_high_risk_count=review_summary["reviewHighRiskCount"],
        review_urgent_count=review_summary["reviewUrgentCount"],
        review_trust_priority_count=int(review_trust_priority.get("count") or 0),
        review_unified_high_priority_count=review_summary["reviewUnifiedHighPriorityCount"],
        review_trust_open_challenge_count=review_summary["reviewTrustOpenChallengeCount"],
        policy_simulation_blocked_count=int(simulation_summary.get("blockedCount") or 0),
        courtroom_sample_count=len(courtroom_items),
        courtroom_queue_count=int(courtroom_queue.get("count") or 0),
        courtroom_drilldown_count=int(courtroom_drilldown.get("count") or 0),
        courtroom_drilldown_review_required_count=int(
            courtroom_drilldown_aggregations.get("reviewRequiredCount") or 0
        ),
        courtroom_drilldown_high_risk_count=int(
            courtroom_drilldown_aggregations.get("highRiskCount") or 0
        ),
        evidence_claim_queue_count=int(evidence_claim_queue.get("count") or 0),
        evidence_claim_high_risk_count=int(evidence_claim_risk_counts.get("high") or 0),
        evidence_claim_conflict_case_count=int(
            evidence_claim_aggregations.get("conflictCaseCount") or 0
        ),
        evidence_claim_unanswered_claim_case_count=int(
            evidence_claim_aggregations.get("unansweredClaimCaseCount")
            or evidence_claim_aggregations.get("unansweredCaseCount")
            or 0
        ),
        trust_challenge_queue_count=int(trust_challenge_queue.get("count") or 0),
        trust_challenge_high_priority_count=review_summary["trustChallengeHighPriorityCount"],
        trust_challenge_urgent_count=review_summary["trustChallengeUrgentCount"],
        registry_prompt_tool_risk_count=len(registry_prompt_tool_risk_items),
        registry_prompt_tool_high_risk_count=registry_prompt_tool_high_risk_count,
    )
    trust_overview = build_ops_read_model_pack_trust_overview_fn(
        include_case_trust=include_case_trust,
        trust_case_limit=trust_case_limit,
        trust_case_ids=trust_case_ids,
        trust_items=trust_items,
        trust_errors=trust_errors,
        verified_count=trust_summary["verifiedCount"],
        review_required_count=trust_summary["reviewRequiredCount"],
        open_challenge_count=trust_summary["openChallengeCount"],
    )
    judge_workflow_coverage = build_ops_read_model_pack_judge_workflow_coverage_fn(
        role_nodes_rows=judge_workflow_role_nodes_rows,
        expected_role_order=judge_role_order,
    )
    case_chain_coverage = build_ops_read_model_pack_case_chain_coverage_fn(
        chain_rows=chain_rows,
    )
    case_lifecycle_overview = build_ops_read_model_pack_case_lifecycle_overview_fn(
        courtroom_items=courtroom_items,
    )
    policy_gate_rows: list[dict[str, Any]] = []
    for row in dependency_overview_rows:
        if not isinstance(row, dict):
            continue
        policy_version_token = str(row.get("policyVersion") or "").strip()
        if not policy_version_token:
            continue
        policy_gate_rows.append(
            {
                "policyVersion": policy_version_token,
                "gateDecision": row.get("latestGateDecision"),
                "gateSource": row.get("latestGateSource"),
                "overrideApplied": row.get("overrideApplied"),
            }
        )
    if not policy_gate_rows:
        simulation_items = (
            policy_gate_simulation.get("items")
            if isinstance(policy_gate_simulation.get("items"), list)
            else []
        )
        for row in simulation_items:
            if not isinstance(row, dict):
                continue
            policy_version_token = str(row.get("policyVersion") or "").strip()
            if not policy_version_token:
                continue
            fairness_gate = row.get("fairnessGate") if isinstance(row.get("fairnessGate"), dict) else {}
            simulated_gate = row.get("simulatedGate") if isinstance(row.get("simulatedGate"), dict) else {}
            decision = "pass" if str(simulated_gate.get("status") or "").strip().lower() == "pass" else "blocked"
            policy_gate_rows.append(
                {
                    "policyVersion": policy_version_token,
                    "gateDecision": decision,
                    "gateSource": fairness_gate.get("source"),
                    "overrideApplied": False,
                }
            )
    fairness_gate_overview = build_ops_read_model_pack_fairness_gate_overview_fn(
        courtroom_items=courtroom_items,
        policy_gate_rows=policy_gate_rows,
    )
    policy_kernel_binding = build_ops_read_model_pack_policy_kernel_binding_fn(
        active_policy_version=(
            governance_overview.get("activeVersions", {}).get("policyVersion")
            if isinstance(governance_overview.get("activeVersions"), dict)
            else None
        ),
        governance_dependency_items=governance_dependency_items,
        policy_gate_rows=policy_gate_rows,
        courtroom_items=courtroom_items,
    )
    read_contract = build_ops_read_model_pack_read_contract_fn()
    pack_filters = build_ops_read_model_pack_filters_fn(
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
    )

    return build_ops_read_model_pack_v5_payload_fn(
        generated_at=datetime.now(timezone.utc).isoformat(),
        fairness_dashboard=fairness_dashboard,
        fairness_calibration_advisor=fairness_calibration_advisor,
        panel_runtime_readiness=panel_runtime_readiness,
        registry_governance=governance_overview,
        registry_prompt_tool_governance=registry_prompt_tool_governance,
        courtroom_case_ids=courtroom_case_ids,
        courtroom_requested_case_limit=top_limit,
        courtroom_items=courtroom_items,
        courtroom_errors=courtroom_errors,
        courtroom_queue=courtroom_queue,
        courtroom_drilldown=courtroom_drilldown,
        review_queue=review_queue,
        review_trust_priority=review_trust_priority,
        evidence_claim_queue=evidence_claim_queue,
        trust_challenge_queue=trust_challenge_queue,
        policy_gate_simulation=policy_gate_simulation,
        adaptive_summary=adaptive_summary,
        trust_overview=trust_overview,
        judge_workflow_coverage=judge_workflow_coverage,
        case_lifecycle_overview=case_lifecycle_overview,
        case_chain_coverage=case_chain_coverage,
        fairness_gate_overview=fairness_gate_overview,
        policy_kernel_binding=policy_kernel_binding,
        read_contract=read_contract,
        pack_filters=pack_filters,
    )


def summarize_ops_read_model_pack_trust_items(
    *,
    trust_items: list[dict[str, Any]],
    open_challenge_states: set[str],
) -> dict[str, int]:
    verified_count = 0
    review_required_count = 0
    open_challenge_count = 0
    normalized_open_states = {
        str(state or "").strip().lower()
        for state in open_challenge_states
        if str(state or "").strip()
    }
    for item in trust_items:
        if bool(item.get("verdictVerified")):
            verified_count += 1
        if bool(item.get("reviewRequired")):
            review_required_count += 1
        challenge_state = str(item.get("challengeState") or "").strip().lower()
        if challenge_state in normalized_open_states:
            open_challenge_count += 1
    return {
        "verifiedCount": verified_count,
        "reviewRequiredCount": review_required_count,
        "openChallengeCount": open_challenge_count,
    }


def summarize_ops_read_model_pack_review_items(
    *,
    review_items: list[dict[str, Any]],
    review_trust_priority_items: list[dict[str, Any]],
    trust_challenge_queue_items: list[dict[str, Any]],
    open_challenge_states: set[str],
) -> dict[str, int]:
    review_high_risk_count = 0
    review_urgent_count = 0
    for row in review_items:
        risk_profile = row.get("riskProfile") if isinstance(row.get("riskProfile"), dict) else {}
        if str(risk_profile.get("level") or "").strip().lower() == "high":
            review_high_risk_count += 1
        if str(risk_profile.get("slaBucket") or "").strip().lower() == "urgent":
            review_urgent_count += 1

    review_unified_high_priority_count = 0
    review_trust_open_challenge_count = 0
    normalized_open_states = {
        str(state or "").strip().lower()
        for state in open_challenge_states
        if str(state or "").strip()
    }
    for row in review_trust_priority_items:
        unified_priority = (
            row.get("unifiedPriorityProfile")
            if isinstance(row.get("unifiedPriorityProfile"), dict)
            else {}
        )
        trust_challenge = (
            row.get("trustChallenge")
            if isinstance(row.get("trustChallenge"), dict)
            else {}
        )
        if str(unified_priority.get("level") or "").strip().lower() == "high":
            review_unified_high_priority_count += 1
        if str(trust_challenge.get("state") or "").strip().lower() in normalized_open_states:
            review_trust_open_challenge_count += 1

    trust_challenge_high_priority_count = 0
    trust_challenge_urgent_count = 0
    for row in trust_challenge_queue_items:
        priority_profile = (
            row.get("priorityProfile")
            if isinstance(row.get("priorityProfile"), dict)
            else {}
        )
        if str(priority_profile.get("level") or "").strip().lower() == "high":
            trust_challenge_high_priority_count += 1
        if str(priority_profile.get("slaBucket") or "").strip().lower() == "urgent":
            trust_challenge_urgent_count += 1

    return {
        "reviewHighRiskCount": review_high_risk_count,
        "reviewUrgentCount": review_urgent_count,
        "reviewUnifiedHighPriorityCount": review_unified_high_priority_count,
        "reviewTrustOpenChallengeCount": review_trust_open_challenge_count,
        "trustChallengeHighPriorityCount": trust_challenge_high_priority_count,
        "trustChallengeUrgentCount": trust_challenge_urgent_count,
    }


def build_ops_read_model_pack_judge_workflow_coverage(
    *,
    role_nodes_rows: list[list[dict[str, Any]] | None],
    expected_role_order: tuple[str, ...],
) -> dict[str, Any]:
    total_cases = len(role_nodes_rows)
    full_count = 0
    partial_count = 0
    missing_count = 0
    invalid_order_count = 0
    missing_role_counts = {role: 0 for role in expected_role_order}

    expected_roles = list(expected_role_order)
    expected_role_set = set(expected_role_order)
    for role_nodes in role_nodes_rows:
        if not isinstance(role_nodes, list) or not role_nodes:
            missing_count += 1
            for role in expected_role_order:
                missing_role_counts[role] += 1
            continue

        normalized_rows = [row for row in role_nodes if isinstance(row, dict)]
        normalized_roles = [
            str(row.get("role") or "").strip().lower()
            for row in normalized_rows
            if str(row.get("role") or "").strip()
        ]
        present_roles = set(normalized_roles)
        for role in expected_role_order:
            if role not in present_roles:
                missing_role_counts[role] += 1

        has_complete_set = present_roles.issuperset(expected_role_set)
        has_expected_order = normalized_roles == expected_roles
        has_expected_size = len(normalized_rows) == len(expected_role_order)
        has_expected_seq = all(
            normalized_rows[idx].get("seq") == idx + 1
            for idx in range(min(len(normalized_rows), len(expected_role_order)))
        )
        if has_complete_set and has_expected_order and has_expected_size and has_expected_seq:
            full_count += 1
            continue

        partial_count += 1
        if not has_expected_order or not has_expected_seq:
            invalid_order_count += 1

    full_coverage_rate = round(float(full_count) / float(total_cases), 4) if total_cases > 0 else 0.0
    return {
        "totalCases": total_cases,
        "fullCount": full_count,
        "partialCount": partial_count,
        "missingCount": missing_count,
        "invalidOrderCount": invalid_order_count,
        "missingRoleCounts": missing_role_counts,
        "fullCoverageRate": full_coverage_rate,
    }


def build_ops_read_model_pack_case_chain_coverage(
    *,
    chain_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    total_cases = len(chain_rows)
    object_presence = {key: 0 for key in OPS_READ_MODEL_PACK_V5_CHAIN_OBJECT_KEYS}
    complete_count = 0
    for row in chain_rows:
        is_complete = True
        for key in OPS_READ_MODEL_PACK_V5_CHAIN_OBJECT_KEYS:
            present = bool(row.get(key))
            if present:
                object_presence[key] += 1
            else:
                is_complete = False
        if is_complete:
            complete_count += 1
    missing_any_count = max(0, total_cases - complete_count)
    full_coverage_rate = round(float(complete_count) / float(total_cases), 4) if total_cases > 0 else 0.0
    missing_any_rate = round(float(missing_any_count) / float(total_cases), 4) if total_cases > 0 else 0.0
    return {
        "totalCases": total_cases,
        "completeCount": complete_count,
        "missingAnyCount": missing_any_count,
        "fullCoverageRate": full_coverage_rate,
        "missingAnyRate": missing_any_rate,
        "byObjectPresence": object_presence,
    }


def build_ops_read_model_pack_case_lifecycle_overview(
    *,
    courtroom_items: list[dict[str, Any]],
) -> dict[str, Any]:
    workflow_status_counts: dict[str, int] = {}
    lifecycle_bucket_counts: dict[str, int] = {}
    review_required_count = 0
    draw_pending_count = 0
    blocked_count = 0
    callback_failed_count = 0

    for row in courtroom_items:
        status = _normalize_optional_token(row.get("workflowStatus")) or "unknown"
        bucket = _normalize_optional_token(row.get("lifecycleBucket")) or "unknown"
        callback_status = _normalize_optional_token(row.get("callbackStatus"))
        workflow_status_counts[status] = workflow_status_counts.get(status, 0) + 1
        lifecycle_bucket_counts[bucket] = lifecycle_bucket_counts.get(bucket, 0) + 1
        if bool(row.get("reviewRequired")):
            review_required_count += 1
        if bool(row.get("needsDrawVote")) or bucket == "draw_pending":
            draw_pending_count += 1
        if bool(row.get("blocked")) or bucket == "blocked":
            blocked_count += 1
        if callback_status is not None and "failed" in callback_status:
            callback_failed_count += 1

    return {
        "totalCases": len(courtroom_items),
        "workflowStatusCounts": dict(
            sorted(workflow_status_counts.items(), key=lambda kv: kv[0])
        ),
        "lifecycleBucketCounts": dict(
            sorted(lifecycle_bucket_counts.items(), key=lambda kv: kv[0])
        ),
        "reviewRequiredCount": review_required_count,
        "drawPendingCount": draw_pending_count,
        "blockedCount": blocked_count,
        "callbackFailedCount": callback_failed_count,
    }


def build_ops_read_model_pack_read_contract() -> dict[str, Any]:
    return {
        "contractVersion": "ops_read_model_pack_v5",
        "businessRoutes": [
            "/internal/judge/cases/{case_id}",
            "/internal/judge/cases/{case_id}/courtroom-read-model",
            "/internal/judge/cases/{case_id}/trust/public-verify",
        ],
        "opsRoutes": [
            "/internal/judge/ops/read-model/pack",
            "/internal/judge/review/cases",
            "/internal/judge/cases/replay/reports",
            "/internal/judge/cases/{case_id}/alerts",
        ],
        "policyRoutes": [
            "/internal/judge/registries/governance/overview",
            "/internal/judge/registries/prompt-tool/governance",
            "/internal/judge/registries/policy/dependencies/health",
            "/internal/judge/registries/policy/gate-simulation",
        ],
        "fieldLayers": {
            "userVisible": [
                "winner",
                "needsDrawVote",
                "reviewRequired",
                "debateSummary",
                "sideAnalysis",
                "verdictReason",
            ],
            "opsVisible": [
                "workflowStatus",
                "callbackStatus",
                "lifecycleBucket",
                "caseLifecycleOverview",
                "caseChainCoverage",
                "fairnessGateOverview",
                "policyKernelBinding",
            ],
            "internalAudit": [
                "traceId",
                "judgeCore",
                "auditAlerts",
                "policyKernelHash",
                "policyGateSource",
                "eventSeq",
            ],
        },
        "errorSemantics": {
            "structuredErrorCodeRequired": True,
            "rawStringFallbackAllowed": False,
        },
    }


def _normalize_policy_gate_decision(value: Any, *, override_applied: bool) -> str:
    if override_applied:
        return "override_activated"
    token = str(value or "").strip().lower()
    if token in {"override_activated", "blocked", "pass"}:
        return token
    if token in {"blocked_to_draw", "violated"}:
        return "blocked"
    if token in {"pass_through", "accepted"}:
        return "pass"
    return "blocked"


def build_ops_read_model_pack_fairness_gate_overview(
    *,
    courtroom_items: list[dict[str, Any]],
    policy_gate_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    case_decision_counts = {
        "pass_through": 0,
        "blocked_to_draw": 0,
        "unknown": 0,
    }
    case_review_required_count = 0
    for row in courtroom_items:
        case_review_required_count += 1 if bool(row.get("reviewRequired")) else 0
        token = str(row.get("gateDecision") or "").strip().lower()
        if token in {"pass_through", "blocked_to_draw"}:
            case_decision_counts[token] += 1
        else:
            case_decision_counts["unknown"] += 1

    policy_gate_decision_counts = {
        "blocked": 0,
        "override_activated": 0,
        "pass": 0,
    }
    policy_gate_source_counts: dict[str, int] = {}
    policy_override_applied_count = 0
    for row in policy_gate_rows:
        override_applied = bool(row.get("overrideApplied"))
        decision = _normalize_policy_gate_decision(
            row.get("gateDecision"),
            override_applied=override_applied,
        )
        policy_gate_decision_counts[decision] = policy_gate_decision_counts.get(decision, 0) + 1
        source = str(row.get("gateSource") or "").strip().lower() or "unknown"
        policy_gate_source_counts[source] = policy_gate_source_counts.get(source, 0) + 1
        if override_applied:
            policy_override_applied_count += 1

    return {
        "totalCases": len(courtroom_items),
        "caseDecisionCounts": case_decision_counts,
        "caseReviewRequiredCount": case_review_required_count,
        "policyVersionCount": len(policy_gate_rows),
        "policyGateDecisionCounts": policy_gate_decision_counts,
        "policyGateSourceCounts": dict(
            sorted(policy_gate_source_counts.items(), key=lambda kv: kv[0])
        ),
        "policyOverrideAppliedCount": policy_override_applied_count,
    }


def build_ops_read_model_pack_policy_kernel_binding(
    *,
    active_policy_version: str | None,
    governance_dependency_items: list[dict[str, Any]],
    policy_gate_rows: list[dict[str, Any]],
    courtroom_items: list[dict[str, Any]],
) -> dict[str, Any]:
    governance_binding_by_policy: dict[str, dict[str, Any]] = {}
    for row in governance_dependency_items:
        if not isinstance(row, dict):
            continue
        policy_version = str(row.get("policyVersion") or "").strip()
        if not policy_version:
            continue
        kernel_version = str(row.get("policyKernelVersion") or "").strip() or None
        kernel_hash = str(row.get("policyKernelHash") or "").strip() or None
        governance_binding_by_policy[policy_version] = {
            "kernelVersion": kernel_version,
            "kernelHash": kernel_hash,
            "kernelBound": bool(kernel_version and kernel_hash),
        }

    tracked_policy_version_count = len(governance_binding_by_policy)
    kernel_bound_policy_count = sum(
        1 for row in governance_binding_by_policy.values() if bool(row.get("kernelBound"))
    )
    missing_kernel_binding_count = max(0, tracked_policy_version_count - kernel_bound_policy_count)

    override_applied_policy_count = sum(
        1 for row in policy_gate_rows if bool(row.get("overrideApplied"))
    )
    gate_decision_counts = {
        "blocked": 0,
        "override_activated": 0,
        "pass": 0,
    }
    for row in policy_gate_rows:
        decision = _normalize_policy_gate_decision(
            row.get("gateDecision"),
            override_applied=bool(row.get("overrideApplied")),
        )
        gate_decision_counts[decision] = gate_decision_counts.get(decision, 0) + 1

    case_policy_version_counts: dict[str, int] = {}
    missing_case_policy_version_count = 0
    case_missing_kernel_binding_count = 0
    for row in courtroom_items:
        policy_version = str(row.get("policyVersion") or "").strip()
        if not policy_version:
            missing_case_policy_version_count += 1
            continue
        case_policy_version_counts[policy_version] = case_policy_version_counts.get(policy_version, 0) + 1
        binding = governance_binding_by_policy.get(policy_version)
        if binding is None or not bool(binding.get("kernelBound")):
            case_missing_kernel_binding_count += 1

    return {
        "activePolicyVersion": str(active_policy_version or "").strip() or None,
        "trackedPolicyVersionCount": tracked_policy_version_count,
        "kernelBoundPolicyCount": kernel_bound_policy_count,
        "missingKernelBindingCount": missing_kernel_binding_count,
        "casePolicyVersionCount": len(case_policy_version_counts),
        "missingCasePolicyVersionCount": missing_case_policy_version_count,
        "caseMissingKernelBindingCount": case_missing_kernel_binding_count,
        "overrideAppliedPolicyCount": override_applied_policy_count,
        "casePolicyVersionCounts": dict(
            sorted(case_policy_version_counts.items(), key=lambda kv: kv[0])
        ),
        "gateDecisionCounts": gate_decision_counts,
    }


def _require_keys(*, section: str, payload: dict[str, Any], required_keys: tuple[str, ...]) -> None:
    missing = [key for key in required_keys if key not in payload]
    if missing:
        raise ValueError(f"{section}_missing_keys:{','.join(missing)}")


def _require_non_negative_int(*, section: str, field: str, value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{section}_{field}_not_non_negative_int")
    if value < 0:
        raise ValueError(f"{section}_{field}_not_non_negative_int")


def _require_positive_int(*, section: str, field: str, value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{section}_{field}_not_positive_int")
    if value <= 0:
        raise ValueError(f"{section}_{field}_not_positive_int")


def validate_ops_read_model_pack_v5_contract(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("ops_read_model_pack_payload_not_dict")
    _require_keys(
        section="ops_read_model_pack",
        payload=payload,
        required_keys=OPS_READ_MODEL_PACK_V5_TOP_LEVEL_KEYS,
    )

    generated_at = payload.get("generatedAt")
    if not isinstance(generated_at, str) or not generated_at.strip():
        raise ValueError("ops_read_model_pack_generatedAt_invalid")

    courtroom_read_model = payload.get("courtroomReadModel")
    if not isinstance(courtroom_read_model, dict):
        raise ValueError("ops_read_model_pack_courtroomReadModel_not_dict")
    _require_keys(
        section="ops_read_model_pack_courtroomReadModel",
        payload=courtroom_read_model,
        required_keys=OPS_READ_MODEL_PACK_V5_COURTROOM_READ_MODEL_KEYS,
    )
    _require_non_negative_int(
        section="ops_read_model_pack_courtroomReadModel",
        field="count",
        value=courtroom_read_model.get("count"),
    )
    _require_non_negative_int(
        section="ops_read_model_pack_courtroomReadModel",
        field="errorCount",
        value=courtroom_read_model.get("errorCount"),
    )
    if not isinstance(courtroom_read_model.get("items"), list):
        raise ValueError("ops_read_model_pack_courtroomReadModel_items_not_list")
    if not isinstance(courtroom_read_model.get("errors"), list):
        raise ValueError("ops_read_model_pack_courtroomReadModel_errors_not_list")
    if int(courtroom_read_model.get("count") or 0) != len(courtroom_read_model.get("items") or []):
        raise ValueError("ops_read_model_pack_courtroomReadModel_count_mismatch")
    if int(courtroom_read_model.get("errorCount") or 0) != len(courtroom_read_model.get("errors") or []):
        raise ValueError("ops_read_model_pack_courtroomReadModel_errorCount_mismatch")
    for row in courtroom_read_model.get("items") or []:
        if not isinstance(row, dict):
            raise ValueError("ops_read_model_pack_courtroomReadModel_item_not_dict")
        _require_keys(
            section="ops_read_model_pack_courtroomReadModel_item",
            payload=row,
            required_keys=OPS_READ_MODEL_PACK_V5_COURTROOM_ITEM_KEYS,
        )
        _require_non_negative_int(
            section="ops_read_model_pack_courtroomReadModel_item",
            field="keyClaimCount",
            value=row.get("keyClaimCount"),
        )
        _require_non_negative_int(
            section="ops_read_model_pack_courtroomReadModel_item",
            field="decisiveEvidenceCount",
            value=row.get("decisiveEvidenceCount"),
        )
        _require_non_negative_int(
            section="ops_read_model_pack_courtroomReadModel_item",
            field="pivotalMomentCount",
            value=row.get("pivotalMomentCount"),
        )
        for field in ("reviewRequired", "needsDrawVote", "blocked"):
            if not isinstance(row.get(field), bool):
                raise ValueError(
                    f"ops_read_model_pack_courtroomReadModel_item_{field}_not_bool"
                )
        lifecycle_bucket = row.get("lifecycleBucket")
        if not isinstance(lifecycle_bucket, str) or not lifecycle_bucket.strip():
            raise ValueError(
                "ops_read_model_pack_courtroomReadModel_item_lifecycleBucket_invalid"
            )
        for field in (
            "workflowStatus",
            "callbackStatus",
            "winner",
            "policyVersion",
            "policyKernelVersion",
            "policyKernelHash",
            "policyGateDecision",
            "policyGateSource",
        ):
            value = row.get(field)
            if value is not None and not isinstance(value, str):
                raise ValueError(
                    f"ops_read_model_pack_courtroomReadModel_item_{field}_not_string"
                )
        policy_override_applied = row.get("policyOverrideApplied")
        if policy_override_applied is not None and not isinstance(policy_override_applied, bool):
            raise ValueError(
                "ops_read_model_pack_courtroomReadModel_item_policyOverrideApplied_not_bool"
            )
    for row in courtroom_read_model.get("errors") or []:
        if not isinstance(row, dict):
            raise ValueError("ops_read_model_pack_courtroomReadModel_error_not_dict")
        _require_keys(
            section="ops_read_model_pack_courtroomReadModel_error",
            payload=row,
            required_keys=OPS_READ_MODEL_PACK_V5_COURTROOM_ERROR_KEYS,
        )

    adaptive_summary = payload.get("adaptiveSummary")
    if not isinstance(adaptive_summary, dict):
        raise ValueError("ops_read_model_pack_adaptiveSummary_not_dict")
    _require_keys(
        section="ops_read_model_pack_adaptiveSummary",
        payload=adaptive_summary,
        required_keys=OPS_READ_MODEL_PACK_V5_ADAPTIVE_SUMMARY_KEYS,
    )
    if not isinstance(adaptive_summary.get("calibrationGatePassed"), bool):
        raise ValueError("ops_read_model_pack_adaptiveSummary_calibrationGatePassed_not_bool")
    for field in _OPS_READ_MODEL_PACK_V5_ADAPTIVE_COUNT_KEYS:
        _require_non_negative_int(
            section="ops_read_model_pack_adaptiveSummary",
            field=field,
            value=adaptive_summary.get(field),
        )

    trust_overview = payload.get("trustOverview")
    if not isinstance(trust_overview, dict):
        raise ValueError("ops_read_model_pack_trustOverview_not_dict")
    _require_keys(
        section="ops_read_model_pack_trustOverview",
        payload=trust_overview,
        required_keys=OPS_READ_MODEL_PACK_V5_TRUST_OVERVIEW_KEYS,
    )
    if not isinstance(trust_overview.get("included"), bool):
        raise ValueError("ops_read_model_pack_trustOverview_included_not_bool")
    if not isinstance(trust_overview.get("caseIds"), list):
        raise ValueError("ops_read_model_pack_trustOverview_caseIds_not_list")
    if not isinstance(trust_overview.get("items"), list):
        raise ValueError("ops_read_model_pack_trustOverview_items_not_list")
    if not isinstance(trust_overview.get("errors"), list):
        raise ValueError("ops_read_model_pack_trustOverview_errors_not_list")
    for field in _OPS_READ_MODEL_PACK_V5_TRUST_OVERVIEW_COUNT_KEYS:
        _require_non_negative_int(
            section="ops_read_model_pack_trustOverview",
            field=field,
            value=trust_overview.get(field),
        )
    if int(trust_overview.get("count") or 0) != len(trust_overview.get("items") or []):
        raise ValueError("ops_read_model_pack_trustOverview_count_mismatch")
    if int(trust_overview.get("errorCount") or 0) != len(trust_overview.get("errors") or []):
        raise ValueError("ops_read_model_pack_trustOverview_errorCount_mismatch")
    if int(trust_overview.get("verifiedCount") or 0) > int(trust_overview.get("count") or 0):
        raise ValueError("ops_read_model_pack_trustOverview_verifiedCount_exceeds_count")

    judge_workflow_coverage = payload.get("judgeWorkflowCoverage")
    if not isinstance(judge_workflow_coverage, dict):
        raise ValueError("ops_read_model_pack_judgeWorkflowCoverage_not_dict")
    _require_keys(
        section="ops_read_model_pack_judgeWorkflowCoverage",
        payload=judge_workflow_coverage,
        required_keys=OPS_READ_MODEL_PACK_V5_JUDGE_WORKFLOW_COVERAGE_KEYS,
    )
    for field in (
        "totalCases",
        "fullCount",
        "partialCount",
        "missingCount",
        "invalidOrderCount",
    ):
        _require_non_negative_int(
            section="ops_read_model_pack_judgeWorkflowCoverage",
            field=field,
            value=judge_workflow_coverage.get(field),
        )
    missing_role_counts = judge_workflow_coverage.get("missingRoleCounts")
    if not isinstance(missing_role_counts, dict):
        raise ValueError("ops_read_model_pack_judgeWorkflowCoverage_missingRoleCounts_not_dict")
    for role, count in missing_role_counts.items():
        _require_non_negative_int(
            section="ops_read_model_pack_judgeWorkflowCoverage_missingRoleCounts",
            field=str(role),
            value=count,
        )
    total_cases = int(judge_workflow_coverage.get("totalCases") or 0)
    full_count = int(judge_workflow_coverage.get("fullCount") or 0)
    partial_count = int(judge_workflow_coverage.get("partialCount") or 0)
    missing_count = int(judge_workflow_coverage.get("missingCount") or 0)
    if full_count + partial_count + missing_count != total_cases:
        raise ValueError("ops_read_model_pack_judgeWorkflowCoverage_count_mismatch")
    full_coverage_rate = judge_workflow_coverage.get("fullCoverageRate")
    if isinstance(full_coverage_rate, bool) or not isinstance(full_coverage_rate, (int, float)):
        raise ValueError("ops_read_model_pack_judgeWorkflowCoverage_fullCoverageRate_invalid")
    if float(full_coverage_rate) < 0.0 or float(full_coverage_rate) > 1.0:
        raise ValueError("ops_read_model_pack_judgeWorkflowCoverage_fullCoverageRate_invalid")

    case_chain_coverage = payload.get("caseChainCoverage")
    if not isinstance(case_chain_coverage, dict):
        raise ValueError("ops_read_model_pack_caseChainCoverage_not_dict")
    _require_keys(
        section="ops_read_model_pack_caseChainCoverage",
        payload=case_chain_coverage,
        required_keys=OPS_READ_MODEL_PACK_V5_CASE_CHAIN_COVERAGE_KEYS,
    )
    for field in ("totalCases", "completeCount", "missingAnyCount"):
        _require_non_negative_int(
            section="ops_read_model_pack_caseChainCoverage",
            field=field,
            value=case_chain_coverage.get(field),
        )
    for field in ("fullCoverageRate", "missingAnyRate"):
        value = case_chain_coverage.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"ops_read_model_pack_caseChainCoverage_{field}_invalid")
        if float(value) < 0.0 or float(value) > 1.0:
            raise ValueError(f"ops_read_model_pack_caseChainCoverage_{field}_invalid")
    object_presence = case_chain_coverage.get("byObjectPresence")
    if not isinstance(object_presence, dict):
        raise ValueError("ops_read_model_pack_caseChainCoverage_byObjectPresence_not_dict")
    _require_keys(
        section="ops_read_model_pack_caseChainCoverage_byObjectPresence",
        payload=object_presence,
        required_keys=OPS_READ_MODEL_PACK_V5_CHAIN_OBJECT_KEYS,
    )
    for field in OPS_READ_MODEL_PACK_V5_CHAIN_OBJECT_KEYS:
        _require_non_negative_int(
            section="ops_read_model_pack_caseChainCoverage_byObjectPresence",
            field=field,
            value=object_presence.get(field),
        )

    case_lifecycle_overview = payload.get("caseLifecycleOverview")
    if not isinstance(case_lifecycle_overview, dict):
        raise ValueError("ops_read_model_pack_caseLifecycleOverview_not_dict")
    _require_keys(
        section="ops_read_model_pack_caseLifecycleOverview",
        payload=case_lifecycle_overview,
        required_keys=OPS_READ_MODEL_PACK_V5_CASE_LIFECYCLE_OVERVIEW_KEYS,
    )
    for field in (
        "totalCases",
        "reviewRequiredCount",
        "drawPendingCount",
        "blockedCount",
        "callbackFailedCount",
    ):
        _require_non_negative_int(
            section="ops_read_model_pack_caseLifecycleOverview",
            field=field,
            value=case_lifecycle_overview.get(field),
        )
    lifecycle_total_cases = int(case_lifecycle_overview.get("totalCases") or 0)
    for field in ("workflowStatusCounts", "lifecycleBucketCounts"):
        value = case_lifecycle_overview.get(field)
        if not isinstance(value, dict):
            raise ValueError(f"ops_read_model_pack_caseLifecycleOverview_{field}_not_dict")
        total_count = 0
        for key, count in value.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError(
                    f"ops_read_model_pack_caseLifecycleOverview_{field}_key_invalid"
                )
            _require_non_negative_int(
                section=f"ops_read_model_pack_caseLifecycleOverview_{field}",
                field=key,
                value=count,
            )
            total_count += int(count)
        if total_count != lifecycle_total_cases:
            raise ValueError(
                f"ops_read_model_pack_caseLifecycleOverview_{field}_count_mismatch"
            )

    fairness_gate_overview = payload.get("fairnessGateOverview")
    if not isinstance(fairness_gate_overview, dict):
        raise ValueError("ops_read_model_pack_fairnessGateOverview_not_dict")
    _require_keys(
        section="ops_read_model_pack_fairnessGateOverview",
        payload=fairness_gate_overview,
        required_keys=OPS_READ_MODEL_PACK_V5_FAIRNESS_GATE_OVERVIEW_KEYS,
    )
    for field in (
        "totalCases",
        "caseReviewRequiredCount",
        "policyVersionCount",
        "policyOverrideAppliedCount",
    ):
        _require_non_negative_int(
            section="ops_read_model_pack_fairnessGateOverview",
            field=field,
            value=fairness_gate_overview.get(field),
        )
    for field in (
        "caseDecisionCounts",
        "policyGateDecisionCounts",
        "policyGateSourceCounts",
    ):
        value = fairness_gate_overview.get(field)
        if not isinstance(value, dict):
            raise ValueError(f"ops_read_model_pack_fairnessGateOverview_{field}_not_dict")

    policy_kernel_binding = payload.get("policyKernelBinding")
    if not isinstance(policy_kernel_binding, dict):
        raise ValueError("ops_read_model_pack_policyKernelBinding_not_dict")
    _require_keys(
        section="ops_read_model_pack_policyKernelBinding",
        payload=policy_kernel_binding,
        required_keys=OPS_READ_MODEL_PACK_V5_POLICY_KERNEL_BINDING_KEYS,
    )
    active_policy_version = policy_kernel_binding.get("activePolicyVersion")
    if active_policy_version is not None and not isinstance(active_policy_version, str):
        raise ValueError("ops_read_model_pack_policyKernelBinding_activePolicyVersion_not_string")
    for field in (
        "trackedPolicyVersionCount",
        "kernelBoundPolicyCount",
        "missingKernelBindingCount",
        "casePolicyVersionCount",
        "missingCasePolicyVersionCount",
        "caseMissingKernelBindingCount",
        "overrideAppliedPolicyCount",
    ):
        _require_non_negative_int(
            section="ops_read_model_pack_policyKernelBinding",
            field=field,
            value=policy_kernel_binding.get(field),
        )
    for field in ("casePolicyVersionCounts", "gateDecisionCounts"):
        value = policy_kernel_binding.get(field)
        if not isinstance(value, dict):
            raise ValueError(f"ops_read_model_pack_policyKernelBinding_{field}_not_dict")

    read_contract = payload.get("readContract")
    if not isinstance(read_contract, dict):
        raise ValueError("ops_read_model_pack_readContract_not_dict")
    _require_keys(
        section="ops_read_model_pack_readContract",
        payload=read_contract,
        required_keys=OPS_READ_MODEL_PACK_V5_READ_CONTRACT_KEYS,
    )
    contract_version = read_contract.get("contractVersion")
    if not isinstance(contract_version, str) or not contract_version.strip():
        raise ValueError("ops_read_model_pack_readContract_contractVersion_invalid")
    for field in ("businessRoutes", "opsRoutes", "policyRoutes"):
        value = read_contract.get(field)
        if not isinstance(value, list) or not value:
            raise ValueError(f"ops_read_model_pack_readContract_{field}_not_non_empty_list")
        for row in value:
            if not isinstance(row, str) or not row.strip():
                raise ValueError(f"ops_read_model_pack_readContract_{field}_item_invalid")
    field_layers = read_contract.get("fieldLayers")
    if not isinstance(field_layers, dict):
        raise ValueError("ops_read_model_pack_readContract_fieldLayers_not_dict")
    _require_keys(
        section="ops_read_model_pack_readContract_fieldLayers",
        payload=field_layers,
        required_keys=OPS_READ_MODEL_PACK_V5_FIELD_LAYER_KEYS,
    )
    for field in OPS_READ_MODEL_PACK_V5_FIELD_LAYER_KEYS:
        value = field_layers.get(field)
        if not isinstance(value, list) or not value:
            raise ValueError(f"ops_read_model_pack_readContract_fieldLayers_{field}_invalid")
        for row in value:
            if not isinstance(row, str) or not row.strip():
                raise ValueError(
                    f"ops_read_model_pack_readContract_fieldLayers_{field}_item_invalid"
                )
    error_semantics = read_contract.get("errorSemantics")
    if not isinstance(error_semantics, dict):
        raise ValueError("ops_read_model_pack_readContract_errorSemantics_not_dict")
    _require_keys(
        section="ops_read_model_pack_readContract_errorSemantics",
        payload=error_semantics,
        required_keys=OPS_READ_MODEL_PACK_V5_ERROR_SEMANTIC_KEYS,
    )
    if error_semantics.get("structuredErrorCodeRequired") is not True:
        raise ValueError(
            "ops_read_model_pack_readContract_structuredErrorCodeRequired_not_true"
        )
    if error_semantics.get("rawStringFallbackAllowed") is not False:
        raise ValueError(
            "ops_read_model_pack_readContract_rawStringFallbackAllowed_not_false"
        )

    filters = payload.get("filters")
    if not isinstance(filters, dict):
        raise ValueError("ops_read_model_pack_filters_not_dict")
    _require_keys(
        section="ops_read_model_pack_filters",
        payload=filters,
        required_keys=OPS_READ_MODEL_PACK_V5_FILTER_KEYS,
    )
    if not isinstance(filters.get("includeCaseTrust"), bool):
        raise ValueError("ops_read_model_pack_filters_includeCaseTrust_not_bool")
    for field in _OPS_READ_MODEL_PACK_V5_FILTER_POSITIVE_INT_KEYS:
        _require_positive_int(
            section="ops_read_model_pack_filters",
            field=field,
            value=filters.get(field),
        )

    for section_key, required_key in OPS_READ_MODEL_PACK_V5_REQUIRED_AGGREGATIONS:
        section_payload = payload.get(section_key)
        if not isinstance(section_payload, dict):
            raise ValueError(f"ops_read_model_pack_{section_key}_not_dict")
        if required_key not in section_payload:
            raise ValueError(f"ops_read_model_pack_{section_key}_missing_{required_key}")


def build_ops_read_model_pack_v5_payload(
    *,
    generated_at: str,
    fairness_dashboard: dict[str, Any],
    fairness_calibration_advisor: dict[str, Any],
    panel_runtime_readiness: dict[str, Any],
    registry_governance: dict[str, Any],
    registry_prompt_tool_governance: dict[str, Any],
    courtroom_case_ids: list[int],
    courtroom_requested_case_limit: int,
    courtroom_items: list[dict[str, Any]],
    courtroom_errors: list[dict[str, Any]],
    courtroom_queue: dict[str, Any],
    courtroom_drilldown: dict[str, Any],
    review_queue: dict[str, Any],
    review_trust_priority: dict[str, Any],
    evidence_claim_queue: dict[str, Any],
    trust_challenge_queue: dict[str, Any],
    policy_gate_simulation: dict[str, Any],
    adaptive_summary: dict[str, Any],
    trust_overview: dict[str, Any],
    judge_workflow_coverage: dict[str, Any],
    case_lifecycle_overview: dict[str, Any],
    case_chain_coverage: dict[str, Any],
    fairness_gate_overview: dict[str, Any],
    policy_kernel_binding: dict[str, Any],
    read_contract: dict[str, Any],
    pack_filters: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "generatedAt": generated_at,
        "fairnessDashboard": fairness_dashboard,
        "fairnessCalibrationAdvisor": fairness_calibration_advisor,
        "panelRuntimeReadiness": panel_runtime_readiness,
        "registryGovernance": registry_governance,
        "registryPromptToolGovernance": registry_prompt_tool_governance,
        "courtroomReadModel": {
            "requestedCaseLimit": int(courtroom_requested_case_limit),
            "caseIds": list(courtroom_case_ids),
            "count": len(courtroom_items),
            "errorCount": len(courtroom_errors),
            "items": list(courtroom_items),
            "errors": list(courtroom_errors),
        },
        "courtroomQueue": courtroom_queue,
        "courtroomDrilldown": courtroom_drilldown,
        "reviewQueue": review_queue,
        "reviewTrustPriority": review_trust_priority,
        "evidenceClaimQueue": evidence_claim_queue,
        "trustChallengeQueue": trust_challenge_queue,
        "policyGateSimulation": policy_gate_simulation,
        "adaptiveSummary": adaptive_summary,
        "trustOverview": trust_overview,
        "judgeWorkflowCoverage": judge_workflow_coverage,
        "caseLifecycleOverview": case_lifecycle_overview,
        "caseChainCoverage": case_chain_coverage,
        "fairnessGateOverview": fairness_gate_overview,
        "policyKernelBinding": policy_kernel_binding,
        "readContract": read_contract,
        "filters": pack_filters,
    }
    validate_ops_read_model_pack_v5_contract(payload)
    return payload
