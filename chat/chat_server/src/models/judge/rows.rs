use chrono::{DateTime, Utc};
use serde_json::Value;
use sqlx::FromRow;

#[derive(Debug, Clone, FromRow)]
pub(super) struct DebateSessionForJudge {
    pub status: String,
}

#[derive(Debug, Clone, FromRow)]
pub(super) struct JudgeJobRow {
    pub id: i64,
    pub status: String,
    pub style_mode: String,
    pub rejudge_triggered: bool,
    pub requested_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
pub(super) struct AutoJudgeRequesterRow {
    pub requester_id: Option<i64>,
}

#[derive(Debug, Clone, FromRow)]
pub(super) struct JudgeJobForUpdate {
    pub id: i64,
    pub session_id: i64,
    pub status: String,
    pub rejudge_triggered: bool,
    pub error_message: Option<String>,
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
pub(super) struct JudgeReportRow {
    pub id: i64,
    pub job_id: i64,
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
    pub created_at: DateTime<Utc>,
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
pub(super) struct JudgeStageSummaryRow {
    pub stage_no: i32,
    pub from_message_id: Option<i64>,
    pub to_message_id: Option<i64>,
    pub pro_score: i32,
    pub con_score: i32,
    pub summary: Value,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
pub(super) struct SessionMessageEvidenceRow {
    pub id: i64,
    pub side: String,
    pub content: String,
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
    pub report_id: i64,
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
