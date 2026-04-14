from __future__ import annotations

from typing import Any


def _normalize_winner(value: Any) -> str | None:
    normalized = str(value or "").strip().lower()
    if normalized in {"pro", "con", "draw"}:
        return normalized
    return None


def _normalize_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _normalize_side_analysis(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {"pro": "", "con": ""}
    return {
        "pro": str(value.get("pro") or "").strip(),
        "con": str(value.get("con") or "").strip(),
    }


def _normalize_dimension_scores(value: Any) -> dict[str, float | None]:
    scores = value if isinstance(value, dict) else {}
    return {
        "logic": _normalize_float(scores.get("logic")),
        "evidence": _normalize_float(scores.get("evidence")),
        "rebuttal": _normalize_float(scores.get("rebuttal")),
        "clarity": _normalize_float(scores.get("clarity")),
    }


def build_verdict_contract(payload: dict[str, Any] | None) -> dict[str, Any]:
    report_payload = payload if isinstance(payload, dict) else {}
    return {
        "winner": _normalize_winner(report_payload.get("winner")),
        "proScore": _normalize_float(report_payload.get("proScore")),
        "conScore": _normalize_float(report_payload.get("conScore")),
        "dimensionScores": _normalize_dimension_scores(report_payload.get("dimensionScores")),
        "debateSummary": str(report_payload.get("debateSummary") or "").strip(),
        "sideAnalysis": _normalize_side_analysis(report_payload.get("sideAnalysis")),
        "verdictReason": str(report_payload.get("verdictReason") or "").strip(),
        "evidenceLedger": (
            dict(report_payload.get("evidenceLedger"))
            if isinstance(report_payload.get("evidenceLedger"), dict)
            else None
        ),
        "verdictEvidenceRefs": [
            row
            for row in (report_payload.get("verdictEvidenceRefs") or [])
            if isinstance(row, dict)
        ],
        "fairnessSummary": (
            dict(report_payload.get("fairnessSummary"))
            if isinstance(report_payload.get("fairnessSummary"), dict)
            else None
        ),
        "auditAlerts": [
            row for row in (report_payload.get("auditAlerts") or []) if isinstance(row, dict)
        ],
        "errorCodes": [
            str(row).strip()
            for row in (report_payload.get("errorCodes") or [])
            if str(row).strip()
        ],
        "degradationLevel": (
            int(report_payload.get("degradationLevel"))
            if isinstance(report_payload.get("degradationLevel"), int)
            else None
        ),
        "needsDrawVote": (
            bool(report_payload.get("needsDrawVote"))
            if "needsDrawVote" in report_payload
            else None
        ),
        "reviewRequired": bool(report_payload.get("reviewRequired")),
    }


def serialize_alert_item(alert: Any) -> dict[str, Any]:
    transitions = getattr(alert, "transitions", [])
    if not isinstance(transitions, list):
        transitions = []
    return {
        "alertId": alert.alert_id,
        "caseId": alert.job_id,
        "scopeId": alert.scope_id,
        "traceId": alert.trace_id,
        "type": alert.alert_type,
        "severity": alert.severity,
        "title": alert.title,
        "message": alert.message,
        "details": alert.details,
        "status": alert.status,
        "createdAt": alert.created_at.isoformat(),
        "updatedAt": alert.updated_at.isoformat(),
        "acknowledgedAt": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
        "resolvedAt": alert.resolved_at.isoformat() if alert.resolved_at else None,
        "transitions": [
            {
                "fromStatus": row.from_status,
                "toStatus": row.to_status,
                "actor": row.actor,
                "reason": row.reason,
                "changedAt": row.changed_at.isoformat(),
            }
            for row in transitions
        ],
    }


def serialize_outbox_event(item: Any) -> dict[str, Any]:
    return {
        "eventId": item.event_id,
        "channel": item.channel,
        "scopeId": item.scope_id,
        "caseId": item.job_id,
        "traceId": item.trace_id,
        "alertId": item.alert_id,
        "status": item.status,
        "payload": item.payload,
        "deliveryStatus": item.delivery_status,
        "errorMessage": item.error_message,
        "createdAt": item.created_at.isoformat(),
        "updatedAt": item.updated_at.isoformat(),
    }


def serialize_dispatch_receipt(item: Any) -> dict[str, Any]:
    return {
        "dispatchType": item.dispatch_type,
        "caseId": item.job_id,
        "scopeId": item.scope_id,
        "sessionId": item.session_id,
        "traceId": item.trace_id,
        "idempotencyKey": item.idempotency_key,
        "rubricVersion": item.rubric_version,
        "judgePolicyVersion": item.judge_policy_version,
        "topicDomain": item.topic_domain,
        "retrievalProfile": item.retrieval_profile,
        "phaseNo": item.phase_no,
        "phaseStartNo": item.phase_start_no,
        "phaseEndNo": item.phase_end_no,
        "messageStartId": item.message_start_id,
        "messageEndId": item.message_end_id,
        "messageCount": item.message_count,
        "status": item.status,
        "request": item.request,
        "response": item.response,
        "createdAt": item.created_at.isoformat(),
        "updatedAt": item.updated_at.isoformat(),
    }


def build_replay_report_payload(record: Any) -> dict[str, Any]:
    report_summary = record.report_summary if isinstance(record.report_summary, dict) else {}
    request = record.request if isinstance(record.request, dict) else {}
    response = record.response if isinstance(record.response, dict) else {}
    payload = report_summary.get("payload") if isinstance(report_summary.get("payload"), dict) else {}
    winner_text = _normalize_winner(report_summary.get("winner") or payload.get("winner"))

    raw_alerts = report_summary.get("auditAlerts")
    if not isinstance(raw_alerts, list):
        raw_alerts = payload.get("auditAlerts")
    audit_alerts = [row for row in (raw_alerts or []) if isinstance(row, dict)]

    callback_status = report_summary.get("callbackStatus") or record.callback_status
    callback_error = report_summary.get("callbackError") or record.callback_error

    verdict_contract = build_verdict_contract(payload)
    return {
        "caseId": record.job_id,
        "traceId": record.trace_id,
        "status": record.status,
        "dispatchType": report_summary.get("dispatchType"),
        "request": request,
        "payload": payload,
        "winner": winner_text,
        "auditAlerts": audit_alerts,
        "callbackStatus": callback_status,
        "callbackError": callback_error,
        "reportSummary": {
            "payload": payload,
            "winner": winner_text,
            "auditAlerts": audit_alerts,
            "callbackStatus": callback_status,
            "callbackError": callback_error,
        },
        "callbackResult": {
            "callbackStatus": callback_status,
            "callbackError": callback_error,
            "response": response,
        },
        "verdictContract": verdict_contract,
        "replays": [
            {
                "replayedAt": item.replayed_at.isoformat(),
                "winner": item.winner,
                "needsDrawVote": item.needs_draw_vote,
                "provider": item.provider,
            }
            for item in record.replays
        ],
    }


def build_replay_report_summary(record: Any) -> dict[str, Any]:
    payload = build_replay_report_payload(record)
    audit_alerts = payload.get("auditAlerts")
    if not isinstance(audit_alerts, list):
        audit_alerts = []
    callback_result = payload.get("callbackResult")
    response = callback_result.get("response") if isinstance(callback_result, dict) else {}
    if not isinstance(response, dict):
        response = {}
    return {
        "caseId": payload.get("caseId"),
        "traceId": payload.get("traceId"),
        "dispatchType": payload.get("dispatchType"),
        "status": payload.get("status"),
        "createdAt": record.created_at.isoformat(),
        "updatedAt": record.updated_at.isoformat(),
        "winner": payload.get("winner"),
        "needsDrawVote": payload.get("payload", {}).get("needsDrawVote")
        if isinstance(payload.get("payload"), dict)
        else None,
        "provider": response.get("provider"),
        "errorCode": response.get("errorCode"),
        "callbackStatus": payload.get("callbackStatus"),
        "callbackError": payload.get("callbackError"),
        "auditAlertCount": len([row for row in audit_alerts if isinstance(row, dict)]),
        "replayCount": len(payload.get("replays") or []),
    }
