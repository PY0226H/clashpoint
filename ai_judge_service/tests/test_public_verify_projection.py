from __future__ import annotations

import unittest
from typing import Any

from app.applications.public_verify_projection import (
    build_trust_public_verify_payload_from_bundle,
    build_trust_public_verify_route_payload,
)


class PublicVerifyProjectionTests(unittest.TestCase):
    def test_route_payload_should_keep_public_contract_envelope(self) -> None:
        verify_payload = {"caseCommitment": {"commitmentHash": "commit-hash"}}

        payload = build_trust_public_verify_route_payload(
            case_id=3001,
            dispatch_type=" FINAL ",
            trace_id=" trace-public-3001 ",
            verify_payload=verify_payload,
        )

        self.assertEqual(payload["caseId"], 3001)
        self.assertEqual(payload["dispatchType"], "final")
        self.assertEqual(payload["traceId"], "trace-public-3001")
        self.assertEqual(
            payload["verificationVersion"],
            "trust-public-verification-v1",
        )
        self.assertEqual(payload["verifyPayload"], verify_payload)
        self.assertIsNot(payload["verifyPayload"], verify_payload)
        self.assertTrue(payload["proxyRequired"])
        self.assertEqual(payload["visibilityContract"]["layer"], "public")
        self.assertTrue(payload["visibilityContract"]["chatProxyRequired"])
        self.assertFalse(
            payload["visibilityContract"]["directAiServiceAccessAllowed"],
        )
        self.assertEqual(
            payload["verificationRequest"]["requestKey"],
            "case:3001:dispatch:final:trace:trace-public-3001:registry:trust-registry-v1:verification:trust-public-verification-v1",
        )
        self.assertEqual(
            payload["verificationReadiness"]["status"],
            "artifact_manifest_pending",
        )
        self.assertFalse(payload["verificationReadiness"]["externalizable"])
        self.assertFalse(payload["cacheProfile"]["cacheable"])
        self.assertEqual(payload["cacheProfile"]["ttlSeconds"], 0)

    def test_bundle_payload_should_build_ready_public_verify_projection(self) -> None:
        artifact_manifest = {"manifestHash": "manifest-hash"}
        bundle = {
            "context": {
                "dispatchType": "final",
                "traceId": "trace-public-3002",
                "registryVersion": "trust-registry-custom-v1",
                "source": "trust_registry",
            },
            "commitment": {
                "version": "trust-phaseA-case-commitment-v1",
                "commitmentHash": "commit-hash",
            },
            "verdictAttestation": {
                "version": "trust-phaseA-verdict-attestation-v1",
                "registryHash": "attestation-hash",
                "verified": True,
            },
            "challengeReview": {
                "version": "trust-phaseB-challenge-review-v1",
                "registryHash": "challenge-hash",
                "challengeState": "not_challenged",
            },
            "kernelVersion": {
                "version": "trust-phaseA-kernel-version-v1",
                "registryHash": "kernel-hash",
            },
        }

        def _build_audit_anchor_export(**kwargs: Any) -> dict[str, Any]:
            self.assertEqual(kwargs["case_id"], 3002)
            self.assertEqual(kwargs["dispatch_type"], "final")
            self.assertEqual(kwargs["trace_id"], "trace-public-3002")
            self.assertFalse(kwargs["include_payload"])
            self.assertEqual(kwargs["artifact_manifest"], artifact_manifest)
            return {
                "version": "trust-phaseA-audit-anchor-v1",
                "anchorHash": "anchor-hash",
                "anchorStatus": "artifact_ready",
                "componentHashes": {
                    "caseCommitmentHash": "commit-hash",
                    "verdictAttestationHash": "attestation-hash",
                    "challengeReviewHash": "challenge-hash",
                    "kernelVersionHash": "kernel-hash",
                    "artifactManifestHash": "manifest-hash",
                },
            }

        def _build_public_verify_payload(**kwargs: Any) -> dict[str, Any]:
            self.assertEqual(kwargs["audit_anchor"]["anchorHash"], "anchor-hash")
            return {
                "caseCommitment": kwargs["commitment"],
                "verdictAttestation": kwargs["verdict_attestation"],
                "challengeReview": kwargs["challenge_review"],
                "kernelVersion": kwargs["kernel_version"],
                "auditAnchor": kwargs["audit_anchor"],
            }

        payload = build_trust_public_verify_payload_from_bundle(
            case_id=3002,
            bundle=bundle,
            build_audit_anchor_export=_build_audit_anchor_export,
            build_public_verify_payload=_build_public_verify_payload,
            artifact_manifest=artifact_manifest,
        )

        self.assertEqual(payload["caseId"], 3002)
        self.assertEqual(payload["dispatchType"], "final")
        self.assertEqual(payload["traceId"], "trace-public-3002")
        self.assertEqual(
            payload["verificationRequest"]["registryVersion"],
            "trust-registry-custom-v1",
        )
        self.assertTrue(payload["verificationReadiness"]["ready"])
        self.assertEqual(payload["verificationReadiness"]["status"], "ready")
        self.assertTrue(payload["verificationReadiness"]["externalizable"])
        self.assertTrue(payload["cacheProfile"]["cacheable"])
        self.assertEqual(payload["cacheProfile"]["ttlSeconds"], 300)
        self.assertEqual(
            payload["verifyPayload"]["auditAnchor"]["componentHashes"][
                "artifactManifestHash"
            ],
            "manifest-hash",
        )


if __name__ == "__main__":
    unittest.main()
