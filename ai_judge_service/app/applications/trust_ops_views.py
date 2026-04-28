from __future__ import annotations

from typing import Any

from .trust_challenge_ops_projection import (
    build_review_trust_unified_priority_profile,
    build_trust_challenge_action_hints,
    build_trust_challenge_ops_queue_item,
    build_trust_challenge_ops_queue_payload,
    build_trust_challenge_ops_queue_summary,
    build_trust_challenge_priority_profile,
    build_trust_challenge_sort_key,
    normalize_trust_challenge_priority_level,
    normalize_trust_challenge_review_state,
    normalize_trust_challenge_sla_bucket,
    normalize_trust_challenge_sort_by,
    normalize_trust_challenge_sort_order,
    normalize_trust_challenge_state_filter,
)
from .trust_public_verify_contract import TRUST_PUBLIC_VERIFY_KERNEL_VECTOR_PUBLIC_KEYS

__all__ = (
    "build_public_trust_verify_payload",
    "build_review_trust_unified_priority_profile",
    "build_trust_challenge_action_hints",
    "build_trust_challenge_ops_queue_item",
    "build_trust_challenge_ops_queue_payload",
    "build_trust_challenge_ops_queue_summary",
    "build_trust_challenge_priority_profile",
    "build_trust_challenge_sort_key",
    "normalize_trust_challenge_priority_level",
    "normalize_trust_challenge_review_state",
    "normalize_trust_challenge_sla_bucket",
    "normalize_trust_challenge_sort_by",
    "normalize_trust_challenge_sort_order",
    "normalize_trust_challenge_state_filter",
)


def _build_public_kernel_vector(payload: dict[str, Any]) -> dict[str, Any]:
    kernel_vector = payload.get("kernelVector")
    if not isinstance(kernel_vector, dict):
        return {}
    return {
        key: kernel_vector.get(key)
        for key in TRUST_PUBLIC_VERIFY_KERNEL_VECTOR_PUBLIC_KEYS
        if kernel_vector.get(key) is not None
    }


def build_public_trust_verify_payload(
    *,
    commitment: dict[str, Any],
    verdict_attestation: dict[str, Any],
    challenge_review: dict[str, Any],
    kernel_version: dict[str, Any],
    audit_anchor: dict[str, Any],
) -> dict[str, Any]:
    attestation = (
        verdict_attestation.get("attestation")
        if isinstance(verdict_attestation.get("attestation"), dict)
        else {}
    )
    attestation_hashes: dict[str, str] = {}
    for key in ("commitmentHash", "verdictHash", "auditHash"):
        token = str(attestation.get(key) or "").strip()
        if token:
            attestation_hashes[key] = token

    mismatch_components_raw = verdict_attestation.get("mismatchComponents")
    mismatch_components = (
        [str(item).strip() for item in mismatch_components_raw if str(item).strip()]
        if isinstance(mismatch_components_raw, list)
        else []
    )
    challenge_reasons_raw = challenge_review.get("challengeReasons")
    challenge_reasons = (
        [str(item).strip() for item in challenge_reasons_raw if str(item).strip()]
        if isinstance(challenge_reasons_raw, list)
        else []
    )
    total_challenges_raw = challenge_review.get("totalChallenges")
    try:
        total_challenges = int(total_challenges_raw)
    except (TypeError, ValueError):
        total_challenges = 0

    return {
        "caseCommitment": {
            "version": commitment.get("version"),
            "commitmentHash": commitment.get("commitmentHash"),
            "requestHash": commitment.get("requestHash"),
            "workflowHash": commitment.get("workflowHash"),
            "reportHash": commitment.get("reportHash"),
            "attestationCommitmentHash": commitment.get("attestationCommitmentHash"),
        },
        "verdictAttestation": {
            "version": verdict_attestation.get("version"),
            "registryHash": verdict_attestation.get("registryHash"),
            "verified": bool(verdict_attestation.get("verified")),
            "reason": verdict_attestation.get("reason"),
            "mismatchComponents": mismatch_components,
            "attestationHashes": attestation_hashes,
        },
        "challengeReview": {
            "version": challenge_review.get("version"),
            "registryHash": challenge_review.get("registryHash"),
            "reviewState": challenge_review.get("reviewState"),
            "reviewRequired": bool(challenge_review.get("reviewRequired")),
            "challengeState": challenge_review.get("challengeState"),
            "activeChallengeId": challenge_review.get("activeChallengeId"),
            "totalChallenges": total_challenges,
            "alertSummary": (
                dict(challenge_review.get("alertSummary"))
                if isinstance(challenge_review.get("alertSummary"), dict)
                else {}
            ),
            "challengeReasons": challenge_reasons,
        },
        "kernelVersion": {
            "version": kernel_version.get("version"),
            "registryHash": kernel_version.get("registryHash"),
            "kernelHash": kernel_version.get("kernelHash"),
            "kernelVector": _build_public_kernel_vector(kernel_version),
        },
        "auditAnchor": {
            "version": audit_anchor.get("version"),
            "anchorHash": audit_anchor.get("anchorHash"),
            "anchorStatus": audit_anchor.get("anchorStatus") or "artifact_pending",
            "componentHashes": (
                dict(audit_anchor.get("componentHashes"))
                if isinstance(audit_anchor.get("componentHashes"), dict)
                else {}
            ),
        },
    }
