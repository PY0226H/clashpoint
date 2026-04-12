import unittest
from datetime import datetime, timezone

from app.b3_report_collision_stress import (
    CollisionStressRun,
    parse_report_path,
    summarize_collision_runs,
)


class B3ReportCollisionStressTests(unittest.TestCase):
    def test_parse_report_path_should_extract_value(self) -> None:
        output = "\n".join(
            [
                "[b3-consistency-gate] mode=memory",
                "[b3-consistency-gate] result=PASS",
                "[b3-consistency-gate] report=/tmp/a.md",
            ]
        )
        self.assertEqual(parse_report_path(output), "/tmp/a.md")

    def test_parse_report_path_should_return_none_when_missing(self) -> None:
        self.assertIsNone(parse_report_path("no report line"))

    def test_summarize_collision_runs_should_pass_when_all_paths_unique(self) -> None:
        runs = [
            CollisionStressRun(index=0, return_code=0, report_path="/tmp/a.md", output="ok"),
            CollisionStressRun(index=1, return_code=0, report_path="/tmp/b.md", output="ok"),
            CollisionStressRun(index=2, return_code=0, report_path="/tmp/c.md", output="ok"),
        ]
        summary = summarize_collision_runs(
            workers=3,
            runs=runs,
            now=datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc),
        )
        self.assertTrue(summary.passed)
        self.assertEqual(summary.failed_workers, 0)
        self.assertEqual(summary.unique_report_paths, 3)
        self.assertEqual(summary.duplicated_report_paths, 0)

    def test_summarize_collision_runs_should_fail_on_duplicate_or_missing(self) -> None:
        runs = [
            CollisionStressRun(index=0, return_code=0, report_path="/tmp/a.md", output="ok"),
            CollisionStressRun(index=1, return_code=0, report_path="/tmp/a.md", output="ok"),
            CollisionStressRun(index=2, return_code=1, report_path=None, output="fail"),
        ]
        summary = summarize_collision_runs(
            workers=3,
            runs=runs,
            now=datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc),
        )
        self.assertFalse(summary.passed)
        self.assertEqual(summary.failed_workers, 1)
        self.assertEqual(summary.missing_report_path_workers, 1)
        self.assertEqual(summary.duplicated_report_paths, 1)
        self.assertGreaterEqual(len(summary.failure_reasons), 2)


if __name__ == "__main__":
    unittest.main()
