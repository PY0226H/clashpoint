use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use utoipa::{IntoParams, ToSchema};

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RequestJudgeJobInput {
    #[serde(default)]
    pub allow_rejudge: bool,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RequestJudgeJobOutput {
    pub accepted: bool,
    pub session_id: u64,
    pub status: String,
    pub reason: Option<String>,
    pub queued_phase_jobs: u32,
    pub queued_final_job: bool,
    pub trigger_mode: String,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgePhaseJobSnapshot {
    pub phase_job_id: u64,
    pub phase_no: i32,
    pub status: String,
    pub message_count: i32,
    pub dispatch_attempts: i32,
    pub last_dispatch_at: Option<DateTime<Utc>>,
    pub error_message: Option<String>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgeFinalJobSnapshot {
    pub final_job_id: u64,
    pub status: String,
    pub phase_start_no: i32,
    pub phase_end_no: i32,
    pub dispatch_attempts: i32,
    pub last_dispatch_at: Option<DateTime<Utc>>,
    pub error_message: Option<String>,
    pub error_code: Option<String>,
    pub contract_failure_type: Option<String>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgeRagSourceItem {
    pub chunk_id: String,
    pub title: String,
    pub source_url: String,
    pub score: Option<f64>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgeRagMeta {
    pub enabled: Option<bool>,
    pub used_by_model: Option<bool>,
    pub snippet_count: Option<u32>,
    pub source_whitelist: Vec<String>,
    pub sources: Vec<JudgeRagSourceItem>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgeReportDetail {
    pub report_id: u64,
    pub job_id: u64,
    pub winner: String,
    pub pro_score: i32,
    pub con_score: i32,
    pub logic_pro: i32,
    pub logic_con: i32,
    pub evidence_pro: i32,
    pub evidence_con: i32,
    pub rebuttal_pro: i32,
    pub rebuttal_con: i32,
    pub clarity_pro: i32,
    pub clarity_con: i32,
    pub pro_summary: String,
    pub con_summary: String,
    pub rationale: String,
    pub style_mode: String,
    pub rubric_version: String,
    pub needs_draw_vote: bool,
    pub rejudge_triggered: bool,
    pub payload: Value,
    pub rag: Option<JudgeRagMeta>,
    #[serde(default)]
    pub verdict_evidence: Vec<JudgeVerdictEvidenceItem>,
    #[serde(default)]
    pub stage_summaries: Vec<JudgeStageSummaryDetail>,
    pub stage_summaries_meta: Option<JudgeStageSummariesMeta>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgeFinalReportDetail {
    pub final_report_id: u64,
    pub final_job_id: u64,
    pub winner: String,
    pub pro_score: f64,
    pub con_score: f64,
    #[serde(default)]
    pub dimension_scores: Value,
    pub debate_summary: String,
    #[serde(default)]
    pub side_analysis: Value,
    pub verdict_reason: String,
    #[serde(default)]
    pub verdict_evidence_refs: Vec<Value>,
    #[serde(default)]
    pub phase_rollup_summary: Vec<Value>,
    #[serde(default)]
    pub retrieval_snapshot_rollup: Vec<Value>,
    pub winner_first: Option<String>,
    pub winner_second: Option<String>,
    pub winner_third: Option<String>,
    pub rejudge_triggered: bool,
    pub needs_draw_vote: bool,
    pub review_required: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub review_decision_sync: Option<Value>,
    #[serde(default)]
    pub claim_graph: Value,
    #[serde(default)]
    pub claim_graph_summary: Value,
    #[serde(default)]
    pub evidence_ledger: Value,
    #[serde(default)]
    pub verdict_ledger: Value,
    #[serde(default)]
    pub opinion_pack: Value,
    #[serde(default)]
    pub fairness_summary: Value,
    #[serde(default)]
    pub trust_attestation: Value,
    #[serde(default)]
    pub judge_trace: Value,
    #[serde(default)]
    pub audit_alerts: Vec<Value>,
    #[serde(default)]
    pub error_codes: Vec<String>,
    pub degradation_level: i32,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgeFinalDispatchDiagnostics {
    pub final_job_id: u64,
    pub status: String,
    pub phase_start_no: i32,
    pub phase_end_no: i32,
    pub dispatch_attempts: i32,
    pub last_dispatch_at: Option<DateTime<Utc>>,
    pub error_message: Option<String>,
    pub error_code: Option<String>,
    pub contract_failure_type: Option<String>,
    pub contract_failure_hint: Option<String>,
    pub contract_failure_action: Option<String>,
    pub contract_violation_blocked: bool,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgeFinalDispatchFailureTypeCount {
    pub failure_type: String,
    pub count: u32,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgeFinalDispatchFailureStats {
    pub total_failed_jobs: u32,
    pub unknown_failed_jobs: u32,
    #[serde(default)]
    pub by_type: Vec<JudgeFinalDispatchFailureTypeCount>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgeVerdictEvidenceItem {
    pub message_id: u64,
    pub side: String,
    pub role: Option<String>,
    pub reason: Option<String>,
    pub content: String,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetJudgeReportOutput {
    pub session_id: u64,
    pub status: String,
    pub status_reason: String,
    pub latest_phase_job: Option<JudgePhaseJobSnapshot>,
    pub latest_final_job: Option<JudgeFinalJobSnapshot>,
    pub final_dispatch_diagnostics: Option<JudgeFinalDispatchDiagnostics>,
    pub final_dispatch_failure_stats: Option<JudgeFinalDispatchFailureStats>,
    pub progress: JudgeReportProgress,
    pub final_report_summary: Option<JudgeFinalReportSummary>,
}

#[derive(Debug, Clone, Default, IntoParams, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetJudgeReportQuery {
    pub rejudge_run_no: Option<u32>,
}

#[derive(Debug, Clone, Default, IntoParams, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetJudgePublicVerifyQuery {
    pub rejudge_run_no: Option<u32>,
    pub dispatch_type: Option<String>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetJudgePublicVerifyOutput {
    pub session_id: u64,
    pub status: String,
    pub status_reason: String,
    pub case_id: Option<u64>,
    pub dispatch_type: String,
    #[serde(default)]
    pub verification_readiness: Value,
    #[serde(default)]
    pub cache_profile: Value,
    #[serde(default)]
    pub public_verify: Value,
}

#[derive(Debug, Clone, Default, IntoParams, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetJudgeChallengeQuery {
    pub rejudge_run_no: Option<u32>,
    pub dispatch_type: Option<String>,
}

#[derive(Debug, Clone, Default, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RequestJudgeChallengeInput {
    pub idempotency_key: Option<String>,
    pub reason_code: Option<String>,
    pub user_reason: Option<String>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RequestNpcCoachAdviceInput {
    pub query: String,
    pub trace_id: Option<String>,
    pub side: Option<String>,
    pub case_id: Option<u64>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RequestRoomQaAnswerInput {
    pub question: String,
    pub trace_id: Option<String>,
    pub case_id: Option<u64>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgeAssistantAdvisoryOutput {
    pub version: String,
    pub agent_kind: String,
    pub session_id: u64,
    pub case_id: Option<u64>,
    pub advisory_only: bool,
    pub status: String,
    pub status_reason: String,
    pub accepted: bool,
    pub error_code: Option<String>,
    pub error_message: Option<String>,
    #[serde(default)]
    pub capability_boundary: Value,
    #[serde(default)]
    pub shared_context: Value,
    #[serde(default)]
    pub advisory_context: Value,
    #[serde(default)]
    pub output: Value,
    #[serde(default)]
    pub cache_profile: Value,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetJudgeChallengeOutput {
    pub session_id: u64,
    pub status: String,
    pub status_reason: String,
    pub case_id: Option<u64>,
    pub dispatch_type: String,
    #[serde(default)]
    pub eligibility: Value,
    #[serde(default)]
    pub challenge: Value,
    #[serde(default)]
    pub review: Value,
    #[serde(default)]
    pub allowed_actions: Vec<String>,
    #[serde(default)]
    pub blockers: Vec<String>,
    #[serde(default)]
    pub cache_profile: Value,
    #[serde(default)]
    pub policy: Value,
    #[serde(default)]
    pub review_decision_sync: Value,
}

#[derive(Debug, Clone, IntoParams, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetJudgeReportFinalOutput {
    pub session_id: u64,
    pub final_report: Option<JudgeFinalReportDetail>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgeReportProgress {
    pub total_phase_jobs: u32,
    pub queued_phase_jobs: u32,
    pub dispatched_phase_jobs: u32,
    pub succeeded_phase_jobs: u32,
    pub failed_phase_jobs: u32,
    pub has_final_job: bool,
    pub has_final_report: bool,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgeFinalReportSummary {
    pub final_report_id: u64,
    pub winner: String,
    pub pro_score: f64,
    pub con_score: f64,
    pub rejudge_triggered: bool,
    pub needs_draw_vote: bool,
    pub review_required: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub review_decision_sync: Option<Value>,
    pub degradation_level: i32,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, IntoParams, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListJudgeReviewOpsQuery {
    pub from: Option<DateTime<Utc>>,
    pub to: Option<DateTime<Utc>>,
    pub winner: Option<String>,
    pub rejudge_triggered: Option<bool>,
    pub has_verdict_evidence: Option<bool>,
    #[serde(default)]
    pub anomaly_only: bool,
    pub limit: Option<u32>,
}

#[derive(Debug, Clone, IntoParams, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetJudgeFinalDispatchFailureStatsQuery {
    pub from: Option<DateTime<Utc>>,
    pub to: Option<DateTime<Utc>>,
    pub limit: Option<u32>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetJudgeFinalDispatchFailureStatsOutput {
    pub window_from: Option<DateTime<Utc>>,
    pub window_to: Option<DateTime<Utc>>,
    pub total_failed_jobs: u32,
    pub scanned_failed_jobs: u32,
    pub truncated: bool,
    pub unknown_failed_jobs: u32,
    #[serde(default)]
    pub by_type: Vec<JudgeFinalDispatchFailureTypeCount>,
}

#[derive(Debug, Clone, IntoParams, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListJudgeTraceReplayOpsQuery {
    pub from: Option<DateTime<Utc>>,
    pub to: Option<DateTime<Utc>>,
    pub session_id: Option<u64>,
    pub scope: Option<String>,
    pub status: Option<String>,
    pub limit: Option<u32>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgeTraceReplayOpsItem {
    pub scope: String,
    pub session_id: u64,
    pub trace_id: String,
    pub idempotency_key: String,
    pub status: String,
    pub created_at: DateTime<Utc>,
    pub dispatch_attempts: i32,
    pub last_dispatch_at: Option<DateTime<Utc>>,
    pub error_message: Option<String>,
    pub error_code: Option<String>,
    pub contract_failure_type: Option<String>,
    pub phase_case_id: Option<u64>,
    pub final_case_id: Option<u64>,
    pub phase_no: Option<i32>,
    pub phase_start_no: Option<i32>,
    pub phase_end_no: Option<i32>,
    pub phase_report_id: Option<u64>,
    pub final_report_id: Option<u64>,
    pub case_id: u64,
    pub report_id: Option<u64>,
    pub replay_action_count: u32,
    pub latest_replay_action_id: Option<u64>,
    pub latest_replay_at: Option<DateTime<Utc>>,
    pub replay_eligible: bool,
    pub replay_recommendation: Option<String>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListJudgeTraceReplayOpsOutput {
    pub window_from: Option<DateTime<Utc>>,
    pub window_to: Option<DateTime<Utc>>,
    pub scanned_count: u32,
    pub returned_count: u32,
    pub phase_count: u32,
    pub final_count: u32,
    pub failed_count: u32,
    pub replay_eligible_count: u32,
    #[serde(default)]
    pub items: Vec<JudgeTraceReplayOpsItem>,
}

#[derive(Debug, Clone, IntoParams, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetJudgeReplayPreviewOpsQuery {
    pub scope: String,
    pub case_id: u64,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgeReplayPreviewMeta {
    pub scope: String,
    pub case_id: u64,
    pub session_id: u64,
    pub status: String,
    pub trace_id: String,
    pub idempotency_key: String,
    pub rubric_version: String,
    pub judge_policy_version: String,
    pub topic_domain: String,
    pub retrieval_profile: Option<String>,
    pub phase_no: Option<i32>,
    pub phase_start_no: Option<i32>,
    pub phase_end_no: Option<i32>,
    pub message_start_id: Option<u64>,
    pub message_end_id: Option<u64>,
    pub message_count: Option<i32>,
    pub created_at: DateTime<Utc>,
    pub dispatch_attempts: i32,
    pub last_dispatch_at: Option<DateTime<Utc>>,
    pub error_message: Option<String>,
    pub replay_eligible: bool,
    pub replay_block_reason: Option<String>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetJudgeReplayPreviewOpsOutput {
    pub side_effect_free: bool,
    pub snapshot_hash: String,
    pub meta: JudgeReplayPreviewMeta,
    #[serde(default)]
    pub request_snapshot: Value,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ExecuteJudgeReplayOpsInput {
    pub scope: String,
    pub case_id: u64,
    pub reason: Option<String>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ExecuteJudgeReplayOpsOutput {
    pub audit_id: u64,
    pub scope: String,
    pub case_id: u64,
    pub session_id: u64,
    pub previous_status: String,
    pub new_status: String,
    pub previous_trace_id: String,
    pub new_trace_id: String,
    pub previous_idempotency_key: String,
    pub new_idempotency_key: String,
    pub replay_triggered_at: DateTime<Utc>,
}

#[derive(Debug, Clone, IntoParams, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListJudgeReplayActionsOpsQuery {
    pub from: Option<DateTime<Utc>>,
    pub to: Option<DateTime<Utc>>,
    pub scope: Option<String>,
    pub session_id: Option<u64>,
    pub case_id: Option<u64>,
    pub requested_by: Option<u64>,
    pub previous_status: Option<String>,
    pub new_status: Option<String>,
    pub reason_keyword: Option<String>,
    pub trace_keyword: Option<String>,
    pub limit: Option<u32>,
    pub offset: Option<u32>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgeReplayActionOpsItem {
    pub audit_id: u64,
    pub scope: String,
    pub case_id: u64,
    pub session_id: u64,
    pub requested_by: u64,
    pub reason: Option<String>,
    pub previous_status: String,
    pub new_status: String,
    pub previous_trace_id: String,
    pub new_trace_id: String,
    pub previous_idempotency_key: String,
    pub new_idempotency_key: String,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListJudgeReplayActionsOpsOutput {
    pub window_from: Option<DateTime<Utc>>,
    pub window_to: Option<DateTime<Utc>>,
    pub scanned_count: u32,
    pub returned_count: u32,
    pub has_more: bool,
    #[serde(default)]
    pub items: Vec<JudgeReplayActionOpsItem>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgeReviewOpsItem {
    pub report_id: u64,
    pub session_id: u64,
    pub job_id: u64,
    pub winner: String,
    pub winner_first: Option<String>,
    pub winner_second: Option<String>,
    pub winner_third: Option<String>,
    pub pro_score: i32,
    pub con_score: i32,
    pub score_gap: i32,
    pub style_mode: String,
    pub rubric_version: String,
    pub needs_draw_vote: bool,
    pub review_required: bool,
    pub rejudge_triggered: bool,
    pub has_verdict_evidence: bool,
    pub verdict_evidence_count: u32,
    #[serde(default)]
    pub abnormal_flags: Vec<String>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListJudgeReviewOpsOutput {
    pub scanned_count: u32,
    pub returned_count: u32,
    pub items: Vec<JudgeReviewOpsItem>,
}

#[derive(Debug, Clone, Default, IntoParams, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetJudgeRuntimeReadinessOpsQuery {
    pub dispatch_type: Option<String>,
    pub policy_version: Option<String>,
    pub window_days: Option<u32>,
    pub case_scan_limit: Option<u32>,
    pub include_case_trust: Option<bool>,
    pub trust_case_limit: Option<u32>,
    pub calibration_risk_limit: Option<u32>,
    pub panel_group_limit: Option<u32>,
    pub panel_attention_limit: Option<u32>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetJudgeRuntimeReadinessOpsOutput {
    pub version: String,
    pub generated_at: Option<String>,
    pub status: String,
    pub status_reason: String,
    #[serde(default)]
    pub summary: Value,
    #[serde(default)]
    pub release_gate: Value,
    #[serde(default)]
    pub fairness_calibration: Value,
    #[serde(default)]
    pub panel_runtime: Value,
    #[serde(default)]
    pub trust_and_challenge: Value,
    #[serde(default)]
    pub real_env: Value,
    #[serde(default)]
    pub recommended_actions: Vec<Value>,
    #[serde(default)]
    pub evidence_refs: Vec<Value>,
    #[serde(default)]
    pub visibility_contract: Value,
    #[serde(default)]
    pub cache_profile: Value,
}

#[derive(Debug, Clone, Default, IntoParams, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListJudgeChallengeOpsQueueQuery {
    pub status: Option<String>,
    pub dispatch_type: Option<String>,
    pub challenge_state: Option<String>,
    pub review_state: Option<String>,
    pub priority_level: Option<String>,
    pub sla_bucket: Option<String>,
    pub has_open_alert: Option<bool>,
    pub sort_by: Option<String>,
    pub sort_order: Option<String>,
    pub scan_limit: Option<u32>,
    pub offset: Option<u32>,
    pub limit: Option<u32>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListJudgeChallengeOpsQueueOutput {
    pub status: String,
    pub status_reason: String,
    pub count: u32,
    pub returned: u32,
    pub scanned: u32,
    pub skipped: u32,
    pub error_count: u32,
    #[serde(default)]
    pub summary: Value,
    #[serde(default)]
    pub items: Vec<Value>,
    #[serde(default)]
    pub errors: Vec<Value>,
    #[serde(default)]
    pub filters: Value,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DrawVoteDetail {
    pub vote_id: u64,
    pub final_report_id: u64,
    pub status: String,
    pub resolution: String,
    pub decision_source: String,
    pub threshold_percent: i32,
    pub eligible_voters: i32,
    pub required_voters: i32,
    pub participated_voters: i32,
    pub agree_votes: i32,
    pub disagree_votes: i32,
    pub voting_ends_at: DateTime<Utc>,
    pub decided_at: Option<DateTime<Utc>>,
    pub my_vote: Option<bool>,
    pub rematch_session_id: Option<u64>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetDrawVoteOutput {
    pub session_id: u64,
    pub status: String,
    pub vote: Option<DrawVoteDetail>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SubmitDrawVoteInput {
    pub agree_draw: bool,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SubmitDrawVoteOutput {
    pub session_id: u64,
    pub status: String,
    pub vote: DrawVoteDetail,
    pub newly_submitted: bool,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
pub struct JudgeStageSummaryInput {
    pub stage_no: i32,
    pub from_message_id: Option<u64>,
    pub to_message_id: Option<u64>,
    pub pro_score: i32,
    pub con_score: i32,
    pub summary: Value,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgeStageSummaryDetail {
    pub stage_no: i32,
    pub from_message_id: Option<u64>,
    pub to_message_id: Option<u64>,
    pub pro_score: i32,
    pub con_score: i32,
    pub summary: Value,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgeStageSummariesMeta {
    pub total_count: u32,
    pub returned_count: u32,
    pub stage_offset: u32,
    pub truncated: bool,
    pub has_more: bool,
    pub next_offset: Option<u32>,
    pub max_stage_count: Option<u32>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgePhaseDispatchMessage {
    pub message_id: u64,
    pub side: String,
    pub content: String,
    pub created_at: DateTime<Utc>,
    pub speaker_tag: Option<String>,
}

#[allow(dead_code)]
#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgePhaseDispatchRequest {
    pub case_id: u64,
    pub scope_id: u64,
    pub session_id: u64,
    pub phase_no: i32,
    pub message_start_id: u64,
    pub message_end_id: u64,
    pub message_count: i32,
    pub messages: Vec<JudgePhaseDispatchMessage>,
    pub rubric_version: String,
    pub judge_policy_version: String,
    pub topic_domain: String,
    pub retrieval_profile: String,
    pub trace_id: String,
    pub idempotency_key: String,
}

#[allow(dead_code)]
#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgeFinalDispatchRequest {
    pub case_id: u64,
    pub scope_id: u64,
    pub session_id: u64,
    pub phase_start_no: i32,
    pub phase_end_no: i32,
    pub rubric_version: String,
    pub judge_policy_version: String,
    pub topic_domain: String,
    pub trace_id: String,
    pub idempotency_key: String,
}

#[allow(dead_code)]
#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgeGroundedSummaryPayload {
    pub text: String,
    pub message_ids: Vec<u64>,
}

#[allow(dead_code)]
#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgeRetrievalBundleItemPayload {
    pub chunk_id: String,
    pub title: String,
    pub source_url: String,
    pub score: Option<f64>,
    pub snippet: Option<String>,
    #[serde(default)]
    pub conflict: bool,
}

#[allow(dead_code)]
#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgeRetrievalBundlePayload {
    pub queries: Vec<String>,
    pub items: Vec<JudgeRetrievalBundleItemPayload>,
}

#[allow(dead_code)]
#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgePhaseAgent1ScorePayload {
    pub pro: f64,
    pub con: f64,
    #[serde(default)]
    pub dimensions: Value,
    pub rationale: String,
}

#[allow(dead_code)]
#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgePhaseAgent2ScorePayload {
    pub pro: f64,
    pub con: f64,
    #[serde(default)]
    pub hit_items: Vec<String>,
    #[serde(default)]
    pub miss_items: Vec<String>,
    pub rationale: String,
}

#[allow(dead_code)]
#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgePhaseAgent3WeightedScorePayload {
    pub pro: f64,
    pub con: f64,
    pub w1: f64,
    pub w2: f64,
}

#[allow(dead_code)]
#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SubmitJudgePhaseReportInput {
    pub session_id: u64,
    pub phase_no: i32,
    pub message_start_id: u64,
    pub message_end_id: u64,
    pub message_count: i32,
    pub pro_summary_grounded: JudgeGroundedSummaryPayload,
    pub con_summary_grounded: JudgeGroundedSummaryPayload,
    pub pro_retrieval_bundle: JudgeRetrievalBundlePayload,
    pub con_retrieval_bundle: JudgeRetrievalBundlePayload,
    pub agent1_score: JudgePhaseAgent1ScorePayload,
    pub agent2_score: JudgePhaseAgent2ScorePayload,
    pub agent3_weighted_score: JudgePhaseAgent3WeightedScorePayload,
    #[serde(default)]
    pub prompt_hashes: Value,
    #[serde(default)]
    pub token_usage: Value,
    #[serde(default)]
    pub latency_ms: Value,
    #[serde(default)]
    pub error_codes: Vec<String>,
    #[serde(default)]
    pub degradation_level: i32,
    #[serde(default)]
    pub judge_trace: Value,
}

#[allow(dead_code)]
#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SubmitJudgePhaseReportOutput {
    pub session_id: u64,
    pub phase_no: i32,
    pub status: String,
}

#[allow(dead_code)]
#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SubmitJudgeFinalReportInput {
    pub session_id: u64,
    pub winner: String,
    pub pro_score: f64,
    pub con_score: f64,
    #[serde(default)]
    pub dimension_scores: Value,
    pub debate_summary: String,
    #[serde(default)]
    pub side_analysis: Value,
    pub verdict_reason: String,
    #[serde(default)]
    pub verdict_evidence_refs: Vec<Value>,
    #[serde(default)]
    pub phase_rollup_summary: Vec<Value>,
    #[serde(default)]
    pub retrieval_snapshot_rollup: Vec<Value>,
    pub winner_first: Option<String>,
    pub winner_second: Option<String>,
    pub winner_third: Option<String>,
    #[serde(default)]
    pub rejudge_triggered: bool,
    #[serde(default)]
    pub needs_draw_vote: bool,
    #[serde(default)]
    pub review_required: bool,
    #[serde(default)]
    pub claim_graph: Value,
    #[serde(default)]
    pub claim_graph_summary: Value,
    #[serde(default)]
    pub evidence_ledger: Value,
    #[serde(default)]
    pub verdict_ledger: Value,
    #[serde(default)]
    pub opinion_pack: Value,
    #[serde(default)]
    pub fairness_summary: Value,
    #[serde(default)]
    pub trust_attestation: Value,
    #[serde(default)]
    pub judge_trace: Value,
    #[serde(default)]
    pub audit_alerts: Vec<Value>,
    #[serde(default)]
    pub error_codes: Vec<String>,
    #[serde(default)]
    pub degradation_level: i32,
}

#[allow(dead_code)]
#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SubmitJudgeFinalReportOutput {
    pub session_id: u64,
    pub status: String,
}

#[allow(dead_code)]
#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SubmitJudgeFailedCallbackInput {
    pub dispatch_type: String,
    pub trace_id: String,
    pub error_code: String,
    pub error_message: String,
    #[serde(default)]
    pub audit_alert_ids: Vec<String>,
    #[serde(default)]
    pub degradation_level: Option<i32>,
}

#[allow(dead_code)]
#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SubmitJudgeFailedCallbackOutput {
    pub session_id: u64,
    pub status: String,
}
