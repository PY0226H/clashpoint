from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable


async def ensure_workflow_schema_ready_for_runtime(
    *,
    runtime: Any,
    workflow_schema_state: dict[str, bool],
    workflow_schema_lock: asyncio.Lock,
) -> None:
    if workflow_schema_state["ready"] or not runtime.settings.db_auto_create_schema:
        return
    async with workflow_schema_lock:
        if workflow_schema_state["ready"]:
            return
        await runtime.workflow_runtime.db.create_schema()
        workflow_schema_state["ready"] = True


async def ensure_registry_runtime_ready_for_runtime(
    *,
    runtime: Any,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
) -> None:
    await ensure_workflow_schema_ready()
    await runtime.registry_product_runtime.ensure_loaded()
