from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

AGENT_KIND_JUDGE = "judge"
AGENT_KIND_NPC_COACH = "npc_coach"
AGENT_KIND_ROOM_QA = "room_qa"
AgentKind = Literal["judge", "npc_coach", "room_qa"]


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
