from __future__ import annotations

import asyncio
import unittest
from dataclasses import dataclass
from typing import Any

from app.applications.assistant_agent_routes import (
    AssistantAgentRouteError,
    build_npc_coach_advice_route_payload,
    build_room_qa_answer_route_payload,
    normalize_assistant_session_id,
    sanitize_assistant_advisory_output,
)


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
            return {"scopeId": 9, "caseId": 3001}

        def _build_execution_request(**kwargs: Any) -> dict[str, Any]:
            request_records.append(dict(kwargs))
            return dict(kwargs)

        async def _execute_agent(request: dict[str, Any]) -> dict[str, Any]:
            return {"request": request, "advice": "先回应对方证据缺口"}

        def _build_assistant_agent_response(
            *,
            agent_kind: str,
            session_id: int,
            shared_context: dict[str, Any],
            execution_result: dict[str, Any],
        ) -> dict[str, Any]:
            return {
                "agentKind": agent_kind,
                "sessionId": session_id,
                "sharedContext": shared_context,
                "result": execution_result,
            }

        route_payload = asyncio.run(
            build_npc_coach_advice_route_payload(
                session_id=2001,
                payload=payload,
                agent_kind_npc_coach="npc_coach",
                build_shared_room_context=_build_shared_room_context,
                execute_agent=_execute_agent,
                build_execution_request=_build_execution_request,
                build_assistant_agent_response=_build_assistant_agent_response,
            )
        )

        self.assertEqual(route_payload["agentKind"], "npc_coach")
        self.assertEqual(route_payload["sessionId"], 2001)
        self.assertEqual(route_payload["sharedContext"]["scopeId"], 9)
        self.assertEqual(route_payload["result"]["advice"], "先回应对方证据缺口")
        self.assertEqual(len(request_records), 1)
        execution_input = request_records[0]["input_payload"]
        self.assertEqual(execution_input["query"], payload.query)
        self.assertEqual(execution_input["side"], payload.side)
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
                    execute_agent=_execute_agent,
                    build_execution_request=lambda **kwargs: kwargs,
                    build_assistant_agent_response=lambda **kwargs: kwargs,
                )
            )

        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail, "invalid_session_id")

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
