from __future__ import annotations

import unittest
from unittest.mock import patch

from app.applications.bootstrap_fairness_helpers import (
    build_case_fairness_aggregations_for_runtime,
    build_case_fairness_item_for_runtime,
)


class BootstrapFairnessHelpersTests(unittest.TestCase):
    def test_build_case_fairness_item_should_inject_runtime_dependencies(self) -> None:
        def _normalize(value: object, **_kwargs: object) -> str:
            return str(value or "normalized")

        def _serialize_benchmark(_record: object) -> dict[str, object]:
            return {"benchmark": True}

        def _serialize_shadow(_record: object) -> dict[str, object]:
            return {"shadow": True}

        with patch(
            "app.applications.bootstrap_fairness_helpers.build_case_fairness_item_v3"
        ) as fairness_item:
            fairness_item.return_value = {"caseId": 42}

            result = build_case_fairness_item_for_runtime(
                case_id=42,
                dispatch_type="final",
                trace_id="trace-42",
                workflow_job=None,
                workflow_events=[],
                report_payload={"winner": "pro"},
                latest_run=None,
                latest_shadow_run=None,
                normalize_fairness_gate_decision=_normalize,
                serialize_fairness_benchmark_run=_serialize_benchmark,
                serialize_fairness_shadow_run=_serialize_shadow,
                trust_challenge_event_type="trust_challenge_requested",
            )

        self.assertEqual(result, {"caseId": 42})
        fairness_item.assert_called_once_with(
            case_id=42,
            dispatch_type="final",
            trace_id="trace-42",
            workflow_job=None,
            workflow_events=[],
            report_payload={"winner": "pro"},
            latest_run=None,
            latest_shadow_run=None,
            normalize_fairness_gate_decision=_normalize,
            serialize_fairness_benchmark_run=_serialize_benchmark,
            serialize_fairness_shadow_run=_serialize_shadow,
            trust_challenge_event_type="trust_challenge_requested",
        )

    def test_build_case_fairness_aggregations_should_inject_conclusions(self) -> None:
        with patch(
            "app.applications.bootstrap_fairness_helpers.build_case_fairness_aggregations_v3"
        ) as aggregations:
            aggregations.return_value = {"totalMatched": 1}

            result = build_case_fairness_aggregations_for_runtime(
                [{"gateConclusion": "pass_through"}],
                case_fairness_gate_conclusions={"pass_through"},
            )

        self.assertEqual(result, {"totalMatched": 1})
        aggregations.assert_called_once_with(
            [{"gateConclusion": "pass_through"}],
            case_fairness_gate_conclusions={"pass_through"},
        )
