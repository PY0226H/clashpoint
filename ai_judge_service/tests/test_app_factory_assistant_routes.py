from __future__ import annotations

import unittest
from typing import Any

from app.app_factory import create_app, create_runtime
from app.domain.agents import AgentExecutionResult

from tests.app_factory_test_helpers import (
    AppFactoryRouteTestMixin,
)
from tests.app_factory_test_helpers import (
    build_final_request as _build_final_request,
)
from tests.app_factory_test_helpers import (
    build_phase_request as _build_phase_request,
)
from tests.app_factory_test_helpers import (
    build_settings as _build_settings,
)
from tests.app_factory_test_helpers import (
    unique_case_id as _unique_case_id,
)


class AppFactoryAssistantRouteTests(
    AppFactoryRouteTestMixin,
    unittest.IsolatedAsyncioTestCase,
):

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
        ledger_before = await runtime.workflow_runtime.facts.list_judge_ledger_snapshots(
            case_id=phase_case_id,
            limit=20,
        )
        events_before = await runtime.workflow_runtime.store.list_events(
            job_id=phase_case_id,
        )

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
        self.assertEqual(body["version"], "assistant_advisory_contract_v1")
        self.assertEqual(body["agentKind"], "npc_coach")
        self.assertTrue(body["advisoryOnly"])
        self.assertEqual(body["status"], "not_ready")
        self.assertEqual(body["errorCode"], "agent_not_enabled")
        self.assertFalse(body["accepted"])
        self.assertEqual(body["capabilityBoundary"]["mode"], "advisory_only")
        self.assertTrue(body["capabilityBoundary"]["advisoryOnly"])
        self.assertFalse(bool(body["capabilityBoundary"]["officialVerdictAuthority"]))
        self.assertFalse(bool(body["capabilityBoundary"]["writesVerdictLedger"]))
        self.assertFalse(bool(body["capabilityBoundary"]["writesJudgeTrace"]))
        self.assertFalse(
            bool(body["capabilityBoundary"]["canTriggerOfficialJudgeRoles"])
        )
        self.assertIn(
            "verdict_ledger",
            body["capabilityBoundary"]["forbiddenWriteTargets"],
        )
        self.assertEqual(body["sharedContext"]["sessionId"], phase_req.session_id)
        self.assertEqual(body["sharedContext"]["caseId"], phase_case_id)
        self.assertEqual(body["sharedContext"]["latestDispatchType"], "phase")
        self.assertNotIn("rubricVersion", body["sharedContext"])
        self.assertEqual(
            body["advisoryContext"]["versionContext"]["rubricVersion"],
            phase_req.rubric_version,
        )
        self.assertEqual(
            body["advisoryContext"]["versionContext"]["judgePolicyVersion"],
            phase_req.judge_policy_version,
        )
        self.assertEqual(
            body["advisoryContext"]["versionContext"]["ruleVersion"],
            phase_req.judge_policy_version,
        )
        self.assertGreaterEqual(body["sharedContext"]["phaseReceiptCount"], 1)
        self.assertTrue(body["sharedContext"]["officialVerdictFieldsRedacted"])
        self.assertNotIn("winnerHint", body["sharedContext"])
        self.assertNotIn("debateSummary", body["sharedContext"])
        self.assertTrue(body["advisoryContext"]["advisoryOnly"])
        self.assertEqual(
            body["advisoryContext"]["stageSummary"]["stage"],
            "phase_context_available",
        )
        self.assertFalse(
            body["advisoryContext"]["knowledgeGateway"]["policyBinding"][
                "officialVerdictPolicy"
            ]
        )
        self.assertEqual(
            body["advisoryContext"]["knowledgeGateway"]["policyBinding"][
                "policyVersion"
            ],
            "npc_coach_advisory_policy_v1",
        )
        self.assertFalse(body["cacheProfile"]["cacheable"])
        self.assertEqual(body["cacheProfile"]["ttlSeconds"], 0)
        ledger_after = await runtime.workflow_runtime.facts.list_judge_ledger_snapshots(
            case_id=phase_case_id,
            limit=20,
        )
        events_after = await runtime.workflow_runtime.store.list_events(
            job_id=phase_case_id,
        )
        self.assertEqual(
            [
                (row.dispatch_type, row.trace_id, row.updated_at.isoformat())
                for row in ledger_after
            ],
            [
                (row.dispatch_type, row.trace_id, row.updated_at.isoformat())
                for row in ledger_before
            ],
        )
        self.assertEqual(
            [(row.event_seq, row.event_type) for row in events_after],
            [(row.event_seq, row.event_type) for row in events_before],
        )

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
        self.assertEqual(body["version"], "assistant_advisory_contract_v1")
        self.assertEqual(body["agentKind"], "room_qa")
        self.assertTrue(body["advisoryOnly"])
        self.assertEqual(body["status"], "not_ready")
        self.assertEqual(body["errorCode"], "agent_not_enabled")
        self.assertFalse(body["accepted"])
        self.assertEqual(body["capabilityBoundary"]["mode"], "advisory_only")
        self.assertFalse(bool(body["capabilityBoundary"]["officialVerdictAuthority"]))
        self.assertEqual(body["sharedContext"]["sessionId"], final_req.session_id)
        self.assertEqual(body["sharedContext"]["caseId"], final_case_id)
        self.assertEqual(body["sharedContext"]["latestDispatchType"], "final")
        self.assertNotIn("rubricVersion", body["sharedContext"])
        self.assertEqual(
            body["advisoryContext"]["versionContext"]["rubricVersion"],
            final_req.rubric_version,
        )
        self.assertEqual(
            body["advisoryContext"]["versionContext"]["judgePolicyVersion"],
            final_req.judge_policy_version,
        )
        self.assertEqual(
            body["advisoryContext"]["versionContext"]["ruleVersion"],
            final_req.judge_policy_version,
        )
        self.assertGreaterEqual(body["sharedContext"]["finalReceiptCount"], 1)
        self.assertTrue(body["sharedContext"]["officialVerdictFieldsRedacted"])
        self.assertNotIn("winnerHint", body["sharedContext"])
        self.assertNotIn("verdictReason", body["sharedContext"])
        self.assertEqual(
            body["advisoryContext"]["stageSummary"]["stage"],
            "final_context_available",
        )
        self.assertFalse(
            body["advisoryContext"]["knowledgeGateway"]["policyBinding"][
                "officialVerdictPolicy"
            ]
        )
        self.assertEqual(
            body["advisoryContext"]["knowledgeGateway"]["policyBinding"][
                "policyVersion"
            ],
            "room_qa_advisory_policy_v1",
        )
        self.assertFalse(body["cacheProfile"]["cacheable"])
        self.assertEqual(body["cacheProfile"]["ttlSeconds"], 0)

    async def test_npc_coach_route_should_fail_closed_on_official_verdict_chain_fields(
        self,
    ) -> None:
        async def _noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        class _NpcAdvisoryTestExecutor:
            async def execute(self, request: Any) -> AgentExecutionResult:
                del request
                return AgentExecutionResult(
                    status="ok",
                    output={
                        "accepted": True,
                        "advice": "建议先补强证据再推进反驳。",
                        "winner": "pro",
                        "verdictReason": "should_be_blocked",
                        "nested": {
                            "needsDrawVote": True,
                            "hint": "保留字段",
                        },
                        "timeline": [
                            {
                                "dimensionScores": {"logic": 9},
                                "note": "保留注记",
                            }
                        ],
                    },
                )

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=_noop_callback,
            callback_final_report_impl=_noop_callback,
            callback_phase_failed_impl=_noop_callback,
            callback_final_failed_impl=_noop_callback,
        )
        runtime.agent_runtime.registry._executors["npc_coach"] = _NpcAdvisoryTestExecutor()  # type: ignore[attr-defined]
        app = create_app(runtime)

        phase_case_id = _unique_case_id(9351)
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
        self.assertEqual(npc_resp.status_code, 500)
        body = npc_resp.json()
        self.assertEqual(body["detail"], "assistant_advisory_contract_violation")

if __name__ == "__main__":
    unittest.main()
