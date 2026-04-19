from __future__ import annotations

import unittest

from app.applications.ops_read_model_pack import (
    OPS_READ_MODEL_PACK_V5_ADAPTIVE_SUMMARY_KEYS,
    OPS_READ_MODEL_PACK_V5_FILTER_KEYS,
    OPS_READ_MODEL_PACK_V5_TOP_LEVEL_KEYS,
    OPS_READ_MODEL_PACK_V5_TRUST_OVERVIEW_KEYS,
    build_ops_read_model_pack_adaptive_summary,
    build_ops_read_model_pack_filters,
    build_ops_read_model_pack_trust_overview,
    build_ops_read_model_pack_v5_payload,
    summarize_ops_read_model_pack_review_items,
    summarize_ops_read_model_pack_trust_items,
    validate_ops_read_model_pack_v5_contract,
)


class OpsReadModelPackTests(unittest.TestCase):
    def _build_pack_payload(
        self,
        *,
        adaptive_summary: dict | None = None,
        trust_overview: dict | None = None,
        filters: dict | None = None,
    ) -> dict:
        return {
            "generatedAt": "2026-04-19T00:00:00Z",
            "fairnessDashboard": {},
            "fairnessCalibrationAdvisor": {},
            "panelRuntimeReadiness": {},
            "registryGovernance": {},
            "registryPromptToolGovernance": {},
            "courtroomReadModel": {
                "requestedCaseLimit": 10,
                "caseIds": [],
                "count": 0,
                "errorCount": 0,
                "items": [],
                "errors": [],
            },
            "courtroomQueue": {},
            "courtroomDrilldown": {"aggregations": {}},
            "reviewQueue": {},
            "reviewTrustPriority": {},
            "evidenceClaimQueue": {"aggregations": {}},
            "trustChallengeQueue": {"aggregations": {}},
            "policyGateSimulation": {},
            "adaptiveSummary": adaptive_summary or {
                "calibrationGatePassed": True,
                "calibrationGateCode": "ok",
                "calibrationHighRiskCount": 0,
                "recommendedActionCount": 0,
                "registryPromptToolRiskCount": 0,
                "registryPromptToolHighRiskCount": 0,
                "panelReadyGroupCount": 0,
                "panelWatchGroupCount": 0,
                "panelAttentionGroupCount": 0,
                "panelScannedRecordCount": 0,
                "reviewQueueCount": 0,
                "reviewHighRiskCount": 0,
                "reviewUrgentCount": 0,
                "reviewTrustPriorityCount": 0,
                "reviewUnifiedHighPriorityCount": 0,
                "reviewTrustOpenChallengeCount": 0,
                "policySimulationBlockedCount": 0,
                "courtroomSampleCount": 0,
                "courtroomQueueCount": 0,
                "courtroomDrilldownCount": 0,
                "courtroomDrilldownReviewRequiredCount": 0,
                "courtroomDrilldownHighRiskCount": 0,
                "evidenceClaimQueueCount": 0,
                "evidenceClaimHighRiskCount": 0,
                "evidenceClaimConflictCaseCount": 0,
                "evidenceClaimUnansweredClaimCaseCount": 0,
                "trustChallengeQueueCount": 0,
                "trustChallengeHighPriorityCount": 0,
                "trustChallengeUrgentCount": 0,
            },
            "trustOverview": trust_overview or {
                "included": True,
                "requestedCaseLimit": 1,
                "caseIds": [],
                "count": 0,
                "verifiedCount": 0,
                "reviewRequiredCount": 0,
                "openChallengeCount": 0,
                "errorCount": 0,
                "items": [],
                "errors": [],
            },
            "filters": filters or {
                "dispatchType": "final",
                "policyVersion": "v3-default",
                "windowDays": 7,
                "topLimit": 10,
                "caseScanLimit": 200,
                "includeCaseTrust": True,
                "trustCaseLimit": 5,
                "dependencyLimit": 200,
                "usagePreviewLimit": 20,
                "releaseLimit": 50,
                "auditLimit": 100,
                "calibrationRiskLimit": 50,
                "calibrationBenchmarkLimit": 200,
                "calibrationShadowLimit": 200,
                "panelProfileScanLimit": 600,
                "panelGroupLimit": 50,
                "panelAttentionLimit": 20,
            },
        }

    def test_build_ops_read_model_pack_adaptive_summary_should_normalize_counts(self) -> None:
        payload = build_ops_read_model_pack_adaptive_summary(
            release_gate={"passed": True, "code": "ok"},
            advisor_overview={"highRiskCount": "3"},
            recommended_action_count=-5,
            readiness_counts={"ready": "2", "watch": None, "attention": "1"},
            readiness_overview={"scannedRecords": "12"},
            review_queue_count="8",
            review_high_risk_count=2,
            review_urgent_count=1,
            review_trust_priority_count=5,
            review_unified_high_priority_count=4,
            review_trust_open_challenge_count=3,
            policy_simulation_blocked_count=2,
            courtroom_sample_count=6,
            courtroom_queue_count=7,
            courtroom_drilldown_count=5,
            courtroom_drilldown_review_required_count=4,
            courtroom_drilldown_high_risk_count=2,
            evidence_claim_queue_count=9,
            evidence_claim_high_risk_count=3,
            evidence_claim_conflict_case_count=2,
            evidence_claim_unanswered_claim_case_count=1,
            trust_challenge_queue_count=4,
            trust_challenge_high_priority_count=2,
            trust_challenge_urgent_count=1,
            registry_prompt_tool_risk_count=7,
            registry_prompt_tool_high_risk_count=3,
        )
        self.assertEqual(
            set(payload.keys()),
            set(OPS_READ_MODEL_PACK_V5_ADAPTIVE_SUMMARY_KEYS),
        )
        self.assertTrue(payload["calibrationGatePassed"])
        self.assertEqual(payload["calibrationGateCode"], "ok")
        self.assertEqual(payload["calibrationHighRiskCount"], 3)
        self.assertEqual(payload["recommendedActionCount"], 0)
        self.assertEqual(payload["panelReadyGroupCount"], 2)
        self.assertEqual(payload["panelWatchGroupCount"], 0)
        self.assertEqual(payload["panelAttentionGroupCount"], 1)
        self.assertEqual(payload["evidenceClaimQueueCount"], 9)
        self.assertEqual(payload["registryPromptToolHighRiskCount"], 3)

    def test_build_ops_read_model_pack_trust_overview_should_keep_case_lists(self) -> None:
        payload = build_ops_read_model_pack_trust_overview(
            include_case_trust=False,
            trust_case_limit=0,
            trust_case_ids=[101, 102],
            trust_items=[{"caseId": 101}],
            trust_errors=[{"caseId": 102, "errorCode": "verify_failed"}],
            verified_count=-1,
            review_required_count=2,
            open_challenge_count=3,
        )
        self.assertEqual(
            set(payload.keys()),
            set(OPS_READ_MODEL_PACK_V5_TRUST_OVERVIEW_KEYS),
        )
        self.assertFalse(payload["included"])
        self.assertEqual(payload["requestedCaseLimit"], 1)
        self.assertEqual(payload["caseIds"], [101, 102])
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["errorCount"], 1)
        self.assertEqual(payload["verifiedCount"], 0)
        self.assertEqual(payload["reviewRequiredCount"], 2)
        self.assertEqual(payload["openChallengeCount"], 3)

    def test_build_ops_read_model_pack_filters_should_clamp_limits(self) -> None:
        payload = build_ops_read_model_pack_filters(
            dispatch_type="FINAL",
            policy_version="v3-default",
            window_days=7,
            top_limit=10,
            case_scan_limit=200,
            include_case_trust=True,
            trust_case_limit=5,
            dependency_limit=-1,
            usage_preview_limit=9999,
            release_limit=500,
            audit_limit=-2,
            calibration_risk_limit=0,
            calibration_benchmark_limit=9999,
            calibration_shadow_limit=-1,
            panel_profile_scan_limit=1,
            panel_group_limit=9999,
            panel_attention_limit=0,
        )
        self.assertEqual(
            set(payload.keys()),
            set(OPS_READ_MODEL_PACK_V5_FILTER_KEYS),
        )
        self.assertEqual(payload["dispatchType"], "final")
        self.assertEqual(payload["policyVersion"], "v3-default")
        self.assertEqual(payload["dependencyLimit"], 1)
        self.assertEqual(payload["usagePreviewLimit"], 200)
        self.assertEqual(payload["releaseLimit"], 200)
        self.assertEqual(payload["auditLimit"], 1)
        self.assertEqual(payload["calibrationRiskLimit"], 1)
        self.assertEqual(payload["calibrationBenchmarkLimit"], 500)
        self.assertEqual(payload["calibrationShadowLimit"], 1)
        self.assertEqual(payload["panelProfileScanLimit"], 50)
        self.assertEqual(payload["panelGroupLimit"], 200)
        self.assertEqual(payload["panelAttentionLimit"], 1)

    def test_validate_ops_read_model_pack_v5_contract_should_pass_for_stable_payload(self) -> None:
        payload = self._build_pack_payload()
        self.assertEqual(set(payload.keys()), set(OPS_READ_MODEL_PACK_V5_TOP_LEVEL_KEYS))
        validate_ops_read_model_pack_v5_contract(payload)

    def test_validate_ops_read_model_pack_v5_contract_should_fail_on_missing_keys(self) -> None:
        payload = self._build_pack_payload()
        payload["adaptiveSummary"].pop("reviewQueueCount")

        with self.assertRaises(ValueError) as ctx:
            validate_ops_read_model_pack_v5_contract(payload)
        self.assertIn("adaptiveSummary_missing_keys", str(ctx.exception))

    def test_validate_ops_read_model_pack_v5_contract_should_fail_on_counter_mismatch(self) -> None:
        payload = self._build_pack_payload(
            trust_overview={
                "included": True,
                "requestedCaseLimit": 1,
                "caseIds": [101],
                "count": 1,
                "verifiedCount": 2,
                "reviewRequiredCount": 0,
                "openChallengeCount": 0,
                "errorCount": 0,
                "items": [{"caseId": 101}],
                "errors": [],
            }
        )

        with self.assertRaises(ValueError) as ctx:
            validate_ops_read_model_pack_v5_contract(payload)
        self.assertIn("verifiedCount_exceeds_count", str(ctx.exception))

    def test_validate_ops_read_model_pack_v5_contract_should_fail_on_courtroom_count_mismatch(self) -> None:
        payload = self._build_pack_payload()
        payload["courtroomReadModel"]["count"] = 1

        with self.assertRaises(ValueError) as ctx:
            validate_ops_read_model_pack_v5_contract(payload)
        self.assertIn("courtroomReadModel_count_mismatch", str(ctx.exception))

    def test_validate_ops_read_model_pack_v5_contract_should_fail_on_courtroom_item_shape(self) -> None:
        payload = self._build_pack_payload()
        payload["courtroomReadModel"]["items"] = [{"caseId": 101}]
        payload["courtroomReadModel"]["count"] = 1

        with self.assertRaises(ValueError) as ctx:
            validate_ops_read_model_pack_v5_contract(payload)
        self.assertIn("courtroomReadModel_item_missing_keys", str(ctx.exception))

    def test_build_ops_read_model_pack_v5_payload_should_return_contract_stable_payload(self) -> None:
        seed = self._build_pack_payload()
        payload = build_ops_read_model_pack_v5_payload(
            generated_at=seed["generatedAt"],
            fairness_dashboard=seed["fairnessDashboard"],
            fairness_calibration_advisor=seed["fairnessCalibrationAdvisor"],
            panel_runtime_readiness=seed["panelRuntimeReadiness"],
            registry_governance=seed["registryGovernance"],
            registry_prompt_tool_governance=seed["registryPromptToolGovernance"],
            courtroom_case_ids=[],
            courtroom_requested_case_limit=10,
            courtroom_items=[],
            courtroom_errors=[],
            courtroom_queue=seed["courtroomQueue"],
            courtroom_drilldown=seed["courtroomDrilldown"],
            review_queue=seed["reviewQueue"],
            review_trust_priority=seed["reviewTrustPriority"],
            evidence_claim_queue=seed["evidenceClaimQueue"],
            trust_challenge_queue=seed["trustChallengeQueue"],
            policy_gate_simulation=seed["policyGateSimulation"],
            adaptive_summary=seed["adaptiveSummary"],
            trust_overview=seed["trustOverview"],
            pack_filters=seed["filters"],
        )
        self.assertEqual(set(payload.keys()), set(OPS_READ_MODEL_PACK_V5_TOP_LEVEL_KEYS))
        self.assertEqual(payload["courtroomReadModel"]["requestedCaseLimit"], 10)

    def test_summarize_ops_read_model_pack_trust_items_should_count_flags(self) -> None:
        summary = summarize_ops_read_model_pack_trust_items(
            trust_items=[
                {"verdictVerified": True, "reviewRequired": True, "challengeState": "requested"},
                {"verdictVerified": False, "reviewRequired": False, "challengeState": "closed"},
                {"verdictVerified": True, "reviewRequired": False, "challengeState": "UNDER_REVIEW"},
            ],
            open_challenge_states={"requested", "under_review"},
        )
        self.assertEqual(summary["verifiedCount"], 2)
        self.assertEqual(summary["reviewRequiredCount"], 1)
        self.assertEqual(summary["openChallengeCount"], 2)

    def test_summarize_ops_read_model_pack_review_items_should_count_risk_and_priority(self) -> None:
        summary = summarize_ops_read_model_pack_review_items(
            review_items=[
                {"riskProfile": {"level": "high", "slaBucket": "urgent"}},
                {"riskProfile": {"level": "low", "slaBucket": "normal"}},
            ],
            review_trust_priority_items=[
                {
                    "unifiedPriorityProfile": {"level": "high"},
                    "trustChallenge": {"state": "requested"},
                },
                {
                    "unifiedPriorityProfile": {"level": "medium"},
                    "trustChallenge": {"state": "closed"},
                },
            ],
            trust_challenge_queue_items=[
                {"priorityProfile": {"level": "high", "slaBucket": "urgent"}},
                {"priorityProfile": {"level": "low", "slaBucket": "normal"}},
            ],
            open_challenge_states={"requested", "under_review"},
        )
        self.assertEqual(summary["reviewHighRiskCount"], 1)
        self.assertEqual(summary["reviewUrgentCount"], 1)
        self.assertEqual(summary["reviewUnifiedHighPriorityCount"], 1)
        self.assertEqual(summary["reviewTrustOpenChallengeCount"], 1)
        self.assertEqual(summary["trustChallengeHighPriorityCount"], 1)
        self.assertEqual(summary["trustChallengeUrgentCount"], 1)


if __name__ == "__main__":
    unittest.main()
