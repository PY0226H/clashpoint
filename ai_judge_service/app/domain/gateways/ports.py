from __future__ import annotations

from typing import Any, Protocol


class LlmGatewayPort(Protocol):
    async def call_json(
        self,
        *,
        cfg: Any,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]: ...


class KnowledgeGatewayPort(Protocol):
    def retrieve_with_meta(
        self,
        *,
        request: Any,
        settings: Any,
    ) -> Any: ...
