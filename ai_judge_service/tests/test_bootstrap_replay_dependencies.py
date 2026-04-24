from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any

from app.applications.bootstrap_replay_dependencies import build_replay_dependency_packs


class BootstrapReplayDependenciesTests(unittest.TestCase):
    def test_build_replay_dependency_packs_should_wire_core_callbacks(self) -> None:
        runtime = SimpleNamespace(
            settings=SimpleNamespace(provider="mock"),
            gateway_runtime=SimpleNamespace(),
            trace_store=SimpleNamespace(
                get_trace=lambda *_args, **_kwargs: None,
                register_start=lambda *_args, **_kwargs: None,
                mark_replay=lambda *_args, **_kwargs: None,
            ),
        )

        async def _async_payload(**_kwargs: Any) -> dict[str, Any]:
            return {}

        async def _async_none(**_kwargs: Any) -> None:
            return None

        context, report, finalize = build_replay_dependency_packs(
            runtime=runtime,
            ensure_registry_runtime_ready=_async_none,
            resolve_policy_profile=lambda **_kwargs: {},
            resolve_prompt_profile=lambda **_kwargs: {},
            resolve_tool_profile=lambda **_kwargs: {},
            build_final_report_payload=lambda **_kwargs: {},
            resolve_panel_runtime_profiles=lambda **_kwargs: {},
            build_phase_report_payload=_async_payload,
            attach_judge_agent_runtime_trace=_async_none,
            attach_policy_trace_snapshot=lambda **_kwargs: None,
            get_dispatch_receipt=_async_payload,
            list_dispatch_receipts=lambda **_kwargs: [],
            append_replay_record=_async_payload,
            workflow_mark_replay=_async_none,
            upsert_claim_ledger_record=_async_payload,
        )

        self.assertEqual(
            context.normalize_replay_dispatch_type(" final "),
            "final",
        )
        self.assertIs(report.settings, runtime.settings)
        self.assertIs(report.gateway_runtime, runtime.gateway_runtime)
        self.assertEqual(finalize.provider, "mock")
        self.assertEqual(finalize.draw_margin, 0.8)
