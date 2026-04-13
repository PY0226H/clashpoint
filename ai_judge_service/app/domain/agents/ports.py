from __future__ import annotations

from typing import Protocol

from .models import AgentExecutionRequest, AgentExecutionResult, AgentKind, AgentProfile


class AgentExecutorPort(Protocol):
    async def execute(self, request: AgentExecutionRequest) -> AgentExecutionResult:
        """Execute one agent request within the runtime boundary."""


class AgentRegistryPort(Protocol):
    def list_profiles(self) -> list[AgentProfile]:
        """List registered agent profiles."""

    def get_profile(self, kind: AgentKind) -> AgentProfile | None:
        """Fetch profile by agent kind."""

    def resolve_executor(self, kind: AgentKind) -> AgentExecutorPort | None:
        """Resolve executor by agent kind."""
