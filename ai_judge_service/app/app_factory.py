from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, cast
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Query, Request

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
    build_challenge_review_registry as build_challenge_review_registry_v3,
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
from .applications.assistant_agent_routes import (
    AssistantAgentRouteError as AssistantAgentRouteError_v3,
)
from .applications.assistant_agent_routes import (
    build_npc_coach_advice_route_payload as build_npc_coach_advice_route_payload_v3,
)
from .applications.assistant_agent_routes import (
    build_room_qa_answer_route_payload as build_room_qa_answer_route_payload_v3,
)
from .applications.assistant_agent_routes import (
    sanitize_assistant_advisory_output as sanitize_assistant_advisory_output_v3,
)
from .applications.case_courtroom_views import (
    build_case_evidence_view as build_case_evidence_view_v3,
)
from .applications.case_courtroom_views import (
    build_courtroom_drilldown_action_hints as build_courtroom_drilldown_action_hints_v3,
)
from .applications.case_courtroom_views import (
    build_courtroom_drilldown_bundle_view as build_courtroom_drilldown_bundle_view_v3,
)
from .applications.case_courtroom_views import (
    build_courtroom_read_model_light_summary as build_courtroom_read_model_light_summary_v3,
)
from .applications.case_courtroom_views import (
    build_courtroom_read_model_view as build_courtroom_read_model_view_v3,
)
from .applications.case_courtroom_views import (
    build_evidence_claim_action_hints as build_evidence_claim_action_hints_v3,
)
from .applications.case_courtroom_views import (
    build_evidence_claim_ops_profile as build_evidence_claim_ops_profile_v3,
)
from .applications.case_courtroom_views import (
    build_evidence_claim_queue_sort_key as build_evidence_claim_queue_sort_key_v3,
)
from .applications.case_courtroom_views import (
    build_evidence_claim_reliability_profile as build_evidence_claim_reliability_profile_v3,
)
from .applications.case_courtroom_views import (
    normalize_evidence_claim_reliability_counts as normalize_evidence_claim_reliability_counts_v3,
)
from .applications.case_overview_contract import (
    validate_case_overview_contract as validate_case_overview_contract_v3,
)
from .applications.case_read_routes import (
    CaseReadRouteError as CaseReadRouteError_v3,
)
from .applications.case_read_routes import (
    build_case_claim_ledger_route_payload as build_case_claim_ledger_route_payload_v3,
)
from .applications.case_read_routes import (
    build_case_courtroom_cases_route_payload as build_case_courtroom_cases_route_payload_v3,
)
from .applications.case_read_routes import (
    build_case_courtroom_drilldown_bundle_route_payload as build_case_courtroom_drilldown_bundle_route_payload_v3,
)
from .applications.case_read_routes import (
    build_case_courtroom_read_model_payload as build_case_courtroom_read_model_payload_v3,
)
from .applications.case_read_routes import (
    build_case_courtroom_read_model_route_payload as build_case_courtroom_read_model_route_payload_v3,
)
from .applications.case_read_routes import (
    build_case_evidence_claim_ops_queue_route_payload as build_case_evidence_claim_ops_queue_route_payload_v3,
)
from .applications.case_read_routes import (
    build_case_overview_payload as build_case_overview_payload_v3,
)
from .applications.case_read_routes import (
    build_case_overview_replay_items as build_case_overview_replay_items_v3,
)
from .applications.case_read_routes import (
    build_case_overview_route_payload as build_case_overview_route_payload_v3,
)
from .applications.courtroom_read_model_contract import (
    validate_courtroom_read_model_contract as validate_courtroom_read_model_contract_v3,
)
from .applications.fairness_analysis import (
    build_fairness_calibration_drift_summary as build_fairness_calibration_drift_summary_v3,
)
from .applications.fairness_analysis import (
    build_fairness_calibration_risk_items as build_fairness_calibration_risk_items_v3,
)
from .applications.fairness_analysis import (
    build_fairness_calibration_threshold_suggestions as build_fairness_calibration_threshold_suggestions_v3,
)
from .applications.fairness_analysis import (
    build_fairness_dashboard_case_trends as build_fairness_dashboard_case_trends_v3,
)
from .applications.fairness_analysis import (
    build_fairness_dashboard_run_trends as build_fairness_dashboard_run_trends_v3,
)
from .applications.fairness_analysis import (
    build_fairness_dashboard_top_risk_cases as build_fairness_dashboard_top_risk_cases_v3,
)
from .applications.fairness_case_contract import (
    validate_case_fairness_detail_contract as validate_case_fairness_detail_contract_v3,
)
from .applications.fairness_case_contract import (
    validate_case_fairness_list_contract as validate_case_fairness_list_contract_v3,
)
from .applications.fairness_case_scan import (
    collect_fairness_case_items as collect_fairness_case_items_v3,
)
from .applications.fairness_dashboard_contract import (
    validate_fairness_dashboard_contract as validate_fairness_dashboard_contract_v3,
)
from .applications.fairness_runtime_routes import (
    FairnessRouteError as FairnessRouteError_v3,
)
from .applications.fairness_runtime_routes import (
    build_fairness_benchmark_list_payload as build_fairness_benchmark_list_payload_v3,
)
from .applications.fairness_runtime_routes import (
    build_fairness_benchmark_upsert_payload as build_fairness_benchmark_upsert_payload_v3,
)
from .applications.fairness_runtime_routes import (
    build_fairness_calibration_pack_payload as build_fairness_calibration_pack_payload_v3,
)
from .applications.fairness_runtime_routes import (
    build_fairness_case_detail_payload as build_fairness_case_detail_payload_v3,
)
from .applications.fairness_runtime_routes import (
    build_fairness_case_list_payload as build_fairness_case_list_payload_v3,
)
from .applications.fairness_runtime_routes import (
    build_fairness_dashboard_payload as build_fairness_dashboard_payload_v3,
)
from .applications.fairness_runtime_routes import (
    build_fairness_policy_calibration_advisor_payload as build_fairness_policy_calibration_advisor_payload_v3,
)
from .applications.fairness_runtime_routes import (
    build_fairness_shadow_list_payload as build_fairness_shadow_list_payload_v3,
)
from .applications.fairness_runtime_routes import (
    build_fairness_shadow_upsert_payload as build_fairness_shadow_upsert_payload_v3,
)
from .applications.judge_app_domain import JUDGE_ROLE_ORDER
from .applications.judge_command_routes import (
    JudgeCommandRouteError as JudgeCommandRouteError_v3,
)
from .applications.judge_command_routes import (
    build_blindization_rejection_route_payload as build_blindization_rejection_route_payload_v3,
)
from .applications.judge_command_routes import (
    build_case_create_route_payload as build_case_create_route_payload_v3,
)
from .applications.judge_command_routes import (
    build_final_contract_blocked_route_payload as build_final_contract_blocked_route_payload_v3,
)
from .applications.judge_command_routes import (
    build_final_dispatch_callback_delivery_route_payload as build_final_dispatch_callback_delivery_route_payload_v3,
)
from .applications.judge_command_routes import (
    build_final_dispatch_callback_result_route_payload as build_final_dispatch_callback_result_route_payload_v3,
)
from .applications.judge_command_routes import (
    build_final_dispatch_preflight_route_payload as build_final_dispatch_preflight_route_payload_v3,
)
from .applications.judge_command_routes import (
    build_final_dispatch_report_materialization_route_payload as build_final_dispatch_report_materialization_route_payload_v3,
)
from .applications.judge_command_routes import (
    build_phase_dispatch_callback_delivery_route_payload as build_phase_dispatch_callback_delivery_route_payload_v3,
)
from .applications.judge_command_routes import (
    build_phase_dispatch_callback_result_route_payload as build_phase_dispatch_callback_result_route_payload_v3,
)
from .applications.judge_command_routes import (
    build_phase_dispatch_preflight_route_payload as build_phase_dispatch_preflight_route_payload_v3,
)
from .applications.judge_command_routes import (
    build_phase_dispatch_report_materialization_route_payload as build_phase_dispatch_report_materialization_route_payload_v3,
)
from .applications.judge_dispatch_runtime import (
    CALLBACK_STATUS_FAILED_CALLBACK_FAILED as CALLBACK_STATUS_FAILED_CALLBACK_FAILED_V3,
)
from .applications.judge_dispatch_runtime import (
    CALLBACK_STATUS_FAILED_REPORTED as CALLBACK_STATUS_FAILED_REPORTED_V3,
)
from .applications.judge_dispatch_runtime import (
    CALLBACK_STATUS_REPORTED as CALLBACK_STATUS_REPORTED_V3,
)
from .applications.judge_dispatch_runtime import (
    build_final_dispatch_accepted_response as build_final_dispatch_accepted_response_v3,
)
from .applications.judge_dispatch_runtime import (
    build_final_workflow_register_payload as build_final_workflow_register_payload_v3,
)
from .applications.judge_dispatch_runtime import (
    build_final_workflow_reported_payload as build_final_workflow_reported_payload_v3,
)
from .applications.judge_dispatch_runtime import (
    build_phase_dispatch_accepted_response as build_phase_dispatch_accepted_response_v3,
)
from .applications.judge_dispatch_runtime import (
    build_phase_workflow_register_payload as build_phase_workflow_register_payload_v3,
)
from .applications.judge_dispatch_runtime import (
    build_phase_workflow_reported_payload as build_phase_workflow_reported_payload_v3,
)
from .applications.judge_dispatch_runtime import (
    deliver_report_callback_with_failed_fallback as deliver_report_callback_with_failed_fallback_v3,
)
from .applications.judge_trace_replay_routes import (
    ReplayContextDependencyPack as ReplayContextDependencyPack_v3,
)
from .applications.judge_trace_replay_routes import (
    ReplayFinalizeDependencyPack as ReplayFinalizeDependencyPack_v3,
)
from .applications.judge_trace_replay_routes import (
    ReplayReadRouteError as ReplayReadRouteError_v3,
)
from .applications.judge_trace_replay_routes import (
    ReplayReportDependencyPack as ReplayReportDependencyPack_v3,
)
from .applications.judge_trace_replay_routes import (
    build_replay_post_route_payload as build_replay_post_route_payload_v3,
)
from .applications.judge_trace_replay_routes import (
    build_replay_report_route_payload as build_replay_report_route_payload_v3,
)
from .applications.judge_trace_replay_routes import (
    build_replay_reports_list_payload as build_replay_reports_list_payload_v3,
)
from .applications.judge_trace_replay_routes import (
    build_replay_reports_route_payload as build_replay_reports_route_payload_v3,
)
from .applications.judge_trace_replay_routes import (
    build_replay_route_payload as build_replay_route_payload_v3,
)
from .applications.judge_trace_replay_routes import (
    build_trace_route_payload as build_trace_route_payload_v3,
)
from .applications.judge_trace_replay_routes import (
    build_trace_route_read_payload as build_trace_route_read_payload_v3,
)
from .applications.judge_trace_replay_routes import (
    build_trace_route_replay_items as build_trace_route_replay_items_v3,
)
from .applications.judge_trace_replay_routes import (
    choose_replay_dispatch_receipt as choose_replay_dispatch_receipt_v3,
)
from .applications.judge_trace_replay_routes import (
    extract_replay_request_snapshot as extract_replay_request_snapshot_v3,
)
from .applications.judge_trace_replay_routes import (
    normalize_replay_dispatch_type as normalize_replay_dispatch_type_v3,
)
from .applications.judge_trace_replay_routes import (
    resolve_replay_trace_id as resolve_replay_trace_id_v3,
)
from .applications.judge_trace_summary import (
    build_trace_report_summary as build_trace_report_summary_v3,
)
from .applications.judge_workflow_roles import (
    build_final_judge_workflow_payload as build_final_judge_workflow_payload_v3,
)
from .applications.judge_workflow_roles import (
    build_phase_judge_workflow_payload as build_phase_judge_workflow_payload_v3,
)
from .applications.ops_read_model_pack import (
    build_ops_read_model_pack_adaptive_summary,
    build_ops_read_model_pack_case_chain_coverage,
    build_ops_read_model_pack_fairness_gate_overview,
    build_ops_read_model_pack_filters,
    build_ops_read_model_pack_judge_workflow_coverage,
    build_ops_read_model_pack_policy_kernel_binding,
    build_ops_read_model_pack_route_payload,
    build_ops_read_model_pack_trust_overview,
    build_ops_read_model_pack_v5_payload,
    summarize_ops_read_model_pack_review_items,
    summarize_ops_read_model_pack_trust_items,
)
from .applications.panel_runtime_profile_contract import (
    validate_panel_runtime_profile_contract as validate_panel_runtime_profile_contract_v3,
)
from .applications.panel_runtime_routes import (
    PanelRuntimeRouteError as PanelRuntimeRouteError_v3,
)
from .applications.panel_runtime_routes import (
    build_panel_runtime_profiles_route_payload as build_panel_runtime_profiles_route_payload_v3,
)
from .applications.panel_runtime_routes import (
    build_panel_runtime_readiness_route_payload as build_panel_runtime_readiness_route_payload_v3,
)
from .applications.registry_governance_routes import (
    RegistryGovernanceRouteDependencyPack as RegistryGovernanceRouteDependencyPack_v3,
)
from .applications.registry_governance_routes import (
    build_policy_domain_judge_families_route_payload_from_pack as build_policy_domain_judge_families_route_payload_from_pack_v3,
)
from .applications.registry_governance_routes import (
    build_policy_gate_simulation_route_payload_from_pack as build_policy_gate_simulation_route_payload_from_pack_v3,
)
from .applications.registry_governance_routes import (
    build_policy_registry_dependency_health_route_payload_from_pack as build_policy_registry_dependency_health_route_payload_from_pack_v3,
)
from .applications.registry_governance_routes import (
    build_registry_governance_overview_route_payload_from_pack as build_registry_governance_overview_route_payload_from_pack_v3,
)
from .applications.registry_governance_routes import (
    build_registry_prompt_tool_governance_route_payload_from_pack as build_registry_prompt_tool_governance_route_payload_from_pack_v3,
)
from .applications.registry_ops_views import (
    build_registry_alert_ops_view as build_registry_alert_ops_view_v3,
)
from .applications.registry_ops_views import (
    build_registry_audit_ops_view as build_registry_audit_ops_view_v3,
)
from .applications.registry_routes import RegistryRouteError as RegistryRouteErrorV3
from .applications.registry_routes import (
    build_registry_activate_payload as build_registry_activate_payload_v3,
)
from .applications.registry_routes import (
    build_registry_audits_payload as build_registry_audits_payload_v3,
)
from .applications.registry_routes import (
    build_registry_profile_payload as build_registry_profile_payload_v3,
)
from .applications.registry_routes import (
    build_registry_profiles_payload as build_registry_profiles_payload_v3,
)
from .applications.registry_routes import (
    build_registry_publish_payload as build_registry_publish_payload_v3,
)
from .applications.registry_routes import (
    build_registry_release_payload as build_registry_release_payload_v3,
)
from .applications.registry_routes import (
    build_registry_releases_payload as build_registry_releases_payload_v3,
)
from .applications.registry_routes import (
    build_registry_rollback_payload as build_registry_rollback_payload_v3,
)
from .applications.registry_routes import (
    parse_registry_publish_request_payload as parse_registry_publish_request_payload_v3,
)
from .applications.review_alert_routes import (
    ReviewRouteError as ReviewRouteError_v3,
)
from .applications.review_alert_routes import (
    build_alert_ops_view_payload as build_alert_ops_view_payload_v3,
)
from .applications.review_alert_routes import (
    build_alert_outbox_delivery_payload as build_alert_outbox_delivery_payload_v3,
)
from .applications.review_alert_routes import (
    build_alert_outbox_route_payload as build_alert_outbox_route_payload_v3,
)
from .applications.review_alert_routes import (
    build_alert_status_transition_payload as build_alert_status_transition_payload_v3,
)
from .applications.review_alert_routes import (
    build_case_alerts_payload as build_case_alerts_payload_v3,
)
from .applications.review_alert_routes import (
    build_rag_diagnostics_payload as build_rag_diagnostics_payload_v3,
)
from .applications.review_alert_routes import (
    build_review_case_decision_payload as build_review_case_decision_payload_v3,
)
from .applications.review_alert_routes import (
    build_review_case_detail_payload as build_review_case_detail_payload_v3,
)
from .applications.review_alert_routes import (
    build_review_cases_list_payload as build_review_cases_list_payload_v3,
)
from .applications.review_alert_routes import (
    normalize_review_case_filters as normalize_review_case_filters_v3,
)
from .applications.review_queue_contract import (
    validate_courtroom_drilldown_bundle_contract as validate_courtroom_drilldown_bundle_contract_v3,
)
from .applications.review_queue_contract import (
    validate_evidence_claim_ops_queue_contract as validate_evidence_claim_ops_queue_contract_v3,
)
from .applications.trust_audit_anchor_contract import (
    validate_trust_audit_anchor_contract as validate_trust_audit_anchor_contract_v3,
)
from .applications.trust_challenge_ops_queue_routes import (
    TrustChallengeOpsQueueRouteError as TrustChallengeOpsQueueRouteError_v3,
)
from .applications.trust_challenge_ops_queue_routes import (
    build_trust_challenge_ops_queue_route_payload as build_trust_challenge_ops_queue_route_payload_v3,
)
from .applications.trust_challenge_queue_contract import (
    validate_trust_challenge_queue_contract as validate_trust_challenge_queue_contract_v3,
)
from .applications.trust_challenge_review_contract import (
    validate_trust_challenge_review_contract as validate_trust_challenge_review_contract_v3,
)
from .applications.trust_challenge_runtime_routes import (
    TrustChallengeRouteError as TrustChallengeRouteError_v3,
)
from .applications.trust_challenge_runtime_routes import (
    build_trust_challenge_decision_payload as build_trust_challenge_decision_payload_v3,
)
from .applications.trust_challenge_runtime_routes import (
    build_trust_challenge_request_payload as build_trust_challenge_request_payload_v3,
)
from .applications.trust_commitment_contract import (
    validate_trust_commitment_contract as validate_trust_commitment_contract_v3,
)
from .applications.trust_kernel_version_contract import (
    validate_trust_kernel_version_contract as validate_trust_kernel_version_contract_v3,
)
from .applications.trust_ops_views import (
    build_public_trust_verify_payload as build_public_trust_verify_payload_v3,
)
from .applications.trust_ops_views import (
    build_trust_challenge_ops_queue_item as build_trust_challenge_ops_queue_item_v3,
)
from .applications.trust_ops_views import (
    build_trust_challenge_ops_queue_payload as build_trust_challenge_ops_queue_payload_v3,
)
from .applications.trust_public_verify_contract import (
    validate_trust_public_verify_contract as validate_trust_public_verify_contract_v3,
)
from .applications.trust_read_routes import (
    TrustReadRouteError as TrustReadRouteError_v3,
)
from .applications.trust_read_routes import (
    build_trust_attestation_verify_payload as build_trust_attestation_verify_payload_v3,
)
from .applications.trust_read_routes import (
    build_trust_audit_anchor_route_payload as build_trust_audit_anchor_route_payload_v3,
)
from .applications.trust_read_routes import (
    build_trust_phasea_bundle_for_case as build_trust_phasea_bundle_for_case_v3,
)
from .applications.trust_read_routes import (
    build_trust_public_verify_bundle_payload as build_trust_public_verify_bundle_payload_v3,
)
from .applications.trust_read_routes import (
    build_validated_trust_item_route_payload as build_validated_trust_item_route_payload_v3,
)
from .applications.trust_read_routes import (
    resolve_trust_report_context_for_case as resolve_trust_report_context_for_case_v3,
)
from .applications.trust_verdict_attestation_contract import (
    validate_trust_verdict_attestation_contract as validate_trust_verdict_attestation_contract_v3,
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
    FairnessShadowRun as FactFairnessShadowRun,
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
        key=lambda row: (
            -int(row.get("count") or 0),
            str(row.get("domainJudgeFamily") or ""),
        )
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


def _serialize_policy_profile(runtime: AppRuntime, *, profile: Any) -> dict[str, Any]:
    payload = runtime.policy_registry_runtime.serialize_profile(profile)
    metadata = dict(payload.get("metadata")) if isinstance(payload.get("metadata"), dict) else {}
    family, valid, error_code = _resolve_policy_domain_judge_family_state(
        topic_domain=payload.get("topicDomain") or payload.get("topic_domain"),
        metadata=metadata,
    )
    metadata["domainJudgeFamily"] = family
    metadata["domainJudgeFamilyValid"] = bool(valid)
    if error_code:
        metadata["domainJudgeFamilyError"] = error_code
    payload["metadata"] = metadata
    return payload


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
    def _normalize_text_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        out: list[str] = []
        seen: set[str] = set()
        for item in value:
            token = str(item or "").strip()
            if not token or token in seen:
                continue
            seen.add(token)
            out.append(token)
        return out

    def _to_bool(value: Any, *, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        text = str(value or "").strip().lower()
        if text in {"1", "true", "yes", "y", "on"}:
            return True
        if text in {"0", "false", "no", "n", "off"}:
            return False
        return default

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
    runtime_context = metadata.get("panelRuntimeContext")
    if not isinstance(runtime_context, dict):
        runtime_context = metadata.get("panel_runtime_context")
    runtime_context = runtime_context if isinstance(runtime_context, dict) else {}
    normalized: dict[str, dict[str, Any]] = {}
    policy_version = str(getattr(profile, "version", "") or "").strip()
    toolset_version = str(getattr(profile, "tool_registry_version", "") or "").strip()
    raw_topic_domain = str(getattr(profile, "topic_domain", "") or "").strip().lower()
    topic_domain = raw_topic_domain if raw_topic_domain not in {"", "*"} else "general"
    default_domain_slot = (
        str(
            runtime_context.get("defaultDomainSlot")
            or runtime_context.get("default_domain_slot")
            or ""
        ).strip()
        or topic_domain
    )
    default_runtime_stage = (
        str(
            runtime_context.get("runtimeStage")
            or runtime_context.get("runtime_stage")
            or "bootstrap"
        ).strip()
        or "bootstrap"
    )
    default_adaptive_enabled = _to_bool(
        runtime_context.get("adaptiveEnabled")
        if runtime_context.get("adaptiveEnabled") is not None
        else runtime_context.get("adaptive_enabled"),
        default=False,
    )
    default_candidate_models = _normalize_text_list(
        runtime_context.get("candidateModels")
        if runtime_context.get("candidateModels") is not None
        else runtime_context.get("candidate_models")
    )
    default_strategy_metadata = (
        dict(runtime_context.get("strategyMetadata"))
        if isinstance(runtime_context.get("strategyMetadata"), dict)
        else (
            dict(runtime_context.get("strategy_metadata"))
            if isinstance(runtime_context.get("strategy_metadata"), dict)
            else {}
        )
    )

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
            "strategySlot": str(
                row.get("strategySlot")
                or row.get("strategy_slot")
                or defaults["strategySlot"]
            ).strip()
            or defaults["strategySlot"],
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
            "domainSlot": str(
                row.get("domainSlot")
                or row.get("domain_slot")
                or default_domain_slot
                or defaults["domainSlot"]
            ).strip()
            or default_domain_slot
            or defaults["domainSlot"],
            "runtimeStage": str(
                row.get("runtimeStage")
                or row.get("runtime_stage")
                or default_runtime_stage
                or defaults["runtimeStage"]
            ).strip()
            or default_runtime_stage
            or defaults["runtimeStage"],
            "adaptiveEnabled": _to_bool(
                row.get("adaptiveEnabled")
                if row.get("adaptiveEnabled") is not None
                else row.get("adaptive_enabled"),
                default=default_adaptive_enabled,
            ),
            "candidateModels": (
                _normalize_text_list(
                    row.get("candidateModels")
                    if row.get("candidateModels") is not None
                    else row.get("candidate_models")
                )
                or list(default_candidate_models)
            ),
            "strategyMetadata": (
                dict(row.get("strategyMetadata"))
                if isinstance(row.get("strategyMetadata"), dict)
                else (
                    dict(row.get("strategy_metadata"))
                    if isinstance(row.get("strategy_metadata"), dict)
                    else dict(default_strategy_metadata)
                )
            ),
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


def _build_verdict_contract(payload: dict[str, Any] | None) -> dict[str, Any]:
    return build_verdict_contract_v3(payload)


def _payload_int(payload: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = payload.get(key)
        if value is None or isinstance(value, bool):
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _payload_str(payload: dict[str, Any], *keys: str) -> str | None:
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

    phase_no = _payload_int(payload, "phase_no", "phaseNo")
    phase_start_no = _payload_int(payload, "phase_start_no", "phaseStartNo")
    phase_end_no = _payload_int(payload, "phase_end_no", "phaseEndNo")
    message_start_id = _payload_int(payload, "message_start_id", "messageStartId")
    message_end_id = _payload_int(payload, "message_end_id", "messageEndId")
    message_count = _payload_int(payload, "message_count", "messageCount")

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
                "messageId": _payload_int(row, "message_id", "messageId"),
                "side": side if side else None,
                "speakerTag": speaker_tag or None,
                "createdAt": _payload_str(row, "created_at", "createdAt"),
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
        "caseId": _payload_int(payload, "case_id", "caseId"),
        "scopeId": _payload_int(payload, "scope_id", "scopeId"),
        "sessionId": _payload_int(payload, "session_id", "sessionId"),
        "traceId": _payload_str(payload, "trace_id", "traceId"),
        "topicDomain": _payload_str(payload, "topic_domain", "topicDomain"),
        "rubricVersion": _payload_str(payload, "rubric_version", "rubricVersion"),
        "judgePolicyVersion": _payload_str(payload, "judge_policy_version", "judgePolicyVersion"),
        "retrievalProfile": _payload_str(payload, "retrieval_profile", "retrievalProfile"),
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


def _build_case_evidence_view(
    *,
    report_payload: dict[str, Any] | None,
    verdict_contract: dict[str, Any] | None,
    claim_ledger_record: FactClaimLedgerRecord | None = None,
) -> dict[str, Any]:
    return build_case_evidence_view_v3(
        report_payload=report_payload,
        verdict_contract=verdict_contract,
        claim_ledger_record=claim_ledger_record,
    )


def _build_courtroom_read_model_view(
    *,
    report_payload: dict[str, Any] | None,
    case_evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    return build_courtroom_read_model_view_v3(
        report_payload=report_payload,
        case_evidence=case_evidence,
        normalize_fairness_gate_decision=_normalize_fairness_gate_decision,
    )


def _build_courtroom_read_model_light_summary(
    *,
    courtroom_view: dict[str, Any] | None,
) -> dict[str, Any]:
    return build_courtroom_read_model_light_summary_v3(
        courtroom_view=courtroom_view,
        normalize_fairness_gate_decision=_normalize_fairness_gate_decision,
    )


def _build_courtroom_drilldown_bundle_view(
    *,
    courtroom_view: dict[str, Any] | None,
    claim_preview_limit: int,
    evidence_preview_limit: int,
    panel_preview_limit: int,
) -> dict[str, Any]:
    return build_courtroom_drilldown_bundle_view_v3(
        courtroom_view=courtroom_view,
        claim_preview_limit=claim_preview_limit,
        evidence_preview_limit=evidence_preview_limit,
        panel_preview_limit=panel_preview_limit,
        normalize_fairness_gate_decision=_normalize_fairness_gate_decision,
    )


def _build_courtroom_drilldown_action_hints(
    *,
    drilldown: dict[str, Any],
) -> list[str]:
    return build_courtroom_drilldown_action_hints_v3(
        drilldown=drilldown,
    )


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
        item["caseDossier"] = dict(record.case_dossier)
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


def _normalize_courtroom_case_sort_by(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "updated_at"
    return normalized


def _normalize_courtroom_case_sort_order(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "desc"
    return normalized


def _build_courtroom_case_sort_key(*, item: dict[str, Any], sort_by: str) -> tuple[Any, ...]:
    risk = item.get("riskProfile") if isinstance(item.get("riskProfile"), dict) else {}
    workflow = item.get("workflow") if isinstance(item.get("workflow"), dict) else {}
    if sort_by == "risk_score":
        return (
            int(risk.get("score") or 0),
            str(workflow.get("updatedAt") or "").strip(),
            int(workflow.get("caseId") or 0),
        )
    if sort_by == "case_id":
        return (int(workflow.get("caseId") or 0),)
    return (
        str(workflow.get("updatedAt") or "").strip(),
        int(risk.get("score") or 0),
        int(workflow.get("caseId") or 0),
    )


def _normalize_evidence_claim_reliability_level(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    return normalized


def _normalize_evidence_claim_queue_sort_by(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "updated_at"
    return normalized


def _normalize_evidence_claim_queue_sort_order(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "desc"
    return normalized


def _normalize_evidence_claim_reliability_counts(raw: Any) -> dict[str, int]:
    return normalize_evidence_claim_reliability_counts_v3(raw)


def _build_evidence_claim_reliability_profile(
    *,
    evidence_stats: dict[str, Any],
    fallback_decisive_count: int,
) -> dict[str, Any]:
    return build_evidence_claim_reliability_profile_v3(
        evidence_stats=evidence_stats,
        fallback_decisive_count=fallback_decisive_count,
    )


def _build_evidence_claim_ops_profile(
    *,
    risk_profile: dict[str, Any],
    courtroom_summary: dict[str, Any],
) -> dict[str, Any]:
    return build_evidence_claim_ops_profile_v3(
        risk_profile=risk_profile,
        courtroom_summary=courtroom_summary,
    )


def _build_evidence_claim_action_hints(
    *,
    ops_profile: dict[str, Any],
    review_required: bool,
) -> list[str]:
    return build_evidence_claim_action_hints_v3(
        ops_profile=ops_profile,
        review_required=review_required,
    )


def _build_evidence_claim_queue_sort_key(
    *,
    item: dict[str, Any],
    sort_by: str,
) -> tuple[Any, ...]:
    return build_evidence_claim_queue_sort_key_v3(
        item=item,
        sort_by=sort_by,
    )


def _normalize_trust_challenge_state_filter(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized or normalized == "all":
        return None
    return normalized


def _normalize_trust_challenge_review_state(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    return normalized


def _normalize_trust_challenge_priority_level(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    return normalized


def _normalize_trust_challenge_sla_bucket(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    return normalized


def _normalize_trust_challenge_sort_by(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "priority_score"
    return normalized


def _normalize_trust_challenge_sort_order(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "desc"
    return normalized


def _build_trust_challenge_priority_profile(
    *,
    workflow: WorkflowJob,
    challenge_review: dict[str, Any],
    report_payload: dict[str, Any],
    report_summary: dict[str, Any],
    now: datetime,
) -> dict[str, Any]:
    review = challenge_review if isinstance(challenge_review, dict) else {}
    payload = report_payload if isinstance(report_payload, dict) else {}
    summary = report_summary if isinstance(report_summary, dict) else {}
    fairness_summary = (
        payload.get("fairnessSummary")
        if isinstance(payload.get("fairnessSummary"), dict)
        else {}
    )

    challenge_state = str(review.get("challengeState") or "").strip().lower()
    review_state = str(review.get("reviewState") or "").strip().lower()
    total_challenges_raw = review.get("totalChallenges")
    try:
        total_challenges = max(0, int(total_challenges_raw))
    except (TypeError, ValueError):
        total_challenges = 0
    open_alert_ids = (
        review.get("openAlertIds")
        if isinstance(review.get("openAlertIds"), list)
        else []
    )
    open_alert_count = len(open_alert_ids)
    alert_summary = (
        review.get("alertSummary")
        if isinstance(review.get("alertSummary"), dict)
        else {}
    )
    critical_alert_count = int(alert_summary.get("critical") or 0)
    challenge_reasons = (
        review.get("challengeReasons")
        if isinstance(review.get("challengeReasons"), list)
        else []
    )

    age_minutes: int | None = None
    if isinstance(workflow.updated_at, datetime):
        updated_at = _normalize_query_datetime(workflow.updated_at)
        if updated_at is not None:
            age_delta = now - updated_at
            age_minutes = max(0, int(age_delta.total_seconds() // 60))

    risk_score = 0
    risk_tags: list[str] = []
    if challenge_state in TRUST_CHALLENGE_OPEN_STATES:
        risk_score += 35
        risk_tags.append("open_challenge")
    if review_state == "pending_review":
        risk_score += 20
        risk_tags.append("pending_review")
    if bool(review.get("reviewRequired")):
        risk_score += 10
        risk_tags.append("review_required")
    if total_challenges >= 2:
        risk_score += min(15, (total_challenges - 1) * 5)
        risk_tags.append("multi_challenge_case")
    if open_alert_count > 0:
        risk_score += min(20, open_alert_count * 4)
        risk_tags.append("open_alerts_present")
    if critical_alert_count > 0:
        risk_score += 10
        risk_tags.append("critical_alert_present")
    if str(summary.get("callbackStatus") or "").strip().lower() in {
        "failed",
        "error",
        "callback_failed",
        "blocked_failed_reported",
    }:
        risk_score += 12
        risk_tags.append("callback_failed")
    if bool(fairness_summary.get("panelHighDisagreement")):
        risk_score += 8
        risk_tags.append("panel_high_disagreement")
    if len([item for item in challenge_reasons if str(item).strip()]) >= 3:
        risk_score += 5
        risk_tags.append("multi_reason_challenge")
    if age_minutes is not None and age_minutes >= 360:
        risk_score += 15
        risk_tags.append("challenge_stale_6h")
    elif age_minutes is not None and age_minutes >= 120:
        risk_score += 8
        risk_tags.append("challenge_stale_2h")

    risk_score = max(0, min(int(risk_score), 100))
    if risk_score >= 75:
        risk_level = "high"
    elif risk_score >= 45:
        risk_level = "medium"
    else:
        risk_level = "low"

    if age_minutes is None:
        sla_bucket = "unknown"
    elif age_minutes >= 360:
        sla_bucket = "urgent"
    elif age_minutes >= 120:
        sla_bucket = "warning"
    else:
        sla_bucket = "normal"

    return {
        "score": risk_score,
        "level": risk_level,
        "tags": risk_tags,
        "ageMinutes": age_minutes,
        "slaBucket": sla_bucket,
        "challengeState": challenge_state or None,
        "reviewState": review_state or None,
        "reviewRequired": bool(review.get("reviewRequired")),
        "totalChallenges": total_challenges,
        "openAlertCount": open_alert_count,
    }


def _build_trust_challenge_sort_key(*, item: dict[str, Any], sort_by: str) -> tuple[Any, ...]:
    priority = (
        item.get("priorityProfile")
        if isinstance(item.get("priorityProfile"), dict)
        else {}
    )
    workflow = item.get("workflow") if isinstance(item.get("workflow"), dict) else {}
    challenge_review = (
        item.get("challengeReview")
        if isinstance(item.get("challengeReview"), dict)
        else {}
    )
    if sort_by == "priority_score":
        return (
            int(priority.get("score") or 0),
            str(workflow.get("updatedAt") or "").strip(),
            int(workflow.get("caseId") or 0),
        )
    if sort_by == "total_challenges":
        return (
            int(challenge_review.get("totalChallenges") or 0),
            int(priority.get("score") or 0),
            int(workflow.get("caseId") or 0),
        )
    if sort_by == "case_id":
        return (int(workflow.get("caseId") or 0),)
    return (
        str(workflow.get("updatedAt") or "").strip(),
        int(priority.get("score") or 0),
        int(workflow.get("caseId") or 0),
    )


def _build_trust_challenge_action_hints(
    *,
    challenge_review: dict[str, Any],
    priority_profile: dict[str, Any],
) -> list[str]:
    review = challenge_review if isinstance(challenge_review, dict) else {}
    priority = priority_profile if isinstance(priority_profile, dict) else {}
    hints: list[str] = []
    challenge_state = str(
        review.get("challengeState") or review.get("state") or ""
    ).strip().lower()
    review_state = str(review.get("reviewState") or "").strip().lower()
    open_alert_count = int(priority.get("openAlertCount") or 0)
    priority_level = str(priority.get("level") or "").strip().lower()

    if challenge_state in TRUST_CHALLENGE_OPEN_STATES:
        hints.append("trust.challenge.decide")
    if review_state == "pending_review":
        hints.append("review.queue.decide")
    if open_alert_count > 0:
        hints.append("alerts.resolve_open")
    if priority_level == "high":
        hints.append("ops.escalate_priority")
    if not hints:
        hints.append("monitor")
    return hints


def _build_review_trust_unified_priority_profile(
    *,
    risk_profile: dict[str, Any],
    trust_priority_profile: dict[str, Any],
    challenge_review: dict[str, Any],
) -> dict[str, Any]:
    risk = risk_profile if isinstance(risk_profile, dict) else {}
    trust = trust_priority_profile if isinstance(trust_priority_profile, dict) else {}
    review = challenge_review if isinstance(challenge_review, dict) else {}
    risk_score = int(risk.get("score") or 0)
    trust_score = int(trust.get("score") or 0)
    challenge_state = str(
        review.get("challengeState") or trust.get("challengeState") or ""
    ).strip().lower()
    review_state = str(
        review.get("reviewState") or trust.get("reviewState") or ""
    ).strip().lower()
    try:
        total_challenges = int(
            review.get("totalChallenges")
            if review.get("totalChallenges") is not None
            else trust.get("totalChallenges")
        )
    except (TypeError, ValueError):
        total_challenges = 0
    open_alert_count = int(trust.get("openAlertCount") or 0)

    score = int(round(risk_score * 0.65 + trust_score * 0.35))
    tags: list[str] = []
    for source in (
        risk.get("tags") if isinstance(risk.get("tags"), list) else [],
        trust.get("tags") if isinstance(trust.get("tags"), list) else [],
    ):
        for token in source:
            text = str(token).strip()
            if text and text not in tags:
                tags.append(text)
    if challenge_state in TRUST_CHALLENGE_OPEN_STATES:
        score += 10
        if "open_challenge" not in tags:
            tags.append("open_challenge")
    if review_state == "pending_review":
        score += 5
        if "pending_review" not in tags:
            tags.append("pending_review")
    if total_challenges >= 2:
        score += min(8, (total_challenges - 1) * 2)
        if "multi_challenge_case" not in tags:
            tags.append("multi_challenge_case")
    score = max(0, min(score, 100))

    if score >= 75:
        level = "high"
    elif score >= 45:
        level = "medium"
    else:
        level = "low"

    bucket_rank = {"unknown": 0, "normal": 1, "warning": 2, "urgent": 3}
    risk_bucket = str(risk.get("slaBucket") or "").strip().lower() or "unknown"
    trust_bucket = str(trust.get("slaBucket") or "").strip().lower() or "unknown"
    if risk_bucket not in bucket_rank:
        risk_bucket = "unknown"
    if trust_bucket not in bucket_rank:
        trust_bucket = "unknown"
    merged_rank = max(bucket_rank.get(risk_bucket, 0), bucket_rank.get(trust_bucket, 0))
    merged_bucket = next(
        (key for key, value in bucket_rank.items() if value == merged_rank),
        "unknown",
    )

    return {
        "score": score,
        "level": level,
        "tags": tags,
        "slaBucket": merged_bucket,
        "riskScore": risk_score,
        "riskLevel": str(risk.get("level") or "").strip().lower() or None,
        "trustScore": trust_score,
        "trustLevel": str(trust.get("level") or "").strip().lower() or None,
        "challengeState": challenge_state or None,
        "reviewState": review_state or None,
        "totalChallenges": max(0, total_challenges),
        "openAlertCount": max(0, open_alert_count),
    }


def _normalize_review_case_risk_level(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    return normalized


def _normalize_review_case_sla_bucket(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    return normalized


def _normalize_review_case_sort_by(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "updated_at"
    return normalized


def _normalize_review_case_sort_order(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "desc"
    return normalized


def _build_review_case_risk_profile(
    *,
    workflow: WorkflowJob,
    report_payload: dict[str, Any],
    report_summary: dict[str, Any],
    now: datetime,
) -> dict[str, Any]:
    payload = report_payload if isinstance(report_payload, dict) else {}
    summary = report_summary if isinstance(report_summary, dict) else {}
    fairness_summary = (
        payload.get("fairnessSummary")
        if isinstance(payload.get("fairnessSummary"), dict)
        else {}
    )
    error_codes = [
        str(item).strip()
        for item in (payload.get("errorCodes") or [])
        if str(item).strip()
    ]
    audit_alerts = summary.get("auditAlerts") if isinstance(summary.get("auditAlerts"), list) else []
    audit_alert_count = len(audit_alerts)
    callback_status = str(summary.get("callbackStatus") or "").strip().lower()
    winner = str(payload.get("winner") or "").strip().lower()
    panel_high_disagreement = bool(fairness_summary.get("panelHighDisagreement"))
    review_required = bool(payload.get("reviewRequired"))

    age_minutes: int | None = None
    if isinstance(workflow.updated_at, datetime):
        updated_at = _normalize_query_datetime(workflow.updated_at)
        if updated_at is not None:
            age_delta = now - updated_at
            age_minutes = max(0, int(age_delta.total_seconds() // 60))

    risk_score = 0
    risk_tags: list[str] = []

    if review_required:
        risk_score += 35
        risk_tags.append("review_required")
    if panel_high_disagreement:
        risk_score += 20
        risk_tags.append("panel_high_disagreement")
    if error_codes:
        risk_score += min(25, len(error_codes) * 8)
        risk_tags.append("error_codes_present")
    if audit_alert_count > 0:
        risk_score += min(20, audit_alert_count * 4)
        risk_tags.append("audit_alerts_present")
    if callback_status in {"failed", "error", "callback_failed"}:
        risk_score += 15
        risk_tags.append("callback_failed")
    if winner == "draw":
        risk_score += 5
        risk_tags.append("draw_outcome")

    if age_minutes is not None and age_minutes >= 360:
        risk_score += 15
        risk_tags.append("review_stale_6h")
    elif age_minutes is not None and age_minutes >= 120:
        risk_score += 8
        risk_tags.append("review_stale_2h")

    risk_score = max(0, min(int(risk_score), 100))
    if risk_score >= 75:
        risk_level = "high"
    elif risk_score >= 45:
        risk_level = "medium"
    else:
        risk_level = "low"

    if age_minutes is None:
        sla_bucket = "unknown"
    elif age_minutes >= 360:
        sla_bucket = "urgent"
    elif age_minutes >= 120:
        sla_bucket = "warning"
    else:
        sla_bucket = "normal"

    return {
        "score": risk_score,
        "level": risk_level,
        "tags": risk_tags,
        "ageMinutes": age_minutes,
        "slaBucket": sla_bucket,
        "auditAlertCount": audit_alert_count,
        "panelHighDisagreement": panel_high_disagreement,
        "reviewRequired": review_required,
    }


def _build_review_case_sort_key(*, item: dict[str, Any], sort_by: str) -> tuple[Any, ...]:
    risk = item.get("riskProfile") if isinstance(item.get("riskProfile"), dict) else {}
    unified = (
        item.get("unifiedPriorityProfile")
        if isinstance(item.get("unifiedPriorityProfile"), dict)
        else {}
    )
    workflow = item.get("workflow") if isinstance(item.get("workflow"), dict) else {}
    if sort_by == "unified_priority_score":
        return (
            int(unified.get("score") or 0),
            int(risk.get("score") or 0),
            str(workflow.get("updatedAt") or "").strip(),
            int(workflow.get("caseId") or 0),
        )
    if sort_by == "risk_score":
        return (
            int(risk.get("score") or 0),
            str(workflow.get("updatedAt") or "").strip(),
            int(workflow.get("caseId") or 0),
        )
    if sort_by == "audit_alert_count":
        return (
            int(risk.get("auditAlertCount") or 0),
            int(risk.get("score") or 0),
            int(workflow.get("caseId") or 0),
        )
    if sort_by == "case_id":
        return (int(workflow.get("caseId") or 0),)
    return (
        str(workflow.get("updatedAt") or "").strip(),
        int(risk.get("score") or 0),
        int(workflow.get("caseId") or 0),
    )


def _normalize_case_fairness_gate_conclusion(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    return normalized or None


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
    shadow_breach_count = 0
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

        shadow = item.get("shadowSummary") if isinstance(item.get("shadowSummary"), dict) else {}
        if bool(shadow.get("hasShadowBreach")):
            shadow_breach_count += 1

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
        "shadowBreachCount": shadow_breach_count,
        "panelHighDisagreementCount": panel_high_disagreement_count,
        "withChallengeCount": with_challenge_count,
        "gateConclusionCounts": gate_counts,
        "winnerCounts": winner_counts,
        "challengeStateCounts": dict(sorted(challenge_state_counts.items(), key=lambda kv: kv[0])),
        "policyVersionCounts": dict(sorted(policy_version_counts.items(), key=lambda kv: kv[0])),
    }


def _parse_iso_datetime(value: Any) -> datetime | None:
    token = str(value or "").strip()
    if not token:
        return None
    normalized = token.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _build_fairness_dashboard_case_trends(
    *,
    items: list[dict[str, Any]],
    window_days: int,
) -> list[dict[str, Any]]:
    return build_fairness_dashboard_case_trends_v3(
        items=items,
        window_days=window_days,
    )


def _build_fairness_dashboard_run_trends(
    *,
    benchmark_runs: list[FactFairnessBenchmarkRun],
    shadow_runs: list[FactFairnessShadowRun],
    window_days: int,
) -> dict[str, Any]:
    return build_fairness_dashboard_run_trends_v3(
        benchmark_runs=benchmark_runs,
        shadow_runs=shadow_runs,
        window_days=window_days,
    )


def _build_fairness_dashboard_top_risk_cases(
    *,
    items: list[dict[str, Any]],
    top_limit: int,
) -> list[dict[str, Any]]:
    return build_fairness_dashboard_top_risk_cases_v3(
        items=items,
        top_limit=top_limit,
    )


def _optional_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _pick_threshold_value(payload: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key not in payload:
            continue
        parsed = _optional_float(payload.get(key))
        if parsed is not None:
            return parsed
    return None


def _suggest_max_threshold(
    values: list[float],
    *,
    margin_ratio: float = 0.1,
    floor: float = 0.0,
    cap: float | None = 1.0,
) -> float | None:
    if not values:
        return None
    baseline = max(values)
    suggested = max(float(floor), baseline * (1.0 + max(0.0, float(margin_ratio))))
    if cap is not None:
        suggested = min(float(cap), suggested)
    return round(suggested, 4)


def _suggest_sample_size_floor(values: list[int], *, floor: int = 100) -> int | None:
    normalized = [item for item in values if item > 0]
    if not normalized:
        return None
    normalized.sort()
    median = normalized[len(normalized) // 2]
    return max(int(floor), int(median))


def _build_fairness_calibration_threshold_suggestions(
    *,
    benchmark_runs: list[FactFairnessBenchmarkRun],
    shadow_runs: list[FactFairnessShadowRun],
) -> dict[str, Any]:
    return build_fairness_calibration_threshold_suggestions_v3(
        benchmark_runs=benchmark_runs,
        shadow_runs=shadow_runs,
    )


def _build_fairness_calibration_drift_summary(
    *,
    latest_benchmark_run: FactFairnessBenchmarkRun | None,
    latest_shadow_run: FactFairnessShadowRun | None,
) -> dict[str, Any]:
    return build_fairness_calibration_drift_summary_v3(
        latest_benchmark_run=latest_benchmark_run,
        latest_shadow_run=latest_shadow_run,
    )


def _build_fairness_calibration_risk_items(
    *,
    benchmark_runs: list[FactFairnessBenchmarkRun],
    shadow_runs: list[FactFairnessShadowRun],
    top_risk_cases: list[dict[str, Any]],
    risk_limit: int,
) -> list[dict[str, Any]]:
    return build_fairness_calibration_risk_items_v3(
        benchmark_runs=benchmark_runs,
        shadow_runs=shadow_runs,
        top_risk_cases=top_risk_cases,
        risk_limit=risk_limit,
    )


def _build_fairness_calibration_on_env_input_template() -> dict[str, Any]:
    return {
        "envMarker": {
            "REAL_CALIBRATION_ENV_READY": "true",
            "CALIBRATION_ENV_MODE": "real",
        },
        "fairnessBenchmarkTrackRequiredKeys": [
            "CALIBRATION_STATUS",
            "WINDOW_FROM",
            "WINDOW_TO",
            "SAMPLE_SIZE",
            "DRAW_RATE",
            "SIDE_BIAS_DELTA",
            "APPEAL_OVERTURN_RATE",
        ],
        "shadowRunPayloadRequiredKeys": [
            "run_id",
            "policy_version",
            "benchmark_run_id",
            "environment_mode",
            "status",
            "threshold_decision",
            "metrics.sample_size",
            "metrics.winner_flip_rate",
            "metrics.score_shift_delta",
            "metrics.review_required_delta",
        ],
        "recommendedCommands": [
            "bash scripts/harness/ai_judge_p5_real_calibration_on_env.sh",
            "bash scripts/harness/ai_judge_fairness_benchmark_freeze.sh",
            "bash scripts/harness/ai_judge_runtime_ops_pack.sh",
            "bash scripts/harness/ai_judge_real_env_window_closure.sh",
        ],
        "notes": [
            (
                "local calibration pack is for threshold suggestions and risk scanning "
                "only; it does not represent real-env pass."
            ),
            (
                "when entering the real-env window, provide real markers and full "
                "five-track calibration evidence."
            ),
        ],
    }


def _build_fairness_policy_calibration_recommended_actions(
    *,
    release_gate: dict[str, Any],
    policy_version: str | None,
    risk_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    seen_action_ids: set[str] = set()

    gate_code = str(release_gate.get("code") or "").strip()
    gate_passed = bool(release_gate.get("passed"))
    benchmark_gate_passed = bool(release_gate.get("benchmarkGatePassed"))
    shadow_gate_applied = bool(release_gate.get("shadowGateApplied"))
    shadow_gate_passed = release_gate.get("shadowGatePassed")
    high_risk_count = sum(
        1
        for item in risk_items
        if isinstance(item, dict)
        and str(item.get("severity") or "").strip().lower() == "high"
    )

    def _append_action(
        *,
        action_id: str,
        priority: str,
        reason_code: str,
        description: str,
        blocking: bool,
    ) -> None:
        normalized_action_id = str(action_id or "").strip()
        if not normalized_action_id or normalized_action_id in seen_action_ids:
            return
        seen_action_ids.add(normalized_action_id)
        actions.append(
            {
                "actionId": normalized_action_id,
                "priority": str(priority or "").strip().lower() or "medium",
                "reasonCode": str(reason_code or "").strip() or None,
                "description": str(description or "").strip(),
                "blocking": bool(blocking),
                "advisoryOnly": True,
                "policyVersion": policy_version,
            }
        )

    if not policy_version:
        _append_action(
            action_id="select_policy_version_context",
            priority="high",
            reason_code="no_policy_version_context",
            description=(
                "provide policy_version in query or upload benchmark/shadow runs "
                "before using calibration advisor."
            ),
            blocking=True,
        )
        return actions

    if gate_code == "registry_fairness_gate_no_benchmark":
        _append_action(
            action_id="run_benchmark_first",
            priority="high",
            reason_code=gate_code,
            description=(
                "no benchmark evidence found for this policy version; run a benchmark "
                "window before publish/activate."
            ),
            blocking=True,
        )
    elif gate_code in {
        "registry_fairness_gate_threshold_not_accepted",
        "registry_fairness_gate_remediation_required",
        "registry_fairness_gate_status_not_ready",
    }:
        _append_action(
            action_id="rerun_benchmark_with_remediation",
            priority="high",
            reason_code=gate_code,
            description=(
                "latest benchmark does not meet release gate; patch policy/prompts/tools "
                "and rerun benchmark."
            ),
            blocking=True,
        )

    if benchmark_gate_passed and not shadow_gate_applied:
        _append_action(
            action_id="run_shadow_evaluation",
            priority="high",
            reason_code="shadow_required_after_benchmark_pass",
            description=(
                "benchmark passed and shadow evidence is missing; run shadow evaluation "
                "to check winner-flip and score-shift risks."
            ),
            blocking=True,
        )

    if shadow_gate_applied and shadow_gate_passed is False:
        _append_action(
            action_id="prepare_candidate_policy_patch",
            priority="high",
            reason_code=gate_code or "shadow_gate_blocked",
            description=(
                "shadow gate is blocked; prepare candidate policy patch and rerun "
                "shadow with the same benchmark baseline."
            ),
            blocking=True,
        )
        _append_action(
            action_id="manual_review_before_activation",
            priority="high",
            reason_code="activation_requires_manual_review",
            description=(
                "activation should stay blocked until shadow breaches are resolved "
                "or a governance override is explicitly approved."
            ),
            blocking=True,
        )

    if gate_passed:
        _append_action(
            action_id="publish_candidate_policy",
            priority="medium",
            reason_code="registry_fairness_gate_passed",
            description=(
                "fairness gate is currently passing; candidate policy can be published "
                "through registry governance flow."
            ),
            blocking=False,
        )
        _append_action(
            action_id="activate_candidate_policy",
            priority="low",
            reason_code="registry_fairness_gate_passed",
            description=(
                "after publish and governance review, policy activation can proceed "
                "without fairness override."
            ),
            blocking=False,
        )

    if high_risk_count > 0 and not gate_passed:
        _append_action(
            action_id="triage_high_risk_cases",
            priority="medium",
            reason_code="high_risk_cases_present",
            description=(
                f"{high_risk_count} high-severity risk items detected; review top cases "
                "for targeted remediation before next calibration run."
            ),
            blocking=False,
        )

    if not actions:
        _append_action(
            action_id="monitor_next_calibration_window",
            priority="low",
            reason_code=gate_code or "gate_status_unknown",
            description=(
                "no immediate blocking suggestion detected; continue monitoring fairness "
                "runs and keep calibration evidence fresh."
            ),
            blocking=False,
        )
    return actions


def _normalize_panel_runtime_profile_source(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    return normalized


def _normalize_panel_runtime_profile_sort_by(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "updated_at"
    return normalized


def _normalize_panel_runtime_profile_sort_order(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "desc"
    return normalized


def _build_panel_runtime_profile_item(
    *,
    case_item: dict[str, Any],
    judge_id: str,
    runtime_profile: dict[str, Any],
) -> dict[str, Any]:
    panel = (
        case_item.get("panelDisagreement")
        if isinstance(case_item.get("panelDisagreement"), dict)
        else {}
    )
    challenge_link = (
        case_item.get("challengeLink")
        if isinstance(case_item.get("challengeLink"), dict)
        else {}
    )
    latest_challenge = (
        challenge_link.get("latest")
        if isinstance(challenge_link.get("latest"), dict)
        else {}
    )
    drift_summary = (
        case_item.get("driftSummary")
        if isinstance(case_item.get("driftSummary"), dict)
        else {}
    )

    profile_source = (
        str(runtime_profile.get("profileSource") or "").strip().lower() or "unknown"
    )
    profile_id = str(runtime_profile.get("profileId") or "").strip() or None
    model_strategy = str(runtime_profile.get("modelStrategy") or "").strip() or None
    score_source = str(runtime_profile.get("scoreSource") or "").strip() or None
    strategy_slot = str(runtime_profile.get("strategySlot") or "").strip() or None
    prompt_version = str(runtime_profile.get("promptVersion") or "").strip() or None
    toolset_version = str(runtime_profile.get("toolsetVersion") or "").strip() or None
    domain_slot = str(runtime_profile.get("domainSlot") or "").strip() or None
    runtime_stage = str(runtime_profile.get("runtimeStage") or "").strip() or None
    candidate_models = (
        [str(item).strip() for item in runtime_profile.get("candidateModels", []) if str(item).strip()]
        if isinstance(runtime_profile.get("candidateModels"), list)
        else []
    )
    strategy_metadata = (
        dict(runtime_profile.get("strategyMetadata"))
        if isinstance(runtime_profile.get("strategyMetadata"), dict)
        else {}
    )
    policy_version = (
        str(runtime_profile.get("policyVersion") or "").strip()
        or str(drift_summary.get("policyVersion") or "").strip()
        or None
    )

    return {
        "caseId": int(case_item.get("caseId") or 0),
        "traceId": str(case_item.get("traceId") or "").strip() or None,
        "dispatchType": str(case_item.get("dispatchType") or "").strip() or None,
        "workflowStatus": str(case_item.get("workflowStatus") or "").strip() or None,
        "updatedAt": str(case_item.get("updatedAt") or "").strip() or None,
        "winner": str(case_item.get("winner") or "").strip().lower() or None,
        "gateConclusion": str(case_item.get("gateConclusion") or "").strip().lower() or None,
        "reviewRequired": bool(case_item.get("reviewRequired")),
        "hasOpenReview": bool(challenge_link.get("hasOpenReview")),
        "challengeState": str(latest_challenge.get("state") or "").strip() or None,
        "panelDisagreement": {
            "high": bool(panel.get("high")),
            "ratio": _safe_float(panel.get("ratio"), default=0.0),
            "ratioMax": _safe_float(panel.get("ratioMax"), default=0.0),
            "reasons": [
                str(item).strip()
                for item in (panel.get("reasons") or [])
                if str(item).strip()
            ],
            "majorityWinner": str(panel.get("majorityWinner") or "").strip().lower() or None,
            "voteBySide": (
                panel.get("voteBySide")
                if isinstance(panel.get("voteBySide"), dict)
                else {}
            ),
        },
        "judgeId": judge_id,
        "profileId": profile_id,
        "profileSource": profile_source,
        "modelStrategy": model_strategy,
        "strategySlot": strategy_slot,
        "scoreSource": score_source,
        "decisionMargin": _safe_float(runtime_profile.get("decisionMargin"), default=0.0),
        "promptVersion": prompt_version,
        "toolsetVersion": toolset_version,
        "domainSlot": domain_slot,
        "runtimeStage": runtime_stage,
        "adaptiveEnabled": bool(runtime_profile.get("adaptiveEnabled")),
        "candidateModels": candidate_models,
        "strategyMetadata": strategy_metadata,
        "policyVersion": policy_version,
        "runtimeProfile": dict(runtime_profile),
    }


def _build_panel_runtime_profile_sort_key(
    *,
    item: dict[str, Any],
    sort_by: str,
) -> tuple[Any, ...]:
    if sort_by == "panel_disagreement_ratio":
        panel = (
            item.get("panelDisagreement")
            if isinstance(item.get("panelDisagreement"), dict)
            else {}
        )
        return (
            _safe_float(panel.get("ratio"), default=0.0),
            int(item.get("caseId") or 0),
            str(item.get("judgeId") or ""),
        )
    if sort_by == "case_id":
        return (
            int(item.get("caseId") or 0),
            str(item.get("judgeId") or ""),
        )
    if sort_by == "judge_id":
        return (
            str(item.get("judgeId") or ""),
            int(item.get("caseId") or 0),
        )
    if sort_by == "profile_id":
        return (
            str(item.get("profileId") or ""),
            int(item.get("caseId") or 0),
            str(item.get("judgeId") or ""),
        )
    if sort_by == "model_strategy":
        return (
            str(item.get("modelStrategy") or ""),
            int(item.get("caseId") or 0),
            str(item.get("judgeId") or ""),
        )
    if sort_by == "strategy_slot":
        return (
            str(item.get("strategySlot") or ""),
            int(item.get("caseId") or 0),
            str(item.get("judgeId") or ""),
        )
    if sort_by == "domain_slot":
        return (
            str(item.get("domainSlot") or ""),
            int(item.get("caseId") or 0),
            str(item.get("judgeId") or ""),
        )
    return (
        str(item.get("updatedAt") or "").strip(),
        int(item.get("caseId") or 0),
        str(item.get("judgeId") or ""),
    )


def _build_panel_runtime_profile_aggregations(items: list[dict[str, Any]]) -> dict[str, Any]:
    judge_counts: dict[str, int] = {}
    profile_id_counts: dict[str, int] = {"unknown": 0}
    model_strategy_counts: dict[str, int] = {"unknown": 0}
    strategy_slot_counts: dict[str, int] = {"unknown": 0}
    domain_slot_counts: dict[str, int] = {"unknown": 0}
    profile_source_counts: dict[str, int] = {"unknown": 0}
    policy_version_counts: dict[str, int] = {"unknown": 0}
    winner_counts: dict[str, int] = {
        "pro": 0,
        "con": 0,
        "draw": 0,
        "unknown": 0,
    }
    review_required_count = 0
    open_review_count = 0
    panel_high_disagreement_count = 0
    disagreement_ratio_sum = 0.0

    for item in items:
        judge_id = str(item.get("judgeId") or "").strip() or "unknown"
        judge_counts[judge_id] = judge_counts.get(judge_id, 0) + 1

        profile_id = str(item.get("profileId") or "").strip()
        if profile_id:
            profile_id_counts[profile_id] = profile_id_counts.get(profile_id, 0) + 1
        else:
            profile_id_counts["unknown"] += 1

        model_strategy = str(item.get("modelStrategy") or "").strip()
        if model_strategy:
            model_strategy_counts[model_strategy] = model_strategy_counts.get(model_strategy, 0) + 1
        else:
            model_strategy_counts["unknown"] += 1

        strategy_slot = str(item.get("strategySlot") or "").strip()
        if strategy_slot:
            strategy_slot_counts[strategy_slot] = strategy_slot_counts.get(strategy_slot, 0) + 1
        else:
            strategy_slot_counts["unknown"] += 1

        domain_slot = str(item.get("domainSlot") or "").strip()
        if domain_slot:
            domain_slot_counts[domain_slot] = domain_slot_counts.get(domain_slot, 0) + 1
        else:
            domain_slot_counts["unknown"] += 1

        profile_source = str(item.get("profileSource") or "").strip().lower()
        if profile_source:
            profile_source_counts[profile_source] = profile_source_counts.get(profile_source, 0) + 1
        else:
            profile_source_counts["unknown"] += 1

        policy_version = str(item.get("policyVersion") or "").strip()
        if policy_version:
            policy_version_counts[policy_version] = policy_version_counts.get(policy_version, 0) + 1
        else:
            policy_version_counts["unknown"] += 1

        winner = str(item.get("winner") or "").strip().lower()
        if winner in winner_counts:
            winner_counts[winner] += 1
        else:
            winner_counts["unknown"] += 1

        if bool(item.get("reviewRequired")):
            review_required_count += 1
        if bool(item.get("hasOpenReview")):
            open_review_count += 1
        panel = (
            item.get("panelDisagreement")
            if isinstance(item.get("panelDisagreement"), dict)
            else {}
        )
        if bool(panel.get("high")):
            panel_high_disagreement_count += 1
        disagreement_ratio_sum += _safe_float(panel.get("ratio"), default=0.0)

    total_matched = len(items)
    return {
        "totalMatched": total_matched,
        "reviewRequiredCount": review_required_count,
        "openReviewCount": open_review_count,
        "panelHighDisagreementCount": panel_high_disagreement_count,
        "avgPanelDisagreementRatio": (
            disagreement_ratio_sum / total_matched if total_matched > 0 else 0.0
        ),
        "byJudgeId": dict(sorted(judge_counts.items(), key=lambda kv: kv[0])),
        "byProfileId": dict(sorted(profile_id_counts.items(), key=lambda kv: kv[0])),
        "byModelStrategy": dict(sorted(model_strategy_counts.items(), key=lambda kv: kv[0])),
        "byStrategySlot": dict(sorted(strategy_slot_counts.items(), key=lambda kv: kv[0])),
        "byDomainSlot": dict(sorted(domain_slot_counts.items(), key=lambda kv: kv[0])),
        "byProfileSource": dict(sorted(profile_source_counts.items(), key=lambda kv: kv[0])),
        "byPolicyVersion": dict(sorted(policy_version_counts.items(), key=lambda kv: kv[0])),
        "winnerCounts": winner_counts,
    }


def _build_panel_runtime_readiness_summary(
    *,
    items: list[dict[str, Any]],
    group_limit: int,
    attention_limit: int,
) -> dict[str, Any]:
    grouped: dict[str, dict[str, Any]] = {}
    for item in items:
        strategy_slot = str(item.get("strategySlot") or "").strip() or "unknown"
        domain_slot = str(item.get("domainSlot") or "").strip() or "unknown"
        model_strategy = str(item.get("modelStrategy") or "").strip() or "unknown"
        profile_id = str(item.get("profileId") or "").strip() or "unknown"
        policy_version = str(item.get("policyVersion") or "").strip() or "unknown"
        group_key = (
            f"{strategy_slot}|{domain_slot}|{model_strategy}|{profile_id}|{policy_version}"
        )

        row = grouped.setdefault(
            group_key,
            {
                "groupKey": group_key,
                "strategySlot": strategy_slot,
                "domainSlot": domain_slot,
                "modelStrategy": model_strategy,
                "profileId": profile_id,
                "policyVersion": policy_version,
                "recordCount": 0,
                "caseIds": set(),
                "judgeIds": set(),
                "profileSources": set(),
                "candidateModels": set(),
                "adaptiveEnabledCount": 0,
                "reviewRequiredCount": 0,
                "openReviewCount": 0,
                "panelHighDisagreementCount": 0,
                "panelDisagreementRatioSum": 0.0,
            },
        )
        row["recordCount"] += 1
        case_id = int(item.get("caseId") or 0)
        if case_id > 0:
            row["caseIds"].add(case_id)
        judge_id = str(item.get("judgeId") or "").strip()
        if judge_id:
            row["judgeIds"].add(judge_id)
        source = str(item.get("profileSource") or "").strip().lower()
        if source:
            row["profileSources"].add(source)
        if bool(item.get("adaptiveEnabled")):
            row["adaptiveEnabledCount"] += 1
        if bool(item.get("reviewRequired")):
            row["reviewRequiredCount"] += 1
        if bool(item.get("hasOpenReview")):
            row["openReviewCount"] += 1
        panel = (
            item.get("panelDisagreement")
            if isinstance(item.get("panelDisagreement"), dict)
            else {}
        )
        if bool(panel.get("high")):
            row["panelHighDisagreementCount"] += 1
        row["panelDisagreementRatioSum"] += _safe_float(panel.get("ratio"), default=0.0)
        for candidate_model in item.get("candidateModels") or []:
            candidate_model_token = str(candidate_model).strip()
            if candidate_model_token:
                row["candidateModels"].add(candidate_model_token)

    group_rows: list[dict[str, Any]] = []
    for row in grouped.values():
        record_count = int(row["recordCount"])
        panel_high_count = int(row["panelHighDisagreementCount"])
        review_required_count = int(row["reviewRequiredCount"])
        open_review_count = int(row["openReviewCount"])
        candidate_models = sorted(str(item) for item in row["candidateModels"])
        panel_high_rate = panel_high_count / record_count if record_count > 0 else 0.0
        review_required_rate = (
            review_required_count / record_count if record_count > 0 else 0.0
        )
        open_review_rate = open_review_count / record_count if record_count > 0 else 0.0
        avg_disagreement_ratio = (
            float(row["panelDisagreementRatioSum"]) / record_count
            if record_count > 0
            else 0.0
        )
        adaptive_enabled_rate = (
            int(row["adaptiveEnabledCount"]) / record_count if record_count > 0 else 0.0
        )
        readiness_score = max(
            0.0,
            min(
                100.0,
                100.0
                - panel_high_rate * 60.0
                - review_required_rate * 30.0
                - open_review_rate * 10.0,
            ),
        )

        if readiness_score < 60.0:
            readiness_level = "attention"
        elif readiness_score < 80.0:
            readiness_level = "watch"
        else:
            readiness_level = "ready"

        switch_conditions: list[str] = []
        if panel_high_rate >= 0.2:
            switch_conditions.append("panel_disagreement_ratio_high")
        if review_required_rate >= 0.2:
            switch_conditions.append("review_required_rate_high")
        if open_review_rate >= 0.1:
            switch_conditions.append("open_review_backlog")
        if not candidate_models:
            switch_conditions.append("candidate_models_missing")
        if not switch_conditions:
            switch_conditions.append("stable_runtime")

        simulations: list[dict[str, Any]] = []
        if len(candidate_models) >= 2 and readiness_level != "ready":
            simulations.append(
                {
                    "scenarioId": "switch_to_secondary_candidate",
                    "trigger": switch_conditions[0],
                    "candidateModel": candidate_models[1],
                    "expectedImpact": "reduce disagreement and review pressure",
                    "advisoryOnly": True,
                }
            )
        else:
            simulations.append(
                {
                    "scenarioId": "keep_current_strategy",
                    "trigger": switch_conditions[0],
                    "candidateModel": candidate_models[0] if candidate_models else None,
                    "expectedImpact": "maintain current runtime strategy and monitor drift",
                    "advisoryOnly": True,
                }
            )

        group_rows.append(
            {
                "groupKey": row["groupKey"],
                "strategySlot": row["strategySlot"],
                "domainSlot": row["domainSlot"],
                "modelStrategy": row["modelStrategy"],
                "profileId": row["profileId"],
                "policyVersion": row["policyVersion"],
                "recordCount": record_count,
                "caseCount": len(row["caseIds"]),
                "judgeIds": sorted(str(item) for item in row["judgeIds"]),
                "profileSources": sorted(str(item) for item in row["profileSources"]),
                "candidateModels": candidate_models,
                "candidateModelCount": len(candidate_models),
                "adaptiveEnabledRate": round(adaptive_enabled_rate, 4),
                "panelHighDisagreementCount": panel_high_count,
                "panelHighDisagreementRate": round(panel_high_rate, 4),
                "reviewRequiredCount": review_required_count,
                "reviewRequiredRate": round(review_required_rate, 4),
                "openReviewCount": open_review_count,
                "openReviewRate": round(open_review_rate, 4),
                "avgPanelDisagreementRatio": round(avg_disagreement_ratio, 4),
                "readinessScore": round(readiness_score, 2),
                "readinessLevel": readiness_level,
                "recommendedSwitchConditions": switch_conditions,
                "simulations": simulations,
            }
        )

    group_rows.sort(
        key=lambda row: (
            float(row.get("readinessScore") or 0.0),
            float(row.get("panelHighDisagreementRate") or 0.0),
            float(row.get("reviewRequiredRate") or 0.0),
            str(row.get("groupKey") or ""),
        ),
    )
    limited_group_rows = group_rows[: max(1, min(int(group_limit), 200))]
    attention_rows = [
        row for row in limited_group_rows if str(row.get("readinessLevel")) != "ready"
    ][: max(1, min(int(attention_limit), 100))]

    readiness_counts = {
        "ready": 0,
        "watch": 0,
        "attention": 0,
    }
    for row in limited_group_rows:
        level = str(row.get("readinessLevel") or "").strip().lower()
        if level in readiness_counts:
            readiness_counts[level] += 1

    return {
        "groups": limited_group_rows,
        "attentionGroups": attention_rows,
        "overview": {
            "totalRecords": len(items),
            "totalGroups": len(limited_group_rows),
            "readinessCounts": readiness_counts,
            "attentionGroupCount": len(attention_rows),
        },
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
        policy_kernel = (
            item.get("policyKernel")
            if isinstance(item.get("policyKernel"), dict)
            else {}
        )
        row = by_policy_version.setdefault(
            version,
            {
                "policyVersion": version,
                "dependencyOk": bool(item.get("ok")),
                "policyKernelVersion": (
                    str(policy_kernel.get("version") or "").strip() or None
                ),
                "policyKernelHash": (
                    str(policy_kernel.get("kernelHash") or "").strip() or None
                ),
                "totalAlerts": 0,
                "openBlockedCount": 0,
                "resolvedCount": 0,
                "recentChanges": 0,
                "lastStatus": None,
                "lastUpdatedAt": None,
                "latestGateDecision": None,
                "latestGateCode": None,
                "latestGateSource": None,
                "overrideApplied": None,
                "overrideActor": None,
                "overrideReason": None,
                "gateUpdatedAt": None,
                "_latestUpdatedAt": None,
                "_latestGateUpdatedAt": None,
            },
        )
        row["dependencyOk"] = bool(item.get("ok"))
        if row.get("policyKernelVersion") is None:
            row["policyKernelVersion"] = (
                str(policy_kernel.get("version") or "").strip() or None
            )
        if row.get("policyKernelHash") is None:
            row["policyKernelHash"] = (
                str(policy_kernel.get("kernelHash") or "").strip() or None
            )

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
                "policyKernelVersion": None,
                "policyKernelHash": None,
                "totalAlerts": 0,
                "openBlockedCount": 0,
                "resolvedCount": 0,
                "recentChanges": 0,
                "lastStatus": None,
                "lastUpdatedAt": None,
                "latestGateDecision": None,
                "latestGateCode": None,
                "latestGateSource": None,
                "overrideApplied": None,
                "overrideActor": None,
                "overrideReason": None,
                "gateUpdatedAt": None,
                "_latestUpdatedAt": None,
                "_latestGateUpdatedAt": None,
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

    gate_decision_counts = {
        "blocked": 0,
        "override_activated": 0,
        "pass": 0,
    }
    for alert in alerts:
        alert_type = str(getattr(alert, "alert_type", "") or "").strip()
        if alert_type not in {
            REGISTRY_FAIRNESS_ALERT_TYPE_BLOCKED,
            REGISTRY_FAIRNESS_ALERT_TYPE_OVERRIDE,
        }:
            continue
        details = (
            dict(getattr(alert, "details"))
            if isinstance(getattr(alert, "details", None), dict)
            else {}
        )
        if str(details.get("registryType") or "").strip().lower() != normalized_registry_type:
            continue
        version = str(details.get("version") or "").strip() or "unknown"
        gate_payload = details.get("gate") if isinstance(details.get("gate"), dict) else {}
        updated_at = _normalize_aware_datetime(
            getattr(alert, "updated_at", None)
        ) or _normalize_aware_datetime(getattr(alert, "created_at", None)) or now

        row = by_policy_version.setdefault(
            version,
            {
                "policyVersion": version,
                "dependencyOk": None,
                "policyKernelVersion": None,
                "policyKernelHash": None,
                "totalAlerts": 0,
                "openBlockedCount": 0,
                "resolvedCount": 0,
                "recentChanges": 0,
                "lastStatus": None,
                "lastUpdatedAt": None,
                "latestGateDecision": None,
                "latestGateCode": None,
                "latestGateSource": None,
                "overrideApplied": None,
                "overrideActor": None,
                "overrideReason": None,
                "gateUpdatedAt": None,
                "_latestUpdatedAt": None,
                "_latestGateUpdatedAt": None,
            },
        )
        override_applied = bool(details.get("overrideApplied"))
        if override_applied:
            gate_decision = "override_activated"
        elif bool(gate_payload.get("passed")):
            gate_decision = "pass"
        else:
            gate_decision = "blocked"
        gate_decision_counts[gate_decision] = gate_decision_counts.get(gate_decision, 0) + 1

        latest_gate_updated_at = row.get("_latestGateUpdatedAt")
        if (
            not isinstance(latest_gate_updated_at, datetime)
            or updated_at >= latest_gate_updated_at
        ):
            row["_latestGateUpdatedAt"] = updated_at
            row["latestGateDecision"] = gate_decision
            row["latestGateCode"] = str(gate_payload.get("code") or "").strip() or None
            row["latestGateSource"] = str(gate_payload.get("source") or "").strip() or None
            row["overrideApplied"] = override_applied
            row["overrideActor"] = str(details.get("actor") or "").strip() or None
            row["overrideReason"] = str(details.get("reason") or "").strip() or None
            row["gateUpdatedAt"] = updated_at.isoformat()

    version_rows = list(by_policy_version.values())
    for row in version_rows:
        row.pop("_latestUpdatedAt", None)
        row.pop("_latestGateUpdatedAt", None)
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
        "gateDecisionCounts": gate_decision_counts,
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


def _registry_prompt_tool_risk_severity_rank(value: str | None) -> int:
    normalized = str(value or "").strip().lower()
    return REGISTRY_PROMPT_TOOL_RISK_SEVERITY_RANK.get(normalized, 0)


def _build_registry_prompt_tool_usage_rows(
    *,
    usage_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    enriched_rows: list[dict[str, Any]] = []
    unreferenced_count = 0
    for row in usage_rows:
        if not isinstance(row, dict):
            continue
        try:
            ref_count = max(0, int(row.get("referencedByPolicyCount") or 0))
        except (TypeError, ValueError):
            ref_count = 0
        is_active = bool(row.get("isActive"))
        risk_tags: list[str] = []
        if ref_count <= 0:
            unreferenced_count += 1
            risk_tags.append("unreferenced")
        if is_active and ref_count <= 0:
            risk_tags.append("active_unreferenced")
        if ref_count <= 0 and is_active:
            risk_level = "medium"
        else:
            risk_level = "low"
        enriched = dict(row)
        enriched["riskLevel"] = risk_level
        enriched["riskTags"] = risk_tags
        enriched_rows.append(enriched)
    return enriched_rows, unreferenced_count


def _build_registry_prompt_tool_risk_items(
    *,
    dependency_items: list[dict[str, Any]],
    prompt_usage_rows: list[dict[str, Any]],
    tool_usage_rows: list[dict[str, Any]],
    missing_prompt_refs: list[str],
    missing_tool_refs: list[str],
    release_state: dict[str, Any],
) -> list[dict[str, Any]]:
    risk_items: list[dict[str, Any]] = []

    for item in dependency_items:
        if not isinstance(item, dict):
            continue
        if bool(item.get("ok")):
            continue
        policy_version = str(item.get("policyVersion") or "").strip() or None
        issue_codes = sorted(
            {
                str(code).strip()
                for code in (item.get("issueCodes") or [])
                if str(code).strip()
            }
        )
        detail_path = "/internal/judge/registries/policy/dependencies/health"
        if policy_version:
            detail_path = f"{detail_path}?policy_version={policy_version}"
        risk_items.append(
            {
                "riskType": "dependency_invalid",
                "severity": "high",
                "policyVersion": policy_version,
                "promptRegistryVersion": (
                    str(item.get("promptRegistryVersion") or "").strip() or None
                ),
                "toolRegistryVersion": (
                    str(item.get("toolRegistryVersion") or "").strip() or None
                ),
                "issueCodes": issue_codes,
                "reason": "policy release dependencies are invalid.",
                "detailPath": detail_path,
                "actionHint": "registry.policy.dependencies.fix",
            }
        )

    for version in sorted({str(row).strip() for row in missing_prompt_refs if str(row).strip()}):
        risk_items.append(
            {
                "riskType": "prompt_registry_ref_missing",
                "severity": "high",
                "promptRegistryVersion": version,
                "reason": "policy references a missing prompt registry version.",
                "detailPath": "/internal/judge/registries/prompts",
                "actionHint": "registry.prompt.curate",
            }
        )
    for version in sorted({str(row).strip() for row in missing_tool_refs if str(row).strip()}):
        risk_items.append(
            {
                "riskType": "tool_registry_ref_missing",
                "severity": "high",
                "toolRegistryVersion": version,
                "reason": "policy references a missing tool registry version.",
                "detailPath": "/internal/judge/registries/tools",
                "actionHint": "registry.tool.curate",
            }
        )

    for row in prompt_usage_rows:
        if not isinstance(row, dict):
            continue
        try:
            ref_count = max(0, int(row.get("referencedByPolicyCount") or 0))
        except (TypeError, ValueError):
            ref_count = 0
        if ref_count > 0:
            continue
        version = str(row.get("version") or "").strip() or None
        is_active = bool(row.get("isActive"))
        risk_items.append(
            {
                "riskType": "prompt_unreferenced",
                "severity": "medium" if is_active else "low",
                "promptRegistryVersion": version,
                "isActive": is_active,
                "reason": "prompt registry version is not referenced by any policy.",
                "detailPath": "/internal/judge/registries/prompts",
                "actionHint": "registry.prompt.curate",
            }
        )

    for row in tool_usage_rows:
        if not isinstance(row, dict):
            continue
        try:
            ref_count = max(0, int(row.get("referencedByPolicyCount") or 0))
        except (TypeError, ValueError):
            ref_count = 0
        if ref_count > 0:
            continue
        version = str(row.get("version") or "").strip() or None
        is_active = bool(row.get("isActive"))
        risk_items.append(
            {
                "riskType": "tool_unreferenced",
                "severity": "medium" if is_active else "low",
                "toolRegistryVersion": version,
                "isActive": is_active,
                "reason": "tool registry version is not referenced by any policy.",
                "detailPath": "/internal/judge/registries/tools",
                "actionHint": "registry.tool.curate",
            }
        )

    for registry_type in ("prompt", "tool"):
        state = (
            release_state.get(registry_type)
            if isinstance(release_state.get(registry_type), dict)
            else {}
        )
        try:
            release_count = max(0, int(state.get("count") or 0))
        except (TypeError, ValueError):
            release_count = 0
        if release_count > 0:
            continue
        risk_items.append(
            {
                "riskType": f"{registry_type}_release_missing",
                "severity": "high",
                "reason": (
                    f"{registry_type} registry has no release history and needs bootstrap."
                ),
                "detailPath": f"/internal/judge/registries/{registry_type}/releases",
                "actionHint": (
                    "registry.prompt.curate"
                    if registry_type == "prompt"
                    else "registry.tool.curate"
                ),
            }
        )

    risk_items.sort(
        key=lambda item: (
            -_registry_prompt_tool_risk_severity_rank(
                str(item.get("severity") or "").strip().lower()
            ),
            str(item.get("riskType") or ""),
            str(item.get("policyVersion") or ""),
            str(item.get("promptRegistryVersion") or ""),
            str(item.get("toolRegistryVersion") or ""),
        )
    )
    return risk_items


def _build_registry_prompt_tool_action_hints(
    *,
    risk_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    action_index: dict[str, dict[str, Any]] = {}

    def upsert_hint(
        *,
        action_id: str,
        path: str,
        reason: str,
        severity: str,
    ) -> None:
        rank = _registry_prompt_tool_risk_severity_rank(severity)
        current = action_index.get(action_id)
        if current is not None and int(current.get("_rank") or 0) >= rank:
            return
        action_index[action_id] = {
            "actionId": action_id,
            "path": path,
            "reason": reason,
            "severity": severity if severity in {"high", "medium", "low"} else "low",
            "_rank": rank,
        }

    for item in risk_items:
        if not isinstance(item, dict):
            continue
        risk_type = str(item.get("riskType") or "").strip().lower()
        severity = str(item.get("severity") or "").strip().lower() or "low"

        if risk_type in {
            "dependency_invalid",
            "prompt_registry_ref_missing",
            "tool_registry_ref_missing",
        }:
            upsert_hint(
                action_id="registry.policy.dependencies.fix",
                path="/internal/judge/registries/policy/dependencies/health",
                reason="resolve policy to prompt/tool dependency mismatch.",
                severity=severity,
            )
        if risk_type.startswith("prompt_"):
            upsert_hint(
                action_id="registry.prompt.curate",
                path="/internal/judge/registries/prompts",
                reason="review prompt releases and keep only referenced versions.",
                severity=severity,
            )
        if risk_type.startswith("tool_"):
            upsert_hint(
                action_id="registry.tool.curate",
                path="/internal/judge/registries/tools",
                reason="review tool releases and keep only referenced versions.",
                severity=severity,
            )
        if risk_type.endswith("_missing"):
            upsert_hint(
                action_id="registry.audits.inspect",
                path="/internal/judge/registries/policy/gate-simulation",
                reason="inspect release gate simulation before activation.",
                severity=severity,
            )

    if not action_index:
        return [
            {
                "actionId": "monitor",
                "path": "/internal/judge/registries/prompt-tool/governance",
                "reason": "governance signals look healthy; continue monitoring.",
                "severity": "low",
            }
        ]

    action_rows = list(action_index.values())
    action_rows.sort(
        key=lambda row: (
            -int(row.get("_rank") or 0),
            str(row.get("actionId") or ""),
        )
    )
    for row in action_rows:
        row.pop("_rank", None)
    return action_rows


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
        "gateSource": row.get("gateSource"),
        "overrideApplied": row.get("overrideApplied"),
        "gateActor": row.get("gateActor"),
        "gateReason": row.get("gateReason"),
        "gateBenchmarkPassed": row.get("gateBenchmarkPassed"),
        "gateShadowApplied": row.get("gateShadowApplied"),
        "gateShadowPassed": row.get("gateShadowPassed"),
        "gateLatestRunId": row.get("gateLatestRunId"),
        "gateLatestRunStatus": row.get("gateLatestRunStatus"),
        "gateLatestRunThresholdDecision": row.get("gateLatestRunThresholdDecision"),
        "gateLatestRunEnvironmentMode": row.get("gateLatestRunEnvironmentMode"),
        "gateLatestRunNeedsRemediation": row.get("gateLatestRunNeedsRemediation"),
        "gateLatestShadowRunId": row.get("gateLatestShadowRunId"),
        "gateLatestShadowRunStatus": row.get("gateLatestShadowRunStatus"),
        "gateLatestShadowRunThresholdDecision": row.get("gateLatestShadowRunThresholdDecision"),
        "gateLatestShadowRunEnvironmentMode": row.get("gateLatestShadowRunEnvironmentMode"),
        "gateLatestShadowRunNeedsRemediation": row.get("gateLatestShadowRunNeedsRemediation"),
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
    return build_registry_audit_ops_view_v3(
        registry_type=registry_type,
        audit_items=audit_items,
        alerts=alerts,
        outbox_events=outbox_events,
        action=action,
        version=version,
        actor=actor,
        gate_code=gate_code,
        override_applied=override_applied,
        include_gate_view=include_gate_view,
        link_limit=link_limit,
        offset=offset,
        limit=limit,
    )


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
    return build_registry_alert_ops_view_v3(
        alerts=alerts,
        outbox_events=outbox_events,
        alert_type=alert_type,
        status=status,
        delivery_status=delivery_status,
        registry_type=registry_type,
        policy_version=policy_version,
        gate_code=gate_code,
        gate_actor=gate_actor,
        override_applied=override_applied,
        fields_mode=fields_mode,
        include_trend=include_trend,
        trend_window_minutes=trend_window_minutes,
        trend_bucket_minutes=trend_bucket_minutes,
        offset=offset,
        limit=limit,
    )


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
    latest_shadow_run: FactFairnessShadowRun | None,
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
    verdict_ledger = (
        report_payload.get("verdictLedger")
        if isinstance(report_payload.get("verdictLedger"), dict)
        else {}
    )
    arbitration = (
        verdict_ledger.get("arbitration")
        if isinstance(verdict_ledger.get("arbitration"), dict)
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
    shadow_summary = (
        latest_shadow_run.summary
        if latest_shadow_run is not None and isinstance(latest_shadow_run.summary, dict)
        else {}
    )
    shadow_breaches = shadow_summary.get("breaches")
    if not isinstance(shadow_breaches, list):
        shadow_breaches = []
    has_shadow_breach = bool(
        shadow_summary.get("hasBreach")
        if isinstance(shadow_summary, dict)
        else False
    )
    if latest_shadow_run is not None and latest_shadow_run.threshold_decision != "accepted":
        has_shadow_breach = True
    gate_conclusion = _normalize_fairness_gate_decision(
        arbitration.get("gateDecision") or fairness_summary.get("gateDecision"),
        review_required=review_required,
    )
    if not gate_conclusion:
        gate_conclusion = "blocked_to_draw" if review_required else "pass_through"

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
        "shadowSummary": {
            "policyVersion": policy_version,
            "latestRun": (
                _serialize_fairness_shadow_run(latest_shadow_run)
                if latest_shadow_run is not None
                else None
            ),
            "benchmarkRunId": latest_shadow_run.benchmark_run_id if latest_shadow_run is not None else None,
            "breaches": [str(item).strip() for item in shadow_breaches if str(item).strip()],
            "hasShadowBreach": has_shadow_breach,
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
    judge_workflow: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_trace_report_summary_v3(
        dispatch_type=dispatch_type,
        payload=payload,
        callback_status=callback_status,
        callback_error=callback_error,
        judge_workflow=judge_workflow,
    )


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


def _validate_fairness_dashboard_contract(payload: dict[str, Any]) -> None:
    validate_fairness_dashboard_contract_v3(payload)


def _validate_case_overview_contract(payload: dict[str, Any]) -> None:
    validate_case_overview_contract_v3(payload)


def _validate_courtroom_read_model_contract(payload: dict[str, Any]) -> None:
    validate_courtroom_read_model_contract_v3(payload)


def _validate_case_fairness_detail_contract(payload: dict[str, Any]) -> None:
    validate_case_fairness_detail_contract_v3(payload)


def _validate_case_fairness_list_contract(payload: dict[str, Any]) -> None:
    validate_case_fairness_list_contract_v3(payload)


def _validate_panel_runtime_profile_contract(payload: dict[str, Any]) -> None:
    validate_panel_runtime_profile_contract_v3(payload)


def _validate_trust_public_verify_contract(payload: dict[str, Any]) -> None:
    validate_trust_public_verify_contract_v3(payload)


def _validate_trust_challenge_ops_queue_contract(payload: dict[str, Any]) -> None:
    validate_trust_challenge_queue_contract_v3(payload)


def _validate_trust_challenge_review_contract(payload: dict[str, Any]) -> None:
    validate_trust_challenge_review_contract_v3(payload)


def _validate_trust_commitment_contract(payload: dict[str, Any]) -> None:
    validate_trust_commitment_contract_v3(payload)


def _validate_trust_verdict_attestation_contract(payload: dict[str, Any]) -> None:
    validate_trust_verdict_attestation_contract_v3(payload)


def _validate_trust_kernel_version_contract(payload: dict[str, Any]) -> None:
    validate_trust_kernel_version_contract_v3(payload)


def _validate_trust_audit_anchor_contract(payload: dict[str, Any]) -> None:
    validate_trust_audit_anchor_contract_v3(payload)


def _validate_courtroom_drilldown_bundle_contract(payload: dict[str, Any]) -> None:
    validate_courtroom_drilldown_bundle_contract_v3(payload)


def _validate_evidence_claim_ops_queue_contract(payload: dict[str, Any]) -> None:
    validate_evidence_claim_ops_queue_contract_v3(payload)


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


def _build_phase_judge_workflow_payload(
    *,
    request: PhaseDispatchRequest,
    report_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    return build_phase_judge_workflow_payload_v3(
        request=request,
        report_payload=report_payload,
    )


def _build_final_judge_workflow_payload(
    *,
    request: FinalDispatchRequest,
    report_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    return build_final_judge_workflow_payload_v3(
        request=request,
        report_payload=report_payload,
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
        request_payload: dict[str, Any] | None = None,
    ) -> FactClaimLedgerRecord | None:
        payload = report_payload if isinstance(report_payload, dict) else {}
        if not payload and not isinstance(request_payload, dict):
            return None
        verdict_contract = _build_verdict_contract(payload)
        evidence_view = _build_case_evidence_view(
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
        await _ensure_workflow_schema_ready()
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

    async def _upsert_fairness_shadow_run(
        *,
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
    ) -> FactFairnessShadowRun:
        await _ensure_workflow_schema_ready()
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

    async def _list_fairness_shadow_runs(
        *,
        policy_version: str | None = None,
        benchmark_run_id: str | None = None,
        environment_mode: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[FactFairnessShadowRun]:
        await _ensure_workflow_schema_ready()
        return await runtime.workflow_runtime.facts.list_fairness_shadow_runs(
            policy_version=policy_version,
            benchmark_run_id=benchmark_run_id,
            environment_mode=environment_mode,
            status=status,
            limit=limit,
        )

    async def _evaluate_policy_release_fairness_gate(
        *,
        policy_version: str,
    ) -> dict[str, Any]:
        def _serialize_benchmark_gate_run(
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

        def _serialize_shadow_gate_run(
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
        serialized_latest_run = _serialize_benchmark_gate_run(latest)
        if benchmark_gate_passed:
            shadow_runs = await _list_fairness_shadow_runs(
                policy_version=version,
                limit=20,
            )
            latest_shadow_run = shadow_runs[0] if shadow_runs else None
            serialized_latest_shadow_run = _serialize_shadow_gate_run(latest_shadow_run)
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
        judge_trace_payload = (
            latest_response.get("judgeTrace")
            if isinstance(latest_response.get("judgeTrace"), dict)
            else {}
        )
        policy_registry_payload = (
            judge_trace_payload.get("policyRegistry")
            if isinstance(judge_trace_payload.get("policyRegistry"), dict)
            else {}
        )
        rubric_version = (
            str(getattr(latest_receipt, "rubric_version", "") or "").strip()
            if latest_receipt is not None
            else ""
        )
        judge_policy_version = (
            str(getattr(latest_receipt, "judge_policy_version", "") or "").strip()
            if latest_receipt is not None
            else ""
        )
        topic_domain = (
            str(getattr(latest_receipt, "topic_domain", "") or "").strip()
            if latest_receipt is not None
            else ""
        )
        retrieval_profile = (
            str(getattr(latest_receipt, "retrieval_profile", "") or "").strip()
            if latest_receipt is not None
            else ""
        )
        rule_version = (
            str(policy_registry_payload.get("version") or "").strip()
            or judge_policy_version
            or None
        )

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
            "ruleVersion": rule_version,
            "rubricVersion": rubric_version or None,
            "judgePolicyVersion": judge_policy_version or None,
            "topicDomain": topic_domain or None,
            "retrievalProfile": retrieval_profile or None,
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
            cast(
                dict[str, Any],
                sanitize_assistant_advisory_output_v3(execution_result.output),
            )
            if isinstance(execution_result.output, dict)
            else {}
        )
        # NPC/Room QA 仅能产出建议，不得进入官方裁决主链。
        capability_boundary = {
            "mode": "advisory_only",
            "officialVerdictAuthority": False,
            "writesVerdictLedger": False,
            "writesJudgeTrace": False,
        }
        return {
            "agentKind": agent_kind,
            "sessionId": session_id,
            "caseId": shared_context.get("caseId"),
            "status": execution_result.status,
            "accepted": bool(output.get("accepted")),
            "errorCode": execution_result.error_code,
            "errorMessage": execution_result.error_message,
            "capabilityBoundary": capability_boundary,
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
        return build_registry_profiles_payload_v3(
            default_version=runtime.prompt_registry_runtime.default_version,
            profiles=profiles,
            serializer=lambda item: _serialize_prompt_profile(runtime, profile=item),
        )

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
        return build_registry_profile_payload_v3(
            profile=profile,
            serializer=lambda item: _serialize_prompt_profile(runtime, profile=item),
        )

    @app.get("/internal/judge/registries/tools")
    async def list_tool_registries(
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        await _ensure_registry_runtime_ready()
        profiles = runtime.tool_registry_runtime.list_profiles()
        return build_registry_profiles_payload_v3(
            default_version=runtime.tool_registry_runtime.default_version,
            profiles=profiles,
            serializer=lambda item: _serialize_tool_profile(runtime, profile=item),
        )

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
        return build_registry_profile_payload_v3(
            profile=profile,
            serializer=lambda item: _serialize_tool_profile(runtime, profile=item),
        )

    def _build_registry_governance_route_dependency_pack() -> (
        RegistryGovernanceRouteDependencyPack_v3
    ):
        return RegistryGovernanceRouteDependencyPack_v3(
            default_policy_version=runtime.policy_registry_runtime.default_version,
            default_prompt_registry_version=runtime.prompt_registry_runtime.default_version,
            default_tool_registry_version=runtime.tool_registry_runtime.default_version,
            policy_registry_type=REGISTRY_TYPE_POLICY,
            prompt_registry_type="prompt",
            tool_registry_type="tool",
            list_policy_profiles=runtime.policy_registry_runtime.list_profiles,
            list_prompt_profiles=runtime.prompt_registry_runtime.list_profiles,
            list_tool_profiles=runtime.tool_registry_runtime.list_profiles,
            get_policy_profile=runtime.policy_registry_runtime.get_profile,
            serialize_policy_profile=(
                lambda profile: _serialize_policy_profile(runtime, profile=profile)
            ),
            evaluate_policy_registry_dependency_health=(
                lambda version: _evaluate_policy_registry_dependency_health(
                    policy_version=version,
                )
            ),
            evaluate_policy_release_fairness_gate=(
                lambda version: _evaluate_policy_release_fairness_gate(
                    policy_version=version,
                )
            ),
            list_releases=runtime.registry_product_runtime.list_releases,
            list_audits=runtime.registry_product_runtime.list_audits,
            normalize_registry_dependency_trend_status=(
                _normalize_registry_dependency_trend_status
            ),
            dependency_trend_status_values=REGISTRY_DEPENDENCY_TREND_STATUS_VALUES,
            list_audit_alerts=_list_audit_alerts,
            build_registry_dependency_overview=_build_registry_dependency_overview,
            build_registry_dependency_trend=_build_registry_dependency_trend,
            build_policy_domain_judge_family_overview=(
                _build_policy_domain_judge_family_overview
            ),
            build_registry_prompt_tool_usage_rows=_build_registry_prompt_tool_usage_rows,
            build_registry_prompt_tool_risk_items=_build_registry_prompt_tool_risk_items,
            build_registry_prompt_tool_action_hints=_build_registry_prompt_tool_action_hints,
        )

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
        dependency_pack = _build_registry_governance_route_dependency_pack()
        return await _run_registry_route_guard(
            build_policy_registry_dependency_health_route_payload_from_pack_v3(
                pack=dependency_pack,
                policy_version=policy_version,
                include_all_versions=include_all_versions,
                include_overview=include_overview,
                include_trend=include_trend,
                trend_status=trend_status,
                trend_policy_version=trend_policy_version,
                trend_offset=trend_offset,
                trend_limit=trend_limit,
                overview_window_minutes=overview_window_minutes,
                limit=limit,
            )
        )

    @app.get("/internal/judge/registries/governance/overview")
    async def get_registry_governance_overview(
        x_ai_internal_key: str | None = Header(default=None),
        dependency_limit: int = Query(default=200, ge=1, le=500),
        usage_preview_limit: int = Query(default=20, ge=1, le=200),
        release_limit: int = Query(default=50, ge=1, le=200),
        audit_limit: int = Query(default=100, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        await _ensure_registry_runtime_ready()
        dependency_pack = _build_registry_governance_route_dependency_pack()
        return await _run_registry_route_guard(
            build_registry_governance_overview_route_payload_from_pack_v3(
                pack=dependency_pack,
                dependency_limit=dependency_limit,
                usage_preview_limit=usage_preview_limit,
                release_limit=release_limit,
                audit_limit=audit_limit,
            )
        )

    @app.get("/internal/judge/registries/prompt-tool/governance")
    async def get_registry_prompt_tool_governance(
        x_ai_internal_key: str | None = Header(default=None),
        dependency_limit: int = Query(default=200, ge=1, le=500),
        usage_preview_limit: int = Query(default=20, ge=1, le=200),
        release_limit: int = Query(default=50, ge=1, le=200),
        audit_limit: int = Query(default=100, ge=1, le=200),
        risk_limit: int = Query(default=50, ge=1, le=500),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        await _ensure_registry_runtime_ready()
        dependency_pack = _build_registry_governance_route_dependency_pack()
        return await _run_registry_route_guard(
            build_registry_prompt_tool_governance_route_payload_from_pack_v3(
                pack=dependency_pack,
                dependency_limit=dependency_limit,
                usage_preview_limit=usage_preview_limit,
                release_limit=release_limit,
                audit_limit=audit_limit,
                risk_limit=risk_limit,
            )
        )

    @app.get("/internal/judge/registries/policy/domain-families")
    async def list_policy_domain_judge_families(
        x_ai_internal_key: str | None = Header(default=None),
        preview_limit: int = Query(default=20, ge=1, le=200),
        include_versions: bool = Query(default=True),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        await _ensure_registry_runtime_ready()
        dependency_pack = _build_registry_governance_route_dependency_pack()
        return await _run_registry_route_guard(
            build_policy_domain_judge_families_route_payload_from_pack_v3(
                pack=dependency_pack,
                preview_limit=preview_limit,
                include_versions=include_versions,
            )
        )

    @app.get("/internal/judge/registries/policy/gate-simulation")
    async def simulate_policy_release_gate(
        x_ai_internal_key: str | None = Header(default=None),
        policy_version: str | None = Query(default=None),
        include_all_versions: bool = Query(default=False),
        limit: int = Query(default=20, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        await _ensure_registry_runtime_ready()
        dependency_pack = _build_registry_governance_route_dependency_pack()
        return await _run_registry_route_guard(
            build_policy_gate_simulation_route_payload_from_pack_v3(
                pack=dependency_pack,
                policy_version=policy_version,
                include_all_versions=include_all_versions,
                limit=limit,
            )
        )

    async def _read_json_object_or_raise_422(*, request: Request) -> dict[str, Any]:
        try:
            payload = await request.json()
        except Exception as err:
            raise HTTPException(status_code=422, detail=f"invalid_json: {err}") from err
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail="invalid_payload")
        return payload

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

    def _raise_policy_registry_not_found_lookup_error(*, err: LookupError) -> None:
        if str(err) == "policy_registry_not_found":
            raise HTTPException(status_code=404, detail="policy_registry_not_found") from err

    def _raise_http_500_contract_violation(*, err: ValueError, code: str) -> None:
        raise HTTPException(
            status_code=500,
            detail={
                "code": str(code),
                "message": str(err),
            },
        ) from err

    def _raise_registry_value_error(
        *,
        err: ValueError,
        default_detail: str,
        unprocessable_codes: set[str],
        conflict_codes: set[str] | None = None,
    ) -> None:
        code = str(err)
        if isinstance(conflict_codes, set) and code in conflict_codes:
            raise HTTPException(status_code=409, detail=code) from err
        if code in unprocessable_codes:
            raise HTTPException(status_code=422, detail=code) from err
        raise HTTPException(status_code=422, detail=default_detail) from err

    @app.post("/internal/judge/registries/{registry_type}/publish")
    async def publish_registry_release(
        registry_type: str,
        request: Request,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        payload = await _read_json_object_or_raise_422(request=request)
        try:
            parsed = parse_registry_publish_request_payload_v3(
                payload=payload,
                extract_optional_bool=_extract_optional_bool,
            )
        except ValueError as err:
            _raise_http_422_from_value_error(err=err)
        await _ensure_registry_runtime_ready()
        try:
            return await _run_registry_route_guard(
                build_registry_publish_payload_v3(
                registry_type=registry_type,
                version=parsed["version"],
                profile_payload=parsed["profilePayload"],
                activate=bool(parsed["activate"]),
                override_fairness_gate=bool(parsed["overrideFairnessGate"]),
                actor=parsed["actor"],
                reason=parsed["reason"],
                policy_registry_type=REGISTRY_TYPE_POLICY,
                enforce_policy_domain_judge_family_profile_payload=(
                    _enforce_policy_domain_judge_family_profile_payload
                ),
                evaluate_policy_registry_dependency_health=(
                    _evaluate_policy_registry_dependency_health
                ),
                emit_registry_dependency_health_alert=_emit_registry_dependency_health_alert,
                resolve_registry_dependency_health_alerts=(
                    _resolve_registry_dependency_health_alerts
                ),
                evaluate_policy_release_fairness_gate=_evaluate_policy_release_fairness_gate,
                emit_registry_fairness_gate_alert=_emit_registry_fairness_gate_alert,
                publish_release=runtime.registry_product_runtime.publish_release,
            )
            )
        except LookupError as err:
            _raise_http_404_from_lookup_error(err=err)
        except ValueError as err:
            _raise_registry_value_error(
                err=err,
                default_detail="registry_publish_invalid",
                unprocessable_codes={
                    "invalid_registry_type",
                    "invalid_registry_version",
                    "invalid_policy_profile",
                    "invalid_policy_domain_judge_family",
                    "policy_domain_family_topic_domain_mismatch",
                    "invalid_prompt_profile",
                    "invalid_tool_profile",
                    "registry_fairness_gate_override_reason_required",
                },
                conflict_codes={"registry_version_already_exists"},
            )

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
        try:
            return await _run_registry_route_guard(
                build_registry_activate_payload_v3(
                registry_type=registry_type,
                version=version,
                actor=actor,
                reason=reason,
                override_fairness_gate=override_fairness_gate,
                policy_registry_type=REGISTRY_TYPE_POLICY,
                evaluate_policy_registry_dependency_health=(
                    _evaluate_policy_registry_dependency_health
                ),
                emit_registry_dependency_health_alert=_emit_registry_dependency_health_alert,
                resolve_registry_dependency_health_alerts=(
                    _resolve_registry_dependency_health_alerts
                ),
                evaluate_policy_release_fairness_gate=_evaluate_policy_release_fairness_gate,
                emit_registry_fairness_gate_alert=_emit_registry_fairness_gate_alert,
                activate_release=runtime.registry_product_runtime.activate_release,
            )
            )
        except LookupError as err:
            raise HTTPException(status_code=404, detail="registry_version_not_found") from err
        except ValueError as err:
            _raise_registry_value_error(
                err=err,
                default_detail="registry_activate_invalid",
                unprocessable_codes={
                    "invalid_registry_type",
                    "invalid_registry_version",
                    "registry_fairness_gate_override_reason_required",
                },
            )

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
            return await build_registry_rollback_payload_v3(
                registry_type=registry_type,
                target_version=target_version,
                actor=actor,
                reason=reason,
                rollback_release=runtime.registry_product_runtime.rollback_release,
            )
        except LookupError as err:
            raise HTTPException(status_code=404, detail="registry_version_not_found") from err
        except ValueError as err:
            _raise_registry_value_error(
                err=err,
                default_detail="registry_rollback_invalid",
                unprocessable_codes={
                    "invalid_registry_type",
                    "invalid_registry_version",
                },
                conflict_codes={"registry_rollback_target_not_found"},
            )

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
        try:
            return await build_registry_audits_payload_v3(
                registry_type=registry_type,
                action=action,
                version=version,
                actor=actor,
                gate_code=gate_code,
                override_applied=override_applied,
                include_gate_view=include_gate_view,
                link_limit=link_limit,
                offset=offset,
                limit=limit,
                normalize_registry_audit_action=_normalize_registry_audit_action,
                registry_audit_action_values=REGISTRY_AUDIT_ACTION_VALUES,
                list_registry_audits=runtime.registry_product_runtime.list_audits,
                list_audit_alerts=_list_audit_alerts,
                list_alert_outbox=runtime.trace_store.list_alert_outbox,
                build_registry_audit_ops_view=_build_registry_audit_ops_view,
            )
        except ValueError as err:
            _raise_registry_value_error(
                err=err,
                default_detail="registry_audit_query_invalid",
                unprocessable_codes={
                    "invalid_registry_audit_action",
                    "invalid_registry_type",
                },
            )

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
            _raise_registry_value_error(
                err=err,
                default_detail="registry_release_query_invalid",
                unprocessable_codes={"invalid_registry_type"},
            )
        return build_registry_releases_payload_v3(
            registry_type=registry_type,
            items=items,
            limit=limit,
            include_payload=include_payload,
        )

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
            _raise_registry_value_error(
                err=err,
                default_detail="registry_release_query_invalid",
                unprocessable_codes={
                    "invalid_registry_type",
                    "invalid_registry_version",
                },
            )
        if item is None:
            raise HTTPException(status_code=404, detail="registry_version_not_found")
        return build_registry_release_payload_v3(item=item)

    @app.post("/internal/judge/cases")
    async def create_judge_case(
        request: Request,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        raw_payload = await _read_json_object_or_raise_422(request=request)
        return await _run_judge_command_route_guard(
            build_case_create_route_payload_v3(
                raw_payload=raw_payload,
                case_create_model_validate=CaseCreateRequest.model_validate,
                resolve_idempotency_or_raise=(
                    lambda *, key, job_id, conflict_detail: _resolve_idempotency_or_raise(
                        runtime=runtime,
                        key=key,
                        job_id=job_id,
                        conflict_detail=conflict_detail,
                    )
                ),
                ensure_registry_runtime_ready=_ensure_registry_runtime_ready,
                resolve_policy_profile=(
                    lambda *, judge_policy_version, rubric_version, topic_domain: _resolve_policy_profile_or_raise(
                        runtime=runtime,
                        judge_policy_version=judge_policy_version,
                        rubric_version=rubric_version,
                        topic_domain=topic_domain,
                    )
                ),
                resolve_prompt_profile=(
                    lambda *, prompt_registry_version: _resolve_prompt_profile_or_raise(
                        runtime=runtime,
                        prompt_registry_version=prompt_registry_version,
                    )
                ),
                resolve_tool_profile=(
                    lambda *, tool_registry_version: _resolve_tool_profile_or_raise(
                        runtime=runtime,
                        tool_registry_version=tool_registry_version,
                    )
                ),
                workflow_get_job=_workflow_get_job,
                build_workflow_job=_build_workflow_job,
                workflow_register_and_mark_case_built=_workflow_register_and_mark_case_built,
                serialize_workflow_job=_serialize_workflow_job,
                trace_register_start=runtime.trace_store.register_start,
                trace_register_success=runtime.trace_store.register_success,
                build_trace_report_summary=_build_trace_report_summary,
                set_idempotency_success=runtime.trace_store.set_idempotency_success,
                idempotency_ttl_secs=runtime.settings.idempotency_ttl_secs,
            )
        )

    @app.post("/internal/judge/v3/phase/dispatch")
    async def dispatch_judge_phase(
        request: Request,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        raw_payload = await _read_json_object_or_raise_422(request=request)
        sensitive_hits = _find_sensitive_key_hits(raw_payload)
        if sensitive_hits:
            await _run_judge_command_route_guard(
                build_blindization_rejection_route_payload_v3(
                    dispatch_type="phase",
                    raw_payload=raw_payload,
                    sensitive_hits=sensitive_hits,
                    extract_dispatch_meta_from_raw=_extract_dispatch_meta_from_raw,
                    extract_receipt_dims_from_raw=_extract_receipt_dims_from_raw,
                    build_workflow_job=_build_workflow_job,
                    trace_register_start=runtime.trace_store.register_start,
                    workflow_register_and_mark_blinded=_workflow_register_and_mark_blinded,
                    build_failed_callback_payload=_build_failed_callback_payload,
                    invoke_failed_callback_with_retry=(
                        lambda *, case_id, payload: _invoke_v3_callback_with_retry(
                            runtime=runtime,
                            callback_fn=_failed_callback_fn_for_dispatch(runtime, "phase"),
                            job_id=case_id,
                            payload=payload,
                        )
                    ),
                    with_error_contract=_with_error_contract,
                    persist_dispatch_receipt=_persist_dispatch_receipt,
                    trace_register_failure=runtime.trace_store.register_failure,
                    workflow_mark_failed=_workflow_mark_failed,
                )
            )
        preflight = await _run_judge_command_route_guard(
            build_phase_dispatch_preflight_route_payload_v3(
                raw_payload=raw_payload,
                phase_dispatch_model_validate=PhaseDispatchRequest.model_validate,
                validate_phase_dispatch_request=_validate_phase_dispatch_request,
                resolve_idempotency_or_raise=(
                    lambda *, key, job_id, conflict_detail: _resolve_idempotency_or_raise(
                        runtime=runtime,
                        key=key,
                        job_id=job_id,
                        conflict_detail=conflict_detail,
                    )
                ),
                ensure_registry_runtime_ready=_ensure_registry_runtime_ready,
                resolve_policy_profile=(
                    lambda *, judge_policy_version, rubric_version, topic_domain: _resolve_policy_profile_or_raise(
                        runtime=runtime,
                        judge_policy_version=judge_policy_version,
                        rubric_version=rubric_version,
                        topic_domain=topic_domain,
                    )
                ),
                resolve_prompt_profile=(
                    lambda *, prompt_registry_version: _resolve_prompt_profile_or_raise(
                        runtime=runtime,
                        prompt_registry_version=prompt_registry_version,
                    )
                ),
                resolve_tool_profile=(
                    lambda *, tool_registry_version: _resolve_tool_profile_or_raise(
                        runtime=runtime,
                        tool_registry_version=tool_registry_version,
                    )
                ),
                build_phase_dispatch_accepted_response=build_phase_dispatch_accepted_response_v3,
                build_workflow_job=_build_workflow_job,
                trace_register_start=runtime.trace_store.register_start,
                persist_dispatch_receipt=_persist_dispatch_receipt,
                workflow_register_and_mark_blinded=_workflow_register_and_mark_blinded,
                build_phase_workflow_register_payload=build_phase_workflow_register_payload_v3,
            )
        )
        replayed_response = preflight.get("replayedResponse")
        if isinstance(replayed_response, dict):
            return replayed_response
        parsed = cast(PhaseDispatchRequest, preflight["parsed"])
        response = cast(dict[str, Any], preflight["response"])
        request_payload = cast(dict[str, Any], preflight["requestPayload"])
        policy_profile = preflight["policyProfile"]
        prompt_profile = preflight["promptProfile"]
        tool_profile = preflight["toolProfile"]

        report_materialization = await _run_judge_command_route_guard(
            build_phase_dispatch_report_materialization_route_payload_v3(
                parsed=parsed,
                request_payload=request_payload,
                policy_profile=policy_profile,
                prompt_profile=prompt_profile,
                tool_profile=tool_profile,
                build_phase_report_payload=(
                    lambda *, request: build_phase_report_payload_v3_phase(
                        request=request,
                        settings=runtime.settings,
                        gateway_runtime=runtime.gateway_runtime,
                    )
                ),
                attach_judge_agent_runtime_trace=(
                    lambda **kwargs: _attach_judge_agent_runtime_trace(
                        runtime=runtime,
                        **kwargs,
                    )
                ),
                attach_policy_trace_snapshot=(
                    lambda *, report_payload, profile, prompt_profile, tool_profile: _attach_policy_trace_snapshot(
                        runtime=runtime,
                        report_payload=report_payload,
                        profile=profile,
                        prompt_profile=prompt_profile,
                        tool_profile=tool_profile,
                    )
                ),
                attach_report_attestation=_attach_report_attestation,
                upsert_claim_ledger_record=_upsert_claim_ledger_record,
                build_phase_judge_workflow_payload=_build_phase_judge_workflow_payload,
            )
        )
        phase_report_payload = cast(dict[str, Any], report_materialization["reportPayload"])
        phase_judge_workflow_payload = cast(
            dict[str, Any],
            report_materialization["phaseJudgeWorkflowPayload"],
        )
        phase_callback_outcome = await _run_judge_command_route_guard(
            build_phase_dispatch_callback_delivery_route_payload_v3(
                parsed=parsed,
                report_payload=phase_report_payload,
                deliver_report_callback_with_failed_fallback=deliver_report_callback_with_failed_fallback_v3,
                report_callback_fn=_report_callback_fn_for_dispatch(runtime, "phase"),
                failed_callback_fn=_failed_callback_fn_for_dispatch(runtime, "phase"),
                invoke_with_retry=(
                    lambda callback_fn, job_id, payload: _invoke_v3_callback_with_retry(
                        runtime=runtime,
                        callback_fn=callback_fn,
                        job_id=job_id,
                        payload=payload,
                    )
                ),
                build_failed_callback_payload=_build_failed_callback_payload,
            )
        )

        return await _run_judge_command_route_guard(
            build_phase_dispatch_callback_result_route_payload_v3(
                parsed=parsed,
                response=response,
                request_payload=request_payload,
                report_payload=phase_report_payload,
                callback_outcome=phase_callback_outcome,
                callback_status_reported=CALLBACK_STATUS_REPORTED_V3,
                callback_status_failed_reported=CALLBACK_STATUS_FAILED_REPORTED_V3,
                callback_status_failed_callback_failed=CALLBACK_STATUS_FAILED_CALLBACK_FAILED_V3,
                with_error_contract=_with_error_contract,
                persist_dispatch_receipt=_persist_dispatch_receipt,
                trace_register_failure=runtime.trace_store.register_failure,
                trace_register_success=runtime.trace_store.register_success,
                workflow_mark_failed=_workflow_mark_failed,
                workflow_mark_completed=_workflow_mark_completed,
                build_phase_workflow_reported_payload=build_phase_workflow_reported_payload_v3,
                build_trace_report_summary=_build_trace_report_summary,
                clear_idempotency=runtime.trace_store.clear_idempotency,
                set_idempotency_success=runtime.trace_store.set_idempotency_success,
                idempotency_ttl_secs=runtime.settings.idempotency_ttl_secs,
                phase_judge_workflow_payload=phase_judge_workflow_payload,
            )
        )

    @app.post("/internal/judge/v3/final/dispatch")
    async def dispatch_judge_final(
        request: Request,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        raw_payload = await _read_json_object_or_raise_422(request=request)
        sensitive_hits = _find_sensitive_key_hits(raw_payload)
        if sensitive_hits:
            await _run_judge_command_route_guard(
                build_blindization_rejection_route_payload_v3(
                    dispatch_type="final",
                    raw_payload=raw_payload,
                    sensitive_hits=sensitive_hits,
                    extract_dispatch_meta_from_raw=_extract_dispatch_meta_from_raw,
                    extract_receipt_dims_from_raw=_extract_receipt_dims_from_raw,
                    build_workflow_job=_build_workflow_job,
                    trace_register_start=runtime.trace_store.register_start,
                    workflow_register_and_mark_blinded=_workflow_register_and_mark_blinded,
                    build_failed_callback_payload=_build_failed_callback_payload,
                    invoke_failed_callback_with_retry=(
                        lambda *, case_id, payload: _invoke_v3_callback_with_retry(
                            runtime=runtime,
                            callback_fn=_failed_callback_fn_for_dispatch(runtime, "final"),
                            job_id=case_id,
                            payload=payload,
                        )
                    ),
                    with_error_contract=_with_error_contract,
                    persist_dispatch_receipt=_persist_dispatch_receipt,
                    trace_register_failure=runtime.trace_store.register_failure,
                    workflow_mark_failed=_workflow_mark_failed,
                )
            )
        preflight = await _run_judge_command_route_guard(
            build_final_dispatch_preflight_route_payload_v3(
                raw_payload=raw_payload,
                final_dispatch_model_validate=FinalDispatchRequest.model_validate,
                validate_final_dispatch_request=_validate_final_dispatch_request,
                resolve_idempotency_or_raise=(
                    lambda *, key, job_id, conflict_detail: _resolve_idempotency_or_raise(
                        runtime=runtime,
                        key=key,
                        job_id=job_id,
                        conflict_detail=conflict_detail,
                    )
                ),
                ensure_registry_runtime_ready=_ensure_registry_runtime_ready,
                resolve_policy_profile=(
                    lambda *, judge_policy_version, rubric_version, topic_domain: _resolve_policy_profile_or_raise(
                        runtime=runtime,
                        judge_policy_version=judge_policy_version,
                        rubric_version=rubric_version,
                        topic_domain=topic_domain,
                    )
                ),
                resolve_prompt_profile=(
                    lambda *, prompt_registry_version: _resolve_prompt_profile_or_raise(
                        runtime=runtime,
                        prompt_registry_version=prompt_registry_version,
                    )
                ),
                resolve_tool_profile=(
                    lambda *, tool_registry_version: _resolve_tool_profile_or_raise(
                        runtime=runtime,
                        tool_registry_version=tool_registry_version,
                    )
                ),
                build_final_dispatch_accepted_response=build_final_dispatch_accepted_response_v3,
                build_workflow_job=_build_workflow_job,
                trace_register_start=runtime.trace_store.register_start,
                persist_dispatch_receipt=_persist_dispatch_receipt,
                workflow_register_and_mark_blinded=_workflow_register_and_mark_blinded,
                build_final_workflow_register_payload=build_final_workflow_register_payload_v3,
            )
        )
        replayed_response = preflight.get("replayedResponse")
        if isinstance(replayed_response, dict):
            return replayed_response
        parsed = cast(FinalDispatchRequest, preflight["parsed"])
        response = cast(dict[str, Any], preflight["response"])
        request_payload = cast(dict[str, Any], preflight["requestPayload"])
        policy_profile = preflight["policyProfile"]
        prompt_profile = preflight["promptProfile"]
        tool_profile = preflight["toolProfile"]

        report_materialization = await _run_judge_command_route_guard(
            build_final_dispatch_report_materialization_route_payload_v3(
                parsed=parsed,
                request_payload=request_payload,
                policy_profile=policy_profile,
                prompt_profile=prompt_profile,
                tool_profile=tool_profile,
                list_dispatch_receipts=_list_dispatch_receipts,
                build_final_report_payload=(
                    lambda *, request, phase_receipts, fairness_thresholds, panel_runtime_profiles: _build_final_report_payload(
                        runtime=runtime,
                        request=request,
                        phase_receipts=phase_receipts,
                        fairness_thresholds=fairness_thresholds,
                        panel_runtime_profiles=panel_runtime_profiles,
                    )
                ),
                resolve_panel_runtime_profiles=_resolve_panel_runtime_profiles,
                attach_judge_agent_runtime_trace=(
                    lambda **kwargs: _attach_judge_agent_runtime_trace(
                        runtime=runtime,
                        **kwargs,
                    )
                ),
                attach_policy_trace_snapshot=(
                    lambda *, report_payload, profile, prompt_profile, tool_profile: _attach_policy_trace_snapshot(
                        runtime=runtime,
                        report_payload=report_payload,
                        profile=profile,
                        prompt_profile=prompt_profile,
                        tool_profile=tool_profile,
                    )
                ),
                attach_report_attestation=_attach_report_attestation,
                upsert_claim_ledger_record=_upsert_claim_ledger_record,
                build_final_judge_workflow_payload=_build_final_judge_workflow_payload,
                validate_final_report_payload_contract=_validate_final_report_payload_contract,
            )
        )
        final_report_payload = cast(dict[str, Any], report_materialization["reportPayload"])
        final_judge_workflow_payload = cast(
            dict[str, Any],
            report_materialization["finalJudgeWorkflowPayload"],
        )
        contract_missing_fields = cast(
            list[str],
            report_materialization["contractMissingFields"],
        )
        if contract_missing_fields:
            await _run_judge_command_route_guard(
                build_final_contract_blocked_route_payload_v3(
                    parsed=parsed,
                    response=response,
                    request_payload=request_payload,
                    report_payload=final_report_payload,
                    contract_missing_fields=contract_missing_fields,
                    upsert_audit_alert=runtime.trace_store.upsert_audit_alert,
                    sync_audit_alert_to_facts=_sync_audit_alert_to_facts,
                    build_failed_callback_payload=_build_failed_callback_payload,
                    invoke_failed_callback_with_retry=(
                        lambda *, case_id, payload: _invoke_v3_callback_with_retry(
                            runtime=runtime,
                            callback_fn=_failed_callback_fn_for_dispatch(runtime, "final"),
                            job_id=case_id,
                            payload=payload,
                        )
                    ),
                    with_error_contract=_with_error_contract,
                    persist_dispatch_receipt=_persist_dispatch_receipt,
                    trace_register_failure=runtime.trace_store.register_failure,
                    workflow_mark_failed=_workflow_mark_failed,
                    clear_idempotency=runtime.trace_store.clear_idempotency,
                )
            )

        final_callback_outcome = await _run_judge_command_route_guard(
            build_final_dispatch_callback_delivery_route_payload_v3(
                parsed=parsed,
                report_payload=final_report_payload,
                deliver_report_callback_with_failed_fallback=deliver_report_callback_with_failed_fallback_v3,
                report_callback_fn=_report_callback_fn_for_dispatch(runtime, "final"),
                failed_callback_fn=_failed_callback_fn_for_dispatch(runtime, "final"),
                invoke_with_retry=(
                    lambda callback_fn, job_id, payload: _invoke_v3_callback_with_retry(
                        runtime=runtime,
                        callback_fn=callback_fn,
                        job_id=job_id,
                        payload=payload,
                    )
                ),
                build_failed_callback_payload=_build_failed_callback_payload,
            )
        )

        return await _run_judge_command_route_guard(
            build_final_dispatch_callback_result_route_payload_v3(
                parsed=parsed,
                response=response,
                request_payload=request_payload,
                report_payload=final_report_payload,
                callback_outcome=final_callback_outcome,
                callback_status_reported=CALLBACK_STATUS_REPORTED_V3,
                callback_status_failed_reported=CALLBACK_STATUS_FAILED_REPORTED_V3,
                callback_status_failed_callback_failed=CALLBACK_STATUS_FAILED_CALLBACK_FAILED_V3,
                with_error_contract=_with_error_contract,
                persist_dispatch_receipt=_persist_dispatch_receipt,
                trace_register_failure=runtime.trace_store.register_failure,
                trace_register_success=runtime.trace_store.register_success,
                workflow_mark_failed=_workflow_mark_failed,
                workflow_mark_review_required=_workflow_mark_review_required,
                workflow_mark_completed=_workflow_mark_completed,
                build_final_workflow_reported_payload=build_final_workflow_reported_payload_v3,
                build_trace_report_summary=_build_trace_report_summary,
                clear_idempotency=runtime.trace_store.clear_idempotency,
                set_idempotency_success=runtime.trace_store.set_idempotency_success,
                idempotency_ttl_secs=runtime.settings.idempotency_ttl_secs,
                final_judge_workflow_payload=final_judge_workflow_payload,
            )
        )

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
        payload = await _run_case_read_route_guard(
            build_case_overview_route_payload_v3(
                case_id=case_id,
                workflow_get_job=_workflow_get_job,
                workflow_list_events=_workflow_list_events,
                get_dispatch_receipt=_get_dispatch_receipt,
                trace_get=runtime.trace_store.get_trace,
                list_replay_records=_list_replay_records,
                list_audit_alerts=_list_audit_alerts,
                get_claim_ledger_record=_get_claim_ledger_record,
                build_verdict_contract=_build_verdict_contract,
                build_case_evidence_view=_build_case_evidence_view,
                build_judge_core_view=_build_judge_core_view,
                build_case_overview_replay_items=build_case_overview_replay_items_v3,
                build_case_overview_payload=build_case_overview_payload_v3,
                serialize_workflow_job=_serialize_workflow_job,
                serialize_dispatch_receipt=_serialize_dispatch_receipt,
                serialize_alert_item=_serialize_alert_item,
            )
        )
        try:
            _validate_case_overview_contract(payload)
        except ValueError as err:
            _raise_http_500_contract_violation(
                err=err,
                code="case_overview_contract_violation",
            )
        return payload

    @app.get("/internal/judge/cases/{case_id}/claim-ledger")
    async def get_judge_case_claim_ledger(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
        limit: int = Query(default=20, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _run_case_read_route_guard(
            build_case_claim_ledger_route_payload_v3(
                case_id=case_id,
                dispatch_type=dispatch_type,
                limit=limit,
                list_claim_ledger_records=_list_claim_ledger_records,
                get_claim_ledger_record=_get_claim_ledger_record,
                serialize_claim_ledger_record=_serialize_claim_ledger_record,
            )
        )

    @app.get("/internal/judge/cases/{case_id}/courtroom-read-model")
    async def get_judge_case_courtroom_read_model(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
        include_events: bool = Query(default=False),
        include_alerts: bool = Query(default=True),
        alert_limit: int = Query(default=200, ge=1, le=500),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        response_payload = await _run_case_read_route_guard(
            build_case_courtroom_read_model_route_payload_v3(
                case_id=case_id,
                dispatch_type=dispatch_type,
                include_events=include_events,
                include_alerts=include_alerts,
                alert_limit=alert_limit,
                resolve_report_context_for_case=_resolve_report_context_for_case,
                workflow_get_job=_workflow_get_job,
                workflow_list_events=_workflow_list_events,
                trace_get=runtime.trace_store.get_trace,
                get_claim_ledger_record=_get_claim_ledger_record,
                build_verdict_contract=_build_verdict_contract,
                build_case_evidence_view=_build_case_evidence_view,
                build_courtroom_read_model_view=_build_courtroom_read_model_view,
                build_judge_core_view=_build_judge_core_view,
                list_audit_alerts=_list_audit_alerts,
                build_case_courtroom_read_model_payload=build_case_courtroom_read_model_payload_v3,
                serialize_workflow_job=_serialize_workflow_job,
                serialize_alert_item=_serialize_alert_item,
            )
        )
        try:
            _validate_courtroom_read_model_contract(response_payload)
        except ValueError as err:
            _raise_http_500_contract_violation(
                err=err,
                code="courtroom_read_model_contract_violation",
            )
        return response_payload

    @app.get("/internal/judge/courtroom/cases")
    async def list_judge_courtroom_cases(
        x_ai_internal_key: str | None = Header(default=None),
        status: str | None = Query(default=None),
        dispatch_type: str = Query(default="auto"),
        winner: str | None = Query(default=None),
        review_required: bool | None = Query(default=None),
        risk_level: str | None = Query(default=None),
        sla_bucket: str | None = Query(default=None),
        updated_from: datetime | None = Query(default=None),
        updated_to: datetime | None = Query(default=None),
        sort_by: str = Query(default="updated_at"),
        sort_order: str = Query(default="desc"),
        scan_limit: int = Query(default=500, ge=20, le=2000),
        offset: int = Query(default=0, ge=0, le=5000),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _run_case_read_route_guard(
            build_case_courtroom_cases_route_payload_v3(
                status=status,
                dispatch_type=dispatch_type,
                winner=winner,
                review_required=review_required,
                risk_level=risk_level,
                sla_bucket=sla_bucket,
                updated_from=updated_from,
                updated_to=updated_to,
                sort_by=sort_by,
                sort_order=sort_order,
                scan_limit=scan_limit,
                offset=offset,
                limit=limit,
                normalize_workflow_status=_normalize_workflow_status,
                workflow_statuses=WORKFLOW_STATUSES,
                normalize_review_case_risk_level=_normalize_review_case_risk_level,
                review_case_risk_level_values=REVIEW_CASE_RISK_LEVEL_VALUES,
                normalize_review_case_sla_bucket=_normalize_review_case_sla_bucket,
                review_case_sla_bucket_values=REVIEW_CASE_SLA_BUCKET_VALUES,
                normalize_query_datetime=_normalize_query_datetime,
                normalize_courtroom_case_sort_by=_normalize_courtroom_case_sort_by,
                normalize_courtroom_case_sort_order=_normalize_courtroom_case_sort_order,
                courtroom_case_sort_fields=COURTROOM_CASE_SORT_FIELDS,
                workflow_list_jobs=_workflow_list_jobs,
                resolve_report_context_for_case=_resolve_report_context_for_case,
                trace_get=runtime.trace_store.get_trace,
                build_review_case_risk_profile=_build_review_case_risk_profile,
                build_verdict_contract=_build_verdict_contract,
                build_case_evidence_view=_build_case_evidence_view,
                build_courtroom_read_model_view=_build_courtroom_read_model_view,
                serialize_workflow_job=_serialize_workflow_job,
                build_courtroom_read_model_light_summary=_build_courtroom_read_model_light_summary,
                build_courtroom_case_sort_key=_build_courtroom_case_sort_key,
            )
        )

    @app.get("/internal/judge/courtroom/drilldown-bundle")
    async def list_judge_courtroom_drilldown_bundle(
        x_ai_internal_key: str | None = Header(default=None),
        status: str | None = Query(default=None),
        dispatch_type: str = Query(default="auto"),
        winner: str | None = Query(default=None),
        review_required: bool | None = Query(default=None),
        risk_level: str | None = Query(default=None),
        sla_bucket: str | None = Query(default=None),
        updated_from: datetime | None = Query(default=None),
        updated_to: datetime | None = Query(default=None),
        sort_by: str = Query(default="updated_at"),
        sort_order: str = Query(default="desc"),
        scan_limit: int = Query(default=500, ge=20, le=2000),
        offset: int = Query(default=0, ge=0, le=5000),
        limit: int = Query(default=50, ge=1, le=200),
        claim_preview_limit: int = Query(default=10, ge=1, le=100),
        evidence_preview_limit: int = Query(default=10, ge=1, le=100),
        panel_preview_limit: int = Query(default=10, ge=1, le=100),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        payload = await _run_case_read_route_guard(
            build_case_courtroom_drilldown_bundle_route_payload_v3(
                status=status,
                dispatch_type=dispatch_type,
                winner=winner,
                review_required=review_required,
                risk_level=risk_level,
                sla_bucket=sla_bucket,
                updated_from=updated_from,
                updated_to=updated_to,
                sort_by=sort_by,
                sort_order=sort_order,
                scan_limit=scan_limit,
                offset=offset,
                limit=limit,
                claim_preview_limit=claim_preview_limit,
                evidence_preview_limit=evidence_preview_limit,
                panel_preview_limit=panel_preview_limit,
                normalize_workflow_status=_normalize_workflow_status,
                workflow_statuses=WORKFLOW_STATUSES,
                normalize_review_case_risk_level=_normalize_review_case_risk_level,
                review_case_risk_level_values=REVIEW_CASE_RISK_LEVEL_VALUES,
                normalize_review_case_sla_bucket=_normalize_review_case_sla_bucket,
                review_case_sla_bucket_values=REVIEW_CASE_SLA_BUCKET_VALUES,
                normalize_query_datetime=_normalize_query_datetime,
                normalize_courtroom_case_sort_by=_normalize_courtroom_case_sort_by,
                normalize_courtroom_case_sort_order=_normalize_courtroom_case_sort_order,
                courtroom_case_sort_fields=COURTROOM_CASE_SORT_FIELDS,
                workflow_list_jobs=_workflow_list_jobs,
                resolve_report_context_for_case=_resolve_report_context_for_case,
                trace_get=runtime.trace_store.get_trace,
                build_review_case_risk_profile=_build_review_case_risk_profile,
                build_verdict_contract=_build_verdict_contract,
                build_case_evidence_view=_build_case_evidence_view,
                build_courtroom_read_model_view=_build_courtroom_read_model_view,
                build_courtroom_drilldown_bundle_view=_build_courtroom_drilldown_bundle_view,
                build_courtroom_drilldown_action_hints=_build_courtroom_drilldown_action_hints,
                serialize_workflow_job=_serialize_workflow_job,
                build_courtroom_case_sort_key=_build_courtroom_case_sort_key,
            )
        )
        try:
            _validate_courtroom_drilldown_bundle_contract(payload)
        except ValueError as err:
            _raise_http_500_contract_violation(
                err=err,
                code="courtroom_drilldown_bundle_contract_violation",
            )
        return payload

    @app.get("/internal/judge/evidence-claim/ops-queue")
    async def list_judge_evidence_claim_ops_queue(
        x_ai_internal_key: str | None = Header(default=None),
        status: str | None = Query(default=None),
        dispatch_type: str = Query(default="auto"),
        winner: str | None = Query(default=None),
        review_required: bool | None = Query(default=None),
        risk_level: str | None = Query(default=None),
        sla_bucket: str | None = Query(default=None),
        reliability_level: str | None = Query(default=None),
        has_conflict: bool | None = Query(default=None),
        has_unanswered_claim: bool | None = Query(default=None),
        updated_from: datetime | None = Query(default=None),
        updated_to: datetime | None = Query(default=None),
        sort_by: str = Query(default="updated_at"),
        sort_order: str = Query(default="desc"),
        scan_limit: int = Query(default=500, ge=20, le=2000),
        offset: int = Query(default=0, ge=0, le=5000),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        payload = await _run_case_read_route_guard(
            build_case_evidence_claim_ops_queue_route_payload_v3(
                status=status,
                dispatch_type=dispatch_type,
                winner=winner,
                review_required=review_required,
                risk_level=risk_level,
                sla_bucket=sla_bucket,
                reliability_level=reliability_level,
                has_conflict=has_conflict,
                has_unanswered_claim=has_unanswered_claim,
                updated_from=updated_from,
                updated_to=updated_to,
                sort_by=sort_by,
                sort_order=sort_order,
                scan_limit=scan_limit,
                offset=offset,
                limit=limit,
                normalize_workflow_status=_normalize_workflow_status,
                workflow_statuses=WORKFLOW_STATUSES,
                normalize_review_case_risk_level=_normalize_review_case_risk_level,
                review_case_risk_level_values=REVIEW_CASE_RISK_LEVEL_VALUES,
                normalize_review_case_sla_bucket=_normalize_review_case_sla_bucket,
                review_case_sla_bucket_values=REVIEW_CASE_SLA_BUCKET_VALUES,
                normalize_evidence_claim_reliability_level=_normalize_evidence_claim_reliability_level,
                evidence_claim_reliability_level_values=EVIDENCE_CLAIM_RELIABILITY_LEVEL_VALUES,
                normalize_query_datetime=_normalize_query_datetime,
                normalize_evidence_claim_queue_sort_by=_normalize_evidence_claim_queue_sort_by,
                normalize_evidence_claim_queue_sort_order=_normalize_evidence_claim_queue_sort_order,
                evidence_claim_queue_sort_fields=EVIDENCE_CLAIM_QUEUE_SORT_FIELDS,
                workflow_list_jobs=_workflow_list_jobs,
                resolve_report_context_for_case=_resolve_report_context_for_case,
                trace_get=runtime.trace_store.get_trace,
                build_review_case_risk_profile=_build_review_case_risk_profile,
                build_verdict_contract=_build_verdict_contract,
                build_case_evidence_view=_build_case_evidence_view,
                build_courtroom_read_model_view=_build_courtroom_read_model_view,
                build_courtroom_read_model_light_summary=_build_courtroom_read_model_light_summary,
                build_evidence_claim_ops_profile=_build_evidence_claim_ops_profile,
                build_evidence_claim_action_hints=_build_evidence_claim_action_hints,
                serialize_workflow_job=_serialize_workflow_job,
                build_evidence_claim_queue_sort_key=_build_evidence_claim_queue_sort_key,
            )
        )
        try:
            _validate_evidence_claim_ops_queue_contract(payload)
        except ValueError as err:
            _raise_http_500_contract_violation(
                err=err,
                code="evidence_claim_ops_queue_contract_violation",
            )
        return payload

    @app.post("/internal/judge/apps/npc-coach/sessions/{session_id}/advice")
    async def request_npc_coach_advice(
        session_id: int,
        payload: NpcCoachAdviceRequest,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _run_assistant_agent_route_guard(
            build_npc_coach_advice_route_payload_v3(
                session_id=session_id,
                payload=payload,
                agent_kind_npc_coach=AGENT_KIND_NPC_COACH,
                build_shared_room_context=_build_shared_room_context,
                execute_agent=runtime.agent_runtime.execute,
                build_execution_request=AgentExecutionRequest,
                build_assistant_agent_response=_build_assistant_agent_response,
            )
        )

    @app.post("/internal/judge/apps/room-qa/sessions/{session_id}/answer")
    async def request_room_qa_answer(
        session_id: int,
        payload: RoomQaAnswerRequest,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _run_assistant_agent_route_guard(
            build_room_qa_answer_route_payload_v3(
                session_id=session_id,
                payload=payload,
                agent_kind_room_qa=AGENT_KIND_ROOM_QA,
                build_shared_room_context=_build_shared_room_context,
                execute_agent=runtime.agent_runtime.execute,
                build_execution_request=AgentExecutionRequest,
                build_assistant_agent_response=_build_assistant_agent_response,
            )
        )

    def _build_replay_context_dependencies() -> ReplayContextDependencyPack_v3:
        return ReplayContextDependencyPack_v3(
            normalize_replay_dispatch_type=normalize_replay_dispatch_type_v3,
            get_dispatch_receipt=_get_dispatch_receipt,
            choose_replay_dispatch_receipt=choose_replay_dispatch_receipt_v3,
            extract_replay_request_snapshot=extract_replay_request_snapshot_v3,
            resolve_replay_trace_id=resolve_replay_trace_id_v3,
        )

    def _resolve_policy_profile_for_replay(
        *,
        judge_policy_version: str,
        rubric_version: str,
        topic_domain: str,
    ) -> Any:
        return _resolve_policy_profile_or_raise(
            runtime=runtime,
            judge_policy_version=judge_policy_version,
            rubric_version=rubric_version,
            topic_domain=topic_domain,
        )

    def _resolve_prompt_profile_for_replay(*, prompt_registry_version: str) -> Any:
        return _resolve_prompt_profile_or_raise(
            runtime=runtime,
            prompt_registry_version=prompt_registry_version,
        )

    def _resolve_tool_profile_for_replay(*, tool_registry_version: str) -> Any:
        return _resolve_tool_profile_or_raise(
            runtime=runtime,
            tool_registry_version=tool_registry_version,
        )

    def _build_final_report_payload_for_replay(
        *,
        request: FinalDispatchRequest,
        phase_receipts: list[Any],
        fairness_thresholds: dict[str, float],
        panel_runtime_profiles: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        return _build_final_report_payload(
            runtime=runtime,
            request=request,
            phase_receipts=phase_receipts,
            fairness_thresholds=fairness_thresholds,
            panel_runtime_profiles=panel_runtime_profiles,
        )

    async def _attach_judge_agent_runtime_trace_for_replay(
        *,
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
        await _attach_judge_agent_runtime_trace(
            runtime=runtime,
            report_payload=report_payload,
            dispatch_type=dispatch_type,
            case_id=case_id,
            scope_id=scope_id,
            session_id=session_id,
            trace_id=trace_id,
            phase_no=phase_no,
            phase_start_no=phase_start_no,
            phase_end_no=phase_end_no,
        )

    def _attach_policy_trace_snapshot_for_replay(
        *,
        report_payload: dict[str, Any],
        profile: Any,
        prompt_profile: Any,
        tool_profile: Any,
    ) -> None:
        _attach_policy_trace_snapshot(
            runtime=runtime,
            report_payload=report_payload,
            profile=profile,
            prompt_profile=prompt_profile,
            tool_profile=tool_profile,
        )

    def _build_replay_report_dependencies() -> ReplayReportDependencyPack_v3:
        # replay 主路由只保留 HTTP 语义，重算编排统一在 applications 层完成。
        return ReplayReportDependencyPack_v3(
            ensure_registry_runtime_ready=_ensure_registry_runtime_ready,
            final_request_model_validate=FinalDispatchRequest.model_validate,
            phase_request_model_validate=PhaseDispatchRequest.model_validate,
            validate_final_dispatch_request=_validate_final_dispatch_request,
            validate_phase_dispatch_request=_validate_phase_dispatch_request,
            resolve_policy_profile=_resolve_policy_profile_for_replay,
            resolve_prompt_profile=_resolve_prompt_profile_for_replay,
            resolve_tool_profile=_resolve_tool_profile_for_replay,
            list_dispatch_receipts=_list_dispatch_receipts,
            build_final_report_payload=_build_final_report_payload_for_replay,
            resolve_panel_runtime_profiles=_resolve_panel_runtime_profiles,
            build_phase_report_payload=build_phase_report_payload_v3_phase,
            attach_judge_agent_runtime_trace=_attach_judge_agent_runtime_trace_for_replay,
            attach_policy_trace_snapshot=_attach_policy_trace_snapshot_for_replay,
            attach_report_attestation=_attach_report_attestation,
            validate_final_report_payload_contract=_validate_final_report_payload_contract,
            settings=runtime.settings,
            gateway_runtime=runtime.gateway_runtime,
        )

    def _build_replay_finalize_dependencies() -> ReplayFinalizeDependencyPack_v3:
        return ReplayFinalizeDependencyPack_v3(
            provider=runtime.settings.provider,
            get_trace=runtime.trace_store.get_trace,
            trace_register_start=runtime.trace_store.register_start,
            trace_mark_replay=runtime.trace_store.mark_replay,
            append_replay_record=_append_replay_record,
            workflow_mark_replay=_workflow_mark_replay,
            upsert_claim_ledger_record=_upsert_claim_ledger_record,
            build_verdict_contract=_build_verdict_contract,
            build_replay_route_payload=build_replay_route_payload_v3,
            safe_float=_safe_float,
            resolve_winner=_resolve_winner,
            draw_margin=0.8,
            judge_core_stage=JUDGE_CORE_STAGE_REPLAY_COMPUTED,
            judge_core_version=JUDGE_CORE_VERSION,
        )

    async def _run_replay_read_guard(self_awaitable: Awaitable[dict[str, Any]]) -> dict[str, Any]:
        try:
            return await self_awaitable
        except ReplayReadRouteError_v3 as err:
            raise HTTPException(status_code=err.status_code, detail=err.detail) from err

    async def _run_trust_read_guard(self_awaitable: Awaitable[dict[str, Any]]) -> dict[str, Any]:
        try:
            return await self_awaitable
        except TrustReadRouteError_v3 as err:
            raise HTTPException(status_code=err.status_code, detail=err.detail) from err

    def _run_trust_read_guard_sync(builder: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        try:
            return builder()
        except TrustReadRouteError_v3 as err:
            raise HTTPException(status_code=err.status_code, detail=err.detail) from err

    async def _run_trust_challenge_guard(
        self_awaitable: Awaitable[dict[str, Any]],
    ) -> dict[str, Any]:
        try:
            return await self_awaitable
        except (TrustChallengeRouteError_v3, TrustChallengeOpsQueueRouteError_v3) as err:
            raise HTTPException(status_code=err.status_code, detail=err.detail) from err

    async def _run_fairness_route_guard(
        self_awaitable: Awaitable[dict[str, Any]],
    ) -> dict[str, Any]:
        try:
            return await self_awaitable
        except FairnessRouteError_v3 as err:
            raise HTTPException(status_code=err.status_code, detail=err.detail) from err

    async def _run_review_route_guard(
        self_awaitable: Awaitable[dict[str, Any]],
    ) -> dict[str, Any]:
        try:
            return await self_awaitable
        except ReviewRouteError_v3 as err:
            raise HTTPException(status_code=err.status_code, detail=err.detail) from err

    async def _run_panel_runtime_route_guard(
        self_awaitable: Awaitable[dict[str, Any]],
    ) -> dict[str, Any]:
        try:
            return await self_awaitable
        except PanelRuntimeRouteError_v3 as err:
            raise HTTPException(status_code=err.status_code, detail=err.detail) from err

    async def _run_registry_route_guard(
        self_awaitable: Awaitable[dict[str, Any]],
    ) -> dict[str, Any]:
        try:
            return await self_awaitable
        except RegistryRouteErrorV3 as err:
            raise HTTPException(status_code=err.status_code, detail=err.detail) from err

    async def _run_judge_command_route_guard(
        self_awaitable: Awaitable[dict[str, Any]],
    ) -> dict[str, Any]:
        try:
            return await self_awaitable
        except JudgeCommandRouteError_v3 as err:
            raise HTTPException(status_code=err.status_code, detail=err.detail) from err

    async def _run_assistant_agent_route_guard(
        self_awaitable: Awaitable[dict[str, Any]],
    ) -> dict[str, Any]:
        try:
            return await self_awaitable
        except AssistantAgentRouteError_v3 as err:
            raise HTTPException(status_code=err.status_code, detail=err.detail) from err

    async def _run_case_read_route_guard(
        self_awaitable: Awaitable[dict[str, Any]],
    ) -> dict[str, Any]:
        try:
            return await self_awaitable
        except CaseReadRouteError_v3 as err:
            raise HTTPException(status_code=err.status_code, detail=err.detail) from err

    @app.get("/internal/judge/cases/{case_id}/trace")
    async def get_judge_job_trace(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _run_replay_read_guard(
            build_trace_route_read_payload_v3(
                case_id=case_id,
                get_trace=runtime.trace_store.get_trace,
                list_replay_records=_list_replay_records,
                build_trace_route_replay_items=build_trace_route_replay_items_v3,
                build_verdict_contract=_build_verdict_contract,
                build_trace_route_payload=build_trace_route_payload_v3,
            )
        )

    @app.post("/internal/judge/cases/{case_id}/replay")
    async def replay_judge_job(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _run_replay_read_guard(
            build_replay_post_route_payload_v3(
                case_id=case_id,
                dispatch_type=dispatch_type,
                context_dependencies=_build_replay_context_dependencies(),
                report_dependencies=_build_replay_report_dependencies(),
                finalize_dependencies=_build_replay_finalize_dependencies(),
            )
        )

    async def _resolve_report_context_for_case(
        *,
        case_id: int,
        dispatch_type: str,
        not_found_detail: str,
        missing_report_detail: str,
    ) -> dict[str, Any]:
        return await _run_trust_read_guard(
            resolve_trust_report_context_for_case_v3(
                case_id=case_id,
                dispatch_type=dispatch_type,
                get_dispatch_receipt=_get_dispatch_receipt,
                not_found_detail=not_found_detail,
                missing_report_detail=missing_report_detail,
            )
        )

    async def _build_trust_phasea_bundle(
        *,
        case_id: int,
        dispatch_type: str,
    ) -> dict[str, Any]:
        return await _run_trust_read_guard(
            build_trust_phasea_bundle_for_case_v3(
                case_id=case_id,
                dispatch_type=dispatch_type,
                get_dispatch_receipt=_get_dispatch_receipt,
                get_workflow_job=_workflow_get_job,
                list_workflow_events=_workflow_list_events,
                list_audit_alerts=_list_audit_alerts,
                serialize_workflow_job=_serialize_workflow_job,
                provider=runtime.settings.provider,
            )
        )

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
        return _run_trust_read_guard_sync(
            lambda: build_validated_trust_item_route_payload_v3(
                case_id=case_id,
                bundle=bundle,
                item_key="commitment",
                validate_contract=_validate_trust_commitment_contract,
                violation_code="trust_commitment_contract_violation",
            )
        )

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
        return _run_trust_read_guard_sync(
            lambda: build_validated_trust_item_route_payload_v3(
                case_id=case_id,
                bundle=bundle,
                item_key="verdictAttestation",
                validate_contract=_validate_trust_verdict_attestation_contract,
                violation_code="trust_verdict_attestation_contract_violation",
            )
        )

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
        return _run_trust_read_guard_sync(
            lambda: build_validated_trust_item_route_payload_v3(
                case_id=case_id,
                bundle=bundle,
                item_key="challengeReview",
                validate_contract=_validate_trust_challenge_review_contract,
                violation_code="trust_challenge_review_contract_violation",
            )
        )

    @app.get("/internal/judge/trust/challenges/ops-queue")
    async def list_judge_trust_challenge_ops_queue(
        x_ai_internal_key: str | None = Header(default=None),
        status: str | None = Query(default=None),
        dispatch_type: str = Query(default="auto"),
        challenge_state: str | None = Query(default="open"),
        review_state: str | None = Query(default=None),
        priority_level: str | None = Query(default=None),
        sla_bucket: str | None = Query(default=None),
        has_open_alert: bool | None = Query(default=None),
        sort_by: str = Query(default="priority_score"),
        sort_order: str = Query(default="desc"),
        scan_limit: int = Query(default=500, ge=20, le=2000),
        offset: int = Query(default=0, ge=0, le=5000),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _run_trust_challenge_guard(
            build_trust_challenge_ops_queue_route_payload_v3(
                status=status,
                dispatch_type=dispatch_type,
                challenge_state=challenge_state,
                review_state=review_state,
                priority_level=priority_level,
                sla_bucket=sla_bucket,
                has_open_alert=has_open_alert,
                sort_by=sort_by,
                sort_order=sort_order,
                scan_limit=scan_limit,
                offset=offset,
                limit=limit,
                normalize_workflow_status=_normalize_workflow_status,
                workflow_statuses=WORKFLOW_STATUSES,
                normalize_trust_challenge_state_filter=_normalize_trust_challenge_state_filter,
                case_fairness_challenge_states=CASE_FAIRNESS_CHALLENGE_STATES,
                normalize_trust_challenge_review_state=_normalize_trust_challenge_review_state,
                trust_challenge_review_state_values=TRUST_CHALLENGE_REVIEW_STATE_VALUES,
                normalize_trust_challenge_priority_level=_normalize_trust_challenge_priority_level,
                trust_challenge_priority_level_values=TRUST_CHALLENGE_PRIORITY_LEVEL_VALUES,
                normalize_trust_challenge_sla_bucket=_normalize_trust_challenge_sla_bucket,
                trust_challenge_sla_bucket_values=TRUST_CHALLENGE_SLA_BUCKET_VALUES,
                normalize_trust_challenge_sort_by=_normalize_trust_challenge_sort_by,
                trust_challenge_sort_fields=TRUST_CHALLENGE_SORT_FIELDS,
                normalize_trust_challenge_sort_order=_normalize_trust_challenge_sort_order,
                trust_challenge_open_states=TRUST_CHALLENGE_OPEN_STATES,
                workflow_list_jobs=_workflow_list_jobs,
                build_trust_phasea_bundle=_build_trust_phasea_bundle,
                get_trace=runtime.trace_store.get_trace,
                build_trust_challenge_priority_profile=_build_trust_challenge_priority_profile,
                serialize_workflow_job=_serialize_workflow_job,
                build_trust_challenge_ops_queue_item=build_trust_challenge_ops_queue_item_v3,
                build_trust_challenge_action_hints=_build_trust_challenge_action_hints,
                build_trust_challenge_sort_key=_build_trust_challenge_sort_key,
                build_trust_challenge_ops_queue_payload=build_trust_challenge_ops_queue_payload_v3,
                validate_trust_challenge_ops_queue_contract=_validate_trust_challenge_ops_queue_contract,
            )
        )

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
        return await _run_trust_challenge_guard(
            build_trust_challenge_request_payload_v3(
                case_id=case_id,
                dispatch_type=dispatch_type,
                reason_code=reason_code,
                reason=reason,
                requested_by=requested_by,
                auto_accept=auto_accept,
                resolve_report_context_for_case=_resolve_report_context_for_case,
                workflow_get_job=_workflow_get_job,
                workflow_append_event=_workflow_append_event,
                workflow_mark_review_required=_workflow_mark_review_required,
                build_trust_phasea_bundle=_build_trust_phasea_bundle,
                new_challenge_id=_new_challenge_id,
                upsert_audit_alert=runtime.trace_store.upsert_audit_alert,
                sync_audit_alert_to_facts=_sync_audit_alert_to_facts,
                serialize_workflow_job=_serialize_workflow_job,
                trust_challenge_event_type=TRUST_CHALLENGE_EVENT_TYPE,
                trust_challenge_state_requested=TRUST_CHALLENGE_STATE_REQUESTED,
                trust_challenge_state_accepted=TRUST_CHALLENGE_STATE_ACCEPTED,
                trust_challenge_state_under_review=TRUST_CHALLENGE_STATE_UNDER_REVIEW,
            )
        )

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
        return await _run_trust_challenge_guard(
            build_trust_challenge_decision_payload_v3(
                case_id=case_id,
                challenge_id=challenge_id,
                dispatch_type=dispatch_type,
                decision=decision,
                actor=actor,
                reason=reason,
                resolve_report_context_for_case=_resolve_report_context_for_case,
                workflow_get_job=_workflow_get_job,
                workflow_append_event=_workflow_append_event,
                workflow_mark_review_required=_workflow_mark_review_required,
                workflow_mark_completed=_workflow_mark_completed,
                workflow_mark_draw_pending_vote=runtime.workflow_runtime.orchestrator.mark_draw_pending_vote,
                resolve_open_alerts_for_review=_resolve_open_alerts_for_review,
                build_trust_phasea_bundle=_build_trust_phasea_bundle,
                serialize_workflow_job=_serialize_workflow_job,
                trust_challenge_event_type=TRUST_CHALLENGE_EVENT_TYPE,
                trust_challenge_state_closed=TRUST_CHALLENGE_STATE_CLOSED,
                trust_challenge_state_accepted=TRUST_CHALLENGE_STATE_ACCEPTED,
                trust_challenge_state_under_review=TRUST_CHALLENGE_STATE_UNDER_REVIEW,
                trust_challenge_state_verdict_upheld=TRUST_CHALLENGE_STATE_VERDICT_UPHELD,
                trust_challenge_state_verdict_overturned=TRUST_CHALLENGE_STATE_VERDICT_OVERTURNED,
                trust_challenge_state_draw_after_review=TRUST_CHALLENGE_STATE_DRAW_AFTER_REVIEW,
                workflow_transition_error_cls=WorkflowTransitionError,
            )
        )

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
        return _run_trust_read_guard_sync(
            lambda: build_validated_trust_item_route_payload_v3(
                case_id=case_id,
                bundle=bundle,
                item_key="kernelVersion",
                validate_contract=_validate_trust_kernel_version_contract,
                violation_code="trust_kernel_version_contract_violation",
            )
        )

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
        return _run_trust_read_guard_sync(
            lambda: build_trust_audit_anchor_route_payload_v3(
                case_id=case_id,
                bundle=bundle,
                include_payload=include_payload,
                build_audit_anchor_export=build_audit_anchor_export_v3,
                validate_contract=_validate_trust_audit_anchor_contract,
                violation_code="trust_audit_anchor_contract_violation",
            )
        )

    @app.get("/internal/judge/cases/{case_id}/trust/public-verify")
    async def get_judge_trust_public_verify(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        bundle = await _build_trust_phasea_bundle(
            case_id=case_id,
            dispatch_type=dispatch_type,
        )
        return _run_trust_read_guard_sync(
            lambda: build_trust_public_verify_bundle_payload_v3(
                case_id=case_id,
                bundle=bundle,
                build_audit_anchor_export=build_audit_anchor_export_v3,
                build_public_verify_payload=build_public_trust_verify_payload_v3,
                validate_contract=_validate_trust_public_verify_contract,
                violation_code="trust_public_verify_contract_violation",
            )
        )

    @app.post("/internal/judge/cases/{case_id}/attestation/verify")
    async def verify_judge_report_attestation(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _run_trust_read_guard(
            build_trust_attestation_verify_payload_v3(
                case_id=case_id,
                dispatch_type=dispatch_type,
                get_dispatch_receipt=_get_dispatch_receipt,
                verify_report_attestation=verify_report_attestation_v3,
            )
        )

    @app.get("/internal/judge/cases/{case_id}/replay/report")
    async def get_judge_replay_report(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _run_replay_read_guard(
            build_replay_report_route_payload_v3(
                case_id=case_id,
                get_trace=runtime.trace_store.get_trace,
                build_replay_report_payload=build_replay_report_payload_v3,
                get_claim_ledger_record=_get_claim_ledger_record,
                serialize_claim_ledger_record=_serialize_claim_ledger_record,
            )
        )

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
        return build_replay_reports_route_payload_v3(
            status=status,
            winner=winner,
            callback_status=callback_status,
            trace_id=trace_id,
            created_after=created_after,
            created_before=created_before,
            has_audit_alert=has_audit_alert,
            limit=limit,
            include_report=include_report,
            normalize_query_datetime=_normalize_query_datetime,
            trace_query_cls=TraceQuery,
            list_traces=runtime.trace_store.list_traces,
            build_replay_report_payload=build_replay_report_payload_v3,
            build_replay_report_summary=build_replay_report_summary_v3,
            build_replay_reports_list_payload=build_replay_reports_list_payload_v3,
        )

    @app.post("/internal/judge/fairness/benchmark-runs")
    async def upsert_judge_fairness_benchmark_run(
        request: Request,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        raw_payload = await _read_json_object_or_raise_422(request=request)
        return await _run_fairness_route_guard(
            build_fairness_benchmark_upsert_payload_v3(
                raw_payload=raw_payload,
                extract_optional_int=_extract_optional_int,
                extract_optional_float=_extract_optional_float,
                extract_optional_str=_extract_optional_str,
                extract_optional_bool=_extract_optional_bool,
                extract_optional_datetime=_extract_optional_datetime,
                list_fairness_benchmark_runs=_list_fairness_benchmark_runs,
                upsert_fairness_benchmark_run=_upsert_fairness_benchmark_run,
                upsert_audit_alert=runtime.trace_store.upsert_audit_alert,
                sync_audit_alert_to_facts=_sync_audit_alert_to_facts,
                serialize_alert_item=_serialize_alert_item,
                serialize_fairness_benchmark_run=_serialize_fairness_benchmark_run,
            )
        )

    @app.get("/internal/judge/fairness/benchmark-runs")
    async def list_judge_fairness_benchmark_runs(
        x_ai_internal_key: str | None = Header(default=None),
        policy_version: str | None = Query(default=None),
        environment_mode: str | None = Query(default=None),
        status: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _run_fairness_route_guard(
            build_fairness_benchmark_list_payload_v3(
                policy_version=policy_version,
                environment_mode=environment_mode,
                status=status,
                limit=limit,
                list_fairness_benchmark_runs=_list_fairness_benchmark_runs,
                serialize_fairness_benchmark_run=_serialize_fairness_benchmark_run,
            )
        )
    @app.post("/internal/judge/fairness/shadow-runs")
    async def upsert_judge_fairness_shadow_run(
        request: Request,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        raw_payload = await _read_json_object_or_raise_422(request=request)
        return await _run_fairness_route_guard(
            build_fairness_shadow_upsert_payload_v3(
                raw_payload=raw_payload,
                extract_optional_int=_extract_optional_int,
                extract_optional_float=_extract_optional_float,
                extract_optional_str=_extract_optional_str,
                extract_optional_bool=_extract_optional_bool,
                extract_optional_datetime=_extract_optional_datetime,
                list_fairness_benchmark_runs=_list_fairness_benchmark_runs,
                list_fairness_shadow_runs=_list_fairness_shadow_runs,
                upsert_fairness_shadow_run=_upsert_fairness_shadow_run,
                upsert_audit_alert=runtime.trace_store.upsert_audit_alert,
                sync_audit_alert_to_facts=_sync_audit_alert_to_facts,
                serialize_alert_item=_serialize_alert_item,
                serialize_fairness_shadow_run=_serialize_fairness_shadow_run,
            )
        )

    @app.get("/internal/judge/fairness/shadow-runs")
    async def list_judge_fairness_shadow_runs(
        x_ai_internal_key: str | None = Header(default=None),
        policy_version: str | None = Query(default=None),
        benchmark_run_id: str | None = Query(default=None),
        environment_mode: str | None = Query(default=None),
        status: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _run_fairness_route_guard(
            build_fairness_shadow_list_payload_v3(
                policy_version=policy_version,
                benchmark_run_id=benchmark_run_id,
                environment_mode=environment_mode,
                status=status,
                limit=limit,
                list_fairness_shadow_runs=_list_fairness_shadow_runs,
                serialize_fairness_shadow_run=_serialize_fairness_shadow_run,
            )
        )
    @app.get("/internal/judge/fairness/cases/{case_id}")
    async def get_judge_case_fairness(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _run_fairness_route_guard(
            build_fairness_case_detail_payload_v3(
                case_id=case_id,
                dispatch_type=dispatch_type,
                resolve_report_context_for_case=_resolve_report_context_for_case,
                workflow_get_job=_workflow_get_job,
                workflow_list_events=_workflow_list_events,
                list_fairness_benchmark_runs=_list_fairness_benchmark_runs,
                list_fairness_shadow_runs=_list_fairness_shadow_runs,
                build_case_fairness_item=_build_case_fairness_item,
                validate_case_fairness_detail_contract=_validate_case_fairness_detail_contract,
            )
        )

    @app.get("/internal/judge/fairness/cases")
    async def list_judge_case_fairness(
        x_ai_internal_key: str | None = Header(default=None),
        status: str | None = Query(default=None),
        dispatch_type: str | None = Query(default=None),
        winner: str | None = Query(default=None),
        policy_version: str | None = Query(default=None),
        has_drift_breach: bool | None = Query(default=None),
        has_threshold_breach: bool | None = Query(default=None),
        has_shadow_breach: bool | None = Query(default=None),
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
        return await _run_fairness_route_guard(
            build_fairness_case_list_payload_v3(
                status=status,
                dispatch_type=dispatch_type,
                winner=winner,
                policy_version=policy_version,
                has_drift_breach=has_drift_breach,
                has_threshold_breach=has_threshold_breach,
                has_shadow_breach=has_shadow_breach,
                has_open_review=has_open_review,
                gate_conclusion=gate_conclusion,
                challenge_state=challenge_state,
                sort_by=sort_by,
                sort_order=sort_order,
                review_required=review_required,
                panel_high_disagreement=panel_high_disagreement,
                offset=offset,
                limit=limit,
                normalize_workflow_status=_normalize_workflow_status,
                workflow_statuses=WORKFLOW_STATUSES,
                normalize_case_fairness_sort_by=_normalize_case_fairness_sort_by,
                case_fairness_sort_fields=CASE_FAIRNESS_SORT_FIELDS,
                normalize_case_fairness_sort_order=_normalize_case_fairness_sort_order,
                normalize_case_fairness_gate_conclusion=_normalize_case_fairness_gate_conclusion,
                case_fairness_gate_conclusions=CASE_FAIRNESS_GATE_CONCLUSIONS,
                normalize_case_fairness_challenge_state=_normalize_case_fairness_challenge_state,
                case_fairness_challenge_states=CASE_FAIRNESS_CHALLENGE_STATES,
                workflow_list_jobs=_workflow_list_jobs,
                get_trace=runtime.trace_store.get_trace,
                workflow_list_events=_workflow_list_events,
                list_fairness_benchmark_runs=_list_fairness_benchmark_runs,
                list_fairness_shadow_runs=_list_fairness_shadow_runs,
                build_case_fairness_item=_build_case_fairness_item,
                build_case_fairness_sort_key=_build_case_fairness_sort_key,
                build_case_fairness_aggregations=_build_case_fairness_aggregations,
                validate_case_fairness_list_contract=_validate_case_fairness_list_contract,
            )
        )

    @app.get("/internal/judge/fairness/dashboard")
    async def get_judge_fairness_dashboard(
        x_ai_internal_key: str | None = Header(default=None),
        status: str | None = Query(default=None),
        dispatch_type: str | None = Query(default="final"),
        winner: str | None = Query(default=None),
        policy_version: str | None = Query(default=None),
        challenge_state: str | None = Query(default=None),
        window_days: int = Query(default=7, ge=1, le=30),
        top_limit: int = Query(default=10, ge=1, le=50),
        case_scan_limit: int = Query(default=200, ge=20, le=1000),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _run_fairness_route_guard(
            build_fairness_dashboard_payload_v3(
                x_ai_internal_key=x_ai_internal_key,
                status=status,
                dispatch_type=dispatch_type,
                winner=winner,
                policy_version=policy_version,
                challenge_state=challenge_state,
                window_days=window_days,
                top_limit=top_limit,
                case_scan_limit=case_scan_limit,
                collect_fairness_case_items=collect_fairness_case_items_v3,
                list_judge_case_fairness=list_judge_case_fairness,
                build_case_fairness_aggregations=_build_case_fairness_aggregations,
                build_fairness_dashboard_case_trends=_build_fairness_dashboard_case_trends,
                build_fairness_dashboard_run_trends=_build_fairness_dashboard_run_trends,
                build_fairness_dashboard_top_risk_cases=_build_fairness_dashboard_top_risk_cases,
                list_fairness_benchmark_runs=_list_fairness_benchmark_runs,
                list_fairness_shadow_runs=_list_fairness_shadow_runs,
                validate_fairness_dashboard_contract=_validate_fairness_dashboard_contract,
            )
        )

    @app.get("/internal/judge/fairness/calibration-pack")
    async def get_judge_fairness_calibration_pack(
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str | None = Query(default="final"),
        status: str | None = Query(default=None),
        winner: str | None = Query(default=None),
        policy_version: str | None = Query(default=None),
        challenge_state: str | None = Query(default=None),
        case_scan_limit: int = Query(default=200, ge=20, le=1000),
        risk_limit: int = Query(default=50, ge=1, le=200),
        benchmark_limit: int = Query(default=200, ge=1, le=500),
        shadow_limit: int = Query(default=200, ge=1, le=500),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await build_fairness_calibration_pack_payload_v3(
            x_ai_internal_key=x_ai_internal_key,
            dispatch_type=dispatch_type,
            status=status,
            winner=winner,
            policy_version=policy_version,
            challenge_state=challenge_state,
            case_scan_limit=case_scan_limit,
            risk_limit=risk_limit,
            benchmark_limit=benchmark_limit,
            shadow_limit=shadow_limit,
            collect_fairness_case_items=collect_fairness_case_items_v3,
            list_judge_case_fairness=list_judge_case_fairness,
            list_fairness_benchmark_runs=_list_fairness_benchmark_runs,
            list_fairness_shadow_runs=_list_fairness_shadow_runs,
            build_fairness_dashboard_top_risk_cases=_build_fairness_dashboard_top_risk_cases,
            build_fairness_calibration_threshold_suggestions=_build_fairness_calibration_threshold_suggestions,
            build_fairness_calibration_drift_summary=_build_fairness_calibration_drift_summary,
            build_fairness_calibration_risk_items=_build_fairness_calibration_risk_items,
            build_fairness_calibration_on_env_input_template=_build_fairness_calibration_on_env_input_template,
        )

    @app.get("/internal/judge/fairness/policy-calibration-advisor")
    async def get_judge_fairness_policy_calibration_advisor(
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str | None = Query(default="final"),
        status: str | None = Query(default=None),
        winner: str | None = Query(default=None),
        policy_version: str | None = Query(default=None),
        challenge_state: str | None = Query(default=None),
        case_scan_limit: int = Query(default=200, ge=20, le=1000),
        risk_limit: int = Query(default=50, ge=1, le=200),
        benchmark_limit: int = Query(default=200, ge=1, le=500),
        shadow_limit: int = Query(default=200, ge=1, le=500),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await build_fairness_policy_calibration_advisor_payload_v3(
            x_ai_internal_key=x_ai_internal_key,
            dispatch_type=dispatch_type,
            status=status,
            winner=winner,
            policy_version=policy_version,
            challenge_state=challenge_state,
            case_scan_limit=case_scan_limit,
            risk_limit=risk_limit,
            benchmark_limit=benchmark_limit,
            shadow_limit=shadow_limit,
            collect_fairness_case_items=collect_fairness_case_items_v3,
            list_judge_case_fairness=list_judge_case_fairness,
            list_fairness_benchmark_runs=_list_fairness_benchmark_runs,
            list_fairness_shadow_runs=_list_fairness_shadow_runs,
            build_fairness_dashboard_top_risk_cases=_build_fairness_dashboard_top_risk_cases,
            build_fairness_calibration_threshold_suggestions=_build_fairness_calibration_threshold_suggestions,
            build_fairness_calibration_drift_summary=_build_fairness_calibration_drift_summary,
            build_fairness_calibration_risk_items=_build_fairness_calibration_risk_items,
            evaluate_policy_release_fairness_gate=_evaluate_policy_release_fairness_gate,
            build_fairness_policy_calibration_recommended_actions=_build_fairness_policy_calibration_recommended_actions,
        )

    @app.get("/internal/judge/ops/read-model/pack")
    async def get_judge_ops_read_model_pack(
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str | None = Query(default="final"),
        policy_version: str | None = Query(default=None),
        window_days: int = Query(default=7, ge=1, le=30),
        top_limit: int = Query(default=10, ge=1, le=50),
        case_scan_limit: int = Query(default=200, ge=20, le=1000),
        include_case_trust: bool = Query(default=True),
        trust_case_limit: int = Query(default=5, ge=1, le=20),
        dependency_limit: int = Query(default=200, ge=1, le=500),
        usage_preview_limit: int = Query(default=20, ge=1, le=200),
        release_limit: int = Query(default=50, ge=1, le=200),
        audit_limit: int = Query(default=100, ge=1, le=200),
        calibration_risk_limit: int = Query(default=50, ge=1, le=200),
        calibration_benchmark_limit: int = Query(default=200, ge=1, le=500),
        calibration_shadow_limit: int = Query(default=200, ge=1, le=500),
        panel_profile_scan_limit: int = Query(default=600, ge=50, le=5000),
        panel_group_limit: int = Query(default=50, ge=1, le=200),
        panel_attention_limit: int = Query(default=20, ge=1, le=100),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        try:
            return await build_ops_read_model_pack_route_payload(
                x_ai_internal_key=x_ai_internal_key,
                dispatch_type=dispatch_type,
                policy_version=policy_version,
                window_days=window_days,
                top_limit=top_limit,
                case_scan_limit=case_scan_limit,
                include_case_trust=include_case_trust,
                trust_case_limit=trust_case_limit,
                dependency_limit=dependency_limit,
                usage_preview_limit=usage_preview_limit,
                release_limit=release_limit,
                audit_limit=audit_limit,
                calibration_risk_limit=calibration_risk_limit,
                calibration_benchmark_limit=calibration_benchmark_limit,
                calibration_shadow_limit=calibration_shadow_limit,
                panel_profile_scan_limit=panel_profile_scan_limit,
                panel_group_limit=panel_group_limit,
                panel_attention_limit=panel_attention_limit,
                trust_challenge_open_states=TRUST_CHALLENGE_OPEN_STATES,
                judge_role_order=JUDGE_ROLE_ORDER,
                get_trace=runtime.trace_store.get_trace,
                get_judge_fairness_dashboard=get_judge_fairness_dashboard,
                get_registry_governance_overview=get_registry_governance_overview,
                get_registry_prompt_tool_governance=get_registry_prompt_tool_governance,
                get_policy_registry_dependency_health=get_policy_registry_dependency_health,
                get_judge_fairness_policy_calibration_advisor=get_judge_fairness_policy_calibration_advisor,
                get_panel_runtime_readiness=get_panel_runtime_readiness,
                list_judge_courtroom_cases=list_judge_courtroom_cases,
                list_judge_courtroom_drilldown_bundle=list_judge_courtroom_drilldown_bundle,
                list_judge_evidence_claim_ops_queue=list_judge_evidence_claim_ops_queue,
                list_judge_trust_challenge_ops_queue=list_judge_trust_challenge_ops_queue,
                list_judge_review_jobs=list_judge_review_jobs,
                simulate_policy_release_gate=simulate_policy_release_gate,
                get_judge_case_courtroom_read_model=get_judge_case_courtroom_read_model,
                get_judge_trust_public_verify=get_judge_trust_public_verify,
                normalize_fairness_gate_decision=_normalize_fairness_gate_decision,
                summarize_ops_read_model_pack_trust_items_fn=summarize_ops_read_model_pack_trust_items,
                summarize_ops_read_model_pack_review_items_fn=summarize_ops_read_model_pack_review_items,
                build_ops_read_model_pack_case_chain_coverage_fn=build_ops_read_model_pack_case_chain_coverage,
                build_ops_read_model_pack_fairness_gate_overview_fn=build_ops_read_model_pack_fairness_gate_overview,
                build_ops_read_model_pack_policy_kernel_binding_fn=build_ops_read_model_pack_policy_kernel_binding,
                build_ops_read_model_pack_adaptive_summary_fn=build_ops_read_model_pack_adaptive_summary,
                build_ops_read_model_pack_trust_overview_fn=build_ops_read_model_pack_trust_overview,
                build_ops_read_model_pack_judge_workflow_coverage_fn=build_ops_read_model_pack_judge_workflow_coverage,
                build_ops_read_model_pack_filters_fn=build_ops_read_model_pack_filters,
                build_ops_read_model_pack_v5_payload_fn=build_ops_read_model_pack_v5_payload,
            )
        except ValueError as err:
            _raise_http_500_contract_violation(
                err=err,
                code="ops_read_model_pack_v5_contract_violation",
            )

    @app.get("/internal/judge/panels/runtime/profiles")
    async def list_panel_runtime_profiles(
        x_ai_internal_key: str | None = Header(default=None),
        status: str | None = Query(default=None),
        dispatch_type: str | None = Query(default=None),
        winner: str | None = Query(default=None),
        policy_version: str | None = Query(default=None),
        has_open_review: bool | None = Query(default=None),
        gate_conclusion: str | None = Query(default=None),
        challenge_state: str | None = Query(default=None),
        review_required: bool | None = Query(default=None),
        panel_high_disagreement: bool | None = Query(default=None),
        judge_id: str | None = Query(default=None),
        profile_source: str | None = Query(default=None),
        profile_id: str | None = Query(default=None),
        model_strategy: str | None = Query(default=None),
        strategy_slot: str | None = Query(default=None),
        domain_slot: str | None = Query(default=None),
        sort_by: str = Query(default="updated_at"),
        sort_order: str = Query(default="desc"),
        offset: int = Query(default=0, ge=0, le=5000),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        try:
            return await _run_panel_runtime_route_guard(
                build_panel_runtime_profiles_route_payload_v3(
                    list_judge_case_fairness=list_judge_case_fairness,
                    build_panel_runtime_profile_item=_build_panel_runtime_profile_item,
                    build_panel_runtime_profile_sort_key=_build_panel_runtime_profile_sort_key,
                    build_panel_runtime_profile_aggregations=_build_panel_runtime_profile_aggregations,
                    validate_panel_runtime_profile_contract=_validate_panel_runtime_profile_contract,
                    panel_judge_ids=PANEL_JUDGE_IDS,
                    panel_runtime_profile_source_values=PANEL_RUNTIME_PROFILE_SOURCE_VALUES,
                    panel_runtime_profile_sort_fields=PANEL_RUNTIME_PROFILE_SORT_FIELDS,
                    normalize_workflow_status=_normalize_workflow_status,
                    normalize_panel_runtime_profile_source=_normalize_panel_runtime_profile_source,
                    normalize_panel_runtime_profile_sort_by=_normalize_panel_runtime_profile_sort_by,
                    normalize_panel_runtime_profile_sort_order=_normalize_panel_runtime_profile_sort_order,
                    normalize_case_fairness_gate_conclusion=_normalize_case_fairness_gate_conclusion,
                    normalize_case_fairness_challenge_state=_normalize_case_fairness_challenge_state,
                    x_ai_internal_key=x_ai_internal_key,
                    status=status,
                    dispatch_type=dispatch_type,
                    winner=winner,
                    policy_version=policy_version,
                    has_open_review=has_open_review,
                    gate_conclusion=gate_conclusion,
                    challenge_state=challenge_state,
                    review_required=review_required,
                    panel_high_disagreement=panel_high_disagreement,
                    judge_id=judge_id,
                    profile_source=profile_source,
                    profile_id=profile_id,
                    model_strategy=model_strategy,
                    strategy_slot=strategy_slot,
                    domain_slot=domain_slot,
                    sort_by=sort_by,
                    sort_order=sort_order,
                    offset=offset,
                    limit=limit,
                )
            )
        except ValueError as err:
            _raise_http_500_contract_violation(
                err=err,
                code="panel_runtime_profile_contract_violation",
            )

    @app.get("/internal/judge/panels/runtime/readiness")
    async def get_panel_runtime_readiness(
        x_ai_internal_key: str | None = Header(default=None),
        status: str | None = Query(default=None),
        dispatch_type: str | None = Query(default="final"),
        winner: str | None = Query(default=None),
        policy_version: str | None = Query(default=None),
        has_open_review: bool | None = Query(default=None),
        gate_conclusion: str | None = Query(default=None),
        challenge_state: str | None = Query(default=None),
        review_required: bool | None = Query(default=None),
        panel_high_disagreement: bool | None = Query(default=None),
        judge_id: str | None = Query(default=None),
        profile_source: str | None = Query(default=None),
        profile_id: str | None = Query(default=None),
        model_strategy: str | None = Query(default=None),
        strategy_slot: str | None = Query(default=None),
        domain_slot: str | None = Query(default=None),
        profile_scan_limit: int = Query(default=600, ge=50, le=5000),
        group_limit: int = Query(default=50, ge=1, le=200),
        attention_limit: int = Query(default=20, ge=1, le=100),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _run_panel_runtime_route_guard(
            build_panel_runtime_readiness_route_payload_v3(
                list_panel_runtime_profiles=list_panel_runtime_profiles,
                build_panel_runtime_readiness_summary=_build_panel_runtime_readiness_summary,
                panel_judge_ids=PANEL_JUDGE_IDS,
                panel_runtime_profile_source_values=PANEL_RUNTIME_PROFILE_SOURCE_VALUES,
                normalize_workflow_status=_normalize_workflow_status,
                normalize_panel_runtime_profile_source=_normalize_panel_runtime_profile_source,
                normalize_case_fairness_gate_conclusion=_normalize_case_fairness_gate_conclusion,
                normalize_case_fairness_challenge_state=_normalize_case_fairness_challenge_state,
                x_ai_internal_key=x_ai_internal_key,
                status=status,
                dispatch_type=dispatch_type,
                winner=winner,
                policy_version=policy_version,
                has_open_review=has_open_review,
                gate_conclusion=gate_conclusion,
                challenge_state=challenge_state,
                review_required=review_required,
                panel_high_disagreement=panel_high_disagreement,
                judge_id=judge_id,
                profile_source=profile_source,
                profile_id=profile_id,
                model_strategy=model_strategy,
                strategy_slot=strategy_slot,
                domain_slot=domain_slot,
                profile_scan_limit=profile_scan_limit,
                group_limit=group_limit,
                attention_limit=attention_limit,
            )
        )

    @app.get("/internal/judge/review/cases")
    async def list_judge_review_jobs(
        x_ai_internal_key: str | None = Header(default=None),
        status: str = Query(default="review_required"),
        dispatch_type: str | None = Query(default=None),
        risk_level: str | None = Query(default=None),
        sla_bucket: str | None = Query(default=None),
        challenge_state: str | None = Query(default=None),
        trust_review_state: str | None = Query(default=None),
        unified_priority_level: str | None = Query(default=None),
        sort_by: str = Query(default="updated_at"),
        sort_order: str = Query(default="desc"),
        scan_limit: int = Query(default=200, ge=20, le=1000),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        try:
            normalized_filters = normalize_review_case_filters_v3(
                status=status,
                dispatch_type=dispatch_type,
                risk_level=risk_level,
                sla_bucket=sla_bucket,
                challenge_state=challenge_state,
                trust_review_state=trust_review_state,
                unified_priority_level=unified_priority_level,
                sort_by=sort_by,
                sort_order=sort_order,
                scan_limit=scan_limit,
                normalize_workflow_status=_normalize_workflow_status,
                workflow_statuses=WORKFLOW_STATUSES,
                normalize_review_case_risk_level=_normalize_review_case_risk_level,
                review_case_risk_level_values=REVIEW_CASE_RISK_LEVEL_VALUES,
                normalize_review_case_sla_bucket=_normalize_review_case_sla_bucket,
                review_case_sla_bucket_values=REVIEW_CASE_SLA_BUCKET_VALUES,
                normalize_trust_challenge_state_filter=_normalize_trust_challenge_state_filter,
                case_fairness_challenge_states=CASE_FAIRNESS_CHALLENGE_STATES,
                normalize_trust_challenge_review_state=_normalize_trust_challenge_review_state,
                trust_challenge_review_state_values=TRUST_CHALLENGE_REVIEW_STATE_VALUES,
                normalize_trust_challenge_priority_level=_normalize_trust_challenge_priority_level,
                trust_challenge_priority_level_values=TRUST_CHALLENGE_PRIORITY_LEVEL_VALUES,
                normalize_review_case_sort_by=_normalize_review_case_sort_by,
                review_case_sort_fields=REVIEW_CASE_SORT_FIELDS,
                normalize_review_case_sort_order=_normalize_review_case_sort_order,
            )
            return await build_review_cases_list_payload_v3(
                normalized_status=str(normalized_filters["status"]),
                normalized_dispatch_type=cast(
                    str | None, normalized_filters["dispatchType"]
                ),
                normalized_risk_level=cast(
                    str | None, normalized_filters["riskLevel"]
                ),
                normalized_sla_bucket=cast(
                    str | None, normalized_filters["slaBucket"]
                ),
                normalized_challenge_state=cast(
                    str | None, normalized_filters["challengeState"]
                ),
                normalized_trust_review_state=cast(
                    str | None, normalized_filters["trustReviewState"]
                ),
                normalized_unified_priority_level=cast(
                    str | None, normalized_filters["unifiedPriorityLevel"]
                ),
                normalized_sort_by=str(normalized_filters["sortBy"]),
                normalized_sort_order=str(normalized_filters["sortOrder"]),
                normalized_scan_limit=int(normalized_filters["scanLimit"]),
                limit=limit,
                trust_challenge_open_states=TRUST_CHALLENGE_OPEN_STATES,
                workflow_list_jobs=_workflow_list_jobs,
                get_trace=runtime.trace_store.get_trace,
                workflow_list_events=_workflow_list_events,
                list_audit_alerts=_list_audit_alerts,
                build_challenge_review_registry=build_challenge_review_registry_v3,
                build_review_case_risk_profile=_build_review_case_risk_profile,
                build_trust_challenge_priority_profile=_build_trust_challenge_priority_profile,
                build_review_trust_unified_priority_profile=_build_review_trust_unified_priority_profile,
                serialize_workflow_job=_serialize_workflow_job,
                build_review_case_sort_key=_build_review_case_sort_key,
            )
        except ValueError as err:
            _raise_http_422_from_value_error(err=err)

    @app.get("/internal/judge/review/cases/{case_id}")
    async def get_judge_review_job(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        try:
            return await build_review_case_detail_payload_v3(
                case_id=case_id,
                workflow_get_job=_workflow_get_job,
                workflow_list_events=_workflow_list_events,
                list_audit_alerts=_list_audit_alerts,
                get_trace=runtime.trace_store.get_trace,
                serialize_workflow_job=_serialize_workflow_job,
                serialize_alert_item=_serialize_alert_item,
            )
        except LookupError as err:
            _raise_http_404_from_lookup_error(err=err)

    @app.post("/internal/judge/review/cases/{case_id}/decision")
    async def decide_judge_review_job(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        decision: str = Query(default="approve"),
        actor: str | None = Query(default=None),
        reason: str | None = Query(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        try:
            return await _run_review_route_guard(
                build_review_case_decision_payload_v3(
                case_id=case_id,
                decision=decision,
                actor=actor,
                reason=reason,
                workflow_get_job=_workflow_get_job,
                workflow_mark_completed=_workflow_mark_completed,
                workflow_mark_failed=_workflow_mark_failed,
                resolve_open_alerts_for_review=_resolve_open_alerts_for_review,
                serialize_workflow_job=_serialize_workflow_job,
            )
            )
        except ValueError as err:
            _raise_http_422_from_value_error(err=err)
        except LookupError as err:
            _raise_http_404_from_lookup_error(err=err)

    @app.get("/internal/judge/cases/{case_id}/alerts")
    async def list_judge_job_alerts(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        status: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await build_case_alerts_payload_v3(
            case_id=case_id,
            status=status,
            limit=limit,
            list_audit_alerts=_list_audit_alerts,
            serialize_alert_item=_serialize_alert_item,
        )

    async def _transition_judge_alert_status(
        *,
        case_id: int,
        alert_id: str,
        to_status: str,
        actor: str | None,
        reason: str | None,
    ) -> dict[str, Any]:
        return await _run_review_route_guard(
            build_alert_status_transition_payload_v3(
                job_id=case_id,
                alert_id=alert_id,
                to_status=to_status,
                actor=actor,
                reason=reason,
                transition_audit_alert=runtime.trace_store.transition_audit_alert,
                sync_audit_alert_to_facts=_sync_audit_alert_to_facts,
                facts_transition_audit_alert=runtime.workflow_runtime.facts.transition_audit_alert,
                serialize_alert_item=_serialize_alert_item,
            )
        )

    @app.post("/internal/judge/cases/{case_id}/alerts/{alert_id}/ack")
    async def ack_judge_job_alert(
        case_id: int,
        alert_id: str,
        x_ai_internal_key: str | None = Header(default=None),
        actor: str | None = Query(default=None),
        reason: str | None = Query(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _transition_judge_alert_status(
            case_id=case_id,
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
        return await _transition_judge_alert_status(
            case_id=case_id,
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
        try:
            return await build_alert_ops_view_payload_v3(
                alert_type=alert_type,
                status=status,
                delivery_status=delivery_status,
                registry_type=registry_type,
                policy_version=policy_version,
                gate_code=gate_code,
                gate_actor=gate_actor,
                override_applied=override_applied,
                fields_mode=fields_mode,
                include_trend=include_trend,
                trend_window_minutes=trend_window_minutes,
                trend_bucket_minutes=trend_bucket_minutes,
                offset=offset,
                limit=limit,
                normalize_ops_alert_status=_normalize_ops_alert_status,
                normalize_ops_alert_delivery_status=_normalize_ops_alert_delivery_status,
                normalize_ops_alert_fields_mode=_normalize_ops_alert_fields_mode,
                ops_registry_alert_types=OPS_REGISTRY_ALERT_TYPES,
                ops_alert_status_values=OPS_ALERT_STATUS_VALUES,
                ops_alert_delivery_status_values=OPS_ALERT_DELIVERY_STATUS_VALUES,
                ops_alert_fields_mode_values=OPS_ALERT_FIELDS_MODE_VALUES,
                list_audit_alerts=_list_audit_alerts,
                list_alert_outbox=runtime.trace_store.list_alert_outbox,
                build_registry_alert_ops_view=_build_registry_alert_ops_view,
            )
        except ValueError as err:
            _raise_http_422_from_value_error(err=err)

    @app.get("/internal/judge/alerts/outbox")
    async def list_judge_alert_outbox(
        x_ai_internal_key: str | None = Header(default=None),
        delivery_status: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return build_alert_outbox_route_payload_v3(
            delivery_status=delivery_status,
            limit=limit,
            list_alert_outbox=runtime.trace_store.list_alert_outbox,
            serialize_outbox_event=_serialize_outbox_event,
        )

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
        try:
            return build_alert_outbox_delivery_payload_v3(
                item=item,
                serialize_outbox_event=_serialize_outbox_event,
            )
        except LookupError as err:
            _raise_http_404_from_lookup_error(err=err)

    @app.get("/internal/judge/rag/diagnostics")
    async def get_rag_diagnostics(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        try:
            return build_rag_diagnostics_payload_v3(
                case_id=case_id,
                get_trace=runtime.trace_store.get_trace,
            )
        except LookupError as err:
            _raise_http_404_from_lookup_error(err=err)

    return app


def create_default_app(*, load_settings_fn: LoadSettingsFn = load_settings) -> FastAPI:
    return create_app(
        create_runtime(
            settings=load_settings_fn(),
        )
    )
