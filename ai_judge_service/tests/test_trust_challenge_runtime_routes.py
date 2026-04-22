from __future__ import annotations

import asyncio
import unittest
from dataclasses import dataclass
from typing import Any

from app.applications.trust_challenge_runtime_routes import (
    TrustChallengeRouteError,
    build_trust_challenge_decision_payload,
    build_trust_challenge_request_payload,
)


@dataclass
class _DummyJob:
    status: str
    scope_id: int


@dataclass
class _DummyAlert:
    alert_id: str


class _DummyWorkflowTransitionError(Exception):
    pass


class TrustChallengeRuntimeRoutesTests(unittest.TestCase):
    def test_build_trust_challenge_request_payload_should_return_route_shape(self) -> None:
        events: list[dict[str, Any]] = []
        review_mark_payloads: list[dict[str, Any]] = []
        jobs = [_DummyJob(status="reported", scope_id=8), _DummyJob(status="review_required", scope_id=8)]

        async def _resolve_report_context_for_case(**kwargs: Any) -> dict[str, Any]:
            self.assertEqual(kwargs["case_id"], 3001)
            return {
                "dispatchType": "final",
                "traceId": "trace-3001",
            }

        async def _workflow_get_job(*, job_id: int) -> Any:
            self.assertEqual(job_id, 3001)
            return jobs.pop(0) if jobs else _DummyJob(status="review_required", scope_id=8)

        async def _workflow_append_event(**kwargs: Any) -> None:
            events.append(dict(kwargs))

        async def _workflow_mark_review_required(*, job_id: int, event_payload: dict[str, Any]) -> None:
            self.assertEqual(job_id, 3001)
            review_mark_payloads.append(dict(event_payload))

        async def _build_trust_phasea_bundle(**kwargs: Any) -> dict[str, Any]:
            self.assertEqual(kwargs["case_id"], 3001)
            return {"challengeReview": {"state": "under_review"}}

        def _new_challenge_id(*, case_id: int) -> str:
            self.assertEqual(case_id, 3001)
            return "ch-3001-01"

        def _upsert_audit_alert(**kwargs: Any) -> _DummyAlert:
            self.assertEqual(kwargs["trace_id"], "trace-3001")
            return _DummyAlert(alert_id="alert-3001")

        async def _sync_audit_alert_to_facts(*, alert: _DummyAlert) -> None:
            self.assertEqual(alert.alert_id, "alert-3001")

        def _serialize_workflow_job(job: _DummyJob) -> dict[str, Any]:
            return {"status": job.status, "scopeId": job.scope_id}

        payload = asyncio.run(
            build_trust_challenge_request_payload(
                case_id=3001,
                dispatch_type="auto",
                reason_code="manual_challenge",
                reason="insufficient rebuttal",
                requested_by="ops-a",
                auto_accept=True,
                resolve_report_context_for_case=_resolve_report_context_for_case,
                workflow_get_job=_workflow_get_job,
                workflow_append_event=_workflow_append_event,
                workflow_mark_review_required=_workflow_mark_review_required,
                build_trust_phasea_bundle=_build_trust_phasea_bundle,
                new_challenge_id=_new_challenge_id,
                upsert_audit_alert=_upsert_audit_alert,
                sync_audit_alert_to_facts=_sync_audit_alert_to_facts,
                serialize_workflow_job=_serialize_workflow_job,
                trust_challenge_event_type="trust_challenge_state_changed",
                trust_challenge_state_requested="challenge_requested",
                trust_challenge_state_accepted="challenge_accepted",
                trust_challenge_state_under_review="under_review",
            )
        )
        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["challengeId"], "ch-3001-01")
        self.assertEqual(payload["alertId"], "alert-3001")
        self.assertEqual(payload["dispatchType"], "final")
        self.assertEqual(payload["traceId"], "trace-3001")
        self.assertEqual(payload["item"]["state"], "under_review")
        self.assertEqual(len(review_mark_payloads), 1)
        self.assertEqual(len(events), 3)

    def test_build_trust_challenge_decision_payload_should_reject_invalid_decision(self) -> None:
        async def _noop(*args: Any, **kwargs: Any) -> Any:
            del args, kwargs
            return None

        with self.assertRaises(TrustChallengeRouteError) as ctx:
            asyncio.run(
                build_trust_challenge_decision_payload(
                    case_id=3002,
                    challenge_id="ch-3002",
                    dispatch_type="auto",
                    decision="invalid",
                    actor=None,
                    reason=None,
                    resolve_report_context_for_case=_noop,
                    workflow_get_job=_noop,
                    workflow_append_event=_noop,
                    workflow_mark_review_required=_noop,
                    workflow_mark_completed=_noop,
                    workflow_mark_draw_pending_vote=_noop,
                    resolve_open_alerts_for_review=_noop,
                    build_trust_phasea_bundle=_noop,
                    serialize_workflow_job=lambda *_args, **_kwargs: {},
                    trust_challenge_event_type="trust_challenge_state_changed",
                    trust_challenge_state_closed="challenge_closed",
                    trust_challenge_state_accepted="challenge_accepted",
                    trust_challenge_state_under_review="under_review",
                    trust_challenge_state_verdict_upheld="verdict_upheld",
                    trust_challenge_state_verdict_overturned="verdict_overturned",
                    trust_challenge_state_draw_after_review="draw_after_review",
                    workflow_transition_error_cls=_DummyWorkflowTransitionError,
                )
            )
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail, "invalid_challenge_decision")

    def test_build_trust_challenge_decision_payload_should_drive_uphold_flow(self) -> None:
        events: list[dict[str, Any]] = []
        completed_payloads: list[dict[str, Any]] = []
        bundle_calls = {"count": 0}
        jobs = [_DummyJob(status="review_required", scope_id=9), _DummyJob(status="completed", scope_id=9)]

        async def _resolve_report_context_for_case(**kwargs: Any) -> dict[str, Any]:
            self.assertEqual(kwargs["case_id"], 3003)
            return {"dispatchType": "final", "traceId": "trace-3003"}

        async def _workflow_get_job(*, job_id: int) -> Any:
            self.assertEqual(job_id, 3003)
            return jobs.pop(0) if jobs else _DummyJob(status="completed", scope_id=9)

        async def _workflow_append_event(**kwargs: Any) -> None:
            events.append(dict(kwargs))

        async def _workflow_mark_review_required(*args: Any, **kwargs: Any) -> None:
            del args, kwargs
            self.fail("uphold flow should not call workflow_mark_review_required")

        async def _workflow_mark_completed(*, job_id: int, event_payload: dict[str, Any]) -> None:
            self.assertEqual(job_id, 3003)
            completed_payloads.append(dict(event_payload))

        async def _workflow_mark_draw_pending_vote(*args: Any, **kwargs: Any) -> None:
            del args, kwargs
            self.fail("uphold flow should not call workflow_mark_draw_pending_vote")

        async def _resolve_open_alerts_for_review(*, job_id: int, actor: str, reason: str) -> list[str]:
            self.assertEqual(job_id, 3003)
            self.assertEqual(actor, "ops-b")
            self.assertEqual(reason, "challenge_upheld")
            return ["alert-open-1"]

        async def _build_trust_phasea_bundle(**kwargs: Any) -> dict[str, Any]:
            self.assertEqual(kwargs["case_id"], 3003)
            bundle_calls["count"] += 1
            if bundle_calls["count"] == 1:
                return {
                    "challengeReview": {
                        "challenges": [
                            {
                                "challengeId": "ch-3003-01",
                                "currentState": "under_review",
                            }
                        ]
                    }
                }
            return {"challengeReview": {"state": "challenge_closed"}}

        def _serialize_workflow_job(job: _DummyJob) -> dict[str, Any]:
            return {"status": job.status}

        payload = asyncio.run(
            build_trust_challenge_decision_payload(
                case_id=3003,
                challenge_id="ch-3003-01",
                dispatch_type="auto",
                decision="uphold",
                actor="ops-b",
                reason=None,
                resolve_report_context_for_case=_resolve_report_context_for_case,
                workflow_get_job=_workflow_get_job,
                workflow_append_event=_workflow_append_event,
                workflow_mark_review_required=_workflow_mark_review_required,
                workflow_mark_completed=_workflow_mark_completed,
                workflow_mark_draw_pending_vote=_workflow_mark_draw_pending_vote,
                resolve_open_alerts_for_review=_resolve_open_alerts_for_review,
                build_trust_phasea_bundle=_build_trust_phasea_bundle,
                serialize_workflow_job=_serialize_workflow_job,
                trust_challenge_event_type="trust_challenge_state_changed",
                trust_challenge_state_closed="challenge_closed",
                trust_challenge_state_accepted="challenge_accepted",
                trust_challenge_state_under_review="under_review",
                trust_challenge_state_verdict_upheld="verdict_upheld",
                trust_challenge_state_verdict_overturned="verdict_overturned",
                trust_challenge_state_draw_after_review="draw_after_review",
                workflow_transition_error_cls=_DummyWorkflowTransitionError,
            )
        )
        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["challengeId"], "ch-3003-01")
        self.assertEqual(payload["decision"], "uphold")
        self.assertEqual(payload["resolvedAlertIds"], ["alert-open-1"])
        self.assertEqual(payload["item"]["state"], "challenge_closed")
        self.assertEqual(payload["job"]["status"], "completed")
        self.assertEqual(len(events), 2)
        self.assertEqual(len(completed_payloads), 1)


if __name__ == "__main__":
    unittest.main()
