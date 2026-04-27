from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.domain.trust import TrustChallengeEvent

from .trust_challenge_public_contract import (
    build_trust_challenge_public_status,
    validate_trust_challenge_public_contract,
)


class TrustChallengeRouteError(Exception):
    def __init__(self, *, status_code: int, detail: Any):
        super().__init__(str(detail))
        self.status_code = int(status_code)
        self.detail = detail


TRUST_CHALLENGE_STATE_REVIEW_RETAINED = "review_retained"
_TRUST_CHALLENGE_OPEN_STATES = {
    "challenge_requested",
    "challenge_accepted",
    "under_internal_review",
}
_TRUST_CHALLENGE_ALLOWED_TRANSITIONS = {
    "challenge_requested": {"challenge_accepted", "challenge_closed"},
    "challenge_accepted": {"under_internal_review", "challenge_closed"},
    "under_internal_review": {
        "verdict_upheld",
        "verdict_overturned",
        "draw_after_review",
        TRUST_CHALLENGE_STATE_REVIEW_RETAINED,
        "challenge_closed",
    },
    "verdict_upheld": {"challenge_closed"},
    "verdict_overturned": {"challenge_closed"},
    "draw_after_review": {"challenge_closed"},
    TRUST_CHALLENGE_STATE_REVIEW_RETAINED: {"challenge_closed"},
    "challenge_closed": set(),
}


def _challenge_review_items(challenge_review: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(challenge_review, dict):
        return []
    challenges = challenge_review.get("challenges")
    if not isinstance(challenges, list):
        return []
    return [item for item in challenges if isinstance(item, dict)]


def _find_active_challenge(challenge_review: dict[str, Any] | None) -> dict[str, Any] | None:
    for item in _challenge_review_items(challenge_review):
        state = str(item.get("currentState") or "").strip().lower()
        if state in _TRUST_CHALLENGE_OPEN_STATES:
            return item
    return None


def _route_error_status_code(err: Exception) -> int | None:
    status_code = getattr(err, "status_code", None)
    try:
        return int(status_code)
    except (TypeError, ValueError):
        return None


def _build_validated_public_status(
    *,
    case_id: int,
    dispatch_type: str,
    trace_id: str | None,
    challenge_review: dict[str, Any] | None,
    workflow_status: str | None,
    kernel_version: dict[str, Any] | None = None,
    case_absent: bool = False,
) -> dict[str, Any]:
    try:
        return build_trust_challenge_public_status(
            case_id=case_id,
            dispatch_type=dispatch_type,
            trace_id=trace_id,
            challenge_review=challenge_review,
            workflow_status=workflow_status,
            kernel_version=kernel_version,
            case_absent=case_absent,
        )
    except ValueError as err:
        raise TrustChallengeRouteError(
            status_code=500,
            detail={
                "code": "trust_challenge_public_status_contract_violation",
                "message": str(err),
            },
        ) from err


def _find_challenge(
    *,
    challenge_review: dict[str, Any] | None,
    challenge_id: str,
) -> dict[str, Any] | None:
    normalized_challenge_id = str(challenge_id or "").strip()
    for item in _challenge_review_items(challenge_review):
        if str(item.get("challengeId") or "").strip() == normalized_challenge_id:
            return item
    return None


async def build_trust_challenge_public_status_payload(
    *,
    case_id: int,
    dispatch_type: str,
    resolve_report_context_for_case: Any,
    workflow_get_job: Any,
    build_trust_phasea_bundle: Any,
) -> dict[str, Any]:
    try:
        context = await resolve_report_context_for_case(
            case_id=case_id,
            dispatch_type=dispatch_type,
            not_found_detail="trust_receipt_not_found",
            missing_report_detail="trust_report_payload_missing",
        )
    except Exception as err:  # noqa: BLE001
        if _route_error_status_code(err) == 404:
            return _build_validated_public_status(
                case_id=case_id,
                dispatch_type=dispatch_type,
                trace_id=None,
                challenge_review=None,
                workflow_status=None,
                case_absent=True,
            )
        raise

    workflow_job = await workflow_get_job(job_id=case_id)
    if workflow_job is None:
        return _build_validated_public_status(
            case_id=case_id,
            dispatch_type=context["dispatchType"],
            trace_id=None,
            challenge_review=None,
            workflow_status=None,
            case_absent=True,
        )

    bundle = await build_trust_phasea_bundle(
        case_id=case_id,
        dispatch_type=context["dispatchType"],
    )
    public_status = _build_validated_public_status(
        case_id=case_id,
        dispatch_type=context["dispatchType"],
        trace_id=context["traceId"],
        challenge_review=bundle.get("challengeReview"),
        workflow_status=getattr(workflow_job, "status", None),
        kernel_version=(
            dict(bundle.get("kernelVersion"))
            if isinstance(bundle.get("kernelVersion"), dict)
            else None
        ),
    )
    validate_trust_challenge_public_contract(public_status)
    return public_status


def _require_challenge_transition(
    *,
    current_state: str,
    next_state: str,
) -> None:
    normalized_current = str(current_state or "").strip().lower()
    normalized_next = str(next_state or "").strip().lower()
    if normalized_next not in _TRUST_CHALLENGE_ALLOWED_TRANSITIONS.get(
        normalized_current,
        set(),
    ):
        raise TrustChallengeRouteError(
            status_code=409,
            detail="trust_challenge_invalid_transition",
        )


async def _append_trust_registry_challenge_event(
    *,
    case_id: int,
    dispatch_type: str,
    trace_id: str,
    event_type: str,
    event_payload: dict[str, Any],
    append_trust_challenge_event: Any | None,
) -> None:
    if append_trust_challenge_event is None:
        return
    try:
        updated = await append_trust_challenge_event(
            case_id=case_id,
            dispatch_type=dispatch_type,
            trace_id=trace_id,
            registry_version=None,
            event=TrustChallengeEvent(
                event_type=event_type,
                challenge_id=str(event_payload.get("challengeId") or "").strip(),
                state=str(event_payload.get("challengeState") or "").strip().lower(),
                actor=(
                    str(
                        event_payload.get("challengeActor")
                        or event_payload.get("challengeRequestedBy")
                        or event_payload.get("challengeAcceptedBy")
                        or event_payload.get("challengeClosedBy")
                        or event_payload.get("reviewActor")
                        or ""
                    ).strip()
                    or None
                ),
                reason_code=(
                    str(event_payload.get("challengeReasonCode") or "").strip()
                    or None
                ),
                reason=(
                    str(
                        event_payload.get("challengeReason")
                        or event_payload.get("challengeDecisionReason")
                        or event_payload.get("challengeCloseReason")
                        or event_payload.get("reviewReason")
                        or ""
                    ).strip()
                    or None
                ),
                payload=dict(event_payload),
                created_at=datetime.now(timezone.utc),
            ),
        )
    except Exception as err:  # noqa: BLE001
        raise TrustChallengeRouteError(
            status_code=500,
            detail={
                "code": "trust_challenge_registry_append_failed",
                "message": str(err),
            },
        ) from err
    if updated is None:
        raise TrustChallengeRouteError(
            status_code=409,
            detail="trust_registry_snapshot_missing",
        )


async def _append_challenge_workflow_event(
    *,
    case_id: int,
    event_type: str,
    event_payload: dict[str, Any],
    workflow_append_event: Any,
    append_trust_challenge_event: Any | None,
) -> None:
    await workflow_append_event(
        job_id=case_id,
        event_type=event_type,
        event_payload=event_payload,
        not_found_detail="review_job_not_found",
    )
    await _append_trust_registry_challenge_event(
        case_id=case_id,
        dispatch_type=str(event_payload.get("dispatchType") or ""),
        trace_id=str(event_payload.get("traceId") or ""),
        event_type=event_type,
        event_payload=event_payload,
        append_trust_challenge_event=append_trust_challenge_event,
    )


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
    append_trust_challenge_event: Any | None = None,
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
    before_bundle = await build_trust_phasea_bundle(
        case_id=case_id,
        dispatch_type=context["dispatchType"],
    )
    active_challenge = _find_active_challenge(before_bundle.get("challengeReview"))
    if active_challenge is not None:
        raise TrustChallengeRouteError(
            status_code=409,
            detail="trust_challenge_already_open",
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
    await _append_challenge_workflow_event(
        case_id=case_id,
        event_type=trust_challenge_event_type,
        event_payload={
            **base_payload,
            "challengeState": trust_challenge_state_requested,
        },
        workflow_append_event=workflow_append_event,
        append_trust_challenge_event=append_trust_challenge_event,
    )

    if not auto_accept and current_job.status != "review_required":
        # challenge 打开后必须进入复核工作流；是否接受只影响 challenge 状态推进。
        await workflow_mark_review_required(
            job_id=case_id,
            event_payload={
                **base_payload,
                "judgeCoreStage": trust_challenge_state_requested,
            },
        )

    if auto_accept:
        _require_challenge_transition(
            current_state=trust_challenge_state_requested,
            next_state=trust_challenge_state_accepted,
        )
        await _append_challenge_workflow_event(
            case_id=case_id,
            event_type=trust_challenge_event_type,
            event_payload={
                **base_payload,
                "challengeState": trust_challenge_state_accepted,
                "challengeAcceptedBy": actor,
            },
            workflow_append_event=workflow_append_event,
            append_trust_challenge_event=append_trust_challenge_event,
        )
        _require_challenge_transition(
            current_state=trust_challenge_state_accepted,
            next_state=trust_challenge_state_under_review,
        )
        if current_job.status != "review_required":
            # challenge 受理后强制进入 review_required 队列，避免绕过复核主状态机。
            await workflow_mark_review_required(
                job_id=case_id,
                event_payload={
                    **base_payload,
                    "judgeCoreStage": trust_challenge_state_under_review,
                },
            )
        await _append_challenge_workflow_event(
            case_id=case_id,
            event_type=trust_challenge_event_type,
            event_payload={
                **base_payload,
                "challengeState": trust_challenge_state_under_review,
                "challengeActor": actor,
            },
            workflow_append_event=workflow_append_event,
            append_trust_challenge_event=append_trust_challenge_event,
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
        "publicStatus": _build_validated_public_status(
            case_id=case_id,
            dispatch_type=context["dispatchType"],
            trace_id=context["traceId"],
            challenge_review=bundle.get("challengeReview"),
            workflow_status=getattr(workflow_job, "status", None),
            kernel_version=(
                dict(bundle.get("kernelVersion"))
                if isinstance(bundle.get("kernelVersion"), dict)
                else None
            ),
        ),
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
    trust_challenge_state_review_retained: str,
    workflow_transition_error_cls: Any,
    append_trust_challenge_event: Any | None = None,
) -> dict[str, Any]:
    normalized_decision = str(decision or "").strip().lower()
    if normalized_decision not in {
        "accept",
        "uphold",
        "overturn",
        "draw",
        "retain_review",
        "close",
    }:
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
    challenge_item = _find_challenge(
        challenge_review=before_bundle.get("challengeReview"),
        challenge_id=normalized_challenge_id,
    )
    if challenge_item is None:
        raise TrustChallengeRouteError(status_code=404, detail="trust_challenge_not_found")
    current_state = str(challenge_item.get("currentState") or "").strip().lower()
    if current_state == trust_challenge_state_closed:
        raise TrustChallengeRouteError(
            status_code=409,
            detail="trust_challenge_already_closed",
        )
    if normalized_decision != "close" and current_state not in _TRUST_CHALLENGE_OPEN_STATES:
        raise TrustChallengeRouteError(
            status_code=409,
            detail="trust_challenge_not_open",
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
        _require_challenge_transition(
            current_state=current_state,
            next_state=trust_challenge_state_accepted,
        )
        await _append_challenge_workflow_event(
            case_id=case_id,
            event_type=trust_challenge_event_type,
            event_payload={
                **base_payload,
                "challengeState": trust_challenge_state_accepted,
                "challengeAcceptedBy": actor_text,
            },
            workflow_append_event=workflow_append_event,
            append_trust_challenge_event=append_trust_challenge_event,
        )
        _require_challenge_transition(
            current_state=trust_challenge_state_accepted,
            next_state=trust_challenge_state_under_review,
        )
        if current_job.status != "review_required":
            await workflow_mark_review_required(
                job_id=case_id,
                event_payload={
                    **base_payload,
                    "judgeCoreStage": trust_challenge_state_under_review,
                },
            )
            updated_job = await workflow_get_job(job_id=case_id)
        await _append_challenge_workflow_event(
            case_id=case_id,
            event_type=trust_challenge_event_type,
            event_payload={
                **base_payload,
                "challengeState": trust_challenge_state_under_review,
            },
            workflow_append_event=workflow_append_event,
            append_trust_challenge_event=append_trust_challenge_event,
        )
        current_state = trust_challenge_state_under_review
    elif normalized_decision == "uphold":
        _require_challenge_transition(
            current_state=current_state,
            next_state=trust_challenge_state_verdict_upheld,
        )
        await _append_challenge_workflow_event(
            case_id=case_id,
            event_type=trust_challenge_event_type,
            event_payload={
                **base_payload,
                "challengeState": trust_challenge_state_verdict_upheld,
                "reviewDecision": "approve",
                "reviewActor": actor_text,
                "reviewReason": reason_text or "challenge_upheld",
            },
            workflow_append_event=workflow_append_event,
            append_trust_challenge_event=append_trust_challenge_event,
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
        current_state = trust_challenge_state_verdict_upheld
    elif normalized_decision in {"overturn", "draw", "retain_review"}:
        decision_state_by_name = {
            "overturn": trust_challenge_state_verdict_overturned,
            "draw": trust_challenge_state_draw_after_review,
            "retain_review": trust_challenge_state_review_retained,
        }
        next_state = decision_state_by_name[normalized_decision]
        _require_challenge_transition(
            current_state=current_state,
            next_state=next_state,
        )
        review_decision = "retain" if normalized_decision == "retain_review" else "reject"
        await _append_challenge_workflow_event(
            case_id=case_id,
            event_type=trust_challenge_event_type,
            event_payload={
                **base_payload,
                "challengeState": next_state,
                "reviewDecision": review_decision,
                "reviewActor": actor_text,
                "reviewReason": reason_text or f"challenge_{normalized_decision}",
            },
            workflow_append_event=workflow_append_event,
            append_trust_challenge_event=append_trust_challenge_event,
        )
        if normalized_decision in {"overturn", "draw"}:
            draw_payload = {
                **base_payload,
                "judgeCoreStage": next_state,
            }
            try:
                await workflow_mark_draw_pending_vote(
                    job_id=case_id,
                    event_payload=draw_payload,
                )
                updated_job = await workflow_get_job(job_id=case_id)
            except workflow_transition_error_cls:
                pass
        current_state = next_state

    if normalized_decision != "accept":
        _require_challenge_transition(
            current_state=current_state,
            next_state=trust_challenge_state_closed,
        )
        await _append_challenge_workflow_event(
            case_id=case_id,
            event_type=trust_challenge_event_type,
            event_payload={
                **base_payload,
                "challengeState": trust_challenge_state_closed,
                "challengeClosedBy": actor_text,
                "challengeCloseReason": reason_text,
            },
            workflow_append_event=workflow_append_event,
            append_trust_challenge_event=append_trust_challenge_event,
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
        "publicStatus": _build_validated_public_status(
            case_id=case_id,
            dispatch_type=context["dispatchType"],
            trace_id=context["traceId"],
            challenge_review=after_bundle.get("challengeReview"),
            workflow_status=getattr(updated_job, "status", None),
            kernel_version=(
                dict(after_bundle.get("kernelVersion"))
                if isinstance(after_bundle.get("kernelVersion"), dict)
                else None
            ),
        ),
    }
