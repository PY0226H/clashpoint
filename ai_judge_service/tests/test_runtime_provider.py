import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from app.rag_retriever import RetrievedContext
from app.runtime_policy import PROVIDER_MOCK, PROVIDER_OPENAI
from app.runtime_provider import build_report_with_provider
from app.settings import Settings


class _FakeReport:
    def __init__(self, payload: dict | None = None) -> None:
        self.payload = payload or {}


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


class RuntimeProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_build_report_with_provider_should_use_openai_path(self) -> None:
        settings = _build_settings(provider=PROVIDER_OPENAI, openai_api_key="sk-test")
        request = _build_request()
        contexts = [RetrievedContext(chunk_id="c1", title="t", source_url="u", content="c", score=0.9)]
        calls: dict[str, object] = {}

        async def fake_openai(**kwargs: object) -> _FakeReport:
            calls["openai_kwargs"] = kwargs
            return _FakeReport(payload={"provider": "openai"})

        def fake_mock(*_args: object, **_kwargs: object) -> _FakeReport:
            raise AssertionError("mock should not be called on openai success")

        report, used_by_model = await build_report_with_provider(
            request=request,
            effective_style_mode="rational",
            style_mode_source="system_config",
            settings=settings,
            retrieved_contexts=contexts,
            build_report_with_openai_fn=fake_openai,
            build_mock_report_fn=fake_mock,
        )
        self.assertTrue(used_by_model)
        self.assertEqual(report.payload["provider"], "openai")
        openai_kwargs = calls["openai_kwargs"]
        self.assertEqual(openai_kwargs["request"], request)
        self.assertEqual(openai_kwargs["retrieved_contexts"], contexts)
        self.assertEqual(openai_kwargs["cfg"].max_stage_agent_chunks, settings.stage_agent_max_chunks)
        self.assertEqual(openai_kwargs["cfg"].reflection_enabled, settings.reflection_enabled)
        self.assertEqual(openai_kwargs["cfg"].graph_v2_enabled, settings.graph_v2_enabled)
        self.assertEqual(openai_kwargs["cfg"].reflection_policy, settings.reflection_policy)
        self.assertEqual(
            openai_kwargs["cfg"].reflection_low_margin_threshold,
            settings.reflection_low_margin_threshold,
        )
        self.assertEqual(openai_kwargs["cfg"].fault_injection_nodes, settings.fault_injection_nodes)

    async def test_build_report_with_provider_should_fallback_when_openai_failed(self) -> None:
        settings = _build_settings(provider=PROVIDER_OPENAI, openai_api_key="sk-test", openai_fallback_to_mock=True)
        request = _build_request()

        async def fake_openai(**_kwargs: object) -> _FakeReport:
            raise RuntimeError("openai down")

        def fake_mock(_request: object, **kwargs: object) -> _FakeReport:
            self.assertEqual(kwargs["system_style_mode"], settings.judge_style_mode)
            return _FakeReport(payload={"provider": "mock"})

        report, used_by_model = await build_report_with_provider(
            request=request,
            effective_style_mode="rational",
            style_mode_source="system_config",
            settings=settings,
            retrieved_contexts=[],
            build_report_with_openai_fn=fake_openai,
            build_mock_report_fn=fake_mock,
        )
        self.assertFalse(used_by_model)
        self.assertEqual(report.payload["provider"], "ai-judge-service-mock-fallback")
        self.assertEqual(report.payload["fallbackFrom"], "openai")
        self.assertIn("openai down", report.payload["fallbackReason"])

    async def test_build_report_with_provider_should_raise_when_openai_failed_and_fallback_disabled(self) -> None:
        settings = _build_settings(provider=PROVIDER_OPENAI, openai_api_key="sk-test", openai_fallback_to_mock=False)
        request = _build_request()

        async def fake_openai(**_kwargs: object) -> _FakeReport:
            raise RuntimeError("openai down")

        def fake_mock(*_args: object, **_kwargs: object) -> _FakeReport:
            raise AssertionError("mock should not be called")

        with self.assertRaises(RuntimeError) as ctx:
            await build_report_with_provider(
                request=request,
                effective_style_mode="rational",
                style_mode_source="system_config",
                settings=settings,
                retrieved_contexts=[],
                build_report_with_openai_fn=fake_openai,
                build_mock_report_fn=fake_mock,
            )
        self.assertIn("openai runtime failed", str(ctx.exception))

    async def test_build_report_with_provider_should_mark_missing_key(self) -> None:
        settings = _build_settings(provider=PROVIDER_OPENAI, openai_api_key="")
        request = _build_request()

        async def fake_openai(**_kwargs: object) -> _FakeReport:
            raise AssertionError("openai should not be called without key")

        def fake_mock(_request: object, **kwargs: object) -> _FakeReport:
            self.assertEqual(kwargs["system_style_mode"], settings.judge_style_mode)
            return _FakeReport(payload={"provider": "mock"})

        report, used_by_model = await build_report_with_provider(
            request=request,
            effective_style_mode="rational",
            style_mode_source="system_config",
            settings=settings,
            retrieved_contexts=[],
            build_report_with_openai_fn=fake_openai,
            build_mock_report_fn=fake_mock,
        )
        self.assertFalse(used_by_model)
        self.assertEqual(report.payload["provider"], "ai-judge-service-mock-missing-openai-key")
        self.assertEqual(report.payload["fallbackFrom"], "openai")
        self.assertEqual(report.payload["fallbackReason"], "missing OPENAI_API_KEY")

    async def test_build_report_with_provider_should_raise_when_missing_key_and_fallback_disabled(self) -> None:
        settings = _build_settings(
            provider=PROVIDER_OPENAI,
            openai_api_key="",
            openai_fallback_to_mock=False,
        )
        request = _build_request()

        async def fake_openai(**_kwargs: object) -> _FakeReport:
            raise AssertionError("openai should not be called without key")

        def fake_mock(*_args: object, **_kwargs: object) -> _FakeReport:
            raise AssertionError("mock should not be called when fallback is disabled")

        with self.assertRaises(RuntimeError) as ctx:
            await build_report_with_provider(
                request=request,
                effective_style_mode="rational",
                style_mode_source="system_config",
                settings=settings,
                retrieved_contexts=[],
                build_report_with_openai_fn=fake_openai,
                build_mock_report_fn=fake_mock,
            )
        self.assertIn("openai runtime missing OPENAI_API_KEY", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
