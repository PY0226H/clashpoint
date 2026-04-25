from __future__ import annotations

import asyncio
import tempfile
import unittest
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.infra.artifacts import LocalArtifactStore
from app.trace_store import TraceStore
from app.trace_store_boundaries import build_trace_store_boundaries


@dataclass(frozen=True)
class _PayloadObject:
    payload: dict

    def to_payload(self) -> dict:
        return dict(self.payload)


@dataclass(frozen=True)
class _ReplayRecord:
    dispatch_type: str
    trace_id: str
    winner: str
    needs_draw_vote: bool
    provider: str
    created_at: datetime


class _WorkflowStore:
    async def get_job(self, *, job_id: int):
        return SimpleNamespace(
            job_id=job_id,
            trace_id=f"trace-{job_id}",
            status="reported",
        )

    async def list_events(self, *, job_id: int):
        return [
            SimpleNamespace(
                job_id=job_id,
                event_seq=1,
                event_type="case_built",
                created_at=datetime(2026, 4, 24, tzinfo=timezone.utc),
            ),
            SimpleNamespace(
                job_id=job_id,
                event_seq=2,
                event_type="opinion_written",
                created_at=datetime(2026, 4, 24, tzinfo=timezone.utc),
            ),
        ]


class _FactRepository:
    async def get_judge_ledger_snapshot(
        self,
        *,
        case_id: int,
        dispatch_type: str | None,
    ):
        return SimpleNamespace(
            case_id=case_id,
            dispatch_type=dispatch_type,
            case_dossier=_PayloadObject({"caseId": case_id}),
            claim_graph=_PayloadObject({"claims": [{"id": "c1"}]}),
            evidence_ledger=_PayloadObject({"evidenceRefs": [{"id": "e1"}]}),
            verdict_ledger=_PayloadObject({"winner": "pro"}),
            fairness_report=_PayloadObject({"autoJudgeAllowed": True}),
            opinion_pack=_PayloadObject({"userReport": {"winner": "pro"}}),
        )

    async def get_claim_ledger_record(
        self,
        *,
        case_id: int,
        dispatch_type: str | None,
    ):
        return SimpleNamespace(case_id=case_id, dispatch_type=dispatch_type)

    async def list_replay_records(
        self,
        *,
        dispatch_type: str | None,
        job_id: int,
        limit: int,
    ):
        return [
            _ReplayRecord(
                dispatch_type=dispatch_type or "final",
                trace_id=f"trace-{job_id}",
                winner="pro",
                needs_draw_vote=False,
                provider="mock",
                created_at=datetime(2026, 4, 24, tzinfo=timezone.utc),
            )
        ][:limit]

    async def append_replay_record(self, **kwargs):
        return _ReplayRecord(
            dispatch_type=str(kwargs["dispatch_type"]),
            trace_id=str(kwargs["trace_id"]),
            winner=str(kwargs["winner"]),
            needs_draw_vote=bool(kwargs["needs_draw_vote"]),
            provider=str(kwargs["provider"]),
            created_at=datetime(2026, 4, 24, tzinfo=timezone.utc),
        )


class TraceStoreBoundariesTests(unittest.TestCase):
    def test_boundaries_should_delegate_writes_replay_and_audit(self) -> None:
        store = TraceStore(ttl_secs=3600)
        boundaries = build_trace_store_boundaries(
            trace_store=store,
            workflow_store=_WorkflowStore(),
            fact_repository=_FactRepository(),
        )

        boundaries.write_store.register_start(
            job_id=7101,
            trace_id="trace-7101",
            request={"traceId": "trace-7101"},
        )
        boundaries.write_store.register_success(
            job_id=7101,
            response={"winner": "pro"},
            callback_status="reported",
            report_summary={"winner": "pro", "payload": {"winner": "pro"}},
        )
        boundaries.replay_store.mark_replay(
            job_id=7101,
            winner="pro",
            needs_draw_vote=False,
            provider="mock",
        )
        alert = boundaries.audit_alert_store.upsert_alert(
            job_id=7101,
            scope_id=1,
            trace_id="trace-7101",
            alert_type="policy_gap",
            severity="warning",
            title="Policy Gap",
            message="missing durable evidence",
            details={"field": "evidenceLedger"},
        )

        trace = boundaries.read_model.get_trace(7101)
        self.assertIsNotNone(trace)
        assert trace is not None
        self.assertEqual(trace.callback_status, "reported")
        self.assertEqual(len(trace.replays), 1)
        alerts = boundaries.audit_alert_store.list_alerts(job_id=7101)
        self.assertEqual(alerts[0].alert_id, alert.alert_id)

    def test_read_model_should_build_durable_chain_summary(self) -> None:
        store = TraceStore(ttl_secs=3600)
        store.register_start(
            job_id=7201,
            trace_id="trace-7201",
            request={"traceId": "trace-7201"},
        )
        store.register_success(
            job_id=7201,
            response={"winner": "pro"},
            callback_status="reported",
            report_summary={"winner": "pro", "payload": {"winner": "pro"}},
        )
        store.upsert_audit_alert(
            job_id=7201,
            scope_id=1,
            trace_id="trace-7201",
            alert_type="review_gap",
            severity="warning",
            title="Review Gap",
            message="review required",
            details={},
        )
        boundaries = build_trace_store_boundaries(
            trace_store=store,
            workflow_store=_WorkflowStore(),
            fact_repository=_FactRepository(),
        )

        summary = asyncio.run(
            boundaries.read_model.build_case_chain_summary(
                job_id=7201,
                dispatch_type="final",
            )
        )

        self.assertEqual(summary["version"], "trace-replay-audit-read-model-v1")
        self.assertEqual(summary["caseId"], 7201)
        self.assertEqual(summary["durableKeys"]["traceId"], "trace-7201")
        self.assertTrue(summary["workflow"]["present"])
        self.assertEqual(summary["workflow"]["eventCount"], 2)
        self.assertEqual(summary["ledgerChain"]["source"], "judge_ledger_snapshots")
        self.assertTrue(summary["ledgerChain"]["complete"])
        self.assertTrue(summary["ledgerChain"]["objectPresence"]["caseDossier"])
        self.assertEqual(summary["replay"]["count"], 1)
        self.assertEqual(summary["audit"]["openAlertCount"], 1)
        self.assertEqual(summary["errors"], [])

    def test_replay_store_should_append_to_fact_repository(self) -> None:
        boundaries = build_trace_store_boundaries(
            trace_store=TraceStore(ttl_secs=3600),
            fact_repository=_FactRepository(),
        )

        row = asyncio.run(
            boundaries.replay_store.append_record(
                dispatch_type="phase",
                job_id=7301,
                trace_id="trace-7301",
                winner="draw",
                needs_draw_vote=True,
                provider="mock",
                report_payload={"winner": "draw"},
            )
        )

        self.assertEqual(row.dispatch_type, "phase")
        self.assertEqual(row.trace_id, "trace-7301")
        self.assertEqual(row.winner, "draw")

    def test_artifact_store_boundary_should_delegate_local_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_store = LocalArtifactStore(root_dir=Path(tmpdir) / "artifacts")
            boundaries = build_trace_store_boundaries(
                trace_store=TraceStore(ttl_secs=3600),
                artifact_store=artifact_store,
            )

            ref = asyncio.run(
                boundaries.artifact_store.put_json(
                    case_id=7401,
                    kind="replay_snapshot",
                    payload={"version": "replay-v1", "winner": "draw"},
                    dispatch_type="phase",
                    trace_id="trace-7401",
                )
            )
            manifest = boundaries.artifact_store.build_manifest(
                case_id=7401,
                dispatch_type="phase",
                trace_id="trace-7401",
                refs=[ref],
            )

            self.assertTrue(asyncio.run(boundaries.artifact_store.exists(ref=ref)))
            self.assertEqual(manifest.to_payload()["artifactRefs"][0]["kind"], "replay_snapshot")


if __name__ == "__main__":
    unittest.main()
