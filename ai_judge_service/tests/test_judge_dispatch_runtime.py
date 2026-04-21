from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.applications.judge_dispatch_runtime import (
    CALLBACK_STATUS_FAILED_CALLBACK_FAILED,
    CALLBACK_STATUS_FAILED_REPORTED,
    CALLBACK_STATUS_REPORTED,
    build_final_dispatch_accepted_response,
    build_final_workflow_register_payload,
    build_final_workflow_reported_payload,
    build_phase_dispatch_accepted_response,
    build_phase_workflow_register_payload,
    build_phase_workflow_reported_payload,
    deliver_report_callback_with_failed_fallback,
)
from app.models import FinalDispatchRequest, PhaseDispatchMessage, PhaseDispatchRequest


def _build_phase_request() -> PhaseDispatchRequest:
    return PhaseDispatchRequest(
        case_id=93001,
        scope_id=1,
        session_id=70001,
        phase_no=2,
        message_start_id=11,
        message_end_id=12,
        message_count=2,
        messages=[
            PhaseDispatchMessage(
                message_id=11,
                side="pro",
                content="pro",
                created_at=datetime.now(timezone.utc),
            ),
            PhaseDispatchMessage(
                message_id=12,
                side="con",
                content="con",
                created_at=datetime.now(timezone.utc),
            ),
        ],
        rubric_version="v3",
        judge_policy_version="v3-default",
        topic_domain="general",
        retrieval_profile="hybrid_v1",
        trace_id="trace-phase-93001",
        idempotency_key="phase:93001",
    )


def _build_final_request() -> FinalDispatchRequest:
    return FinalDispatchRequest(
        case_id=93002,
        scope_id=1,
        session_id=70002,
        phase_start_no=1,
        phase_end_no=3,
        rubric_version="v3",
        judge_policy_version="v3-default",
        topic_domain="general",
        trace_id="trace-final-93002",
        idempotency_key="final:93002",
    )


class JudgeDispatchRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def test_build_dispatch_payloads_should_follow_contract(self) -> None:
        phase_request = _build_phase_request()
        final_request = _build_final_request()

        phase_response = build_phase_dispatch_accepted_response(request=phase_request)
        self.assertEqual(phase_response["dispatchType"], "phase")
        self.assertEqual(phase_response["phaseNo"], phase_request.phase_no)
        self.assertEqual(phase_response["messageCount"], phase_request.message_count)

        final_response = build_final_dispatch_accepted_response(request=final_request)
        self.assertEqual(final_response["dispatchType"], "final")
        self.assertEqual(final_response["phaseStartNo"], final_request.phase_start_no)
        self.assertEqual(final_response["phaseEndNo"], final_request.phase_end_no)

        phase_register_payload = build_phase_workflow_register_payload(
            request=phase_request,
            policy_version="policy-v1",
            prompt_version="prompt-v1",
            toolset_version="tool-v1",
        )
        self.assertEqual(phase_register_payload["policyVersion"], "policy-v1")
        self.assertEqual(phase_register_payload["promptVersion"], "prompt-v1")
        self.assertEqual(phase_register_payload["toolsetVersion"], "tool-v1")

        final_register_payload = build_final_workflow_register_payload(
            request=final_request,
            policy_version="policy-v2",
            prompt_version="prompt-v2",
            toolset_version="tool-v2",
        )
        self.assertEqual(final_register_payload["policyVersion"], "policy-v2")
        self.assertEqual(final_register_payload["promptVersion"], "prompt-v2")
        self.assertEqual(final_register_payload["toolsetVersion"], "tool-v2")

        phase_reported_payload = build_phase_workflow_reported_payload(
            request=phase_request,
        )
        self.assertEqual(phase_reported_payload["callbackStatus"], "reported")

        final_reported_payload = build_final_workflow_reported_payload(
            request=final_request,
            report_payload={
                "winner": "pro",
                "reviewRequired": False,
                "errorCodes": ["warn_a"],
            },
        )
        self.assertEqual(final_reported_payload["winner"], "pro")
        self.assertFalse(final_reported_payload["reviewRequired"])
        self.assertEqual(final_reported_payload["errorCodes"], ["warn_a"])

    async def test_deliver_report_callback_should_return_reported(self) -> None:
        async def report_callback(case_id: int, payload: dict[str, object]) -> None:
            self.assertEqual(case_id, 93001)
            self.assertEqual(payload.get("winner"), "pro")

        async def failed_callback(case_id: int, payload: dict[str, object]) -> None:
            self.fail(f"unexpected failed callback: {case_id} {payload}")

        async def invoke_with_retry(callback_fn, job_id: int, payload: dict[str, object]):
            await callback_fn(job_id, payload)
            return 1, 0

        outcome = await deliver_report_callback_with_failed_fallback(
            job_id=93001,
            report_payload={"winner": "pro"},
            report_callback_fn=report_callback,
            failed_callback_fn=failed_callback,
            invoke_with_retry=invoke_with_retry,
            build_failed_payload=lambda error: {"error": error},
        )
        self.assertEqual(outcome.callback_status, CALLBACK_STATUS_REPORTED)
        self.assertEqual(outcome.callback_attempts, 1)
        self.assertEqual(outcome.callback_retries, 0)

    async def test_deliver_report_callback_should_return_failed_reported(self) -> None:
        async def report_callback(case_id: int, payload: dict[str, object]) -> None:
            raise RuntimeError("report_failed")

        async def failed_callback(case_id: int, payload: dict[str, object]) -> None:
            self.assertEqual(case_id, 93002)
            self.assertIn("errorCode", payload)

        async def invoke_with_retry(callback_fn, job_id: int, payload: dict[str, object]):
            await callback_fn(job_id, payload)
            return 2, 1

        outcome = await deliver_report_callback_with_failed_fallback(
            job_id=93002,
            report_payload={"winner": "draw"},
            report_callback_fn=report_callback,
            failed_callback_fn=failed_callback,
            invoke_with_retry=invoke_with_retry,
            build_failed_payload=lambda error: {
                "errorCode": "callback_retry_exhausted",
                "errorMessage": error,
            },
        )
        self.assertEqual(outcome.callback_status, CALLBACK_STATUS_FAILED_REPORTED)
        self.assertEqual(outcome.report_error, "report_failed")
        self.assertEqual(outcome.failed_attempts, 2)
        self.assertEqual(outcome.failed_retries, 1)
        self.assertIsNone(outcome.failed_error)

    async def test_deliver_report_callback_should_return_failed_callback_failed(self) -> None:
        async def report_callback(case_id: int, payload: dict[str, object]) -> None:
            raise RuntimeError("report_failed")

        async def failed_callback(case_id: int, payload: dict[str, object]) -> None:
            raise RuntimeError("failed_callback_failed")

        async def invoke_with_retry(callback_fn, job_id: int, payload: dict[str, object]):
            await callback_fn(job_id, payload)
            return 1, 0

        outcome = await deliver_report_callback_with_failed_fallback(
            job_id=93003,
            report_payload={"winner": "draw"},
            report_callback_fn=report_callback,
            failed_callback_fn=failed_callback,
            invoke_with_retry=invoke_with_retry,
            build_failed_payload=lambda error: {
                "errorCode": "callback_retry_exhausted",
                "errorMessage": error,
            },
        )
        self.assertEqual(outcome.callback_status, CALLBACK_STATUS_FAILED_CALLBACK_FAILED)
        self.assertEqual(outcome.report_error, "report_failed")
        self.assertEqual(outcome.failed_error, "failed_callback_failed")


if __name__ == "__main__":
    unittest.main()
