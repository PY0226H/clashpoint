from __future__ import annotations

from dataclasses import dataclass

from app.domain.gateways import KnowledgeGatewayPort, LlmGatewayPort
from app.infra.gateways import DefaultKnowledgeGateway, DefaultLlmGateway


@dataclass(frozen=True)
class GatewayRuntime:
    llm: LlmGatewayPort
    knowledge: KnowledgeGatewayPort


def build_gateway_runtime(*, settings: object) -> GatewayRuntime:
    _ = settings
    return GatewayRuntime(
        llm=DefaultLlmGateway(),
        knowledge=DefaultKnowledgeGateway(),
    )
