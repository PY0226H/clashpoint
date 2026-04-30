from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models import (
    CaseCreateRequest,
    FinalDispatchRequest,
    PhaseDispatchMessage,
    PhaseDispatchRequest,
)
from app.settings import ASSISTANT_ADVISORY_EXECUTOR_MODE_PLACEHOLDER, Settings
from httpx import ASGITransport, AsyncClient


def build_settings(**overrides: object) -> Settings:
    unique_db_suffix = int(datetime.now(timezone.utc).timestamp() * 1_000_000)
    base = {
        "ai_internal_key": "k",
        "chat_server_base_url": "http://chat",
        "phase_report_path_template": "/r/phase/{case_id}",
        "final_report_path_template": "/r/final/{case_id}",
        "phase_failed_path_template": "/f/phase/{case_id}",
        "final_failed_path_template": "/f/final/{case_id}",
        "callback_timeout_secs": 8.0,
        "process_delay_ms": 0,
        "judge_style_mode": "rational",
        "provider": "mock",
        "openai_api_key": "",
        "openai_model": "gpt-4.1-mini",
        "openai_base_url": "https://api.openai.com/v1",
        "openai_timeout_secs": 25.0,
        "openai_temperature": 0.1,
        "openai_max_retries": 2,
        "openai_fallback_to_mock": True,
        "rag_enabled": True,
        "rag_knowledge_file": "",
        "rag_max_snippets": 4,
        "rag_max_chars_per_snippet": 280,
        "rag_query_message_limit": 80,
        "rag_source_whitelist": (
            "https://teamfighttactics.leagueoflegends.com/en-us/news",
        ),
        "rag_backend": "file",
        "rag_openai_embedding_model": "text-embedding-3-small",
        "rag_milvus_uri": "",
        "rag_milvus_token": "",
        "rag_milvus_db_name": "",
        "rag_milvus_collection": "",
        "rag_milvus_vector_field": "embedding",
        "rag_milvus_content_field": "content",
        "rag_milvus_title_field": "title",
        "rag_milvus_source_url_field": "source_url",
        "rag_milvus_chunk_id_field": "chunk_id",
        "rag_milvus_tags_field": "tags",
        "rag_milvus_metric_type": "COSINE",
        "rag_milvus_search_limit": 20,
        "stage_agent_max_chunks": 12,
        "reflection_enabled": True,
        "topic_memory_enabled": True,
        "rag_hybrid_enabled": True,
        "rag_rerank_enabled": True,
        "rag_rerank_engine": "heuristic",
        "reflection_policy": "winner_mismatch_only",
        "reflection_low_margin_threshold": 3,
        "fault_injection_nodes": (),
        "degrade_max_level": 3,
        "trace_ttl_secs": 86400,
        "idempotency_ttl_secs": 86400,
        "redis_enabled": False,
        "redis_required": False,
        "redis_url": "redis://127.0.0.1:6379/0",
        "redis_pool_size": 20,
        "redis_key_prefix": "ai_judge:v2",
        "db_url": f"sqlite+aiosqlite:////tmp/echoisle_ai_judge_service_test_{unique_db_suffix}.db",
        "db_echo": False,
        "db_pool_size": 10,
        "db_max_overflow": 20,
        "db_auto_create_schema": True,
        "artifact_store_root": f"/tmp/echoisle_ai_judge_service_artifacts_{unique_db_suffix}",
        "topic_memory_limit": 5,
        "topic_memory_min_evidence_refs": 1,
        "topic_memory_min_rationale_chars": 20,
        "topic_memory_min_quality_score": 0.55,
        "runtime_retry_max_attempts": 2,
        "runtime_retry_backoff_ms": 200,
        "compliance_block_enabled": True,
    }
    base.update(overrides)
    if (
        base.get("assistant_advisory_placeholder_enabled") is True
        and "assistant_advisory_executor_mode" not in overrides
    ):
        base["assistant_advisory_executor_mode"] = ASSISTANT_ADVISORY_EXECUTOR_MODE_PLACEHOLDER
    return Settings(**base)


def build_phase_request(
    *,
    case_id: int = 101,
    idempotency_key: str = "phase-key-101",
    rubric_version: str = "v3",
    judge_policy_version: str = "v3-default",
) -> PhaseDispatchRequest:
    now = datetime.now(timezone.utc)
    return PhaseDispatchRequest(
        case_id=case_id,
        scope_id=1,
        session_id=2,
        phase_no=1,
        message_start_id=1,
        message_end_id=2,
        message_count=2,
        messages=[
            PhaseDispatchMessage(
                message_id=1,
                side="pro",
                content="pro message",
                created_at=now,
                speaker_tag="pro_1",
            ),
            PhaseDispatchMessage(
                message_id=2,
                side="con",
                content="con message",
                created_at=now,
                speaker_tag="con_1",
            ),
        ],
        rubric_version=rubric_version,
        judge_policy_version=judge_policy_version,
        topic_domain="tft",
        retrieval_profile="hybrid_v1",
        trace_id=f"trace-phase-{case_id}",
        idempotency_key=idempotency_key,
    )


def build_final_request(
    *,
    case_id: int = 202,
    idempotency_key: str = "final-key-202",
    rubric_version: str = "v3",
    judge_policy_version: str = "v3-default",
) -> FinalDispatchRequest:
    return FinalDispatchRequest(
        case_id=case_id,
        scope_id=1,
        session_id=2,
        phase_start_no=1,
        phase_end_no=1,
        rubric_version=rubric_version,
        judge_policy_version=judge_policy_version,
        topic_domain="tft",
        trace_id=f"trace-final-{case_id}",
        idempotency_key=idempotency_key,
    )


def build_case_create_request(
    *,
    case_id: int = 901,
    idempotency_key: str = "case-key-901",
    rubric_version: str = "v3",
    judge_policy_version: str = "v3-default",
) -> CaseCreateRequest:
    return CaseCreateRequest(
        case_id=case_id,
        scope_id=1,
        session_id=2,
        rubric_version=rubric_version,
        judge_policy_version=judge_policy_version,
        topic_domain="tft",
        retrieval_profile="hybrid_v1",
        trace_id=f"trace-case-{case_id}",
        idempotency_key=idempotency_key,
    )


def build_env_blocked_citation_verification() -> dict[str, Any]:
    return {
        "version": "evidence-citation-verification-v1",
        "status": "env_blocked",
        "citationCount": 0,
        "messageRefCount": 0,
        "sourceRefCount": 0,
        "missingCitationCount": 0,
        "weakCitationCount": 0,
        "forbiddenSourceCount": 0,
        "reasonCodes": ["citation_verifier_real_sample_env_blocked"],
    }


def unique_case_id(seed: int) -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1_000_000) + seed


class AppFactoryRouteTestMixin:
    async def _post_json(
        self,
        *,
        app: Any,
        path: str,
        payload: dict[str, Any],
        internal_key: str,
    ) -> Any:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                path,
                json=payload,
                headers={"x-ai-internal-key": internal_key},
            )

    async def _get(self, *, app: Any, path: str, internal_key: str) -> Any:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(
                path,
                headers={"x-ai-internal-key": internal_key},
            )

    async def _post(self, *, app: Any, path: str, internal_key: str) -> Any:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                path,
                headers={"x-ai-internal-key": internal_key},
            )
