from __future__ import annotations

import json
from typing import Any, Protocol, cast

import httpx

OPENAI_META_KEY = "__openai_meta"


def _extract_json_object(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("empty model response")
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end < 0 or end <= start:
        raise ValueError("json object not found in model response")
    parsed = json.loads(raw[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("json root must be object")
    return cast(dict[str, Any], parsed)


def _extract_usage_payload(value: object) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    payload = cast(dict[str, object], value)
    prompt = payload.get("prompt_tokens")
    completion = payload.get("completion_tokens")
    total = payload.get("total_tokens")
    prompt_i = _coerce_int(prompt, default=0)
    completion_i = _coerce_int(completion, default=0)
    total_i = _coerce_int(total, default=max(0, prompt_i + completion_i))
    return {
        "prompt_tokens": max(0, prompt_i),
        "completion_tokens": max(0, completion_i),
        "total_tokens": max(0, total_i),
    }


def _coerce_int(value: object, *, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return default
        try:
            return int(raw)
        except ValueError:
            return default
    return default


class OpenAiConfigProtocol(Protocol):
    api_key: str
    model: str
    base_url: str
    timeout_secs: float
    temperature: float
    max_retries: int


async def call_openai_json(
    *,
    cfg: OpenAiConfigProtocol,
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any]:
    body = {
        "model": cfg.model,
        "temperature": cfg.temperature,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {
        "Authorization": f"Bearer {cfg.api_key}",
        "Content-Type": "application/json",
    }
    last_err: Exception | None = None
    for _ in range(max(1, cfg.max_retries)):
        try:
            async with httpx.AsyncClient(timeout=cfg.timeout_secs) as client:
                resp = await client.post(
                    f"{cfg.base_url}/chat/completions",
                    headers=headers,
                    json=body,
                )
            if resp.status_code // 100 != 2:
                raise RuntimeError(f"openai status={resp.status_code}, body={resp.text[:500]}")
            data = resp.json()
            if not isinstance(data, dict):
                raise RuntimeError("openai response must be object")
            choices = data.get("choices")
            if not isinstance(choices, list) or not choices:
                raise RuntimeError("openai response missing choices")
            first_choice = choices[0]
            if not isinstance(first_choice, dict):
                raise RuntimeError("openai choice must be object")
            message = first_choice.get("message")
            if not isinstance(message, dict):
                raise RuntimeError("openai choice missing message")
            content = message.get("content")
            if not isinstance(content, str):
                raise RuntimeError("openai message content must be string")
            payload = _extract_json_object(content)
            usage = _extract_usage_payload(data.get("usage"))
            if usage is not None:
                payload[OPENAI_META_KEY] = {"usage": usage}
            return payload
        except Exception as err:  # pragma: no cover
            last_err = err
    raise RuntimeError(f"openai call failed after retries: {last_err}")
