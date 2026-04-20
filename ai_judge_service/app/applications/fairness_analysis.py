from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from app.domain.facts import FairnessBenchmarkRun, FairnessShadowRun


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_aware_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    token = str(value or "").strip()
    if not token:
        return None
    normalized = token.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_iso_datetime(value: Any) -> datetime | None:
    token = str(value or "").strip()
    if not token:
        return None
    normalized = token.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _optional_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _pick_threshold_value(payload: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key not in payload:
            continue
        parsed = _optional_float(payload.get(key))
        if parsed is not None:
            return parsed
    return None


def _suggest_max_threshold(
    values: list[float],
    *,
    margin_ratio: float = 0.1,
    floor: float = 0.0,
    cap: float | None = 1.0,
) -> float | None:
    if not values:
        return None
    baseline = max(values)
    suggested = max(float(floor), baseline * (1.0 + max(0.0, float(margin_ratio))))
    if cap is not None:
        suggested = min(float(cap), suggested)
    return round(suggested, 4)


def _suggest_sample_size_floor(values: list[int], *, floor: int = 100) -> int | None:
    normalized = [item for item in values if item > 0]
    if not normalized:
        return None
    normalized.sort()
    median = normalized[len(normalized) // 2]
    return max(int(floor), int(median))


def build_fairness_dashboard_case_trends(
    *,
    items: list[dict[str, Any]],
    window_days: int,
) -> list[dict[str, Any]]:
    window = max(1, min(int(window_days), 30))
    now = datetime.now(timezone.utc)
    date_keys = [
        (now - timedelta(days=offset)).date().isoformat()
        for offset in range(window - 1, -1, -1)
    ]
    counters: dict[str, dict[str, int]] = {
        key: {
            "totalCases": 0,
            "reviewRequiredCount": 0,
            "openReviewCount": 0,
            "benchmarkAttentionCount": 0,
        }
        for key in date_keys
    }
    for item in items:
        updated_at = _parse_iso_datetime(item.get("updatedAt"))
        if updated_at is None:
            continue
        date_key = updated_at.date().isoformat()
        row = counters.get(date_key)
        if row is None:
            continue
        row["totalCases"] += 1
        if bool(item.get("reviewRequired")):
            row["reviewRequiredCount"] += 1
        challenge_link = item.get("challengeLink") if isinstance(item.get("challengeLink"), dict) else {}
        if bool(challenge_link.get("hasOpenReview")):
            row["openReviewCount"] += 1
        if str(item.get("gateConclusion") or "").strip().lower() == "benchmark_attention_required":
            row["benchmarkAttentionCount"] += 1

    return [
        {
            "date": date_key,
            **counters[date_key],
        }
        for date_key in date_keys
    ]


def build_fairness_dashboard_run_trends(
    *,
    benchmark_runs: list[FairnessBenchmarkRun],
    shadow_runs: list[FairnessShadowRun],
    window_days: int,
) -> dict[str, Any]:
    window = max(1, min(int(window_days), 30))
    now = datetime.now(timezone.utc)
    window_from = now - timedelta(days=window)

    benchmark_items: list[dict[str, Any]] = []
    for row in benchmark_runs:
        reported_at = _normalize_aware_datetime(row.reported_at)
        if reported_at is None or reported_at < window_from:
            continue
        summary = row.summary if isinstance(row.summary, dict) else {}
        drift = summary.get("drift") if isinstance(summary.get("drift"), dict) else {}
        benchmark_items.append(
            {
                "runId": row.run_id,
                "policyVersion": row.policy_version,
                "environmentMode": row.environment_mode,
                "status": row.status,
                "thresholdDecision": row.threshold_decision,
                "reportedAt": reported_at.isoformat(),
                "hasThresholdBreach": bool(summary.get("hasThresholdBreach")),
                "hasDriftBreach": bool(drift.get("hasDriftBreach")),
                "thresholdBreaches": [
                    str(item).strip()
                    for item in (summary.get("thresholdBreaches") or [])
                    if str(item).strip()
                ],
                "driftBreaches": [
                    str(item).strip()
                    for item in (drift.get("driftBreaches") or [])
                    if str(item).strip()
                ],
            }
        )

    shadow_items: list[dict[str, Any]] = []
    for row in shadow_runs:
        reported_at = _normalize_aware_datetime(row.reported_at)
        if reported_at is None or reported_at < window_from:
            continue
        summary = row.summary if isinstance(row.summary, dict) else {}
        shadow_items.append(
            {
                "runId": row.run_id,
                "policyVersion": row.policy_version,
                "benchmarkRunId": row.benchmark_run_id,
                "environmentMode": row.environment_mode,
                "status": row.status,
                "thresholdDecision": row.threshold_decision,
                "reportedAt": reported_at.isoformat(),
                "hasShadowBreach": (
                    bool(summary.get("hasBreach")) or row.threshold_decision != "accepted"
                ),
                "breaches": [
                    str(item).strip()
                    for item in (summary.get("breaches") or [])
                    if str(item).strip()
                ],
            }
        )

    benchmark_items.sort(key=lambda item: str(item.get("reportedAt") or ""), reverse=True)
    shadow_items.sort(key=lambda item: str(item.get("reportedAt") or ""), reverse=True)
    return {
        "benchmarkRuns": benchmark_items[:50],
        "shadowRuns": shadow_items[:50],
    }


def build_fairness_dashboard_top_risk_cases(
    *,
    items: list[dict[str, Any]],
    top_limit: int,
) -> list[dict[str, Any]]:
    limit = max(1, min(int(top_limit), 50))

    risk_rows: list[dict[str, Any]] = []
    for item in items:
        risk_score = 0
        risk_tags: list[str] = []
        gate_conclusion = str(item.get("gateConclusion") or "").strip().lower()
        if gate_conclusion == "benchmark_attention_required":
            risk_score += 20
            risk_tags.append("benchmark_attention")
        if bool(item.get("reviewRequired")):
            risk_score += 30
            risk_tags.append("review_required")
        panel = item.get("panelDisagreement") if isinstance(item.get("panelDisagreement"), dict) else {}
        if bool(panel.get("high")):
            risk_score += 20
            risk_tags.append("panel_high_disagreement")
        drift = item.get("driftSummary") if isinstance(item.get("driftSummary"), dict) else {}
        if bool(drift.get("hasThresholdBreach")):
            risk_score += 25
            risk_tags.append("benchmark_threshold_breach")
        if bool(drift.get("hasDriftBreach")):
            risk_score += 15
            risk_tags.append("benchmark_drift_breach")
        shadow = item.get("shadowSummary") if isinstance(item.get("shadowSummary"), dict) else {}
        if bool(shadow.get("hasShadowBreach")):
            risk_score += 20
            risk_tags.append("shadow_breach")
        challenge_link = item.get("challengeLink") if isinstance(item.get("challengeLink"), dict) else {}
        if bool(challenge_link.get("hasOpenReview")):
            risk_score += 10
            risk_tags.append("open_review")
        latest_challenge = (
            challenge_link.get("latest")
            if isinstance(challenge_link.get("latest"), dict)
            else {}
        )
        challenge_state = str(latest_challenge.get("state") or "").strip()
        if challenge_state:
            risk_score += 5
            risk_tags.append("challenge_active")

        risk_rows.append(
            {
                "caseId": int(item.get("caseId") or 0),
                "dispatchType": item.get("dispatchType"),
                "updatedAt": item.get("updatedAt"),
                "winner": item.get("winner"),
                "gateConclusion": item.get("gateConclusion"),
                "reviewRequired": bool(item.get("reviewRequired")),
                "riskScore": risk_score,
                "riskTags": risk_tags,
                "panelDisagreementRatio": _safe_float(panel.get("ratio"), default=0.0),
                "hasOpenReview": bool(challenge_link.get("hasOpenReview")),
                "policyVersion": (
                    str((drift.get("policyVersion") or "").strip())
                    or str((shadow.get("policyVersion") or "").strip())
                    or None
                ),
            }
        )

    risk_rows.sort(
        key=lambda row: (
            int(row.get("riskScore") or 0),
            str(row.get("updatedAt") or ""),
            int(row.get("caseId") or 0),
        ),
        reverse=True,
    )
    return risk_rows[:limit]


def build_fairness_calibration_threshold_suggestions(
    *,
    benchmark_runs: list[FairnessBenchmarkRun],
    shadow_runs: list[FairnessShadowRun],
) -> dict[str, Any]:
    benchmark_draw_rates = [
        item
        for item in (_optional_float(row.draw_rate) for row in benchmark_runs)
        if item is not None
    ]
    benchmark_side_bias = [
        item
        for item in (_optional_float(row.side_bias_delta) for row in benchmark_runs)
        if item is not None
    ]
    benchmark_appeal_overturn = [
        item
        for item in (_optional_float(row.appeal_overturn_rate) for row in benchmark_runs)
        if item is not None
    ]
    benchmark_sample_sizes = [
        item
        for item in (_optional_int(row.sample_size) for row in benchmark_runs)
        if item is not None and item > 0
    ]

    benchmark_draw_rate_thresholds = [
        item
        for item in (
            _pick_threshold_value(row.thresholds, "drawRateMax", "draw_rate_max")
            if isinstance(row.thresholds, dict)
            else None
            for row in benchmark_runs
        )
        if item is not None
    ]
    benchmark_side_bias_thresholds = [
        item
        for item in (
            _pick_threshold_value(
                row.thresholds,
                "sideBiasDeltaMax",
                "side_bias_delta_max",
            )
            if isinstance(row.thresholds, dict)
            else None
            for row in benchmark_runs
        )
        if item is not None
    ]
    benchmark_appeal_thresholds = [
        item
        for item in (
            _pick_threshold_value(
                row.thresholds,
                "appealOverturnRateMax",
                "appeal_overturn_rate_max",
            )
            if isinstance(row.thresholds, dict)
            else None
            for row in benchmark_runs
        )
        if item is not None
    ]

    shadow_winner_flip_rates = [
        item
        for item in (_optional_float(row.winner_flip_rate) for row in shadow_runs)
        if item is not None
    ]
    shadow_score_shift = [
        item
        for item in (_optional_float(row.score_shift_delta) for row in shadow_runs)
        if item is not None
    ]
    shadow_review_delta = [
        item
        for item in (_optional_float(row.review_required_delta) for row in shadow_runs)
        if item is not None
    ]
    shadow_sample_sizes = [
        item
        for item in (_optional_int(row.sample_size) for row in shadow_runs)
        if item is not None and item > 0
    ]
    shadow_winner_flip_thresholds = [
        item
        for item in (
            _pick_threshold_value(
                row.thresholds,
                "winnerFlipRateMax",
                "winner_flip_rate_max",
            )
            if isinstance(row.thresholds, dict)
            else None
            for row in shadow_runs
        )
        if item is not None
    ]
    shadow_score_shift_thresholds = [
        item
        for item in (
            _pick_threshold_value(
                row.thresholds,
                "scoreShiftDeltaMax",
                "score_shift_delta_max",
            )
            if isinstance(row.thresholds, dict)
            else None
            for row in shadow_runs
        )
        if item is not None
    ]
    shadow_review_delta_thresholds = [
        item
        for item in (
            _pick_threshold_value(
                row.thresholds,
                "reviewRequiredDeltaMax",
                "review_required_delta_max",
            )
            if isinstance(row.thresholds, dict)
            else None
            for row in shadow_runs
        )
        if item is not None
    ]

    return {
        "method": "local_observed_max_with_margin",
        "benchmark": {
            "drawRateMaxSuggested": _suggest_max_threshold(benchmark_draw_rates),
            "sideBiasDeltaMaxSuggested": _suggest_max_threshold(benchmark_side_bias),
            "appealOverturnRateMaxSuggested": _suggest_max_threshold(
                benchmark_appeal_overturn
            ),
            "sampleSizeMinSuggested": _suggest_sample_size_floor(benchmark_sample_sizes),
            "currentThresholdsObserved": {
                "drawRateMax": (
                    round(max(benchmark_draw_rate_thresholds), 4)
                    if benchmark_draw_rate_thresholds
                    else None
                ),
                "sideBiasDeltaMax": (
                    round(max(benchmark_side_bias_thresholds), 4)
                    if benchmark_side_bias_thresholds
                    else None
                ),
                "appealOverturnRateMax": (
                    round(max(benchmark_appeal_thresholds), 4)
                    if benchmark_appeal_thresholds
                    else None
                ),
            },
        },
        "shadow": {
            "winnerFlipRateMaxSuggested": _suggest_max_threshold(shadow_winner_flip_rates),
            "scoreShiftDeltaMaxSuggested": _suggest_max_threshold(shadow_score_shift),
            "reviewRequiredDeltaMaxSuggested": _suggest_max_threshold(shadow_review_delta),
            "sampleSizeMinSuggested": _suggest_sample_size_floor(shadow_sample_sizes),
            "currentThresholdsObserved": {
                "winnerFlipRateMax": (
                    round(max(shadow_winner_flip_thresholds), 4)
                    if shadow_winner_flip_thresholds
                    else None
                ),
                "scoreShiftDeltaMax": (
                    round(max(shadow_score_shift_thresholds), 4)
                    if shadow_score_shift_thresholds
                    else None
                ),
                "reviewRequiredDeltaMax": (
                    round(max(shadow_review_delta_thresholds), 4)
                    if shadow_review_delta_thresholds
                    else None
                ),
            },
        },
    }


def build_fairness_calibration_drift_summary(
    *,
    latest_benchmark_run: FairnessBenchmarkRun | None,
    latest_shadow_run: FairnessShadowRun | None,
) -> dict[str, Any]:
    benchmark_summary = (
        latest_benchmark_run.summary
        if latest_benchmark_run is not None and isinstance(latest_benchmark_run.summary, dict)
        else {}
    )
    drift_payload = (
        benchmark_summary.get("drift")
        if isinstance(benchmark_summary.get("drift"), dict)
        else {}
    )
    benchmark_threshold_breaches = drift_payload.get("thresholdBreaches")
    if not isinstance(benchmark_threshold_breaches, list):
        benchmark_threshold_breaches = []
    benchmark_drift_breaches = drift_payload.get("driftBreaches")
    if not isinstance(benchmark_drift_breaches, list):
        benchmark_drift_breaches = []

    shadow_summary = (
        latest_shadow_run.summary
        if latest_shadow_run is not None and isinstance(latest_shadow_run.summary, dict)
        else {}
    )
    shadow_breaches = shadow_summary.get("breaches")
    if not isinstance(shadow_breaches, list):
        shadow_breaches = []

    return {
        "benchmark": {
            "latestRunId": latest_benchmark_run.run_id if latest_benchmark_run is not None else None,
            "baselineRunId": str(drift_payload.get("baselineRunId") or "").strip() or None,
            "thresholdBreaches": [
                str(item).strip()
                for item in benchmark_threshold_breaches
                if str(item).strip()
            ],
            "driftBreaches": [
                str(item).strip() for item in benchmark_drift_breaches if str(item).strip()
            ],
            "hasThresholdBreach": bool(drift_payload.get("hasThresholdBreach")),
            "hasDriftBreach": bool(drift_payload.get("hasDriftBreach")),
            "drawRateDelta": _optional_float(drift_payload.get("drawRateDelta")),
            "sideBiasDeltaDelta": _optional_float(drift_payload.get("sideBiasDeltaDelta")),
            "appealOverturnRateDelta": _optional_float(
                drift_payload.get("appealOverturnRateDelta")
            ),
        },
        "shadow": {
            "latestRunId": latest_shadow_run.run_id if latest_shadow_run is not None else None,
            "benchmarkRunId": (
                latest_shadow_run.benchmark_run_id if latest_shadow_run is not None else None
            ),
            "breaches": [str(item).strip() for item in shadow_breaches if str(item).strip()],
            "hasBreach": bool(shadow_summary.get("hasBreach")),
        },
    }


def build_fairness_calibration_risk_items(
    *,
    benchmark_runs: list[FairnessBenchmarkRun],
    shadow_runs: list[FairnessShadowRun],
    top_risk_cases: list[dict[str, Any]],
    risk_limit: int,
) -> list[dict[str, Any]]:
    risk_items: list[dict[str, Any]] = []

    for row in benchmark_runs:
        summary = row.summary if isinstance(row.summary, dict) else {}
        drift = summary.get("drift") if isinstance(summary.get("drift"), dict) else {}
        threshold_breaches = drift.get("thresholdBreaches")
        if not isinstance(threshold_breaches, list):
            threshold_breaches = []
        drift_breaches = drift.get("driftBreaches")
        if not isinstance(drift_breaches, list):
            drift_breaches = []

        if row.threshold_decision == "violated" or row.status == "threshold_violation":
            risk_items.append(
                {
                    "riskType": "benchmark_threshold_violation",
                    "severity": "high",
                    "source": "fairness_benchmark_run",
                    "runId": row.run_id,
                    "policyVersion": row.policy_version,
                    "message": (
                        "benchmark threshold violated"
                        if not threshold_breaches
                        else f"benchmark threshold violated: {','.join(str(item) for item in threshold_breaches)}"
                    ),
                    "reportedAt": row.reported_at.isoformat(),
                }
            )
        if bool(drift.get("hasDriftBreach")):
            risk_items.append(
                {
                    "riskType": "benchmark_drift_breach",
                    "severity": "medium",
                    "source": "fairness_benchmark_run",
                    "runId": row.run_id,
                    "policyVersion": row.policy_version,
                    "message": (
                        "benchmark drift breached"
                        if not drift_breaches
                        else f"benchmark drift breached: {','.join(str(item) for item in drift_breaches)}"
                    ),
                    "reportedAt": row.reported_at.isoformat(),
                }
            )

    for row in shadow_runs:
        summary = row.summary if isinstance(row.summary, dict) else {}
        breaches = summary.get("breaches")
        if not isinstance(breaches, list):
            breaches = []
        has_breach = bool(summary.get("hasBreach")) or row.threshold_decision == "violated"
        if not has_breach and row.status != "threshold_violation":
            continue
        risk_items.append(
            {
                "riskType": "shadow_threshold_violation",
                "severity": "high",
                "source": "fairness_shadow_run",
                "runId": row.run_id,
                "policyVersion": row.policy_version,
                "benchmarkRunId": row.benchmark_run_id,
                "message": (
                    "shadow threshold violated"
                    if not breaches
                    else f"shadow threshold violated: {','.join(str(item) for item in breaches)}"
                ),
                "reportedAt": row.reported_at.isoformat(),
            }
        )

    for item in top_risk_cases:
        if not isinstance(item, dict):
            continue
        try:
            risk_score = int(item.get("riskScore") or 0)
        except (TypeError, ValueError):
            risk_score = 0
        if risk_score < 40:
            continue
        severity = "high" if risk_score >= 70 else "medium"
        risk_items.append(
            {
                "riskType": "case_risk_rank",
                "severity": severity,
                "source": "fairness_case_dashboard",
                "caseId": int(item.get("caseId") or 0),
                "policyVersion": str(item.get("policyVersion") or "").strip() or None,
                "message": (
                    f"case risk score={risk_score}, tags="
                    f"{','.join(str(tag) for tag in (item.get('riskTags') or []))}"
                ),
                "updatedAt": str(item.get("updatedAt") or "").strip() or None,
            }
        )

    severity_rank = {"high": 3, "medium": 2, "low": 1}
    risk_items.sort(
        key=lambda row: (
            severity_rank.get(str(row.get("severity") or "").strip().lower(), 0),
            str(row.get("reportedAt") or row.get("updatedAt") or ""),
            str(row.get("runId") or row.get("caseId") or ""),
        ),
        reverse=True,
    )
    return risk_items[: max(1, min(int(risk_limit), 200))]
