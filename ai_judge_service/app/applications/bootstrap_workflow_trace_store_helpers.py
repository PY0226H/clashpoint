from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from fastapi import HTTPException

from app.domain.facts import (
    ClaimLedgerRecord as FactClaimLedgerRecord,
)
from app.domain.facts import (
    DispatchReceipt as FactDispatchReceipt,
)

from .case_courtroom_views import build_case_evidence_view as build_case_evidence_view_v3
from .judge_command_routes import save_dispatch_receipt as save_dispatch_receipt_v3
from .replay_audit_ops import build_verdict_contract as build_verdict_contract_v3


def _payload_int_from_mapping(payload: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = payload.get(key)
        if value is None or isinstance(value, bool):
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _payload_str_from_mapping(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        normalized = str(value).strip()
        if normalized:
            return normalized
    return None


def _build_case_dossier_from_request_payload(
    *,
    dispatch_type: str,
    request_payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    payload = request_payload if isinstance(request_payload, dict) else {}
    if not payload:
        return None

    phase_no = _payload_int_from_mapping(payload, "phase_no", "phaseNo")
    phase_start_no = _payload_int_from_mapping(payload, "phase_start_no", "phaseStartNo")
    phase_end_no = _payload_int_from_mapping(payload, "phase_end_no", "phaseEndNo")
    message_start_id = _payload_int_from_mapping(payload, "message_start_id", "messageStartId")
    message_end_id = _payload_int_from_mapping(payload, "message_end_id", "messageEndId")
    message_count = _payload_int_from_mapping(payload, "message_count", "messageCount")

    message_digest: list[dict[str, Any]] = []
    side_distribution = {"pro": 0, "con": 0, "other": 0}
    speaker_tags: list[str] = []
    speaker_seen: set[str] = set()

    message_rows = payload.get("messages") if isinstance(payload.get("messages"), list) else []
    for row in message_rows:
        if not isinstance(row, dict):
            continue
        side = str(row.get("side") or "").strip().lower()
        if side == "pro":
            side_distribution["pro"] += 1
        elif side == "con":
            side_distribution["con"] += 1
        else:
            side_distribution["other"] += 1
        speaker_tag = str(row.get("speaker_tag") or row.get("speakerTag") or "").strip()
        if speaker_tag and speaker_tag not in speaker_seen:
            speaker_seen.add(speaker_tag)
            speaker_tags.append(speaker_tag)
        message_digest.append(
            {
                "messageId": _payload_int_from_mapping(row, "message_id", "messageId"),
                "side": side if side else None,
                "speakerTag": speaker_tag or None,
                "createdAt": _payload_str_from_mapping(row, "created_at", "createdAt"),
            }
        )

    if dispatch_type == "final":
        phase_scope: dict[str, Any] = {
            "startNo": phase_start_no,
            "endNo": phase_end_no,
        }
    else:
        phase_scope = {"no": phase_no}

    return {
        "version": "v1",
        "dispatchType": dispatch_type,
        "caseId": _payload_int_from_mapping(payload, "case_id", "caseId"),
        "scopeId": _payload_int_from_mapping(payload, "scope_id", "scopeId"),
        "sessionId": _payload_int_from_mapping(payload, "session_id", "sessionId"),
        "traceId": _payload_str_from_mapping(payload, "trace_id", "traceId"),
        "topicDomain": _payload_str_from_mapping(payload, "topic_domain", "topicDomain"),
        "rubricVersion": _payload_str_from_mapping(payload, "rubric_version", "rubricVersion"),
        "judgePolicyVersion": _payload_str_from_mapping(
            payload,
            "judge_policy_version",
            "judgePolicyVersion",
        ),
        "retrievalProfile": _payload_str_from_mapping(
            payload,
            "retrieval_profile",
            "retrievalProfile",
        ),
        "phase": phase_scope,
        "messageWindow": {
            "startId": message_start_id,
            "endId": message_end_id,
            "count": message_count,
        },
        "sideDistribution": side_distribution,
        "speakerTags": speaker_tags,
        "messageDigest": message_digest,
    }


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


async def persist_dispatch_receipt_for_runtime(
    *,
    runtime: Any,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    dispatch_type: str,
    job_id: int,
    scope_id: int,
    session_id: int,
    trace_id: str,
    idempotency_key: str,
    rubric_version: str,
    judge_policy_version: str,
    topic_domain: str,
    retrieval_profile: str | None,
    phase_no: int | None,
    phase_start_no: int | None,
    phase_end_no: int | None,
    message_start_id: int | None,
    message_end_id: int | None,
    message_count: int | None,
    status: str,
    request_payload: dict[str, Any],
    response_payload: dict[str, Any] | None,
) -> None:
    save_dispatch_receipt_v3(
        save_dispatch_receipt_fn=runtime.trace_store.save_dispatch_receipt,
        dispatch_type=dispatch_type,
        job_id=job_id,
        scope_id=scope_id,
        session_id=session_id,
        trace_id=trace_id,
        idempotency_key=idempotency_key,
        rubric_version=rubric_version,
        judge_policy_version=judge_policy_version,
        topic_domain=topic_domain,
        retrieval_profile=retrieval_profile,
        phase_no=phase_no,
        phase_start_no=phase_start_no,
        phase_end_no=phase_end_no,
        message_start_id=message_start_id,
        message_end_id=message_end_id,
        message_count=message_count,
        status=status,
        request_payload=request_payload,
        response_payload=response_payload,
    )
    await ensure_workflow_schema_ready()
    await runtime.workflow_runtime.facts.upsert_dispatch_receipt(
        receipt=FactDispatchReceipt(
            dispatch_type=dispatch_type,
            job_id=max(0, int(job_id)),
            scope_id=max(0, int(scope_id)),
            session_id=max(0, int(session_id)),
            trace_id=str(trace_id or "").strip(),
            idempotency_key=str(idempotency_key or "").strip(),
            rubric_version=str(rubric_version or "").strip(),
            judge_policy_version=str(judge_policy_version or "").strip(),
            topic_domain=str(topic_domain or "").strip(),
            retrieval_profile=retrieval_profile,
            phase_no=phase_no,
            phase_start_no=phase_start_no,
            phase_end_no=phase_end_no,
            message_start_id=message_start_id,
            message_end_id=message_end_id,
            message_count=message_count,
            status=str(status or "").strip(),
            request=dict(request_payload or {}),
            response=(dict(response_payload) if isinstance(response_payload, dict) else None),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
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


async def upsert_claim_ledger_record_for_runtime(
    *,
    runtime: Any,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    case_id: int,
    dispatch_type: str,
    trace_id: str,
    report_payload: dict[str, Any] | None,
    request_payload: dict[str, Any] | None = None,
) -> FactClaimLedgerRecord | None:
    payload = report_payload if isinstance(report_payload, dict) else {}
    if not payload and not isinstance(request_payload, dict):
        return None
    verdict_contract = build_verdict_contract_v3(payload)
    evidence_view = build_case_evidence_view_v3(
        report_payload=payload,
        verdict_contract=verdict_contract,
        claim_ledger_record=None,
    )
    case_dossier = (
        evidence_view.get("caseDossier")
        if isinstance(evidence_view.get("caseDossier"), dict)
        else _build_case_dossier_from_request_payload(
            dispatch_type=dispatch_type,
            request_payload=request_payload,
        )
    )
    claim_graph = (
        evidence_view.get("claimGraph")
        if isinstance(evidence_view.get("claimGraph"), dict)
        else None
    )
    claim_graph_summary = (
        evidence_view.get("claimGraphSummary")
        if isinstance(evidence_view.get("claimGraphSummary"), dict)
        else None
    )
    evidence_ledger = (
        evidence_view.get("evidenceLedger")
        if isinstance(evidence_view.get("evidenceLedger"), dict)
        else None
    )
    verdict_evidence_refs = [
        dict(item)
        for item in (evidence_view.get("verdictEvidenceRefs") or [])
        if isinstance(item, dict)
    ]
    if (
        case_dossier is None
        and claim_graph is None
        and claim_graph_summary is None
        and not verdict_evidence_refs
    ):
        return None
    await ensure_workflow_schema_ready()
    return await runtime.workflow_runtime.facts.upsert_claim_ledger_record(
        case_id=case_id,
        dispatch_type=dispatch_type,
        trace_id=trace_id,
        case_dossier=case_dossier,
        claim_graph=claim_graph,
        claim_graph_summary=claim_graph_summary,
        evidence_ledger=evidence_ledger,
        verdict_evidence_refs=verdict_evidence_refs,
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
