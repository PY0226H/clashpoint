from __future__ import annotations

from typing import Any

TRUST_ARTIFACT_COMPONENT_KEYS: tuple[str, ...] = (
    "caseCommitment",
    "verdictAttestation",
    "challengeReview",
    "kernelVersion",
    "auditAnchor",
)


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _token(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _lower_token(value: Any) -> str | None:
    token = _token(value)
    return token.lower() if token is not None else None


def _safe_int(value: Any) -> int:
    try:
        if isinstance(value, bool):
            return 0
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _artifact_refs_from_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows = manifest.get("artifactRefs")
    if not isinstance(rows, list):
        return []
    refs: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        kind = _lower_token(row.get("kind"))
        if kind is None:
            continue
        refs.append(
            {
                "kind": kind,
                "artifactId": _token(row.get("artifactId")),
                "uri": _token(row.get("uri")),
                "sha256": _lower_token(row.get("sha256")),
                "redactionLevel": _lower_token(row.get("redactionLevel")),
            }
        )
    return refs


def _artifact_kind_counts(refs: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in refs:
        kind = _lower_token(row.get("kind")) or "unknown"
        counts[kind] = counts.get(kind, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: kv[0]))


def _artifact_manifest_from_anchor(audit_anchor: dict[str, Any]) -> dict[str, Any]:
    manifest = audit_anchor.get("artifactManifest")
    return dict(manifest) if isinstance(manifest, dict) else {}


def _component_hashes_from_anchor(audit_anchor: dict[str, Any]) -> dict[str, Any]:
    return (
        dict(audit_anchor.get("componentHashes"))
        if isinstance(audit_anchor.get("componentHashes"), dict)
        else {}
    )


def build_trust_artifact_summary(
    *,
    case_id: int | None,
    dispatch_type: str | None,
    trace_id: str | None,
    source: str,
    case_commitment: dict[str, Any] | None = None,
    verdict_attestation: dict[str, Any] | None = None,
    challenge_review: dict[str, Any] | None = None,
    kernel_version: dict[str, Any] | None = None,
    audit_anchor: dict[str, Any] | None = None,
    include_artifact_refs: bool = False,
) -> dict[str, Any]:
    commitment = _dict_or_empty(case_commitment)
    verdict = _dict_or_empty(verdict_attestation)
    challenge = _dict_or_empty(challenge_review)
    kernel = _dict_or_empty(kernel_version)
    anchor = _dict_or_empty(audit_anchor)
    manifest = _artifact_manifest_from_anchor(anchor)
    component_hashes = _component_hashes_from_anchor(anchor)
    artifact_refs = _artifact_refs_from_manifest(manifest)
    artifact_kind_counts = _artifact_kind_counts(artifact_refs)

    anchor_status = _lower_token(anchor.get("anchorStatus")) or "missing"
    anchor_hash_present = bool(_token(anchor.get("anchorHash")))
    artifact_manifest_hash = (
        _token(component_hashes.get("artifactManifestHash"))
        or _token(manifest.get("manifestHash"))
    )
    artifact_manifest_hash_present = bool(artifact_manifest_hash)

    component_ready = {
        "caseCommitment": bool(_token(commitment.get("commitmentHash"))),
        "verdictAttestation": bool(_token(verdict.get("registryHash"))),
        "challengeReview": bool(_token(challenge.get("registryHash"))),
        "kernelVersion": bool(_token(kernel.get("registryHash"))),
        "auditAnchor": bool(anchor_hash_present and artifact_manifest_hash_present),
    }
    complete = all(component_ready.values())

    review_state = _lower_token(challenge.get("reviewState")) or "not_required"
    challenge_state = _lower_token(challenge.get("challengeState"))
    artifact_ready = bool(
        anchor_status == "artifact_ready"
        and artifact_manifest_hash_present
        and (artifact_refs or not include_artifact_refs)
    )

    artifact_coverage: dict[str, Any] = {
        "ready": artifact_ready,
        "artifactManifestHashPresent": artifact_manifest_hash_present,
        "artifactManifestHash": artifact_manifest_hash,
        "artifactRefCount": len(artifact_refs),
        "artifactKinds": sorted(artifact_kind_counts.keys()),
        "artifactKindCounts": artifact_kind_counts,
    }
    if include_artifact_refs:
        artifact_coverage["artifactRefs"] = artifact_refs

    return {
        "source": _lower_token(source) or "unknown",
        "caseId": int(case_id) if case_id is not None else None,
        "dispatchType": _lower_token(dispatch_type),
        "traceId": _token(trace_id),
        "trustCompleteness": {
            **component_ready,
            "complete": complete,
        },
        "publicVerifyStatus": {
            "verified": bool(verdict.get("verified")),
            "reason": _lower_token(verdict.get("reason")),
            "mismatchComponents": (
                [
                    str(item).strip()
                    for item in verdict.get("mismatchComponents")
                    if str(item).strip()
                ]
                if isinstance(verdict.get("mismatchComponents"), list)
                else []
            ),
        },
        "challengeReview": {
            "reviewRequired": bool(challenge.get("reviewRequired")),
            "reviewState": review_state,
            "challengeState": challenge_state,
            "totalChallenges": _safe_int(challenge.get("totalChallenges")),
        },
        "auditAnchor": {
            "anchorStatus": anchor_status,
            "anchorHashPresent": anchor_hash_present,
            "artifactManifestHashPresent": artifact_manifest_hash_present,
            "artifactManifestHash": artifact_manifest_hash,
        },
        "artifactCoverage": artifact_coverage,
    }


def build_trust_artifact_summary_from_public_verify_payload(
    *,
    public_verify_payload: dict[str, Any] | None,
    include_artifact_refs: bool = False,
) -> dict[str, Any]:
    payload = _dict_or_empty(public_verify_payload)
    verify_payload = _dict_or_empty(payload.get("verifyPayload"))
    return build_trust_artifact_summary(
        case_id=_safe_int(payload.get("caseId")) or None,
        dispatch_type=_lower_token(payload.get("dispatchType")),
        trace_id=_token(payload.get("traceId")),
        source="public_verify",
        case_commitment=_dict_or_empty(verify_payload.get("caseCommitment")),
        verdict_attestation=_dict_or_empty(verify_payload.get("verdictAttestation")),
        challenge_review=_dict_or_empty(verify_payload.get("challengeReview")),
        kernel_version=_dict_or_empty(verify_payload.get("kernelVersion")),
        audit_anchor=_dict_or_empty(verify_payload.get("auditAnchor")),
        include_artifact_refs=include_artifact_refs,
    )


def build_trust_artifact_summary_from_registry_snapshot(
    *,
    snapshot: Any,
    include_artifact_refs: bool = False,
) -> dict[str, Any]:
    normalized = snapshot.normalized() if hasattr(snapshot, "normalized") else snapshot
    payload = normalized.to_payload() if hasattr(normalized, "to_payload") else _dict_or_empty(normalized)
    return build_trust_artifact_summary(
        case_id=_safe_int(payload.get("caseId")) or None,
        dispatch_type=_lower_token(payload.get("dispatchType")),
        trace_id=_token(payload.get("traceId")),
        source="trust_registry",
        case_commitment=_dict_or_empty(payload.get("caseCommitment")),
        verdict_attestation=_dict_or_empty(payload.get("verdictAttestation")),
        challenge_review=_dict_or_empty(payload.get("challengeReview")),
        kernel_version=_dict_or_empty(payload.get("kernelVersion")),
        audit_anchor=_dict_or_empty(payload.get("auditAnchor")),
        include_artifact_refs=include_artifact_refs,
    )


def build_trust_artifact_summary_from_report_payload(
    *,
    report_payload: dict[str, Any] | None,
    case_id: int | None,
    dispatch_type: str | None,
    trace_id: str | None,
    include_artifact_refs: bool = False,
) -> dict[str, Any]:
    report = _dict_or_empty(report_payload)
    attestation = _dict_or_empty(report.get("trustAttestation"))
    component_hashes = _dict_or_empty(attestation.get("componentHashes"))
    return build_trust_artifact_summary(
        case_id=case_id,
        dispatch_type=dispatch_type or _lower_token(attestation.get("dispatchType")),
        trace_id=trace_id,
        source="report_payload",
        case_commitment={
            "commitmentHash": attestation.get("commitmentHash"),
        },
        verdict_attestation={
            "registryHash": component_hashes.get("verdictHash"),
            "verified": False,
            "reason": "registry_snapshot_missing",
        },
        challenge_review={},
        kernel_version={},
        audit_anchor={},
        include_artifact_refs=include_artifact_refs,
    )
