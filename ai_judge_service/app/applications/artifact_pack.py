from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.artifacts import ArtifactManifest, ArtifactRef, ArtifactStorePort, sha256_hex

CASE_ARTIFACT_KINDS: tuple[str, ...] = (
    "transcript_snapshot",
    "evidence_pack",
    "replay_snapshot",
    "audit_pack",
    "trust_registry_snapshot",
)
ARTIFACT_STORE_HEALTHCHECK_VERSION = "artifact-store-healthcheck-v1"
ARTIFACT_STORE_HEALTHCHECK_PROBE_CASE_ID = 1
ARTIFACT_STORE_HEALTHCHECK_PROBE_ARTIFACT_ID = "artifact-store-healthcheck-probe"


@dataclass(frozen=True)
class CaseArtifactPack:
    manifest: ArtifactManifest
    refs: tuple[ArtifactRef, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "manifest": self.manifest.to_payload(),
            "refs": [ref.to_payload() for ref in self.refs],
        }


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_int(value: Any) -> int | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _payload_str(value: Any) -> str | None:
    token = str(value or "").strip()
    return token or None


def build_artifact_store_readiness_payload(artifact_store: ArtifactStorePort) -> dict[str, Any]:
    readiness = getattr(artifact_store, "readiness_payload", None)
    if callable(readiness):
        payload = readiness()
        if isinstance(payload, dict):
            return dict(payload)
    return {
        "provider": "unknown",
        "status": "unknown",
        "productionReady": False,
    }


def _artifact_store_healthcheck_base(
    *,
    readiness: dict[str, Any],
) -> dict[str, Any]:
    provider = str(readiness.get("provider") or "unknown").strip() or "unknown"
    uri_scheme = str(readiness.get("uriScheme") or "").strip() or None
    return {
        "version": ARTIFACT_STORE_HEALTHCHECK_VERSION,
        "provider": provider,
        "status": "unknown",
        "uriScheme": uri_scheme,
        "bucketConfigured": bool(readiness.get("bucketConfigured")),
        "prefixConfigured": bool(readiness.get("prefixConfigured")),
        "endpointConfigured": bool(readiness.get("endpointConfigured")),
        "writeReadRoundtripStatus": "not_run",
        "lastErrorCode": None,
        "productionReady": False,
    }


def _artifact_store_healthcheck_error_code(err: Exception) -> str:
    response = getattr(err, "response", None)
    if isinstance(response, dict):
        error = response.get("Error")
        if isinstance(error, dict):
            code = _payload_str(error.get("Code"))
            if code:
                return f"artifact_store_{code.lower()}"
    token = str(err).strip().strip("'\"")
    if token:
        normalized = token.lower().replace(" ", "_").replace("-", "_")
        return normalized
    return err.__class__.__name__.lower()


async def build_artifact_store_healthcheck_payload(
    *,
    artifact_store: ArtifactStorePort,
    roundtrip_enabled: bool,
) -> dict[str, Any]:
    readiness = build_artifact_store_readiness_payload(artifact_store)
    payload = _artifact_store_healthcheck_base(readiness=readiness)
    provider = str(payload["provider"]).strip().lower()

    if provider == "local":
        payload.update(
            {
                "status": "local_reference",
                "writeReadRoundtripStatus": "not_applicable",
                "lastErrorCode": "local_provider_not_production",
                "productionReady": False,
            }
        )
        return payload

    if provider != "s3_compatible":
        payload.update(
            {
                "status": "env_blocked",
                "writeReadRoundtripStatus": "unsupported_provider",
                "lastErrorCode": "artifact_store_provider_unknown",
            }
        )
        return payload

    if not bool(payload["bucketConfigured"]):
        payload.update(
            {
                "status": "env_blocked",
                "writeReadRoundtripStatus": "configuration_missing",
                "lastErrorCode": "artifact_store_bucket_missing",
            }
        )
        return payload

    if not roundtrip_enabled:
        payload.update(
            {
                "status": "env_blocked",
                "writeReadRoundtripStatus": "not_enabled",
                "lastErrorCode": "artifact_healthcheck_not_enabled",
            }
        )
        return payload

    probe_payload = {
        "version": ARTIFACT_STORE_HEALTHCHECK_VERSION,
        "probe": "artifact_store_healthcheck",
    }
    try:
        ref = await artifact_store.put_json(
            case_id=ARTIFACT_STORE_HEALTHCHECK_PROBE_CASE_ID,
            kind="replay_snapshot",
            payload=probe_payload,
            redaction_level="redacted",
            dispatch_type="final",
            trace_id="artifact-healthcheck",
            artifact_id=ARTIFACT_STORE_HEALTHCHECK_PROBE_ARTIFACT_ID,
            metadata={"purpose": "artifact_store_healthcheck"},
        )
    except Exception as err:
        payload.update(
            {
                "status": "blocked",
                "writeReadRoundtripStatus": "put_failed",
                "lastErrorCode": _artifact_store_healthcheck_error_code(err),
            }
        )
        return payload

    if not await artifact_store.exists(ref=ref):
        payload.update(
            {
                "status": "blocked",
                "writeReadRoundtripStatus": "head_missing",
                "lastErrorCode": "artifact_healthcheck_head_missing",
            }
        )
        return payload

    try:
        stored_payload = await artifact_store.get_json(ref=ref)
    except Exception as err:
        code = _artifact_store_healthcheck_error_code(err)
        payload.update(
            {
                "status": "blocked",
                "writeReadRoundtripStatus": (
                    "sha_mismatch" if code == "artifact_sha256_mismatch" else "get_failed"
                ),
                "lastErrorCode": code,
            }
        )
        return payload

    if stored_payload != probe_payload:
        payload.update(
            {
                "status": "blocked",
                "writeReadRoundtripStatus": "payload_mismatch",
                "lastErrorCode": "artifact_healthcheck_payload_mismatch",
            }
        )
        return payload

    payload.update(
        {
            "status": "ready",
            "writeReadRoundtripStatus": "pass",
            "lastErrorCode": None,
            "productionReady": True,
        }
    )
    return payload


def _artifact_pack_metadata(
    *,
    artifact_store: ArtifactStorePort,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = dict(metadata or {})
    readiness = build_artifact_store_readiness_payload(artifact_store)
    payload["artifactStore"] = readiness
    payload.setdefault(
        "storageMode",
        "production" if readiness.get("productionReady") is True else "local_reference",
    )
    return payload


def _compact_evidence_ref(row: dict[str, Any]) -> dict[str, Any]:
    item = row.get("item")
    payload = {
        "evidenceId": _payload_str(row.get("evidenceId") or row.get("id")),
        "phaseNo": _safe_int(row.get("phaseNo") or row.get("phase_no")),
        "side": _payload_str(row.get("side")),
        "type": _payload_str(row.get("type")),
        "messageId": _safe_int(row.get("messageId") or row.get("message_id")),
        "chunkId": _payload_str(row.get("chunkId") or row.get("chunk_id")),
        "reason": _payload_str(row.get("reason")),
        "itemHash": sha256_hex(item) if item is not None else None,
    }
    return {key: value for key, value in payload.items() if value is not None}


def build_redacted_transcript_artifact(
    *,
    case_id: int,
    dispatch_type: str,
    trace_id: str,
    request_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    request = _dict_or_empty(request_snapshot)
    rows = request.get("messages") if isinstance(request.get("messages"), list) else []
    message_digest: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        message_digest.append(
            {
                "messageId": _safe_int(row.get("message_id") or row.get("messageId")),
                "side": _payload_str(row.get("side")),
                "createdAt": _payload_str(row.get("created_at") or row.get("createdAt")),
            }
        )
    return {
        "version": "trust-artifact-transcript-redacted-v1",
        "caseId": int(case_id),
        "dispatchType": str(dispatch_type or "").strip().lower(),
        "traceId": str(trace_id or "").strip(),
        "messageWindow": {
            "startId": _safe_int(request.get("message_start_id") or request.get("messageStartId")),
            "endId": _safe_int(request.get("message_end_id") or request.get("messageEndId")),
            "count": _safe_int(request.get("message_count") or request.get("messageCount")),
        },
        "messageDigest": message_digest,
        "redactionSummary": {
            "rawTextStored": False,
            "identityFieldsStored": False,
        },
    }


def build_redacted_evidence_artifact(
    *,
    case_id: int,
    dispatch_type: str,
    trace_id: str,
    report_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    report = _dict_or_empty(report_payload)
    evidence_ledger = _dict_or_empty(report.get("evidenceLedger"))
    refs_raw = report.get("verdictEvidenceRefs")
    refs = (
        [_compact_evidence_ref(item) for item in refs_raw if isinstance(item, dict)]
        if isinstance(refs_raw, list)
        else []
    )
    entries_raw = evidence_ledger.get("entries")
    entry_refs: list[dict[str, Any]] = []
    if isinstance(entries_raw, list):
        for row in entries_raw:
            if not isinstance(row, dict):
                continue
            entry_refs.append(
                {
                    "id": _payload_str(row.get("id") or row.get("evidenceId")),
                    "claimId": _payload_str(row.get("claimId") or row.get("claim_id")),
                    "sourceId": _payload_str(row.get("sourceId") or row.get("source_id")),
                }
            )
    return {
        "version": "trust-artifact-evidence-redacted-v1",
        "caseId": int(case_id),
        "dispatchType": str(dispatch_type or "").strip().lower(),
        "traceId": str(trace_id or "").strip(),
        "entryCount": len(entry_refs),
        "entries": entry_refs,
        "verdictEvidenceRefs": refs,
        "redactionSummary": {
            "rawEvidenceTextStored": False,
            "sourceMessageTextStored": False,
        },
    }


def build_replay_snapshot_artifact(
    *,
    case_id: int,
    dispatch_type: str,
    trace_id: str,
    report_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    report = _dict_or_empty(report_payload)
    return {
        "version": "trust-artifact-replay-snapshot-v1",
        "caseId": int(case_id),
        "dispatchType": str(dispatch_type or "").strip().lower(),
        "traceId": str(trace_id or "").strip(),
        "winner": _payload_str(report.get("winner")),
        "needsDrawVote": bool(report.get("needsDrawVote")),
        "reviewRequired": bool(report.get("reviewRequired")),
        "degradationLevel": _safe_int(report.get("degradationLevel")),
        "errorCodes": (
            [str(item).strip() for item in report.get("errorCodes") if str(item).strip()]
            if isinstance(report.get("errorCodes"), list)
            else []
        ),
    }


def build_audit_pack_artifact(
    *,
    case_id: int,
    dispatch_type: str,
    trace_id: str,
    challenge_review: dict[str, Any] | None,
    workflow_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    challenge = _dict_or_empty(challenge_review)
    workflow = _dict_or_empty(workflow_snapshot)
    return {
        "version": "trust-artifact-audit-pack-v1",
        "caseId": int(case_id),
        "dispatchType": str(dispatch_type or "").strip().lower(),
        "traceId": str(trace_id or "").strip(),
        "workflow": {
            "status": workflow.get("status"),
            "updatedAt": workflow.get("updatedAt"),
        },
        "challengeReview": {
            "registryHash": challenge.get("registryHash"),
            "reviewState": challenge.get("reviewState"),
            "challengeState": challenge.get("challengeState"),
            "activeChallengeId": challenge.get("activeChallengeId"),
            "totalChallenges": int(challenge.get("totalChallenges") or 0),
            "alertSummary": (
                dict(challenge.get("alertSummary"))
                if isinstance(challenge.get("alertSummary"), dict)
                else {}
            ),
        },
    }


def build_trust_registry_artifact(
    *,
    case_id: int,
    dispatch_type: str,
    trace_id: str,
    commitment: dict[str, Any],
    verdict_attestation: dict[str, Any],
    challenge_review: dict[str, Any],
    kernel_version: dict[str, Any],
) -> dict[str, Any]:
    return {
        "version": "trust-artifact-registry-summary-v1",
        "caseId": int(case_id),
        "dispatchType": str(dispatch_type or "").strip().lower(),
        "traceId": str(trace_id or "").strip(),
        "componentHashes": {
            "caseCommitmentHash": commitment.get("commitmentHash"),
            "verdictAttestationHash": verdict_attestation.get("registryHash"),
            "challengeReviewHash": challenge_review.get("registryHash"),
            "kernelVersionHash": kernel_version.get("registryHash"),
        },
        "componentVersions": {
            "caseCommitment": commitment.get("version"),
            "verdictAttestation": verdict_attestation.get("version"),
            "challengeReview": challenge_review.get("version"),
            "kernelVersion": kernel_version.get("version"),
        },
    }


async def write_case_artifact_pack(
    *,
    artifact_store: ArtifactStorePort,
    case_id: int,
    dispatch_type: str,
    trace_id: str,
    transcript_snapshot: dict[str, Any] | None = None,
    evidence_pack: dict[str, Any] | None = None,
    replay_snapshot: dict[str, Any] | None = None,
    audit_pack: dict[str, Any] | None = None,
    trust_registry_snapshot: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> CaseArtifactPack:
    sections = {
        "transcript_snapshot": _dict_or_empty(transcript_snapshot),
        "evidence_pack": _dict_or_empty(evidence_pack),
        "replay_snapshot": _dict_or_empty(replay_snapshot),
        "audit_pack": _dict_or_empty(audit_pack),
        "trust_registry_snapshot": _dict_or_empty(trust_registry_snapshot),
    }
    refs: list[ArtifactRef] = []
    for kind in CASE_ARTIFACT_KINDS:
        payload = sections[kind]
        if not payload:
            continue
        ref = await artifact_store.put_json(
            case_id=case_id,
            kind=kind,
            payload=payload,
            redaction_level="ops" if kind == "audit_pack" else "redacted",
            dispatch_type=dispatch_type,
            trace_id=trace_id,
            metadata={
                "caseId": int(case_id),
                "dispatchType": str(dispatch_type or "").strip().lower(),
                "traceId": str(trace_id or "").strip(),
            },
        )
        refs.append(ref)
    manifest = artifact_store.build_manifest(
        case_id=case_id,
        dispatch_type=dispatch_type,
        trace_id=trace_id,
        refs=refs,
        metadata=_artifact_pack_metadata(
            artifact_store=artifact_store,
            metadata=metadata,
        ),
    )
    return CaseArtifactPack(manifest=manifest, refs=tuple(refs))


async def write_trust_audit_artifact_pack(
    *,
    artifact_store: ArtifactStorePort,
    case_id: int,
    dispatch_type: str,
    trace_id: str,
    request_snapshot: dict[str, Any] | None,
    report_payload: dict[str, Any] | None,
    workflow_snapshot: dict[str, Any] | None,
    commitment: dict[str, Any],
    verdict_attestation: dict[str, Any],
    challenge_review: dict[str, Any],
    kernel_version: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> CaseArtifactPack:
    return await write_case_artifact_pack(
        artifact_store=artifact_store,
        case_id=case_id,
        dispatch_type=dispatch_type,
        trace_id=trace_id,
        transcript_snapshot=build_redacted_transcript_artifact(
            case_id=case_id,
            dispatch_type=dispatch_type,
            trace_id=trace_id,
            request_snapshot=request_snapshot,
        ),
        evidence_pack=build_redacted_evidence_artifact(
            case_id=case_id,
            dispatch_type=dispatch_type,
            trace_id=trace_id,
            report_payload=report_payload,
        ),
        replay_snapshot=build_replay_snapshot_artifact(
            case_id=case_id,
            dispatch_type=dispatch_type,
            trace_id=trace_id,
            report_payload=report_payload,
        ),
        audit_pack=build_audit_pack_artifact(
            case_id=case_id,
            dispatch_type=dispatch_type,
            trace_id=trace_id,
            challenge_review=challenge_review,
            workflow_snapshot=workflow_snapshot,
        ),
        trust_registry_snapshot=build_trust_registry_artifact(
            case_id=case_id,
            dispatch_type=dispatch_type,
            trace_id=trace_id,
            commitment=commitment,
            verdict_attestation=verdict_attestation,
            challenge_review=challenge_review,
            kernel_version=kernel_version,
        ),
        metadata={
            "source": "trust_audit_anchor_export",
            **dict(metadata or {}),
        },
    )
