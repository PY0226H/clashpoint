from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any

from app.applications.route_group_panel_runtime import (
    PanelRuntimeRouteDependencies,
    register_panel_runtime_routes,
)
from fastapi import FastAPI


class RouteGroupPanelRuntimeTests(unittest.TestCase):
    def test_register_panel_runtime_routes_should_expose_paths_and_handles(self) -> None:
        app = FastAPI()
        runtime = SimpleNamespace(settings=SimpleNamespace())

        async def _payload(**_kwargs: Any) -> dict[str, Any]:
            return {}

        deps = PanelRuntimeRouteDependencies(
            runtime=runtime,
            require_internal_key_fn=lambda _settings, _header: None,
            await_payload_or_raise_http_500=_payload,
            build_panel_runtime_profiles_payload=_payload,
            build_panel_runtime_readiness_payload=_payload,
            list_judge_case_fairness=_payload,
            run_panel_runtime_route_guard=lambda awaitable: awaitable,
        )

        handles = register_panel_runtime_routes(app=app, deps=deps)

        paths = {route.path for route in app.routes}
        self.assertIn("/internal/judge/panels/runtime/profiles", paths)
        self.assertIn("/internal/judge/panels/runtime/readiness", paths)
        self.assertEqual(
            handles.list_panel_runtime_profiles.__name__,
            "list_panel_runtime_profiles",
        )
        self.assertEqual(
            handles.get_panel_runtime_readiness.__name__,
            "get_panel_runtime_readiness",
        )
