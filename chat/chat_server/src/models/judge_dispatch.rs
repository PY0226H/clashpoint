use crate::{AppError, AppState};
use chrono::{DateTime, Utc};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use sqlx::FromRow;
use tracing::warn;

const DISPATCH_MESSAGE_WINDOW_LIMIT: i64 = 100;
const DISPATCH_ERROR_MAX_LEN: usize = 1000;

#[derive(Debug, Default, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgeDispatchTickReport {
    pub claimed: usize,
    pub dispatched: usize,
    pub failed: usize,
    pub marked_failed: usize,
    pub timed_out_failed: usize,
    pub terminal_failed: usize,
    pub retryable_failed: usize,
    pub failed_contract: usize,
    pub failed_http_4xx: usize,
    pub failed_http_429: usize,
    pub failed_http_5xx: usize,
    pub failed_network: usize,
    pub failed_internal: usize,
}

#[derive(Debug, Clone, FromRow)]
struct PendingDispatchJob {
    id: i64,
    ws_id: i64,
    session_id: i64,
    requested_by: i64,
    style_mode: String,
    rejudge_triggered: bool,
    requested_at: DateTime<Utc>,
    dispatch_attempts: i32,
}

#[derive(Debug, Clone, FromRow)]
struct SessionTopicRow {
    status: String,
    scheduled_start_at: DateTime<Utc>,
    actual_start_at: Option<DateTime<Utc>>,
    end_at: DateTime<Utc>,
    title: String,
    description: String,
    category: String,
    stance_pro: String,
    stance_con: String,
    context_seed: Option<String>,
}

#[derive(Debug, Clone, FromRow)]
struct SessionMessageRow {
    id: i64,
    user_id: i64,
    side: String,
    content: String,
    created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct AiJudgeDispatchRequest {
    job: AiJudgeDispatchJob,
    session: AiJudgeDispatchSession,
    topic: AiJudgeDispatchTopic,
    messages: Vec<AiJudgeDispatchMessage>,
    message_window_size: i64,
    rubric_version: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct AiJudgeDispatchJob {
    job_id: u64,
    ws_id: u64,
    session_id: u64,
    requested_by: u64,
    style_mode: String,
    rejudge_triggered: bool,
    requested_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct AiJudgeDispatchSession {
    status: String,
    scheduled_start_at: DateTime<Utc>,
    actual_start_at: Option<DateTime<Utc>>,
    end_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct AiJudgeDispatchTopic {
    title: String,
    description: String,
    category: String,
    stance_pro: String,
    stance_con: String,
    context_seed: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct AiJudgeDispatchMessage {
    message_id: u64,
    user_id: u64,
    side: String,
    content: String,
    created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
struct AiJudgeDispatchResponse {
    accepted: Option<bool>,
    job_id: Option<u64>,
    status: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum DispatchFailureCode {
    PayloadBuildFailed,
    BuildClientFailed,
    NetworkSendFailed,
    ResponseAcceptedFalse,
    ResponseJobIdMismatch,
    Http4xx,
    Http429,
    Http5xx,
    HttpUnexpectedStatus,
}

impl DispatchFailureCode {
    fn as_str(self) -> &'static str {
        match self {
            Self::PayloadBuildFailed => "payload_build_failed",
            Self::BuildClientFailed => "build_client_failed",
            Self::NetworkSendFailed => "network_send_failed",
            Self::ResponseAcceptedFalse => "response_accepted_false",
            Self::ResponseJobIdMismatch => "response_job_id_mismatch",
            Self::Http4xx => "http_4xx",
            Self::Http429 => "http_429",
            Self::Http5xx => "http_5xx",
            Self::HttpUnexpectedStatus => "http_unexpected_status",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
enum DispatchResponseViolation {
    AcceptedFalse { status: String },
    JobIdMismatch { expected: u64, got: u64 },
}

impl std::fmt::Display for DispatchResponseViolation {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::AcceptedFalse { status } => {
                write!(
                    f,
                    "dispatch response rejected: accepted=false, status={status}"
                )
            }
            Self::JobIdMismatch { expected, got } => write!(
                f,
                "dispatch response job_id mismatch: expected={}, got={}",
                expected, got
            ),
        }
    }
}

#[derive(Debug, Clone)]
struct DispatchSendError {
    code: DispatchFailureCode,
    message: String,
    terminal: bool,
}

impl DispatchSendError {
    fn retryable(code: DispatchFailureCode, message: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
            terminal: false,
        }
    }

    fn terminal(code: DispatchFailureCode, message: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
            terminal: true,
        }
    }
}

fn build_dispatch_url(base: &str, path: &str) -> String {
    let base = base.trim_end_matches('/');
    let path = path.trim_start_matches('/');
    format!("{base}/{path}")
}

fn sanitize_error_message(err: &str) -> String {
    let ret = err.trim();
    if ret.is_empty() {
        return "dispatch failed with empty error".to_string();
    }
    if ret.len() <= DISPATCH_ERROR_MAX_LEN {
        return ret.to_string();
    }
    ret.chars().take(DISPATCH_ERROR_MAX_LEN).collect()
}

fn coded_error_message(code: DispatchFailureCode, msg: &str) -> String {
    format!("[{}] {}", code.as_str(), msg)
}

fn deterministic_jitter_offset(job_id: i64, dispatch_attempts: i32, jitter_window: i64) -> i64 {
    if jitter_window <= 0 {
        return 0;
    }
    let attempt = dispatch_attempts.max(1) as u64;
    let seed = (job_id as u64)
        .wrapping_mul(6_364_136_223_846_793_005)
        .wrapping_add(attempt.wrapping_mul(1_442_695_040_888_963_407));
    let span = (jitter_window as u64).saturating_mul(2).saturating_add(1);
    let bucket = if span == 0 { 0 } else { seed % span };
    bucket as i64 - jitter_window
}

fn calc_retry_lock_secs(
    job_id: i64,
    dispatch_attempts: i32,
    base_lock_secs: i64,
    max_backoff_multiplier: i64,
    jitter_ratio: i64,
) -> i64 {
    let base = base_lock_secs.max(1);
    let attempts = dispatch_attempts.max(1) as u32;
    let shift = attempts.saturating_sub(1).min(3);
    let max_multiplier = max_backoff_multiplier.clamp(1, 64);
    let multiplier = (1_i64 << shift).min(max_multiplier);
    let lock_secs = base.saturating_mul(multiplier).max(1);

    let jitter_ratio = jitter_ratio.clamp(0, 100);
    if jitter_ratio == 0 {
        return lock_secs;
    }
    let jitter_window = lock_secs.saturating_mul(jitter_ratio).saturating_div(100);
    let jitter_offset = deterministic_jitter_offset(job_id, dispatch_attempts, jitter_window);
    lock_secs.saturating_add(jitter_offset).max(1)
}

fn validate_dispatch_response(
    body: &str,
    expected_job_id: u64,
) -> Result<(), DispatchResponseViolation> {
    let trimmed = body.trim();
    if trimmed.is_empty() {
        return Ok(());
    }

    // Backward compatibility: old AI judge mock may return free-form json body.
    let parsed: AiJudgeDispatchResponse = match serde_json::from_str(trimmed) {
        Ok(v) => v,
        Err(_) => return Ok(()),
    };

    if parsed.accepted == Some(false) {
        return Err(DispatchResponseViolation::AcceptedFalse {
            status: parsed.status.unwrap_or_else(|| "unknown".to_string()),
        });
    }

    if let Some(job_id) = parsed.job_id {
        if job_id != expected_job_id {
            return Err(DispatchResponseViolation::JobIdMismatch {
                expected: expected_job_id,
                got: job_id,
            });
        }
    }

    Ok(())
}

impl AppState {
    pub async fn dispatch_pending_judge_jobs_once(
        &self,
    ) -> Result<JudgeDispatchTickReport, AppError> {
        let timed_out_failed = self.mark_timed_out_dispatch_jobs_failed().await?;
        let jobs = self.claim_pending_dispatch_jobs().await?;
        let mut report = JudgeDispatchTickReport {
            timed_out_failed,
            claimed: jobs.len(),
            ..Default::default()
        };

        for job in jobs.into_iter() {
            let payload = match self.load_dispatch_payload(&job).await {
                Ok(v) => v,
                Err(err) => {
                    report.failed += 1;
                    report.retryable_failed += 1;
                    report.failed_internal += 1;
                    let coded_msg = coded_error_message(
                        DispatchFailureCode::PayloadBuildFailed,
                        &err.to_string(),
                    );
                    if self
                        .mark_dispatch_failure(job.id, job.dispatch_attempts, &coded_msg)
                        .await?
                    {
                        report.marked_failed += 1;
                    }
                    continue;
                }
            };
            match self.send_dispatch_request(&payload).await {
                Ok(_) => {
                    self.mark_dispatch_sent(job.id).await?;
                    report.dispatched += 1;
                }
                Err(err) => {
                    report.failed += 1;
                    if err.terminal {
                        report.terminal_failed += 1;
                        if self
                            .mark_dispatch_terminal_failure(job.id, &err.message)
                            .await?
                        {
                            report.marked_failed += 1;
                        }
                    } else if self
                        .mark_dispatch_failure(job.id, job.dispatch_attempts, &err.message)
                        .await?
                    {
                        report.retryable_failed += 1;
                        report.marked_failed += 1;
                    } else {
                        report.retryable_failed += 1;
                    }
                    match err.code {
                        DispatchFailureCode::ResponseAcceptedFalse
                        | DispatchFailureCode::ResponseJobIdMismatch => report.failed_contract += 1,
                        DispatchFailureCode::Http4xx => report.failed_http_4xx += 1,
                        DispatchFailureCode::Http429 => report.failed_http_429 += 1,
                        DispatchFailureCode::Http5xx
                        | DispatchFailureCode::HttpUnexpectedStatus => report.failed_http_5xx += 1,
                        DispatchFailureCode::NetworkSendFailed => report.failed_network += 1,
                        DispatchFailureCode::BuildClientFailed
                        | DispatchFailureCode::PayloadBuildFailed => report.failed_internal += 1,
                    }
                }
            }
        }

        Ok(report)
    }

    async fn mark_timed_out_dispatch_jobs_failed(&self) -> Result<usize, AppError> {
        let max_attempts = self.config.ai_judge.dispatch_max_attempts.max(1);
        let rows_affected = sqlx::query(
            r#"
            UPDATE judge_jobs j
            SET status = 'failed',
                error_message = COALESCE(
                    NULLIF(j.error_message, ''),
                    format(
                        'dispatch callback timeout after %s attempts',
                        j.dispatch_attempts::text
                    )
                ),
                finished_at = NOW(),
                dispatch_locked_until = NULL,
                updated_at = NOW()
            WHERE j.status = 'running'
              AND NOT EXISTS (
                SELECT 1
                FROM judge_reports r
                WHERE r.job_id = j.id
              )
              AND j.dispatch_attempts >= $1
              AND j.dispatch_locked_until IS NOT NULL
              AND j.dispatch_locked_until <= NOW()
            "#,
        )
        .bind(max_attempts)
        .execute(&self.pool)
        .await?
        .rows_affected() as usize;
        Ok(rows_affected)
    }

    async fn claim_pending_dispatch_jobs(&self) -> Result<Vec<PendingDispatchJob>, AppError> {
        let max_attempts = self.config.ai_judge.dispatch_max_attempts.max(1);
        let batch_size = self.config.ai_judge.dispatch_batch_size.max(1);
        let lock_secs = self.config.ai_judge.dispatch_lock_secs.max(1);
        let rows = sqlx::query_as(
            r#"
            WITH due AS (
                SELECT j.id
                FROM judge_jobs j
                WHERE j.status = 'running'
                  AND NOT EXISTS (
                    SELECT 1
                    FROM judge_reports r
                    WHERE r.job_id = j.id
                  )
                  AND (j.dispatch_locked_until IS NULL OR j.dispatch_locked_until <= NOW())
                  AND j.dispatch_attempts < $1
                ORDER BY j.requested_at ASC
                LIMIT $2
                FOR UPDATE SKIP LOCKED
            )
            UPDATE judge_jobs j
            SET dispatch_attempts = j.dispatch_attempts + 1,
                last_dispatch_at = NOW(),
                dispatch_locked_until = NOW() + ($3::bigint * INTERVAL '1 second'),
                updated_at = NOW()
            FROM due
            WHERE j.id = due.id
            RETURNING
                j.id,
                j.ws_id,
                j.session_id,
                j.requested_by,
                j.style_mode,
                j.rejudge_triggered,
                j.requested_at,
                j.dispatch_attempts
            "#,
        )
        .bind(max_attempts)
        .bind(batch_size)
        .bind(lock_secs)
        .fetch_all(&self.pool)
        .await?;
        Ok(rows)
    }

    async fn load_dispatch_payload(
        &self,
        job: &PendingDispatchJob,
    ) -> Result<AiJudgeDispatchRequest, AppError> {
        let session_topic: SessionTopicRow = sqlx::query_as(
            r#"
            SELECT
                s.status,
                s.scheduled_start_at,
                s.actual_start_at,
                s.end_at,
                t.title,
                t.description,
                t.category,
                t.stance_pro,
                t.stance_con,
                t.context_seed
            FROM debate_sessions s
            JOIN debate_topics t ON t.id = s.topic_id
            WHERE s.id = $1 AND s.ws_id = $2
            "#,
        )
        .bind(job.session_id)
        .bind(job.ws_id)
        .fetch_optional(&self.pool)
        .await?
        .ok_or_else(|| {
            AppError::NotFound(format!(
                "dispatch session {} in workspace {}",
                job.session_id, job.ws_id
            ))
        })?;

        let mut messages: Vec<SessionMessageRow> = sqlx::query_as(
            r#"
            SELECT id, user_id, side, content, created_at
            FROM session_messages
            WHERE session_id = $1
            ORDER BY id DESC
            LIMIT $2
            "#,
        )
        .bind(job.session_id)
        .bind(DISPATCH_MESSAGE_WINDOW_LIMIT)
        .fetch_all(&self.pool)
        .await?;
        messages.reverse();

        Ok(AiJudgeDispatchRequest {
            job: AiJudgeDispatchJob {
                job_id: job.id as u64,
                ws_id: job.ws_id as u64,
                session_id: job.session_id as u64,
                requested_by: job.requested_by as u64,
                style_mode: job.style_mode.clone(),
                rejudge_triggered: job.rejudge_triggered,
                requested_at: job.requested_at,
            },
            session: AiJudgeDispatchSession {
                status: session_topic.status,
                scheduled_start_at: session_topic.scheduled_start_at,
                actual_start_at: session_topic.actual_start_at,
                end_at: session_topic.end_at,
            },
            topic: AiJudgeDispatchTopic {
                title: session_topic.title,
                description: session_topic.description,
                category: session_topic.category,
                stance_pro: session_topic.stance_pro,
                stance_con: session_topic.stance_con,
                context_seed: session_topic.context_seed,
            },
            messages: messages
                .into_iter()
                .map(|v| AiJudgeDispatchMessage {
                    message_id: v.id as u64,
                    user_id: v.user_id as u64,
                    side: v.side,
                    content: v.content,
                    created_at: v.created_at,
                })
                .collect(),
            message_window_size: DISPATCH_MESSAGE_WINDOW_LIMIT,
            rubric_version: "v1-logic-evidence-rebuttal-clarity".to_string(),
        })
    }

    async fn send_dispatch_request(
        &self,
        payload: &AiJudgeDispatchRequest,
    ) -> Result<(), DispatchSendError> {
        let url = build_dispatch_url(
            &self.config.ai_judge.service_base_url,
            &self.config.ai_judge.dispatch_path,
        );
        let client = Client::builder()
            .timeout(std::time::Duration::from_millis(
                self.config.ai_judge.dispatch_timeout_ms.max(1),
            ))
            .build()
            .map_err(|e| {
                DispatchSendError::terminal(
                    DispatchFailureCode::BuildClientFailed,
                    coded_error_message(
                        DispatchFailureCode::BuildClientFailed,
                        &format!("build dispatch client failed: {e}"),
                    ),
                )
            })?;
        let resp = client
            .post(&url)
            .header("x-ai-internal-key", &self.config.ai_judge.internal_key)
            .json(payload)
            .send()
            .await
            .map_err(|e| {
                DispatchSendError::retryable(
                    DispatchFailureCode::NetworkSendFailed,
                    coded_error_message(
                        DispatchFailureCode::NetworkSendFailed,
                        &format!("dispatch request io failed: {e}"),
                    ),
                )
            })?;
        if resp.status().is_success() {
            let body = resp.text().await.unwrap_or_default();
            if let Err(err) = validate_dispatch_response(&body, payload.job.job_id) {
                let (code, msg) = match err {
                    DispatchResponseViolation::AcceptedFalse { status } => (
                        DispatchFailureCode::ResponseAcceptedFalse,
                        format!("dispatch response rejected: accepted=false, status={status}"),
                    ),
                    DispatchResponseViolation::JobIdMismatch { expected, got } => (
                        DispatchFailureCode::ResponseJobIdMismatch,
                        format!(
                            "dispatch response job_id mismatch: expected={}, got={}",
                            expected, got
                        ),
                    ),
                };
                return Err(DispatchSendError::terminal(
                    code,
                    coded_error_message(code, &msg),
                ));
            }
            Ok(())
        } else {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            let message = format!("dispatch request failed: status={}, body={}", status, body);
            if status == reqwest::StatusCode::TOO_MANY_REQUESTS {
                let code = DispatchFailureCode::Http429;
                Err(DispatchSendError::retryable(
                    code,
                    coded_error_message(code, &message),
                ))
            } else if status.is_client_error() {
                let code = DispatchFailureCode::Http4xx;
                Err(DispatchSendError::terminal(
                    code,
                    coded_error_message(code, &message),
                ))
            } else if status.is_server_error() {
                let code = DispatchFailureCode::Http5xx;
                Err(DispatchSendError::retryable(
                    code,
                    coded_error_message(code, &message),
                ))
            } else {
                let code = DispatchFailureCode::HttpUnexpectedStatus;
                Err(DispatchSendError::retryable(
                    code,
                    coded_error_message(code, &message),
                ))
            }
        }
    }

    async fn mark_dispatch_sent(&self, job_id: i64) -> Result<(), AppError> {
        let callback_wait_secs = self.config.ai_judge.dispatch_callback_wait_secs.max(1);
        sqlx::query(
            r#"
            UPDATE judge_jobs
            SET started_at = COALESCE(started_at, NOW()),
                error_message = NULL,
                dispatch_locked_until = NOW() + ($2::bigint * INTERVAL '1 second'),
                updated_at = NOW()
            WHERE id = $1 AND status = 'running'
            "#,
        )
        .bind(job_id)
        .bind(callback_wait_secs)
        .execute(&self.pool)
        .await?;
        Ok(())
    }

    async fn mark_dispatch_failure(
        &self,
        job_id: i64,
        dispatch_attempts: i32,
        err_msg: &str,
    ) -> Result<bool, AppError> {
        let err_msg = sanitize_error_message(err_msg);
        let max_attempts = self.config.ai_judge.dispatch_max_attempts.max(1);
        if dispatch_attempts >= max_attempts {
            sqlx::query(
                r#"
                UPDATE judge_jobs
                SET status = 'failed',
                    error_message = $2,
                    finished_at = NOW(),
                    dispatch_locked_until = NULL,
                    updated_at = NOW()
                WHERE id = $1
                  AND status = 'running'
                "#,
            )
            .bind(job_id)
            .bind(&err_msg)
            .execute(&self.pool)
            .await?;
            warn!(
                job_id,
                "judge dispatch failed and marked job as failed: {}", err_msg
            );
            Ok(true)
        } else {
            let retry_lock_secs = calc_retry_lock_secs(
                job_id,
                dispatch_attempts,
                self.config.ai_judge.dispatch_lock_secs,
                self.config.ai_judge.dispatch_retry_backoff_max_multiplier,
                self.config.ai_judge.dispatch_retry_jitter_ratio,
            );
            sqlx::query(
                r#"
                UPDATE judge_jobs
                SET error_message = $2,
                    dispatch_locked_until = NOW() + ($3::bigint * INTERVAL '1 second'),
                    updated_at = NOW()
                WHERE id = $1
                  AND status = 'running'
                "#,
            )
            .bind(job_id)
            .bind(&err_msg)
            .bind(retry_lock_secs)
            .execute(&self.pool)
            .await?;
            warn!(
                job_id,
                retry_lock_secs, "judge dispatch failed, waiting next retry: {}", err_msg
            );
            Ok(false)
        }
    }

    async fn mark_dispatch_terminal_failure(
        &self,
        job_id: i64,
        err_msg: &str,
    ) -> Result<bool, AppError> {
        let err_msg = sanitize_error_message(err_msg);
        let rows_affected = sqlx::query(
            r#"
            UPDATE judge_jobs
            SET status = 'failed',
                error_message = $2,
                finished_at = NOW(),
                dispatch_locked_until = NULL,
                updated_at = NOW()
            WHERE id = $1
              AND status = 'running'
            "#,
        )
        .bind(job_id)
        .bind(&err_msg)
        .execute(&self.pool)
        .await?
        .rows_affected();
        if rows_affected > 0 {
            warn!(
                job_id,
                "judge dispatch terminal failure, job marked failed: {}", err_msg
            );
            Ok(true)
        } else {
            Ok(false)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use anyhow::Result;
    use axum::{routing::post, Json, Router};
    use chrono::Duration;
    use reqwest::StatusCode;
    use serde_json::Value;
    use std::sync::{
        atomic::{AtomicUsize, Ordering},
        Arc,
    };
    use tokio::net::TcpListener;

    async fn seed_topic_and_session(state: &AppState, ws_id: i64, status: &str) -> Result<i64> {
        let topic_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO debate_topics(ws_id, title, description, category, stance_pro, stance_con, is_active, created_by)
            VALUES ($1, 'topic-dispatch', 'desc', 'game', 'pro', 'con', true, 1)
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

    async fn seed_running_job(
        state: &AppState,
        session_id: i64,
        attempts: i32,
        lock_secs_offset: Option<i64>,
    ) -> Result<i64> {
        let dispatch_locked_until =
            lock_secs_offset.map(|secs| Utc::now() + Duration::seconds(secs));
        let job_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO judge_jobs(
                ws_id, session_id, requested_by, status, style_mode, requested_at, dispatch_attempts, dispatch_locked_until
            )
            VALUES ($1, $2, $3, 'running', 'rational', NOW(), $4, $5)
            RETURNING id
            "#,
        )
        .bind(1_i64)
        .bind(session_id)
        .bind(1_i64)
        .bind(attempts)
        .bind(dispatch_locked_until)
        .fetch_one(&state.pool)
        .await?;
        Ok(job_id.0)
    }

    async fn spawn_mock_dispatch_server() -> Result<(String, Arc<AtomicUsize>)> {
        let hit_count = Arc::new(AtomicUsize::new(0));
        let app = {
            let hit_count = hit_count.clone();
            Router::new().route(
                "/internal/judge/dispatch",
                post(move |Json(_payload): Json<Value>| {
                    let hit_count = hit_count.clone();
                    async move {
                        hit_count.fetch_add(1, Ordering::SeqCst);
                        (
                            axum::http::StatusCode::OK,
                            Json(serde_json::json!({"ok": true})),
                        )
                    }
                }),
            )
        };
        let listener = TcpListener::bind("127.0.0.1:0").await?;
        let addr = listener.local_addr()?;
        tokio::spawn(async move {
            let _ = axum::serve(listener, app).await;
        });
        Ok((format!("http://{}", addr), hit_count))
    }

    async fn spawn_mock_dispatch_server_with_json(response: Value) -> Result<String> {
        let app = Router::new().route(
            "/internal/judge/dispatch",
            post(move |Json(_payload): Json<Value>| {
                let response = response.clone();
                async move { (axum::http::StatusCode::OK, Json(response)) }
            }),
        );
        let listener = TcpListener::bind("127.0.0.1:0").await?;
        let addr = listener.local_addr()?;
        tokio::spawn(async move {
            let _ = axum::serve(listener, app).await;
        });
        Ok(format!("http://{}", addr))
    }

    async fn spawn_mock_dispatch_server_with_status(status: StatusCode) -> Result<String> {
        let app = Router::new().route(
            "/internal/judge/dispatch",
            post(move |Json(_payload): Json<Value>| async move {
                (
                    axum::http::StatusCode::from_u16(status.as_u16()).expect("valid status"),
                    Json(serde_json::json!({"error":"mock"})),
                )
            }),
        );
        let listener = TcpListener::bind("127.0.0.1:0").await?;
        let addr = listener.local_addr()?;
        tokio::spawn(async move {
            let _ = axum::serve(listener, app).await;
        });
        Ok(format!("http://{}", addr))
    }

    async fn seed_messages(state: &AppState, session_id: i64, count: i64) -> Result<()> {
        for idx in 0..count {
            sqlx::query(
                r#"
                INSERT INTO session_messages(ws_id, session_id, user_id, side, content)
                VALUES (1, $1, 1, 'pro', $2)
                "#,
            )
            .bind(session_id)
            .bind(format!("msg-{idx}"))
            .execute(&state.pool)
            .await?;
        }
        Ok(())
    }

    #[tokio::test]
    async fn load_dispatch_payload_should_include_recent_messages_ordered_asc() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id = seed_topic_and_session(&state, 1, "judging").await?;
        let job_id = seed_running_job(&state, session_id, 0, None).await?;
        seed_messages(&state, session_id, 3).await?;

        let job = PendingDispatchJob {
            id: job_id,
            ws_id: 1,
            session_id,
            requested_by: 1,
            style_mode: "rational".to_string(),
            rejudge_triggered: false,
            requested_at: Utc::now(),
            dispatch_attempts: 1,
        };
        let payload = state.load_dispatch_payload(&job).await?;
        assert_eq!(payload.job.job_id, job_id as u64);
        assert_eq!(payload.topic.title, "topic-dispatch");
        assert_eq!(payload.messages.len(), 3);
        assert_eq!(payload.messages[0].content, "msg-0");
        assert_eq!(payload.messages[2].content, "msg-2");
        Ok(())
    }

    #[tokio::test]
    async fn dispatch_pending_judge_jobs_once_should_mark_failed_after_max_attempts() -> Result<()>
    {
        let (_tdb, mut state) = AppState::new_for_test().await?;
        let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
        inner.config.ai_judge.dispatch_max_attempts = 1;
        inner.config.ai_judge.dispatch_timeout_ms = 200;
        inner.config.ai_judge.dispatch_lock_secs = 1;
        inner.config.ai_judge.dispatch_batch_size = 20;
        inner.config.ai_judge.service_base_url = "http://127.0.0.1:9".to_string();
        inner.config.ai_judge.dispatch_path = "/internal/judge/dispatch".to_string();

        let session_id = seed_topic_and_session(&state, 1, "judging").await?;
        let job_id = seed_running_job(&state, session_id, 0, None).await?;

        let tick = state.dispatch_pending_judge_jobs_once().await?;
        assert_eq!(tick.claimed, 1);
        assert_eq!(tick.failed, 1);
        assert_eq!(tick.marked_failed, 1);

        let row: (String,) = sqlx::query_as(
            r#"
            SELECT status
            FROM judge_jobs
            WHERE id = $1
            "#,
        )
        .bind(job_id)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(row.0, "failed");
        assert_eq!(tick.timed_out_failed, 0);
        Ok(())
    }

    #[tokio::test]
    async fn dispatch_pending_judge_jobs_once_should_not_redispatch_within_callback_wait_window(
    ) -> Result<()> {
        let (_tdb, mut state) = AppState::new_for_test().await?;
        let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
        let (service_base_url, hit_count) = spawn_mock_dispatch_server().await?;
        inner.config.ai_judge.dispatch_max_attempts = 3;
        inner.config.ai_judge.dispatch_timeout_ms = 1_000;
        inner.config.ai_judge.dispatch_lock_secs = 1;
        inner.config.ai_judge.dispatch_batch_size = 20;
        inner.config.ai_judge.dispatch_callback_wait_secs = 120;
        inner.config.ai_judge.service_base_url = service_base_url;
        inner.config.ai_judge.dispatch_path = "/internal/judge/dispatch".to_string();

        let session_id = seed_topic_and_session(&state, 1, "judging").await?;
        seed_messages(&state, session_id, 2).await?;
        let job_id = seed_running_job(&state, session_id, 0, None).await?;

        let first = state.dispatch_pending_judge_jobs_once().await?;
        assert_eq!(first.claimed, 1);
        assert_eq!(first.dispatched, 1);
        assert_eq!(hit_count.load(Ordering::SeqCst), 1);

        let second = state.dispatch_pending_judge_jobs_once().await?;
        assert_eq!(second.claimed, 0);
        assert_eq!(second.dispatched, 0);
        assert_eq!(hit_count.load(Ordering::SeqCst), 1);

        let lock_row: (Option<DateTime<Utc>>,) = sqlx::query_as(
            r#"
            SELECT dispatch_locked_until
            FROM judge_jobs
            WHERE id = $1
            "#,
        )
        .bind(job_id)
        .fetch_one(&state.pool)
        .await?;
        assert!(lock_row.0.is_some());
        Ok(())
    }

    #[tokio::test]
    async fn dispatch_pending_judge_jobs_once_should_mark_timeout_failed_when_attempts_exhausted(
    ) -> Result<()> {
        let (_tdb, mut state) = AppState::new_for_test().await?;
        let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
        inner.config.ai_judge.dispatch_max_attempts = 2;
        inner.config.ai_judge.dispatch_timeout_ms = 200;
        inner.config.ai_judge.dispatch_lock_secs = 1;
        inner.config.ai_judge.dispatch_batch_size = 20;
        inner.config.ai_judge.dispatch_callback_wait_secs = 60;

        let session_id = seed_topic_and_session(&state, 1, "judging").await?;
        let job_id = seed_running_job(&state, session_id, 2, Some(-10)).await?;

        let tick = state.dispatch_pending_judge_jobs_once().await?;
        assert_eq!(tick.claimed, 0);
        assert_eq!(tick.timed_out_failed, 1);

        let row: (String, Option<String>) = sqlx::query_as(
            r#"
            SELECT status, error_message
            FROM judge_jobs
            WHERE id = $1
            "#,
        )
        .bind(job_id)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(row.0, "failed");
        assert!(row
            .1
            .unwrap_or_default()
            .contains("dispatch callback timeout after 2 attempts"));
        Ok(())
    }

    #[tokio::test]
    async fn dispatch_pending_judge_jobs_once_should_mark_failed_when_response_rejected(
    ) -> Result<()> {
        let (_tdb, mut state) = AppState::new_for_test().await?;
        let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
        inner.config.ai_judge.dispatch_max_attempts = 1;
        inner.config.ai_judge.dispatch_timeout_ms = 1_000;
        inner.config.ai_judge.dispatch_lock_secs = 1;
        inner.config.ai_judge.dispatch_batch_size = 20;
        inner.config.ai_judge.service_base_url =
            spawn_mock_dispatch_server_with_json(serde_json::json!({
                "accepted": false,
                "status": "marked_failed"
            }))
            .await?;
        inner.config.ai_judge.dispatch_path = "/internal/judge/dispatch".to_string();

        let session_id = seed_topic_and_session(&state, 1, "judging").await?;
        let job_id = seed_running_job(&state, session_id, 0, None).await?;

        let tick = state.dispatch_pending_judge_jobs_once().await?;
        assert_eq!(tick.claimed, 1);
        assert_eq!(tick.dispatched, 0);
        assert_eq!(tick.failed, 1);
        assert_eq!(tick.marked_failed, 1);
        assert_eq!(tick.terminal_failed, 1);
        assert_eq!(tick.retryable_failed, 0);
        assert_eq!(tick.failed_contract, 1);

        let row: (String, Option<String>) = sqlx::query_as(
            r#"
            SELECT status, error_message
            FROM judge_jobs
            WHERE id = $1
            "#,
        )
        .bind(job_id)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(row.0, "failed");
        assert!(row.1.unwrap_or_default().contains("accepted=false"));
        Ok(())
    }

    #[tokio::test]
    async fn dispatch_pending_judge_jobs_once_should_mark_terminal_failed_immediately_when_response_rejected_with_retries_left(
    ) -> Result<()> {
        let (_tdb, mut state) = AppState::new_for_test().await?;
        let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
        inner.config.ai_judge.dispatch_max_attempts = 3;
        inner.config.ai_judge.dispatch_timeout_ms = 1_000;
        inner.config.ai_judge.dispatch_lock_secs = 1;
        inner.config.ai_judge.dispatch_batch_size = 20;
        inner.config.ai_judge.service_base_url =
            spawn_mock_dispatch_server_with_json(serde_json::json!({
                "accepted": false,
                "status": "marked_failed"
            }))
            .await?;
        inner.config.ai_judge.dispatch_path = "/internal/judge/dispatch".to_string();

        let session_id = seed_topic_and_session(&state, 1, "judging").await?;
        let job_id = seed_running_job(&state, session_id, 0, None).await?;

        let tick = state.dispatch_pending_judge_jobs_once().await?;
        assert_eq!(tick.claimed, 1);
        assert_eq!(tick.dispatched, 0);
        assert_eq!(tick.failed, 1);
        assert_eq!(tick.marked_failed, 1);
        assert_eq!(tick.terminal_failed, 1);
        assert_eq!(tick.retryable_failed, 0);
        assert_eq!(tick.failed_contract, 1);

        let row: (String, i32) = sqlx::query_as(
            r#"
            SELECT status, dispatch_attempts
            FROM judge_jobs
            WHERE id = $1
            "#,
        )
        .bind(job_id)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(row.0, "failed");
        assert_eq!(row.1, 1);
        Ok(())
    }

    #[tokio::test]
    async fn dispatch_pending_judge_jobs_once_should_mark_failed_when_response_job_id_mismatch(
    ) -> Result<()> {
        let (_tdb, mut state) = AppState::new_for_test().await?;
        let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
        inner.config.ai_judge.dispatch_max_attempts = 1;
        inner.config.ai_judge.dispatch_timeout_ms = 1_000;
        inner.config.ai_judge.dispatch_lock_secs = 1;
        inner.config.ai_judge.dispatch_batch_size = 20;
        inner.config.ai_judge.service_base_url =
            spawn_mock_dispatch_server_with_json(serde_json::json!({
                "accepted": true,
                "jobId": 999999_u64
            }))
            .await?;
        inner.config.ai_judge.dispatch_path = "/internal/judge/dispatch".to_string();

        let session_id = seed_topic_and_session(&state, 1, "judging").await?;
        let job_id = seed_running_job(&state, session_id, 0, None).await?;

        let tick = state.dispatch_pending_judge_jobs_once().await?;
        assert_eq!(tick.claimed, 1);
        assert_eq!(tick.dispatched, 0);
        assert_eq!(tick.failed, 1);
        assert_eq!(tick.marked_failed, 1);
        assert_eq!(tick.terminal_failed, 1);
        assert_eq!(tick.failed_contract, 1);

        let row: (String, Option<String>) = sqlx::query_as(
            r#"
            SELECT status, error_message
            FROM judge_jobs
            WHERE id = $1
            "#,
        )
        .bind(job_id)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(row.0, "failed");
        assert!(row.1.unwrap_or_default().contains("job_id mismatch"));
        Ok(())
    }

    #[tokio::test]
    async fn dispatch_pending_judge_jobs_once_should_mark_terminal_failed_on_http_400_even_with_retries_left(
    ) -> Result<()> {
        let (_tdb, mut state) = AppState::new_for_test().await?;
        let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
        inner.config.ai_judge.dispatch_max_attempts = 3;
        inner.config.ai_judge.dispatch_timeout_ms = 1_000;
        inner.config.ai_judge.dispatch_lock_secs = 1;
        inner.config.ai_judge.dispatch_batch_size = 20;
        inner.config.ai_judge.service_base_url =
            spawn_mock_dispatch_server_with_status(StatusCode::BAD_REQUEST).await?;
        inner.config.ai_judge.dispatch_path = "/internal/judge/dispatch".to_string();

        let session_id = seed_topic_and_session(&state, 1, "judging").await?;
        let job_id = seed_running_job(&state, session_id, 0, None).await?;

        let tick = state.dispatch_pending_judge_jobs_once().await?;
        assert_eq!(tick.claimed, 1);
        assert_eq!(tick.dispatched, 0);
        assert_eq!(tick.failed, 1);
        assert_eq!(tick.marked_failed, 1);
        assert_eq!(tick.terminal_failed, 1);
        assert_eq!(tick.failed_http_4xx, 1);

        let row: (String, Option<String>) = sqlx::query_as(
            r#"
            SELECT status, error_message
            FROM judge_jobs
            WHERE id = $1
            "#,
        )
        .bind(job_id)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(row.0, "failed");
        assert!(row.1.unwrap_or_default().contains("status=400"));
        Ok(())
    }

    #[tokio::test]
    async fn dispatch_pending_judge_jobs_once_should_keep_running_on_http_500_when_retries_left(
    ) -> Result<()> {
        let (_tdb, mut state) = AppState::new_for_test().await?;
        let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
        inner.config.ai_judge.dispatch_max_attempts = 3;
        inner.config.ai_judge.dispatch_timeout_ms = 1_000;
        inner.config.ai_judge.dispatch_lock_secs = 1;
        inner.config.ai_judge.dispatch_batch_size = 20;
        inner.config.ai_judge.service_base_url =
            spawn_mock_dispatch_server_with_status(StatusCode::INTERNAL_SERVER_ERROR).await?;
        inner.config.ai_judge.dispatch_path = "/internal/judge/dispatch".to_string();

        let session_id = seed_topic_and_session(&state, 1, "judging").await?;
        let job_id = seed_running_job(&state, session_id, 0, None).await?;

        let tick = state.dispatch_pending_judge_jobs_once().await?;
        assert_eq!(tick.claimed, 1);
        assert_eq!(tick.dispatched, 0);
        assert_eq!(tick.failed, 1);
        assert_eq!(tick.marked_failed, 0);
        assert_eq!(tick.retryable_failed, 1);
        assert_eq!(tick.failed_http_5xx, 1);

        let row: (String, i32, Option<String>) = sqlx::query_as(
            r#"
            SELECT status, dispatch_attempts, error_message
            FROM judge_jobs
            WHERE id = $1
            "#,
        )
        .bind(job_id)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(row.0, "running");
        assert_eq!(row.1, 1);
        assert!(row.2.unwrap_or_default().contains("status=500"));
        Ok(())
    }

    #[tokio::test]
    async fn dispatch_pending_judge_jobs_once_should_keep_running_on_http_429_when_retries_left(
    ) -> Result<()> {
        let (_tdb, mut state) = AppState::new_for_test().await?;
        let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
        inner.config.ai_judge.dispatch_max_attempts = 3;
        inner.config.ai_judge.dispatch_timeout_ms = 1_000;
        inner.config.ai_judge.dispatch_lock_secs = 1;
        inner.config.ai_judge.dispatch_batch_size = 20;
        inner.config.ai_judge.service_base_url =
            spawn_mock_dispatch_server_with_status(StatusCode::TOO_MANY_REQUESTS).await?;
        inner.config.ai_judge.dispatch_path = "/internal/judge/dispatch".to_string();

        let session_id = seed_topic_and_session(&state, 1, "judging").await?;
        let job_id = seed_running_job(&state, session_id, 0, None).await?;

        let tick = state.dispatch_pending_judge_jobs_once().await?;
        assert_eq!(tick.claimed, 1);
        assert_eq!(tick.dispatched, 0);
        assert_eq!(tick.failed, 1);
        assert_eq!(tick.marked_failed, 0);
        assert_eq!(tick.retryable_failed, 1);
        assert_eq!(tick.failed_http_429, 1);

        let row: (String, i32, Option<String>) = sqlx::query_as(
            r#"
            SELECT status, dispatch_attempts, error_message
            FROM judge_jobs
            WHERE id = $1
            "#,
        )
        .bind(job_id)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(row.0, "running");
        assert_eq!(row.1, 1);
        assert!(row.2.unwrap_or_default().contains("status=429"));
        Ok(())
    }

    #[tokio::test]
    async fn dispatch_pending_judge_jobs_once_should_count_failed_internal_when_payload_loading_fails(
    ) -> Result<()> {
        let (_tdb, mut state) = AppState::new_for_test().await?;
        let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
        inner.config.ai_judge.dispatch_max_attempts = 1;
        inner.config.ai_judge.dispatch_timeout_ms = 1_000;
        inner.config.ai_judge.dispatch_lock_secs = 1;
        inner.config.ai_judge.dispatch_batch_size = 20;
        inner.config.ai_judge.service_base_url = "http://127.0.0.1:9".to_string();
        inner.config.ai_judge.dispatch_path = "/internal/judge/dispatch".to_string();

        let session_id = seed_topic_and_session(&state, 2, "judging").await?;
        let job_id = seed_running_job(&state, session_id, 0, None).await?;

        let tick = state.dispatch_pending_judge_jobs_once().await?;
        assert_eq!(tick.claimed, 1);
        assert_eq!(tick.dispatched, 0);
        assert_eq!(tick.failed, 1);
        assert_eq!(tick.marked_failed, 1);
        assert_eq!(tick.retryable_failed, 1);
        assert_eq!(tick.failed_internal, 1);

        let row: (String, Option<String>) = sqlx::query_as(
            r#"
            SELECT status, error_message
            FROM judge_jobs
            WHERE id = $1
            "#,
        )
        .bind(job_id)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(row.0, "failed");
        assert!(row.1.unwrap_or_default().contains("[payload_build_failed]"));
        Ok(())
    }

    #[test]
    fn build_dispatch_url_should_join_base_and_path() {
        assert_eq!(
            build_dispatch_url("http://127.0.0.1:8787/", "/internal/judge/dispatch"),
            "http://127.0.0.1:8787/internal/judge/dispatch"
        );
        assert_eq!(
            build_dispatch_url("http://127.0.0.1:8787", "internal/judge/dispatch"),
            "http://127.0.0.1:8787/internal/judge/dispatch"
        );
    }

    #[test]
    fn validate_dispatch_response_should_allow_legacy_or_empty_body() {
        assert!(validate_dispatch_response("", 1).is_ok());
        assert!(validate_dispatch_response("{\"ok\":true}", 1).is_ok());
        assert!(validate_dispatch_response("not-json", 1).is_ok());
    }

    #[test]
    fn validate_dispatch_response_should_reject_accepted_false() {
        let err = validate_dispatch_response(r#"{"accepted":false,"status":"marked_failed"}"#, 42)
            .expect_err("should reject");
        assert!(err.to_string().contains("accepted=false"));
    }

    #[test]
    fn validate_dispatch_response_should_reject_job_id_mismatch() {
        let err = validate_dispatch_response(r#"{"accepted":true,"jobId":99}"#, 42)
            .expect_err("should reject mismatch");
        assert!(err.to_string().contains("job_id mismatch"));
    }

    #[test]
    fn calc_retry_lock_secs_should_apply_exponential_backoff_with_cap() {
        assert_eq!(calc_retry_lock_secs(1, 1, 2, 8, 0), 2);
        assert_eq!(calc_retry_lock_secs(1, 2, 2, 8, 0), 4);
        assert_eq!(calc_retry_lock_secs(1, 3, 2, 8, 0), 8);
        assert_eq!(calc_retry_lock_secs(1, 4, 2, 8, 0), 16);
        assert_eq!(calc_retry_lock_secs(1, 9, 2, 8, 0), 16);
    }

    #[test]
    fn calc_retry_lock_secs_should_apply_deterministic_jitter_within_bounds() {
        let base = calc_retry_lock_secs(42, 4, 10, 8, 0);
        let jittered = calc_retry_lock_secs(42, 4, 10, 8, 20);
        let jittered_repeat = calc_retry_lock_secs(42, 4, 10, 8, 20);
        let window = base * 20 / 100;
        assert!(jittered >= base - window);
        assert!(jittered <= base + window);
        assert_eq!(jittered, jittered_repeat);
    }
}
