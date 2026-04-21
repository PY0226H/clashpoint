from __future__ import annotations

import unittest

from app.applications.judge_app_domain import (
    JUDGE_ROLE_ORDER,
    JUDGE_WORKFLOW_ROOT_KEY,
    JUDGE_WORKFLOW_SECTION_KEYS,
    build_judge_role_domain_state,
    validate_judge_app_domain_payload,
)


class JudgeAppDomainTests(unittest.TestCase):
    def test_build_judge_role_domain_state_should_emit_single_root_field(self) -> None:
        state = build_judge_role_domain_state(
            case_id=12001,
            dispatch_type="final",
            trace_id="trace-final-12001",
            message_count=18,
            judge_policy_version="v3-default",
            rubric_version="v3",
            topic_domain="general",
            claim_graph={"stats": {"totalClaims": 6}},
            fairness_gate={"decision": "pass_through"},
            verdict={"winner": "pro"},
            opinion={"debateSummary": "summary ready"},
        )

        payload = state.to_payload()
        self.assertEqual(set(payload.keys()), {JUDGE_WORKFLOW_ROOT_KEY})
        workflow = payload[JUDGE_WORKFLOW_ROOT_KEY]
        self.assertEqual(set(workflow.keys()), set(JUDGE_WORKFLOW_SECTION_KEYS))
        self.assertEqual(
            workflow["caseDossier"]["roleOrder"],
            list(JUDGE_ROLE_ORDER),
        )
        validate_judge_app_domain_payload(payload)

    def test_validate_judge_app_domain_payload_should_fail_on_missing_root_key(self) -> None:
        payload = {
            "workflow": {
                "caseDossier": {
                    "caseId": 1,
                    "dispatchType": "final",
                    "roleOrder": list(JUDGE_ROLE_ORDER),
                }
            }
        }
        with self.assertRaises(ValueError) as ctx:
            validate_judge_app_domain_payload(payload)
        self.assertIn("judge_workflow_root_key_invalid", str(ctx.exception))

    def test_validate_judge_app_domain_payload_should_fail_on_role_order_drift(self) -> None:
        payload = build_judge_role_domain_state(
            case_id=12002,
            dispatch_type="phase",
        ).to_payload()
        payload[JUDGE_WORKFLOW_ROOT_KEY]["caseDossier"]["roleOrder"] = [
            "clerk",
            "recorder",
        ]
        with self.assertRaises(ValueError) as ctx:
            validate_judge_app_domain_payload(payload)
        self.assertIn("judge_workflow_case_dossier_role_order_invalid", str(ctx.exception))

    def test_validate_judge_app_domain_payload_should_fail_on_unknown_fairness_decision(self) -> None:
        payload = build_judge_role_domain_state(
            case_id=12003,
            dispatch_type="final",
        ).to_payload()
        payload[JUDGE_WORKFLOW_ROOT_KEY]["fairnessGate"]["decision"] = "manual_override"
        with self.assertRaises(ValueError) as ctx:
            validate_judge_app_domain_payload(payload)
        self.assertIn("judge_workflow_fairness_gate_decision_invalid", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
