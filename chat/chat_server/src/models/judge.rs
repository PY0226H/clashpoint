use crate::{AiJudgeJobCreatedEvent, AppError, AppState};
use chat_core::User;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sqlx::{FromRow, Postgres, Transaction};
use std::collections::HashSet;
use tracing::warn;
use utoipa::ToSchema;

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
    pub needs_draw_vote: bool,
    pub rejudge_triggered: bool,
    pub payload: Value,
    pub rag: Option<JudgeRagMeta>,
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

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DrawVoteDetail {
    pub vote_id: u64,
    pub report_id: u64,
    pub status: String,
    pub resolution: String,
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
    needs_draw_vote: bool,
    rejudge_triggered: bool,
    payload: Value,
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

fn normalize_style_mode(style_mode: Option<String>) -> Result<String, AppError> {
    let raw = style_mode.unwrap_or_else(|| STYLE_RATIONAL.to_string());
    let mode = raw.trim().to_ascii_lowercase();
    if mode.is_empty() {
        return Err(AppError::DebateError(
            "style_mode cannot be empty".to_string(),
        ));
    }
    if matches!(
        mode.as_str(),
        STYLE_RATIONAL | STYLE_ENTERTAINING | STYLE_MIXED
    ) {
        Ok(mode)
    } else {
        Err(AppError::DebateError(format!(
            "invalid style_mode: {raw}, expect `rational` | `entertaining` | `mixed`"
        )))
    }
}

fn can_request_judge(status: &str) -> bool {
    matches!(status, "judging" | "closed")
}

fn normalize_winner(winner: &str, field: &str) -> Result<String, AppError> {
    let winner = winner.trim().to_ascii_lowercase();
    if matches!(winner.as_str(), "pro" | "con" | "draw") {
        Ok(winner)
    } else {
        Err(AppError::DebateError(format!(
            "invalid {field}: {winner}, expect `pro` | `con` | `draw`"
        )))
    }
}

fn validate_score(score: i32, field: &str) -> Result<(), AppError> {
    if !(0..=100).contains(&score) {
        return Err(AppError::DebateError(format!(
            "invalid {field}: {score}, expect 0..=100"
        )));
    }
    Ok(())
}

fn validate_non_empty_text(input: &str, field: &str, max_len: usize) -> Result<String, AppError> {
    let ret = input.trim();
    if ret.is_empty() {
        return Err(AppError::DebateError(format!("{field} cannot be empty")));
    }
    if ret.len() > max_len {
        return Err(AppError::DebateError(format!(
            "{field} too long, max {max_len} chars"
        )));
    }
    Ok(ret.to_string())
}

fn map_report_detail(v: JudgeReportRow) -> JudgeReportDetail {
    let rag = extract_rag_meta(&v.payload);
    JudgeReportDetail {
        report_id: v.id as u64,
        job_id: v.job_id as u64,
        winner: v.winner,
        pro_score: v.pro_score,
        con_score: v.con_score,
        logic_pro: v.logic_pro,
        logic_con: v.logic_con,
        evidence_pro: v.evidence_pro,
        evidence_con: v.evidence_con,
        rebuttal_pro: v.rebuttal_pro,
        rebuttal_con: v.rebuttal_con,
        clarity_pro: v.clarity_pro,
        clarity_con: v.clarity_con,
        pro_summary: v.pro_summary,
        con_summary: v.con_summary,
        rationale: v.rationale,
        style_mode: v.style_mode,
        needs_draw_vote: v.needs_draw_vote,
        rejudge_triggered: v.rejudge_triggered,
        payload: v.payload,
        rag,
        created_at: v.created_at,
    }
}

fn extract_rag_meta(payload: &Value) -> Option<JudgeRagMeta> {
    let enabled = payload.get("ragEnabled").and_then(Value::as_bool);
    let used_by_model = payload.get("ragUsedByModel").and_then(Value::as_bool);
    let snippet_count = payload
        .get("ragSnippetCount")
        .and_then(Value::as_u64)
        .and_then(|v| u32::try_from(v).ok());
    let source_whitelist: Vec<String> = payload
        .get("ragSourceWhitelist")
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(Value::as_str)
                .map(str::trim)
                .filter(|v| !v.is_empty())
                .map(ToString::to_string)
                .collect()
        })
        .unwrap_or_default();
    let sources: Vec<JudgeRagSourceItem> = payload
        .get("ragSources")
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(|item| {
                    let chunk_id = item
                        .get("chunkId")
                        .and_then(Value::as_str)
                        .or_else(|| item.get("chunk_id").and_then(Value::as_str))
                        .unwrap_or_default()
                        .trim()
                        .to_string();
                    let title = item
                        .get("title")
                        .and_then(Value::as_str)
                        .unwrap_or_default()
                        .trim()
                        .to_string();
                    let source_url = item
                        .get("sourceUrl")
                        .and_then(Value::as_str)
                        .or_else(|| item.get("source_url").and_then(Value::as_str))
                        .unwrap_or_default()
                        .trim()
                        .to_string();
                    if chunk_id.is_empty() && title.is_empty() && source_url.is_empty() {
                        return None;
                    }
                    Some(JudgeRagSourceItem {
                        chunk_id,
                        title,
                        source_url,
                        score: item.get("score").and_then(Value::as_f64),
                    })
                })
                .collect()
        })
        .unwrap_or_default();
    if enabled.is_none()
        && used_by_model.is_none()
        && snippet_count.is_none()
        && source_whitelist.is_empty()
        && sources.is_empty()
    {
        return None;
    }
    Some(JudgeRagMeta {
        enabled,
        used_by_model,
        snippet_count,
        source_whitelist,
        sources,
    })
}

fn calc_required_voters(eligible_voters: i32, threshold_percent: i32) -> i32 {
    if eligible_voters <= 0 {
        return 1;
    }
    let threshold = threshold_percent.clamp(1, 100) as i64;
    let eligible = eligible_voters as i64;
    ((eligible * threshold + 99) / 100) as i32
}

fn majority_resolution(agree_votes: i32, disagree_votes: i32) -> &'static str {
    if agree_votes > disagree_votes {
        "accept_draw"
    } else {
        "open_rematch"
    }
}

fn map_draw_vote_detail(
    vote: DrawVoteRow,
    stats: DrawVoteStatsRow,
    my_vote: Option<bool>,
) -> DrawVoteDetail {
    DrawVoteDetail {
        vote_id: vote.id as u64,
        report_id: vote.report_id as u64,
        status: vote.status,
        resolution: vote.resolution,
        threshold_percent: vote.threshold_percent,
        eligible_voters: vote.eligible_voters,
        required_voters: vote.required_voters,
        participated_voters: stats.participated_voters,
        agree_votes: stats.agree_votes,
        disagree_votes: stats.disagree_votes,
        voting_ends_at: vote.voting_ends_at,
        decided_at: vote.decided_at,
        my_vote,
        rematch_session_id: vote.rematch_session_id.map(|v| v as u64),
    }
}

impl AppState {
    pub async fn request_judge_job(
        &self,
        session_id: u64,
        user: &User,
        input: RequestJudgeJobInput,
    ) -> Result<RequestJudgeJobOutput, AppError> {
        let configured_style_mode = self.config.ai_judge.style_mode.clone();
        let (style_mode, style_mode_source) =
            match normalize_style_mode(Some(configured_style_mode.clone())) {
                Ok(mode) => (mode, STYLE_SOURCE_SYSTEM_CONFIG),
                Err(_) => {
                    warn!(
                        configured_style_mode,
                        "invalid ai_judge.style_mode config, fallback to rational"
                    );
                    (
                        STYLE_RATIONAL.to_string(),
                        STYLE_SOURCE_SYSTEM_CONFIG_FALLBACK_DEFAULT,
                    )
                }
            };
        let mut tx = self.pool.begin().await?;

        let Some(session): Option<DebateSessionForJudge> = sqlx::query_as(
            r#"
            SELECT ws_id, status
            FROM debate_sessions
            WHERE id = $1
            FOR UPDATE
            "#,
        )
        .bind(session_id as i64)
        .fetch_optional(&mut *tx)
        .await?
        else {
            return Err(AppError::NotFound(format!(
                "debate session id {session_id}"
            )));
        };

        if session.ws_id != user.ws_id {
            return Err(AppError::NotFound(format!(
                "debate session id {session_id}"
            )));
        }

        if !can_request_judge(&session.status) {
            return Err(AppError::DebateConflict(format!(
                "session {} is not in judging/closed status",
                session_id
            )));
        }

        let joined: Option<(i32,)> = sqlx::query_as(
            r#"
            SELECT 1
            FROM session_participants
            WHERE session_id = $1 AND user_id = $2
            "#,
        )
        .bind(session_id as i64)
        .bind(user.id)
        .fetch_optional(&mut *tx)
        .await?;
        if joined.is_none() {
            return Err(AppError::DebateConflict(format!(
                "user {} has not joined session {}",
                user.id, session_id
            )));
        }

        let existing_running: Option<JudgeJobRow> = sqlx::query_as(
            r#"
            SELECT id, status, style_mode, rejudge_triggered, requested_at
            FROM judge_jobs
            WHERE session_id = $1 AND status = 'running'
            ORDER BY requested_at DESC
            LIMIT 1
            "#,
        )
        .bind(session_id as i64)
        .fetch_optional(&mut *tx)
        .await?;
        if let Some(job) = existing_running {
            tx.commit().await?;
            return Ok(RequestJudgeJobOutput {
                session_id,
                job_id: job.id as u64,
                status: job.status,
                style_mode: job.style_mode,
                style_mode_source: STYLE_SOURCE_EXISTING_RUNNING_JOB.to_string(),
                rejudge_triggered: job.rejudge_triggered,
                requested_at: job.requested_at,
                newly_created: false,
            });
        }

        let report_exists = sqlx::query_scalar::<_, i64>(
            r#"
            SELECT id
            FROM judge_reports
            WHERE session_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            "#,
        )
        .bind(session_id as i64)
        .fetch_optional(&mut *tx)
        .await?
        .is_some();
        if report_exists && !input.allow_rejudge {
            return Err(AppError::DebateConflict(format!(
                "session {} already has judge report, set allowRejudge=true to create rejudge job",
                session_id
            )));
        }

        let rejudge_triggered = report_exists && input.allow_rejudge;
        let job: JudgeJobRow = sqlx::query_as(
            r#"
            INSERT INTO judge_jobs(
                ws_id, session_id, requested_by, status, style_mode, rejudge_triggered,
                requested_at, started_at, created_at, updated_at
            )
            VALUES ($1, $2, $3, 'running', $4, $5, NOW(), NULL, NOW(), NOW())
            RETURNING id, status, style_mode, rejudge_triggered, requested_at
            "#,
        )
        .bind(user.ws_id)
        .bind(session_id as i64)
        .bind(user.id)
        .bind(&style_mode)
        .bind(rejudge_triggered)
        .fetch_one(&mut *tx)
        .await?;

        tx.commit().await?;

        if let Err(err) = self
            .event_bus
            .publish_ai_judge_job_created(AiJudgeJobCreatedEvent {
                ws_id: user.ws_id as u64,
                session_id,
                job_id: job.id as u64,
                requested_by: user.id as u64,
                style_mode: style_mode.clone(),
                rejudge_triggered,
                requested_at: job.requested_at,
            })
            .await
        {
            warn!(
                session_id,
                user_id = user.id,
                "publish kafka ai judge job created failed: {}",
                err
            );
        }

        Ok(RequestJudgeJobOutput {
            session_id,
            job_id: job.id as u64,
            status: job.status,
            style_mode: job.style_mode,
            style_mode_source: style_mode_source.to_string(),
            rejudge_triggered: job.rejudge_triggered,
            requested_at: job.requested_at,
            newly_created: true,
        })
    }

    pub async fn get_latest_judge_report(
        &self,
        session_id: u64,
        user: &User,
    ) -> Result<GetJudgeReportOutput, AppError> {
        let session_ws_id: Option<(i64,)> = sqlx::query_as(
            r#"
            SELECT ws_id
            FROM debate_sessions
            WHERE id = $1
            "#,
        )
        .bind(session_id as i64)
        .fetch_optional(&self.pool)
        .await?;
        let Some((session_ws_id,)) = session_ws_id else {
            return Err(AppError::NotFound(format!(
                "debate session id {session_id}"
            )));
        };
        if session_ws_id != user.ws_id {
            return Err(AppError::NotFound(format!(
                "debate session id {session_id}"
            )));
        }

        let latest_job: Option<JudgeJobRow> = sqlx::query_as(
            r#"
            SELECT id, status, style_mode, rejudge_triggered, requested_at
            FROM judge_jobs
            WHERE session_id = $1
            ORDER BY requested_at DESC
            LIMIT 1
            "#,
        )
        .bind(session_id as i64)
        .fetch_optional(&self.pool)
        .await?;

        let report: Option<JudgeReportRow> = sqlx::query_as(
            r#"
            SELECT
                id, job_id, winner, pro_score, con_score,
                logic_pro, logic_con, evidence_pro, evidence_con, rebuttal_pro, rebuttal_con,
                clarity_pro, clarity_con, pro_summary, con_summary, rationale, style_mode,
                needs_draw_vote, rejudge_triggered, payload, created_at
            FROM judge_reports
            WHERE session_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            "#,
        )
        .bind(session_id as i64)
        .fetch_optional(&self.pool)
        .await?;

        let status = if report.is_some() {
            "ready".to_string()
        } else if let Some(job) = latest_job.as_ref() {
            if job.status == "failed" {
                "failed".to_string()
            } else {
                "pending".to_string()
            }
        } else {
            "absent".to_string()
        };

        Ok(GetJudgeReportOutput {
            session_id,
            status,
            latest_job: latest_job.map(|job| JudgeJobSnapshot {
                job_id: job.id as u64,
                status: job.status,
                style_mode: job.style_mode,
                rejudge_triggered: job.rejudge_triggered,
                requested_at: job.requested_at,
            }),
            report: report.map(map_report_detail),
        })
    }

    async fn load_draw_vote_stats(
        tx: &mut Transaction<'_, Postgres>,
        vote_id: i64,
    ) -> Result<DrawVoteStatsRow, AppError> {
        let stats = sqlx::query_as(
            r#"
            SELECT
                COUNT(*)::integer AS participated_voters,
                COUNT(*) FILTER (WHERE agree_draw)::integer AS agree_votes,
                COUNT(*) FILTER (WHERE NOT agree_draw)::integer AS disagree_votes
            FROM judge_draw_vote_ballots
            WHERE vote_id = $1
            "#,
        )
        .bind(vote_id)
        .fetch_one(&mut **tx)
        .await?;
        Ok(stats)
    }

    async fn maybe_finalize_draw_vote(
        tx: &mut Transaction<'_, Postgres>,
        vote: DrawVoteRow,
        stats: &DrawVoteStatsRow,
    ) -> Result<DrawVoteRow, AppError> {
        if vote.status != "open" {
            return Ok(vote);
        }
        let now = Utc::now();
        let decision = if stats.participated_voters >= vote.required_voters {
            Some((
                "decided",
                majority_resolution(stats.agree_votes, stats.disagree_votes),
            ))
        } else if vote.voting_ends_at <= now {
            Some(("expired", "open_rematch"))
        } else {
            None
        };
        let Some((status, resolution)) = decision else {
            return Ok(vote);
        };
        let vote = if resolution == "open_rematch" && vote.rematch_session_id.is_none() {
            Self::ensure_rematch_session_for_vote(tx, vote).await?
        } else {
            vote
        };
        let updated: DrawVoteRow = sqlx::query_as(
            r#"
            UPDATE judge_draw_votes
            SET status = $2,
                resolution = $3,
                decided_at = $4,
                updated_at = NOW()
            WHERE id = $1
            RETURNING
                id, ws_id, session_id, report_id, threshold_percent, eligible_voters, required_voters,
                voting_ends_at, status, resolution, decided_at, rematch_session_id
            "#,
        )
        .bind(vote.id)
        .bind(status)
        .bind(resolution)
        .bind(Some(now))
        .fetch_one(&mut **tx)
        .await?;
        Ok(updated)
    }

    fn rematch_schedule_from_source(
        source: &DebateSessionForRematch,
    ) -> (DateTime<Utc>, DateTime<Utc>, i32) {
        let now = Utc::now();
        let base_start = now + chrono::Duration::seconds(REMATCH_DELAY_SECS);
        let base_from = source.actual_start_at.unwrap_or(source.scheduled_start_at);
        let duration_secs = (source.end_at - base_from)
            .num_seconds()
            .clamp(REMATCH_MIN_DURATION_SECS, REMATCH_MAX_DURATION_SECS);
        let end_at = base_start + chrono::Duration::seconds(duration_secs);
        let next_round = source.rematch_round + 1;
        (base_start, end_at, next_round)
    }

    async fn ensure_rematch_session_for_vote(
        tx: &mut Transaction<'_, Postgres>,
        vote: DrawVoteRow,
    ) -> Result<DrawVoteRow, AppError> {
        if vote.rematch_session_id.is_some() {
            return Ok(vote);
        }

        let existing: Option<(i64,)> = sqlx::query_as(
            r#"
            SELECT id
            FROM debate_sessions
            WHERE parent_session_id = $1
            ORDER BY rematch_round DESC, created_at DESC
            LIMIT 1
            "#,
        )
        .bind(vote.session_id)
        .fetch_optional(&mut **tx)
        .await?;

        let rematch_session_id = if let Some((session_id,)) = existing {
            session_id
        } else {
            let source: DebateSessionForRematch = sqlx::query_as(
                r#"
                SELECT
                    id, ws_id, topic_id, scheduled_start_at, actual_start_at, end_at,
                    max_participants_per_side, rematch_round
                FROM debate_sessions
                WHERE id = $1
                FOR UPDATE
                "#,
            )
            .bind(vote.session_id)
            .fetch_one(&mut **tx)
            .await?;
            let (scheduled_start_at, end_at, next_round) =
                Self::rematch_schedule_from_source(&source);
            let rematch_id: (i64,) = sqlx::query_as(
                r#"
                INSERT INTO debate_sessions(
                    ws_id, topic_id, status, scheduled_start_at, actual_start_at, end_at,
                    max_participants_per_side, pro_count, con_count, hot_score,
                    parent_session_id, rematch_round, created_at, updated_at
                )
                VALUES (
                    $1, $2, 'scheduled', $3, NULL, $4,
                    $5, 0, 0, 0,
                    $6, $7, NOW(), NOW()
                )
                RETURNING id
                "#,
            )
            .bind(source.ws_id)
            .bind(source.topic_id)
            .bind(scheduled_start_at)
            .bind(end_at)
            .bind(source.max_participants_per_side)
            .bind(source.id)
            .bind(next_round)
            .fetch_one(&mut **tx)
            .await?;
            rematch_id.0
        };

        let updated: DrawVoteRow = sqlx::query_as(
            r#"
            UPDATE judge_draw_votes
            SET rematch_session_id = $2,
                updated_at = NOW()
            WHERE id = $1
            RETURNING
                id, ws_id, session_id, report_id, threshold_percent, eligible_voters, required_voters,
                voting_ends_at, status, resolution, decided_at, rematch_session_id
            "#,
        )
        .bind(vote.id)
        .bind(rematch_session_id)
        .fetch_one(&mut **tx)
        .await?;
        Ok(updated)
    }

    async fn create_draw_vote_for_report(
        tx: &mut Transaction<'_, Postgres>,
        ws_id: i64,
        session_id: i64,
        report_id: i64,
    ) -> Result<(), AppError> {
        let eligible_voters: i32 = sqlx::query_scalar(
            r#"
            SELECT COUNT(*)::integer
            FROM session_participants
            WHERE session_id = $1
            "#,
        )
        .bind(session_id)
        .fetch_one(&mut **tx)
        .await?;
        let required_voters = calc_required_voters(eligible_voters, DRAW_VOTE_THRESHOLD_PERCENT);
        sqlx::query(
            r#"
            INSERT INTO judge_draw_votes(
                ws_id, session_id, report_id, threshold_percent, eligible_voters, required_voters,
                voting_ends_at, status, resolution, created_at, updated_at
            )
            VALUES (
                $1, $2, $3, $4, $5, $6,
                NOW() + ($7::bigint * INTERVAL '1 second'),
                'open', 'pending', NOW(), NOW()
            )
            ON CONFLICT (report_id) DO NOTHING
            "#,
        )
        .bind(ws_id)
        .bind(session_id)
        .bind(report_id)
        .bind(DRAW_VOTE_THRESHOLD_PERCENT)
        .bind(eligible_voters)
        .bind(required_voters)
        .bind(DRAW_VOTE_WINDOW_SECS)
        .execute(&mut **tx)
        .await?;
        Ok(())
    }

    pub async fn get_draw_vote_status(
        &self,
        session_id: u64,
        user: &User,
    ) -> Result<GetDrawVoteOutput, AppError> {
        let mut tx = self.pool.begin().await?;

        let session_ws_id: Option<(i64,)> = sqlx::query_as(
            r#"
            SELECT ws_id
            FROM debate_sessions
            WHERE id = $1
            "#,
        )
        .bind(session_id as i64)
        .fetch_optional(&mut *tx)
        .await?;
        let Some((session_ws_id,)) = session_ws_id else {
            return Err(AppError::NotFound(format!(
                "debate session id {session_id}"
            )));
        };
        if session_ws_id != user.ws_id {
            return Err(AppError::NotFound(format!(
                "debate session id {session_id}"
            )));
        }

        let joined = sqlx::query_scalar::<_, i32>(
            r#"
            SELECT 1
            FROM session_participants
            WHERE session_id = $1 AND user_id = $2
            LIMIT 1
            "#,
        )
        .bind(session_id as i64)
        .bind(user.id)
        .fetch_optional(&mut *tx)
        .await?;
        if joined.is_none() {
            return Err(AppError::DebateConflict(format!(
                "user {} has not joined session {}",
                user.id, session_id
            )));
        }

        let vote: Option<DrawVoteRow> = sqlx::query_as(
            r#"
            SELECT
                id, ws_id, session_id, report_id, threshold_percent, eligible_voters, required_voters,
                voting_ends_at, status, resolution, decided_at, rematch_session_id
            FROM judge_draw_votes
            WHERE session_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            FOR UPDATE
            "#,
        )
        .bind(session_id as i64)
        .fetch_optional(&mut *tx)
        .await?;
        let Some(vote) = vote else {
            tx.commit().await?;
            return Ok(GetDrawVoteOutput {
                session_id,
                status: "absent".to_string(),
                vote: None,
            });
        };

        let stats = Self::load_draw_vote_stats(&mut tx, vote.id).await?;
        let mut vote = Self::maybe_finalize_draw_vote(&mut tx, vote, &stats).await?;
        if vote.resolution == "open_rematch" && vote.rematch_session_id.is_none() {
            vote = Self::ensure_rematch_session_for_vote(&mut tx, vote).await?;
        }
        let my_vote: Option<(bool,)> = sqlx::query_as(
            r#"
            SELECT agree_draw
            FROM judge_draw_vote_ballots
            WHERE vote_id = $1 AND user_id = $2
            LIMIT 1
            "#,
        )
        .bind(vote.id)
        .bind(user.id)
        .fetch_optional(&mut *tx)
        .await?;

        tx.commit().await?;
        let status = vote.status.clone();
        Ok(GetDrawVoteOutput {
            session_id,
            status,
            vote: Some(map_draw_vote_detail(
                vote,
                stats,
                my_vote.map(|(agree_draw,)| agree_draw),
            )),
        })
    }

    pub async fn submit_draw_vote(
        &self,
        session_id: u64,
        user: &User,
        input: SubmitDrawVoteInput,
    ) -> Result<SubmitDrawVoteOutput, AppError> {
        let mut tx = self.pool.begin().await?;

        let session_ws_id: Option<(i64,)> = sqlx::query_as(
            r#"
            SELECT ws_id
            FROM debate_sessions
            WHERE id = $1
            "#,
        )
        .bind(session_id as i64)
        .fetch_optional(&mut *tx)
        .await?;
        let Some((session_ws_id,)) = session_ws_id else {
            return Err(AppError::NotFound(format!(
                "debate session id {session_id}"
            )));
        };
        if session_ws_id != user.ws_id {
            return Err(AppError::NotFound(format!(
                "debate session id {session_id}"
            )));
        }

        let joined = sqlx::query_scalar::<_, i32>(
            r#"
            SELECT 1
            FROM session_participants
            WHERE session_id = $1 AND user_id = $2
            LIMIT 1
            "#,
        )
        .bind(session_id as i64)
        .bind(user.id)
        .fetch_optional(&mut *tx)
        .await?;
        if joined.is_none() {
            return Err(AppError::DebateConflict(format!(
                "user {} has not joined session {}",
                user.id, session_id
            )));
        }

        let vote: Option<DrawVoteRow> = sqlx::query_as(
            r#"
            SELECT
                id, ws_id, session_id, report_id, threshold_percent, eligible_voters, required_voters,
                voting_ends_at, status, resolution, decided_at, rematch_session_id
            FROM judge_draw_votes
            WHERE session_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            FOR UPDATE
            "#,
        )
        .bind(session_id as i64)
        .fetch_optional(&mut *tx)
        .await?;
        let Some(vote) = vote else {
            return Err(AppError::DebateConflict(format!(
                "session {} has no draw vote",
                session_id
            )));
        };

        let before_stats = Self::load_draw_vote_stats(&mut tx, vote.id).await?;
        let vote = Self::maybe_finalize_draw_vote(&mut tx, vote, &before_stats).await?;
        if vote.status != "open" {
            return Err(AppError::DebateConflict(format!(
                "draw vote for session {} is already {}",
                session_id, vote.status
            )));
        }

        let existing: Option<(bool,)> = sqlx::query_as(
            r#"
            SELECT agree_draw
            FROM judge_draw_vote_ballots
            WHERE vote_id = $1 AND user_id = $2
            LIMIT 1
            "#,
        )
        .bind(vote.id)
        .bind(user.id)
        .fetch_optional(&mut *tx)
        .await?;
        let newly_submitted = existing.is_none();

        sqlx::query(
            r#"
            INSERT INTO judge_draw_vote_ballots(
                vote_id, ws_id, session_id, report_id, user_id, agree_draw, voted_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            ON CONFLICT (vote_id, user_id)
            DO UPDATE
            SET agree_draw = EXCLUDED.agree_draw,
                voted_at = NOW()
            "#,
        )
        .bind(vote.id)
        .bind(vote.ws_id)
        .bind(vote.session_id)
        .bind(vote.report_id)
        .bind(user.id)
        .bind(input.agree_draw)
        .execute(&mut *tx)
        .await?;

        let stats = Self::load_draw_vote_stats(&mut tx, vote.id).await?;
        let mut vote = Self::maybe_finalize_draw_vote(&mut tx, vote, &stats).await?;
        if vote.resolution == "open_rematch" && vote.rematch_session_id.is_none() {
            vote = Self::ensure_rematch_session_for_vote(&mut tx, vote).await?;
        }

        tx.commit().await?;
        let status = vote.status.clone();
        Ok(SubmitDrawVoteOutput {
            session_id,
            status,
            vote: map_draw_vote_detail(vote, stats, Some(input.agree_draw)),
            newly_submitted,
        })
    }

    pub async fn submit_judge_report(
        &self,
        job_id: u64,
        input: SubmitJudgeReportInput,
    ) -> Result<SubmitJudgeReportOutput, AppError> {
        let winner = normalize_winner(&input.winner, "winner")?;
        let winner_first = match input.winner_first.as_deref() {
            Some(v) => Some(normalize_winner(v, "winner_first")?),
            None => None,
        };
        let winner_second = match input.winner_second.as_deref() {
            Some(v) => Some(normalize_winner(v, "winner_second")?),
            None => None,
        };
        let style_mode = normalize_style_mode(input.style_mode)?;
        let pro_summary = validate_non_empty_text(&input.pro_summary, "pro_summary", 4000)?;
        let con_summary = validate_non_empty_text(&input.con_summary, "con_summary", 4000)?;
        let rationale = validate_non_empty_text(&input.rationale, "rationale", 4000)?;

        for (score, field) in [
            (input.pro_score, "pro_score"),
            (input.con_score, "con_score"),
            (input.logic_pro, "logic_pro"),
            (input.logic_con, "logic_con"),
            (input.evidence_pro, "evidence_pro"),
            (input.evidence_con, "evidence_con"),
            (input.rebuttal_pro, "rebuttal_pro"),
            (input.rebuttal_con, "rebuttal_con"),
            (input.clarity_pro, "clarity_pro"),
            (input.clarity_con, "clarity_con"),
        ] {
            validate_score(score, field)?;
        }

        let mut stage_no_set = HashSet::new();
        for stage in input.stage_summaries.iter() {
            if stage.stage_no <= 0 {
                return Err(AppError::DebateError(format!(
                    "invalid stage_no: {}, expect > 0",
                    stage.stage_no
                )));
            }
            if !stage_no_set.insert(stage.stage_no) {
                return Err(AppError::DebateError(format!(
                    "duplicated stage_no: {}",
                    stage.stage_no
                )));
            }
            validate_score(stage.pro_score, "stage.pro_score")?;
            validate_score(stage.con_score, "stage.con_score")?;
        }

        let mut tx = self.pool.begin().await?;
        let Some(job): Option<JudgeJobForUpdate> = sqlx::query_as(
            r#"
            SELECT id, ws_id, session_id, status, rejudge_triggered, error_message
            FROM judge_jobs
            WHERE id = $1
            FOR UPDATE
            "#,
        )
        .bind(job_id as i64)
        .fetch_optional(&mut *tx)
        .await?
        else {
            return Err(AppError::NotFound(format!("judge job id {job_id}")));
        };

        let existing_report: Option<JudgeReportRow> = sqlx::query_as(
            r#"
            SELECT
                id, job_id, winner, pro_score, con_score,
                logic_pro, logic_con, evidence_pro, evidence_con, rebuttal_pro, rebuttal_con,
                clarity_pro, clarity_con, pro_summary, con_summary, rationale, style_mode,
                needs_draw_vote, rejudge_triggered, payload, created_at
            FROM judge_reports
            WHERE job_id = $1
            LIMIT 1
            "#,
        )
        .bind(job_id as i64)
        .fetch_optional(&mut *tx)
        .await?;
        if let Some(report) = existing_report {
            tx.commit().await?;
            return Ok(SubmitJudgeReportOutput {
                job_id,
                session_id: job.session_id as u64,
                report_id: report.id as u64,
                status: "succeeded".to_string(),
                newly_created: false,
            });
        }

        if job.status != "running" {
            return Err(AppError::DebateConflict(format!(
                "judge job {} is not running, current status {}",
                job_id, job.status
            )));
        }

        let rejudge_triggered = input.rejudge_triggered || job.rejudge_triggered;
        let report_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO judge_reports(
                ws_id, session_id, job_id, winner, pro_score, con_score,
                logic_pro, logic_con, evidence_pro, evidence_con, rebuttal_pro, rebuttal_con,
                clarity_pro, clarity_con, pro_summary, con_summary, rationale, style_mode,
                needs_draw_vote, rejudge_triggered, payload, created_at, updated_at
            )
            SELECT
                ws_id, session_id, id, $2, $3, $4,
                $5, $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15, $16,
                $17, $18, $19, NOW(), NOW()
            FROM judge_jobs
            WHERE id = $1
            RETURNING id
            "#,
        )
        .bind(job_id as i64)
        .bind(&winner)
        .bind(input.pro_score)
        .bind(input.con_score)
        .bind(input.logic_pro)
        .bind(input.logic_con)
        .bind(input.evidence_pro)
        .bind(input.evidence_con)
        .bind(input.rebuttal_pro)
        .bind(input.rebuttal_con)
        .bind(input.clarity_pro)
        .bind(input.clarity_con)
        .bind(pro_summary)
        .bind(con_summary)
        .bind(rationale)
        .bind(style_mode.clone())
        .bind(input.needs_draw_vote)
        .bind(rejudge_triggered)
        .bind(input.payload)
        .fetch_one(&mut *tx)
        .await?;

        if input.needs_draw_vote {
            Self::create_draw_vote_for_report(&mut tx, job.ws_id, job.session_id, report_id.0)
                .await?;
        }

        for stage in input.stage_summaries.iter() {
            sqlx::query(
                r#"
                INSERT INTO judge_stage_summaries(
                    ws_id, session_id, job_id, stage_no, from_message_id, to_message_id,
                    pro_score, con_score, summary, created_at
                )
                SELECT
                    ws_id, session_id, id, $2, $3, $4, $5, $6, $7, NOW()
                FROM judge_jobs
                WHERE id = $1
                "#,
            )
            .bind(job_id as i64)
            .bind(stage.stage_no)
            .bind(stage.from_message_id.map(|v| v as i64))
            .bind(stage.to_message_id.map(|v| v as i64))
            .bind(stage.pro_score)
            .bind(stage.con_score)
            .bind(stage.summary.clone())
            .execute(&mut *tx)
            .await?;
        }

        sqlx::query(
            r#"
            UPDATE judge_jobs
            SET status = 'succeeded',
                style_mode = $2,
                winner_first = $3,
                winner_second = $4,
                error_message = NULL,
                finished_at = NOW(),
                updated_at = NOW()
            WHERE id = $1
            "#,
        )
        .bind(job_id as i64)
        .bind(style_mode)
        .bind(winner_first)
        .bind(winner_second)
        .execute(&mut *tx)
        .await?;

        tx.commit().await?;
        Ok(SubmitJudgeReportOutput {
            job_id,
            session_id: job.session_id as u64,
            report_id: report_id.0 as u64,
            status: "succeeded".to_string(),
            newly_created: true,
        })
    }

    pub async fn mark_judge_job_failed(
        &self,
        job_id: u64,
        input: MarkJudgeJobFailedInput,
    ) -> Result<MarkJudgeJobFailedOutput, AppError> {
        let error_message = validate_non_empty_text(&input.error_message, "error_message", 4000)?;
        let mut tx = self.pool.begin().await?;
        let Some(job): Option<JudgeJobForUpdate> = sqlx::query_as(
            r#"
            SELECT id, ws_id, session_id, status, rejudge_triggered, error_message
            FROM judge_jobs
            WHERE id = $1
            FOR UPDATE
            "#,
        )
        .bind(job_id as i64)
        .fetch_optional(&mut *tx)
        .await?
        else {
            return Err(AppError::NotFound(format!("judge job id {job_id}")));
        };
        let report_exists = sqlx::query_scalar::<_, i64>(
            r#"
            SELECT id
            FROM judge_reports
            WHERE job_id = $1
            LIMIT 1
            "#,
        )
        .bind(job.id)
        .fetch_optional(&mut *tx)
        .await?
        .is_some();
        if report_exists {
            return Err(AppError::DebateConflict(format!(
                "judge job {} already has report, cannot mark failed",
                job_id
            )));
        }

        if job.status == "failed" {
            tx.commit().await?;
            return Ok(MarkJudgeJobFailedOutput {
                job_id,
                session_id: job.session_id as u64,
                status: "failed".to_string(),
                error_message: job.error_message.unwrap_or(error_message),
                newly_marked: false,
            });
        }
        if job.status != "running" {
            return Err(AppError::DebateConflict(format!(
                "judge job {} is not running, current status {}",
                job_id, job.status
            )));
        }

        sqlx::query(
            r#"
            UPDATE judge_jobs
            SET status = 'failed',
                error_message = $2,
                finished_at = NOW(),
                updated_at = NOW()
            WHERE id = $1
            "#,
        )
        .bind(job.id)
        .bind(&error_message)
        .execute(&mut *tx)
        .await?;

        tx.commit().await?;
        Ok(MarkJudgeJobFailedOutput {
            job_id,
            session_id: job.session_id as u64,
            status: "failed".to_string(),
            error_message,
            newly_marked: true,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use anyhow::Result;
    use chrono::Duration;
    use std::sync::Arc;

    async fn seed_topic_and_session(state: &AppState, ws_id: i64, status: &str) -> Result<i64> {
        let topic_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO debate_topics(ws_id, title, description, category, stance_pro, stance_con, is_active, created_by)
            VALUES ($1, 'topic-ai', 'desc', 'game', 'pro', 'con', true, 1)
            RETURNING id
            "#,
        )
        .bind(ws_id)
        .fetch_one(&state.pool)
        .await?;

        let now = Utc::now();
        let session_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO debate_sessions(
                ws_id, topic_id, status, scheduled_start_at, actual_start_at, end_at, max_participants_per_side
            )
            VALUES ($1, $2, $3, $4, $5, $6, 500)
            RETURNING id
            "#,
        )
        .bind(ws_id)
        .bind(topic_id.0)
        .bind(status)
        .bind(now - Duration::minutes(20))
        .bind(now - Duration::minutes(15))
        .bind(now - Duration::minutes(1))
        .fetch_one(&state.pool)
        .await?;

        Ok(session_id.0)
    }

    async fn join_user_to_session(state: &AppState, session_id: i64, user_id: i64) -> Result<()> {
        sqlx::query(
            r#"
            INSERT INTO session_participants(session_id, user_id, side)
            VALUES ($1, $2, 'pro')
            "#,
        )
        .bind(session_id)
        .bind(user_id)
        .execute(&state.pool)
        .await?;
        Ok(())
    }

    async fn seed_running_judge_job(state: &AppState, session_id: i64) -> Result<i64> {
        let job_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO judge_jobs(
                ws_id, session_id, requested_by, status, style_mode, requested_at, started_at, created_at, updated_at
            )
            VALUES ($1, $2, $3, 'running', 'rational', NOW(), NOW(), NOW(), NOW())
            RETURNING id
            "#,
        )
        .bind(1_i64)
        .bind(session_id)
        .bind(1_i64)
        .fetch_one(&state.pool)
        .await?;
        Ok(job_id.0)
    }

    #[test]
    fn extract_rag_meta_should_return_none_when_payload_has_no_rag_fields() {
        let payload = serde_json::json!({
            "provider": "openai",
            "traceId": "trace-1"
        });
        assert!(extract_rag_meta(&payload).is_none());
    }

    #[test]
    fn extract_rag_meta_should_parse_whitelist_and_sources() {
        let payload = serde_json::json!({
            "ragEnabled": true,
            "ragUsedByModel": false,
            "ragSnippetCount": 2,
            "ragSourceWhitelist": [" https://foo.example/news/ ", "", "https://bar.example/"],
            "ragSources": [
                {
                    "chunkId": "chunk-1",
                    "title": "doc-a",
                    "sourceUrl": "https://foo.example/news/a",
                    "score": 0.91
                },
                {
                    "chunk_id": "chunk-2",
                    "title": "doc-b",
                    "source_url": "https://bar.example/b"
                },
                {}
            ]
        });

        let meta = extract_rag_meta(&payload).expect("meta should exist");
        assert_eq!(meta.enabled, Some(true));
        assert_eq!(meta.used_by_model, Some(false));
        assert_eq!(meta.snippet_count, Some(2));
        assert_eq!(
            meta.source_whitelist,
            vec![
                "https://foo.example/news/".to_string(),
                "https://bar.example/".to_string()
            ]
        );
        assert_eq!(meta.sources.len(), 2);
        assert_eq!(meta.sources[0].chunk_id, "chunk-1");
        assert_eq!(meta.sources[0].source_url, "https://foo.example/news/a");
        assert_eq!(meta.sources[1].chunk_id, "chunk-2");
        assert_eq!(meta.sources[1].source_url, "https://bar.example/b");
    }

    #[tokio::test]
    async fn request_judge_job_should_create_running_job_with_default_style() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id = seed_topic_and_session(&state, 1, "judging").await?;
        join_user_to_session(&state, session_id, 1).await?;
        let user = state.find_user_by_id(1).await?.expect("user should exist");

        let ret = state
            .request_judge_job(
                session_id as u64,
                &user,
                RequestJudgeJobInput {
                    style_mode: None,
                    allow_rejudge: false,
                },
            )
            .await?;

        assert!(ret.newly_created);
        assert_eq!(ret.style_mode, "rational");
        assert_eq!(ret.style_mode_source, "system_config");
        assert_eq!(ret.status, "running");
        Ok(())
    }

    #[tokio::test]
    async fn request_judge_job_should_be_idempotent_with_running_job() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id = seed_topic_and_session(&state, 1, "closed").await?;
        join_user_to_session(&state, session_id, 1).await?;
        let user = state.find_user_by_id(1).await?.expect("user should exist");

        let first = state
            .request_judge_job(
                session_id as u64,
                &user,
                RequestJudgeJobInput {
                    style_mode: Some("mixed".to_string()),
                    allow_rejudge: false,
                },
            )
            .await?;
        let second = state
            .request_judge_job(
                session_id as u64,
                &user,
                RequestJudgeJobInput {
                    style_mode: Some("mixed".to_string()),
                    allow_rejudge: false,
                },
            )
            .await?;

        assert!(first.newly_created);
        assert!(!second.newly_created);
        assert_eq!(first.job_id, second.job_id);
        assert_eq!(first.style_mode, "rational");
        assert_eq!(first.style_mode_source, "system_config");
        assert_eq!(second.style_mode, "rational");
        assert_eq!(second.style_mode_source, "existing_running_job");
        Ok(())
    }

    #[tokio::test]
    async fn request_judge_job_should_use_system_style_mode_instead_of_request_value() -> Result<()>
    {
        let (_tdb, mut state) = AppState::new_for_test().await?;
        let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
        inner.config.ai_judge.style_mode = "entertaining".to_string();

        let session_id = seed_topic_and_session(&state, 1, "closed").await?;
        join_user_to_session(&state, session_id, 1).await?;
        let user = state.find_user_by_id(1).await?.expect("user should exist");

        let ret = state
            .request_judge_job(
                session_id as u64,
                &user,
                RequestJudgeJobInput {
                    style_mode: Some("mixed".to_string()),
                    allow_rejudge: false,
                },
            )
            .await?;

        assert_eq!(ret.style_mode, "entertaining");
        assert_eq!(ret.style_mode_source, "system_config");
        Ok(())
    }

    #[tokio::test]
    async fn request_judge_job_should_fallback_to_rational_when_system_style_invalid() -> Result<()>
    {
        let (_tdb, mut state) = AppState::new_for_test().await?;
        let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
        inner.config.ai_judge.style_mode = "invalid-style".to_string();

        let session_id = seed_topic_and_session(&state, 1, "closed").await?;
        join_user_to_session(&state, session_id, 1).await?;
        let user = state.find_user_by_id(1).await?.expect("user should exist");

        let ret = state
            .request_judge_job(
                session_id as u64,
                &user,
                RequestJudgeJobInput {
                    style_mode: Some("mixed".to_string()),
                    allow_rejudge: false,
                },
            )
            .await?;

        assert_eq!(ret.style_mode, "rational");
        assert_eq!(ret.style_mode_source, "system_config_fallback_default");
        Ok(())
    }

    #[tokio::test]
    async fn request_judge_job_should_reject_user_not_joined() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id = seed_topic_and_session(&state, 1, "judging").await?;
        let user = state.find_user_by_id(1).await?.expect("user should exist");

        let err = state
            .request_judge_job(
                session_id as u64,
                &user,
                RequestJudgeJobInput {
                    style_mode: None,
                    allow_rejudge: false,
                },
            )
            .await
            .expect_err("should reject non participant");
        assert!(matches!(err, AppError::DebateConflict(_)));
        Ok(())
    }

    #[tokio::test]
    async fn request_judge_job_should_reject_non_judging_session() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id = seed_topic_and_session(&state, 1, "running").await?;
        join_user_to_session(&state, session_id, 1).await?;
        let user = state.find_user_by_id(1).await?.expect("user should exist");

        let err = state
            .request_judge_job(
                session_id as u64,
                &user,
                RequestJudgeJobInput {
                    style_mode: None,
                    allow_rejudge: false,
                },
            )
            .await
            .expect_err("running status should reject");
        assert!(matches!(err, AppError::DebateConflict(_)));
        Ok(())
    }

    #[tokio::test]
    async fn get_latest_judge_report_should_return_pending_when_job_running() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id = seed_topic_and_session(&state, 1, "judging").await?;
        join_user_to_session(&state, session_id, 1).await?;
        let user = state.find_user_by_id(1).await?.expect("user should exist");

        state
            .request_judge_job(
                session_id as u64,
                &user,
                RequestJudgeJobInput {
                    style_mode: None,
                    allow_rejudge: false,
                },
            )
            .await?;

        let ret = state
            .get_latest_judge_report(session_id as u64, &user)
            .await?;
        assert_eq!(ret.status, "pending");
        assert!(ret.latest_job.is_some());
        assert!(ret.report.is_none());
        Ok(())
    }

    #[tokio::test]
    async fn get_latest_judge_report_should_return_ready_when_report_exists() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id = seed_topic_and_session(&state, 1, "closed").await?;
        join_user_to_session(&state, session_id, 1).await?;
        let user = state.find_user_by_id(1).await?.expect("user should exist");

        let job_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO judge_jobs(
                ws_id, session_id, requested_by, status, style_mode, requested_at, started_at, finished_at
            )
            VALUES ($1, $2, $3, 'succeeded', 'rational', NOW(), NOW(), NOW())
            RETURNING id
            "#,
        )
        .bind(1_i64)
        .bind(session_id)
        .bind(1_i64)
        .fetch_one(&state.pool)
        .await?;

        sqlx::query(
            r#"
            INSERT INTO judge_reports(
                ws_id, session_id, job_id, winner, pro_score, con_score,
                logic_pro, logic_con, evidence_pro, evidence_con, rebuttal_pro, rebuttal_con,
                clarity_pro, clarity_con, pro_summary, con_summary, rationale, style_mode,
                needs_draw_vote, rejudge_triggered, payload
            )
            VALUES (
                $1, $2, $3, 'pro', 82, 74,
                80, 72, 85, 76, 79, 71,
                84, 77, 'pro summary', 'con summary', 'rationale', 'rational',
                false, false, '{"trace":"ok"}'::jsonb
            )
            "#,
        )
        .bind(1_i64)
        .bind(session_id)
        .bind(job_id.0)
        .execute(&state.pool)
        .await?;

        let ret = state
            .get_latest_judge_report(session_id as u64, &user)
            .await?;
        assert_eq!(ret.status, "ready");
        let report = ret.report.expect("report should exist");
        assert_eq!(report.job_id, job_id.0 as u64);
        assert_eq!(report.winner, "pro");
        assert_eq!(report.pro_score, 82);
        Ok(())
    }

    #[tokio::test]
    async fn submit_judge_report_should_persist_report_and_mark_job_succeeded() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id = seed_topic_and_session(&state, 1, "judging").await?;
        let job_id = seed_running_judge_job(&state, session_id).await?;

        let ret = state
            .submit_judge_report(
                job_id as u64,
                SubmitJudgeReportInput {
                    winner: "pro".to_string(),
                    pro_score: 84,
                    con_score: 76,
                    logic_pro: 83,
                    logic_con: 74,
                    evidence_pro: 85,
                    evidence_con: 78,
                    rebuttal_pro: 82,
                    rebuttal_con: 73,
                    clarity_pro: 86,
                    clarity_con: 79,
                    pro_summary: "pro summary".to_string(),
                    con_summary: "con summary".to_string(),
                    rationale: "final rationale".to_string(),
                    style_mode: Some("mixed".to_string()),
                    needs_draw_vote: false,
                    rejudge_triggered: false,
                    payload: serde_json::json!({"provider":"openai","traceId":"abc"}),
                    winner_first: Some("pro".to_string()),
                    winner_second: Some("pro".to_string()),
                    stage_summaries: vec![
                        JudgeStageSummaryInput {
                            stage_no: 1,
                            from_message_id: Some(1),
                            to_message_id: Some(100),
                            pro_score: 80,
                            con_score: 75,
                            summary: serde_json::json!({"brief":"s1"}),
                        },
                        JudgeStageSummaryInput {
                            stage_no: 2,
                            from_message_id: Some(101),
                            to_message_id: Some(200),
                            pro_score: 84,
                            con_score: 76,
                            summary: serde_json::json!({"brief":"s2"}),
                        },
                    ],
                },
            )
            .await?;
        assert!(ret.newly_created);
        assert_eq!(ret.status, "succeeded");

        let row: (String, Option<String>, Option<String>) = sqlx::query_as(
            r#"
            SELECT status, winner_first, winner_second
            FROM judge_jobs
            WHERE id = $1
            "#,
        )
        .bind(job_id)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(row.0, "succeeded");
        assert_eq!(row.1.as_deref(), Some("pro"));
        assert_eq!(row.2.as_deref(), Some("pro"));

        let stage_cnt: (i64,) = sqlx::query_as(
            r#"
            SELECT COUNT(*)::bigint
            FROM judge_stage_summaries
            WHERE job_id = $1
            "#,
        )
        .bind(job_id)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(stage_cnt.0, 2);
        Ok(())
    }

    #[tokio::test]
    async fn submit_judge_report_should_be_idempotent_by_job_id() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id = seed_topic_and_session(&state, 1, "judging").await?;
        let job_id = seed_running_judge_job(&state, session_id).await?;
        let input = SubmitJudgeReportInput {
            winner: "con".to_string(),
            pro_score: 72,
            con_score: 81,
            logic_pro: 70,
            logic_con: 83,
            evidence_pro: 74,
            evidence_con: 82,
            rebuttal_pro: 71,
            rebuttal_con: 80,
            clarity_pro: 73,
            clarity_con: 79,
            pro_summary: "pro".to_string(),
            con_summary: "con".to_string(),
            rationale: "rationale".to_string(),
            style_mode: Some("rational".to_string()),
            needs_draw_vote: false,
            rejudge_triggered: false,
            payload: serde_json::json!({"x":1}),
            winner_first: Some("con".to_string()),
            winner_second: Some("con".to_string()),
            stage_summaries: vec![],
        };
        let first = state
            .submit_judge_report(job_id as u64, input.clone())
            .await?;
        let second = state.submit_judge_report(job_id as u64, input).await?;
        assert!(first.newly_created);
        assert!(!second.newly_created);
        assert_eq!(first.report_id, second.report_id);
        Ok(())
    }

    #[tokio::test]
    async fn mark_judge_job_failed_should_update_status_and_be_idempotent() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id = seed_topic_and_session(&state, 1, "judging").await?;
        let job_id = seed_running_judge_job(&state, session_id).await?;
        let first = state
            .mark_judge_job_failed(
                job_id as u64,
                MarkJudgeJobFailedInput {
                    error_message: "timeout".to_string(),
                },
            )
            .await?;
        let second = state
            .mark_judge_job_failed(
                job_id as u64,
                MarkJudgeJobFailedInput {
                    error_message: "ignored".to_string(),
                },
            )
            .await?;
        assert!(first.newly_marked);
        assert!(!second.newly_marked);
        assert_eq!(second.error_message, "timeout");
        Ok(())
    }

    #[tokio::test]
    async fn mark_judge_job_failed_should_reject_when_report_exists() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id = seed_topic_and_session(&state, 1, "closed").await?;
        let job_id = seed_running_judge_job(&state, session_id).await?;

        state
            .submit_judge_report(
                job_id as u64,
                SubmitJudgeReportInput {
                    winner: "pro".to_string(),
                    pro_score: 80,
                    con_score: 70,
                    logic_pro: 80,
                    logic_con: 70,
                    evidence_pro: 80,
                    evidence_con: 70,
                    rebuttal_pro: 80,
                    rebuttal_con: 70,
                    clarity_pro: 80,
                    clarity_con: 70,
                    pro_summary: "p".to_string(),
                    con_summary: "c".to_string(),
                    rationale: "r".to_string(),
                    style_mode: Some("rational".to_string()),
                    needs_draw_vote: false,
                    rejudge_triggered: false,
                    payload: serde_json::json!({}),
                    winner_first: Some("pro".to_string()),
                    winner_second: Some("pro".to_string()),
                    stage_summaries: vec![],
                },
            )
            .await?;

        let err = state
            .mark_judge_job_failed(
                job_id as u64,
                MarkJudgeJobFailedInput {
                    error_message: "should fail".to_string(),
                },
            )
            .await
            .expect_err("should reject");
        assert!(matches!(err, AppError::DebateConflict(_)));
        Ok(())
    }

    #[tokio::test]
    async fn submit_judge_report_should_create_draw_vote_when_needed() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id = seed_topic_and_session(&state, 1, "closed").await?;
        join_user_to_session(&state, session_id, 1).await?;
        join_user_to_session(&state, session_id, 2).await?;
        join_user_to_session(&state, session_id, 3).await?;
        let job_id = seed_running_judge_job(&state, session_id).await?;

        state
            .submit_judge_report(
                job_id as u64,
                SubmitJudgeReportInput {
                    winner: "draw".to_string(),
                    pro_score: 80,
                    con_score: 80,
                    logic_pro: 80,
                    logic_con: 80,
                    evidence_pro: 80,
                    evidence_con: 80,
                    rebuttal_pro: 80,
                    rebuttal_con: 80,
                    clarity_pro: 80,
                    clarity_con: 80,
                    pro_summary: "pro".to_string(),
                    con_summary: "con".to_string(),
                    rationale: "rationale".to_string(),
                    style_mode: Some("rational".to_string()),
                    needs_draw_vote: true,
                    rejudge_triggered: true,
                    payload: serde_json::json!({}),
                    winner_first: Some("pro".to_string()),
                    winner_second: Some("con".to_string()),
                    stage_summaries: vec![],
                },
            )
            .await?;

        let row: (i32, i32, String, String) = sqlx::query_as(
            r#"
            SELECT eligible_voters, required_voters, status, resolution
            FROM judge_draw_votes
            WHERE session_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            "#,
        )
        .bind(session_id)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(row.0, 3);
        assert_eq!(row.1, 3);
        assert_eq!(row.2, "open");
        assert_eq!(row.3, "pending");
        Ok(())
    }

    #[tokio::test]
    async fn submit_draw_vote_should_decide_after_threshold_reached() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id = seed_topic_and_session(&state, 1, "closed").await?;
        join_user_to_session(&state, session_id, 1).await?;
        join_user_to_session(&state, session_id, 2).await?;
        join_user_to_session(&state, session_id, 3).await?;
        let job_id = seed_running_judge_job(&state, session_id).await?;

        state
            .submit_judge_report(
                job_id as u64,
                SubmitJudgeReportInput {
                    winner: "draw".to_string(),
                    pro_score: 79,
                    con_score: 79,
                    logic_pro: 79,
                    logic_con: 79,
                    evidence_pro: 79,
                    evidence_con: 79,
                    rebuttal_pro: 79,
                    rebuttal_con: 79,
                    clarity_pro: 79,
                    clarity_con: 79,
                    pro_summary: "pro".to_string(),
                    con_summary: "con".to_string(),
                    rationale: "rationale".to_string(),
                    style_mode: Some("rational".to_string()),
                    needs_draw_vote: true,
                    rejudge_triggered: true,
                    payload: serde_json::json!({}),
                    winner_first: Some("pro".to_string()),
                    winner_second: Some("con".to_string()),
                    stage_summaries: vec![],
                },
            )
            .await?;

        let user1 = state.find_user_by_id(1).await?.expect("user1 should exist");
        let user2 = state.find_user_by_id(2).await?.expect("user2 should exist");
        let user3 = state.find_user_by_id(3).await?.expect("user3 should exist");

        let vote1 = state
            .submit_draw_vote(
                session_id as u64,
                &user1,
                SubmitDrawVoteInput { agree_draw: true },
            )
            .await?;
        assert_eq!(vote1.status, "open");

        let vote2 = state
            .submit_draw_vote(
                session_id as u64,
                &user2,
                SubmitDrawVoteInput { agree_draw: true },
            )
            .await?;
        assert_eq!(vote2.status, "open");

        let vote3 = state
            .submit_draw_vote(
                session_id as u64,
                &user3,
                SubmitDrawVoteInput { agree_draw: false },
            )
            .await?;
        assert_eq!(vote3.status, "decided");
        assert_eq!(vote3.vote.resolution, "accept_draw");
        assert_eq!(vote3.vote.participated_voters, 3);
        assert_eq!(vote3.vote.agree_votes, 2);
        assert_eq!(vote3.vote.disagree_votes, 1);
        assert!(vote3.vote.rematch_session_id.is_none());
        Ok(())
    }

    #[tokio::test]
    async fn get_draw_vote_status_should_auto_expire_to_open_rematch() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id = seed_topic_and_session(&state, 1, "closed").await?;
        join_user_to_session(&state, session_id, 1).await?;
        join_user_to_session(&state, session_id, 2).await?;
        let job_id = seed_running_judge_job(&state, session_id).await?;

        state
            .submit_judge_report(
                job_id as u64,
                SubmitJudgeReportInput {
                    winner: "draw".to_string(),
                    pro_score: 75,
                    con_score: 75,
                    logic_pro: 75,
                    logic_con: 75,
                    evidence_pro: 75,
                    evidence_con: 75,
                    rebuttal_pro: 75,
                    rebuttal_con: 75,
                    clarity_pro: 75,
                    clarity_con: 75,
                    pro_summary: "pro".to_string(),
                    con_summary: "con".to_string(),
                    rationale: "rationale".to_string(),
                    style_mode: Some("rational".to_string()),
                    needs_draw_vote: true,
                    rejudge_triggered: true,
                    payload: serde_json::json!({}),
                    winner_first: Some("pro".to_string()),
                    winner_second: Some("con".to_string()),
                    stage_summaries: vec![],
                },
            )
            .await?;

        sqlx::query(
            r#"
            UPDATE judge_draw_votes
            SET voting_ends_at = NOW() - INTERVAL '1 second',
                updated_at = NOW()
            WHERE session_id = $1
            "#,
        )
        .bind(session_id)
        .execute(&state.pool)
        .await?;

        let user1 = state.find_user_by_id(1).await?.expect("user1 should exist");
        let status = state
            .get_draw_vote_status(session_id as u64, &user1)
            .await?;
        assert_eq!(status.status, "expired");
        let vote = status.vote.expect("vote should exist");
        assert_eq!(vote.resolution, "open_rematch");
        assert_eq!(vote.participated_voters, 0);
        let rematch_session_id = vote
            .rematch_session_id
            .expect("expired open_rematch should create rematch session");
        let rematch_row: (String, Option<i64>, i32) = sqlx::query_as(
            r#"
            SELECT status, parent_session_id, rematch_round
            FROM debate_sessions
            WHERE id = $1
            "#,
        )
        .bind(rematch_session_id as i64)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(rematch_row.0, "scheduled");
        assert_eq!(rematch_row.1, Some(session_id));
        assert_eq!(rematch_row.2, 1);
        Ok(())
    }

    #[tokio::test]
    async fn submit_draw_vote_should_open_rematch_when_disagree_majority() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id = seed_topic_and_session(&state, 1, "closed").await?;
        join_user_to_session(&state, session_id, 1).await?;
        join_user_to_session(&state, session_id, 2).await?;
        join_user_to_session(&state, session_id, 3).await?;
        let job_id = seed_running_judge_job(&state, session_id).await?;

        state
            .submit_judge_report(
                job_id as u64,
                SubmitJudgeReportInput {
                    winner: "draw".to_string(),
                    pro_score: 78,
                    con_score: 78,
                    logic_pro: 78,
                    logic_con: 78,
                    evidence_pro: 78,
                    evidence_con: 78,
                    rebuttal_pro: 78,
                    rebuttal_con: 78,
                    clarity_pro: 78,
                    clarity_con: 78,
                    pro_summary: "pro".to_string(),
                    con_summary: "con".to_string(),
                    rationale: "rationale".to_string(),
                    style_mode: Some("rational".to_string()),
                    needs_draw_vote: true,
                    rejudge_triggered: true,
                    payload: serde_json::json!({}),
                    winner_first: Some("pro".to_string()),
                    winner_second: Some("con".to_string()),
                    stage_summaries: vec![],
                },
            )
            .await?;

        let user1 = state.find_user_by_id(1).await?.expect("user1 should exist");
        let user2 = state.find_user_by_id(2).await?.expect("user2 should exist");
        let user3 = state.find_user_by_id(3).await?.expect("user3 should exist");

        state
            .submit_draw_vote(
                session_id as u64,
                &user1,
                SubmitDrawVoteInput { agree_draw: false },
            )
            .await?;
        state
            .submit_draw_vote(
                session_id as u64,
                &user2,
                SubmitDrawVoteInput { agree_draw: false },
            )
            .await?;
        let final_vote = state
            .submit_draw_vote(
                session_id as u64,
                &user3,
                SubmitDrawVoteInput { agree_draw: true },
            )
            .await?;
        assert_eq!(final_vote.status, "decided");
        assert_eq!(final_vote.vote.resolution, "open_rematch");
        assert_eq!(final_vote.vote.agree_votes, 1);
        assert_eq!(final_vote.vote.disagree_votes, 2);
        let rematch_session_id = final_vote
            .vote
            .rematch_session_id
            .expect("open_rematch decision should create rematch session");
        let rematch_row: (String, Option<i64>, i32) = sqlx::query_as(
            r#"
            SELECT status, parent_session_id, rematch_round
            FROM debate_sessions
            WHERE id = $1
            "#,
        )
        .bind(rematch_session_id as i64)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(rematch_row.0, "scheduled");
        assert_eq!(rematch_row.1, Some(session_id));
        assert_eq!(rematch_row.2, 1);
        Ok(())
    }

    #[tokio::test]
    async fn submit_draw_vote_should_reject_non_participant() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id = seed_topic_and_session(&state, 1, "closed").await?;
        join_user_to_session(&state, session_id, 1).await?;
        let job_id = seed_running_judge_job(&state, session_id).await?;

        state
            .submit_judge_report(
                job_id as u64,
                SubmitJudgeReportInput {
                    winner: "draw".to_string(),
                    pro_score: 70,
                    con_score: 70,
                    logic_pro: 70,
                    logic_con: 70,
                    evidence_pro: 70,
                    evidence_con: 70,
                    rebuttal_pro: 70,
                    rebuttal_con: 70,
                    clarity_pro: 70,
                    clarity_con: 70,
                    pro_summary: "pro".to_string(),
                    con_summary: "con".to_string(),
                    rationale: "rationale".to_string(),
                    style_mode: Some("rational".to_string()),
                    needs_draw_vote: true,
                    rejudge_triggered: true,
                    payload: serde_json::json!({}),
                    winner_first: Some("pro".to_string()),
                    winner_second: Some("con".to_string()),
                    stage_summaries: vec![],
                },
            )
            .await?;

        let user4 = state.find_user_by_id(4).await?.expect("user4 should exist");
        let err = state
            .submit_draw_vote(
                session_id as u64,
                &user4,
                SubmitDrawVoteInput { agree_draw: true },
            )
            .await
            .expect_err("non participant should be rejected");
        assert!(matches!(err, AppError::DebateConflict(_)));
        Ok(())
    }
}
