import asyncio

from fastapi import FastAPI, Header, HTTPException

from .callback_client import callback_failed, callback_report
from .dispatch_controller import process_dispatch_request
from .models import JudgeDispatchRequest
from .openai_judge import OpenAiJudgeConfig, build_report_with_openai
from .rag_retriever import (
    RAG_BACKEND_MILVUS,
    RagMilvusConfig,
    retrieve_contexts,
    summarize_retrieved_contexts,
)
from .runtime_policy import PROVIDER_OPENAI, should_use_openai
from .scoring import build_report
from .settings import (
    build_callback_client_config,
    build_dispatch_runtime_config,
    load_settings,
)


SETTINGS = load_settings()
app = FastAPI(title="AI Judge Service", version="0.2.0")
CALLBACK_CFG = build_callback_client_config(SETTINGS)
DISPATCH_RUNTIME_CFG = build_dispatch_runtime_config(SETTINGS)


def _require_internal_key(header_value: str | None) -> None:
    if not header_value:
        raise HTTPException(status_code=401, detail="missing x-ai-internal-key")
    if header_value.strip() != SETTINGS.ai_internal_key:
        raise HTTPException(status_code=401, detail="invalid x-ai-internal-key")


async def _build_report_by_runtime(
    request: JudgeDispatchRequest,
    effective_style_mode: str,
    style_mode_source: str,
):
    milvus_config: RagMilvusConfig | None = None
    if (
        SETTINGS.rag_backend == RAG_BACKEND_MILVUS
        and SETTINGS.rag_milvus_uri.strip()
        and SETTINGS.rag_milvus_collection.strip()
    ):
        milvus_config = RagMilvusConfig(
            uri=SETTINGS.rag_milvus_uri,
            token=SETTINGS.rag_milvus_token,
            db_name=SETTINGS.rag_milvus_db_name,
            collection=SETTINGS.rag_milvus_collection,
            vector_field=SETTINGS.rag_milvus_vector_field,
            content_field=SETTINGS.rag_milvus_content_field,
            title_field=SETTINGS.rag_milvus_title_field,
            source_url_field=SETTINGS.rag_milvus_source_url_field,
            chunk_id_field=SETTINGS.rag_milvus_chunk_id_field,
            tags_field=SETTINGS.rag_milvus_tags_field,
            metric_type=SETTINGS.rag_milvus_metric_type,
            search_limit=SETTINGS.rag_milvus_search_limit,
        )

    retrieved_contexts = retrieve_contexts(
        request,
        enabled=SETTINGS.rag_enabled,
        knowledge_file=SETTINGS.rag_knowledge_file,
        max_snippets=SETTINGS.rag_max_snippets,
        max_chars_per_snippet=SETTINGS.rag_max_chars_per_snippet,
        query_message_limit=SETTINGS.rag_query_message_limit,
        allowed_source_prefixes=SETTINGS.rag_source_whitelist,
        backend=SETTINGS.rag_backend,
        milvus_config=milvus_config,
        openai_api_key=SETTINGS.openai_api_key,
        openai_base_url=SETTINGS.openai_base_url,
        openai_embedding_model=SETTINGS.rag_openai_embedding_model,
        openai_timeout_secs=SETTINGS.openai_timeout_secs,
    )

    def apply_rag_payload_fields(report, *, used_by_model: bool) -> None:
        report.payload["ragEnabled"] = SETTINGS.rag_enabled
        report.payload["ragBackend"] = SETTINGS.rag_backend
        report.payload["ragUsedByModel"] = used_by_model and bool(retrieved_contexts)
        report.payload["ragSnippetCount"] = len(retrieved_contexts)
        report.payload["ragSources"] = summarize_retrieved_contexts(retrieved_contexts)
        report.payload["ragSourceWhitelist"] = list(SETTINGS.rag_source_whitelist)

    if should_use_openai(SETTINGS.provider, SETTINGS.openai_api_key):
        cfg = OpenAiJudgeConfig(
            api_key=SETTINGS.openai_api_key,
            model=SETTINGS.openai_model,
            base_url=SETTINGS.openai_base_url,
            timeout_secs=SETTINGS.openai_timeout_secs,
            temperature=SETTINGS.openai_temperature,
            max_retries=SETTINGS.openai_max_retries,
            max_stage_agent_chunks=SETTINGS.stage_agent_max_chunks,
        )
        try:
            report = await build_report_with_openai(
                request=request,
                effective_style_mode=effective_style_mode,
                style_mode_source=style_mode_source,
                cfg=cfg,
                retrieved_contexts=retrieved_contexts,
            )
        except Exception as err:
            if not SETTINGS.openai_fallback_to_mock:
                raise RuntimeError(f"openai runtime failed: {err}") from err
            report = build_report(request, system_style_mode=SETTINGS.judge_style_mode)
            report.payload["provider"] = "ai-judge-service-mock-fallback"
            report.payload["fallbackFrom"] = "openai"
            report.payload["fallbackReason"] = str(err)[:500]
            apply_rag_payload_fields(report, used_by_model=False)
            return report
        apply_rag_payload_fields(report, used_by_model=True)
        return report

    report = build_report(request, system_style_mode=SETTINGS.judge_style_mode)
    if SETTINGS.provider == PROVIDER_OPENAI and not SETTINGS.openai_api_key.strip():
        report.payload["provider"] = "ai-judge-service-mock-missing-openai-key"
        report.payload["fallbackFrom"] = "openai"
        report.payload["fallbackReason"] = "missing OPENAI_API_KEY"
    apply_rag_payload_fields(report, used_by_model=False)
    return report


@app.get("/healthz")
async def healthz() -> dict[str, bool]:
    return {"ok": True}


@app.post("/internal/judge/dispatch")
async def dispatch_judge_job(
    request: JudgeDispatchRequest,
    x_ai_internal_key: str | None = Header(default=None),
) -> dict:
    _require_internal_key(x_ai_internal_key)
    return await process_dispatch_request(
        request=request,
        runtime_cfg=DISPATCH_RUNTIME_CFG,
        build_report_by_runtime=_build_report_by_runtime,
        callback_report=lambda job_id, payload: callback_report(
            cfg=CALLBACK_CFG,
            job_id=job_id,
            payload=payload,
        ),
        callback_failed=lambda job_id, error_message: callback_failed(
            cfg=CALLBACK_CFG,
            job_id=job_id,
            error_message=error_message,
        ),
        sleep_fn=asyncio.sleep,
    )
