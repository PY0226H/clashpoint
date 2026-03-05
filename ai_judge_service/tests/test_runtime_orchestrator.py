import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from app.rag_retriever import RAG_BACKEND_MILVUS, RetrievedContext
from app.runtime_errors import (
    ERROR_CONSISTENCY_CONFLICT,
    ERROR_JUDGE_TIMEOUT,
    ERROR_MODEL_OVERLOAD,
    ERROR_RAG_UNAVAILABLE,
)
from app.runtime_orchestrator import build_report_by_runtime
from app.runtime_policy import PROVIDER_MOCK, PROVIDER_OPENAI
from app.settings import Settings
from app.trace_store import TopicMemoryRecord


class _FakeReport:
    def __init__(self, payload: dict | None = None) -> None:
        self.payload = payload or {}
        self.winner_first = "pro"
        self.winner_second = "pro"
        self.rejudge_triggered = False


def _build_settings(**overrides: object) -> Settings:
    base = {
        "ai_internal_key": "k",
        "chat_server_base_url": "http://chat",
        "report_path_template": "/r/{job_id}",
        "failed_path_template": "/f/{job_id}",
        "callback_timeout_secs": 8.0,
        "process_delay_ms": 0,
        "judge_style_mode": "rational",
        "provider": PROVIDER_MOCK,
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


def _build_request() -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        job=SimpleNamespace(
            job_id=1,
            ws_id=1,
            session_id=2,
            requested_by=1,
            style_mode="rational",
            rejudge_triggered=False,
            requested_at=now,
        ),
        session=SimpleNamespace(
            status="judging",
            scheduled_start_at=now,
            actual_start_at=now,
            end_at=now,
        ),
        topic=SimpleNamespace(
            title="test",
            description="desc",
            category="game",
            stance_pro="pro",
            stance_con="con",
            context_seed=None,
        ),
        messages=[],
        message_window_size=100,
        rubric_version="v1",
    )


class RuntimeOrchestratorTests(unittest.IsolatedAsyncioTestCase):
    async def test_build_report_by_runtime_should_use_openai_and_set_rag_meta(self) -> None:
        settings = _build_settings(provider=PROVIDER_OPENAI, openai_api_key="sk-test")
        request = _build_request()
        contexts = [
            RetrievedContext(
                chunk_id="c1",
                title="title",
                source_url="https://teamfighttactics.leagueoflegends.com/en-us/news/patch",
                content="content",
                score=0.9,
            )
        ]
        captured: dict[str, object] = {}

        def fake_retrieve_contexts(_req: object, **kwargs: object) -> list[RetrievedContext]:
            captured["retrieve_kwargs"] = kwargs
            return contexts

        async def fake_build_openai(**kwargs: object) -> _FakeReport:
            captured["openai_kwargs"] = kwargs
            return _FakeReport(payload={"provider": "openai"})

        def fake_build_mock(*_args: object, **_kwargs: object) -> _FakeReport:
            raise AssertionError("mock builder should not be called")

        report = await build_report_by_runtime(
            request=request,
            effective_style_mode="rational",
            style_mode_source="system_config",
            settings=settings,
            retrieve_contexts_fn=fake_retrieve_contexts,
            build_report_with_openai_fn=fake_build_openai,
            build_mock_report_fn=fake_build_mock,
        )

        openai_kwargs = captured["openai_kwargs"]
        self.assertEqual(openai_kwargs["request"], request)
        self.assertEqual(openai_kwargs["effective_style_mode"], "rational")
        self.assertEqual(openai_kwargs["style_mode_source"], "system_config")
        self.assertEqual(openai_kwargs["retrieved_contexts"], contexts)
        self.assertEqual(report.payload["provider"], "openai")
        self.assertTrue(report.payload["ragEnabled"])
        self.assertTrue(report.payload["ragUsedByModel"])
        self.assertEqual(report.payload["ragSnippetCount"], 1)
        self.assertEqual(report.payload["ragBackend"], "file")
        self.assertEqual(report.payload["ragSourceWhitelist"], list(settings.rag_source_whitelist))
        self.assertEqual(len(report.payload["ragSources"]), 1)
        self.assertIn("judgeTrace", report.payload)
        self.assertIn("retrievalDiagnostics", report.payload)
        self.assertIn("consistency", report.payload)
        self.assertIn("cost", report.payload)
        rag_diag = report.payload["retrievalDiagnostics"]["ragRetriever"]
        self.assertEqual(rag_diag["profileResolved"], "hybrid_v1")
        self.assertTrue(rag_diag["hybridEnabledEffective"])
        self.assertTrue(rag_diag["rerankEnabledEffective"])
        self.assertIsNone(captured["retrieve_kwargs"]["milvus_config"])
        self.assertEqual(report.payload["topicMemory"]["reuseCount"], 0)
        self.assertIsNone(report.payload["retrievalDiagnostics"]["topicMemoryAvgQualityScore"])
        self.assertEqual(report.payload["errorCodes"], [])
        judge_audit = report.payload.get("judgeAudit")
        self.assertIsInstance(judge_audit, dict)
        self.assertEqual(judge_audit["rubricVersion"], "v1")
        self.assertEqual(judge_audit["judgePolicyVersion"], "v2-default")
        self.assertEqual(judge_audit["degradationLevel"], report.payload["judgeTrace"]["degradationLevel"])
        self.assertEqual(len(judge_audit["promptHash"]), 64)
        self.assertEqual(len(judge_audit["retrievalSnapshot"]), 1)
        self.assertEqual(judge_audit["retrievalSnapshot"][0]["chunkId"], "c1")

    async def test_build_report_by_runtime_should_mark_degradation_level_l1_when_rerank_disabled_by_profile(
        self,
    ) -> None:
        settings = _build_settings(provider=PROVIDER_OPENAI, openai_api_key="sk-test")
        request = _build_request()
        request.retrieval_profile = "hybrid_recall_v1"

        def fake_retrieve_contexts(_req: object, **_kwargs: object) -> list[RetrievedContext]:
            return [
                RetrievedContext(
                    chunk_id="c1",
                    title="t",
                    source_url="https://example.com",
                    content="c",
                    score=0.8,
                )
            ]

        async def fake_build_openai(**_kwargs: object) -> _FakeReport:
            return _FakeReport(payload={"provider": "openai"})

        report = await build_report_by_runtime(
            request=request,
            effective_style_mode="rational",
            style_mode_source="system_config",
            settings=settings,
            retrieve_contexts_fn=fake_retrieve_contexts,
            build_report_with_openai_fn=fake_build_openai,
            build_mock_report_fn=lambda *_args, **_kwargs: _FakeReport(payload={"provider": "mock"}),
        )
        self.assertEqual(report.payload["judgeTrace"]["degradationLevel"], 1)
        self.assertEqual(report.payload["errorCodes"], [])

    async def test_build_report_by_runtime_should_reuse_topic_memory_as_context(self) -> None:
        settings = _build_settings(provider=PROVIDER_OPENAI, openai_api_key="sk-test")
        request = _build_request()
        request.topic_domain = "finance"
        request.rubric_version = "v1"
        rag_contexts = [
            RetrievedContext(
                chunk_id="rag-1",
                title="kb",
                source_url="https://example.com/kb",
                content="rag content",
                score=0.7,
            )
        ]

        class _FakeTraceStore:
            def list_topic_memory(self, *, topic_domain: str, rubric_version: str, limit: int = 3):
                self.args = (topic_domain, rubric_version, limit)
                return [
                    TopicMemoryRecord(
                        created_at=datetime.now(timezone.utc),
                        job_id=99,
                        trace_id="trace-99",
                        topic_domain="finance",
                        rubric_version="v1",
                        winner="pro",
                        rationale="历史高质量判决",
                        evidence_refs=[{"messageId": 12, "reason": "证据完整"}],
                        provider="openai",
                        audit={"qualityScore": 0.92},
                    )
                ]

        trace_store = _FakeTraceStore()
        captured: dict[str, object] = {}

        def fake_retrieve_contexts(_req: object, **_kwargs: object) -> list[RetrievedContext]:
            return rag_contexts

        async def fake_build_openai(**kwargs: object) -> _FakeReport:
            captured["openai_kwargs"] = kwargs
            return _FakeReport(payload={"provider": "openai"})

        report = await build_report_by_runtime(
            request=request,
            effective_style_mode="rational",
            style_mode_source="system_config",
            settings=settings,
            trace_store=trace_store,
            retrieve_contexts_fn=fake_retrieve_contexts,
            build_report_with_openai_fn=fake_build_openai,
            build_mock_report_fn=lambda *_args, **_kwargs: _FakeReport(payload={"provider": "mock"}),
        )

        openai_contexts = captured["openai_kwargs"]["retrieved_contexts"]
        self.assertEqual(len(openai_contexts), 2)
        self.assertEqual(openai_contexts[0].source_url, "memory://topic/finance")
        self.assertEqual(openai_contexts[1].chunk_id, "rag-1")
        self.assertEqual(report.payload["topicMemory"]["reuseCount"], 1)
        self.assertEqual(report.payload["topicMemory"]["qualityScores"], [0.92])
        self.assertEqual(report.payload["retrievalDiagnostics"]["topicMemoryReuseCount"], 1)
        self.assertEqual(report.payload["retrievalDiagnostics"]["topicMemoryAvgQualityScore"], 0.92)
        rag_diag = report.payload["retrievalDiagnostics"]["ragRetriever"]
        self.assertEqual(rag_diag["profileResolved"], "hybrid_v1")
        self.assertEqual(report.payload["errorCodes"], [])

    async def test_build_report_by_runtime_should_mark_consistency_conflict_when_reflection_draw_protection(
        self,
    ) -> None:
        settings = _build_settings(provider=PROVIDER_OPENAI, openai_api_key="sk-test")
        request = _build_request()

        def fake_retrieve_contexts(_req: object, **_kwargs: object) -> list[RetrievedContext]:
            return [
                RetrievedContext(
                    chunk_id="c1",
                    title="t",
                    source_url="https://example.com",
                    content="c",
                    score=0.8,
                )
            ]

        async def fake_build_openai(**_kwargs: object) -> _FakeReport:
            return _FakeReport(
                payload={
                    "provider": "openai",
                    "agentPipeline": {"reflectionAction": "draw_protection"},
                }
            )

        report = await build_report_by_runtime(
            request=request,
            effective_style_mode="rational",
            style_mode_source="system_config",
            settings=settings,
            retrieve_contexts_fn=fake_retrieve_contexts,
            build_report_with_openai_fn=fake_build_openai,
            build_mock_report_fn=lambda *_args, **_kwargs: _FakeReport(payload={"provider": "mock"}),
        )
        self.assertIn(ERROR_CONSISTENCY_CONFLICT, report.payload["errorCodes"])

    async def test_build_report_by_runtime_should_fail_open_when_rag_retrieval_runtime_error(self) -> None:
        settings = _build_settings(provider=PROVIDER_MOCK)
        request = _build_request()

        def fake_retrieve_contexts(_req: object, **_kwargs: object) -> list[RetrievedContext]:
            raise RuntimeError("milvus timeout")

        report = await build_report_by_runtime(
            request=request,
            effective_style_mode="rational",
            style_mode_source="system_config",
            settings=settings,
            retrieve_contexts_fn=fake_retrieve_contexts,
            build_report_with_openai_fn=lambda **_kwargs: _FakeReport(payload={"provider": "openai"}),
            build_mock_report_fn=lambda *_args, **_kwargs: _FakeReport(payload={"provider": "mock"}),
        )

        self.assertEqual(report.payload["provider"], "mock")
        self.assertEqual(report.payload["judgeTrace"]["degradationLevel"], 2)
        self.assertEqual(report.payload["retrievalDiagnostics"]["ragRetriever"]["strategy"], "runtime_error")
        self.assertIn(ERROR_JUDGE_TIMEOUT, report.payload["errorCodes"])
        self.assertIn(ERROR_RAG_UNAVAILABLE, report.payload["errorCodes"])

    async def test_build_report_by_runtime_should_mark_topic_memory_unavailable_when_fault_injected(self) -> None:
        settings = _build_settings(
            provider=PROVIDER_OPENAI,
            openai_api_key="sk-test",
            fault_injection_nodes=("topic_memory_unavailable",),
        )
        request = _build_request()

        class _FakeTraceStore:
            def list_topic_memory(self, *, topic_domain: str, rubric_version: str, limit: int = 3):
                raise AssertionError("list_topic_memory should be bypassed by fault injection")

        def fake_retrieve_contexts(_req: object, **_kwargs: object) -> list[RetrievedContext]:
            return [
                RetrievedContext(
                    chunk_id="rag-1",
                    title="kb",
                    source_url="https://example.com/kb",
                    content="rag content",
                    score=0.7,
                )
            ]

        async def fake_build_openai(**_kwargs: object) -> _FakeReport:
            return _FakeReport(payload={"provider": "openai"})

        report = await build_report_by_runtime(
            request=request,
            effective_style_mode="rational",
            style_mode_source="system_config",
            settings=settings,
            trace_store=_FakeTraceStore(),
            retrieve_contexts_fn=fake_retrieve_contexts,
            build_report_with_openai_fn=fake_build_openai,
            build_mock_report_fn=lambda *_args, **_kwargs: _FakeReport(payload={"provider": "mock"}),
        )

        self.assertEqual(report.payload["judgeTrace"]["degradationLevel"], 1)
        self.assertIn("fault injected topic memory unavailable", report.payload["retrievalDiagnostics"]["topicMemoryError"])
        self.assertTrue(report.payload["retrievalDiagnostics"]["topicMemoryFaultInjected"])
        self.assertIn(ERROR_RAG_UNAVAILABLE, report.payload["errorCodes"])

    async def test_build_report_by_runtime_should_fallback_when_openai_failed_and_enabled(self) -> None:
        settings = _build_settings(provider=PROVIDER_OPENAI, openai_api_key="sk-test", openai_fallback_to_mock=True)
        request = _build_request()

        def fake_retrieve_contexts(_req: object, **_kwargs: object) -> list[RetrievedContext]:
            return []

        async def fake_build_openai(**_kwargs: object) -> _FakeReport:
            raise RuntimeError("openai boom")

        def fake_build_mock(_request: object, **kwargs: object) -> _FakeReport:
            self.assertEqual(kwargs["system_style_mode"], settings.judge_style_mode)
            return _FakeReport(payload={"provider": "mock"})

        report = await build_report_by_runtime(
            request=request,
            effective_style_mode="rational",
            style_mode_source="system_config",
            settings=settings,
            retrieve_contexts_fn=fake_retrieve_contexts,
            build_report_with_openai_fn=fake_build_openai,
            build_mock_report_fn=fake_build_mock,
        )

        self.assertEqual(report.payload["provider"], "ai-judge-service-mock-fallback")
        self.assertEqual(report.payload["fallbackFrom"], "openai")
        self.assertIn("openai boom", report.payload["fallbackReason"])
        self.assertFalse(report.payload["ragUsedByModel"])
        self.assertIn(ERROR_MODEL_OVERLOAD, report.payload["errorCodes"])
        self.assertIn(ERROR_RAG_UNAVAILABLE, report.payload["errorCodes"])

    async def test_build_report_by_runtime_should_raise_when_openai_failed_and_fallback_disabled(self) -> None:
        settings = _build_settings(provider=PROVIDER_OPENAI, openai_api_key="sk-test", openai_fallback_to_mock=False)
        request = _build_request()

        def fake_retrieve_contexts(_req: object, **_kwargs: object) -> list[RetrievedContext]:
            return []

        async def fake_build_openai(**_kwargs: object) -> _FakeReport:
            raise RuntimeError("network error")

        def fake_build_mock(*_args: object, **_kwargs: object) -> _FakeReport:
            raise AssertionError("mock builder should not be called")

        with self.assertRaises(RuntimeError) as ctx:
            await build_report_by_runtime(
                request=request,
                effective_style_mode="rational",
                style_mode_source="system_config",
                settings=settings,
                retrieve_contexts_fn=fake_retrieve_contexts,
                build_report_with_openai_fn=fake_build_openai,
                build_mock_report_fn=fake_build_mock,
            )
        self.assertIn("openai runtime failed", str(ctx.exception))

    async def test_build_report_by_runtime_should_mark_missing_openai_key(self) -> None:
        settings = _build_settings(provider=PROVIDER_OPENAI, openai_api_key="")
        request = _build_request()
        calls: dict[str, object] = {}

        def fake_retrieve_contexts(_req: object, **_kwargs: object) -> list[RetrievedContext]:
            return []

        async def fake_build_openai(**_kwargs: object) -> _FakeReport:
            raise AssertionError("openai builder should not be called without api key")

        def fake_build_mock(_request: object, **kwargs: object) -> _FakeReport:
            calls["system_style_mode"] = kwargs["system_style_mode"]
            return _FakeReport(payload={"provider": "mock"})

        report = await build_report_by_runtime(
            request=request,
            effective_style_mode="rational",
            style_mode_source="system_config",
            settings=settings,
            retrieve_contexts_fn=fake_retrieve_contexts,
            build_report_with_openai_fn=fake_build_openai,
            build_mock_report_fn=fake_build_mock,
        )

        self.assertEqual(calls["system_style_mode"], settings.judge_style_mode)
        self.assertEqual(report.payload["provider"], "ai-judge-service-mock-missing-openai-key")
        self.assertEqual(report.payload["fallbackFrom"], "openai")
        self.assertEqual(report.payload["fallbackReason"], "missing OPENAI_API_KEY")
        self.assertFalse(report.payload["ragUsedByModel"])
        self.assertIn(ERROR_MODEL_OVERLOAD, report.payload["errorCodes"])
        self.assertIn(ERROR_RAG_UNAVAILABLE, report.payload["errorCodes"])

    async def test_build_report_by_runtime_should_raise_when_missing_openai_key_and_fallback_disabled(self) -> None:
        settings = _build_settings(
            provider=PROVIDER_OPENAI,
            openai_api_key="",
            openai_fallback_to_mock=False,
        )
        request = _build_request()

        def fake_retrieve_contexts(_req: object, **_kwargs: object) -> list[RetrievedContext]:
            return []

        async def fake_build_openai(**_kwargs: object) -> _FakeReport:
            raise AssertionError("openai builder should not be called without api key")

        def fake_build_mock(*_args: object, **_kwargs: object) -> _FakeReport:
            raise AssertionError("mock builder should not be called when fallback disabled")

        with self.assertRaises(RuntimeError) as ctx:
            await build_report_by_runtime(
                request=request,
                effective_style_mode="rational",
                style_mode_source="system_config",
                settings=settings,
                retrieve_contexts_fn=fake_retrieve_contexts,
                build_report_with_openai_fn=fake_build_openai,
                build_mock_report_fn=fake_build_mock,
            )
        self.assertIn("openai runtime missing OPENAI_API_KEY", str(ctx.exception))

    async def test_build_report_by_runtime_should_build_milvus_config_when_enabled(self) -> None:
        settings = _build_settings(
            provider=PROVIDER_MOCK,
            rag_backend=RAG_BACKEND_MILVUS,
            rag_milvus_uri="http://milvus:19530",
            rag_milvus_collection="judge_kb",
            rag_milvus_search_limit=33,
            rag_milvus_metric_type="IP",
            openai_api_key="sk-test",
        )
        request = _build_request()
        calls: dict[str, object] = {}

        def fake_retrieve_contexts(_req: object, **kwargs: object) -> list[RetrievedContext]:
            calls["milvus_config"] = kwargs["milvus_config"]
            return []

        async def fake_build_openai(**_kwargs: object) -> _FakeReport:
            raise AssertionError("openai builder should not be called in mock provider")

        def fake_build_mock(*_args: object, **_kwargs: object) -> _FakeReport:
            return _FakeReport(payload={"provider": "mock"})

        report = await build_report_by_runtime(
            request=request,
            effective_style_mode="rational",
            style_mode_source="system_config",
            settings=settings,
            retrieve_contexts_fn=fake_retrieve_contexts,
            build_report_with_openai_fn=fake_build_openai,
            build_mock_report_fn=fake_build_mock,
        )

        milvus_config = calls["milvus_config"]
        self.assertIsNotNone(milvus_config)
        self.assertEqual(milvus_config.uri, "http://milvus:19530")
        self.assertEqual(milvus_config.collection, "judge_kb")
        self.assertEqual(milvus_config.metric_type, "IP")
        self.assertEqual(milvus_config.search_limit, 33)
        self.assertEqual(report.payload["ragBackend"], RAG_BACKEND_MILVUS)
        self.assertEqual(report.payload["ragRequestedBackend"], RAG_BACKEND_MILVUS)

    async def test_build_report_by_runtime_should_fallback_rag_backend_to_file_when_milvus_embedding_key_missing(
        self,
    ) -> None:
        settings = _build_settings(
            provider=PROVIDER_MOCK,
            rag_backend=RAG_BACKEND_MILVUS,
            rag_milvus_uri="http://milvus:19530",
            rag_milvus_collection="judge_kb",
            openai_api_key="",
        )
        request = _build_request()
        calls: dict[str, object] = {}

        def fake_retrieve_contexts(_req: object, **kwargs: object) -> list[RetrievedContext]:
            calls["backend"] = kwargs["backend"]
            calls["milvus_config"] = kwargs["milvus_config"]
            return []

        async def fake_build_openai(**_kwargs: object) -> _FakeReport:
            raise AssertionError("openai builder should not be called in mock provider")

        def fake_build_mock(*_args: object, **_kwargs: object) -> _FakeReport:
            return _FakeReport(payload={"provider": "mock"})

        report = await build_report_by_runtime(
            request=request,
            effective_style_mode="rational",
            style_mode_source="system_config",
            settings=settings,
            retrieve_contexts_fn=fake_retrieve_contexts,
            build_report_with_openai_fn=fake_build_openai,
            build_mock_report_fn=fake_build_mock,
        )

        self.assertEqual(calls["backend"], "file")
        self.assertIsNone(calls["milvus_config"])
        self.assertEqual(report.payload["ragRequestedBackend"], RAG_BACKEND_MILVUS)
        self.assertEqual(report.payload["ragBackend"], "file")
        self.assertEqual(
            report.payload["ragBackendFallbackReason"],
            "missing_openai_api_key_for_milvus_embedding",
        )
        self.assertEqual(report.payload["errorCodes"], [ERROR_RAG_UNAVAILABLE])


if __name__ == "__main__":
    unittest.main()
