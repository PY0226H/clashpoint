from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.applications.judge_app_domain import (
    JUDGE_WORKFLOW_ROOT_KEY,
    validate_judge_app_domain_payload,
)
from app.applications.judge_trace_summary import build_trace_report_summary
from app.applications.judge_workflow_roles import (
    build_case_dossier_enrichment,
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
        dossier = payload[JUDGE_WORKFLOW_ROOT_KEY]["caseDossier"]
        self.assertEqual(dossier["inputValidation"]["status"], "accepted")
        self.assertTrue(dossier["completeness"]["complete"])
        self.assertEqual(dossier["transcriptSnapshot"]["messageIds"], [11, 12])
        self.assertEqual(
            dossier["transcriptSnapshot"]["replyLinks"],
            [
                {
                    "fromMessageId": 12,
                    "toMessageId": 11,
                    "linkType": "reply_to_previous_opponent",
                }
            ],
        )
        claim_graph = payload[JUDGE_WORKFLOW_ROOT_KEY]["claimGraph"]
        self.assertIn("claims", claim_graph)
        self.assertIn("support_edges", claim_graph)
        self.assertIn("rebuttal_edges", claim_graph)
        self.assertIn("unanswered_claims", claim_graph)
        self.assertIn("pivotal_turns", claim_graph)
        evidence_bundle = payload[JUDGE_WORKFLOW_ROOT_KEY]["evidenceBundle"]
        self.assertNotIn("winner", evidence_bundle)
        self.assertIn("message_refs", evidence_bundle)
        self.assertIn("source_citations", evidence_bundle)
        self.assertIn("conflict_sources", evidence_bundle)
        self.assertIn("reliability_notes", evidence_bundle)
        self.assertIn("evidence_sufficiency", evidence_bundle)
        self.assertEqual(evidence_bundle["citationVerification"]["status"], "env_blocked")
        self.assertIn(
            "citation_verifier_real_sample_env_blocked",
            evidence_bundle["citationVerification"]["reasonCodes"],
        )
        dossier_message_ids = set(dossier["transcriptSnapshot"]["messageIds"])
        for ref in evidence_bundle["messageRefs"]:
            self.assertIn(ref["messageId"], dossier_message_ids)
        panel_bundle = payload[JUDGE_WORKFLOW_ROOT_KEY]["panelBundle"]
        self.assertEqual(set(panel_bundle["judges"].keys()), {"logic", "evidence", "rebuttal"})
        self.assertEqual(panel_bundle["topWinner"], "pro")
        self.assertFalse(panel_bundle["agentMeta"]["officialVerdictAuthority"])
        for role, decision in panel_bundle["judges"].items():
            self.assertEqual(decision["role"], role)
            self.assertIn("sideScores", decision)
            self.assertIn("acceptedClaims", decision)
            self.assertFalse(decision["officialVerdictAuthority"])
        fairness_gate = payload[JUDGE_WORKFLOW_ROOT_KEY]["fairnessGate"]
        self.assertEqual(fairness_gate["decision"], "pass_through")
        self.assertTrue(fairness_gate["autoJudgeAllowed"])
        self.assertTrue(fairness_gate["fairnessReport"]["doesNotDecideWinner"])
        self.assertEqual(fairness_gate["citationVerification"]["status"], "env_blocked")
        verdict = payload[JUDGE_WORKFLOW_ROOT_KEY]["verdict"]
        self.assertEqual(
            verdict["decisionPath"],
            ["judge_panel", "fairness_sentinel", "chief_arbiter"],
        )
        self.assertEqual(verdict["gateDecision"], "pass_through")
        self.assertTrue(verdict["agentMeta"]["officialVerdictAuthority"])
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
                    "semanticDecisions": {
                        "logic": {"winner": "pro"},
                        "evidence": {"winner": "pro"},
                        "rebuttal": {"winner": "draw"},
                    },
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
            "fairnessSummary": {
                "reviewReasons": [],
                "autoJudgeAllowed": True,
                "panelHighDisagreement": False,
                "identityLeakage": {"detected": False},
            },
            "auditAlerts": [{"alertId": "alert-1"}],
            "phaseRollupSummary": [
                {"phaseNo": 1, "messageCount": 20},
                {"phaseNo": 2, "messageCount": 18},
            ],
            "opinionPack": {
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
                "userReport": {
                    "winner": "pro",
                    "factSource": "verdict_ledger",
                    "debateSummary": "ledger debate summary",
                    "sideAnalysis": {"pro": "ledger pro", "con": "ledger con"},
                    "verdictReason": "ledger reason",
                },
            },
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
        self.assertTrue(
            payload[JUDGE_WORKFLOW_ROOT_KEY]["caseDossier"]["completeness"]["complete"]
        )
        self.assertEqual(
            payload[JUDGE_WORKFLOW_ROOT_KEY]["caseDossier"]["transcriptSnapshot"][
                "phaseWindows"
            ][0]["messageCount"],
            20,
        )
        self.assertIn("claims", payload[JUDGE_WORKFLOW_ROOT_KEY]["claimGraph"])
        self.assertIn(
            "evidence_sufficiency",
            payload[JUDGE_WORKFLOW_ROOT_KEY]["evidenceBundle"],
        )
        self.assertEqual(
            payload[JUDGE_WORKFLOW_ROOT_KEY]["panelBundle"]["topWinner"],
            "pro",
        )
        self.assertEqual(
            set(payload[JUDGE_WORKFLOW_ROOT_KEY]["panelBundle"]["semanticDecisions"].keys()),
            {"logic", "evidence", "rebuttal"},
        )
        self.assertTrue(payload[JUDGE_WORKFLOW_ROOT_KEY]["fairnessGate"]["autoJudgeAllowed"])
        self.assertTrue(
            payload[JUDGE_WORKFLOW_ROOT_KEY]["verdict"]["agentMeta"][
                "officialVerdictAuthority"
            ]
        )
        self.assertEqual(
            payload[JUDGE_WORKFLOW_ROOT_KEY]["opinion"]["debateSummary"],
            "ledger debate summary",
        )
        self.assertEqual(
            payload[JUDGE_WORKFLOW_ROOT_KEY]["opinion"]["factSource"],
            "verdict_ledger",
        )
        self.assertFalse(
            payload[JUDGE_WORKFLOW_ROOT_KEY]["opinion"]["writesVerdictFacts"]
        )
        validate_judge_app_domain_payload(payload)

    def test_case_dossier_enrichment_should_redact_identity_signals_and_flag_gaps(
        self,
    ) -> None:
        request = PhaseDispatchRequest(
            case_id=9904,
            scope_id=1,
            session_id=7004,
            phase_no=3,
            message_start_id=21,
            message_end_id=23,
            message_count=3,
            messages=[
                PhaseDispatchMessage(
                    message_id=21,
                    side="pro",
                    content="nickname alpha claims the opening point",
                    created_at=datetime.now(timezone.utc),
                ),
                PhaseDispatchMessage(
                    message_id=23,
                    side="con",
                    content="con replies without identity noise",
                    created_at=datetime.now(timezone.utc),
                ),
            ],
            rubric_version="v3",
            judge_policy_version="v3-default",
            topic_domain="general",
            retrieval_profile="hybrid_v1",
            trace_id="trace-phase-9904",
            idempotency_key="phase:9904:3",
        )

        enrichment = build_case_dossier_enrichment(
            request=request,
            dispatch_type="phase",
            report_payload={},
        )

        self.assertEqual(enrichment["inputValidation"]["status"], "blocked")
        self.assertIn(
            "message_window_incomplete",
            enrichment["inputValidation"]["auditReasons"],
        )
        self.assertEqual(enrichment["completeness"]["missingMessageIds"], [22])
        self.assertFalse(enrichment["completeness"]["complete"])
        self.assertEqual(enrichment["redactionSummary"]["semanticRedactionCount"], 1)
        first_digest = enrichment["transcriptSnapshot"]["messageDigest"][0]
        self.assertIn("[REDACTED_IDENTITY_SIGNAL]", first_digest["contentPreview"])
        observed_ids = set(enrichment["transcriptSnapshot"]["messageIds"])
        for link in enrichment["transcriptSnapshot"]["replyLinks"]:
            self.assertIn(link["fromMessageId"], observed_ids)
            self.assertIn(link["toMessageId"], observed_ids)

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
            "opinionPack": {
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
                "userReport": {
                    "winner": "draw",
                    "factSource": "verdict_ledger",
                    "debateSummary": "ledger review summary",
                    "sideAnalysis": {"pro": "ledger pro", "con": "ledger con"},
                    "verdictReason": "ledger review reason",
                },
            },
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
        self.assertFalse(fairness_gate["autoJudgeAllowed"])
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
                    "claimGraph": {
                        "stats": {},
                        "items": [],
                        "unansweredClaimIds": [],
                    },
                    "evidenceBundle": {
                        "entries": [],
                        "sourceCitations": [],
                        "conflictSources": [],
                        "stats": {},
                    },
                    "panelBundle": {
                        "topWinner": "pro",
                        "disagreementRatio": 0.0,
                        "judges": {},
                    },
                    "fairnessGate": {
                        "decision": "pass_through",
                        "reviewRequired": False,
                        "reasons": [],
                        "auditAlertIds": [],
                    },
                    "verdict": {
                        "winner": "pro",
                        "needsDrawVote": False,
                        "reviewRequired": False,
                        "decisionPath": [
                            "judge_panel",
                            "fairness_sentinel",
                            "chief_arbiter",
                        ],
                    },
                    "opinion": {
                        "debateSummary": "",
                        "sideAnalysis": {},
                        "verdictReason": "",
                    },
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
