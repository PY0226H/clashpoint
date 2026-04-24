from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any

from app.applications.route_group_review import (
    ReviewRouteDependencies,
    register_review_routes,
)
from fastapi import FastAPI


class RouteGroupReviewTests(unittest.TestCase):
    def test_register_review_routes_should_expose_paths_and_handles(self) -> None:
        app = FastAPI()
        runtime = SimpleNamespace(settings=SimpleNamespace())

        async def _payload(**_kwargs: Any) -> dict[str, Any]:
            return {}

        async def _list_payload(**_kwargs: Any) -> list[Any]:
            return []

        async def _none_payload(**_kwargs: Any) -> None:
            return None

        def _sync_payload(**_kwargs: Any) -> dict[str, Any]:
            return {}

        deps = ReviewRouteDependencies(
            runtime=runtime,
            require_internal_key_fn=lambda _settings, _header: None,
            await_payload_or_raise_http_422=_payload,
            await_payload_or_raise_http_404=_payload,
            await_payload_or_raise_http_422_404=_payload,
            build_review_cases_list_payload=_payload,
            build_review_case_detail_payload=_payload,
            run_review_route_guard=lambda awaitable: awaitable,
            workflow_get_job=_payload,
            workflow_list_jobs=_list_payload,
            workflow_list_events=_list_payload,
            workflow_mark_completed=_none_payload,
            workflow_mark_failed=_none_payload,
            list_audit_alerts=_list_payload,
            get_trace=_sync_payload,
            build_review_case_risk_profile=_sync_payload,
            build_trust_challenge_priority_profile=_sync_payload,
            build_review_trust_unified_priority_profile=_sync_payload,
            resolve_open_alerts_for_review=_list_payload,
            serialize_workflow_job=lambda _record: {},
            serialize_alert_item=lambda _record: {},
        )

        handles = register_review_routes(app=app, deps=deps)

        paths = {route.path for route in app.routes}
        self.assertIn("/internal/judge/review/cases", paths)
        self.assertIn("/internal/judge/review/cases/{case_id}", paths)
        self.assertIn("/internal/judge/review/cases/{case_id}/decision", paths)
        self.assertEqual(
            handles.list_judge_review_jobs.__name__,
            "list_judge_review_jobs",
        )
        self.assertEqual(
            handles.decide_judge_review_job.__name__,
            "decide_judge_review_job",
        )
