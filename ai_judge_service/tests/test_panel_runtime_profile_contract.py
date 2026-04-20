from __future__ import annotations

import unittest

from app.applications.panel_runtime_profile_contract import (
    PANEL_RUNTIME_PROFILE_AGGREGATIONS_KEYS,
    PANEL_RUNTIME_PROFILE_FILTER_KEYS,
    PANEL_RUNTIME_PROFILE_ITEM_KEYS,
    PANEL_RUNTIME_PROFILE_TOP_LEVEL_KEYS,
    validate_panel_runtime_profile_contract,
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
            "gateConclusion": "auto_passed",
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
                "winnerCounts": {"pro": 3, "con": 0, "draw": 0, "unknown": 0},
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


if __name__ == "__main__":
    unittest.main()
