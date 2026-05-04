from __future__ import annotations

import asyncio
import json

import httpx
from app.app_factory import create_app
from app.chat_client import NpcChatClient
from app.guard import candidate_from_raw_output
from app.models import NpcDecisionContext, NpcDecisionRun

from helpers import make_context, make_settings, make_trigger


class FakeRouter:
    def __init__(self) -> None:
        self.context: NpcDecisionContext | None = None

    async def decide(self, context: NpcDecisionContext) -> NpcDecisionRun:
        self.context = context
        settings = make_settings()
        return NpcDecisionRun(
            status="created",
            executorKind="llm_executor_v1",
            executorVersion="llm_executor_v1",
            fallbackUsed=False,
            candidate=candidate_from_raw_output(
                {
                    "actionType": "praise",
                    "publicText": "这个点很有张力。",
                    "targetMessageId": 1001,
                },
                context=context,
                settings=settings,
                executor_kind="llm_executor_v1",
                executor_version="llm_executor_v1",
            ),
        )


def test_healthz_reports_executor_and_fallback_state() -> None:
    async def scenario() -> None:
        settings = make_settings(api_key="", rule_fallback_enabled=True)
        app = create_app(settings=settings, router=FakeRouter())
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/healthz")

        assert response.status_code == 200
        assert response.json() == {
            "ok": True,
            "service": "npc_service_test",
            "executorPrimary": "llm_executor_v1",
            "llmEnabled": True,
            "llmConfigured": False,
            "ruleFallbackEnabled": True,
            "eventConsumerEnabled": False,
            "eventConsumerSource": "kafka",
            "eventWebhookEnabled": True,
        }

    asyncio.run(scenario())


def test_debate_message_event_route_can_be_disabled_for_non_local_consumer_path() -> None:
    async def scenario() -> None:
        app = create_app(settings=make_settings(event_webhook_enabled=False), router=FakeRouter())
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/internal/npc/events/debate-message-created",
                headers={"x-ai-internal-key": "test-internal-key"},
                json=make_trigger().model_dump(by_alias=True),
            )

        assert response.status_code == 404
        assert response.json()["detail"] == "event webhook disabled"

    asyncio.run(scenario())


def test_evaluate_decision_route_returns_router_run() -> None:
    async def scenario() -> None:
        router = FakeRouter()
        app = create_app(settings=make_settings(), router=router)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/internal/npc/decisions/evaluate",
                json=make_context().model_dump(by_alias=True),
            )

        payload = response.json()
        assert response.status_code == 200
        assert router.context is not None
        assert router.context.session_id == 77
        assert payload["status"] == "created"
        assert payload["executorKind"] == "llm_executor_v1"
        assert payload["candidate"]["actionType"] == "praise"
        assert payload["candidate"]["publicText"] == "这个点很有张力。"

    asyncio.run(scenario())


def test_debate_message_event_route_requires_internal_key_and_processes_trigger() -> None:
    async def scenario() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                return httpx.Response(200, json=make_context().model_dump(by_alias=True))
            payload = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "accepted": True,
                    "actionId": 9002,
                    "actionUid": payload["actionUid"],
                    "status": "created",
                    "reasonCode": None,
                },
            )

        settings = make_settings()
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as chat_http_client:
            app = create_app(
                settings=settings,
                router=FakeRouter(),
                chat_client=NpcChatClient(settings=settings, client=chat_http_client),
            )
            app_transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=app_transport,
                base_url="http://test",
            ) as client:
                unauthorized = await client.post(
                    "/api/internal/npc/events/debate-message-created",
                    json=make_trigger().model_dump(by_alias=True),
                )
                authorized = await client.post(
                    "/api/internal/npc/events/debate-message-created",
                    headers={"x-ai-internal-key": "test-internal-key"},
                    json=make_trigger().model_dump(by_alias=True),
                )

        assert unauthorized.status_code == 401
        assert authorized.status_code == 200
        payload = authorized.json()
        assert payload["status"] == "submitted"
        assert payload["submitResult"]["actionId"] == 9002
        assert payload["decisionRun"]["candidate"]["actionType"] == "praise"

    asyncio.run(scenario())
