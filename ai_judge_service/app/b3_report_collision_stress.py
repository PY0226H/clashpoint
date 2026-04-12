from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

REPORT_LINE_PATTERN = re.compile(r"^\[b3-consistency-gate\] report=(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class CollisionStressRun:
    index: int
    return_code: int
    report_path: str | None
    output: str


@dataclass(frozen=True)
class CollisionStressSummary:
    generated_at: datetime
    workers: int
    succeeded_workers: int
    failed_workers: int
    missing_report_path_workers: int
    unique_report_paths: int
    duplicated_report_paths: int
    passed: bool
    failure_reasons: list[str]
    runs: list[CollisionStressRun]


def parse_report_path(output: str) -> str | None:
    matched = REPORT_LINE_PATTERN.search(output or "")
    if not matched:
        return None
    return matched.group(1).strip() or None


def summarize_collision_runs(
    *,
    workers: int,
    runs: list[CollisionStressRun],
    now: datetime | None = None,
) -> CollisionStressSummary:
    resolved_workers = max(0, int(workers))
    succeeded = sum(1 for item in runs if item.return_code == 0)
    failed = len(runs) - succeeded
    report_paths = [item.report_path for item in runs if item.report_path]
    unique_count = len(set(report_paths))
    missing_paths = sum(1 for item in runs if not item.report_path)
    duplicated = len(report_paths) - unique_count
    reasons: list[str] = []
    if failed > 0:
        reasons.append(f"{failed} worker(s) returned non-zero status")
    if missing_paths > 0:
        reasons.append(f"{missing_paths} worker(s) did not expose report path")
    if unique_count != len(report_paths):
        reasons.append("duplicate report paths detected")
    if len(runs) != resolved_workers:
        reasons.append(f"expected {resolved_workers} runs, got {len(runs)}")
    passed = len(reasons) == 0
    return CollisionStressSummary(
        generated_at=(now or datetime.now(timezone.utc)).astimezone(timezone.utc),
        workers=resolved_workers,
        succeeded_workers=succeeded,
        failed_workers=failed,
        missing_report_path_workers=missing_paths,
        unique_report_paths=unique_count,
        duplicated_report_paths=max(0, duplicated),
        passed=passed,
        failure_reasons=reasons,
        runs=runs,
    )


def render_collision_stress_markdown(summary: CollisionStressSummary) -> str:
    status_line = "PASS" if summary.passed else "FAIL"
    lines = [
        "# B3 报告并发冲突压测报告",
        "",
        f"- generated_at_utc: `{summary.generated_at.isoformat()}`",
        f"- workers: `{summary.workers}`",
        f"- succeeded_workers: `{summary.succeeded_workers}`",
        f"- failed_workers: `{summary.failed_workers}`",
        f"- missing_report_path_workers: `{summary.missing_report_path_workers}`",
        f"- unique_report_paths: `{summary.unique_report_paths}`",
        f"- duplicated_report_paths: `{summary.duplicated_report_paths}`",
        f"- result: `{status_line}`",
    ]
    if summary.failure_reasons:
        lines.extend(["", "## 失败原因"])
        for reason in summary.failure_reasons:
            lines.append(f"- {reason}")
    lines.extend(["", "## Worker 明细"])
    for item in summary.runs:
        lines.append(
            f"- worker#{item.index}: return_code={item.return_code}, report={item.report_path or 'N/A'}"
        )
    return "\n".join(lines) + "\n"
