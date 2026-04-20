from __future__ import annotations

import unittest

from app.applications.trust_ops_views import (
    build_public_trust_verify_payload,
    build_trust_challenge_ops_queue_item,
    build_trust_challenge_ops_queue_payload,
)


class TrustOpsViewsTests(unittest.TestCase):
    def test_build_public_trust_verify_payload_should_keep_public_fields_only(self) -> None:
        payload = build_public_trust_verify_payload(
            commitment={
                "version": "trust-phaseA-case-commitment-v1",
                "commitmentHash": "c_hash",
                "requestHash": "r_hash",
                "workflowHash": "w_hash",
                "reportHash": "rp_hash",
                "attestationCommitmentHash": "a_hash",
            },
            verdict_attestation={
                "version": "trust-phaseA-verdict-attestation-v1",
                "registryHash": "va_hash",
                "verified": True,
                "reason": "ok",
                "mismatchComponents": [],
                "attestation": {
                    "commitmentHash": "att_c",
                    "verdictHash": "att_v",
                    "auditHash": "att_a",
                },
            },
            challenge_review={
                "version": "trust-phaseB-challenge-review-v1",
                "registryHash": "cr_hash",
                "reviewState": "approved",
                "reviewRequired": False,
                "challengeState": "not_challenged",
                "activeChallengeId": None,
                "totalChallenges": 0,
                "alertSummary": {},
                "challengeReasons": [],
                "timeline": [{"eventSeq": 1}],
                "openAlertIds": ["alert-1"],
            },
            kernel_version={
                "version": "trust-phaseA-kernel-version-v1",
                "registryHash": "kv_hash",
                "kernelHash": "k_hash",
                "kernelVector": {"judgeCoreVersion": "judge-core-v3"},
            },
            audit_anchor={
                "version": "trust-phaseA-audit-anchor-v1",
                "anchorHash": "a_hash",
                "componentHashes": {"caseCommitmentHash": "c_hash"},
                "payload": {"should_not": "appear"},
            },
        )

        self.assertIn("attestationHashes", payload["verdictAttestation"])
        self.assertNotIn("attestation", payload["verdictAttestation"])
        self.assertNotIn("timeline", payload["challengeReview"])
        self.assertNotIn("openAlertIds", payload["challengeReview"])
        self.assertNotIn("payload", payload["auditAnchor"])

    def test_build_trust_challenge_ops_queue_item_and_payload_should_build_stable_shape(self) -> None:
        item = build_trust_challenge_ops_queue_item(
            case_id=9301,
            dispatch_type="final",
            trace_id="trace-final-9301",
            workflow={
                "caseId": 9301,
                "dispatchType": "final",
                "traceId": "trace-final-9301",
                "status": "review_required",
                "scopeId": "9301",
                "sessionId": "room-9301",
                "idempotencyKey": "final:9301",
                "rubricVersion": "v1",
                "judgePolicyVersion": "v3-default",
                "topicDomain": "general",
                "retrievalProfile": "default",
                "createdAt": "2026-04-20T00:00:00Z",
                "updatedAt": "2026-04-20T00:10:00Z",
            },
            trace_payload={
                "status": "success",
                "callbackStatus": "reported",
                "callbackError": None,
                "updatedAt": "2026-04-20T00:10:00Z",
            },
            challenge_review={
                "challengeState": "under_review",
                "activeChallengeId": "chlg-9301-aaaa",
                "totalChallenges": 1,
                "reviewState": "pending_review",
                "reviewRequired": True,
                "challengeReasons": ["manual_challenge"],
                "alertSummary": {"critical": 0},
                "openAlertIds": [],
                "timeline": [],
            },
            priority_profile={
                "score": 55,
                "level": "medium",
                "tags": ["open_challenge"],
                "ageMinutes": 20,
                "slaBucket": "normal",
                "challengeState": "under_review",
                "reviewState": "pending_review",
                "reviewRequired": True,
                "totalChallenges": 1,
                "openAlertCount": 0,
            },
            active_challenge_id="chlg-9301-aaaa",
        )
        self.assertEqual(item["caseId"], 9301)
        self.assertEqual(item["review"]["workflowStatus"], "review_required")
        self.assertEqual(item["actionPaths"]["reviewDetailPath"], "/internal/judge/review/cases/9301")

        payload = build_trust_challenge_ops_queue_payload(
            items=[item],
            page_items=[item],
            jobs_count=2,
            errors=[{"caseId": 9302, "statusCode": 404, "errorCode": "trust_receipt_not_found"}],
            filters={
                "status": None,
                "dispatchType": "auto",
                "challengeState": "open",
                "reviewState": None,
                "priorityLevel": None,
                "slaBucket": None,
                "hasOpenAlert": None,
                "sortBy": "priority_score",
                "sortOrder": "desc",
                "scanLimit": 500,
                "offset": 0,
                "limit": 50,
            },
        )
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["returned"], 1)
        self.assertEqual(payload["scanned"], 2)
        self.assertEqual(payload["skipped"], 1)
        self.assertEqual(payload["errorCount"], 1)


if __name__ == "__main__":
    unittest.main()
