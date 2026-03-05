use crate::{AiJudgeJobCreatedEvent, AppError, AppState, JudgeDispatchTrigger};
use chat_core::User;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sqlx::{FromRow, Postgres, Transaction};
use tracing::warn;
use utoipa::{IntoParams, ToSchema};

mod draw_vote;
mod helpers;
mod report_submit;
mod request_report;

#[cfg(test)]
use helpers::extract_rag_meta;
use helpers::{
    calc_required_voters, can_request_judge, extract_verdict_evidence_refs, majority_resolution,
    map_draw_vote_detail, map_report_detail, map_stage_summary, normalize_stage_summary_limit,
    normalize_stage_summary_offset, normalize_style_mode, normalize_winner, resolve_rubric_version,
    validate_non_empty_text, validate_score,
};

const STYLE_RATIONAL: &str = "rational";
const STYLE_ENTERTAINING: &str = "entertaining";
const STYLE_MIXED: &str = "mixed";
const STYLE_SOURCE_SYSTEM_CONFIG: &str = "system_config";
const STYLE_SOURCE_SYSTEM_CONFIG_FALLBACK_DEFAULT: &str = "system_config_fallback_default";
const STYLE_SOURCE_EXISTING_RUNNING_JOB: &str = "existing_running_job";
const DRAW_VOTE_THRESHOLD_PERCENT: i32 = 70;
const DRAW_VOTE_WINDOW_SECS: i64 = 300;
const REMATCH_DELAY_SECS: i64 = 600;
const REMATCH_MIN_DURATION_SECS: i64 = 900;
const REMATCH_MAX_DURATION_SECS: i64 = 14_400;
const MAX_STAGE_SUMMARY_COUNT: u32 = 200;
const MAX_STAGE_SUMMARY_OFFSET: u32 = 10_000;
const DEFAULT_OPS_JUDGE_REVIEW_LIMIT: u32 = 50;
const MAX_OPS_JUDGE_REVIEW_LIMIT: u32 = 200;

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RequestJudgeJobInput {
    /// Deprecated for decision making. Server keeps this for compatibility but now enforces
    /// `ai_judge.style_mode` from system config.
    pub style_mode: Option<String>,
    #[serde(default)]
    pub allow_rejudge: bool,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RequestJudgeJobOutput {
    pub session_id: u64,
    pub job_id: u64,
    pub status: String,
    pub style_mode: String,
    pub style_mode_source: String,
    pub rejudge_triggered: bool,
    pub requested_at: DateTime<Utc>,
    pub newly_created: bool,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgeJobSnapshot {
    pub job_id: u64,
    pub status: String,
    pub style_mode: String,
    pub rejudge_triggered: bool,
    pub requested_at: DateTime<Utc>,
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
    pub latest_job: Option<JudgeJobSnapshot>,
    pub report: Option<JudgeReportDetail>,
}

#[derive(Debug, Clone, IntoParams, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetJudgeReportQuery {
    pub max_stage_count: Option<u32>,
    pub stage_offset: Option<u32>,
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

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgeReviewOpsItem {
    pub report_id: u64,
    pub session_id: u64,
    pub job_id: u64,
    pub winner: String,
    pub winner_first: Option<String>,
    pub winner_second: Option<String>,
    pub pro_score: i32,
    pub con_score: i32,
    pub score_gap: i32,
    pub style_mode: String,
    pub rubric_version: String,
    pub needs_draw_vote: bool,
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

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DrawVoteDetail {
    pub vote_id: u64,
    pub report_id: u64,
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
#[serde(rename_all = "camelCase")]
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
pub struct SubmitJudgeReportInput {
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
    pub style_mode: Option<String>,
    #[serde(default)]
    pub needs_draw_vote: bool,
    #[serde(default)]
    pub rejudge_triggered: bool,
    #[serde(default)]
    pub payload: Value,
    pub winner_first: Option<String>,
    pub winner_second: Option<String>,
    #[serde(default)]
    pub stage_summaries: Vec<JudgeStageSummaryInput>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SubmitJudgeReportOutput {
    pub job_id: u64,
    pub session_id: u64,
    pub report_id: u64,
    pub status: String,
    pub newly_created: bool,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MarkJudgeJobFailedInput {
    pub error_message: String,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MarkJudgeJobFailedOutput {
    pub job_id: u64,
    pub session_id: u64,
    pub status: String,
    pub error_message: String,
    pub newly_marked: bool,
}

#[derive(Debug, Clone, FromRow)]
struct DebateSessionForJudge {
    ws_id: i64,
    status: String,
}

#[derive(Debug, Clone, FromRow)]
struct JudgeJobRow {
    id: i64,
    status: String,
    style_mode: String,
    rejudge_triggered: bool,
    requested_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
struct AutoJudgeRequesterRow {
    ws_id: i64,
    requester_id: Option<i64>,
}

#[derive(Debug, Clone, FromRow)]
struct JudgeJobForUpdate {
    id: i64,
    ws_id: i64,
    session_id: i64,
    status: String,
    rejudge_triggered: bool,
    error_message: Option<String>,
}

#[derive(Debug, Clone, FromRow)]
struct JudgeReportRow {
    id: i64,
    job_id: i64,
    winner: String,
    pro_score: i32,
    con_score: i32,
    logic_pro: i32,
    logic_con: i32,
    evidence_pro: i32,
    evidence_con: i32,
    rebuttal_pro: i32,
    rebuttal_con: i32,
    clarity_pro: i32,
    clarity_con: i32,
    pro_summary: String,
    con_summary: String,
    rationale: String,
    style_mode: String,
    rubric_version: String,
    needs_draw_vote: bool,
    rejudge_triggered: bool,
    payload: Value,
    created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
struct JudgeStageSummaryRow {
    stage_no: i32,
    from_message_id: Option<i64>,
    to_message_id: Option<i64>,
    pro_score: i32,
    con_score: i32,
    summary: Value,
    created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
struct SessionMessageEvidenceRow {
    id: i64,
    side: String,
    content: String,
    created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
struct JudgeReviewOpsRow {
    report_id: i64,
    session_id: i64,
    job_id: i64,
    winner: String,
    winner_first: Option<String>,
    winner_second: Option<String>,
    pro_score: i32,
    con_score: i32,
    style_mode: String,
    rubric_version: String,
    needs_draw_vote: bool,
    rejudge_triggered: bool,
    verdict_evidence_count: i32,
    created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
struct DrawVoteRow {
    id: i64,
    ws_id: i64,
    session_id: i64,
    report_id: i64,
    threshold_percent: i32,
    eligible_voters: i32,
    required_voters: i32,
    voting_ends_at: DateTime<Utc>,
    status: String,
    resolution: String,
    decided_at: Option<DateTime<Utc>>,
    rematch_session_id: Option<i64>,
}

#[derive(Debug, Clone, FromRow)]
struct DrawVoteStatsRow {
    participated_voters: i32,
    agree_votes: i32,
    disagree_votes: i32,
}

#[derive(Debug, Clone, FromRow)]
struct DebateSessionForRematch {
    id: i64,
    ws_id: i64,
    topic_id: i64,
    scheduled_start_at: DateTime<Utc>,
    actual_start_at: Option<DateTime<Utc>>,
    end_at: DateTime<Utc>,
    max_participants_per_side: i32,
    rematch_round: i32,
}

#[cfg(test)]
mod tests;
