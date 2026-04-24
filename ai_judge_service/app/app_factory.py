from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
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
    build_assistant_agent_response as build_assistant_agent_response_v3,
)
from .applications.assistant_agent_routes import (
    build_npc_coach_advice_route_payload as build_npc_coach_advice_route_payload_v3,
)
from .applications.assistant_agent_routes import (
    build_room_qa_answer_route_payload as build_room_qa_answer_route_payload_v3,
)
from .applications.case_courtroom_views import (
    build_case_evidence_view as build_case_evidence_view_v3,
)
from .applications.case_courtroom_views import (
    build_courtroom_case_sort_key as build_courtroom_case_sort_key_v3,
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
    normalize_courtroom_case_sort_by as normalize_courtroom_case_sort_by_v3,
)
from .applications.case_courtroom_views import (
    normalize_courtroom_case_sort_order as normalize_courtroom_case_sort_order_v3,
)
from .applications.case_courtroom_views import (
    normalize_evidence_claim_queue_sort_by as normalize_evidence_claim_queue_sort_by_v3,
)
from .applications.case_courtroom_views import (
    normalize_evidence_claim_queue_sort_order as normalize_evidence_claim_queue_sort_order_v3,
)
from .applications.case_courtroom_views import (
    normalize_evidence_claim_reliability_level as normalize_evidence_claim_reliability_level_v3,
)
from .applications.case_courtroom_views import (
    serialize_claim_ledger_record as serialize_claim_ledger_record_v3,
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
    build_case_fairness_aggregations as build_case_fairness_aggregations_v3,
)
from .applications.fairness_runtime_routes import (
    build_case_fairness_item as build_case_fairness_item_v3,
)
from .applications.fairness_runtime_routes import (
    build_case_fairness_sort_key as build_case_fairness_sort_key_v3,
)
from .applications.fairness_runtime_routes import (
    build_fairness_benchmark_list_payload as build_fairness_benchmark_list_payload_v3,
)
from .applications.fairness_runtime_routes import (
    build_fairness_benchmark_upsert_payload as build_fairness_benchmark_upsert_payload_v3,
)
from .applications.fairness_runtime_routes import (
    build_fairness_calibration_on_env_input_template as build_fairness_calibration_on_env_input_template_v3,
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
    build_fairness_policy_calibration_recommended_actions as build_fairness_policy_calibration_recommended_actions_v3,
)
from .applications.fairness_runtime_routes import (
    build_fairness_shadow_list_payload as build_fairness_shadow_list_payload_v3,
)
from .applications.fairness_runtime_routes import (
    build_fairness_shadow_upsert_payload as build_fairness_shadow_upsert_payload_v3,
)
from .applications.fairness_runtime_routes import (
    normalize_case_fairness_challenge_state as normalize_case_fairness_challenge_state_v3,
)
from .applications.fairness_runtime_routes import (
    normalize_case_fairness_gate_conclusion as normalize_case_fairness_gate_conclusion_v3,
)
from .applications.fairness_runtime_routes import (
    normalize_case_fairness_sort_by as normalize_case_fairness_sort_by_v3,
)
from .applications.fairness_runtime_routes import (
    normalize_case_fairness_sort_order as normalize_case_fairness_sort_order_v3,
)
from .applications.judge_app_domain import JUDGE_ROLE_ORDER
from .applications.judge_command_routes import (
    JudgeCommandRouteError as JudgeCommandRouteError_v3,
)
from .applications.judge_command_routes import (
    attach_policy_trace_snapshot as attach_policy_trace_snapshot_v3,
)
from .applications.judge_command_routes import (
    build_blindization_rejection_route_payload as build_blindization_rejection_route_payload_v3,
)
from .applications.judge_command_routes import (
    build_case_create_route_payload as build_case_create_route_payload_v3,
)
from .applications.judge_command_routes import (
    build_dispatch_meta_from_raw as build_dispatch_meta_from_raw_v3,
)
from .applications.judge_command_routes import (
    build_error_contract as build_error_contract_v3,
)
from .applications.judge_command_routes import (
    build_failed_callback_payload as build_failed_callback_payload_v3,
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
    build_final_report_payload_for_dispatch as build_final_report_payload_for_dispatch_v3,
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
from .applications.judge_command_routes import (
    build_receipt_dims_from_raw as build_receipt_dims_from_raw_v3,
)
from .applications.judge_command_routes import (
    build_workflow_job as build_workflow_job_v3,
)
from .applications.judge_command_routes import (
    extract_optional_bool as extract_optional_bool_v3,
)
from .applications.judge_command_routes import (
    extract_optional_datetime as extract_optional_datetime_v3,
)
from .applications.judge_command_routes import (
    extract_optional_float as extract_optional_float_v3,
)
from .applications.judge_command_routes import (
    extract_optional_int as extract_optional_int_v3,
)
from .applications.judge_command_routes import (
    extract_optional_str as extract_optional_str_v3,
)
from .applications.judge_command_routes import (
    find_sensitive_key_hits as find_sensitive_key_hits_v3,
)
from .applications.judge_command_routes import (
    invoke_callback_with_retry as invoke_callback_with_retry_v3,
)
from .applications.judge_command_routes import (
    resolve_failed_callback_fn_for_dispatch as resolve_failed_callback_fn_for_dispatch_v3,
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
    resolve_report_callback_fn_for_dispatch as resolve_report_callback_fn_for_dispatch_v3,
)
from .applications.judge_command_routes import (
    resolve_tool_profile_or_raise as resolve_tool_profile_or_raise_v3,
)
from .applications.judge_command_routes import (
    resolve_winner as resolve_winner_v3,
)
from .applications.judge_command_routes import (
    safe_float as safe_float_v3,
)
from .applications.judge_command_routes import (
    save_dispatch_receipt as save_dispatch_receipt_v3,
)
from .applications.judge_command_routes import (
    validate_final_dispatch_request as validate_final_dispatch_request_v3,
)
from .applications.judge_command_routes import (
    validate_phase_dispatch_request as validate_phase_dispatch_request_v3,
)
from .applications.judge_command_routes import (
    with_error_contract as with_error_contract_v3,
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
    build_panel_runtime_profile_aggregations as build_panel_runtime_profile_aggregations_v3,
)
from .applications.panel_runtime_routes import (
    build_panel_runtime_profile_item as build_panel_runtime_profile_item_v3,
)
from .applications.panel_runtime_routes import (
    build_panel_runtime_profile_sort_key as build_panel_runtime_profile_sort_key_v3,
)
from .applications.panel_runtime_routes import (
    build_panel_runtime_profiles_route_payload as build_panel_runtime_profiles_route_payload_v3,
)
from .applications.panel_runtime_routes import (
    build_panel_runtime_readiness_route_payload as build_panel_runtime_readiness_route_payload_v3,
)
from .applications.panel_runtime_routes import (
    build_panel_runtime_readiness_summary as build_panel_runtime_readiness_summary_v3,
)
from .applications.panel_runtime_routes import (
    normalize_panel_runtime_profile_sort_by as normalize_panel_runtime_profile_sort_by_v3,
)
from .applications.panel_runtime_routes import (
    normalize_panel_runtime_profile_sort_order as normalize_panel_runtime_profile_sort_order_v3,
)
from .applications.panel_runtime_routes import (
    normalize_panel_runtime_profile_source as normalize_panel_runtime_profile_source_v3,
)
from .applications.registry_governance_routes import (
    RegistryGovernanceRouteDependencyPack as RegistryGovernanceRouteDependencyPack_v3,
)
from .applications.registry_governance_routes import (
    serialize_policy_profile_with_domain_family as serialize_policy_profile_with_domain_family_v3,
)
from .applications.registry_ops_views import (
    build_registry_alert_ops_view as build_registry_alert_ops_view_v3,
)
from .applications.registry_ops_views import (
    build_registry_audit_ops_view as build_registry_audit_ops_view_v3,
)
from .applications.registry_ops_views import (
    build_registry_dependency_overview as build_registry_dependency_overview_v3,
)
from .applications.registry_ops_views import (
    build_registry_dependency_trend as build_registry_dependency_trend_v3,
)
from .applications.registry_ops_views import (
    build_registry_prompt_tool_action_hints as build_registry_prompt_tool_action_hints_v3,
)
from .applications.registry_ops_views import (
    build_registry_prompt_tool_risk_items as build_registry_prompt_tool_risk_items_v3,
)
from .applications.registry_ops_views import (
    build_registry_prompt_tool_usage_rows as build_registry_prompt_tool_usage_rows_v3,
)
from .applications.registry_ops_views import (
    normalize_ops_alert_delivery_status as normalize_ops_alert_delivery_status_v3,
)
from .applications.registry_ops_views import (
    normalize_ops_alert_fields_mode as normalize_ops_alert_fields_mode_v3,
)
from .applications.registry_ops_views import (
    normalize_ops_alert_status as normalize_ops_alert_status_v3,
)
from .applications.registry_ops_views import (
    normalize_registry_audit_action as normalize_registry_audit_action_v3,
)
from .applications.registry_ops_views import (
    normalize_registry_dependency_trend_status as normalize_registry_dependency_trend_status_v3,
)
from .applications.registry_routes import RegistryRouteError as RegistryRouteErrorV3
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
    build_registry_release_payload as build_registry_release_payload_v3,
)
from .applications.registry_routes import (
    build_registry_releases_payload as build_registry_releases_payload_v3,
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
    build_review_case_risk_profile as build_review_case_risk_profile_v3,
)
from .applications.review_alert_routes import (
    build_review_case_sort_key as build_review_case_sort_key_v3,
)
from .applications.review_alert_routes import (
    build_review_cases_list_payload as build_review_cases_list_payload_v3,
)
from .applications.review_alert_routes import (
    normalize_review_case_filters as normalize_review_case_filters_v3,
)
from .applications.review_alert_routes import (
    normalize_review_case_risk_level as normalize_review_case_risk_level_v3,
)
from .applications.review_alert_routes import (
    normalize_review_case_sla_bucket as normalize_review_case_sla_bucket_v3,
)
from .applications.review_alert_routes import (
    normalize_review_case_sort_by as normalize_review_case_sort_by_v3,
)
from .applications.review_alert_routes import (
    normalize_review_case_sort_order as normalize_review_case_sort_order_v3,
)
from .applications.review_queue_contract import (
    validate_courtroom_drilldown_bundle_contract as validate_courtroom_drilldown_bundle_contract_v3,
)
from .applications.review_queue_contract import (
    validate_evidence_claim_ops_queue_contract as validate_evidence_claim_ops_queue_contract_v3,
)
from .applications.route_group_registry import register_registry_routes
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
    build_review_trust_unified_priority_profile as build_review_trust_unified_priority_profile_v3,
)
from .applications.trust_ops_views import (
    build_trust_challenge_action_hints as build_trust_challenge_action_hints_v3,
)
from .applications.trust_ops_views import (
    build_trust_challenge_ops_queue_item as build_trust_challenge_ops_queue_item_v3,
)
from .applications.trust_ops_views import (
    build_trust_challenge_ops_queue_payload as build_trust_challenge_ops_queue_payload_v3,
)
from .applications.trust_ops_views import (
    build_trust_challenge_priority_profile as build_trust_challenge_priority_profile_v3,
)
from .applications.trust_ops_views import (
    build_trust_challenge_sort_key as build_trust_challenge_sort_key_v3,
)
from .applications.trust_ops_views import (
    normalize_trust_challenge_priority_level as normalize_trust_challenge_priority_level_v3,
)
from .applications.trust_ops_views import (
    normalize_trust_challenge_review_state as normalize_trust_challenge_review_state_v3,
)
from .applications.trust_ops_views import (
    normalize_trust_challenge_sla_bucket as normalize_trust_challenge_sla_bucket_v3,
)
from .applications.trust_ops_views import (
    normalize_trust_challenge_sort_by as normalize_trust_challenge_sort_by_v3,
)
from .applications.trust_ops_views import (
    normalize_trust_challenge_sort_order as normalize_trust_challenge_sort_order_v3,
)
from .applications.trust_ops_views import (
    normalize_trust_challenge_state_filter as normalize_trust_challenge_state_filter_v3,
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
from .domain.workflow import WORKFLOW_STATUSES, WorkflowJob
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


def _raise_policy_registry_not_found_lookup_error(*, err: LookupError) -> None:
    if str(err) == "policy_registry_not_found":
        raise HTTPException(status_code=404, detail="policy_registry_not_found") from err


def _raise_registry_version_not_found_lookup_error(*, err: LookupError) -> None:
    raise HTTPException(status_code=404, detail="registry_version_not_found") from err


def _raise_http_500_contract_violation(*, err: ValueError, code: str) -> None:
    raise HTTPException(
        status_code=500,
        detail={
            "code": str(code),
            "message": str(err),
        },
    ) from err


def _validate_contract_or_raise_http_500_for_runtime(
    *,
    payload: dict[str, Any],
    validate_contract: Callable[[dict[str, Any]], None],
    code: str,
) -> dict[str, Any]:
    try:
        validate_contract(payload)
    except ValueError as err:
        _raise_http_500_contract_violation(err=err, code=code)
    return payload


async def _await_payload_or_raise_http_500_for_runtime(
    *,
    self_awaitable: Awaitable[dict[str, Any]],
    code: str,
) -> dict[str, Any]:
    try:
        return await self_awaitable
    except ValueError as err:
        _raise_http_500_contract_violation(err=err, code=code)


async def _await_payload_or_raise_http_422_for_runtime(
    *,
    self_awaitable: Awaitable[dict[str, Any]],
) -> dict[str, Any]:
    try:
        return await self_awaitable
    except ValueError as err:
        _raise_http_422_from_value_error(err=err)


async def _await_payload_or_raise_http_404_for_runtime(
    *,
    self_awaitable: Awaitable[dict[str, Any]],
) -> dict[str, Any]:
    try:
        return await self_awaitable
    except LookupError as err:
        _raise_http_404_from_lookup_error(err=err)


async def _await_payload_or_raise_http_422_404_for_runtime(
    *,
    self_awaitable: Awaitable[dict[str, Any]],
) -> dict[str, Any]:
    try:
        return await self_awaitable
    except ValueError as err:
        _raise_http_422_from_value_error(err=err)
    except LookupError as err:
        _raise_http_404_from_lookup_error(err=err)


def _build_payload_or_raise_http_404_for_runtime(
    *,
    builder: Callable[..., dict[str, Any]],
    **kwargs: Any,
) -> dict[str, Any]:
    try:
        return builder(**kwargs)
    except LookupError as err:
        _raise_http_404_from_lookup_error(err=err)


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


def _build_domain_family_sort_key_for_runtime(row: dict[str, Any]) -> tuple[int, str]:
    return (
        -int(row.get("count") or 0),
        str(row.get("domainJudgeFamily") or ""),
    )


def _run_trust_read_guard_sync(
    builder: Callable[..., dict[str, Any]],
    **kwargs: Any,
) -> dict[str, Any]:
    try:
        return builder(**kwargs)
    except TrustReadRouteError_v3 as err:
        raise HTTPException(status_code=err.status_code, detail=err.detail) from err


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


async def _run_registry_route_guard(
    self_awaitable: Awaitable[dict[str, Any]],
) -> dict[str, Any]:
    return await _run_route_guard_with_http_bridge(
        self_awaitable,
        route_error_types=(RegistryRouteErrorV3,),
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


def _serialize_policy_profile_with_domain_family_for_runtime(
    profile: Any,
    *,
    runtime: AppRuntime,
) -> dict[str, Any]:
    return serialize_policy_profile_with_domain_family_v3(
        profile=profile,
        serialize_policy_profile=runtime.policy_registry_runtime.serialize_profile,
        resolve_policy_domain_judge_family_state=_resolve_policy_domain_judge_family_state,
    )


def _evaluate_policy_registry_dependency_health_for_governance(
    version: str,
    *,
    evaluate_policy_registry_dependency_health: Callable[[str], Awaitable[dict[str, Any]]],
) -> Awaitable[dict[str, Any]]:
    return evaluate_policy_registry_dependency_health(
        policy_version=version,
    )


def _evaluate_policy_release_fairness_gate_for_governance(
    version: str,
    *,
    evaluate_policy_release_fairness_gate: Callable[[str], Awaitable[dict[str, Any]]],
) -> Awaitable[dict[str, Any]]:
    return evaluate_policy_release_fairness_gate(
        policy_version=version,
    )


def _build_registry_governance_route_dependency_pack_for_runtime(
    *,
    runtime: AppRuntime,
    evaluate_policy_registry_dependency_health: Callable[[str], Awaitable[dict[str, Any]]],
    evaluate_policy_release_fairness_gate: Callable[[str], Awaitable[dict[str, Any]]],
    list_audit_alerts: Callable[..., Awaitable[list[Any]]],
) -> RegistryGovernanceRouteDependencyPack_v3:
    serialize_policy_profile = partial(
        _serialize_policy_profile_with_domain_family_for_runtime,
        runtime=runtime,
    )
    evaluate_dependency_health = partial(
        _evaluate_policy_registry_dependency_health_for_governance,
        evaluate_policy_registry_dependency_health=(
            evaluate_policy_registry_dependency_health
        ),
    )
    evaluate_fairness_gate = partial(
        _evaluate_policy_release_fairness_gate_for_governance,
        evaluate_policy_release_fairness_gate=evaluate_policy_release_fairness_gate,
    )
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
        serialize_policy_profile=serialize_policy_profile,
        evaluate_policy_registry_dependency_health=evaluate_dependency_health,
        evaluate_policy_release_fairness_gate=evaluate_fairness_gate,
        list_releases=runtime.registry_product_runtime.list_releases,
        list_audits=runtime.registry_product_runtime.list_audits,
        normalize_registry_dependency_trend_status=(
            normalize_registry_dependency_trend_status_v3
        ),
        dependency_trend_status_values=REGISTRY_DEPENDENCY_TREND_STATUS_VALUES,
        list_audit_alerts=list_audit_alerts,
        build_registry_dependency_overview=build_registry_dependency_overview_v3,
        build_registry_dependency_trend=build_registry_dependency_trend_v3,
        build_policy_domain_judge_family_overview=_build_policy_domain_judge_family_overview,
        build_registry_prompt_tool_usage_rows=build_registry_prompt_tool_usage_rows_v3,
        build_registry_prompt_tool_risk_items=build_registry_prompt_tool_risk_items_v3,
        build_registry_prompt_tool_action_hints=build_registry_prompt_tool_action_hints_v3,
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


async def _invoke_v3_callback_with_retry(
    *,
    runtime: AppRuntime,
    callback_fn: CallbackReportFn,
    job_id: int,
    payload: dict[str, Any],
) -> tuple[int, int]:
    return await invoke_callback_with_retry_v3(
        callback_fn=callback_fn,
        job_id=job_id,
        payload=payload,
        max_attempts=runtime.dispatch_runtime_cfg.runtime_retry_max_attempts,
        backoff_ms=runtime.dispatch_runtime_cfg.retry_backoff_ms,
        sleep_fn=runtime.sleep_fn,
    )


async def _invoke_v3_callback_with_retry_for_runtime(
    callback_fn: CallbackReportFn,
    job_id: int,
    payload: dict[str, Any],
    *,
    runtime: AppRuntime,
) -> tuple[int, int]:
    return await _invoke_v3_callback_with_retry(
        runtime=runtime,
        callback_fn=callback_fn,
        job_id=job_id,
        payload=payload,
    )


async def _invoke_failed_callback_with_retry_for_runtime(
    *,
    runtime: AppRuntime,
    dispatch_type: str,
    callback_phase_failed_fn: CallbackReportFn | None,
    callback_final_failed_fn: CallbackReportFn | None,
    case_id: int,
    payload: dict[str, Any],
) -> tuple[int, int]:
    callback_fn = cast(
        CallbackReportFn,
        resolve_failed_callback_fn_for_dispatch_v3(
            dispatch_type=dispatch_type,
            callback_phase_failed_fn=callback_phase_failed_fn,
            callback_final_failed_fn=callback_final_failed_fn,
        ),
    )
    return await _invoke_v3_callback_with_retry(
        runtime=runtime,
        callback_fn=callback_fn,
        job_id=case_id,
        payload=payload,
    )


def _attach_policy_trace_snapshot_for_runtime(
    *,
    runtime: AppRuntime,
    report_payload: dict[str, Any],
    profile: Any,
    prompt_profile: Any,
    tool_profile: Any,
) -> None:
    attach_policy_trace_snapshot_v3(
        report_payload=report_payload,
        profile=profile,
        prompt_profile=prompt_profile,
        tool_profile=tool_profile,
        build_policy_trace_snapshot=runtime.policy_registry_runtime.build_trace_snapshot,
        build_prompt_trace_snapshot=runtime.prompt_registry_runtime.build_trace_snapshot,
        build_tool_trace_snapshot=runtime.tool_registry_runtime.build_trace_snapshot,
    )


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
        await sync_audit_alert_to_facts(alert=row)
        resolved_alert_ids.append(row.alert_id)
    return resolved_alert_ids


async def _build_shared_room_context_for_runtime(
    *,
    session_id: int,
    case_id: int | None,
    list_dispatch_receipts: Callable[..., Awaitable[list[Any]]],
    workflow_list_jobs: Callable[..., Awaitable[list[WorkflowJob]]],
) -> dict[str, Any]:
    normalized_session_id = max(0, int(session_id))
    requested_case_id = max(0, int(case_id)) if case_id is not None else None

    phase_receipts = await list_dispatch_receipts(
        dispatch_type="phase",
        session_id=normalized_session_id,
        limit=200,
    )
    final_receipts = await list_dispatch_receipts(
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

    workflow_jobs = await workflow_list_jobs(
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

    verdict_contract = build_verdict_contract_v3(report_payload)
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


async def _list_audit_alerts_for_runtime(
    *,
    runtime: AppRuntime,
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


async def _workflow_get_job_for_runtime(
    *,
    runtime: AppRuntime,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    job_id: int,
) -> WorkflowJob | None:
    await ensure_workflow_schema_ready()
    return await runtime.workflow_runtime.orchestrator.get_job(job_id=job_id)


async def _workflow_list_jobs_for_runtime(
    *,
    runtime: AppRuntime,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    status: str | None,
    dispatch_type: str | None,
    limit: int,
) -> list[WorkflowJob]:
    await ensure_workflow_schema_ready()
    return await runtime.workflow_runtime.orchestrator.list_jobs(
        status=status,
        dispatch_type=dispatch_type,
        limit=limit,
    )


async def _workflow_list_events_for_runtime(
    *,
    runtime: AppRuntime,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    job_id: int,
) -> list[Any]:
    await ensure_workflow_schema_ready()
    return await runtime.workflow_runtime.orchestrator.list_events(job_id=job_id)


async def _workflow_append_event_for_runtime(
    *,
    runtime: AppRuntime,
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


async def _upsert_fairness_benchmark_run_for_runtime(
    *,
    runtime: AppRuntime,
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
) -> FactFairnessBenchmarkRun:
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


async def _list_fairness_benchmark_runs_for_runtime(
    *,
    runtime: AppRuntime,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    policy_version: str | None = None,
    environment_mode: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[FactFairnessBenchmarkRun]:
    await ensure_workflow_schema_ready()
    return await runtime.workflow_runtime.facts.list_fairness_benchmark_runs(
        policy_version=policy_version,
        environment_mode=environment_mode,
        status=status,
        limit=limit,
    )


async def _upsert_fairness_shadow_run_for_runtime(
    *,
    runtime: AppRuntime,
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
) -> FactFairnessShadowRun:
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


async def _list_fairness_shadow_runs_for_runtime(
    *,
    runtime: AppRuntime,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    policy_version: str | None = None,
    benchmark_run_id: str | None = None,
    environment_mode: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[FactFairnessShadowRun]:
    await ensure_workflow_schema_ready()
    return await runtime.workflow_runtime.facts.list_fairness_shadow_runs(
        policy_version=policy_version,
        benchmark_run_id=benchmark_run_id,
        environment_mode=environment_mode,
        status=status,
        limit=limit,
    )


async def _get_dispatch_receipt_for_runtime(
    *,
    runtime: AppRuntime,
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


async def _list_dispatch_receipts_for_runtime(
    *,
    runtime: AppRuntime,
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


async def _append_replay_record_for_runtime(
    *,
    runtime: AppRuntime,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    dispatch_type: str,
    job_id: int,
    trace_id: str,
    winner: str | None,
    needs_draw_vote: bool | None,
    provider: str | None,
    report_payload: dict[str, Any] | None,
) -> FactReplayRecord:
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


async def _list_replay_records_for_runtime(
    *,
    runtime: AppRuntime,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    job_id: int,
    dispatch_type: str | None = None,
    limit: int = 50,
) -> list[FactReplayRecord]:
    await ensure_workflow_schema_ready()
    return await runtime.workflow_runtime.facts.list_replay_records(
        dispatch_type=dispatch_type,
        job_id=job_id,
        limit=limit,
    )


async def _get_claim_ledger_record_for_runtime(
    *,
    runtime: AppRuntime,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    case_id: int,
    dispatch_type: str | None = None,
) -> FactClaimLedgerRecord | None:
    await ensure_workflow_schema_ready()
    return await runtime.workflow_runtime.facts.get_claim_ledger_record(
        case_id=case_id,
        dispatch_type=dispatch_type,
    )


async def _list_claim_ledger_records_for_runtime(
    *,
    runtime: AppRuntime,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    case_id: int,
    limit: int = 20,
) -> list[FactClaimLedgerRecord]:
    await ensure_workflow_schema_ready()
    return await runtime.workflow_runtime.facts.list_claim_ledger_records(
        case_id=case_id,
        limit=limit,
    )


async def _persist_dispatch_receipt_for_runtime(
    *,
    runtime: AppRuntime,
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


async def _upsert_claim_ledger_record_for_runtime(
    *,
    runtime: AppRuntime,
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


async def _sync_audit_alert_to_facts_for_runtime(
    *,
    runtime: AppRuntime,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    alert: Any,
) -> FactAuditAlert:
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


async def _workflow_register_and_mark_blinded_for_runtime(
    *,
    judge_core: JudgeCoreOrchestrator,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    job: WorkflowJob,
    event_payload: dict[str, Any] | None = None,
) -> None:
    await ensure_workflow_schema_ready()
    await judge_core.register_blinded(
        job=job,
        event_payload=event_payload,
    )


async def _workflow_register_and_mark_case_built_for_runtime(
    *,
    judge_core: JudgeCoreOrchestrator,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    job: WorkflowJob,
    event_payload: dict[str, Any] | None = None,
) -> WorkflowJob:
    await ensure_workflow_schema_ready()
    return await judge_core.register_case_built(
        job=job,
        event_payload=event_payload,
    )


async def _workflow_mark_completed_for_runtime(
    *,
    judge_core: JudgeCoreOrchestrator,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    job_id: int,
    event_payload: dict[str, Any] | None = None,
) -> None:
    await ensure_workflow_schema_ready()
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


async def _workflow_mark_review_required_for_runtime(
    *,
    judge_core: JudgeCoreOrchestrator,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    job_id: int,
    event_payload: dict[str, Any] | None = None,
) -> None:
    await ensure_workflow_schema_ready()
    payload = dict(event_payload or {})
    dispatch_type = str(payload.get("dispatchType") or "").strip().lower() or "unknown"
    await judge_core.mark_reported(
        job_id=job_id,
        dispatch_type=dispatch_type,
        review_required=True,
        event_payload=payload,
    )


async def _workflow_mark_failed_for_runtime(
    *,
    judge_core: JudgeCoreOrchestrator,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    job_id: int,
    error_code: str,
    error_message: str,
    event_payload: dict[str, Any] | None = None,
) -> None:
    await ensure_workflow_schema_ready()
    payload = dict(event_payload or {})
    dispatch_type = str(payload.get("dispatchType") or "").strip().lower() or "unknown"
    failed_stage = str(payload.get("judgeCoreStage") or "").strip().lower()
    if not failed_stage:
        failed_stage = "review_rejected" if error_code == "review_rejected" else "blocked_failed"
    payload.setdefault("errorCode", error_code)
    payload.setdefault("errorMessage", error_message)
    payload["error"] = build_error_contract_v3(
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


async def _workflow_mark_replay_for_runtime(
    *,
    judge_core: JudgeCoreOrchestrator,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
    job_id: int,
    dispatch_type: str,
    event_payload: dict[str, Any] | None = None,
) -> None:
    await ensure_workflow_schema_ready()
    payload = dict(event_payload or {})
    try:
        await judge_core.mark_replay(
            job_id=job_id,
            dispatch_type=dispatch_type,
            event_payload=payload,
        )
    except LookupError:
        return


async def _transition_judge_alert_status_for_runtime(
    *,
    case_id: int,
    alert_id: str,
    to_status: str,
    actor: str | None,
    reason: str | None,
    transition_audit_alert: Callable[..., Any],
    sync_audit_alert_to_facts: Callable[..., Awaitable[FactAuditAlert]],
    facts_transition_audit_alert: Callable[..., Awaitable[Any]],
    serialize_alert_item: Callable[[Any], dict[str, Any]],
    run_review_route_guard: Callable[[Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    return await run_review_route_guard(
        build_alert_status_transition_payload_v3(
            job_id=case_id,
            alert_id=alert_id,
            to_status=to_status,
            actor=actor,
            reason=reason,
            transition_audit_alert=transition_audit_alert,
            sync_audit_alert_to_facts=sync_audit_alert_to_facts,
            facts_transition_audit_alert=facts_transition_audit_alert,
            serialize_alert_item=serialize_alert_item,
        )
    )


async def _resolve_report_context_for_case_for_runtime(
    *,
    case_id: int,
    dispatch_type: str,
    not_found_detail: str,
    missing_report_detail: str,
    get_dispatch_receipt: Callable[..., Awaitable[Any | None]],
    run_trust_read_guard: Callable[[Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    return await run_trust_read_guard(
        resolve_trust_report_context_for_case_v3(
            case_id=case_id,
            dispatch_type=dispatch_type,
            get_dispatch_receipt=get_dispatch_receipt,
            not_found_detail=not_found_detail,
            missing_report_detail=missing_report_detail,
        )
    )


async def _build_trust_phasea_bundle_for_runtime(
    *,
    case_id: int,
    dispatch_type: str,
    get_dispatch_receipt: Callable[..., Awaitable[Any | None]],
    get_workflow_job: Callable[..., Awaitable[WorkflowJob | None]],
    list_workflow_events: Callable[..., Awaitable[list[Any]]],
    list_audit_alerts: Callable[..., Awaitable[list[Any]]],
    serialize_workflow_job: Callable[[WorkflowJob], dict[str, Any]],
    provider: str,
    run_trust_read_guard: Callable[[Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    return await run_trust_read_guard(
        build_trust_phasea_bundle_for_case_v3(
            case_id=case_id,
            dispatch_type=dispatch_type,
            get_dispatch_receipt=get_dispatch_receipt,
            get_workflow_job=get_workflow_job,
            list_workflow_events=list_workflow_events,
            list_audit_alerts=list_audit_alerts,
            serialize_workflow_job=serialize_workflow_job,
            provider=provider,
        )
    )


def _build_registry_profiles_payload_for_runtime(
    *,
    list_profiles: Callable[[], list[Any]],
    default_version: str,
    serializer: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    return build_registry_profiles_payload_v3(
        default_version=default_version,
        profiles=list_profiles(),
        serializer=serializer,
    )


async def _build_registry_profiles_payload_with_ready_for_runtime(
    *,
    ensure_registry_runtime_ready: Callable[[], Awaitable[None]],
    list_profiles: Callable[[], list[Any]],
    default_version: str,
    serializer: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    await ensure_registry_runtime_ready()
    return _build_registry_profiles_payload_for_runtime(
        list_profiles=list_profiles,
        default_version=default_version,
        serializer=serializer,
    )


def _build_registry_profile_payload_for_runtime(
    *,
    version: str,
    get_profile: Callable[[str], Any | None],
    serializer: Callable[[Any], dict[str, Any]],
    not_found_detail: str,
) -> dict[str, Any]:
    profile = get_profile(version)
    if profile is None:
        raise HTTPException(status_code=404, detail=not_found_detail)
    return build_registry_profile_payload_v3(
        profile=profile,
        serializer=serializer,
    )


async def _build_registry_profile_payload_with_ready_for_runtime(
    *,
    ensure_registry_runtime_ready: Callable[[], Awaitable[None]],
    version: str,
    get_profile: Callable[[str], Any | None],
    serializer: Callable[[Any], dict[str, Any]],
    not_found_detail: str,
) -> dict[str, Any]:
    await ensure_registry_runtime_ready()
    return _build_registry_profile_payload_for_runtime(
        version=version,
        get_profile=get_profile,
        serializer=serializer,
        not_found_detail=not_found_detail,
    )


def _build_policy_registry_profiles_payload_for_runtime(
    *,
    runtime: AppRuntime,
    serialize_policy_profile_with_domain_family: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    return _build_registry_profiles_payload_for_runtime(
        list_profiles=runtime.policy_registry_runtime.list_profiles,
        default_version=runtime.policy_registry_runtime.default_version,
        serializer=serialize_policy_profile_with_domain_family,
    )


async def _build_policy_registry_profiles_payload_with_ready_for_runtime(
    *,
    ensure_registry_runtime_ready: Callable[[], Awaitable[None]],
    runtime: AppRuntime,
    serialize_policy_profile_with_domain_family: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    await ensure_registry_runtime_ready()
    return _build_policy_registry_profiles_payload_for_runtime(
        runtime=runtime,
        serialize_policy_profile_with_domain_family=(
            serialize_policy_profile_with_domain_family
        ),
    )


def _build_policy_registry_profile_payload_for_runtime(
    *,
    policy_version: str,
    runtime: AppRuntime,
    serialize_policy_profile_with_domain_family: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    return _build_registry_profile_payload_for_runtime(
        version=policy_version,
        get_profile=runtime.policy_registry_runtime.get_profile,
        serializer=serialize_policy_profile_with_domain_family,
        not_found_detail="judge_policy_not_found",
    )


async def _build_policy_registry_profile_payload_with_ready_for_runtime(
    *,
    ensure_registry_runtime_ready: Callable[[], Awaitable[None]],
    policy_version: str,
    runtime: AppRuntime,
    serialize_policy_profile_with_domain_family: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    await ensure_registry_runtime_ready()
    return _build_policy_registry_profile_payload_for_runtime(
        policy_version=policy_version,
        runtime=runtime,
        serialize_policy_profile_with_domain_family=(
            serialize_policy_profile_with_domain_family
        ),
    )


async def _build_dispatch_receipt_payload_for_runtime(
    *,
    case_id: int,
    dispatch_type: str,
    not_found_detail: str,
    get_dispatch_receipt: Callable[..., Awaitable[Any | None]],
) -> dict[str, Any]:
    item = await get_dispatch_receipt(
        dispatch_type=dispatch_type,
        job_id=case_id,
    )
    if item is None:
        raise HTTPException(status_code=404, detail=not_found_detail)
    return serialize_dispatch_receipt_v3(item)


async def _build_registry_audits_payload_for_runtime(
    *,
    runtime: AppRuntime,
    list_audit_alerts: Callable[..., Awaitable[list[Any]]],
    registry_type: str,
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
            normalize_registry_audit_action=normalize_registry_audit_action_v3,
            registry_audit_action_values=REGISTRY_AUDIT_ACTION_VALUES,
            list_registry_audits=runtime.registry_product_runtime.list_audits,
            list_audit_alerts=list_audit_alerts,
            list_alert_outbox=runtime.trace_store.list_alert_outbox,
            build_registry_audit_ops_view=build_registry_audit_ops_view_v3,
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


async def _build_registry_releases_payload_for_runtime(
    *,
    runtime: AppRuntime,
    registry_type: str,
    limit: int,
    include_payload: bool,
) -> dict[str, Any]:
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


async def _build_registry_release_payload_for_runtime(
    *,
    runtime: AppRuntime,
    registry_type: str,
    version: str,
    not_found_detail: str,
) -> dict[str, Any]:
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
        raise HTTPException(status_code=404, detail=not_found_detail)
    return build_registry_release_payload_v3(item=item)


async def _build_review_cases_list_payload_for_runtime(
    *,
    status: str,
    dispatch_type: str | None,
    risk_level: str | None,
    sla_bucket: str | None,
    challenge_state: str | None,
    trust_review_state: str | None,
    unified_priority_level: str | None,
    sort_by: str,
    sort_order: str,
    scan_limit: int,
    limit: int,
    workflow_list_jobs: Callable[..., Awaitable[list[WorkflowJob]]],
    workflow_list_events: Callable[..., Awaitable[list[dict[str, Any]]]],
    list_audit_alerts: Callable[..., Awaitable[list[Any]]],
    get_trace: Callable[[int], dict[str, Any] | None],
    build_review_case_risk_profile: Callable[..., dict[str, Any]],
    build_trust_challenge_priority_profile: Callable[..., dict[str, Any]],
    build_review_trust_unified_priority_profile: Callable[..., dict[str, Any]],
    serialize_workflow_job: Callable[[WorkflowJob], dict[str, Any]],
) -> dict[str, Any]:
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
        normalize_review_case_risk_level=normalize_review_case_risk_level_v3,
        review_case_risk_level_values=REVIEW_CASE_RISK_LEVEL_VALUES,
        normalize_review_case_sla_bucket=normalize_review_case_sla_bucket_v3,
        review_case_sla_bucket_values=REVIEW_CASE_SLA_BUCKET_VALUES,
        normalize_trust_challenge_state_filter=normalize_trust_challenge_state_filter_v3,
        case_fairness_challenge_states=CASE_FAIRNESS_CHALLENGE_STATES,
        normalize_trust_challenge_review_state=normalize_trust_challenge_review_state_v3,
        trust_challenge_review_state_values=TRUST_CHALLENGE_REVIEW_STATE_VALUES,
        normalize_trust_challenge_priority_level=normalize_trust_challenge_priority_level_v3,
        trust_challenge_priority_level_values=TRUST_CHALLENGE_PRIORITY_LEVEL_VALUES,
        normalize_review_case_sort_by=normalize_review_case_sort_by_v3,
        review_case_sort_fields=REVIEW_CASE_SORT_FIELDS,
        normalize_review_case_sort_order=normalize_review_case_sort_order_v3,
    )
    return await build_review_cases_list_payload_v3(
        normalized_status=str(normalized_filters["status"]),
        normalized_dispatch_type=cast(
            str | None, normalized_filters["dispatchType"]
        ),
        normalized_risk_level=cast(str | None, normalized_filters["riskLevel"]),
        normalized_sla_bucket=cast(str | None, normalized_filters["slaBucket"]),
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
        workflow_list_jobs=workflow_list_jobs,
        get_trace=get_trace,
        workflow_list_events=workflow_list_events,
        list_audit_alerts=list_audit_alerts,
        build_challenge_review_registry=build_challenge_review_registry_v3,
        build_review_case_risk_profile=build_review_case_risk_profile,
        build_trust_challenge_priority_profile=build_trust_challenge_priority_profile,
        build_review_trust_unified_priority_profile=(
            build_review_trust_unified_priority_profile
        ),
        serialize_workflow_job=serialize_workflow_job,
        build_review_case_sort_key=build_review_case_sort_key_v3,
    )


async def _build_review_case_detail_payload_for_runtime(
    *,
    case_id: int,
    workflow_get_job: Callable[..., Awaitable[WorkflowJob | None]],
    workflow_list_events: Callable[..., Awaitable[list[dict[str, Any]]]],
    list_audit_alerts: Callable[..., Awaitable[list[Any]]],
    get_trace: Callable[[int], dict[str, Any] | None],
    serialize_workflow_job: Callable[[WorkflowJob], dict[str, Any]],
    serialize_alert_item: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    return await build_review_case_detail_payload_v3(
        case_id=case_id,
        workflow_get_job=workflow_get_job,
        workflow_list_events=workflow_list_events,
        list_audit_alerts=list_audit_alerts,
        get_trace=get_trace,
        serialize_workflow_job=serialize_workflow_job,
        serialize_alert_item=serialize_alert_item,
    )


async def _build_alert_ops_view_payload_for_runtime(
    *,
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
    list_audit_alerts: Callable[..., Awaitable[list[Any]]],
    list_alert_outbox: Callable[..., list[Any]],
) -> dict[str, Any]:
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
        normalize_ops_alert_status=normalize_ops_alert_status_v3,
        normalize_ops_alert_delivery_status=normalize_ops_alert_delivery_status_v3,
        normalize_ops_alert_fields_mode=normalize_ops_alert_fields_mode_v3,
        ops_registry_alert_types=OPS_REGISTRY_ALERT_TYPES,
        ops_alert_status_values=OPS_ALERT_STATUS_VALUES,
        ops_alert_delivery_status_values=OPS_ALERT_DELIVERY_STATUS_VALUES,
        ops_alert_fields_mode_values=OPS_ALERT_FIELDS_MODE_VALUES,
        list_audit_alerts=list_audit_alerts,
        list_alert_outbox=list_alert_outbox,
        build_registry_alert_ops_view=build_registry_alert_ops_view_v3,
    )


async def _build_case_alerts_payload_for_runtime(
    *,
    case_id: int,
    status: str | None,
    limit: int,
    list_audit_alerts: Callable[..., Awaitable[list[Any]]],
    serialize_alert_item: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    return await build_case_alerts_payload_v3(
        case_id=case_id,
        status=status,
        limit=limit,
        list_audit_alerts=list_audit_alerts,
        serialize_alert_item=serialize_alert_item,
    )


def _build_alert_outbox_payload_for_runtime(
    *,
    delivery_status: str | None,
    limit: int,
    list_alert_outbox: Callable[..., list[Any]],
    serialize_outbox_event: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    return build_alert_outbox_route_payload_v3(
        delivery_status=delivery_status,
        limit=limit,
        list_alert_outbox=list_alert_outbox,
        serialize_outbox_event=serialize_outbox_event,
    )


async def _build_ops_read_model_pack_payload_for_runtime(
    *,
    x_ai_internal_key: str | None,
    dispatch_type: str | None,
    policy_version: str | None,
    window_days: int,
    top_limit: int,
    case_scan_limit: int,
    include_case_trust: bool,
    trust_case_limit: int,
    dependency_limit: int,
    usage_preview_limit: int,
    release_limit: int,
    audit_limit: int,
    calibration_risk_limit: int,
    calibration_benchmark_limit: int,
    calibration_shadow_limit: int,
    panel_profile_scan_limit: int,
    panel_group_limit: int,
    panel_attention_limit: int,
    runtime: AppRuntime,
    get_judge_fairness_dashboard: Callable[..., Awaitable[dict[str, Any]]],
    get_registry_governance_overview: Callable[..., Awaitable[dict[str, Any]]],
    get_registry_prompt_tool_governance: Callable[..., Awaitable[dict[str, Any]]],
    get_policy_registry_dependency_health: Callable[..., Awaitable[dict[str, Any]]],
    get_judge_fairness_policy_calibration_advisor: Callable[..., Awaitable[dict[str, Any]]],
    get_panel_runtime_readiness: Callable[..., Awaitable[dict[str, Any]]],
    list_judge_courtroom_cases: Callable[..., Awaitable[dict[str, Any]]],
    list_judge_courtroom_drilldown_bundle: Callable[..., Awaitable[dict[str, Any]]],
    list_judge_evidence_claim_ops_queue: Callable[..., Awaitable[dict[str, Any]]],
    list_judge_trust_challenge_ops_queue: Callable[..., Awaitable[dict[str, Any]]],
    list_judge_review_jobs: Callable[..., Awaitable[dict[str, Any]]],
    simulate_policy_release_gate: Callable[..., Awaitable[dict[str, Any]]],
    get_judge_case_courtroom_read_model: Callable[..., Awaitable[dict[str, Any]]],
    get_judge_trust_public_verify: Callable[..., Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
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
        get_judge_fairness_policy_calibration_advisor=(
            get_judge_fairness_policy_calibration_advisor
        ),
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
        summarize_ops_read_model_pack_trust_items_fn=(
            summarize_ops_read_model_pack_trust_items
        ),
        summarize_ops_read_model_pack_review_items_fn=(
            summarize_ops_read_model_pack_review_items
        ),
        build_ops_read_model_pack_case_chain_coverage_fn=(
            build_ops_read_model_pack_case_chain_coverage
        ),
        build_ops_read_model_pack_fairness_gate_overview_fn=(
            build_ops_read_model_pack_fairness_gate_overview
        ),
        build_ops_read_model_pack_policy_kernel_binding_fn=(
            build_ops_read_model_pack_policy_kernel_binding
        ),
        build_ops_read_model_pack_adaptive_summary_fn=(
            build_ops_read_model_pack_adaptive_summary
        ),
        build_ops_read_model_pack_trust_overview_fn=build_ops_read_model_pack_trust_overview,
        build_ops_read_model_pack_judge_workflow_coverage_fn=(
            build_ops_read_model_pack_judge_workflow_coverage
        ),
        build_ops_read_model_pack_filters_fn=build_ops_read_model_pack_filters,
        build_ops_read_model_pack_v5_payload_fn=build_ops_read_model_pack_v5_payload,
    )


async def _build_panel_runtime_profiles_payload_for_runtime(
    *,
    x_ai_internal_key: str | None,
    status: str | None,
    dispatch_type: str | None,
    winner: str | None,
    policy_version: str | None,
    has_open_review: bool | None,
    gate_conclusion: str | None,
    challenge_state: str | None,
    review_required: bool | None,
    panel_high_disagreement: bool | None,
    judge_id: str | None,
    profile_source: str | None,
    profile_id: str | None,
    model_strategy: str | None,
    strategy_slot: str | None,
    domain_slot: str | None,
    sort_by: str,
    sort_order: str,
    offset: int,
    limit: int,
    list_judge_case_fairness: Callable[..., Awaitable[dict[str, Any]]],
    run_panel_runtime_route_guard: Callable[
        [Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]
    ],
) -> dict[str, Any]:
    return await run_panel_runtime_route_guard(
        build_panel_runtime_profiles_route_payload_v3(
            list_judge_case_fairness=list_judge_case_fairness,
            build_panel_runtime_profile_item=build_panel_runtime_profile_item_v3,
            build_panel_runtime_profile_sort_key=build_panel_runtime_profile_sort_key_v3,
            build_panel_runtime_profile_aggregations=(
                build_panel_runtime_profile_aggregations_v3
            ),
            validate_panel_runtime_profile_contract=(
                validate_panel_runtime_profile_contract_v3
            ),
            panel_judge_ids=PANEL_JUDGE_IDS,
            panel_runtime_profile_source_values=PANEL_RUNTIME_PROFILE_SOURCE_VALUES,
            panel_runtime_profile_sort_fields=PANEL_RUNTIME_PROFILE_SORT_FIELDS,
            normalize_workflow_status=_normalize_workflow_status,
            normalize_panel_runtime_profile_source=normalize_panel_runtime_profile_source_v3,
            normalize_panel_runtime_profile_sort_by=normalize_panel_runtime_profile_sort_by_v3,
            normalize_panel_runtime_profile_sort_order=normalize_panel_runtime_profile_sort_order_v3,
            normalize_case_fairness_gate_conclusion=(
                normalize_case_fairness_gate_conclusion_v3
            ),
            normalize_case_fairness_challenge_state=(
                normalize_case_fairness_challenge_state_v3
            ),
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


async def _build_panel_runtime_readiness_payload_for_runtime(
    *,
    x_ai_internal_key: str | None,
    status: str | None,
    dispatch_type: str | None,
    winner: str | None,
    policy_version: str | None,
    has_open_review: bool | None,
    gate_conclusion: str | None,
    challenge_state: str | None,
    review_required: bool | None,
    panel_high_disagreement: bool | None,
    judge_id: str | None,
    profile_source: str | None,
    profile_id: str | None,
    model_strategy: str | None,
    strategy_slot: str | None,
    domain_slot: str | None,
    profile_scan_limit: int,
    group_limit: int,
    attention_limit: int,
    list_panel_runtime_profiles: Callable[..., Awaitable[dict[str, Any]]],
    run_panel_runtime_route_guard: Callable[
        [Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]
    ],
) -> dict[str, Any]:
    return await run_panel_runtime_route_guard(
        build_panel_runtime_readiness_route_payload_v3(
            list_panel_runtime_profiles=list_panel_runtime_profiles,
            build_panel_runtime_readiness_summary=build_panel_runtime_readiness_summary_v3,
            panel_judge_ids=PANEL_JUDGE_IDS,
            panel_runtime_profile_source_values=PANEL_RUNTIME_PROFILE_SOURCE_VALUES,
            normalize_workflow_status=_normalize_workflow_status,
            normalize_panel_runtime_profile_source=normalize_panel_runtime_profile_source_v3,
            normalize_case_fairness_gate_conclusion=(
                normalize_case_fairness_gate_conclusion_v3
            ),
            normalize_case_fairness_challenge_state=(
                normalize_case_fairness_challenge_state_v3
            ),
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


async def _build_replay_report_payload_for_runtime(
    *,
    case_id: int,
    get_trace: Callable[[int], dict[str, Any] | None],
    get_claim_ledger_record: Callable[..., Awaitable[FactClaimLedgerRecord | None]],
    run_replay_read_guard: Callable[
        [Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]
    ],
) -> dict[str, Any]:
    return await run_replay_read_guard(
        build_replay_report_route_payload_v3(
            case_id=case_id,
            get_trace=get_trace,
            build_replay_report_payload=build_replay_report_payload_v3,
            get_claim_ledger_record=get_claim_ledger_record,
            serialize_claim_ledger_record=serialize_claim_ledger_record_v3,
        )
    )


def _build_replay_reports_payload_for_runtime(
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
    list_traces: Callable[..., list[Any]],
) -> dict[str, Any]:
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
        list_traces=list_traces,
        build_replay_report_payload=build_replay_report_payload_v3,
        build_replay_report_summary=build_replay_report_summary_v3,
        build_replay_reports_list_payload=build_replay_reports_list_payload_v3,
    )


async def _build_fairness_calibration_pack_payload_for_runtime(
    *,
    x_ai_internal_key: str | None,
    dispatch_type: str | None,
    status: str | None,
    winner: str | None,
    policy_version: str | None,
    challenge_state: str | None,
    case_scan_limit: int,
    risk_limit: int,
    benchmark_limit: int,
    shadow_limit: int,
    list_judge_case_fairness: Callable[..., Awaitable[dict[str, Any]]],
    list_fairness_benchmark_runs: Callable[..., Awaitable[list[FactFairnessBenchmarkRun]]],
    list_fairness_shadow_runs: Callable[..., Awaitable[list[FactFairnessShadowRun]]],
) -> dict[str, Any]:
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
        list_fairness_benchmark_runs=list_fairness_benchmark_runs,
        list_fairness_shadow_runs=list_fairness_shadow_runs,
        build_fairness_dashboard_top_risk_cases=build_fairness_dashboard_top_risk_cases_v3,
        build_fairness_calibration_threshold_suggestions=(
            build_fairness_calibration_threshold_suggestions_v3
        ),
        build_fairness_calibration_drift_summary=(
            build_fairness_calibration_drift_summary_v3
        ),
        build_fairness_calibration_risk_items=build_fairness_calibration_risk_items_v3,
        build_fairness_calibration_on_env_input_template=(
            build_fairness_calibration_on_env_input_template_v3
        ),
    )


async def _build_fairness_policy_calibration_advisor_payload_for_runtime(
    *,
    x_ai_internal_key: str | None,
    dispatch_type: str | None,
    status: str | None,
    winner: str | None,
    policy_version: str | None,
    challenge_state: str | None,
    case_scan_limit: int,
    risk_limit: int,
    benchmark_limit: int,
    shadow_limit: int,
    list_judge_case_fairness: Callable[..., Awaitable[dict[str, Any]]],
    list_fairness_benchmark_runs: Callable[..., Awaitable[list[FactFairnessBenchmarkRun]]],
    list_fairness_shadow_runs: Callable[..., Awaitable[list[FactFairnessShadowRun]]],
    evaluate_policy_release_fairness_gate: Callable[..., Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
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
        list_fairness_benchmark_runs=list_fairness_benchmark_runs,
        list_fairness_shadow_runs=list_fairness_shadow_runs,
        build_fairness_dashboard_top_risk_cases=build_fairness_dashboard_top_risk_cases_v3,
        build_fairness_calibration_threshold_suggestions=(
            build_fairness_calibration_threshold_suggestions_v3
        ),
        build_fairness_calibration_drift_summary=(
            build_fairness_calibration_drift_summary_v3
        ),
        build_fairness_calibration_risk_items=build_fairness_calibration_risk_items_v3,
        evaluate_policy_release_fairness_gate=evaluate_policy_release_fairness_gate,
        build_fairness_policy_calibration_recommended_actions=(
            build_fairness_policy_calibration_recommended_actions_v3
        ),
    )


async def _build_trust_challenge_ops_queue_payload_for_runtime(
    *,
    status: str | None,
    dispatch_type: str,
    challenge_state: str | None,
    review_state: str | None,
    priority_level: str | None,
    sla_bucket: str | None,
    has_open_alert: bool | None,
    sort_by: str,
    sort_order: str,
    scan_limit: int,
    offset: int,
    limit: int,
    workflow_list_jobs: Callable[..., Awaitable[list[WorkflowJob]]],
    build_trust_phasea_bundle: Callable[..., Awaitable[dict[str, Any]]],
    get_trace: Callable[[int], dict[str, Any] | None],
    build_trust_challenge_priority_profile: Callable[..., dict[str, Any]],
    serialize_workflow_job: Callable[[WorkflowJob], dict[str, Any]],
    build_trust_challenge_action_hints: Callable[..., dict[str, Any]],
    run_trust_challenge_guard: Callable[
        [Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]
    ],
) -> dict[str, Any]:
    return await run_trust_challenge_guard(
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
            normalize_trust_challenge_state_filter=normalize_trust_challenge_state_filter_v3,
            case_fairness_challenge_states=CASE_FAIRNESS_CHALLENGE_STATES,
            normalize_trust_challenge_review_state=normalize_trust_challenge_review_state_v3,
            trust_challenge_review_state_values=TRUST_CHALLENGE_REVIEW_STATE_VALUES,
            normalize_trust_challenge_priority_level=(
                normalize_trust_challenge_priority_level_v3
            ),
            trust_challenge_priority_level_values=TRUST_CHALLENGE_PRIORITY_LEVEL_VALUES,
            normalize_trust_challenge_sla_bucket=normalize_trust_challenge_sla_bucket_v3,
            trust_challenge_sla_bucket_values=TRUST_CHALLENGE_SLA_BUCKET_VALUES,
            normalize_trust_challenge_sort_by=normalize_trust_challenge_sort_by_v3,
            trust_challenge_sort_fields=TRUST_CHALLENGE_SORT_FIELDS,
            normalize_trust_challenge_sort_order=normalize_trust_challenge_sort_order_v3,
            trust_challenge_open_states=TRUST_CHALLENGE_OPEN_STATES,
            workflow_list_jobs=workflow_list_jobs,
            build_trust_phasea_bundle=build_trust_phasea_bundle,
            get_trace=get_trace,
            build_trust_challenge_priority_profile=(
                build_trust_challenge_priority_profile
            ),
            serialize_workflow_job=serialize_workflow_job,
            build_trust_challenge_ops_queue_item=build_trust_challenge_ops_queue_item_v3,
            build_trust_challenge_action_hints=build_trust_challenge_action_hints,
            build_trust_challenge_sort_key=build_trust_challenge_sort_key_v3,
            build_trust_challenge_ops_queue_payload=build_trust_challenge_ops_queue_payload_v3,
            validate_trust_challenge_ops_queue_contract=(
                validate_trust_challenge_queue_contract_v3
            ),
        )
    )


async def _build_trust_challenge_request_payload_for_runtime(
    *,
    case_id: int,
    dispatch_type: str,
    reason_code: str,
    reason: str | None,
    requested_by: str | None,
    auto_accept: bool,
    trust_challenge_common_dependencies: dict[str, Any],
    upsert_audit_alert: Callable[..., Any],
    sync_audit_alert_to_facts: Callable[..., Awaitable[FactAuditAlert]],
    run_trust_challenge_guard: Callable[
        [Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]
    ],
) -> dict[str, Any]:
    return await run_trust_challenge_guard(
        build_trust_challenge_request_payload_v3(
            case_id=case_id,
            dispatch_type=dispatch_type,
            reason_code=reason_code,
            reason=reason,
            requested_by=requested_by,
            auto_accept=auto_accept,
            **trust_challenge_common_dependencies,
            new_challenge_id=_build_trust_challenge_id_for_runtime,
            upsert_audit_alert=upsert_audit_alert,
            sync_audit_alert_to_facts=sync_audit_alert_to_facts,
            trust_challenge_state_requested=TRUST_CHALLENGE_STATE_REQUESTED,
        )
    )


async def _build_trust_challenge_decision_payload_for_runtime(
    *,
    case_id: int,
    challenge_id: str,
    dispatch_type: str,
    decision: str,
    actor: str | None,
    reason: str | None,
    trust_challenge_common_dependencies: dict[str, Any],
    workflow_mark_completed: Callable[..., Awaitable[None]],
    workflow_mark_draw_pending_vote: Callable[..., Awaitable[Any]],
    resolve_open_alerts_for_review: Callable[..., Awaitable[list[str]]],
    run_trust_challenge_guard: Callable[
        [Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]
    ],
) -> dict[str, Any]:
    return await run_trust_challenge_guard(
        build_trust_challenge_decision_payload_v3(
            case_id=case_id,
            challenge_id=challenge_id,
            dispatch_type=dispatch_type,
            decision=decision,
            actor=actor,
            reason=reason,
            **trust_challenge_common_dependencies,
            workflow_mark_completed=workflow_mark_completed,
            workflow_mark_draw_pending_vote=workflow_mark_draw_pending_vote,
            resolve_open_alerts_for_review=resolve_open_alerts_for_review,
            trust_challenge_state_closed=TRUST_CHALLENGE_STATE_CLOSED,
            trust_challenge_state_verdict_upheld=TRUST_CHALLENGE_STATE_VERDICT_UPHELD,
            trust_challenge_state_verdict_overturned=(
                TRUST_CHALLENGE_STATE_VERDICT_OVERTURNED
            ),
            trust_challenge_state_draw_after_review=(
                TRUST_CHALLENGE_STATE_DRAW_AFTER_REVIEW
            ),
            workflow_transition_error_cls=WorkflowTransitionError,
        )
    )


async def _build_validated_trust_item_payload_for_runtime(
    *,
    case_id: int,
    dispatch_type: str,
    item_key: str,
    validate_contract: Callable[[dict[str, Any]], None],
    violation_code: str,
    build_trust_phasea_bundle: Callable[..., Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    bundle = await build_trust_phasea_bundle(
        case_id=case_id,
        dispatch_type=dispatch_type,
    )
    return _run_trust_read_guard_sync(
        build_validated_trust_item_route_payload_v3,
        case_id=case_id,
        bundle=bundle,
        item_key=item_key,
        validate_contract=validate_contract,
        violation_code=violation_code,
    )


async def _build_trust_audit_anchor_payload_for_runtime(
    *,
    case_id: int,
    dispatch_type: str,
    include_payload: bool,
    build_trust_phasea_bundle: Callable[..., Awaitable[dict[str, Any]]],
    build_audit_anchor_export: Callable[..., dict[str, Any]],
    validate_contract: Callable[[dict[str, Any]], None],
    violation_code: str,
) -> dict[str, Any]:
    bundle = await build_trust_phasea_bundle(
        case_id=case_id,
        dispatch_type=dispatch_type,
    )
    return _run_trust_read_guard_sync(
        build_trust_audit_anchor_route_payload_v3,
        case_id=case_id,
        bundle=bundle,
        include_payload=include_payload,
        build_audit_anchor_export=build_audit_anchor_export,
        validate_contract=validate_contract,
        violation_code=violation_code,
    )


async def _build_trust_public_verify_payload_for_runtime(
    *,
    case_id: int,
    dispatch_type: str,
    build_trust_phasea_bundle: Callable[..., Awaitable[dict[str, Any]]],
    build_audit_anchor_export: Callable[..., dict[str, Any]],
    build_public_verify_payload: Callable[..., dict[str, Any]],
    validate_contract: Callable[[dict[str, Any]], None],
    violation_code: str,
) -> dict[str, Any]:
    bundle = await build_trust_phasea_bundle(
        case_id=case_id,
        dispatch_type=dispatch_type,
    )
    return _run_trust_read_guard_sync(
        build_trust_public_verify_bundle_payload_v3,
        case_id=case_id,
        bundle=bundle,
        build_audit_anchor_export=build_audit_anchor_export,
        build_public_verify_payload=build_public_verify_payload,
        validate_contract=validate_contract,
        violation_code=violation_code,
    )


def _build_registry_release_gate_dependencies_for_runtime(
    *,
    policy_registry_type: str,
    evaluate_policy_registry_dependency_health: Callable[..., Awaitable[dict[str, Any]]],
    emit_registry_dependency_health_alert: Callable[..., Awaitable[dict[str, Any]]],
    resolve_registry_dependency_health_alerts: Callable[..., Awaitable[list[dict[str, Any]]]],
    evaluate_policy_release_fairness_gate: Callable[..., Awaitable[dict[str, Any]]],
    emit_registry_fairness_gate_alert: Callable[..., Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    return {
        "policy_registry_type": policy_registry_type,
        "evaluate_policy_registry_dependency_health": (
            evaluate_policy_registry_dependency_health
        ),
        "emit_registry_dependency_health_alert": emit_registry_dependency_health_alert,
        "resolve_registry_dependency_health_alerts": (
            resolve_registry_dependency_health_alerts
        ),
        "evaluate_policy_release_fairness_gate": evaluate_policy_release_fairness_gate,
        "emit_registry_fairness_gate_alert": emit_registry_fairness_gate_alert,
    }


def _build_trust_challenge_common_dependencies_for_runtime(
    *,
    resolve_report_context_for_case: Callable[..., Awaitable[dict[str, Any]]],
    workflow_get_job: Callable[..., Awaitable[WorkflowJob | None]],
    workflow_append_event: Callable[..., Awaitable[dict[str, Any]]],
    workflow_mark_review_required: Callable[..., Awaitable[None]],
    build_trust_phasea_bundle: Callable[..., Awaitable[dict[str, Any]]],
    serialize_workflow_job: Callable[[WorkflowJob], dict[str, Any]],
    trust_challenge_event_type: str,
    trust_challenge_state_accepted: str,
    trust_challenge_state_under_review: str,
) -> dict[str, Any]:
    return {
        "resolve_report_context_for_case": resolve_report_context_for_case,
        "workflow_get_job": workflow_get_job,
        "workflow_append_event": workflow_append_event,
        "workflow_mark_review_required": workflow_mark_review_required,
        "build_trust_phasea_bundle": build_trust_phasea_bundle,
        "serialize_workflow_job": serialize_workflow_job,
        "trust_challenge_event_type": trust_challenge_event_type,
        "trust_challenge_state_accepted": trust_challenge_state_accepted,
        "trust_challenge_state_under_review": trust_challenge_state_under_review,
    }


def _build_review_case_risk_profile_for_runtime(
    *,
    workflow: WorkflowJob,
    report_payload: dict[str, Any] | None,
    report_summary: dict[str, Any] | None,
    now: datetime | str | None,
    normalize_query_datetime: Callable[[datetime | str | None], datetime | None],
) -> dict[str, Any]:
    return build_review_case_risk_profile_v3(
        workflow=workflow,
        report_payload=report_payload,
        report_summary=report_summary,
        now=now,
        normalize_query_datetime=normalize_query_datetime,
    )


def _build_trust_challenge_priority_profile_for_runtime(
    *,
    workflow: WorkflowJob,
    challenge_review: dict[str, Any] | None,
    report_payload: dict[str, Any] | None,
    report_summary: dict[str, Any] | None,
    now: datetime | str | None,
    normalize_query_datetime: Callable[[datetime | str | None], datetime | None],
    trust_challenge_open_states: set[str],
) -> dict[str, Any]:
    return build_trust_challenge_priority_profile_v3(
        workflow=workflow,
        challenge_review=challenge_review,
        report_payload=report_payload,
        report_summary=report_summary,
        now=now,
        normalize_query_datetime=normalize_query_datetime,
        trust_challenge_open_states=trust_challenge_open_states,
    )


def _build_trust_challenge_action_hints_for_runtime(
    *,
    challenge_review: dict[str, Any] | None,
    priority_profile: dict[str, Any] | None,
    trust_challenge_open_states: set[str],
) -> list[dict[str, Any]]:
    return build_trust_challenge_action_hints_v3(
        challenge_review=challenge_review,
        priority_profile=priority_profile,
        trust_challenge_open_states=trust_challenge_open_states,
    )


def _build_review_trust_unified_priority_profile_for_runtime(
    *,
    risk_profile: dict[str, Any] | None,
    trust_priority_profile: dict[str, Any] | None,
    challenge_review: dict[str, Any] | None,
    trust_challenge_open_states: set[str],
) -> dict[str, Any]:
    return build_review_trust_unified_priority_profile_v3(
        risk_profile=risk_profile,
        trust_priority_profile=trust_priority_profile,
        challenge_review=challenge_review,
        trust_challenge_open_states=trust_challenge_open_states,
    )


def _build_courtroom_read_model_view_for_runtime(
    *,
    report_payload: dict[str, Any],
    case_evidence: dict[str, Any],
) -> dict[str, Any]:
    return build_courtroom_read_model_view_v3(
        report_payload=report_payload,
        case_evidence=case_evidence,
        normalize_fairness_gate_decision=_normalize_fairness_gate_decision,
    )


def _build_courtroom_read_model_light_summary_for_runtime(
    *,
    courtroom_view: dict[str, Any],
) -> dict[str, Any]:
    return build_courtroom_read_model_light_summary_v3(
        courtroom_view=courtroom_view,
        normalize_fairness_gate_decision=_normalize_fairness_gate_decision,
    )


def _build_courtroom_drilldown_bundle_view_for_runtime(
    *,
    courtroom_view: dict[str, Any],
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


def _extract_optional_datetime_for_runtime(
    payload: dict[str, Any],
    *keys: str,
) -> datetime | None:
    return extract_optional_datetime_v3(
        payload,
        *keys,
        normalize_query_datetime=_normalize_query_datetime,
    )


def _build_case_fairness_item_for_runtime(
    *,
    case_id: int,
    dispatch_type: str,
    trace_id: str,
    workflow_job: WorkflowJob | None,
    workflow_events: list[Any],
    report_payload: dict[str, Any] | None,
    latest_run: FactFairnessBenchmarkRun | None,
    latest_shadow_run: FactFairnessShadowRun | None,
) -> dict[str, Any]:
    return build_case_fairness_item_v3(
        case_id=case_id,
        dispatch_type=dispatch_type,
        trace_id=trace_id,
        workflow_job=workflow_job,
        workflow_events=workflow_events,
        report_payload=report_payload,
        latest_run=latest_run,
        latest_shadow_run=latest_shadow_run,
        normalize_fairness_gate_decision=_normalize_fairness_gate_decision,
        serialize_fairness_benchmark_run=_serialize_fairness_benchmark_run,
        serialize_fairness_shadow_run=_serialize_fairness_shadow_run,
        trust_challenge_event_type=TRUST_CHALLENGE_EVENT_TYPE,
    )


def _build_case_fairness_aggregations_for_runtime(
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    return build_case_fairness_aggregations_v3(
        items,
        case_fairness_gate_conclusions=CASE_FAIRNESS_GATE_CONCLUSIONS,
    )


def _build_trust_challenge_id_for_runtime(*, case_id: int) -> str:
    return f"chlg-{max(0, int(case_id))}-{uuid4().hex[:12]}"


def _build_final_report_payload_for_runtime(
    *,
    runtime: AppRuntime,
    request: Any,
    phase_receipts: list[Any] | None,
    fairness_thresholds: dict[str, Any] | None,
    panel_runtime_profiles: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    return build_final_report_payload_for_dispatch_v3(
        request=request,
        phase_receipts=phase_receipts,
        fairness_thresholds=fairness_thresholds,
        panel_runtime_profiles=panel_runtime_profiles,
        list_dispatch_receipts=runtime.trace_store.list_dispatch_receipts,
        build_final_report_payload=build_final_report_payload_v3_final,
        judge_style_mode=runtime.dispatch_runtime_cfg.judge_style_mode,
    )


async def _ensure_workflow_schema_ready_for_runtime(
    *,
    runtime: AppRuntime,
    workflow_schema_state: dict[str, bool],
    workflow_schema_lock: asyncio.Lock,
) -> None:
    if workflow_schema_state["ready"] or not runtime.settings.db_auto_create_schema:
        return
    async with workflow_schema_lock:
        if workflow_schema_state["ready"]:
            return
        await runtime.workflow_runtime.db.create_schema()
        workflow_schema_state["ready"] = True


async def _ensure_registry_runtime_ready_for_runtime(
    *,
    runtime: AppRuntime,
    ensure_workflow_schema_ready: Callable[[], Awaitable[None]],
) -> None:
    await ensure_workflow_schema_ready()
    await runtime.registry_product_runtime.ensure_loaded()


def _build_replay_dependency_packs_for_runtime(
    *,
    runtime: AppRuntime,
    ensure_registry_runtime_ready: Callable[[], Awaitable[None]],
    resolve_policy_profile: Callable[..., Any],
    resolve_prompt_profile: Callable[..., Any],
    resolve_tool_profile: Callable[..., Any],
    build_final_report_payload: Callable[..., dict[str, Any]],
    resolve_panel_runtime_profiles: Callable[..., dict[str, dict[str, Any]]],
    build_phase_report_payload: Callable[..., Awaitable[dict[str, Any]]],
    attach_judge_agent_runtime_trace: Callable[..., Awaitable[None]],
    attach_policy_trace_snapshot: Callable[..., None],
    get_dispatch_receipt: Callable[..., Awaitable[Any | None]],
    list_dispatch_receipts: Callable[..., Awaitable[list[Any]]],
    append_replay_record: Callable[..., Awaitable[FactReplayRecord]],
    workflow_mark_replay: Callable[..., Awaitable[None]],
    upsert_claim_ledger_record: Callable[..., Awaitable[FactClaimLedgerRecord | None]],
) -> tuple[
    ReplayContextDependencyPack_v3,
    ReplayReportDependencyPack_v3,
    ReplayFinalizeDependencyPack_v3,
]:
    context_dependencies = ReplayContextDependencyPack_v3(
        normalize_replay_dispatch_type=normalize_replay_dispatch_type_v3,
        get_dispatch_receipt=get_dispatch_receipt,
        choose_replay_dispatch_receipt=choose_replay_dispatch_receipt_v3,
        extract_replay_request_snapshot=extract_replay_request_snapshot_v3,
        resolve_replay_trace_id=resolve_replay_trace_id_v3,
    )
    report_dependencies = ReplayReportDependencyPack_v3(
        ensure_registry_runtime_ready=ensure_registry_runtime_ready,
        final_request_model_validate=FinalDispatchRequest.model_validate,
        phase_request_model_validate=PhaseDispatchRequest.model_validate,
        validate_final_dispatch_request=validate_final_dispatch_request_v3,
        validate_phase_dispatch_request=validate_phase_dispatch_request_v3,
        resolve_policy_profile=resolve_policy_profile,
        resolve_prompt_profile=resolve_prompt_profile,
        resolve_tool_profile=resolve_tool_profile,
        list_dispatch_receipts=list_dispatch_receipts,
        build_final_report_payload=build_final_report_payload,
        resolve_panel_runtime_profiles=resolve_panel_runtime_profiles,
        build_phase_report_payload=build_phase_report_payload,
        attach_judge_agent_runtime_trace=attach_judge_agent_runtime_trace,
        attach_policy_trace_snapshot=attach_policy_trace_snapshot,
        attach_report_attestation=attach_report_attestation_v3,
        validate_final_report_payload_contract=validate_final_report_payload_contract_v3_final,
        settings=runtime.settings,
        gateway_runtime=runtime.gateway_runtime,
    )
    finalize_dependencies = ReplayFinalizeDependencyPack_v3(
        provider=runtime.settings.provider,
        get_trace=runtime.trace_store.get_trace,
        trace_register_start=runtime.trace_store.register_start,
        trace_mark_replay=runtime.trace_store.mark_replay,
        append_replay_record=append_replay_record,
        workflow_mark_replay=workflow_mark_replay,
        upsert_claim_ledger_record=upsert_claim_ledger_record,
        build_verdict_contract=build_verdict_contract_v3,
        build_replay_route_payload=build_replay_route_payload_v3,
        safe_float=safe_float_v3,
        resolve_winner=resolve_winner_v3,
        draw_margin=0.8,
        judge_core_stage=JUDGE_CORE_STAGE_REPLAY_COMPUTED,
        judge_core_version=JUDGE_CORE_VERSION,
    )
    return context_dependencies, report_dependencies, finalize_dependencies


def create_app(runtime: AppRuntime) -> FastAPI:
    app = FastAPI(title="AI Judge Service", version="0.2.0")
    judge_core = JudgeCoreOrchestrator(
        workflow_orchestrator=runtime.workflow_runtime.orchestrator
    )
    workflow_schema_state = {"ready": False}
    workflow_schema_lock = asyncio.Lock()
    _ensure_workflow_schema_ready = partial(
        _ensure_workflow_schema_ready_for_runtime,
        runtime=runtime,
        workflow_schema_state=workflow_schema_state,
        workflow_schema_lock=workflow_schema_lock,
    )
    _ensure_registry_runtime_ready = partial(
        _ensure_registry_runtime_ready_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )

    _persist_dispatch_receipt = partial(
        _persist_dispatch_receipt_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )

    _get_dispatch_receipt = partial(
        _get_dispatch_receipt_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _list_dispatch_receipts = partial(
        _list_dispatch_receipts_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _append_replay_record = partial(
        _append_replay_record_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _list_replay_records = partial(
        _list_replay_records_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )

    _upsert_claim_ledger_record = partial(
        _upsert_claim_ledger_record_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )

    _get_claim_ledger_record = partial(
        _get_claim_ledger_record_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _list_claim_ledger_records = partial(
        _list_claim_ledger_records_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )

    _upsert_fairness_benchmark_run = partial(
        _upsert_fairness_benchmark_run_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _list_fairness_benchmark_runs = partial(
        _list_fairness_benchmark_runs_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _upsert_fairness_shadow_run = partial(
        _upsert_fairness_shadow_run_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _list_fairness_shadow_runs = partial(
        _list_fairness_shadow_runs_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )

    _sync_audit_alert_to_facts = partial(
        _sync_audit_alert_to_facts_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )

    _list_audit_alerts = partial(
        _list_audit_alerts_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )

    _workflow_register_and_mark_blinded = partial(
        _workflow_register_and_mark_blinded_for_runtime,
        judge_core=judge_core,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _workflow_register_and_mark_case_built = partial(
        _workflow_register_and_mark_case_built_for_runtime,
        judge_core=judge_core,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _workflow_mark_completed = partial(
        _workflow_mark_completed_for_runtime,
        judge_core=judge_core,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _workflow_mark_review_required = partial(
        _workflow_mark_review_required_for_runtime,
        judge_core=judge_core,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _workflow_mark_failed = partial(
        _workflow_mark_failed_for_runtime,
        judge_core=judge_core,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _workflow_mark_replay = partial(
        _workflow_mark_replay_for_runtime,
        judge_core=judge_core,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )

    _workflow_get_job = partial(
        _workflow_get_job_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _workflow_list_jobs = partial(
        _workflow_list_jobs_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _workflow_list_events = partial(
        _workflow_list_events_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
    )
    _workflow_append_event = partial(
        _workflow_append_event_for_runtime,
        runtime=runtime,
        ensure_workflow_schema_ready=_ensure_workflow_schema_ready,
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
        _build_shared_room_context_for_runtime,
        list_dispatch_receipts=_list_dispatch_receipts,
        workflow_list_jobs=_workflow_list_jobs,
    )
    _resolve_report_context_for_case = partial(
        _resolve_report_context_for_case_for_runtime,
        get_dispatch_receipt=_get_dispatch_receipt,
        run_trust_read_guard=_run_trust_read_guard,
    )
    _build_trust_phasea_bundle = partial(
        _build_trust_phasea_bundle_for_runtime,
        get_dispatch_receipt=_get_dispatch_receipt,
        get_workflow_job=_workflow_get_job,
        list_workflow_events=_workflow_list_events,
        list_audit_alerts=_list_audit_alerts,
        serialize_workflow_job=_serialize_workflow_job,
        provider=runtime.settings.provider,
        run_trust_read_guard=_run_trust_read_guard,
    )
    _transition_judge_alert_status = partial(
        _transition_judge_alert_status_for_runtime,
        transition_audit_alert=runtime.trace_store.transition_audit_alert,
        sync_audit_alert_to_facts=_sync_audit_alert_to_facts,
        facts_transition_audit_alert=runtime.workflow_runtime.facts.transition_audit_alert,
        serialize_alert_item=serialize_alert_item_v3,
        run_review_route_guard=_run_review_route_guard,
    )
    serialize_policy_profile_with_domain_family = partial(
        _serialize_policy_profile_with_domain_family_for_runtime,
        runtime=runtime,
    )
    build_registry_governance_dependency_pack = partial(
        _build_registry_governance_route_dependency_pack_for_runtime,
        runtime=runtime,
        evaluate_policy_registry_dependency_health=evaluate_policy_registry_dependency_health,
        evaluate_policy_release_fairness_gate=evaluate_policy_release_fairness_gate,
        list_audit_alerts=_list_audit_alerts,
    )
    registry_release_gate_dependencies = (
        _build_registry_release_gate_dependencies_for_runtime(
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
        _build_trust_challenge_common_dependencies_for_runtime(
            resolve_report_context_for_case=_resolve_report_context_for_case,
            workflow_get_job=_workflow_get_job,
            workflow_append_event=_workflow_append_event,
            workflow_mark_review_required=_workflow_mark_review_required,
            build_trust_phasea_bundle=_build_trust_phasea_bundle,
            serialize_workflow_job=_serialize_workflow_job,
            trust_challenge_event_type=TRUST_CHALLENGE_EVENT_TYPE,
            trust_challenge_state_accepted=TRUST_CHALLENGE_STATE_ACCEPTED,
            trust_challenge_state_under_review=TRUST_CHALLENGE_STATE_UNDER_REVIEW,
        )
    )
    build_review_case_risk_profile = partial(
        _build_review_case_risk_profile_for_runtime,
        normalize_query_datetime=_normalize_query_datetime,
    )
    build_trust_challenge_priority_profile = partial(
        _build_trust_challenge_priority_profile_for_runtime,
        normalize_query_datetime=_normalize_query_datetime,
        trust_challenge_open_states=TRUST_CHALLENGE_OPEN_STATES,
    )
    build_trust_challenge_action_hints = partial(
        _build_trust_challenge_action_hints_for_runtime,
        trust_challenge_open_states=TRUST_CHALLENGE_OPEN_STATES,
    )
    build_review_trust_unified_priority_profile = partial(
        _build_review_trust_unified_priority_profile_for_runtime,
        trust_challenge_open_states=TRUST_CHALLENGE_OPEN_STATES,
    )
    build_courtroom_read_model_view = _build_courtroom_read_model_view_for_runtime
    build_courtroom_read_model_light_summary = (
        _build_courtroom_read_model_light_summary_for_runtime
    )
    build_courtroom_drilldown_bundle_view = (
        _build_courtroom_drilldown_bundle_view_for_runtime
    )
    extract_optional_datetime = _extract_optional_datetime_for_runtime
    build_case_fairness_item = _build_case_fairness_item_for_runtime
    build_case_fairness_aggregations = _build_case_fairness_aggregations_for_runtime
    resolve_idempotency_or_raise = partial(
        resolve_idempotency_or_raise_v3,
        resolve_idempotency=runtime.trace_store.resolve_idempotency,
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
        _build_final_report_payload_for_runtime,
        runtime=runtime,
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
        _attach_policy_trace_snapshot_for_runtime,
        runtime=runtime,
    )
    invoke_callback_with_retry = partial(
        _invoke_v3_callback_with_retry_for_runtime,
        runtime=runtime,
    )
    invoke_phase_failed_callback_with_retry = partial(
        _invoke_failed_callback_with_retry_for_runtime,
        runtime=runtime,
        dispatch_type="phase",
        callback_phase_failed_fn=runtime.callback_phase_failed_fn,
        callback_final_failed_fn=runtime.callback_final_failed_fn,
    )
    invoke_final_failed_callback_with_retry = partial(
        _invoke_failed_callback_with_retry_for_runtime,
        runtime=runtime,
        dispatch_type="final",
        callback_phase_failed_fn=runtime.callback_phase_failed_fn,
        callback_final_failed_fn=runtime.callback_final_failed_fn,
    )
    (
        replay_context_dependencies,
        replay_report_dependencies,
        replay_finalize_dependencies,
    ) = _build_replay_dependency_packs_for_runtime(
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

    @app.get("/healthz")
    async def healthz() -> dict[str, bool]:
        return {"ok": True}

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
        run_registry_route_guard=_run_registry_route_guard,
        build_policy_registry_profiles_payload_with_ready=(
            _build_policy_registry_profiles_payload_with_ready_for_runtime
        ),
        build_policy_registry_profile_payload_with_ready=(
            _build_policy_registry_profile_payload_with_ready_for_runtime
        ),
        build_registry_profiles_payload_with_ready=(
            _build_registry_profiles_payload_with_ready_for_runtime
        ),
        build_registry_profile_payload_with_ready=(
            _build_registry_profile_payload_with_ready_for_runtime
        ),
        build_registry_audits_payload=_build_registry_audits_payload_for_runtime,
        build_registry_releases_payload=_build_registry_releases_payload_for_runtime,
        build_registry_release_payload=_build_registry_release_payload_for_runtime,
        enforce_policy_domain_judge_family_profile_payload=(
            _enforce_policy_domain_judge_family_profile_payload
        ),
        raise_http_422_from_value_error=_raise_http_422_from_value_error,
        raise_http_404_from_lookup_error=_raise_http_404_from_lookup_error,
        raise_registry_value_error=_raise_registry_value_error,
        raise_registry_version_not_found_lookup_error=(
            _raise_registry_version_not_found_lookup_error
        ),
    )

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
                resolve_idempotency_or_raise=resolve_idempotency_or_raise,
                ensure_registry_runtime_ready=_ensure_registry_runtime_ready,
                resolve_policy_profile=resolve_policy_profile,
                resolve_prompt_profile=resolve_prompt_profile,
                resolve_tool_profile=resolve_tool_profile,
                workflow_get_job=_workflow_get_job,
                build_workflow_job=build_workflow_job_v3,
                workflow_register_and_mark_case_built=_workflow_register_and_mark_case_built,
                serialize_workflow_job=_serialize_workflow_job,
                trace_register_start=runtime.trace_store.register_start,
                trace_register_success=runtime.trace_store.register_success,
                build_trace_report_summary=build_trace_report_summary_v3,
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
        sensitive_hits = find_sensitive_key_hits_v3(raw_payload)
        if sensitive_hits:
            await _run_judge_command_route_guard(
                build_blindization_rejection_route_payload_v3(
                    dispatch_type="phase",
                    raw_payload=raw_payload,
                    sensitive_hits=sensitive_hits,
                    extract_dispatch_meta_from_raw=extract_dispatch_meta_from_raw,
                    extract_receipt_dims_from_raw=extract_receipt_dims_from_raw,
                    build_workflow_job=build_workflow_job_v3,
                    trace_register_start=runtime.trace_store.register_start,
                    workflow_register_and_mark_blinded=_workflow_register_and_mark_blinded,
                    build_failed_callback_payload=build_failed_callback_payload_v3,
                    invoke_failed_callback_with_retry=(
                        invoke_phase_failed_callback_with_retry
                    ),
                    with_error_contract=with_error_contract_v3,
                    persist_dispatch_receipt=_persist_dispatch_receipt,
                    trace_register_failure=runtime.trace_store.register_failure,
                    workflow_mark_failed=_workflow_mark_failed,
                )
            )
        preflight = await _run_judge_command_route_guard(
            build_phase_dispatch_preflight_route_payload_v3(
                raw_payload=raw_payload,
                phase_dispatch_model_validate=PhaseDispatchRequest.model_validate,
                validate_phase_dispatch_request=validate_phase_dispatch_request_v3,
                resolve_idempotency_or_raise=resolve_idempotency_or_raise,
                ensure_registry_runtime_ready=_ensure_registry_runtime_ready,
                resolve_policy_profile=resolve_policy_profile,
                resolve_prompt_profile=resolve_prompt_profile,
                resolve_tool_profile=resolve_tool_profile,
                build_phase_dispatch_accepted_response=build_phase_dispatch_accepted_response_v3,
                build_workflow_job=build_workflow_job_v3,
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
                build_phase_report_payload=build_phase_report_payload,
                attach_judge_agent_runtime_trace=attach_judge_agent_runtime_trace,
                attach_policy_trace_snapshot=attach_policy_trace_snapshot,
                attach_report_attestation=attach_report_attestation_v3,
                upsert_claim_ledger_record=_upsert_claim_ledger_record,
                build_phase_judge_workflow_payload=build_phase_judge_workflow_payload_v3,
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
                report_callback_fn=cast(
                    CallbackReportFn,
                    resolve_report_callback_fn_for_dispatch_v3(
                        dispatch_type="phase",
                        callback_phase_report_fn=runtime.callback_phase_report_fn,
                        callback_final_report_fn=runtime.callback_final_report_fn,
                    ),
                ),
                failed_callback_fn=cast(
                    CallbackReportFn,
                    resolve_failed_callback_fn_for_dispatch_v3(
                        dispatch_type="phase",
                        callback_phase_failed_fn=runtime.callback_phase_failed_fn,
                        callback_final_failed_fn=runtime.callback_final_failed_fn,
                    ),
                ),
                invoke_with_retry=invoke_callback_with_retry,
                build_failed_callback_payload=build_failed_callback_payload_v3,
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
                with_error_contract=with_error_contract_v3,
                persist_dispatch_receipt=_persist_dispatch_receipt,
                trace_register_failure=runtime.trace_store.register_failure,
                trace_register_success=runtime.trace_store.register_success,
                workflow_mark_failed=_workflow_mark_failed,
                workflow_mark_completed=_workflow_mark_completed,
                build_phase_workflow_reported_payload=build_phase_workflow_reported_payload_v3,
                build_trace_report_summary=build_trace_report_summary_v3,
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
        sensitive_hits = find_sensitive_key_hits_v3(raw_payload)
        if sensitive_hits:
            await _run_judge_command_route_guard(
                build_blindization_rejection_route_payload_v3(
                    dispatch_type="final",
                    raw_payload=raw_payload,
                    sensitive_hits=sensitive_hits,
                    extract_dispatch_meta_from_raw=extract_dispatch_meta_from_raw,
                    extract_receipt_dims_from_raw=extract_receipt_dims_from_raw,
                    build_workflow_job=build_workflow_job_v3,
                    trace_register_start=runtime.trace_store.register_start,
                    workflow_register_and_mark_blinded=_workflow_register_and_mark_blinded,
                    build_failed_callback_payload=build_failed_callback_payload_v3,
                    invoke_failed_callback_with_retry=(
                        invoke_final_failed_callback_with_retry
                    ),
                    with_error_contract=with_error_contract_v3,
                    persist_dispatch_receipt=_persist_dispatch_receipt,
                    trace_register_failure=runtime.trace_store.register_failure,
                    workflow_mark_failed=_workflow_mark_failed,
                )
            )
        preflight = await _run_judge_command_route_guard(
            build_final_dispatch_preflight_route_payload_v3(
                raw_payload=raw_payload,
                final_dispatch_model_validate=FinalDispatchRequest.model_validate,
                validate_final_dispatch_request=validate_final_dispatch_request_v3,
                resolve_idempotency_or_raise=resolve_idempotency_or_raise,
                ensure_registry_runtime_ready=_ensure_registry_runtime_ready,
                resolve_policy_profile=resolve_policy_profile,
                resolve_prompt_profile=resolve_prompt_profile,
                resolve_tool_profile=resolve_tool_profile,
                build_final_dispatch_accepted_response=build_final_dispatch_accepted_response_v3,
                build_workflow_job=build_workflow_job_v3,
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
                build_final_report_payload=build_final_report_payload,
                resolve_panel_runtime_profiles=resolve_panel_runtime_profiles,
                attach_judge_agent_runtime_trace=attach_judge_agent_runtime_trace,
                attach_policy_trace_snapshot=attach_policy_trace_snapshot,
                attach_report_attestation=attach_report_attestation_v3,
                upsert_claim_ledger_record=_upsert_claim_ledger_record,
                build_final_judge_workflow_payload=build_final_judge_workflow_payload_v3,
                validate_final_report_payload_contract=validate_final_report_payload_contract_v3_final,
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
                    build_failed_callback_payload=build_failed_callback_payload_v3,
                    invoke_failed_callback_with_retry=(
                        invoke_final_failed_callback_with_retry
                    ),
                    with_error_contract=with_error_contract_v3,
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
                report_callback_fn=cast(
                    CallbackReportFn,
                    resolve_report_callback_fn_for_dispatch_v3(
                        dispatch_type="final",
                        callback_phase_report_fn=runtime.callback_phase_report_fn,
                        callback_final_report_fn=runtime.callback_final_report_fn,
                    ),
                ),
                failed_callback_fn=cast(
                    CallbackReportFn,
                    resolve_failed_callback_fn_for_dispatch_v3(
                        dispatch_type="final",
                        callback_phase_failed_fn=runtime.callback_phase_failed_fn,
                        callback_final_failed_fn=runtime.callback_final_failed_fn,
                    ),
                ),
                invoke_with_retry=invoke_callback_with_retry,
                build_failed_callback_payload=build_failed_callback_payload_v3,
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
                with_error_contract=with_error_contract_v3,
                persist_dispatch_receipt=_persist_dispatch_receipt,
                trace_register_failure=runtime.trace_store.register_failure,
                trace_register_success=runtime.trace_store.register_success,
                workflow_mark_failed=_workflow_mark_failed,
                workflow_mark_review_required=_workflow_mark_review_required,
                workflow_mark_completed=_workflow_mark_completed,
                build_final_workflow_reported_payload=build_final_workflow_reported_payload_v3,
                build_trace_report_summary=build_trace_report_summary_v3,
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
        return await _build_dispatch_receipt_payload_for_runtime(
            case_id=case_id,
            dispatch_type="phase",
            not_found_detail="phase_dispatch_receipt_not_found",
            get_dispatch_receipt=_get_dispatch_receipt,
        )

    @app.get("/internal/judge/v3/final/cases/{case_id}/receipt")
    async def get_final_dispatch_receipt(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _build_dispatch_receipt_payload_for_runtime(
            case_id=case_id,
            dispatch_type="final",
            not_found_detail="final_dispatch_receipt_not_found",
            get_dispatch_receipt=_get_dispatch_receipt,
        )

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
                build_verdict_contract=build_verdict_contract_v3,
                build_case_evidence_view=build_case_evidence_view_v3,
                build_judge_core_view=_build_judge_core_view,
                build_case_overview_replay_items=build_case_overview_replay_items_v3,
                build_case_overview_payload=build_case_overview_payload_v3,
                serialize_workflow_job=_serialize_workflow_job,
                serialize_dispatch_receipt=serialize_dispatch_receipt_v3,
                serialize_alert_item=serialize_alert_item_v3,
            )
        )
        return _validate_contract_or_raise_http_500_for_runtime(
            payload=payload,
            validate_contract=validate_case_overview_contract_v3,
            code="case_overview_contract_violation",
        )

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
                serialize_claim_ledger_record=serialize_claim_ledger_record_v3,
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
                build_verdict_contract=build_verdict_contract_v3,
                build_case_evidence_view=build_case_evidence_view_v3,
                build_courtroom_read_model_view=build_courtroom_read_model_view,
                build_judge_core_view=_build_judge_core_view,
                list_audit_alerts=_list_audit_alerts,
                build_case_courtroom_read_model_payload=build_case_courtroom_read_model_payload_v3,
                serialize_workflow_job=_serialize_workflow_job,
                serialize_alert_item=serialize_alert_item_v3,
            )
        )
        return _validate_contract_or_raise_http_500_for_runtime(
            payload=response_payload,
            validate_contract=validate_courtroom_read_model_contract_v3,
            code="courtroom_read_model_contract_violation",
        )

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
                normalize_review_case_risk_level=normalize_review_case_risk_level_v3,
                review_case_risk_level_values=REVIEW_CASE_RISK_LEVEL_VALUES,
                normalize_review_case_sla_bucket=normalize_review_case_sla_bucket_v3,
                review_case_sla_bucket_values=REVIEW_CASE_SLA_BUCKET_VALUES,
                normalize_query_datetime=_normalize_query_datetime,
                normalize_courtroom_case_sort_by=normalize_courtroom_case_sort_by_v3,
                normalize_courtroom_case_sort_order=normalize_courtroom_case_sort_order_v3,
                courtroom_case_sort_fields=COURTROOM_CASE_SORT_FIELDS,
                workflow_list_jobs=_workflow_list_jobs,
                resolve_report_context_for_case=_resolve_report_context_for_case,
                trace_get=runtime.trace_store.get_trace,
                build_review_case_risk_profile=build_review_case_risk_profile,
                build_verdict_contract=build_verdict_contract_v3,
                build_case_evidence_view=build_case_evidence_view_v3,
                build_courtroom_read_model_view=build_courtroom_read_model_view,
                serialize_workflow_job=_serialize_workflow_job,
                build_courtroom_read_model_light_summary=(
                    build_courtroom_read_model_light_summary
                ),
                build_courtroom_case_sort_key=build_courtroom_case_sort_key_v3,
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
                normalize_review_case_risk_level=normalize_review_case_risk_level_v3,
                review_case_risk_level_values=REVIEW_CASE_RISK_LEVEL_VALUES,
                normalize_review_case_sla_bucket=normalize_review_case_sla_bucket_v3,
                review_case_sla_bucket_values=REVIEW_CASE_SLA_BUCKET_VALUES,
                normalize_query_datetime=_normalize_query_datetime,
                normalize_courtroom_case_sort_by=normalize_courtroom_case_sort_by_v3,
                normalize_courtroom_case_sort_order=normalize_courtroom_case_sort_order_v3,
                courtroom_case_sort_fields=COURTROOM_CASE_SORT_FIELDS,
                workflow_list_jobs=_workflow_list_jobs,
                resolve_report_context_for_case=_resolve_report_context_for_case,
                trace_get=runtime.trace_store.get_trace,
                build_review_case_risk_profile=build_review_case_risk_profile,
                build_verdict_contract=build_verdict_contract_v3,
                build_case_evidence_view=build_case_evidence_view_v3,
                build_courtroom_read_model_view=build_courtroom_read_model_view,
                build_courtroom_drilldown_bundle_view=(
                    build_courtroom_drilldown_bundle_view
                ),
                build_courtroom_drilldown_action_hints=build_courtroom_drilldown_action_hints_v3,
                serialize_workflow_job=_serialize_workflow_job,
                build_courtroom_case_sort_key=build_courtroom_case_sort_key_v3,
            )
        )
        return _validate_contract_or_raise_http_500_for_runtime(
            payload=payload,
            validate_contract=validate_courtroom_drilldown_bundle_contract_v3,
            code="courtroom_drilldown_bundle_contract_violation",
        )

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
                normalize_review_case_risk_level=normalize_review_case_risk_level_v3,
                review_case_risk_level_values=REVIEW_CASE_RISK_LEVEL_VALUES,
                normalize_review_case_sla_bucket=normalize_review_case_sla_bucket_v3,
                review_case_sla_bucket_values=REVIEW_CASE_SLA_BUCKET_VALUES,
                normalize_evidence_claim_reliability_level=normalize_evidence_claim_reliability_level_v3,
                evidence_claim_reliability_level_values=EVIDENCE_CLAIM_RELIABILITY_LEVEL_VALUES,
                normalize_query_datetime=_normalize_query_datetime,
                normalize_evidence_claim_queue_sort_by=normalize_evidence_claim_queue_sort_by_v3,
                normalize_evidence_claim_queue_sort_order=normalize_evidence_claim_queue_sort_order_v3,
                evidence_claim_queue_sort_fields=EVIDENCE_CLAIM_QUEUE_SORT_FIELDS,
                workflow_list_jobs=_workflow_list_jobs,
                resolve_report_context_for_case=_resolve_report_context_for_case,
                trace_get=runtime.trace_store.get_trace,
                build_review_case_risk_profile=build_review_case_risk_profile,
                build_verdict_contract=build_verdict_contract_v3,
                build_case_evidence_view=build_case_evidence_view_v3,
                build_courtroom_read_model_view=build_courtroom_read_model_view,
                build_courtroom_read_model_light_summary=(
                    build_courtroom_read_model_light_summary
                ),
                build_evidence_claim_ops_profile=build_evidence_claim_ops_profile_v3,
                build_evidence_claim_action_hints=build_evidence_claim_action_hints_v3,
                serialize_workflow_job=_serialize_workflow_job,
                build_evidence_claim_queue_sort_key=build_evidence_claim_queue_sort_key_v3,
            )
        )
        return _validate_contract_or_raise_http_500_for_runtime(
            payload=payload,
            validate_contract=validate_evidence_claim_ops_queue_contract_v3,
            code="evidence_claim_ops_queue_contract_violation",
        )

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
                build_shared_room_context=build_shared_room_context,
                execute_agent=runtime.agent_runtime.execute,
                build_execution_request=AgentExecutionRequest,
                build_assistant_agent_response=build_assistant_agent_response_v3,
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
                build_shared_room_context=build_shared_room_context,
                execute_agent=runtime.agent_runtime.execute,
                build_execution_request=AgentExecutionRequest,
                build_assistant_agent_response=build_assistant_agent_response_v3,
            )
        )

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
                build_verdict_contract=build_verdict_contract_v3,
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
                context_dependencies=replay_context_dependencies,
                # replay 主路由只保留 HTTP 语义，重算编排统一在 applications 层完成。
                report_dependencies=replay_report_dependencies,
                finalize_dependencies=replay_finalize_dependencies,
            )
        )

    @app.get("/internal/judge/cases/{case_id}/trust/commitment")
    async def get_judge_trust_case_commitment(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _build_validated_trust_item_payload_for_runtime(
            case_id=case_id,
            dispatch_type=dispatch_type,
            item_key="commitment",
            validate_contract=validate_trust_commitment_contract_v3,
            violation_code="trust_commitment_contract_violation",
            build_trust_phasea_bundle=_build_trust_phasea_bundle,
        )

    @app.get("/internal/judge/cases/{case_id}/trust/verdict-attestation")
    async def get_judge_trust_verdict_attestation(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _build_validated_trust_item_payload_for_runtime(
            case_id=case_id,
            dispatch_type=dispatch_type,
            item_key="verdictAttestation",
            validate_contract=validate_trust_verdict_attestation_contract_v3,
            violation_code="trust_verdict_attestation_contract_violation",
            build_trust_phasea_bundle=_build_trust_phasea_bundle,
        )

    @app.get("/internal/judge/cases/{case_id}/trust/challenges")
    async def get_judge_trust_challenge_review(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _build_validated_trust_item_payload_for_runtime(
            case_id=case_id,
            dispatch_type=dispatch_type,
            item_key="challengeReview",
            validate_contract=validate_trust_challenge_review_contract_v3,
            violation_code="trust_challenge_review_contract_violation",
            build_trust_phasea_bundle=_build_trust_phasea_bundle,
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
        return await _build_trust_challenge_ops_queue_payload_for_runtime(
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
            workflow_list_jobs=_workflow_list_jobs,
            build_trust_phasea_bundle=_build_trust_phasea_bundle,
            get_trace=runtime.trace_store.get_trace,
            build_trust_challenge_priority_profile=build_trust_challenge_priority_profile,
            serialize_workflow_job=_serialize_workflow_job,
            build_trust_challenge_action_hints=build_trust_challenge_action_hints,
            run_trust_challenge_guard=_run_trust_challenge_guard,
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
        return await _build_trust_challenge_request_payload_for_runtime(
            case_id=case_id,
            dispatch_type=dispatch_type,
            reason_code=reason_code,
            reason=reason,
            requested_by=requested_by,
            auto_accept=auto_accept,
            trust_challenge_common_dependencies=trust_challenge_common_dependencies,
            upsert_audit_alert=runtime.trace_store.upsert_audit_alert,
            sync_audit_alert_to_facts=_sync_audit_alert_to_facts,
            run_trust_challenge_guard=_run_trust_challenge_guard,
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
        return await _build_trust_challenge_decision_payload_for_runtime(
            case_id=case_id,
            challenge_id=challenge_id,
            dispatch_type=dispatch_type,
            decision=decision,
            actor=actor,
            reason=reason,
            trust_challenge_common_dependencies=trust_challenge_common_dependencies,
            workflow_mark_completed=_workflow_mark_completed,
            workflow_mark_draw_pending_vote=runtime.workflow_runtime.orchestrator.mark_draw_pending_vote,
            resolve_open_alerts_for_review=resolve_open_alerts_for_review,
            run_trust_challenge_guard=_run_trust_challenge_guard,
        )

    @app.get("/internal/judge/cases/{case_id}/trust/kernel-version")
    async def get_judge_trust_kernel_version(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _build_validated_trust_item_payload_for_runtime(
            case_id=case_id,
            dispatch_type=dispatch_type,
            item_key="kernelVersion",
            validate_contract=validate_trust_kernel_version_contract_v3,
            violation_code="trust_kernel_version_contract_violation",
            build_trust_phasea_bundle=_build_trust_phasea_bundle,
        )

    @app.get("/internal/judge/cases/{case_id}/trust/audit-anchor")
    async def get_judge_trust_audit_anchor(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
        include_payload: bool = Query(default=False),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _build_trust_audit_anchor_payload_for_runtime(
            case_id=case_id,
            dispatch_type=dispatch_type,
            include_payload=include_payload,
            build_trust_phasea_bundle=_build_trust_phasea_bundle,
            build_audit_anchor_export=build_audit_anchor_export_v3,
            validate_contract=validate_trust_audit_anchor_contract_v3,
            violation_code="trust_audit_anchor_contract_violation",
        )

    @app.get("/internal/judge/cases/{case_id}/trust/public-verify")
    async def get_judge_trust_public_verify(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _build_trust_public_verify_payload_for_runtime(
            case_id=case_id,
            dispatch_type=dispatch_type,
            build_trust_phasea_bundle=_build_trust_phasea_bundle,
            build_audit_anchor_export=build_audit_anchor_export_v3,
            build_public_verify_payload=build_public_trust_verify_payload_v3,
            validate_contract=validate_trust_public_verify_contract_v3,
            violation_code="trust_public_verify_contract_violation",
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
        return await _build_replay_report_payload_for_runtime(
            case_id=case_id,
            get_trace=runtime.trace_store.get_trace,
            get_claim_ledger_record=_get_claim_ledger_record,
            run_replay_read_guard=_run_replay_read_guard,
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
        return _build_replay_reports_payload_for_runtime(
            status=status,
            winner=winner,
            callback_status=callback_status,
            trace_id=trace_id,
            created_after=created_after,
            created_before=created_before,
            has_audit_alert=has_audit_alert,
            limit=limit,
            include_report=include_report,
            list_traces=runtime.trace_store.list_traces,
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
                extract_optional_int=extract_optional_int_v3,
                extract_optional_float=extract_optional_float_v3,
                extract_optional_str=extract_optional_str_v3,
                extract_optional_bool=extract_optional_bool_v3,
                extract_optional_datetime=extract_optional_datetime,
                list_fairness_benchmark_runs=_list_fairness_benchmark_runs,
                upsert_fairness_benchmark_run=_upsert_fairness_benchmark_run,
                upsert_audit_alert=runtime.trace_store.upsert_audit_alert,
                sync_audit_alert_to_facts=_sync_audit_alert_to_facts,
                serialize_alert_item=serialize_alert_item_v3,
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
                extract_optional_int=extract_optional_int_v3,
                extract_optional_float=extract_optional_float_v3,
                extract_optional_str=extract_optional_str_v3,
                extract_optional_bool=extract_optional_bool_v3,
                extract_optional_datetime=extract_optional_datetime,
                list_fairness_benchmark_runs=_list_fairness_benchmark_runs,
                list_fairness_shadow_runs=_list_fairness_shadow_runs,
                upsert_fairness_shadow_run=_upsert_fairness_shadow_run,
                upsert_audit_alert=runtime.trace_store.upsert_audit_alert,
                sync_audit_alert_to_facts=_sync_audit_alert_to_facts,
                serialize_alert_item=serialize_alert_item_v3,
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
                build_case_fairness_item=build_case_fairness_item,
                validate_case_fairness_detail_contract=validate_case_fairness_detail_contract_v3,
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
                normalize_case_fairness_sort_by=normalize_case_fairness_sort_by_v3,
                case_fairness_sort_fields=CASE_FAIRNESS_SORT_FIELDS,
                normalize_case_fairness_sort_order=normalize_case_fairness_sort_order_v3,
                normalize_case_fairness_gate_conclusion=normalize_case_fairness_gate_conclusion_v3,
                case_fairness_gate_conclusions=CASE_FAIRNESS_GATE_CONCLUSIONS,
                normalize_case_fairness_challenge_state=normalize_case_fairness_challenge_state_v3,
                case_fairness_challenge_states=CASE_FAIRNESS_CHALLENGE_STATES,
                workflow_list_jobs=_workflow_list_jobs,
                get_trace=runtime.trace_store.get_trace,
                workflow_list_events=_workflow_list_events,
                list_fairness_benchmark_runs=_list_fairness_benchmark_runs,
                list_fairness_shadow_runs=_list_fairness_shadow_runs,
                build_case_fairness_item=build_case_fairness_item,
                build_case_fairness_sort_key=build_case_fairness_sort_key_v3,
                build_case_fairness_aggregations=build_case_fairness_aggregations,
                validate_case_fairness_list_contract=validate_case_fairness_list_contract_v3,
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
                build_case_fairness_aggregations=build_case_fairness_aggregations,
                build_fairness_dashboard_case_trends=build_fairness_dashboard_case_trends_v3,
                build_fairness_dashboard_run_trends=build_fairness_dashboard_run_trends_v3,
                build_fairness_dashboard_top_risk_cases=build_fairness_dashboard_top_risk_cases_v3,
                list_fairness_benchmark_runs=_list_fairness_benchmark_runs,
                list_fairness_shadow_runs=_list_fairness_shadow_runs,
                validate_fairness_dashboard_contract=validate_fairness_dashboard_contract_v3,
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
        return await _build_fairness_calibration_pack_payload_for_runtime(
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
            list_judge_case_fairness=list_judge_case_fairness,
            list_fairness_benchmark_runs=_list_fairness_benchmark_runs,
            list_fairness_shadow_runs=_list_fairness_shadow_runs,
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
        return await _build_fairness_policy_calibration_advisor_payload_for_runtime(
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
            list_judge_case_fairness=list_judge_case_fairness,
            list_fairness_benchmark_runs=_list_fairness_benchmark_runs,
            list_fairness_shadow_runs=_list_fairness_shadow_runs,
            evaluate_policy_release_fairness_gate=evaluate_policy_release_fairness_gate,
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
        return await _await_payload_or_raise_http_500_for_runtime(
            self_awaitable=_build_ops_read_model_pack_payload_for_runtime(
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
                runtime=runtime,
                get_judge_fairness_dashboard=get_judge_fairness_dashboard,
                get_registry_governance_overview=(
                    registry_route_handles.get_registry_governance_overview
                ),
                get_registry_prompt_tool_governance=(
                    registry_route_handles.get_registry_prompt_tool_governance
                ),
                get_policy_registry_dependency_health=(
                    registry_route_handles.get_policy_registry_dependency_health
                ),
                get_judge_fairness_policy_calibration_advisor=get_judge_fairness_policy_calibration_advisor,
                get_panel_runtime_readiness=get_panel_runtime_readiness,
                list_judge_courtroom_cases=list_judge_courtroom_cases,
                list_judge_courtroom_drilldown_bundle=list_judge_courtroom_drilldown_bundle,
                list_judge_evidence_claim_ops_queue=list_judge_evidence_claim_ops_queue,
                list_judge_trust_challenge_ops_queue=list_judge_trust_challenge_ops_queue,
                list_judge_review_jobs=list_judge_review_jobs,
                simulate_policy_release_gate=(
                    registry_route_handles.simulate_policy_release_gate
                ),
                get_judge_case_courtroom_read_model=get_judge_case_courtroom_read_model,
                get_judge_trust_public_verify=get_judge_trust_public_verify,
            ),
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
        return await _await_payload_or_raise_http_500_for_runtime(
            self_awaitable=_build_panel_runtime_profiles_payload_for_runtime(
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
                list_judge_case_fairness=list_judge_case_fairness,
                run_panel_runtime_route_guard=_run_panel_runtime_route_guard,
            ),
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
        return await _build_panel_runtime_readiness_payload_for_runtime(
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
            list_panel_runtime_profiles=list_panel_runtime_profiles,
            run_panel_runtime_route_guard=_run_panel_runtime_route_guard,
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
        return await _await_payload_or_raise_http_422_for_runtime(
            self_awaitable=_build_review_cases_list_payload_for_runtime(
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
                limit=limit,
                workflow_list_jobs=_workflow_list_jobs,
                workflow_list_events=_workflow_list_events,
                list_audit_alerts=_list_audit_alerts,
                get_trace=runtime.trace_store.get_trace,
                build_review_case_risk_profile=build_review_case_risk_profile,
                build_trust_challenge_priority_profile=build_trust_challenge_priority_profile,
                build_review_trust_unified_priority_profile=(
                    build_review_trust_unified_priority_profile
                ),
                serialize_workflow_job=_serialize_workflow_job,
            ),
        )

    @app.get("/internal/judge/review/cases/{case_id}")
    async def get_judge_review_job(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _await_payload_or_raise_http_404_for_runtime(
            self_awaitable=_build_review_case_detail_payload_for_runtime(
                case_id=case_id,
                workflow_get_job=_workflow_get_job,
                workflow_list_events=_workflow_list_events,
                list_audit_alerts=_list_audit_alerts,
                get_trace=runtime.trace_store.get_trace,
                serialize_workflow_job=_serialize_workflow_job,
                serialize_alert_item=serialize_alert_item_v3,
            ),
        )

    @app.post("/internal/judge/review/cases/{case_id}/decision")
    async def decide_judge_review_job(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        decision: str = Query(default="approve"),
        actor: str | None = Query(default=None),
        reason: str | None = Query(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _await_payload_or_raise_http_422_404_for_runtime(
            self_awaitable=_run_review_route_guard(
                build_review_case_decision_payload_v3(
                    case_id=case_id,
                    decision=decision,
                    actor=actor,
                    reason=reason,
                    workflow_get_job=_workflow_get_job,
                    workflow_mark_completed=_workflow_mark_completed,
                    workflow_mark_failed=_workflow_mark_failed,
                    resolve_open_alerts_for_review=resolve_open_alerts_for_review,
                    serialize_workflow_job=_serialize_workflow_job,
                )
            ),
        )

    @app.get("/internal/judge/cases/{case_id}/alerts")
    async def list_judge_job_alerts(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        status: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return await _build_case_alerts_payload_for_runtime(
            case_id=case_id,
            status=status,
            limit=limit,
            list_audit_alerts=_list_audit_alerts,
            serialize_alert_item=serialize_alert_item_v3,
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
        return await _await_payload_or_raise_http_422_for_runtime(
            self_awaitable=_build_alert_ops_view_payload_for_runtime(
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
                list_audit_alerts=_list_audit_alerts,
                list_alert_outbox=runtime.trace_store.list_alert_outbox,
            ),
        )

    @app.get("/internal/judge/alerts/outbox")
    async def list_judge_alert_outbox(
        x_ai_internal_key: str | None = Header(default=None),
        delivery_status: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return _build_alert_outbox_payload_for_runtime(
            delivery_status=delivery_status,
            limit=limit,
            list_alert_outbox=runtime.trace_store.list_alert_outbox,
            serialize_outbox_event=serialize_outbox_event_v3,
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
        return _build_payload_or_raise_http_404_for_runtime(
            builder=build_alert_outbox_delivery_payload_v3,
            item=item,
            serialize_outbox_event=serialize_outbox_event_v3,
        )

    @app.get("/internal/judge/rag/diagnostics")
    async def get_rag_diagnostics(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_key(runtime.settings, x_ai_internal_key)
        return _build_payload_or_raise_http_404_for_runtime(
            builder=build_rag_diagnostics_payload_v3,
            case_id=case_id,
            get_trace=runtime.trace_store.get_trace,
        )

    return app


def create_default_app(*, load_settings_fn: LoadSettingsFn = load_settings) -> FastAPI:
    return create_app(
        create_runtime(
            settings=load_settings_fn(),
        )
    )
