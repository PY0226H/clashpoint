from __future__ import annotations

from typing import Any

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
    "winner",
    "reviewRequired",
    "gateDecision",
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


def _to_int(value: Any, *, default: int = 0) -> int:
    try:
        if isinstance(value, bool):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


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
        "filters": pack_filters,
    }
    validate_ops_read_model_pack_v5_contract(payload)
    return payload
