from __future__ import annotations

import asyncio
import json

import httpx
from app.openai_provider import OpenAICompatibleProvider

from helpers import make_context, make_settings


def test_openai_provider_posts_chat_completion_and_extracts_json_action() -> None:
    async def scenario() -> None:
        observed: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            observed["url"] = str(request.url)
            observed["authorization"] = request.headers.get("Authorization")
            body = json.loads(request.content.decode("utf-8"))
            observed["body"] = body
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "actionType": "praise",
                                        "publicText": "这个点很清楚。",
                                        "targetMessageId": 1001,
                                    },
                                    ensure_ascii=False,
                                )
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 12, "total_tokens": 22},
                },
            )

        transport = httpx.MockTransport(handler)
        provider = OpenAICompatibleProvider(
            make_settings(),
            client_factory=lambda: httpx.AsyncClient(transport=transport),
        )

        output = await provider.generate_action(make_context())

        assert observed["url"] == "http://openai.test/v1/chat/completions"
        assert observed["authorization"] == "Bearer test-openai-key"
        assert observed["body"]["response_format"] == {"type": "json_object"}
        assert output["actionType"] == "praise"
        assert output["targetMessageId"] == 1001
        assert output["_openaiUsage"]["total_tokens"] == 22

    asyncio.run(scenario())
