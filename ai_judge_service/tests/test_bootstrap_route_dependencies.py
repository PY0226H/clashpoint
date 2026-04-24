from __future__ import annotations

import unittest
from typing import Any

from app.applications.bootstrap_route_dependencies import (
    build_registry_release_gate_dependencies,
    build_trust_challenge_common_dependencies,
)


class BootstrapRouteDependenciesTests(unittest.TestCase):
    def test_build_registry_release_gate_dependencies_should_keep_keys(self) -> None:
        async def _async_payload(**_kwargs: Any) -> dict[str, Any]:
            return {}

        async def _async_list(**_kwargs: Any) -> list[dict[str, Any]]:
            return []

        deps = build_registry_release_gate_dependencies(
            policy_registry_type="policy",
            evaluate_policy_registry_dependency_health=_async_payload,
            emit_registry_dependency_health_alert=_async_payload,
            resolve_registry_dependency_health_alerts=_async_list,
            evaluate_policy_release_fairness_gate=_async_payload,
            emit_registry_fairness_gate_alert=_async_payload,
        )

        self.assertEqual(deps["policy_registry_type"], "policy")
        self.assertIs(deps["evaluate_policy_registry_dependency_health"], _async_payload)
        self.assertIs(deps["resolve_registry_dependency_health_alerts"], _async_list)

    def test_build_trust_challenge_common_dependencies_should_keep_keys(self) -> None:
        async def _async_payload(**_kwargs: Any) -> dict[str, Any]:
            return {}

        async def _async_none(**_kwargs: Any) -> None:
            return None

        deps = build_trust_challenge_common_dependencies(
            resolve_report_context_for_case=_async_payload,
            workflow_get_job=_async_payload,
            workflow_append_event=_async_payload,
            workflow_mark_review_required=_async_none,
            build_trust_phasea_bundle=_async_payload,
            serialize_workflow_job=lambda _record: {},
            trust_challenge_event_type="trust_challenge_requested",
            trust_challenge_state_accepted="accepted",
            trust_challenge_state_under_review="under_review",
        )

        self.assertEqual(deps["trust_challenge_event_type"], "trust_challenge_requested")
        self.assertEqual(deps["trust_challenge_state_accepted"], "accepted")
        self.assertEqual(deps["trust_challenge_state_under_review"], "under_review")
