from __future__ import annotations

import unittest

from app.applications.registry_release_gate import build_policy_release_gate_decision


class RegistryReleaseGateTests(unittest.TestCase):
    def test_policy_release_gate_decision_should_merge_p37_readiness_inputs(self) -> None:
        dependency_health = {
            "ok": True,
            "code": "dependency_ok",
            "policyProfile": {
                "metadata": {
                    "releaseGateInputs": {
                        "artifactStoreReadiness": {"status": "env_blocked"},
                        "publicVerificationReadiness": {"status": "ready"},
                        "trustRegistryWriteThrough": {"status": "ready"},
                        "panelShadowDrift": {"status": "ready"},
                    }
                }
            },
        }
        fairness_gate = {
            "passed": True,
            "benchmarkGatePassed": True,
            "shadowGateApplied": False,
            "shadowGatePassed": None,
            "thresholdDecision": "accepted",
        }

        payload = build_policy_release_gate_decision(
            dependency_health=dependency_health,
            fairness_gate=fairness_gate,
        )

        self.assertFalse(payload["allowed"])
        self.assertEqual(payload["decision"], "env_blocked")
        self.assertEqual(payload["code"], "registry_release_gate_env_blocked")
        reason_codes = {row["code"] for row in payload["reasons"]}
        self.assertIn("registry_release_gate_artifactStoreReadiness_env_blocked", reason_codes)

    def test_policy_release_gate_should_env_block_without_benchmark(self) -> None:
        dependency_health = {
            "ok": True,
            "code": "dependency_ok",
            "policyProfile": {
                "metadata": {
                    "releaseGateInputs": {
                        "artifactStoreReadiness": {"status": "ready"},
                        "publicVerificationReadiness": {"status": "ready"},
                        "trustRegistryWriteThrough": {"status": "ready"},
                        "panelShadowDrift": {"status": "ready"},
                    }
                }
            },
        }
        fairness_gate = {
            "passed": False,
            "benchmarkGatePassed": False,
            "shadowGateApplied": False,
            "code": "registry_fairness_gate_no_benchmark",
        }

        payload = build_policy_release_gate_decision(
            dependency_health=dependency_health,
            fairness_gate=fairness_gate,
        )

        self.assertFalse(payload["allowed"])
        self.assertEqual(payload["decision"], "env_blocked")
        reason_codes = {row["code"] for row in payload["reasons"]}
        self.assertIn("registry_fairness_gate_no_benchmark", reason_codes)

    def test_policy_release_gate_should_need_review_for_missing_p37_inputs(self) -> None:
        dependency_health = {
            "ok": True,
            "code": "dependency_ok",
            "policyProfile": {"metadata": {}},
        }
        fairness_gate = {
            "passed": True,
            "benchmarkGatePassed": True,
            "shadowGateApplied": False,
            "thresholdDecision": "accepted",
        }

        payload = build_policy_release_gate_decision(
            dependency_health=dependency_health,
            fairness_gate=fairness_gate,
        )

        self.assertFalse(payload["allowed"])
        self.assertEqual(payload["decision"], "needs_review")
        self.assertFalse(payload["metadataInputPresent"])
        self.assertEqual(payload["statusCounts"]["needs_review"], 4)


if __name__ == "__main__":
    unittest.main()
