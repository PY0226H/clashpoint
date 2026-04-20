from __future__ import annotations

from typing import Any

CASE_FAIRNESS_DETAIL_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "caseId",
    "dispatchType",
    "item",
)

CASE_FAIRNESS_LIST_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "count",
    "returned",
    "items",
    "aggregations",
    "filters",
)

CASE_FAIRNESS_ITEM_KEYS: tuple[str, ...] = (
    "caseId",
    "dispatchType",
    "traceId",
    "workflowStatus",
    "updatedAt",
    "winner",
    "reviewRequired",
    "gateConclusion",
    "errorCodes",
    "panelDisagreement",
    "driftSummary",
    "shadowSummary",
    "challengeLink",
)

CASE_FAIRNESS_PANEL_DISAGREEMENT_KEYS: tuple[str, ...] = (
    "high",
    "ratio",
    "ratioMax",
    "reasons",
    "majorityWinner",
    "voteBySide",
    "runtimeProfiles",
)

CASE_FAIRNESS_DRIFT_SUMMARY_KEYS: tuple[str, ...] = (
    "policyVersion",
    "latestRun",
    "thresholdBreaches",
    "driftBreaches",
    "hasThresholdBreach",
    "hasDriftBreach",
)

CASE_FAIRNESS_SHADOW_SUMMARY_KEYS: tuple[str, ...] = (
    "policyVersion",
    "latestRun",
    "benchmarkRunId",
    "breaches",
    "hasShadowBreach",
)

CASE_FAIRNESS_CHALLENGE_LINK_KEYS: tuple[str, ...] = (
    "latest",
    "hasOpenReview",
)

CASE_FAIRNESS_AGGREGATIONS_KEYS: tuple[str, ...] = (
    "totalMatched",
    "reviewRequiredCount",
    "openReviewCount",
    "driftBreachCount",
    "thresholdBreachCount",
    "shadowBreachCount",
    "panelHighDisagreementCount",
    "withChallengeCount",
    "gateConclusionCounts",
    "winnerCounts",
    "challengeStateCounts",
    "policyVersionCounts",
)

CASE_FAIRNESS_FILTER_KEYS: tuple[str, ...] = (
    "status",
    "dispatchType",
    "winner",
    "policyVersion",
    "hasDriftBreach",
    "hasThresholdBreach",
    "hasShadowBreach",
    "hasOpenReview",
    "gateConclusion",
    "challengeState",
    "sortBy",
    "sortOrder",
    "reviewRequired",
    "panelHighDisagreement",
    "offset",
    "limit",
)

CASE_FAIRNESS_GATE_COUNT_KEYS: tuple[str, ...] = (
    "auto_passed",
    "review_required",
    "benchmark_attention_required",
    "unknown",
)

CASE_FAIRNESS_WINNER_COUNT_KEYS: tuple[str, ...] = (
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


def _assert_optional_dict(section: str, value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValueError(f"{section}_not_dict")


def _assert_item_contract(payload: dict[str, Any], *, section: str) -> None:
    _assert_required_keys(
        section=section,
        payload=payload,
        keys=CASE_FAIRNESS_ITEM_KEYS,
    )
    case_id = _non_negative_int(payload.get("caseId"), default=0)
    if case_id <= 0:
        raise ValueError(f"{section}_case_id_invalid")

    gate_conclusion = str(payload.get("gateConclusion") or "").strip().lower()
    if gate_conclusion not in CASE_FAIRNESS_GATE_COUNT_KEYS:
        raise ValueError(f"{section}_gate_conclusion_invalid")

    error_codes = payload.get("errorCodes")
    if not isinstance(error_codes, list):
        raise ValueError(f"{section}_error_codes_not_list")

    panel_disagreement = payload.get("panelDisagreement")
    if not isinstance(panel_disagreement, dict):
        raise ValueError(f"{section}_panel_disagreement_not_dict")
    _assert_required_keys(
        section=f"{section}_panel_disagreement",
        payload=panel_disagreement,
        keys=CASE_FAIRNESS_PANEL_DISAGREEMENT_KEYS,
    )
    if not isinstance(panel_disagreement.get("reasons"), list):
        raise ValueError(f"{section}_panel_disagreement_reasons_not_list")
    if not isinstance(panel_disagreement.get("voteBySide"), dict):
        raise ValueError(f"{section}_panel_disagreement_vote_by_side_not_dict")
    if not isinstance(panel_disagreement.get("runtimeProfiles"), dict):
        raise ValueError(f"{section}_panel_disagreement_runtime_profiles_not_dict")

    drift_summary = payload.get("driftSummary")
    if not isinstance(drift_summary, dict):
        raise ValueError(f"{section}_drift_summary_not_dict")
    _assert_required_keys(
        section=f"{section}_drift_summary",
        payload=drift_summary,
        keys=CASE_FAIRNESS_DRIFT_SUMMARY_KEYS,
    )
    _assert_optional_dict(
        f"{section}_drift_summary_latest_run",
        drift_summary.get("latestRun"),
    )
    if not isinstance(drift_summary.get("thresholdBreaches"), list):
        raise ValueError(f"{section}_drift_summary_threshold_breaches_not_list")
    if not isinstance(drift_summary.get("driftBreaches"), list):
        raise ValueError(f"{section}_drift_summary_drift_breaches_not_list")

    shadow_summary = payload.get("shadowSummary")
    if not isinstance(shadow_summary, dict):
        raise ValueError(f"{section}_shadow_summary_not_dict")
    _assert_required_keys(
        section=f"{section}_shadow_summary",
        payload=shadow_summary,
        keys=CASE_FAIRNESS_SHADOW_SUMMARY_KEYS,
    )
    _assert_optional_dict(
        f"{section}_shadow_summary_latest_run",
        shadow_summary.get("latestRun"),
    )
    if not isinstance(shadow_summary.get("breaches"), list):
        raise ValueError(f"{section}_shadow_summary_breaches_not_list")

    challenge_link = payload.get("challengeLink")
    if not isinstance(challenge_link, dict):
        raise ValueError(f"{section}_challenge_link_not_dict")
    _assert_required_keys(
        section=f"{section}_challenge_link",
        payload=challenge_link,
        keys=CASE_FAIRNESS_CHALLENGE_LINK_KEYS,
    )
    _assert_optional_dict(
        f"{section}_challenge_link_latest",
        challenge_link.get("latest"),
    )


def validate_case_fairness_detail_contract(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("fairness_case_detail_payload_not_dict")
    _assert_required_keys(
        section="fairness_case_detail",
        payload=payload,
        keys=CASE_FAIRNESS_DETAIL_TOP_LEVEL_KEYS,
    )
    case_id = _non_negative_int(payload.get("caseId"), default=0)
    if case_id <= 0:
        raise ValueError("fairness_case_detail_case_id_invalid")
    item = payload.get("item")
    if not isinstance(item, dict):
        raise ValueError("fairness_case_detail_item_not_dict")
    _assert_item_contract(item, section="fairness_case_detail_item")
    if _non_negative_int(item.get("caseId"), default=0) != case_id:
        raise ValueError("fairness_case_detail_item_case_id_mismatch")


def validate_case_fairness_list_contract(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("fairness_case_list_payload_not_dict")
    _assert_required_keys(
        section="fairness_case_list",
        payload=payload,
        keys=CASE_FAIRNESS_LIST_TOP_LEVEL_KEYS,
    )
    count = _non_negative_int(payload.get("count"), default=0)
    returned = _non_negative_int(payload.get("returned"), default=0)
    if returned > count:
        raise ValueError("fairness_case_list_returned_exceeds_count")

    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("fairness_case_list_items_not_list")
    if len(items) != returned:
        raise ValueError("fairness_case_list_returned_mismatch")
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("fairness_case_list_item_not_dict")
        _assert_item_contract(item, section="fairness_case_list_item")

    aggregations = payload.get("aggregations")
    if not isinstance(aggregations, dict):
        raise ValueError("fairness_case_list_aggregations_not_dict")
    _assert_required_keys(
        section="fairness_case_list_aggregations",
        payload=aggregations,
        keys=CASE_FAIRNESS_AGGREGATIONS_KEYS,
    )
    total_matched = _non_negative_int(aggregations.get("totalMatched"), default=0)
    if total_matched != count:
        raise ValueError("fairness_case_list_total_matched_mismatch")

    gate_counts = aggregations.get("gateConclusionCounts")
    if not isinstance(gate_counts, dict):
        raise ValueError("fairness_case_list_gate_counts_not_dict")
    _assert_required_keys(
        section="fairness_case_list_gate_counts",
        payload=gate_counts,
        keys=CASE_FAIRNESS_GATE_COUNT_KEYS,
    )
    gate_sum = sum(_non_negative_int(gate_counts.get(key), default=0) for key in CASE_FAIRNESS_GATE_COUNT_KEYS)
    if gate_sum != total_matched:
        raise ValueError("fairness_case_list_gate_counts_sum_mismatch")

    winner_counts = aggregations.get("winnerCounts")
    if not isinstance(winner_counts, dict):
        raise ValueError("fairness_case_list_winner_counts_not_dict")
    _assert_required_keys(
        section="fairness_case_list_winner_counts",
        payload=winner_counts,
        keys=CASE_FAIRNESS_WINNER_COUNT_KEYS,
    )
    winner_sum = sum(
        _non_negative_int(winner_counts.get(key), default=0)
        for key in CASE_FAIRNESS_WINNER_COUNT_KEYS
    )
    if winner_sum != total_matched:
        raise ValueError("fairness_case_list_winner_counts_sum_mismatch")

    challenge_state_counts = aggregations.get("challengeStateCounts")
    if not isinstance(challenge_state_counts, dict):
        raise ValueError("fairness_case_list_challenge_state_counts_not_dict")
    if "none" not in challenge_state_counts:
        raise ValueError("fairness_case_list_challenge_state_counts_missing_none")
    challenge_state_sum = sum(
        _non_negative_int(value, default=0) for value in challenge_state_counts.values()
    )
    if challenge_state_sum != total_matched:
        raise ValueError("fairness_case_list_challenge_state_counts_sum_mismatch")

    policy_version_counts = aggregations.get("policyVersionCounts")
    if not isinstance(policy_version_counts, dict):
        raise ValueError("fairness_case_list_policy_version_counts_not_dict")
    if "unknown" not in policy_version_counts:
        raise ValueError("fairness_case_list_policy_version_counts_missing_unknown")
    policy_version_sum = sum(
        _non_negative_int(value, default=0) for value in policy_version_counts.values()
    )
    if policy_version_sum != total_matched:
        raise ValueError("fairness_case_list_policy_version_counts_sum_mismatch")

    filters = payload.get("filters")
    if not isinstance(filters, dict):
        raise ValueError("fairness_case_list_filters_not_dict")
    _assert_required_keys(
        section="fairness_case_list_filters",
        payload=filters,
        keys=CASE_FAIRNESS_FILTER_KEYS,
    )
    offset = _non_negative_int(filters.get("offset"), default=0)
    limit = _non_negative_int(filters.get("limit"), default=0)
    if limit <= 0:
        raise ValueError("fairness_case_list_limit_invalid")
    if offset < 0:
        raise ValueError("fairness_case_list_offset_invalid")
