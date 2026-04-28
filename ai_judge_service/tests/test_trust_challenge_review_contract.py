from __future__ import annotations

import unittest

from app.applications.trust_challenge_review_contract import (
    TRUST_CHALLENGE_REVIEW_ITEM_KEYS,
    TRUST_CHALLENGE_REVIEW_TOP_LEVEL_KEYS,
    build_trust_challenge_review_decision_sync,
    validate_trust_challenge_review_contract,
    validate_trust_challenge_review_decision_sync_contract,
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
                "challengeState": "under_internal_review",
                "activeChallengeId": "challenge-9303",
                "totalChallenges": 1,
                "challenges": [
                    {
                        "challengeId": "challenge-9303",
                        "currentState": "under_internal_review",
                    }
                ],
                "timeline": [
                    {
                        "eventSeq": 1,
                        "challengeId": "challenge-9303",
                        "state": "under_internal_review",
                    }
                ],
                "reviewState": "pending_review",
                "reviewRequired": True,
                "reviewDecisions": [],
                "reviewDecisionSync": {
                    "version": "trust-challenge-review-decision-sync-v1",
                    "syncState": "pending_review",
                    "result": "none",
                    "userVisibleStatus": "review_required",
                    "source": {
                        "originalCaseId": 9303,
                        "originalVerdictVersion": "v2-panel-arbiter-opinion",
                        "challengeId": "challenge-9303",
                        "reviewDecisionId": None,
                        "reviewDecisionEventSeq": None,
                        "reviewDecidedAt": None,
                        "decisionSource": "none",
                    },
                    "verdictEffect": {
                        "ledgerAction": "none",
                        "directWinnerWriteAllowed": False,
                        "requiresVerdictLedgerSource": False,
                        "drawVoteRequired": False,
                        "reviewRequired": True,
                    },
                    "nextStep": "await_review_decision",
                },
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

    def test_build_review_decision_sync_should_map_all_public_outcomes(self) -> None:
        cases = [
            (
                "verdict_upheld",
                "completed",
                "completed",
                "retain_original_verdict",
            ),
            (
                "verdict_overturned",
                "awaiting_verdict_source",
                "review_required",
                "await_revised_verdict_ledger",
            ),
            (
                "draw_after_review",
                "draw_pending_vote",
                "draw_pending_vote",
                "open_draw_vote",
            ),
            (
                "review_retained",
                "review_retained",
                "review_required",
                "retain_review_required",
            ),
        ]
        for decision, sync_state, visible_status, ledger_action in cases:
            with self.subTest(decision=decision):
                payload = build_trust_challenge_review_decision_sync(
                    case_id=9304,
                    challenge_state="challenge_closed",
                    review_state="approved",
                    workflow_status="callback_reported",
                    latest_challenge={
                        "challengeId": f"challenge-9304-{decision}",
                        "decision": decision,
                        "latestEventSeq": 7,
                        "decisionAt": "2026-04-26T00:00:00+00:00",
                    },
                    report_payload={
                        "verdictLedger": {"version": "v2-panel-arbiter-opinion"}
                    },
                )
                validate_trust_challenge_review_decision_sync_contract(payload)
                self.assertEqual(payload["result"], decision)
                self.assertEqual(payload["syncState"], sync_state)
                self.assertEqual(payload["userVisibleStatus"], visible_status)
                self.assertEqual(
                    payload["verdictEffect"]["ledgerAction"],
                    ledger_action,
                )
                self.assertFalse(
                    payload["verdictEffect"]["directWinnerWriteAllowed"]
                )
                self.assertEqual(payload["source"]["originalCaseId"], 9304)
                self.assertEqual(
                    payload["source"]["originalVerdictVersion"],
                    "v2-panel-arbiter-opinion",
                )
                self.assertTrue(payload["source"]["reviewDecisionId"])


if __name__ == "__main__":
    unittest.main()
