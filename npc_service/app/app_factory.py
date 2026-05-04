from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any, Protocol

from fastapi import FastAPI, Header, HTTPException

from .chat_client import NpcChatClient
from .event_consumer import run_event_consumer_loop, stop_background_task
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
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.event_consumer.enabled:
            app.state.event_consumer_task = asyncio.create_task(
                run_event_consumer_loop(
                    settings=settings.event_consumer,
                    processor=app.state.event_processor,
                )
            )
        else:
            app.state.event_consumer_task = None
        try:
            yield
        finally:
            await stop_background_task(getattr(app.state, "event_consumer_task", None))

    app = FastAPI(title="EchoIsle NPC Service", version="0.1.0", lifespan=lifespan)
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
            "eventConsumerEnabled": settings.event_consumer.enabled,
            "eventConsumerSource": settings.event_consumer.source,
            "eventWebhookEnabled": settings.event_consumer.webhook_enabled,
        }

    @app.post("/api/internal/npc/decisions/evaluate", response_model=NpcDecisionRun)
    async def evaluate_decision(context: NpcDecisionContext) -> NpcDecisionRun:
        return await router.decide(context)

    @app.post("/api/internal/npc/events/debate-message-created")
    async def handle_debate_message_created(
        trigger: DebateMessageCreatedTrigger,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> Any:
        if not settings.event_consumer.webhook_enabled:
            raise HTTPException(status_code=404, detail="event webhook disabled")
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
