from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .trust_artifact_summary import (
    build_trust_artifact_summary_from_registry_snapshot,
    build_trust_artifact_summary_from_report_payload,
)

REPLAY_DISPATCH_TYPES: frozenset[str] = frozenset({"auto", "phase", "final"})


@dataclass(frozen=True)
class ReplayReadRouteError(Exception):
    status_code: int
    detail: Any


@dataclass(frozen=True)
class ReplayReportDependencyPack:
    ensure_registry_runtime_ready: Any
    final_request_model_validate: Any
    phase_request_model_validate: Any
    validate_final_dispatch_request: Any
    validate_phase_dispatch_request: Any
    resolve_policy_profile: Any
    resolve_prompt_profile: Any
    resolve_tool_profile: Any
    list_dispatch_receipts: Any
    build_final_report_payload: Any
    resolve_panel_runtime_profiles: Any
    build_phase_report_payload: Any
    attach_judge_agent_runtime_trace: Any
    attach_policy_trace_snapshot: Any
    attach_report_attestation: Any
    validate_final_report_payload_contract: Any
    settings: Any
    gateway_runtime: Any


@dataclass(frozen=True)
class ReplayFinalizeDependencyPack:
    provider: str
    get_trace: Any
    trace_register_start: Any
    trace_mark_replay: Any
    append_replay_record: Any
    workflow_mark_replay: Any
    upsert_claim_ledger_record: Any
    build_verdict_contract: Any
    build_replay_route_payload: Any
    safe_float: Any
    resolve_winner: Any
    draw_margin: float
    judge_core_stage: str
    judge_core_version: str


@dataclass(frozen=True)
class ReplayContextDependencyPack:
    normalize_replay_dispatch_type: Any
    get_dispatch_receipt: Any
    choose_replay_dispatch_receipt: Any
    extract_replay_request_snapshot: Any
    resolve_replay_trace_id: Any


def normalize_replay_dispatch_type(dispatch_type: str) -> str:
    normalized = str(dispatch_type or "auto").strip().lower()
    if normalized not in REPLAY_DISPATCH_TYPES:
        raise ValueError("invalid_dispatch_type")
    return normalized


def choose_replay_dispatch_receipt(
    *,
    dispatch_type: str,
    final_receipt: Any | None = None,
    phase_receipt: Any | None = None,
    explicit_receipt: Any | None = None,
) -> tuple[str, Any | None]:
    if dispatch_type == "auto":
        if final_receipt is not None:
            return "final", final_receipt
        if phase_receipt is not None:
            return "phase", phase_receipt
        return "auto", None
    return dispatch_type, explicit_receipt


def extract_replay_request_snapshot(receipt: Any | None) -> dict[str, Any]:
    return receipt.request if isinstance(getattr(receipt, "request", None), dict) else {}


def resolve_replay_trace_id(
    *,
    receipt: Any | None,
    request_snapshot: dict[str, Any] | None,
) -> str:
    snapshot = request_snapshot if isinstance(request_snapshot, dict) else {}
    return str(getattr(receipt, "trace_id", None) or snapshot.get("traceId") or "").strip()


def build_trace_route_replay_items(
    *,
    replay_records: list[Any] | None,
    trace_record: Any | None,
) -> list[dict[str, Any]]:
    records = replay_records if isinstance(replay_records, list) else []
    if records:
        return [
            {
                "replayedAt": item.created_at.isoformat(),
                "winner": item.winner,
                "needsDrawVote": item.needs_draw_vote,
                "provider": item.provider,
            }
            for item in records
        ]

    trace_replays = trace_record.replays if trace_record is not None else []
    return [
        {
            "replayedAt": item.replayed_at.isoformat(),
            "winner": item.winner,
            "needsDrawVote": item.needs_draw_vote,
            "provider": item.provider,
        }
        for item in trace_replays
    ]


def build_trace_route_payload(
    *,
    record: Any,
    report_summary: dict[str, Any] | None,
    verdict_contract: dict[str, Any],
    replay_items: list[dict[str, Any]],
    case_chain_summary: dict[str, Any] | None = None,
    trust_artifact_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = report_summary if isinstance(report_summary, dict) else {}
    role_nodes = summary.get("roleNodes") if isinstance(summary.get("roleNodes"), list) else []
    return {
        "caseId": record.job_id,
        "traceId": record.trace_id,
        "status": record.status,
        "createdAt": record.created_at.isoformat(),
        "updatedAt": record.updated_at.isoformat(),
        "callbackStatus": record.callback_status,
        "callbackError": record.callback_error,
        "response": record.response,
        "request": record.request,
        "reportSummary": summary,
        "roleNodes": role_nodes,
        "verdictContract": dict(verdict_contract) if isinstance(verdict_contract, dict) else {},
        "caseChainSummary": (
            dict(case_chain_summary) if isinstance(case_chain_summary, dict) else {}
        ),
        "replays": list(replay_items),
        "trustArtifactSummary": (
            dict(trust_artifact_summary)
            if isinstance(trust_artifact_summary, dict)
            else {}
        ),
    }


def build_replay_route_payload(
    *,
    case_id: int,
    dispatch_type: str,
    replayed_at: datetime | str,
    report_payload: dict[str, Any],
    verdict_contract: dict[str, Any],
    winner: str,
    needs_draw_vote: bool,
    trace_id: str,
    judge_core_stage: str,
    judge_core_version: str,
    trust_artifact_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if isinstance(replayed_at, datetime):
        replayed_at_value = replayed_at.isoformat()
    else:
        replayed_at_value = str(replayed_at)
    return {
        "caseId": int(case_id),
        "dispatchType": str(dispatch_type),
        "replayedAt": replayed_at_value,
        "reportPayload": dict(report_payload),
        "verdictContract": dict(verdict_contract),
        "winner": str(winner),
        "needsDrawVote": bool(needs_draw_vote),
        "traceId": str(trace_id),
        "judgeCoreStage": str(judge_core_stage),
        "judgeCoreVersion": str(judge_core_version),
        "trustArtifactSummary": (
            dict(trust_artifact_summary)
            if isinstance(trust_artifact_summary, dict)
            else build_trust_artifact_summary_from_report_payload(
                report_payload=report_payload,
                case_id=case_id,
                dispatch_type=dispatch_type,
                trace_id=trace_id,
                include_artifact_refs=True,
            )
        ),
    }


def build_replay_reports_list_payload(
    *,
    items: list[dict[str, Any]],
    status: str | None,
    winner: str | None,
    callback_status: str | None,
    trace_id: str | None,
    created_after: datetime | None,
    created_before: datetime | None,
    has_audit_alert: bool | None,
    limit: int,
    include_report: bool,
) -> dict[str, Any]:
    return {
        "count": len(items),
        "items": list(items),
        "filters": {
            "status": status,
            "winner": winner,
            "callbackStatus": callback_status,
            "traceId": trace_id,
            "createdAfter": created_after.isoformat() if created_after else None,
            "createdBefore": created_before.isoformat() if created_before else None,
            "hasAuditAlert": has_audit_alert,
            "limit": int(limit),
            "includeReport": bool(include_report),
        },
    }


async def build_replay_report_route_payload(
    *,
    case_id: int,
    get_trace: Any,
    build_replay_report_payload: Any,
    get_claim_ledger_record: Any,
    serialize_claim_ledger_record: Any,
) -> dict[str, Any]:
    record = get_trace(case_id)
    if record is None:
        raise ReplayReadRouteError(status_code=404, detail="judge_trace_not_found")
    payload = build_replay_report_payload(record)
    if not isinstance(payload, dict):
        payload = {}
    claim_ledger_record = await get_claim_ledger_record(
        case_id=case_id,
        dispatch_type=None,
    )
    if claim_ledger_record is not None:
        payload = dict(payload)
        payload["claimLedger"] = serialize_claim_ledger_record(
            claim_ledger_record,
            include_payload=True,
        )
    return payload


def build_replay_reports_route_payload(
    *,
    status: str | None,
    winner: str | None,
    callback_status: str | None,
    trace_id: str | None,
    created_after: datetime | None,
    created_before: datetime | None,
    has_audit_alert: bool | None,
    limit: int,
    include_report: bool,
    normalize_query_datetime: Any,
    trace_query_cls: Any,
    list_traces: Any,
    build_replay_report_payload: Any,
    build_replay_report_summary: Any,
    build_replay_reports_list_payload: Any,
) -> dict[str, Any]:
    normalized_created_after = normalize_query_datetime(created_after)
    normalized_created_before = normalize_query_datetime(created_before)
    query = trace_query_cls(
        status=status,
        winner=winner,
        callback_status=callback_status,
        trace_id=trace_id,
        created_after=normalized_created_after,
        created_before=normalized_created_before,
        has_audit_alert=has_audit_alert,
        limit=limit,
    )
    records = list_traces(query=query)
    if include_report:
        items = [build_replay_report_payload(record) for record in records]
    else:
        items = [build_replay_report_summary(record) for record in records]
    return build_replay_reports_list_payload(
        items=items,
        status=status,
        winner=winner,
        callback_status=callback_status,
        trace_id=trace_id,
        created_after=normalized_created_after,
        created_before=normalized_created_before,
        has_audit_alert=has_audit_alert,
        limit=limit,
        include_report=include_report,
    )


async def build_trace_route_read_payload(
    *,
    case_id: int,
    get_trace: Any,
    list_replay_records: Any,
    build_trace_route_replay_items: Any,
    build_verdict_contract: Any,
    build_trace_route_payload: Any,
    build_case_chain_summary: Any | None = None,
    get_trust_registry_snapshot: Any | None = None,
) -> dict[str, Any]:
    record = get_trace(case_id)
    if record is None:
        raise ReplayReadRouteError(status_code=404, detail="judge_trace_not_found")
    replay_records = await list_replay_records(job_id=case_id, limit=50)
    replay_items = build_trace_route_replay_items(
        replay_records=replay_records,
        trace_record=record,
    )
    report_summary = record.report_summary if isinstance(record.report_summary, dict) else {}
    report_payload = (
        report_summary.get("payload")
        if isinstance(report_summary.get("payload"), dict)
        else {}
    )
    verdict_contract = build_verdict_contract(report_payload)
    case_chain_summary = (
        await build_case_chain_summary(job_id=case_id)
        if build_case_chain_summary is not None
        else None
    )
    trust_artifact_summary: dict[str, Any]
    registry_snapshot = None
    if get_trust_registry_snapshot is not None:
        for dispatch_type in ("final", "phase"):
            registry_snapshot = await get_trust_registry_snapshot(
                case_id=case_id,
                dispatch_type=dispatch_type,
            )
            if registry_snapshot is not None:
                break
    if registry_snapshot is not None:
        trust_artifact_summary = build_trust_artifact_summary_from_registry_snapshot(
            snapshot=registry_snapshot,
            include_artifact_refs=True,
        )
    else:
        trust_artifact_summary = build_trust_artifact_summary_from_report_payload(
            report_payload=report_payload,
            case_id=case_id,
            dispatch_type=None,
            trace_id=record.trace_id,
            include_artifact_refs=True,
        )
    return build_trace_route_payload(
        record=record,
        report_summary=report_summary,
        verdict_contract=verdict_contract,
        replay_items=replay_items,
        case_chain_summary=case_chain_summary,
        trust_artifact_summary=trust_artifact_summary,
    )


async def resolve_replay_dispatch_context_for_case(
    *,
    case_id: int,
    dispatch_type: str,
    normalize_replay_dispatch_type: Any,
    get_dispatch_receipt: Any,
    choose_replay_dispatch_receipt: Any,
    extract_replay_request_snapshot: Any,
    resolve_replay_trace_id: Any,
) -> dict[str, Any]:
    try:
        dispatch_type_normalized = normalize_replay_dispatch_type(dispatch_type)
    except ValueError as err:
        raise ReplayReadRouteError(status_code=422, detail="invalid_dispatch_type") from err

    if dispatch_type_normalized == "auto":
        final_receipt = await get_dispatch_receipt(
            dispatch_type="final",
            job_id=case_id,
        )
        phase_receipt = await get_dispatch_receipt(
            dispatch_type="phase",
            job_id=case_id,
        )
        chosen_dispatch_type, chosen_receipt = choose_replay_dispatch_receipt(
            dispatch_type=dispatch_type_normalized,
            final_receipt=final_receipt,
            phase_receipt=phase_receipt,
        )
    else:
        explicit_receipt = await get_dispatch_receipt(
            dispatch_type=dispatch_type_normalized,
            job_id=case_id,
        )
        chosen_dispatch_type, chosen_receipt = choose_replay_dispatch_receipt(
            dispatch_type=dispatch_type_normalized,
            explicit_receipt=explicit_receipt,
        )

    if chosen_receipt is None:
        raise ReplayReadRouteError(status_code=404, detail="replay_receipt_not_found")
    request_snapshot = extract_replay_request_snapshot(chosen_receipt)
    trace_id = resolve_replay_trace_id(
        receipt=chosen_receipt,
        request_snapshot=request_snapshot,
    )
    if not trace_id:
        raise ReplayReadRouteError(status_code=409, detail="replay_missing_trace_id")
    return {
        "dispatchType": str(chosen_dispatch_type),
        "receipt": chosen_receipt,
        "requestSnapshot": request_snapshot,
        "traceId": str(trace_id),
    }


async def build_replay_report_payload_for_dispatch(
    *,
    dispatch_type: str,
    request_snapshot: dict[str, Any],
    dependencies: ReplayReportDependencyPack,
) -> dict[str, Any]:
    deps = dependencies
    await deps.ensure_registry_runtime_ready()

    normalized_dispatch_type = str(dispatch_type or "").strip().lower()
    if normalized_dispatch_type == "final":
        try:
            final_request = deps.final_request_model_validate(request_snapshot)
        except Exception as err:
            raise ReplayReadRouteError(
                status_code=409,
                detail=f"replay_invalid_final_request: {err}",
            ) from err
        deps.validate_final_dispatch_request(final_request)
        policy_profile = deps.resolve_policy_profile(
            judge_policy_version=final_request.judge_policy_version,
            rubric_version=final_request.rubric_version,
            topic_domain=final_request.topic_domain,
        )
        prompt_profile = deps.resolve_prompt_profile(
            prompt_registry_version=policy_profile.prompt_registry_version,
        )
        tool_profile = deps.resolve_tool_profile(
            tool_registry_version=policy_profile.tool_registry_version,
        )
        phase_receipts = await deps.list_dispatch_receipts(
            dispatch_type="phase",
            session_id=final_request.session_id,
            status="reported",
            limit=1000,
        )
        report_payload = deps.build_final_report_payload(
            request=final_request,
            phase_receipts=phase_receipts,
            fairness_thresholds=policy_profile.fairness_thresholds,
            panel_runtime_profiles=deps.resolve_panel_runtime_profiles(profile=policy_profile),
        )
        await deps.attach_judge_agent_runtime_trace(
            report_payload=report_payload,
            dispatch_type="final",
            case_id=final_request.case_id,
            scope_id=final_request.scope_id,
            session_id=final_request.session_id,
            trace_id=final_request.trace_id,
            phase_start_no=final_request.phase_start_no,
            phase_end_no=final_request.phase_end_no,
        )
        deps.attach_policy_trace_snapshot(
            report_payload=report_payload,
            profile=policy_profile,
            prompt_profile=prompt_profile,
            tool_profile=tool_profile,
        )
        deps.attach_report_attestation(
            report_payload=report_payload,
            dispatch_type="final",
        )
        replay_contract_missing = deps.validate_final_report_payload_contract(report_payload)
        if replay_contract_missing:
            raise ReplayReadRouteError(
                status_code=409,
                detail="replay_final_contract_violation: missing_fields="
                + ",".join(replay_contract_missing[:12]),
            )
        return report_payload

    if normalized_dispatch_type == "phase":
        try:
            phase_request = deps.phase_request_model_validate(request_snapshot)
        except Exception as err:
            raise ReplayReadRouteError(
                status_code=409,
                detail=f"replay_invalid_phase_request: {err}",
            ) from err
        deps.validate_phase_dispatch_request(phase_request)
        policy_profile = deps.resolve_policy_profile(
            judge_policy_version=phase_request.judge_policy_version,
            rubric_version=phase_request.rubric_version,
            topic_domain=phase_request.topic_domain,
        )
        prompt_profile = deps.resolve_prompt_profile(
            prompt_registry_version=policy_profile.prompt_registry_version,
        )
        tool_profile = deps.resolve_tool_profile(
            tool_registry_version=policy_profile.tool_registry_version,
        )
        report_payload = await deps.build_phase_report_payload(
            request=phase_request,
            settings=deps.settings,
            gateway_runtime=deps.gateway_runtime,
        )
        await deps.attach_judge_agent_runtime_trace(
            report_payload=report_payload,
            dispatch_type="phase",
            case_id=phase_request.case_id,
            scope_id=phase_request.scope_id,
            session_id=phase_request.session_id,
            trace_id=phase_request.trace_id,
            phase_no=phase_request.phase_no,
        )
        deps.attach_policy_trace_snapshot(
            report_payload=report_payload,
            profile=policy_profile,
            prompt_profile=prompt_profile,
            tool_profile=tool_profile,
        )
        deps.attach_report_attestation(
            report_payload=report_payload,
            dispatch_type="phase",
        )
        return report_payload

    raise ReplayReadRouteError(status_code=422, detail="invalid_dispatch_type")


async def finalize_replay_route_payload(
    *,
    case_id: int,
    dispatch_type: str,
    trace_id: str,
    request_snapshot: dict[str, Any],
    report_payload: dict[str, Any],
    dependencies: ReplayFinalizeDependencyPack,
) -> dict[str, Any]:
    deps = dependencies
    await deps.upsert_claim_ledger_record(
        case_id=case_id,
        dispatch_type=dispatch_type,
        trace_id=trace_id,
        report_payload=report_payload,
        request_payload=request_snapshot,
    )

    winner = str(report_payload.get("winner") or "").strip().lower()
    if winner not in {"pro", "con", "draw"}:
        agent3 = (
            report_payload.get("agent3WeightedScore")
            if isinstance(report_payload.get("agent3WeightedScore"), dict)
            else {}
        )
        winner = deps.resolve_winner(
            deps.safe_float(agent3.get("pro"), default=50.0),
            deps.safe_float(agent3.get("con"), default=50.0),
            margin=deps.draw_margin,
        )
    needs_draw_vote = (
        bool(report_payload.get("needsDrawVote"))
        if "needsDrawVote" in report_payload
        else winner == "draw"
    )

    if deps.get_trace(case_id) is None:
        deps.trace_register_start(
            job_id=case_id,
            trace_id=trace_id,
            request=request_snapshot,
        )
    deps.trace_mark_replay(
        job_id=case_id,
        winner=winner,
        needs_draw_vote=needs_draw_vote,
        provider=deps.provider,
    )
    replay_row = await deps.append_replay_record(
        dispatch_type=dispatch_type,
        job_id=case_id,
        trace_id=trace_id,
        winner=winner,
        needs_draw_vote=needs_draw_vote,
        provider=deps.provider,
        report_payload=report_payload,
    )
    await deps.workflow_mark_replay(
        job_id=case_id,
        dispatch_type=dispatch_type,
        event_payload={
            "traceId": trace_id,
            "winner": winner,
            "needsDrawVote": needs_draw_vote,
            "dispatchType": dispatch_type,
        },
    )
    replayed_at = replay_row.created_at
    verdict_contract = deps.build_verdict_contract(report_payload)

    return deps.build_replay_route_payload(
        case_id=case_id,
        dispatch_type=dispatch_type,
        replayed_at=replayed_at,
        report_payload=report_payload,
        verdict_contract=verdict_contract,
        winner=winner,
        needs_draw_vote=needs_draw_vote,
        trace_id=trace_id,
        judge_core_stage=deps.judge_core_stage,
        judge_core_version=deps.judge_core_version,
    )


async def build_replay_post_route_payload(
    *,
    case_id: int,
    dispatch_type: str,
    context_dependencies: ReplayContextDependencyPack,
    report_dependencies: ReplayReportDependencyPack,
    finalize_dependencies: ReplayFinalizeDependencyPack,
) -> dict[str, Any]:
    replay_context = await resolve_replay_dispatch_context_for_case(
        case_id=case_id,
        dispatch_type=dispatch_type,
        normalize_replay_dispatch_type=(
            context_dependencies.normalize_replay_dispatch_type
        ),
        get_dispatch_receipt=context_dependencies.get_dispatch_receipt,
        choose_replay_dispatch_receipt=(
            context_dependencies.choose_replay_dispatch_receipt
        ),
        extract_replay_request_snapshot=(
            context_dependencies.extract_replay_request_snapshot
        ),
        resolve_replay_trace_id=context_dependencies.resolve_replay_trace_id,
    )
    chosen_dispatch_type = str(replay_context["dispatchType"])
    request_snapshot = replay_context["requestSnapshot"]
    trace_id = str(replay_context["traceId"])

    report_payload = await build_replay_report_payload_for_dispatch(
        dispatch_type=chosen_dispatch_type,
        request_snapshot=request_snapshot,
        dependencies=report_dependencies,
    )
    return await finalize_replay_route_payload(
        case_id=case_id,
        dispatch_type=chosen_dispatch_type,
        trace_id=trace_id,
        request_snapshot=request_snapshot,
        report_payload=report_payload,
        dependencies=finalize_dependencies,
    )
