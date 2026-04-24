from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any

from app.applications.route_group_alert_ops import (
    AlertOpsRouteDependencies,
    register_alert_ops_routes,
)
from fastapi import FastAPI


class RouteGroupAlertOpsTests(unittest.TestCase):
    def test_register_alert_ops_routes_should_expose_paths_and_handles(self) -> None:
        app = FastAPI()
        runtime = SimpleNamespace(settings=SimpleNamespace())

        async def _payload(**_kwargs: Any) -> dict[str, Any]:
            return {}

        async def _list_payload(**_kwargs: Any) -> list[Any]:
            return []

        def _sync_payload(**_kwargs: Any) -> dict[str, Any]:
            return {}

        deps = AlertOpsRouteDependencies(
            runtime=runtime,
            require_internal_key_fn=lambda _settings, _header: None,
            await_payload_or_raise_http_422=_payload,
            build_payload_or_raise_http_404=_sync_payload,
            build_case_alerts_payload=_payload,
            transition_judge_alert_status=_payload,
            build_alert_ops_view_payload=_payload,
            build_alert_outbox_payload=_sync_payload,
            list_audit_alerts=_list_payload,
            list_alert_outbox=lambda **_kwargs: [],
            mark_alert_outbox_delivery=lambda **_kwargs: None,
            get_trace=lambda **_kwargs: {},
            serialize_alert_item=lambda _record: {},
            serialize_outbox_event=lambda _record: {},
        )

        handles = register_alert_ops_routes(app=app, deps=deps)

        paths = {route.path for route in app.routes}
        self.assertIn("/internal/judge/cases/{case_id}/alerts", paths)
        self.assertIn(
            "/internal/judge/cases/{case_id}/alerts/{alert_id}/ack",
            paths,
        )
        self.assertIn(
            "/internal/judge/cases/{case_id}/alerts/{alert_id}/resolve",
            paths,
        )
        self.assertIn("/internal/judge/alerts/ops-view", paths)
        self.assertIn("/internal/judge/alerts/outbox", paths)
        self.assertIn("/internal/judge/alerts/outbox/{event_id}/delivery", paths)
        self.assertIn("/internal/judge/rag/diagnostics", paths)
        self.assertEqual(
            handles.list_judge_alert_ops_view.__name__,
            "list_judge_alert_ops_view",
        )
        self.assertEqual(
            handles.mark_judge_alert_outbox_delivery.__name__,
            "mark_judge_alert_outbox_delivery",
        )
