from __future__ import annotations

import asyncio
import unittest
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from app.applications.assistant_advisory_contract import (
    ASSISTANT_ADVISORY_CONTRACT_VERSION,
    ASSISTANT_ADVISORY_TOP_LEVEL_KEYS,
)
from app.applications.assistant_agent_routes import (
    AssistantAgentRouteError,
    build_assistant_advisory_context,
    build_assistant_agent_response,
    build_assistant_gateway_trace_snapshot,
    build_npc_coach_advice_route_payload,
    build_room_qa_answer_route_payload,
    normalize_assistant_session_id,
    sanitize_assistant_advisory_output,
)
from app.models import NpcCoachAdviceRequest, RoomQaAnswerRequest
from pydantic import ValidationError


@dataclass
class _DummyNpcPayload:
    case_id: int
    query: str
    side: str
    trace_id: str


@dataclass
class _DummyRoomQaPayload:
    case_id: int
    question: str
    trace_id: str


class AssistantAgentRoutesTests(unittest.TestCase):
    def test_normalize_assistant_session_id_should_validate_positive_values(self) -> None:
        self.assertEqual(normalize_assistant_session_id(1001), 1001)
        with self.assertRaises(ValueError) as ctx:
            normalize_assistant_session_id(0)
        self.assertEqual(str(ctx.exception), "invalid_session_id")

    def test_build_assistant_advisory_context_should_redact_official_context_fields(
        self,
    ) -> None:
        def _build_gateway_trace_snapshot(**kwargs: Any) -> dict[str, Any]:
            return {
                "traceId": kwargs["trace_id"],
                "useCase": kwargs["use_case"],
                "requestedPolicyVersion": kwargs["requested_policy_version"],
                "requestedRetrievalProfile": kwargs["requested_retrieval_profile"],
                "policyBinding": {
                    "policyVersion": "v3-default",
                    "officialVerdictPolicy": True,
                },
            }

        payload = build_assistant_advisory_context(
            agent_kind="room_qa",
            trace_id="trace-room-qa-1001",
            shared_context={
                "source": "shared_room_context_v1",
                "sessionId": 1001,
                "scopeId": 7,
                "caseId": 3001,
                "latestDispatchType": "final",
                "retrievalProfile": "hybrid_v1",
                "finalReceiptCount": 1,
                "winnerHint": "pro",
                "debateSummary": "official-chain-field",
                "verdictReason": "official-chain-field",
            },
            build_gateway_trace_snapshot=_build_gateway_trace_snapshot,
        )

        self.assertTrue(payload["advisoryOnly"])
        self.assertEqual(payload["roomContextSnapshot"]["caseId"], 3001)
        self.assertNotIn("winnerHint", payload["roomContextSnapshot"])
        self.assertNotIn("debateSummary", payload["roomContextSnapshot"])
        self.assertNotIn("verdictReason", payload["roomContextSnapshot"])
        self.assertEqual(payload["stageSummary"]["stage"], "final_context_available")
        self.assertTrue(payload["stageSummary"]["officialVerdictFieldsRedacted"])
        self.assertEqual(
            payload["knowledgeGateway"]["policyBinding"]["policyVersion"],
            "room_qa_advisory_policy_v1",
        )
        self.assertEqual(
            payload["knowledgeGateway"]["policyBinding"]["baseJudgePolicyVersion"],
            "v3-default",
        )
        self.assertFalse(
            payload["knowledgeGateway"]["policyBinding"]["officialVerdictPolicy"]
        )
        self.assertIn("verdict_ledger", payload["readPolicy"]["forbiddenWriteTargets"])
        self.assertFalse(payload["readPolicy"]["officialJudgeFeedbackAllowed"])

    def test_build_assistant_gateway_trace_snapshot_should_force_advisory_policy(
        self,
    ) -> None:
        payload = build_assistant_gateway_trace_snapshot(
            agent_kind="npc_coach",
            trace_id="trace-npc-1001",
            room_context_snapshot={"retrievalProfile": "hybrid_v1"},
            build_gateway_trace_snapshot=lambda **kwargs: {
                "traceId": kwargs["trace_id"],
                "useCase": "judge",
                "policyBinding": {
                    "policyVersion": "v3-default",
                    "officialVerdictPolicy": True,
                },
            },
        )

        self.assertTrue(payload["advisoryOnly"])
        self.assertEqual(payload["useCase"], "npc_coach")
        self.assertEqual(
            payload["policyBinding"]["policyVersion"],
            "npc_coach_advisory_policy_v1",
        )
        self.assertFalse(payload["policyBinding"]["officialVerdictPolicy"])

    def test_build_npc_coach_advice_route_payload_should_build_response(self) -> None:
        payload = _DummyNpcPayload(
            case_id=3001,
            query="如何反驳对方核心论点？",
            side="pro",
            trace_id="trace-npc-3001",
        )
        request_records: list[dict[str, Any]] = []

        async def _build_shared_room_context(*, session_id: int, case_id: int) -> dict[str, Any]:
            self.assertEqual(session_id, 2001)
            self.assertEqual(case_id, 3001)
            return {
                "scopeId": 9,
                "sessionId": session_id,
                "caseId": 3001,
                "latestDispatchType": "phase",
                "retrievalProfile": "hybrid_v1",
                "winnerHint": "pro",
                "verdictReason": "official-chain-field",
            }

        def _build_gateway_trace_snapshot(**kwargs: Any) -> dict[str, Any]:
            return {
                "useCase": kwargs["use_case"],
                "requestedPolicyVersion": kwargs["requested_policy_version"],
                "policyBinding": {
                    "policyVersion": "v3-default",
                    "officialVerdictPolicy": True,
                },
            }

        def _build_execution_request(**kwargs: Any) -> dict[str, Any]:
            request_records.append(dict(kwargs))
            return dict(kwargs)

        async def _execute_agent(request: dict[str, Any]) -> dict[str, Any]:
            return {"request": request, "advice": "先回应对方证据缺口"}

        def _build_assistant_agent_response(
            *,
            agent_kind: str,
            session_id: int,
            advisory_context: dict[str, Any],
            execution_result: dict[str, Any],
        ) -> dict[str, Any]:
            return {
                "agentKind": agent_kind,
                "sessionId": session_id,
                "sharedContext": advisory_context["roomContextSnapshot"],
                "advisoryContext": advisory_context,
                "result": execution_result,
            }

        route_payload = asyncio.run(
            build_npc_coach_advice_route_payload(
                session_id=2001,
                payload=payload,
                agent_kind_npc_coach="npc_coach",
                build_shared_room_context=_build_shared_room_context,
                build_gateway_trace_snapshot=_build_gateway_trace_snapshot,
                execute_agent=_execute_agent,
                build_execution_request=_build_execution_request,
                build_assistant_agent_response=_build_assistant_agent_response,
            )
        )

        self.assertEqual(route_payload["agentKind"], "npc_coach")
        self.assertEqual(route_payload["sessionId"], 2001)
        self.assertEqual(route_payload["sharedContext"]["scopeId"], 9)
        self.assertNotIn("winnerHint", route_payload["sharedContext"])
        self.assertNotIn("verdictReason", route_payload["sharedContext"])
        self.assertTrue(route_payload["advisoryContext"]["advisoryOnly"])
        self.assertFalse(
            route_payload["advisoryContext"]["knowledgeGateway"]["policyBinding"][
                "officialVerdictPolicy"
            ]
        )
        self.assertEqual(
            route_payload["advisoryContext"]["knowledgeGateway"]["policyBinding"][
                "policyVersion"
            ],
            "npc_coach_advisory_policy_v1",
        )
        self.assertEqual(route_payload["result"]["advice"], "先回应对方证据缺口")
        self.assertEqual(len(request_records), 1)
        execution_input = request_records[0]["input_payload"]
        self.assertEqual(execution_input["query"], payload.query)
        self.assertEqual(execution_input["side"], payload.side)
        self.assertIn("advisoryContext", execution_input)
        self.assertNotIn("sharedContext", execution_input)
        self.assertFalse(request_records[0]["metadata"]["officialVerdictAuthority"])
        self.assertTrue(request_records[0]["metadata"]["advisoryOnly"])
        self.assertEqual(
            request_records[0]["metadata"]["policyVersion"],
            "npc_coach_advisory_policy_v1",
        )
        self.assertEqual(request_records[0]["scope_id"], 9)

    def test_build_room_qa_answer_route_payload_should_reject_invalid_session_id(self) -> None:
        payload = _DummyRoomQaPayload(
            case_id=3002,
            question="现在哪一方更占优？",
            trace_id="trace-room-qa-3002",
        )

        async def _build_shared_room_context(*, session_id: int, case_id: int) -> dict[str, Any]:
            del session_id, case_id
            return {}

        async def _execute_agent(request: Any) -> dict[str, Any]:
            del request
            return {}

        with self.assertRaises(AssistantAgentRouteError) as ctx:
            asyncio.run(
                build_room_qa_answer_route_payload(
                    session_id=0,
                    payload=payload,
                    agent_kind_room_qa="room_qa",
                    build_shared_room_context=_build_shared_room_context,
                    build_gateway_trace_snapshot=lambda **_kwargs: {},
                    execute_agent=_execute_agent,
                    build_execution_request=lambda **kwargs: kwargs,
                    build_assistant_agent_response=lambda **kwargs: kwargs,
                )
            )

        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail, "invalid_session_id")

    def test_build_assistant_agent_response_should_freeze_contract_shape(self) -> None:
        response = build_assistant_agent_response(
            agent_kind="room_qa",
            session_id=2002,
            advisory_context={
                "advisoryOnly": True,
                "roomContextSnapshot": {
                    "sessionId": 2002,
                    "caseId": 3002,
                    "officialVerdictFieldsRedacted": True,
                },
                "stageSummary": {"officialVerdictFieldsRedacted": True},
                "knowledgeGateway": {},
                "readPolicy": {},
            },
            execution_result=SimpleNamespace(
                status="not_ready",
                output={
                    "accepted": False,
                    "kind": "room_qa",
                    "reason": "room_qa runtime shell is reserved",
                },
                error_code="agent_not_enabled",
                error_message="room_qa runtime shell is reserved",
            ),
        )

        self.assertEqual(set(response.keys()), set(ASSISTANT_ADVISORY_TOP_LEVEL_KEYS))
        self.assertEqual(response["version"], ASSISTANT_ADVISORY_CONTRACT_VERSION)
        self.assertEqual(response["status"], "not_ready")
        self.assertEqual(response["errorCode"], "agent_not_enabled")
        self.assertFalse(response["accepted"])
        self.assertFalse(response["cacheProfile"]["cacheable"])
        self.assertEqual(response["cacheProfile"]["ttlSeconds"], 0)
        self.assertEqual(response["capabilityBoundary"]["mode"], "advisory_only")
        self.assertFalse(response["capabilityBoundary"]["officialVerdictAuthority"])
        self.assertFalse(response["capabilityBoundary"]["writesVerdictLedger"])
        self.assertFalse(response["capabilityBoundary"]["writesJudgeTrace"])
        self.assertFalse(
            response["capabilityBoundary"]["canTriggerOfficialJudgeRoles"]
        )

    def test_build_assistant_agent_response_should_fail_closed_on_forbidden_output(
        self,
    ) -> None:
        with self.assertRaises(AssistantAgentRouteError) as ctx:
            build_assistant_agent_response(
                agent_kind="npc_coach",
                session_id=2003,
                advisory_context={
                    "advisoryOnly": True,
                    "roomContextSnapshot": {
                        "sessionId": 2003,
                        "caseId": 3003,
                        "officialVerdictFieldsRedacted": True,
                    },
                    "stageSummary": {"officialVerdictFieldsRedacted": True},
                    "knowledgeGateway": {},
                    "readPolicy": {},
                },
                execution_result=SimpleNamespace(
                    status="ok",
                    output={
                        "accepted": True,
                        "advice": "先补证据。",
                        "winner": "pro",
                    },
                    error_code=None,
                    error_message=None,
                ),
            )

        self.assertEqual(ctx.exception.status_code, 500)
        self.assertEqual(
            ctx.exception.detail,
            "assistant_advisory_contract_violation",
        )

    def test_assistant_request_models_should_reject_boundary_payloads(self) -> None:
        with self.assertRaises(ValidationError):
            NpcCoachAdviceRequest(trace_id="trace-npc", query="")
        with self.assertRaises(ValidationError):
            NpcCoachAdviceRequest(trace_id="trace-npc", query="x" * 2001)
        with self.assertRaises(ValidationError):
            NpcCoachAdviceRequest(
                trace_id="trace-npc",
                query="如何补强论点？",
                extra="blocked",
            )
        with self.assertRaises(ValidationError):
            RoomQaAnswerRequest(trace_id="trace-room", question="")
        with self.assertRaises(ValidationError):
            RoomQaAnswerRequest(trace_id="trace-room", question="x" * 2001)
        with self.assertRaises(ValidationError):
            RoomQaAnswerRequest(
                trace_id="trace-room",
                question="现在进展如何？",
                extra="blocked",
            )

    def test_sanitize_assistant_advisory_output_should_strip_official_verdict_fields(self) -> None:
        payload = {
            "accepted": True,
            "advice": "先补齐证据链，再针对反驳漏洞推进。",
            "winner": "pro",
            "verdictReason": "official-chain-field",
            "nested": {
                "needsDrawVote": True,
                "summary": "保留字段",
                "trust_attestation": {
                    "hash": "abc",
                },
            },
            "items": [
                {
                    "dimensionScores": {"logic": 9},
                    "note": "这条应保留",
                },
                {
                    "final-rationale": "legacy-chain-field",
                    "hint": "这条应保留",
                },
            ],
        }

        sanitized = sanitize_assistant_advisory_output(payload)

        self.assertTrue(bool(sanitized["accepted"]))
        self.assertEqual(
            sanitized["advice"],
            "先补齐证据链，再针对反驳漏洞推进。",
        )
        self.assertNotIn("winner", sanitized)
        self.assertNotIn("verdictReason", sanitized)
        self.assertNotIn("needsDrawVote", sanitized["nested"])
        self.assertNotIn("trust_attestation", sanitized["nested"])
        self.assertEqual(sanitized["nested"]["summary"], "保留字段")
        self.assertNotIn("dimensionScores", sanitized["items"][0])
        self.assertEqual(sanitized["items"][0]["note"], "这条应保留")
        self.assertNotIn("final-rationale", sanitized["items"][1])
        self.assertEqual(sanitized["items"][1]["hint"], "这条应保留")


if __name__ == "__main__":
    unittest.main()
