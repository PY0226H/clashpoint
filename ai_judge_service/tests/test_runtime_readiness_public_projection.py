from __future__ import annotations

import unittest

from app.applications.runtime_readiness_public_projection import (
    build_runtime_readiness_evidence_refs,
    build_runtime_readiness_fairness_section,
    build_runtime_readiness_panel_runtime_section,
    build_runtime_readiness_release_gate_section,
)


class RuntimeReadinessPublicProjectionTests(unittest.TestCase):
    def test_release_gate_and_evidence_refs_should_project_p41_counts(self) -> None:
        trust_monitoring = {
            "registryReleaseReadiness": {
                "status": "blocked",
                "blockedPolicyCount": 1,
                "releaseReadinessEvidenceVersion": "rr-v1",
                "releaseReadinessEvidenceCount": 2,
                "releaseReadinessArtifactCount": 1,
                "releaseReadinessManifestHashCount": 1,
                "p41ControlPlaneEvidenceCount": 1,
                "p41ControlPlaneStatusCounts": {"env_blocked": 1},
                "reasonCodes": ["real_env_evidence_not_ready"],
            },
            "realEnvEvidenceStatus": {
                "status": "env_blocked",
                "realEnvEvidenceAvailable": False,
            },
        }

        release_gate = build_runtime_readiness_release_gate_section(
            release_gate={"passed": False},
            trust_monitoring=trust_monitoring,
            adaptive_summary={"calibrationGateCode": "real_env_evidence_not_ready"},
        )
        refs = build_runtime_readiness_evidence_refs(
            trust_monitoring=trust_monitoring
        )

        self.assertFalse(release_gate["passed"])
        self.assertEqual(release_gate["registryStatus"], "blocked")
        self.assertEqual(refs[0]["p41ControlPlaneEvidenceCount"], 1)
        self.assertEqual(refs[0]["p41ControlPlaneStatusCounts"], {"env_blocked": 1})
        self.assertFalse(refs[1]["evidenceAvailable"])

    def test_calibration_and_panel_sections_should_keep_advisory_only_flags(
        self,
    ) -> None:
        fairness = build_runtime_readiness_fairness_section(
            fairness_calibration_advisor={
                "decisionLog": {
                    "summary": {
                        "totalCount": 3,
                        "acceptedForReviewCount": 2,
                    },
                    "releaseGateReference": {"blockingDecisionCount": 1},
                }
            },
            trust_monitoring={
                "panelShadowDrift": {
                    "status": "blocked",
                    "shadowRunCount": 4,
                    "shadowThresholdViolationCount": 1,
                },
                "realEnvEvidenceStatus": {"realSampleManifestStatus": "missing"},
            },
            adaptive_summary={
                "calibrationGatePassed": False,
                "calibrationGateCode": "decision_log_blocked",
                "calibrationHighRiskCount": 2,
                "recommendedActionCount": 1,
            },
        )
        panel = build_runtime_readiness_panel_runtime_section(
            panel_runtime_readiness={
                "overview": {
                    "shadow": {
                        "candidateModelGroupCount": 2,
                        "switchBlockerCounts": {
                            "real_samples_missing": 1,
                            "release_gate_blocked": 1,
                        },
                        "releaseGateSignalCounts": {"blocked": 1},
                        "avgDecisionAgreement": 0.82,
                    }
                }
            },
            trust_monitoring={"panelShadowDrift": {"status": "blocked"}},
            adaptive_summary={
                "panelReadyGroupCount": 1,
                "panelWatchGroupCount": 1,
                "panelAttentionGroupCount": 1,
                "panelScannedRecordCount": 20,
            },
        )

        self.assertEqual(fairness["decisionCount"], 3)
        self.assertEqual(fairness["decisionLogBlocksProductionReadyCount"], 1)
        self.assertEqual(panel["candidateModelGroupCount"], 2)
        self.assertEqual(panel["switchBlockerCount"], 2)
        self.assertEqual(panel["releaseBlockedGroupCount"], 1)
        self.assertFalse(panel["autoSwitchAllowed"])
        self.assertFalse(panel["officialWinnerSemanticsChanged"])
