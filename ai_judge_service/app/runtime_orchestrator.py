from __future__ import annotations

from typing import Awaitable, Callable

from .models import JudgeDispatchRequest, SubmitJudgeReportInput
from .openai_judge import OpenAiJudgeConfig, build_report_with_openai
from .rag_retriever import (
    RAG_BACKEND_MILVUS,
    RagMilvusConfig,
    RetrievedContext,
    retrieve_contexts,
    summarize_retrieved_contexts,
)
from .runtime_policy import PROVIDER_OPENAI, should_use_openai
from .scoring import build_report
from .settings import Settings

RetrieveContextsFn = Callable[..., list[RetrievedContext]]
BuildOpenAiReportFn = Callable[..., Awaitable[SubmitJudgeReportInput]]
BuildMockReportFn = Callable[..., SubmitJudgeReportInput]


def _build_milvus_config(settings: Settings) -> RagMilvusConfig | None:
    if (
        settings.rag_backend != RAG_BACKEND_MILVUS
        or not settings.rag_milvus_uri.strip()
        or not settings.rag_milvus_collection.strip()
    ):
        return None
    return RagMilvusConfig(
        uri=settings.rag_milvus_uri,
        token=settings.rag_milvus_token,
        db_name=settings.rag_milvus_db_name,
        collection=settings.rag_milvus_collection,
        vector_field=settings.rag_milvus_vector_field,
        content_field=settings.rag_milvus_content_field,
        title_field=settings.rag_milvus_title_field,
        source_url_field=settings.rag_milvus_source_url_field,
        chunk_id_field=settings.rag_milvus_chunk_id_field,
        tags_field=settings.rag_milvus_tags_field,
        metric_type=settings.rag_milvus_metric_type,
        search_limit=settings.rag_milvus_search_limit,
    )


def _apply_rag_payload_fields(
    report: SubmitJudgeReportInput,
    settings: Settings,
    retrieved_contexts: list[RetrievedContext],
    *,
    used_by_model: bool,
) -> None:
    report.payload["ragEnabled"] = settings.rag_enabled
    report.payload["ragBackend"] = settings.rag_backend
    report.payload["ragUsedByModel"] = used_by_model and bool(retrieved_contexts)
    report.payload["ragSnippetCount"] = len(retrieved_contexts)
    report.payload["ragSources"] = summarize_retrieved_contexts(retrieved_contexts)
    report.payload["ragSourceWhitelist"] = list(settings.rag_source_whitelist)


async def build_report_by_runtime(
    *,
    request: JudgeDispatchRequest,
    effective_style_mode: str,
    style_mode_source: str,
    settings: Settings,
    retrieve_contexts_fn: RetrieveContextsFn = retrieve_contexts,
    build_report_with_openai_fn: BuildOpenAiReportFn = build_report_with_openai,
    build_mock_report_fn: BuildMockReportFn = build_report,
) -> SubmitJudgeReportInput:
    retrieved_contexts = retrieve_contexts_fn(
        request,
        enabled=settings.rag_enabled,
        knowledge_file=settings.rag_knowledge_file,
        max_snippets=settings.rag_max_snippets,
        max_chars_per_snippet=settings.rag_max_chars_per_snippet,
        query_message_limit=settings.rag_query_message_limit,
        allowed_source_prefixes=settings.rag_source_whitelist,
        backend=settings.rag_backend,
        milvus_config=_build_milvus_config(settings),
        openai_api_key=settings.openai_api_key,
        openai_base_url=settings.openai_base_url,
        openai_embedding_model=settings.rag_openai_embedding_model,
        openai_timeout_secs=settings.openai_timeout_secs,
    )

    if should_use_openai(settings.provider, settings.openai_api_key):
        cfg = OpenAiJudgeConfig(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
            timeout_secs=settings.openai_timeout_secs,
            temperature=settings.openai_temperature,
            max_retries=settings.openai_max_retries,
            max_stage_agent_chunks=settings.stage_agent_max_chunks,
        )
        try:
            report = await build_report_with_openai_fn(
                request=request,
                effective_style_mode=effective_style_mode,
                style_mode_source=style_mode_source,
                cfg=cfg,
                retrieved_contexts=retrieved_contexts,
            )
        except Exception as err:
            if not settings.openai_fallback_to_mock:
                raise RuntimeError(f"openai runtime failed: {err}") from err
            report = build_mock_report_fn(
                request,
                system_style_mode=settings.judge_style_mode,
            )
            report.payload["provider"] = "ai-judge-service-mock-fallback"
            report.payload["fallbackFrom"] = "openai"
            report.payload["fallbackReason"] = str(err)[:500]
            _apply_rag_payload_fields(
                report,
                settings,
                retrieved_contexts,
                used_by_model=False,
            )
            return report
        _apply_rag_payload_fields(
            report,
            settings,
            retrieved_contexts,
            used_by_model=True,
        )
        return report

    report = build_mock_report_fn(
        request,
        system_style_mode=settings.judge_style_mode,
    )
    if settings.provider == PROVIDER_OPENAI and not settings.openai_api_key.strip():
        report.payload["provider"] = "ai-judge-service-mock-missing-openai-key"
        report.payload["fallbackFrom"] = "openai"
        report.payload["fallbackReason"] = "missing OPENAI_API_KEY"
    _apply_rag_payload_fields(
        report,
        settings,
        retrieved_contexts,
        used_by_model=False,
    )
    return report
