from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..domain.agents import (
    AGENT_KIND_JUDGE,
    AGENT_KIND_NPC_COACH,
    AGENT_KIND_ROOM_QA,
    AgentExecutionRequest,
    AgentExecutionResult,
    AgentExecutorPort,
    AgentKind,
    AgentProfile,
    AgentRegistryPort,
)


class _ReservedAgentExecutor(AgentExecutorPort):
    def __init__(self, *, kind: AgentKind, reason: str) -> None:
        self._kind = kind
        self._reason = reason

    async def execute(self, request: AgentExecutionRequest) -> AgentExecutionResult:
        return AgentExecutionResult(
            status="not_ready",
            output={
                "kind": self._kind,
                "accepted": False,
                "reason": self._reason,
                "traceId": request.trace_id,
            },
            error_code="agent_not_enabled",
            error_message=self._reason,
        )


class StaticAgentRegistry(AgentRegistryPort):
    def __init__(
        self,
        *,
        profiles: list[AgentProfile],
        executors: dict[AgentKind, AgentExecutorPort],
    ) -> None:
        self._profiles: dict[AgentKind, AgentProfile] = {row.kind: row for row in profiles}
        self._executors = dict(executors)

    def list_profiles(self) -> list[AgentProfile]:
        return [self._profiles[key] for key in sorted(self._profiles.keys())]

    def get_profile(self, kind: AgentKind) -> AgentProfile | None:
        return self._profiles.get(kind)

    def resolve_executor(self, kind: AgentKind) -> AgentExecutorPort | None:
        return self._executors.get(kind)


@dataclass(frozen=True)
class AgentRuntime:
    registry: AgentRegistryPort

    def list_profiles(self) -> list[AgentProfile]:
        return self.registry.list_profiles()

    def get_profile(self, kind: AgentKind) -> AgentProfile | None:
        return self.registry.get_profile(kind)

    async def execute(self, request: AgentExecutionRequest) -> AgentExecutionResult:
        executor = self.registry.resolve_executor(request.kind)
        if executor is None:
            return AgentExecutionResult(
                status="error",
                output={
                    "kind": request.kind,
                    "accepted": False,
                    "traceId": request.trace_id,
                },
                error_code="agent_not_registered",
                error_message=f"agent '{request.kind}' is not registered",
            )
        return await executor.execute(request)


def build_agent_runtime(*, settings: Any) -> AgentRuntime:
    timeout_ms = max(100, int(getattr(settings, "openai_timeout_secs", 30.0) * 1000))
    profiles = [
        AgentProfile(
            kind=AGENT_KIND_JUDGE,
            display_name="Judge Mainline",
            description="Official judge pipeline entry managed by v3 phase/final dispatch.",
            enabled=True,
            owner="ai_judge_service",
            timeout_ms=timeout_ms,
            tags=("official", "verdict"),
        ),
        AgentProfile(
            kind=AGENT_KIND_NPC_COACH,
            display_name="NPC Coach",
            description="Reserved shell for future in-room coaching guidance agent.",
            enabled=False,
            owner="ai_judge_service",
            timeout_ms=timeout_ms,
            tags=("shell", "future"),
        ),
        AgentProfile(
            kind=AGENT_KIND_ROOM_QA,
            display_name="Room QA",
            description="Reserved shell for future room-state QA agent.",
            enabled=False,
            owner="ai_judge_service",
            timeout_ms=timeout_ms,
            tags=("shell", "future"),
        ),
    ]
    executors: dict[AgentKind, AgentExecutorPort] = {
        AGENT_KIND_JUDGE: _ReservedAgentExecutor(
            kind=AGENT_KIND_JUDGE,
            reason="judge_mainline is served by /internal/judge/v3/{phase|final}/dispatch",
        ),
        AGENT_KIND_NPC_COACH: _ReservedAgentExecutor(
            kind=AGENT_KIND_NPC_COACH,
            reason="npc_coach runtime shell is reserved for future rollout",
        ),
        AGENT_KIND_ROOM_QA: _ReservedAgentExecutor(
            kind=AGENT_KIND_ROOM_QA,
            reason="room_qa runtime shell is reserved for future rollout",
        ),
    }
    return AgentRuntime(
        registry=StaticAgentRegistry(
            profiles=profiles,
            executors=executors,
        )
    )
