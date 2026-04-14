from __future__ import annotations

import hashlib
import json
from typing import Any


def _stable_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_hex(value: Any) -> str:
    return hashlib.sha256(_stable_json_bytes(value)).hexdigest()


def _build_phase_component_hashes(report_payload: dict[str, Any]) -> dict[str, str]:
    transcript_basis = {
        "sessionId": report_payload.get("sessionId"),
        "phaseNo": report_payload.get("phaseNo"),
        "messageStartId": report_payload.get("messageStartId"),
        "messageEndId": report_payload.get("messageEndId"),
        "messageCount": report_payload.get("messageCount"),
        "proSummaryGrounded": report_payload.get("proSummaryGrounded"),
        "conSummaryGrounded": report_payload.get("conSummaryGrounded"),
    }
    evidence_basis = {
        "proRetrievalBundle": report_payload.get("proRetrievalBundle"),
        "conRetrievalBundle": report_payload.get("conRetrievalBundle"),
    }
    score_basis = {
        "agent1Score": report_payload.get("agent1Score"),
        "agent2Score": report_payload.get("agent2Score"),
        "agent3WeightedScore": report_payload.get("agent3WeightedScore"),
    }
    policy_basis = {
        "judgePolicyVersion": report_payload.get("judgePolicyVersion"),
        "rubricVersion": report_payload.get("rubricVersion"),
        "policyRegistry": (
            report_payload.get("judgeTrace", {}).get("policyRegistry")
            if isinstance(report_payload.get("judgeTrace"), dict)
            else None
        ),
        "promptRegistry": (
            report_payload.get("judgeTrace", {}).get("promptRegistry")
            if isinstance(report_payload.get("judgeTrace"), dict)
            else None
        ),
        "toolRegistry": (
            report_payload.get("judgeTrace", {}).get("toolRegistry")
            if isinstance(report_payload.get("judgeTrace"), dict)
            else None
        ),
    }
    return {
        "transcriptHash": _sha256_hex(transcript_basis),
        "evidenceHash": _sha256_hex(evidence_basis),
        "scoreHash": _sha256_hex(score_basis),
        "policyHash": _sha256_hex(policy_basis),
    }


def _build_final_component_hashes(report_payload: dict[str, Any]) -> dict[str, str]:
    transcript_basis = {
        "sessionId": report_payload.get("sessionId"),
        "phaseRollupSummary": report_payload.get("phaseRollupSummary"),
    }
    evidence_basis = {
        "evidenceLedger": report_payload.get("evidenceLedger"),
        "verdictEvidenceRefs": report_payload.get("verdictEvidenceRefs"),
        "retrievalSnapshotRollup": report_payload.get("retrievalSnapshotRollup"),
    }
    claim_basis = {
        "claimGraph": report_payload.get("claimGraph"),
        "claimGraphSummary": report_payload.get("claimGraphSummary"),
    }
    verdict_basis = {
        "winner": report_payload.get("winner"),
        "proScore": report_payload.get("proScore"),
        "conScore": report_payload.get("conScore"),
        "dimensionScores": report_payload.get("dimensionScores"),
        "debateSummary": report_payload.get("debateSummary"),
        "sideAnalysis": report_payload.get("sideAnalysis"),
        "verdictReason": report_payload.get("verdictReason"),
        "rejudgeTriggered": report_payload.get("rejudgeTriggered"),
        "needsDrawVote": report_payload.get("needsDrawVote"),
    }
    fairness_basis = {
        "fairnessSummary": report_payload.get("fairnessSummary"),
        "auditAlerts": report_payload.get("auditAlerts"),
        "errorCodes": report_payload.get("errorCodes"),
        "degradationLevel": report_payload.get("degradationLevel"),
    }
    policy_basis = {
        "judgePolicyVersion": report_payload.get("judgePolicyVersion"),
        "rubricVersion": report_payload.get("rubricVersion"),
        "policyRegistry": (
            report_payload.get("judgeTrace", {}).get("policyRegistry")
            if isinstance(report_payload.get("judgeTrace"), dict)
            else None
        ),
        "promptRegistry": (
            report_payload.get("judgeTrace", {}).get("promptRegistry")
            if isinstance(report_payload.get("judgeTrace"), dict)
            else None
        ),
        "toolRegistry": (
            report_payload.get("judgeTrace", {}).get("toolRegistry")
            if isinstance(report_payload.get("judgeTrace"), dict)
            else None
        ),
    }
    return {
        "transcriptHash": _sha256_hex(transcript_basis),
        "evidenceHash": _sha256_hex(evidence_basis),
        "claimGraphHash": _sha256_hex(claim_basis),
        "verdictHash": _sha256_hex(verdict_basis),
        "fairnessHash": _sha256_hex(fairness_basis),
        "policyHash": _sha256_hex(policy_basis),
    }


def build_report_attestation(
    *,
    report_payload: dict[str, Any],
    dispatch_type: str,
) -> dict[str, Any]:
    normalized_dispatch_type = str(dispatch_type or "").strip().lower()
    if normalized_dispatch_type == "final":
        component_hashes = _build_final_component_hashes(report_payload)
    else:
        normalized_dispatch_type = "phase"
        component_hashes = _build_phase_component_hashes(report_payload)

    commitment_basis = {
        "version": "trust-attestation-v1",
        "dispatchType": normalized_dispatch_type,
        "algorithm": "sha256",
        "componentHashes": component_hashes,
    }
    return {
        **commitment_basis,
        "commitmentHash": _sha256_hex(commitment_basis),
    }


def attach_report_attestation(
    *,
    report_payload: dict[str, Any],
    dispatch_type: str,
) -> dict[str, Any]:
    attestation = build_report_attestation(
        report_payload=report_payload,
        dispatch_type=dispatch_type,
    )
    report_payload["trustAttestation"] = attestation
    return attestation


def verify_report_attestation(
    *,
    report_payload: dict[str, Any],
    dispatch_type: str,
) -> dict[str, Any]:
    existing = (
        report_payload.get("trustAttestation")
        if isinstance(report_payload.get("trustAttestation"), dict)
        else None
    )
    expected = build_report_attestation(
        report_payload=report_payload,
        dispatch_type=dispatch_type,
    )
    if existing is None:
        return {
            "verified": False,
            "reason": "trust_attestation_missing",
            "expected": expected,
            "actual": None,
        }

    mismatch_components: list[str] = []
    actual_components = (
        existing.get("componentHashes")
        if isinstance(existing.get("componentHashes"), dict)
        else {}
    )
    expected_components = expected["componentHashes"]
    for key, expected_hash in expected_components.items():
        if str(actual_components.get(key) or "").strip() != str(expected_hash):
            mismatch_components.append(key)
    if str(existing.get("commitmentHash") or "").strip() != str(expected["commitmentHash"]):
        mismatch_components.append("commitmentHash")

    return {
        "verified": not mismatch_components,
        "reason": "ok" if not mismatch_components else "trust_attestation_mismatch",
        "expected": expected,
        "actual": existing,
        "mismatchComponents": mismatch_components,
    }
