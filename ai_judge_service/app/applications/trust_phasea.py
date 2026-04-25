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


CHALLENGE_STATE_NOT_CHALLENGED = "not_challenged"
CHALLENGE_STATE_REQUESTED = "challenge_requested"
CHALLENGE_STATE_ACCEPTED = "challenge_accepted"
CHALLENGE_STATE_UNDER_REVIEW = "under_internal_review"
CHALLENGE_STATE_VERDICT_UPHELD = "verdict_upheld"
CHALLENGE_STATE_VERDICT_OVERTURNED = "verdict_overturned"
CHALLENGE_STATE_DRAW_AFTER_REVIEW = "draw_after_review"
CHALLENGE_STATE_REVIEW_RETAINED = "review_retained"
CHALLENGE_STATE_CLOSED = "challenge_closed"

_CHALLENGE_OPEN_STATES = {
    CHALLENGE_STATE_REQUESTED,
    CHALLENGE_STATE_ACCEPTED,
    CHALLENGE_STATE_UNDER_REVIEW,
}
_CHALLENGE_DECISION_STATES = {
    CHALLENGE_STATE_VERDICT_UPHELD,
    CHALLENGE_STATE_VERDICT_OVERTURNED,
    CHALLENGE_STATE_DRAW_AFTER_REVIEW,
    CHALLENGE_STATE_REVIEW_RETAINED,
}
_CHALLENGE_VALID_STATES = (
    _CHALLENGE_OPEN_STATES
    | _CHALLENGE_DECISION_STATES
    | {CHALLENGE_STATE_CLOSED}
)


def _safe_iso(value: Any) -> str | None:
    if value is None:
        return None
    iso_fn = getattr(value, "isoformat", None)
    if callable(iso_fn):
        try:
            return str(iso_fn())
        except Exception:
            return None
    return None


def _extract_challenge_timeline(
    *,
    workflow_events: list[Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    timeline: list[dict[str, Any]] = []
    review_decisions: list[dict[str, Any]] = []
    for event in workflow_events:
        payload = event.payload if isinstance(getattr(event, "payload", None), dict) else {}
        event_seq = int(getattr(event, "event_seq", 0) or 0)
        created_at = _safe_iso(getattr(event, "created_at", None))
        challenge_id = str(payload.get("challengeId") or "").strip()
        challenge_state = str(payload.get("challengeState") or "").strip().lower()
        if challenge_id and challenge_state in _CHALLENGE_VALID_STATES:
            timeline.append(
                {
                    "eventSeq": event_seq,
                    "challengeId": challenge_id,
                    "state": challenge_state,
                    "actor": str(
                        payload.get("challengeActor")
                        or payload.get("challengeRequestedBy")
                        or payload.get("challengeAcceptedBy")
                        or payload.get("challengeDecisionBy")
                        or payload.get("challengeClosedBy")
                        or payload.get("reviewActor")
                        or ""
                    ).strip()
                    or None,
                    "reasonCode": str(payload.get("challengeReasonCode") or "").strip() or None,
                    "reason": str(
                        payload.get("challengeReason")
                        or payload.get("challengeDecisionReason")
                        or payload.get("challengeCloseReason")
                        or payload.get("reviewReason")
                        or ""
                    ).strip()
                    or None,
                    "createdAt": created_at,
                }
            )

        decision = str(payload.get("reviewDecision") or "").strip().lower()
        if decision in {"approve", "reject"}:
            review_decisions.append(
                {
                    "eventSeq": event_seq,
                    "decision": decision,
                    "actor": str(payload.get("reviewActor") or "").strip() or None,
                    "reason": str(payload.get("reviewReason") or "").strip() or None,
                    "createdAt": created_at,
                }
            )
    timeline.sort(
        key=lambda row: (
            int(row.get("eventSeq") or 0),
            str(row.get("createdAt") or ""),
        )
    )
    return timeline, review_decisions


def _build_challenge_entries(
    *,
    timeline: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str | None, str]:
    entries_by_id: dict[str, dict[str, Any]] = {}

    for row in timeline:
        challenge_id = str(row.get("challengeId") or "").strip()
        if not challenge_id:
            continue
        state = str(row.get("state") or "").strip().lower()
        event_seq = int(row.get("eventSeq") or 0)
        actor = str(row.get("actor") or "").strip() or None
        reason_code = str(row.get("reasonCode") or "").strip() or None
        reason = str(row.get("reason") or "").strip() or None
        created_at = str(row.get("createdAt") or "").strip() or None

        entry = entries_by_id.get(challenge_id)
        if entry is None:
            entry = {
                "challengeId": challenge_id,
                "currentState": state,
                "reasonCode": reason_code,
                "reason": reason,
                "requestedBy": None,
                "requestedAt": None,
                "acceptedBy": None,
                "acceptedAt": None,
                "reviewStartedAt": None,
                "decision": None,
                "decisionBy": None,
                "decisionReason": None,
                "decisionAt": None,
                "closedBy": None,
                "closedAt": None,
                "latestEventSeq": event_seq,
                "stateHistory": [],
            }
            entries_by_id[challenge_id] = entry

        if reason_code and not entry.get("reasonCode"):
            entry["reasonCode"] = reason_code
        if reason and not entry.get("reason"):
            entry["reason"] = reason

        entry["currentState"] = state
        entry["latestEventSeq"] = max(int(entry.get("latestEventSeq") or 0), event_seq)
        entry["stateHistory"].append(
            {
                "eventSeq": event_seq,
                "state": state,
                "actor": actor,
                "reasonCode": reason_code,
                "reason": reason,
                "createdAt": created_at,
            }
        )

        if state == CHALLENGE_STATE_REQUESTED:
            if created_at and not entry.get("requestedAt"):
                entry["requestedAt"] = created_at
            if actor and not entry.get("requestedBy"):
                entry["requestedBy"] = actor
        elif state == CHALLENGE_STATE_ACCEPTED:
            if created_at and not entry.get("acceptedAt"):
                entry["acceptedAt"] = created_at
            if actor and not entry.get("acceptedBy"):
                entry["acceptedBy"] = actor
        elif state == CHALLENGE_STATE_UNDER_REVIEW:
            if created_at and not entry.get("reviewStartedAt"):
                entry["reviewStartedAt"] = created_at
        elif state in _CHALLENGE_DECISION_STATES:
            entry["decision"] = state
            if created_at:
                entry["decisionAt"] = created_at
            if actor:
                entry["decisionBy"] = actor
            if reason:
                entry["decisionReason"] = reason
        elif state == CHALLENGE_STATE_CLOSED:
            if created_at:
                entry["closedAt"] = created_at
            if actor:
                entry["closedBy"] = actor

    entries = list(entries_by_id.values())
    entries.sort(
        key=lambda row: (
            -int(row.get("latestEventSeq") or 0),
            str(row.get("challengeId") or ""),
        )
    )

    active_challenge_id: str | None = None
    for row in entries:
        if str(row.get("currentState") or "") in _CHALLENGE_OPEN_STATES:
            active_challenge_id = str(row.get("challengeId") or "")
            break

    if active_challenge_id:
        challenge_state = str(
            next(
                (
                    item.get("currentState")
                    for item in entries
                    if str(item.get("challengeId") or "") == active_challenge_id
                ),
                CHALLENGE_STATE_NOT_CHALLENGED,
            )
        )
    elif entries:
        challenge_state = str(entries[0].get("currentState") or CHALLENGE_STATE_NOT_CHALLENGED)
    else:
        challenge_state = CHALLENGE_STATE_NOT_CHALLENGED
    return entries, active_challenge_id, challenge_state


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
    timeline, review_decisions = _extract_challenge_timeline(workflow_events=workflow_events)
    challenge_entries, active_challenge_id, challenge_state = _build_challenge_entries(
        timeline=timeline
    )

    approved = False
    rejected = False
    for row in review_decisions:
        decision = str(row.get("decision") or "").strip().lower()
        if decision == "approve":
            approved = True
        if decision == "reject":
            rejected = True
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
        "version": "trust-phaseB-challenge-review-v1",
        "caseId": int(case_id),
        "traceId": str(trace_id or "").strip(),
        "challengeState": challenge_state,
        "activeChallengeId": active_challenge_id,
        "totalChallenges": len(challenge_entries),
        "challenges": challenge_entries,
        "timeline": timeline,
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
    artifact_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest_payload = artifact_manifest if isinstance(artifact_manifest, dict) else {}
    artifact_manifest_hash = str(manifest_payload.get("manifestHash") or "").strip()
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
    if artifact_manifest_hash:
        component_hashes["artifactManifestHash"] = artifact_manifest_hash
    anchor_status = "artifact_ready" if artifact_manifest_hash else "artifact_pending"
    anchor_basis = {
        "version": "trust-phaseA-audit-anchor-v1",
        "caseId": int(case_id),
        "dispatchType": _normalize_dispatch_type(dispatch_type),
        "traceId": str(trace_id or "").strip(),
        "anchorStatus": anchor_status,
        "componentHashes": component_hashes,
    }
    payload: dict[str, Any] = {
        **anchor_basis,
        "anchorHash": _sha256_hex(anchor_basis) if artifact_manifest_hash else None,
        "artifactManifest": dict(manifest_payload) if artifact_manifest_hash else None,
    }
    if include_payload:
        payload["payload"] = {
            "caseCommitment": case_commitment,
            "verdictAttestation": verdict_attestation,
            "challengeReview": challenge_review,
            "kernelVersion": kernel_version,
        }
        if artifact_manifest_hash:
            payload["payload"]["artifactManifest"] = dict(manifest_payload)
    return payload
