from __future__ import annotations

import unittest

from app.applications.panel_runtime_profile_contract import (
    PANEL_RUNTIME_PROFILE_AGGREGATIONS_KEYS,
    PANEL_RUNTIME_PROFILE_FILTER_KEYS,
    PANEL_RUNTIME_PROFILE_ITEM_KEYS,
    PANEL_RUNTIME_PROFILE_TOP_LEVEL_KEYS,
    PANEL_RUNTIME_READINESS_SWITCH_BLOCKERS,
    validate_panel_runtime_profile_contract,
    validate_panel_runtime_readiness_contract,
)


class PanelRuntimeProfileContractTests(unittest.TestCase):
    def _build_item(self, *, case_id: int, judge_id: str) -> dict:
        return {
            "caseId": case_id,
            "traceId": f"trace-{case_id}",
            "dispatchType": "final",
            "workflowStatus": "completed",
            "updatedAt": "2026-04-19T00:00:00Z",
            "winner": "pro",
            "gateConclusion": "pass_through",
            "reviewRequired": False,
            "hasOpenReview": False,
            "challengeState": None,
            "panelDisagreement": {
                "high": False,
                "ratio": 0.0,
                "ratioMax": 0.0,
                "reasons": [],
                "majorityWinner": "pro",
                "voteBySide": {"pro": 2, "con": 1},
            },
            "judgeId": judge_id,
            "profileId": f"profile-{judge_id}",
            "profileSource": "builtin_default",
            "modelStrategy": "deterministic_path_alignment",
            "strategySlot": "path_alignment",
            "scoreSource": "panel_vote",
            "decisionMargin": 0.0,
            "promptVersion": "p-v1",
            "toolsetVersion": "t-v1",
            "domainSlot": "general",
            "runtimeStage": "final",
            "adaptiveEnabled": False,
            "candidateModels": [],
            "strategyMetadata": {},
            "policyVersion": "v3-default",
            "shadowEnabled": True,
            "shadowModelStrategy": "shadow_weighted_vote",
            "shadowDecisionAgreement": 0.92,
            "shadowCostEstimate": 0.018,
            "shadowLatencyEstimate": 820.0,
            "shadowDriftSignals": [],
            "shadowReleaseGateSignal": {
                "status": "ready",
                "blocksAutoRelease": False,
                "reasons": [],
                "advisoryOnly": True,
            },
            "shadowEvaluation": {
                "enabled": True,
                "modelStrategy": "shadow_weighted_vote",
                "decisionAgreement": 0.92,
                "costEstimate": 0.018,
                "latencyEstimate": 820.0,
                "driftSignals": [],
                "releaseGateSignal": {
                    "status": "ready",
                    "blocksAutoRelease": False,
                    "reasons": [],
                    "advisoryOnly": True,
                },
                "latestRun": None,
                "benchmarkRunId": None,
                "officialWinnerMutationAllowed": False,
                "advisoryOnly": True,
            },
            "runtimeProfile": {"judgeId": judge_id},
        }

    def _build_payload(self) -> dict:
        items = [
            self._build_item(case_id=7001, judge_id="judgeA"),
            self._build_item(case_id=7001, judge_id="judgeB"),
            self._build_item(case_id=7001, judge_id="judgeC"),
        ]
        return {
            "count": 3,
            "returned": 3,
            "items": items,
            "aggregations": {
                "totalMatched": 3,
                "reviewRequiredCount": 0,
                "openReviewCount": 0,
                "panelHighDisagreementCount": 0,
                "avgPanelDisagreementRatio": 0.0,
                "byJudgeId": {"judgeA": 1, "judgeB": 1, "judgeC": 1},
                "byProfileId": {
                    "profile-judgeA": 1,
                    "profile-judgeB": 1,
                    "profile-judgeC": 1,
                    "unknown": 0,
                },
                "byModelStrategy": {"deterministic_path_alignment": 3, "unknown": 0},
                "byStrategySlot": {"path_alignment": 3, "unknown": 0},
                "byDomainSlot": {"general": 3, "unknown": 0},
                "byProfileSource": {"builtin_default": 3, "unknown": 0},
                "byPolicyVersion": {"v3-default": 3, "unknown": 0},
                "byShadowModelStrategy": {"shadow_weighted_vote": 3, "unknown": 0},
                "winnerCounts": {"pro": 3, "con": 0, "draw": 0, "unknown": 0},
                "shadowEnabledCount": 3,
                "shadowAgreementCount": 3,
                "shadowDriftSignalCount": 0,
                "avgShadowDecisionAgreement": 0.92,
                "avgShadowCostEstimate": 0.018,
                "avgShadowLatencyEstimate": 820.0,
            },
            "filters": {
                "status": None,
                "dispatchType": "final",
                "winner": None,
                "policyVersion": "v3-default",
                "hasOpenReview": None,
                "gateConclusion": None,
                "challengeState": None,
                "reviewRequired": None,
                "panelHighDisagreement": None,
                "judgeId": None,
                "profileSource": None,
                "profileId": None,
                "modelStrategy": None,
                "strategySlot": None,
                "domainSlot": None,
                "sortBy": "updated_at",
                "sortOrder": "desc",
                "offset": 0,
                "limit": 200,
            },
        }

    def test_validate_panel_runtime_profile_contract_should_pass_for_stable_payload(self) -> None:
        payload = self._build_payload()
        self.assertEqual(set(payload.keys()), set(PANEL_RUNTIME_PROFILE_TOP_LEVEL_KEYS))
        self.assertEqual(set(payload["items"][0].keys()), set(PANEL_RUNTIME_PROFILE_ITEM_KEYS))
        self.assertEqual(
            set(payload["aggregations"].keys()),
            set(PANEL_RUNTIME_PROFILE_AGGREGATIONS_KEYS),
        )
        self.assertEqual(set(payload["filters"].keys()), set(PANEL_RUNTIME_PROFILE_FILTER_KEYS))
        validate_panel_runtime_profile_contract(payload)

    def test_validate_panel_runtime_profile_contract_should_fail_on_missing_item_key(self) -> None:
        payload = self._build_payload()
        payload["items"][0].pop("judgeId")

        with self.assertRaises(ValueError) as ctx:
            validate_panel_runtime_profile_contract(payload)
        self.assertIn("panel_runtime_profile_item_missing_keys", str(ctx.exception))

    def test_validate_panel_runtime_profile_contract_should_fail_on_count_map_mismatch(self) -> None:
        payload = self._build_payload()
        payload["aggregations"]["byModelStrategy"]["deterministic_path_alignment"] = 2

        with self.assertRaises(ValueError) as ctx:
            validate_panel_runtime_profile_contract(payload)
        self.assertIn("panel_runtime_profile_by_model_strategy_sum_mismatch", str(ctx.exception))

    def test_validate_panel_runtime_readiness_contract_should_require_safe_candidate_shape(
        self,
    ) -> None:
        blocker_counts = {blocker: 0 for blocker in PANEL_RUNTIME_READINESS_SWITCH_BLOCKERS}
        blocker_counts["real_samples_missing"] = 1
        group = {
            "groupKey": "path|general|weighted|profile-a|v3-default",
            "strategySlot": "path",
            "domainSlot": "general",
            "modelStrategy": "weighted",
            "profileId": "profile-a",
            "policyVersion": "v3-default",
            "recordCount": 3,
            "caseCount": 1,
            "judgeIds": ["judgeA", "judgeB", "judgeC"],
            "profileSources": ["trace"],
            "candidateModels": ["gpt-4.1-mini"],
            "candidateModelCount": 1,
            "adaptiveEnabledRate": 0.0,
            "shadowEnabledCount": 3,
            "shadowEnabledRate": 1.0,
            "shadowDriftSignalCount": 0,
            "shadowDriftSignalRate": 0.0,
            "avgShadowDecisionAgreement": 0.91,
            "avgShadowCostEstimate": 0.02,
            "avgShadowLatencyEstimate": 900.0,
            "shadowReleaseGateSignals": ["watch"],
            "panelHighDisagreementCount": 0,
            "panelHighDisagreementRate": 0.0,
            "reviewRequiredCount": 0,
            "reviewRequiredRate": 0.0,
            "openReviewCount": 0,
            "openReviewRate": 0.0,
            "avgPanelDisagreementRatio": 0.0,
            "readinessScore": 95.0,
            "readinessLevel": "ready",
            "switchBlockers": ["real_samples_missing"],
            "releaseGateSignals": {
                "status": "watch",
                "blocksCandidateRollout": True,
                "switchBlockers": ["real_samples_missing"],
                "candidateModelCount": 1,
                "shadowAgreementThreshold": 0.8,
                "costBudgetMax": 0.05,
                "latencyBudgetMsMax": 2000.0,
                "advisoryOnly": True,
                "autoSwitchAllowed": False,
                "officialWinnerSemanticsChanged": False,
            },
            "recommendedSwitchConditions": ["stable_runtime"],
            "simulations": [{"scenarioId": "keep", "advisoryOnly": True}],
        }
        payload = {
            "generatedAt": "2026-04-28T00:00:00Z",
            "overview": {
                "totalMatched": 3,
                "scannedRecords": 3,
                "scanTruncated": False,
                "totalGroups": 1,
                "attentionGroupCount": 0,
                "readinessCounts": {"ready": 1, "watch": 0, "attention": 0},
                "shadow": {
                    "enabledGroupCount": 1,
                    "blockedGroupCount": 0,
                    "watchGroupCount": 1,
                    "driftSignalGroupCount": 0,
                    "candidateModelGroupCount": 1,
                    "releaseGateSignalCounts": {"ready": 0, "watch": 1, "blocked": 0},
                    "switchBlockerCounts": blocker_counts,
                    "avgDecisionAgreement": 0.91,
                    "avgCostEstimate": 0.02,
                    "avgLatencyEstimate": 900.0,
                    "officialWinnerMutationAllowed": False,
                    "officialWinnerSemanticsChanged": False,
                    "autoSwitchAllowed": False,
                },
            },
            "groups": [group],
            "attentionGroups": [],
            "notes": ["advisory-only"],
            "filters": {},
        }

        validate_panel_runtime_readiness_contract(payload)

        payload["groups"][0]["releaseGateSignals"]["autoSwitchAllowed"] = True
        with self.assertRaisesRegex(ValueError, "auto_switch_allowed_not_false"):
            validate_panel_runtime_readiness_contract(payload)


if __name__ == "__main__":
    unittest.main()
