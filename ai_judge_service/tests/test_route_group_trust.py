from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any

from app.applications.route_group_trust import (
    TrustRouteDependencies,
    register_trust_routes,
)
from fastapi import FastAPI


class RouteGroupTrustTests(unittest.TestCase):
    def test_register_trust_routes_should_expose_paths_and_handles(self) -> None:
        app = FastAPI()
        runtime = SimpleNamespace(settings=SimpleNamespace())

        async def _payload(**_kwargs: Any) -> dict[str, Any]:
            return {}

        async def _list_payload(**_kwargs: Any) -> list[Any]:
            return []

        async def _none_payload(**_kwargs: Any) -> None:
            return None

        def _sync_payload(**_kwargs: Any) -> dict[str, Any]:
            return {}

        deps = TrustRouteDependencies(
            runtime=runtime,
            require_internal_key_fn=lambda _settings, _header: None,
            build_validated_trust_item_payload=_payload,
            build_trust_challenge_ops_queue_payload=_payload,
            build_trust_challenge_public_status_payload=_payload,
            build_trust_challenge_request_payload=_payload,
            build_trust_challenge_decision_payload=_payload,
            build_trust_audit_anchor_payload=_payload,
            build_trust_public_verify_payload=_payload,
            run_trust_read_guard=lambda awaitable: awaitable,
            build_trust_phasea_bundle=_payload,
            build_audit_anchor_export=_sync_payload,
            build_public_verify_payload=_sync_payload,
            verify_report_attestation=_sync_payload,
            get_dispatch_receipt=_payload,
            workflow_list_jobs=_list_payload,
            get_trace=_sync_payload,
            build_trust_challenge_priority_profile=_sync_payload,
            serialize_workflow_job=lambda _record: {},
            build_trust_challenge_action_hints=_sync_payload,
            run_trust_challenge_guard=lambda awaitable: awaitable,
            trust_challenge_common_dependencies={},
            upsert_audit_alert=_sync_payload,
            sync_audit_alert_to_facts=_payload,
            workflow_mark_completed=_none_payload,
            workflow_mark_draw_pending_vote=_none_payload,
            resolve_open_alerts_for_review=_list_payload,
            validate_trust_commitment_contract=lambda _payload: None,
            validate_trust_verdict_attestation_contract=lambda _payload: None,
            validate_trust_challenge_review_contract=lambda _payload: None,
            validate_trust_challenge_public_contract=lambda _payload: None,
            validate_trust_kernel_version_contract=lambda _payload: None,
            validate_trust_audit_anchor_contract=lambda _payload: None,
            validate_trust_public_verify_contract=lambda _payload: None,
        )

        handles = register_trust_routes(app=app, deps=deps)

        paths = {route.path for route in app.routes}
        self.assertIn("/internal/judge/cases/{case_id}/trust/commitment", paths)
        self.assertIn(
            "/internal/judge/cases/{case_id}/trust/verdict-attestation",
            paths,
        )
        self.assertIn("/internal/judge/cases/{case_id}/trust/challenges", paths)
        self.assertIn(
            "/internal/judge/cases/{case_id}/trust/challenges/public-status",
            paths,
        )
        self.assertIn("/internal/judge/trust/challenges/ops-queue", paths)
        self.assertIn(
            "/internal/judge/cases/{case_id}/trust/challenges/request",
            paths,
        )
        self.assertIn(
            "/internal/judge/cases/{case_id}/trust/challenges/{challenge_id}/decision",
            paths,
        )
        self.assertIn("/internal/judge/cases/{case_id}/trust/kernel-version", paths)
        self.assertIn("/internal/judge/cases/{case_id}/trust/audit-anchor", paths)
        self.assertIn("/internal/judge/cases/{case_id}/trust/public-verify", paths)
        self.assertIn("/internal/judge/cases/{case_id}/attestation/verify", paths)
        self.assertEqual(
            handles.list_judge_trust_challenge_ops_queue.__name__,
            "list_judge_trust_challenge_ops_queue",
        )
        self.assertEqual(
            handles.get_judge_trust_challenge_public_status.__name__,
            "get_judge_trust_challenge_public_status",
        )
        self.assertEqual(
            handles.get_judge_trust_public_verify.__name__,
            "get_judge_trust_public_verify",
        )
