import unittest
from datetime import datetime, timezone

from app.app_factory import create_app, create_default_app, create_runtime, require_internal_key
from app.models import FinalDispatchRequest, PhaseDispatchMessage, PhaseDispatchRequest
from app.settings import Settings
from fastapi import HTTPException


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
        "topic_memory_limit": 5,
        "topic_memory_min_evidence_refs": 1,
        "topic_memory_min_rationale_chars": 20,
        "topic_memory_min_quality_score": 0.55,
        "runtime_retry_max_attempts": 2,
        "runtime_retry_backoff_ms": 200,
        "compliance_block_enabled": True,
    }
    base.update(overrides)
    return Settings(**base)


def _build_phase_request(
    *, job_id: int = 101, idempotency_key: str = "phase-key-101"
) -> PhaseDispatchRequest:
    now = datetime.now(timezone.utc)
    return PhaseDispatchRequest(
        job_id=job_id,
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
        rubric_version="v3",
        judge_policy_version="v3-default",
        topic_domain="tft",
        retrieval_profile="hybrid_v1",
        trace_id=f"trace-phase-{job_id}",
        idempotency_key=idempotency_key,
    )


def _build_final_request(
    *, job_id: int = 202, idempotency_key: str = "final-key-202"
) -> FinalDispatchRequest:
    return FinalDispatchRequest(
        job_id=job_id,
        scope_id=1,
        session_id=2,
        phase_start_no=1,
        phase_end_no=1,
        rubric_version="v3",
        judge_policy_version="v3-default",
        topic_domain="tft",
        trace_id=f"trace-final-{job_id}",
        idempotency_key=idempotency_key,
    )


def _route_endpoint(app, path: str):
    for route in app.routes:
        if getattr(route, "path", "") == path:
            return route.endpoint
    raise AssertionError(f"route not found: {path}")


class AppFactoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_require_internal_key_should_validate_header(self) -> None:
        settings = _build_settings(ai_internal_key="expected")

        with self.assertRaises(HTTPException) as ctx_missing:
            require_internal_key(settings, None)
        self.assertEqual(ctx_missing.exception.status_code, 401)
        self.assertEqual(ctx_missing.exception.detail, "missing x-ai-internal-key")

        with self.assertRaises(HTTPException) as ctx_invalid:
            require_internal_key(settings, "wrong")
        self.assertEqual(ctx_invalid.exception.status_code, 401)
        self.assertEqual(ctx_invalid.exception.detail, "invalid x-ai-internal-key")

        require_internal_key(settings, " expected ")

    async def test_create_app_should_expose_v3_routes_only(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        paths = {getattr(route, "path", "") for route in app.routes}

        self.assertIn("/internal/judge/v3/phase/dispatch", paths)
        self.assertIn("/internal/judge/v3/final/dispatch", paths)
        self.assertNotIn("/internal/judge/dispatch", paths)

    async def test_phase_dispatch_should_callback_and_support_idempotent_replay(self) -> None:
        phase_callback_calls: list[tuple[int, dict]] = []

        async def fake_phase_callback(*, cfg: object, job_id: int, payload: dict) -> None:
            phase_callback_calls.append((job_id, payload))

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=fake_phase_callback,
            callback_final_report_impl=fake_phase_callback,
        )
        app = create_app(runtime)
        endpoint = _route_endpoint(app, "/internal/judge/v3/phase/dispatch")

        req = _build_phase_request(job_id=1001, idempotency_key="phase:1001")
        first = await endpoint(request=req, x_ai_internal_key=runtime.settings.ai_internal_key)
        self.assertTrue(first["accepted"])
        self.assertEqual(first["dispatchType"], "phase")
        self.assertEqual(len(phase_callback_calls), 1)

        replay = await endpoint(request=req, x_ai_internal_key=runtime.settings.ai_internal_key)
        self.assertTrue(replay["idempotentReplay"])
        self.assertEqual(len(phase_callback_calls), 1)

    async def test_final_dispatch_should_use_phase_receipts_and_callback(self) -> None:
        phase_callback_calls: list[tuple[int, dict]] = []
        final_callback_calls: list[tuple[int, dict]] = []

        async def fake_phase_callback(*, cfg: object, job_id: int, payload: dict) -> None:
            phase_callback_calls.append((job_id, payload))

        async def fake_final_callback(*, cfg: object, job_id: int, payload: dict) -> None:
            final_callback_calls.append((job_id, payload))

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=fake_phase_callback,
            callback_final_report_impl=fake_final_callback,
        )
        app = create_app(runtime)
        phase_endpoint = _route_endpoint(app, "/internal/judge/v3/phase/dispatch")
        final_endpoint = _route_endpoint(app, "/internal/judge/v3/final/dispatch")

        phase_req = _build_phase_request(job_id=2001, idempotency_key="phase:2001")
        await phase_endpoint(request=phase_req, x_ai_internal_key=runtime.settings.ai_internal_key)
        self.assertEqual(len(phase_callback_calls), 1)

        final_req = _build_final_request(job_id=2002, idempotency_key="final:2002")
        result = await final_endpoint(
            request=final_req, x_ai_internal_key=runtime.settings.ai_internal_key
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(result["dispatchType"], "final")
        self.assertEqual(len(final_callback_calls), 1)
        self.assertEqual(final_callback_calls[0][0], 2002)
        self.assertIn("winner", final_callback_calls[0][1])

    async def test_phase_dispatch_should_mark_callback_failed_receipt_when_callback_raises(
        self,
    ) -> None:
        async def failing_phase_callback(*, cfg: object, job_id: int, payload: dict) -> None:
            raise RuntimeError("phase-callback-down")

        runtime = create_runtime(
            settings=_build_settings(runtime_retry_max_attempts=1),
            callback_phase_report_impl=failing_phase_callback,
            callback_final_report_impl=failing_phase_callback,
        )
        app = create_app(runtime)
        phase_endpoint = _route_endpoint(app, "/internal/judge/v3/phase/dispatch")
        receipt_endpoint = _route_endpoint(app, "/internal/judge/v3/phase/jobs/{job_id}/receipt")

        req = _build_phase_request(job_id=3001, idempotency_key="phase:3001")
        with self.assertRaises(HTTPException) as ctx:
            await phase_endpoint(request=req, x_ai_internal_key=runtime.settings.ai_internal_key)
        self.assertEqual(ctx.exception.status_code, 502)
        self.assertIn("phase_callback_failed", str(ctx.exception.detail))

        receipt = await receipt_endpoint(
            job_id=3001,
            x_ai_internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(receipt["status"], "callback_failed")

    async def test_create_default_app_should_be_constructible(self) -> None:
        app = create_default_app(load_settings_fn=_build_settings)
        self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main()
