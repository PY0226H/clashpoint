from __future__ import annotations

from typing import Any

from app.domain.trust import TRUST_REGISTRY_VERSION

from .trust_public_verify_contract import (
    TRUST_PUBLIC_VERIFICATION_VERSION,
    build_trust_public_verify_cache_profile,
    build_trust_public_verify_readiness,
    build_trust_public_verify_request,
    build_trust_public_verify_visibility_contract,
)


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def build_trust_public_verify_route_payload(
    *,
    case_id: int,
    dispatch_type: str,
    trace_id: str,
    verify_payload: dict[str, Any] | Any,
    registry_version: str = TRUST_REGISTRY_VERSION,
    source: str | None = None,
) -> dict[str, Any]:
    verify_payload_dict = _dict_or_empty(verify_payload)
    normalized_dispatch_type = str(dispatch_type or "").strip().lower()
    normalized_trace_id = str(trace_id or "").strip()
    verification_request = build_trust_public_verify_request(
        case_id=int(case_id),
        dispatch_type=normalized_dispatch_type,
        trace_id=normalized_trace_id,
        registry_version=registry_version,
    )
    verification_readiness = build_trust_public_verify_readiness(
        verify_payload=verify_payload_dict,
        source=source,
    )
    return {
        "caseId": int(case_id),
        "dispatchType": normalized_dispatch_type,
        "traceId": normalized_trace_id,
        "verificationVersion": TRUST_PUBLIC_VERIFICATION_VERSION,
        "verificationRequest": verification_request,
        "verificationReadiness": verification_readiness,
        "verifyPayload": verify_payload_dict,
        "visibilityContract": build_trust_public_verify_visibility_contract(),
        "cacheProfile": build_trust_public_verify_cache_profile(
            verification_request=verification_request,
            verification_readiness=verification_readiness,
        ),
        "proxyRequired": True,
    }


def build_trust_public_verify_payload_from_bundle(
    *,
    case_id: int,
    bundle: dict[str, Any],
    build_audit_anchor_export: Any,
    build_public_verify_payload: Any,
    artifact_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = _dict_or_empty(bundle.get("context"))
    commitment = _dict_or_empty(bundle.get("commitment"))
    verdict_attestation = _dict_or_empty(bundle.get("verdictAttestation"))
    challenge_review = _dict_or_empty(bundle.get("challengeReview"))
    kernel_version = _dict_or_empty(bundle.get("kernelVersion"))
    audit_anchor = build_audit_anchor_export(
        case_id=case_id,
        dispatch_type=context.get("dispatchType"),
        trace_id=context.get("traceId"),
        case_commitment=commitment,
        verdict_attestation=verdict_attestation,
        challenge_review=challenge_review,
        kernel_version=kernel_version,
        include_payload=False,
        artifact_manifest=artifact_manifest,
    )
    return build_trust_public_verify_route_payload(
        case_id=case_id,
        dispatch_type=str(context.get("dispatchType") or ""),
        trace_id=str(context.get("traceId") or ""),
        verify_payload=build_public_verify_payload(
            commitment=commitment,
            verdict_attestation=verdict_attestation,
            challenge_review=challenge_review,
            kernel_version=kernel_version,
            audit_anchor=audit_anchor,
        ),
        registry_version=str(context.get("registryVersion") or TRUST_REGISTRY_VERSION),
        source=str(context.get("source") or ""),
    )
