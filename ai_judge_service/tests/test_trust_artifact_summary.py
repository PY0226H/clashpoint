from __future__ import annotations

import unittest

from app.applications.trust_artifact_summary import (
    build_trust_artifact_summary_from_public_verify_payload,
    build_trust_artifact_summary_from_report_payload,
)


class TrustArtifactSummaryTests(unittest.TestCase):
    def test_public_verify_summary_should_expose_refs_without_private_payload(self) -> None:
        payload = build_trust_artifact_summary_from_public_verify_payload(
            public_verify_payload={
                "caseId": 9701,
                "dispatchType": "final",
                "traceId": "trace-9701",
                "verifyPayload": {
                    "caseCommitment": {"commitmentHash": "commit-hash"},
                    "verdictAttestation": {
                        "registryHash": "verdict-hash",
                        "verified": True,
                        "reason": "ok",
                    },
                    "challengeReview": {
                        "registryHash": "challenge-hash",
                        "reviewRequired": False,
                        "reviewState": "not_required",
                        "challengeState": None,
                        "totalChallenges": 0,
                    },
                    "kernelVersion": {"registryHash": "kernel-hash"},
                    "auditAnchor": {
                        "anchorStatus": "artifact_ready",
                        "anchorHash": "anchor-hash",
                        "componentHashes": {
                            "artifactManifestHash": "manifest-hash",
                        },
                        "artifactManifest": {
                            "manifestHash": "manifest-hash",
                            "releaseReadinessArtifactSummary": {
                                "artifactRef": "release-artifact-1",
                                "manifestHash": "release-manifest-hash",
                                "decision": "env_blocked",
                                "storageMode": "local_reference",
                            },
                            "artifactRefs": [
                                {
                                    "kind": "audit_pack",
                                    "artifactId": "art-1",
                                    "uri": "artifact://case/9701/audit",
                                    "sha256": "a" * 64,
                                    "redactionLevel": "ops",
                                }
                            ],
                        },
                    },
                },
            },
            include_artifact_refs=True,
        )

        self.assertTrue(payload["trustCompleteness"]["complete"])
        self.assertTrue(payload["artifactCoverage"]["ready"])
        self.assertEqual(payload["artifactCoverage"]["artifactRefCount"], 1)
        self.assertEqual(payload["artifactCoverage"]["artifactRefs"][0]["kind"], "audit_pack")
        self.assertEqual(
            payload["artifactCoverage"]["releaseReadinessArtifact"]["artifactRef"],
            "release-artifact-1",
        )
        self.assertEqual(
            payload["artifactCoverage"]["releaseReadinessArtifact"]["decision"],
            "env_blocked",
        )
        self.assertNotIn("payload", payload["artifactCoverage"]["artifactRefs"][0])

    def test_report_payload_summary_should_mark_registry_snapshot_missing(self) -> None:
        payload = build_trust_artifact_summary_from_report_payload(
            report_payload={
                "trustAttestation": {
                    "dispatchType": "final",
                    "commitmentHash": "commit-hash",
                    "componentHashes": {"verdictHash": "verdict-hash"},
                }
            },
            case_id=9702,
            dispatch_type=None,
            trace_id="trace-9702",
            include_artifact_refs=True,
        )

        self.assertEqual(payload["source"], "report_payload")
        self.assertTrue(payload["trustCompleteness"]["caseCommitment"])
        self.assertFalse(payload["trustCompleteness"]["complete"])
        self.assertEqual(
            payload["publicVerifyStatus"]["reason"],
            "registry_snapshot_missing",
        )
        self.assertFalse(payload["artifactCoverage"]["ready"])


if __name__ == "__main__":
    unittest.main()
