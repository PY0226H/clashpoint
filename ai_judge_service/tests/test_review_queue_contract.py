from __future__ import annotations

import unittest

from app.applications.review_queue_contract import (
    validate_courtroom_drilldown_bundle_contract,
    validate_evidence_claim_ops_queue_contract,
)


class ReviewQueueContractTests(unittest.TestCase):
    def _build_courtroom_payload(self) -> dict:
        return {
            "count": 1,
            "returned": 1,
            "scanned": 1,
            "skipped": 0,
            "errorCount": 0,
            "items": [
                {
                    "caseId": 7001,
                    "dispatchType": "final",
                    "traceId": "trace-7001",
                    "workflow": {},
                    "winner": "pro",
                    "reviewRequired": True,
                    "needsDrawVote": False,
                    "callbackStatus": "reported",
                    "callbackError": None,
                    "riskProfile": {"level": "high"},
                    "drilldown": {},
                    "actionHints": ["review.queue.decide"],
                    "detailPath": "/internal/judge/cases/7001/courtroom-read-model",
                }
            ],
            "errors": [],
            "aggregations": {
                "totalConflictPairCount": 1,
                "totalUnansweredClaimCount": 1,
                "totalDecisiveEvidenceCount": 1,
                "totalPivotalMomentCount": 1,
                "reviewRequiredCount": 1,
                "highRiskCount": 1,
            },
            "filters": {
                "status": None,
                "dispatchType": "auto",
                "winner": None,
                "reviewRequired": None,
                "riskLevel": None,
                "slaBucket": None,
                "updatedFrom": None,
                "updatedTo": None,
                "sortBy": "risk_score",
                "sortOrder": "desc",
                "scanLimit": 500,
                "offset": 0,
                "limit": 50,
                "claimPreviewLimit": 10,
                "evidencePreviewLimit": 10,
                "panelPreviewLimit": 10,
            },
            "notes": ["read_only"],
        }

    def _build_evidence_payload(self) -> dict:
        return {
            "count": 1,
            "returned": 1,
            "scanned": 1,
            "skipped": 0,
            "errorCount": 0,
            "items": [
                {
                    "caseId": 7002,
                    "dispatchType": "final",
                    "traceId": "trace-7002",
                    "workflow": {},
                    "winner": "con",
                    "reviewRequired": False,
                    "needsDrawVote": False,
                    "callbackStatus": "reported",
                    "callbackError": None,
                    "riskProfile": {"level": "medium"},
                    "courtroomSummary": {},
                    "claimEvidenceProfile": {"reliability": {"level": "high"}},
                    "actionHints": ["evidence.upgrade_reliability"],
                    "detailPath": "/internal/judge/cases/7002/courtroom-read-model",
                }
            ],
            "errors": [],
            "aggregations": {
                "riskLevelCounts": {"high": 0, "medium": 1, "low": 0},
                "reliabilityLevelCounts": {
                    "high": 1,
                    "medium": 0,
                    "low": 0,
                    "unknown": 0,
                },
                "conflictCaseCount": 0,
                "unansweredCaseCount": 0,
            },
            "filters": {
                "status": None,
                "dispatchType": "final",
                "winner": None,
                "reviewRequired": None,
                "riskLevel": None,
                "slaBucket": None,
                "reliabilityLevel": None,
                "hasConflict": None,
                "hasUnansweredClaim": None,
                "updatedFrom": None,
                "updatedTo": None,
                "sortBy": "risk_score",
                "sortOrder": "desc",
                "scanLimit": 500,
                "offset": 0,
                "limit": 50,
            },
        }

    def test_validate_courtroom_drilldown_bundle_contract_should_pass(self) -> None:
        validate_courtroom_drilldown_bundle_contract(self._build_courtroom_payload())

    def test_validate_courtroom_drilldown_bundle_contract_should_fail_on_missing_key(self) -> None:
        payload = self._build_courtroom_payload()
        payload["items"][0].pop("riskProfile")

        with self.assertRaises(ValueError) as ctx:
            validate_courtroom_drilldown_bundle_contract(payload)
        self.assertIn("courtroom_drilldown_bundle_item_missing_keys", str(ctx.exception))

    def test_validate_evidence_claim_ops_queue_contract_should_pass(self) -> None:
        validate_evidence_claim_ops_queue_contract(self._build_evidence_payload())

    def test_validate_evidence_claim_ops_queue_contract_should_fail_on_counts(self) -> None:
        payload = self._build_evidence_payload()
        payload["returned"] = 2

        with self.assertRaises(ValueError) as ctx:
            validate_evidence_claim_ops_queue_contract(payload)
        self.assertIn("evidence_claim_ops_queue_returned_count_mismatch", str(ctx.exception))

    def test_validate_evidence_claim_ops_queue_contract_should_fail_on_reliability_shape(self) -> None:
        payload = self._build_evidence_payload()
        payload["aggregations"]["reliabilityLevelCounts"].pop("unknown")

        with self.assertRaises(ValueError) as ctx:
            validate_evidence_claim_ops_queue_contract(payload)
        self.assertIn(
            "evidence_claim_ops_queue_reliability_level_counts_missing_keys",
            str(ctx.exception),
        )


if __name__ == "__main__":
    unittest.main()
