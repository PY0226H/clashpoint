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
        "db_url": f"sqlite+aiosqlite:////tmp/echoisle_ai_judge_service_test_{unique_db_suffix}.db",
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
        self.assertIn("/internal/judge/cases/{case_id}/claim-ledger", paths)
        self.assertIn("/internal/judge/policies", paths)
        self.assertIn("/internal/judge/policies/{policy_version}", paths)
        self.assertIn("/internal/judge/registries/prompts", paths)
        self.assertIn("/internal/judge/registries/prompts/{prompt_version}", paths)
        self.assertIn("/internal/judge/registries/tools", paths)
        self.assertIn("/internal/judge/registries/tools/{toolset_version}", paths)
        self.assertIn("/internal/judge/registries/policy/dependencies/health", paths)
        self.assertIn("/internal/judge/registries/{registry_type}/publish", paths)
        self.assertIn("/internal/judge/registries/{registry_type}/{version}/activate", paths)
        self.assertIn("/internal/judge/registries/{registry_type}/rollback", paths)
        self.assertIn("/internal/judge/registries/{registry_type}/audits", paths)
        self.assertIn("/internal/judge/registries/{registry_type}/releases", paths)
        self.assertIn("/internal/judge/registries/{registry_type}/releases/{version}", paths)
        self.assertIn("/internal/judge/fairness/cases", paths)
        self.assertIn("/internal/judge/fairness/cases/{case_id}", paths)
        self.assertIn("/internal/judge/panels/runtime/profiles", paths)
        self.assertIn("/internal/judge/cases/{case_id}/attestation/verify", paths)
        self.assertIn("/internal/judge/cases/{case_id}/trust/commitment", paths)
        self.assertIn("/internal/judge/cases/{case_id}/trust/verdict-attestation", paths)
        self.assertIn("/internal/judge/cases/{case_id}/trust/challenges", paths)
        self.assertIn("/internal/judge/cases/{case_id}/trust/challenges/request", paths)
        self.assertIn("/internal/judge/cases/{case_id}/trust/challenges/{challenge_id}/decision", paths)
        self.assertIn("/internal/judge/cases/{case_id}/trust/kernel-version", paths)
        self.assertIn("/internal/judge/cases/{case_id}/trust/audit-anchor", paths)
        self.assertIn("/internal/judge/alerts/ops-view", paths)
        self.assertIn("/internal/judge/fairness/benchmark-runs", paths)
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
        self.assertTrue(case_evidence["hasClaimLedger"])
        self.assertEqual(case_evidence["claimLedger"]["dispatchType"], "final")
        self.assertEqual(detail_payload["judgeCore"]["stage"], "reported")
        self.assertEqual(detail_payload["judgeCore"]["version"], "v1")
        self.assertGreaterEqual(len(detail_payload["events"]), 2)

    async def test_claim_ledger_route_should_return_persisted_claim_graph(self) -> None:
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

        case_id = _unique_case_id(9120)
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

        ledger_resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/claim-ledger?dispatch_type=final",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(ledger_resp.status_code, 200)
        ledger_body = ledger_resp.json()
        self.assertEqual(ledger_body["dispatchType"], "final")
        self.assertGreaterEqual(ledger_body["count"], 1)
        self.assertIsInstance(ledger_body["item"]["claimGraph"], dict)
        self.assertIsInstance(ledger_body["item"]["claimGraph"]["nodes"], list)
        self.assertIsInstance(ledger_body["item"]["claimGraph"]["edges"], list)
        self.assertIsInstance(ledger_body["item"]["claimGraphSummary"], dict)
        self.assertIsInstance(ledger_body["item"]["evidenceLedger"], dict)
        self.assertIsInstance(ledger_body["item"]["verdictEvidenceRefs"], list)

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

    async def test_policy_registry_publish_should_reject_unknown_prompt_registry_version(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        policy_version = f"policy-missing-{_unique_case_id(8105)}"
        publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": policy_version,
                "activate": False,
                "reason": "test_policy_override_for_prompt_registry_validation",
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-missing",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_resp.status_code, 422)
        detail = publish_resp.json()["detail"]
        self.assertEqual(detail["code"], "registry_policy_dependency_invalid")
        dependency = detail["dependency"]
        self.assertFalse(dependency["ok"])
        issue_codes = {str(item.get("code") or "") for item in dependency["issues"]}
        self.assertIn("prompt_registry_version_not_found", issue_codes)
        self.assertEqual(detail["alert"]["type"], "registry_dependency_health_blocked")
        self.assertEqual(detail["alert"]["status"], "raised")

    async def test_registry_routes_should_support_publish_activate_rollback_and_audit(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9201)
        version = f"promptset-p8-{suffix}"
        actor = f"actor-{suffix}"

        publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/prompt/publish",
            payload={
                "version": version,
                "activate": False,
                "actor": actor,
                "reason": "test_publish",
                "profile": {
                    "promptVersions": {
                        "claimGraphVersion": "v1-claim-graph-bootstrap",
                    },
                    "metadata": {
                        "status": "candidate",
                    },
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_resp.status_code, 200)
        publish_item = publish_resp.json()["item"]
        self.assertEqual(publish_item["version"], version)
        self.assertFalse(publish_item["isActive"])

        activate_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/registries/prompt/{version}/activate"
                f"?actor={actor}&reason=test_activate"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(activate_resp.status_code, 200)
        activate_item = activate_resp.json()["item"]
        self.assertEqual(activate_item["version"], version)
        self.assertTrue(activate_item["isActive"])

        prompt_list_resp = await self._get(
            app=app,
            path="/internal/judge/registries/prompts",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(prompt_list_resp.status_code, 200)
        self.assertEqual(prompt_list_resp.json()["defaultVersion"], version)

        rollback_resp = await self._post(
            app=app,
            path=f"/internal/judge/registries/prompt/rollback?actor={actor}&reason=test_rollback",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(rollback_resp.status_code, 200)
        rollback_item = rollback_resp.json()["item"]
        self.assertNotEqual(rollback_item["version"], version)

        prompt_list_after_rollback = await self._get(
            app=app,
            path="/internal/judge/registries/prompts",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(prompt_list_after_rollback.status_code, 200)
        self.assertEqual(
            prompt_list_after_rollback.json()["defaultVersion"],
            rollback_item["version"],
        )

        audits_resp = await self._get(
            app=app,
            path="/internal/judge/registries/prompt/audits?limit=200",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(audits_resp.status_code, 200)
        audit_items = audits_resp.json()["items"]
        actor_actions = [
            str(item.get("action") or "")
            for item in audit_items
            if str(item.get("actor") or "") == actor
        ]
        self.assertIn("publish", actor_actions)
        self.assertIn("activate", actor_actions)
        self.assertIn("rollback", actor_actions)

        releases_resp = await self._get(
            app=app,
            path="/internal/judge/registries/prompt/releases?limit=200&include_payload=false",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(releases_resp.status_code, 200)
        release_items = releases_resp.json()["items"]
        version_items = [
            item
            for item in release_items
            if str(item.get("version") or "") == version
        ]
        self.assertTrue(version_items)
        self.assertNotIn("payload", version_items[0])

        get_release_resp = await self._get(
            app=app,
            path=f"/internal/judge/registries/prompt/releases/{version}",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(get_release_resp.status_code, 200)
        release_item = get_release_resp.json()["item"]
        self.assertEqual(release_item["version"], version)
        self.assertIn("payload", release_item)

    async def test_policy_registry_activate_should_block_when_fairness_gate_not_ready(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9211)
        version = f"policy-gate-{suffix}"

        publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_resp.status_code, 200)

        activate_resp = await self._post(
            app=app,
            path=f"/internal/judge/registries/policy/{version}/activate",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(activate_resp.status_code, 409)
        detail = activate_resp.json()["detail"]
        self.assertEqual(detail["code"], "registry_fairness_gate_blocked")
        self.assertEqual(
            detail["gate"]["code"],
            "registry_fairness_gate_no_benchmark",
        )

    async def test_policy_registry_activate_should_block_when_dependency_invalid(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        await runtime.workflow_runtime.db.create_schema()
        suffix = _unique_case_id(9212)
        version = f"policy-dep-{suffix}"
        await runtime.registry_product_runtime.publish_release(
            registry_type="policy",
            version=version,
            profile_payload={
                "rubricVersion": "v3",
                "topicDomain": "tft",
                "promptRegistryVersion": "promptset-not-exist",
                "toolRegistryVersion": "toolset-v3-default",
            },
            actor="seed",
            reason="seed_invalid_dependency_for_activate",
            activate=False,
        )

        activate_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/registries/policy/{version}/activate"
                "?override_fairness_gate=true&reason=test_override"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(activate_resp.status_code, 409)
        detail = activate_resp.json()["detail"]
        self.assertEqual(detail["code"], "registry_policy_dependency_blocked")
        dependency = detail["dependency"]
        self.assertFalse(dependency["ok"])
        issue_codes = {str(item.get("code") or "") for item in dependency["issues"]}
        self.assertIn("prompt_registry_version_not_found", issue_codes)

    async def test_policy_registry_dependency_health_route_should_return_dependency_snapshot(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9214)
        version = f"policy-health-{suffix}"
        publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": version,
                "activate": False,
                "reason": "prepare_for_dependency_health",
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-v3-default",
                    "toolRegistryVersion": "toolset-v3-default",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_resp.status_code, 200)

        health_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/registries/policy/dependencies/health"
                f"?policy_version={version}&include_all_versions=true&limit=5"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(health_resp.status_code, 200)
        payload = health_resp.json()
        self.assertEqual(payload["selectedPolicyVersion"], version)
        self.assertGreaterEqual(payload["count"], 1)
        self.assertTrue(payload["includeAllVersions"])
        self.assertTrue(payload["includeOverview"])
        self.assertTrue(payload["includeTrend"])
        self.assertEqual(payload["item"]["policyVersion"], version)
        self.assertTrue(payload["item"]["ok"])
        self.assertTrue(payload["item"]["checks"]["promptRegistryExists"])
        self.assertTrue(payload["item"]["checks"]["toolRegistryExists"])
        self.assertEqual(payload["activeVersions"]["policyVersion"], runtime.policy_registry_runtime.default_version)
        overview = payload["dependencyOverview"]
        self.assertIsInstance(overview, dict)
        self.assertEqual(overview["registryType"], "policy")
        self.assertGreaterEqual(overview["counts"]["trackedPolicyVersions"], 1)
        self.assertIn("byPolicyVersion", overview)
        self.assertTrue(any(row["policyVersion"] == version for row in overview["byPolicyVersion"]))
        trend = payload["dependencyTrend"]
        self.assertIsInstance(trend, dict)
        self.assertEqual(trend["registryType"], "policy")
        self.assertIn("items", trend)
        self.assertGreaterEqual(trend["count"], 0)

    async def test_policy_registry_dependency_health_route_should_reject_invalid_trend_status(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        health_resp = await self._get(
            app=app,
            path="/internal/judge/registries/policy/dependencies/health?trend_status=bad-status",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(health_resp.status_code, 422)
        self.assertIn("invalid_trend_status", health_resp.text)

    async def test_policy_registry_dependency_blocked_alert_should_emit_and_resolve_outbox(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        version = f"policy-dep-alert-{_unique_case_id(9215)}"

        blocked_publish = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-missing",
                    "toolRegistryVersion": "toolset-v3-default",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(blocked_publish.status_code, 422)
        blocked_detail = blocked_publish.json()["detail"]
        self.assertEqual(blocked_detail["code"], "registry_policy_dependency_invalid")
        blocked_alert = blocked_detail["alert"]
        self.assertEqual(blocked_alert["type"], "registry_dependency_health_blocked")
        self.assertEqual(blocked_alert["status"], "raised")

        outbox_after_blocked = await self._get(
            app=app,
            path="/internal/judge/alerts/outbox",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(outbox_after_blocked.status_code, 200)
        blocked_event = next(
            (
                item
                for item in outbox_after_blocked.json()["items"]
                if item.get("payload", {}).get("alertType")
                == "registry_dependency_health_blocked"
                and item.get("payload", {}).get("status") == "raised"
                and item.get("payload", {}).get("details", {}).get("version") == version
            ),
            None,
        )
        self.assertIsNotNone(blocked_event)
        open_trend_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/registries/policy/dependencies/health"
                "?include_all_versions=true&include_overview=false"
                "&include_trend=true&trend_status=open&trend_policy_version="
                f"{version}&trend_limit=20&trend_offset=0"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(open_trend_resp.status_code, 200)
        open_trend_payload = open_trend_resp.json()
        self.assertIsNone(open_trend_payload["dependencyOverview"])
        self.assertIsInstance(open_trend_payload["dependencyTrend"], dict)
        self.assertGreaterEqual(open_trend_payload["dependencyTrend"]["count"], 1)
        self.assertGreaterEqual(
            open_trend_payload["dependencyTrend"]["statusCounts"]["raised"],
            1,
        )
        self.assertTrue(
            all(
                row["policyVersion"] == version
                for row in open_trend_payload["dependencyTrend"]["items"]
            )
        )

        prompt_publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/prompt/publish",
            payload={
                "version": "promptset-dep-recover",
                "activate": False,
                "profile": {
                    "promptVersions": {
                        "summaryPromptVersion": "v3.a2a3.summary.v1",
                        "agent2PromptVersion": "v3.a6a7.bidirectional.v2",
                        "finalPipelineVersion": "v3-final-a9a10-rollup-v2",
                        "claimGraphVersion": "v1-claim-graph-bootstrap",
                    },
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(prompt_publish_resp.status_code, 200)

        recovered_publish = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": version,
                "activate": False,
                "reason": "dependency_recovered",
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-dep-recover",
                    "toolRegistryVersion": "toolset-v3-default",
                    "promptVersions": {
                        "summaryPromptVersion": "v3.a2a3.summary.v1",
                        "agent2PromptVersion": "v3.a6a7.bidirectional.v2",
                        "finalPipelineVersion": "v3-final-a9a10-rollup-v2",
                        "claimGraphVersion": "v1-claim-graph-bootstrap",
                    },
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(recovered_publish.status_code, 200)
        recovered_payload = recovered_publish.json()
        self.assertIsNotNone(recovered_payload["dependencyHealth"])
        self.assertTrue(recovered_payload["dependencyHealth"]["ok"])
        self.assertGreaterEqual(len(recovered_payload["resolvedDependencyAlerts"]), 1)

        outbox_after_recovered = await self._get(
            app=app,
            path="/internal/judge/alerts/outbox",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(outbox_after_recovered.status_code, 200)
        resolved_event = next(
            (
                item
                for item in outbox_after_recovered.json()["items"]
                if item.get("payload", {}).get("alertType")
                == "registry_dependency_health_blocked"
                and item.get("payload", {}).get("status") == "resolved"
                and item.get("payload", {}).get("details", {}).get("version") == version
            ),
            None,
        )
        self.assertIsNotNone(resolved_event)

        health_overview_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/registries/policy/dependencies/health"
                f"?policy_version={version}&include_all_versions=true&include_overview=true"
                "&overview_window_minutes=1440&limit=20"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(health_overview_resp.status_code, 200)
        health_overview_payload = health_overview_resp.json()
        overview = health_overview_payload["dependencyOverview"]
        self.assertIsInstance(overview, dict)
        self.assertGreaterEqual(overview["counts"]["totalAlerts"], 1)
        self.assertGreaterEqual(overview["counts"]["resolvedCount"], 1)
        self.assertGreaterEqual(overview["counts"]["recentChanges"], 1)
        target_row = next(
            (
                row
                for row in overview["byPolicyVersion"]
                if row["policyVersion"] == version
            ),
            None,
        )
        self.assertIsNotNone(target_row)
        assert target_row is not None
        self.assertGreaterEqual(target_row["totalAlerts"], 1)
        self.assertGreaterEqual(target_row["resolvedCount"], 1)
        self.assertEqual(target_row["openBlockedCount"], 0)
        self.assertEqual(target_row["lastStatus"], "resolved")
        resolved_trend = health_overview_payload["dependencyTrend"]
        self.assertIsInstance(resolved_trend, dict)
        self.assertGreaterEqual(resolved_trend["count"], 1)

        resolved_trend_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/registries/policy/dependencies/health"
                f"?policy_version={version}&include_all_versions=true&include_overview=false"
                "&include_trend=true&trend_status=resolved"
                f"&trend_policy_version={version}&trend_limit=1&trend_offset=0"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(resolved_trend_resp.status_code, 200)
        resolved_trend_payload = resolved_trend_resp.json()["dependencyTrend"]
        self.assertEqual(resolved_trend_payload["returned"], 1)
        self.assertGreaterEqual(resolved_trend_payload["count"], 1)
        self.assertEqual(resolved_trend_payload["filters"]["status"], "resolved")
        self.assertEqual(resolved_trend_payload["filters"]["policyVersion"], version)
        self.assertEqual(resolved_trend_payload["items"][0]["status"], "resolved")

    async def test_policy_registry_activate_override_should_require_reason_and_be_auditable(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9213)
        version = f"policy-gate-{suffix}"
        actor = f"policy-actor-{suffix}"

        publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": version,
                "activate": False,
                "actor": actor,
                "reason": "prepare_policy_release",
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_resp.status_code, 200)

        missing_reason_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/registries/policy/{version}/activate"
                f"?override_fairness_gate=true&actor={actor}"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(missing_reason_resp.status_code, 422)
        self.assertIn(
            "registry_fairness_gate_override_reason_required",
            missing_reason_resp.text,
        )

        activate_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/registries/policy/{version}/activate"
                f"?override_fairness_gate=true&actor={actor}&reason=manual_override_for_trial"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(activate_resp.status_code, 200)
        activate_payload = activate_resp.json()
        self.assertEqual(activate_payload["item"]["version"], version)
        self.assertTrue(activate_payload["item"]["isActive"])
        self.assertIsNotNone(activate_payload["dependencyHealth"])
        self.assertTrue(bool(activate_payload["dependencyHealth"]["ok"]))
        self.assertIsNotNone(activate_payload["fairnessGate"])
        self.assertTrue(
            activate_payload["fairnessGate"]["latestRun"] is None
            or isinstance(activate_payload["fairnessGate"]["latestRun"], dict)
        )

        audits_resp = await self._get(
            app=app,
            path="/internal/judge/registries/policy/audits?limit=200",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(audits_resp.status_code, 200)
        audit_items = audits_resp.json()["items"]
        override_audit = next(
            (
                item
                for item in audit_items
                if str(item.get("action") or "") == "activate"
                and str(item.get("version") or "") == version
                and str(item.get("actor") or "") == actor
            ),
            None,
        )
        self.assertIsNotNone(override_audit)
        assert override_audit is not None
        fairness_gate = override_audit["details"].get("fairnessGate")
        self.assertIsInstance(fairness_gate, dict)
        self.assertTrue(bool(fairness_gate.get("overrideApplied")))
        dependency_health = override_audit["details"].get("dependencyHealth")
        self.assertIsInstance(dependency_health, dict)
        self.assertTrue(bool(dependency_health.get("ok")))

    async def test_policy_registry_audits_should_support_gate_link_export_and_filters(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9220)
        override_version = f"policy-audit-override-{suffix}"
        override_actor = f"audit-actor-{suffix}"

        override_publish = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": override_version,
                "activate": False,
                "actor": override_actor,
                "reason": "audit_prepare",
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-v3-default",
                    "toolRegistryVersion": "toolset-v3-default",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(override_publish.status_code, 200)

        override_activate = await self._post(
            app=app,
            path=(
                f"/internal/judge/registries/policy/{override_version}/activate"
                f"?override_fairness_gate=true&actor={override_actor}"
                "&reason=audit_manual_override"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(override_activate.status_code, 200)
        override_gate_code = override_activate.json()["alert"]["details"]["gate"]["code"]

        audits_resp = await self._get(
            app=app,
            path="/internal/judge/registries/policy/audits?limit=200",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(audits_resp.status_code, 200)
        audits_payload = audits_resp.json()
        self.assertGreaterEqual(audits_payload["count"], 2)
        self.assertGreaterEqual(audits_payload["aggregations"]["byAction"]["publish"], 1)
        self.assertGreaterEqual(audits_payload["aggregations"]["byAction"]["activate"], 1)
        self.assertGreaterEqual(audits_payload["aggregations"]["byGateCode"][override_gate_code], 1)
        self.assertGreaterEqual(audits_payload["aggregations"]["withGateReviewCount"], 1)
        self.assertGreaterEqual(audits_payload["aggregations"]["withLinkedAlertsCount"], 1)
        target_item = next(
            (
                row
                for row in audits_payload["items"]
                if row["action"] == "activate"
                and row["version"] == override_version
                and row["actor"] == override_actor
            ),
            None,
        )
        self.assertIsNotNone(target_item)
        assert target_item is not None
        self.assertEqual(target_item["gateReview"]["gateCode"], override_gate_code)
        self.assertTrue(bool(target_item["gateReview"]["overrideApplied"]))
        self.assertIsInstance(target_item["linkedAlertSummary"], dict)
        self.assertGreaterEqual(target_item["linkedAlertSummary"]["count"], 1)
        self.assertGreaterEqual(
            target_item["linkedAlertSummary"]["byType"]["registry_fairness_gate_override"],
            1,
        )
        self.assertTrue(
            any(
                row["type"] == "registry_fairness_gate_override"
                for row in target_item["linkedAlerts"]
            )
        )

        gate_filter_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/registries/policy/audits"
                f"?action=activate&version={override_version}&actor={override_actor}"
                f"&gate_code={override_gate_code}&override_applied=true&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(gate_filter_resp.status_code, 200)
        gate_filter_payload = gate_filter_resp.json()
        self.assertGreaterEqual(gate_filter_payload["returned"], 1)
        self.assertEqual(gate_filter_payload["filters"]["action"], "activate")
        self.assertEqual(gate_filter_payload["filters"]["version"], override_version)
        self.assertEqual(gate_filter_payload["filters"]["actor"], override_actor)
        self.assertEqual(gate_filter_payload["filters"]["gateCode"], override_gate_code)
        self.assertTrue(bool(gate_filter_payload["filters"]["overrideApplied"]))
        self.assertTrue(
            all(
                row["action"] == "activate"
                and row["version"] == override_version
                and row["actor"] == override_actor
                and row["gateReview"]["gateCode"] == override_gate_code
                and bool(row["gateReview"]["overrideApplied"])
                for row in gate_filter_payload["items"]
            )
        )

        no_gate_view_resp = await self._get(
            app=app,
            path="/internal/judge/registries/policy/audits?include_gate_view=false&limit=20",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(no_gate_view_resp.status_code, 200)
        no_gate_view_payload = no_gate_view_resp.json()
        self.assertFalse(bool(no_gate_view_payload["filters"]["includeGateView"]))
        self.assertTrue(
            all(row["linkedAlerts"] is None for row in no_gate_view_payload["items"])
        )

        bad_action_resp = await self._get(
            app=app,
            path="/internal/judge/registries/policy/audits?action=invalid-action",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_action_resp.status_code, 422)
        self.assertIn("invalid_registry_audit_action", bad_action_resp.text)

    async def test_registry_alert_ops_view_should_join_outbox_and_support_filters(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9221)
        blocked_actor = f"ops-blocked-{suffix}"
        override_actor = f"ops-override-{suffix}"

        fairness_blocked_version = f"policy-ops-blocked-{suffix}"
        fairness_blocked_publish = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": fairness_blocked_version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-v3-default",
                    "toolRegistryVersion": "toolset-v3-default",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(fairness_blocked_publish.status_code, 200)
        fairness_blocked_activate = await self._post(
            app=app,
            path=(
                f"/internal/judge/registries/policy/{fairness_blocked_version}/activate"
                f"?actor={blocked_actor}"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(fairness_blocked_activate.status_code, 409)
        fairness_blocked_alert_id = fairness_blocked_activate.json()["detail"]["alert"]["alertId"]
        blocked_gate_code = fairness_blocked_activate.json()["detail"]["alert"]["details"]["gate"]["code"]

        fairness_override_version = f"policy-ops-override-{suffix}"
        fairness_override_publish = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": fairness_override_version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-v3-default",
                    "toolRegistryVersion": "toolset-v3-default",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(fairness_override_publish.status_code, 200)
        fairness_override_activate = await self._post(
            app=app,
            path=(
                f"/internal/judge/registries/policy/{fairness_override_version}/activate"
                f"?override_fairness_gate=true&actor={override_actor}"
                f"&reason=ops_view_override_{suffix}"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(fairness_override_activate.status_code, 200)
        self.assertEqual(
            fairness_override_activate.json()["alert"]["type"],
            "registry_fairness_gate_override",
        )
        override_gate_code = fairness_override_activate.json()["alert"]["details"]["gate"]["code"]

        dep_version = f"policy-ops-dep-{suffix}"
        dep_blocked = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": dep_version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": f"promptset-missing-{suffix}",
                    "toolRegistryVersion": "toolset-v3-default",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(dep_blocked.status_code, 422)
        self.assertEqual(
            dep_blocked.json()["detail"]["alert"]["type"],
            "registry_dependency_health_blocked",
        )

        dep_promptset_version = f"promptset-ops-{suffix}"
        dep_promptset_publish = await self._post_json(
            app=app,
            path="/internal/judge/registries/prompt/publish",
            payload={
                "version": dep_promptset_version,
                "activate": False,
                "profile": {
                    "promptVersions": {
                        "summaryPromptVersion": "v3.a2a3.summary.v1",
                        "agent2PromptVersion": "v3.a6a7.bidirectional.v2",
                        "finalPipelineVersion": "v3-final-a9a10-rollup-v2",
                        "claimGraphVersion": "v1-claim-graph-bootstrap",
                    },
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(dep_promptset_publish.status_code, 200)
        dep_recovered = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": dep_version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": dep_promptset_version,
                    "toolRegistryVersion": "toolset-v3-default",
                    "promptVersions": {
                        "summaryPromptVersion": "v3.a2a3.summary.v1",
                        "agent2PromptVersion": "v3.a6a7.bidirectional.v2",
                        "finalPipelineVersion": "v3-final-a9a10-rollup-v2",
                        "claimGraphVersion": "v1-claim-graph-bootstrap",
                    },
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(dep_recovered.status_code, 200)

        outbox_resp = await self._get(
            app=app,
            path="/internal/judge/alerts/outbox",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(outbox_resp.status_code, 200)
        blocked_event = next(
            (
                row
                for row in outbox_resp.json()["items"]
                if row["alertId"] == fairness_blocked_alert_id
            ),
            None,
        )
        self.assertIsNotNone(blocked_event)
        assert blocked_event is not None
        mark_failed_resp = await self._post(
            app=app,
            path=(
                "/internal/judge/alerts/outbox/"
                f"{blocked_event['eventId']}/delivery?delivery_status=failed&error_message=ops_view_probe"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(mark_failed_resp.status_code, 200)
        self.assertEqual(mark_failed_resp.json()["item"]["deliveryStatus"], "failed")

        ops_view_resp = await self._get(
            app=app,
            path="/internal/judge/alerts/ops-view?limit=200",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(ops_view_resp.status_code, 200)
        ops_payload = ops_view_resp.json()
        self.assertGreaterEqual(ops_payload["count"], 3)
        self.assertGreaterEqual(ops_payload["aggregations"]["byType"]["registry_fairness_gate_blocked"], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["byType"]["registry_fairness_gate_override"], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["byType"]["registry_dependency_health_blocked"], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["byGateCode"][blocked_gate_code], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["byGateCode"][override_gate_code], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["byGateActor"][blocked_actor], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["byGateActor"][override_actor], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["byOverrideApplied"]["true"], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["byOverrideApplied"]["false"], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["overrideAppliedCount"], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["blockedWithoutOverrideCount"], 1)
        self.assertEqual(ops_payload["filters"]["fieldsMode"], "full")
        self.assertTrue(bool(ops_payload["filters"]["includeTrend"]))
        self.assertIsInstance(ops_payload["trend"], dict)
        self.assertGreaterEqual(ops_payload["trend"]["count"], 1)
        blocked_item = next(
            (
                row
                for row in ops_payload["items"]
                if row["alertId"] == fairness_blocked_alert_id
            ),
            None,
        )
        self.assertIsNotNone(blocked_item)
        assert blocked_item is not None
        self.assertEqual(blocked_item["outbox"]["latestDeliveryStatus"], "failed")
        self.assertEqual(blocked_item["gateCode"], blocked_gate_code)
        self.assertEqual(blocked_item["gateActor"], blocked_actor)
        self.assertFalse(bool(blocked_item["overrideApplied"]))

        failed_filter_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/alerts/ops-view"
                "?alert_type=registry_fairness_gate_blocked&delivery_status=failed&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(failed_filter_resp.status_code, 200)
        failed_filter_payload = failed_filter_resp.json()
        self.assertGreaterEqual(failed_filter_payload["returned"], 1)
        self.assertTrue(
            all(
                row["type"] == "registry_fairness_gate_blocked"
                and row["outbox"]["latestDeliveryStatus"] == "failed"
                for row in failed_filter_payload["items"]
            )
        )

        open_filter_resp = await self._get(
            app=app,
            path="/internal/judge/alerts/ops-view?status=open&limit=50",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(open_filter_resp.status_code, 200)
        self.assertTrue(
            all(row["status"] in {"raised", "acked"} for row in open_filter_resp.json()["items"])
        )

        dep_resolved_filter_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/alerts/ops-view"
                f"?alert_type=registry_dependency_health_blocked&status=resolved&policy_version={dep_version}"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(dep_resolved_filter_resp.status_code, 200)
        dep_resolved_payload = dep_resolved_filter_resp.json()
        self.assertGreaterEqual(dep_resolved_payload["returned"], 1)
        self.assertTrue(
            all(
                row["type"] == "registry_dependency_health_blocked"
                and row["status"] == "resolved"
                and row["policyVersion"] == dep_version
                for row in dep_resolved_payload["items"]
            )
        )

        override_gate_filter_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/alerts/ops-view"
                f"?gate_code={override_gate_code}&gate_actor={override_actor}"
                "&override_applied=true&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(override_gate_filter_resp.status_code, 200)
        override_gate_filter_payload = override_gate_filter_resp.json()
        self.assertGreaterEqual(override_gate_filter_payload["returned"], 1)
        self.assertEqual(override_gate_filter_payload["filters"]["gateCode"], override_gate_code)
        self.assertEqual(override_gate_filter_payload["filters"]["gateActor"], override_actor)
        self.assertTrue(bool(override_gate_filter_payload["filters"]["overrideApplied"]))
        self.assertTrue(
            all(
                row["gateCode"] == override_gate_code
                and row["gateActor"] == override_actor
                and bool(row["overrideApplied"])
                for row in override_gate_filter_payload["items"]
            )
        )

        blocked_gate_filter_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/alerts/ops-view"
                f"?gate_code={blocked_gate_code}&gate_actor={blocked_actor}"
                "&override_applied=false&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(blocked_gate_filter_resp.status_code, 200)
        blocked_gate_filter_payload = blocked_gate_filter_resp.json()
        self.assertGreaterEqual(blocked_gate_filter_payload["returned"], 1)
        self.assertEqual(blocked_gate_filter_payload["filters"]["gateCode"], blocked_gate_code)
        self.assertEqual(blocked_gate_filter_payload["filters"]["gateActor"], blocked_actor)
        self.assertFalse(bool(blocked_gate_filter_payload["filters"]["overrideApplied"]))
        self.assertTrue(
            all(
                row["gateCode"] == blocked_gate_code
                and row["gateActor"] == blocked_actor
                and not bool(row["overrideApplied"])
                for row in blocked_gate_filter_payload["items"]
            )
        )

        bad_alert_type_resp = await self._get(
            app=app,
            path="/internal/judge/alerts/ops-view?alert_type=invalid-type",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_alert_type_resp.status_code, 422)
        self.assertIn("invalid_alert_type", bad_alert_type_resp.text)

        bad_status_resp = await self._get(
            app=app,
            path="/internal/judge/alerts/ops-view?status=invalid-status",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_status_resp.status_code, 422)
        self.assertIn("invalid_alert_status", bad_status_resp.text)

        bad_delivery_status_resp = await self._get(
            app=app,
            path="/internal/judge/alerts/ops-view?delivery_status=invalid-delivery",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_delivery_status_resp.status_code, 422)
        self.assertIn("invalid_delivery_status", bad_delivery_status_resp.text)

    async def test_registry_alert_ops_view_should_support_lite_mode_and_trend_window(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9222)

        blocked_version = f"policy-ops-lite-blocked-{suffix}"
        blocked_publish = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": blocked_version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-v3-default",
                    "toolRegistryVersion": "toolset-v3-default",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(blocked_publish.status_code, 200)
        blocked_activate = await self._post(
            app=app,
            path=f"/internal/judge/registries/policy/{blocked_version}/activate",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(blocked_activate.status_code, 409)

        override_version = f"policy-ops-lite-override-{suffix}"
        override_publish = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": override_version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-v3-default",
                    "toolRegistryVersion": "toolset-v3-default",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(override_publish.status_code, 200)
        override_activate = await self._post(
            app=app,
            path=(
                f"/internal/judge/registries/policy/{override_version}/activate"
                f"?override_fairness_gate=true&reason=ops_lite_override_{suffix}"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(override_activate.status_code, 200)

        lite_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/alerts/ops-view"
                "?fields_mode=lite&trend_window_minutes=1440&trend_bucket_minutes=120&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(lite_resp.status_code, 200)
        lite_payload = lite_resp.json()
        self.assertEqual(lite_payload["filters"]["fieldsMode"], "lite")
        self.assertEqual(lite_payload["filters"]["trendWindowMinutes"], 1440)
        self.assertEqual(lite_payload["filters"]["trendBucketMinutes"], 120)
        self.assertIsInstance(lite_payload["trend"], dict)
        self.assertGreaterEqual(lite_payload["trend"]["count"], 2)
        self.assertGreaterEqual(lite_payload["trend"]["typeCounts"]["registry_fairness_gate_blocked"], 1)
        self.assertGreaterEqual(lite_payload["trend"]["typeCounts"]["registry_fairness_gate_override"], 1)
        self.assertGreaterEqual(len(lite_payload["trend"]["timeline"]), 1)
        self.assertGreaterEqual(lite_payload["returned"], 1)
        lite_item = lite_payload["items"][0]
        self.assertNotIn("message", lite_item)
        self.assertIn("outbox", lite_item)
        self.assertIn("latestDeliveryStatus", lite_item["outbox"])
        self.assertIn("totalEvents", lite_item["outbox"])

        no_trend_resp = await self._get(
            app=app,
            path="/internal/judge/alerts/ops-view?include_trend=false&fields_mode=lite&limit=20",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(no_trend_resp.status_code, 200)
        no_trend_payload = no_trend_resp.json()
        self.assertFalse(bool(no_trend_payload["filters"]["includeTrend"]))
        self.assertIsNone(no_trend_payload["trend"])

        bad_fields_mode_resp = await self._get(
            app=app,
            path="/internal/judge/alerts/ops-view?fields_mode=compact",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_fields_mode_resp.status_code, 422)
        self.assertIn("invalid_fields_mode", bad_fields_mode_resp.text)

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

    async def test_npc_coach_shell_route_should_return_not_ready_with_shared_context(
        self,
    ) -> None:
        async def _noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=_noop_callback,
            callback_final_report_impl=_noop_callback,
            callback_phase_failed_impl=_noop_callback,
            callback_final_failed_impl=_noop_callback,
        )
        app = create_app(runtime)

        phase_case_id = _unique_case_id(9301)
        phase_req = _build_phase_request(
            case_id=phase_case_id,
            idempotency_key=f"phase:{phase_case_id}",
        )
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        npc_resp = await self._post_json(
            app=app,
            path=f"/internal/judge/apps/npc-coach/sessions/{phase_req.session_id}/advice",
            payload={
                "trace_id": f"trace-npc-{phase_case_id}",
                "query": "请给我当前阶段的论点补强建议",
                "side": "pro",
                "caseId": phase_case_id,
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(npc_resp.status_code, 200)
        body = npc_resp.json()
        self.assertEqual(body["agentKind"], "npc_coach")
        self.assertEqual(body["status"], "not_ready")
        self.assertEqual(body["errorCode"], "agent_not_enabled")
        self.assertFalse(body["accepted"])
        self.assertEqual(body["capabilityBoundary"]["mode"], "advisory_only")
        self.assertFalse(bool(body["capabilityBoundary"]["officialVerdictAuthority"]))
        self.assertEqual(body["sharedContext"]["sessionId"], phase_req.session_id)
        self.assertEqual(body["sharedContext"]["caseId"], phase_case_id)
        self.assertEqual(body["sharedContext"]["latestDispatchType"], "phase")
        self.assertEqual(body["sharedContext"]["rubricVersion"], phase_req.rubric_version)
        self.assertEqual(
            body["sharedContext"]["judgePolicyVersion"],
            phase_req.judge_policy_version,
        )
        self.assertEqual(body["sharedContext"]["ruleVersion"], phase_req.judge_policy_version)
        self.assertGreaterEqual(body["sharedContext"]["phaseReceiptCount"], 1)

    async def test_room_qa_shell_route_should_return_not_ready_with_final_context(
        self,
    ) -> None:
        async def _noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=_noop_callback,
            callback_final_report_impl=_noop_callback,
            callback_phase_failed_impl=_noop_callback,
            callback_final_failed_impl=_noop_callback,
        )
        app = create_app(runtime)

        phase_case_id = _unique_case_id(9401)
        phase_req = _build_phase_request(
            case_id=phase_case_id,
            idempotency_key=f"phase:{phase_case_id}",
        )
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_case_id = _unique_case_id(9402)
        final_req = _build_final_request(
            case_id=final_case_id,
            idempotency_key=f"final:{final_case_id}",
        )
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        room_qa_resp = await self._post_json(
            app=app,
            path=f"/internal/judge/apps/room-qa/sessions/{final_req.session_id}/answer",
            payload={
                "trace_id": f"trace-room-qa-{final_case_id}",
                "question": "当前辩论进行到什么程度，哪一方更有优势？",
                "caseId": final_case_id,
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(room_qa_resp.status_code, 200)
        body = room_qa_resp.json()
        self.assertEqual(body["agentKind"], "room_qa")
        self.assertEqual(body["status"], "not_ready")
        self.assertEqual(body["errorCode"], "agent_not_enabled")
        self.assertFalse(body["accepted"])
        self.assertEqual(body["capabilityBoundary"]["mode"], "advisory_only")
        self.assertFalse(bool(body["capabilityBoundary"]["officialVerdictAuthority"]))
        self.assertEqual(body["sharedContext"]["sessionId"], final_req.session_id)
        self.assertEqual(body["sharedContext"]["caseId"], final_case_id)
        self.assertEqual(body["sharedContext"]["latestDispatchType"], "final")
        self.assertEqual(body["sharedContext"]["rubricVersion"], final_req.rubric_version)
        self.assertEqual(
            body["sharedContext"]["judgePolicyVersion"],
            final_req.judge_policy_version,
        )
        self.assertEqual(body["sharedContext"]["ruleVersion"], final_req.judge_policy_version)
        self.assertGreaterEqual(body["sharedContext"]["finalReceiptCount"], 1)

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
            final_callback_calls[0][1]["verdictLedger"]["panelDecisions"]["runtimeProfiles"][
                "judgeA"
            ]["profileId"],
            "panel-judgeA-weighted-v1",
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["panelRuntimeProfiles"]["judgeB"][
                "modelStrategy"
            ],
            "deterministic_path_alignment",
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

    async def test_final_dispatch_should_apply_policy_panel_runtime_profiles(self) -> None:
        final_callback_calls: list[tuple[int, dict]] = []

        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            final_callback_calls.append((case_id, payload))

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)
        prompt_publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/prompt/publish",
            payload={
                "version": "promptset-v9-custom",
                "activate": False,
                "profile": {
                    "promptVersions": {
                        "summaryPromptVersion": "summary-v9",
                        "agent2PromptVersion": "agent2-v9",
                        "finalPipelineVersion": "final-v9",
                        "claimGraphVersion": "v1-claim-graph-bootstrap",
                    },
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(prompt_publish_resp.status_code, 200)
        publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": "v3-custom",
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-v9-custom",
                    "toolRegistryVersion": "toolset-v3-default",
                    "promptVersions": {
                        "summaryPromptVersion": "summary-v9",
                        "agent2PromptVersion": "agent2-v9",
                        "finalPipelineVersion": "final-v9",
                        "claimGraphVersion": "v1-claim-graph-bootstrap",
                    },
                    "metadata": {
                        "panelRuntimeProfiles": {
                            "judgeA": {
                                "profileId": "panel-a-custom",
                                "modelStrategy": "llm_vote",
                                "promptVersion": "panel-prompt-v9",
                                "profileSource": "policy_metadata",
                            }
                        }
                    },
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_resp.status_code, 200)
        final_req = _build_final_request(
            case_id=2012,
            idempotency_key="final:2012",
            judge_policy_version="v3-custom",
        )

        resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(final_callback_calls), 1)
        final_payload = final_callback_calls[0][1]
        judge_a_profile = final_payload["verdictLedger"]["panelDecisions"]["runtimeProfiles"][
            "judgeA"
        ]
        self.assertEqual(judge_a_profile["profileId"], "panel-a-custom")
        self.assertEqual(judge_a_profile["modelStrategy"], "llm_vote")
        self.assertEqual(judge_a_profile["promptVersion"], "panel-prompt-v9")
        self.assertEqual(judge_a_profile["profileSource"], "policy_metadata")
        self.assertEqual(
            final_payload["judgeTrace"]["panelRuntimeProfiles"]["judgeA"]["profileId"],
            "panel-a-custom",
        )

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

    async def test_trust_challenge_request_and_decision_should_drive_phaseb_lifecycle(
        self,
    ) -> None:
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

        case_id = _unique_case_id(8420)
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

        before_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=case_id)
        self.assertIsNotNone(before_job)
        assert before_job is not None
        self.assertEqual(before_job.status, "callback_reported")

        request_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/cases/{case_id}/trust/challenges/request"
                "?dispatch_type=auto&reason_code=manual_challenge&reason=need_recheck&requested_by=ops"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(request_resp.status_code, 200)
        request_payload = request_resp.json()
        self.assertTrue(request_payload["ok"])
        self.assertEqual(request_payload["dispatchType"], "final")
        self.assertTrue(str(request_payload["challengeId"]).startswith(f"chlg-{case_id}-"))
        self.assertEqual(request_payload["item"]["version"], "trust-phaseB-challenge-review-v1")
        self.assertEqual(request_payload["item"]["reviewState"], "pending_review")
        self.assertEqual(request_payload["item"]["challengeState"], "under_review")
        self.assertEqual(request_payload["item"]["activeChallengeId"], request_payload["challengeId"])
        self.assertGreaterEqual(request_payload["item"]["totalChallenges"], 1)

        review_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=case_id)
        self.assertIsNotNone(review_job)
        assert review_job is not None
        self.assertEqual(review_job.status, "review_required")

        decision_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/cases/{case_id}/trust/challenges/{request_payload['challengeId']}/decision"
                "?dispatch_type=auto&decision=uphold&actor=reviewer&reason=verified"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(decision_resp.status_code, 200)
        decision_payload = decision_resp.json()
        self.assertTrue(decision_payload["ok"])
        self.assertEqual(decision_payload["decision"], "uphold")
        self.assertEqual(decision_payload["job"]["status"], "callback_reported")
        self.assertEqual(decision_payload["item"]["reviewState"], "approved")
        self.assertEqual(decision_payload["item"]["challengeState"], "challenge_closed")
        self.assertEqual(decision_payload["item"]["activeChallengeId"], None)
        challenges = decision_payload["item"]["challenges"]
        self.assertTrue(any(row["challengeId"] == request_payload["challengeId"] for row in challenges))
        target = next(row for row in challenges if row["challengeId"] == request_payload["challengeId"])
        self.assertEqual(target["currentState"], "challenge_closed")
        self.assertEqual(target["decision"], "verdict_upheld")
        self.assertEqual(target["decisionBy"], "reviewer")

        final_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=case_id)
        self.assertIsNotNone(final_job)
        assert final_job is not None
        self.assertEqual(final_job.status, "callback_reported")

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
        self.assertEqual(
            replay_payload["reportPayload"]["judgeTrace"]["panelRuntimeProfiles"]["judgeC"][
                "profileId"
            ],
            "panel-judgeC-dimension-composite-v1",
        )
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
        self.assertEqual(challenge_item["version"], "trust-phaseB-challenge-review-v1")
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
        await runtime.workflow_runtime.db.create_schema()
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

    async def test_fairness_benchmark_routes_should_persist_and_list_runs(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        run_id = f"run-{_unique_case_id(7601)}"

        post_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": run_id,
                "policy_version": "fairness-benchmark-v1",
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "needs_real_env_reconfirm": True,
                "needs_remediation": False,
                "metrics": {
                    "sample_size": 384,
                    "draw_rate": 0.2,
                    "side_bias_delta": 0.04,
                    "appeal_overturn_rate": 0.07,
                },
                "thresholds": {
                    "draw_rate_max": 0.3,
                    "side_bias_delta_max": 0.08,
                    "appeal_overturn_rate_max": 0.12,
                },
                "summary": {
                    "note": "local reference frozen",
                },
                "source": "harness_freeze_script",
                "reported_by": "ci",
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(post_resp.status_code, 200)
        post_payload = post_resp.json()
        self.assertTrue(post_payload["ok"])
        self.assertEqual(post_payload["item"]["runId"], run_id)
        self.assertEqual(post_payload["item"]["status"], "local_reference_frozen")
        self.assertIsNone(post_payload["alert"])
        self.assertEqual(post_payload["drift"]["baselineRunId"], None)

        list_resp = await self._get(
            app=app,
            path="/internal/judge/fairness/benchmark-runs?policy_version=fairness-benchmark-v1",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(list_resp.status_code, 200)
        list_payload = list_resp.json()
        self.assertGreaterEqual(list_payload["count"], 1)
        self.assertTrue(any(item["runId"] == run_id for item in list_payload["items"]))

        fact_runs = await runtime.workflow_runtime.facts.list_fairness_benchmark_runs(
            policy_version="fairness-benchmark-v1",
            limit=20,
        )
        self.assertTrue(any(item.run_id == run_id for item in fact_runs))

    async def test_fairness_benchmark_threshold_breach_should_raise_alert_outbox(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        baseline_run_id = f"run-{_unique_case_id(7611)}"
        breached_run_id = f"run-{_unique_case_id(7612)}"

        baseline_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": baseline_run_id,
                "policy_version": "fairness-benchmark-v1",
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "metrics": {
                    "sample_size": 384,
                    "draw_rate": 0.2,
                    "side_bias_delta": 0.04,
                    "appeal_overturn_rate": 0.07,
                },
                "thresholds": {
                    "draw_rate_max": 0.3,
                    "side_bias_delta_max": 0.08,
                    "appeal_overturn_rate_max": 0.12,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(baseline_resp.status_code, 200)

        breached_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": breached_run_id,
                "policy_version": "fairness-benchmark-v1",
                "environment_mode": "local_reference",
                "status": "threshold_violation",
                "threshold_decision": "violated",
                "metrics": {
                    "sample_size": 384,
                    "draw_rate": 0.41,
                    "side_bias_delta": 0.04,
                    "appeal_overturn_rate": 0.07,
                },
                "thresholds": {
                    "draw_rate_max": 0.3,
                    "side_bias_delta_max": 0.08,
                    "appeal_overturn_rate_max": 0.12,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(breached_resp.status_code, 200)
        breached_payload = breached_resp.json()
        self.assertTrue(breached_payload["drift"]["hasThresholdBreach"])
        self.assertIn("draw_rate", breached_payload["drift"]["thresholdBreaches"])
        self.assertIsNotNone(breached_payload["alert"])
        self.assertEqual(
            breached_payload["alert"]["type"],
            "fairness_benchmark_threshold_violation",
        )
        self.assertEqual(
            breached_payload["drift"]["baselineRunId"],
            baseline_run_id,
        )

        outbox_resp = await self._get(
            app=app,
            path="/internal/judge/alerts/outbox",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(outbox_resp.status_code, 200)
        outbox_items = outbox_resp.json()["items"]
        self.assertTrue(
            any(
                item.get("payload", {}).get("alertType")
                == "fairness_benchmark_threshold_violation"
                for item in outbox_items
            )
        )

        fact_alerts = await runtime.workflow_runtime.facts.list_audit_alerts(
            job_id=0,
            limit=20,
        )
        self.assertTrue(
            any(item.alert_type == "fairness_benchmark_threshold_violation" for item in fact_alerts)
        )

    async def test_fairness_case_read_model_routes_should_return_case_and_list_views(self) -> None:
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
        case_id = _unique_case_id(7621)
        phase_req = _build_phase_request(
            case_id=case_id,
            idempotency_key=f"phase:{case_id}",
            judge_policy_version="v3-default",
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
            judge_policy_version="v3-default",
        )
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        run_id = f"run-{_unique_case_id(7622)}"
        benchmark_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": run_id,
                "policy_version": "v3-default",
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "metrics": {
                    "sample_size": 384,
                    "draw_rate": 0.2,
                    "side_bias_delta": 0.03,
                    "appeal_overturn_rate": 0.06,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(benchmark_resp.status_code, 200)

        detail_resp = await self._get(
            app=app,
            path=f"/internal/judge/fairness/cases/{case_id}?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(detail_resp.status_code, 200)
        detail_payload = detail_resp.json()
        self.assertEqual(detail_payload["caseId"], case_id)
        self.assertEqual(detail_payload["dispatchType"], "final")
        item = detail_payload["item"]
        self.assertEqual(item["caseId"], case_id)
        self.assertIn(item["gateConclusion"], {"auto_passed", "review_required", "benchmark_attention_required"})
        self.assertIsInstance(item["panelDisagreement"]["runtimeProfiles"], dict)
        self.assertIn("judgeA", item["panelDisagreement"]["runtimeProfiles"])
        self.assertEqual(item["driftSummary"]["latestRun"]["runId"], run_id)

        list_resp = await self._get(
            app=app,
            path="/internal/judge/fairness/cases?dispatch_type=final&limit=50",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(list_resp.status_code, 200)
        list_payload = list_resp.json()
        self.assertGreaterEqual(list_payload["count"], 1)
        self.assertGreaterEqual(list_payload["returned"], 1)
        self.assertTrue(any(row["caseId"] == case_id for row in list_payload["items"]))
        self.assertEqual(list_payload["filters"]["dispatchType"], "final")
        self.assertEqual(list_payload["aggregations"]["totalMatched"], list_payload["count"])
        self.assertGreaterEqual(
            list_payload["aggregations"]["gateConclusionCounts"][item["gateConclusion"]],
            1,
        )
        self.assertGreaterEqual(
            list_payload["aggregations"]["policyVersionCounts"]["v3-default"],
            1,
        )

        challenge_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/cases/{case_id}/trust/challenges/request"
                "?dispatch_type=auto&reason_code=manual_challenge&requested_by=ops&auto_accept=true"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(challenge_resp.status_code, 200)
        challenge_payload = challenge_resp.json()
        self.assertEqual(challenge_payload["item"]["challengeState"], "under_review")

        filtered_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/fairness/cases"
                f"?dispatch_type=final&gate_conclusion={item['gateConclusion']}"
                "&challenge_state=under_review&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(filtered_resp.status_code, 200)
        filtered_payload = filtered_resp.json()
        self.assertGreaterEqual(filtered_payload["count"], 1)
        self.assertTrue(any(row["caseId"] == case_id for row in filtered_payload["items"]))
        self.assertEqual(filtered_payload["filters"]["sortBy"], "updated_at")
        self.assertEqual(filtered_payload["filters"]["sortOrder"], "desc")

        drift_filter_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/fairness/cases"
                "?dispatch_type=final&policy_version=v3-default"
                "&has_threshold_breach=false&has_drift_breach=false&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(drift_filter_resp.status_code, 200)
        drift_filter_payload = drift_filter_resp.json()
        self.assertGreaterEqual(drift_filter_payload["count"], 1)
        self.assertTrue(any(row["caseId"] == case_id for row in drift_filter_payload["items"]))
        self.assertEqual(drift_filter_payload["filters"]["policyVersion"], "v3-default")
        self.assertFalse(drift_filter_payload["filters"]["hasThresholdBreach"])
        self.assertFalse(drift_filter_payload["filters"]["hasDriftBreach"])

        case_id_2 = _unique_case_id(7623)
        phase_req_2 = _build_phase_request(
            case_id=case_id_2,
            idempotency_key=f"phase:{case_id_2}",
            judge_policy_version="v3-default",
        )
        phase_resp_2 = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req_2.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp_2.status_code, 200)
        final_req_2 = _build_final_request(
            case_id=case_id_2,
            idempotency_key=f"final:{case_id_2}",
            judge_policy_version="v3-default",
        )
        final_resp_2 = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req_2.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp_2.status_code, 200)

        page_resp = await self._get(
            app=app,
            path="/internal/judge/fairness/cases?dispatch_type=final&offset=1&limit=1",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(page_resp.status_code, 200)
        page_payload = page_resp.json()
        self.assertGreaterEqual(page_payload["count"], 2)
        self.assertEqual(page_payload["returned"], 1)
        self.assertEqual(page_payload["filters"]["offset"], 1)

        open_review_resp = await self._get(
            app=app,
            path="/internal/judge/fairness/cases?dispatch_type=final&has_open_review=true&limit=50",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(open_review_resp.status_code, 200)
        open_review_payload = open_review_resp.json()
        self.assertTrue(any(row["caseId"] == case_id for row in open_review_payload["items"]))
        self.assertTrue(all(bool(row["challengeLink"]["hasOpenReview"]) for row in open_review_payload["items"]))
        self.assertGreaterEqual(open_review_payload["aggregations"]["openReviewCount"], 1)
        self.assertGreaterEqual(open_review_payload["aggregations"]["withChallengeCount"], 1)

        sorted_resp = await self._get(
            app=app,
            path="/internal/judge/fairness/cases?dispatch_type=final&sort_by=updated_at&sort_order=asc&limit=2",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(sorted_resp.status_code, 200)
        sorted_payload = sorted_resp.json()
        self.assertEqual(sorted_payload["returned"], 2)
        self.assertEqual(sorted_payload["filters"]["sortBy"], "updated_at")
        self.assertEqual(sorted_payload["filters"]["sortOrder"], "asc")
        self.assertEqual(sorted_payload["aggregations"]["totalMatched"], sorted_payload["count"])
        ordered_case_ids = [int(row["caseId"]) for row in sorted_payload["items"]]
        self.assertEqual(ordered_case_ids[0], case_id)
        self.assertEqual(ordered_case_ids[1], case_id_2)

        invalid_gate_resp = await self._get(
            app=app,
            path="/internal/judge/fairness/cases?gate_conclusion=bad-value",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(invalid_gate_resp.status_code, 422)
        self.assertIn("invalid_gate_conclusion", invalid_gate_resp.text)

        invalid_challenge_resp = await self._get(
            app=app,
            path="/internal/judge/fairness/cases?challenge_state=bad-value",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(invalid_challenge_resp.status_code, 422)
        self.assertIn("invalid_challenge_state", invalid_challenge_resp.text)

        invalid_sort_by_resp = await self._get(
            app=app,
            path="/internal/judge/fairness/cases?sort_by=bad-value",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(invalid_sort_by_resp.status_code, 422)
        self.assertIn("invalid_sort_by", invalid_sort_by_resp.text)

        invalid_sort_order_resp = await self._get(
            app=app,
            path="/internal/judge/fairness/cases?sort_order=bad-value",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(invalid_sort_order_resp.status_code, 422)
        self.assertIn("invalid_sort_order", invalid_sort_order_resp.text)

    async def test_panel_runtime_profile_ops_view_should_support_filters_and_aggregations(
        self,
    ) -> None:
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
        case_id = _unique_case_id(7821)

        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=_build_phase_request(
                case_id=case_id,
                idempotency_key=f"phase:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=_build_final_request(
                case_id=case_id,
                idempotency_key=f"final:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        run_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": f"run-{_unique_case_id(7822)}",
                "policy_version": "v3-default",
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "metrics": {
                    "sample_size": 384,
                    "draw_rate": 0.2,
                    "side_bias_delta": 0.03,
                    "appeal_overturn_rate": 0.06,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(run_resp.status_code, 200)

        list_resp = await self._get(
            app=app,
            path="/internal/judge/panels/runtime/profiles?dispatch_type=final&limit=200",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(list_resp.status_code, 200)
        payload = list_resp.json()
        self.assertGreaterEqual(payload["count"], 3)
        self.assertGreaterEqual(payload["returned"], 3)
        self.assertGreaterEqual(payload["aggregations"]["byJudgeId"]["judgeA"], 1)
        self.assertGreaterEqual(payload["aggregations"]["byJudgeId"]["judgeB"], 1)
        self.assertGreaterEqual(payload["aggregations"]["byJudgeId"]["judgeC"], 1)
        self.assertGreaterEqual(
            payload["aggregations"]["byModelStrategy"]["deterministic_path_alignment"],
            1,
        )
        self.assertGreaterEqual(
            payload["aggregations"]["byProfileSource"]["builtin_default"],
            1,
        )
        self.assertTrue(any(row["caseId"] == case_id for row in payload["items"]))

        judge_a_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/panels/runtime/profiles"
                "?dispatch_type=final&judge_id=judgeA"
                "&profile_id=panel-judgeA-weighted-v1&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(judge_a_resp.status_code, 200)
        judge_a_payload = judge_a_resp.json()
        self.assertGreaterEqual(judge_a_payload["count"], 1)
        self.assertEqual(judge_a_payload["filters"]["judgeId"], "judgeA")
        self.assertEqual(
            judge_a_payload["filters"]["profileId"],
            "panel-judgeA-weighted-v1",
        )
        self.assertTrue(
            all(
                row["judgeId"] == "judgeA"
                and row["profileId"] == "panel-judgeA-weighted-v1"
                for row in judge_a_payload["items"]
            )
        )

        judge_b_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/panels/runtime/profiles"
                "?dispatch_type=final&judge_id=judgeB"
                "&model_strategy=deterministic_path_alignment&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(judge_b_resp.status_code, 200)
        judge_b_payload = judge_b_resp.json()
        self.assertGreaterEqual(judge_b_payload["count"], 1)
        self.assertTrue(
            all(
                row["judgeId"] == "judgeB"
                and row["modelStrategy"] == "deterministic_path_alignment"
                for row in judge_b_payload["items"]
            )
        )

        bad_judge_resp = await self._get(
            app=app,
            path="/internal/judge/panels/runtime/profiles?judge_id=judgeX",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_judge_resp.status_code, 422)
        self.assertIn("invalid_panel_judge_id", bad_judge_resp.text)

        bad_source_resp = await self._get(
            app=app,
            path="/internal/judge/panels/runtime/profiles?profile_source=invalid",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_source_resp.status_code, 422)
        self.assertIn("invalid_panel_profile_source", bad_source_resp.text)

        bad_sort_by_resp = await self._get(
            app=app,
            path="/internal/judge/panels/runtime/profiles?sort_by=unknown",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_sort_by_resp.status_code, 422)
        self.assertIn("invalid_panel_runtime_sort_by", bad_sort_by_resp.text)

        bad_sort_order_resp = await self._get(
            app=app,
            path="/internal/judge/panels/runtime/profiles?sort_order=unknown",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_sort_order_resp.status_code, 422)
        self.assertIn("invalid_panel_runtime_sort_order", bad_sort_order_resp.text)

    async def test_create_default_app_should_be_constructible(self) -> None:
        app = create_default_app(load_settings_fn=_build_settings)
        self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main()
