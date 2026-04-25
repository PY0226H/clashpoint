from __future__ import annotations

import unittest
from unittest.mock import patch

from app.app_factory import create_app, create_runtime

from tests.app_factory_test_helpers import (
    AppFactoryRouteTestMixin,
)
from tests.app_factory_test_helpers import (
    build_case_create_request as _build_case_create_request,
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


class AppFactoryCommandDispatchRouteTests(
    AppFactoryRouteTestMixin,
    unittest.IsolatedAsyncioTestCase,
):

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
            phase_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["workflowVersion"],
            "courtroom_8agent_chain_v1",
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["roleContractVersion"],
            "courtroom_role_contract_v1",
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["workflowContractVersion"],
            "courtroom_workflow_contract_v1",
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["artifactContractVersion"],
            "courtroom_artifact_contract_v1",
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["stageContractVersion"],
            "courtroom_stage_contract_v1",
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["mode"],
            "official_verdict_plane",
        )
        self.assertTrue(
            bool(
                phase_callback_calls[0][1]["judgeTrace"]["agentRuntime"][
                    "officialVerdictAuthority"
                ]
            )
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
            phase_callback_calls[0][1]["judgeTrace"]["courtroomRoles"][0]["contractVersion"],
            "courtroom_role_contract_v1",
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["courtroomRoles"][0]["activationScope"],
            "phase_and_final",
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["courtroomRoles"][-1]["activationScope"],
            "final_only",
        )
        self.assertEqual(
            len(phase_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["activeRoles"]),
            5,
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["workflowEdgeCount"],
            7,
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["artifactCount"],
            8,
        )
        self.assertEqual(
            len(phase_callback_calls[0][1]["judgeTrace"]["courtroomWorkflowEdges"]),
            7,
        )
        self.assertEqual(
            len(phase_callback_calls[0][1]["judgeTrace"]["courtroomArtifacts"]),
            8,
        )
        deferred_artifacts = [
            row
            for row in phase_callback_calls[0][1]["judgeTrace"]["courtroomArtifacts"]
            if row.get("availability") == "deferred"
        ]
        self.assertGreaterEqual(len(deferred_artifacts), 1)
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
            final_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["workflowVersion"],
            "courtroom_8agent_chain_v1",
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["roleContractVersion"],
            "courtroom_role_contract_v1",
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["workflowContractVersion"],
            "courtroom_workflow_contract_v1",
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["artifactContractVersion"],
            "courtroom_artifact_contract_v1",
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["stageContractVersion"],
            "courtroom_stage_contract_v1",
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["mode"],
            "official_verdict_plane",
        )
        self.assertTrue(
            bool(
                final_callback_calls[0][1]["judgeTrace"]["agentRuntime"][
                    "officialVerdictAuthority"
                ]
            )
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
        self.assertTrue(
            all(
                str(row.get("contractVersion") or "") == "courtroom_role_contract_v1"
                for row in final_callback_calls[0][1]["judgeTrace"]["courtroomRoles"]
            )
        )
        self.assertEqual(
            len(final_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["activeRoles"]),
            8,
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["workflowEdgeCount"],
            7,
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["artifactCount"],
            8,
        )
        self.assertEqual(
            len(final_callback_calls[0][1]["judgeTrace"]["courtroomWorkflowEdges"]),
            7,
        )
        self.assertEqual(
            len(final_callback_calls[0][1]["judgeTrace"]["courtroomArtifacts"]),
            8,
        )
        self.assertTrue(
            all(
                bool(row.get("available"))
                for row in final_callback_calls[0][1]["judgeTrace"]["courtroomArtifacts"]
            )
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
                        "panelRuntimeContext": {
                            "defaultDomainSlot": "tft_ranked",
                            "runtimeStage": "adaptive_bootstrap",
                            "adaptiveEnabled": True,
                            "candidateModels": ["gpt-5.4", "gpt-5.4-mini"],
                            "strategyMetadata": {"calibrationVersion": "calib-local-v2"},
                            "shadowEnabled": True,
                            "shadowModelStrategy": "shadow_tri_panel_v1",
                            "shadowCostEstimate": 0.031,
                            "shadowLatencyEstimate": 1450,
                        },
                        "panelRuntimeProfiles": {
                            "judgeA": {
                                "profileId": "panel-a-custom",
                                "modelStrategy": "llm_vote",
                                "strategySlot": "adaptive_weighted_vote",
                                "promptVersion": "panel-prompt-v9",
                                "candidateModels": ["gpt-5.4"],
                                "profileSource": "policy_metadata",
                                "shadowCostEstimate": "0.027",
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
        self.assertEqual(judge_a_profile["strategySlot"], "adaptive_weighted_vote")
        self.assertEqual(judge_a_profile["domainSlot"], "tft_ranked")
        self.assertEqual(judge_a_profile["runtimeStage"], "adaptive_bootstrap")
        self.assertTrue(judge_a_profile["adaptiveEnabled"])
        self.assertEqual(judge_a_profile["candidateModels"], ["gpt-5.4"])
        self.assertEqual(
            judge_a_profile["strategyMetadata"]["calibrationVersion"],
            "calib-local-v2",
        )
        self.assertEqual(judge_a_profile["profileSource"], "policy_metadata")
        self.assertTrue(judge_a_profile["shadowEnabled"])
        self.assertEqual(judge_a_profile["shadowModelStrategy"], "shadow_tri_panel_v1")
        self.assertEqual(judge_a_profile["shadowCostEstimate"], 0.027)
        self.assertEqual(judge_a_profile["shadowLatencyEstimate"], 1450.0)
        self.assertEqual(
            final_payload["judgeTrace"]["panelRuntimeProfiles"]["judgeA"]["profileId"],
            "panel-a-custom",
        )
        self.assertEqual(
            final_payload["judgeTrace"]["panelRuntimeProfiles"]["judgeB"]["domainSlot"],
            "tft_ranked",
        )
        self.assertTrue(
            final_payload["judgeTrace"]["panelRuntimeProfiles"]["judgeB"]["shadowEnabled"]
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
                "pipelineVersion": "v3-evidence-bundle",
                "entries": [],
                "refsById": {},
                "messageRefs": [],
                "sourceCitations": [],
                "conflictSources": [],
                "stats": {
                    "totalEntries": 0,
                    "messageRefCount": 0,
                    "sourceCitationCount": 0,
                    "conflictSourceCount": 0,
                    "verdictReferencedCount": 0,
                },
            },
            "verdictLedger": {
                "version": "v2-panel-arbiter-opinion",
                "scoreCard": {"proScore": 61.0, "conScore": 60.2, "dimensionScores": {"logic": 60.0}},
                "panelDecisions": {"probeWinners": {"agent3Weighted": "pro"}},
                "arbitration": {
                    "chainVersion": "v1-panel-fairness-arbiter",
                    "decisionPath": ["judge_panel", "fairness_sentinel", "chief_arbiter"],
                    "fairnessGateApplied": True,
                    "winnerBeforeFairnessGate": "pro",
                    "winnerAfterArbitration": "draw",
                    "gateDecision": "blocked_to_draw",
                    "reviewRequired": True,
                    "verdictLedgerLocked": True,
                },
                "pivotalMoments": [],
                "decisiveEvidenceRefs": [],
            },
            "opinionPack": {
                "version": "v2-opinion-pack",
                "sourceContract": {
                    "ownerAgent": "opinion_writer",
                    "inputObjects": [
                        "verdict_ledger",
                        "evidence_ledger",
                        "fairness_report",
                    ],
                    "verdictLedgerLocked": True,
                    "writesVerdictFacts": False,
                    "rawPromptAllowed": False,
                    "failClosed": True,
                    "status": "passed",
                },
                "factLock": {"winner": "draw"},
                "userReport": {
                    "winner": "draw",
                    "factSource": "verdict_ledger",
                    "debateSummary": "summary",
                    "sideAnalysis": {"pro": "pro", "con": "con"},
                    "verdictReason": "reason",
                    "phaseDebateTimeline": [],
                    "evidenceInsightCards": [],
                },
                "opsSummary": {"reviewRequired": True, "sourceContractStatus": "passed"},
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
            "fairnessSummary": {
                "phase": "phase2",
                "panelHighDisagreement": False,
                "panelDisagreementRatio": 0.0,
                "reviewRequired": True,
                "gateDecision": "blocked_to_draw",
                "reviewReasons": ["style_shift_instability"],
            },
            "judgeTrace": {"traceId": "trace-final-7401"},
            "auditAlerts": [{"type": "style_shift_instability"}],
            "errorCodes": ["style_shift_instability", "fairness_gate_review_required"],
            "degradationLevel": 1,
        }

        with patch(
            "app.applications.bootstrap_final_report_helpers.build_final_report_payload_for_dispatch_v3",
            return_value=gated_payload,
        ):
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

if __name__ == "__main__":
    unittest.main()
