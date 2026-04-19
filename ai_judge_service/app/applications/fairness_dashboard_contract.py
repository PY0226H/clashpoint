from __future__ import annotations

from typing import Any

FAIRNESS_DASHBOARD_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "generatedAt",
    "overview",
    "gateDistribution",
    "trends",
    "topRiskCases",
    "filters",
)

FAIRNESS_DASHBOARD_OVERVIEW_KEYS: tuple[str, ...] = (
    "totalMatched",
    "scannedCases",
    "scanTruncated",
    "reviewRequiredCount",
    "openReviewCount",
    "panelHighDisagreementCount",
    "driftBreachCount",
    "thresholdBreachCount",
    "shadowBreachCount",
)

FAIRNESS_DASHBOARD_GATE_DISTRIBUTION_KEYS: tuple[str, ...] = (
    "auto_passed",
    "review_required",
    "benchmark_attention_required",
    "unknown",
)

FAIRNESS_DASHBOARD_TRENDS_KEYS: tuple[str, ...] = (
    "windowDays",
    "caseDaily",
    "benchmarkRuns",
    "shadowRuns",
)

FAIRNESS_DASHBOARD_CASE_DAILY_KEYS: tuple[str, ...] = (
    "date",
    "totalCases",
    "reviewRequiredCount",
    "openReviewCount",
    "benchmarkAttentionCount",
)

FAIRNESS_DASHBOARD_TOP_RISK_ITEM_KEYS: tuple[str, ...] = (
    "caseId",
    "dispatchType",
    "updatedAt",
    "winner",
    "gateConclusion",
    "reviewRequired",
    "riskScore",
    "riskTags",
    "panelDisagreementRatio",
    "hasOpenReview",
    "policyVersion",
)

FAIRNESS_DASHBOARD_FILTER_KEYS: tuple[str, ...] = (
    "status",
    "dispatchType",
    "winner",
    "policyVersion",
    "challengeState",
    "windowDays",
    "topLimit",
    "caseScanLimit",
)


def _required_keys_missing(payload: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    return [key for key in keys if key not in payload]


def _non_negative_int(value: Any, *, default: int = 0) -> int:
    try:
        if isinstance(value, bool):
            return default
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, parsed)


def _assert_required_keys(
    *,
    section: str,
    payload: dict[str, Any],
    keys: tuple[str, ...],
) -> None:
    missing = _required_keys_missing(payload, keys)
    if missing:
        raise ValueError(f"{section}_missing_keys:{','.join(sorted(missing))}")


def validate_fairness_dashboard_contract(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("fairness_dashboard_payload_not_dict")
    _assert_required_keys(
        section="fairness_dashboard",
        payload=payload,
        keys=FAIRNESS_DASHBOARD_TOP_LEVEL_KEYS,
    )

    overview = payload.get("overview")
    if not isinstance(overview, dict):
        raise ValueError("fairness_dashboard_overview_not_dict")
    _assert_required_keys(
        section="fairness_dashboard_overview",
        payload=overview,
        keys=FAIRNESS_DASHBOARD_OVERVIEW_KEYS,
    )

    total_matched = _non_negative_int(overview.get("totalMatched"), default=0)
    scanned_cases = _non_negative_int(overview.get("scannedCases"), default=0)
    if scanned_cases > total_matched:
        raise ValueError("fairness_dashboard_overview_scanned_exceeds_total")
    expected_scan_truncated = scanned_cases < total_matched
    if bool(overview.get("scanTruncated")) != expected_scan_truncated:
        raise ValueError("fairness_dashboard_overview_scan_truncated_mismatch")
    for key in (
        "reviewRequiredCount",
        "openReviewCount",
        "panelHighDisagreementCount",
        "driftBreachCount",
        "thresholdBreachCount",
        "shadowBreachCount",
    ):
        value = _non_negative_int(overview.get(key), default=0)
        if value > scanned_cases:
            raise ValueError(f"fairness_dashboard_overview_{key}_exceeds_scanned")

    gate_distribution = payload.get("gateDistribution")
    if not isinstance(gate_distribution, dict):
        raise ValueError("fairness_dashboard_gate_distribution_not_dict")
    _assert_required_keys(
        section="fairness_dashboard_gate_distribution",
        payload=gate_distribution,
        keys=FAIRNESS_DASHBOARD_GATE_DISTRIBUTION_KEYS,
    )
    gate_sum = sum(
        _non_negative_int(gate_distribution.get(key), default=0)
        for key in FAIRNESS_DASHBOARD_GATE_DISTRIBUTION_KEYS
    )
    if gate_sum != scanned_cases:
        raise ValueError("fairness_dashboard_gate_distribution_sum_mismatch")

    trends = payload.get("trends")
    if not isinstance(trends, dict):
        raise ValueError("fairness_dashboard_trends_not_dict")
    _assert_required_keys(
        section="fairness_dashboard_trends",
        payload=trends,
        keys=FAIRNESS_DASHBOARD_TRENDS_KEYS,
    )
    trends_window_days = _non_negative_int(trends.get("windowDays"), default=0)
    if trends_window_days <= 0:
        raise ValueError("fairness_dashboard_trends_window_days_invalid")

    case_daily = trends.get("caseDaily")
    if not isinstance(case_daily, list):
        raise ValueError("fairness_dashboard_case_daily_not_list")
    for row in case_daily:
        if not isinstance(row, dict):
            raise ValueError("fairness_dashboard_case_daily_item_not_dict")
        _assert_required_keys(
            section="fairness_dashboard_case_daily_item",
            payload=row,
            keys=FAIRNESS_DASHBOARD_CASE_DAILY_KEYS,
        )
        total_cases = _non_negative_int(row.get("totalCases"), default=0)
        review_required = _non_negative_int(row.get("reviewRequiredCount"), default=0)
        open_review = _non_negative_int(row.get("openReviewCount"), default=0)
        benchmark_attention = _non_negative_int(row.get("benchmarkAttentionCount"), default=0)
        if review_required > total_cases:
            raise ValueError("fairness_dashboard_case_daily_review_required_exceeds_total")
        if open_review > total_cases:
            raise ValueError("fairness_dashboard_case_daily_open_review_exceeds_total")
        if benchmark_attention > total_cases:
            raise ValueError("fairness_dashboard_case_daily_benchmark_attention_exceeds_total")

    benchmark_runs = trends.get("benchmarkRuns")
    if not isinstance(benchmark_runs, list):
        raise ValueError("fairness_dashboard_benchmark_runs_not_list")
    shadow_runs = trends.get("shadowRuns")
    if not isinstance(shadow_runs, list):
        raise ValueError("fairness_dashboard_shadow_runs_not_list")

    top_risk_cases = payload.get("topRiskCases")
    if not isinstance(top_risk_cases, list):
        raise ValueError("fairness_dashboard_top_risk_cases_not_list")
    for row in top_risk_cases:
        if not isinstance(row, dict):
            raise ValueError("fairness_dashboard_top_risk_item_not_dict")
        _assert_required_keys(
            section="fairness_dashboard_top_risk_item",
            payload=row,
            keys=FAIRNESS_DASHBOARD_TOP_RISK_ITEM_KEYS,
        )
        if _non_negative_int(row.get("riskScore"), default=0) < 0:
            raise ValueError("fairness_dashboard_top_risk_score_invalid")
        if not isinstance(row.get("riskTags"), list):
            raise ValueError("fairness_dashboard_top_risk_tags_not_list")

    filters = payload.get("filters")
    if not isinstance(filters, dict):
        raise ValueError("fairness_dashboard_filters_not_dict")
    _assert_required_keys(
        section="fairness_dashboard_filters",
        payload=filters,
        keys=FAIRNESS_DASHBOARD_FILTER_KEYS,
    )
    filters_window_days = _non_negative_int(filters.get("windowDays"), default=0)
    if filters_window_days <= 0:
        raise ValueError("fairness_dashboard_filters_window_days_invalid")
    if filters_window_days != trends_window_days:
        raise ValueError("fairness_dashboard_window_days_mismatch")
    top_limit = _non_negative_int(filters.get("topLimit"), default=0)
    if top_limit <= 0:
        raise ValueError("fairness_dashboard_filters_top_limit_invalid")
    if len(top_risk_cases) > top_limit:
        raise ValueError("fairness_dashboard_top_risk_exceeds_top_limit")
