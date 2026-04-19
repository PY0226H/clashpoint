from __future__ import annotations

import unittest

from app.applications.fairness_dashboard_contract import (
    FAIRNESS_DASHBOARD_FILTER_KEYS,
    FAIRNESS_DASHBOARD_GATE_DISTRIBUTION_KEYS,
    FAIRNESS_DASHBOARD_OVERVIEW_KEYS,
    FAIRNESS_DASHBOARD_TOP_LEVEL_KEYS,
    FAIRNESS_DASHBOARD_TRENDS_KEYS,
    validate_fairness_dashboard_contract,
)


class FairnessDashboardContractTests(unittest.TestCase):
    def _build_payload(self) -> dict:
        return {
            "generatedAt": "2026-04-19T00:00:00Z",
            "overview": {
                "totalMatched": 2,
                "scannedCases": 2,
                "scanTruncated": False,
                "reviewRequiredCount": 1,
                "openReviewCount": 1,
                "panelHighDisagreementCount": 1,
                "driftBreachCount": 1,
                "thresholdBreachCount": 1,
                "shadowBreachCount": 1,
            },
            "gateDistribution": {
                "auto_passed": 1,
                "review_required": 0,
                "benchmark_attention_required": 1,
                "unknown": 0,
            },
            "trends": {
                "windowDays": 7,
                "caseDaily": [
                    {
                        "date": "2026-04-19",
                        "totalCases": 2,
                        "reviewRequiredCount": 1,
                        "openReviewCount": 1,
                        "benchmarkAttentionCount": 1,
                    }
                ],
                "benchmarkRuns": [],
                "shadowRuns": [],
            },
            "topRiskCases": [
                {
                    "caseId": 7001,
                    "dispatchType": "final",
                    "updatedAt": "2026-04-19T00:00:00Z",
                    "winner": "pro",
                    "gateConclusion": "benchmark_attention_required",
                    "reviewRequired": True,
                    "riskScore": 85,
                    "riskTags": ["shadow_breach"],
                    "panelDisagreementRatio": 0.2,
                    "hasOpenReview": True,
                    "policyVersion": "v3-default",
                }
            ],
            "filters": {
                "status": None,
                "dispatchType": "final",
                "winner": None,
                "policyVersion": "v3-default",
                "challengeState": None,
                "windowDays": 7,
                "topLimit": 10,
                "caseScanLimit": 200,
            },
        }

    def test_validate_fairness_dashboard_contract_should_pass_for_stable_payload(self) -> None:
        payload = self._build_payload()
        self.assertEqual(set(payload.keys()), set(FAIRNESS_DASHBOARD_TOP_LEVEL_KEYS))
        self.assertEqual(
            set(payload["overview"].keys()),
            set(FAIRNESS_DASHBOARD_OVERVIEW_KEYS),
        )
        self.assertEqual(
            set(payload["gateDistribution"].keys()),
            set(FAIRNESS_DASHBOARD_GATE_DISTRIBUTION_KEYS),
        )
        self.assertEqual(
            set(payload["trends"].keys()),
            set(FAIRNESS_DASHBOARD_TRENDS_KEYS),
        )
        self.assertEqual(set(payload["filters"].keys()), set(FAIRNESS_DASHBOARD_FILTER_KEYS))
        validate_fairness_dashboard_contract(payload)

    def test_validate_fairness_dashboard_contract_should_fail_on_missing_keys(self) -> None:
        payload = self._build_payload()
        payload["overview"].pop("openReviewCount")

        with self.assertRaises(ValueError) as ctx:
            validate_fairness_dashboard_contract(payload)
        self.assertIn("fairness_dashboard_overview_missing_keys", str(ctx.exception))

    def test_validate_fairness_dashboard_contract_should_fail_on_gate_sum_mismatch(self) -> None:
        payload = self._build_payload()
        payload["gateDistribution"]["auto_passed"] = 0
        payload["gateDistribution"]["review_required"] = 0

        with self.assertRaises(ValueError) as ctx:
            validate_fairness_dashboard_contract(payload)
        self.assertIn("fairness_dashboard_gate_distribution_sum_mismatch", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
