from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any

from app.applications.route_group_judge_command import (
    JudgeCommandRouteDependencies,
    register_judge_command_routes,
)
from fastapi import FastAPI


class RouteGroupJudgeCommandTests(unittest.TestCase):
    def test_register_judge_command_routes_should_expose_command_paths(self) -> None:
        app = FastAPI()
        runtime = SimpleNamespace(settings=SimpleNamespace(), trace_store=SimpleNamespace())

        async def _payload(**_kwargs: Any) -> dict[str, Any]:
            return {}

        async def _list_payload(**_kwargs: Any) -> list[Any]:
            return []

        async def _none(**_kwargs: Any) -> None:
            return None

        def _sync_payload(**_kwargs: Any) -> dict[str, Any]:
            return {}

        deps = JudgeCommandRouteDependencies(
            runtime=runtime,
            require_internal_key_fn=lambda _settings, _header: None,
            read_json_object_or_raise_422=_payload,
            run_judge_command_route_guard=lambda awaitable: awaitable,
            ensure_registry_runtime_ready=_none,
            resolve_idempotency_or_raise=_sync_payload,
            resolve_policy_profile=_sync_payload,
            resolve_prompt_profile=_sync_payload,
            resolve_tool_profile=_sync_payload,
            workflow_get_job=_payload,
            workflow_register_and_mark_case_built=_payload,
            serialize_workflow_job=lambda _job: {},
            extract_dispatch_meta_from_raw=_sync_payload,
            extract_receipt_dims_from_raw=_sync_payload,
            workflow_register_and_mark_blinded=_payload,
            invoke_phase_failed_callback_with_retry=_payload,
            invoke_final_failed_callback_with_retry=_payload,
            persist_dispatch_receipt=_none,
            workflow_mark_failed=_none,
            build_phase_report_payload=_payload,
            build_final_report_payload=_sync_payload,
            attach_judge_agent_runtime_trace=_none,
            attach_policy_trace_snapshot=lambda **_kwargs: None,
            upsert_claim_ledger_record=_payload,
            invoke_callback_with_retry=_none,
            workflow_mark_completed=_none,
            workflow_mark_review_required=_none,
            list_dispatch_receipts=_list_payload,
            resolve_panel_runtime_profiles=lambda **_kwargs: {},
            sync_audit_alert_to_facts=_payload,
            get_dispatch_receipt=_payload,
            build_dispatch_receipt_payload=_payload,
            validate_final_report_payload_contract=lambda **_kwargs: None,
            validate_phase_dispatch_request=lambda **_kwargs: None,
            validate_final_dispatch_request=lambda **_kwargs: None,
        )

        register_judge_command_routes(app=app, deps=deps)

        paths = {route.path for route in app.routes}
        self.assertIn("/internal/judge/cases", paths)
        self.assertIn("/internal/judge/v3/phase/dispatch", paths)
        self.assertIn("/internal/judge/v3/final/dispatch", paths)
        self.assertIn("/internal/judge/v3/phase/cases/{case_id}/receipt", paths)
        self.assertIn("/internal/judge/v3/final/cases/{case_id}/receipt", paths)
