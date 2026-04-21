from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.applications.judge_app_domain import (
    JUDGE_WORKFLOW_ROOT_KEY,
    validate_judge_app_domain_payload,
)
from app.applications.judge_trace_summary import build_trace_report_summary
from app.applications.judge_workflow_roles import (
    build_final_judge_workflow_payload,
    build_phase_judge_workflow_payload,
)
from app.models import FinalDispatchRequest, PhaseDispatchMessage, PhaseDispatchRequest


class JudgeWorkflowRolesTests(unittest.TestCase):
    def test_build_phase_judge_workflow_payload_should_pass_contract(self) -> None:
        request = PhaseDispatchRequest(
            case_id=9901,
            scope_id=1,
            session_id=7001,
            phase_no=2,
            message_start_id=11,
            message_end_id=12,
            message_count=2,
            messages=[
                PhaseDispatchMessage(
                    message_id=11,
                    side="pro",
                    content="pro says",
                    created_at=datetime.now(timezone.utc),
                ),
                PhaseDispatchMessage(
                    message_id=12,
                    side="con",
                    content="con says",
                    created_at=datetime.now(timezone.utc),
                ),
            ],
            rubric_version="v3",
            judge_policy_version="v3-default",
            topic_domain="general",
            retrieval_profile="hybrid_v1",
            trace_id="trace-phase-9901",
            idempotency_key="phase:9901:2",
        )
        report_payload = {
            "agent3WeightedScore": {"pro": 66.0, "con": 60.0},
            "agent2Score": {
                "hitItems": ["pro:claim-1"],
                "missItems": ["con:claim-2"],
            },
            "proRetrievalBundle": {"items": [{"chunkId": "c1"}]},
            "conRetrievalBundle": {"items": [{"chunkId": "c2"}]},
        }

        payload = build_phase_judge_workflow_payload(
            request=request,
            report_payload=report_payload,
        )
        self.assertIn(JUDGE_WORKFLOW_ROOT_KEY, payload)
        self.assertEqual(
            payload[JUDGE_WORKFLOW_ROOT_KEY]["caseDossier"]["dispatchType"],
            "phase",
        )
        validate_judge_app_domain_payload(payload)

    def test_build_final_judge_workflow_payload_should_pass_contract(self) -> None:
        request = FinalDispatchRequest(
            case_id=9902,
            scope_id=1,
            session_id=7002,
            phase_start_no=1,
            phase_end_no=2,
            rubric_version="v3",
            judge_policy_version="v3-default",
            topic_domain="general",
            trace_id="trace-final-9902",
            idempotency_key="final:9902:1:2",
        )
        report_payload = {
            "winner": "pro",
            "needsDrawVote": False,
            "reviewRequired": False,
            "claimGraph": {"stats": {"totalClaims": 5}},
            "evidenceLedger": {"entries": [{"evidenceId": "e1"}]},
            "verdictLedger": {
                "panelDecisions": {
                    "topWinner": "pro",
                    "panelDisagreementRatio": 0.12,
                    "judges": {"judgeA": {"winner": "pro"}},
                },
                "arbitration": {
                    "gateDecision": "pass_through",
                    "decisionPath": [
                        "judge_panel",
                        "fairness_sentinel",
                        "chief_arbiter",
                    ],
                },
            },
            "fairnessSummary": {"reviewReasons": []},
            "auditAlerts": [{"alertId": "alert-1"}],
            "phaseRollupSummary": [{"phaseNo": 1, "messageCount": 20}],
            "debateSummary": "debate summary",
            "sideAnalysis": {"pro": "pro", "con": "con"},
            "verdictReason": "reason",
        }

        payload = build_final_judge_workflow_payload(
            request=request,
            report_payload=report_payload,
        )
        self.assertIn(JUDGE_WORKFLOW_ROOT_KEY, payload)
        self.assertEqual(
            payload[JUDGE_WORKFLOW_ROOT_KEY]["caseDossier"]["dispatchType"],
            "final",
        )
        self.assertEqual(
            payload[JUDGE_WORKFLOW_ROOT_KEY]["panelBundle"]["topWinner"],
            "pro",
        )
        validate_judge_app_domain_payload(payload)

    def test_build_final_judge_workflow_payload_should_map_blocked_gate_and_fallback_reasons(
        self,
    ) -> None:
        request = FinalDispatchRequest(
            case_id=9903,
            scope_id=1,
            session_id=7003,
            phase_start_no=1,
            phase_end_no=1,
            rubric_version="v3",
            judge_policy_version="v3-default",
            topic_domain="general",
            trace_id="trace-final-9903",
            idempotency_key="final:9903:1:1",
        )
        report_payload = {
            "winner": "draw",
            "needsDrawVote": True,
            "reviewRequired": True,
            "claimGraph": {"stats": {"totalClaims": 3}},
            "evidenceLedger": {"entries": [{"evidenceId": "e1"}]},
            "verdictLedger": {
                "panelDecisions": {
                    "topWinner": "pro",
                    "panelDisagreementRatio": 0.33,
                    "judges": {"judgeA": {"winner": "pro"}},
                },
                "arbitration": {
                    "gateDecision": "blocked_to_draw",
                    "decisionPath": [
                        "judge_panel",
                        "fairness_sentinel",
                        "chief_arbiter",
                    ],
                },
            },
            "fairnessSummary": {},
            "errorCodes": [
                "judge_panel_high_disagreement",
                "fairness_gate_review_required",
            ],
            "auditAlerts": [{"alertId": "alert-2"}],
            "phaseRollupSummary": [{"phaseNo": 1, "messageCount": 12}],
            "debateSummary": "debate summary",
            "sideAnalysis": {"pro": "pro", "con": "con"},
            "verdictReason": "reason",
        }
        payload = build_final_judge_workflow_payload(
            request=request,
            report_payload=report_payload,
        )
        fairness_gate = payload[JUDGE_WORKFLOW_ROOT_KEY]["fairnessGate"]
        self.assertEqual(fairness_gate["decision"], "blocked_to_draw")
        self.assertEqual(
            fairness_gate["reasons"],
            ["judge_panel_high_disagreement", "fairness_gate_review_required"],
        )
        validate_judge_app_domain_payload(payload)

    def test_trace_role_nodes_should_be_built_from_judge_workflow(self) -> None:
        summary = build_trace_report_summary(
            dispatch_type="final",
            payload={"winner": "pro", "auditAlerts": []},
            callback_status="reported",
            callback_error=None,
            judge_workflow={
                "judgeWorkflow": {
                    "caseDossier": {
                        "caseId": 1,
                        "dispatchType": "final",
                        "roleOrder": [
                            "clerk",
                            "recorder",
                            "claim_graph",
                            "evidence",
                            "panel",
                            "fairness_sentinel",
                            "chief_arbiter",
                            "opinion_writer",
                        ],
                    },
                    "claimGraph": {},
                    "evidenceBundle": {},
                    "panelBundle": {},
                    "fairnessGate": {"decision": "pass_through", "reviewRequired": False},
                    "verdict": {
                        "winner": "pro",
                        "needsDrawVote": False,
                        "reviewRequired": False,
                    },
                    "opinion": {"sideAnalysis": {}},
                }
            },
        )
        self.assertIn("judgeWorkflow", summary)
        self.assertIsInstance(summary["judgeWorkflow"], dict)
        self.assertIn("roleNodes", summary)
        self.assertEqual(len(summary["roleNodes"]), 8)
        self.assertEqual(summary["roleNodes"][0]["role"], "clerk")


if __name__ == "__main__":
    unittest.main()
