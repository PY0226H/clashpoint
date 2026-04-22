from __future__ import annotations

import unittest

from app.applications.courtroom_read_model_contract import (
    COURTROOM_READ_MODEL_TOP_LEVEL_KEYS,
    validate_courtroom_read_model_contract,
)


class CourtroomReadModelContractTests(unittest.TestCase):
    def _build_payload(self) -> dict:
        return {
            "caseId": 9402,
            "dispatchType": "final",
            "traceId": "trace-final-9402",
            "generatedAt": "2026-04-20T00:00:00Z",
            "workflow": {"status": "callback_reported"},
            "judgeCore": {"stage": "reported", "version": "v1", "eventSeq": 3},
            "callback": {"status": "reported", "error": None},
            "report": {
                "winner": "pro",
                "reviewRequired": False,
                "needsDrawVote": False,
                "debateSummary": "summary",
                "sideAnalysis": {"pro": "p", "con": "c"},
                "verdictReason": "reason",
            },
            "courtroom": {
                "recorder": {"caseDossier": {}},
                "claim": {"claimGraph": {}},
                "evidence": {"evidenceLedger": {}},
                "panel": {"panelDecisions": {}},
                "fairness": {"summary": {}},
                "opinion": {"sideAnalysis": {"pro": [], "con": []}},
                "governance": {
                    "policyVersion": "v3-default",
                    "promptVersion": "promptset-v3",
                    "toolsetVersion": "toolset-v3",
                },
            },
            "events": [],
            "eventCount": 2,
            "alerts": [],
            "filters": {
                "dispatchType": "final",
                "includeEvents": False,
                "includeAlerts": True,
                "alertLimit": 200,
            },
        }

    def test_validate_courtroom_read_model_contract_should_pass_for_stable_payload(
        self,
    ) -> None:
        payload = self._build_payload()
        self.assertEqual(set(payload.keys()), set(COURTROOM_READ_MODEL_TOP_LEVEL_KEYS))
        validate_courtroom_read_model_contract(payload)

    def test_validate_courtroom_read_model_contract_should_fail_on_missing_top_key(
        self,
    ) -> None:
        payload = self._build_payload()
        payload.pop("courtroom")
        with self.assertRaises(ValueError) as ctx:
            validate_courtroom_read_model_contract(payload)
        self.assertIn("courtroom_read_model_missing_keys:courtroom", str(ctx.exception))

    def test_validate_courtroom_read_model_contract_should_fail_on_invalid_dispatch_type(
        self,
    ) -> None:
        payload = self._build_payload()
        payload["dispatchType"] = "auto"
        with self.assertRaises(ValueError) as ctx:
            validate_courtroom_read_model_contract(payload)
        self.assertIn("courtroom_read_model_dispatch_type_invalid", str(ctx.exception))

    def test_validate_courtroom_read_model_contract_should_fail_when_courtroom_lacks_six_object_keys(
        self,
    ) -> None:
        payload = self._build_payload()
        payload["courtroom"]["claim"].pop("claimGraph")
        with self.assertRaises(ValueError) as ctx:
            validate_courtroom_read_model_contract(payload)
        self.assertIn(
            "courtroom_read_model_courtroom_claim_missing_keys:claimGraph",
            str(ctx.exception),
        )


if __name__ == "__main__":
    unittest.main()
