from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.gateways import (
    GatewayKnowledgePolicy,
    GatewayLlmPolicy,
    GatewayPolicyBinding,
    KnowledgeGatewayPort,
    LlmGatewayPort,
)
from app.infra.gateways import DefaultKnowledgeGateway, DefaultLlmGateway
from app.rag_profiles import DEFAULT_RETRIEVAL_PROFILE, resolve_retrieval_profile
from app.runtime_policy import normalize_provider

from .policy_registry import build_policy_registry_runtime


@dataclass(frozen=True)
class GatewayRuntime:
    llm: LlmGatewayPort
    knowledge: KnowledgeGatewayPort
    llm_policy: GatewayLlmPolicy | None = None
    knowledge_policy: GatewayKnowledgePolicy | None = None
    policy_binding: GatewayPolicyBinding | None = None

    def build_trace_snapshot(
        self,
        *,
        trace_id: str | None = None,
        requested_policy_version: str | None = None,
        requested_retrieval_profile: str | None = None,
        use_case: str = "judge",
    ) -> dict[str, Any]:
        return {
            "version": "gateway-core-v1",
            "traceId": str(trace_id or "").strip() or None,
            "useCase": use_case,
            "requestedPolicyVersion": str(requested_policy_version or "").strip() or None,
            "requestedRetrievalProfile": str(requested_retrieval_profile or "").strip() or None,
            "llm": self.llm_policy.to_payload() if self.llm_policy is not None else {},
            "knowledge": (
                self.knowledge_policy.to_payload()
                if self.knowledge_policy is not None
                else {}
            ),
            "policyBinding": (
                self.policy_binding.to_payload()
                if self.policy_binding is not None
                else {}
            ),
            "noLangChainLangGraph": True,
        }


def build_gateway_runtime(*, settings: object) -> GatewayRuntime:
    provider = normalize_provider(str(getattr(settings, "provider", "openai") or "openai"))
    retrieval_profile, _profile_reason = resolve_retrieval_profile(
        str(getattr(settings, "gateway_retrieval_profile", "") or DEFAULT_RETRIEVAL_PROFILE)
    )
    policy_runtime = build_policy_registry_runtime(settings=settings)
    profile = policy_runtime.get_profile(policy_runtime.default_version)
    llm_policy = GatewayLlmPolicy(
        provider=provider,
        model=str(getattr(settings, "openai_model", "") or ""),
        timeout_secs=float(getattr(settings, "openai_timeout_secs", 0.0) or 0.0),
        max_retries=int(getattr(settings, "openai_max_retries", 0) or 0),
        temperature=float(getattr(settings, "openai_temperature", 0.0) or 0.0),
        fallback_policy=(
            "mock_fallback"
            if bool(getattr(settings, "openai_fallback_to_mock", False))
            else "fail_closed"
        ),
    )
    knowledge_policy = GatewayKnowledgePolicy(
        retrieval_profile=retrieval_profile.name,
        backend=str(getattr(settings, "rag_backend", "") or ""),
        source_whitelist=tuple(getattr(settings, "rag_source_whitelist", ()) or ()),
        hybrid_enabled=bool(getattr(settings, "rag_hybrid_enabled", False)),
        rerank_enabled=bool(getattr(settings, "rag_rerank_enabled", False)),
        rrf_k=int(retrieval_profile.hybrid_rrf_k),
    )
    policy_binding = (
        GatewayPolicyBinding(
            policy_version=profile.version,
            rubric_version=profile.rubric_version,
            prompt_registry_version=profile.prompt_registry_version,
            tool_registry_version=profile.tool_registry_version,
            fairness_thresholds=dict(profile.fairness_thresholds),
            draw_policy=dict(profile.draw_policy),
            review_escalation_policy=dict(profile.review_escalation_policy),
            official_verdict_policy=True,
        )
        if profile is not None
        else None
    )
    return GatewayRuntime(
        llm=DefaultLlmGateway(policy=llm_policy),
        knowledge=DefaultKnowledgeGateway(policy=knowledge_policy),
        llm_policy=llm_policy,
        knowledge_policy=knowledge_policy,
        policy_binding=policy_binding,
    )
