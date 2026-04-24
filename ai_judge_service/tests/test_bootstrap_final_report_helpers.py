from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any

from app.applications.bootstrap_final_report_helpers import (
    build_final_report_payload_for_runtime,
)


class BootstrapFinalReportHelpersTests(unittest.TestCase):
    def test_build_final_report_payload_should_inject_runtime_dependencies(self) -> None:
        list_calls: list[dict[str, Any]] = []

        def _list_dispatch_receipts(**kwargs: Any) -> list[dict[str, Any]]:
            list_calls.append(kwargs)
            return [{"dispatchType": "phase"}]

        def _build_final_report_payload(**kwargs: Any) -> dict[str, Any]:
            return dict(kwargs)

        request = SimpleNamespace(session_id=23)

        payload = build_final_report_payload_for_runtime(
            request=request,
            phase_receipts=None,
            fairness_thresholds={"drawMargin": 0.8},
            panel_runtime_profiles={"p1": {"mode": "mock"}},
            list_dispatch_receipts=_list_dispatch_receipts,
            build_final_report_payload=_build_final_report_payload,
            judge_style_mode="rational",
        )

        self.assertEqual(
            list_calls,
            [
                {
                    "dispatch_type": "phase",
                    "session_id": 23,
                    "status": "reported",
                    "limit": 1000,
                }
            ],
        )
        self.assertEqual(payload["phase_receipts"], [{"dispatchType": "phase"}])
        self.assertEqual(payload["judge_style_mode"], "rational")
        self.assertEqual(payload["fairness_thresholds"], {"drawMargin": 0.8})
        self.assertEqual(payload["panel_runtime_profiles"], {"p1": {"mode": "mock"}})

    def test_build_final_report_payload_should_use_explicit_phase_receipts(self) -> None:
        def _list_dispatch_receipts(**_kwargs: Any) -> list[dict[str, Any]]:
            raise AssertionError("explicit phase receipts should skip trace store lookup")

        def _build_final_report_payload(**kwargs: Any) -> dict[str, Any]:
            return dict(kwargs)

        payload = build_final_report_payload_for_runtime(
            request=SimpleNamespace(session_id=23),
            phase_receipts=[{"dispatchType": "phase", "jobId": 1}],
            fairness_thresholds=None,
            panel_runtime_profiles=None,
            list_dispatch_receipts=_list_dispatch_receipts,
            build_final_report_payload=_build_final_report_payload,
            judge_style_mode="rational",
        )

        self.assertEqual(
            payload["phase_receipts"],
            [{"dispatchType": "phase", "jobId": 1}],
        )
