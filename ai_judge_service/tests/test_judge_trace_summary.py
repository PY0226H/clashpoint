from __future__ import annotations

import unittest

from app.applications.judge_trace_summary import (
    build_judge_workflow_role_nodes,
    build_trace_report_summary,
    validate_trace_report_summary_contract,
)


class JudgeTraceSummaryTests(unittest.TestCase):
    _ROLE_ORDER = [
        "clerk",
        "recorder",
        "claim_graph",
        "evidence",
        "panel",
        "fairness_sentinel",
        "chief_arbiter",
        "opinion_writer",
    ]

    def _build_judge_workflow(self) -> dict:
        return {
            "judgeWorkflow": {
                "caseDossier": {
                    "caseId": 1001,
                    "dispatchType": "final",
                    "roleOrder": list(self._ROLE_ORDER),
                },
                "claimGraph": {"stats": {}},
                "evidenceBundle": {"entries": []},
                "panelBundle": {"judges": {}},
                "fairnessGate": {"decision": "pass_through", "reviewRequired": False},
                "verdict": {
                    "winner": "pro",
                    "needsDrawVote": False,
                    "reviewRequired": False,
                },
                "opinion": {"sideAnalysis": {}},
            }
        }

    def test_build_judge_workflow_role_nodes_should_keep_role_order(self) -> None:
        role_nodes = build_judge_workflow_role_nodes(self._build_judge_workflow())
        self.assertEqual(len(role_nodes), 8)
        self.assertEqual([row["role"] for row in role_nodes], self._ROLE_ORDER)
        self.assertEqual([row["seq"] for row in role_nodes], list(range(1, 9)))
        self.assertEqual(role_nodes[0]["status"], "completed")

    def test_build_trace_report_summary_should_attach_role_nodes(self) -> None:
        summary = build_trace_report_summary(
            dispatch_type="final",
            payload={"winner": "pro", "auditAlerts": []},
            callback_status="reported",
            callback_error=None,
            judge_workflow=self._build_judge_workflow(),
        )
        self.assertIn("judgeWorkflow", summary)
        self.assertIn("roleNodes", summary)
        self.assertEqual(len(summary["roleNodes"]), 8)
        self.assertEqual(
            [row["role"] for row in summary["roleNodes"]],
            self._ROLE_ORDER,
        )

    def test_validate_trace_report_summary_contract_should_fail_when_final_missing_workflow(
        self,
    ) -> None:
        payload = {
            "dispatchType": "final",
            "payload": {"winner": "pro"},
            "winner": "pro",
            "auditAlerts": [],
            "callbackStatus": "reported",
            "callbackError": None,
        }
        with self.assertRaises(ValueError) as ctx:
            validate_trace_report_summary_contract(payload)
        self.assertIn("trace_report_summary_judge_workflow_missing", str(ctx.exception))

    def test_validate_trace_report_summary_contract_should_fail_when_role_nodes_incomplete(
        self,
    ) -> None:
        payload = {
            "dispatchType": "final",
            "payload": {"winner": "pro"},
            "winner": "pro",
            "auditAlerts": [],
            "callbackStatus": "reported",
            "callbackError": None,
            "judgeWorkflow": self._build_judge_workflow(),
            "roleNodes": [
                {
                    "seq": 1,
                    "role": "clerk",
                    "section": "caseDossier",
                    "status": "completed",
                }
            ],
        }
        with self.assertRaises(ValueError) as ctx:
            validate_trace_report_summary_contract(payload)
        self.assertIn("trace_report_summary_role_nodes_incomplete", str(ctx.exception))

    def test_validate_trace_report_summary_contract_should_fail_when_role_nodes_order_invalid(
        self,
    ) -> None:
        payload = {
            "dispatchType": "final",
            "payload": {"winner": "pro"},
            "winner": "pro",
            "auditAlerts": [],
            "callbackStatus": "reported",
            "callbackError": None,
            "judgeWorkflow": self._build_judge_workflow(),
            "roleNodes": [
                {
                    "seq": 1,
                    "role": "recorder",
                    "section": "claimGraph",
                    "status": "completed",
                },
                {
                    "seq": 2,
                    "role": "clerk",
                    "section": "caseDossier",
                    "status": "completed",
                },
                {
                    "seq": 3,
                    "role": "claim_graph",
                    "section": "claimGraph",
                    "status": "completed",
                },
                {
                    "seq": 4,
                    "role": "evidence",
                    "section": "evidenceBundle",
                    "status": "completed",
                },
                {
                    "seq": 5,
                    "role": "panel",
                    "section": "panelBundle",
                    "status": "completed",
                },
                {
                    "seq": 6,
                    "role": "fairness_sentinel",
                    "section": "fairnessGate",
                    "status": "completed",
                },
                {
                    "seq": 7,
                    "role": "chief_arbiter",
                    "section": "verdict",
                    "status": "completed",
                },
                {
                    "seq": 8,
                    "role": "opinion_writer",
                    "section": "opinion",
                    "status": "completed",
                },
            ],
        }
        with self.assertRaises(ValueError) as ctx:
            validate_trace_report_summary_contract(payload)
        self.assertIn(
            "trace_report_summary_role_node_role_order_invalid:0",
            str(ctx.exception),
        )

    def test_validate_trace_report_summary_contract_should_allow_case_without_workflow(
        self,
    ) -> None:
        payload = {
            "dispatchType": "case",
            "payload": {},
            "winner": None,
            "auditAlerts": [],
            "callbackStatus": "case_built",
            "callbackError": None,
        }
        validate_trace_report_summary_contract(payload)


if __name__ == "__main__":
    unittest.main()
