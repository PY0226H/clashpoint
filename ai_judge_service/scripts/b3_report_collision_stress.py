#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.b3_consistency_gate import build_default_report_path  # noqa: E402
from app.b3_report_collision_stress import (  # noqa: E402
    CollisionStressRun,
    parse_report_path,
    render_collision_stress_markdown,
    summarize_collision_runs,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run collision stress against B3 report output path."
    )
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--mode", choices=("memory", "auto", "redis"), default="memory")
    parser.add_argument("--report-dir", default="")
    parser.add_argument("--stress-report-out", default="")
    parser.add_argument("--collision-retries", type=int, default=8)
    parser.add_argument("--pending-total-requests", type=int, default=10)
    parser.add_argument("--pending-concurrency", type=int, default=2)
    parser.add_argument("--replay-total-requests", type=int, default=10)
    parser.add_argument("--replay-concurrency", type=int, default=2)
    parser.add_argument("--outbox-total-updates", type=int, default=12)
    parser.add_argument("--outbox-concurrency", type=int, default=2)
    return parser


def _run_worker(
    *,
    index: int,
    py_runner: Path,
    script_path: Path,
    report_out: Path,
    mode: str,
    collision_retries: int,
    pending_total_requests: int,
    pending_concurrency: int,
    replay_total_requests: int,
    replay_concurrency: int,
    outbox_total_updates: int,
    outbox_concurrency: int,
    key_prefix: str,
) -> CollisionStressRun:
    cmd = [
        str(py_runner),
        str(script_path),
        "--mode",
        mode,
        "--key-prefix",
        key_prefix,
        "--report-out",
        str(report_out),
        "--report-collision-retries",
        str(collision_retries),
        "--skip-report-prune",
        "--pending-total-requests",
        str(pending_total_requests),
        "--pending-concurrency",
        str(pending_concurrency),
        "--replay-total-requests",
        str(replay_total_requests),
        "--replay-concurrency",
        str(replay_concurrency),
        "--outbox-total-updates",
        str(outbox_total_updates),
        "--outbox-concurrency",
        str(outbox_concurrency),
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True)
    output = f"{completed.stdout}\n{completed.stderr}".strip()
    return CollisionStressRun(
        index=index,
        return_code=int(completed.returncode),
        report_path=parse_report_path(output),
        output=output,
    )


def main() -> int:
    args = build_parser().parse_args()
    workers = max(1, int(args.workers))
    workspace_root = Path(__file__).resolve().parents[2]
    report_dir = (
        Path(str(args.report_dir)).resolve()
        if str(args.report_dir or "").strip()
        else workspace_root / "docs" / "consistency_reports"
    )
    report_dir.mkdir(parents=True, exist_ok=True)
    stress_report_out = (
        Path(str(args.stress_report_out)).resolve()
        if str(args.stress_report_out or "").strip()
        else build_default_report_path(
            report_dir=report_dir,
            report_prefix="AI裁判B3报告冲突压测报告",
            mode=str(args.mode),
            now=datetime.now(timezone.utc),
        )
    )
    target_report_out = report_dir / "b3-collision-stress-target.md"
    gate_script = Path(__file__).resolve().parent / "b3_consistency_gate.py"
    py_runner = (workspace_root / "scripts" / "py").resolve()
    run_prefix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")

    runs: list[CollisionStressRun] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(
                _run_worker,
                index=index,
                py_runner=py_runner,
                script_path=gate_script,
                report_out=target_report_out,
                mode=str(args.mode),
                collision_retries=int(args.collision_retries),
                pending_total_requests=int(args.pending_total_requests),
                pending_concurrency=int(args.pending_concurrency),
                replay_total_requests=int(args.replay_total_requests),
                replay_concurrency=int(args.replay_concurrency),
                outbox_total_updates=int(args.outbox_total_updates),
                outbox_concurrency=int(args.outbox_concurrency),
                key_prefix=f"ai_judge:b3_stress:{run_prefix}:worker:{index}",
            )
            for index in range(workers)
        ]
        for future in futures:
            runs.append(future.result())

    summary = summarize_collision_runs(workers=workers, runs=runs, now=datetime.now(timezone.utc))
    stress_report_out.parent.mkdir(parents=True, exist_ok=True)
    stress_report_out.write_text(render_collision_stress_markdown(summary), encoding="utf-8")

    print(f"[b3-report-collision-stress] workers={workers} mode={args.mode}")
    print(
        f"[b3-report-collision-stress] passed={'true' if summary.passed else 'false'} "
        f"succeeded={summary.succeeded_workers} failed={summary.failed_workers}"
    )
    print(
        f"[b3-report-collision-stress] unique_report_paths={summary.unique_report_paths} "
        f"duplicates={summary.duplicated_report_paths} missing={summary.missing_report_path_workers}"
    )
    print(f"[b3-report-collision-stress] report={stress_report_out}")
    return 0 if summary.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
