from __future__ import annotations

import unittest
from unittest.mock import patch

from app.app_factory import create_app, create_runtime
from app.applications.trust_challenge_public_contract import (
    find_trust_challenge_public_forbidden_keys,
)

from tests.app_factory_test_helpers import (
    AppFactoryRouteTestMixin,
)
from tests.app_factory_test_helpers import (
    build_final_request as _build_final_request,
)
from tests.app_factory_test_helpers import (
    build_phase_request as _build_phase_request,
)
from tests.app_factory_test_helpers import (
    build_settings as _build_settings,
)
from tests.app_factory_test_helpers import (
    unique_case_id as _unique_case_id,
)


class AppFactoryTrustChallengeRouteTests(
    AppFactoryRouteTestMixin,
    unittest.IsolatedAsyncioTestCase,
):

    async def test_trust_challenge_request_and_decision_should_drive_phaseb_lifecycle(
        self,
    ) -> None:
        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)

        case_id = _unique_case_id(8420)
        phase_req = _build_phase_request(case_id=case_id, idempotency_key=f"phase:{case_id}")
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)
        final_req = _build_final_request(case_id=case_id, idempotency_key=f"final:{case_id}")
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        before_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=case_id)
        self.assertIsNotNone(before_job)
        assert before_job is not None
        self.assertEqual(before_job.status, "callback_reported")

        eligible_status_resp = await self._get(
            app=app,
            path=(
                f"/internal/judge/cases/{case_id}/trust/challenges/public-status"
                "?dispatch_type=auto"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(eligible_status_resp.status_code, 200)
        eligible_status = eligible_status_resp.json()
        self.assertEqual(eligible_status["eligibility"]["status"], "eligible")
        self.assertIn("challenge.request", eligible_status["allowedActions"])
        self.assertEqual(
            find_trust_challenge_public_forbidden_keys(eligible_status),
            set(),
        )

        request_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/cases/{case_id}/trust/challenges/request"
                "?dispatch_type=auto&reason_code=manual_challenge&reason=need_recheck&requested_by=ops"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(request_resp.status_code, 200)
        request_payload = request_resp.json()
        self.assertTrue(request_payload["ok"])
        self.assertEqual(request_payload["dispatchType"], "final")
        self.assertTrue(str(request_payload["challengeId"]).startswith(f"chlg-{case_id}-"))
        self.assertEqual(request_payload["item"]["version"], "trust-phaseB-challenge-review-v1")
        self.assertEqual(request_payload["item"]["reviewState"], "pending_review")
        self.assertEqual(request_payload["item"]["challengeState"], "under_internal_review")
        self.assertEqual(request_payload["item"]["activeChallengeId"], request_payload["challengeId"])
        self.assertGreaterEqual(request_payload["item"]["totalChallenges"], 1)
        self.assertEqual(
            request_payload["item"]["latestRegistryEvent"]["state"],
            "under_internal_review",
        )
        self.assertEqual(
            request_payload["publicStatus"]["eligibility"]["status"],
            "under_review",
        )
        self.assertNotIn(
            "challenge.request",
            request_payload["publicStatus"]["allowedActions"],
        )
        self.assertNotIn("timeline", request_payload["publicStatus"]["challenge"])

        duplicate_request_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/cases/{case_id}/trust/challenges/request"
                "?dispatch_type=auto&reason_code=manual_challenge&reason=duplicate"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(duplicate_request_resp.status_code, 409)
        self.assertIn("trust_challenge_already_open", duplicate_request_resp.text)

        review_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=case_id)
        self.assertIsNotNone(review_job)
        assert review_job is not None
        self.assertEqual(review_job.status, "review_required")

        under_review_status_resp = await self._get(
            app=app,
            path=(
                f"/internal/judge/cases/{case_id}/trust/challenges/public-status"
                "?dispatch_type=auto"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(under_review_status_resp.status_code, 200)
        under_review_status = under_review_status_resp.json()
        self.assertEqual(under_review_status["eligibility"]["status"], "under_review")
        self.assertEqual(
            under_review_status["blockers"],
            ["challenge_duplicate_open"],
        )
        self.assertNotIn("challenge.request", under_review_status["allowedActions"])

        decision_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/cases/{case_id}/trust/challenges/{request_payload['challengeId']}/decision"
                "?dispatch_type=auto&decision=uphold&actor=reviewer&reason=verified"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(decision_resp.status_code, 200)
        decision_payload = decision_resp.json()
        self.assertTrue(decision_payload["ok"])
        self.assertEqual(decision_payload["decision"], "uphold")
        self.assertEqual(decision_payload["job"]["status"], "callback_reported")
        self.assertEqual(decision_payload["item"]["reviewState"], "approved")
        self.assertEqual(decision_payload["item"]["challengeState"], "challenge_closed")
        self.assertEqual(decision_payload["item"]["activeChallengeId"], None)
        challenges = decision_payload["item"]["challenges"]
        self.assertTrue(any(row["challengeId"] == request_payload["challengeId"] for row in challenges))
        target = next(row for row in challenges if row["challengeId"] == request_payload["challengeId"])
        self.assertEqual(target["currentState"], "challenge_closed")
        self.assertEqual(target["decision"], "verdict_upheld")
        self.assertEqual(target["decisionBy"], "reviewer")
        self.assertEqual(decision_payload["publicStatus"]["eligibility"]["status"], "closed")
        self.assertEqual(
            decision_payload["publicStatus"]["blockers"],
            ["challenge_review_already_closed"],
        )

        final_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=case_id)
        self.assertIsNotNone(final_job)
        assert final_job is not None
        self.assertEqual(final_job.status, "callback_reported")

        closed_status_resp = await self._get(
            app=app,
            path=(
                f"/internal/judge/cases/{case_id}/trust/challenges/public-status"
                "?dispatch_type=auto"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(closed_status_resp.status_code, 200)
        closed_status = closed_status_resp.json()
        self.assertEqual(closed_status["eligibility"]["status"], "closed")
        self.assertNotIn("challenge.request", closed_status["allowedActions"])

    async def test_trust_challenge_ops_queue_route_should_support_state_and_priority_filters(
        self,
    ) -> None:
        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)

        open_case_id = _unique_case_id(8451)
        closed_case_id = _unique_case_id(8452)
        passive_case_id = _unique_case_id(8453)

        for case_id in (open_case_id, closed_case_id, passive_case_id):
            final_resp = await self._post_json(
                app=app,
                path="/internal/judge/v3/final/dispatch",
                payload=_build_final_request(
                    case_id=case_id,
                    idempotency_key=f"final:{case_id}",
                ).model_dump(mode="json"),
                internal_key=runtime.settings.ai_internal_key,
            )
            self.assertEqual(final_resp.status_code, 200)

        open_request_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/cases/{open_case_id}/trust/challenges/request"
                "?dispatch_type=auto&reason_code=manual_challenge&reason=open_case"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(open_request_resp.status_code, 200)
        open_challenge_id = open_request_resp.json()["challengeId"]

        closed_request_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/cases/{closed_case_id}/trust/challenges/request"
                "?dispatch_type=auto&reason_code=manual_challenge&reason=closed_case"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(closed_request_resp.status_code, 200)
        closed_challenge_id = closed_request_resp.json()["challengeId"]
        closed_decision_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/cases/{closed_case_id}/trust/challenges/{closed_challenge_id}/decision"
                "?dispatch_type=auto&decision=uphold&actor=ops&reason=verified"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(closed_decision_resp.status_code, 200)

        open_queue_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/trust/challenges/ops-queue"
                "?dispatch_type=auto&challenge_state=open&sort_by=priority_score"
                "&sort_order=desc&scan_limit=300&offset=0&limit=20"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(open_queue_resp.status_code, 200)
        open_queue_payload = open_queue_resp.json()
        self.assertGreaterEqual(open_queue_payload["count"], 1)
        self.assertGreaterEqual(open_queue_payload["returned"], 1)
        open_case_item = next(
            item for item in open_queue_payload["items"] if item["caseId"] == open_case_id
        )
        self.assertEqual(open_case_item["challengeReview"]["state"], "under_internal_review")
        self.assertEqual(open_case_item["challengeReview"]["activeChallengeId"], open_challenge_id)
        self.assertEqual(open_case_item["review"]["state"], "pending_review")
        self.assertIn(
            open_case_item["priorityProfile"]["level"],
            {"medium", "high"},
        )
        self.assertIn("trust.challenge.decide", open_case_item["actionHints"])
        self.assertIn("review.queue.decide", open_case_item["actionHints"])
        self.assertIn(
            f"/internal/judge/cases/{open_case_id}/trust/challenges/{open_challenge_id}/decision",
            str(open_case_item["actionPaths"]["decisionPath"]),
        )
        self.assertEqual(open_queue_payload["filters"]["challengeState"], "open")
        self.assertEqual(open_queue_payload["filters"]["sortBy"], "priority_score")

        closed_queue_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/trust/challenges/ops-queue"
                "?dispatch_type=auto&challenge_state=challenge_closed"
                "&review_state=approved&sort_by=case_id&sort_order=asc"
                "&scan_limit=300&offset=0&limit=20"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(closed_queue_resp.status_code, 200)
        closed_queue_payload = closed_queue_resp.json()
        self.assertGreaterEqual(closed_queue_payload["count"], 1)
        closed_case_item = next(
            item for item in closed_queue_payload["items"] if item["caseId"] == closed_case_id
        )
        self.assertEqual(closed_case_item["challengeReview"]["state"], "challenge_closed")
        self.assertEqual(closed_case_item["review"]["state"], "approved")
        self.assertEqual(closed_case_item["review"]["workflowStatus"], "callback_reported")
        self.assertIsNone(closed_case_item["actionPaths"]["decisionPath"])
        self.assertEqual(closed_queue_payload["filters"]["reviewState"], "approved")

    async def test_trust_challenge_ops_queue_route_should_validate_query_values(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)

        invalid_state_resp = await self._get(
            app=app,
            path="/internal/judge/trust/challenges/ops-queue?challenge_state=invalid",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(invalid_state_resp.status_code, 422)
        self.assertIn("invalid_trust_challenge_state", invalid_state_resp.text)

        invalid_priority_resp = await self._get(
            app=app,
            path="/internal/judge/trust/challenges/ops-queue?priority_level=extreme",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(invalid_priority_resp.status_code, 422)
        self.assertIn("invalid_trust_priority_level", invalid_priority_resp.text)

        invalid_sort_resp = await self._get(
            app=app,
            path="/internal/judge/trust/challenges/ops-queue?sort_by=unknown",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(invalid_sort_resp.status_code, 422)
        self.assertIn("invalid_trust_sort_by", invalid_sort_resp.text)

    async def test_trust_challenge_ops_queue_route_should_return_500_when_contract_validation_fails(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)

        with patch(
            "app.applications.bootstrap_review_alert_trust_payload_helpers."
            "validate_trust_challenge_queue_contract_v3",
            side_effect=ValueError("trust_challenge_queue_missing_keys:items"),
        ):
            resp = await self._get(
                app=app,
                path="/internal/judge/trust/challenges/ops-queue?dispatch_type=final",
                internal_key=runtime.settings.ai_internal_key,
            )

        self.assertEqual(resp.status_code, 500)
        detail = resp.json()["detail"]
        self.assertEqual(detail["code"], "trust_challenge_ops_queue_contract_violation")
        self.assertIn("trust_challenge_queue_missing_keys:items", detail["message"])

if __name__ == "__main__":
    unittest.main()
