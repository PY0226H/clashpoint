import unittest
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch

from app.app_factory import create_app, create_default_app, create_runtime
from app.applications import (
    build_final_report_payload as build_final_report_payload_v3_final,
)
from app.applications.fairness_case_contract import (
    CASE_FAIRNESS_AGGREGATIONS_KEYS,
    CASE_FAIRNESS_DETAIL_TOP_LEVEL_KEYS,
    CASE_FAIRNESS_FILTER_KEYS,
    CASE_FAIRNESS_ITEM_KEYS,
    CASE_FAIRNESS_LIST_TOP_LEVEL_KEYS,
    validate_case_fairness_detail_contract,
    validate_case_fairness_list_contract,
)
from app.applications.fairness_dashboard_contract import (
    FAIRNESS_DASHBOARD_FILTER_KEYS,
    FAIRNESS_DASHBOARD_GATE_DISTRIBUTION_KEYS,
    FAIRNESS_DASHBOARD_OVERVIEW_KEYS,
    FAIRNESS_DASHBOARD_TOP_LEVEL_KEYS,
    FAIRNESS_DASHBOARD_TRENDS_KEYS,
    validate_fairness_dashboard_contract,
)
from app.applications.ops_read_model_pack import (
    OPS_READ_MODEL_PACK_V5_ADAPTIVE_SUMMARY_KEYS,
    OPS_READ_MODEL_PACK_V5_FILTER_KEYS,
    OPS_READ_MODEL_PACK_V5_JUDGE_WORKFLOW_COVERAGE_KEYS,
    OPS_READ_MODEL_PACK_V5_TOP_LEVEL_KEYS,
    OPS_READ_MODEL_PACK_V5_TRUST_OVERVIEW_KEYS,
    validate_ops_read_model_pack_v5_contract,
)
from app.applications.panel_runtime_profile_contract import (
    PANEL_RUNTIME_PROFILE_AGGREGATIONS_KEYS,
    PANEL_RUNTIME_PROFILE_FILTER_KEYS,
    PANEL_RUNTIME_PROFILE_ITEM_KEYS,
    PANEL_RUNTIME_PROFILE_TOP_LEVEL_KEYS,
    validate_panel_runtime_profile_contract,
)
from app.domain.agents import AgentExecutionResult
from app.models import (
    CaseCreateRequest,
    FinalDispatchRequest,
    PhaseDispatchMessage,
    PhaseDispatchRequest,
)
from httpx import ASGITransport, AsyncClient

from tests.app_factory_test_helpers import build_settings as _build_settings


def _build_phase_request(
    *,
    case_id: int = 101,
    idempotency_key: str = "phase-key-101",
    rubric_version: str = "v3",
    judge_policy_version: str = "v3-default",
) -> PhaseDispatchRequest:
    now = datetime.now(timezone.utc)
    return PhaseDispatchRequest(
        case_id=case_id,
        scope_id=1,
        session_id=2,
        phase_no=1,
        message_start_id=1,
        message_end_id=2,
        message_count=2,
        messages=[
            PhaseDispatchMessage(
                message_id=1,
                side="pro",
                content="pro message",
                created_at=now,
                speaker_tag="pro_1",
            ),
            PhaseDispatchMessage(
                message_id=2,
                side="con",
                content="con message",
                created_at=now,
                speaker_tag="con_1",
            ),
        ],
        rubric_version=rubric_version,
        judge_policy_version=judge_policy_version,
        topic_domain="tft",
        retrieval_profile="hybrid_v1",
        trace_id=f"trace-phase-{case_id}",
        idempotency_key=idempotency_key,
    )


def _build_final_request(
    *,
    case_id: int = 202,
    idempotency_key: str = "final-key-202",
    rubric_version: str = "v3",
    judge_policy_version: str = "v3-default",
) -> FinalDispatchRequest:
    return FinalDispatchRequest(
        case_id=case_id,
        scope_id=1,
        session_id=2,
        phase_start_no=1,
        phase_end_no=1,
        rubric_version=rubric_version,
        judge_policy_version=judge_policy_version,
        topic_domain="tft",
        trace_id=f"trace-final-{case_id}",
        idempotency_key=idempotency_key,
    )


def _build_case_create_request(
    *,
    case_id: int = 901,
    idempotency_key: str = "case-key-901",
    rubric_version: str = "v3",
    judge_policy_version: str = "v3-default",
) -> CaseCreateRequest:
    return CaseCreateRequest(
        case_id=case_id,
        scope_id=1,
        session_id=2,
        rubric_version=rubric_version,
        judge_policy_version=judge_policy_version,
        topic_domain="tft",
        retrieval_profile="hybrid_v1",
        trace_id=f"trace-case-{case_id}",
        idempotency_key=idempotency_key,
    )


def _unique_case_id(seed: int) -> int:
    # 使用时间戳生成本地唯一 case_id，避免 sqlite 测试库跨命令复用导致冲突。
    return int(datetime.now(timezone.utc).timestamp() * 1_000_000) + seed


class AppFactoryTests(unittest.IsolatedAsyncioTestCase):
    async def _post_json(
        self,
        *,
        app,
        path: str,
        payload: dict,
        internal_key: str,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                path,
                json=payload,
                headers={"x-ai-internal-key": internal_key},
            )

    async def _get(self, *, app, path: str, internal_key: str):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(
                path,
                headers={"x-ai-internal-key": internal_key},
            )

    async def _post(self, *, app, path: str, internal_key: str):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                path,
                headers={"x-ai-internal-key": internal_key},
            )

    async def test_case_create_should_mark_case_built_and_support_idempotent_replay(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)

        case_id = _unique_case_id(11)
        req = _build_case_create_request(
            case_id=case_id,
            idempotency_key=f"case:{case_id}",
        )
        first_resp = await self._post_json(
            app=app,
            path="/internal/judge/cases",
            payload=req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(first_resp.status_code, 200)
        first_payload = first_resp.json()
        self.assertTrue(first_payload["accepted"])
        self.assertEqual(first_payload["status"], "case_built")
        self.assertEqual(first_payload["caseId"], case_id)
        self.assertEqual(first_payload["workflow"]["status"], "case_built")

        workflow_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=case_id)
        self.assertIsNotNone(workflow_job)
        assert workflow_job is not None
        self.assertEqual(workflow_job.status, "case_built")
        workflow_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=case_id)
        self.assertEqual(workflow_events[0].event_type, "job_registered")
        self.assertGreaterEqual(len(workflow_events), 3)
        self.assertTrue(all(row.event_type == "status_changed" for row in workflow_events[1:]))
        self.assertEqual(workflow_events[-1].payload.get("toStatus"), "case_built")

        replay_resp = await self._post_json(
            app=app,
            path="/internal/judge/cases",
            payload=req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(replay_resp.status_code, 200)
        self.assertTrue(replay_resp.json()["idempotentReplay"])

    async def test_case_create_should_reject_existing_case_with_new_idempotency_key(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)

        case_id = _unique_case_id(22)
        first_req = _build_case_create_request(
            case_id=case_id,
            idempotency_key=f"case:{case_id}:first",
        )
        first_resp = await self._post_json(
            app=app,
            path="/internal/judge/cases",
            payload=first_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(first_resp.status_code, 200)

        second_req = _build_case_create_request(
            case_id=case_id,
            idempotency_key=f"case:{case_id}:second",
        )
        second_resp = await self._post_json(
            app=app,
            path="/internal/judge/cases",
            payload=second_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(second_resp.status_code, 409)
        self.assertIn("case_already_exists", second_resp.text)

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

    async def test_phase_dispatch_should_reject_unknown_policy_version(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        req = _build_phase_request(
            case_id=8101,
            idempotency_key="phase:8101",
            judge_policy_version="v9-not-exist",
        )

        bad_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_resp.status_code, 422)
        self.assertIn("unknown_judge_policy_version", bad_resp.text)

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

    async def test_policy_registry_dependency_blocked_alert_should_emit_and_resolve_outbox(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        version = f"policy-dep-alert-{_unique_case_id(9215)}"

        blocked_publish = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-missing",
                    "toolRegistryVersion": "toolset-v3-default",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(blocked_publish.status_code, 422)
        blocked_detail = blocked_publish.json()["detail"]
        self.assertEqual(blocked_detail["code"], "registry_policy_dependency_invalid")
        blocked_alert = blocked_detail["alert"]
        self.assertEqual(blocked_alert["type"], "registry_dependency_health_blocked")
        self.assertEqual(blocked_alert["status"], "raised")

        outbox_after_blocked = await self._get(
            app=app,
            path="/internal/judge/alerts/outbox",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(outbox_after_blocked.status_code, 200)
        blocked_event = next(
            (
                item
                for item in outbox_after_blocked.json()["items"]
                if item.get("payload", {}).get("alertType")
                == "registry_dependency_health_blocked"
                and item.get("payload", {}).get("status") == "raised"
                and item.get("payload", {}).get("details", {}).get("version") == version
            ),
            None,
        )
        self.assertIsNotNone(blocked_event)
        open_trend_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/registries/policy/dependencies/health"
                "?include_all_versions=true&include_overview=false"
                "&include_trend=true&trend_status=open&trend_policy_version="
                f"{version}&trend_limit=20&trend_offset=0"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(open_trend_resp.status_code, 200)
        open_trend_payload = open_trend_resp.json()
        self.assertIsNone(open_trend_payload["dependencyOverview"])
        self.assertIsInstance(open_trend_payload["dependencyTrend"], dict)
        self.assertGreaterEqual(open_trend_payload["dependencyTrend"]["count"], 1)
        self.assertGreaterEqual(
            open_trend_payload["dependencyTrend"]["statusCounts"]["raised"],
            1,
        )
        self.assertTrue(
            all(
                row["policyVersion"] == version
                for row in open_trend_payload["dependencyTrend"]["items"]
            )
        )

        prompt_publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/prompt/publish",
            payload={
                "version": "promptset-dep-recover",
                "activate": False,
                "profile": {
                    "promptVersions": {
                        "summaryPromptVersion": "v3.a2a3.summary.v1",
                        "agent2PromptVersion": "v3.a6a7.bidirectional.v2",
                        "finalPipelineVersion": "v3-final-a9a10-rollup-v2",
                        "claimGraphVersion": "v1-claim-graph-bootstrap",
                    },
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(prompt_publish_resp.status_code, 200)

        recovered_publish = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": version,
                "activate": False,
                "reason": "dependency_recovered",
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-dep-recover",
                    "toolRegistryVersion": "toolset-v3-default",
                    "promptVersions": {
                        "summaryPromptVersion": "v3.a2a3.summary.v1",
                        "agent2PromptVersion": "v3.a6a7.bidirectional.v2",
                        "finalPipelineVersion": "v3-final-a9a10-rollup-v2",
                        "claimGraphVersion": "v1-claim-graph-bootstrap",
                    },
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(recovered_publish.status_code, 200)
        recovered_payload = recovered_publish.json()
        self.assertIsNotNone(recovered_payload["dependencyHealth"])
        self.assertTrue(recovered_payload["dependencyHealth"]["ok"])
        self.assertGreaterEqual(len(recovered_payload["resolvedDependencyAlerts"]), 1)

        outbox_after_recovered = await self._get(
            app=app,
            path="/internal/judge/alerts/outbox",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(outbox_after_recovered.status_code, 200)
        resolved_event = next(
            (
                item
                for item in outbox_after_recovered.json()["items"]
                if item.get("payload", {}).get("alertType")
                == "registry_dependency_health_blocked"
                and item.get("payload", {}).get("status") == "resolved"
                and item.get("payload", {}).get("details", {}).get("version") == version
            ),
            None,
        )
        self.assertIsNotNone(resolved_event)

        health_overview_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/registries/policy/dependencies/health"
                f"?policy_version={version}&include_all_versions=true&include_overview=true"
                "&overview_window_minutes=1440&limit=20"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(health_overview_resp.status_code, 200)
        health_overview_payload = health_overview_resp.json()
        overview = health_overview_payload["dependencyOverview"]
        self.assertIsInstance(overview, dict)
        self.assertGreaterEqual(overview["counts"]["totalAlerts"], 1)
        self.assertGreaterEqual(overview["counts"]["resolvedCount"], 1)
        self.assertGreaterEqual(overview["counts"]["recentChanges"], 1)
        target_row = next(
            (
                row
                for row in overview["byPolicyVersion"]
                if row["policyVersion"] == version
            ),
            None,
        )
        self.assertIsNotNone(target_row)
        assert target_row is not None
        self.assertGreaterEqual(target_row["totalAlerts"], 1)
        self.assertGreaterEqual(target_row["resolvedCount"], 1)
        self.assertEqual(target_row["openBlockedCount"], 0)
        self.assertEqual(target_row["lastStatus"], "resolved")
        resolved_trend = health_overview_payload["dependencyTrend"]
        self.assertIsInstance(resolved_trend, dict)
        self.assertGreaterEqual(resolved_trend["count"], 1)

        resolved_trend_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/registries/policy/dependencies/health"
                f"?policy_version={version}&include_all_versions=true&include_overview=false"
                "&include_trend=true&trend_status=resolved"
                f"&trend_policy_version={version}&trend_limit=1&trend_offset=0"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(resolved_trend_resp.status_code, 200)
        resolved_trend_payload = resolved_trend_resp.json()["dependencyTrend"]
        self.assertEqual(resolved_trend_payload["returned"], 1)
        self.assertGreaterEqual(resolved_trend_payload["count"], 1)
        self.assertEqual(resolved_trend_payload["filters"]["status"], "resolved")
        self.assertEqual(resolved_trend_payload["filters"]["policyVersion"], version)
        self.assertEqual(resolved_trend_payload["items"][0]["status"], "resolved")

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

    async def test_registry_alert_ops_view_should_join_outbox_and_support_filters(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9221)
        blocked_actor = f"ops-blocked-{suffix}"
        override_actor = f"ops-override-{suffix}"

        fairness_blocked_version = f"policy-ops-blocked-{suffix}"
        fairness_blocked_publish = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": fairness_blocked_version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-v3-default",
                    "toolRegistryVersion": "toolset-v3-default",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(fairness_blocked_publish.status_code, 200)
        fairness_blocked_activate = await self._post(
            app=app,
            path=(
                f"/internal/judge/registries/policy/{fairness_blocked_version}/activate"
                f"?actor={blocked_actor}"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(fairness_blocked_activate.status_code, 409)
        fairness_blocked_alert_id = fairness_blocked_activate.json()["detail"]["alert"]["alertId"]
        blocked_gate_code = fairness_blocked_activate.json()["detail"]["alert"]["details"]["gate"]["code"]

        fairness_override_version = f"policy-ops-override-{suffix}"
        fairness_override_publish = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": fairness_override_version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-v3-default",
                    "toolRegistryVersion": "toolset-v3-default",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(fairness_override_publish.status_code, 200)
        fairness_override_activate = await self._post(
            app=app,
            path=(
                f"/internal/judge/registries/policy/{fairness_override_version}/activate"
                f"?override_fairness_gate=true&actor={override_actor}"
                f"&reason=ops_view_override_{suffix}"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(fairness_override_activate.status_code, 200)
        self.assertEqual(
            fairness_override_activate.json()["alert"]["type"],
            "registry_fairness_gate_override",
        )
        override_gate_code = fairness_override_activate.json()["alert"]["details"]["gate"]["code"]

        dep_version = f"policy-ops-dep-{suffix}"
        dep_blocked = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": dep_version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": f"promptset-missing-{suffix}",
                    "toolRegistryVersion": "toolset-v3-default",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(dep_blocked.status_code, 422)
        self.assertEqual(
            dep_blocked.json()["detail"]["alert"]["type"],
            "registry_dependency_health_blocked",
        )

        dep_promptset_version = f"promptset-ops-{suffix}"
        dep_promptset_publish = await self._post_json(
            app=app,
            path="/internal/judge/registries/prompt/publish",
            payload={
                "version": dep_promptset_version,
                "activate": False,
                "profile": {
                    "promptVersions": {
                        "summaryPromptVersion": "v3.a2a3.summary.v1",
                        "agent2PromptVersion": "v3.a6a7.bidirectional.v2",
                        "finalPipelineVersion": "v3-final-a9a10-rollup-v2",
                        "claimGraphVersion": "v1-claim-graph-bootstrap",
                    },
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(dep_promptset_publish.status_code, 200)
        dep_recovered = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": dep_version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": dep_promptset_version,
                    "toolRegistryVersion": "toolset-v3-default",
                    "promptVersions": {
                        "summaryPromptVersion": "v3.a2a3.summary.v1",
                        "agent2PromptVersion": "v3.a6a7.bidirectional.v2",
                        "finalPipelineVersion": "v3-final-a9a10-rollup-v2",
                        "claimGraphVersion": "v1-claim-graph-bootstrap",
                    },
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(dep_recovered.status_code, 200)

        outbox_resp = await self._get(
            app=app,
            path="/internal/judge/alerts/outbox",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(outbox_resp.status_code, 200)
        blocked_event = next(
            (
                row
                for row in outbox_resp.json()["items"]
                if row["alertId"] == fairness_blocked_alert_id
            ),
            None,
        )
        self.assertIsNotNone(blocked_event)
        assert blocked_event is not None
        mark_failed_resp = await self._post(
            app=app,
            path=(
                "/internal/judge/alerts/outbox/"
                f"{blocked_event['eventId']}/delivery?delivery_status=failed&error_message=ops_view_probe"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(mark_failed_resp.status_code, 200)
        self.assertEqual(mark_failed_resp.json()["item"]["deliveryStatus"], "failed")

        ops_view_resp = await self._get(
            app=app,
            path="/internal/judge/alerts/ops-view?limit=200",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(ops_view_resp.status_code, 200)
        ops_payload = ops_view_resp.json()
        self.assertGreaterEqual(ops_payload["count"], 3)
        self.assertGreaterEqual(ops_payload["aggregations"]["byType"]["registry_fairness_gate_blocked"], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["byType"]["registry_fairness_gate_override"], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["byType"]["registry_dependency_health_blocked"], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["byGateCode"][blocked_gate_code], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["byGateCode"][override_gate_code], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["byGateActor"][blocked_actor], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["byGateActor"][override_actor], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["byOverrideApplied"]["true"], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["byOverrideApplied"]["false"], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["overrideAppliedCount"], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["blockedWithoutOverrideCount"], 1)
        self.assertEqual(ops_payload["filters"]["fieldsMode"], "full")
        self.assertTrue(bool(ops_payload["filters"]["includeTrend"]))
        self.assertIsInstance(ops_payload["trend"], dict)
        self.assertGreaterEqual(ops_payload["trend"]["count"], 1)
        blocked_item = next(
            (
                row
                for row in ops_payload["items"]
                if row["alertId"] == fairness_blocked_alert_id
            ),
            None,
        )
        self.assertIsNotNone(blocked_item)
        assert blocked_item is not None
        self.assertEqual(blocked_item["outbox"]["latestDeliveryStatus"], "failed")
        self.assertEqual(blocked_item["gateCode"], blocked_gate_code)
        self.assertEqual(blocked_item["gateActor"], blocked_actor)
        self.assertFalse(bool(blocked_item["overrideApplied"]))

        failed_filter_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/alerts/ops-view"
                "?alert_type=registry_fairness_gate_blocked&delivery_status=failed&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(failed_filter_resp.status_code, 200)
        failed_filter_payload = failed_filter_resp.json()
        self.assertGreaterEqual(failed_filter_payload["returned"], 1)
        self.assertTrue(
            all(
                row["type"] == "registry_fairness_gate_blocked"
                and row["outbox"]["latestDeliveryStatus"] == "failed"
                for row in failed_filter_payload["items"]
            )
        )

        open_filter_resp = await self._get(
            app=app,
            path="/internal/judge/alerts/ops-view?status=open&limit=50",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(open_filter_resp.status_code, 200)
        self.assertTrue(
            all(row["status"] in {"raised", "acked"} for row in open_filter_resp.json()["items"])
        )

        dep_resolved_filter_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/alerts/ops-view"
                f"?alert_type=registry_dependency_health_blocked&status=resolved&policy_version={dep_version}"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(dep_resolved_filter_resp.status_code, 200)
        dep_resolved_payload = dep_resolved_filter_resp.json()
        self.assertGreaterEqual(dep_resolved_payload["returned"], 1)
        self.assertTrue(
            all(
                row["type"] == "registry_dependency_health_blocked"
                and row["status"] == "resolved"
                and row["policyVersion"] == dep_version
                for row in dep_resolved_payload["items"]
            )
        )

        override_gate_filter_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/alerts/ops-view"
                f"?gate_code={override_gate_code}&gate_actor={override_actor}"
                "&override_applied=true&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(override_gate_filter_resp.status_code, 200)
        override_gate_filter_payload = override_gate_filter_resp.json()
        self.assertGreaterEqual(override_gate_filter_payload["returned"], 1)
        self.assertEqual(override_gate_filter_payload["filters"]["gateCode"], override_gate_code)
        self.assertEqual(override_gate_filter_payload["filters"]["gateActor"], override_actor)
        self.assertTrue(bool(override_gate_filter_payload["filters"]["overrideApplied"]))
        self.assertTrue(
            all(
                row["gateCode"] == override_gate_code
                and row["gateActor"] == override_actor
                and bool(row["overrideApplied"])
                for row in override_gate_filter_payload["items"]
            )
        )

        blocked_gate_filter_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/alerts/ops-view"
                f"?gate_code={blocked_gate_code}&gate_actor={blocked_actor}"
                "&override_applied=false&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(blocked_gate_filter_resp.status_code, 200)
        blocked_gate_filter_payload = blocked_gate_filter_resp.json()
        self.assertGreaterEqual(blocked_gate_filter_payload["returned"], 1)
        self.assertEqual(blocked_gate_filter_payload["filters"]["gateCode"], blocked_gate_code)
        self.assertEqual(blocked_gate_filter_payload["filters"]["gateActor"], blocked_actor)
        self.assertFalse(bool(blocked_gate_filter_payload["filters"]["overrideApplied"]))
        self.assertTrue(
            all(
                row["gateCode"] == blocked_gate_code
                and row["gateActor"] == blocked_actor
                and not bool(row["overrideApplied"])
                for row in blocked_gate_filter_payload["items"]
            )
        )

        bad_alert_type_resp = await self._get(
            app=app,
            path="/internal/judge/alerts/ops-view?alert_type=invalid-type",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_alert_type_resp.status_code, 422)
        self.assertIn("invalid_alert_type", bad_alert_type_resp.text)

        bad_status_resp = await self._get(
            app=app,
            path="/internal/judge/alerts/ops-view?status=invalid-status",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_status_resp.status_code, 422)
        self.assertIn("invalid_alert_status", bad_status_resp.text)

        bad_delivery_status_resp = await self._get(
            app=app,
            path="/internal/judge/alerts/ops-view?delivery_status=invalid-delivery",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_delivery_status_resp.status_code, 422)
        self.assertIn("invalid_delivery_status", bad_delivery_status_resp.text)

    async def test_registry_alert_ops_view_should_support_lite_mode_and_trend_window(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9222)

        blocked_version = f"policy-ops-lite-blocked-{suffix}"
        blocked_publish = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": blocked_version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-v3-default",
                    "toolRegistryVersion": "toolset-v3-default",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(blocked_publish.status_code, 200)
        blocked_activate = await self._post(
            app=app,
            path=f"/internal/judge/registries/policy/{blocked_version}/activate",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(blocked_activate.status_code, 409)

        override_version = f"policy-ops-lite-override-{suffix}"
        override_publish = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": override_version,
                "activate": False,
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
                f"?override_fairness_gate=true&reason=ops_lite_override_{suffix}"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(override_activate.status_code, 200)

        lite_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/alerts/ops-view"
                "?fields_mode=lite&trend_window_minutes=1440&trend_bucket_minutes=120&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(lite_resp.status_code, 200)
        lite_payload = lite_resp.json()
        self.assertEqual(lite_payload["filters"]["fieldsMode"], "lite")
        self.assertEqual(lite_payload["filters"]["trendWindowMinutes"], 1440)
        self.assertEqual(lite_payload["filters"]["trendBucketMinutes"], 120)
        self.assertIsInstance(lite_payload["trend"], dict)
        self.assertGreaterEqual(lite_payload["trend"]["count"], 2)
        self.assertGreaterEqual(lite_payload["trend"]["typeCounts"]["registry_fairness_gate_blocked"], 1)
        self.assertGreaterEqual(lite_payload["trend"]["typeCounts"]["registry_fairness_gate_override"], 1)
        self.assertGreaterEqual(len(lite_payload["trend"]["timeline"]), 1)
        self.assertGreaterEqual(lite_payload["returned"], 1)
        lite_item = lite_payload["items"][0]
        self.assertNotIn("message", lite_item)
        self.assertIn("outbox", lite_item)
        self.assertIn("latestDeliveryStatus", lite_item["outbox"])
        self.assertIn("totalEvents", lite_item["outbox"])

        no_trend_resp = await self._get(
            app=app,
            path="/internal/judge/alerts/ops-view?include_trend=false&fields_mode=lite&limit=20",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(no_trend_resp.status_code, 200)
        no_trend_payload = no_trend_resp.json()
        self.assertFalse(bool(no_trend_payload["filters"]["includeTrend"]))
        self.assertIsNone(no_trend_payload["trend"])

        bad_fields_mode_resp = await self._get(
            app=app,
            path="/internal/judge/alerts/ops-view?fields_mode=compact",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_fields_mode_resp.status_code, 422)
        self.assertIn("invalid_fields_mode", bad_fields_mode_resp.text)

    async def test_final_dispatch_should_reject_policy_rubric_mismatch(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        req = _build_final_request(
            case_id=8102,
            idempotency_key="final:8102",
            rubric_version="v2",
            judge_policy_version="v3-default",
        )

        bad_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_resp.status_code, 422)
        self.assertIn("judge_policy_rubric_mismatch", bad_resp.text)

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

    async def test_phase_dispatch_should_callback_and_support_idempotent_replay(self) -> None:
        phase_callback_calls: list[tuple[int, dict]] = []

        async def fake_phase_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            phase_callback_calls.append((case_id, payload))

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=fake_phase_callback,
            callback_final_report_impl=fake_phase_callback,
            callback_phase_failed_impl=fake_phase_callback,
            callback_final_failed_impl=fake_phase_callback,
        )
        app = create_app(runtime)

        req = _build_phase_request(case_id=1001, idempotency_key="phase:1001")
        first_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(first_resp.status_code, 200)
        first = first_resp.json()
        self.assertTrue(first["accepted"])
        self.assertEqual(first["dispatchType"], "phase")
        self.assertEqual(len(phase_callback_calls), 1)
        self.assertIn("trustAttestation", phase_callback_calls[0][1])
        self.assertEqual(
            phase_callback_calls[0][1]["trustAttestation"]["dispatchType"],
            "phase",
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["status"],
            "ok",
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["dispatchType"],
            "phase",
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["workflowVersion"],
            "courtroom_8agent_chain_v1",
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["roleContractVersion"],
            "courtroom_role_contract_v1",
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["workflowContractVersion"],
            "courtroom_workflow_contract_v1",
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["artifactContractVersion"],
            "courtroom_artifact_contract_v1",
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["stageContractVersion"],
            "courtroom_stage_contract_v1",
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["mode"],
            "official_verdict_plane",
        )
        self.assertTrue(
            bool(
                phase_callback_calls[0][1]["judgeTrace"]["agentRuntime"][
                    "officialVerdictAuthority"
                ]
            )
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["policyRegistry"]["version"],
            "v3-default",
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["promptRegistry"]["version"],
            "promptset-v3-default",
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["toolRegistry"]["version"],
            "toolset-v3-default",
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["registryVersions"]["promptVersion"],
            "promptset-v3-default",
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["registryVersions"]["toolsetVersion"],
            "toolset-v3-default",
        )
        self.assertEqual(
            len(phase_callback_calls[0][1]["judgeTrace"]["courtroomRoles"]),
            8,
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["courtroomRoles"][0]["contractVersion"],
            "courtroom_role_contract_v1",
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["courtroomRoles"][0]["activationScope"],
            "phase_and_final",
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["courtroomRoles"][-1]["activationScope"],
            "final_only",
        )
        self.assertEqual(
            len(phase_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["activeRoles"]),
            5,
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["workflowEdgeCount"],
            7,
        )
        self.assertEqual(
            phase_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["artifactCount"],
            8,
        )
        self.assertEqual(
            len(phase_callback_calls[0][1]["judgeTrace"]["courtroomWorkflowEdges"]),
            7,
        )
        self.assertEqual(
            len(phase_callback_calls[0][1]["judgeTrace"]["courtroomArtifacts"]),
            8,
        )
        deferred_artifacts = [
            row
            for row in phase_callback_calls[0][1]["judgeTrace"]["courtroomArtifacts"]
            if row.get("availability") == "deferred"
        ]
        self.assertGreaterEqual(len(deferred_artifacts), 1)
        phase_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=1001)
        self.assertIsNotNone(phase_job)
        assert phase_job is not None
        self.assertEqual(phase_job.status, "callback_reported")
        phase_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=1001)
        self.assertGreaterEqual(len(phase_events), 8)
        self.assertTrue(all(row.event_type == "status_changed" for row in phase_events[-8:]))
        self.assertEqual(phase_events[-1].payload.get("toStatus"), "callback_reported")
        self.assertEqual(phase_events[-1].payload.get("judgeCoreStage"), "reported")
        self.assertEqual(phase_events[-1].payload.get("judgeCoreVersion"), "v1")

        replay_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(replay_resp.status_code, 200)
        replay = replay_resp.json()
        self.assertTrue(replay["idempotentReplay"])
        self.assertEqual(len(phase_callback_calls), 1)

    async def test_final_dispatch_should_use_phase_receipts_and_callback(self) -> None:
        phase_callback_calls: list[tuple[int, dict]] = []
        final_callback_calls: list[tuple[int, dict]] = []

        async def fake_phase_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            phase_callback_calls.append((case_id, payload))

        async def fake_final_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            final_callback_calls.append((case_id, payload))

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=fake_phase_callback,
            callback_final_report_impl=fake_final_callback,
            callback_phase_failed_impl=fake_phase_callback,
            callback_final_failed_impl=fake_final_callback,
        )
        app = create_app(runtime)

        phase_req = _build_phase_request(case_id=2001, idempotency_key="phase:2001")
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)
        self.assertEqual(len(phase_callback_calls), 1)

        final_req = _build_final_request(case_id=2002, idempotency_key="final:2002")
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)
        result = final_resp.json()
        self.assertTrue(result["accepted"])
        self.assertEqual(result["dispatchType"], "final")
        self.assertEqual(len(final_callback_calls), 1)
        self.assertEqual(final_callback_calls[0][0], 2002)
        self.assertIn("winner", final_callback_calls[0][1])
        self.assertIn("trustAttestation", final_callback_calls[0][1])
        self.assertEqual(
            final_callback_calls[0][1]["trustAttestation"]["dispatchType"],
            "final",
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["policyRegistry"]["version"],
            "v3-default",
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["status"],
            "ok",
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["dispatchType"],
            "final",
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["workflowVersion"],
            "courtroom_8agent_chain_v1",
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["roleContractVersion"],
            "courtroom_role_contract_v1",
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["workflowContractVersion"],
            "courtroom_workflow_contract_v1",
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["artifactContractVersion"],
            "courtroom_artifact_contract_v1",
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["stageContractVersion"],
            "courtroom_stage_contract_v1",
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["mode"],
            "official_verdict_plane",
        )
        self.assertTrue(
            bool(
                final_callback_calls[0][1]["judgeTrace"]["agentRuntime"][
                    "officialVerdictAuthority"
                ]
            )
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["promptRegistry"]["version"],
            "promptset-v3-default",
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["toolRegistry"]["version"],
            "toolset-v3-default",
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["registryVersions"]["promptVersion"],
            "promptset-v3-default",
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["registryVersions"]["toolsetVersion"],
            "toolset-v3-default",
        )
        self.assertEqual(
            final_callback_calls[0][1]["verdictLedger"]["panelDecisions"]["runtimeProfiles"][
                "judgeA"
            ]["profileId"],
            "panel-judgeA-weighted-v1",
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["panelRuntimeProfiles"]["judgeB"][
                "modelStrategy"
            ],
            "deterministic_path_alignment",
        )
        self.assertEqual(
            len(final_callback_calls[0][1]["judgeTrace"]["courtroomRoles"]),
            8,
        )
        self.assertTrue(
            all(
                str(row.get("contractVersion") or "") == "courtroom_role_contract_v1"
                for row in final_callback_calls[0][1]["judgeTrace"]["courtroomRoles"]
            )
        )
        self.assertEqual(
            len(final_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["activeRoles"]),
            8,
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["workflowEdgeCount"],
            7,
        )
        self.assertEqual(
            final_callback_calls[0][1]["judgeTrace"]["agentRuntime"]["artifactCount"],
            8,
        )
        self.assertEqual(
            len(final_callback_calls[0][1]["judgeTrace"]["courtroomWorkflowEdges"]),
            7,
        )
        self.assertEqual(
            len(final_callback_calls[0][1]["judgeTrace"]["courtroomArtifacts"]),
            8,
        )
        self.assertTrue(
            all(
                bool(row.get("available"))
                for row in final_callback_calls[0][1]["judgeTrace"]["courtroomArtifacts"]
            )
        )
        phase_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=2001)
        final_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=2002)
        self.assertIsNotNone(phase_job)
        self.assertIsNotNone(final_job)
        assert phase_job is not None and final_job is not None
        self.assertEqual(phase_job.status, "callback_reported")
        self.assertEqual(final_job.status, "callback_reported")

    async def test_final_dispatch_should_apply_policy_panel_runtime_profiles(self) -> None:
        final_callback_calls: list[tuple[int, dict]] = []

        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            final_callback_calls.append((case_id, payload))

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)
        prompt_publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/prompt/publish",
            payload={
                "version": "promptset-v9-custom",
                "activate": False,
                "profile": {
                    "promptVersions": {
                        "summaryPromptVersion": "summary-v9",
                        "agent2PromptVersion": "agent2-v9",
                        "finalPipelineVersion": "final-v9",
                        "claimGraphVersion": "v1-claim-graph-bootstrap",
                    },
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(prompt_publish_resp.status_code, 200)
        publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": "v3-custom",
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-v9-custom",
                    "toolRegistryVersion": "toolset-v3-default",
                    "promptVersions": {
                        "summaryPromptVersion": "summary-v9",
                        "agent2PromptVersion": "agent2-v9",
                        "finalPipelineVersion": "final-v9",
                        "claimGraphVersion": "v1-claim-graph-bootstrap",
                    },
                    "metadata": {
                        "panelRuntimeContext": {
                            "defaultDomainSlot": "tft_ranked",
                            "runtimeStage": "adaptive_bootstrap",
                            "adaptiveEnabled": True,
                            "candidateModels": ["gpt-5.4", "gpt-5.4-mini"],
                            "strategyMetadata": {"calibrationVersion": "calib-local-v2"},
                        },
                        "panelRuntimeProfiles": {
                            "judgeA": {
                                "profileId": "panel-a-custom",
                                "modelStrategy": "llm_vote",
                                "strategySlot": "adaptive_weighted_vote",
                                "promptVersion": "panel-prompt-v9",
                                "candidateModels": ["gpt-5.4"],
                                "profileSource": "policy_metadata",
                            }
                        }
                    },
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_resp.status_code, 200)
        final_req = _build_final_request(
            case_id=2012,
            idempotency_key="final:2012",
            judge_policy_version="v3-custom",
        )

        resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(final_callback_calls), 1)
        final_payload = final_callback_calls[0][1]
        judge_a_profile = final_payload["verdictLedger"]["panelDecisions"]["runtimeProfiles"][
            "judgeA"
        ]
        self.assertEqual(judge_a_profile["profileId"], "panel-a-custom")
        self.assertEqual(judge_a_profile["modelStrategy"], "llm_vote")
        self.assertEqual(judge_a_profile["promptVersion"], "panel-prompt-v9")
        self.assertEqual(judge_a_profile["strategySlot"], "adaptive_weighted_vote")
        self.assertEqual(judge_a_profile["domainSlot"], "tft_ranked")
        self.assertEqual(judge_a_profile["runtimeStage"], "adaptive_bootstrap")
        self.assertTrue(judge_a_profile["adaptiveEnabled"])
        self.assertEqual(judge_a_profile["candidateModels"], ["gpt-5.4"])
        self.assertEqual(
            judge_a_profile["strategyMetadata"]["calibrationVersion"],
            "calib-local-v2",
        )
        self.assertEqual(judge_a_profile["profileSource"], "policy_metadata")
        self.assertEqual(
            final_payload["judgeTrace"]["panelRuntimeProfiles"]["judgeA"]["profileId"],
            "panel-a-custom",
        )
        self.assertEqual(
            final_payload["judgeTrace"]["panelRuntimeProfiles"]["judgeB"]["domainSlot"],
            "tft_ranked",
        )

    async def test_final_dispatch_should_mark_workflow_review_required_when_gate_triggers(
        self,
    ) -> None:
        final_callback_calls: list[tuple[int, dict]] = []

        async def noop_phase_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        async def final_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            final_callback_calls.append((case_id, payload))

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_phase_callback,
            callback_final_report_impl=final_callback,
            callback_phase_failed_impl=noop_phase_callback,
            callback_final_failed_impl=final_callback,
        )
        app = create_app(runtime)
        final_req = _build_final_request(case_id=7401, idempotency_key="final:7401")
        gated_payload = {
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
                "scoreCard": {"proScore": 61.0, "conScore": 60.2, "dimensionScores": {"logic": 60.0}},
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
                "internalReview": {"traceId": "trace-final-7401"},
            },
            "verdictEvidenceRefs": [],
            "phaseRollupSummary": [{"phaseNo": 1}],
            "retrievalSnapshotRollup": [],
            "winnerFirst": "pro",
            "winnerSecond": "pro",
            "rejudgeTriggered": True,
            "needsDrawVote": True,
            "reviewRequired": True,
            "fairnessSummary": {
                "phase": "phase2",
                "panelHighDisagreement": False,
                "panelDisagreementRatio": 0.0,
                "reviewRequired": True,
                "gateDecision": "blocked_to_draw",
                "reviewReasons": ["style_shift_instability"],
            },
            "judgeTrace": {"traceId": "trace-final-7401"},
            "auditAlerts": [{"type": "style_shift_instability"}],
            "errorCodes": ["style_shift_instability", "fairness_gate_review_required"],
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
        self.assertEqual(len(final_callback_calls), 1)
        workflow_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=7401)
        self.assertIsNotNone(workflow_job)
        assert workflow_job is not None
        self.assertEqual(workflow_job.status, "review_required")
        workflow_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=7401)
        self.assertEqual(workflow_events[-1].payload.get("toStatus"), "review_required")
        self.assertTrue(workflow_events[-1].payload.get("reviewRequired"))
        self.assertEqual(workflow_events[-1].payload.get("judgeCoreStage"), "review_required")

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
            "app.app_factory.validate_trust_challenge_queue_contract_v3",
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

    async def test_phase_dispatch_should_mark_callback_failed_receipt_when_callback_raises(
        self,
    ) -> None:
        async def failing_phase_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            raise RuntimeError("phase-callback-down")

        async def noop_failed_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(runtime_retry_max_attempts=1),
            callback_phase_report_impl=failing_phase_callback,
            callback_final_report_impl=failing_phase_callback,
            callback_phase_failed_impl=noop_failed_callback,
            callback_final_failed_impl=noop_failed_callback,
        )
        app = create_app(runtime)

        req = _build_phase_request(case_id=3001, idempotency_key="phase:3001")
        failed_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(failed_resp.status_code, 502)
        self.assertIn("phase_callback_failed", failed_resp.text)

        receipt_resp = await self._get(
            app=app,
            path="/internal/judge/v3/phase/cases/3001/receipt",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(receipt_resp.status_code, 200)
        receipt = receipt_resp.json()
        self.assertEqual(receipt["status"], "callback_failed")
        self.assertEqual(
            receipt["response"].get("errorCode"),
            "phase_callback_retry_exhausted",
        )
        self.assertEqual(
            receipt["response"].get("error", {}).get("code"),
            "phase_callback_retry_exhausted",
        )
        self.assertEqual(
            receipt["response"].get("error", {}).get("dispatchType"),
            "phase",
        )
        self.assertEqual(
            receipt["response"].get("error", {}).get("category"),
            "callback_delivery",
        )
        phase_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=3001)
        self.assertIsNotNone(phase_job)
        assert phase_job is not None
        self.assertEqual(phase_job.status, "blocked_failed")
        workflow_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=3001)
        self.assertEqual(
            workflow_events[-1].payload.get("errorCode"),
            "phase_callback_retry_exhausted",
        )
        self.assertEqual(
            workflow_events[-1].payload.get("error", {}).get("code"),
            "phase_callback_retry_exhausted",
        )

    async def test_final_dispatch_should_mark_callback_failed_receipt_when_callback_raises(
        self,
    ) -> None:
        case_id = _unique_case_id(8301)

        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        async def failing_final_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            raise RuntimeError("final-callback-down")

        runtime = create_runtime(
            settings=_build_settings(runtime_retry_max_attempts=1),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=failing_final_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)

        phase_req = _build_phase_request(
            case_id=case_id,
            idempotency_key=f"phase:{case_id}",
        )
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(
            case_id=case_id,
            idempotency_key=f"final:{case_id}",
        )
        failed_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(failed_resp.status_code, 502)
        self.assertIn("final_callback_failed", failed_resp.text)

        receipt_resp = await self._get(
            app=app,
            path=f"/internal/judge/v3/final/cases/{case_id}/receipt",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(receipt_resp.status_code, 200)
        receipt = receipt_resp.json()
        self.assertEqual(receipt["status"], "callback_failed")
        self.assertEqual(
            receipt["response"].get("errorCode"),
            "final_callback_retry_exhausted",
        )
        self.assertEqual(
            receipt["response"].get("error", {}).get("code"),
            "final_callback_retry_exhausted",
        )
        self.assertEqual(
            receipt["response"].get("error", {}).get("dispatchType"),
            "final",
        )
        self.assertEqual(
            receipt["response"].get("error", {}).get("category"),
            "callback_delivery",
        )
        workflow_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=case_id)
        self.assertEqual(
            workflow_events[-1].payload.get("errorCode"),
            "final_callback_retry_exhausted",
        )
        self.assertEqual(
            workflow_events[-1].payload.get("error", {}).get("code"),
            "final_callback_retry_exhausted",
        )

    async def test_final_dispatch_should_mark_failed_when_failed_callback_fails(self) -> None:
        case_id = _unique_case_id(8302)

        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        async def failing_final_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            raise RuntimeError("final-callback-down")

        async def failing_failed_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            raise RuntimeError("final-failed-callback-down")

        runtime = create_runtime(
            settings=_build_settings(runtime_retry_max_attempts=1),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=failing_final_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=failing_failed_callback,
        )
        app = create_app(runtime)

        phase_req = _build_phase_request(
            case_id=case_id,
            idempotency_key=f"phase:{case_id}",
        )
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(
            case_id=case_id,
            idempotency_key=f"final:{case_id}",
        )
        failed_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(failed_resp.status_code, 502)
        self.assertIn("final_failed_callback_failed", failed_resp.text)

        receipt_resp = await self._get(
            app=app,
            path=f"/internal/judge/v3/final/cases/{case_id}/receipt",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(receipt_resp.status_code, 200)
        receipt = receipt_resp.json()
        self.assertEqual(receipt["status"], "callback_failed")
        self.assertEqual(
            receipt["response"].get("errorCode"),
            "final_failed_callback_failed",
        )
        self.assertEqual(
            receipt["response"].get("error", {}).get("code"),
            "final_failed_callback_failed",
        )
        self.assertEqual(
            receipt["response"].get("error", {}).get("dispatchType"),
            "final",
        )
        workflow_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=case_id)
        self.assertEqual(
            workflow_events[-1].payload.get("errorCode"),
            "final_failed_callback_failed",
        )
        self.assertEqual(
            workflow_events[-1].payload.get("callbackStatus"),
            "failed_callback_failed",
        )
        self.assertEqual(
            workflow_events[-1].payload.get("error", {}).get("code"),
            "final_failed_callback_failed",
        )

    async def test_replay_post_should_prefer_final_receipt_when_auto(self) -> None:
        phase_calls: list[tuple[int, dict]] = []
        final_calls: list[tuple[int, dict]] = []

        async def phase_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            phase_calls.append((case_id, payload))

        async def final_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            final_calls.append((case_id, payload))

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=phase_callback,
            callback_final_report_impl=final_callback,
            callback_phase_failed_impl=phase_callback,
            callback_final_failed_impl=final_callback,
        )
        app = create_app(runtime)

        phase_req = _build_phase_request(case_id=5001, idempotency_key="phase:5001")
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(case_id=5001, idempotency_key="final:5001")
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)
        callback_total_before_replay = len(phase_calls) + len(final_calls)

        replay_resp = await self._post(
            app=app,
            path="/internal/judge/cases/5001/replay?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(replay_resp.status_code, 200)
        replay_payload = replay_resp.json()
        self.assertEqual(replay_payload["dispatchType"], "final")
        self.assertIn("reportPayload", replay_payload)
        self.assertIn("verdictContract", replay_payload)
        self.assertIn("debateSummary", replay_payload["reportPayload"])
        self.assertIn("trustAttestation", replay_payload["reportPayload"])
        self.assertEqual(
            replay_payload["reportPayload"]["judgeTrace"]["panelRuntimeProfiles"]["judgeC"][
                "profileId"
            ],
            "panel-judgeC-dimension-composite-v1",
        )
        self.assertEqual(replay_payload["judgeCoreStage"], "replay_computed")
        self.assertEqual(replay_payload["judgeCoreVersion"], "v1")
        self.assertEqual(callback_total_before_replay, len(phase_calls) + len(final_calls))
        replay_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=5001)
        self.assertEqual(replay_events[-1].event_type, "replay_marked")
        self.assertEqual(replay_events[-1].payload.get("judgeCoreStage"), "replay_computed")
        replay_claim_ledger = await runtime.workflow_runtime.facts.get_claim_ledger_record(
            case_id=5001,
            dispatch_type="final",
        )
        self.assertIsNotNone(replay_claim_ledger)
        assert replay_claim_ledger is not None
        self.assertEqual(replay_claim_ledger.case_dossier.get("dispatchType"), "final")
        self.assertEqual(
            replay_claim_ledger.case_dossier.get("phase", {}).get("startNo"),
            final_req.phase_start_no,
        )
        self.assertEqual(
            replay_claim_ledger.case_dossier.get("phase", {}).get("endNo"),
            final_req.phase_end_no,
        )

    async def test_trace_and_replay_report_should_keep_judge_workflow_summary_contract(
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

        case_id = _unique_case_id(5401)
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

        trace_resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/trace",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(trace_resp.status_code, 200)
        trace_payload = trace_resp.json()
        trace_summary = trace_payload["reportSummary"]
        self.assertEqual(trace_summary["dispatchType"], "final")
        self.assertIsInstance(trace_summary["judgeWorkflow"], dict)
        self.assertIsInstance(trace_summary["roleNodes"], list)
        self.assertEqual(len(trace_summary["roleNodes"]), 8)
        self.assertEqual(trace_summary["roleNodes"][0]["role"], "clerk")
        self.assertEqual(trace_summary["roleNodes"][-1]["role"], "opinion_writer")

        replay_report_resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/replay/report",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(replay_report_resp.status_code, 200)
        replay_report_payload = replay_report_resp.json()
        replay_summary = replay_report_payload["reportSummary"]
        self.assertEqual(replay_summary["dispatchType"], "final")
        self.assertIsInstance(replay_summary["judgeWorkflow"], dict)
        self.assertIsInstance(replay_summary["roleNodes"], list)
        self.assertEqual(len(replay_summary["roleNodes"]), 8)
        self.assertEqual(replay_summary["roleNodes"][0]["role"], "clerk")
        self.assertEqual(replay_summary["roleNodes"][-1]["role"], "opinion_writer")

    async def test_attestation_verify_should_use_auto_dispatch_and_return_verified(self) -> None:
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

        phase_req = _build_phase_request(case_id=8103, idempotency_key="phase:8103")
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(case_id=8103, idempotency_key="final:8103")
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        verify_resp = await self._post(
            app=app,
            path="/internal/judge/cases/8103/attestation/verify?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(verify_resp.status_code, 200)
        verify_payload = verify_resp.json()
        self.assertEqual(verify_payload["dispatchType"], "final")
        self.assertEqual(verify_payload["traceId"], "trace-final-8103")
        self.assertTrue(verify_payload["verified"])
        self.assertEqual(verify_payload["reason"], "ok")
        self.assertEqual(verify_payload["mismatchComponents"], [])

    async def test_attestation_verify_should_detect_tampered_report_payload(self) -> None:
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

        phase_req = _build_phase_request(case_id=8104, idempotency_key="phase:8104")
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(case_id=8104, idempotency_key="final:8104")
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        fact_receipt = await runtime.workflow_runtime.facts.get_dispatch_receipt(
            dispatch_type="final",
            job_id=8104,
        )
        self.assertIsNotNone(fact_receipt)
        assert fact_receipt is not None
        response_payload = dict(fact_receipt.response or {})
        report_payload = (
            dict(response_payload.get("reportPayload"))
            if isinstance(response_payload.get("reportPayload"), dict)
            else {}
        )
        report_payload["winner"] = "draw" if report_payload.get("winner") != "draw" else "pro"
        response_payload["reportPayload"] = report_payload
        await runtime.workflow_runtime.facts.upsert_dispatch_receipt(
            receipt=replace(fact_receipt, response=response_payload),
        )

        verify_resp = await self._post(
            app=app,
            path="/internal/judge/cases/8104/attestation/verify?dispatch_type=final",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(verify_resp.status_code, 200)
        verify_payload = verify_resp.json()
        self.assertFalse(verify_payload["verified"])
        self.assertEqual(verify_payload["reason"], "trust_attestation_mismatch")
        self.assertIn("verdictHash", verify_payload["mismatchComponents"])

    async def test_trust_routes_should_return_phasea_registry_bundle(self) -> None:
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

        case_id = _unique_case_id(8105)
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

        commitment_resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/trust/commitment?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(commitment_resp.status_code, 200)
        commitment_payload = commitment_resp.json()
        commitment_item = commitment_payload["item"]
        self.assertEqual(commitment_payload["dispatchType"], "final")
        self.assertEqual(commitment_payload["traceId"], f"trace-final-{case_id}")
        self.assertEqual(commitment_item["version"], "trust-phaseA-case-commitment-v1")
        self.assertIn("commitmentHash", commitment_item)

        attestation_resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/trust/verdict-attestation?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(attestation_resp.status_code, 200)
        attestation_item = attestation_resp.json()["item"]
        self.assertEqual(attestation_item["version"], "trust-phaseA-verdict-attestation-v1")
        self.assertTrue(attestation_item["verified"])
        self.assertEqual(attestation_item["reason"], "ok")
        self.assertIn("registryHash", attestation_item)

        challenge_resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/trust/challenges?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(challenge_resp.status_code, 200)
        challenge_item = challenge_resp.json()["item"]
        self.assertEqual(challenge_item["version"], "trust-phaseB-challenge-review-v1")
        self.assertEqual(challenge_item["reviewState"], "approved")
        self.assertIn("registryHash", challenge_item)

        kernel_resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/trust/kernel-version?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(kernel_resp.status_code, 200)
        kernel_item = kernel_resp.json()["item"]
        self.assertEqual(kernel_item["version"], "trust-phaseA-kernel-version-v1")
        self.assertIn("kernelVector", kernel_item)
        self.assertIn("kernelHash", kernel_item)
        self.assertIn("registryHash", kernel_item)

        anchor_resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/trust/audit-anchor?dispatch_type=auto&include_payload=true",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(anchor_resp.status_code, 200)
        anchor_item = anchor_resp.json()["item"]
        self.assertEqual(anchor_item["version"], "trust-phaseA-audit-anchor-v1")
        self.assertIn("anchorHash", anchor_item)
        self.assertIn("payload", anchor_item)
        self.assertEqual(
            anchor_item["componentHashes"]["caseCommitmentHash"],
            commitment_item["commitmentHash"],
        )
        self.assertEqual(
            anchor_item["componentHashes"]["verdictAttestationHash"],
            attestation_item["registryHash"],
        )
        self.assertEqual(
            anchor_item["componentHashes"]["challengeReviewHash"],
            challenge_item["registryHash"],
        )
        self.assertEqual(
            anchor_item["componentHashes"]["kernelVersionHash"],
            kernel_item["registryHash"],
        )

        public_verify_resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/trust/public-verify?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(public_verify_resp.status_code, 200)
        public_verify_payload = public_verify_resp.json()
        self.assertEqual(public_verify_payload["dispatchType"], "final")
        self.assertEqual(public_verify_payload["traceId"], f"trace-final-{case_id}")
        verify_payload = public_verify_payload["verifyPayload"]
        self.assertEqual(
            verify_payload["caseCommitment"]["commitmentHash"],
            commitment_item["commitmentHash"],
        )
        self.assertEqual(
            verify_payload["verdictAttestation"]["registryHash"],
            attestation_item["registryHash"],
        )
        self.assertEqual(
            verify_payload["challengeReview"]["registryHash"],
            challenge_item["registryHash"],
        )
        self.assertEqual(
            verify_payload["kernelVersion"]["registryHash"],
            kernel_item["registryHash"],
        )
        self.assertEqual(
            verify_payload["auditAnchor"]["anchorHash"],
            anchor_item["anchorHash"],
        )
        self.assertNotIn("attestation", verify_payload["verdictAttestation"])
        self.assertNotIn("challenges", verify_payload["challengeReview"])
        self.assertNotIn("timeline", verify_payload["challengeReview"])
        self.assertNotIn("reviewDecisions", verify_payload["challengeReview"])
        self.assertNotIn("openAlertIds", verify_payload["challengeReview"])
        self.assertNotIn("payload", verify_payload["auditAnchor"])

    async def test_trust_public_verify_route_should_return_500_when_contract_validation_fails(
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
        case_id = _unique_case_id(8106)
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=_build_phase_request(
                case_id=case_id,
                idempotency_key=f"phase:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)
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
            "app.app_factory.validate_trust_public_verify_contract_v3",
            side_effect=ValueError("trust_public_verify_missing_keys:verifyPayload"),
        ):
            resp = await self._get(
                app=app,
                path=f"/internal/judge/cases/{case_id}/trust/public-verify?dispatch_type=final",
                internal_key=runtime.settings.ai_internal_key,
            )

        self.assertEqual(resp.status_code, 500)
        detail = resp.json()["detail"]
        self.assertEqual(detail["code"], "trust_public_verify_contract_violation")
        self.assertIn("trust_public_verify_missing_keys:verifyPayload", detail["message"])

    async def test_trust_commitment_route_should_return_500_when_contract_validation_fails(
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
        case_id = _unique_case_id(8109)
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=_build_phase_request(
                case_id=case_id,
                idempotency_key=f"phase:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)
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
            "app.app_factory.validate_trust_commitment_contract_v3",
            side_effect=ValueError("trust_commitment_missing_keys:item"),
        ):
            resp = await self._get(
                app=app,
                path=f"/internal/judge/cases/{case_id}/trust/commitment?dispatch_type=final",
                internal_key=runtime.settings.ai_internal_key,
            )

        self.assertEqual(resp.status_code, 500)
        detail = resp.json()["detail"]
        self.assertEqual(detail["code"], "trust_commitment_contract_violation")
        self.assertIn("trust_commitment_missing_keys:item", detail["message"])

    async def test_trust_verdict_attestation_route_should_return_500_when_contract_validation_fails(
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
        case_id = _unique_case_id(8110)
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=_build_phase_request(
                case_id=case_id,
                idempotency_key=f"phase:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)
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
            "app.app_factory.validate_trust_verdict_attestation_contract_v3",
            side_effect=ValueError("trust_verdict_attestation_missing_keys:item"),
        ):
            resp = await self._get(
                app=app,
                path=f"/internal/judge/cases/{case_id}/trust/verdict-attestation?dispatch_type=final",
                internal_key=runtime.settings.ai_internal_key,
            )

        self.assertEqual(resp.status_code, 500)
        detail = resp.json()["detail"]
        self.assertEqual(detail["code"], "trust_verdict_attestation_contract_violation")
        self.assertIn("trust_verdict_attestation_missing_keys:item", detail["message"])

    async def test_trust_challenge_review_route_should_return_500_when_contract_validation_fails(
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
        case_id = _unique_case_id(8111)
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=_build_phase_request(
                case_id=case_id,
                idempotency_key=f"phase:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)
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
            "app.app_factory.validate_trust_challenge_review_contract_v3",
            side_effect=ValueError("trust_challenge_review_missing_keys:item"),
        ):
            resp = await self._get(
                app=app,
                path=f"/internal/judge/cases/{case_id}/trust/challenges?dispatch_type=final",
                internal_key=runtime.settings.ai_internal_key,
            )

        self.assertEqual(resp.status_code, 500)
        detail = resp.json()["detail"]
        self.assertEqual(detail["code"], "trust_challenge_review_contract_violation")
        self.assertIn("trust_challenge_review_missing_keys:item", detail["message"])

    async def test_trust_kernel_version_route_should_return_500_when_contract_validation_fails(
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
        case_id = _unique_case_id(8107)
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=_build_phase_request(
                case_id=case_id,
                idempotency_key=f"phase:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)
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
            "app.app_factory.validate_trust_kernel_version_contract_v3",
            side_effect=ValueError("trust_kernel_version_missing_keys:item"),
        ):
            resp = await self._get(
                app=app,
                path=f"/internal/judge/cases/{case_id}/trust/kernel-version?dispatch_type=final",
                internal_key=runtime.settings.ai_internal_key,
            )

        self.assertEqual(resp.status_code, 500)
        detail = resp.json()["detail"]
        self.assertEqual(detail["code"], "trust_kernel_version_contract_violation")
        self.assertIn("trust_kernel_version_missing_keys:item", detail["message"])

    async def test_trust_audit_anchor_route_should_return_500_when_contract_validation_fails(
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
        case_id = _unique_case_id(8108)
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=_build_phase_request(
                case_id=case_id,
                idempotency_key=f"phase:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)
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
            "app.app_factory.validate_trust_audit_anchor_contract_v3",
            side_effect=ValueError("trust_audit_anchor_missing_keys:item"),
        ):
            resp = await self._get(
                app=app,
                path=f"/internal/judge/cases/{case_id}/trust/audit-anchor?dispatch_type=final",
                internal_key=runtime.settings.ai_internal_key,
            )

        self.assertEqual(resp.status_code, 500)
        detail = resp.json()["detail"]
        self.assertEqual(detail["code"], "trust_audit_anchor_contract_violation")
        self.assertIn("trust_audit_anchor_missing_keys:item", detail["message"])

    async def test_receipt_route_should_fallback_to_fact_repository_when_trace_missing(self) -> None:
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

        req = _build_phase_request(case_id=7001, idempotency_key="phase:7001")
        dispatch_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(dispatch_resp.status_code, 200)

        fact_receipt = await runtime.workflow_runtime.facts.get_dispatch_receipt(
            dispatch_type="phase",
            job_id=7001,
        )
        self.assertIsNotNone(fact_receipt)
        assert fact_receipt is not None
        self.assertEqual(fact_receipt.status, "reported")

        runtime.trace_store.get_dispatch_receipt = lambda **kwargs: None  # type: ignore[attr-defined]
        receipt_resp = await self._get(
            app=app,
            path="/internal/judge/v3/phase/cases/7001/receipt",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(receipt_resp.status_code, 200)
        self.assertEqual(receipt_resp.json()["status"], "reported")

    async def test_replay_post_should_persist_replay_record_to_fact_repository(self) -> None:
        phase_calls: list[tuple[int, dict]] = []
        final_calls: list[tuple[int, dict]] = []

        async def phase_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            phase_calls.append((case_id, payload))

        async def final_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            final_calls.append((case_id, payload))

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=phase_callback,
            callback_final_report_impl=final_callback,
            callback_phase_failed_impl=phase_callback,
            callback_final_failed_impl=final_callback,
        )
        app = create_app(runtime)
        await runtime.workflow_runtime.db.create_schema()
        before_rows = await runtime.workflow_runtime.facts.list_replay_records(
            job_id=7101,
            limit=200,
        )
        before_count = len(before_rows)

        phase_req = _build_phase_request(case_id=7101, idempotency_key="phase:7101")
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(case_id=7101, idempotency_key="final:7101")
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        replay_resp = await self._post(
            app=app,
            path="/internal/judge/cases/7101/replay?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(replay_resp.status_code, 200)

        replay_rows = await runtime.workflow_runtime.facts.list_replay_records(
            job_id=7101,
            limit=200,
        )
        self.assertEqual(len(replay_rows), before_count + 1)
        self.assertEqual(replay_rows[0].dispatch_type, "final")
        self.assertIn(replay_rows[0].winner, {"pro", "con", "draw"})
        replay_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=7101)
        self.assertEqual(replay_events[-1].event_type, "replay_marked")
        self.assertEqual(replay_events[-1].payload.get("judgeCoreStage"), "replay_computed")

    async def test_replay_post_should_block_when_final_contract_missing_fields(self) -> None:
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

        phase_req = _build_phase_request(case_id=7102, idempotency_key="phase:7102")
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(case_id=7102, idempotency_key="final:7102")
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)
        before_replay_rows = await runtime.workflow_runtime.facts.list_replay_records(
            job_id=7102,
            limit=100,
        )
        before_replay_count = len(before_replay_rows)

        broken_payload = {
            "winner": "pro",
            "proScore": 70.0,
            "conScore": 62.0,
            "dimensionScores": {"logic": 70.0},
        }
        with patch(
            "app.applications.bootstrap_final_report_helpers.build_final_report_payload_for_dispatch_v3",
            return_value=broken_payload,
        ):
            replay_resp = await self._post(
                app=app,
                path="/internal/judge/cases/7102/replay?dispatch_type=final",
                internal_key=runtime.settings.ai_internal_key,
            )
        self.assertEqual(replay_resp.status_code, 409)
        self.assertIn("replay_final_contract_violation", replay_resp.text)

        after_replay_rows = await runtime.workflow_runtime.facts.list_replay_records(
            job_id=7102,
            limit=100,
        )
        self.assertEqual(len(after_replay_rows), before_replay_count)
        workflow_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=7102)
        self.assertNotEqual(workflow_events[-1].event_type, "replay_marked")

    async def test_alert_ack_should_sync_status_to_fact_repository(self) -> None:
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
        alert = runtime.trace_store.upsert_audit_alert(job_id=7201,
            scope_id=1,
            trace_id="trace-alert-7201",
            alert_type="test_alert",
            severity="warning",
            title="test",
            message="test message",
            details={"k": "v"},
        )

        ack_resp = await self._post(
            app=app,
            path=f"/internal/judge/cases/7201/alerts/{alert.alert_id}/ack",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(ack_resp.status_code, 200)
        self.assertEqual(ack_resp.json()["status"], "acked")

        fact_alerts = await runtime.workflow_runtime.facts.list_audit_alerts(
            job_id=7201,
            limit=10,
        )
        self.assertEqual(len(fact_alerts), 1)
        self.assertEqual(fact_alerts[0].alert_id, alert.alert_id)
        self.assertEqual(fact_alerts[0].status, "acked")

    async def test_blindization_reject_should_return_422_and_trigger_failed_callback(self) -> None:
        failed_calls: list[tuple[int, dict]] = []

        async def phase_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        async def failed_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            failed_calls.append((case_id, payload))

        runtime = create_runtime(
            settings=_build_settings(runtime_retry_max_attempts=1),
            callback_phase_report_impl=phase_callback,
            callback_final_report_impl=phase_callback,
            callback_phase_failed_impl=failed_callback,
            callback_final_failed_impl=failed_callback,
        )
        app = create_app(runtime)
        bad_payload = _build_phase_request(case_id=6001, idempotency_key="phase:6001").model_dump(
            mode="json"
        )
        bad_payload["messages"][0]["user_id"] = 99

        bad_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=bad_payload,
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_resp.status_code, 422)
        self.assertIn("input_not_blinded", bad_resp.text)
        self.assertEqual(len(failed_calls), 1)
        self.assertEqual(failed_calls[0][0], 6001)
        self.assertEqual(failed_calls[0][1]["errorCode"], "input_not_blinded")
        self.assertEqual(
            failed_calls[0][1].get("error", {}).get("code"),
            "input_not_blinded",
        )
        workflow_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=6001)
        self.assertIsNotNone(workflow_job)
        assert workflow_job is not None
        self.assertEqual(workflow_job.status, "blocked_failed")
        workflow_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=6001)
        self.assertEqual(workflow_events[-1].payload.get("errorCode"), "input_not_blinded")
        self.assertEqual(workflow_events[-1].payload.get("callbackStatus"), "failed_reported")
        self.assertEqual(
            workflow_events[-1].payload.get("error", {}).get("code"),
            "input_not_blinded",
        )

    async def test_blindization_reject_should_mark_workflow_failed_when_failed_callback_fails(
        self,
    ) -> None:
        async def phase_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        async def failing_failed_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            raise RuntimeError("failed-callback-down")

        runtime = create_runtime(
            settings=_build_settings(runtime_retry_max_attempts=1),
            callback_phase_report_impl=phase_callback,
            callback_final_report_impl=phase_callback,
            callback_phase_failed_impl=failing_failed_callback,
            callback_final_failed_impl=failing_failed_callback,
        )
        app = create_app(runtime)
        bad_payload = _build_phase_request(case_id=6002, idempotency_key="phase:6002").model_dump(
            mode="json"
        )
        bad_payload["messages"][0]["vip"] = True

        bad_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=bad_payload,
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_resp.status_code, 502)
        self.assertIn("phase_failed_callback_failed", bad_resp.text)
        workflow_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=6002)
        self.assertIsNotNone(workflow_job)
        assert workflow_job is not None
        self.assertEqual(workflow_job.status, "blocked_failed")
        receipt_resp = await self._get(
            app=app,
            path="/internal/judge/v3/phase/cases/6002/receipt",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(receipt_resp.status_code, 200)
        self.assertEqual(
            receipt_resp.json()["response"].get("errorCode"),
            "phase_failed_callback_failed",
        )
        workflow_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=6002)
        self.assertEqual(workflow_events[-1].payload.get("errorCode"), "phase_failed_callback_failed")
        self.assertEqual(
            workflow_events[-1].payload.get("callbackStatus"),
            "failed_callback_failed",
        )
        self.assertEqual(
            workflow_events[-1].payload.get("error", {}).get("code"),
            "phase_failed_callback_failed",
        )

    async def test_final_contract_blocked_should_mark_workflow_failed_and_sync_alert(self) -> None:
        failed_calls: list[tuple[int, dict]] = []

        async def phase_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        async def final_failed_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            failed_calls.append((case_id, payload))

        runtime = create_runtime(
            settings=_build_settings(runtime_retry_max_attempts=1),
            callback_phase_report_impl=phase_callback,
            callback_final_report_impl=phase_callback,
            callback_phase_failed_impl=phase_callback,
            callback_final_failed_impl=final_failed_callback,
        )
        app = create_app(runtime)
        final_req = _build_final_request(case_id=7301, idempotency_key="final:7301")

        with patch(
            "app.applications.bootstrap_final_report_helpers.build_final_report_payload_for_dispatch_v3",
            return_value={"winner": "draw", "degradationLevel": 1},
        ):
            blocked_resp = await self._post_json(
                app=app,
                path="/internal/judge/v3/final/dispatch",
                payload=final_req.model_dump(mode="json"),
                internal_key=runtime.settings.ai_internal_key,
            )
        self.assertEqual(blocked_resp.status_code, 502)
        self.assertIn("final_contract_blocked", blocked_resp.text)
        self.assertEqual(len(failed_calls), 1)
        self.assertEqual(failed_calls[0][0], 7301)
        self.assertEqual(failed_calls[0][1]["errorCode"], "final_contract_blocked")

        workflow_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=7301)
        self.assertIsNotNone(workflow_job)
        assert workflow_job is not None
        self.assertEqual(workflow_job.status, "blocked_failed")
        workflow_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=7301)
        self.assertEqual(workflow_events[-1].payload.get("errorCode"), "final_contract_blocked")
        self.assertEqual(workflow_events[-1].payload.get("callbackStatus"), "blocked_failed_reported")
        self.assertEqual(
            workflow_events[-1].payload.get("error", {}).get("code"),
            "final_contract_blocked",
        )

        receipt_resp = await self._get(
            app=app,
            path="/internal/judge/v3/final/cases/7301/receipt",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(receipt_resp.status_code, 200)
        self.assertEqual(
            receipt_resp.json()["response"].get("errorCode"),
            "final_contract_blocked",
        )
        self.assertEqual(
            receipt_resp.json()["response"].get("error", {}).get("category"),
            "contract_blocked",
        )

        fact_alerts = await runtime.workflow_runtime.facts.list_audit_alerts(job_id=7301, limit=10)
        self.assertGreaterEqual(len(fact_alerts), 1)
        self.assertEqual(fact_alerts[0].alert_type, "final_contract_violation")

    async def test_fairness_benchmark_routes_should_persist_and_list_runs(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        run_id = f"run-{_unique_case_id(7601)}"

        post_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": run_id,
                "policy_version": "fairness-benchmark-v1",
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "needs_real_env_reconfirm": True,
                "needs_remediation": False,
                "metrics": {
                    "sample_size": 384,
                    "draw_rate": 0.2,
                    "side_bias_delta": 0.04,
                    "appeal_overturn_rate": 0.07,
                },
                "thresholds": {
                    "draw_rate_max": 0.3,
                    "side_bias_delta_max": 0.08,
                    "appeal_overturn_rate_max": 0.12,
                },
                "summary": {
                    "note": "local reference frozen",
                },
                "source": "harness_freeze_script",
                "reported_by": "ci",
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(post_resp.status_code, 200)
        post_payload = post_resp.json()
        self.assertTrue(post_payload["ok"])
        self.assertEqual(post_payload["item"]["runId"], run_id)
        self.assertEqual(post_payload["item"]["status"], "local_reference_frozen")
        self.assertIsNone(post_payload["alert"])
        self.assertEqual(post_payload["drift"]["baselineRunId"], None)

        list_resp = await self._get(
            app=app,
            path="/internal/judge/fairness/benchmark-runs?policy_version=fairness-benchmark-v1",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(list_resp.status_code, 200)
        list_payload = list_resp.json()
        self.assertGreaterEqual(list_payload["count"], 1)
        self.assertTrue(any(item["runId"] == run_id for item in list_payload["items"]))

        fact_runs = await runtime.workflow_runtime.facts.list_fairness_benchmark_runs(
            policy_version="fairness-benchmark-v1",
            limit=20,
        )
        self.assertTrue(any(item.run_id == run_id for item in fact_runs))

    async def test_fairness_shadow_routes_should_persist_list_and_raise_alert(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        benchmark_run_id = f"run-{_unique_case_id(7605)}"
        shadow_run_id = f"shadow-{_unique_case_id(7606)}"
        shadow_breach_run_id = f"shadow-{_unique_case_id(7607)}"

        benchmark_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": benchmark_run_id,
                "policy_version": "fairness-benchmark-v1",
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "metrics": {
                    "sample_size": 384,
                    "draw_rate": 0.2,
                    "side_bias_delta": 0.04,
                    "appeal_overturn_rate": 0.07,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(benchmark_resp.status_code, 200)

        shadow_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/shadow-runs",
            payload={
                "run_id": shadow_run_id,
                "policy_version": "fairness-benchmark-v1",
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "metrics": {
                    "sample_size": 200,
                    "winner_flip_rate": 0.05,
                    "score_shift_delta": 0.08,
                    "review_required_delta": 0.04,
                },
                "thresholds": {
                    "winner_flip_rate_max": 0.1,
                    "score_shift_delta_max": 0.2,
                    "review_required_delta_max": 0.1,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(shadow_resp.status_code, 200)
        shadow_payload = shadow_resp.json()
        self.assertTrue(shadow_payload["ok"])
        self.assertEqual(shadow_payload["item"]["runId"], shadow_run_id)
        self.assertEqual(shadow_payload["item"]["benchmarkRunId"], benchmark_run_id)
        self.assertEqual(shadow_payload["breaches"], [])
        self.assertIsNone(shadow_payload["alert"])

        list_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/fairness/shadow-runs"
                "?policy_version=fairness-benchmark-v1&benchmark_run_id="
                f"{benchmark_run_id}"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(list_resp.status_code, 200)
        list_payload = list_resp.json()
        self.assertGreaterEqual(list_payload["count"], 1)
        self.assertTrue(any(item["runId"] == shadow_run_id for item in list_payload["items"]))

        breached_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/shadow-runs",
            payload={
                "run_id": shadow_breach_run_id,
                "policy_version": "fairness-benchmark-v1",
                "environment_mode": "local_reference",
                "status": "threshold_violation",
                "threshold_decision": "violated",
                "benchmark_run_id": benchmark_run_id,
                "metrics": {
                    "sample_size": 200,
                    "winner_flip_rate": 0.25,
                    "score_shift_delta": 0.35,
                    "review_required_delta": 0.18,
                },
                "thresholds": {
                    "winner_flip_rate_max": 0.1,
                    "score_shift_delta_max": 0.2,
                    "review_required_delta_max": 0.1,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(breached_resp.status_code, 200)
        breached_payload = breached_resp.json()
        self.assertIn("winner_flip_rate", breached_payload["breaches"])
        self.assertIn("score_shift_delta", breached_payload["breaches"])
        self.assertIn("review_required_delta", breached_payload["breaches"])
        self.assertIsNotNone(breached_payload["alert"])
        self.assertEqual(
            breached_payload["alert"]["type"],
            "fairness_shadow_threshold_violation",
        )

        fact_shadow_runs = await runtime.workflow_runtime.facts.list_fairness_shadow_runs(
            policy_version="fairness-benchmark-v1",
            limit=20,
        )
        self.assertTrue(any(item.run_id == shadow_breach_run_id for item in fact_shadow_runs))

    async def test_fairness_benchmark_threshold_breach_should_raise_alert_outbox(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        baseline_run_id = f"run-{_unique_case_id(7611)}"
        breached_run_id = f"run-{_unique_case_id(7612)}"

        baseline_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": baseline_run_id,
                "policy_version": "fairness-benchmark-v1",
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "metrics": {
                    "sample_size": 384,
                    "draw_rate": 0.2,
                    "side_bias_delta": 0.04,
                    "appeal_overturn_rate": 0.07,
                },
                "thresholds": {
                    "draw_rate_max": 0.3,
                    "side_bias_delta_max": 0.08,
                    "appeal_overturn_rate_max": 0.12,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(baseline_resp.status_code, 200)

        breached_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": breached_run_id,
                "policy_version": "fairness-benchmark-v1",
                "environment_mode": "local_reference",
                "status": "threshold_violation",
                "threshold_decision": "violated",
                "metrics": {
                    "sample_size": 384,
                    "draw_rate": 0.41,
                    "side_bias_delta": 0.04,
                    "appeal_overturn_rate": 0.07,
                },
                "thresholds": {
                    "draw_rate_max": 0.3,
                    "side_bias_delta_max": 0.08,
                    "appeal_overturn_rate_max": 0.12,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(breached_resp.status_code, 200)
        breached_payload = breached_resp.json()
        self.assertTrue(breached_payload["drift"]["hasThresholdBreach"])
        self.assertIn("draw_rate", breached_payload["drift"]["thresholdBreaches"])
        self.assertIsNotNone(breached_payload["alert"])
        self.assertEqual(
            breached_payload["alert"]["type"],
            "fairness_benchmark_threshold_violation",
        )
        self.assertEqual(
            breached_payload["drift"]["baselineRunId"],
            baseline_run_id,
        )

        outbox_resp = await self._get(
            app=app,
            path="/internal/judge/alerts/outbox",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(outbox_resp.status_code, 200)
        outbox_items = outbox_resp.json()["items"]
        self.assertTrue(
            any(
                item.get("payload", {}).get("alertType")
                == "fairness_benchmark_threshold_violation"
                for item in outbox_items
            )
        )

        fact_alerts = await runtime.workflow_runtime.facts.list_audit_alerts(
            job_id=0,
            limit=20,
        )
        self.assertTrue(
            any(item.alert_type == "fairness_benchmark_threshold_violation" for item in fact_alerts)
        )

    async def test_fairness_case_read_model_routes_should_return_case_and_list_views(self) -> None:
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
        case_id = _unique_case_id(7621)
        phase_req = _build_phase_request(
            case_id=case_id,
            idempotency_key=f"phase:{case_id}",
            judge_policy_version="v3-default",
        )
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(
            case_id=case_id,
            idempotency_key=f"final:{case_id}",
            judge_policy_version="v3-default",
        )
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        run_id = f"run-{_unique_case_id(7622)}"
        benchmark_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": run_id,
                "policy_version": "v3-default",
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "metrics": {
                    "sample_size": 384,
                    "draw_rate": 0.2,
                    "side_bias_delta": 0.03,
                    "appeal_overturn_rate": 0.06,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(benchmark_resp.status_code, 200)
        benchmark_run_id = benchmark_resp.json()["item"]["runId"]

        shadow_run_id = f"shadow-{_unique_case_id(7624)}"
        shadow_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/shadow-runs",
            payload={
                "run_id": shadow_run_id,
                "policy_version": "v3-default",
                "benchmark_run_id": benchmark_run_id,
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "metrics": {
                    "sample_size": 200,
                    "winner_flip_rate": 0.05,
                    "score_shift_delta": 0.08,
                    "review_required_delta": 0.03,
                },
                "thresholds": {
                    "winner_flip_rate_max": 0.1,
                    "score_shift_delta_max": 0.2,
                    "review_required_delta_max": 0.1,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(shadow_resp.status_code, 200)

        detail_resp = await self._get(
            app=app,
            path=f"/internal/judge/fairness/cases/{case_id}?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(detail_resp.status_code, 200)
        detail_payload = detail_resp.json()
        self.assertEqual(detail_payload["caseId"], case_id)
        self.assertEqual(detail_payload["dispatchType"], "final")
        self.assertEqual(set(detail_payload.keys()), set(CASE_FAIRNESS_DETAIL_TOP_LEVEL_KEYS))
        validate_case_fairness_detail_contract(detail_payload)
        item = detail_payload["item"]
        self.assertEqual(set(item.keys()), set(CASE_FAIRNESS_ITEM_KEYS))
        self.assertEqual(item["caseId"], case_id)
        self.assertIn(item["gateConclusion"], {"pass_through", "blocked_to_draw"})
        self.assertIsInstance(item["panelDisagreement"]["runtimeProfiles"], dict)
        self.assertIn("judgeA", item["panelDisagreement"]["runtimeProfiles"])
        self.assertEqual(item["driftSummary"]["latestRun"]["runId"], run_id)
        self.assertEqual(item["shadowSummary"]["latestRun"]["runId"], shadow_run_id)
        self.assertFalse(item["shadowSummary"]["hasShadowBreach"])

        list_resp = await self._get(
            app=app,
            path="/internal/judge/fairness/cases?dispatch_type=final&limit=50",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(list_resp.status_code, 200)
        list_payload = list_resp.json()
        self.assertEqual(set(list_payload.keys()), set(CASE_FAIRNESS_LIST_TOP_LEVEL_KEYS))
        self.assertEqual(set(list_payload["aggregations"].keys()), set(CASE_FAIRNESS_AGGREGATIONS_KEYS))
        self.assertEqual(set(list_payload["filters"].keys()), set(CASE_FAIRNESS_FILTER_KEYS))
        validate_case_fairness_list_contract(list_payload)
        self.assertGreaterEqual(list_payload["count"], 1)
        self.assertGreaterEqual(list_payload["returned"], 1)
        self.assertTrue(any(row["caseId"] == case_id for row in list_payload["items"]))
        self.assertEqual(list_payload["filters"]["dispatchType"], "final")
        self.assertEqual(list_payload["aggregations"]["totalMatched"], list_payload["count"])
        self.assertGreaterEqual(
            list_payload["aggregations"]["gateConclusionCounts"][item["gateConclusion"]],
            1,
        )
        self.assertGreaterEqual(
            list_payload["aggregations"]["policyVersionCounts"]["v3-default"],
            1,
        )

        challenge_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/cases/{case_id}/trust/challenges/request"
                "?dispatch_type=auto&reason_code=manual_challenge&requested_by=ops&auto_accept=true"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(challenge_resp.status_code, 200)
        challenge_payload = challenge_resp.json()
        self.assertEqual(challenge_payload["item"]["challengeState"], "under_review")

        filtered_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/fairness/cases"
                f"?dispatch_type=final&gate_conclusion={item['gateConclusion']}"
                "&challenge_state=under_review&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(filtered_resp.status_code, 200)
        filtered_payload = filtered_resp.json()
        self.assertGreaterEqual(filtered_payload["count"], 1)
        self.assertTrue(any(row["caseId"] == case_id for row in filtered_payload["items"]))
        self.assertEqual(filtered_payload["filters"]["sortBy"], "updated_at")
        self.assertEqual(filtered_payload["filters"]["sortOrder"], "desc")

        drift_filter_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/fairness/cases"
                "?dispatch_type=final&policy_version=v3-default"
                "&has_threshold_breach=false&has_drift_breach=false&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(drift_filter_resp.status_code, 200)
        drift_filter_payload = drift_filter_resp.json()
        self.assertGreaterEqual(drift_filter_payload["count"], 1)
        self.assertTrue(any(row["caseId"] == case_id for row in drift_filter_payload["items"]))
        self.assertEqual(drift_filter_payload["filters"]["policyVersion"], "v3-default")
        self.assertFalse(drift_filter_payload["filters"]["hasThresholdBreach"])
        self.assertFalse(drift_filter_payload["filters"]["hasDriftBreach"])

        shadow_filter_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/fairness/cases"
                "?dispatch_type=final&policy_version=v3-default"
                "&has_shadow_breach=false&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(shadow_filter_resp.status_code, 200)
        shadow_filter_payload = shadow_filter_resp.json()
        self.assertGreaterEqual(shadow_filter_payload["count"], 1)
        self.assertTrue(any(row["caseId"] == case_id for row in shadow_filter_payload["items"]))
        self.assertFalse(shadow_filter_payload["filters"]["hasShadowBreach"])

        case_id_2 = _unique_case_id(7623)
        phase_req_2 = _build_phase_request(
            case_id=case_id_2,
            idempotency_key=f"phase:{case_id_2}",
            judge_policy_version="v3-default",
        )
        phase_resp_2 = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req_2.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp_2.status_code, 200)
        final_req_2 = _build_final_request(
            case_id=case_id_2,
            idempotency_key=f"final:{case_id_2}",
            judge_policy_version="v3-default",
        )
        final_resp_2 = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req_2.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp_2.status_code, 200)

        page_resp = await self._get(
            app=app,
            path="/internal/judge/fairness/cases?dispatch_type=final&offset=1&limit=1",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(page_resp.status_code, 200)
        page_payload = page_resp.json()
        self.assertGreaterEqual(page_payload["count"], 2)
        self.assertEqual(page_payload["returned"], 1)
        self.assertEqual(page_payload["filters"]["offset"], 1)

        open_review_resp = await self._get(
            app=app,
            path="/internal/judge/fairness/cases?dispatch_type=final&has_open_review=true&limit=50",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(open_review_resp.status_code, 200)
        open_review_payload = open_review_resp.json()
        self.assertTrue(any(row["caseId"] == case_id for row in open_review_payload["items"]))
        self.assertTrue(all(bool(row["challengeLink"]["hasOpenReview"]) for row in open_review_payload["items"]))
        self.assertGreaterEqual(open_review_payload["aggregations"]["openReviewCount"], 1)
        self.assertGreaterEqual(open_review_payload["aggregations"]["withChallengeCount"], 1)

        sorted_resp = await self._get(
            app=app,
            path="/internal/judge/fairness/cases?dispatch_type=final&sort_by=updated_at&sort_order=asc&limit=2",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(sorted_resp.status_code, 200)
        sorted_payload = sorted_resp.json()
        self.assertEqual(sorted_payload["returned"], 2)
        self.assertEqual(sorted_payload["filters"]["sortBy"], "updated_at")
        self.assertEqual(sorted_payload["filters"]["sortOrder"], "asc")
        self.assertEqual(sorted_payload["aggregations"]["totalMatched"], sorted_payload["count"])
        ordered_case_ids = [int(row["caseId"]) for row in sorted_payload["items"]]
        self.assertEqual(ordered_case_ids[0], case_id)
        self.assertEqual(ordered_case_ids[1], case_id_2)

        invalid_gate_resp = await self._get(
            app=app,
            path="/internal/judge/fairness/cases?gate_conclusion=bad-value",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(invalid_gate_resp.status_code, 422)
        self.assertIn("invalid_gate_conclusion", invalid_gate_resp.text)

        invalid_challenge_resp = await self._get(
            app=app,
            path="/internal/judge/fairness/cases?challenge_state=bad-value",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(invalid_challenge_resp.status_code, 422)
        self.assertIn("invalid_challenge_state", invalid_challenge_resp.text)

        invalid_sort_by_resp = await self._get(
            app=app,
            path="/internal/judge/fairness/cases?sort_by=bad-value",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(invalid_sort_by_resp.status_code, 422)
        self.assertIn("invalid_sort_by", invalid_sort_by_resp.text)

        invalid_sort_order_resp = await self._get(
            app=app,
            path="/internal/judge/fairness/cases?sort_order=bad-value",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(invalid_sort_order_resp.status_code, 422)
        self.assertIn("invalid_sort_order", invalid_sort_order_resp.text)

    async def test_fairness_case_list_route_should_return_500_when_contract_validation_fails(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)

        with patch(
            "app.app_factory.validate_case_fairness_list_contract_v3",
            side_effect=ValueError("fairness_case_list_missing_keys:items"),
        ):
            resp = await self._get(
                app=app,
                path="/internal/judge/fairness/cases?dispatch_type=final",
                internal_key=runtime.settings.ai_internal_key,
            )

        self.assertEqual(resp.status_code, 500)
        detail = resp.json()["detail"]
        self.assertEqual(detail["code"], "fairness_case_list_contract_violation")
        self.assertIn("fairness_case_list_missing_keys:items", detail["message"])

    async def test_fairness_case_detail_route_should_return_500_when_contract_validation_fails(
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
        case_id = _unique_case_id(7625)
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=_build_phase_request(
                case_id=case_id,
                idempotency_key=f"phase:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)
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
            "app.app_factory.validate_case_fairness_detail_contract_v3",
            side_effect=ValueError("fairness_case_detail_missing_keys:item"),
        ):
            resp = await self._get(
                app=app,
                path=f"/internal/judge/fairness/cases/{case_id}?dispatch_type=final",
                internal_key=runtime.settings.ai_internal_key,
            )

        self.assertEqual(resp.status_code, 500)
        detail = resp.json()["detail"]
        self.assertEqual(detail["code"], "fairness_case_detail_contract_violation")
        self.assertIn("fairness_case_detail_missing_keys:item", detail["message"])

    async def test_fairness_dashboard_route_should_return_overview_trends_and_top_risk(self) -> None:
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
        case_id = _unique_case_id(7841)

        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=_build_phase_request(
                case_id=case_id,
                idempotency_key=f"phase:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)
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

        benchmark_run_id = f"run-{_unique_case_id(7842)}"
        benchmark_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": benchmark_run_id,
                "policy_version": "v3-default",
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "metrics": {
                    "sample_size": 384,
                    "draw_rate": 0.2,
                    "side_bias_delta": 0.03,
                    "appeal_overturn_rate": 0.06,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(benchmark_resp.status_code, 200)

        shadow_run_id = f"shadow-{_unique_case_id(7843)}"
        shadow_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/shadow-runs",
            payload={
                "run_id": shadow_run_id,
                "policy_version": "v3-default",
                "benchmark_run_id": benchmark_run_id,
                "environment_mode": "local_reference",
                "status": "threshold_violation",
                "threshold_decision": "violated",
                "metrics": {
                    "sample_size": 200,
                    "winner_flip_rate": 0.22,
                    "score_shift_delta": 0.33,
                    "review_required_delta": 0.18,
                },
                "thresholds": {
                    "winner_flip_rate_max": 0.1,
                    "score_shift_delta_max": 0.2,
                    "review_required_delta_max": 0.1,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(shadow_resp.status_code, 200)

        dashboard_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/fairness/dashboard"
                "?dispatch_type=final&policy_version=v3-default"
                "&window_days=7&top_limit=10&case_scan_limit=200"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(dashboard_resp.status_code, 200)
        payload = dashboard_resp.json()
        self.assertEqual(set(payload.keys()), set(FAIRNESS_DASHBOARD_TOP_LEVEL_KEYS))
        self.assertEqual(
            set(payload["overview"].keys()),
            set(FAIRNESS_DASHBOARD_OVERVIEW_KEYS),
        )
        self.assertEqual(
            set(payload["gateDistribution"].keys()),
            set(FAIRNESS_DASHBOARD_GATE_DISTRIBUTION_KEYS),
        )
        self.assertEqual(
            set(payload["trends"].keys()),
            set(FAIRNESS_DASHBOARD_TRENDS_KEYS),
        )
        self.assertEqual(
            set(payload["filters"].keys()),
            set(FAIRNESS_DASHBOARD_FILTER_KEYS),
        )
        validate_fairness_dashboard_contract(payload)
        self.assertIsInstance(payload["overview"], dict)
        self.assertIsInstance(payload["trends"], dict)
        self.assertIsInstance(payload["topRiskCases"], list)
        self.assertIsInstance(payload["gateDistribution"], dict)
        self.assertGreaterEqual(payload["overview"]["totalMatched"], 1)
        self.assertGreaterEqual(payload["overview"]["shadowBreachCount"], 1)
        self.assertGreaterEqual(
            payload["gateDistribution"]["pass_through"]
            + payload["gateDistribution"]["blocked_to_draw"],
            1,
        )
        self.assertTrue(any(row["caseId"] == case_id for row in payload["topRiskCases"]))
        self.assertTrue(
            any(
                row["caseId"] == case_id and "shadow_breach" in row["riskTags"]
                for row in payload["topRiskCases"]
            )
        )
        self.assertTrue(
            any(
                row.get("runId") == benchmark_run_id
                for row in payload["trends"]["benchmarkRuns"]
            )
        )
        self.assertTrue(
            any(
                row.get("runId") == shadow_run_id
                for row in payload["trends"]["shadowRuns"]
            )
        )
        self.assertEqual(payload["filters"]["dispatchType"], "final")
        self.assertEqual(payload["filters"]["policyVersion"], "v3-default")
        self.assertEqual(payload["filters"]["windowDays"], 7)
        self.assertEqual(payload["filters"]["topLimit"], 10)

    async def test_fairness_dashboard_route_should_return_500_when_contract_validation_fails(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)

        with patch(
            "app.app_factory.validate_fairness_dashboard_contract_v3",
            side_effect=ValueError("fairness_dashboard_overview_missing_keys"),
        ):
            resp = await self._get(
                app=app,
                path="/internal/judge/fairness/dashboard?dispatch_type=final",
                internal_key=runtime.settings.ai_internal_key,
            )

        self.assertEqual(resp.status_code, 500)
        detail = resp.json()["detail"]
        self.assertEqual(detail["code"], "fairness_dashboard_contract_violation")
        self.assertIn(
            "fairness_dashboard_overview_missing_keys",
            detail["message"],
        )

    async def test_fairness_calibration_pack_route_should_return_thresholds_drift_and_risks(
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
        case_id = _unique_case_id(7851)

        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=_build_phase_request(
                case_id=case_id,
                idempotency_key=f"phase:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)
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

        baseline_run_id = f"run-{_unique_case_id(7852)}"
        baseline_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": baseline_run_id,
                "policy_version": "v3-default",
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "metrics": {
                    "sample_size": 400,
                    "draw_rate": 0.2,
                    "side_bias_delta": 0.03,
                    "appeal_overturn_rate": 0.05,
                },
                "thresholds": {
                    "draw_rate_max": 0.3,
                    "side_bias_delta_max": 0.08,
                    "appeal_overturn_rate_max": 0.1,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(baseline_resp.status_code, 200)

        breached_run_id = f"run-{_unique_case_id(7853)}"
        breached_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": breached_run_id,
                "policy_version": "v3-default",
                "environment_mode": "local_reference",
                "status": "threshold_violation",
                "threshold_decision": "violated",
                "metrics": {
                    "sample_size": 420,
                    "draw_rate": 0.45,
                    "side_bias_delta": 0.04,
                    "appeal_overturn_rate": 0.08,
                },
                "thresholds": {
                    "draw_rate_max": 0.3,
                    "side_bias_delta_max": 0.08,
                    "appeal_overturn_rate_max": 0.1,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(breached_resp.status_code, 200)

        shadow_run_id = f"shadow-{_unique_case_id(7854)}"
        shadow_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/shadow-runs",
            payload={
                "run_id": shadow_run_id,
                "policy_version": "v3-default",
                "benchmark_run_id": breached_run_id,
                "environment_mode": "local_reference",
                "status": "threshold_violation",
                "threshold_decision": "violated",
                "metrics": {
                    "sample_size": 200,
                    "winner_flip_rate": 0.26,
                    "score_shift_delta": 0.3,
                    "review_required_delta": 0.19,
                },
                "thresholds": {
                    "winner_flip_rate_max": 0.1,
                    "score_shift_delta_max": 0.2,
                    "review_required_delta_max": 0.1,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(shadow_resp.status_code, 200)

        pack_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/fairness/calibration-pack"
                "?dispatch_type=final&policy_version=v3-default"
                "&case_scan_limit=200&risk_limit=30"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(pack_resp.status_code, 200)
        payload = pack_resp.json()

        self.assertIsInstance(payload["overview"], dict)
        self.assertIsInstance(payload["thresholdSuggestions"], dict)
        self.assertIsInstance(payload["driftSummary"], dict)
        self.assertIsInstance(payload["riskItems"], list)
        self.assertIsInstance(payload["onEnvInputTemplate"], dict)
        self.assertGreaterEqual(payload["overview"]["benchmarkRunCount"], 2)
        self.assertGreaterEqual(payload["overview"]["shadowRunCount"], 1)
        self.assertGreaterEqual(payload["overview"]["highRiskCount"], 1)
        self.assertEqual(payload["overview"]["latestBenchmarkRunId"], breached_run_id)
        self.assertEqual(payload["overview"]["latestShadowRunId"], shadow_run_id)
        self.assertEqual(payload["filters"]["policyVersion"], "v3-default")
        self.assertEqual(payload["filters"]["riskLimit"], 30)

        threshold_suggestions = payload["thresholdSuggestions"]
        self.assertEqual(threshold_suggestions["method"], "local_observed_max_with_margin")
        self.assertIsNotNone(
            threshold_suggestions["benchmark"]["drawRateMaxSuggested"]
        )
        self.assertIsNotNone(
            threshold_suggestions["shadow"]["winnerFlipRateMaxSuggested"]
        )

        drift_summary = payload["driftSummary"]
        self.assertEqual(drift_summary["benchmark"]["latestRunId"], breached_run_id)
        self.assertEqual(drift_summary["shadow"]["latestRunId"], shadow_run_id)
        self.assertTrue(drift_summary["benchmark"]["hasThresholdBreach"])
        self.assertTrue(drift_summary["shadow"]["hasBreach"])

        risk_types = {row.get("riskType") for row in payload["riskItems"]}
        self.assertIn("benchmark_threshold_violation", risk_types)
        self.assertIn("shadow_threshold_violation", risk_types)
        self.assertEqual(
            payload["onEnvInputTemplate"]["envMarker"]["REAL_CALIBRATION_ENV_READY"],
            "true",
        )
        self.assertTrue(
            any(
                "real-env pass" in str(note)
                for note in payload["onEnvInputTemplate"]["notes"]
            )
        )

    async def test_policy_calibration_advisor_route_should_return_gate_and_advisory_actions(
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
        case_id = _unique_case_id(7861)

        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=_build_phase_request(
                case_id=case_id,
                idempotency_key=f"phase:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)
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

        benchmark_run_id = f"run-{_unique_case_id(7862)}"
        benchmark_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": benchmark_run_id,
                "policy_version": "v3-default",
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "metrics": {
                    "sample_size": 400,
                    "draw_rate": 0.18,
                    "side_bias_delta": 0.03,
                    "appeal_overturn_rate": 0.05,
                },
                "thresholds": {
                    "draw_rate_max": 0.3,
                    "side_bias_delta_max": 0.08,
                    "appeal_overturn_rate_max": 0.1,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(benchmark_resp.status_code, 200)

        shadow_run_id = f"shadow-{_unique_case_id(7863)}"
        shadow_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/shadow-runs",
            payload={
                "run_id": shadow_run_id,
                "policy_version": "v3-default",
                "benchmark_run_id": benchmark_run_id,
                "environment_mode": "local_reference",
                "status": "threshold_violation",
                "threshold_decision": "violated",
                "metrics": {
                    "sample_size": 220,
                    "winner_flip_rate": 0.22,
                    "score_shift_delta": 0.31,
                    "review_required_delta": 0.16,
                },
                "thresholds": {
                    "winner_flip_rate_max": 0.1,
                    "score_shift_delta_max": 0.2,
                    "review_required_delta_max": 0.1,
                },
                "summary": {
                    "hasBreach": True,
                    "breaches": ["winner_flip_rate_exceeded"],
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(shadow_resp.status_code, 200)

        advisor_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/fairness/policy-calibration-advisor"
                "?dispatch_type=final&policy_version=v3-default"
                "&case_scan_limit=200&risk_limit=30"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(advisor_resp.status_code, 200)
        payload = advisor_resp.json()

        self.assertIsInstance(payload["overview"], dict)
        self.assertIsInstance(payload["thresholdSuggestions"], dict)
        self.assertIsInstance(payload["driftSummary"], dict)
        self.assertIsInstance(payload["releaseGate"], dict)
        self.assertIsInstance(payload["recommendedActions"], list)
        self.assertIsInstance(payload["riskItems"], list)
        self.assertEqual(payload["overview"]["policyVersion"], "v3-default")
        self.assertEqual(payload["overview"]["latestBenchmarkRunId"], benchmark_run_id)
        self.assertEqual(payload["overview"]["latestShadowRunId"], shadow_run_id)

        release_gate = payload["releaseGate"]
        self.assertFalse(release_gate["passed"])
        self.assertEqual(
            release_gate["code"],
            "registry_fairness_gate_shadow_threshold_not_accepted",
        )

        action_ids = {
            str(row.get("actionId") or "")
            for row in payload["recommendedActions"]
            if isinstance(row, dict)
        }
        self.assertIn("prepare_candidate_policy_patch", action_ids)
        self.assertIn("manual_review_before_activation", action_ids)
        self.assertTrue(
            all(
                bool(row.get("advisoryOnly"))
                for row in payload["recommendedActions"]
                if isinstance(row, dict)
            )
        )
        self.assertTrue(
            any(
                "advisory only" in str(note).lower()
                for note in payload["notes"]
            )
        )
        self.assertEqual(payload["filters"]["policyVersion"], "v3-default")
        self.assertEqual(payload["filters"]["effectivePolicyVersion"], "v3-default")
        self.assertEqual(payload["filters"]["riskLimit"], 30)

    async def test_ops_read_model_pack_route_should_join_fairness_registry_and_trust_v5(self) -> None:
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
        case_id = _unique_case_id(7844)

        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=_build_phase_request(
                case_id=case_id,
                idempotency_key=f"phase:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)
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

        pack_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/ops/read-model/pack"
                "?dispatch_type=final&policy_version=v3-default"
                "&window_days=7&top_limit=10&case_scan_limit=200"
                "&include_case_trust=true&trust_case_limit=3"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(pack_resp.status_code, 200)
        payload = pack_resp.json()
        self.assertEqual(set(payload.keys()), set(OPS_READ_MODEL_PACK_V5_TOP_LEVEL_KEYS))
        self.assertEqual(
            set(payload["adaptiveSummary"].keys()),
            set(OPS_READ_MODEL_PACK_V5_ADAPTIVE_SUMMARY_KEYS),
        )
        self.assertEqual(
            set(payload["trustOverview"].keys()),
            set(OPS_READ_MODEL_PACK_V5_TRUST_OVERVIEW_KEYS),
        )
        self.assertEqual(
            set(payload["judgeWorkflowCoverage"].keys()),
            set(OPS_READ_MODEL_PACK_V5_JUDGE_WORKFLOW_COVERAGE_KEYS),
        )
        self.assertEqual(
            set(payload["filters"].keys()),
            set(OPS_READ_MODEL_PACK_V5_FILTER_KEYS),
        )
        validate_ops_read_model_pack_v5_contract(payload)
        self.assertIsInstance(payload["fairnessDashboard"], dict)
        self.assertIsInstance(payload["fairnessCalibrationAdvisor"], dict)
        self.assertIsInstance(payload["panelRuntimeReadiness"], dict)
        self.assertIsInstance(payload["registryGovernance"], dict)
        self.assertIsInstance(payload["registryPromptToolGovernance"], dict)
        self.assertIsInstance(payload["courtroomReadModel"], dict)
        self.assertIsInstance(payload["courtroomQueue"], dict)
        self.assertIsInstance(payload["courtroomDrilldown"], dict)
        self.assertIsInstance(payload["reviewQueue"], dict)
        self.assertIsInstance(payload["reviewTrustPriority"], dict)
        self.assertIsInstance(payload["evidenceClaimQueue"], dict)
        self.assertIsInstance(payload["trustChallengeQueue"], dict)
        self.assertIsInstance(payload["policyGateSimulation"], dict)
        self.assertIsInstance(payload["adaptiveSummary"], dict)
        self.assertIsInstance(payload["trustOverview"], dict)
        self.assertIsInstance(payload["judgeWorkflowCoverage"], dict)
        self.assertIsInstance(payload["caseChainCoverage"], dict)
        self.assertIsInstance(payload["fairnessGateOverview"], dict)
        self.assertIsInstance(payload["policyKernelBinding"], dict)
        self.assertGreaterEqual(
            payload["fairnessDashboard"]["overview"]["totalMatched"],
            1,
        )
        self.assertIn("releaseGate", payload["fairnessCalibrationAdvisor"])
        self.assertIn("groups", payload["panelRuntimeReadiness"])
        self.assertIn("calibrationGateCode", payload["adaptiveSummary"])
        self.assertGreaterEqual(payload["adaptiveSummary"]["recommendedActionCount"], 1)
        self.assertIn("reviewQueueCount", payload["adaptiveSummary"])
        self.assertIn("policySimulationBlockedCount", payload["adaptiveSummary"])
        self.assertIn("courtroomSampleCount", payload["adaptiveSummary"])
        self.assertIn("courtroomQueueCount", payload["adaptiveSummary"])
        self.assertIn("courtroomDrilldownCount", payload["adaptiveSummary"])
        self.assertIn("courtroomDrilldownHighRiskCount", payload["adaptiveSummary"])
        self.assertIn("evidenceClaimQueueCount", payload["adaptiveSummary"])
        self.assertIn("evidenceClaimHighRiskCount", payload["adaptiveSummary"])
        self.assertIn("registryPromptToolRiskCount", payload["adaptiveSummary"])
        self.assertIn("trustChallengeQueueCount", payload["adaptiveSummary"])
        self.assertIn("reviewTrustPriorityCount", payload["adaptiveSummary"])
        self.assertIn("reviewUnifiedHighPriorityCount", payload["adaptiveSummary"])
        self.assertGreaterEqual(payload["adaptiveSummary"]["reviewQueueCount"], 0)
        self.assertGreaterEqual(payload["adaptiveSummary"]["courtroomSampleCount"], 1)
        self.assertGreaterEqual(payload["adaptiveSummary"]["courtroomQueueCount"], 1)
        self.assertGreaterEqual(payload["adaptiveSummary"]["courtroomDrilldownCount"], 1)
        self.assertGreaterEqual(payload["adaptiveSummary"]["evidenceClaimQueueCount"], 1)
        self.assertGreaterEqual(
            payload["adaptiveSummary"]["registryPromptToolRiskCount"],
            0,
        )
        self.assertIn(
            "activeVersions",
            payload["registryGovernance"],
        )
        self.assertIn(
            "dependencyHealth",
            payload["registryGovernance"],
        )
        self.assertIn("summary", payload["registryPromptToolGovernance"])
        self.assertIn("riskItems", payload["registryPromptToolGovernance"])
        self.assertGreaterEqual(payload["courtroomReadModel"]["count"], 1)
        self.assertIn("items", payload["courtroomReadModel"])
        self.assertGreaterEqual(payload["courtroomQueue"]["count"], 1)
        self.assertEqual(payload["courtroomQueue"]["filters"]["sortBy"], "risk_score")
        self.assertEqual(payload["courtroomQueue"]["filters"]["dispatchType"], "auto")
        self.assertGreaterEqual(payload["courtroomDrilldown"]["count"], 1)
        self.assertIn("aggregations", payload["courtroomDrilldown"])
        self.assertIn("simulatedGate", payload["policyGateSimulation"]["items"][0])
        self.assertGreaterEqual(payload["reviewQueue"]["count"], 0)
        self.assertEqual(payload["reviewQueue"]["filters"]["sortBy"], "risk_score")
        self.assertGreaterEqual(payload["reviewTrustPriority"]["count"], 0)
        self.assertEqual(
            payload["reviewTrustPriority"]["filters"]["sortBy"],
            "unified_priority_score",
        )
        self.assertGreaterEqual(payload["evidenceClaimQueue"]["count"], 1)
        self.assertEqual(payload["evidenceClaimQueue"]["filters"]["sortBy"], "risk_score")
        self.assertIn("aggregations", payload["evidenceClaimQueue"])
        self.assertEqual(
            payload["adaptiveSummary"]["evidenceClaimConflictCaseCount"],
            payload["evidenceClaimQueue"]["aggregations"]["conflictCaseCount"],
        )
        self.assertEqual(
            payload["adaptiveSummary"]["evidenceClaimUnansweredClaimCaseCount"],
            payload["evidenceClaimQueue"]["aggregations"]["unansweredCaseCount"],
        )
        self.assertGreaterEqual(payload["trustChallengeQueue"]["count"], 0)
        self.assertEqual(payload["trustChallengeQueue"]["filters"]["challengeState"], "open")
        self.assertGreaterEqual(payload["trustOverview"]["count"], 1)
        self.assertGreaterEqual(payload["trustOverview"]["verifiedCount"], 0)
        self.assertLessEqual(
            payload["trustOverview"]["verifiedCount"],
            payload["trustOverview"]["count"],
        )
        self.assertGreaterEqual(payload["trustOverview"]["reviewRequiredCount"], 0)
        self.assertTrue(
            any(row["caseId"] == case_id for row in payload["trustOverview"]["items"])
        )
        self.assertGreaterEqual(payload["judgeWorkflowCoverage"]["totalCases"], 1)
        self.assertGreaterEqual(payload["judgeWorkflowCoverage"]["fullCount"], 1)
        self.assertLessEqual(payload["judgeWorkflowCoverage"]["fullCoverageRate"], 1.0)
        self.assertGreaterEqual(payload["caseChainCoverage"]["totalCases"], 1)
        self.assertGreaterEqual(payload["caseChainCoverage"]["completeCount"], 1)
        self.assertIn("byObjectPresence", payload["caseChainCoverage"])
        self.assertIn("caseDossier", payload["caseChainCoverage"]["byObjectPresence"])
        self.assertGreaterEqual(payload["fairnessGateOverview"]["totalCases"], 1)
        self.assertIn("caseDecisionCounts", payload["fairnessGateOverview"])
        self.assertIn("policyGateDecisionCounts", payload["fairnessGateOverview"])
        self.assertIn("policyGateSourceCounts", payload["fairnessGateOverview"])
        self.assertIn("gateDecisionCounts", payload["policyKernelBinding"])
        self.assertGreaterEqual(payload["policyKernelBinding"]["trackedPolicyVersionCount"], 1)
        self.assertGreaterEqual(payload["policyKernelBinding"]["kernelBoundPolicyCount"], 1)
        self.assertIn("v3-default", payload["policyKernelBinding"]["casePolicyVersionCounts"])
        courtroom_item = payload["courtroomReadModel"]["items"][0]
        self.assertIn("policyVersion", courtroom_item)
        self.assertIn("policyKernelVersion", courtroom_item)
        self.assertIn("policyKernelHash", courtroom_item)
        self.assertIn("policyGateDecision", courtroom_item)
        self.assertIn("policyGateSource", courtroom_item)
        self.assertIn("policyOverrideApplied", courtroom_item)
        self.assertEqual(courtroom_item["policyVersion"], "v3-default")
        self.assertEqual(payload["filters"]["dispatchType"], "final")
        self.assertEqual(payload["filters"]["policyVersion"], "v3-default")
        self.assertEqual(payload["filters"]["trustCaseLimit"], 3)
        self.assertEqual(payload["filters"]["calibrationRiskLimit"], 50)
        self.assertEqual(payload["filters"]["panelGroupLimit"], 50)

        pack_without_trust_resp = await self._get(
            app=app,
            path="/internal/judge/ops/read-model/pack?include_case_trust=false",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(pack_without_trust_resp.status_code, 200)
        without_trust_payload = pack_without_trust_resp.json()
        self.assertFalse(without_trust_payload["trustOverview"]["included"])
        self.assertEqual(without_trust_payload["trustOverview"]["count"], 0)
        self.assertEqual(without_trust_payload["trustOverview"]["errorCount"], 0)
        self.assertIn("adaptiveSummary", without_trust_payload)

    async def test_panel_runtime_profile_ops_view_should_support_filters_and_aggregations(
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
        case_id = _unique_case_id(7821)

        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=_build_phase_request(
                case_id=case_id,
                idempotency_key=f"phase:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

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

        run_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": f"run-{_unique_case_id(7822)}",
                "policy_version": "v3-default",
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "metrics": {
                    "sample_size": 384,
                    "draw_rate": 0.2,
                    "side_bias_delta": 0.03,
                    "appeal_overturn_rate": 0.06,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(run_resp.status_code, 200)

        list_resp = await self._get(
            app=app,
            path="/internal/judge/panels/runtime/profiles?dispatch_type=final&limit=200",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(list_resp.status_code, 200)
        payload = list_resp.json()
        self.assertEqual(set(payload.keys()), set(PANEL_RUNTIME_PROFILE_TOP_LEVEL_KEYS))
        self.assertEqual(set(payload["aggregations"].keys()), set(PANEL_RUNTIME_PROFILE_AGGREGATIONS_KEYS))
        self.assertEqual(set(payload["filters"].keys()), set(PANEL_RUNTIME_PROFILE_FILTER_KEYS))
        validate_panel_runtime_profile_contract(payload)
        self.assertGreaterEqual(payload["count"], 3)
        self.assertGreaterEqual(payload["returned"], 3)
        self.assertEqual(set(payload["items"][0].keys()), set(PANEL_RUNTIME_PROFILE_ITEM_KEYS))
        self.assertGreaterEqual(payload["aggregations"]["byJudgeId"]["judgeA"], 1)
        self.assertGreaterEqual(payload["aggregations"]["byJudgeId"]["judgeB"], 1)
        self.assertGreaterEqual(payload["aggregations"]["byJudgeId"]["judgeC"], 1)
        self.assertGreaterEqual(
            payload["aggregations"]["byModelStrategy"]["deterministic_path_alignment"],
            1,
        )
        self.assertGreaterEqual(
            payload["aggregations"]["byStrategySlot"]["path_alignment"],
            1,
        )
        self.assertGreaterEqual(
            payload["aggregations"]["byDomainSlot"]["general"],
            1,
        )
        self.assertGreaterEqual(
            payload["aggregations"]["byProfileSource"]["builtin_default"],
            1,
        )
        self.assertTrue(any(row["caseId"] == case_id for row in payload["items"]))

        judge_a_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/panels/runtime/profiles"
                "?dispatch_type=final&judge_id=judgeA"
                "&profile_id=panel-judgeA-weighted-v1&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(judge_a_resp.status_code, 200)
        judge_a_payload = judge_a_resp.json()
        self.assertGreaterEqual(judge_a_payload["count"], 1)
        self.assertEqual(judge_a_payload["filters"]["judgeId"], "judgeA")
        self.assertEqual(
            judge_a_payload["filters"]["profileId"],
            "panel-judgeA-weighted-v1",
        )
        self.assertTrue(
            all(
                row["judgeId"] == "judgeA"
                and row["profileId"] == "panel-judgeA-weighted-v1"
                for row in judge_a_payload["items"]
            )
        )

        judge_b_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/panels/runtime/profiles"
                "?dispatch_type=final&judge_id=judgeB"
                "&model_strategy=deterministic_path_alignment&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(judge_b_resp.status_code, 200)
        judge_b_payload = judge_b_resp.json()
        self.assertGreaterEqual(judge_b_payload["count"], 1)
        self.assertTrue(
            all(
                row["judgeId"] == "judgeB"
                and row["modelStrategy"] == "deterministic_path_alignment"
                for row in judge_b_payload["items"]
            )
        )

        strategy_slot_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/panels/runtime/profiles"
                "?dispatch_type=final&strategy_slot=path_alignment"
                "&domain_slot=general&sort_by=strategy_slot&sort_order=asc&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(strategy_slot_resp.status_code, 200)
        strategy_slot_payload = strategy_slot_resp.json()
        self.assertGreaterEqual(strategy_slot_payload["count"], 1)
        self.assertEqual(strategy_slot_payload["filters"]["strategySlot"], "path_alignment")
        self.assertEqual(strategy_slot_payload["filters"]["domainSlot"], "general")
        self.assertEqual(strategy_slot_payload["filters"]["sortBy"], "strategy_slot")
        self.assertTrue(
            all(
                row["strategySlot"] == "path_alignment"
                and row["domainSlot"] == "general"
                for row in strategy_slot_payload["items"]
            )
        )

        bad_judge_resp = await self._get(
            app=app,
            path="/internal/judge/panels/runtime/profiles?judge_id=judgeX",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_judge_resp.status_code, 422)
        self.assertIn("invalid_panel_judge_id", bad_judge_resp.text)

        bad_source_resp = await self._get(
            app=app,
            path="/internal/judge/panels/runtime/profiles?profile_source=invalid",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_source_resp.status_code, 422)
        self.assertIn("invalid_panel_profile_source", bad_source_resp.text)

        bad_sort_by_resp = await self._get(
            app=app,
            path="/internal/judge/panels/runtime/profiles?sort_by=unknown",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_sort_by_resp.status_code, 422)
        self.assertIn("invalid_panel_runtime_sort_by", bad_sort_by_resp.text)

        bad_sort_order_resp = await self._get(
            app=app,
            path="/internal/judge/panels/runtime/profiles?sort_order=unknown",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_sort_order_resp.status_code, 422)
        self.assertIn("invalid_panel_runtime_sort_order", bad_sort_order_resp.text)

    async def test_panel_runtime_profile_ops_view_should_return_500_when_contract_validation_fails(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)

        with patch(
            "app.app_factory.validate_panel_runtime_profile_contract_v3",
            side_effect=ValueError("panel_runtime_profile_missing_keys:items"),
        ):
            resp = await self._get(
                app=app,
                path="/internal/judge/panels/runtime/profiles?dispatch_type=final",
                internal_key=runtime.settings.ai_internal_key,
            )

        self.assertEqual(resp.status_code, 500)
        detail = resp.json()["detail"]
        self.assertEqual(detail["code"], "panel_runtime_profile_contract_violation")
        self.assertIn("panel_runtime_profile_missing_keys:items", detail["message"])

    async def test_panel_runtime_readiness_route_should_return_groups_and_simulations(
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
        case_id = _unique_case_id(7871)

        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=_build_phase_request(
                case_id=case_id,
                idempotency_key=f"phase:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)
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

        readiness_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/panels/runtime/readiness"
                "?dispatch_type=final&policy_version=v3-default"
                "&profile_scan_limit=200&group_limit=20&attention_limit=10"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(readiness_resp.status_code, 200)
        payload = readiness_resp.json()

        self.assertIsInstance(payload["overview"], dict)
        self.assertIsInstance(payload["groups"], list)
        self.assertIsInstance(payload["attentionGroups"], list)
        self.assertGreaterEqual(payload["overview"]["totalMatched"], 3)
        self.assertGreaterEqual(payload["overview"]["scannedRecords"], 3)
        self.assertGreaterEqual(payload["overview"]["totalGroups"], 1)
        self.assertIn("readinessCounts", payload["overview"])
        self.assertTrue(any(int(row.get("caseCount") or 0) >= 1 for row in payload["groups"]))

        first_group = payload["groups"][0]
        self.assertIn("recommendedSwitchConditions", first_group)
        self.assertIn("simulations", first_group)
        self.assertIsInstance(first_group["recommendedSwitchConditions"], list)
        self.assertIsInstance(first_group["simulations"], list)
        self.assertTrue(
            all(
                bool(sim.get("advisoryOnly"))
                for sim in first_group["simulations"]
                if isinstance(sim, dict)
            )
        )
        self.assertTrue(
            any(
                "advisory-only" in str(note).lower()
                for note in payload["notes"]
            )
        )
        self.assertEqual(payload["filters"]["dispatchType"], "final")
        self.assertEqual(payload["filters"]["policyVersion"], "v3-default")
        self.assertEqual(payload["filters"]["profileScanLimit"], 200)
        self.assertEqual(payload["filters"]["groupLimit"], 20)
        self.assertEqual(payload["filters"]["attentionLimit"], 10)

    async def test_create_default_app_should_be_constructible(self) -> None:
        app = create_default_app(load_settings_fn=_build_settings)
        self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main()
