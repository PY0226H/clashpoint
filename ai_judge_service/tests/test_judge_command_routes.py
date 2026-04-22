from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from typing import Any

from app.applications.judge_command_routes import (
    JudgeCommandRouteError,
    build_blindization_rejection_route_payload,
    build_case_create_route_payload,
    build_final_dispatch_preflight_route_payload,
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


if __name__ == "__main__":
    unittest.main()
