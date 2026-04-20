from __future__ import annotations

import unittest

from app.applications.trust_challenge_queue_contract import (
    TRUST_CHALLENGE_QUEUE_CHALLENGE_REVIEW_KEYS,
    TRUST_CHALLENGE_QUEUE_FILTER_KEYS,
    TRUST_CHALLENGE_QUEUE_ITEM_KEYS,
    TRUST_CHALLENGE_QUEUE_PRIORITY_PROFILE_KEYS,
    TRUST_CHALLENGE_QUEUE_REVIEW_KEYS,
    TRUST_CHALLENGE_QUEUE_TOP_LEVEL_KEYS,
    validate_trust_challenge_queue_contract,
)


class TrustChallengeQueueContractTests(unittest.TestCase):
    def _build_payload(self) -> dict:
        return {
            "count": 1,
            "returned": 1,
            "scanned": 1,
            "skipped": 0,
            "errorCount": 0,
            "items": [
                {
                    "caseId": 9201,
                    "dispatchType": "final",
                    "traceId": "trace-final-9201",
                    "workflow": {
                        "caseId": 9201,
                        "dispatchType": "final",
                        "traceId": "trace-final-9201",
                        "status": "callback_reported",
                        "scopeId": "9201",
                        "sessionId": "room-9201",
                        "idempotencyKey": "final:9201",
                        "rubricVersion": "v1",
                        "judgePolicyVersion": "v3-default",
                        "topicDomain": "general",
                        "retrievalProfile": "default",
                        "createdAt": "2026-04-20T00:00:00Z",
                        "updatedAt": "2026-04-20T00:00:00Z",
                    },
                    "trace": {
                        "status": "success",
                        "callbackStatus": "reported",
                        "callbackError": None,
                        "updatedAt": "2026-04-20T00:00:00Z",
                    },
                    "challengeReview": {
                        "state": "under_review",
                        "activeChallengeId": "chlg-9201-aaaa",
                        "totalChallenges": 1,
                        "reviewState": "pending_review",
                        "reviewRequired": True,
                        "challengeReasons": ["manual_challenge"],
                        "alertSummary": {"critical": 0},
                        "openAlertIds": [],
                        "timeline": [],
                    },
                    "priorityProfile": {
                        "score": 56,
                        "level": "medium",
                        "tags": ["open_challenge"],
                        "ageMinutes": 30,
                        "slaBucket": "normal",
                        "challengeState": "under_review",
                        "reviewState": "pending_review",
                        "reviewRequired": True,
                        "totalChallenges": 1,
                        "openAlertCount": 0,
                    },
                    "review": {
                        "required": True,
                        "state": "pending_review",
                        "workflowStatus": "callback_reported",
                        "detailPath": "/internal/judge/review/cases/9201",
                    },
                    "actionHints": ["trust.challenge.decide"],
                    "actionPaths": {
                        "requestChallengePath": "/internal/judge/cases/9201/trust/challenges/request",
                        "decisionPath": "/internal/judge/cases/9201/trust/challenges/chlg-9201-aaaa/decision",
                        "reviewDetailPath": "/internal/judge/review/cases/9201",
                    },
                }
            ],
            "errors": [],
            "filters": {
                "status": None,
                "dispatchType": "auto",
                "challengeState": "open",
                "reviewState": None,
                "priorityLevel": None,
                "slaBucket": None,
                "hasOpenAlert": None,
                "sortBy": "priority_score",
                "sortOrder": "desc",
                "scanLimit": 500,
                "offset": 0,
                "limit": 50,
            },
        }

    def test_validate_trust_challenge_queue_contract_should_pass_for_stable_payload(self) -> None:
        payload = self._build_payload()
        self.assertEqual(set(payload.keys()), set(TRUST_CHALLENGE_QUEUE_TOP_LEVEL_KEYS))
        self.assertEqual(
            set(payload["items"][0].keys()),
            set(TRUST_CHALLENGE_QUEUE_ITEM_KEYS),
        )
        self.assertEqual(
            set(payload["items"][0]["challengeReview"].keys()),
            set(TRUST_CHALLENGE_QUEUE_CHALLENGE_REVIEW_KEYS),
        )
        self.assertEqual(
            set(payload["items"][0]["priorityProfile"].keys()),
            set(TRUST_CHALLENGE_QUEUE_PRIORITY_PROFILE_KEYS),
        )
        self.assertEqual(
            set(payload["items"][0]["review"].keys()),
            set(TRUST_CHALLENGE_QUEUE_REVIEW_KEYS),
        )
        self.assertEqual(
            set(payload["filters"].keys()),
            set(TRUST_CHALLENGE_QUEUE_FILTER_KEYS),
        )
        validate_trust_challenge_queue_contract(payload)

    def test_validate_trust_challenge_queue_contract_should_fail_on_missing_item_key(self) -> None:
        payload = self._build_payload()
        payload["items"][0].pop("priorityProfile")

        with self.assertRaises(ValueError) as ctx:
            validate_trust_challenge_queue_contract(payload)
        self.assertIn("trust_challenge_queue_item_missing_keys:priorityProfile", str(ctx.exception))

    def test_validate_trust_challenge_queue_contract_should_fail_on_filter_sort_order(self) -> None:
        payload = self._build_payload()
        payload["filters"]["sortOrder"] = "invalid"

        with self.assertRaises(ValueError) as ctx:
            validate_trust_challenge_queue_contract(payload)
        self.assertIn("trust_challenge_queue_filters_sort_order_invalid", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
