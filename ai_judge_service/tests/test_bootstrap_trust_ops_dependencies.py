from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from app.applications import bootstrap_trust_ops_dependencies as bootstrap
from app.applications.route_group_ops_read_model_pack import (
    OpsReadModelPackRouteDependencies,
)
from app.applications.route_group_trust import TrustRouteDependencies


async def _payload(**_kwargs: Any) -> dict[str, Any]:
    return {}


def _sync_payload(**_kwargs: Any) -> dict[str, Any]:
    return {}


class BootstrapTrustOpsDependenciesTests(unittest.TestCase):
    def test_build_trust_runtime_dependency_pack_should_refresh_registry(self) -> None:
        calls: dict[str, Any] = {}

        async def _get_snapshot(**kwargs: Any) -> None:
            calls["get_snapshot"] = dict(kwargs)
            return None

        async def _upsert_snapshot(**kwargs: Any) -> dict[str, Any]:
            calls["upsert_snapshot"] = dict(kwargs)
            return {"upserted": True}

        async def _write_registry(**kwargs: Any) -> dict[str, Any]:
            calls["write_registry"] = dict(kwargs)
            return {"caseId": kwargs["case_id"], "dispatchType": kwargs["dispatch_type"]}

        async def _resolve_context(**kwargs: Any) -> dict[str, Any]:
            calls["resolve_context"] = dict(kwargs)
            return {
                "dispatchType": "final",
                "traceId": "trace-9701",
                "requestSnapshot": {"traceId": "trace-9701"},
                "reportPayload": {"winner": "pro"},
            }

        async def _workflow_get_job(**kwargs: Any) -> Any:
            calls["workflow_get_job"] = dict(kwargs)
            return SimpleNamespace(status="review_required")

        async def _workflow_list_events(**kwargs: Any) -> list[Any]:
            calls["workflow_list_events"] = dict(kwargs)
            return [{"eventSeq": 1}]

        async def _list_audit_alerts(**kwargs: Any) -> list[Any]:
            calls["list_audit_alerts"] = dict(kwargs)
            return [{"alertId": "a1"}]

        runtime = SimpleNamespace(
            settings=SimpleNamespace(provider="mock"),
            workflow_runtime=SimpleNamespace(
                trust_registry=SimpleNamespace(
                    get_trust_registry_snapshot=_get_snapshot,
                    upsert_trust_registry_snapshot=_upsert_snapshot,
                )
            ),
            trace_store_boundaries=SimpleNamespace(artifact_store=object()),
        )

        with patch.object(
            bootstrap,
            "write_trust_registry_snapshot_for_report",
            side_effect=_write_registry,
        ):
            pack = bootstrap.build_trust_runtime_dependency_pack_for_runtime(
                runtime=runtime,
                get_dispatch_receipt=_payload,
                workflow_get_job=_workflow_get_job,
                workflow_list_events=_workflow_list_events,
                list_audit_alerts=_list_audit_alerts,
                serialize_workflow_job=lambda row: {"status": row.status},
                run_trust_read_guard=lambda awaitable: awaitable,
                resolve_report_context_for_case=_resolve_context,
                build_trust_phasea_bundle_for_runtime=_payload,
            )

        self.assertIs(pack.get_trust_registry_snapshot, _get_snapshot)
        payload = asyncio.run(
            pack.refresh_trust_registry_snapshot_for_case(
                case_id=9701,
                dispatch_type="auto",
            )
        )
        self.assertEqual(payload["caseId"], 9701)
        self.assertEqual(calls["resolve_context"]["not_found_detail"], "trust_receipt_not_found")
        self.assertEqual(calls["workflow_get_job"]["job_id"], 9701)
        self.assertEqual(calls["list_audit_alerts"]["limit"], 200)
        self.assertEqual(calls["write_registry"]["workflow_status"], "review_required")
        self.assertEqual(calls["write_registry"]["workflow_snapshot"], {"status": "review_required"})

    def test_build_trust_route_dependencies_should_attach_contracts_and_callbacks(self) -> None:
        runtime = SimpleNamespace(settings=SimpleNamespace())
        deps = bootstrap.build_trust_route_dependencies_for_runtime(
            runtime=runtime,
            require_internal_key_fn=lambda _settings, _key: None,
            build_validated_trust_item_payload=_payload,
            build_trust_challenge_ops_queue_payload=_payload,
            build_trust_challenge_request_payload=_payload,
            build_trust_challenge_decision_payload=_payload,
            build_trust_audit_anchor_payload=_payload,
            build_trust_public_verify_payload=_payload,
            run_trust_read_guard=lambda awaitable: awaitable,
            build_trust_phasea_bundle=_payload,
            get_dispatch_receipt=_payload,
            workflow_list_jobs=lambda **_kwargs: asyncio.sleep(0, result=[]),
            get_trace=lambda _case_id: None,
            build_trust_challenge_priority_profile=_sync_payload,
            serialize_workflow_job=lambda _row: {},
            build_trust_challenge_action_hints=_sync_payload,
            run_trust_challenge_guard=lambda awaitable: awaitable,
            trust_challenge_common_dependencies={"ok": True},
            upsert_audit_alert=_payload,
            sync_audit_alert_to_facts=_payload,
            workflow_mark_completed=lambda **_kwargs: asyncio.sleep(0),
            workflow_mark_draw_pending_vote=_payload,
            resolve_open_alerts_for_review=lambda **_kwargs: asyncio.sleep(0, result=[]),
        )

        self.assertIsInstance(deps, TrustRouteDependencies)
        self.assertIs(deps.runtime, runtime)
        self.assertIs(deps.build_validated_trust_item_payload, _payload)
        self.assertEqual(deps.trust_challenge_common_dependencies, {"ok": True})
        self.assertIs(deps.build_audit_anchor_export, bootstrap.build_audit_anchor_export)
        self.assertIs(
            deps.build_public_verify_payload,
            bootstrap.build_public_trust_verify_payload,
        )
        self.assertIs(
            deps.validate_trust_public_verify_contract,
            bootstrap.validate_trust_public_verify_contract,
        )

    def test_build_ops_read_model_pack_route_dependencies_should_forward_handles(self) -> None:
        runtime = SimpleNamespace(settings=SimpleNamespace())
        fairness_handles = SimpleNamespace(
            get_judge_fairness_dashboard=_payload,
            get_judge_fairness_policy_calibration_advisor=_payload,
        )
        registry_handles = SimpleNamespace(
            get_registry_governance_overview=_payload,
            get_registry_prompt_tool_governance=_payload,
            get_policy_registry_dependency_health=_payload,
            simulate_policy_release_gate=_payload,
        )
        panel_handles = SimpleNamespace(get_panel_runtime_readiness=_payload)
        case_handles = SimpleNamespace(
            list_judge_courtroom_cases=_payload,
            list_judge_courtroom_drilldown_bundle=_payload,
            list_judge_evidence_claim_ops_queue=_payload,
            get_judge_case_courtroom_read_model=_payload,
        )
        trust_handles = SimpleNamespace(
            list_judge_trust_challenge_ops_queue=_payload,
            get_judge_trust_public_verify=_payload,
        )
        review_handles = SimpleNamespace(list_judge_review_jobs=_payload)

        deps = bootstrap.build_ops_read_model_pack_route_dependencies_for_runtime(
            runtime=runtime,
            require_internal_key_fn=lambda _settings, _key: None,
            await_payload_or_raise_http_500=_payload,
            build_ops_read_model_pack_payload=_payload,
            fairness_route_handles=fairness_handles,
            registry_route_handles=registry_handles,
            panel_runtime_route_handles=panel_handles,
            case_read_route_handles=case_handles,
            trust_route_handles=trust_handles,
            review_route_handles=review_handles,
        )

        self.assertIsInstance(deps, OpsReadModelPackRouteDependencies)
        self.assertIs(deps.get_judge_fairness_dashboard, _payload)
        self.assertIs(deps.get_registry_governance_overview, _payload)
        self.assertIs(deps.get_panel_runtime_readiness, _payload)
        self.assertIs(deps.list_judge_trust_challenge_ops_queue, _payload)
        self.assertIs(deps.list_judge_review_jobs, _payload)
        self.assertIs(deps.get_judge_trust_public_verify, _payload)


if __name__ == "__main__":
    unittest.main()
