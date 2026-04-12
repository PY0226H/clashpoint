from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Header, HTTPException, Query

from .callback_client import (
    callback_final_report,
    callback_phase_report,
)
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
    sleep_fn: SleepFn
    trace_store: TraceStoreProtocol


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
    sleep_fn: SleepFn = asyncio.sleep,
) -> AppRuntime:
    trace_store = build_trace_store_from_settings(settings=settings)
    callback_cfg = build_callback_client_config(settings)
    callback_phase_report_fn, callback_final_report_fn = build_v3_dispatch_callbacks(
        cfg=callback_cfg,
        callback_phase_report_impl=callback_phase_report_impl,
        callback_final_report_impl=callback_final_report_impl,
    )
    return AppRuntime(
        settings=settings,
        dispatch_runtime_cfg=build_dispatch_runtime_config(settings),
        callback_phase_report_fn=callback_phase_report_fn,
        callback_final_report_fn=callback_final_report_fn,
        sleep_fn=sleep_fn,
        trace_store=trace_store,
    )


def _serialize_alert_item(alert: Any) -> dict[str, Any]:
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
            for row in alert.transitions
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

    payload = report_summary.get("payload")
    if not isinstance(payload, dict):
        payload = {}
    response_audit_alert = response.get("auditAlert")
    payload_audit_alerts = payload.get("auditAlerts")
    audit_alerts: list[dict[str, Any]] = []
    if isinstance(payload_audit_alerts, list):
        audit_alerts.extend([row for row in payload_audit_alerts if isinstance(row, dict)])
    if isinstance(response_audit_alert, dict):
        audit_alerts.append(response_audit_alert)

    stage_summaries = report_summary.get("stage_summaries") or report_summary.get("stageSummaries")
    if not isinstance(stage_summaries, list):
        stage_summaries = []

    return {
        "jobId": record.job_id,
        "traceId": record.trace_id,
        "status": record.status,
        "requestInput": {
            "job": request.get("job") or {},
            "session": request.get("session") or {},
            "topic": request.get("topic") or {},
            "messages": request.get("messages") or [],
            "messageWindowSize": request.get("message_window_size")
            or request.get("messageWindowSize"),
            "rubricVersion": request.get("rubric_version") or request.get("rubricVersion"),
            "judgePolicyVersion": request.get("judge_policy_version")
            or request.get("judgePolicyVersion"),
            "retrievalProfile": request.get("retrieval_profile") or request.get("retrievalProfile"),
        },
        "pipeline": {
            "agentPipeline": payload.get("agentPipeline"),
            "stageSummaries": stage_summaries,
            "winnerFirst": report_summary.get("winner_first") or report_summary.get("winnerFirst"),
            "winnerSecond": report_summary.get("winner_second")
            or report_summary.get("winnerSecond"),
            "finalWinner": report_summary.get("winner"),
            "needsDrawVote": report_summary.get("needs_draw_vote")
            or report_summary.get("needsDrawVote"),
            "rationale": report_summary.get("rationale"),
            "proSummary": report_summary.get("pro_summary") or report_summary.get("proSummary"),
            "conSummary": report_summary.get("con_summary") or report_summary.get("conSummary"),
        },
        "judgeAudit": payload.get("judgeAudit"),
        "auditAlerts": audit_alerts,
        "callbackResult": {
            "callbackStatus": record.callback_status,
            "callbackError": record.callback_error,
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
    callback_result = payload.get("callbackResult")
    response = callback_result.get("response") if isinstance(callback_result, dict) else {}
    if not isinstance(response, dict):
        response = {}
    pipeline = payload.get("pipeline")
    if not isinstance(pipeline, dict):
        pipeline = {}
    audit_alerts = payload.get("auditAlerts")
    if not isinstance(audit_alerts, list):
        audit_alerts = []
    return {
        "jobId": payload.get("jobId"),
        "traceId": payload.get("traceId"),
        "status": payload.get("status"),
        "createdAt": record.created_at.isoformat(),
        "updatedAt": record.updated_at.isoformat(),
        "winner": pipeline.get("finalWinner"),
        "needsDrawVote": pipeline.get("needsDrawVote"),
        "provider": response.get("provider"),
        "errorCode": response.get("errorCode"),
        "callbackStatus": callback_result.get("callbackStatus")
        if isinstance(callback_result, dict)
        else None,
        "callbackError": callback_result.get("callbackError")
        if isinstance(callback_result, dict)
        else None,
        "auditAlertCount": len([row for row in audit_alerts if isinstance(row, dict)]),
        "replayCount": len(payload.get("replays") or []),
    }


def _normalize_query_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


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
        headline = f"Final buzzer: {winner_label} takes the edge"
        rationale_display = (
            f"{headline}. Scoreboard says pro {round(_clamp_score(pro_score), 2)} vs "
            f"con {round(_clamp_score(con_score), 2)}. Reviewed {phase_count_used}/{phase_count_expected} phase(s). "
            f"Consistency check: first={winner_first}, second={winner_second}. "
            f"Facts locked: {fact_sentence}."
        )
    elif normalized == "mixed":
        headline = f"Final call: {winner_label}"
        rationale_display = (
            f"{headline}. Pro {round(_clamp_score(pro_score), 2)} and con {round(_clamp_score(con_score), 2)} "
            f"after {phase_count_used}/{phase_count_expected} phase(s). "
            f"Consistency check first={winner_first}, second={winner_second}. "
            f"Facts locked: {fact_sentence}."
        )
    else:
        normalized = "rational"
        headline = f"Final verdict: {winner_label}"
        rationale_display = (
            f"{headline}. Scores pro={round(_clamp_score(pro_score), 2)}, "
            f"con={round(_clamp_score(con_score), 2)}. "
            f"Used {phase_count_used}/{phase_count_expected} phase(s), missing={missing}. "
            f"Consistency check first={winner_first}, second={winner_second}. "
            f"Facts locked: {fact_sentence}."
        )
    return {
        "styleMode": normalized,
        "headline": headline,
        "rationaleDisplay": rationale_display,
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

    final_rationale = str(payload.get("finalRationale") or "").strip()
    if not final_rationale:
        missing.append("finalRationale")

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
) -> dict[str, Any]:
    expected_phase_nos = list(range(request.phase_start_no, request.phase_end_no + 1))
    expected_phase_set = set(expected_phase_nos)
    receipts = runtime.trace_store.list_dispatch_receipts(
        dispatch_type="phase",
        session_id=request.session_id,
        status="reported",
        limit=1000,
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
    final_rationale = str(display_payload.get("rationaleDisplay") or final_rationale_raw)

    return {
        "sessionId": request.session_id,
        "winner": winner,
        "proScore": round(_clamp_score(pro_score), 2),
        "conScore": round(_clamp_score(con_score), 2),
        "dimensionScores": dimension_scores,
        "finalRationale": final_rationale,
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
            "displayHeadline": display_payload.get("headline"),
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


def create_app(runtime: AppRuntime) -> FastAPI:
    app = FastAPI(title="AI Judge Service", version="0.2.0")

    @app.get("/healthz")
    async def healthz() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/internal/judge/v3/phase/dispatch")
    async def dispatch_judge_phase(
        request: PhaseDispatchRequest,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        _validate_phase_dispatch_request(request)

        replayed = _resolve_idempotency_or_raise(
            runtime=runtime,
            key=request.idempotency_key,
            job_id=request.job_id,
            conflict_detail="idempotency_conflict:phase_dispatch",
        )
        if replayed is not None:
            return replayed

        response = {
            "accepted": True,
            "dispatchType": "phase",
            "status": "queued",
            "jobId": request.job_id,
            "scopeId": request.scope_id,
            "sessionId": request.session_id,
            "phaseNo": request.phase_no,
            "messageCount": request.message_count,
            "traceId": request.trace_id,
        }
        request_payload = request.model_dump(mode="json")
        runtime.trace_store.save_dispatch_receipt(
            dispatch_type="phase",
            job_id=request.job_id,
            scope_id=request.scope_id,
            session_id=request.session_id,
            trace_id=request.trace_id,
            idempotency_key=request.idempotency_key,
            rubric_version=request.rubric_version,
            judge_policy_version=request.judge_policy_version,
            topic_domain=request.topic_domain,
            retrieval_profile=request.retrieval_profile,
            phase_no=request.phase_no,
            phase_start_no=None,
            phase_end_no=None,
            message_start_id=request.message_start_id,
            message_end_id=request.message_end_id,
            message_count=request.message_count,
            status="queued",
            request=request_payload,
            response=response,
        )

        phase_report_payload = await build_phase_report_payload_v3(
            request=request,
            settings=runtime.settings,
        )
        try:
            callback_attempts, callback_retries = await _invoke_v3_callback_with_retry(
                runtime=runtime,
                callback_fn=runtime.callback_phase_report_fn,
                job_id=request.job_id,
                payload=phase_report_payload,
            )
        except Exception as err:
            runtime.trace_store.save_dispatch_receipt(
                dispatch_type="phase",
                job_id=request.job_id,
                scope_id=request.scope_id,
                session_id=request.session_id,
                trace_id=request.trace_id,
                idempotency_key=request.idempotency_key,
                rubric_version=request.rubric_version,
                judge_policy_version=request.judge_policy_version,
                topic_domain=request.topic_domain,
                retrieval_profile=request.retrieval_profile,
                phase_no=request.phase_no,
                phase_start_no=None,
                phase_end_no=None,
                message_start_id=request.message_start_id,
                message_end_id=request.message_end_id,
                message_count=request.message_count,
                status="callback_failed",
                request=request_payload,
                response={
                    **response,
                    "status": "callback_failed",
                    "callbackStatus": "failed",
                    "callbackError": str(err),
                    "reportPayload": phase_report_payload,
                },
            )
            runtime.trace_store.clear_idempotency(request.idempotency_key)
            raise HTTPException(status_code=502, detail=f"phase_callback_failed: {err}") from err

        runtime.trace_store.save_dispatch_receipt(
            dispatch_type="phase",
            job_id=request.job_id,
            scope_id=request.scope_id,
            session_id=request.session_id,
            trace_id=request.trace_id,
            idempotency_key=request.idempotency_key,
            rubric_version=request.rubric_version,
            judge_policy_version=request.judge_policy_version,
            topic_domain=request.topic_domain,
            retrieval_profile=request.retrieval_profile,
            phase_no=request.phase_no,
            phase_start_no=None,
            phase_end_no=None,
            message_start_id=request.message_start_id,
            message_end_id=request.message_end_id,
            message_count=request.message_count,
            status="reported",
            request=request_payload,
            response={
                **response,
                "callbackStatus": "reported",
                "callbackAttempts": callback_attempts,
                "callbackRetries": callback_retries,
                "reportPayload": phase_report_payload,
            },
        )
        runtime.trace_store.set_idempotency_success(
            key=request.idempotency_key,
            job_id=request.job_id,
            response=response,
            ttl_secs=runtime.settings.idempotency_ttl_secs,
        )
        return response

    @app.post("/internal/judge/v3/final/dispatch")
    async def dispatch_judge_final(
        request: FinalDispatchRequest,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        _validate_final_dispatch_request(request)

        replayed = _resolve_idempotency_or_raise(
            runtime=runtime,
            key=request.idempotency_key,
            job_id=request.job_id,
            conflict_detail="idempotency_conflict:final_dispatch",
        )
        if replayed is not None:
            return replayed

        response = {
            "accepted": True,
            "dispatchType": "final",
            "status": "queued",
            "jobId": request.job_id,
            "scopeId": request.scope_id,
            "sessionId": request.session_id,
            "phaseStartNo": request.phase_start_no,
            "phaseEndNo": request.phase_end_no,
            "traceId": request.trace_id,
        }
        request_payload = request.model_dump(mode="json")
        runtime.trace_store.save_dispatch_receipt(
            dispatch_type="final",
            job_id=request.job_id,
            scope_id=request.scope_id,
            session_id=request.session_id,
            trace_id=request.trace_id,
            idempotency_key=request.idempotency_key,
            rubric_version=request.rubric_version,
            judge_policy_version=request.judge_policy_version,
            topic_domain=request.topic_domain,
            retrieval_profile=None,
            phase_no=None,
            phase_start_no=request.phase_start_no,
            phase_end_no=request.phase_end_no,
            message_start_id=None,
            message_end_id=None,
            message_count=None,
            status="queued",
            request=request_payload,
            response=response,
        )

        final_report_payload = _build_final_report_payload(
            runtime=runtime,
            request=request,
        )
        contract_missing_fields = _validate_final_report_payload_contract(final_report_payload)
        if contract_missing_fields:
            error_text = "final_contract_violation: missing_fields=" + ",".join(
                contract_missing_fields[:12]
            )
            alert = runtime.trace_store.upsert_audit_alert(
                job_id=request.job_id,
                scope_id=request.scope_id,
                trace_id=request.trace_id,
                alert_type="final_contract_violation",
                severity="critical",
                title="AI Judge Final Contract Violation",
                message=error_text,
                details={
                    "dispatchType": "final",
                    "sessionId": request.session_id,
                    "phaseRange": {
                        "startNo": request.phase_start_no,
                        "endNo": request.phase_end_no,
                    },
                    "missingFields": contract_missing_fields,
                    "errorCode": "phase_artifact_incomplete",
                },
            )
            runtime.trace_store.save_dispatch_receipt(
                dispatch_type="final",
                job_id=request.job_id,
                scope_id=request.scope_id,
                session_id=request.session_id,
                trace_id=request.trace_id,
                idempotency_key=request.idempotency_key,
                rubric_version=request.rubric_version,
                judge_policy_version=request.judge_policy_version,
                topic_domain=request.topic_domain,
                retrieval_profile=None,
                phase_no=None,
                phase_start_no=request.phase_start_no,
                phase_end_no=request.phase_end_no,
                message_start_id=None,
                message_end_id=None,
                message_count=None,
                status="callback_failed",
                request=request_payload,
                response={
                    **response,
                    "status": "callback_failed",
                    "callbackStatus": "blocked",
                    "callbackError": error_text,
                    "auditAlertIds": [alert.alert_id],
                    "reportPayload": final_report_payload,
                },
            )
            runtime.trace_store.clear_idempotency(request.idempotency_key)
            raise HTTPException(
                status_code=502,
                detail="final_contract_blocked: missing_critical_fields",
            )
        try:
            callback_attempts, callback_retries = await _invoke_v3_callback_with_retry(
                runtime=runtime,
                callback_fn=runtime.callback_final_report_fn,
                job_id=request.job_id,
                payload=final_report_payload,
            )
        except Exception as err:
            runtime.trace_store.save_dispatch_receipt(
                dispatch_type="final",
                job_id=request.job_id,
                scope_id=request.scope_id,
                session_id=request.session_id,
                trace_id=request.trace_id,
                idempotency_key=request.idempotency_key,
                rubric_version=request.rubric_version,
                judge_policy_version=request.judge_policy_version,
                topic_domain=request.topic_domain,
                retrieval_profile=None,
                phase_no=None,
                phase_start_no=request.phase_start_no,
                phase_end_no=request.phase_end_no,
                message_start_id=None,
                message_end_id=None,
                message_count=None,
                status="callback_failed",
                request=request_payload,
                response={
                    **response,
                    "status": "callback_failed",
                    "callbackStatus": "failed",
                    "callbackError": str(err),
                    "reportPayload": final_report_payload,
                },
            )
            runtime.trace_store.clear_idempotency(request.idempotency_key)
            raise HTTPException(status_code=502, detail=f"final_callback_failed: {err}") from err

        runtime.trace_store.save_dispatch_receipt(
            dispatch_type="final",
            job_id=request.job_id,
            scope_id=request.scope_id,
            session_id=request.session_id,
            trace_id=request.trace_id,
            idempotency_key=request.idempotency_key,
            rubric_version=request.rubric_version,
            judge_policy_version=request.judge_policy_version,
            topic_domain=request.topic_domain,
            retrieval_profile=None,
            phase_no=None,
            phase_start_no=request.phase_start_no,
            phase_end_no=request.phase_end_no,
            message_start_id=None,
            message_end_id=None,
            message_count=None,
            status="reported",
            request=request_payload,
            response={
                **response,
                "callbackStatus": "reported",
                "callbackAttempts": callback_attempts,
                "callbackRetries": callback_retries,
                "reportPayload": final_report_payload,
            },
        )
        runtime.trace_store.set_idempotency_success(
            key=request.idempotency_key,
            job_id=request.job_id,
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
        item = runtime.trace_store.get_dispatch_receipt(
            dispatch_type="phase",
            job_id=job_id,
        )
        if item is None:
            raise HTTPException(status_code=404, detail="phase_dispatch_receipt_not_found")
        return _serialize_dispatch_receipt(item)

    @app.get("/internal/judge/v3/final/jobs/{job_id}/receipt")
    async def get_final_dispatch_receipt(
        job_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        item = runtime.trace_store.get_dispatch_receipt(
            dispatch_type="final",
            job_id=job_id,
        )
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
        items = runtime.trace_store.list_audit_alerts(
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
        return {
            "ok": True,
            "jobId": job_id,
            "alertId": alert_id,
            "status": row.status,
            "item": _serialize_alert_item(row),
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
