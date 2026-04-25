from __future__ import annotations

from typing import Any

from app.domain.trust import find_public_verify_forbidden_keys

TRUST_PUBLIC_VERIFICATION_VERSION = "trust-public-verification-v1"

TRUST_PUBLIC_VERIFY_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "caseId",
    "dispatchType",
    "traceId",
    "verificationVersion",
    "verificationRequest",
    "verificationReadiness",
    "verifyPayload",
    "visibilityContract",
    "cacheProfile",
    "proxyRequired",
)

TRUST_PUBLIC_VERIFY_REQUEST_KEYS: tuple[str, ...] = (
    "requestKey",
    "caseId",
    "dispatchType",
    "traceId",
    "registryVersion",
    "verificationVersion",
)

TRUST_PUBLIC_VERIFY_READINESS_KEYS: tuple[str, ...] = (
    "ready",
    "status",
    "errorCode",
    "blockers",
    "externalizable",
)

TRUST_PUBLIC_VERIFY_READY_STATUSES: tuple[str, ...] = (
    "ready",
    "verification_not_ready",
    "trust_registry_missing",
    "artifact_manifest_pending",
    "challenge_under_review",
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
    "anchorStatus",
    "componentHashes",
)

TRUST_PUBLIC_VERIFY_AUDIT_ANCHOR_BASE_COMPONENT_HASH_KEYS: tuple[str, ...] = (
    "caseCommitmentHash",
    "verdictAttestationHash",
    "challengeReviewHash",
    "kernelVersionHash",
)

TRUST_PUBLIC_VERIFY_AUDIT_ANCHOR_COMPONENT_HASH_KEYS: tuple[str, ...] = (
    *TRUST_PUBLIC_VERIFY_AUDIT_ANCHOR_BASE_COMPONENT_HASH_KEYS,
    "artifactManifestHash",
)

TRUST_PUBLIC_VERIFY_VISIBILITY_CONTRACT_KEYS: tuple[str, ...] = (
    "version",
    "layer",
    "payloadLayer",
    "allowedSections",
    "forbiddenFieldFamilies",
    "internalAuditRouteRequired",
    "chatProxyRequired",
    "directAiServiceAccessAllowed",
)

TRUST_PUBLIC_VERIFY_CACHE_PROFILE_KEYS: tuple[str, ...] = (
    "cacheable",
    "ttlSeconds",
    "staleIfErrorSeconds",
    "cacheKey",
    "varyBy",
)

TRUST_PUBLIC_VERIFY_CACHE_VARY_BY: tuple[str, ...] = (
    "caseId",
    "dispatchType",
    "traceId",
    "registryVersion",
    "verificationVersion",
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


def build_trust_public_verify_request(
    *,
    case_id: int,
    dispatch_type: str,
    trace_id: str,
    registry_version: str,
    verification_version: str = TRUST_PUBLIC_VERIFICATION_VERSION,
) -> dict[str, Any]:
    normalized_dispatch_type = str(dispatch_type or "").strip().lower()
    normalized_trace_id = str(trace_id or "").strip()
    normalized_registry_version = str(registry_version or "").strip()
    request_key = (
        f"case:{int(case_id)}"
        f":dispatch:{normalized_dispatch_type}"
        f":trace:{normalized_trace_id}"
        f":registry:{normalized_registry_version}"
        f":verification:{verification_version}"
    )
    return {
        "requestKey": request_key,
        "caseId": int(case_id),
        "dispatchType": normalized_dispatch_type,
        "traceId": normalized_trace_id,
        "registryVersion": normalized_registry_version,
        "verificationVersion": verification_version,
    }


def build_trust_public_verify_readiness(
    *,
    verify_payload: dict[str, Any] | None,
    source: str | None,
) -> dict[str, Any]:
    payload = dict(verify_payload) if isinstance(verify_payload, dict) else {}
    source_token = str(source or "").strip().lower()
    audit_anchor = (
        dict(payload.get("auditAnchor"))
        if isinstance(payload.get("auditAnchor"), dict)
        else {}
    )
    challenge_review = (
        dict(payload.get("challengeReview"))
        if isinstance(payload.get("challengeReview"), dict)
        else {}
    )
    blockers: list[str] = []
    if not payload:
        blockers.append("verification_not_ready")
    if source_token and source_token != "trust_registry":
        blockers.append("trust_registry_missing")
    anchor_status = str(audit_anchor.get("anchorStatus") or "").strip().lower()
    if anchor_status != "artifact_ready":
        blockers.append("artifact_manifest_pending")
    challenge_state = str(challenge_review.get("challengeState") or "").strip().lower()
    review_state = str(challenge_review.get("reviewState") or "").strip().lower()
    if challenge_state in {
        "challenge_requested",
        "challenge_accepted",
        "under_internal_review",
    } or review_state == "under_internal_review":
        blockers.append("challenge_under_review")

    deduped_blockers = list(dict.fromkeys(blockers))
    if not deduped_blockers:
        return {
            "ready": True,
            "status": "ready",
            "errorCode": None,
            "blockers": [],
            "externalizable": True,
        }
    status = deduped_blockers[0]
    return {
        "ready": False,
        "status": status,
        "errorCode": status,
        "blockers": deduped_blockers,
        "externalizable": False,
    }


def build_trust_public_verify_cache_profile(
    *,
    verification_request: dict[str, Any],
    verification_readiness: dict[str, Any],
) -> dict[str, Any]:
    ready = bool(verification_readiness.get("ready"))
    return {
        "cacheable": ready,
        "ttlSeconds": 300 if ready else 0,
        "staleIfErrorSeconds": 0,
        "cacheKey": str(verification_request.get("requestKey") or "").strip(),
        "varyBy": list(TRUST_PUBLIC_VERIFY_CACHE_VARY_BY),
    }


def _validate_verification_request(
    payload: dict[str, Any],
    *,
    parent: dict[str, Any],
) -> None:
    _assert_required_keys(
        section="trust_public_verify_request",
        payload=payload,
        keys=TRUST_PUBLIC_VERIFY_REQUEST_KEYS,
    )
    _assert_only_keys(
        section="trust_public_verify_request",
        payload=payload,
        keys=TRUST_PUBLIC_VERIFY_REQUEST_KEYS,
    )
    _assert_non_empty_string(
        "trust_public_verify_request_request_key",
        payload.get("requestKey"),
    )
    _assert_non_empty_string(
        "trust_public_verify_request_registry_version",
        payload.get("registryVersion"),
    )
    if payload.get("caseId") != parent.get("caseId"):
        raise ValueError("trust_public_verify_request_case_id_mismatch")
    if payload.get("dispatchType") != parent.get("dispatchType"):
        raise ValueError("trust_public_verify_request_dispatch_type_mismatch")
    if payload.get("traceId") != parent.get("traceId"):
        raise ValueError("trust_public_verify_request_trace_id_mismatch")
    if payload.get("verificationVersion") != parent.get("verificationVersion"):
        raise ValueError("trust_public_verify_request_version_mismatch")


def _validate_verification_readiness(payload: dict[str, Any]) -> None:
    _assert_required_keys(
        section="trust_public_verify_readiness",
        payload=payload,
        keys=TRUST_PUBLIC_VERIFY_READINESS_KEYS,
    )
    _assert_only_keys(
        section="trust_public_verify_readiness",
        payload=payload,
        keys=TRUST_PUBLIC_VERIFY_READINESS_KEYS,
    )
    if not isinstance(payload.get("ready"), bool):
        raise ValueError("trust_public_verify_readiness_ready_not_bool")
    status = str(payload.get("status") or "").strip().lower()
    if status not in TRUST_PUBLIC_VERIFY_READY_STATUSES:
        raise ValueError("trust_public_verify_readiness_status_invalid")
    blockers = payload.get("blockers")
    if not isinstance(blockers, list):
        raise ValueError("trust_public_verify_readiness_blockers_not_list")
    invalid_blockers = [
        str(item)
        for item in blockers
        if str(item or "").strip().lower() not in TRUST_PUBLIC_VERIFY_READY_STATUSES
        or str(item or "").strip().lower() == "ready"
    ]
    if invalid_blockers:
        raise ValueError("trust_public_verify_readiness_blockers_invalid")
    if not isinstance(payload.get("externalizable"), bool):
        raise ValueError("trust_public_verify_readiness_externalizable_not_bool")
    if payload["ready"]:
        if status != "ready":
            raise ValueError("trust_public_verify_readiness_ready_status_invalid")
        if payload.get("errorCode") is not None:
            raise ValueError("trust_public_verify_readiness_ready_error_code_forbidden")
        if blockers:
            raise ValueError("trust_public_verify_readiness_ready_blockers_forbidden")
        if payload.get("externalizable") is not True:
            raise ValueError("trust_public_verify_readiness_ready_externalizable_invalid")
    else:
        if status == "ready":
            raise ValueError("trust_public_verify_readiness_blocked_status_invalid")
        if str(payload.get("errorCode") or "").strip().lower() != status:
            raise ValueError("trust_public_verify_readiness_error_code_mismatch")
        if not blockers:
            raise ValueError("trust_public_verify_readiness_blockers_required")
        if payload.get("externalizable") is not False:
            raise ValueError("trust_public_verify_readiness_blocked_externalizable_invalid")


def _validate_cache_profile(
    payload: dict[str, Any],
    *,
    verification_request: dict[str, Any],
    verification_readiness: dict[str, Any],
) -> None:
    _assert_required_keys(
        section="trust_public_verify_cache_profile",
        payload=payload,
        keys=TRUST_PUBLIC_VERIFY_CACHE_PROFILE_KEYS,
    )
    _assert_only_keys(
        section="trust_public_verify_cache_profile",
        payload=payload,
        keys=TRUST_PUBLIC_VERIFY_CACHE_PROFILE_KEYS,
    )
    if not isinstance(payload.get("cacheable"), bool):
        raise ValueError("trust_public_verify_cache_profile_cacheable_not_bool")
    ttl_seconds = _non_negative_int(payload.get("ttlSeconds"), default=-1)
    if ttl_seconds < 0:
        raise ValueError("trust_public_verify_cache_profile_ttl_invalid")
    stale_if_error_seconds = _non_negative_int(
        payload.get("staleIfErrorSeconds"),
        default=-1,
    )
    if stale_if_error_seconds < 0:
        raise ValueError("trust_public_verify_cache_profile_stale_invalid")
    cache_key = str(payload.get("cacheKey") or "").strip()
    if not cache_key:
        raise ValueError("trust_public_verify_cache_profile_cache_key_empty")
    if cache_key != str(verification_request.get("requestKey") or "").strip():
        raise ValueError("trust_public_verify_cache_profile_cache_key_mismatch")
    vary_by = payload.get("varyBy")
    if not isinstance(vary_by, list):
        raise ValueError("trust_public_verify_cache_profile_vary_by_not_list")
    if vary_by != list(TRUST_PUBLIC_VERIFY_CACHE_VARY_BY):
        raise ValueError("trust_public_verify_cache_profile_vary_by_invalid")
    ready = bool(verification_readiness.get("ready"))
    if ready:
        if payload.get("cacheable") is not True or ttl_seconds <= 0:
            raise ValueError("trust_public_verify_cache_profile_ready_cache_invalid")
    elif payload.get("cacheable") is not False or ttl_seconds != 0:
        raise ValueError("trust_public_verify_cache_profile_not_ready_cache_invalid")


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
    anchor_status = str(payload.get("anchorStatus") or "").strip().lower()
    if anchor_status not in {"artifact_ready", "artifact_pending"}:
        raise ValueError("trust_public_verify_audit_anchor_status_invalid")
    component_hashes = payload.get("componentHashes")
    if not isinstance(component_hashes, dict):
        raise ValueError("trust_public_verify_audit_anchor_component_hashes_not_dict")
    _assert_required_keys(
        section="trust_public_verify_audit_anchor_component_hashes",
        payload=component_hashes,
        keys=TRUST_PUBLIC_VERIFY_AUDIT_ANCHOR_BASE_COMPONENT_HASH_KEYS,
    )
    _assert_only_keys(
        section="trust_public_verify_audit_anchor_component_hashes",
        payload=component_hashes,
        keys=TRUST_PUBLIC_VERIFY_AUDIT_ANCHOR_COMPONENT_HASH_KEYS,
    )
    for key in TRUST_PUBLIC_VERIFY_AUDIT_ANCHOR_BASE_COMPONENT_HASH_KEYS:
        _assert_non_empty_string(
            f"trust_public_verify_audit_anchor_component_hashes_{key}",
            component_hashes.get(key),
        )
    if anchor_status == "artifact_ready":
        _assert_non_empty_string(
            "trust_public_verify_audit_anchor_anchor_hash",
            payload.get("anchorHash"),
        )
        _assert_non_empty_string(
            "trust_public_verify_audit_anchor_component_hashes_artifactManifestHash",
            component_hashes.get("artifactManifestHash"),
        )
    else:
        if str(payload.get("anchorHash") or "").strip():
            raise ValueError("trust_public_verify_audit_anchor_pending_anchor_hash_forbidden")
        if str(component_hashes.get("artifactManifestHash") or "").strip():
            raise ValueError(
                "trust_public_verify_audit_anchor_pending_artifact_manifest_hash_forbidden"
            )


def build_trust_public_verify_visibility_contract() -> dict[str, Any]:
    return {
        "version": "trust-public-verify-visibility-v1",
        "layer": "public",
        "payloadLayer": "commitment_hashes_only",
        "allowedSections": list(TRUST_PUBLIC_VERIFY_ALLOWED_FIELD_FAMILIES),
        "forbiddenFieldFamilies": list(TRUST_PUBLIC_VERIFY_FORBIDDEN_FIELD_FAMILIES),
        "internalAuditRouteRequired": True,
        "chatProxyRequired": True,
        "directAiServiceAccessAllowed": False,
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
    if payload.get("chatProxyRequired") is not True:
        raise ValueError("trust_public_verify_visibility_contract_chat_proxy_invalid")
    if payload.get("directAiServiceAccessAllowed") is not False:
        raise ValueError("trust_public_verify_visibility_contract_direct_ai_access_invalid")


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
    if payload.get("verificationVersion") != TRUST_PUBLIC_VERIFICATION_VERSION:
        raise ValueError("trust_public_verify_verification_version_invalid")

    verification_request = payload.get("verificationRequest")
    if not isinstance(verification_request, dict):
        raise ValueError("trust_public_verify_request_not_dict")
    _validate_verification_request(verification_request, parent=payload)

    verification_readiness = payload.get("verificationReadiness")
    if not isinstance(verification_readiness, dict):
        raise ValueError("trust_public_verify_readiness_not_dict")
    _validate_verification_readiness(verification_readiness)

    verify_payload = payload.get("verifyPayload")
    if not isinstance(verify_payload, dict):
        raise ValueError("trust_public_verify_verify_payload_not_dict")

    visibility_contract = payload.get("visibilityContract")
    if not isinstance(visibility_contract, dict):
        raise ValueError("trust_public_verify_visibility_contract_not_dict")
    _validate_visibility_contract(visibility_contract)

    if payload.get("proxyRequired") is not True:
        raise ValueError("trust_public_verify_proxy_required_invalid")
    if payload.get("proxyRequired") != visibility_contract.get("chatProxyRequired"):
        raise ValueError("trust_public_verify_proxy_visibility_mismatch")

    cache_profile = payload.get("cacheProfile")
    if not isinstance(cache_profile, dict):
        raise ValueError("trust_public_verify_cache_profile_not_dict")
    _validate_cache_profile(
        cache_profile,
        verification_request=verification_request,
        verification_readiness=verification_readiness,
    )

    if not bool(verification_readiness.get("ready")) and not verify_payload:
        return

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
