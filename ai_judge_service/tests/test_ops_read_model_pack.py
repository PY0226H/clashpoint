from __future__ import annotations

import unittest

from app.applications.ops_read_model_pack import (
    OPS_READ_MODEL_PACK_V5_ADAPTIVE_SUMMARY_KEYS,
    OPS_READ_MODEL_PACK_V5_ARTIFACT_COVERAGE_KEYS,
    OPS_READ_MODEL_PACK_V5_AUDIT_ANCHOR_STATUS_KEYS,
    OPS_READ_MODEL_PACK_V5_CASE_CHAIN_COVERAGE_KEYS,
    OPS_READ_MODEL_PACK_V5_CASE_LIFECYCLE_OVERVIEW_KEYS,
    OPS_READ_MODEL_PACK_V5_CHALLENGE_REVIEW_STATE_KEYS,
    OPS_READ_MODEL_PACK_V5_FAIRNESS_GATE_OVERVIEW_KEYS,
    OPS_READ_MODEL_PACK_V5_FILTER_KEYS,
    OPS_READ_MODEL_PACK_V5_JUDGE_WORKFLOW_COVERAGE_KEYS,
    OPS_READ_MODEL_PACK_V5_POLICY_KERNEL_BINDING_KEYS,
    OPS_READ_MODEL_PACK_V5_PUBLIC_VERIFY_STATUS_KEYS,
    OPS_READ_MODEL_PACK_V5_READ_CONTRACT_KEYS,
    OPS_READ_MODEL_PACK_V5_TOP_LEVEL_KEYS,
    OPS_READ_MODEL_PACK_V5_TRUST_COVERAGE_KEYS,
    OPS_READ_MODEL_PACK_V5_TRUST_MONITORING_KEYS,
    OPS_READ_MODEL_PACK_V5_TRUST_OVERVIEW_KEYS,
    build_ops_read_model_pack_adaptive_summary,
    build_ops_read_model_pack_case_chain_coverage,
    build_ops_read_model_pack_case_lifecycle_overview,
    build_ops_read_model_pack_fairness_gate_overview,
    build_ops_read_model_pack_filters,
    build_ops_read_model_pack_judge_workflow_coverage,
    build_ops_read_model_pack_policy_kernel_binding,
    build_ops_read_model_pack_read_contract,
    build_ops_read_model_pack_trust_overview,
    build_ops_read_model_pack_v5_payload,
    summarize_ops_read_model_pack_review_items,
    validate_ops_read_model_pack_v5_contract,
)
from app.applications.ops_read_model_trust_projection import (
    build_ops_read_model_pack_policy_gate_rows,
    build_ops_read_model_pack_trust_artifact_coverage,
    build_ops_read_model_pack_trust_item_from_public_verify_payload,
    summarize_ops_read_model_pack_trust_items,
)
from app.applications.ops_trust_monitoring import (
    OPS_TRUST_MONITORING_KEYS,
    build_ops_trust_monitoring_summary,
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
            "trustCoverage": {
                "sampledCaseCount": 0,
                "completeCount": 0,
                "partialCount": 0,
                "missingCount": 0,
                "completeRate": 0.0,
                "byComponent": {
                    "caseCommitment": 0,
                    "verdictAttestation": 0,
                    "challengeReview": 0,
                    "kernelVersion": 0,
                    "auditAnchor": 0,
                },
                "sourceCounts": {},
            },
            "publicVerifyStatus": {
                "sampledCaseCount": 0,
                "verifiedCount": 0,
                "failedCount": 0,
                "pendingCount": 0,
                "errorCount": 0,
                "reasonCounts": {},
            },
            "challengeReviewState": {
                "sampledCaseCount": 0,
                "reviewRequiredCount": 0,
                "openChallengeCount": 0,
                "totalChallengeCount": 0,
                "challengeStateCounts": {},
                "reviewStateCounts": {},
            },
            "auditAnchorStatus": {
                "sampledCaseCount": 0,
                "readyCount": 0,
                "pendingCount": 0,
                "missingCount": 0,
                "anchorHashPresentCount": 0,
                "artifactManifestHashPresentCount": 0,
                "statusCounts": {},
            },
            "artifactCoverage": {
                "sampledCaseCount": 0,
                "readyCount": 0,
                "pendingCount": 0,
                "missingCount": 0,
                "manifestHashPresentCount": 0,
                "artifactRefCount": 0,
                "artifactKindCounts": {},
            },
            "trustMonitoring": {
                "monitoringVersion": "ops-trust-monitoring-v1",
                "overallStatus": "ready",
                "sampledCaseCount": 0,
                "artifactStoreReadiness": {},
                "publicVerificationReadiness": {},
                "challengeReviewLag": {},
                "registryReleaseReadiness": {},
                "citationVerifierEvidence": {
                    "status": "not_sampled",
                    "statusCounts": {},
                    "reasonCodes": [],
                    "missingCitationCount": 0,
                    "weakCitationCount": 0,
                    "forbiddenSourceCount": 0,
                },
                "panelShadowDrift": {},
                "realEnvEvidenceStatus": {},
                "blockerCounts": {
                    "production": 0,
                    "review": 0,
                    "release": 0,
                    "evidence": 0,
                },
                "blockers": [],
                "redactionContract": {
                    "artifactRefsVisible": False,
                    "hashesOnly": True,
                    "internalAuditPayloadVisible": False,
                    "rawPromptVisible": False,
                    "rawTraceVisible": False,
                    "publicPayloadFields": [],
                },
            },
            "judgeWorkflowCoverage": {
                "totalCases": 0,
                "fullCount": 0,
                "partialCount": 0,
                "missingCount": 0,
                "invalidOrderCount": 0,
                "missingRoleCounts": {
                    "clerk": 0,
                    "recorder": 0,
                    "claim_graph": 0,
                    "evidence": 0,
                    "panel": 0,
                    "fairness_sentinel": 0,
                    "chief_arbiter": 0,
                    "opinion_writer": 0,
                },
                "fullCoverageRate": 0.0,
            },
            "caseLifecycleOverview": {
                "totalCases": 0,
                "workflowStatusCounts": {},
                "lifecycleBucketCounts": {},
                "reviewRequiredCount": 0,
                "drawPendingCount": 0,
                "blockedCount": 0,
                "callbackFailedCount": 0,
            },
            "caseChainCoverage": {
                "totalCases": 0,
                "completeCount": 0,
                "missingAnyCount": 0,
                "fullCoverageRate": 0.0,
                "missingAnyRate": 0.0,
                "byObjectPresence": {
                    "caseDossier": 0,
                    "claimGraph": 0,
                    "evidenceBundle": 0,
                    "verdictLedger": 0,
                    "fairnessReport": 0,
                    "opinionPack": 0,
                },
            },
            "fairnessGateOverview": {
                "totalCases": 0,
                "caseDecisionCounts": {
                    "pass_through": 0,
                    "blocked_to_draw": 0,
                    "unknown": 0,
                },
                "caseReviewRequiredCount": 0,
                "policyVersionCount": 0,
                "policyGateDecisionCounts": {
                    "blocked": 0,
                    "override_activated": 0,
                    "pass": 0,
                },
                "policyGateSourceCounts": {},
                "policyOverrideAppliedCount": 0,
            },
            "policyKernelBinding": {
                "activePolicyVersion": "v3-default",
                "trackedPolicyVersionCount": 1,
                "kernelBoundPolicyCount": 1,
                "missingKernelBindingCount": 0,
                "casePolicyVersionCount": 0,
                "missingCasePolicyVersionCount": 0,
                "caseMissingKernelBindingCount": 0,
                "overrideAppliedPolicyCount": 0,
                "casePolicyVersionCounts": {},
                "gateDecisionCounts": {
                    "blocked": 0,
                    "override_activated": 0,
                    "pass": 0,
                },
            },
            "readContract": {
                "contractVersion": "ops_read_model_pack_v5",
                "businessRoutes": [
                    "/internal/judge/cases/{case_id}",
                    "/internal/judge/cases/{case_id}/courtroom-read-model",
                ],
                "opsRoutes": [
                    "/internal/judge/ops/read-model/pack",
                    "/internal/judge/review/cases",
                ],
                "policyRoutes": [
                    "/internal/judge/registries/governance/overview",
                    "/internal/judge/registries/policy/gate-simulation",
                ],
                "fieldLayers": {
                    "userVisible": ["winner", "needsDrawVote", "reviewRequired"],
                    "opsVisible": ["workflowStatus", "caseLifecycleOverview"],
                    "internalAudit": ["traceId", "judgeCore"],
                },
                "errorSemantics": {
                    "structuredErrorCodeRequired": True,
                    "rawStringFallbackAllowed": False,
                },
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

    def test_build_ops_read_model_pack_trust_artifact_coverage_should_count_statuses(
        self,
    ) -> None:
        sections = build_ops_read_model_pack_trust_artifact_coverage(
            trust_items=[
                {
                    "trustArtifactSummary": {
                        "source": "trust_registry",
                        "trustCompleteness": {
                            "caseCommitment": True,
                            "verdictAttestation": True,
                            "challengeReview": True,
                            "kernelVersion": True,
                            "auditAnchor": True,
                            "complete": True,
                        },
                        "publicVerifyStatus": {"verified": True, "reason": "ok"},
                        "challengeReview": {
                            "reviewRequired": True,
                            "challengeState": "under_internal_review",
                            "reviewState": "pending_review",
                            "totalChallenges": 2,
                        },
                        "auditAnchor": {
                            "anchorStatus": "artifact_ready",
                            "anchorHashPresent": True,
                            "artifactManifestHashPresent": True,
                        },
                        "artifactCoverage": {
                            "ready": True,
                            "artifactRefCount": 5,
                            "artifactKindCounts": {"audit_pack": 1},
                        },
                    }
                },
                {
                    "trustArtifactSummary": {
                        "source": "report_payload",
                        "trustCompleteness": {
                            "caseCommitment": True,
                            "verdictAttestation": False,
                            "challengeReview": False,
                            "kernelVersion": False,
                            "auditAnchor": False,
                            "complete": False,
                        },
                        "publicVerifyStatus": {
                            "verified": False,
                            "reason": "registry_snapshot_missing",
                        },
                        "challengeReview": {
                            "reviewRequired": False,
                            "challengeState": None,
                            "reviewState": "not_required",
                            "totalChallenges": 0,
                        },
                        "auditAnchor": {
                            "anchorStatus": "missing",
                            "anchorHashPresent": False,
                            "artifactManifestHashPresent": False,
                        },
                        "artifactCoverage": {
                            "ready": False,
                            "artifactRefCount": 0,
                            "artifactKindCounts": {},
                        },
                    }
                },
            ],
            trust_errors=[{"caseId": 103, "errorCode": "verify_failed"}],
            open_challenge_states={"under_internal_review"},
        )
        self.assertEqual(
            set(sections["trustCoverage"].keys()),
            set(OPS_READ_MODEL_PACK_V5_TRUST_COVERAGE_KEYS),
        )
        self.assertEqual(
            set(sections["publicVerifyStatus"].keys()),
            set(OPS_READ_MODEL_PACK_V5_PUBLIC_VERIFY_STATUS_KEYS),
        )
        self.assertEqual(
            set(sections["challengeReviewState"].keys()),
            set(OPS_READ_MODEL_PACK_V5_CHALLENGE_REVIEW_STATE_KEYS),
        )
        self.assertEqual(
            set(sections["auditAnchorStatus"].keys()),
            set(OPS_READ_MODEL_PACK_V5_AUDIT_ANCHOR_STATUS_KEYS),
        )
        self.assertEqual(
            set(sections["artifactCoverage"].keys()),
            set(OPS_READ_MODEL_PACK_V5_ARTIFACT_COVERAGE_KEYS),
        )
        self.assertEqual(sections["trustCoverage"]["sampledCaseCount"], 3)
        self.assertEqual(sections["trustCoverage"]["completeCount"], 1)
        self.assertEqual(sections["trustCoverage"]["partialCount"], 1)
        self.assertEqual(sections["trustCoverage"]["missingCount"], 1)
        self.assertEqual(sections["publicVerifyStatus"]["verifiedCount"], 1)
        self.assertEqual(sections["publicVerifyStatus"]["pendingCount"], 1)
        self.assertEqual(sections["publicVerifyStatus"]["errorCount"], 1)
        self.assertEqual(sections["challengeReviewState"]["openChallengeCount"], 1)
        self.assertEqual(sections["auditAnchorStatus"]["readyCount"], 1)
        self.assertEqual(sections["artifactCoverage"]["artifactRefCount"], 5)

    def test_build_ops_read_model_pack_judge_workflow_coverage_should_count_full_partial_missing(
        self,
    ) -> None:
        payload = build_ops_read_model_pack_judge_workflow_coverage(
            role_nodes_rows=[
                [
                    {"seq": 1, "role": "clerk"},
                    {"seq": 2, "role": "recorder"},
                    {"seq": 3, "role": "claim_graph"},
                    {"seq": 4, "role": "evidence"},
                    {"seq": 5, "role": "panel"},
                    {"seq": 6, "role": "fairness_sentinel"},
                    {"seq": 7, "role": "chief_arbiter"},
                    {"seq": 8, "role": "opinion_writer"},
                ],
                [
                    {"seq": 1, "role": "clerk"},
                    {"seq": 2, "role": "recorder"},
                ],
                None,
            ],
            expected_role_order=(
                "clerk",
                "recorder",
                "claim_graph",
                "evidence",
                "panel",
                "fairness_sentinel",
                "chief_arbiter",
                "opinion_writer",
            ),
        )
        self.assertEqual(
            set(payload.keys()),
            set(OPS_READ_MODEL_PACK_V5_JUDGE_WORKFLOW_COVERAGE_KEYS),
        )
        self.assertEqual(payload["totalCases"], 3)
        self.assertEqual(payload["fullCount"], 1)
        self.assertEqual(payload["partialCount"], 1)
        self.assertEqual(payload["missingCount"], 1)
        self.assertGreaterEqual(payload["missingRoleCounts"]["panel"], 2)
        self.assertAlmostEqual(payload["fullCoverageRate"], 0.3333, places=4)

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

    def test_build_ops_read_model_pack_case_chain_coverage_should_count_object_presence(self) -> None:
        payload = build_ops_read_model_pack_case_chain_coverage(
            chain_rows=[
                {
                    "caseDossier": True,
                    "claimGraph": True,
                    "evidenceBundle": True,
                    "verdictLedger": True,
                    "fairnessReport": True,
                    "opinionPack": True,
                },
                {
                    "caseDossier": True,
                    "claimGraph": False,
                    "evidenceBundle": True,
                    "verdictLedger": False,
                    "fairnessReport": True,
                    "opinionPack": False,
                },
            ]
        )
        self.assertEqual(
            set(payload.keys()),
            set(OPS_READ_MODEL_PACK_V5_CASE_CHAIN_COVERAGE_KEYS),
        )
        self.assertEqual(payload["totalCases"], 2)
        self.assertEqual(payload["completeCount"], 1)
        self.assertEqual(payload["missingAnyCount"], 1)
        self.assertEqual(payload["byObjectPresence"]["claimGraph"], 1)

    def test_build_ops_read_model_pack_case_lifecycle_overview_should_count_states(
        self,
    ) -> None:
        payload = build_ops_read_model_pack_case_lifecycle_overview(
            courtroom_items=[
                {
                    "workflowStatus": "callback_reported",
                    "callbackStatus": "reported",
                    "reviewRequired": False,
                    "needsDrawVote": False,
                    "blocked": False,
                    "lifecycleBucket": "reported",
                },
                {
                    "workflowStatus": "review_required",
                    "callbackStatus": "blocked_failed_reported",
                    "reviewRequired": True,
                    "needsDrawVote": True,
                    "blocked": True,
                    "lifecycleBucket": "blocked",
                },
            ]
        )
        self.assertEqual(
            set(payload.keys()),
            set(OPS_READ_MODEL_PACK_V5_CASE_LIFECYCLE_OVERVIEW_KEYS),
        )
        self.assertEqual(payload["totalCases"], 2)
        self.assertEqual(payload["workflowStatusCounts"]["callback_reported"], 1)
        self.assertEqual(payload["lifecycleBucketCounts"]["blocked"], 1)
        self.assertEqual(payload["reviewRequiredCount"], 1)
        self.assertEqual(payload["drawPendingCount"], 1)
        self.assertEqual(payload["blockedCount"], 1)
        self.assertEqual(payload["callbackFailedCount"], 1)

    def test_build_ops_read_model_pack_read_contract_should_layer_fields(self) -> None:
        payload = build_ops_read_model_pack_read_contract()
        self.assertEqual(
            set(payload.keys()),
            set(OPS_READ_MODEL_PACK_V5_READ_CONTRACT_KEYS),
        )
        self.assertIn("/internal/judge/ops/read-model/pack", payload["opsRoutes"])
        self.assertIn("/internal/judge/ops/runtime-readiness", payload["opsRoutes"])
        self.assertIn("winner", payload["fieldLayers"]["userVisible"])
        self.assertIn("caseLifecycleOverview", payload["fieldLayers"]["opsVisible"])
        self.assertIn("artifactCoverage", payload["fieldLayers"]["opsVisible"])
        self.assertIn("trustMonitoring", payload["fieldLayers"]["opsVisible"])
        self.assertIn("policyKernelHash", payload["fieldLayers"]["internalAudit"])
        self.assertIn("artifactManifestHash", payload["fieldLayers"]["internalAudit"])
        self.assertTrue(payload["errorSemantics"]["structuredErrorCodeRequired"])
        self.assertFalse(payload["errorSemantics"]["rawStringFallbackAllowed"])

    def test_build_ops_read_model_pack_fairness_gate_overview_should_summarize_case_and_policy(
        self,
    ) -> None:
        payload = build_ops_read_model_pack_fairness_gate_overview(
            courtroom_items=[
                {"gateDecision": "pass_through", "reviewRequired": False},
                {"gateDecision": "blocked_to_draw", "reviewRequired": True},
                {"gateDecision": "", "reviewRequired": False},
            ],
            policy_gate_rows=[
                {
                    "policyVersion": "v3-default",
                    "gateDecision": "blocked",
                    "gateSource": "benchmark",
                    "overrideApplied": False,
                },
                {
                    "policyVersion": "v3-exp",
                    "gateDecision": "pass",
                    "gateSource": "shadow",
                    "overrideApplied": True,
                },
            ],
        )
        self.assertEqual(
            set(payload.keys()),
            set(OPS_READ_MODEL_PACK_V5_FAIRNESS_GATE_OVERVIEW_KEYS),
        )
        self.assertEqual(payload["caseDecisionCounts"]["pass_through"], 1)
        self.assertEqual(payload["caseDecisionCounts"]["blocked_to_draw"], 1)
        self.assertEqual(payload["caseDecisionCounts"]["unknown"], 1)
        self.assertEqual(payload["policyVersionCount"], 2)
        self.assertEqual(payload["policyGateDecisionCounts"]["override_activated"], 1)
        self.assertEqual(payload["policyGateSourceCounts"]["benchmark"], 1)

    def test_build_ops_read_model_pack_policy_kernel_binding_should_summarize_binding_health(
        self,
    ) -> None:
        payload = build_ops_read_model_pack_policy_kernel_binding(
            active_policy_version="v3-default",
            governance_dependency_items=[
                {
                    "policyVersion": "v3-default",
                    "policyKernelVersion": "policy-kernel-binding-v1",
                    "policyKernelHash": "hash-1",
                },
                {
                    "policyVersion": "v3-exp",
                    "policyKernelVersion": None,
                    "policyKernelHash": None,
                },
            ],
            policy_gate_rows=[
                {
                    "policyVersion": "v3-default",
                    "gateDecision": "pass",
                    "gateSource": "benchmark",
                    "overrideApplied": False,
                },
                {
                    "policyVersion": "v3-exp",
                    "gateDecision": "blocked",
                    "gateSource": "shadow",
                    "overrideApplied": True,
                },
            ],
            courtroom_items=[
                {"policyVersion": "v3-default"},
                {"policyVersion": "v3-exp"},
                {"policyVersion": None},
            ],
        )
        self.assertEqual(
            set(payload.keys()),
            set(OPS_READ_MODEL_PACK_V5_POLICY_KERNEL_BINDING_KEYS),
        )
        self.assertEqual(payload["trackedPolicyVersionCount"], 2)
        self.assertEqual(payload["kernelBoundPolicyCount"], 1)
        self.assertEqual(payload["missingKernelBindingCount"], 1)
        self.assertEqual(payload["casePolicyVersionCount"], 2)
        self.assertEqual(payload["missingCasePolicyVersionCount"], 1)
        self.assertEqual(payload["caseMissingKernelBindingCount"], 1)
        self.assertEqual(payload["overrideAppliedPolicyCount"], 1)

    def test_validate_ops_read_model_pack_v5_contract_should_pass_for_stable_payload(self) -> None:
        payload = self._build_pack_payload()
        self.assertEqual(set(payload.keys()), set(OPS_READ_MODEL_PACK_V5_TOP_LEVEL_KEYS))
        self.assertEqual(
            set(payload["trustMonitoring"].keys()),
            set(OPS_READ_MODEL_PACK_V5_TRUST_MONITORING_KEYS),
        )
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
            trust_coverage=seed["trustCoverage"],
            public_verify_status=seed["publicVerifyStatus"],
            challenge_review_state=seed["challengeReviewState"],
            audit_anchor_status=seed["auditAnchorStatus"],
            artifact_coverage=seed["artifactCoverage"],
            trust_monitoring=seed["trustMonitoring"],
            judge_workflow_coverage=seed["judgeWorkflowCoverage"],
            case_lifecycle_overview=seed["caseLifecycleOverview"],
            case_chain_coverage=seed["caseChainCoverage"],
            fairness_gate_overview=seed["fairnessGateOverview"],
            policy_kernel_binding=seed["policyKernelBinding"],
            read_contract=seed["readContract"],
            pack_filters=seed["filters"],
        )
        self.assertEqual(set(payload.keys()), set(OPS_READ_MODEL_PACK_V5_TOP_LEVEL_KEYS))
        self.assertEqual(payload["courtroomReadModel"]["requestedCaseLimit"], 10)
        self.assertEqual(payload["trustMonitoring"]["overallStatus"], "ready")

    def test_build_ops_trust_monitoring_summary_should_bucket_p37_readiness(self) -> None:
        payload = build_ops_trust_monitoring_summary(
            trust_items=[
                {
                    "publicVerificationReadiness": {
                        "status": "artifact_manifest_pending",
                        "errorCode": "artifact_manifest_pending",
                        "externalizable": False,
                    }
                }
            ],
            trust_errors=[],
            artifact_coverage={
                "sampledCaseCount": 1,
                "readyCount": 0,
                "pendingCount": 1,
                "missingCount": 0,
                "manifestHashPresentCount": 1,
                "artifactRefCount": 0,
            },
            audit_anchor_status={
                "readyCount": 0,
                "pendingCount": 1,
                "missingCount": 0,
            },
            public_verify_status={
                "sampledCaseCount": 1,
                "verifiedCount": 1,
                "failedCount": 0,
                "pendingCount": 0,
                "errorCount": 0,
                "reasonCounts": {"ok": 1},
            },
            challenge_review_state={
                "sampledCaseCount": 1,
                "reviewRequiredCount": 1,
                "openChallengeCount": 1,
                "totalChallengeCount": 1,
                "challengeStateCounts": {"under_internal_review": 1},
                "reviewStateCounts": {"pending_review": 1},
            },
            trust_challenge_queue={
                "count": 1,
                "items": [
                    {
                        "priorityProfile": {
                            "level": "high",
                            "slaBucket": "urgent",
                        }
                    }
                ],
            },
            registry_prompt_tool_governance={
                "summary": {"riskTotalCount": 2, "riskHighCount": 1},
                "riskItems": [],
            },
            policy_gate_simulation={
                "summary": {"blockedCount": 1},
                "items": [
                    {
                        "policyVersion": "v3-default",
                        "releaseReadinessEvidence": {
                            "evidenceVersion": "policy-release-readiness-evidence-v1",
                            "policyVersion": "v3-default",
                            "decision": "env_blocked",
                            "decisionCode": "registry_release_gate_env_blocked",
                            "reasonCodes": [
                                (
                                    "registry_release_gate_fairness_benchmark_"
                                    "local_reference_only"
                                )
                            ],
                            "envBlockedComponents": ["fairnessBenchmark"],
                            "artifactRefs": ["release-manifest"],
                            "releaseReadinessArtifactSummary": {
                                "artifactRef": "release-readiness-artifact",
                                "manifestHash": "a" * 64,
                                "storageUri": "s3://hidden-bucket/path",
                            },
                            "publicVerificationReadiness": {"status": "ready"},
                            "citationVerification": {
                                "status": "warning",
                                "reasonCodes": [
                                    "citation_verifier_weak_citations",
                                ],
                                "missingCitationCount": 0,
                                "weakCitationCount": 2,
                                "forbiddenSourceCount": 0,
                            },
                            "realEnvEvidenceStatus": {"status": "env_blocked"},
                        },
                    }
                ],
            },
            fairness_calibration_advisor={
                "overview": {
                    "shadowRunCount": 0,
                    "shadowThresholdViolationCount": 0,
                    "driftBreachCount": 0,
                },
                "releaseGate": {
                    "shadowGateApplied": False,
                    "shadowGatePassed": None,
                    "latestRun": {
                        "runId": "local-reference",
                        "status": "passed",
                        "environmentMode": "local",
                    },
                    "latestShadowRun": None,
                },
            },
            policy_kernel_binding={
                "activePolicyVersion": "v3-default",
                "missingKernelBindingCount": 1,
                "overrideAppliedPolicyCount": 0,
                "gateDecisionCounts": {"blocked": 1},
            },
        )

        self.assertEqual(set(payload.keys()), set(OPS_TRUST_MONITORING_KEYS))
        self.assertEqual(payload["overallStatus"], "blocked")
        self.assertEqual(payload["artifactStoreReadiness"]["status"], "pending")
        self.assertEqual(payload["publicVerificationReadiness"]["status"], "blocked")
        self.assertEqual(payload["challengeReviewLag"]["status"], "blocked")
        self.assertEqual(payload["registryReleaseReadiness"]["status"], "blocked")
        self.assertEqual(
            payload["registryReleaseReadiness"]["releaseReadinessEvidenceCount"],
            1,
        )
        self.assertEqual(
            payload["registryReleaseReadiness"]["envBlockedComponents"],
            ["fairnessBenchmark"],
        )
        self.assertIn(
            "registry_release_gate_fairness_benchmark_local_reference_only",
            payload["registryReleaseReadiness"]["reasonCodes"],
        )
        self.assertEqual(payload["registryReleaseReadiness"]["artifactRefCount"], 1)
        self.assertEqual(
            payload["registryReleaseReadiness"]["releaseReadinessArtifactCount"],
            1,
        )
        self.assertEqual(
            payload["registryReleaseReadiness"]["releaseReadinessManifestHashCount"],
            1,
        )
        self.assertEqual(
            payload["registryReleaseReadiness"]["publicVerificationReadyCount"],
            1,
        )
        self.assertNotIn("hidden-bucket", str(payload["registryReleaseReadiness"]))
        self.assertEqual(
            payload["registryReleaseReadiness"]["realEnvEvidenceStatusCounts"],
            {"env_blocked": 1},
        )
        self.assertEqual(payload["citationVerifierEvidence"]["status"], "watch")
        self.assertEqual(payload["citationVerifierEvidence"]["weakCitationCount"], 2)
        self.assertIn(
            "citation_verifier_weak_citations",
            payload["citationVerifierEvidence"]["reasonCodes"],
        )
        self.assertEqual(payload["panelShadowDrift"]["status"], "missing")
        self.assertEqual(payload["realEnvEvidenceStatus"]["status"], "env_blocked")
        self.assertEqual(
            payload["realEnvEvidenceStatus"]["realSampleManifestStatus"],
            "env_blocked",
        )
        self.assertEqual(
            payload["realEnvEvidenceStatus"]["normalizedEvidence"][
                "benchmarkEvidenceStatus"
            ],
            "env_blocked",
        )
        self.assertFalse(
            payload["panelShadowDrift"]["normalizedEvidence"][
                "officialWinnerMutationAllowed"
            ]
        )
        self.assertFalse(payload["redactionContract"]["internalAuditPayloadVisible"])

    def test_summarize_ops_read_model_pack_trust_items_should_count_flags(self) -> None:
        summary = summarize_ops_read_model_pack_trust_items(
            trust_items=[
                {"verdictVerified": True, "reviewRequired": True, "challengeState": "requested"},
                {"verdictVerified": False, "reviewRequired": False, "challengeState": "closed"},
                {
                    "verdictVerified": True,
                    "reviewRequired": False,
                    "challengeState": "UNDER_INTERNAL_REVIEW",
                },
            ],
            open_challenge_states={"requested", "under_internal_review"},
        )
        self.assertEqual(summary["verifiedCount"], 2)
        self.assertEqual(summary["reviewRequiredCount"], 1)
        self.assertEqual(summary["openChallengeCount"], 2)

    def test_build_ops_read_model_pack_trust_item_should_project_public_verify_payload(
        self,
    ) -> None:
        item = build_ops_read_model_pack_trust_item_from_public_verify_payload(
            case_id=501,
            trust_payload={
                "caseId": 501,
                "dispatchType": "final",
                "traceId": "trace-trust-501",
                "verificationReadiness": {
                    "status": "ready",
                    "externalizable": True,
                },
                "verifyPayload": {
                    "caseCommitment": {"commitmentHash": "commit-hash"},
                    "verdictAttestation": {
                        "registryHash": "attestation-hash",
                        "verified": True,
                        "reason": "ok",
                    },
                    "challengeReview": {
                        "registryHash": "challenge-hash",
                        "reviewRequired": True,
                        "reviewState": "Pending_Review",
                        "challengeState": "UNDER_INTERNAL_REVIEW",
                        "totalChallenges": "2",
                    },
                    "kernelVersion": {
                        "registryHash": "kernel-hash",
                        "kernelHash": "kernel-hash",
                    },
                    "auditAnchor": {
                        "anchorHash": "anchor-hash",
                        "anchorStatus": "artifact_ready",
                        "componentHashes": {
                            "caseCommitmentHash": "commit-hash",
                            "verdictAttestationHash": "attestation-hash",
                            "challengeReviewHash": "challenge-hash",
                            "kernelVersionHash": "kernel-hash",
                            "artifactManifestHash": "manifest-hash",
                        },
                    },
                },
            },
        )

        self.assertEqual(item["caseId"], 501)
        self.assertEqual(item["dispatchType"], "final")
        self.assertEqual(item["traceId"], "trace-trust-501")
        self.assertTrue(item["verdictVerified"])
        self.assertEqual(item["verdictReason"], "ok")
        self.assertTrue(item["reviewRequired"])
        self.assertEqual(item["reviewState"], "pending_review")
        self.assertEqual(item["challengeState"], "under_internal_review")
        self.assertEqual(item["totalChallenges"], 2)
        self.assertEqual(item["publicVerificationReadiness"]["status"], "ready")
        self.assertTrue(item["trustArtifactSummary"]["trustCompleteness"]["complete"])
        self.assertFalse(
            item["trustArtifactSummary"]["artifactCoverage"].get("artifactRefs")
        )

    def test_build_ops_read_model_pack_policy_gate_rows_should_prefer_dependency_overview(
        self,
    ) -> None:
        rows = build_ops_read_model_pack_policy_gate_rows(
            dependency_overview_rows=[
                {
                    "policyVersion": "policy-v1",
                    "latestGateDecision": "pass",
                    "latestGateSource": "release_readiness",
                    "overrideApplied": False,
                }
            ],
            policy_gate_simulation={
                "items": [
                    {
                        "policyVersion": "policy-v2",
                        "simulatedGate": {"status": "blocked"},
                        "fairnessGate": {"source": "benchmark"},
                    }
                ]
            },
        )

        self.assertEqual(
            rows,
            [
                {
                    "policyVersion": "policy-v1",
                    "gateDecision": "pass",
                    "gateSource": "release_readiness",
                    "overrideApplied": False,
                }
            ],
        )

    def test_build_ops_read_model_pack_policy_gate_rows_should_fallback_to_simulation(
        self,
    ) -> None:
        rows = build_ops_read_model_pack_policy_gate_rows(
            dependency_overview_rows=[],
            policy_gate_simulation={
                "items": [
                    {
                        "policyVersion": "policy-v1",
                        "simulatedGate": {"status": "pass"},
                        "fairnessGate": {"source": "shadow"},
                    },
                    {
                        "policyVersion": "policy-v2",
                        "simulatedGate": {"status": "env_blocked"},
                        "fairnessGate": {"source": "benchmark"},
                    },
                ]
            },
        )

        self.assertEqual(
            rows,
            [
                {
                    "policyVersion": "policy-v1",
                    "gateDecision": "pass",
                    "gateSource": "shadow",
                    "overrideApplied": False,
                },
                {
                    "policyVersion": "policy-v2",
                    "gateDecision": "blocked",
                    "gateSource": "benchmark",
                    "overrideApplied": False,
                },
            ],
        )

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
            open_challenge_states={"requested", "under_internal_review"},
        )
        self.assertEqual(summary["reviewHighRiskCount"], 1)
        self.assertEqual(summary["reviewUrgentCount"], 1)
        self.assertEqual(summary["reviewUnifiedHighPriorityCount"], 1)
        self.assertEqual(summary["reviewTrustOpenChallengeCount"], 1)
        self.assertEqual(summary["trustChallengeHighPriorityCount"], 1)
        self.assertEqual(summary["trustChallengeUrgentCount"], 1)


if __name__ == "__main__":
    unittest.main()
