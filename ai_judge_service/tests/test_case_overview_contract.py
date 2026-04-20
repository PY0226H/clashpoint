from __future__ import annotations

import unittest

from app.applications.case_overview_contract import (
    CASE_OVERVIEW_TOP_LEVEL_KEYS,
    validate_case_overview_contract,
)


class CaseOverviewContractTests(unittest.TestCase):
    def _build_payload(self) -> dict:
        return {
            "caseId": 9401,
            "workflow": {"status": "callback_reported"},
            "trace": {
                "traceId": "trace-final-9401",
                "status": "reported",
                "createdAt": "2026-04-20T00:00:00Z",
                "updatedAt": "2026-04-20T00:00:10Z",
            },
            "receipts": {
                "phase": None,
                "final": {"dispatchType": "final"},
            },
            "latestDispatchType": "final",
            "reportPayload": {"winner": "pro"},
            "verdictContract": {"winner": "pro", "needsDrawVote": False, "reviewRequired": False},
            "caseEvidence": {"hasCaseDossier": True},
            "winner": "pro",
            "needsDrawVote": False,
            "reviewRequired": False,
            "callbackStatus": "reported",
            "callbackError": None,
            "judgeCore": {"stage": "reported", "version": "v1", "eventSeq": 3},
            "events": [
                {
                    "eventSeq": 1,
                    "eventType": "queued",
                    "payload": {},
                    "createdAt": "2026-04-20T00:00:00Z",
                }
            ],
            "alerts": [],
            "replays": [
                {
                    "dispatchType": "final",
                    "traceId": "trace-final-9401",
                    "replayedAt": "2026-04-20T00:00:12Z",
                    "winner": "pro",
                    "needsDrawVote": False,
                    "provider": "mock",
                }
            ],
        }

    def test_validate_case_overview_contract_should_pass_for_stable_payload(self) -> None:
        payload = self._build_payload()
        self.assertEqual(set(payload.keys()), set(CASE_OVERVIEW_TOP_LEVEL_KEYS))
        validate_case_overview_contract(payload)

    def test_validate_case_overview_contract_should_fail_on_missing_top_key(self) -> None:
        payload = self._build_payload()
        payload.pop("caseEvidence")
        with self.assertRaises(ValueError) as ctx:
            validate_case_overview_contract(payload)
        self.assertIn("case_overview_missing_keys:caseEvidence", str(ctx.exception))

    def test_validate_case_overview_contract_should_fail_on_invalid_dispatch_type(self) -> None:
        payload = self._build_payload()
        payload["latestDispatchType"] = "auto"
        with self.assertRaises(ValueError) as ctx:
            validate_case_overview_contract(payload)
        self.assertIn("case_overview_latest_dispatch_type_invalid", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
