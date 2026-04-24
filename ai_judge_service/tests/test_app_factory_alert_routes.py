from __future__ import annotations

import unittest
from unittest.mock import patch

from app.app_factory import create_app, create_runtime

from tests.app_factory_test_helpers import (
    AppFactoryRouteTestMixin,
)
from tests.app_factory_test_helpers import (
    build_final_request as _build_final_request,
)
from tests.app_factory_test_helpers import (
    build_settings as _build_settings,
)
from tests.app_factory_test_helpers import (
    unique_case_id as _unique_case_id,
)


class AppFactoryAlertRouteTests(
    AppFactoryRouteTestMixin,
    unittest.IsolatedAsyncioTestCase,
):

    async def test_policy_registry_dependency_blocked_alert_should_emit_and_resolve_outbox(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        version = f"policy-dep-alert-{_unique_case_id(9215)}"

        blocked_publish = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-missing",
                    "toolRegistryVersion": "toolset-v3-default",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(blocked_publish.status_code, 422)
        blocked_detail = blocked_publish.json()["detail"]
        self.assertEqual(blocked_detail["code"], "registry_policy_dependency_invalid")
        blocked_alert = blocked_detail["alert"]
        self.assertEqual(blocked_alert["type"], "registry_dependency_health_blocked")
        self.assertEqual(blocked_alert["status"], "raised")

        outbox_after_blocked = await self._get(
            app=app,
            path="/internal/judge/alerts/outbox",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(outbox_after_blocked.status_code, 200)
        blocked_event = next(
            (
                item
                for item in outbox_after_blocked.json()["items"]
                if item.get("payload", {}).get("alertType")
                == "registry_dependency_health_blocked"
                and item.get("payload", {}).get("status") == "raised"
                and item.get("payload", {}).get("details", {}).get("version") == version
            ),
            None,
        )
        self.assertIsNotNone(blocked_event)
        open_trend_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/registries/policy/dependencies/health"
                "?include_all_versions=true&include_overview=false"
                "&include_trend=true&trend_status=open&trend_policy_version="
                f"{version}&trend_limit=20&trend_offset=0"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(open_trend_resp.status_code, 200)
        open_trend_payload = open_trend_resp.json()
        self.assertIsNone(open_trend_payload["dependencyOverview"])
        self.assertIsInstance(open_trend_payload["dependencyTrend"], dict)
        self.assertGreaterEqual(open_trend_payload["dependencyTrend"]["count"], 1)
        self.assertGreaterEqual(
            open_trend_payload["dependencyTrend"]["statusCounts"]["raised"],
            1,
        )
        self.assertTrue(
            all(
                row["policyVersion"] == version
                for row in open_trend_payload["dependencyTrend"]["items"]
            )
        )

        prompt_publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/prompt/publish",
            payload={
                "version": "promptset-dep-recover",
                "activate": False,
                "profile": {
                    "promptVersions": {
                        "summaryPromptVersion": "v3.a2a3.summary.v1",
                        "agent2PromptVersion": "v3.a6a7.bidirectional.v2",
                        "finalPipelineVersion": "v3-final-a9a10-rollup-v2",
                        "claimGraphVersion": "v1-claim-graph-bootstrap",
                    },
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(prompt_publish_resp.status_code, 200)

        recovered_publish = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": version,
                "activate": False,
                "reason": "dependency_recovered",
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-dep-recover",
                    "toolRegistryVersion": "toolset-v3-default",
                    "promptVersions": {
                        "summaryPromptVersion": "v3.a2a3.summary.v1",
                        "agent2PromptVersion": "v3.a6a7.bidirectional.v2",
                        "finalPipelineVersion": "v3-final-a9a10-rollup-v2",
                        "claimGraphVersion": "v1-claim-graph-bootstrap",
                    },
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(recovered_publish.status_code, 200)
        recovered_payload = recovered_publish.json()
        self.assertIsNotNone(recovered_payload["dependencyHealth"])
        self.assertTrue(recovered_payload["dependencyHealth"]["ok"])
        self.assertGreaterEqual(len(recovered_payload["resolvedDependencyAlerts"]), 1)

        outbox_after_recovered = await self._get(
            app=app,
            path="/internal/judge/alerts/outbox",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(outbox_after_recovered.status_code, 200)
        resolved_event = next(
            (
                item
                for item in outbox_after_recovered.json()["items"]
                if item.get("payload", {}).get("alertType")
                == "registry_dependency_health_blocked"
                and item.get("payload", {}).get("status") == "resolved"
                and item.get("payload", {}).get("details", {}).get("version") == version
            ),
            None,
        )
        self.assertIsNotNone(resolved_event)

        health_overview_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/registries/policy/dependencies/health"
                f"?policy_version={version}&include_all_versions=true&include_overview=true"
                "&overview_window_minutes=1440&limit=20"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(health_overview_resp.status_code, 200)
        health_overview_payload = health_overview_resp.json()
        overview = health_overview_payload["dependencyOverview"]
        self.assertIsInstance(overview, dict)
        self.assertGreaterEqual(overview["counts"]["totalAlerts"], 1)
        self.assertGreaterEqual(overview["counts"]["resolvedCount"], 1)
        self.assertGreaterEqual(overview["counts"]["recentChanges"], 1)
        target_row = next(
            (
                row
                for row in overview["byPolicyVersion"]
                if row["policyVersion"] == version
            ),
            None,
        )
        self.assertIsNotNone(target_row)
        assert target_row is not None
        self.assertGreaterEqual(target_row["totalAlerts"], 1)
        self.assertGreaterEqual(target_row["resolvedCount"], 1)
        self.assertEqual(target_row["openBlockedCount"], 0)
        self.assertEqual(target_row["lastStatus"], "resolved")
        resolved_trend = health_overview_payload["dependencyTrend"]
        self.assertIsInstance(resolved_trend, dict)
        self.assertGreaterEqual(resolved_trend["count"], 1)

        resolved_trend_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/registries/policy/dependencies/health"
                f"?policy_version={version}&include_all_versions=true&include_overview=false"
                "&include_trend=true&trend_status=resolved"
                f"&trend_policy_version={version}&trend_limit=1&trend_offset=0"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(resolved_trend_resp.status_code, 200)
        resolved_trend_payload = resolved_trend_resp.json()["dependencyTrend"]
        self.assertEqual(resolved_trend_payload["returned"], 1)
        self.assertGreaterEqual(resolved_trend_payload["count"], 1)
        self.assertEqual(resolved_trend_payload["filters"]["status"], "resolved")
        self.assertEqual(resolved_trend_payload["filters"]["policyVersion"], version)
        self.assertEqual(resolved_trend_payload["items"][0]["status"], "resolved")

    async def test_registry_alert_ops_view_should_join_outbox_and_support_filters(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9221)
        blocked_actor = f"ops-blocked-{suffix}"
        override_actor = f"ops-override-{suffix}"

        fairness_blocked_version = f"policy-ops-blocked-{suffix}"
        fairness_blocked_publish = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": fairness_blocked_version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-v3-default",
                    "toolRegistryVersion": "toolset-v3-default",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(fairness_blocked_publish.status_code, 200)
        fairness_blocked_activate = await self._post(
            app=app,
            path=(
                f"/internal/judge/registries/policy/{fairness_blocked_version}/activate"
                f"?actor={blocked_actor}"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(fairness_blocked_activate.status_code, 409)
        fairness_blocked_alert_id = fairness_blocked_activate.json()["detail"]["alert"]["alertId"]
        blocked_gate_code = fairness_blocked_activate.json()["detail"]["alert"]["details"]["gate"]["code"]

        fairness_override_version = f"policy-ops-override-{suffix}"
        fairness_override_publish = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": fairness_override_version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-v3-default",
                    "toolRegistryVersion": "toolset-v3-default",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(fairness_override_publish.status_code, 200)
        fairness_override_activate = await self._post(
            app=app,
            path=(
                f"/internal/judge/registries/policy/{fairness_override_version}/activate"
                f"?override_fairness_gate=true&actor={override_actor}"
                f"&reason=ops_view_override_{suffix}"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(fairness_override_activate.status_code, 200)
        self.assertEqual(
            fairness_override_activate.json()["alert"]["type"],
            "registry_fairness_gate_override",
        )
        override_gate_code = fairness_override_activate.json()["alert"]["details"]["gate"]["code"]

        dep_version = f"policy-ops-dep-{suffix}"
        dep_blocked = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": dep_version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": f"promptset-missing-{suffix}",
                    "toolRegistryVersion": "toolset-v3-default",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(dep_blocked.status_code, 422)
        self.assertEqual(
            dep_blocked.json()["detail"]["alert"]["type"],
            "registry_dependency_health_blocked",
        )

        dep_promptset_version = f"promptset-ops-{suffix}"
        dep_promptset_publish = await self._post_json(
            app=app,
            path="/internal/judge/registries/prompt/publish",
            payload={
                "version": dep_promptset_version,
                "activate": False,
                "profile": {
                    "promptVersions": {
                        "summaryPromptVersion": "v3.a2a3.summary.v1",
                        "agent2PromptVersion": "v3.a6a7.bidirectional.v2",
                        "finalPipelineVersion": "v3-final-a9a10-rollup-v2",
                        "claimGraphVersion": "v1-claim-graph-bootstrap",
                    },
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(dep_promptset_publish.status_code, 200)
        dep_recovered = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": dep_version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": dep_promptset_version,
                    "toolRegistryVersion": "toolset-v3-default",
                    "promptVersions": {
                        "summaryPromptVersion": "v3.a2a3.summary.v1",
                        "agent2PromptVersion": "v3.a6a7.bidirectional.v2",
                        "finalPipelineVersion": "v3-final-a9a10-rollup-v2",
                        "claimGraphVersion": "v1-claim-graph-bootstrap",
                    },
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(dep_recovered.status_code, 200)

        outbox_resp = await self._get(
            app=app,
            path="/internal/judge/alerts/outbox",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(outbox_resp.status_code, 200)
        blocked_event = next(
            (
                row
                for row in outbox_resp.json()["items"]
                if row["alertId"] == fairness_blocked_alert_id
            ),
            None,
        )
        self.assertIsNotNone(blocked_event)
        assert blocked_event is not None
        mark_failed_resp = await self._post(
            app=app,
            path=(
                "/internal/judge/alerts/outbox/"
                f"{blocked_event['eventId']}/delivery?delivery_status=failed&error_message=ops_view_probe"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(mark_failed_resp.status_code, 200)
        self.assertEqual(mark_failed_resp.json()["item"]["deliveryStatus"], "failed")

        ops_view_resp = await self._get(
            app=app,
            path="/internal/judge/alerts/ops-view?limit=200",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(ops_view_resp.status_code, 200)
        ops_payload = ops_view_resp.json()
        self.assertGreaterEqual(ops_payload["count"], 3)
        self.assertGreaterEqual(ops_payload["aggregations"]["byType"]["registry_fairness_gate_blocked"], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["byType"]["registry_fairness_gate_override"], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["byType"]["registry_dependency_health_blocked"], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["byGateCode"][blocked_gate_code], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["byGateCode"][override_gate_code], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["byGateActor"][blocked_actor], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["byGateActor"][override_actor], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["byOverrideApplied"]["true"], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["byOverrideApplied"]["false"], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["overrideAppliedCount"], 1)
        self.assertGreaterEqual(ops_payload["aggregations"]["blockedWithoutOverrideCount"], 1)
        self.assertEqual(ops_payload["filters"]["fieldsMode"], "full")
        self.assertTrue(bool(ops_payload["filters"]["includeTrend"]))
        self.assertIsInstance(ops_payload["trend"], dict)
        self.assertGreaterEqual(ops_payload["trend"]["count"], 1)
        blocked_item = next(
            (
                row
                for row in ops_payload["items"]
                if row["alertId"] == fairness_blocked_alert_id
            ),
            None,
        )
        self.assertIsNotNone(blocked_item)
        assert blocked_item is not None
        self.assertEqual(blocked_item["outbox"]["latestDeliveryStatus"], "failed")
        self.assertEqual(blocked_item["gateCode"], blocked_gate_code)
        self.assertEqual(blocked_item["gateActor"], blocked_actor)
        self.assertFalse(bool(blocked_item["overrideApplied"]))

        failed_filter_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/alerts/ops-view"
                "?alert_type=registry_fairness_gate_blocked&delivery_status=failed&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(failed_filter_resp.status_code, 200)
        failed_filter_payload = failed_filter_resp.json()
        self.assertGreaterEqual(failed_filter_payload["returned"], 1)
        self.assertTrue(
            all(
                row["type"] == "registry_fairness_gate_blocked"
                and row["outbox"]["latestDeliveryStatus"] == "failed"
                for row in failed_filter_payload["items"]
            )
        )

        open_filter_resp = await self._get(
            app=app,
            path="/internal/judge/alerts/ops-view?status=open&limit=50",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(open_filter_resp.status_code, 200)
        self.assertTrue(
            all(row["status"] in {"raised", "acked"} for row in open_filter_resp.json()["items"])
        )

        dep_resolved_filter_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/alerts/ops-view"
                f"?alert_type=registry_dependency_health_blocked&status=resolved&policy_version={dep_version}"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(dep_resolved_filter_resp.status_code, 200)
        dep_resolved_payload = dep_resolved_filter_resp.json()
        self.assertGreaterEqual(dep_resolved_payload["returned"], 1)
        self.assertTrue(
            all(
                row["type"] == "registry_dependency_health_blocked"
                and row["status"] == "resolved"
                and row["policyVersion"] == dep_version
                for row in dep_resolved_payload["items"]
            )
        )

        override_gate_filter_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/alerts/ops-view"
                f"?gate_code={override_gate_code}&gate_actor={override_actor}"
                "&override_applied=true&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(override_gate_filter_resp.status_code, 200)
        override_gate_filter_payload = override_gate_filter_resp.json()
        self.assertGreaterEqual(override_gate_filter_payload["returned"], 1)
        self.assertEqual(override_gate_filter_payload["filters"]["gateCode"], override_gate_code)
        self.assertEqual(override_gate_filter_payload["filters"]["gateActor"], override_actor)
        self.assertTrue(bool(override_gate_filter_payload["filters"]["overrideApplied"]))
        self.assertTrue(
            all(
                row["gateCode"] == override_gate_code
                and row["gateActor"] == override_actor
                and bool(row["overrideApplied"])
                for row in override_gate_filter_payload["items"]
            )
        )

        blocked_gate_filter_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/alerts/ops-view"
                f"?gate_code={blocked_gate_code}&gate_actor={blocked_actor}"
                "&override_applied=false&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(blocked_gate_filter_resp.status_code, 200)
        blocked_gate_filter_payload = blocked_gate_filter_resp.json()
        self.assertGreaterEqual(blocked_gate_filter_payload["returned"], 1)
        self.assertEqual(blocked_gate_filter_payload["filters"]["gateCode"], blocked_gate_code)
        self.assertEqual(blocked_gate_filter_payload["filters"]["gateActor"], blocked_actor)
        self.assertFalse(bool(blocked_gate_filter_payload["filters"]["overrideApplied"]))
        self.assertTrue(
            all(
                row["gateCode"] == blocked_gate_code
                and row["gateActor"] == blocked_actor
                and not bool(row["overrideApplied"])
                for row in blocked_gate_filter_payload["items"]
            )
        )

        bad_alert_type_resp = await self._get(
            app=app,
            path="/internal/judge/alerts/ops-view?alert_type=invalid-type",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_alert_type_resp.status_code, 422)
        self.assertIn("invalid_alert_type", bad_alert_type_resp.text)

        bad_status_resp = await self._get(
            app=app,
            path="/internal/judge/alerts/ops-view?status=invalid-status",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_status_resp.status_code, 422)
        self.assertIn("invalid_alert_status", bad_status_resp.text)

        bad_delivery_status_resp = await self._get(
            app=app,
            path="/internal/judge/alerts/ops-view?delivery_status=invalid-delivery",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_delivery_status_resp.status_code, 422)
        self.assertIn("invalid_delivery_status", bad_delivery_status_resp.text)

    async def test_registry_alert_ops_view_should_support_lite_mode_and_trend_window(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9222)

        blocked_version = f"policy-ops-lite-blocked-{suffix}"
        blocked_publish = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": blocked_version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-v3-default",
                    "toolRegistryVersion": "toolset-v3-default",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(blocked_publish.status_code, 200)
        blocked_activate = await self._post(
            app=app,
            path=f"/internal/judge/registries/policy/{blocked_version}/activate",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(blocked_activate.status_code, 409)

        override_version = f"policy-ops-lite-override-{suffix}"
        override_publish = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": override_version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-v3-default",
                    "toolRegistryVersion": "toolset-v3-default",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(override_publish.status_code, 200)
        override_activate = await self._post(
            app=app,
            path=(
                f"/internal/judge/registries/policy/{override_version}/activate"
                f"?override_fairness_gate=true&reason=ops_lite_override_{suffix}"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(override_activate.status_code, 200)

        lite_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/alerts/ops-view"
                "?fields_mode=lite&trend_window_minutes=1440&trend_bucket_minutes=120&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(lite_resp.status_code, 200)
        lite_payload = lite_resp.json()
        self.assertEqual(lite_payload["filters"]["fieldsMode"], "lite")
        self.assertEqual(lite_payload["filters"]["trendWindowMinutes"], 1440)
        self.assertEqual(lite_payload["filters"]["trendBucketMinutes"], 120)
        self.assertIsInstance(lite_payload["trend"], dict)
        self.assertGreaterEqual(lite_payload["trend"]["count"], 2)
        self.assertGreaterEqual(lite_payload["trend"]["typeCounts"]["registry_fairness_gate_blocked"], 1)
        self.assertGreaterEqual(lite_payload["trend"]["typeCounts"]["registry_fairness_gate_override"], 1)
        self.assertGreaterEqual(len(lite_payload["trend"]["timeline"]), 1)
        self.assertGreaterEqual(lite_payload["returned"], 1)
        lite_item = lite_payload["items"][0]
        self.assertNotIn("message", lite_item)
        self.assertIn("outbox", lite_item)
        self.assertIn("latestDeliveryStatus", lite_item["outbox"])
        self.assertIn("totalEvents", lite_item["outbox"])

        no_trend_resp = await self._get(
            app=app,
            path="/internal/judge/alerts/ops-view?include_trend=false&fields_mode=lite&limit=20",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(no_trend_resp.status_code, 200)
        no_trend_payload = no_trend_resp.json()
        self.assertFalse(bool(no_trend_payload["filters"]["includeTrend"]))
        self.assertIsNone(no_trend_payload["trend"])

        bad_fields_mode_resp = await self._get(
            app=app,
            path="/internal/judge/alerts/ops-view?fields_mode=compact",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_fields_mode_resp.status_code, 422)
        self.assertIn("invalid_fields_mode", bad_fields_mode_resp.text)

    async def test_alert_ack_should_sync_status_to_fact_repository(self) -> None:
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
        alert = runtime.trace_store.upsert_audit_alert(job_id=7201,
            scope_id=1,
            trace_id="trace-alert-7201",
            alert_type="test_alert",
            severity="warning",
            title="test",
            message="test message",
            details={"k": "v"},
        )

        ack_resp = await self._post(
            app=app,
            path=f"/internal/judge/cases/7201/alerts/{alert.alert_id}/ack",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(ack_resp.status_code, 200)
        self.assertEqual(ack_resp.json()["status"], "acked")

        fact_alerts = await runtime.workflow_runtime.facts.list_audit_alerts(
            job_id=7201,
            limit=10,
        )
        self.assertEqual(len(fact_alerts), 1)
        self.assertEqual(fact_alerts[0].alert_id, alert.alert_id)
        self.assertEqual(fact_alerts[0].status, "acked")

    async def test_final_contract_blocked_should_mark_workflow_failed_and_sync_alert(self) -> None:
        failed_calls: list[tuple[int, dict]] = []

        async def phase_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        async def final_failed_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            failed_calls.append((case_id, payload))

        runtime = create_runtime(
            settings=_build_settings(runtime_retry_max_attempts=1),
            callback_phase_report_impl=phase_callback,
            callback_final_report_impl=phase_callback,
            callback_phase_failed_impl=phase_callback,
            callback_final_failed_impl=final_failed_callback,
        )
        app = create_app(runtime)
        final_req = _build_final_request(case_id=7301, idempotency_key="final:7301")

        with patch(
            "app.applications.bootstrap_final_report_helpers.build_final_report_payload_for_dispatch_v3",
            return_value={"winner": "draw", "degradationLevel": 1},
        ):
            blocked_resp = await self._post_json(
                app=app,
                path="/internal/judge/v3/final/dispatch",
                payload=final_req.model_dump(mode="json"),
                internal_key=runtime.settings.ai_internal_key,
            )
        self.assertEqual(blocked_resp.status_code, 502)
        self.assertIn("final_contract_blocked", blocked_resp.text)
        self.assertEqual(len(failed_calls), 1)
        self.assertEqual(failed_calls[0][0], 7301)
        self.assertEqual(failed_calls[0][1]["errorCode"], "final_contract_blocked")

        workflow_job = await runtime.workflow_runtime.orchestrator.get_job(job_id=7301)
        self.assertIsNotNone(workflow_job)
        assert workflow_job is not None
        self.assertEqual(workflow_job.status, "blocked_failed")
        workflow_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=7301)
        self.assertEqual(workflow_events[-1].payload.get("errorCode"), "final_contract_blocked")
        self.assertEqual(workflow_events[-1].payload.get("callbackStatus"), "blocked_failed_reported")
        self.assertEqual(
            workflow_events[-1].payload.get("error", {}).get("code"),
            "final_contract_blocked",
        )

        receipt_resp = await self._get(
            app=app,
            path="/internal/judge/v3/final/cases/7301/receipt",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(receipt_resp.status_code, 200)
        self.assertEqual(
            receipt_resp.json()["response"].get("errorCode"),
            "final_contract_blocked",
        )
        self.assertEqual(
            receipt_resp.json()["response"].get("error", {}).get("category"),
            "contract_blocked",
        )

        fact_alerts = await runtime.workflow_runtime.facts.list_audit_alerts(job_id=7301, limit=10)
        self.assertGreaterEqual(len(fact_alerts), 1)
        self.assertEqual(fact_alerts[0].alert_type, "final_contract_violation")

if __name__ == "__main__":
    unittest.main()
