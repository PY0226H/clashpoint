from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from typing import Any

from app.applications.judge_command_routes import (
    JudgeCommandRouteError,
    attach_policy_trace_snapshot,
    build_blindization_rejection_route_payload,
    build_case_create_route_payload,
    build_dispatch_meta_from_raw,
    build_final_contract_blocked_route_payload,
    build_final_dispatch_callback_delivery_route_payload,
    build_final_dispatch_callback_result_route_payload,
    build_final_dispatch_preflight_route_payload,
    build_final_dispatch_report_materialization_route_payload,
    build_final_report_payload_for_dispatch,
    build_phase_dispatch_callback_delivery_route_payload,
    build_phase_dispatch_callback_result_route_payload,
    build_phase_dispatch_preflight_route_payload,
    build_phase_dispatch_report_materialization_route_payload,
    build_receipt_dims_from_raw,
    extract_optional_bool,
    extract_optional_datetime,
    extract_optional_float,
    extract_optional_int,
    extract_optional_str,
    extract_raw_field,
    invoke_callback_with_retry,
    resolve_failed_callback_fn_for_dispatch,
    resolve_idempotency_or_raise,
    resolve_panel_runtime_profiles,
    resolve_policy_profile_or_raise,
    resolve_prompt_profile_or_raise,
    resolve_report_callback_fn_for_dispatch,
    resolve_tool_profile_or_raise,
    resolve_winner,
    safe_float,
    save_dispatch_receipt,
    validate_final_dispatch_request,
    validate_phase_dispatch_request,
)
from app.models import CaseCreateRequest, FinalDispatchRequest, PhaseDispatchRequest


def _build_case_payload(*, case_id: int, idempotency_key: str) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "scopeId": 1,
        "session_id": case_id + 10,
        "rubric_version": "v3",
        "judge_policy_version": "v3-default",
        "topic_domain": "tft",
        "retrieval_profile": "hybrid_v1",
        "trace_id": f"trace-case-{case_id}",
        "idempotency_key": idempotency_key,
    }


def _build_phase_payload(*, case_id: int, idempotency_key: str) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "scopeId": 1,
        "session_id": case_id + 30,
        "phase_no": 3,
        "message_start_id": 11,
        "message_end_id": 12,
        "message_count": 2,
        "messages": [
            {
                "message_id": 11,
                "side": "pro",
                "content": "pro message",
                "created_at": "2026-04-22T00:00:00Z",
            },
            {
                "message_id": 12,
                "side": "con",
                "content": "con message",
                "created_at": "2026-04-22T00:00:01Z",
            },
        ],
        "rubric_version": "v3",
        "judge_policy_version": "v3-default",
        "topic_domain": "tft",
        "retrieval_profile": "hybrid_v1",
        "trace_id": f"trace-phase-{case_id}",
        "idempotency_key": idempotency_key,
    }


def _build_final_payload(*, case_id: int, idempotency_key: str) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "scopeId": 1,
        "session_id": case_id + 40,
        "phase_start_no": 1,
        "phase_end_no": 4,
        "rubric_version": "v3",
        "judge_policy_version": "v3-default",
        "topic_domain": "tft",
        "trace_id": f"trace-final-{case_id}",
        "idempotency_key": idempotency_key,
    }


class JudgeCommandRoutesTests(unittest.TestCase):
    def test_extract_optional_helpers_should_parse_raw_values(self) -> None:
        payload = {
            "count": "7",
            "ratio": "0.25",
            "label": "  ready  ",
            "enabled": "YES",
            "rawOnly": "raw-value",
        }

        self.assertEqual(extract_raw_field(payload, "missing", "rawOnly"), "raw-value")
        self.assertEqual(extract_optional_int(payload, "count"), 7)
        self.assertEqual(extract_optional_float(payload, "ratio"), 0.25)
        self.assertEqual(extract_optional_str(payload, "label"), "ready")
        self.assertTrue(extract_optional_bool(payload, "enabled"))
        self.assertIsNone(extract_optional_int(payload, "missing"))
        self.assertIsNone(extract_optional_float({"ratio": "nan?"}, "ratio"))
        self.assertIsNone(extract_optional_bool({"enabled": "unknown"}, "enabled"))

    def test_extract_optional_datetime_should_support_z_and_normalizer(self) -> None:
        payload = {"ts": "2026-04-22T01:02:03Z"}
        parsed = extract_optional_datetime(payload, "ts")
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.isoformat(), "2026-04-22T01:02:03+00:00")

        normalized = extract_optional_datetime(
            payload,
            "ts",
            normalize_query_datetime=lambda value: None if value is None else value.replace(second=0),
        )
        self.assertIsNotNone(normalized)
        assert normalized is not None
        self.assertEqual(normalized.isoformat(), "2026-04-22T01:02:00+00:00")
        self.assertIsNone(extract_optional_datetime({"ts": "not-datetime"}, "ts"))

    def test_build_dispatch_meta_and_receipt_dims_should_normalize_raw_payload(self) -> None:
        raw_payload = _build_phase_payload(case_id=4001, idempotency_key="phase:4001")

        meta = build_dispatch_meta_from_raw(
            raw_payload,
            extract_optional_int=extract_optional_int,
            extract_optional_str=extract_optional_str,
        )
        dims = build_receipt_dims_from_raw(
            "phase",
            raw_payload,
            extract_optional_int=extract_optional_int,
        )

        self.assertEqual(meta["caseId"], 4001)
        self.assertEqual(meta["sessionId"], 4031)
        self.assertEqual(meta["idempotencyKey"], "phase:4001")
        self.assertEqual(dims["phaseNo"], 3)
        self.assertEqual(dims["messageCount"], 2)
        self.assertIsNone(dims["phaseStartNo"])

    def test_resolve_idempotency_or_raise_should_return_replayed_response(self) -> None:
        replayed = resolve_idempotency_or_raise(
            resolve_idempotency=lambda **kwargs: SimpleNamespace(
                status="replay",
                record=SimpleNamespace(response={"accepted": True, "status": "queued"}),
            ),
            key="phase:4101",
            job_id=4101,
            ttl_secs=3600,
            conflict_detail="idempotency_conflict:phase_dispatch",
        )

        self.assertIsNotNone(replayed)
        assert replayed is not None
        self.assertTrue(replayed["accepted"])
        self.assertTrue(replayed["idempotentReplay"])

    def test_resolve_idempotency_or_raise_should_raise_on_conflict(self) -> None:
        with self.assertRaises(JudgeCommandRouteError) as ctx:
            resolve_idempotency_or_raise(
                resolve_idempotency=lambda **kwargs: SimpleNamespace(
                    status="occupied",
                    record=None,
                ),
                key="phase:4102",
                job_id=4102,
                ttl_secs=3600,
                conflict_detail="idempotency_conflict:phase_dispatch",
            )
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail, "idempotency_conflict:phase_dispatch")

    def test_validate_dispatch_request_helpers_should_raise_422_on_invalid_ranges(self) -> None:
        phase_payload = _build_phase_payload(case_id=4201, idempotency_key="phase:4201")
        phase_payload["message_count"] = 1
        phase_payload["messages"] = []
        phase_request = PhaseDispatchRequest.model_validate(phase_payload)

        with self.assertRaises(JudgeCommandRouteError) as phase_ctx:
            validate_phase_dispatch_request(phase_request)
        self.assertEqual(phase_ctx.exception.status_code, 422)
        self.assertEqual(phase_ctx.exception.detail, "message_count_mismatch")

        final_payload = _build_final_payload(case_id=4202, idempotency_key="final:4202")
        final_payload["phase_start_no"] = 3
        final_payload["phase_end_no"] = 2
        final_request = FinalDispatchRequest.model_validate(final_payload)

        with self.assertRaises(JudgeCommandRouteError) as final_ctx:
            validate_final_dispatch_request(final_request)
        self.assertEqual(final_ctx.exception.status_code, 422)
        self.assertEqual(final_ctx.exception.detail, "invalid_phase_range")

    def test_resolve_callback_fn_for_dispatch_should_choose_by_dispatch_type(self) -> None:
        phase_failed = object()
        final_failed = object()
        phase_report = object()
        final_report = object()

        self.assertIs(
            resolve_failed_callback_fn_for_dispatch(
                dispatch_type="phase",
                callback_phase_failed_fn=phase_failed,
                callback_final_failed_fn=final_failed,
            ),
            phase_failed,
        )
        self.assertIs(
            resolve_failed_callback_fn_for_dispatch(
                dispatch_type="final",
                callback_phase_failed_fn=phase_failed,
                callback_final_failed_fn=final_failed,
            ),
            final_failed,
        )
        self.assertIs(
            resolve_report_callback_fn_for_dispatch(
                dispatch_type="phase",
                callback_phase_report_fn=phase_report,
                callback_final_report_fn=final_report,
            ),
            phase_report,
        )
        self.assertIs(
            resolve_report_callback_fn_for_dispatch(
                dispatch_type="final",
                callback_phase_report_fn=phase_report,
                callback_final_report_fn=final_report,
            ),
            final_report,
        )

    def test_invoke_callback_with_retry_should_retry_until_success(self) -> None:
        calls: dict[str, Any] = {"attempt": 0, "sleep": []}

        async def _callback(job_id: int, payload: dict[str, Any]) -> None:
            calls["attempt"] += 1
            if calls["attempt"] < 3:
                raise RuntimeError("temp-down")

        async def _sleep(seconds: float) -> None:
            calls["sleep"].append(seconds)

        attempts, retries = asyncio.run(
            invoke_callback_with_retry(
                callback_fn=_callback,
                job_id=5001,
                payload={"status": "reported"},
                max_attempts=5,
                backoff_ms=10,
                sleep_fn=_sleep,
            )
        )
        self.assertEqual(attempts, 3)
        self.assertEqual(retries, 2)
        self.assertEqual(calls["sleep"], [0.01, 0.02])

    def test_invoke_callback_with_retry_should_raise_after_max_attempts(self) -> None:
        async def _callback(job_id: int, payload: dict[str, Any]) -> None:
            raise RuntimeError("always-fail")

        with self.assertRaises(RuntimeError) as ctx:
            asyncio.run(
                invoke_callback_with_retry(
                    callback_fn=_callback,
                    job_id=5002,
                    payload={"status": "reported"},
                    max_attempts=2,
                    backoff_ms=0,
                    sleep_fn=lambda _seconds: asyncio.sleep(0),
                )
            )
        self.assertIn("after 2 attempts", str(ctx.exception))

    def test_save_dispatch_receipt_should_forward_payload_to_store(self) -> None:
        calls: dict[str, Any] = {}

        def _save_dispatch_receipt_fn(**kwargs: Any) -> None:
            calls["kwargs"] = dict(kwargs)

        save_dispatch_receipt(
            save_dispatch_receipt_fn=_save_dispatch_receipt_fn,
            dispatch_type="phase",
            job_id=5101,
            scope_id=1,
            session_id=5131,
            trace_id="trace-phase-5101",
            idempotency_key="phase:5101",
            rubric_version="v3",
            judge_policy_version="v3-default",
            topic_domain="tft",
            retrieval_profile="hybrid_v1",
            phase_no=3,
            phase_start_no=None,
            phase_end_no=None,
            message_start_id=11,
            message_end_id=12,
            message_count=2,
            status="reported",
            request_payload={"dispatchType": "phase"},
            response_payload={"accepted": True},
        )

        saved = calls["kwargs"]
        self.assertEqual(saved["dispatch_type"], "phase")
        self.assertEqual(saved["job_id"], 5101)
        self.assertEqual(saved["status"], "reported")
        self.assertEqual(saved["request"], {"dispatchType": "phase"})
        self.assertEqual(saved["response"], {"accepted": True})

    def test_safe_float_should_fallback_on_invalid_values(self) -> None:
        self.assertEqual(safe_float("1.5"), 1.5)
        self.assertEqual(safe_float(2), 2.0)
        self.assertEqual(safe_float("bad", default=9.0), 9.0)

    def test_resolve_winner_should_honor_margin(self) -> None:
        self.assertEqual(resolve_winner(8.5, 6.9, margin=1.0), "pro")
        self.assertEqual(resolve_winner(6.2, 7.6, margin=1.0), "con")
        self.assertEqual(resolve_winner(7.0, 6.4, margin=1.0), "draw")

    def test_build_final_report_payload_for_dispatch_should_list_phase_receipts_when_missing(
        self,
    ) -> None:
        calls: dict[str, Any] = {}

        def _list_dispatch_receipts(**kwargs: Any) -> list[Any]:
            calls["list"] = dict(kwargs)
            return [{"phaseNo": 1}, {"phaseNo": 2}]

        def _build_final_report_payload(**kwargs: Any) -> dict[str, Any]:
            calls["build"] = dict(kwargs)
            return {
                "accepted": True,
                "phaseCount": len(kwargs["phase_receipts"]),
            }

        result = build_final_report_payload_for_dispatch(
            request=SimpleNamespace(session_id=8101),
            phase_receipts=None,
            fairness_thresholds={"biasGap": 0.05},
            panel_runtime_profiles={"judgeA": {"judgeId": "judgeA"}},
            list_dispatch_receipts=_list_dispatch_receipts,
            build_final_report_payload=_build_final_report_payload,
            judge_style_mode="balanced",
        )

        self.assertEqual(calls["list"]["dispatch_type"], "phase")
        self.assertEqual(calls["list"]["session_id"], 8101)
        self.assertEqual(calls["build"]["judge_style_mode"], "balanced")
        self.assertEqual(len(calls["build"]["phase_receipts"]), 2)
        self.assertEqual(result["phaseCount"], 2)

    def test_build_final_report_payload_for_dispatch_should_use_given_phase_receipts(self) -> None:
        calls: dict[str, Any] = {"listCalled": False}

        def _list_dispatch_receipts(**kwargs: Any) -> list[Any]:
            calls["listCalled"] = True
            return [{"phaseNo": 9}]

        def _build_final_report_payload(**kwargs: Any) -> dict[str, Any]:
            calls["build"] = dict(kwargs)
            return {"accepted": True}

        provided_receipts: tuple[dict[str, Any], ...] = (
            {"phaseNo": 5},
            {"phaseNo": 6},
        )

        build_final_report_payload_for_dispatch(
            request=SimpleNamespace(session_id=8201),
            phase_receipts=provided_receipts,  # type: ignore[arg-type]
            fairness_thresholds=None,
            panel_runtime_profiles=None,
            list_dispatch_receipts=_list_dispatch_receipts,
            build_final_report_payload=_build_final_report_payload,
            judge_style_mode="strict",
        )

        self.assertFalse(calls["listCalled"])
        self.assertEqual(len(calls["build"]["phase_receipts"]), 2)
        self.assertIsNot(calls["build"]["phase_receipts"], provided_receipts)

    def test_resolve_registry_profile_helpers_should_resolve_profiles(self) -> None:
        policy_profile = object()
        prompt_profile = object()
        tool_profile = object()

        resolved_policy = resolve_policy_profile_or_raise(
            resolve_policy_profile=lambda **kwargs: SimpleNamespace(
                profile=policy_profile,
                error_code=None,
            ),
            judge_policy_version="v3-default",
            rubric_version="v3",
            topic_domain="tft",
        )
        resolved_prompt = resolve_prompt_profile_or_raise(
            get_prompt_profile=lambda _version: prompt_profile,
            prompt_registry_version="promptset-v3-default",
        )
        resolved_tool = resolve_tool_profile_or_raise(
            get_tool_profile=lambda _version: tool_profile,
            tool_registry_version="toolset-v3-default",
        )

        self.assertIs(resolved_policy, policy_profile)
        self.assertIs(resolved_prompt, prompt_profile)
        self.assertIs(resolved_tool, tool_profile)

    def test_resolve_registry_profile_helpers_should_raise_422_on_missing(self) -> None:
        with self.assertRaises(JudgeCommandRouteError) as policy_ctx:
            resolve_policy_profile_or_raise(
                resolve_policy_profile=lambda **kwargs: SimpleNamespace(
                    profile=None,
                    error_code="judge_policy_version_unknown",
                ),
                judge_policy_version="missing",
                rubric_version="v3",
                topic_domain="tft",
            )
        self.assertEqual(policy_ctx.exception.status_code, 422)
        self.assertEqual(policy_ctx.exception.detail, "judge_policy_version_unknown")

        with self.assertRaises(JudgeCommandRouteError) as prompt_ctx:
            resolve_prompt_profile_or_raise(
                get_prompt_profile=lambda _version: None,
                prompt_registry_version="missing",
            )
        self.assertEqual(prompt_ctx.exception.status_code, 422)
        self.assertEqual(prompt_ctx.exception.detail, "unknown_prompt_registry_version")

        with self.assertRaises(JudgeCommandRouteError) as tool_ctx:
            resolve_tool_profile_or_raise(
                get_tool_profile=lambda _version: None,
                tool_registry_version="missing",
            )
        self.assertEqual(tool_ctx.exception.status_code, 422)
        self.assertEqual(tool_ctx.exception.detail, "unknown_tool_registry_version")

    def test_attach_policy_trace_snapshot_should_fill_registry_trace_fields(self) -> None:
        report_payload: dict[str, Any] = {"status": "queued"}
        policy_profile = SimpleNamespace(version="policy-v3")
        prompt_profile = SimpleNamespace(version="prompt-v7")
        tool_profile = SimpleNamespace(version="tool-v5")

        attach_policy_trace_snapshot(
            report_payload=report_payload,
            profile=policy_profile,
            prompt_profile=prompt_profile,
            tool_profile=tool_profile,
            build_policy_trace_snapshot=lambda profile: {"policyVersion": profile.version},
            build_prompt_trace_snapshot=lambda profile: {"promptVersion": profile.version},
            build_tool_trace_snapshot=lambda profile: {"toolVersion": profile.version},
        )

        judge_trace = report_payload["judgeTrace"]
        self.assertEqual(judge_trace["policyRegistry"]["policyVersion"], "policy-v3")
        self.assertEqual(judge_trace["promptRegistry"]["promptVersion"], "prompt-v7")
        self.assertEqual(judge_trace["toolRegistry"]["toolVersion"], "tool-v5")
        self.assertEqual(
            judge_trace["registryVersions"],
            {
                "policyVersion": "policy-v3",
                "promptVersion": "prompt-v7",
                "toolsetVersion": "tool-v5",
            },
        )

    def test_attach_policy_trace_snapshot_should_noop_for_non_dict_payload(self) -> None:
        attach_policy_trace_snapshot(
            report_payload=None,
            profile=SimpleNamespace(version="policy-v3"),
            prompt_profile=SimpleNamespace(version="prompt-v7"),
            tool_profile=SimpleNamespace(version="tool-v5"),
            build_policy_trace_snapshot=lambda profile: {"policyVersion": profile.version},
            build_prompt_trace_snapshot=lambda profile: {"promptVersion": profile.version},
            build_tool_trace_snapshot=lambda profile: {"toolVersion": profile.version},
        )

    def test_resolve_panel_runtime_profiles_should_merge_metadata_and_defaults(self) -> None:
        profile = SimpleNamespace(
            version="v3-custom",
            tool_registry_version="toolset-v7",
            topic_domain="tft",
            prompt_versions={
                "summaryPromptVersion": "summary-v9",
                "agent2PromptVersion": "agent2-v9",
            },
            metadata={
                "panelRuntimeContext": {
                    "defaultDomainSlot": "tft_ranked",
                    "runtimeStage": "adaptive_bootstrap",
                    "adaptiveEnabled": True,
                    "candidateModels": ["gpt-5.4", "gpt-5.4", "gpt-5.4-mini"],
                    "strategyMetadata": {"calibrationVersion": "calib-local-v2"},
                    "shadowEnabled": True,
                    "shadowModelStrategy": "shadow_tri_panel_v1",
                    "shadowCostEstimate": "0.031",
                    "shadowLatencyEstimate": 1450,
                },
                "panelRuntimeProfiles": {
                    "judgeA": {
                        "profileId": "panel-a-custom",
                        "modelStrategy": "llm_vote",
                        "strategySlot": "adaptive_weighted_vote",
                        "scoreSource": "weighted_blend",
                        "decisionMargin": "0.45",
                        "promptVersion": "panel-prompt-v9",
                        "toolsetVersion": "toolset-custom",
                        "candidateModels": ["gpt-5.4", "gpt-5.4"],
                        "shadowCostEstimate": "0.027",
                    }
                },
            },
        )
        defaults = {
            "judgeA": {
                "promptVersionKey": "summaryPromptVersion",
                "profileId": "panel-judgeA-default-v1",
                "modelStrategy": "judge_dimension_composite",
                "strategySlot": "dimension_composite",
                "scoreSource": "dimension_composite",
                "decisionMargin": 0.8,
                "domainSlot": "tft",
                "runtimeStage": "bootstrap",
            },
            "judgeB": {
                "promptVersionKey": "agent2PromptVersion",
                "profileId": "panel-judgeB-default-v1",
                "modelStrategy": "judge_dimension_composite",
                "strategySlot": "dimension_composite",
                "scoreSource": "dimension_composite",
                "decisionMargin": 0.8,
                "domainSlot": "tft",
                "runtimeStage": "bootstrap",
            },
        }

        result = resolve_panel_runtime_profiles(
            profile=profile,
            panel_judge_ids=("judgeA", "judgeB"),
            panel_runtime_profile_defaults=defaults,
        )

        judge_a = result["judgeA"]
        self.assertEqual(judge_a["profileId"], "panel-a-custom")
        self.assertEqual(judge_a["modelStrategy"], "llm_vote")
        self.assertEqual(judge_a["strategySlot"], "adaptive_weighted_vote")
        self.assertEqual(judge_a["scoreSource"], "weighted_blend")
        self.assertEqual(judge_a["decisionMargin"], 0.45)
        self.assertEqual(judge_a["promptVersion"], "panel-prompt-v9")
        self.assertEqual(judge_a["toolsetVersion"], "toolset-custom")
        self.assertEqual(judge_a["domainSlot"], "tft_ranked")
        self.assertEqual(judge_a["runtimeStage"], "adaptive_bootstrap")
        self.assertTrue(judge_a["adaptiveEnabled"])
        self.assertEqual(judge_a["candidateModels"], ["gpt-5.4"])
        self.assertEqual(judge_a["profileSource"], "policy_metadata")
        self.assertEqual(judge_a["policyVersion"], "v3-custom")
        self.assertTrue(judge_a["shadowEnabled"])
        self.assertEqual(judge_a["shadowModelStrategy"], "shadow_tri_panel_v1")
        self.assertEqual(judge_a["shadowCostEstimate"], 0.027)
        self.assertEqual(judge_a["shadowLatencyEstimate"], 1450.0)

        judge_b = result["judgeB"]
        self.assertEqual(judge_b["profileId"], "panel-judgeB-default-v1")
        self.assertEqual(judge_b["promptVersion"], "agent2-v9")
        self.assertEqual(judge_b["toolsetVersion"], "toolset-v7")
        self.assertEqual(judge_b["domainSlot"], "tft_ranked")
        self.assertEqual(judge_b["runtimeStage"], "adaptive_bootstrap")
        self.assertTrue(judge_b["adaptiveEnabled"])
        self.assertEqual(judge_b["candidateModels"], ["gpt-5.4", "gpt-5.4-mini"])
        self.assertEqual(
            judge_b["strategyMetadata"],
            {"calibrationVersion": "calib-local-v2"},
        )
        self.assertEqual(judge_b["profileSource"], "builtin_default")
        self.assertTrue(judge_b["shadowEnabled"])
        self.assertEqual(judge_b["shadowModelStrategy"], "shadow_tri_panel_v1")
        self.assertEqual(judge_b["shadowCostEstimate"], 0.031)
        self.assertEqual(judge_b["shadowLatencyEstimate"], 1450.0)

    def test_resolve_panel_runtime_profiles_should_fallback_to_general_topic_defaults(self) -> None:
        profile = SimpleNamespace(
            version="v3-default",
            tool_registry_version="",
            topic_domain="*",
            prompt_versions={},
            metadata={},
        )
        defaults = {
            "judgeA": {
                "promptVersionKey": "summaryPromptVersion",
                "profileId": "panel-judgeA-default-v1",
                "modelStrategy": "judge_dimension_composite",
                "strategySlot": "dimension_composite",
                "scoreSource": "dimension_composite",
                "decisionMargin": 0.75,
                "domainSlot": "tft",
                "runtimeStage": "bootstrap",
            }
        }

        result = resolve_panel_runtime_profiles(
            profile=profile,
            panel_judge_ids=("judgeA",),
            panel_runtime_profile_defaults=defaults,
        )
        judge_a = result["judgeA"]

        self.assertEqual(judge_a["domainSlot"], "general")
        self.assertEqual(judge_a["runtimeStage"], "bootstrap")
        self.assertFalse(judge_a["adaptiveEnabled"])
        self.assertEqual(judge_a["candidateModels"], [])
        self.assertEqual(judge_a["strategyMetadata"], {})
        self.assertEqual(judge_a["decisionMargin"], 0.75)
        self.assertIsNone(judge_a["toolsetVersion"])
        self.assertIsNone(judge_a["promptVersion"])
        self.assertFalse(judge_a["shadowEnabled"])
        self.assertEqual(judge_a["shadowModelStrategy"], "judge_dimension_composite")
        self.assertEqual(judge_a["shadowCostEstimate"], 0.0)
        self.assertEqual(judge_a["shadowLatencyEstimate"], 0.0)
        self.assertEqual(judge_a["profileSource"], "builtin_default")

    def test_build_case_create_route_payload_should_return_case_built_response(self) -> None:
        raw_payload = _build_case_payload(case_id=4101, idempotency_key="case:4101")
        calls: dict[str, Any] = {}

        def _resolve_idempotency_or_raise(*, key: str, job_id: int, conflict_detail: str) -> None:
            calls["idempotency"] = {
                "key": key,
                "jobId": job_id,
                "conflictDetail": conflict_detail,
            }
            return None

        async def _ensure_registry_runtime_ready() -> None:
            calls["registryReady"] = True

        def _resolve_policy_profile(
            *,
            judge_policy_version: str,
            rubric_version: str,
            topic_domain: str,
        ) -> Any:
            calls["policy"] = {
                "judgePolicyVersion": judge_policy_version,
                "rubricVersion": rubric_version,
                "topicDomain": topic_domain,
            }
            return SimpleNamespace(
                version="v3-default",
                prompt_registry_version="promptset-v3-default",
                tool_registry_version="toolset-v3-default",
            )

        def _resolve_prompt_profile(*, prompt_registry_version: str) -> Any:
            calls["prompt"] = prompt_registry_version
            return SimpleNamespace(version="promptset-v3-default")

        def _resolve_tool_profile(*, tool_registry_version: str) -> Any:
            calls["tool"] = tool_registry_version
            return SimpleNamespace(version="toolset-v3-default")

        async def _workflow_get_job(*, job_id: int) -> Any:
            calls["workflowGetJob"] = job_id
            return None

        def _build_workflow_job(**kwargs: Any) -> dict[str, Any]:
            calls["workflowJob"] = dict(kwargs)
            return dict(kwargs)

        async def _workflow_register_and_mark_case_built(
            *,
            job: dict[str, Any],
            event_payload: dict[str, Any],
        ) -> dict[str, Any]:
            calls["workflowRegister"] = {
                "job": dict(job),
                "eventPayload": dict(event_payload),
            }
            return {"status": "case_built", "jobId": job["job_id"]}

        def _serialize_workflow_job(job: dict[str, Any]) -> dict[str, Any]:
            return {"status": str(job.get("status") or "case_built")}

        def _trace_register_start(*, job_id: int, trace_id: str, request: dict[str, Any]) -> None:
            calls["traceStart"] = {
                "jobId": job_id,
                "traceId": trace_id,
                "request": dict(request),
            }

        def _trace_register_success(
            *,
            job_id: int,
            response: dict[str, Any],
            callback_status: str,
            report_summary: dict[str, Any],
        ) -> None:
            calls["traceSuccess"] = {
                "jobId": job_id,
                "response": dict(response),
                "callbackStatus": callback_status,
                "reportSummary": dict(report_summary),
            }

        def _build_trace_report_summary(**kwargs: Any) -> dict[str, Any]:
            calls["traceSummary"] = dict(kwargs)
            return {"dispatchType": kwargs.get("dispatch_type"), "callbackStatus": "case_built"}

        def _set_idempotency_success(
            *,
            key: str,
            job_id: int,
            response: dict[str, Any],
            ttl_secs: int,
        ) -> None:
            calls["idempotencySuccess"] = {
                "key": key,
                "jobId": job_id,
                "response": dict(response),
                "ttlSecs": ttl_secs,
            }

        response = asyncio.run(
            build_case_create_route_payload(
                raw_payload=raw_payload,
                case_create_model_validate=CaseCreateRequest.model_validate,
                resolve_idempotency_or_raise=_resolve_idempotency_or_raise,
                ensure_registry_runtime_ready=_ensure_registry_runtime_ready,
                resolve_policy_profile=_resolve_policy_profile,
                resolve_prompt_profile=_resolve_prompt_profile,
                resolve_tool_profile=_resolve_tool_profile,
                workflow_get_job=_workflow_get_job,
                build_workflow_job=_build_workflow_job,
                workflow_register_and_mark_case_built=_workflow_register_and_mark_case_built,
                serialize_workflow_job=_serialize_workflow_job,
                trace_register_start=_trace_register_start,
                trace_register_success=_trace_register_success,
                build_trace_report_summary=_build_trace_report_summary,
                set_idempotency_success=_set_idempotency_success,
                idempotency_ttl_secs=3600,
            )
        )

        self.assertTrue(response["accepted"])
        self.assertEqual(response["status"], "case_built")
        self.assertEqual(response["caseId"], 4101)
        self.assertEqual(response["registryVersions"]["policyVersion"], "v3-default")
        self.assertEqual(response["registryVersions"]["promptVersion"], "promptset-v3-default")
        self.assertEqual(response["registryVersions"]["toolsetVersion"], "toolset-v3-default")
        self.assertEqual(response["workflow"]["status"], "case_built")
        self.assertEqual(calls["idempotency"]["conflictDetail"], "idempotency_conflict:case_create")
        self.assertEqual(calls["workflowGetJob"], 4101)
        self.assertEqual(calls["traceStart"]["traceId"], "trace-case-4101")
        self.assertEqual(calls["idempotencySuccess"]["ttlSecs"], 3600)

    def test_build_case_create_route_payload_should_raise_422_for_validation_error(self) -> None:
        with self.assertRaises(JudgeCommandRouteError) as ctx:
            asyncio.run(
                build_case_create_route_payload(
                    raw_payload={},
                    case_create_model_validate=CaseCreateRequest.model_validate,
                    resolve_idempotency_or_raise=lambda **kwargs: None,
                    ensure_registry_runtime_ready=lambda: asyncio.sleep(0),
                    resolve_policy_profile=lambda **kwargs: None,
                    resolve_prompt_profile=lambda **kwargs: None,
                    resolve_tool_profile=lambda **kwargs: None,
                    workflow_get_job=lambda **kwargs: asyncio.sleep(0),
                    build_workflow_job=lambda **kwargs: {},
                    workflow_register_and_mark_case_built=lambda **kwargs: asyncio.sleep(0),
                    serialize_workflow_job=lambda job: {},
                    trace_register_start=lambda **kwargs: None,
                    trace_register_success=lambda **kwargs: None,
                    build_trace_report_summary=lambda **kwargs: {},
                    set_idempotency_success=lambda **kwargs: None,
                    idempotency_ttl_secs=3600,
                )
            )

        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIsInstance(ctx.exception.detail, list)

    def test_build_case_create_route_payload_should_short_circuit_on_idempotent_replay(self) -> None:
        replay_payload = {"accepted": True, "idempotentReplay": True}
        route_payload = asyncio.run(
            build_case_create_route_payload(
                raw_payload=_build_case_payload(case_id=4201, idempotency_key="case:4201"),
                case_create_model_validate=CaseCreateRequest.model_validate,
                resolve_idempotency_or_raise=lambda **kwargs: replay_payload,
                ensure_registry_runtime_ready=lambda: asyncio.sleep(0),
                resolve_policy_profile=lambda **kwargs: None,
                resolve_prompt_profile=lambda **kwargs: None,
                resolve_tool_profile=lambda **kwargs: None,
                workflow_get_job=lambda **kwargs: asyncio.sleep(0),
                build_workflow_job=lambda **kwargs: {},
                workflow_register_and_mark_case_built=lambda **kwargs: asyncio.sleep(0),
                serialize_workflow_job=lambda job: {},
                trace_register_start=lambda **kwargs: None,
                trace_register_success=lambda **kwargs: None,
                build_trace_report_summary=lambda **kwargs: {},
                set_idempotency_success=lambda **kwargs: None,
                idempotency_ttl_secs=3600,
            )
        )
        self.assertEqual(route_payload, replay_payload)

    def test_build_case_create_route_payload_should_raise_409_when_case_exists(self) -> None:
        async def _workflow_get_job(*, job_id: int) -> Any:
            return {"jobId": job_id}

        with self.assertRaises(JudgeCommandRouteError) as ctx:
            asyncio.run(
                build_case_create_route_payload(
                    raw_payload=_build_case_payload(case_id=4301, idempotency_key="case:4301"),
                    case_create_model_validate=CaseCreateRequest.model_validate,
                    resolve_idempotency_or_raise=lambda **kwargs: None,
                    ensure_registry_runtime_ready=lambda: asyncio.sleep(0),
                    resolve_policy_profile=lambda **kwargs: SimpleNamespace(
                        version="v3-default",
                        prompt_registry_version="promptset-v3-default",
                        tool_registry_version="toolset-v3-default",
                    ),
                    resolve_prompt_profile=lambda **kwargs: SimpleNamespace(version="promptset-v3-default"),
                    resolve_tool_profile=lambda **kwargs: SimpleNamespace(version="toolset-v3-default"),
                    workflow_get_job=_workflow_get_job,
                    build_workflow_job=lambda **kwargs: {},
                    workflow_register_and_mark_case_built=lambda **kwargs: asyncio.sleep(0),
                    serialize_workflow_job=lambda job: {},
                    trace_register_start=lambda **kwargs: None,
                    trace_register_success=lambda **kwargs: None,
                    build_trace_report_summary=lambda **kwargs: {},
                    set_idempotency_success=lambda **kwargs: None,
                    idempotency_ttl_secs=3600,
                )
            )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail, "case_already_exists")

    def test_build_phase_dispatch_preflight_route_payload_should_return_route_bundle(self) -> None:
        raw_payload = _build_phase_payload(case_id=5101, idempotency_key="phase:5101")
        calls: dict[str, Any] = {}

        def _validate_phase_dispatch_request(payload: Any) -> None:
            calls["validated"] = bool(getattr(payload, "case_id", 0))

        def _resolve_idempotency_or_raise(*, key: str, job_id: int, conflict_detail: str) -> None:
            calls["idempotency"] = {
                "key": key,
                "jobId": job_id,
                "conflictDetail": conflict_detail,
            }
            return None

        async def _ensure_registry_runtime_ready() -> None:
            calls["registryReady"] = True

        def _resolve_policy_profile(**kwargs: Any) -> Any:
            calls["policy"] = dict(kwargs)
            return SimpleNamespace(
                version="v3-default",
                prompt_registry_version="promptset-v3-default",
                tool_registry_version="toolset-v3-default",
            )

        def _resolve_prompt_profile(*, prompt_registry_version: str) -> Any:
            calls["prompt"] = prompt_registry_version
            return SimpleNamespace(version="promptset-v3-default")

        def _resolve_tool_profile(*, tool_registry_version: str) -> Any:
            calls["tool"] = tool_registry_version
            return SimpleNamespace(version="toolset-v3-default")

        def _build_phase_dispatch_accepted_response(*, request: Any) -> dict[str, Any]:
            calls["accepted"] = request.case_id
            return {"accepted": True, "dispatchType": "phase", "caseId": request.case_id}

        def _build_workflow_job(**kwargs: Any) -> dict[str, Any]:
            calls["workflowJob"] = dict(kwargs)
            return dict(kwargs)

        def _trace_register_start(*, job_id: int, trace_id: str, request: dict[str, Any]) -> None:
            calls["traceStart"] = {"jobId": job_id, "traceId": trace_id, "request": dict(request)}

        async def _persist_dispatch_receipt(**kwargs: Any) -> None:
            calls["persistReceipt"] = dict(kwargs)

        async def _workflow_register_and_mark_blinded(*, job: dict[str, Any], event_payload: dict[str, Any]) -> None:
            calls["workflowBlinded"] = {"job": dict(job), "eventPayload": dict(event_payload)}

        def _build_phase_workflow_register_payload(**kwargs: Any) -> dict[str, Any]:
            calls["workflowRegisterPayload"] = dict(kwargs)
            request = kwargs["request"]
            return {
                "dispatchType": "phase",
                "traceId": request.trace_id,
                "policyVersion": kwargs["policy_version"],
                "promptVersion": kwargs["prompt_version"],
                "toolsetVersion": kwargs["toolset_version"],
            }

        result = asyncio.run(
            build_phase_dispatch_preflight_route_payload(
                raw_payload=raw_payload,
                phase_dispatch_model_validate=PhaseDispatchRequest.model_validate,
                validate_phase_dispatch_request=_validate_phase_dispatch_request,
                resolve_idempotency_or_raise=_resolve_idempotency_or_raise,
                ensure_registry_runtime_ready=_ensure_registry_runtime_ready,
                resolve_policy_profile=_resolve_policy_profile,
                resolve_prompt_profile=_resolve_prompt_profile,
                resolve_tool_profile=_resolve_tool_profile,
                build_phase_dispatch_accepted_response=_build_phase_dispatch_accepted_response,
                build_workflow_job=_build_workflow_job,
                trace_register_start=_trace_register_start,
                persist_dispatch_receipt=_persist_dispatch_receipt,
                workflow_register_and_mark_blinded=_workflow_register_and_mark_blinded,
                build_phase_workflow_register_payload=_build_phase_workflow_register_payload,
            )
        )

        self.assertEqual(calls["idempotency"]["conflictDetail"], "idempotency_conflict:phase_dispatch")
        self.assertTrue(calls["validated"])
        self.assertTrue(calls["registryReady"])
        self.assertEqual(calls["workflowJob"]["retrieval_profile"], "hybrid_v1")
        self.assertEqual(calls["persistReceipt"]["status"], "queued")
        self.assertEqual(calls["workflowBlinded"]["eventPayload"]["dispatchType"], "phase")
        self.assertEqual(result["response"]["dispatchType"], "phase")
        self.assertEqual(result["requestPayload"]["case_id"], 5101)

    def test_build_phase_dispatch_preflight_route_payload_should_short_circuit_idempotent_replay(self) -> None:
        replayed = {"accepted": True, "idempotentReplay": True}
        route_payload = asyncio.run(
            build_phase_dispatch_preflight_route_payload(
                raw_payload=_build_phase_payload(case_id=5102, idempotency_key="phase:5102"),
                phase_dispatch_model_validate=PhaseDispatchRequest.model_validate,
                validate_phase_dispatch_request=lambda payload: None,
                resolve_idempotency_or_raise=lambda **kwargs: replayed,
                ensure_registry_runtime_ready=lambda: asyncio.sleep(0),
                resolve_policy_profile=lambda **kwargs: None,
                resolve_prompt_profile=lambda **kwargs: None,
                resolve_tool_profile=lambda **kwargs: None,
                build_phase_dispatch_accepted_response=lambda **kwargs: {},
                build_workflow_job=lambda **kwargs: {},
                trace_register_start=lambda **kwargs: None,
                persist_dispatch_receipt=lambda **kwargs: asyncio.sleep(0),
                workflow_register_and_mark_blinded=lambda **kwargs: asyncio.sleep(0),
                build_phase_workflow_register_payload=lambda **kwargs: {},
            )
        )
        self.assertEqual(route_payload["replayedResponse"], replayed)

    def test_build_phase_dispatch_preflight_route_payload_should_map_http_validation_error(self) -> None:
        class _FakeHttpValidationError(Exception):
            status_code = 422
            detail = "invalid_message_range"

        def _raise_http_error(_: Any) -> None:
            raise _FakeHttpValidationError()

        with self.assertRaises(JudgeCommandRouteError) as ctx:
            asyncio.run(
                build_phase_dispatch_preflight_route_payload(
                    raw_payload=_build_phase_payload(case_id=5103, idempotency_key="phase:5103"),
                    phase_dispatch_model_validate=PhaseDispatchRequest.model_validate,
                    validate_phase_dispatch_request=_raise_http_error,
                    resolve_idempotency_or_raise=lambda **kwargs: None,
                    ensure_registry_runtime_ready=lambda: asyncio.sleep(0),
                    resolve_policy_profile=lambda **kwargs: None,
                    resolve_prompt_profile=lambda **kwargs: None,
                    resolve_tool_profile=lambda **kwargs: None,
                    build_phase_dispatch_accepted_response=lambda **kwargs: {},
                    build_workflow_job=lambda **kwargs: {},
                    trace_register_start=lambda **kwargs: None,
                    persist_dispatch_receipt=lambda **kwargs: asyncio.sleep(0),
                    workflow_register_and_mark_blinded=lambda **kwargs: asyncio.sleep(0),
                    build_phase_workflow_register_payload=lambda **kwargs: {},
                )
            )

        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail, "invalid_message_range")

    def test_build_final_dispatch_preflight_route_payload_should_return_route_bundle(self) -> None:
        raw_payload = _build_final_payload(case_id=5201, idempotency_key="final:5201")
        calls: dict[str, Any] = {}

        def _resolve_idempotency_or_raise(*, key: str, job_id: int, conflict_detail: str) -> None:
            calls["idempotency"] = {
                "key": key,
                "jobId": job_id,
                "conflictDetail": conflict_detail,
            }
            return None

        async def _ensure_registry_runtime_ready() -> None:
            calls["registryReady"] = True

        def _resolve_policy_profile(**kwargs: Any) -> Any:
            calls["policy"] = dict(kwargs)
            return SimpleNamespace(
                version="v3-default",
                prompt_registry_version="promptset-v3-default",
                tool_registry_version="toolset-v3-default",
            )

        def _resolve_prompt_profile(*, prompt_registry_version: str) -> Any:
            calls["prompt"] = prompt_registry_version
            return SimpleNamespace(version="promptset-v3-default")

        def _resolve_tool_profile(*, tool_registry_version: str) -> Any:
            calls["tool"] = tool_registry_version
            return SimpleNamespace(version="toolset-v3-default")

        def _build_final_dispatch_accepted_response(*, request: Any) -> dict[str, Any]:
            calls["accepted"] = request.case_id
            return {"accepted": True, "dispatchType": "final", "caseId": request.case_id}

        def _build_workflow_job(**kwargs: Any) -> dict[str, Any]:
            calls["workflowJob"] = dict(kwargs)
            return dict(kwargs)

        def _trace_register_start(*, job_id: int, trace_id: str, request: dict[str, Any]) -> None:
            calls["traceStart"] = {"jobId": job_id, "traceId": trace_id, "request": dict(request)}

        async def _persist_dispatch_receipt(**kwargs: Any) -> None:
            calls["persistReceipt"] = dict(kwargs)

        async def _workflow_register_and_mark_blinded(*, job: dict[str, Any], event_payload: dict[str, Any]) -> None:
            calls["workflowBlinded"] = {"job": dict(job), "eventPayload": dict(event_payload)}

        def _build_final_workflow_register_payload(**kwargs: Any) -> dict[str, Any]:
            calls["workflowRegisterPayload"] = dict(kwargs)
            request = kwargs["request"]
            return {
                "dispatchType": "final",
                "traceId": request.trace_id,
                "policyVersion": kwargs["policy_version"],
                "promptVersion": kwargs["prompt_version"],
                "toolsetVersion": kwargs["toolset_version"],
            }

        result = asyncio.run(
            build_final_dispatch_preflight_route_payload(
                raw_payload=raw_payload,
                final_dispatch_model_validate=FinalDispatchRequest.model_validate,
                validate_final_dispatch_request=lambda payload: None,
                resolve_idempotency_or_raise=_resolve_idempotency_or_raise,
                ensure_registry_runtime_ready=_ensure_registry_runtime_ready,
                resolve_policy_profile=_resolve_policy_profile,
                resolve_prompt_profile=_resolve_prompt_profile,
                resolve_tool_profile=_resolve_tool_profile,
                build_final_dispatch_accepted_response=_build_final_dispatch_accepted_response,
                build_workflow_job=_build_workflow_job,
                trace_register_start=_trace_register_start,
                persist_dispatch_receipt=_persist_dispatch_receipt,
                workflow_register_and_mark_blinded=_workflow_register_and_mark_blinded,
                build_final_workflow_register_payload=_build_final_workflow_register_payload,
            )
        )

        self.assertEqual(calls["idempotency"]["conflictDetail"], "idempotency_conflict:final_dispatch")
        self.assertTrue(calls["registryReady"])
        self.assertIsNone(calls["workflowJob"]["retrieval_profile"])
        self.assertEqual(calls["persistReceipt"]["status"], "queued")
        self.assertEqual(calls["workflowBlinded"]["eventPayload"]["dispatchType"], "final")
        self.assertEqual(result["response"]["dispatchType"], "final")
        self.assertEqual(result["requestPayload"]["case_id"], 5201)

    def test_build_blindization_rejection_route_payload_should_raise_422_and_record_failed_reported(self) -> None:
        calls: dict[str, Any] = {}

        def _extract_dispatch_meta_from_raw(payload: dict[str, Any]) -> dict[str, Any]:
            return {
                "caseId": payload.get("case_id"),
                "scopeId": payload.get("scopeId"),
                "sessionId": payload.get("session_id"),
                "traceId": payload.get("trace_id"),
                "idempotencyKey": payload.get("idempotency_key"),
                "rubricVersion": payload.get("rubric_version"),
                "judgePolicyVersion": payload.get("judge_policy_version"),
                "topicDomain": payload.get("topic_domain"),
                "retrievalProfile": payload.get("retrieval_profile"),
            }

        def _extract_receipt_dims_from_raw(_: str, payload: dict[str, Any]) -> dict[str, int | None]:
            return {
                "phaseNo": payload.get("phase_no"),
                "phaseStartNo": None,
                "phaseEndNo": None,
                "messageStartId": payload.get("message_start_id"),
                "messageEndId": payload.get("message_end_id"),
                "messageCount": payload.get("message_count"),
            }

        def _build_workflow_job(**kwargs: Any) -> dict[str, Any]:
            calls["workflowJob"] = dict(kwargs)
            return dict(kwargs)

        def _trace_register_start(*, job_id: int, trace_id: str, request: dict[str, Any]) -> None:
            calls["traceStart"] = {"jobId": job_id, "traceId": trace_id, "request": dict(request)}

        async def _workflow_register_and_mark_blinded(*, job: dict[str, Any], event_payload: dict[str, Any]) -> None:
            calls["workflowBlinded"] = {"job": dict(job), "eventPayload": dict(event_payload)}

        def _build_failed_callback_payload(**kwargs: Any) -> dict[str, Any]:
            calls["failedPayload"] = dict(kwargs)
            return dict(kwargs)

        async def _invoke_failed_callback_with_retry(*, case_id: int, payload: dict[str, Any]) -> tuple[int, int]:
            calls["failedInvoke"] = {"caseId": case_id, "payload": dict(payload)}
            return 1, 0

        def _with_error_contract(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            out = dict(payload)
            out["errorCode"] = kwargs.get("error_code")
            return out

        async def _persist_dispatch_receipt(**kwargs: Any) -> None:
            calls["persistReceipt"] = dict(kwargs)

        def _trace_register_failure(*, job_id: int, response: dict[str, Any], callback_status: str, callback_error: str) -> None:
            calls["traceFailure"] = {
                "jobId": job_id,
                "response": dict(response),
                "callbackStatus": callback_status,
                "callbackError": callback_error,
            }

        async def _workflow_mark_failed(**kwargs: Any) -> None:
            calls["workflowFailed"] = dict(kwargs)

        with self.assertRaises(JudgeCommandRouteError) as ctx:
            asyncio.run(
                build_blindization_rejection_route_payload(
                    dispatch_type="phase",
                    raw_payload=_build_phase_payload(case_id=5301, idempotency_key="phase:5301"),
                    sensitive_hits=["messages[0].user_id"],
                    extract_dispatch_meta_from_raw=_extract_dispatch_meta_from_raw,
                    extract_receipt_dims_from_raw=_extract_receipt_dims_from_raw,
                    build_workflow_job=_build_workflow_job,
                    trace_register_start=_trace_register_start,
                    workflow_register_and_mark_blinded=_workflow_register_and_mark_blinded,
                    build_failed_callback_payload=_build_failed_callback_payload,
                    invoke_failed_callback_with_retry=_invoke_failed_callback_with_retry,
                    with_error_contract=_with_error_contract,
                    persist_dispatch_receipt=_persist_dispatch_receipt,
                    trace_register_failure=_trace_register_failure,
                    workflow_mark_failed=_workflow_mark_failed,
                )
            )

        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail, "input_not_blinded")
        self.assertEqual(calls["traceStart"]["jobId"], 5301)
        self.assertEqual(calls["workflowBlinded"]["eventPayload"]["rejectionCode"], "input_not_blinded")
        self.assertEqual(calls["traceFailure"]["callbackStatus"], "failed_reported")
        self.assertEqual(calls["persistReceipt"]["status"], "callback_failed")
        self.assertEqual(calls["workflowFailed"]["error_code"], "input_not_blinded")

    def test_build_blindization_rejection_route_payload_should_raise_502_when_failed_callback_fails(self) -> None:
        async def _raise_failed_callback(*, case_id: int, payload: dict[str, Any]) -> tuple[int, int]:
            raise RuntimeError("failed-callback-down")

        with self.assertRaises(JudgeCommandRouteError) as ctx:
            asyncio.run(
                build_blindization_rejection_route_payload(
                    dispatch_type="phase",
                    raw_payload=_build_phase_payload(case_id=5302, idempotency_key="phase:5302"),
                    sensitive_hits=["messages[0].vip"],
                    extract_dispatch_meta_from_raw=lambda payload: {
                        "caseId": payload.get("case_id"),
                        "scopeId": payload.get("scopeId"),
                        "sessionId": payload.get("session_id"),
                        "traceId": payload.get("trace_id"),
                        "idempotencyKey": payload.get("idempotency_key"),
                        "rubricVersion": payload.get("rubric_version"),
                        "judgePolicyVersion": payload.get("judge_policy_version"),
                        "topicDomain": payload.get("topic_domain"),
                        "retrievalProfile": payload.get("retrieval_profile"),
                    },
                    extract_receipt_dims_from_raw=lambda _dispatch_type, payload: {
                        "phaseNo": payload.get("phase_no"),
                        "phaseStartNo": None,
                        "phaseEndNo": None,
                        "messageStartId": payload.get("message_start_id"),
                        "messageEndId": payload.get("message_end_id"),
                        "messageCount": payload.get("message_count"),
                    },
                    build_workflow_job=lambda **kwargs: dict(kwargs),
                    trace_register_start=lambda **kwargs: None,
                    workflow_register_and_mark_blinded=lambda **kwargs: asyncio.sleep(0),
                    build_failed_callback_payload=lambda **kwargs: dict(kwargs),
                    invoke_failed_callback_with_retry=_raise_failed_callback,
                    with_error_contract=lambda payload, **kwargs: dict(payload),
                    persist_dispatch_receipt=lambda **kwargs: asyncio.sleep(0),
                    trace_register_failure=lambda **kwargs: None,
                    workflow_mark_failed=lambda **kwargs: asyncio.sleep(0),
                )
            )

        self.assertEqual(ctx.exception.status_code, 502)
        self.assertIn("phase_failed_callback_failed", str(ctx.exception.detail))

    def test_build_phase_dispatch_callback_delivery_route_payload_should_build_failed_payload(self) -> None:
        parsed = SimpleNamespace(case_id=5351, trace_id="trace-phase-5351")
        calls: dict[str, Any] = {}

        async def _deliver_report_callback_with_failed_fallback(**kwargs: Any) -> Any:
            calls["deliver"] = dict(kwargs)
            calls["failedPayload"] = kwargs["build_failed_payload"]("phase-retry-exhausted")
            return SimpleNamespace(callback_status="reported")

        result = asyncio.run(
            build_phase_dispatch_callback_delivery_route_payload(
                parsed=parsed,
                report_payload={"degradationLevel": 2},
                deliver_report_callback_with_failed_fallback=_deliver_report_callback_with_failed_fallback,
                report_callback_fn=object(),
                failed_callback_fn=object(),
                invoke_with_retry=lambda *args, **kwargs: asyncio.sleep(0),
                build_failed_callback_payload=lambda **kwargs: dict(kwargs),
            )
        )

        self.assertEqual(result.callback_status, "reported")
        self.assertEqual(calls["deliver"]["job_id"], 5351)
        self.assertEqual(calls["failedPayload"]["dispatch_type"], "phase")
        self.assertEqual(calls["failedPayload"]["error_code"], "phase_callback_retry_exhausted")
        self.assertEqual(calls["failedPayload"]["degradation_level"], 2)

    def test_build_final_dispatch_callback_delivery_route_payload_should_build_failed_payload(self) -> None:
        parsed = SimpleNamespace(case_id=5352, trace_id="trace-final-5352")
        calls: dict[str, Any] = {}

        async def _deliver_report_callback_with_failed_fallback(**kwargs: Any) -> Any:
            calls["deliver"] = dict(kwargs)
            calls["failedPayload"] = kwargs["build_failed_payload"]("final-retry-exhausted")
            return SimpleNamespace(callback_status="reported")

        result = asyncio.run(
            build_final_dispatch_callback_delivery_route_payload(
                parsed=parsed,
                report_payload={"degradationLevel": 3},
                deliver_report_callback_with_failed_fallback=_deliver_report_callback_with_failed_fallback,
                report_callback_fn=object(),
                failed_callback_fn=object(),
                invoke_with_retry=lambda *args, **kwargs: asyncio.sleep(0),
                build_failed_callback_payload=lambda **kwargs: dict(kwargs),
            )
        )

        self.assertEqual(result.callback_status, "reported")
        self.assertEqual(calls["deliver"]["job_id"], 5352)
        self.assertEqual(calls["failedPayload"]["dispatch_type"], "final")
        self.assertEqual(calls["failedPayload"]["error_code"], "final_callback_retry_exhausted")
        self.assertEqual(calls["failedPayload"]["degradation_level"], 3)

    def test_build_phase_dispatch_callback_result_route_payload_should_raise_502_for_failed_reported(self) -> None:
        parsed = SimpleNamespace(
            case_id=5401,
            scope_id=1,
            session_id=5411,
            trace_id="trace-phase-5401",
            idempotency_key="phase:5401",
            rubric_version="v3",
            judge_policy_version="v3-default",
            topic_domain="tft",
            retrieval_profile="hybrid_v1",
            phase_no=3,
            message_start_id=11,
            message_end_id=12,
            message_count=2,
        )
        callback_outcome = SimpleNamespace(
            callback_status="failed_reported",
            report_error="retry exhausted",
            failed_payload={"errorCode": "phase_callback_retry_exhausted"},
            failed_attempts=2,
            failed_retries=1,
        )
        calls: dict[str, Any] = {}

        def _with_error_contract(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            out = dict(payload)
            out["errorCode"] = kwargs.get("error_code")
            return out

        async def _persist_dispatch_receipt(**kwargs: Any) -> None:
            calls["receipt"] = dict(kwargs)

        def _trace_register_failure(**kwargs: Any) -> None:
            calls["traceFailure"] = dict(kwargs)

        async def _workflow_mark_failed(**kwargs: Any) -> None:
            calls["workflowFailed"] = dict(kwargs)

        with self.assertRaises(JudgeCommandRouteError) as ctx:
            asyncio.run(
                build_phase_dispatch_callback_result_route_payload(
                    parsed=parsed,
                    response={"accepted": True, "dispatchType": "phase"},
                    request_payload={"case_id": 5401},
                    report_payload={"winner": "pro"},
                    callback_outcome=callback_outcome,
                    callback_status_reported="reported",
                    callback_status_failed_reported="failed_reported",
                    callback_status_failed_callback_failed="failed_callback_failed",
                    with_error_contract=_with_error_contract,
                    persist_dispatch_receipt=_persist_dispatch_receipt,
                    trace_register_failure=_trace_register_failure,
                    trace_register_success=lambda **kwargs: None,
                    workflow_mark_failed=_workflow_mark_failed,
                    workflow_mark_completed=lambda **kwargs: asyncio.sleep(0),
                    build_phase_workflow_reported_payload=lambda **kwargs: {"callbackStatus": kwargs["callback_status"]},
                    build_trace_report_summary=lambda **kwargs: {},
                    clear_idempotency=lambda key: calls.update({"cleared": key}),
                    set_idempotency_success=lambda **kwargs: None,
                    idempotency_ttl_secs=3600,
                    phase_judge_workflow_payload={"graph": "ok"},
                )
            )

        self.assertEqual(ctx.exception.status_code, 502)
        self.assertIn("phase_callback_failed", str(ctx.exception.detail))
        self.assertEqual(calls["receipt"]["status"], "callback_failed")
        self.assertEqual(calls["traceFailure"]["callback_status"], "failed_reported")
        self.assertEqual(calls["workflowFailed"]["error_code"], "phase_callback_retry_exhausted")
        self.assertEqual(calls["cleared"], "phase:5401")

    def test_build_phase_dispatch_callback_result_route_payload_should_return_response_for_reported(self) -> None:
        parsed = SimpleNamespace(
            case_id=5402,
            scope_id=1,
            session_id=5412,
            trace_id="trace-phase-5402",
            idempotency_key="phase:5402",
            rubric_version="v3",
            judge_policy_version="v3-default",
            topic_domain="tft",
            retrieval_profile="hybrid_v1",
            phase_no=4,
            message_start_id=21,
            message_end_id=22,
            message_count=2,
        )
        callback_outcome = SimpleNamespace(
            callback_status="reported",
            callback_attempts=1,
            callback_retries=0,
        )
        calls: dict[str, Any] = {}

        async def _persist_dispatch_receipt(**kwargs: Any) -> None:
            calls["receipt"] = dict(kwargs)

        def _trace_register_success(**kwargs: Any) -> None:
            calls["traceSuccess"] = dict(kwargs)

        async def _workflow_mark_completed(**kwargs: Any) -> None:
            calls["workflowCompleted"] = dict(kwargs)

        def _set_idempotency_success(**kwargs: Any) -> None:
            calls["idempotencySuccess"] = dict(kwargs)

        result = asyncio.run(
            build_phase_dispatch_callback_result_route_payload(
                parsed=parsed,
                response={"accepted": True, "dispatchType": "phase"},
                request_payload={"case_id": 5402},
                report_payload={"winner": "con"},
                callback_outcome=callback_outcome,
                callback_status_reported="reported",
                callback_status_failed_reported="failed_reported",
                callback_status_failed_callback_failed="failed_callback_failed",
                with_error_contract=lambda payload, **kwargs: dict(payload),
                persist_dispatch_receipt=_persist_dispatch_receipt,
                trace_register_failure=lambda **kwargs: None,
                trace_register_success=_trace_register_success,
                workflow_mark_failed=lambda **kwargs: asyncio.sleep(0),
                workflow_mark_completed=_workflow_mark_completed,
                build_phase_workflow_reported_payload=lambda **kwargs: {"callbackStatus": kwargs["callback_status"]},
                build_trace_report_summary=lambda **kwargs: {"dispatchType": kwargs.get("dispatch_type")},
                clear_idempotency=lambda key: None,
                set_idempotency_success=_set_idempotency_success,
                idempotency_ttl_secs=3600,
                phase_judge_workflow_payload={"graph": "ok"},
            )
        )

        self.assertTrue(result["accepted"])
        self.assertEqual(calls["receipt"]["status"], "reported")
        self.assertEqual(calls["traceSuccess"]["callback_status"], "reported")
        self.assertEqual(calls["workflowCompleted"]["event_payload"]["callbackStatus"], "reported")
        self.assertEqual(calls["idempotencySuccess"]["ttl_secs"], 3600)

    def test_build_final_dispatch_callback_result_route_payload_should_raise_502_for_failed_callback_failed(self) -> None:
        parsed = SimpleNamespace(
            case_id=5501,
            scope_id=1,
            session_id=5511,
            trace_id="trace-final-5501",
            idempotency_key="final:5501",
            rubric_version="v3",
            judge_policy_version="v3-default",
            topic_domain="tft",
            phase_start_no=1,
            phase_end_no=4,
        )
        callback_outcome = SimpleNamespace(
            callback_status="failed_callback_failed",
            report_error="report failed",
            failed_error="failed-callback-down",
            failed_payload={"errorCode": "final_callback_retry_exhausted"},
        )
        calls: dict[str, Any] = {}

        async def _persist_dispatch_receipt(**kwargs: Any) -> None:
            calls["receipt"] = dict(kwargs)

        def _trace_register_failure(**kwargs: Any) -> None:
            calls["traceFailure"] = dict(kwargs)

        async def _workflow_mark_failed(**kwargs: Any) -> None:
            calls["workflowFailed"] = dict(kwargs)

        with self.assertRaises(JudgeCommandRouteError) as ctx:
            asyncio.run(
                build_final_dispatch_callback_result_route_payload(
                    parsed=parsed,
                    response={"accepted": True, "dispatchType": "final"},
                    request_payload={"case_id": 5501},
                    report_payload={"winner": "draw"},
                    callback_outcome=callback_outcome,
                    callback_status_reported="reported",
                    callback_status_failed_reported="failed_reported",
                    callback_status_failed_callback_failed="failed_callback_failed",
                    with_error_contract=lambda payload, **kwargs: dict(payload),
                    persist_dispatch_receipt=_persist_dispatch_receipt,
                    trace_register_failure=_trace_register_failure,
                    trace_register_success=lambda **kwargs: None,
                    workflow_mark_failed=_workflow_mark_failed,
                    workflow_mark_review_required=lambda **kwargs: asyncio.sleep(0),
                    workflow_mark_completed=lambda **kwargs: asyncio.sleep(0),
                    build_final_workflow_reported_payload=lambda **kwargs: {"callbackStatus": kwargs["callback_status"]},
                    build_trace_report_summary=lambda **kwargs: {},
                    clear_idempotency=lambda key: calls.update({"cleared": key}),
                    set_idempotency_success=lambda **kwargs: None,
                    idempotency_ttl_secs=3600,
                    final_judge_workflow_payload={"graph": "ok"},
                )
            )

        self.assertEqual(ctx.exception.status_code, 502)
        self.assertIn("final_failed_callback_failed", str(ctx.exception.detail))
        self.assertEqual(calls["receipt"]["status"], "callback_failed")
        self.assertEqual(calls["traceFailure"]["callback_status"], "failed_callback_failed")
        self.assertEqual(calls["workflowFailed"]["error_code"], "final_failed_callback_failed")
        self.assertEqual(calls["cleared"], "final:5501")

    def test_build_final_dispatch_callback_result_route_payload_should_mark_review_required_on_reported(self) -> None:
        parsed = SimpleNamespace(
            case_id=5502,
            scope_id=1,
            session_id=5512,
            trace_id="trace-final-5502",
            idempotency_key="final:5502",
            rubric_version="v3",
            judge_policy_version="v3-default",
            topic_domain="tft",
            phase_start_no=1,
            phase_end_no=6,
        )
        callback_outcome = SimpleNamespace(
            callback_status="reported",
            callback_attempts=1,
            callback_retries=0,
        )
        calls: dict[str, Any] = {}

        async def _persist_dispatch_receipt(**kwargs: Any) -> None:
            calls["receipt"] = dict(kwargs)

        def _trace_register_success(**kwargs: Any) -> None:
            calls["traceSuccess"] = dict(kwargs)

        async def _workflow_mark_review_required(**kwargs: Any) -> None:
            calls["workflowReviewRequired"] = dict(kwargs)

        def _set_idempotency_success(**kwargs: Any) -> None:
            calls["idempotencySuccess"] = dict(kwargs)

        result = asyncio.run(
            build_final_dispatch_callback_result_route_payload(
                parsed=parsed,
                response={"accepted": True, "dispatchType": "final"},
                request_payload={"case_id": 5502},
                report_payload={"winner": "draw", "reviewRequired": True},
                callback_outcome=callback_outcome,
                callback_status_reported="reported",
                callback_status_failed_reported="failed_reported",
                callback_status_failed_callback_failed="failed_callback_failed",
                with_error_contract=lambda payload, **kwargs: dict(payload),
                persist_dispatch_receipt=_persist_dispatch_receipt,
                trace_register_failure=lambda **kwargs: None,
                trace_register_success=_trace_register_success,
                workflow_mark_failed=lambda **kwargs: asyncio.sleep(0),
                workflow_mark_review_required=_workflow_mark_review_required,
                workflow_mark_completed=lambda **kwargs: asyncio.sleep(0),
                build_final_workflow_reported_payload=lambda **kwargs: {
                    "callbackStatus": kwargs["callback_status"],
                    "reviewRequired": bool(kwargs["report_payload"].get("reviewRequired")),
                },
                build_trace_report_summary=lambda **kwargs: {"dispatchType": kwargs.get("dispatch_type")},
                clear_idempotency=lambda key: None,
                set_idempotency_success=_set_idempotency_success,
                idempotency_ttl_secs=3600,
                final_judge_workflow_payload={"graph": "ok"},
            )
        )

        self.assertTrue(result["accepted"])
        self.assertEqual(calls["receipt"]["status"], "reported")
        self.assertEqual(calls["traceSuccess"]["callback_status"], "reported")
        self.assertTrue(calls["workflowReviewRequired"]["event_payload"]["reviewRequired"])
        self.assertEqual(calls["idempotencySuccess"]["ttl_secs"], 3600)

    def test_build_final_contract_blocked_route_payload_should_raise_502_when_failed_callback_reported(
        self,
    ) -> None:
        parsed = SimpleNamespace(
            case_id=5601,
            scope_id=1,
            session_id=5611,
            trace_id="trace-final-5601",
            idempotency_key="final:5601",
            rubric_version="v3",
            judge_policy_version="v3-default",
            topic_domain="tft",
            phase_start_no=1,
            phase_end_no=5,
        )
        calls: dict[str, Any] = {}

        def _upsert_audit_alert(**kwargs: Any) -> Any:
            calls["alert"] = dict(kwargs)
            return SimpleNamespace(alert_id="alert-final-5601")

        async def _sync_audit_alert_to_facts(*, alert: Any) -> None:
            calls["syncedAlertId"] = alert.alert_id

        def _build_failed_callback_payload(**kwargs: Any) -> dict[str, Any]:
            calls["failedPayload"] = dict(kwargs)
            return dict(kwargs)

        async def _invoke_failed_callback_with_retry(*, case_id: int, payload: dict[str, Any]) -> tuple[int, int]:
            calls["failedInvoke"] = {"caseId": case_id, "payload": dict(payload)}
            return 1, 0

        def _with_error_contract(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            out = dict(payload)
            out["errorCode"] = kwargs.get("error_code")
            return out

        async def _persist_dispatch_receipt(**kwargs: Any) -> None:
            calls["receipt"] = dict(kwargs)

        def _trace_register_failure(**kwargs: Any) -> None:
            calls["traceFailure"] = dict(kwargs)

        async def _workflow_mark_failed(**kwargs: Any) -> None:
            calls["workflowFailed"] = dict(kwargs)

        with self.assertRaises(JudgeCommandRouteError) as ctx:
            asyncio.run(
                build_final_contract_blocked_route_payload(
                    parsed=parsed,
                    response={"accepted": True, "dispatchType": "final"},
                    request_payload={"case_id": 5601},
                    report_payload={"degradationLevel": 2},
                    contract_missing_fields=["debateSummary", "sideAnalysis", "verdictReason"],
                    upsert_audit_alert=_upsert_audit_alert,
                    sync_audit_alert_to_facts=_sync_audit_alert_to_facts,
                    build_failed_callback_payload=_build_failed_callback_payload,
                    invoke_failed_callback_with_retry=_invoke_failed_callback_with_retry,
                    with_error_contract=_with_error_contract,
                    persist_dispatch_receipt=_persist_dispatch_receipt,
                    trace_register_failure=_trace_register_failure,
                    workflow_mark_failed=_workflow_mark_failed,
                    clear_idempotency=lambda key: calls.update({"cleared": key}),
                )
            )

        self.assertEqual(ctx.exception.status_code, 502)
        self.assertIn("final_contract_blocked", str(ctx.exception.detail))
        self.assertEqual(calls["syncedAlertId"], "alert-final-5601")
        self.assertEqual(calls["receipt"]["status"], "callback_failed")
        self.assertEqual(calls["traceFailure"]["callback_status"], "blocked_failed_reported")
        self.assertEqual(calls["workflowFailed"]["error_code"], "final_contract_blocked")
        self.assertEqual(calls["cleared"], "final:5601")

    def test_build_final_contract_blocked_route_payload_should_raise_502_when_failed_callback_fails(
        self,
    ) -> None:
        parsed = SimpleNamespace(
            case_id=5602,
            scope_id=1,
            session_id=5612,
            trace_id="trace-final-5602",
            idempotency_key="final:5602",
            rubric_version="v3",
            judge_policy_version="v3-default",
            topic_domain="tft",
            phase_start_no=2,
            phase_end_no=6,
        )
        calls: dict[str, Any] = {}

        async def _raise_failed_callback(*, case_id: int, payload: dict[str, Any]) -> tuple[int, int]:
            raise RuntimeError("final-failed-callback-down")

        async def _persist_dispatch_receipt(**kwargs: Any) -> None:
            calls["receipt"] = dict(kwargs)

        def _trace_register_failure(**kwargs: Any) -> None:
            calls["traceFailure"] = dict(kwargs)

        async def _workflow_mark_failed(**kwargs: Any) -> None:
            calls["workflowFailed"] = dict(kwargs)

        with self.assertRaises(JudgeCommandRouteError) as ctx:
            asyncio.run(
                build_final_contract_blocked_route_payload(
                    parsed=parsed,
                    response={"accepted": True, "dispatchType": "final"},
                    request_payload={"case_id": 5602},
                    report_payload={"degradationLevel": 1},
                    contract_missing_fields=["debateSummary"],
                    upsert_audit_alert=lambda **kwargs: SimpleNamespace(alert_id="alert-final-5602"),
                    sync_audit_alert_to_facts=lambda **kwargs: asyncio.sleep(0),
                    build_failed_callback_payload=lambda **kwargs: dict(kwargs),
                    invoke_failed_callback_with_retry=_raise_failed_callback,
                    with_error_contract=lambda payload, **kwargs: dict(payload),
                    persist_dispatch_receipt=_persist_dispatch_receipt,
                    trace_register_failure=_trace_register_failure,
                    workflow_mark_failed=_workflow_mark_failed,
                    clear_idempotency=lambda key: calls.update({"cleared": key}),
                )
            )

        self.assertEqual(ctx.exception.status_code, 502)
        self.assertIn("final_failed_callback_failed", str(ctx.exception.detail))
        self.assertEqual(calls["receipt"]["status"], "callback_failed")
        self.assertEqual(calls["traceFailure"]["callback_status"], "failed_callback_failed")
        self.assertEqual(calls["workflowFailed"]["error_code"], "final_failed_callback_failed")
        self.assertEqual(calls["cleared"], "final:5602")

    def test_build_final_dispatch_report_materialization_route_payload_should_build_materialized_payload(
        self,
    ) -> None:
        parsed = SimpleNamespace(
            case_id=5701,
            scope_id=1,
            session_id=5711,
            trace_id="trace-final-5701",
            phase_start_no=1,
            phase_end_no=7,
        )
        policy_profile = SimpleNamespace(
            fairness_thresholds={"drawMargin": 0.8},
            version="v3-default",
        )
        prompt_profile = SimpleNamespace(version="promptset-v3-default")
        tool_profile = SimpleNamespace(version="toolset-v3-default")
        calls: dict[str, Any] = {}

        async def _list_dispatch_receipts(**kwargs: Any) -> list[Any]:
            calls["phaseReceiptsQuery"] = dict(kwargs)
            return [{"jobId": 5701, "status": "reported"}]

        def _build_final_report_payload(**kwargs: Any) -> dict[str, Any]:
            calls["buildFinalReport"] = dict(kwargs)
            return {"winner": "pro", "degradationLevel": 0}

        def _resolve_panel_runtime_profiles(*, profile: Any) -> dict[str, dict[str, Any]]:
            calls["panelRuntimeProfile"] = {"version": profile.version}
            return {"default": {"enabled": True}}

        async def _attach_judge_agent_runtime_trace(**kwargs: Any) -> None:
            calls["attachRuntimeTrace"] = dict(kwargs)

        def _attach_policy_trace_snapshot(**kwargs: Any) -> None:
            calls["attachPolicyTrace"] = dict(kwargs)

        def _attach_report_attestation(**kwargs: Any) -> None:
            calls["attachAttestation"] = dict(kwargs)

        async def _upsert_claim_ledger_record(**kwargs: Any) -> None:
            calls["upsertClaimLedger"] = dict(kwargs)

        def _build_final_judge_workflow_payload(**kwargs: Any) -> dict[str, Any]:
            calls["buildWorkflowPayload"] = dict(kwargs)
            return {"edgeCount": 8}

        def _validate_final_report_payload_contract(report_payload: dict[str, Any]) -> list[str]:
            calls["validateContract"] = dict(report_payload)
            return ["debateSummary"]

        materialized = asyncio.run(
            build_final_dispatch_report_materialization_route_payload(
                parsed=parsed,
                request_payload={"case_id": 5701},
                policy_profile=policy_profile,
                prompt_profile=prompt_profile,
                tool_profile=tool_profile,
                list_dispatch_receipts=_list_dispatch_receipts,
                build_final_report_payload=_build_final_report_payload,
                resolve_panel_runtime_profiles=_resolve_panel_runtime_profiles,
                attach_judge_agent_runtime_trace=_attach_judge_agent_runtime_trace,
                attach_policy_trace_snapshot=_attach_policy_trace_snapshot,
                attach_report_attestation=_attach_report_attestation,
                upsert_claim_ledger_record=_upsert_claim_ledger_record,
                build_final_judge_workflow_payload=_build_final_judge_workflow_payload,
                validate_final_report_payload_contract=_validate_final_report_payload_contract,
            )
        )

        self.assertEqual(calls["phaseReceiptsQuery"]["dispatch_type"], "phase")
        self.assertEqual(calls["phaseReceiptsQuery"]["session_id"], 5711)
        self.assertEqual(calls["buildFinalReport"]["fairness_thresholds"]["drawMargin"], 0.8)
        self.assertEqual(calls["attachRuntimeTrace"]["dispatch_type"], "final")
        self.assertEqual(calls["attachPolicyTrace"]["profile"].version, "v3-default")
        self.assertEqual(calls["attachAttestation"]["dispatch_type"], "final")
        self.assertEqual(calls["upsertClaimLedger"]["dispatch_type"], "final")
        self.assertEqual(calls["buildWorkflowPayload"]["request"].case_id, 5701)
        self.assertEqual(materialized["reportPayload"]["winner"], "pro")
        self.assertEqual(materialized["finalJudgeWorkflowPayload"]["edgeCount"], 8)
        self.assertEqual(materialized["contractMissingFields"], ["debateSummary"])

    def test_build_phase_dispatch_report_materialization_route_payload_should_build_materialized_payload(
        self,
    ) -> None:
        parsed = SimpleNamespace(
            case_id=5801,
            scope_id=1,
            session_id=5811,
            trace_id="trace-phase-5801",
            phase_no=6,
        )
        policy_profile = SimpleNamespace(version="v3-default")
        prompt_profile = SimpleNamespace(version="promptset-v3-default")
        tool_profile = SimpleNamespace(version="toolset-v3-default")
        calls: dict[str, Any] = {}

        async def _build_phase_report_payload(*, request: Any) -> dict[str, Any]:
            calls["buildPhaseReport"] = {"caseId": request.case_id, "phaseNo": request.phase_no}
            return {"winner": "con", "degradationLevel": 1}

        async def _attach_judge_agent_runtime_trace(**kwargs: Any) -> None:
            calls["attachRuntimeTrace"] = dict(kwargs)

        def _attach_policy_trace_snapshot(**kwargs: Any) -> None:
            calls["attachPolicyTrace"] = dict(kwargs)

        def _attach_report_attestation(**kwargs: Any) -> None:
            calls["attachAttestation"] = dict(kwargs)

        async def _upsert_claim_ledger_record(**kwargs: Any) -> None:
            calls["upsertClaimLedger"] = dict(kwargs)

        def _build_phase_judge_workflow_payload(**kwargs: Any) -> dict[str, Any]:
            calls["buildWorkflowPayload"] = dict(kwargs)
            return {"edgeCount": 5}

        materialized = asyncio.run(
            build_phase_dispatch_report_materialization_route_payload(
                parsed=parsed,
                request_payload={"case_id": 5801},
                policy_profile=policy_profile,
                prompt_profile=prompt_profile,
                tool_profile=tool_profile,
                build_phase_report_payload=_build_phase_report_payload,
                attach_judge_agent_runtime_trace=_attach_judge_agent_runtime_trace,
                attach_policy_trace_snapshot=_attach_policy_trace_snapshot,
                attach_report_attestation=_attach_report_attestation,
                upsert_claim_ledger_record=_upsert_claim_ledger_record,
                build_phase_judge_workflow_payload=_build_phase_judge_workflow_payload,
            )
        )

        self.assertEqual(calls["buildPhaseReport"]["caseId"], 5801)
        self.assertEqual(calls["attachRuntimeTrace"]["dispatch_type"], "phase")
        self.assertEqual(calls["attachRuntimeTrace"]["phase_no"], 6)
        self.assertEqual(calls["attachPolicyTrace"]["profile"].version, "v3-default")
        self.assertEqual(calls["attachAttestation"]["dispatch_type"], "phase")
        self.assertEqual(calls["upsertClaimLedger"]["dispatch_type"], "phase")
        self.assertEqual(calls["buildWorkflowPayload"]["request"].case_id, 5801)
        self.assertEqual(materialized["reportPayload"]["winner"], "con")
        self.assertEqual(materialized["phaseJudgeWorkflowPayload"]["edgeCount"], 5)


if __name__ == "__main__":
    unittest.main()
