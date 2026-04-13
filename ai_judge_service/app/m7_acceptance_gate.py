from __future__ import annotations

import asyncio
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from httpx import ASGITransport, AsyncClient

from .app_factory import create_app, create_runtime
from .models import (
    PhaseDispatchMessage,
    PhaseDispatchRequest,
)
from .settings import Settings


@dataclass(frozen=True)
class GateThresholds:
    min_success_rate: float = 0.98
    max_p95_latency_ms: float = 5000.0


@dataclass(frozen=True)
class GateTestResult:
    module: str
    passed: bool
    duration_ms: float
    exit_code: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class GateLoadResult:
    total_requests: int
    succeeded: int
    failed: int
    success_rate: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    max_latency_ms: float


@dataclass(frozen=True)
class GateRunResult:
    generated_at: datetime
    tests: list[GateTestResult]
    load: GateLoadResult | None
    thresholds: GateThresholds
    passed: bool
    failure_reasons: list[str]


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if p <= 0:
        return min(values)
    if p >= 100:
        return max(values)
    sorted_values = sorted(values)
    rank = max(
        0, min(len(sorted_values) - 1, int(round((p / 100.0) * len(sorted_values) + 0.5)) - 1)
    )
    return float(sorted_values[rank])


def run_unittest_module(module: str, *, python_exec: str = sys.executable) -> GateTestResult:
    start = perf_counter()
    process = subprocess.run(
        [python_exec, "-m", "unittest", module, "-q"],
        capture_output=True,
        text=True,
        check=False,
    )
    duration_ms = (perf_counter() - start) * 1000.0
    return GateTestResult(
        module=module,
        passed=process.returncode == 0,
        duration_ms=round(duration_ms, 2),
        exit_code=process.returncode,
        stdout=process.stdout.strip(),
        stderr=process.stderr.strip(),
    )


def default_report_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    date_tag = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return root / "docs" / "dev_plan" / f"AI裁判M7验收报告-{date_tag}.md"


def _build_gate_settings(**overrides: object) -> Settings:
    base = {
        "ai_internal_key": "m7-gate-key",
        "chat_server_base_url": "http://chat",
        "phase_report_path_template": "/r/phase/{job_id}",
        "final_report_path_template": "/r/final/{job_id}",
        "phase_failed_path_template": "/f/phase/{job_id}",
        "final_failed_path_template": "/f/final/{job_id}",
        "callback_timeout_secs": 8.0,
        "process_delay_ms": 0,
        "judge_style_mode": "rational",
        "provider": "mock",
        "openai_api_key": "",
        "openai_model": "gpt-4.1-mini",
        "openai_base_url": "https://api.openai.com/v1",
        "openai_timeout_secs": 25.0,
        "openai_temperature": 0.1,
        "openai_max_retries": 2,
        "openai_fallback_to_mock": True,
        "rag_enabled": True,
        "rag_knowledge_file": "",
        "rag_max_snippets": 4,
        "rag_max_chars_per_snippet": 280,
        "rag_query_message_limit": 80,
        "rag_source_whitelist": ("https://teamfighttactics.leagueoflegends.com/en-us/news",),
        "rag_backend": "file",
        "rag_openai_embedding_model": "text-embedding-3-small",
        "rag_milvus_uri": "",
        "rag_milvus_token": "",
        "rag_milvus_db_name": "",
        "rag_milvus_collection": "",
        "rag_milvus_vector_field": "embedding",
        "rag_milvus_content_field": "content",
        "rag_milvus_title_field": "title",
        "rag_milvus_source_url_field": "source_url",
        "rag_milvus_chunk_id_field": "chunk_id",
        "rag_milvus_tags_field": "tags",
        "rag_milvus_metric_type": "COSINE",
        "rag_milvus_search_limit": 20,
        "stage_agent_max_chunks": 12,
        "reflection_enabled": True,
        "topic_memory_enabled": True,
        "rag_hybrid_enabled": True,
        "rag_rerank_enabled": True,
        "rag_rerank_engine": "heuristic",
        "reflection_policy": "winner_mismatch_only",
        "reflection_low_margin_threshold": 3,
        "fault_injection_nodes": (),
        "degrade_max_level": 3,
        "trace_ttl_secs": 86400,
        "idempotency_ttl_secs": 86400,
        "redis_enabled": False,
        "redis_required": False,
        "redis_url": "redis://127.0.0.1:6379/0",
        "redis_pool_size": 20,
        "redis_key_prefix": "ai_judge:v2",
        "topic_memory_limit": 5,
        "topic_memory_min_evidence_refs": 1,
        "topic_memory_min_rationale_chars": 20,
        "topic_memory_min_quality_score": 0.55,
        "runtime_retry_max_attempts": 2,
        "runtime_retry_backoff_ms": 200,
        "compliance_block_enabled": True,
    }
    base.update(overrides)
    return Settings(**base)


def _build_request(job_id: int) -> PhaseDispatchRequest:
    now = datetime.now(timezone.utc)
    return PhaseDispatchRequest(
        job_id=job_id,
        scope_id=1,
        session_id=2,
        phase_no=1,
        message_start_id=1,
        message_end_id=1,
        message_count=1,
        messages=[
            PhaseDispatchMessage(
                message_id=1,
                speaker_tag="pro_1",
                side="pro",
                content=f"message-{job_id}",
                created_at=now,
            )
        ],
        rubric_version="v3",
        judge_policy_version="v3-default",
        topic_domain="default",
        retrieval_profile="hybrid_v1",
        trace_id=f"m7-phase-{job_id}",
        idempotency_key=f"m7:phase:{job_id}",
    )


async def run_inprocess_dispatch_load(
    *,
    total_requests: int,
    concurrency: int,
    settings: Settings | None = None,
) -> GateLoadResult:
    if total_requests < 1:
        raise ValueError("total_requests must be >= 1")
    if concurrency < 1:
        raise ValueError("concurrency must be >= 1")

    async def _noop_callback_report(*, cfg: object, job_id: int, payload: dict) -> None:
        return None

    runtime = create_runtime(
        settings=settings or _build_gate_settings(),
        callback_phase_report_impl=_noop_callback_report,
        callback_final_report_impl=_noop_callback_report,
        callback_phase_failed_impl=_noop_callback_report,
        callback_final_failed_impl=_noop_callback_report,
    )
    app = create_app(runtime)
    semaphore = asyncio.Semaphore(concurrency)

    latencies: list[float] = []
    succeeded = 0
    failed = 0

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        async def _run_one(job_id: int) -> None:
            nonlocal succeeded, failed
            async with semaphore:
                started = perf_counter()
                try:
                    payload = _build_request(job_id).model_dump(mode="json")
                    resp = await client.post(
                        "/internal/judge/v3/phase/dispatch",
                        json=payload,
                        headers={"x-ai-internal-key": runtime.settings.ai_internal_key},
                    )
                    if resp.status_code == 200 and bool(resp.json().get("accepted")):
                        succeeded += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1
                finally:
                    latencies.append((perf_counter() - started) * 1000.0)

        tasks = [asyncio.create_task(_run_one(i + 1)) for i in range(total_requests)]
        await asyncio.gather(*tasks)

    success_rate = succeeded / float(total_requests)
    return GateLoadResult(
        total_requests=total_requests,
        succeeded=succeeded,
        failed=failed,
        success_rate=round(success_rate, 4),
        p50_latency_ms=round(percentile(latencies, 50), 2),
        p95_latency_ms=round(percentile(latencies, 95), 2),
        p99_latency_ms=round(percentile(latencies, 99), 2),
        max_latency_ms=round(max(latencies) if latencies else 0.0, 2),
    )


def evaluate_load_gate(load: GateLoadResult, thresholds: GateThresholds) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if load.success_rate < thresholds.min_success_rate:
        reasons.append(
            f"load success_rate {load.success_rate:.4f} < threshold {thresholds.min_success_rate:.4f}"
        )
    if load.p95_latency_ms > thresholds.max_p95_latency_ms:
        reasons.append(
            f"load p95_latency_ms {load.p95_latency_ms:.2f} > threshold {thresholds.max_p95_latency_ms:.2f}"
        )
    return len(reasons) == 0, reasons


async def run_gate(
    *,
    test_modules: list[str],
    run_tests: bool,
    run_load: bool,
    python_exec: str,
    load_total_requests: int,
    load_concurrency: int,
    thresholds: GateThresholds,
) -> GateRunResult:
    test_results: list[GateTestResult] = []
    failure_reasons: list[str] = []

    if run_tests:
        for module in test_modules:
            result = run_unittest_module(module=module, python_exec=python_exec)
            test_results.append(result)
            if not result.passed:
                failure_reasons.append(f"test module failed: {module}")

    load_result: GateLoadResult | None = None
    if run_load:
        load_result = await run_inprocess_dispatch_load(
            total_requests=load_total_requests,
            concurrency=load_concurrency,
        )
        load_passed, load_reasons = evaluate_load_gate(load_result, thresholds)
        if not load_passed:
            failure_reasons.extend(load_reasons)

    return GateRunResult(
        generated_at=datetime.now(timezone.utc),
        tests=test_results,
        load=load_result,
        thresholds=thresholds,
        passed=len(failure_reasons) == 0,
        failure_reasons=failure_reasons,
    )


def render_markdown_report(result: GateRunResult) -> str:
    lines = [
        "# AI裁判 M7 验收门禁报告",
        "",
        f"- 生成时间(UTC)：{result.generated_at.isoformat()}",
        f"- 门禁结果：{'PASS' if result.passed else 'FAIL'}",
        "",
        "## 1. 回归测试结果",
    ]
    if not result.tests:
        lines.extend(["- 未执行回归测试（skip）。", ""])
    else:
        lines.append("| 模块 | 结果 | 耗时(ms) | 退出码 |")
        lines.append("|---|---:|---:|---:|")
        for item in result.tests:
            lines.append(
                f"| `{item.module}` | {'PASS' if item.passed else 'FAIL'} | {item.duration_ms:.2f} | {item.exit_code} |"
            )
        lines.append("")

    lines.append("## 2. 负载门禁结果")
    if not result.load:
        lines.extend(["- 未执行负载门禁（skip）。", ""])
    else:
        load = result.load
        lines.extend(
            [
                f"- total_requests: `{load.total_requests}`",
                f"- succeeded: `{load.succeeded}`",
                f"- failed: `{load.failed}`",
                f"- success_rate: `{load.success_rate:.4f}`（阈值 >= `{result.thresholds.min_success_rate:.4f}`）",
                f"- p50/p95/p99/max(ms): `{load.p50_latency_ms:.2f}/{load.p95_latency_ms:.2f}/{load.p99_latency_ms:.2f}/{load.max_latency_ms:.2f}`",
                f"- p95 阈值(ms): `<= {result.thresholds.max_p95_latency_ms:.2f}`",
                "",
            ]
        )

    lines.append("## 3. 失败原因")
    if not result.failure_reasons:
        lines.extend(["- 无。", ""])
    else:
        for reason in result.failure_reasons:
            lines.append(f"- {reason}")
        lines.append("")

    lines.append("## 4. 测试日志摘要")
    if not result.tests:
        lines.append("- 无。")
    else:
        for item in result.tests:
            lines.append(f"### `{item.module}`")
            lines.append("```text")
            if item.stdout:
                lines.append(item.stdout)
            if item.stderr:
                if item.stdout:
                    lines.append("---")
                lines.append(item.stderr)
            if not item.stdout and not item.stderr:
                lines.append("(empty output)")
            lines.append("```")
    lines.append("")
    return "\n".join(lines)
