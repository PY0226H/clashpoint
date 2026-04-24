from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from app.applications.bootstrap_workflow_trace_store_helpers import (
    append_replay_record_for_runtime,
    get_claim_ledger_record_for_runtime,
    get_dispatch_receipt_for_runtime,
    list_audit_alerts_for_runtime,
    list_claim_ledger_records_for_runtime,
    list_dispatch_receipts_for_runtime,
    list_fairness_benchmark_runs_for_runtime,
    list_fairness_shadow_runs_for_runtime,
    list_replay_records_for_runtime,
    persist_dispatch_receipt_for_runtime,
    sync_audit_alert_to_facts_for_runtime,
    upsert_claim_ledger_record_for_runtime,
    upsert_fairness_benchmark_run_for_runtime,
    upsert_fairness_shadow_run_for_runtime,
    workflow_append_event_for_runtime,
    workflow_get_job_for_runtime,
    workflow_list_events_for_runtime,
    workflow_list_jobs_for_runtime,
)
from fastapi import HTTPException


class _Facts:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.audit_alerts: list[Any] = []
        self.dispatch_receipt: Any | None = None
        self.dispatch_receipts: list[Any] = []
        self.dispatch_receipt_upserts: list[Any] = []
        self.claim_ledger_upserts: list[dict[str, Any]] = []

    async def list_audit_alerts(self, **kwargs: Any) -> list[Any]:
        self.calls.append(("list_audit_alerts", kwargs))
        return self.audit_alerts

    async def upsert_fairness_benchmark_run(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("upsert_fairness_benchmark_run", kwargs))
        return {"kind": "benchmark", **kwargs}

    async def list_fairness_benchmark_runs(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.calls.append(("list_fairness_benchmark_runs", kwargs))
        return [{"kind": "benchmark-list", **kwargs}]

    async def upsert_fairness_shadow_run(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("upsert_fairness_shadow_run", kwargs))
        return {"kind": "shadow", **kwargs}

    async def list_fairness_shadow_runs(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.calls.append(("list_fairness_shadow_runs", kwargs))
        return [{"kind": "shadow-list", **kwargs}]

    async def get_dispatch_receipt(self, **kwargs: Any) -> Any | None:
        self.calls.append(("get_dispatch_receipt", kwargs))
        return self.dispatch_receipt

    async def list_dispatch_receipts(self, **kwargs: Any) -> list[Any]:
        self.calls.append(("list_dispatch_receipts", kwargs))
        return self.dispatch_receipts

    async def append_replay_record(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("append_replay_record", kwargs))
        return {"kind": "replay", **kwargs}

    async def upsert_dispatch_receipt(self, *, receipt: Any) -> Any:
        self.calls.append(("upsert_dispatch_receipt", {"receipt": receipt}))
        self.dispatch_receipt_upserts.append(receipt)
        return receipt

    async def list_replay_records(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.calls.append(("list_replay_records", kwargs))
        return [{"kind": "replay-list", **kwargs}]

    async def get_claim_ledger_record(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("get_claim_ledger_record", kwargs))
        return {"kind": "claim", **kwargs}

    async def list_claim_ledger_records(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.calls.append(("list_claim_ledger_records", kwargs))
        return [{"kind": "claim-list", **kwargs}]

    async def upsert_claim_ledger_record(self, **kwargs: Any) -> Any:
        self.calls.append(("upsert_claim_ledger_record", kwargs))
        self.claim_ledger_upserts.append(kwargs)
        return SimpleNamespace(**kwargs)

    async def upsert_audit_alert(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("upsert_audit_alert", kwargs))
        return {"kind": "alert", **kwargs}


class _Orchestrator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.append_should_fail = False

    async def get_job(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("get_job", kwargs))
        return {"kind": "job", **kwargs}

    async def list_jobs(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.calls.append(("list_jobs", kwargs))
        return [{"kind": "job-list", **kwargs}]

    async def list_events(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.calls.append(("list_events", kwargs))
        return [{"kind": "event-list", **kwargs}]

    async def append_event(self, **kwargs: Any) -> None:
        self.calls.append(("append_event", kwargs))
        if self.append_should_fail:
            raise LookupError("missing")


class _TraceStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.saved_dispatch_receipts: list[dict[str, Any]] = []

    def list_audit_alerts(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.calls.append(("list_audit_alerts", kwargs))
        return [{"source": "trace-alert", **kwargs}]

    def get_dispatch_receipt(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("get_dispatch_receipt", kwargs))
        return {"source": "trace-receipt", **kwargs}

    def list_dispatch_receipts(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.calls.append(("list_dispatch_receipts", kwargs))
        return [{"source": "trace-receipt-list", **kwargs}]

    def save_dispatch_receipt(self, **kwargs: Any) -> None:
        self.calls.append(("save_dispatch_receipt", kwargs))
        self.saved_dispatch_receipts.append(kwargs)


class BootstrapWorkflowTraceStoreHelpersTests(unittest.IsolatedAsyncioTestCase):
    def _runtime(self) -> tuple[SimpleNamespace, _Facts, _Orchestrator, _TraceStore]:
        facts = _Facts()
        orchestrator = _Orchestrator()
        trace_store = _TraceStore()
        runtime = SimpleNamespace(
            workflow_runtime=SimpleNamespace(
                facts=facts,
                orchestrator=orchestrator,
            ),
            trace_store=trace_store,
        )
        return runtime, facts, orchestrator, trace_store

    async def test_list_alerts_and_receipts_should_fallback_to_trace_store(self) -> None:
        runtime, facts, _orchestrator, trace_store = self._runtime()
        ensure_calls = {"count": 0}

        async def _ensure() -> None:
            ensure_calls["count"] += 1

        self.assertEqual(
            await list_audit_alerts_for_runtime(
                runtime=runtime,
                ensure_workflow_schema_ready=_ensure,
                job_id=42,
                status="open",
                limit=10,
            ),
            [{"source": "trace-alert", "job_id": 42, "status": "open", "limit": 10}],
        )
        self.assertEqual(
            await get_dispatch_receipt_for_runtime(
                runtime=runtime,
                ensure_workflow_schema_ready=_ensure,
                dispatch_type="final",
                job_id=42,
            ),
            {"source": "trace-receipt", "dispatch_type": "final", "job_id": 42},
        )
        self.assertEqual(
            await list_dispatch_receipts_for_runtime(
                runtime=runtime,
                ensure_workflow_schema_ready=_ensure,
                dispatch_type="phase",
                session_id=2,
                status="reported",
                limit=3,
            ),
            [
                {
                    "source": "trace-receipt-list",
                    "dispatch_type": "phase",
                    "session_id": 2,
                    "status": "reported",
                    "limit": 3,
                }
            ],
        )

        self.assertEqual(ensure_calls, {"count": 3})
        self.assertEqual(len(facts.calls), 3)
        self.assertEqual(len(trace_store.calls), 3)

    async def test_workflow_orchestrator_helpers_should_call_schema_first(self) -> None:
        runtime, _facts, orchestrator, _trace_store = self._runtime()
        ensure_calls = {"count": 0}

        async def _ensure() -> None:
            ensure_calls["count"] += 1

        self.assertEqual(
            await workflow_get_job_for_runtime(
                runtime=runtime,
                ensure_workflow_schema_ready=_ensure,
                job_id=7,
            ),
            {"kind": "job", "job_id": 7},
        )
        self.assertEqual(
            await workflow_list_jobs_for_runtime(
                runtime=runtime,
                ensure_workflow_schema_ready=_ensure,
                status="reported",
                dispatch_type="final",
                limit=5,
            ),
            [
                {
                    "kind": "job-list",
                    "status": "reported",
                    "dispatch_type": "final",
                    "limit": 5,
                }
            ],
        )
        self.assertEqual(
            await workflow_list_events_for_runtime(
                runtime=runtime,
                ensure_workflow_schema_ready=_ensure,
                job_id=7,
            ),
            [{"kind": "event-list", "job_id": 7}],
        )
        await workflow_append_event_for_runtime(
            runtime=runtime,
            ensure_workflow_schema_ready=_ensure,
            job_id=7,
            event_type="marked",
            event_payload={"ok": True},
        )
        orchestrator.append_should_fail = True
        with self.assertRaises(HTTPException) as ctx:
            await workflow_append_event_for_runtime(
                runtime=runtime,
                ensure_workflow_schema_ready=_ensure,
                job_id=99,
                event_type="missing",
                event_payload={},
                not_found_detail="custom_missing",
            )

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "custom_missing")
        self.assertEqual(ensure_calls, {"count": 5})
        self.assertEqual([name for name, _kwargs in orchestrator.calls], [
            "get_job",
            "list_jobs",
            "list_events",
            "append_event",
            "append_event",
        ])

    async def test_fact_helpers_should_delegate_to_workflow_facts(self) -> None:
        runtime, facts, _orchestrator, _trace_store = self._runtime()
        ensure_calls = {"count": 0}

        async def _ensure() -> None:
            ensure_calls["count"] += 1

        reported_at = datetime(2026, 4, 24, tzinfo=timezone.utc)
        benchmark = await upsert_fairness_benchmark_run_for_runtime(
            runtime=runtime,
            ensure_workflow_schema_ready=_ensure,
            run_id="bench-1",
            policy_version="p1",
            environment_mode="mock",
            status="completed",
            threshold_decision="accepted",
            needs_real_env_reconfirm=False,
            needs_remediation=False,
            sample_size=10,
            draw_rate=0.2,
            side_bias_delta=0.1,
            appeal_overturn_rate=0.0,
            thresholds={"draw": 0.8},
            metrics={"sample": 10},
            summary={"ok": True},
            source="test",
            reported_by="tester",
            reported_at=reported_at,
        )
        shadow = await upsert_fairness_shadow_run_for_runtime(
            runtime=runtime,
            ensure_workflow_schema_ready=_ensure,
            run_id="shadow-1",
            policy_version="p1",
            benchmark_run_id="bench-1",
            environment_mode="mock",
            status="completed",
            threshold_decision="accepted",
            needs_real_env_reconfirm=False,
            needs_remediation=False,
            sample_size=10,
            winner_flip_rate=0.0,
            score_shift_delta=0.0,
            review_required_delta=0.0,
            thresholds=None,
            metrics=None,
            summary=None,
            source=None,
            reported_by=None,
            reported_at=None,
        )
        replay = await append_replay_record_for_runtime(
            runtime=runtime,
            ensure_workflow_schema_ready=_ensure,
            dispatch_type="final",
            job_id=42,
            trace_id="trace-42",
            winner="draw",
            needs_draw_vote=True,
            provider="mock",
            report_payload={"winner": "draw"},
        )
        claim = await get_claim_ledger_record_for_runtime(
            runtime=runtime,
            ensure_workflow_schema_ready=_ensure,
            case_id=42,
            dispatch_type="final",
        )
        alert = await sync_audit_alert_to_facts_for_runtime(
            runtime=runtime,
            ensure_workflow_schema_ready=_ensure,
            alert=SimpleNamespace(
                alert_id=" alert-1 ",
                job_id=42,
                scope_id=2,
                trace_id=" trace-42 ",
                alert_type=" fairness ",
                severity=" warning ",
                title=" title ",
                message=" message ",
                details={"k": "v"},
                updated_at=reported_at,
            ),
        )
        await list_fairness_benchmark_runs_for_runtime(
            runtime=runtime,
            ensure_workflow_schema_ready=_ensure,
            policy_version="p1",
            environment_mode="mock",
            status="completed",
            limit=5,
        )
        await list_fairness_shadow_runs_for_runtime(
            runtime=runtime,
            ensure_workflow_schema_ready=_ensure,
            policy_version="p1",
            benchmark_run_id="bench-1",
            environment_mode="mock",
            status="completed",
            limit=5,
        )
        await list_replay_records_for_runtime(
            runtime=runtime,
            ensure_workflow_schema_ready=_ensure,
            job_id=42,
            dispatch_type="final",
            limit=5,
        )
        await list_claim_ledger_records_for_runtime(
            runtime=runtime,
            ensure_workflow_schema_ready=_ensure,
            case_id=42,
            limit=5,
        )

        self.assertEqual(benchmark["run_id"], "bench-1")
        self.assertEqual(shadow["benchmark_run_id"], "bench-1")
        self.assertEqual(replay["trace_id"], "trace-42")
        self.assertEqual(claim["case_id"], 42)
        self.assertEqual(alert["alert_id"], "alert-1")
        self.assertEqual(alert["trace_id"], "trace-42")
        self.assertEqual(ensure_calls, {"count": 9})
        self.assertIn("append_replay_record", [name for name, _kwargs in facts.calls])

    async def test_persist_dispatch_receipt_should_write_trace_store_and_facts(self) -> None:
        runtime, facts, _orchestrator, trace_store = self._runtime()
        ensure_calls = {"count": 0}

        async def _ensure() -> None:
            ensure_calls["count"] += 1

        await persist_dispatch_receipt_for_runtime(
            runtime=runtime,
            ensure_workflow_schema_ready=_ensure,
            dispatch_type="final",
            job_id=-42,
            scope_id=7,
            session_id=9,
            trace_id=" trace-42 ",
            idempotency_key=" idem-42 ",
            rubric_version=" rubric-v1 ",
            judge_policy_version=" policy-v1 ",
            topic_domain=" debate ",
            retrieval_profile="default",
            phase_no=None,
            phase_start_no=1,
            phase_end_no=3,
            message_start_id=None,
            message_end_id=None,
            message_count=None,
            status=" reported ",
            request_payload={"caseId": 42},
            response_payload={"winner": "draw"},
        )

        self.assertEqual(ensure_calls, {"count": 1})
        self.assertEqual(trace_store.saved_dispatch_receipts[0]["job_id"], -42)
        self.assertEqual(trace_store.saved_dispatch_receipts[0]["request"], {"caseId": 42})
        receipt = facts.dispatch_receipt_upserts[0]
        self.assertEqual(receipt.job_id, 0)
        self.assertEqual(receipt.trace_id, "trace-42")
        self.assertEqual(receipt.status, "reported")
        self.assertEqual(receipt.request, {"caseId": 42})
        self.assertEqual(receipt.response, {"winner": "draw"})

    async def test_upsert_claim_ledger_should_build_request_dossier_fallback(self) -> None:
        runtime, facts, _orchestrator, _trace_store = self._runtime()
        ensure_calls = {"count": 0}

        async def _ensure() -> None:
            ensure_calls["count"] += 1

        result = await upsert_claim_ledger_record_for_runtime(
            runtime=runtime,
            ensure_workflow_schema_ready=_ensure,
            case_id=42,
            dispatch_type="phase",
            trace_id="trace-42",
            report_payload={},
            request_payload={
                "case_id": "42",
                "scope_id": 7,
                "session_id": 9,
                "phaseNo": "2",
                "message_start_id": 100,
                "message_end_id": 102,
                "message_count": 3,
                "messages": [
                    {
                        "messageId": "100",
                        "side": "pro",
                        "speakerTag": "A",
                        "createdAt": "2026-04-24T00:00:00Z",
                    },
                    {"message_id": 101, "side": "con", "speaker_tag": "B"},
                    {"message_id": 102, "side": "neutral", "speaker_tag": "A"},
                ],
            },
        )

        self.assertIsNotNone(result)
        self.assertEqual(ensure_calls, {"count": 1})
        record = facts.claim_ledger_upserts[0]
        self.assertEqual(record["case_id"], 42)
        self.assertEqual(record["dispatch_type"], "phase")
        self.assertEqual(record["case_dossier"]["phase"], {"no": 2})
        self.assertEqual(record["case_dossier"]["messageWindow"]["count"], 3)
        self.assertEqual(
            record["case_dossier"]["sideDistribution"],
            {"pro": 1, "con": 1, "other": 1},
        )
        self.assertEqual(record["case_dossier"]["speakerTags"], ["A", "B"])
        self.assertEqual(len(record["case_dossier"]["messageDigest"]), 3)

    async def test_upsert_claim_ledger_should_skip_without_report_or_request(self) -> None:
        runtime, facts, _orchestrator, _trace_store = self._runtime()
        ensure_calls = {"count": 0}

        async def _ensure() -> None:
            ensure_calls["count"] += 1

        result = await upsert_claim_ledger_record_for_runtime(
            runtime=runtime,
            ensure_workflow_schema_ready=_ensure,
            case_id=42,
            dispatch_type="final",
            trace_id="trace-42",
            report_payload=None,
            request_payload=None,
        )

        self.assertIsNone(result)
        self.assertEqual(ensure_calls, {"count": 0})
        self.assertEqual(facts.claim_ledger_upserts, [])
