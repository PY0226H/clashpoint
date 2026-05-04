from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from app.openai_provider import OpenAICompatibleProvider, OpenAIProviderError

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
                    "model": "provider-model",
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
        system_prompt = observed["body"]["messages"][0]["content"]
        assert "pause_suggestion" in system_prompt
        assert "soft_pause" in system_prompt
        assert "hard_pause" in system_prompt
        assert output["actionType"] == "praise"
        assert output["targetMessageId"] == 1001
        assert output["_openaiUsage"]["total_tokens"] == 22
        assert output["_openaiModel"] == "provider-model"
        assert output["_openaiProviderName"] == "openai-compatible-test"
        assert output["_openaiPromptVersion"] == "npc_prompt_test"

    asyncio.run(scenario())


def test_openai_provider_maps_rate_limit_to_reason_code() -> None:
    async def scenario() -> None:
        transport = httpx.MockTransport(lambda request: httpx.Response(429, text="too many"))
        provider = OpenAICompatibleProvider(
            make_settings(),
            client_factory=lambda: httpx.AsyncClient(transport=transport),
        )

        with pytest.raises(OpenAIProviderError) as err:
            await provider.generate_action(make_context())

        assert err.value.reason_code == "llm_rate_limited"

    asyncio.run(scenario())
