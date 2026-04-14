from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Header, HTTPException, Query, Request
from pydantic import ValidationError

from .applications import (
    AgentRuntime,
    GatewayRuntime,
    PolicyRegistryRuntime,
    WorkflowRuntime,
    build_agent_runtime,
    build_gateway_runtime,
    build_policy_registry_runtime,
    build_workflow_runtime,
)
from .applications import (
    attach_report_attestation as attach_report_attestation_v3,
)
from .applications import (
    build_final_report_payload as build_final_report_payload_v3_final,
)
from .applications import (
    build_phase_report_payload as build_phase_report_payload_v3_phase,
)
from .applications import (
    build_replay_report_payload as build_replay_report_payload_v3,
)
from .applications import (
    build_replay_report_summary as build_replay_report_summary_v3,
)
from .applications import (
    build_verdict_contract as build_verdict_contract_v3,
)
from .applications import (
    serialize_alert_item as serialize_alert_item_v3,
)
from .applications import (
    serialize_dispatch_receipt as serialize_dispatch_receipt_v3,
)
from .applications import (
    serialize_outbox_event as serialize_outbox_event_v3,
)
from .applications import (
    validate_final_report_payload_contract as validate_final_report_payload_contract_v3_final,
)
from .applications import (
    verify_report_attestation as verify_report_attestation_v3,
)
from .callback_client import (
    callback_final_failed,
    callback_final_report,
    callback_phase_failed,
    callback_phase_report,
)
from .core.judge_core import (
    JUDGE_CORE_STAGE_REPLAY_COMPUTED,
    JUDGE_CORE_VERSION,
    JudgeCoreOrchestrator,
)
from .domain.agents import AGENT_KIND_JUDGE, AgentExecutionRequest
from .domain.facts import (
    AuditAlert as FactAuditAlert,
)
from .domain.facts import (
    DispatchReceipt as FactDispatchReceipt,
)
from .domain.facts import (
    ReplayRecord as FactReplayRecord,
)
from .domain.workflow import WORKFLOW_STATUS_QUEUED, WORKFLOW_STATUSES, WorkflowJob
from .models import CaseCreateRequest, FinalDispatchRequest, PhaseDispatchRequest
from .runtime_types import CallbackReportFn, DispatchRuntimeConfig, SleepFn
from .settings import (
    Settings,
    build_callback_client_config,
    build_dispatch_runtime_config,
    load_settings,
)
from .trace_store import TraceQuery, TraceStoreProtocol, build_trace_store_from_settings
from .wiring import build_v3_dispatch_callbacks

LoadSettingsFn = Callable[[], Settings]


@dataclass(frozen=True)
class AppRuntime:
    settings: Settings
    dispatch_runtime_cfg: DispatchRuntimeConfig
    callback_phase_report_fn: Callable[[int, dict[str, Any]], Awaitable[None]]
    callback_final_report_fn: Callable[[int, dict[str, Any]], Awaitable[None]]
    callback_phase_failed_fn: Callable[[int, dict[str, Any]], Awaitable[None]]
    callback_final_failed_fn: Callable[[int, dict[str, Any]], Awaitable[None]]
    sleep_fn: SleepFn
    trace_store: TraceStoreProtocol
    workflow_runtime: WorkflowRuntime
    gateway_runtime: GatewayRuntime
    agent_runtime: AgentRuntime
    policy_registry_runtime: PolicyRegistryRuntime


def require_internal_key(settings: Settings, header_value: str | None) -> None:
    if not header_value:
        raise HTTPException(status_code=401, detail="missing x-ai-internal-key")
    if header_value.strip() != settings.ai_internal_key:
        raise HTTPException(status_code=401, detail="invalid x-ai-internal-key")


def create_runtime(
    *,
    settings: Settings,
    callback_phase_report_impl=callback_phase_report,
    callback_final_report_impl=callback_final_report,
    callback_phase_failed_impl=callback_phase_failed,
    callback_final_failed_impl=callback_final_failed,
    sleep_fn: SleepFn = asyncio.sleep,
) -> AppRuntime:
    trace_store = build_trace_store_from_settings(settings=settings)
    workflow_runtime = build_workflow_runtime(settings=settings)
    gateway_runtime = build_gateway_runtime(settings=settings)
    agent_runtime = build_agent_runtime(settings=settings)
    policy_registry_runtime = build_policy_registry_runtime(settings=settings)
    callback_cfg = build_callback_client_config(settings)
    (
        callback_phase_report_fn,
        callback_final_report_fn,
        callback_phase_failed_fn,
        callback_final_failed_fn,
    ) = build_v3_dispatch_callbacks(
        cfg=callback_cfg,
        callback_phase_report_impl=callback_phase_report_impl,
        callback_final_report_impl=callback_final_report_impl,
        callback_phase_failed_impl=callback_phase_failed_impl,
        callback_final_failed_impl=callback_final_failed_impl,
    )
    return AppRuntime(
        settings=settings,
        dispatch_runtime_cfg=build_dispatch_runtime_config(settings),
        callback_phase_report_fn=callback_phase_report_fn,
        callback_final_report_fn=callback_final_report_fn,
        callback_phase_failed_fn=callback_phase_failed_fn,
        callback_final_failed_fn=callback_final_failed_fn,
        sleep_fn=sleep_fn,
        trace_store=trace_store,
        workflow_runtime=workflow_runtime,
        gateway_runtime=gateway_runtime,
        agent_runtime=agent_runtime,
        policy_registry_runtime=policy_registry_runtime,
    )


_BLIND_SENSITIVE_KEY_TOKENS = {
    "user_id",
    "userid",
    "vip",
    "balance",
    "wallet_balance",
    "is_vip",
}


def _serialize_alert_item(alert: Any) -> dict[str, Any]:
    return serialize_alert_item_v3(alert)


def _serialize_outbox_event(item: Any) -> dict[str, Any]:
    return serialize_outbox_event_v3(item)


def _serialize_dispatch_receipt(item: Any) -> dict[str, Any]:
    return serialize_dispatch_receipt_v3(item)


def _serialize_workflow_job(item: WorkflowJob) -> dict[str, Any]:
    return {
        "caseId": item.job_id,
        "dispatchType": item.dispatch_type,
        "traceId": item.trace_id,
        "status": item.status,
        "scopeId": item.scope_id,
        "sessionId": item.session_id,
        "idempotencyKey": item.idempotency_key,
        "rubricVersion": item.rubric_version,
        "judgePolicyVersion": item.judge_policy_version,
        "topicDomain": item.topic_domain,
        "retrievalProfile": item.retrieval_profile,
        "createdAt": item.created_at.isoformat() if item.created_at else None,
        "updatedAt": item.updated_at.isoformat() if item.updated_at else None,
    }


def _serialize_policy_profile(runtime: AppRuntime, *, profile: Any) -> dict[str, Any]:
    return runtime.policy_registry_runtime.serialize_profile(profile)


def _resolve_policy_profile_or_raise(
    *,
    runtime: AppRuntime,
    judge_policy_version: str,
    rubric_version: str,
    topic_domain: str,
) -> Any:
    outcome = runtime.policy_registry_runtime.resolve(
        requested_version=judge_policy_version,
        rubric_version=rubric_version,
        topic_domain=topic_domain,
    )
    if outcome.profile is not None:
        return outcome.profile
    raise HTTPException(
        status_code=422,
        detail=outcome.error_code or "judge_policy_invalid",
    )


def _attach_policy_trace_snapshot(
    *,
    runtime: AppRuntime,
    report_payload: dict[str, Any],
    profile: Any,
) -> None:
    if not isinstance(report_payload, dict):
        return
    judge_trace = report_payload.get("judgeTrace")
    if not isinstance(judge_trace, dict):
        judge_trace = {}
        report_payload["judgeTrace"] = judge_trace
    judge_trace["policyRegistry"] = runtime.policy_registry_runtime.build_trace_snapshot(profile)


def _attach_report_attestation(
    *,
    report_payload: dict[str, Any],
    dispatch_type: str,
) -> dict[str, Any]:
    return attach_report_attestation_v3(
        report_payload=report_payload,
        dispatch_type=dispatch_type,
    )


def _verify_report_attestation(
    *,
    report_payload: dict[str, Any],
    dispatch_type: str,
) -> dict[str, Any]:
    return verify_report_attestation_v3(
        report_payload=report_payload,
        dispatch_type=dispatch_type,
    )


def _build_replay_report_payload(record: Any) -> dict[str, Any]:
    return build_replay_report_payload_v3(record)


def _build_replay_report_summary(record: Any) -> dict[str, Any]:
    return build_replay_report_summary_v3(record)


def _build_verdict_contract(payload: dict[str, Any] | None) -> dict[str, Any]:
    return build_verdict_contract_v3(payload)


def _build_case_evidence_view(
    *,
    report_payload: dict[str, Any] | None,
    verdict_contract: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = report_payload if isinstance(report_payload, dict) else {}
    contract = verdict_contract if isinstance(verdict_contract, dict) else {}
    judge_trace = payload.get("judgeTrace") if isinstance(payload.get("judgeTrace"), dict) else {}

    claim_graph = payload.get("claimGraph") if isinstance(payload.get("claimGraph"), dict) else None
    claim_graph_summary = (
        payload.get("claimGraphSummary")
        if isinstance(payload.get("claimGraphSummary"), dict)
        else None
    )
    policy_snapshot = (
        judge_trace.get("policyRegistry")
        if isinstance(judge_trace.get("policyRegistry"), dict)
        else None
    )
    trust_attestation = (
        payload.get("trustAttestation")
        if isinstance(payload.get("trustAttestation"), dict)
        else None
    )
    fairness_summary = (
        payload.get("fairnessSummary")
        if isinstance(payload.get("fairnessSummary"), dict)
        else (
            contract.get("fairnessSummary")
            if isinstance(contract.get("fairnessSummary"), dict)
            else None
        )
    )

    raw_audit_alerts = payload.get("auditAlerts")
    if not isinstance(raw_audit_alerts, list):
        raw_audit_alerts = contract.get("auditAlerts")
    audit_alerts = [item for item in (raw_audit_alerts or []) if isinstance(item, dict)]

    raw_error_codes = payload.get("errorCodes")
    if not isinstance(raw_error_codes, list):
        raw_error_codes = contract.get("errorCodes")
    error_codes = [
        str(item).strip()
        for item in (raw_error_codes or [])
        if str(item).strip()
    ]

    raw_verdict_refs = payload.get("verdictEvidenceRefs")
    if not isinstance(raw_verdict_refs, list):
        raw_verdict_refs = contract.get("verdictEvidenceRefs")
    verdict_evidence_refs = [
        str(item).strip()
        for item in (raw_verdict_refs or [])
        if str(item).strip()
    ]

    degradation_level = (
        int(payload.get("degradationLevel"))
        if isinstance(payload.get("degradationLevel"), int)
        else (
            int(contract.get("degradationLevel"))
            if isinstance(contract.get("degradationLevel"), int)
            else None
        )
    )

    policy_version = (
        str(policy_snapshot.get("version")).strip()
        if isinstance(policy_snapshot, dict)
        and str(policy_snapshot.get("version") or "").strip()
        else None
    )

    return {
        "claimGraph": claim_graph,
        "claimGraphSummary": claim_graph_summary,
        "policySnapshot": policy_snapshot,
        "policyVersion": policy_version,
        "trustAttestation": trust_attestation,
        "fairnessSummary": fairness_summary,
        "verdictEvidenceRefs": verdict_evidence_refs,
        "auditSummary": {
            "alertCount": len(audit_alerts),
            "auditAlerts": audit_alerts,
            "errorCodes": error_codes,
            "degradationLevel": degradation_level,
        },
        "hasClaimGraph": claim_graph is not None,
        "hasTrustAttestation": trust_attestation is not None,
    }


def _normalize_query_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _normalize_workflow_status(status: str | None) -> str | None:
    if status is None:
        return None
    normalized = str(status).strip().lower()
    if not normalized:
        return None
    return normalized


def _build_judge_core_view(
    *,
    workflow_job: WorkflowJob | None,
    workflow_events: list[Any],
) -> dict[str, Any] | None:
    latest_stage: str | None = None
    latest_version: str | None = None
    latest_event_seq: int | None = None
    for event in reversed(workflow_events):
        payload = event.payload if isinstance(getattr(event, "payload", None), dict) else {}
        stage = str(payload.get("judgeCoreStage") or "").strip().lower()
        if not stage:
            continue
        latest_stage = stage
        latest_version = str(payload.get("judgeCoreVersion") or "").strip() or None
        latest_event_seq = int(getattr(event, "event_seq", 0) or 0)
        break
    if latest_stage is None and workflow_job is not None:
        status = str(workflow_job.status or "").strip().lower()
        fallback_by_status = {
            "queued": "queued",
            "blinded": "blinded",
            "case_built": "case_built",
            "claim_graph_ready": "claim_graph_ready",
            "evidence_ready": "evidence_ready",
            "panel_judged": "panel_judged",
            "fairness_checked": "fairness_checked",
            "arbitrated": "arbitrated",
            "opinion_written": "opinion_written",
            "callback_reported": "callback_reported",
            "archived": "archived",
            "review_required": "review_required",
            "draw_pending_vote": "draw_pending_vote",
            "blocked_failed": "blocked_failed",
        }
        latest_stage = fallback_by_status.get(status)
        latest_version = JUDGE_CORE_VERSION if latest_stage is not None else None
    if latest_stage is None:
        return None
    return {
        "stage": latest_stage,
        "version": latest_version or JUDGE_CORE_VERSION,
        "eventSeq": latest_event_seq,
    }


def _normalize_key_token(value: Any) -> str:
    lowered = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return lowered


def _collect_sensitive_key_hits(
    value: Any,
    *,
    path: str,
    out: list[str],
) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            key_token = _normalize_key_token(key_text)
            compact = key_token.replace("_", "")
            if key_token in _BLIND_SENSITIVE_KEY_TOKENS or compact in _BLIND_SENSITIVE_KEY_TOKENS:
                out.append(f"{path}.{key_text}" if path else key_text)
            next_path = f"{path}.{key_text}" if path else key_text
            _collect_sensitive_key_hits(child, path=next_path, out=out)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            next_path = f"{path}[{index}]" if path else f"[{index}]"
            _collect_sensitive_key_hits(child, path=next_path, out=out)


def _find_sensitive_key_hits(payload: Any) -> list[str]:
    out: list[str] = []
    _collect_sensitive_key_hits(payload, path="", out=out)
    dedup: list[str] = []
    seen: set[str] = set()
    for item in out:
        if item in seen:
            continue
        seen.add(item)
        dedup.append(item)
    return dedup


def _extract_raw_field(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload.get(key)
    return None


def _extract_optional_int(payload: dict[str, Any], *keys: str) -> int | None:
    value = _extract_raw_field(payload, *keys)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_optional_str(payload: dict[str, Any], *keys: str) -> str | None:
    value = _extract_raw_field(payload, *keys)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _build_failed_callback_payload(
    *,
    case_id: int,
    dispatch_type: str,
    trace_id: str,
    error_code: str,
    error_message: str,
    audit_alert_ids: list[str] | None = None,
    degradation_level: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "caseId": case_id,
        "dispatchType": dispatch_type,
        "traceId": trace_id,
        "errorCode": error_code,
        "errorMessage": error_message,
        "auditAlertIds": list(audit_alert_ids or []),
    }
    if degradation_level is not None:
        payload["degradationLevel"] = int(degradation_level)
    payload["error"] = _build_error_contract(
        error_code=error_code,
        error_message=error_message,
        dispatch_type=dispatch_type,
        trace_id=trace_id,
        retryable=False,
        category="failed_callback",
    )
    return payload


def _build_error_contract(
    *,
    error_code: str,
    error_message: str,
    dispatch_type: str,
    trace_id: str,
    retryable: bool,
    category: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "code": str(error_code or "").strip(),
        "message": str(error_message or "").strip(),
        "dispatchType": str(dispatch_type or "").strip().lower(),
        "traceId": str(trace_id or "").strip(),
        "retryable": bool(retryable),
        "category": str(category or "").strip().lower(),
        "details": dict(details or {}),
    }


def _with_error_contract(
    payload: dict[str, Any],
    *,
    error_code: str,
    error_message: str,
    dispatch_type: str,
    trace_id: str,
    retryable: bool,
    category: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = dict(payload)
    out["errorCode"] = str(error_code or "").strip()
    out["errorMessage"] = str(error_message or "").strip()
    out["error"] = _build_error_contract(
        error_code=error_code,
        error_message=error_message,
        dispatch_type=dispatch_type,
        trace_id=trace_id,
        retryable=retryable,
        category=category,
        details=details,
    )
    return out


def _build_trace_report_summary(
    *,
    dispatch_type: str,
    payload: dict[str, Any] | None,
    callback_status: str,
    callback_error: str | None,
) -> dict[str, Any]:
    report_payload = payload if isinstance(payload, dict) else {}
    alerts = report_payload.get("auditAlerts")
    if not isinstance(alerts, list):
        alerts = []
    winner = str(report_payload.get("winner") or "").strip().lower() or None
    return {
        "dispatchType": dispatch_type,
        "payload": report_payload,
        "winner": winner,
        "auditAlerts": [item for item in alerts if isinstance(item, dict)],
        "callbackStatus": callback_status,
        "callbackError": callback_error,
    }


def _resolve_idempotency_or_raise(
    *,
    runtime: AppRuntime,
    key: str,
    job_id: int,
    conflict_detail: str,
) -> dict[str, Any] | None:
    resolution = runtime.trace_store.resolve_idempotency(
        key=key,
        job_id=job_id,
        ttl_secs=runtime.settings.idempotency_ttl_secs,
    )
    if resolution.status == "replay" and resolution.record and resolution.record.response:
        replayed = dict(resolution.record.response)
        replayed["idempotentReplay"] = True
        return replayed
    if resolution.status != "acquired":
        raise HTTPException(status_code=409, detail=conflict_detail)
    return None


def _validate_phase_dispatch_request(request: PhaseDispatchRequest) -> None:
    if request.message_count <= 0:
        raise HTTPException(status_code=422, detail="invalid_message_count")
    if request.message_end_id < request.message_start_id:
        raise HTTPException(status_code=422, detail="invalid_message_range")
    if request.message_count != len(request.messages):
        raise HTTPException(status_code=422, detail="message_count_mismatch")
    for message in request.messages:
        if (
            message.message_id < request.message_start_id
            or message.message_id > request.message_end_id
        ):
            raise HTTPException(status_code=422, detail="message_id_out_of_range")


def _validate_final_dispatch_request(request: FinalDispatchRequest) -> None:
    if request.phase_start_no <= 0 or request.phase_end_no <= 0:
        raise HTTPException(status_code=422, detail="invalid_phase_no")
    if request.phase_start_no > request.phase_end_no:
        raise HTTPException(status_code=422, detail="invalid_phase_range")


def _extract_dispatch_meta_from_raw(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "caseId": _extract_optional_int(payload, "case_id", "caseId"),
        "scopeId": _extract_optional_int(payload, "scope_id", "scopeId") or 1,
        "sessionId": _extract_optional_int(payload, "session_id", "sessionId"),
        "traceId": _extract_optional_str(payload, "trace_id", "traceId") or "",
        "idempotencyKey": _extract_optional_str(payload, "idempotency_key", "idempotencyKey") or "",
        "rubricVersion": _extract_optional_str(payload, "rubric_version", "rubricVersion") or "",
        "judgePolicyVersion": _extract_optional_str(
            payload,
            "judge_policy_version",
            "judgePolicyVersion",
        )
        or "",
        "topicDomain": _extract_optional_str(payload, "topic_domain", "topicDomain") or "",
        "retrievalProfile": _extract_optional_str(
            payload,
            "retrieval_profile",
            "retrievalProfile",
        ),
    }


def _extract_receipt_dims_from_raw(
    dispatch_type: str,
    payload: dict[str, Any],
) -> dict[str, int | None]:
    if dispatch_type == "phase":
        return {
            "phaseNo": _extract_optional_int(payload, "phase_no", "phaseNo"),
            "phaseStartNo": None,
            "phaseEndNo": None,
            "messageStartId": _extract_optional_int(payload, "message_start_id", "messageStartId"),
            "messageEndId": _extract_optional_int(payload, "message_end_id", "messageEndId"),
            "messageCount": _extract_optional_int(payload, "message_count", "messageCount"),
        }
    return {
        "phaseNo": None,
        "phaseStartNo": _extract_optional_int(payload, "phase_start_no", "phaseStartNo"),
        "phaseEndNo": _extract_optional_int(payload, "phase_end_no", "phaseEndNo"),
        "messageStartId": None,
        "messageEndId": None,
        "messageCount": None,
    }


def _failed_callback_fn_for_dispatch(runtime: AppRuntime, dispatch_type: str) -> CallbackReportFn:
    return runtime.callback_phase_failed_fn if dispatch_type == "phase" else runtime.callback_final_failed_fn


def _report_callback_fn_for_dispatch(runtime: AppRuntime, dispatch_type: str) -> CallbackReportFn:
    return runtime.callback_phase_report_fn if dispatch_type == "phase" else runtime.callback_final_report_fn


async def _attach_judge_agent_runtime_trace(
    *,
    runtime: AppRuntime,
    report_payload: dict[str, Any],
    dispatch_type: str,
    case_id: int,
    scope_id: int,
    session_id: int,
    trace_id: str,
    phase_no: int | None = None,
    phase_start_no: int | None = None,
    phase_end_no: int | None = None,
) -> None:
    if not isinstance(report_payload, dict):
        return

    judge_trace = report_payload.get("judgeTrace")
    if not isinstance(judge_trace, dict):
        judge_trace = {}
        report_payload["judgeTrace"] = judge_trace

    request_metadata: dict[str, Any] = {"dispatchType": dispatch_type}
    if phase_no is not None:
        request_metadata["phaseNo"] = phase_no
    if phase_start_no is not None:
        request_metadata["phaseStartNo"] = phase_start_no
    if phase_end_no is not None:
        request_metadata["phaseEndNo"] = phase_end_no

    request_payload: dict[str, Any] = {
        "dispatchType": dispatch_type,
        "caseId": case_id,
        "scopeId": scope_id,
        "sessionId": session_id,
    }
    if phase_no is not None:
        request_payload["phaseNo"] = phase_no
    if phase_start_no is not None:
        request_payload["phaseStartNo"] = phase_start_no
    if phase_end_no is not None:
        request_payload["phaseEndNo"] = phase_end_no

    try:
        judge_runtime_result = await runtime.agent_runtime.execute(
            AgentExecutionRequest(
                kind=AGENT_KIND_JUDGE,
                input_payload=request_payload,
                trace_id=trace_id,
                session_id=session_id,
                scope_id=scope_id,
                metadata=request_metadata,
            )
        )
    except Exception as err:
        judge_trace["agentRuntime"] = {
            "kind": AGENT_KIND_JUDGE,
            "status": "error",
            "dispatchType": dispatch_type,
            "errorCode": "agent_runtime_exception",
            "errorMessage": str(err),
        }
        return

    runtime_output = judge_runtime_result.output if isinstance(judge_runtime_result.output, dict) else {}
    judge_trace["agentRuntime"] = {
        "kind": AGENT_KIND_JUDGE,
        "status": judge_runtime_result.status,
        "dispatchType": dispatch_type,
        "errorCode": judge_runtime_result.error_code,
        "errorMessage": judge_runtime_result.error_message,
        "runtimeVersion": runtime_output.get("runtimeVersion"),
        "activeRoles": runtime_output.get("activeRoles"),
    }
    roles = runtime_output.get("roles")
    if isinstance(roles, list):
        judge_trace["courtroomRoles"] = [item for item in roles if isinstance(item, dict)]
    role_order = runtime_output.get("roleOrder")
    if isinstance(role_order, list):
        judge_trace["courtroomRoleOrder"] = [str(item) for item in role_order if str(item).strip()]


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _resolve_winner(pro_score: float, con_score: float, *, margin: float = 1.0) -> str:
    if pro_score - con_score >= margin:
        return "pro"
    if con_score - pro_score >= margin:
        return "con"
    return "draw"


def _validate_final_report_payload_contract(payload: dict[str, Any]) -> list[str]:
    return validate_final_report_payload_contract_v3_final(payload)


def _build_final_report_payload(
    *,
    runtime: AppRuntime,
    request: FinalDispatchRequest,
    phase_receipts: list[Any] | None = None,
) -> dict[str, Any]:
    receipts = (
        phase_receipts
        if phase_receipts is not None
        else runtime.trace_store.list_dispatch_receipts(
            dispatch_type="phase",
            session_id=request.session_id,
            status="reported",
            limit=1000,
        )
    )
    return build_final_report_payload_v3_final(
        request=request,
        phase_receipts=list(receipts),
        judge_style_mode=runtime.dispatch_runtime_cfg.judge_style_mode,
    )


async def _invoke_v3_callback_with_retry(
    *,
    runtime: AppRuntime,
    callback_fn: CallbackReportFn,
    job_id: int,
    payload: dict[str, Any],
) -> tuple[int, int]:
    max_attempts = max(1, int(runtime.dispatch_runtime_cfg.runtime_retry_max_attempts))
    backoff_ms = max(0, int(runtime.dispatch_runtime_cfg.retry_backoff_ms))
    attempt = 0
    last_error: Exception | None = None
    while attempt < max_attempts:
        attempt += 1
        try:
            await callback_fn(job_id, payload)
            return attempt, max(0, attempt - 1)
        except Exception as err:
            last_error = err
            if attempt >= max_attempts:
                break
            if backoff_ms > 0:
                await runtime.sleep_fn((backoff_ms * attempt) / 1000.0)
    raise RuntimeError(
        f"v3 callback failed after {max_attempts} attempts: {last_error or 'unknown'}"
    ) from last_error


def _save_dispatch_receipt(
    *,
    runtime: AppRuntime,
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
    runtime.trace_store.save_dispatch_receipt(
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
        request=request_payload,
        response=response_payload,
    )


def create_app(runtime: AppRuntime) -> FastAPI:
    app = FastAPI(title="AI Judge Service", version="0.2.0")
    judge_core = JudgeCoreOrchestrator(
        workflow_orchestrator=runtime.workflow_runtime.orchestrator
    )
    workflow_schema_ready = False
    workflow_schema_lock = asyncio.Lock()

    async def _ensure_workflow_schema_ready() -> None:
        nonlocal workflow_schema_ready
        if workflow_schema_ready or not runtime.settings.db_auto_create_schema:
            return
        async with workflow_schema_lock:
            if workflow_schema_ready:
                return
            await runtime.workflow_runtime.db.create_schema()
            workflow_schema_ready = True

    async def _persist_dispatch_receipt(
        *,
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
        _save_dispatch_receipt(
            runtime=runtime,
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
        await _ensure_workflow_schema_ready()
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

    async def _get_dispatch_receipt(*, dispatch_type: str, job_id: int) -> Any | None:
        await _ensure_workflow_schema_ready()
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

    async def _list_dispatch_receipts(
        *,
        dispatch_type: str,
        session_id: int | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> list[Any]:
        await _ensure_workflow_schema_ready()
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

    async def _append_replay_record(
        *,
        dispatch_type: str,
        job_id: int,
        trace_id: str,
        winner: str | None,
        needs_draw_vote: bool | None,
        provider: str | None,
        report_payload: dict[str, Any] | None,
    ) -> FactReplayRecord:
        await _ensure_workflow_schema_ready()
        return await runtime.workflow_runtime.facts.append_replay_record(
            dispatch_type=dispatch_type,
            job_id=job_id,
            trace_id=trace_id,
            winner=winner,
            needs_draw_vote=needs_draw_vote,
            provider=provider,
            report_payload=report_payload,
        )

    async def _list_replay_records(
        *,
        job_id: int,
        dispatch_type: str | None = None,
        limit: int = 50,
    ) -> list[FactReplayRecord]:
        await _ensure_workflow_schema_ready()
        return await runtime.workflow_runtime.facts.list_replay_records(
            dispatch_type=dispatch_type,
            job_id=job_id,
            limit=limit,
        )

    async def _sync_audit_alert_to_facts(*, alert: Any) -> FactAuditAlert:
        await _ensure_workflow_schema_ready()
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

    async def _list_audit_alerts(
        *,
        job_id: int,
        status: str | None,
        limit: int,
    ) -> list[Any]:
        await _ensure_workflow_schema_ready()
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

    def _build_workflow_job(
        *,
        dispatch_type: str,
        job_id: int,
        trace_id: str,
        scope_id: int,
        session_id: int,
        idempotency_key: str,
        rubric_version: str,
        judge_policy_version: str,
        topic_domain: str,
        retrieval_profile: str | None,
    ) -> WorkflowJob:
        return WorkflowJob(
            job_id=max(0, int(job_id)),
            dispatch_type=str(dispatch_type or "").strip().lower(),
            trace_id=str(trace_id or "").strip(),
            status=WORKFLOW_STATUS_QUEUED,
            scope_id=max(0, int(scope_id)),
            session_id=max(0, int(session_id)),
            idempotency_key=str(idempotency_key or "").strip(),
            rubric_version=str(rubric_version or "").strip(),
            judge_policy_version=str(judge_policy_version or "").strip(),
            topic_domain=str(topic_domain or "").strip().lower() or "default",
            retrieval_profile=(
                str(retrieval_profile).strip()
                if retrieval_profile is not None and str(retrieval_profile).strip()
                else None
            ),
        )

    async def _workflow_register_and_mark_blinded(
        *,
        job: WorkflowJob,
        event_payload: dict[str, Any] | None = None,
    ) -> None:
        await _ensure_workflow_schema_ready()
        await judge_core.register_blinded(
            job=job,
            event_payload=event_payload,
        )

    async def _workflow_register_and_mark_case_built(
        *,
        job: WorkflowJob,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowJob:
        await _ensure_workflow_schema_ready()
        return await judge_core.register_case_built(
            job=job,
            event_payload=event_payload,
        )

    async def _workflow_mark_completed(
        *,
        job_id: int,
        event_payload: dict[str, Any] | None = None,
    ) -> None:
        await _ensure_workflow_schema_ready()
        payload = dict(event_payload or {})
        dispatch_type = str(payload.get("dispatchType") or "").strip().lower() or "unknown"
        completed_stage = str(payload.get("judgeCoreStage") or "").strip().lower()
        if not completed_stage:
            completed_stage = "review_approved" if payload.get("reviewDecision") else "reported"
        await judge_core.mark_reported(
            job_id=job_id,
            dispatch_type=dispatch_type,
            review_required=False,
            completed_stage=completed_stage,
            event_payload=payload,
        )

    async def _workflow_mark_review_required(
        *,
        job_id: int,
        event_payload: dict[str, Any] | None = None,
    ) -> None:
        await _ensure_workflow_schema_ready()
        payload = dict(event_payload or {})
        dispatch_type = str(payload.get("dispatchType") or "").strip().lower() or "unknown"
        await judge_core.mark_reported(
            job_id=job_id,
            dispatch_type=dispatch_type,
            review_required=True,
            event_payload=payload,
        )

    async def _workflow_mark_failed(
        *,
        job_id: int,
        error_code: str,
        error_message: str,
        event_payload: dict[str, Any] | None = None,
    ) -> None:
        await _ensure_workflow_schema_ready()
        payload = dict(event_payload or {})
        dispatch_type = str(payload.get("dispatchType") or "").strip().lower() or "unknown"
        failed_stage = str(payload.get("judgeCoreStage") or "").strip().lower()
        if not failed_stage:
            failed_stage = "review_rejected" if error_code == "review_rejected" else "blocked_failed"
        payload.setdefault("errorCode", error_code)
        payload.setdefault("errorMessage", error_message)
        payload["error"] = _build_error_contract(
            error_code=error_code,
            error_message=error_message,
            dispatch_type=dispatch_type,
            trace_id=str(payload.get("traceId") or ""),
            retryable=False,
            category="workflow_failed",
            details={
                "judgeCoreStage": failed_stage,
                "callbackStatus": payload.get("callbackStatus"),
            },
        )
        await judge_core.mark_failed(
            job_id=job_id,
            dispatch_type=dispatch_type,
            error_code=error_code,
            error_message=error_message,
            stage=failed_stage,
            event_payload=payload,
        )

    async def _workflow_mark_replay(
        *,
        job_id: int,
        dispatch_type: str,
        event_payload: dict[str, Any] | None = None,
    ) -> None:
        await _ensure_workflow_schema_ready()
        payload = dict(event_payload or {})
        try:
            await judge_core.mark_replay(
                job_id=job_id,
                dispatch_type=dispatch_type,
                event_payload=payload,
            )
        except LookupError:
            return

    async def _workflow_get_job(*, job_id: int) -> WorkflowJob | None:
        await _ensure_workflow_schema_ready()
        return await runtime.workflow_runtime.orchestrator.get_job(job_id=job_id)

    async def _workflow_list_jobs(
        *,
        status: str | None,
        dispatch_type: str | None,
        limit: int,
    ) -> list[WorkflowJob]:
        await _ensure_workflow_schema_ready()
        return await runtime.workflow_runtime.orchestrator.list_jobs(
            status=status,
            dispatch_type=dispatch_type,
            limit=limit,
        )

    async def _workflow_list_events(*, job_id: int):
        await _ensure_workflow_schema_ready()
        return await runtime.workflow_runtime.orchestrator.list_events(job_id=job_id)

    @app.get("/healthz")
    async def healthz() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/internal/judge/policies")
    async def list_judge_policies(
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        profiles = runtime.policy_registry_runtime.list_profiles()
        return {
            "defaultVersion": runtime.policy_registry_runtime.default_version,
            "count": len(profiles),
            "items": [
                _serialize_policy_profile(runtime, profile=item)
                for item in profiles
            ],
        }

    @app.get("/internal/judge/policies/{policy_version}")
    async def get_judge_policy(
        policy_version: str,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        profile = runtime.policy_registry_runtime.get_profile(policy_version)
        if profile is None:
            raise HTTPException(status_code=404, detail="judge_policy_not_found")
        return {
            "item": _serialize_policy_profile(runtime, profile=profile),
        }

    @app.post("/internal/judge/cases")
    async def create_judge_case(
        request: Request,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        try:
            raw_payload = await request.json()
        except Exception as err:
            raise HTTPException(status_code=422, detail=f"invalid_json: {err}") from err
        if not isinstance(raw_payload, dict):
            raise HTTPException(status_code=422, detail="invalid_payload")
        try:
            parsed = CaseCreateRequest.model_validate(raw_payload)
        except ValidationError as err:
            raise HTTPException(status_code=422, detail=err.errors()) from err
        replayed = _resolve_idempotency_or_raise(
            runtime=runtime,
            key=parsed.idempotency_key,
            job_id=parsed.case_id,
            conflict_detail="idempotency_conflict:case_create",
        )
        if replayed is not None:
            return replayed
        policy_profile = _resolve_policy_profile_or_raise(
            runtime=runtime,
            judge_policy_version=parsed.judge_policy_version,
            rubric_version=parsed.rubric_version,
            topic_domain=parsed.topic_domain,
        )
        existing_job = await _workflow_get_job(job_id=parsed.case_id)
        if existing_job is not None:
            raise HTTPException(status_code=409, detail="case_already_exists")

        request_payload = parsed.model_dump(mode="json")
        workflow_job = _build_workflow_job(
            dispatch_type="phase",
            job_id=parsed.case_id,
            trace_id=parsed.trace_id,
            scope_id=parsed.scope_id,
            session_id=parsed.session_id,
            idempotency_key=parsed.idempotency_key,
            rubric_version=parsed.rubric_version,
            judge_policy_version=parsed.judge_policy_version,
            topic_domain=parsed.topic_domain,
            retrieval_profile=parsed.retrieval_profile,
        )
        transitioned_job = await _workflow_register_and_mark_case_built(
            job=workflow_job,
            event_payload={
                "dispatchType": "case",
                "scopeId": parsed.scope_id,
                "sessionId": parsed.session_id,
                "traceId": parsed.trace_id,
                "policyVersion": policy_profile.version,
                "caseStatus": "case_built",
            },
        )
        response = {
            "accepted": True,
            "status": "case_built",
            "caseId": parsed.case_id,
            "scopeId": parsed.scope_id,
            "sessionId": parsed.session_id,
            "traceId": parsed.trace_id,
            "idempotencyKey": parsed.idempotency_key,
            "workflow": _serialize_workflow_job(transitioned_job),
        }
        runtime.trace_store.register_start(
            job_id=parsed.case_id,
            trace_id=parsed.trace_id,
            request=request_payload,
        )
        runtime.trace_store.register_success(
            job_id=parsed.case_id,
            response=response,
            callback_status="case_built",
            report_summary=_build_trace_report_summary(
                dispatch_type="case",
                payload={},
                callback_status="case_built",
                callback_error=None,
            ),
        )
        runtime.trace_store.set_idempotency_success(
            key=parsed.idempotency_key,
            job_id=parsed.case_id,
            response=response,
            ttl_secs=runtime.settings.idempotency_ttl_secs,
        )
        return response

    async def _handle_blindization_rejection(
        *,
        dispatch_type: str,
        raw_payload: dict[str, Any],
        sensitive_hits: list[str],
    ) -> None:
        meta = _extract_dispatch_meta_from_raw(raw_payload)
        job_id = int(meta.get("caseId") or 0)
        session_id = int(meta.get("sessionId") or 0)
        trace_id = str(meta.get("traceId") or "")
        if job_id <= 0 or session_id <= 0 or not trace_id:
            raise HTTPException(status_code=422, detail="input_not_blinded")
        scope_id = int(meta.get("scopeId") or 1)
        dims = _extract_receipt_dims_from_raw(dispatch_type, raw_payload)
        request_payload = dict(raw_payload)
        workflow_job = _build_workflow_job(
            dispatch_type=dispatch_type,
            job_id=job_id,
            trace_id=trace_id,
            scope_id=scope_id,
            session_id=session_id,
            idempotency_key=str(meta.get("idempotencyKey") or ""),
            rubric_version=str(meta.get("rubricVersion") or ""),
            judge_policy_version=str(meta.get("judgePolicyVersion") or ""),
            topic_domain=str(meta.get("topicDomain") or ""),
            retrieval_profile=(
                str(meta.get("retrievalProfile")) if meta.get("retrievalProfile") is not None else None
            ),
        )
        runtime.trace_store.register_start(job_id=job_id, trace_id=trace_id, request=request_payload)
        await _workflow_register_and_mark_blinded(
            job=workflow_job,
            event_payload={
                "dispatchType": dispatch_type,
                "scopeId": scope_id,
                "sessionId": session_id,
                "phaseNo": dims.get("phaseNo"),
                "phaseStartNo": dims.get("phaseStartNo"),
                "phaseEndNo": dims.get("phaseEndNo"),
                "messageCount": dims.get("messageCount"),
                "traceId": trace_id,
                "rejectionCode": "input_not_blinded",
                "sensitiveHits": sensitive_hits[:12],
            },
        )
        response = {
            "accepted": False,
            "dispatchType": dispatch_type,
            "status": "callback_failed",
            "caseId": job_id,
            "scopeId": scope_id,
            "sessionId": session_id,
            "traceId": trace_id,
        }
        if dispatch_type == "phase":
            response["phaseNo"] = dims.get("phaseNo")
            response["messageCount"] = dims.get("messageCount")
        else:
            response["phaseStartNo"] = dims.get("phaseStartNo")
            response["phaseEndNo"] = dims.get("phaseEndNo")

        error_code = "input_not_blinded"
        error_message = (
            "sensitive fields detected in judge input: " + ",".join(sensitive_hits[:12])
        )
        failed_payload = _build_failed_callback_payload(
            case_id=job_id,
            dispatch_type=dispatch_type,
            trace_id=trace_id,
            error_code=error_code,
            error_message=error_message,
        )
        failed_callback_fn = _failed_callback_fn_for_dispatch(runtime, dispatch_type)
        try:
            failed_attempts, failed_retries = await _invoke_v3_callback_with_retry(
                runtime=runtime,
                callback_fn=failed_callback_fn,
                job_id=job_id,
                payload=failed_payload,
            )
        except Exception as failed_err:
            receipt_response = _with_error_contract(
                {
                    **response,
                    "callbackStatus": "failed_callback_failed",
                    "callbackError": error_message,
                    "failedCallbackPayload": failed_payload,
                    "failedCallbackError": str(failed_err),
                },
                error_code=f"{dispatch_type}_failed_callback_failed",
                error_message=str(failed_err),
                dispatch_type=dispatch_type,
                trace_id=trace_id,
                retryable=False,
                category="blindization_rejection",
                details={"sensitiveHits": sensitive_hits[:12]},
            )
            await _persist_dispatch_receipt(
                dispatch_type=dispatch_type,
                job_id=job_id,
                scope_id=scope_id,
                session_id=session_id,
                trace_id=trace_id,
                idempotency_key=str(meta.get("idempotencyKey") or ""),
                rubric_version=str(meta.get("rubricVersion") or ""),
                judge_policy_version=str(meta.get("judgePolicyVersion") or ""),
                topic_domain=str(meta.get("topicDomain") or ""),
                retrieval_profile=(
                    str(meta.get("retrievalProfile")) if meta.get("retrievalProfile") is not None else None
                ),
                phase_no=dims.get("phaseNo"),
                phase_start_no=dims.get("phaseStartNo"),
                phase_end_no=dims.get("phaseEndNo"),
                message_start_id=dims.get("messageStartId"),
                message_end_id=dims.get("messageEndId"),
                message_count=dims.get("messageCount"),
                status="callback_failed",
                request_payload=request_payload,
                response_payload=receipt_response,
            )
            runtime.trace_store.register_failure(
                job_id=job_id,
                response=receipt_response,
                callback_status="failed_callback_failed",
                callback_error=str(failed_err),
            )
            await _workflow_mark_failed(
                job_id=job_id,
                error_code=f"{dispatch_type}_failed_callback_failed",
                error_message=str(failed_err),
                event_payload={
                    "dispatchType": dispatch_type,
                    "phaseNo": dims.get("phaseNo"),
                    "phaseStartNo": dims.get("phaseStartNo"),
                    "phaseEndNo": dims.get("phaseEndNo"),
                    "callbackStatus": "failed_callback_failed",
                    "sensitiveHits": sensitive_hits[:12],
                },
            )
            raise HTTPException(
                status_code=502,
                detail=f"{dispatch_type}_failed_callback_failed: {failed_err}",
            ) from failed_err

        receipt_response = _with_error_contract(
            {
                **response,
                "callbackStatus": "failed_reported",
                "callbackError": error_message,
                "failedCallbackPayload": failed_payload,
                "failedCallbackAttempts": failed_attempts,
                "failedCallbackRetries": failed_retries,
            },
            error_code=error_code,
            error_message=error_message,
            dispatch_type=dispatch_type,
            trace_id=trace_id,
            retryable=False,
            category="blindization_rejection",
            details={"sensitiveHits": sensitive_hits[:12]},
        )
        await _persist_dispatch_receipt(
            dispatch_type=dispatch_type,
            job_id=job_id,
            scope_id=scope_id,
            session_id=session_id,
            trace_id=trace_id,
            idempotency_key=str(meta.get("idempotencyKey") or ""),
            rubric_version=str(meta.get("rubricVersion") or ""),
            judge_policy_version=str(meta.get("judgePolicyVersion") or ""),
            topic_domain=str(meta.get("topicDomain") or ""),
            retrieval_profile=(
                str(meta.get("retrievalProfile")) if meta.get("retrievalProfile") is not None else None
            ),
            phase_no=dims.get("phaseNo"),
            phase_start_no=dims.get("phaseStartNo"),
            phase_end_no=dims.get("phaseEndNo"),
            message_start_id=dims.get("messageStartId"),
            message_end_id=dims.get("messageEndId"),
            message_count=dims.get("messageCount"),
            status="callback_failed",
            request_payload=request_payload,
            response_payload=receipt_response,
        )
        runtime.trace_store.register_failure(
            job_id=job_id,
            response=receipt_response,
            callback_status="failed_reported",
            callback_error=error_message,
        )
        await _workflow_mark_failed(
            job_id=job_id,
            error_code=error_code,
            error_message=error_message,
            event_payload={
                "dispatchType": dispatch_type,
                "phaseNo": dims.get("phaseNo"),
                "phaseStartNo": dims.get("phaseStartNo"),
                "phaseEndNo": dims.get("phaseEndNo"),
                "callbackStatus": "failed_reported",
                "sensitiveHits": sensitive_hits[:12],
            },
        )
        raise HTTPException(status_code=422, detail=error_code)

    @app.post("/internal/judge/v3/phase/dispatch")
    async def dispatch_judge_phase(
        request: Request,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        try:
            raw_payload = await request.json()
        except Exception as err:
            raise HTTPException(status_code=422, detail=f"invalid_json: {err}") from err
        if not isinstance(raw_payload, dict):
            raise HTTPException(status_code=422, detail="invalid_payload")
        sensitive_hits = _find_sensitive_key_hits(raw_payload)
        if sensitive_hits:
            await _handle_blindization_rejection(
                dispatch_type="phase",
                raw_payload=raw_payload,
                sensitive_hits=sensitive_hits,
            )
        try:
            parsed = PhaseDispatchRequest.model_validate(raw_payload)
        except ValidationError as err:
            raise HTTPException(status_code=422, detail=err.errors()) from err
        _validate_phase_dispatch_request(parsed)

        replayed = _resolve_idempotency_or_raise(
            runtime=runtime,
            key=parsed.idempotency_key,
            job_id=parsed.case_id,
            conflict_detail="idempotency_conflict:phase_dispatch",
        )
        if replayed is not None:
            return replayed
        policy_profile = _resolve_policy_profile_or_raise(
            runtime=runtime,
            judge_policy_version=parsed.judge_policy_version,
            rubric_version=parsed.rubric_version,
            topic_domain=parsed.topic_domain,
        )

        response = {
            "accepted": True,
            "dispatchType": "phase",
            "status": "queued",
            "caseId": parsed.case_id,
            "scopeId": parsed.scope_id,
            "sessionId": parsed.session_id,
            "phaseNo": parsed.phase_no,
            "messageCount": parsed.message_count,
            "traceId": parsed.trace_id,
        }
        request_payload = parsed.model_dump(mode="json")
        workflow_job = _build_workflow_job(
            dispatch_type="phase",
            job_id=parsed.case_id,
            trace_id=parsed.trace_id,
            scope_id=parsed.scope_id,
            session_id=parsed.session_id,
            idempotency_key=parsed.idempotency_key,
            rubric_version=parsed.rubric_version,
            judge_policy_version=parsed.judge_policy_version,
            topic_domain=parsed.topic_domain,
            retrieval_profile=parsed.retrieval_profile,
        )
        runtime.trace_store.register_start(
            job_id=parsed.case_id,
            trace_id=parsed.trace_id,
            request=request_payload,
        )
        await _persist_dispatch_receipt(
            dispatch_type="phase",
            job_id=parsed.case_id,
            scope_id=parsed.scope_id,
            session_id=parsed.session_id,
            trace_id=parsed.trace_id,
            idempotency_key=parsed.idempotency_key,
            rubric_version=parsed.rubric_version,
            judge_policy_version=parsed.judge_policy_version,
            topic_domain=parsed.topic_domain,
            retrieval_profile=parsed.retrieval_profile,
            phase_no=parsed.phase_no,
            phase_start_no=None,
            phase_end_no=None,
            message_start_id=parsed.message_start_id,
            message_end_id=parsed.message_end_id,
            message_count=parsed.message_count,
            status="queued",
            request_payload=request_payload,
            response_payload=response,
        )
        await _workflow_register_and_mark_blinded(
            job=workflow_job,
            event_payload={
                "dispatchType": "phase",
                "scopeId": parsed.scope_id,
                "sessionId": parsed.session_id,
                "phaseNo": parsed.phase_no,
                "messageCount": parsed.message_count,
                "traceId": parsed.trace_id,
                "policyVersion": policy_profile.version,
            },
        )

        phase_report_payload = await build_phase_report_payload_v3_phase(
            request=parsed,
            settings=runtime.settings,
            gateway_runtime=runtime.gateway_runtime,
        )
        await _attach_judge_agent_runtime_trace(
            runtime=runtime,
            report_payload=phase_report_payload,
            dispatch_type="phase",
            case_id=parsed.case_id,
            scope_id=parsed.scope_id,
            session_id=parsed.session_id,
            trace_id=parsed.trace_id,
            phase_no=parsed.phase_no,
        )
        _attach_policy_trace_snapshot(
            runtime=runtime,
            report_payload=phase_report_payload,
            profile=policy_profile,
        )
        _attach_report_attestation(
            report_payload=phase_report_payload,
            dispatch_type="phase",
        )
        try:
            callback_attempts, callback_retries = await _invoke_v3_callback_with_retry(
                runtime=runtime,
                callback_fn=_report_callback_fn_for_dispatch(runtime, "phase"),
                job_id=parsed.case_id,
                payload=phase_report_payload,
            )
        except Exception as err:
            error_code = "phase_callback_retry_exhausted"
            error_message = str(err)
            failed_payload = _build_failed_callback_payload(
                case_id=parsed.case_id,
                dispatch_type="phase",
                trace_id=parsed.trace_id,
                error_code=error_code,
                error_message=error_message,
                degradation_level=int(phase_report_payload.get("degradationLevel") or 0),
            )
            try:
                failed_attempts, failed_retries = await _invoke_v3_callback_with_retry(
                    runtime=runtime,
                    callback_fn=_failed_callback_fn_for_dispatch(runtime, "phase"),
                    job_id=parsed.case_id,
                    payload=failed_payload,
                )
            except Exception as failed_err:
                receipt_response = _with_error_contract(
                    {
                        **response,
                        "status": "callback_failed",
                        "callbackStatus": "failed_callback_failed",
                        "callbackError": error_message,
                        "reportPayload": phase_report_payload,
                        "failedCallbackPayload": failed_payload,
                        "failedCallbackError": str(failed_err),
                    },
                    error_code="phase_failed_callback_failed",
                    error_message=str(failed_err),
                    dispatch_type="phase",
                    trace_id=parsed.trace_id,
                    retryable=False,
                    category="callback_delivery",
                    details={"reportError": error_message},
                )
                await _persist_dispatch_receipt(
                    dispatch_type="phase",
                    job_id=parsed.case_id,
                    scope_id=parsed.scope_id,
                    session_id=parsed.session_id,
                    trace_id=parsed.trace_id,
                    idempotency_key=parsed.idempotency_key,
                    rubric_version=parsed.rubric_version,
                    judge_policy_version=parsed.judge_policy_version,
                    topic_domain=parsed.topic_domain,
                    retrieval_profile=parsed.retrieval_profile,
                    phase_no=parsed.phase_no,
                    phase_start_no=None,
                    phase_end_no=None,
                    message_start_id=parsed.message_start_id,
                    message_end_id=parsed.message_end_id,
                    message_count=parsed.message_count,
                    status="callback_failed",
                    request_payload=request_payload,
                    response_payload=receipt_response,
                )
                runtime.trace_store.register_failure(
                    job_id=parsed.case_id,
                    response=receipt_response,
                    callback_status="failed_callback_failed",
                    callback_error=str(failed_err),
                )
                await _workflow_mark_failed(
                    job_id=parsed.case_id,
                    error_code="phase_failed_callback_failed",
                    error_message=str(failed_err),
                    event_payload={
                        "dispatchType": "phase",
                        "phaseNo": parsed.phase_no,
                        "callbackStatus": "failed_callback_failed",
                    },
                )
                runtime.trace_store.clear_idempotency(parsed.idempotency_key)
                raise HTTPException(
                    status_code=502,
                    detail=f"phase_failed_callback_failed: {failed_err}",
                ) from failed_err

            receipt_response = _with_error_contract(
                {
                    **response,
                    "status": "callback_failed",
                    "callbackStatus": "failed_reported",
                    "callbackError": error_message,
                    "reportPayload": phase_report_payload,
                    "failedCallbackPayload": failed_payload,
                    "failedCallbackAttempts": failed_attempts,
                    "failedCallbackRetries": failed_retries,
                },
                error_code=error_code,
                error_message=error_message,
                dispatch_type="phase",
                trace_id=parsed.trace_id,
                retryable=False,
                category="callback_delivery",
                details={
                    "failedCallbackAttempts": failed_attempts,
                    "failedCallbackRetries": failed_retries,
                },
            )
            await _persist_dispatch_receipt(
                dispatch_type="phase",
                job_id=parsed.case_id,
                scope_id=parsed.scope_id,
                session_id=parsed.session_id,
                trace_id=parsed.trace_id,
                idempotency_key=parsed.idempotency_key,
                rubric_version=parsed.rubric_version,
                judge_policy_version=parsed.judge_policy_version,
                topic_domain=parsed.topic_domain,
                retrieval_profile=parsed.retrieval_profile,
                phase_no=parsed.phase_no,
                phase_start_no=None,
                phase_end_no=None,
                message_start_id=parsed.message_start_id,
                message_end_id=parsed.message_end_id,
                message_count=parsed.message_count,
                status="callback_failed",
                request_payload=request_payload,
                response_payload=receipt_response,
            )
            runtime.trace_store.register_failure(
                job_id=parsed.case_id,
                response=receipt_response,
                callback_status="failed_reported",
                callback_error=error_message,
            )
            await _workflow_mark_failed(
                job_id=parsed.case_id,
                error_code=error_code,
                error_message=error_message,
                event_payload={
                    "dispatchType": "phase",
                    "phaseNo": parsed.phase_no,
                    "callbackStatus": "failed_reported",
                },
            )
            runtime.trace_store.clear_idempotency(parsed.idempotency_key)
            raise HTTPException(status_code=502, detail=f"phase_callback_failed: {err}") from err

        reported_response = {
            **response,
            "callbackStatus": "reported",
            "callbackAttempts": callback_attempts,
            "callbackRetries": callback_retries,
            "reportPayload": phase_report_payload,
        }
        await _persist_dispatch_receipt(
            dispatch_type="phase",
            job_id=parsed.case_id,
            scope_id=parsed.scope_id,
            session_id=parsed.session_id,
            trace_id=parsed.trace_id,
            idempotency_key=parsed.idempotency_key,
            rubric_version=parsed.rubric_version,
            judge_policy_version=parsed.judge_policy_version,
            topic_domain=parsed.topic_domain,
            retrieval_profile=parsed.retrieval_profile,
            phase_no=parsed.phase_no,
            phase_start_no=None,
            phase_end_no=None,
            message_start_id=parsed.message_start_id,
            message_end_id=parsed.message_end_id,
            message_count=parsed.message_count,
            status="reported",
            request_payload=request_payload,
            response_payload=reported_response,
        )
        runtime.trace_store.register_success(
            job_id=parsed.case_id,
            response=reported_response,
            callback_status="reported",
            report_summary=_build_trace_report_summary(
                dispatch_type="phase",
                payload=phase_report_payload,
                callback_status="reported",
                callback_error=None,
            ),
        )
        await _workflow_mark_completed(
            job_id=parsed.case_id,
            event_payload={
                "dispatchType": "phase",
                "phaseNo": parsed.phase_no,
                "callbackStatus": "reported",
            },
        )
        runtime.trace_store.set_idempotency_success(
            key=parsed.idempotency_key,
            job_id=parsed.case_id,
            response=response,
            ttl_secs=runtime.settings.idempotency_ttl_secs,
        )
        return response

    @app.post("/internal/judge/v3/final/dispatch")
    async def dispatch_judge_final(
        request: Request,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        try:
            raw_payload = await request.json()
        except Exception as err:
            raise HTTPException(status_code=422, detail=f"invalid_json: {err}") from err
        if not isinstance(raw_payload, dict):
            raise HTTPException(status_code=422, detail="invalid_payload")
        sensitive_hits = _find_sensitive_key_hits(raw_payload)
        if sensitive_hits:
            await _handle_blindization_rejection(
                dispatch_type="final",
                raw_payload=raw_payload,
                sensitive_hits=sensitive_hits,
            )
        try:
            parsed = FinalDispatchRequest.model_validate(raw_payload)
        except ValidationError as err:
            raise HTTPException(status_code=422, detail=err.errors()) from err
        _validate_final_dispatch_request(parsed)

        replayed = _resolve_idempotency_or_raise(
            runtime=runtime,
            key=parsed.idempotency_key,
            job_id=parsed.case_id,
            conflict_detail="idempotency_conflict:final_dispatch",
        )
        if replayed is not None:
            return replayed
        policy_profile = _resolve_policy_profile_or_raise(
            runtime=runtime,
            judge_policy_version=parsed.judge_policy_version,
            rubric_version=parsed.rubric_version,
            topic_domain=parsed.topic_domain,
        )

        response = {
            "accepted": True,
            "dispatchType": "final",
            "status": "queued",
            "caseId": parsed.case_id,
            "scopeId": parsed.scope_id,
            "sessionId": parsed.session_id,
            "phaseStartNo": parsed.phase_start_no,
            "phaseEndNo": parsed.phase_end_no,
            "traceId": parsed.trace_id,
        }
        request_payload = parsed.model_dump(mode="json")
        workflow_job = _build_workflow_job(
            dispatch_type="final",
            job_id=parsed.case_id,
            trace_id=parsed.trace_id,
            scope_id=parsed.scope_id,
            session_id=parsed.session_id,
            idempotency_key=parsed.idempotency_key,
            rubric_version=parsed.rubric_version,
            judge_policy_version=parsed.judge_policy_version,
            topic_domain=parsed.topic_domain,
            retrieval_profile=None,
        )
        runtime.trace_store.register_start(
            job_id=parsed.case_id,
            trace_id=parsed.trace_id,
            request=request_payload,
        )
        await _persist_dispatch_receipt(
            dispatch_type="final",
            job_id=parsed.case_id,
            scope_id=parsed.scope_id,
            session_id=parsed.session_id,
            trace_id=parsed.trace_id,
            idempotency_key=parsed.idempotency_key,
            rubric_version=parsed.rubric_version,
            judge_policy_version=parsed.judge_policy_version,
            topic_domain=parsed.topic_domain,
            retrieval_profile=None,
            phase_no=None,
            phase_start_no=parsed.phase_start_no,
            phase_end_no=parsed.phase_end_no,
            message_start_id=None,
            message_end_id=None,
            message_count=None,
            status="queued",
            request_payload=request_payload,
            response_payload=response,
        )
        await _workflow_register_and_mark_blinded(
            job=workflow_job,
            event_payload={
                "dispatchType": "final",
                "scopeId": parsed.scope_id,
                "sessionId": parsed.session_id,
                "phaseStartNo": parsed.phase_start_no,
                "phaseEndNo": parsed.phase_end_no,
                "traceId": parsed.trace_id,
                "policyVersion": policy_profile.version,
            },
        )

        phase_receipts = await _list_dispatch_receipts(
            dispatch_type="phase",
            session_id=parsed.session_id,
            status="reported",
            limit=1000,
        )
        final_report_payload = _build_final_report_payload(
            runtime=runtime,
            request=parsed,
            phase_receipts=phase_receipts,
        )
        await _attach_judge_agent_runtime_trace(
            runtime=runtime,
            report_payload=final_report_payload,
            dispatch_type="final",
            case_id=parsed.case_id,
            scope_id=parsed.scope_id,
            session_id=parsed.session_id,
            trace_id=parsed.trace_id,
            phase_start_no=parsed.phase_start_no,
            phase_end_no=parsed.phase_end_no,
        )
        _attach_policy_trace_snapshot(
            runtime=runtime,
            report_payload=final_report_payload,
            profile=policy_profile,
        )
        _attach_report_attestation(
            report_payload=final_report_payload,
            dispatch_type="final",
        )
        contract_missing_fields = _validate_final_report_payload_contract(final_report_payload)
        if contract_missing_fields:
            error_text = "final_contract_violation: missing_fields=" + ",".join(
                contract_missing_fields[:12]
            )
            alert = runtime.trace_store.upsert_audit_alert(
                job_id=parsed.case_id,
                scope_id=parsed.scope_id,
                trace_id=parsed.trace_id,
                alert_type="final_contract_violation",
                severity="critical",
                title="AI Judge Final Contract Violation",
                message=error_text,
                details={
                    "dispatchType": "final",
                    "sessionId": parsed.session_id,
                    "phaseRange": {
                        "startNo": parsed.phase_start_no,
                        "endNo": parsed.phase_end_no,
                    },
                    "missingFields": contract_missing_fields,
                    "errorCode": "final_contract_blocked",
                },
            )
            await _sync_audit_alert_to_facts(alert=alert)
            failed_payload = _build_failed_callback_payload(
                case_id=parsed.case_id,
                dispatch_type="final",
                trace_id=parsed.trace_id,
                error_code="final_contract_blocked",
                error_message=error_text,
                audit_alert_ids=[alert.alert_id],
                degradation_level=int(final_report_payload.get("degradationLevel") or 0),
            )
            try:
                failed_attempts, failed_retries = await _invoke_v3_callback_with_retry(
                    runtime=runtime,
                    callback_fn=_failed_callback_fn_for_dispatch(runtime, "final"),
                    job_id=parsed.case_id,
                    payload=failed_payload,
                )
            except Exception as failed_err:
                receipt_response = _with_error_contract(
                    {
                        **response,
                        "status": "callback_failed",
                        "callbackStatus": "failed_callback_failed",
                        "callbackError": error_text,
                        "auditAlertIds": [alert.alert_id],
                        "reportPayload": final_report_payload,
                        "failedCallbackPayload": failed_payload,
                        "failedCallbackError": str(failed_err),
                    },
                    error_code="final_failed_callback_failed",
                    error_message=str(failed_err),
                    dispatch_type="final",
                    trace_id=parsed.trace_id,
                    retryable=False,
                    category="contract_blocked",
                    details={
                        "auditAlertId": alert.alert_id,
                        "blockedReason": error_text,
                    },
                )
                await _persist_dispatch_receipt(
                    dispatch_type="final",
                    job_id=parsed.case_id,
                    scope_id=parsed.scope_id,
                    session_id=parsed.session_id,
                    trace_id=parsed.trace_id,
                    idempotency_key=parsed.idempotency_key,
                    rubric_version=parsed.rubric_version,
                    judge_policy_version=parsed.judge_policy_version,
                    topic_domain=parsed.topic_domain,
                    retrieval_profile=None,
                    phase_no=None,
                    phase_start_no=parsed.phase_start_no,
                    phase_end_no=parsed.phase_end_no,
                    message_start_id=None,
                    message_end_id=None,
                    message_count=None,
                    status="callback_failed",
                    request_payload=request_payload,
                    response_payload=receipt_response,
                )
                runtime.trace_store.register_failure(
                    job_id=parsed.case_id,
                    response=receipt_response,
                    callback_status="failed_callback_failed",
                    callback_error=str(failed_err),
                )
                await _workflow_mark_failed(
                    job_id=parsed.case_id,
                    error_code="final_failed_callback_failed",
                    error_message=str(failed_err),
                    event_payload={
                        "dispatchType": "final",
                        "phaseStartNo": parsed.phase_start_no,
                        "phaseEndNo": parsed.phase_end_no,
                        "callbackStatus": "failed_callback_failed",
                    },
                )
                runtime.trace_store.clear_idempotency(parsed.idempotency_key)
                raise HTTPException(
                    status_code=502,
                    detail=f"final_failed_callback_failed: {failed_err}",
                ) from failed_err

            receipt_response = _with_error_contract(
                {
                    **response,
                    "status": "callback_failed",
                    "callbackStatus": "blocked_failed_reported",
                    "callbackError": error_text,
                    "auditAlertIds": [alert.alert_id],
                    "reportPayload": final_report_payload,
                    "failedCallbackPayload": failed_payload,
                    "failedCallbackAttempts": failed_attempts,
                    "failedCallbackRetries": failed_retries,
                },
                error_code="final_contract_blocked",
                error_message=error_text,
                dispatch_type="final",
                trace_id=parsed.trace_id,
                retryable=False,
                category="contract_blocked",
                details={
                    "auditAlertId": alert.alert_id,
                    "failedCallbackAttempts": failed_attempts,
                    "failedCallbackRetries": failed_retries,
                    "missingFields": contract_missing_fields[:12],
                },
            )
            await _persist_dispatch_receipt(
                dispatch_type="final",
                job_id=parsed.case_id,
                scope_id=parsed.scope_id,
                session_id=parsed.session_id,
                trace_id=parsed.trace_id,
                idempotency_key=parsed.idempotency_key,
                rubric_version=parsed.rubric_version,
                judge_policy_version=parsed.judge_policy_version,
                topic_domain=parsed.topic_domain,
                retrieval_profile=None,
                phase_no=None,
                phase_start_no=parsed.phase_start_no,
                phase_end_no=parsed.phase_end_no,
                message_start_id=None,
                message_end_id=None,
                message_count=None,
                status="callback_failed",
                request_payload=request_payload,
                response_payload=receipt_response,
            )
            runtime.trace_store.register_failure(
                job_id=parsed.case_id,
                response=receipt_response,
                callback_status="blocked_failed_reported",
                callback_error=error_text,
            )
            await _workflow_mark_failed(
                job_id=parsed.case_id,
                error_code="final_contract_blocked",
                error_message=error_text,
                event_payload={
                    "dispatchType": "final",
                    "phaseStartNo": parsed.phase_start_no,
                    "phaseEndNo": parsed.phase_end_no,
                    "callbackStatus": "blocked_failed_reported",
                    "missingFields": contract_missing_fields[:12],
                },
            )
            runtime.trace_store.clear_idempotency(parsed.idempotency_key)
            raise HTTPException(
                status_code=502,
                detail="final_contract_blocked: missing_critical_fields",
            )

        try:
            callback_attempts, callback_retries = await _invoke_v3_callback_with_retry(
                runtime=runtime,
                callback_fn=_report_callback_fn_for_dispatch(runtime, "final"),
                job_id=parsed.case_id,
                payload=final_report_payload,
            )
        except Exception as err:
            error_code = "final_callback_retry_exhausted"
            error_message = str(err)
            failed_payload = _build_failed_callback_payload(
                case_id=parsed.case_id,
                dispatch_type="final",
                trace_id=parsed.trace_id,
                error_code=error_code,
                error_message=error_message,
                degradation_level=int(final_report_payload.get("degradationLevel") or 0),
            )
            try:
                failed_attempts, failed_retries = await _invoke_v3_callback_with_retry(
                    runtime=runtime,
                    callback_fn=_failed_callback_fn_for_dispatch(runtime, "final"),
                    job_id=parsed.case_id,
                    payload=failed_payload,
                )
            except Exception as failed_err:
                receipt_response = _with_error_contract(
                    {
                        **response,
                        "status": "callback_failed",
                        "callbackStatus": "failed_callback_failed",
                        "callbackError": error_message,
                        "reportPayload": final_report_payload,
                        "failedCallbackPayload": failed_payload,
                        "failedCallbackError": str(failed_err),
                    },
                    error_code="final_failed_callback_failed",
                    error_message=str(failed_err),
                    dispatch_type="final",
                    trace_id=parsed.trace_id,
                    retryable=False,
                    category="callback_delivery",
                    details={"reportError": error_message},
                )
                await _persist_dispatch_receipt(
                    dispatch_type="final",
                    job_id=parsed.case_id,
                    scope_id=parsed.scope_id,
                    session_id=parsed.session_id,
                    trace_id=parsed.trace_id,
                    idempotency_key=parsed.idempotency_key,
                    rubric_version=parsed.rubric_version,
                    judge_policy_version=parsed.judge_policy_version,
                    topic_domain=parsed.topic_domain,
                    retrieval_profile=None,
                    phase_no=None,
                    phase_start_no=parsed.phase_start_no,
                    phase_end_no=parsed.phase_end_no,
                    message_start_id=None,
                    message_end_id=None,
                    message_count=None,
                    status="callback_failed",
                    request_payload=request_payload,
                    response_payload=receipt_response,
                )
                runtime.trace_store.register_failure(
                    job_id=parsed.case_id,
                    response=receipt_response,
                    callback_status="failed_callback_failed",
                    callback_error=str(failed_err),
                )
                await _workflow_mark_failed(
                    job_id=parsed.case_id,
                    error_code="final_failed_callback_failed",
                    error_message=str(failed_err),
                    event_payload={
                        "dispatchType": "final",
                        "phaseStartNo": parsed.phase_start_no,
                        "phaseEndNo": parsed.phase_end_no,
                        "callbackStatus": "failed_callback_failed",
                    },
                )
                runtime.trace_store.clear_idempotency(parsed.idempotency_key)
                raise HTTPException(
                    status_code=502,
                    detail=f"final_failed_callback_failed: {failed_err}",
                ) from failed_err

            receipt_response = _with_error_contract(
                {
                    **response,
                    "status": "callback_failed",
                    "callbackStatus": "failed_reported",
                    "callbackError": error_message,
                    "reportPayload": final_report_payload,
                    "failedCallbackPayload": failed_payload,
                    "failedCallbackAttempts": failed_attempts,
                    "failedCallbackRetries": failed_retries,
                },
                error_code=error_code,
                error_message=error_message,
                dispatch_type="final",
                trace_id=parsed.trace_id,
                retryable=False,
                category="callback_delivery",
                details={
                    "failedCallbackAttempts": failed_attempts,
                    "failedCallbackRetries": failed_retries,
                },
            )
            await _persist_dispatch_receipt(
                dispatch_type="final",
                job_id=parsed.case_id,
                scope_id=parsed.scope_id,
                session_id=parsed.session_id,
                trace_id=parsed.trace_id,
                idempotency_key=parsed.idempotency_key,
                rubric_version=parsed.rubric_version,
                judge_policy_version=parsed.judge_policy_version,
                topic_domain=parsed.topic_domain,
                retrieval_profile=None,
                phase_no=None,
                phase_start_no=parsed.phase_start_no,
                phase_end_no=parsed.phase_end_no,
                message_start_id=None,
                message_end_id=None,
                message_count=None,
                status="callback_failed",
                request_payload=request_payload,
                response_payload=receipt_response,
            )
            runtime.trace_store.register_failure(
                job_id=parsed.case_id,
                response=receipt_response,
                callback_status="failed_reported",
                callback_error=error_message,
            )
            await _workflow_mark_failed(
                job_id=parsed.case_id,
                error_code=error_code,
                error_message=error_message,
                event_payload={
                    "dispatchType": "final",
                    "phaseStartNo": parsed.phase_start_no,
                    "phaseEndNo": parsed.phase_end_no,
                    "callbackStatus": "failed_reported",
                },
            )
            runtime.trace_store.clear_idempotency(parsed.idempotency_key)
            raise HTTPException(status_code=502, detail=f"final_callback_failed: {err}") from err

        reported_response = {
            **response,
            "callbackStatus": "reported",
            "callbackAttempts": callback_attempts,
            "callbackRetries": callback_retries,
            "reportPayload": final_report_payload,
        }
        await _persist_dispatch_receipt(
            dispatch_type="final",
            job_id=parsed.case_id,
            scope_id=parsed.scope_id,
            session_id=parsed.session_id,
            trace_id=parsed.trace_id,
            idempotency_key=parsed.idempotency_key,
            rubric_version=parsed.rubric_version,
            judge_policy_version=parsed.judge_policy_version,
            topic_domain=parsed.topic_domain,
            retrieval_profile=None,
            phase_no=None,
            phase_start_no=parsed.phase_start_no,
            phase_end_no=parsed.phase_end_no,
            message_start_id=None,
            message_end_id=None,
            message_count=None,
            status="reported",
            request_payload=request_payload,
            response_payload=reported_response,
        )
        runtime.trace_store.register_success(
            job_id=parsed.case_id,
            response=reported_response,
            callback_status="reported",
            report_summary=_build_trace_report_summary(
                dispatch_type="final",
                payload=final_report_payload,
                callback_status="reported",
                callback_error=None,
            ),
        )
        review_required = bool(final_report_payload.get("reviewRequired"))
        workflow_event_payload = {
            "dispatchType": "final",
            "phaseStartNo": parsed.phase_start_no,
            "phaseEndNo": parsed.phase_end_no,
            "callbackStatus": "reported",
            "winner": final_report_payload.get("winner"),
            "reviewRequired": review_required,
            "errorCodes": (
                final_report_payload.get("errorCodes")
                if isinstance(final_report_payload.get("errorCodes"), list)
                else []
            ),
        }
        if review_required:
            await _workflow_mark_review_required(
                job_id=parsed.case_id,
                event_payload=workflow_event_payload,
            )
        else:
            await _workflow_mark_completed(
                job_id=parsed.case_id,
                event_payload=workflow_event_payload,
            )
        runtime.trace_store.set_idempotency_success(
            key=parsed.idempotency_key,
            job_id=parsed.case_id,
            response=response,
            ttl_secs=runtime.settings.idempotency_ttl_secs,
        )
        return response

    @app.get("/internal/judge/v3/phase/cases/{case_id}/receipt")
    async def get_phase_dispatch_receipt(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        item = await _get_dispatch_receipt(dispatch_type="phase", job_id=case_id)
        if item is None:
            raise HTTPException(status_code=404, detail="phase_dispatch_receipt_not_found")
        return _serialize_dispatch_receipt(item)

    @app.get("/internal/judge/v3/final/cases/{case_id}/receipt")
    async def get_final_dispatch_receipt(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        item = await _get_dispatch_receipt(dispatch_type="final", job_id=case_id)
        if item is None:
            raise HTTPException(status_code=404, detail="final_dispatch_receipt_not_found")
        return _serialize_dispatch_receipt(item)

    @app.get("/internal/judge/cases/{case_id}")
    async def get_judge_case(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        workflow_job = await _workflow_get_job(job_id=case_id)
        workflow_events = (
            await _workflow_list_events(job_id=case_id)
            if workflow_job is not None
            else []
        )
        final_receipt = await _get_dispatch_receipt(dispatch_type="final", job_id=case_id)
        phase_receipt = await _get_dispatch_receipt(dispatch_type="phase", job_id=case_id)
        trace = runtime.trace_store.get_trace(case_id)
        replay_records = await _list_replay_records(job_id=case_id, limit=50)
        alerts = await _list_audit_alerts(job_id=case_id, status=None, limit=200)
        if (
            workflow_job is None
            and final_receipt is None
            and phase_receipt is None
            and trace is None
            and not replay_records
            and not alerts
        ):
            raise HTTPException(status_code=404, detail="case_not_found")

        report_summary = (
            trace.report_summary if trace and isinstance(trace.report_summary, dict) else {}
        )
        final_response = (
            final_receipt.response if final_receipt and isinstance(final_receipt.response, dict) else {}
        )
        phase_response = (
            phase_receipt.response if phase_receipt and isinstance(phase_receipt.response, dict) else {}
        )
        summary_payload = (
            report_summary.get("payload")
            if isinstance(report_summary.get("payload"), dict)
            else {}
        )
        final_report_payload = (
            final_response.get("reportPayload")
            if isinstance(final_response.get("reportPayload"), dict)
            else {}
        )
        phase_report_payload = (
            phase_response.get("reportPayload")
            if isinstance(phase_response.get("reportPayload"), dict)
            else {}
        )
        report_payload = final_report_payload or summary_payload or phase_report_payload
        verdict_contract = _build_verdict_contract(report_payload)
        case_evidence = _build_case_evidence_view(
            report_payload=report_payload,
            verdict_contract=verdict_contract,
        )
        winner_raw = (
            report_summary.get("winner")
            or verdict_contract.get("winner")
            or final_response.get("winner")
            or phase_response.get("winner")
        )
        winner = str(winner_raw or "").strip().lower() or None
        callback_status = (
            report_summary.get("callbackStatus")
            or (trace.callback_status if trace is not None else None)
            or final_response.get("callbackStatus")
            or phase_response.get("callbackStatus")
        )
        callback_error = (
            report_summary.get("callbackError")
            or (trace.callback_error if trace is not None else None)
            or final_response.get("callbackError")
            or phase_response.get("callbackError")
        )
        judge_core_view = _build_judge_core_view(
            workflow_job=workflow_job,
            workflow_events=workflow_events,
        )
        if replay_records:
            replay_items = [
                {
                    "dispatchType": item.dispatch_type,
                    "traceId": item.trace_id,
                    "replayedAt": item.created_at.isoformat(),
                    "winner": item.winner,
                    "needsDrawVote": item.needs_draw_vote,
                    "provider": item.provider,
                }
                for item in replay_records
            ]
        else:
            replay_items = [
                {
                    "dispatchType": None,
                    "traceId": trace.trace_id if trace is not None else None,
                    "replayedAt": item.replayed_at.isoformat(),
                    "winner": item.winner,
                    "needsDrawVote": item.needs_draw_vote,
                    "provider": item.provider,
                }
                for item in (trace.replays if trace is not None else [])
            ]

        return {
            "caseId": case_id,
            "workflow": _serialize_workflow_job(workflow_job) if workflow_job else None,
            "trace": (
                {
                    "traceId": trace.trace_id,
                    "status": trace.status,
                    "createdAt": trace.created_at.isoformat(),
                    "updatedAt": trace.updated_at.isoformat(),
                }
                if trace is not None
                else None
            ),
            "receipts": {
                "phase": _serialize_dispatch_receipt(phase_receipt) if phase_receipt else None,
                "final": _serialize_dispatch_receipt(final_receipt) if final_receipt else None,
            },
            "latestDispatchType": "final" if final_receipt is not None else ("phase" if phase_receipt is not None else None),
            "reportPayload": report_payload,
            "verdictContract": verdict_contract,
            "caseEvidence": case_evidence,
            "winner": winner,
            "needsDrawVote": (
                verdict_contract.get("needsDrawVote")
                if verdict_contract.get("needsDrawVote") is not None
                else (winner == "draw" if winner is not None else None)
            ),
            "reviewRequired": bool(verdict_contract.get("reviewRequired")),
            "callbackStatus": callback_status,
            "callbackError": callback_error,
            "judgeCore": judge_core_view,
            "events": [
                {
                    "eventSeq": item.event_seq,
                    "eventType": item.event_type,
                    "payload": item.payload,
                    "createdAt": item.created_at.isoformat(),
                }
                for item in workflow_events
            ],
            "alerts": [_serialize_alert_item(item) for item in alerts],
            "replays": replay_items,
        }

    @app.get("/internal/judge/cases/{case_id}/trace")
    async def get_judge_job_trace(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        record = runtime.trace_store.get_trace(case_id)
        if record is None:
            raise HTTPException(status_code=404, detail="judge_trace_not_found")
        replay_records = await _list_replay_records(job_id=case_id, limit=50)
        replay_items = (
            [
                {
                    "replayedAt": item.created_at.isoformat(),
                    "winner": item.winner,
                    "needsDrawVote": item.needs_draw_vote,
                    "provider": item.provider,
                }
                for item in replay_records
            ]
            if replay_records
            else [
                {
                    "replayedAt": item.replayed_at.isoformat(),
                    "winner": item.winner,
                    "needsDrawVote": item.needs_draw_vote,
                    "provider": item.provider,
                }
                for item in record.replays
            ]
        )
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
            "reportSummary": record.report_summary,
            "verdictContract": _build_verdict_contract(
                record.report_summary.get("payload")
                if isinstance(record.report_summary, dict)
                and isinstance(record.report_summary.get("payload"), dict)
                else {}
            ),
            "replays": replay_items,
        }

    @app.post("/internal/judge/cases/{case_id}/replay")
    async def replay_judge_job(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        dispatch_type_normalized = str(dispatch_type or "auto").strip().lower()
        if dispatch_type_normalized not in {"auto", "phase", "final"}:
            raise HTTPException(status_code=422, detail="invalid_dispatch_type")

        chosen_dispatch_type = dispatch_type_normalized
        chosen_receipt = None
        if dispatch_type_normalized == "auto":
            final_receipt = await _get_dispatch_receipt(
                dispatch_type="final",
                job_id=case_id,
            )
            phase_receipt = await _get_dispatch_receipt(
                dispatch_type="phase",
                job_id=case_id,
            )
            chosen_receipt = final_receipt or phase_receipt
            if chosen_receipt is None:
                raise HTTPException(status_code=404, detail="replay_receipt_not_found")
            chosen_dispatch_type = "final" if final_receipt is not None else "phase"
        else:
            chosen_receipt = await _get_dispatch_receipt(
                dispatch_type=dispatch_type_normalized,
                job_id=case_id,
            )
            if chosen_receipt is None:
                raise HTTPException(status_code=404, detail="replay_receipt_not_found")

        request_snapshot = (
            chosen_receipt.request if isinstance(chosen_receipt.request, dict) else {}
        )
        trace_id = str(chosen_receipt.trace_id or request_snapshot.get("traceId") or "").strip()
        if not trace_id:
            raise HTTPException(status_code=409, detail="replay_missing_trace_id")

        report_payload: dict[str, Any]
        if chosen_dispatch_type == "final":
            try:
                final_request = FinalDispatchRequest.model_validate(request_snapshot)
            except ValidationError as err:
                raise HTTPException(status_code=409, detail=f"replay_invalid_final_request: {err}") from err
            _validate_final_dispatch_request(final_request)
            policy_profile = _resolve_policy_profile_or_raise(
                runtime=runtime,
                judge_policy_version=final_request.judge_policy_version,
                rubric_version=final_request.rubric_version,
                topic_domain=final_request.topic_domain,
            )
            phase_receipts = await _list_dispatch_receipts(
                dispatch_type="phase",
                session_id=final_request.session_id,
                status="reported",
                limit=1000,
            )
            report_payload = _build_final_report_payload(
                runtime=runtime,
                request=final_request,
                phase_receipts=phase_receipts,
            )
            await _attach_judge_agent_runtime_trace(
                runtime=runtime,
                report_payload=report_payload,
                dispatch_type="final",
                case_id=final_request.case_id,
                scope_id=final_request.scope_id,
                session_id=final_request.session_id,
                trace_id=final_request.trace_id,
                phase_start_no=final_request.phase_start_no,
                phase_end_no=final_request.phase_end_no,
            )
            _attach_policy_trace_snapshot(
                runtime=runtime,
                report_payload=report_payload,
                profile=policy_profile,
            )
            _attach_report_attestation(
                report_payload=report_payload,
                dispatch_type="final",
            )
            replay_contract_missing = _validate_final_report_payload_contract(report_payload)
            if replay_contract_missing:
                raise HTTPException(
                    status_code=409,
                    detail="replay_final_contract_violation: missing_fields="
                    + ",".join(replay_contract_missing[:12]),
                )
        else:
            try:
                phase_request = PhaseDispatchRequest.model_validate(request_snapshot)
            except ValidationError as err:
                raise HTTPException(status_code=409, detail=f"replay_invalid_phase_request: {err}") from err
            _validate_phase_dispatch_request(phase_request)
            policy_profile = _resolve_policy_profile_or_raise(
                runtime=runtime,
                judge_policy_version=phase_request.judge_policy_version,
                rubric_version=phase_request.rubric_version,
                topic_domain=phase_request.topic_domain,
            )
            report_payload = await build_phase_report_payload_v3_phase(
                request=phase_request,
                settings=runtime.settings,
                gateway_runtime=runtime.gateway_runtime,
            )
            await _attach_judge_agent_runtime_trace(
                runtime=runtime,
                report_payload=report_payload,
                dispatch_type="phase",
                case_id=phase_request.case_id,
                scope_id=phase_request.scope_id,
                session_id=phase_request.session_id,
                trace_id=phase_request.trace_id,
                phase_no=phase_request.phase_no,
            )
            _attach_policy_trace_snapshot(
                runtime=runtime,
                report_payload=report_payload,
                profile=policy_profile,
            )
            _attach_report_attestation(
                report_payload=report_payload,
                dispatch_type="phase",
            )

        winner = str(report_payload.get("winner") or "").strip().lower()
        if winner not in {"pro", "con", "draw"}:
            agent3 = (
                report_payload.get("agent3WeightedScore")
                if isinstance(report_payload.get("agent3WeightedScore"), dict)
                else {}
            )
            winner = _resolve_winner(
                _safe_float(agent3.get("pro"), default=50.0),
                _safe_float(agent3.get("con"), default=50.0),
                margin=0.8,
            )
        needs_draw_vote = bool(report_payload.get("needsDrawVote")) if "needsDrawVote" in report_payload else winner == "draw"

        if runtime.trace_store.get_trace(case_id) is None:
            runtime.trace_store.register_start(
                job_id=case_id,
                trace_id=trace_id,
                request=request_snapshot,
            )
        runtime.trace_store.mark_replay(
            job_id=case_id,
            winner=winner,
            needs_draw_vote=needs_draw_vote,
            provider=runtime.settings.provider,
        )
        replay_row = await _append_replay_record(
            dispatch_type=chosen_dispatch_type,
            job_id=case_id,
            trace_id=trace_id,
            winner=winner,
            needs_draw_vote=needs_draw_vote,
            provider=runtime.settings.provider,
            report_payload=report_payload,
        )
        await _workflow_mark_replay(
            job_id=case_id,
            dispatch_type=chosen_dispatch_type,
            event_payload={
                "traceId": trace_id,
                "winner": winner,
                "needsDrawVote": needs_draw_vote,
                "dispatchType": chosen_dispatch_type,
            },
        )
        replayed_at = replay_row.created_at.isoformat()
        verdict_contract = _build_verdict_contract(report_payload)

        return {
            "caseId": case_id,
            "dispatchType": chosen_dispatch_type,
            "replayedAt": replayed_at,
            "reportPayload": report_payload,
            "verdictContract": verdict_contract,
            "winner": winner,
            "needsDrawVote": needs_draw_vote,
            "traceId": trace_id,
            "judgeCoreStage": JUDGE_CORE_STAGE_REPLAY_COMPUTED,
            "judgeCoreVersion": JUDGE_CORE_VERSION,
        }

    @app.post("/internal/judge/cases/{case_id}/attestation/verify")
    async def verify_judge_report_attestation(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        dispatch_type_normalized = str(dispatch_type or "auto").strip().lower()
        if dispatch_type_normalized not in {"auto", "phase", "final"}:
            raise HTTPException(status_code=422, detail="invalid_dispatch_type")

        chosen_dispatch_type = dispatch_type_normalized
        chosen_receipt = None
        if dispatch_type_normalized == "auto":
            final_receipt = await _get_dispatch_receipt(
                dispatch_type="final",
                job_id=case_id,
            )
            phase_receipt = await _get_dispatch_receipt(
                dispatch_type="phase",
                job_id=case_id,
            )
            chosen_receipt = final_receipt or phase_receipt
            if chosen_receipt is None:
                raise HTTPException(status_code=404, detail="attestation_receipt_not_found")
            chosen_dispatch_type = "final" if final_receipt is not None else "phase"
        else:
            chosen_receipt = await _get_dispatch_receipt(
                dispatch_type=dispatch_type_normalized,
                job_id=case_id,
            )
            if chosen_receipt is None:
                raise HTTPException(status_code=404, detail="attestation_receipt_not_found")

        response_payload = (
            chosen_receipt.response if isinstance(chosen_receipt.response, dict) else {}
        )
        report_payload = (
            response_payload.get("reportPayload")
            if isinstance(response_payload.get("reportPayload"), dict)
            else None
        )
        if report_payload is None:
            raise HTTPException(status_code=409, detail="attestation_report_payload_missing")

        trace_id = str(chosen_receipt.trace_id or response_payload.get("traceId") or "").strip()
        verify_result = _verify_report_attestation(
            report_payload=report_payload,
            dispatch_type=chosen_dispatch_type,
        )
        return {
            "caseId": case_id,
            "dispatchType": chosen_dispatch_type,
            "traceId": trace_id,
            **verify_result,
        }

    @app.get("/internal/judge/cases/{case_id}/replay/report")
    async def get_judge_replay_report(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        record = runtime.trace_store.get_trace(case_id)
        if record is None:
            raise HTTPException(status_code=404, detail="judge_trace_not_found")
        return _build_replay_report_payload(record)

    @app.get("/internal/judge/cases/replay/reports")
    async def list_judge_replay_reports(
        x_ai_internal_key: str | None = Header(default=None),
        status: str | None = Query(default=None),
        winner: str | None = Query(default=None),
        callback_status: str | None = Query(default=None),
        trace_id: str | None = Query(default=None),
        created_after: datetime | None = Query(default=None),
        created_before: datetime | None = Query(default=None),
        has_audit_alert: bool | None = Query(default=None),
        limit: int = Query(default=20, ge=1, le=200),
        include_report: bool = Query(default=False),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        normalized_created_after = _normalize_query_datetime(created_after)
        normalized_created_before = _normalize_query_datetime(created_before)
        query = TraceQuery(
            status=status,
            winner=winner,
            callback_status=callback_status,
            trace_id=trace_id,
            created_after=normalized_created_after,
            created_before=normalized_created_before,
            has_audit_alert=has_audit_alert,
            limit=limit,
        )
        records = runtime.trace_store.list_traces(query=query)
        if include_report:
            items = [_build_replay_report_payload(record) for record in records]
        else:
            items = [_build_replay_report_summary(record) for record in records]
        return {
            "count": len(items),
            "items": items,
            "filters": {
                "status": status,
                "winner": winner,
                "callbackStatus": callback_status,
                "traceId": trace_id,
                "createdAfter": normalized_created_after.isoformat()
                if normalized_created_after
                else None,
                "createdBefore": normalized_created_before.isoformat()
                if normalized_created_before
                else None,
                "hasAuditAlert": has_audit_alert,
                "limit": limit,
                "includeReport": include_report,
            },
        }

    @app.get("/internal/judge/review/cases")
    async def list_judge_review_jobs(
        x_ai_internal_key: str | None = Header(default=None),
        status: str = Query(default="review_required"),
        dispatch_type: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        normalized_status = _normalize_workflow_status(status)
        if normalized_status is None or normalized_status not in WORKFLOW_STATUSES:
            raise HTTPException(status_code=422, detail="invalid_workflow_status")
        normalized_dispatch_type = (
            str(dispatch_type or "").strip().lower() or None
        )
        if normalized_dispatch_type not in {None, "phase", "final"}:
            raise HTTPException(status_code=422, detail="invalid_dispatch_type")

        jobs = await _workflow_list_jobs(
            status=normalized_status,
            dispatch_type=normalized_dispatch_type,
            limit=limit,
        )
        items: list[dict[str, Any]] = []
        for job in jobs:
            trace = runtime.trace_store.get_trace(job.job_id)
            report_summary = (
                trace.report_summary if trace and isinstance(trace.report_summary, dict) else {}
            )
            report_payload = (
                report_summary.get("payload") if isinstance(report_summary.get("payload"), dict) else {}
            )
            error_codes = report_payload.get("errorCodes")
            audit_alerts = report_summary.get("auditAlerts")
            items.append(
                {
                    "workflow": _serialize_workflow_job(job),
                    "winner": report_summary.get("winner"),
                    "reviewRequired": bool(report_payload.get("reviewRequired")),
                    "fairnessSummary": (
                        report_payload.get("fairnessSummary")
                        if isinstance(report_payload.get("fairnessSummary"), dict)
                        else None
                    ),
                    "errorCodes": error_codes if isinstance(error_codes, list) else [],
                    "auditAlertCount": (
                        len(audit_alerts)
                        if isinstance(audit_alerts, list)
                        else 0
                    ),
                    "callbackStatus": report_summary.get("callbackStatus"),
                }
            )
        return {
            "count": len(items),
            "items": items,
            "filters": {
                "status": normalized_status,
                "dispatchType": normalized_dispatch_type,
                "limit": limit,
            },
        }

    @app.get("/internal/judge/review/cases/{case_id}")
    async def get_judge_review_job(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        workflow_job = await _workflow_get_job(job_id=case_id)
        if workflow_job is None:
            raise HTTPException(status_code=404, detail="review_job_not_found")
        workflow_events = await _workflow_list_events(job_id=case_id)
        alerts = await _list_audit_alerts(job_id=case_id, status=None, limit=200)
        trace = runtime.trace_store.get_trace(case_id)
        report_summary = (
            trace.report_summary if trace and isinstance(trace.report_summary, dict) else {}
        )
        report_payload = (
            report_summary.get("payload") if isinstance(report_summary.get("payload"), dict) else {}
        )
        return {
            "job": _serialize_workflow_job(workflow_job),
            "reportPayload": report_payload,
            "winner": report_summary.get("winner"),
            "reviewRequired": bool(report_payload.get("reviewRequired")),
            "callbackStatus": report_summary.get("callbackStatus"),
            "callbackError": report_summary.get("callbackError"),
            "trace": (
                {
                    "traceId": trace.trace_id,
                    "status": trace.status,
                    "createdAt": trace.created_at.isoformat(),
                    "updatedAt": trace.updated_at.isoformat(),
                }
                if trace is not None
                else None
            ),
            "events": [
                {
                    "eventSeq": item.event_seq,
                    "eventType": item.event_type,
                    "payload": item.payload,
                    "createdAt": item.created_at.isoformat(),
                }
                for item in workflow_events
            ],
            "alerts": [_serialize_alert_item(item) for item in alerts],
        }

    @app.post("/internal/judge/review/cases/{case_id}/decision")
    async def decide_judge_review_job(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        decision: str = Query(default="approve"),
        actor: str | None = Query(default=None),
        reason: str | None = Query(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        normalized_decision = str(decision or "").strip().lower()
        if normalized_decision not in {"approve", "reject"}:
            raise HTTPException(status_code=422, detail="invalid_review_decision")

        current_job = await _workflow_get_job(job_id=case_id)
        if current_job is None:
            raise HTTPException(status_code=404, detail="review_job_not_found")
        # 复核决策只允许消费 review_required 队列，避免绕过主状态机直接改裁决状态。
        if current_job.status != "review_required":
            raise HTTPException(status_code=409, detail="review_job_not_pending")

        event_payload = {
            "dispatchType": current_job.dispatch_type,
            "reviewDecision": normalized_decision,
            "reviewActor": str(actor or "").strip() or "system",
            "reviewReason": str(reason or "").strip() or None,
        }
        resolved_alert_ids: list[str] = []
        if normalized_decision == "approve":
            event_payload["judgeCoreStage"] = "review_approved"
            await _workflow_mark_completed(
                job_id=case_id,
                event_payload=event_payload,
            )
            transitioned = await _workflow_get_job(job_id=case_id)
            if transitioned is None:
                raise HTTPException(status_code=404, detail="review_job_not_found")
            raised_alerts = runtime.trace_store.list_audit_alerts(
                job_id=case_id,
                status="raised",
                limit=200,
            )
            for item in raised_alerts:
                row = runtime.trace_store.transition_audit_alert(
                    job_id=case_id,
                    alert_id=item.alert_id,
                    to_status="resolved",
                    actor=event_payload["reviewActor"],
                    reason=event_payload["reviewReason"] or "review_approved",
                )
                if row is None:
                    continue
                await _sync_audit_alert_to_facts(alert=row)
                resolved_alert_ids.append(row.alert_id)
        else:
            reject_reason = event_payload["reviewReason"] or "review rejected by reviewer"
            event_payload["judgeCoreStage"] = "review_rejected"
            await _workflow_mark_failed(
                job_id=case_id,
                error_code="review_rejected",
                error_message=reject_reason,
                event_payload=event_payload,
            )
            transitioned = await _workflow_get_job(job_id=case_id)
            if transitioned is None:
                raise HTTPException(status_code=404, detail="review_job_not_found")

        return {
            "ok": True,
            "job": _serialize_workflow_job(transitioned),
            "decision": normalized_decision,
            "resolvedAlertIds": resolved_alert_ids,
        }

    @app.get("/internal/judge/cases/{case_id}/alerts")
    async def list_judge_job_alerts(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        status: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        items = await _list_audit_alerts(
            job_id=case_id,
            status=status,
            limit=limit,
        )
        return {
            "caseId": case_id,
            "count": len(items),
            "items": [_serialize_alert_item(item) for item in items],
        }

    async def _transition_alert_status(
        *,
        job_id: int,
        alert_id: str,
        to_status: str,
        actor: str | None,
        reason: str | None,
    ) -> dict[str, Any]:
        row = runtime.trace_store.transition_audit_alert(
            job_id=job_id,
            alert_id=alert_id,
            to_status=to_status,
            actor=actor,
            reason=reason,
        )
        if row is None:
            raise HTTPException(status_code=409, detail="invalid_alert_status_transition")
        await _sync_audit_alert_to_facts(alert=row)
        transitioned = await runtime.workflow_runtime.facts.transition_audit_alert(
            alert_id=alert_id,
            to_status=to_status,
            now=row.updated_at,
        )
        if transitioned is None:
            raise HTTPException(status_code=409, detail="invalid_alert_status_transition")
        return {
            "ok": True,
            "caseId": job_id,
            "alertId": alert_id,
            "status": transitioned.status,
            "item": _serialize_alert_item(transitioned),
        }

    @app.post("/internal/judge/cases/{case_id}/alerts/{alert_id}/ack")
    async def ack_judge_job_alert(
        case_id: int,
        alert_id: str,
        x_ai_internal_key: str | None = Header(default=None),
        actor: str | None = Query(default=None),
        reason: str | None = Query(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _transition_alert_status(
            job_id=case_id,
            alert_id=alert_id,
            to_status="acked",
            actor=actor,
            reason=reason,
        )

    @app.post("/internal/judge/cases/{case_id}/alerts/{alert_id}/resolve")
    async def resolve_judge_job_alert(
        case_id: int,
        alert_id: str,
        x_ai_internal_key: str | None = Header(default=None),
        actor: str | None = Query(default=None),
        reason: str | None = Query(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _transition_alert_status(
            job_id=case_id,
            alert_id=alert_id,
            to_status="resolved",
            actor=actor,
            reason=reason,
        )

    @app.get("/internal/judge/alerts/outbox")
    async def list_judge_alert_outbox(
        x_ai_internal_key: str | None = Header(default=None),
        delivery_status: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        rows = runtime.trace_store.list_alert_outbox(
            delivery_status=delivery_status,
            limit=limit,
        )
        return {
            "count": len(rows),
            "items": [_serialize_outbox_event(item) for item in rows],
            "filters": {
                "deliveryStatus": delivery_status,
                "limit": limit,
            },
        }

    @app.post("/internal/judge/alerts/outbox/{event_id}/delivery")
    async def mark_judge_alert_outbox_delivery(
        event_id: str,
        x_ai_internal_key: str | None = Header(default=None),
        delivery_status: str = Query(default="sent"),
        error_message: str | None = Query(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        item = runtime.trace_store.mark_alert_outbox_delivery(
            event_id=event_id,
            delivery_status=delivery_status,
            error_message=error_message,
        )
        if item is None:
            raise HTTPException(status_code=404, detail="alert_outbox_event_not_found")
        return {
            "ok": True,
            "item": _serialize_outbox_event(item),
        }

    @app.get("/internal/judge/rag/diagnostics")
    async def get_rag_diagnostics(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        record = runtime.trace_store.get_trace(case_id)
        if record is None:
            raise HTTPException(status_code=404, detail="judge_trace_not_found")
        report_summary = record.report_summary or {}
        payload = report_summary.get("payload") or {}
        return {
            "caseId": case_id,
            "traceId": record.trace_id,
            "retrievalDiagnostics": payload.get("retrievalDiagnostics"),
            "ragSources": payload.get("ragSources"),
            "ragBackend": payload.get("ragBackend"),
            "ragRequestedBackend": payload.get("ragRequestedBackend"),
            "ragBackendFallbackReason": payload.get("ragBackendFallbackReason"),
        }

    return app


def create_default_app(*, load_settings_fn: LoadSettingsFn = load_settings) -> FastAPI:
    return create_app(
        create_runtime(
            settings=load_settings_fn(),
        )
    )
