from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Query, Request
from pydantic import ValidationError

from .applications import (
    AgentRuntime,
    GatewayRuntime,
    MutablePolicyRegistryRuntime,
    MutablePromptRegistryRuntime,
    MutableToolRegistryRuntime,
    RegistryProductRuntime,
    WorkflowRuntime,
    build_agent_runtime,
    build_gateway_runtime,
    build_registry_product_runtime,
    build_workflow_runtime,
)
from .applications import (
    attach_report_attestation as attach_report_attestation_v3,
)
from .applications import (
    build_audit_anchor_export as build_audit_anchor_export_v3,
)
from .applications import (
    build_case_commitment_registry as build_case_commitment_registry_v3,
)
from .applications import (
    build_challenge_review_registry as build_challenge_review_registry_v3,
)
from .applications import (
    build_final_report_payload as build_final_report_payload_v3_final,
)
from .applications import (
    build_judge_kernel_registry as build_judge_kernel_registry_v3,
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
    build_verdict_attestation_registry as build_verdict_attestation_registry_v3,
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
from .core.workflow import WorkflowTransitionError
from .domain.agents import (
    AGENT_KIND_JUDGE,
    AGENT_KIND_NPC_COACH,
    AGENT_KIND_ROOM_QA,
    AgentExecutionRequest,
)
from .domain.facts import (
    AuditAlert as FactAuditAlert,
)
from .domain.facts import (
    ClaimLedgerRecord as FactClaimLedgerRecord,
)
from .domain.facts import (
    DispatchReceipt as FactDispatchReceipt,
)
from .domain.facts import (
    FairnessBenchmarkRun as FactFairnessBenchmarkRun,
)
from .domain.facts import (
    ReplayRecord as FactReplayRecord,
)
from .domain.workflow import WORKFLOW_STATUS_QUEUED, WORKFLOW_STATUSES, WorkflowJob
from .models import (
    CaseCreateRequest,
    FinalDispatchRequest,
    NpcCoachAdviceRequest,
    PhaseDispatchRequest,
    RoomQaAnswerRequest,
)
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
    registry_product_runtime: RegistryProductRuntime
    agent_runtime: AgentRuntime
    policy_registry_runtime: MutablePolicyRegistryRuntime
    prompt_registry_runtime: MutablePromptRegistryRuntime
    tool_registry_runtime: MutableToolRegistryRuntime


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
    registry_product_runtime = build_registry_product_runtime(
        session_factory=workflow_runtime.db.session_factory,
        settings=settings,
    )
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
        registry_product_runtime=registry_product_runtime,
        agent_runtime=agent_runtime,
        policy_registry_runtime=registry_product_runtime.policy_runtime,
        prompt_registry_runtime=registry_product_runtime.prompt_runtime,
        tool_registry_runtime=registry_product_runtime.tool_runtime,
    )


_BLIND_SENSITIVE_KEY_TOKENS = {
    "user_id",
    "userid",
    "vip",
    "balance",
    "wallet_balance",
    "is_vip",
}

TRUST_CHALLENGE_EVENT_TYPE = "trust_challenge_state_changed"
TRUST_CHALLENGE_STATE_REQUESTED = "challenge_requested"
TRUST_CHALLENGE_STATE_ACCEPTED = "challenge_accepted"
TRUST_CHALLENGE_STATE_UNDER_REVIEW = "under_review"
TRUST_CHALLENGE_STATE_VERDICT_UPHELD = "verdict_upheld"
TRUST_CHALLENGE_STATE_VERDICT_OVERTURNED = "verdict_overturned"
TRUST_CHALLENGE_STATE_DRAW_AFTER_REVIEW = "draw_after_review"
TRUST_CHALLENGE_STATE_CLOSED = "challenge_closed"

REGISTRY_TYPE_POLICY = "policy"
REGISTRY_DEPENDENCY_ALERT_TYPE_BLOCKED = "registry_dependency_health_blocked"
REGISTRY_FAIRNESS_ALERT_TYPE_BLOCKED = "registry_fairness_gate_blocked"
REGISTRY_FAIRNESS_ALERT_TYPE_OVERRIDE = "registry_fairness_gate_override"
OPS_REGISTRY_ALERT_TYPES = {
    REGISTRY_FAIRNESS_ALERT_TYPE_BLOCKED,
    REGISTRY_FAIRNESS_ALERT_TYPE_OVERRIDE,
    REGISTRY_DEPENDENCY_ALERT_TYPE_BLOCKED,
}
OPS_ALERT_STATUS_VALUES = {"raised", "acked", "resolved", "open"}
OPS_ALERT_DELIVERY_STATUS_VALUES = {"pending", "sent", "failed"}
OPS_ALERT_FIELDS_MODE_VALUES = {"full", "lite"}
REGISTRY_AUDIT_ACTION_VALUES = {"bootstrap", "publish", "activate", "rollback"}
REGISTRY_DEPENDENCY_TREND_STATUS_VALUES = {
    "open",
    "raised",
    "acked",
    "resolved",
}
FAIRNESS_RELEASE_GATE_ACCEPTED_STATUSES = {
    "pass",
    "local_reference_frozen",
}
PANEL_JUDGE_IDS = ("judgeA", "judgeB", "judgeC")
PANEL_RUNTIME_PROFILE_DEFAULTS = {
    "judgeA": {
        "profileId": "panel-judgeA-weighted-v1",
        "modelStrategy": "deterministic_weighted",
        "scoreSource": "agent3WeightedScore",
        "decisionMargin": 0.8,
        "promptVersionKey": "finalPipelineVersion",
    },
    "judgeB": {
        "profileId": "panel-judgeB-path-alignment-v1",
        "modelStrategy": "deterministic_path_alignment",
        "scoreSource": "agent2Score",
        "decisionMargin": 0.8,
        "promptVersionKey": "agent2PromptVersion",
    },
    "judgeC": {
        "profileId": "panel-judgeC-dimension-composite-v1",
        "modelStrategy": "deterministic_dimension_composite",
        "scoreSource": "agent1Dimensions",
        "decisionMargin": 0.8,
        "promptVersionKey": "summaryPromptVersion",
    },
}
CASE_FAIRNESS_GATE_CONCLUSIONS = {
    "auto_passed",
    "review_required",
    "benchmark_attention_required",
}
CASE_FAIRNESS_CHALLENGE_STATES = {
    TRUST_CHALLENGE_STATE_REQUESTED,
    TRUST_CHALLENGE_STATE_ACCEPTED,
    TRUST_CHALLENGE_STATE_UNDER_REVIEW,
    TRUST_CHALLENGE_STATE_VERDICT_UPHELD,
    TRUST_CHALLENGE_STATE_VERDICT_OVERTURNED,
    TRUST_CHALLENGE_STATE_DRAW_AFTER_REVIEW,
    TRUST_CHALLENGE_STATE_CLOSED,
}
CASE_FAIRNESS_SORT_FIELDS = {
    "updated_at",
    "panel_disagreement_ratio",
    "gate_conclusion",
    "case_id",
}


def _new_challenge_id(*, case_id: int) -> str:
    return f"chlg-{max(0, int(case_id))}-{uuid4().hex[:12]}"


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


def _serialize_prompt_profile(runtime: AppRuntime, *, profile: Any) -> dict[str, Any]:
    return runtime.prompt_registry_runtime.serialize_profile(profile)


def _serialize_tool_profile(runtime: AppRuntime, *, profile: Any) -> dict[str, Any]:
    return runtime.tool_registry_runtime.serialize_profile(profile)


async def _ensure_registry_runtime_loaded(*, runtime: AppRuntime) -> None:
    await runtime.registry_product_runtime.ensure_loaded()


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


def _resolve_prompt_profile_or_raise(
    *,
    runtime: AppRuntime,
    prompt_registry_version: str,
) -> Any:
    profile = runtime.prompt_registry_runtime.get_profile(prompt_registry_version)
    if profile is not None:
        return profile
    raise HTTPException(status_code=422, detail="unknown_prompt_registry_version")


def _resolve_tool_profile_or_raise(
    *,
    runtime: AppRuntime,
    tool_registry_version: str,
) -> Any:
    profile = runtime.tool_registry_runtime.get_profile(tool_registry_version)
    if profile is not None:
        return profile
    raise HTTPException(status_code=422, detail="unknown_tool_registry_version")


def _attach_policy_trace_snapshot(
    *,
    runtime: AppRuntime,
    report_payload: dict[str, Any],
    profile: Any,
    prompt_profile: Any,
    tool_profile: Any,
) -> None:
    if not isinstance(report_payload, dict):
        return
    judge_trace = report_payload.get("judgeTrace")
    if not isinstance(judge_trace, dict):
        judge_trace = {}
        report_payload["judgeTrace"] = judge_trace
    judge_trace["policyRegistry"] = runtime.policy_registry_runtime.build_trace_snapshot(profile)
    judge_trace["promptRegistry"] = runtime.prompt_registry_runtime.build_trace_snapshot(prompt_profile)
    judge_trace["toolRegistry"] = runtime.tool_registry_runtime.build_trace_snapshot(tool_profile)
    judge_trace["registryVersions"] = {
        "policyVersion": str(getattr(profile, "version", "") or "").strip(),
        "promptVersion": str(getattr(prompt_profile, "version", "") or "").strip(),
        "toolsetVersion": str(getattr(tool_profile, "version", "") or "").strip(),
    }


def _resolve_panel_runtime_profiles(*, profile: Any) -> dict[str, dict[str, Any]]:
    prompt_versions = (
        getattr(profile, "prompt_versions", None)
        if isinstance(getattr(profile, "prompt_versions", None), dict)
        else {}
    )
    metadata = (
        getattr(profile, "metadata", None)
        if isinstance(getattr(profile, "metadata", None), dict)
        else {}
    )
    raw_profiles = metadata.get("panelRuntimeProfiles")
    if not isinstance(raw_profiles, dict):
        raw_profiles = metadata.get("panel_runtime_profiles")
    normalized: dict[str, dict[str, Any]] = {}
    policy_version = str(getattr(profile, "version", "") or "").strip()
    toolset_version = str(getattr(profile, "tool_registry_version", "") or "").strip()

    for judge_id in PANEL_JUDGE_IDS:
        defaults = PANEL_RUNTIME_PROFILE_DEFAULTS[judge_id]
        raw_row = raw_profiles.get(judge_id) if isinstance(raw_profiles, dict) else None
        row = raw_row if isinstance(raw_row, dict) else {}
        prompt_version_key = defaults["promptVersionKey"]
        prompt_version = str(
            row.get("promptVersion")
            or row.get("prompt_version")
            or prompt_versions.get(prompt_version_key)
            or ""
        ).strip()
        normalized[judge_id] = {
            "judgeId": judge_id,
            "profileId": str(
                row.get("profileId")
                or row.get("profile_id")
                or defaults["profileId"]
            ).strip()
            or defaults["profileId"],
            "modelStrategy": str(
                row.get("modelStrategy")
                or row.get("model_strategy")
                or defaults["modelStrategy"]
            ).strip()
            or defaults["modelStrategy"],
            "scoreSource": str(
                row.get("scoreSource")
                or row.get("score_source")
                or defaults["scoreSource"]
            ).strip()
            or defaults["scoreSource"],
            "decisionMargin": _safe_float(
                row.get("decisionMargin") or row.get("decision_margin"),
                default=float(defaults["decisionMargin"]),
            ),
            "promptVersion": prompt_version or None,
            "toolsetVersion": (
                str(row.get("toolsetVersion") or row.get("toolset_version") or "").strip()
                or toolset_version
                or None
            ),
            "policyVersion": policy_version or None,
            # 这里显式记录来源，便于重放时判断是策略配置还是默认值导致的分歧。
            "profileSource": "policy_metadata" if row else "builtin_default",
        }
    return normalized


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
    claim_ledger_record: FactClaimLedgerRecord | None = None,
) -> dict[str, Any]:
    payload = report_payload if isinstance(report_payload, dict) else {}
    contract = verdict_contract if isinstance(verdict_contract, dict) else {}
    judge_trace = payload.get("judgeTrace") if isinstance(payload.get("judgeTrace"), dict) else {}
    ledger_claim_graph = (
        claim_ledger_record.claim_graph
        if claim_ledger_record is not None and isinstance(claim_ledger_record.claim_graph, dict)
        else None
    )
    ledger_claim_summary = (
        claim_ledger_record.claim_graph_summary
        if claim_ledger_record is not None and isinstance(claim_ledger_record.claim_graph_summary, dict)
        else None
    )
    ledger_evidence_ledger = (
        claim_ledger_record.evidence_ledger
        if claim_ledger_record is not None and isinstance(claim_ledger_record.evidence_ledger, dict)
        else None
    )
    ledger_verdict_refs = (
        claim_ledger_record.verdict_evidence_refs
        if claim_ledger_record is not None and isinstance(claim_ledger_record.verdict_evidence_refs, list)
        else []
    )

    claim_graph = (
        payload.get("claimGraph")
        if isinstance(payload.get("claimGraph"), dict)
        else ledger_claim_graph
    )
    claim_graph_summary = (
        payload.get("claimGraphSummary")
        if isinstance(payload.get("claimGraphSummary"), dict)
        else ledger_claim_summary
    )
    verdict_ledger = (
        payload.get("verdictLedger")
        if isinstance(payload.get("verdictLedger"), dict)
        else (
            contract.get("verdictLedger")
            if isinstance(contract.get("verdictLedger"), dict)
            else None
        )
    )
    opinion_pack = (
        payload.get("opinionPack")
        if isinstance(payload.get("opinionPack"), dict)
        else (
            contract.get("opinionPack")
            if isinstance(contract.get("opinionPack"), dict)
            else None
        )
    )
    evidence_ledger = (
        payload.get("evidenceLedger")
        if isinstance(payload.get("evidenceLedger"), dict)
        else (
            contract.get("evidenceLedger")
            if isinstance(contract.get("evidenceLedger"), dict)
            else ledger_evidence_ledger
        )
    )
    policy_snapshot = (
        judge_trace.get("policyRegistry")
        if isinstance(judge_trace.get("policyRegistry"), dict)
        else None
    )
    prompt_snapshot = (
        judge_trace.get("promptRegistry")
        if isinstance(judge_trace.get("promptRegistry"), dict)
        else None
    )
    tool_snapshot = (
        judge_trace.get("toolRegistry")
        if isinstance(judge_trace.get("toolRegistry"), dict)
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
    panel_runtime_profiles = (
        judge_trace.get("panelRuntimeProfiles")
        if isinstance(judge_trace.get("panelRuntimeProfiles"), dict)
        else (
            (
                verdict_ledger.get("panelDecisions")
                if isinstance(verdict_ledger, dict)
                and isinstance(verdict_ledger.get("panelDecisions"), dict)
                else {}
            ).get("runtimeProfiles")
            if isinstance(
                (
                    verdict_ledger.get("panelDecisions")
                    if isinstance(verdict_ledger, dict)
                    and isinstance(verdict_ledger.get("panelDecisions"), dict)
                    else {}
                ).get("runtimeProfiles"),
                dict,
            )
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
        dict(item)
        for item in ((raw_verdict_refs or ledger_verdict_refs) or [])
        if isinstance(item, dict)
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
    prompt_version = (
        str(prompt_snapshot.get("version")).strip()
        if isinstance(prompt_snapshot, dict)
        and str(prompt_snapshot.get("version") or "").strip()
        else None
    )
    toolset_version = (
        str(tool_snapshot.get("version")).strip()
        if isinstance(tool_snapshot, dict)
        and str(tool_snapshot.get("version") or "").strip()
        else None
    )

    return {
        "claimGraph": claim_graph,
        "claimGraphSummary": claim_graph_summary,
        "evidenceLedger": evidence_ledger,
        "verdictLedger": verdict_ledger,
        "opinionPack": opinion_pack,
        "policySnapshot": policy_snapshot,
        "policyVersion": policy_version,
        "promptSnapshot": prompt_snapshot,
        "promptVersion": prompt_version,
        "toolSnapshot": tool_snapshot,
        "toolsetVersion": toolset_version,
        "trustAttestation": trust_attestation,
        "fairnessSummary": fairness_summary,
        "panelRuntimeProfiles": panel_runtime_profiles,
        "verdictEvidenceRefs": verdict_evidence_refs,
        "auditSummary": {
            "alertCount": len(audit_alerts),
            "auditAlerts": audit_alerts,
            "errorCodes": error_codes,
            "degradationLevel": degradation_level,
        },
        "claimLedger": (
            {
                "dispatchType": claim_ledger_record.dispatch_type,
                "traceId": claim_ledger_record.trace_id,
                "createdAt": claim_ledger_record.created_at.isoformat(),
                "updatedAt": claim_ledger_record.updated_at.isoformat(),
            }
            if claim_ledger_record is not None
            else None
        ),
        "hasClaimGraph": claim_graph is not None,
        "hasClaimLedger": claim_ledger_record is not None,
        "hasEvidenceLedger": evidence_ledger is not None,
        "hasVerdictLedger": verdict_ledger is not None,
        "hasOpinionPack": opinion_pack is not None,
        "hasTrustAttestation": trust_attestation is not None,
    }


def _serialize_claim_ledger_record(
    record: FactClaimLedgerRecord,
    *,
    include_payload: bool = True,
) -> dict[str, Any]:
    item = {
        "caseId": record.case_id,
        "dispatchType": record.dispatch_type,
        "traceId": record.trace_id,
        "createdAt": record.created_at.isoformat(),
        "updatedAt": record.updated_at.isoformat(),
    }
    if include_payload:
        item["claimGraph"] = dict(record.claim_graph)
        item["claimGraphSummary"] = dict(record.claim_graph_summary)
        item["evidenceLedger"] = dict(record.evidence_ledger)
        item["verdictEvidenceRefs"] = [dict(row) for row in record.verdict_evidence_refs]
    return item


def _serialize_fairness_benchmark_run(record: FactFairnessBenchmarkRun) -> dict[str, Any]:
    return {
        "runId": record.run_id,
        "policyVersion": record.policy_version,
        "environmentMode": record.environment_mode,
        "status": record.status,
        "thresholdDecision": record.threshold_decision,
        "needsRealEnvReconfirm": bool(record.needs_real_env_reconfirm),
        "needsRemediation": bool(record.needs_remediation),
        "sampleSize": record.sample_size,
        "drawRate": record.draw_rate,
        "sideBiasDelta": record.side_bias_delta,
        "appealOverturnRate": record.appeal_overturn_rate,
        "thresholds": dict(record.thresholds),
        "metrics": dict(record.metrics),
        "summary": dict(record.summary),
        "source": record.source,
        "reportedBy": record.reported_by,
        "reportedAt": record.reported_at.isoformat(),
        "createdAt": record.created_at.isoformat(),
        "updatedAt": record.updated_at.isoformat(),
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


def _normalize_case_fairness_gate_conclusion(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    return normalized


def _normalize_case_fairness_challenge_state(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    return normalized


def _normalize_case_fairness_sort_by(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "updated_at"
    return normalized


def _normalize_case_fairness_sort_order(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "desc"
    return normalized


def _build_case_fairness_sort_key(*, item: dict[str, Any], sort_by: str) -> tuple[Any, ...]:
    if sort_by == "panel_disagreement_ratio":
        panel = item.get("panelDisagreement") if isinstance(item.get("panelDisagreement"), dict) else {}
        return (
            _safe_float(panel.get("ratio"), default=0.0),
            int(item.get("caseId") or 0),
        )
    if sort_by == "gate_conclusion":
        return (
            str(item.get("gateConclusion") or "").strip().lower(),
            int(item.get("caseId") or 0),
        )
    if sort_by == "case_id":
        return (int(item.get("caseId") or 0),)
    return (
        str(item.get("updatedAt") or "").strip(),
        int(item.get("caseId") or 0),
    )


def _build_case_fairness_aggregations(items: list[dict[str, Any]]) -> dict[str, Any]:
    gate_counts: dict[str, int] = {key: 0 for key in sorted(CASE_FAIRNESS_GATE_CONCLUSIONS)}
    gate_counts["unknown"] = 0
    winner_counts: dict[str, int] = {
        "pro": 0,
        "con": 0,
        "draw": 0,
        "unknown": 0,
    }
    challenge_state_counts: dict[str, int] = {"none": 0}
    policy_version_counts: dict[str, int] = {"unknown": 0}

    open_review_count = 0
    review_required_count = 0
    drift_breach_count = 0
    threshold_breach_count = 0
    panel_high_disagreement_count = 0
    with_challenge_count = 0

    for item in items:
        gate = str(item.get("gateConclusion") or "").strip().lower()
        if gate in gate_counts:
            gate_counts[gate] += 1
        else:
            gate_counts["unknown"] += 1

        winner = str(item.get("winner") or "").strip().lower()
        if winner in winner_counts:
            winner_counts[winner] += 1
        else:
            winner_counts["unknown"] += 1

        if bool(item.get("reviewRequired")):
            review_required_count += 1

        panel = item.get("panelDisagreement") if isinstance(item.get("panelDisagreement"), dict) else {}
        if bool(panel.get("high")):
            panel_high_disagreement_count += 1

        drift = item.get("driftSummary") if isinstance(item.get("driftSummary"), dict) else {}
        if bool(drift.get("hasDriftBreach")):
            drift_breach_count += 1
        if bool(drift.get("hasThresholdBreach")):
            threshold_breach_count += 1
        policy_version = str(drift.get("policyVersion") or "").strip()
        if policy_version:
            policy_version_counts[policy_version] = policy_version_counts.get(policy_version, 0) + 1
        else:
            policy_version_counts["unknown"] += 1

        challenge_link = item.get("challengeLink") if isinstance(item.get("challengeLink"), dict) else {}
        if bool(challenge_link.get("hasOpenReview")):
            open_review_count += 1
        latest_challenge = challenge_link.get("latest") if isinstance(challenge_link.get("latest"), dict) else None
        state = str(latest_challenge.get("state") or "").strip() if isinstance(latest_challenge, dict) else ""
        if state:
            challenge_state_counts[state] = challenge_state_counts.get(state, 0) + 1
            with_challenge_count += 1
        else:
            challenge_state_counts["none"] = challenge_state_counts.get("none", 0) + 1

    return {
        "totalMatched": len(items),
        "reviewRequiredCount": review_required_count,
        "openReviewCount": open_review_count,
        "driftBreachCount": drift_breach_count,
        "thresholdBreachCount": threshold_breach_count,
        "panelHighDisagreementCount": panel_high_disagreement_count,
        "withChallengeCount": with_challenge_count,
        "gateConclusionCounts": gate_counts,
        "winnerCounts": winner_counts,
        "challengeStateCounts": dict(sorted(challenge_state_counts.items(), key=lambda kv: kv[0])),
        "policyVersionCounts": dict(sorted(policy_version_counts.items(), key=lambda kv: kv[0])),
    }


def _normalize_aware_datetime(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _build_registry_dependency_overview(
    *,
    items: list[dict[str, Any]],
    alerts: list[Any],
    registry_type: str,
    window_minutes: int,
) -> dict[str, Any]:
    normalized_registry_type = str(registry_type or "").strip().lower()
    window = max(10, min(int(window_minutes), 43200))
    now = datetime.now(timezone.utc)
    window_from = now - timedelta(minutes=window)

    by_policy_version: dict[str, dict[str, Any]] = {}
    for item in items:
        version = str(item.get("policyVersion") or "").strip()
        if not version:
            continue
        row = by_policy_version.setdefault(
            version,
            {
                "policyVersion": version,
                "dependencyOk": bool(item.get("ok")),
                "totalAlerts": 0,
                "openBlockedCount": 0,
                "resolvedCount": 0,
                "recentChanges": 0,
                "lastStatus": None,
                "lastUpdatedAt": None,
                "_latestUpdatedAt": None,
            },
        )
        row["dependencyOk"] = bool(item.get("ok"))

    total_alerts = 0
    open_blocked_count = 0
    resolved_count = 0
    recent_total = 0
    recent_status_counts = {
        "raised": 0,
        "acked": 0,
        "resolved": 0,
        "unknown": 0,
    }

    for alert in alerts:
        alert_type = str(getattr(alert, "alert_type", "") or "").strip()
        if alert_type != REGISTRY_DEPENDENCY_ALERT_TYPE_BLOCKED:
            continue
        details = (
            dict(getattr(alert, "details"))
            if isinstance(getattr(alert, "details", None), dict)
            else {}
        )
        if str(details.get("registryType") or "").strip().lower() != normalized_registry_type:
            continue
        version = str(details.get("version") or "").strip() or "unknown"
        status = str(getattr(alert, "status", "") or "").strip().lower() or "unknown"
        updated_at = _normalize_aware_datetime(
            getattr(alert, "updated_at", None)
        ) or _normalize_aware_datetime(getattr(alert, "created_at", None)) or now

        row = by_policy_version.setdefault(
            version,
            {
                "policyVersion": version,
                "dependencyOk": None,
                "totalAlerts": 0,
                "openBlockedCount": 0,
                "resolvedCount": 0,
                "recentChanges": 0,
                "lastStatus": None,
                "lastUpdatedAt": None,
                "_latestUpdatedAt": None,
            },
        )
        row["totalAlerts"] += 1
        total_alerts += 1
        if status == "resolved":
            row["resolvedCount"] += 1
            resolved_count += 1
        else:
            row["openBlockedCount"] += 1
            open_blocked_count += 1

        latest_updated_at = row.get("_latestUpdatedAt")
        if not isinstance(latest_updated_at, datetime) or updated_at >= latest_updated_at:
            row["_latestUpdatedAt"] = updated_at
            row["lastStatus"] = status
            row["lastUpdatedAt"] = updated_at.isoformat()

        if updated_at >= window_from:
            row["recentChanges"] += 1
            recent_total += 1
            if status in recent_status_counts:
                recent_status_counts[status] += 1
            else:
                recent_status_counts["unknown"] += 1

    version_rows = list(by_policy_version.values())
    for row in version_rows:
        row.pop("_latestUpdatedAt", None)
    version_rows.sort(
        key=lambda row: (
            -int(row.get("totalAlerts") or 0),
            str(row.get("policyVersion") or ""),
        )
    )

    return {
        "registryType": normalized_registry_type,
        "windowMinutes": window,
        "window": {
            "from": window_from.isoformat(),
            "to": now.isoformat(),
        },
        "counts": {
            "trackedPolicyVersions": len(items),
            "totalPolicyVersions": len(version_rows),
            "totalAlerts": total_alerts,
            "openBlockedCount": open_blocked_count,
            "resolvedCount": resolved_count,
            "recentChanges": recent_total,
        },
        "recentStatusCounts": recent_status_counts,
        "byPolicyVersion": version_rows,
    }


def _normalize_registry_dependency_trend_status(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    return normalized


def _build_registry_dependency_trend(
    *,
    alerts: list[Any],
    registry_type: str,
    window_minutes: int,
    status_filter: str | None,
    policy_version_filter: str | None,
    offset: int,
    limit: int,
) -> dict[str, Any]:
    normalized_registry_type = str(registry_type or "").strip().lower()
    normalized_status_filter = _normalize_registry_dependency_trend_status(status_filter)
    normalized_policy_version_filter = str(policy_version_filter or "").strip() or None
    window = max(10, min(int(window_minutes), 43200))
    page_offset = max(0, int(offset))
    page_limit = max(1, min(int(limit), 500))
    now = datetime.now(timezone.utc)
    window_from = now - timedelta(minutes=window)

    rows: list[dict[str, Any]] = []
    status_counts = {
        "raised": 0,
        "acked": 0,
        "resolved": 0,
        "unknown": 0,
    }

    for alert in alerts:
        alert_type = str(getattr(alert, "alert_type", "") or "").strip()
        if alert_type != REGISTRY_DEPENDENCY_ALERT_TYPE_BLOCKED:
            continue
        details = (
            dict(getattr(alert, "details"))
            if isinstance(getattr(alert, "details", None), dict)
            else {}
        )
        if str(details.get("registryType") or "").strip().lower() != normalized_registry_type:
            continue
        policy_version = str(details.get("version") or "").strip() or "unknown"
        if (
            normalized_policy_version_filter is not None
            and policy_version != normalized_policy_version_filter
        ):
            continue
        status = str(getattr(alert, "status", "") or "").strip().lower() or "unknown"
        if normalized_status_filter == "open":
            if status not in {"raised", "acked"}:
                continue
        elif normalized_status_filter is not None and status != normalized_status_filter:
            continue
        created_at = _normalize_aware_datetime(getattr(alert, "created_at", None)) or now
        updated_at = _normalize_aware_datetime(getattr(alert, "updated_at", None)) or created_at
        if updated_at < window_from:
            continue

        if status in status_counts:
            status_counts[status] += 1
        else:
            status_counts["unknown"] += 1

        dependency_payload = (
            details.get("dependency")
            if isinstance(details.get("dependency"), dict)
            else {}
        )
        rows.append(
            {
                "alertId": str(getattr(alert, "alert_id", "") or "").strip() or None,
                "caseId": int(getattr(alert, "job_id", 0) or 0),
                "scopeId": int(getattr(alert, "scope_id", 0) or 0),
                "traceId": str(getattr(alert, "trace_id", "") or "").strip() or None,
                "type": alert_type,
                "status": status,
                "severity": str(getattr(alert, "severity", "") or "").strip() or None,
                "title": str(getattr(alert, "title", "") or "").strip() or None,
                "message": str(getattr(alert, "message", "") or "").strip() or None,
                "registryType": normalized_registry_type,
                "policyVersion": policy_version,
                "action": str(details.get("action") or "").strip() or None,
                "dependencyCode": str(dependency_payload.get("code") or "").strip() or None,
                "dependencyOk": (
                    bool(dependency_payload.get("ok"))
                    if "ok" in dependency_payload
                    else None
                ),
                "createdAt": created_at.isoformat(),
                "updatedAt": updated_at.isoformat(),
                "_updatedAt": updated_at,
                "_createdAt": created_at,
            }
        )

    rows.sort(
        key=lambda row: (
            row.get("_updatedAt"),
            row.get("_createdAt"),
            str(row.get("alertId") or ""),
        ),
        reverse=True,
    )
    total_count = len(rows)
    paged_rows = rows[page_offset : page_offset + page_limit]
    for row in paged_rows:
        row.pop("_updatedAt", None)
        row.pop("_createdAt", None)

    return {
        "registryType": normalized_registry_type,
        "windowMinutes": window,
        "window": {
            "from": window_from.isoformat(),
            "to": now.isoformat(),
        },
        "filters": {
            "status": normalized_status_filter,
            "policyVersion": normalized_policy_version_filter,
            "offset": page_offset,
            "limit": page_limit,
        },
        "count": total_count,
        "returned": len(paged_rows),
        "statusCounts": status_counts,
        "items": paged_rows,
    }


def _normalize_ops_alert_status(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    return normalized


def _normalize_ops_alert_delivery_status(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    return normalized


def _normalize_ops_alert_fields_mode(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return "full"
    return normalized


def _normalize_registry_audit_action(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    return normalized


def _build_alert_outbox_index(events: list[Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for event in events:
        alert_id = str(getattr(event, "alert_id", "") or "").strip()
        if not alert_id:
            continue
        delivery_status = (
            str(getattr(event, "delivery_status", "") or "").strip().lower() or "unknown"
        )
        updated_at = _normalize_aware_datetime(
            getattr(event, "updated_at", None)
        ) or _normalize_aware_datetime(getattr(event, "created_at", None)) or datetime.now(timezone.utc)
        created_at = _normalize_aware_datetime(getattr(event, "created_at", None)) or updated_at
        row = index.setdefault(
            alert_id,
            {
                "alertId": alert_id,
                "totalEvents": 0,
                "deliveryCounts": {
                    "pending": 0,
                    "sent": 0,
                    "failed": 0,
                    "unknown": 0,
                },
                "latestEventId": None,
                "latestDeliveryStatus": None,
                "latestErrorMessage": None,
                "latestUpdatedAt": None,
                "_latestUpdatedAt": None,
                "_latestCreatedAt": None,
            },
        )
        row["totalEvents"] += 1
        if delivery_status in row["deliveryCounts"]:
            row["deliveryCounts"][delivery_status] += 1
        else:
            row["deliveryCounts"]["unknown"] += 1

        latest_updated_at = row.get("_latestUpdatedAt")
        latest_created_at = row.get("_latestCreatedAt")
        should_replace_latest = (
            not isinstance(latest_updated_at, datetime)
            or updated_at > latest_updated_at
            or (
                updated_at == latest_updated_at
                and (
                    not isinstance(latest_created_at, datetime)
                    or created_at >= latest_created_at
                )
            )
        )
        if should_replace_latest:
            row["_latestUpdatedAt"] = updated_at
            row["_latestCreatedAt"] = created_at
            row["latestEventId"] = str(getattr(event, "event_id", "") or "").strip() or None
            row["latestDeliveryStatus"] = delivery_status
            row["latestErrorMessage"] = (
                str(getattr(event, "error_message", "") or "").strip() or None
            )
            row["latestUpdatedAt"] = updated_at.isoformat()

    for row in index.values():
        row.pop("_latestUpdatedAt", None)
        row.pop("_latestCreatedAt", None)
    return index


def _build_registry_alert_ops_trend(
    *,
    rows: list[dict[str, Any]],
    window_minutes: int,
    bucket_minutes: int,
) -> dict[str, Any]:
    window = max(10, min(int(window_minutes), 43200))
    requested_bucket = max(5, min(int(bucket_minutes), 1440))
    max_buckets = 240
    effective_bucket = max(requested_bucket, math.ceil(window / max_buckets))

    now = datetime.now(timezone.utc)
    window_from = now - timedelta(minutes=window)
    bucket_count = max(1, math.ceil(window / effective_bucket))
    bucket_span_seconds = max(60, effective_bucket * 60)

    timeline: list[dict[str, Any]] = []
    for idx in range(bucket_count):
        bucket_start = window_from + timedelta(minutes=idx * effective_bucket)
        bucket_end = min(now, bucket_start + timedelta(minutes=effective_bucket))
        timeline.append(
            {
                "bucketStart": bucket_start.isoformat(),
                "bucketEnd": bucket_end.isoformat(),
                "count": 0,
                "byType": {},
                "byStatus": {},
                "byDeliveryStatus": {},
                "_bucketStart": bucket_start,
                "_bucketEnd": bucket_end,
            }
        )

    type_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    delivery_counts: dict[str, int] = {
        "pending": 0,
        "sent": 0,
        "failed": 0,
        "none": 0,
        "unknown": 0,
    }
    matched_rows = 0
    for row in rows:
        updated_at = row.get("_updatedAt")
        if not isinstance(updated_at, datetime):
            updated_at = _normalize_aware_datetime(row.get("updatedAt"))
        if not isinstance(updated_at, datetime):
            continue
        if updated_at < window_from or updated_at > now:
            continue

        matched_rows += 1
        row_type = str(row.get("type") or "").strip() or "unknown"
        row_status = str(row.get("status") or "").strip().lower() or "unknown"
        row_delivery_status = str(row.get("_deliveryStatus") or "").strip().lower()
        if not row_delivery_status:
            row_delivery_status = "none"
        elif row_delivery_status not in {"pending", "sent", "failed"}:
            row_delivery_status = "unknown"

        type_counts[row_type] = type_counts.get(row_type, 0) + 1
        status_counts[row_status] = status_counts.get(row_status, 0) + 1
        delivery_counts[row_delivery_status] = delivery_counts.get(row_delivery_status, 0) + 1

        bucket_index = int((updated_at - window_from).total_seconds() // bucket_span_seconds)
        if bucket_index < 0:
            continue
        if bucket_index >= len(timeline):
            bucket_index = len(timeline) - 1
        bucket = timeline[bucket_index]
        bucket["count"] += 1
        bucket_type = bucket["byType"]
        bucket_status = bucket["byStatus"]
        bucket_delivery = bucket["byDeliveryStatus"]
        bucket_type[row_type] = bucket_type.get(row_type, 0) + 1
        bucket_status[row_status] = bucket_status.get(row_status, 0) + 1
        bucket_delivery[row_delivery_status] = bucket_delivery.get(row_delivery_status, 0) + 1

    timeline_rows: list[dict[str, Any]] = []
    for bucket in timeline:
        if int(bucket.get("count") or 0) <= 0:
            continue
        bucket.pop("_bucketStart", None)
        bucket.pop("_bucketEnd", None)
        bucket["byType"] = dict(sorted(bucket["byType"].items(), key=lambda kv: kv[0]))
        bucket["byStatus"] = dict(sorted(bucket["byStatus"].items(), key=lambda kv: kv[0]))
        bucket["byDeliveryStatus"] = dict(
            sorted(bucket["byDeliveryStatus"].items(), key=lambda kv: kv[0])
        )
        timeline_rows.append(bucket)

    return {
        "windowMinutes": window,
        "bucketMinutes": effective_bucket,
        "requestedBucketMinutes": requested_bucket,
        "window": {
            "from": window_from.isoformat(),
            "to": now.isoformat(),
        },
        "count": matched_rows,
        "typeCounts": dict(sorted(type_counts.items(), key=lambda kv: kv[0])),
        "statusCounts": dict(sorted(status_counts.items(), key=lambda kv: kv[0])),
        "deliveryStatusCounts": delivery_counts,
        "timeline": timeline_rows,
    }


def _serialize_registry_alert_ops_item(
    row: dict[str, Any],
    *,
    fields_mode: str,
) -> dict[str, Any]:
    if fields_mode == "full":
        payload = dict(row)
        payload.pop("_updatedAt", None)
        payload.pop("_createdAt", None)
        payload.pop("_deliveryStatus", None)
        return payload

    outbox_payload = (
        dict(row.get("outbox"))
        if isinstance(row.get("outbox"), dict)
        else {}
    )
    return {
        "alertId": row.get("alertId"),
        "caseId": row.get("caseId"),
        "scopeId": row.get("scopeId"),
        "traceId": row.get("traceId"),
        "type": row.get("type"),
        "status": row.get("status"),
        "severity": row.get("severity"),
        "title": row.get("title"),
        "registryType": row.get("registryType"),
        "policyVersion": row.get("policyVersion"),
        "action": row.get("action"),
        "gateCode": row.get("gateCode"),
        "gateMessage": row.get("gateMessage"),
        "overrideApplied": row.get("overrideApplied"),
        "gateActor": row.get("gateActor"),
        "gateReason": row.get("gateReason"),
        "gateLatestRunId": row.get("gateLatestRunId"),
        "gateLatestRunStatus": row.get("gateLatestRunStatus"),
        "gateLatestRunThresholdDecision": row.get("gateLatestRunThresholdDecision"),
        "gateLatestRunEnvironmentMode": row.get("gateLatestRunEnvironmentMode"),
        "gateLatestRunNeedsRemediation": row.get("gateLatestRunNeedsRemediation"),
        "dependencyCode": row.get("dependencyCode"),
        "createdAt": row.get("createdAt"),
        "updatedAt": row.get("updatedAt"),
        "outbox": {
            "totalEvents": int(outbox_payload.get("totalEvents", 0) or 0),
            "latestEventId": outbox_payload.get("latestEventId"),
            "latestDeliveryStatus": outbox_payload.get("latestDeliveryStatus"),
            "latestErrorMessage": outbox_payload.get("latestErrorMessage"),
            "latestUpdatedAt": outbox_payload.get("latestUpdatedAt"),
        },
    }


def _build_registry_alert_link_index_for_audits(
    *,
    alerts: list[Any],
    outbox_events: list[Any],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    outbox_index = _build_alert_outbox_index(outbox_events)
    rows_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for alert in alerts:
        row_type = str(getattr(alert, "alert_type", "") or "").strip()
        if row_type not in OPS_REGISTRY_ALERT_TYPES:
            continue
        details = (
            dict(getattr(alert, "details"))
            if isinstance(getattr(alert, "details", None), dict)
            else {}
        )
        row_registry_type = str(details.get("registryType") or "").strip().lower() or None
        row_policy_version = str(details.get("version") or "").strip() or None
        if row_registry_type is None or row_policy_version is None:
            continue

        gate_payload = details.get("gate") if isinstance(details.get("gate"), dict) else {}
        dependency_payload = (
            details.get("dependency")
            if isinstance(details.get("dependency"), dict)
            else {}
        )
        row_outbox = outbox_index.get(str(getattr(alert, "alert_id", "") or "").strip())
        created_at = _normalize_aware_datetime(getattr(alert, "created_at", None)) or datetime.now(timezone.utc)
        updated_at = _normalize_aware_datetime(getattr(alert, "updated_at", None)) or created_at

        row = {
            "alertId": str(getattr(alert, "alert_id", "") or "").strip() or None,
            "caseId": int(getattr(alert, "job_id", 0) or 0),
            "scopeId": int(getattr(alert, "scope_id", 0) or 0),
            "traceId": str(getattr(alert, "trace_id", "") or "").strip() or None,
            "type": row_type,
            "status": str(getattr(alert, "status", "") or "").strip().lower() or "unknown",
            "severity": str(getattr(alert, "severity", "") or "").strip() or None,
            "title": str(getattr(alert, "title", "") or "").strip() or None,
            "message": str(getattr(alert, "message", "") or "").strip() or None,
            "registryType": row_registry_type,
            "policyVersion": row_policy_version,
            "gateCode": str(gate_payload.get("code") or "").strip() or None,
            "overrideApplied": _extract_optional_bool(
                {"overrideApplied": details.get("overrideApplied")},
                "overrideApplied",
            ),
            "gateActor": str(details.get("actor") or "").strip() or None,
            "gateReason": str(details.get("reason") or "").strip() or None,
            "dependencyCode": str(dependency_payload.get("code") or "").strip() or None,
            "createdAt": created_at.isoformat(),
            "updatedAt": updated_at.isoformat(),
            "outbox": (
                dict(row_outbox)
                if isinstance(row_outbox, dict)
                else {
                    "alertId": str(getattr(alert, "alert_id", "") or "").strip() or None,
                    "totalEvents": 0,
                    "deliveryCounts": {
                        "pending": 0,
                        "sent": 0,
                        "failed": 0,
                        "unknown": 0,
                    },
                    "latestEventId": None,
                    "latestDeliveryStatus": None,
                    "latestErrorMessage": None,
                    "latestUpdatedAt": None,
                }
            ),
            "_updatedAt": updated_at,
        }
        rows_by_key.setdefault((row_registry_type, row_policy_version), []).append(row)

    for key, rows in rows_by_key.items():
        rows.sort(
            key=lambda row: (
                row.get("_updatedAt"),
                str(row.get("alertId") or ""),
            ),
            reverse=True,
        )
        cleaned_rows: list[dict[str, Any]] = []
        for row in rows:
            row_copy = dict(row)
            row_copy.pop("_updatedAt", None)
            cleaned_rows.append(row_copy)
        rows_by_key[key] = cleaned_rows
    return rows_by_key


def _build_registry_audit_ops_view(
    *,
    registry_type: str,
    audit_items: list[dict[str, Any]],
    alerts: list[Any],
    outbox_events: list[Any],
    action: str | None,
    version: str | None,
    actor: str | None,
    gate_code: str | None,
    override_applied: bool | None,
    include_gate_view: bool,
    link_limit: int,
    offset: int,
    limit: int,
) -> dict[str, Any]:
    normalized_registry_type = str(registry_type or "").strip().lower()
    normalized_action = _normalize_registry_audit_action(action)
    normalized_version = str(version or "").strip() or None
    normalized_actor = str(actor or "").strip() or None
    normalized_gate_code = str(gate_code or "").strip() or None
    page_offset = max(0, int(offset))
    page_limit = max(1, min(int(limit), 500))
    resolved_link_limit = max(1, min(int(link_limit), 20))

    alert_link_index: dict[tuple[str, str], list[dict[str, Any]]] = {}
    if include_gate_view:
        alert_link_index = _build_registry_alert_link_index_for_audits(
            alerts=alerts,
            outbox_events=outbox_events,
        )

    rows: list[dict[str, Any]] = []
    counts_by_action: dict[str, int] = {}
    counts_by_version: dict[str, int] = {"unknown": 0}
    counts_by_actor: dict[str, int] = {}
    counts_by_gate_code: dict[str, int] = {"unknown": 0}
    counts_by_override_applied: dict[str, int] = {
        "true": 0,
        "false": 0,
        "unknown": 0,
    }
    with_gate_review_count = 0
    with_linked_alerts_count = 0
    linked_outbox_failed_count = 0

    for item in audit_items:
        row_registry_type = str(item.get("registryType") or "").strip().lower()
        if normalized_registry_type and row_registry_type != normalized_registry_type:
            continue
        row_action = str(item.get("action") or "").strip().lower() or "unknown"
        if normalized_action is not None and row_action != normalized_action:
            continue
        row_version = str(item.get("version") or "").strip() or None
        if normalized_version is not None and row_version != normalized_version:
            continue
        row_actor = str(item.get("actor") or "").strip() or None
        if normalized_actor is not None and row_actor != normalized_actor:
            continue
        row_reason = str(item.get("reason") or "").strip() or None
        details = dict(item.get("details")) if isinstance(item.get("details"), dict) else {}

        fairness_gate = (
            details.get("fairnessGate")
            if isinstance(details.get("fairnessGate"), dict)
            else {}
        )
        dependency_health = (
            details.get("dependencyHealth")
            if isinstance(details.get("dependencyHealth"), dict)
            else {}
        )
        latest_run = (
            fairness_gate.get("latestRun")
            if isinstance(fairness_gate.get("latestRun"), dict)
            else {}
        )
        row_gate_code = str(fairness_gate.get("code") or "").strip() or None
        if normalized_gate_code is not None and row_gate_code != normalized_gate_code:
            continue
        row_override_applied = _extract_optional_bool(
            {"overrideApplied": fairness_gate.get("overrideApplied")},
            "overrideApplied",
        )
        if (
            override_applied is not None
            and row_override_applied is not None
            and row_override_applied != override_applied
        ):
            continue
        if override_applied is not None and row_override_applied is None:
            continue

        row_created_at_text = str(item.get("createdAt") or "").strip() or None
        row_created_at = _extract_optional_datetime(
            {"createdAt": row_created_at_text},
            "createdAt",
        ) or datetime.now(timezone.utc)

        gate_review = {
            "hasFairnessGate": bool(fairness_gate),
            "hasDependencyHealth": bool(dependency_health),
            "gateCode": row_gate_code,
            "gateMessage": str(fairness_gate.get("message") or "").strip() or None,
            "gatePassed": _extract_optional_bool({"passed": fairness_gate.get("passed")}, "passed"),
            "overrideApplied": row_override_applied,
            "thresholdDecision": str(fairness_gate.get("thresholdDecision") or "").strip() or None,
            "needsRemediation": _extract_optional_bool(
                {"needsRemediation": fairness_gate.get("needsRemediation")},
                "needsRemediation",
            ),
            "dependencyOk": _extract_optional_bool(
                {"ok": dependency_health.get("ok")},
                "ok",
            ),
            "dependencyCode": str(dependency_health.get("code") or "").strip() or None,
            "latestRunId": str(latest_run.get("runId") or "").strip() or None,
            "latestRunStatus": str(latest_run.get("status") or "").strip() or None,
            "latestRunThresholdDecision": (
                str(latest_run.get("thresholdDecision") or "").strip() or None
            ),
            "latestRunEnvironmentMode": (
                str(latest_run.get("environmentMode") or "").strip() or None
            ),
            "latestRunNeedsRemediation": _extract_optional_bool(
                {"needsRemediation": latest_run.get("needsRemediation")},
                "needsRemediation",
            ),
            "actor": row_actor,
            "reason": row_reason,
        }

        linked_alerts: list[dict[str, Any]] = []
        linked_alert_summary: dict[str, Any] | None = None
        if include_gate_view and row_version is not None:
            candidates = alert_link_index.get((row_registry_type, row_version), [])
            linked_alerts = [dict(row) for row in candidates[:resolved_link_limit]]

            linked_by_type: dict[str, int] = {}
            linked_by_status: dict[str, int] = {}
            linked_by_delivery: dict[str, int] = {
                "pending": 0,
                "sent": 0,
                "failed": 0,
                "none": 0,
                "unknown": 0,
            }
            linked_open_count = 0
            linked_resolved_count = 0
            linked_failed_count = 0
            for row in linked_alerts:
                alert_type = str(row.get("type") or "").strip() or "unknown"
                alert_status = str(row.get("status") or "").strip().lower() or "unknown"
                latest_delivery = str(
                    (row.get("outbox") or {}).get("latestDeliveryStatus") or ""
                ).strip().lower()
                if latest_delivery in linked_by_delivery:
                    linked_by_delivery[latest_delivery] += 1
                elif latest_delivery:
                    linked_by_delivery["unknown"] += 1
                else:
                    linked_by_delivery["none"] += 1
                if alert_status in {"raised", "acked"}:
                    linked_open_count += 1
                if alert_status == "resolved":
                    linked_resolved_count += 1
                if latest_delivery == "failed":
                    linked_failed_count += 1
                linked_by_type[alert_type] = linked_by_type.get(alert_type, 0) + 1
                linked_by_status[alert_status] = linked_by_status.get(alert_status, 0) + 1

            linked_alert_summary = {
                "count": len(linked_alerts),
                "byType": dict(sorted(linked_by_type.items(), key=lambda kv: kv[0])),
                "byStatus": dict(sorted(linked_by_status.items(), key=lambda kv: kv[0])),
                "byDeliveryStatus": linked_by_delivery,
                "openCount": linked_open_count,
                "resolvedCount": linked_resolved_count,
                "outboxFailedCount": linked_failed_count,
            }

        has_gate_review = bool(gate_review.get("hasFairnessGate")) or bool(gate_review.get("hasDependencyHealth"))
        if has_gate_review:
            with_gate_review_count += 1
        if include_gate_view and linked_alerts:
            with_linked_alerts_count += 1
            linked_outbox_failed_count += int(
                (linked_alert_summary or {}).get("outboxFailedCount") or 0
            )

        counts_by_action[row_action] = counts_by_action.get(row_action, 0) + 1
        if row_version:
            counts_by_version[row_version] = counts_by_version.get(row_version, 0) + 1
        else:
            counts_by_version["unknown"] += 1
        if row_actor:
            counts_by_actor[row_actor] = counts_by_actor.get(row_actor, 0) + 1
        if row_gate_code:
            counts_by_gate_code[row_gate_code] = counts_by_gate_code.get(row_gate_code, 0) + 1
        else:
            counts_by_gate_code["unknown"] += 1
        if row_override_applied is True:
            counts_by_override_applied["true"] += 1
        elif row_override_applied is False:
            counts_by_override_applied["false"] += 1
        else:
            counts_by_override_applied["unknown"] += 1

        rows.append(
            {
                "registryType": row_registry_type,
                "action": row_action,
                "version": row_version,
                "actor": row_actor,
                "reason": row_reason,
                "details": details,
                "createdAt": row_created_at_text,
                "gateReview": gate_review,
                "linkedAlerts": linked_alerts if include_gate_view else None,
                "linkedAlertSummary": linked_alert_summary if include_gate_view else None,
                "_createdAt": row_created_at,
            }
        )

    rows.sort(
        key=lambda row: (
            row.get("_createdAt"),
            str(row.get("action") or ""),
            str(row.get("version") or ""),
        ),
        reverse=True,
    )
    total_count = len(rows)
    paged_rows = rows[page_offset : page_offset + page_limit]
    for row in paged_rows:
        row.pop("_createdAt", None)

    return {
        "registryType": normalized_registry_type,
        "count": total_count,
        "returned": len(paged_rows),
        "items": paged_rows,
        "aggregations": {
            "byAction": dict(sorted(counts_by_action.items(), key=lambda kv: kv[0])),
            "byVersion": dict(sorted(counts_by_version.items(), key=lambda kv: kv[0])),
            "byActor": dict(sorted(counts_by_actor.items(), key=lambda kv: kv[0])),
            "byGateCode": dict(sorted(counts_by_gate_code.items(), key=lambda kv: kv[0])),
            "byOverrideApplied": counts_by_override_applied,
            "withGateReviewCount": with_gate_review_count,
            "withLinkedAlertsCount": with_linked_alerts_count,
            "linkedOutboxFailedCount": linked_outbox_failed_count,
        },
        "filters": {
            "action": normalized_action,
            "version": normalized_version,
            "actor": normalized_actor,
            "gateCode": normalized_gate_code,
            "overrideApplied": override_applied,
            "includeGateView": bool(include_gate_view),
            "linkLimit": resolved_link_limit,
            "offset": page_offset,
            "limit": page_limit,
        },
        "limit": page_limit,
    }


def _build_registry_alert_ops_view(
    *,
    alerts: list[Any],
    outbox_events: list[Any],
    alert_type: str | None,
    status: str | None,
    delivery_status: str | None,
    registry_type: str | None,
    policy_version: str | None,
    gate_code: str | None,
    gate_actor: str | None,
    override_applied: bool | None,
    fields_mode: str,
    include_trend: bool,
    trend_window_minutes: int,
    trend_bucket_minutes: int,
    offset: int,
    limit: int,
) -> dict[str, Any]:
    normalized_alert_type = str(alert_type or "").strip() or None
    normalized_status = _normalize_ops_alert_status(status)
    normalized_delivery_status = _normalize_ops_alert_delivery_status(delivery_status)
    normalized_fields_mode = _normalize_ops_alert_fields_mode(fields_mode)
    normalized_registry_type = str(registry_type or "").strip().lower() or None
    normalized_policy_version = str(policy_version or "").strip() or None
    normalized_gate_code = str(gate_code or "").strip() or None
    normalized_gate_actor = str(gate_actor or "").strip() or None
    page_offset = max(0, int(offset))
    page_limit = max(1, min(int(limit), 500))
    outbox_index = _build_alert_outbox_index(outbox_events)

    rows: list[dict[str, Any]] = []
    counts_by_type: dict[str, int] = {}
    counts_by_status: dict[str, int] = {}
    counts_by_delivery: dict[str, int] = {
        "pending": 0,
        "sent": 0,
        "failed": 0,
        "none": 0,
        "unknown": 0,
    }
    counts_by_gate_code: dict[str, int] = {"unknown": 0}
    counts_by_gate_actor: dict[str, int] = {}
    counts_by_override_applied: dict[str, int] = {
        "true": 0,
        "false": 0,
        "unknown": 0,
    }
    counts_by_registry_type: dict[str, int] = {}
    counts_by_policy_version: dict[str, int] = {"unknown": 0}
    open_count = 0
    resolved_count = 0
    outbox_failed_count = 0
    override_applied_count = 0
    blocked_without_override_count = 0

    for alert in alerts:
        row_type = str(getattr(alert, "alert_type", "") or "").strip()
        if row_type not in OPS_REGISTRY_ALERT_TYPES:
            continue
        if normalized_alert_type is not None and row_type != normalized_alert_type:
            continue
        row_status = str(getattr(alert, "status", "") or "").strip().lower() or "unknown"
        if normalized_status == "open":
            if row_status not in {"raised", "acked"}:
                continue
        elif normalized_status is not None and row_status != normalized_status:
            continue
        details = (
            dict(getattr(alert, "details"))
            if isinstance(getattr(alert, "details", None), dict)
            else {}
        )
        gate_payload = details.get("gate") if isinstance(details.get("gate"), dict) else {}
        row_gate_code = str(gate_payload.get("code") or "").strip() or None
        row_gate_actor = str(details.get("actor") or "").strip() or None
        row_gate_reason = str(details.get("reason") or "").strip() or None
        row_override_applied = _extract_optional_bool(
            {"overrideApplied": details.get("overrideApplied")},
            "overrideApplied",
        )
        if normalized_gate_code is not None and row_gate_code != normalized_gate_code:
            continue
        if normalized_gate_actor is not None and row_gate_actor != normalized_gate_actor:
            continue
        if (
            override_applied is not None
            and row_override_applied is not None
            and row_override_applied != override_applied
        ):
            continue
        if override_applied is not None and row_override_applied is None:
            continue

        row_registry_type = str(details.get("registryType") or "").strip().lower() or None
        if (
            normalized_registry_type is not None
            and row_registry_type != normalized_registry_type
        ):
            continue
        row_policy_version = str(details.get("version") or "").strip() or None
        if (
            normalized_policy_version is not None
            and row_policy_version != normalized_policy_version
        ):
            continue

        row_outbox = outbox_index.get(str(getattr(alert, "alert_id", "") or "").strip())
        latest_delivery = (
            str(row_outbox.get("latestDeliveryStatus") or "").strip().lower()
            if isinstance(row_outbox, dict)
            else ""
        )
        if normalized_delivery_status is not None and latest_delivery != normalized_delivery_status:
            continue
        if row_status in {"raised", "acked"}:
            open_count += 1
        if row_status == "resolved":
            resolved_count += 1
        if latest_delivery == "failed":
            outbox_failed_count += 1

        counts_by_type[row_type] = counts_by_type.get(row_type, 0) + 1
        counts_by_status[row_status] = counts_by_status.get(row_status, 0) + 1
        if latest_delivery in counts_by_delivery:
            counts_by_delivery[latest_delivery] += 1
        elif latest_delivery:
            counts_by_delivery["unknown"] += 1
        else:
            counts_by_delivery["none"] += 1
        if row_gate_code:
            counts_by_gate_code[row_gate_code] = counts_by_gate_code.get(row_gate_code, 0) + 1
        else:
            counts_by_gate_code["unknown"] += 1
        if row_gate_actor:
            counts_by_gate_actor[row_gate_actor] = counts_by_gate_actor.get(row_gate_actor, 0) + 1
        if row_override_applied is True:
            counts_by_override_applied["true"] += 1
            override_applied_count += 1
        elif row_override_applied is False:
            counts_by_override_applied["false"] += 1
            if row_type == REGISTRY_FAIRNESS_ALERT_TYPE_BLOCKED:
                blocked_without_override_count += 1
        else:
            counts_by_override_applied["unknown"] += 1

        if row_registry_type:
            counts_by_registry_type[row_registry_type] = (
                counts_by_registry_type.get(row_registry_type, 0) + 1
            )
        if row_policy_version:
            counts_by_policy_version[row_policy_version] = (
                counts_by_policy_version.get(row_policy_version, 0) + 1
            )
        else:
            counts_by_policy_version["unknown"] += 1

        created_at = _normalize_aware_datetime(getattr(alert, "created_at", None)) or datetime.now(timezone.utc)
        updated_at = _normalize_aware_datetime(getattr(alert, "updated_at", None)) or created_at
        dependency_payload = (
            details.get("dependency")
            if isinstance(details.get("dependency"), dict)
            else {}
        )
        latest_run_payload = (
            gate_payload.get("latestRun")
            if isinstance(gate_payload.get("latestRun"), dict)
            else {}
        )
        rows.append(
            {
                "alertId": str(getattr(alert, "alert_id", "") or "").strip() or None,
                "caseId": int(getattr(alert, "job_id", 0) or 0),
                "scopeId": int(getattr(alert, "scope_id", 0) or 0),
                "traceId": str(getattr(alert, "trace_id", "") or "").strip() or None,
                "type": row_type,
                "status": row_status,
                "severity": str(getattr(alert, "severity", "") or "").strip() or None,
                "title": str(getattr(alert, "title", "") or "").strip() or None,
                "message": str(getattr(alert, "message", "") or "").strip() or None,
                "registryType": row_registry_type,
                "policyVersion": row_policy_version,
                "action": str(details.get("action") or "").strip() or None,
                "gateCode": row_gate_code,
                "gateMessage": str(gate_payload.get("message") or "").strip() or None,
                "overrideApplied": row_override_applied,
                "gateActor": row_gate_actor,
                "gateReason": row_gate_reason,
                "gateLatestRunId": str(latest_run_payload.get("runId") or "").strip() or None,
                "gateLatestRunStatus": str(latest_run_payload.get("status") or "").strip() or None,
                "gateLatestRunThresholdDecision": (
                    str(latest_run_payload.get("thresholdDecision") or "").strip() or None
                ),
                "gateLatestRunEnvironmentMode": (
                    str(latest_run_payload.get("environmentMode") or "").strip() or None
                ),
                "gateLatestRunNeedsRemediation": _extract_optional_bool(
                    {"needsRemediation": latest_run_payload.get("needsRemediation")},
                    "needsRemediation",
                ),
                "dependencyCode": str(dependency_payload.get("code") or "").strip() or None,
                "createdAt": created_at.isoformat(),
                "updatedAt": updated_at.isoformat(),
                "outbox": (
                    dict(row_outbox)
                    if isinstance(row_outbox, dict)
                    else {
                        "alertId": str(getattr(alert, "alert_id", "") or "").strip() or None,
                        "totalEvents": 0,
                        "deliveryCounts": {
                            "pending": 0,
                            "sent": 0,
                            "failed": 0,
                            "unknown": 0,
                        },
                        "latestEventId": None,
                        "latestDeliveryStatus": None,
                        "latestErrorMessage": None,
                        "latestUpdatedAt": None,
                    }
                ),
                "_updatedAt": updated_at,
                "_createdAt": created_at,
                "_deliveryStatus": latest_delivery or "none",
            }
        )

    rows.sort(
        key=lambda row: (
            row.get("_updatedAt"),
            row.get("_createdAt"),
            str(row.get("alertId") or ""),
        ),
        reverse=True,
    )
    total_count = len(rows)
    paged_rows = rows[page_offset : page_offset + page_limit]
    serialized_rows = [
        _serialize_registry_alert_ops_item(
            row,
            fields_mode=normalized_fields_mode,
        )
        for row in paged_rows
    ]
    trend_payload = (
        _build_registry_alert_ops_trend(
            rows=rows,
            window_minutes=trend_window_minutes,
            bucket_minutes=trend_bucket_minutes,
        )
        if include_trend
        else None
    )

    return {
        "count": total_count,
        "returned": len(serialized_rows),
        "items": serialized_rows,
        "aggregations": {
            "byType": dict(sorted(counts_by_type.items(), key=lambda kv: kv[0])),
            "byStatus": dict(sorted(counts_by_status.items(), key=lambda kv: kv[0])),
            "byDeliveryStatus": counts_by_delivery,
            "byGateCode": dict(sorted(counts_by_gate_code.items(), key=lambda kv: kv[0])),
            "byGateActor": dict(sorted(counts_by_gate_actor.items(), key=lambda kv: kv[0])),
            "byOverrideApplied": counts_by_override_applied,
            "byRegistryType": dict(sorted(counts_by_registry_type.items(), key=lambda kv: kv[0])),
            "byPolicyVersion": dict(sorted(counts_by_policy_version.items(), key=lambda kv: kv[0])),
            "openCount": open_count,
            "resolvedCount": resolved_count,
            "outboxFailedCount": outbox_failed_count,
            "overrideAppliedCount": override_applied_count,
            "blockedWithoutOverrideCount": blocked_without_override_count,
        },
        "trend": trend_payload,
        "filters": {
            "alertType": normalized_alert_type,
            "status": normalized_status,
            "deliveryStatus": normalized_delivery_status,
            "registryType": normalized_registry_type,
            "policyVersion": normalized_policy_version,
            "gateCode": normalized_gate_code,
            "gateActor": normalized_gate_actor,
            "overrideApplied": override_applied,
            "fieldsMode": normalized_fields_mode,
            "includeTrend": bool(include_trend),
            "trendWindowMinutes": int(trend_window_minutes),
            "trendBucketMinutes": int(trend_bucket_minutes),
            "offset": page_offset,
            "limit": page_limit,
        },
    }


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


def _extract_latest_challenge_snapshot(workflow_events: list[Any]) -> dict[str, Any] | None:
    for event in reversed(workflow_events):
        if str(getattr(event, "event_type", "") or "").strip() != TRUST_CHALLENGE_EVENT_TYPE:
            continue
        payload = event.payload if isinstance(getattr(event, "payload", None), dict) else {}
        state = str(
            payload.get("state")
            or payload.get("challengeState")
            or payload.get("currentState")
            or ""
        ).strip()
        if not state:
            continue
        return {
            "state": state,
            "reasonCode": (
                str(payload.get("reasonCode") or payload.get("challengeReasonCode") or "").strip()
                or None
            ),
            "reason": (
                str(payload.get("reason") or payload.get("challengeReason") or "").strip() or None
            ),
            "requestedBy": (
                str(
                    payload.get("requestedBy")
                    or payload.get("challengeRequestedBy")
                    or ""
                ).strip()
                or None
            ),
            "decidedBy": (
                str(
                    payload.get("decidedBy")
                    or payload.get("challengeDecisionBy")
                    or ""
                ).strip()
                or None
            ),
            "dispatchType": str(payload.get("dispatchType") or "").strip() or None,
            "at": (
                getattr(event, "created_at", None).isoformat()
                if isinstance(getattr(event, "created_at", None), datetime)
                else None
            ),
        }
    return None


def _build_case_fairness_item(
    *,
    case_id: int,
    dispatch_type: str,
    trace_id: str,
    workflow_job: WorkflowJob | None,
    workflow_events: list[Any],
    report_payload: dict[str, Any],
    latest_run: FactFairnessBenchmarkRun | None,
) -> dict[str, Any]:
    fairness_summary = (
        report_payload.get("fairnessSummary")
        if isinstance(report_payload.get("fairnessSummary"), dict)
        else {}
    )
    judge_trace = (
        report_payload.get("judgeTrace")
        if isinstance(report_payload.get("judgeTrace"), dict)
        else {}
    )
    panel_runtime_profiles = (
        judge_trace.get("panelRuntimeProfiles")
        if isinstance(judge_trace.get("panelRuntimeProfiles"), dict)
        else {}
    )
    winner = str(report_payload.get("winner") or "").strip().lower() or None
    review_required = bool(report_payload.get("reviewRequired"))
    error_codes = [
        str(item).strip()
        for item in (report_payload.get("errorCodes") or [])
        if str(item).strip()
    ]
    panel_high_disagreement = bool(fairness_summary.get("panelHighDisagreement"))
    challenge_snapshot = _extract_latest_challenge_snapshot(workflow_events)
    policy_version = (
        str((judge_trace.get("policyRegistry") or {}).get("version") or "").strip()
        if isinstance(judge_trace.get("policyRegistry"), dict)
        else ""
    ) or None
    run_summary = (
        latest_run.summary if latest_run is not None and isinstance(latest_run.summary, dict) else {}
    )
    drift_payload = run_summary.get("drift") if isinstance(run_summary.get("drift"), dict) else {}
    threshold_breaches = run_summary.get("thresholdBreaches")
    if not isinstance(threshold_breaches, list):
        threshold_breaches = []
    drift_breaches = drift_payload.get("driftBreaches")
    if not isinstance(drift_breaches, list):
        drift_breaches = []
    gate_conclusion = "review_required" if review_required else "auto_passed"
    if (
        latest_run is not None
        and latest_run.threshold_decision != "accepted"
        and gate_conclusion != "review_required"
    ):
        gate_conclusion = "benchmark_attention_required"

    return {
        "caseId": case_id,
        "dispatchType": dispatch_type,
        "traceId": trace_id or None,
        "workflowStatus": workflow_job.status if workflow_job is not None else None,
        "updatedAt": (
            workflow_job.updated_at.isoformat()
            if workflow_job is not None and isinstance(workflow_job.updated_at, datetime)
            else None
        ),
        "winner": winner,
        "reviewRequired": review_required,
        "gateConclusion": gate_conclusion,
        "errorCodes": error_codes,
        "panelDisagreement": {
            "high": panel_high_disagreement,
            "ratio": _safe_float(fairness_summary.get("panelDisagreementRatio"), default=0.0),
            "ratioMax": _safe_float(fairness_summary.get("panelDisagreementRatioMax"), default=0.0),
            "reasons": [
                str(item).strip()
                for item in (fairness_summary.get("panelDisagreementReasons") or [])
                if str(item).strip()
            ],
            "majorityWinner": (
                str(fairness_summary.get("panelMajorityWinner") or "").strip().lower() or None
            ),
            "voteBySide": (
                fairness_summary.get("panelVoteBySide")
                if isinstance(fairness_summary.get("panelVoteBySide"), dict)
                else {}
            ),
            "runtimeProfiles": panel_runtime_profiles,
        },
        "driftSummary": {
            "policyVersion": policy_version,
            "latestRun": (
                _serialize_fairness_benchmark_run(latest_run)
                if latest_run is not None
                else None
            ),
            "thresholdBreaches": [str(item).strip() for item in threshold_breaches if str(item).strip()],
            "driftBreaches": [str(item).strip() for item in drift_breaches if str(item).strip()],
            "hasThresholdBreach": bool(run_summary.get("hasThresholdBreach")),
            "hasDriftBreach": bool(drift_payload.get("hasDriftBreach")),
        },
        "challengeLink": {
            "latest": challenge_snapshot,
            "hasOpenReview": (
                workflow_job is not None
                and workflow_job.status in {"review_required", "draw_pending_vote"}
            ),
        },
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


def _extract_optional_float(payload: dict[str, Any], *keys: str) -> float | None:
    value = _extract_raw_field(payload, *keys)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_optional_str(payload: dict[str, Any], *keys: str) -> str | None:
    value = _extract_raw_field(payload, *keys)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _extract_optional_bool(payload: dict[str, Any], *keys: str) -> bool | None:
    value = _extract_raw_field(payload, *keys)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    token = str(value).strip().lower()
    if token in {"1", "true", "yes", "on"}:
        return True
    if token in {"0", "false", "no", "off"}:
        return False
    return None


def _extract_optional_datetime(payload: dict[str, Any], *keys: str) -> datetime | None:
    value = _extract_raw_field(payload, *keys)
    if value is None:
        return None
    if isinstance(value, datetime):
        return _normalize_query_datetime(value)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return _normalize_query_datetime(parsed)


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
    fairness_thresholds: dict[str, Any] | None = None,
    panel_runtime_profiles: dict[str, dict[str, Any]] | None = None,
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
        fairness_thresholds=fairness_thresholds,
        panel_runtime_profiles=panel_runtime_profiles,
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

    async def _ensure_registry_runtime_ready() -> None:
        await _ensure_workflow_schema_ready()
        await _ensure_registry_runtime_loaded(runtime=runtime)

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

    async def _upsert_claim_ledger_record(
        *,
        case_id: int,
        dispatch_type: str,
        trace_id: str,
        report_payload: dict[str, Any] | None,
    ) -> FactClaimLedgerRecord | None:
        payload = report_payload if isinstance(report_payload, dict) else {}
        if not payload:
            return None
        verdict_contract = _build_verdict_contract(payload)
        evidence_view = _build_case_evidence_view(
            report_payload=payload,
            verdict_contract=verdict_contract,
            claim_ledger_record=None,
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
        if claim_graph is None and claim_graph_summary is None and not verdict_evidence_refs:
            return None
        await _ensure_workflow_schema_ready()
        return await runtime.workflow_runtime.facts.upsert_claim_ledger_record(
            case_id=case_id,
            dispatch_type=dispatch_type,
            trace_id=trace_id,
            claim_graph=claim_graph,
            claim_graph_summary=claim_graph_summary,
            evidence_ledger=evidence_ledger,
            verdict_evidence_refs=verdict_evidence_refs,
        )

    async def _get_claim_ledger_record(
        *,
        case_id: int,
        dispatch_type: str | None = None,
    ) -> FactClaimLedgerRecord | None:
        await _ensure_workflow_schema_ready()
        return await runtime.workflow_runtime.facts.get_claim_ledger_record(
            case_id=case_id,
            dispatch_type=dispatch_type,
        )

    async def _list_claim_ledger_records(
        *,
        case_id: int,
        limit: int = 20,
    ) -> list[FactClaimLedgerRecord]:
        await _ensure_workflow_schema_ready()
        return await runtime.workflow_runtime.facts.list_claim_ledger_records(
            case_id=case_id,
            limit=limit,
        )

    async def _upsert_fairness_benchmark_run(
        *,
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
    ) -> FactFairnessBenchmarkRun:
        await _ensure_workflow_schema_ready()
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

    async def _list_fairness_benchmark_runs(
        *,
        policy_version: str | None = None,
        environment_mode: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[FactFairnessBenchmarkRun]:
        await _ensure_workflow_schema_ready()
        return await runtime.workflow_runtime.facts.list_fairness_benchmark_runs(
            policy_version=policy_version,
            environment_mode=environment_mode,
            status=status,
            limit=limit,
        )

    async def _evaluate_policy_release_fairness_gate(
        *,
        policy_version: str,
    ) -> dict[str, Any]:
        version = str(policy_version or "").strip()
        if not version:
            return {
                "passed": False,
                "code": "registry_fairness_gate_invalid_policy_version",
                "message": "policy version is empty",
                "latestRun": None,
            }
        runs = await _list_fairness_benchmark_runs(
            policy_version=version,
            limit=20,
        )
        latest = runs[0] if runs else None
        if latest is None:
            return {
                "passed": False,
                "code": "registry_fairness_gate_no_benchmark",
                "message": "no fairness benchmark run found for policy version",
                "latestRun": None,
            }

        passed = (
            latest.threshold_decision == "accepted"
            and not bool(latest.needs_remediation)
            and latest.status in FAIRNESS_RELEASE_GATE_ACCEPTED_STATUSES
        )
        if passed:
            code = "registry_fairness_gate_passed"
            message = "fairness gate passed"
        elif latest.threshold_decision != "accepted":
            code = "registry_fairness_gate_threshold_not_accepted"
            message = "latest benchmark threshold_decision is not accepted"
        elif bool(latest.needs_remediation):
            code = "registry_fairness_gate_remediation_required"
            message = "latest benchmark requires remediation"
        else:
            code = "registry_fairness_gate_status_not_ready"
            message = "latest benchmark status is not release-ready"

        return {
            "passed": bool(passed),
            "code": code,
            "message": message,
            "latestRun": {
                "runId": latest.run_id,
                "policyVersion": latest.policy_version,
                "environmentMode": latest.environment_mode,
                "status": latest.status,
                "thresholdDecision": latest.threshold_decision,
                "needsRemediation": bool(latest.needs_remediation),
                "needsRealEnvReconfirm": bool(latest.needs_real_env_reconfirm),
                "reportedAt": (
                    latest.reported_at.isoformat()
                    if latest.reported_at is not None
                    else None
                ),
            },
        }

    async def _evaluate_policy_registry_dependency_health(
        *,
        policy_version: str,
        profile_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            return await runtime.registry_product_runtime.evaluate_policy_dependency_health(
                policy_version=policy_version,
                profile_payload=profile_payload,
            )
        except ValueError as err:
            code = str(err)
            if code in {"invalid_policy_profile", "invalid_registry_version"}:
                raise HTTPException(status_code=422, detail=code) from err
            raise HTTPException(
                status_code=422,
                detail="registry_dependency_health_invalid",
            ) from err

    async def _emit_registry_fairness_gate_alert(
        *,
        registry_type: str,
        version: str,
        gate_result: dict[str, Any],
        override_applied: bool,
        actor: str | None,
        reason: str | None,
    ) -> dict[str, Any]:
        alert_type = (
            "registry_fairness_gate_override"
            if override_applied
            else "registry_fairness_gate_blocked"
        )
        severity = "warning" if override_applied else "critical"
        title = (
            "AI Judge Registry Fairness Gate Override"
            if override_applied
            else "AI Judge Registry Fairness Gate Blocked"
        )
        message = (
            f"registry fairness gate {'overridden' if override_applied else 'blocked'}: "
            f"registry_type={registry_type}; version={version}; code={gate_result.get('code')}"
        )
        alert = runtime.trace_store.upsert_audit_alert(
            job_id=0,
            scope_id=1,
            trace_id=f"registry-fairness:{registry_type}:{version}",
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            details={
                "registryType": registry_type,
                "version": version,
                "overrideApplied": bool(override_applied),
                "actor": (str(actor or "").strip() or None),
                "reason": (str(reason or "").strip() or None),
                "gate": dict(gate_result),
            },
        )
        fact_alert = await _sync_audit_alert_to_facts(alert=alert)
        return _serialize_alert_item(fact_alert)

    async def _emit_registry_dependency_health_alert(
        *,
        registry_type: str,
        version: str,
        dependency_health: dict[str, Any],
        action: str,
    ) -> dict[str, Any]:
        message = (
            f"registry dependency health blocked: registry_type={registry_type}; "
            f"version={version}; code={dependency_health.get('code')}; action={action}"
        )
        alert = runtime.trace_store.upsert_audit_alert(
            job_id=0,
            scope_id=1,
            trace_id=f"registry-dependency:{registry_type}:{version}",
            alert_type=REGISTRY_DEPENDENCY_ALERT_TYPE_BLOCKED,
            severity="critical",
            title="AI Judge Registry Dependency Health Blocked",
            message=message,
            details={
                "registryType": registry_type,
                "version": version,
                "action": action,
                "dependency": dict(dependency_health),
            },
        )
        fact_alert = await _sync_audit_alert_to_facts(alert=alert)
        return _serialize_alert_item(fact_alert)

    async def _resolve_registry_dependency_health_alerts(
        *,
        registry_type: str,
        version: str,
        actor: str | None,
        reason: str | None,
        action: str,
    ) -> list[dict[str, Any]]:
        rows = runtime.trace_store.list_audit_alerts(
            job_id=0,
            status=None,
            limit=500,
        )
        resolved_items: list[dict[str, Any]] = []
        for row in rows:
            if str(getattr(row, "alert_type", "") or "").strip() != REGISTRY_DEPENDENCY_ALERT_TYPE_BLOCKED:
                continue
            details = (
                dict(getattr(row, "details"))
                if isinstance(getattr(row, "details", None), dict)
                else {}
            )
            if str(details.get("registryType") or "").strip().lower() != registry_type:
                continue
            if str(details.get("version") or "").strip() != version:
                continue
            if str(getattr(row, "status", "") or "").strip().lower() == "resolved":
                continue
            transitioned = runtime.trace_store.transition_audit_alert(
                job_id=0,
                alert_id=str(getattr(row, "alert_id", "") or "").strip(),
                to_status="resolved",
                actor=actor,
                reason=(
                    str(reason or "").strip()
                    or f"dependency_health_passed_on_{action}"
                ),
            )
            if transitioned is None:
                continue
            await _sync_audit_alert_to_facts(alert=transitioned)
            transitioned_fact = await runtime.workflow_runtime.facts.transition_audit_alert(
                alert_id=transitioned.alert_id,
                to_status=transitioned.status,
                now=getattr(transitioned, "updated_at", None),
            )
            resolved_items.append(
                _serialize_alert_item(transitioned_fact or transitioned)
            )
        return resolved_items

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

    async def _workflow_append_event(
        *,
        job_id: int,
        event_type: str,
        event_payload: dict[str, Any],
        not_found_detail: str = "workflow_job_not_found",
    ) -> None:
        await _ensure_workflow_schema_ready()
        try:
            await runtime.workflow_runtime.orchestrator.append_event(
                job_id=job_id,
                event_type=event_type,
                event_payload=event_payload,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=not_found_detail) from exc

    async def _resolve_open_alerts_for_review(
        *,
        job_id: int,
        actor: str,
        reason: str,
    ) -> list[str]:
        resolved_alert_ids: list[str] = []
        raised_alerts = runtime.trace_store.list_audit_alerts(
            job_id=job_id,
            status="raised",
            limit=200,
        )
        for item in raised_alerts:
            row = runtime.trace_store.transition_audit_alert(
                job_id=job_id,
                alert_id=item.alert_id,
                to_status="resolved",
                actor=actor,
                reason=reason,
            )
            if row is None:
                continue
            await _sync_audit_alert_to_facts(alert=row)
            resolved_alert_ids.append(row.alert_id)
        return resolved_alert_ids

    async def _build_shared_room_context(
        *,
        session_id: int,
        case_id: int | None,
    ) -> dict[str, Any]:
        normalized_session_id = max(0, int(session_id))
        requested_case_id = max(0, int(case_id)) if case_id is not None else None

        phase_receipts = await _list_dispatch_receipts(
            dispatch_type="phase",
            session_id=normalized_session_id,
            limit=200,
        )
        final_receipts = await _list_dispatch_receipts(
            dispatch_type="final",
            session_id=normalized_session_id,
            limit=200,
        )
        if requested_case_id is not None:
            phase_receipts = [
                row
                for row in phase_receipts
                if int(getattr(row, "job_id", 0)) == requested_case_id
            ]
            final_receipts = [
                row
                for row in final_receipts
                if int(getattr(row, "job_id", 0)) == requested_case_id
            ]

        latest_phase = phase_receipts[0] if phase_receipts else None
        latest_final = final_receipts[0] if final_receipts else None
        latest_receipt = latest_final or latest_phase

        workflow_jobs = await _workflow_list_jobs(
            status=None,
            dispatch_type=None,
            limit=300,
        )
        session_jobs = [
            row
            for row in workflow_jobs
            if int(row.session_id or 0) == normalized_session_id
        ]
        if requested_case_id is not None:
            session_jobs = [row for row in session_jobs if row.job_id == requested_case_id]
        latest_workflow_job = session_jobs[0] if session_jobs else None

        selected_case_id = (
            int(getattr(latest_receipt, "job_id", 0))
            if latest_receipt is not None
            else requested_case_id
        )
        if selected_case_id is not None and selected_case_id <= 0:
            selected_case_id = None
        selected_scope_id = (
            int(getattr(latest_receipt, "scope_id", 0))
            if latest_receipt is not None
            else int(getattr(latest_workflow_job, "scope_id", 0) or 0)
        )
        if selected_scope_id <= 0:
            selected_scope_id = 1

        report_payload: dict[str, Any] = {}
        latest_response = (
            latest_receipt.response
            if latest_receipt is not None and isinstance(latest_receipt.response, dict)
            else {}
        )
        if isinstance(latest_response.get("reportPayload"), dict):
            report_payload = latest_response["reportPayload"]

        verdict_contract = _build_verdict_contract(report_payload)
        winner_raw = latest_response.get("winner") or verdict_contract.get("winner")
        winner = str(winner_raw or "").strip().lower() or None
        debate_summary = (
            report_payload.get("debateSummary")
            if isinstance(report_payload.get("debateSummary"), str)
            else None
        )
        side_analysis = (
            report_payload.get("sideAnalysis")
            if isinstance(report_payload.get("sideAnalysis"), dict)
            else {}
        )
        verdict_reason = (
            report_payload.get("verdictReason")
            if isinstance(report_payload.get("verdictReason"), str)
            else None
        )
        updated_at = (
            latest_receipt.updated_at.isoformat()
            if latest_receipt is not None and getattr(latest_receipt, "updated_at", None) is not None
            else None
        )
        latest_dispatch_type = (
            "final" if latest_final is not None else ("phase" if latest_phase is not None else None)
        )

        return {
            "source": "shared_room_context_v1",
            "sessionId": normalized_session_id,
            "scopeId": selected_scope_id,
            "caseId": selected_case_id,
            "latestDispatchType": latest_dispatch_type,
            "workflowStatus": latest_workflow_job.status if latest_workflow_job is not None else None,
            "winnerHint": winner,
            "reviewRequired": bool(verdict_contract.get("reviewRequired")),
            "needsDrawVote": bool(verdict_contract.get("needsDrawVote")),
            "phaseReceiptCount": len(phase_receipts),
            "finalReceiptCount": len(final_receipts),
            "debateSummary": debate_summary,
            "sideAnalysis": side_analysis,
            "verdictReason": verdict_reason,
            "updatedAt": updated_at,
        }

    def _build_assistant_agent_response(
        *,
        agent_kind: str,
        session_id: int,
        shared_context: dict[str, Any],
        execution_result: Any,
    ) -> dict[str, Any]:
        output = (
            dict(execution_result.output)
            if isinstance(execution_result.output, dict)
            else {}
        )
        return {
            "agentKind": agent_kind,
            "sessionId": session_id,
            "caseId": shared_context.get("caseId"),
            "status": execution_result.status,
            "accepted": bool(output.get("accepted")),
            "errorCode": execution_result.error_code,
            "errorMessage": execution_result.error_message,
            "sharedContext": shared_context,
            "output": output,
        }

    @app.get("/healthz")
    async def healthz() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/internal/judge/policies")
    async def list_judge_policies(
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        await _ensure_registry_runtime_ready()
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
        await _ensure_registry_runtime_ready()
        profile = runtime.policy_registry_runtime.get_profile(policy_version)
        if profile is None:
            raise HTTPException(status_code=404, detail="judge_policy_not_found")
        return {
            "item": _serialize_policy_profile(runtime, profile=profile),
        }

    @app.get("/internal/judge/registries/prompts")
    async def list_prompt_registries(
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        await _ensure_registry_runtime_ready()
        profiles = runtime.prompt_registry_runtime.list_profiles()
        return {
            "defaultVersion": runtime.prompt_registry_runtime.default_version,
            "count": len(profiles),
            "items": [
                _serialize_prompt_profile(runtime, profile=item)
                for item in profiles
            ],
        }

    @app.get("/internal/judge/registries/prompts/{prompt_version}")
    async def get_prompt_registry(
        prompt_version: str,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        await _ensure_registry_runtime_ready()
        profile = runtime.prompt_registry_runtime.get_profile(prompt_version)
        if profile is None:
            raise HTTPException(status_code=404, detail="prompt_registry_not_found")
        return {
            "item": _serialize_prompt_profile(runtime, profile=profile),
        }

    @app.get("/internal/judge/registries/tools")
    async def list_tool_registries(
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        await _ensure_registry_runtime_ready()
        profiles = runtime.tool_registry_runtime.list_profiles()
        return {
            "defaultVersion": runtime.tool_registry_runtime.default_version,
            "count": len(profiles),
            "items": [
                _serialize_tool_profile(runtime, profile=item)
                for item in profiles
            ],
        }

    @app.get("/internal/judge/registries/tools/{toolset_version}")
    async def get_tool_registry(
        toolset_version: str,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        await _ensure_registry_runtime_ready()
        profile = runtime.tool_registry_runtime.get_profile(toolset_version)
        if profile is None:
            raise HTTPException(status_code=404, detail="tool_registry_not_found")
        return {
            "item": _serialize_tool_profile(runtime, profile=profile),
        }

    @app.get("/internal/judge/registries/policy/dependencies/health")
    async def get_policy_registry_dependency_health(
        x_ai_internal_key: str | None = Header(default=None),
        policy_version: str | None = Query(default=None),
        include_all_versions: bool = Query(default=False),
        include_overview: bool = Query(default=True),
        include_trend: bool = Query(default=True),
        trend_status: str | None = Query(default=None),
        trend_policy_version: str | None = Query(default=None),
        trend_offset: int = Query(default=0, ge=0, le=5000),
        trend_limit: int = Query(default=50, ge=1, le=500),
        overview_window_minutes: int = Query(default=1440, ge=10, le=43200),
        limit: int = Query(default=20, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        await _ensure_registry_runtime_ready()
        selected_policy_version = (
            str(policy_version or "").strip()
            or runtime.policy_registry_runtime.default_version
        )
        selected_item = await _evaluate_policy_registry_dependency_health(
            policy_version=selected_policy_version,
        )
        if selected_item.get("code") == "policy_registry_not_found":
            raise HTTPException(status_code=404, detail="policy_registry_not_found")
        items: list[dict[str, Any]] = [selected_item]
        if include_all_versions:
            policy_versions: list[str] = []
            seen_versions: set[str] = set()
            for row in runtime.policy_registry_runtime.list_profiles():
                version_token = str(getattr(row, "version", "") or "").strip()
                if not version_token or version_token in seen_versions:
                    continue
                seen_versions.add(version_token)
                policy_versions.append(version_token)
            if selected_policy_version not in seen_versions:
                policy_versions.insert(0, selected_policy_version)
            items = []
            for version_token in policy_versions[: max(1, min(int(limit), 200))]:
                dependency_item = await _evaluate_policy_registry_dependency_health(
                    policy_version=version_token,
                )
                if dependency_item.get("code") == "policy_registry_not_found":
                    continue
                items.append(dependency_item)
        normalized_trend_status = _normalize_registry_dependency_trend_status(
            trend_status
        )
        if (
            normalized_trend_status is not None
            and normalized_trend_status not in REGISTRY_DEPENDENCY_TREND_STATUS_VALUES
        ):
            raise HTTPException(status_code=422, detail="invalid_trend_status")
        alerts: list[Any] = []
        if include_overview or include_trend:
            alerts = await _list_audit_alerts(job_id=0, status=None, limit=5000)
        dependency_overview = None
        if include_overview:
            dependency_overview = _build_registry_dependency_overview(
                items=items,
                alerts=alerts,
                registry_type=REGISTRY_TYPE_POLICY,
                window_minutes=overview_window_minutes,
            )
        dependency_trend = None
        if include_trend:
            dependency_trend = _build_registry_dependency_trend(
                alerts=alerts,
                registry_type=REGISTRY_TYPE_POLICY,
                window_minutes=overview_window_minutes,
                status_filter=normalized_trend_status,
                policy_version_filter=trend_policy_version,
                offset=trend_offset,
                limit=trend_limit,
            )
        return {
            "activeVersions": {
                "policyVersion": runtime.policy_registry_runtime.default_version,
                "promptRegistryVersion": runtime.prompt_registry_runtime.default_version,
                "toolRegistryVersion": runtime.tool_registry_runtime.default_version,
            },
            "selectedPolicyVersion": selected_policy_version,
            "item": selected_item,
            "count": len(items),
            "items": items,
            "includeAllVersions": bool(include_all_versions),
            "includeOverview": bool(include_overview),
            "includeTrend": bool(include_trend),
            "trendStatus": normalized_trend_status,
            "trendPolicyVersion": (
                str(trend_policy_version or "").strip() or None
            ),
            "trendOffset": int(trend_offset),
            "trendLimit": int(trend_limit),
            "overviewWindowMinutes": int(overview_window_minutes),
            "dependencyOverview": dependency_overview,
            "dependencyTrend": dependency_trend,
            "limit": int(limit),
        }

    @app.post("/internal/judge/registries/{registry_type}/publish")
    async def publish_registry_release(
        registry_type: str,
        request: Request,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        try:
            payload = await request.json()
        except Exception as err:
            raise HTTPException(status_code=422, detail=f"invalid_json: {err}") from err
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail="invalid_payload")
        version = str(payload.get("version") or "").strip()
        profile_payload = payload.get("profile")
        if not isinstance(profile_payload, dict):
            raise HTTPException(status_code=422, detail="invalid_registry_profile")
        activate = bool(payload.get("activate"))
        override_fairness_gate = bool(
            _extract_optional_bool(
                payload,
                "override_fairness_gate",
                "overrideFairnessGate",
            )
        )
        actor = str(payload.get("actor") or "").strip() or None
        reason = str(payload.get("reason") or "").strip() or None

        await _ensure_registry_runtime_ready()
        registry_type_token = str(registry_type or "").strip().lower()
        fairness_gate: dict[str, Any] | None = None
        fairness_alert: dict[str, Any] | None = None
        dependency_alert: dict[str, Any] | None = None
        dependency_alert_resolved: list[dict[str, Any]] = []
        dependency_health: dict[str, Any] | None = None
        if registry_type_token == REGISTRY_TYPE_POLICY:
            dependency_health = await _evaluate_policy_registry_dependency_health(
                policy_version=version,
                profile_payload=profile_payload,
            )
            if not bool(dependency_health.get("ok")):
                dependency_alert = await _emit_registry_dependency_health_alert(
                    registry_type=registry_type_token,
                    version=version,
                    dependency_health=dependency_health,
                    action="publish",
                )
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "registry_policy_dependency_invalid",
                        "dependency": dependency_health,
                        "alert": dependency_alert,
                    },
                )
            dependency_alert_resolved = await _resolve_registry_dependency_health_alerts(
                registry_type=registry_type_token,
                version=version,
                actor=actor,
                reason=reason,
                action="publish",
            )
        if registry_type_token == REGISTRY_TYPE_POLICY and activate:
            fairness_gate = await _evaluate_policy_release_fairness_gate(
                policy_version=version,
            )
            if not bool(fairness_gate.get("passed")):
                if override_fairness_gate:
                    if reason is None:
                        raise HTTPException(
                            status_code=422,
                            detail="registry_fairness_gate_override_reason_required",
                        )
                    fairness_alert = await _emit_registry_fairness_gate_alert(
                        registry_type=registry_type_token,
                        version=version,
                        gate_result=fairness_gate,
                        override_applied=True,
                        actor=actor,
                        reason=reason,
                    )
                else:
                    fairness_alert = await _emit_registry_fairness_gate_alert(
                        registry_type=registry_type_token,
                        version=version,
                        gate_result=fairness_gate,
                        override_applied=False,
                        actor=actor,
                        reason=reason,
                    )
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "code": "registry_fairness_gate_blocked",
                            "gate": fairness_gate,
                            "alert": fairness_alert,
                        },
                    )

        extra_details_payload: dict[str, Any] = {}
        if dependency_health is not None:
            extra_details_payload["dependencyHealth"] = dict(dependency_health)
        if fairness_gate is not None:
            extra_details_payload["fairnessGate"] = {
                **(fairness_gate or {}),
                "overrideApplied": bool(
                    override_fairness_gate
                    and fairness_gate is not None
                    and not bool(fairness_gate.get("passed"))
                ),
            }
        extra_details = extra_details_payload or None
        try:
            item = await runtime.registry_product_runtime.publish_release(
                registry_type=registry_type,
                version=version,
                profile_payload=profile_payload,
                actor=actor,
                reason=reason,
                activate=activate,
                extra_details=extra_details,
            )
        except LookupError as err:
            raise HTTPException(status_code=404, detail=str(err)) from err
        except ValueError as err:
            code = str(err)
            if code == "registry_version_already_exists":
                raise HTTPException(status_code=409, detail=code) from err
            if code in {
                "invalid_registry_type",
                "invalid_registry_version",
                "invalid_policy_profile",
                "invalid_prompt_profile",
                "invalid_tool_profile",
            }:
                raise HTTPException(status_code=422, detail=code) from err
            raise HTTPException(status_code=422, detail="registry_publish_invalid") from err
        return {
            "ok": True,
            "item": item,
            "dependencyHealth": dependency_health,
            "dependencyAlert": dependency_alert,
            "resolvedDependencyAlerts": dependency_alert_resolved,
            "fairnessGate": fairness_gate,
            "alert": fairness_alert,
        }

    @app.post("/internal/judge/registries/{registry_type}/{version}/activate")
    async def activate_registry_release(
        registry_type: str,
        version: str,
        x_ai_internal_key: str | None = Header(default=None),
        actor: str | None = Query(default=None),
        reason: str | None = Query(default=None),
        override_fairness_gate: bool = Query(default=False),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        await _ensure_registry_runtime_ready()
        registry_type_token = str(registry_type or "").strip().lower()
        fairness_gate: dict[str, Any] | None = None
        fairness_alert: dict[str, Any] | None = None
        dependency_alert: dict[str, Any] | None = None
        dependency_alert_resolved: list[dict[str, Any]] = []
        dependency_health: dict[str, Any] | None = None
        if registry_type_token == REGISTRY_TYPE_POLICY:
            dependency_health = await _evaluate_policy_registry_dependency_health(
                policy_version=version,
            )
            if not bool(dependency_health.get("ok")):
                dependency_alert = await _emit_registry_dependency_health_alert(
                    registry_type=registry_type_token,
                    version=version,
                    dependency_health=dependency_health,
                    action="activate",
                )
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "registry_policy_dependency_blocked",
                        "dependency": dependency_health,
                        "alert": dependency_alert,
                    },
                )
            dependency_alert_resolved = await _resolve_registry_dependency_health_alerts(
                registry_type=registry_type_token,
                version=version,
                actor=actor,
                reason=reason,
                action="activate",
            )
            fairness_gate = await _evaluate_policy_release_fairness_gate(
                policy_version=version,
            )
            if not bool(fairness_gate.get("passed")):
                if override_fairness_gate:
                    if reason is None:
                        raise HTTPException(
                            status_code=422,
                            detail="registry_fairness_gate_override_reason_required",
                        )
                    fairness_alert = await _emit_registry_fairness_gate_alert(
                        registry_type=registry_type_token,
                        version=version,
                        gate_result=fairness_gate,
                        override_applied=True,
                        actor=actor,
                        reason=reason,
                    )
                else:
                    fairness_alert = await _emit_registry_fairness_gate_alert(
                        registry_type=registry_type_token,
                        version=version,
                        gate_result=fairness_gate,
                        override_applied=False,
                        actor=actor,
                        reason=reason,
                    )
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "code": "registry_fairness_gate_blocked",
                            "gate": fairness_gate,
                            "alert": fairness_alert,
                        },
                    )
        extra_details_payload: dict[str, Any] = {}
        if dependency_health is not None:
            extra_details_payload["dependencyHealth"] = dict(dependency_health)
        if fairness_gate is not None:
            extra_details_payload["fairnessGate"] = {
                **(fairness_gate or {}),
                "overrideApplied": bool(
                    override_fairness_gate
                    and fairness_gate is not None
                    and not bool(fairness_gate.get("passed"))
                ),
            }
        extra_details = extra_details_payload or None
        try:
            item = await runtime.registry_product_runtime.activate_release(
                registry_type=registry_type,
                version=version,
                actor=actor,
                reason=reason,
                extra_details=extra_details,
            )
        except LookupError as err:
            raise HTTPException(status_code=404, detail="registry_version_not_found") from err
        except ValueError as err:
            code = str(err)
            if code in {"invalid_registry_type", "invalid_registry_version"}:
                raise HTTPException(status_code=422, detail=code) from err
            raise HTTPException(status_code=422, detail="registry_activate_invalid") from err
        return {
            "ok": True,
            "item": item,
            "dependencyHealth": dependency_health,
            "dependencyAlert": dependency_alert,
            "resolvedDependencyAlerts": dependency_alert_resolved,
            "fairnessGate": fairness_gate,
            "alert": fairness_alert,
        }

    @app.post("/internal/judge/registries/{registry_type}/rollback")
    async def rollback_registry_release(
        registry_type: str,
        x_ai_internal_key: str | None = Header(default=None),
        target_version: str | None = Query(default=None),
        actor: str | None = Query(default=None),
        reason: str | None = Query(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        await _ensure_registry_runtime_ready()
        try:
            item = await runtime.registry_product_runtime.rollback_release(
                registry_type=registry_type,
                target_version=target_version,
                actor=actor,
                reason=reason,
            )
        except LookupError as err:
            raise HTTPException(status_code=404, detail="registry_version_not_found") from err
        except ValueError as err:
            code = str(err)
            if code in {
                "invalid_registry_type",
                "invalid_registry_version",
                "registry_rollback_target_not_found",
            }:
                raise HTTPException(status_code=409 if code == "registry_rollback_target_not_found" else 422, detail=code) from err
            raise HTTPException(status_code=422, detail="registry_rollback_invalid") from err
        return {
            "ok": True,
            "item": item,
        }

    @app.get("/internal/judge/registries/{registry_type}/audits")
    async def list_registry_audits(
        registry_type: str,
        x_ai_internal_key: str | None = Header(default=None),
        action: str | None = Query(default=None),
        version: str | None = Query(default=None),
        actor: str | None = Query(default=None),
        gate_code: str | None = Query(default=None),
        override_applied: bool | None = Query(default=None),
        include_gate_view: bool = Query(default=True),
        link_limit: int = Query(default=5, ge=1, le=20),
        offset: int = Query(default=0, ge=0, le=5000),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        await _ensure_registry_runtime_ready()
        normalized_action = _normalize_registry_audit_action(action)
        if (
            normalized_action is not None
            and normalized_action not in REGISTRY_AUDIT_ACTION_VALUES
        ):
            raise HTTPException(status_code=422, detail="invalid_registry_audit_action")

        try:
            fetch_limit = max(1, min(int(limit) + int(offset), 200))
            items = await runtime.registry_product_runtime.list_audits(
                registry_type=registry_type,
                limit=fetch_limit,
            )
        except ValueError as err:
            code = str(err)
            if code == "invalid_registry_type":
                raise HTTPException(status_code=422, detail=code) from err
            raise HTTPException(status_code=422, detail="registry_audit_query_invalid") from err
        alerts: list[Any] = []
        outbox_events: list[Any] = []
        if include_gate_view:
            alerts = await _list_audit_alerts(job_id=0, status=None, limit=5000)
            outbox_events = runtime.trace_store.list_alert_outbox(limit=500)
        payload = _build_registry_audit_ops_view(
            registry_type=registry_type,
            audit_items=items,
            alerts=alerts,
            outbox_events=outbox_events,
            action=normalized_action,
            version=version,
            actor=actor,
            gate_code=gate_code,
            override_applied=override_applied,
            include_gate_view=include_gate_view,
            link_limit=link_limit,
            offset=offset,
            limit=limit,
        )
        return payload

    @app.get("/internal/judge/registries/{registry_type}/releases")
    async def list_registry_releases(
        registry_type: str,
        x_ai_internal_key: str | None = Header(default=None),
        limit: int = Query(default=50, ge=1, le=200),
        include_payload: bool = Query(default=True),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        await _ensure_registry_runtime_ready()
        try:
            items = await runtime.registry_product_runtime.list_releases(
                registry_type=registry_type,
                limit=limit,
                include_payload=include_payload,
            )
        except ValueError as err:
            code = str(err)
            if code == "invalid_registry_type":
                raise HTTPException(status_code=422, detail=code) from err
            raise HTTPException(status_code=422, detail="registry_release_query_invalid") from err
        return {
            "registryType": str(registry_type or "").strip().lower(),
            "count": len(items),
            "items": items,
            "limit": limit,
            "includePayload": bool(include_payload),
        }

    @app.get("/internal/judge/registries/{registry_type}/releases/{version}")
    async def get_registry_release(
        registry_type: str,
        version: str,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        await _ensure_registry_runtime_ready()
        try:
            item = await runtime.registry_product_runtime.get_release(
                registry_type=registry_type,
                version=version,
            )
        except ValueError as err:
            code = str(err)
            if code in {"invalid_registry_type", "invalid_registry_version"}:
                raise HTTPException(status_code=422, detail=code) from err
            raise HTTPException(status_code=422, detail="registry_release_query_invalid") from err
        if item is None:
            raise HTTPException(status_code=404, detail="registry_version_not_found")
        return {
            "item": item,
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
        await _ensure_registry_runtime_ready()
        policy_profile = _resolve_policy_profile_or_raise(
            runtime=runtime,
            judge_policy_version=parsed.judge_policy_version,
            rubric_version=parsed.rubric_version,
            topic_domain=parsed.topic_domain,
        )
        prompt_profile = _resolve_prompt_profile_or_raise(
            runtime=runtime,
            prompt_registry_version=policy_profile.prompt_registry_version,
        )
        tool_profile = _resolve_tool_profile_or_raise(
            runtime=runtime,
            tool_registry_version=policy_profile.tool_registry_version,
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
                "promptVersion": prompt_profile.version,
                "toolsetVersion": tool_profile.version,
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
            "registryVersions": {
                "policyVersion": policy_profile.version,
                "promptVersion": prompt_profile.version,
                "toolsetVersion": tool_profile.version,
            },
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
        await _ensure_registry_runtime_ready()
        policy_profile = _resolve_policy_profile_or_raise(
            runtime=runtime,
            judge_policy_version=parsed.judge_policy_version,
            rubric_version=parsed.rubric_version,
            topic_domain=parsed.topic_domain,
        )
        prompt_profile = _resolve_prompt_profile_or_raise(
            runtime=runtime,
            prompt_registry_version=policy_profile.prompt_registry_version,
        )
        tool_profile = _resolve_tool_profile_or_raise(
            runtime=runtime,
            tool_registry_version=policy_profile.tool_registry_version,
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
                "promptVersion": prompt_profile.version,
                "toolsetVersion": tool_profile.version,
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
            prompt_profile=prompt_profile,
            tool_profile=tool_profile,
        )
        _attach_report_attestation(
            report_payload=phase_report_payload,
            dispatch_type="phase",
        )
        await _upsert_claim_ledger_record(
            case_id=parsed.case_id,
            dispatch_type="phase",
            trace_id=parsed.trace_id,
            report_payload=phase_report_payload,
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
        await _ensure_registry_runtime_ready()
        policy_profile = _resolve_policy_profile_or_raise(
            runtime=runtime,
            judge_policy_version=parsed.judge_policy_version,
            rubric_version=parsed.rubric_version,
            topic_domain=parsed.topic_domain,
        )
        prompt_profile = _resolve_prompt_profile_or_raise(
            runtime=runtime,
            prompt_registry_version=policy_profile.prompt_registry_version,
        )
        tool_profile = _resolve_tool_profile_or_raise(
            runtime=runtime,
            tool_registry_version=policy_profile.tool_registry_version,
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
                "promptVersion": prompt_profile.version,
                "toolsetVersion": tool_profile.version,
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
            fairness_thresholds=policy_profile.fairness_thresholds,
            panel_runtime_profiles=_resolve_panel_runtime_profiles(profile=policy_profile),
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
            prompt_profile=prompt_profile,
            tool_profile=tool_profile,
        )
        _attach_report_attestation(
            report_payload=final_report_payload,
            dispatch_type="final",
        )
        await _upsert_claim_ledger_record(
            case_id=parsed.case_id,
            dispatch_type="final",
            trace_id=parsed.trace_id,
            report_payload=final_report_payload,
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
        claim_ledger_record = await _get_claim_ledger_record(
            case_id=case_id,
            dispatch_type=None,
        )
        if (
            workflow_job is None
            and final_receipt is None
            and phase_receipt is None
            and trace is None
            and not replay_records
            and not alerts
            and claim_ledger_record is None
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
            claim_ledger_record=claim_ledger_record,
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

    @app.get("/internal/judge/cases/{case_id}/claim-ledger")
    async def get_judge_case_claim_ledger(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
        limit: int = Query(default=20, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        normalized_dispatch_type = str(dispatch_type or "").strip().lower() or "auto"
        if normalized_dispatch_type not in {"auto", "phase", "final"}:
            raise HTTPException(status_code=422, detail="invalid_dispatch_type")

        if normalized_dispatch_type == "auto":
            records = await _list_claim_ledger_records(case_id=case_id, limit=limit)
            if not records:
                raise HTTPException(status_code=404, detail="claim_ledger_not_found")
            primary = records[0]
        else:
            primary = await _get_claim_ledger_record(
                case_id=case_id,
                dispatch_type=normalized_dispatch_type,
            )
            if primary is None:
                raise HTTPException(status_code=404, detail="claim_ledger_not_found")
            records = [primary]

        return {
            "caseId": case_id,
            "dispatchType": primary.dispatch_type,
            "traceId": primary.trace_id,
            "count": len(records),
            "item": _serialize_claim_ledger_record(primary, include_payload=True),
            "items": [
                _serialize_claim_ledger_record(row, include_payload=False)
                for row in records
            ],
        }

    @app.post("/internal/judge/apps/npc-coach/sessions/{session_id}/advice")
    async def request_npc_coach_advice(
        session_id: int,
        payload: NpcCoachAdviceRequest,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        normalized_session_id = max(0, int(session_id))
        if normalized_session_id <= 0:
            raise HTTPException(status_code=422, detail="invalid_session_id")

        shared_context = await _build_shared_room_context(
            session_id=normalized_session_id,
            case_id=payload.case_id,
        )
        scope_id = max(1, int(shared_context.get("scopeId") or 1))
        execution_result = await runtime.agent_runtime.execute(
            AgentExecutionRequest(
                kind=AGENT_KIND_NPC_COACH,
                input_payload={
                    "sessionId": normalized_session_id,
                    "caseId": shared_context.get("caseId"),
                    "query": payload.query,
                    "side": payload.side,
                    "sharedContext": shared_context,
                },
                trace_id=payload.trace_id,
                session_id=normalized_session_id,
                scope_id=scope_id,
                metadata={
                    "app": "npc_coach",
                    "entrypoint": "npc_coach_advice",
                },
            )
        )
        return _build_assistant_agent_response(
            agent_kind=AGENT_KIND_NPC_COACH,
            session_id=normalized_session_id,
            shared_context=shared_context,
            execution_result=execution_result,
        )

    @app.post("/internal/judge/apps/room-qa/sessions/{session_id}/answer")
    async def request_room_qa_answer(
        session_id: int,
        payload: RoomQaAnswerRequest,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        normalized_session_id = max(0, int(session_id))
        if normalized_session_id <= 0:
            raise HTTPException(status_code=422, detail="invalid_session_id")

        shared_context = await _build_shared_room_context(
            session_id=normalized_session_id,
            case_id=payload.case_id,
        )
        scope_id = max(1, int(shared_context.get("scopeId") or 1))
        execution_result = await runtime.agent_runtime.execute(
            AgentExecutionRequest(
                kind=AGENT_KIND_ROOM_QA,
                input_payload={
                    "sessionId": normalized_session_id,
                    "caseId": shared_context.get("caseId"),
                    "question": payload.question,
                    "sharedContext": shared_context,
                },
                trace_id=payload.trace_id,
                session_id=normalized_session_id,
                scope_id=scope_id,
                metadata={
                    "app": "room_qa",
                    "entrypoint": "room_qa_answer",
                },
            )
        )
        return _build_assistant_agent_response(
            agent_kind=AGENT_KIND_ROOM_QA,
            session_id=normalized_session_id,
            shared_context=shared_context,
            execution_result=execution_result,
        )

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
        await _ensure_registry_runtime_ready()

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
            prompt_profile = _resolve_prompt_profile_or_raise(
                runtime=runtime,
                prompt_registry_version=policy_profile.prompt_registry_version,
            )
            tool_profile = _resolve_tool_profile_or_raise(
                runtime=runtime,
                tool_registry_version=policy_profile.tool_registry_version,
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
                fairness_thresholds=policy_profile.fairness_thresholds,
                panel_runtime_profiles=_resolve_panel_runtime_profiles(profile=policy_profile),
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
                prompt_profile=prompt_profile,
                tool_profile=tool_profile,
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
            prompt_profile = _resolve_prompt_profile_or_raise(
                runtime=runtime,
                prompt_registry_version=policy_profile.prompt_registry_version,
            )
            tool_profile = _resolve_tool_profile_or_raise(
                runtime=runtime,
                tool_registry_version=policy_profile.tool_registry_version,
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
                prompt_profile=prompt_profile,
                tool_profile=tool_profile,
            )
            _attach_report_attestation(
                report_payload=report_payload,
                dispatch_type="phase",
            )

        await _upsert_claim_ledger_record(
            case_id=case_id,
            dispatch_type=chosen_dispatch_type,
            trace_id=trace_id,
            report_payload=report_payload,
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

    async def _resolve_report_context_for_case(
        *,
        case_id: int,
        dispatch_type: str,
        not_found_detail: str,
        missing_report_detail: str,
    ) -> dict[str, Any]:
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
                raise HTTPException(status_code=404, detail=not_found_detail)
            chosen_dispatch_type = "final" if final_receipt is not None else "phase"
        else:
            chosen_receipt = await _get_dispatch_receipt(
                dispatch_type=dispatch_type_normalized,
                job_id=case_id,
            )
            if chosen_receipt is None:
                raise HTTPException(status_code=404, detail=not_found_detail)

        response_payload = (
            chosen_receipt.response if isinstance(chosen_receipt.response, dict) else {}
        )
        request_snapshot = (
            chosen_receipt.request if isinstance(chosen_receipt.request, dict) else {}
        )
        report_payload = (
            response_payload.get("reportPayload")
            if isinstance(response_payload.get("reportPayload"), dict)
            else None
        )
        if report_payload is None:
            raise HTTPException(status_code=409, detail=missing_report_detail)
        judge_trace = (
            report_payload.get("judgeTrace")
            if isinstance(report_payload.get("judgeTrace"), dict)
            else {}
        )
        trace_id = str(
            chosen_receipt.trace_id
            or response_payload.get("traceId")
            or request_snapshot.get("traceId")
            or judge_trace.get("traceId")
            or ""
        ).strip()
        return {
            "dispatchType": chosen_dispatch_type,
            "receipt": chosen_receipt,
            "traceId": trace_id,
            "requestSnapshot": request_snapshot,
            "responsePayload": response_payload,
            "reportPayload": report_payload,
        }

    async def _build_trust_phasea_bundle(
        *,
        case_id: int,
        dispatch_type: str,
    ) -> dict[str, Any]:
        context = await _resolve_report_context_for_case(
            case_id=case_id,
            dispatch_type=dispatch_type,
            not_found_detail="trust_receipt_not_found",
            missing_report_detail="trust_report_payload_missing",
        )
        workflow_job = await _workflow_get_job(job_id=case_id)
        workflow_events = list(await _workflow_list_events(job_id=case_id))
        alerts = await _list_audit_alerts(job_id=case_id, status=None, limit=200)
        verify_result = _verify_report_attestation(
            report_payload=context["reportPayload"],
            dispatch_type=context["dispatchType"],
        )
        commitment = build_case_commitment_registry_v3(
            case_id=case_id,
            dispatch_type=context["dispatchType"],
            trace_id=context["traceId"],
            request_snapshot=context["requestSnapshot"],
            workflow_snapshot=(
                _serialize_workflow_job(workflow_job)
                if workflow_job is not None
                else None
            ),
            report_payload=context["reportPayload"],
        )
        verdict_attestation = build_verdict_attestation_registry_v3(
            case_id=case_id,
            dispatch_type=context["dispatchType"],
            trace_id=context["traceId"],
            report_payload=context["reportPayload"],
            verify_result=verify_result,
        )
        challenge_review = build_challenge_review_registry_v3(
            case_id=case_id,
            trace_id=context["traceId"],
            workflow_status=workflow_job.status if workflow_job is not None else None,
            workflow_events=workflow_events,
            alerts=alerts,
            report_payload=context["reportPayload"],
        )
        kernel_version = build_judge_kernel_registry_v3(
            case_id=case_id,
            dispatch_type=context["dispatchType"],
            trace_id=context["traceId"],
            report_payload=context["reportPayload"],
            workflow_events=workflow_events,
            provider=runtime.settings.provider,
        )
        return {
            "context": context,
            "verifyResult": verify_result,
            "commitment": commitment,
            "verdictAttestation": verdict_attestation,
            "challengeReview": challenge_review,
            "kernelVersion": kernel_version,
        }

    @app.get("/internal/judge/cases/{case_id}/trust/commitment")
    async def get_judge_trust_case_commitment(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        bundle = await _build_trust_phasea_bundle(
            case_id=case_id,
            dispatch_type=dispatch_type,
        )
        context = bundle["context"]
        return {
            "caseId": case_id,
            "dispatchType": context["dispatchType"],
            "traceId": context["traceId"],
            "item": bundle["commitment"],
        }

    @app.get("/internal/judge/cases/{case_id}/trust/verdict-attestation")
    async def get_judge_trust_verdict_attestation(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        bundle = await _build_trust_phasea_bundle(
            case_id=case_id,
            dispatch_type=dispatch_type,
        )
        context = bundle["context"]
        return {
            "caseId": case_id,
            "dispatchType": context["dispatchType"],
            "traceId": context["traceId"],
            "item": bundle["verdictAttestation"],
        }

    @app.get("/internal/judge/cases/{case_id}/trust/challenges")
    async def get_judge_trust_challenge_review(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        bundle = await _build_trust_phasea_bundle(
            case_id=case_id,
            dispatch_type=dispatch_type,
        )
        context = bundle["context"]
        return {
            "caseId": case_id,
            "dispatchType": context["dispatchType"],
            "traceId": context["traceId"],
            "item": bundle["challengeReview"],
        }

    @app.post("/internal/judge/cases/{case_id}/trust/challenges/request")
    async def request_judge_trust_challenge(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
        reason_code: str = Query(default="manual_challenge"),
        reason: str | None = Query(default=None),
        requested_by: str | None = Query(default=None),
        auto_accept: bool = Query(default=True),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        normalized_reason_code = str(reason_code or "").strip().lower()
        if not normalized_reason_code:
            raise HTTPException(status_code=422, detail="invalid_challenge_reason_code")
        actor = str(requested_by or "").strip() or "ops"
        reason_text = str(reason or "").strip() or None
        context = await _resolve_report_context_for_case(
            case_id=case_id,
            dispatch_type=dispatch_type,
            not_found_detail="trust_receipt_not_found",
            missing_report_detail="trust_report_payload_missing",
        )
        current_job = await _workflow_get_job(job_id=case_id)
        if current_job is None:
            raise HTTPException(status_code=404, detail="review_job_not_found")
        if current_job.status in {"blocked_failed", "archived"}:
            raise HTTPException(status_code=409, detail="challenge_request_not_allowed")

        challenge_id = _new_challenge_id(case_id=case_id)
        base_payload = {
            "dispatchType": context["dispatchType"],
            "traceId": context["traceId"],
            "challengeId": challenge_id,
            "challengeReasonCode": normalized_reason_code,
            "challengeReason": reason_text,
            "challengeRequestedBy": actor,
            "challengeActor": actor,
        }
        await _workflow_append_event(
            job_id=case_id,
            event_type=TRUST_CHALLENGE_EVENT_TYPE,
            event_payload={
                **base_payload,
                "challengeState": TRUST_CHALLENGE_STATE_REQUESTED,
            },
            not_found_detail="review_job_not_found",
        )

        if current_job.status != "review_required":
            # challenge 受理后强制进入 review_required 队列，避免绕过复核主状态机。
            await _workflow_mark_review_required(
                job_id=case_id,
                event_payload={
                    **base_payload,
                    "challengeState": TRUST_CHALLENGE_STATE_UNDER_REVIEW,
                    "judgeCoreStage": TRUST_CHALLENGE_STATE_UNDER_REVIEW,
                },
            )

        if auto_accept:
            await _workflow_append_event(
                job_id=case_id,
                event_type=TRUST_CHALLENGE_EVENT_TYPE,
                event_payload={
                    **base_payload,
                    "challengeState": TRUST_CHALLENGE_STATE_ACCEPTED,
                    "challengeAcceptedBy": actor,
                },
                not_found_detail="review_job_not_found",
            )
            await _workflow_append_event(
                job_id=case_id,
                event_type=TRUST_CHALLENGE_EVENT_TYPE,
                event_payload={
                    **base_payload,
                    "challengeState": TRUST_CHALLENGE_STATE_UNDER_REVIEW,
                    "challengeActor": actor,
                },
                not_found_detail="review_job_not_found",
            )

        alert = runtime.trace_store.upsert_audit_alert(
            job_id=case_id,
            scope_id=current_job.scope_id,
            trace_id=context["traceId"],
            alert_type="trust_challenge_requested",
            severity="warning",
            title="AI Judge Trust Challenge Requested",
            message=f"challenge requested ({normalized_reason_code})",
            details={
                "dispatchType": context["dispatchType"],
                "challengeId": challenge_id,
                "reasonCode": normalized_reason_code,
                "reason": reason_text,
                "requestedBy": actor,
            },
        )
        await _sync_audit_alert_to_facts(alert=alert)

        bundle = await _build_trust_phasea_bundle(
            case_id=case_id,
            dispatch_type=context["dispatchType"],
        )
        workflow_job = await _workflow_get_job(job_id=case_id)
        return {
            "ok": True,
            "caseId": case_id,
            "dispatchType": context["dispatchType"],
            "traceId": context["traceId"],
            "challengeId": challenge_id,
            "alertId": alert.alert_id,
            "job": (
                _serialize_workflow_job(workflow_job)
                if workflow_job is not None
                else None
            ),
            "item": bundle["challengeReview"],
        }

    @app.post("/internal/judge/cases/{case_id}/trust/challenges/{challenge_id}/decision")
    async def decide_judge_trust_challenge(
        case_id: int,
        challenge_id: str,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
        decision: str = Query(default="uphold"),
        actor: str | None = Query(default=None),
        reason: str | None = Query(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        normalized_decision = str(decision or "").strip().lower()
        if normalized_decision not in {"accept", "uphold", "overturn", "draw", "close"}:
            raise HTTPException(status_code=422, detail="invalid_challenge_decision")
        normalized_challenge_id = str(challenge_id or "").strip()
        if not normalized_challenge_id:
            raise HTTPException(status_code=422, detail="invalid_challenge_id")

        context = await _resolve_report_context_for_case(
            case_id=case_id,
            dispatch_type=dispatch_type,
            not_found_detail="trust_receipt_not_found",
            missing_report_detail="trust_report_payload_missing",
        )
        current_job = await _workflow_get_job(job_id=case_id)
        if current_job is None:
            raise HTTPException(status_code=404, detail="review_job_not_found")
        actor_text = str(actor or "").strip() or "ops"
        reason_text = str(reason or "").strip() or None

        before_bundle = await _build_trust_phasea_bundle(
            case_id=case_id,
            dispatch_type=context["dispatchType"],
        )
        challenge_item = next(
            (
                item
                for item in (
                    before_bundle["challengeReview"].get("challenges")
                    if isinstance(before_bundle["challengeReview"].get("challenges"), list)
                    else []
                )
                if str(item.get("challengeId") or "") == normalized_challenge_id
            ),
            None,
        )
        if challenge_item is None:
            raise HTTPException(status_code=404, detail="trust_challenge_not_found")
        if str(challenge_item.get("currentState") or "") == TRUST_CHALLENGE_STATE_CLOSED:
            raise HTTPException(status_code=409, detail="trust_challenge_already_closed")

        base_payload = {
            "dispatchType": context["dispatchType"],
            "traceId": context["traceId"],
            "challengeId": normalized_challenge_id,
            "challengeActor": actor_text,
            "challengeDecision": normalized_decision,
            "challengeDecisionReason": reason_text,
        }
        resolved_alert_ids: list[str] = []
        updated_job: WorkflowJob | None = current_job

        if normalized_decision == "accept":
            await _workflow_append_event(
                job_id=case_id,
                event_type=TRUST_CHALLENGE_EVENT_TYPE,
                event_payload={
                    **base_payload,
                    "challengeState": TRUST_CHALLENGE_STATE_ACCEPTED,
                    "challengeAcceptedBy": actor_text,
                },
            )
            await _workflow_append_event(
                job_id=case_id,
                event_type=TRUST_CHALLENGE_EVENT_TYPE,
                event_payload={
                    **base_payload,
                    "challengeState": TRUST_CHALLENGE_STATE_UNDER_REVIEW,
                },
            )
            if current_job.status != "review_required":
                await _workflow_mark_review_required(
                    job_id=case_id,
                    event_payload={
                        **base_payload,
                        "challengeState": TRUST_CHALLENGE_STATE_UNDER_REVIEW,
                        "judgeCoreStage": TRUST_CHALLENGE_STATE_UNDER_REVIEW,
                    },
                )
                updated_job = await _workflow_get_job(job_id=case_id)
        elif normalized_decision == "uphold":
            await _workflow_append_event(
                job_id=case_id,
                event_type=TRUST_CHALLENGE_EVENT_TYPE,
                event_payload={
                    **base_payload,
                    "challengeState": TRUST_CHALLENGE_STATE_VERDICT_UPHELD,
                    "reviewDecision": "approve",
                    "reviewActor": actor_text,
                    "reviewReason": reason_text or "challenge_upheld",
                },
            )
            if current_job.status == "review_required":
                await _workflow_mark_completed(
                    job_id=case_id,
                    event_payload={
                        **base_payload,
                        "reviewDecision": "approve",
                        "reviewActor": actor_text,
                        "reviewReason": reason_text or "challenge_upheld",
                        "judgeCoreStage": "review_approved",
                    },
                )
                resolved_alert_ids = await _resolve_open_alerts_for_review(
                    job_id=case_id,
                    actor=actor_text,
                    reason=reason_text or "challenge_upheld",
                )
                updated_job = await _workflow_get_job(job_id=case_id)
        elif normalized_decision in {"overturn", "draw"}:
            overturned_state = (
                TRUST_CHALLENGE_STATE_VERDICT_OVERTURNED
                if normalized_decision == "overturn"
                else TRUST_CHALLENGE_STATE_DRAW_AFTER_REVIEW
            )
            await _workflow_append_event(
                job_id=case_id,
                event_type=TRUST_CHALLENGE_EVENT_TYPE,
                event_payload={
                    **base_payload,
                    "challengeState": overturned_state,
                },
            )
            draw_payload = {
                **base_payload,
                "challengeState": TRUST_CHALLENGE_STATE_DRAW_AFTER_REVIEW,
                "judgeCoreStage": TRUST_CHALLENGE_STATE_DRAW_AFTER_REVIEW,
            }
            try:
                await runtime.workflow_runtime.orchestrator.mark_draw_pending_vote(
                    job_id=case_id,
                    event_payload=draw_payload,
                )
                updated_job = await _workflow_get_job(job_id=case_id)
            except WorkflowTransitionError:
                pass
            await _workflow_append_event(
                job_id=case_id,
                event_type=TRUST_CHALLENGE_EVENT_TYPE,
                event_payload={
                    **base_payload,
                    "challengeState": TRUST_CHALLENGE_STATE_DRAW_AFTER_REVIEW,
                },
            )

        await _workflow_append_event(
            job_id=case_id,
            event_type=TRUST_CHALLENGE_EVENT_TYPE,
            event_payload={
                **base_payload,
                "challengeState": TRUST_CHALLENGE_STATE_CLOSED,
                "challengeClosedBy": actor_text,
                "challengeCloseReason": reason_text,
            },
        )

        after_bundle = await _build_trust_phasea_bundle(
            case_id=case_id,
            dispatch_type=context["dispatchType"],
        )
        if updated_job is None:
            updated_job = await _workflow_get_job(job_id=case_id)
        return {
            "ok": True,
            "caseId": case_id,
            "dispatchType": context["dispatchType"],
            "traceId": context["traceId"],
            "challengeId": normalized_challenge_id,
            "decision": normalized_decision,
            "resolvedAlertIds": resolved_alert_ids,
            "job": _serialize_workflow_job(updated_job) if updated_job is not None else None,
            "item": after_bundle["challengeReview"],
        }

    @app.get("/internal/judge/cases/{case_id}/trust/kernel-version")
    async def get_judge_trust_kernel_version(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        bundle = await _build_trust_phasea_bundle(
            case_id=case_id,
            dispatch_type=dispatch_type,
        )
        context = bundle["context"]
        return {
            "caseId": case_id,
            "dispatchType": context["dispatchType"],
            "traceId": context["traceId"],
            "item": bundle["kernelVersion"],
        }

    @app.get("/internal/judge/cases/{case_id}/trust/audit-anchor")
    async def get_judge_trust_audit_anchor(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
        include_payload: bool = Query(default=False),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        bundle = await _build_trust_phasea_bundle(
            case_id=case_id,
            dispatch_type=dispatch_type,
        )
        context = bundle["context"]
        anchor = build_audit_anchor_export_v3(
            case_id=case_id,
            dispatch_type=context["dispatchType"],
            trace_id=context["traceId"],
            case_commitment=bundle["commitment"],
            verdict_attestation=bundle["verdictAttestation"],
            challenge_review=bundle["challengeReview"],
            kernel_version=bundle["kernelVersion"],
            include_payload=include_payload,
        )
        return {
            "caseId": case_id,
            "dispatchType": context["dispatchType"],
            "traceId": context["traceId"],
            "item": anchor,
        }

    @app.post("/internal/judge/cases/{case_id}/attestation/verify")
    async def verify_judge_report_attestation(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        context = await _resolve_report_context_for_case(
            case_id=case_id,
            dispatch_type=dispatch_type,
            not_found_detail="attestation_receipt_not_found",
            missing_report_detail="attestation_report_payload_missing",
        )
        verify_result = _verify_report_attestation(
            report_payload=context["reportPayload"],
            dispatch_type=context["dispatchType"],
        )
        return {
            "caseId": case_id,
            "dispatchType": context["dispatchType"],
            "traceId": context["traceId"],
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
        payload = _build_replay_report_payload(record)
        claim_ledger_record = await _get_claim_ledger_record(case_id=case_id, dispatch_type=None)
        if claim_ledger_record is not None:
            payload["claimLedger"] = _serialize_claim_ledger_record(
                claim_ledger_record,
                include_payload=True,
            )
        return payload

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

    def _normalize_fairness_environment_mode(
        value: str | None,
        *,
        strict: bool = False,
    ) -> str | None:
        token = str(value or "").strip().lower()
        if not token:
            return None if strict else "blocked"
        if token in {"real", "local_reference", "blocked"}:
            return token
        return None if strict else "blocked"

    def _normalize_fairness_status(
        value: str | None,
        *,
        strict: bool = False,
    ) -> str | None:
        token = str(value or "").strip().lower()
        if not token:
            return None if strict else "pending_data"
        if token in {
            "pass",
            "local_reference_frozen",
            "pending_data",
            "threshold_violation",
            "env_blocked",
            "evidence_missing",
        }:
            return token
        return None if strict else "pending_data"

    def _normalize_fairness_threshold_decision(value: str | None) -> str:
        token = str(value or "").strip().lower()
        if token in {"accepted", "violated", "pending"}:
            return token
        return "pending"

    def _metric_delta(current: float | None, baseline: float | None) -> float | None:
        if current is None or baseline is None:
            return None
        return round(current - baseline, 8)

    @app.post("/internal/judge/fairness/benchmark-runs")
    async def upsert_judge_fairness_benchmark_run(
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

        run_id = _extract_optional_str(raw_payload, "run_id", "runId")
        if run_id is None:
            raise HTTPException(status_code=422, detail="invalid_fairness_run_id")
        policy_version = (
            _extract_optional_str(raw_payload, "policy_version", "policyVersion")
            or "fairness-benchmark-v1"
        )
        environment_mode = _normalize_fairness_environment_mode(
            _extract_optional_str(raw_payload, "environment_mode", "environmentMode"),
            strict=False,
        )
        assert environment_mode is not None
        status = _normalize_fairness_status(
            _extract_optional_str(raw_payload, "status"),
            strict=False,
        )
        assert status is not None
        threshold_decision = _normalize_fairness_threshold_decision(
            _extract_optional_str(raw_payload, "threshold_decision", "thresholdDecision")
        )

        thresholds_payload = (
            raw_payload.get("thresholds")
            if isinstance(raw_payload.get("thresholds"), dict)
            else {}
        )
        metrics_payload = (
            raw_payload.get("metrics")
            if isinstance(raw_payload.get("metrics"), dict)
            else {}
        )
        summary_payload = (
            raw_payload.get("summary")
            if isinstance(raw_payload.get("summary"), dict)
            else {}
        )
        note = (
            _extract_optional_str(raw_payload, "note")
            or _extract_optional_str(summary_payload, "note")
            or ""
        )

        sample_size = _extract_optional_int(raw_payload, "sample_size", "sampleSize")
        if sample_size is None:
            sample_size = _extract_optional_int(metrics_payload, "sample_size", "sampleSize")
        draw_rate = _extract_optional_float(raw_payload, "draw_rate", "drawRate")
        if draw_rate is None:
            draw_rate = _extract_optional_float(metrics_payload, "draw_rate", "drawRate")
        side_bias_delta = _extract_optional_float(
            raw_payload,
            "side_bias_delta",
            "sideBiasDelta",
        )
        if side_bias_delta is None:
            side_bias_delta = _extract_optional_float(
                metrics_payload,
                "side_bias_delta",
                "sideBiasDelta",
            )
        appeal_overturn_rate = _extract_optional_float(
            raw_payload,
            "appeal_overturn_rate",
            "appealOverturnRate",
        )
        if appeal_overturn_rate is None:
            appeal_overturn_rate = _extract_optional_float(
                metrics_payload,
                "appeal_overturn_rate",
                "appealOverturnRate",
            )

        draw_rate_max = _extract_optional_float(raw_payload, "draw_rate_max", "drawRateMax")
        if draw_rate_max is None:
            draw_rate_max = _extract_optional_float(
                thresholds_payload,
                "draw_rate_max",
                "drawRateMax",
            )
        side_bias_delta_max = _extract_optional_float(
            raw_payload,
            "side_bias_delta_max",
            "sideBiasDeltaMax",
        )
        if side_bias_delta_max is None:
            side_bias_delta_max = _extract_optional_float(
                thresholds_payload,
                "side_bias_delta_max",
                "sideBiasDeltaMax",
            )
        appeal_overturn_rate_max = _extract_optional_float(
            raw_payload,
            "appeal_overturn_rate_max",
            "appealOverturnRateMax",
        )
        if appeal_overturn_rate_max is None:
            appeal_overturn_rate_max = _extract_optional_float(
                thresholds_payload,
                "appeal_overturn_rate_max",
                "appealOverturnRateMax",
            )

        draw_rate_drift_max = _extract_optional_float(
            raw_payload,
            "draw_rate_drift_max",
            "drawRateDriftMax",
        )
        if draw_rate_drift_max is None:
            draw_rate_drift_max = _extract_optional_float(
                thresholds_payload,
                "draw_rate_drift_max",
                "drawRateDriftMax",
            )
        side_bias_delta_drift_max = _extract_optional_float(
            raw_payload,
            "side_bias_delta_drift_max",
            "sideBiasDeltaDriftMax",
        )
        if side_bias_delta_drift_max is None:
            side_bias_delta_drift_max = _extract_optional_float(
                thresholds_payload,
                "side_bias_delta_drift_max",
                "sideBiasDeltaDriftMax",
            )
        appeal_overturn_rate_drift_max = _extract_optional_float(
            raw_payload,
            "appeal_overturn_rate_drift_max",
            "appealOverturnRateDriftMax",
        )
        if appeal_overturn_rate_drift_max is None:
            appeal_overturn_rate_drift_max = _extract_optional_float(
                thresholds_payload,
                "appeal_overturn_rate_drift_max",
                "appealOverturnRateDriftMax",
            )

        runs = await _list_fairness_benchmark_runs(
            policy_version=policy_version,
            limit=200,
        )
        baseline_run = next(
            (
                row
                for row in runs
                if row.run_id != run_id
                and row.threshold_decision == "accepted"
                and row.status in {"pass", "local_reference_frozen"}
            ),
            None,
        )
        baseline_draw_rate = baseline_run.draw_rate if baseline_run is not None else None
        baseline_side_bias_delta = baseline_run.side_bias_delta if baseline_run is not None else None
        baseline_appeal_overturn_rate = (
            baseline_run.appeal_overturn_rate if baseline_run is not None else None
        )

        draw_rate_delta = _metric_delta(draw_rate, baseline_draw_rate)
        side_bias_delta_delta = _metric_delta(side_bias_delta, baseline_side_bias_delta)
        appeal_overturn_rate_delta = _metric_delta(
            appeal_overturn_rate,
            baseline_appeal_overturn_rate,
        )
        draw_rate_delta_abs = abs(draw_rate_delta) if draw_rate_delta is not None else None
        side_bias_delta_delta_abs = (
            abs(side_bias_delta_delta) if side_bias_delta_delta is not None else None
        )
        appeal_overturn_rate_delta_abs = (
            abs(appeal_overturn_rate_delta)
            if appeal_overturn_rate_delta is not None
            else None
        )

        threshold_breaches: list[str] = []
        if draw_rate_max is not None and draw_rate is not None and draw_rate > draw_rate_max:
            threshold_breaches.append("draw_rate")
        if (
            side_bias_delta_max is not None
            and side_bias_delta is not None
            and side_bias_delta > side_bias_delta_max
        ):
            threshold_breaches.append("side_bias_delta")
        if (
            appeal_overturn_rate_max is not None
            and appeal_overturn_rate is not None
            and appeal_overturn_rate > appeal_overturn_rate_max
        ):
            threshold_breaches.append("appeal_overturn_rate")

        drift_breaches: list[str] = []
        if (
            draw_rate_drift_max is not None
            and draw_rate_delta_abs is not None
            and draw_rate_delta_abs > draw_rate_drift_max
        ):
            drift_breaches.append("draw_rate")
        if (
            side_bias_delta_drift_max is not None
            and side_bias_delta_delta_abs is not None
            and side_bias_delta_delta_abs > side_bias_delta_drift_max
        ):
            drift_breaches.append("side_bias_delta")
        if (
            appeal_overturn_rate_drift_max is not None
            and appeal_overturn_rate_delta_abs is not None
            and appeal_overturn_rate_delta_abs > appeal_overturn_rate_drift_max
        ):
            drift_breaches.append("appeal_overturn_rate")

        has_threshold_breach = bool(threshold_breaches) or status == "threshold_violation"
        has_drift_breach = bool(drift_breaches)
        needs_remediation = bool(
            _extract_optional_bool(raw_payload, "needs_remediation", "needsRemediation")
        ) or has_threshold_breach or has_drift_breach or threshold_decision == "violated"
        needs_real_env_reconfirm_override = _extract_optional_bool(
            raw_payload,
            "needs_real_env_reconfirm",
            "needsRealEnvReconfirm",
        )
        needs_real_env_reconfirm = (
            bool(needs_real_env_reconfirm_override)
            if needs_real_env_reconfirm_override is not None
            else environment_mode != "real"
        )
        reported_at = _extract_optional_datetime(raw_payload, "reported_at", "reportedAt")
        source = _extract_optional_str(raw_payload, "source") or "manual"
        reported_by = _extract_optional_str(raw_payload, "reported_by", "reportedBy") or "system"

        normalized_thresholds = dict(thresholds_payload)
        normalized_thresholds["drawRateMax"] = draw_rate_max
        normalized_thresholds["sideBiasDeltaMax"] = side_bias_delta_max
        normalized_thresholds["appealOverturnRateMax"] = appeal_overturn_rate_max
        normalized_thresholds["drawRateDriftMax"] = draw_rate_drift_max
        normalized_thresholds["sideBiasDeltaDriftMax"] = side_bias_delta_drift_max
        normalized_thresholds["appealOverturnRateDriftMax"] = appeal_overturn_rate_drift_max
        normalized_thresholds = {
            key: value for key, value in normalized_thresholds.items() if value is not None
        }

        normalized_metrics = dict(metrics_payload)
        normalized_metrics["sampleSize"] = sample_size
        normalized_metrics["drawRate"] = draw_rate
        normalized_metrics["sideBiasDelta"] = side_bias_delta
        normalized_metrics["appealOverturnRate"] = appeal_overturn_rate
        normalized_metrics["drawRateDelta"] = draw_rate_delta
        normalized_metrics["sideBiasDeltaDelta"] = side_bias_delta_delta
        normalized_metrics["appealOverturnRateDelta"] = appeal_overturn_rate_delta
        normalized_metrics = {
            key: value for key, value in normalized_metrics.items() if value is not None
        }

        drift_summary = {
            "baselineRunId": baseline_run.run_id if baseline_run is not None else None,
            "baselineReportedAt": (
                baseline_run.reported_at.isoformat() if baseline_run is not None else None
            ),
            "drawRateDelta": draw_rate_delta,
            "sideBiasDeltaDelta": side_bias_delta_delta,
            "appealOverturnRateDelta": appeal_overturn_rate_delta,
            "thresholdBreaches": threshold_breaches,
            "driftBreaches": drift_breaches,
            "hasThresholdBreach": has_threshold_breach,
            "hasDriftBreach": has_drift_breach,
        }
        normalized_summary = dict(summary_payload)
        if note:
            normalized_summary["note"] = note
        normalized_summary["drift"] = drift_summary

        row = await _upsert_fairness_benchmark_run(
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
            thresholds=normalized_thresholds,
            metrics=normalized_metrics,
            summary=normalized_summary,
            source=source,
            reported_by=reported_by,
            reported_at=reported_at,
        )

        alert_item: dict[str, Any] | None = None
        if has_threshold_breach or has_drift_breach:
            alert_type = (
                "fairness_benchmark_threshold_violation"
                if has_threshold_breach
                else "fairness_benchmark_drift_violation"
            )
            severity = "critical" if has_threshold_breach else "warning"
            breached_items = threshold_breaches if has_threshold_breach else drift_breaches
            message = (
                f"fairness benchmark run breached: run_id={run_id}; "
                f"breaches={','.join(breached_items)}"
            )
            alert = runtime.trace_store.upsert_audit_alert(
                job_id=0,
                scope_id=1,
                trace_id=f"fairness-benchmark:{run_id}",
                alert_type=alert_type,
                severity=severity,
                title="AI Judge Fairness Benchmark Drift",
                message=message,
                details={
                    "runId": run_id,
                    "policyVersion": policy_version,
                    "environmentMode": environment_mode,
                    "status": status,
                    "thresholdDecision": threshold_decision,
                    "metrics": normalized_metrics,
                    "thresholds": normalized_thresholds,
                    "drift": drift_summary,
                },
            )
            await _sync_audit_alert_to_facts(alert=alert)
            alert_item = _serialize_alert_item(alert)

        return {
            "ok": True,
            "item": _serialize_fairness_benchmark_run(row),
            "drift": drift_summary,
            "alert": alert_item,
        }

    @app.get("/internal/judge/fairness/benchmark-runs")
    async def list_judge_fairness_benchmark_runs(
        x_ai_internal_key: str | None = Header(default=None),
        policy_version: str | None = Query(default=None),
        environment_mode: str | None = Query(default=None),
        status: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        normalized_policy_version = (
            str(policy_version or "").strip() if policy_version is not None else None
        )
        if normalized_policy_version == "":
            normalized_policy_version = None
        normalized_environment_mode = _normalize_fairness_environment_mode(
            environment_mode,
            strict=True,
        )
        if environment_mode is not None and normalized_environment_mode is None:
            raise HTTPException(status_code=422, detail="invalid_environment_mode")
        normalized_status = _normalize_fairness_status(status, strict=True)
        if status is not None and normalized_status is None:
            raise HTTPException(status_code=422, detail="invalid_fairness_status")

        rows = await _list_fairness_benchmark_runs(
            policy_version=normalized_policy_version,
            environment_mode=normalized_environment_mode,
            status=normalized_status,
            limit=limit,
        )
        return {
            "count": len(rows),
            "items": [_serialize_fairness_benchmark_run(row) for row in rows],
            "filters": {
                "policyVersion": normalized_policy_version,
                "environmentMode": normalized_environment_mode,
                "status": normalized_status,
                "limit": limit,
            },
        }

    @app.get("/internal/judge/fairness/cases/{case_id}")
    async def get_judge_case_fairness(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        context = await _resolve_report_context_for_case(
            case_id=case_id,
            dispatch_type=dispatch_type,
            not_found_detail="fairness_case_not_found",
            missing_report_detail="fairness_report_payload_missing",
        )
        workflow_job = await _workflow_get_job(job_id=case_id)
        workflow_events = (
            await _workflow_list_events(job_id=case_id)
            if workflow_job is not None
            else []
        )
        report_payload = (
            context["reportPayload"] if isinstance(context["reportPayload"], dict) else {}
        )
        judge_trace = (
            report_payload.get("judgeTrace")
            if isinstance(report_payload.get("judgeTrace"), dict)
            else {}
        )
        policy_version = (
            str((judge_trace.get("policyRegistry") or {}).get("version") or "").strip()
            if isinstance(judge_trace.get("policyRegistry"), dict)
            else ""
        )
        latest_run = None
        if policy_version:
            runs = await _list_fairness_benchmark_runs(
                policy_version=policy_version,
                limit=1,
            )
            latest_run = runs[0] if runs else None

        item = _build_case_fairness_item(
            case_id=case_id,
            dispatch_type=context["dispatchType"],
            trace_id=str(context["traceId"] or ""),
            workflow_job=workflow_job,
            workflow_events=workflow_events,
            report_payload=report_payload,
            latest_run=latest_run,
        )
        return {
            "caseId": case_id,
            "dispatchType": context["dispatchType"],
            "item": item,
        }

    @app.get("/internal/judge/fairness/cases")
    async def list_judge_case_fairness(
        x_ai_internal_key: str | None = Header(default=None),
        status: str | None = Query(default=None),
        dispatch_type: str | None = Query(default=None),
        winner: str | None = Query(default=None),
        policy_version: str | None = Query(default=None),
        has_drift_breach: bool | None = Query(default=None),
        has_threshold_breach: bool | None = Query(default=None),
        has_open_review: bool | None = Query(default=None),
        gate_conclusion: str | None = Query(default=None),
        challenge_state: str | None = Query(default=None),
        sort_by: str = Query(default="updated_at"),
        sort_order: str = Query(default="desc"),
        review_required: bool | None = Query(default=None),
        panel_high_disagreement: bool | None = Query(default=None),
        offset: int = Query(default=0, ge=0, le=2000),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        normalized_status = _normalize_workflow_status(status)
        if status is not None and normalized_status is None:
            raise HTTPException(status_code=422, detail="invalid_workflow_status")
        if normalized_status is not None and normalized_status not in WORKFLOW_STATUSES:
            raise HTTPException(status_code=422, detail="invalid_workflow_status")
        normalized_dispatch_type = str(dispatch_type or "").strip().lower() or None
        if normalized_dispatch_type not in {None, "phase", "final"}:
            raise HTTPException(status_code=422, detail="invalid_dispatch_type")
        normalized_winner = str(winner or "").strip().lower() or None
        if normalized_winner not in {None, "pro", "con", "draw"}:
            raise HTTPException(status_code=422, detail="invalid_winner")
        normalized_policy_version = (
            str(policy_version or "").strip() if policy_version is not None else None
        )
        if normalized_policy_version == "":
            normalized_policy_version = None
        normalized_sort_by = _normalize_case_fairness_sort_by(sort_by)
        if normalized_sort_by not in CASE_FAIRNESS_SORT_FIELDS:
            raise HTTPException(status_code=422, detail="invalid_sort_by")
        normalized_sort_order = _normalize_case_fairness_sort_order(sort_order)
        if normalized_sort_order not in {"asc", "desc"}:
            raise HTTPException(status_code=422, detail="invalid_sort_order")
        normalized_gate_conclusion = _normalize_case_fairness_gate_conclusion(gate_conclusion)
        if (
            normalized_gate_conclusion is not None
            and normalized_gate_conclusion not in CASE_FAIRNESS_GATE_CONCLUSIONS
        ):
            raise HTTPException(status_code=422, detail="invalid_gate_conclusion")
        normalized_challenge_state = _normalize_case_fairness_challenge_state(challenge_state)
        if (
            normalized_challenge_state is not None
            and normalized_challenge_state not in CASE_FAIRNESS_CHALLENGE_STATES
        ):
            raise HTTPException(status_code=422, detail="invalid_challenge_state")

        jobs = await _workflow_list_jobs(
            status=normalized_status,
            dispatch_type=normalized_dispatch_type,
            limit=max(limit, limit + offset),
        )
        benchmark_cache: dict[str, FactFairnessBenchmarkRun | None] = {}
        items: list[dict[str, Any]] = []
        for job in jobs:
            trace = runtime.trace_store.get_trace(job.job_id)
            report_summary = (
                trace.report_summary if trace and isinstance(trace.report_summary, dict) else {}
            )
            report_payload = (
                report_summary.get("payload")
                if isinstance(report_summary.get("payload"), dict)
                else {}
            )
            if not report_payload:
                continue
            workflow_events = await _workflow_list_events(job_id=job.job_id)
            trace_id = (
                str(
                    (trace.trace_id if trace is not None else "")
                    or report_summary.get("traceId")
                    or ""
                ).strip()
            )
            dispatch_type_token = (
                str(report_summary.get("dispatchType") or "").strip().lower()
                or job.dispatch_type
            )
            judge_trace = (
                report_payload.get("judgeTrace")
                if isinstance(report_payload.get("judgeTrace"), dict)
                else {}
            )
            policy_version = (
                str((judge_trace.get("policyRegistry") or {}).get("version") or "").strip()
                if isinstance(judge_trace.get("policyRegistry"), dict)
                else ""
            )
            latest_run: FactFairnessBenchmarkRun | None = None
            if policy_version:
                if policy_version not in benchmark_cache:
                    runs = await _list_fairness_benchmark_runs(
                        policy_version=policy_version,
                        limit=1,
                    )
                    benchmark_cache[policy_version] = runs[0] if runs else None
                latest_run = benchmark_cache.get(policy_version)
            item = _build_case_fairness_item(
                case_id=job.job_id,
                dispatch_type=dispatch_type_token,
                trace_id=trace_id,
                workflow_job=job,
                workflow_events=workflow_events,
                report_payload=report_payload,
                latest_run=latest_run,
            )
            if normalized_winner is not None and item.get("winner") != normalized_winner:
                continue
            drift_summary = (
                item.get("driftSummary")
                if isinstance(item.get("driftSummary"), dict)
                else {}
            )
            if (
                normalized_policy_version is not None
                and str(drift_summary.get("policyVersion") or "").strip()
                != normalized_policy_version
            ):
                continue
            if (
                has_drift_breach is not None
                and bool(drift_summary.get("hasDriftBreach")) != has_drift_breach
            ):
                continue
            if (
                has_threshold_breach is not None
                and bool(drift_summary.get("hasThresholdBreach")) != has_threshold_breach
            ):
                continue
            challenge_link = (
                item.get("challengeLink")
                if isinstance(item.get("challengeLink"), dict)
                else {}
            )
            if (
                has_open_review is not None
                and bool(challenge_link.get("hasOpenReview")) != has_open_review
            ):
                continue
            if (
                normalized_gate_conclusion is not None
                and str(item.get("gateConclusion") or "").strip().lower()
                != normalized_gate_conclusion
            ):
                continue
            if review_required is not None and bool(item.get("reviewRequired")) != review_required:
                continue
            if panel_high_disagreement is not None and bool(
                ((item.get("panelDisagreement") or {}).get("high"))
            ) != panel_high_disagreement:
                continue
            if normalized_challenge_state is not None:
                latest_challenge = (
                    challenge_link.get("latest")
                    if isinstance(challenge_link, dict)
                    else None
                )
                latest_state = (
                    str(latest_challenge.get("state") or "").strip()
                    if isinstance(latest_challenge, dict)
                    else ""
                )
                if latest_state != normalized_challenge_state:
                    continue
            items.append(item)

        items.sort(
            key=lambda row: _build_case_fairness_sort_key(item=row, sort_by=normalized_sort_by),
            reverse=(normalized_sort_order == "desc"),
        )
        total_count = len(items)
        aggregations = _build_case_fairness_aggregations(items)
        page_items = items[offset : offset + limit]
        return {
            "count": total_count,
            "returned": len(page_items),
            "items": page_items,
            "aggregations": aggregations,
            "filters": {
                "status": normalized_status,
                "dispatchType": normalized_dispatch_type,
                "winner": normalized_winner,
                "policyVersion": normalized_policy_version,
                "hasDriftBreach": has_drift_breach,
                "hasThresholdBreach": has_threshold_breach,
                "hasOpenReview": has_open_review,
                "gateConclusion": normalized_gate_conclusion,
                "challengeState": normalized_challenge_state,
                "sortBy": normalized_sort_by,
                "sortOrder": normalized_sort_order,
                "reviewRequired": review_required,
                "panelHighDisagreement": panel_high_disagreement,
                "offset": offset,
                "limit": limit,
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
            resolved_alert_ids = await _resolve_open_alerts_for_review(
                job_id=case_id,
                actor=event_payload["reviewActor"],
                reason=event_payload["reviewReason"] or "review_approved",
            )
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

    @app.get("/internal/judge/alerts/ops-view")
    async def list_judge_alert_ops_view(
        x_ai_internal_key: str | None = Header(default=None),
        alert_type: str | None = Query(default=None),
        status: str | None = Query(default=None),
        delivery_status: str | None = Query(default=None),
        registry_type: str | None = Query(default=None),
        policy_version: str | None = Query(default=None),
        gate_code: str | None = Query(default=None),
        gate_actor: str | None = Query(default=None),
        override_applied: bool | None = Query(default=None),
        fields_mode: str = Query(default="full"),
        include_trend: bool = Query(default=True),
        trend_window_minutes: int = Query(default=1440, ge=10, le=43200),
        trend_bucket_minutes: int = Query(default=60, ge=5, le=1440),
        offset: int = Query(default=0, ge=0, le=5000),
        limit: int = Query(default=50, ge=1, le=500),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        normalized_alert_type = str(alert_type or "").strip() or None
        if (
            normalized_alert_type is not None
            and normalized_alert_type not in OPS_REGISTRY_ALERT_TYPES
        ):
            raise HTTPException(status_code=422, detail="invalid_alert_type")
        normalized_status = _normalize_ops_alert_status(status)
        if (
            normalized_status is not None
            and normalized_status not in OPS_ALERT_STATUS_VALUES
        ):
            raise HTTPException(status_code=422, detail="invalid_alert_status")
        normalized_delivery_status = _normalize_ops_alert_delivery_status(
            delivery_status
        )
        if (
            normalized_delivery_status is not None
            and normalized_delivery_status not in OPS_ALERT_DELIVERY_STATUS_VALUES
        ):
            raise HTTPException(status_code=422, detail="invalid_delivery_status")
        normalized_fields_mode = _normalize_ops_alert_fields_mode(fields_mode)
        if normalized_fields_mode not in OPS_ALERT_FIELDS_MODE_VALUES:
            raise HTTPException(status_code=422, detail="invalid_fields_mode")

        alerts = await _list_audit_alerts(job_id=0, status=None, limit=5000)
        outbox_events = runtime.trace_store.list_alert_outbox(limit=200)
        payload = _build_registry_alert_ops_view(
            alerts=alerts,
            outbox_events=outbox_events,
            alert_type=normalized_alert_type,
            status=normalized_status,
            delivery_status=normalized_delivery_status,
            registry_type=registry_type,
            policy_version=policy_version,
            gate_code=gate_code,
            gate_actor=gate_actor,
            override_applied=override_applied,
            fields_mode=normalized_fields_mode,
            include_trend=include_trend,
            trend_window_minutes=trend_window_minutes,
            trend_bucket_minutes=trend_bucket_minutes,
            offset=offset,
            limit=limit,
        )
        return payload

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
