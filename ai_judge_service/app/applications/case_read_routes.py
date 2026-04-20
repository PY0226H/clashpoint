from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


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
