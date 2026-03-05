from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .models import JudgeDispatchRequest, SubmitJudgeReportInput
from .rag_profiles import DEFAULT_RETRIEVAL_PROFILE, resolve_retrieval_profile
from .rag_retriever import (
    RAG_BACKEND_FILE,
    RAG_BACKEND_MILVUS,
    RagMilvusConfig,
    RetrievedContext,
    retrieve_contexts,
    summarize_retrieved_contexts,
)
from .settings import Settings

RetrieveContextsFn = Callable[..., list[RetrievedContext]]


@dataclass(frozen=True)
class RuntimeRagResult:
    retrieved_contexts: list[RetrievedContext]
    requested_backend: str
    effective_backend: str
    backend_fallback_reason: str | None
    retrieval_diagnostics: dict[str, Any]


def build_milvus_config(settings: Settings) -> RagMilvusConfig | None:
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


def resolve_effective_rag_backend(
    settings: Settings,
    milvus_config: RagMilvusConfig | None,
) -> tuple[str, str | None]:
    requested = settings.rag_backend
    if requested != RAG_BACKEND_MILVUS:
        return requested, None

    if milvus_config is None:
        return RAG_BACKEND_FILE, "milvus_config_missing"

    if not settings.openai_api_key.strip():
        return RAG_BACKEND_FILE, "missing_openai_api_key_for_milvus_embedding"

    return RAG_BACKEND_MILVUS, None


def retrieve_runtime_contexts_with_meta(
    *,
    request: JudgeDispatchRequest,
    settings: Settings,
    retrieve_contexts_fn: RetrieveContextsFn = retrieve_contexts,
) -> RuntimeRagResult:
    profile_requested = str(
        getattr(request, "retrieval_profile", DEFAULT_RETRIEVAL_PROFILE)
        or DEFAULT_RETRIEVAL_PROFILE
    )
    profile, profile_fallback_reason = resolve_retrieval_profile(profile_requested)
    effective_hybrid_enabled = settings.rag_hybrid_enabled and profile.hybrid_enabled
    effective_rerank_enabled = settings.rag_rerank_enabled and profile.rerank_enabled
    milvus_config = build_milvus_config(settings)
    effective_backend, backend_fallback_reason = resolve_effective_rag_backend(
        settings,
        milvus_config,
    )
    retrieve_kwargs: dict[str, Any] = {
        "enabled": settings.rag_enabled,
        "knowledge_file": settings.rag_knowledge_file,
        "max_snippets": settings.rag_max_snippets,
        "max_chars_per_snippet": settings.rag_max_chars_per_snippet,
        "query_message_limit": settings.rag_query_message_limit,
        "allowed_source_prefixes": settings.rag_source_whitelist,
        "backend": effective_backend,
        "milvus_config": milvus_config if effective_backend == RAG_BACKEND_MILVUS else None,
        "openai_api_key": settings.openai_api_key,
        "openai_base_url": settings.openai_base_url,
        "openai_embedding_model": settings.rag_openai_embedding_model,
        "openai_timeout_secs": settings.openai_timeout_secs,
        "hybrid_enabled": effective_hybrid_enabled,
        "rerank_enabled": effective_rerank_enabled,
        "hybrid_rrf_k": profile.hybrid_rrf_k,
        "hybrid_vector_limit_multiplier": profile.hybrid_vector_limit_multiplier,
        "hybrid_lexical_limit_multiplier": profile.hybrid_lexical_limit_multiplier,
        "rerank_query_weight": profile.rerank_query_weight,
        "rerank_base_weight": profile.rerank_base_weight,
    }
    retrieval_diagnostics: dict[str, Any] = {}
    retrieve_kwargs["diagnostics"] = retrieval_diagnostics
    try:
        retrieved_contexts = retrieve_contexts_fn(
            request,
            **retrieve_kwargs,
        )
    except TypeError:
        retrieve_kwargs.pop("hybrid_enabled", None)
        retrieve_kwargs.pop("rerank_enabled", None)
        retrieve_kwargs.pop("hybrid_rrf_k", None)
        retrieve_kwargs.pop("hybrid_vector_limit_multiplier", None)
        retrieve_kwargs.pop("hybrid_lexical_limit_multiplier", None)
        retrieve_kwargs.pop("rerank_query_weight", None)
        retrieve_kwargs.pop("rerank_base_weight", None)
        retrieve_kwargs.pop("diagnostics", None)
        retrieved_contexts = retrieve_contexts_fn(
            request,
            **retrieve_kwargs,
        )
    retrieval_diagnostics.setdefault("profileRequested", profile_requested)
    retrieval_diagnostics.setdefault("profileResolved", profile.name)
    retrieval_diagnostics.setdefault("profileFallbackReason", profile_fallback_reason)
    retrieval_diagnostics.setdefault("hybridEnabledBySettings", settings.rag_hybrid_enabled)
    retrieval_diagnostics.setdefault("rerankEnabledBySettings", settings.rag_rerank_enabled)
    retrieval_diagnostics.setdefault("hybridEnabledEffective", effective_hybrid_enabled)
    retrieval_diagnostics.setdefault("rerankEnabledEffective", effective_rerank_enabled)
    retrieval_diagnostics.setdefault(
        "profileTuning",
        {
            "rrfK": profile.hybrid_rrf_k,
            "vectorLimitMultiplier": profile.hybrid_vector_limit_multiplier,
            "lexicalLimitMultiplier": profile.hybrid_lexical_limit_multiplier,
            "rerankQueryWeight": profile.rerank_query_weight,
            "rerankBaseWeight": profile.rerank_base_weight,
        },
    )
    return RuntimeRagResult(
        retrieved_contexts=retrieved_contexts,
        requested_backend=settings.rag_backend,
        effective_backend=effective_backend,
        backend_fallback_reason=backend_fallback_reason,
        retrieval_diagnostics=retrieval_diagnostics,
    )


def retrieve_runtime_contexts(
    *,
    request: JudgeDispatchRequest,
    settings: Settings,
    retrieve_contexts_fn: RetrieveContextsFn = retrieve_contexts,
) -> list[RetrievedContext]:
    return retrieve_runtime_contexts_with_meta(
        request=request,
        settings=settings,
        retrieve_contexts_fn=retrieve_contexts_fn,
    ).retrieved_contexts


def apply_rag_payload_fields(
    report: SubmitJudgeReportInput,
    settings: Settings,
    retrieved_contexts: list[RetrievedContext],
    *,
    used_by_model: bool,
    requested_backend: str | None = None,
    effective_backend: str | None = None,
    backend_fallback_reason: str | None = None,
) -> None:
    report.payload["ragEnabled"] = settings.rag_enabled
    report.payload["ragBackend"] = effective_backend or settings.rag_backend
    report.payload["ragRequestedBackend"] = requested_backend or settings.rag_backend
    if backend_fallback_reason:
        report.payload["ragBackendFallbackReason"] = backend_fallback_reason
    report.payload["ragUsedByModel"] = used_by_model and bool(retrieved_contexts)
    report.payload["ragSnippetCount"] = len(retrieved_contexts)
    report.payload["ragSources"] = summarize_retrieved_contexts(retrieved_contexts)
    report.payload["ragSourceWhitelist"] = list(settings.rag_source_whitelist)
