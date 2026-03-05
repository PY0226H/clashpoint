import unittest
from types import SimpleNamespace

from app.rag_retriever import RAG_BACKEND_MILVUS, RetrievedContext
from app.runtime_rag import (
    apply_rag_payload_fields,
    build_milvus_config,
    retrieve_runtime_contexts_with_meta,
    retrieve_runtime_contexts,
    resolve_effective_rag_backend,
)
from app.settings import Settings


class _FakeReport:
    def __init__(self) -> None:
        self.payload: dict = {}


def _build_settings(**overrides: object) -> Settings:
    base = {
        "ai_internal_key": "k",
        "chat_server_base_url": "http://chat",
        "report_path_template": "/r/{job_id}",
        "failed_path_template": "/f/{job_id}",
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
        "rag_source_whitelist": ("https://teamfighttactics.leagueoflegends.com/en-us/news",),
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
        "graph_v2_enabled": True,
        "reflection_enabled": True,
        "topic_memory_enabled": True,
        "rag_hybrid_enabled": True,
        "rag_rerank_enabled": True,
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
        "topic_memory_limit": 5,
        "topic_memory_min_evidence_refs": 1,
        "topic_memory_min_rationale_chars": 20,
        "topic_memory_min_quality_score": 0.55,
    }
    base.update(overrides)
    return Settings(**base)


class RuntimeRagTests(unittest.TestCase):
    def test_build_milvus_config_should_return_none_when_backend_invalid(self) -> None:
        settings = _build_settings(rag_backend="file")
        self.assertIsNone(build_milvus_config(settings))

    def test_build_milvus_config_should_return_config_when_enabled(self) -> None:
        settings = _build_settings(
            rag_backend=RAG_BACKEND_MILVUS,
            rag_milvus_uri="http://milvus:19530",
            rag_milvus_collection="judge_kb",
            rag_milvus_metric_type="IP",
            rag_milvus_search_limit=33,
        )
        cfg = build_milvus_config(settings)
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.uri, "http://milvus:19530")
        self.assertEqual(cfg.collection, "judge_kb")
        self.assertEqual(cfg.metric_type, "IP")
        self.assertEqual(cfg.search_limit, 33)

    def test_retrieve_runtime_contexts_should_forward_settings_and_milvus_config(self) -> None:
        settings = _build_settings(
            rag_enabled=False,
            rag_backend=RAG_BACKEND_MILVUS,
            rag_milvus_uri="http://milvus:19530",
            rag_milvus_collection="judge_kb",
            openai_api_key="sk-test",
        )
        request = SimpleNamespace(job=SimpleNamespace(job_id=1))
        captured: dict[str, object] = {}
        expected = [
            RetrievedContext(
                chunk_id="c1",
                title="title",
                source_url="https://example.com",
                content="content",
                score=0.9,
            )
        ]

        def fake_retrieve_contexts(req: object, **kwargs: object) -> list[RetrievedContext]:
            captured["req"] = req
            captured["kwargs"] = kwargs
            return expected

        actual = retrieve_runtime_contexts(
            request=request,
            settings=settings,
            retrieve_contexts_fn=fake_retrieve_contexts,
        )

        self.assertEqual(actual, expected)
        self.assertIs(captured["req"], request)
        kwargs = captured["kwargs"]
        self.assertFalse(kwargs["enabled"])
        self.assertEqual(kwargs["backend"], RAG_BACKEND_MILVUS)
        self.assertEqual(kwargs["openai_api_key"], "sk-test")
        self.assertTrue(kwargs["hybrid_enabled"])
        self.assertTrue(kwargs["rerank_enabled"])
        self.assertEqual(kwargs["hybrid_rrf_k"], 60)
        self.assertEqual(kwargs["hybrid_vector_limit_multiplier"], 1)
        self.assertEqual(kwargs["hybrid_lexical_limit_multiplier"], 2)
        self.assertEqual(kwargs["rerank_query_weight"], 0.7)
        self.assertEqual(kwargs["rerank_base_weight"], 0.3)
        self.assertIsInstance(kwargs["diagnostics"], dict)
        self.assertEqual(kwargs["milvus_config"].collection, "judge_kb")

    def test_retrieve_runtime_contexts_with_meta_should_fallback_to_file_when_missing_embedding_key(
        self,
    ) -> None:
        settings = _build_settings(
            rag_backend=RAG_BACKEND_MILVUS,
            rag_milvus_uri="http://milvus:19530",
            rag_milvus_collection="judge_kb",
            rag_knowledge_file="/tmp/knowledge.json",
            openai_api_key="",
        )
        request = SimpleNamespace(job=SimpleNamespace(job_id=1))
        captured: dict[str, object] = {}

        def fake_retrieve_contexts(req: object, **kwargs: object) -> list[RetrievedContext]:
            captured["req"] = req
            captured["kwargs"] = kwargs
            kwargs["diagnostics"]["strategy"] = "file_fallback"
            return []

        result = retrieve_runtime_contexts_with_meta(
            request=request,
            settings=settings,
            retrieve_contexts_fn=fake_retrieve_contexts,
        )

        self.assertEqual(result.requested_backend, RAG_BACKEND_MILVUS)
        self.assertEqual(result.effective_backend, "file")
        self.assertEqual(
            result.backend_fallback_reason,
            "missing_openai_api_key_for_milvus_embedding",
        )
        kwargs = captured["kwargs"]
        self.assertEqual(kwargs["backend"], "file")
        self.assertIsNone(kwargs["milvus_config"])
        self.assertEqual(result.retrieval_diagnostics["strategy"], "file_fallback")
        self.assertEqual(result.retrieval_diagnostics["profileResolved"], "hybrid_v1")
        self.assertIsNone(result.retrieval_diagnostics["profileFallbackReason"])

    def test_retrieve_runtime_contexts_with_meta_should_retry_without_hybrid_kwargs_for_legacy_fn(self) -> None:
        settings = _build_settings(rag_enabled=True)
        request = SimpleNamespace(job=SimpleNamespace(job_id=1))
        calls = {"count": 0}

        def legacy_retrieve_contexts(req: object, **kwargs: object) -> list[RetrievedContext]:
            calls["count"] += 1
            if "hybrid_enabled" in kwargs:
                raise TypeError("legacy fn got unexpected keyword")
            return []

        result = retrieve_runtime_contexts_with_meta(
            request=request,
            settings=settings,
            retrieve_contexts_fn=legacy_retrieve_contexts,
        )
        self.assertEqual(calls["count"], 2)
        self.assertEqual(result.retrieval_diagnostics["profileResolved"], "hybrid_v1")
        self.assertTrue(result.retrieval_diagnostics["hybridEnabledEffective"])
        self.assertTrue(result.retrieval_diagnostics["rerankEnabledEffective"])

    def test_retrieve_runtime_contexts_with_meta_should_fallback_unknown_profile_to_default(self) -> None:
        settings = _build_settings(rag_enabled=True)
        request = SimpleNamespace(
            job=SimpleNamespace(job_id=1),
            retrieval_profile="unknown-profile",
        )
        captured: dict[str, object] = {}

        def fake_retrieve_contexts(req: object, **kwargs: object) -> list[RetrievedContext]:
            captured["req"] = req
            captured["kwargs"] = kwargs
            return []

        result = retrieve_runtime_contexts_with_meta(
            request=request,
            settings=settings,
            retrieve_contexts_fn=fake_retrieve_contexts,
        )
        kwargs = captured["kwargs"]
        self.assertEqual(kwargs["hybrid_rrf_k"], 60)
        self.assertEqual(kwargs["hybrid_lexical_limit_multiplier"], 2)
        self.assertEqual(result.retrieval_diagnostics["profileRequested"], "unknown-profile")
        self.assertEqual(result.retrieval_diagnostics["profileResolved"], "hybrid_v1")
        self.assertEqual(result.retrieval_diagnostics["profileFallbackReason"], "unknown_profile")

    def test_resolve_effective_rag_backend_should_fallback_when_milvus_config_missing(self) -> None:
        settings = _build_settings(rag_backend=RAG_BACKEND_MILVUS, openai_api_key="sk-test")
        backend, reason = resolve_effective_rag_backend(settings, milvus_config=None)
        self.assertEqual(backend, "file")
        self.assertEqual(reason, "milvus_config_missing")

    def test_apply_rag_payload_fields_should_write_payload_with_used_flag(self) -> None:
        settings = _build_settings(rag_backend=RAG_BACKEND_MILVUS, rag_enabled=True)
        report = _FakeReport()
        contexts = [
            RetrievedContext(
                chunk_id="c1",
                title="title",
                source_url="https://example.com",
                content="content",
                score=0.9,
            )
        ]

        apply_rag_payload_fields(
            report,
            settings,
            contexts,
            used_by_model=True,
            requested_backend="milvus",
            effective_backend="file",
            backend_fallback_reason="missing_openai_api_key_for_milvus_embedding",
        )
        self.assertTrue(report.payload["ragEnabled"])
        self.assertEqual(report.payload["ragBackend"], "file")
        self.assertEqual(report.payload["ragRequestedBackend"], "milvus")
        self.assertEqual(
            report.payload["ragBackendFallbackReason"],
            "missing_openai_api_key_for_milvus_embedding",
        )
        self.assertTrue(report.payload["ragUsedByModel"])
        self.assertEqual(report.payload["ragSnippetCount"], 1)
        self.assertEqual(report.payload["ragSourceWhitelist"], list(settings.rag_source_whitelist))
        self.assertEqual(len(report.payload["ragSources"]), 1)

        report2 = _FakeReport()
        apply_rag_payload_fields(
            report2,
            settings,
            [],
            used_by_model=True,
        )
        self.assertFalse(report2.payload["ragUsedByModel"])


if __name__ == "__main__":
    unittest.main()
