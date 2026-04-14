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


def _normalize_dispatch_type(value: Any) -> str:
    token = str(value or "").strip().lower()
    if token in {"phase", "final"}:
        return token
    return "unknown"


def build_case_commitment_registry(
    *,
    case_id: int,
    dispatch_type: str,
    trace_id: str,
    request_snapshot: dict[str, Any] | None,
    workflow_snapshot: dict[str, Any] | None,
    report_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    request_payload = request_snapshot if isinstance(request_snapshot, dict) else {}
    workflow_payload = workflow_snapshot if isinstance(workflow_snapshot, dict) else {}
    report = report_payload if isinstance(report_payload, dict) else {}
    attestation = report.get("trustAttestation") if isinstance(report.get("trustAttestation"), dict) else {}

    request_hash = _sha256_hex(request_payload)
    workflow_hash = _sha256_hex(workflow_payload)
    report_hash = _sha256_hex(
        {
            "winner": report.get("winner"),
            "proScore": report.get("proScore"),
            "conScore": report.get("conScore"),
            "degradationLevel": report.get("degradationLevel"),
        }
    )
    commitment_basis = {
        "version": "trust-phaseA-case-commitment-v1",
        "caseId": int(case_id),
        "dispatchType": _normalize_dispatch_type(dispatch_type),
        "traceId": str(trace_id or "").strip(),
        "requestHash": request_hash,
        "workflowHash": workflow_hash,
        "reportHash": report_hash,
        "attestationCommitmentHash": str(attestation.get("commitmentHash") or "").strip() or None,
    }
    commitment_hash = _sha256_hex(commitment_basis)
    return {
        **commitment_basis,
        "commitmentHash": commitment_hash,
    }


def build_verdict_attestation_registry(
    *,
    case_id: int,
    dispatch_type: str,
    trace_id: str,
    report_payload: dict[str, Any] | None,
    verify_result: dict[str, Any] | None,
) -> dict[str, Any]:
    report = report_payload if isinstance(report_payload, dict) else {}
    attestation = report.get("trustAttestation") if isinstance(report.get("trustAttestation"), dict) else {}
    verify_payload = verify_result if isinstance(verify_result, dict) else {}
    mismatch_components = verify_payload.get("mismatchComponents")
    if not isinstance(mismatch_components, list):
        mismatch_components = []
    registry_basis = {
        "version": "trust-phaseA-verdict-attestation-v1",
        "caseId": int(case_id),
        "dispatchType": _normalize_dispatch_type(dispatch_type),
        "traceId": str(trace_id or "").strip(),
        "attestation": dict(attestation),
        "verified": bool(verify_payload.get("verified")),
        "reason": str(verify_payload.get("reason") or "").strip() or None,
        "mismatchComponents": [str(item).strip() for item in mismatch_components if str(item).strip()],
    }
    registry_hash = _sha256_hex(registry_basis)
    return {
        **registry_basis,
        "registryHash": registry_hash,
    }


def build_challenge_review_registry(
    *,
    case_id: int,
    trace_id: str,
    workflow_status: str | None,
    workflow_events: list[Any],
    alerts: list[Any],
    report_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    report = report_payload if isinstance(report_payload, dict) else {}
    review_decisions: list[dict[str, Any]] = []
    approved = False
    rejected = False
    for event in workflow_events:
        payload = event.payload if isinstance(getattr(event, "payload", None), dict) else {}
        decision = str(payload.get("reviewDecision") or "").strip().lower()
        if decision not in {"approve", "reject"}:
            continue
        if decision == "approve":
            approved = True
        if decision == "reject":
            rejected = True
        review_decisions.append(
            {
                "eventSeq": int(getattr(event, "event_seq", 0) or 0),
                "decision": decision,
                "actor": str(payload.get("reviewActor") or "").strip() or None,
                "reason": str(payload.get("reviewReason") or "").strip() or None,
                "createdAt": (
                    getattr(event, "created_at", None).isoformat()
                    if getattr(event, "created_at", None) is not None
                    else None
                ),
            }
        )
    normalized_status = str(workflow_status or "").strip().lower()
    if normalized_status == "review_required":
        review_state = "pending_review"
    elif rejected or normalized_status == "blocked_failed":
        review_state = "rejected"
    elif approved or normalized_status == "callback_reported":
        review_state = "approved"
    else:
        review_state = "not_required"

    alert_summary = {
        "total": 0,
        "raised": 0,
        "acked": 0,
        "resolved": 0,
        "critical": 0,
        "warning": 0,
    }
    open_alert_ids: list[str] = []
    alert_types: list[str] = []
    for row in alerts:
        alert_summary["total"] += 1
        status = str(getattr(row, "status", "") or "").strip().lower()
        severity = str(getattr(row, "severity", "") or "").strip().lower()
        alert_type = str(getattr(row, "alert_type", "") or "").strip()
        alert_id = str(getattr(row, "alert_id", "") or "").strip()
        if status in alert_summary:
            alert_summary[status] += 1
        if severity in {"critical", "warning"}:
            alert_summary[severity] += 1
        if status in {"raised", "acked"} and alert_id:
            open_alert_ids.append(alert_id)
        if alert_type and alert_type not in alert_types:
            alert_types.append(alert_type)

    challenge_reasons: list[str] = []
    error_codes = report.get("errorCodes")
    if isinstance(error_codes, list):
        for row in error_codes:
            token = str(row).strip()
            if token and token not in challenge_reasons:
                challenge_reasons.append(token)
    for token in alert_types:
        if token not in challenge_reasons:
            challenge_reasons.append(token)

    registry_basis = {
        "version": "trust-phaseA-challenge-review-v1",
        "caseId": int(case_id),
        "traceId": str(trace_id or "").strip(),
        "reviewState": review_state,
        "reviewRequired": bool(report.get("reviewRequired")),
        "reviewDecisions": review_decisions,
        "challengeReasons": challenge_reasons,
        "alertSummary": alert_summary,
        "openAlertIds": open_alert_ids,
    }
    return {
        **registry_basis,
        "registryHash": _sha256_hex(registry_basis),
    }


def build_judge_kernel_registry(
    *,
    case_id: int,
    dispatch_type: str,
    trace_id: str,
    report_payload: dict[str, Any] | None,
    workflow_events: list[Any],
    provider: str,
) -> dict[str, Any]:
    report = report_payload if isinstance(report_payload, dict) else {}
    judge_trace = report.get("judgeTrace") if isinstance(report.get("judgeTrace"), dict) else {}
    registry_versions = (
        judge_trace.get("registryVersions")
        if isinstance(judge_trace.get("registryVersions"), dict)
        else {}
    )
    latest_judge_core_version: str | None = None
    for event in reversed(workflow_events):
        payload = event.payload if isinstance(getattr(event, "payload", None), dict) else {}
        token = str(payload.get("judgeCoreVersion") or "").strip()
        if token:
            latest_judge_core_version = token
            break
    kernel_vector = {
        "dispatchType": _normalize_dispatch_type(dispatch_type),
        "provider": str(provider or "").strip() or "unknown",
        "judgeCoreVersion": latest_judge_core_version,
        "pipelineVersion": str(judge_trace.get("pipelineVersion") or "").strip() or None,
        "policyVersion": (
            str(registry_versions.get("policyVersion") or "").strip()
            or str(judge_trace.get("policyRegistry", {}).get("version") or "").strip()
            or None
        ),
        "promptVersion": (
            str(registry_versions.get("promptVersion") or "").strip()
            or str(judge_trace.get("promptRegistry", {}).get("version") or "").strip()
            or None
        ),
        "toolsetVersion": (
            str(registry_versions.get("toolsetVersion") or "").strip()
            or str(judge_trace.get("toolRegistry", {}).get("version") or "").strip()
            or None
        ),
        "agentRuntimeVersion": (
            str(judge_trace.get("agentRuntime", {}).get("runtimeVersion") or "").strip() or None
        ),
    }
    registry_basis = {
        "version": "trust-phaseA-kernel-version-v1",
        "caseId": int(case_id),
        "traceId": str(trace_id or "").strip(),
        "kernelVector": kernel_vector,
    }
    return {
        **registry_basis,
        "kernelHash": _sha256_hex(kernel_vector),
        "registryHash": _sha256_hex(registry_basis),
    }


def build_audit_anchor_export(
    *,
    case_id: int,
    dispatch_type: str,
    trace_id: str,
    case_commitment: dict[str, Any],
    verdict_attestation: dict[str, Any],
    challenge_review: dict[str, Any],
    kernel_version: dict[str, Any],
    include_payload: bool,
) -> dict[str, Any]:
    component_hashes = {
        "caseCommitmentHash": str(case_commitment.get("commitmentHash") or "").strip()
        or _sha256_hex(case_commitment),
        "verdictAttestationHash": str(verdict_attestation.get("registryHash") or "").strip()
        or _sha256_hex(verdict_attestation),
        "challengeReviewHash": str(challenge_review.get("registryHash") or "").strip()
        or _sha256_hex(challenge_review),
        "kernelVersionHash": str(kernel_version.get("registryHash") or "").strip()
        or _sha256_hex(kernel_version),
    }
    anchor_basis = {
        "version": "trust-phaseA-audit-anchor-v1",
        "caseId": int(case_id),
        "dispatchType": _normalize_dispatch_type(dispatch_type),
        "traceId": str(trace_id or "").strip(),
        "componentHashes": component_hashes,
    }
    anchor_hash = _sha256_hex(anchor_basis)
    payload: dict[str, Any] = {
        **anchor_basis,
        "anchorHash": anchor_hash,
    }
    if include_payload:
        payload["payload"] = {
            "caseCommitment": case_commitment,
            "verdictAttestation": verdict_attestation,
            "challengeReview": challenge_review,
            "kernelVersion": kernel_version,
        }
    return payload
