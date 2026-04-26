from __future__ import annotations

from typing import Any

from app.applications.fairness_panel_evidence import (
    build_fairness_panel_evidence_normalization,
)

OPS_TRUST_MONITORING_VERSION = "ops-trust-monitoring-v1"

OPS_TRUST_MONITORING_KEYS: tuple[str, ...] = (
    "monitoringVersion",
    "overallStatus",
    "sampledCaseCount",
    "artifactStoreReadiness",
    "publicVerificationReadiness",
    "challengeReviewLag",
    "registryReleaseReadiness",
    "citationVerifierEvidence",
    "panelShadowDrift",
    "realEnvEvidenceStatus",
    "blockerCounts",
    "blockers",
    "redactionContract",
)

OPS_TRUST_MONITORING_BLOCKER_BUCKETS: tuple[str, ...] = (
    "production",
    "review",
    "release",
    "evidence",
)


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


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(row) for row in value if isinstance(row, dict)]


def _count_dict(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    counts: dict[str, int] = {}
    for key, count in value.items():
        token = _lower_token(key) or "unknown"
        counts[token] = counts.get(token, 0) + _to_int(count)
    return dict(sorted(counts.items(), key=lambda kv: kv[0]))


def _release_readiness_evidence_from_row(row: dict[str, Any]) -> dict[str, Any] | None:
    for key in ("releaseReadinessEvidence", "evidence"):
        value = row.get(key)
        if isinstance(value, dict):
            return dict(value)
    release_gate = row.get("releaseGate")
    if isinstance(release_gate, dict) and isinstance(
        release_gate.get("releaseReadinessEvidence"),
        dict,
    ):
        return dict(release_gate["releaseReadinessEvidence"])
    return None


def _collect_release_readiness_evidence_items(
    *,
    registry_prompt_tool_governance: dict[str, Any],
    policy_gate_simulation: dict[str, Any],
) -> list[dict[str, Any]]:
    evidence_items: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str]] = set()

    def _append(value: Any) -> None:
        if not isinstance(value, dict):
            return
        policy_version = _token(value.get("policyVersion")) or ""
        evidence_version = _token(value.get("evidenceVersion")) or ""
        decision_code = _token(value.get("decisionCode")) or ""
        key = (policy_version, evidence_version, decision_code)
        if key == ("", "", ""):
            key = (f"index:{len(evidence_items)}", "", "")
        if key in seen_keys:
            return
        seen_keys.add(key)
        evidence_items.append(dict(value))

    for row in _list_of_dicts(policy_gate_simulation.get("items")):
        _append(_release_readiness_evidence_from_row(row))

    release_readiness = _dict_or_empty(
        registry_prompt_tool_governance.get("releaseReadiness")
    )
    for row in _list_of_dicts(release_readiness.get("items")):
        _append(_release_readiness_evidence_from_row(row))

    dependency_health = _dict_or_empty(
        registry_prompt_tool_governance.get("dependencyHealth")
    )
    for row in _list_of_dicts(dependency_health.get("items")):
        _append(_release_readiness_evidence_from_row(row))

    return evidence_items


def _summarize_release_readiness_evidence_items(
    evidence_items: list[dict[str, Any]],
) -> dict[str, Any]:
    evidence_version = next(
        (_token(item.get("evidenceVersion")) for item in evidence_items),
        None,
    )
    env_blocked_components = sorted(
        {
            str(component or "").strip()
            for item in evidence_items
            for component in (item.get("envBlockedComponents") or [])
            if str(component or "").strip()
        }
    )
    reason_codes = sorted(
        {
            str(code or "").strip()
            for item in evidence_items
            for code in (item.get("reasonCodes") or [])
            if str(code or "").strip()
        }
    )
    artifact_refs = sorted(
        {
            str(ref or "").strip()
            for item in evidence_items
            for ref in (item.get("artifactRefs") or [])
            if str(ref or "").strip()
        }
    )
    release_readiness_artifact_refs = sorted(
        {
            str(summary.get("artifactRef") or "").strip()
            for item in evidence_items
            for summary in [_dict_or_empty(item.get("releaseReadinessArtifactSummary"))]
            if str(summary.get("artifactRef") or "").strip()
        }
    )
    release_readiness_manifest_hashes = sorted(
        {
            str(summary.get("manifestHash") or "").strip()
            for item in evidence_items
            for summary in [_dict_or_empty(item.get("releaseReadinessArtifactSummary"))]
            if str(summary.get("manifestHash") or "").strip()
        }
    )
    public_verification_ready_count = 0
    real_env_evidence_status_counts: dict[str, int] = {}
    citation_verifier_status_counts: dict[str, int] = {}
    citation_verifier_reason_codes: set[str] = set()
    citation_verifier_missing_count = 0
    citation_verifier_weak_count = 0
    citation_verifier_forbidden_count = 0
    for item in evidence_items:
        public_verification = _dict_or_empty(item.get("publicVerificationReadiness"))
        if _lower_token(public_verification.get("status")) == "ready":
            public_verification_ready_count += 1
        real_env_status = _dict_or_empty(item.get("realEnvEvidenceStatus"))
        status = _lower_token(real_env_status.get("status")) or "unknown"
        real_env_evidence_status_counts[status] = (
            real_env_evidence_status_counts.get(status, 0) + 1
        )
        citation_verification = _dict_or_empty(item.get("citationVerification"))
        citation_status = _lower_token(citation_verification.get("status")) or "unknown"
        citation_verifier_status_counts[citation_status] = (
            citation_verifier_status_counts.get(citation_status, 0) + 1
        )
        citation_verifier_reason_codes.update(
            str(code or "").strip()
            for code in (citation_verification.get("reasonCodes") or [])
            if str(code or "").strip()
        )
        citation_verifier_missing_count += _to_int(
            citation_verification.get("missingCitationCount")
        )
        citation_verifier_weak_count += _to_int(
            citation_verification.get("weakCitationCount")
        )
        citation_verifier_forbidden_count += _to_int(
            citation_verification.get("forbiddenSourceCount")
        )
    return {
        "evidenceVersion": evidence_version,
        "evidenceCount": len(evidence_items),
        "envBlockedComponents": env_blocked_components,
        "reasonCodes": reason_codes,
        "artifactRefCount": len(artifact_refs),
        "releaseReadinessArtifactCount": len(release_readiness_artifact_refs),
        "releaseReadinessManifestHashCount": len(release_readiness_manifest_hashes),
        "publicVerificationReadyCount": public_verification_ready_count,
        "realEnvEvidenceStatusCounts": dict(
            sorted(real_env_evidence_status_counts.items(), key=lambda kv: kv[0])
        ),
        "citationVerifierStatusCounts": dict(
            sorted(citation_verifier_status_counts.items(), key=lambda kv: kv[0])
        ),
        "citationVerifierReasonCodes": sorted(citation_verifier_reason_codes),
        "citationVerifierMissingCitationCount": citation_verifier_missing_count,
        "citationVerifierWeakCitationCount": citation_verifier_weak_count,
        "citationVerifierForbiddenSourceCount": citation_verifier_forbidden_count,
    }


def _add_blocker(
    blockers: list[dict[str, Any]],
    *,
    bucket: str,
    code: str,
    count: int,
    severity: str = "blocker",
) -> None:
    normalized_count = _to_int(count)
    if normalized_count <= 0:
        return
    blockers.append(
        {
            "bucket": bucket,
            "code": code,
            "count": normalized_count,
            "severity": severity,
        }
    )


def _status_from_artifacts(
    *,
    sampled_case_count: int,
    ready_count: int,
    pending_count: int,
    missing_count: int,
) -> str:
    if sampled_case_count <= 0:
        return "not_sampled"
    if missing_count > 0:
        return "blocked"
    if pending_count > 0:
        return "pending"
    if ready_count >= sampled_case_count:
        return "ready"
    return "watch"


def _build_artifact_store_readiness(
    *,
    artifact_coverage: dict[str, Any],
    audit_anchor_status: dict[str, Any],
) -> dict[str, Any]:
    sampled_case_count = _to_int(artifact_coverage.get("sampledCaseCount"))
    ready_count = _to_int(artifact_coverage.get("readyCount"))
    pending_count = _to_int(artifact_coverage.get("pendingCount"))
    missing_count = _to_int(artifact_coverage.get("missingCount"))
    manifest_hash_present_count = _to_int(
        artifact_coverage.get("manifestHashPresentCount")
    )
    return {
        "status": _status_from_artifacts(
            sampled_case_count=sampled_case_count,
            ready_count=ready_count,
            pending_count=pending_count,
            missing_count=missing_count,
        ),
        "sampledCaseCount": sampled_case_count,
        "readyCount": ready_count,
        "pendingCount": pending_count,
        "missingCount": missing_count,
        "manifestHashPresentCount": manifest_hash_present_count,
        "artifactRefCount": _to_int(artifact_coverage.get("artifactRefCount")),
        "auditAnchorReadyCount": _to_int(audit_anchor_status.get("readyCount")),
        "auditAnchorPendingCount": _to_int(audit_anchor_status.get("pendingCount")),
        "auditAnchorMissingCount": _to_int(audit_anchor_status.get("missingCount")),
    }


def _build_public_verification_readiness(
    *,
    trust_items: list[dict[str, Any]],
    trust_errors: list[dict[str, Any]],
    public_verify_status: dict[str, Any],
) -> dict[str, Any]:
    sampled_case_count = _to_int(public_verify_status.get("sampledCaseCount"))
    readiness_status_counts: dict[str, int] = {}
    readiness_error_counts: dict[str, int] = {}
    externalizable_count = 0
    blocked_count = 0
    for item in trust_items:
        readiness = _dict_or_empty(item.get("publicVerificationReadiness"))
        status = _lower_token(readiness.get("status")) or "unknown"
        readiness_status_counts[status] = readiness_status_counts.get(status, 0) + 1
        error_code = _lower_token(readiness.get("errorCode"))
        if error_code is not None:
            readiness_error_counts[error_code] = readiness_error_counts.get(error_code, 0) + 1
        if bool(readiness.get("externalizable")):
            externalizable_count += 1
        else:
            blocked_count += 1

    error_count = _to_int(public_verify_status.get("errorCount")) + len(trust_errors)
    failed_count = _to_int(public_verify_status.get("failedCount"))
    pending_count = _to_int(public_verify_status.get("pendingCount"))
    if not trust_items and sampled_case_count <= 0:
        status = "not_sampled"
    elif error_count > 0 or failed_count > 0 or blocked_count > 0:
        status = "blocked"
    elif pending_count > 0:
        status = "pending"
    elif externalizable_count >= len(trust_items):
        status = "ready"
    else:
        status = "watch"

    return {
        "status": status,
        "sampledCaseCount": sampled_case_count,
        "verifiedCount": _to_int(public_verify_status.get("verifiedCount")),
        "failedCount": failed_count,
        "pendingCount": pending_count,
        "errorCount": error_count,
        "externalizableCount": externalizable_count,
        "blockedCount": blocked_count,
        "readinessStatusCounts": dict(
            sorted(readiness_status_counts.items(), key=lambda kv: kv[0])
        ),
        "readinessErrorCounts": dict(
            sorted(readiness_error_counts.items(), key=lambda kv: kv[0])
        ),
        "reasonCounts": _count_dict(public_verify_status.get("reasonCounts")),
    }


def _build_challenge_review_lag(
    *,
    challenge_review_state: dict[str, Any],
    trust_challenge_queue: dict[str, Any],
) -> dict[str, Any]:
    items = _list_of_dicts(trust_challenge_queue.get("items"))
    urgent_count = 0
    high_priority_count = 0
    for row in items:
        priority_profile = _dict_or_empty(row.get("priorityProfile"))
        if _lower_token(priority_profile.get("slaBucket")) == "urgent":
            urgent_count += 1
        if _lower_token(priority_profile.get("level")) == "high":
            high_priority_count += 1

    open_challenge_count = _to_int(challenge_review_state.get("openChallengeCount"))
    if urgent_count > 0:
        status = "blocked"
    elif high_priority_count > 0 or open_challenge_count > 0:
        status = "watch"
    elif _to_int(challenge_review_state.get("sampledCaseCount")) <= 0:
        status = "not_sampled"
    else:
        status = "clear"

    return {
        "status": status,
        "sampledCaseCount": _to_int(challenge_review_state.get("sampledCaseCount")),
        "openChallengeCount": open_challenge_count,
        "reviewRequiredCount": _to_int(challenge_review_state.get("reviewRequiredCount")),
        "totalChallengeCount": _to_int(challenge_review_state.get("totalChallengeCount")),
        "queueCount": _to_int(trust_challenge_queue.get("count")),
        "urgentCount": urgent_count,
        "highPriorityCount": high_priority_count,
        "challengeStateCounts": _count_dict(
            challenge_review_state.get("challengeStateCounts")
        ),
        "reviewStateCounts": _count_dict(challenge_review_state.get("reviewStateCounts")),
    }


def _build_registry_release_readiness(
    *,
    registry_prompt_tool_governance: dict[str, Any],
    policy_gate_simulation: dict[str, Any],
    policy_kernel_binding: dict[str, Any],
) -> dict[str, Any]:
    simulation_summary = _dict_or_empty(policy_gate_simulation.get("summary"))
    prompt_tool_summary = _dict_or_empty(registry_prompt_tool_governance.get("summary"))
    gate_decision_counts = _count_dict(policy_kernel_binding.get("gateDecisionCounts"))
    blocked_policy_count = (
        _to_int(simulation_summary.get("blockedCount"))
        + _to_int(gate_decision_counts.get("blocked"))
    )
    missing_kernel_binding_count = _to_int(
        policy_kernel_binding.get("missingKernelBindingCount")
    )
    evidence_summary = _summarize_release_readiness_evidence_items(
        _collect_release_readiness_evidence_items(
            registry_prompt_tool_governance=registry_prompt_tool_governance,
            policy_gate_simulation=policy_gate_simulation,
        )
    )
    high_risk_count = _to_int(prompt_tool_summary.get("riskHighCount")) or sum(
        1
        for row in _list_of_dicts(registry_prompt_tool_governance.get("riskItems"))
        if _lower_token(row.get("severity")) == "high"
    )
    risk_total_count = _to_int(prompt_tool_summary.get("riskTotalCount"))
    if blocked_policy_count > 0 or missing_kernel_binding_count > 0 or high_risk_count > 0:
        status = "blocked"
    elif risk_total_count > 0:
        status = "watch"
    else:
        status = "ready"

    return {
        "status": status,
        "activePolicyVersion": policy_kernel_binding.get("activePolicyVersion"),
        "blockedPolicyCount": blocked_policy_count,
        "overrideAppliedPolicyCount": _to_int(
            policy_kernel_binding.get("overrideAppliedPolicyCount")
        ),
        "missingKernelBindingCount": missing_kernel_binding_count,
        "riskItemCount": risk_total_count,
        "highRiskItemCount": high_risk_count,
        "gateDecisionCounts": gate_decision_counts,
        "releaseReadinessEvidenceVersion": evidence_summary["evidenceVersion"],
        "releaseReadinessEvidenceCount": evidence_summary["evidenceCount"],
        "envBlockedComponents": evidence_summary["envBlockedComponents"],
        "reasonCodes": evidence_summary["reasonCodes"],
        "artifactRefCount": evidence_summary["artifactRefCount"],
        "releaseReadinessArtifactCount": evidence_summary[
            "releaseReadinessArtifactCount"
        ],
        "releaseReadinessManifestHashCount": evidence_summary[
            "releaseReadinessManifestHashCount"
        ],
        "publicVerificationReadyCount": evidence_summary[
            "publicVerificationReadyCount"
        ],
        "realEnvEvidenceStatusCounts": evidence_summary[
            "realEnvEvidenceStatusCounts"
        ],
        "citationVerifierStatusCounts": evidence_summary[
            "citationVerifierStatusCounts"
        ],
        "citationVerifierReasonCodes": evidence_summary[
            "citationVerifierReasonCodes"
        ],
        "citationVerifierMissingCitationCount": evidence_summary[
            "citationVerifierMissingCitationCount"
        ],
        "citationVerifierWeakCitationCount": evidence_summary[
            "citationVerifierWeakCitationCount"
        ],
        "citationVerifierForbiddenSourceCount": evidence_summary[
            "citationVerifierForbiddenSourceCount"
        ],
    }


def _build_citation_verifier_evidence(
    *,
    registry_readiness: dict[str, Any],
) -> dict[str, Any]:
    status_counts = _count_dict(registry_readiness.get("citationVerifierStatusCounts"))
    evidence_count = _to_int(registry_readiness.get("releaseReadinessEvidenceCount"))
    blocked_like = (
        _to_int(status_counts.get("blocked"))
        + _to_int(registry_readiness.get("citationVerifierMissingCitationCount"))
        + _to_int(registry_readiness.get("citationVerifierForbiddenSourceCount"))
    )
    warning_like = (
        _to_int(status_counts.get("needs_review"))
        + _to_int(status_counts.get("warning"))
        + _to_int(registry_readiness.get("citationVerifierWeakCitationCount"))
    )
    env_blocked = _to_int(status_counts.get("env_blocked"))
    ready_like = _to_int(status_counts.get("ready")) + _to_int(status_counts.get("passed"))
    if evidence_count <= 0 or not status_counts:
        status = "not_sampled"
    elif blocked_like > 0:
        status = "blocked"
    elif env_blocked > 0:
        status = "env_blocked"
    elif warning_like > 0:
        status = "watch"
    elif ready_like > 0:
        status = "ready"
    else:
        status = "watch"
    return {
        "status": status,
        "statusCounts": status_counts,
        "reasonCodes": [
            str(code or "").strip()
            for code in (registry_readiness.get("citationVerifierReasonCodes") or [])
            if str(code or "").strip()
        ],
        "missingCitationCount": _to_int(
            registry_readiness.get("citationVerifierMissingCitationCount")
        ),
        "weakCitationCount": _to_int(
            registry_readiness.get("citationVerifierWeakCitationCount")
        ),
        "forbiddenSourceCount": _to_int(
            registry_readiness.get("citationVerifierForbiddenSourceCount")
        ),
    }


def _release_gate_from_advisor(
    fairness_calibration_advisor: dict[str, Any],
) -> dict[str, Any]:
    return _dict_or_empty(fairness_calibration_advisor.get("releaseGate"))


def _build_panel_shadow_drift(
    *,
    fairness_calibration_advisor: dict[str, Any],
) -> dict[str, Any]:
    overview = _dict_or_empty(fairness_calibration_advisor.get("overview"))
    drift_summary = _dict_or_empty(fairness_calibration_advisor.get("driftSummary"))
    release_gate = _release_gate_from_advisor(fairness_calibration_advisor)
    latest_shadow_run = _dict_or_empty(release_gate.get("latestShadowRun"))
    shadow_gate_applied = bool(release_gate.get("shadowGateApplied"))
    shadow_gate_passed = release_gate.get("shadowGatePassed")
    shadow_violation_count = _to_int(overview.get("shadowThresholdViolationCount"))
    drift_breach_count = _to_int(overview.get("driftBreachCount"))
    normalized_evidence = build_fairness_panel_evidence_normalization(
        fairness_calibration_advisor=fairness_calibration_advisor,
    )
    shadow_evidence_status = _lower_token(normalized_evidence.get("shadowEvidenceStatus"))
    if (
        shadow_evidence_status == "blocked"
        or shadow_gate_passed is False
        or shadow_violation_count > 0
    ):
        status = "blocked"
    elif shadow_evidence_status == "missing" or not shadow_gate_applied:
        status = "missing"
    elif shadow_evidence_status == "env_blocked":
        status = "env_blocked"
    elif (
        shadow_evidence_status == "watch"
        or drift_breach_count > 0
        or bool(drift_summary.get("hasBreach"))
    ):
        status = "watch"
    else:
        status = "ready"
    return {
        "status": status,
        "shadowRunCount": _to_int(overview.get("shadowRunCount")),
        "latestShadowRunId": (
            _token(overview.get("latestShadowRunId"))
            or _token(latest_shadow_run.get("runId"))
        ),
        "shadowThresholdViolationCount": shadow_violation_count,
        "driftBreachCount": drift_breach_count,
        "shadowGateApplied": shadow_gate_applied,
        "shadowGatePassed": shadow_gate_passed if isinstance(shadow_gate_passed, bool) else None,
        "latestShadowRunStatus": _lower_token(latest_shadow_run.get("status")),
        "latestShadowRunThresholdDecision": _lower_token(
            latest_shadow_run.get("thresholdDecision")
        ),
        "latestShadowRunEnvironmentMode": _lower_token(
            latest_shadow_run.get("environmentMode")
        ),
        "latestShadowRunNeedsRemediation": (
            bool(latest_shadow_run.get("needsRemediation"))
            if latest_shadow_run.get("needsRemediation") is not None
            else None
        ),
        "normalizedEvidence": normalized_evidence,
    }


def _build_real_env_evidence_status(
    *,
    fairness_calibration_advisor: dict[str, Any],
) -> dict[str, Any]:
    release_gate = _release_gate_from_advisor(fairness_calibration_advisor)
    normalized_evidence = build_fairness_panel_evidence_normalization(
        fairness_calibration_advisor=fairness_calibration_advisor,
    )
    latest_run = _dict_or_empty(release_gate.get("latestRun"))
    environment_mode = _lower_token(latest_run.get("environmentMode"))
    latest_status = _lower_token(latest_run.get("status"))
    threshold_decision = _lower_token(latest_run.get("thresholdDecision"))
    needs_remediation = (
        bool(latest_run.get("needsRemediation"))
        if latest_run.get("needsRemediation") is not None
        else None
    )
    real_env = environment_mode in {"real", "prod", "production", "staging"}
    pass_status = latest_status in {"pass", "passed", "completed", "success"}
    real_sample_status = _lower_token(normalized_evidence.get("realSampleManifestStatus"))
    if real_sample_status in {"env_blocked", "pending_real_samples"} or not real_env:
        status = "env_blocked"
    elif needs_remediation is True or threshold_decision in {"blocked", "fail", "failed"}:
        status = "blocked"
    elif pass_status:
        status = "ready"
    else:
        status = "pending"

    return {
        "status": status,
        "latestRunId": _token(latest_run.get("runId")),
        "latestRunStatus": latest_status,
        "latestRunThresholdDecision": threshold_decision,
        "latestRunEnvironmentMode": environment_mode,
        "latestRunNeedsRemediation": needs_remediation,
        "realEnvEvidenceAvailable": bool(real_env),
        "realSampleManifestStatus": real_sample_status,
        "normalizedEvidence": normalized_evidence,
    }


def _overall_status(blockers: list[dict[str, Any]]) -> str:
    if not blockers:
        return "ready"
    if any(row.get("severity") == "blocker" for row in blockers):
        return "blocked"
    return "watch"


def build_ops_trust_monitoring_summary(
    *,
    trust_items: list[dict[str, Any]],
    trust_errors: list[dict[str, Any]],
    artifact_coverage: dict[str, Any],
    audit_anchor_status: dict[str, Any],
    public_verify_status: dict[str, Any],
    challenge_review_state: dict[str, Any],
    trust_challenge_queue: dict[str, Any],
    registry_prompt_tool_governance: dict[str, Any],
    policy_gate_simulation: dict[str, Any],
    fairness_calibration_advisor: dict[str, Any],
    policy_kernel_binding: dict[str, Any],
) -> dict[str, Any]:
    artifact_readiness = _build_artifact_store_readiness(
        artifact_coverage=artifact_coverage,
        audit_anchor_status=audit_anchor_status,
    )
    verification_readiness = _build_public_verification_readiness(
        trust_items=trust_items,
        trust_errors=trust_errors,
        public_verify_status=public_verify_status,
    )
    challenge_lag = _build_challenge_review_lag(
        challenge_review_state=challenge_review_state,
        trust_challenge_queue=trust_challenge_queue,
    )
    registry_readiness = _build_registry_release_readiness(
        registry_prompt_tool_governance=registry_prompt_tool_governance,
        policy_gate_simulation=policy_gate_simulation,
        policy_kernel_binding=policy_kernel_binding,
    )
    citation_verifier_evidence = _build_citation_verifier_evidence(
        registry_readiness=registry_readiness,
    )
    shadow_drift = _build_panel_shadow_drift(
        fairness_calibration_advisor=fairness_calibration_advisor,
    )
    real_env_status = _build_real_env_evidence_status(
        fairness_calibration_advisor=fairness_calibration_advisor,
    )

    blockers: list[dict[str, Any]] = []
    _add_blocker(
        blockers,
        bucket="production",
        code="artifact_store_not_ready",
        count=artifact_readiness["missingCount"] + artifact_readiness["pendingCount"],
    )
    _add_blocker(
        blockers,
        bucket="production",
        code="public_verification_not_externalizable",
        count=verification_readiness["blockedCount"] + verification_readiness["errorCount"],
    )
    _add_blocker(
        blockers,
        bucket="review",
        code="challenge_review_lag",
        count=challenge_lag["openChallengeCount"] + challenge_lag["urgentCount"],
        severity="watch" if challenge_lag["urgentCount"] <= 0 else "blocker",
    )
    _add_blocker(
        blockers,
        bucket="release",
        code="registry_release_not_ready",
        count=(
            registry_readiness["blockedPolicyCount"]
            + registry_readiness["missingKernelBindingCount"]
            + registry_readiness["highRiskItemCount"]
        ),
    )
    _add_blocker(
        blockers,
        bucket="release",
        code="panel_shadow_drift_not_ready",
        count=(
            shadow_drift["shadowThresholdViolationCount"]
            + (0 if shadow_drift["status"] == "ready" else 1)
        ),
        severity="watch" if shadow_drift["status"] in {"missing", "watch"} else "blocker",
    )
    _add_blocker(
        blockers,
        bucket="evidence",
        code="real_env_evidence_not_ready",
        count=0 if real_env_status["status"] == "ready" else 1,
        severity="watch" if real_env_status["status"] == "env_blocked" else "blocker",
    )
    _add_blocker(
        blockers,
        bucket="evidence",
        code="citation_verifier_not_ready",
        count=(
            citation_verifier_evidence["missingCitationCount"]
            + citation_verifier_evidence["forbiddenSourceCount"]
            + (
                0
                if citation_verifier_evidence["status"] in {"ready", "not_sampled"}
                else 1
            )
        ),
        severity=(
            "blocker"
            if citation_verifier_evidence["status"] == "blocked"
            else "watch"
        ),
    )

    blocker_counts = {bucket: 0 for bucket in OPS_TRUST_MONITORING_BLOCKER_BUCKETS}
    for blocker in blockers:
        bucket = str(blocker.get("bucket") or "").strip()
        if bucket in blocker_counts:
            blocker_counts[bucket] += _to_int(blocker.get("count"))

    return {
        "monitoringVersion": OPS_TRUST_MONITORING_VERSION,
        "overallStatus": _overall_status(blockers),
        "sampledCaseCount": _to_int(artifact_coverage.get("sampledCaseCount")),
        "artifactStoreReadiness": artifact_readiness,
        "publicVerificationReadiness": verification_readiness,
        "challengeReviewLag": challenge_lag,
        "registryReleaseReadiness": registry_readiness,
        "citationVerifierEvidence": citation_verifier_evidence,
        "panelShadowDrift": shadow_drift,
        "realEnvEvidenceStatus": real_env_status,
        "blockerCounts": blocker_counts,
        "blockers": blockers,
        "redactionContract": {
            "artifactRefsVisible": False,
            "hashesOnly": True,
            "internalAuditPayloadVisible": False,
            "rawPromptVisible": False,
            "rawTraceVisible": False,
            "publicPayloadFields": [
                "caseId",
                "dispatchType",
                "traceId",
                "verificationVersion",
                "verificationRequest",
                "verificationReadiness",
                "visibilityContract",
            ],
        },
    }
