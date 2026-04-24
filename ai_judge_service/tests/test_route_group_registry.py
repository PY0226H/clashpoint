from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any

from app.applications.route_group_registry import register_registry_routes
from fastapi import FastAPI


class RouteGroupRegistryTests(unittest.TestCase):
    def test_register_registry_routes_should_expose_registry_paths_and_handles(self) -> None:
        app = FastAPI()
        runtime = SimpleNamespace(settings=SimpleNamespace())

        async def _ready() -> None:
            return None

        async def _payload(**_kwargs: Any) -> dict[str, Any]:
            return {}

        async def _guard(awaitable: Any) -> dict[str, Any]:
            return await awaitable

        def _raise(**_kwargs: Any) -> None:
            raise AssertionError("unexpected error bridge call")

        handles = register_registry_routes(
            app=app,
            runtime=runtime,
            require_internal_key_fn=lambda _settings, _header: None,
            ensure_registry_runtime_ready=_ready,
            serialize_policy_profile_with_domain_family=lambda **_kwargs: {},
            build_registry_governance_dependency_pack=lambda: {},
            registry_release_gate_dependencies={},
            list_audit_alerts=_payload,
            read_json_object_or_raise_422=_payload,
            run_registry_route_guard=_guard,
            build_policy_registry_profiles_payload_with_ready=_payload,
            build_policy_registry_profile_payload_with_ready=_payload,
            build_registry_profiles_payload_with_ready=_payload,
            build_registry_profile_payload_with_ready=_payload,
            build_registry_audits_payload=_payload,
            build_registry_releases_payload=_payload,
            build_registry_release_payload=_payload,
            enforce_policy_domain_judge_family_profile_payload=lambda **_kwargs: None,
            raise_http_422_from_value_error=_raise,
            raise_http_404_from_lookup_error=_raise,
            raise_registry_value_error=_raise,
            raise_registry_version_not_found_lookup_error=_raise,
        )

        paths = {route.path for route in app.routes}
        self.assertIn("/internal/judge/policies", paths)
        self.assertIn("/internal/judge/registries/policy/dependencies/health", paths)
        self.assertIn("/internal/judge/registries/governance/overview", paths)
        self.assertIn("/internal/judge/registries/policy/gate-simulation", paths)
        self.assertIn("/internal/judge/registries/{registry_type}/releases/{version}", paths)
        self.assertTrue(callable(handles.get_registry_governance_overview))
        self.assertTrue(callable(handles.get_registry_prompt_tool_governance))
        self.assertTrue(callable(handles.get_policy_registry_dependency_health))
        self.assertTrue(callable(handles.simulate_policy_release_gate))
