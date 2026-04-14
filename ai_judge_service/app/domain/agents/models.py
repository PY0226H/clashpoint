from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

AGENT_KIND_JUDGE = "judge"
AGENT_KIND_NPC_COACH = "npc_coach"
AGENT_KIND_ROOM_QA = "room_qa"
AgentKind = Literal["judge", "npc_coach", "room_qa"]

ROLE_CLERK = "clerk"
ROLE_RECORDER = "recorder"
ROLE_CLAIM_GRAPH = "claim_graph"
ROLE_EVIDENCE = "evidence"
ROLE_JUDGE_PANEL = "judge_panel"
ROLE_FAIRNESS_SENTINEL = "fairness_sentinel"
ROLE_CHIEF_ARBITER = "chief_arbiter"
ROLE_OPINION_WRITER = "opinion_writer"
CourtroomRole = Literal[
    "clerk",
    "recorder",
    "claim_graph",
    "evidence",
    "judge_panel",
    "fairness_sentinel",
    "chief_arbiter",
    "opinion_writer",
]
JUDGE_COURTROOM_ROLE_ORDER: tuple[CourtroomRole, ...] = (
    ROLE_CLERK,
    ROLE_RECORDER,
    ROLE_CLAIM_GRAPH,
    ROLE_EVIDENCE,
    ROLE_JUDGE_PANEL,
    ROLE_FAIRNESS_SENTINEL,
    ROLE_CHIEF_ARBITER,
    ROLE_OPINION_WRITER,
)


@dataclass(frozen=True)
class AgentProfile:
    kind: AgentKind
    display_name: str
    description: str
    enabled: bool
    owner: str
    timeout_ms: int
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgentExecutionRequest:
    kind: AgentKind
    input_payload: dict[str, Any]
    trace_id: str | None = None
    session_id: int | None = None
    scope_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentExecutionResult:
    status: Literal["ok", "not_ready", "error"]
    output: dict[str, Any]
    error_code: str | None = None
    error_message: str | None = None
