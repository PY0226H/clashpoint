from __future__ import annotations

import unittest
from dataclasses import dataclass
from typing import Any

from app.applications.trust_read_routes import (
    build_trust_item_route_payload,
    build_trust_public_verify_route_payload,
    build_trust_report_context_from_receipt,
    choose_trust_read_dispatch_receipt,
    normalize_trust_read_dispatch_type,
)


@dataclass
class _DummyReceipt:
    request: dict[str, Any] | None
    response: dict[str, Any] | None
    trace_id: str | None


class TrustReadRoutesTests(unittest.TestCase):
    def test_normalize_trust_read_dispatch_type_should_validate_values(self) -> None:
        self.assertEqual(normalize_trust_read_dispatch_type("auto"), "auto")
        self.assertEqual(normalize_trust_read_dispatch_type(" FINAL "), "final")
        self.assertEqual(normalize_trust_read_dispatch_type("phase"), "phase")
        with self.assertRaises(ValueError) as ctx:
            normalize_trust_read_dispatch_type("unknown")
        self.assertEqual(str(ctx.exception), "invalid_dispatch_type")

    def test_choose_trust_read_dispatch_receipt_should_follow_auto_priority(self) -> None:
        final_receipt = _DummyReceipt(request={}, response={}, trace_id="trace-final")
        phase_receipt = _DummyReceipt(request={}, response={}, trace_id="trace-phase")
        dispatch_type, chosen = choose_trust_read_dispatch_receipt(
            dispatch_type="auto",
            final_receipt=final_receipt,
            phase_receipt=phase_receipt,
        )
        self.assertEqual(dispatch_type, "final")
        self.assertIs(chosen, final_receipt)

        dispatch_type, chosen = choose_trust_read_dispatch_receipt(
            dispatch_type="auto",
            final_receipt=None,
            phase_receipt=phase_receipt,
        )
        self.assertEqual(dispatch_type, "phase")
        self.assertIs(chosen, phase_receipt)

    def test_build_trust_report_context_from_receipt_should_parse_snapshots(self) -> None:
        receipt = _DummyReceipt(
            request={"traceId": "trace-request"},
            response={"reportPayload": {"winner": "pro", "judgeTrace": {"traceId": "trace-judge"}}},
            trace_id="trace-receipt",
        )
        payload = build_trust_report_context_from_receipt(
            dispatch_type="final",
            receipt=receipt,
        )
        self.assertEqual(payload["dispatchType"], "final")
        self.assertEqual(payload["traceId"], "trace-receipt")
        self.assertEqual(payload["requestSnapshot"], {"traceId": "trace-request"})
        self.assertEqual(payload["reportPayload"]["winner"], "pro")
        self.assertIs(payload["receipt"], receipt)

    def test_build_trust_report_context_from_receipt_should_fail_on_missing_report(self) -> None:
        receipt = _DummyReceipt(
            request={"traceId": "trace-request"},
            response={},
            trace_id="trace-receipt",
        )
        with self.assertRaises(ValueError) as ctx:
            build_trust_report_context_from_receipt(
                dispatch_type="phase",
                receipt=receipt,
            )
        self.assertEqual(str(ctx.exception), "trust_report_payload_missing")

    def test_route_payload_builders_should_keep_trust_shape(self) -> None:
        item = {"version": "v1", "traceId": "trace-item"}
        verify_payload = {"commitment": {"hash": "h1"}}
        item_payload = build_trust_item_route_payload(
            case_id=1001,
            dispatch_type="final",
            trace_id="trace-final-1001",
            item=item,
        )
        public_payload = build_trust_public_verify_route_payload(
            case_id=1001,
            dispatch_type="final",
            trace_id="trace-final-1001",
            verify_payload=verify_payload,
        )
        self.assertEqual(item_payload["caseId"], 1001)
        self.assertEqual(item_payload["dispatchType"], "final")
        self.assertEqual(item_payload["traceId"], "trace-final-1001")
        self.assertEqual(item_payload["item"], item)
        self.assertIsNot(item_payload["item"], item)
        self.assertEqual(public_payload["verifyPayload"], verify_payload)
        self.assertIsNot(public_payload["verifyPayload"], verify_payload)


if __name__ == "__main__":
    unittest.main()
