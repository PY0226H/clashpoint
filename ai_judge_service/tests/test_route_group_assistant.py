from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any

from app.applications.route_group_assistant import (
    AssistantRouteDependencies,
    register_assistant_routes,
)
from fastapi import FastAPI


class RouteGroupAssistantTests(unittest.TestCase):
    def test_register_assistant_routes_should_expose_paths_and_handles(self) -> None:
        app = FastAPI()
        runtime = SimpleNamespace(settings=SimpleNamespace())

        async def _payload(**_kwargs: Any) -> dict[str, Any]:
            return {}

        deps = AssistantRouteDependencies(
            runtime=runtime,
            require_internal_key_fn=lambda _settings, _header: None,
            run_assistant_agent_route_guard=lambda awaitable: awaitable,
            build_shared_room_context=_payload,
            execute_agent=_payload,
        )

        handles = register_assistant_routes(app=app, deps=deps)

        paths = {route.path for route in app.routes}
        self.assertIn(
            "/internal/judge/apps/npc-coach/sessions/{session_id}/advice",
            paths,
        )
        self.assertIn(
            "/internal/judge/apps/room-qa/sessions/{session_id}/answer",
            paths,
        )
        self.assertEqual(
            handles.request_npc_coach_advice.__name__,
            "request_npc_coach_advice",
        )
        self.assertEqual(
            handles.request_room_qa_answer.__name__,
            "request_room_qa_answer",
        )
