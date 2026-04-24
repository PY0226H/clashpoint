from __future__ import annotations

import unittest
from datetime import datetime
from types import SimpleNamespace
from typing import Any

from app.applications.route_group_case_read import (
    CaseReadRouteDependencies,
    register_case_read_routes,
)
from fastapi import FastAPI


class RouteGroupCaseReadTests(unittest.TestCase):
    def test_register_case_read_routes_should_expose_read_paths_and_handles(self) -> None:
        app = FastAPI()
        runtime = SimpleNamespace(settings=SimpleNamespace())

        async def _payload(**_kwargs: Any) -> dict[str, Any]:
            return {}

        async def _list_payload(**_kwargs: Any) -> list[Any]:
            return []

        def _sync_payload(**_kwargs: Any) -> dict[str, Any]:
            return {}

        deps = CaseReadRouteDependencies(
            runtime=runtime,
            require_internal_key_fn=lambda _settings, _header: None,
            run_case_read_route_guard=lambda awaitable: awaitable,
            validate_contract_or_raise_http_500=lambda **kwargs: kwargs["payload"],
            workflow_get_job=_payload,
            workflow_list_events=_payload,
            get_dispatch_receipt=_payload,
            trace_get=_sync_payload,
            list_replay_records=_list_payload,
            list_audit_alerts=_list_payload,
            get_claim_ledger_record=_payload,
            list_claim_ledger_records=_list_payload,
            resolve_report_context_for_case=_payload,
            workflow_list_jobs=_list_payload,
            build_judge_core_view=_sync_payload,
            build_review_case_risk_profile=_sync_payload,
            build_courtroom_read_model_view=_sync_payload,
            build_courtroom_read_model_light_summary=_sync_payload,
            build_courtroom_drilldown_bundle_view=_sync_payload,
            serialize_workflow_job=lambda _job: {},
            normalize_workflow_status=lambda status: status,
            workflow_statuses={"completed", "failed"},
            normalize_query_datetime=lambda value: (
                value if isinstance(value, datetime) else None
            ),
            review_case_risk_level_values={"low", "medium", "high"},
            review_case_sla_bucket_values={"healthy", "warning", "breached"},
            courtroom_case_sort_fields={"updated_at", "risk_score"},
            evidence_claim_reliability_level_values={"low", "medium", "high"},
            evidence_claim_queue_sort_fields={"updated_at", "risk_score"},
            validate_case_overview_contract=lambda _payload: None,
            validate_courtroom_read_model_contract=lambda _payload: None,
            validate_courtroom_drilldown_bundle_contract=lambda _payload: None,
            validate_evidence_claim_ops_queue_contract=lambda _payload: None,
        )

        handles = register_case_read_routes(app=app, deps=deps)

        paths = {route.path for route in app.routes}
        self.assertIn("/internal/judge/cases/{case_id}", paths)
        self.assertIn("/internal/judge/cases/{case_id}/claim-ledger", paths)
        self.assertIn("/internal/judge/cases/{case_id}/courtroom-read-model", paths)
        self.assertIn("/internal/judge/courtroom/cases", paths)
        self.assertIn("/internal/judge/courtroom/drilldown-bundle", paths)
        self.assertIn("/internal/judge/evidence-claim/ops-queue", paths)
        self.assertEqual(
            handles.get_judge_case_courtroom_read_model.__name__,
            "get_judge_case_courtroom_read_model",
        )
        self.assertEqual(
            handles.list_judge_evidence_claim_ops_queue.__name__,
            "list_judge_evidence_claim_ops_queue",
        )
