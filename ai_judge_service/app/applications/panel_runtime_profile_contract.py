from __future__ import annotations

from typing import Any

PANEL_RUNTIME_PROFILE_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "count",
    "returned",
    "items",
    "aggregations",
    "filters",
)

PANEL_RUNTIME_PROFILE_ITEM_KEYS: tuple[str, ...] = (
    "caseId",
    "traceId",
    "dispatchType",
    "workflowStatus",
    "updatedAt",
    "winner",
    "gateConclusion",
    "reviewRequired",
    "hasOpenReview",
    "challengeState",
    "panelDisagreement",
    "judgeId",
    "profileId",
    "profileSource",
    "modelStrategy",
    "strategySlot",
    "scoreSource",
    "decisionMargin",
    "promptVersion",
    "toolsetVersion",
    "domainSlot",
    "runtimeStage",
    "adaptiveEnabled",
    "candidateModels",
    "strategyMetadata",
    "policyVersion",
    "shadowEnabled",
    "shadowModelStrategy",
    "shadowDecisionAgreement",
    "shadowCostEstimate",
    "shadowLatencyEstimate",
    "shadowDriftSignals",
    "shadowReleaseGateSignal",
    "shadowEvaluation",
    "runtimeProfile",
)

PANEL_RUNTIME_PROFILE_PANEL_DISAGREEMENT_KEYS: tuple[str, ...] = (
    "high",
    "ratio",
    "ratioMax",
    "reasons",
    "majorityWinner",
    "voteBySide",
)

PANEL_RUNTIME_PROFILE_AGGREGATIONS_KEYS: tuple[str, ...] = (
    "totalMatched",
    "reviewRequiredCount",
    "openReviewCount",
    "panelHighDisagreementCount",
    "avgPanelDisagreementRatio",
    "byJudgeId",
    "byProfileId",
    "byModelStrategy",
    "byStrategySlot",
    "byDomainSlot",
    "byProfileSource",
    "byPolicyVersion",
    "byShadowModelStrategy",
    "winnerCounts",
    "shadowEnabledCount",
    "shadowAgreementCount",
    "shadowDriftSignalCount",
    "avgShadowDecisionAgreement",
    "avgShadowCostEstimate",
    "avgShadowLatencyEstimate",
)

PANEL_RUNTIME_PROFILE_FILTER_KEYS: tuple[str, ...] = (
    "status",
    "dispatchType",
    "winner",
    "policyVersion",
    "hasOpenReview",
    "gateConclusion",
    "challengeState",
    "reviewRequired",
    "panelHighDisagreement",
    "judgeId",
    "profileSource",
    "profileId",
    "modelStrategy",
    "strategySlot",
    "domainSlot",
    "sortBy",
    "sortOrder",
    "offset",
    "limit",
)

PANEL_RUNTIME_PROFILE_WINNER_COUNT_KEYS: tuple[str, ...] = (
    "pro",
    "con",
    "draw",
    "unknown",
)


def _required_keys_missing(payload: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    return [key for key in keys if key not in payload]


def _assert_required_keys(
    *,
    section: str,
    payload: dict[str, Any],
    keys: tuple[str, ...],
) -> None:
    missing = _required_keys_missing(payload, keys)
    if missing:
        raise ValueError(f"{section}_missing_keys:{','.join(sorted(missing))}")


def _non_negative_int(value: Any, *, default: int = 0) -> int:
    try:
        if isinstance(value, bool):
            return default
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, parsed)


def _assert_count_map(
    *,
    section: str,
    payload: Any,
    total: int,
    required_keys: tuple[str, ...] | None = None,
) -> None:
    if not isinstance(payload, dict):
        raise ValueError(f"{section}_not_dict")
    if required_keys is not None:
        _assert_required_keys(section=section, payload=payload, keys=required_keys)
    count_sum = sum(_non_negative_int(value, default=0) for value in payload.values())
    if count_sum != total:
        raise ValueError(f"{section}_sum_mismatch")


def _validate_item(payload: dict[str, Any]) -> None:
    _assert_required_keys(
        section="panel_runtime_profile_item",
        payload=payload,
        keys=PANEL_RUNTIME_PROFILE_ITEM_KEYS,
    )
    case_id = _non_negative_int(payload.get("caseId"), default=0)
    if case_id <= 0:
        raise ValueError("panel_runtime_profile_item_case_id_invalid")
    judge_id = str(payload.get("judgeId") or "").strip()
    if not judge_id:
        raise ValueError("panel_runtime_profile_item_judge_id_empty")
    profile_source = str(payload.get("profileSource") or "").strip().lower()
    if not profile_source:
        raise ValueError("panel_runtime_profile_item_profile_source_empty")
    if not isinstance(payload.get("candidateModels"), list):
        raise ValueError("panel_runtime_profile_item_candidate_models_not_list")
    if not isinstance(payload.get("strategyMetadata"), dict):
        raise ValueError("panel_runtime_profile_item_strategy_metadata_not_dict")
    if not isinstance(payload.get("shadowDriftSignals"), list):
        raise ValueError("panel_runtime_profile_item_shadow_drift_signals_not_list")
    if not isinstance(payload.get("shadowReleaseGateSignal"), dict):
        raise ValueError("panel_runtime_profile_item_shadow_release_gate_signal_not_dict")
    if not isinstance(payload.get("shadowEvaluation"), dict):
        raise ValueError("panel_runtime_profile_item_shadow_evaluation_not_dict")
    if not isinstance(payload.get("runtimeProfile"), dict):
        raise ValueError("panel_runtime_profile_item_runtime_profile_not_dict")
    panel = payload.get("panelDisagreement")
    if not isinstance(panel, dict):
        raise ValueError("panel_runtime_profile_item_panel_disagreement_not_dict")
    _assert_required_keys(
        section="panel_runtime_profile_item_panel_disagreement",
        payload=panel,
        keys=PANEL_RUNTIME_PROFILE_PANEL_DISAGREEMENT_KEYS,
    )
    if not isinstance(panel.get("reasons"), list):
        raise ValueError("panel_runtime_profile_item_panel_disagreement_reasons_not_list")
    if not isinstance(panel.get("voteBySide"), dict):
        raise ValueError("panel_runtime_profile_item_panel_disagreement_vote_by_side_not_dict")


def validate_panel_runtime_profile_contract(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("panel_runtime_profile_payload_not_dict")
    _assert_required_keys(
        section="panel_runtime_profile",
        payload=payload,
        keys=PANEL_RUNTIME_PROFILE_TOP_LEVEL_KEYS,
    )
    count = _non_negative_int(payload.get("count"), default=0)
    returned = _non_negative_int(payload.get("returned"), default=0)
    if returned > count:
        raise ValueError("panel_runtime_profile_returned_exceeds_count")

    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("panel_runtime_profile_items_not_list")
    if len(items) != returned:
        raise ValueError("panel_runtime_profile_returned_mismatch")
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("panel_runtime_profile_item_not_dict")
        _validate_item(item)

    aggregations = payload.get("aggregations")
    if not isinstance(aggregations, dict):
        raise ValueError("panel_runtime_profile_aggregations_not_dict")
    _assert_required_keys(
        section="panel_runtime_profile_aggregations",
        payload=aggregations,
        keys=PANEL_RUNTIME_PROFILE_AGGREGATIONS_KEYS,
    )

    total_matched = _non_negative_int(aggregations.get("totalMatched"), default=0)
    if total_matched != count:
        raise ValueError("panel_runtime_profile_total_matched_mismatch")

    for key in (
        "reviewRequiredCount",
        "openReviewCount",
        "panelHighDisagreementCount",
    ):
        value = _non_negative_int(aggregations.get(key), default=0)
        if value > total_matched:
            raise ValueError(f"panel_runtime_profile_{key}_exceeds_total")
    for key in (
        "shadowEnabledCount",
        "shadowAgreementCount",
        "shadowDriftSignalCount",
    ):
        value = _non_negative_int(aggregations.get(key), default=0)
        if value > total_matched:
            raise ValueError(f"panel_runtime_profile_{key}_exceeds_total")

    avg_panel_disagreement_ratio = float(aggregations.get("avgPanelDisagreementRatio") or 0.0)
    if avg_panel_disagreement_ratio < 0:
        raise ValueError("panel_runtime_profile_avg_panel_disagreement_ratio_invalid")
    for key in (
        "avgShadowDecisionAgreement",
        "avgShadowCostEstimate",
        "avgShadowLatencyEstimate",
    ):
        value = float(aggregations.get(key) or 0.0)
        if value < 0:
            raise ValueError(f"panel_runtime_profile_{key}_invalid")

    _assert_count_map(
        section="panel_runtime_profile_by_judge_id",
        payload=aggregations.get("byJudgeId"),
        total=total_matched,
    )
    _assert_count_map(
        section="panel_runtime_profile_by_profile_id",
        payload=aggregations.get("byProfileId"),
        total=total_matched,
    )
    _assert_count_map(
        section="panel_runtime_profile_by_model_strategy",
        payload=aggregations.get("byModelStrategy"),
        total=total_matched,
    )
    _assert_count_map(
        section="panel_runtime_profile_by_strategy_slot",
        payload=aggregations.get("byStrategySlot"),
        total=total_matched,
    )
    _assert_count_map(
        section="panel_runtime_profile_by_domain_slot",
        payload=aggregations.get("byDomainSlot"),
        total=total_matched,
    )
    _assert_count_map(
        section="panel_runtime_profile_by_profile_source",
        payload=aggregations.get("byProfileSource"),
        total=total_matched,
    )
    _assert_count_map(
        section="panel_runtime_profile_by_policy_version",
        payload=aggregations.get("byPolicyVersion"),
        total=total_matched,
    )
    _assert_count_map(
        section="panel_runtime_profile_by_shadow_model_strategy",
        payload=aggregations.get("byShadowModelStrategy"),
        total=total_matched,
    )
    _assert_count_map(
        section="panel_runtime_profile_winner_counts",
        payload=aggregations.get("winnerCounts"),
        total=total_matched,
        required_keys=PANEL_RUNTIME_PROFILE_WINNER_COUNT_KEYS,
    )

    filters = payload.get("filters")
    if not isinstance(filters, dict):
        raise ValueError("panel_runtime_profile_filters_not_dict")
    _assert_required_keys(
        section="panel_runtime_profile_filters",
        payload=filters,
        keys=PANEL_RUNTIME_PROFILE_FILTER_KEYS,
    )
    limit = _non_negative_int(filters.get("limit"), default=0)
    if limit <= 0:
        raise ValueError("panel_runtime_profile_filters_limit_invalid")
