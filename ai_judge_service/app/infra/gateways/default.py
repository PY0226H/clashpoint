from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.gateways import (
    GatewayKnowledgePolicy,
    GatewayLlmPolicy,
    KnowledgeGatewayPort,
    LlmGatewayPort,
)
from app.openai_judge_client import OPENAI_META_KEY, call_openai_json
from app.runtime_rag import retrieve_runtime_contexts_with_meta


@dataclass(frozen=True)
class DefaultLlmGateway(LlmGatewayPort):
    policy: GatewayLlmPolicy | None = None

    async def call_json(
        self,
        *,
        cfg: Any,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        payload = await call_openai_json(
            cfg=cfg,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        if self.policy is None:
            return payload
        meta = payload.get(OPENAI_META_KEY) if isinstance(payload.get(OPENAI_META_KEY), dict) else {}
        meta["gateway"] = {
            "kind": "llm",
            "provider": self.policy.provider,
            "model": getattr(cfg, "model", self.policy.model),
            "structuredOutput": self.policy.structured_output,
            "usageAccounting": self.policy.usage_accounting,
            "traceTagging": self.policy.trace_tagging,
            "fallbackPolicy": self.policy.fallback_policy,
        }
        payload[OPENAI_META_KEY] = meta
        return payload


@dataclass(frozen=True)
class DefaultKnowledgeGateway(KnowledgeGatewayPort):
    policy: GatewayKnowledgePolicy | None = None

    def retrieve_with_meta(
        self,
        *,
        request: Any,
        settings: Any,
    ) -> Any:
        result = retrieve_runtime_contexts_with_meta(
            request=request,
            settings=settings,
        )
        if self.policy is None:
            return result
        diagnostics = getattr(result, "retrieval_diagnostics", None)
        if isinstance(diagnostics, dict):
            diagnostics["gateway"] = {
                "kind": "knowledge",
                "retrievalProfileDefault": self.policy.retrieval_profile,
                "retrievalProfileRequested": getattr(request, "retrieval_profile", None),
                "backend": self.policy.backend,
                "sourceWhitelist": list(self.policy.source_whitelist),
                "hybridEnabled": self.policy.hybrid_enabled,
                "rerankEnabled": self.policy.rerank_enabled,
                "conflictTagging": self.policy.conflict_tagging,
                "traceTagging": self.policy.trace_tagging,
            }
        return result
