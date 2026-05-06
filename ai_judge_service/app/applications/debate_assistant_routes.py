from __future__ import annotations

from typing import Any, Awaitable, Callable

from ..domain.agents import AgentExecutionRequest
from .assistant_agent_routes import AssistantAgentRouteError

DEBATE_ASSISTANT_AGENT_KIND = "debate_assistant"
DEBATE_ASSISTANT_CONTRACT_VERSION = "debate_assistant_contract_v1"
DEBATE_ASSISTANT_CONTEXT_VERSION = "assistant_room_transcript_context_v1"
DEBATE_ASSISTANT_NOT_READY = "debate_assistant_not_ready"
DEBATE_ASSISTANT_CONTRACT_VIOLATION = "debate_assistant_contract_violation"

_TOP_LEVEL_KEYS = {
    "version",
    "agentKind",
    "sessionId",
    "caseId",
    "advisoryOnly",
    "status",
    "statusReason",
    "accepted",
    "errorCode",
    "errorMessage",
    "capabilityBoundary",
    "sharedContext",
    "advisoryContext",
    "output",
    "cacheProfile",
}

_OUTPUT_KEYS = {
    "accepted",
    "intent",
    "answerSummary",
    "keyPoints",
    "suggestedActions",
    "contextCaveats",
    "boundaryNotice",
    "sourceUsePolicy",
}

_FORBIDDEN_KEYS = {
    "winner",
    "proscore",
    "conscore",
    "dimensionscores",
    "verdictreason",
    "verdictledger",
    "fairnessgate",
    "trustattestation",
    "judgetrace",
    "rawprompt",
    "rawtrace",
    "artifactref",
    "artifactrefs",
    "providerconfig",
    "secret",
    "secretref",
    "credential",
    "internalkey",
    "xaiinternalkey",
    "walletbalance",
    "membershiptier",
    "userentitlements",
    "phone",
    "phonenumber",
    "email",
    "officialverdictauthority",
    "writesverdictledger",
    "writesjudgetrace",
    "cantriggerofficialjudgeroles",
}


def _normalize_key(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch not in {"_", "-", ".", " "})


def _contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            _normalize_key(key) in _FORBIDDEN_KEYS or _contains_forbidden_key(nested)
            for key, nested in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_key(item) for item in value)
    return False


def _context_is_safe(context: dict[str, Any], session_id: int) -> bool:
    redaction = context.get("redaction")
    return (
        context.get("version") == DEBATE_ASSISTANT_CONTEXT_VERSION
        and int(context.get("sessionId") or 0) == int(session_id)
        and isinstance(context.get("topic"), dict)
        and isinstance(context.get("session"), dict)
        and isinstance(context.get("viewer"), dict)
        and isinstance(context.get("recentMessages"), list)
        and isinstance(context.get("messageWindow"), dict)
        and isinstance(redaction, dict)
        and redaction.get("publicOnly") is True
        and redaction.get("privateFieldsRedacted") is True
        and redaction.get("officialVerdictFieldsRedacted") is True
        and redaction.get("membershipSignalsRedacted") is True
        and not _contains_forbidden_key(context)
    )


def _capability_boundary() -> dict[str, Any]:
    return {
        "mode": "advisory_only",
        "advisoryOnly": True,
        "officialVerdictAuthority": False,
        "writesVerdictLedger": False,
        "writesJudgeTrace": False,
        "canTriggerOfficialJudgeRoles": False,
    }


def _cache_profile(session_id: int) -> dict[str, Any]:
    return {
        "cacheable": False,
        "ttlSeconds": 0,
        "cacheKey": f"debate-assistant:ai-service:session:{session_id}",
        "varyBy": ["authorization", "sessionId", "intent"],
    }


def _boundary_notice() -> str:
    return "私人辅助，不代表官方裁决；不会自动发送公开发言。"


def _default_output(*, intent: str | None, accepted: bool, reason: str) -> dict[str, Any]:
    return {
        "accepted": accepted,
        "intent": intent,
        "answerSummary": None,
        "keyPoints": [],
        "suggestedActions": [],
        "contextCaveats": [reason],
        "boundaryNotice": _boundary_notice(),
        "sourceUsePolicy": "仅基于当前房间公开内容和用户输入。",
    }


def validate_debate_assistant_public_output(output: dict[str, Any]) -> None:
    if set(output.keys()) != _OUTPUT_KEYS:
        raise AssistantAgentRouteError(
            status_code=500,
            detail=DEBATE_ASSISTANT_CONTRACT_VIOLATION,
        )
    if output.get("accepted") is not True:
        raise AssistantAgentRouteError(
            status_code=500,
            detail=DEBATE_ASSISTANT_CONTRACT_VIOLATION,
        )
    if not isinstance(output.get("intent"), str):
        raise AssistantAgentRouteError(
            status_code=500,
            detail=DEBATE_ASSISTANT_CONTRACT_VIOLATION,
        )
    for key in ("keyPoints", "suggestedActions", "contextCaveats"):
        if not isinstance(output.get(key), list) or not all(
            isinstance(item, str) for item in output[key]
        ):
            raise AssistantAgentRouteError(
                status_code=500,
                detail=DEBATE_ASSISTANT_CONTRACT_VIOLATION,
            )
    for key in ("answerSummary", "boundaryNotice", "sourceUsePolicy"):
        if not isinstance(output.get(key), str) or not output[key].strip():
            raise AssistantAgentRouteError(
                status_code=500,
                detail=DEBATE_ASSISTANT_CONTRACT_VIOLATION,
            )
    if _contains_forbidden_key(output):
        raise AssistantAgentRouteError(
            status_code=500,
            detail=DEBATE_ASSISTANT_CONTRACT_VIOLATION,
        )


def validate_debate_assistant_response_contract(payload: dict[str, Any]) -> None:
    if set(payload.keys()) != _TOP_LEVEL_KEYS:
        raise AssistantAgentRouteError(
            status_code=500,
            detail=DEBATE_ASSISTANT_CONTRACT_VIOLATION,
        )
    if payload.get("version") != DEBATE_ASSISTANT_CONTRACT_VERSION:
        raise AssistantAgentRouteError(
            status_code=500,
            detail=DEBATE_ASSISTANT_CONTRACT_VIOLATION,
        )
    if payload.get("agentKind") != DEBATE_ASSISTANT_AGENT_KIND:
        raise AssistantAgentRouteError(
            status_code=500,
            detail=DEBATE_ASSISTANT_CONTRACT_VIOLATION,
        )
    if payload.get("advisoryOnly") is not True:
        raise AssistantAgentRouteError(
            status_code=500,
            detail=DEBATE_ASSISTANT_CONTRACT_VIOLATION,
        )
    boundary = payload.get("capabilityBoundary")
    if not isinstance(boundary, dict) or boundary != _capability_boundary():
        raise AssistantAgentRouteError(
            status_code=500,
            detail=DEBATE_ASSISTANT_CONTRACT_VIOLATION,
        )
    shared_context = payload.get("sharedContext")
    if not isinstance(shared_context, dict) or not _context_is_safe(
        shared_context,
        int(payload.get("sessionId") or 0),
    ):
        raise AssistantAgentRouteError(
            status_code=500,
            detail=DEBATE_ASSISTANT_CONTRACT_VIOLATION,
        )
    advisory_context = payload.get("advisoryContext")
    if not isinstance(advisory_context, dict):
        raise AssistantAgentRouteError(
            status_code=500,
            detail=DEBATE_ASSISTANT_CONTRACT_VIOLATION,
        )
    if advisory_context.get("roomTranscriptContext") != shared_context:
        raise AssistantAgentRouteError(
            status_code=500,
            detail=DEBATE_ASSISTANT_CONTRACT_VIOLATION,
        )
    if _contains_forbidden_key(advisory_context) or _contains_forbidden_key(
        payload.get("output")
    ):
        raise AssistantAgentRouteError(
            status_code=500,
            detail=DEBATE_ASSISTANT_CONTRACT_VIOLATION,
        )


def build_debate_assistant_response(
    *,
    session_id: int,
    payload: Any,
    advisory_context: dict[str, Any],
    execution_result: Any,
) -> dict[str, Any]:
    status = str(execution_result.status or "error")
    raw_output = execution_result.output if isinstance(execution_result.output, dict) else {}
    if status == "ok":
        output = dict(raw_output)
        validate_debate_assistant_public_output(output)
        accepted = True
        error_code = None
        error_message = None
        status_reason = "debate_assistant_ready"
    elif status == "not_ready":
        reason = str(execution_result.error_message or "debate assistant is not ready")
        output = _default_output(intent=payload.intent, accepted=False, reason=reason)
        accepted = False
        error_code = execution_result.error_code or DEBATE_ASSISTANT_NOT_READY
        error_message = reason
        status_reason = error_code
    else:
        reason = str(execution_result.error_message or "debate assistant executor failed")
        output = _default_output(intent=payload.intent, accepted=False, reason=reason)
        accepted = False
        error_code = execution_result.error_code or "debate_assistant_executor_error"
        error_message = reason
        status_reason = error_code

    response = {
        "version": DEBATE_ASSISTANT_CONTRACT_VERSION,
        "agentKind": DEBATE_ASSISTANT_AGENT_KIND,
        "sessionId": session_id,
        "caseId": payload.case_id,
        "advisoryOnly": True,
        "status": status,
        "statusReason": status_reason,
        "accepted": accepted,
        "errorCode": error_code,
        "errorMessage": error_message,
        "capabilityBoundary": _capability_boundary(),
        "sharedContext": payload.room_transcript_context,
        "advisoryContext": advisory_context,
        "output": output,
        "cacheProfile": _cache_profile(session_id),
    }
    validate_debate_assistant_response_contract(response)
    return response


async def build_debate_assistant_query_route_payload(
    *,
    session_id: int,
    payload: Any,
    execute_agent: Callable[..., Awaitable[Any]],
    build_execution_request: Callable[..., Any] = AgentExecutionRequest,
    build_response: Callable[..., dict[str, Any]] = build_debate_assistant_response,
) -> dict[str, Any]:
    if session_id <= 0:
        raise AssistantAgentRouteError(status_code=422, detail="invalid_session_id")
    if not _context_is_safe(payload.room_transcript_context, session_id):
        raise AssistantAgentRouteError(
            status_code=422,
            detail="debate_assistant_context_invalid",
        )

    advisory_context = {
        "advisoryOnly": True,
        "roomTranscriptContext": payload.room_transcript_context,
        "readPolicy": {
            "allowedSources": [
                "room_transcript_context",
                "user_question",
                "user_draft",
            ],
            "forbiddenWriteTargets": [
                "public_room_message",
                "verdict_ledger",
                "judge_trace",
            ],
            "officialJudgeFeedbackAllowed": False,
        },
    }
    execution_result = await execute_agent(
        build_execution_request(
            kind=DEBATE_ASSISTANT_AGENT_KIND,
            input_payload={
                "sessionId": session_id,
                "caseId": payload.case_id,
                "intent": payload.intent,
                "question": payload.question,
                "draft": payload.draft,
                "side": payload.side,
                "roomTranscriptContext": payload.room_transcript_context,
                "advisoryContext": advisory_context,
            },
            trace_id=payload.trace_id,
            session_id=session_id,
            scope_id=session_id,
            metadata={
                "app": DEBATE_ASSISTANT_AGENT_KIND,
                "entrypoint": "debate_assistant_query",
                "advisoryOnly": True,
                "officialVerdictAuthority": False,
            },
        )
    )
    return build_response(
        session_id=session_id,
        payload=payload,
        advisory_context=advisory_context,
        execution_result=execution_result,
    )
