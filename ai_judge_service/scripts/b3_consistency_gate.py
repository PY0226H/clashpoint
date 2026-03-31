#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.b3_consistency_gate import (  # noqa: E402
    B3GateRunResult,
    B3GateThresholds,
    build_default_report_path,
    evaluate_b3_gate,
    prune_report_files,
    render_markdown_report,
    run_idempotency_race,
    run_outbox_delivery_race,
    write_report_with_collision_retry,
)
from app.trace_store import RedisTraceStore, TraceStore, TraceStoreProtocol  # noqa: E402

DEFAULT_REPORT_PREFIX = "AI裁判B3一致性验收报告"


class _EvalFailureRedisProxy:
    def __init__(self, client: Any) -> None:
        self._client = client

    def eval(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("lua disabled for fallback drill")

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def _build_store(mode: str, redis_url: str, key_prefix: str) -> tuple[TraceStoreProtocol, str]:
    if mode == "memory":
        return TraceStore(ttl_secs=3600), "memory"
    try:
        from redis import Redis

        client = Redis.from_url(redis_url)
        client.ping()
        return RedisTraceStore(redis_client=client, ttl_secs=3600, key_prefix=key_prefix), "redis"
    except Exception:
        if mode == "redis":
            raise
        return TraceStore(ttl_secs=3600), "memory"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run AI Judge B3 consistency gate.")
    parser.add_argument("--mode", choices=("auto", "memory", "redis"), default="auto")
    parser.add_argument("--redis-url", default="redis://127.0.0.1:6379/0")
    parser.add_argument("--pending-total-requests", type=int, default=100)
    parser.add_argument("--pending-concurrency", type=int, default=16)
    parser.add_argument("--replay-total-requests", type=int, default=100)
    parser.add_argument("--replay-concurrency", type=int, default=16)
    parser.add_argument("--outbox-total-updates", type=int, default=120)
    parser.add_argument("--outbox-concurrency", type=int, default=16)
    parser.add_argument("--max-pending-p95-ms", type=float, default=200.0)
    parser.add_argument("--max-replay-p95-ms", type=float, default=200.0)
    parser.add_argument("--max-outbox-p95-ms", type=float, default=200.0)
    parser.add_argument("--skip-lua-fallback-drill", action="store_true")
    parser.add_argument("--report-out", default="")
    parser.add_argument("--report-dir", default="")
    parser.add_argument("--report-prefix", default=DEFAULT_REPORT_PREFIX)
    parser.add_argument("--report-retention-max-files", type=int, default=60)
    parser.add_argument("--report-retention-max-days", type=int, default=30)
    parser.add_argument("--skip-report-prune", action="store_true")
    parser.add_argument("--report-collision-retries", type=int, default=8)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    mode = str(args.mode or "auto").strip().lower()
    key_prefix = f"ai_judge:b3_gate:{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    store, resolved_mode = _build_store(mode, str(args.redis_url), key_prefix)

    pending_key = f"{key_prefix}:pending"
    pending_job_id = 91001
    pending_race = run_idempotency_race(
        store=store,
        key=pending_key,
        job_id=pending_job_id,
        total_requests=args.pending_total_requests,
        concurrency=args.pending_concurrency,
    )

    replay_key = f"{key_prefix}:replay"
    replay_job_id = 91002
    store.resolve_idempotency(key=replay_key, job_id=replay_job_id)
    store.set_idempotency_success(
        key=replay_key,
        job_id=replay_job_id,
        response={"accepted": True, "jobId": replay_job_id},
    )
    replay_race = run_idempotency_race(
        store=store,
        key=replay_key,
        job_id=replay_job_id,
        total_requests=args.replay_total_requests,
        concurrency=args.replay_concurrency,
    )

    outbox_race = run_outbox_delivery_race(
        store=store,
        job_id=92001,
        scope_id=1,
        trace_id=f"{key_prefix}:trace",
        total_updates=args.outbox_total_updates,
        concurrency=args.outbox_concurrency,
    )

    failure_reasons: list[str] = []
    if resolved_mode == "redis" and not args.skip_lua_fallback_drill:
        proxy_store = RedisTraceStore(
            redis_client=_EvalFailureRedisProxy(store._redis),  # type: ignore[attr-defined]
            ttl_secs=3600,
            key_prefix=f"{key_prefix}:fallback",
        )
        fallback_race = run_idempotency_race(
            store=proxy_store,
            key=f"{key_prefix}:fallback:idem",
            job_id=93001,
            total_requests=max(10, int(args.pending_total_requests / 4)),
            concurrency=max(2, int(args.pending_concurrency / 2)),
        )
        if fallback_race.acquired != 1 or fallback_race.errors != 0:
            failure_reasons.append(
                "lua fallback drill failed: expected exactly one acquired and zero errors"
            )

    passed, reasons = evaluate_b3_gate(
        pending_race=pending_race,
        replay_race=replay_race,
        outbox_race=outbox_race,
        thresholds=B3GateThresholds(
            max_pending_race_p95_ms=args.max_pending_p95_ms,
            max_replay_race_p95_ms=args.max_replay_p95_ms,
            max_outbox_race_p95_ms=args.max_outbox_p95_ms,
        ),
    )
    all_reasons = reasons + failure_reasons
    if all_reasons:
        passed = False
    result = B3GateRunResult(
        generated_at=datetime.now(timezone.utc),
        pending_race=pending_race,
        replay_race=replay_race,
        outbox_race=outbox_race,
        passed=passed,
        failure_reasons=all_reasons,
        mode=resolved_mode,
    )

    if str(args.report_out or "").strip():
        report_path = Path(str(args.report_out)).resolve()
        report_dir = report_path.parent
    else:
        root = Path(__file__).resolve().parents[2]
        report_dir = (
            Path(str(args.report_dir)).resolve()
            if str(args.report_dir or "").strip()
            else root / "docs" / "consistency_reports"
        )
        report_path = build_default_report_path(
            report_dir=report_dir,
            report_prefix=str(args.report_prefix),
            mode=resolved_mode,
            now=result.generated_at,
        )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path = write_report_with_collision_retry(
        report_path=report_path,
        content=render_markdown_report(result),
        max_collision_retries=int(args.report_collision_retries),
    )
    removed: list[Path] = []
    if not bool(args.skip_report_prune):
        removed = prune_report_files(
            report_dir=report_dir,
            report_prefix=str(args.report_prefix),
            max_files=int(args.report_retention_max_files),
            max_days=int(args.report_retention_max_days),
            now=result.generated_at,
            keep_filenames={report_path.name},
        )

    print(f"[b3-consistency-gate] mode={resolved_mode}")
    print(f"[b3-consistency-gate] result={'PASS' if result.passed else 'FAIL'}")
    print(f"[b3-consistency-gate] report={report_path}")
    if removed:
        print(f"[b3-consistency-gate] pruned={len(removed)}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
