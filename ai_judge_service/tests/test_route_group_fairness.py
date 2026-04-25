from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any

from app.applications.route_group_fairness import (
    FairnessRouteDependencies,
    register_fairness_routes,
)
from fastapi import FastAPI


class RouteGroupFairnessTests(unittest.TestCase):
    def test_register_fairness_routes_should_expose_paths_and_handles(self) -> None:
        app = FastAPI()
        runtime = SimpleNamespace(
            settings=SimpleNamespace(),
            trace_store=SimpleNamespace(upsert_audit_alert=lambda **_kwargs: None),
        )

        async def _payload(**_kwargs: Any) -> dict[str, Any]:
            return {}

        async def _list_payload(**_kwargs: Any) -> list[Any]:
            return []

        def _sync_payload(**_kwargs: Any) -> dict[str, Any]:
            return {}

        deps = FairnessRouteDependencies(
            runtime=runtime,
            require_internal_key_fn=lambda _settings, _header: None,
            read_json_object_or_raise_422=_payload,
            run_fairness_route_guard=lambda awaitable: awaitable,
            workflow_get_job=_payload,
            workflow_list_events=_list_payload,
            workflow_list_jobs=_list_payload,
            get_trace=_sync_payload,
            resolve_report_context_for_case=_payload,
            list_fairness_benchmark_runs=_list_payload,
            list_fairness_shadow_runs=_list_payload,
            upsert_fairness_benchmark_run=_payload,
            upsert_fairness_shadow_run=_payload,
            sync_audit_alert_to_facts=_payload,
            serialize_fairness_benchmark_run=lambda _record: {},
            serialize_fairness_shadow_run=lambda _record: {},
            build_case_fairness_item=_sync_payload,
            build_case_fairness_aggregations=lambda _items: {},
            evaluate_policy_release_fairness_gate=_payload,
            extract_optional_datetime=lambda *_args, **_kwargs: None,
            normalize_workflow_status=lambda status: status,
            workflow_statuses={"completed", "failed"},
            case_fairness_sort_fields={"updated_at", "risk_score"},
            case_fairness_gate_conclusions={"pass_through", "blocked_to_draw"},
            case_fairness_challenge_states={"open", "under_internal_review"},
            validate_case_fairness_detail_contract=lambda _payload: None,
            validate_case_fairness_list_contract=lambda _payload: None,
            validate_fairness_dashboard_contract=lambda _payload: None,
        )

        handles = register_fairness_routes(app=app, deps=deps)

        paths = {route.path for route in app.routes}
        self.assertIn("/internal/judge/fairness/benchmark-runs", paths)
        self.assertIn("/internal/judge/fairness/shadow-runs", paths)
        self.assertIn("/internal/judge/fairness/cases/{case_id}", paths)
        self.assertIn("/internal/judge/fairness/cases", paths)
        self.assertIn("/internal/judge/fairness/dashboard", paths)
        self.assertIn("/internal/judge/fairness/calibration-pack", paths)
        self.assertIn("/internal/judge/fairness/policy-calibration-advisor", paths)
        self.assertEqual(
            handles.list_judge_case_fairness.__name__,
            "list_judge_case_fairness",
        )
        self.assertEqual(
            handles.get_judge_fairness_policy_calibration_advisor.__name__,
            "get_judge_fairness_policy_calibration_advisor",
        )
