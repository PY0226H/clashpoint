#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.consistency_report_archive import archive_consistency_reports  # noqa: E402

DEFAULT_REPORT_PREFIX = "AI裁判B3一致性验收报告"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Archive old consistency reports into monthly folders."
    )
    parser.add_argument("--report-dir", default="")
    parser.add_argument("--archive-dir", default="")
    parser.add_argument("--report-prefix", default=DEFAULT_REPORT_PREFIX)
    parser.add_argument("--keep-days-in-root", type=int, default=14)
    parser.add_argument("--max-collision-retries", type=int, default=8)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    workspace_root = Path(__file__).resolve().parents[2]
    report_dir = (
        Path(str(args.report_dir)).resolve()
        if str(args.report_dir or "").strip()
        else workspace_root / "docs" / "consistency_reports"
    )
    archive_dir = (
        Path(str(args.archive_dir)).resolve()
        if str(args.archive_dir or "").strip()
        else report_dir / "archive"
    )

    result = archive_consistency_reports(
        report_dir=report_dir,
        archive_dir=archive_dir,
        report_prefix=str(args.report_prefix),
        keep_days_in_root=int(args.keep_days_in_root),
        now=datetime.now(timezone.utc),
        dry_run=bool(args.dry_run),
        max_collision_retries=int(args.max_collision_retries),
    )

    print(
        f"[consistency-reports-archive] report_dir={report_dir} "
        f"archive_dir={archive_dir} keep_days_in_root={int(args.keep_days_in_root)}"
    )
    print(
        f"[consistency-reports-archive] scanned={result.scanned} eligible={result.eligible} "
        f"moved={result.moved} dry_run={'true' if result.dry_run else 'false'}"
    )
    for action in result.actions:
        print(f"[consistency-reports-archive] move {action.source} -> {action.destination}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
