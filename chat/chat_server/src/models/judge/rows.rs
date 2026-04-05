use chrono::{DateTime, Utc};
use serde_json::Value;
use sqlx::FromRow;

#[derive(Debug, Clone, FromRow)]
pub(super) struct DebateSessionForJudge {
    pub status: String,
}

#[derive(Debug, Clone, FromRow)]
pub(super) struct AutoJudgeRequesterRow {
    pub requester_id: Option<i64>,
}

#[derive(Debug, Clone, FromRow)]
pub(super) struct JudgeJobRequestIdempotencyRow {
    pub request_hash: String,
    pub status: String,
    pub response_snapshot: Option<Value>,
}

#[derive(Debug, Clone, FromRow)]
pub(super) struct JudgePhaseJobForUpdate {
    pub id: i64,
    pub session_id: i64,
    pub phase_no: i32,
    pub message_start_id: i64,
    pub message_end_id: i64,
    pub message_count: i32,
    pub status: String,
}

#[derive(Debug, Clone, FromRow)]
pub(super) struct JudgeFinalJobForUpdate {
    pub id: i64,
    pub session_id: i64,
    pub status: String,
}

#[derive(Debug, Clone, FromRow)]
pub(super) struct JudgeFinalReportRow {
    pub id: i64,
    pub final_job_id: i64,
    pub winner: String,
    pub pro_score: f64,
    pub con_score: f64,
    pub dimension_scores: Value,
    pub final_rationale: String,
    pub verdict_evidence_refs: Value,
    pub phase_rollup_summary: Value,
    pub retrieval_snapshot_rollup: Value,
    pub winner_first: Option<String>,
    pub winner_second: Option<String>,
    pub rejudge_triggered: bool,
    pub needs_draw_vote: bool,
    pub judge_trace: Value,
    pub audit_alerts: Value,
    pub error_codes: Value,
    pub degradation_level: i32,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
pub(super) struct JudgeFinalJobSnapshotRow {
    pub id: i64,
    pub status: String,
    pub phase_start_no: i32,
    pub phase_end_no: i32,
    pub dispatch_attempts: i32,
    pub last_dispatch_at: Option<DateTime<Utc>>,
    pub error_message: Option<String>,
}

#[derive(Debug, Clone, FromRow)]
pub(super) struct JudgePhaseJobSnapshotRow {
    pub id: i64,
    pub phase_no: i32,
    pub status: String,
    pub message_count: i32,
    pub dispatch_attempts: i32,
    pub last_dispatch_at: Option<DateTime<Utc>>,
    pub error_message: Option<String>,
}

#[derive(Debug, Clone, FromRow)]
pub(super) struct JudgeTraceReplayOpsRow {
    pub scope: String,
    pub session_id: i64,
    pub trace_id: String,
    pub idempotency_key: String,
    pub status: String,
    pub created_at: DateTime<Utc>,
    pub dispatch_attempts: i32,
    pub last_dispatch_at: Option<DateTime<Utc>>,
    pub error_message: Option<String>,
    pub phase_job_id: Option<i64>,
    pub final_job_id: Option<i64>,
    pub phase_no: Option<i32>,
    pub phase_start_no: Option<i32>,
    pub phase_end_no: Option<i32>,
    pub phase_report_id: Option<i64>,
    pub final_report_id: Option<i64>,
    pub replay_action_count: i64,
    pub latest_replay_action_id: Option<i64>,
    pub latest_replay_at: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone, FromRow)]
pub(super) struct JudgePhaseReplayJobRow {
    pub id: i64,
    pub session_id: i64,
    pub phase_no: i32,
    pub message_start_id: i64,
    pub message_end_id: i64,
    pub message_count: i32,
    pub status: String,
    pub trace_id: String,
    pub idempotency_key: String,
    pub rubric_version: String,
    pub judge_policy_version: String,
    pub topic_domain: String,
    pub retrieval_profile: String,
    pub dispatch_attempts: i32,
    pub last_dispatch_at: Option<DateTime<Utc>>,
    pub error_message: Option<String>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
pub(super) struct JudgeFinalReplayJobRow {
    pub id: i64,
    pub session_id: i64,
    pub phase_start_no: i32,
    pub phase_end_no: i32,
    pub status: String,
    pub trace_id: String,
    pub idempotency_key: String,
    pub rubric_version: String,
    pub judge_policy_version: String,
    pub topic_domain: String,
    pub dispatch_attempts: i32,
    pub last_dispatch_at: Option<DateTime<Utc>>,
    pub error_message: Option<String>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
pub(super) struct JudgeReplayActionRow {
    pub id: i64,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
pub(super) struct JudgeReplayActionOpsRow {
    pub audit_id: i64,
    pub scope: String,
    pub job_id: i64,
    pub session_id: i64,
    pub requested_by: i64,
    pub reason: Option<String>,
    pub previous_status: String,
    pub new_status: String,
    pub previous_trace_id: String,
    pub new_trace_id: String,
    pub previous_idempotency_key: String,
    pub new_idempotency_key: String,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
pub(super) struct JudgeReviewOpsRow {
    pub report_id: i64,
    pub session_id: i64,
    pub job_id: i64,
    pub winner: String,
    pub winner_first: Option<String>,
    pub winner_second: Option<String>,
    pub pro_score: i32,
    pub con_score: i32,
    pub style_mode: String,
    pub rubric_version: String,
    pub needs_draw_vote: bool,
    pub rejudge_triggered: bool,
    pub verdict_evidence_count: i32,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
pub(super) struct DrawVoteRow {
    pub id: i64,
    pub session_id: i64,
    pub final_report_id: i64,
    pub threshold_percent: i32,
    pub eligible_voters: i32,
    pub required_voters: i32,
    pub voting_ends_at: DateTime<Utc>,
    pub status: String,
    pub resolution: String,
    pub decided_at: Option<DateTime<Utc>>,
    pub rematch_session_id: Option<i64>,
}

#[derive(Debug, Clone, FromRow)]
pub(super) struct DrawVoteStatsRow {
    pub participated_voters: i32,
    pub agree_votes: i32,
    pub disagree_votes: i32,
}

#[derive(Debug, Clone, FromRow)]
pub(super) struct DebateSessionForRematch {
    pub id: i64,
    pub topic_id: i64,
    pub scheduled_start_at: DateTime<Utc>,
    pub actual_start_at: Option<DateTime<Utc>>,
    pub end_at: DateTime<Utc>,
    pub max_participants_per_side: i32,
    pub rematch_round: i32,
}
