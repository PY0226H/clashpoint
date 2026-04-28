from __future__ import annotations

from typing import Any

RUNTIME_READINESS_PUBLIC_CONTRACT_VERSION = "ai-judge-runtime-readiness-v1"

RUNTIME_READINESS_PUBLIC_ALLOWED_STATUSES: tuple[str, ...] = (
    "ready",
    "watch",
    "blocked",
    "env_blocked",
    "local_reference_only",
    "not_configured",
)

RUNTIME_READINESS_PUBLIC_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "version",
    "generatedAt",
    "status",
    "statusReason",
    "summary",
    "releaseGate",
    "fairnessCalibration",
    "panelRuntime",
    "trustAndChallenge",
    "realEnv",
    "recommendedActions",
    "evidenceRefs",
    "visibilityContract",
    "cacheProfile",
)

RUNTIME_READINESS_PUBLIC_FORBIDDEN_KEYS: tuple[str, ...] = (
    "apiKey",
    "secret",
    "provider",
    "providerConfig",
    "rawPrompt",
    "rawTrace",
    "prompt",
    "trace",
    "traceId",
    "internalAuditPayload",
    "privateAudit",
    "auditPayload",
    "artifactRef",
    "artifactRefs",
    "objectKey",
    "bucket",
    "signedUrl",
    "endpoint",
)


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(row) for row in value if isinstance(row, dict)]


def _to_int(value: Any, *, default: int = 0) -> int:
    try:
        if isinstance(value, bool):
            return default
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


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


def _blocker_count(blocker_counts: dict[str, Any], *buckets: str) -> int:
    return sum(_to_int(blocker_counts.get(bucket)) for bucket in buckets)


def _derive_status(
    *,
    release_gate: dict[str, Any],
    trust_monitoring: dict[str, Any],
    adaptive_summary: dict[str, Any],
) -> tuple[str, str]:
    real_env = _dict_or_empty(trust_monitoring.get("realEnvEvidenceStatus"))
    blocker_counts = _dict_or_empty(trust_monitoring.get("blockerCounts"))
    registry_readiness = _dict_or_empty(
        trust_monitoring.get("registryReleaseReadiness")
    )
    monitoring_status = _lower_token(trust_monitoring.get("overallStatus"))
    real_env_status = _lower_token(real_env.get("status"))
    evidence_available = bool(real_env.get("realEnvEvidenceAvailable"))
    release_gate_passed = _bool_or_none(release_gate.get("passed"))

    if real_env_status in {"env_blocked", "not_sampled"} and not evidence_available:
        return "local_reference_only", "real_env_evidence_missing"
    if real_env_status == "env_blocked":
        return "env_blocked", "real_env_evidence_env_blocked"
    if (
        release_gate_passed is False
        or monitoring_status == "blocked"
        or _blocker_count(blocker_counts, "production", "release") > 0
    ):
        return "blocked", "release_or_production_blocked"
    if _lower_token(registry_readiness.get("status")) == "blocked":
        return "blocked", "registry_release_blocked"
    if (
        monitoring_status == "watch"
        or _blocker_count(blocker_counts, "review", "evidence") > 0
        or _to_int(adaptive_summary.get("calibrationHighRiskCount")) > 0
        or _to_int(adaptive_summary.get("recommendedActionCount")) > 0
        or _to_int(adaptive_summary.get("panelAttentionGroupCount")) > 0
    ):
        return "watch", "ops_attention_required"
    if not trust_monitoring and not release_gate:
        return "not_configured", "runtime_readiness_source_missing"
    return "ready", "runtime_readiness_ready"


def _build_release_gate_section(
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


def _build_fairness_section(
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


def _build_panel_runtime_section(
    *,
    trust_monitoring: dict[str, Any],
    adaptive_summary: dict[str, Any],
) -> dict[str, Any]:
    panel_shadow_drift = _dict_or_empty(trust_monitoring.get("panelShadowDrift"))
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
    }


def _build_trust_and_challenge_section(
    *,
    trust_monitoring: dict[str, Any],
    adaptive_summary: dict[str, Any],
) -> dict[str, Any]:
    artifact_readiness = _dict_or_empty(
        trust_monitoring.get("artifactStoreReadiness")
    )
    verification_readiness = _dict_or_empty(
        trust_monitoring.get("publicVerificationReadiness")
    )
    challenge_lag = _dict_or_empty(trust_monitoring.get("challengeReviewLag"))
    blocker_counts = _dict_or_empty(trust_monitoring.get("blockerCounts"))
    return {
        "overallStatus": _lower_token(trust_monitoring.get("overallStatus")),
        "artifactStoreStatus": _lower_token(artifact_readiness.get("status")),
        "publicVerificationStatus": _lower_token(
            verification_readiness.get("status")
        ),
        "challengeReviewLagStatus": _lower_token(challenge_lag.get("status")),
        "sampledCaseCount": _to_int(trust_monitoring.get("sampledCaseCount")),
        "publicVerifiedCount": _to_int(verification_readiness.get("verifiedCount")),
        "publicVerificationFailedCount": _to_int(
            verification_readiness.get("failedCount")
        ),
        "openChallengeCount": _to_int(challenge_lag.get("openChallengeCount")),
        "urgentChallengeCount": _to_int(challenge_lag.get("urgentCount")),
        "highPriorityChallengeCount": _to_int(
            challenge_lag.get("highPriorityCount")
        ),
        "trustChallengeQueueCount": _to_int(
            adaptive_summary.get("trustChallengeQueueCount")
        ),
        "productionBlockerCount": _blocker_count(blocker_counts, "production"),
        "reviewBlockerCount": _blocker_count(blocker_counts, "review"),
    }


def _build_real_env_section(*, trust_monitoring: dict[str, Any]) -> dict[str, Any]:
    real_env = _dict_or_empty(trust_monitoring.get("realEnvEvidenceStatus"))
    citation = _dict_or_empty(trust_monitoring.get("citationVerifierEvidence"))
    registry_readiness = _dict_or_empty(
        trust_monitoring.get("registryReleaseReadiness")
    )
    reason_codes = sorted(
        set(_tokens(registry_readiness.get("reasonCodes")))
        | set(_tokens(citation.get("reasonCodes")))
    )
    return {
        "status": _lower_token(real_env.get("status")),
        "evidenceAvailable": bool(real_env.get("realEnvEvidenceAvailable")),
        "latestRunStatus": _lower_token(real_env.get("latestRunStatus")),
        "latestRunThresholdDecision": _lower_token(
            real_env.get("latestRunThresholdDecision")
        ),
        "latestRunEnvironmentMode": _lower_token(
            real_env.get("latestRunEnvironmentMode")
        ),
        "latestRunNeedsRemediation": _bool_or_none(
            real_env.get("latestRunNeedsRemediation")
        ),
        "realSampleManifestStatus": _lower_token(
            real_env.get("realSampleManifestStatus")
        ),
        "citationVerifierStatus": _lower_token(citation.get("status")),
        "citationVerifierMissingCitationCount": _to_int(
            citation.get("missingCitationCount")
        ),
        "citationVerifierWeakCitationCount": _to_int(citation.get("weakCitationCount")),
        "citationVerifierForbiddenSourceCount": _to_int(
            citation.get("forbiddenSourceCount")
        ),
        "envBlockedComponents": _tokens(
            registry_readiness.get("envBlockedComponents")
        ),
        "reasonCodes": reason_codes[:20],
    }


def _build_summary_section(
    *,
    adaptive_summary: dict[str, Any],
    trust_monitoring: dict[str, Any],
) -> dict[str, Any]:
    blocker_counts = _dict_or_empty(trust_monitoring.get("blockerCounts"))
    return {
        "calibrationGatePassed": _bool_or_none(
            adaptive_summary.get("calibrationGatePassed")
        ),
        "calibrationHighRiskCount": _to_int(
            adaptive_summary.get("calibrationHighRiskCount")
        ),
        "recommendedActionCount": _to_int(
            adaptive_summary.get("recommendedActionCount")
        ),
        "registryPromptToolRiskCount": _to_int(
            adaptive_summary.get("registryPromptToolRiskCount")
        ),
        "registryPromptToolHighRiskCount": _to_int(
            adaptive_summary.get("registryPromptToolHighRiskCount")
        ),
        "panelReadyGroupCount": _to_int(adaptive_summary.get("panelReadyGroupCount")),
        "panelWatchGroupCount": _to_int(adaptive_summary.get("panelWatchGroupCount")),
        "panelAttentionGroupCount": _to_int(
            adaptive_summary.get("panelAttentionGroupCount")
        ),
        "reviewQueueCount": _to_int(adaptive_summary.get("reviewQueueCount")),
        "reviewHighRiskCount": _to_int(adaptive_summary.get("reviewHighRiskCount")),
        "evidenceClaimQueueCount": _to_int(
            adaptive_summary.get("evidenceClaimQueueCount")
        ),
        "trustChallengeQueueCount": _to_int(
            adaptive_summary.get("trustChallengeQueueCount")
        ),
        "productionBlockerCount": _blocker_count(blocker_counts, "production"),
        "releaseBlockerCount": _blocker_count(blocker_counts, "release"),
        "evidenceBlockerCount": _blocker_count(blocker_counts, "evidence"),
    }


def _public_action(row: dict[str, Any], *, index: int) -> dict[str, Any]:
    return {
        "id": (
            _token(row.get("id"))
            or _token(row.get("actionId"))
            or f"action:{index + 1}"
        ),
        "source": _token(row.get("source")) or "fairnessCalibrationAdvisor",
        "severity": _lower_token(row.get("severity")) or "watch",
        "code": (
            _token(row.get("code"))
            or _token(row.get("reasonCode"))
            or _token(row.get("decisionCode"))
            or "ops_review_required"
        ),
        "title": (
            _token(row.get("title"))
            or _token(row.get("label"))
            or _token(row.get("action"))
            or "Review runtime readiness advisory"
        ),
        "owner": _token(row.get("owner")) or _token(row.get("ownerRole")),
        "status": _lower_token(row.get("status")),
    }


def _build_recommended_actions(
    *,
    fairness_calibration_advisor: dict[str, Any],
    trust_monitoring: dict[str, Any],
) -> list[dict[str, Any]]:
    actions = [
        _public_action(row, index=index)
        for index, row in enumerate(
            _list_of_dicts(fairness_calibration_advisor.get("recommendedActions"))
        )
    ]
    if actions:
        return actions[:10]

    blockers = _list_of_dicts(trust_monitoring.get("blockers"))
    return [
        {
            "id": f"blocker:{_token(row.get('code')) or index + 1}",
            "source": "opsTrustMonitoring",
            "severity": _lower_token(row.get("severity")) or "watch",
            "code": _token(row.get("code")) or "ops_blocker",
            "title": "Resolve runtime readiness blocker",
            "owner": _token(row.get("bucket")),
            "status": "open",
        }
        for index, row in enumerate(blockers[:10])
    ]


def _build_evidence_refs(*, trust_monitoring: dict[str, Any]) -> list[dict[str, Any]]:
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


def _build_visibility_contract() -> dict[str, Any]:
    return {
        "allowedSections": [
            "summary",
            "releaseGate",
            "fairnessCalibration",
            "panelRuntime",
            "trustAndChallenge",
            "realEnv",
            "recommendedActions",
            "evidenceRefs",
        ],
        "forbiddenKeys": list(RUNTIME_READINESS_PUBLIC_FORBIDDEN_KEYS),
        "rawPromptVisible": False,
        "rawTraceVisible": False,
        "internalAuditPayloadVisible": False,
        "providerConfigVisible": False,
        "artifactRefsVisible": False,
        "officialVerdictSemanticsChanged": False,
    }


def _build_cache_profile(*, filters: dict[str, Any]) -> dict[str, Any]:
    dispatch_type = _token(filters.get("dispatchType")) or "final"
    policy_version = _token(filters.get("policyVersion")) or "active"
    window_days = _to_int(filters.get("windowDays"), default=7)
    return {
        "cacheKey": (
            "ai_judge_runtime_readiness:"
            f"{dispatch_type}:{policy_version}:{window_days}"
        ),
        "ttlSeconds": 30,
        "sourceContractVersion": "ops_read_model_pack_v5",
    }


def build_runtime_readiness_public_payload(
    pack_payload: dict[str, Any],
) -> dict[str, Any]:
    fairness_calibration_advisor = _dict_or_empty(
        pack_payload.get("fairnessCalibrationAdvisor")
    )
    release_gate = _dict_or_empty(fairness_calibration_advisor.get("releaseGate"))
    adaptive_summary = _dict_or_empty(pack_payload.get("adaptiveSummary"))
    trust_monitoring = _dict_or_empty(pack_payload.get("trustMonitoring"))
    filters = _dict_or_empty(pack_payload.get("filters"))

    status, status_reason = _derive_status(
        release_gate=release_gate,
        trust_monitoring=trust_monitoring,
        adaptive_summary=adaptive_summary,
    )
    payload = {
        "version": RUNTIME_READINESS_PUBLIC_CONTRACT_VERSION,
        "generatedAt": _token(pack_payload.get("generatedAt")),
        "status": status,
        "statusReason": status_reason,
        "summary": _build_summary_section(
            adaptive_summary=adaptive_summary,
            trust_monitoring=trust_monitoring,
        ),
        "releaseGate": _build_release_gate_section(
            release_gate=release_gate,
            trust_monitoring=trust_monitoring,
            adaptive_summary=adaptive_summary,
        ),
        "fairnessCalibration": _build_fairness_section(
            fairness_calibration_advisor=fairness_calibration_advisor,
            trust_monitoring=trust_monitoring,
            adaptive_summary=adaptive_summary,
        ),
        "panelRuntime": _build_panel_runtime_section(
            trust_monitoring=trust_monitoring,
            adaptive_summary=adaptive_summary,
        ),
        "trustAndChallenge": _build_trust_and_challenge_section(
            trust_monitoring=trust_monitoring,
            adaptive_summary=adaptive_summary,
        ),
        "realEnv": _build_real_env_section(trust_monitoring=trust_monitoring),
        "recommendedActions": _build_recommended_actions(
            fairness_calibration_advisor=fairness_calibration_advisor,
            trust_monitoring=trust_monitoring,
        ),
        "evidenceRefs": _build_evidence_refs(trust_monitoring=trust_monitoring),
        "visibilityContract": _build_visibility_contract(),
        "cacheProfile": _build_cache_profile(filters=filters),
    }
    validate_runtime_readiness_public_contract(payload)
    return payload


def _validate_no_forbidden_keys(value: Any, *, path: str = "payload") -> None:
    forbidden = {key.lower() for key in RUNTIME_READINESS_PUBLIC_FORBIDDEN_KEYS}
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in forbidden:
                raise ValueError(f"runtime_readiness_forbidden_key:{path}.{key}")
            _validate_no_forbidden_keys(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_no_forbidden_keys(child, path=f"{path}[{index}]")


def validate_runtime_readiness_public_contract(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("runtime_readiness_payload_not_dict")
    if set(payload.keys()) != set(RUNTIME_READINESS_PUBLIC_TOP_LEVEL_KEYS):
        raise ValueError("runtime_readiness_top_level_keys_mismatch")
    if payload.get("version") != RUNTIME_READINESS_PUBLIC_CONTRACT_VERSION:
        raise ValueError("runtime_readiness_version_invalid")
    if payload.get("status") not in RUNTIME_READINESS_PUBLIC_ALLOWED_STATUSES:
        raise ValueError("runtime_readiness_status_invalid")

    for field in (
        "summary",
        "releaseGate",
        "fairnessCalibration",
        "panelRuntime",
        "trustAndChallenge",
        "realEnv",
        "visibilityContract",
        "cacheProfile",
    ):
        if not isinstance(payload.get(field), dict):
            raise ValueError(f"runtime_readiness_{field}_not_dict")
    for field in ("recommendedActions", "evidenceRefs"):
        if not isinstance(payload.get(field), list):
            raise ValueError(f"runtime_readiness_{field}_not_list")

    visibility = _dict_or_empty(payload.get("visibilityContract"))
    for flag in (
        "rawPromptVisible",
        "rawTraceVisible",
        "internalAuditPayloadVisible",
        "providerConfigVisible",
        "artifactRefsVisible",
        "officialVerdictSemanticsChanged",
    ):
        if visibility.get(flag) is not False:
            raise ValueError(f"runtime_readiness_visibility_{flag}_not_false")

    _validate_no_forbidden_keys(payload)
