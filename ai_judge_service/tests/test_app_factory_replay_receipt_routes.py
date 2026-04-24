from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from app.app_factory import create_app, create_runtime

from tests.app_factory_test_helpers import (
    AppFactoryRouteTestMixin,
)
from tests.app_factory_test_helpers import (
    build_final_request as _build_final_request,
)
from tests.app_factory_test_helpers import (
    build_phase_request as _build_phase_request,
)
from tests.app_factory_test_helpers import (
    build_settings as _build_settings,
)
from tests.app_factory_test_helpers import (
    unique_case_id as _unique_case_id,
)


class AppFactoryReplayReceiptRouteTests(
    AppFactoryRouteTestMixin,
    unittest.IsolatedAsyncioTestCase,
):
    async def test_replay_post_should_prefer_final_receipt_when_auto(self) -> None:
        phase_calls: list[tuple[int, dict[str, Any]]] = []
        final_calls: list[tuple[int, dict[str, Any]]] = []

        async def phase_callback(
            *, cfg: object, case_id: int, payload: dict[str, Any]
        ) -> None:
            phase_calls.append((case_id, payload))

        async def final_callback(
            *, cfg: object, case_id: int, payload: dict[str, Any]
        ) -> None:
            final_calls.append((case_id, payload))

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=phase_callback,
            callback_final_report_impl=final_callback,
            callback_phase_failed_impl=phase_callback,
            callback_final_failed_impl=final_callback,
        )
        app = create_app(runtime)

        phase_req = _build_phase_request(case_id=5001, idempotency_key="phase:5001")
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(case_id=5001, idempotency_key="final:5001")
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)
        callback_total_before_replay = len(phase_calls) + len(final_calls)

        replay_resp = await self._post(
            app=app,
            path="/internal/judge/cases/5001/replay?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(replay_resp.status_code, 200)
        replay_payload = replay_resp.json()
        self.assertEqual(replay_payload["dispatchType"], "final")
        self.assertIn("reportPayload", replay_payload)
        self.assertIn("verdictContract", replay_payload)
        self.assertIn("debateSummary", replay_payload["reportPayload"])
        self.assertIn("trustAttestation", replay_payload["reportPayload"])
        self.assertEqual(
            replay_payload["reportPayload"]["judgeTrace"]["panelRuntimeProfiles"]["judgeC"][
                "profileId"
            ],
            "panel-judgeC-dimension-composite-v1",
        )
        self.assertEqual(replay_payload["judgeCoreStage"], "replay_computed")
        self.assertEqual(replay_payload["judgeCoreVersion"], "v1")
        self.assertEqual(callback_total_before_replay, len(phase_calls) + len(final_calls))
        replay_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=5001)
        self.assertEqual(replay_events[-1].event_type, "replay_marked")
        self.assertEqual(replay_events[-1].payload.get("judgeCoreStage"), "replay_computed")
        replay_claim_ledger = await runtime.workflow_runtime.facts.get_claim_ledger_record(
            case_id=5001,
            dispatch_type="final",
        )
        self.assertIsNotNone(replay_claim_ledger)
        assert replay_claim_ledger is not None
        self.assertEqual(replay_claim_ledger.case_dossier.get("dispatchType"), "final")
        self.assertEqual(
            replay_claim_ledger.case_dossier.get("phase", {}).get("startNo"),
            final_req.phase_start_no,
        )
        self.assertEqual(
            replay_claim_ledger.case_dossier.get("phase", {}).get("endNo"),
            final_req.phase_end_no,
        )

    async def test_trace_and_replay_report_should_keep_judge_workflow_summary_contract(
        self,
    ) -> None:
        async def noop_callback(
            *, cfg: object, case_id: int, payload: dict[str, Any]
        ) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)

        case_id = _unique_case_id(5401)
        phase_req = _build_phase_request(case_id=case_id, idempotency_key=f"phase:{case_id}")
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(case_id=case_id, idempotency_key=f"final:{case_id}")
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        trace_resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/trace",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(trace_resp.status_code, 200)
        trace_payload = trace_resp.json()
        trace_summary = trace_payload["reportSummary"]
        self.assertEqual(trace_summary["dispatchType"], "final")
        self.assertIsInstance(trace_summary["judgeWorkflow"], dict)
        self.assertIsInstance(trace_summary["roleNodes"], list)
        self.assertEqual(len(trace_summary["roleNodes"]), 8)
        self.assertEqual(trace_summary["roleNodes"][0]["role"], "clerk")
        self.assertEqual(trace_summary["roleNodes"][-1]["role"], "opinion_writer")

        replay_report_resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/replay/report",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(replay_report_resp.status_code, 200)
        replay_report_payload = replay_report_resp.json()
        replay_summary = replay_report_payload["reportSummary"]
        self.assertEqual(replay_summary["dispatchType"], "final")
        self.assertIsInstance(replay_summary["judgeWorkflow"], dict)
        self.assertIsInstance(replay_summary["roleNodes"], list)
        self.assertEqual(len(replay_summary["roleNodes"]), 8)
        self.assertEqual(replay_summary["roleNodes"][0]["role"], "clerk")
        self.assertEqual(replay_summary["roleNodes"][-1]["role"], "opinion_writer")

    async def test_receipt_route_should_fallback_to_fact_repository_when_trace_missing(
        self,
    ) -> None:
        async def noop_callback(
            *, cfg: object, case_id: int, payload: dict[str, Any]
        ) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)

        req = _build_phase_request(case_id=7001, idempotency_key="phase:7001")
        dispatch_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(dispatch_resp.status_code, 200)

        fact_receipt = await runtime.workflow_runtime.facts.get_dispatch_receipt(
            dispatch_type="phase",
            job_id=7001,
        )
        self.assertIsNotNone(fact_receipt)
        assert fact_receipt is not None
        self.assertEqual(fact_receipt.status, "reported")

        runtime.trace_store.get_dispatch_receipt = lambda **kwargs: None  # type: ignore[attr-defined]
        receipt_resp = await self._get(
            app=app,
            path="/internal/judge/v3/phase/cases/7001/receipt",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(receipt_resp.status_code, 200)
        self.assertEqual(receipt_resp.json()["status"], "reported")

    async def test_replay_post_should_persist_replay_record_to_fact_repository(
        self,
    ) -> None:
        phase_calls: list[tuple[int, dict[str, Any]]] = []
        final_calls: list[tuple[int, dict[str, Any]]] = []

        async def phase_callback(
            *, cfg: object, case_id: int, payload: dict[str, Any]
        ) -> None:
            phase_calls.append((case_id, payload))

        async def final_callback(
            *, cfg: object, case_id: int, payload: dict[str, Any]
        ) -> None:
            final_calls.append((case_id, payload))

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=phase_callback,
            callback_final_report_impl=final_callback,
            callback_phase_failed_impl=phase_callback,
            callback_final_failed_impl=final_callback,
        )
        app = create_app(runtime)
        await runtime.workflow_runtime.db.create_schema()
        before_rows = await runtime.workflow_runtime.facts.list_replay_records(
            job_id=7101,
            limit=200,
        )
        before_count = len(before_rows)

        phase_req = _build_phase_request(case_id=7101, idempotency_key="phase:7101")
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(case_id=7101, idempotency_key="final:7101")
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        replay_resp = await self._post(
            app=app,
            path="/internal/judge/cases/7101/replay?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(replay_resp.status_code, 200)

        replay_rows = await runtime.workflow_runtime.facts.list_replay_records(
            job_id=7101,
            limit=200,
        )
        self.assertEqual(len(replay_rows), before_count + 1)
        self.assertEqual(replay_rows[0].dispatch_type, "final")
        self.assertIn(replay_rows[0].winner, {"pro", "con", "draw"})
        replay_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=7101)
        self.assertEqual(replay_events[-1].event_type, "replay_marked")
        self.assertEqual(replay_events[-1].payload.get("judgeCoreStage"), "replay_computed")

    async def test_replay_post_should_block_when_final_contract_missing_fields(
        self,
    ) -> None:
        async def noop_callback(
            *, cfg: object, case_id: int, payload: dict[str, Any]
        ) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)

        phase_req = _build_phase_request(case_id=7102, idempotency_key="phase:7102")
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(case_id=7102, idempotency_key="final:7102")
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)
        before_replay_rows = await runtime.workflow_runtime.facts.list_replay_records(
            job_id=7102,
            limit=100,
        )
        before_replay_count = len(before_replay_rows)

        broken_payload = {
            "winner": "pro",
            "proScore": 70.0,
            "conScore": 62.0,
            "dimensionScores": {"logic": 70.0},
        }
        with patch(
            "app.applications.bootstrap_final_report_helpers."
            "build_final_report_payload_for_dispatch_v3",
            return_value=broken_payload,
        ):
            replay_resp = await self._post(
                app=app,
                path="/internal/judge/cases/7102/replay?dispatch_type=final",
                internal_key=runtime.settings.ai_internal_key,
            )
        self.assertEqual(replay_resp.status_code, 409)
        self.assertIn("replay_final_contract_violation", replay_resp.text)

        after_replay_rows = await runtime.workflow_runtime.facts.list_replay_records(
            job_id=7102,
            limit=100,
        )
        self.assertEqual(len(after_replay_rows), before_replay_count)
        workflow_events = await runtime.workflow_runtime.orchestrator.list_events(job_id=7102)
        self.assertNotEqual(workflow_events[-1].event_type, "replay_marked")


if __name__ == "__main__":
    unittest.main()
