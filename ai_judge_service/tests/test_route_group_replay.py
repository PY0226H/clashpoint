from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any

from app.applications.route_group_replay import (
    ReplayRouteDependencies,
    register_replay_routes,
)
from fastapi import FastAPI


class RouteGroupReplayTests(unittest.TestCase):
    def test_register_replay_routes_should_expose_paths_and_handles(self) -> None:
        app = FastAPI()
        runtime = SimpleNamespace(settings=SimpleNamespace())

        async def _payload(**_kwargs: Any) -> dict[str, Any]:
            return {}

        async def _list_payload(**_kwargs: Any) -> list[Any]:
            return []

        def _sync_payload(**_kwargs: Any) -> dict[str, Any]:
            return {}

        deps = ReplayRouteDependencies(
            runtime=runtime,
            require_internal_key_fn=lambda _settings, _header: None,
            run_replay_read_guard=lambda awaitable: awaitable,
            build_replay_report_payload=_payload,
            build_replay_reports_payload=_sync_payload,
            replay_context_dependencies=SimpleNamespace(),
            replay_report_dependencies=SimpleNamespace(),
            replay_finalize_dependencies=SimpleNamespace(),
            get_trace=_sync_payload,
            list_replay_records=_list_payload,
            get_claim_ledger_record=_payload,
            list_traces=lambda **_kwargs: [],
        )

        handles = register_replay_routes(app=app, deps=deps)

        paths = {route.path for route in app.routes}
        self.assertIn("/internal/judge/cases/{case_id}/trace", paths)
        self.assertIn("/internal/judge/cases/{case_id}/replay", paths)
        self.assertIn("/internal/judge/cases/{case_id}/replay/report", paths)
        self.assertIn("/internal/judge/cases/replay/reports", paths)
        self.assertEqual(
            handles.replay_judge_job.__name__,
            "replay_judge_job",
        )
        self.assertEqual(
            handles.list_judge_replay_reports.__name__,
            "list_judge_replay_reports",
        )
