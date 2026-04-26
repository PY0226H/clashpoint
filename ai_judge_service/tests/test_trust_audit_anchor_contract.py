from __future__ import annotations

import unittest

from app.applications.trust_audit_anchor_contract import (
    TRUST_AUDIT_ANCHOR_BASE_COMPONENT_HASH_KEYS,
    TRUST_AUDIT_ANCHOR_COMPONENT_HASH_KEYS,
    TRUST_AUDIT_ANCHOR_ITEM_KEYS,
    TRUST_AUDIT_ANCHOR_PAYLOAD_KEYS,
    TRUST_AUDIT_ANCHOR_TOP_LEVEL_KEYS,
    validate_trust_audit_anchor_contract,
)


class TrustAuditAnchorContractTests(unittest.TestCase):
    def _build_payload(self, *, include_payload: bool, artifact_ready: bool = True) -> dict:
        artifact_manifest = {
            "version": "artifact-manifest-v1",
            "manifestHash": "artifact_manifest_hash",
            "artifactRefs": [],
        }
        component_hashes = {
            "caseCommitmentHash": "c_hash",
            "verdictAttestationHash": "va_hash",
            "challengeReviewHash": "cr_hash",
            "kernelVersionHash": "kv_hash",
        }
        if artifact_ready:
            component_hashes["artifactManifestHash"] = "artifact_manifest_hash"
        item = {
            "version": "trust-phaseA-audit-anchor-v1",
            "caseId": 9501,
            "dispatchType": "final",
            "traceId": "trace-final-9501",
            "anchorStatus": "artifact_ready" if artifact_ready else "artifact_pending",
            "componentHashes": component_hashes,
            "anchorHash": "anchor_hash" if artifact_ready else None,
            "artifactManifest": artifact_manifest if artifact_ready else None,
        }
        if include_payload:
            item["payload"] = {
                "caseCommitment": {"version": "trust-phaseA-case-commitment-v1"},
                "verdictAttestation": {"version": "trust-phaseA-verdict-attestation-v1"},
                "challengeReview": {"version": "trust-phaseB-challenge-review-v1"},
                "kernelVersion": {"version": "trust-phaseA-kernel-version-v1"},
            }
        return {
            "caseId": 9501,
            "dispatchType": "final",
            "traceId": "trace-final-9501",
            "item": item,
        }

    def test_validate_trust_audit_anchor_contract_should_pass_for_stable_payload(self) -> None:
        payload = self._build_payload(include_payload=True)
        self.assertEqual(set(payload.keys()), set(TRUST_AUDIT_ANCHOR_TOP_LEVEL_KEYS))
        self.assertEqual(set(payload["item"].keys()), set(TRUST_AUDIT_ANCHOR_ITEM_KEYS) | {"payload"})
        self.assertEqual(
            set(payload["item"]["componentHashes"].keys()),
            set(TRUST_AUDIT_ANCHOR_COMPONENT_HASH_KEYS),
        )
        self.assertEqual(
            set(payload["item"]["payload"].keys()),
            set(TRUST_AUDIT_ANCHOR_PAYLOAD_KEYS),
        )
        validate_trust_audit_anchor_contract(payload)

    def test_validate_trust_audit_anchor_contract_should_pass_when_optional_payload_absent(self) -> None:
        payload = self._build_payload(include_payload=False)
        validate_trust_audit_anchor_contract(payload)

    def test_validate_trust_audit_anchor_contract_should_pass_when_artifact_pending(self) -> None:
        payload = self._build_payload(include_payload=False, artifact_ready=False)
        self.assertEqual(
            set(payload["item"]["componentHashes"].keys()),
            set(TRUST_AUDIT_ANCHOR_BASE_COMPONENT_HASH_KEYS),
        )
        validate_trust_audit_anchor_contract(payload)

    def test_validate_trust_audit_anchor_contract_should_accept_release_readiness_manifest_hash(
        self,
    ) -> None:
        payload = self._build_payload(include_payload=False)
        payload["item"]["componentHashes"][
            "releaseReadinessManifestHash"
        ] = "release-readiness-manifest-hash"
        payload["item"]["artifactManifest"]["releaseReadinessArtifactSummary"] = {
            "artifactRef": "release-readiness-artifact",
            "manifestHash": "release-readiness-manifest-hash",
        }

        validate_trust_audit_anchor_contract(payload)

    def test_validate_trust_audit_anchor_contract_should_reject_release_readiness_hash_mismatch(
        self,
    ) -> None:
        payload = self._build_payload(include_payload=False)
        payload["item"]["componentHashes"][
            "releaseReadinessManifestHash"
        ] = "release-readiness-manifest-hash"
        payload["item"]["artifactManifest"]["releaseReadinessArtifactSummary"] = {
            "artifactRef": "release-readiness-artifact",
            "manifestHash": "other-manifest-hash",
        }

        with self.assertRaisesRegex(
            ValueError,
            "release_readiness_manifest_hash_mismatch",
        ):
            validate_trust_audit_anchor_contract(payload)

    def test_validate_trust_audit_anchor_contract_should_fail_on_missing_component_hash(self) -> None:
        payload = self._build_payload(include_payload=False)
        payload["item"]["componentHashes"].pop("kernelVersionHash")

        with self.assertRaises(ValueError) as ctx:
            validate_trust_audit_anchor_contract(payload)
        self.assertIn(
            "trust_audit_anchor_component_hashes_missing_keys:kernelVersionHash",
            str(ctx.exception),
        )

    def test_validate_trust_audit_anchor_contract_should_fail_on_pending_fake_anchor(self) -> None:
        payload = self._build_payload(include_payload=False, artifact_ready=False)
        payload["item"]["anchorHash"] = "fake-anchor"

        with self.assertRaisesRegex(ValueError, "pending_anchor_hash_forbidden"):
            validate_trust_audit_anchor_contract(payload)


if __name__ == "__main__":
    unittest.main()
