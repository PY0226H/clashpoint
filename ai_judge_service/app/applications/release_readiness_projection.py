from __future__ import annotations

from typing import Any


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _token(value: Any) -> str | None:
    token = str(value or "").strip()
    return token or None


def _tokens_from_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [token for item in value if (token := _token(item))]


def summarize_release_readiness_evidence(
    evidence_items: list[dict[str, Any]],
) -> dict[str, Any]:
    evidence_version = next(
        (
            str(item.get("evidenceVersion") or "").strip()
            for item in evidence_items
            if str(item.get("evidenceVersion") or "").strip()
        ),
        None,
    )
    env_blocked_components = sorted(
        {
            component
            for item in evidence_items
            for component in _tokens_from_list(item.get("envBlockedComponents"))
        }
    )
    reason_codes = sorted(
        {
            code
            for item in evidence_items
            for code in _tokens_from_list(item.get("reasonCodes"))
        }
    )
    artifact_refs = sorted(
        {
            ref
            for item in evidence_items
            for ref in _tokens_from_list(item.get("artifactRefs"))
        }
    )
    release_artifact_refs = sorted(
        {
            artifact_ref
            for item in evidence_items
            for summary in [_dict_or_empty(item.get("releaseReadinessArtifactSummary"))]
            if (artifact_ref := _token(summary.get("artifactRef")))
        }
    )
    release_manifest_hashes = sorted(
        {
            manifest_hash
            for item in evidence_items
            for summary in [_dict_or_empty(item.get("releaseReadinessArtifactSummary"))]
            if (manifest_hash := _token(summary.get("manifestHash")))
        }
    )
    real_env_evidence_status_counts: dict[str, int] = {}
    for item in evidence_items:
        real_env_status = _dict_or_empty(item.get("realEnvEvidenceStatus"))
        status = str(real_env_status.get("status") or "").strip().lower() or "unknown"
        real_env_evidence_status_counts[status] = (
            real_env_evidence_status_counts.get(status, 0) + 1
        )
    return {
        "evidenceVersion": evidence_version,
        "evidenceCount": len(evidence_items),
        "envBlockedComponents": env_blocked_components,
        "reasonCodes": reason_codes,
        "artifactRefCount": len(artifact_refs),
        "releaseReadinessArtifactCount": len(release_artifact_refs),
        "releaseReadinessManifestHashCount": len(release_manifest_hashes),
        "realEnvEvidenceStatusCounts": dict(
            sorted(real_env_evidence_status_counts.items(), key=lambda kv: kv[0])
        ),
    }


def build_registry_release_readiness_projection(
    *,
    decision_counts: dict[str, int],
    component_block_counts: dict[str, int],
    dependency_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    evidence_items = [
        row.get("releaseReadinessEvidence")
        for row in dependency_rows
        if isinstance(row.get("releaseReadinessEvidence"), dict)
    ]
    evidence_summary = summarize_release_readiness_evidence(evidence_items)
    return {
        "decisionCounts": dict(decision_counts),
        "allowedCount": int(decision_counts.get("allowed") or 0),
        "blockedCount": int(decision_counts.get("blocked") or 0),
        "envBlockedCount": int(decision_counts.get("env_blocked") or 0),
        "needsReviewCount": int(decision_counts.get("needs_review") or 0),
        "componentBlockCounts": dict(
            sorted(component_block_counts.items(), key=lambda kv: kv[0])
        ),
        "evidenceVersion": evidence_summary["evidenceVersion"],
        "evidenceCount": evidence_summary["evidenceCount"],
        "envBlockedComponents": evidence_summary["envBlockedComponents"],
        "reasonCodes": evidence_summary["reasonCodes"],
        "artifactRefCount": evidence_summary["artifactRefCount"],
        "releaseReadinessArtifactCount": evidence_summary[
            "releaseReadinessArtifactCount"
        ],
        "releaseReadinessManifestHashCount": evidence_summary[
            "releaseReadinessManifestHashCount"
        ],
        "realEnvEvidenceStatusCounts": evidence_summary[
            "realEnvEvidenceStatusCounts"
        ],
        "items": [
            {
                "policyVersion": row.get("policyVersion"),
                "decision": row.get("releaseGateDecision"),
                "code": row.get("releaseGateCode"),
                "reasonCodes": row.get("releaseGateReasonCodes"),
                "evidence": row.get("releaseReadinessEvidence"),
            }
            for row in dependency_rows
        ],
    }
