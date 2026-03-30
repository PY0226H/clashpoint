from __future__ import annotations

from typing import Any, Protocol

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
    import json

    return json.loads(raw[start : end + 1])


def _extract_usage_payload(value: Any) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    prompt = value.get("prompt_tokens")
    completion = value.get("completion_tokens")
    total = value.get("total_tokens")
    try:
        prompt_i = int(prompt) if prompt is not None else 0
        completion_i = int(completion) if completion is not None else 0
        total_i = int(total) if total is not None else max(0, prompt_i + completion_i)
    except (TypeError, ValueError):
        return None
    return {
        "prompt_tokens": max(0, prompt_i),
        "completion_tokens": max(0, completion_i),
        "total_tokens": max(0, total_i),
    }


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
            content = data["choices"][0]["message"]["content"]
            payload = _extract_json_object(content)
            usage = _extract_usage_payload(data.get("usage"))
            if usage is not None:
                payload[OPENAI_META_KEY] = {"usage": usage}
            return payload
        except Exception as err:  # pragma: no cover
            last_err = err
    raise RuntimeError(f"openai call failed after retries: {last_err}")
