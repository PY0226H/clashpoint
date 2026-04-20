from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import datetime, timezone

from app.applications.trust_attestation import attach_report_attestation
from app.applications.trust_phasea_bundle import build_trust_phasea_bundle


@dataclass
class _EventStub:
    event_seq: int
    payload: dict
    created_at: datetime


@dataclass
class _AlertStub:
    alert_id: str
    status: str
    severity: str
    alert_type: str


class TrustPhaseaBundleTests(unittest.TestCase):
    def _build_report_payload(self) -> dict:
        payload = {
            "winner": "pro",
            "proScore": 74.0,
            "conScore": 66.0,
            "degradationLevel": "none",
            "reviewRequired": False,
            "errorCodes": [],
            "judgeTrace": {
                "pipelineVersion": "pipeline-v3",
                "policyRegistry": {"version": "v3-default"},
                "promptRegistry": {"version": "prompt-v3"},
                "toolRegistry": {"version": "toolset-v3"},
                "registryVersions": {
                    "policyVersion": "v3-default",
                    "promptVersion": "prompt-v3",
                    "toolsetVersion": "toolset-v3",
                },
                "agentRuntime": {"runtimeVersion": "agent-runtime-v3"},
            },
            "phaseRollupSummary": {"phaseCount": 3},
            "evidenceLedger": {"pro": [], "con": []},
            "verdictEvidenceRefs": [],
            "retrievalSnapshotRollup": {},
            "claimGraph": {},
            "claimGraphSummary": {},
            "debateSummary": "summary",
            "sideAnalysis": {"pro": "p", "con": "c"},
            "verdictReason": "reason",
            "dimensionScores": [],
            "fairnessSummary": {},
            "auditAlerts": [],
            "sessionId": "room-9601",
        }
        attach_report_attestation(report_payload=payload, dispatch_type="final")
        return payload

    def test_build_trust_phasea_bundle_should_return_stable_keys(self) -> None:
        now = datetime.now(timezone.utc)
        report_payload = self._build_report_payload()
        bundle = build_trust_phasea_bundle(
            case_id=9601,
            dispatch_type="final",
            trace_id="trace-final-9601",
            request_snapshot={"sessionId": "room-9601"},
            report_payload=report_payload,
            workflow_snapshot={
                "caseId": 9601,
                "dispatchType": "final",
                "traceId": "trace-final-9601",
            },
            workflow_status="callback_reported",
            workflow_events=[
                _EventStub(
                    event_seq=1,
                    payload={"judgeCoreVersion": "judge-core-v3"},
                    created_at=now,
                )
            ],
            alerts=[
                _AlertStub(
                    alert_id="alert-1",
                    status="resolved",
                    severity="warning",
                    alert_type="manual_review",
                )
            ],
            provider="mock",
        )
        self.assertTrue(bundle["verifyResult"]["verified"])
        self.assertEqual(bundle["commitment"]["version"], "trust-phaseA-case-commitment-v1")
        self.assertEqual(
            bundle["verdictAttestation"]["version"],
            "trust-phaseA-verdict-attestation-v1",
        )
        self.assertEqual(
            bundle["challengeReview"]["version"],
            "trust-phaseB-challenge-review-v1",
        )
        self.assertEqual(bundle["kernelVersion"]["version"], "trust-phaseA-kernel-version-v1")


if __name__ == "__main__":
    unittest.main()
