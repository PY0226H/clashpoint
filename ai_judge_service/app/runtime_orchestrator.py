from __future__ import annotations

import hashlib
import json
from time import perf_counter
from typing import TYPE_CHECKING, Awaitable, Callable

from .models import JudgeDispatchRequest, SubmitJudgeReportInput
from .openai_judge import build_report_with_openai
from .rag_retriever import RAG_BACKEND_FILE, RetrievedContext, retrieve_contexts
from .runtime_errors import (
    ERROR_CONSISTENCY_CONFLICT,
    ERROR_JUDGE_TIMEOUT,
    ERROR_MODEL_OVERLOAD,
    ERROR_RAG_UNAVAILABLE,
    classify_rag_failure,
    normalize_runtime_error_code,
)
from .runtime_provider import build_report_with_provider
from .runtime_rag import (
    RuntimeRagResult,
    apply_rag_payload_fields,
    retrieve_runtime_contexts_with_meta,
)
from .scoring import build_report
from .settings import Settings

if TYPE_CHECKING:
    from .trace_store import TopicMemoryRecord, TraceStoreProtocol

RetrieveContextsFn = Callable[..., list[RetrievedContext]]
BuildOpenAiReportFn = Callable[..., Awaitable[SubmitJudgeReportInput]]
BuildMockReportFn = Callable[..., SubmitJudgeReportInput]


def _fault_nodes(settings: Settings) -> set[str]:
    return {
        str(node).strip().lower()
        for node in getattr(settings, "fault_injection_nodes", ())
        if str(node).strip()
    }


def _normalize_evidence_refs(report: SubmitJudgeReportInput) -> list[dict]:
    refs = report.payload.get("verdictEvidenceRefs")
    if not isinstance(refs, list):
        return []
    normalized: list[dict] = []
    for item in refs:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "messageId": item.get("messageId"),
                "side": item.get("side"),
                "role": item.get("role"),
                "reason": item.get("reason"),
                "sourceUrl": item.get("sourceUrl"),
            }
        )
    return normalized


def _build_topic_memory_contexts(
    records: list["TopicMemoryRecord"],
    *,
    max_chars_per_snippet: int,
) -> list[RetrievedContext]:
    contexts: list[RetrievedContext] = []
    max_chars = max(160, max_chars_per_snippet)
    for index, record in enumerate(records):
        evidence_rows: list[str] = []
        for evidence in record.evidence_refs[:4]:
            message_id = evidence.get("messageId") or evidence.get("message_id")
            reason = str(evidence.get("reason") or "").strip()
            if not message_id and not reason:
                continue
            evidence_rows.append(f"- message={message_id} reason={reason}")

        body_parts = [
            f"winner={record.winner or 'unknown'}",
            f"rubric={record.rubric_version}",
            f"rationale={record.rationale.strip()}",
        ]
        if evidence_rows:
            body_parts.append("evidence:\n" + "\n".join(evidence_rows))

        contexts.append(
            RetrievedContext(
                chunk_id=f"topic-memory-{record.job_id}-{index + 1}",
                title=f"TopicMemory #{index + 1}",
                source_url=f"memory://topic/{record.topic_domain}",
                content="\n".join(body_parts)[:max_chars],
                score=max(0.2, 0.95 - index * 0.05),
            )
        )
    return contexts


def _topic_memory_quality_scores(records: list["TopicMemoryRecord"]) -> list[float]:
    out: list[float] = []
    for record in records:
        raw = record.audit.get("qualityScore")
        try:
            score = float(raw)
        except Exception:
            continue
        if score < 0:
            continue
        out.append(score)
    return out


def _build_retrieval_snapshot(
    retrieved_contexts: list[RetrievedContext],
    *,
    max_items: int = 12,
    preview_chars: int = 160,
) -> list[dict]:
    snapshot: list[dict] = []
    for ctx in retrieved_contexts[: max(1, max_items)]:
        snapshot.append(
            {
                "chunkId": ctx.chunk_id,
                "title": ctx.title,
                "sourceUrl": ctx.source_url,
                "score": round(float(ctx.score), 4),
                "preview": str(ctx.content or "")[: max(40, preview_chars)],
            }
        )
    return snapshot


def _build_prompt_hash(
    *,
    request: JudgeDispatchRequest,
    effective_style_mode: str,
    retrieved_contexts: list[RetrievedContext],
) -> str:
    payload = {
        "jobId": request.job.job_id,
        "styleMode": effective_style_mode,
        "rubricVersion": request.rubric_version,
        "judgePolicyVersion": getattr(request, "judge_policy_version", "v2-default"),
        "topicDomain": getattr(request, "topic_domain", "default"),
        "topicTitle": getattr(request.topic, "title", ""),
        "messages": [
            {
                "messageId": msg.message_id,
                "side": msg.side,
                "content": msg.content,
            }
            for msg in request.messages
        ],
        "contexts": [
            {
                "chunkId": ctx.chunk_id,
                "sourceUrl": ctx.source_url,
                "content": ctx.content,
            }
            for ctx in retrieved_contexts
        ],
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _resolve_degradation_level(
    *,
    settings: Settings,
    rag_result: "RuntimeRagResult",
    report: SubmitJudgeReportInput,
    topic_memory_error: str | None = None,
) -> int:
    level = 0
    rag_diag = rag_result.retrieval_diagnostics if isinstance(rag_result.retrieval_diagnostics, dict) else {}
    rerank_effective = bool(rag_diag.get("rerankEnabledEffective", settings.rag_rerank_enabled))
    if settings.rag_rerank_enabled and not rerank_effective:
        level = max(level, 1)
    if rag_result.backend_fallback_reason:
        level = max(level, 1)
    if topic_memory_error:
        level = max(level, 1)
    if settings.rag_enabled and not report.payload.get("ragUsedByModel", False):
        level = max(level, 2)
    if report.payload.get("fallbackFrom") == "openai":
        level = max(level, 3)
    return min(level, settings.degrade_max_level)


def _collect_runtime_error_codes(
    *,
    settings: Settings,
    rag_result: "RuntimeRagResult",
    report: SubmitJudgeReportInput,
    topic_memory_error: str | None = None,
) -> list[str]:
    codes: list[str] = []
    rag_diag = rag_result.retrieval_diagnostics if isinstance(rag_result.retrieval_diagnostics, dict) else {}
    rag_error_code = rag_diag.get("errorCode")
    if rag_error_code:
        codes.append(normalize_runtime_error_code(str(rag_error_code)))
    if rag_result.backend_fallback_reason:
        codes.append(ERROR_RAG_UNAVAILABLE)
    if settings.rag_enabled and not report.payload.get("ragUsedByModel", False):
        codes.append(ERROR_RAG_UNAVAILABLE)
    if topic_memory_error:
        codes.append(ERROR_RAG_UNAVAILABLE)

    agent_pipeline = report.payload.get("agentPipeline")
    if isinstance(agent_pipeline, dict):
        reflection_action = str(agent_pipeline.get("reflectionAction") or "").strip().lower()
        if reflection_action in {"draw_protection", "low_margin_protection"}:
            codes.append(ERROR_CONSISTENCY_CONFLICT)

    if report.payload.get("fallbackFrom") == "openai":
        raw_code = str(report.payload.get("fallbackErrorCode") or ERROR_MODEL_OVERLOAD)
        codes.append(normalize_runtime_error_code(raw_code))

    deduped: list[str] = []
    seen: set[str] = set()
    for code in codes:
        normalized = normalize_runtime_error_code(code)
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _build_rag_failure_result(
    *,
    settings: Settings,
    error_code: str,
    error_message: str,
    fault_injected: bool,
) -> RuntimeRagResult:
    effective_backend = settings.rag_backend or RAG_BACKEND_FILE
    return RuntimeRagResult(
        retrieved_contexts=[],
        requested_backend=settings.rag_backend,
        effective_backend=effective_backend,
        backend_fallback_reason="rag_runtime_error",
        retrieval_diagnostics={
            "strategy": "runtime_error",
            "errorCode": normalize_runtime_error_code(error_code),
            "errorMessage": str(error_message)[:500],
            "faultInjected": fault_injected,
            "hybridEnabledBySettings": settings.rag_hybrid_enabled,
            "rerankEnabledBySettings": settings.rag_rerank_enabled,
            "hybridEnabledEffective": False,
            "rerankEnabledEffective": False,
        },
    )


async def build_report_by_runtime(
    *,
    request: JudgeDispatchRequest,
    effective_style_mode: str,
    style_mode_source: str,
    settings: Settings,
    trace_store: "TraceStoreProtocol | None" = None,
    retrieve_contexts_fn: RetrieveContextsFn = retrieve_contexts,
    build_report_with_openai_fn: BuildOpenAiReportFn = build_report_with_openai,
    build_mock_report_fn: BuildMockReportFn = build_report,
) -> SubmitJudgeReportInput:
    trace_id = getattr(request, "trace_id", None)
    retrieval_profile = getattr(request, "retrieval_profile", "hybrid_v1")
    injected = _fault_nodes(settings)
    overall_start = perf_counter()
    rag_start = perf_counter()
    try:
        if "rag_retrieve_timeout" in injected:
            raise RuntimeError("fault injected rag retrieve timeout")
        if "rag_retrieve_unavailable" in injected:
            raise RuntimeError("fault injected rag retrieve unavailable")
        rag_result = retrieve_runtime_contexts_with_meta(
            request=request,
            settings=settings,
            retrieve_contexts_fn=retrieve_contexts_fn,
        )
    except Exception as err:
        if "rag_retrieve_timeout" in injected:
            rag_code = ERROR_JUDGE_TIMEOUT
        elif "rag_retrieve_unavailable" in injected:
            rag_code = ERROR_RAG_UNAVAILABLE
        else:
            rag_code = classify_rag_failure(str(err))
        rag_result = _build_rag_failure_result(
            settings=settings,
            error_code=rag_code,
            error_message=str(err),
            fault_injected=bool({"rag_retrieve_timeout", "rag_retrieve_unavailable"}.intersection(injected)),
        )
    rag_elapsed_ms = (perf_counter() - rag_start) * 1000.0
    retrieved_contexts = list(rag_result.retrieved_contexts)
    topic_memories: list["TopicMemoryRecord"] = []
    topic_memory_error: str | None = None
    if settings.topic_memory_enabled and trace_store is not None:
        try:
            if "topic_memory_unavailable" in injected:
                raise RuntimeError("fault injected topic memory unavailable")
            topic_memories = trace_store.list_topic_memory(
                topic_domain=getattr(request, "topic_domain", "default"),
                rubric_version=request.rubric_version,
                limit=settings.topic_memory_limit,
            )
            retrieved_contexts = _build_topic_memory_contexts(
                topic_memories,
                max_chars_per_snippet=settings.rag_max_chars_per_snippet,
            ) + retrieved_contexts
        except Exception as err:
            topic_memory_error = str(err)[:500]
            topic_memories = []
    topic_memory_quality_scores = _topic_memory_quality_scores(topic_memories)
    provider_start = perf_counter()
    report, used_by_model = await build_report_with_provider(
        request=request,
        effective_style_mode=effective_style_mode,
        style_mode_source=style_mode_source,
        settings=settings,
        retrieved_contexts=retrieved_contexts,
        build_report_with_openai_fn=build_report_with_openai_fn,
        build_mock_report_fn=build_mock_report_fn,
    )
    provider_elapsed_ms = (perf_counter() - provider_start) * 1000.0
    apply_rag_payload_fields(
        report,
        settings,
        retrieved_contexts,
        used_by_model=used_by_model,
        requested_backend=rag_result.requested_backend,
        effective_backend=rag_result.effective_backend,
        backend_fallback_reason=rag_result.backend_fallback_reason,
    )

    total_elapsed_ms = (perf_counter() - overall_start) * 1000.0
    error_codes = _collect_runtime_error_codes(
        settings=settings,
        rag_result=rag_result,
        report=report,
        topic_memory_error=topic_memory_error,
    )
    degradation_level = _resolve_degradation_level(
        settings=settings,
        rag_result=rag_result,
        report=report,
        topic_memory_error=topic_memory_error,
    )
    report.payload["judgeTrace"] = {
        "traceId": trace_id,
        "pipelineVersion": "multi-agent-v2",
        "graphV2Enabled": settings.graph_v2_enabled,
        "reflectionEnabled": settings.reflection_enabled,
        "degradationLevel": degradation_level,
        "timingsMs": {
            "ragRetrieve": round(rag_elapsed_ms, 2),
            "provider": round(provider_elapsed_ms, 2),
            "total": round(total_elapsed_ms, 2),
        },
        "fallback": {
            "ragBackendFallbackReason": rag_result.backend_fallback_reason,
            "topicMemoryError": topic_memory_error,
            "providerFallbackFrom": report.payload.get("fallbackFrom"),
            "providerFallbackReason": report.payload.get("fallbackReason"),
        },
        "errorCodes": error_codes,
    }
    report.payload["retrievalDiagnostics"] = {
        "profile": retrieval_profile,
        "profileResolved": rag_result.retrieval_diagnostics.get("profileResolved"),
        "profileFallbackReason": rag_result.retrieval_diagnostics.get("profileFallbackReason"),
        "hybridEnabled": settings.rag_hybrid_enabled,
        "rerankEnabled": settings.rag_rerank_enabled,
        "topicMemoryEnabled": settings.topic_memory_enabled,
        "topicMemoryReuseCount": len(topic_memories),
        "topicMemoryError": topic_memory_error,
        "topicMemoryFaultInjected": "topic_memory_unavailable" in injected and bool(topic_memory_error),
        "topicMemoryAvgQualityScore": (
            round(sum(topic_memory_quality_scores) / len(topic_memory_quality_scores), 4)
            if topic_memory_quality_scores
            else None
        ),
        "requestedBackend": rag_result.requested_backend,
        "effectiveBackend": rag_result.effective_backend,
        "snippetCount": len(retrieved_contexts),
        "sourceCount": len(report.payload.get("ragSources", [])),
        "ragRetriever": rag_result.retrieval_diagnostics,
    }
    retrieval_snapshot = _build_retrieval_snapshot(retrieved_contexts)
    prompt_hash = _build_prompt_hash(
        request=request,
        effective_style_mode=effective_style_mode,
        retrieved_contexts=retrieved_contexts,
    )
    report.payload["judgeAudit"] = {
        "traceId": trace_id,
        "promptHash": prompt_hash,
        "provider": report.payload.get("provider"),
        "model": report.payload.get("model"),
        "rubricVersion": request.rubric_version,
        "judgePolicyVersion": getattr(request, "judge_policy_version", "v2-default"),
        "retrievalProfile": retrieval_profile,
        "retrievalSnapshot": retrieval_snapshot,
        "degradationLevel": degradation_level,
    }
    report.payload["errorCodes"] = error_codes
    report.payload["topicMemory"] = {
        "enabled": settings.topic_memory_enabled,
        "topicDomain": getattr(request, "topic_domain", "default"),
        "rubricVersion": request.rubric_version,
        "reuseCount": len(topic_memories),
        "jobIds": [row.job_id for row in topic_memories],
        "qualityScores": topic_memory_quality_scores,
    }
    report.payload["evidenceRefs"] = _normalize_evidence_refs(report)
    report.payload["consistency"] = {
        "winnerFirst": report.winner_first,
        "winnerSecond": report.winner_second,
        "rejudgeTriggered": report.rejudge_triggered,
    }
    report.payload["cost"] = {
        "tokenUsage": report.payload.get("tokenUsage"),
        "costEstimate": report.payload.get("costEstimate"),
    }
    return report
