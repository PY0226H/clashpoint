from __future__ import annotations

import unittest

from app.applications.trust_challenge_review_contract import (
    TRUST_CHALLENGE_REVIEW_ITEM_KEYS,
    TRUST_CHALLENGE_REVIEW_TOP_LEVEL_KEYS,
    validate_trust_challenge_review_contract,
)


class TrustChallengeReviewContractTests(unittest.TestCase):
    def _build_payload(self) -> dict:
        return {
            "caseId": 9303,
            "dispatchType": "final",
            "traceId": "trace-final-9303",
            "item": {
                "version": "trust-phaseB-challenge-review-v1",
                "caseId": 9303,
                "traceId": "trace-final-9303",
                "challengeState": "open",
                "activeChallengeId": "challenge-9303",
                "totalChallenges": 1,
                "challenges": [{"challengeId": "challenge-9303"}],
                "timeline": [],
                "reviewState": "pending_review",
                "reviewRequired": True,
                "reviewDecisions": [],
                "challengeReasons": ["manual_challenge"],
                "alertSummary": {
                    "total": 1,
                    "raised": 1,
                    "acked": 0,
                    "resolved": 0,
                    "critical": 0,
                    "warning": 1,
                },
                "openAlertIds": ["alert-1"],
                "registryHash": "registry_hash",
            },
        }

    def test_validate_trust_challenge_review_contract_should_pass_for_stable_payload(
        self,
    ) -> None:
        payload = self._build_payload()
        self.assertEqual(set(payload.keys()), set(TRUST_CHALLENGE_REVIEW_TOP_LEVEL_KEYS))
        self.assertEqual(set(payload["item"].keys()), set(TRUST_CHALLENGE_REVIEW_ITEM_KEYS))
        validate_trust_challenge_review_contract(payload)

    def test_validate_trust_challenge_review_contract_should_fail_on_missing_item_key(
        self,
    ) -> None:
        payload = self._build_payload()
        payload["item"].pop("registryHash")

        with self.assertRaises(ValueError) as ctx:
            validate_trust_challenge_review_contract(payload)
        self.assertIn(
            "trust_challenge_review_item_missing_keys:registryHash",
            str(ctx.exception),
        )

    def test_validate_trust_challenge_review_contract_should_fail_on_total_mismatch(
        self,
    ) -> None:
        payload = self._build_payload()
        payload["item"]["totalChallenges"] = 2

        with self.assertRaises(ValueError) as ctx:
            validate_trust_challenge_review_contract(payload)
        self.assertIn(
            "trust_challenge_review_item_total_challenges_mismatch",
            str(ctx.exception),
        )


if __name__ == "__main__":
    unittest.main()
