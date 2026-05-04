from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from fastapi import FastAPI, Header, HTTPException

from .chat_client import NpcChatClient
from .event_processor import NpcEventProcessor
from .executors import LLM_EXECUTOR_KIND, create_default_router
from .models import DebateMessageCreatedTrigger, NpcDecisionContext, NpcDecisionRun
from .settings import Settings, load_settings


class DecisionRouterProtocol(Protocol):
    async def decide(self, context: NpcDecisionContext) -> NpcDecisionRun:
        pass


def create_app(
    *,
    settings: Settings,
    router: DecisionRouterProtocol,
    chat_client: NpcChatClient | None = None,
) -> FastAPI:
    app = FastAPI(title="EchoIsle NPC Service", version="0.1.0")
    app.state.settings = settings
    app.state.router = router
    resolved_chat_client = chat_client or NpcChatClient(settings=settings)
    app.state.chat_client = resolved_chat_client
    app.state.event_processor = NpcEventProcessor(
        settings=settings,
        router=router,
        chat_client=resolved_chat_client,
    )

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {
            "ok": True,
            "service": settings.service_name,
            "executorPrimary": LLM_EXECUTOR_KIND,
            "llmEnabled": settings.llm_enabled,
            "llmConfigured": settings.openai.configured,
            "ruleFallbackEnabled": settings.rule_fallback_enabled,
        }

    @app.post("/api/internal/npc/decisions/evaluate", response_model=NpcDecisionRun)
    async def evaluate_decision(context: NpcDecisionContext) -> NpcDecisionRun:
        return await router.decide(context)

    @app.post("/api/internal/npc/events/debate-message-created")
    async def handle_debate_message_created(
        trigger: DebateMessageCreatedTrigger,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> Any:
        if x_ai_internal_key != settings.ai_internal_key:
            raise HTTPException(status_code=401, detail="invalid internal key")
        return await app.state.event_processor.handle_debate_message_created(trigger)

    return app


def create_default_app(*, load_settings_fn: Callable[[], Settings] = load_settings) -> FastAPI:
    settings = load_settings_fn()
    return create_app(
        settings=settings,
        router=create_default_router(settings),
        chat_client=NpcChatClient(settings=settings),
    )
