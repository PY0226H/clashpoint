import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from app.b3_consistency_gate import (
    B3GateThresholds,
    B3IdempotencyRaceResult,
    B3OutboxRaceResult,
    build_default_report_path,
    evaluate_b3_gate,
    percentile,
    prune_report_files,
    run_idempotency_race,
    run_outbox_delivery_race,
    write_report_with_collision_retry,
)
from app.trace_store import OUTBOX_DELIVERY_FAILED, OUTBOX_DELIVERY_SENT, TraceStore


class B3ConsistencyGateTests(unittest.TestCase):
    def test_percentile_should_handle_empty_and_boundaries(self) -> None:
        self.assertEqual(percentile([], 95), 0.0)
        self.assertEqual(percentile([3, 1, 9], 0), 1.0)
        self.assertEqual(percentile([3, 1, 9], 100), 9.0)

    def test_run_idempotency_race_should_have_single_acquired_before_success(self) -> None:
        store = TraceStore(ttl_secs=3600)
        result = run_idempotency_race(
            store=store,
            key="b3:idem:pending",
            job_id=7001,
            total_requests=32,
            concurrency=8,
        )
        self.assertEqual(result.acquired, 1)
        self.assertEqual(result.replay, 0)
        self.assertEqual(result.conflict, 31)
        self.assertEqual(result.errors, 0)

    def test_run_idempotency_race_should_return_all_replay_after_success(self) -> None:
        store = TraceStore(ttl_secs=3600)
        store.resolve_idempotency(key="b3:idem:replay", job_id=7002)
        store.set_idempotency_success(
            key="b3:idem:replay",
            job_id=7002,
            response={"accepted": True, "jobId": 7002},
        )
        result = run_idempotency_race(
            store=store,
            key="b3:idem:replay",
            job_id=7002,
            total_requests=24,
            concurrency=6,
        )
        self.assertEqual(result.replay, 24)
        self.assertEqual(result.errors, 0)

    def test_run_outbox_delivery_race_should_keep_event_visible(self) -> None:
        store = TraceStore(ttl_secs=3600)
        result = run_outbox_delivery_race(
            store=store,
            job_id=8001,
            scope_id=1,
            trace_id="b3:trace:8001",
            total_updates=40,
            concurrency=8,
        )
        self.assertEqual(result.errors, 0)
        self.assertIn(result.final_delivery_status, {OUTBOX_DELIVERY_SENT, OUTBOX_DELIVERY_FAILED})
        self.assertGreaterEqual(result.sent_updates + result.failed_updates, 40)

    def test_evaluate_b3_gate_should_fail_when_pending_race_is_invalid(self) -> None:
        pending = B3IdempotencyRaceResult(
            total_requests=10,
            concurrency=2,
            acquired=2,
            replay=0,
            conflict=8,
            errors=0,
            p50_latency_ms=1.0,
            p95_latency_ms=2.0,
            max_latency_ms=3.0,
        )
        replay = B3IdempotencyRaceResult(
            total_requests=10,
            concurrency=2,
            acquired=0,
            replay=10,
            conflict=0,
            errors=0,
            p50_latency_ms=1.0,
            p95_latency_ms=2.0,
            max_latency_ms=3.0,
        )
        outbox = B3OutboxRaceResult(
            total_updates=10,
            concurrency=2,
            sent_updates=6,
            failed_updates=4,
            errors=0,
            final_delivery_status=OUTBOX_DELIVERY_SENT,
            pending_rows=0,
            sent_rows=1,
            failed_rows=0,
            p50_latency_ms=1.0,
            p95_latency_ms=2.0,
            max_latency_ms=3.0,
        )
        passed, reasons = evaluate_b3_gate(
            pending_race=pending,
            replay_race=replay,
            outbox_race=outbox,
            thresholds=B3GateThresholds(),
        )
        self.assertFalse(passed)
        self.assertTrue(any("pending race acquired" in reason for reason in reasons))

    def test_build_default_report_path_should_include_mode_and_timestamp(self) -> None:
        now = datetime(2026, 3, 31, 11, 22, 33, tzinfo=timezone.utc)
        report = build_default_report_path(
            report_dir=Path("/tmp/consistency"),
            report_prefix="AI裁判B3一致性验收报告",
            mode="redis",
            now=now,
        )
        self.assertEqual(
            str(report), "/tmp/consistency/AI裁判B3一致性验收报告-redis-20260331-112233Z.md"
        )

    def test_prune_report_files_should_apply_age_and_count(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            prefix = "AI裁判B3一致性验收报告"
            base = datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc)
            files = [
                root / f"{prefix}-memory-20260331-120000Z.md",
                root / f"{prefix}-memory-20260330-120000Z.md",
                root / f"{prefix}-memory-20260320-120000Z.md",
            ]
            for index, path in enumerate(files):
                path.write_text("report", encoding="utf-8")
                modified = (base - timedelta(days=index * 5)).timestamp()
                path.touch()
                path.chmod(0o644)
                # Keep deterministic sort by mtime.
                os.utime(path, (modified, modified))

            removed = prune_report_files(
                report_dir=root,
                report_prefix=prefix,
                max_files=2,
                max_days=7,
                now=base,
                keep_filenames={files[0].name},
            )
            removed_names = {path.name for path in removed}
            self.assertIn(files[2].name, removed_names)
            self.assertNotIn(files[0].name, removed_names)
            self.assertTrue(files[0].exists())
            self.assertTrue(files[1].exists())
            self.assertFalse(files[2].exists())

    def test_write_report_with_collision_retry_should_append_random_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            base = root / "AI裁判B3一致性验收报告-redis-20260331-120000Z.md"
            base.write_text("existing", encoding="utf-8")
            collide = root / "AI裁判B3一致性验收报告-redis-20260331-120000Z-aaaaaa.md"
            collide.write_text("existing", encoding="utf-8")
            with patch(
                "app.b3_consistency_gate.secrets.token_hex", side_effect=["aaaaaa", "bbbbbb"]
            ):
                resolved = write_report_with_collision_retry(
                    report_path=base,
                    content="new-report",
                    max_collision_retries=3,
                )
            self.assertEqual(
                resolved.name,
                "AI裁判B3一致性验收报告-redis-20260331-120000Z-bbbbbb.md",
            )
            self.assertEqual(resolved.read_text(encoding="utf-8"), "new-report")


if __name__ == "__main__":
    unittest.main()
