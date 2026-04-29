from __future__ import annotations

from typing import Any


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _to_int(value: Any, *, default: int = 0) -> int:
    try:
        if isinstance(value, bool):
            return default
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        if value is None or isinstance(value, bool):
            return float(default)
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return float(default)


def _token(value: Any) -> str | None:
    token = str(value or "").strip()
    return token or None


def _lower_token(value: Any) -> str | None:
    token = _token(value)
    return token.lower() if token is not None else None


def _bool_or_none(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _tokens(value: Any, *, limit: int = 20) -> list[str]:
    if not isinstance(value, list):
        return []
    seen: set[str] = set()
    items: list[str] = []
    for raw in value:
        token = _token(raw)
        if token is None or token in seen:
            continue
        seen.add(token)
        items.append(token)
        if len(items) >= limit:
            break
    return items


def build_runtime_readiness_release_gate_section(
    *,
    release_gate: dict[str, Any],
    trust_monitoring: dict[str, Any],
    adaptive_summary: dict[str, Any],
) -> dict[str, Any]:
    registry_readiness = _dict_or_empty(
        trust_monitoring.get("registryReleaseReadiness")
    )
    return {
        "passed": _bool_or_none(release_gate.get("passed")),
        "code": (
            _token(release_gate.get("code"))
            or _token(adaptive_summary.get("calibrationGateCode"))
        ),
        "registryStatus": _lower_token(registry_readiness.get("status")),
        "blockedPolicyCount": _to_int(registry_readiness.get("blockedPolicyCount")),
        "missingKernelBindingCount": _to_int(
            registry_readiness.get("missingKernelBindingCount")
        ),
        "highRiskItemCount": _to_int(registry_readiness.get("highRiskItemCount")),
        "overrideAppliedPolicyCount": _to_int(
            registry_readiness.get("overrideAppliedPolicyCount")
        ),
        "releaseReadinessEvidenceVersion": _token(
            registry_readiness.get("releaseReadinessEvidenceVersion")
        ),
        "releaseReadinessEvidenceCount": _to_int(
            registry_readiness.get("releaseReadinessEvidenceCount")
        ),
        "releaseReadinessArtifactCount": _to_int(
            registry_readiness.get("releaseReadinessArtifactCount")
        ),
        "releaseReadinessManifestHashCount": _to_int(
            registry_readiness.get("releaseReadinessManifestHashCount")
        ),
        "reasonCodes": _tokens(registry_readiness.get("reasonCodes")),
    }


def build_runtime_readiness_fairness_section(
    *,
    fairness_calibration_advisor: dict[str, Any],
    trust_monitoring: dict[str, Any],
    adaptive_summary: dict[str, Any],
) -> dict[str, Any]:
    panel_shadow_drift = _dict_or_empty(trust_monitoring.get("panelShadowDrift"))
    real_env = _dict_or_empty(trust_monitoring.get("realEnvEvidenceStatus"))
    advisor_overview = _dict_or_empty(fairness_calibration_advisor.get("overview"))
    decision_log = _dict_or_empty(fairness_calibration_advisor.get("decisionLog"))
    decision_summary = _dict_or_empty(decision_log.get("summary"))
    release_gate_reference = _dict_or_empty(
        decision_log.get("releaseGateReference")
    )
    return {
        "gatePassed": _bool_or_none(adaptive_summary.get("calibrationGatePassed")),
        "gateCode": _token(adaptive_summary.get("calibrationGateCode")),
        "highRiskCount": _to_int(adaptive_summary.get("calibrationHighRiskCount")),
        "recommendedActionCount": _to_int(
            adaptive_summary.get("recommendedActionCount")
        ),
        "panelShadowStatus": _lower_token(panel_shadow_drift.get("status")),
        "shadowRunCount": _to_int(panel_shadow_drift.get("shadowRunCount")),
        "shadowThresholdViolationCount": _to_int(
            panel_shadow_drift.get("shadowThresholdViolationCount")
        ),
        "driftBreachCount": _to_int(panel_shadow_drift.get("driftBreachCount")),
        "realSampleManifestStatus": _lower_token(
            real_env.get("realSampleManifestStatus")
        ),
        "decisionCount": _to_int(
            decision_summary.get("totalCount")
            or advisor_overview.get("decisionCount")
        ),
        "acceptedForReviewDecisionCount": _to_int(
            decision_summary.get("acceptedForReviewCount")
            or advisor_overview.get("acceptedForReviewDecisionCount")
        ),
        "productionReadyDecisionCount": _to_int(
            decision_summary.get("productionReadyDecisionCount")
            or advisor_overview.get("productionReadyDecisionCount")
        ),
        "decisionLogBlocksProductionReadyCount": _to_int(
            release_gate_reference.get("blockingDecisionCount")
            or advisor_overview.get("decisionLogBlocksProductionReadyCount")
        ),
    }


def build_runtime_readiness_panel_runtime_section(
    *,
    panel_runtime_readiness: dict[str, Any],
    trust_monitoring: dict[str, Any],
    adaptive_summary: dict[str, Any],
) -> dict[str, Any]:
    panel_shadow_drift = _dict_or_empty(trust_monitoring.get("panelShadowDrift"))
    readiness_overview = _dict_or_empty(panel_runtime_readiness.get("overview"))
    readiness_shadow = _dict_or_empty(readiness_overview.get("shadow"))
    switch_blocker_counts = _dict_or_empty(readiness_shadow.get("switchBlockerCounts"))
    release_gate_signal_counts = _dict_or_empty(
        readiness_shadow.get("releaseGateSignalCounts")
    )
    return {
        "status": _lower_token(panel_shadow_drift.get("status")),
        "readyGroupCount": _to_int(adaptive_summary.get("panelReadyGroupCount")),
        "watchGroupCount": _to_int(adaptive_summary.get("panelWatchGroupCount")),
        "attentionGroupCount": _to_int(
            adaptive_summary.get("panelAttentionGroupCount")
        ),
        "scannedRecordCount": _to_int(adaptive_summary.get("panelScannedRecordCount")),
        "shadowGateApplied": bool(panel_shadow_drift.get("shadowGateApplied")),
        "shadowGatePassed": _bool_or_none(panel_shadow_drift.get("shadowGatePassed")),
        "latestShadowRunStatus": _lower_token(
            panel_shadow_drift.get("latestShadowRunStatus")
        ),
        "latestShadowRunThresholdDecision": _lower_token(
            panel_shadow_drift.get("latestShadowRunThresholdDecision")
        ),
        "latestShadowRunEnvironmentMode": _lower_token(
            panel_shadow_drift.get("latestShadowRunEnvironmentMode")
        ),
        "candidateModelGroupCount": _to_int(
            readiness_shadow.get("candidateModelGroupCount")
        ),
        "switchBlockerCount": sum(
            _to_int(value) for value in switch_blocker_counts.values()
        ),
        "releaseBlockedGroupCount": _to_int(release_gate_signal_counts.get("blocked")),
        "avgShadowDecisionAgreement": _safe_float(
            readiness_shadow.get("avgDecisionAgreement")
        ),
        "avgShadowCostEstimate": _safe_float(readiness_shadow.get("avgCostEstimate")),
        "avgShadowLatencyEstimate": _safe_float(
            readiness_shadow.get("avgLatencyEstimate")
        ),
        "autoSwitchAllowed": False,
        "officialWinnerSemanticsChanged": False,
    }


def build_runtime_readiness_evidence_refs(
    *, trust_monitoring: dict[str, Any]
) -> list[dict[str, Any]]:
    registry_readiness = _dict_or_empty(
        trust_monitoring.get("registryReleaseReadiness")
    )
    real_env = _dict_or_empty(trust_monitoring.get("realEnvEvidenceStatus"))
    public_verification = _dict_or_empty(
        trust_monitoring.get("publicVerificationReadiness")
    )
    artifact_store = _dict_or_empty(trust_monitoring.get("artifactStoreReadiness"))
    return [
        {
            "kind": "release_readiness",
            "status": _lower_token(registry_readiness.get("status")),
            "evidenceVersion": _token(
                registry_readiness.get("releaseReadinessEvidenceVersion")
            ),
            "evidenceCount": _to_int(
                registry_readiness.get("releaseReadinessEvidenceCount")
            ),
            "artifactCount": _to_int(
                registry_readiness.get("releaseReadinessArtifactCount")
            ),
            "manifestHashCount": _to_int(
                registry_readiness.get("releaseReadinessManifestHashCount")
            ),
            "p41ControlPlaneEvidenceCount": _to_int(
                registry_readiness.get("p41ControlPlaneEvidenceCount")
            ),
            "p41ControlPlaneStatusCounts": _dict_or_empty(
                registry_readiness.get("p41ControlPlaneStatusCounts")
            ),
        },
        {
            "kind": "real_env_evidence",
            "status": _lower_token(real_env.get("status")),
            "evidenceAvailable": bool(real_env.get("realEnvEvidenceAvailable")),
            "realSampleManifestStatus": _lower_token(
                real_env.get("realSampleManifestStatus")
            ),
        },
        {
            "kind": "public_verification",
            "status": _lower_token(public_verification.get("status")),
            "sampledCaseCount": _to_int(public_verification.get("sampledCaseCount")),
            "verifiedCount": _to_int(public_verification.get("verifiedCount")),
            "failedCount": _to_int(public_verification.get("failedCount")),
        },
        {
            "kind": "artifact_store",
            "status": _lower_token(artifact_store.get("status")),
            "sampledCaseCount": _to_int(artifact_store.get("sampledCaseCount")),
            "readyCount": _to_int(artifact_store.get("readyCount")),
            "missingCount": _to_int(artifact_store.get("missingCount")),
            "manifestHashPresentCount": _to_int(
                artifact_store.get("manifestHashPresentCount")
            ),
        },
    ]
