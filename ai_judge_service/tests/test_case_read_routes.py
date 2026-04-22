from __future__ import annotations

import asyncio
import unittest
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.applications.case_read_routes import (
    CaseReadRouteError,
    build_case_courtroom_read_model_payload,
    build_case_overview_payload,
    build_case_overview_replay_items,
    build_case_overview_route_payload,
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
    def test_build_case_overview_route_payload_should_raise_404_when_case_missing(self) -> None:
        with self.assertRaises(CaseReadRouteError) as ctx:
            asyncio.run(
                build_case_overview_route_payload(
                    case_id=9601,
                    workflow_get_job=lambda **kwargs: asyncio.sleep(0, result=None),
                    workflow_list_events=lambda **kwargs: asyncio.sleep(0, result=[]),
                    get_dispatch_receipt=lambda **kwargs: asyncio.sleep(0, result=None),
                    trace_get=lambda case_id: None,
                    list_replay_records=lambda **kwargs: asyncio.sleep(0, result=[]),
                    list_audit_alerts=lambda **kwargs: asyncio.sleep(0, result=[]),
                    get_claim_ledger_record=lambda **kwargs: asyncio.sleep(0, result=None),
                    build_verdict_contract=lambda report_payload: {},
                    build_case_evidence_view=lambda **kwargs: {},
                    build_judge_core_view=lambda **kwargs: None,
                    build_case_overview_replay_items=lambda **kwargs: [],
                    build_case_overview_payload=lambda **kwargs: {},
                    serialize_workflow_job=lambda item: {},
                    serialize_dispatch_receipt=lambda item: {},
                    serialize_alert_item=lambda item: {},
                )
            )
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "case_not_found")

    def test_build_case_overview_route_payload_should_build_payload(self) -> None:
        created_at = datetime(2026, 4, 21, 0, 0, tzinfo=timezone.utc)
        trace = _DummyTrace(
            trace_id="trace-9602",
            replays=[],
        )
        trace.status = "reported"
        trace.created_at = created_at
        trace.updated_at = created_at
        trace.report_summary = {"payload": {"winner": "pro"}, "callbackStatus": "reported"}
        trace.callback_status = "reported"
        trace.callback_error = None

        workflow_job = type("Job", (), {"job_id": 9602})()
        workflow_event = type(
            "Evt",
            (),
            {
                "event_seq": 1,
                "event_type": "judge.reported",
                "payload": {"status": "reported"},
                "created_at": created_at,
            },
        )()
        phase_receipt = type("Receipt", (), {"response": {"winner": "con"}})()
        final_receipt = type("Receipt", (), {"response": {"reportPayload": {"winner": "pro"}}})()

        payload = asyncio.run(
            build_case_overview_route_payload(
                case_id=9602,
                workflow_get_job=lambda **kwargs: asyncio.sleep(0, result=workflow_job),
                workflow_list_events=lambda **kwargs: asyncio.sleep(0, result=[workflow_event]),
                get_dispatch_receipt=lambda **kwargs: asyncio.sleep(
                    0,
                    result=(final_receipt if kwargs.get("dispatch_type") == "final" else phase_receipt),
                ),
                trace_get=lambda case_id: trace,
                list_replay_records=lambda **kwargs: asyncio.sleep(0, result=[]),
                list_audit_alerts=lambda **kwargs: asyncio.sleep(0, result=[{"alert_id": "a1"}]),
                get_claim_ledger_record=lambda **kwargs: asyncio.sleep(0, result={"dispatchType": "final"}),
                build_verdict_contract=lambda report_payload: {
                    "winner": report_payload.get("winner"),
                    "needsDrawVote": False,
                    "reviewRequired": False,
                },
                build_case_evidence_view=lambda **kwargs: {"hasCaseDossier": True},
                build_judge_core_view=lambda **kwargs: {"stage": "reported", "version": "v1"},
                build_case_overview_replay_items=lambda **kwargs: [{"traceId": "trace-9602"}],
                build_case_overview_payload=lambda **kwargs: dict(kwargs),
                serialize_workflow_job=lambda item: {"jobId": item.job_id},
                serialize_dispatch_receipt=lambda item: {"hasResponse": bool(getattr(item, "response", {}))},
                serialize_alert_item=lambda item: {"alertId": item["alert_id"]},
            )
        )

        self.assertEqual(payload["case_id"], 9602)
        self.assertEqual(payload["winner"], "pro")
        self.assertEqual(payload["latest_dispatch_type"], "final")
        self.assertEqual(payload["callback_status"], "reported")
        self.assertEqual(payload["workflow"]["jobId"], 9602)
        self.assertEqual(len(payload["events"]), 1)
        self.assertEqual(payload["alerts"][0]["alertId"], "a1")

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
