from __future__ import annotations

from typing import Any


class TrustChallengeRouteError(Exception):
    def __init__(self, *, status_code: int, detail: Any):
        super().__init__(str(detail))
        self.status_code = int(status_code)
        self.detail = detail


async def build_trust_challenge_request_payload(
    *,
    case_id: int,
    dispatch_type: str,
    reason_code: str,
    reason: str | None,
    requested_by: str | None,
    auto_accept: bool,
    resolve_report_context_for_case: Any,
    workflow_get_job: Any,
    workflow_append_event: Any,
    workflow_mark_review_required: Any,
    build_trust_phasea_bundle: Any,
    new_challenge_id: Any,
    upsert_audit_alert: Any,
    sync_audit_alert_to_facts: Any,
    serialize_workflow_job: Any,
    trust_challenge_event_type: str,
    trust_challenge_state_requested: str,
    trust_challenge_state_accepted: str,
    trust_challenge_state_under_review: str,
) -> dict[str, Any]:
    normalized_reason_code = str(reason_code or "").strip().lower()
    if not normalized_reason_code:
        raise TrustChallengeRouteError(
            status_code=422,
            detail="invalid_challenge_reason_code",
        )
    actor = str(requested_by or "").strip() or "ops"
    reason_text = str(reason or "").strip() or None
    context = await resolve_report_context_for_case(
        case_id=case_id,
        dispatch_type=dispatch_type,
        not_found_detail="trust_receipt_not_found",
        missing_report_detail="trust_report_payload_missing",
    )
    current_job = await workflow_get_job(job_id=case_id)
    if current_job is None:
        raise TrustChallengeRouteError(status_code=404, detail="review_job_not_found")
    if current_job.status in {"blocked_failed", "archived"}:
        raise TrustChallengeRouteError(
            status_code=409,
            detail="challenge_request_not_allowed",
        )

    challenge_id = new_challenge_id(case_id=case_id)
    base_payload = {
        "dispatchType": context["dispatchType"],
        "traceId": context["traceId"],
        "challengeId": challenge_id,
        "challengeReasonCode": normalized_reason_code,
        "challengeReason": reason_text,
        "challengeRequestedBy": actor,
        "challengeActor": actor,
    }
    await workflow_append_event(
        job_id=case_id,
        event_type=trust_challenge_event_type,
        event_payload={
            **base_payload,
            "challengeState": trust_challenge_state_requested,
        },
        not_found_detail="review_job_not_found",
    )

    if current_job.status != "review_required":
        # challenge 受理后强制进入 review_required 队列，避免绕过复核主状态机。
        await workflow_mark_review_required(
            job_id=case_id,
            event_payload={
                **base_payload,
                "challengeState": trust_challenge_state_under_review,
                "judgeCoreStage": trust_challenge_state_under_review,
            },
        )

    if auto_accept:
        await workflow_append_event(
            job_id=case_id,
            event_type=trust_challenge_event_type,
            event_payload={
                **base_payload,
                "challengeState": trust_challenge_state_accepted,
                "challengeAcceptedBy": actor,
            },
            not_found_detail="review_job_not_found",
        )
        await workflow_append_event(
            job_id=case_id,
            event_type=trust_challenge_event_type,
            event_payload={
                **base_payload,
                "challengeState": trust_challenge_state_under_review,
                "challengeActor": actor,
            },
            not_found_detail="review_job_not_found",
        )

    alert = upsert_audit_alert(
        job_id=case_id,
        scope_id=current_job.scope_id,
        trace_id=context["traceId"],
        alert_type="trust_challenge_requested",
        severity="warning",
        title="AI Judge Trust Challenge Requested",
        message=f"challenge requested ({normalized_reason_code})",
        details={
            "dispatchType": context["dispatchType"],
            "challengeId": challenge_id,
            "reasonCode": normalized_reason_code,
            "reason": reason_text,
            "requestedBy": actor,
        },
    )
    await sync_audit_alert_to_facts(alert=alert)

    bundle = await build_trust_phasea_bundle(
        case_id=case_id,
        dispatch_type=context["dispatchType"],
    )
    workflow_job = await workflow_get_job(job_id=case_id)
    return {
        "ok": True,
        "caseId": case_id,
        "dispatchType": context["dispatchType"],
        "traceId": context["traceId"],
        "challengeId": challenge_id,
        "alertId": alert.alert_id,
        "job": serialize_workflow_job(workflow_job) if workflow_job is not None else None,
        "item": bundle["challengeReview"],
    }


async def build_trust_challenge_decision_payload(
    *,
    case_id: int,
    challenge_id: str,
    dispatch_type: str,
    decision: str,
    actor: str | None,
    reason: str | None,
    resolve_report_context_for_case: Any,
    workflow_get_job: Any,
    workflow_append_event: Any,
    workflow_mark_review_required: Any,
    workflow_mark_completed: Any,
    workflow_mark_draw_pending_vote: Any,
    resolve_open_alerts_for_review: Any,
    build_trust_phasea_bundle: Any,
    serialize_workflow_job: Any,
    trust_challenge_event_type: str,
    trust_challenge_state_closed: str,
    trust_challenge_state_accepted: str,
    trust_challenge_state_under_review: str,
    trust_challenge_state_verdict_upheld: str,
    trust_challenge_state_verdict_overturned: str,
    trust_challenge_state_draw_after_review: str,
    workflow_transition_error_cls: Any,
) -> dict[str, Any]:
    normalized_decision = str(decision or "").strip().lower()
    if normalized_decision not in {"accept", "uphold", "overturn", "draw", "close"}:
        raise TrustChallengeRouteError(
            status_code=422,
            detail="invalid_challenge_decision",
        )
    normalized_challenge_id = str(challenge_id or "").strip()
    if not normalized_challenge_id:
        raise TrustChallengeRouteError(status_code=422, detail="invalid_challenge_id")

    context = await resolve_report_context_for_case(
        case_id=case_id,
        dispatch_type=dispatch_type,
        not_found_detail="trust_receipt_not_found",
        missing_report_detail="trust_report_payload_missing",
    )
    current_job = await workflow_get_job(job_id=case_id)
    if current_job is None:
        raise TrustChallengeRouteError(status_code=404, detail="review_job_not_found")
    actor_text = str(actor or "").strip() or "ops"
    reason_text = str(reason or "").strip() or None

    before_bundle = await build_trust_phasea_bundle(
        case_id=case_id,
        dispatch_type=context["dispatchType"],
    )
    challenge_item = next(
        (
            item
            for item in (
                before_bundle["challengeReview"].get("challenges")
                if isinstance(before_bundle["challengeReview"].get("challenges"), list)
                else []
            )
            if str(item.get("challengeId") or "") == normalized_challenge_id
        ),
        None,
    )
    if challenge_item is None:
        raise TrustChallengeRouteError(status_code=404, detail="trust_challenge_not_found")
    if str(challenge_item.get("currentState") or "") == trust_challenge_state_closed:
        raise TrustChallengeRouteError(
            status_code=409,
            detail="trust_challenge_already_closed",
        )

    base_payload = {
        "dispatchType": context["dispatchType"],
        "traceId": context["traceId"],
        "challengeId": normalized_challenge_id,
        "challengeActor": actor_text,
        "challengeDecision": normalized_decision,
        "challengeDecisionReason": reason_text,
    }
    resolved_alert_ids: list[str] = []
    updated_job = current_job

    if normalized_decision == "accept":
        await workflow_append_event(
            job_id=case_id,
            event_type=trust_challenge_event_type,
            event_payload={
                **base_payload,
                "challengeState": trust_challenge_state_accepted,
                "challengeAcceptedBy": actor_text,
            },
        )
        await workflow_append_event(
            job_id=case_id,
            event_type=trust_challenge_event_type,
            event_payload={
                **base_payload,
                "challengeState": trust_challenge_state_under_review,
            },
        )
        if current_job.status != "review_required":
            await workflow_mark_review_required(
                job_id=case_id,
                event_payload={
                    **base_payload,
                    "challengeState": trust_challenge_state_under_review,
                    "judgeCoreStage": trust_challenge_state_under_review,
                },
            )
            updated_job = await workflow_get_job(job_id=case_id)
    elif normalized_decision == "uphold":
        await workflow_append_event(
            job_id=case_id,
            event_type=trust_challenge_event_type,
            event_payload={
                **base_payload,
                "challengeState": trust_challenge_state_verdict_upheld,
                "reviewDecision": "approve",
                "reviewActor": actor_text,
                "reviewReason": reason_text or "challenge_upheld",
            },
        )
        if current_job.status == "review_required":
            await workflow_mark_completed(
                job_id=case_id,
                event_payload={
                    **base_payload,
                    "reviewDecision": "approve",
                    "reviewActor": actor_text,
                    "reviewReason": reason_text or "challenge_upheld",
                    "judgeCoreStage": "review_approved",
                },
            )
            resolved_alert_ids = await resolve_open_alerts_for_review(
                job_id=case_id,
                actor=actor_text,
                reason=reason_text or "challenge_upheld",
            )
            updated_job = await workflow_get_job(job_id=case_id)
    elif normalized_decision in {"overturn", "draw"}:
        overturned_state = (
            trust_challenge_state_verdict_overturned
            if normalized_decision == "overturn"
            else trust_challenge_state_draw_after_review
        )
        await workflow_append_event(
            job_id=case_id,
            event_type=trust_challenge_event_type,
            event_payload={
                **base_payload,
                "challengeState": overturned_state,
            },
        )
        draw_payload = {
            **base_payload,
            "challengeState": trust_challenge_state_draw_after_review,
            "judgeCoreStage": trust_challenge_state_draw_after_review,
        }
        try:
            await workflow_mark_draw_pending_vote(
                job_id=case_id,
                event_payload=draw_payload,
            )
            updated_job = await workflow_get_job(job_id=case_id)
        except workflow_transition_error_cls:
            pass
        await workflow_append_event(
            job_id=case_id,
            event_type=trust_challenge_event_type,
            event_payload={
                **base_payload,
                "challengeState": trust_challenge_state_draw_after_review,
            },
        )

    await workflow_append_event(
        job_id=case_id,
        event_type=trust_challenge_event_type,
        event_payload={
            **base_payload,
            "challengeState": trust_challenge_state_closed,
            "challengeClosedBy": actor_text,
            "challengeCloseReason": reason_text,
        },
    )

    after_bundle = await build_trust_phasea_bundle(
        case_id=case_id,
        dispatch_type=context["dispatchType"],
    )
    if updated_job is None:
        updated_job = await workflow_get_job(job_id=case_id)
    return {
        "ok": True,
        "caseId": case_id,
        "dispatchType": context["dispatchType"],
        "traceId": context["traceId"],
        "challengeId": normalized_challenge_id,
        "decision": normalized_decision,
        "resolvedAlertIds": resolved_alert_ids,
        "job": serialize_workflow_job(updated_job) if updated_job is not None else None,
        "item": after_bundle["challengeReview"],
    }
