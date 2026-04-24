from __future__ import annotations

from datetime import datetime
from typing import Any, Awaitable, Callable

from fastapi import HTTPException


async def list_audit_alerts_for_runtime(
    *,
    runtime: Any,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    job_id: int,
    status: str | None,
    limit: int,
) -> list[Any]:
    await ensure_workflow_schema_ready()
    items = await runtime.workflow_runtime.facts.list_audit_alerts(
        job_id=job_id,
        status=status,
        limit=limit,
    )
    if items:
        return items
    return list(
        runtime.trace_store.list_audit_alerts(
            job_id=job_id,
            status=status,
            limit=limit,
        )
    )


async def workflow_get_job_for_runtime(
    *,
    runtime: Any,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    job_id: int,
) -> Any | None:
    await ensure_workflow_schema_ready()
    return await runtime.workflow_runtime.orchestrator.get_job(job_id=job_id)


async def workflow_list_jobs_for_runtime(
    *,
    runtime: Any,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    status: str | None,
    dispatch_type: str | None,
    limit: int,
) -> list[Any]:
    await ensure_workflow_schema_ready()
    return await runtime.workflow_runtime.orchestrator.list_jobs(
        status=status,
        dispatch_type=dispatch_type,
        limit=limit,
    )


async def workflow_list_events_for_runtime(
    *,
    runtime: Any,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    job_id: int,
) -> list[Any]:
    await ensure_workflow_schema_ready()
    return await runtime.workflow_runtime.orchestrator.list_events(job_id=job_id)


async def workflow_append_event_for_runtime(
    *,
    runtime: Any,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    job_id: int,
    event_type: str,
    event_payload: dict[str, Any],
    not_found_detail: str = "workflow_job_not_found",
) -> None:
    await ensure_workflow_schema_ready()
    try:
        await runtime.workflow_runtime.orchestrator.append_event(
            job_id=job_id,
            event_type=event_type,
            event_payload=event_payload,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=not_found_detail) from exc


async def upsert_fairness_benchmark_run_for_runtime(
    *,
    runtime: Any,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    run_id: str,
    policy_version: str,
    environment_mode: str,
    status: str,
    threshold_decision: str,
    needs_real_env_reconfirm: bool,
    needs_remediation: bool,
    sample_size: int | None,
    draw_rate: float | None,
    side_bias_delta: float | None,
    appeal_overturn_rate: float | None,
    thresholds: dict[str, Any] | None,
    metrics: dict[str, Any] | None,
    summary: dict[str, Any] | None,
    source: str | None,
    reported_by: str | None,
    reported_at: datetime | None = None,
) -> Any:
    await ensure_workflow_schema_ready()
    return await runtime.workflow_runtime.facts.upsert_fairness_benchmark_run(
        run_id=run_id,
        policy_version=policy_version,
        environment_mode=environment_mode,
        status=status,
        threshold_decision=threshold_decision,
        needs_real_env_reconfirm=needs_real_env_reconfirm,
        needs_remediation=needs_remediation,
        sample_size=sample_size,
        draw_rate=draw_rate,
        side_bias_delta=side_bias_delta,
        appeal_overturn_rate=appeal_overturn_rate,
        thresholds=thresholds,
        metrics=metrics,
        summary=summary,
        source=source,
        reported_by=reported_by,
        reported_at=reported_at,
    )


async def list_fairness_benchmark_runs_for_runtime(
    *,
    runtime: Any,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    policy_version: str | None = None,
    environment_mode: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[Any]:
    await ensure_workflow_schema_ready()
    return await runtime.workflow_runtime.facts.list_fairness_benchmark_runs(
        policy_version=policy_version,
        environment_mode=environment_mode,
        status=status,
        limit=limit,
    )


async def upsert_fairness_shadow_run_for_runtime(
    *,
    runtime: Any,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    run_id: str,
    policy_version: str,
    benchmark_run_id: str | None,
    environment_mode: str,
    status: str,
    threshold_decision: str,
    needs_real_env_reconfirm: bool,
    needs_remediation: bool,
    sample_size: int | None,
    winner_flip_rate: float | None,
    score_shift_delta: float | None,
    review_required_delta: float | None,
    thresholds: dict[str, Any] | None,
    metrics: dict[str, Any] | None,
    summary: dict[str, Any] | None,
    source: str | None,
    reported_by: str | None,
    reported_at: datetime | None = None,
) -> Any:
    await ensure_workflow_schema_ready()
    return await runtime.workflow_runtime.facts.upsert_fairness_shadow_run(
        run_id=run_id,
        policy_version=policy_version,
        benchmark_run_id=benchmark_run_id,
        environment_mode=environment_mode,
        status=status,
        threshold_decision=threshold_decision,
        needs_real_env_reconfirm=needs_real_env_reconfirm,
        needs_remediation=needs_remediation,
        sample_size=sample_size,
        winner_flip_rate=winner_flip_rate,
        score_shift_delta=score_shift_delta,
        review_required_delta=review_required_delta,
        thresholds=thresholds,
        metrics=metrics,
        summary=summary,
        source=source,
        reported_by=reported_by,
        reported_at=reported_at,
    )


async def list_fairness_shadow_runs_for_runtime(
    *,
    runtime: Any,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    policy_version: str | None = None,
    benchmark_run_id: str | None = None,
    environment_mode: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[Any]:
    await ensure_workflow_schema_ready()
    return await runtime.workflow_runtime.facts.list_fairness_shadow_runs(
        policy_version=policy_version,
        benchmark_run_id=benchmark_run_id,
        environment_mode=environment_mode,
        status=status,
        limit=limit,
    )


async def get_dispatch_receipt_for_runtime(
    *,
    runtime: Any,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    dispatch_type: str,
    job_id: int,
) -> Any | None:
    await ensure_workflow_schema_ready()
    receipt = await runtime.workflow_runtime.facts.get_dispatch_receipt(
        dispatch_type=dispatch_type,
        job_id=job_id,
    )
    if receipt is not None:
        return receipt
    return runtime.trace_store.get_dispatch_receipt(
        dispatch_type=dispatch_type,
        job_id=job_id,
    )


async def list_dispatch_receipts_for_runtime(
    *,
    runtime: Any,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    dispatch_type: str,
    session_id: int | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[Any]:
    await ensure_workflow_schema_ready()
    receipts = await runtime.workflow_runtime.facts.list_dispatch_receipts(
        dispatch_type=dispatch_type,
        session_id=session_id,
        status=status,
        limit=limit,
    )
    if receipts:
        return list(receipts)
    return list(
        runtime.trace_store.list_dispatch_receipts(
            dispatch_type=dispatch_type,
            session_id=session_id,
            status=status,
            limit=limit,
        )
    )


async def append_replay_record_for_runtime(
    *,
    runtime: Any,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    dispatch_type: str,
    job_id: int,
    trace_id: str,
    winner: str | None,
    needs_draw_vote: bool | None,
    provider: str | None,
    report_payload: dict[str, Any] | None,
) -> Any:
    await ensure_workflow_schema_ready()
    return await runtime.workflow_runtime.facts.append_replay_record(
        dispatch_type=dispatch_type,
        job_id=job_id,
        trace_id=trace_id,
        winner=winner,
        needs_draw_vote=needs_draw_vote,
        provider=provider,
        report_payload=report_payload,
    )


async def list_replay_records_for_runtime(
    *,
    runtime: Any,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    job_id: int,
    dispatch_type: str | None = None,
    limit: int = 50,
) -> list[Any]:
    await ensure_workflow_schema_ready()
    return await runtime.workflow_runtime.facts.list_replay_records(
        dispatch_type=dispatch_type,
        job_id=job_id,
        limit=limit,
    )


async def get_claim_ledger_record_for_runtime(
    *,
    runtime: Any,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    case_id: int,
    dispatch_type: str | None = None,
) -> Any | None:
    await ensure_workflow_schema_ready()
    return await runtime.workflow_runtime.facts.get_claim_ledger_record(
        case_id=case_id,
        dispatch_type=dispatch_type,
    )


async def list_claim_ledger_records_for_runtime(
    *,
    runtime: Any,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    case_id: int,
    limit: int = 20,
) -> list[Any]:
    await ensure_workflow_schema_ready()
    return await runtime.workflow_runtime.facts.list_claim_ledger_records(
        case_id=case_id,
        limit=limit,
    )


async def sync_audit_alert_to_facts_for_runtime(
    *,
    runtime: Any,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    alert: Any,
) -> Any:
    await ensure_workflow_schema_ready()
    return await runtime.workflow_runtime.facts.upsert_audit_alert(
        alert_id=str(alert.alert_id or "").strip() or None,
        job_id=int(alert.job_id),
        scope_id=int(alert.scope_id),
        trace_id=str(alert.trace_id or "").strip(),
        alert_type=str(alert.alert_type or "").strip(),
        severity=str(alert.severity or "").strip(),
        title=str(alert.title or "").strip(),
        message=str(alert.message or "").strip(),
        details=(dict(alert.details) if isinstance(alert.details, dict) else {}),
        now=getattr(alert, "updated_at", None),
    )
