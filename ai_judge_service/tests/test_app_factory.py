import unittest
from typing import Any
from unittest.mock import patch

from app.app_factory import create_app, create_default_app, create_runtime
from app.applications import (
    build_final_report_payload as build_final_report_payload_v3_final,
)
from app.domain.agents import AgentExecutionResult

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


class AppFactoryTests(AppFactoryRouteTestMixin, unittest.IsolatedAsyncioTestCase):

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

    async def test_policy_routes_should_return_default_registry_profile(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)

        list_resp = await self._get(
            app=app,
            path="/internal/judge/policies",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(list_resp.status_code, 200)
        payload = list_resp.json()
        self.assertEqual(payload["defaultVersion"], "v3-default")
        self.assertGreaterEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["promptRegistryVersion"], "promptset-v3-default")
        self.assertEqual(payload["items"][0]["toolRegistryVersion"], "toolset-v3-default")
        self.assertEqual(payload["items"][0]["promptVersions"]["claimGraphVersion"], "v1-claim-graph-bootstrap")
        self.assertIn("evidenceMinTotalRefs", payload["items"][0]["fairnessThresholds"])

        detail_resp = await self._get(
            app=app,
            path="/internal/judge/policies/v3-default",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(detail_resp.status_code, 200)
        self.assertEqual(detail_resp.json()["item"]["version"], "v3-default")

        prompt_list_resp = await self._get(
            app=app,
            path="/internal/judge/registries/prompts",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(prompt_list_resp.status_code, 200)
        prompt_list_payload = prompt_list_resp.json()
        self.assertEqual(prompt_list_payload["defaultVersion"], "promptset-v3-default")
        self.assertGreaterEqual(prompt_list_payload["count"], 1)
        self.assertEqual(
            prompt_list_payload["items"][0]["promptVersions"]["claimGraphVersion"],
            "v1-claim-graph-bootstrap",
        )

        prompt_detail_resp = await self._get(
            app=app,
            path="/internal/judge/registries/prompts/promptset-v3-default",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(prompt_detail_resp.status_code, 200)
        self.assertEqual(prompt_detail_resp.json()["item"]["version"], "promptset-v3-default")

        tool_list_resp = await self._get(
            app=app,
            path="/internal/judge/registries/tools",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(tool_list_resp.status_code, 200)
        tool_list_payload = tool_list_resp.json()
        self.assertEqual(tool_list_payload["defaultVersion"], "toolset-v3-default")
        self.assertGreaterEqual(tool_list_payload["count"], 1)
        self.assertIn("claim_graph_builder", tool_list_payload["items"][0]["toolIds"])

        tool_detail_resp = await self._get(
            app=app,
            path="/internal/judge/registries/tools/toolset-v3-default",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(tool_detail_resp.status_code, 200)
        self.assertEqual(tool_detail_resp.json()["item"]["version"], "toolset-v3-default")

    async def test_policy_registry_publish_should_reject_unknown_prompt_registry_version(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        policy_version = f"policy-missing-{_unique_case_id(8105)}"
        publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": policy_version,
                "activate": False,
                "reason": "test_policy_override_for_prompt_registry_validation",
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-missing",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_resp.status_code, 422)
        detail = publish_resp.json()["detail"]
        self.assertEqual(detail["code"], "registry_policy_dependency_invalid")
        dependency = detail["dependency"]
        self.assertFalse(dependency["ok"])
        issue_codes = {str(item.get("code") or "") for item in dependency["issues"]}
        self.assertIn("prompt_registry_version_not_found", issue_codes)
        self.assertEqual(detail["alert"]["type"], "registry_dependency_health_blocked")
        self.assertEqual(detail["alert"]["status"], "raised")

    async def test_registry_routes_should_support_publish_activate_rollback_and_audit(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9201)
        version = f"promptset-p8-{suffix}"
        actor = f"actor-{suffix}"

        publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/prompt/publish",
            payload={
                "version": version,
                "activate": False,
                "actor": actor,
                "reason": "test_publish",
                "profile": {
                    "promptVersions": {
                        "claimGraphVersion": "v1-claim-graph-bootstrap",
                    },
                    "metadata": {
                        "status": "candidate",
                    },
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_resp.status_code, 200)
        publish_item = publish_resp.json()["item"]
        self.assertEqual(publish_item["version"], version)
        self.assertFalse(publish_item["isActive"])

        activate_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/registries/prompt/{version}/activate"
                f"?actor={actor}&reason=test_activate"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(activate_resp.status_code, 200)
        activate_item = activate_resp.json()["item"]
        self.assertEqual(activate_item["version"], version)
        self.assertTrue(activate_item["isActive"])

        prompt_list_resp = await self._get(
            app=app,
            path="/internal/judge/registries/prompts",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(prompt_list_resp.status_code, 200)
        self.assertEqual(prompt_list_resp.json()["defaultVersion"], version)

        rollback_resp = await self._post(
            app=app,
            path=f"/internal/judge/registries/prompt/rollback?actor={actor}&reason=test_rollback",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(rollback_resp.status_code, 200)
        rollback_item = rollback_resp.json()["item"]
        self.assertNotEqual(rollback_item["version"], version)

        prompt_list_after_rollback = await self._get(
            app=app,
            path="/internal/judge/registries/prompts",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(prompt_list_after_rollback.status_code, 200)
        self.assertEqual(
            prompt_list_after_rollback.json()["defaultVersion"],
            rollback_item["version"],
        )

        audits_resp = await self._get(
            app=app,
            path="/internal/judge/registries/prompt/audits?limit=200",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(audits_resp.status_code, 200)
        audit_items = audits_resp.json()["items"]
        actor_actions = [
            str(item.get("action") or "")
            for item in audit_items
            if str(item.get("actor") or "") == actor
        ]
        self.assertIn("publish", actor_actions)
        self.assertIn("activate", actor_actions)
        self.assertIn("rollback", actor_actions)

        releases_resp = await self._get(
            app=app,
            path="/internal/judge/registries/prompt/releases?limit=200&include_payload=false",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(releases_resp.status_code, 200)
        release_items = releases_resp.json()["items"]
        version_items = [
            item
            for item in release_items
            if str(item.get("version") or "") == version
        ]
        self.assertTrue(version_items)
        self.assertNotIn("payload", version_items[0])

        get_release_resp = await self._get(
            app=app,
            path=f"/internal/judge/registries/prompt/releases/{version}",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(get_release_resp.status_code, 200)
        release_item = get_release_resp.json()["item"]
        self.assertEqual(release_item["version"], version)
        self.assertIn("payload", release_item)

    async def test_policy_registry_activate_should_block_when_fairness_gate_not_ready(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9211)
        version = f"policy-gate-{suffix}"

        publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_resp.status_code, 200)

        activate_resp = await self._post(
            app=app,
            path=f"/internal/judge/registries/policy/{version}/activate",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(activate_resp.status_code, 409)
        detail = activate_resp.json()["detail"]
        self.assertEqual(detail["code"], "registry_fairness_gate_blocked")
        self.assertEqual(
            detail["gate"]["code"],
            "registry_fairness_gate_no_benchmark",
        )

    async def test_policy_registry_activate_should_block_when_shadow_gate_not_ready(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9216)
        version = f"policy-shadow-gate-{suffix}"
        benchmark_run_id = f"benchmark-{suffix}"
        shadow_run_id = f"shadow-{suffix}"

        publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_resp.status_code, 200)

        benchmark_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": benchmark_run_id,
                "policy_version": version,
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "sample_size": 48,
                "draw_rate": 0.11,
                "side_bias_delta": 0.02,
                "appeal_overturn_rate": 0.03,
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(benchmark_resp.status_code, 200)

        shadow_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/shadow-runs",
            payload={
                "run_id": shadow_run_id,
                "policy_version": version,
                "benchmark_run_id": benchmark_run_id,
                "environment_mode": "local_reference",
                "status": "threshold_violation",
                "threshold_decision": "violated",
                "sample_size": 48,
                "winner_flip_rate": 0.12,
                "score_shift_delta": 0.18,
                "review_required_delta": 0.07,
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(shadow_resp.status_code, 200)

        activate_resp = await self._post(
            app=app,
            path=f"/internal/judge/registries/policy/{version}/activate",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(activate_resp.status_code, 409)
        detail = activate_resp.json()["detail"]
        self.assertEqual(detail["code"], "registry_fairness_gate_blocked")
        gate = detail["gate"]
        self.assertEqual(
            gate["code"],
            "registry_fairness_gate_shadow_threshold_not_accepted",
        )
        self.assertEqual(gate["source"], "shadow")
        self.assertTrue(bool(gate["benchmarkGatePassed"]))
        self.assertTrue(bool(gate["shadowGateApplied"]))
        self.assertFalse(bool(gate["shadowGatePassed"]))
        self.assertEqual(gate["latestRun"]["runId"], benchmark_run_id)
        self.assertEqual(gate["latestShadowRun"]["runId"], shadow_run_id)

    async def test_policy_registry_publish_activate_should_allow_shadow_gate_override_and_audit(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9217)
        version = f"policy-shadow-override-{suffix}"
        benchmark_run_id = f"benchmark-{suffix}"
        shadow_run_id = f"shadow-{suffix}"
        actor = f"shadow-override-actor-{suffix}"

        benchmark_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": benchmark_run_id,
                "policy_version": version,
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "sample_size": 52,
                "draw_rate": 0.12,
                "side_bias_delta": 0.02,
                "appeal_overturn_rate": 0.02,
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(benchmark_resp.status_code, 200)

        shadow_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/shadow-runs",
            payload={
                "run_id": shadow_run_id,
                "policy_version": version,
                "benchmark_run_id": benchmark_run_id,
                "environment_mode": "local_reference",
                "status": "threshold_violation",
                "threshold_decision": "violated",
                "sample_size": 52,
                "winner_flip_rate": 0.11,
                "score_shift_delta": 0.16,
                "review_required_delta": 0.05,
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(shadow_resp.status_code, 200)

        publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": version,
                "activate": True,
                "override_fairness_gate": True,
                "actor": actor,
                "reason": "shadow_gate_manual_override",
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-v3-default",
                    "toolRegistryVersion": "toolset-v3-default",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_resp.status_code, 200)
        publish_payload = publish_resp.json()
        self.assertTrue(bool(publish_payload["item"]["isActive"]))
        self.assertEqual(
            publish_payload["fairnessGate"]["code"],
            "registry_fairness_gate_shadow_threshold_not_accepted",
        )
        self.assertEqual(
            publish_payload["alert"]["type"],
            "registry_fairness_gate_override",
        )
        self.assertTrue(bool(publish_payload["alert"]["details"]["overrideApplied"]))
        self.assertEqual(
            publish_payload["alert"]["details"]["gate"]["latestShadowRun"]["runId"],
            shadow_run_id,
        )

        audits_resp = await self._get(
            app=app,
            path="/internal/judge/registries/policy/audits?limit=200",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(audits_resp.status_code, 200)
        audit_items = audits_resp.json()["items"]
        activate_audit = next(
            (
                item
                for item in audit_items
                if str(item.get("action") or "") == "activate"
                and str(item.get("version") or "") == version
                and str(item.get("actor") or "") == actor
            ),
            None,
        )
        self.assertIsNotNone(activate_audit)
        assert activate_audit is not None
        fairness_gate = activate_audit["details"].get("fairnessGate")
        self.assertIsInstance(fairness_gate, dict)
        self.assertTrue(bool(fairness_gate.get("overrideApplied")))
        self.assertEqual(
            fairness_gate.get("code"),
            "registry_fairness_gate_shadow_threshold_not_accepted",
        )
        self.assertEqual(
            fairness_gate.get("latestShadowRun", {}).get("runId"),
            shadow_run_id,
        )

    async def test_policy_registry_activate_should_block_when_dependency_invalid(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        await runtime.workflow_runtime.db.create_schema()
        suffix = _unique_case_id(9212)
        version = f"policy-dep-{suffix}"
        await runtime.registry_product_runtime.publish_release(
            registry_type="policy",
            version=version,
            profile_payload={
                "rubricVersion": "v3",
                "topicDomain": "tft",
                "promptRegistryVersion": "promptset-not-exist",
                "toolRegistryVersion": "toolset-v3-default",
            },
            actor="seed",
            reason="seed_invalid_dependency_for_activate",
            activate=False,
        )

        activate_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/registries/policy/{version}/activate"
                "?override_fairness_gate=true&reason=test_override"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(activate_resp.status_code, 409)
        detail = activate_resp.json()["detail"]
        self.assertEqual(detail["code"], "registry_policy_dependency_blocked")
        dependency = detail["dependency"]
        self.assertFalse(dependency["ok"])
        issue_codes = {str(item.get("code") or "") for item in dependency["issues"]}
        self.assertIn("prompt_registry_version_not_found", issue_codes)

    async def test_policy_registry_dependency_health_route_should_return_dependency_snapshot(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9214)
        version = f"policy-health-{suffix}"
        actor = f"dependency-health-actor-{suffix}"
        publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": version,
                "activate": False,
                "reason": "prepare_for_dependency_health",
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-v3-default",
                    "toolRegistryVersion": "toolset-v3-default",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_resp.status_code, 200)
        activate_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/registries/policy/{version}/activate"
                f"?override_fairness_gate=true&actor={actor}&reason=dependency_health_override_probe"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(activate_resp.status_code, 200)

        health_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/registries/policy/dependencies/health"
                f"?policy_version={version}&include_all_versions=true&limit=5"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(health_resp.status_code, 200)
        payload = health_resp.json()
        self.assertEqual(payload["selectedPolicyVersion"], version)
        self.assertGreaterEqual(payload["count"], 1)
        self.assertTrue(payload["includeAllVersions"])
        self.assertTrue(payload["includeOverview"])
        self.assertTrue(payload["includeTrend"])
        self.assertEqual(payload["item"]["policyVersion"], version)
        self.assertTrue(payload["item"]["ok"])
        self.assertTrue(payload["item"]["checks"]["promptRegistryExists"])
        self.assertTrue(payload["item"]["checks"]["toolRegistryExists"])
        self.assertIsInstance(payload["item"]["policyKernel"], dict)
        self.assertEqual(
            payload["item"]["policyKernel"]["version"],
            "policy-kernel-binding-v1",
        )
        self.assertTrue(str(payload["item"]["policyKernel"]["kernelHash"] or "").strip())
        self.assertEqual(
            payload["item"]["policyKernel"]["kernelVector"]["policyVersion"],
            version,
        )
        self.assertEqual(payload["activeVersions"]["policyVersion"], runtime.policy_registry_runtime.default_version)
        overview = payload["dependencyOverview"]
        self.assertIsInstance(overview, dict)
        self.assertEqual(overview["registryType"], "policy")
        self.assertGreaterEqual(overview["counts"]["trackedPolicyVersions"], 1)
        self.assertIn("gateDecisionCounts", overview)
        self.assertIn("byPolicyVersion", overview)
        self.assertTrue(any(row["policyVersion"] == version for row in overview["byPolicyVersion"]))
        target_overview = next(row for row in overview["byPolicyVersion"] if row["policyVersion"] == version)
        self.assertEqual(target_overview["policyKernelVersion"], "policy-kernel-binding-v1")
        self.assertTrue(str(target_overview["policyKernelHash"] or "").strip())
        self.assertEqual(target_overview["latestGateDecision"], "override_activated")
        self.assertTrue(bool(target_overview["overrideApplied"]))
        self.assertEqual(target_overview["overrideActor"], actor)
        self.assertEqual(target_overview["latestGateSource"], "benchmark")
        trend = payload["dependencyTrend"]
        self.assertIsInstance(trend, dict)
        self.assertEqual(trend["registryType"], "policy")
        self.assertIn("items", trend)
        self.assertGreaterEqual(trend["count"], 0)

    async def test_policy_registry_dependency_health_route_should_reject_invalid_trend_status(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        health_resp = await self._get(
            app=app,
            path="/internal/judge/registries/policy/dependencies/health?trend_status=bad-status",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(health_resp.status_code, 422)
        self.assertIn("invalid_trend_status", health_resp.text)

    async def test_policy_gate_simulation_route_should_return_advisory_snapshot(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9215)
        version = f"policy-gate-sim-{suffix}"
        publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": version,
                "activate": False,
                "reason": "prepare_for_policy_gate_simulation",
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-v3-default",
                    "toolRegistryVersion": "toolset-v3-default",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_resp.status_code, 200)
        before_alerts = list(
            runtime.trace_store.list_audit_alerts(job_id=0, status=None, limit=500)
        )

        sim_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/registries/policy/gate-simulation"
                f"?policy_version={version}&include_all_versions=true&limit=10"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(sim_resp.status_code, 200)
        payload = sim_resp.json()
        self.assertEqual(payload["selectedPolicyVersion"], version)
        self.assertGreaterEqual(payload["count"], 1)
        self.assertTrue(payload["summary"]["advisoryOnly"])
        self.assertTrue(payload["filters"]["includeAllVersions"])
        self.assertIn("notes", payload)
        target = next(row for row in payload["items"] if row["policyVersion"] == version)
        self.assertIn("domainJudgeFamily", target)
        self.assertIn("dependencyHealth", target)
        self.assertIn("fairnessGate", target)
        self.assertIn("simulatedGate", target)
        self.assertIn(target["simulatedGate"]["status"], {"pass", "blocked"})
        self.assertIsInstance(target["simulatedGate"]["failingComponents"], list)

        after_alerts = list(
            runtime.trace_store.list_audit_alerts(job_id=0, status=None, limit=500)
        )
        self.assertEqual(len(after_alerts), len(before_alerts))

    async def test_policy_gate_simulation_route_should_return_404_when_policy_missing(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        missing_version = f"policy-gate-sim-missing-{_unique_case_id(9216)}"
        sim_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/registries/policy/gate-simulation"
                f"?policy_version={missing_version}"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(sim_resp.status_code, 404)
        self.assertIn("policy_registry_not_found", sim_resp.text)

    async def test_registry_governance_overview_route_should_join_triple_dependency_usage_and_audits(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9218)
        prompt_version = f"promptset-governance-{suffix}"
        policy_invalid_version = f"policy-governance-invalid-{suffix}"
        actor = f"governance-actor-{suffix}"

        prompt_publish = await self._post_json(
            app=app,
            path="/internal/judge/registries/prompt/publish",
            payload={
                "version": prompt_version,
                "activate": False,
                "actor": actor,
                "reason": "governance_publish_prompt",
                "profile": {
                    "promptVersions": {
                        "claimGraphVersion": "v1-claim-graph-bootstrap",
                    },
                    "metadata": {
                        "status": "candidate",
                    },
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(prompt_publish.status_code, 200)

        prompt_activate = await self._post(
            app=app,
            path=(
                f"/internal/judge/registries/prompt/{prompt_version}/activate"
                f"?actor={actor}&reason=governance_activate_prompt"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(prompt_activate.status_code, 200)

        prompt_rollback = await self._post(
            app=app,
            path=(
                "/internal/judge/registries/prompt/rollback"
                f"?actor={actor}&reason=governance_rollback_prompt"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(prompt_rollback.status_code, 200)

        await runtime.registry_product_runtime.publish_release(
            registry_type="policy",
            version=policy_invalid_version,
            profile_payload={
                "rubricVersion": "v3",
                "topicDomain": "tft",
                "promptRegistryVersion": f"promptset-missing-{suffix}",
                "toolRegistryVersion": "toolset-v3-default",
            },
            actor="seed",
            reason="seed_invalid_prompt_dependency_for_governance_overview",
            activate=False,
        )

        overview_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/registries/governance/overview"
                "?dependency_limit=200&usage_preview_limit=10&release_limit=100&audit_limit=200"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(overview_resp.status_code, 200)
        payload = overview_resp.json()
        active_versions = payload["activeVersions"]
        self.assertTrue(str(active_versions["policyVersion"] or "").strip())
        self.assertTrue(str(active_versions["promptRegistryVersion"] or "").strip())
        self.assertTrue(str(active_versions["toolRegistryVersion"] or "").strip())

        dependency = payload["dependencyHealth"]
        self.assertGreaterEqual(dependency["count"], 1)
        self.assertGreaterEqual(dependency["invalidCount"], 1)
        invalid_row = next(
            (
                row
                for row in dependency["items"]
                if row["policyVersion"] == policy_invalid_version
            ),
            None,
        )
        self.assertIsNotNone(invalid_row)
        assert invalid_row is not None
        self.assertFalse(bool(invalid_row["ok"]))
        self.assertIn("prompt_registry_version_not_found", invalid_row["issueCodes"])
        self.assertEqual(invalid_row["policyKernelVersion"], "policy-kernel-binding-v1")
        self.assertTrue(str(invalid_row["policyKernelHash"] or "").strip())
        self.assertIn(f"promptset-missing-{suffix}", dependency["byPromptRegistryVersion"])

        reverse_usage = payload["reverseUsage"]
        prompt_row = next(
            (
                row
                for row in reverse_usage["prompts"]
                if row["version"] == prompt_version
            ),
            None,
        )
        self.assertIsNotNone(prompt_row)
        assert prompt_row is not None
        self.assertIsInstance(prompt_row["referencedByPolicyCount"], int)
        self.assertGreaterEqual(prompt_row["referencedByPolicyCount"], 0)
        domain_families = payload["domainJudgeFamilies"]
        self.assertIsInstance(domain_families, dict)
        self.assertGreaterEqual(domain_families["count"], 1)
        self.assertIn("allowedFamilies", domain_families)
        self.assertIn("items", domain_families)
        self.assertTrue(
            any(row["domainJudgeFamily"] == "tft" for row in domain_families["items"])
        )

        release_state = payload["releaseState"]
        self.assertIn("policy", release_state)
        self.assertIn("prompt", release_state)
        self.assertIn("tool", release_state)
        self.assertGreaterEqual(release_state["prompt"]["count"], 1)

        audit_summary = payload["auditSummary"]
        self.assertGreaterEqual(audit_summary["countsByAction"].get("publish", 0), 1)
        self.assertGreaterEqual(audit_summary["countsByAction"].get("activate", 0), 1)
        self.assertGreaterEqual(audit_summary["countsByAction"].get("rollback", 0), 1)
        latest_rollback = audit_summary["latestRollbackByRegistryType"]["prompt"]
        self.assertIsNotNone(latest_rollback)
        assert latest_rollback is not None
        self.assertEqual(latest_rollback["registryType"], "prompt")

    async def test_registry_prompt_tool_governance_route_should_return_risk_and_action_hints(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9220)
        actor = f"prompt-tool-governance-actor-{suffix}"
        orphan_prompt_version = f"promptset-orphan-{suffix}"
        missing_prompt_version = f"promptset-missing-{suffix}"
        missing_tool_version = f"toolset-missing-{suffix}"
        policy_invalid_version = f"policy-prompt-tool-risk-{suffix}"

        publish_prompt_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/prompt/publish",
            payload={
                "version": orphan_prompt_version,
                "activate": False,
                "actor": actor,
                "reason": "seed_orphan_prompt_for_prompt_tool_governance",
                "profile": {
                    "promptVersions": {
                        "claimGraphVersion": "v1-claim-graph-bootstrap",
                    },
                    "metadata": {
                        "status": "candidate",
                    },
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_prompt_resp.status_code, 200)

        await runtime.registry_product_runtime.publish_release(
            registry_type="policy",
            version=policy_invalid_version,
            profile_payload={
                "rubricVersion": "v3",
                "topicDomain": "tft",
                "promptRegistryVersion": missing_prompt_version,
                "toolRegistryVersion": missing_tool_version,
            },
            actor="seed",
            reason="seed_invalid_dependencies_for_prompt_tool_governance",
            activate=False,
        )

        route_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/registries/prompt-tool/governance"
                "?dependency_limit=200&usage_preview_limit=20&release_limit=50&audit_limit=100"
                "&risk_limit=3"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(route_resp.status_code, 200)
        payload = route_resp.json()
        self.assertIsInstance(payload["summary"], dict)
        self.assertIsInstance(payload["dependencyHealth"], dict)
        self.assertIsInstance(payload["promptToolUsage"], dict)
        self.assertIsInstance(payload["riskItems"], list)
        self.assertIsInstance(payload["actionHints"], list)
        self.assertEqual(payload["filters"]["riskLimit"], 3)

        summary = payload["summary"]
        self.assertIn(summary["riskLevel"], {"high", "medium", "low", "healthy"})
        self.assertGreaterEqual(summary["dependencyInvalidCount"], 1)
        self.assertGreaterEqual(summary["missingPromptRefCount"], 1)
        self.assertGreaterEqual(summary["missingToolRefCount"], 1)
        self.assertGreaterEqual(summary["unreferencedPromptCount"], 1)
        self.assertGreaterEqual(summary["riskTotalCount"], summary["riskReturned"])
        self.assertEqual(summary["riskReturned"], len(payload["riskItems"]))
        self.assertTrue(summary["riskTruncated"])

        prompt_usage = payload["promptToolUsage"]["prompts"]
        orphan_prompt_row = next(
            (row for row in prompt_usage if row["version"] == orphan_prompt_version),
            None,
        )
        self.assertIsNotNone(orphan_prompt_row)
        assert orphan_prompt_row is not None
        self.assertEqual(orphan_prompt_row["referencedByPolicyCount"], 0)
        self.assertIn("unreferenced", orphan_prompt_row["riskTags"])

        self.assertIn(
            missing_prompt_version,
            payload["promptToolUsage"]["missingPromptRegistryRefs"],
        )
        self.assertIn(
            missing_tool_version,
            payload["promptToolUsage"]["missingToolRegistryRefs"],
        )

        risk_types = {row.get("riskType") for row in payload["riskItems"]}
        self.assertIn("dependency_invalid", risk_types)
        action_ids = {row.get("actionId") for row in payload["actionHints"]}
        self.assertIn("registry.policy.dependencies.fix", action_ids)
        self.assertIn("registry.prompt.curate", action_ids)
        self.assertIn("registry.tool.curate", action_ids)

    async def test_policy_domain_judge_families_route_should_return_family_snapshot(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        version = f"policy-domain-family-{_unique_case_id(9219)}"
        publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-v3-default",
                    "toolRegistryVersion": "toolset-v3-default",
                    "metadata": {
                        "domainJudgeFamily": "tft",
                    },
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_resp.status_code, 200)
        publish_payload = publish_resp.json()
        self.assertEqual(publish_payload["policyDomainJudgeFamily"], "tft")

        route_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/registries/policy/domain-families"
                "?preview_limit=20&include_versions=true"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(route_resp.status_code, 200)
        payload = route_resp.json()
        self.assertIsInstance(payload["domainJudgeFamilies"], dict)
        self.assertGreaterEqual(payload["domainJudgeFamilies"]["count"], 1)
        self.assertIn("allowedFamilies", payload["domainJudgeFamilies"])
        tft_row = next(
            (
                row
                for row in payload["domainJudgeFamilies"]["items"]
                if row["domainJudgeFamily"] == "tft"
            ),
            None,
        )
        self.assertIsNotNone(tft_row)
        assert tft_row is not None
        self.assertGreaterEqual(tft_row["count"], 1)
        self.assertIn(version, tft_row["policyVersions"])

    async def test_policy_registry_publish_should_reject_domain_family_topic_mismatch(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        version = f"policy-family-mismatch-{_unique_case_id(9220)}"
        publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-v3-default",
                    "toolRegistryVersion": "toolset-v3-default",
                    "metadata": {
                        "domainJudgeFamily": "finance",
                    },
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_resp.status_code, 422)
        self.assertIn("policy_domain_family_topic_domain_mismatch", publish_resp.text)

    async def test_policy_registry_activate_override_should_require_reason_and_be_auditable(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9213)
        version = f"policy-gate-{suffix}"
        actor = f"policy-actor-{suffix}"

        publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": version,
                "activate": False,
                "actor": actor,
                "reason": "prepare_policy_release",
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_resp.status_code, 200)

        missing_reason_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/registries/policy/{version}/activate"
                f"?override_fairness_gate=true&actor={actor}"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(missing_reason_resp.status_code, 422)
        self.assertIn(
            "registry_fairness_gate_override_reason_required",
            missing_reason_resp.text,
        )

        activate_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/registries/policy/{version}/activate"
                f"?override_fairness_gate=true&actor={actor}&reason=manual_override_for_trial"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(activate_resp.status_code, 200)
        activate_payload = activate_resp.json()
        self.assertEqual(activate_payload["item"]["version"], version)
        self.assertTrue(activate_payload["item"]["isActive"])
        self.assertIsNotNone(activate_payload["dependencyHealth"])
        self.assertTrue(bool(activate_payload["dependencyHealth"]["ok"]))
        self.assertIsNotNone(activate_payload["fairnessGate"])
        self.assertTrue(
            activate_payload["fairnessGate"]["latestRun"] is None
            or isinstance(activate_payload["fairnessGate"]["latestRun"], dict)
        )

        audits_resp = await self._get(
            app=app,
            path="/internal/judge/registries/policy/audits?limit=200",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(audits_resp.status_code, 200)
        audit_items = audits_resp.json()["items"]
        override_audit = next(
            (
                item
                for item in audit_items
                if str(item.get("action") or "") == "activate"
                and str(item.get("version") or "") == version
                and str(item.get("actor") or "") == actor
            ),
            None,
        )
        self.assertIsNotNone(override_audit)
        assert override_audit is not None
        fairness_gate = override_audit["details"].get("fairnessGate")
        self.assertIsInstance(fairness_gate, dict)
        self.assertTrue(bool(fairness_gate.get("overrideApplied")))
        dependency_health = override_audit["details"].get("dependencyHealth")
        self.assertIsInstance(dependency_health, dict)
        self.assertTrue(bool(dependency_health.get("ok")))

    async def test_policy_registry_audits_should_support_gate_link_export_and_filters(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9220)
        override_version = f"policy-audit-override-{suffix}"
        override_actor = f"audit-actor-{suffix}"

        override_publish = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": override_version,
                "activate": False,
                "actor": override_actor,
                "reason": "audit_prepare",
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-v3-default",
                    "toolRegistryVersion": "toolset-v3-default",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(override_publish.status_code, 200)

        override_activate = await self._post(
            app=app,
            path=(
                f"/internal/judge/registries/policy/{override_version}/activate"
                f"?override_fairness_gate=true&actor={override_actor}"
                "&reason=audit_manual_override"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(override_activate.status_code, 200)
        override_gate_code = override_activate.json()["alert"]["details"]["gate"]["code"]

        audits_resp = await self._get(
            app=app,
            path="/internal/judge/registries/policy/audits?limit=200",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(audits_resp.status_code, 200)
        audits_payload = audits_resp.json()
        self.assertGreaterEqual(audits_payload["count"], 2)
        self.assertGreaterEqual(audits_payload["aggregations"]["byAction"]["publish"], 1)
        self.assertGreaterEqual(audits_payload["aggregations"]["byAction"]["activate"], 1)
        self.assertGreaterEqual(audits_payload["aggregations"]["byGateCode"][override_gate_code], 1)
        self.assertGreaterEqual(audits_payload["aggregations"]["withGateReviewCount"], 1)
        self.assertGreaterEqual(audits_payload["aggregations"]["withLinkedAlertsCount"], 1)
        target_item = next(
            (
                row
                for row in audits_payload["items"]
                if row["action"] == "activate"
                and row["version"] == override_version
                and row["actor"] == override_actor
            ),
            None,
        )
        self.assertIsNotNone(target_item)
        assert target_item is not None
        self.assertEqual(target_item["gateReview"]["gateCode"], override_gate_code)
        self.assertTrue(bool(target_item["gateReview"]["overrideApplied"]))
        self.assertIsInstance(target_item["linkedAlertSummary"], dict)
        self.assertGreaterEqual(target_item["linkedAlertSummary"]["count"], 1)
        self.assertGreaterEqual(
            target_item["linkedAlertSummary"]["byType"]["registry_fairness_gate_override"],
            1,
        )
        self.assertTrue(
            any(
                row["type"] == "registry_fairness_gate_override"
                for row in target_item["linkedAlerts"]
            )
        )

        gate_filter_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/registries/policy/audits"
                f"?action=activate&version={override_version}&actor={override_actor}"
                f"&gate_code={override_gate_code}&override_applied=true&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(gate_filter_resp.status_code, 200)
        gate_filter_payload = gate_filter_resp.json()
        self.assertGreaterEqual(gate_filter_payload["returned"], 1)
        self.assertEqual(gate_filter_payload["filters"]["action"], "activate")
        self.assertEqual(gate_filter_payload["filters"]["version"], override_version)
        self.assertEqual(gate_filter_payload["filters"]["actor"], override_actor)
        self.assertEqual(gate_filter_payload["filters"]["gateCode"], override_gate_code)
        self.assertTrue(bool(gate_filter_payload["filters"]["overrideApplied"]))
        self.assertTrue(
            all(
                row["action"] == "activate"
                and row["version"] == override_version
                and row["actor"] == override_actor
                and row["gateReview"]["gateCode"] == override_gate_code
                and bool(row["gateReview"]["overrideApplied"])
                for row in gate_filter_payload["items"]
            )
        )

        no_gate_view_resp = await self._get(
            app=app,
            path="/internal/judge/registries/policy/audits?include_gate_view=false&limit=20",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(no_gate_view_resp.status_code, 200)
        no_gate_view_payload = no_gate_view_resp.json()
        self.assertFalse(bool(no_gate_view_payload["filters"]["includeGateView"]))
        self.assertTrue(
            all(row["linkedAlerts"] is None for row in no_gate_view_payload["items"])
        )

        bad_action_resp = await self._get(
            app=app,
            path="/internal/judge/registries/policy/audits?action=invalid-action",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_action_resp.status_code, 422)
        self.assertIn("invalid_registry_audit_action", bad_action_resp.text)

    async def test_create_runtime_should_include_agent_runtime_shell_profiles(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        profiles = runtime.agent_runtime.list_profiles()
        kinds = [row.kind for row in profiles]
        self.assertEqual(kinds, ["judge", "npc_coach", "room_qa"])

    async def test_npc_coach_shell_route_should_return_not_ready_with_shared_context(
        self,
    ) -> None:
        async def _noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=_noop_callback,
            callback_final_report_impl=_noop_callback,
            callback_phase_failed_impl=_noop_callback,
            callback_final_failed_impl=_noop_callback,
        )
        app = create_app(runtime)

        phase_case_id = _unique_case_id(9301)
        phase_req = _build_phase_request(
            case_id=phase_case_id,
            idempotency_key=f"phase:{phase_case_id}",
        )
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        npc_resp = await self._post_json(
            app=app,
            path=f"/internal/judge/apps/npc-coach/sessions/{phase_req.session_id}/advice",
            payload={
                "trace_id": f"trace-npc-{phase_case_id}",
                "query": "请给我当前阶段的论点补强建议",
                "side": "pro",
                "caseId": phase_case_id,
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(npc_resp.status_code, 200)
        body = npc_resp.json()
        self.assertEqual(body["agentKind"], "npc_coach")
        self.assertEqual(body["status"], "not_ready")
        self.assertEqual(body["errorCode"], "agent_not_enabled")
        self.assertFalse(body["accepted"])
        self.assertEqual(body["capabilityBoundary"]["mode"], "advisory_only")
        self.assertFalse(bool(body["capabilityBoundary"]["officialVerdictAuthority"]))
        self.assertEqual(body["sharedContext"]["sessionId"], phase_req.session_id)
        self.assertEqual(body["sharedContext"]["caseId"], phase_case_id)
        self.assertEqual(body["sharedContext"]["latestDispatchType"], "phase")
        self.assertEqual(body["sharedContext"]["rubricVersion"], phase_req.rubric_version)
        self.assertEqual(
            body["sharedContext"]["judgePolicyVersion"],
            phase_req.judge_policy_version,
        )
        self.assertEqual(body["sharedContext"]["ruleVersion"], phase_req.judge_policy_version)
        self.assertGreaterEqual(body["sharedContext"]["phaseReceiptCount"], 1)

    async def test_room_qa_shell_route_should_return_not_ready_with_final_context(
        self,
    ) -> None:
        async def _noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=_noop_callback,
            callback_final_report_impl=_noop_callback,
            callback_phase_failed_impl=_noop_callback,
            callback_final_failed_impl=_noop_callback,
        )
        app = create_app(runtime)

        phase_case_id = _unique_case_id(9401)
        phase_req = _build_phase_request(
            case_id=phase_case_id,
            idempotency_key=f"phase:{phase_case_id}",
        )
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_case_id = _unique_case_id(9402)
        final_req = _build_final_request(
            case_id=final_case_id,
            idempotency_key=f"final:{final_case_id}",
        )
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        room_qa_resp = await self._post_json(
            app=app,
            path=f"/internal/judge/apps/room-qa/sessions/{final_req.session_id}/answer",
            payload={
                "trace_id": f"trace-room-qa-{final_case_id}",
                "question": "当前辩论进行到什么程度，哪一方更有优势？",
                "caseId": final_case_id,
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(room_qa_resp.status_code, 200)
        body = room_qa_resp.json()
        self.assertEqual(body["agentKind"], "room_qa")
        self.assertEqual(body["status"], "not_ready")
        self.assertEqual(body["errorCode"], "agent_not_enabled")
        self.assertFalse(body["accepted"])
        self.assertEqual(body["capabilityBoundary"]["mode"], "advisory_only")
        self.assertFalse(bool(body["capabilityBoundary"]["officialVerdictAuthority"]))
        self.assertEqual(body["sharedContext"]["sessionId"], final_req.session_id)
        self.assertEqual(body["sharedContext"]["caseId"], final_case_id)
        self.assertEqual(body["sharedContext"]["latestDispatchType"], "final")
        self.assertEqual(body["sharedContext"]["rubricVersion"], final_req.rubric_version)
        self.assertEqual(
            body["sharedContext"]["judgePolicyVersion"],
            final_req.judge_policy_version,
        )
        self.assertEqual(body["sharedContext"]["ruleVersion"], final_req.judge_policy_version)
        self.assertGreaterEqual(body["sharedContext"]["finalReceiptCount"], 1)

    async def test_npc_coach_route_should_strip_official_verdict_chain_fields(
        self,
    ) -> None:
        async def _noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        class _NpcAdvisoryTestExecutor:
            async def execute(self, request: Any) -> AgentExecutionResult:
                del request
                return AgentExecutionResult(
                    status="ok",
                    output={
                        "accepted": True,
                        "advice": "建议先补强证据再推进反驳。",
                        "winner": "pro",
                        "verdictReason": "should_be_blocked",
                        "nested": {
                            "needsDrawVote": True,
                            "hint": "保留字段",
                        },
                        "timeline": [
                            {
                                "dimensionScores": {"logic": 9},
                                "note": "保留注记",
                            }
                        ],
                    },
                )

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=_noop_callback,
            callback_final_report_impl=_noop_callback,
            callback_phase_failed_impl=_noop_callback,
            callback_final_failed_impl=_noop_callback,
        )
        runtime.agent_runtime.registry._executors["npc_coach"] = _NpcAdvisoryTestExecutor()  # type: ignore[attr-defined]
        app = create_app(runtime)

        phase_case_id = _unique_case_id(9351)
        phase_req = _build_phase_request(
            case_id=phase_case_id,
            idempotency_key=f"phase:{phase_case_id}",
        )
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        npc_resp = await self._post_json(
            app=app,
            path=f"/internal/judge/apps/npc-coach/sessions/{phase_req.session_id}/advice",
            payload={
                "trace_id": f"trace-npc-{phase_case_id}",
                "query": "请给我当前阶段的论点补强建议",
                "side": "pro",
                "caseId": phase_case_id,
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(npc_resp.status_code, 200)
        body = npc_resp.json()
        self.assertEqual(body["status"], "ok")
        self.assertTrue(body["accepted"])
        self.assertEqual(body["capabilityBoundary"]["mode"], "advisory_only")
        self.assertFalse(bool(body["capabilityBoundary"]["officialVerdictAuthority"]))
        self.assertNotIn("winner", body["output"])
        self.assertNotIn("verdictReason", body["output"])
        self.assertNotIn("needsDrawVote", body["output"]["nested"])
        self.assertEqual(body["output"]["nested"]["hint"], "保留字段")
        self.assertNotIn("dimensionScores", body["output"]["timeline"][0])
        self.assertEqual(body["output"]["timeline"][0]["note"], "保留注记")

    async def test_review_routes_should_list_detail_and_decide_review_job(self) -> None:
        async def noop_phase_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        async def noop_final_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_phase_callback,
            callback_final_report_impl=noop_final_callback,
            callback_phase_failed_impl=noop_phase_callback,
            callback_final_failed_impl=noop_final_callback,
        )
        app = create_app(runtime)
        final_req = _build_final_request(case_id=7411, idempotency_key="final:7411")
        gated_payload = {
            "sessionId": 2,
            "winner": "draw",
            "proScore": 60.8,
            "conScore": 60.2,
            "dimensionScores": {
                "logic": 60.5,
                "evidence": 60.2,
                "rebuttal": 59.9,
                "clarity": 60.1,
            },
            "debateSummary": "summary",
            "sideAnalysis": {"pro": "pro", "con": "con"},
            "verdictReason": "reason",
            "claimGraph": {
                "pipelineVersion": "v1-claim-graph-bootstrap",
                "nodes": [],
                "edges": [],
                "unansweredClaimIds": [],
                "stats": {
                    "totalClaims": 0,
                    "proClaims": 0,
                    "conClaims": 0,
                    "conflictEdges": 0,
                    "unansweredClaims": 0,
                    "weakSupportedClaims": 0,
                    "verdictReferencedClaims": 0,
                },
            },
            "claimGraphSummary": {
                "coreClaims": {"pro": [], "con": []},
                "conflictPairs": [],
                "unansweredClaims": [],
                "stats": {
                    "totalClaims": 0,
                    "proClaims": 0,
                    "conClaims": 0,
                    "conflictEdges": 0,
                    "unansweredClaims": 0,
                    "weakSupportedClaims": 0,
                    "verdictReferencedClaims": 0,
                },
            },
            "evidenceLedger": {
                "pipelineVersion": "v3-evidence-bundle",
                "entries": [],
                "refsById": {},
                "messageRefs": [],
                "sourceCitations": [],
                "conflictSources": [],
                "stats": {
                    "totalEntries": 0,
                    "messageRefCount": 0,
                    "sourceCitationCount": 0,
                    "conflictSourceCount": 0,
                    "verdictReferencedCount": 0,
                },
            },
            "verdictLedger": {
                "version": "v2-panel-arbiter-opinion",
                "scoreCard": {"proScore": 60.8, "conScore": 60.2, "dimensionScores": {"logic": 60.5}},
                "panelDecisions": {"probeWinners": {"agent3Weighted": "pro"}},
                "arbitration": {
                    "chainVersion": "v1-panel-fairness-arbiter",
                    "decisionPath": ["judge_panel", "fairness_sentinel", "chief_arbiter"],
                    "fairnessGateApplied": True,
                    "winnerBeforeFairnessGate": "pro",
                    "winnerAfterArbitration": "draw",
                    "gateDecision": "blocked_to_draw",
                    "reviewRequired": True,
                },
                "pivotalMoments": [],
                "decisiveEvidenceRefs": [],
            },
            "opinionPack": {
                "version": "v2-opinion-pack",
                "userReport": {
                    "winner": "draw",
                    "debateSummary": "summary",
                    "sideAnalysis": {"pro": "pro", "con": "con"},
                    "verdictReason": "reason",
                    "phaseDebateTimeline": [],
                    "evidenceInsightCards": [],
                },
                "opsSummary": {"reviewRequired": True},
                "internalReview": {"traceId": "trace-final-7411"},
            },
            "verdictEvidenceRefs": [],
            "phaseRollupSummary": [{"phaseNo": 1}],
            "retrievalSnapshotRollup": [],
            "winnerFirst": "pro",
            "winnerSecond": "pro",
            "winnerThird": "con",
            "rejudgeTriggered": True,
            "needsDrawVote": True,
            "reviewRequired": True,
            "judgeTrace": {
                "traceId": "trace-final-7411",
                "fairnessGate": {
                    "phase": "phase2",
                    "panelHighDisagreement": True,
                    "reviewRequired": True,
                },
            },
            "fairnessSummary": {
                "phase": "phase2",
                "panelHighDisagreement": True,
                "reviewRequired": True,
                "gateDecision": "blocked_to_draw",
                "reviewReasons": ["judge_panel_high_disagreement"],
            },
            "auditAlerts": [{"type": "judge_panel_high_disagreement"}],
            "errorCodes": ["judge_panel_high_disagreement", "fairness_gate_review_required"],
            "degradationLevel": 1,
        }

        with patch(
            "app.applications.bootstrap_final_report_helpers.build_final_report_payload_for_dispatch_v3",
            return_value=gated_payload,
        ):
            final_resp = await self._post_json(
                app=app,
                path="/internal/judge/v3/final/dispatch",
                payload=final_req.model_dump(mode="json"),
                internal_key=runtime.settings.ai_internal_key,
            )
        self.assertEqual(final_resp.status_code, 200)

        list_resp = await self._get(
            app=app,
            path="/internal/judge/review/cases?status=review_required&dispatch_type=final",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(list_resp.status_code, 200)
        queue_payload = list_resp.json()
        self.assertGreaterEqual(queue_payload["count"], 1)
        target_item = next(
            item for item in queue_payload["items"] if item["workflow"]["caseId"] == 7411
        )
        self.assertTrue(target_item["reviewRequired"])
        self.assertIn("judge_panel_high_disagreement", target_item["errorCodes"])

        detail_resp = await self._get(
            app=app,
            path="/internal/judge/review/cases/7411",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(detail_resp.status_code, 200)
        detail_payload = detail_resp.json()
        self.assertEqual(detail_payload["job"]["status"], "review_required")
        self.assertTrue(detail_payload["reviewRequired"])
        self.assertEqual(
            detail_payload["reportPayload"]["fairnessSummary"]["panelHighDisagreement"],
            True,
        )

        pending_challenge_resp = await self._get(
            app=app,
            path="/internal/judge/cases/7411/trust/challenges?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(pending_challenge_resp.status_code, 200)
        pending_challenge_item = pending_challenge_resp.json()["item"]
        self.assertEqual(pending_challenge_item["reviewState"], "pending_review")
        self.assertIn("judge_panel_high_disagreement", pending_challenge_item["challengeReasons"])

        decision_resp = await self._post(
            app=app,
            path="/internal/judge/review/cases/7411/decision?decision=approve&actor=ops&reason=manual_pass",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(decision_resp.status_code, 200)
        decision_payload = decision_resp.json()
        self.assertEqual(decision_payload["decision"], "approve")
        self.assertEqual(decision_payload["job"]["status"], "callback_reported")

        workflow_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=7411)
        self.assertIsNotNone(workflow_job)
        assert workflow_job is not None
        self.assertEqual(workflow_job.status, "callback_reported")
        workflow_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=7411)
        self.assertEqual(workflow_events[-1].payload.get("judgeCoreStage"), "review_approved")

        approved_challenge_resp = await self._get(
            app=app,
            path="/internal/judge/cases/7411/trust/challenges?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(approved_challenge_resp.status_code, 200)
        approved_challenge_item = approved_challenge_resp.json()["item"]
        self.assertEqual(approved_challenge_item["reviewState"], "approved")
        self.assertEqual(approved_challenge_item["openAlertIds"], [])

    async def test_review_cases_route_should_support_risk_filter_and_sorting(self) -> None:
        async def noop_phase_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        async def noop_final_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_phase_callback,
            callback_final_report_impl=noop_final_callback,
            callback_phase_failed_impl=noop_phase_callback,
            callback_final_failed_impl=noop_final_callback,
        )
        app = create_app(runtime)

        def _build_review_payload(
            *,
            trace_id: str,
            panel_high_disagreement: bool,
            error_codes: list[str],
            audit_alerts: list[dict[str, Any]],
        ) -> dict[str, Any]:
            return {
                "sessionId": 2,
                "winner": "draw",
                "proScore": 61.0,
                "conScore": 60.2,
                "dimensionScores": {
                    "logic": 60.0,
                    "evidence": 61.0,
                    "rebuttal": 59.5,
                    "clarity": 60.4,
                },
                "debateSummary": "summary",
                "sideAnalysis": {"pro": "pro", "con": "con"},
                "verdictReason": "reason",
                "claimGraph": {
                    "pipelineVersion": "v1-claim-graph-bootstrap",
                    "nodes": [],
                    "edges": [],
                    "unansweredClaimIds": [],
                    "stats": {
                        "totalClaims": 0,
                        "proClaims": 0,
                        "conClaims": 0,
                        "conflictEdges": 0,
                        "unansweredClaims": 0,
                        "weakSupportedClaims": 0,
                        "verdictReferencedClaims": 0,
                    },
                },
                "claimGraphSummary": {
                    "coreClaims": {"pro": [], "con": []},
                    "conflictPairs": [],
                    "unansweredClaims": [],
                    "stats": {
                        "totalClaims": 0,
                        "proClaims": 0,
                        "conClaims": 0,
                        "conflictEdges": 0,
                        "unansweredClaims": 0,
                        "weakSupportedClaims": 0,
                        "verdictReferencedClaims": 0,
                    },
                },
                "evidenceLedger": {
                    "pipelineVersion": "v3-evidence-bundle",
                    "entries": [],
                    "refsById": {},
                    "messageRefs": [],
                    "sourceCitations": [],
                    "conflictSources": [],
                    "stats": {
                        "totalEntries": 0,
                        "messageRefCount": 0,
                        "sourceCitationCount": 0,
                        "conflictSourceCount": 0,
                        "verdictReferencedCount": 0,
                    },
                },
                "verdictLedger": {
                    "version": "v2-panel-arbiter-opinion",
                    "scoreCard": {
                        "proScore": 61.0,
                        "conScore": 60.2,
                        "dimensionScores": {"logic": 60.0},
                    },
                    "panelDecisions": {"probeWinners": {"agent3Weighted": "pro"}},
                    "arbitration": {
                        "chainVersion": "v1-panel-fairness-arbiter",
                        "decisionPath": ["judge_panel", "fairness_sentinel", "chief_arbiter"],
                        "fairnessGateApplied": True,
                        "winnerBeforeFairnessGate": "pro",
                        "winnerAfterArbitration": "draw",
                        "gateDecision": "blocked_to_draw",
                        "reviewRequired": True,
                    },
                    "pivotalMoments": [],
                    "decisiveEvidenceRefs": [],
                },
                "opinionPack": {
                    "version": "v2-opinion-pack",
                    "userReport": {
                        "winner": "draw",
                        "debateSummary": "summary",
                        "sideAnalysis": {"pro": "pro", "con": "con"},
                        "verdictReason": "reason",
                        "phaseDebateTimeline": [],
                        "evidenceInsightCards": [],
                    },
                    "opsSummary": {"reviewRequired": True},
                    "internalReview": {"traceId": trace_id},
                },
                "verdictEvidenceRefs": [],
                "phaseRollupSummary": [{"phaseNo": 1}],
                "retrievalSnapshotRollup": [],
                "winnerFirst": "pro",
                "winnerSecond": "pro",
                "rejudgeTriggered": True,
                "needsDrawVote": True,
                "reviewRequired": True,
                "judgeTrace": {"traceId": trace_id},
                "fairnessSummary": {
                    "phase": "phase2",
                    "panelHighDisagreement": panel_high_disagreement,
                    "reviewRequired": True,
                    "gateDecision": "blocked_to_draw",
                    "reviewReasons": [str(error_codes[0]) if error_codes else "review_required"],
                },
                "auditAlerts": audit_alerts,
                "errorCodes": error_codes,
                "degradationLevel": 1,
            }

        high_risk_case_id = _unique_case_id(7421)
        low_risk_case_id = _unique_case_id(7422)

        payload_call_index = {"value": 0}

        def _payload_side_effect(*args, **kwargs):
            payload_call_index["value"] += 1
            if payload_call_index["value"] == 1:
                return _build_review_payload(
                    trace_id=f"trace-final-{high_risk_case_id}",
                    panel_high_disagreement=True,
                    error_codes=["judge_panel_high_disagreement", "fairness_gate_review_required"],
                    audit_alerts=[
                        {"type": "judge_panel_high_disagreement"},
                        {"type": "fairness_gate_review_required"},
                    ],
                )
            return _build_review_payload(
                trace_id=f"trace-final-{low_risk_case_id}",
                panel_high_disagreement=False,
                error_codes=["fairness_gate_review_required"],
                audit_alerts=[],
            )

        with patch(
            "app.applications.bootstrap_final_report_helpers.build_final_report_payload_for_dispatch_v3",
            side_effect=_payload_side_effect,
        ):
            high_resp = await self._post_json(
                app=app,
                path="/internal/judge/v3/final/dispatch",
                payload=_build_final_request(
                    case_id=high_risk_case_id,
                    idempotency_key=f"final:{high_risk_case_id}",
                ).model_dump(mode="json"),
                internal_key=runtime.settings.ai_internal_key,
            )
            self.assertEqual(high_resp.status_code, 200)
            low_resp = await self._post_json(
                app=app,
                path="/internal/judge/v3/final/dispatch",
                payload=_build_final_request(
                    case_id=low_risk_case_id,
                    idempotency_key=f"final:{low_risk_case_id}",
                ).model_dump(mode="json"),
                internal_key=runtime.settings.ai_internal_key,
            )
            self.assertEqual(low_resp.status_code, 200)

        high_filter_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/review/cases"
                "?status=review_required&dispatch_type=final"
                "&risk_level=high&sort_by=risk_score&sort_order=desc"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(high_filter_resp.status_code, 200)
        high_filter_payload = high_filter_resp.json()
        self.assertGreaterEqual(high_filter_payload["count"], 1)
        self.assertEqual(high_filter_payload["filters"]["riskLevel"], "high")
        self.assertEqual(high_filter_payload["filters"]["sortBy"], "risk_score")
        self.assertGreaterEqual(high_filter_payload["returned"], 1)
        self.assertEqual(
            high_filter_payload["items"][0]["workflow"]["caseId"],
            high_risk_case_id,
        )
        self.assertEqual(
            high_filter_payload["items"][0]["riskProfile"]["level"],
            "high",
        )
        self.assertGreaterEqual(
            int(high_filter_payload["items"][0]["riskProfile"]["score"]),
            75,
        )

        sorted_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/review/cases"
                "?status=review_required&dispatch_type=final"
                "&sla_bucket=normal&sort_by=risk_score&sort_order=desc"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(sorted_resp.status_code, 200)
        sorted_payload = sorted_resp.json()
        self.assertEqual(sorted_payload["count"], 2)
        self.assertEqual(sorted_payload["filters"]["slaBucket"], "normal")
        self.assertEqual(sorted_payload["items"][0]["workflow"]["caseId"], high_risk_case_id)
        self.assertEqual(sorted_payload["items"][1]["workflow"]["caseId"], low_risk_case_id)

    async def test_review_cases_route_should_include_trust_association_and_unified_priority(self) -> None:
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

        challenged_case_id = _unique_case_id(8521)
        plain_case_id = _unique_case_id(8522)
        forced_review_cases = {challenged_case_id, plain_case_id}

        def _build_review_payload(
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
            if int(request.case_id) in forced_review_cases:
                payload["reviewRequired"] = True
                fairness_summary = (
                    payload.get("fairnessSummary")
                    if isinstance(payload.get("fairnessSummary"), dict)
                    else {}
                )
                fairness_summary["reviewRequired"] = True
                fairness_summary["gateDecision"] = "blocked_to_draw"
                fairness_summary["reviewReasons"] = ["review_required"]
                payload["fairnessSummary"] = fairness_summary
                verdict_ledger = (
                    payload.get("verdictLedger")
                    if isinstance(payload.get("verdictLedger"), dict)
                    else {}
                )
                arbitration = (
                    verdict_ledger.get("arbitration")
                    if isinstance(verdict_ledger.get("arbitration"), dict)
                    else {}
                )
                arbitration["reviewRequired"] = True
                arbitration["gateDecision"] = "blocked_to_draw"
                verdict_ledger["arbitration"] = arbitration
                payload["verdictLedger"] = verdict_ledger
                payload["errorCodes"] = ["review_required", "fairness_gate_review_required"]
                payload["degradationLevel"] = max(1, int(payload.get("degradationLevel") or 0))
            return payload

        with patch(
            "app.applications.bootstrap_final_report_helpers.build_final_report_payload_for_dispatch_v3",
            side_effect=_build_review_payload,
        ):
            for case_id in (challenged_case_id, plain_case_id):
                final_resp = await self._post_json(
                    app=app,
                    path="/internal/judge/v3/final/dispatch",
                    payload=_build_final_request(
                        case_id=case_id,
                        idempotency_key=f"final:{case_id}",
                    ).model_dump(mode="json"),
                    internal_key=runtime.settings.ai_internal_key,
                )
                self.assertEqual(final_resp.status_code, 200)

        challenge_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/cases/{challenged_case_id}/trust/challenges/request"
                "?dispatch_type=auto&reason_code=manual_challenge&reason=need_recheck"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(challenge_resp.status_code, 200)

        open_only_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/review/cases"
                "?status=review_required&dispatch_type=final"
                "&challenge_state=open&trust_review_state=pending_review"
                "&sort_by=unified_priority_score&sort_order=desc"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(open_only_resp.status_code, 200)
        open_only_payload = open_only_resp.json()
        self.assertEqual(open_only_payload["count"], 1)
        item = open_only_payload["items"][0]
        self.assertEqual(item["workflow"]["caseId"], challenged_case_id)
        self.assertEqual(item["trustChallenge"]["state"], "under_review")
        self.assertEqual(item["trustChallenge"]["reviewState"], "pending_review")
        self.assertIsInstance(item["trustPriorityProfile"], dict)
        self.assertIsInstance(item["unifiedPriorityProfile"], dict)
        self.assertGreaterEqual(
            int(item["unifiedPriorityProfile"]["score"]),
            int(item["riskProfile"]["score"]),
        )
        self.assertEqual(open_only_payload["filters"]["challengeState"], "open")
        self.assertEqual(open_only_payload["filters"]["trustReviewState"], "pending_review")
        self.assertEqual(open_only_payload["filters"]["sortBy"], "unified_priority_score")

        merged_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/review/cases"
                "?status=review_required&dispatch_type=final"
                "&sort_by=unified_priority_score&sort_order=desc"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(merged_resp.status_code, 200)
        merged_payload = merged_resp.json()
        self.assertEqual(merged_payload["count"], 2)
        self.assertEqual(
            merged_payload["items"][0]["workflow"]["caseId"],
            challenged_case_id,
        )
        self.assertEqual(
            merged_payload["items"][1]["workflow"]["caseId"],
            plain_case_id,
        )

    async def test_review_cases_route_should_validate_trust_priority_query_values(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)

        invalid_challenge_state_resp = await self._get(
            app=app,
            path="/internal/judge/review/cases?challenge_state=invalid",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(invalid_challenge_state_resp.status_code, 422)
        self.assertIn("invalid_review_challenge_state", invalid_challenge_state_resp.text)

        invalid_review_state_resp = await self._get(
            app=app,
            path="/internal/judge/review/cases?trust_review_state=invalid",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(invalid_review_state_resp.status_code, 422)
        self.assertIn("invalid_review_trust_review_state", invalid_review_state_resp.text)

        invalid_unified_level_resp = await self._get(
            app=app,
            path="/internal/judge/review/cases?unified_priority_level=extreme",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(invalid_unified_level_resp.status_code, 422)
        self.assertIn(
            "invalid_review_unified_priority_level",
            invalid_unified_level_resp.text,
        )

    async def test_trust_challenge_request_and_decision_should_drive_phaseb_lifecycle(
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

        case_id = _unique_case_id(8420)
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

        before_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=case_id)
        self.assertIsNotNone(before_job)
        assert before_job is not None
        self.assertEqual(before_job.status, "callback_reported")

        request_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/cases/{case_id}/trust/challenges/request"
                "?dispatch_type=auto&reason_code=manual_challenge&reason=need_recheck&requested_by=ops"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(request_resp.status_code, 200)
        request_payload = request_resp.json()
        self.assertTrue(request_payload["ok"])
        self.assertEqual(request_payload["dispatchType"], "final")
        self.assertTrue(str(request_payload["challengeId"]).startswith(f"chlg-{case_id}-"))
        self.assertEqual(request_payload["item"]["version"], "trust-phaseB-challenge-review-v1")
        self.assertEqual(request_payload["item"]["reviewState"], "pending_review")
        self.assertEqual(request_payload["item"]["challengeState"], "under_review")
        self.assertEqual(request_payload["item"]["activeChallengeId"], request_payload["challengeId"])
        self.assertGreaterEqual(request_payload["item"]["totalChallenges"], 1)

        review_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=case_id)
        self.assertIsNotNone(review_job)
        assert review_job is not None
        self.assertEqual(review_job.status, "review_required")

        decision_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/cases/{case_id}/trust/challenges/{request_payload['challengeId']}/decision"
                "?dispatch_type=auto&decision=uphold&actor=reviewer&reason=verified"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(decision_resp.status_code, 200)
        decision_payload = decision_resp.json()
        self.assertTrue(decision_payload["ok"])
        self.assertEqual(decision_payload["decision"], "uphold")
        self.assertEqual(decision_payload["job"]["status"], "callback_reported")
        self.assertEqual(decision_payload["item"]["reviewState"], "approved")
        self.assertEqual(decision_payload["item"]["challengeState"], "challenge_closed")
        self.assertEqual(decision_payload["item"]["activeChallengeId"], None)
        challenges = decision_payload["item"]["challenges"]
        self.assertTrue(any(row["challengeId"] == request_payload["challengeId"] for row in challenges))
        target = next(row for row in challenges if row["challengeId"] == request_payload["challengeId"])
        self.assertEqual(target["currentState"], "challenge_closed")
        self.assertEqual(target["decision"], "verdict_upheld")
        self.assertEqual(target["decisionBy"], "reviewer")

        final_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=case_id)
        self.assertIsNotNone(final_job)
        assert final_job is not None
        self.assertEqual(final_job.status, "callback_reported")

    async def test_trust_challenge_ops_queue_route_should_support_state_and_priority_filters(
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

        open_case_id = _unique_case_id(8451)
        closed_case_id = _unique_case_id(8452)
        passive_case_id = _unique_case_id(8453)

        for case_id in (open_case_id, closed_case_id, passive_case_id):
            final_resp = await self._post_json(
                app=app,
                path="/internal/judge/v3/final/dispatch",
                payload=_build_final_request(
                    case_id=case_id,
                    idempotency_key=f"final:{case_id}",
                ).model_dump(mode="json"),
                internal_key=runtime.settings.ai_internal_key,
            )
            self.assertEqual(final_resp.status_code, 200)

        open_request_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/cases/{open_case_id}/trust/challenges/request"
                "?dispatch_type=auto&reason_code=manual_challenge&reason=open_case"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(open_request_resp.status_code, 200)
        open_challenge_id = open_request_resp.json()["challengeId"]

        closed_request_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/cases/{closed_case_id}/trust/challenges/request"
                "?dispatch_type=auto&reason_code=manual_challenge&reason=closed_case"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(closed_request_resp.status_code, 200)
        closed_challenge_id = closed_request_resp.json()["challengeId"]
        closed_decision_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/cases/{closed_case_id}/trust/challenges/{closed_challenge_id}/decision"
                "?dispatch_type=auto&decision=uphold&actor=ops&reason=verified"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(closed_decision_resp.status_code, 200)

        open_queue_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/trust/challenges/ops-queue"
                "?dispatch_type=auto&challenge_state=open&sort_by=priority_score"
                "&sort_order=desc&scan_limit=300&offset=0&limit=20"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(open_queue_resp.status_code, 200)
        open_queue_payload = open_queue_resp.json()
        self.assertGreaterEqual(open_queue_payload["count"], 1)
        self.assertGreaterEqual(open_queue_payload["returned"], 1)
        open_case_item = next(
            item for item in open_queue_payload["items"] if item["caseId"] == open_case_id
        )
        self.assertEqual(open_case_item["challengeReview"]["state"], "under_review")
        self.assertEqual(open_case_item["challengeReview"]["activeChallengeId"], open_challenge_id)
        self.assertEqual(open_case_item["review"]["state"], "pending_review")
        self.assertIn(
            open_case_item["priorityProfile"]["level"],
            {"medium", "high"},
        )
        self.assertIn("trust.challenge.decide", open_case_item["actionHints"])
        self.assertIn("review.queue.decide", open_case_item["actionHints"])
        self.assertIn(
            f"/internal/judge/cases/{open_case_id}/trust/challenges/{open_challenge_id}/decision",
            str(open_case_item["actionPaths"]["decisionPath"]),
        )
        self.assertEqual(open_queue_payload["filters"]["challengeState"], "open")
        self.assertEqual(open_queue_payload["filters"]["sortBy"], "priority_score")

        closed_queue_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/trust/challenges/ops-queue"
                "?dispatch_type=auto&challenge_state=challenge_closed"
                "&review_state=approved&sort_by=case_id&sort_order=asc"
                "&scan_limit=300&offset=0&limit=20"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(closed_queue_resp.status_code, 200)
        closed_queue_payload = closed_queue_resp.json()
        self.assertGreaterEqual(closed_queue_payload["count"], 1)
        closed_case_item = next(
            item for item in closed_queue_payload["items"] if item["caseId"] == closed_case_id
        )
        self.assertEqual(closed_case_item["challengeReview"]["state"], "challenge_closed")
        self.assertEqual(closed_case_item["review"]["state"], "approved")
        self.assertEqual(closed_case_item["review"]["workflowStatus"], "callback_reported")
        self.assertIsNone(closed_case_item["actionPaths"]["decisionPath"])
        self.assertEqual(closed_queue_payload["filters"]["reviewState"], "approved")

    async def test_trust_challenge_ops_queue_route_should_validate_query_values(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)

        invalid_state_resp = await self._get(
            app=app,
            path="/internal/judge/trust/challenges/ops-queue?challenge_state=invalid",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(invalid_state_resp.status_code, 422)
        self.assertIn("invalid_trust_challenge_state", invalid_state_resp.text)

        invalid_priority_resp = await self._get(
            app=app,
            path="/internal/judge/trust/challenges/ops-queue?priority_level=extreme",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(invalid_priority_resp.status_code, 422)
        self.assertIn("invalid_trust_priority_level", invalid_priority_resp.text)

        invalid_sort_resp = await self._get(
            app=app,
            path="/internal/judge/trust/challenges/ops-queue?sort_by=unknown",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(invalid_sort_resp.status_code, 422)
        self.assertIn("invalid_trust_sort_by", invalid_sort_resp.text)

    async def test_trust_challenge_ops_queue_route_should_return_500_when_contract_validation_fails(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)

        with patch(
            "app.applications.bootstrap_review_alert_trust_payload_helpers."
            "validate_trust_challenge_queue_contract_v3",
            side_effect=ValueError("trust_challenge_queue_missing_keys:items"),
        ):
            resp = await self._get(
                app=app,
                path="/internal/judge/trust/challenges/ops-queue?dispatch_type=final",
                internal_key=runtime.settings.ai_internal_key,
            )

        self.assertEqual(resp.status_code, 500)
        detail = resp.json()["detail"]
        self.assertEqual(detail["code"], "trust_challenge_ops_queue_contract_violation")
        self.assertIn("trust_challenge_queue_missing_keys:items", detail["message"])

    async def test_create_default_app_should_be_constructible(self) -> None:
        app = create_default_app(load_settings_fn=_build_settings)
        self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main()
