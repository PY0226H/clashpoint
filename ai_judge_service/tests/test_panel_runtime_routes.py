from __future__ import annotations

import unittest

from app.applications.panel_runtime_routes import (
    PanelRuntimeRouteError,
    build_panel_runtime_readiness_summary,
    build_panel_shadow_evaluation,
    normalize_panel_runtime_profile_query,
)


class PanelRuntimeRoutesTests(unittest.TestCase):
    def test_build_panel_shadow_evaluation_should_emit_blocking_drift_signal(
        self,
    ) -> None:
        payload = build_panel_shadow_evaluation(
            case_item={
                "shadowSummary": {
                    "benchmarkRunId": "shadow-run-v1",
                    "latestRun": {
                        "runId": "shadow-run-v1",
                        "metrics": {"winnerFlipRate": 0.2},
                    },
                    "hasShadowBreach": True,
                    "breaches": ["winner_flip_rate", "winner_flip_rate"],
                },
                "panelDisagreement": {"high": True},
            },
            runtime_profile={
                "shadowEnabled": True,
                "shadowModelStrategy": "shadow_tri_panel_v1",
                "shadowCostEstimate": "0.031",
                "shadowLatencyEstimate": "1450",
            },
            model_strategy="deterministic_weighted",
        )

        self.assertTrue(payload["enabled"])
        self.assertEqual(payload["modelStrategy"], "shadow_tri_panel_v1")
        self.assertEqual(payload["decisionAgreement"], 0.8)
        self.assertEqual(payload["costEstimate"], 0.031)
        self.assertEqual(payload["latencyEstimate"], 1450.0)
        self.assertEqual(
            payload["driftSignals"],
            ["winner_flip_rate", "shadow_breach", "panel_high_disagreement"],
        )
        self.assertEqual(payload["releaseGateSignal"]["status"], "blocked")
        self.assertTrue(payload["releaseGateSignal"]["blocksAutoRelease"])
        self.assertFalse(payload["officialWinnerMutationAllowed"])
        self.assertTrue(payload["advisoryOnly"])

    def test_build_panel_shadow_evaluation_should_watch_enabled_missing_run(
        self,
    ) -> None:
        payload = build_panel_shadow_evaluation(
            case_item={"shadowSummary": {}, "panelDisagreement": {"high": False}},
            runtime_profile={
                "strategyMetadata": {
                    "shadowEnabled": True,
                    "shadowModelStrategy": "shadow_watch_v1",
                }
            },
            model_strategy="deterministic_weighted",
        )

        self.assertTrue(payload["enabled"])
        self.assertEqual(payload["decisionAgreement"], 0.0)
        self.assertEqual(payload["driftSignals"], ["shadow_run_missing"])
        self.assertEqual(payload["releaseGateSignal"]["status"], "watch")
        self.assertFalse(payload["releaseGateSignal"]["blocksAutoRelease"])

    def test_build_panel_runtime_readiness_summary_should_emit_candidate_contract(
        self,
    ) -> None:
        items = [
            {
                "caseId": 7001,
                "judgeId": "judgeA",
                "profileSource": "trace",
                "strategySlot": "path_alignment",
                "domainSlot": "general",
                "modelStrategy": "weighted_panel",
                "profileId": "profile-a",
                "policyVersion": "v3-default",
                "candidateModels": ["candidate-a"],
                "adaptiveEnabled": False,
                "reviewRequired": False,
                "hasOpenReview": False,
                "panelDisagreement": {"high": False, "ratio": 0.0},
                "shadowEnabled": True,
                "shadowDriftSignals": [],
                "shadowDecisionAgreement": 0.91,
                "shadowCostEstimate": 0.02,
                "shadowLatencyEstimate": 900.0,
                "shadowReleaseGateSignal": {"status": "watch"},
            }
        ]

        payload = build_panel_runtime_readiness_summary(
            items=items,
            group_limit=10,
            attention_limit=5,
        )

        group = payload["groups"][0]
        self.assertEqual(group["candidateModelCount"], 1)
        self.assertEqual(group["switchBlockers"], ["real_samples_missing"])
        self.assertEqual(group["releaseGateSignals"]["status"], "watch")
        self.assertFalse(group["releaseGateSignals"]["autoSwitchAllowed"])
        self.assertFalse(group["releaseGateSignals"]["officialWinnerSemanticsChanged"])
        self.assertEqual(payload["overview"]["shadow"]["candidateModelGroupCount"], 1)
        self.assertEqual(
            payload["overview"]["shadow"]["switchBlockerCounts"]["real_samples_missing"],
            1,
        )

    def test_normalize_panel_runtime_profile_query_should_raise_for_invalid_judge_id(
        self,
    ) -> None:
        with self.assertRaises(PanelRuntimeRouteError) as ctx:
            normalize_panel_runtime_profile_query(
                status=None,
                dispatch_type="final",
                winner=None,
                policy_version=None,
                gate_conclusion=None,
                challenge_state=None,
                judge_id="judgeX",
                profile_source=None,
                profile_id=None,
                model_strategy=None,
                strategy_slot=None,
                domain_slot=None,
                sort_by="updated_at",
                sort_order="desc",
                offset=0,
                limit=20,
                panel_judge_ids=("judgeA", "judgeB", "judgeC"),
                panel_runtime_profile_source_values={"trace", "override"},
                panel_runtime_profile_sort_fields={"updated_at", "case_id"},
                normalize_workflow_status=lambda value: value,
                normalize_panel_runtime_profile_source=lambda value: value,
                normalize_panel_runtime_profile_sort_by=lambda value: str(value or "").strip().lower(),
                normalize_panel_runtime_profile_sort_order=lambda value: str(value or "").strip().lower(),
                normalize_case_fairness_gate_conclusion=lambda value: value,
                normalize_case_fairness_challenge_state=lambda value: value,
            )
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail, "invalid_panel_judge_id")

    def test_normalize_panel_runtime_profile_query_should_return_normalized_filters(
        self,
    ) -> None:
        payload = normalize_panel_runtime_profile_query(
            status="review_required",
            dispatch_type=" FINAL ",
            winner=" Draw ",
            policy_version=" v3-default ",
            gate_conclusion="blocked_to_draw",
            challenge_state="under_internal_review",
            judge_id=" judgeA ",
            profile_source="trace",
            profile_id=" profile-1 ",
            model_strategy="strategy-v1",
            strategy_slot="path_alignment",
            domain_slot="general",
            sort_by="updated_at",
            sort_order="desc",
            offset=5,
            limit=300,
            panel_judge_ids=("judgeA", "judgeB", "judgeC"),
            panel_runtime_profile_source_values={"trace", "override"},
            panel_runtime_profile_sort_fields={"updated_at", "case_id"},
            normalize_workflow_status=lambda value: str(value or "").strip().lower() or None,
            normalize_panel_runtime_profile_source=lambda value: str(value or "").strip().lower() or None,
            normalize_panel_runtime_profile_sort_by=lambda value: str(value or "").strip().lower(),
            normalize_panel_runtime_profile_sort_order=lambda value: str(value or "").strip().lower(),
            normalize_case_fairness_gate_conclusion=lambda value: str(value or "").strip().lower() or None,
            normalize_case_fairness_challenge_state=lambda value: str(value or "").strip() or None,
        )
        self.assertEqual(payload["status"], "review_required")
        self.assertEqual(payload["dispatchType"], "final")
        self.assertEqual(payload["winner"], "draw")
        self.assertEqual(payload["policyVersion"], "v3-default")
        self.assertEqual(payload["judgeId"], "judgeA")
        self.assertEqual(payload["profileSource"], "trace")
        self.assertEqual(payload["sortBy"], "updated_at")
        self.assertEqual(payload["sortOrder"], "desc")
        self.assertEqual(payload["offset"], 5)
        self.assertEqual(payload["limit"], 200)


if __name__ == "__main__":
    unittest.main()
