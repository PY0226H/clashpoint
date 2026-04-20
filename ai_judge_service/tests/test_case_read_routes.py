from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.applications.case_read_routes import (
    build_case_courtroom_read_model_payload,
    build_case_overview_payload,
    build_case_overview_replay_items,
)


@dataclass
class _DummyReplayRecord:
    dispatch_type: str | None
    trace_id: str | None
    created_at: datetime
    winner: str | None
    needs_draw_vote: bool | None
    provider: str | None


@dataclass
class _DummyTraceReplay:
    replayed_at: datetime
    winner: str | None
    needs_draw_vote: bool | None
    provider: str | None


@dataclass
class _DummyTrace:
    trace_id: str
    replays: list[Any]


class CaseReadRoutesTests(unittest.TestCase):
    def test_build_case_overview_replay_items_should_prefer_replay_records(self) -> None:
        records = [
            _DummyReplayRecord(
                dispatch_type="final",
                trace_id="trace-final-9501",
                created_at=datetime(2026, 4, 20, 0, 0, tzinfo=timezone.utc),
                winner="pro",
                needs_draw_vote=False,
                provider="mock",
            )
        ]
        payload = build_case_overview_replay_items(
            replay_records=records,
            trace=None,
        )
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["dispatchType"], "final")
        self.assertEqual(payload[0]["traceId"], "trace-final-9501")

    def test_build_case_overview_replay_items_should_fallback_to_trace_replays(self) -> None:
        trace = _DummyTrace(
            trace_id="trace-case-9502",
            replays=[
                _DummyTraceReplay(
                    replayed_at=datetime(2026, 4, 20, 0, 1, tzinfo=timezone.utc),
                    winner="draw",
                    needs_draw_vote=True,
                    provider="mock",
                )
            ],
        )
        payload = build_case_overview_replay_items(
            replay_records=[],
            trace=trace,
        )
        self.assertEqual(len(payload), 1)
        self.assertIsNone(payload[0]["dispatchType"])
        self.assertEqual(payload[0]["traceId"], "trace-case-9502")

    def test_build_case_overview_payload_should_keep_contract_shape(self) -> None:
        payload = build_case_overview_payload(
            case_id=9503,
            workflow={"status": "callback_reported"},
            trace=None,
            receipts={"phase": None, "final": {"dispatchType": "final"}},
            latest_dispatch_type="final",
            report_payload={"winner": "pro"},
            verdict_contract={"winner": "pro"},
            case_evidence={"hasCaseDossier": True},
            winner="pro",
            needs_draw_vote=False,
            review_required=False,
            callback_status="reported",
            callback_error=None,
            judge_core={"stage": "reported", "version": "v1", "eventSeq": 2},
            events=[],
            alerts=[],
            replays=[],
        )
        self.assertEqual(payload["caseId"], 9503)
        self.assertEqual(payload["latestDispatchType"], "final")
        self.assertIn("caseEvidence", payload)
        self.assertIn("replays", payload)

    def test_build_case_courtroom_read_model_payload_should_keep_contract_shape(self) -> None:
        payload = build_case_courtroom_read_model_payload(
            case_id=9504,
            dispatch_type="final",
            trace_id="trace-final-9504",
            workflow={"status": "callback_reported"},
            judge_core={"stage": "reported", "version": "v1", "eventSeq": 3},
            callback_status="reported",
            callback_error=None,
            report_payload={
                "winner": "pro",
                "reviewRequired": False,
                "needsDrawVote": False,
                "debateSummary": "summary",
                "sideAnalysis": {"pro": "p", "con": "c"},
                "verdictReason": "reason",
            },
            courtroom={"recorder": {}, "claim": {}, "evidence": {}},
            events=[{"eventSeq": 1}],
            event_count=5,
            alerts=[{"alertId": "a1"}],
            include_events=False,
            include_alerts=True,
            alert_limit=200,
        )
        self.assertEqual(payload["caseId"], 9504)
        self.assertEqual(payload["dispatchType"], "final")
        self.assertEqual(payload["eventCount"], 5)
        self.assertEqual(payload["events"], [])
        self.assertEqual(payload["filters"]["alertLimit"], 200)
        self.assertTrue(payload["filters"]["includeAlerts"])


if __name__ == "__main__":
    unittest.main()
