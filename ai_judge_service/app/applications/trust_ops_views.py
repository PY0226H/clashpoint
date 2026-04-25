from __future__ import annotations

from datetime import datetime
from typing import Any

from .trust_public_verify_contract import TRUST_PUBLIC_VERIFY_KERNEL_VECTOR_PUBLIC_KEYS


def _build_public_kernel_vector(payload: dict[str, Any]) -> dict[str, Any]:
    kernel_vector = payload.get("kernelVector")
    if not isinstance(kernel_vector, dict):
        return {}
    return {
        key: kernel_vector.get(key)
        for key in TRUST_PUBLIC_VERIFY_KERNEL_VECTOR_PUBLIC_KEYS
        if kernel_vector.get(key) is not None
    }


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
            "kernelVector": _build_public_kernel_vector(kernel_version),
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


def normalize_trust_challenge_state_filter(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized or normalized == "all":
        return None
    return normalized


def normalize_trust_challenge_review_state(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    return normalized


def normalize_trust_challenge_priority_level(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    return normalized


def normalize_trust_challenge_sla_bucket(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    return normalized


def normalize_trust_challenge_sort_by(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "priority_score"
    return normalized


def normalize_trust_challenge_sort_order(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "desc"
    return normalized


def build_trust_challenge_priority_profile(
    *,
    workflow: Any,
    challenge_review: dict[str, Any],
    report_payload: dict[str, Any],
    report_summary: dict[str, Any],
    now: datetime,
    normalize_query_datetime: Any,
    trust_challenge_open_states: set[str] | frozenset[str],
) -> dict[str, Any]:
    review = challenge_review if isinstance(challenge_review, dict) else {}
    payload = report_payload if isinstance(report_payload, dict) else {}
    summary = report_summary if isinstance(report_summary, dict) else {}
    fairness_summary = (
        payload.get("fairnessSummary")
        if isinstance(payload.get("fairnessSummary"), dict)
        else {}
    )

    challenge_state = str(review.get("challengeState") or "").strip().lower()
    review_state = str(review.get("reviewState") or "").strip().lower()
    total_challenges_raw = review.get("totalChallenges")
    try:
        total_challenges = max(0, int(total_challenges_raw))
    except (TypeError, ValueError):
        total_challenges = 0
    open_alert_ids = (
        review.get("openAlertIds")
        if isinstance(review.get("openAlertIds"), list)
        else []
    )
    open_alert_count = len(open_alert_ids)
    alert_summary = (
        review.get("alertSummary")
        if isinstance(review.get("alertSummary"), dict)
        else {}
    )
    critical_alert_count = int(alert_summary.get("critical") or 0)
    challenge_reasons = (
        review.get("challengeReasons")
        if isinstance(review.get("challengeReasons"), list)
        else []
    )

    age_minutes: int | None = None
    workflow_updated_at = getattr(workflow, "updated_at", None)
    if isinstance(workflow_updated_at, datetime):
        updated_at = normalize_query_datetime(workflow_updated_at)
        if updated_at is not None:
            age_delta = now - updated_at
            age_minutes = max(0, int(age_delta.total_seconds() // 60))

    risk_score = 0
    risk_tags: list[str] = []
    if challenge_state in trust_challenge_open_states:
        risk_score += 35
        risk_tags.append("open_challenge")
    if review_state == "pending_review":
        risk_score += 20
        risk_tags.append("pending_review")
    if bool(review.get("reviewRequired")):
        risk_score += 10
        risk_tags.append("review_required")
    if total_challenges >= 2:
        risk_score += min(15, (total_challenges - 1) * 5)
        risk_tags.append("multi_challenge_case")
    if open_alert_count > 0:
        risk_score += min(20, open_alert_count * 4)
        risk_tags.append("open_alerts_present")
    if critical_alert_count > 0:
        risk_score += 10
        risk_tags.append("critical_alert_present")
    if str(summary.get("callbackStatus") or "").strip().lower() in {
        "failed",
        "error",
        "callback_failed",
        "blocked_failed_reported",
    }:
        risk_score += 12
        risk_tags.append("callback_failed")
    if bool(fairness_summary.get("panelHighDisagreement")):
        risk_score += 8
        risk_tags.append("panel_high_disagreement")
    if len([item for item in challenge_reasons if str(item).strip()]) >= 3:
        risk_score += 5
        risk_tags.append("multi_reason_challenge")
    if age_minutes is not None and age_minutes >= 360:
        risk_score += 15
        risk_tags.append("challenge_stale_6h")
    elif age_minutes is not None and age_minutes >= 120:
        risk_score += 8
        risk_tags.append("challenge_stale_2h")

    risk_score = max(0, min(int(risk_score), 100))
    if risk_score >= 75:
        risk_level = "high"
    elif risk_score >= 45:
        risk_level = "medium"
    else:
        risk_level = "low"

    if age_minutes is None:
        sla_bucket = "unknown"
    elif age_minutes >= 360:
        sla_bucket = "urgent"
    elif age_minutes >= 120:
        sla_bucket = "warning"
    else:
        sla_bucket = "normal"

    return {
        "score": risk_score,
        "level": risk_level,
        "tags": risk_tags,
        "ageMinutes": age_minutes,
        "slaBucket": sla_bucket,
        "challengeState": challenge_state or None,
        "reviewState": review_state or None,
        "reviewRequired": bool(review.get("reviewRequired")),
        "totalChallenges": total_challenges,
        "openAlertCount": open_alert_count,
    }


def build_trust_challenge_sort_key(
    *,
    item: dict[str, Any],
    sort_by: str,
) -> tuple[Any, ...]:
    priority = (
        item.get("priorityProfile")
        if isinstance(item.get("priorityProfile"), dict)
        else {}
    )
    workflow = item.get("workflow") if isinstance(item.get("workflow"), dict) else {}
    challenge_review = (
        item.get("challengeReview")
        if isinstance(item.get("challengeReview"), dict)
        else {}
    )
    if sort_by == "priority_score":
        return (
            int(priority.get("score") or 0),
            str(workflow.get("updatedAt") or "").strip(),
            int(workflow.get("caseId") or 0),
        )
    if sort_by == "total_challenges":
        return (
            int(challenge_review.get("totalChallenges") or 0),
            int(priority.get("score") or 0),
            int(workflow.get("caseId") or 0),
        )
    if sort_by == "case_id":
        return (int(workflow.get("caseId") or 0),)
    return (
        str(workflow.get("updatedAt") or "").strip(),
        int(priority.get("score") or 0),
        int(workflow.get("caseId") or 0),
    )


def build_trust_challenge_action_hints(
    *,
    challenge_review: dict[str, Any],
    priority_profile: dict[str, Any],
    trust_challenge_open_states: set[str] | frozenset[str],
) -> list[str]:
    review = challenge_review if isinstance(challenge_review, dict) else {}
    priority = priority_profile if isinstance(priority_profile, dict) else {}
    hints: list[str] = []
    challenge_state = str(
        review.get("challengeState") or review.get("state") or ""
    ).strip().lower()
    review_state = str(review.get("reviewState") or "").strip().lower()
    open_alert_count = int(priority.get("openAlertCount") or 0)
    priority_level = str(priority.get("level") or "").strip().lower()

    if challenge_state in trust_challenge_open_states:
        hints.append("trust.challenge.decide")
    if review_state == "pending_review":
        hints.append("review.queue.decide")
    if open_alert_count > 0:
        hints.append("alerts.resolve_open")
    if priority_level == "high":
        hints.append("ops.escalate_priority")
    if not hints:
        hints.append("monitor")
    return hints


def build_review_trust_unified_priority_profile(
    *,
    risk_profile: dict[str, Any],
    trust_priority_profile: dict[str, Any],
    challenge_review: dict[str, Any],
    trust_challenge_open_states: set[str] | frozenset[str],
) -> dict[str, Any]:
    risk = risk_profile if isinstance(risk_profile, dict) else {}
    trust = trust_priority_profile if isinstance(trust_priority_profile, dict) else {}
    review = challenge_review if isinstance(challenge_review, dict) else {}
    risk_score = int(risk.get("score") or 0)
    trust_score = int(trust.get("score") or 0)
    challenge_state = str(
        review.get("challengeState") or trust.get("challengeState") or ""
    ).strip().lower()
    review_state = str(
        review.get("reviewState") or trust.get("reviewState") or ""
    ).strip().lower()
    try:
        total_challenges = int(
            review.get("totalChallenges")
            if review.get("totalChallenges") is not None
            else trust.get("totalChallenges")
        )
    except (TypeError, ValueError):
        total_challenges = 0
    open_alert_count = int(trust.get("openAlertCount") or 0)

    score = int(round(risk_score * 0.65 + trust_score * 0.35))
    tags: list[str] = []
    for source in (
        risk.get("tags") if isinstance(risk.get("tags"), list) else [],
        trust.get("tags") if isinstance(trust.get("tags"), list) else [],
    ):
        for token in source:
            text = str(token).strip()
            if text and text not in tags:
                tags.append(text)
    if challenge_state in trust_challenge_open_states:
        score += 10
        if "open_challenge" not in tags:
            tags.append("open_challenge")
    if review_state == "pending_review":
        score += 5
        if "pending_review" not in tags:
            tags.append("pending_review")
    if total_challenges >= 2:
        score += min(8, (total_challenges - 1) * 2)
        if "multi_challenge_case" not in tags:
            tags.append("multi_challenge_case")
    score = max(0, min(score, 100))

    if score >= 75:
        level = "high"
    elif score >= 45:
        level = "medium"
    else:
        level = "low"

    bucket_rank = {"unknown": 0, "normal": 1, "warning": 2, "urgent": 3}
    risk_bucket = str(risk.get("slaBucket") or "").strip().lower() or "unknown"
    trust_bucket = str(trust.get("slaBucket") or "").strip().lower() or "unknown"
    if risk_bucket not in bucket_rank:
        risk_bucket = "unknown"
    if trust_bucket not in bucket_rank:
        trust_bucket = "unknown"
    merged_rank = max(bucket_rank.get(risk_bucket, 0), bucket_rank.get(trust_bucket, 0))
    merged_bucket = next(
        (key for key, value in bucket_rank.items() if value == merged_rank),
        "unknown",
    )

    return {
        "score": score,
        "level": level,
        "tags": tags,
        "slaBucket": merged_bucket,
        "riskScore": risk_score,
        "riskLevel": str(risk.get("level") or "").strip().lower() or None,
        "trustScore": trust_score,
        "trustLevel": str(trust.get("level") or "").strip().lower() or None,
        "challengeState": challenge_state or None,
        "reviewState": review_state or None,
        "totalChallenges": max(0, total_challenges),
        "openAlertCount": max(0, open_alert_count),
    }
