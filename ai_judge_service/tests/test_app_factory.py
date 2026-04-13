import unittest
from datetime import datetime, timezone

from app.app_factory import create_app, create_default_app, create_runtime, require_internal_key
from app.models import FinalDispatchRequest, PhaseDispatchMessage, PhaseDispatchRequest
from app.settings import Settings
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient


def _build_settings(**overrides: object) -> Settings:
    base = {
        "ai_internal_key": "k",
        "chat_server_base_url": "http://chat",
        "phase_report_path_template": "/r/phase/{job_id}",
        "final_report_path_template": "/r/final/{job_id}",
        "phase_failed_path_template": "/f/phase/{job_id}",
        "final_failed_path_template": "/f/final/{job_id}",
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
        "db_url": "sqlite+aiosqlite:///./ai_judge_service.db",
        "db_echo": False,
        "db_pool_size": 10,
        "db_max_overflow": 20,
        "db_auto_create_schema": True,
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


class AppFactoryTests(unittest.IsolatedAsyncioTestCase):
    async def _post_json(
        self,
        *,
        app,
        path: str,
        payload: dict,
        internal_key: str,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                path,
                json=payload,
                headers={"x-ai-internal-key": internal_key},
            )

    async def _get(self, *, app, path: str, internal_key: str):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(
                path,
                headers={"x-ai-internal-key": internal_key},
            )

    async def _post(self, *, app, path: str, internal_key: str):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                path,
                headers={"x-ai-internal-key": internal_key},
            )

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
            callback_phase_failed_impl=fake_phase_callback,
            callback_final_failed_impl=fake_phase_callback,
        )
        app = create_app(runtime)

        req = _build_phase_request(job_id=1001, idempotency_key="phase:1001")
        first_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(first_resp.status_code, 200)
        first = first_resp.json()
        self.assertTrue(first["accepted"])
        self.assertEqual(first["dispatchType"], "phase")
        self.assertEqual(len(phase_callback_calls), 1)
        phase_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=1001)
        self.assertIsNotNone(phase_job)
        assert phase_job is not None
        self.assertEqual(phase_job.status, "completed")
        phase_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=1001)
        self.assertEqual(
            [row.event_type for row in phase_events][-3:],
            ["job_registered", "status_changed", "status_changed"],
        )
        self.assertEqual(phase_events[-1].payload.get("toStatus"), "completed")

        replay_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(replay_resp.status_code, 200)
        replay = replay_resp.json()
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
            callback_phase_failed_impl=fake_phase_callback,
            callback_final_failed_impl=fake_final_callback,
        )
        app = create_app(runtime)

        phase_req = _build_phase_request(job_id=2001, idempotency_key="phase:2001")
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)
        self.assertEqual(len(phase_callback_calls), 1)

        final_req = _build_final_request(job_id=2002, idempotency_key="final:2002")
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)
        result = final_resp.json()
        self.assertTrue(result["accepted"])
        self.assertEqual(result["dispatchType"], "final")
        self.assertEqual(len(final_callback_calls), 1)
        self.assertEqual(final_callback_calls[0][0], 2002)
        self.assertIn("winner", final_callback_calls[0][1])
        phase_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=2001)
        final_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=2002)
        self.assertIsNotNone(phase_job)
        self.assertIsNotNone(final_job)
        assert phase_job is not None and final_job is not None
        self.assertEqual(phase_job.status, "completed")
        self.assertEqual(final_job.status, "completed")

    async def test_phase_dispatch_should_mark_callback_failed_receipt_when_callback_raises(
        self,
    ) -> None:
        async def failing_phase_callback(*, cfg: object, job_id: int, payload: dict) -> None:
            raise RuntimeError("phase-callback-down")

        async def noop_failed_callback(*, cfg: object, job_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(runtime_retry_max_attempts=1),
            callback_phase_report_impl=failing_phase_callback,
            callback_final_report_impl=failing_phase_callback,
            callback_phase_failed_impl=noop_failed_callback,
            callback_final_failed_impl=noop_failed_callback,
        )
        app = create_app(runtime)

        req = _build_phase_request(job_id=3001, idempotency_key="phase:3001")
        failed_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(failed_resp.status_code, 502)
        self.assertIn("phase_callback_failed", failed_resp.text)

        receipt_resp = await self._get(
            app=app,
            path="/internal/judge/v3/phase/jobs/3001/receipt",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(receipt_resp.status_code, 200)
        receipt = receipt_resp.json()
        self.assertEqual(receipt["status"], "callback_failed")
        phase_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=3001)
        self.assertIsNotNone(phase_job)
        assert phase_job is not None
        self.assertEqual(phase_job.status, "failed")

    async def test_replay_post_should_prefer_final_receipt_when_auto(self) -> None:
        phase_calls: list[tuple[int, dict]] = []
        final_calls: list[tuple[int, dict]] = []

        async def phase_callback(*, cfg: object, job_id: int, payload: dict) -> None:
            phase_calls.append((job_id, payload))

        async def final_callback(*, cfg: object, job_id: int, payload: dict) -> None:
            final_calls.append((job_id, payload))

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=phase_callback,
            callback_final_report_impl=final_callback,
            callback_phase_failed_impl=phase_callback,
            callback_final_failed_impl=final_callback,
        )
        app = create_app(runtime)

        phase_req = _build_phase_request(job_id=5001, idempotency_key="phase:5001")
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(job_id=5001, idempotency_key="final:5001")
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)
        callback_total_before_replay = len(phase_calls) + len(final_calls)

        replay_resp = await self._post(
            app=app,
            path="/internal/judge/jobs/5001/replay?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(replay_resp.status_code, 200)
        replay_payload = replay_resp.json()
        self.assertEqual(replay_payload["dispatchType"], "final")
        self.assertIn("reportPayload", replay_payload)
        self.assertIn("debateSummary", replay_payload["reportPayload"])
        self.assertEqual(callback_total_before_replay, len(phase_calls) + len(final_calls))

    async def test_receipt_route_should_fallback_to_fact_repository_when_trace_missing(self) -> None:
        async def noop_callback(*, cfg: object, job_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)

        req = _build_phase_request(job_id=7001, idempotency_key="phase:7001")
        dispatch_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(dispatch_resp.status_code, 200)

        fact_receipt = await runtime.workflow_runtime.facts.get_dispatch_receipt(
            dispatch_type="phase",
            job_id=7001,
        )
        self.assertIsNotNone(fact_receipt)
        assert fact_receipt is not None
        self.assertEqual(fact_receipt.status, "reported")

        runtime.trace_store.get_dispatch_receipt = lambda **kwargs: None  # type: ignore[attr-defined]
        receipt_resp = await self._get(
            app=app,
            path="/internal/judge/v3/phase/jobs/7001/receipt",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(receipt_resp.status_code, 200)
        self.assertEqual(receipt_resp.json()["status"], "reported")

    async def test_replay_post_should_persist_replay_record_to_fact_repository(self) -> None:
        phase_calls: list[tuple[int, dict]] = []
        final_calls: list[tuple[int, dict]] = []

        async def phase_callback(*, cfg: object, job_id: int, payload: dict) -> None:
            phase_calls.append((job_id, payload))

        async def final_callback(*, cfg: object, job_id: int, payload: dict) -> None:
            final_calls.append((job_id, payload))

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=phase_callback,
            callback_final_report_impl=final_callback,
            callback_phase_failed_impl=phase_callback,
            callback_final_failed_impl=final_callback,
        )
        app = create_app(runtime)
        before_rows = await runtime.workflow_runtime.facts.list_replay_records(
            job_id=7101,
            limit=200,
        )
        before_count = len(before_rows)

        phase_req = _build_phase_request(job_id=7101, idempotency_key="phase:7101")
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(job_id=7101, idempotency_key="final:7101")
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        replay_resp = await self._post(
            app=app,
            path="/internal/judge/jobs/7101/replay?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(replay_resp.status_code, 200)

        replay_rows = await runtime.workflow_runtime.facts.list_replay_records(
            job_id=7101,
            limit=200,
        )
        self.assertEqual(len(replay_rows), before_count + 1)
        self.assertEqual(replay_rows[0].dispatch_type, "final")
        self.assertIn(replay_rows[0].winner, {"pro", "con", "draw"})

    async def test_alert_ack_should_sync_status_to_fact_repository(self) -> None:
        async def noop_callback(*, cfg: object, job_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)
        alert = runtime.trace_store.upsert_audit_alert(
            job_id=7201,
            scope_id=1,
            trace_id="trace-alert-7201",
            alert_type="test_alert",
            severity="warning",
            title="test",
            message="test message",
            details={"k": "v"},
        )

        ack_resp = await self._post(
            app=app,
            path=f"/internal/judge/jobs/7201/alerts/{alert.alert_id}/ack",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(ack_resp.status_code, 200)
        self.assertEqual(ack_resp.json()["status"], "acked")

        fact_alerts = await runtime.workflow_runtime.facts.list_audit_alerts(
            job_id=7201,
            limit=10,
        )
        self.assertEqual(len(fact_alerts), 1)
        self.assertEqual(fact_alerts[0].alert_id, alert.alert_id)
        self.assertEqual(fact_alerts[0].status, "acked")

    async def test_blindization_reject_should_return_422_and_trigger_failed_callback(self) -> None:
        failed_calls: list[tuple[int, dict]] = []

        async def phase_callback(*, cfg: object, job_id: int, payload: dict) -> None:
            return None

        async def failed_callback(*, cfg: object, job_id: int, payload: dict) -> None:
            failed_calls.append((job_id, payload))

        runtime = create_runtime(
            settings=_build_settings(runtime_retry_max_attempts=1),
            callback_phase_report_impl=phase_callback,
            callback_final_report_impl=phase_callback,
            callback_phase_failed_impl=failed_callback,
            callback_final_failed_impl=failed_callback,
        )
        app = create_app(runtime)
        bad_payload = _build_phase_request(job_id=6001, idempotency_key="phase:6001").model_dump(
            mode="json"
        )
        bad_payload["messages"][0]["user_id"] = 99

        bad_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=bad_payload,
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_resp.status_code, 422)
        self.assertIn("input_not_blinded", bad_resp.text)
        self.assertEqual(len(failed_calls), 1)
        self.assertEqual(failed_calls[0][0], 6001)
        self.assertEqual(failed_calls[0][1]["errorCode"], "input_not_blinded")

    async def test_create_default_app_should_be_constructible(self) -> None:
        app = create_default_app(load_settings_fn=_build_settings)
        self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main()
