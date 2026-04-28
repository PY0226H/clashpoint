from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.applications.fairness_calibration_decision_log import (
    FAIRNESS_CALIBRATION_DECISION_LOG_VERSION,
    InMemoryFairnessCalibrationDecisionLogStore,
    build_fairness_calibration_decision_create_payload,
    build_fairness_calibration_decision_list_payload,
    build_fairness_calibration_decision_log_entry,
)


class FairnessCalibrationDecisionLogTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_and_list_should_keep_local_reference_out_of_production_ready(
        self,
    ) -> None:
        store = InMemoryFairnessCalibrationDecisionLogStore()
        now = datetime(2026, 4, 28, 12, 0, tzinfo=timezone.utc)

        payload = await build_fairness_calibration_decision_create_payload(
            raw_payload={
                "decisionId": "decision-local-1",
                "sourceRecommendationId": "run_shadow_evaluation",
                "policyVersion": "v3-default",
                "decision": "accept_for_review",
                "actor": {"id": "ops-user-1", "type": "ai_ops"},
                "reasonCode": "calibration_local_reference_only",
                "environmentMode": "local_reference",
                "evidenceRefs": [
                    {
                        "kind": "benchmark_summary",
                        "ref": "bench-1",
                        "status": "local_reference_frozen",
                    }
                ],
            },
            store=store,
            now=now,
        )

        self.assertEqual(payload["version"], FAIRNESS_CALIBRATION_DECISION_LOG_VERSION)
        entry = payload["entry"]
        self.assertEqual(entry["decision"], "accept_for_review")
        self.assertFalse(entry["releaseGateInput"]["eligibleForProductionReady"])
        self.assertTrue(entry["releaseGateInput"]["blocksProductionReady"])
        self.assertTrue(entry["releaseGateInput"]["localReferenceOnly"])
        self.assertFalse(entry["visibility"]["autoActivateAllowed"])
        self.assertFalse(entry["visibility"]["officialVerdictSemanticsChanged"])

        listed = await build_fairness_calibration_decision_list_payload(
            store=store,
            policy_version="v3-default",
            source_recommendation_id=None,
            decision=None,
            limit=10,
            now=now,
        )

        self.assertEqual(listed["summary"]["totalCount"], 1)
        self.assertEqual(listed["summary"]["acceptedForReviewCount"], 1)
        self.assertEqual(listed["summary"]["localReferenceOnlyCount"], 1)
        self.assertEqual(listed["summary"]["productionReadyDecisionCount"], 0)
        self.assertEqual(
            listed["releaseGateReference"]["blockingDecisionCount"],
            1,
        )
        self.assertFalse(listed["releaseGateReference"]["autoPublishAllowed"])

    def test_accept_for_review_should_be_release_gate_input_but_not_auto_apply(
        self,
    ) -> None:
        entry = build_fairness_calibration_decision_log_entry(
            {
                "decisionId": "decision-real-1",
                "sourceRecommendationId": "publish_candidate_policy",
                "policyVersion": "v3-default",
                "decision": "accept_for_review",
                "actor": "ops-user-1",
                "reasonCode": "calibration_release_gate_blocked",
                "evidenceRefs": ["release-gate-snapshot-1"],
            },
            now=datetime(2026, 4, 28, 12, 0, tzinfo=timezone.utc),
        )

        self.assertTrue(entry["releaseGateInput"]["eligibleForProductionReady"])
        self.assertFalse(entry["releaseGateInput"]["autoPublishAllowed"])
        self.assertFalse(entry["releaseGateInput"]["autoActivateAllowed"])
        self.assertFalse(entry["releaseGateInput"]["officialVerdictSemanticsChanged"])

    def test_local_reference_should_reject_requested_production_ready(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "calibration_local_reference_cannot_be_production_ready",
        ):
            build_fairness_calibration_decision_log_entry(
                {
                    "sourceRecommendationId": "run_shadow_evaluation",
                    "policyVersion": "v3-default",
                    "decision": "accept_for_review",
                    "actor": "ops-user-1",
                    "reasonCode": "calibration_local_reference_only",
                    "environmentMode": "local_reference",
                    "productionReady": True,
                }
            )

    def test_payload_should_reject_forbidden_internal_fields(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "calibration_decision_forbidden_key",
        ):
            build_fairness_calibration_decision_log_entry(
                {
                    "sourceRecommendationId": "run_shadow_evaluation",
                    "policyVersion": "v3-default",
                    "decision": "request_more_evidence",
                    "actor": "ops-user-1",
                    "reasonCode": "calibration_real_samples_missing",
                    "rawTrace": {"provider": "hidden"},
                }
            )

    def test_payload_should_reject_auto_apply_requests(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "calibration_decision_auto_apply_forbidden",
        ):
            build_fairness_calibration_decision_log_entry(
                {
                    "sourceRecommendationId": "publish_candidate_policy",
                    "policyVersion": "v3-default",
                    "decision": "accept_for_review",
                    "actor": "ops-user-1",
                    "reasonCode": "calibration_release_gate_blocked",
                    "autoActivate": True,
                }
            )
