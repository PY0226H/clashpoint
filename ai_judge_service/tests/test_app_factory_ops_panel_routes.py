from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from app.app_factory import create_app, create_runtime
from app.applications.ops_read_model_pack import (
    OPS_READ_MODEL_PACK_V5_ADAPTIVE_SUMMARY_KEYS,
    OPS_READ_MODEL_PACK_V5_CASE_LIFECYCLE_OVERVIEW_KEYS,
    OPS_READ_MODEL_PACK_V5_FILTER_KEYS,
    OPS_READ_MODEL_PACK_V5_JUDGE_WORKFLOW_COVERAGE_KEYS,
    OPS_READ_MODEL_PACK_V5_READ_CONTRACT_KEYS,
    OPS_READ_MODEL_PACK_V5_TOP_LEVEL_KEYS,
    OPS_READ_MODEL_PACK_V5_TRUST_OVERVIEW_KEYS,
    validate_ops_read_model_pack_v5_contract,
)
from app.applications.panel_runtime_profile_contract import (
    PANEL_RUNTIME_PROFILE_AGGREGATIONS_KEYS,
    PANEL_RUNTIME_PROFILE_FILTER_KEYS,
    PANEL_RUNTIME_PROFILE_ITEM_KEYS,
    PANEL_RUNTIME_PROFILE_TOP_LEVEL_KEYS,
    validate_panel_runtime_profile_contract,
)

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


class AppFactoryOpsPanelRouteTests(
    AppFactoryRouteTestMixin,
    unittest.IsolatedAsyncioTestCase,
):

    async def test_ops_read_model_pack_route_should_join_fairness_registry_and_trust_v5(
        self,
    ) -> None:
        async def noop_callback(
            *, cfg: object, case_id: int, payload: dict[str, Any]
        ) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)
        case_id = _unique_case_id(7844)

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

        pack_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/ops/read-model/pack"
                "?dispatch_type=final&policy_version=v3-default"
                "&window_days=7&top_limit=10&case_scan_limit=200"
                "&include_case_trust=true&trust_case_limit=3"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(pack_resp.status_code, 200)
        payload = pack_resp.json()
        self.assertEqual(set(payload.keys()), set(OPS_READ_MODEL_PACK_V5_TOP_LEVEL_KEYS))
        self.assertEqual(
            set(payload["adaptiveSummary"].keys()),
            set(OPS_READ_MODEL_PACK_V5_ADAPTIVE_SUMMARY_KEYS),
        )
        self.assertEqual(
            set(payload["trustOverview"].keys()),
            set(OPS_READ_MODEL_PACK_V5_TRUST_OVERVIEW_KEYS),
        )
        self.assertEqual(
            set(payload["judgeWorkflowCoverage"].keys()),
            set(OPS_READ_MODEL_PACK_V5_JUDGE_WORKFLOW_COVERAGE_KEYS),
        )
        self.assertEqual(
            set(payload["caseLifecycleOverview"].keys()),
            set(OPS_READ_MODEL_PACK_V5_CASE_LIFECYCLE_OVERVIEW_KEYS),
        )
        self.assertEqual(
            set(payload["readContract"].keys()),
            set(OPS_READ_MODEL_PACK_V5_READ_CONTRACT_KEYS),
        )
        self.assertEqual(
            set(payload["filters"].keys()),
            set(OPS_READ_MODEL_PACK_V5_FILTER_KEYS),
        )
        validate_ops_read_model_pack_v5_contract(payload)
        self.assertIsInstance(payload["fairnessDashboard"], dict)
        self.assertIsInstance(payload["fairnessCalibrationAdvisor"], dict)
        self.assertIsInstance(payload["panelRuntimeReadiness"], dict)
        self.assertIsInstance(payload["registryGovernance"], dict)
        self.assertIsInstance(payload["registryPromptToolGovernance"], dict)
        self.assertIsInstance(payload["courtroomReadModel"], dict)
        self.assertIsInstance(payload["courtroomQueue"], dict)
        self.assertIsInstance(payload["courtroomDrilldown"], dict)
        self.assertIsInstance(payload["reviewQueue"], dict)
        self.assertIsInstance(payload["reviewTrustPriority"], dict)
        self.assertIsInstance(payload["evidenceClaimQueue"], dict)
        self.assertIsInstance(payload["trustChallengeQueue"], dict)
        self.assertIsInstance(payload["policyGateSimulation"], dict)
        self.assertIsInstance(payload["adaptiveSummary"], dict)
        self.assertIsInstance(payload["trustOverview"], dict)
        self.assertIsInstance(payload["trustMonitoring"], dict)
        self.assertIsInstance(payload["judgeWorkflowCoverage"], dict)
        self.assertIsInstance(payload["caseLifecycleOverview"], dict)
        self.assertIsInstance(payload["caseChainCoverage"], dict)
        self.assertIsInstance(payload["fairnessGateOverview"], dict)
        self.assertIsInstance(payload["policyKernelBinding"], dict)
        self.assertIsInstance(payload["readContract"], dict)
        self.assertGreaterEqual(
            payload["fairnessDashboard"]["overview"]["totalMatched"],
            1,
        )
        self.assertIn("releaseGate", payload["fairnessCalibrationAdvisor"])
        self.assertIn("groups", payload["panelRuntimeReadiness"])
        self.assertIn("calibrationGateCode", payload["adaptiveSummary"])
        self.assertGreaterEqual(payload["adaptiveSummary"]["recommendedActionCount"], 1)
        self.assertIn("reviewQueueCount", payload["adaptiveSummary"])
        self.assertIn("policySimulationBlockedCount", payload["adaptiveSummary"])
        self.assertIn("courtroomSampleCount", payload["adaptiveSummary"])
        self.assertIn("courtroomQueueCount", payload["adaptiveSummary"])
        self.assertIn("courtroomDrilldownCount", payload["adaptiveSummary"])
        self.assertIn("courtroomDrilldownHighRiskCount", payload["adaptiveSummary"])
        self.assertIn("evidenceClaimQueueCount", payload["adaptiveSummary"])
        self.assertIn("evidenceClaimHighRiskCount", payload["adaptiveSummary"])
        self.assertIn("registryPromptToolRiskCount", payload["adaptiveSummary"])
        self.assertIn("trustChallengeQueueCount", payload["adaptiveSummary"])
        self.assertIn("reviewTrustPriorityCount", payload["adaptiveSummary"])
        self.assertIn("reviewUnifiedHighPriorityCount", payload["adaptiveSummary"])
        self.assertGreaterEqual(payload["adaptiveSummary"]["reviewQueueCount"], 0)
        self.assertGreaterEqual(payload["adaptiveSummary"]["courtroomSampleCount"], 1)
        self.assertGreaterEqual(payload["adaptiveSummary"]["courtroomQueueCount"], 1)
        self.assertGreaterEqual(payload["adaptiveSummary"]["courtroomDrilldownCount"], 1)
        self.assertGreaterEqual(payload["adaptiveSummary"]["evidenceClaimQueueCount"], 1)
        self.assertGreaterEqual(
            payload["adaptiveSummary"]["registryPromptToolRiskCount"],
            0,
        )
        self.assertIn(
            "activeVersions",
            payload["registryGovernance"],
        )
        self.assertIn(
            "dependencyHealth",
            payload["registryGovernance"],
        )
        self.assertIn("summary", payload["registryPromptToolGovernance"])
        self.assertIn("riskItems", payload["registryPromptToolGovernance"])
        self.assertGreaterEqual(payload["courtroomReadModel"]["count"], 1)
        self.assertIn("items", payload["courtroomReadModel"])
        self.assertGreaterEqual(payload["courtroomQueue"]["count"], 1)
        self.assertEqual(payload["courtroomQueue"]["filters"]["sortBy"], "risk_score")
        self.assertEqual(payload["courtroomQueue"]["filters"]["dispatchType"], "auto")
        self.assertGreaterEqual(payload["courtroomDrilldown"]["count"], 1)
        self.assertIn("aggregations", payload["courtroomDrilldown"])
        self.assertIn("simulatedGate", payload["policyGateSimulation"]["items"][0])
        self.assertGreaterEqual(payload["reviewQueue"]["count"], 0)
        self.assertEqual(payload["reviewQueue"]["filters"]["sortBy"], "risk_score")
        self.assertGreaterEqual(payload["reviewTrustPriority"]["count"], 0)
        self.assertEqual(
            payload["reviewTrustPriority"]["filters"]["sortBy"],
            "unified_priority_score",
        )
        self.assertGreaterEqual(payload["evidenceClaimQueue"]["count"], 1)
        self.assertEqual(payload["evidenceClaimQueue"]["filters"]["sortBy"], "risk_score")
        self.assertIn("aggregations", payload["evidenceClaimQueue"])
        self.assertEqual(
            payload["adaptiveSummary"]["evidenceClaimConflictCaseCount"],
            payload["evidenceClaimQueue"]["aggregations"]["conflictCaseCount"],
        )
        self.assertEqual(
            payload["adaptiveSummary"]["evidenceClaimUnansweredClaimCaseCount"],
            payload["evidenceClaimQueue"]["aggregations"]["unansweredCaseCount"],
        )
        self.assertGreaterEqual(payload["trustChallengeQueue"]["count"], 0)
        self.assertEqual(payload["trustChallengeQueue"]["filters"]["challengeState"], "open")
        self.assertGreaterEqual(payload["trustOverview"]["count"], 1)
        self.assertGreaterEqual(payload["trustOverview"]["verifiedCount"], 0)
        self.assertLessEqual(
            payload["trustOverview"]["verifiedCount"],
            payload["trustOverview"]["count"],
        )
        self.assertGreaterEqual(payload["trustOverview"]["reviewRequiredCount"], 0)
        self.assertIn("artifactStoreReadiness", payload["trustMonitoring"])
        self.assertIn("publicVerificationReadiness", payload["trustMonitoring"])
        self.assertIn("registryReleaseReadiness", payload["trustMonitoring"])
        self.assertFalse(
            payload["trustMonitoring"]["redactionContract"]["internalAuditPayloadVisible"]
        )
        self.assertTrue(
            any(row["caseId"] == case_id for row in payload["trustOverview"]["items"])
        )
        self.assertGreaterEqual(payload["judgeWorkflowCoverage"]["totalCases"], 1)
        self.assertGreaterEqual(payload["judgeWorkflowCoverage"]["fullCount"], 1)
        self.assertLessEqual(payload["judgeWorkflowCoverage"]["fullCoverageRate"], 1.0)
        self.assertGreaterEqual(payload["caseLifecycleOverview"]["totalCases"], 1)
        self.assertIn("workflowStatusCounts", payload["caseLifecycleOverview"])
        self.assertIn("lifecycleBucketCounts", payload["caseLifecycleOverview"])
        self.assertIn(
            "/internal/judge/ops/read-model/pack",
            payload["readContract"]["opsRoutes"],
        )
        self.assertIn("winner", payload["readContract"]["fieldLayers"]["userVisible"])
        self.assertIn(
            "caseLifecycleOverview",
            payload["readContract"]["fieldLayers"]["opsVisible"],
        )
        self.assertFalse(
            payload["readContract"]["errorSemantics"]["rawStringFallbackAllowed"]
        )
        self.assertGreaterEqual(payload["caseChainCoverage"]["totalCases"], 1)
        self.assertGreaterEqual(payload["caseChainCoverage"]["completeCount"], 1)
        self.assertIn("byObjectPresence", payload["caseChainCoverage"])
        self.assertIn("caseDossier", payload["caseChainCoverage"]["byObjectPresence"])
        self.assertGreaterEqual(payload["fairnessGateOverview"]["totalCases"], 1)
        self.assertIn("caseDecisionCounts", payload["fairnessGateOverview"])
        self.assertIn("policyGateDecisionCounts", payload["fairnessGateOverview"])
        self.assertIn("policyGateSourceCounts", payload["fairnessGateOverview"])
        self.assertIn("gateDecisionCounts", payload["policyKernelBinding"])
        self.assertGreaterEqual(payload["policyKernelBinding"]["trackedPolicyVersionCount"], 1)
        self.assertGreaterEqual(payload["policyKernelBinding"]["kernelBoundPolicyCount"], 1)
        self.assertIn("v3-default", payload["policyKernelBinding"]["casePolicyVersionCounts"])
        courtroom_item = payload["courtroomReadModel"]["items"][0]
        self.assertIn("workflowStatus", courtroom_item)
        self.assertIn("callbackStatus", courtroom_item)
        self.assertIn("needsDrawVote", courtroom_item)
        self.assertIn("blocked", courtroom_item)
        self.assertIn("lifecycleBucket", courtroom_item)
        self.assertIn("policyVersion", courtroom_item)
        self.assertIn("policyKernelVersion", courtroom_item)
        self.assertIn("policyKernelHash", courtroom_item)
        self.assertIn("policyGateDecision", courtroom_item)
        self.assertIn("policyGateSource", courtroom_item)
        self.assertIn("policyOverrideApplied", courtroom_item)
        self.assertEqual(courtroom_item["policyVersion"], "v3-default")
        self.assertEqual(payload["filters"]["dispatchType"], "final")
        self.assertEqual(payload["filters"]["policyVersion"], "v3-default")
        self.assertEqual(payload["filters"]["trustCaseLimit"], 3)
        self.assertEqual(payload["filters"]["calibrationRiskLimit"], 50)
        self.assertEqual(payload["filters"]["panelGroupLimit"], 50)

        pack_without_trust_resp = await self._get(
            app=app,
            path="/internal/judge/ops/read-model/pack?include_case_trust=false",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(pack_without_trust_resp.status_code, 200)
        without_trust_payload = pack_without_trust_resp.json()
        self.assertFalse(without_trust_payload["trustOverview"]["included"])
        self.assertEqual(without_trust_payload["trustOverview"]["count"], 0)
        self.assertEqual(without_trust_payload["trustOverview"]["errorCount"], 0)
        self.assertIn("adaptiveSummary", without_trust_payload)

    async def test_panel_runtime_profile_ops_view_should_support_filters_and_aggregations(
        self,
    ) -> None:
        async def noop_callback(
            *, cfg: object, case_id: int, payload: dict[str, Any]
        ) -> None:
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
        self.assertEqual(set(payload.keys()), set(PANEL_RUNTIME_PROFILE_TOP_LEVEL_KEYS))
        self.assertEqual(
            set(payload["aggregations"].keys()),
            set(PANEL_RUNTIME_PROFILE_AGGREGATIONS_KEYS),
        )
        self.assertEqual(set(payload["filters"].keys()), set(PANEL_RUNTIME_PROFILE_FILTER_KEYS))
        validate_panel_runtime_profile_contract(payload)
        self.assertGreaterEqual(payload["count"], 3)
        self.assertGreaterEqual(payload["returned"], 3)
        self.assertEqual(set(payload["items"][0].keys()), set(PANEL_RUNTIME_PROFILE_ITEM_KEYS))
        first_item = payload["items"][0]
        self.assertIsInstance(first_item["shadowEvaluation"], dict)
        self.assertIsInstance(first_item["shadowReleaseGateSignal"], dict)
        self.assertFalse(first_item["shadowEvaluation"]["officialWinnerMutationAllowed"])
        self.assertGreaterEqual(payload["aggregations"]["byJudgeId"]["judgeA"], 1)
        self.assertGreaterEqual(payload["aggregations"]["byJudgeId"]["judgeB"], 1)
        self.assertGreaterEqual(payload["aggregations"]["byJudgeId"]["judgeC"], 1)
        self.assertGreaterEqual(payload["aggregations"]["shadowEnabledCount"], 0)
        self.assertGreaterEqual(payload["aggregations"]["shadowAgreementCount"], 0)
        self.assertGreaterEqual(payload["aggregations"]["shadowDriftSignalCount"], 0)
        self.assertGreaterEqual(payload["aggregations"]["avgShadowDecisionAgreement"], 0.0)
        self.assertGreaterEqual(payload["aggregations"]["avgShadowCostEstimate"], 0.0)
        self.assertGreaterEqual(payload["aggregations"]["avgShadowLatencyEstimate"], 0.0)
        self.assertIn("byShadowModelStrategy", payload["aggregations"])
        self.assertGreaterEqual(
            payload["aggregations"]["byModelStrategy"]["deterministic_path_alignment"],
            1,
        )
        self.assertGreaterEqual(
            payload["aggregations"]["byStrategySlot"]["path_alignment"],
            1,
        )
        self.assertGreaterEqual(
            payload["aggregations"]["byDomainSlot"]["general"],
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

        strategy_slot_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/panels/runtime/profiles"
                "?dispatch_type=final&strategy_slot=path_alignment"
                "&domain_slot=general&sort_by=strategy_slot&sort_order=asc&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(strategy_slot_resp.status_code, 200)
        strategy_slot_payload = strategy_slot_resp.json()
        self.assertGreaterEqual(strategy_slot_payload["count"], 1)
        self.assertEqual(strategy_slot_payload["filters"]["strategySlot"], "path_alignment")
        self.assertEqual(strategy_slot_payload["filters"]["domainSlot"], "general")
        self.assertEqual(strategy_slot_payload["filters"]["sortBy"], "strategy_slot")
        self.assertTrue(
            all(
                row["strategySlot"] == "path_alignment"
                and row["domainSlot"] == "general"
                for row in strategy_slot_payload["items"]
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

    async def test_panel_runtime_profile_ops_view_should_return_500_when_contract_validation_fails(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)

        with patch(
            "app.applications.bootstrap_ops_panel_replay_payload_helpers."
            "validate_panel_runtime_profile_contract_v3",
            side_effect=ValueError("panel_runtime_profile_missing_keys:items"),
        ):
            resp = await self._get(
                app=app,
                path="/internal/judge/panels/runtime/profiles?dispatch_type=final",
                internal_key=runtime.settings.ai_internal_key,
            )

        self.assertEqual(resp.status_code, 500)
        detail = resp.json()["detail"]
        self.assertEqual(detail["code"], "panel_runtime_profile_contract_violation")
        self.assertIn("panel_runtime_profile_missing_keys:items", detail["message"])

    async def test_panel_runtime_readiness_route_should_return_groups_and_simulations(
        self,
    ) -> None:
        async def noop_callback(
            *, cfg: object, case_id: int, payload: dict[str, Any]
        ) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)
        case_id = _unique_case_id(7871)

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

        readiness_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/panels/runtime/readiness"
                "?dispatch_type=final&policy_version=v3-default"
                "&profile_scan_limit=200&group_limit=20&attention_limit=10"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(readiness_resp.status_code, 200)
        payload = readiness_resp.json()

        self.assertIsInstance(payload["overview"], dict)
        self.assertIsInstance(payload["groups"], list)
        self.assertIsInstance(payload["attentionGroups"], list)
        self.assertGreaterEqual(payload["overview"]["totalMatched"], 3)
        self.assertGreaterEqual(payload["overview"]["scannedRecords"], 3)
        self.assertGreaterEqual(payload["overview"]["totalGroups"], 1)
        self.assertIn("readinessCounts", payload["overview"])
        self.assertIn("shadow", payload["overview"])
        self.assertFalse(payload["overview"]["shadow"]["officialWinnerMutationAllowed"])
        self.assertTrue(any(int(row.get("caseCount") or 0) >= 1 for row in payload["groups"]))

        first_group = payload["groups"][0]
        self.assertIn("recommendedSwitchConditions", first_group)
        self.assertIn("simulations", first_group)
        self.assertIn("shadowReleaseGateSignals", first_group)
        self.assertIn("avgShadowDecisionAgreement", first_group)
        self.assertIn("avgShadowCostEstimate", first_group)
        self.assertIn("avgShadowLatencyEstimate", first_group)
        self.assertIsInstance(first_group["shadowReleaseGateSignals"], list)
        self.assertIsInstance(first_group["recommendedSwitchConditions"], list)
        self.assertIsInstance(first_group["simulations"], list)
        self.assertTrue(
            all(
                bool(sim.get("advisoryOnly"))
                for sim in first_group["simulations"]
                if isinstance(sim, dict)
            )
        )
        self.assertTrue(
            any(
                "advisory-only" in str(note).lower()
                for note in payload["notes"]
            )
        )
        self.assertEqual(payload["filters"]["dispatchType"], "final")
        self.assertEqual(payload["filters"]["policyVersion"], "v3-default")
        self.assertEqual(payload["filters"]["profileScanLimit"], 200)
        self.assertEqual(payload["filters"]["groupLimit"], 20)
        self.assertEqual(payload["filters"]["attentionLimit"], 10)


if __name__ == "__main__":
    unittest.main()
