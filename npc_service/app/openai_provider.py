from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Protocol, cast

import httpx

from .models import NpcDecisionContext
from .settings import Settings


class OpenAIProviderError(RuntimeError):
    def __init__(self, reason_code: str, message: str | None = None) -> None:
        super().__init__(message or reason_code)
        self.reason_code = reason_code


class LlmActionProvider(Protocol):
    async def generate_action(self, context: NpcDecisionContext) -> dict[str, Any]:
        pass


class OpenAICompatibleProvider:
    def __init__(
        self,
        settings: Settings,
        *,
        client_factory: Callable[[], httpx.AsyncClient] | None = None,
    ) -> None:
        self._settings = settings
        self._client_factory = client_factory

    async def generate_action(self, context: NpcDecisionContext) -> dict[str, Any]:
        body = {
            "model": self._settings.openai.model,
            "temperature": self._settings.openai.temperature,
            "max_tokens": self._settings.openai.max_output_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": _user_prompt(context)},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self._settings.openai.api_key}",
            "Content-Type": "application/json",
        }
        last_err: Exception | None = None
        for _ in range(max(1, self._settings.openai.max_retries)):
            try:
                async with self._new_client() as client:
                    response = await client.post(
                        f"{self._settings.openai.base_url}/chat/completions",
                        headers=headers,
                        json=body,
                    )
                if response.status_code // 100 != 2:
                    raise OpenAIProviderError(
                        _provider_error_code_for_status(response.status_code),
                        f"openai_status_{response.status_code}: {response.text[:500]}",
                    )
                return _extract_action_payload(response.json(), settings=self._settings)
            except httpx.TimeoutException as err:  # pragma: no cover
                last_err = OpenAIProviderError("llm_timeout", str(err))
            except httpx.HTTPError as err:  # pragma: no cover
                last_err = OpenAIProviderError("llm_provider_http_error", str(err))
            except OpenAIProviderError as err:
                last_err = err
            except Exception as err:  # pragma: no cover
                last_err = err
        if isinstance(last_err, OpenAIProviderError):
            raise OpenAIProviderError(
                last_err.reason_code,
                f"openai_call_failed: {last_err}",
            ) from last_err
        raise OpenAIProviderError("llm_provider_call_failed", f"openai_call_failed: {last_err}") from last_err

    def _new_client(self) -> httpx.AsyncClient:
        if self._client_factory is not None:
            return cast(httpx.AsyncClient, self._client_factory())
        return httpx.AsyncClient(timeout=self._settings.openai.timeout_secs)


def _system_prompt() -> str:
    return "\n".join(
        [
            "You are EchoIsle's virtual judge NPC in a live debate room.",
            "You are public, entertainment-oriented, concise, neutral, and playful.",
            "You may praise a strong user message, speak to energize the room, trigger an effect, or stay quiet.",
            "If publicCall is present, respond only as a room-wide NPC action; never provide private coaching.",
            "You are not the official AI judge panel and must never decide winners, scores, verdicts, or reports.",
            "Return only one JSON object. Use either actionType=no_action, or an allowed public NPC action.",
            "Allowed action fields: actionType, publicText, targetMessageId, effectKind, npcStatus, reasonCode.",
        ]
    )


def _user_prompt(context: NpcDecisionContext) -> str:
    payload = context.model_dump(by_alias=True)
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _extract_action_payload(value: object, *, settings: Settings) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OpenAIProviderError("llm_response_not_object")
    choices = value.get("choices")
    if not isinstance(choices, list) or not choices:
        raise OpenAIProviderError("llm_response_missing_choices")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise OpenAIProviderError("llm_choice_not_object")
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise OpenAIProviderError("llm_choice_missing_message")
    content = message.get("content")
    if not isinstance(content, str):
        raise OpenAIProviderError("llm_content_not_string")
    parsed = _extract_json_object(content)
    usage = value.get("usage")
    if isinstance(usage, dict):
        parsed["_openaiUsage"] = usage
    parsed["_openaiModel"] = str(value.get("model") or settings.openai.model)
    parsed["_openaiProviderName"] = settings.openai.provider_name
    parsed["_openaiPromptVersion"] = settings.npc_prompt_version
    return parsed


def _extract_json_object(text: str) -> dict[str, Any]:
    raw = text.strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end < 0 or end <= start:
        raise OpenAIProviderError("llm_json_object_not_found")
    try:
        parsed = json.loads(raw[start : end + 1])
    except json.JSONDecodeError as err:
        raise OpenAIProviderError("llm_json_invalid", str(err)) from err
    if not isinstance(parsed, dict):
        raise OpenAIProviderError("llm_json_root_not_object")
    return cast(dict[str, Any], parsed)


def _provider_error_code_for_status(status_code: int) -> str:
    if status_code in {401, 403}:
        return "llm_auth_error"
    if status_code == 429:
        return "llm_rate_limited"
    if status_code >= 500:
        return "llm_provider_unavailable"
    return "llm_provider_http_error"
