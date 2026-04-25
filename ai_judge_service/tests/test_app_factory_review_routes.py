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
    build_final_request as _build_final_request,
)
from tests.app_factory_test_helpers import (
    build_settings as _build_settings,
)
from tests.app_factory_test_helpers import (
    unique_case_id as _unique_case_id,
)


class AppFactoryReviewRouteTests(
    AppFactoryRouteTestMixin,
    unittest.IsolatedAsyncioTestCase,
):

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
                    "verdictLedgerLocked": True,
                },
                "pivotalMoments": [],
                "decisiveEvidenceRefs": [],
            },
            "opinionPack": {
                "version": "v2-opinion-pack",
                "sourceContract": {
                    "ownerAgent": "opinion_writer",
                    "inputObjects": [
                        "verdict_ledger",
                        "evidence_ledger",
                        "fairness_report",
                    ],
                    "verdictLedgerLocked": True,
                    "writesVerdictFacts": False,
                    "rawPromptAllowed": False,
                    "failClosed": True,
                    "status": "passed",
                },
                "factLock": {"winner": "draw"},
                "userReport": {
                    "winner": "draw",
                    "factSource": "verdict_ledger",
                    "debateSummary": "summary",
                    "sideAnalysis": {"pro": "pro", "con": "con"},
                    "verdictReason": "reason",
                    "phaseDebateTimeline": [],
                    "evidenceInsightCards": [],
                },
                "opsSummary": {"reviewRequired": True, "sourceContractStatus": "passed"},
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
                        "verdictLedgerLocked": True,
                    },
                    "pivotalMoments": [],
                    "decisiveEvidenceRefs": [],
                },
                "opinionPack": {
                    "version": "v2-opinion-pack",
                    "sourceContract": {
                        "ownerAgent": "opinion_writer",
                        "inputObjects": [
                            "verdict_ledger",
                            "evidence_ledger",
                            "fairness_report",
                        ],
                        "verdictLedgerLocked": True,
                        "writesVerdictFacts": False,
                        "rawPromptAllowed": False,
                        "failClosed": True,
                        "status": "passed",
                    },
                    "factLock": {"winner": "draw"},
                    "userReport": {
                        "winner": "draw",
                        "factSource": "verdict_ledger",
                        "debateSummary": "summary",
                        "sideAnalysis": {"pro": "pro", "con": "con"},
                        "verdictReason": "reason",
                        "phaseDebateTimeline": [],
                        "evidenceInsightCards": [],
                    },
                    "opsSummary": {"reviewRequired": True, "sourceContractStatus": "passed"},
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
        self.assertEqual(item["trustChallenge"]["state"], "under_internal_review")
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

if __name__ == "__main__":
    unittest.main()
