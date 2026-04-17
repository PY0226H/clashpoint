import copy
import unittest

from app.applications.trust_attestation import (
    attach_report_attestation,
    build_report_attestation,
    verify_report_attestation,
)


class TrustAttestationTests(unittest.TestCase):
    def _build_phase_payload(self) -> dict:
        return {
            "sessionId": 2,
            "phaseNo": 1,
            "messageStartId": 1,
            "messageEndId": 2,
            "messageCount": 2,
            "proSummaryGrounded": "pro summary",
            "conSummaryGrounded": "con summary",
            "proRetrievalBundle": [{"id": "p1"}],
            "conRetrievalBundle": [{"id": "c1"}],
            "agent1Score": {"pro": 60, "con": 40},
            "agent2Score": {"pro": 58, "con": 42},
            "agent3WeightedScore": {"pro": 59.3, "con": 40.7},
            "judgePolicyVersion": "v3-default",
            "rubricVersion": "v3",
            "judgeTrace": {"policyRegistry": {"version": "v3-default"}},
        }

    def _build_final_payload(self) -> dict:
        return {
            "sessionId": 2,
            "phaseRollupSummary": [{"phaseNo": 1}],
            "verdictEvidenceRefs": [{"evidenceId": "ev1"}],
            "evidenceLedger": {
                "pipelineVersion": "v3-evidence-bundle",
                "entries": [{"evidenceId": "ev1", "kind": "message_ref", "phaseNo": 1, "side": "pro"}],
                "refsById": {"ev1": {"index": 0, "kind": "message_ref", "phaseNo": 1, "side": "pro"}},
                "messageRefs": [{"evidenceId": "ev1", "messageId": 1}],
                "sourceCitations": [],
                "conflictSources": [],
                "stats": {
                    "totalEntries": 1,
                    "messageRefCount": 1,
                    "sourceCitationCount": 0,
                    "conflictSourceCount": 0,
                    "verdictReferencedCount": 1,
                },
                "bundleMeta": {
                    "kind": "evidence_bundle",
                    "ownerAgent": "evidence_agent",
                    "decisionAuthority": "non_verdict",
                    "officialVerdictAuthority": False,
                },
            },
            "retrievalSnapshotRollup": [{"phaseNo": 1, "sources": 1}],
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
            "winner": "pro",
            "proScore": 61.2,
            "conScore": 58.9,
            "dimensionScores": {"logic": 62, "evidence": 60},
            "debateSummary": "summary",
            "sideAnalysis": {"pro": "pro", "con": "con"},
            "verdictReason": "reason",
            "rejudgeTriggered": False,
            "needsDrawVote": False,
            "fairnessSummary": {"reviewRequired": False},
            "auditAlerts": [],
            "errorCodes": [],
            "degradationLevel": 0,
            "judgePolicyVersion": "v3-default",
            "rubricVersion": "v3",
            "judgeTrace": {"policyRegistry": {"version": "v3-default"}},
        }

    def test_build_report_attestation_should_return_final_contract(self) -> None:
        payload = self._build_final_payload()
        attestation = build_report_attestation(
            report_payload=payload,
            dispatch_type="final",
        )
        self.assertEqual(attestation["version"], "trust-attestation-v1")
        self.assertEqual(attestation["dispatchType"], "final")
        self.assertEqual(attestation["algorithm"], "sha256")
        self.assertIn("componentHashes", attestation)
        self.assertIn("commitmentHash", attestation)
        self.assertIn("verdictHash", attestation["componentHashes"])
        self.assertIn("claimGraphHash", attestation["componentHashes"])

    def test_attach_and_verify_should_pass_for_original_payload(self) -> None:
        payload = self._build_phase_payload()
        attach_report_attestation(report_payload=payload, dispatch_type="phase")
        verify = verify_report_attestation(report_payload=payload, dispatch_type="phase")
        self.assertTrue(verify["verified"])
        self.assertEqual(verify["reason"], "ok")
        self.assertEqual(verify["mismatchComponents"], [])

    def test_verify_should_fail_when_payload_tampered(self) -> None:
        payload = self._build_final_payload()
        attach_report_attestation(report_payload=payload, dispatch_type="final")
        tampered = copy.deepcopy(payload)
        tampered["winner"] = "draw"
        verify = verify_report_attestation(report_payload=tampered, dispatch_type="final")
        self.assertFalse(verify["verified"])
        self.assertEqual(verify["reason"], "trust_attestation_mismatch")
        self.assertIn("verdictHash", verify["mismatchComponents"])

    def test_verify_should_fail_when_attestation_missing(self) -> None:
        payload = self._build_phase_payload()
        verify = verify_report_attestation(report_payload=payload, dispatch_type="phase")
        self.assertFalse(verify["verified"])
        self.assertEqual(verify["reason"], "trust_attestation_missing")
        self.assertIsNone(verify["actual"])


if __name__ == "__main__":
    unittest.main()
