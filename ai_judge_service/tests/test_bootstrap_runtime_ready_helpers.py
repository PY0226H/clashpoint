from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace

from app.applications.bootstrap_runtime_ready_helpers import (
    ensure_registry_runtime_ready_for_runtime,
    ensure_workflow_schema_ready_for_runtime,
)


class BootstrapRuntimeReadyHelpersTests(unittest.IsolatedAsyncioTestCase):
    async def test_ensure_workflow_schema_ready_should_create_schema_once(self) -> None:
        calls = {"schema": 0}

        async def _create_schema() -> None:
            calls["schema"] += 1

        runtime = SimpleNamespace(
            settings=SimpleNamespace(db_auto_create_schema=True),
            workflow_runtime=SimpleNamespace(
                db=SimpleNamespace(create_schema=_create_schema)
            ),
        )
        state = {"ready": False}
        lock = asyncio.Lock()

        await ensure_workflow_schema_ready_for_runtime(
            runtime=runtime,
            workflow_schema_state=state,
            workflow_schema_lock=lock,
        )
        await ensure_workflow_schema_ready_for_runtime(
            runtime=runtime,
            workflow_schema_state=state,
            workflow_schema_lock=lock,
        )

        self.assertEqual(calls, {"schema": 1})
        self.assertTrue(state["ready"])

    async def test_ensure_registry_runtime_ready_should_load_after_schema_ready(self) -> None:
        calls: list[str] = []

        async def _ensure_schema() -> None:
            calls.append("schema")

        async def _ensure_loaded() -> None:
            calls.append("registry")

        runtime = SimpleNamespace(
            registry_product_runtime=SimpleNamespace(ensure_loaded=_ensure_loaded)
        )

        await ensure_registry_runtime_ready_for_runtime(
            runtime=runtime,
            ensure_workflow_schema_ready=_ensure_schema,
        )

        self.assertEqual(calls, ["schema", "registry"])
