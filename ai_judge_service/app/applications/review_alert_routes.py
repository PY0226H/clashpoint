from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Awaitable, Callable


class ReviewRouteError(Exception):
    def __init__(self, *, status_code: int, detail: Any):
        super().__init__(str(detail))
        self.status_code = int(status_code)
        self.detail = detail


def normalize_review_case_risk_level(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    return normalized


def normalize_review_case_sla_bucket(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    return normalized


def normalize_review_case_sort_by(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "updated_at"
    return normalized


def normalize_review_case_sort_order(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "desc"
    return normalized


def build_review_case_risk_profile(
    *,
    workflow: Any,
    report_payload: dict[str, Any],
    report_summary: dict[str, Any],
    now: datetime,
    normalize_query_datetime: Callable[[datetime | None], datetime | None],
) -> dict[str, Any]:
    payload = report_payload if isinstance(report_payload, dict) else {}
    summary = report_summary if isinstance(report_summary, dict) else {}
    fairness_summary = (
        payload.get("fairnessSummary")
        if isinstance(payload.get("fairnessSummary"), dict)
        else {}
    )
    error_codes = [
        str(item).strip()
        for item in (payload.get("errorCodes") or [])
        if str(item).strip()
    ]
    audit_alerts = (
        summary.get("auditAlerts")
        if isinstance(summary.get("auditAlerts"), list)
        else []
    )
    audit_alert_count = len(audit_alerts)
    callback_status = str(summary.get("callbackStatus") or "").strip().lower()
    winner = str(payload.get("winner") or "").strip().lower()
    panel_high_disagreement = bool(fairness_summary.get("panelHighDisagreement"))
    review_required = bool(payload.get("reviewRequired"))

    age_minutes: int | None = None
    workflow_updated_at = getattr(workflow, "updated_at", None)
    if isinstance(workflow_updated_at, datetime):
        updated_at = normalize_query_datetime(workflow_updated_at)
        if updated_at is not None:
            age_delta = now - updated_at
            age_minutes = max(0, int(age_delta.total_seconds() // 60))

    risk_score = 0
    risk_tags: list[str] = []

    if review_required:
        risk_score += 35
        risk_tags.append("review_required")
    if panel_high_disagreement:
        risk_score += 20
        risk_tags.append("panel_high_disagreement")
    if error_codes:
        risk_score += min(25, len(error_codes) * 8)
        risk_tags.append("error_codes_present")
    if audit_alert_count > 0:
        risk_score += min(20, audit_alert_count * 4)
        risk_tags.append("audit_alerts_present")
    if callback_status in {"failed", "error", "callback_failed"}:
        risk_score += 15
        risk_tags.append("callback_failed")
    if winner == "draw":
        risk_score += 5
        risk_tags.append("draw_outcome")

    if age_minutes is not None and age_minutes >= 360:
        risk_score += 15
        risk_tags.append("review_stale_6h")
    elif age_minutes is not None and age_minutes >= 120:
        risk_score += 8
        risk_tags.append("review_stale_2h")

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
        "auditAlertCount": audit_alert_count,
        "panelHighDisagreement": panel_high_disagreement,
        "reviewRequired": review_required,
    }


def build_review_case_sort_key(
    *,
    item: dict[str, Any],
    sort_by: str,
) -> tuple[Any, ...]:
    risk = item.get("riskProfile") if isinstance(item.get("riskProfile"), dict) else {}
    unified = (
        item.get("unifiedPriorityProfile")
        if isinstance(item.get("unifiedPriorityProfile"), dict)
        else {}
    )
    workflow = item.get("workflow") if isinstance(item.get("workflow"), dict) else {}
    if sort_by == "unified_priority_score":
        return (
            int(unified.get("score") or 0),
            int(risk.get("score") or 0),
            str(workflow.get("updatedAt") or "").strip(),
            int(workflow.get("caseId") or 0),
        )
    if sort_by == "risk_score":
        return (
            int(risk.get("score") or 0),
            str(workflow.get("updatedAt") or "").strip(),
            int(workflow.get("caseId") or 0),
        )
    if sort_by == "audit_alert_count":
        return (
            int(risk.get("auditAlertCount") or 0),
            int(risk.get("score") or 0),
            int(workflow.get("caseId") or 0),
        )
    if sort_by == "case_id":
        return (int(workflow.get("caseId") or 0),)
    return (
        str(workflow.get("updatedAt") or "").strip(),
        int(risk.get("score") or 0),
        int(workflow.get("caseId") or 0),
    )


def normalize_review_case_filters(
    *,
    status: str,
    dispatch_type: str | None,
    risk_level: str | None,
    sla_bucket: str | None,
    challenge_state: str | None,
    trust_review_state: str | None,
    unified_priority_level: str | None,
    sort_by: str,
    sort_order: str,
    scan_limit: int,
    normalize_workflow_status: Callable[[str | None], str | None],
    workflow_statuses: set[str] | frozenset[str],
    normalize_review_case_risk_level: Callable[[str | None], str | None],
    review_case_risk_level_values: set[str] | frozenset[str],
    normalize_review_case_sla_bucket: Callable[[str | None], str | None],
    review_case_sla_bucket_values: set[str] | frozenset[str],
    normalize_trust_challenge_state_filter: Callable[[str | None], str | None],
    case_fairness_challenge_states: set[str] | frozenset[str],
    normalize_trust_challenge_review_state: Callable[[str | None], str | None],
    trust_challenge_review_state_values: set[str] | frozenset[str],
    normalize_trust_challenge_priority_level: Callable[[str | None], str | None],
    trust_challenge_priority_level_values: set[str] | frozenset[str],
    normalize_review_case_sort_by: Callable[[str], str],
    review_case_sort_fields: set[str] | frozenset[str],
    normalize_review_case_sort_order: Callable[[str], str],
) -> dict[str, Any]:
    normalized_status = normalize_workflow_status(status)
    if normalized_status is None or normalized_status not in workflow_statuses:
        raise ValueError("invalid_workflow_status")
    normalized_dispatch_type = str(dispatch_type or "").strip().lower() or None
    if normalized_dispatch_type not in {None, "phase", "final"}:
        raise ValueError("invalid_dispatch_type")
    normalized_risk_level = normalize_review_case_risk_level(risk_level)
    if (
        normalized_risk_level is not None
        and normalized_risk_level not in review_case_risk_level_values
    ):
        raise ValueError("invalid_review_risk_level")
    normalized_sla_bucket = normalize_review_case_sla_bucket(sla_bucket)
    if (
        normalized_sla_bucket is not None
        and normalized_sla_bucket not in review_case_sla_bucket_values
    ):
        raise ValueError("invalid_review_sla_bucket")
    normalized_challenge_state = normalize_trust_challenge_state_filter(challenge_state)
    if (
        normalized_challenge_state is not None
        and normalized_challenge_state != "open"
        and normalized_challenge_state not in case_fairness_challenge_states
    ):
        raise ValueError("invalid_review_challenge_state")
    normalized_trust_review_state = normalize_trust_challenge_review_state(trust_review_state)
    if (
        normalized_trust_review_state is not None
        and normalized_trust_review_state not in trust_challenge_review_state_values
    ):
        raise ValueError("invalid_review_trust_review_state")
    normalized_unified_priority_level = normalize_trust_challenge_priority_level(
        unified_priority_level
    )
    if (
        normalized_unified_priority_level is not None
        and normalized_unified_priority_level not in trust_challenge_priority_level_values
    ):
        raise ValueError("invalid_review_unified_priority_level")
    normalized_sort_by = normalize_review_case_sort_by(sort_by)
    if normalized_sort_by not in review_case_sort_fields:
        raise ValueError("invalid_review_sort_by")
    normalized_sort_order = normalize_review_case_sort_order(sort_order)
    if normalized_sort_order not in {"asc", "desc"}:
        raise ValueError("invalid_review_sort_order")
    normalized_scan_limit = max(20, min(int(scan_limit), 1000))
    return {
        "status": normalized_status,
        "dispatchType": normalized_dispatch_type,
        "riskLevel": normalized_risk_level,
        "slaBucket": normalized_sla_bucket,
        "challengeState": normalized_challenge_state,
        "trustReviewState": normalized_trust_review_state,
        "unifiedPriorityLevel": normalized_unified_priority_level,
        "sortBy": normalized_sort_by,
        "sortOrder": normalized_sort_order,
        "scanLimit": normalized_scan_limit,
    }


async def build_review_cases_list_payload(
    *,
    normalized_status: str,
    normalized_dispatch_type: str | None,
    normalized_risk_level: str | None,
    normalized_sla_bucket: str | None,
    normalized_challenge_state: str | None,
    normalized_trust_review_state: str | None,
    normalized_unified_priority_level: str | None,
    normalized_sort_by: str,
    normalized_sort_order: str,
    normalized_scan_limit: int,
    limit: int,
    trust_challenge_open_states: set[str] | frozenset[str],
    workflow_list_jobs: Callable[..., Awaitable[list[Any]]],
    get_trace: Callable[[int], Any | None],
    workflow_list_events: Callable[..., Awaitable[list[Any]]],
    list_audit_alerts: Callable[..., Awaitable[list[Any]]],
    build_challenge_review_registry: Callable[..., dict[str, Any]],
    build_review_case_risk_profile: Callable[..., dict[str, Any]],
    build_trust_challenge_priority_profile: Callable[..., dict[str, Any]],
    build_review_trust_unified_priority_profile: Callable[..., dict[str, Any]],
    serialize_workflow_job: Callable[[Any], dict[str, Any]],
    build_review_case_sort_key: Callable[..., Any],
) -> dict[str, Any]:
    jobs = await workflow_list_jobs(
        status=normalized_status,
        dispatch_type=normalized_dispatch_type,
        limit=normalized_scan_limit,
    )
    items: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for job in jobs:
        trace = get_trace(job.job_id)
        report_summary = (
            trace.report_summary if trace and isinstance(trace.report_summary, dict) else {}
        )
        report_payload = (
            report_summary.get("payload") if isinstance(report_summary.get("payload"), dict) else {}
        )
        workflow_events = list(await workflow_list_events(job_id=job.job_id))
        alerts = await list_audit_alerts(job_id=job.job_id, status=None, limit=200)
        trace_id = str(
            (trace.trace_id if trace is not None else "")
            or job.trace_id
            or report_summary.get("traceId")
            or ""
        ).strip()
        challenge_review = build_challenge_review_registry(
            case_id=job.job_id,
            trace_id=trace_id,
            workflow_status=job.status,
            workflow_events=workflow_events,
            alerts=alerts,
            report_payload=report_payload,
        )
        error_codes = report_payload.get("errorCodes")
        audit_alerts = report_summary.get("auditAlerts")
        risk_profile = build_review_case_risk_profile(
            workflow=job,
            report_payload=report_payload,
            report_summary=report_summary,
            now=now,
        )
        trust_priority_profile = build_trust_challenge_priority_profile(
            workflow=job,
            challenge_review=challenge_review,
            report_payload=report_payload,
            report_summary=report_summary,
            now=now,
        )
        unified_priority_profile = build_review_trust_unified_priority_profile(
            risk_profile=risk_profile,
            trust_priority_profile=trust_priority_profile,
            challenge_review=challenge_review,
        )
        items.append(
            {
                "workflow": serialize_workflow_job(job),
                "winner": report_summary.get("winner"),
                "reviewRequired": bool(report_payload.get("reviewRequired")),
                "fairnessSummary": (
                    report_payload.get("fairnessSummary")
                    if isinstance(report_payload.get("fairnessSummary"), dict)
                    else None
                ),
                "errorCodes": error_codes if isinstance(error_codes, list) else [],
                "auditAlertCount": len(audit_alerts) if isinstance(audit_alerts, list) else 0,
                "callbackStatus": report_summary.get("callbackStatus"),
                "riskProfile": risk_profile,
                "trustChallenge": {
                    "state": str(challenge_review.get("challengeState") or "").strip().lower()
                    or None,
                    "reviewState": str(challenge_review.get("reviewState") or "").strip().lower()
                    or None,
                    "activeChallengeId": (
                        str(challenge_review.get("activeChallengeId") or "").strip() or None
                    ),
                    "totalChallenges": int(challenge_review.get("totalChallenges") or 0),
                    "openAlertIds": (
                        challenge_review.get("openAlertIds")
                        if isinstance(challenge_review.get("openAlertIds"), list)
                        else []
                    ),
                    "challengeReasons": (
                        challenge_review.get("challengeReasons")
                        if isinstance(challenge_review.get("challengeReasons"), list)
                        else []
                    ),
                },
                "trustPriorityProfile": trust_priority_profile,
                "unifiedPriorityProfile": unified_priority_profile,
            }
        )

    filtered_items: list[dict[str, Any]] = []
    for row in items:
        risk_profile = row.get("riskProfile") if isinstance(row.get("riskProfile"), dict) else {}
        trust_challenge = (
            row.get("trustChallenge") if isinstance(row.get("trustChallenge"), dict) else {}
        )
        unified_priority = (
            row.get("unifiedPriorityProfile")
            if isinstance(row.get("unifiedPriorityProfile"), dict)
            else {}
        )
        if (
            normalized_risk_level is not None
            and str(risk_profile.get("level") or "").strip().lower() != normalized_risk_level
        ):
            continue
        if (
            normalized_sla_bucket is not None
            and str(unified_priority.get("slaBucket") or "").strip().lower() != normalized_sla_bucket
        ):
            continue
        challenge_state_value = str(trust_challenge.get("state") or "").strip().lower()
        if normalized_challenge_state == "open":
            if challenge_state_value not in trust_challenge_open_states:
                continue
        elif (
            normalized_challenge_state is not None
            and challenge_state_value != normalized_challenge_state
        ):
            continue
        if (
            normalized_trust_review_state is not None
            and str(trust_challenge.get("reviewState") or "").strip().lower()
            != normalized_trust_review_state
        ):
            continue
        if (
            normalized_unified_priority_level is not None
            and str(unified_priority.get("level") or "").strip().lower()
            != normalized_unified_priority_level
        ):
            continue
        filtered_items.append(row)

    filtered_items.sort(
        key=lambda row: build_review_case_sort_key(item=row, sort_by=normalized_sort_by),
        reverse=(normalized_sort_order == "desc"),
    )
    page_items = filtered_items[:limit]
    return {
        "count": len(filtered_items),
        "returned": len(page_items),
        "scanned": len(items),
        "items": page_items,
        "filters": {
            "status": normalized_status,
            "dispatchType": normalized_dispatch_type,
            "riskLevel": normalized_risk_level,
            "slaBucket": normalized_sla_bucket,
            "challengeState": normalized_challenge_state,
            "trustReviewState": normalized_trust_review_state,
            "unifiedPriorityLevel": normalized_unified_priority_level,
            "sortBy": normalized_sort_by,
            "sortOrder": normalized_sort_order,
            "scanLimit": normalized_scan_limit,
            "limit": limit,
        },
    }


async def build_review_case_detail_payload(
    *,
    case_id: int,
    workflow_get_job: Callable[..., Awaitable[Any | None]],
    workflow_list_events: Callable[..., Awaitable[list[Any]]],
    list_audit_alerts: Callable[..., Awaitable[list[Any]]],
    get_trace: Callable[[int], Any | None],
    serialize_workflow_job: Callable[[Any], dict[str, Any]],
    serialize_alert_item: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    workflow_job = await workflow_get_job(job_id=case_id)
    if workflow_job is None:
        raise LookupError("review_job_not_found")
    workflow_events = await workflow_list_events(job_id=case_id)
    alerts = await list_audit_alerts(job_id=case_id, status=None, limit=200)
    trace = get_trace(case_id)
    report_summary = (
        trace.report_summary if trace and isinstance(trace.report_summary, dict) else {}
    )
    report_payload = (
        report_summary.get("payload") if isinstance(report_summary.get("payload"), dict) else {}
    )
    return {
        "job": serialize_workflow_job(workflow_job),
        "reportPayload": report_payload,
        "winner": report_summary.get("winner"),
        "reviewRequired": bool(report_payload.get("reviewRequired")),
        "callbackStatus": report_summary.get("callbackStatus"),
        "callbackError": report_summary.get("callbackError"),
        "trace": (
            {
                "traceId": trace.trace_id,
                "status": trace.status,
                "createdAt": trace.created_at.isoformat(),
                "updatedAt": trace.updated_at.isoformat(),
            }
            if trace is not None
            else None
        ),
        "events": [
            {
                "eventSeq": item.event_seq,
                "eventType": item.event_type,
                "payload": item.payload,
                "createdAt": item.created_at.isoformat(),
            }
            for item in workflow_events
        ],
        "alerts": [serialize_alert_item(item) for item in alerts],
    }


async def build_review_case_decision_payload(
    *,
    case_id: int,
    decision: str,
    actor: str | None,
    reason: str | None,
    workflow_get_job: Callable[..., Awaitable[Any | None]],
    workflow_mark_completed: Callable[..., Awaitable[None]],
    workflow_mark_failed: Callable[..., Awaitable[None]],
    resolve_open_alerts_for_review: Callable[..., Awaitable[list[str]]],
    serialize_workflow_job: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    normalized_decision = str(decision or "").strip().lower()
    if normalized_decision not in {"approve", "reject"}:
        raise ValueError("invalid_review_decision")
    current_job = await workflow_get_job(job_id=case_id)
    if current_job is None:
        raise LookupError("review_job_not_found")
    if current_job.status != "review_required":
        raise ReviewRouteError(status_code=409, detail="review_job_not_pending")

    event_payload = {
        "dispatchType": current_job.dispatch_type,
        "reviewDecision": normalized_decision,
        "reviewActor": str(actor or "").strip() or "system",
        "reviewReason": str(reason or "").strip() or None,
    }
    resolved_alert_ids: list[str] = []
    if normalized_decision == "approve":
        event_payload["judgeCoreStage"] = "review_approved"
        await workflow_mark_completed(
            job_id=case_id,
            event_payload=event_payload,
        )
        transitioned = await workflow_get_job(job_id=case_id)
        if transitioned is None:
            raise LookupError("review_job_not_found")
        resolved_alert_ids = await resolve_open_alerts_for_review(
            job_id=case_id,
            actor=event_payload["reviewActor"],
            reason=event_payload["reviewReason"] or "review_approved",
        )
    else:
        reject_reason = event_payload["reviewReason"] or "review rejected by reviewer"
        event_payload["judgeCoreStage"] = "review_rejected"
        await workflow_mark_failed(
            job_id=case_id,
            error_code="review_rejected",
            error_message=reject_reason,
            event_payload=event_payload,
        )
        transitioned = await workflow_get_job(job_id=case_id)
        if transitioned is None:
            raise LookupError("review_job_not_found")
    return {
        "ok": True,
        "job": serialize_workflow_job(transitioned),
        "decision": normalized_decision,
        "resolvedAlertIds": resolved_alert_ids,
    }


async def build_case_alerts_payload(
    *,
    case_id: int,
    status: str | None,
    limit: int,
    list_audit_alerts: Callable[..., Awaitable[list[Any]]],
    serialize_alert_item: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    items = await list_audit_alerts(
        job_id=case_id,
        status=status,
        limit=limit,
    )
    return {
        "caseId": case_id,
        "count": len(items),
        "items": [serialize_alert_item(item) for item in items],
    }


async def build_alert_status_transition_payload(
    *,
    job_id: int,
    alert_id: str,
    to_status: str,
    actor: str | None,
    reason: str | None,
    transition_audit_alert: Callable[..., Any | None],
    sync_audit_alert_to_facts: Callable[..., Awaitable[None]],
    facts_transition_audit_alert: Callable[..., Awaitable[Any | None]],
    serialize_alert_item: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    row = transition_audit_alert(
        job_id=job_id,
        alert_id=alert_id,
        to_status=to_status,
        actor=actor,
        reason=reason,
    )
    if row is None:
        raise ReviewRouteError(status_code=409, detail="invalid_alert_status_transition")
    await sync_audit_alert_to_facts(alert=row)
    transitioned = await facts_transition_audit_alert(
        alert_id=alert_id,
        to_status=to_status,
        now=row.updated_at,
    )
    if transitioned is None:
        raise ReviewRouteError(status_code=409, detail="invalid_alert_status_transition")
    return {
        "ok": True,
        "caseId": job_id,
        "alertId": alert_id,
        "status": transitioned.status,
        "item": serialize_alert_item(transitioned),
    }


async def build_alert_ops_view_payload(
    *,
    alert_type: str | None,
    status: str | None,
    delivery_status: str | None,
    registry_type: str | None,
    policy_version: str | None,
    gate_code: str | None,
    gate_actor: str | None,
    override_applied: bool | None,
    fields_mode: str,
    include_trend: bool,
    trend_window_minutes: int,
    trend_bucket_minutes: int,
    offset: int,
    limit: int,
    normalize_ops_alert_status: Callable[[str | None], str | None],
    normalize_ops_alert_delivery_status: Callable[[str | None], str | None],
    normalize_ops_alert_fields_mode: Callable[[str], str],
    ops_registry_alert_types: set[str] | frozenset[str],
    ops_alert_status_values: set[str] | frozenset[str],
    ops_alert_delivery_status_values: set[str] | frozenset[str],
    ops_alert_fields_mode_values: set[str] | frozenset[str],
    list_audit_alerts: Callable[..., Awaitable[list[Any]]],
    list_alert_outbox: Callable[..., list[Any]],
    build_registry_alert_ops_view: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    normalized_alert_type = str(alert_type or "").strip() or None
    if (
        normalized_alert_type is not None
        and normalized_alert_type not in ops_registry_alert_types
    ):
        raise ValueError("invalid_alert_type")
    normalized_status = normalize_ops_alert_status(status)
    if normalized_status is not None and normalized_status not in ops_alert_status_values:
        raise ValueError("invalid_alert_status")
    normalized_delivery_status = normalize_ops_alert_delivery_status(delivery_status)
    if (
        normalized_delivery_status is not None
        and normalized_delivery_status not in ops_alert_delivery_status_values
    ):
        raise ValueError("invalid_delivery_status")
    normalized_fields_mode = normalize_ops_alert_fields_mode(fields_mode)
    if normalized_fields_mode not in ops_alert_fields_mode_values:
        raise ValueError("invalid_fields_mode")

    alerts = await list_audit_alerts(job_id=0, status=None, limit=5000)
    outbox_events = list_alert_outbox(limit=200)
    return build_registry_alert_ops_view(
        alerts=alerts,
        outbox_events=outbox_events,
        alert_type=normalized_alert_type,
        status=normalized_status,
        delivery_status=normalized_delivery_status,
        registry_type=registry_type,
        policy_version=policy_version,
        gate_code=gate_code,
        gate_actor=gate_actor,
        override_applied=override_applied,
        fields_mode=normalized_fields_mode,
        include_trend=include_trend,
        trend_window_minutes=trend_window_minutes,
        trend_bucket_minutes=trend_bucket_minutes,
        offset=offset,
        limit=limit,
    )


def build_alert_outbox_list_payload(
    *,
    rows: list[Any],
    delivery_status: str | None,
    limit: int,
    serialize_outbox_event: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    return {
        "count": len(rows),
        "items": [serialize_outbox_event(item) for item in rows],
        "filters": {
            "deliveryStatus": delivery_status,
            "limit": limit,
        },
    }


def build_alert_outbox_route_payload(
    *,
    delivery_status: str | None,
    limit: int,
    list_alert_outbox: Callable[..., list[Any]],
    serialize_outbox_event: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    rows = list_alert_outbox(
        delivery_status=delivery_status,
        limit=limit,
    )
    return build_alert_outbox_list_payload(
        rows=rows,
        delivery_status=delivery_status,
        limit=limit,
        serialize_outbox_event=serialize_outbox_event,
    )


def build_alert_outbox_delivery_payload(
    *,
    item: Any | None,
    serialize_outbox_event: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    if item is None:
        raise LookupError("alert_outbox_event_not_found")
    return {
        "ok": True,
        "item": serialize_outbox_event(item),
    }


def build_rag_diagnostics_payload(
    *,
    case_id: int,
    get_trace: Callable[[int], Any | None],
) -> dict[str, Any]:
    record = get_trace(case_id)
    if record is None:
        raise LookupError("judge_trace_not_found")
    report_summary = (
        record.report_summary if isinstance(record.report_summary, dict) else {}
    )
    payload = report_summary.get("payload") if isinstance(report_summary.get("payload"), dict) else {}
    return {
        "caseId": case_id,
        "traceId": record.trace_id,
        "retrievalDiagnostics": payload.get("retrievalDiagnostics"),
        "ragSources": payload.get("ragSources"),
        "ragBackend": payload.get("ragBackend"),
        "ragRequestedBackend": payload.get("ragRequestedBackend"),
        "ragBackendFallbackReason": payload.get("ragBackendFallbackReason"),
    }
