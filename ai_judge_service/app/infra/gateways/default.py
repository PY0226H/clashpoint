from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.gateways import KnowledgeGatewayPort, LlmGatewayPort
from app.openai_judge_client import call_openai_json
from app.runtime_rag import retrieve_runtime_contexts_with_meta


@dataclass(frozen=True)
class DefaultLlmGateway(LlmGatewayPort):
    async def call_json(
        self,
        *,
        cfg: Any,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        return await call_openai_json(
            cfg=cfg,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )


@dataclass(frozen=True)
class DefaultKnowledgeGateway(KnowledgeGatewayPort):
    def retrieve_with_meta(
        self,
        *,
        request: Any,
        settings: Any,
    ) -> Any:
        return retrieve_runtime_contexts_with_meta(
            request=request,
            settings=settings,
        )
