from __future__ import annotations

import unittest

from app.applications.fairness_case_contract import (
    CASE_FAIRNESS_AGGREGATIONS_KEYS,
    CASE_FAIRNESS_DETAIL_TOP_LEVEL_KEYS,
    CASE_FAIRNESS_FILTER_KEYS,
    CASE_FAIRNESS_ITEM_KEYS,
    CASE_FAIRNESS_LIST_TOP_LEVEL_KEYS,
    validate_case_fairness_detail_contract,
    validate_case_fairness_list_contract,
)


class FairnessCaseContractTests(unittest.TestCase):
    def _build_item(self, *, case_id: int) -> dict:
        return {
            "caseId": case_id,
            "dispatchType": "final",
            "traceId": f"trace-{case_id}",
            "workflowStatus": "completed",
            "updatedAt": "2026-04-19T00:00:00Z",
            "winner": "pro",
            "reviewRequired": False,
            "gateConclusion": "auto_passed",
            "errorCodes": [],
            "panelDisagreement": {
                "high": False,
                "ratio": 0.0,
                "ratioMax": 0.0,
                "reasons": [],
                "majorityWinner": "pro",
                "voteBySide": {"pro": 2, "con": 1},
                "runtimeProfiles": {"judgeA": {"profileId": "p-a"}},
            },
            "driftSummary": {
                "policyVersion": "v3-default",
                "latestRun": None,
                "thresholdBreaches": [],
                "driftBreaches": [],
                "hasThresholdBreach": False,
                "hasDriftBreach": False,
            },
            "shadowSummary": {
                "policyVersion": "v3-default",
                "latestRun": None,
                "benchmarkRunId": None,
                "breaches": [],
                "hasShadowBreach": False,
            },
            "challengeLink": {
                "latest": None,
                "hasOpenReview": False,
            },
        }

    def _build_list_payload(self) -> dict:
        items = [self._build_item(case_id=7001), self._build_item(case_id=7002)]
        return {
            "count": 2,
            "returned": 2,
            "items": items,
            "aggregations": {
                "totalMatched": 2,
                "reviewRequiredCount": 0,
                "openReviewCount": 0,
                "driftBreachCount": 0,
                "thresholdBreachCount": 0,
                "shadowBreachCount": 0,
                "panelHighDisagreementCount": 0,
                "withChallengeCount": 0,
                "gateConclusionCounts": {
                    "auto_passed": 2,
                    "review_required": 0,
                    "benchmark_attention_required": 0,
                    "unknown": 0,
                },
                "winnerCounts": {
                    "pro": 2,
                    "con": 0,
                    "draw": 0,
                    "unknown": 0,
                },
                "challengeStateCounts": {"none": 2},
                "policyVersionCounts": {"v3-default": 2, "unknown": 0},
            },
            "filters": {
                "status": None,
                "dispatchType": "final",
                "winner": None,
                "policyVersion": "v3-default",
                "hasDriftBreach": None,
                "hasThresholdBreach": None,
                "hasShadowBreach": None,
                "hasOpenReview": None,
                "gateConclusion": None,
                "challengeState": None,
                "sortBy": "updated_at",
                "sortOrder": "desc",
                "reviewRequired": None,
                "panelHighDisagreement": None,
                "offset": 0,
                "limit": 50,
            },
        }

    def test_validate_case_fairness_list_contract_should_pass_for_stable_payload(self) -> None:
        payload = self._build_list_payload()
        self.assertEqual(set(payload.keys()), set(CASE_FAIRNESS_LIST_TOP_LEVEL_KEYS))
        self.assertEqual(
            set(payload["items"][0].keys()),
            set(CASE_FAIRNESS_ITEM_KEYS),
        )
        self.assertEqual(
            set(payload["aggregations"].keys()),
            set(CASE_FAIRNESS_AGGREGATIONS_KEYS),
        )
        self.assertEqual(
            set(payload["filters"].keys()),
            set(CASE_FAIRNESS_FILTER_KEYS),
        )
        validate_case_fairness_list_contract(payload)

    def test_validate_case_fairness_detail_contract_should_pass_for_stable_payload(self) -> None:
        payload = {
            "caseId": 7001,
            "dispatchType": "final",
            "item": self._build_item(case_id=7001),
        }
        self.assertEqual(set(payload.keys()), set(CASE_FAIRNESS_DETAIL_TOP_LEVEL_KEYS))
        validate_case_fairness_detail_contract(payload)

    def test_validate_case_fairness_list_contract_should_fail_on_missing_item_key(self) -> None:
        payload = self._build_list_payload()
        payload["items"][0].pop("winner")

        with self.assertRaises(ValueError) as ctx:
            validate_case_fairness_list_contract(payload)
        self.assertIn("fairness_case_list_item_missing_keys", str(ctx.exception))

    def test_validate_case_fairness_list_contract_should_fail_on_aggregation_mismatch(self) -> None:
        payload = self._build_list_payload()
        payload["aggregations"]["gateConclusionCounts"]["auto_passed"] = 1

        with self.assertRaises(ValueError) as ctx:
            validate_case_fairness_list_contract(payload)
        self.assertIn("fairness_case_list_gate_counts_sum_mismatch", str(ctx.exception))

    def test_validate_case_fairness_detail_contract_should_fail_on_case_id_mismatch(self) -> None:
        payload = {
            "caseId": 7001,
            "dispatchType": "final",
            "item": self._build_item(case_id=7002),
        }

        with self.assertRaises(ValueError) as ctx:
            validate_case_fairness_detail_contract(payload)
        self.assertIn("fairness_case_detail_item_case_id_mismatch", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
