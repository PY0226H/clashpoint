from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from typing import Any, Awaitable, Callable, cast

from fastapi import FastAPI, HTTPException, Request

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
    build_final_report_payload as build_final_report_payload_v3_final,
)
from .applications import (
    build_phase_report_payload as build_phase_report_payload_v3_phase,
)
from .applications import (
    serialize_alert_item as serialize_alert_item_v3,
)
from .applications import (
    serialize_outbox_event as serialize_outbox_event_v3,
)
from .applications import (
    validate_final_report_payload_contract as validate_final_report_payload_contract_v3_final,
)
from .applications.assistant_agent_routes import (
    AssistantAgentRouteError as AssistantAgentRouteError_v3,
)
from .applications.bootstrap_callback_helpers import (
    attach_policy_trace_snapshot_for_runtime,
    invoke_failed_callback_with_retry_for_runtime,
    invoke_v3_callback_with_retry_for_runtime,
)
from .applications.bootstrap_case_read_helpers import (
    build_courtroom_drilldown_bundle_view_for_runtime,
    build_courtroom_read_model_light_summary_for_runtime,
    build_courtroom_read_model_view_for_runtime,
    extract_optional_datetime_for_runtime,
)
from .applications.bootstrap_fairness_helpers import (
    build_case_fairness_aggregations_for_runtime,
    build_case_fairness_item_for_runtime,
)
from .applications.bootstrap_final_report_helpers import (
    build_final_report_payload_for_runtime,
)
from .applications.bootstrap_ops_panel_replay_payload_helpers import (
    build_dispatch_receipt_payload_for_runtime,
    build_ops_read_model_pack_payload_for_runtime,
    build_panel_runtime_profiles_payload_for_runtime,
    build_panel_runtime_readiness_payload_for_runtime,
    build_replay_report_payload_for_runtime,
    build_replay_reports_payload_for_runtime,
    build_shared_room_context_for_runtime,
)
from .applications.bootstrap_registry_route_helpers import (
    build_policy_registry_profile_payload_with_ready_for_runtime,
    build_policy_registry_profiles_payload_with_ready_for_runtime,
    build_registry_audits_payload_for_runtime,
    build_registry_governance_route_dependency_pack_for_runtime,
    build_registry_profile_payload_with_ready_for_runtime,
    build_registry_profiles_payload_with_ready_for_runtime,
    build_registry_release_payload_for_runtime,
    build_registry_releases_payload_for_runtime,
    raise_registry_value_error,
    raise_registry_version_not_found_lookup_error,
    run_registry_route_guard_for_runtime,
    serialize_policy_profile_with_domain_family_for_runtime,
)
from .applications.bootstrap_replay_dependencies import build_replay_dependency_packs
from .applications.bootstrap_review_alert_trust_payload_helpers import (
    build_alert_ops_view_payload_for_runtime,
    build_alert_outbox_payload_for_runtime,
    build_case_alerts_payload_for_runtime,
    build_review_case_detail_payload_for_runtime,
    build_review_cases_list_payload_for_runtime,
    build_trust_audit_anchor_payload_for_runtime,
    build_trust_challenge_decision_payload_for_runtime,
    build_trust_challenge_ops_queue_payload_for_runtime,
    build_trust_challenge_public_status_payload_for_runtime,
    build_trust_challenge_request_payload_for_runtime,
    build_trust_phasea_bundle_for_runtime,
    build_trust_public_verify_payload_for_runtime,
    build_validated_trust_item_payload_for_runtime,
    resolve_report_context_for_case_for_runtime,
    transition_judge_alert_status_for_runtime,
)
from .applications.bootstrap_review_trust_helpers import (
    build_review_case_risk_profile_for_runtime,
    build_review_trust_unified_priority_profile_for_runtime,
    build_trust_challenge_action_hints_for_runtime,
    build_trust_challenge_priority_profile_for_runtime,
)
from .applications.bootstrap_route_dependencies import (
    build_registry_release_gate_dependencies,
    build_trust_challenge_common_dependencies,
)
from .applications.bootstrap_route_guard_helpers import (
    await_payload_or_raise_http_404_for_runtime,
    await_payload_or_raise_http_422_404_for_runtime,
    await_payload_or_raise_http_422_for_runtime,
    await_payload_or_raise_http_500_for_runtime,
    build_payload_or_raise_http_404_for_runtime,
    validate_contract_or_raise_http_500_for_runtime,
)
from .applications.bootstrap_runtime_ready_helpers import (
    ensure_registry_runtime_ready_for_runtime,
    ensure_workflow_schema_ready_for_runtime,
)
from .applications.bootstrap_trust_ops_dependencies import (
    build_ops_read_model_pack_route_dependencies_for_runtime,
    build_trust_route_dependencies_for_runtime,
    build_trust_runtime_dependency_pack_for_runtime,
)
from .applications.bootstrap_workflow_state_helpers import (
    workflow_mark_completed_for_runtime,
    workflow_mark_failed_for_runtime,
    workflow_mark_replay_for_runtime,
    workflow_mark_review_required_for_runtime,
    workflow_register_and_mark_blinded_for_runtime,
    workflow_register_and_mark_case_built_for_runtime,
)
from .applications.bootstrap_workflow_trace_store_helpers import (
    append_replay_record_for_runtime,
    get_claim_ledger_record_for_runtime,
    get_dispatch_receipt_for_runtime,
    list_audit_alerts_for_runtime,
    list_claim_ledger_records_for_runtime,
    list_dispatch_receipts_for_runtime,
    list_fairness_benchmark_runs_for_runtime,
    list_fairness_shadow_runs_for_runtime,
    list_replay_records_for_runtime,
    persist_dispatch_receipt_for_runtime,
    sync_audit_alert_to_facts_for_runtime,
    upsert_claim_ledger_record_for_runtime,
    upsert_fairness_benchmark_run_for_runtime,
    upsert_fairness_shadow_run_for_runtime,
    workflow_append_event_for_runtime,
    workflow_get_job_for_runtime,
    workflow_list_events_for_runtime,
    workflow_list_jobs_for_runtime,
)
from .applications.case_overview_contract import (
    validate_case_overview_contract as validate_case_overview_contract_v3,
)
from .applications.case_read_routes import (
    CaseReadRouteError as CaseReadRouteError_v3,
)
from .applications.courtroom_read_model_contract import (
    validate_courtroom_read_model_contract as validate_courtroom_read_model_contract_v3,
)
from .applications.fairness_calibration_decision_log import (
    WorkflowFactsFairnessCalibrationDecisionLogStore,
)
from .applications.fairness_case_contract import (
    validate_case_fairness_detail_contract as validate_case_fairness_detail_contract_v3,
)
from .applications.fairness_case_contract import (
    validate_case_fairness_list_contract as validate_case_fairness_list_contract_v3,
)
from .applications.fairness_dashboard_contract import (
    validate_fairness_dashboard_contract as validate_fairness_dashboard_contract_v3,
)
from .applications.fairness_runtime_routes import (
    FairnessRouteError as FairnessRouteError_v3,
)
from .applications.judge_app_domain import JUDGE_ROLE_ORDER
from .applications.judge_command_routes import (
    JudgeCommandRouteError as JudgeCommandRouteError_v3,
)
from .applications.judge_command_routes import (
    build_dispatch_meta_from_raw as build_dispatch_meta_from_raw_v3,
)
from .applications.judge_command_routes import (
    build_receipt_dims_from_raw as build_receipt_dims_from_raw_v3,
)
from .applications.judge_command_routes import (
    extract_optional_int as extract_optional_int_v3,
)
from .applications.judge_command_routes import (
    extract_optional_str as extract_optional_str_v3,
)
from .applications.judge_command_routes import (
    resolve_idempotency_or_raise as resolve_idempotency_or_raise_v3,
)
from .applications.judge_command_routes import (
    resolve_panel_runtime_profiles as resolve_panel_runtime_profiles_v3,
)
from .applications.judge_command_routes import (
    resolve_policy_profile_or_raise as resolve_policy_profile_or_raise_v3,
)
from .applications.judge_command_routes import (
    resolve_prompt_profile_or_raise as resolve_prompt_profile_or_raise_v3,
)
from .applications.judge_command_routes import (
    resolve_tool_profile_or_raise as resolve_tool_profile_or_raise_v3,
)
from .applications.judge_command_routes import (
    validate_final_dispatch_request as validate_final_dispatch_request_v3,
)
from .applications.judge_command_routes import (
    validate_phase_dispatch_request as validate_phase_dispatch_request_v3,
)
from .applications.judge_trace_replay_routes import (
    ReplayReadRouteError as ReplayReadRouteError_v3,
)
from .applications.panel_runtime_routes import (
    PanelRuntimeRouteError as PanelRuntimeRouteError_v3,
)
from .applications.review_alert_routes import (
    ReviewRouteError as ReviewRouteError_v3,
)
from .applications.review_queue_contract import (
    validate_courtroom_drilldown_bundle_contract as validate_courtroom_drilldown_bundle_contract_v3,
)
from .applications.review_queue_contract import (
    validate_evidence_claim_ops_queue_contract as validate_evidence_claim_ops_queue_contract_v3,
)
from .applications.route_group_alert_ops import (
    AlertOpsRouteDependencies,
    register_alert_ops_routes,
)
from .applications.route_group_assistant import (
    AssistantRouteDependencies,
    register_assistant_routes,
)
from .applications.route_group_case_read import (
    CaseReadRouteDependencies,
    register_case_read_routes,
)
from .applications.route_group_fairness import (
    FairnessRouteDependencies,
    register_fairness_routes,
)
from .applications.route_group_health import register_health_routes
from .applications.route_group_judge_command import (
    JudgeCommandRouteDependencies,
    register_judge_command_routes,
)
from .applications.route_group_ops_read_model_pack import (
    register_ops_read_model_pack_routes,
)
from .applications.route_group_panel_runtime import (
    PanelRuntimeRouteDependencies,
    register_panel_runtime_routes,
)
from .applications.route_group_registry import register_registry_routes
from .applications.route_group_replay import (
    ReplayRouteDependencies,
    register_replay_routes,
)
from .applications.route_group_review import (
    ReviewRouteDependencies,
    register_review_routes,
)
from .applications.route_group_trust import (
    register_trust_routes,
)
from .applications.trust_challenge_ops_queue_routes import (
    TrustChallengeOpsQueueRouteError as TrustChallengeOpsQueueRouteError_v3,
)
from .applications.trust_challenge_runtime_routes import (
    TrustChallengeRouteError as TrustChallengeRouteError_v3,
)
from .applications.trust_read_routes import (
    TrustReadRouteError as TrustReadRouteError_v3,
)
from .callback_client import (
    callback_final_failed,
    callback_final_report,
    callback_phase_failed,
    callback_phase_report,
)
from .core.judge_core import (
    JUDGE_CORE_VERSION,
    JudgeCoreOrchestrator,
)
from .core.workflow import WorkflowTransitionError
from .domain.agents import (
    AGENT_KIND_JUDGE,
    AgentExecutionRequest,
)
from .domain.artifacts import ArtifactStorePort
from .domain.facts import (
    AuditAlert as FactAuditAlert,
)
from .domain.facts import (
    FairnessBenchmarkRun as FactFairnessBenchmarkRun,
)
from .domain.facts import (
    FairnessShadowRun as FactFairnessShadowRun,
)
from .domain.workflow import WORKFLOW_STATUSES, WorkflowJob
from .runtime_types import DispatchRuntimeConfig, SleepFn
from .settings import (
    Settings,
    build_callback_client_config,
    build_dispatch_runtime_config,
    load_settings,
)
from .trace_store import TraceStoreProtocol, build_trace_store_from_settings
from .trace_store_boundaries import TraceStoreBoundaries, build_trace_store_boundaries
from .wiring import build_artifact_store, build_v3_dispatch_callbacks

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
    trace_store_boundaries: TraceStoreBoundaries
    artifact_store: ArtifactStorePort
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
    artifact_store = build_artifact_store(settings=settings)
    trace_store_boundaries = build_trace_store_boundaries(
        trace_store=trace_store,
        workflow_store=workflow_runtime.store,
        fact_repository=workflow_runtime.facts,
        artifact_store=artifact_store,
    )
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
        trace_store_boundaries=trace_store_boundaries,
        artifact_store=artifact_store,
        workflow_runtime=workflow_runtime,
        gateway_runtime=gateway_runtime,
        registry_product_runtime=registry_product_runtime,
        agent_runtime=agent_runtime,
        policy_registry_runtime=registry_product_runtime.policy_runtime,
        prompt_registry_runtime=registry_product_runtime.prompt_runtime,
        tool_registry_runtime=registry_product_runtime.tool_runtime,
    )


TRUST_CHALLENGE_EVENT_TYPE = "trust_challenge_state_changed"
TRUST_CHALLENGE_STATE_REQUESTED = "challenge_requested"
TRUST_CHALLENGE_STATE_ACCEPTED = "challenge_accepted"
TRUST_CHALLENGE_STATE_UNDER_REVIEW = "under_internal_review"
TRUST_CHALLENGE_STATE_VERDICT_UPHELD = "verdict_upheld"
TRUST_CHALLENGE_STATE_VERDICT_OVERTURNED = "verdict_overturned"
TRUST_CHALLENGE_STATE_DRAW_AFTER_REVIEW = "draw_after_review"
TRUST_CHALLENGE_STATE_REVIEW_RETAINED = "review_retained"
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
REGISTRY_PROMPT_TOOL_RISK_SEVERITY_RANK = {
    "high": 3,
    "medium": 2,
    "low": 1,
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
        "strategySlot": "weighted_vote",
        "scoreSource": "agent3WeightedScore",
        "decisionMargin": 0.8,
        "domainSlot": "general",
        "runtimeStage": "bootstrap",
        "promptVersionKey": "finalPipelineVersion",
    },
    "judgeB": {
        "profileId": "panel-judgeB-path-alignment-v1",
        "modelStrategy": "deterministic_path_alignment",
        "strategySlot": "path_alignment",
        "scoreSource": "agent2Score",
        "decisionMargin": 0.8,
        "domainSlot": "general",
        "runtimeStage": "bootstrap",
        "promptVersionKey": "agent2PromptVersion",
    },
    "judgeC": {
        "profileId": "panel-judgeC-dimension-composite-v1",
        "modelStrategy": "deterministic_dimension_composite",
        "strategySlot": "dimension_composite",
        "scoreSource": "agent1Dimensions",
        "decisionMargin": 0.8,
        "domainSlot": "general",
        "runtimeStage": "bootstrap",
        "promptVersionKey": "summaryPromptVersion",
    },
}
CASE_FAIRNESS_GATE_CONCLUSIONS = {
    "pass_through",
    "blocked_to_draw",
}
FAIRNESS_GATE_DECISION_ALIASES = {
    "auto_passed": "pass_through",
    "review_required": "blocked_to_draw",
    "blocked_failed": "blocked_to_draw",
}
CASE_FAIRNESS_CHALLENGE_STATES = {
    TRUST_CHALLENGE_STATE_REQUESTED,
    TRUST_CHALLENGE_STATE_ACCEPTED,
    TRUST_CHALLENGE_STATE_UNDER_REVIEW,
    TRUST_CHALLENGE_STATE_VERDICT_UPHELD,
    TRUST_CHALLENGE_STATE_VERDICT_OVERTURNED,
    TRUST_CHALLENGE_STATE_DRAW_AFTER_REVIEW,
    TRUST_CHALLENGE_STATE_REVIEW_RETAINED,
    TRUST_CHALLENGE_STATE_CLOSED,
}
TRUST_CHALLENGE_OPEN_STATES = {
    TRUST_CHALLENGE_STATE_REQUESTED,
    TRUST_CHALLENGE_STATE_ACCEPTED,
    TRUST_CHALLENGE_STATE_UNDER_REVIEW,
}
CASE_FAIRNESS_SORT_FIELDS = {
    "updated_at",
    "panel_disagreement_ratio",
    "gate_conclusion",
    "case_id",
}
PANEL_RUNTIME_PROFILE_SOURCE_VALUES = {
    "policy_metadata",
    "builtin_default",
    "unknown",
}
PANEL_RUNTIME_PROFILE_SORT_FIELDS = {
    "updated_at",
    "panel_disagreement_ratio",
    "case_id",
    "judge_id",
    "profile_id",
    "model_strategy",
    "strategy_slot",
    "domain_slot",
}
REVIEW_CASE_RISK_LEVEL_VALUES = {"high", "medium", "low"}
REVIEW_CASE_SLA_BUCKET_VALUES = {"normal", "warning", "urgent", "unknown"}
REVIEW_CASE_SORT_FIELDS = {
    "updated_at",
    "risk_score",
    "unified_priority_score",
    "audit_alert_count",
    "case_id",
}
TRUST_CHALLENGE_REVIEW_STATE_VALUES = {
    "pending_review",
    "approved",
    "rejected",
    "not_required",
}
TRUST_CHALLENGE_PRIORITY_LEVEL_VALUES = {"high", "medium", "low"}
TRUST_CHALLENGE_SLA_BUCKET_VALUES = {"normal", "warning", "urgent", "unknown"}
TRUST_CHALLENGE_SORT_FIELDS = {
    "updated_at",
    "priority_score",
    "total_challenges",
    "case_id",
}
COURTROOM_CASE_SORT_FIELDS = {
    "updated_at",
    "risk_score",
    "case_id",
}
EVIDENCE_CLAIM_RELIABILITY_LEVEL_VALUES = {"high", "medium", "low", "unknown"}
EVIDENCE_CLAIM_QUEUE_SORT_FIELDS = {
    "updated_at",
    "risk_score",
    "conflict_pair_count",
    "unanswered_claim_count",
    "reliability_score",
    "case_id",
}
POLICY_DOMAIN_JUDGE_FAMILY_VALUES = {
    "general",
    "tft",
    "education",
    "finance",
    "healthcare",
    "public_policy",
    "technology",
    "law",
    "ethics",
}


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


def _normalize_policy_domain_judge_family_token(
    value: Any,
    *,
    default_general: bool,
) -> str | None:
    token = str(value or "").strip().lower()
    if token in {"*", "default"}:
        return "general"
    if not token:
        return "general" if default_general else None
    return token


def _resolve_policy_domain_judge_family_state(
    *,
    topic_domain: Any,
    metadata: dict[str, Any] | None,
) -> tuple[str, bool, str | None]:
    normalized_topic_domain = _normalize_policy_domain_judge_family_token(
        topic_domain,
        default_general=True,
    )
    effective_topic_domain = normalized_topic_domain or "general"
    metadata_payload = metadata if isinstance(metadata, dict) else {}
    configured_family = _normalize_policy_domain_judge_family_token(
        metadata_payload.get("domainJudgeFamily")
        or metadata_payload.get("domain_judge_family"),
        default_general=False,
    )
    family = configured_family or effective_topic_domain
    if family not in POLICY_DOMAIN_JUDGE_FAMILY_VALUES:
        return family, False, "invalid_policy_domain_judge_family"
    if effective_topic_domain != "general" and family != effective_topic_domain:
        return family, False, "policy_domain_family_topic_domain_mismatch"
    return family, True, None


def _enforce_policy_domain_judge_family_profile_payload(
    *,
    profile_payload: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    payload = dict(profile_payload) if isinstance(profile_payload, dict) else {}
    metadata = dict(payload.get("metadata")) if isinstance(payload.get("metadata"), dict) else {}
    family, valid, error_code = _resolve_policy_domain_judge_family_state(
        topic_domain=payload.get("topicDomain") or payload.get("topic_domain"),
        metadata=metadata,
    )
    if not valid:
        raise ValueError(error_code or "invalid_policy_domain_judge_family")
    metadata["domainJudgeFamily"] = family
    metadata["domainJudgeFamilyValid"] = True
    payload["metadata"] = metadata
    return payload, family


def _build_policy_domain_judge_family_overview(
    *,
    policy_profiles: list[Any],
    active_policy_version: str,
    preview_limit: int,
    include_versions: bool,
) -> dict[str, Any]:
    by_family: dict[str, dict[str, Any]] = {}
    invalid_items: list[dict[str, Any]] = []
    valid_count = 0
    preview_cap = max(1, min(int(preview_limit), 200))
    normalized_active_version = str(active_policy_version or "").strip()

    for profile in policy_profiles:
        version = str(getattr(profile, "version", "") or "").strip() or "unknown"
        topic_domain = str(getattr(profile, "topic_domain", "") or "").strip() or "general"
        metadata = (
            dict(getattr(profile, "metadata"))
            if isinstance(getattr(profile, "metadata", None), dict)
            else {}
        )
        family, valid, error_code = _resolve_policy_domain_judge_family_state(
            topic_domain=topic_domain,
            metadata=metadata,
        )
        family_token = family or "unknown"
        row = by_family.setdefault(
            family_token,
            {
                "domainJudgeFamily": family_token,
                "count": 0,
                "activeCount": 0,
                "validCount": 0,
                "invalidCount": 0,
                "topicDomains": set(),
                "policyVersions": [],
            },
        )
        row["count"] += 1
        if version == normalized_active_version:
            row["activeCount"] += 1
        row["topicDomains"].add(topic_domain.strip().lower() or "general")
        if include_versions and len(row["policyVersions"]) < preview_cap:
            row["policyVersions"].append(version)
        if valid:
            row["validCount"] += 1
            valid_count += 1
        else:
            row["invalidCount"] += 1
            invalid_items.append(
                {
                    "policyVersion": version,
                    "topicDomain": topic_domain,
                    "domainJudgeFamily": family_token,
                    "errorCode": error_code,
                }
            )

    family_items = []
    for row in by_family.values():
        family_items.append(
            {
                "domainJudgeFamily": row["domainJudgeFamily"],
                "count": int(row["count"]),
                "activeCount": int(row["activeCount"]),
                "validCount": int(row["validCount"]),
                "invalidCount": int(row["invalidCount"]),
                "topicDomains": sorted(str(item) for item in row["topicDomains"]),
                "policyVersions": list(row["policyVersions"]) if include_versions else [],
            }
        )
    family_items.sort(
        key=_build_domain_family_sort_key_for_runtime
    )
    return {
        "count": len(policy_profiles),
        "validCount": valid_count,
        "invalidCount": max(0, len(policy_profiles) - valid_count),
        "allowedFamilies": sorted(POLICY_DOMAIN_JUDGE_FAMILY_VALUES),
        "items": family_items,
        "invalidItems": invalid_items[:preview_cap],
        "includeVersions": bool(include_versions),
    }


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


def _serialize_fairness_shadow_run(record: FactFairnessShadowRun) -> dict[str, Any]:
    return {
        "runId": record.run_id,
        "policyVersion": record.policy_version,
        "benchmarkRunId": record.benchmark_run_id,
        "environmentMode": record.environment_mode,
        "status": record.status,
        "thresholdDecision": record.threshold_decision,
        "needsRealEnvReconfirm": bool(record.needs_real_env_reconfirm),
        "needsRemediation": bool(record.needs_remediation),
        "sampleSize": record.sample_size,
        "winnerFlipRate": record.winner_flip_rate,
        "scoreShiftDelta": record.score_shift_delta,
        "reviewRequiredDelta": record.review_required_delta,
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


def _normalize_fairness_gate_decision(
    value: Any,
    *,
    review_required: bool | None = None,
) -> str:
    token = str(value or "").strip().lower()
    if token in CASE_FAIRNESS_GATE_CONCLUSIONS:
        return token
    alias = FAIRNESS_GATE_DECISION_ALIASES.get(token)
    if alias in CASE_FAIRNESS_GATE_CONCLUSIONS:
        return alias
    if review_required is True:
        return "blocked_to_draw"
    if review_required is False:
        return "pass_through"
    if not token:
        return "pass_through"
    return ""


def _normalize_aware_datetime(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


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


def _raise_http_422_from_value_error(*, err: ValueError) -> None:
    raise HTTPException(status_code=422, detail=str(err)) from err


def _raise_http_404_from_lookup_error(*, err: LookupError) -> None:
    raise HTTPException(status_code=404, detail=str(err)) from err


def _raise_http_422_for_known_value_error(
    *,
    err: ValueError,
    details_by_code: dict[str, str],
) -> None:
    code = str(err)
    detail = details_by_code.get(code)
    if detail is not None:
        raise HTTPException(status_code=422, detail=detail) from err


def _build_domain_family_sort_key_for_runtime(row: dict[str, Any]) -> tuple[int, str]:
    return (
        -int(row.get("count") or 0),
        str(row.get("domainJudgeFamily") or ""),
    )


async def _run_route_guard_with_http_bridge(
    self_awaitable: Awaitable[dict[str, Any]],
    *,
    route_error_types: tuple[type[Exception], ...],
) -> dict[str, Any]:
    try:
        return await self_awaitable
    except route_error_types as err:
        route_err = cast(Any, err)
        raise HTTPException(
            status_code=int(route_err.status_code),
            detail=route_err.detail,
        ) from err


async def _run_replay_read_guard(self_awaitable: Awaitable[dict[str, Any]]) -> dict[str, Any]:
    return await _run_route_guard_with_http_bridge(
        self_awaitable,
        route_error_types=(ReplayReadRouteError_v3,),
    )


async def _run_trust_read_guard(self_awaitable: Awaitable[dict[str, Any]]) -> dict[str, Any]:
    return await _run_route_guard_with_http_bridge(
        self_awaitable,
        route_error_types=(TrustReadRouteError_v3,),
    )


async def _run_trust_challenge_guard(
    self_awaitable: Awaitable[dict[str, Any]],
) -> dict[str, Any]:
    return await _run_route_guard_with_http_bridge(
        self_awaitable,
        route_error_types=(
            TrustChallengeRouteError_v3,
            TrustChallengeOpsQueueRouteError_v3,
        ),
    )


async def _run_fairness_route_guard(
    self_awaitable: Awaitable[dict[str, Any]],
) -> dict[str, Any]:
    return await _run_route_guard_with_http_bridge(
        self_awaitable,
        route_error_types=(FairnessRouteError_v3,),
    )


async def _run_review_route_guard(
    self_awaitable: Awaitable[dict[str, Any]],
) -> dict[str, Any]:
    return await _run_route_guard_with_http_bridge(
        self_awaitable,
        route_error_types=(ReviewRouteError_v3,),
    )


async def _run_panel_runtime_route_guard(
    self_awaitable: Awaitable[dict[str, Any]],
) -> dict[str, Any]:
    return await _run_route_guard_with_http_bridge(
        self_awaitable,
        route_error_types=(PanelRuntimeRouteError_v3,),
    )


async def _run_judge_command_route_guard(
    self_awaitable: Awaitable[dict[str, Any]],
) -> dict[str, Any]:
    return await _run_route_guard_with_http_bridge(
        self_awaitable,
        route_error_types=(JudgeCommandRouteError_v3,),
    )


async def _run_assistant_agent_route_guard(
    self_awaitable: Awaitable[dict[str, Any]],
) -> dict[str, Any]:
    return await _run_route_guard_with_http_bridge(
        self_awaitable,
        route_error_types=(AssistantAgentRouteError_v3,),
    )


async def _run_case_read_route_guard(
    self_awaitable: Awaitable[dict[str, Any]],
) -> dict[str, Any]:
    return await _run_route_guard_with_http_bridge(
        self_awaitable,
        route_error_types=(CaseReadRouteError_v3,),
    )


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
        "workflowVersion": runtime_output.get("workflowVersion"),
        "roleContractVersion": runtime_output.get("roleContractVersion"),
        "workflowContractVersion": runtime_output.get("workflowContractVersion"),
        "artifactContractVersion": runtime_output.get("artifactContractVersion"),
        "stageContractVersion": runtime_output.get("stageContractVersion"),
        "mode": runtime_output.get("mode"),
        "officialVerdictAuthority": bool(runtime_output.get("officialVerdictAuthority")),
        "activeRoles": runtime_output.get("activeRoles"),
    }
    roles = runtime_output.get("roles")
    if isinstance(roles, list):
        judge_trace["courtroomRoles"] = [item for item in roles if isinstance(item, dict)]
    workflow_edges = runtime_output.get("workflowEdges")
    if isinstance(workflow_edges, list):
        judge_trace["courtroomWorkflowEdges"] = [
            item for item in workflow_edges if isinstance(item, dict)
        ]
        judge_trace["agentRuntime"]["workflowEdgeCount"] = len(
            judge_trace["courtroomWorkflowEdges"]
        )
    artifacts = runtime_output.get("artifacts")
    if isinstance(artifacts, list):
        judge_trace["courtroomArtifacts"] = [
            item for item in artifacts if isinstance(item, dict)
        ]
        judge_trace["agentRuntime"]["artifactCount"] = len(
            judge_trace["courtroomArtifacts"]
        )
    role_order = runtime_output.get("roleOrder")
    if isinstance(role_order, list):
        judge_trace["courtroomRoleOrder"] = [str(item) for item in role_order if str(item).strip()]


async def _read_json_object_or_raise_422(*, request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception as err:
        raise HTTPException(status_code=422, detail=f"invalid_json: {err}") from err
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="invalid_payload")
    return payload


def _serialize_fairness_benchmark_gate_run(
    row: FactFairnessBenchmarkRun | None,
) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "runId": row.run_id,
        "policyVersion": row.policy_version,
        "environmentMode": row.environment_mode,
        "status": row.status,
        "thresholdDecision": row.threshold_decision,
        "needsRemediation": bool(row.needs_remediation),
        "needsRealEnvReconfirm": bool(row.needs_real_env_reconfirm),
        "reportedAt": (
            row.reported_at.isoformat()
            if row.reported_at is not None
            else None
        ),
    }


def _serialize_fairness_shadow_gate_run(
    row: FactFairnessShadowRun | None,
) -> dict[str, Any] | None:
    if row is None:
        return None
    summary_payload = row.summary if isinstance(row.summary, dict) else {}
    breaches = summary_payload.get("breaches")
    if not isinstance(breaches, list):
        breaches = []
    return {
        "runId": row.run_id,
        "policyVersion": row.policy_version,
        "benchmarkRunId": row.benchmark_run_id,
        "environmentMode": row.environment_mode,
        "status": row.status,
        "thresholdDecision": row.threshold_decision,
        "needsRemediation": bool(row.needs_remediation),
        "needsRealEnvReconfirm": bool(row.needs_real_env_reconfirm),
        "hasBreach": bool(summary_payload.get("hasBreach")),
        "breaches": [str(item).strip() for item in breaches if str(item).strip()],
        "reportedAt": (
            row.reported_at.isoformat()
            if row.reported_at is not None
            else None
        ),
    }


async def _evaluate_policy_release_fairness_gate_for_runtime(
    *,
    policy_version: str,
    list_fairness_benchmark_runs: Callable[..., Awaitable[list[FactFairnessBenchmarkRun]]],
    list_fairness_shadow_runs: Callable[..., Awaitable[list[FactFairnessShadowRun]]],
) -> dict[str, Any]:
    version = str(policy_version or "").strip()
    if not version:
        return {
            "passed": False,
            "code": "registry_fairness_gate_invalid_policy_version",
            "message": "policy version is empty",
            "source": "benchmark",
            "benchmarkGatePassed": False,
            "shadowGateApplied": False,
            "shadowGatePassed": None,
            "thresholdDecision": None,
            "needsRemediation": None,
            "latestRun": None,
            "latestShadowRun": None,
        }
    runs = await list_fairness_benchmark_runs(
        policy_version=version,
        limit=20,
    )
    latest = runs[0] if runs else None
    if latest is None:
        return {
            "passed": False,
            "code": "registry_fairness_gate_no_benchmark",
            "message": "no fairness benchmark run found for policy version",
            "source": "benchmark",
            "benchmarkGatePassed": False,
            "shadowGateApplied": False,
            "shadowGatePassed": None,
            "thresholdDecision": None,
            "needsRemediation": None,
            "latestRun": None,
            "latestShadowRun": None,
        }

    benchmark_gate_passed = (
        latest.threshold_decision == "accepted"
        and not bool(latest.needs_remediation)
        and latest.status in FAIRNESS_RELEASE_GATE_ACCEPTED_STATUSES
    )
    serialized_latest_run = _serialize_fairness_benchmark_gate_run(latest)
    if benchmark_gate_passed:
        shadow_runs = await list_fairness_shadow_runs(
            policy_version=version,
            limit=20,
        )
        latest_shadow_run = shadow_runs[0] if shadow_runs else None
        serialized_latest_shadow_run = _serialize_fairness_shadow_gate_run(latest_shadow_run)
        if latest_shadow_run is None:
            return {
                "passed": True,
                "code": "registry_fairness_gate_passed",
                "message": "fairness gate passed",
                "source": "benchmark",
                "benchmarkGatePassed": True,
                "shadowGateApplied": False,
                "shadowGatePassed": None,
                "thresholdDecision": latest.threshold_decision,
                "needsRemediation": bool(latest.needs_remediation),
                "latestRun": serialized_latest_run,
                "latestShadowRun": None,
            }

        shadow_summary = (
            latest_shadow_run.summary
            if isinstance(latest_shadow_run.summary, dict)
            else {}
        )
        shadow_has_breach = bool(shadow_summary.get("hasBreach"))
        shadow_gate_passed = (
            latest_shadow_run.threshold_decision == "accepted"
            and not bool(latest_shadow_run.needs_remediation)
            and latest_shadow_run.status in FAIRNESS_RELEASE_GATE_ACCEPTED_STATUSES
            and not shadow_has_breach
        )
        if shadow_gate_passed:
            return {
                "passed": True,
                "code": "registry_fairness_gate_passed",
                "message": "fairness gate passed (benchmark + shadow)",
                "source": "shadow",
                "benchmarkGatePassed": True,
                "shadowGateApplied": True,
                "shadowGatePassed": True,
                "thresholdDecision": latest_shadow_run.threshold_decision,
                "needsRemediation": bool(latest_shadow_run.needs_remediation),
                "latestRun": serialized_latest_run,
                "latestShadowRun": serialized_latest_shadow_run,
            }

        if latest_shadow_run.threshold_decision != "accepted":
            code = "registry_fairness_gate_shadow_threshold_not_accepted"
            message = "latest shadow threshold_decision is not accepted"
        elif bool(latest_shadow_run.needs_remediation):
            code = "registry_fairness_gate_shadow_remediation_required"
            message = "latest shadow run requires remediation"
        elif latest_shadow_run.status not in FAIRNESS_RELEASE_GATE_ACCEPTED_STATUSES:
            code = "registry_fairness_gate_shadow_status_not_ready"
            message = "latest shadow status is not release-ready"
        else:
            code = "registry_fairness_gate_shadow_breach_detected"
            message = "latest shadow summary indicates breach"

        return {
            "passed": False,
            "code": code,
            "message": message,
            "source": "shadow",
            "benchmarkGatePassed": True,
            "shadowGateApplied": True,
            "shadowGatePassed": False,
            "thresholdDecision": latest_shadow_run.threshold_decision,
            "needsRemediation": bool(latest_shadow_run.needs_remediation),
            "latestRun": serialized_latest_run,
            "latestShadowRun": serialized_latest_shadow_run,
        }

    if latest.threshold_decision != "accepted":
        code = "registry_fairness_gate_threshold_not_accepted"
        message = "latest benchmark threshold_decision is not accepted"
    elif bool(latest.needs_remediation):
        code = "registry_fairness_gate_remediation_required"
        message = "latest benchmark requires remediation"
    else:
        code = "registry_fairness_gate_status_not_ready"
        message = "latest benchmark status is not release-ready"

    return {
        "passed": False,
        "code": code,
        "message": message,
        "source": "benchmark",
        "benchmarkGatePassed": False,
        "shadowGateApplied": False,
        "shadowGatePassed": None,
        "thresholdDecision": latest.threshold_decision,
        "needsRemediation": bool(latest.needs_remediation),
        "latestRun": serialized_latest_run,
        "latestShadowRun": None,
    }


async def _evaluate_policy_registry_dependency_health_for_runtime(
    *,
    registry_product_runtime: RegistryProductRuntime,
    policy_version: str,
    profile_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        return await registry_product_runtime.evaluate_policy_dependency_health(
            policy_version=policy_version,
            profile_payload=profile_payload,
        )
    except ValueError as err:
        code = str(err)
        if code in {
            "invalid_policy_profile",
            "invalid_registry_version",
            "invalid_policy_domain_judge_family",
            "policy_domain_family_topic_domain_mismatch",
        }:
            raise HTTPException(status_code=422, detail=code) from err
        raise HTTPException(
            status_code=422,
            detail="registry_dependency_health_invalid",
        ) from err


async def _emit_registry_fairness_gate_alert_for_runtime(
    *,
    trace_store: TraceStoreProtocol,
    sync_audit_alert_to_facts: Callable[..., Awaitable[FactAuditAlert]],
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
    alert = trace_store.upsert_audit_alert(
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
    fact_alert = await sync_audit_alert_to_facts(alert=alert)
    return serialize_alert_item_v3(fact_alert)


async def _emit_registry_dependency_health_alert_for_runtime(
    *,
    trace_store: TraceStoreProtocol,
    sync_audit_alert_to_facts: Callable[..., Awaitable[FactAuditAlert]],
    registry_type: str,
    version: str,
    dependency_health: dict[str, Any],
    action: str,
) -> dict[str, Any]:
    message = (
        f"registry dependency health blocked: registry_type={registry_type}; "
        f"version={version}; code={dependency_health.get('code')}; action={action}"
    )
    alert = trace_store.upsert_audit_alert(
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
    fact_alert = await sync_audit_alert_to_facts(alert=alert)
    return serialize_alert_item_v3(fact_alert)


async def _resolve_registry_dependency_health_alerts_for_runtime(
    *,
    runtime: AppRuntime,
    sync_audit_alert_to_facts: Callable[..., Awaitable[FactAuditAlert]],
    registry_type: str,
    version: str,
    actor: str | None,
    reason: str | None,
    action: str,
) -> list[dict[str, Any]]:
    rows = runtime.trace_store_boundaries.audit_alert_store.list_alerts(
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
        transitioned = runtime.trace_store_boundaries.audit_alert_store.transition_alert(
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
        await sync_audit_alert_to_facts(alert=transitioned)
        transitioned_fact = await runtime.workflow_runtime.facts.transition_audit_alert(
            alert_id=transitioned.alert_id,
            to_status=transitioned.status,
            now=getattr(transitioned, "updated_at", None),
        )
        resolved_items.append(
            serialize_alert_item_v3(transitioned_fact or transitioned)
        )
    return resolved_items


async def _resolve_open_alerts_for_review_for_runtime(
    *,
    runtime: AppRuntime,
    sync_audit_alert_to_facts: Callable[..., Awaitable[FactAuditAlert]],
    job_id: int,
    actor: str,
    reason: str,
) -> list[str]:
    resolved_alert_ids: list[str] = []
    raised_alerts = runtime.trace_store_boundaries.audit_alert_store.list_alerts(
        job_id=job_id,
        status="raised",
        limit=200,
    )
    for item in raised_alerts:
        row = runtime.trace_store_boundaries.audit_alert_store.transition_alert(
            job_id=job_id,
            alert_id=item.alert_id,
            to_status="resolved",
            actor=actor,
            reason=reason,
        )
        if row is None:
            continue
        await sync_audit_alert_to_facts(alert=row)
        resolved_alert_ids.append(row.alert_id)
    return resolved_alert_ids


def create_app(runtime: AppRuntime) -> FastAPI:
    app = FastAPI(title="AI Judge Service", version="0.2.0")
    judge_core = JudgeCoreOrchestrator(
        workflow_orchestrator=runtime.workflow_runtime.orchestrator
    )
    workflow_schema_state = {"ready": False}
    workflow_schema_lock = asyncio.Lock()
    _ensure_workflow_schema_ready = partial(
        ensure_workflow_schema_ready_for_runtime,
        runtime=runtime,
        workflow_schema_state=workflow_schema_state,
        workflow_schema_lock=workflow_schema_lock,
    )
    _ensure_registry_runtime_ready = partial(
        ensure_registry_runtime_ready_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )

    _persist_dispatch_receipt = partial(
        persist_dispatch_receipt_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )

    _get_dispatch_receipt = partial(
        get_dispatch_receipt_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _list_dispatch_receipts = partial(
        list_dispatch_receipts_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _append_replay_record = partial(
        append_replay_record_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _list_replay_records = partial(
        list_replay_records_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )

    _upsert_claim_ledger_record = partial(
        upsert_claim_ledger_record_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )

    _get_claim_ledger_record = partial(
        get_claim_ledger_record_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _list_claim_ledger_records = partial(
        list_claim_ledger_records_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )

    _upsert_fairness_benchmark_run = partial(
        upsert_fairness_benchmark_run_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _list_fairness_benchmark_runs = partial(
        list_fairness_benchmark_runs_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _upsert_fairness_shadow_run = partial(
        upsert_fairness_shadow_run_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _list_fairness_shadow_runs = partial(
        list_fairness_shadow_runs_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _fairness_calibration_decision_log_store = (
        WorkflowFactsFairnessCalibrationDecisionLogStore(
            facts=runtime.workflow_runtime.facts,
            ensure_schema_ready=_ensure_workflow_schema_ready,
        )
    )

    _sync_audit_alert_to_facts = partial(
        sync_audit_alert_to_facts_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )

    _list_audit_alerts = partial(
        list_audit_alerts_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )

    _workflow_register_and_mark_blinded = partial(
        workflow_register_and_mark_blinded_for_runtime,
        judge_core=judge_core,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _workflow_register_and_mark_case_built = partial(
        workflow_register_and_mark_case_built_for_runtime,
        judge_core=judge_core,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _workflow_mark_completed = partial(
        workflow_mark_completed_for_runtime,
        judge_core=judge_core,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _workflow_mark_review_required = partial(
        workflow_mark_review_required_for_runtime,
        judge_core=judge_core,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _workflow_mark_failed = partial(
        workflow_mark_failed_for_runtime,
        judge_core=judge_core,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _workflow_mark_replay = partial(
        workflow_mark_replay_for_runtime,
        judge_core=judge_core,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )

    _workflow_get_job = partial(
        workflow_get_job_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _workflow_list_jobs = partial(
        workflow_list_jobs_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _workflow_list_events = partial(
        workflow_list_events_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _workflow_append_event = partial(
        workflow_append_event_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    trust_runtime_dependencies = build_trust_runtime_dependency_pack_for_runtime(
        runtime=runtime,
        get_dispatch_receipt=_get_dispatch_receipt,
        workflow_get_job=_workflow_get_job,
        workflow_list_events=_workflow_list_events,
        list_audit_alerts=_list_audit_alerts,
        serialize_workflow_job=_serialize_workflow_job,
        run_trust_read_guard=_run_trust_read_guard,
        resolve_report_context_for_case=resolve_report_context_for_case_for_runtime,
        build_trust_phasea_bundle_for_runtime=build_trust_phasea_bundle_for_runtime,
    )
    _get_trust_registry_snapshot = (
        trust_runtime_dependencies.get_trust_registry_snapshot
    )
    _write_trust_registry_snapshot = (
        trust_runtime_dependencies.write_trust_registry_snapshot
    )
    _resolve_report_context_for_case = (
        trust_runtime_dependencies.resolve_report_context_for_case
    )
    _build_trust_phasea_bundle = trust_runtime_dependencies.build_trust_phasea_bundle
    _refresh_trust_registry_snapshot_for_case = (
        trust_runtime_dependencies.refresh_trust_registry_snapshot_for_case
    )

    evaluate_policy_release_fairness_gate = partial(
        _evaluate_policy_release_fairness_gate_for_runtime,
        list_fairness_benchmark_runs=_list_fairness_benchmark_runs,
        list_fairness_shadow_runs=_list_fairness_shadow_runs,
    )
    evaluate_policy_registry_dependency_health = partial(
        _evaluate_policy_registry_dependency_health_for_runtime,
        registry_product_runtime=runtime.registry_product_runtime,
    )
    emit_registry_fairness_gate_alert = partial(
        _emit_registry_fairness_gate_alert_for_runtime,
        trace_store=runtime.trace_store,
        sync_audit_alert_to_facts=_sync_audit_alert_to_facts,
    )
    emit_registry_dependency_health_alert = partial(
        _emit_registry_dependency_health_alert_for_runtime,
        trace_store=runtime.trace_store,
        sync_audit_alert_to_facts=_sync_audit_alert_to_facts,
    )
    resolve_registry_dependency_health_alerts = partial(
        _resolve_registry_dependency_health_alerts_for_runtime,
        runtime=runtime,
        sync_audit_alert_to_facts=_sync_audit_alert_to_facts,
    )
    resolve_open_alerts_for_review = partial(
        _resolve_open_alerts_for_review_for_runtime,
        runtime=runtime,
        sync_audit_alert_to_facts=_sync_audit_alert_to_facts,
    )
    build_shared_room_context = partial(
        build_shared_room_context_for_runtime,
        list_dispatch_receipts=_list_dispatch_receipts,
        workflow_list_jobs=_workflow_list_jobs,
    )
    build_replay_reports_payload = partial(
        build_replay_reports_payload_for_runtime,
        normalize_query_datetime=_normalize_query_datetime,
    )
    build_panel_runtime_profiles_payload = partial(
        build_panel_runtime_profiles_payload_for_runtime,
        panel_judge_ids=PANEL_JUDGE_IDS,
        panel_runtime_profile_source_values=PANEL_RUNTIME_PROFILE_SOURCE_VALUES,
        panel_runtime_profile_sort_fields=PANEL_RUNTIME_PROFILE_SORT_FIELDS,
        normalize_workflow_status=_normalize_workflow_status,
    )
    build_panel_runtime_readiness_payload = partial(
        build_panel_runtime_readiness_payload_for_runtime,
        panel_judge_ids=PANEL_JUDGE_IDS,
        panel_runtime_profile_source_values=PANEL_RUNTIME_PROFILE_SOURCE_VALUES,
        normalize_workflow_status=_normalize_workflow_status,
    )
    build_ops_read_model_pack_payload = partial(
        build_ops_read_model_pack_payload_for_runtime,
        trust_challenge_open_states=TRUST_CHALLENGE_OPEN_STATES,
        judge_role_order=JUDGE_ROLE_ORDER,
        normalize_fairness_gate_decision=_normalize_fairness_gate_decision,
    )
    _transition_judge_alert_status = partial(
        transition_judge_alert_status_for_runtime,
        transition_audit_alert=(
            runtime.trace_store_boundaries.audit_alert_store.transition_alert
        ),
        sync_audit_alert_to_facts=_sync_audit_alert_to_facts,
        facts_transition_audit_alert=runtime.workflow_runtime.facts.transition_audit_alert,
        serialize_alert_item=serialize_alert_item_v3,
        run_review_route_guard=_run_review_route_guard,
    )
    build_review_cases_list_payload = partial(
        build_review_cases_list_payload_for_runtime,
        normalize_workflow_status=_normalize_workflow_status,
        workflow_statuses=WORKFLOW_STATUSES,
        review_case_risk_level_values=REVIEW_CASE_RISK_LEVEL_VALUES,
        review_case_sla_bucket_values=REVIEW_CASE_SLA_BUCKET_VALUES,
        case_fairness_challenge_states=CASE_FAIRNESS_CHALLENGE_STATES,
        trust_challenge_review_state_values=TRUST_CHALLENGE_REVIEW_STATE_VALUES,
        trust_challenge_priority_level_values=TRUST_CHALLENGE_PRIORITY_LEVEL_VALUES,
        review_case_sort_fields=REVIEW_CASE_SORT_FIELDS,
        trust_challenge_open_states=TRUST_CHALLENGE_OPEN_STATES,
    )
    build_alert_ops_view_payload = partial(
        build_alert_ops_view_payload_for_runtime,
        ops_registry_alert_types=OPS_REGISTRY_ALERT_TYPES,
        ops_alert_status_values=OPS_ALERT_STATUS_VALUES,
        ops_alert_delivery_status_values=OPS_ALERT_DELIVERY_STATUS_VALUES,
        ops_alert_fields_mode_values=OPS_ALERT_FIELDS_MODE_VALUES,
    )
    build_trust_challenge_ops_queue_payload = partial(
        build_trust_challenge_ops_queue_payload_for_runtime,
        normalize_workflow_status=_normalize_workflow_status,
        workflow_statuses=WORKFLOW_STATUSES,
        case_fairness_challenge_states=CASE_FAIRNESS_CHALLENGE_STATES,
        trust_challenge_review_state_values=TRUST_CHALLENGE_REVIEW_STATE_VALUES,
        trust_challenge_priority_level_values=TRUST_CHALLENGE_PRIORITY_LEVEL_VALUES,
        trust_challenge_sla_bucket_values=TRUST_CHALLENGE_SLA_BUCKET_VALUES,
        trust_challenge_sort_fields=TRUST_CHALLENGE_SORT_FIELDS,
        trust_challenge_open_states=TRUST_CHALLENGE_OPEN_STATES,
    )
    build_trust_challenge_request_payload = partial(
        build_trust_challenge_request_payload_for_runtime,
        trust_challenge_state_requested=TRUST_CHALLENGE_STATE_REQUESTED,
    )
    build_trust_challenge_decision_payload = partial(
        build_trust_challenge_decision_payload_for_runtime,
        trust_challenge_state_closed=TRUST_CHALLENGE_STATE_CLOSED,
        trust_challenge_state_verdict_upheld=TRUST_CHALLENGE_STATE_VERDICT_UPHELD,
        trust_challenge_state_verdict_overturned=(
            TRUST_CHALLENGE_STATE_VERDICT_OVERTURNED
        ),
        trust_challenge_state_draw_after_review=TRUST_CHALLENGE_STATE_DRAW_AFTER_REVIEW,
        trust_challenge_state_review_retained=TRUST_CHALLENGE_STATE_REVIEW_RETAINED,
        workflow_transition_error_cls=WorkflowTransitionError,
    )
    serialize_policy_profile_with_domain_family = partial(
        serialize_policy_profile_with_domain_family_for_runtime,
        runtime=runtime,
        resolve_policy_domain_judge_family_state=(
            _resolve_policy_domain_judge_family_state
        ),
    )
    build_registry_governance_dependency_pack = partial(
        build_registry_governance_route_dependency_pack_for_runtime,
        runtime=runtime,
        registry_type_policy=REGISTRY_TYPE_POLICY,
        dependency_trend_status_values=REGISTRY_DEPENDENCY_TREND_STATUS_VALUES,
        resolve_policy_domain_judge_family_state=(
            _resolve_policy_domain_judge_family_state
        ),
        build_policy_domain_judge_family_overview=(
            _build_policy_domain_judge_family_overview
        ),
        evaluate_policy_registry_dependency_health=evaluate_policy_registry_dependency_health,
        evaluate_policy_release_fairness_gate=evaluate_policy_release_fairness_gate,
        list_audit_alerts=_list_audit_alerts,
    )
    registry_release_gate_dependencies = (
        build_registry_release_gate_dependencies(
            policy_registry_type=REGISTRY_TYPE_POLICY,
            evaluate_policy_registry_dependency_health=(
                evaluate_policy_registry_dependency_health
            ),
            emit_registry_dependency_health_alert=emit_registry_dependency_health_alert,
            resolve_registry_dependency_health_alerts=(
                resolve_registry_dependency_health_alerts
            ),
            evaluate_policy_release_fairness_gate=evaluate_policy_release_fairness_gate,
            emit_registry_fairness_gate_alert=emit_registry_fairness_gate_alert,
        )
    )
    trust_challenge_common_dependencies = (
        build_trust_challenge_common_dependencies(
            resolve_report_context_for_case=_resolve_report_context_for_case,
            workflow_get_job=_workflow_get_job,
            workflow_append_event=_workflow_append_event,
            workflow_mark_review_required=_workflow_mark_review_required,
            build_trust_phasea_bundle=_build_trust_phasea_bundle,
            serialize_workflow_job=_serialize_workflow_job,
            append_trust_challenge_event=(
                runtime.workflow_runtime.trust_registry.append_challenge_event
            ),
            trust_challenge_event_type=TRUST_CHALLENGE_EVENT_TYPE,
            trust_challenge_state_accepted=TRUST_CHALLENGE_STATE_ACCEPTED,
            trust_challenge_state_under_review=TRUST_CHALLENGE_STATE_UNDER_REVIEW,
        )
    )
    build_review_case_risk_profile = partial(
        build_review_case_risk_profile_for_runtime,
        normalize_query_datetime=_normalize_query_datetime,
    )
    build_trust_challenge_priority_profile = partial(
        build_trust_challenge_priority_profile_for_runtime,
        normalize_query_datetime=_normalize_query_datetime,
        trust_challenge_open_states=TRUST_CHALLENGE_OPEN_STATES,
    )
    build_trust_challenge_action_hints = partial(
        build_trust_challenge_action_hints_for_runtime,
        trust_challenge_open_states=TRUST_CHALLENGE_OPEN_STATES,
    )
    build_review_trust_unified_priority_profile = partial(
        build_review_trust_unified_priority_profile_for_runtime,
        trust_challenge_open_states=TRUST_CHALLENGE_OPEN_STATES,
    )
    build_courtroom_read_model_view = partial(
        build_courtroom_read_model_view_for_runtime,
        normalize_fairness_gate_decision=_normalize_fairness_gate_decision,
    )
    build_courtroom_read_model_light_summary = partial(
        build_courtroom_read_model_light_summary_for_runtime,
        normalize_fairness_gate_decision=_normalize_fairness_gate_decision,
    )
    build_courtroom_drilldown_bundle_view = partial(
        build_courtroom_drilldown_bundle_view_for_runtime,
        normalize_fairness_gate_decision=_normalize_fairness_gate_decision,
    )
    extract_optional_datetime = partial(
        extract_optional_datetime_for_runtime,
        normalize_query_datetime=_normalize_query_datetime,
    )
    build_case_fairness_item = partial(
        build_case_fairness_item_for_runtime,
        normalize_fairness_gate_decision=_normalize_fairness_gate_decision,
        serialize_fairness_benchmark_run=_serialize_fairness_benchmark_run,
        serialize_fairness_shadow_run=_serialize_fairness_shadow_run,
        trust_challenge_event_type=TRUST_CHALLENGE_EVENT_TYPE,
    )
    build_case_fairness_aggregations = partial(
        build_case_fairness_aggregations_for_runtime,
        case_fairness_gate_conclusions=CASE_FAIRNESS_GATE_CONCLUSIONS,
    )
    resolve_idempotency_or_raise = partial(
        resolve_idempotency_or_raise_v3,
        resolve_idempotency=runtime.trace_store_boundaries.write_store.resolve_idempotency,
        ttl_secs=runtime.settings.idempotency_ttl_secs,
    )
    resolve_policy_profile = partial(
        resolve_policy_profile_or_raise_v3,
        resolve_policy_profile=runtime.policy_registry_runtime.resolve,
    )
    resolve_prompt_profile = partial(
        resolve_prompt_profile_or_raise_v3,
        get_prompt_profile=runtime.prompt_registry_runtime.get_profile,
    )
    resolve_tool_profile = partial(
        resolve_tool_profile_or_raise_v3,
        get_tool_profile=runtime.tool_registry_runtime.get_profile,
    )
    extract_dispatch_meta_from_raw = partial(
        build_dispatch_meta_from_raw_v3,
        extract_optional_int=extract_optional_int_v3,
        extract_optional_str=extract_optional_str_v3,
    )
    extract_receipt_dims_from_raw = partial(
        build_receipt_dims_from_raw_v3,
        extract_optional_int=extract_optional_int_v3,
    )
    build_phase_report_payload = partial(
        build_phase_report_payload_v3_phase,
        settings=runtime.settings,
        gateway_runtime=runtime.gateway_runtime,
    )
    build_final_report_payload = partial(
        build_final_report_payload_for_runtime,
        list_dispatch_receipts=runtime.trace_store_boundaries.read_model.list_dispatch_receipts,
        build_final_report_payload=build_final_report_payload_v3_final,
        judge_style_mode=runtime.dispatch_runtime_cfg.judge_style_mode,
    )
    resolve_panel_runtime_profiles = partial(
        resolve_panel_runtime_profiles_v3,
        panel_judge_ids=PANEL_JUDGE_IDS,
        panel_runtime_profile_defaults=PANEL_RUNTIME_PROFILE_DEFAULTS,
    )
    attach_judge_agent_runtime_trace = partial(
        _attach_judge_agent_runtime_trace,
        runtime=runtime,
    )
    attach_policy_trace_snapshot = partial(
        attach_policy_trace_snapshot_for_runtime,
        runtime=runtime,
    )
    invoke_callback_with_retry = partial(
        invoke_v3_callback_with_retry_for_runtime,
        runtime=runtime,
    )
    invoke_phase_failed_callback_with_retry = partial(
        invoke_failed_callback_with_retry_for_runtime,
        runtime=runtime,
        dispatch_type="phase",
        callback_phase_failed_fn=runtime.callback_phase_failed_fn,
        callback_final_failed_fn=runtime.callback_final_failed_fn,
    )
    invoke_final_failed_callback_with_retry = partial(
        invoke_failed_callback_with_retry_for_runtime,
        runtime=runtime,
        dispatch_type="final",
        callback_phase_failed_fn=runtime.callback_phase_failed_fn,
        callback_final_failed_fn=runtime.callback_final_failed_fn,
    )
    (
        replay_context_dependencies,
        replay_report_dependencies,
        replay_finalize_dependencies,
    ) = build_replay_dependency_packs(
        runtime=runtime,
        ensure_registry_runtime_ready=_ensure_registry_runtime_ready,
        resolve_policy_profile=resolve_policy_profile,
        resolve_prompt_profile=resolve_prompt_profile,
        resolve_tool_profile=resolve_tool_profile,
        build_final_report_payload=build_final_report_payload,
        resolve_panel_runtime_profiles=resolve_panel_runtime_profiles,
        build_phase_report_payload=build_phase_report_payload,
        attach_judge_agent_runtime_trace=attach_judge_agent_runtime_trace,
        attach_policy_trace_snapshot=attach_policy_trace_snapshot,
        get_dispatch_receipt=_get_dispatch_receipt,
        list_dispatch_receipts=_list_dispatch_receipts,
        append_replay_record=_append_replay_record,
        workflow_mark_replay=_workflow_mark_replay,
        upsert_claim_ledger_record=_upsert_claim_ledger_record,
    )

    register_health_routes(app=app)

    registry_route_handles = register_registry_routes(
        app=app,
        runtime=runtime,
        require_internal_key_fn=require_internal_key,
        ensure_registry_runtime_ready=_ensure_registry_runtime_ready,
        serialize_policy_profile_with_domain_family=(
            serialize_policy_profile_with_domain_family
        ),
        build_registry_governance_dependency_pack=(
            build_registry_governance_dependency_pack
        ),
        registry_release_gate_dependencies=registry_release_gate_dependencies,
        list_audit_alerts=_list_audit_alerts,
        read_json_object_or_raise_422=_read_json_object_or_raise_422,
        run_registry_route_guard=run_registry_route_guard_for_runtime,
        build_policy_registry_profiles_payload_with_ready=(
            build_policy_registry_profiles_payload_with_ready_for_runtime
        ),
        build_policy_registry_profile_payload_with_ready=(
            build_policy_registry_profile_payload_with_ready_for_runtime
        ),
        build_registry_profiles_payload_with_ready=(
            build_registry_profiles_payload_with_ready_for_runtime
        ),
        build_registry_profile_payload_with_ready=(
            build_registry_profile_payload_with_ready_for_runtime
        ),
        build_registry_audits_payload=partial(
            build_registry_audits_payload_for_runtime,
            registry_audit_action_values=REGISTRY_AUDIT_ACTION_VALUES,
        ),
        build_registry_releases_payload=build_registry_releases_payload_for_runtime,
        build_registry_release_payload=build_registry_release_payload_for_runtime,
        enforce_policy_domain_judge_family_profile_payload=(
            _enforce_policy_domain_judge_family_profile_payload
        ),
        raise_http_422_from_value_error=_raise_http_422_from_value_error,
        raise_http_404_from_lookup_error=_raise_http_404_from_lookup_error,
        raise_registry_value_error=raise_registry_value_error,
        raise_registry_version_not_found_lookup_error=(
            raise_registry_version_not_found_lookup_error
        ),
    )

    register_judge_command_routes(
        app=app,
        deps=JudgeCommandRouteDependencies(
            runtime=runtime,
            require_internal_key_fn=require_internal_key,
            read_json_object_or_raise_422=_read_json_object_or_raise_422,
            run_judge_command_route_guard=_run_judge_command_route_guard,
            ensure_registry_runtime_ready=_ensure_registry_runtime_ready,
            resolve_idempotency_or_raise=resolve_idempotency_or_raise,
            resolve_policy_profile=resolve_policy_profile,
            resolve_prompt_profile=resolve_prompt_profile,
            resolve_tool_profile=resolve_tool_profile,
            workflow_get_job=_workflow_get_job,
            workflow_register_and_mark_case_built=(
                _workflow_register_and_mark_case_built
            ),
            serialize_workflow_job=_serialize_workflow_job,
            extract_dispatch_meta_from_raw=extract_dispatch_meta_from_raw,
            extract_receipt_dims_from_raw=extract_receipt_dims_from_raw,
            workflow_register_and_mark_blinded=_workflow_register_and_mark_blinded,
            invoke_phase_failed_callback_with_retry=(
                invoke_phase_failed_callback_with_retry
            ),
            invoke_final_failed_callback_with_retry=(
                invoke_final_failed_callback_with_retry
            ),
            persist_dispatch_receipt=_persist_dispatch_receipt,
            workflow_mark_failed=_workflow_mark_failed,
            build_phase_report_payload=build_phase_report_payload,
            build_final_report_payload=build_final_report_payload,
            attach_judge_agent_runtime_trace=attach_judge_agent_runtime_trace,
            attach_policy_trace_snapshot=attach_policy_trace_snapshot,
            upsert_claim_ledger_record=_upsert_claim_ledger_record,
            invoke_callback_with_retry=invoke_callback_with_retry,
            workflow_mark_completed=_workflow_mark_completed,
            workflow_mark_review_required=_workflow_mark_review_required,
            list_dispatch_receipts=_list_dispatch_receipts,
            resolve_panel_runtime_profiles=resolve_panel_runtime_profiles,
            sync_audit_alert_to_facts=_sync_audit_alert_to_facts,
            get_dispatch_receipt=_get_dispatch_receipt,
            build_dispatch_receipt_payload=build_dispatch_receipt_payload_for_runtime,
            validate_final_report_payload_contract=(
                validate_final_report_payload_contract_v3_final
            ),
            validate_phase_dispatch_request=validate_phase_dispatch_request_v3,
            validate_final_dispatch_request=validate_final_dispatch_request_v3,
            write_trust_registry_snapshot=_write_trust_registry_snapshot,
        ),
    )

    case_read_route_handles = register_case_read_routes(
        app=app,
        deps=CaseReadRouteDependencies(
            runtime=runtime,
            require_internal_key_fn=require_internal_key,
            run_case_read_route_guard=_run_case_read_route_guard,
            validate_contract_or_raise_http_500=(
                validate_contract_or_raise_http_500_for_runtime
            ),
            workflow_get_job=_workflow_get_job,
            workflow_list_events=_workflow_list_events,
            get_dispatch_receipt=_get_dispatch_receipt,
            trace_get=runtime.trace_store_boundaries.read_model.get_trace,
            list_replay_records=_list_replay_records,
            list_audit_alerts=_list_audit_alerts,
            get_claim_ledger_record=_get_claim_ledger_record,
            list_claim_ledger_records=_list_claim_ledger_records,
            resolve_report_context_for_case=_resolve_report_context_for_case,
            workflow_list_jobs=_workflow_list_jobs,
            build_judge_core_view=_build_judge_core_view,
            build_review_case_risk_profile=build_review_case_risk_profile,
            build_courtroom_read_model_view=build_courtroom_read_model_view,
            build_courtroom_read_model_light_summary=(
                build_courtroom_read_model_light_summary
            ),
            build_courtroom_drilldown_bundle_view=build_courtroom_drilldown_bundle_view,
            serialize_workflow_job=_serialize_workflow_job,
            normalize_workflow_status=_normalize_workflow_status,
            workflow_statuses=WORKFLOW_STATUSES,
            normalize_query_datetime=_normalize_query_datetime,
            review_case_risk_level_values=REVIEW_CASE_RISK_LEVEL_VALUES,
            review_case_sla_bucket_values=REVIEW_CASE_SLA_BUCKET_VALUES,
            courtroom_case_sort_fields=COURTROOM_CASE_SORT_FIELDS,
            evidence_claim_reliability_level_values=(
                EVIDENCE_CLAIM_RELIABILITY_LEVEL_VALUES
            ),
            evidence_claim_queue_sort_fields=EVIDENCE_CLAIM_QUEUE_SORT_FIELDS,
            validate_case_overview_contract=(
                lambda payload: validate_case_overview_contract_v3(payload)
            ),
            validate_courtroom_read_model_contract=(
                lambda payload: validate_courtroom_read_model_contract_v3(payload)
            ),
            validate_courtroom_drilldown_bundle_contract=(
                lambda payload: validate_courtroom_drilldown_bundle_contract_v3(payload)
            ),
            validate_evidence_claim_ops_queue_contract=(
                lambda payload: validate_evidence_claim_ops_queue_contract_v3(payload)
            ),
            get_trust_registry_snapshot=_get_trust_registry_snapshot,
        ),
    )

    register_assistant_routes(
        app=app,
        deps=AssistantRouteDependencies(
            runtime=runtime,
            require_internal_key_fn=require_internal_key,
            run_assistant_agent_route_guard=_run_assistant_agent_route_guard,
            build_shared_room_context=build_shared_room_context,
            build_gateway_trace_snapshot=runtime.gateway_runtime.build_trace_snapshot,
            execute_agent=runtime.agent_runtime.execute,
        ),
    )

    register_replay_routes(
        app=app,
        deps=ReplayRouteDependencies(
            runtime=runtime,
            require_internal_key_fn=require_internal_key,
            run_replay_read_guard=_run_replay_read_guard,
            build_replay_report_payload=build_replay_report_payload_for_runtime,
            build_replay_reports_payload=build_replay_reports_payload,
            replay_context_dependencies=replay_context_dependencies,
            replay_report_dependencies=replay_report_dependencies,
            replay_finalize_dependencies=replay_finalize_dependencies,
            get_trace=runtime.trace_store_boundaries.read_model.get_trace,
            list_replay_records=_list_replay_records,
            get_claim_ledger_record=_get_claim_ledger_record,
            list_traces=runtime.trace_store_boundaries.read_model.list_traces,
            build_case_chain_summary=(
                runtime.trace_store_boundaries.read_model.build_case_chain_summary
            ),
            get_trust_registry_snapshot=_get_trust_registry_snapshot,
        ),
    )

    trust_route_handles = register_trust_routes(
        app=app,
        deps=build_trust_route_dependencies_for_runtime(
            runtime=runtime,
            require_internal_key_fn=require_internal_key,
            build_validated_trust_item_payload=(
                build_validated_trust_item_payload_for_runtime
            ),
            build_trust_challenge_ops_queue_payload=(
                build_trust_challenge_ops_queue_payload
            ),
            build_trust_challenge_public_status_payload=(
                build_trust_challenge_public_status_payload_for_runtime
            ),
            build_trust_challenge_request_payload=(
                build_trust_challenge_request_payload
            ),
            build_trust_challenge_decision_payload=(
                build_trust_challenge_decision_payload
            ),
            build_trust_audit_anchor_payload=(
                build_trust_audit_anchor_payload_for_runtime
            ),
            build_trust_public_verify_payload=(
                build_trust_public_verify_payload_for_runtime
            ),
            run_trust_read_guard=_run_trust_read_guard,
            build_trust_phasea_bundle=_build_trust_phasea_bundle,
            get_dispatch_receipt=_get_dispatch_receipt,
            workflow_list_jobs=_workflow_list_jobs,
            get_trace=runtime.trace_store_boundaries.read_model.get_trace,
            build_trust_challenge_priority_profile=(
                build_trust_challenge_priority_profile
            ),
            serialize_workflow_job=_serialize_workflow_job,
            build_trust_challenge_action_hints=build_trust_challenge_action_hints,
            run_trust_challenge_guard=_run_trust_challenge_guard,
            trust_challenge_common_dependencies=trust_challenge_common_dependencies,
            upsert_audit_alert=runtime.trace_store_boundaries.audit_alert_store.upsert_alert,
            sync_audit_alert_to_facts=_sync_audit_alert_to_facts,
            workflow_mark_completed=_workflow_mark_completed,
            workflow_mark_draw_pending_vote=(
                runtime.workflow_runtime.orchestrator.mark_draw_pending_vote
            ),
            resolve_open_alerts_for_review=resolve_open_alerts_for_review,
        ),
    )

    fairness_route_handles = register_fairness_routes(
        app=app,
        deps=FairnessRouteDependencies(
            runtime=runtime,
            require_internal_key_fn=require_internal_key,
            read_json_object_or_raise_422=_read_json_object_or_raise_422,
            run_fairness_route_guard=_run_fairness_route_guard,
            workflow_get_job=_workflow_get_job,
            workflow_list_events=_workflow_list_events,
            workflow_list_jobs=_workflow_list_jobs,
            get_trace=runtime.trace_store_boundaries.read_model.get_trace,
            resolve_report_context_for_case=_resolve_report_context_for_case,
            list_fairness_benchmark_runs=_list_fairness_benchmark_runs,
            list_fairness_shadow_runs=_list_fairness_shadow_runs,
            upsert_fairness_benchmark_run=_upsert_fairness_benchmark_run,
            upsert_fairness_shadow_run=_upsert_fairness_shadow_run,
            sync_audit_alert_to_facts=_sync_audit_alert_to_facts,
            serialize_fairness_benchmark_run=_serialize_fairness_benchmark_run,
            serialize_fairness_shadow_run=_serialize_fairness_shadow_run,
            build_case_fairness_item=build_case_fairness_item,
            build_case_fairness_aggregations=build_case_fairness_aggregations,
            evaluate_policy_release_fairness_gate=evaluate_policy_release_fairness_gate,
            extract_optional_datetime=extract_optional_datetime,
            normalize_workflow_status=_normalize_workflow_status,
            workflow_statuses=WORKFLOW_STATUSES,
            case_fairness_sort_fields=CASE_FAIRNESS_SORT_FIELDS,
            case_fairness_gate_conclusions=CASE_FAIRNESS_GATE_CONCLUSIONS,
            case_fairness_challenge_states=CASE_FAIRNESS_CHALLENGE_STATES,
            validate_case_fairness_detail_contract=(
                lambda payload: validate_case_fairness_detail_contract_v3(payload)
            ),
            validate_case_fairness_list_contract=(
                lambda payload: validate_case_fairness_list_contract_v3(payload)
            ),
            validate_fairness_dashboard_contract=(
                lambda payload: validate_fairness_dashboard_contract_v3(payload)
            ),
            calibration_decision_log_store=_fairness_calibration_decision_log_store,
        ),
    )

    panel_runtime_route_handles = register_panel_runtime_routes(
        app=app,
        deps=PanelRuntimeRouteDependencies(
            runtime=runtime,
            require_internal_key_fn=require_internal_key,
            await_payload_or_raise_http_500=(
                await_payload_or_raise_http_500_for_runtime
            ),
            build_panel_runtime_profiles_payload=build_panel_runtime_profiles_payload,
            build_panel_runtime_readiness_payload=build_panel_runtime_readiness_payload,
            list_judge_case_fairness=fairness_route_handles.list_judge_case_fairness,
            run_panel_runtime_route_guard=_run_panel_runtime_route_guard,
        ),
    )

    review_route_handles = register_review_routes(
        app=app,
        deps=ReviewRouteDependencies(
            runtime=runtime,
            require_internal_key_fn=require_internal_key,
            await_payload_or_raise_http_422=(
                await_payload_or_raise_http_422_for_runtime
            ),
            await_payload_or_raise_http_404=(
                await_payload_or_raise_http_404_for_runtime
            ),
            await_payload_or_raise_http_422_404=(
                await_payload_or_raise_http_422_404_for_runtime
            ),
            build_review_cases_list_payload=build_review_cases_list_payload,
            build_review_case_detail_payload=build_review_case_detail_payload_for_runtime,
            run_review_route_guard=_run_review_route_guard,
            workflow_get_job=_workflow_get_job,
            workflow_list_jobs=_workflow_list_jobs,
            workflow_list_events=_workflow_list_events,
            workflow_mark_completed=_workflow_mark_completed,
            workflow_mark_failed=_workflow_mark_failed,
            list_audit_alerts=_list_audit_alerts,
            get_trace=runtime.trace_store_boundaries.read_model.get_trace,
            build_review_case_risk_profile=build_review_case_risk_profile,
            build_trust_challenge_priority_profile=(
                build_trust_challenge_priority_profile
            ),
            build_review_trust_unified_priority_profile=(
                build_review_trust_unified_priority_profile
            ),
            resolve_open_alerts_for_review=resolve_open_alerts_for_review,
            serialize_workflow_job=_serialize_workflow_job,
            serialize_alert_item=serialize_alert_item_v3,
            refresh_trust_registry_snapshot=(
                _refresh_trust_registry_snapshot_for_case
            ),
        ),
    )

    register_ops_read_model_pack_routes(
        app=app,
        deps=build_ops_read_model_pack_route_dependencies_for_runtime(
            runtime=runtime,
            require_internal_key_fn=require_internal_key,
            await_payload_or_raise_http_500=(
                await_payload_or_raise_http_500_for_runtime
            ),
            build_ops_read_model_pack_payload=build_ops_read_model_pack_payload,
            fairness_route_handles=fairness_route_handles,
            registry_route_handles=registry_route_handles,
            panel_runtime_route_handles=panel_runtime_route_handles,
            case_read_route_handles=case_read_route_handles,
            trust_route_handles=trust_route_handles,
            review_route_handles=review_route_handles,
        ),
    )

    register_alert_ops_routes(
        app=app,
        deps=AlertOpsRouteDependencies(
            runtime=runtime,
            require_internal_key_fn=require_internal_key,
            await_payload_or_raise_http_422=(
                await_payload_or_raise_http_422_for_runtime
            ),
            build_payload_or_raise_http_404=(
                build_payload_or_raise_http_404_for_runtime
            ),
            build_case_alerts_payload=build_case_alerts_payload_for_runtime,
            transition_judge_alert_status=_transition_judge_alert_status,
            build_alert_ops_view_payload=build_alert_ops_view_payload,
            build_alert_outbox_payload=build_alert_outbox_payload_for_runtime,
            list_audit_alerts=_list_audit_alerts,
            list_alert_outbox=runtime.trace_store_boundaries.audit_alert_store.list_outbox,
            mark_alert_outbox_delivery=(
                runtime.trace_store_boundaries.audit_alert_store.mark_outbox_delivery
            ),
            get_trace=runtime.trace_store_boundaries.read_model.get_trace,
            serialize_alert_item=serialize_alert_item_v3,
            serialize_outbox_event=serialize_outbox_event_v3,
        ),
    )

    return app


def create_default_app(*, load_settings_fn: LoadSettingsFn = load_settings) -> FastAPI:
    return create_app(
        create_runtime(
            settings=load_settings_fn(),
        )
    )
