from __future__ import annotations

from typing import Any

from app.domain.trust import find_public_verify_forbidden_keys

TRUST_PUBLIC_VERIFY_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "caseId",
    "dispatchType",
    "traceId",
    "verifyPayload",
    "visibilityContract",
)

TRUST_PUBLIC_VERIFY_PAYLOAD_KEYS: tuple[str, ...] = (
    "caseCommitment",
    "verdictAttestation",
    "challengeReview",
    "kernelVersion",
    "auditAnchor",
)

TRUST_PUBLIC_VERIFY_CASE_COMMITMENT_KEYS: tuple[str, ...] = (
    "version",
    "commitmentHash",
    "requestHash",
    "workflowHash",
    "reportHash",
    "attestationCommitmentHash",
)

TRUST_PUBLIC_VERIFY_VERDICT_ATTESTATION_KEYS: tuple[str, ...] = (
    "version",
    "registryHash",
    "verified",
    "reason",
    "mismatchComponents",
    "attestationHashes",
)

TRUST_PUBLIC_VERIFY_CHALLENGE_REVIEW_KEYS: tuple[str, ...] = (
    "version",
    "registryHash",
    "reviewState",
    "reviewRequired",
    "challengeState",
    "activeChallengeId",
    "totalChallenges",
    "alertSummary",
    "challengeReasons",
)

TRUST_PUBLIC_VERIFY_KERNEL_VERSION_KEYS: tuple[str, ...] = (
    "version",
    "registryHash",
    "kernelHash",
    "kernelVector",
)

TRUST_PUBLIC_VERIFY_AUDIT_ANCHOR_KEYS: tuple[str, ...] = (
    "version",
    "anchorHash",
    "componentHashes",
)

TRUST_PUBLIC_VERIFY_AUDIT_ANCHOR_COMPONENT_HASH_KEYS: tuple[str, ...] = (
    "caseCommitmentHash",
    "verdictAttestationHash",
    "challengeReviewHash",
    "kernelVersionHash",
)

TRUST_PUBLIC_VERIFY_VISIBILITY_CONTRACT_KEYS: tuple[str, ...] = (
    "version",
    "layer",
    "payloadLayer",
    "allowedSections",
    "forbiddenFieldFamilies",
    "internalAuditRouteRequired",
)

TRUST_PUBLIC_VERIFY_ALLOWED_FIELD_FAMILIES: tuple[str, ...] = (
    "case_commitment_hashes",
    "verdict_attestation_hashes",
    "challenge_public_state",
    "kernel_version_hashes",
    "audit_anchor_hashes",
    "component_hashes",
)

TRUST_PUBLIC_VERIFY_FORBIDDEN_FIELD_FAMILIES: tuple[str, ...] = (
    "raw_prompt",
    "raw_trace",
    "raw_transcript",
    "internal_fairness_details",
    "user_identity",
    "spend_or_reputation",
)

TRUST_PUBLIC_VERIFY_KERNEL_VECTOR_PUBLIC_KEYS: tuple[str, ...] = (
    "judgeCoreVersion",
    "pipelineVersion",
    "policyVersion",
    "promptVersion",
    "toolsetVersion",
    "agentRuntimeVersion",
)

TRUST_PUBLIC_VERIFY_ATTESTATION_HASH_KEYS: tuple[str, ...] = (
    "commitmentHash",
    "verdictHash",
    "auditHash",
)


def _required_keys_missing(payload: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    return [key for key in keys if key not in payload]


def _assert_required_keys(
    *,
    section: str,
    payload: dict[str, Any],
    keys: tuple[str, ...],
) -> None:
    missing = _required_keys_missing(payload, keys)
    if missing:
        raise ValueError(f"{section}_missing_keys:{','.join(sorted(missing))}")


def _assert_only_keys(
    *,
    section: str,
    payload: dict[str, Any],
    keys: tuple[str, ...],
) -> None:
    allowed = set(keys)
    extra = sorted(str(key) for key in payload.keys() if str(key) not in allowed)
    if extra:
        raise ValueError(f"{section}_unexpected_keys:{','.join(extra)}")


def _non_negative_int(value: Any, *, default: int = 0) -> int:
    try:
        if isinstance(value, bool):
            return default
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, parsed)


def _assert_non_empty_string(section: str, value: Any) -> None:
    if not str(value or "").strip():
        raise ValueError(f"{section}_empty")


def _validate_case_commitment(payload: dict[str, Any]) -> None:
    _assert_required_keys(
        section="trust_public_verify_case_commitment",
        payload=payload,
        keys=TRUST_PUBLIC_VERIFY_CASE_COMMITMENT_KEYS,
    )
    _assert_only_keys(
        section="trust_public_verify_case_commitment",
        payload=payload,
        keys=TRUST_PUBLIC_VERIFY_CASE_COMMITMENT_KEYS,
    )
    _assert_non_empty_string(
        "trust_public_verify_case_commitment_version",
        payload.get("version"),
    )
    _assert_non_empty_string(
        "trust_public_verify_case_commitment_commitment_hash",
        payload.get("commitmentHash"),
    )
    _assert_non_empty_string(
        "trust_public_verify_case_commitment_request_hash",
        payload.get("requestHash"),
    )
    _assert_non_empty_string(
        "trust_public_verify_case_commitment_workflow_hash",
        payload.get("workflowHash"),
    )
    _assert_non_empty_string(
        "trust_public_verify_case_commitment_report_hash",
        payload.get("reportHash"),
    )


def _validate_verdict_attestation(payload: dict[str, Any]) -> None:
    _assert_required_keys(
        section="trust_public_verify_verdict_attestation",
        payload=payload,
        keys=TRUST_PUBLIC_VERIFY_VERDICT_ATTESTATION_KEYS,
    )
    _assert_only_keys(
        section="trust_public_verify_verdict_attestation",
        payload=payload,
        keys=TRUST_PUBLIC_VERIFY_VERDICT_ATTESTATION_KEYS,
    )
    _assert_non_empty_string(
        "trust_public_verify_verdict_attestation_version",
        payload.get("version"),
    )
    _assert_non_empty_string(
        "trust_public_verify_verdict_attestation_registry_hash",
        payload.get("registryHash"),
    )
    if not isinstance(payload.get("verified"), bool):
        raise ValueError("trust_public_verify_verdict_attestation_verified_not_bool")
    mismatch_components = payload.get("mismatchComponents")
    if not isinstance(mismatch_components, list):
        raise ValueError("trust_public_verify_verdict_attestation_mismatch_components_not_list")
    attestation_hashes = payload.get("attestationHashes")
    if not isinstance(attestation_hashes, dict):
        raise ValueError("trust_public_verify_verdict_attestation_attestation_hashes_not_dict")
    for key in TRUST_PUBLIC_VERIFY_ATTESTATION_HASH_KEYS:
        token = attestation_hashes.get(key)
        if token is None:
            continue
        _assert_non_empty_string(
            f"trust_public_verify_verdict_attestation_attestation_hashes_{key}",
            token,
        )


def _validate_challenge_review(payload: dict[str, Any]) -> None:
    _assert_required_keys(
        section="trust_public_verify_challenge_review",
        payload=payload,
        keys=TRUST_PUBLIC_VERIFY_CHALLENGE_REVIEW_KEYS,
    )
    _assert_only_keys(
        section="trust_public_verify_challenge_review",
        payload=payload,
        keys=TRUST_PUBLIC_VERIFY_CHALLENGE_REVIEW_KEYS,
    )
    _assert_non_empty_string(
        "trust_public_verify_challenge_review_version",
        payload.get("version"),
    )
    _assert_non_empty_string(
        "trust_public_verify_challenge_review_registry_hash",
        payload.get("registryHash"),
    )
    if not isinstance(payload.get("reviewRequired"), bool):
        raise ValueError("trust_public_verify_challenge_review_review_required_not_bool")
    total_challenges = _non_negative_int(payload.get("totalChallenges"), default=-1)
    if total_challenges < 0:
        raise ValueError("trust_public_verify_challenge_review_total_challenges_invalid")
    alert_summary = payload.get("alertSummary")
    if not isinstance(alert_summary, dict):
        raise ValueError("trust_public_verify_challenge_review_alert_summary_not_dict")
    challenge_reasons = payload.get("challengeReasons")
    if not isinstance(challenge_reasons, list):
        raise ValueError("trust_public_verify_challenge_review_challenge_reasons_not_list")


def _validate_kernel_version(payload: dict[str, Any]) -> None:
    _assert_required_keys(
        section="trust_public_verify_kernel_version",
        payload=payload,
        keys=TRUST_PUBLIC_VERIFY_KERNEL_VERSION_KEYS,
    )
    _assert_only_keys(
        section="trust_public_verify_kernel_version",
        payload=payload,
        keys=TRUST_PUBLIC_VERIFY_KERNEL_VERSION_KEYS,
    )
    _assert_non_empty_string(
        "trust_public_verify_kernel_version_version",
        payload.get("version"),
    )
    _assert_non_empty_string(
        "trust_public_verify_kernel_version_registry_hash",
        payload.get("registryHash"),
    )
    _assert_non_empty_string(
        "trust_public_verify_kernel_version_kernel_hash",
        payload.get("kernelHash"),
    )
    kernel_vector = payload.get("kernelVector")
    if not isinstance(kernel_vector, dict):
        raise ValueError("trust_public_verify_kernel_version_kernel_vector_not_dict")
    _assert_only_keys(
        section="trust_public_verify_kernel_version_kernel_vector",
        payload=kernel_vector,
        keys=TRUST_PUBLIC_VERIFY_KERNEL_VECTOR_PUBLIC_KEYS,
    )


def _validate_audit_anchor(payload: dict[str, Any]) -> None:
    _assert_required_keys(
        section="trust_public_verify_audit_anchor",
        payload=payload,
        keys=TRUST_PUBLIC_VERIFY_AUDIT_ANCHOR_KEYS,
    )
    _assert_only_keys(
        section="trust_public_verify_audit_anchor",
        payload=payload,
        keys=TRUST_PUBLIC_VERIFY_AUDIT_ANCHOR_KEYS,
    )
    _assert_non_empty_string(
        "trust_public_verify_audit_anchor_version",
        payload.get("version"),
    )
    _assert_non_empty_string(
        "trust_public_verify_audit_anchor_anchor_hash",
        payload.get("anchorHash"),
    )
    component_hashes = payload.get("componentHashes")
    if not isinstance(component_hashes, dict):
        raise ValueError("trust_public_verify_audit_anchor_component_hashes_not_dict")
    _assert_required_keys(
        section="trust_public_verify_audit_anchor_component_hashes",
        payload=component_hashes,
        keys=TRUST_PUBLIC_VERIFY_AUDIT_ANCHOR_COMPONENT_HASH_KEYS,
    )
    _assert_only_keys(
        section="trust_public_verify_audit_anchor_component_hashes",
        payload=component_hashes,
        keys=TRUST_PUBLIC_VERIFY_AUDIT_ANCHOR_COMPONENT_HASH_KEYS,
    )
    for key in TRUST_PUBLIC_VERIFY_AUDIT_ANCHOR_COMPONENT_HASH_KEYS:
        _assert_non_empty_string(
            f"trust_public_verify_audit_anchor_component_hashes_{key}",
            component_hashes.get(key),
        )


def build_trust_public_verify_visibility_contract() -> dict[str, Any]:
    return {
        "version": "trust-public-verify-visibility-v1",
        "layer": "public",
        "payloadLayer": "commitment_hashes_only",
        "allowedSections": list(TRUST_PUBLIC_VERIFY_ALLOWED_FIELD_FAMILIES),
        "forbiddenFieldFamilies": list(TRUST_PUBLIC_VERIFY_FORBIDDEN_FIELD_FAMILIES),
        "internalAuditRouteRequired": True,
    }


def _validate_visibility_contract(payload: dict[str, Any]) -> None:
    _assert_required_keys(
        section="trust_public_verify_visibility_contract",
        payload=payload,
        keys=TRUST_PUBLIC_VERIFY_VISIBILITY_CONTRACT_KEYS,
    )
    _assert_only_keys(
        section="trust_public_verify_visibility_contract",
        payload=payload,
        keys=TRUST_PUBLIC_VERIFY_VISIBILITY_CONTRACT_KEYS,
    )
    if payload.get("version") != "trust-public-verify-visibility-v1":
        raise ValueError("trust_public_verify_visibility_contract_version_invalid")
    if payload.get("layer") != "public":
        raise ValueError("trust_public_verify_visibility_contract_layer_invalid")
    if payload.get("payloadLayer") != "commitment_hashes_only":
        raise ValueError("trust_public_verify_visibility_contract_payload_layer_invalid")
    allowed_sections = payload.get("allowedSections")
    if not isinstance(allowed_sections, list):
        raise ValueError("trust_public_verify_visibility_contract_allowed_sections_not_list")
    if set(allowed_sections) != set(TRUST_PUBLIC_VERIFY_ALLOWED_FIELD_FAMILIES):
        raise ValueError("trust_public_verify_visibility_contract_allowed_sections_invalid")
    forbidden_families = payload.get("forbiddenFieldFamilies")
    if not isinstance(forbidden_families, list):
        raise ValueError("trust_public_verify_visibility_contract_forbidden_families_not_list")
    if set(forbidden_families) != set(TRUST_PUBLIC_VERIFY_FORBIDDEN_FIELD_FAMILIES):
        raise ValueError("trust_public_verify_visibility_contract_forbidden_families_invalid")
    if payload.get("internalAuditRouteRequired") is not True:
        raise ValueError("trust_public_verify_visibility_contract_internal_audit_route_invalid")


def _assert_no_forbidden_public_verify_fields(payload: dict[str, Any]) -> None:
    forbidden_keys = sorted(find_public_verify_forbidden_keys(payload))
    if forbidden_keys:
        raise ValueError(
            "trust_public_verify_forbidden_fields:"
            + ",".join(forbidden_keys)
        )


def validate_trust_public_verify_contract(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("trust_public_verify_payload_not_dict")
    _assert_no_forbidden_public_verify_fields(payload)
    _assert_required_keys(
        section="trust_public_verify",
        payload=payload,
        keys=TRUST_PUBLIC_VERIFY_TOP_LEVEL_KEYS,
    )
    _assert_only_keys(
        section="trust_public_verify",
        payload=payload,
        keys=TRUST_PUBLIC_VERIFY_TOP_LEVEL_KEYS,
    )
    case_id = _non_negative_int(payload.get("caseId"), default=0)
    if case_id <= 0:
        raise ValueError("trust_public_verify_case_id_invalid")
    dispatch_type = str(payload.get("dispatchType") or "").strip().lower()
    if dispatch_type not in {"phase", "final"}:
        raise ValueError("trust_public_verify_dispatch_type_invalid")
    _assert_non_empty_string("trust_public_verify_trace_id", payload.get("traceId"))

    verify_payload = payload.get("verifyPayload")
    if not isinstance(verify_payload, dict):
        raise ValueError("trust_public_verify_verify_payload_not_dict")
    _assert_required_keys(
        section="trust_public_verify_verify_payload",
        payload=verify_payload,
        keys=TRUST_PUBLIC_VERIFY_PAYLOAD_KEYS,
    )
    _assert_only_keys(
        section="trust_public_verify_verify_payload",
        payload=verify_payload,
        keys=TRUST_PUBLIC_VERIFY_PAYLOAD_KEYS,
    )

    visibility_contract = payload.get("visibilityContract")
    if not isinstance(visibility_contract, dict):
        raise ValueError("trust_public_verify_visibility_contract_not_dict")
    _validate_visibility_contract(visibility_contract)

    case_commitment = verify_payload.get("caseCommitment")
    if not isinstance(case_commitment, dict):
        raise ValueError("trust_public_verify_case_commitment_not_dict")
    _validate_case_commitment(case_commitment)

    verdict_attestation = verify_payload.get("verdictAttestation")
    if not isinstance(verdict_attestation, dict):
        raise ValueError("trust_public_verify_verdict_attestation_not_dict")
    _validate_verdict_attestation(verdict_attestation)

    challenge_review = verify_payload.get("challengeReview")
    if not isinstance(challenge_review, dict):
        raise ValueError("trust_public_verify_challenge_review_not_dict")
    _validate_challenge_review(challenge_review)

    kernel_version = verify_payload.get("kernelVersion")
    if not isinstance(kernel_version, dict):
        raise ValueError("trust_public_verify_kernel_version_not_dict")
    _validate_kernel_version(kernel_version)

    audit_anchor = verify_payload.get("auditAnchor")
    if not isinstance(audit_anchor, dict):
        raise ValueError("trust_public_verify_audit_anchor_not_dict")
    _validate_audit_anchor(audit_anchor)
