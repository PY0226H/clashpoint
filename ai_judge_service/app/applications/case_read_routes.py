from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable


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
        latest_dispatch_type=(
            "final"
            if final_receipt is not None
            else ("phase" if phase_receipt is not None else None)
        ),
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
