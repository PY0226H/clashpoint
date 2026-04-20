from __future__ import annotations

import unittest

from app.applications.trust_verdict_attestation_contract import (
    TRUST_VERDICT_ATTESTATION_ITEM_KEYS,
    TRUST_VERDICT_ATTESTATION_TOP_LEVEL_KEYS,
    validate_trust_verdict_attestation_contract,
)


class TrustVerdictAttestationContractTests(unittest.TestCase):
    def _build_payload(self) -> dict:
        return {
            "caseId": 9302,
            "dispatchType": "final",
            "traceId": "trace-final-9302",
            "item": {
                "version": "trust-phaseA-verdict-attestation-v1",
                "caseId": 9302,
                "dispatchType": "final",
                "traceId": "trace-final-9302",
                "attestation": {},
                "verified": True,
                "reason": "ok",
                "mismatchComponents": [],
                "registryHash": "registry_hash",
            },
        }

    def test_validate_trust_verdict_attestation_contract_should_pass_for_stable_payload(
        self,
    ) -> None:
        payload = self._build_payload()
        self.assertEqual(set(payload.keys()), set(TRUST_VERDICT_ATTESTATION_TOP_LEVEL_KEYS))
        self.assertEqual(set(payload["item"].keys()), set(TRUST_VERDICT_ATTESTATION_ITEM_KEYS))
        validate_trust_verdict_attestation_contract(payload)

    def test_validate_trust_verdict_attestation_contract_should_fail_on_missing_item_key(
        self,
    ) -> None:
        payload = self._build_payload()
        payload["item"].pop("registryHash")

        with self.assertRaises(ValueError) as ctx:
            validate_trust_verdict_attestation_contract(payload)
        self.assertIn(
            "trust_verdict_attestation_item_missing_keys:registryHash",
            str(ctx.exception),
        )

    def test_validate_trust_verdict_attestation_contract_should_fail_on_verified_not_bool(
        self,
    ) -> None:
        payload = self._build_payload()
        payload["item"]["verified"] = "yes"

        with self.assertRaises(ValueError) as ctx:
            validate_trust_verdict_attestation_contract(payload)
        self.assertIn("trust_verdict_attestation_item_verified_not_bool", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
