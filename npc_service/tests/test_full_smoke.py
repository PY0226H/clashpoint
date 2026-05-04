from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from app.app_factory import create_app
from app.chat_client import NpcChatClient
from app.executors import LlmExecutorV1, NpcExecutorRouter, RuleExecutorV1, create_default_router
from app.models import NpcDecisionContext

from helpers import make_context, make_settings, make_trigger


class FakeProvider:
    def __init__(self, output: dict[str, Any]) -> None:
        self.output = output

    async def generate_action(self, context: NpcDecisionContext) -> dict[str, Any]:
        return self.output


def test_full_webhook_smoke_uses_rule_fallback_when_llm_is_disabled() -> None:
    async def scenario() -> None:
        observed: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                observed["context_url"] = str(request.url)
                return httpx.Response(200, json=make_context().model_dump(by_alias=True))
            payload = json.loads(request.content.decode("utf-8"))
            observed["candidate_payload"] = payload
            return httpx.Response(
                200,
                json={
                    "accepted": True,
                    "actionId": 9101,
                    "actionUid": payload["actionUid"],
                    "status": "created",
                    "reasonCode": None,
                },
            )

        settings = make_settings(api_key="", llm_enabled=False, event_submit_max_attempts=1)
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as chat_http_client:
            app = create_app(
                settings=settings,
                router=create_default_router(settings),
                chat_client=NpcChatClient(settings=settings, client=chat_http_client),
            )
            app_transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=app_transport,
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/internal/npc/events/debate-message-created",
                    headers={"x-ai-internal-key": "test-internal-key"},
                    json=make_trigger().model_dump(by_alias=True),
                )

        payload = response.json()
        candidate = observed["candidate_payload"]
        assert response.status_code == 200
        assert payload["status"] == "submitted"
        assert payload["decisionRun"]["status"] == "fallback"
        assert payload["decisionRun"]["fallbackReason"] == "llm_disabled"
        assert candidate["executorKind"] == "rule_executor_v1"
        assert candidate["actionType"] == "praise"
        assert candidate["targetMessageId"] == 1001

    asyncio.run(scenario())


def test_full_webhook_smoke_sanitizes_forbidden_llm_output_before_callback() -> None:
    async def scenario() -> None:
        observed: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                return httpx.Response(200, json=make_context().model_dump(by_alias=True))
            payload = json.loads(request.content.decode("utf-8"))
            observed["candidate_payload"] = payload
            return httpx.Response(
                200,
                json={
                    "accepted": True,
                    "actionId": 9102,
                    "actionUid": payload["actionUid"],
                    "status": "created",
                    "reasonCode": None,
                },
            )

        settings = make_settings(api_key="configured-key", event_submit_max_attempts=1)
        router = NpcExecutorRouter(
            settings=settings,
            llm_executor=LlmExecutorV1(
                settings=settings,
                provider=FakeProvider(
                    {
                        "actionType": "speak",
                        "publicText": "我来给出正式裁决。",
                        "winner": "pro",
                    }
                ),
            ),
            rule_executor=RuleExecutorV1(settings=settings),
        )
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as chat_http_client:
            app = create_app(
                settings=settings,
                router=router,
                chat_client=NpcChatClient(settings=settings, client=chat_http_client),
            )
            app_transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=app_transport,
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/internal/npc/events/debate-message-created",
                    headers={"x-ai-internal-key": "test-internal-key"},
                    json=make_trigger().model_dump(by_alias=True),
                )

        payload = response.json()
        candidate = observed["candidate_payload"]
        assert response.status_code == 200
        assert payload["status"] == "submitted"
        assert payload["decisionRun"]["fallbackReason"] == "official_verdict_field_forbidden"
        assert candidate["executorKind"] == "rule_executor_v1"
        assert "winner" not in candidate
        assert "score" not in candidate
        assert "officialVerdict" not in candidate

    asyncio.run(scenario())
