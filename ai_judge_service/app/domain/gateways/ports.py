from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class GatewayLlmPolicy:
    provider: str
    model: str
    timeout_secs: float
    max_retries: int
    temperature: float
    structured_output: bool = True
    usage_accounting: bool = True
    trace_tagging: bool = True
    fallback_policy: str = "fail_closed"

    def to_payload(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "timeoutSecs": float(self.timeout_secs),
            "maxRetries": int(self.max_retries),
            "temperature": float(self.temperature),
            "structuredOutput": bool(self.structured_output),
            "usageAccounting": bool(self.usage_accounting),
            "traceTagging": bool(self.trace_tagging),
            "fallbackPolicy": self.fallback_policy,
        }


@dataclass(frozen=True)
class GatewayKnowledgePolicy:
    retrieval_profile: str
    backend: str
    source_whitelist: tuple[str, ...] = ()
    hybrid_enabled: bool = True
    rerank_enabled: bool = True
    rrf_k: int = 60
    conflict_tagging: bool = True
    trace_tagging: bool = True

    def to_payload(self) -> dict[str, Any]:
        return {
            "retrievalProfile": self.retrieval_profile,
            "backend": self.backend,
            "sourceWhitelist": list(self.source_whitelist),
            "hybridEnabled": bool(self.hybrid_enabled),
            "rerankEnabled": bool(self.rerank_enabled),
            "rrfK": int(self.rrf_k),
            "conflictTagging": bool(self.conflict_tagging),
            "traceTagging": bool(self.trace_tagging),
        }


@dataclass(frozen=True)
class GatewayPolicyBinding:
    policy_version: str
    rubric_version: str
    prompt_registry_version: str
    tool_registry_version: str
    fairness_thresholds: dict[str, Any] = field(default_factory=dict)
    draw_policy: dict[str, Any] = field(default_factory=dict)
    review_escalation_policy: dict[str, Any] = field(default_factory=dict)
    official_verdict_policy: bool = True

    def to_payload(self) -> dict[str, Any]:
        return {
            "policyVersion": self.policy_version,
            "rubricVersion": self.rubric_version,
            "promptRegistryVersion": self.prompt_registry_version,
            "toolRegistryVersion": self.tool_registry_version,
            "fairnessThresholds": dict(self.fairness_thresholds),
            "drawPolicy": dict(self.draw_policy),
            "reviewEscalationPolicy": dict(self.review_escalation_policy),
            "officialVerdictPolicy": bool(self.official_verdict_policy),
            "advisoryOnlyUseCases": ["npc_coach", "room_qa"],
        }


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
