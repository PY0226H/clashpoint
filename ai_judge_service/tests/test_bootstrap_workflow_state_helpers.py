from __future__ import annotations

import unittest
from typing import Any

from app.applications.bootstrap_workflow_state_helpers import (
    workflow_mark_completed_for_runtime,
    workflow_mark_failed_for_runtime,
    workflow_mark_replay_for_runtime,
    workflow_mark_review_required_for_runtime,
    workflow_register_and_mark_blinded_for_runtime,
    workflow_register_and_mark_case_built_for_runtime,
)


class _JudgeCore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.replay_should_fail = False

    async def register_blinded(self, **kwargs: Any) -> None:
        self.calls.append(("register_blinded", kwargs))

    async def register_case_built(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("register_case_built", kwargs))
        return {"caseBuilt": True, **kwargs}

    async def mark_reported(self, **kwargs: Any) -> None:
        self.calls.append(("mark_reported", kwargs))

    async def mark_failed(self, **kwargs: Any) -> None:
        self.calls.append(("mark_failed", kwargs))

    async def mark_replay(self, **kwargs: Any) -> None:
        self.calls.append(("mark_replay", kwargs))
        if self.replay_should_fail:
            raise LookupError("missing_workflow")


class BootstrapWorkflowStateHelpersTests(unittest.IsolatedAsyncioTestCase):
    async def test_register_helpers_should_ensure_schema_before_core_call(self) -> None:
        judge_core = _JudgeCore()
        ensure_calls = {"count": 0}

        async def _ensure() -> None:
            ensure_calls["count"] += 1

        job = {"id": 42}
        await workflow_register_and_mark_blinded_for_runtime(
            judge_core=judge_core,
            ensure_workflow_schema_ready=_ensure,
            job=job,
            event_payload={"stage": "blinded"},
        )
        result = await workflow_register_and_mark_case_built_for_runtime(
            judge_core=judge_core,
            ensure_workflow_schema_ready=_ensure,
            job=job,
            event_payload={"stage": "case_built"},
        )

        self.assertEqual(ensure_calls, {"count": 2})
        self.assertEqual(result["caseBuilt"], True)
        self.assertEqual(
            [name for name, _kwargs in judge_core.calls],
            ["register_blinded", "register_case_built"],
        )
        self.assertIs(judge_core.calls[0][1]["job"], job)

    async def test_mark_reported_helpers_should_keep_stage_fallbacks(self) -> None:
        judge_core = _JudgeCore()
        ensure_calls = {"count": 0}

        async def _ensure() -> None:
            ensure_calls["count"] += 1

        await workflow_mark_completed_for_runtime(
            judge_core=judge_core,
            ensure_workflow_schema_ready=_ensure,
            job_id=101,
            event_payload={"dispatchType": " Final ", "reviewDecision": "approved"},
        )
        await workflow_mark_review_required_for_runtime(
            judge_core=judge_core,
            ensure_workflow_schema_ready=_ensure,
            job_id=102,
            event_payload={"dispatchType": "phase"},
        )

        completed = judge_core.calls[0][1]
        review_required = judge_core.calls[1][1]
        self.assertEqual(ensure_calls, {"count": 2})
        self.assertEqual(completed["dispatch_type"], "final")
        self.assertEqual(completed["completed_stage"], "review_approved")
        self.assertFalse(completed["review_required"])
        self.assertEqual(review_required["dispatch_type"], "phase")
        self.assertTrue(review_required["review_required"])

    async def test_mark_failed_should_attach_workflow_error_contract(self) -> None:
        judge_core = _JudgeCore()
        original_payload = {
            "dispatchType": " final ",
            "traceId": "trace-1",
            "callbackStatus": "callback_failed",
        }

        async def _ensure() -> None:
            return None

        await workflow_mark_failed_for_runtime(
            judge_core=judge_core,
            ensure_workflow_schema_ready=_ensure,
            job_id=201,
            error_code="callback_failed",
            error_message="callback boom",
            event_payload=original_payload,
        )

        call = judge_core.calls[0][1]
        payload = call["event_payload"]
        self.assertEqual(call["dispatch_type"], "final")
        self.assertEqual(call["stage"], "blocked_failed")
        self.assertEqual(payload["errorCode"], "callback_failed")
        self.assertEqual(payload["error"]["category"], "workflow_failed")
        self.assertEqual(payload["error"]["details"]["judgeCoreStage"], "blocked_failed")
        self.assertNotIn("error", original_payload)

    async def test_mark_replay_should_ignore_missing_workflow_job(self) -> None:
        judge_core = _JudgeCore()
        judge_core.replay_should_fail = True
        ensure_calls = {"count": 0}

        async def _ensure() -> None:
            ensure_calls["count"] += 1

        await workflow_mark_replay_for_runtime(
            judge_core=judge_core,
            ensure_workflow_schema_ready=_ensure,
            job_id=301,
            dispatch_type="final",
            event_payload={"traceId": "trace-301"},
        )

        self.assertEqual(ensure_calls, {"count": 1})
        self.assertEqual(judge_core.calls[0][0], "mark_replay")
