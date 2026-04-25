from __future__ import annotations

import unittest

from app.app_factory import create_app, create_runtime

from tests.app_factory_test_helpers import (
    AppFactoryRouteTestMixin,
)
from tests.app_factory_test_helpers import (
    build_settings as _build_settings,
)
from tests.app_factory_test_helpers import (
    unique_case_id as _unique_case_id,
)


class AppFactoryRegistryRouteTests(
    AppFactoryRouteTestMixin,
    unittest.IsolatedAsyncioTestCase,
):

    async def test_policy_routes_should_return_default_registry_profile(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)

        list_resp = await self._get(
            app=app,
            path="/internal/judge/policies",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(list_resp.status_code, 200)
        payload = list_resp.json()
        self.assertEqual(payload["defaultVersion"], "v3-default")
        self.assertGreaterEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["promptRegistryVersion"], "promptset-v3-default")
        self.assertEqual(payload["items"][0]["toolRegistryVersion"], "toolset-v3-default")
        self.assertEqual(payload["items"][0]["promptVersions"]["claimGraphVersion"], "v1-claim-graph-bootstrap")
        self.assertIn("evidenceMinTotalRefs", payload["items"][0]["fairnessThresholds"])

        detail_resp = await self._get(
            app=app,
            path="/internal/judge/policies/v3-default",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(detail_resp.status_code, 200)
        self.assertEqual(detail_resp.json()["item"]["version"], "v3-default")

        prompt_list_resp = await self._get(
            app=app,
            path="/internal/judge/registries/prompts",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(prompt_list_resp.status_code, 200)
        prompt_list_payload = prompt_list_resp.json()
        self.assertEqual(prompt_list_payload["defaultVersion"], "promptset-v3-default")
        self.assertGreaterEqual(prompt_list_payload["count"], 1)
        self.assertEqual(
            prompt_list_payload["items"][0]["promptVersions"]["claimGraphVersion"],
            "v1-claim-graph-bootstrap",
        )

        prompt_detail_resp = await self._get(
            app=app,
            path="/internal/judge/registries/prompts/promptset-v3-default",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(prompt_detail_resp.status_code, 200)
        self.assertEqual(prompt_detail_resp.json()["item"]["version"], "promptset-v3-default")

        tool_list_resp = await self._get(
            app=app,
            path="/internal/judge/registries/tools",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(tool_list_resp.status_code, 200)
        tool_list_payload = tool_list_resp.json()
        self.assertEqual(tool_list_payload["defaultVersion"], "toolset-v3-default")
        self.assertGreaterEqual(tool_list_payload["count"], 1)
        self.assertIn("claim_graph_builder", tool_list_payload["items"][0]["toolIds"])

        tool_detail_resp = await self._get(
            app=app,
            path="/internal/judge/registries/tools/toolset-v3-default",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(tool_detail_resp.status_code, 200)
        self.assertEqual(tool_detail_resp.json()["item"]["version"], "toolset-v3-default")

    async def test_policy_registry_publish_should_reject_unknown_prompt_registry_version(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        policy_version = f"policy-missing-{_unique_case_id(8105)}"
        publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": policy_version,
                "activate": False,
                "reason": "test_policy_override_for_prompt_registry_validation",
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-missing",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_resp.status_code, 422)
        detail = publish_resp.json()["detail"]
        self.assertEqual(detail["code"], "registry_policy_dependency_invalid")
        dependency = detail["dependency"]
        self.assertFalse(dependency["ok"])
        issue_codes = {str(item.get("code") or "") for item in dependency["issues"]}
        self.assertIn("prompt_registry_version_not_found", issue_codes)
        self.assertEqual(detail["alert"]["type"], "registry_dependency_health_blocked")
        self.assertEqual(detail["alert"]["status"], "raised")

    async def test_registry_routes_should_support_publish_activate_rollback_and_audit(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9201)
        version = f"promptset-p8-{suffix}"
        actor = f"actor-{suffix}"

        publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/prompt/publish",
            payload={
                "version": version,
                "activate": False,
                "actor": actor,
                "reason": "test_publish",
                "profile": {
                    "promptVersions": {
                        "claimGraphVersion": "v1-claim-graph-bootstrap",
                    },
                    "metadata": {
                        "status": "candidate",
                    },
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_resp.status_code, 200)
        publish_item = publish_resp.json()["item"]
        self.assertEqual(publish_item["version"], version)
        self.assertFalse(publish_item["isActive"])

        activate_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/registries/prompt/{version}/activate"
                f"?actor={actor}&reason=test_activate"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(activate_resp.status_code, 200)
        activate_item = activate_resp.json()["item"]
        self.assertEqual(activate_item["version"], version)
        self.assertTrue(activate_item["isActive"])

        prompt_list_resp = await self._get(
            app=app,
            path="/internal/judge/registries/prompts",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(prompt_list_resp.status_code, 200)
        self.assertEqual(prompt_list_resp.json()["defaultVersion"], version)

        rollback_resp = await self._post(
            app=app,
            path=f"/internal/judge/registries/prompt/rollback?actor={actor}&reason=test_rollback",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(rollback_resp.status_code, 200)
        rollback_item = rollback_resp.json()["item"]
        self.assertNotEqual(rollback_item["version"], version)

        prompt_list_after_rollback = await self._get(
            app=app,
            path="/internal/judge/registries/prompts",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(prompt_list_after_rollback.status_code, 200)
        self.assertEqual(
            prompt_list_after_rollback.json()["defaultVersion"],
            rollback_item["version"],
        )

        audits_resp = await self._get(
            app=app,
            path="/internal/judge/registries/prompt/audits?limit=200",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(audits_resp.status_code, 200)
        audit_items = audits_resp.json()["items"]
        actor_actions = [
            str(item.get("action") or "")
            for item in audit_items
            if str(item.get("actor") or "") == actor
        ]
        self.assertIn("publish", actor_actions)
        self.assertIn("activate", actor_actions)
        self.assertIn("rollback", actor_actions)

        releases_resp = await self._get(
            app=app,
            path="/internal/judge/registries/prompt/releases?limit=200&include_payload=false",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(releases_resp.status_code, 200)
        release_items = releases_resp.json()["items"]
        version_items = [
            item
            for item in release_items
            if str(item.get("version") or "") == version
        ]
        self.assertTrue(version_items)
        self.assertNotIn("payload", version_items[0])

        get_release_resp = await self._get(
            app=app,
            path=f"/internal/judge/registries/prompt/releases/{version}",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(get_release_resp.status_code, 200)
        release_item = get_release_resp.json()["item"]
        self.assertEqual(release_item["version"], version)
        self.assertIn("payload", release_item)

    async def test_policy_registry_activate_should_block_when_fairness_gate_not_ready(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9211)
        version = f"policy-gate-{suffix}"

        publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_resp.status_code, 200)

        activate_resp = await self._post(
            app=app,
            path=f"/internal/judge/registries/policy/{version}/activate",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(activate_resp.status_code, 409)
        detail = activate_resp.json()["detail"]
        self.assertEqual(detail["code"], "registry_fairness_gate_blocked")
        self.assertEqual(
            detail["gate"]["code"],
            "registry_fairness_gate_no_benchmark",
        )

    async def test_policy_registry_activate_should_block_when_shadow_gate_not_ready(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9216)
        version = f"policy-shadow-gate-{suffix}"
        benchmark_run_id = f"benchmark-{suffix}"
        shadow_run_id = f"shadow-{suffix}"

        publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_resp.status_code, 200)

        benchmark_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": benchmark_run_id,
                "policy_version": version,
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "sample_size": 48,
                "draw_rate": 0.11,
                "side_bias_delta": 0.02,
                "appeal_overturn_rate": 0.03,
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(benchmark_resp.status_code, 200)

        shadow_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/shadow-runs",
            payload={
                "run_id": shadow_run_id,
                "policy_version": version,
                "benchmark_run_id": benchmark_run_id,
                "environment_mode": "local_reference",
                "status": "threshold_violation",
                "threshold_decision": "violated",
                "sample_size": 48,
                "winner_flip_rate": 0.12,
                "score_shift_delta": 0.18,
                "review_required_delta": 0.07,
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(shadow_resp.status_code, 200)

        activate_resp = await self._post(
            app=app,
            path=f"/internal/judge/registries/policy/{version}/activate",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(activate_resp.status_code, 409)
        detail = activate_resp.json()["detail"]
        self.assertEqual(detail["code"], "registry_fairness_gate_blocked")
        gate = detail["gate"]
        self.assertEqual(
            gate["code"],
            "registry_fairness_gate_shadow_threshold_not_accepted",
        )
        self.assertEqual(gate["source"], "shadow")
        self.assertTrue(bool(gate["benchmarkGatePassed"]))
        self.assertTrue(bool(gate["shadowGateApplied"]))
        self.assertFalse(bool(gate["shadowGatePassed"]))
        self.assertEqual(gate["latestRun"]["runId"], benchmark_run_id)
        self.assertEqual(gate["latestShadowRun"]["runId"], shadow_run_id)

    async def test_policy_registry_publish_activate_should_allow_shadow_gate_override_and_audit(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9217)
        version = f"policy-shadow-override-{suffix}"
        benchmark_run_id = f"benchmark-{suffix}"
        shadow_run_id = f"shadow-{suffix}"
        actor = f"shadow-override-actor-{suffix}"

        benchmark_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": benchmark_run_id,
                "policy_version": version,
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "sample_size": 52,
                "draw_rate": 0.12,
                "side_bias_delta": 0.02,
                "appeal_overturn_rate": 0.02,
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(benchmark_resp.status_code, 200)

        shadow_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/shadow-runs",
            payload={
                "run_id": shadow_run_id,
                "policy_version": version,
                "benchmark_run_id": benchmark_run_id,
                "environment_mode": "local_reference",
                "status": "threshold_violation",
                "threshold_decision": "violated",
                "sample_size": 52,
                "winner_flip_rate": 0.11,
                "score_shift_delta": 0.16,
                "review_required_delta": 0.05,
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(shadow_resp.status_code, 200)

        publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": version,
                "activate": True,
                "override_fairness_gate": True,
                "actor": actor,
                "reason": "shadow_gate_manual_override",
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-v3-default",
                    "toolRegistryVersion": "toolset-v3-default",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_resp.status_code, 200)
        publish_payload = publish_resp.json()
        self.assertTrue(bool(publish_payload["item"]["isActive"]))
        self.assertEqual(
            publish_payload["fairnessGate"]["code"],
            "registry_fairness_gate_shadow_threshold_not_accepted",
        )
        self.assertEqual(
            publish_payload["alert"]["type"],
            "registry_fairness_gate_override",
        )
        self.assertTrue(bool(publish_payload["alert"]["details"]["overrideApplied"]))
        self.assertEqual(
            publish_payload["alert"]["details"]["gate"]["latestShadowRun"]["runId"],
            shadow_run_id,
        )

        audits_resp = await self._get(
            app=app,
            path="/internal/judge/registries/policy/audits?limit=200",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(audits_resp.status_code, 200)
        audit_items = audits_resp.json()["items"]
        activate_audit = next(
            (
                item
                for item in audit_items
                if str(item.get("action") or "") == "activate"
                and str(item.get("version") or "") == version
                and str(item.get("actor") or "") == actor
            ),
            None,
        )
        self.assertIsNotNone(activate_audit)
        assert activate_audit is not None
        fairness_gate = activate_audit["details"].get("fairnessGate")
        self.assertIsInstance(fairness_gate, dict)
        self.assertTrue(bool(fairness_gate.get("overrideApplied")))
        self.assertEqual(
            fairness_gate.get("code"),
            "registry_fairness_gate_shadow_threshold_not_accepted",
        )
        self.assertEqual(
            fairness_gate.get("latestShadowRun", {}).get("runId"),
            shadow_run_id,
        )

    async def test_policy_registry_activate_should_block_when_p37_release_readiness_env_blocked(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9218)
        version = f"policy-release-gate-{suffix}"
        benchmark_run_id = f"benchmark-release-{suffix}"
        shadow_run_id = f"shadow-release-{suffix}"
        actor = f"release-gate-actor-{suffix}"

        publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-v3-default",
                    "toolRegistryVersion": "toolset-v3-default",
                    "metadata": {
                        "releaseGateInputs": {
                            "artifactStoreReadiness": {
                                "status": "env_blocked",
                                "code": "artifact_store_real_env_missing",
                            },
                            "publicVerificationReadiness": {"status": "ready"},
                            "trustRegistryWriteThrough": {"status": "ready"},
                            "panelShadowDrift": {"status": "ready"},
                        }
                    },
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_resp.status_code, 200)

        benchmark_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/benchmark-runs",
            payload={
                "run_id": benchmark_run_id,
                "policy_version": version,
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "sample_size": 64,
                "draw_rate": 0.12,
                "side_bias_delta": 0.02,
                "appeal_overturn_rate": 0.03,
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(benchmark_resp.status_code, 200)

        shadow_resp = await self._post_json(
            app=app,
            path="/internal/judge/fairness/shadow-runs",
            payload={
                "run_id": shadow_run_id,
                "policy_version": version,
                "benchmark_run_id": benchmark_run_id,
                "environment_mode": "local_reference",
                "status": "local_reference_frozen",
                "threshold_decision": "accepted",
                "sample_size": 64,
                "winner_flip_rate": 0.01,
                "score_shift_delta": 0.02,
                "review_required_delta": 0.0,
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(shadow_resp.status_code, 200)

        activate_resp = await self._post(
            app=app,
            path=f"/internal/judge/registries/policy/{version}/activate?actor={actor}",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(activate_resp.status_code, 409)
        detail = activate_resp.json()["detail"]
        self.assertEqual(detail["code"], "registry_release_gate_env_blocked")
        self.assertEqual(detail["releaseGate"]["decision"], "env_blocked")
        reason_codes = {row["code"] for row in detail["releaseGate"]["reasons"]}
        self.assertIn("artifact_store_real_env_missing", reason_codes)

        override_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/registries/policy/{version}/activate"
                f"?override_fairness_gate=true&actor={actor}"
                "&reason=release_gate_env_override"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(override_resp.status_code, 200)
        override_payload = override_resp.json()
        self.assertTrue(override_payload["item"]["isActive"])
        self.assertEqual(override_payload["releaseGate"]["decision"], "env_blocked")

        audits_resp = await self._get(
            app=app,
            path="/internal/judge/registries/policy/audits?limit=200",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(audits_resp.status_code, 200)
        audit_items = audits_resp.json()["items"]
        activate_audit = next(
            (
                item
                for item in audit_items
                if item["action"] == "activate"
                and item["version"] == version
                and item["actor"] == actor
            ),
            None,
        )
        self.assertIsNotNone(activate_audit)
        assert activate_audit is not None
        self.assertEqual(
            activate_audit["details"]["releaseGate"]["decision"],
            "env_blocked",
        )
        self.assertTrue(bool(activate_audit["details"]["releaseGate"]["overrideApplied"]))

    async def test_policy_registry_activate_should_block_when_dependency_invalid(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        await runtime.workflow_runtime.db.create_schema()
        suffix = _unique_case_id(9212)
        version = f"policy-dep-{suffix}"
        await runtime.registry_product_runtime.publish_release(
            registry_type="policy",
            version=version,
            profile_payload={
                "rubricVersion": "v3",
                "topicDomain": "tft",
                "promptRegistryVersion": "promptset-not-exist",
                "toolRegistryVersion": "toolset-v3-default",
            },
            actor="seed",
            reason="seed_invalid_dependency_for_activate",
            activate=False,
        )

        activate_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/registries/policy/{version}/activate"
                "?override_fairness_gate=true&reason=test_override"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(activate_resp.status_code, 409)
        detail = activate_resp.json()["detail"]
        self.assertEqual(detail["code"], "registry_policy_dependency_blocked")
        dependency = detail["dependency"]
        self.assertFalse(dependency["ok"])
        issue_codes = {str(item.get("code") or "") for item in dependency["issues"]}
        self.assertIn("prompt_registry_version_not_found", issue_codes)

    async def test_policy_registry_dependency_health_route_should_return_dependency_snapshot(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9214)
        version = f"policy-health-{suffix}"
        actor = f"dependency-health-actor-{suffix}"
        publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": version,
                "activate": False,
                "reason": "prepare_for_dependency_health",
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-v3-default",
                    "toolRegistryVersion": "toolset-v3-default",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_resp.status_code, 200)
        activate_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/registries/policy/{version}/activate"
                f"?override_fairness_gate=true&actor={actor}&reason=dependency_health_override_probe"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(activate_resp.status_code, 200)

        health_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/registries/policy/dependencies/health"
                f"?policy_version={version}&include_all_versions=true&limit=5"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(health_resp.status_code, 200)
        payload = health_resp.json()
        self.assertEqual(payload["selectedPolicyVersion"], version)
        self.assertGreaterEqual(payload["count"], 1)
        self.assertTrue(payload["includeAllVersions"])
        self.assertTrue(payload["includeOverview"])
        self.assertTrue(payload["includeTrend"])
        self.assertEqual(payload["item"]["policyVersion"], version)
        self.assertTrue(payload["item"]["ok"])
        self.assertTrue(payload["item"]["checks"]["promptRegistryExists"])
        self.assertTrue(payload["item"]["checks"]["toolRegistryExists"])
        self.assertIsInstance(payload["item"]["policyKernel"], dict)
        self.assertEqual(
            payload["item"]["policyKernel"]["version"],
            "policy-kernel-binding-v1",
        )
        self.assertTrue(str(payload["item"]["policyKernel"]["kernelHash"] or "").strip())
        self.assertEqual(
            payload["item"]["policyKernel"]["kernelVector"]["policyVersion"],
            version,
        )
        self.assertEqual(payload["activeVersions"]["policyVersion"], runtime.policy_registry_runtime.default_version)
        overview = payload["dependencyOverview"]
        self.assertIsInstance(overview, dict)
        self.assertEqual(overview["registryType"], "policy")
        self.assertGreaterEqual(overview["counts"]["trackedPolicyVersions"], 1)
        self.assertIn("gateDecisionCounts", overview)
        self.assertIn("byPolicyVersion", overview)
        self.assertTrue(any(row["policyVersion"] == version for row in overview["byPolicyVersion"]))
        target_overview = next(row for row in overview["byPolicyVersion"] if row["policyVersion"] == version)
        self.assertEqual(target_overview["policyKernelVersion"], "policy-kernel-binding-v1")
        self.assertTrue(str(target_overview["policyKernelHash"] or "").strip())
        self.assertEqual(target_overview["latestGateDecision"], "override_activated")
        self.assertTrue(bool(target_overview["overrideApplied"]))
        self.assertEqual(target_overview["overrideActor"], actor)
        self.assertEqual(target_overview["latestGateSource"], "benchmark")
        trend = payload["dependencyTrend"]
        self.assertIsInstance(trend, dict)
        self.assertEqual(trend["registryType"], "policy")
        self.assertIn("items", trend)
        self.assertGreaterEqual(trend["count"], 0)

    async def test_policy_registry_dependency_health_route_should_reject_invalid_trend_status(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        health_resp = await self._get(
            app=app,
            path="/internal/judge/registries/policy/dependencies/health?trend_status=bad-status",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(health_resp.status_code, 422)
        self.assertIn("invalid_trend_status", health_resp.text)

    async def test_policy_gate_simulation_route_should_return_advisory_snapshot(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9215)
        version = f"policy-gate-sim-{suffix}"
        publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": version,
                "activate": False,
                "reason": "prepare_for_policy_gate_simulation",
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-v3-default",
                    "toolRegistryVersion": "toolset-v3-default",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_resp.status_code, 200)
        before_alerts = list(
            runtime.trace_store.list_audit_alerts(job_id=0, status=None, limit=500)
        )

        sim_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/registries/policy/gate-simulation"
                f"?policy_version={version}&include_all_versions=true&limit=10"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(sim_resp.status_code, 200)
        payload = sim_resp.json()
        self.assertEqual(payload["selectedPolicyVersion"], version)
        self.assertGreaterEqual(payload["count"], 1)
        self.assertTrue(payload["summary"]["advisoryOnly"])
        self.assertTrue(payload["filters"]["includeAllVersions"])
        self.assertIn("notes", payload)
        target = next(row for row in payload["items"] if row["policyVersion"] == version)
        self.assertIn("domainJudgeFamily", target)
        self.assertIn("dependencyHealth", target)
        self.assertIn("fairnessGate", target)
        self.assertIn("releaseGate", target)
        self.assertIn("simulatedGate", target)
        self.assertIn(
            target["simulatedGate"]["status"],
            {"allowed", "blocked", "needs_review", "env_blocked"},
        )
        self.assertIsInstance(target["simulatedGate"]["failingComponents"], list)

        after_alerts = list(
            runtime.trace_store.list_audit_alerts(job_id=0, status=None, limit=500)
        )
        self.assertEqual(len(after_alerts), len(before_alerts))

    async def test_policy_gate_simulation_route_should_return_404_when_policy_missing(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        missing_version = f"policy-gate-sim-missing-{_unique_case_id(9216)}"
        sim_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/registries/policy/gate-simulation"
                f"?policy_version={missing_version}"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(sim_resp.status_code, 404)
        self.assertIn("policy_registry_not_found", sim_resp.text)

    async def test_registry_governance_overview_route_should_join_triple_dependency_usage_and_audits(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9218)
        prompt_version = f"promptset-governance-{suffix}"
        policy_invalid_version = f"policy-governance-invalid-{suffix}"
        actor = f"governance-actor-{suffix}"

        prompt_publish = await self._post_json(
            app=app,
            path="/internal/judge/registries/prompt/publish",
            payload={
                "version": prompt_version,
                "activate": False,
                "actor": actor,
                "reason": "governance_publish_prompt",
                "profile": {
                    "promptVersions": {
                        "claimGraphVersion": "v1-claim-graph-bootstrap",
                    },
                    "metadata": {
                        "status": "candidate",
                    },
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(prompt_publish.status_code, 200)

        prompt_activate = await self._post(
            app=app,
            path=(
                f"/internal/judge/registries/prompt/{prompt_version}/activate"
                f"?actor={actor}&reason=governance_activate_prompt"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(prompt_activate.status_code, 200)

        prompt_rollback = await self._post(
            app=app,
            path=(
                "/internal/judge/registries/prompt/rollback"
                f"?actor={actor}&reason=governance_rollback_prompt"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(prompt_rollback.status_code, 200)

        await runtime.registry_product_runtime.publish_release(
            registry_type="policy",
            version=policy_invalid_version,
            profile_payload={
                "rubricVersion": "v3",
                "topicDomain": "tft",
                "promptRegistryVersion": f"promptset-missing-{suffix}",
                "toolRegistryVersion": "toolset-v3-default",
            },
            actor="seed",
            reason="seed_invalid_prompt_dependency_for_governance_overview",
            activate=False,
        )

        overview_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/registries/governance/overview"
                "?dependency_limit=200&usage_preview_limit=10&release_limit=100&audit_limit=200"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(overview_resp.status_code, 200)
        payload = overview_resp.json()
        active_versions = payload["activeVersions"]
        self.assertTrue(str(active_versions["policyVersion"] or "").strip())
        self.assertTrue(str(active_versions["promptRegistryVersion"] or "").strip())
        self.assertTrue(str(active_versions["toolRegistryVersion"] or "").strip())

        dependency = payload["dependencyHealth"]
        self.assertGreaterEqual(dependency["count"], 1)
        self.assertGreaterEqual(dependency["invalidCount"], 1)
        invalid_row = next(
            (
                row
                for row in dependency["items"]
                if row["policyVersion"] == policy_invalid_version
            ),
            None,
        )
        self.assertIsNotNone(invalid_row)
        assert invalid_row is not None
        self.assertFalse(bool(invalid_row["ok"]))
        self.assertIn("prompt_registry_version_not_found", invalid_row["issueCodes"])
        self.assertEqual(invalid_row["policyKernelVersion"], "policy-kernel-binding-v1")
        self.assertTrue(str(invalid_row["policyKernelHash"] or "").strip())
        self.assertIn("releaseGate", invalid_row)
        self.assertEqual(invalid_row["releaseGateDecision"], "blocked")
        self.assertIn(f"promptset-missing-{suffix}", dependency["byPromptRegistryVersion"])

        reverse_usage = payload["reverseUsage"]
        prompt_row = next(
            (
                row
                for row in reverse_usage["prompts"]
                if row["version"] == prompt_version
            ),
            None,
        )
        self.assertIsNotNone(prompt_row)
        assert prompt_row is not None
        self.assertIsInstance(prompt_row["referencedByPolicyCount"], int)
        self.assertGreaterEqual(prompt_row["referencedByPolicyCount"], 0)
        domain_families = payload["domainJudgeFamilies"]
        self.assertIsInstance(domain_families, dict)
        self.assertGreaterEqual(domain_families["count"], 1)
        self.assertIn("allowedFamilies", domain_families)
        self.assertIn("items", domain_families)
        self.assertTrue(
            any(row["domainJudgeFamily"] == "tft" for row in domain_families["items"])
        )
        release_readiness = payload["releaseReadiness"]
        self.assertIsInstance(release_readiness, dict)
        self.assertGreaterEqual(release_readiness["blockedCount"], 1)
        self.assertIn("dependencyHealth", release_readiness["componentBlockCounts"])

        release_state = payload["releaseState"]
        self.assertIn("policy", release_state)
        self.assertIn("prompt", release_state)
        self.assertIn("tool", release_state)
        self.assertGreaterEqual(release_state["prompt"]["count"], 1)

        audit_summary = payload["auditSummary"]
        self.assertGreaterEqual(audit_summary["countsByAction"].get("publish", 0), 1)
        self.assertGreaterEqual(audit_summary["countsByAction"].get("activate", 0), 1)
        self.assertGreaterEqual(audit_summary["countsByAction"].get("rollback", 0), 1)
        latest_rollback = audit_summary["latestRollbackByRegistryType"]["prompt"]
        self.assertIsNotNone(latest_rollback)
        assert latest_rollback is not None
        self.assertEqual(latest_rollback["registryType"], "prompt")

    async def test_registry_prompt_tool_governance_route_should_return_risk_and_action_hints(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9220)
        actor = f"prompt-tool-governance-actor-{suffix}"
        orphan_prompt_version = f"promptset-orphan-{suffix}"
        missing_prompt_version = f"promptset-missing-{suffix}"
        missing_tool_version = f"toolset-missing-{suffix}"
        policy_invalid_version = f"policy-prompt-tool-risk-{suffix}"

        publish_prompt_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/prompt/publish",
            payload={
                "version": orphan_prompt_version,
                "activate": False,
                "actor": actor,
                "reason": "seed_orphan_prompt_for_prompt_tool_governance",
                "profile": {
                    "promptVersions": {
                        "claimGraphVersion": "v1-claim-graph-bootstrap",
                    },
                    "metadata": {
                        "status": "candidate",
                    },
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_prompt_resp.status_code, 200)

        await runtime.registry_product_runtime.publish_release(
            registry_type="policy",
            version=policy_invalid_version,
            profile_payload={
                "rubricVersion": "v3",
                "topicDomain": "tft",
                "promptRegistryVersion": missing_prompt_version,
                "toolRegistryVersion": missing_tool_version,
            },
            actor="seed",
            reason="seed_invalid_dependencies_for_prompt_tool_governance",
            activate=False,
        )

        route_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/registries/prompt-tool/governance"
                "?dependency_limit=200&usage_preview_limit=20&release_limit=50&audit_limit=100"
                "&risk_limit=3"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(route_resp.status_code, 200)
        payload = route_resp.json()
        self.assertIsInstance(payload["summary"], dict)
        self.assertIsInstance(payload["dependencyHealth"], dict)
        self.assertIsInstance(payload["promptToolUsage"], dict)
        self.assertIsInstance(payload["riskItems"], list)
        self.assertIsInstance(payload["actionHints"], list)
        self.assertEqual(payload["filters"]["riskLimit"], 3)

        summary = payload["summary"]
        self.assertIn(summary["riskLevel"], {"high", "medium", "low", "healthy"})
        self.assertGreaterEqual(summary["dependencyInvalidCount"], 1)
        self.assertGreaterEqual(summary["missingPromptRefCount"], 1)
        self.assertGreaterEqual(summary["missingToolRefCount"], 1)
        self.assertGreaterEqual(summary["unreferencedPromptCount"], 1)
        self.assertGreaterEqual(summary["riskTotalCount"], summary["riskReturned"])
        self.assertEqual(summary["riskReturned"], len(payload["riskItems"]))
        self.assertTrue(summary["riskTruncated"])

        prompt_usage = payload["promptToolUsage"]["prompts"]
        orphan_prompt_row = next(
            (row for row in prompt_usage if row["version"] == orphan_prompt_version),
            None,
        )
        self.assertIsNotNone(orphan_prompt_row)
        assert orphan_prompt_row is not None
        self.assertEqual(orphan_prompt_row["referencedByPolicyCount"], 0)
        self.assertIn("unreferenced", orphan_prompt_row["riskTags"])

        self.assertIn(
            missing_prompt_version,
            payload["promptToolUsage"]["missingPromptRegistryRefs"],
        )
        self.assertIn(
            missing_tool_version,
            payload["promptToolUsage"]["missingToolRegistryRefs"],
        )

        risk_types = {row.get("riskType") for row in payload["riskItems"]}
        self.assertIn("dependency_invalid", risk_types)
        action_ids = {row.get("actionId") for row in payload["actionHints"]}
        self.assertIn("registry.policy.dependencies.fix", action_ids)
        self.assertIn("registry.prompt.curate", action_ids)
        self.assertIn("registry.tool.curate", action_ids)

    async def test_policy_domain_judge_families_route_should_return_family_snapshot(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        version = f"policy-domain-family-{_unique_case_id(9219)}"
        publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-v3-default",
                    "toolRegistryVersion": "toolset-v3-default",
                    "metadata": {
                        "domainJudgeFamily": "tft",
                    },
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_resp.status_code, 200)
        publish_payload = publish_resp.json()
        self.assertEqual(publish_payload["policyDomainJudgeFamily"], "tft")

        route_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/registries/policy/domain-families"
                "?preview_limit=20&include_versions=true"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(route_resp.status_code, 200)
        payload = route_resp.json()
        self.assertIsInstance(payload["domainJudgeFamilies"], dict)
        self.assertGreaterEqual(payload["domainJudgeFamilies"]["count"], 1)
        self.assertIn("allowedFamilies", payload["domainJudgeFamilies"])
        tft_row = next(
            (
                row
                for row in payload["domainJudgeFamilies"]["items"]
                if row["domainJudgeFamily"] == "tft"
            ),
            None,
        )
        self.assertIsNotNone(tft_row)
        assert tft_row is not None
        self.assertGreaterEqual(tft_row["count"], 1)
        self.assertIn(version, tft_row["policyVersions"])

    async def test_policy_registry_publish_should_reject_domain_family_topic_mismatch(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        version = f"policy-family-mismatch-{_unique_case_id(9220)}"
        publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": version,
                "activate": False,
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                    "promptRegistryVersion": "promptset-v3-default",
                    "toolRegistryVersion": "toolset-v3-default",
                    "metadata": {
                        "domainJudgeFamily": "finance",
                    },
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_resp.status_code, 422)
        self.assertIn("policy_domain_family_topic_domain_mismatch", publish_resp.text)

    async def test_policy_registry_activate_override_should_require_reason_and_be_auditable(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9213)
        version = f"policy-gate-{suffix}"
        actor = f"policy-actor-{suffix}"

        publish_resp = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": version,
                "activate": False,
                "actor": actor,
                "reason": "prepare_policy_release",
                "profile": {
                    "rubricVersion": "v3",
                    "topicDomain": "tft",
                },
            },
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(publish_resp.status_code, 200)

        missing_reason_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/registries/policy/{version}/activate"
                f"?override_fairness_gate=true&actor={actor}"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(missing_reason_resp.status_code, 422)
        self.assertIn(
            "registry_fairness_gate_override_reason_required",
            missing_reason_resp.text,
        )

        activate_resp = await self._post(
            app=app,
            path=(
                f"/internal/judge/registries/policy/{version}/activate"
                f"?override_fairness_gate=true&actor={actor}&reason=manual_override_for_trial"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(activate_resp.status_code, 200)
        activate_payload = activate_resp.json()
        self.assertEqual(activate_payload["item"]["version"], version)
        self.assertTrue(activate_payload["item"]["isActive"])
        self.assertIsNotNone(activate_payload["dependencyHealth"])
        self.assertTrue(bool(activate_payload["dependencyHealth"]["ok"]))
        self.assertIsNotNone(activate_payload["fairnessGate"])
        self.assertTrue(
            activate_payload["fairnessGate"]["latestRun"] is None
            or isinstance(activate_payload["fairnessGate"]["latestRun"], dict)
        )

        audits_resp = await self._get(
            app=app,
            path="/internal/judge/registries/policy/audits?limit=200",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(audits_resp.status_code, 200)
        audit_items = audits_resp.json()["items"]
        override_audit = next(
            (
                item
                for item in audit_items
                if str(item.get("action") or "") == "activate"
                and str(item.get("version") or "") == version
                and str(item.get("actor") or "") == actor
            ),
            None,
        )
        self.assertIsNotNone(override_audit)
        assert override_audit is not None
        fairness_gate = override_audit["details"].get("fairnessGate")
        self.assertIsInstance(fairness_gate, dict)
        self.assertTrue(bool(fairness_gate.get("overrideApplied")))
        dependency_health = override_audit["details"].get("dependencyHealth")
        self.assertIsInstance(dependency_health, dict)
        self.assertTrue(bool(dependency_health.get("ok")))

    async def test_policy_registry_audits_should_support_gate_link_export_and_filters(
        self,
    ) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        suffix = _unique_case_id(9220)
        override_version = f"policy-audit-override-{suffix}"
        override_actor = f"audit-actor-{suffix}"

        override_publish = await self._post_json(
            app=app,
            path="/internal/judge/registries/policy/publish",
            payload={
                "version": override_version,
                "activate": False,
                "actor": override_actor,
                "reason": "audit_prepare",
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
                f"?override_fairness_gate=true&actor={override_actor}"
                "&reason=audit_manual_override"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(override_activate.status_code, 200)
        override_gate_code = override_activate.json()["alert"]["details"]["gate"]["code"]

        audits_resp = await self._get(
            app=app,
            path="/internal/judge/registries/policy/audits?limit=200",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(audits_resp.status_code, 200)
        audits_payload = audits_resp.json()
        self.assertGreaterEqual(audits_payload["count"], 2)
        self.assertGreaterEqual(audits_payload["aggregations"]["byAction"]["publish"], 1)
        self.assertGreaterEqual(audits_payload["aggregations"]["byAction"]["activate"], 1)
        self.assertGreaterEqual(audits_payload["aggregations"]["byGateCode"][override_gate_code], 1)
        self.assertGreaterEqual(audits_payload["aggregations"]["withGateReviewCount"], 1)
        self.assertGreaterEqual(audits_payload["aggregations"]["withLinkedAlertsCount"], 1)
        target_item = next(
            (
                row
                for row in audits_payload["items"]
                if row["action"] == "activate"
                and row["version"] == override_version
                and row["actor"] == override_actor
            ),
            None,
        )
        self.assertIsNotNone(target_item)
        assert target_item is not None
        self.assertEqual(target_item["gateReview"]["gateCode"], override_gate_code)
        self.assertTrue(bool(target_item["gateReview"]["overrideApplied"]))
        self.assertIsInstance(target_item["linkedAlertSummary"], dict)
        self.assertGreaterEqual(target_item["linkedAlertSummary"]["count"], 1)
        self.assertGreaterEqual(
            target_item["linkedAlertSummary"]["byType"]["registry_fairness_gate_override"],
            1,
        )
        self.assertTrue(
            any(
                row["type"] == "registry_fairness_gate_override"
                for row in target_item["linkedAlerts"]
            )
        )

        gate_filter_resp = await self._get(
            app=app,
            path=(
                "/internal/judge/registries/policy/audits"
                f"?action=activate&version={override_version}&actor={override_actor}"
                f"&gate_code={override_gate_code}&override_applied=true&limit=50"
            ),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(gate_filter_resp.status_code, 200)
        gate_filter_payload = gate_filter_resp.json()
        self.assertGreaterEqual(gate_filter_payload["returned"], 1)
        self.assertEqual(gate_filter_payload["filters"]["action"], "activate")
        self.assertEqual(gate_filter_payload["filters"]["version"], override_version)
        self.assertEqual(gate_filter_payload["filters"]["actor"], override_actor)
        self.assertEqual(gate_filter_payload["filters"]["gateCode"], override_gate_code)
        self.assertTrue(bool(gate_filter_payload["filters"]["overrideApplied"]))
        self.assertTrue(
            all(
                row["action"] == "activate"
                and row["version"] == override_version
                and row["actor"] == override_actor
                and row["gateReview"]["gateCode"] == override_gate_code
                and bool(row["gateReview"]["overrideApplied"])
                for row in gate_filter_payload["items"]
            )
        )

        no_gate_view_resp = await self._get(
            app=app,
            path="/internal/judge/registries/policy/audits?include_gate_view=false&limit=20",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(no_gate_view_resp.status_code, 200)
        no_gate_view_payload = no_gate_view_resp.json()
        self.assertFalse(bool(no_gate_view_payload["filters"]["includeGateView"]))
        self.assertTrue(
            all(row["linkedAlerts"] is None for row in no_gate_view_payload["items"])
        )

        bad_action_resp = await self._get(
            app=app,
            path="/internal/judge/registries/policy/audits?action=invalid-action",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(bad_action_resp.status_code, 422)
        self.assertIn("invalid_registry_audit_action", bad_action_resp.text)

if __name__ == "__main__":
    unittest.main()
