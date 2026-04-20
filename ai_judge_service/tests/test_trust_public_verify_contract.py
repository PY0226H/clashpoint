from __future__ import annotations

import unittest

from app.applications.trust_public_verify_contract import (
    TRUST_PUBLIC_VERIFY_AUDIT_ANCHOR_COMPONENT_HASH_KEYS,
    TRUST_PUBLIC_VERIFY_AUDIT_ANCHOR_KEYS,
    TRUST_PUBLIC_VERIFY_CASE_COMMITMENT_KEYS,
    TRUST_PUBLIC_VERIFY_CHALLENGE_REVIEW_KEYS,
    TRUST_PUBLIC_VERIFY_KERNEL_VERSION_KEYS,
    TRUST_PUBLIC_VERIFY_PAYLOAD_KEYS,
    TRUST_PUBLIC_VERIFY_TOP_LEVEL_KEYS,
    TRUST_PUBLIC_VERIFY_VERDICT_ATTESTATION_KEYS,
    validate_trust_public_verify_contract,
)


class TrustPublicVerifyContractTests(unittest.TestCase):
    def _build_payload(self) -> dict:
        return {
            "caseId": 9101,
            "dispatchType": "final",
            "traceId": "trace-final-9101",
            "verifyPayload": {
                "caseCommitment": {
                    "version": "trust-phaseA-case-commitment-v1",
                    "commitmentHash": "c_hash",
                    "requestHash": "r_hash",
                    "workflowHash": "w_hash",
                    "reportHash": "rp_hash",
                    "attestationCommitmentHash": "a_hash",
                },
                "verdictAttestation": {
                    "version": "trust-phaseA-verdict-attestation-v1",
                    "registryHash": "va_hash",
                    "verified": True,
                    "reason": "ok",
                    "mismatchComponents": [],
                    "attestationHashes": {
                        "commitmentHash": "ac_hash",
                        "verdictHash": "av_hash",
                        "auditHash": "aa_hash",
                    },
                },
                "challengeReview": {
                    "version": "trust-phaseB-challenge-review-v1",
                    "registryHash": "cr_hash",
                    "reviewState": "approved",
                    "reviewRequired": False,
                    "challengeState": "not_challenged",
                    "activeChallengeId": None,
                    "totalChallenges": 0,
                    "alertSummary": {
                        "openAlertCount": 0,
                        "criticalAlertCount": 0,
                    },
                    "challengeReasons": [],
                },
                "kernelVersion": {
                    "version": "trust-phaseA-kernel-version-v1",
                    "registryHash": "kv_registry_hash",
                    "kernelHash": "kv_kernel_hash",
                    "kernelVector": {
                        "judgeCoreVersion": "judge-core-v3",
                        "agentRuntimeVersion": "agent-runtime-v3",
                    },
                },
                "auditAnchor": {
                    "version": "trust-phaseA-audit-anchor-v1",
                    "anchorHash": "anchor_hash",
                    "componentHashes": {
                        "caseCommitmentHash": "c_hash",
                        "verdictAttestationHash": "va_hash",
                        "challengeReviewHash": "cr_hash",
                        "kernelVersionHash": "kv_registry_hash",
                    },
                },
            },
        }

    def test_validate_trust_public_verify_contract_should_pass_for_stable_payload(self) -> None:
        payload = self._build_payload()
        self.assertEqual(set(payload.keys()), set(TRUST_PUBLIC_VERIFY_TOP_LEVEL_KEYS))
        self.assertEqual(
            set(payload["verifyPayload"].keys()),
            set(TRUST_PUBLIC_VERIFY_PAYLOAD_KEYS),
        )
        self.assertEqual(
            set(payload["verifyPayload"]["caseCommitment"].keys()),
            set(TRUST_PUBLIC_VERIFY_CASE_COMMITMENT_KEYS),
        )
        self.assertEqual(
            set(payload["verifyPayload"]["verdictAttestation"].keys()),
            set(TRUST_PUBLIC_VERIFY_VERDICT_ATTESTATION_KEYS),
        )
        self.assertEqual(
            set(payload["verifyPayload"]["challengeReview"].keys()),
            set(TRUST_PUBLIC_VERIFY_CHALLENGE_REVIEW_KEYS),
        )
        self.assertEqual(
            set(payload["verifyPayload"]["kernelVersion"].keys()),
            set(TRUST_PUBLIC_VERIFY_KERNEL_VERSION_KEYS),
        )
        self.assertEqual(
            set(payload["verifyPayload"]["auditAnchor"].keys()),
            set(TRUST_PUBLIC_VERIFY_AUDIT_ANCHOR_KEYS),
        )
        self.assertEqual(
            set(payload["verifyPayload"]["auditAnchor"]["componentHashes"].keys()),
            set(TRUST_PUBLIC_VERIFY_AUDIT_ANCHOR_COMPONENT_HASH_KEYS),
        )
        validate_trust_public_verify_contract(payload)

    def test_validate_trust_public_verify_contract_should_fail_on_missing_verify_payload_key(
        self,
    ) -> None:
        payload = self._build_payload()
        payload["verifyPayload"].pop("kernelVersion")

        with self.assertRaises(ValueError) as ctx:
            validate_trust_public_verify_contract(payload)
        self.assertIn(
            "trust_public_verify_verify_payload_missing_keys:kernelVersion",
            str(ctx.exception),
        )

    def test_validate_trust_public_verify_contract_should_fail_on_anchor_component_hash_missing(
        self,
    ) -> None:
        payload = self._build_payload()
        payload["verifyPayload"]["auditAnchor"]["componentHashes"].pop("kernelVersionHash")

        with self.assertRaises(ValueError) as ctx:
            validate_trust_public_verify_contract(payload)
        self.assertIn(
            "trust_public_verify_audit_anchor_component_hashes_missing_keys:kernelVersionHash",
            str(ctx.exception),
        )


if __name__ == "__main__":
    unittest.main()
