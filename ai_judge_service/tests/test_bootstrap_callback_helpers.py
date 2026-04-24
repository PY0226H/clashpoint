from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from app.applications.bootstrap_callback_helpers import (
    attach_policy_trace_snapshot_for_runtime,
    invoke_failed_callback_with_retry_for_runtime,
    invoke_v3_callback_with_retry_for_runtime,
)


class BootstrapCallbackHelpersTests(unittest.IsolatedAsyncioTestCase):
    async def test_invoke_callback_should_inject_retry_runtime_settings(self) -> None:
        async def _sleep(_delay: float) -> None:
            return None

        runtime = SimpleNamespace(
            dispatch_runtime_cfg=SimpleNamespace(
                runtime_retry_max_attempts=3,
                retry_backoff_ms=25,
            ),
            sleep_fn=_sleep,
        )

        async def _callback(**_kwargs: Any) -> None:
            return None

        with patch(
            "app.applications.bootstrap_callback_helpers.invoke_callback_with_retry_v3"
        ) as invoke:
            invoke.return_value = (2, 1)

            result = await invoke_v3_callback_with_retry_for_runtime(
                _callback,
                42,
                {"ok": True},
                runtime=runtime,
            )

        self.assertEqual(result, (2, 1))
        invoke.assert_awaited_once_with(
            callback_fn=_callback,
            job_id=42,
            payload={"ok": True},
            max_attempts=3,
            backoff_ms=25,
            sleep_fn=_sleep,
        )

    async def test_invoke_failed_callback_should_resolve_callback_by_dispatch_type(self) -> None:
        async def _sleep(_delay: float) -> None:
            return None

        async def _phase_failed(**_kwargs: Any) -> None:
            return None

        async def _final_failed(**_kwargs: Any) -> None:
            return None

        runtime = SimpleNamespace(
            dispatch_runtime_cfg=SimpleNamespace(
                runtime_retry_max_attempts=1,
                retry_backoff_ms=0,
            ),
            sleep_fn=_sleep,
        )

        with patch(
            "app.applications.bootstrap_callback_helpers.invoke_callback_with_retry_v3"
        ) as invoke:
            invoke.return_value = (1, 0)

            result = await invoke_failed_callback_with_retry_for_runtime(
                runtime=runtime,
                dispatch_type="final",
                callback_phase_failed_fn=_phase_failed,
                callback_final_failed_fn=_final_failed,
                case_id=77,
                payload={"failed": True},
            )

        self.assertEqual(result, (1, 0))
        invoke.assert_awaited_once_with(
            callback_fn=_final_failed,
            job_id=77,
            payload={"failed": True},
            max_attempts=1,
            backoff_ms=0,
            sleep_fn=_sleep,
        )

    async def test_attach_policy_trace_snapshot_should_inject_trace_builders(self) -> None:
        runtime = SimpleNamespace(
            policy_registry_runtime=SimpleNamespace(
                build_trace_snapshot=lambda _profile: {"policy": True}
            ),
            prompt_registry_runtime=SimpleNamespace(
                build_trace_snapshot=lambda _profile: {"prompt": True}
            ),
            tool_registry_runtime=SimpleNamespace(
                build_trace_snapshot=lambda _profile: {"tool": True}
            ),
        )
        report_payload: dict[str, Any] = {}

        with patch(
            "app.applications.bootstrap_callback_helpers.attach_policy_trace_snapshot_v3"
        ) as attach:
            attach_policy_trace_snapshot_for_runtime(
                runtime=runtime,
                report_payload=report_payload,
                profile={"version": "policy"},
                prompt_profile={"version": "prompt"},
                tool_profile={"version": "tool"},
            )

        attach.assert_called_once()
        self.assertIs(attach.call_args.kwargs["report_payload"], report_payload)
        self.assertEqual(attach.call_args.kwargs["profile"], {"version": "policy"})
        self.assertTrue(callable(attach.call_args.kwargs["build_policy_trace_snapshot"]))
