import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.domain.facts import DispatchReceipt
from app.infra.db.runtime import build_database_runtime
from app.infra.facts import JudgeFactRepository


class JudgeFactRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        db_file = Path(self._tmpdir.name) / "fact_repo_test.db"
        settings = SimpleNamespace(
            db_url=f"sqlite+aiosqlite:///{db_file}",
            db_echo=False,
            db_pool_size=5,
            db_max_overflow=5,
        )
        self._db_runtime = build_database_runtime(settings=settings)
        await self._db_runtime.create_schema()
        self._repo = JudgeFactRepository(session_factory=self._db_runtime.session_factory)

    async def asyncTearDown(self) -> None:
        await self._db_runtime.dispose()
        self._tmpdir.cleanup()

    async def test_dispatch_receipt_upsert_should_replace_and_query(self) -> None:
        created = datetime(2026, 4, 13, 0, 0, tzinfo=timezone.utc)
        first = DispatchReceipt(
            dispatch_type="phase",
            job_id=8101,
            scope_id=1,
            session_id=11,
            trace_id="trace-8101",
            idempotency_key="idemp-8101",
            rubric_version="v3",
            judge_policy_version="jp-v3",
            topic_domain="default",
            retrieval_profile="hybrid_v1",
            phase_no=1,
            phase_start_no=None,
            phase_end_no=None,
            message_start_id=10,
            message_end_id=20,
            message_count=11,
            status="queued",
            request={"jobId": 8101},
            response=None,
            created_at=created,
            updated_at=created,
        )
        await self._repo.upsert_dispatch_receipt(receipt=first)

        second = DispatchReceipt(
            dispatch_type="phase",
            job_id=8101,
            scope_id=1,
            session_id=11,
            trace_id="trace-8101",
            idempotency_key="idemp-8101",
            rubric_version="v3",
            judge_policy_version="jp-v3",
            topic_domain="default",
            retrieval_profile="hybrid_v1",
            phase_no=1,
            phase_start_no=None,
            phase_end_no=None,
            message_start_id=10,
            message_end_id=20,
            message_count=11,
            status="completed",
            request={"jobId": 8101},
            response={"winner": "pro"},
            created_at=created,
            updated_at=datetime(2026, 4, 13, 0, 5, tzinfo=timezone.utc),
        )
        await self._repo.upsert_dispatch_receipt(receipt=second)

        row = await self._repo.get_dispatch_receipt(dispatch_type="phase", job_id=8101)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row.status, "completed")
        self.assertEqual(row.response, {"winner": "pro"})

        completed_rows = await self._repo.list_dispatch_receipts(
            dispatch_type="phase",
            session_id=11,
            status="completed",
            limit=10,
        )
        self.assertEqual(len(completed_rows), 1)

    async def test_replay_records_should_append_and_filter(self) -> None:
        first = await self._repo.append_replay_record(
            dispatch_type="final",
            job_id=8201,
            trace_id="trace-8201",
            winner="draw",
            needs_draw_vote=True,
            provider="mock",
            report_payload={"winner": "draw"},
        )
        second = await self._repo.append_replay_record(
            dispatch_type="phase",
            job_id=8202,
            trace_id="trace-8202",
            winner="pro",
            needs_draw_vote=False,
            provider="openai",
            report_payload={"winner": "pro"},
        )

        rows = await self._repo.list_replay_records(limit=10)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].job_id, second.job_id)
        self.assertEqual(rows[1].job_id, first.job_id)

        phase_rows = await self._repo.list_replay_records(dispatch_type="phase", job_id=8202)
        self.assertEqual(len(phase_rows), 1)
        self.assertEqual(phase_rows[0].winner, "pro")

    async def test_audit_alert_should_dedupe_and_transition_status(self) -> None:
        alert = await self._repo.upsert_audit_alert(
            job_id=8301,
            scope_id=3,
            trace_id="trace-8301",
            alert_type="callback_failed",
            severity="critical",
            title="callback failed",
            message="phase callback timeout",
            details={"errorCode": "callback_timeout"},
        )
        deduped = await self._repo.upsert_audit_alert(
            job_id=8301,
            scope_id=3,
            trace_id="trace-8301-b",
            alert_type="callback_failed",
            severity="critical",
            title="callback failed",
            message="phase callback timeout",
            details={"errorCode": "callback_timeout"},
        )
        self.assertEqual(alert.alert_id, deduped.alert_id)

        alerts = await self._repo.list_audit_alerts(job_id=8301, limit=10)
        self.assertEqual(len(alerts), 1)

        acked = await self._repo.transition_audit_alert(alert_id=alert.alert_id, to_status="acked")
        self.assertIsNotNone(acked)
        assert acked is not None
        self.assertEqual(acked.status, "acked")
        self.assertIsNotNone(acked.acknowledged_at)

        resolved = await self._repo.transition_audit_alert(
            alert_id=alert.alert_id,
            to_status="resolved",
        )
        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertEqual(resolved.status, "resolved")
        self.assertIsNotNone(resolved.resolved_at)

        invalid = await self._repo.transition_audit_alert(
            alert_id=alert.alert_id,
            to_status="raised",
        )
        self.assertIsNone(invalid)


if __name__ == "__main__":
    unittest.main()
