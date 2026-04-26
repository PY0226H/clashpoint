from __future__ import annotations

import json
import unittest

from app.applications.registry_release_gate import (
    RELEASE_READINESS_EVIDENCE_VERSION,
    build_policy_release_gate_decision,
)


class RegistryReleaseGateTests(unittest.TestCase):
    def test_policy_release_gate_decision_should_merge_p37_readiness_inputs(self) -> None:
        dependency_health = {
            "ok": True,
            "code": "dependency_ok",
            "policyVersion": "policy-v3-default",
            "policyProfile": {
                "metadata": {
                    "releaseGateInputs": {
                        "generatedAt": "2026-04-25T00:00:00Z",
                        "artifactStoreReadiness": {"status": "env_blocked"},
                        "publicVerificationReadiness": {
                            "status": "ready",
                            "externalizable": True,
                            "evidenceRef": "public-verify-manifest",
                        },
                        "citationVerification": {"status": "passed"},
                        "trustRegistryWriteThrough": {"status": "ready"},
                        "panelShadowDrift": {"status": "ready"},
                        "artifactRefs": [{"ref": "release-manifest"}],
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
            "latestRun": {
                "runId": "benchmark-real",
                "status": "pass",
                "thresholdDecision": "accepted",
                "environmentMode": "real",
            },
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
        evidence = payload["releaseReadinessEvidence"]
        self.assertEqual(
            evidence["evidenceVersion"],
            RELEASE_READINESS_EVIDENCE_VERSION,
        )
        self.assertEqual(evidence["generatedAt"], "2026-04-25T00:00:00Z")
        self.assertEqual(evidence["policyVersion"], "policy-v3-default")
        self.assertEqual(evidence["decision"], "env_blocked")
        self.assertEqual(evidence["decisionCode"], "registry_release_gate_env_blocked")
        self.assertIn("artifactStoreReadiness", evidence["envBlockedComponents"])
        self.assertIn(
            "registry_release_gate_artifactStoreReadiness_env_blocked",
            evidence["reasonCodes"],
        )
        self.assertEqual(
            evidence["publicVerificationReadiness"]["status"],
            "ready",
        )
        self.assertTrue(evidence["publicVerificationReadiness"]["externalizable"])
        self.assertEqual(
            evidence["artifactRefs"],
            ["public-verify-manifest", "release-manifest"],
        )
        self.assertEqual(evidence["realEnvEvidenceStatus"]["status"], "env_blocked")
        self.assertEqual(
            evidence["fairnessPanelEvidence"]["benchmarkEvidenceStatus"],
            "ready",
        )
        self.assertEqual(
            evidence["fairnessPanelEvidence"]["realSampleManifestStatus"],
            "ready",
        )

    def test_policy_release_gate_should_env_block_without_benchmark(self) -> None:
        dependency_health = {
            "ok": True,
            "code": "dependency_ok",
            "policyProfile": {
                "metadata": {
                    "releaseGateInputs": {
                        "artifactStoreReadiness": {"status": "ready"},
                        "publicVerificationReadiness": {"status": "ready"},
                        "citationVerification": {"status": "passed"},
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
        self.assertEqual(
            payload["releaseReadinessEvidence"]["fairnessPanelEvidence"][
                "benchmarkEvidenceStatus"
            ],
            "pending_real_samples",
        )

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
            "latestRun": {
                "runId": "benchmark-real",
                "status": "pass",
                "thresholdDecision": "accepted",
                "environmentMode": "real",
            },
        }

        payload = build_policy_release_gate_decision(
            dependency_health=dependency_health,
            fairness_gate=fairness_gate,
        )

        self.assertFalse(payload["allowed"])
        self.assertEqual(payload["decision"], "needs_review")
        self.assertFalse(payload["metadataInputPresent"])
        self.assertEqual(payload["statusCounts"]["needs_review"], 5)

    def test_policy_release_gate_should_env_block_local_reference_fairness(self) -> None:
        dependency_health = {
            "ok": True,
            "code": "dependency_ok",
            "policyVersion": "policy-v3-local",
            "policyProfile": {
                "metadata": {
                    "releaseGateInputs": {
                        "artifactStoreReadiness": {"status": "ready"},
                        "publicVerificationReadiness": {"status": "ready"},
                        "citationVerification": {"status": "passed"},
                        "trustRegistryWriteThrough": {"status": "ready"},
                        "panelShadowDrift": {"status": "ready"},
                    }
                }
            },
        }
        fairness_gate = {
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
                "environmentMode": "local_reference",
            },
        }

        payload = build_policy_release_gate_decision(
            dependency_health=dependency_health,
            fairness_gate=fairness_gate,
        )

        self.assertFalse(payload["allowed"])
        self.assertEqual(payload["decision"], "env_blocked")
        reason_codes = {row["code"] for row in payload["reasons"]}
        self.assertIn(
            "registry_release_gate_fairness_benchmark_local_reference_only",
            reason_codes,
        )
        self.assertIn(
            "registry_release_gate_panel_shadow_local_reference_only",
            reason_codes,
        )
        evidence = payload["releaseReadinessEvidence"]
        self.assertEqual(evidence["realEnvEvidenceStatus"]["status"], "env_blocked")
        self.assertIn("fairnessBenchmark", evidence["envBlockedComponents"])
        self.assertIn("panelShadowDrift", evidence["envBlockedComponents"])
        self.assertEqual(
            evidence["fairnessPanelEvidence"]["benchmarkEvidenceStatus"],
            "env_blocked",
        )
        self.assertEqual(
            evidence["fairnessPanelEvidence"]["shadowEvidenceStatus"],
            "env_blocked",
        )

    def test_policy_release_readiness_evidence_should_redact_unknown_raw_payload(self) -> None:
        dependency_health = {
            "ok": True,
            "code": "dependency_ok",
            "policyVersion": "policy-v3-redaction",
            "policyProfile": {
                "metadata": {
                    "releaseGateInputs": {
                        "artifactStoreReadiness": {"status": "ready"},
                        "publicVerificationReadiness": {
                            "status": "ready",
                            "rawPrompt": "hidden prompt",
                            "rawTrace": "hidden trace",
                            "rawTranscript": "hidden transcript",
                            "userIdentity": "hidden identity",
                            "spend": "hidden spend",
                            "reputation": "hidden reputation",
                        },
                        "citationVerification": {
                            "status": "passed",
                            "reasonCodes": [],
                            "rawPrompt": "hidden citation prompt",
                        },
                        "trustRegistryWriteThrough": {"status": "ready"},
                        "panelShadowDrift": {"status": "ready"},
                        "artifactRefs": [
                            {
                                "ref": "safe-release-manifest",
                                "rawPrompt": "hidden prompt in artifact ref",
                            }
                        ],
                    }
                }
            },
        }
        fairness_gate = {
            "passed": True,
            "benchmarkGatePassed": True,
            "shadowGateApplied": False,
            "thresholdDecision": "accepted",
            "latestRun": {
                "runId": "benchmark-real",
                "status": "pass",
                "thresholdDecision": "accepted",
                "environmentMode": "real",
            },
        }

        payload = build_policy_release_gate_decision(
            dependency_health=dependency_health,
            fairness_gate=fairness_gate,
        )

        evidence_text = json.dumps(
            payload["releaseReadinessEvidence"],
            ensure_ascii=False,
            sort_keys=True,
        )
        self.assertNotIn("hidden prompt", evidence_text)
        self.assertNotIn("hidden trace", evidence_text)
        self.assertNotIn("hidden transcript", evidence_text)
        self.assertNotIn("hidden identity", evidence_text)
        self.assertNotIn("hidden spend", evidence_text)
        self.assertNotIn("hidden reputation", evidence_text)
        self.assertNotIn("hidden citation prompt", evidence_text)
        self.assertIn("safe-release-manifest", evidence_text)

    def test_policy_release_gate_should_block_for_citation_verifier_blocked(self) -> None:
        dependency_health = {
            "ok": True,
            "code": "dependency_ok",
            "policyVersion": "policy-v3-citation",
            "policyProfile": {
                "metadata": {
                    "releaseGateInputs": {
                        "artifactStoreReadiness": {"status": "ready"},
                        "publicVerificationReadiness": {"status": "ready"},
                        "trustRegistryWriteThrough": {"status": "ready"},
                        "panelShadowDrift": {"status": "ready"},
                        "citationVerification": {
                            "version": "evidence-citation-verification-v1",
                            "status": "blocked",
                            "citationCount": 2,
                            "messageRefCount": 1,
                            "sourceRefCount": 1,
                            "missingCitationCount": 1,
                            "weakCitationCount": 0,
                            "forbiddenSourceCount": 1,
                            "reasonCodes": [
                                "citation_verifier_missing_evidence_refs",
                                "citation_verifier_forbidden_source_metadata",
                            ],
                        },
                    }
                }
            },
        }
        fairness_gate = {
            "passed": True,
            "benchmarkGatePassed": True,
            "shadowGateApplied": False,
            "thresholdDecision": "accepted",
            "latestRun": {
                "runId": "benchmark-real",
                "status": "pass",
                "thresholdDecision": "accepted",
                "environmentMode": "real",
            },
        }

        payload = build_policy_release_gate_decision(
            dependency_health=dependency_health,
            fairness_gate=fairness_gate,
        )

        self.assertFalse(payload["allowed"])
        self.assertEqual(payload["decision"], "blocked")
        reason_codes = {row["code"] for row in payload["reasons"]}
        self.assertIn("citation_verifier_missing_evidence_refs", reason_codes)
        evidence = payload["releaseReadinessEvidence"]
        self.assertEqual(evidence["citationVerification"]["status"], "blocked")
        self.assertEqual(evidence["citationVerification"]["missingCitationCount"], 1)
        self.assertEqual(evidence["citationVerification"]["forbiddenSourceCount"], 1)
        self.assertIn(
            "citation_verifier_forbidden_source_metadata",
            evidence["reasonCodes"],
        )


if __name__ == "__main__":
    unittest.main()
