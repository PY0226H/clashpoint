from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import secrets
from time import perf_counter
from typing import Any

from .trace_store import (
    ALERT_STATUS_RAISED,
    IDEMPOTENCY_RESOLUTION_ACQUIRED,
    IDEMPOTENCY_RESOLUTION_CONFLICT,
    IDEMPOTENCY_RESOLUTION_REPLAY,
    OUTBOX_DELIVERY_FAILED,
    OUTBOX_DELIVERY_PENDING,
    OUTBOX_DELIVERY_SENT,
    TraceStoreProtocol,
)


@dataclass(frozen=True)
class B3GateThresholds:
    max_pending_race_p95_ms: float = 200.0
    max_replay_race_p95_ms: float = 200.0
    max_outbox_race_p95_ms: float = 200.0


@dataclass(frozen=True)
class B3IdempotencyRaceResult:
    total_requests: int
    concurrency: int
    acquired: int
    replay: int
    conflict: int
    errors: int
    p50_latency_ms: float
    p95_latency_ms: float
    max_latency_ms: float


@dataclass(frozen=True)
class B3OutboxRaceResult:
    total_updates: int
    concurrency: int
    sent_updates: int
    failed_updates: int
    errors: int
    final_delivery_status: str | None
    pending_rows: int
    sent_rows: int
    failed_rows: int
    p50_latency_ms: float
    p95_latency_ms: float
    max_latency_ms: float


@dataclass(frozen=True)
class B3GateRunResult:
    generated_at: datetime
    pending_race: B3IdempotencyRaceResult
    replay_race: B3IdempotencyRaceResult
    outbox_race: B3OutboxRaceResult
    passed: bool
    failure_reasons: list[str]
    mode: str


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if p <= 0:
        return min(values)
    if p >= 100:
        return max(values)
    sorted_values = sorted(values)
    rank = max(0, min(len(sorted_values) - 1, int(round((p / 100.0) * len(sorted_values) + 0.5)) - 1))
    return float(sorted_values[rank])


def _normalize_report_mode(mode: str) -> str:
    token = (mode or "").strip().lower()
    if not token:
        return "unknown"
    out: list[str] = []
    for char in token:
        if char.isalnum() or char in ("-", "_"):
            out.append(char)
        else:
            out.append("-")
    return "".join(out).strip("-") or "unknown"


def build_default_report_path(
    *,
    report_dir: Path,
    report_prefix: str,
    mode: str,
    now: datetime | None = None,
) -> Path:
    ts = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    mode_token = _normalize_report_mode(mode)
    filename = f"{report_prefix}-{mode_token}-{ts}.md"
    return report_dir / filename


def prune_report_files(
    *,
    report_dir: Path,
    report_prefix: str,
    max_files: int,
    max_days: int,
    now: datetime | None = None,
    keep_filenames: set[str] | None = None,
) -> list[Path]:
    if not report_dir.exists():
        return []
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    keep = keep_filenames or set()
    candidates = sorted(
        report_dir.glob(f"{report_prefix}-*.md"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    removed: list[Path] = []
    max_keep = max(0, int(max_files))
    max_age_days = max(0, int(max_days))
    age_cutoff = current - timedelta(days=max_age_days) if max_age_days > 0 else None
    for index, path in enumerate(candidates):
        if path.name in keep:
            continue
        by_count = max_keep > 0 and index >= max_keep
        by_age = False
        if age_cutoff is not None:
            modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            by_age = modified < age_cutoff
        if not by_count and not by_age:
            continue
        try:
            path.unlink()
            removed.append(path)
        except Exception:
            continue
    return removed


def write_report_with_collision_retry(
    *,
    report_path: Path,
    content: str,
    max_collision_retries: int = 8,
) -> Path:
    base_name = report_path.stem
    suffix = report_path.suffix
    attempts = max(0, int(max_collision_retries))
    for index in range(attempts + 1):
        if index == 0:
            candidate = report_path
        else:
            candidate = report_path.with_name(f"{base_name}-{secrets.token_hex(3)}{suffix}")
        try:
            with candidate.open("x", encoding="utf-8") as handle:
                handle.write(content)
            return candidate
        except FileExistsError:
            continue
    raise RuntimeError("failed to allocate unique report path after collision retries")


def _run_concurrent(total_requests: int, concurrency: int, fn: Any) -> tuple[list[Any], list[float]]:
    if total_requests < 1:
        raise ValueError("total_requests must be >= 1")
    if concurrency < 1:
        raise ValueError("concurrency must be >= 1")
    results: list[Any] = []
    latencies: list[float] = []
    def _measure(index: int) -> tuple[Any, float]:
        started = perf_counter()
        value = fn(index)
        elapsed_ms = (perf_counter() - started) * 1000.0
        return value, elapsed_ms

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(_measure, index) for index in range(total_requests)]
        for future in futures:
            value, elapsed_ms = future.result()
            results.append(value)
            latencies.append(elapsed_ms)
    return results, latencies


def run_idempotency_race(
    *,
    store: TraceStoreProtocol,
    key: str,
    job_id: int,
    total_requests: int,
    concurrency: int,
) -> B3IdempotencyRaceResult:
    def _worker(_: int) -> str:
        try:
            resolved = store.resolve_idempotency(key=key, job_id=job_id)
            return str(resolved.status or "").strip().lower()
        except Exception:
            return "error"

    statuses, latencies = _run_concurrent(total_requests, concurrency, _worker)
    acquired = sum(1 for status in statuses if status == IDEMPOTENCY_RESOLUTION_ACQUIRED)
    replay = sum(1 for status in statuses if status == IDEMPOTENCY_RESOLUTION_REPLAY)
    conflict = sum(1 for status in statuses if status == IDEMPOTENCY_RESOLUTION_CONFLICT)
    errors = len(statuses) - acquired - replay - conflict
    return B3IdempotencyRaceResult(
        total_requests=total_requests,
        concurrency=concurrency,
        acquired=acquired,
        replay=replay,
        conflict=conflict,
        errors=errors,
        p50_latency_ms=round(percentile(latencies, 50), 2),
        p95_latency_ms=round(percentile(latencies, 95), 2),
        max_latency_ms=round(max(latencies) if latencies else 0.0, 2),
    )


def run_outbox_delivery_race(
    *,
    store: TraceStoreProtocol,
    job_id: int,
    scope_id: int,
    trace_id: str,
    total_updates: int,
    concurrency: int,
) -> B3OutboxRaceResult:
    alert = store.upsert_audit_alert(
        job_id=job_id,
        scope_id=scope_id,
        trace_id=trace_id,
        alert_type="consistency_race",
        severity="warning",
        title="B3 Consistency Gate",
        message="outbox delivery race",
        details={"source": "b3_consistency_gate"},
    )
    if alert.status != ALERT_STATUS_RAISED:
        raise RuntimeError("unexpected initial alert status")
    pending_rows = store.list_alert_outbox(delivery_status=OUTBOX_DELIVERY_PENDING, limit=10)
    if not pending_rows:
        raise RuntimeError("outbox event not generated")
    event_id = pending_rows[0].event_id

    def _worker(index: int) -> tuple[str, bool]:
        delivery_status = OUTBOX_DELIVERY_SENT if index % 2 == 0 else OUTBOX_DELIVERY_FAILED
        error_message = None if delivery_status == OUTBOX_DELIVERY_SENT else "delivery_failed_for_race"
        item = store.mark_alert_outbox_delivery(
            event_id=event_id,
            delivery_status=delivery_status,
            error_message=error_message,
        )
        return delivery_status, item is not None

    updates, latencies = _run_concurrent(total_updates, concurrency, _worker)
    sent_updates = sum(1 for status, ok in updates if ok and status == OUTBOX_DELIVERY_SENT)
    failed_updates = sum(1 for status, ok in updates if ok and status == OUTBOX_DELIVERY_FAILED)
    errors = sum(1 for _, ok in updates if not ok)

    all_rows = store.list_alert_outbox(limit=20)
    target = next((row for row in all_rows if row.event_id == event_id), None)
    pending_after = store.list_alert_outbox(delivery_status=OUTBOX_DELIVERY_PENDING, limit=20)
    sent_after = store.list_alert_outbox(delivery_status=OUTBOX_DELIVERY_SENT, limit=20)
    failed_after = store.list_alert_outbox(delivery_status=OUTBOX_DELIVERY_FAILED, limit=20)
    return B3OutboxRaceResult(
        total_updates=total_updates,
        concurrency=concurrency,
        sent_updates=sent_updates,
        failed_updates=failed_updates,
        errors=errors,
        final_delivery_status=target.delivery_status if target is not None else None,
        pending_rows=len(pending_after),
        sent_rows=len(sent_after),
        failed_rows=len(failed_after),
        p50_latency_ms=round(percentile(latencies, 50), 2),
        p95_latency_ms=round(percentile(latencies, 95), 2),
        max_latency_ms=round(max(latencies) if latencies else 0.0, 2),
    )


def evaluate_b3_gate(
    *,
    pending_race: B3IdempotencyRaceResult,
    replay_race: B3IdempotencyRaceResult,
    outbox_race: B3OutboxRaceResult,
    thresholds: B3GateThresholds,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if pending_race.errors != 0:
        reasons.append(f"pending race errors={pending_race.errors}")
    if pending_race.acquired != 1:
        reasons.append(f"pending race acquired={pending_race.acquired}, expected=1")
    if pending_race.conflict + pending_race.acquired != pending_race.total_requests:
        reasons.append("pending race status accounting mismatch")
    if pending_race.p95_latency_ms > thresholds.max_pending_race_p95_ms:
        reasons.append(
            f"pending race p95={pending_race.p95_latency_ms:.2f}ms > {thresholds.max_pending_race_p95_ms:.2f}ms"
        )

    if replay_race.errors != 0:
        reasons.append(f"replay race errors={replay_race.errors}")
    if replay_race.replay != replay_race.total_requests:
        reasons.append(
            f"replay race replay={replay_race.replay}, expected={replay_race.total_requests}"
        )
    if replay_race.p95_latency_ms > thresholds.max_replay_race_p95_ms:
        reasons.append(
            f"replay race p95={replay_race.p95_latency_ms:.2f}ms > {thresholds.max_replay_race_p95_ms:.2f}ms"
        )

    if outbox_race.errors != 0:
        reasons.append(f"outbox race errors={outbox_race.errors}")
    if outbox_race.final_delivery_status not in {OUTBOX_DELIVERY_SENT, OUTBOX_DELIVERY_FAILED}:
        reasons.append(f"outbox final delivery status invalid: {outbox_race.final_delivery_status}")
    if outbox_race.p95_latency_ms > thresholds.max_outbox_race_p95_ms:
        reasons.append(
            f"outbox race p95={outbox_race.p95_latency_ms:.2f}ms > {thresholds.max_outbox_race_p95_ms:.2f}ms"
        )
    return len(reasons) == 0, reasons


def render_markdown_report(result: B3GateRunResult) -> str:
    pending = result.pending_race
    replay = result.replay_race
    outbox = result.outbox_race
    lines = [
        "# AI 裁判 B3 一致性专项验收报告",
        "",
        f"- 生成时间: {result.generated_at.isoformat()}",
        f"- 运行模式: `{result.mode}`",
        f"- 结论: {'PASS' if result.passed else 'FAIL'}",
        "",
        "## 幂等并发竞争（pending）",
        f"- 请求数/并发: {pending.total_requests}/{pending.concurrency}",
        f"- 状态计数: acquired={pending.acquired}, conflict={pending.conflict}, replay={pending.replay}, errors={pending.errors}",
        f"- 时延: p50={pending.p50_latency_ms}ms, p95={pending.p95_latency_ms}ms, max={pending.max_latency_ms}ms",
        "",
        "## 幂等重放竞争（success）",
        f"- 请求数/并发: {replay.total_requests}/{replay.concurrency}",
        f"- 状态计数: acquired={replay.acquired}, conflict={replay.conflict}, replay={replay.replay}, errors={replay.errors}",
        f"- 时延: p50={replay.p50_latency_ms}ms, p95={replay.p95_latency_ms}ms, max={replay.max_latency_ms}ms",
        "",
        "## Outbox 并发回写",
        f"- 更新数/并发: {outbox.total_updates}/{outbox.concurrency}",
        f"- 更新统计: sent={outbox.sent_updates}, failed={outbox.failed_updates}, errors={outbox.errors}",
        f"- 最终状态: {outbox.final_delivery_status}",
        f"- 可见性快照: pending={outbox.pending_rows}, sent={outbox.sent_rows}, failed={outbox.failed_rows}",
        f"- 时延: p50={outbox.p50_latency_ms}ms, p95={outbox.p95_latency_ms}ms, max={outbox.max_latency_ms}ms",
        "",
        "## 失败原因",
    ]
    if result.failure_reasons:
        for reason in result.failure_reasons:
            lines.append(f"- {reason}")
    else:
        lines.append("- 无")
    return "\n".join(lines).strip() + "\n"
