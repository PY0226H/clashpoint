from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from app.consistency_report_archive import (
    _extract_report_timestamp,
    archive_consistency_reports,
)


class ConsistencyReportArchiveTests(unittest.TestCase):
    def test_extract_report_timestamp_should_support_mode_with_utc_stamp(self) -> None:
        ts = _extract_report_timestamp(
            "AI裁判B3一致性验收报告-redis-20260331-120030Z.md",
            "AI裁判B3一致性验收报告",
        )
        self.assertEqual(ts, datetime(2026, 3, 31, 12, 0, 30, tzinfo=timezone.utc))

    def test_extract_report_timestamp_should_support_legacy_daily_name(self) -> None:
        ts = _extract_report_timestamp(
            "AI裁判B3一致性验收报告-redis-2026-03-31.md",
            "AI裁判B3一致性验收报告",
        )
        self.assertEqual(ts, datetime(2026, 3, 31, 0, 0, 0, tzinfo=timezone.utc))

    def test_archive_consistency_reports_should_move_only_older_files(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            report_dir = root / "reports"
            archive_dir = root / "archive"
            report_dir.mkdir(parents=True, exist_ok=True)
            recent = report_dir / "AI裁判B3一致性验收报告-memory-20260331-120000Z.md"
            old = report_dir / "AI裁判B3一致性验收报告-memory-20260301-120000Z.md"
            recent.write_text("recent", encoding="utf-8")
            old.write_text("old", encoding="utf-8")
            now = datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc)
            os.utime(recent, (now.timestamp(), now.timestamp()))
            old_time = (now - timedelta(days=30)).timestamp()
            os.utime(old, (old_time, old_time))

            result = archive_consistency_reports(
                report_dir=report_dir,
                archive_dir=archive_dir,
                report_prefix="AI裁判B3一致性验收报告",
                keep_days_in_root=14,
                now=now,
            )
            self.assertEqual(result.scanned, 2)
            self.assertEqual(result.eligible, 1)
            self.assertEqual(result.moved, 1)
            self.assertTrue(recent.exists())
            self.assertFalse(old.exists())
            archived = archive_dir / "2026-03" / old.name
            self.assertTrue(archived.exists())
            self.assertEqual(archived.read_text(encoding="utf-8"), "old")

    def test_archive_consistency_reports_should_dry_run_without_moving(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            report_dir = root / "reports"
            archive_dir = root / "archive"
            report_dir.mkdir(parents=True, exist_ok=True)
            old = report_dir / "AI裁判B3一致性验收报告-memory-20260301-120000Z.md"
            old.write_text("old", encoding="utf-8")
            now = datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc)

            result = archive_consistency_reports(
                report_dir=report_dir,
                archive_dir=archive_dir,
                report_prefix="AI裁判B3一致性验收报告",
                keep_days_in_root=1,
                now=now,
                dry_run=True,
            )
            self.assertEqual(result.eligible, 1)
            self.assertEqual(result.moved, 1)
            self.assertTrue(old.exists())
            self.assertFalse((archive_dir / "2026-03" / old.name).exists())

    def test_archive_consistency_reports_should_append_dup_suffix_on_collision(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            report_dir = root / "reports"
            archive_dir = root / "archive"
            report_dir.mkdir(parents=True, exist_ok=True)
            target_name = "AI裁判B3一致性验收报告-memory-20260301-120000Z.md"
            old = report_dir / target_name
            old.write_text("old", encoding="utf-8")
            month_dir = archive_dir / "2026-03"
            month_dir.mkdir(parents=True, exist_ok=True)
            existing = month_dir / target_name
            existing.write_text("existing", encoding="utf-8")
            now = datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc)

            with patch(
                "app.consistency_report_archive.secrets.token_hex",
                side_effect=["a1b2c3"],
            ):
                result = archive_consistency_reports(
                    report_dir=report_dir,
                    archive_dir=archive_dir,
                    report_prefix="AI裁判B3一致性验收报告",
                    keep_days_in_root=14,
                    now=now,
                    max_collision_retries=3,
                )

            self.assertEqual(result.moved, 1)
            archived = month_dir / "AI裁判B3一致性验收报告-memory-20260301-120000Z-dup-a1b2c3.md"
            self.assertTrue(archived.exists())
            self.assertEqual(archived.read_text(encoding="utf-8"), "old")
            self.assertEqual(existing.read_text(encoding="utf-8"), "existing")


if __name__ == "__main__":
    unittest.main()
