from __future__ import annotations

from typing import Any

from .trust_artifact_summary import TRUST_ARTIFACT_COMPONENT_KEYS


def _to_int(value: Any, *, default: int = 0) -> int:
    try:
        if isinstance(value, bool):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _increment_count(target: dict[str, int], key: Any) -> None:
    token = str(key or "").strip().lower() or "unknown"
    target[token] = target.get(token, 0) + 1


def _sorted_counts(counts: dict[str, int]) -> dict[str, int]:
    return dict(sorted(counts.items(), key=lambda kv: kv[0]))


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


def build_ops_read_model_pack_trust_artifact_coverage(
    *,
    trust_items: list[dict[str, Any]],
    trust_errors: list[dict[str, Any]],
    open_challenge_states: set[str],
) -> dict[str, Any]:
    sampled_case_count = len(trust_items) + len(trust_errors)
    complete_count = 0
    partial_count = 0
    missing_count = len(trust_errors)
    by_component = {key: 0 for key in TRUST_ARTIFACT_COMPONENT_KEYS}
    source_counts: dict[str, int] = {}
    reason_counts: dict[str, int] = {}
    challenge_state_counts: dict[str, int] = {}
    review_state_counts: dict[str, int] = {}
    anchor_status_counts: dict[str, int] = {}
    artifact_kind_counts: dict[str, int] = {}

    verified_count = 0
    failed_count = 0
    pending_count = 0
    review_required_count = 0
    open_challenge_count = 0
    total_challenge_count = 0
    audit_ready_count = 0
    audit_pending_count = 0
    audit_missing_count = len(trust_errors)
    anchor_hash_present_count = 0
    artifact_manifest_hash_present_count = 0
    artifact_ready_count = 0
    artifact_pending_count = 0
    artifact_missing_count = len(trust_errors)
    artifact_ref_count = 0

    normalized_open_states = {
        str(state or "").strip().lower()
        for state in open_challenge_states
        if str(state or "").strip()
    }

    for item in trust_items:
        summary = (
            item.get("trustArtifactSummary")
            if isinstance(item.get("trustArtifactSummary"), dict)
            else {}
        )
        completeness = (
            summary.get("trustCompleteness")
            if isinstance(summary.get("trustCompleteness"), dict)
            else {}
        )
        ready_components = 0
        for key in TRUST_ARTIFACT_COMPONENT_KEYS:
            if bool(completeness.get(key)):
                by_component[key] += 1
                ready_components += 1
        if bool(completeness.get("complete")):
            complete_count += 1
        elif ready_components == 0:
            missing_count += 1
        else:
            partial_count += 1

        _increment_count(source_counts, summary.get("source"))

        public_verify = (
            summary.get("publicVerifyStatus")
            if isinstance(summary.get("publicVerifyStatus"), dict)
            else {}
        )
        reason = str(public_verify.get("reason") or "").strip().lower() or "unknown"
        _increment_count(reason_counts, reason)
        if bool(public_verify.get("verified")):
            verified_count += 1
        elif reason in {"registry_snapshot_missing", "unknown"}:
            pending_count += 1
        else:
            failed_count += 1

        challenge = (
            summary.get("challengeReview")
            if isinstance(summary.get("challengeReview"), dict)
            else {}
        )
        review_required = bool(challenge.get("reviewRequired"))
        review_required_count += 1 if review_required else 0
        total_challenge_count += max(0, _to_int(challenge.get("totalChallenges"), default=0))
        challenge_state = str(challenge.get("challengeState") or "").strip().lower()
        _increment_count(challenge_state_counts, challenge_state or "none")
        _increment_count(review_state_counts, challenge.get("reviewState") or "unknown")
        if challenge_state in normalized_open_states:
            open_challenge_count += 1

        audit_anchor = (
            summary.get("auditAnchor")
            if isinstance(summary.get("auditAnchor"), dict)
            else {}
        )
        anchor_status = str(audit_anchor.get("anchorStatus") or "").strip().lower() or "missing"
        _increment_count(anchor_status_counts, anchor_status)
        anchor_hash_present = bool(audit_anchor.get("anchorHashPresent"))
        manifest_hash_present = bool(audit_anchor.get("artifactManifestHashPresent"))
        anchor_hash_present_count += 1 if anchor_hash_present else 0
        artifact_manifest_hash_present_count += 1 if manifest_hash_present else 0
        if anchor_status == "artifact_ready" and anchor_hash_present:
            audit_ready_count += 1
        elif anchor_status == "artifact_pending":
            audit_pending_count += 1
        else:
            audit_missing_count += 1

        artifact = (
            summary.get("artifactCoverage")
            if isinstance(summary.get("artifactCoverage"), dict)
            else {}
        )
        if bool(artifact.get("ready")):
            artifact_ready_count += 1
        elif manifest_hash_present or anchor_status == "artifact_pending":
            artifact_pending_count += 1
        else:
            artifact_missing_count += 1
        artifact_ref_count += max(0, _to_int(artifact.get("artifactRefCount"), default=0))
        item_kind_counts = (
            artifact.get("artifactKindCounts")
            if isinstance(artifact.get("artifactKindCounts"), dict)
            else {}
        )
        for kind, count in item_kind_counts.items():
            token = str(kind or "").strip().lower() or "unknown"
            artifact_kind_counts[token] = artifact_kind_counts.get(token, 0) + max(
                0,
                _to_int(count, default=0),
            )

    error_count = len(trust_errors)
    if error_count:
        source_counts["error"] = source_counts.get("error", 0) + error_count
        reason_counts["error"] = reason_counts.get("error", 0) + error_count
    complete_rate = (
        round(float(complete_count) / float(sampled_case_count), 4)
        if sampled_case_count > 0
        else 0.0
    )
    return {
        "trustCoverage": {
            "sampledCaseCount": sampled_case_count,
            "completeCount": complete_count,
            "partialCount": partial_count,
            "missingCount": missing_count,
            "completeRate": complete_rate,
            "byComponent": by_component,
            "sourceCounts": _sorted_counts(source_counts),
        },
        "publicVerifyStatus": {
            "sampledCaseCount": sampled_case_count,
            "verifiedCount": verified_count,
            "failedCount": failed_count,
            "pendingCount": pending_count,
            "errorCount": error_count,
            "reasonCounts": _sorted_counts(reason_counts),
        },
        "challengeReviewState": {
            "sampledCaseCount": sampled_case_count,
            "reviewRequiredCount": review_required_count,
            "openChallengeCount": open_challenge_count,
            "totalChallengeCount": total_challenge_count,
            "challengeStateCounts": _sorted_counts(challenge_state_counts),
            "reviewStateCounts": _sorted_counts(review_state_counts),
        },
        "auditAnchorStatus": {
            "sampledCaseCount": sampled_case_count,
            "readyCount": audit_ready_count,
            "pendingCount": audit_pending_count,
            "missingCount": audit_missing_count,
            "anchorHashPresentCount": anchor_hash_present_count,
            "artifactManifestHashPresentCount": artifact_manifest_hash_present_count,
            "statusCounts": _sorted_counts(anchor_status_counts),
        },
        "artifactCoverage": {
            "sampledCaseCount": sampled_case_count,
            "readyCount": artifact_ready_count,
            "pendingCount": artifact_pending_count,
            "missingCount": artifact_missing_count,
            "manifestHashPresentCount": artifact_manifest_hash_present_count,
            "artifactRefCount": artifact_ref_count,
            "artifactKindCounts": _sorted_counts(artifact_kind_counts),
        },
    }


def build_ops_read_model_pack_policy_gate_rows(
    *,
    dependency_overview_rows: list[Any],
    policy_gate_simulation: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in dependency_overview_rows:
        if not isinstance(row, dict):
            continue
        policy_version_token = str(row.get("policyVersion") or "").strip()
        if not policy_version_token:
            continue
        rows.append(
            {
                "policyVersion": policy_version_token,
                "gateDecision": row.get("latestGateDecision"),
                "gateSource": row.get("latestGateSource"),
                "overrideApplied": row.get("overrideApplied"),
            }
        )
    if rows:
        return rows

    simulation_items = (
        policy_gate_simulation.get("items")
        if isinstance(policy_gate_simulation.get("items"), list)
        else []
    )
    for row in simulation_items:
        if not isinstance(row, dict):
            continue
        policy_version_token = str(row.get("policyVersion") or "").strip()
        if not policy_version_token:
            continue
        fairness_gate = row.get("fairnessGate") if isinstance(row.get("fairnessGate"), dict) else {}
        simulated_gate = row.get("simulatedGate") if isinstance(row.get("simulatedGate"), dict) else {}
        decision = (
            "pass"
            if str(simulated_gate.get("status") or "").strip().lower() == "pass"
            else "blocked"
        )
        rows.append(
            {
                "policyVersion": policy_version_token,
                "gateDecision": decision,
                "gateSource": fairness_gate.get("source"),
                "overrideApplied": False,
            }
        )
    return rows
