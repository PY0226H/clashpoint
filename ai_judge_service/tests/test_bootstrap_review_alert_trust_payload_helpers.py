from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from app.applications import bootstrap_review_alert_trust_payload_helpers as helpers
from app.applications.trust_read_routes import TrustReadRouteError
from fastapi import HTTPException


class BootstrapReviewAlertTrustPayloadHelpersTests(unittest.IsolatedAsyncioTestCase):
    async def test_transition_alert_status_should_run_review_guard(self) -> None:
        calls: dict[str, Any] = {}

        async def _build_transition(**kwargs: Any) -> dict[str, Any]:
            calls["builder"] = kwargs
            return {"transition": kwargs["alert_id"]}

        async def _guard(awaitable: Any) -> dict[str, Any]:
            payload = await awaitable
            calls["guard"] = payload
            return {"guarded": payload}

        with patch.object(
            helpers,
            "build_alert_status_transition_payload_v3",
            side_effect=_build_transition,
        ):
            payload = await helpers.transition_judge_alert_status_for_runtime(
                case_id=42,
                alert_id="alert-1",
                to_status="acked",
                actor="ops",
                reason="seen",
                transition_audit_alert=lambda **_kwargs: None,
                sync_audit_alert_to_facts=lambda **_kwargs: None,
                facts_transition_audit_alert=lambda **_kwargs: None,
                serialize_alert_item=lambda item: {"item": item},
                run_review_route_guard=_guard,
            )

        self.assertEqual(payload, {"guarded": {"transition": "alert-1"}})
        self.assertEqual(calls["builder"]["job_id"], 42)
        self.assertEqual(calls["builder"]["to_status"], "acked")
        self.assertEqual(calls["guard"], {"transition": "alert-1"})

    async def test_review_list_payload_should_forward_normalized_filters(self) -> None:
        calls: dict[str, Any] = {}

        def _normalize_filters(**kwargs: Any) -> dict[str, Any]:
            calls["normalize"] = kwargs
            return {
                "status": "reported",
                "dispatchType": "final",
                "riskLevel": "high",
                "slaBucket": "urgent",
                "challengeState": "requested",
                "trustReviewState": "pending_review",
                "unifiedPriorityLevel": "high",
                "sortBy": "updated_at",
                "sortOrder": "desc",
                "scanLimit": 25,
            }

        async def _build_review_list(**kwargs: Any) -> dict[str, Any]:
            calls["builder"] = kwargs
            return {"status": kwargs["normalized_status"], "limit": kwargs["limit"]}

        with (
            patch.object(
                helpers,
                "normalize_review_case_filters_v3",
                side_effect=_normalize_filters,
            ),
            patch.object(
                helpers,
                "build_review_cases_list_payload_v3",
                side_effect=_build_review_list,
            ),
        ):
            payload = await helpers.build_review_cases_list_payload_for_runtime(
                normalize_workflow_status=lambda value: value or "reported",
                workflow_statuses={"reported"},
                review_case_risk_level_values={"high"},
                review_case_sla_bucket_values={"urgent"},
                case_fairness_challenge_states={"requested"},
                trust_challenge_review_state_values={"pending_review"},
                trust_challenge_priority_level_values={"high"},
                review_case_sort_fields={"updated_at"},
                trust_challenge_open_states={"requested"},
                status="reported",
                dispatch_type="final",
                risk_level="high",
                sla_bucket="urgent",
                challenge_state="requested",
                trust_review_state="pending_review",
                unified_priority_level="high",
                sort_by="updated_at",
                sort_order="desc",
                scan_limit=25,
                limit=10,
                workflow_list_jobs=lambda **_kwargs: [],
                workflow_list_events=lambda **_kwargs: [],
                list_audit_alerts=lambda **_kwargs: [],
                get_trace=lambda _case_id: None,
                build_review_case_risk_profile=lambda **_kwargs: {},
                build_trust_challenge_priority_profile=lambda **_kwargs: {},
                build_review_trust_unified_priority_profile=lambda **_kwargs: {},
                serialize_workflow_job=lambda item: {"item": item},
            )

        self.assertEqual(payload, {"status": "reported", "limit": 10})
        self.assertEqual(calls["normalize"]["review_case_risk_level_values"], {"high"})
        self.assertEqual(calls["builder"]["normalized_dispatch_type"], "final")
        self.assertEqual(calls["builder"]["trust_challenge_open_states"], {"requested"})

    async def test_alert_ops_view_payload_should_forward_ops_constants(self) -> None:
        calls: dict[str, Any] = {}

        async def _build_alert_ops_view(**kwargs: Any) -> dict[str, Any]:
            calls["builder"] = kwargs
            return {"fieldsMode": kwargs["fields_mode"]}

        with patch.object(
            helpers,
            "build_alert_ops_view_payload_v3",
            side_effect=_build_alert_ops_view,
        ):
            payload = await helpers.build_alert_ops_view_payload_for_runtime(
                ops_registry_alert_types={"registry_fairness_gate_blocked"},
                ops_alert_status_values={"raised"},
                ops_alert_delivery_status_values={"pending"},
                ops_alert_fields_mode_values={"lite"},
                alert_type="registry_fairness_gate_blocked",
                status="raised",
                delivery_status="pending",
                registry_type="policy",
                policy_version="p1",
                gate_code="blocked",
                gate_actor="ops",
                override_applied=False,
                fields_mode="lite",
                include_trend=True,
                trend_window_minutes=60,
                trend_bucket_minutes=10,
                offset=0,
                limit=20,
                list_audit_alerts=lambda **_kwargs: [],
                list_alert_outbox=lambda **_kwargs: [],
            )

        self.assertEqual(payload, {"fieldsMode": "lite"})
        self.assertEqual(
            calls["builder"]["ops_registry_alert_types"],
            {"registry_fairness_gate_blocked"},
        )
        self.assertEqual(calls["builder"]["ops_alert_fields_mode_values"], {"lite"})

    async def test_trust_challenge_request_and_decision_should_forward_state_constants(self) -> None:
        calls: dict[str, Any] = {}

        async def _guard(awaitable: Any) -> dict[str, Any]:
            return await awaitable

        async def _build_request(**kwargs: Any) -> dict[str, Any]:
            calls["request"] = kwargs
            return {"requestState": kwargs["trust_challenge_state_requested"]}

        async def _build_decision(**kwargs: Any) -> dict[str, Any]:
            calls["decision"] = kwargs
            return {"closedState": kwargs["trust_challenge_state_closed"]}

        class _TransitionError(Exception):
            pass

        with (
            patch.object(
                helpers,
                "build_trust_challenge_request_payload_v3",
                side_effect=_build_request,
            ),
            patch.object(
                helpers,
                "build_trust_challenge_decision_payload_v3",
                side_effect=_build_decision,
            ),
        ):
            request_payload = await helpers.build_trust_challenge_request_payload_for_runtime(
                trust_challenge_state_requested="requested",
                case_id=42,
                dispatch_type="final",
                reason_code="evidence_gap",
                reason="missing citation",
                requested_by="ops",
                auto_accept=True,
                trust_challenge_common_dependencies={"shared_dep": "ok"},
                upsert_audit_alert=lambda **_kwargs: None,
                sync_audit_alert_to_facts=lambda **_kwargs: None,
                run_trust_challenge_guard=_guard,
            )
            decision_payload = await helpers.build_trust_challenge_decision_payload_for_runtime(
                trust_challenge_state_closed="closed",
                trust_challenge_state_verdict_upheld="verdict_upheld",
                trust_challenge_state_verdict_overturned="verdict_overturned",
                trust_challenge_state_draw_after_review="draw_after_review",
                trust_challenge_state_review_retained="review_retained",
                workflow_transition_error_cls=_TransitionError,
                case_id=42,
                challenge_id="chlg-42",
                dispatch_type="final",
                decision="approve",
                actor="ops",
                reason=None,
                trust_challenge_common_dependencies={"shared_dep": "ok"},
                workflow_mark_completed=lambda **_kwargs: None,
                workflow_mark_draw_pending_vote=lambda **_kwargs: None,
                resolve_open_alerts_for_review=lambda **_kwargs: [],
                run_trust_challenge_guard=_guard,
            )

        self.assertEqual(request_payload, {"requestState": "requested"})
        self.assertEqual(decision_payload, {"closedState": "closed"})
        self.assertEqual(calls["request"]["shared_dep"], "ok")
        self.assertTrue(callable(calls["request"]["new_challenge_id"]))
        self.assertEqual(
            calls["decision"]["workflow_transition_error_cls"],
            _TransitionError,
        )
        self.assertEqual(
            calls["decision"]["trust_challenge_state_verdict_overturned"],
            "verdict_overturned",
        )
        self.assertEqual(
            calls["decision"]["trust_challenge_state_review_retained"],
            "review_retained",
        )

    async def test_trust_read_sync_wrappers_should_map_route_error(self) -> None:
        async def _bundle(**_kwargs: Any) -> dict[str, Any]:
            return {"bundle": True}

        def _raise_route_error(**_kwargs: Any) -> dict[str, Any]:
            raise TrustReadRouteError(status_code=500, detail={"code": "bad_trust"})

        with patch.object(
            helpers,
            "build_validated_trust_item_route_payload_v3",
            side_effect=_raise_route_error,
        ):
            with self.assertRaises(HTTPException) as ctx:
                await helpers.build_validated_trust_item_payload_for_runtime(
                    case_id=42,
                    dispatch_type="final",
                    item_key="commitment",
                    validate_contract=lambda _payload: None,
                    violation_code="contract_invalid",
                    build_trust_phasea_bundle=_bundle,
                )

        self.assertEqual(ctx.exception.status_code, 500)
        self.assertEqual(ctx.exception.detail, {"code": "bad_trust"})

    async def test_trust_audit_and_public_verify_should_use_phase_bundle(self) -> None:
        calls: dict[str, Any] = {}

        async def _bundle(**kwargs: Any) -> dict[str, Any]:
            calls["bundle_call"] = kwargs
            return {"bundle": True}

        def _audit_builder(**kwargs: Any) -> dict[str, Any]:
            calls["audit"] = kwargs
            return {"audit": kwargs["include_payload"]}

        def _public_builder(**kwargs: Any) -> dict[str, Any]:
            calls["public"] = kwargs
            return {"public": kwargs["case_id"]}

        with (
            patch.object(
                helpers,
                "build_trust_audit_anchor_route_payload_v3",
                side_effect=_audit_builder,
            ),
            patch.object(
                helpers,
                "build_trust_public_verify_bundle_payload_v3",
                side_effect=_public_builder,
            ),
        ):
            audit_payload = await helpers.build_trust_audit_anchor_payload_for_runtime(
                case_id=42,
                dispatch_type="final",
                include_payload=True,
                build_trust_phasea_bundle=_bundle,
                build_audit_anchor_export=lambda **_kwargs: {},
                validate_contract=lambda _payload: None,
                violation_code="audit_invalid",
            )
            public_payload = await helpers.build_trust_public_verify_payload_for_runtime(
                case_id=42,
                dispatch_type="final",
                build_trust_phasea_bundle=_bundle,
                build_audit_anchor_export=lambda **_kwargs: {},
                build_public_verify_payload=lambda **_kwargs: {},
                validate_contract=lambda _payload: None,
                violation_code="public_invalid",
            )

        self.assertEqual(audit_payload, {"audit": True})
        self.assertEqual(public_payload, {"public": 42})
        self.assertEqual(calls["bundle_call"], {"case_id": 42, "dispatch_type": "final"})
        self.assertEqual(calls["audit"]["bundle"], {"bundle": True})
        self.assertEqual(calls["public"]["bundle"], {"bundle": True})
