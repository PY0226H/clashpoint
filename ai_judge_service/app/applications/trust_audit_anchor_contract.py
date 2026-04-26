from __future__ import annotations

from typing import Any

TRUST_AUDIT_ANCHOR_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "caseId",
    "dispatchType",
    "traceId",
    "item",
)

TRUST_AUDIT_ANCHOR_ITEM_KEYS: tuple[str, ...] = (
    "version",
    "caseId",
    "dispatchType",
    "traceId",
    "anchorStatus",
    "componentHashes",
    "anchorHash",
    "artifactManifest",
)

TRUST_AUDIT_ANCHOR_BASE_COMPONENT_HASH_KEYS: tuple[str, ...] = (
    "caseCommitmentHash",
    "verdictAttestationHash",
    "challengeReviewHash",
    "kernelVersionHash",
)

TRUST_AUDIT_ANCHOR_COMPONENT_HASH_KEYS: tuple[str, ...] = (
    *TRUST_AUDIT_ANCHOR_BASE_COMPONENT_HASH_KEYS,
    "artifactManifestHash",
)
TRUST_AUDIT_ANCHOR_OPTIONAL_COMPONENT_HASH_KEYS: tuple[str, ...] = (
    "releaseReadinessManifestHash",
)

TRUST_AUDIT_ANCHOR_PAYLOAD_KEYS: tuple[str, ...] = (
    "caseCommitment",
    "verdictAttestation",
    "challengeReview",
    "kernelVersion",
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


def validate_trust_audit_anchor_contract(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("trust_audit_anchor_payload_not_dict")
    _assert_required_keys(
        section="trust_audit_anchor",
        payload=payload,
        keys=TRUST_AUDIT_ANCHOR_TOP_LEVEL_KEYS,
    )
    case_id = _non_negative_int(payload.get("caseId"), default=0)
    if case_id <= 0:
        raise ValueError("trust_audit_anchor_case_id_invalid")
    dispatch_type = str(payload.get("dispatchType") or "").strip().lower()
    if dispatch_type not in {"phase", "final"}:
        raise ValueError("trust_audit_anchor_dispatch_type_invalid")
    _assert_non_empty_string("trust_audit_anchor_trace_id", payload.get("traceId"))

    item = payload.get("item")
    if not isinstance(item, dict):
        raise ValueError("trust_audit_anchor_item_not_dict")
    _assert_required_keys(
        section="trust_audit_anchor_item",
        payload=item,
        keys=TRUST_AUDIT_ANCHOR_ITEM_KEYS,
    )
    if _non_negative_int(item.get("caseId"), default=0) != case_id:
        raise ValueError("trust_audit_anchor_item_case_id_mismatch")
    if str(item.get("dispatchType") or "").strip().lower() != dispatch_type:
        raise ValueError("trust_audit_anchor_item_dispatch_type_mismatch")
    if str(item.get("traceId") or "").strip() != str(payload.get("traceId") or "").strip():
        raise ValueError("trust_audit_anchor_item_trace_id_mismatch")
    _assert_non_empty_string("trust_audit_anchor_item_version", item.get("version"))
    anchor_status = str(item.get("anchorStatus") or "").strip().lower()
    if anchor_status not in {"artifact_ready", "artifact_pending"}:
        raise ValueError("trust_audit_anchor_item_anchor_status_invalid")

    component_hashes = item.get("componentHashes")
    if not isinstance(component_hashes, dict):
        raise ValueError("trust_audit_anchor_component_hashes_not_dict")
    _assert_required_keys(
        section="trust_audit_anchor_component_hashes",
        payload=component_hashes,
        keys=TRUST_AUDIT_ANCHOR_BASE_COMPONENT_HASH_KEYS,
    )
    for key in TRUST_AUDIT_ANCHOR_BASE_COMPONENT_HASH_KEYS:
        _assert_non_empty_string(
            f"trust_audit_anchor_component_hashes_{key}",
            component_hashes.get(key),
        )
    artifact_manifest = item.get("artifactManifest")
    if anchor_status == "artifact_ready":
        _assert_non_empty_string("trust_audit_anchor_item_anchor_hash", item.get("anchorHash"))
        _assert_required_keys(
            section="trust_audit_anchor_component_hashes",
            payload=component_hashes,
            keys=("artifactManifestHash",),
        )
        _assert_non_empty_string(
            "trust_audit_anchor_component_hashes_artifactManifestHash",
            component_hashes.get("artifactManifestHash"),
        )
        if not isinstance(artifact_manifest, dict):
            raise ValueError("trust_audit_anchor_artifact_manifest_not_dict")
        if (
            str(artifact_manifest.get("manifestHash") or "").strip()
            != str(component_hashes.get("artifactManifestHash") or "").strip()
        ):
            raise ValueError("trust_audit_anchor_artifact_manifest_hash_mismatch")
        release_readiness_manifest_hash = str(
            component_hashes.get("releaseReadinessManifestHash") or ""
        ).strip()
        if release_readiness_manifest_hash:
            release_summary = artifact_manifest.get("releaseReadinessArtifactSummary")
            if isinstance(release_summary, dict):
                summary_manifest_hash = str(release_summary.get("manifestHash") or "").strip()
                if summary_manifest_hash and summary_manifest_hash != release_readiness_manifest_hash:
                    raise ValueError(
                        "trust_audit_anchor_release_readiness_manifest_hash_mismatch"
                    )
    else:
        if str(item.get("anchorHash") or "").strip():
            raise ValueError("trust_audit_anchor_pending_anchor_hash_forbidden")
        if str(component_hashes.get("artifactManifestHash") or "").strip():
            raise ValueError("trust_audit_anchor_pending_artifact_manifest_hash_forbidden")
        if str(component_hashes.get("releaseReadinessManifestHash") or "").strip():
            raise ValueError(
                "trust_audit_anchor_pending_release_readiness_manifest_hash_forbidden"
            )
        if isinstance(artifact_manifest, dict) and artifact_manifest:
            raise ValueError("trust_audit_anchor_pending_artifact_manifest_forbidden")

    if "payload" in item:
        item_payload = item.get("payload")
        if not isinstance(item_payload, dict):
            raise ValueError("trust_audit_anchor_payload_not_dict")
        _assert_required_keys(
            section="trust_audit_anchor_payload",
            payload=item_payload,
            keys=TRUST_AUDIT_ANCHOR_PAYLOAD_KEYS,
        )
        for key in TRUST_AUDIT_ANCHOR_PAYLOAD_KEYS:
            if not isinstance(item_payload.get(key), dict):
                raise ValueError(f"trust_audit_anchor_payload_{key}_not_dict")
