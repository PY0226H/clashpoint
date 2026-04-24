from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from fastapi import FastAPI

AsyncPayloadFn = Callable[..., Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class HealthRouteHandles:
    healthz: AsyncPayloadFn


def register_health_routes(*, app: FastAPI) -> HealthRouteHandles:
    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {"ok": True}

    return HealthRouteHandles(healthz=healthz)
