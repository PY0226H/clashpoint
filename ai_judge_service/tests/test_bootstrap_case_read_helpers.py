from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.applications.bootstrap_case_read_helpers import (
    build_courtroom_drilldown_bundle_view_for_runtime,
    build_courtroom_read_model_light_summary_for_runtime,
    build_courtroom_read_model_view_for_runtime,
    extract_optional_datetime_for_runtime,
)


class BootstrapCaseReadHelpersTests(unittest.TestCase):
    def test_build_courtroom_helpers_should_inject_fairness_normalizer(self) -> None:
        def _normalize(value: object, **_kwargs: object) -> str:
            return f"normalized:{value}"

        with patch(
            "app.applications.bootstrap_case_read_helpers.build_courtroom_read_model_view_v3"
        ) as read_model:
            read_model.return_value = {"ok": True}

            result = build_courtroom_read_model_view_for_runtime(
                report_payload={"winner": "pro"},
                case_evidence={"fairnessSummary": {}},
                normalize_fairness_gate_decision=_normalize,
            )

        self.assertEqual(result, {"ok": True})
        read_model.assert_called_once_with(
            report_payload={"winner": "pro"},
            case_evidence={"fairnessSummary": {}},
            normalize_fairness_gate_decision=_normalize,
        )

        with patch(
            "app.applications.bootstrap_case_read_helpers.build_courtroom_read_model_light_summary_v3"
        ) as light_summary:
            light_summary.return_value = {"summary": True}

            result = build_courtroom_read_model_light_summary_for_runtime(
                courtroom_view={"fairness": {}},
                normalize_fairness_gate_decision=_normalize,
            )

        self.assertEqual(result, {"summary": True})
        light_summary.assert_called_once_with(
            courtroom_view={"fairness": {}},
            normalize_fairness_gate_decision=_normalize,
        )

        with patch(
            "app.applications.bootstrap_case_read_helpers.build_courtroom_drilldown_bundle_view_v3"
        ) as drilldown:
            drilldown.return_value = {"bundle": True}

            result = build_courtroom_drilldown_bundle_view_for_runtime(
                courtroom_view={"claim": {}},
                claim_preview_limit=3,
                evidence_preview_limit=4,
                panel_preview_limit=5,
                normalize_fairness_gate_decision=_normalize,
            )

        self.assertEqual(result, {"bundle": True})
        drilldown.assert_called_once_with(
            courtroom_view={"claim": {}},
            claim_preview_limit=3,
            evidence_preview_limit=4,
            panel_preview_limit=5,
            normalize_fairness_gate_decision=_normalize,
        )

    def test_extract_optional_datetime_should_inject_query_normalizer(self) -> None:
        seen: list[datetime] = []

        def _normalize(value: datetime | None) -> datetime | None:
            if value is not None:
                seen.append(value)
                return value.astimezone(timezone.utc)
            return None

        result = extract_optional_datetime_for_runtime(
            {"createdAt": "2026-04-24T08:30:00Z"},
            "createdAt",
            normalize_query_datetime=_normalize,
        )

        self.assertEqual(result, datetime(2026, 4, 24, 8, 30, tzinfo=timezone.utc))
        self.assertEqual(seen, [datetime(2026, 4, 24, 8, 30, tzinfo=timezone.utc)])
