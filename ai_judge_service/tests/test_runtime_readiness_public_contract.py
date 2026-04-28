from __future__ import annotations

import unittest
from typing import Any

from app.applications.runtime_readiness_public_contract import (
    RUNTIME_READINESS_PUBLIC_CONTRACT_VERSION,
    build_runtime_readiness_public_payload,
    validate_runtime_readiness_public_contract,
)


class RuntimeReadinessPublicContractTests(unittest.TestCase):
    def _build_pack_payload(
        self,
        *,
        real_env_status: str = "env_blocked",
        real_env_available: bool = True,
        release_gate_passed: bool | None = False,
    ) -> dict[str, Any]:
        return {
            "generatedAt": "2026-04-28T00:00:00Z",
            "fairnessCalibrationAdvisor": {
                "releaseGate": {
                    "passed": release_gate_passed,
                    "code": "real_env_evidence_not_ready",
                },
                "recommendedActions": [
                    {
                        "actionId": "collect-real-env-samples",
                        "severity": "blocker",
                        "reasonCode": "real_env_evidence_not_ready",
                        "title": "Collect real environment calibration evidence",
                        "ownerRole": "ai_ops",
                        "provider": "should_not_leak",
                    }
                ],
            },
            "adaptiveSummary": {
                "calibrationGatePassed": release_gate_passed,
                "calibrationGateCode": "real_env_evidence_not_ready",
                "calibrationHighRiskCount": 2,
                "recommendedActionCount": 1,
                "registryPromptToolRiskCount": 3,
                "registryPromptToolHighRiskCount": 1,
                "panelReadyGroupCount": 4,
                "panelWatchGroupCount": 2,
                "panelAttentionGroupCount": 1,
                "panelScannedRecordCount": 120,
                "reviewQueueCount": 5,
                "reviewHighRiskCount": 1,
                "evidenceClaimQueueCount": 2,
                "trustChallengeQueueCount": 1,
            },
            "trustMonitoring": {
                "overallStatus": "blocked",
                "sampledCaseCount": 8,
                "artifactStoreReadiness": {
                    "status": "ready",
                    "sampledCaseCount": 8,
                    "readyCount": 8,
                    "missingCount": 0,
                    "manifestHashPresentCount": 8,
                },
                "publicVerificationReadiness": {
                    "status": "ready",
                    "sampledCaseCount": 8,
                    "verifiedCount": 8,
                    "failedCount": 0,
                },
                "challengeReviewLag": {
                    "status": "watch",
                    "openChallengeCount": 1,
                    "urgentCount": 0,
                    "highPriorityCount": 1,
                },
                "registryReleaseReadiness": {
                    "status": "blocked",
                    "blockedPolicyCount": 1,
                    "missingKernelBindingCount": 0,
                    "highRiskItemCount": 1,
                    "overrideAppliedPolicyCount": 0,
                    "releaseReadinessEvidenceVersion": "rr-v1",
                    "releaseReadinessEvidenceCount": 2,
                    "releaseReadinessArtifactCount": 1,
                    "releaseReadinessManifestHashCount": 1,
                    "envBlockedComponents": ["calibration_samples"],
                    "reasonCodes": ["real_env_evidence_not_ready"],
                },
                "citationVerifierEvidence": {
                    "status": "ready",
                    "reasonCodes": [],
                    "missingCitationCount": 0,
                    "weakCitationCount": 0,
                    "forbiddenSourceCount": 0,
                },
                "panelShadowDrift": {
                    "status": "blocked",
                    "shadowRunCount": 3,
                    "shadowThresholdViolationCount": 1,
                    "driftBreachCount": 0,
                    "shadowGateApplied": True,
                    "shadowGatePassed": False,
                    "latestShadowRunStatus": "completed",
                    "latestShadowRunThresholdDecision": "blocked",
                    "latestShadowRunEnvironmentMode": "shadow",
                },
                "realEnvEvidenceStatus": {
                    "status": real_env_status,
                    "realEnvEvidenceAvailable": real_env_available,
                    "latestRunStatus": "completed",
                    "latestRunThresholdDecision": "blocked",
                    "latestRunEnvironmentMode": "production",
                    "latestRunNeedsRemediation": True,
                    "realSampleManifestStatus": real_env_status,
                },
                "blockerCounts": {
                    "production": 0,
                    "review": 1,
                    "release": 2,
                    "evidence": 1,
                },
                "blockers": [
                    {
                        "bucket": "evidence",
                        "code": "real_env_evidence_not_ready",
                        "count": 1,
                        "severity": "watch",
                    }
                ],
            },
            "filters": {
                "dispatchType": "final",
                "policyVersion": "v3-default",
                "windowDays": 7,
            },
            "rawTrace": {"provider": "should_not_leak"},
        }

    def test_build_runtime_readiness_public_payload_should_project_safe_shape(
        self,
    ) -> None:
        payload = build_runtime_readiness_public_payload(self._build_pack_payload())

        self.assertEqual(payload["version"], RUNTIME_READINESS_PUBLIC_CONTRACT_VERSION)
        self.assertEqual(payload["status"], "env_blocked")
        self.assertEqual(payload["statusReason"], "real_env_evidence_env_blocked")
        self.assertFalse(payload["releaseGate"]["passed"])
        self.assertEqual(payload["summary"]["calibrationHighRiskCount"], 2)
        self.assertEqual(payload["panelRuntime"]["attentionGroupCount"], 1)
        self.assertEqual(payload["trustAndChallenge"]["openChallengeCount"], 1)
        self.assertTrue(payload["realEnv"]["evidenceAvailable"])
        self.assertEqual(payload["recommendedActions"][0]["id"], "collect-real-env-samples")
        self.assertNotIn("provider", payload["recommendedActions"][0])
        self.assertFalse(payload["visibilityContract"]["rawTraceVisible"])
        self.assertFalse(payload["visibilityContract"]["artifactRefsVisible"])
        validate_runtime_readiness_public_contract(payload)

    def test_build_runtime_readiness_public_payload_should_mark_local_reference_only(
        self,
    ) -> None:
        payload = build_runtime_readiness_public_payload(
            self._build_pack_payload(
                real_env_status="env_blocked",
                real_env_available=False,
            )
        )

        self.assertEqual(payload["status"], "local_reference_only")
        self.assertEqual(payload["statusReason"], "real_env_evidence_missing")

    def test_validate_runtime_readiness_public_contract_should_reject_forbidden_keys(
        self,
    ) -> None:
        payload = build_runtime_readiness_public_payload(self._build_pack_payload())
        payload["summary"]["traceId"] = "internal-trace"

        with self.assertRaisesRegex(ValueError, "runtime_readiness_forbidden_key"):
            validate_runtime_readiness_public_contract(payload)

