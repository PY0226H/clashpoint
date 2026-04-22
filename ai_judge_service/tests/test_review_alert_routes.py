from __future__ import annotations

import unittest

from app.applications.review_alert_routes import (
    build_alert_outbox_route_payload,
    build_rag_diagnostics_payload,
)


class ReviewAlertRoutesTests(unittest.TestCase):
    def test_build_alert_outbox_route_payload_should_build_items(self) -> None:
        row = type(
            "OutboxRow",
            (),
            {
                "event_id": "evt-1",
                "alert_id": "alert-1",
                "delivery_status": "failed",
            },
        )()
        payload = build_alert_outbox_route_payload(
            delivery_status="failed",
            limit=20,
            list_alert_outbox=lambda **kwargs: [row],
            serialize_outbox_event=lambda item: {
                "eventId": item.event_id,
                "alertId": item.alert_id,
                "deliveryStatus": item.delivery_status,
            },
        )
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["eventId"], "evt-1")
        self.assertEqual(payload["filters"]["deliveryStatus"], "failed")
        self.assertEqual(payload["filters"]["limit"], 20)

    def test_build_rag_diagnostics_payload_should_raise_when_trace_missing(self) -> None:
        with self.assertRaises(LookupError) as ctx:
            build_rag_diagnostics_payload(
                case_id=9001,
                get_trace=lambda case_id: None,
            )
        self.assertEqual(str(ctx.exception), "judge_trace_not_found")

    def test_build_rag_diagnostics_payload_should_map_fields(self) -> None:
        trace = type(
            "Trace",
            (),
            {
                "trace_id": "trace-9002",
                "report_summary": {
                    "payload": {
                        "retrievalDiagnostics": {"pro": {"queryCount": 2}},
                        "ragSources": [{"sourceId": "s1"}],
                        "ragBackend": "milvus",
                        "ragRequestedBackend": "milvus",
                        "ragBackendFallbackReason": None,
                    }
                },
            },
        )()
        payload = build_rag_diagnostics_payload(
            case_id=9002,
            get_trace=lambda case_id: trace,
        )
        self.assertEqual(payload["caseId"], 9002)
        self.assertEqual(payload["traceId"], "trace-9002")
        self.assertEqual(payload["ragBackend"], "milvus")
        self.assertIsInstance(payload["retrievalDiagnostics"], dict)
        self.assertIsInstance(payload["ragSources"], list)


if __name__ == "__main__":
    unittest.main()
