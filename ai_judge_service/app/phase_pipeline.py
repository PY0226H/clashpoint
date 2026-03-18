from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from .models import (
    DispatchJob,
    DispatchMessage,
    DispatchSession,
    DispatchTopic,
    JudgeDispatchRequest,
    PhaseDispatchMessage,
    PhaseDispatchRequest,
)
from .runtime_rag import RuntimeRagResult, retrieve_runtime_contexts_with_meta
from .settings import Settings

TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]+")
REBUTTAL_MARKERS = (
    "但是",
    "然而",
    "不过",
    "反驳",
    "质疑",
    "并非",
    "but",
    "however",
    "rebut",
)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


def _hash_payload(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _select_side_messages(
    request: PhaseDispatchRequest,
    side: str,
) -> list[PhaseDispatchMessage]:
    side_messages = [msg for msg in request.messages if msg.side == side]
    if side_messages:
        return side_messages
    return list(request.messages[:1])


def _build_grounded_summary(
    request: PhaseDispatchRequest,
    *,
    side: str,
) -> dict[str, Any]:
    side_messages = _select_side_messages(request, side)
    lines = [f"[{msg.message_id}] {msg.content}" for msg in side_messages]
    return {
        "text": "\n".join(lines)[:8000],
        "messageIds": [msg.message_id for msg in side_messages],
    }


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for token in TOKEN_RE.findall((text or "").lower()):
        token = token.strip()
        if len(token) < 2:
            continue
        tokens.append(token)
    return tokens


def _top_keywords(messages: list[PhaseDispatchMessage], *, limit: int = 6) -> list[str]:
    counts: dict[str, int] = {}
    for msg in messages:
        for token in _tokenize(msg.content):
            counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts.items(), key=lambda row: (-row[1], row[0]))
    return [token for token, _ in ranked[: max(1, limit)]]


def _build_side_queries(
    request: PhaseDispatchRequest,
    *,
    side: str,
    side_messages: list[PhaseDispatchMessage],
) -> list[str]:
    if not side_messages:
        return [f"{request.topic_domain} {side} 论点"]

    latest_text = " ".join(msg.content for msg in side_messages[-3:])
    rebuttal_messages = [
        msg
        for msg in side_messages
        if any(marker in msg.content.lower() for marker in REBUTTAL_MARKERS)
    ]
    rebuttal_text = " ".join(msg.content for msg in rebuttal_messages[-2:])
    keywords = _top_keywords(side_messages, limit=6)
    keyword_text = " ".join(keywords)

    candidates = [
        f"{request.topic_domain} {side} 核心观点 {keyword_text}".strip(),
        f"{request.topic_domain} {side} 最新主张 {latest_text}".strip(),
        f"{request.topic_domain} {side} 反驳证据 {rebuttal_text}".strip(),
    ]
    deduped: list[str] = []
    seen: set[str] = set()
    for raw in candidates:
        normalized = " ".join(raw.split())
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(normalized[:240])
    return deduped[:3] if deduped else [f"{request.topic_domain} {side} 论点"]


def _build_side_rag_request(
    request: PhaseDispatchRequest,
    *,
    side: str,
    side_messages: list[PhaseDispatchMessage],
) -> JudgeDispatchRequest:
    now = datetime.now(timezone.utc)
    dispatch_messages = [
        DispatchMessage(
            message_id=msg.message_id,
            speaker_tag=msg.speaker_tag,
            user_id=None,
            side=msg.side,
            content=msg.content,
            created_at=msg.created_at,
        )
        for msg in side_messages
    ]
    return JudgeDispatchRequest(
        job=DispatchJob(
            job_id=request.job_id,
            scope_id=request.scope_id,
            session_id=request.session_id,
            requested_by=0,
            style_mode="rational",
            rejudge_triggered=False,
            requested_at=now,
        ),
        session=DispatchSession(
            status="judging",
            scheduled_start_at=now,
            actual_start_at=now,
            end_at=now,
        ),
        topic=DispatchTopic(
            title=f"{request.topic_domain}:{side}",
            description=f"phase_{request.phase_no}",
            category=request.topic_domain,
            stance_pro="pro",
            stance_con="con",
            context_seed=None,
        ),
        messages=dispatch_messages,
        message_window_size=request.message_count,
        rubric_version=request.rubric_version,
        trace_id=f"{request.trace_id}:{side}",
        idempotency_key=f"{request.idempotency_key}:{side}",
        judge_policy_version=request.judge_policy_version,
        topic_domain=request.topic_domain,
        retrieval_profile=request.retrieval_profile,
    )


def _build_retrieval_items(
    rag_result: RuntimeRagResult,
    *,
    max_chars: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rag_result.retrieved_contexts:
        out.append(
            {
                "chunkId": row.chunk_id,
                "title": row.title,
                "sourceUrl": row.source_url,
                "score": round(float(row.score), 4),
                "snippet": str(row.content or "")[: max(120, max_chars)],
                "conflict": False,
            }
        )
    return out


def _extract_retrieval_error_codes(
    *,
    rag_result: RuntimeRagResult,
    side: str,
) -> list[str]:
    diagnostics = (
        rag_result.retrieval_diagnostics
        if isinstance(rag_result.retrieval_diagnostics, dict)
        else {}
    )
    out: list[str] = []
    error_code = diagnostics.get("errorCode")
    if error_code:
        out.append(str(error_code).strip().lower())
    if rag_result.backend_fallback_reason:
        out.append("rag_backend_fallback")
    if not rag_result.retrieved_contexts:
        out.append(f"rag_no_hit_{side}")

    deduped: list[str] = []
    seen: set[str] = set()
    for code in out:
        if not code or code in seen:
            continue
        seen.add(code)
        deduped.append(code)
    return deduped


def _count_rebuttals(messages: list[PhaseDispatchMessage]) -> int:
    total = 0
    for msg in messages:
        lowered = msg.content.lower()
        if any(marker in lowered for marker in REBUTTAL_MARKERS):
            total += 1
    return total


def _compute_phase_scores(
    request: PhaseDispatchRequest,
    *,
    pro_messages: list[PhaseDispatchMessage],
    con_messages: list[PhaseDispatchMessage],
    pro_retrieval_items: list[dict[str, Any]],
    con_retrieval_items: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    total_messages = max(1, request.message_count)
    pro_count = len([msg for msg in request.messages if msg.side == "pro"])
    con_count = len([msg for msg in request.messages if msg.side == "con"])
    participation_delta = (pro_count - con_count) / float(total_messages)

    pro_rebuttal_rate = _count_rebuttals(pro_messages) / float(max(1, len(pro_messages)))
    con_rebuttal_rate = _count_rebuttals(con_messages) / float(max(1, len(con_messages)))
    rebuttal_delta = pro_rebuttal_rate - con_rebuttal_rate

    pro_hits = len(pro_retrieval_items)
    con_hits = len(con_retrieval_items)
    rag_delta = (pro_hits - con_hits) / float(max(1, max(pro_hits, con_hits, 1)))

    agent1_pro = round(_clamp(50.0 + participation_delta * 10.0 + rebuttal_delta * 8.0, 0.0, 100.0), 2)
    agent1_con = round(_clamp(50.0 - participation_delta * 10.0 - rebuttal_delta * 8.0, 0.0, 100.0), 2)

    agent2_pro = round(
        _clamp(
            50.0 + participation_delta * 6.0 + rebuttal_delta * 10.0 + rag_delta * 12.0,
            0.0,
            100.0,
        ),
        2,
    )
    agent2_con = round(
        _clamp(
            50.0 - participation_delta * 6.0 - rebuttal_delta * 10.0 - rag_delta * 12.0,
            0.0,
            100.0,
        ),
        2,
    )

    w1 = 0.35
    w2 = 0.65
    agent3_pro = round(_clamp(agent1_pro * w1 + agent2_pro * w2, 0.0, 100.0), 2)
    agent3_con = round(_clamp(agent1_con * w1 + agent2_con * w2, 0.0, 100.0), 2)

    agent1 = {
        "pro": agent1_pro,
        "con": agent1_con,
        "dimensions": {
            "proCoverage": round(pro_count / float(total_messages), 4),
            "conCoverage": round(con_count / float(total_messages), 4),
            "proRebuttalRate": round(pro_rebuttal_rate, 4),
            "conRebuttalRate": round(con_rebuttal_rate, 4),
        },
        "rationale": "agent1 uses participation balance and rebuttal density as baseline signals.",
    }
    agent2 = {
        "pro": agent2_pro,
        "con": agent2_con,
        "hitItems": [item.get("chunkId") for item in pro_retrieval_items[:6] if item.get("chunkId")],
        "missItems": [item.get("chunkId") for item in con_retrieval_items[:6] if item.get("chunkId")],
        "rationale": "agent2 emphasizes retrieval hit ratio with rebuttal strength.",
    }
    agent3 = {
        "pro": agent3_pro,
        "con": agent3_con,
        "w1": w1,
        "w2": w2,
    }
    return agent1, agent2, agent3


def _resolve_degradation_level(
    *,
    pro_items: list[dict[str, Any]],
    con_items: list[dict[str, Any]],
    error_codes: list[str],
) -> int:
    level = 0
    if not pro_items or not con_items:
        level = max(level, 1)
    if not pro_items and not con_items:
        level = max(level, 2)
    if any(code.startswith("rag_") for code in error_codes):
        level = max(level, 2)
    return level


def build_phase_report_payload(
    *,
    request: PhaseDispatchRequest,
    settings: Settings,
) -> dict[str, Any]:
    started = perf_counter()

    summary_started = perf_counter()
    pro_messages = _select_side_messages(request, "pro")
    con_messages = _select_side_messages(request, "con")
    pro_summary = _build_grounded_summary(request, side="pro")
    con_summary = _build_grounded_summary(request, side="con")
    summary_latency_ms = (perf_counter() - summary_started) * 1000.0

    retrieval_started = perf_counter()
    pro_queries = _build_side_queries(request, side="pro", side_messages=pro_messages)
    con_queries = _build_side_queries(request, side="con", side_messages=con_messages)

    pro_rag_request = _build_side_rag_request(request, side="pro", side_messages=pro_messages)
    con_rag_request = _build_side_rag_request(request, side="con", side_messages=con_messages)

    pro_rag_result = retrieve_runtime_contexts_with_meta(
        request=pro_rag_request,
        settings=settings,
    )
    con_rag_result = retrieve_runtime_contexts_with_meta(
        request=con_rag_request,
        settings=settings,
    )
    retrieval_latency_ms = (perf_counter() - retrieval_started) * 1000.0

    pro_items = _build_retrieval_items(
        pro_rag_result,
        max_chars=settings.rag_max_chars_per_snippet,
    )
    con_items = _build_retrieval_items(
        con_rag_result,
        max_chars=settings.rag_max_chars_per_snippet,
    )
    pro_bundle = {"queries": pro_queries, "items": pro_items}
    con_bundle = {"queries": con_queries, "items": con_items}

    agent1_score, agent2_score, agent3_score = _compute_phase_scores(
        request,
        pro_messages=pro_messages,
        con_messages=con_messages,
        pro_retrieval_items=pro_items,
        con_retrieval_items=con_items,
    )

    error_codes = _extract_retrieval_error_codes(rag_result=pro_rag_result, side="pro")
    error_codes.extend(_extract_retrieval_error_codes(rag_result=con_rag_result, side="con"))
    deduped_error_codes: list[str] = []
    seen_codes: set[str] = set()
    for code in error_codes:
        if code in seen_codes:
            continue
        seen_codes.add(code)
        deduped_error_codes.append(code)

    degradation_level = _resolve_degradation_level(
        pro_items=pro_items,
        con_items=con_items,
        error_codes=deduped_error_codes,
    )
    total_latency_ms = (perf_counter() - started) * 1000.0

    prompt_hashes = {
        "a2": _hash_payload(pro_summary),
        "a3": _hash_payload(con_summary),
        "a4": _hash_payload({"proQueries": pro_queries, "conQueries": con_queries}),
        "a5": _hash_payload(agent1_score),
        "a6": _hash_payload(agent2_score),
        "a7": _hash_payload(agent3_score),
    }

    return {
        "sessionId": request.session_id,
        "phaseNo": request.phase_no,
        "messageStartId": request.message_start_id,
        "messageEndId": request.message_end_id,
        "messageCount": request.message_count,
        "proSummaryGrounded": pro_summary,
        "conSummaryGrounded": con_summary,
        "proRetrievalBundle": pro_bundle,
        "conRetrievalBundle": con_bundle,
        "agent1Score": agent1_score,
        "agent2Score": agent2_score,
        "agent3WeightedScore": agent3_score,
        "promptHashes": prompt_hashes,
        "tokenUsage": {
            "prompt": 0,
            "completion": 0,
            "total": 0,
        },
        "latencyMs": {
            "summary": round(summary_latency_ms, 2),
            "retrieval": round(retrieval_latency_ms, 2),
            "total": round(total_latency_ms, 2),
        },
        "errorCodes": deduped_error_codes,
        "degradationLevel": degradation_level,
        "judgeTrace": {
            "traceId": request.trace_id,
            "pipelineVersion": "v3-phase-m4-baseline",
            "idempotencyKey": request.idempotency_key,
            "retrievalDiagnostics": {
                "pro": pro_rag_result.retrieval_diagnostics,
                "con": con_rag_result.retrieval_diagnostics,
            },
            "retrievalBackend": {
                "requested": settings.rag_backend,
                "effectivePro": pro_rag_result.effective_backend,
                "effectiveCon": con_rag_result.effective_backend,
            },
        },
    }
