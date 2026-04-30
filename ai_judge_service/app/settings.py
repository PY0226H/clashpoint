from __future__ import annotations

import os
from dataclasses import dataclass

from .callback_client import CallbackClientConfig
from .lexical_retriever import (
    DEFAULT_BM25_CACHE_DIR,
    DEFAULT_LEXICAL_ENGINE,
    VALID_LEXICAL_ENGINES,
    normalize_lexical_engine,
)
from .rag_retriever import parse_rag_backend, parse_source_whitelist
from .reranker_engine import (
    DEFAULT_BGE_MODEL,
    VALID_RERANK_DEVICES,
    VALID_RERANK_ENGINES,
    normalize_rerank_device,
    normalize_rerank_engine,
)
from .runtime_policy import (
    PROVIDER_MOCK,
    PROVIDER_OPENAI,
    is_production_env,
    normalize_provider,
    parse_env_bool,
    runtime_env_label,
)
from .runtime_types import DispatchRuntimeConfig

DEFAULT_RAG_SOURCE_WHITELIST = "https://teamfighttactics.leagueoflegends.com/en-us/news/"
DEFAULT_REFLECTION_POLICY = "winner_mismatch_only"
VALID_REFLECTION_POLICIES = {
    "winner_mismatch_only",
    "winner_mismatch_or_low_margin",
}
VALID_FAULT_INJECTION_NODES = {
    "provider_timeout",
    "provider_overload",
    "rag_retrieve_timeout",
    "rag_retrieve_unavailable",
    "topic_memory_unavailable",
    "stage_judge",
    "aggregate",
    "final_pass_1",
    "final_pass_2",
    "display",
}
ARTIFACT_STORE_PROVIDER_LOCAL = "local"
ARTIFACT_STORE_PROVIDER_S3_COMPATIBLE = "s3_compatible"
VALID_ARTIFACT_STORE_PROVIDERS = {
    ARTIFACT_STORE_PROVIDER_LOCAL,
    ARTIFACT_STORE_PROVIDER_S3_COMPATIBLE,
}


def parse_csv_items(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    items: list[str] = []
    seen: set[str] = set()
    normalized = value.replace(";", ",").replace("\n", ",")
    for raw in normalized.split(","):
        item = raw.strip().lower()
        if not item or item in seen:
            continue
        seen.add(item)
        items.append(item)
    return tuple(items)


def normalize_artifact_store_provider(value: str | None) -> str:
    token = str(value or "").strip().lower().replace("-", "_")
    if not token:
        return ARTIFACT_STORE_PROVIDER_LOCAL
    if token in {"s3", "minio", "s3_compatible"}:
        return ARTIFACT_STORE_PROVIDER_S3_COMPATIBLE
    return token


@dataclass(frozen=True)
class Settings:
    ai_internal_key: str
    chat_server_base_url: str
    phase_report_path_template: str
    final_report_path_template: str
    phase_failed_path_template: str
    final_failed_path_template: str
    callback_timeout_secs: float
    process_delay_ms: int
    judge_style_mode: str
    provider: str
    openai_api_key: str
    openai_model: str
    openai_base_url: str
    openai_timeout_secs: float
    openai_temperature: float
    openai_max_retries: int
    openai_fallback_to_mock: bool
    rag_enabled: bool
    rag_knowledge_file: str
    rag_max_snippets: int
    rag_max_chars_per_snippet: int
    rag_query_message_limit: int
    rag_source_whitelist: tuple[str, ...]
    rag_backend: str
    rag_openai_embedding_model: str
    rag_milvus_uri: str
    rag_milvus_token: str
    rag_milvus_db_name: str
    rag_milvus_collection: str
    rag_milvus_vector_field: str
    rag_milvus_content_field: str
    rag_milvus_title_field: str
    rag_milvus_source_url_field: str
    rag_milvus_chunk_id_field: str
    rag_milvus_tags_field: str
    rag_milvus_metric_type: str
    rag_milvus_search_limit: int
    stage_agent_max_chunks: int
    reflection_enabled: bool
    topic_memory_enabled: bool
    rag_hybrid_enabled: bool
    rag_rerank_enabled: bool
    reflection_policy: str
    reflection_low_margin_threshold: int
    fault_injection_nodes: tuple[str, ...]
    degrade_max_level: int
    trace_ttl_secs: int
    idempotency_ttl_secs: int
    redis_enabled: bool
    redis_required: bool
    redis_url: str
    redis_pool_size: int
    redis_key_prefix: str
    db_url: str
    db_echo: bool
    db_pool_size: int
    db_max_overflow: int
    db_auto_create_schema: bool
    topic_memory_limit: int
    topic_memory_min_evidence_refs: int
    topic_memory_min_rationale_chars: int
    topic_memory_min_quality_score: float
    artifact_store_provider: str = ARTIFACT_STORE_PROVIDER_LOCAL
    artifact_store_root: str = "artifacts/ai_judge_service"
    artifact_store_bucket: str = ""
    artifact_store_prefix: str = "ai_judge_service"
    artifact_store_endpoint_url: str = ""
    artifact_store_region: str = ""
    artifact_store_force_path_style: bool = False
    artifact_store_healthcheck_enabled: bool = False
    tokenizer_fallback_encoding: str = "o200k_base"
    phase_prompt_max_tokens: int = 3200
    agent2_prompt_max_tokens: int = 3600
    rag_query_max_tokens: int = 1600
    rag_snippet_max_tokens: int = 180
    embed_input_max_tokens: int = 2000
    runtime_retry_max_attempts: int = 2
    runtime_retry_backoff_ms: int = 200
    compliance_block_enabled: bool = True
    rag_lexical_engine: str = DEFAULT_LEXICAL_ENGINE
    rag_bm25_cache_dir: str = DEFAULT_BM25_CACHE_DIR
    rag_bm25_use_disk_cache: bool = True
    rag_bm25_fallback_to_simple: bool = True
    rag_rerank_engine: str = "bge"
    rag_rerank_model: str = DEFAULT_BGE_MODEL
    rag_rerank_batch_size: int = 16
    rag_rerank_candidate_cap: int = 50
    rag_rerank_timeout_ms: int = 12000
    rag_rerank_device: str = "cpu"
    policy_registry_default_version: str = "v3-default"
    policy_registry_json: str = ""
    prompt_registry_default_version: str = "promptset-v3-default"
    prompt_registry_json: str = ""
    tool_registry_default_version: str = "toolset-v3-default"
    tool_registry_json: str = ""
    assistant_advisory_placeholder_enabled: bool = False


def load_settings() -> Settings:
    provider = normalize_provider(os.getenv("AI_JUDGE_PROVIDER"))
    settings = Settings(
        ai_internal_key=os.getenv("AI_JUDGE_INTERNAL_KEY", "dev-ai-internal-key"),
        chat_server_base_url=os.getenv("CHAT_SERVER_BASE_URL", "http://127.0.0.1:6688"),
        phase_report_path_template=os.getenv(
            "CHAT_SERVER_PHASE_REPORT_PATH_TEMPLATE",
            "/api/internal/ai/judge/v3/phase/cases/{case_id}/report",
        ),
        final_report_path_template=os.getenv(
            "CHAT_SERVER_FINAL_REPORT_PATH_TEMPLATE",
            "/api/internal/ai/judge/v3/final/cases/{case_id}/report",
        ),
        phase_failed_path_template=os.getenv(
            "CHAT_SERVER_PHASE_FAILED_PATH_TEMPLATE",
            "/api/internal/ai/judge/v3/phase/cases/{case_id}/failed",
        ),
        final_failed_path_template=os.getenv(
            "CHAT_SERVER_FINAL_FAILED_PATH_TEMPLATE",
            "/api/internal/ai/judge/v3/final/cases/{case_id}/failed",
        ),
        callback_timeout_secs=float(os.getenv("CALLBACK_TIMEOUT_SECONDS", "8")),
        process_delay_ms=int(os.getenv("JUDGE_PROCESS_DELAY_MS", "0")),
        judge_style_mode=os.getenv("JUDGE_STYLE_MODE", "rational"),
        provider=provider,
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("AI_JUDGE_OPENAI_MODEL", "gpt-4.1-mini"),
        openai_base_url=os.getenv("AI_JUDGE_OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip(
            "/"
        ),
        openai_timeout_secs=float(os.getenv("AI_JUDGE_OPENAI_TIMEOUT_SECONDS", "25")),
        openai_temperature=float(os.getenv("AI_JUDGE_OPENAI_TEMPERATURE", "0.1")),
        openai_max_retries=int(os.getenv("AI_JUDGE_OPENAI_MAX_RETRIES", "2")),
        openai_fallback_to_mock=parse_env_bool(
            os.getenv("AI_JUDGE_OPENAI_FALLBACK_TO_MOCK"),
            default=False,
        ),
        rag_enabled=parse_env_bool(os.getenv("AI_JUDGE_RAG_ENABLED"), default=True),
        rag_knowledge_file=os.getenv("AI_JUDGE_RAG_KNOWLEDGE_FILE", ""),
        rag_max_snippets=int(os.getenv("AI_JUDGE_RAG_MAX_SNIPPETS", "4")),
        rag_max_chars_per_snippet=int(os.getenv("AI_JUDGE_RAG_MAX_CHARS_PER_SNIPPET", "280")),
        rag_query_message_limit=int(os.getenv("AI_JUDGE_RAG_QUERY_MESSAGE_LIMIT", "80")),
        rag_source_whitelist=parse_source_whitelist(
            os.getenv(
                "AI_JUDGE_RAG_SOURCE_WHITELIST",
                DEFAULT_RAG_SOURCE_WHITELIST,
            )
        ),
        rag_backend=parse_rag_backend(os.getenv("AI_JUDGE_RAG_BACKEND", "file")),
        rag_openai_embedding_model=os.getenv(
            "AI_JUDGE_RAG_OPENAI_EMBEDDING_MODEL",
            "text-embedding-3-small",
        ),
        rag_milvus_uri=os.getenv("AI_JUDGE_RAG_MILVUS_URI", ""),
        rag_milvus_token=os.getenv("AI_JUDGE_RAG_MILVUS_TOKEN", ""),
        rag_milvus_db_name=os.getenv("AI_JUDGE_RAG_MILVUS_DB_NAME", ""),
        rag_milvus_collection=os.getenv("AI_JUDGE_RAG_MILVUS_COLLECTION", ""),
        rag_milvus_vector_field=os.getenv("AI_JUDGE_RAG_MILVUS_VECTOR_FIELD", "embedding"),
        rag_milvus_content_field=os.getenv("AI_JUDGE_RAG_MILVUS_CONTENT_FIELD", "content"),
        rag_milvus_title_field=os.getenv("AI_JUDGE_RAG_MILVUS_TITLE_FIELD", "title"),
        rag_milvus_source_url_field=os.getenv(
            "AI_JUDGE_RAG_MILVUS_SOURCE_URL_FIELD",
            "source_url",
        ),
        rag_milvus_chunk_id_field=os.getenv("AI_JUDGE_RAG_MILVUS_CHUNK_ID_FIELD", "chunk_id"),
        rag_milvus_tags_field=os.getenv("AI_JUDGE_RAG_MILVUS_TAGS_FIELD", "tags"),
        rag_milvus_metric_type=os.getenv("AI_JUDGE_RAG_MILVUS_METRIC_TYPE", "COSINE"),
        rag_milvus_search_limit=int(os.getenv("AI_JUDGE_RAG_MILVUS_SEARCH_LIMIT", "20")),
        stage_agent_max_chunks=int(os.getenv("AI_JUDGE_STAGE_AGENT_MAX_CHUNKS", "12")),
        reflection_enabled=parse_env_bool(os.getenv("AI_JUDGE_REFLECTION_ENABLED"), default=True),
        topic_memory_enabled=parse_env_bool(
            os.getenv("AI_JUDGE_TOPIC_MEMORY_ENABLED"), default=True
        ),
        rag_hybrid_enabled=parse_env_bool(os.getenv("AI_JUDGE_RAG_HYBRID_ENABLED"), default=True),
        rag_rerank_enabled=parse_env_bool(os.getenv("AI_JUDGE_RAG_RERANK_ENABLED"), default=True),
        reflection_policy=os.getenv(
            "AI_JUDGE_REFLECTION_POLICY",
            DEFAULT_REFLECTION_POLICY,
        )
        .strip()
        .lower(),
        reflection_low_margin_threshold=int(
            os.getenv("AI_JUDGE_REFLECTION_LOW_MARGIN_THRESHOLD", "3")
        ),
        fault_injection_nodes=parse_csv_items(os.getenv("AI_JUDGE_FAULT_INJECTION_NODES")),
        degrade_max_level=int(os.getenv("AI_JUDGE_DEGRADE_MAX_LEVEL", "3")),
        trace_ttl_secs=int(os.getenv("AI_JUDGE_TRACE_TTL_SECS", "86400")),
        idempotency_ttl_secs=int(os.getenv("AI_JUDGE_IDEMPOTENCY_TTL_SECS", "86400")),
        redis_enabled=parse_env_bool(os.getenv("AI_JUDGE_REDIS_ENABLED"), default=False),
        redis_required=parse_env_bool(os.getenv("AI_JUDGE_REDIS_REQUIRED"), default=False),
        redis_url=os.getenv("AI_JUDGE_REDIS_URL", "redis://127.0.0.1:6379/0").strip(),
        redis_pool_size=int(os.getenv("AI_JUDGE_REDIS_POOL_SIZE", "20")),
        redis_key_prefix=os.getenv("AI_JUDGE_REDIS_KEY_PREFIX", "ai_judge:v2").strip(),
        db_url=os.getenv("AI_JUDGE_DB_URL", "sqlite+aiosqlite:///./ai_judge_service.db").strip(),
        db_echo=parse_env_bool(os.getenv("AI_JUDGE_DB_ECHO"), default=False),
        db_pool_size=int(os.getenv("AI_JUDGE_DB_POOL_SIZE", "10")),
        db_max_overflow=int(os.getenv("AI_JUDGE_DB_MAX_OVERFLOW", "20")),
        db_auto_create_schema=parse_env_bool(
            os.getenv("AI_JUDGE_DB_AUTO_CREATE_SCHEMA"),
            default=True,
        ),
        artifact_store_root=(
            os.getenv("AI_JUDGE_ARTIFACT_STORE_ROOT", "artifacts/ai_judge_service").strip()
            or "artifacts/ai_judge_service"
        ),
        artifact_store_provider=normalize_artifact_store_provider(
            os.getenv("AI_JUDGE_ARTIFACT_STORE_PROVIDER")
        ),
        artifact_store_bucket=os.getenv("AI_JUDGE_ARTIFACT_BUCKET", "").strip(),
        artifact_store_prefix=(
            os.getenv("AI_JUDGE_ARTIFACT_PREFIX", "ai_judge_service").strip()
            or "ai_judge_service"
        ),
        artifact_store_endpoint_url=os.getenv(
            "AI_JUDGE_ARTIFACT_ENDPOINT_URL",
            "",
        ).strip(),
        artifact_store_region=os.getenv("AI_JUDGE_ARTIFACT_REGION", "").strip(),
        artifact_store_force_path_style=parse_env_bool(
            os.getenv("AI_JUDGE_ARTIFACT_FORCE_PATH_STYLE"),
            default=False,
        ),
        artifact_store_healthcheck_enabled=parse_env_bool(
            os.getenv("AI_JUDGE_ARTIFACT_HEALTHCHECK_ENABLED"),
            default=False,
        ),
        topic_memory_limit=int(os.getenv("AI_JUDGE_TOPIC_MEMORY_LIMIT", "5")),
        topic_memory_min_evidence_refs=int(
            os.getenv("AI_JUDGE_TOPIC_MEMORY_MIN_EVIDENCE_REFS", "1")
        ),
        topic_memory_min_rationale_chars=int(
            os.getenv("AI_JUDGE_TOPIC_MEMORY_MIN_RATIONALE_CHARS", "20")
        ),
        topic_memory_min_quality_score=float(
            os.getenv("AI_JUDGE_TOPIC_MEMORY_MIN_QUALITY_SCORE", "0.55")
        ),
        tokenizer_fallback_encoding=os.getenv(
            "AI_JUDGE_TOKENIZER_FALLBACK_ENCODING",
            "o200k_base",
        ).strip()
        or "o200k_base",
        phase_prompt_max_tokens=int(os.getenv("AI_JUDGE_PHASE_PROMPT_MAX_TOKENS", "3200")),
        agent2_prompt_max_tokens=int(os.getenv("AI_JUDGE_AGENT2_PROMPT_MAX_TOKENS", "3600")),
        rag_query_max_tokens=int(os.getenv("AI_JUDGE_RAG_QUERY_MAX_TOKENS", "1600")),
        rag_snippet_max_tokens=int(os.getenv("AI_JUDGE_RAG_SNIPPET_MAX_TOKENS", "180")),
        embed_input_max_tokens=int(os.getenv("AI_JUDGE_EMBED_INPUT_MAX_TOKENS", "2000")),
        runtime_retry_max_attempts=int(os.getenv("AI_JUDGE_RUNTIME_RETRY_MAX_ATTEMPTS", "2")),
        runtime_retry_backoff_ms=int(os.getenv("AI_JUDGE_RUNTIME_RETRY_BACKOFF_MS", "200")),
        compliance_block_enabled=parse_env_bool(
            os.getenv("AI_JUDGE_COMPLIANCE_BLOCK_ENABLED"),
            default=True,
        ),
        rag_lexical_engine=normalize_lexical_engine(
            os.getenv("AI_JUDGE_RAG_LEXICAL_ENGINE", DEFAULT_LEXICAL_ENGINE)
        ),
        rag_bm25_cache_dir=os.getenv(
            "AI_JUDGE_RAG_BM25_CACHE_DIR",
            DEFAULT_BM25_CACHE_DIR,
        ).strip()
        or DEFAULT_BM25_CACHE_DIR,
        rag_bm25_use_disk_cache=parse_env_bool(
            os.getenv("AI_JUDGE_RAG_BM25_USE_DISK_CACHE"),
            default=True,
        ),
        rag_bm25_fallback_to_simple=parse_env_bool(
            os.getenv("AI_JUDGE_RAG_BM25_FALLBACK_TO_SIMPLE"),
            default=True,
        ),
        rag_rerank_engine=normalize_rerank_engine(os.getenv("AI_JUDGE_RAG_RERANK_ENGINE", "bge")),
        rag_rerank_model=os.getenv(
            "AI_JUDGE_RAG_RERANK_MODEL",
            DEFAULT_BGE_MODEL,
        ).strip()
        or DEFAULT_BGE_MODEL,
        rag_rerank_batch_size=int(os.getenv("AI_JUDGE_RAG_RERANK_BATCH_SIZE", "16")),
        rag_rerank_candidate_cap=int(os.getenv("AI_JUDGE_RAG_RERANK_CANDIDATE_CAP", "50")),
        rag_rerank_timeout_ms=int(os.getenv("AI_JUDGE_RAG_RERANK_TIMEOUT_MS", "12000")),
        rag_rerank_device=normalize_rerank_device(os.getenv("AI_JUDGE_RAG_RERANK_DEVICE", "cpu")),
        policy_registry_default_version=(
            os.getenv("AI_JUDGE_POLICY_REGISTRY_DEFAULT_VERSION", "v3-default").strip()
            or "v3-default"
        ),
        policy_registry_json=os.getenv("AI_JUDGE_POLICY_REGISTRY_JSON", "").strip(),
        prompt_registry_default_version=(
            os.getenv(
                "AI_JUDGE_PROMPT_REGISTRY_DEFAULT_VERSION",
                "promptset-v3-default",
            ).strip()
            or "promptset-v3-default"
        ),
        prompt_registry_json=os.getenv("AI_JUDGE_PROMPT_REGISTRY_JSON", "").strip(),
        tool_registry_default_version=(
            os.getenv(
                "AI_JUDGE_TOOL_REGISTRY_DEFAULT_VERSION",
                "toolset-v3-default",
            ).strip()
            or "toolset-v3-default"
        ),
        tool_registry_json=os.getenv("AI_JUDGE_TOOL_REGISTRY_JSON", "").strip(),
        assistant_advisory_placeholder_enabled=parse_env_bool(
            os.getenv("AI_JUDGE_ASSISTANT_ADVISORY_PLACEHOLDER_ENABLED"),
            default=False,
        ),
    )
    validate_for_runtime_env(settings, runtime_env=runtime_env_label())
    return settings


def validate_for_runtime_env(settings: Settings, runtime_env: str | None) -> None:
    if settings.reflection_policy not in VALID_REFLECTION_POLICIES:
        raise ValueError(
            "AI_JUDGE_REFLECTION_POLICY must be one of "
            f"{','.join(sorted(VALID_REFLECTION_POLICIES))}"
        )
    if (
        settings.reflection_low_margin_threshold < 0
        or settings.reflection_low_margin_threshold > 50
    ):
        raise ValueError("AI_JUDGE_REFLECTION_LOW_MARGIN_THRESHOLD must be between 0 and 50")
    invalid_fault_nodes = [
        node for node in settings.fault_injection_nodes if node not in VALID_FAULT_INJECTION_NODES
    ]
    if invalid_fault_nodes:
        raise ValueError(
            "AI_JUDGE_FAULT_INJECTION_NODES contains invalid node(s): "
            + ",".join(invalid_fault_nodes)
        )

    if settings.degrade_max_level < 0 or settings.degrade_max_level > 3:
        raise ValueError("AI_JUDGE_DEGRADE_MAX_LEVEL must be between 0 and 3")
    if settings.trace_ttl_secs < 60:
        raise ValueError("AI_JUDGE_TRACE_TTL_SECS must be >= 60")
    if settings.idempotency_ttl_secs < 60:
        raise ValueError("AI_JUDGE_IDEMPOTENCY_TTL_SECS must be >= 60")
    if settings.redis_pool_size < 1:
        raise ValueError("AI_JUDGE_REDIS_POOL_SIZE must be >= 1")
    if not settings.db_url.strip():
        raise ValueError("AI_JUDGE_DB_URL cannot be empty")
    if not settings.artifact_store_root.strip():
        raise ValueError("AI_JUDGE_ARTIFACT_STORE_ROOT cannot be empty")
    if settings.artifact_store_provider not in VALID_ARTIFACT_STORE_PROVIDERS:
        raise ValueError(
            "AI_JUDGE_ARTIFACT_STORE_PROVIDER must be one of "
            + ",".join(sorted(VALID_ARTIFACT_STORE_PROVIDERS))
        )
    if settings.artifact_store_provider == ARTIFACT_STORE_PROVIDER_S3_COMPATIBLE:
        if not settings.artifact_store_bucket.strip():
            raise ValueError(
                "AI_JUDGE_ARTIFACT_BUCKET cannot be empty when "
                "AI_JUDGE_ARTIFACT_STORE_PROVIDER=s3_compatible"
            )
        if "/" in settings.artifact_store_bucket.strip():
            raise ValueError("AI_JUDGE_ARTIFACT_BUCKET must be a bucket name, not a path")
        if any(part in {".", ".."} for part in settings.artifact_store_prefix.split("/")):
            raise ValueError("AI_JUDGE_ARTIFACT_PREFIX cannot contain . or .. segments")
    if settings.db_pool_size < 1 or settings.db_pool_size > 200:
        raise ValueError("AI_JUDGE_DB_POOL_SIZE must be between 1 and 200")
    if settings.db_max_overflow < 0 or settings.db_max_overflow > 200:
        raise ValueError("AI_JUDGE_DB_MAX_OVERFLOW must be between 0 and 200")
    if settings.topic_memory_limit < 1 or settings.topic_memory_limit > 20:
        raise ValueError("AI_JUDGE_TOPIC_MEMORY_LIMIT must be between 1 and 20")
    if settings.topic_memory_min_evidence_refs < 0 or settings.topic_memory_min_evidence_refs > 20:
        raise ValueError("AI_JUDGE_TOPIC_MEMORY_MIN_EVIDENCE_REFS must be between 0 and 20")
    if (
        settings.topic_memory_min_rationale_chars < 0
        or settings.topic_memory_min_rationale_chars > 2000
    ):
        raise ValueError("AI_JUDGE_TOPIC_MEMORY_MIN_RATIONALE_CHARS must be between 0 and 2000")
    if (
        settings.topic_memory_min_quality_score < 0.0
        or settings.topic_memory_min_quality_score > 1.0
    ):
        raise ValueError("AI_JUDGE_TOPIC_MEMORY_MIN_QUALITY_SCORE must be between 0 and 1")
    if not settings.tokenizer_fallback_encoding.strip():
        raise ValueError("AI_JUDGE_TOKENIZER_FALLBACK_ENCODING cannot be empty")
    if settings.phase_prompt_max_tokens < 256 or settings.phase_prompt_max_tokens > 32000:
        raise ValueError("AI_JUDGE_PHASE_PROMPT_MAX_TOKENS must be between 256 and 32000")
    if settings.agent2_prompt_max_tokens < 256 or settings.agent2_prompt_max_tokens > 32000:
        raise ValueError("AI_JUDGE_AGENT2_PROMPT_MAX_TOKENS must be between 256 and 32000")
    if settings.rag_query_max_tokens < 64 or settings.rag_query_max_tokens > 32000:
        raise ValueError("AI_JUDGE_RAG_QUERY_MAX_TOKENS must be between 64 and 32000")
    if settings.rag_snippet_max_tokens < 16 or settings.rag_snippet_max_tokens > 8000:
        raise ValueError("AI_JUDGE_RAG_SNIPPET_MAX_TOKENS must be between 16 and 8000")
    if settings.embed_input_max_tokens < 64 or settings.embed_input_max_tokens > 32000:
        raise ValueError("AI_JUDGE_EMBED_INPUT_MAX_TOKENS must be between 64 and 32000")
    if settings.runtime_retry_max_attempts < 1 or settings.runtime_retry_max_attempts > 10:
        raise ValueError("AI_JUDGE_RUNTIME_RETRY_MAX_ATTEMPTS must be between 1 and 10")
    if settings.runtime_retry_backoff_ms < 0 or settings.runtime_retry_backoff_ms > 10000:
        raise ValueError("AI_JUDGE_RUNTIME_RETRY_BACKOFF_MS must be between 0 and 10000")
    if settings.rag_lexical_engine not in VALID_LEXICAL_ENGINES:
        raise ValueError(
            "AI_JUDGE_RAG_LEXICAL_ENGINE must be one of " + ",".join(sorted(VALID_LEXICAL_ENGINES))
        )
    if not settings.rag_bm25_cache_dir.strip():
        raise ValueError("AI_JUDGE_RAG_BM25_CACHE_DIR cannot be empty")
    if settings.rag_rerank_engine not in VALID_RERANK_ENGINES:
        raise ValueError(
            "AI_JUDGE_RAG_RERANK_ENGINE must be one of " + ",".join(sorted(VALID_RERANK_ENGINES))
        )
    if not settings.rag_rerank_model.strip():
        raise ValueError("AI_JUDGE_RAG_RERANK_MODEL cannot be empty")
    if settings.rag_rerank_batch_size < 1 or settings.rag_rerank_batch_size > 128:
        raise ValueError("AI_JUDGE_RAG_RERANK_BATCH_SIZE must be between 1 and 128")
    if settings.rag_rerank_candidate_cap < 1 or settings.rag_rerank_candidate_cap > 200:
        raise ValueError("AI_JUDGE_RAG_RERANK_CANDIDATE_CAP must be between 1 and 200")
    if settings.rag_rerank_timeout_ms < 100 or settings.rag_rerank_timeout_ms > 60000:
        raise ValueError("AI_JUDGE_RAG_RERANK_TIMEOUT_MS must be between 100 and 60000")
    if settings.rag_rerank_device not in VALID_RERANK_DEVICES:
        raise ValueError(
            "AI_JUDGE_RAG_RERANK_DEVICE must be one of " + ",".join(sorted(VALID_RERANK_DEVICES))
        )
    if not settings.policy_registry_default_version.strip():
        raise ValueError("AI_JUDGE_POLICY_REGISTRY_DEFAULT_VERSION cannot be empty")
    if not settings.prompt_registry_default_version.strip():
        raise ValueError("AI_JUDGE_PROMPT_REGISTRY_DEFAULT_VERSION cannot be empty")
    if not settings.tool_registry_default_version.strip():
        raise ValueError("AI_JUDGE_TOOL_REGISTRY_DEFAULT_VERSION cannot be empty")
    if settings.redis_enabled:
        if not settings.redis_url:
            raise ValueError("AI_JUDGE_REDIS_URL cannot be empty when AI_JUDGE_REDIS_ENABLED=true")
        if not settings.redis_key_prefix:
            raise ValueError(
                "AI_JUDGE_REDIS_KEY_PREFIX cannot be empty when AI_JUDGE_REDIS_ENABLED=true"
            )

    if is_production_env(runtime_env):
        if settings.provider == PROVIDER_MOCK:
            raise ValueError("AI_JUDGE_PROVIDER=mock is forbidden when runtime env is production")
        if settings.openai_fallback_to_mock:
            raise ValueError(
                "AI_JUDGE_OPENAI_FALLBACK_TO_MOCK=true is forbidden when runtime env is production"
            )
        if settings.provider == PROVIDER_OPENAI and not settings.openai_api_key.strip():
            raise ValueError("OPENAI_API_KEY cannot be empty when runtime env is production")
        if settings.fault_injection_nodes:
            raise ValueError(
                "AI_JUDGE_FAULT_INJECTION_NODES is forbidden when runtime env is production"
            )
        if settings.artifact_store_provider == ARTIFACT_STORE_PROVIDER_LOCAL:
            raise ValueError(
                "AI_JUDGE_ARTIFACT_STORE_PROVIDER=local is forbidden when runtime env is production"
            )
        if settings.assistant_advisory_placeholder_enabled:
            raise ValueError(
                "AI_JUDGE_ASSISTANT_ADVISORY_PLACEHOLDER_ENABLED=true is forbidden "
                "when runtime env is production"
            )


def build_callback_client_config(settings: Settings) -> CallbackClientConfig:
    return CallbackClientConfig(
        ai_internal_key=settings.ai_internal_key,
        chat_server_base_url=settings.chat_server_base_url,
        callback_timeout_secs=settings.callback_timeout_secs,
        phase_report_path_template=settings.phase_report_path_template,
        final_report_path_template=settings.final_report_path_template,
        phase_failed_path_template=settings.phase_failed_path_template,
        final_failed_path_template=settings.final_failed_path_template,
    )


def build_dispatch_runtime_config(settings: Settings) -> DispatchRuntimeConfig:
    return DispatchRuntimeConfig(
        process_delay_ms=settings.process_delay_ms,
        judge_style_mode=settings.judge_style_mode,
        runtime_retry_max_attempts=settings.runtime_retry_max_attempts,
        retry_backoff_ms=settings.runtime_retry_backoff_ms,
        compliance_block_enabled=settings.compliance_block_enabled,
    )
