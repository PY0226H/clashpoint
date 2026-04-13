from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Header, HTTPException, Query, Request
from pydantic import ValidationError

from .applications import WorkflowRuntime, build_workflow_runtime
from .callback_client import (
    callback_final_failed,
    callback_final_report,
    callback_phase_failed,
    callback_phase_report,
)
from .domain.facts import (
    AuditAlert as FactAuditAlert,
)
from .domain.facts import (
    DispatchReceipt as FactDispatchReceipt,
)
from .domain.facts import (
    ReplayRecord as FactReplayRecord,
)
from .domain.workflow import WORKFLOW_STATUS_QUEUED, WorkflowJob
from .models import FinalDispatchRequest, PhaseDispatchRequest
from .phase_pipeline import build_phase_report_payload as build_phase_report_payload_v3
from .runtime_types import CallbackReportFn, DispatchRuntimeConfig, SleepFn
from .settings import (
    Settings,
    build_callback_client_config,
    build_dispatch_runtime_config,
    load_settings,
)
from .style_mode import resolve_effective_style_mode
from .trace_store import TraceQuery, TraceStoreProtocol, build_trace_store_from_settings
from .wiring import build_v3_dispatch_callbacks

LoadSettingsFn = Callable[[], Settings]


@dataclass(frozen=True)
class AppRuntime:
    settings: Settings
    dispatch_runtime_cfg: DispatchRuntimeConfig
    callback_phase_report_fn: Callable[[int, dict[str, Any]], Awaitable[None]]
    callback_final_report_fn: Callable[[int, dict[str, Any]], Awaitable[None]]
    callback_phase_failed_fn: Callable[[int, dict[str, Any]], Awaitable[None]]
    callback_final_failed_fn: Callable[[int, dict[str, Any]], Awaitable[None]]
    sleep_fn: SleepFn
    trace_store: TraceStoreProtocol
    workflow_runtime: WorkflowRuntime


def require_internal_key(settings: Settings, header_value: str | None) -> None:
    if not header_value:
        raise HTTPException(status_code=401, detail="missing x-ai-internal-key")
    if header_value.strip() != settings.ai_internal_key:
        raise HTTPException(status_code=401, detail="invalid x-ai-internal-key")


def create_runtime(
    *,
    settings: Settings,
    callback_phase_report_impl=callback_phase_report,
    callback_final_report_impl=callback_final_report,
    callback_phase_failed_impl=callback_phase_failed,
    callback_final_failed_impl=callback_final_failed,
    sleep_fn: SleepFn = asyncio.sleep,
) -> AppRuntime:
    trace_store = build_trace_store_from_settings(settings=settings)
    workflow_runtime = build_workflow_runtime(settings=settings)
    callback_cfg = build_callback_client_config(settings)
    (
        callback_phase_report_fn,
        callback_final_report_fn,
        callback_phase_failed_fn,
        callback_final_failed_fn,
    ) = build_v3_dispatch_callbacks(
        cfg=callback_cfg,
        callback_phase_report_impl=callback_phase_report_impl,
        callback_final_report_impl=callback_final_report_impl,
        callback_phase_failed_impl=callback_phase_failed_impl,
        callback_final_failed_impl=callback_final_failed_impl,
    )
    return AppRuntime(
        settings=settings,
        dispatch_runtime_cfg=build_dispatch_runtime_config(settings),
        callback_phase_report_fn=callback_phase_report_fn,
        callback_final_report_fn=callback_final_report_fn,
        callback_phase_failed_fn=callback_phase_failed_fn,
        callback_final_failed_fn=callback_final_failed_fn,
        sleep_fn=sleep_fn,
        trace_store=trace_store,
        workflow_runtime=workflow_runtime,
    )


_BLIND_SENSITIVE_KEY_TOKENS = {
    "user_id",
    "userid",
    "vip",
    "balance",
    "wallet_balance",
    "is_vip",
}


def _serialize_alert_item(alert: Any) -> dict[str, Any]:
    transitions = getattr(alert, "transitions", [])
    if not isinstance(transitions, list):
        transitions = []
    return {
        "alertId": alert.alert_id,
        "jobId": alert.job_id,
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


def _serialize_outbox_event(item: Any) -> dict[str, Any]:
    return {
        "eventId": item.event_id,
        "channel": item.channel,
        "scopeId": item.scope_id,
        "jobId": item.job_id,
        "traceId": item.trace_id,
        "alertId": item.alert_id,
        "status": item.status,
        "payload": item.payload,
        "deliveryStatus": item.delivery_status,
        "errorMessage": item.error_message,
        "createdAt": item.created_at.isoformat(),
        "updatedAt": item.updated_at.isoformat(),
    }


def _serialize_dispatch_receipt(item: Any) -> dict[str, Any]:
    return {
        "dispatchType": item.dispatch_type,
        "jobId": item.job_id,
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


def _build_replay_report_payload(record: Any) -> dict[str, Any]:
    report_summary = record.report_summary if isinstance(record.report_summary, dict) else {}
    request = record.request if isinstance(record.request, dict) else {}
    response = record.response if isinstance(record.response, dict) else {}
    payload = report_summary.get("payload") if isinstance(report_summary.get("payload"), dict) else {}
    winner = report_summary.get("winner") or payload.get("winner")
    winner_text = str(winner).strip().lower() if winner is not None else None
    if winner_text not in {"pro", "con", "draw"}:
        winner_text = None

    raw_alerts = report_summary.get("auditAlerts")
    if not isinstance(raw_alerts, list):
        raw_alerts = payload.get("auditAlerts")
    audit_alerts = [row for row in (raw_alerts or []) if isinstance(row, dict)]

    callback_status = report_summary.get("callbackStatus") or record.callback_status
    callback_error = report_summary.get("callbackError") or record.callback_error

    return {
        "jobId": record.job_id,
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


def _build_replay_report_summary(record: Any) -> dict[str, Any]:
    payload = _build_replay_report_payload(record)
    audit_alerts = payload.get("auditAlerts")
    if not isinstance(audit_alerts, list):
        audit_alerts = []
    callback_result = payload.get("callbackResult")
    response = callback_result.get("response") if isinstance(callback_result, dict) else {}
    if not isinstance(response, dict):
        response = {}
    return {
        "jobId": payload.get("jobId"),
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


def _normalize_query_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _normalize_key_token(value: Any) -> str:
    lowered = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return lowered


def _collect_sensitive_key_hits(
    value: Any,
    *,
    path: str,
    out: list[str],
) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            key_token = _normalize_key_token(key_text)
            compact = key_token.replace("_", "")
            if key_token in _BLIND_SENSITIVE_KEY_TOKENS or compact in _BLIND_SENSITIVE_KEY_TOKENS:
                out.append(f"{path}.{key_text}" if path else key_text)
            next_path = f"{path}.{key_text}" if path else key_text
            _collect_sensitive_key_hits(child, path=next_path, out=out)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            next_path = f"{path}[{index}]" if path else f"[{index}]"
            _collect_sensitive_key_hits(child, path=next_path, out=out)


def _find_sensitive_key_hits(payload: Any) -> list[str]:
    out: list[str] = []
    _collect_sensitive_key_hits(payload, path="", out=out)
    dedup: list[str] = []
    seen: set[str] = set()
    for item in out:
        if item in seen:
            continue
        seen.add(item)
        dedup.append(item)
    return dedup


def _extract_raw_field(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload.get(key)
    return None


def _extract_optional_int(payload: dict[str, Any], *keys: str) -> int | None:
    value = _extract_raw_field(payload, *keys)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_optional_str(payload: dict[str, Any], *keys: str) -> str | None:
    value = _extract_raw_field(payload, *keys)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _build_failed_callback_payload(
    *,
    job_id: int,
    dispatch_type: str,
    trace_id: str,
    error_code: str,
    error_message: str,
    audit_alert_ids: list[str] | None = None,
    degradation_level: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "jobId": job_id,
        "dispatchType": dispatch_type,
        "traceId": trace_id,
        "errorCode": error_code,
        "errorMessage": error_message,
        "auditAlertIds": list(audit_alert_ids or []),
    }
    if degradation_level is not None:
        payload["degradationLevel"] = int(degradation_level)
    return payload


def _build_trace_report_summary(
    *,
    dispatch_type: str,
    payload: dict[str, Any] | None,
    callback_status: str,
    callback_error: str | None,
) -> dict[str, Any]:
    report_payload = payload if isinstance(payload, dict) else {}
    alerts = report_payload.get("auditAlerts")
    if not isinstance(alerts, list):
        alerts = []
    winner = str(report_payload.get("winner") or "").strip().lower() or None
    return {
        "dispatchType": dispatch_type,
        "payload": report_payload,
        "winner": winner,
        "auditAlerts": [item for item in alerts if isinstance(item, dict)],
        "callbackStatus": callback_status,
        "callbackError": callback_error,
    }


def _resolve_idempotency_or_raise(
    *,
    runtime: AppRuntime,
    key: str,
    job_id: int,
    conflict_detail: str,
) -> dict[str, Any] | None:
    resolution = runtime.trace_store.resolve_idempotency(
        key=key,
        job_id=job_id,
        ttl_secs=runtime.settings.idempotency_ttl_secs,
    )
    if resolution.status == "replay" and resolution.record and resolution.record.response:
        replayed = dict(resolution.record.response)
        replayed["idempotentReplay"] = True
        return replayed
    if resolution.status != "acquired":
        raise HTTPException(status_code=409, detail=conflict_detail)
    return None


def _validate_phase_dispatch_request(request: PhaseDispatchRequest) -> None:
    if request.message_count <= 0:
        raise HTTPException(status_code=422, detail="invalid_message_count")
    if request.message_end_id < request.message_start_id:
        raise HTTPException(status_code=422, detail="invalid_message_range")
    if request.message_count != len(request.messages):
        raise HTTPException(status_code=422, detail="message_count_mismatch")
    for message in request.messages:
        if (
            message.message_id < request.message_start_id
            or message.message_id > request.message_end_id
        ):
            raise HTTPException(status_code=422, detail="message_id_out_of_range")


def _validate_final_dispatch_request(request: FinalDispatchRequest) -> None:
    if request.phase_start_no <= 0 or request.phase_end_no <= 0:
        raise HTTPException(status_code=422, detail="invalid_phase_no")
    if request.phase_start_no > request.phase_end_no:
        raise HTTPException(status_code=422, detail="invalid_phase_range")


def _extract_dispatch_meta_from_raw(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "jobId": _extract_optional_int(payload, "job_id", "jobId"),
        "scopeId": _extract_optional_int(payload, "scope_id", "scopeId") or 1,
        "sessionId": _extract_optional_int(payload, "session_id", "sessionId"),
        "traceId": _extract_optional_str(payload, "trace_id", "traceId") or "",
        "idempotencyKey": _extract_optional_str(payload, "idempotency_key", "idempotencyKey") or "",
        "rubricVersion": _extract_optional_str(payload, "rubric_version", "rubricVersion") or "",
        "judgePolicyVersion": _extract_optional_str(
            payload,
            "judge_policy_version",
            "judgePolicyVersion",
        )
        or "",
        "topicDomain": _extract_optional_str(payload, "topic_domain", "topicDomain") or "",
        "retrievalProfile": _extract_optional_str(
            payload,
            "retrieval_profile",
            "retrievalProfile",
        ),
    }


def _extract_receipt_dims_from_raw(
    dispatch_type: str,
    payload: dict[str, Any],
) -> dict[str, int | None]:
    if dispatch_type == "phase":
        return {
            "phaseNo": _extract_optional_int(payload, "phase_no", "phaseNo"),
            "phaseStartNo": None,
            "phaseEndNo": None,
            "messageStartId": _extract_optional_int(payload, "message_start_id", "messageStartId"),
            "messageEndId": _extract_optional_int(payload, "message_end_id", "messageEndId"),
            "messageCount": _extract_optional_int(payload, "message_count", "messageCount"),
        }
    return {
        "phaseNo": None,
        "phaseStartNo": _extract_optional_int(payload, "phase_start_no", "phaseStartNo"),
        "phaseEndNo": _extract_optional_int(payload, "phase_end_no", "phaseEndNo"),
        "messageStartId": None,
        "messageEndId": None,
        "messageCount": None,
    }


def _failed_callback_fn_for_dispatch(runtime: AppRuntime, dispatch_type: str) -> CallbackReportFn:
    return runtime.callback_phase_failed_fn if dispatch_type == "phase" else runtime.callback_final_failed_fn


def _report_callback_fn_for_dispatch(runtime: AppRuntime, dispatch_type: str) -> CallbackReportFn:
    return runtime.callback_phase_report_fn if dispatch_type == "phase" else runtime.callback_final_report_fn


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp_score(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def _resolve_winner(pro_score: float, con_score: float, *, margin: float = 1.0) -> str:
    if pro_score - con_score >= margin:
        return "pro"
    if con_score - pro_score >= margin:
        return "con"
    return "draw"


def _extract_phase_report_payload_from_receipt(receipt: Any) -> tuple[int, dict[str, Any] | None]:
    phase_no = int(getattr(receipt, "phase_no", 0) or 0)
    response = getattr(receipt, "response", None)
    if not isinstance(response, dict):
        return phase_no, None
    report = (
        response.get("reportPayload")
        or response.get("phaseReport")
        or response.get("phase_report_payload")
    )
    if not isinstance(report, dict):
        return phase_no, None
    return phase_no, report


def _extract_agent1_dimensions(payload: dict[str, Any], *, side: str) -> dict[str, float]:
    agent1 = payload.get("agent1Score") if isinstance(payload.get("agent1Score"), dict) else {}
    dimensions = agent1.get("dimensions") if isinstance(agent1.get("dimensions"), dict) else {}
    side_dimensions = dimensions.get(side) if isinstance(dimensions.get(side), dict) else None
    if isinstance(side_dimensions, dict):
        return {
            "logic": _clamp_score(_safe_float(side_dimensions.get("logic"), default=50.0)),
            "evidence": _clamp_score(_safe_float(side_dimensions.get("evidence"), default=50.0)),
            "rebuttal": _clamp_score(_safe_float(side_dimensions.get("rebuttal"), default=50.0)),
            "clarity": _clamp_score(_safe_float(side_dimensions.get("expression"), default=50.0)),
        }
    return {
        "logic": 50.0,
        "evidence": 50.0,
        "rebuttal": 50.0,
        "clarity": 50.0,
    }


def _parse_agent2_ref_item(raw: Any) -> tuple[str, str]:
    text = str(raw or "").strip()
    if not text:
        return "unknown", ""
    if ":" in text:
        prefix, rest = text.split(":", 1)
        side = prefix.strip().lower()
        if side in {"pro", "con"}:
            return side, rest.strip()
    return "unknown", text


def _winner_label(winner: str) -> str:
    mapping = {
        "pro": "pro side",
        "con": "con side",
        "draw": "draw",
    }
    return mapping.get(str(winner or "").strip().lower(), "unknown")


def _build_final_display_payload(
    *,
    style_mode: str,
    winner: str,
    pro_score: float,
    con_score: float,
    phase_count_used: int,
    phase_count_expected: int,
    missing_phase_nos: list[int],
    winner_first: str,
    winner_second: str,
    rejudge_triggered: bool,
    raw_rationale: str,
) -> dict[str, Any]:
    winner_label = _winner_label(winner)
    missing = ",".join(str(no) for no in missing_phase_nos) if missing_phase_nos else "none"
    fact_sentence = (
        f"winner={winner}, pro={round(_clamp_score(pro_score), 2)}, con={round(_clamp_score(con_score), 2)}, "
        f"phases={phase_count_used}/{phase_count_expected}, missing={missing}, "
        f"first={winner_first}, second={winner_second}, rejudge={str(rejudge_triggered).lower()}"
    )

    normalized = str(style_mode or "").strip().lower()
    if normalized == "entertaining":
        debate_summary = (
            f"Final buzzer: {winner_label} takes the edge. Scoreboard pro "
            f"{round(_clamp_score(pro_score), 2)} vs con {round(_clamp_score(con_score), 2)}."
        )
    elif normalized == "mixed":
        debate_summary = (
            f"Final call: {winner_label}. Pro {round(_clamp_score(pro_score), 2)} and "
            f"con {round(_clamp_score(con_score), 2)} after {phase_count_used}/{phase_count_expected} phase(s)."
        )
    else:
        normalized = "rational"
        debate_summary = (
            f"Final verdict: {winner_label}. Scores pro={round(_clamp_score(pro_score), 2)}, "
            f"con={round(_clamp_score(con_score), 2)}."
        )
    side_analysis = {
        "pro": (
            f"Pro side average score {round(_clamp_score(pro_score), 2)}; "
            f"phase coverage {phase_count_used}/{phase_count_expected}."
        ),
        "con": (
            f"Con side average score {round(_clamp_score(con_score), 2)}; "
            f"missing phases={missing}."
        ),
    }
    verdict_reason = (
        f"Consistency check first={winner_first}, second={winner_second}, "
        f"rejudge={str(rejudge_triggered).lower()}. Facts locked: {fact_sentence}."
    )
    return {
        "styleMode": normalized,
        "debateSummary": debate_summary,
        "sideAnalysis": side_analysis,
        "verdictReason": verdict_reason,
        "rationaleRaw": raw_rationale,
        "factLock": {
            "winner": winner,
            "proScore": round(_clamp_score(pro_score), 2),
            "conScore": round(_clamp_score(con_score), 2),
            "phaseCountUsed": phase_count_used,
            "phaseCountExpected": phase_count_expected,
            "missingPhaseNos": list(missing_phase_nos),
            "winnerFirst": winner_first,
            "winnerSecond": winner_second,
            "rejudgeTriggered": rejudge_triggered,
        },
    }


def _validate_final_report_payload_contract(payload: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    winner = str(payload.get("winner") or "").strip().lower()
    if winner not in {"pro", "con", "draw"}:
        missing.append("winner")

    if not isinstance(payload.get("proScore"), (int, float)):
        missing.append("proScore")
    if not isinstance(payload.get("conScore"), (int, float)):
        missing.append("conScore")

    debate_summary = str(payload.get("debateSummary") or "").strip()
    if not debate_summary:
        missing.append("debateSummary")
    verdict_reason = str(payload.get("verdictReason") or "").strip()
    if not verdict_reason:
        missing.append("verdictReason")
    side_analysis = payload.get("sideAnalysis")
    if not isinstance(side_analysis, dict):
        missing.append("sideAnalysis")
    else:
        for side in ("pro", "con"):
            if not str(side_analysis.get(side) or "").strip():
                missing.append(f"sideAnalysis.{side}")

    dimension_scores = payload.get("dimensionScores")
    if not isinstance(dimension_scores, dict):
        missing.append("dimensionScores")
    else:
        for key in ("logic", "evidence", "rebuttal", "clarity"):
            if not isinstance(dimension_scores.get(key), (int, float)):
                missing.append(f"dimensionScores.{key}")

    for key in ("verdictEvidenceRefs", "phaseRollupSummary", "retrievalSnapshotRollup"):
        if not isinstance(payload.get(key), list):
            missing.append(key)

    winner_first = str(payload.get("winnerFirst") or "").strip().lower()
    winner_second = str(payload.get("winnerSecond") or "").strip().lower()
    if winner_first not in {"pro", "con", "draw"}:
        missing.append("winnerFirst")
    if winner_second not in {"pro", "con", "draw"}:
        missing.append("winnerSecond")

    if not isinstance(payload.get("rejudgeTriggered"), bool):
        missing.append("rejudgeTriggered")
    if not isinstance(payload.get("needsDrawVote"), bool):
        missing.append("needsDrawVote")
    if not isinstance(payload.get("errorCodes"), list):
        missing.append("errorCodes")
    if not isinstance(payload.get("degradationLevel"), int):
        missing.append("degradationLevel")

    judge_trace = payload.get("judgeTrace")
    if not isinstance(judge_trace, dict):
        missing.append("judgeTrace")
    else:
        trace_id = str(judge_trace.get("traceId") or "").strip()
        if not trace_id:
            missing.append("judgeTrace.traceId")
    return missing


def _build_final_report_payload(
    *,
    runtime: AppRuntime,
    request: FinalDispatchRequest,
    phase_receipts: list[Any] | None = None,
) -> dict[str, Any]:
    expected_phase_nos = list(range(request.phase_start_no, request.phase_end_no + 1))
    expected_phase_set = set(expected_phase_nos)
    receipts = (
        phase_receipts
        if phase_receipts is not None
        else runtime.trace_store.list_dispatch_receipts(
            dispatch_type="phase",
            session_id=request.session_id,
            status="reported",
            limit=1000,
        )
    )

    phase_reports_by_no: dict[int, tuple[datetime, dict[str, Any]]] = {}
    for receipt in receipts:
        phase_no, report_payload = _extract_phase_report_payload_from_receipt(receipt)
        if phase_no not in expected_phase_set or not isinstance(report_payload, dict):
            continue
        prev = phase_reports_by_no.get(phase_no)
        if prev is not None and prev[0] >= receipt.updated_at:
            continue
        phase_reports_by_no[phase_no] = (receipt.updated_at, report_payload)

    used_phase_nos = sorted(phase_reports_by_no.keys())
    missing_phase_nos = [no for no in expected_phase_nos if no not in phase_reports_by_no]

    phase_rollup_summary: list[dict[str, Any]] = []
    retrieval_snapshot_rollup: list[dict[str, Any]] = []
    retrieval_seen: set[tuple[int, str, str]] = set()
    pro_agent3_scores: list[float] = []
    con_agent3_scores: list[float] = []
    pro_agent2_scores: list[float] = []
    con_agent2_scores: list[float] = []
    pro_dimensions_rows: list[dict[str, float]] = []
    con_dimensions_rows: list[dict[str, float]] = []
    verdict_evidence_refs: list[dict[str, Any]] = []
    score_evidence_rollup: list[dict[str, Any]] = []

    for phase_no in used_phase_nos:
        payload = phase_reports_by_no[phase_no][1]
        agent3 = (
            payload.get("agent3WeightedScore")
            if isinstance(payload.get("agent3WeightedScore"), dict)
            else {}
        )
        agent2 = payload.get("agent2Score") if isinstance(payload.get("agent2Score"), dict) else {}

        pro_agent3 = _clamp_score(_safe_float(agent3.get("pro"), default=50.0))
        con_agent3 = _clamp_score(_safe_float(agent3.get("con"), default=50.0))
        pro_agent2 = _clamp_score(_safe_float(agent2.get("pro"), default=50.0))
        con_agent2 = _clamp_score(_safe_float(agent2.get("con"), default=50.0))
        pro_agent3_scores.append(pro_agent3)
        con_agent3_scores.append(con_agent3)
        pro_agent2_scores.append(pro_agent2)
        con_agent2_scores.append(con_agent2)
        pro_dimensions_rows.append(_extract_agent1_dimensions(payload, side="pro"))
        con_dimensions_rows.append(_extract_agent1_dimensions(payload, side="con"))
        hit_items = [item for item in (agent2.get("hitItems") or []) if str(item or "").strip()]
        miss_items = [item for item in (agent2.get("missItems") or []) if str(item or "").strip()]
        score_evidence_rollup.append(
            {
                "phaseNo": phase_no,
                "agent1Dimensions": {
                    "pro": _extract_agent1_dimensions(payload, side="pro"),
                    "con": _extract_agent1_dimensions(payload, side="con"),
                },
                "agent2": {
                    "proScore": round(pro_agent2, 2),
                    "conScore": round(con_agent2, 2),
                    "hitCount": len(hit_items),
                    "missCount": len(miss_items),
                },
            }
        )

        phase_rollup_summary.append(
            {
                "phaseNo": phase_no,
                "messageStartId": payload.get("messageStartId"),
                "messageEndId": payload.get("messageEndId"),
                "messageCount": payload.get("messageCount"),
                "proScore": round(pro_agent3, 2),
                "conScore": round(con_agent3, 2),
                "winnerHint": _resolve_winner(pro_agent3, con_agent3, margin=0.6),
                "errorCodes": payload.get("errorCodes") or [],
                "degradationLevel": int(payload.get("degradationLevel") or 0),
            }
        )

        agent1 = payload.get("agent1Score") if isinstance(payload.get("agent1Score"), dict) else {}
        refs = agent1.get("evidenceRefs") if isinstance(agent1.get("evidenceRefs"), dict) else {}
        for side in ("pro", "con"):
            ref = refs.get(side) if isinstance(refs.get(side), dict) else {}
            for message_id in ref.get("messageIds") or []:
                if len(verdict_evidence_refs) >= 16:
                    break
                verdict_evidence_refs.append(
                    {
                        "phaseNo": phase_no,
                        "side": side,
                        "type": "message",
                        "messageId": message_id,
                        "reason": "agent1_evidence_ref",
                    }
                )
            for chunk_id in ref.get("chunkIds") or []:
                if len(verdict_evidence_refs) >= 16:
                    break
                verdict_evidence_refs.append(
                    {
                        "phaseNo": phase_no,
                        "side": side,
                        "type": "retrieval_chunk",
                        "chunkId": chunk_id,
                        "reason": "agent1_retrieval_ref",
                    }
                )
        for ref_type, rows in (
            ("agent2_hit", agent2.get("hitItems") or []),
            ("agent2_miss", agent2.get("missItems") or []),
        ):
            for raw in rows:
                if len(verdict_evidence_refs) >= 16:
                    break
                side, content = _parse_agent2_ref_item(raw)
                if not content:
                    continue
                verdict_evidence_refs.append(
                    {
                        "phaseNo": phase_no,
                        "side": side,
                        "type": ref_type,
                        "item": content,
                        "reason": "agent2_path_alignment",
                    }
                )

        for side, bundle_key in (("pro", "proRetrievalBundle"), ("con", "conRetrievalBundle")):
            bundle = payload.get(bundle_key) if isinstance(payload.get(bundle_key), dict) else {}
            for item in bundle.get("items") or []:
                if not isinstance(item, dict):
                    continue
                chunk_id = str(item.get("chunkId") or item.get("chunk_id") or "").strip()
                dedupe_key = (phase_no, side, chunk_id or str(item.get("sourceUrl") or ""))
                if dedupe_key in retrieval_seen:
                    continue
                retrieval_seen.add(dedupe_key)
                retrieval_snapshot_rollup.append(
                    {
                        "phaseNo": phase_no,
                        "side": side,
                        "chunkId": chunk_id or None,
                        "title": item.get("title"),
                        "sourceUrl": item.get("sourceUrl") or item.get("source_url"),
                        "score": _safe_float(item.get("score"), default=0.0),
                        "conflict": bool(item.get("conflict")),
                        "snippet": item.get("snippet"),
                    }
                )
                if len(retrieval_snapshot_rollup) >= 120:
                    break

    if phase_rollup_summary:
        pro_score = round(sum(pro_agent3_scores) / float(len(pro_agent3_scores)), 2)
        con_score = round(sum(con_agent3_scores) / float(len(con_agent3_scores)), 2)
        winner_first = _resolve_winner(pro_score, con_score, margin=0.8)
        second_pro = sum(pro_agent2_scores) / float(max(1, len(pro_agent2_scores)))
        second_con = sum(con_agent2_scores) / float(max(1, len(con_agent2_scores)))
        winner_second = _resolve_winner(second_pro, second_con, margin=0.8)

        if winner_first in {"pro", "con"}:
            winner_side = winner_first
            dims_rows = pro_dimensions_rows if winner_side == "pro" else con_dimensions_rows
        else:
            dims_rows = pro_dimensions_rows + con_dimensions_rows

        def _avg_dim(rows: list[dict[str, float]], key: str, default: float = 50.0) -> float:
            if not rows:
                return default
            return sum(_safe_float(row.get(key), default=default) for row in rows) / float(
                len(rows)
            )

        dimension_scores = {
            "logic": round(_clamp_score(_avg_dim(dims_rows, "logic")), 2),
            "evidence": round(_clamp_score(_avg_dim(dims_rows, "evidence")), 2),
            "rebuttal": round(_clamp_score(_avg_dim(dims_rows, "rebuttal")), 2),
            "clarity": round(_clamp_score(_avg_dim(dims_rows, "clarity")), 2),
        }
    else:
        pro_score = 50.0
        con_score = 50.0
        winner_first = "draw"
        winner_second = "draw"
        dimension_scores = {
            "logic": 50.0,
            "evidence": 50.0,
            "rebuttal": 50.0,
            "clarity": 50.0,
        }

    error_codes: list[str] = []
    if missing_phase_nos:
        error_codes.append("final_rollup_incomplete")
    if not phase_rollup_summary:
        error_codes.append("final_rollup_no_phase_payload")

    rejudge_triggered = False
    winner = winner_first
    if winner_first != winner_second:
        winner = "draw"
        rejudge_triggered = True
        error_codes.append("consistency_conflict")

    needs_draw_vote = winner == "draw"
    if not error_codes:
        degradation_level = 0
    elif phase_rollup_summary:
        degradation_level = 1
    else:
        degradation_level = 2

    if phase_rollup_summary:
        final_rationale_raw = (
            f"A9 final aggregated {len(phase_rollup_summary)} phases "
            f"(expected={len(expected_phase_nos)}), "
            f"agent3_avg: pro={pro_score}, con={con_score}, winner={winner}."
        )
    else:
        final_rationale_raw = (
            "A9 final aggregation fallback: no usable phase report payload was found "
            "in the requested phase range."
        )

    audit_alerts: list[dict[str, Any]] = []
    if missing_phase_nos:
        audit_alerts.append(
            {
                "type": "final_rollup_incomplete",
                "severity": "warning",
                "message": f"missing phase payloads: {missing_phase_nos}",
            }
        )

    final_style_mode, final_style_mode_source = resolve_effective_style_mode(
        "rational",
        runtime.dispatch_runtime_cfg.judge_style_mode,
    )
    display_payload = _build_final_display_payload(
        style_mode=final_style_mode,
        winner=winner,
        pro_score=pro_score,
        con_score=con_score,
        phase_count_used=len(phase_rollup_summary),
        phase_count_expected=len(expected_phase_nos),
        missing_phase_nos=missing_phase_nos,
        winner_first=winner_first,
        winner_second=winner_second,
        rejudge_triggered=rejudge_triggered,
        raw_rationale=final_rationale_raw,
    )
    debate_summary = str(display_payload.get("debateSummary") or "").strip()
    side_analysis = (
        display_payload.get("sideAnalysis") if isinstance(display_payload.get("sideAnalysis"), dict) else {}
    )
    verdict_reason = str(display_payload.get("verdictReason") or final_rationale_raw)

    return {
        "sessionId": request.session_id,
        "winner": winner,
        "proScore": round(_clamp_score(pro_score), 2),
        "conScore": round(_clamp_score(con_score), 2),
        "dimensionScores": dimension_scores,
        "debateSummary": debate_summary,
        "sideAnalysis": side_analysis,
        "verdictReason": verdict_reason,
        "verdictEvidenceRefs": verdict_evidence_refs[:16],
        "phaseRollupSummary": phase_rollup_summary,
        "retrievalSnapshotRollup": retrieval_snapshot_rollup,
        "winnerFirst": winner_first,
        "winnerSecond": winner_second,
        "rejudgeTriggered": rejudge_triggered,
        "needsDrawVote": needs_draw_vote,
        "judgeTrace": {
            "traceId": request.trace_id,
            "pipelineVersion": "v3-final-a9a10-rollup-v2",
            "idempotencyKey": request.idempotency_key,
            "phaseRange": {
                "startNo": request.phase_start_no,
                "endNo": request.phase_end_no,
            },
            "phaseCountExpected": len(expected_phase_nos),
            "phaseCountUsed": len(phase_rollup_summary),
            "phaseNosUsed": used_phase_nos,
            "missingPhaseNos": missing_phase_nos,
            "winnerFirst": winner_first,
            "winnerSecond": winner_second,
            "source": "phase_receipt_report_payload",
            "a9RationaleRaw": final_rationale_raw,
            "displayStyleMode": final_style_mode,
            "displayStyleModeSource": final_style_mode_source,
            "displayDebateSummary": debate_summary,
            "displayVerdictReason": verdict_reason,
            "factLock": display_payload.get("factLock"),
            "scoreEvidenceRollup": score_evidence_rollup,
        },
        "auditAlerts": audit_alerts,
        "errorCodes": error_codes,
        "degradationLevel": degradation_level,
    }


async def _invoke_v3_callback_with_retry(
    *,
    runtime: AppRuntime,
    callback_fn: CallbackReportFn,
    job_id: int,
    payload: dict[str, Any],
) -> tuple[int, int]:
    max_attempts = max(1, int(runtime.dispatch_runtime_cfg.runtime_retry_max_attempts))
    backoff_ms = max(0, int(runtime.dispatch_runtime_cfg.retry_backoff_ms))
    attempt = 0
    last_error: Exception | None = None
    while attempt < max_attempts:
        attempt += 1
        try:
            await callback_fn(job_id, payload)
            return attempt, max(0, attempt - 1)
        except Exception as err:
            last_error = err
            if attempt >= max_attempts:
                break
            if backoff_ms > 0:
                await runtime.sleep_fn((backoff_ms * attempt) / 1000.0)
    raise RuntimeError(
        f"v3 callback failed after {max_attempts} attempts: {last_error or 'unknown'}"
    ) from last_error


def _save_dispatch_receipt(
    *,
    runtime: AppRuntime,
    dispatch_type: str,
    job_id: int,
    scope_id: int,
    session_id: int,
    trace_id: str,
    idempotency_key: str,
    rubric_version: str,
    judge_policy_version: str,
    topic_domain: str,
    retrieval_profile: str | None,
    phase_no: int | None,
    phase_start_no: int | None,
    phase_end_no: int | None,
    message_start_id: int | None,
    message_end_id: int | None,
    message_count: int | None,
    status: str,
    request_payload: dict[str, Any],
    response_payload: dict[str, Any] | None,
) -> None:
    runtime.trace_store.save_dispatch_receipt(
        dispatch_type=dispatch_type,
        job_id=job_id,
        scope_id=scope_id,
        session_id=session_id,
        trace_id=trace_id,
        idempotency_key=idempotency_key,
        rubric_version=rubric_version,
        judge_policy_version=judge_policy_version,
        topic_domain=topic_domain,
        retrieval_profile=retrieval_profile,
        phase_no=phase_no,
        phase_start_no=phase_start_no,
        phase_end_no=phase_end_no,
        message_start_id=message_start_id,
        message_end_id=message_end_id,
        message_count=message_count,
        status=status,
        request=request_payload,
        response=response_payload,
    )


def create_app(runtime: AppRuntime) -> FastAPI:
    app = FastAPI(title="AI Judge Service", version="0.2.0")
    workflow_schema_ready = False
    workflow_schema_lock = asyncio.Lock()

    async def _ensure_workflow_schema_ready() -> None:
        nonlocal workflow_schema_ready
        if workflow_schema_ready or not runtime.settings.db_auto_create_schema:
            return
        async with workflow_schema_lock:
            if workflow_schema_ready:
                return
            await runtime.workflow_runtime.db.create_schema()
            workflow_schema_ready = True

    async def _persist_dispatch_receipt(
        *,
        dispatch_type: str,
        job_id: int,
        scope_id: int,
        session_id: int,
        trace_id: str,
        idempotency_key: str,
        rubric_version: str,
        judge_policy_version: str,
        topic_domain: str,
        retrieval_profile: str | None,
        phase_no: int | None,
        phase_start_no: int | None,
        phase_end_no: int | None,
        message_start_id: int | None,
        message_end_id: int | None,
        message_count: int | None,
        status: str,
        request_payload: dict[str, Any],
        response_payload: dict[str, Any] | None,
    ) -> None:
        _save_dispatch_receipt(
            runtime=runtime,
            dispatch_type=dispatch_type,
            job_id=job_id,
            scope_id=scope_id,
            session_id=session_id,
            trace_id=trace_id,
            idempotency_key=idempotency_key,
            rubric_version=rubric_version,
            judge_policy_version=judge_policy_version,
            topic_domain=topic_domain,
            retrieval_profile=retrieval_profile,
            phase_no=phase_no,
            phase_start_no=phase_start_no,
            phase_end_no=phase_end_no,
            message_start_id=message_start_id,
            message_end_id=message_end_id,
            message_count=message_count,
            status=status,
            request_payload=request_payload,
            response_payload=response_payload,
        )
        await _ensure_workflow_schema_ready()
        await runtime.workflow_runtime.facts.upsert_dispatch_receipt(
            receipt=FactDispatchReceipt(
                dispatch_type=dispatch_type,
                job_id=max(0, int(job_id)),
                scope_id=max(0, int(scope_id)),
                session_id=max(0, int(session_id)),
                trace_id=str(trace_id or "").strip(),
                idempotency_key=str(idempotency_key or "").strip(),
                rubric_version=str(rubric_version or "").strip(),
                judge_policy_version=str(judge_policy_version or "").strip(),
                topic_domain=str(topic_domain or "").strip(),
                retrieval_profile=retrieval_profile,
                phase_no=phase_no,
                phase_start_no=phase_start_no,
                phase_end_no=phase_end_no,
                message_start_id=message_start_id,
                message_end_id=message_end_id,
                message_count=message_count,
                status=str(status or "").strip(),
                request=dict(request_payload or {}),
                response=(dict(response_payload) if isinstance(response_payload, dict) else None),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )

    async def _get_dispatch_receipt(*, dispatch_type: str, job_id: int) -> Any | None:
        await _ensure_workflow_schema_ready()
        receipt = await runtime.workflow_runtime.facts.get_dispatch_receipt(
            dispatch_type=dispatch_type,
            job_id=job_id,
        )
        if receipt is not None:
            return receipt
        return runtime.trace_store.get_dispatch_receipt(
            dispatch_type=dispatch_type,
            job_id=job_id,
        )

    async def _list_dispatch_receipts(
        *,
        dispatch_type: str,
        session_id: int | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> list[Any]:
        await _ensure_workflow_schema_ready()
        receipts = await runtime.workflow_runtime.facts.list_dispatch_receipts(
            dispatch_type=dispatch_type,
            session_id=session_id,
            status=status,
            limit=limit,
        )
        if receipts:
            return list(receipts)
        return list(
            runtime.trace_store.list_dispatch_receipts(
                dispatch_type=dispatch_type,
                session_id=session_id,
                status=status,
                limit=limit,
            )
        )

    async def _append_replay_record(
        *,
        dispatch_type: str,
        job_id: int,
        trace_id: str,
        winner: str | None,
        needs_draw_vote: bool | None,
        provider: str | None,
        report_payload: dict[str, Any] | None,
    ) -> FactReplayRecord:
        await _ensure_workflow_schema_ready()
        return await runtime.workflow_runtime.facts.append_replay_record(
            dispatch_type=dispatch_type,
            job_id=job_id,
            trace_id=trace_id,
            winner=winner,
            needs_draw_vote=needs_draw_vote,
            provider=provider,
            report_payload=report_payload,
        )

    async def _list_replay_records(
        *,
        job_id: int,
        dispatch_type: str | None = None,
        limit: int = 50,
    ) -> list[FactReplayRecord]:
        await _ensure_workflow_schema_ready()
        return await runtime.workflow_runtime.facts.list_replay_records(
            dispatch_type=dispatch_type,
            job_id=job_id,
            limit=limit,
        )

    async def _sync_audit_alert_to_facts(*, alert: Any) -> FactAuditAlert:
        await _ensure_workflow_schema_ready()
        return await runtime.workflow_runtime.facts.upsert_audit_alert(
            alert_id=str(alert.alert_id or "").strip() or None,
            job_id=int(alert.job_id),
            scope_id=int(alert.scope_id),
            trace_id=str(alert.trace_id or "").strip(),
            alert_type=str(alert.alert_type or "").strip(),
            severity=str(alert.severity or "").strip(),
            title=str(alert.title or "").strip(),
            message=str(alert.message or "").strip(),
            details=(dict(alert.details) if isinstance(alert.details, dict) else {}),
            now=getattr(alert, "updated_at", None),
        )

    async def _list_audit_alerts(
        *,
        job_id: int,
        status: str | None,
        limit: int,
    ) -> list[Any]:
        await _ensure_workflow_schema_ready()
        items = await runtime.workflow_runtime.facts.list_audit_alerts(
            job_id=job_id,
            status=status,
            limit=limit,
        )
        if items:
            return items
        return list(
            runtime.trace_store.list_audit_alerts(
                job_id=job_id,
                status=status,
                limit=limit,
            )
        )

    def _build_workflow_job(
        *,
        dispatch_type: str,
        job_id: int,
        trace_id: str,
        scope_id: int,
        session_id: int,
        idempotency_key: str,
        rubric_version: str,
        judge_policy_version: str,
        topic_domain: str,
        retrieval_profile: str | None,
    ) -> WorkflowJob:
        return WorkflowJob(
            job_id=max(0, int(job_id)),
            dispatch_type=str(dispatch_type or "").strip().lower(),
            trace_id=str(trace_id or "").strip(),
            status=WORKFLOW_STATUS_QUEUED,
            scope_id=max(0, int(scope_id)),
            session_id=max(0, int(session_id)),
            idempotency_key=str(idempotency_key or "").strip(),
            rubric_version=str(rubric_version or "").strip(),
            judge_policy_version=str(judge_policy_version or "").strip(),
            topic_domain=str(topic_domain or "").strip().lower() or "default",
            retrieval_profile=(
                str(retrieval_profile).strip()
                if retrieval_profile is not None and str(retrieval_profile).strip()
                else None
            ),
        )

    async def _workflow_register_and_mark_running(
        *,
        job: WorkflowJob,
        event_payload: dict[str, Any] | None = None,
    ) -> None:
        payload = dict(event_payload or {})
        await _ensure_workflow_schema_ready()
        await runtime.workflow_runtime.orchestrator.register_job(
            job=job,
            event_payload=payload,
        )
        await runtime.workflow_runtime.orchestrator.mark_running(
            job_id=job.job_id,
            event_payload=payload,
        )

    async def _workflow_mark_completed(
        *,
        job_id: int,
        event_payload: dict[str, Any] | None = None,
    ) -> None:
        await _ensure_workflow_schema_ready()
        await runtime.workflow_runtime.orchestrator.mark_completed(
            job_id=job_id,
            event_payload=event_payload,
        )

    async def _workflow_mark_failed(
        *,
        job_id: int,
        error_code: str,
        error_message: str,
        event_payload: dict[str, Any] | None = None,
    ) -> None:
        await _ensure_workflow_schema_ready()
        await runtime.workflow_runtime.orchestrator.mark_failed(
            job_id=job_id,
            error_code=error_code,
            error_message=error_message,
            event_payload=event_payload,
        )

    @app.get("/healthz")
    async def healthz() -> dict[str, bool]:
        return {"ok": True}

    async def _handle_blindization_rejection(
        *,
        dispatch_type: str,
        raw_payload: dict[str, Any],
        sensitive_hits: list[str],
    ) -> None:
        meta = _extract_dispatch_meta_from_raw(raw_payload)
        job_id = int(meta.get("jobId") or 0)
        session_id = int(meta.get("sessionId") or 0)
        trace_id = str(meta.get("traceId") or "")
        if job_id <= 0 or session_id <= 0 or not trace_id:
            raise HTTPException(status_code=422, detail="input_not_blinded")
        scope_id = int(meta.get("scopeId") or 1)
        dims = _extract_receipt_dims_from_raw(dispatch_type, raw_payload)
        request_payload = dict(raw_payload)
        runtime.trace_store.register_start(job_id=job_id, trace_id=trace_id, request=request_payload)
        response = {
            "accepted": False,
            "dispatchType": dispatch_type,
            "status": "callback_failed",
            "jobId": job_id,
            "scopeId": scope_id,
            "sessionId": session_id,
            "traceId": trace_id,
        }
        if dispatch_type == "phase":
            response["phaseNo"] = dims.get("phaseNo")
            response["messageCount"] = dims.get("messageCount")
        else:
            response["phaseStartNo"] = dims.get("phaseStartNo")
            response["phaseEndNo"] = dims.get("phaseEndNo")

        error_code = "input_not_blinded"
        error_message = (
            "sensitive fields detected in judge input: " + ",".join(sensitive_hits[:12])
        )
        failed_payload = _build_failed_callback_payload(
            job_id=job_id,
            dispatch_type=dispatch_type,
            trace_id=trace_id,
            error_code=error_code,
            error_message=error_message,
        )
        failed_callback_fn = _failed_callback_fn_for_dispatch(runtime, dispatch_type)
        try:
            failed_attempts, failed_retries = await _invoke_v3_callback_with_retry(
                runtime=runtime,
                callback_fn=failed_callback_fn,
                job_id=job_id,
                payload=failed_payload,
            )
        except Exception as failed_err:
            receipt_response = {
                **response,
                "callbackStatus": "failed_callback_failed",
                "callbackError": error_message,
                "failedCallbackPayload": failed_payload,
                "failedCallbackError": str(failed_err),
            }
            await _persist_dispatch_receipt(
                dispatch_type=dispatch_type,
                job_id=job_id,
                scope_id=scope_id,
                session_id=session_id,
                trace_id=trace_id,
                idempotency_key=str(meta.get("idempotencyKey") or ""),
                rubric_version=str(meta.get("rubricVersion") or ""),
                judge_policy_version=str(meta.get("judgePolicyVersion") or ""),
                topic_domain=str(meta.get("topicDomain") or ""),
                retrieval_profile=(
                    str(meta.get("retrievalProfile")) if meta.get("retrievalProfile") is not None else None
                ),
                phase_no=dims.get("phaseNo"),
                phase_start_no=dims.get("phaseStartNo"),
                phase_end_no=dims.get("phaseEndNo"),
                message_start_id=dims.get("messageStartId"),
                message_end_id=dims.get("messageEndId"),
                message_count=dims.get("messageCount"),
                status="callback_failed",
                request_payload=request_payload,
                response_payload=receipt_response,
            )
            runtime.trace_store.register_failure(
                job_id=job_id,
                response=receipt_response,
                callback_status="failed_callback_failed",
                callback_error=str(failed_err),
            )
            raise HTTPException(
                status_code=502,
                detail=f"{dispatch_type}_failed_callback_failed: {failed_err}",
            ) from failed_err

        receipt_response = {
            **response,
            "callbackStatus": "failed_reported",
            "callbackError": error_message,
            "failedCallbackPayload": failed_payload,
            "failedCallbackAttempts": failed_attempts,
            "failedCallbackRetries": failed_retries,
        }
        await _persist_dispatch_receipt(
            dispatch_type=dispatch_type,
            job_id=job_id,
            scope_id=scope_id,
            session_id=session_id,
            trace_id=trace_id,
            idempotency_key=str(meta.get("idempotencyKey") or ""),
            rubric_version=str(meta.get("rubricVersion") or ""),
            judge_policy_version=str(meta.get("judgePolicyVersion") or ""),
            topic_domain=str(meta.get("topicDomain") or ""),
            retrieval_profile=(
                str(meta.get("retrievalProfile")) if meta.get("retrievalProfile") is not None else None
            ),
            phase_no=dims.get("phaseNo"),
            phase_start_no=dims.get("phaseStartNo"),
            phase_end_no=dims.get("phaseEndNo"),
            message_start_id=dims.get("messageStartId"),
            message_end_id=dims.get("messageEndId"),
            message_count=dims.get("messageCount"),
            status="callback_failed",
            request_payload=request_payload,
            response_payload=receipt_response,
        )
        runtime.trace_store.register_failure(
            job_id=job_id,
            response=receipt_response,
            callback_status="failed_reported",
            callback_error=error_message,
        )
        raise HTTPException(status_code=422, detail=error_code)

    @app.post("/internal/judge/v3/phase/dispatch")
    async def dispatch_judge_phase(
        request: Request,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        try:
            raw_payload = await request.json()
        except Exception as err:
            raise HTTPException(status_code=422, detail=f"invalid_json: {err}") from err
        if not isinstance(raw_payload, dict):
            raise HTTPException(status_code=422, detail="invalid_payload")
        sensitive_hits = _find_sensitive_key_hits(raw_payload)
        if sensitive_hits:
            await _handle_blindization_rejection(
                dispatch_type="phase",
                raw_payload=raw_payload,
                sensitive_hits=sensitive_hits,
            )
        try:
            parsed = PhaseDispatchRequest.model_validate(raw_payload)
        except ValidationError as err:
            raise HTTPException(status_code=422, detail=err.errors()) from err
        _validate_phase_dispatch_request(parsed)

        replayed = _resolve_idempotency_or_raise(
            runtime=runtime,
            key=parsed.idempotency_key,
            job_id=parsed.job_id,
            conflict_detail="idempotency_conflict:phase_dispatch",
        )
        if replayed is not None:
            return replayed

        response = {
            "accepted": True,
            "dispatchType": "phase",
            "status": "queued",
            "jobId": parsed.job_id,
            "scopeId": parsed.scope_id,
            "sessionId": parsed.session_id,
            "phaseNo": parsed.phase_no,
            "messageCount": parsed.message_count,
            "traceId": parsed.trace_id,
        }
        request_payload = parsed.model_dump(mode="json")
        workflow_job = _build_workflow_job(
            dispatch_type="phase",
            job_id=parsed.job_id,
            trace_id=parsed.trace_id,
            scope_id=parsed.scope_id,
            session_id=parsed.session_id,
            idempotency_key=parsed.idempotency_key,
            rubric_version=parsed.rubric_version,
            judge_policy_version=parsed.judge_policy_version,
            topic_domain=parsed.topic_domain,
            retrieval_profile=parsed.retrieval_profile,
        )
        runtime.trace_store.register_start(
            job_id=parsed.job_id,
            trace_id=parsed.trace_id,
            request=request_payload,
        )
        await _persist_dispatch_receipt(
            dispatch_type="phase",
            job_id=parsed.job_id,
            scope_id=parsed.scope_id,
            session_id=parsed.session_id,
            trace_id=parsed.trace_id,
            idempotency_key=parsed.idempotency_key,
            rubric_version=parsed.rubric_version,
            judge_policy_version=parsed.judge_policy_version,
            topic_domain=parsed.topic_domain,
            retrieval_profile=parsed.retrieval_profile,
            phase_no=parsed.phase_no,
            phase_start_no=None,
            phase_end_no=None,
            message_start_id=parsed.message_start_id,
            message_end_id=parsed.message_end_id,
            message_count=parsed.message_count,
            status="queued",
            request_payload=request_payload,
            response_payload=response,
        )
        await _workflow_register_and_mark_running(
            job=workflow_job,
            event_payload={
                "dispatchType": "phase",
                "scopeId": parsed.scope_id,
                "sessionId": parsed.session_id,
                "phaseNo": parsed.phase_no,
                "messageCount": parsed.message_count,
                "traceId": parsed.trace_id,
            },
        )

        phase_report_payload = await build_phase_report_payload_v3(
            request=parsed,
            settings=runtime.settings,
        )
        try:
            callback_attempts, callback_retries = await _invoke_v3_callback_with_retry(
                runtime=runtime,
                callback_fn=_report_callback_fn_for_dispatch(runtime, "phase"),
                job_id=parsed.job_id,
                payload=phase_report_payload,
            )
        except Exception as err:
            error_code = "phase_callback_retry_exhausted"
            error_message = str(err)
            failed_payload = _build_failed_callback_payload(
                job_id=parsed.job_id,
                dispatch_type="phase",
                trace_id=parsed.trace_id,
                error_code=error_code,
                error_message=error_message,
                degradation_level=int(phase_report_payload.get("degradationLevel") or 0),
            )
            try:
                failed_attempts, failed_retries = await _invoke_v3_callback_with_retry(
                    runtime=runtime,
                    callback_fn=_failed_callback_fn_for_dispatch(runtime, "phase"),
                    job_id=parsed.job_id,
                    payload=failed_payload,
                )
            except Exception as failed_err:
                receipt_response = {
                    **response,
                    "status": "callback_failed",
                    "callbackStatus": "failed_callback_failed",
                    "callbackError": error_message,
                    "reportPayload": phase_report_payload,
                    "failedCallbackPayload": failed_payload,
                    "failedCallbackError": str(failed_err),
                }
                await _persist_dispatch_receipt(
                    dispatch_type="phase",
                    job_id=parsed.job_id,
                    scope_id=parsed.scope_id,
                    session_id=parsed.session_id,
                    trace_id=parsed.trace_id,
                    idempotency_key=parsed.idempotency_key,
                    rubric_version=parsed.rubric_version,
                    judge_policy_version=parsed.judge_policy_version,
                    topic_domain=parsed.topic_domain,
                    retrieval_profile=parsed.retrieval_profile,
                    phase_no=parsed.phase_no,
                    phase_start_no=None,
                    phase_end_no=None,
                    message_start_id=parsed.message_start_id,
                    message_end_id=parsed.message_end_id,
                    message_count=parsed.message_count,
                    status="callback_failed",
                    request_payload=request_payload,
                    response_payload=receipt_response,
                )
                runtime.trace_store.register_failure(
                    job_id=parsed.job_id,
                    response=receipt_response,
                    callback_status="failed_callback_failed",
                    callback_error=str(failed_err),
                )
                await _workflow_mark_failed(
                    job_id=parsed.job_id,
                    error_code="phase_failed_callback_failed",
                    error_message=str(failed_err),
                    event_payload={
                        "dispatchType": "phase",
                        "phaseNo": parsed.phase_no,
                        "callbackStatus": "failed_callback_failed",
                    },
                )
                runtime.trace_store.clear_idempotency(parsed.idempotency_key)
                raise HTTPException(
                    status_code=502,
                    detail=f"phase_failed_callback_failed: {failed_err}",
                ) from failed_err

            receipt_response = {
                **response,
                "status": "callback_failed",
                "callbackStatus": "failed_reported",
                "callbackError": error_message,
                "reportPayload": phase_report_payload,
                "failedCallbackPayload": failed_payload,
                "failedCallbackAttempts": failed_attempts,
                "failedCallbackRetries": failed_retries,
            }
            await _persist_dispatch_receipt(
                dispatch_type="phase",
                job_id=parsed.job_id,
                scope_id=parsed.scope_id,
                session_id=parsed.session_id,
                trace_id=parsed.trace_id,
                idempotency_key=parsed.idempotency_key,
                rubric_version=parsed.rubric_version,
                judge_policy_version=parsed.judge_policy_version,
                topic_domain=parsed.topic_domain,
                retrieval_profile=parsed.retrieval_profile,
                phase_no=parsed.phase_no,
                phase_start_no=None,
                phase_end_no=None,
                message_start_id=parsed.message_start_id,
                message_end_id=parsed.message_end_id,
                message_count=parsed.message_count,
                status="callback_failed",
                request_payload=request_payload,
                response_payload=receipt_response,
            )
            runtime.trace_store.register_failure(
                job_id=parsed.job_id,
                response=receipt_response,
                callback_status="failed_reported",
                callback_error=error_message,
            )
            await _workflow_mark_failed(
                job_id=parsed.job_id,
                error_code=error_code,
                error_message=error_message,
                event_payload={
                    "dispatchType": "phase",
                    "phaseNo": parsed.phase_no,
                    "callbackStatus": "failed_reported",
                },
            )
            runtime.trace_store.clear_idempotency(parsed.idempotency_key)
            raise HTTPException(status_code=502, detail=f"phase_callback_failed: {err}") from err

        reported_response = {
            **response,
            "callbackStatus": "reported",
            "callbackAttempts": callback_attempts,
            "callbackRetries": callback_retries,
            "reportPayload": phase_report_payload,
        }
        await _persist_dispatch_receipt(
            dispatch_type="phase",
            job_id=parsed.job_id,
            scope_id=parsed.scope_id,
            session_id=parsed.session_id,
            trace_id=parsed.trace_id,
            idempotency_key=parsed.idempotency_key,
            rubric_version=parsed.rubric_version,
            judge_policy_version=parsed.judge_policy_version,
            topic_domain=parsed.topic_domain,
            retrieval_profile=parsed.retrieval_profile,
            phase_no=parsed.phase_no,
            phase_start_no=None,
            phase_end_no=None,
            message_start_id=parsed.message_start_id,
            message_end_id=parsed.message_end_id,
            message_count=parsed.message_count,
            status="reported",
            request_payload=request_payload,
            response_payload=reported_response,
        )
        runtime.trace_store.register_success(
            job_id=parsed.job_id,
            response=reported_response,
            callback_status="reported",
            report_summary=_build_trace_report_summary(
                dispatch_type="phase",
                payload=phase_report_payload,
                callback_status="reported",
                callback_error=None,
            ),
        )
        await _workflow_mark_completed(
            job_id=parsed.job_id,
            event_payload={
                "dispatchType": "phase",
                "phaseNo": parsed.phase_no,
                "callbackStatus": "reported",
            },
        )
        runtime.trace_store.set_idempotency_success(
            key=parsed.idempotency_key,
            job_id=parsed.job_id,
            response=response,
            ttl_secs=runtime.settings.idempotency_ttl_secs,
        )
        return response

    @app.post("/internal/judge/v3/final/dispatch")
    async def dispatch_judge_final(
        request: Request,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        try:
            raw_payload = await request.json()
        except Exception as err:
            raise HTTPException(status_code=422, detail=f"invalid_json: {err}") from err
        if not isinstance(raw_payload, dict):
            raise HTTPException(status_code=422, detail="invalid_payload")
        sensitive_hits = _find_sensitive_key_hits(raw_payload)
        if sensitive_hits:
            await _handle_blindization_rejection(
                dispatch_type="final",
                raw_payload=raw_payload,
                sensitive_hits=sensitive_hits,
            )
        try:
            parsed = FinalDispatchRequest.model_validate(raw_payload)
        except ValidationError as err:
            raise HTTPException(status_code=422, detail=err.errors()) from err
        _validate_final_dispatch_request(parsed)

        replayed = _resolve_idempotency_or_raise(
            runtime=runtime,
            key=parsed.idempotency_key,
            job_id=parsed.job_id,
            conflict_detail="idempotency_conflict:final_dispatch",
        )
        if replayed is not None:
            return replayed

        response = {
            "accepted": True,
            "dispatchType": "final",
            "status": "queued",
            "jobId": parsed.job_id,
            "scopeId": parsed.scope_id,
            "sessionId": parsed.session_id,
            "phaseStartNo": parsed.phase_start_no,
            "phaseEndNo": parsed.phase_end_no,
            "traceId": parsed.trace_id,
        }
        request_payload = parsed.model_dump(mode="json")
        workflow_job = _build_workflow_job(
            dispatch_type="final",
            job_id=parsed.job_id,
            trace_id=parsed.trace_id,
            scope_id=parsed.scope_id,
            session_id=parsed.session_id,
            idempotency_key=parsed.idempotency_key,
            rubric_version=parsed.rubric_version,
            judge_policy_version=parsed.judge_policy_version,
            topic_domain=parsed.topic_domain,
            retrieval_profile=None,
        )
        runtime.trace_store.register_start(
            job_id=parsed.job_id,
            trace_id=parsed.trace_id,
            request=request_payload,
        )
        await _persist_dispatch_receipt(
            dispatch_type="final",
            job_id=parsed.job_id,
            scope_id=parsed.scope_id,
            session_id=parsed.session_id,
            trace_id=parsed.trace_id,
            idempotency_key=parsed.idempotency_key,
            rubric_version=parsed.rubric_version,
            judge_policy_version=parsed.judge_policy_version,
            topic_domain=parsed.topic_domain,
            retrieval_profile=None,
            phase_no=None,
            phase_start_no=parsed.phase_start_no,
            phase_end_no=parsed.phase_end_no,
            message_start_id=None,
            message_end_id=None,
            message_count=None,
            status="queued",
            request_payload=request_payload,
            response_payload=response,
        )
        await _workflow_register_and_mark_running(
            job=workflow_job,
            event_payload={
                "dispatchType": "final",
                "scopeId": parsed.scope_id,
                "sessionId": parsed.session_id,
                "phaseStartNo": parsed.phase_start_no,
                "phaseEndNo": parsed.phase_end_no,
                "traceId": parsed.trace_id,
            },
        )

        phase_receipts = await _list_dispatch_receipts(
            dispatch_type="phase",
            session_id=parsed.session_id,
            status="reported",
            limit=1000,
        )
        final_report_payload = _build_final_report_payload(
            runtime=runtime,
            request=parsed,
            phase_receipts=phase_receipts,
        )
        contract_missing_fields = _validate_final_report_payload_contract(final_report_payload)
        if contract_missing_fields:
            error_text = "final_contract_violation: missing_fields=" + ",".join(
                contract_missing_fields[:12]
            )
            alert = runtime.trace_store.upsert_audit_alert(
                job_id=parsed.job_id,
                scope_id=parsed.scope_id,
                trace_id=parsed.trace_id,
                alert_type="final_contract_violation",
                severity="critical",
                title="AI Judge Final Contract Violation",
                message=error_text,
                details={
                    "dispatchType": "final",
                    "sessionId": parsed.session_id,
                    "phaseRange": {
                        "startNo": parsed.phase_start_no,
                        "endNo": parsed.phase_end_no,
                    },
                    "missingFields": contract_missing_fields,
                    "errorCode": "final_contract_blocked",
                },
            )
            await _sync_audit_alert_to_facts(alert=alert)
            failed_payload = _build_failed_callback_payload(
                job_id=parsed.job_id,
                dispatch_type="final",
                trace_id=parsed.trace_id,
                error_code="final_contract_blocked",
                error_message=error_text,
                audit_alert_ids=[alert.alert_id],
                degradation_level=int(final_report_payload.get("degradationLevel") or 0),
            )
            try:
                failed_attempts, failed_retries = await _invoke_v3_callback_with_retry(
                    runtime=runtime,
                    callback_fn=_failed_callback_fn_for_dispatch(runtime, "final"),
                    job_id=parsed.job_id,
                    payload=failed_payload,
                )
            except Exception as failed_err:
                receipt_response = {
                    **response,
                    "status": "callback_failed",
                    "callbackStatus": "failed_callback_failed",
                    "callbackError": error_text,
                    "auditAlertIds": [alert.alert_id],
                    "reportPayload": final_report_payload,
                    "failedCallbackPayload": failed_payload,
                    "failedCallbackError": str(failed_err),
                }
                await _persist_dispatch_receipt(
                    dispatch_type="final",
                    job_id=parsed.job_id,
                    scope_id=parsed.scope_id,
                    session_id=parsed.session_id,
                    trace_id=parsed.trace_id,
                    idempotency_key=parsed.idempotency_key,
                    rubric_version=parsed.rubric_version,
                    judge_policy_version=parsed.judge_policy_version,
                    topic_domain=parsed.topic_domain,
                    retrieval_profile=None,
                    phase_no=None,
                    phase_start_no=parsed.phase_start_no,
                    phase_end_no=parsed.phase_end_no,
                    message_start_id=None,
                    message_end_id=None,
                    message_count=None,
                    status="callback_failed",
                    request_payload=request_payload,
                    response_payload=receipt_response,
                )
                runtime.trace_store.register_failure(
                    job_id=parsed.job_id,
                    response=receipt_response,
                    callback_status="failed_callback_failed",
                    callback_error=str(failed_err),
                )
                await _workflow_mark_failed(
                    job_id=parsed.job_id,
                    error_code="final_failed_callback_failed",
                    error_message=str(failed_err),
                    event_payload={
                        "dispatchType": "final",
                        "phaseStartNo": parsed.phase_start_no,
                        "phaseEndNo": parsed.phase_end_no,
                        "callbackStatus": "failed_callback_failed",
                    },
                )
                runtime.trace_store.clear_idempotency(parsed.idempotency_key)
                raise HTTPException(
                    status_code=502,
                    detail=f"final_failed_callback_failed: {failed_err}",
                ) from failed_err

            receipt_response = {
                **response,
                "status": "callback_failed",
                "callbackStatus": "blocked_failed_reported",
                "callbackError": error_text,
                "auditAlertIds": [alert.alert_id],
                "reportPayload": final_report_payload,
                "failedCallbackPayload": failed_payload,
                "failedCallbackAttempts": failed_attempts,
                "failedCallbackRetries": failed_retries,
            }
            await _persist_dispatch_receipt(
                dispatch_type="final",
                job_id=parsed.job_id,
                scope_id=parsed.scope_id,
                session_id=parsed.session_id,
                trace_id=parsed.trace_id,
                idempotency_key=parsed.idempotency_key,
                rubric_version=parsed.rubric_version,
                judge_policy_version=parsed.judge_policy_version,
                topic_domain=parsed.topic_domain,
                retrieval_profile=None,
                phase_no=None,
                phase_start_no=parsed.phase_start_no,
                phase_end_no=parsed.phase_end_no,
                message_start_id=None,
                message_end_id=None,
                message_count=None,
                status="callback_failed",
                request_payload=request_payload,
                response_payload=receipt_response,
            )
            runtime.trace_store.register_failure(
                job_id=parsed.job_id,
                response=receipt_response,
                callback_status="blocked_failed_reported",
                callback_error=error_text,
            )
            await _workflow_mark_failed(
                job_id=parsed.job_id,
                error_code="final_contract_blocked",
                error_message=error_text,
                event_payload={
                    "dispatchType": "final",
                    "phaseStartNo": parsed.phase_start_no,
                    "phaseEndNo": parsed.phase_end_no,
                    "callbackStatus": "blocked_failed_reported",
                    "missingFields": contract_missing_fields[:12],
                },
            )
            runtime.trace_store.clear_idempotency(parsed.idempotency_key)
            raise HTTPException(
                status_code=502,
                detail="final_contract_blocked: missing_critical_fields",
            )

        try:
            callback_attempts, callback_retries = await _invoke_v3_callback_with_retry(
                runtime=runtime,
                callback_fn=_report_callback_fn_for_dispatch(runtime, "final"),
                job_id=parsed.job_id,
                payload=final_report_payload,
            )
        except Exception as err:
            error_code = "final_callback_retry_exhausted"
            error_message = str(err)
            failed_payload = _build_failed_callback_payload(
                job_id=parsed.job_id,
                dispatch_type="final",
                trace_id=parsed.trace_id,
                error_code=error_code,
                error_message=error_message,
                degradation_level=int(final_report_payload.get("degradationLevel") or 0),
            )
            try:
                failed_attempts, failed_retries = await _invoke_v3_callback_with_retry(
                    runtime=runtime,
                    callback_fn=_failed_callback_fn_for_dispatch(runtime, "final"),
                    job_id=parsed.job_id,
                    payload=failed_payload,
                )
            except Exception as failed_err:
                receipt_response = {
                    **response,
                    "status": "callback_failed",
                    "callbackStatus": "failed_callback_failed",
                    "callbackError": error_message,
                    "reportPayload": final_report_payload,
                    "failedCallbackPayload": failed_payload,
                    "failedCallbackError": str(failed_err),
                }
                await _persist_dispatch_receipt(
                    dispatch_type="final",
                    job_id=parsed.job_id,
                    scope_id=parsed.scope_id,
                    session_id=parsed.session_id,
                    trace_id=parsed.trace_id,
                    idempotency_key=parsed.idempotency_key,
                    rubric_version=parsed.rubric_version,
                    judge_policy_version=parsed.judge_policy_version,
                    topic_domain=parsed.topic_domain,
                    retrieval_profile=None,
                    phase_no=None,
                    phase_start_no=parsed.phase_start_no,
                    phase_end_no=parsed.phase_end_no,
                    message_start_id=None,
                    message_end_id=None,
                    message_count=None,
                    status="callback_failed",
                    request_payload=request_payload,
                    response_payload=receipt_response,
                )
                runtime.trace_store.register_failure(
                    job_id=parsed.job_id,
                    response=receipt_response,
                    callback_status="failed_callback_failed",
                    callback_error=str(failed_err),
                )
                await _workflow_mark_failed(
                    job_id=parsed.job_id,
                    error_code="final_failed_callback_failed",
                    error_message=str(failed_err),
                    event_payload={
                        "dispatchType": "final",
                        "phaseStartNo": parsed.phase_start_no,
                        "phaseEndNo": parsed.phase_end_no,
                        "callbackStatus": "failed_callback_failed",
                    },
                )
                runtime.trace_store.clear_idempotency(parsed.idempotency_key)
                raise HTTPException(
                    status_code=502,
                    detail=f"final_failed_callback_failed: {failed_err}",
                ) from failed_err

            receipt_response = {
                **response,
                "status": "callback_failed",
                "callbackStatus": "failed_reported",
                "callbackError": error_message,
                "reportPayload": final_report_payload,
                "failedCallbackPayload": failed_payload,
                "failedCallbackAttempts": failed_attempts,
                "failedCallbackRetries": failed_retries,
            }
            await _persist_dispatch_receipt(
                dispatch_type="final",
                job_id=parsed.job_id,
                scope_id=parsed.scope_id,
                session_id=parsed.session_id,
                trace_id=parsed.trace_id,
                idempotency_key=parsed.idempotency_key,
                rubric_version=parsed.rubric_version,
                judge_policy_version=parsed.judge_policy_version,
                topic_domain=parsed.topic_domain,
                retrieval_profile=None,
                phase_no=None,
                phase_start_no=parsed.phase_start_no,
                phase_end_no=parsed.phase_end_no,
                message_start_id=None,
                message_end_id=None,
                message_count=None,
                status="callback_failed",
                request_payload=request_payload,
                response_payload=receipt_response,
            )
            runtime.trace_store.register_failure(
                job_id=parsed.job_id,
                response=receipt_response,
                callback_status="failed_reported",
                callback_error=error_message,
            )
            await _workflow_mark_failed(
                job_id=parsed.job_id,
                error_code=error_code,
                error_message=error_message,
                event_payload={
                    "dispatchType": "final",
                    "phaseStartNo": parsed.phase_start_no,
                    "phaseEndNo": parsed.phase_end_no,
                    "callbackStatus": "failed_reported",
                },
            )
            runtime.trace_store.clear_idempotency(parsed.idempotency_key)
            raise HTTPException(status_code=502, detail=f"final_callback_failed: {err}") from err

        reported_response = {
            **response,
            "callbackStatus": "reported",
            "callbackAttempts": callback_attempts,
            "callbackRetries": callback_retries,
            "reportPayload": final_report_payload,
        }
        await _persist_dispatch_receipt(
            dispatch_type="final",
            job_id=parsed.job_id,
            scope_id=parsed.scope_id,
            session_id=parsed.session_id,
            trace_id=parsed.trace_id,
            idempotency_key=parsed.idempotency_key,
            rubric_version=parsed.rubric_version,
            judge_policy_version=parsed.judge_policy_version,
            topic_domain=parsed.topic_domain,
            retrieval_profile=None,
            phase_no=None,
            phase_start_no=parsed.phase_start_no,
            phase_end_no=parsed.phase_end_no,
            message_start_id=None,
            message_end_id=None,
            message_count=None,
            status="reported",
            request_payload=request_payload,
            response_payload=reported_response,
        )
        runtime.trace_store.register_success(
            job_id=parsed.job_id,
            response=reported_response,
            callback_status="reported",
            report_summary=_build_trace_report_summary(
                dispatch_type="final",
                payload=final_report_payload,
                callback_status="reported",
                callback_error=None,
            ),
        )
        await _workflow_mark_completed(
            job_id=parsed.job_id,
            event_payload={
                "dispatchType": "final",
                "phaseStartNo": parsed.phase_start_no,
                "phaseEndNo": parsed.phase_end_no,
                "callbackStatus": "reported",
                "winner": final_report_payload.get("winner"),
            },
        )
        runtime.trace_store.set_idempotency_success(
            key=parsed.idempotency_key,
            job_id=parsed.job_id,
            response=response,
            ttl_secs=runtime.settings.idempotency_ttl_secs,
        )
        return response

    @app.get("/internal/judge/v3/phase/jobs/{job_id}/receipt")
    async def get_phase_dispatch_receipt(
        job_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        item = await _get_dispatch_receipt(dispatch_type="phase", job_id=job_id)
        if item is None:
            raise HTTPException(status_code=404, detail="phase_dispatch_receipt_not_found")
        return _serialize_dispatch_receipt(item)

    @app.get("/internal/judge/v3/final/jobs/{job_id}/receipt")
    async def get_final_dispatch_receipt(
        job_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        item = await _get_dispatch_receipt(dispatch_type="final", job_id=job_id)
        if item is None:
            raise HTTPException(status_code=404, detail="final_dispatch_receipt_not_found")
        return _serialize_dispatch_receipt(item)

    @app.get("/internal/judge/jobs/{job_id}/trace")
    async def get_judge_job_trace(
        job_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        record = runtime.trace_store.get_trace(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="judge_trace_not_found")
        replay_records = await _list_replay_records(job_id=job_id, limit=50)
        replay_items = (
            [
                {
                    "replayedAt": item.created_at.isoformat(),
                    "winner": item.winner,
                    "needsDrawVote": item.needs_draw_vote,
                    "provider": item.provider,
                }
                for item in replay_records
            ]
            if replay_records
            else [
                {
                    "replayedAt": item.replayed_at.isoformat(),
                    "winner": item.winner,
                    "needsDrawVote": item.needs_draw_vote,
                    "provider": item.provider,
                }
                for item in record.replays
            ]
        )
        return {
            "jobId": record.job_id,
            "traceId": record.trace_id,
            "status": record.status,
            "createdAt": record.created_at.isoformat(),
            "updatedAt": record.updated_at.isoformat(),
            "callbackStatus": record.callback_status,
            "callbackError": record.callback_error,
            "response": record.response,
            "request": record.request,
            "reportSummary": record.report_summary,
            "replays": replay_items,
        }

    @app.post("/internal/judge/jobs/{job_id}/replay")
    async def replay_judge_job(
        job_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        dispatch_type_normalized = str(dispatch_type or "auto").strip().lower()
        if dispatch_type_normalized not in {"auto", "phase", "final"}:
            raise HTTPException(status_code=422, detail="invalid_dispatch_type")

        chosen_dispatch_type = dispatch_type_normalized
        chosen_receipt = None
        if dispatch_type_normalized == "auto":
            final_receipt = await _get_dispatch_receipt(
                dispatch_type="final",
                job_id=job_id,
            )
            phase_receipt = await _get_dispatch_receipt(
                dispatch_type="phase",
                job_id=job_id,
            )
            chosen_receipt = final_receipt or phase_receipt
            if chosen_receipt is None:
                raise HTTPException(status_code=404, detail="replay_receipt_not_found")
            chosen_dispatch_type = "final" if final_receipt is not None else "phase"
        else:
            chosen_receipt = await _get_dispatch_receipt(
                dispatch_type=dispatch_type_normalized,
                job_id=job_id,
            )
            if chosen_receipt is None:
                raise HTTPException(status_code=404, detail="replay_receipt_not_found")

        request_snapshot = (
            chosen_receipt.request if isinstance(chosen_receipt.request, dict) else {}
        )
        trace_id = str(chosen_receipt.trace_id or request_snapshot.get("traceId") or "").strip()
        if not trace_id:
            raise HTTPException(status_code=409, detail="replay_missing_trace_id")

        report_payload: dict[str, Any]
        if chosen_dispatch_type == "final":
            try:
                final_request = FinalDispatchRequest.model_validate(request_snapshot)
            except ValidationError as err:
                raise HTTPException(status_code=409, detail=f"replay_invalid_final_request: {err}") from err
            _validate_final_dispatch_request(final_request)
            phase_receipts = await _list_dispatch_receipts(
                dispatch_type="phase",
                session_id=final_request.session_id,
                status="reported",
                limit=1000,
            )
            report_payload = _build_final_report_payload(
                runtime=runtime,
                request=final_request,
                phase_receipts=phase_receipts,
            )
        else:
            try:
                phase_request = PhaseDispatchRequest.model_validate(request_snapshot)
            except ValidationError as err:
                raise HTTPException(status_code=409, detail=f"replay_invalid_phase_request: {err}") from err
            _validate_phase_dispatch_request(phase_request)
            report_payload = await build_phase_report_payload_v3(
                request=phase_request,
                settings=runtime.settings,
            )

        winner = str(report_payload.get("winner") or "").strip().lower()
        if winner not in {"pro", "con", "draw"}:
            agent3 = (
                report_payload.get("agent3WeightedScore")
                if isinstance(report_payload.get("agent3WeightedScore"), dict)
                else {}
            )
            winner = _resolve_winner(
                _safe_float(agent3.get("pro"), default=50.0),
                _safe_float(agent3.get("con"), default=50.0),
                margin=0.8,
            )
        needs_draw_vote = bool(report_payload.get("needsDrawVote")) if "needsDrawVote" in report_payload else winner == "draw"

        if runtime.trace_store.get_trace(job_id) is None:
            runtime.trace_store.register_start(
                job_id=job_id,
                trace_id=trace_id,
                request=request_snapshot,
            )
        runtime.trace_store.mark_replay(
            job_id=job_id,
            winner=winner,
            needs_draw_vote=needs_draw_vote,
            provider=runtime.settings.provider,
        )
        replay_row = await _append_replay_record(
            dispatch_type=chosen_dispatch_type,
            job_id=job_id,
            trace_id=trace_id,
            winner=winner,
            needs_draw_vote=needs_draw_vote,
            provider=runtime.settings.provider,
            report_payload=report_payload,
        )
        replayed_at = replay_row.created_at.isoformat()

        return {
            "jobId": job_id,
            "dispatchType": chosen_dispatch_type,
            "replayedAt": replayed_at,
            "reportPayload": report_payload,
            "winner": winner,
            "needsDrawVote": needs_draw_vote,
            "traceId": trace_id,
        }

    @app.get("/internal/judge/jobs/{job_id}/replay/report")
    async def get_judge_replay_report(
        job_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        record = runtime.trace_store.get_trace(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="judge_trace_not_found")
        return _build_replay_report_payload(record)

    @app.get("/internal/judge/jobs/replay/reports")
    async def list_judge_replay_reports(
        x_ai_internal_key: str | None = Header(default=None),
        status: str | None = Query(default=None),
        winner: str | None = Query(default=None),
        callback_status: str | None = Query(default=None),
        trace_id: str | None = Query(default=None),
        created_after: datetime | None = Query(default=None),
        created_before: datetime | None = Query(default=None),
        has_audit_alert: bool | None = Query(default=None),
        limit: int = Query(default=20, ge=1, le=200),
        include_report: bool = Query(default=False),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        normalized_created_after = _normalize_query_datetime(created_after)
        normalized_created_before = _normalize_query_datetime(created_before)
        query = TraceQuery(
            status=status,
            winner=winner,
            callback_status=callback_status,
            trace_id=trace_id,
            created_after=normalized_created_after,
            created_before=normalized_created_before,
            has_audit_alert=has_audit_alert,
            limit=limit,
        )
        records = runtime.trace_store.list_traces(query=query)
        if include_report:
            items = [_build_replay_report_payload(record) for record in records]
        else:
            items = [_build_replay_report_summary(record) for record in records]
        return {
            "count": len(items),
            "items": items,
            "filters": {
                "status": status,
                "winner": winner,
                "callbackStatus": callback_status,
                "traceId": trace_id,
                "createdAfter": normalized_created_after.isoformat()
                if normalized_created_after
                else None,
                "createdBefore": normalized_created_before.isoformat()
                if normalized_created_before
                else None,
                "hasAuditAlert": has_audit_alert,
                "limit": limit,
                "includeReport": include_report,
            },
        }

    @app.get("/internal/judge/jobs/{job_id}/alerts")
    async def list_judge_job_alerts(
        job_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        status: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        items = await _list_audit_alerts(
            job_id=job_id,
            status=status,
            limit=limit,
        )
        return {
            "jobId": job_id,
            "count": len(items),
            "items": [_serialize_alert_item(item) for item in items],
        }

    async def _transition_alert_status(
        *,
        job_id: int,
        alert_id: str,
        to_status: str,
        actor: str | None,
        reason: str | None,
    ) -> dict[str, Any]:
        row = runtime.trace_store.transition_audit_alert(
            job_id=job_id,
            alert_id=alert_id,
            to_status=to_status,
            actor=actor,
            reason=reason,
        )
        if row is None:
            raise HTTPException(status_code=409, detail="invalid_alert_status_transition")
        await _sync_audit_alert_to_facts(alert=row)
        transitioned = await runtime.workflow_runtime.facts.transition_audit_alert(
            alert_id=alert_id,
            to_status=to_status,
            now=row.updated_at,
        )
        if transitioned is None:
            raise HTTPException(status_code=409, detail="invalid_alert_status_transition")
        return {
            "ok": True,
            "jobId": job_id,
            "alertId": alert_id,
            "status": transitioned.status,
            "item": _serialize_alert_item(transitioned),
        }

    @app.post("/internal/judge/jobs/{job_id}/alerts/{alert_id}/ack")
    async def ack_judge_job_alert(
        job_id: int,
        alert_id: str,
        x_ai_internal_key: str | None = Header(default=None),
        actor: str | None = Query(default=None),
        reason: str | None = Query(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _transition_alert_status(
            job_id=job_id,
            alert_id=alert_id,
            to_status="acked",
            actor=actor,
            reason=reason,
        )

    @app.post("/internal/judge/jobs/{job_id}/alerts/{alert_id}/resolve")
    async def resolve_judge_job_alert(
        job_id: int,
        alert_id: str,
        x_ai_internal_key: str | None = Header(default=None),
        actor: str | None = Query(default=None),
        reason: str | None = Query(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _transition_alert_status(
            job_id=job_id,
            alert_id=alert_id,
            to_status="resolved",
            actor=actor,
            reason=reason,
        )

    @app.get("/internal/judge/alerts/outbox")
    async def list_judge_alert_outbox(
        x_ai_internal_key: str | None = Header(default=None),
        delivery_status: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        rows = runtime.trace_store.list_alert_outbox(
            delivery_status=delivery_status,
            limit=limit,
        )
        return {
            "count": len(rows),
            "items": [_serialize_outbox_event(item) for item in rows],
            "filters": {
                "deliveryStatus": delivery_status,
                "limit": limit,
            },
        }

    @app.post("/internal/judge/alerts/outbox/{event_id}/delivery")
    async def mark_judge_alert_outbox_delivery(
        event_id: str,
        x_ai_internal_key: str | None = Header(default=None),
        delivery_status: str = Query(default="sent"),
        error_message: str | None = Query(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        item = runtime.trace_store.mark_alert_outbox_delivery(
            event_id=event_id,
            delivery_status=delivery_status,
            error_message=error_message,
        )
        if item is None:
            raise HTTPException(status_code=404, detail="alert_outbox_event_not_found")
        return {
            "ok": True,
            "item": _serialize_outbox_event(item),
        }

    @app.get("/internal/judge/rag/diagnostics")
    async def get_rag_diagnostics(
        job_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        record = runtime.trace_store.get_trace(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="judge_trace_not_found")
        report_summary = record.report_summary or {}
        payload = report_summary.get("payload") or {}
        return {
            "jobId": job_id,
            "traceId": record.trace_id,
            "retrievalDiagnostics": payload.get("retrievalDiagnostics"),
            "ragSources": payload.get("ragSources"),
            "ragBackend": payload.get("ragBackend"),
            "ragRequestedBackend": payload.get("ragRequestedBackend"),
            "ragBackendFallbackReason": payload.get("ragBackendFallbackReason"),
        }

    return app


def create_default_app(*, load_settings_fn: LoadSettingsFn = load_settings) -> FastAPI:
    return create_app(
        create_runtime(
            settings=load_settings_fn(),
        )
    )
