from __future__ import annotations

import unittest

from app.applications.trust_challenge_public_contract import (
    TRUST_CHALLENGE_PUBLIC_TOP_LEVEL_KEYS,
    build_trust_challenge_public_status,
    find_trust_challenge_public_forbidden_keys,
    validate_trust_challenge_public_contract,
)


class TrustChallengePublicContractTests(unittest.TestCase):
    def _kernel_version(self) -> dict:
        return {
            "version": "trust-phaseA-kernel-version-v1",
            "kernelVector": {
                "policyVersion": "policy-v5",
                "promptVersion": "prompt-v5",
            },
            "kernelHash": "kernel-hash",
            "registryHash": "kernel-registry-hash",
        }

    def test_public_status_should_pass_for_eligible_final_case(self) -> None:
        payload = build_trust_challenge_public_status(
            case_id=9201,
            dispatch_type="final",
            trace_id="trace-9201",
            challenge_review={
                "challengeState": "not_challenged",
                "reviewState": "not_required",
                "reviewRequired": False,
                "totalChallenges": 0,
                "activeChallengeId": None,
                "challenges": [],
            },
            workflow_status="callback_reported",
            kernel_version=self._kernel_version(),
        )

        self.assertEqual(set(payload.keys()), set(TRUST_CHALLENGE_PUBLIC_TOP_LEVEL_KEYS))
        self.assertEqual(payload["eligibility"]["status"], "eligible")
        self.assertTrue(payload["eligibility"]["requestable"])
        self.assertIn("challenge.request", payload["allowedActions"])
        self.assertEqual(payload["blockers"], [])
        self.assertEqual(payload["policy"]["policyVersion"], "policy-v5")
        validate_trust_challenge_public_contract(payload)
        self.assertEqual(find_trust_challenge_public_forbidden_keys(payload), set())

    def test_public_status_should_block_duplicate_open_challenge(self) -> None:
        payload = build_trust_challenge_public_status(
            case_id=9202,
            dispatch_type="final",
            trace_id="trace-9202",
            challenge_review={
                "challengeState": "under_internal_review",
                "reviewState": "pending_review",
                "reviewRequired": True,
                "totalChallenges": 1,
                "activeChallengeId": "chlg-9202-1",
                "challenges": [
                    {
                        "challengeId": "chlg-9202-1",
                        "currentState": "under_internal_review",
                        "reasonCode": "manual_challenge",
                    }
                ],
            },
            workflow_status="review_required",
            kernel_version=self._kernel_version(),
        )

        self.assertEqual(payload["eligibility"]["status"], "under_review")
        self.assertEqual(payload["blockers"], ["challenge_duplicate_open"])
        self.assertNotIn("challenge.request", payload["allowedActions"])
        self.assertIn("review.view", payload["allowedActions"])
        validate_trust_challenge_public_contract(payload)

    def test_public_status_should_mark_closed_challenge_cacheable(self) -> None:
        payload = build_trust_challenge_public_status(
            case_id=9203,
            dispatch_type="final",
            trace_id="trace-9203",
            challenge_review={
                "challengeState": "challenge_closed",
                "reviewState": "approved",
                "reviewRequired": False,
                "totalChallenges": 1,
                "activeChallengeId": None,
                "challenges": [
                    {
                        "challengeId": "chlg-9203-1",
                        "currentState": "challenge_closed",
                        "decision": "verdict_upheld",
                        "reasonCode": "manual_challenge",
                    }
                ],
            },
            workflow_status="callback_reported",
            kernel_version=self._kernel_version(),
        )

        self.assertEqual(payload["eligibility"]["status"], "closed")
        self.assertEqual(payload["blockers"], ["challenge_review_already_closed"])
        self.assertEqual(payload["challenge"]["latestDecision"], "verdict_upheld")
        self.assertTrue(payload["cacheProfile"]["cacheable"])
        validate_trust_challenge_public_contract(payload)

    def test_public_status_should_use_stable_case_absent_and_policy_blockers(
        self,
    ) -> None:
        absent = build_trust_challenge_public_status(
            case_id=9204,
            dispatch_type="auto",
            trace_id=None,
            challenge_review=None,
            workflow_status=None,
            case_absent=True,
        )
        self.assertEqual(absent["eligibility"]["status"], "case_absent")
        self.assertEqual(absent["blockers"], ["challenge_case_absent"])
        self.assertIsNone(absent["traceId"])
        validate_trust_challenge_public_contract(absent)

        policy_disabled = build_trust_challenge_public_status(
            case_id=9205,
            dispatch_type="final",
            trace_id="trace-9205",
            challenge_review={
                "challengeState": "not_challenged",
                "reviewState": "not_required",
                "reviewRequired": False,
                "totalChallenges": 0,
                "challenges": [],
            },
            workflow_status="callback_reported",
            kernel_version=self._kernel_version(),
            policy_enabled=False,
        )
        self.assertEqual(policy_disabled["eligibility"]["status"], "not_eligible")
        self.assertEqual(policy_disabled["blockers"], ["challenge_policy_disabled"])
        validate_trust_challenge_public_contract(policy_disabled)

    def test_public_status_should_reject_secret_or_internal_locator_keys(self) -> None:
        payload = build_trust_challenge_public_status(
            case_id=9206,
            dispatch_type="final",
            trace_id="trace-9206",
            challenge_review={
                "challengeState": "not_challenged",
                "reviewState": "not_required",
                "reviewRequired": False,
                "totalChallenges": 0,
                "challenges": [],
            },
            workflow_status="callback_reported",
            kernel_version=self._kernel_version(),
        )
        payload["policy"]["provider"] = "mock"

        with self.assertRaises(ValueError) as ctx:
            validate_trust_challenge_public_contract(payload)
        self.assertIn("trust_challenge_public_forbidden_fields:provider", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
