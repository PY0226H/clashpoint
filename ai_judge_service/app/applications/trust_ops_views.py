from __future__ import annotations

from typing import Any


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
            "kernelVector": (
                dict(kernel_version.get("kernelVector"))
                if isinstance(kernel_version.get("kernelVector"), dict)
                else {}
            ),
        },
        "auditAnchor": {
            "version": audit_anchor.get("version"),
            "anchorHash": audit_anchor.get("anchorHash"),
            "componentHashes": (
                dict(audit_anchor.get("componentHashes"))
                if isinstance(audit_anchor.get("componentHashes"), dict)
                else {}
            ),
        },
    }


def build_trust_challenge_ops_queue_item(
    *,
    case_id: int,
    dispatch_type: str | None,
    trace_id: str | None,
    workflow: dict[str, Any],
    trace_payload: dict[str, Any],
    challenge_review: dict[str, Any],
    priority_profile: dict[str, Any],
    active_challenge_id: str | None,
) -> dict[str, Any]:
    workflow_status = str(workflow.get("status") or "").strip().lower() or None
    current_review_state = str(challenge_review.get("reviewState") or "").strip().lower() or None
    return {
        "caseId": int(case_id),
        "dispatchType": dispatch_type,
        "traceId": trace_id or None,
        "workflow": dict(workflow),
        "trace": dict(trace_payload),
        "challengeReview": {
            "state": str(challenge_review.get("challengeState") or "").strip().lower() or None,
            "activeChallengeId": active_challenge_id,
            "totalChallenges": int(challenge_review.get("totalChallenges") or 0),
            "reviewState": current_review_state,
            "reviewRequired": bool(challenge_review.get("reviewRequired")),
            "challengeReasons": (
                challenge_review.get("challengeReasons")
                if isinstance(challenge_review.get("challengeReasons"), list)
                else []
            ),
            "alertSummary": (
                challenge_review.get("alertSummary")
                if isinstance(challenge_review.get("alertSummary"), dict)
                else {}
            ),
            "openAlertIds": (
                challenge_review.get("openAlertIds")
                if isinstance(challenge_review.get("openAlertIds"), list)
                else []
            ),
            "timeline": (
                challenge_review.get("timeline")
                if isinstance(challenge_review.get("timeline"), list)
                else []
            ),
        },
        "priorityProfile": dict(priority_profile),
        "review": {
            "required": bool(challenge_review.get("reviewRequired")),
            "state": current_review_state,
            "workflowStatus": workflow_status,
            "detailPath": f"/internal/judge/review/cases/{int(case_id)}",
        },
        "actionHints": [],
        "actionPaths": {
            "requestChallengePath": f"/internal/judge/cases/{int(case_id)}/trust/challenges/request",
            "decisionPath": (
                f"/internal/judge/cases/{int(case_id)}/trust/challenges/{active_challenge_id}/decision"
                if active_challenge_id is not None
                else None
            ),
            "reviewDetailPath": f"/internal/judge/review/cases/{int(case_id)}",
        },
    }


def build_trust_challenge_ops_queue_payload(
    *,
    items: list[dict[str, Any]],
    page_items: list[dict[str, Any]],
    jobs_count: int,
    errors: list[dict[str, Any]],
    filters: dict[str, Any],
) -> dict[str, Any]:
    count = len(items)
    payload = {
        "count": count,
        "returned": len(page_items),
        "scanned": int(jobs_count),
        "skipped": max(0, int(jobs_count) - count),
        "errorCount": len(errors),
        "items": page_items,
        "errors": errors,
        "filters": dict(filters),
    }
    return payload
