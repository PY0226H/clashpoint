from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from app.app_factory import create_app, create_runtime
from app.applications import (
    build_final_report_payload as build_final_report_payload_v3_final,
)

from tests.app_factory_test_helpers import (
    AppFactoryRouteTestMixin,
)
from tests.app_factory_test_helpers import (
    build_case_create_request as _build_case_create_request,
)
from tests.app_factory_test_helpers import (
    build_final_request as _build_final_request,
)
from tests.app_factory_test_helpers import (
    build_phase_request as _build_phase_request,
)
from tests.app_factory_test_helpers import (
    build_settings as _build_settings,
)
from tests.app_factory_test_helpers import (
    unique_case_id as _unique_case_id,
)


class AppFactoryCaseReadRouteTests(
    AppFactoryRouteTestMixin,
    unittest.IsolatedAsyncioTestCase,
):

    async def test_case_detail_route_should_aggregate_case_snapshot(self) -> None:
        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)

        case_id = _unique_case_id(33)
        case_req = _build_case_create_request(
            case_id=case_id,
            idempotency_key=f"case:{case_id}",
        )
        case_resp = await self._post_json(
            app=app,
            path="/internal/judge/cases",
            payload=case_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(case_resp.status_code, 200)

        phase_req = _build_phase_request(case_id=case_id, idempotency_key=f"phase:{case_id}")
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(case_id=case_id, idempotency_key=f"final:{case_id}")
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        detail_resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(detail_resp.status_code, 200)
        detail_payload = detail_resp.json()
        self.assertEqual(detail_payload["caseId"], case_id)
        self.assertEqual(detail_payload["workflow"]["status"], "callback_reported")
        self.assertEqual(detail_payload["latestDispatchType"], "final")
        self.assertIsNotNone(detail_payload["receipts"]["phase"])
        self.assertIsNotNone(detail_payload["receipts"]["final"])
        self.assertIn(detail_payload["winner"], {"pro", "con", "draw"})
        self.assertIn("verdictContract", detail_payload)
        self.assertEqual(
            detail_payload["verdictContract"]["winner"],
            detail_payload["winner"],
        )
        self.assertIn("trustAttestation", detail_payload["reportPayload"])
        self.assertIn("caseEvidence", detail_payload)
        case_evidence = detail_payload["caseEvidence"]
        self.assertTrue(case_evidence["hasCaseDossier"])
        self.assertTrue(case_evidence["hasClaimGraph"])
        self.assertTrue(case_evidence["hasEvidenceLedger"])
        self.assertTrue(case_evidence["hasVerdictLedger"])
        self.assertTrue(case_evidence["hasOpinionPack"])
        self.assertTrue(case_evidence["hasTrustAttestation"])
        self.assertIsInstance(case_evidence["caseDossier"], dict)
        self.assertEqual(case_evidence["caseDossier"]["dispatchType"], "final")
        self.assertEqual(
            case_evidence["caseDossier"]["phase"]["startNo"],
            final_req.phase_start_no,
        )
        self.assertEqual(
            case_evidence["caseDossier"]["phase"]["endNo"],
            final_req.phase_end_no,
        )
        self.assertIsInstance(case_evidence["claimGraph"], dict)
        self.assertIsInstance(case_evidence["claimGraphSummary"], dict)
        self.assertIsInstance(case_evidence["evidenceLedger"], dict)
        self.assertIsInstance(case_evidence["evidenceLedger"]["entries"], list)
        self.assertIsInstance(case_evidence["evidenceLedger"]["sourceCitations"], list)
        self.assertIsInstance(case_evidence["evidenceLedger"]["conflictSources"], list)
        self.assertFalse(
            bool(case_evidence["evidenceLedger"]["bundleMeta"]["officialVerdictAuthority"])
        )
        self.assertIsInstance(case_evidence["verdictLedger"], dict)
        self.assertIsInstance(case_evidence["opinionPack"], dict)
        self.assertIsInstance(case_evidence["policySnapshot"], dict)
        self.assertTrue(str(case_evidence["policyVersion"] or "").strip())
        self.assertIsInstance(case_evidence["promptSnapshot"], dict)
        self.assertTrue(str(case_evidence["promptVersion"] or "").strip())
        self.assertIsInstance(case_evidence["toolSnapshot"], dict)
        self.assertTrue(str(case_evidence["toolsetVersion"] or "").strip())
        self.assertEqual(case_evidence["trustAttestation"]["dispatchType"], "final")
        self.assertIsInstance(case_evidence["fairnessSummary"], dict)
        self.assertIsInstance(case_evidence["verdictEvidenceRefs"], list)
        self.assertTrue(
            all(
                isinstance(item, dict) and str(item.get("evidenceId") or "").strip()
                for item in case_evidence["verdictEvidenceRefs"]
            )
        )
        self.assertIn("auditSummary", case_evidence)
        self.assertEqual(
            case_evidence["auditSummary"]["alertCount"],
            len(case_evidence["auditSummary"]["auditAlerts"]),
        )
        self.assertTrue(case_evidence["hasClaimLedger"])
        self.assertEqual(case_evidence["claimLedger"]["dispatchType"], "final")
        self.assertEqual(detail_payload["judgeCore"]["stage"], "reported")
        self.assertEqual(detail_payload["judgeCore"]["version"], "v1")
        self.assertGreaterEqual(len(detail_payload["events"]), 2)

    async def test_case_detail_route_should_return_500_when_contract_validation_fails(
        self,
    ) -> None:
        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)

        case_id = _unique_case_id(9341)
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=_build_final_request(
                case_id=case_id,
                idempotency_key=f"final:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        with patch(
            "app.app_factory.validate_case_overview_contract_v3",
            side_effect=ValueError("case_overview_missing_keys:caseEvidence"),
        ):
            resp = await self._get(
                app=app,
                path=f"/internal/judge/cases/{case_id}",
                internal_key=runtime.settings.ai_internal_key,
            )

        self.assertEqual(resp.status_code, 500)
        detail = resp.json()["detail"]
        self.assertEqual(detail["code"], "case_overview_contract_violation")
        self.assertIn("case_overview_missing_keys:caseEvidence", detail["message"])

    async def test_courtroom_read_model_route_should_aggregate_case_view(self) -> None:
        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)

        case_id = _unique_case_id(9340)
        final_req = _build_final_request(case_id=case_id, idempotency_key=f"final:{case_id}")
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        read_resp = await self._get(
            app=app,
            path=(
                f"/internal/judge/cases/{case_id}/courtroom-read-model"
                "?dispatch_type=auto&include_events=true&include_alerts=false"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(read_resp.status_code, 200)
        payload = read_resp.json()
        self.assertEqual(payload["caseId"], case_id)
        self.assertEqual(payload["dispatchType"], "final")
        self.assertTrue(str(payload["traceId"] or "").strip())
        self.assertEqual(payload["filters"]["dispatchType"], "final")
        self.assertTrue(payload["filters"]["includeEvents"])
        self.assertFalse(payload["filters"]["includeAlerts"])
        self.assertEqual(payload["alerts"], [])
        self.assertEqual(len(payload["events"]), payload["eventCount"])

        courtroom = payload["courtroom"]
        self.assertEqual(
            courtroom["recorder"]["caseDossier"]["dispatchType"],
            "final",
        )
        self.assertIsInstance(courtroom["claim"]["claimGraph"], dict)
        self.assertIsInstance(courtroom["claim"]["claimGraphSummary"], dict)
        self.assertIsInstance(courtroom["claim"]["keyClaimsBySide"], dict)
        self.assertIsInstance(courtroom["evidence"]["evidenceLedger"], dict)
        self.assertIsInstance(courtroom["evidence"]["decisiveEvidenceRefs"], list)
        self.assertIsInstance(courtroom["panel"]["panelDecisions"], dict)
        self.assertEqual(len(courtroom["panel"]["courtroomRoles"]), 8)
        self.assertIsInstance(courtroom["fairness"]["summary"], dict)
        self.assertIn(
            courtroom["fairness"]["gateDecision"],
            {"pass_through", "blocked_to_draw"},
        )
        self.assertIsInstance(courtroom["opinion"]["userReport"], dict)
        self.assertIsInstance(courtroom["governance"]["policySnapshot"], dict)
        self.assertEqual(courtroom["governance"]["trustAttestation"]["dispatchType"], "final")
        self.assertIn(payload["report"]["winner"], {"pro", "con", "draw"})

    async def test_courtroom_read_model_route_should_return_404_when_case_missing(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)

        missing_resp = await self._get(
            app=app,
            path="/internal/judge/cases/999902/courtroom-read-model",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(missing_resp.status_code, 404)
        self.assertIn("courtroom_case_not_found", missing_resp.text)

    async def test_courtroom_read_model_route_should_return_500_when_contract_validation_fails(
        self,
    ) -> None:
        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)
        case_id = _unique_case_id(9342)
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=_build_final_request(
                case_id=case_id,
                idempotency_key=f"final:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        with patch(
            "app.app_factory.validate_courtroom_read_model_contract_v3",
            side_effect=ValueError("courtroom_read_model_missing_keys:report"),
        ):
            resp = await self._get(
                app=app,
                path=f"/internal/judge/cases/{case_id}/courtroom-read-model?dispatch_type=final",
                internal_key=runtime.settings.ai_internal_key,
            )

        self.assertEqual(resp.status_code, 500)
        detail = resp.json()["detail"]
        self.assertEqual(detail["code"], "courtroom_read_model_contract_violation")
        self.assertIn("courtroom_read_model_missing_keys:report", detail["message"])

    async def test_courtroom_cases_route_should_support_filters_sorting_and_pagination(self) -> None:
        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)

        high_case_id = _unique_case_id(9510)
        mid_case_id = _unique_case_id(9511)
        low_case_id = _unique_case_id(9512)
        case_overrides: dict[int, dict[str, Any]] = {
            high_case_id: {
                "reviewRequired": True,
                "fairnessSummary": {
                    "phase": "phase2",
                    "panelHighDisagreement": True,
                    "reviewRequired": True,
                    "gateDecision": "blocked_to_draw",
                    "reviewReasons": ["judge_panel_high_disagreement"],
                },
                "verdictLedger": {
                    "arbitration": {
                        "reviewRequired": True,
                        "gateDecision": "blocked_to_draw",
                    },
                },
                "errorCodes": [
                    "judge_panel_high_disagreement",
                    "fairness_gate_review_required",
                ],
                "auditAlerts": [{"type": "judge_panel_high_disagreement"}],
                "degradationLevel": 1,
            },
            mid_case_id: {
                "fairnessSummary": {
                    "phase": "phase2",
                    "panelHighDisagreement": False,
                    "reviewRequired": False,
                },
                "errorCodes": ["manual_watch"],
                "auditAlerts": [],
                "degradationLevel": 0,
            },
            low_case_id: {
                "fairnessSummary": {
                    "phase": "phase2",
                    "panelHighDisagreement": False,
                    "reviewRequired": False,
                },
                "errorCodes": [],
                "auditAlerts": [],
                "degradationLevel": 0,
            },
        }

        def _build_custom_final_payload(
            *,
            request,
            phase_receipts=None,
            fairness_thresholds=None,
            panel_runtime_profiles=None,
            list_dispatch_receipts=None,
            build_final_report_payload=None,
            judge_style_mode=None,
            **_unused,
        ):
            receipts = (
                list(phase_receipts)
                if phase_receipts is not None
                else list(
                    list_dispatch_receipts(
                        dispatch_type="phase",
                        session_id=request.session_id,
                        status="reported",
                        limit=1000,
                    )
                )
                if callable(list_dispatch_receipts)
                else []
            )
            payload = (
                build_final_report_payload
                if callable(build_final_report_payload)
                else build_final_report_payload_v3_final
            )(
                request=request,
                phase_receipts=receipts,
                judge_style_mode=judge_style_mode,
                fairness_thresholds=fairness_thresholds,
                panel_runtime_profiles=panel_runtime_profiles,
            )
            override = case_overrides.get(int(request.case_id), {})
            if "winner" in override:
                payload["winner"] = override["winner"]
            if "reviewRequired" in override:
                payload["reviewRequired"] = bool(override["reviewRequired"])
            if "fairnessSummary" in override:
                fairness_summary = (
                    payload.get("fairnessSummary")
                    if isinstance(payload.get("fairnessSummary"), dict)
                    else {}
                )
                fairness_summary.update(override["fairnessSummary"])
                payload["fairnessSummary"] = fairness_summary
            if "verdictLedger" in override:
                verdict_ledger = (
                    payload.get("verdictLedger")
                    if isinstance(payload.get("verdictLedger"), dict)
                    else {}
                )
                ledger_override = (
                    override.get("verdictLedger")
                    if isinstance(override.get("verdictLedger"), dict)
                    else {}
                )
                arbitration = (
                    verdict_ledger.get("arbitration")
                    if isinstance(verdict_ledger.get("arbitration"), dict)
                    else {}
                )
                arbitration_override = (
                    ledger_override.get("arbitration")
                    if isinstance(ledger_override.get("arbitration"), dict)
                    else {}
                )
                arbitration.update(arbitration_override)
                verdict_ledger["arbitration"] = arbitration
                payload["verdictLedger"] = verdict_ledger
            if "errorCodes" in override:
                payload["errorCodes"] = list(override["errorCodes"])
            if "auditAlerts" in override:
                payload["auditAlerts"] = list(override["auditAlerts"])
            if "degradationLevel" in override:
                payload["degradationLevel"] = int(override["degradationLevel"])
            if str(payload.get("winner") or "").strip().lower() == "draw":
                payload["needsDrawVote"] = True
            return payload

        with patch(
            "app.applications.bootstrap_final_report_helpers.build_final_report_payload_for_dispatch_v3",
            side_effect=_build_custom_final_payload,
        ):
            for case_id in (high_case_id, mid_case_id, low_case_id):
                final_req = _build_final_request(
                    case_id=case_id,
                    idempotency_key=f"final:{case_id}",
                )
                final_resp = await self._post_json(
                    app=app,
                    path="/internal/judge/v3/final/dispatch",
                    payload=final_req.model_dump(mode="json"),
                    internal_key=runtime.settings.ai_internal_key,
                )
                self.assertEqual(final_resp.status_code, 200, final_resp.text)

        filtered_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/courtroom/cases"
                "?dispatch_type=auto"
                "&status=review_required"
                "&winner=draw"
                "&review_required=true"
                "&risk_level=high"
                "&sort_by=risk_score"
                "&sort_order=desc"
                "&scan_limit=200"
                "&offset=0"
                "&limit=10"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(filtered_resp.status_code, 200)
        filtered_payload = filtered_resp.json()
        self.assertEqual(filtered_payload["count"], 1)
        self.assertEqual(filtered_payload["returned"], 1)
        item = filtered_payload["items"][0]
        self.assertEqual(item["caseId"], high_case_id)
        self.assertEqual(item["winner"], "draw")
        self.assertTrue(item["reviewRequired"])
        self.assertEqual(item["riskProfile"]["level"], "high")
        self.assertEqual(item["workflow"]["status"], "review_required")
        self.assertIsInstance(item["courtroomSummary"]["recorder"], dict)
        self.assertIsInstance(item["courtroomSummary"]["claim"], dict)
        self.assertIsInstance(item["courtroomSummary"]["evidence"], dict)
        self.assertIsInstance(item["courtroomSummary"]["panel"], dict)
        self.assertIsInstance(item["courtroomSummary"]["fairness"], dict)
        self.assertIsInstance(item["courtroomSummary"]["opinion"], dict)
        self.assertEqual(filtered_payload["filters"]["status"], "review_required")
        self.assertEqual(filtered_payload["filters"]["riskLevel"], "high")
        self.assertEqual(filtered_payload["filters"]["sortBy"], "risk_score")

        paged_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/courtroom/cases"
                "?dispatch_type=auto"
                "&sort_by=case_id"
                "&sort_order=asc"
                "&offset=1"
                "&limit=1"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(paged_resp.status_code, 200)
        paged_payload = paged_resp.json()
        self.assertEqual(paged_payload["returned"], 1)
        self.assertGreaterEqual(paged_payload["count"], 3)
        sorted_case_ids = sorted([high_case_id, mid_case_id, low_case_id])
        self.assertEqual(paged_payload["items"][0]["caseId"], sorted_case_ids[1])
        self.assertEqual(paged_payload["filters"]["offset"], 1)
        self.assertEqual(paged_payload["filters"]["limit"], 1)

    async def test_courtroom_cases_route_should_validate_query_values(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)

        invalid_winner_resp = await self._get(
            app=app,
            path="/internal/judge/courtroom/cases?winner=invalid",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(invalid_winner_resp.status_code, 422)
        self.assertIn("invalid_winner", invalid_winner_resp.text)

        invalid_window_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/courtroom/cases"
                "?updated_from=2026-04-18T03:00:00Z"
                "&updated_to=2026-04-18T02:00:00Z"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(invalid_window_resp.status_code, 422)
        self.assertIn("invalid_updated_time_window", invalid_window_resp.text)

    async def test_courtroom_drilldown_bundle_route_should_support_batch_filters_and_aggregations(
        self,
    ) -> None:
        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)

        high_case_id = _unique_case_id(9528)
        low_case_id = _unique_case_id(9529)
        case_overrides: dict[int, dict[str, Any]] = {
            high_case_id: {
                "reviewRequired": True,
                "fairnessSummary": {
                    "phase": "phase2",
                    "panelHighDisagreement": True,
                    "reviewRequired": True,
                    "gateDecision": "blocked_to_draw",
                    "reviewReasons": ["judge_panel_high_disagreement"],
                },
                "verdictLedger": {
                    "arbitration": {
                        "reviewRequired": True,
                        "gateDecision": "blocked_to_draw",
                    },
                    "pivotalMoments": [
                        {"id": "pivot-high-1", "phaseNo": 1},
                        {"id": "pivot-high-2", "phaseNo": 2},
                    ],
                },
                "claimGraphSummary": {
                    "stats": {
                        "totalClaims": 4,
                        "proClaims": 2,
                        "conClaims": 2,
                        "conflictEdges": 2,
                        "unansweredClaims": 1,
                        "weakSupportedClaims": 1,
                        "verdictReferencedClaims": 2,
                    },
                },
                "evidenceLedger": {
                    "stats": {
                        "totalEntries": 3,
                        "messageRefCount": 3,
                        "sourceCitationCount": 2,
                        "conflictSourceCount": 1,
                        "verdictReferencedCount": 3,
                        "reliabilityCounts": {"high": 1, "medium": 0, "low": 2},
                        "verdictReferencedReliabilityCounts": {
                            "high": 1,
                            "medium": 0,
                            "low": 2,
                        },
                    },
                },
                "errorCodes": [
                    "judge_panel_high_disagreement",
                    "evidence_reliability_too_low",
                    "fairness_gate_review_required",
                ],
                "auditAlerts": [{"type": "judge_panel_high_disagreement"}],
                "degradationLevel": 1,
            },
            low_case_id: {
                "reviewRequired": False,
                "fairnessSummary": {
                    "phase": "phase2",
                    "panelHighDisagreement": False,
                    "reviewRequired": False,
                },
                "verdictLedger": {
                    "arbitration": {
                        "reviewRequired": False,
                        "gateDecision": "pass_through",
                    },
                    "pivotalMoments": [],
                },
                "claimGraphSummary": {
                    "stats": {
                        "totalClaims": 2,
                        "proClaims": 1,
                        "conClaims": 1,
                        "conflictEdges": 0,
                        "unansweredClaims": 0,
                        "weakSupportedClaims": 0,
                        "verdictReferencedClaims": 2,
                    },
                },
                "evidenceLedger": {
                    "stats": {
                        "totalEntries": 2,
                        "messageRefCount": 2,
                        "sourceCitationCount": 1,
                        "conflictSourceCount": 0,
                        "verdictReferencedCount": 2,
                        "reliabilityCounts": {"high": 2, "medium": 0, "low": 0},
                        "verdictReferencedReliabilityCounts": {
                            "high": 2,
                            "medium": 0,
                            "low": 0,
                        },
                    },
                },
                "errorCodes": [],
                "auditAlerts": [],
                "degradationLevel": 0,
            },
        }

        def _build_custom_final_payload(
            *,
            request,
            phase_receipts=None,
            fairness_thresholds=None,
            panel_runtime_profiles=None,
            list_dispatch_receipts=None,
            build_final_report_payload=None,
            judge_style_mode=None,
            **_unused,
        ):
            receipts = (
                list(phase_receipts)
                if phase_receipts is not None
                else list(
                    list_dispatch_receipts(
                        dispatch_type="phase",
                        session_id=request.session_id,
                        status="reported",
                        limit=1000,
                    )
                )
                if callable(list_dispatch_receipts)
                else []
            )
            payload = (
                build_final_report_payload
                if callable(build_final_report_payload)
                else build_final_report_payload_v3_final
            )(
                request=request,
                phase_receipts=receipts,
                judge_style_mode=judge_style_mode,
                fairness_thresholds=fairness_thresholds,
                panel_runtime_profiles=panel_runtime_profiles,
            )
            override = case_overrides.get(int(request.case_id), {})
            if not override:
                return payload
            if "reviewRequired" in override:
                payload["reviewRequired"] = bool(override["reviewRequired"])
            if "fairnessSummary" in override:
                fairness_summary = (
                    payload.get("fairnessSummary")
                    if isinstance(payload.get("fairnessSummary"), dict)
                    else {}
                )
                fairness_summary.update(dict(override["fairnessSummary"]))
                payload["fairnessSummary"] = fairness_summary
            if "verdictLedger" in override:
                verdict_ledger = (
                    payload.get("verdictLedger")
                    if isinstance(payload.get("verdictLedger"), dict)
                    else {}
                )
                verdict_override = (
                    override.get("verdictLedger")
                    if isinstance(override.get("verdictLedger"), dict)
                    else {}
                )
                arbitration = (
                    verdict_ledger.get("arbitration")
                    if isinstance(verdict_ledger.get("arbitration"), dict)
                    else {}
                )
                arbitration_override = (
                    verdict_override.get("arbitration")
                    if isinstance(verdict_override.get("arbitration"), dict)
                    else {}
                )
                arbitration.update(arbitration_override)
                verdict_ledger["arbitration"] = arbitration
                if isinstance(verdict_override.get("pivotalMoments"), list):
                    verdict_ledger["pivotalMoments"] = list(
                        verdict_override["pivotalMoments"]
                    )
                payload["verdictLedger"] = verdict_ledger
            if "claimGraphSummary" in override:
                claim_summary = (
                    payload.get("claimGraphSummary")
                    if isinstance(payload.get("claimGraphSummary"), dict)
                    else {}
                )
                claim_summary_override = (
                    override.get("claimGraphSummary")
                    if isinstance(override.get("claimGraphSummary"), dict)
                    else {}
                )
                claim_summary.update(claim_summary_override)
                payload["claimGraphSummary"] = claim_summary
            if "evidenceLedger" in override:
                evidence_ledger = (
                    payload.get("evidenceLedger")
                    if isinstance(payload.get("evidenceLedger"), dict)
                    else {}
                )
                evidence_override = (
                    override.get("evidenceLedger")
                    if isinstance(override.get("evidenceLedger"), dict)
                    else {}
                )
                evidence_ledger.update(
                    {
                        key: value
                        for key, value in evidence_override.items()
                        if key != "stats"
                    }
                )
                evidence_stats = (
                    evidence_ledger.get("stats")
                    if isinstance(evidence_ledger.get("stats"), dict)
                    else {}
                )
                stats_override = (
                    evidence_override.get("stats")
                    if isinstance(evidence_override.get("stats"), dict)
                    else {}
                )
                evidence_stats.update(stats_override)
                evidence_ledger["stats"] = evidence_stats
                payload["evidenceLedger"] = evidence_ledger
            if "errorCodes" in override:
                payload["errorCodes"] = list(override["errorCodes"])
            if "auditAlerts" in override:
                payload["auditAlerts"] = list(override["auditAlerts"])
            if "degradationLevel" in override:
                payload["degradationLevel"] = int(override["degradationLevel"])
            return payload

        with patch(
            "app.applications.bootstrap_final_report_helpers.build_final_report_payload_for_dispatch_v3",
            side_effect=_build_custom_final_payload,
        ):
            for case_id in (high_case_id, low_case_id):
                final_req = _build_final_request(
                    case_id=case_id,
                    idempotency_key=f"final:{case_id}",
                )
                final_resp = await self._post_json(
                    app=app,
                    path="/internal/judge/v3/final/dispatch",
                    payload=final_req.model_dump(mode="json"),
                    internal_key=runtime.settings.ai_internal_key,
                )
                self.assertEqual(final_resp.status_code, 200, final_resp.text)

        filtered_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/courtroom/drilldown-bundle"
                "?dispatch_type=auto"
                "&status=review_required"
                "&review_required=true"
                "&risk_level=high"
                "&sort_by=risk_score"
                "&sort_order=desc"
                "&scan_limit=200"
                "&claim_preview_limit=5"
                "&evidence_preview_limit=5"
                "&panel_preview_limit=5"
                "&limit=20"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(filtered_resp.status_code, 200)
        filtered_payload = filtered_resp.json()
        self.assertEqual(filtered_payload["count"], 1)
        self.assertEqual(filtered_payload["returned"], 1)
        item = filtered_payload["items"][0]
        self.assertEqual(item["caseId"], high_case_id)
        self.assertTrue(item["reviewRequired"])
        self.assertEqual(item["riskProfile"]["level"], "high")
        self.assertIsInstance(item["drilldown"]["claim"], dict)
        self.assertIsInstance(item["drilldown"]["evidence"], dict)
        self.assertIsInstance(item["drilldown"]["panel"], dict)
        self.assertIsInstance(item["drilldown"]["fairness"], dict)
        self.assertIsInstance(item["drilldown"]["opinion"], dict)
        self.assertIsInstance(item["drilldown"]["governance"], dict)
        self.assertGreaterEqual(item["drilldown"]["claim"]["conflictPairCount"], 2)
        self.assertGreaterEqual(item["drilldown"]["claim"]["unansweredClaimCount"], 1)
        self.assertEqual(item["drilldown"]["panel"]["pivotalMomentCount"], 2)
        self.assertIn("claim.resolve_conflict", item["actionHints"])
        self.assertIn("claim.answer_missing", item["actionHints"])
        self.assertIn("review.queue.decide", item["actionHints"])
        self.assertIn(
            f"/internal/judge/cases/{high_case_id}/courtroom-read-model",
            item["detailPath"],
        )
        self.assertEqual(filtered_payload["filters"]["sortBy"], "risk_score")
        self.assertEqual(filtered_payload["filters"]["claimPreviewLimit"], 5)
        self.assertGreaterEqual(
            filtered_payload["aggregations"]["totalConflictPairCount"],
            2,
        )
        self.assertGreaterEqual(
            filtered_payload["aggregations"]["totalUnansweredClaimCount"],
            1,
        )
        self.assertGreaterEqual(
            filtered_payload["aggregations"]["totalPivotalMomentCount"],
            2,
        )

        paged_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/courtroom/drilldown-bundle"
                "?dispatch_type=auto"
                "&sort_by=case_id"
                "&sort_order=asc"
                "&offset=1"
                "&limit=1"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(paged_resp.status_code, 200)
        paged_payload = paged_resp.json()
        self.assertGreaterEqual(paged_payload["count"], 2)
        self.assertEqual(paged_payload["returned"], 1)
        self.assertEqual(paged_payload["filters"]["offset"], 1)
        self.assertEqual(paged_payload["filters"]["limit"], 1)

        invalid_sort_resp = await self._get(
            app=app,
            path="/internal/judge/courtroom/drilldown-bundle?sort_by=bad-value",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(invalid_sort_resp.status_code, 422)
        self.assertIn("invalid_courtroom_drilldown_sort_by", invalid_sort_resp.text)

    async def test_evidence_claim_ops_queue_route_should_support_conflict_reliability_and_unanswered_filters(
        self,
    ) -> None:
        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)

        high_case_id = _unique_case_id(9521)
        low_case_id = _unique_case_id(9522)
        case_overrides: dict[int, dict[str, Any]] = {
            high_case_id: {
                "reviewRequired": True,
                "fairnessSummary": {
                    "phase": "phase2",
                    "panelHighDisagreement": True,
                    "reviewRequired": True,
                    "gateDecision": "blocked_to_draw",
                    "reviewReasons": ["judge_panel_high_disagreement"],
                },
                "verdictLedger": {
                    "arbitration": {
                        "reviewRequired": True,
                        "gateDecision": "blocked_to_draw",
                    },
                },
                "claimGraphSummary": {
                    "stats": {
                        "totalClaims": 4,
                        "proClaims": 2,
                        "conClaims": 2,
                        "conflictEdges": 2,
                        "unansweredClaims": 1,
                        "weakSupportedClaims": 1,
                        "verdictReferencedClaims": 2,
                    },
                },
                "evidenceLedger": {
                    "stats": {
                        "totalEntries": 3,
                        "messageRefCount": 3,
                        "sourceCitationCount": 1,
                        "conflictSourceCount": 1,
                        "verdictReferencedCount": 3,
                        "reliabilityCounts": {"high": 1, "medium": 0, "low": 2},
                        "verdictReferencedReliabilityCounts": {
                            "high": 1,
                            "medium": 0,
                            "low": 2,
                        },
                    },
                },
                "errorCodes": [
                    "judge_panel_high_disagreement",
                    "evidence_reliability_too_low",
                    "fairness_gate_review_required",
                ],
                "auditAlerts": [{"type": "judge_panel_high_disagreement"}],
                "degradationLevel": 1,
            },
            low_case_id: {
                "reviewRequired": False,
                "fairnessSummary": {
                    "phase": "phase2",
                    "panelHighDisagreement": False,
                    "reviewRequired": False,
                },
                "verdictLedger": {
                    "arbitration": {
                        "reviewRequired": False,
                        "gateDecision": "pass_through",
                    },
                },
                "claimGraphSummary": {
                    "stats": {
                        "totalClaims": 2,
                        "proClaims": 1,
                        "conClaims": 1,
                        "conflictEdges": 0,
                        "unansweredClaims": 0,
                        "weakSupportedClaims": 0,
                        "verdictReferencedClaims": 2,
                    },
                },
                "evidenceLedger": {
                    "stats": {
                        "totalEntries": 2,
                        "messageRefCount": 2,
                        "sourceCitationCount": 2,
                        "conflictSourceCount": 0,
                        "verdictReferencedCount": 2,
                        "reliabilityCounts": {"high": 2, "medium": 0, "low": 0},
                        "verdictReferencedReliabilityCounts": {
                            "high": 2,
                            "medium": 0,
                            "low": 0,
                        },
                    },
                },
                "errorCodes": [],
                "auditAlerts": [],
                "degradationLevel": 0,
            },
        }

        def _build_custom_final_payload(
            *,
            request,
            phase_receipts=None,
            fairness_thresholds=None,
            panel_runtime_profiles=None,
            list_dispatch_receipts=None,
            build_final_report_payload=None,
            judge_style_mode=None,
            **_unused,
        ):
            receipts = (
                list(phase_receipts)
                if phase_receipts is not None
                else list(
                    list_dispatch_receipts(
                        dispatch_type="phase",
                        session_id=request.session_id,
                        status="reported",
                        limit=1000,
                    )
                )
                if callable(list_dispatch_receipts)
                else []
            )
            payload = (
                build_final_report_payload
                if callable(build_final_report_payload)
                else build_final_report_payload_v3_final
            )(
                request=request,
                phase_receipts=receipts,
                judge_style_mode=judge_style_mode,
                fairness_thresholds=fairness_thresholds,
                panel_runtime_profiles=panel_runtime_profiles,
            )
            override = case_overrides.get(int(request.case_id), {})
            if not override:
                return payload

            if "reviewRequired" in override:
                payload["reviewRequired"] = bool(override["reviewRequired"])
            if "fairnessSummary" in override:
                fairness_summary = (
                    payload.get("fairnessSummary")
                    if isinstance(payload.get("fairnessSummary"), dict)
                    else {}
                )
                fairness_summary.update(dict(override["fairnessSummary"]))
                payload["fairnessSummary"] = fairness_summary
            if "verdictLedger" in override:
                verdict_ledger = (
                    payload.get("verdictLedger")
                    if isinstance(payload.get("verdictLedger"), dict)
                    else {}
                )
                verdict_override = (
                    override.get("verdictLedger")
                    if isinstance(override.get("verdictLedger"), dict)
                    else {}
                )
                arbitration = (
                    verdict_ledger.get("arbitration")
                    if isinstance(verdict_ledger.get("arbitration"), dict)
                    else {}
                )
                arbitration_override = (
                    verdict_override.get("arbitration")
                    if isinstance(verdict_override.get("arbitration"), dict)
                    else {}
                )
                arbitration.update(arbitration_override)
                verdict_ledger["arbitration"] = arbitration
                if isinstance(verdict_override.get("decisiveEvidenceRefs"), list):
                    verdict_ledger["decisiveEvidenceRefs"] = list(
                        verdict_override["decisiveEvidenceRefs"]
                    )
                payload["verdictLedger"] = verdict_ledger
            if "claimGraphSummary" in override:
                claim_summary = (
                    payload.get("claimGraphSummary")
                    if isinstance(payload.get("claimGraphSummary"), dict)
                    else {}
                )
                claim_summary_override = (
                    override.get("claimGraphSummary")
                    if isinstance(override.get("claimGraphSummary"), dict)
                    else {}
                )
                claim_summary.update(claim_summary_override)
                payload["claimGraphSummary"] = claim_summary
            if "evidenceLedger" in override:
                evidence_ledger = (
                    payload.get("evidenceLedger")
                    if isinstance(payload.get("evidenceLedger"), dict)
                    else {}
                )
                evidence_override = (
                    override.get("evidenceLedger")
                    if isinstance(override.get("evidenceLedger"), dict)
                    else {}
                )
                evidence_ledger.update(
                    {
                        key: value
                        for key, value in evidence_override.items()
                        if key != "stats"
                    }
                )
                evidence_stats = (
                    evidence_ledger.get("stats")
                    if isinstance(evidence_ledger.get("stats"), dict)
                    else {}
                )
                stats_override = (
                    evidence_override.get("stats")
                    if isinstance(evidence_override.get("stats"), dict)
                    else {}
                )
                evidence_stats.update(stats_override)
                evidence_ledger["stats"] = evidence_stats
                payload["evidenceLedger"] = evidence_ledger
            if isinstance(override.get("verdictEvidenceRefs"), list):
                payload["verdictEvidenceRefs"] = list(override["verdictEvidenceRefs"])
            if "errorCodes" in override:
                payload["errorCodes"] = list(override["errorCodes"])
            if "auditAlerts" in override:
                payload["auditAlerts"] = list(override["auditAlerts"])
            if "degradationLevel" in override:
                payload["degradationLevel"] = int(override["degradationLevel"])
            if str(payload.get("winner") or "").strip().lower() == "draw":
                payload["needsDrawVote"] = True
            return payload

        with patch(
            "app.applications.bootstrap_final_report_helpers.build_final_report_payload_for_dispatch_v3",
            side_effect=_build_custom_final_payload,
        ):
            for case_id in (high_case_id, low_case_id):
                final_req = _build_final_request(
                    case_id=case_id,
                    idempotency_key=f"final:{case_id}",
                )
                final_resp = await self._post_json(
                    app=app,
                    path="/internal/judge/v3/final/dispatch",
                    payload=final_req.model_dump(mode="json"),
                    internal_key=runtime.settings.ai_internal_key,
                )
                self.assertEqual(final_resp.status_code, 200, final_resp.text)

        low_reliability_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/evidence-claim/ops-queue"
                "?dispatch_type=final"
                "&has_conflict=true"
                "&has_unanswered_claim=true"
                "&reliability_level=low"
                "&risk_level=high"
                "&sort_by=conflict_pair_count"
                "&sort_order=desc"
                "&scan_limit=200"
                "&limit=20"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(low_reliability_resp.status_code, 200)
        low_payload = low_reliability_resp.json()
        self.assertEqual(low_payload["count"], 1)
        self.assertEqual(low_payload["returned"], 1)
        high_item = low_payload["items"][0]
        self.assertEqual(high_item["caseId"], high_case_id)
        self.assertTrue(high_item["claimEvidenceProfile"]["hasConflict"])
        self.assertTrue(high_item["claimEvidenceProfile"]["hasUnansweredClaim"])
        self.assertEqual(high_item["claimEvidenceProfile"]["reliability"]["level"], "low")
        self.assertIn("claim.resolve_conflict", high_item["actionHints"])
        self.assertIn("claim.answer_missing", high_item["actionHints"])
        self.assertIn("evidence.upgrade_reliability", high_item["actionHints"])
        self.assertIn("review.queue.decide", high_item["actionHints"])
        self.assertIn(
            f"/internal/judge/cases/{high_case_id}/courtroom-read-model",
            high_item["detailPath"],
        )
        self.assertEqual(low_payload["filters"]["reliabilityLevel"], "low")
        self.assertEqual(low_payload["filters"]["sortBy"], "conflict_pair_count")
        self.assertGreaterEqual(
            low_payload["aggregations"]["reliabilityLevelCounts"]["low"],
            1,
        )

        high_reliability_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/evidence-claim/ops-queue"
                "?dispatch_type=final"
                "&reliability_level=high"
                "&sort_by=reliability_score"
                "&sort_order=desc"
                "&scan_limit=200"
                "&limit=20"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(high_reliability_resp.status_code, 200)
        high_payload = high_reliability_resp.json()
        self.assertEqual(high_payload["count"], 1)
        self.assertEqual(high_payload["items"][0]["caseId"], low_case_id)
        self.assertEqual(
            high_payload["items"][0]["claimEvidenceProfile"]["reliability"]["level"],
            "high",
        )

        invalid_reliability_resp = await self._get(
            app=app,
            path="/internal/judge/evidence-claim/ops-queue?reliability_level=invalid",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(invalid_reliability_resp.status_code, 422)
        self.assertIn(
            "invalid_evidence_claim_reliability_level",
            invalid_reliability_resp.text,
        )

    async def test_courtroom_drilldown_bundle_route_should_return_500_when_contract_validation_fails(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)

        with patch(
            "app.app_factory.validate_courtroom_drilldown_bundle_contract_v3",
            side_effect=ValueError("courtroom_drilldown_bundle_missing_keys:items"),
        ):
            resp = await self._get(
                app=app,
                path="/internal/judge/courtroom/drilldown-bundle",
                internal_key=runtime.settings.ai_internal_key,
            )
        self.assertEqual(resp.status_code, 500)
        detail = resp.json()["detail"]
        self.assertEqual(detail["code"], "courtroom_drilldown_bundle_contract_violation")
        self.assertIn("courtroom_drilldown_bundle_missing_keys", detail["message"])

    async def test_evidence_claim_ops_queue_route_should_return_500_when_contract_validation_fails(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)

        with patch(
            "app.app_factory.validate_evidence_claim_ops_queue_contract_v3",
            side_effect=ValueError("evidence_claim_ops_queue_missing_keys:items"),
        ):
            resp = await self._get(
                app=app,
                path="/internal/judge/evidence-claim/ops-queue",
                internal_key=runtime.settings.ai_internal_key,
            )
        self.assertEqual(resp.status_code, 500)
        detail = resp.json()["detail"]
        self.assertEqual(detail["code"], "evidence_claim_ops_queue_contract_violation")
        self.assertIn("evidence_claim_ops_queue_missing_keys", detail["message"])

    async def test_claim_ledger_route_should_return_persisted_claim_graph(self) -> None:
        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)

        case_id = _unique_case_id(9120)
        phase_req = _build_phase_request(case_id=case_id, idempotency_key=f"phase:{case_id}")
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(case_id=case_id, idempotency_key=f"final:{case_id}")
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        ledger_resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/claim-ledger?dispatch_type=final",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(ledger_resp.status_code, 200)
        ledger_body = ledger_resp.json()
        self.assertEqual(ledger_body["dispatchType"], "final")
        self.assertGreaterEqual(ledger_body["count"], 1)
        self.assertIsInstance(ledger_body["item"]["caseDossier"], dict)
        self.assertEqual(ledger_body["item"]["caseDossier"]["dispatchType"], "final")
        self.assertEqual(
            ledger_body["item"]["caseDossier"]["phase"]["startNo"],
            final_req.phase_start_no,
        )
        self.assertEqual(
            ledger_body["item"]["caseDossier"]["phase"]["endNo"],
            final_req.phase_end_no,
        )
        self.assertIsInstance(ledger_body["item"]["claimGraph"], dict)
        self.assertIsInstance(ledger_body["item"]["claimGraph"]["nodes"], list)
        self.assertIsInstance(ledger_body["item"]["claimGraph"]["edges"], list)
        self.assertIsInstance(ledger_body["item"]["claimGraphSummary"], dict)
        self.assertIsInstance(ledger_body["item"]["evidenceLedger"], dict)
        self.assertIsInstance(ledger_body["item"]["evidenceLedger"]["sourceCitations"], list)
        self.assertIsInstance(ledger_body["item"]["evidenceLedger"]["conflictSources"], list)
        self.assertIsInstance(ledger_body["item"]["verdictEvidenceRefs"], list)

        phase_ledger_resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/claim-ledger?dispatch_type=phase",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_ledger_resp.status_code, 200)
        phase_ledger_body = phase_ledger_resp.json()
        self.assertEqual(phase_ledger_body["dispatchType"], "phase")
        self.assertEqual(phase_ledger_body["item"]["caseDossier"]["phase"]["no"], phase_req.phase_no)
        self.assertEqual(
            phase_ledger_body["item"]["caseDossier"]["messageWindow"]["count"],
            phase_req.message_count,
        )
        self.assertEqual(
            len(phase_ledger_body["item"]["caseDossier"]["messageDigest"]),
            phase_req.message_count,
        )
        self.assertEqual(
            phase_ledger_body["item"]["caseDossier"]["sideDistribution"]["pro"],
            1,
        )
        self.assertEqual(
            phase_ledger_body["item"]["caseDossier"]["sideDistribution"]["con"],
            1,
        )

    async def test_case_detail_route_should_return_404_when_case_missing(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)

        missing_resp = await self._get(
            app=app,
            path="/internal/judge/cases/999901",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(missing_resp.status_code, 404)
        self.assertIn("case_not_found", missing_resp.text)

if __name__ == "__main__":
    unittest.main()
