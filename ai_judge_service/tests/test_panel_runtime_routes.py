from __future__ import annotations

import unittest

from app.applications.panel_runtime_routes import (
    PanelRuntimeRouteError,
    normalize_panel_runtime_profile_query,
)


class PanelRuntimeRoutesTests(unittest.TestCase):
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
            challenge_state="under_review",
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
