import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from app.applications.trust_phasea import (
    build_audit_anchor_export,
    build_case_commitment_registry,
    build_challenge_review_registry,
    build_judge_kernel_registry,
    build_verdict_attestation_registry,
)


def _event(*, seq: int, payload: dict, created_at: datetime | None = None):
    return SimpleNamespace(
        event_seq=seq,
        payload=payload,
        created_at=created_at or datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def _alert(
    *,
    alert_id: str,
    alert_type: str,
    status: str,
    severity: str,
):
    return SimpleNamespace(
        alert_id=alert_id,
        alert_type=alert_type,
        status=status,
        severity=severity,
    )


class TrustPhaseATests(unittest.TestCase):
    def test_case_commitment_should_build_stable_hash(self) -> None:
        payload = {
            "winner": "pro",
            "proScore": 61.2,
            "conScore": 58.9,
            "degradationLevel": 0,
            "trustAttestation": {"commitmentHash": "att-commit-1"},
        }
        first = build_case_commitment_registry(
            case_id=9001,
            dispatch_type="auto",
            trace_id="trace-9001",
            request_snapshot={"caseId": 9001, "foo": "bar"},
            workflow_snapshot={"status": "callback_reported"},
            report_payload=payload,
        )
        second = build_case_commitment_registry(
            case_id=9001,
            dispatch_type="auto",
            trace_id="trace-9001",
            request_snapshot={"caseId": 9001, "foo": "bar"},
            workflow_snapshot={"status": "callback_reported"},
            report_payload=payload,
        )
        self.assertEqual(first["dispatchType"], "unknown")
        self.assertEqual(first["attestationCommitmentHash"], "att-commit-1")
        self.assertEqual(first["commitmentHash"], second["commitmentHash"])

    def test_verdict_attestation_registry_should_normalize_verify_result(self) -> None:
        registry = build_verdict_attestation_registry(
            case_id=9002,
            dispatch_type="final",
            trace_id="trace-9002",
            report_payload={
                "trustAttestation": {"version": "trust-attestation-v1", "commitmentHash": "c1"},
            },
            verify_result={
                "verified": False,
                "reason": "trust_attestation_mismatch",
                "mismatchComponents": [" verdictHash ", "claimGraphHash", ""],
            },
        )
        self.assertEqual(registry["dispatchType"], "final")
        self.assertFalse(registry["verified"])
        self.assertEqual(registry["reason"], "trust_attestation_mismatch")
        self.assertEqual(registry["mismatchComponents"], ["verdictHash", "claimGraphHash"])
        self.assertIn("registryHash", registry)

    def test_challenge_review_registry_should_track_pending_and_open_alerts(self) -> None:
        registry = build_challenge_review_registry(
            case_id=9003,
            trace_id="trace-9003",
            workflow_status="review_required",
            workflow_events=[_event(seq=1, payload={"eventType": "review_required"})],
            alerts=[
                _alert(
                    alert_id="A1",
                    alert_type="fairness_gate_review_required",
                    status="raised",
                    severity="critical",
                ),
                _alert(
                    alert_id="A2",
                    alert_type="style_shift_instability",
                    status="acked",
                    severity="warning",
                ),
                _alert(
                    alert_id="A3",
                    alert_type="manual_verification",
                    status="resolved",
                    severity="critical",
                ),
            ],
            report_payload={
                "reviewRequired": True,
                "errorCodes": ["fairness_gate_review_required", "manual_check"],
            },
        )
        self.assertEqual(registry["reviewState"], "pending_review")
        self.assertEqual(registry["alertSummary"]["total"], 3)
        self.assertEqual(registry["alertSummary"]["raised"], 1)
        self.assertEqual(registry["alertSummary"]["acked"], 1)
        self.assertEqual(registry["alertSummary"]["resolved"], 1)
        self.assertEqual(registry["alertSummary"]["critical"], 2)
        self.assertEqual(registry["alertSummary"]["warning"], 1)
        self.assertEqual(registry["openAlertIds"], ["A1", "A2"])
        self.assertIn("manual_check", registry["challengeReasons"])
        self.assertIn("style_shift_instability", registry["challengeReasons"])
        self.assertIn("registryHash", registry)

    def test_judge_kernel_registry_should_resolve_latest_core_and_registry_versions(self) -> None:
        registry = build_judge_kernel_registry(
            case_id=9004,
            dispatch_type="final",
            trace_id="trace-9004",
            report_payload={
                "judgeTrace": {
                    "pipelineVersion": "pipeline-v2",
                    "registryVersions": {
                        "policyVersion": "policy-v5",
                        "promptVersion": "prompt-v5",
                        "toolsetVersion": "toolset-v5",
                    },
                    "agentRuntime": {"runtimeVersion": "agent-runtime-v3"},
                }
            },
            workflow_events=[
                _event(seq=1, payload={"judgeCoreVersion": "v0.9"}),
                _event(seq=2, payload={"judgeCoreVersion": ""}),
                _event(seq=3, payload={"judgeCoreVersion": "v1.2"}),
            ],
            provider="openai",
        )
        kernel = registry["kernelVector"]
        self.assertEqual(kernel["dispatchType"], "final")
        self.assertEqual(kernel["provider"], "openai")
        self.assertEqual(kernel["judgeCoreVersion"], "v1.2")
        self.assertEqual(kernel["pipelineVersion"], "pipeline-v2")
        self.assertEqual(kernel["policyVersion"], "policy-v5")
        self.assertEqual(kernel["promptVersion"], "prompt-v5")
        self.assertEqual(kernel["toolsetVersion"], "toolset-v5")
        self.assertEqual(kernel["agentRuntimeVersion"], "agent-runtime-v3")
        self.assertIn("kernelHash", registry)
        self.assertIn("registryHash", registry)

    def test_audit_anchor_export_should_include_optional_payload(self) -> None:
        commitment = {"commitmentHash": "commit-h1"}
        attestation = {"registryHash": "attest-r1"}
        challenge = {"registryHash": "challenge-r1"}
        kernel = {"registryHash": "kernel-r1"}

        anchor_without_payload = build_audit_anchor_export(
            case_id=9005,
            dispatch_type="final",
            trace_id="trace-9005",
            case_commitment=commitment,
            verdict_attestation=attestation,
            challenge_review=challenge,
            kernel_version=kernel,
            include_payload=False,
        )
        self.assertEqual(anchor_without_payload["dispatchType"], "final")
        self.assertNotIn("payload", anchor_without_payload)
        self.assertEqual(anchor_without_payload["componentHashes"]["caseCommitmentHash"], "commit-h1")
        self.assertEqual(anchor_without_payload["componentHashes"]["verdictAttestationHash"], "attest-r1")
        self.assertEqual(anchor_without_payload["componentHashes"]["challengeReviewHash"], "challenge-r1")
        self.assertEqual(anchor_without_payload["componentHashes"]["kernelVersionHash"], "kernel-r1")

        anchor_with_payload = build_audit_anchor_export(
            case_id=9005,
            dispatch_type="final",
            trace_id="trace-9005",
            case_commitment=commitment,
            verdict_attestation=attestation,
            challenge_review=challenge,
            kernel_version=kernel,
            include_payload=True,
        )
        self.assertIn("payload", anchor_with_payload)
        self.assertIn("anchorHash", anchor_with_payload)
        self.assertEqual(
            anchor_with_payload["payload"]["caseCommitment"]["commitmentHash"],
            "commit-h1",
        )


if __name__ == "__main__":
    unittest.main()
