from __future__ import annotations

import asyncio
import json

import httpx
from app.chat_client import NpcChatClient
from app.guard import candidate_from_raw_output

from helpers import make_context, make_settings


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
