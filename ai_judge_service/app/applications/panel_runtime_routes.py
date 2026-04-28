from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from .panel_runtime_profile_contract import PANEL_RUNTIME_READINESS_SWITCH_BLOCKERS

PANEL_SHADOW_CANDIDATE_AGREEMENT_MIN = 0.8
PANEL_SHADOW_CANDIDATE_COST_BUDGET_MAX = 0.05
PANEL_SHADOW_CANDIDATE_LATENCY_BUDGET_MS_MAX = 2000.0


class PanelRuntimeRouteError(Exception):
    def __init__(self, *, status_code: int, detail: Any):
        super().__init__(str(detail))
        self.status_code = int(status_code)
        self.detail = detail


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    if value is None or isinstance(value, bool):
        return float(default)
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return float(default)
    if math.isnan(parsed) or math.isinf(parsed):
        return float(default)
    return parsed


def _safe_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    token = str(value or "").strip().lower()
    if token in {"1", "true", "yes", "y", "on"}:
        return True
    if token in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _unique_tokens(values: list[Any] | tuple[Any, ...] | set[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        token = str(value or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _build_shadow_candidate_switch_blockers(
    *,
    candidate_models: list[str],
    shadow_enabled_rate: float,
    shadow_release_gate_signals: set[str],
    shadow_drift_signal_rate: float,
    avg_shadow_decision_agreement: float,
    avg_shadow_cost_estimate: float,
    avg_shadow_latency_estimate: float,
) -> list[str]:
    blockers: list[str] = []
    if shadow_enabled_rate <= 0 or "watch" in shadow_release_gate_signals:
        blockers.append("real_samples_missing")
    if avg_shadow_decision_agreement < PANEL_SHADOW_CANDIDATE_AGREEMENT_MIN:
        blockers.append("shadow_agreement_below_threshold")
    if avg_shadow_cost_estimate > PANEL_SHADOW_CANDIDATE_COST_BUDGET_MAX:
        blockers.append("cost_budget_exceeded")
    if avg_shadow_latency_estimate > PANEL_SHADOW_CANDIDATE_LATENCY_BUDGET_MS_MAX:
        blockers.append("latency_budget_exceeded")
    if "blocked" in shadow_release_gate_signals or shadow_drift_signal_rate > 0:
        blockers.append("release_gate_blocked")
    if not candidate_models:
        blockers.append("candidate_models_missing")
    allowed = set(PANEL_RUNTIME_READINESS_SWITCH_BLOCKERS)
    return [item for item in _unique_tokens(blockers) if item in allowed]


def _build_shadow_candidate_release_gate_signals(
    *,
    switch_blockers: list[str],
    candidate_model_count: int,
) -> dict[str, Any]:
    blocking_codes = {
        "shadow_agreement_below_threshold",
        "cost_budget_exceeded",
        "latency_budget_exceeded",
        "release_gate_blocked",
    }
    if any(code in blocking_codes for code in switch_blockers):
        status = "blocked"
    elif switch_blockers:
        status = "watch"
    else:
        status = "ready"
    return {
        "status": status,
        "blocksCandidateRollout": bool(switch_blockers),
        "switchBlockers": switch_blockers,
        "candidateModelCount": max(0, int(candidate_model_count)),
        "shadowAgreementThreshold": PANEL_SHADOW_CANDIDATE_AGREEMENT_MIN,
        "costBudgetMax": PANEL_SHADOW_CANDIDATE_COST_BUDGET_MAX,
        "latencyBudgetMsMax": PANEL_SHADOW_CANDIDATE_LATENCY_BUDGET_MS_MAX,
        "advisoryOnly": True,
        "autoSwitchAllowed": False,
        "officialWinnerSemanticsChanged": False,
    }


def normalize_panel_runtime_profile_source(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    return normalized


def normalize_panel_runtime_profile_sort_by(value: str | None) -> str:
    return str(value or "").strip().lower() or "updated_at"


def normalize_panel_runtime_profile_sort_order(value: str | None) -> str:
    return str(value or "").strip().lower() or "desc"


def build_panel_shadow_evaluation(
    *,
    case_item: dict[str, Any],
    runtime_profile: dict[str, Any],
    model_strategy: str | None,
) -> dict[str, Any]:
    strategy_metadata = (
        runtime_profile.get("strategyMetadata")
        if isinstance(runtime_profile.get("strategyMetadata"), dict)
        else {}
    )
    shadow_summary = (
        case_item.get("shadowSummary")
        if isinstance(case_item.get("shadowSummary"), dict)
        else {}
    )
    latest_run = (
        shadow_summary.get("latestRun")
        if isinstance(shadow_summary.get("latestRun"), dict)
        else {}
    )
    latest_metrics = (
        latest_run.get("metrics") if isinstance(latest_run.get("metrics"), dict) else {}
    )
    shadow_enabled = _safe_bool(
        runtime_profile.get("shadowEnabled")
        if runtime_profile.get("shadowEnabled") is not None
        else strategy_metadata.get("shadowEnabled"),
        default=latest_run != {},
    )
    shadow_model_strategy = (
        str(
            runtime_profile.get("shadowModelStrategy")
            or strategy_metadata.get("shadowModelStrategy")
            or model_strategy
            or ""
        ).strip()
        or None
    )
    winner_flip_rate = _safe_float(
        latest_run.get("winnerFlipRate")
        if latest_run.get("winnerFlipRate") is not None
        else latest_metrics.get("winnerFlipRate"),
        default=0.0,
    )
    if shadow_summary.get("decisionAgreement") is not None:
        raw_agreement = shadow_summary.get("decisionAgreement")
    elif latest_metrics.get("decisionAgreement") is not None:
        raw_agreement = latest_metrics.get("decisionAgreement")
    elif latest_run:
        raw_agreement = 1.0 - winner_flip_rate
    else:
        raw_agreement = 0.0
    decision_agreement = max(0.0, min(1.0, _safe_float(raw_agreement, default=0.0)))
    cost_estimate = _safe_float(
        runtime_profile.get("shadowCostEstimate")
        if runtime_profile.get("shadowCostEstimate") is not None
        else strategy_metadata.get("shadowCostEstimate"),
        default=0.0,
    )
    latency_estimate = _safe_float(
        runtime_profile.get("shadowLatencyEstimate")
        if runtime_profile.get("shadowLatencyEstimate") is not None
        else strategy_metadata.get("shadowLatencyEstimate"),
        default=0.0,
    )
    breaches = (
        shadow_summary.get("breaches")
        if isinstance(shadow_summary.get("breaches"), list)
        else []
    )
    signals = _unique_tokens(list(breaches))
    has_shadow_breach = bool(shadow_summary.get("hasShadowBreach"))
    if has_shadow_breach:
        signals = _unique_tokens([*signals, "shadow_breach"])
    panel = (
        case_item.get("panelDisagreement")
        if isinstance(case_item.get("panelDisagreement"), dict)
        else {}
    )
    if bool(panel.get("high")):
        signals = _unique_tokens([*signals, "panel_high_disagreement"])
    if shadow_enabled and not latest_run:
        signals = _unique_tokens([*signals, "shadow_run_missing"])

    if has_shadow_breach or bool(panel.get("high")):
        release_gate_signal = "blocked"
    elif shadow_enabled and not latest_run:
        release_gate_signal = "watch"
    elif shadow_enabled:
        release_gate_signal = "ready"
    else:
        release_gate_signal = "advisory_only"

    return {
        "enabled": shadow_enabled,
        "modelStrategy": shadow_model_strategy,
        "decisionAgreement": round(decision_agreement, 4),
        "costEstimate": round(cost_estimate, 6),
        "latencyEstimate": round(latency_estimate, 2),
        "driftSignals": signals,
        "releaseGateSignal": {
            "status": release_gate_signal,
            "blocksAutoRelease": release_gate_signal == "blocked",
            "reasons": signals,
            "advisoryOnly": True,
        },
        "latestRun": latest_run or None,
        "benchmarkRunId": shadow_summary.get("benchmarkRunId"),
        "officialWinnerMutationAllowed": False,
        "advisoryOnly": True,
    }


def build_panel_runtime_profile_item(
    *,
    case_item: dict[str, Any],
    judge_id: str,
    runtime_profile: dict[str, Any],
) -> dict[str, Any]:
    panel = (
        case_item.get("panelDisagreement")
        if isinstance(case_item.get("panelDisagreement"), dict)
        else {}
    )
    challenge_link = (
        case_item.get("challengeLink")
        if isinstance(case_item.get("challengeLink"), dict)
        else {}
    )
    latest_challenge = (
        challenge_link.get("latest")
        if isinstance(challenge_link.get("latest"), dict)
        else {}
    )
    drift_summary = (
        case_item.get("driftSummary")
        if isinstance(case_item.get("driftSummary"), dict)
        else {}
    )

    profile_source = (
        str(runtime_profile.get("profileSource") or "").strip().lower() or "unknown"
    )
    profile_id = str(runtime_profile.get("profileId") or "").strip() or None
    model_strategy = str(runtime_profile.get("modelStrategy") or "").strip() or None
    score_source = str(runtime_profile.get("scoreSource") or "").strip() or None
    strategy_slot = str(runtime_profile.get("strategySlot") or "").strip() or None
    prompt_version = str(runtime_profile.get("promptVersion") or "").strip() or None
    toolset_version = str(runtime_profile.get("toolsetVersion") or "").strip() or None
    domain_slot = str(runtime_profile.get("domainSlot") or "").strip() or None
    runtime_stage = str(runtime_profile.get("runtimeStage") or "").strip() or None
    candidate_models = (
        [
            str(item).strip()
            for item in runtime_profile.get("candidateModels", [])
            if str(item).strip()
        ]
        if isinstance(runtime_profile.get("candidateModels"), list)
        else []
    )
    strategy_metadata = (
        dict(runtime_profile.get("strategyMetadata"))
        if isinstance(runtime_profile.get("strategyMetadata"), dict)
        else {}
    )
    policy_version = (
        str(runtime_profile.get("policyVersion") or "").strip()
        or str(drift_summary.get("policyVersion") or "").strip()
        or None
    )
    shadow = build_panel_shadow_evaluation(
        case_item=case_item,
        runtime_profile=runtime_profile,
        model_strategy=model_strategy,
    )

    return {
        "caseId": int(case_item.get("caseId") or 0),
        "traceId": str(case_item.get("traceId") or "").strip() or None,
        "dispatchType": str(case_item.get("dispatchType") or "").strip() or None,
        "workflowStatus": str(case_item.get("workflowStatus") or "").strip() or None,
        "updatedAt": str(case_item.get("updatedAt") or "").strip() or None,
        "winner": str(case_item.get("winner") or "").strip().lower() or None,
        "gateConclusion": str(case_item.get("gateConclusion") or "").strip().lower() or None,
        "reviewRequired": bool(case_item.get("reviewRequired")),
        "hasOpenReview": bool(challenge_link.get("hasOpenReview")),
        "challengeState": str(latest_challenge.get("state") or "").strip() or None,
        "panelDisagreement": {
            "high": bool(panel.get("high")),
            "ratio": _safe_float(panel.get("ratio"), default=0.0),
            "ratioMax": _safe_float(panel.get("ratioMax"), default=0.0),
            "reasons": [
                str(item).strip()
                for item in (panel.get("reasons") or [])
                if str(item).strip()
            ],
            "majorityWinner": str(panel.get("majorityWinner") or "").strip().lower() or None,
            "voteBySide": (
                panel.get("voteBySide")
                if isinstance(panel.get("voteBySide"), dict)
                else {}
            ),
        },
        "judgeId": judge_id,
        "profileId": profile_id,
        "profileSource": profile_source,
        "modelStrategy": model_strategy,
        "strategySlot": strategy_slot,
        "scoreSource": score_source,
        "decisionMargin": _safe_float(runtime_profile.get("decisionMargin"), default=0.0),
        "promptVersion": prompt_version,
        "toolsetVersion": toolset_version,
        "domainSlot": domain_slot,
        "runtimeStage": runtime_stage,
        "adaptiveEnabled": bool(runtime_profile.get("adaptiveEnabled")),
        "candidateModels": candidate_models,
        "strategyMetadata": strategy_metadata,
        "policyVersion": policy_version,
        "shadowEnabled": bool(shadow["enabled"]),
        "shadowModelStrategy": shadow["modelStrategy"],
        "shadowDecisionAgreement": shadow["decisionAgreement"],
        "shadowCostEstimate": shadow["costEstimate"],
        "shadowLatencyEstimate": shadow["latencyEstimate"],
        "shadowDriftSignals": shadow["driftSignals"],
        "shadowReleaseGateSignal": shadow["releaseGateSignal"],
        "shadowEvaluation": shadow,
        "runtimeProfile": dict(runtime_profile),
    }


def build_panel_runtime_profile_sort_key(
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
            str(item.get("judgeId") or ""),
        )
    if sort_by == "case_id":
        return (
            int(item.get("caseId") or 0),
            str(item.get("judgeId") or ""),
        )
    if sort_by == "judge_id":
        return (
            str(item.get("judgeId") or ""),
            int(item.get("caseId") or 0),
        )
    if sort_by == "profile_id":
        return (
            str(item.get("profileId") or ""),
            int(item.get("caseId") or 0),
            str(item.get("judgeId") or ""),
        )
    if sort_by == "model_strategy":
        return (
            str(item.get("modelStrategy") or ""),
            int(item.get("caseId") or 0),
            str(item.get("judgeId") or ""),
        )
    if sort_by == "strategy_slot":
        return (
            str(item.get("strategySlot") or ""),
            int(item.get("caseId") or 0),
            str(item.get("judgeId") or ""),
        )
    if sort_by == "domain_slot":
        return (
            str(item.get("domainSlot") or ""),
            int(item.get("caseId") or 0),
            str(item.get("judgeId") or ""),
        )
    return (
        str(item.get("updatedAt") or "").strip(),
        int(item.get("caseId") or 0),
        str(item.get("judgeId") or ""),
    )


def build_panel_runtime_profile_aggregations(items: list[dict[str, Any]]) -> dict[str, Any]:
    judge_counts: dict[str, int] = {}
    profile_id_counts: dict[str, int] = {"unknown": 0}
    model_strategy_counts: dict[str, int] = {"unknown": 0}
    strategy_slot_counts: dict[str, int] = {"unknown": 0}
    domain_slot_counts: dict[str, int] = {"unknown": 0}
    profile_source_counts: dict[str, int] = {"unknown": 0}
    policy_version_counts: dict[str, int] = {"unknown": 0}
    shadow_model_strategy_counts: dict[str, int] = {"unknown": 0}
    winner_counts: dict[str, int] = {
        "pro": 0,
        "con": 0,
        "draw": 0,
        "unknown": 0,
    }
    review_required_count = 0
    open_review_count = 0
    panel_high_disagreement_count = 0
    disagreement_ratio_sum = 0.0
    shadow_enabled_count = 0
    shadow_agreement_count = 0
    shadow_drift_signal_count = 0
    shadow_decision_agreement_sum = 0.0
    shadow_cost_estimate_sum = 0.0
    shadow_latency_estimate_sum = 0.0

    for item in items:
        judge_id = str(item.get("judgeId") or "").strip() or "unknown"
        judge_counts[judge_id] = judge_counts.get(judge_id, 0) + 1

        profile_id = str(item.get("profileId") or "").strip()
        if profile_id:
            profile_id_counts[profile_id] = profile_id_counts.get(profile_id, 0) + 1
        else:
            profile_id_counts["unknown"] += 1

        model_strategy = str(item.get("modelStrategy") or "").strip()
        if model_strategy:
            model_strategy_counts[model_strategy] = (
                model_strategy_counts.get(model_strategy, 0) + 1
            )
        else:
            model_strategy_counts["unknown"] += 1

        strategy_slot = str(item.get("strategySlot") or "").strip()
        if strategy_slot:
            strategy_slot_counts[strategy_slot] = strategy_slot_counts.get(strategy_slot, 0) + 1
        else:
            strategy_slot_counts["unknown"] += 1

        domain_slot = str(item.get("domainSlot") or "").strip()
        if domain_slot:
            domain_slot_counts[domain_slot] = domain_slot_counts.get(domain_slot, 0) + 1
        else:
            domain_slot_counts["unknown"] += 1

        profile_source = str(item.get("profileSource") or "").strip().lower()
        if profile_source:
            profile_source_counts[profile_source] = profile_source_counts.get(profile_source, 0) + 1
        else:
            profile_source_counts["unknown"] += 1

        policy_version = str(item.get("policyVersion") or "").strip()
        if policy_version:
            policy_version_counts[policy_version] = policy_version_counts.get(policy_version, 0) + 1
        else:
            policy_version_counts["unknown"] += 1

        shadow_model_strategy = str(item.get("shadowModelStrategy") or "").strip()
        if shadow_model_strategy:
            shadow_model_strategy_counts[shadow_model_strategy] = (
                shadow_model_strategy_counts.get(shadow_model_strategy, 0) + 1
            )
        else:
            shadow_model_strategy_counts["unknown"] += 1

        winner = str(item.get("winner") or "").strip().lower()
        if winner in winner_counts:
            winner_counts[winner] += 1
        else:
            winner_counts["unknown"] += 1

        if bool(item.get("reviewRequired")):
            review_required_count += 1
        if bool(item.get("hasOpenReview")):
            open_review_count += 1
        panel = (
            item.get("panelDisagreement")
            if isinstance(item.get("panelDisagreement"), dict)
            else {}
        )
        if bool(panel.get("high")):
            panel_high_disagreement_count += 1
        disagreement_ratio_sum += _safe_float(panel.get("ratio"), default=0.0)
        if bool(item.get("shadowEnabled")):
            shadow_enabled_count += 1
        shadow_decision_agreement = _safe_float(
            item.get("shadowDecisionAgreement"),
            default=0.0,
        )
        if shadow_decision_agreement >= 0.8:
            shadow_agreement_count += 1
        shadow_decision_agreement_sum += shadow_decision_agreement
        shadow_cost_estimate_sum += _safe_float(item.get("shadowCostEstimate"), default=0.0)
        shadow_latency_estimate_sum += _safe_float(
            item.get("shadowLatencyEstimate"),
            default=0.0,
        )
        signals = item.get("shadowDriftSignals")
        if isinstance(signals, list) and len(signals) > 0:
            shadow_drift_signal_count += 1

    total_matched = len(items)
    return {
        "totalMatched": total_matched,
        "reviewRequiredCount": review_required_count,
        "openReviewCount": open_review_count,
        "panelHighDisagreementCount": panel_high_disagreement_count,
        "avgPanelDisagreementRatio": (
            disagreement_ratio_sum / total_matched if total_matched > 0 else 0.0
        ),
        "byJudgeId": dict(sorted(judge_counts.items(), key=lambda kv: kv[0])),
        "byProfileId": dict(sorted(profile_id_counts.items(), key=lambda kv: kv[0])),
        "byModelStrategy": dict(sorted(model_strategy_counts.items(), key=lambda kv: kv[0])),
        "byStrategySlot": dict(sorted(strategy_slot_counts.items(), key=lambda kv: kv[0])),
        "byDomainSlot": dict(sorted(domain_slot_counts.items(), key=lambda kv: kv[0])),
        "byProfileSource": dict(sorted(profile_source_counts.items(), key=lambda kv: kv[0])),
        "byPolicyVersion": dict(sorted(policy_version_counts.items(), key=lambda kv: kv[0])),
        "byShadowModelStrategy": dict(
            sorted(shadow_model_strategy_counts.items(), key=lambda kv: kv[0])
        ),
        "winnerCounts": winner_counts,
        "shadowEnabledCount": shadow_enabled_count,
        "shadowAgreementCount": shadow_agreement_count,
        "shadowDriftSignalCount": shadow_drift_signal_count,
        "avgShadowDecisionAgreement": (
            shadow_decision_agreement_sum / total_matched if total_matched > 0 else 0.0
        ),
        "avgShadowCostEstimate": (
            shadow_cost_estimate_sum / total_matched if total_matched > 0 else 0.0
        ),
        "avgShadowLatencyEstimate": (
            shadow_latency_estimate_sum / total_matched if total_matched > 0 else 0.0
        ),
    }


def build_panel_runtime_readiness_summary(
    *,
    items: list[dict[str, Any]],
    group_limit: int,
    attention_limit: int,
) -> dict[str, Any]:
    grouped: dict[str, dict[str, Any]] = {}
    for item in items:
        strategy_slot = str(item.get("strategySlot") or "").strip() or "unknown"
        domain_slot = str(item.get("domainSlot") or "").strip() or "unknown"
        model_strategy = str(item.get("modelStrategy") or "").strip() or "unknown"
        profile_id = str(item.get("profileId") or "").strip() or "unknown"
        policy_version = str(item.get("policyVersion") or "").strip() or "unknown"
        group_key = (
            f"{strategy_slot}|{domain_slot}|{model_strategy}|{profile_id}|{policy_version}"
        )

        row = grouped.setdefault(
            group_key,
            {
                "groupKey": group_key,
                "strategySlot": strategy_slot,
                "domainSlot": domain_slot,
                "modelStrategy": model_strategy,
                "profileId": profile_id,
                "policyVersion": policy_version,
                "recordCount": 0,
                "caseIds": set(),
                "judgeIds": set(),
                "profileSources": set(),
                "candidateModels": set(),
                "adaptiveEnabledCount": 0,
                "reviewRequiredCount": 0,
                "openReviewCount": 0,
                "panelHighDisagreementCount": 0,
                "panelDisagreementRatioSum": 0.0,
                "shadowEnabledCount": 0,
                "shadowDriftSignalCount": 0,
                "shadowDecisionAgreementSum": 0.0,
                "shadowCostEstimateSum": 0.0,
                "shadowLatencyEstimateSum": 0.0,
                "shadowReleaseGateSignals": set(),
            },
        )
        row["recordCount"] += 1
        case_id = int(item.get("caseId") or 0)
        if case_id > 0:
            row["caseIds"].add(case_id)
        judge_id = str(item.get("judgeId") or "").strip()
        if judge_id:
            row["judgeIds"].add(judge_id)
        source = str(item.get("profileSource") or "").strip().lower()
        if source:
            row["profileSources"].add(source)
        if bool(item.get("adaptiveEnabled")):
            row["adaptiveEnabledCount"] += 1
        if bool(item.get("reviewRequired")):
            row["reviewRequiredCount"] += 1
        if bool(item.get("hasOpenReview")):
            row["openReviewCount"] += 1
        panel = (
            item.get("panelDisagreement")
            if isinstance(item.get("panelDisagreement"), dict)
            else {}
        )
        if bool(panel.get("high")):
            row["panelHighDisagreementCount"] += 1
        row["panelDisagreementRatioSum"] += _safe_float(panel.get("ratio"), default=0.0)
        if bool(item.get("shadowEnabled")):
            row["shadowEnabledCount"] += 1
        signals = item.get("shadowDriftSignals")
        if isinstance(signals, list) and len(signals) > 0:
            row["shadowDriftSignalCount"] += 1
        row["shadowDecisionAgreementSum"] += _safe_float(
            item.get("shadowDecisionAgreement"),
            default=0.0,
        )
        row["shadowCostEstimateSum"] += _safe_float(
            item.get("shadowCostEstimate"),
            default=0.0,
        )
        row["shadowLatencyEstimateSum"] += _safe_float(
            item.get("shadowLatencyEstimate"),
            default=0.0,
        )
        release_signal = (
            item.get("shadowReleaseGateSignal")
            if isinstance(item.get("shadowReleaseGateSignal"), dict)
            else {}
        )
        signal_status = str(release_signal.get("status") or "").strip()
        if signal_status:
            row["shadowReleaseGateSignals"].add(signal_status)
        for candidate_model in item.get("candidateModels") or []:
            candidate_model_token = str(candidate_model).strip()
            if candidate_model_token:
                row["candidateModels"].add(candidate_model_token)

    group_rows: list[dict[str, Any]] = []
    for row in grouped.values():
        record_count = int(row["recordCount"])
        panel_high_count = int(row["panelHighDisagreementCount"])
        review_required_count = int(row["reviewRequiredCount"])
        open_review_count = int(row["openReviewCount"])
        candidate_models = sorted(str(item) for item in row["candidateModels"])
        panel_high_rate = panel_high_count / record_count if record_count > 0 else 0.0
        review_required_rate = (
            review_required_count / record_count if record_count > 0 else 0.0
        )
        open_review_rate = open_review_count / record_count if record_count > 0 else 0.0
        avg_disagreement_ratio = (
            float(row["panelDisagreementRatioSum"]) / record_count
            if record_count > 0
            else 0.0
        )
        adaptive_enabled_rate = (
            int(row["adaptiveEnabledCount"]) / record_count if record_count > 0 else 0.0
        )
        shadow_enabled_rate = (
            int(row["shadowEnabledCount"]) / record_count if record_count > 0 else 0.0
        )
        shadow_drift_signal_rate = (
            int(row["shadowDriftSignalCount"]) / record_count if record_count > 0 else 0.0
        )
        avg_shadow_decision_agreement = (
            float(row["shadowDecisionAgreementSum"]) / record_count
            if record_count > 0
            else 0.0
        )
        avg_shadow_cost_estimate = (
            float(row["shadowCostEstimateSum"]) / record_count
            if record_count > 0
            else 0.0
        )
        avg_shadow_latency_estimate = (
            float(row["shadowLatencyEstimateSum"]) / record_count
            if record_count > 0
            else 0.0
        )
        shadow_release_gate_signals = {
            str(item).strip()
            for item in row["shadowReleaseGateSignals"]
            if str(item).strip()
        }
        switch_blockers = _build_shadow_candidate_switch_blockers(
            candidate_models=candidate_models,
            shadow_enabled_rate=shadow_enabled_rate,
            shadow_release_gate_signals=shadow_release_gate_signals,
            shadow_drift_signal_rate=shadow_drift_signal_rate,
            avg_shadow_decision_agreement=avg_shadow_decision_agreement,
            avg_shadow_cost_estimate=avg_shadow_cost_estimate,
            avg_shadow_latency_estimate=avg_shadow_latency_estimate,
        )
        release_gate_signals = _build_shadow_candidate_release_gate_signals(
            switch_blockers=switch_blockers,
            candidate_model_count=len(candidate_models),
        )
        readiness_score = max(
            0.0,
            min(
                100.0,
                100.0
                - panel_high_rate * 60.0
                - review_required_rate * 30.0
                - open_review_rate * 10.0
                - shadow_drift_signal_rate * 20.0,
            ),
        )

        if readiness_score < 60.0:
            readiness_level = "attention"
        elif readiness_score < 80.0:
            readiness_level = "watch"
        else:
            readiness_level = "ready"

        switch_conditions: list[str] = []
        if panel_high_rate >= 0.2:
            switch_conditions.append("panel_disagreement_ratio_high")
        if review_required_rate >= 0.2:
            switch_conditions.append("review_required_rate_high")
        if open_review_rate >= 0.1:
            switch_conditions.append("open_review_backlog")
        if shadow_drift_signal_rate > 0:
            switch_conditions.append("shadow_drift_signal")
        if not candidate_models:
            switch_conditions.append("candidate_models_missing")
        if not switch_conditions:
            switch_conditions.append("stable_runtime")

        simulations: list[dict[str, Any]] = []
        if len(candidate_models) >= 2 and readiness_level != "ready":
            simulations.append(
                {
                    "scenarioId": "switch_to_secondary_candidate",
                    "trigger": switch_conditions[0],
                    "candidateModel": candidate_models[1],
                    "expectedImpact": "reduce disagreement and review pressure",
                    "advisoryOnly": True,
                }
            )
        else:
            simulations.append(
                {
                    "scenarioId": "keep_current_strategy",
                    "trigger": switch_conditions[0],
                    "candidateModel": candidate_models[0] if candidate_models else None,
                    "expectedImpact": "maintain current runtime strategy and monitor drift",
                    "advisoryOnly": True,
                }
            )

        group_rows.append(
            {
                "groupKey": row["groupKey"],
                "strategySlot": row["strategySlot"],
                "domainSlot": row["domainSlot"],
                "modelStrategy": row["modelStrategy"],
                "profileId": row["profileId"],
                "policyVersion": row["policyVersion"],
                "recordCount": record_count,
                "caseCount": len(row["caseIds"]),
                "judgeIds": sorted(str(item) for item in row["judgeIds"]),
                "profileSources": sorted(str(item) for item in row["profileSources"]),
                "candidateModels": candidate_models,
                "candidateModelCount": len(candidate_models),
                "adaptiveEnabledRate": round(adaptive_enabled_rate, 4),
                "shadowEnabledCount": int(row["shadowEnabledCount"]),
                "shadowEnabledRate": round(shadow_enabled_rate, 4),
                "shadowDriftSignalCount": int(row["shadowDriftSignalCount"]),
                "shadowDriftSignalRate": round(shadow_drift_signal_rate, 4),
                "avgShadowDecisionAgreement": round(avg_shadow_decision_agreement, 4),
                "avgShadowCostEstimate": round(avg_shadow_cost_estimate, 6),
                "avgShadowLatencyEstimate": round(avg_shadow_latency_estimate, 2),
                "shadowReleaseGateSignals": sorted(
                    str(item) for item in row["shadowReleaseGateSignals"]
                ),
                "panelHighDisagreementCount": panel_high_count,
                "panelHighDisagreementRate": round(panel_high_rate, 4),
                "reviewRequiredCount": review_required_count,
                "reviewRequiredRate": round(review_required_rate, 4),
                "openReviewCount": open_review_count,
                "openReviewRate": round(open_review_rate, 4),
                "avgPanelDisagreementRatio": round(avg_disagreement_ratio, 4),
                "readinessScore": round(readiness_score, 2),
                "readinessLevel": readiness_level,
                "switchBlockers": switch_blockers,
                "releaseGateSignals": release_gate_signals,
                "recommendedSwitchConditions": switch_conditions,
                "simulations": simulations,
            }
        )

    group_rows.sort(
        key=lambda row: (
            float(row.get("readinessScore") or 0.0),
            float(row.get("panelHighDisagreementRate") or 0.0),
            float(row.get("reviewRequiredRate") or 0.0),
            str(row.get("groupKey") or ""),
        ),
    )
    limited_group_rows = group_rows[: max(1, min(int(group_limit), 200))]
    attention_rows = [
        row for row in limited_group_rows if str(row.get("readinessLevel")) != "ready"
    ][: max(1, min(int(attention_limit), 100))]

    readiness_counts = {
        "ready": 0,
        "watch": 0,
        "attention": 0,
    }
    shadow_enabled_groups = 0
    shadow_blocked_groups = 0
    shadow_watch_groups = 0
    shadow_drift_signal_groups = 0
    shadow_candidate_model_groups = 0
    shadow_cost_sum = 0.0
    shadow_latency_sum = 0.0
    shadow_decision_agreement_sum = 0.0
    release_gate_signal_counts = {
        "ready": 0,
        "watch": 0,
        "blocked": 0,
    }
    switch_blocker_counts = {
        blocker: 0 for blocker in PANEL_RUNTIME_READINESS_SWITCH_BLOCKERS
    }
    for row in limited_group_rows:
        level = str(row.get("readinessLevel") or "").strip().lower()
        if level in readiness_counts:
            readiness_counts[level] += 1
        signals = row.get("shadowReleaseGateSignals")
        signal_tokens = (
            {str(item).strip() for item in signals if str(item).strip()}
            if isinstance(signals, list)
            else set()
        )
        if float(row.get("shadowEnabledRate") or 0.0) > 0:
            shadow_enabled_groups += 1
        if "blocked" in signal_tokens:
            shadow_blocked_groups += 1
        if "watch" in signal_tokens:
            shadow_watch_groups += 1
        if int(row.get("shadowDriftSignalCount") or 0) > 0:
            shadow_drift_signal_groups += 1
        if int(row.get("candidateModelCount") or 0) > 0:
            shadow_candidate_model_groups += 1
        shadow_cost_sum += float(row.get("avgShadowCostEstimate") or 0.0)
        shadow_latency_sum += float(row.get("avgShadowLatencyEstimate") or 0.0)
        shadow_decision_agreement_sum += float(
            row.get("avgShadowDecisionAgreement") or 0.0
        )
        release_gate_signals = (
            row.get("releaseGateSignals")
            if isinstance(row.get("releaseGateSignals"), dict)
            else {}
        )
        release_status = str(release_gate_signals.get("status") or "").strip().lower()
        if release_status in release_gate_signal_counts:
            release_gate_signal_counts[release_status] += 1
        for blocker in row.get("switchBlockers") or []:
            blocker_token = str(blocker or "").strip()
            if blocker_token in switch_blocker_counts:
                switch_blocker_counts[blocker_token] += 1

    return {
        "groups": limited_group_rows,
        "attentionGroups": attention_rows,
        "overview": {
            "totalRecords": len(items),
            "totalGroups": len(limited_group_rows),
            "readinessCounts": readiness_counts,
            "attentionGroupCount": len(attention_rows),
            "shadow": {
                "enabledGroupCount": shadow_enabled_groups,
                "blockedGroupCount": shadow_blocked_groups,
                "watchGroupCount": shadow_watch_groups,
                "driftSignalGroupCount": shadow_drift_signal_groups,
                "candidateModelGroupCount": shadow_candidate_model_groups,
                "releaseGateSignalCounts": release_gate_signal_counts,
                "switchBlockerCounts": switch_blocker_counts,
                "avgDecisionAgreement": (
                    shadow_decision_agreement_sum / len(limited_group_rows)
                    if limited_group_rows
                    else 0.0
                ),
                "avgCostEstimate": (
                    shadow_cost_sum / len(limited_group_rows)
                    if limited_group_rows
                    else 0.0
                ),
                "avgLatencyEstimate": (
                    shadow_latency_sum / len(limited_group_rows)
                    if limited_group_rows
                    else 0.0
                ),
                "officialWinnerMutationAllowed": False,
                "officialWinnerSemanticsChanged": False,
                "autoSwitchAllowed": False,
            },
        },
    }


def normalize_panel_runtime_profile_query(
    *,
    status: str | None,
    dispatch_type: str | None,
    winner: str | None,
    policy_version: str | None,
    gate_conclusion: str | None,
    challenge_state: str | None,
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
    panel_judge_ids: tuple[str, ...] | list[str],
    panel_runtime_profile_source_values: set[str] | frozenset[str],
    panel_runtime_profile_sort_fields: set[str] | frozenset[str],
    normalize_workflow_status: Callable[[str | None], str | None],
    normalize_panel_runtime_profile_source: Callable[[str | None], str | None],
    normalize_panel_runtime_profile_sort_by: Callable[[str | None], str],
    normalize_panel_runtime_profile_sort_order: Callable[[str | None], str],
    normalize_case_fairness_gate_conclusion: Callable[[str | None], str | None],
    normalize_case_fairness_challenge_state: Callable[[str | None], str | None],
) -> dict[str, Any]:
    normalized_judge_id = str(judge_id or "").strip() or None
    if normalized_judge_id is not None and normalized_judge_id not in panel_judge_ids:
        raise PanelRuntimeRouteError(status_code=422, detail="invalid_panel_judge_id")
    normalized_profile_source = normalize_panel_runtime_profile_source(profile_source)
    if (
        normalized_profile_source is not None
        and normalized_profile_source not in panel_runtime_profile_source_values
    ):
        raise PanelRuntimeRouteError(
            status_code=422,
            detail="invalid_panel_profile_source",
        )
    normalized_sort_by = normalize_panel_runtime_profile_sort_by(sort_by)
    if normalized_sort_by not in panel_runtime_profile_sort_fields:
        raise PanelRuntimeRouteError(status_code=422, detail="invalid_panel_runtime_sort_by")
    normalized_sort_order = normalize_panel_runtime_profile_sort_order(sort_order)
    if normalized_sort_order not in {"asc", "desc"}:
        raise PanelRuntimeRouteError(
            status_code=422,
            detail="invalid_panel_runtime_sort_order",
        )
    return {
        "status": normalize_workflow_status(status),
        "dispatchType": str(dispatch_type or "").strip().lower() or None,
        "winner": str(winner or "").strip().lower() or None,
        "policyVersion": str(policy_version or "").strip() or None,
        "gateConclusion": normalize_case_fairness_gate_conclusion(gate_conclusion),
        "challengeState": normalize_case_fairness_challenge_state(challenge_state),
        "judgeId": normalized_judge_id,
        "profileSource": normalized_profile_source,
        "profileId": str(profile_id or "").strip() or None,
        "modelStrategy": str(model_strategy or "").strip() or None,
        "strategySlot": str(strategy_slot or "").strip() or None,
        "domainSlot": str(domain_slot or "").strip() or None,
        "sortBy": normalized_sort_by,
        "sortOrder": normalized_sort_order,
        "offset": max(0, int(offset)),
        "limit": max(1, min(int(limit), 200)),
    }


async def build_panel_runtime_profiles_payload(
    *,
    list_judge_case_fairness: Callable[..., Awaitable[dict[str, Any]]],
    build_panel_runtime_profile_item: Callable[..., dict[str, Any]],
    build_panel_runtime_profile_sort_key: Callable[..., Any],
    build_panel_runtime_profile_aggregations: Callable[[list[dict[str, Any]]], dict[str, Any]],
    validate_panel_runtime_profile_contract: Callable[[dict[str, Any]], None],
    panel_judge_ids: tuple[str, ...] | list[str],
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
    normalized_judge_id: str | None,
    normalized_profile_source: str | None,
    normalized_profile_id: str | None,
    normalized_model_strategy: str | None,
    normalized_strategy_slot: str | None,
    normalized_domain_slot: str | None,
    normalized_sort_by: str,
    normalized_sort_order: str,
    normalized_status: str | None,
    normalized_dispatch_type: str | None,
    normalized_winner: str | None,
    normalized_policy_version: str | None,
    normalized_gate_conclusion: str | None,
    normalized_challenge_state: str | None,
    offset: int,
    limit: int,
) -> dict[str, Any]:
    fairness_case_items: list[dict[str, Any]] = []
    fairness_offset = 0
    while True:
        fairness_page = await list_judge_case_fairness(
            x_ai_internal_key=x_ai_internal_key,
            status=status,
            dispatch_type=dispatch_type,
            winner=winner,
            policy_version=policy_version,
            has_drift_breach=None,
            has_threshold_breach=None,
            has_shadow_breach=None,
            has_open_review=has_open_review,
            gate_conclusion=gate_conclusion,
            challenge_state=challenge_state,
            sort_by="updated_at",
            sort_order="desc",
            review_required=review_required,
            panel_high_disagreement=panel_high_disagreement,
            offset=fairness_offset,
            limit=200,
        )
        page_items = (
            fairness_page.get("items")
            if isinstance(fairness_page.get("items"), list)
            else []
        )
        if not page_items:
            break
        fairness_case_items.extend(page_items)
        if len(page_items) < 200:
            break
        fairness_offset += 200

    items: list[dict[str, Any]] = []
    for case_item in fairness_case_items:
        panel = (
            case_item.get("panelDisagreement")
            if isinstance(case_item.get("panelDisagreement"), dict)
            else {}
        )
        runtime_profiles = (
            panel.get("runtimeProfiles")
            if isinstance(panel.get("runtimeProfiles"), dict)
            else {}
        )
        for judge in panel_judge_ids:
            runtime_profile = (
                runtime_profiles.get(judge)
                if isinstance(runtime_profiles.get(judge), dict)
                else {}
            )
            item = build_panel_runtime_profile_item(
                case_item=case_item,
                judge_id=judge,
                runtime_profile=runtime_profile,
            )
            if normalized_judge_id is not None and item.get("judgeId") != normalized_judge_id:
                continue
            if (
                normalized_profile_source is not None
                and str(item.get("profileSource") or "").strip().lower()
                != normalized_profile_source
            ):
                continue
            if (
                normalized_profile_id is not None
                and str(item.get("profileId") or "").strip() != normalized_profile_id
            ):
                continue
            if (
                normalized_model_strategy is not None
                and str(item.get("modelStrategy") or "").strip() != normalized_model_strategy
            ):
                continue
            if (
                normalized_strategy_slot is not None
                and str(item.get("strategySlot") or "").strip() != normalized_strategy_slot
            ):
                continue
            if (
                normalized_domain_slot is not None
                and str(item.get("domainSlot") or "").strip() != normalized_domain_slot
            ):
                continue
            items.append(item)

    items.sort(
        key=lambda row: build_panel_runtime_profile_sort_key(
            item=row,
            sort_by=normalized_sort_by,
        ),
        reverse=(normalized_sort_order == "desc"),
    )
    total_count = len(items)
    aggregations = build_panel_runtime_profile_aggregations(items)
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
            "hasOpenReview": has_open_review,
            "gateConclusion": normalized_gate_conclusion,
            "challengeState": normalized_challenge_state,
            "reviewRequired": review_required,
            "panelHighDisagreement": panel_high_disagreement,
            "judgeId": normalized_judge_id,
            "profileSource": normalized_profile_source,
            "profileId": normalized_profile_id,
            "modelStrategy": normalized_model_strategy,
            "strategySlot": normalized_strategy_slot,
            "domainSlot": normalized_domain_slot,
            "sortBy": normalized_sort_by,
            "sortOrder": normalized_sort_order,
            "offset": offset,
            "limit": limit,
        },
    }
    validate_panel_runtime_profile_contract(payload)
    return payload


async def build_panel_runtime_profiles_route_payload(
    *,
    list_judge_case_fairness: Callable[..., Awaitable[dict[str, Any]]],
    build_panel_runtime_profile_item: Callable[..., dict[str, Any]],
    build_panel_runtime_profile_sort_key: Callable[..., Any],
    build_panel_runtime_profile_aggregations: Callable[[list[dict[str, Any]]], dict[str, Any]],
    validate_panel_runtime_profile_contract: Callable[[dict[str, Any]], None],
    panel_judge_ids: tuple[str, ...] | list[str],
    panel_runtime_profile_source_values: set[str] | frozenset[str],
    panel_runtime_profile_sort_fields: set[str] | frozenset[str],
    normalize_workflow_status: Callable[[str | None], str | None],
    normalize_panel_runtime_profile_source: Callable[[str | None], str | None],
    normalize_panel_runtime_profile_sort_by: Callable[[str | None], str],
    normalize_panel_runtime_profile_sort_order: Callable[[str | None], str],
    normalize_case_fairness_gate_conclusion: Callable[[str | None], str | None],
    normalize_case_fairness_challenge_state: Callable[[str | None], str | None],
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
) -> dict[str, Any]:
    normalized = normalize_panel_runtime_profile_query(
        status=status,
        dispatch_type=dispatch_type,
        winner=winner,
        policy_version=policy_version,
        gate_conclusion=gate_conclusion,
        challenge_state=challenge_state,
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
        panel_judge_ids=panel_judge_ids,
        panel_runtime_profile_source_values=panel_runtime_profile_source_values,
        panel_runtime_profile_sort_fields=panel_runtime_profile_sort_fields,
        normalize_workflow_status=normalize_workflow_status,
        normalize_panel_runtime_profile_source=normalize_panel_runtime_profile_source,
        normalize_panel_runtime_profile_sort_by=normalize_panel_runtime_profile_sort_by,
        normalize_panel_runtime_profile_sort_order=normalize_panel_runtime_profile_sort_order,
        normalize_case_fairness_gate_conclusion=normalize_case_fairness_gate_conclusion,
        normalize_case_fairness_challenge_state=normalize_case_fairness_challenge_state,
    )
    return await build_panel_runtime_profiles_payload(
        list_judge_case_fairness=list_judge_case_fairness,
        build_panel_runtime_profile_item=build_panel_runtime_profile_item,
        build_panel_runtime_profile_sort_key=build_panel_runtime_profile_sort_key,
        build_panel_runtime_profile_aggregations=build_panel_runtime_profile_aggregations,
        validate_panel_runtime_profile_contract=validate_panel_runtime_profile_contract,
        panel_judge_ids=panel_judge_ids,
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
        normalized_judge_id=normalized["judgeId"],
        normalized_profile_source=normalized["profileSource"],
        normalized_profile_id=normalized["profileId"],
        normalized_model_strategy=normalized["modelStrategy"],
        normalized_strategy_slot=normalized["strategySlot"],
        normalized_domain_slot=normalized["domainSlot"],
        normalized_sort_by=str(normalized["sortBy"]),
        normalized_sort_order=str(normalized["sortOrder"]),
        normalized_status=normalized["status"],
        normalized_dispatch_type=normalized["dispatchType"],
        normalized_winner=normalized["winner"],
        normalized_policy_version=normalized["policyVersion"],
        normalized_gate_conclusion=normalized["gateConclusion"],
        normalized_challenge_state=normalized["challengeState"],
        offset=int(normalized["offset"]),
        limit=int(normalized["limit"]),
    )


async def build_panel_runtime_readiness_payload(
    *,
    list_panel_runtime_profiles: Callable[..., Awaitable[dict[str, Any]]],
    build_panel_runtime_readiness_summary: Callable[..., dict[str, Any]],
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
    normalized_status: str | None,
    normalized_dispatch_type: str | None,
    normalized_winner: str | None,
    normalized_policy_version: str | None,
    normalized_gate_conclusion: str | None,
    normalized_challenge_state: str | None,
    normalized_judge_id: str | None,
    normalized_profile_source: str | None,
    normalized_profile_id: str | None,
    normalized_model_strategy: str | None,
    normalized_strategy_slot: str | None,
    normalized_domain_slot: str | None,
    normalized_scan_limit: int,
    normalized_group_limit: int,
    normalized_attention_limit: int,
) -> dict[str, Any]:
    collected_items: list[dict[str, Any]] = []
    offset = 0
    total_count: int | None = None
    while len(collected_items) < normalized_scan_limit:
        batch_limit = min(200, normalized_scan_limit - len(collected_items))
        page = await list_panel_runtime_profiles(
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
            sort_by="updated_at",
            sort_order="desc",
            offset=offset,
            limit=batch_limit,
        )
        if total_count is None:
            total_count = int(page.get("count") or 0)
        page_items = page.get("items") if isinstance(page.get("items"), list) else []
        if not page_items:
            break
        collected_items.extend(page_items)
        if len(page_items) < batch_limit:
            break
        offset += batch_limit

    readiness = build_panel_runtime_readiness_summary(
        items=collected_items,
        group_limit=normalized_group_limit,
        attention_limit=normalized_attention_limit,
    )
    overview = readiness.get("overview") if isinstance(readiness.get("overview"), dict) else {}
    total_matched = int(total_count or 0)
    scanned_records = len(collected_items)
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "overview": {
            "totalMatched": total_matched,
            "scannedRecords": scanned_records,
            "scanTruncated": scanned_records < total_matched,
            "totalGroups": int(overview.get("totalGroups") or 0),
            "attentionGroupCount": int(overview.get("attentionGroupCount") or 0),
            "readinessCounts": (
                overview.get("readinessCounts")
                if isinstance(overview.get("readinessCounts"), dict)
                else {"ready": 0, "watch": 0, "attention": 0}
            ),
            "shadow": (
                overview.get("shadow")
                if isinstance(overview.get("shadow"), dict)
                else {
                    "enabledGroupCount": 0,
                    "blockedGroupCount": 0,
                    "watchGroupCount": 0,
                    "driftSignalGroupCount": 0,
                    "candidateModelGroupCount": 0,
                    "releaseGateSignalCounts": {
                        "ready": 0,
                        "watch": 0,
                        "blocked": 0,
                    },
                    "switchBlockerCounts": {
                        blocker: 0 for blocker in PANEL_RUNTIME_READINESS_SWITCH_BLOCKERS
                    },
                    "avgDecisionAgreement": 0.0,
                    "avgCostEstimate": 0.0,
                    "avgLatencyEstimate": 0.0,
                    "officialWinnerMutationAllowed": False,
                    "officialWinnerSemanticsChanged": False,
                    "autoSwitchAllowed": False,
                }
            ),
        },
        "groups": (
            readiness.get("groups")
            if isinstance(readiness.get("groups"), list)
            else []
        ),
        "attentionGroups": (
            readiness.get("attentionGroups")
            if isinstance(readiness.get("attentionGroups"), list)
            else []
        ),
        "notes": [
            (
                "simulations are advisory-only readiness suggestions and never "
                "change official winner semantics or auto-switch active policy."
            ),
        ],
        "filters": {
            "status": normalized_status,
            "dispatchType": normalized_dispatch_type,
            "winner": normalized_winner,
            "policyVersion": normalized_policy_version,
            "hasOpenReview": has_open_review,
            "gateConclusion": normalized_gate_conclusion,
            "challengeState": normalized_challenge_state,
            "reviewRequired": review_required,
            "panelHighDisagreement": panel_high_disagreement,
            "judgeId": normalized_judge_id,
            "profileSource": normalized_profile_source,
            "profileId": normalized_profile_id,
            "modelStrategy": normalized_model_strategy,
            "strategySlot": normalized_strategy_slot,
            "domainSlot": normalized_domain_slot,
            "profileScanLimit": normalized_scan_limit,
            "groupLimit": normalized_group_limit,
            "attentionLimit": normalized_attention_limit,
        },
    }


async def build_panel_runtime_readiness_route_payload(
    *,
    list_panel_runtime_profiles: Callable[..., Awaitable[dict[str, Any]]],
    build_panel_runtime_readiness_summary: Callable[..., dict[str, Any]],
    panel_judge_ids: tuple[str, ...] | list[str],
    panel_runtime_profile_source_values: set[str] | frozenset[str],
    normalize_workflow_status: Callable[[str | None], str | None],
    normalize_panel_runtime_profile_source: Callable[[str | None], str | None],
    normalize_case_fairness_gate_conclusion: Callable[[str | None], str | None],
    normalize_case_fairness_challenge_state: Callable[[str | None], str | None],
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
) -> dict[str, Any]:
    normalized = normalize_panel_runtime_profile_query(
        status=status,
        dispatch_type=dispatch_type,
        winner=winner,
        policy_version=policy_version,
        gate_conclusion=gate_conclusion,
        challenge_state=challenge_state,
        judge_id=judge_id,
        profile_source=profile_source,
        profile_id=profile_id,
        model_strategy=model_strategy,
        strategy_slot=strategy_slot,
        domain_slot=domain_slot,
        sort_by="updated_at",
        sort_order="desc",
        offset=0,
        limit=50,
        panel_judge_ids=panel_judge_ids,
        panel_runtime_profile_source_values=panel_runtime_profile_source_values,
        panel_runtime_profile_sort_fields={"updated_at"},
        normalize_workflow_status=normalize_workflow_status,
        normalize_panel_runtime_profile_source=normalize_panel_runtime_profile_source,
        normalize_panel_runtime_profile_sort_by=lambda _: "updated_at",
        normalize_panel_runtime_profile_sort_order=lambda _: "desc",
        normalize_case_fairness_gate_conclusion=normalize_case_fairness_gate_conclusion,
        normalize_case_fairness_challenge_state=normalize_case_fairness_challenge_state,
    )
    normalized_scan_limit = max(50, min(int(profile_scan_limit), 5000))
    normalized_group_limit = max(1, min(int(group_limit), 200))
    normalized_attention_limit = max(1, min(int(attention_limit), 100))
    return await build_panel_runtime_readiness_payload(
        list_panel_runtime_profiles=list_panel_runtime_profiles,
        build_panel_runtime_readiness_summary=build_panel_runtime_readiness_summary,
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
        normalized_status=normalized["status"],
        normalized_dispatch_type=normalized["dispatchType"],
        normalized_winner=normalized["winner"],
        normalized_policy_version=normalized["policyVersion"],
        normalized_gate_conclusion=normalized["gateConclusion"],
        normalized_challenge_state=normalized["challengeState"],
        normalized_judge_id=normalized["judgeId"],
        normalized_profile_source=normalized["profileSource"],
        normalized_profile_id=normalized["profileId"],
        normalized_model_strategy=normalized["modelStrategy"],
        normalized_strategy_slot=normalized["strategySlot"],
        normalized_domain_slot=normalized["domainSlot"],
        normalized_scan_limit=normalized_scan_limit,
        normalized_group_limit=normalized_group_limit,
        normalized_attention_limit=normalized_attention_limit,
    )
