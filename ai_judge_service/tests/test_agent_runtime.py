from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.applications import build_agent_runtime
from app.domain.agents import (
    AGENT_KIND_JUDGE,
    AGENT_KIND_NPC_COACH,
    AGENT_KIND_ROOM_QA,
    ROLE_CHIEF_ARBITER,
    ROLE_CLAIM_GRAPH,
    ROLE_CLERK,
    ROLE_EVIDENCE,
    ROLE_FAIRNESS_SENTINEL,
    ROLE_JUDGE_PANEL,
    ROLE_OPINION_WRITER,
    ROLE_RECORDER,
    AgentExecutionRequest,
)


class AgentRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_build_agent_runtime_should_register_shell_profiles(self) -> None:
        runtime = build_agent_runtime(settings=SimpleNamespace(openai_timeout_secs=25.0))

        profiles = runtime.list_profiles()
        kinds = [row.kind for row in profiles]
        self.assertEqual(kinds, [AGENT_KIND_JUDGE, AGENT_KIND_NPC_COACH, AGENT_KIND_ROOM_QA])
        self.assertTrue(runtime.get_profile(AGENT_KIND_JUDGE).enabled)  # type: ignore[union-attr]
        self.assertFalse(runtime.get_profile(AGENT_KIND_NPC_COACH).enabled)  # type: ignore[union-attr]
        self.assertFalse(runtime.get_profile(AGENT_KIND_ROOM_QA).enabled)  # type: ignore[union-attr]
        self.assertIn(
            "advisory_only",
            runtime.get_profile(AGENT_KIND_NPC_COACH).tags,  # type: ignore[union-attr]
        )
        self.assertIn(
            "no_verdict_write",
            runtime.get_profile(AGENT_KIND_ROOM_QA).tags,  # type: ignore[union-attr]
        )

    async def test_execute_should_enable_deterministic_assistant_placeholder_when_configured(
        self,
    ) -> None:
        runtime = build_agent_runtime(
            settings=SimpleNamespace(
                openai_timeout_secs=25.0,
                assistant_advisory_placeholder_enabled=True,
            )
        )

        npc_profile = runtime.get_profile(AGENT_KIND_NPC_COACH)
        room_qa_profile = runtime.get_profile(AGENT_KIND_ROOM_QA)
        self.assertTrue(npc_profile.enabled)  # type: ignore[union-attr]
        self.assertTrue(room_qa_profile.enabled)  # type: ignore[union-attr]

        advisory_context = {
            "roomContextSnapshot": {
                "phaseReceiptCount": 1,
                "finalReceiptCount": 0,
            },
            "stageSummary": {
                "stage": "phase_context_available",
                "workflowStatus": "done",
                "hasPhaseReceipt": True,
                "hasFinalReceipt": False,
            },
        }
        result = await runtime.execute(
            AgentExecutionRequest(
                kind=AGENT_KIND_NPC_COACH,
                input_payload={
                    "sessionId": 11,
                    "query": "我该怎么回应？",
                    "side": "pro",
                    "advisoryContext": advisory_context,
                },
                trace_id="trace-npc-placeholder",
                session_id=11,
            )
        )
        room_qa_result = await runtime.execute(
            AgentExecutionRequest(
                kind=AGENT_KIND_ROOM_QA,
                input_payload={
                    "sessionId": 11,
                    "question": "当前上下文阶段是什么？",
                    "advisoryContext": advisory_context,
                },
                trace_id="trace-room-placeholder",
                session_id=11,
            )
        )

        self.assertEqual(result.status, "ok")
        self.assertIsNone(result.error_code)
        self.assertEqual(result.output.get("accepted"), True)
        self.assertEqual(result.output.get("mode"), "advisory_only")
        self.assertTrue(result.output.get("advisoryOnly"))
        self.assertEqual(
            result.output.get("availableContext"),
            {
                "stage": "phase_context_available",
                "stageLabel": "已有阶段上下文",
                "workflowStatus": "done",
                "hasPhaseReceipt": True,
                "hasFinalReceipt": False,
                "receiptSummary": "phase 1 / final 0",
                "officialVerdictFieldsRedacted": True,
            },
        )
        self.assertIn("safeGuidanceSummary", result.output)
        self.assertIn("suggestedNextQuestions", result.output)
        self.assertNotIn("winner", result.output)
        self.assertNotIn("verdictReason", result.output)
        self.assertEqual(room_qa_result.status, "ok")
        self.assertIn("当前上下文阶段：已有阶段上下文", room_qa_result.output["safeGuidanceSummary"])

    async def test_execute_should_enable_judge_courtroom_runtime(self) -> None:
        runtime = build_agent_runtime(settings=SimpleNamespace(openai_timeout_secs=25.0))

        judge_result = await runtime.execute(
            AgentExecutionRequest(
                kind=AGENT_KIND_JUDGE,
                input_payload={"caseId": 101, "phaseNo": 3},
                trace_id="trace-101",
                session_id=11,
                scope_id=1,
                metadata={"dispatchType": "phase"},
            )
        )
        npc_result = await runtime.execute(
            AgentExecutionRequest(
                kind=AGENT_KIND_NPC_COACH,
                input_payload={"sessionId": 11},
                trace_id="trace-102",
            )
        )

        self.assertEqual(judge_result.status, "ok")
        self.assertIsNone(judge_result.error_code)
        self.assertEqual(judge_result.output.get("accepted"), True)
        self.assertEqual(judge_result.output.get("mode"), "official_verdict_plane")
        self.assertTrue(bool(judge_result.output.get("officialVerdictAuthority")))
        self.assertEqual(judge_result.output.get("dispatchType"), "phase")
        self.assertEqual(judge_result.output.get("runtimeVersion"), "courtroom_agent_runtime_mvp_v1")
        self.assertEqual(judge_result.output.get("workflowVersion"), "courtroom_8agent_chain_v1")
        self.assertEqual(
            judge_result.output.get("roleContractVersion"),
            "courtroom_role_contract_v1",
        )
        self.assertEqual(
            judge_result.output.get("workflowContractVersion"),
            "courtroom_workflow_contract_v1",
        )
        self.assertEqual(
            judge_result.output.get("artifactContractVersion"),
            "courtroom_artifact_contract_v1",
        )
        self.assertEqual(
            judge_result.output.get("stageContractVersion"),
            "courtroom_stage_contract_v1",
        )
        self.assertEqual(
            judge_result.output.get("roleOrder"),
            [
                ROLE_CLERK,
                ROLE_RECORDER,
                ROLE_CLAIM_GRAPH,
                ROLE_EVIDENCE,
                ROLE_JUDGE_PANEL,
                ROLE_FAIRNESS_SENTINEL,
                ROLE_CHIEF_ARBITER,
                ROLE_OPINION_WRITER,
            ],
        )
        self.assertEqual(
            judge_result.output.get("activeRoles"),
            [
                ROLE_CLERK,
                ROLE_RECORDER,
                ROLE_CLAIM_GRAPH,
                ROLE_EVIDENCE,
                ROLE_JUDGE_PANEL,
            ],
        )
        role_rows = judge_result.output.get("roles")
        self.assertTrue(isinstance(role_rows, list) and len(role_rows) == 8)
        assert isinstance(role_rows, list)
        self.assertEqual(role_rows[0]["state"], "active")
        self.assertEqual(role_rows[-1]["state"], "deferred")
        self.assertEqual(role_rows[0]["stageTag"], "blinded")
        self.assertEqual(role_rows[-1]["stageTag"], "opinion_written")
        self.assertEqual(role_rows[0]["activationScope"], "phase_and_final")
        self.assertEqual(role_rows[-1]["activationScope"], "final_only")
        self.assertEqual(role_rows[0]["contractVersion"], "courtroom_role_contract_v1")
        self.assertIsInstance(role_rows[0]["contract"], dict)
        self.assertEqual(role_rows[0]["contract"]["version"], "courtroom_role_contract_v1")
        self.assertEqual(role_rows[0]["contract"]["stageTag"], "blinded")
        self.assertEqual(role_rows[0]["outputArtifacts"], ["case_dossier"])
        self.assertEqual(role_rows[-1]["inputArtifacts"], ["final_verdict"])

        workflow_edges = judge_result.output.get("workflowEdges")
        self.assertTrue(isinstance(workflow_edges, list) and len(workflow_edges) == 7)
        assert isinstance(workflow_edges, list)
        self.assertEqual(
            workflow_edges[0],
            {
                "sequence": 1,
                "fromRole": ROLE_CLERK,
                "toRole": ROLE_RECORDER,
                "condition": "on_success",
            },
        )
        self.assertEqual(
            workflow_edges[-1]["toRole"],
            ROLE_OPINION_WRITER,
        )

        artifacts = judge_result.output.get("artifacts")
        self.assertTrue(isinstance(artifacts, list) and len(artifacts) == 8)
        assert isinstance(artifacts, list)
        self.assertTrue(artifacts[0]["available"])
        self.assertFalse(artifacts[-1]["available"])
        self.assertEqual(artifacts[-1]["availability"], "deferred")

        final_judge_result = await runtime.execute(
            AgentExecutionRequest(
                kind=AGENT_KIND_JUDGE,
                input_payload={"caseId": 101, "phaseStartNo": 1, "phaseEndNo": 3},
                trace_id="trace-101-final",
                session_id=11,
                scope_id=1,
                metadata={"dispatchType": "final"},
            )
        )
        final_artifacts = final_judge_result.output.get("artifacts")
        self.assertTrue(isinstance(final_artifacts, list) and len(final_artifacts) == 8)
        assert isinstance(final_artifacts, list)
        self.assertTrue(all(bool(item.get("available")) for item in final_artifacts))
        final_roles = final_judge_result.output.get("roles")
        self.assertTrue(isinstance(final_roles, list) and len(final_roles) == 8)
        assert isinstance(final_roles, list)
        self.assertTrue(all(bool(row.get("active")) for row in final_roles))
        self.assertTrue(
            all(str(row.get("contractVersion") or "") == "courtroom_role_contract_v1" for row in final_roles)
        )
        self.assertEqual(
            len(final_judge_result.output.get("activeRoles", [])),
            8,
        )

        self.assertEqual(npc_result.status, "not_ready")
        self.assertEqual(npc_result.error_code, "agent_not_enabled")
        self.assertEqual(npc_result.output.get("kind"), AGENT_KIND_NPC_COACH)
        self.assertEqual(npc_result.output.get("mode"), "advisory_only")
        self.assertTrue(bool(npc_result.output.get("advisoryOnly")))
        self.assertNotIn("officialVerdictAuthority", npc_result.output)
        self.assertNotIn("writesVerdictLedger", npc_result.output)
        self.assertNotIn("writesJudgeTrace", npc_result.output)
        self.assertNotIn("canTriggerOfficialJudgeRoles", npc_result.output)
        self.assertEqual(
            npc_result.output.get("policyIsolation"),
            "assistant_advisory_policy",
        )
        self.assertIn(
            "knowledge_gateway",
            npc_result.output.get("allowedContextSources", []),
        )

    async def test_execute_should_report_error_for_unknown_agent_kind(self) -> None:
        runtime = build_agent_runtime(settings=SimpleNamespace(openai_timeout_secs=25.0))

        result = await runtime.execute(
            AgentExecutionRequest(  # type: ignore[arg-type]
                kind="unknown",
                input_payload={},
                trace_id="trace-unknown",
            )
        )
        self.assertEqual(result.status, "error")
        self.assertEqual(result.error_code, "agent_not_registered")


if __name__ == "__main__":
    unittest.main()
