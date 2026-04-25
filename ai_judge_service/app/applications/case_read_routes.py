from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from .trust_artifact_summary import (
    build_trust_artifact_summary_from_registry_snapshot,
    build_trust_artifact_summary_from_report_payload,
)


@dataclass(frozen=True)
class CaseReadRouteError(Exception):
    status_code: int
    detail: Any


@dataclass
class CaseReadTraceReplayItem:
    replayed_at: datetime
    winner: str | None
    needs_draw_vote: bool | None
    provider: str | None


@dataclass
class CaseReadReplayRecord:
    dispatch_type: str | None
    trace_id: str | None
    created_at: datetime
    winner: str | None
    needs_draw_vote: bool | None
    provider: str | None


async def build_case_trust_artifact_summary(
    *,
    case_id: int,
    latest_dispatch_type: str | None,
    trace_id: str | None,
    report_payload: dict[str, Any],
    get_trust_registry_snapshot: Callable[..., Awaitable[Any | None]] | None = None,
) -> dict[str, Any]:
    if get_trust_registry_snapshot is not None:
        dispatch_candidates = (
            [latest_dispatch_type]
            if latest_dispatch_type in {"final", "phase"}
            else ["final", "phase"]
        )
        for dispatch_type in dispatch_candidates:
            snapshot = await get_trust_registry_snapshot(
                case_id=case_id,
                dispatch_type=dispatch_type,
            )
            if snapshot is not None:
                return build_trust_artifact_summary_from_registry_snapshot(
                    snapshot=snapshot,
                    include_artifact_refs=True,
                )

    return build_trust_artifact_summary_from_report_payload(
        report_payload=report_payload,
        case_id=case_id,
        dispatch_type=latest_dispatch_type,
        trace_id=trace_id,
        include_artifact_refs=True,
    )


def _raise_route_error_from_http_exception(err: Exception) -> None:
    status_code = getattr(err, "status_code", None)
    detail = getattr(err, "detail", None)
    if isinstance(status_code, int):
        raise CaseReadRouteError(status_code=status_code, detail=detail) from err
    if status_code is not None:
        try:
            normalized_status_code = int(status_code)
        except (TypeError, ValueError):
            return
        raise CaseReadRouteError(
            status_code=normalized_status_code,
            detail=detail,
        ) from err


async def build_case_overview_route_payload(
    *,
    case_id: int,
    workflow_get_job: Callable[..., Awaitable[Any | None]],
    workflow_list_events: Callable[..., Awaitable[list[Any]]],
    get_dispatch_receipt: Callable[..., Awaitable[Any | None]],
    trace_get: Callable[[int], Any | None],
    list_replay_records: Callable[..., Awaitable[list[Any]]],
    list_audit_alerts: Callable[..., Awaitable[list[Any]]],
    get_claim_ledger_record: Callable[..., Awaitable[Any | None]],
    build_verdict_contract: Callable[[dict[str, Any]], dict[str, Any]],
    build_case_evidence_view: Callable[..., dict[str, Any]],
    build_judge_core_view: Callable[..., dict[str, Any] | None],
    build_case_overview_replay_items: Callable[..., list[dict[str, Any]]],
    build_case_overview_payload: Callable[..., dict[str, Any]],
    serialize_workflow_job: Callable[[Any], dict[str, Any]],
    serialize_dispatch_receipt: Callable[[Any], dict[str, Any]],
    serialize_alert_item: Callable[[Any], dict[str, Any]],
    get_trust_registry_snapshot: Callable[..., Awaitable[Any | None]] | None = None,
) -> dict[str, Any]:
    workflow_job = await workflow_get_job(job_id=case_id)
    workflow_events = (
        await workflow_list_events(job_id=case_id) if workflow_job is not None else []
    )
    final_receipt = await get_dispatch_receipt(dispatch_type="final", job_id=case_id)
    phase_receipt = await get_dispatch_receipt(dispatch_type="phase", job_id=case_id)
    trace = trace_get(case_id)
    replay_records = await list_replay_records(job_id=case_id, limit=50)
    alerts = await list_audit_alerts(job_id=case_id, status=None, limit=200)
    claim_ledger_record = await get_claim_ledger_record(
        case_id=case_id,
        dispatch_type=None,
    )
    if (
        workflow_job is None
        and final_receipt is None
        and phase_receipt is None
        and trace is None
        and not replay_records
        and not alerts
        and claim_ledger_record is None
    ):
        raise CaseReadRouteError(status_code=404, detail="case_not_found")

    report_summary = (
        trace.report_summary if trace and isinstance(trace.report_summary, dict) else {}
    )
    final_response = (
        final_receipt.response
        if final_receipt and isinstance(final_receipt.response, dict)
        else {}
    )
    phase_response = (
        phase_receipt.response
        if phase_receipt and isinstance(phase_receipt.response, dict)
        else {}
    )
    summary_payload = (
        report_summary.get("payload")
        if isinstance(report_summary.get("payload"), dict)
        else {}
    )
    final_report_payload = (
        final_response.get("reportPayload")
        if isinstance(final_response.get("reportPayload"), dict)
        else {}
    )
    phase_report_payload = (
        phase_response.get("reportPayload")
        if isinstance(phase_response.get("reportPayload"), dict)
        else {}
    )
    report_payload = final_report_payload or summary_payload or phase_report_payload
    verdict_contract = build_verdict_contract(report_payload)
    case_evidence = build_case_evidence_view(
        report_payload=report_payload,
        verdict_contract=verdict_contract,
        claim_ledger_record=claim_ledger_record,
    )
    winner_raw = (
        report_summary.get("winner")
        or verdict_contract.get("winner")
        or final_response.get("winner")
        or phase_response.get("winner")
    )
    winner = str(winner_raw or "").strip().lower() or None
    callback_status = (
        report_summary.get("callbackStatus")
        or (trace.callback_status if trace is not None else None)
        or final_response.get("callbackStatus")
        or phase_response.get("callbackStatus")
    )
    callback_error = (
        report_summary.get("callbackError")
        or (trace.callback_error if trace is not None else None)
        or final_response.get("callbackError")
        or phase_response.get("callbackError")
    )
    judge_core_view = build_judge_core_view(
        workflow_job=workflow_job,
        workflow_events=workflow_events,
    )
    replay_items = build_case_overview_replay_items(
        replay_records=replay_records,
        trace=trace,
    )
    latest_dispatch_type = (
        "final"
        if final_receipt is not None
        else ("phase" if phase_receipt is not None else None)
    )
    trace_id = (
        str(trace.trace_id).strip()
        if trace is not None and str(getattr(trace, "trace_id", "") or "").strip()
        else None
    )
    trust_artifact_summary = await build_case_trust_artifact_summary(
        case_id=case_id,
        latest_dispatch_type=latest_dispatch_type,
        trace_id=trace_id,
        report_payload=report_payload,
        get_trust_registry_snapshot=get_trust_registry_snapshot,
    )
    return build_case_overview_payload(
        case_id=case_id,
        workflow=serialize_workflow_job(workflow_job) if workflow_job else None,
        trace=(
            {
                "traceId": trace.trace_id,
                "status": trace.status,
                "createdAt": trace.created_at.isoformat(),
                "updatedAt": trace.updated_at.isoformat(),
            }
            if trace is not None
            else None
        ),
        receipts={
            "phase": serialize_dispatch_receipt(phase_receipt) if phase_receipt else None,
            "final": serialize_dispatch_receipt(final_receipt) if final_receipt else None,
        },
        latest_dispatch_type=latest_dispatch_type,
        report_payload=report_payload,
        verdict_contract=verdict_contract,
        case_evidence=case_evidence,
        winner=winner,
        needs_draw_vote=(
            verdict_contract.get("needsDrawVote")
            if verdict_contract.get("needsDrawVote") is not None
            else (winner == "draw" if winner is not None else None)
        ),
        review_required=bool(verdict_contract.get("reviewRequired")),
        callback_status=callback_status,
        callback_error=callback_error,
        judge_core=judge_core_view,
        events=[
            {
                "eventSeq": item.event_seq,
                "eventType": item.event_type,
                "payload": item.payload,
                "createdAt": item.created_at.isoformat(),
            }
            for item in workflow_events
        ],
        alerts=[serialize_alert_item(item) for item in alerts],
        replays=replay_items,
        trust_artifact_summary=trust_artifact_summary,
    )


async def build_case_claim_ledger_route_payload(
    *,
    case_id: int,
    dispatch_type: str,
    limit: int,
    list_claim_ledger_records: Callable[..., Awaitable[list[Any]]],
    get_claim_ledger_record: Callable[..., Awaitable[Any | None]],
    serialize_claim_ledger_record: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    normalized_dispatch_type = str(dispatch_type or "").strip().lower() or "auto"
    if normalized_dispatch_type not in {"auto", "phase", "final"}:
        raise CaseReadRouteError(status_code=422, detail="invalid_dispatch_type")

    normalized_limit = max(1, min(int(limit), 200))
    if normalized_dispatch_type == "auto":
        records = await list_claim_ledger_records(case_id=case_id, limit=normalized_limit)
        if not records:
            raise CaseReadRouteError(status_code=404, detail="claim_ledger_not_found")
        primary = records[0]
    else:
        primary = await get_claim_ledger_record(
            case_id=case_id,
            dispatch_type=normalized_dispatch_type,
        )
        if primary is None:
            raise CaseReadRouteError(status_code=404, detail="claim_ledger_not_found")
        records = [primary]

    return {
        "caseId": case_id,
        "dispatchType": primary.dispatch_type,
        "traceId": primary.trace_id,
        "count": len(records),
        "item": serialize_claim_ledger_record(primary, include_payload=True),
        "items": [
            serialize_claim_ledger_record(row, include_payload=False) for row in records
        ],
    }


async def build_case_courtroom_read_model_route_payload(
    *,
    case_id: int,
    dispatch_type: str,
    include_events: bool,
    include_alerts: bool,
    alert_limit: int,
    resolve_report_context_for_case: Callable[..., Awaitable[dict[str, Any]]],
    workflow_get_job: Callable[..., Awaitable[Any | None]],
    workflow_list_events: Callable[..., Awaitable[list[Any]]],
    trace_get: Callable[[int], Any | None],
    get_claim_ledger_record: Callable[..., Awaitable[Any | None]],
    build_verdict_contract: Callable[[dict[str, Any]], dict[str, Any]],
    build_case_evidence_view: Callable[..., dict[str, Any]],
    build_courtroom_read_model_view: Callable[..., dict[str, Any]],
    build_judge_core_view: Callable[..., dict[str, Any] | None],
    list_audit_alerts: Callable[..., Awaitable[list[Any]]],
    build_case_courtroom_read_model_payload: Callable[..., dict[str, Any]],
    serialize_workflow_job: Callable[[Any], dict[str, Any]],
    serialize_alert_item: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    try:
        context = await resolve_report_context_for_case(
            case_id=case_id,
            dispatch_type=dispatch_type,
            not_found_detail="courtroom_case_not_found",
            missing_report_detail="courtroom_report_payload_missing",
        )
    except Exception as err:
        _raise_route_error_from_http_exception(err)
        raise

    workflow_job = await workflow_get_job(job_id=case_id)
    workflow_events = list(await workflow_list_events(job_id=case_id))
    trace = trace_get(case_id)
    report_summary = (
        trace.report_summary if trace and isinstance(trace.report_summary, dict) else {}
    )
    callback_status = (
        report_summary.get("callbackStatus")
        or context["responsePayload"].get("callbackStatus")
        or (trace.callback_status if trace is not None else None)
    )
    callback_error = (
        report_summary.get("callbackError")
        or context["responsePayload"].get("callbackError")
        or (trace.callback_error if trace is not None else None)
    )
    claim_ledger_record = await get_claim_ledger_record(
        case_id=case_id,
        dispatch_type=context["dispatchType"],
    )
    verdict_contract = build_verdict_contract(context["reportPayload"])
    case_evidence = build_case_evidence_view(
        report_payload=context["reportPayload"],
        verdict_contract=verdict_contract,
        claim_ledger_record=claim_ledger_record,
    )
    courtroom_read_model = build_courtroom_read_model_view(
        report_payload=context["reportPayload"],
        case_evidence=case_evidence,
    )
    judge_core_view = build_judge_core_view(
        workflow_job=workflow_job,
        workflow_events=workflow_events,
    )
    normalized_alert_limit = max(1, min(int(alert_limit), 500))
    alert_items = (
        await list_audit_alerts(job_id=case_id, status=None, limit=normalized_alert_limit)
        if include_alerts
        else []
    )

    return build_case_courtroom_read_model_payload(
        case_id=case_id,
        dispatch_type=context["dispatchType"],
        trace_id=context["traceId"] or None,
        workflow=serialize_workflow_job(workflow_job) if workflow_job is not None else None,
        judge_core=judge_core_view,
        callback_status=callback_status,
        callback_error=callback_error,
        report_payload=context["reportPayload"],
        courtroom=courtroom_read_model,
        events=[
            {
                "eventSeq": item.event_seq,
                "eventType": item.event_type,
                "payload": item.payload,
                "createdAt": item.created_at.isoformat(),
            }
            for item in workflow_events
        ],
        event_count=len(workflow_events),
        alerts=[serialize_alert_item(item) for item in alert_items],
        include_events=bool(include_events),
        include_alerts=bool(include_alerts),
        alert_limit=normalized_alert_limit,
    )


async def build_case_courtroom_cases_route_payload(
    *,
    status: str | None,
    dispatch_type: str,
    winner: str | None,
    review_required: bool | None,
    risk_level: str | None,
    sla_bucket: str | None,
    updated_from: datetime | None,
    updated_to: datetime | None,
    sort_by: str,
    sort_order: str,
    scan_limit: int,
    offset: int,
    limit: int,
    normalize_workflow_status: Callable[[str | None], str | None],
    workflow_statuses: set[str],
    normalize_review_case_risk_level: Callable[[str | None], str | None],
    review_case_risk_level_values: set[str],
    normalize_review_case_sla_bucket: Callable[[str | None], str | None],
    review_case_sla_bucket_values: set[str],
    normalize_query_datetime: Callable[[datetime | None], datetime | None],
    normalize_courtroom_case_sort_by: Callable[[str | None], str],
    normalize_courtroom_case_sort_order: Callable[[str | None], str],
    courtroom_case_sort_fields: set[str],
    workflow_list_jobs: Callable[..., Awaitable[list[Any]]],
    resolve_report_context_for_case: Callable[..., Awaitable[dict[str, Any]]],
    trace_get: Callable[[int], Any | None],
    build_review_case_risk_profile: Callable[..., dict[str, Any]],
    build_verdict_contract: Callable[[dict[str, Any]], dict[str, Any]],
    build_case_evidence_view: Callable[..., dict[str, Any]],
    build_courtroom_read_model_view: Callable[..., dict[str, Any]],
    serialize_workflow_job: Callable[[Any], dict[str, Any]],
    build_courtroom_read_model_light_summary: Callable[..., dict[str, Any]],
    build_courtroom_case_sort_key: Callable[..., tuple[Any, ...]],
) -> dict[str, Any]:
    normalized_status = normalize_workflow_status(status)
    if normalized_status is not None and normalized_status not in workflow_statuses:
        raise CaseReadRouteError(status_code=422, detail="invalid_workflow_status")

    normalized_dispatch_type = str(dispatch_type or "").strip().lower() or "auto"
    if normalized_dispatch_type not in {"auto", "phase", "final"}:
        raise CaseReadRouteError(status_code=422, detail="invalid_dispatch_type")
    workflow_dispatch_filter = (
        None if normalized_dispatch_type == "auto" else normalized_dispatch_type
    )

    normalized_winner = str(winner or "").strip().lower() or None
    if normalized_winner not in {None, "pro", "con", "draw"}:
        raise CaseReadRouteError(status_code=422, detail="invalid_winner")

    normalized_risk_level = normalize_review_case_risk_level(risk_level)
    if (
        normalized_risk_level is not None
        and normalized_risk_level not in review_case_risk_level_values
    ):
        raise CaseReadRouteError(status_code=422, detail="invalid_review_risk_level")

    normalized_sla_bucket = normalize_review_case_sla_bucket(sla_bucket)
    if (
        normalized_sla_bucket is not None
        and normalized_sla_bucket not in review_case_sla_bucket_values
    ):
        raise CaseReadRouteError(status_code=422, detail="invalid_review_sla_bucket")

    normalized_updated_from = normalize_query_datetime(updated_from)
    normalized_updated_to = normalize_query_datetime(updated_to)
    if (
        normalized_updated_from is not None
        and normalized_updated_to is not None
        and normalized_updated_from > normalized_updated_to
    ):
        raise CaseReadRouteError(status_code=422, detail="invalid_updated_time_window")

    normalized_sort_by = normalize_courtroom_case_sort_by(sort_by)
    if normalized_sort_by not in courtroom_case_sort_fields:
        raise CaseReadRouteError(status_code=422, detail="invalid_courtroom_sort_by")
    normalized_sort_order = normalize_courtroom_case_sort_order(sort_order)
    if normalized_sort_order not in {"asc", "desc"}:
        raise CaseReadRouteError(status_code=422, detail="invalid_courtroom_sort_order")

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
        updated_at = normalize_query_datetime(job.updated_at)
        if (
            normalized_updated_from is not None
            and (updated_at is None or updated_at < normalized_updated_from)
        ):
            continue
        if (
            normalized_updated_to is not None
            and (updated_at is None or updated_at > normalized_updated_to)
        ):
            continue

        try:
            context = await resolve_report_context_for_case(
                case_id=job.job_id,
                dispatch_type=normalized_dispatch_type,
                not_found_detail="courtroom_case_not_found",
                missing_report_detail="courtroom_report_payload_missing",
            )
        except Exception as err:
            status_code = getattr(err, "status_code", None)
            detail = getattr(err, "detail", None)
            if not isinstance(status_code, int):
                try:
                    status_code = int(status_code)
                except (TypeError, ValueError):
                    raise
            error_code = str(detail or "").strip() or "courtroom_case_unavailable"
            if error_code in {
                "courtroom_case_not_found",
                "courtroom_report_payload_missing",
            }:
                errors.append(
                    {
                        "caseId": int(job.job_id),
                        "statusCode": int(status_code),
                        "errorCode": error_code,
                    }
                )
                continue
            _raise_route_error_from_http_exception(err)
            raise

        report_payload = (
            context.get("reportPayload")
            if isinstance(context.get("reportPayload"), dict)
            else {}
        )
        winner_value = str(report_payload.get("winner") or "").strip().lower() or None
        if normalized_winner is not None and winner_value != normalized_winner:
            continue
        report_review_required = bool(report_payload.get("reviewRequired"))
        if review_required is not None and report_review_required != bool(review_required):
            continue

        trace = trace_get(job.job_id)
        report_summary = (
            trace.report_summary if trace and isinstance(trace.report_summary, dict) else {}
        )
        risk_profile = build_review_case_risk_profile(
            workflow=job,
            report_payload=report_payload,
            report_summary=report_summary,
            now=now,
        )
        if (
            normalized_risk_level is not None
            and str(risk_profile.get("level") or "").strip().lower() != normalized_risk_level
        ):
            continue
        if (
            normalized_sla_bucket is not None
            and str(risk_profile.get("slaBucket") or "").strip().lower()
            != normalized_sla_bucket
        ):
            continue

        verdict_contract = build_verdict_contract(report_payload)
        case_evidence = build_case_evidence_view(
            report_payload=report_payload,
            verdict_contract=verdict_contract,
            claim_ledger_record=None,
        )
        courtroom_view = build_courtroom_read_model_view(
            report_payload=report_payload,
            case_evidence=case_evidence,
        )
        response_payload = (
            context.get("responsePayload")
            if isinstance(context.get("responsePayload"), dict)
            else {}
        )
        callback_status = (
            report_summary.get("callbackStatus")
            or response_payload.get("callbackStatus")
            or (trace.callback_status if trace is not None else None)
        )
        callback_error = (
            report_summary.get("callbackError")
            or response_payload.get("callbackError")
            or (trace.callback_error if trace is not None else None)
        )

        items.append(
            {
                "caseId": int(job.job_id),
                "dispatchType": context.get("dispatchType"),
                "traceId": context.get("traceId") or None,
                "workflow": serialize_workflow_job(job),
                "winner": winner_value,
                "reviewRequired": report_review_required,
                "needsDrawVote": bool(report_payload.get("needsDrawVote")),
                "callbackStatus": callback_status,
                "callbackError": callback_error,
                "riskProfile": risk_profile,
                "courtroomSummary": build_courtroom_read_model_light_summary(
                    courtroom_view=courtroom_view,
                ),
            }
        )

    items.sort(
        key=lambda row: build_courtroom_case_sort_key(
            item=row,
            sort_by=normalized_sort_by,
        ),
        reverse=(normalized_sort_order == "desc"),
    )
    page_items = items[normalized_offset : normalized_offset + normalized_limit]

    return {
        "count": len(items),
        "returned": len(page_items),
        "scanned": len(jobs),
        "skipped": max(0, len(jobs) - len(items)),
        "errorCount": len(errors),
        "items": page_items,
        "errors": errors,
        "filters": {
            "status": normalized_status,
            "dispatchType": normalized_dispatch_type,
            "winner": normalized_winner,
            "reviewRequired": review_required,
            "riskLevel": normalized_risk_level,
            "slaBucket": normalized_sla_bucket,
            "updatedFrom": (
                normalized_updated_from.isoformat()
                if normalized_updated_from is not None
                else None
            ),
            "updatedTo": (
                normalized_updated_to.isoformat()
                if normalized_updated_to is not None
                else None
            ),
            "sortBy": normalized_sort_by,
            "sortOrder": normalized_sort_order,
            "scanLimit": normalized_scan_limit,
            "offset": normalized_offset,
            "limit": normalized_limit,
        },
    }


async def build_case_courtroom_drilldown_bundle_route_payload(
    *,
    status: str | None,
    dispatch_type: str,
    winner: str | None,
    review_required: bool | None,
    risk_level: str | None,
    sla_bucket: str | None,
    updated_from: datetime | None,
    updated_to: datetime | None,
    sort_by: str,
    sort_order: str,
    scan_limit: int,
    offset: int,
    limit: int,
    claim_preview_limit: int,
    evidence_preview_limit: int,
    panel_preview_limit: int,
    normalize_workflow_status: Callable[[str | None], str | None],
    workflow_statuses: set[str],
    normalize_review_case_risk_level: Callable[[str | None], str | None],
    review_case_risk_level_values: set[str],
    normalize_review_case_sla_bucket: Callable[[str | None], str | None],
    review_case_sla_bucket_values: set[str],
    normalize_query_datetime: Callable[[datetime | None], datetime | None],
    normalize_courtroom_case_sort_by: Callable[[str | None], str],
    normalize_courtroom_case_sort_order: Callable[[str | None], str],
    courtroom_case_sort_fields: set[str],
    workflow_list_jobs: Callable[..., Awaitable[list[Any]]],
    resolve_report_context_for_case: Callable[..., Awaitable[dict[str, Any]]],
    trace_get: Callable[[int], Any | None],
    build_review_case_risk_profile: Callable[..., dict[str, Any]],
    build_verdict_contract: Callable[[dict[str, Any]], dict[str, Any]],
    build_case_evidence_view: Callable[..., dict[str, Any]],
    build_courtroom_read_model_view: Callable[..., dict[str, Any]],
    build_courtroom_drilldown_bundle_view: Callable[..., dict[str, Any]],
    build_courtroom_drilldown_action_hints: Callable[..., list[str]],
    serialize_workflow_job: Callable[[Any], dict[str, Any]],
    build_courtroom_case_sort_key: Callable[..., tuple[Any, ...]],
) -> dict[str, Any]:
    normalized_status = normalize_workflow_status(status)
    if normalized_status is not None and normalized_status not in workflow_statuses:
        raise CaseReadRouteError(status_code=422, detail="invalid_workflow_status")

    normalized_dispatch_type = str(dispatch_type or "").strip().lower() or "auto"
    if normalized_dispatch_type not in {"auto", "phase", "final"}:
        raise CaseReadRouteError(status_code=422, detail="invalid_dispatch_type")
    workflow_dispatch_filter = (
        None if normalized_dispatch_type == "auto" else normalized_dispatch_type
    )

    normalized_winner = str(winner or "").strip().lower() or None
    if normalized_winner not in {None, "pro", "con", "draw"}:
        raise CaseReadRouteError(status_code=422, detail="invalid_winner")

    normalized_risk_level = normalize_review_case_risk_level(risk_level)
    if (
        normalized_risk_level is not None
        and normalized_risk_level not in review_case_risk_level_values
    ):
        raise CaseReadRouteError(status_code=422, detail="invalid_review_risk_level")

    normalized_sla_bucket = normalize_review_case_sla_bucket(sla_bucket)
    if (
        normalized_sla_bucket is not None
        and normalized_sla_bucket not in review_case_sla_bucket_values
    ):
        raise CaseReadRouteError(status_code=422, detail="invalid_review_sla_bucket")

    normalized_updated_from = normalize_query_datetime(updated_from)
    normalized_updated_to = normalize_query_datetime(updated_to)
    if (
        normalized_updated_from is not None
        and normalized_updated_to is not None
        and normalized_updated_from > normalized_updated_to
    ):
        raise CaseReadRouteError(status_code=422, detail="invalid_updated_time_window")

    normalized_sort_by = normalize_courtroom_case_sort_by(sort_by)
    if normalized_sort_by not in courtroom_case_sort_fields:
        raise CaseReadRouteError(
            status_code=422,
            detail="invalid_courtroom_drilldown_sort_by",
        )
    normalized_sort_order = normalize_courtroom_case_sort_order(sort_order)
    if normalized_sort_order not in {"asc", "desc"}:
        raise CaseReadRouteError(
            status_code=422,
            detail="invalid_courtroom_drilldown_sort_order",
        )

    normalized_scan_limit = max(20, min(int(scan_limit), 2000))
    normalized_offset = max(0, int(offset))
    normalized_limit = max(1, min(int(limit), 200))
    normalized_claim_preview_limit = max(1, min(int(claim_preview_limit), 100))
    normalized_evidence_preview_limit = max(1, min(int(evidence_preview_limit), 100))
    normalized_panel_preview_limit = max(1, min(int(panel_preview_limit), 100))

    jobs = await workflow_list_jobs(
        status=normalized_status,
        dispatch_type=workflow_dispatch_filter,
        limit=normalized_scan_limit,
    )
    now = datetime.now(timezone.utc)
    items: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for job in jobs:
        updated_at = normalize_query_datetime(job.updated_at)
        if (
            normalized_updated_from is not None
            and (updated_at is None or updated_at < normalized_updated_from)
        ):
            continue
        if (
            normalized_updated_to is not None
            and (updated_at is None or updated_at > normalized_updated_to)
        ):
            continue

        try:
            context = await resolve_report_context_for_case(
                case_id=job.job_id,
                dispatch_type=normalized_dispatch_type,
                not_found_detail="courtroom_case_not_found",
                missing_report_detail="courtroom_report_payload_missing",
            )
        except Exception as err:
            status_code = getattr(err, "status_code", None)
            detail = str(getattr(err, "detail", "") or "").strip()
            error_code = detail or "courtroom_case_unavailable"
            if error_code in {
                "courtroom_case_not_found",
                "courtroom_report_payload_missing",
            }:
                if not isinstance(status_code, int):
                    try:
                        status_code = int(status_code)
                    except (TypeError, ValueError):
                        status_code = 500
                errors.append(
                    {
                        "caseId": int(job.job_id),
                        "statusCode": int(status_code),
                        "errorCode": error_code,
                    }
                )
                continue
            _raise_route_error_from_http_exception(err)
            raise

        report_payload = (
            context.get("reportPayload")
            if isinstance(context.get("reportPayload"), dict)
            else {}
        )
        winner_value = str(report_payload.get("winner") or "").strip().lower() or None
        if normalized_winner is not None and winner_value != normalized_winner:
            continue
        report_review_required = bool(report_payload.get("reviewRequired"))
        if review_required is not None and report_review_required != bool(review_required):
            continue

        trace = trace_get(job.job_id)
        report_summary = (
            trace.report_summary if trace and isinstance(trace.report_summary, dict) else {}
        )
        risk_profile = build_review_case_risk_profile(
            workflow=job,
            report_payload=report_payload,
            report_summary=report_summary,
            now=now,
        )
        if (
            normalized_risk_level is not None
            and str(risk_profile.get("level") or "").strip().lower() != normalized_risk_level
        ):
            continue
        if (
            normalized_sla_bucket is not None
            and str(risk_profile.get("slaBucket") or "").strip().lower()
            != normalized_sla_bucket
        ):
            continue

        verdict_contract = build_verdict_contract(report_payload)
        case_evidence = build_case_evidence_view(
            report_payload=report_payload,
            verdict_contract=verdict_contract,
            claim_ledger_record=None,
        )
        courtroom_view = build_courtroom_read_model_view(
            report_payload=report_payload,
            case_evidence=case_evidence,
        )
        drilldown = build_courtroom_drilldown_bundle_view(
            courtroom_view=courtroom_view,
            claim_preview_limit=normalized_claim_preview_limit,
            evidence_preview_limit=normalized_evidence_preview_limit,
            panel_preview_limit=normalized_panel_preview_limit,
        )
        response_payload = (
            context.get("responsePayload")
            if isinstance(context.get("responsePayload"), dict)
            else {}
        )
        callback_status = (
            report_summary.get("callbackStatus")
            or response_payload.get("callbackStatus")
            or (trace.callback_status if trace is not None else None)
        )
        callback_error = (
            report_summary.get("callbackError")
            or response_payload.get("callbackError")
            or (trace.callback_error if trace is not None else None)
        )
        dispatch_type_value = (
            str(context.get("dispatchType") or "").strip().lower() or "auto"
        )
        items.append(
            {
                "caseId": int(job.job_id),
                "dispatchType": dispatch_type_value,
                "traceId": context.get("traceId") or None,
                "workflow": serialize_workflow_job(job),
                "winner": winner_value,
                "reviewRequired": report_review_required,
                "needsDrawVote": bool(report_payload.get("needsDrawVote")),
                "callbackStatus": callback_status,
                "callbackError": callback_error,
                "riskProfile": risk_profile,
                "drilldown": drilldown,
                "actionHints": build_courtroom_drilldown_action_hints(
                    drilldown=drilldown,
                ),
                "detailPath": (
                    f"/internal/judge/cases/{int(job.job_id)}/courtroom-read-model"
                    f"?dispatch_type={dispatch_type_value}"
                ),
            }
        )

    items.sort(
        key=lambda row: build_courtroom_case_sort_key(
            item=row,
            sort_by=normalized_sort_by,
        ),
        reverse=(normalized_sort_order == "desc"),
    )
    page_items = items[normalized_offset : normalized_offset + normalized_limit]

    total_conflict_pairs = 0
    total_unanswered_claims = 0
    total_decisive_evidence = 0
    total_pivotal_moments = 0
    review_required_count = 0
    high_risk_count = 0
    for row in items:
        drilldown = row.get("drilldown") if isinstance(row.get("drilldown"), dict) else {}
        claim = drilldown.get("claim") if isinstance(drilldown.get("claim"), dict) else {}
        evidence = drilldown.get("evidence") if isinstance(drilldown.get("evidence"), dict) else {}
        panel = drilldown.get("panel") if isinstance(drilldown.get("panel"), dict) else {}
        total_conflict_pairs += int(claim.get("conflictPairCount") or 0)
        total_unanswered_claims += int(claim.get("unansweredClaimCount") or 0)
        total_decisive_evidence += int(evidence.get("decisiveEvidenceCount") or 0)
        total_pivotal_moments += int(panel.get("pivotalMomentCount") or 0)
        if bool(row.get("reviewRequired")):
            review_required_count += 1
        risk_profile = (
            row.get("riskProfile") if isinstance(row.get("riskProfile"), dict) else {}
        )
        if str(risk_profile.get("level") or "").strip().lower() == "high":
            high_risk_count += 1

    return {
        "count": len(items),
        "returned": len(page_items),
        "scanned": len(jobs),
        "skipped": max(0, len(jobs) - len(items)),
        "errorCount": len(errors),
        "items": page_items,
        "errors": errors,
        "aggregations": {
            "totalConflictPairCount": total_conflict_pairs,
            "totalUnansweredClaimCount": total_unanswered_claims,
            "totalDecisiveEvidenceCount": total_decisive_evidence,
            "totalPivotalMomentCount": total_pivotal_moments,
            "reviewRequiredCount": review_required_count,
            "highRiskCount": high_risk_count,
        },
        "filters": {
            "status": normalized_status,
            "dispatchType": normalized_dispatch_type,
            "winner": normalized_winner,
            "reviewRequired": review_required,
            "riskLevel": normalized_risk_level,
            "slaBucket": normalized_sla_bucket,
            "updatedFrom": (
                normalized_updated_from.isoformat()
                if normalized_updated_from is not None
                else None
            ),
            "updatedTo": (
                normalized_updated_to.isoformat()
                if normalized_updated_to is not None
                else None
            ),
            "sortBy": normalized_sort_by,
            "sortOrder": normalized_sort_order,
            "scanLimit": normalized_scan_limit,
            "offset": normalized_offset,
            "limit": normalized_limit,
            "claimPreviewLimit": normalized_claim_preview_limit,
            "evidencePreviewLimit": normalized_evidence_preview_limit,
            "panelPreviewLimit": normalized_panel_preview_limit,
        },
        "notes": [
            "drilldown bundle is read-only and does not change verdict state.",
        ],
    }


async def build_case_evidence_claim_ops_queue_route_payload(
    *,
    status: str | None,
    dispatch_type: str,
    winner: str | None,
    review_required: bool | None,
    risk_level: str | None,
    sla_bucket: str | None,
    reliability_level: str | None,
    has_conflict: bool | None,
    has_unanswered_claim: bool | None,
    updated_from: datetime | None,
    updated_to: datetime | None,
    sort_by: str,
    sort_order: str,
    scan_limit: int,
    offset: int,
    limit: int,
    normalize_workflow_status: Callable[[str | None], str | None],
    workflow_statuses: set[str],
    normalize_review_case_risk_level: Callable[[str | None], str | None],
    review_case_risk_level_values: set[str],
    normalize_review_case_sla_bucket: Callable[[str | None], str | None],
    review_case_sla_bucket_values: set[str],
    normalize_evidence_claim_reliability_level: Callable[[str | None], str | None],
    evidence_claim_reliability_level_values: set[str],
    normalize_query_datetime: Callable[[datetime | None], datetime | None],
    normalize_evidence_claim_queue_sort_by: Callable[[str | None], str],
    normalize_evidence_claim_queue_sort_order: Callable[[str | None], str],
    evidence_claim_queue_sort_fields: set[str],
    workflow_list_jobs: Callable[..., Awaitable[list[Any]]],
    resolve_report_context_for_case: Callable[..., Awaitable[dict[str, Any]]],
    trace_get: Callable[[int], Any | None],
    build_review_case_risk_profile: Callable[..., dict[str, Any]],
    build_verdict_contract: Callable[[dict[str, Any]], dict[str, Any]],
    build_case_evidence_view: Callable[..., dict[str, Any]],
    build_courtroom_read_model_view: Callable[..., dict[str, Any]],
    build_courtroom_read_model_light_summary: Callable[..., dict[str, Any]],
    build_evidence_claim_ops_profile: Callable[..., dict[str, Any]],
    build_evidence_claim_action_hints: Callable[..., list[str]],
    serialize_workflow_job: Callable[[Any], dict[str, Any]],
    build_evidence_claim_queue_sort_key: Callable[..., tuple[Any, ...]],
) -> dict[str, Any]:
    normalized_status = normalize_workflow_status(status)
    if normalized_status is not None and normalized_status not in workflow_statuses:
        raise CaseReadRouteError(status_code=422, detail="invalid_workflow_status")

    normalized_dispatch_type = str(dispatch_type or "").strip().lower() or "auto"
    if normalized_dispatch_type not in {"auto", "phase", "final"}:
        raise CaseReadRouteError(status_code=422, detail="invalid_dispatch_type")
    workflow_dispatch_filter = (
        None if normalized_dispatch_type == "auto" else normalized_dispatch_type
    )

    normalized_winner = str(winner or "").strip().lower() or None
    if normalized_winner not in {None, "pro", "con", "draw"}:
        raise CaseReadRouteError(status_code=422, detail="invalid_winner")

    normalized_risk_level = normalize_review_case_risk_level(risk_level)
    if (
        normalized_risk_level is not None
        and normalized_risk_level not in review_case_risk_level_values
    ):
        raise CaseReadRouteError(status_code=422, detail="invalid_review_risk_level")

    normalized_sla_bucket = normalize_review_case_sla_bucket(sla_bucket)
    if (
        normalized_sla_bucket is not None
        and normalized_sla_bucket not in review_case_sla_bucket_values
    ):
        raise CaseReadRouteError(status_code=422, detail="invalid_review_sla_bucket")

    normalized_reliability_level = normalize_evidence_claim_reliability_level(
        reliability_level
    )
    if (
        normalized_reliability_level is not None
        and normalized_reliability_level not in evidence_claim_reliability_level_values
    ):
        raise CaseReadRouteError(
            status_code=422,
            detail="invalid_evidence_claim_reliability_level",
        )

    normalized_updated_from = normalize_query_datetime(updated_from)
    normalized_updated_to = normalize_query_datetime(updated_to)
    if (
        normalized_updated_from is not None
        and normalized_updated_to is not None
        and normalized_updated_from > normalized_updated_to
    ):
        raise CaseReadRouteError(status_code=422, detail="invalid_updated_time_window")

    normalized_sort_by = normalize_evidence_claim_queue_sort_by(sort_by)
    if normalized_sort_by not in evidence_claim_queue_sort_fields:
        raise CaseReadRouteError(status_code=422, detail="invalid_evidence_claim_sort_by")
    normalized_sort_order = normalize_evidence_claim_queue_sort_order(sort_order)
    if normalized_sort_order not in {"asc", "desc"}:
        raise CaseReadRouteError(status_code=422, detail="invalid_evidence_claim_sort_order")

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
        updated_at = normalize_query_datetime(job.updated_at)
        if (
            normalized_updated_from is not None
            and (updated_at is None or updated_at < normalized_updated_from)
        ):
            continue
        if (
            normalized_updated_to is not None
            and (updated_at is None or updated_at > normalized_updated_to)
        ):
            continue

        try:
            context = await resolve_report_context_for_case(
                case_id=job.job_id,
                dispatch_type=normalized_dispatch_type,
                not_found_detail="courtroom_case_not_found",
                missing_report_detail="courtroom_report_payload_missing",
            )
        except Exception as err:
            status_code = getattr(err, "status_code", None)
            detail = str(getattr(err, "detail", "") or "").strip()
            error_code = detail or "evidence_claim_case_unavailable"
            if error_code in {
                "courtroom_case_not_found",
                "courtroom_report_payload_missing",
            }:
                if not isinstance(status_code, int):
                    try:
                        status_code = int(status_code)
                    except (TypeError, ValueError):
                        status_code = 500
                errors.append(
                    {
                        "caseId": int(job.job_id),
                        "statusCode": int(status_code),
                        "errorCode": error_code,
                    }
                )
                continue
            _raise_route_error_from_http_exception(err)
            raise

        report_payload = (
            context.get("reportPayload")
            if isinstance(context.get("reportPayload"), dict)
            else {}
        )
        winner_value = str(report_payload.get("winner") or "").strip().lower() or None
        if normalized_winner is not None and winner_value != normalized_winner:
            continue

        report_review_required = bool(report_payload.get("reviewRequired"))
        if review_required is not None and report_review_required != bool(review_required):
            continue

        trace = trace_get(job.job_id)
        report_summary = (
            trace.report_summary if trace and isinstance(trace.report_summary, dict) else {}
        )
        risk_profile = build_review_case_risk_profile(
            workflow=job,
            report_payload=report_payload,
            report_summary=report_summary,
            now=now,
        )
        if (
            normalized_risk_level is not None
            and str(risk_profile.get("level") or "").strip().lower() != normalized_risk_level
        ):
            continue
        if (
            normalized_sla_bucket is not None
            and str(risk_profile.get("slaBucket") or "").strip().lower()
            != normalized_sla_bucket
        ):
            continue

        verdict_contract = build_verdict_contract(report_payload)
        case_evidence = build_case_evidence_view(
            report_payload=report_payload,
            verdict_contract=verdict_contract,
            claim_ledger_record=None,
        )
        courtroom_view = build_courtroom_read_model_view(
            report_payload=report_payload,
            case_evidence=case_evidence,
        )
        courtroom_summary = build_courtroom_read_model_light_summary(
            courtroom_view=courtroom_view,
        )
        ops_profile = build_evidence_claim_ops_profile(
            risk_profile=risk_profile,
            courtroom_summary=courtroom_summary,
        )
        if has_conflict is not None and bool(ops_profile.get("hasConflict")) != bool(has_conflict):
            continue
        if (
            has_unanswered_claim is not None
            and bool(ops_profile.get("hasUnansweredClaim")) != bool(has_unanswered_claim)
        ):
            continue
        reliability = (
            ops_profile.get("reliability")
            if isinstance(ops_profile.get("reliability"), dict)
            else {}
        )
        reliability_level_value = (
            str(reliability.get("level") or "").strip().lower() or "unknown"
        )
        if (
            normalized_reliability_level is not None
            and reliability_level_value != normalized_reliability_level
        ):
            continue

        response_payload = (
            context.get("responsePayload")
            if isinstance(context.get("responsePayload"), dict)
            else {}
        )
        callback_status = (
            report_summary.get("callbackStatus")
            or response_payload.get("callbackStatus")
            or (trace.callback_status if trace is not None else None)
        )
        callback_error = (
            report_summary.get("callbackError")
            or response_payload.get("callbackError")
            or (trace.callback_error if trace is not None else None)
        )
        dispatch_type_value = (
            str(context.get("dispatchType") or "").strip().lower() or "auto"
        )
        items.append(
            {
                "caseId": int(job.job_id),
                "dispatchType": dispatch_type_value,
                "traceId": context.get("traceId") or None,
                "workflow": serialize_workflow_job(job),
                "winner": winner_value,
                "reviewRequired": report_review_required,
                "needsDrawVote": bool(report_payload.get("needsDrawVote")),
                "callbackStatus": callback_status,
                "callbackError": callback_error,
                "riskProfile": risk_profile,
                "courtroomSummary": courtroom_summary,
                "claimEvidenceProfile": ops_profile,
                "actionHints": build_evidence_claim_action_hints(
                    ops_profile=ops_profile,
                    review_required=report_review_required,
                ),
                "detailPath": (
                    f"/internal/judge/cases/{int(job.job_id)}/courtroom-read-model"
                    f"?dispatch_type={dispatch_type_value}"
                ),
            }
        )

    items.sort(
        key=lambda row: build_evidence_claim_queue_sort_key(
            item=row,
            sort_by=normalized_sort_by,
        ),
        reverse=(normalized_sort_order == "desc"),
    )
    page_items = items[normalized_offset : normalized_offset + normalized_limit]

    risk_level_counts = {
        "high": 0,
        "medium": 0,
        "low": 0,
    }
    reliability_level_counts = {
        "high": 0,
        "medium": 0,
        "low": 0,
        "unknown": 0,
    }
    conflict_case_count = 0
    unanswered_case_count = 0
    for row in items:
        risk_profile = row.get("riskProfile") if isinstance(row.get("riskProfile"), dict) else {}
        risk_level_value = str(risk_profile.get("level") or "").strip().lower()
        if risk_level_value in risk_level_counts:
            risk_level_counts[risk_level_value] += 1

        ops_profile = (
            row.get("claimEvidenceProfile")
            if isinstance(row.get("claimEvidenceProfile"), dict)
            else {}
        )
        if bool(ops_profile.get("hasConflict")):
            conflict_case_count += 1
        if bool(ops_profile.get("hasUnansweredClaim")):
            unanswered_case_count += 1
        reliability = (
            ops_profile.get("reliability")
            if isinstance(ops_profile.get("reliability"), dict)
            else {}
        )
        reliability_level_value = str(reliability.get("level") or "").strip().lower()
        if reliability_level_value in reliability_level_counts:
            reliability_level_counts[reliability_level_value] += 1
        else:
            reliability_level_counts["unknown"] += 1

    return {
        "count": len(items),
        "returned": len(page_items),
        "scanned": len(jobs),
        "skipped": max(0, len(jobs) - len(items)),
        "errorCount": len(errors),
        "items": page_items,
        "errors": errors,
        "aggregations": {
            "riskLevelCounts": risk_level_counts,
            "reliabilityLevelCounts": reliability_level_counts,
            "conflictCaseCount": conflict_case_count,
            "unansweredCaseCount": unanswered_case_count,
        },
        "filters": {
            "status": normalized_status,
            "dispatchType": normalized_dispatch_type,
            "winner": normalized_winner,
            "reviewRequired": review_required,
            "riskLevel": normalized_risk_level,
            "slaBucket": normalized_sla_bucket,
            "reliabilityLevel": normalized_reliability_level,
            "hasConflict": has_conflict,
            "hasUnansweredClaim": has_unanswered_claim,
            "updatedFrom": (
                normalized_updated_from.isoformat()
                if normalized_updated_from is not None
                else None
            ),
            "updatedTo": (
                normalized_updated_to.isoformat()
                if normalized_updated_to is not None
                else None
            ),
            "sortBy": normalized_sort_by,
            "sortOrder": normalized_sort_order,
            "scanLimit": normalized_scan_limit,
            "offset": normalized_offset,
            "limit": normalized_limit,
        },
    }


def build_case_overview_replay_items(
    *,
    replay_records: list[Any],
    trace: Any | None,
) -> list[dict[str, Any]]:
    if replay_records:
        return [
            {
                "dispatchType": item.dispatch_type,
                "traceId": item.trace_id,
                "replayedAt": item.created_at.isoformat(),
                "winner": item.winner,
                "needsDrawVote": item.needs_draw_vote,
                "provider": item.provider,
            }
            for item in replay_records
        ]
    trace_replays = trace.replays if trace is not None else []
    return [
        {
            "dispatchType": None,
            "traceId": trace.trace_id if trace is not None else None,
            "replayedAt": item.replayed_at.isoformat(),
            "winner": item.winner,
            "needsDrawVote": item.needs_draw_vote,
            "provider": item.provider,
        }
        for item in trace_replays
    ]


def build_case_overview_payload(
    *,
    case_id: int,
    workflow: dict[str, Any] | None,
    trace: dict[str, Any] | None,
    receipts: dict[str, Any],
    latest_dispatch_type: str | None,
    report_payload: dict[str, Any],
    verdict_contract: dict[str, Any],
    case_evidence: dict[str, Any],
    winner: str | None,
    needs_draw_vote: bool | None,
    review_required: bool,
    callback_status: str | None,
    callback_error: str | None,
    judge_core: dict[str, Any] | None,
    events: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
    replays: list[dict[str, Any]],
    trust_artifact_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "caseId": case_id,
        "workflow": workflow,
        "trace": trace,
        "receipts": receipts,
        "latestDispatchType": latest_dispatch_type,
        "reportPayload": report_payload,
        "verdictContract": verdict_contract,
        "caseEvidence": case_evidence,
        "winner": winner,
        "needsDrawVote": needs_draw_vote,
        "reviewRequired": review_required,
        "callbackStatus": callback_status,
        "callbackError": callback_error,
        "judgeCore": judge_core,
        "events": events,
        "alerts": alerts,
        "replays": replays,
        "trustArtifactSummary": (
            dict(trust_artifact_summary)
            if isinstance(trust_artifact_summary, dict)
            else {}
        ),
    }


def build_case_courtroom_read_model_payload(
    *,
    case_id: int,
    dispatch_type: str,
    trace_id: str | None,
    workflow: dict[str, Any] | None,
    judge_core: dict[str, Any] | None,
    callback_status: str | None,
    callback_error: str | None,
    report_payload: dict[str, Any],
    courtroom: dict[str, Any],
    events: list[dict[str, Any]],
    event_count: int,
    alerts: list[dict[str, Any]],
    include_events: bool,
    include_alerts: bool,
    alert_limit: int,
) -> dict[str, Any]:
    return {
        "caseId": case_id,
        "dispatchType": dispatch_type,
        "traceId": trace_id,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "workflow": workflow,
        "judgeCore": judge_core,
        "callback": {
            "status": callback_status,
            "error": callback_error,
        },
        "report": {
            "winner": str(report_payload.get("winner") or "").strip().lower() or None,
            "reviewRequired": bool(report_payload.get("reviewRequired")),
            "needsDrawVote": bool(report_payload.get("needsDrawVote")),
            "debateSummary": (
                report_payload.get("debateSummary")
                if isinstance(report_payload.get("debateSummary"), str)
                else None
            ),
            "sideAnalysis": (
                report_payload.get("sideAnalysis")
                if isinstance(report_payload.get("sideAnalysis"), dict)
                else {}
            ),
            "verdictReason": (
                report_payload.get("verdictReason")
                if isinstance(report_payload.get("verdictReason"), str)
                else None
            ),
        },
        "courtroom": courtroom,
        "events": events if include_events else [],
        "eventCount": int(event_count),
        "alerts": alerts if include_alerts else [],
        "filters": {
            "dispatchType": dispatch_type,
            "includeEvents": bool(include_events),
            "includeAlerts": bool(include_alerts),
            "alertLimit": int(alert_limit),
        },
    }
