from __future__ import annotations

from time import perf_counter
from typing import TYPE_CHECKING, Awaitable, Callable

from .models import JudgeDispatchRequest, SubmitJudgeReportInput
from .openai_judge import build_report_with_openai
from .rag_retriever import RetrievedContext, retrieve_contexts
from .runtime_provider import build_report_with_provider
from .runtime_rag import (
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


def _resolve_degradation_level(
    *,
    settings: Settings,
    rag_backend_fallback_reason: str | None,
    report: SubmitJudgeReportInput,
) -> int:
    level = 0
    if rag_backend_fallback_reason:
        level = max(level, 1)
    if settings.rag_enabled and not report.payload.get("ragUsedByModel", False):
        level = max(level, 2)
    if report.payload.get("fallbackFrom") == "openai":
        level = max(level, 3)
    return min(level, settings.degrade_max_level)


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
    overall_start = perf_counter()
    rag_start = perf_counter()
    rag_result = retrieve_runtime_contexts_with_meta(
        request=request,
        settings=settings,
        retrieve_contexts_fn=retrieve_contexts_fn,
    )
    rag_elapsed_ms = (perf_counter() - rag_start) * 1000.0
    retrieved_contexts = list(rag_result.retrieved_contexts)
    topic_memories: list["TopicMemoryRecord"] = []
    if settings.topic_memory_enabled and trace_store is not None:
        topic_memories = trace_store.list_topic_memory(
            topic_domain=getattr(request, "topic_domain", "default"),
            rubric_version=request.rubric_version,
            limit=settings.topic_memory_limit,
        )
        retrieved_contexts = _build_topic_memory_contexts(
            topic_memories,
            max_chars_per_snippet=settings.rag_max_chars_per_snippet,
        ) + retrieved_contexts
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
    degradation_level = _resolve_degradation_level(
        settings=settings,
        rag_backend_fallback_reason=rag_result.backend_fallback_reason,
        report=report,
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
            "providerFallbackFrom": report.payload.get("fallbackFrom"),
            "providerFallbackReason": report.payload.get("fallbackReason"),
        },
    }
    report.payload["retrievalDiagnostics"] = {
        "profile": retrieval_profile,
        "hybridEnabled": settings.rag_hybrid_enabled,
        "rerankEnabled": settings.rag_rerank_enabled,
        "topicMemoryEnabled": settings.topic_memory_enabled,
        "topicMemoryReuseCount": len(topic_memories),
        "requestedBackend": rag_result.requested_backend,
        "effectiveBackend": rag_result.effective_backend,
        "snippetCount": len(retrieved_contexts),
        "sourceCount": len(report.payload.get("ragSources", [])),
    }
    report.payload["topicMemory"] = {
        "enabled": settings.topic_memory_enabled,
        "topicDomain": getattr(request, "topic_domain", "default"),
        "rubricVersion": request.rubric_version,
        "reuseCount": len(topic_memories),
        "jobIds": [row.job_id for row in topic_memories],
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
