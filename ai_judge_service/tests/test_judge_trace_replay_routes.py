from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import datetime, timezone

from app.applications.judge_trace_replay_routes import (
    build_replay_reports_list_payload,
    build_replay_route_payload,
    build_trace_route_payload,
    build_trace_route_replay_items,
    choose_replay_dispatch_receipt,
    extract_replay_request_snapshot,
    normalize_replay_dispatch_type,
    resolve_replay_trace_id,
)


@dataclass
class _ReplayRow:
    created_at: datetime
    winner: str
    needs_draw_vote: bool
    provider: str


@dataclass
class _TraceReplayRow:
    replayed_at: datetime
    winner: str
    needs_draw_vote: bool
    provider: str


@dataclass
class _TraceRow:
    job_id: int
    trace_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    callback_status: str | None
    callback_error: str | None
    request: dict
    response: dict
    replays: list[_TraceReplayRow]


@dataclass
class _Receipt:
    trace_id: str
    request: dict


class JudgeTraceReplayRoutesTests(unittest.TestCase):
    def test_normalize_replay_dispatch_type_should_validate_values(self) -> None:
        self.assertEqual(normalize_replay_dispatch_type("auto"), "auto")
        self.assertEqual(normalize_replay_dispatch_type(" FINAL "), "final")
        with self.assertRaises(ValueError):
            normalize_replay_dispatch_type("invalid")

    def test_choose_replay_dispatch_receipt_should_prefer_final_on_auto(self) -> None:
        final_receipt = object()
        phase_receipt = object()
        dispatch_type, receipt = choose_replay_dispatch_receipt(
            dispatch_type="auto",
            final_receipt=final_receipt,
            phase_receipt=phase_receipt,
        )
        self.assertEqual(dispatch_type, "final")
        self.assertIs(receipt, final_receipt)

        dispatch_type, receipt = choose_replay_dispatch_receipt(
            dispatch_type="auto",
            final_receipt=None,
            phase_receipt=phase_receipt,
        )
        self.assertEqual(dispatch_type, "phase")
        self.assertIs(receipt, phase_receipt)

    def test_extract_and_resolve_trace_id_should_use_receipt_or_snapshot(self) -> None:
        receipt = _Receipt(trace_id="trace-1", request={"traceId": "trace-2"})
        snapshot = extract_replay_request_snapshot(receipt)
        self.assertEqual(snapshot["traceId"], "trace-2")
        trace_id = resolve_replay_trace_id(receipt=receipt, request_snapshot=snapshot)
        self.assertEqual(trace_id, "trace-1")

        trace_id_fallback = resolve_replay_trace_id(
            receipt=_Receipt(trace_id="", request={"traceId": "trace-3"}),
            request_snapshot={"traceId": "trace-3"},
        )
        self.assertEqual(trace_id_fallback, "trace-3")

    def test_build_trace_route_replay_items_should_support_fact_and_trace_fallback(self) -> None:
        now = datetime.now(timezone.utc)
        fact_items = build_trace_route_replay_items(
            replay_records=[
                _ReplayRow(
                    created_at=now,
                    winner="pro",
                    needs_draw_vote=False,
                    provider="mock",
                )
            ],
            trace_record=None,
        )
        self.assertEqual(len(fact_items), 1)
        self.assertEqual(fact_items[0]["winner"], "pro")
        self.assertIn("replayedAt", fact_items[0])

        trace_record = _TraceRow(
            job_id=1001,
            trace_id="trace-1001",
            status="reported",
            created_at=now,
            updated_at=now,
            callback_status="reported",
            callback_error=None,
            request={},
            response={},
            replays=[
                _TraceReplayRow(
                    replayed_at=now,
                    winner="con",
                    needs_draw_vote=False,
                    provider="mock",
                )
            ],
        )
        trace_items = build_trace_route_replay_items(
            replay_records=[],
            trace_record=trace_record,
        )
        self.assertEqual(len(trace_items), 1)
        self.assertEqual(trace_items[0]["winner"], "con")

    def test_build_trace_route_payload_should_keep_summary_and_role_nodes(self) -> None:
        now = datetime.now(timezone.utc)
        record = _TraceRow(
            job_id=1002,
            trace_id="trace-1002",
            status="reported",
            created_at=now,
            updated_at=now,
            callback_status="reported",
            callback_error=None,
            request={"k": "v"},
            response={"ok": True},
            replays=[],
        )
        payload = build_trace_route_payload(
            record=record,
            report_summary={
                "payload": {"winner": "pro"},
                "roleNodes": [{"role": "clerk"}],
            },
            verdict_contract={"winner": "pro"},
            replay_items=[{"winner": "pro"}],
        )
        self.assertEqual(payload["caseId"], 1002)
        self.assertEqual(payload["roleNodes"][0]["role"], "clerk")
        self.assertEqual(payload["verdictContract"]["winner"], "pro")
        self.assertEqual(payload["replays"][0]["winner"], "pro")

    def test_build_replay_route_payload_should_return_stable_contract(self) -> None:
        now = datetime.now(timezone.utc)
        payload = build_replay_route_payload(
            case_id=1003,
            dispatch_type="final",
            replayed_at=now,
            report_payload={"winner": "pro"},
            verdict_contract={"winner": "pro"},
            winner="pro",
            needs_draw_vote=False,
            trace_id="trace-1003",
            judge_core_stage="replay_computed",
            judge_core_version="v1",
        )
        self.assertEqual(payload["caseId"], 1003)
        self.assertEqual(payload["dispatchType"], "final")
        self.assertEqual(payload["winner"], "pro")
        self.assertEqual(payload["traceId"], "trace-1003")
        self.assertEqual(payload["judgeCoreStage"], "replay_computed")

    def test_build_replay_reports_list_payload_should_keep_filter_shape(self) -> None:
        now = datetime.now(timezone.utc)
        payload = build_replay_reports_list_payload(
            items=[{"caseId": 1}],
            status="reported",
            winner="pro",
            callback_status="reported",
            trace_id="trace-1",
            created_after=now,
            created_before=now,
            has_audit_alert=False,
            limit=20,
            include_report=True,
        )
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["caseId"], 1)
        self.assertEqual(payload["filters"]["winner"], "pro")
        self.assertTrue(payload["filters"]["createdAfter"].endswith("+00:00"))


if __name__ == "__main__":
    unittest.main()
