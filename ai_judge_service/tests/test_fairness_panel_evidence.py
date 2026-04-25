from __future__ import annotations

import unittest

from app.applications.fairness_panel_evidence import (
    FAIRNESS_PANEL_EVIDENCE_VERSION,
    build_fairness_panel_evidence_normalization,
)


class FairnessPanelEvidenceTests(unittest.TestCase):
    def test_normalization_should_env_block_local_reference_runs(self) -> None:
        payload = build_fairness_panel_evidence_normalization(
            fairness_gate={
                "passed": True,
                "benchmarkGatePassed": True,
                "shadowGateApplied": True,
                "shadowGatePassed": True,
                "thresholdDecision": "accepted",
                "latestRun": {
                    "runId": "benchmark-local",
                    "status": "local_reference_frozen",
                    "environmentMode": "local_reference",
                },
                "latestShadowRun": {
                    "runId": "shadow-local",
                    "status": "local_reference_frozen",
                    "environmentMode": "local",
                },
            },
        )

        self.assertEqual(payload["evidenceVersion"], FAIRNESS_PANEL_EVIDENCE_VERSION)
        self.assertEqual(payload["benchmarkEvidenceStatus"], "env_blocked")
        self.assertEqual(payload["realSampleManifestStatus"], "env_blocked")
        self.assertEqual(payload["shadowEvidenceStatus"], "env_blocked")
        self.assertEqual(payload["latestRunEnvironmentMode"], "local_reference")
        self.assertEqual(payload["releaseGateInputStatus"], "env_blocked")
        self.assertTrue(payload["advisoryOnly"])
        self.assertFalse(payload["officialWinnerMutationAllowed"])

    def test_normalization_should_keep_missing_real_samples_env_blocked(self) -> None:
        payload = build_fairness_panel_evidence_normalization(
            fairness_gate={
                "passed": False,
                "benchmarkGatePassed": False,
                "shadowGateApplied": False,
                "shadowGatePassed": None,
                "code": "registry_fairness_gate_no_benchmark",
            },
            release_inputs={"panelShadowDrift": {"status": "ready"}},
        )

        self.assertEqual(payload["benchmarkEvidenceStatus"], "pending_real_samples")
        self.assertEqual(payload["realSampleManifestStatus"], "pending_real_samples")
        self.assertEqual(payload["shadowEvidenceStatus"], "missing")
        self.assertEqual(payload["releaseGateInputStatus"], "env_blocked")

    def test_normalization_should_mark_real_shadow_pass_ready(self) -> None:
        payload = build_fairness_panel_evidence_normalization(
            fairness_gate={
                "passed": True,
                "benchmarkGatePassed": True,
                "shadowGateApplied": True,
                "shadowGatePassed": True,
                "thresholdDecision": "accepted",
                "latestRun": {
                    "runId": "benchmark-real",
                    "status": "pass",
                    "thresholdDecision": "accepted",
                    "environmentMode": "real",
                },
                "latestShadowRun": {
                    "runId": "shadow-real",
                    "status": "pass",
                    "thresholdDecision": "accepted",
                    "environmentMode": "real",
                },
            },
            release_inputs={"realEnvEvidenceStatus": {"status": "ready"}},
            fairness_calibration_advisor={"overview": {"driftBreachCount": 0}},
        )

        self.assertEqual(payload["benchmarkEvidenceStatus"], "ready")
        self.assertEqual(payload["realSampleManifestStatus"], "ready")
        self.assertEqual(payload["shadowEvidenceStatus"], "ready")
        self.assertEqual(payload["thresholdDecision"], "accepted")
        self.assertEqual(payload["latestRunEnvironmentMode"], "real")
        self.assertEqual(payload["releaseGateInputStatus"], "ready")

    def test_normalization_should_block_shadow_breaches_without_mutating_official_winner(
        self,
    ) -> None:
        payload = build_fairness_panel_evidence_normalization(
            fairness_gate={
                "benchmarkGatePassed": True,
                "shadowGateApplied": True,
                "shadowGatePassed": False,
                "thresholdDecision": "violated",
                "latestRun": {
                    "runId": "benchmark-real",
                    "status": "pass",
                    "thresholdDecision": "accepted",
                    "environmentMode": "real",
                },
                "latestShadowRun": {
                    "runId": "shadow-real",
                    "status": "threshold_violation",
                    "thresholdDecision": "violated",
                    "environmentMode": "real",
                },
            },
            fairness_calibration_advisor={
                "overview": {"shadowThresholdViolationCount": 1},
                "driftSummary": {"shadow": {"breaches": ["winner_flip_rate"]}},
            },
        )

        self.assertEqual(payload["shadowEvidenceStatus"], "blocked")
        self.assertEqual(payload["driftBreachCount"], 1)
        self.assertEqual(payload["releaseGateInputStatus"], "blocked")
        self.assertTrue(payload["advisoryOnly"])
        self.assertFalse(payload["officialWinnerMutationAllowed"])


if __name__ == "__main__":
    unittest.main()
