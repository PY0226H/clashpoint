from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class TrustChallengeOpsQueueRouteError(Exception):
    def __init__(self, *, status_code: int, detail: Any):
        super().__init__(str(detail))
        self.status_code = int(status_code)
        self.detail = detail


async def build_trust_challenge_ops_queue_route_payload(
    *,
    status: str | None,
    dispatch_type: str,
    challenge_state: str | None,
    review_state: str | None,
    priority_level: str | None,
    sla_bucket: str | None,
    has_open_alert: bool | None,
    sort_by: str,
    sort_order: str,
    scan_limit: int,
    offset: int,
    limit: int,
    normalize_workflow_status: Any,
    workflow_statuses: set[str],
    normalize_trust_challenge_state_filter: Any,
    case_fairness_challenge_states: set[str],
    normalize_trust_challenge_review_state: Any,
    trust_challenge_review_state_values: set[str],
    normalize_trust_challenge_priority_level: Any,
    trust_challenge_priority_level_values: set[str],
    normalize_trust_challenge_sla_bucket: Any,
    trust_challenge_sla_bucket_values: set[str],
    normalize_trust_challenge_sort_by: Any,
    trust_challenge_sort_fields: set[str],
    normalize_trust_challenge_sort_order: Any,
    trust_challenge_open_states: set[str],
    workflow_list_jobs: Any,
    build_trust_phasea_bundle: Any,
    get_trace: Any,
    build_trust_challenge_priority_profile: Any,
    serialize_workflow_job: Any,
    build_trust_challenge_ops_queue_item: Any,
    build_trust_challenge_action_hints: Any,
    build_trust_challenge_sort_key: Any,
    build_trust_challenge_ops_queue_payload: Any,
    validate_trust_challenge_ops_queue_contract: Any,
) -> dict[str, Any]:
    normalized_status = normalize_workflow_status(status)
    if normalized_status is not None and normalized_status not in workflow_statuses:
        raise TrustChallengeOpsQueueRouteError(
            status_code=422,
            detail="invalid_workflow_status",
        )
    normalized_dispatch_type = str(dispatch_type or "").strip().lower() or "auto"
    if normalized_dispatch_type not in {"auto", "phase", "final"}:
        raise TrustChallengeOpsQueueRouteError(
            status_code=422,
            detail="invalid_dispatch_type",
        )
    workflow_dispatch_filter = (
        None if normalized_dispatch_type == "auto" else normalized_dispatch_type
    )

    normalized_challenge_state = normalize_trust_challenge_state_filter(challenge_state)
    if (
        normalized_challenge_state is not None
        and normalized_challenge_state != "open"
        and normalized_challenge_state not in case_fairness_challenge_states
    ):
        raise TrustChallengeOpsQueueRouteError(
            status_code=422,
            detail="invalid_trust_challenge_state",
        )
    normalized_review_state = normalize_trust_challenge_review_state(review_state)
    if (
        normalized_review_state is not None
        and normalized_review_state not in trust_challenge_review_state_values
    ):
        raise TrustChallengeOpsQueueRouteError(
            status_code=422,
            detail="invalid_trust_review_state",
        )
    normalized_priority_level = normalize_trust_challenge_priority_level(priority_level)
    if (
        normalized_priority_level is not None
        and normalized_priority_level not in trust_challenge_priority_level_values
    ):
        raise TrustChallengeOpsQueueRouteError(
            status_code=422,
            detail="invalid_trust_priority_level",
        )
    normalized_sla_bucket = normalize_trust_challenge_sla_bucket(sla_bucket)
    if (
        normalized_sla_bucket is not None
        and normalized_sla_bucket not in trust_challenge_sla_bucket_values
    ):
        raise TrustChallengeOpsQueueRouteError(
            status_code=422,
            detail="invalid_trust_sla_bucket",
        )
    normalized_sort_by = normalize_trust_challenge_sort_by(sort_by)
    if normalized_sort_by not in trust_challenge_sort_fields:
        raise TrustChallengeOpsQueueRouteError(status_code=422, detail="invalid_trust_sort_by")
    normalized_sort_order = normalize_trust_challenge_sort_order(sort_order)
    if normalized_sort_order not in {"asc", "desc"}:
        raise TrustChallengeOpsQueueRouteError(
            status_code=422,
            detail="invalid_trust_sort_order",
        )
    normalized_scan_limit = max(20, min(int(scan_limit), 2000))
    normalized_offset = max(0, int(offset))
    normalized_limit = max(1, min(int(limit), 200))

    jobs = await workflow_list_jobs(
        status=normalized_status,
        dispatch_type=workflow_dispatch_filter,
        limit=normalized_scan_limit,
    )
    now = datetime.now(timezone.utc)
    items: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for job in jobs:
        try:
            bundle = await build_trust_phasea_bundle(
                case_id=job.job_id,
                dispatch_type=normalized_dispatch_type,
            )
        except Exception as err:  # noqa: BLE001
            status_code = int(getattr(err, "status_code", 500) or 500)
            detail = getattr(err, "detail", "")
            error_code = str(detail or "").strip() or "trust_case_unavailable"
            if error_code in {"trust_receipt_not_found", "trust_report_payload_missing"}:
                errors.append(
                    {
                        "caseId": int(job.job_id),
                        "statusCode": status_code,
                        "errorCode": error_code,
                    }
                )
                continue
            raise

        challenge_review = (
            bundle.get("challengeReview")
            if isinstance(bundle.get("challengeReview"), dict)
            else {}
        )
        current_challenge_state = (
            str(challenge_review.get("challengeState") or "").strip().lower() or None
        )
        if normalized_challenge_state == "open":
            if current_challenge_state not in trust_challenge_open_states:
                continue
        elif (
            normalized_challenge_state is not None
            and current_challenge_state != normalized_challenge_state
        ):
            continue

        current_review_state = (
            str(challenge_review.get("reviewState") or "").strip().lower() or None
        )
        if (
            normalized_review_state is not None
            and current_review_state != normalized_review_state
        ):
            continue

        context = bundle["context"] if isinstance(bundle.get("context"), dict) else {}
        report_payload = (
            context.get("reportPayload")
            if isinstance(context.get("reportPayload"), dict)
            else {}
        )
        trace = get_trace(job.job_id)
        report_summary = (
            trace.report_summary if trace and isinstance(trace.report_summary, dict) else {}
        )
        priority_profile = build_trust_challenge_priority_profile(
            workflow=job,
            challenge_review=challenge_review,
            report_payload=report_payload,
            report_summary=report_summary,
            now=now,
        )
        if (
            normalized_priority_level is not None
            and str(priority_profile.get("level") or "").strip().lower()
            != normalized_priority_level
        ):
            continue
        if (
            normalized_sla_bucket is not None
            and str(priority_profile.get("slaBucket") or "").strip().lower()
            != normalized_sla_bucket
        ):
            continue
        if (
            has_open_alert is not None
            and (int(priority_profile.get("openAlertCount") or 0) > 0)
            != bool(has_open_alert)
        ):
            continue

        active_challenge_id = str(challenge_review.get("activeChallengeId") or "").strip() or None
        workflow_payload = serialize_workflow_job(job)
        trace_payload = {
            "status": trace.status if trace is not None else None,
            "callbackStatus": (
                report_summary.get("callbackStatus")
                or (trace.callback_status if trace is not None else None)
            ),
            "callbackError": (
                report_summary.get("callbackError")
                or (trace.callback_error if trace is not None else None)
            ),
            "updatedAt": trace.updated_at.isoformat() if trace is not None else None,
        }
        item_payload = build_trust_challenge_ops_queue_item(
            case_id=int(job.job_id),
            dispatch_type=context.get("dispatchType"),
            trace_id=context.get("traceId"),
            workflow=workflow_payload,
            trace_payload=trace_payload,
            challenge_review=challenge_review,
            priority_profile=priority_profile,
            active_challenge_id=active_challenge_id,
        )
        item_payload["actionHints"] = build_trust_challenge_action_hints(
            challenge_review=item_payload["challengeReview"],
            priority_profile=priority_profile,
        )
        items.append(item_payload)

    items.sort(
        key=lambda row: build_trust_challenge_sort_key(
            item=row,
            sort_by=normalized_sort_by,
        ),
        reverse=(normalized_sort_order == "desc"),
    )
    page_items = items[normalized_offset : normalized_offset + normalized_limit]

    payload = build_trust_challenge_ops_queue_payload(
        items=items,
        page_items=page_items,
        jobs_count=len(jobs),
        errors=errors,
        filters={
            "status": normalized_status,
            "dispatchType": normalized_dispatch_type,
            "challengeState": normalized_challenge_state,
            "reviewState": normalized_review_state,
            "priorityLevel": normalized_priority_level,
            "slaBucket": normalized_sla_bucket,
            "hasOpenAlert": has_open_alert,
            "sortBy": normalized_sort_by,
            "sortOrder": normalized_sort_order,
            "scanLimit": normalized_scan_limit,
            "offset": normalized_offset,
            "limit": normalized_limit,
        },
    )
    try:
        validate_trust_challenge_ops_queue_contract(payload)
    except ValueError as err:
        raise TrustChallengeOpsQueueRouteError(
            status_code=500,
            detail={
                "code": "trust_challenge_ops_queue_contract_violation",
                "message": str(err),
            },
        ) from err
    return payload
