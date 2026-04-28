from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any

from app.applications.route_group_ops_read_model_pack import (
    OpsReadModelPackRouteDependencies,
    register_ops_read_model_pack_routes,
)
from fastapi import FastAPI


class RouteGroupOpsReadModelPackTests(unittest.TestCase):
    def test_register_ops_read_model_pack_routes_should_expose_path_and_handle(
        self,
    ) -> None:
        app = FastAPI()
        runtime = SimpleNamespace(settings=SimpleNamespace())

        async def _payload(**_kwargs: Any) -> dict[str, Any]:
            return {}

        deps = OpsReadModelPackRouteDependencies(
            runtime=runtime,
            require_internal_key_fn=lambda _settings, _header: None,
            await_payload_or_raise_http_500=_payload,
            build_ops_read_model_pack_payload=_payload,
            get_judge_fairness_dashboard=_payload,
            get_registry_governance_overview=_payload,
            get_registry_prompt_tool_governance=_payload,
            get_policy_registry_dependency_health=_payload,
            get_judge_fairness_policy_calibration_advisor=_payload,
            get_panel_runtime_readiness=_payload,
            list_judge_courtroom_cases=_payload,
            list_judge_courtroom_drilldown_bundle=_payload,
            list_judge_evidence_claim_ops_queue=_payload,
            list_judge_trust_challenge_ops_queue=_payload,
            list_judge_review_jobs=_payload,
            simulate_policy_release_gate=_payload,
            get_judge_case_courtroom_read_model=_payload,
            get_judge_trust_public_verify=_payload,
        )

        handles = register_ops_read_model_pack_routes(app=app, deps=deps)

        paths = {route.path for route in app.routes}
        self.assertIn("/internal/judge/ops/read-model/pack", paths)
        self.assertIn("/internal/judge/ops/runtime-readiness", paths)
        self.assertEqual(
            handles.get_judge_ops_read_model_pack.__name__,
            "get_judge_ops_read_model_pack",
        )
        self.assertEqual(
            handles.get_judge_runtime_readiness.__name__,
            "get_judge_runtime_readiness",
        )
