from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ...models import FinalDispatchRequest
from ...style_mode import resolve_effective_style_mode


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


def validate_final_report_payload_contract(payload: dict[str, Any]) -> list[str]:
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


def build_final_report_payload(
    *,
    request: FinalDispatchRequest,
    phase_receipts: list[Any],
    judge_style_mode: str,
) -> dict[str, Any]:
    expected_phase_nos = list(range(request.phase_start_no, request.phase_end_no + 1))
    expected_phase_set = set(expected_phase_nos)

    phase_reports_by_no: dict[int, tuple[datetime, dict[str, Any]]] = {}
    for receipt in phase_receipts:
        phase_no, report_payload = _extract_phase_report_payload_from_receipt(receipt)
        if phase_no not in expected_phase_set or not isinstance(report_payload, dict):
            continue
        updated_at = getattr(receipt, "updated_at", None)
        if not isinstance(updated_at, datetime):
            updated_at = datetime.min.replace(tzinfo=timezone.utc)
        prev = phase_reports_by_no.get(phase_no)
        if prev is not None and prev[0] >= updated_at:
            continue
        phase_reports_by_no[phase_no] = (updated_at, report_payload)

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
        judge_style_mode,
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
        display_payload.get("sideAnalysis")
        if isinstance(display_payload.get("sideAnalysis"), dict)
        else {}
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
