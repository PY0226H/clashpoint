from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from app.applications import bootstrap_ops_panel_replay_payload_helpers as helpers
from app.applications.panel_runtime_profile_contract import (
    PANEL_RUNTIME_READINESS_SWITCH_BLOCKERS,
)
from fastapi import HTTPException


class BootstrapOpsPanelReplayPayloadHelpersTests(unittest.IsolatedAsyncioTestCase):
    async def test_dispatch_receipt_payload_should_serialize_or_raise_404(self) -> None:
        receipt = SimpleNamespace(kind="phase")

        async def _get_dispatch_receipt(**kwargs: Any) -> Any | None:
            if kwargs["job_id"] == 42:
                return receipt
            return None

        with patch.object(
            helpers,
            "serialize_dispatch_receipt_v3",
            side_effect=lambda item: {"kind": item.kind},
        ):
            payload = await helpers.build_dispatch_receipt_payload_for_runtime(
                case_id=42,
                dispatch_type="phase",
                not_found_detail="receipt_not_found",
                get_dispatch_receipt=_get_dispatch_receipt,
            )
            with self.assertRaises(HTTPException) as ctx:
                await helpers.build_dispatch_receipt_payload_for_runtime(
                    case_id=99,
                    dispatch_type="phase",
                    not_found_detail="receipt_not_found",
                    get_dispatch_receipt=_get_dispatch_receipt,
                )

        self.assertEqual(payload, {"kind": "phase"})
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "receipt_not_found")

    async def test_shared_room_context_should_select_latest_receipt_scope(self) -> None:
        updated_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        phase_receipt = SimpleNamespace(
            job_id=42,
            scope_id=6,
            response={"winner": "con"},
            rubric_version="rubric-old",
            judge_policy_version="policy-old",
            topic_domain="science",
            retrieval_profile="strict",
            updated_at=updated_at,
        )
        final_receipt = SimpleNamespace(
            job_id=42,
            scope_id=7,
            response={
                "winner": "PRO",
                "reportPayload": {
                    "debateSummary": "summary",
                    "sideAnalysis": {"pro": "strong"},
                    "verdictReason": "reason",
                },
                "judgeTrace": {"policyRegistry": {"version": "policy-v2"}},
            },
            rubric_version="rubric-v2",
            judge_policy_version="policy-v1",
            topic_domain="law",
            retrieval_profile="balanced",
            updated_at=updated_at,
        )

        async def _list_dispatch_receipts(**kwargs: Any) -> list[Any]:
            if kwargs["dispatch_type"] == "phase":
                return [phase_receipt]
            return [final_receipt]

        async def _workflow_list_jobs(**_kwargs: Any) -> list[Any]:
            return [SimpleNamespace(session_id=9, job_id=42, scope_id=8, status="done")]

        with patch.object(
            helpers,
            "build_verdict_contract_v3",
            return_value={"winner": "draw", "reviewRequired": True},
        ):
            payload = await helpers.build_shared_room_context_for_runtime(
                session_id=9,
                case_id=42,
                list_dispatch_receipts=_list_dispatch_receipts,
                workflow_list_jobs=_workflow_list_jobs,
            )

        self.assertEqual(payload["source"], "shared_room_context_v1")
        self.assertEqual(payload["sessionId"], 9)
        self.assertEqual(payload["scopeId"], 7)
        self.assertEqual(payload["caseId"], 42)
        self.assertEqual(payload["latestDispatchType"], "final")
        self.assertEqual(payload["workflowStatus"], "done")
        self.assertEqual(payload["winnerHint"], "pro")
        self.assertEqual(payload["ruleVersion"], "policy-v2")
        self.assertEqual(payload["phaseReceiptCount"], 1)
        self.assertEqual(payload["finalReceiptCount"], 1)
        self.assertEqual(payload["updatedAt"], updated_at.isoformat())

    async def test_ops_read_model_pack_should_forward_runtime_dependencies(self) -> None:
        calls: dict[str, Any] = {}

        def _get_trace(case_id: int) -> dict[str, Any]:
            return {"caseId": case_id}

        async def _build_pack(**kwargs: Any) -> dict[str, Any]:
            calls["builder"] = kwargs
            return {"pack": kwargs["policy_version"]}

        async def _payload(**_kwargs: Any) -> dict[str, Any]:
            return {}

        runtime = SimpleNamespace(trace_store=SimpleNamespace(get_trace=_get_trace))
        normalize = lambda value: str(value or "unknown")

        with patch.object(
            helpers,
            "build_ops_read_model_pack_route_payload",
            side_effect=_build_pack,
        ):
            payload = await helpers.build_ops_read_model_pack_payload_for_runtime(
                trust_challenge_open_states={"requested"},
                judge_role_order=("judgeA", "judgeB"),
                normalize_fairness_gate_decision=normalize,
                x_ai_internal_key="key",
                dispatch_type="final",
                policy_version="policy-v1",
                window_days=7,
                top_limit=10,
                case_scan_limit=200,
                include_case_trust=True,
                trust_case_limit=5,
                dependency_limit=20,
                usage_preview_limit=10,
                release_limit=10,
                audit_limit=10,
                calibration_risk_limit=10,
                calibration_benchmark_limit=10,
                calibration_shadow_limit=10,
                panel_profile_scan_limit=50,
                panel_group_limit=10,
                panel_attention_limit=5,
                runtime=runtime,
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

        self.assertEqual(payload, {"pack": "policy-v1"})
        self.assertEqual(calls["builder"]["trust_challenge_open_states"], {"requested"})
        self.assertEqual(calls["builder"]["judge_role_order"], ("judgeA", "judgeB"))
        self.assertIs(calls["builder"]["get_trace"], _get_trace)
        self.assertIs(calls["builder"]["normalize_fairness_gate_decision"], normalize)
        self.assertIs(
            calls["builder"]["build_ops_read_model_pack_v5_payload_fn"],
            helpers.build_ops_read_model_pack_v5_payload,
        )

    async def test_panel_runtime_profiles_should_guard_and_forward_constants(self) -> None:
        calls: dict[str, Any] = {}

        async def _build_profiles(**kwargs: Any) -> dict[str, Any]:
            calls["builder"] = kwargs
            return {"limit": kwargs["limit"]}

        async def _guard(awaitable: Any) -> dict[str, Any]:
            payload = await awaitable
            calls["guarded"] = payload
            return {"guarded": payload}

        async def _list_fairness(**_kwargs: Any) -> dict[str, Any]:
            return {}

        normalize = lambda value: value or "unknown"

        with patch.object(
            helpers,
            "build_panel_runtime_profiles_route_payload_v3",
            side_effect=_build_profiles,
        ):
            payload = await helpers.build_panel_runtime_profiles_payload_for_runtime(
                panel_judge_ids=("judgeA",),
                panel_runtime_profile_source_values={"runtime"},
                panel_runtime_profile_sort_fields={"updated_at"},
                normalize_workflow_status=normalize,
                x_ai_internal_key=None,
                status=None,
                dispatch_type="final",
                winner=None,
                policy_version=None,
                has_open_review=None,
                gate_conclusion=None,
                challenge_state=None,
                review_required=None,
                panel_high_disagreement=None,
                judge_id=None,
                profile_source=None,
                profile_id=None,
                model_strategy=None,
                strategy_slot=None,
                domain_slot=None,
                sort_by="updated_at",
                sort_order="desc",
                offset=0,
                limit=20,
                list_judge_case_fairness=_list_fairness,
                run_panel_runtime_route_guard=_guard,
            )

        self.assertEqual(payload, {"guarded": {"limit": 20}})
        self.assertEqual(calls["guarded"], {"limit": 20})
        self.assertEqual(calls["builder"]["panel_judge_ids"], ("judgeA",))
        self.assertEqual(calls["builder"]["panel_runtime_profile_sort_fields"], {"updated_at"})
        self.assertIs(calls["builder"]["normalize_workflow_status"], normalize)
        self.assertIs(
            calls["builder"]["validate_panel_runtime_profile_contract"],
            helpers.validate_panel_runtime_profile_contract_v3,
        )

    async def test_panel_runtime_readiness_should_forward_summary_builder(self) -> None:
        calls: dict[str, Any] = {}

        async def _build_readiness(**kwargs: Any) -> dict[str, Any]:
            calls["builder"] = kwargs
            return {
                "generatedAt": "2026-04-28T00:00:00Z",
                "overview": {
                    "totalMatched": 0,
                    "scannedRecords": kwargs["profile_scan_limit"],
                    "scanTruncated": False,
                    "totalGroups": 0,
                    "attentionGroupCount": 0,
                    "readinessCounts": {"ready": 0, "watch": 0, "attention": 0},
                    "shadow": {
                        "enabledGroupCount": 0,
                        "blockedGroupCount": 0,
                        "watchGroupCount": 0,
                        "driftSignalGroupCount": 0,
                        "candidateModelGroupCount": 0,
                        "releaseGateSignalCounts": {
                            "ready": 0,
                            "watch": 0,
                            "blocked": 0,
                        },
                        "switchBlockerCounts": {
                            blocker: 0
                            for blocker in PANEL_RUNTIME_READINESS_SWITCH_BLOCKERS
                        },
                        "avgDecisionAgreement": 0.0,
                        "avgCostEstimate": 0.0,
                        "avgLatencyEstimate": 0.0,
                        "officialWinnerMutationAllowed": False,
                        "officialWinnerSemanticsChanged": False,
                        "autoSwitchAllowed": False,
                    },
                },
                "groups": [],
                "attentionGroups": [],
                "notes": [],
                "filters": {},
            }

        async def _guard(awaitable: Any) -> dict[str, Any]:
            payload = await awaitable
            calls["guarded"] = payload
            return payload

        async def _list_profiles(**_kwargs: Any) -> dict[str, Any]:
            return {}

        normalize = lambda value: value or "unknown"

        with patch.object(
            helpers,
            "build_panel_runtime_readiness_route_payload_v3",
            side_effect=_build_readiness,
        ):
            payload = await helpers.build_panel_runtime_readiness_payload_for_runtime(
                panel_judge_ids=("judgeA", "judgeB"),
                panel_runtime_profile_source_values={"runtime"},
                normalize_workflow_status=normalize,
                x_ai_internal_key=None,
                status=None,
                dispatch_type="final",
                winner=None,
                policy_version=None,
                has_open_review=None,
                gate_conclusion=None,
                challenge_state=None,
                review_required=None,
                panel_high_disagreement=None,
                judge_id=None,
                profile_source=None,
                profile_id=None,
                model_strategy=None,
                strategy_slot=None,
                domain_slot=None,
                profile_scan_limit=60,
                group_limit=10,
                attention_limit=5,
                list_panel_runtime_profiles=_list_profiles,
                run_panel_runtime_route_guard=_guard,
            )

        self.assertEqual(payload["overview"]["scannedRecords"], 60)
        self.assertEqual(calls["guarded"]["overview"]["scannedRecords"], 60)
        self.assertEqual(calls["builder"]["panel_judge_ids"], ("judgeA", "judgeB"))
        self.assertIs(
            calls["builder"]["build_panel_runtime_readiness_summary"],
            helpers.build_panel_runtime_readiness_summary_v3,
        )

    async def test_replay_report_should_guard_and_forward_serializers(self) -> None:
        calls: dict[str, Any] = {}

        async def _build_report(**kwargs: Any) -> dict[str, Any]:
            calls["builder"] = kwargs
            return {"caseId": kwargs["case_id"]}

        async def _guard(awaitable: Any) -> dict[str, Any]:
            return {"guarded": await awaitable}

        async def _get_claim(**_kwargs: Any) -> Any | None:
            return None

        with patch.object(
            helpers,
            "build_replay_report_route_payload_v3",
            side_effect=_build_report,
        ):
            payload = await helpers.build_replay_report_payload_for_runtime(
                case_id=42,
                get_trace=lambda case_id: {"caseId": case_id},
                get_claim_ledger_record=_get_claim,
                run_replay_read_guard=_guard,
            )

        self.assertEqual(payload, {"guarded": {"caseId": 42}})
        self.assertIs(
            calls["builder"]["build_replay_report_payload"],
            helpers.build_replay_report_payload_v3,
        )
        self.assertIs(
            calls["builder"]["serialize_claim_ledger_record"],
            helpers.serialize_claim_ledger_record_v3,
        )

    async def test_replay_reports_should_forward_query_normalizer(self) -> None:
        calls: dict[str, Any] = {}

        def _build_reports(**kwargs: Any) -> dict[str, Any]:
            calls["builder"] = kwargs
            return {"limit": kwargs["limit"]}

        normalize = lambda value: value
        list_traces = lambda **_kwargs: []

        with patch.object(
            helpers,
            "build_replay_reports_route_payload_v3",
            side_effect=_build_reports,
        ):
            payload = helpers.build_replay_reports_payload_for_runtime(
                status="completed",
                winner=None,
                callback_status=None,
                trace_id=None,
                created_after=None,
                created_before=None,
                has_audit_alert=None,
                limit=20,
                include_report=False,
                normalize_query_datetime=normalize,
                list_traces=list_traces,
            )

        self.assertEqual(payload, {"limit": 20})
        self.assertIs(calls["builder"]["normalize_query_datetime"], normalize)
        self.assertIs(calls["builder"]["trace_query_cls"], helpers.TraceQuery)
        self.assertIs(calls["builder"]["list_traces"], list_traces)
        self.assertIs(
            calls["builder"]["build_replay_reports_list_payload"],
            helpers.build_replay_reports_list_payload_v3,
        )
