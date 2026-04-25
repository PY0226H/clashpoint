from __future__ import annotations

import unittest
from unittest.mock import patch

from app.app_factory import create_app, create_runtime
from app.applications.fairness_case_contract import (
    CASE_FAIRNESS_AGGREGATIONS_KEYS,
    CASE_FAIRNESS_DETAIL_TOP_LEVEL_KEYS,
    CASE_FAIRNESS_FILTER_KEYS,
    CASE_FAIRNESS_ITEM_KEYS,
    CASE_FAIRNESS_LIST_TOP_LEVEL_KEYS,
    validate_case_fairness_detail_contract,
    validate_case_fairness_list_contract,
)
from app.applications.fairness_dashboard_contract import (
    FAIRNESS_DASHBOARD_FILTER_KEYS,
    FAIRNESS_DASHBOARD_GATE_DISTRIBUTION_KEYS,
    FAIRNESS_DASHBOARD_OVERVIEW_KEYS,
    FAIRNESS_DASHBOARD_TOP_LEVEL_KEYS,
    FAIRNESS_DASHBOARD_TRENDS_KEYS,
    validate_fairness_dashboard_contract,
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


class AppFactoryFairnessRouteTests(
    AppFactoryRouteTestMixin,
    unittest.IsolatedAsyncioTestCase,
):

    async def test_fairness_benchmark_routes_should_persist_and_list_runs(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        run_id = f"run-{_unique_case_id(7601)}"

        post_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": run_id,
                "policy_version": "fairness-benchmark-v1",
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "needs_real_env_reconfirm": True,
                "needs_remediation": False,
                "metrics": {
                    "sample_size": 384,
                    "draw_rate": 0.2,
                    "side_bias_delta": 0.04,
                    "appeal_overturn_rate": 0.07,
                },
                "thresholds": {
                    "draw_rate_max": 0.3,
                    "side_bias_delta_max": 0.08,
                    "appeal_overturn_rate_max": 0.12,
                },
                "summary": {
                    "note": "local reference frozen",
                },
                "source": "harness_freeze_script",
                "reported_by": "ci",
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(post_resp.status_code, 200)
        post_payload = post_resp.json()
        self.assertTrue(post_payload["ok"])
        self.assertEqual(post_payload["item"]["runId"], run_id)
        self.assertEqual(post_payload["item"]["status"], "local_reference_frozen")
        self.assertIsNone(post_payload["alert"])
        self.assertEqual(post_payload["drift"]["baselineRunId"], None)

        list_resp = await self._get(
            app=app,
            path="/internal/judge/fairness/benchmark-runs?policy_version=fairness-benchmark-v1",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(list_resp.status_code, 200)
        list_payload = list_resp.json()
        self.assertGreaterEqual(list_payload["count"], 1)
        self.assertTrue(any(item["runId"] == run_id for item in list_payload["items"]))

        fact_runs = await runtime.workflow_runtime.facts.list_fairness_benchmark_runs(
            policy_version="fairness-benchmark-v1",
            limit=20,
        )
        self.assertTrue(any(item.run_id == run_id for item in fact_runs))

    async def test_fairness_benchmark_routes_should_preserve_pending_real_samples(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        run_id = f"run-{_unique_case_id(7602)}"

        post_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": run_id,
                "policy_version": "fairness-benchmark-v1",
                "environment_mode": "real",
                "status": "pending_real_samples",
                "threshold_decision": "pending",
                "needs_real_env_reconfirm": True,
                "summary": {
                    "note": "real sample manifest missing",
                    "realSampleManifest": {
                        "manifestRef": "",
                        "status": "missing",
                        "ready": False,
                    },
                    "releaseGateInputReady": False,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(post_resp.status_code, 200)
        post_payload = post_resp.json()
        self.assertEqual(post_payload["item"]["status"], "pending_real_samples")
        self.assertEqual(
            post_payload["item"]["summary"]["realSampleManifest"]["status"],
            "missing",
        )

        list_resp = await self._get(
            app=app,
            path="/internal/judge/fairness/benchmark-runs?status=pending_real_samples",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(list_resp.status_code, 200)
        list_payload = list_resp.json()
        self.assertTrue(any(item["runId"] == run_id for item in list_payload["items"]))

    async def test_fairness_shadow_routes_should_persist_list_and_raise_alert(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        benchmark_run_id = f"run-{_unique_case_id(7605)}"
        shadow_run_id = f"shadow-{_unique_case_id(7606)}"
        shadow_breach_run_id = f"shadow-{_unique_case_id(7607)}"

        benchmark_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": benchmark_run_id,
                "policy_version": "fairness-benchmark-v1",
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "metrics": {
                    "sample_size": 384,
                    "draw_rate": 0.2,
                    "side_bias_delta": 0.04,
                    "appeal_overturn_rate": 0.07,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(benchmark_resp.status_code, 200)

        shadow_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/shadow-runs",
            payload={
                "run_id": shadow_run_id,
                "policy_version": "fairness-benchmark-v1",
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "metrics": {
                    "sample_size": 200,
                    "winner_flip_rate": 0.05,
                    "score_shift_delta": 0.08,
                    "review_required_delta": 0.04,
                },
                "thresholds": {
                    "winner_flip_rate_max": 0.1,
                    "score_shift_delta_max": 0.2,
                    "review_required_delta_max": 0.1,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(shadow_resp.status_code, 200)
        shadow_payload = shadow_resp.json()
        self.assertTrue(shadow_payload["ok"])
        self.assertEqual(shadow_payload["item"]["runId"], shadow_run_id)
        self.assertEqual(shadow_payload["item"]["benchmarkRunId"], benchmark_run_id)
        self.assertEqual(shadow_payload["breaches"], [])
        self.assertIsNone(shadow_payload["alert"])

        list_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/fairness/shadow-runs"
                "?policy_version=fairness-benchmark-v1&benchmark_run_id="
                f"{benchmark_run_id}"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(list_resp.status_code, 200)
        list_payload = list_resp.json()
        self.assertGreaterEqual(list_payload["count"], 1)
        self.assertTrue(any(item["runId"] == shadow_run_id for item in list_payload["items"]))

        breached_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/shadow-runs",
            payload={
                "run_id": shadow_breach_run_id,
                "policy_version": "fairness-benchmark-v1",
                "environment_mode": "local_reference",
                "status": "threshold_violation",
                "threshold_decision": "violated",
                "benchmark_run_id": benchmark_run_id,
                "metrics": {
                    "sample_size": 200,
                    "winner_flip_rate": 0.25,
                    "score_shift_delta": 0.35,
                    "review_required_delta": 0.18,
                },
                "thresholds": {
                    "winner_flip_rate_max": 0.1,
                    "score_shift_delta_max": 0.2,
                    "review_required_delta_max": 0.1,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(breached_resp.status_code, 200)
        breached_payload = breached_resp.json()
        self.assertIn("winner_flip_rate", breached_payload["breaches"])
        self.assertIn("score_shift_delta", breached_payload["breaches"])
        self.assertIn("review_required_delta", breached_payload["breaches"])
        self.assertIsNotNone(breached_payload["alert"])
        self.assertEqual(
            breached_payload["alert"]["type"],
            "fairness_shadow_threshold_violation",
        )

        fact_shadow_runs = await runtime.workflow_runtime.facts.list_fairness_shadow_runs(
            policy_version="fairness-benchmark-v1",
            limit=20,
        )
        self.assertTrue(any(item.run_id == shadow_breach_run_id for item in fact_shadow_runs))

    async def test_fairness_benchmark_threshold_breach_should_raise_alert_outbox(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        baseline_run_id = f"run-{_unique_case_id(7611)}"
        breached_run_id = f"run-{_unique_case_id(7612)}"

        baseline_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": baseline_run_id,
                "policy_version": "fairness-benchmark-v1",
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "metrics": {
                    "sample_size": 384,
                    "draw_rate": 0.2,
                    "side_bias_delta": 0.04,
                    "appeal_overturn_rate": 0.07,
                },
                "thresholds": {
                    "draw_rate_max": 0.3,
                    "side_bias_delta_max": 0.08,
                    "appeal_overturn_rate_max": 0.12,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(baseline_resp.status_code, 200)

        breached_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": breached_run_id,
                "policy_version": "fairness-benchmark-v1",
                "environment_mode": "local_reference",
                "status": "threshold_violation",
                "threshold_decision": "violated",
                "metrics": {
                    "sample_size": 384,
                    "draw_rate": 0.41,
                    "side_bias_delta": 0.04,
                    "appeal_overturn_rate": 0.07,
                },
                "thresholds": {
                    "draw_rate_max": 0.3,
                    "side_bias_delta_max": 0.08,
                    "appeal_overturn_rate_max": 0.12,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(breached_resp.status_code, 200)
        breached_payload = breached_resp.json()
        self.assertTrue(breached_payload["drift"]["hasThresholdBreach"])
        self.assertIn("draw_rate", breached_payload["drift"]["thresholdBreaches"])
        self.assertIsNotNone(breached_payload["alert"])
        self.assertEqual(
            breached_payload["alert"]["type"],
            "fairness_benchmark_threshold_violation",
        )
        self.assertEqual(
            breached_payload["drift"]["baselineRunId"],
            baseline_run_id,
        )

        outbox_resp = await self._get(
            app=app,
            path="/internal/judge/alerts/outbox",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(outbox_resp.status_code, 200)
        outbox_items = outbox_resp.json()["items"]
        self.assertTrue(
            any(
                item.get("payload", {}).get("alertType")
                == "fairness_benchmark_threshold_violation"
                for item in outbox_items
            )
        )

        fact_alerts = await runtime.workflow_runtime.facts.list_audit_alerts(
            job_id=0,
            limit=20,
        )
        self.assertTrue(
            any(item.alert_type == "fairness_benchmark_threshold_violation" for item in fact_alerts)
        )

    async def test_fairness_case_read_model_routes_should_return_case_and_list_views(self) -> None:
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
        case_id = _unique_case_id(7621)
        phase_req = _build_phase_request(
            case_id=case_id,
            idempotency_key=f"phase:{case_id}",
            judge_policy_version="v3-default",
        )
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(
            case_id=case_id,
            idempotency_key=f"final:{case_id}",
            judge_policy_version="v3-default",
        )
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        run_id = f"run-{_unique_case_id(7622)}"
        benchmark_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": run_id,
                "policy_version": "v3-default",
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "metrics": {
                    "sample_size": 384,
                    "draw_rate": 0.2,
                    "side_bias_delta": 0.03,
                    "appeal_overturn_rate": 0.06,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(benchmark_resp.status_code, 200)
        benchmark_run_id = benchmark_resp.json()["item"]["runId"]

        shadow_run_id = f"shadow-{_unique_case_id(7624)}"
        shadow_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/shadow-runs",
            payload={
                "run_id": shadow_run_id,
                "policy_version": "v3-default",
                "benchmark_run_id": benchmark_run_id,
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "metrics": {
                    "sample_size": 200,
                    "winner_flip_rate": 0.05,
                    "score_shift_delta": 0.08,
                    "review_required_delta": 0.03,
                },
                "thresholds": {
                    "winner_flip_rate_max": 0.1,
                    "score_shift_delta_max": 0.2,
                    "review_required_delta_max": 0.1,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(shadow_resp.status_code, 200)

        detail_resp = await self._get(
            app=app,
            path=f"/internal/judge/fairness/cases/{case_id}?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(detail_resp.status_code, 200)
        detail_payload = detail_resp.json()
        self.assertEqual(detail_payload["caseId"], case_id)
        self.assertEqual(detail_payload["dispatchType"], "final")
        self.assertEqual(set(detail_payload.keys()), set(CASE_FAIRNESS_DETAIL_TOP_LEVEL_KEYS))
        validate_case_fairness_detail_contract(detail_payload)
        item = detail_payload["item"]
        self.assertEqual(set(item.keys()), set(CASE_FAIRNESS_ITEM_KEYS))
        self.assertEqual(item["caseId"], case_id)
        self.assertIn(item["gateConclusion"], {"pass_through", "blocked_to_draw"})
        self.assertIsInstance(item["panelDisagreement"]["runtimeProfiles"], dict)
        self.assertIn("judgeA", item["panelDisagreement"]["runtimeProfiles"])
        self.assertEqual(item["driftSummary"]["latestRun"]["runId"], run_id)
        self.assertEqual(item["shadowSummary"]["latestRun"]["runId"], shadow_run_id)
        self.assertFalse(item["shadowSummary"]["hasShadowBreach"])

        list_resp = await self._get(
            app=app,
            path="/internal/judge/fairness/cases?dispatch_type=final&limit=50",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(list_resp.status_code, 200)
        list_payload = list_resp.json()
        self.assertEqual(set(list_payload.keys()), set(CASE_FAIRNESS_LIST_TOP_LEVEL_KEYS))
        self.assertEqual(set(list_payload["aggregations"].keys()), set(CASE_FAIRNESS_AGGREGATIONS_KEYS))
        self.assertEqual(set(list_payload["filters"].keys()), set(CASE_FAIRNESS_FILTER_KEYS))
        validate_case_fairness_list_contract(list_payload)
        self.assertGreaterEqual(list_payload["count"], 1)
        self.assertGreaterEqual(list_payload["returned"], 1)
        self.assertTrue(any(row["caseId"] == case_id for row in list_payload["items"]))
        self.assertEqual(list_payload["filters"]["dispatchType"], "final")
        self.assertEqual(list_payload["aggregations"]["totalMatched"], list_payload["count"])
        self.assertGreaterEqual(
            list_payload["aggregations"]["gateConclusionCounts"][item["gateConclusion"]],
            1,
        )
        self.assertGreaterEqual(
            list_payload["aggregations"]["policyVersionCounts"]["v3-default"],
            1,
        )

        challenge_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/cases/{case_id}/trust/challenges/request"
                "?dispatch_type=auto&reason_code=manual_challenge&requested_by=ops&auto_accept=true"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(challenge_resp.status_code, 200)
        challenge_payload = challenge_resp.json()
        self.assertEqual(challenge_payload["item"]["challengeState"], "under_internal_review")

        filtered_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/fairness/cases"
                f"?dispatch_type=final&gate_conclusion={item['gateConclusion']}"
                "&challenge_state=under_internal_review&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(filtered_resp.status_code, 200)
        filtered_payload = filtered_resp.json()
        self.assertGreaterEqual(filtered_payload["count"], 1)
        self.assertTrue(any(row["caseId"] == case_id for row in filtered_payload["items"]))
        self.assertEqual(filtered_payload["filters"]["sortBy"], "updated_at")
        self.assertEqual(filtered_payload["filters"]["sortOrder"], "desc")

        drift_filter_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/fairness/cases"
                "?dispatch_type=final&policy_version=v3-default"
                "&has_threshold_breach=false&has_drift_breach=false&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(drift_filter_resp.status_code, 200)
        drift_filter_payload = drift_filter_resp.json()
        self.assertGreaterEqual(drift_filter_payload["count"], 1)
        self.assertTrue(any(row["caseId"] == case_id for row in drift_filter_payload["items"]))
        self.assertEqual(drift_filter_payload["filters"]["policyVersion"], "v3-default")
        self.assertFalse(drift_filter_payload["filters"]["hasThresholdBreach"])
        self.assertFalse(drift_filter_payload["filters"]["hasDriftBreach"])

        shadow_filter_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/fairness/cases"
                "?dispatch_type=final&policy_version=v3-default"
                "&has_shadow_breach=false&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(shadow_filter_resp.status_code, 200)
        shadow_filter_payload = shadow_filter_resp.json()
        self.assertGreaterEqual(shadow_filter_payload["count"], 1)
        self.assertTrue(any(row["caseId"] == case_id for row in shadow_filter_payload["items"]))
        self.assertFalse(shadow_filter_payload["filters"]["hasShadowBreach"])

        case_id_2 = _unique_case_id(7623)
        phase_req_2 = _build_phase_request(
            case_id=case_id_2,
            idempotency_key=f"phase:{case_id_2}",
            judge_policy_version="v3-default",
        )
        phase_resp_2 = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req_2.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp_2.status_code, 200)
        final_req_2 = _build_final_request(
            case_id=case_id_2,
            idempotency_key=f"final:{case_id_2}",
            judge_policy_version="v3-default",
        )
        final_resp_2 = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req_2.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp_2.status_code, 200)

        page_resp = await self._get(
            app=app,
            path="/internal/judge/fairness/cases?dispatch_type=final&offset=1&limit=1",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(page_resp.status_code, 200)
        page_payload = page_resp.json()
        self.assertGreaterEqual(page_payload["count"], 2)
        self.assertEqual(page_payload["returned"], 1)
        self.assertEqual(page_payload["filters"]["offset"], 1)

        open_review_resp = await self._get(
            app=app,
            path="/internal/judge/fairness/cases?dispatch_type=final&has_open_review=true&limit=50",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(open_review_resp.status_code, 200)
        open_review_payload = open_review_resp.json()
        self.assertTrue(any(row["caseId"] == case_id for row in open_review_payload["items"]))
        self.assertTrue(all(bool(row["challengeLink"]["hasOpenReview"]) for row in open_review_payload["items"]))
        self.assertGreaterEqual(open_review_payload["aggregations"]["openReviewCount"], 1)
        self.assertGreaterEqual(open_review_payload["aggregations"]["withChallengeCount"], 1)

        sorted_resp = await self._get(
            app=app,
            path="/internal/judge/fairness/cases?dispatch_type=final&sort_by=updated_at&sort_order=asc&limit=2",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(sorted_resp.status_code, 200)
        sorted_payload = sorted_resp.json()
        self.assertEqual(sorted_payload["returned"], 2)
        self.assertEqual(sorted_payload["filters"]["sortBy"], "updated_at")
        self.assertEqual(sorted_payload["filters"]["sortOrder"], "asc")
        self.assertEqual(sorted_payload["aggregations"]["totalMatched"], sorted_payload["count"])
        ordered_case_ids = [int(row["caseId"]) for row in sorted_payload["items"]]
        self.assertEqual(ordered_case_ids[0], case_id)
        self.assertEqual(ordered_case_ids[1], case_id_2)

        invalid_gate_resp = await self._get(
            app=app,
            path="/internal/judge/fairness/cases?gate_conclusion=bad-value",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(invalid_gate_resp.status_code, 422)
        self.assertIn("invalid_gate_conclusion", invalid_gate_resp.text)

        invalid_challenge_resp = await self._get(
            app=app,
            path="/internal/judge/fairness/cases?challenge_state=bad-value",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(invalid_challenge_resp.status_code, 422)
        self.assertIn("invalid_challenge_state", invalid_challenge_resp.text)

        invalid_sort_by_resp = await self._get(
            app=app,
            path="/internal/judge/fairness/cases?sort_by=bad-value",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(invalid_sort_by_resp.status_code, 422)
        self.assertIn("invalid_sort_by", invalid_sort_by_resp.text)

        invalid_sort_order_resp = await self._get(
            app=app,
            path="/internal/judge/fairness/cases?sort_order=bad-value",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(invalid_sort_order_resp.status_code, 422)
        self.assertIn("invalid_sort_order", invalid_sort_order_resp.text)

    async def test_fairness_case_list_route_should_return_500_when_contract_validation_fails(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)

        with patch(
            "app.app_factory.validate_case_fairness_list_contract_v3",
            side_effect=ValueError("fairness_case_list_missing_keys:items"),
        ):
            resp = await self._get(
                app=app,
                path="/internal/judge/fairness/cases?dispatch_type=final",
                internal_key=runtime.settings.ai_internal_key,
            )

        self.assertEqual(resp.status_code, 500)
        detail = resp.json()["detail"]
        self.assertEqual(detail["code"], "fairness_case_list_contract_violation")
        self.assertIn("fairness_case_list_missing_keys:items", detail["message"])

    async def test_fairness_case_detail_route_should_return_500_when_contract_validation_fails(
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
        case_id = _unique_case_id(7625)
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=_build_phase_request(
                case_id=case_id,
                idempotency_key=f"phase:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=_build_final_request(
                case_id=case_id,
                idempotency_key=f"final:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        with patch(
            "app.app_factory.validate_case_fairness_detail_contract_v3",
            side_effect=ValueError("fairness_case_detail_missing_keys:item"),
        ):
            resp = await self._get(
                app=app,
                path=f"/internal/judge/fairness/cases/{case_id}?dispatch_type=final",
                internal_key=runtime.settings.ai_internal_key,
            )

        self.assertEqual(resp.status_code, 500)
        detail = resp.json()["detail"]
        self.assertEqual(detail["code"], "fairness_case_detail_contract_violation")
        self.assertIn("fairness_case_detail_missing_keys:item", detail["message"])

    async def test_fairness_dashboard_route_should_return_overview_trends_and_top_risk(self) -> None:
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
        case_id = _unique_case_id(7841)

        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=_build_phase_request(
                case_id=case_id,
                idempotency_key=f"phase:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=_build_final_request(
                case_id=case_id,
                idempotency_key=f"final:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        benchmark_run_id = f"run-{_unique_case_id(7842)}"
        benchmark_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": benchmark_run_id,
                "policy_version": "v3-default",
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "metrics": {
                    "sample_size": 384,
                    "draw_rate": 0.2,
                    "side_bias_delta": 0.03,
                    "appeal_overturn_rate": 0.06,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(benchmark_resp.status_code, 200)

        shadow_run_id = f"shadow-{_unique_case_id(7843)}"
        shadow_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/shadow-runs",
            payload={
                "run_id": shadow_run_id,
                "policy_version": "v3-default",
                "benchmark_run_id": benchmark_run_id,
                "environment_mode": "local_reference",
                "status": "threshold_violation",
                "threshold_decision": "violated",
                "metrics": {
                    "sample_size": 200,
                    "winner_flip_rate": 0.22,
                    "score_shift_delta": 0.33,
                    "review_required_delta": 0.18,
                },
                "thresholds": {
                    "winner_flip_rate_max": 0.1,
                    "score_shift_delta_max": 0.2,
                    "review_required_delta_max": 0.1,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(shadow_resp.status_code, 200)

        dashboard_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/fairness/dashboard"
                "?dispatch_type=final&policy_version=v3-default"
                "&window_days=7&top_limit=10&case_scan_limit=200"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(dashboard_resp.status_code, 200)
        payload = dashboard_resp.json()
        self.assertEqual(set(payload.keys()), set(FAIRNESS_DASHBOARD_TOP_LEVEL_KEYS))
        self.assertEqual(
            set(payload["overview"].keys()),
            set(FAIRNESS_DASHBOARD_OVERVIEW_KEYS),
        )
        self.assertEqual(
            set(payload["gateDistribution"].keys()),
            set(FAIRNESS_DASHBOARD_GATE_DISTRIBUTION_KEYS),
        )
        self.assertEqual(
            set(payload["trends"].keys()),
            set(FAIRNESS_DASHBOARD_TRENDS_KEYS),
        )
        self.assertEqual(
            set(payload["filters"].keys()),
            set(FAIRNESS_DASHBOARD_FILTER_KEYS),
        )
        validate_fairness_dashboard_contract(payload)
        self.assertIsInstance(payload["overview"], dict)
        self.assertIsInstance(payload["trends"], dict)
        self.assertIsInstance(payload["topRiskCases"], list)
        self.assertIsInstance(payload["gateDistribution"], dict)
        self.assertGreaterEqual(payload["overview"]["totalMatched"], 1)
        self.assertGreaterEqual(payload["overview"]["shadowBreachCount"], 1)
        self.assertGreaterEqual(
            payload["gateDistribution"]["pass_through"]
            + payload["gateDistribution"]["blocked_to_draw"],
            1,
        )
        self.assertTrue(any(row["caseId"] == case_id for row in payload["topRiskCases"]))
        self.assertTrue(
            any(
                row["caseId"] == case_id and "shadow_breach" in row["riskTags"]
                for row in payload["topRiskCases"]
            )
        )
        self.assertTrue(
            any(
                row.get("runId") == benchmark_run_id
                for row in payload["trends"]["benchmarkRuns"]
            )
        )
        self.assertTrue(
            any(
                row.get("runId") == shadow_run_id
                for row in payload["trends"]["shadowRuns"]
            )
        )
        self.assertEqual(payload["filters"]["dispatchType"], "final")
        self.assertEqual(payload["filters"]["policyVersion"], "v3-default")
        self.assertEqual(payload["filters"]["windowDays"], 7)
        self.assertEqual(payload["filters"]["topLimit"], 10)

    async def test_fairness_dashboard_route_should_return_500_when_contract_validation_fails(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)

        with patch(
            "app.app_factory.validate_fairness_dashboard_contract_v3",
            side_effect=ValueError("fairness_dashboard_overview_missing_keys"),
        ):
            resp = await self._get(
                app=app,
                path="/internal/judge/fairness/dashboard?dispatch_type=final",
                internal_key=runtime.settings.ai_internal_key,
            )

        self.assertEqual(resp.status_code, 500)
        detail = resp.json()["detail"]
        self.assertEqual(detail["code"], "fairness_dashboard_contract_violation")
        self.assertIn(
            "fairness_dashboard_overview_missing_keys",
            detail["message"],
        )

    async def test_fairness_calibration_pack_route_should_return_thresholds_drift_and_risks(
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
        case_id = _unique_case_id(7851)

        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=_build_phase_request(
                case_id=case_id,
                idempotency_key=f"phase:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=_build_final_request(
                case_id=case_id,
                idempotency_key=f"final:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        baseline_run_id = f"run-{_unique_case_id(7852)}"
        baseline_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": baseline_run_id,
                "policy_version": "v3-default",
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "metrics": {
                    "sample_size": 400,
                    "draw_rate": 0.2,
                    "side_bias_delta": 0.03,
                    "appeal_overturn_rate": 0.05,
                },
                "thresholds": {
                    "draw_rate_max": 0.3,
                    "side_bias_delta_max": 0.08,
                    "appeal_overturn_rate_max": 0.1,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(baseline_resp.status_code, 200)

        breached_run_id = f"run-{_unique_case_id(7853)}"
        breached_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": breached_run_id,
                "policy_version": "v3-default",
                "environment_mode": "local_reference",
                "status": "threshold_violation",
                "threshold_decision": "violated",
                "metrics": {
                    "sample_size": 420,
                    "draw_rate": 0.45,
                    "side_bias_delta": 0.04,
                    "appeal_overturn_rate": 0.08,
                },
                "thresholds": {
                    "draw_rate_max": 0.3,
                    "side_bias_delta_max": 0.08,
                    "appeal_overturn_rate_max": 0.1,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(breached_resp.status_code, 200)

        shadow_run_id = f"shadow-{_unique_case_id(7854)}"
        shadow_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/shadow-runs",
            payload={
                "run_id": shadow_run_id,
                "policy_version": "v3-default",
                "benchmark_run_id": breached_run_id,
                "environment_mode": "local_reference",
                "status": "threshold_violation",
                "threshold_decision": "violated",
                "metrics": {
                    "sample_size": 200,
                    "winner_flip_rate": 0.26,
                    "score_shift_delta": 0.3,
                    "review_required_delta": 0.19,
                },
                "thresholds": {
                    "winner_flip_rate_max": 0.1,
                    "score_shift_delta_max": 0.2,
                    "review_required_delta_max": 0.1,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(shadow_resp.status_code, 200)

        pack_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/fairness/calibration-pack"
                "?dispatch_type=final&policy_version=v3-default"
                "&case_scan_limit=200&risk_limit=30"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(pack_resp.status_code, 200)
        payload = pack_resp.json()

        self.assertIsInstance(payload["overview"], dict)
        self.assertIsInstance(payload["thresholdSuggestions"], dict)
        self.assertIsInstance(payload["driftSummary"], dict)
        self.assertIsInstance(payload["riskItems"], list)
        self.assertIsInstance(payload["onEnvInputTemplate"], dict)
        self.assertGreaterEqual(payload["overview"]["benchmarkRunCount"], 2)
        self.assertGreaterEqual(payload["overview"]["shadowRunCount"], 1)
        self.assertGreaterEqual(payload["overview"]["highRiskCount"], 1)
        self.assertEqual(payload["overview"]["latestBenchmarkRunId"], breached_run_id)
        self.assertEqual(payload["overview"]["latestShadowRunId"], shadow_run_id)
        self.assertEqual(payload["filters"]["policyVersion"], "v3-default")
        self.assertEqual(payload["filters"]["riskLimit"], 30)

        threshold_suggestions = payload["thresholdSuggestions"]
        self.assertEqual(threshold_suggestions["method"], "local_observed_max_with_margin")
        self.assertIsNotNone(
            threshold_suggestions["benchmark"]["drawRateMaxSuggested"]
        )
        self.assertIsNotNone(
            threshold_suggestions["shadow"]["winnerFlipRateMaxSuggested"]
        )

        drift_summary = payload["driftSummary"]
        self.assertEqual(drift_summary["benchmark"]["latestRunId"], breached_run_id)
        self.assertEqual(drift_summary["shadow"]["latestRunId"], shadow_run_id)
        self.assertTrue(drift_summary["benchmark"]["hasThresholdBreach"])
        self.assertTrue(drift_summary["shadow"]["hasBreach"])

        risk_types = {row.get("riskType") for row in payload["riskItems"]}
        self.assertIn("benchmark_threshold_violation", risk_types)
        self.assertIn("shadow_threshold_violation", risk_types)
        self.assertEqual(
            payload["onEnvInputTemplate"]["envMarker"]["REAL_CALIBRATION_ENV_READY"],
            "true",
        )
        self.assertTrue(
            any(
                "real-env pass" in str(note)
                for note in payload["onEnvInputTemplate"]["notes"]
            )
        )

    async def test_policy_calibration_advisor_route_should_return_gate_and_advisory_actions(
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
        case_id = _unique_case_id(7861)

        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=_build_phase_request(
                case_id=case_id,
                idempotency_key=f"phase:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=_build_final_request(
                case_id=case_id,
                idempotency_key=f"final:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        benchmark_run_id = f"run-{_unique_case_id(7862)}"
        benchmark_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": benchmark_run_id,
                "policy_version": "v3-default",
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "metrics": {
                    "sample_size": 400,
                    "draw_rate": 0.18,
                    "side_bias_delta": 0.03,
                    "appeal_overturn_rate": 0.05,
                },
                "thresholds": {
                    "draw_rate_max": 0.3,
                    "side_bias_delta_max": 0.08,
                    "appeal_overturn_rate_max": 0.1,
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(benchmark_resp.status_code, 200)

        shadow_run_id = f"shadow-{_unique_case_id(7863)}"
        shadow_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/shadow-runs",
            payload={
                "run_id": shadow_run_id,
                "policy_version": "v3-default",
                "benchmark_run_id": benchmark_run_id,
                "environment_mode": "local_reference",
                "status": "threshold_violation",
                "threshold_decision": "violated",
                "metrics": {
                    "sample_size": 220,
                    "winner_flip_rate": 0.22,
                    "score_shift_delta": 0.31,
                    "review_required_delta": 0.16,
                },
                "thresholds": {
                    "winner_flip_rate_max": 0.1,
                    "score_shift_delta_max": 0.2,
                    "review_required_delta_max": 0.1,
                },
                "summary": {
                    "hasBreach": True,
                    "breaches": ["winner_flip_rate_exceeded"],
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(shadow_resp.status_code, 200)

        advisor_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/fairness/policy-calibration-advisor"
                "?dispatch_type=final&policy_version=v3-default"
                "&case_scan_limit=200&risk_limit=30"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(advisor_resp.status_code, 200)
        payload = advisor_resp.json()

        self.assertIsInstance(payload["overview"], dict)
        self.assertIsInstance(payload["thresholdSuggestions"], dict)
        self.assertIsInstance(payload["driftSummary"], dict)
        self.assertIsInstance(payload["releaseGate"], dict)
        self.assertIsInstance(payload["recommendedActions"], list)
        self.assertIsInstance(payload["riskItems"], list)
        self.assertEqual(payload["overview"]["policyVersion"], "v3-default")
        self.assertEqual(payload["overview"]["latestBenchmarkRunId"], benchmark_run_id)
        self.assertEqual(payload["overview"]["latestShadowRunId"], shadow_run_id)

        release_gate = payload["releaseGate"]
        self.assertFalse(release_gate["passed"])
        self.assertEqual(
            release_gate["code"],
            "registry_fairness_gate_shadow_threshold_not_accepted",
        )

        action_ids = {
            str(row.get("actionId") or "")
            for row in payload["recommendedActions"]
            if isinstance(row, dict)
        }
        self.assertIn("prepare_candidate_policy_patch", action_ids)
        self.assertIn("manual_review_before_activation", action_ids)
        self.assertTrue(
            all(
                bool(row.get("advisoryOnly"))
                for row in payload["recommendedActions"]
                if isinstance(row, dict)
            )
        )
        self.assertTrue(
            any(
                "advisory only" in str(note).lower()
                for note in payload["notes"]
            )
        )
        self.assertEqual(payload["filters"]["policyVersion"], "v3-default")
        self.assertEqual(payload["filters"]["effectivePolicyVersion"], "v3-default")
        self.assertEqual(payload["filters"]["riskLimit"], 30)

if __name__ == "__main__":
    unittest.main()
