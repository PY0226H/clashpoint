from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Header

from ..domain.agents import (
    AGENT_KIND_NPC_COACH,
    AGENT_KIND_ROOM_QA,
    AgentExecutionRequest,
)
from ..models import NpcCoachAdviceRequest, RoomQaAnswerRequest
from .assistant_agent_routes import (
    build_assistant_agent_response as build_assistant_agent_response_v3,
)
from .assistant_agent_routes import (
    build_npc_coach_advice_route_payload as build_npc_coach_advice_route_payload_v3,
)
from .assistant_agent_routes import (
    build_room_qa_answer_route_payload as build_room_qa_answer_route_payload_v3,
)

AsyncPayloadFn = Callable[..., Awaitable[dict[str, Any]]]
AssistantRouteGuardFn = Callable[
    [Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]
]
RequireInternalKeyFn = Callable[[Any, str | None], None]


@dataclass(frozen=True)
class AssistantRouteHandles:
    request_npc_coach_advice: AsyncPayloadFn
    request_room_qa_answer: AsyncPayloadFn


@dataclass(frozen=True)
class AssistantRouteDependencies:
    runtime: Any
    require_internal_key_fn: RequireInternalKeyFn
    run_assistant_agent_route_guard: AssistantRouteGuardFn
    build_shared_room_context: Callable[..., Awaitable[dict[str, Any]]]
    execute_agent: Callable[..., Awaitable[Any]]


def register_assistant_routes(
    *,
    app: FastAPI,
    deps: AssistantRouteDependencies,
) -> AssistantRouteHandles:
    runtime = deps.runtime

    @app.post("/internal/judge/apps/npc-coach/sessions/{session_id}/advice")
    async def request_npc_coach_advice(
        session_id: int,
        payload: NpcCoachAdviceRequest,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.run_assistant_agent_route_guard(
            build_npc_coach_advice_route_payload_v3(
                session_id=session_id,
                payload=payload,
                agent_kind_npc_coach=AGENT_KIND_NPC_COACH,
                build_shared_room_context=deps.build_shared_room_context,
                execute_agent=deps.execute_agent,
                build_execution_request=AgentExecutionRequest,
                build_assistant_agent_response=build_assistant_agent_response_v3,
            )
        )

    @app.post("/internal/judge/apps/room-qa/sessions/{session_id}/answer")
    async def request_room_qa_answer(
        session_id: int,
        payload: RoomQaAnswerRequest,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.run_assistant_agent_route_guard(
            build_room_qa_answer_route_payload_v3(
                session_id=session_id,
                payload=payload,
                agent_kind_room_qa=AGENT_KIND_ROOM_QA,
                build_shared_room_context=deps.build_shared_room_context,
                execute_agent=deps.execute_agent,
                build_execution_request=AgentExecutionRequest,
                build_assistant_agent_response=build_assistant_agent_response_v3,
            )
        )

    return AssistantRouteHandles(
        request_npc_coach_advice=request_npc_coach_advice,
        request_room_qa_answer=request_room_qa_answer,
    )
