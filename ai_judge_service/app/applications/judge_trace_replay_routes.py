from __future__ import annotations

from datetime import datetime
from typing import Any

REPLAY_DISPATCH_TYPES: frozenset[str] = frozenset({"auto", "phase", "final"})


def normalize_replay_dispatch_type(dispatch_type: str) -> str:
    normalized = str(dispatch_type or "auto").strip().lower()
    if normalized not in REPLAY_DISPATCH_TYPES:
        raise ValueError("invalid_dispatch_type")
    return normalized


def choose_replay_dispatch_receipt(
    *,
    dispatch_type: str,
    final_receipt: Any | None = None,
    phase_receipt: Any | None = None,
    explicit_receipt: Any | None = None,
) -> tuple[str, Any | None]:
    if dispatch_type == "auto":
        if final_receipt is not None:
            return "final", final_receipt
        if phase_receipt is not None:
            return "phase", phase_receipt
        return "auto", None
    return dispatch_type, explicit_receipt


def extract_replay_request_snapshot(receipt: Any | None) -> dict[str, Any]:
    return receipt.request if isinstance(getattr(receipt, "request", None), dict) else {}


def resolve_replay_trace_id(
    *,
    receipt: Any | None,
    request_snapshot: dict[str, Any] | None,
) -> str:
    snapshot = request_snapshot if isinstance(request_snapshot, dict) else {}
    return str(getattr(receipt, "trace_id", None) or snapshot.get("traceId") or "").strip()


def build_trace_route_replay_items(
    *,
    replay_records: list[Any] | None,
    trace_record: Any | None,
) -> list[dict[str, Any]]:
    records = replay_records if isinstance(replay_records, list) else []
    if records:
        return [
            {
                "replayedAt": item.created_at.isoformat(),
                "winner": item.winner,
                "needsDrawVote": item.needs_draw_vote,
                "provider": item.provider,
            }
            for item in records
        ]

    trace_replays = trace_record.replays if trace_record is not None else []
    return [
        {
            "replayedAt": item.replayed_at.isoformat(),
            "winner": item.winner,
            "needsDrawVote": item.needs_draw_vote,
            "provider": item.provider,
        }
        for item in trace_replays
    ]


def build_trace_route_payload(
    *,
    record: Any,
    report_summary: dict[str, Any] | None,
    verdict_contract: dict[str, Any],
    replay_items: list[dict[str, Any]],
) -> dict[str, Any]:
    summary = report_summary if isinstance(report_summary, dict) else {}
    role_nodes = summary.get("roleNodes") if isinstance(summary.get("roleNodes"), list) else []
    return {
        "caseId": record.job_id,
        "traceId": record.trace_id,
        "status": record.status,
        "createdAt": record.created_at.isoformat(),
        "updatedAt": record.updated_at.isoformat(),
        "callbackStatus": record.callback_status,
        "callbackError": record.callback_error,
        "response": record.response,
        "request": record.request,
        "reportSummary": summary,
        "roleNodes": role_nodes,
        "verdictContract": dict(verdict_contract) if isinstance(verdict_contract, dict) else {},
        "replays": list(replay_items),
    }


def build_replay_route_payload(
    *,
    case_id: int,
    dispatch_type: str,
    replayed_at: datetime | str,
    report_payload: dict[str, Any],
    verdict_contract: dict[str, Any],
    winner: str,
    needs_draw_vote: bool,
    trace_id: str,
    judge_core_stage: str,
    judge_core_version: str,
) -> dict[str, Any]:
    if isinstance(replayed_at, datetime):
        replayed_at_value = replayed_at.isoformat()
    else:
        replayed_at_value = str(replayed_at)
    return {
        "caseId": int(case_id),
        "dispatchType": str(dispatch_type),
        "replayedAt": replayed_at_value,
        "reportPayload": dict(report_payload),
        "verdictContract": dict(verdict_contract),
        "winner": str(winner),
        "needsDrawVote": bool(needs_draw_vote),
        "traceId": str(trace_id),
        "judgeCoreStage": str(judge_core_stage),
        "judgeCoreVersion": str(judge_core_version),
    }


def build_replay_reports_list_payload(
    *,
    items: list[dict[str, Any]],
    status: str | None,
    winner: str | None,
    callback_status: str | None,
    trace_id: str | None,
    created_after: datetime | None,
    created_before: datetime | None,
    has_audit_alert: bool | None,
    limit: int,
    include_report: bool,
) -> dict[str, Any]:
    return {
        "count": len(items),
        "items": list(items),
        "filters": {
            "status": status,
            "winner": winner,
            "callbackStatus": callback_status,
            "traceId": trace_id,
            "createdAfter": created_after.isoformat() if created_after else None,
            "createdBefore": created_before.isoformat() if created_before else None,
            "hasAuditAlert": has_audit_alert,
            "limit": int(limit),
            "includeReport": bool(include_report),
        },
    }
