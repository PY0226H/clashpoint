from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass(frozen=True)
class AssistantAgentRouteError(Exception):
    status_code: int
    detail: Any


_OFFICIAL_VERDICT_CHAIN_KEYS = frozenset(
    {
        "winner",
        "proscore",
        "conscore",
        "dimensionscores",
        "verdictevidencerefs",
        "auditalerts",
        "errorcodes",
        "degradationlevel",
        "debatesummary",
        "sideanalysis",
        "verdictreason",
        "finalrationale",
        "verdictledger",
        "fairnesssummary",
        "fairnessgate",
        "trustattestation",
        "needsdrawvote",
        "reviewrequired",
        "dispatchtype",
        "judgepolicyversion",
        "rubricversion",
        "ruleversion",
        "officialverdictauthority",
        "writesverdictledger",
        "writesjudgetrace",
    }
)


def _normalize_advisory_output_key(key: str) -> str:
    return "".join(char for char in key.lower() if char.isalnum())


def _is_official_verdict_chain_key(key: str) -> bool:
    return _normalize_advisory_output_key(key) in _OFFICIAL_VERDICT_CHAIN_KEYS


def sanitize_assistant_advisory_output(payload: Any) -> Any:
    if isinstance(payload, dict):
        sanitized: dict[Any, Any] = {}
        for key, value in payload.items():
            if isinstance(key, str) and _is_official_verdict_chain_key(key):
                continue
            sanitized[key] = sanitize_assistant_advisory_output(value)
        return sanitized
    if isinstance(payload, list):
        return [sanitize_assistant_advisory_output(item) for item in payload]
    return payload


def normalize_assistant_session_id(session_id: int) -> int:
    normalized_session_id = max(0, int(session_id))
    if normalized_session_id <= 0:
        raise ValueError("invalid_session_id")
    return normalized_session_id


async def build_npc_coach_advice_route_payload(
    *,
    session_id: int,
    payload: Any,
    agent_kind_npc_coach: str,
    build_shared_room_context: Callable[..., Awaitable[dict[str, Any]]],
    execute_agent: Callable[..., Awaitable[Any]],
    build_execution_request: Callable[..., Any],
    build_assistant_agent_response: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    try:
        normalized_session_id = normalize_assistant_session_id(session_id)
    except ValueError as err:
        raise AssistantAgentRouteError(status_code=422, detail="invalid_session_id") from err

    shared_context = await build_shared_room_context(
        session_id=normalized_session_id,
        case_id=payload.case_id,
    )
    scope_id = max(1, int(shared_context.get("scopeId") or 1))
    execution_result = await execute_agent(
        build_execution_request(
            kind=agent_kind_npc_coach,
            input_payload={
                "sessionId": normalized_session_id,
                "caseId": shared_context.get("caseId"),
                "query": payload.query,
                "side": payload.side,
                "sharedContext": shared_context,
            },
            trace_id=payload.trace_id,
            session_id=normalized_session_id,
            scope_id=scope_id,
            metadata={
                "app": "npc_coach",
                "entrypoint": "npc_coach_advice",
            },
        )
    )
    return build_assistant_agent_response(
        agent_kind=agent_kind_npc_coach,
        session_id=normalized_session_id,
        shared_context=shared_context,
        execution_result=execution_result,
    )


async def build_room_qa_answer_route_payload(
    *,
    session_id: int,
    payload: Any,
    agent_kind_room_qa: str,
    build_shared_room_context: Callable[..., Awaitable[dict[str, Any]]],
    execute_agent: Callable[..., Awaitable[Any]],
    build_execution_request: Callable[..., Any],
    build_assistant_agent_response: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    try:
        normalized_session_id = normalize_assistant_session_id(session_id)
    except ValueError as err:
        raise AssistantAgentRouteError(status_code=422, detail="invalid_session_id") from err

    shared_context = await build_shared_room_context(
        session_id=normalized_session_id,
        case_id=payload.case_id,
    )
    scope_id = max(1, int(shared_context.get("scopeId") or 1))
    execution_result = await execute_agent(
        build_execution_request(
            kind=agent_kind_room_qa,
            input_payload={
                "sessionId": normalized_session_id,
                "caseId": shared_context.get("caseId"),
                "question": payload.question,
                "sharedContext": shared_context,
            },
            trace_id=payload.trace_id,
            session_id=normalized_session_id,
            scope_id=scope_id,
            metadata={
                "app": "room_qa",
                "entrypoint": "room_qa_answer",
            },
        )
    )
    return build_assistant_agent_response(
        agent_kind=agent_kind_room_qa,
        session_id=normalized_session_id,
        shared_context=shared_context,
        execution_result=execution_result,
    )
