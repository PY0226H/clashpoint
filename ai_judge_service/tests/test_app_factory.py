import unittest
from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import patch

from app.app_factory import create_app, create_default_app, create_runtime, require_internal_key
from app.models import (
    CaseCreateRequest,
    FinalDispatchRequest,
    PhaseDispatchMessage,
    PhaseDispatchRequest,
)
from app.settings import Settings
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient


def _build_settings(**overrides: object) -> Settings:
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
        "db_url": "sqlite+aiosqlite:////tmp/echoisle_ai_judge_service_test.db",
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


def _build_final_request(
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


def _build_case_create_request(
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


def _unique_case_id(seed: int) -> int:
    # 使用时间戳生成本地唯一 case_id，避免 sqlite 测试库跨命令复用导致冲突。
    return int(datetime.now(timezone.utc).timestamp() * 1_000_000) + seed


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
        self.assertIn("/internal/judge/cases", paths)
        self.assertIn("/internal/judge/cases/{case_id}", paths)
        self.assertIn("/internal/judge/policies", paths)
        self.assertIn("/internal/judge/policies/{policy_version}", paths)
        self.assertIn("/internal/judge/registries/prompts", paths)
        self.assertIn("/internal/judge/registries/prompts/{prompt_version}", paths)
        self.assertIn("/internal/judge/registries/tools", paths)
        self.assertIn("/internal/judge/registries/tools/{toolset_version}", paths)
        self.assertIn("/internal/judge/cases/{case_id}/attestation/verify", paths)
        self.assertIn("/internal/judge/cases/{case_id}/trust/commitment", paths)
        self.assertIn("/internal/judge/cases/{case_id}/trust/verdict-attestation", paths)
        self.assertIn("/internal/judge/cases/{case_id}/trust/challenges", paths)
        self.assertIn("/internal/judge/cases/{case_id}/trust/kernel-version", paths)
        self.assertIn("/internal/judge/cases/{case_id}/trust/audit-anchor", paths)
        self.assertNotIn("/internal/judge/dispatch", paths)

    async def test_case_create_should_mark_case_built_and_support_idempotent_replay(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)

        case_id = _unique_case_id(11)
        req = _build_case_create_request(
            case_id=case_id,
            idempotency_key=f"case:{case_id}",
        )
        first_resp = await self._post_json(
            app=app,
            path="/internal/judge/cases",
            payload=req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(first_resp.status_code, 200)
        first_payload = first_resp.json()
        self.assertTrue(first_payload["accepted"])
        self.assertEqual(first_payload["status"], "case_built")
        self.assertEqual(first_payload["caseId"], case_id)
        self.assertEqual(first_payload["workflow"]["status"], "case_built")

        workflow_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=case_id)
        self.assertIsNotNone(workflow_job)
        assert workflow_job is not None
        self.assertEqual(workflow_job.status, "case_built")
        workflow_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=case_id)
        self.assertEqual(workflow_events[0].event_type, "job_registered")
        self.assertGreaterEqual(len(workflow_events), 3)
        self.assertTrue(all(row.event_type == "status_changed" for row in workflow_events[1:]))
        self.assertEqual(workflow_events[-1].payload.get("toStatus"), "case_built")

        replay_resp = await self._post_json(
            app=app,
            path="/internal/judge/cases",
            payload=req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(replay_resp.status_code, 200)
        self.assertTrue(replay_resp.json()["idempotentReplay"])

    async def test_case_create_should_reject_existing_case_with_new_idempotency_key(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)

        case_id = _unique_case_id(22)
        first_req = _build_case_create_request(
            case_id=case_id,
            idempotency_key=f"case:{case_id}:first",
        )
        first_resp = await self._post_json(
            app=app,
            path="/internal/judge/cases",
            payload=first_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(first_resp.status_code, 200)

        second_req = _build_case_create_request(
            case_id=case_id,
            idempotency_key=f"case:{case_id}:second",
        )
        second_resp = await self._post_json(
            app=app,
            path="/internal/judge/cases",
            payload=second_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(second_resp.status_code, 409)
        self.assertIn("case_already_exists", second_resp.text)

    async def test_case_detail_route_should_aggregate_case_snapshot(self) -> None:
        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)

        case_id = _unique_case_id(33)
        case_req = _build_case_create_request(
            case_id=case_id,
            idempotency_key=f"case:{case_id}",
        )
        case_resp = await self._post_json(
            app=app,
            path="/internal/judge/cases",
            payload=case_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(case_resp.status_code, 200)

        phase_req = _build_phase_request(case_id=case_id, idempotency_key=f"phase:{case_id}")
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(case_id=case_id, idempotency_key=f"final:{case_id}")
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        detail_resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(detail_resp.status_code, 200)
        detail_payload = detail_resp.json()
        self.assertEqual(detail_payload["caseId"], case_id)
        self.assertEqual(detail_payload["workflow"]["status"], "callback_reported")
        self.assertEqual(detail_payload["latestDispatchType"], "final")
        self.assertIsNotNone(detail_payload["receipts"]["phase"])
        self.assertIsNotNone(detail_payload["receipts"]["final"])
        self.assertIn(detail_payload["winner"], {"pro", "con", "draw"})
        self.assertIn("verdictContract", detail_payload)
        self.assertEqual(
            detail_payload["verdictContract"]["winner"],
            detail_payload["winner"],
        )
        self.assertIn("trustAttestation", detail_payload["reportPayload"])
        self.assertIn("caseEvidence", detail_payload)
        case_evidence = detail_payload["caseEvidence"]
        self.assertTrue(case_evidence["hasClaimGraph"])
        self.assertTrue(case_evidence["hasEvidenceLedger"])
        self.assertTrue(case_evidence["hasVerdictLedger"])
        self.assertTrue(case_evidence["hasOpinionPack"])
        self.assertTrue(case_evidence["hasTrustAttestation"])
        self.assertIsInstance(case_evidence["claimGraph"], dict)
        self.assertIsInstance(case_evidence["claimGraphSummary"], dict)
        self.assertIsInstance(case_evidence["evidenceLedger"], dict)
        self.assertIsInstance(case_evidence["evidenceLedger"]["entries"], list)
        self.assertIsInstance(case_evidence["verdictLedger"], dict)
        self.assertIsInstance(case_evidence["opinionPack"], dict)
        self.assertIsInstance(case_evidence["policySnapshot"], dict)
        self.assertTrue(str(case_evidence["policyVersion"] or "").strip())
        self.assertIsInstance(case_evidence["promptSnapshot"], dict)
        self.assertTrue(str(case_evidence["promptVersion"] or "").strip())
        self.assertIsInstance(case_evidence["toolSnapshot"], dict)
        self.assertTrue(str(case_evidence["toolsetVersion"] or "").strip())
        self.assertEqual(case_evidence["trustAttestation"]["dispatchType"], "final")
        self.assertIsInstance(case_evidence["fairnessSummary"], dict)
        self.assertIsInstance(case_evidence["verdictEvidenceRefs"], list)
        self.assertTrue(
            all(
                isinstance(item, dict) and str(item.get("evidenceId") or "").strip()
                for item in case_evidence["verdictEvidenceRefs"]
            )
        )
        self.assertIn("auditSummary", case_evidence)
        self.assertEqual(
            case_evidence["auditSummary"]["alertCount"],
            len(case_evidence["auditSummary"]["auditAlerts"]),
        )
        self.assertEqual(detail_payload["judgeCore"]["stage"], "reported")
        self.assertEqual(detail_payload["judgeCore"]["version"], "v1")
        self.assertGreaterEqual(len(detail_payload["events"]), 2)

    async def test_case_detail_route_should_return_404_when_case_missing(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)

        missing_resp = await self._get(
            app=app,
            path="/internal/judge/cases/999901",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(missing_resp.status_code, 404)
        self.assertIn("case_not_found", missing_resp.text)

    async def test_policy_routes_should_return_default_registry_profile(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)

        list_resp = await self._get(
            app=app,
            path="/internal/judge/policies",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(list_resp.status_code, 200)
        payload = list_resp.json()
        self.assertEqual(payload["defaultVersion"], "v3-default")
        self.assertGreaterEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["promptRegistryVersion"], "promptset-v3-default")
        self.assertEqual(payload["items"][0]["toolRegistryVersion"], "toolset-v3-default")
        self.assertEqual(payload["items"][0]["promptVersions"]["claimGraphVersion"], "v1-claim-graph-bootstrap")
        self.assertIn("evidenceMinTotalRefs", payload["items"][0]["fairnessThresholds"])

        detail_resp = await self._get(
            app=app,
            path="/internal/judge/policies/v3-default",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(detail_resp.status_code, 200)
        self.assertEqual(detail_resp.json()["item"]["version"], "v3-default")

        prompt_list_resp = await self._get(
            app=app,
            path="/internal/judge/registries/prompts",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(prompt_list_resp.status_code, 200)
        prompt_list_payload = prompt_list_resp.json()
        self.assertEqual(prompt_list_payload["defaultVersion"], "promptset-v3-default")
        self.assertGreaterEqual(prompt_list_payload["count"], 1)
        self.assertEqual(
            prompt_list_payload["items"][0]["promptVersions"]["claimGraphVersion"],
            "v1-claim-graph-bootstrap",
        )

        prompt_detail_resp = await self._get(
            app=app,
            path="/internal/judge/registries/prompts/promptset-v3-default",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(prompt_detail_resp.status_code, 200)
        self.assertEqual(prompt_detail_resp.json()["item"]["version"], "promptset-v3-default")

        tool_list_resp = await self._get(
            app=app,
            path="/internal/judge/registries/tools",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(tool_list_resp.status_code, 200)
        tool_list_payload = tool_list_resp.json()
        self.assertEqual(tool_list_payload["defaultVersion"], "toolset-v3-default")
        self.assertGreaterEqual(tool_list_payload["count"], 1)
        self.assertIn("claim_graph_builder", tool_list_payload["items"][0]["toolIds"])

        tool_detail_resp = await self._get(
            app=app,
            path="/internal/judge/registries/tools/toolset-v3-default",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(tool_detail_resp.status_code, 200)
        self.assertEqual(tool_detail_resp.json()["item"]["version"], "toolset-v3-default")

    async def test_phase_dispatch_should_reject_unknown_policy_version(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        req = _build_phase_request(
            case_id=8101,
            idempotency_key="phase:8101",
            judge_policy_version="v9-not-exist",
        )

        bad_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_resp.status_code, 422)
        self.assertIn("unknown_judge_policy_version", bad_resp.text)

    async def test_phase_dispatch_should_reject_unknown_prompt_registry_version(self) -> None:
        runtime = create_runtime(
            settings=_build_settings(
                policy_registry_json=(
                    '{"defaultVersion":"v3-default","profiles":[{"version":"v3-default","rubricVersion":"v3",'
                    '"topicDomain":"tft","promptRegistryVersion":"promptset-missing"}]}'
                )
            )
        )
        app = create_app(runtime)
        req = _build_phase_request(
            case_id=8105,
            idempotency_key="phase:8105",
            judge_policy_version="v3-default",
        )

        bad_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_resp.status_code, 422)
        self.assertIn("unknown_prompt_registry_version", bad_resp.text)

    async def test_final_dispatch_should_reject_policy_rubric_mismatch(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        req = _build_final_request(
            case_id=8102,
            idempotency_key="final:8102",
            rubric_version="v2",
            judge_policy_version="v3-default",
        )

        bad_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_resp.status_code, 422)
        self.assertIn("judge_policy_rubric_mismatch", bad_resp.text)

    async def test_create_runtime_should_include_agent_runtime_shell_profiles(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        profiles = runtime.agent_runtime.list_profiles()
        kinds = [row.kind for row in profiles]
        self.assertEqual(kinds, ["judge", "npc_coach", "room_qa"])

    async def test_phase_dispatch_should_callback_and_support_idempotent_replay(self) -> None:
        phase_callback_calls: list[tuple[int, dict]] = []

        async def fake_phase_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            phase_callback_calls.append((case_id, payload))

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=fake_phase_callback,
            callback_final_report_impl=fake_phase_callback,
            callback_phase_failed_impl=fake_phase_callback,
            callback_final_failed_impl=fake_phase_callback,
        )
        app = create_app(runtime)

        req = _build_phase_request(case_id=1001, idempotency_key="phase:1001")
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
        self.assertIn("trustAttestation", phase_callback_calls[0][1])
        self.assertEqual(
            phase_callback_calls[0][1]["trustAttestation"]["dispatchType"],
            "phase",
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["status"],
            "ok",
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["dispatchType"],
            "phase",
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["policyRegistry"]["version"],
            "v3-default",
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["promptRegistry"]["version"],
            "promptset-v3-default",
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["toolRegistry"]["version"],
            "toolset-v3-default",
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["registryVersions"]["promptVersion"],
            "promptset-v3-default",
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["registryVersions"]["toolsetVersion"],
            "toolset-v3-default",
        )
        self.assertEqual(
            len(phase_callback_calls[0][1]["judgeTrace"]["courtroomRoles"]),
            8,
        )
        self.assertEqual(
            len(phase_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["activeRoles"]),
            5,
        )
        phase_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=1001)
        self.assertIsNotNone(phase_job)
        assert phase_job is not None
        self.assertEqual(phase_job.status, "callback_reported")
        phase_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=1001)
        self.assertGreaterEqual(len(phase_events), 8)
        self.assertTrue(all(row.event_type == "status_changed" for row in phase_events[-8:]))
        self.assertEqual(phase_events[-1].payload.get("toStatus"), "callback_reported")
        self.assertEqual(phase_events[-1].payload.get("judgeCoreStage"), "reported")
        self.assertEqual(phase_events[-1].payload.get("judgeCoreVersion"), "v1")

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

        async def fake_phase_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            phase_callback_calls.append((case_id, payload))

        async def fake_final_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            final_callback_calls.append((case_id, payload))

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=fake_phase_callback,
            callback_final_report_impl=fake_final_callback,
            callback_phase_failed_impl=fake_phase_callback,
            callback_final_failed_impl=fake_final_callback,
        )
        app = create_app(runtime)

        phase_req = _build_phase_request(case_id=2001, idempotency_key="phase:2001")
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)
        self.assertEqual(len(phase_callback_calls), 1)

        final_req = _build_final_request(case_id=2002, idempotency_key="final:2002")
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
        self.assertIn("trustAttestation", final_callback_calls[0][1])
        self.assertEqual(
            final_callback_calls[0][1]["trustAttestation"]["dispatchType"],
            "final",
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["policyRegistry"]["version"],
            "v3-default",
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["status"],
            "ok",
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["dispatchType"],
            "final",
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["promptRegistry"]["version"],
            "promptset-v3-default",
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["toolRegistry"]["version"],
            "toolset-v3-default",
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["registryVersions"]["promptVersion"],
            "promptset-v3-default",
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["registryVersions"]["toolsetVersion"],
            "toolset-v3-default",
        )
        self.assertEqual(
            len(final_callback_calls[0][1]["judgeTrace"]["courtroomRoles"]),
            8,
        )
        self.assertEqual(
            len(final_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["activeRoles"]),
            8,
        )
        phase_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=2001)
        final_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=2002)
        self.assertIsNotNone(phase_job)
        self.assertIsNotNone(final_job)
        assert phase_job is not None and final_job is not None
        self.assertEqual(phase_job.status, "callback_reported")
        self.assertEqual(final_job.status, "callback_reported")

    async def test_final_dispatch_should_mark_workflow_review_required_when_gate_triggers(
        self,
    ) -> None:
        final_callback_calls: list[tuple[int, dict]] = []

        async def noop_phase_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        async def final_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            final_callback_calls.append((case_id, payload))

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_phase_callback,
            callback_final_report_impl=final_callback,
            callback_phase_failed_impl=noop_phase_callback,
            callback_final_failed_impl=final_callback,
        )
        app = create_app(runtime)
        final_req = _build_final_request(case_id=7401, idempotency_key="final:7401")
        gated_payload = {
            "sessionId": 2,
            "winner": "draw",
            "proScore": 61.0,
            "conScore": 60.2,
            "dimensionScores": {
                "logic": 60.0,
                "evidence": 61.0,
                "rebuttal": 59.5,
                "clarity": 60.4,
            },
            "debateSummary": "summary",
            "sideAnalysis": {"pro": "pro", "con": "con"},
            "verdictReason": "reason",
            "claimGraph": {
                "pipelineVersion": "v1-claim-graph-bootstrap",
                "nodes": [],
                "edges": [],
                "unansweredClaimIds": [],
                "stats": {
                    "totalClaims": 0,
                    "proClaims": 0,
                    "conClaims": 0,
                    "conflictEdges": 0,
                    "unansweredClaims": 0,
                    "weakSupportedClaims": 0,
                    "verdictReferencedClaims": 0,
                },
            },
            "claimGraphSummary": {
                "coreClaims": {"pro": [], "con": []},
                "conflictPairs": [],
                "unansweredClaims": [],
                "stats": {
                    "totalClaims": 0,
                    "proClaims": 0,
                    "conClaims": 0,
                    "conflictEdges": 0,
                    "unansweredClaims": 0,
                    "weakSupportedClaims": 0,
                    "verdictReferencedClaims": 0,
                },
            },
            "evidenceLedger": {
                "pipelineVersion": "v2-evidence-ledger",
                "entries": [],
                "refsById": {},
                "messageRefs": [],
                "citationRefs": [],
                "conflictRefs": [],
                "stats": {
                    "totalEntries": 0,
                    "messageRefCount": 0,
                    "citationRefCount": 0,
                    "conflictRefCount": 0,
                    "verdictReferencedCount": 0,
                },
            },
            "verdictLedger": {
                "version": "v2-panel-arbiter-opinion",
                "scoreCard": {"proScore": 61.0, "conScore": 60.2, "dimensionScores": {"logic": 60.0}},
                "panelDecisions": {"probeWinners": {"agent3Weighted": "pro"}},
                "arbitration": {"winnerAfterArbitration": "draw", "reviewRequired": True},
                "pivotalMoments": [],
                "decisiveEvidenceRefs": [],
            },
            "opinionPack": {
                "version": "v2-opinion-pack",
                "userReport": {"winner": "draw", "debateSummary": "summary"},
                "opsSummary": {"reviewRequired": True},
                "internalReview": {"traceId": "trace-final-7401"},
            },
            "verdictEvidenceRefs": [],
            "phaseRollupSummary": [{"phaseNo": 1}],
            "retrievalSnapshotRollup": [],
            "winnerFirst": "pro",
            "winnerSecond": "pro",
            "rejudgeTriggered": True,
            "needsDrawVote": True,
            "reviewRequired": True,
            "judgeTrace": {"traceId": "trace-final-7401"},
            "auditAlerts": [{"type": "style_shift_instability"}],
            "errorCodes": ["style_shift_instability", "fairness_gate_review_required"],
            "degradationLevel": 1,
        }

        with patch("app.app_factory._build_final_report_payload", return_value=gated_payload):
            final_resp = await self._post_json(
                app=app,
                path="/internal/judge/v3/final/dispatch",
                payload=final_req.model_dump(mode="json"),
                internal_key=runtime.settings.ai_internal_key,
            )

        self.assertEqual(final_resp.status_code, 200)
        self.assertEqual(len(final_callback_calls), 1)
        workflow_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=7401)
        self.assertIsNotNone(workflow_job)
        assert workflow_job is not None
        self.assertEqual(workflow_job.status, "review_required")
        workflow_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=7401)
        self.assertEqual(workflow_events[-1].payload.get("toStatus"), "review_required")
        self.assertTrue(workflow_events[-1].payload.get("reviewRequired"))
        self.assertEqual(workflow_events[-1].payload.get("judgeCoreStage"), "review_required")

    async def test_review_routes_should_list_detail_and_decide_review_job(self) -> None:
        async def noop_phase_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        async def noop_final_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_phase_callback,
            callback_final_report_impl=noop_final_callback,
            callback_phase_failed_impl=noop_phase_callback,
            callback_final_failed_impl=noop_final_callback,
        )
        app = create_app(runtime)
        final_req = _build_final_request(case_id=7411, idempotency_key="final:7411")
        gated_payload = {
            "sessionId": 2,
            "winner": "draw",
            "proScore": 60.8,
            "conScore": 60.2,
            "dimensionScores": {
                "logic": 60.5,
                "evidence": 60.2,
                "rebuttal": 59.9,
                "clarity": 60.1,
            },
            "debateSummary": "summary",
            "sideAnalysis": {"pro": "pro", "con": "con"},
            "verdictReason": "reason",
            "claimGraph": {
                "pipelineVersion": "v1-claim-graph-bootstrap",
                "nodes": [],
                "edges": [],
                "unansweredClaimIds": [],
                "stats": {
                    "totalClaims": 0,
                    "proClaims": 0,
                    "conClaims": 0,
                    "conflictEdges": 0,
                    "unansweredClaims": 0,
                    "weakSupportedClaims": 0,
                    "verdictReferencedClaims": 0,
                },
            },
            "claimGraphSummary": {
                "coreClaims": {"pro": [], "con": []},
                "conflictPairs": [],
                "unansweredClaims": [],
                "stats": {
                    "totalClaims": 0,
                    "proClaims": 0,
                    "conClaims": 0,
                    "conflictEdges": 0,
                    "unansweredClaims": 0,
                    "weakSupportedClaims": 0,
                    "verdictReferencedClaims": 0,
                },
            },
            "evidenceLedger": {
                "pipelineVersion": "v2-evidence-ledger",
                "entries": [],
                "refsById": {},
                "messageRefs": [],
                "citationRefs": [],
                "conflictRefs": [],
                "stats": {
                    "totalEntries": 0,
                    "messageRefCount": 0,
                    "citationRefCount": 0,
                    "conflictRefCount": 0,
                    "verdictReferencedCount": 0,
                },
            },
            "verdictLedger": {
                "version": "v2-panel-arbiter-opinion",
                "scoreCard": {"proScore": 60.8, "conScore": 60.2, "dimensionScores": {"logic": 60.5}},
                "panelDecisions": {"probeWinners": {"agent3Weighted": "pro"}},
                "arbitration": {"winnerAfterArbitration": "draw", "reviewRequired": True},
                "pivotalMoments": [],
                "decisiveEvidenceRefs": [],
            },
            "opinionPack": {
                "version": "v2-opinion-pack",
                "userReport": {"winner": "draw", "debateSummary": "summary"},
                "opsSummary": {"reviewRequired": True},
                "internalReview": {"traceId": "trace-final-7411"},
            },
            "verdictEvidenceRefs": [],
            "phaseRollupSummary": [{"phaseNo": 1}],
            "retrievalSnapshotRollup": [],
            "winnerFirst": "pro",
            "winnerSecond": "pro",
            "winnerThird": "con",
            "rejudgeTriggered": True,
            "needsDrawVote": True,
            "reviewRequired": True,
            "judgeTrace": {
                "traceId": "trace-final-7411",
                "fairnessGate": {
                    "phase": "phase2",
                    "panelHighDisagreement": True,
                    "reviewRequired": True,
                },
            },
            "fairnessSummary": {
                "phase": "phase2",
                "panelHighDisagreement": True,
                "reviewRequired": True,
            },
            "auditAlerts": [{"type": "judge_panel_high_disagreement"}],
            "errorCodes": ["judge_panel_high_disagreement", "fairness_gate_review_required"],
            "degradationLevel": 1,
        }

        with patch("app.app_factory._build_final_report_payload", return_value=gated_payload):
            final_resp = await self._post_json(
                app=app,
                path="/internal/judge/v3/final/dispatch",
                payload=final_req.model_dump(mode="json"),
                internal_key=runtime.settings.ai_internal_key,
            )
        self.assertEqual(final_resp.status_code, 200)

        list_resp = await self._get(
            app=app,
            path="/internal/judge/review/cases?status=review_required&dispatch_type=final",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(list_resp.status_code, 200)
        queue_payload = list_resp.json()
        self.assertGreaterEqual(queue_payload["count"], 1)
        target_item = next(
            item for item in queue_payload["items"] if item["workflow"]["caseId"] == 7411
        )
        self.assertTrue(target_item["reviewRequired"])
        self.assertIn("judge_panel_high_disagreement", target_item["errorCodes"])

        detail_resp = await self._get(
            app=app,
            path="/internal/judge/review/cases/7411",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(detail_resp.status_code, 200)
        detail_payload = detail_resp.json()
        self.assertEqual(detail_payload["job"]["status"], "review_required")
        self.assertTrue(detail_payload["reviewRequired"])
        self.assertEqual(
            detail_payload["reportPayload"]["fairnessSummary"]["panelHighDisagreement"],
            True,
        )

        pending_challenge_resp = await self._get(
            app=app,
            path="/internal/judge/cases/7411/trust/challenges?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(pending_challenge_resp.status_code, 200)
        pending_challenge_item = pending_challenge_resp.json()["item"]
        self.assertEqual(pending_challenge_item["reviewState"], "pending_review")
        self.assertIn("judge_panel_high_disagreement", pending_challenge_item["challengeReasons"])

        decision_resp = await self._post(
            app=app,
            path="/internal/judge/review/cases/7411/decision?decision=approve&actor=ops&reason=manual_pass",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(decision_resp.status_code, 200)
        decision_payload = decision_resp.json()
        self.assertEqual(decision_payload["decision"], "approve")
        self.assertEqual(decision_payload["job"]["status"], "callback_reported")

        workflow_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=7411)
        self.assertIsNotNone(workflow_job)
        assert workflow_job is not None
        self.assertEqual(workflow_job.status, "callback_reported")
        workflow_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=7411)
        self.assertEqual(workflow_events[-1].payload.get("judgeCoreStage"), "review_approved")

        approved_challenge_resp = await self._get(
            app=app,
            path="/internal/judge/cases/7411/trust/challenges?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(approved_challenge_resp.status_code, 200)
        approved_challenge_item = approved_challenge_resp.json()["item"]
        self.assertEqual(approved_challenge_item["reviewState"], "approved")
        self.assertEqual(approved_challenge_item["openAlertIds"], [])

    async def test_phase_dispatch_should_mark_callback_failed_receipt_when_callback_raises(
        self,
    ) -> None:
        async def failing_phase_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            raise RuntimeError("phase-callback-down")

        async def noop_failed_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(runtime_retry_max_attempts=1),
            callback_phase_report_impl=failing_phase_callback,
            callback_final_report_impl=failing_phase_callback,
            callback_phase_failed_impl=noop_failed_callback,
            callback_final_failed_impl=noop_failed_callback,
        )
        app = create_app(runtime)

        req = _build_phase_request(case_id=3001, idempotency_key="phase:3001")
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
            path="/internal/judge/v3/phase/cases/3001/receipt",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(receipt_resp.status_code, 200)
        receipt = receipt_resp.json()
        self.assertEqual(receipt["status"], "callback_failed")
        self.assertEqual(
            receipt["response"].get("errorCode"),
            "phase_callback_retry_exhausted",
        )
        self.assertEqual(
            receipt["response"].get("error", {}).get("code"),
            "phase_callback_retry_exhausted",
        )
        self.assertEqual(
            receipt["response"].get("error", {}).get("dispatchType"),
            "phase",
        )
        self.assertEqual(
            receipt["response"].get("error", {}).get("category"),
            "callback_delivery",
        )
        phase_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=3001)
        self.assertIsNotNone(phase_job)
        assert phase_job is not None
        self.assertEqual(phase_job.status, "blocked_failed")
        workflow_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=3001)
        self.assertEqual(
            workflow_events[-1].payload.get("errorCode"),
            "phase_callback_retry_exhausted",
        )
        self.assertEqual(
            workflow_events[-1].payload.get("error", {}).get("code"),
            "phase_callback_retry_exhausted",
        )

    async def test_final_dispatch_should_mark_callback_failed_receipt_when_callback_raises(
        self,
    ) -> None:
        case_id = _unique_case_id(8301)

        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        async def failing_final_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            raise RuntimeError("final-callback-down")

        runtime = create_runtime(
            settings=_build_settings(runtime_retry_max_attempts=1),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=failing_final_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)

        phase_req = _build_phase_request(
            case_id=case_id,
            idempotency_key=f"phase:{case_id}",
        )
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(
            case_id=case_id,
            idempotency_key=f"final:{case_id}",
        )
        failed_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(failed_resp.status_code, 502)
        self.assertIn("final_callback_failed", failed_resp.text)

        receipt_resp = await self._get(
            app=app,
            path=f"/internal/judge/v3/final/cases/{case_id}/receipt",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(receipt_resp.status_code, 200)
        receipt = receipt_resp.json()
        self.assertEqual(receipt["status"], "callback_failed")
        self.assertEqual(
            receipt["response"].get("errorCode"),
            "final_callback_retry_exhausted",
        )
        self.assertEqual(
            receipt["response"].get("error", {}).get("code"),
            "final_callback_retry_exhausted",
        )
        self.assertEqual(
            receipt["response"].get("error", {}).get("dispatchType"),
            "final",
        )
        self.assertEqual(
            receipt["response"].get("error", {}).get("category"),
            "callback_delivery",
        )
        workflow_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=case_id)
        self.assertEqual(
            workflow_events[-1].payload.get("errorCode"),
            "final_callback_retry_exhausted",
        )
        self.assertEqual(
            workflow_events[-1].payload.get("error", {}).get("code"),
            "final_callback_retry_exhausted",
        )

    async def test_final_dispatch_should_mark_failed_when_failed_callback_fails(self) -> None:
        case_id = _unique_case_id(8302)

        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        async def failing_final_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            raise RuntimeError("final-callback-down")

        async def failing_failed_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            raise RuntimeError("final-failed-callback-down")

        runtime = create_runtime(
            settings=_build_settings(runtime_retry_max_attempts=1),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=failing_final_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=failing_failed_callback,
        )
        app = create_app(runtime)

        phase_req = _build_phase_request(
            case_id=case_id,
            idempotency_key=f"phase:{case_id}",
        )
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(
            case_id=case_id,
            idempotency_key=f"final:{case_id}",
        )
        failed_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(failed_resp.status_code, 502)
        self.assertIn("final_failed_callback_failed", failed_resp.text)

        receipt_resp = await self._get(
            app=app,
            path=f"/internal/judge/v3/final/cases/{case_id}/receipt",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(receipt_resp.status_code, 200)
        receipt = receipt_resp.json()
        self.assertEqual(receipt["status"], "callback_failed")
        self.assertEqual(
            receipt["response"].get("errorCode"),
            "final_failed_callback_failed",
        )
        self.assertEqual(
            receipt["response"].get("error", {}).get("code"),
            "final_failed_callback_failed",
        )
        self.assertEqual(
            receipt["response"].get("error", {}).get("dispatchType"),
            "final",
        )
        workflow_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=case_id)
        self.assertEqual(
            workflow_events[-1].payload.get("errorCode"),
            "final_failed_callback_failed",
        )
        self.assertEqual(
            workflow_events[-1].payload.get("callbackStatus"),
            "failed_callback_failed",
        )
        self.assertEqual(
            workflow_events[-1].payload.get("error", {}).get("code"),
            "final_failed_callback_failed",
        )

    async def test_replay_post_should_prefer_final_receipt_when_auto(self) -> None:
        phase_calls: list[tuple[int, dict]] = []
        final_calls: list[tuple[int, dict]] = []

        async def phase_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            phase_calls.append((case_id, payload))

        async def final_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            final_calls.append((case_id, payload))

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=phase_callback,
            callback_final_report_impl=final_callback,
            callback_phase_failed_impl=phase_callback,
            callback_final_failed_impl=final_callback,
        )
        app = create_app(runtime)

        phase_req = _build_phase_request(case_id=5001, idempotency_key="phase:5001")
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(case_id=5001, idempotency_key="final:5001")
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
            path="/internal/judge/cases/5001/replay?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(replay_resp.status_code, 200)
        replay_payload = replay_resp.json()
        self.assertEqual(replay_payload["dispatchType"], "final")
        self.assertIn("reportPayload", replay_payload)
        self.assertIn("verdictContract", replay_payload)
        self.assertIn("debateSummary", replay_payload["reportPayload"])
        self.assertIn("trustAttestation", replay_payload["reportPayload"])
        self.assertEqual(replay_payload["judgeCoreStage"], "replay_computed")
        self.assertEqual(replay_payload["judgeCoreVersion"], "v1")
        self.assertEqual(callback_total_before_replay, len(phase_calls) + len(final_calls))
        replay_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=5001)
        self.assertEqual(replay_events[-1].event_type, "replay_marked")
        self.assertEqual(replay_events[-1].payload.get("judgeCoreStage"), "replay_computed")

    async def test_attestation_verify_should_use_auto_dispatch_and_return_verified(self) -> None:
        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)

        phase_req = _build_phase_request(case_id=8103, idempotency_key="phase:8103")
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(case_id=8103, idempotency_key="final:8103")
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        verify_resp = await self._post(
            app=app,
            path="/internal/judge/cases/8103/attestation/verify?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(verify_resp.status_code, 200)
        verify_payload = verify_resp.json()
        self.assertEqual(verify_payload["dispatchType"], "final")
        self.assertEqual(verify_payload["traceId"], "trace-final-8103")
        self.assertTrue(verify_payload["verified"])
        self.assertEqual(verify_payload["reason"], "ok")
        self.assertEqual(verify_payload["mismatchComponents"], [])

    async def test_attestation_verify_should_detect_tampered_report_payload(self) -> None:
        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)

        phase_req = _build_phase_request(case_id=8104, idempotency_key="phase:8104")
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(case_id=8104, idempotency_key="final:8104")
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        fact_receipt = await runtime.workflow_runtime.facts.get_dispatch_receipt(
            dispatch_type="final",
            job_id=8104,
        )
        self.assertIsNotNone(fact_receipt)
        assert fact_receipt is not None
        response_payload = dict(fact_receipt.response or {})
        report_payload = (
            dict(response_payload.get("reportPayload"))
            if isinstance(response_payload.get("reportPayload"), dict)
            else {}
        )
        report_payload["winner"] = "draw" if report_payload.get("winner") != "draw" else "pro"
        response_payload["reportPayload"] = report_payload
        await runtime.workflow_runtime.facts.upsert_dispatch_receipt(
            receipt=replace(fact_receipt, response=response_payload),
        )

        verify_resp = await self._post(
            app=app,
            path="/internal/judge/cases/8104/attestation/verify?dispatch_type=final",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(verify_resp.status_code, 200)
        verify_payload = verify_resp.json()
        self.assertFalse(verify_payload["verified"])
        self.assertEqual(verify_payload["reason"], "trust_attestation_mismatch")
        self.assertIn("verdictHash", verify_payload["mismatchComponents"])

    async def test_trust_routes_should_return_phasea_registry_bundle(self) -> None:
        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)

        case_id = _unique_case_id(8105)
        phase_req = _build_phase_request(case_id=case_id, idempotency_key=f"phase:{case_id}")
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(case_id=case_id, idempotency_key=f"final:{case_id}")
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        commitment_resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/trust/commitment?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(commitment_resp.status_code, 200)
        commitment_payload = commitment_resp.json()
        commitment_item = commitment_payload["item"]
        self.assertEqual(commitment_payload["dispatchType"], "final")
        self.assertEqual(commitment_payload["traceId"], f"trace-final-{case_id}")
        self.assertEqual(commitment_item["version"], "trust-phaseA-case-commitment-v1")
        self.assertIn("commitmentHash", commitment_item)

        attestation_resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/trust/verdict-attestation?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(attestation_resp.status_code, 200)
        attestation_item = attestation_resp.json()["item"]
        self.assertEqual(attestation_item["version"], "trust-phaseA-verdict-attestation-v1")
        self.assertTrue(attestation_item["verified"])
        self.assertEqual(attestation_item["reason"], "ok")
        self.assertIn("registryHash", attestation_item)

        challenge_resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/trust/challenges?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(challenge_resp.status_code, 200)
        challenge_item = challenge_resp.json()["item"]
        self.assertEqual(challenge_item["version"], "trust-phaseA-challenge-review-v1")
        self.assertEqual(challenge_item["reviewState"], "approved")
        self.assertIn("registryHash", challenge_item)

        kernel_resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/trust/kernel-version?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(kernel_resp.status_code, 200)
        kernel_item = kernel_resp.json()["item"]
        self.assertEqual(kernel_item["version"], "trust-phaseA-kernel-version-v1")
        self.assertIn("kernelVector", kernel_item)
        self.assertIn("kernelHash", kernel_item)
        self.assertIn("registryHash", kernel_item)

        anchor_resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/trust/audit-anchor?dispatch_type=auto&include_payload=true",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(anchor_resp.status_code, 200)
        anchor_item = anchor_resp.json()["item"]
        self.assertEqual(anchor_item["version"], "trust-phaseA-audit-anchor-v1")
        self.assertIn("anchorHash", anchor_item)
        self.assertIn("payload", anchor_item)
        self.assertEqual(
            anchor_item["componentHashes"]["caseCommitmentHash"],
            commitment_item["commitmentHash"],
        )
        self.assertEqual(
            anchor_item["componentHashes"]["verdictAttestationHash"],
            attestation_item["registryHash"],
        )
        self.assertEqual(
            anchor_item["componentHashes"]["challengeReviewHash"],
            challenge_item["registryHash"],
        )
        self.assertEqual(
            anchor_item["componentHashes"]["kernelVersionHash"],
            kernel_item["registryHash"],
        )

    async def test_receipt_route_should_fallback_to_fact_repository_when_trace_missing(self) -> None:
        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)

        req = _build_phase_request(case_id=7001, idempotency_key="phase:7001")
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
            path="/internal/judge/v3/phase/cases/7001/receipt",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(receipt_resp.status_code, 200)
        self.assertEqual(receipt_resp.json()["status"], "reported")

    async def test_replay_post_should_persist_replay_record_to_fact_repository(self) -> None:
        phase_calls: list[tuple[int, dict]] = []
        final_calls: list[tuple[int, dict]] = []

        async def phase_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            phase_calls.append((case_id, payload))

        async def final_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            final_calls.append((case_id, payload))

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

        phase_req = _build_phase_request(case_id=7101, idempotency_key="phase:7101")
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(case_id=7101, idempotency_key="final:7101")
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        replay_resp = await self._post(
            app=app,
            path="/internal/judge/cases/7101/replay?dispatch_type=auto",
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
        replay_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=7101)
        self.assertEqual(replay_events[-1].event_type, "replay_marked")
        self.assertEqual(replay_events[-1].payload.get("judgeCoreStage"), "replay_computed")

    async def test_replay_post_should_block_when_final_contract_missing_fields(self) -> None:
        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)

        phase_req = _build_phase_request(case_id=7102, idempotency_key="phase:7102")
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(case_id=7102, idempotency_key="final:7102")
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)
        before_replay_rows = await runtime.workflow_runtime.facts.list_replay_records(
            job_id=7102,
            limit=100,
        )
        before_replay_count = len(before_replay_rows)

        broken_payload = {
            "winner": "pro",
            "proScore": 70.0,
            "conScore": 62.0,
            "dimensionScores": {"logic": 70.0},
        }
        with patch("app.app_factory._build_final_report_payload", return_value=broken_payload):
            replay_resp = await self._post(
                app=app,
                path="/internal/judge/cases/7102/replay?dispatch_type=final",
                internal_key=runtime.settings.ai_internal_key,
            )
        self.assertEqual(replay_resp.status_code, 409)
        self.assertIn("replay_final_contract_violation", replay_resp.text)

        after_replay_rows = await runtime.workflow_runtime.facts.list_replay_records(
            job_id=7102,
            limit=100,
        )
        self.assertEqual(len(after_replay_rows), before_replay_count)
        workflow_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=7102)
        self.assertNotEqual(workflow_events[-1].event_type, "replay_marked")

    async def test_alert_ack_should_sync_status_to_fact_repository(self) -> None:
        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)
        alert = runtime.trace_store.upsert_audit_alert(job_id=7201,
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
            path=f"/internal/judge/cases/7201/alerts/{alert.alert_id}/ack",
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

        async def phase_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        async def failed_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            failed_calls.append((case_id, payload))

        runtime = create_runtime(
            settings=_build_settings(runtime_retry_max_attempts=1),
            callback_phase_report_impl=phase_callback,
            callback_final_report_impl=phase_callback,
            callback_phase_failed_impl=failed_callback,
            callback_final_failed_impl=failed_callback,
        )
        app = create_app(runtime)
        bad_payload = _build_phase_request(case_id=6001, idempotency_key="phase:6001").model_dump(
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
        self.assertEqual(
            failed_calls[0][1].get("error", {}).get("code"),
            "input_not_blinded",
        )
        workflow_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=6001)
        self.assertIsNotNone(workflow_job)
        assert workflow_job is not None
        self.assertEqual(workflow_job.status, "blocked_failed")
        workflow_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=6001)
        self.assertEqual(workflow_events[-1].payload.get("errorCode"), "input_not_blinded")
        self.assertEqual(workflow_events[-1].payload.get("callbackStatus"), "failed_reported")
        self.assertEqual(
            workflow_events[-1].payload.get("error", {}).get("code"),
            "input_not_blinded",
        )

    async def test_blindization_reject_should_mark_workflow_failed_when_failed_callback_fails(
        self,
    ) -> None:
        async def phase_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        async def failing_failed_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            raise RuntimeError("failed-callback-down")

        runtime = create_runtime(
            settings=_build_settings(runtime_retry_max_attempts=1),
            callback_phase_report_impl=phase_callback,
            callback_final_report_impl=phase_callback,
            callback_phase_failed_impl=failing_failed_callback,
            callback_final_failed_impl=failing_failed_callback,
        )
        app = create_app(runtime)
        bad_payload = _build_phase_request(case_id=6002, idempotency_key="phase:6002").model_dump(
            mode="json"
        )
        bad_payload["messages"][0]["vip"] = True

        bad_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=bad_payload,
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_resp.status_code, 502)
        self.assertIn("phase_failed_callback_failed", bad_resp.text)
        workflow_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=6002)
        self.assertIsNotNone(workflow_job)
        assert workflow_job is not None
        self.assertEqual(workflow_job.status, "blocked_failed")
        receipt_resp = await self._get(
            app=app,
            path="/internal/judge/v3/phase/cases/6002/receipt",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(receipt_resp.status_code, 200)
        self.assertEqual(
            receipt_resp.json()["response"].get("errorCode"),
            "phase_failed_callback_failed",
        )
        workflow_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=6002)
        self.assertEqual(workflow_events[-1].payload.get("errorCode"), "phase_failed_callback_failed")
        self.assertEqual(
            workflow_events[-1].payload.get("callbackStatus"),
            "failed_callback_failed",
        )
        self.assertEqual(
            workflow_events[-1].payload.get("error", {}).get("code"),
            "phase_failed_callback_failed",
        )

    async def test_final_contract_blocked_should_mark_workflow_failed_and_sync_alert(self) -> None:
        failed_calls: list[tuple[int, dict]] = []

        async def phase_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        async def final_failed_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            failed_calls.append((case_id, payload))

        runtime = create_runtime(
            settings=_build_settings(runtime_retry_max_attempts=1),
            callback_phase_report_impl=phase_callback,
            callback_final_report_impl=phase_callback,
            callback_phase_failed_impl=phase_callback,
            callback_final_failed_impl=final_failed_callback,
        )
        app = create_app(runtime)
        final_req = _build_final_request(case_id=7301, idempotency_key="final:7301")

        with patch(
            "app.app_factory._build_final_report_payload",
            return_value={"winner": "draw", "degradationLevel": 1},
        ):
            blocked_resp = await self._post_json(
                app=app,
                path="/internal/judge/v3/final/dispatch",
                payload=final_req.model_dump(mode="json"),
                internal_key=runtime.settings.ai_internal_key,
            )
        self.assertEqual(blocked_resp.status_code, 502)
        self.assertIn("final_contract_blocked", blocked_resp.text)
        self.assertEqual(len(failed_calls), 1)
        self.assertEqual(failed_calls[0][0], 7301)
        self.assertEqual(failed_calls[0][1]["errorCode"], "final_contract_blocked")

        workflow_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=7301)
        self.assertIsNotNone(workflow_job)
        assert workflow_job is not None
        self.assertEqual(workflow_job.status, "blocked_failed")
        workflow_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=7301)
        self.assertEqual(workflow_events[-1].payload.get("errorCode"), "final_contract_blocked")
        self.assertEqual(workflow_events[-1].payload.get("callbackStatus"), "blocked_failed_reported")
        self.assertEqual(
            workflow_events[-1].payload.get("error", {}).get("code"),
            "final_contract_blocked",
        )

        receipt_resp = await self._get(
            app=app,
            path="/internal/judge/v3/final/cases/7301/receipt",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(receipt_resp.status_code, 200)
        self.assertEqual(
            receipt_resp.json()["response"].get("errorCode"),
            "final_contract_blocked",
        )
        self.assertEqual(
            receipt_resp.json()["response"].get("error", {}).get("category"),
            "contract_blocked",
        )

        fact_alerts = await runtime.workflow_runtime.facts.list_audit_alerts(job_id=7301, limit=10)
        self.assertGreaterEqual(len(fact_alerts), 1)
        self.assertEqual(fact_alerts[0].alert_type, "final_contract_violation")

    async def test_create_default_app_should_be_constructible(self) -> None:
        app = create_default_app(load_settings_fn=_build_settings)
        self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main()
