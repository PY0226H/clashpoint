from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from ..domain.agents import ROLE_CHIEF_ARBITER, ROLE_FAIRNESS_SENTINEL


@dataclass(frozen=True)
class AssistantAgentRouteError(Exception):
    status_code: int
    detail: Any


ASSISTANT_ADVISORY_ALLOWED_CONTEXT_SOURCES: tuple[str, ...] = (
    "room_context_snapshot",
    "stage_summary",
    "knowledge_gateway",
)
ASSISTANT_ADVISORY_FORBIDDEN_WRITE_TARGETS: tuple[str, ...] = (
    "verdict_ledger",
    "judge_trace",
    "fairness_report",
    "official_review_queue",
)
ASSISTANT_ADVISORY_FORBIDDEN_OFFICIAL_ROLES: tuple[str, ...] = (
    ROLE_FAIRNESS_SENTINEL,
    ROLE_CHIEF_ARBITER,
)
ASSISTANT_ADVISORY_POLICY_VERSION_BY_KIND: dict[str, str] = {
    "npc_coach": "npc_coach_advisory_policy_v1",
    "room_qa": "room_qa_advisory_policy_v1",
}

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
        "cantriggerofficialjudgeroles",
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


def _optional_context_token(value: Any) -> str | None:
    token = str(value or "").strip()
    return token or None


def _optional_context_int(value: Any) -> int | None:
    try:
        if isinstance(value, bool):
            return None
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def build_assistant_room_context_snapshot(
    *,
    shared_context: dict[str, Any],
) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for key in (
        "source",
        "sessionId",
        "scopeId",
        "caseId",
        "latestDispatchType",
        "workflowStatus",
        "ruleVersion",
        "rubricVersion",
        "judgePolicyVersion",
        "topicDomain",
        "retrievalProfile",
        "phaseReceiptCount",
        "finalReceiptCount",
        "updatedAt",
    ):
        value = shared_context.get(key)
        if value is not None:
            snapshot[key] = value
    snapshot["officialVerdictFieldsRedacted"] = True
    return snapshot


def build_assistant_stage_summary(
    *,
    room_context_snapshot: dict[str, Any],
) -> dict[str, Any]:
    phase_receipt_count = _optional_context_int(
        room_context_snapshot.get("phaseReceiptCount")
    ) or 0
    final_receipt_count = _optional_context_int(
        room_context_snapshot.get("finalReceiptCount")
    ) or 0
    latest_dispatch_type = _optional_context_token(
        room_context_snapshot.get("latestDispatchType")
    )
    workflow_status = _optional_context_token(room_context_snapshot.get("workflowStatus"))
    if final_receipt_count > 0 or latest_dispatch_type == "final":
        stage = "final_context_available"
    elif phase_receipt_count > 0 or latest_dispatch_type == "phase":
        stage = "phase_context_available"
    else:
        stage = "room_context_only"
    return {
        "stage": stage,
        "workflowStatus": workflow_status,
        "latestDispatchType": latest_dispatch_type,
        "hasPhaseReceipt": phase_receipt_count > 0,
        "hasFinalReceipt": final_receipt_count > 0,
        "officialVerdictFieldsRedacted": True,
    }


def build_assistant_gateway_trace_snapshot(
    *,
    agent_kind: str,
    trace_id: str | None,
    room_context_snapshot: dict[str, Any],
    build_gateway_trace_snapshot: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    advisory_policy_version = (
        ASSISTANT_ADVISORY_POLICY_VERSION_BY_KIND.get(agent_kind)
        or "assistant_advisory_policy_v1"
    )
    raw_snapshot = build_gateway_trace_snapshot(
        trace_id=trace_id,
        requested_policy_version=advisory_policy_version,
        requested_retrieval_profile=room_context_snapshot.get("retrievalProfile"),
        use_case=agent_kind,
    )
    snapshot = dict(raw_snapshot) if isinstance(raw_snapshot, dict) else {}
    policy_binding = (
        dict(snapshot.get("policyBinding"))
        if isinstance(snapshot.get("policyBinding"), dict)
        else {}
    )
    base_policy_version = _optional_context_token(policy_binding.get("policyVersion"))
    policy_binding.update(
        {
            "policyVersion": advisory_policy_version,
            "baseJudgePolicyVersion": base_policy_version,
            "officialVerdictPolicy": False,
            "advisoryOnly": True,
            "policyIsolation": "assistant_advisory_policy",
            "useCase": agent_kind,
        }
    )
    snapshot["useCase"] = agent_kind
    snapshot["advisoryOnly"] = True
    snapshot["policyBinding"] = policy_binding
    return snapshot


def build_assistant_advisory_context(
    *,
    agent_kind: str,
    trace_id: str | None,
    shared_context: dict[str, Any],
    build_gateway_trace_snapshot: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    room_context_snapshot = build_assistant_room_context_snapshot(
        shared_context=shared_context,
    )
    stage_summary = build_assistant_stage_summary(
        room_context_snapshot=room_context_snapshot,
    )
    knowledge_gateway = build_assistant_gateway_trace_snapshot(
        agent_kind=agent_kind,
        trace_id=trace_id,
        room_context_snapshot=room_context_snapshot,
        build_gateway_trace_snapshot=build_gateway_trace_snapshot,
    )
    return {
        "advisoryOnly": True,
        "roomContextSnapshot": room_context_snapshot,
        "stageSummary": stage_summary,
        "knowledgeGateway": knowledge_gateway,
        "readPolicy": {
            "allowedSources": list(ASSISTANT_ADVISORY_ALLOWED_CONTEXT_SOURCES),
            "forbiddenWriteTargets": list(ASSISTANT_ADVISORY_FORBIDDEN_WRITE_TARGETS),
            "forbiddenOfficialRoles": list(ASSISTANT_ADVISORY_FORBIDDEN_OFFICIAL_ROLES),
            "officialJudgeFeedbackAllowed": False,
        },
    }


def build_assistant_agent_response(
    *,
    agent_kind: str,
    session_id: int,
    advisory_context: dict[str, Any],
    execution_result: Any,
) -> dict[str, Any]:
    output = (
        sanitize_assistant_advisory_output(execution_result.output)
        if isinstance(execution_result.output, dict)
        else {}
    )
    capability_boundary = {
        "mode": "advisory_only",
        "advisoryOnly": True,
        "officialVerdictAuthority": False,
        "writesVerdictLedger": False,
        "writesJudgeTrace": False,
        "canTriggerOfficialJudgeRoles": False,
        "allowedContextSources": list(ASSISTANT_ADVISORY_ALLOWED_CONTEXT_SOURCES),
        "forbiddenWriteTargets": list(ASSISTANT_ADVISORY_FORBIDDEN_WRITE_TARGETS),
        "forbiddenOfficialRoles": list(ASSISTANT_ADVISORY_FORBIDDEN_OFFICIAL_ROLES),
    }
    shared_context = (
        advisory_context.get("roomContextSnapshot")
        if isinstance(advisory_context.get("roomContextSnapshot"), dict)
        else {}
    )
    return {
        "agentKind": agent_kind,
        "sessionId": session_id,
        "caseId": shared_context.get("caseId"),
        "advisoryOnly": True,
        "status": execution_result.status,
        "accepted": bool(output.get("accepted")),
        "errorCode": execution_result.error_code,
        "errorMessage": execution_result.error_message,
        "capabilityBoundary": capability_boundary,
        "sharedContext": shared_context,
        "advisoryContext": advisory_context,
        "output": output,
    }


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
    build_gateway_trace_snapshot: Callable[..., dict[str, Any]],
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
    advisory_context = build_assistant_advisory_context(
        agent_kind=agent_kind_npc_coach,
        trace_id=payload.trace_id,
        shared_context=shared_context,
        build_gateway_trace_snapshot=build_gateway_trace_snapshot,
    )
    scope_id = max(1, int(shared_context.get("scopeId") or 1))
    execution_result = await execute_agent(
        build_execution_request(
            kind=agent_kind_npc_coach,
            input_payload={
                "sessionId": normalized_session_id,
                "caseId": advisory_context.get("roomContextSnapshot", {}).get("caseId"),
                "query": payload.query,
                "side": payload.side,
                "advisoryContext": advisory_context,
            },
            trace_id=payload.trace_id,
            session_id=normalized_session_id,
            scope_id=scope_id,
            metadata={
                "app": "npc_coach",
                "entrypoint": "npc_coach_advice",
                "advisoryOnly": True,
                "officialVerdictAuthority": False,
                "policyVersion": advisory_context.get("knowledgeGateway", {})
                .get("policyBinding", {})
                .get("policyVersion"),
            },
        )
    )
    return build_assistant_agent_response(
        agent_kind=agent_kind_npc_coach,
        session_id=normalized_session_id,
        advisory_context=advisory_context,
        execution_result=execution_result,
    )


async def build_room_qa_answer_route_payload(
    *,
    session_id: int,
    payload: Any,
    agent_kind_room_qa: str,
    build_shared_room_context: Callable[..., Awaitable[dict[str, Any]]],
    build_gateway_trace_snapshot: Callable[..., dict[str, Any]],
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
    advisory_context = build_assistant_advisory_context(
        agent_kind=agent_kind_room_qa,
        trace_id=payload.trace_id,
        shared_context=shared_context,
        build_gateway_trace_snapshot=build_gateway_trace_snapshot,
    )
    scope_id = max(1, int(shared_context.get("scopeId") or 1))
    execution_result = await execute_agent(
        build_execution_request(
            kind=agent_kind_room_qa,
            input_payload={
                "sessionId": normalized_session_id,
                "caseId": advisory_context.get("roomContextSnapshot", {}).get("caseId"),
                "question": payload.question,
                "advisoryContext": advisory_context,
            },
            trace_id=payload.trace_id,
            session_id=normalized_session_id,
            scope_id=scope_id,
            metadata={
                "app": "room_qa",
                "entrypoint": "room_qa_answer",
                "advisoryOnly": True,
                "officialVerdictAuthority": False,
                "policyVersion": advisory_context.get("knowledgeGateway", {})
                .get("policyBinding", {})
                .get("policyVersion"),
            },
        )
    )
    return build_assistant_agent_response(
        agent_kind=agent_kind_room_qa,
        session_id=normalized_session_id,
        advisory_context=advisory_context,
        execution_result=execution_result,
    )
