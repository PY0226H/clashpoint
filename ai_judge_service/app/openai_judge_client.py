from __future__ import annotations

from typing import Any, Protocol

import httpx


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
            return _extract_json_object(content)
        except Exception as err:  # pragma: no cover
            last_err = err
    raise RuntimeError(f"openai call failed after retries: {last_err}")
