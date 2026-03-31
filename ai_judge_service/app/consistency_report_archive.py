from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import secrets
import shutil


@dataclass(frozen=True)
class ReportArchiveAction:
    source: Path
    destination: Path
    reference_time: datetime


@dataclass(frozen=True)
class ReportArchiveResult:
    scanned: int
    eligible: int
    moved: int
    dry_run: bool
    actions: list[ReportArchiveAction]


def _extract_report_timestamp(filename: str, report_prefix: str) -> datetime | None:
    mode_ts_pattern = re.compile(
        rf"^{re.escape(report_prefix)}-[A-Za-z0-9_-]+-(\d{{8}}-\d{{6}}Z)(?:-[A-Za-z0-9_-]+)?\.md$"
    )
    legacy_date_pattern = re.compile(
        rf"^{re.escape(report_prefix)}(?:-[A-Za-z0-9_-]+)?-(\d{{4}}-\d{{2}}-\d{{2}})\.md$"
    )
    matched = mode_ts_pattern.match(filename)
    if matched:
        try:
            return datetime.strptime(matched.group(1), "%Y%m%d-%H%M%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    matched = legacy_date_pattern.match(filename)
    if not matched:
        return None
    try:
        return datetime.strptime(matched.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _resolve_archive_destination(path: Path, max_collision_retries: int) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    retries = max(0, int(max_collision_retries))
    for _ in range(retries):
        candidate = path.with_name(f"{stem}-dup-{secrets.token_hex(3)}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"failed to allocate archive destination for {path.name}")


def archive_consistency_reports(
    *,
    report_dir: Path,
    archive_dir: Path,
    report_prefix: str,
    keep_days_in_root: int,
    now: datetime | None = None,
    dry_run: bool = False,
    max_collision_retries: int = 8,
) -> ReportArchiveResult:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = current - timedelta(days=max(0, int(keep_days_in_root)))
    candidates = sorted(
        [path for path in report_dir.glob(f"{report_prefix}-*.md") if path.is_file()],
        key=lambda path: path.stat().st_mtime,
    )

    actions: list[ReportArchiveAction] = []
    for source in candidates:
        reference_time = _extract_report_timestamp(source.name, report_prefix)
        if reference_time is None:
            reference_time = datetime.fromtimestamp(source.stat().st_mtime, tz=timezone.utc)
        if reference_time >= cutoff:
            continue
        month_dir = archive_dir / reference_time.strftime("%Y-%m")
        destination = _resolve_archive_destination(month_dir / source.name, max_collision_retries)
        actions.append(
            ReportArchiveAction(
                source=source,
                destination=destination,
                reference_time=reference_time,
            )
        )

    moved = 0
    if not dry_run:
        for action in actions:
            action.destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(action.source), str(action.destination))
            moved += 1

    return ReportArchiveResult(
        scanned=len(candidates),
        eligible=len(actions),
        moved=len(actions) if dry_run else moved,
        dry_run=bool(dry_run),
        actions=actions,
    )
