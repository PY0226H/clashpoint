import unittest
from datetime import datetime, timezone

from app.models import (
    CaseCreateRequest,
    FinalDispatchRequest,
    FinalReportInput,
    PhaseDispatchRequest,
    PhaseReportInput,
)


class PhaseFinalContractModelsTests(unittest.TestCase):
    def test_case_create_request_should_parse_required_fields(self) -> None:
        payload = {
            "case_id": 1201,
            "scope_id": 1,
            "session_id": 2001,
            "rubric_version": "v3",
            "judge_policy_version": "v3-default",
            "topic_domain": "tft",
            "retrieval_profile": "hybrid_v1",
            "trace_id": "trace-case-1201",
            "idempotency_key": "judge_case:1201",
        }
        req = CaseCreateRequest.model_validate(payload)
        self.assertEqual(req.case_id, 1201)
        self.assertEqual(req.scope_id, 1)
        self.assertEqual(req.trace_id, "trace-case-1201")

    def test_phase_dispatch_request_should_parse_required_fields(self) -> None:
        now = datetime.now(timezone.utc)
        payload = {
            "case_id": 1001,
            "scope_id": 1,
            "session_id": 2001,
            "phase_no": 3,
            "message_start_id": 301,
            "message_end_id": 400,
            "message_count": 100,
            "messages": [
                {
                    "message_id": 301,
                    "side": "pro",
                    "content": "观点A",
                    "created_at": now.isoformat(),
                    "speaker_tag": "pro_1",
                },
                {
                    "message_id": 302,
                    "side": "con",
                    "content": "反驳A",
                    "created_at": now.isoformat(),
                },
            ],
            "rubric_version": "v3",
            "judge_policy_version": "v3-default",
            "topic_domain": "tft",
            "retrieval_profile": "hybrid_v1",
            "trace_id": "trace-1",
            "idempotency_key": "judge_phase:2001:3:v3:v3-default",
        }
        req = PhaseDispatchRequest.model_validate(payload)
        self.assertEqual(req.phase_no, 3)
        self.assertEqual(req.message_count, 100)
        self.assertEqual(len(req.messages), 2)
        self.assertEqual(req.messages[0].side, "pro")

    def test_final_dispatch_request_should_parse_required_fields(self) -> None:
        payload = {
            "case_id": 1002,
            "scope_id": 1,
            "session_id": 2001,
            "phase_start_no": 1,
            "phase_end_no": 8,
            "rubric_version": "v3",
            "judge_policy_version": "v3-default",
            "topic_domain": "tft",
            "trace_id": "trace-2",
            "idempotency_key": "judge_final:2001:1:8:v3:v3-default",
        }
        req = FinalDispatchRequest.model_validate(payload)
        self.assertEqual(req.phase_start_no, 1)
        self.assertEqual(req.phase_end_no, 8)

    def test_phase_report_input_should_require_nested_payloads(self) -> None:
        payload = {
            "session_id": 2001,
            "phase_no": 3,
            "message_start_id": 301,
            "message_end_id": 400,
            "message_count": 100,
            "pro_summary_grounded": {"text": "正方总结", "message_ids": [301, 305]},
            "con_summary_grounded": {"text": "反方总结", "message_ids": [302, 306]},
            "pro_retrieval_bundle": {
                "queries": ["query-a"],
                "items": [
                    {
                        "chunk_id": "c1",
                        "title": "知识1",
                        "source_url": "https://teamfighttactics.leagueoflegends.com/en-us/news/x",
                        "score": 0.8,
                        "snippet": "内容1",
                    }
                ],
            },
            "con_retrieval_bundle": {"queries": ["query-b"], "items": []},
            "agent1_score": {
                "pro": 66.0,
                "con": 64.0,
                "dimensions": {"logic": 70},
                "rationale": "agent1 rationale",
            },
            "agent2_score": {
                "pro": 68.0,
                "con": 62.0,
                "hit_items": ["h1"],
                "miss_items": ["m1"],
                "rationale": "agent2 rationale",
            },
            "agent3_weighted_score": {"pro": 67.3, "con": 62.7, "w1": 0.35, "w2": 0.65},
            "prompt_hashes": {"a2": "hash-a2"},
            "token_usage": {"total": 1024},
            "latency_ms": {"total": 1800},
            "error_codes": [],
            "degradation_level": 0,
            "judge_trace": {"traceId": "trace-3"},
        }
        report = PhaseReportInput.model_validate(payload)
        self.assertEqual(report.agent3_weighted_score.w2, 0.65)
        self.assertEqual(report.pro_retrieval_bundle.items[0].chunk_id, "c1")

    def test_final_report_input_should_support_pro_con_draw(self) -> None:
        payload = {
            "session_id": 2001,
            "winner": "draw",
            "pro_score": 71.5,
            "con_score": 71.5,
            "dimension_scores": {
                "logic": 72.0,
                "evidence": 70.0,
                "rebuttal": 73.0,
                "clarity": 71.0,
            },
            "debate_summary": "终局摘要",
            "side_analysis": {
                "pro": "正方优势",
                "con": "反方优势",
            },
            "verdict_reason": "裁决理由",
            "claim_graph": {
                "pipelineVersion": "v1-claim-graph-bootstrap",
                "nodes": [],
                "edges": [],
                "unansweredClaimIds": [],
                "stats": {"totalClaims": 0},
            },
            "claim_graph_summary": {
                "coreClaims": {"pro": [], "con": []},
                "stats": {"totalClaims": 0},
            },
            "evidence_ledger": {
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
            "verdict_ledger": {
                "version": "v2-panel-arbiter-opinion",
                "scoreCard": {"proScore": 71.5, "conScore": 71.5, "dimensionScores": {"logic": 72.0}},
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
            "opinion_pack": {
                "version": "v2-opinion-pack",
                "userReport": {"winner": "draw", "debateSummary": "终局摘要"},
                "opsSummary": {"reviewRequired": True},
                "internalReview": {"traceId": "trace-4"},
            },
            "verdict_evidence_refs": [{"messageId": 3001}],
            "phase_rollup_summary": [{"phaseNo": 1}],
            "retrieval_snapshot_rollup": [{"chunkId": "c-1"}],
            "winner_first": "pro",
            "winner_second": "con",
            "rejudge_triggered": True,
            "needs_draw_vote": True,
            "review_required": True,
            "judge_trace": {"traceId": "trace-4"},
            "audit_alerts": [{"type": "consistency_conflict"}],
            "error_codes": ["consistency_conflict"],
            "degradation_level": 1,
        }
        report = FinalReportInput.model_validate(payload)
        self.assertEqual(report.winner, "draw")
        self.assertTrue(report.rejudge_triggered)
        self.assertIn("stats", report.claim_graph_summary)
        self.assertIn("stats", report.evidence_ledger)
        self.assertIn("scoreCard", report.verdict_ledger)
        self.assertIn("userReport", report.opinion_pack)


if __name__ == "__main__":
    unittest.main()
