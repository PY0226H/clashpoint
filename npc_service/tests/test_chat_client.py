from __future__ import annotations

import asyncio
import json

import httpx
from app.chat_client import NpcChatClient
from app.guard import candidate_from_raw_output

from helpers import make_context, make_public_call, make_settings


def test_chat_client_fetches_public_decision_context() -> None:
    async def scenario() -> None:
        observed: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            observed["url"] = str(request.url)
            observed["internal_key"] = request.headers.get("x-ai-internal-key")
            return httpx.Response(
                200,
                json=make_context().model_dump(by_alias=True),
            )

        settings = make_settings()
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            context = await NpcChatClient(settings=settings, client=client).fetch_decision_context(
                session_id=77,
                trigger_message_id=1001,
                source_event_id="evt-1",
                limit=20,
            )

        assert (
            observed["url"]
            == "http://chat.test/api/internal/ai/debate/npc/sessions/77/context?triggerMessageId=1001&sourceEventId=evt-1&limit=20"
        )
        assert observed["internal_key"] == "test-internal-key"
        assert context.session_id == 77
        assert context.trigger_message is not None
        assert context.trigger_message.message_id == 1001

    asyncio.run(scenario())


def test_chat_client_fetches_public_call_context() -> None:
    async def scenario() -> None:
        observed: dict[str, object] = {}
        public_call = make_public_call()

        def handler(request: httpx.Request) -> httpx.Response:
            observed["url"] = str(request.url)
            return httpx.Response(
                200,
                json=make_context(
                    trigger_message=None,
                    public_call=public_call,
                ).model_dump(by_alias=True),
            )

        settings = make_settings()
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            context = await NpcChatClient(
                settings=settings,
                client=client,
            ).fetch_decision_context(
                session_id=77,
                public_call_id=3001,
                source_event_id="evt-call-1",
            )

        assert (
            observed["url"]
            == "http://chat.test/api/internal/ai/debate/npc/sessions/77/context?publicCallId=3001&sourceEventId=evt-call-1"
        )
        assert context.trigger_message is None
        assert context.public_call is not None
        assert context.public_call.public_call_id == 3001

    asyncio.run(scenario())


def test_chat_client_posts_candidate_with_internal_key_and_camel_payload() -> None:
    async def scenario() -> None:
        observed: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            observed["url"] = str(request.url)
            observed["internal_key"] = request.headers.get("x-ai-internal-key")
            observed["payload"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "accepted": True,
                    "actionId": 9001,
                    "actionUid": observed["payload"]["actionUid"],
                    "status": "created",
                    "reasonCode": None,
                },
            )

        settings = make_settings()
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            candidate = candidate_from_raw_output(
                {
                    "actionType": "praise",
                    "publicText": "这个回应很漂亮。",
                    "targetMessageId": 1001,
                },
                context=make_context(),
                settings=settings,
                executor_kind="llm_executor_v1",
                executor_version="llm_executor_v1",
            )
            output = await NpcChatClient(settings=settings, client=client).submit_action_candidate(
                candidate
            )

        assert observed["url"] == "http://chat.test/api/internal/ai/debate/npc/actions/candidates"
        assert observed["internal_key"] == "test-internal-key"
        assert observed["payload"]["actionType"] == "praise"
        assert observed["payload"]["publicText"] == "这个回应很漂亮。"
        assert observed["payload"]["executorKind"] == "llm_executor_v1"
        assert output.accepted is True
        assert output.action_id == 9001
        assert output.action_uid == candidate.action_uid

    asyncio.run(scenario())
