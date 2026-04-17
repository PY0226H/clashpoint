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
        self.assertEqual(
            len(final_judge_result.output.get("activeRoles", [])),
            8,
        )

        self.assertEqual(npc_result.status, "not_ready")
        self.assertEqual(npc_result.error_code, "agent_not_enabled")
        self.assertEqual(npc_result.output.get("kind"), AGENT_KIND_NPC_COACH)
        self.assertEqual(npc_result.output.get("mode"), "advisory_only")
        self.assertFalse(bool(npc_result.output.get("officialVerdictAuthority")))

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
