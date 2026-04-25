from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Awaitable, Callable


class FairnessRouteError(Exception):
    def __init__(self, *, status_code: int, detail: Any):
        super().__init__(str(detail))
        self.status_code = int(status_code)
        self.detail = detail


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_case_fairness_gate_conclusion(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    return normalized or None


def normalize_case_fairness_challenge_state(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    return normalized


def normalize_case_fairness_sort_by(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "updated_at"
    return normalized


def normalize_case_fairness_sort_order(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "desc"
    return normalized


def build_case_fairness_sort_key(
    *,
    item: dict[str, Any],
    sort_by: str,
) -> tuple[Any, ...]:
    if sort_by == "panel_disagreement_ratio":
        panel = (
            item.get("panelDisagreement")
            if isinstance(item.get("panelDisagreement"), dict)
            else {}
        )
        return (
            _safe_float(panel.get("ratio"), default=0.0),
            int(item.get("caseId") or 0),
        )
    if sort_by == "gate_conclusion":
        return (
            str(item.get("gateConclusion") or "").strip().lower(),
            int(item.get("caseId") or 0),
        )
    if sort_by == "case_id":
        return (int(item.get("caseId") or 0),)
    return (
        str(item.get("updatedAt") or "").strip(),
        int(item.get("caseId") or 0),
    )


def build_case_fairness_aggregations(
    items: list[dict[str, Any]],
    *,
    case_fairness_gate_conclusions: set[str] | frozenset[str],
) -> dict[str, Any]:
    gate_counts: dict[str, int] = {
        key: 0 for key in sorted(case_fairness_gate_conclusions)
    }
    gate_counts["unknown"] = 0
    winner_counts: dict[str, int] = {
        "pro": 0,
        "con": 0,
        "draw": 0,
        "unknown": 0,
    }
    challenge_state_counts: dict[str, int] = {"none": 0}
    policy_version_counts: dict[str, int] = {"unknown": 0}

    open_review_count = 0
    review_required_count = 0
    drift_breach_count = 0
    threshold_breach_count = 0
    shadow_breach_count = 0
    panel_high_disagreement_count = 0
    with_challenge_count = 0

    for item in items:
        gate = str(item.get("gateConclusion") or "").strip().lower()
        if gate in gate_counts:
            gate_counts[gate] += 1
        else:
            gate_counts["unknown"] += 1

        winner = str(item.get("winner") or "").strip().lower()
        if winner in winner_counts:
            winner_counts[winner] += 1
        else:
            winner_counts["unknown"] += 1

        if bool(item.get("reviewRequired")):
            review_required_count += 1

        panel = (
            item.get("panelDisagreement")
            if isinstance(item.get("panelDisagreement"), dict)
            else {}
        )
        if bool(panel.get("high")):
            panel_high_disagreement_count += 1

        drift = item.get("driftSummary") if isinstance(item.get("driftSummary"), dict) else {}
        if bool(drift.get("hasDriftBreach")):
            drift_breach_count += 1
        if bool(drift.get("hasThresholdBreach")):
            threshold_breach_count += 1
        policy_version = str(drift.get("policyVersion") or "").strip()
        if policy_version:
            policy_version_counts[policy_version] = (
                policy_version_counts.get(policy_version, 0) + 1
            )
        else:
            policy_version_counts["unknown"] += 1

        shadow = item.get("shadowSummary") if isinstance(item.get("shadowSummary"), dict) else {}
        if bool(shadow.get("hasShadowBreach")):
            shadow_breach_count += 1

        challenge_link = (
            item.get("challengeLink") if isinstance(item.get("challengeLink"), dict) else {}
        )
        if bool(challenge_link.get("hasOpenReview")):
            open_review_count += 1
        latest_challenge = (
            challenge_link.get("latest")
            if isinstance(challenge_link.get("latest"), dict)
            else None
        )
        state = (
            str(latest_challenge.get("state") or "").strip()
            if isinstance(latest_challenge, dict)
            else ""
        )
        if state:
            challenge_state_counts[state] = challenge_state_counts.get(state, 0) + 1
            with_challenge_count += 1
        else:
            challenge_state_counts["none"] = challenge_state_counts.get("none", 0) + 1

    return {
        "totalMatched": len(items),
        "reviewRequiredCount": review_required_count,
        "openReviewCount": open_review_count,
        "driftBreachCount": drift_breach_count,
        "thresholdBreachCount": threshold_breach_count,
        "shadowBreachCount": shadow_breach_count,
        "panelHighDisagreementCount": panel_high_disagreement_count,
        "withChallengeCount": with_challenge_count,
        "gateConclusionCounts": gate_counts,
        "winnerCounts": winner_counts,
        "challengeStateCounts": dict(
            sorted(challenge_state_counts.items(), key=lambda kv: kv[0])
        ),
        "policyVersionCounts": dict(
            sorted(policy_version_counts.items(), key=lambda kv: kv[0])
        ),
    }


def _extract_latest_challenge_snapshot(
    workflow_events: list[Any],
    *,
    trust_challenge_event_type: str,
) -> dict[str, Any] | None:
    for event in reversed(workflow_events):
        if (
            str(getattr(event, "event_type", "") or "").strip()
            != trust_challenge_event_type
        ):
            continue
        payload = event.payload if isinstance(getattr(event, "payload", None), dict) else {}
        state = str(
            payload.get("state")
            or payload.get("challengeState")
            or payload.get("currentState")
            or ""
        ).strip()
        if not state:
            continue
        return {
            "state": state,
            "reasonCode": (
                str(payload.get("reasonCode") or payload.get("challengeReasonCode") or "").strip()
                or None
            ),
            "reason": (
                str(payload.get("reason") or payload.get("challengeReason") or "").strip() or None
            ),
            "requestedBy": (
                str(payload.get("requestedBy") or payload.get("challengeRequestedBy") or "").strip()
                or None
            ),
            "decidedBy": (
                str(payload.get("decidedBy") or payload.get("challengeDecisionBy") or "").strip()
                or None
            ),
            "dispatchType": str(payload.get("dispatchType") or "").strip() or None,
            "at": (
                getattr(event, "created_at", None).isoformat()
                if isinstance(getattr(event, "created_at", None), datetime)
                else None
            ),
        }
    return None


def build_case_fairness_item(
    *,
    case_id: int,
    dispatch_type: str,
    trace_id: str,
    workflow_job: Any | None,
    workflow_events: list[Any],
    report_payload: dict[str, Any],
    latest_run: Any | None,
    latest_shadow_run: Any | None,
    normalize_fairness_gate_decision: Callable[..., str],
    serialize_fairness_benchmark_run: Callable[[Any], dict[str, Any]],
    serialize_fairness_shadow_run: Callable[[Any], dict[str, Any]],
    trust_challenge_event_type: str,
) -> dict[str, Any]:
    fairness_summary = (
        report_payload.get("fairnessSummary")
        if isinstance(report_payload.get("fairnessSummary"), dict)
        else {}
    )
    judge_trace = (
        report_payload.get("judgeTrace")
        if isinstance(report_payload.get("judgeTrace"), dict)
        else {}
    )
    panel_runtime_profiles = (
        judge_trace.get("panelRuntimeProfiles")
        if isinstance(judge_trace.get("panelRuntimeProfiles"), dict)
        else {}
    )
    verdict_ledger = (
        report_payload.get("verdictLedger")
        if isinstance(report_payload.get("verdictLedger"), dict)
        else {}
    )
    arbitration = (
        verdict_ledger.get("arbitration")
        if isinstance(verdict_ledger.get("arbitration"), dict)
        else {}
    )
    winner = str(report_payload.get("winner") or "").strip().lower() or None
    review_required = bool(report_payload.get("reviewRequired"))
    error_codes = [
        str(item).strip()
        for item in (report_payload.get("errorCodes") or [])
        if str(item).strip()
    ]
    panel_high_disagreement = bool(fairness_summary.get("panelHighDisagreement"))
    challenge_snapshot = _extract_latest_challenge_snapshot(
        workflow_events,
        trust_challenge_event_type=trust_challenge_event_type,
    )
    policy_version = (
        str((judge_trace.get("policyRegistry") or {}).get("version") or "").strip()
        if isinstance(judge_trace.get("policyRegistry"), dict)
        else ""
    ) or None
    run_summary = (
        dict(getattr(latest_run, "summary"))
        if latest_run is not None and isinstance(getattr(latest_run, "summary", None), dict)
        else {}
    )
    drift_payload = run_summary.get("drift") if isinstance(run_summary.get("drift"), dict) else {}
    threshold_breaches = run_summary.get("thresholdBreaches")
    if not isinstance(threshold_breaches, list):
        threshold_breaches = []
    drift_breaches = drift_payload.get("driftBreaches")
    if not isinstance(drift_breaches, list):
        drift_breaches = []
    shadow_summary = (
        dict(getattr(latest_shadow_run, "summary"))
        if latest_shadow_run is not None
        and isinstance(getattr(latest_shadow_run, "summary", None), dict)
        else {}
    )
    shadow_breaches = shadow_summary.get("breaches")
    if not isinstance(shadow_breaches, list):
        shadow_breaches = []
    has_shadow_breach = bool(
        shadow_summary.get("hasBreach")
        if isinstance(shadow_summary, dict)
        else False
    )
    if (
        latest_shadow_run is not None
        and str(getattr(latest_shadow_run, "threshold_decision", "") or "").strip().lower()
        != "accepted"
    ):
        has_shadow_breach = True
    gate_conclusion = normalize_fairness_gate_decision(
        arbitration.get("gateDecision") or fairness_summary.get("gateDecision"),
        review_required=review_required,
    )
    if not gate_conclusion:
        gate_conclusion = "blocked_to_draw" if review_required else "pass_through"

    return {
        "caseId": case_id,
        "dispatchType": dispatch_type,
        "traceId": trace_id or None,
        "workflowStatus": getattr(workflow_job, "status", None) if workflow_job is not None else None,
        "updatedAt": (
            getattr(workflow_job, "updated_at", None).isoformat()
            if workflow_job is not None
            and isinstance(getattr(workflow_job, "updated_at", None), datetime)
            else None
        ),
        "winner": winner,
        "reviewRequired": review_required,
        "gateConclusion": gate_conclusion,
        "errorCodes": error_codes,
        "panelDisagreement": {
            "high": panel_high_disagreement,
            "ratio": _safe_float(fairness_summary.get("panelDisagreementRatio"), default=0.0),
            "ratioMax": _safe_float(fairness_summary.get("panelDisagreementRatioMax"), default=0.0),
            "reasons": [
                str(item).strip()
                for item in (fairness_summary.get("panelDisagreementReasons") or [])
                if str(item).strip()
            ],
            "majorityWinner": (
                str(fairness_summary.get("panelMajorityWinner") or "").strip().lower() or None
            ),
            "voteBySide": (
                fairness_summary.get("panelVoteBySide")
                if isinstance(fairness_summary.get("panelVoteBySide"), dict)
                else {}
            ),
            "runtimeProfiles": panel_runtime_profiles,
        },
        "driftSummary": {
            "policyVersion": policy_version,
            "latestRun": (
                serialize_fairness_benchmark_run(latest_run) if latest_run is not None else None
            ),
            "thresholdBreaches": [
                str(item).strip() for item in threshold_breaches if str(item).strip()
            ],
            "driftBreaches": [str(item).strip() for item in drift_breaches if str(item).strip()],
            "hasThresholdBreach": bool(run_summary.get("hasThresholdBreach")),
            "hasDriftBreach": bool(drift_payload.get("hasDriftBreach")),
        },
        "shadowSummary": {
            "policyVersion": policy_version,
            "latestRun": (
                serialize_fairness_shadow_run(latest_shadow_run)
                if latest_shadow_run is not None
                else None
            ),
            "benchmarkRunId": (
                str(getattr(latest_shadow_run, "benchmark_run_id", "") or "").strip() or None
                if latest_shadow_run is not None
                else None
            ),
            "breaches": [str(item).strip() for item in shadow_breaches if str(item).strip()],
            "hasShadowBreach": has_shadow_breach,
        },
        "challengeLink": {
            "latest": challenge_snapshot,
            "hasOpenReview": (
                workflow_job is not None
                and str(getattr(workflow_job, "status", "") or "").strip()
                in {"review_required", "draw_pending_vote"}
            ),
        },
    }


def build_fairness_calibration_on_env_input_template() -> dict[str, Any]:
    return {
        "envMarker": {
            "REAL_CALIBRATION_ENV_READY": "true",
            "CALIBRATION_ENV_MODE": "real",
        },
        "fairnessBenchmarkTrackRequiredKeys": [
            "CALIBRATION_STATUS",
            "WINDOW_FROM",
            "WINDOW_TO",
            "SAMPLE_SIZE",
            "DRAW_RATE",
            "SIDE_BIAS_DELTA",
            "APPEAL_OVERTURN_RATE",
        ],
        "shadowRunPayloadRequiredKeys": [
            "run_id",
            "policy_version",
            "benchmark_run_id",
            "environment_mode",
            "status",
            "threshold_decision",
            "metrics.sample_size",
            "metrics.winner_flip_rate",
            "metrics.score_shift_delta",
            "metrics.review_required_delta",
        ],
        "recommendedCommands": [
            "bash scripts/harness/ai_judge_p5_real_calibration_on_env.sh",
            "bash scripts/harness/ai_judge_fairness_benchmark_freeze.sh",
            "bash scripts/harness/ai_judge_runtime_ops_pack.sh",
            "bash scripts/harness/ai_judge_real_env_window_closure.sh",
        ],
        "notes": [
            (
                "local calibration pack is for threshold suggestions and risk scanning "
                "only; it does not represent real-env pass."
            ),
            (
                "when entering the real-env window, provide real markers and full "
                "five-track calibration evidence."
            ),
        ],
    }


def build_fairness_policy_calibration_recommended_actions(
    *,
    release_gate: dict[str, Any],
    policy_version: str | None,
    risk_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    seen_action_ids: set[str] = set()

    gate_code = str(release_gate.get("code") or "").strip()
    gate_passed = bool(release_gate.get("passed"))
    benchmark_gate_passed = bool(release_gate.get("benchmarkGatePassed"))
    shadow_gate_applied = bool(release_gate.get("shadowGateApplied"))
    shadow_gate_passed = release_gate.get("shadowGatePassed")
    high_risk_count = sum(
        1
        for item in risk_items
        if isinstance(item, dict)
        and str(item.get("severity") or "").strip().lower() == "high"
    )

    def _append_action(
        *,
        action_id: str,
        priority: str,
        reason_code: str,
        description: str,
        blocking: bool,
    ) -> None:
        normalized_action_id = str(action_id or "").strip()
        if not normalized_action_id or normalized_action_id in seen_action_ids:
            return
        seen_action_ids.add(normalized_action_id)
        actions.append(
            {
                "actionId": normalized_action_id,
                "priority": str(priority or "").strip().lower() or "medium",
                "reasonCode": str(reason_code or "").strip() or None,
                "description": str(description or "").strip(),
                "blocking": bool(blocking),
                "advisoryOnly": True,
                "policyVersion": policy_version,
            }
        )

    if not policy_version:
        _append_action(
            action_id="select_policy_version_context",
            priority="high",
            reason_code="no_policy_version_context",
            description=(
                "provide policy_version in query or upload benchmark/shadow runs "
                "before using calibration advisor."
            ),
            blocking=True,
        )
        return actions

    if gate_code == "registry_fairness_gate_no_benchmark":
        _append_action(
            action_id="run_benchmark_first",
            priority="high",
            reason_code=gate_code,
            description=(
                "no benchmark evidence found for this policy version; run a benchmark "
                "window before publish/activate."
            ),
            blocking=True,
        )
    elif gate_code in {
        "registry_fairness_gate_threshold_not_accepted",
        "registry_fairness_gate_remediation_required",
        "registry_fairness_gate_status_not_ready",
    }:
        _append_action(
            action_id="rerun_benchmark_with_remediation",
            priority="high",
            reason_code=gate_code,
            description=(
                "latest benchmark does not meet release gate; patch policy/prompts/tools "
                "and rerun benchmark."
            ),
            blocking=True,
        )

    if benchmark_gate_passed and not shadow_gate_applied:
        _append_action(
            action_id="run_shadow_evaluation",
            priority="high",
            reason_code="shadow_required_after_benchmark_pass",
            description=(
                "benchmark passed and shadow evidence is missing; run shadow evaluation "
                "to check winner-flip and score-shift risks."
            ),
            blocking=True,
        )

    if shadow_gate_applied and shadow_gate_passed is False:
        _append_action(
            action_id="prepare_candidate_policy_patch",
            priority="high",
            reason_code=gate_code or "shadow_gate_blocked",
            description=(
                "shadow gate is blocked; prepare candidate policy patch and rerun "
                "shadow with the same benchmark baseline."
            ),
            blocking=True,
        )
        _append_action(
            action_id="manual_review_before_activation",
            priority="high",
            reason_code="activation_requires_manual_review",
            description=(
                "activation should stay blocked until shadow breaches are resolved "
                "or a governance override is explicitly approved."
            ),
            blocking=True,
        )

    if gate_passed:
        _append_action(
            action_id="publish_candidate_policy",
            priority="medium",
            reason_code="registry_fairness_gate_passed",
            description=(
                "fairness gate is currently passing; candidate policy can be published "
                "through registry governance flow."
            ),
            blocking=False,
        )
        _append_action(
            action_id="activate_candidate_policy",
            priority="low",
            reason_code="registry_fairness_gate_passed",
            description=(
                "after publish and governance review, policy activation can proceed "
                "without fairness override."
            ),
            blocking=False,
        )

    if high_risk_count > 0 and not gate_passed:
        _append_action(
            action_id="triage_high_risk_cases",
            priority="medium",
            reason_code="high_risk_cases_present",
            description=(
                f"{high_risk_count} high-severity risk items detected; review top cases "
                "for targeted remediation before next calibration run."
            ),
            blocking=False,
        )

    if not actions:
        _append_action(
            action_id="monitor_next_calibration_window",
            priority="low",
            reason_code=gate_code or "gate_status_unknown",
            description=(
                "no immediate blocking suggestion detected; continue monitoring fairness "
                "runs and keep calibration evidence fresh."
            ),
            blocking=False,
        )
    return actions


def normalize_fairness_environment_mode(
    value: str | None,
    *,
    strict: bool = False,
) -> str | None:
    token = str(value or "").strip().lower()
    if not token:
        return None if strict else "blocked"
    if token in {"real", "local_reference", "blocked"}:
        return token
    return None if strict else "blocked"


def normalize_fairness_status(
    value: str | None,
    *,
    strict: bool = False,
) -> str | None:
    token = str(value or "").strip().lower()
    if not token:
        return None if strict else "pending_data"
    if token in {
        "pass",
        "local_reference_frozen",
        "pending_real_samples",
        "pending_data",
        "threshold_violation",
        "env_blocked",
        "evidence_missing",
    }:
        return token
    return None if strict else "pending_data"


def normalize_fairness_threshold_decision(value: str | None) -> str:
    token = str(value or "").strip().lower()
    if token in {"accepted", "violated", "pending"}:
        return token
    return "pending"


def metric_delta(current: float | None, baseline: float | None) -> float | None:
    if current is None or baseline is None:
        return None
    return round(current - baseline, 8)


async def build_fairness_benchmark_upsert_payload(
    *,
    raw_payload: dict[str, Any],
    extract_optional_int: Callable[[dict[str, Any], str], int | None]
    | Callable[[dict[str, Any], str, str], int | None],
    extract_optional_float: Callable[[dict[str, Any], str], float | None]
    | Callable[[dict[str, Any], str, str], float | None],
    extract_optional_str: Callable[[dict[str, Any], str], str | None]
    | Callable[[dict[str, Any], str, str], str | None],
    extract_optional_bool: Callable[[dict[str, Any], str], bool | None]
    | Callable[[dict[str, Any], str, str], bool | None],
    extract_optional_datetime: Callable[[dict[str, Any], str], datetime | None]
    | Callable[[dict[str, Any], str, str], datetime | None],
    list_fairness_benchmark_runs: Callable[..., Awaitable[list[Any]]],
    upsert_fairness_benchmark_run: Callable[..., Awaitable[Any]],
    upsert_audit_alert: Callable[..., Any],
    sync_audit_alert_to_facts: Callable[..., Awaitable[Any]],
    serialize_alert_item: Callable[[Any], dict[str, Any]],
    serialize_fairness_benchmark_run: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    run_id = extract_optional_str(raw_payload, "run_id", "runId")
    if run_id is None:
        raise FairnessRouteError(status_code=422, detail="invalid_fairness_run_id")
    policy_version = (
        extract_optional_str(raw_payload, "policy_version", "policyVersion")
        or "fairness-benchmark-v1"
    )
    environment_mode = normalize_fairness_environment_mode(
        extract_optional_str(raw_payload, "environment_mode", "environmentMode"),
        strict=False,
    )
    assert environment_mode is not None
    status = normalize_fairness_status(
        extract_optional_str(raw_payload, "status"),
        strict=False,
    )
    assert status is not None
    threshold_decision = normalize_fairness_threshold_decision(
        extract_optional_str(raw_payload, "threshold_decision", "thresholdDecision")
    )

    thresholds_payload = (
        raw_payload.get("thresholds")
        if isinstance(raw_payload.get("thresholds"), dict)
        else {}
    )
    metrics_payload = (
        raw_payload.get("metrics")
        if isinstance(raw_payload.get("metrics"), dict)
        else {}
    )
    summary_payload = (
        raw_payload.get("summary")
        if isinstance(raw_payload.get("summary"), dict)
        else {}
    )
    note = (
        extract_optional_str(raw_payload, "note")
        or extract_optional_str(summary_payload, "note")
        or ""
    )

    sample_size = extract_optional_int(raw_payload, "sample_size", "sampleSize")
    if sample_size is None:
        sample_size = extract_optional_int(metrics_payload, "sample_size", "sampleSize")
    draw_rate = extract_optional_float(raw_payload, "draw_rate", "drawRate")
    if draw_rate is None:
        draw_rate = extract_optional_float(metrics_payload, "draw_rate", "drawRate")
    side_bias_delta = extract_optional_float(
        raw_payload,
        "side_bias_delta",
        "sideBiasDelta",
    )
    if side_bias_delta is None:
        side_bias_delta = extract_optional_float(
            metrics_payload,
            "side_bias_delta",
            "sideBiasDelta",
        )
    appeal_overturn_rate = extract_optional_float(
        raw_payload,
        "appeal_overturn_rate",
        "appealOverturnRate",
    )
    if appeal_overturn_rate is None:
        appeal_overturn_rate = extract_optional_float(
            metrics_payload,
            "appeal_overturn_rate",
            "appealOverturnRate",
        )

    draw_rate_max = extract_optional_float(raw_payload, "draw_rate_max", "drawRateMax")
    if draw_rate_max is None:
        draw_rate_max = extract_optional_float(
            thresholds_payload,
            "draw_rate_max",
            "drawRateMax",
        )
    side_bias_delta_max = extract_optional_float(
        raw_payload,
        "side_bias_delta_max",
        "sideBiasDeltaMax",
    )
    if side_bias_delta_max is None:
        side_bias_delta_max = extract_optional_float(
            thresholds_payload,
            "side_bias_delta_max",
            "sideBiasDeltaMax",
        )
    appeal_overturn_rate_max = extract_optional_float(
        raw_payload,
        "appeal_overturn_rate_max",
        "appealOverturnRateMax",
    )
    if appeal_overturn_rate_max is None:
        appeal_overturn_rate_max = extract_optional_float(
            thresholds_payload,
            "appeal_overturn_rate_max",
            "appealOverturnRateMax",
        )

    draw_rate_drift_max = extract_optional_float(
        raw_payload,
        "draw_rate_drift_max",
        "drawRateDriftMax",
    )
    if draw_rate_drift_max is None:
        draw_rate_drift_max = extract_optional_float(
            thresholds_payload,
            "draw_rate_drift_max",
            "drawRateDriftMax",
        )
    side_bias_delta_drift_max = extract_optional_float(
        raw_payload,
        "side_bias_delta_drift_max",
        "sideBiasDeltaDriftMax",
    )
    if side_bias_delta_drift_max is None:
        side_bias_delta_drift_max = extract_optional_float(
            thresholds_payload,
            "side_bias_delta_drift_max",
            "sideBiasDeltaDriftMax",
        )
    appeal_overturn_rate_drift_max = extract_optional_float(
        raw_payload,
        "appeal_overturn_rate_drift_max",
        "appealOverturnRateDriftMax",
    )
    if appeal_overturn_rate_drift_max is None:
        appeal_overturn_rate_drift_max = extract_optional_float(
            thresholds_payload,
            "appeal_overturn_rate_drift_max",
            "appealOverturnRateDriftMax",
        )

    runs = await list_fairness_benchmark_runs(
        policy_version=policy_version,
        limit=200,
    )
    baseline_run = next(
        (
            row
            for row in runs
            if row.run_id != run_id
            and row.threshold_decision == "accepted"
            and row.status in {"pass", "local_reference_frozen"}
        ),
        None,
    )
    baseline_draw_rate = baseline_run.draw_rate if baseline_run is not None else None
    baseline_side_bias_delta = baseline_run.side_bias_delta if baseline_run is not None else None
    baseline_appeal_overturn_rate = (
        baseline_run.appeal_overturn_rate if baseline_run is not None else None
    )

    draw_rate_delta = metric_delta(draw_rate, baseline_draw_rate)
    side_bias_delta_delta = metric_delta(side_bias_delta, baseline_side_bias_delta)
    appeal_overturn_rate_delta = metric_delta(
        appeal_overturn_rate,
        baseline_appeal_overturn_rate,
    )
    draw_rate_delta_abs = abs(draw_rate_delta) if draw_rate_delta is not None else None
    side_bias_delta_delta_abs = (
        abs(side_bias_delta_delta) if side_bias_delta_delta is not None else None
    )
    appeal_overturn_rate_delta_abs = (
        abs(appeal_overturn_rate_delta)
        if appeal_overturn_rate_delta is not None
        else None
    )

    threshold_breaches: list[str] = []
    if draw_rate_max is not None and draw_rate is not None and draw_rate > draw_rate_max:
        threshold_breaches.append("draw_rate")
    if (
        side_bias_delta_max is not None
        and side_bias_delta is not None
        and side_bias_delta > side_bias_delta_max
    ):
        threshold_breaches.append("side_bias_delta")
    if (
        appeal_overturn_rate_max is not None
        and appeal_overturn_rate is not None
        and appeal_overturn_rate > appeal_overturn_rate_max
    ):
        threshold_breaches.append("appeal_overturn_rate")

    drift_breaches: list[str] = []
    if (
        draw_rate_drift_max is not None
        and draw_rate_delta_abs is not None
        and draw_rate_delta_abs > draw_rate_drift_max
    ):
        drift_breaches.append("draw_rate")
    if (
        side_bias_delta_drift_max is not None
        and side_bias_delta_delta_abs is not None
        and side_bias_delta_delta_abs > side_bias_delta_drift_max
    ):
        drift_breaches.append("side_bias_delta")
    if (
        appeal_overturn_rate_drift_max is not None
        and appeal_overturn_rate_delta_abs is not None
        and appeal_overturn_rate_delta_abs > appeal_overturn_rate_drift_max
    ):
        drift_breaches.append("appeal_overturn_rate")

    has_threshold_breach = bool(threshold_breaches) or status == "threshold_violation"
    has_drift_breach = bool(drift_breaches)
    needs_remediation = bool(
        extract_optional_bool(raw_payload, "needs_remediation", "needsRemediation")
    ) or has_threshold_breach or has_drift_breach or threshold_decision == "violated"
    needs_real_env_reconfirm_override = extract_optional_bool(
        raw_payload,
        "needs_real_env_reconfirm",
        "needsRealEnvReconfirm",
    )
    needs_real_env_reconfirm = (
        bool(needs_real_env_reconfirm_override)
        if needs_real_env_reconfirm_override is not None
        else environment_mode != "real"
    )
    reported_at = extract_optional_datetime(raw_payload, "reported_at", "reportedAt")
    source = extract_optional_str(raw_payload, "source") or "manual"
    reported_by = extract_optional_str(raw_payload, "reported_by", "reportedBy") or "system"

    normalized_thresholds = dict(thresholds_payload)
    normalized_thresholds["drawRateMax"] = draw_rate_max
    normalized_thresholds["sideBiasDeltaMax"] = side_bias_delta_max
    normalized_thresholds["appealOverturnRateMax"] = appeal_overturn_rate_max
    normalized_thresholds["drawRateDriftMax"] = draw_rate_drift_max
    normalized_thresholds["sideBiasDeltaDriftMax"] = side_bias_delta_drift_max
    normalized_thresholds["appealOverturnRateDriftMax"] = appeal_overturn_rate_drift_max
    normalized_thresholds = {
        key: value for key, value in normalized_thresholds.items() if value is not None
    }

    normalized_metrics = dict(metrics_payload)
    normalized_metrics["sampleSize"] = sample_size
    normalized_metrics["drawRate"] = draw_rate
    normalized_metrics["sideBiasDelta"] = side_bias_delta
    normalized_metrics["appealOverturnRate"] = appeal_overturn_rate
    normalized_metrics["drawRateDelta"] = draw_rate_delta
    normalized_metrics["sideBiasDeltaDelta"] = side_bias_delta_delta
    normalized_metrics["appealOverturnRateDelta"] = appeal_overturn_rate_delta
    normalized_metrics = {
        key: value for key, value in normalized_metrics.items() if value is not None
    }

    drift_summary = {
        "baselineRunId": baseline_run.run_id if baseline_run is not None else None,
        "baselineReportedAt": (
            baseline_run.reported_at.isoformat() if baseline_run is not None else None
        ),
        "drawRateDelta": draw_rate_delta,
        "sideBiasDeltaDelta": side_bias_delta_delta,
        "appealOverturnRateDelta": appeal_overturn_rate_delta,
        "thresholdBreaches": threshold_breaches,
        "driftBreaches": drift_breaches,
        "hasThresholdBreach": has_threshold_breach,
        "hasDriftBreach": has_drift_breach,
    }
    normalized_summary = dict(summary_payload)
    if note:
        normalized_summary["note"] = note
    normalized_summary["drift"] = drift_summary

    row = await upsert_fairness_benchmark_run(
        run_id=run_id,
        policy_version=policy_version,
        environment_mode=environment_mode,
        status=status,
        threshold_decision=threshold_decision,
        needs_real_env_reconfirm=needs_real_env_reconfirm,
        needs_remediation=needs_remediation,
        sample_size=sample_size,
        draw_rate=draw_rate,
        side_bias_delta=side_bias_delta,
        appeal_overturn_rate=appeal_overturn_rate,
        thresholds=normalized_thresholds,
        metrics=normalized_metrics,
        summary=normalized_summary,
        source=source,
        reported_by=reported_by,
        reported_at=reported_at,
    )

    alert_item: dict[str, Any] | None = None
    if has_threshold_breach or has_drift_breach:
        alert_type = (
            "fairness_benchmark_threshold_violation"
            if has_threshold_breach
            else "fairness_benchmark_drift_violation"
        )
        severity = "critical" if has_threshold_breach else "warning"
        breached_items = threshold_breaches if has_threshold_breach else drift_breaches
        message = (
            f"fairness benchmark run breached: run_id={run_id}; "
            f"breaches={','.join(breached_items)}"
        )
        alert = upsert_audit_alert(
            job_id=0,
            scope_id=1,
            trace_id=f"fairness-benchmark:{run_id}",
            alert_type=alert_type,
            severity=severity,
            title="AI Judge Fairness Benchmark Drift",
            message=message,
            details={
                "runId": run_id,
                "policyVersion": policy_version,
                "environmentMode": environment_mode,
                "status": status,
                "thresholdDecision": threshold_decision,
                "metrics": normalized_metrics,
                "thresholds": normalized_thresholds,
                "drift": drift_summary,
            },
        )
        await sync_audit_alert_to_facts(alert=alert)
        alert_item = serialize_alert_item(alert)

    return {
        "ok": True,
        "item": serialize_fairness_benchmark_run(row),
        "drift": drift_summary,
        "alert": alert_item,
    }


async def build_fairness_benchmark_list_payload(
    *,
    policy_version: str | None,
    environment_mode: str | None,
    status: str | None,
    limit: int,
    list_fairness_benchmark_runs: Callable[..., Awaitable[list[Any]]],
    serialize_fairness_benchmark_run: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    normalized_policy_version = (
        str(policy_version or "").strip() if policy_version is not None else None
    )
    if normalized_policy_version == "":
        normalized_policy_version = None
    normalized_environment_mode = normalize_fairness_environment_mode(
        environment_mode,
        strict=True,
    )
    if environment_mode is not None and normalized_environment_mode is None:
        raise FairnessRouteError(status_code=422, detail="invalid_environment_mode")
    normalized_status = normalize_fairness_status(status, strict=True)
    if status is not None and normalized_status is None:
        raise FairnessRouteError(status_code=422, detail="invalid_fairness_status")

    rows = await list_fairness_benchmark_runs(
        policy_version=normalized_policy_version,
        environment_mode=normalized_environment_mode,
        status=normalized_status,
        limit=limit,
    )
    return {
        "count": len(rows),
        "items": [serialize_fairness_benchmark_run(row) for row in rows],
        "filters": {
            "policyVersion": normalized_policy_version,
            "environmentMode": normalized_environment_mode,
            "status": normalized_status,
            "limit": limit,
        },
    }


async def build_fairness_shadow_upsert_payload(
    *,
    raw_payload: dict[str, Any],
    extract_optional_int: Callable[[dict[str, Any], str], int | None]
    | Callable[[dict[str, Any], str, str], int | None],
    extract_optional_float: Callable[[dict[str, Any], str], float | None]
    | Callable[[dict[str, Any], str, str], float | None],
    extract_optional_str: Callable[[dict[str, Any], str], str | None]
    | Callable[[dict[str, Any], str, str], str | None],
    extract_optional_bool: Callable[[dict[str, Any], str], bool | None]
    | Callable[[dict[str, Any], str, str], bool | None],
    extract_optional_datetime: Callable[[dict[str, Any], str], datetime | None]
    | Callable[[dict[str, Any], str, str], datetime | None],
    list_fairness_benchmark_runs: Callable[..., Awaitable[list[Any]]],
    list_fairness_shadow_runs: Callable[..., Awaitable[list[Any]]],
    upsert_fairness_shadow_run: Callable[..., Awaitable[Any]],
    upsert_audit_alert: Callable[..., Any],
    sync_audit_alert_to_facts: Callable[..., Awaitable[Any]],
    serialize_alert_item: Callable[[Any], dict[str, Any]],
    serialize_fairness_shadow_run: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    run_id = extract_optional_str(raw_payload, "run_id", "runId")
    if run_id is None:
        raise FairnessRouteError(status_code=422, detail="invalid_fairness_shadow_run_id")
    policy_version = (
        extract_optional_str(raw_payload, "policy_version", "policyVersion")
        or "fairness-benchmark-v1"
    )
    benchmark_run_id = extract_optional_str(raw_payload, "benchmark_run_id", "benchmarkRunId")
    environment_mode = normalize_fairness_environment_mode(
        extract_optional_str(raw_payload, "environment_mode", "environmentMode"),
        strict=False,
    )
    assert environment_mode is not None
    status = normalize_fairness_status(
        extract_optional_str(raw_payload, "status"),
        strict=False,
    )
    assert status is not None
    threshold_decision = normalize_fairness_threshold_decision(
        extract_optional_str(raw_payload, "threshold_decision", "thresholdDecision")
    )
    thresholds_payload = (
        raw_payload.get("thresholds")
        if isinstance(raw_payload.get("thresholds"), dict)
        else {}
    )
    metrics_payload = (
        raw_payload.get("metrics")
        if isinstance(raw_payload.get("metrics"), dict)
        else {}
    )
    summary_payload = (
        raw_payload.get("summary")
        if isinstance(raw_payload.get("summary"), dict)
        else {}
    )
    note = (
        extract_optional_str(raw_payload, "note")
        or extract_optional_str(summary_payload, "note")
        or ""
    )
    sample_size = extract_optional_int(raw_payload, "sample_size", "sampleSize")
    if sample_size is None:
        sample_size = extract_optional_int(metrics_payload, "sample_size", "sampleSize")
    winner_flip_rate = extract_optional_float(
        raw_payload,
        "winner_flip_rate",
        "winnerFlipRate",
    )
    if winner_flip_rate is None:
        winner_flip_rate = extract_optional_float(
            metrics_payload,
            "winner_flip_rate",
            "winnerFlipRate",
        )
    score_shift_delta = extract_optional_float(
        raw_payload,
        "score_shift_delta",
        "scoreShiftDelta",
    )
    if score_shift_delta is None:
        score_shift_delta = extract_optional_float(
            metrics_payload,
            "score_shift_delta",
            "scoreShiftDelta",
        )
    review_required_delta = extract_optional_float(
        raw_payload,
        "review_required_delta",
        "reviewRequiredDelta",
    )
    if review_required_delta is None:
        review_required_delta = extract_optional_float(
            metrics_payload,
            "review_required_delta",
            "reviewRequiredDelta",
        )

    winner_flip_rate_max = extract_optional_float(
        raw_payload,
        "winner_flip_rate_max",
        "winnerFlipRateMax",
    )
    if winner_flip_rate_max is None:
        winner_flip_rate_max = extract_optional_float(
            thresholds_payload,
            "winner_flip_rate_max",
            "winnerFlipRateMax",
        )
    score_shift_delta_max = extract_optional_float(
        raw_payload,
        "score_shift_delta_max",
        "scoreShiftDeltaMax",
    )
    if score_shift_delta_max is None:
        score_shift_delta_max = extract_optional_float(
            thresholds_payload,
            "score_shift_delta_max",
            "scoreShiftDeltaMax",
        )
    review_required_delta_max = extract_optional_float(
        raw_payload,
        "review_required_delta_max",
        "reviewRequiredDeltaMax",
    )
    if review_required_delta_max is None:
        review_required_delta_max = extract_optional_float(
            thresholds_payload,
            "review_required_delta_max",
            "reviewRequiredDeltaMax",
        )

    if benchmark_run_id is None:
        benchmark_runs = await list_fairness_benchmark_runs(
            policy_version=policy_version,
            limit=1,
        )
        benchmark_run_id = benchmark_runs[0].run_id if benchmark_runs else None

    breaches: list[str] = []
    if (
        winner_flip_rate_max is not None
        and winner_flip_rate is not None
        and winner_flip_rate > winner_flip_rate_max
    ):
        breaches.append("winner_flip_rate")
    if (
        score_shift_delta_max is not None
        and score_shift_delta is not None
        and score_shift_delta > score_shift_delta_max
    ):
        breaches.append("score_shift_delta")
    if (
        review_required_delta_max is not None
        and review_required_delta is not None
        and review_required_delta > review_required_delta_max
    ):
        breaches.append("review_required_delta")

    has_breach = bool(breaches)
    needs_remediation = bool(
        extract_optional_bool(raw_payload, "needs_remediation", "needsRemediation")
    ) or has_breach or threshold_decision == "violated"
    needs_real_env_reconfirm_override = extract_optional_bool(
        raw_payload,
        "needs_real_env_reconfirm",
        "needsRealEnvReconfirm",
    )
    needs_real_env_reconfirm = (
        bool(needs_real_env_reconfirm_override)
        if needs_real_env_reconfirm_override is not None
        else environment_mode != "real"
    )
    reported_at = extract_optional_datetime(raw_payload, "reported_at", "reportedAt")
    source = extract_optional_str(raw_payload, "source") or "manual"
    reported_by = extract_optional_str(raw_payload, "reported_by", "reportedBy") or "system"

    normalized_thresholds = dict(thresholds_payload)
    normalized_thresholds["winnerFlipRateMax"] = winner_flip_rate_max
    normalized_thresholds["scoreShiftDeltaMax"] = score_shift_delta_max
    normalized_thresholds["reviewRequiredDeltaMax"] = review_required_delta_max
    normalized_thresholds = {
        key: value for key, value in normalized_thresholds.items() if value is not None
    }

    normalized_metrics = dict(metrics_payload)
    normalized_metrics["sampleSize"] = sample_size
    normalized_metrics["winnerFlipRate"] = winner_flip_rate
    normalized_metrics["scoreShiftDelta"] = score_shift_delta
    normalized_metrics["reviewRequiredDelta"] = review_required_delta
    normalized_metrics = {
        key: value for key, value in normalized_metrics.items() if value is not None
    }

    normalized_summary = dict(summary_payload)
    if note:
        normalized_summary["note"] = note
    normalized_summary["hasBreach"] = has_breach
    normalized_summary["breaches"] = breaches
    normalized_summary["benchmarkRunId"] = benchmark_run_id

    row = await upsert_fairness_shadow_run(
        run_id=run_id,
        policy_version=policy_version,
        benchmark_run_id=benchmark_run_id,
        environment_mode=environment_mode,
        status=status,
        threshold_decision=threshold_decision,
        needs_real_env_reconfirm=needs_real_env_reconfirm,
        needs_remediation=needs_remediation,
        sample_size=sample_size,
        winner_flip_rate=winner_flip_rate,
        score_shift_delta=score_shift_delta,
        review_required_delta=review_required_delta,
        thresholds=normalized_thresholds,
        metrics=normalized_metrics,
        summary=normalized_summary,
        source=source,
        reported_by=reported_by,
        reported_at=reported_at,
    )

    alert_item: dict[str, Any] | None = None
    if has_breach:
        alert = upsert_audit_alert(
            job_id=0,
            scope_id=1,
            trace_id=f"fairness-shadow:{run_id}",
            alert_type="fairness_shadow_threshold_violation",
            severity="warning",
            title="AI Judge Fairness Shadow Drift",
            message=(
                f"fairness shadow run breached: run_id={run_id}; "
                f"breaches={','.join(breaches)}"
            ),
            details={
                "runId": run_id,
                "policyVersion": policy_version,
                "benchmarkRunId": benchmark_run_id,
                "environmentMode": environment_mode,
                "status": status,
                "thresholdDecision": threshold_decision,
                "metrics": normalized_metrics,
                "thresholds": normalized_thresholds,
                "breaches": breaches,
            },
        )
        await sync_audit_alert_to_facts(alert=alert)
        alert_item = serialize_alert_item(alert)

    return {
        "ok": True,
        "item": serialize_fairness_shadow_run(row),
        "breaches": breaches,
        "alert": alert_item,
    }


async def build_fairness_shadow_list_payload(
    *,
    policy_version: str | None,
    benchmark_run_id: str | None,
    environment_mode: str | None,
    status: str | None,
    limit: int,
    list_fairness_shadow_runs: Callable[..., Awaitable[list[Any]]],
    serialize_fairness_shadow_run: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    normalized_policy_version = (
        str(policy_version or "").strip() if policy_version is not None else None
    )
    if normalized_policy_version == "":
        normalized_policy_version = None
    normalized_benchmark_run_id = (
        str(benchmark_run_id or "").strip() if benchmark_run_id is not None else None
    )
    if normalized_benchmark_run_id == "":
        normalized_benchmark_run_id = None
    normalized_environment_mode = normalize_fairness_environment_mode(
        environment_mode,
        strict=True,
    )
    if environment_mode is not None and normalized_environment_mode is None:
        raise FairnessRouteError(status_code=422, detail="invalid_environment_mode")
    normalized_status = normalize_fairness_status(status, strict=True)
    if status is not None and normalized_status is None:
        raise FairnessRouteError(status_code=422, detail="invalid_fairness_status")

    rows = await list_fairness_shadow_runs(
        policy_version=normalized_policy_version,
        benchmark_run_id=normalized_benchmark_run_id,
        environment_mode=normalized_environment_mode,
        status=normalized_status,
        limit=limit,
    )
    return {
        "count": len(rows),
        "items": [serialize_fairness_shadow_run(row) for row in rows],
        "filters": {
            "policyVersion": normalized_policy_version,
            "benchmarkRunId": normalized_benchmark_run_id,
            "environmentMode": normalized_environment_mode,
            "status": normalized_status,
            "limit": limit,
        },
    }


async def build_fairness_case_detail_payload(
    *,
    case_id: int,
    dispatch_type: str,
    resolve_report_context_for_case: Callable[..., Awaitable[dict[str, Any]]],
    workflow_get_job: Callable[..., Awaitable[Any]],
    workflow_list_events: Callable[..., Awaitable[list[Any]]],
    list_fairness_benchmark_runs: Callable[..., Awaitable[list[Any]]],
    list_fairness_shadow_runs: Callable[..., Awaitable[list[Any]]],
    build_case_fairness_item: Callable[..., dict[str, Any]],
    validate_case_fairness_detail_contract: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    context = await resolve_report_context_for_case(
        case_id=case_id,
        dispatch_type=dispatch_type,
        not_found_detail="fairness_case_not_found",
        missing_report_detail="fairness_report_payload_missing",
    )
    workflow_job = await workflow_get_job(job_id=case_id)
    workflow_events = (
        await workflow_list_events(job_id=case_id)
        if workflow_job is not None
        else []
    )
    report_payload = (
        context["reportPayload"] if isinstance(context["reportPayload"], dict) else {}
    )
    judge_trace = (
        report_payload.get("judgeTrace")
        if isinstance(report_payload.get("judgeTrace"), dict)
        else {}
    )
    policy_version = (
        str((judge_trace.get("policyRegistry") or {}).get("version") or "").strip()
        if isinstance(judge_trace.get("policyRegistry"), dict)
        else ""
    )
    latest_run = None
    if policy_version:
        runs = await list_fairness_benchmark_runs(
            policy_version=policy_version,
            limit=1,
        )
        latest_run = runs[0] if runs else None
    latest_shadow_run = None
    if policy_version:
        shadow_runs = await list_fairness_shadow_runs(
            policy_version=policy_version,
            limit=1,
        )
        latest_shadow_run = shadow_runs[0] if shadow_runs else None

    item = build_case_fairness_item(
        case_id=case_id,
        dispatch_type=context["dispatchType"],
        trace_id=str(context["traceId"] or ""),
        workflow_job=workflow_job,
        workflow_events=workflow_events,
        report_payload=report_payload,
        latest_run=latest_run,
        latest_shadow_run=latest_shadow_run,
    )
    payload = {
        "caseId": case_id,
        "dispatchType": context["dispatchType"],
        "item": item,
    }
    try:
        validate_case_fairness_detail_contract(payload)
    except ValueError as err:
        raise FairnessRouteError(
            status_code=500,
            detail={
                "code": "fairness_case_detail_contract_violation",
                "message": str(err),
            },
        ) from err
    return payload


async def build_fairness_case_list_payload(
    *,
    status: str | None,
    dispatch_type: str | None,
    winner: str | None,
    policy_version: str | None,
    has_drift_breach: bool | None,
    has_threshold_breach: bool | None,
    has_shadow_breach: bool | None,
    has_open_review: bool | None,
    gate_conclusion: str | None,
    challenge_state: str | None,
    sort_by: str,
    sort_order: str,
    review_required: bool | None,
    panel_high_disagreement: bool | None,
    offset: int,
    limit: int,
    normalize_workflow_status: Callable[[str | None], str | None],
    workflow_statuses: set[str],
    normalize_case_fairness_sort_by: Callable[[str | None], str],
    case_fairness_sort_fields: set[str],
    normalize_case_fairness_sort_order: Callable[[str | None], str],
    normalize_case_fairness_gate_conclusion: Callable[[str | None], str | None],
    case_fairness_gate_conclusions: set[str],
    normalize_case_fairness_challenge_state: Callable[[str | None], str | None],
    case_fairness_challenge_states: set[str],
    workflow_list_jobs: Callable[..., Awaitable[list[Any]]],
    get_trace: Callable[[int], Any],
    workflow_list_events: Callable[..., Awaitable[list[Any]]],
    list_fairness_benchmark_runs: Callable[..., Awaitable[list[Any]]],
    list_fairness_shadow_runs: Callable[..., Awaitable[list[Any]]],
    build_case_fairness_item: Callable[..., dict[str, Any]],
    build_case_fairness_sort_key: Callable[..., tuple[Any, ...]],
    build_case_fairness_aggregations: Callable[[list[dict[str, Any]]], dict[str, Any]],
    validate_case_fairness_list_contract: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    normalized_status = normalize_workflow_status(status)
    if status is not None and normalized_status is None:
        raise FairnessRouteError(status_code=422, detail="invalid_workflow_status")
    if normalized_status is not None and normalized_status not in workflow_statuses:
        raise FairnessRouteError(status_code=422, detail="invalid_workflow_status")
    normalized_dispatch_type = str(dispatch_type or "").strip().lower() or None
    if normalized_dispatch_type not in {None, "phase", "final"}:
        raise FairnessRouteError(status_code=422, detail="invalid_dispatch_type")
    normalized_winner = str(winner or "").strip().lower() or None
    if normalized_winner not in {None, "pro", "con", "draw"}:
        raise FairnessRouteError(status_code=422, detail="invalid_winner")
    normalized_policy_version = (
        str(policy_version or "").strip() if policy_version is not None else None
    )
    if normalized_policy_version == "":
        normalized_policy_version = None
    normalized_sort_by = normalize_case_fairness_sort_by(sort_by)
    if normalized_sort_by not in case_fairness_sort_fields:
        raise FairnessRouteError(status_code=422, detail="invalid_sort_by")
    normalized_sort_order = normalize_case_fairness_sort_order(sort_order)
    if normalized_sort_order not in {"asc", "desc"}:
        raise FairnessRouteError(status_code=422, detail="invalid_sort_order")
    normalized_gate_conclusion = normalize_case_fairness_gate_conclusion(gate_conclusion)
    if (
        normalized_gate_conclusion is not None
        and normalized_gate_conclusion not in case_fairness_gate_conclusions
    ):
        raise FairnessRouteError(status_code=422, detail="invalid_gate_conclusion")
    normalized_challenge_state = normalize_case_fairness_challenge_state(challenge_state)
    if (
        normalized_challenge_state is not None
        and normalized_challenge_state not in case_fairness_challenge_states
    ):
        raise FairnessRouteError(status_code=422, detail="invalid_challenge_state")

    jobs = await workflow_list_jobs(
        status=normalized_status,
        dispatch_type=normalized_dispatch_type,
        limit=max(limit, limit + offset),
    )
    benchmark_cache: dict[str, Any | None] = {}
    shadow_cache: dict[str, Any | None] = {}
    items: list[dict[str, Any]] = []
    for job in jobs:
        trace = get_trace(job.job_id)
        report_summary = (
            trace.report_summary if trace and isinstance(trace.report_summary, dict) else {}
        )
        report_payload = (
            report_summary.get("payload")
            if isinstance(report_summary.get("payload"), dict)
            else {}
        )
        if not report_payload:
            continue
        workflow_events = await workflow_list_events(job_id=job.job_id)
        trace_id = (
            str(
                (trace.trace_id if trace is not None else "")
                or report_summary.get("traceId")
                or ""
            ).strip()
        )
        dispatch_type_token = (
            str(report_summary.get("dispatchType") or "").strip().lower()
            or job.dispatch_type
        )
        judge_trace = (
            report_payload.get("judgeTrace")
            if isinstance(report_payload.get("judgeTrace"), dict)
            else {}
        )
        policy_version = (
            str((judge_trace.get("policyRegistry") or {}).get("version") or "").strip()
            if isinstance(judge_trace.get("policyRegistry"), dict)
            else ""
        )
        latest_run = None
        if policy_version:
            if policy_version not in benchmark_cache:
                runs = await list_fairness_benchmark_runs(
                    policy_version=policy_version,
                    limit=1,
                )
                benchmark_cache[policy_version] = runs[0] if runs else None
            latest_run = benchmark_cache.get(policy_version)
        latest_shadow_run = None
        if policy_version:
            if policy_version not in shadow_cache:
                shadow_runs = await list_fairness_shadow_runs(
                    policy_version=policy_version,
                    limit=1,
                )
                shadow_cache[policy_version] = shadow_runs[0] if shadow_runs else None
            latest_shadow_run = shadow_cache.get(policy_version)
        item = build_case_fairness_item(
            case_id=job.job_id,
            dispatch_type=dispatch_type_token,
            trace_id=trace_id,
            workflow_job=job,
            workflow_events=workflow_events,
            report_payload=report_payload,
            latest_run=latest_run,
            latest_shadow_run=latest_shadow_run,
        )
        if normalized_winner is not None and item.get("winner") != normalized_winner:
            continue
        drift_summary = (
            item.get("driftSummary")
            if isinstance(item.get("driftSummary"), dict)
            else {}
        )
        if (
            normalized_policy_version is not None
            and str(drift_summary.get("policyVersion") or "").strip()
            != normalized_policy_version
        ):
            continue
        if (
            has_drift_breach is not None
            and bool(drift_summary.get("hasDriftBreach")) != has_drift_breach
        ):
            continue
        if (
            has_threshold_breach is not None
            and bool(drift_summary.get("hasThresholdBreach")) != has_threshold_breach
        ):
            continue
        shadow_summary = (
            item.get("shadowSummary")
            if isinstance(item.get("shadowSummary"), dict)
            else {}
        )
        if (
            has_shadow_breach is not None
            and bool(shadow_summary.get("hasShadowBreach")) != has_shadow_breach
        ):
            continue
        challenge_link = (
            item.get("challengeLink")
            if isinstance(item.get("challengeLink"), dict)
            else {}
        )
        if (
            has_open_review is not None
            and bool(challenge_link.get("hasOpenReview")) != has_open_review
        ):
            continue
        if (
            normalized_gate_conclusion is not None
            and str(item.get("gateConclusion") or "").strip().lower()
            != normalized_gate_conclusion
        ):
            continue
        if review_required is not None and bool(item.get("reviewRequired")) != review_required:
            continue
        panel = item.get("panelDisagreement")
        panel_map = panel if isinstance(panel, dict) else {}
        if (
            panel_high_disagreement is not None
            and bool(panel_map.get("high")) != panel_high_disagreement
        ):
            continue
        if normalized_challenge_state is not None:
            latest_challenge = (
                challenge_link.get("latest")
                if isinstance(challenge_link, dict)
                else None
            )
            latest_state = (
                str(latest_challenge.get("state") or "").strip()
                if isinstance(latest_challenge, dict)
                else ""
            )
            if latest_state != normalized_challenge_state:
                continue
        items.append(item)

    items.sort(
        key=lambda row: build_case_fairness_sort_key(item=row, sort_by=normalized_sort_by),
        reverse=(normalized_sort_order == "desc"),
    )
    total_count = len(items)
    aggregations = build_case_fairness_aggregations(items)
    page_items = items[offset : offset + limit]
    payload = {
        "count": total_count,
        "returned": len(page_items),
        "items": page_items,
        "aggregations": aggregations,
        "filters": {
            "status": normalized_status,
            "dispatchType": normalized_dispatch_type,
            "winner": normalized_winner,
            "policyVersion": normalized_policy_version,
            "hasDriftBreach": has_drift_breach,
            "hasThresholdBreach": has_threshold_breach,
            "hasShadowBreach": has_shadow_breach,
            "hasOpenReview": has_open_review,
            "gateConclusion": normalized_gate_conclusion,
            "challengeState": normalized_challenge_state,
            "sortBy": normalized_sort_by,
            "sortOrder": normalized_sort_order,
            "reviewRequired": review_required,
            "panelHighDisagreement": panel_high_disagreement,
            "offset": offset,
            "limit": limit,
        },
    }
    try:
        validate_case_fairness_list_contract(payload)
    except ValueError as err:
        raise FairnessRouteError(
            status_code=500,
            detail={
                "code": "fairness_case_list_contract_violation",
                "message": str(err),
            },
        ) from err
    return payload


async def build_fairness_dashboard_payload(
    *,
    x_ai_internal_key: str | None,
    status: str | None,
    dispatch_type: str | None,
    winner: str | None,
    policy_version: str | None,
    challenge_state: str | None,
    window_days: int,
    top_limit: int,
    case_scan_limit: int,
    collect_fairness_case_items: Callable[..., Awaitable[tuple[list[dict[str, Any]], int]]],
    list_judge_case_fairness: Callable[..., Awaitable[dict[str, Any]]],
    build_case_fairness_aggregations: Callable[[list[dict[str, Any]]], dict[str, Any]],
    build_fairness_dashboard_case_trends: Callable[..., list[dict[str, Any]]],
    build_fairness_dashboard_run_trends: Callable[..., dict[str, Any]],
    build_fairness_dashboard_top_risk_cases: Callable[..., list[dict[str, Any]]],
    list_fairness_benchmark_runs: Callable[..., Awaitable[list[Any]]],
    list_fairness_shadow_runs: Callable[..., Awaitable[list[Any]]],
    validate_fairness_dashboard_contract: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    collected_items, total_count = await collect_fairness_case_items(
        fetch_page=lambda offset, limit: list_judge_case_fairness(
            x_ai_internal_key=x_ai_internal_key,
            status=status,
            dispatch_type=dispatch_type,
            winner=winner,
            policy_version=policy_version,
            has_drift_breach=None,
            has_threshold_breach=None,
            has_shadow_breach=None,
            has_open_review=None,
            gate_conclusion=None,
            challenge_state=challenge_state,
            sort_by="updated_at",
            sort_order="desc",
            review_required=None,
            panel_high_disagreement=None,
            offset=offset,
            limit=limit,
        ),
        scan_limit=case_scan_limit,
        page_limit=200,
    )

    aggregations = build_case_fairness_aggregations(collected_items)
    gate_distribution = (
        aggregations.get("gateConclusionCounts")
        if isinstance(aggregations.get("gateConclusionCounts"), dict)
        else {}
    )
    case_trends = build_fairness_dashboard_case_trends(
        items=collected_items,
        window_days=window_days,
    )
    normalized_policy_version = str(policy_version or "").strip() or None
    benchmark_runs = await list_fairness_benchmark_runs(
        policy_version=normalized_policy_version,
        limit=200,
    )
    shadow_runs = await list_fairness_shadow_runs(
        policy_version=normalized_policy_version,
        limit=200,
    )
    run_trends = build_fairness_dashboard_run_trends(
        benchmark_runs=benchmark_runs,
        shadow_runs=shadow_runs,
        window_days=window_days,
    )
    top_risk_cases = build_fairness_dashboard_top_risk_cases(
        items=collected_items,
        top_limit=top_limit,
    )
    generated_at = datetime.now(timezone.utc).isoformat()
    total_matched = int(total_count or 0)
    scanned_count = len(collected_items)
    payload = {
        "generatedAt": generated_at,
        "overview": {
            "totalMatched": total_matched,
            "scannedCases": scanned_count,
            "scanTruncated": scanned_count < total_matched,
            "reviewRequiredCount": int(aggregations.get("reviewRequiredCount") or 0),
            "openReviewCount": int(aggregations.get("openReviewCount") or 0),
            "panelHighDisagreementCount": int(
                aggregations.get("panelHighDisagreementCount") or 0
            ),
            "driftBreachCount": int(aggregations.get("driftBreachCount") or 0),
            "thresholdBreachCount": int(aggregations.get("thresholdBreachCount") or 0),
            "shadowBreachCount": int(aggregations.get("shadowBreachCount") or 0),
        },
        "gateDistribution": {
            "pass_through": int(gate_distribution.get("pass_through") or 0),
            "blocked_to_draw": int(gate_distribution.get("blocked_to_draw") or 0),
            "unknown": int(gate_distribution.get("unknown") or 0),
        },
        "trends": {
            "windowDays": int(window_days),
            "caseDaily": case_trends,
            "benchmarkRuns": run_trends.get("benchmarkRuns")
            if isinstance(run_trends.get("benchmarkRuns"), list)
            else [],
            "shadowRuns": run_trends.get("shadowRuns")
            if isinstance(run_trends.get("shadowRuns"), list)
            else [],
        },
        "topRiskCases": top_risk_cases,
        "filters": {
            "status": status,
            "dispatchType": dispatch_type,
            "winner": winner,
            "policyVersion": normalized_policy_version,
            "challengeState": challenge_state,
            "windowDays": int(window_days),
            "topLimit": int(top_limit),
            "caseScanLimit": int(case_scan_limit),
        },
    }
    try:
        validate_fairness_dashboard_contract(payload)
    except ValueError as err:
        raise FairnessRouteError(
            status_code=500,
            detail={
                "code": "fairness_dashboard_contract_violation",
                "message": str(err),
            },
        ) from err
    return payload


def _sort_runs_by_reported_at_desc(rows: list[Any]) -> list[Any]:
    return sorted(
        rows,
        key=lambda row: row.reported_at.isoformat() if row.reported_at is not None else "",
        reverse=True,
    )


async def build_fairness_calibration_pack_payload(
    *,
    x_ai_internal_key: str | None,
    dispatch_type: str | None,
    status: str | None,
    winner: str | None,
    policy_version: str | None,
    challenge_state: str | None,
    case_scan_limit: int,
    risk_limit: int,
    benchmark_limit: int,
    shadow_limit: int,
    collect_fairness_case_items: Callable[..., Awaitable[tuple[list[dict[str, Any]], int]]],
    list_judge_case_fairness: Callable[..., Awaitable[dict[str, Any]]],
    list_fairness_benchmark_runs: Callable[..., Awaitable[list[Any]]],
    list_fairness_shadow_runs: Callable[..., Awaitable[list[Any]]],
    build_fairness_dashboard_top_risk_cases: Callable[..., list[dict[str, Any]]],
    build_fairness_calibration_threshold_suggestions: Callable[..., list[dict[str, Any]]],
    build_fairness_calibration_drift_summary: Callable[..., dict[str, Any]],
    build_fairness_calibration_risk_items: Callable[..., list[dict[str, Any]]],
    build_fairness_calibration_on_env_input_template: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    normalized_policy_version = str(policy_version or "").strip() or None
    normalized_benchmark_limit = max(1, min(int(benchmark_limit), 500))
    normalized_shadow_limit = max(1, min(int(shadow_limit), 500))
    normalized_risk_limit = max(1, min(int(risk_limit), 200))
    collected_items, total_count = await collect_fairness_case_items(
        fetch_page=lambda offset, limit: list_judge_case_fairness(
            x_ai_internal_key=x_ai_internal_key,
            status=status,
            dispatch_type=dispatch_type,
            winner=winner,
            policy_version=normalized_policy_version,
            has_drift_breach=None,
            has_threshold_breach=None,
            has_shadow_breach=None,
            has_open_review=None,
            gate_conclusion=None,
            challenge_state=challenge_state,
            sort_by="updated_at",
            sort_order="desc",
            review_required=None,
            panel_high_disagreement=None,
            offset=offset,
            limit=limit,
        ),
        scan_limit=case_scan_limit,
        page_limit=200,
    )

    benchmark_runs = await list_fairness_benchmark_runs(
        policy_version=normalized_policy_version,
        limit=normalized_benchmark_limit,
    )
    shadow_runs = await list_fairness_shadow_runs(
        policy_version=normalized_policy_version,
        limit=normalized_shadow_limit,
    )
    sorted_benchmark_runs = _sort_runs_by_reported_at_desc(benchmark_runs)
    sorted_shadow_runs = _sort_runs_by_reported_at_desc(shadow_runs)
    latest_benchmark_run = sorted_benchmark_runs[0] if sorted_benchmark_runs else None
    latest_shadow_run = sorted_shadow_runs[0] if sorted_shadow_runs else None

    top_risk_cases = build_fairness_dashboard_top_risk_cases(
        items=collected_items,
        top_limit=normalized_risk_limit,
    )
    threshold_suggestions = build_fairness_calibration_threshold_suggestions(
        benchmark_runs=sorted_benchmark_runs,
        shadow_runs=sorted_shadow_runs,
    )
    drift_summary = build_fairness_calibration_drift_summary(
        latest_benchmark_run=latest_benchmark_run,
        latest_shadow_run=latest_shadow_run,
    )
    risk_items = build_fairness_calibration_risk_items(
        benchmark_runs=sorted_benchmark_runs,
        shadow_runs=sorted_shadow_runs,
        top_risk_cases=top_risk_cases,
        risk_limit=normalized_risk_limit,
    )

    high_risk_count = 0
    benchmark_threshold_violation_count = 0
    shadow_threshold_violation_count = 0
    drift_breach_count = 0
    case_risk_count = 0
    for item in risk_items:
        if not isinstance(item, dict):
            continue
        risk_type = str(item.get("riskType") or "").strip()
        severity = str(item.get("severity") or "").strip().lower()
        if severity == "high":
            high_risk_count += 1
        if risk_type == "benchmark_threshold_violation":
            benchmark_threshold_violation_count += 1
        elif risk_type == "shadow_threshold_violation":
            shadow_threshold_violation_count += 1
        elif risk_type == "benchmark_drift_breach":
            drift_breach_count += 1
        elif risk_type == "case_risk_rank":
            case_risk_count += 1

    total_matched = int(total_count or 0)
    scanned_cases = len(collected_items)
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "overview": {
            "policyVersion": normalized_policy_version,
            "dispatchType": str(dispatch_type or "").strip().lower() or None,
            "totalMatched": total_matched,
            "scannedCases": scanned_cases,
            "scanTruncated": scanned_cases < total_matched,
            "benchmarkRunCount": len(sorted_benchmark_runs),
            "shadowRunCount": len(sorted_shadow_runs),
            "latestBenchmarkRunId": (
                latest_benchmark_run.run_id if latest_benchmark_run is not None else None
            ),
            "latestShadowRunId": (
                latest_shadow_run.run_id if latest_shadow_run is not None else None
            ),
            "highRiskCount": high_risk_count,
            "benchmarkThresholdViolationCount": benchmark_threshold_violation_count,
            "shadowThresholdViolationCount": shadow_threshold_violation_count,
            "driftBreachCount": drift_breach_count,
            "caseRiskCount": case_risk_count,
        },
        "thresholdSuggestions": threshold_suggestions,
        "driftSummary": drift_summary,
        "riskItems": risk_items,
        "onEnvInputTemplate": build_fairness_calibration_on_env_input_template(),
        "filters": {
            "dispatchType": str(dispatch_type or "").strip().lower() or None,
            "status": str(status or "").strip() or None,
            "winner": str(winner or "").strip().lower() or None,
            "policyVersion": normalized_policy_version,
            "challengeState": str(challenge_state or "").strip() or None,
            "caseScanLimit": int(case_scan_limit),
            "riskLimit": normalized_risk_limit,
            "benchmarkLimit": normalized_benchmark_limit,
            "shadowLimit": normalized_shadow_limit,
        },
    }


async def build_fairness_policy_calibration_advisor_payload(
    *,
    x_ai_internal_key: str | None,
    dispatch_type: str | None,
    status: str | None,
    winner: str | None,
    policy_version: str | None,
    challenge_state: str | None,
    case_scan_limit: int,
    risk_limit: int,
    benchmark_limit: int,
    shadow_limit: int,
    collect_fairness_case_items: Callable[..., Awaitable[tuple[list[dict[str, Any]], int]]],
    list_judge_case_fairness: Callable[..., Awaitable[dict[str, Any]]],
    list_fairness_benchmark_runs: Callable[..., Awaitable[list[Any]]],
    list_fairness_shadow_runs: Callable[..., Awaitable[list[Any]]],
    build_fairness_dashboard_top_risk_cases: Callable[..., list[dict[str, Any]]],
    build_fairness_calibration_threshold_suggestions: Callable[..., list[dict[str, Any]]],
    build_fairness_calibration_drift_summary: Callable[..., dict[str, Any]],
    build_fairness_calibration_risk_items: Callable[..., list[dict[str, Any]]],
    evaluate_policy_release_fairness_gate: Callable[..., Awaitable[dict[str, Any]]],
    build_fairness_policy_calibration_recommended_actions: Callable[..., list[dict[str, Any]]],
) -> dict[str, Any]:
    normalized_policy_version = str(policy_version or "").strip() or None
    normalized_benchmark_limit = max(1, min(int(benchmark_limit), 500))
    normalized_shadow_limit = max(1, min(int(shadow_limit), 500))
    normalized_risk_limit = max(1, min(int(risk_limit), 200))
    collected_items, total_count = await collect_fairness_case_items(
        fetch_page=lambda offset, limit: list_judge_case_fairness(
            x_ai_internal_key=x_ai_internal_key,
            status=status,
            dispatch_type=dispatch_type,
            winner=winner,
            policy_version=normalized_policy_version,
            has_drift_breach=None,
            has_threshold_breach=None,
            has_shadow_breach=None,
            has_open_review=None,
            gate_conclusion=None,
            challenge_state=challenge_state,
            sort_by="updated_at",
            sort_order="desc",
            review_required=None,
            panel_high_disagreement=None,
            offset=offset,
            limit=limit,
        ),
        scan_limit=case_scan_limit,
        page_limit=200,
    )

    benchmark_runs = await list_fairness_benchmark_runs(
        policy_version=normalized_policy_version,
        limit=normalized_benchmark_limit,
    )
    shadow_runs = await list_fairness_shadow_runs(
        policy_version=normalized_policy_version,
        limit=normalized_shadow_limit,
    )
    sorted_benchmark_runs = _sort_runs_by_reported_at_desc(benchmark_runs)
    sorted_shadow_runs = _sort_runs_by_reported_at_desc(shadow_runs)
    latest_benchmark_run = sorted_benchmark_runs[0] if sorted_benchmark_runs else None
    latest_shadow_run = sorted_shadow_runs[0] if sorted_shadow_runs else None
    inferred_policy_version = (
        normalized_policy_version
        or (
            latest_benchmark_run.policy_version if latest_benchmark_run is not None else None
        )
        or (latest_shadow_run.policy_version if latest_shadow_run is not None else None)
    )

    top_risk_cases = build_fairness_dashboard_top_risk_cases(
        items=collected_items,
        top_limit=normalized_risk_limit,
    )
    threshold_suggestions = build_fairness_calibration_threshold_suggestions(
        benchmark_runs=sorted_benchmark_runs,
        shadow_runs=sorted_shadow_runs,
    )
    drift_summary = build_fairness_calibration_drift_summary(
        latest_benchmark_run=latest_benchmark_run,
        latest_shadow_run=latest_shadow_run,
    )
    risk_items = build_fairness_calibration_risk_items(
        benchmark_runs=sorted_benchmark_runs,
        shadow_runs=sorted_shadow_runs,
        top_risk_cases=top_risk_cases,
        risk_limit=normalized_risk_limit,
    )
    release_gate = (
        await evaluate_policy_release_fairness_gate(policy_version=inferred_policy_version)
        if inferred_policy_version is not None
        else {
            "passed": False,
            "code": "registry_fairness_gate_no_policy_context",
            "message": "no policy context for fairness gate evaluation",
            "source": "benchmark",
            "benchmarkGatePassed": False,
            "shadowGateApplied": False,
            "shadowGatePassed": None,
            "thresholdDecision": None,
            "needsRemediation": None,
            "latestRun": None,
            "latestShadowRun": None,
        }
    )
    recommended_actions = build_fairness_policy_calibration_recommended_actions(
        release_gate=release_gate,
        policy_version=inferred_policy_version,
        risk_items=risk_items,
    )

    high_risk_count = sum(
        1
        for item in risk_items
        if isinstance(item, dict)
        and str(item.get("severity") or "").strip().lower() == "high"
    )
    total_matched = int(total_count or 0)
    scanned_cases = len(collected_items)
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "overview": {
            "policyVersion": inferred_policy_version,
            "dispatchType": str(dispatch_type or "").strip().lower() or None,
            "totalMatched": total_matched,
            "scannedCases": scanned_cases,
            "scanTruncated": scanned_cases < total_matched,
            "benchmarkRunCount": len(sorted_benchmark_runs),
            "shadowRunCount": len(sorted_shadow_runs),
            "latestBenchmarkRunId": (
                latest_benchmark_run.run_id if latest_benchmark_run is not None else None
            ),
            "latestShadowRunId": (
                latest_shadow_run.run_id if latest_shadow_run is not None else None
            ),
            "highRiskCount": high_risk_count,
            "releaseGatePassed": bool(release_gate.get("passed")),
            "releaseGateCode": str(release_gate.get("code") or "").strip() or None,
        },
        "thresholdSuggestions": threshold_suggestions,
        "driftSummary": drift_summary,
        "releaseGate": release_gate,
        "recommendedActions": recommended_actions,
        "riskItems": risk_items,
        "filters": {
            "dispatchType": str(dispatch_type or "").strip().lower() or None,
            "status": str(status or "").strip() or None,
            "winner": str(winner or "").strip().lower() or None,
            "policyVersion": normalized_policy_version,
            "effectivePolicyVersion": inferred_policy_version,
            "challengeState": str(challenge_state or "").strip() or None,
            "caseScanLimit": int(case_scan_limit),
            "riskLimit": normalized_risk_limit,
            "benchmarkLimit": normalized_benchmark_limit,
            "shadowLimit": normalized_shadow_limit,
        },
        "notes": [
            (
                "recommendedActions are advisory only and do not auto-publish "
                "or auto-activate policy versions."
            ),
        ],
    }
