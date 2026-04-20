from __future__ import annotations

import unittest

from app.applications.trust_commitment_contract import (
    TRUST_COMMITMENT_ITEM_KEYS,
    TRUST_COMMITMENT_TOP_LEVEL_KEYS,
    validate_trust_commitment_contract,
)


class TrustCommitmentContractTests(unittest.TestCase):
    def _build_payload(self) -> dict:
        return {
            "caseId": 9301,
            "dispatchType": "final",
            "traceId": "trace-final-9301",
            "item": {
                "version": "trust-phaseA-case-commitment-v1",
                "caseId": 9301,
                "dispatchType": "final",
                "traceId": "trace-final-9301",
                "requestHash": "request_hash",
                "workflowHash": "workflow_hash",
                "reportHash": "report_hash",
                "attestationCommitmentHash": None,
                "commitmentHash": "commitment_hash",
            },
        }

    def test_validate_trust_commitment_contract_should_pass_for_stable_payload(self) -> None:
        payload = self._build_payload()
        self.assertEqual(set(payload.keys()), set(TRUST_COMMITMENT_TOP_LEVEL_KEYS))
        self.assertEqual(set(payload["item"].keys()), set(TRUST_COMMITMENT_ITEM_KEYS))
        validate_trust_commitment_contract(payload)

    def test_validate_trust_commitment_contract_should_fail_on_missing_item_key(self) -> None:
        payload = self._build_payload()
        payload["item"].pop("commitmentHash")

        with self.assertRaises(ValueError) as ctx:
            validate_trust_commitment_contract(payload)
        self.assertIn("trust_commitment_item_missing_keys:commitmentHash", str(ctx.exception))

    def test_validate_trust_commitment_contract_should_fail_on_dispatch_type_mismatch(self) -> None:
        payload = self._build_payload()
        payload["item"]["dispatchType"] = "phase"

        with self.assertRaises(ValueError) as ctx:
            validate_trust_commitment_contract(payload)
        self.assertIn("trust_commitment_item_dispatch_type_mismatch", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
