from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from typing import Any

from app.applications.judge_command_routes import (
    JudgeCommandRouteError,
    build_blindization_rejection_route_payload,
    build_case_create_route_payload,
    build_final_contract_blocked_route_payload,
    build_final_dispatch_callback_result_route_payload,
    build_final_dispatch_preflight_route_payload,
    build_final_dispatch_report_materialization_route_payload,
    build_phase_dispatch_callback_result_route_payload,
    build_phase_dispatch_preflight_route_payload,
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


if __name__ == "__main__":
    unittest.main()
