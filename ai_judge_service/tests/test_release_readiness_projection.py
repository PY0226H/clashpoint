from __future__ import annotations

import unittest

from app.applications.release_readiness_projection import (
    build_registry_release_readiness_projection,
    summarize_release_readiness_evidence,
)


class ReleaseReadinessProjectionTests(unittest.TestCase):
    def test_summary_should_count_artifact_refs_and_real_env_statuses(self) -> None:
        summary = summarize_release_readiness_evidence(
            [
                {
                    "evidenceVersion": "policy-release-readiness-evidence-v1",
                    "envBlockedComponents": ["artifactStoreReadiness", "fairnessBenchmark"],
                    "reasonCodes": [
                        "registry_release_gate_artifactStoreReadiness_local_reference_only"
                    ],
                    "artifactRefs": ["public-verify-manifest", "public-verify-manifest"],
                    "releaseReadinessArtifactSummary": {
                        "artifactRef": "release-readiness-artifact-a",
                        "manifestHash": "a" * 64,
                    },
                    "p41ControlPlaneEvidence": {
                        "status": "env_blocked",
                        "signalCounts": {
                            "ready": 5,
                            "env_blocked": 1,
                            "blocked": 0,
                            "needs_review": 0,
                            "missing": 0,
                        },
                    },
                    "realEnvEvidenceStatus": {"status": "env_blocked"},
                },
                {
                    "envBlockedComponents": ["fairnessBenchmark"],
                    "reasonCodes": [
                        "registry_release_gate_artifactStoreReadiness_local_reference_only",
                        "registry_release_gate_fairness_benchmark_local_reference_only",
                    ],
                    "artifactRefs": ["release-manifest"],
                    "releaseReadinessArtifactSummary": {
                        "artifactRef": "release-readiness-artifact-b",
                        "manifestHash": "b" * 64,
                    },
                    "realEnvEvidenceStatus": {"status": "ready"},
                },
            ]
        )

        self.assertEqual(
            summary["evidenceVersion"],
            "policy-release-readiness-evidence-v1",
        )
        self.assertEqual(summary["evidenceCount"], 2)
        self.assertEqual(
            summary["envBlockedComponents"],
            ["artifactStoreReadiness", "fairnessBenchmark"],
        )
        self.assertEqual(summary["artifactRefCount"], 2)
        self.assertEqual(summary["releaseReadinessArtifactCount"], 2)
        self.assertEqual(summary["releaseReadinessManifestHashCount"], 2)
        self.assertEqual(
            summary["realEnvEvidenceStatusCounts"],
            {"env_blocked": 1, "ready": 1},
        )
        self.assertEqual(summary["p41ControlPlaneEvidenceCount"], 1)
        self.assertEqual(summary["p41ControlPlaneStatusCounts"], {"env_blocked": 1})
        self.assertEqual(
            summary["p41ControlPlaneSignalCounts"],
            {
                "blocked": 0,
                "env_blocked": 1,
                "missing": 0,
                "needs_review": 0,
                "ready": 5,
            },
        )

    def test_registry_projection_should_keep_route_contract_and_items(self) -> None:
        rows = [
            {
                "policyVersion": "policy-v3-local",
                "releaseGateDecision": "env_blocked",
                "releaseGateCode": "registry_release_gate_env_blocked",
                "releaseGateReasonCodes": [
                    "registry_release_gate_fairness_benchmark_local_reference_only"
                ],
                "releaseReadinessEvidence": {
                    "evidenceVersion": "policy-release-readiness-evidence-v1",
                    "policyVersion": "policy-v3-local",
                    "decision": "env_blocked",
                    "artifactRefs": ["release-manifest"],
                    "releaseReadinessArtifactSummary": {
                        "artifactRef": "release-readiness-artifact",
                        "manifestHash": "c" * 64,
                    },
                    "p41ControlPlaneEvidence": {
                        "status": "env_blocked",
                        "signalCounts": {"ready": 5, "env_blocked": 1},
                    },
                    "realEnvEvidenceStatus": {"status": "env_blocked"},
                },
            }
        ]

        payload = build_registry_release_readiness_projection(
            decision_counts={
                "allowed": 0,
                "blocked": 0,
                "env_blocked": 1,
                "needs_review": 0,
            },
            component_block_counts={"fairnessBenchmark": 1},
            dependency_rows=rows,
        )

        self.assertEqual(payload["decisionCounts"]["env_blocked"], 1)
        self.assertEqual(payload["envBlockedCount"], 1)
        self.assertEqual(payload["componentBlockCounts"], {"fairnessBenchmark": 1})
        self.assertEqual(payload["evidenceCount"], 1)
        self.assertEqual(payload["releaseReadinessArtifactCount"], 1)
        self.assertEqual(payload["releaseReadinessManifestHashCount"], 1)
        self.assertEqual(payload["p41ControlPlaneEvidenceCount"], 1)
        self.assertEqual(payload["p41ControlPlaneStatusCounts"], {"env_blocked": 1})
        self.assertEqual(payload["items"][0]["policyVersion"], "policy-v3-local")
        self.assertEqual(
            payload["items"][0]["evidence"]["releaseReadinessArtifactSummary"][
                "artifactRef"
            ],
            "release-readiness-artifact",
        )


if __name__ == "__main__":
    unittest.main()
