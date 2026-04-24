from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any

from app.applications.bootstrap_registry_route_helpers import (
    build_registry_audits_payload_for_runtime,
    build_registry_governance_route_dependency_pack_for_runtime,
    build_registry_profile_payload_for_runtime,
    build_registry_profiles_payload_with_ready_for_runtime,
    build_registry_release_payload_for_runtime,
    build_registry_releases_payload_for_runtime,
    raise_registry_value_error,
    run_registry_route_guard_for_runtime,
)
from app.applications.registry_routes import RegistryRouteError
from fastapi import HTTPException


class _ProfileRuntime:
    def __init__(self, *, default_version: str, profiles: list[Any]) -> None:
        self.default_version = default_version
        self._profiles = list(profiles)

    def list_profiles(self) -> list[Any]:
        return list(self._profiles)

    def get_profile(self, version: str) -> Any | None:
        for item in self._profiles:
            if getattr(item, "version", None) == version:
                return item
        return None

    def serialize_profile(self, profile: Any) -> dict[str, Any]:
        return {
            "version": profile.version,
            "topicDomain": getattr(profile, "topic_domain", None),
            "metadata": dict(getattr(profile, "metadata", {}) or {}),
        }


class _RegistryProductRuntime:
    def __init__(self) -> None:
        self.raise_invalid_type = False
        self.release_item: dict[str, Any] | None = {"version": "p1"}

    async def list_releases(self, **kwargs: Any) -> list[dict[str, Any]]:
        if self.raise_invalid_type:
            raise ValueError("invalid_registry_type")
        return [{"kind": "release", **kwargs}]

    async def get_release(self, **kwargs: Any) -> dict[str, Any] | None:
        if self.raise_invalid_type:
            raise ValueError("invalid_registry_version")
        if self.release_item is None:
            return None
        return {**self.release_item, **kwargs}

    async def list_audits(self, **kwargs: Any) -> list[dict[str, Any]]:
        return [{"kind": "audit", **kwargs}]


class _TraceStore:
    def list_alert_outbox(self, **kwargs: Any) -> list[dict[str, Any]]:
        return [{"kind": "outbox", **kwargs}]


class BootstrapRegistryRouteHelpersTests(unittest.IsolatedAsyncioTestCase):
    def _runtime(self) -> SimpleNamespace:
        policy_profiles = [
            SimpleNamespace(version="policy-v1", topic_domain="science", metadata={})
        ]
        return SimpleNamespace(
            policy_registry_runtime=_ProfileRuntime(
                default_version="policy-v1",
                profiles=policy_profiles,
            ),
            prompt_registry_runtime=_ProfileRuntime(
                default_version="prompt-v1",
                profiles=[SimpleNamespace(version="prompt-v1")],
            ),
            tool_registry_runtime=_ProfileRuntime(
                default_version="tool-v1",
                profiles=[SimpleNamespace(version="tool-v1")],
            ),
            registry_product_runtime=_RegistryProductRuntime(),
            trace_store=_TraceStore(),
        )

    async def test_registry_route_guard_should_bridge_route_error(self) -> None:
        async def _raise_route_error() -> dict[str, Any]:
            raise RegistryRouteError(status_code=409, detail="registry_conflict")

        with self.assertRaises(HTTPException) as ctx:
            await run_registry_route_guard_for_runtime(_raise_route_error())

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail, "registry_conflict")

    async def test_profile_payload_helpers_should_call_ready_and_serialize(self) -> None:
        ready_calls = {"count": 0}

        async def _ensure_ready() -> None:
            ready_calls["count"] += 1

        profile = SimpleNamespace(version="v1")
        payload = await build_registry_profiles_payload_with_ready_for_runtime(
            ensure_registry_runtime_ready=_ensure_ready,
            list_profiles=lambda: [profile],
            default_version="v1",
            serializer=lambda item: {"version": item.version},
        )

        self.assertEqual(ready_calls, {"count": 1})
        self.assertEqual(payload["defaultVersion"], "v1")
        self.assertEqual(payload["items"], [{"version": "v1"}])
        with self.assertRaises(HTTPException) as ctx:
            build_registry_profile_payload_for_runtime(
                version="missing",
                get_profile=lambda _version: None,
                serializer=lambda item: {"version": item.version},
                not_found_detail="registry_not_found",
            )
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "registry_not_found")

    async def test_governance_pack_should_wire_registry_runtime_dependencies(self) -> None:
        runtime = self._runtime()

        async def _evaluate_dependency_health(*, policy_version: str) -> dict[str, Any]:
            return {"policyVersion": policy_version, "source": "dependency"}

        async def _evaluate_fairness_gate(*, policy_version: str) -> dict[str, Any]:
            return {"policyVersion": policy_version, "source": "fairness"}

        async def _list_audit_alerts(**kwargs: Any) -> list[Any]:
            return [{"kind": "alert", **kwargs}]

        def _resolve_family(**_kwargs: Any) -> tuple[str, bool, str | None]:
            return ("debate-general", True, None)

        pack = build_registry_governance_route_dependency_pack_for_runtime(
            runtime=runtime,
            registry_type_policy="policy",
            dependency_trend_status_values={"healthy", "blocked"},
            resolve_policy_domain_judge_family_state=_resolve_family,
            build_policy_domain_judge_family_overview=lambda **kwargs: kwargs,
            evaluate_policy_registry_dependency_health=_evaluate_dependency_health,
            evaluate_policy_release_fairness_gate=_evaluate_fairness_gate,
            list_audit_alerts=_list_audit_alerts,
        )

        self.assertEqual(pack.default_policy_version, "policy-v1")
        self.assertEqual(pack.policy_registry_type, "policy")
        self.assertEqual(pack.dependency_trend_status_values, {"healthy", "blocked"})
        serialized = pack.serialize_policy_profile(
            SimpleNamespace(version="policy-v1", topic_domain="science", metadata={})
        )
        self.assertEqual(serialized["metadata"]["domainJudgeFamily"], "debate-general")
        self.assertEqual(
            await pack.evaluate_policy_registry_dependency_health("policy-v2"),
            {"policyVersion": "policy-v2", "source": "dependency"},
        )
        self.assertEqual(
            await pack.evaluate_policy_release_fairness_gate("policy-v2"),
            {"policyVersion": "policy-v2", "source": "fairness"},
        )

    async def test_registry_release_helpers_should_preserve_error_semantics(self) -> None:
        runtime = self._runtime()

        releases = await build_registry_releases_payload_for_runtime(
            runtime=runtime,
            registry_type="policy",
            limit=2,
            include_payload=False,
        )
        self.assertEqual(releases["registryType"], "policy")
        self.assertEqual(releases["count"], 1)

        release = await build_registry_release_payload_for_runtime(
            runtime=runtime,
            registry_type="policy",
            version="policy-v1",
            not_found_detail="registry_release_not_found",
        )
        self.assertEqual(release["item"]["version"], "policy-v1")

        runtime.registry_product_runtime.release_item = None
        with self.assertRaises(HTTPException) as not_found_ctx:
            await build_registry_release_payload_for_runtime(
                runtime=runtime,
                registry_type="policy",
                version="missing",
                not_found_detail="registry_release_not_found",
            )
        self.assertEqual(not_found_ctx.exception.status_code, 404)

        runtime.registry_product_runtime.raise_invalid_type = True
        with self.assertRaises(HTTPException) as invalid_ctx:
            await build_registry_releases_payload_for_runtime(
                runtime=runtime,
                registry_type="unknown",
                limit=2,
                include_payload=False,
            )
        self.assertEqual(invalid_ctx.exception.status_code, 422)
        self.assertEqual(invalid_ctx.exception.detail, "invalid_registry_type")

    async def test_registry_audits_should_map_invalid_query_to_422(self) -> None:
        runtime = self._runtime()

        async def _list_audit_alerts(**_kwargs: Any) -> list[Any]:
            return []

        with self.assertRaises(HTTPException) as ctx:
            await build_registry_audits_payload_for_runtime(
                runtime=runtime,
                registry_audit_action_values={"bootstrap"},
                list_audit_alerts=_list_audit_alerts,
                registry_type="policy",
                action="publish",
                version=None,
                actor=None,
                gate_code=None,
                override_applied=None,
                include_gate_view=False,
                link_limit=5,
                offset=0,
                limit=10,
            )

        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail, "invalid_registry_audit_action")

    async def test_raise_registry_value_error_should_support_conflict(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            raise_registry_value_error(
                err=ValueError("stale_registry_version"),
                default_detail="registry_invalid",
                unprocessable_codes={"invalid_registry_version"},
                conflict_codes={"stale_registry_version"},
            )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail, "stale_registry_version")
