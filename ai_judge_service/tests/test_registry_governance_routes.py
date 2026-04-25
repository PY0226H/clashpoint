from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from typing import Any

from app.applications.registry_governance_routes import (
    build_policy_gate_simulation_route_payload,
    build_policy_registry_dependency_health_route_payload,
    build_registry_prompt_tool_governance_route_payload,
)
from app.applications.registry_routes import RegistryRouteError


class RegistryGovernanceRoutesTests(unittest.TestCase):
    def test_dependency_health_route_should_map_invalid_trend_status(self) -> None:
        async def _evaluate_dependency_health(version: str) -> dict[str, Any]:
            return {
                "policyVersion": version,
                "ok": True,
                "code": "dependency_ok",
                "issues": [],
                "promptRegistryVersion": "promptset-v3-default",
                "toolRegistryVersion": "toolset-v3-default",
            }

        async def _list_audit_alerts(*, job_id: int, status: str | None, limit: int) -> list[Any]:
            del job_id, status, limit
            return []

        with self.assertRaises(RegistryRouteError) as ctx:
            asyncio.run(
                build_policy_registry_dependency_health_route_payload(
                    policy_version="policy-v3-default",
                    default_policy_version="policy-v3-default",
                    default_prompt_registry_version="promptset-v3-default",
                    default_tool_registry_version="toolset-v3-default",
                    include_all_versions=False,
                    include_overview=False,
                    include_trend=False,
                    trend_status="bad-status",
                    trend_policy_version=None,
                    trend_offset=0,
                    trend_limit=20,
                    overview_window_minutes=1440,
                    limit=20,
                    list_policy_profiles=lambda: [],
                    evaluate_policy_registry_dependency_health=_evaluate_dependency_health,
                    normalize_registry_dependency_trend_status=lambda value: value,
                    dependency_trend_status_values=frozenset({"open", "resolved"}),
                    list_audit_alerts=_list_audit_alerts,
                    build_registry_dependency_overview=lambda **kwargs: {},
                    build_registry_dependency_trend=lambda **kwargs: {},
                )
            )

        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail, "invalid_trend_status")

    def test_dependency_health_route_should_map_policy_not_found(self) -> None:
        async def _evaluate_dependency_health(version: str) -> dict[str, Any]:
            del version
            return {
                "ok": False,
                "code": "policy_registry_not_found",
            }

        async def _list_audit_alerts(*, job_id: int, status: str | None, limit: int) -> list[Any]:
            del job_id, status, limit
            return []

        with self.assertRaises(RegistryRouteError) as ctx:
            asyncio.run(
                build_policy_registry_dependency_health_route_payload(
                    policy_version="policy-missing",
                    default_policy_version="policy-v3-default",
                    default_prompt_registry_version="promptset-v3-default",
                    default_tool_registry_version="toolset-v3-default",
                    include_all_versions=False,
                    include_overview=False,
                    include_trend=False,
                    trend_status=None,
                    trend_policy_version=None,
                    trend_offset=0,
                    trend_limit=20,
                    overview_window_minutes=1440,
                    limit=20,
                    list_policy_profiles=lambda: [],
                    evaluate_policy_registry_dependency_health=_evaluate_dependency_health,
                    normalize_registry_dependency_trend_status=lambda value: value,
                    dependency_trend_status_values=frozenset({"open", "resolved"}),
                    list_audit_alerts=_list_audit_alerts,
                    build_registry_dependency_overview=lambda **kwargs: {},
                    build_registry_dependency_trend=lambda **kwargs: {},
                )
            )

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "policy_registry_not_found")

    def test_policy_gate_simulation_route_should_map_invalid_policy_version(self) -> None:
        async def _evaluate_dependency_health(version: str) -> dict[str, Any]:
            del version
            return {}

        async def _evaluate_release_gate(version: str) -> dict[str, Any]:
            del version
            return {}

        with self.assertRaises(RegistryRouteError) as ctx:
            asyncio.run(
                build_policy_gate_simulation_route_payload(
                    policy_version=None,
                    default_policy_version="",
                    include_all_versions=False,
                    limit=10,
                    list_policy_profiles=lambda: [],
                    get_policy_profile=lambda version: None,
                    serialize_policy_profile=lambda profile: {},
                    evaluate_policy_registry_dependency_health=_evaluate_dependency_health,
                    evaluate_policy_release_fairness_gate=_evaluate_release_gate,
                )
            )

        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail, "invalid_policy_version")

    def test_policy_gate_simulation_route_should_map_policy_not_found(self) -> None:
        async def _evaluate_dependency_health(version: str) -> dict[str, Any]:
            del version
            return {}

        async def _evaluate_release_gate(version: str) -> dict[str, Any]:
            del version
            return {}

        with self.assertRaises(RegistryRouteError) as ctx:
            asyncio.run(
                build_policy_gate_simulation_route_payload(
                    policy_version="policy-missing",
                    default_policy_version="policy-v3-default",
                    include_all_versions=False,
                    limit=10,
                    list_policy_profiles=lambda: [],
                    get_policy_profile=lambda version: None,
                    serialize_policy_profile=lambda profile: {},
                    evaluate_policy_registry_dependency_health=_evaluate_dependency_health,
                    evaluate_policy_release_fairness_gate=_evaluate_release_gate,
                )
            )

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "policy_registry_not_found")

    def test_prompt_tool_governance_route_should_return_payload(self) -> None:
        policy_profile = SimpleNamespace(
            version="policy-v3-default",
            prompt_registry_version="promptset-v3-default",
            tool_registry_version="toolset-v3-default",
        )
        prompt_profile = SimpleNamespace(version="promptset-v3-default")
        tool_profile = SimpleNamespace(version="toolset-v3-default")

        async def _evaluate_dependency_health(version: str) -> dict[str, Any]:
            return {
                "policyVersion": version,
                "ok": True,
                "code": "dependency_ok",
                "issues": [],
                "promptRegistryVersion": "promptset-v3-default",
                "toolRegistryVersion": "toolset-v3-default",
                "policyKernel": {
                    "version": "policy-kernel-binding-v1",
                    "kernelHash": "kernel-hash",
                },
            }

        async def _evaluate_release_gate(version: str) -> dict[str, Any]:
            return {
                "policyVersion": version,
                "passed": True,
                "benchmarkGatePassed": True,
                "shadowGateApplied": False,
            }

        async def _list_releases(
            *,
            registry_type: str,
            limit: int,
            include_payload: bool,
        ) -> list[dict[str, Any]]:
            del registry_type, limit, include_payload
            return []

        async def _list_audits(
            *,
            registry_type: str,
            limit: int,
        ) -> list[dict[str, Any]]:
            del registry_type, limit
            return []

        payload = asyncio.run(
            build_registry_prompt_tool_governance_route_payload(
                dependency_limit=20,
                usage_preview_limit=10,
                release_limit=20,
                audit_limit=20,
                risk_limit=20,
                default_policy_version="policy-v3-default",
                default_prompt_registry_version="promptset-v3-default",
                default_tool_registry_version="toolset-v3-default",
                policy_registry_type="policy",
                prompt_registry_type="prompt",
                tool_registry_type="tool",
                list_policy_profiles=lambda: [policy_profile],
                list_prompt_profiles=lambda: [prompt_profile],
                list_tool_profiles=lambda: [tool_profile],
                evaluate_policy_registry_dependency_health=_evaluate_dependency_health,
                evaluate_policy_release_fairness_gate=_evaluate_release_gate,
                list_releases=_list_releases,
                list_audits=_list_audits,
                build_policy_domain_judge_family_overview=lambda **kwargs: {
                    "count": 1,
                    "allowedFamilies": ["tft"],
                    "items": [],
                },
                build_registry_prompt_tool_usage_rows=lambda **kwargs: (
                    list(kwargs.get("usage_rows") or []),
                    0,
                ),
                build_registry_prompt_tool_risk_items=lambda **kwargs: [],
                build_registry_prompt_tool_action_hints=lambda **kwargs: [],
            )
        )

        self.assertEqual(payload["summary"]["riskLevel"], "healthy")
        self.assertEqual(payload["summary"]["riskTotalCount"], 0)
        self.assertEqual(payload["summary"]["riskReturned"], 0)
        self.assertEqual(payload["filters"]["riskLimit"], 20)


if __name__ == "__main__":
    unittest.main()
