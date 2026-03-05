import unittest
from datetime import datetime, timezone

from fastapi import HTTPException

from app.app_factory import (
    create_app,
    create_default_app,
    create_runtime,
    require_internal_key,
)
from app.models import (
    DispatchJob,
    DispatchMessage,
    DispatchSession,
    DispatchTopic,
    JudgeDispatchRequest,
)
from app.runtime_errors import JudgeRuntimeError
from app.settings import Settings


class _FakeReport:
    def __init__(self) -> None:
        self.winner = "pro"
        self.needs_draw_vote = False
        self.payload = {
            "provider": "openai",
            "evidenceRefs": [{"messageId": 1, "reason": "test"}],
            "judgeAudit": {
                "promptHash": "hash-1",
                "model": "gpt-4.1-mini",
                "rubricVersion": "v1",
                "retrievalSnapshot": [],
                "degradationLevel": 0,
            },
        }
        self.rationale = "test rationale with enough chars"

    def model_dump(self, *, mode: str = "python") -> dict:
        return {
            "winner": self.winner,
            "needsDrawVote": self.needs_draw_vote,
            "rationale": self.rationale,
            "payload": self.payload,
            "stage_summaries": [
                {
                    "stage_no": 1,
                    "from_message_id": 1,
                    "to_message_id": 1,
                    "pro_score": 30,
                    "con_score": 28,
                    "summary": {"stageFocus": "opening"},
                }
            ],
            "mode": mode,
        }


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


def _build_request() -> JudgeDispatchRequest:
    now = datetime.now(timezone.utc)
    return JudgeDispatchRequest(
        job=DispatchJob(
            job_id=1,
            ws_id=1,
            session_id=2,
            requested_by=1,
            style_mode="rational",
            rejudge_triggered=False,
            requested_at=now,
        ),
        session=DispatchSession(
            status="judging",
            scheduled_start_at=now,
            actual_start_at=now,
            end_at=now,
        ),
        topic=DispatchTopic(
            title="test",
            description="desc",
            category="game",
            stance_pro="pro",
            stance_con="con",
            context_seed=None,
        ),
        messages=[
            DispatchMessage(
                message_id=1,
                speaker_tag="pro_1",
                user_id=None,
                side="pro",
                content="hello",
                created_at=now,
            )
        ],
        message_window_size=100,
        rubric_version="v1",
    )


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

    async def test_create_runtime_should_bind_callbacks_and_adapter(self) -> None:
        settings = _build_settings(
            ai_internal_key="k2",
            process_delay_ms=120,
            judge_style_mode="entertaining",
        )
        calls: dict[str, object] = {}

        async def fake_callback_report(*, cfg: object, job_id: int, payload: dict) -> None:
            calls["report"] = (cfg, job_id, payload)

        async def fake_callback_failed(*, cfg: object, job_id: int, error_message: str) -> None:
            calls["failed"] = (cfg, job_id, error_message)

        async def fake_runtime_builder(**kwargs: object) -> _FakeReport:
            calls["runtime"] = kwargs
            return _FakeReport()

        runtime = create_runtime(
            settings=settings,
            callback_report_impl=fake_callback_report,
            callback_failed_impl=fake_callback_failed,
            build_report_by_runtime_fn=fake_runtime_builder,
        )
        self.assertEqual(runtime.dispatch_runtime_cfg.process_delay_ms, 120)
        self.assertEqual(runtime.dispatch_runtime_cfg.judge_style_mode, "entertaining")

        await runtime.callback_report_fn(11, {"a": 1})
        await runtime.callback_failed_fn(11, "err")
        report_call = calls["report"]
        failed_call = calls["failed"]
        self.assertEqual(report_call[1], 11)
        self.assertEqual(report_call[2], {"a": 1})
        self.assertEqual(failed_call[1], 11)
        self.assertEqual(failed_call[2], "err")

        request = _build_request()
        result = await runtime.build_report_by_runtime_adapter(
            request,
            "rational",
            "system_config",
        )
        self.assertIsInstance(result, _FakeReport)
        runtime_call = calls["runtime"]
        self.assertEqual(runtime_call["request"], request)
        self.assertEqual(runtime_call["effective_style_mode"], "rational")
        self.assertEqual(runtime_call["style_mode_source"], "system_config")
        self.assertEqual(runtime_call["settings"], settings)

    async def test_create_app_should_register_routes_and_delegate_dispatch(self) -> None:
        settings = _build_settings(ai_internal_key="k3")
        request = _build_request()
        callback_report_calls: list[tuple[int, dict]] = []
        callback_failed_calls: list[tuple[int, str]] = []

        async def fake_runtime_builder(**_kwargs: object) -> _FakeReport:
            return _FakeReport()

        async def fake_callback_report(*, cfg: object, job_id: int, payload: dict) -> None:
            callback_report_calls.append((job_id, payload))

        async def fake_callback_failed(*, cfg: object, job_id: int, error_message: str) -> None:
            callback_failed_calls.append((job_id, error_message))

        async def fake_sleep(_seconds: float) -> None:
            return None

        runtime = create_runtime(
            settings=settings,
            build_report_by_runtime_fn=fake_runtime_builder,
            callback_report_impl=fake_callback_report,
            callback_failed_impl=fake_callback_failed,
            sleep_fn=fake_sleep,
        )
        app = create_app(runtime)
        paths = {route.path for route in app.routes if hasattr(route, "path")}
        self.assertIn("/healthz", paths)
        self.assertIn("/internal/judge/dispatch", paths)
        self.assertIn("/internal/judge/jobs/{job_id}/trace", paths)
        self.assertIn("/internal/judge/jobs/{job_id}/replay", paths)
        self.assertIn("/internal/judge/jobs/{job_id}/replay/report", paths)
        self.assertIn("/internal/judge/rag/diagnostics", paths)

        dispatch_route = next(route for route in app.routes if getattr(route, "path", "") == "/internal/judge/dispatch")
        endpoint = dispatch_route.endpoint

        with self.assertRaises(HTTPException):
            await endpoint(request=request, x_ai_internal_key=None)

        result = await endpoint(request=request, x_ai_internal_key="k3")
        self.assertTrue(result["accepted"])
        self.assertEqual(result["winner"], "pro")
        self.assertEqual(result["provider"], "openai")
        self.assertEqual(len(callback_report_calls), 1)
        self.assertEqual(callback_report_calls[0][0], 1)
        self.assertEqual(callback_failed_calls, [])

        trace_route = next(
            route for route in app.routes if getattr(route, "path", "") == "/internal/judge/jobs/{job_id}/trace"
        )
        trace = await trace_route.endpoint(job_id=1, x_ai_internal_key="k3")
        self.assertEqual(trace["jobId"], 1)
        self.assertEqual(trace["status"], "completed")
        self.assertTrue(trace["reportSummary"]["topicMemoryAudit"]["accepted"])
        topic_memory_rows = runtime.trace_store.list_topic_memory(
            topic_domain="default",
            rubric_version="v1",
            limit=3,
        )
        self.assertEqual(len(topic_memory_rows), 1)
        self.assertEqual(topic_memory_rows[0].job_id, 1)

        rag_route = next(
            route for route in app.routes if getattr(route, "path", "") == "/internal/judge/rag/diagnostics"
        )
        rag = await rag_route.endpoint(job_id=1, x_ai_internal_key="k3")
        self.assertEqual(rag["jobId"], 1)

        replay_report_route = next(
            route for route in app.routes if getattr(route, "path", "") == "/internal/judge/jobs/{job_id}/replay/report"
        )
        replay_report = await replay_report_route.endpoint(job_id=1, x_ai_internal_key="k3")
        self.assertEqual(replay_report["jobId"], 1)
        self.assertEqual(replay_report["status"], "completed")
        self.assertEqual(replay_report["judgeAudit"]["promptHash"], "hash-1")
        self.assertEqual(replay_report["pipeline"]["finalWinner"], "pro")
        self.assertEqual(len(replay_report["pipeline"]["stageSummaries"]), 1)

    async def test_dispatch_should_reject_unblinded_user_id(self) -> None:
        settings = _build_settings(ai_internal_key="k4")
        request = _build_request()
        request.messages[0].user_id = 123  # type: ignore[misc]

        async def fake_runtime_builder(**_kwargs: object) -> _FakeReport:
            return _FakeReport()

        async def fake_callback_report(*, cfg: object, job_id: int, payload: dict) -> None:
            return None

        async def fake_callback_failed(*, cfg: object, job_id: int, error_message: str) -> None:
            return None

        runtime = create_runtime(
            settings=settings,
            build_report_by_runtime_fn=fake_runtime_builder,
            callback_report_impl=fake_callback_report,
            callback_failed_impl=fake_callback_failed,
        )
        app = create_app(runtime)
        dispatch_route = next(route for route in app.routes if getattr(route, "path", "") == "/internal/judge/dispatch")

        with self.assertRaises(HTTPException) as ctx:
            await dispatch_route.endpoint(request=request, x_ai_internal_key="k4")
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail, "unblinded_user_id_in_messages")

    async def test_dispatch_should_support_idempotency_replay(self) -> None:
        settings = _build_settings(ai_internal_key="k5")
        request = _build_request()
        request.idempotency_key = "same-key"
        call_counter = {"n": 0}

        async def fake_runtime_builder(**_kwargs: object) -> _FakeReport:
            call_counter["n"] += 1
            return _FakeReport()

        async def fake_callback_report(*, cfg: object, job_id: int, payload: dict) -> None:
            return None

        async def fake_callback_failed(*, cfg: object, job_id: int, error_message: str) -> None:
            return None

        runtime = create_runtime(
            settings=settings,
            build_report_by_runtime_fn=fake_runtime_builder,
            callback_report_impl=fake_callback_report,
            callback_failed_impl=fake_callback_failed,
        )
        app = create_app(runtime)
        dispatch_route = next(route for route in app.routes if getattr(route, "path", "") == "/internal/judge/dispatch")

        first = await dispatch_route.endpoint(request=request, x_ai_internal_key="k5")
        second = await dispatch_route.endpoint(request=request, x_ai_internal_key="k5")
        self.assertTrue(first["accepted"])
        self.assertTrue(second["accepted"])
        self.assertTrue(second["idempotentReplay"])
        self.assertEqual(call_counter["n"], 1)

    async def test_dispatch_should_reject_idempotency_pending_conflict(self) -> None:
        settings = _build_settings(ai_internal_key="k5c")
        request = _build_request()
        request.idempotency_key = "same-key-pending"

        async def fake_runtime_builder(**_kwargs: object) -> _FakeReport:
            raise AssertionError("pending conflict should short-circuit before runtime")

        async def fake_callback_report(*, cfg: object, job_id: int, payload: dict) -> None:
            return None

        async def fake_callback_failed(*, cfg: object, job_id: int, error_message: str) -> None:
            return None

        runtime = create_runtime(
            settings=settings,
            build_report_by_runtime_fn=fake_runtime_builder,
            callback_report_impl=fake_callback_report,
            callback_failed_impl=fake_callback_failed,
        )
        runtime.trace_store.set_idempotency_pending(
            key="same-key-pending",
            job_id=request.job.job_id,
            ttl_secs=3600,
        )
        app = create_app(runtime)
        dispatch_route = next(route for route in app.routes if getattr(route, "path", "") == "/internal/judge/dispatch")

        with self.assertRaises(HTTPException) as ctx:
            await dispatch_route.endpoint(request=request, x_ai_internal_key="k5c")
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail, "idempotency_conflict:judge_dispatch")

    async def test_dispatch_should_clear_idempotency_on_failed_and_allow_retry(self) -> None:
        settings = _build_settings(ai_internal_key="k5d")
        request = _build_request()
        request.idempotency_key = "retry-after-failed"
        call_counter = {"n": 0}

        async def fake_runtime_builder(**_kwargs: object) -> _FakeReport:
            call_counter["n"] += 1
            if call_counter["n"] == 1:
                raise JudgeRuntimeError(code="consistency_conflict", message="draw protection conflict")
            return _FakeReport()

        async def fake_callback_report(*, cfg: object, job_id: int, payload: dict) -> None:
            return None

        async def fake_callback_failed(*, cfg: object, job_id: int, error_message: str) -> None:
            return None

        runtime = create_runtime(
            settings=settings,
            build_report_by_runtime_fn=fake_runtime_builder,
            callback_report_impl=fake_callback_report,
            callback_failed_impl=fake_callback_failed,
        )
        app = create_app(runtime)
        dispatch_route = next(route for route in app.routes if getattr(route, "path", "") == "/internal/judge/dispatch")

        first = await dispatch_route.endpoint(request=request, x_ai_internal_key="k5d")
        self.assertEqual(first["status"], "marked_failed")
        self.assertIsNone(runtime.trace_store.get_idempotency("retry-after-failed"))

        second = await dispatch_route.endpoint(request=request, x_ai_internal_key="k5d")
        self.assertTrue(second["accepted"])
        self.assertNotIn("status", second)
        self.assertEqual(call_counter["n"], 2)

    async def test_dispatch_should_skip_low_quality_topic_memory_but_keep_audit(self) -> None:
        settings = _build_settings(
            ai_internal_key="k6",
            topic_memory_min_rationale_chars=100,
        )
        request = _build_request()

        async def fake_runtime_builder(**_kwargs: object) -> _FakeReport:
            return _FakeReport()

        async def fake_callback_report(*, cfg: object, job_id: int, payload: dict) -> None:
            return None

        async def fake_callback_failed(*, cfg: object, job_id: int, error_message: str) -> None:
            return None

        runtime = create_runtime(
            settings=settings,
            build_report_by_runtime_fn=fake_runtime_builder,
            callback_report_impl=fake_callback_report,
            callback_failed_impl=fake_callback_failed,
        )
        app = create_app(runtime)
        dispatch_route = next(route for route in app.routes if getattr(route, "path", "") == "/internal/judge/dispatch")
        trace_route = next(
            route for route in app.routes if getattr(route, "path", "") == "/internal/judge/jobs/{job_id}/trace"
        )

        result = await dispatch_route.endpoint(request=request, x_ai_internal_key="k6")
        self.assertTrue(result["accepted"])
        trace = await trace_route.endpoint(job_id=1, x_ai_internal_key="k6")
        self.assertFalse(trace["reportSummary"]["topicMemoryAudit"]["accepted"])
        self.assertIn("insufficient_rationale_chars", trace["reportSummary"]["topicMemoryAudit"]["rejectReasons"])
        topic_memory_rows = runtime.trace_store.list_topic_memory(
            topic_domain="default",
            rubric_version="v1",
            limit=3,
        )
        self.assertEqual(topic_memory_rows, [])

    async def test_create_default_app_should_use_loader(self) -> None:
        settings = _build_settings(ai_internal_key="loader-key")
        called = {"count": 0}

        def fake_loader() -> Settings:
            called["count"] += 1
            return settings

        app = create_default_app(load_settings_fn=fake_loader)
        self.assertEqual(called["count"], 1)
        self.assertEqual(app.title, "AI Judge Service")


if __name__ == "__main__":
    unittest.main()
