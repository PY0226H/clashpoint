from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from .models import (
    PhaseDispatchMessage,
    PhaseDispatchRequest,
)
from .openai_judge_client import OPENAI_META_KEY, call_openai_json
from .rag_retriever import RetrievedContext
from .reranker_engine import RerankCandidate, RerankRequest, rerank_with_fallback
from .runtime_errors import classify_openai_failure
from .runtime_policy import should_use_openai
from .runtime_rag import RuntimeRagResult, retrieve_runtime_contexts_with_meta
from .runtime_types import RagMessageContext, RagTopicContext, RuntimeRagRequest
from .settings import Settings
from .token_budget import TokenSegment, count_tokens, pack_segments_with_budget

TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]+")
SUMMARY_PROMPT_VERSION = "v3.a2a3.summary.v1"
AGENT2_PROMPT_VERSION = "v3.a6a7.bidirectional.v2"
AGENT2_DIMENSION_WEIGHTS = {
    "coverage": 0.35,
    "depth": 0.30,
    "evidenceFit": 0.25,
    "keyPointHitRate": 0.10,
}
DEFAULT_SUMMARY_COVERAGE_MIN_RATIO = 1.0
MAX_SUMMARY_TEXT_CHARS = 8000
MAX_SUMMARY_MESSAGE_CHARS = 640
TOKEN_CLIP_ERROR_SUMMARY = "summary_prompt_token_clipped"
TOKEN_CLIP_ERROR_AGENT2 = "agent2_prompt_token_clipped"
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
LOGIC_MARKERS = (
    "因为",
    "所以",
    "因此",
    "由此",
    "如果",
    "结论",
    "推导",
    "if",
    "therefore",
    "hence",
)
EVIDENCE_MARKERS = (
    "数据",
    "版本",
    "来源",
    "证据",
    "统计",
    "官网",
    "更新",
    "数值",
    "patch",
    "meta",
    "evidence",
    "source",
)
CONFLICT_POSITIVE_MARKERS = (
    "稳定",
    "优势",
    "提升",
    "可行",
    "收益",
    "强势",
    "stable",
    "advantage",
    "improve",
    "strong",
)
CONFLICT_NEGATIVE_MARKERS = (
    "崩盘",
    "劣势",
    "风险",
    "过晚",
    "丢失",
    "失败",
    "弱势",
    "collapse",
    "risk",
    "weak",
    "late",
)


@dataclass(frozen=True)
class _SummaryConfig:
    api_key: str
    model: str
    base_url: str
    timeout_secs: float
    temperature: float
    max_retries: int


@dataclass(frozen=True)
class SideSummaryResult:
    summary: dict[str, Any]
    source: str
    coverage_ratio: float
    fallback_reason: str | None
    error_codes: list[str]
    usage_records: list[dict[str, Any]]
    token_clip_summaries: list[dict[str, Any]]


@dataclass(frozen=True)
class SideRetrievalResult:
    bundle: dict[str, Any]
    diagnostics: dict[str, Any]
    requested_backend: str
    effective_backend: str
    backend_fallback_reason: str | None
    error_codes: list[str]


@dataclass(frozen=True)
class Agent2PathResult:
    target_side: str
    score: float
    raw_score: float
    calibrated_score: float
    dimension_scores: dict[str, float]
    calibration_notes: list[str]
    hit_points: list[str]
    miss_points: list[str]
    rationale: str
    ideal_rebuttal: str
    key_points: list[str]
    source: str
    fallback_reason: str | None
    error_codes: list[str]
    usage_records: list[dict[str, Any]]
    token_clip_summaries: list[dict[str, Any]]


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
        "text": "\n".join(lines)[:MAX_SUMMARY_TEXT_CHARS],
        "messageIds": [msg.message_id for msg in side_messages],
    }


def _summary_coverage_threshold(settings: Settings) -> float:
    raw_value = getattr(
        settings, "phase_summary_coverage_min_ratio", DEFAULT_SUMMARY_COVERAGE_MIN_RATIO
    )
    try:
        threshold = float(raw_value)
    except (TypeError, ValueError):
        threshold = DEFAULT_SUMMARY_COVERAGE_MIN_RATIO
    return _clamp(threshold, 0.0, 1.0)


def _count_tokens_for_model(settings: Settings, *, model: str, text: str) -> int:
    return count_tokens(
        model,
        text,
        fallback_encoding=settings.tokenizer_fallback_encoding,
    )


def _available_prompt_budget(
    settings: Settings,
    *,
    model: str,
    system_prompt: str,
    total_budget: int,
    minimum_user_budget: int = 128,
) -> int:
    budget = max(0, int(total_budget))
    if budget == 0:
        return 0
    system_tokens = _count_tokens_for_model(settings, model=model, text=system_prompt)
    available = max(0, budget - system_tokens)
    if available == 0:
        return 0
    if available < minimum_user_budget:
        return available
    return available


def _pack_user_prompt_segments(
    settings: Settings,
    *,
    model: str,
    budget_tokens: int,
    segments: list[TokenSegment],
) -> tuple[str, dict[str, Any]]:
    packed = pack_segments_with_budget(
        model,
        segments,
        budget_tokens,
        strategy="priority",
        fallback_encoding=settings.tokenizer_fallback_encoding,
    )
    prompt = "\n".join(
        segment.text for segment in packed.segments if segment.included and segment.text
    ).strip()
    return prompt, packed.clip_summary()


def _extract_llm_usage_record(
    *,
    settings: Settings,
    cfg: _SummaryConfig,
    call_id: str,
    system_prompt: str,
    user_prompt: str,
    response_payload: dict[str, Any],
) -> dict[str, Any]:
    usage_payload: dict[str, Any] | None = None
    meta = response_payload.get(OPENAI_META_KEY)
    if isinstance(meta, dict):
        usage_payload = meta.get("usage") if isinstance(meta.get("usage"), dict) else None

    if usage_payload is None:
        prompt_tokens = _count_tokens_for_model(
            settings,
            model=cfg.model,
            text=f"{system_prompt}\n{user_prompt}",
        )
        completion_tokens = _count_tokens_for_model(
            settings,
            model=cfg.model,
            text=json.dumps(response_payload, ensure_ascii=False, sort_keys=True),
        )
        total_tokens = prompt_tokens + completion_tokens
        return {
            "callId": call_id,
            "model": cfg.model,
            "prompt": prompt_tokens,
            "completion": completion_tokens,
            "total": total_tokens,
            "usageEstimated": True,
        }

    prompt_tokens = max(0, int(usage_payload.get("prompt_tokens") or 0))
    completion_tokens = max(0, int(usage_payload.get("completion_tokens") or 0))
    total_tokens = max(
        0,
        int(usage_payload.get("total_tokens") or (prompt_tokens + completion_tokens)),
    )
    return {
        "callId": call_id,
        "model": cfg.model,
        "prompt": prompt_tokens,
        "completion": completion_tokens,
        "total": total_tokens,
        "usageEstimated": False,
    }


def _clean_openai_payload(raw: dict[str, Any]) -> dict[str, Any]:
    if OPENAI_META_KEY not in raw:
        return raw
    return {key: value for key, value in raw.items() if key != OPENAI_META_KEY}


def _build_summary_system_prompt(*, side: str, topic_domain: str) -> str:
    return (
        "你是辩论阶段总结Agent。"
        "只允许基于输入消息做保真总结，禁止补充窗口外信息。"
        "禁止改写消息立场，禁止编造观点。"
        "输出必须是JSON对象，字段为 summary_text 和 message_ids。"
        f"当前阵营: {side}，topic_domain: {topic_domain}。"
    )


def _build_summary_user_prompt(
    *,
    request: PhaseDispatchRequest,
    settings: Settings,
    system_prompt: str,
    side: str,
    side_messages: list[PhaseDispatchMessage],
) -> tuple[str, dict[str, Any]]:
    segments: list[TokenSegment] = [
        TokenSegment(
            segment_id="summary_instruction",
            priority=0,
            required=True,
            text=(
                "请输出保真总结并覆盖输入消息中的所有观点、反驳与关键论据。\n"
                "要求:\n"
                "1) 仅使用输入消息，不得引入外部信息。\n"
                "2) message_ids 只能填写输入中出现过的消息ID。\n"
                "3) summary_text 使用中文。\n"
                "4) 仅输出JSON，不要输出其他文本。"
            ),
        ),
        TokenSegment(
            segment_id="summary_meta",
            priority=1,
            required=True,
            text=f"phase_no={request.phase_no}, side={side}, message_count={len(side_messages)}",
        ),
        TokenSegment(
            segment_id="summary_messages_header",
            priority=2,
            required=True,
            text="messages:",
        ),
    ]

    for idx, msg in enumerate(side_messages):
        content = str(msg.content or "").strip().replace("\n", " ")
        segments.append(
            TokenSegment(
                segment_id=f"message_{msg.message_id}",
                priority=10 + idx,
                required=False,
                text=f"[{msg.message_id}] {content}",
            )
        )

    budget_tokens = _available_prompt_budget(
        settings,
        model=settings.openai_model,
        system_prompt=system_prompt,
        total_budget=settings.phase_prompt_max_tokens,
        minimum_user_budget=256,
    )
    prompt, clip_summary = _pack_user_prompt_segments(
        settings,
        model=settings.openai_model,
        budget_tokens=budget_tokens,
        segments=segments,
    )
    return prompt, clip_summary


def _normalize_summary_message_ids(
    *,
    raw_ids: Any,
    valid_ids: list[int],
) -> tuple[list[int], bool]:
    valid_set = set(valid_ids)
    normalized: list[int] = []
    seen: set[int] = set()
    has_invalid = False
    values = raw_ids if isinstance(raw_ids, list) else []
    for value in values:
        try:
            message_id = int(value)
        except (TypeError, ValueError):
            has_invalid = True
            continue
        if message_id not in valid_set:
            has_invalid = True
            continue
        if message_id in seen:
            continue
        seen.add(message_id)
        normalized.append(message_id)
    return normalized, has_invalid


def _compute_summary_coverage(*, expected_ids: list[int], covered_ids: list[int]) -> float:
    if not expected_ids:
        return 1.0
    expected_set = set(expected_ids)
    covered_set = set(covered_ids)
    return len(expected_set & covered_set) / float(len(expected_set))


async def _build_side_summary_with_guard(
    request: PhaseDispatchRequest,
    *,
    side: str,
    side_messages: list[PhaseDispatchMessage],
    settings: Settings,
) -> SideSummaryResult:
    fallback_summary = _build_grounded_summary(request, side=side)
    expected_ids = fallback_summary["messageIds"]
    threshold = _summary_coverage_threshold(settings)
    system_prompt = _build_summary_system_prompt(
        side=side,
        topic_domain=request.topic_domain,
    )
    user_prompt, clip_summary = _build_summary_user_prompt(
        request=request,
        settings=settings,
        system_prompt=system_prompt,
        side=side,
        side_messages=side_messages,
    )
    token_clip_summaries = [
        {
            "callId": f"a2a3_summary_{side}",
            "stage": "summary",
            "side": side,
            **clip_summary,
        }
    ]
    clip_error_codes = [TOKEN_CLIP_ERROR_SUMMARY] if bool(clip_summary.get("clipped")) else []

    if not should_use_openai(settings.provider, settings.openai_api_key):
        return SideSummaryResult(
            summary=fallback_summary,
            source="extractive_fallback",
            coverage_ratio=1.0,
            fallback_reason="provider_disabled_or_missing_key",
            error_codes=clip_error_codes,
            usage_records=[],
            token_clip_summaries=token_clip_summaries,
        )

    cfg = _SummaryConfig(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        base_url=settings.openai_base_url,
        timeout_secs=settings.openai_timeout_secs,
        temperature=min(0.2, max(0.0, settings.openai_temperature)),
        max_retries=settings.openai_max_retries,
    )
    try:
        raw = await call_openai_json(
            cfg=cfg,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        usage_record = _extract_llm_usage_record(
            settings=settings,
            cfg=cfg,
            call_id=f"a2a3_summary_{side}",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_payload=raw,
        )
        raw = _clean_openai_payload(raw)
    except Exception as err:
        return SideSummaryResult(
            summary=fallback_summary,
            source="extractive_fallback",
            coverage_ratio=0.0,
            fallback_reason="openai_call_failed",
            error_codes=[
                f"summary_model_error_{side}",
                classify_openai_failure(str(err)),
                *clip_error_codes,
            ],
            usage_records=[],
            token_clip_summaries=token_clip_summaries,
        )

    summary_text = str(
        raw.get("summary_text")
        or raw.get("summaryText")
        or raw.get("summary")
        or raw.get("text")
        or ""
    ).strip()
    message_ids, has_invalid_ids = _normalize_summary_message_ids(
        raw_ids=raw.get("message_ids") or raw.get("messageIds"),
        valid_ids=expected_ids,
    )
    coverage_ratio = _compute_summary_coverage(expected_ids=expected_ids, covered_ids=message_ids)

    if not summary_text:
        return SideSummaryResult(
            summary=fallback_summary,
            source="extractive_fallback",
            coverage_ratio=coverage_ratio,
            fallback_reason="summary_text_empty",
            error_codes=[f"summary_schema_invalid_{side}", *clip_error_codes],
            usage_records=[usage_record],
            token_clip_summaries=token_clip_summaries,
        )
    if has_invalid_ids:
        return SideSummaryResult(
            summary=fallback_summary,
            source="extractive_fallback",
            coverage_ratio=coverage_ratio,
            fallback_reason="summary_message_ids_invalid",
            error_codes=[f"summary_schema_invalid_{side}", *clip_error_codes],
            usage_records=[usage_record],
            token_clip_summaries=token_clip_summaries,
        )
    if coverage_ratio < threshold:
        return SideSummaryResult(
            summary=fallback_summary,
            source="extractive_fallback",
            coverage_ratio=coverage_ratio,
            fallback_reason="summary_coverage_below_threshold",
            error_codes=[f"summary_coverage_low_{side}", *clip_error_codes],
            usage_records=[usage_record],
            token_clip_summaries=token_clip_summaries,
        )

    return SideSummaryResult(
        summary={
            "text": summary_text[:MAX_SUMMARY_TEXT_CHARS],
            "messageIds": message_ids,
        },
        source="llm",
        coverage_ratio=coverage_ratio,
        fallback_reason=None,
        error_codes=clip_error_codes,
        usage_records=[usage_record],
        token_clip_summaries=token_clip_summaries,
    )


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
    query_text: str | None = None,
) -> RuntimeRagRequest:
    query = str(query_text or "").strip()
    topic_description = (
        f"phase_{request.phase_no}" if not query else f"phase_{request.phase_no}:{query[:200]}"
    )
    rag_messages = [
        RagMessageContext(
            message_id=msg.message_id,
            speaker_tag=msg.speaker_tag,
            user_id=None,
            side=msg.side,
            content=msg.content,
            created_at=msg.created_at,
        )
        for msg in side_messages
    ]
    return RuntimeRagRequest(
        topic=RagTopicContext(
            title=f"{request.topic_domain}:{side}",
            description=topic_description,
            category=request.topic_domain,
            stance_pro="pro",
            stance_con="con",
            context_seed=query or None,
        ),
        messages=rag_messages,
        retrieval_profile=request.retrieval_profile,
    )


def _normalize_conflict_key(text: str) -> str:
    return " ".join(_tokenize(text))[:160]


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in markers)


def _rrf_fuse_context_lists(
    ranked_lists: list[list[RetrievedContext]],
    *,
    rrf_k: int,
) -> list[RetrievedContext]:
    if not ranked_lists:
        return []
    k = max(1, int(rrf_k))
    score_map: dict[str, float] = {}
    context_map: dict[str, RetrievedContext] = {}
    for rows in ranked_lists:
        for rank, row in enumerate(rows):
            score_map[row.chunk_id] = score_map.get(row.chunk_id, 0.0) + (1.0 / (k + rank + 1))
            previous = context_map.get(row.chunk_id)
            if previous is None or row.score > previous.score:
                context_map[row.chunk_id] = row

    fused: list[RetrievedContext] = []
    for chunk_id, score in score_map.items():
        context = context_map.get(chunk_id)
        if context is None:
            continue
        fused.append(
            RetrievedContext(
                chunk_id=context.chunk_id,
                title=context.title,
                source_url=context.source_url,
                content=context.content,
                score=score,
            )
        )
    fused.sort(key=lambda row: (-row.score, row.chunk_id))
    return fused


def _rerank_contexts_for_queries(
    contexts: list[RetrievedContext],
    *,
    queries: list[str],
    limit: int,
    settings: Settings,
    rerank_enabled_effective: bool,
) -> tuple[list[RetrievedContext], dict[str, Any], str | None]:
    clipped_limit = max(0, int(limit))
    if not contexts or clipped_limit == 0:
        return (
            [],
            {
                "rerankEngineConfigured": settings.rag_rerank_engine,
                "rerankEngineEffective": "disabled",
                "rerankModel": settings.rag_rerank_model,
                "rerankLatencyMs": 0.0,
                "rerankFallbackReason": None,
                "candidateBeforeRerank": len(contexts),
                "candidateAfterRerank": 0,
            },
            None,
        )

    query_text = " ".join(queries).strip()
    if not query_text:
        return (
            contexts[:clipped_limit],
            {
                "rerankEngineConfigured": settings.rag_rerank_engine,
                "rerankEngineEffective": "disabled",
                "rerankModel": settings.rag_rerank_model,
                "rerankLatencyMs": 0.0,
                "rerankFallbackReason": None,
                "candidateBeforeRerank": len(contexts),
                "candidateAfterRerank": min(clipped_limit, len(contexts)),
            },
            None,
        )

    if not rerank_enabled_effective:
        return (
            contexts[:clipped_limit],
            {
                "rerankEngineConfigured": settings.rag_rerank_engine,
                "rerankEngineEffective": "disabled",
                "rerankModel": settings.rag_rerank_model,
                "rerankLatencyMs": 0.0,
                "rerankFallbackReason": None,
                "candidateBeforeRerank": len(contexts),
                "candidateAfterRerank": min(clipped_limit, len(contexts)),
            },
            None,
        )

    candidates: list[RerankCandidate] = []
    for row in contexts:
        candidates.append(
            RerankCandidate(
                chunk_id=row.chunk_id,
                title=row.title,
                content=row.content,
                score=float(row.score),
                source_url=row.source_url,
            )
        )
    result = rerank_with_fallback(
        RerankRequest(
            query_text=query_text,
            candidates=candidates,
            top_n=clipped_limit,
            configured_engine=settings.rag_rerank_engine,
            model_name=settings.rag_rerank_model,
            batch_size=settings.rag_rerank_batch_size,
            candidate_cap=settings.rag_rerank_candidate_cap,
            timeout_ms=settings.rag_rerank_timeout_ms,
            device=settings.rag_rerank_device,
        )
    )
    reranked: list[RetrievedContext] = []
    for row in result.candidates:
        reranked.append(
            RetrievedContext(
                chunk_id=row.chunk_id,
                title=row.title,
                source_url=row.source_url,
                content=row.content,
                score=float(row.score),
            )
        )
    diagnostics = {
        "rerankEngineConfigured": result.configured_engine,
        "rerankEngineEffective": result.effective_engine,
        "rerankModel": result.model_name,
        "rerankLatencyMs": round(float(result.latency_ms), 2),
        "rerankFallbackReason": result.fallback_reason,
        "candidateBeforeRerank": int(result.candidate_before),
        "candidateAfterRerank": int(result.candidate_after),
    }
    return reranked, diagnostics, result.error_code


def _build_retrieval_items(
    contexts: list[RetrievedContext],
    *,
    max_chars: int,
) -> list[dict[str, Any]]:
    if not contexts:
        return []

    # 后处理去重：优先 chunk_id，兜底 source+title
    deduped: list[RetrievedContext] = []
    seen_chunk_ids: set[str] = set()
    seen_source_title: set[tuple[str, str]] = set()
    for row in contexts:
        chunk_id = str(row.chunk_id or "").strip()
        title = str(row.title or "").strip()
        source = str(row.source_url or "").strip().lower()
        fallback_key = (source, title.lower())
        if chunk_id and chunk_id in seen_chunk_ids:
            continue
        if fallback_key in seen_source_title:
            continue
        if chunk_id:
            seen_chunk_ids.add(chunk_id)
        seen_source_title.add(fallback_key)
        deduped.append(row)

    title_group_sources: dict[str, set[str]] = {}
    title_group_items: dict[str, list[RetrievedContext]] = {}
    for row in deduped:
        key = _normalize_conflict_key(row.title or row.content)
        if not key:
            continue
        title_group_sources.setdefault(key, set()).add((row.source_url or "").strip().lower())
        title_group_items.setdefault(key, []).append(row)

    conflicting_chunk_ids: set[str] = set()
    for key, rows in title_group_items.items():
        sources = title_group_sources.get(key, set())
        # 冲突标注策略：
        # 1) 同主题 key 在多个来源出现（来源冲突）
        # 2) 同主题中出现显著正负语义分歧
        has_multi_source = len({s for s in sources if s}) >= 2
        has_positive = any(
            _contains_any(f"{row.title} {row.content}", CONFLICT_POSITIVE_MARKERS) for row in rows
        )
        has_negative = any(
            _contains_any(f"{row.title} {row.content}", CONFLICT_NEGATIVE_MARKERS) for row in rows
        )
        if has_multi_source or (has_positive and has_negative):
            for row in rows:
                conflicting_chunk_ids.add(row.chunk_id)

    out: list[dict[str, Any]] = []
    for row in deduped:
        out.append(
            {
                "chunkId": row.chunk_id,
                "title": row.title,
                "sourceUrl": row.source_url,
                "score": round(float(row.score), 4),
                "snippet": str(row.content or "")[: max(120, max_chars)],
                "conflict": row.chunk_id in conflicting_chunk_ids,
            }
        )
    return out


def _retrieve_side_with_query_plan(
    request: PhaseDispatchRequest,
    *,
    side: str,
    side_messages: list[PhaseDispatchMessage],
    queries: list[str],
    settings: Settings,
) -> SideRetrievalResult:
    query_results: list[RuntimeRagResult] = []
    per_query_diagnostics: list[dict[str, Any]] = []
    ranked_lists: list[list[RetrievedContext]] = []
    requested_backend = settings.rag_backend
    effective_backend = settings.rag_backend
    backend_fallback_reason: str | None = None

    for query in queries:
        rag_request = _build_side_rag_request(
            request,
            side=side,
            side_messages=side_messages,
            query_text=query,
        )
        rag_result = retrieve_runtime_contexts_with_meta(
            request=rag_request,
            settings=settings,
        )
        query_results.append(rag_result)
        requested_backend = rag_result.requested_backend
        effective_backend = rag_result.effective_backend
        if rag_result.backend_fallback_reason and not backend_fallback_reason:
            backend_fallback_reason = rag_result.backend_fallback_reason
        ranked_lists.append(list(rag_result.retrieved_contexts))
        per_query_diagnostics.append(
            {
                "query": query,
                "requestedBackend": rag_result.requested_backend,
                "effectiveBackend": rag_result.effective_backend,
                "backendFallbackReason": rag_result.backend_fallback_reason,
                "diagnostics": rag_result.retrieval_diagnostics,
                "candidateCount": len(rag_result.retrieved_contexts),
            }
        )

    rrf_k = 60
    rerank_enabled_effective = settings.rag_rerank_enabled
    if per_query_diagnostics:
        first_diag = per_query_diagnostics[0].get("diagnostics")
        if isinstance(first_diag, dict):
            tuning = first_diag.get("profileTuning")
            if isinstance(tuning, dict):
                try:
                    rrf_k = max(1, int(tuning.get("rrfK", 60)))
                except (TypeError, ValueError):
                    rrf_k = 60
            rerank_enabled_effective = bool(
                first_diag.get("rerankEnabledEffective", settings.rag_rerank_enabled)
            )

    fused_contexts = _rrf_fuse_context_lists(ranked_lists, rrf_k=rrf_k)
    final_contexts, rerank_diagnostics, rerank_error_code = _rerank_contexts_for_queries(
        fused_contexts,
        queries=queries,
        limit=settings.rag_max_snippets,
        settings=settings,
        rerank_enabled_effective=rerank_enabled_effective,
    )
    items = _build_retrieval_items(
        final_contexts,
        max_chars=settings.rag_max_chars_per_snippet,
    )

    error_codes: list[str] = []
    for result in query_results:
        diagnostics = (
            result.retrieval_diagnostics if isinstance(result.retrieval_diagnostics, dict) else {}
        )
        error_code = diagnostics.get("errorCode")
        if error_code:
            error_codes.append(str(error_code).strip().lower())
        if result.backend_fallback_reason:
            error_codes.append("rag_backend_fallback")
    if rerank_error_code:
        error_codes.append(rerank_error_code)
    if not items:
        error_codes.append(f"rag_no_hit_{side}")

    deduped_codes: list[str] = []
    seen_codes: set[str] = set()
    for code in error_codes:
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)
        deduped_codes.append(code)

    diagnostics = {
        "queryCount": len(queries),
        "perQuery": per_query_diagnostics,
        "fusion": {
            "method": "rrf+rerank",
            "rrfK": rrf_k,
            "rankListCount": len(ranked_lists),
            "fusedCount": len(fused_contexts),
            "finalCount": len(final_contexts),
        },
        "rerank": rerank_diagnostics,
    }
    return SideRetrievalResult(
        bundle={"queries": queries, "items": items},
        diagnostics=diagnostics,
        requested_backend=requested_backend,
        effective_backend=effective_backend,
        backend_fallback_reason=backend_fallback_reason,
        error_codes=deduped_codes,
    )


def _build_llm_cfg(settings: Settings, *, temperature: float) -> _SummaryConfig:
    return _SummaryConfig(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        base_url=settings.openai_base_url,
        timeout_secs=settings.openai_timeout_secs,
        temperature=min(max(temperature, 0.0), 0.5),
        max_retries=settings.openai_max_retries,
    )


def _normalize_text_list(raw: Any, *, limit: int = 8, max_chars: int = 180) -> list[str]:
    values = raw if isinstance(raw, list) else []
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        normalized = " ".join(text.split())[:max_chars]
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(normalized)
        if len(out) >= max(1, int(limit)):
            break
    return out


def _extract_heuristic_points(
    *,
    source_summary: dict[str, Any],
    source_bundle: dict[str, Any],
    limit: int = 6,
) -> list[str]:
    candidates: list[str] = []
    summary_text = str(source_summary.get("text") or "").strip()
    if summary_text:
        for piece in re.split(r"[。！？\n;；]+", summary_text):
            item = piece.strip()
            if item:
                candidates.append(item)
    for item in source_bundle.get("items") or []:
        title = str((item or {}).get("title") or "").strip()
        snippet = str((item or {}).get("snippet") or "").strip()
        if title:
            candidates.append(title)
        if snippet:
            candidates.append(snippet[:120])
    return _normalize_text_list(candidates, limit=limit, max_chars=160)


def _safe_score(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return _clamp(numeric, 0.0, 100.0)


def _split_sentences(text: str, *, limit: int = 120) -> list[str]:
    pieces: list[str] = []
    for part in re.split(r"[。！？!?；;\n]+", text or ""):
        sentence = part.strip()
        if sentence:
            pieces.append(sentence[:240])
        if len(pieces) >= max(1, limit):
            break
    return pieces


def _parse_dimension_scores(raw: dict[str, Any]) -> dict[str, float]:
    dimension_raw = (
        raw.get("dimension_scores") or raw.get("dimensionScores") or raw.get("dimensions")
    )
    if not isinstance(dimension_raw, dict):
        return {}

    aliases = {
        "coverage": ("coverage", "coverage_score", "coverageScore"),
        "depth": ("depth", "rebuttal_depth", "rebuttalDepth"),
        "evidenceFit": ("evidence_fit", "evidenceFit", "evidence"),
        "keyPointHitRate": ("key_point_hit_rate", "keyPointHitRate", "hit_rate", "hitRate"),
    }
    parsed: dict[str, float] = {}
    for key, candidates in aliases.items():
        for candidate in candidates:
            score = _safe_score(dimension_raw.get(candidate))
            if score is None:
                continue
            parsed[key] = round(score, 2)
            break
    return parsed


def _build_heuristic_dimension_scores(
    *,
    key_points: list[str],
    hit_points: list[str],
    hit_ratio: float,
    target_summary: dict[str, Any],
    target_messages: list[PhaseDispatchMessage],
    source_bundle: dict[str, Any],
) -> dict[str, float]:
    safe_hit_ratio = _clamp(hit_ratio, 0.0, 1.0)
    key_point_hit_rate = len(hit_points) / float(
        max(1, len(_normalize_text_list(key_points, limit=12)))
    )

    target_text = str(target_summary.get("text") or "")
    target_text += "\n" + "\n".join(msg.content for msg in target_messages)
    sentence_token_sets = [
        set(_tokenize(sentence)) for sentence in _split_sentences(target_text) if sentence.strip()
    ]

    depth_samples: list[float] = []
    for point in hit_points:
        point_tokens = set(_tokenize(point))
        if not point_tokens:
            continue
        best_overlap = 0.0
        for sentence_tokens in sentence_token_sets:
            if not sentence_tokens:
                continue
            overlap = len(point_tokens & sentence_tokens) / float(max(1, len(point_tokens)))
            if overlap > best_overlap:
                best_overlap = overlap
        depth_samples.append(best_overlap)
    depth_overlap = sum(depth_samples) / float(max(1, len(depth_samples)))
    rebuttal_density = _count_rebuttals(target_messages) / float(max(1, len(target_messages)))
    depth_score = _clamp((depth_overlap * 0.75 + rebuttal_density * 0.25) * 100.0, 0.0, 100.0)

    target_tokens = set(_tokenize(target_text))
    evidence_overlaps: list[float] = []
    for item in (source_bundle.get("items") or [])[:8]:
        evidence_text = " ".join(
            [
                str((item or {}).get("title") or ""),
                str((item or {}).get("snippet") or ""),
            ]
        ).strip()
        evidence_tokens = set(_tokenize(evidence_text))
        if not evidence_tokens:
            continue
        overlap = len(evidence_tokens & target_tokens) / float(max(1, len(evidence_tokens)))
        evidence_overlaps.append(overlap)
    if evidence_overlaps:
        ranked = sorted(evidence_overlaps, reverse=True)
        top_overlap = ranked[0]
        avg_overlap = sum(ranked[: min(3, len(ranked))]) / float(min(3, len(ranked)))
        evidence_fit = _clamp((top_overlap * 0.6 + avg_overlap * 0.4) * 100.0, 0.0, 100.0)
    else:
        evidence_fit = 50.0

    return {
        "coverage": round(safe_hit_ratio * 100.0, 2),
        "depth": round(depth_score, 2),
        "evidenceFit": round(evidence_fit, 2),
        "keyPointHitRate": round(_clamp(key_point_hit_rate * 100.0, 0.0, 100.0), 2),
    }


def _compose_calibrated_agent2_score(
    *,
    llm_score: float | None,
    llm_dimensions: dict[str, float],
    heuristic_dimensions: dict[str, float],
    key_points: list[str],
    hit_ratio: float,
) -> tuple[float, float, dict[str, float], list[str]]:
    notes: list[str] = []
    dimensions: dict[str, float] = {}
    for key in ("coverage", "depth", "evidenceFit", "keyPointHitRate"):
        if key in llm_dimensions:
            dimensions[key] = round(_clamp(llm_dimensions[key], 0.0, 100.0), 2)
        else:
            dimensions[key] = round(_clamp(heuristic_dimensions.get(key, 50.0), 0.0, 100.0), 2)
            notes.append(f"dimension_fallback_{key}")

    raw_score = 0.0
    for key, weight in AGENT2_DIMENSION_WEIGHTS.items():
        raw_score += dimensions[key] * weight
    if llm_score is not None:
        raw_score = raw_score * 0.6 + llm_score * 0.4
        notes.append("blend_llm_score")

    calibrated = 50.0 + (raw_score - 50.0) * 0.88
    normalized_points = _normalize_text_list(key_points, limit=12)
    if len(normalized_points) < 3:
        calibrated -= 5.0
        notes.append("few_key_points_penalty")
    if hit_ratio < 0.25:
        calibrated = min(calibrated, 60.0)
        notes.append("low_hit_ratio_cap")
    if dimensions["evidenceFit"] < 35.0:
        calibrated -= 4.0
        notes.append("low_evidence_fit_penalty")
    if hit_ratio > 0.85 and dimensions["depth"] > 75.0 and dimensions["evidenceFit"] > 70.0:
        calibrated += 2.0
        notes.append("high_quality_bonus")

    final_score = round(_clamp(calibrated, 0.0, 100.0), 2)
    return final_score, round(raw_score, 2), dimensions, notes


def _score_hit_points(
    *,
    key_points: list[str],
    target_summary: dict[str, Any],
    target_messages: list[PhaseDispatchMessage],
) -> tuple[float, list[str], list[str], float]:
    normalized_points = _normalize_text_list(key_points, limit=8, max_chars=180)
    if not normalized_points:
        return 50.0, [], [], 0.0

    target_text = str(target_summary.get("text") or "")
    target_text += "\n" + "\n".join(msg.content for msg in target_messages)
    corpus_tokens = set(_tokenize(target_text))

    hit_points: list[str] = []
    miss_points: list[str] = []
    for point in normalized_points:
        tokens = set(_tokenize(point))
        if not tokens:
            miss_points.append(point)
            continue
        overlap_ratio = len(tokens & corpus_tokens) / float(max(1, len(tokens)))
        if overlap_ratio >= 0.2:
            hit_points.append(point)
        else:
            miss_points.append(point)
    hit_ratio = len(hit_points) / float(max(1, len(normalized_points)))
    score = round(_clamp(40.0 + hit_ratio * 60.0, 0.0, 100.0), 2)
    return score, hit_points, miss_points, hit_ratio


def _build_agent2_a6_system_prompt(*, source_side: str, target_side: str, topic_domain: str) -> str:
    return (
        "你是顶级辩手。"
        "你的任务是基于给定素材，为对方阵营生成理想反驳。"
        "仅可使用输入素材，不得编造新事实。"
        "输出JSON字段：ideal_rebuttal, key_points。"
        f"source_side={source_side}, target_side={target_side}, topic_domain={topic_domain}。"
    )


def _build_agent2_a6_user_prompt(
    *,
    settings: Settings,
    system_prompt: str,
    source_summary: dict[str, Any],
    source_messages: list[PhaseDispatchMessage],
    source_bundle: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    segments: list[TokenSegment] = [
        TokenSegment(
            segment_id="a6_instruction",
            priority=0,
            required=True,
            text=(
                "请为对方阵营生成理想反驳答案，并提炼关键点（3-8条）。\n"
                "要求：\n"
                "1) 不得引入输入之外的事实。\n"
                "2) key_points必须可用于后续命中评估。\n"
                "3) 仅输出JSON。"
            ),
        ),
        TokenSegment(
            segment_id="a6_source_summary_header",
            priority=1,
            required=True,
            text="source_summary:",
        ),
        TokenSegment(
            segment_id="a6_source_summary_body",
            priority=2,
            required=True,
            text=str(source_summary.get("text") or ""),
        ),
        TokenSegment(
            segment_id="a6_source_messages_header",
            priority=3,
            required=False,
            text="source_messages:",
        ),
    ]
    for idx, msg in enumerate(source_messages[-8:]):
        segments.append(
            TokenSegment(
                segment_id=f"a6_message_{msg.message_id}",
                priority=10 + idx,
                required=False,
                text=f"[{msg.message_id}] {str(msg.content or '').strip()}",
            )
        )
    segments.append(
        TokenSegment(
            segment_id="a6_source_retrieval_header",
            priority=30,
            required=False,
            text="source_retrieval:",
        )
    )
    for idx, item in enumerate((source_bundle.get("items") or [])[:8]):
        title = str((item or {}).get("title") or "").strip()
        snippet = str((item or {}).get("snippet") or "").strip()
        segments.append(
            TokenSegment(
                segment_id=f"a6_retrieval_{idx}",
                priority=40 + idx,
                required=False,
                text=f"- {title}: {snippet}",
            )
        )

    budget_tokens = _available_prompt_budget(
        settings,
        model=settings.openai_model,
        system_prompt=system_prompt,
        total_budget=settings.agent2_prompt_max_tokens,
        minimum_user_budget=256,
    )
    return _pack_user_prompt_segments(
        settings,
        model=settings.openai_model,
        budget_tokens=budget_tokens,
        segments=segments,
    )


def _build_agent2_a7_system_prompt(*, target_side: str) -> str:
    return (
        "你是辩论命中度评估器。"
        "根据理想反驳与真实内容比较，输出命中分。"
        "输出JSON字段：score, hit_points, miss_points, rationale, dimension_scores。"
        "dimension_scores必须包含coverage/depth/evidence_fit/key_point_hit_rate四项，范围0-100。"
        f"target_side={target_side}。"
    )


def _build_agent2_a7_user_prompt(
    *,
    settings: Settings,
    system_prompt: str,
    ideal_rebuttal: str,
    key_points: list[str],
    target_summary: dict[str, Any],
    target_messages: list[PhaseDispatchMessage],
) -> tuple[str, dict[str, Any]]:
    segments: list[TokenSegment] = [
        TokenSegment(
            segment_id="a7_instruction",
            priority=0,
            required=True,
            text=(
                "请评估真实内容命中了理想反驳多少关键点，并给出0-100分。\n"
                "要求：\n"
                "1) score范围0到100。\n"
                "2) hit_points/miss_points 只写关键点短语。\n"
                "3) dimension_scores包含coverage/depth/evidence_fit/key_point_hit_rate，逐项给0-100分。\n"
                "4) 仅输出JSON。"
            ),
        ),
        TokenSegment(
            segment_id="a7_ideal_rebuttal_header",
            priority=1,
            required=True,
            text="ideal_rebuttal:",
        ),
        TokenSegment(
            segment_id="a7_ideal_rebuttal_body",
            priority=2,
            required=True,
            text=ideal_rebuttal,
        ),
        TokenSegment(
            segment_id="a7_key_points_header",
            priority=3,
            required=True,
            text="key_points:",
        ),
    ]
    for idx, item in enumerate(key_points[:12]):
        segments.append(
            TokenSegment(
                segment_id=f"a7_key_point_{idx}",
                priority=10 + idx,
                required=False,
                text=f"- {item}",
            )
        )
    segments.extend(
        [
            TokenSegment(
                segment_id="a7_target_summary_header",
                priority=30,
                required=False,
                text="target_summary:",
            ),
            TokenSegment(
                segment_id="a7_target_summary_body",
                priority=31,
                required=False,
                text=str(target_summary.get("text") or ""),
            ),
            TokenSegment(
                segment_id="a7_target_messages_header",
                priority=32,
                required=False,
                text="target_messages:",
            ),
        ]
    )
    for idx, msg in enumerate(target_messages[-8:]):
        segments.append(
            TokenSegment(
                segment_id=f"a7_message_{msg.message_id}",
                priority=40 + idx,
                required=False,
                text=f"[{msg.message_id}] {str(msg.content or '').strip()}",
            )
        )

    budget_tokens = _available_prompt_budget(
        settings,
        model=settings.openai_model,
        system_prompt=system_prompt,
        total_budget=settings.agent2_prompt_max_tokens,
        minimum_user_budget=256,
    )
    return _pack_user_prompt_segments(
        settings,
        model=settings.openai_model,
        budget_tokens=budget_tokens,
        segments=segments,
    )


def _build_agent2_path_rationale(
    *,
    target_side: str,
    hit_ratio: float,
    source: str,
    score: float | None = None,
    fallback_reason: str | None = None,
) -> str:
    ratio = round(hit_ratio, 4)
    base = (
        f"agent2 path for {target_side} uses ideal rebuttal hit scoring; "
        f"hit_ratio={ratio}, source={source}."
    )
    if score is not None:
        base = f"{base} calibrated_score={round(score, 2)}."
    if fallback_reason:
        return f"{base} fallback_reason={fallback_reason}."
    return base


def _build_agent2_heuristic_path(
    *,
    target_side: str,
    source_summary: dict[str, Any],
    source_bundle: dict[str, Any],
    target_summary: dict[str, Any],
    target_messages: list[PhaseDispatchMessage],
    source: str,
    fallback_reason: str | None,
    error_codes: list[str],
) -> Agent2PathResult:
    key_points = _extract_heuristic_points(
        source_summary=source_summary,
        source_bundle=source_bundle,
        limit=6,
    )
    _, hit_points, miss_points, hit_ratio = _score_hit_points(
        key_points=key_points,
        target_summary=target_summary,
        target_messages=target_messages,
    )
    heuristic_dimensions = _build_heuristic_dimension_scores(
        key_points=key_points,
        hit_points=hit_points,
        hit_ratio=hit_ratio,
        target_summary=target_summary,
        target_messages=target_messages,
        source_bundle=source_bundle,
    )
    calibrated_score, raw_score, dimensions, notes = _compose_calibrated_agent2_score(
        llm_score=None,
        llm_dimensions={},
        heuristic_dimensions=heuristic_dimensions,
        key_points=key_points,
        hit_ratio=hit_ratio,
    )
    return Agent2PathResult(
        target_side=target_side,
        score=calibrated_score,
        raw_score=raw_score,
        calibrated_score=calibrated_score,
        dimension_scores=dimensions,
        calibration_notes=notes,
        hit_points=hit_points,
        miss_points=miss_points,
        rationale=_build_agent2_path_rationale(
            target_side=target_side,
            hit_ratio=hit_ratio,
            source=source,
            score=calibrated_score,
            fallback_reason=fallback_reason,
        ),
        ideal_rebuttal="; ".join(key_points)[:1200],
        key_points=key_points,
        source=source,
        fallback_reason=fallback_reason,
        error_codes=error_codes,
        usage_records=[],
        token_clip_summaries=[],
    )


async def _run_agent2_path(
    *,
    topic_domain: str,
    source_side: str,
    target_side: str,
    source_summary: dict[str, Any],
    source_messages: list[PhaseDispatchMessage],
    source_bundle: dict[str, Any],
    target_summary: dict[str, Any],
    target_messages: list[PhaseDispatchMessage],
    settings: Settings,
) -> Agent2PathResult:
    if not should_use_openai(settings.provider, settings.openai_api_key):
        return _build_agent2_heuristic_path(
            target_side=target_side,
            source_summary=source_summary,
            source_bundle=source_bundle,
            target_summary=target_summary,
            target_messages=target_messages,
            source="heuristic",
            fallback_reason="provider_disabled_or_missing_key",
            error_codes=[],
        )

    cfg_a6 = _build_llm_cfg(settings, temperature=0.2)
    cfg_a7 = _build_llm_cfg(settings, temperature=0.1)
    a6_system_prompt = _build_agent2_a6_system_prompt(
        source_side=source_side,
        target_side=target_side,
        topic_domain=topic_domain,
    )
    a6_user_prompt, a6_clip_summary = _build_agent2_a6_user_prompt(
        settings=settings,
        system_prompt=a6_system_prompt,
        source_summary=source_summary,
        source_messages=source_messages,
        source_bundle=source_bundle,
    )
    token_clip_summaries = [
        {
            "callId": f"a6_{target_side}",
            "stage": "agent2_a6",
            "targetSide": target_side,
            **a6_clip_summary,
        }
    ]
    clip_error_codes: list[str] = []
    if bool(a6_clip_summary.get("clipped")):
        clip_error_codes.append(TOKEN_CLIP_ERROR_AGENT2)

    try:
        a6_raw = await call_openai_json(
            cfg=cfg_a6,
            system_prompt=a6_system_prompt,
            user_prompt=a6_user_prompt,
        )
        a6_usage = _extract_llm_usage_record(
            settings=settings,
            cfg=cfg_a6,
            call_id=f"a6_{target_side}",
            system_prompt=a6_system_prompt,
            user_prompt=a6_user_prompt,
            response_payload=a6_raw,
        )
        a6_raw = _clean_openai_payload(a6_raw)
        ideal_rebuttal = str(
            a6_raw.get("ideal_rebuttal")
            or a6_raw.get("idealRebuttal")
            or a6_raw.get("rebuttal")
            or ""
        ).strip()
        key_points = _normalize_text_list(
            a6_raw.get("key_points") or a6_raw.get("keyPoints"),
            limit=8,
        )
        if not key_points:
            key_points = _extract_heuristic_points(
                source_summary=source_summary,
                source_bundle=source_bundle,
                limit=6,
            )
        if not ideal_rebuttal:
            ideal_rebuttal = "; ".join(key_points)[:1200]

        a7_system_prompt = _build_agent2_a7_system_prompt(target_side=target_side)
        a7_user_prompt, a7_clip_summary = _build_agent2_a7_user_prompt(
            settings=settings,
            system_prompt=a7_system_prompt,
            ideal_rebuttal=ideal_rebuttal,
            key_points=key_points,
            target_summary=target_summary,
            target_messages=target_messages,
        )
        token_clip_summaries.append(
            {
                "callId": f"a7_{target_side}",
                "stage": "agent2_a7",
                "targetSide": target_side,
                **a7_clip_summary,
            }
        )
        if bool(a7_clip_summary.get("clipped")) and TOKEN_CLIP_ERROR_AGENT2 not in clip_error_codes:
            clip_error_codes.append(TOKEN_CLIP_ERROR_AGENT2)

        a7_raw = await call_openai_json(
            cfg=cfg_a7,
            system_prompt=a7_system_prompt,
            user_prompt=a7_user_prompt,
        )
        a7_usage = _extract_llm_usage_record(
            settings=settings,
            cfg=cfg_a7,
            call_id=f"a7_{target_side}",
            system_prompt=a7_system_prompt,
            user_prompt=a7_user_prompt,
            response_payload=a7_raw,
        )
        a7_raw = _clean_openai_payload(a7_raw)
        score_raw = a7_raw.get("score") or a7_raw.get("hit_score") or a7_raw.get("hitScore")
        llm_score = _safe_score(score_raw)
        hit_points = _normalize_text_list(
            a7_raw.get("hit_points") or a7_raw.get("hitPoints"),
            limit=8,
        )
        miss_points = _normalize_text_list(
            a7_raw.get("miss_points") or a7_raw.get("missPoints"),
            limit=8,
        )
        rationale = str(a7_raw.get("rationale") or "").strip()
        llm_dimensions = _parse_dimension_scores(a7_raw)

        _, heuristic_hit, heuristic_miss, hit_ratio = _score_hit_points(
            key_points=key_points,
            target_summary=target_summary,
            target_messages=target_messages,
        )
        if not hit_points and not miss_points:
            hit_points = heuristic_hit
            miss_points = heuristic_miss
        heuristic_dimensions = _build_heuristic_dimension_scores(
            key_points=key_points,
            hit_points=hit_points,
            hit_ratio=hit_ratio,
            target_summary=target_summary,
            target_messages=target_messages,
            source_bundle=source_bundle,
        )
        calibrated_score, raw_score, dimensions, notes = _compose_calibrated_agent2_score(
            llm_score=llm_score,
            llm_dimensions=llm_dimensions,
            heuristic_dimensions=heuristic_dimensions,
            key_points=key_points,
            hit_ratio=hit_ratio,
        )
        if not rationale:
            rationale = _build_agent2_path_rationale(
                target_side=target_side,
                hit_ratio=hit_ratio,
                source="llm",
                score=calibrated_score,
            )

        return Agent2PathResult(
            target_side=target_side,
            score=calibrated_score,
            raw_score=raw_score,
            calibrated_score=calibrated_score,
            dimension_scores=dimensions,
            calibration_notes=notes,
            hit_points=hit_points,
            miss_points=miss_points,
            rationale=rationale[:2000],
            ideal_rebuttal=ideal_rebuttal[:2000],
            key_points=key_points,
            source="llm",
            fallback_reason=None,
            error_codes=clip_error_codes,
            usage_records=[a6_usage, a7_usage],
            token_clip_summaries=token_clip_summaries,
        )
    except Exception as err:
        return _build_agent2_heuristic_path(
            target_side=target_side,
            source_summary=source_summary,
            source_bundle=source_bundle,
            target_summary=target_summary,
            target_messages=target_messages,
            source="heuristic",
            fallback_reason="llm_path_failed",
            error_codes=[
                f"agent2_path_failed_{target_side}",
                classify_openai_failure(str(err)),
                *clip_error_codes,
            ],
        )


def _fuse_agent3_score(
    *,
    agent1_score: dict[str, Any],
    agent2_score: dict[str, Any],
    w1: float,
    w2: float,
) -> dict[str, Any]:
    return {
        "pro": round(_clamp(agent1_score["pro"] * w1 + agent2_score["pro"] * w2, 0.0, 100.0), 2),
        "con": round(_clamp(agent1_score["con"] * w1 + agent2_score["con"] * w2, 0.0, 100.0), 2),
        "w1": round(w1, 4),
        "w2": round(w2, 4),
    }


async def _build_agent2_bidirectional_score(
    *,
    topic_domain: str,
    pro_summary: dict[str, Any],
    con_summary: dict[str, Any],
    pro_messages: list[PhaseDispatchMessage],
    con_messages: list[PhaseDispatchMessage],
    pro_bundle: dict[str, Any],
    con_bundle: dict[str, Any],
    baseline_agent2_score: dict[str, Any],
    settings: Settings,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[str],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    con_path, pro_path = await asyncio.gather(
        _run_agent2_path(
            topic_domain=topic_domain,
            source_side="pro",
            target_side="con",
            source_summary=pro_summary,
            source_messages=pro_messages,
            source_bundle=pro_bundle,
            target_summary=con_summary,
            target_messages=con_messages,
            settings=settings,
        ),
        _run_agent2_path(
            topic_domain=topic_domain,
            source_side="con",
            target_side="pro",
            source_summary=con_summary,
            source_messages=con_messages,
            source_bundle=con_bundle,
            target_summary=pro_summary,
            target_messages=pro_messages,
            settings=settings,
        ),
    )

    error_codes: list[str] = []
    error_codes.extend(con_path.error_codes)
    error_codes.extend(pro_path.error_codes)
    usage_records: list[dict[str, Any]] = []
    usage_records.extend(con_path.usage_records)
    usage_records.extend(pro_path.usage_records)
    token_clip_summaries: list[dict[str, Any]] = []
    token_clip_summaries.extend(con_path.token_clip_summaries)
    token_clip_summaries.extend(pro_path.token_clip_summaries)

    pro_failed = any(code.startswith("agent2_path_failed_pro") for code in pro_path.error_codes)
    con_failed = any(code.startswith("agent2_path_failed_con") for code in con_path.error_codes)

    pro_score = pro_path.score if not pro_failed else float(baseline_agent2_score["pro"])
    con_score = con_path.score if not con_failed else float(baseline_agent2_score["con"])
    pro_used_baseline = bool(pro_failed)
    con_used_baseline = bool(con_failed)
    if pro_failed or con_failed:
        error_codes.append("agent2_partial_degraded")
    if pro_failed and con_failed:
        error_codes.append("agent2_both_paths_failed")

    hit_items = [f"pro:{item}" for item in pro_path.hit_points[:4]]
    hit_items.extend(f"con:{item}" for item in con_path.hit_points[:4])
    miss_items = [f"pro:{item}" for item in pro_path.miss_points[:4]]
    miss_items.extend(f"con:{item}" for item in con_path.miss_points[:4])

    agent2_score = {
        "pro": round(float(pro_score), 2),
        "con": round(float(con_score), 2),
        "hitItems": hit_items[:8],
        "missItems": miss_items[:8],
        "rationale": (
            "agent2 bidirectional paths evaluated ideal rebuttal hit score."
            f" pro_source={pro_path.source}, con_source={con_path.source},"
            f" pro_baseline_fallback={pro_used_baseline}, con_baseline_fallback={con_used_baseline}"
        ),
    }
    audit = {
        "promptVersion": AGENT2_PROMPT_VERSION,
        "weights": AGENT2_DIMENSION_WEIGHTS,
        "resilience": {
            "pro": {
                "usedBaselineFallback": pro_used_baseline,
                "baselineScore": round(float(baseline_agent2_score["pro"]), 2),
                "effectiveScore": round(float(pro_score), 2),
                "pathErrorCodes": pro_path.error_codes,
            },
            "con": {
                "usedBaselineFallback": con_used_baseline,
                "baselineScore": round(float(baseline_agent2_score["con"]), 2),
                "effectiveScore": round(float(con_score), 2),
                "pathErrorCodes": con_path.error_codes,
            },
        },
        "paths": {
            "pro": {
                "sourceSide": "con",
                "targetSide": "pro",
                "source": pro_path.source,
                "fallbackReason": pro_path.fallback_reason,
                "pathStatus": "failed_baseline_fallback" if pro_used_baseline else "ok",
                "score": pro_path.score,
                "rawScore": pro_path.raw_score,
                "calibratedScore": pro_path.calibrated_score,
                "dimensionScores": pro_path.dimension_scores,
                "calibrationNotes": pro_path.calibration_notes,
                "idealRebuttal": pro_path.ideal_rebuttal,
                "keyPoints": pro_path.key_points,
                "hitPoints": pro_path.hit_points,
                "missPoints": pro_path.miss_points,
                "rationale": pro_path.rationale,
            },
            "con": {
                "sourceSide": "pro",
                "targetSide": "con",
                "source": con_path.source,
                "fallbackReason": con_path.fallback_reason,
                "pathStatus": "failed_baseline_fallback" if con_used_baseline else "ok",
                "score": con_path.score,
                "rawScore": con_path.raw_score,
                "calibratedScore": con_path.calibrated_score,
                "dimensionScores": con_path.dimension_scores,
                "calibrationNotes": con_path.calibration_notes,
                "idealRebuttal": con_path.ideal_rebuttal,
                "keyPoints": con_path.key_points,
                "hitPoints": con_path.hit_points,
                "missPoints": con_path.miss_points,
                "rationale": con_path.rationale,
            },
        },
    }
    deduped_codes: list[str] = []
    seen_codes: set[str] = set()
    for code in error_codes:
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)
        deduped_codes.append(code)
    return agent2_score, audit, deduped_codes, usage_records, token_clip_summaries


def _count_rebuttals(messages: list[PhaseDispatchMessage]) -> int:
    total = 0
    for msg in messages:
        lowered = msg.content.lower()
        if any(marker in lowered for marker in REBUTTAL_MARKERS):
            total += 1
    return total


def _marker_density(messages: list[PhaseDispatchMessage], markers: tuple[str, ...]) -> float:
    if not messages:
        return 0.0
    matched = 0
    for msg in messages:
        lowered = msg.content.lower()
        if any(marker in lowered for marker in markers):
            matched += 1
    return matched / float(len(messages))


def _digit_density(messages: list[PhaseDispatchMessage]) -> float:
    if not messages:
        return 0.0
    matched = 0
    for msg in messages:
        if any(ch.isdigit() for ch in msg.content):
            matched += 1
    return matched / float(len(messages))


def _punctuation_density(messages: list[PhaseDispatchMessage]) -> float:
    if not messages:
        return 0.0
    matched = 0
    for msg in messages:
        if any(ch in msg.content for ch in ("，", "。", "！", "？", ",", ".", "!", "?", ";", "；")):
            matched += 1
    return matched / float(len(messages))


def _average_message_length(messages: list[PhaseDispatchMessage]) -> float:
    if not messages:
        return 0.0
    total_chars = sum(len(str(msg.content or "").strip()) for msg in messages)
    return total_chars / float(len(messages))


def _token_diversity(messages: list[PhaseDispatchMessage]) -> float:
    tokens: list[str] = []
    for msg in messages:
        tokens.extend(_tokenize(msg.content))
    if not tokens:
        return 0.0
    return len(set(tokens)) / float(len(tokens))


def _compute_side_dimensions(
    *,
    side_messages: list[PhaseDispatchMessage],
    opponent_messages: list[PhaseDispatchMessage],
    retrieval_items: list[dict[str, Any]],
) -> dict[str, float]:
    logic_density = _marker_density(side_messages, LOGIC_MARKERS)
    evidence_density = _marker_density(side_messages, EVIDENCE_MARKERS)
    rebuttal_rate = _count_rebuttals(side_messages) / float(max(1, len(side_messages)))
    digit_density = _digit_density(side_messages)
    punctuation_density = _punctuation_density(side_messages)
    avg_length = _average_message_length(side_messages)
    length_norm = _clamp(avg_length / 180.0, 0.0, 1.0)
    diversity = _token_diversity(side_messages)

    retrieval_support = _clamp(len(retrieval_items) / 6.0, 0.0, 1.0)
    opponent_tokens = set(_tokenize("\n".join(msg.content for msg in opponent_messages)))
    rebuttal_overlaps: list[float] = []
    for msg in side_messages:
        lowered = msg.content.lower()
        if not any(marker in lowered for marker in REBUTTAL_MARKERS):
            continue
        msg_tokens = set(_tokenize(msg.content))
        if not msg_tokens:
            continue
        rebuttal_overlaps.append(len(msg_tokens & opponent_tokens) / float(max(1, len(msg_tokens))))
    rebuttal_overlap = sum(rebuttal_overlaps) / float(max(1, len(rebuttal_overlaps)))

    logic = _clamp(
        (0.45 * logic_density + 0.25 * length_norm + 0.30 * diversity) * 100.0, 0.0, 100.0
    )
    evidence = _clamp(
        (0.50 * retrieval_support + 0.30 * evidence_density + 0.20 * digit_density) * 100.0,
        0.0,
        100.0,
    )
    rebuttal = _clamp((0.45 * rebuttal_rate + 0.55 * rebuttal_overlap) * 100.0, 0.0, 100.0)
    expression = _clamp(
        (0.40 * length_norm + 0.35 * punctuation_density + 0.25 * diversity) * 100.0,
        0.0,
        100.0,
    )

    return {
        "logic": round(logic, 2),
        "evidence": round(evidence, 2),
        "rebuttal": round(rebuttal, 2),
        "expression": round(expression, 2),
    }


def _collect_side_evidence_refs(
    *,
    messages: list[PhaseDispatchMessage],
    retrieval_items: list[dict[str, Any]],
) -> dict[str, Any]:
    selected_ids: list[int] = []
    seen_ids: set[int] = set()
    priority_markers = REBUTTAL_MARKERS + LOGIC_MARKERS + EVIDENCE_MARKERS
    for msg in messages:
        lowered = msg.content.lower()
        if not any(marker in lowered for marker in priority_markers):
            continue
        if msg.message_id in seen_ids:
            continue
        seen_ids.add(msg.message_id)
        selected_ids.append(msg.message_id)
        if len(selected_ids) >= 6:
            break
    if len(selected_ids) < 3:
        for msg in messages:
            if msg.message_id in seen_ids:
                continue
            seen_ids.add(msg.message_id)
            selected_ids.append(msg.message_id)
            if len(selected_ids) >= 3:
                break

    chunk_ids: list[str] = []
    seen_chunk_ids: set[str] = set()
    for item in retrieval_items[:8]:
        chunk_id = str(item.get("chunkId") or item.get("chunk_id") or "").strip()
        if not chunk_id or chunk_id in seen_chunk_ids:
            continue
        seen_chunk_ids.add(chunk_id)
        chunk_ids.append(chunk_id)
        if len(chunk_ids) >= 6:
            break
    return {
        "messageIds": selected_ids,
        "chunkIds": chunk_ids,
    }


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

    pro_dimensions = _compute_side_dimensions(
        side_messages=pro_messages,
        opponent_messages=con_messages,
        retrieval_items=pro_retrieval_items,
    )
    con_dimensions = _compute_side_dimensions(
        side_messages=con_messages,
        opponent_messages=pro_messages,
        retrieval_items=con_retrieval_items,
    )
    dimension_weights = {
        "logic": 0.30,
        "evidence": 0.30,
        "rebuttal": 0.25,
        "expression": 0.15,
    }
    pro_weighted = sum(pro_dimensions[key] * weight for key, weight in dimension_weights.items())
    con_weighted = sum(con_dimensions[key] * weight for key, weight in dimension_weights.items())

    pro_rebuttal_rate = _count_rebuttals(pro_messages) / float(max(1, len(pro_messages)))
    con_rebuttal_rate = _count_rebuttals(con_messages) / float(max(1, len(con_messages)))
    rebuttal_delta = pro_rebuttal_rate - con_rebuttal_rate

    pro_hits = len(pro_retrieval_items)
    con_hits = len(con_retrieval_items)
    rag_delta = (pro_hits - con_hits) / float(max(1, max(pro_hits, con_hits, 1)))

    balance_adjustment = participation_delta * 4.0 + rebuttal_delta * 3.0
    agent1_pro = round(_clamp(pro_weighted + balance_adjustment, 0.0, 100.0), 2)
    agent1_con = round(_clamp(con_weighted - balance_adjustment, 0.0, 100.0), 2)

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
        "weights": dimension_weights,
        "dimensions": {
            "pro": pro_dimensions,
            "con": con_dimensions,
        },
        "evidenceRefs": {
            "pro": _collect_side_evidence_refs(
                messages=pro_messages,
                retrieval_items=pro_retrieval_items,
            ),
            "con": _collect_side_evidence_refs(
                messages=con_messages,
                retrieval_items=con_retrieval_items,
            ),
        },
        "balanceSignals": {
            "proCoverage": round(pro_count / float(total_messages), 4),
            "conCoverage": round(con_count / float(total_messages), 4),
            "proRebuttalRate": round(pro_rebuttal_rate, 4),
            "conRebuttalRate": round(con_rebuttal_rate, 4),
            "participationDelta": round(participation_delta, 4),
            "rebuttalDelta": round(rebuttal_delta, 4),
        },
        "rationale": (
            "agent1 uses weighted rubric dimensions (logic/evidence/rebuttal/expression) "
            "with light participation+rebuttal balance adjustment."
        ),
    }
    agent2 = {
        "pro": agent2_pro,
        "con": agent2_con,
        "hitItems": [
            item.get("chunkId") for item in pro_retrieval_items[:6] if item.get("chunkId")
        ],
        "missItems": [
            item.get("chunkId") for item in con_retrieval_items[:6] if item.get("chunkId")
        ],
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
    if any(code.startswith("summary_") for code in error_codes):
        level = max(level, 1)
    if any(code.startswith("agent2_") for code in error_codes):
        level = max(level, 1)
    if "agent2_both_paths_failed" in error_codes:
        level = max(level, 2)
    if any(code.startswith("rag_") for code in error_codes):
        level = max(level, 2)
    if any(code in {"judge_timeout", "model_overload"} for code in error_codes):
        level = max(level, 2)
    return level


async def build_phase_report_payload(
    *,
    request: PhaseDispatchRequest,
    settings: Settings,
) -> dict[str, Any]:
    started = perf_counter()

    summary_started = perf_counter()
    pro_messages = _select_side_messages(request, "pro")
    con_messages = _select_side_messages(request, "con")
    pro_summary_result, con_summary_result = await asyncio.gather(
        _build_side_summary_with_guard(
            request,
            side="pro",
            side_messages=pro_messages,
            settings=settings,
        ),
        _build_side_summary_with_guard(
            request,
            side="con",
            side_messages=con_messages,
            settings=settings,
        ),
    )
    pro_summary = pro_summary_result.summary
    con_summary = con_summary_result.summary
    usage_records: list[dict[str, Any]] = []
    usage_records.extend(pro_summary_result.usage_records)
    usage_records.extend(con_summary_result.usage_records)
    token_clip_summaries: list[dict[str, Any]] = []
    token_clip_summaries.extend(pro_summary_result.token_clip_summaries)
    token_clip_summaries.extend(con_summary_result.token_clip_summaries)
    summary_latency_ms = (perf_counter() - summary_started) * 1000.0

    retrieval_started = perf_counter()
    pro_queries = _build_side_queries(request, side="pro", side_messages=pro_messages)
    con_queries = _build_side_queries(request, side="con", side_messages=con_messages)

    pro_retrieval_result = _retrieve_side_with_query_plan(
        request,
        side="pro",
        side_messages=pro_messages,
        queries=pro_queries,
        settings=settings,
    )
    con_retrieval_result = _retrieve_side_with_query_plan(
        request,
        side="con",
        side_messages=con_messages,
        queries=con_queries,
        settings=settings,
    )
    retrieval_latency_ms = (perf_counter() - retrieval_started) * 1000.0

    pro_bundle = pro_retrieval_result.bundle
    con_bundle = con_retrieval_result.bundle
    pro_items = pro_bundle.get("items", [])
    con_items = con_bundle.get("items", [])

    baseline_agent1_score, baseline_agent2_score, _ = _compute_phase_scores(
        request,
        pro_messages=pro_messages,
        con_messages=con_messages,
        pro_retrieval_items=pro_items,
        con_retrieval_items=con_items,
    )
    (
        agent2_score,
        agent2_audit,
        agent2_error_codes,
        agent2_usage_records,
        agent2_token_clip_summaries,
    ) = await _build_agent2_bidirectional_score(
        topic_domain=request.topic_domain,
        pro_summary=pro_summary,
        con_summary=con_summary,
        pro_messages=pro_messages,
        con_messages=con_messages,
        pro_bundle=pro_bundle,
        con_bundle=con_bundle,
        baseline_agent2_score=baseline_agent2_score,
        settings=settings,
    )
    usage_records.extend(agent2_usage_records)
    token_clip_summaries.extend(agent2_token_clip_summaries)

    if "agent2_both_paths_failed" in agent2_error_codes:
        fusion_w1, fusion_w2 = 1.0, 0.0
    elif "agent2_partial_degraded" in agent2_error_codes:
        fusion_w1, fusion_w2 = 0.7, 0.3
    else:
        fusion_w1, fusion_w2 = 0.35, 0.65
    agent3_score = _fuse_agent3_score(
        agent1_score=baseline_agent1_score,
        agent2_score=agent2_score,
        w1=fusion_w1,
        w2=fusion_w2,
    )

    error_codes: list[str] = []
    error_codes.extend(pro_summary_result.error_codes)
    error_codes.extend(con_summary_result.error_codes)
    error_codes.extend(pro_retrieval_result.error_codes)
    error_codes.extend(con_retrieval_result.error_codes)
    error_codes.extend(agent2_error_codes)
    deduped_error_codes: list[str] = []
    seen_codes: set[str] = set()
    for code in error_codes:
        if code in seen_codes:
            continue
        seen_codes.add(code)
        deduped_error_codes.append(code)

    prompt_tokens = sum(max(0, int(item.get("prompt", 0))) for item in usage_records)
    completion_tokens = sum(max(0, int(item.get("completion", 0))) for item in usage_records)
    total_tokens = sum(max(0, int(item.get("total", 0))) for item in usage_records)
    usage_estimated = any(bool(item.get("usageEstimated")) for item in usage_records)

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
        "a5": _hash_payload(baseline_agent1_score),
        "a6": _hash_payload(agent2_audit),
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
        "agent1Score": baseline_agent1_score,
        "agent2Score": agent2_score,
        "agent3WeightedScore": agent3_score,
        "promptHashes": prompt_hashes,
        "tokenUsage": {
            "prompt": prompt_tokens,
            "completion": completion_tokens,
            "total": total_tokens if total_tokens > 0 else prompt_tokens + completion_tokens,
            "usageEstimated": usage_estimated,
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
            "pipelineVersion": "v3-phase-m5-agent2-bidirectional-v2",
            "idempotencyKey": request.idempotency_key,
            "summaryPromptVersion": SUMMARY_PROMPT_VERSION,
            "agent2PromptVersion": AGENT2_PROMPT_VERSION,
            "agent2Audit": agent2_audit,
            "summaryAudit": {
                "coverageThreshold": _summary_coverage_threshold(settings),
                "pro": {
                    "source": pro_summary_result.source,
                    "coverageRatio": round(pro_summary_result.coverage_ratio, 4),
                    "fallbackReason": pro_summary_result.fallback_reason,
                },
                "con": {
                    "source": con_summary_result.source,
                    "coverageRatio": round(con_summary_result.coverage_ratio, 4),
                    "fallbackReason": con_summary_result.fallback_reason,
                },
            },
            "retrievalDiagnostics": {
                "pro": pro_retrieval_result.diagnostics,
                "con": con_retrieval_result.diagnostics,
            },
            "retrievalBackend": {
                "requestedPro": pro_retrieval_result.requested_backend,
                "requestedCon": con_retrieval_result.requested_backend,
                "effectivePro": pro_retrieval_result.effective_backend,
                "effectiveCon": con_retrieval_result.effective_backend,
                "fallbackReasonPro": pro_retrieval_result.backend_fallback_reason,
                "fallbackReasonCon": con_retrieval_result.backend_fallback_reason,
            },
            "tokenClipSummary": token_clip_summaries,
            "tokenUsageBreakdown": usage_records,
        },
    }
