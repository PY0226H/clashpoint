use crate::{AppError, AppState};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::FromRow;
use std::sync::atomic::{AtomicU64, Ordering};
use utoipa::ToSchema;

mod dispatch_worker;

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

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct GetJudgeDispatchMetricsOutput {
    pub tick_success_total: u64,
    pub tick_error_total: u64,
    pub claimed_total: u64,
    pub dispatched_total: u64,
    pub failed_total: u64,
    pub marked_failed_total: u64,
    pub timed_out_failed_total: u64,
    pub terminal_failed_total: u64,
    pub retryable_failed_total: u64,
    pub failed_contract_total: u64,
    pub failed_http_4xx_total: u64,
    pub failed_http_429_total: u64,
    pub failed_http_5xx_total: u64,
    pub failed_network_total: u64,
    pub failed_internal_total: u64,
}

#[derive(Debug, Default)]
pub(crate) struct AiJudgeDispatchMetrics {
    tick_success_total: AtomicU64,
    tick_error_total: AtomicU64,
    claimed_total: AtomicU64,
    dispatched_total: AtomicU64,
    failed_total: AtomicU64,
    marked_failed_total: AtomicU64,
    timed_out_failed_total: AtomicU64,
    terminal_failed_total: AtomicU64,
    retryable_failed_total: AtomicU64,
    failed_contract_total: AtomicU64,
    failed_http_4xx_total: AtomicU64,
    failed_http_429_total: AtomicU64,
    failed_http_5xx_total: AtomicU64,
    failed_network_total: AtomicU64,
    failed_internal_total: AtomicU64,
}

impl AiJudgeDispatchMetrics {
    pub(crate) fn observe_tick_success(&self, report: &JudgeDispatchTickReport) {
        self.tick_success_total.fetch_add(1, Ordering::Relaxed);
        self.claimed_total
            .fetch_add(report.claimed as u64, Ordering::Relaxed);
        self.dispatched_total
            .fetch_add(report.dispatched as u64, Ordering::Relaxed);
        self.failed_total
            .fetch_add(report.failed as u64, Ordering::Relaxed);
        self.marked_failed_total
            .fetch_add(report.marked_failed as u64, Ordering::Relaxed);
        self.timed_out_failed_total
            .fetch_add(report.timed_out_failed as u64, Ordering::Relaxed);
        self.terminal_failed_total
            .fetch_add(report.terminal_failed as u64, Ordering::Relaxed);
        self.retryable_failed_total
            .fetch_add(report.retryable_failed as u64, Ordering::Relaxed);
        self.failed_contract_total
            .fetch_add(report.failed_contract as u64, Ordering::Relaxed);
        self.failed_http_4xx_total
            .fetch_add(report.failed_http_4xx as u64, Ordering::Relaxed);
        self.failed_http_429_total
            .fetch_add(report.failed_http_429 as u64, Ordering::Relaxed);
        self.failed_http_5xx_total
            .fetch_add(report.failed_http_5xx as u64, Ordering::Relaxed);
        self.failed_network_total
            .fetch_add(report.failed_network as u64, Ordering::Relaxed);
        self.failed_internal_total
            .fetch_add(report.failed_internal as u64, Ordering::Relaxed);
    }

    pub(crate) fn observe_tick_error(&self) {
        self.tick_error_total.fetch_add(1, Ordering::Relaxed);
    }

    pub(crate) fn snapshot(&self) -> GetJudgeDispatchMetricsOutput {
        GetJudgeDispatchMetricsOutput {
            tick_success_total: self.tick_success_total.load(Ordering::Relaxed),
            tick_error_total: self.tick_error_total.load(Ordering::Relaxed),
            claimed_total: self.claimed_total.load(Ordering::Relaxed),
            dispatched_total: self.dispatched_total.load(Ordering::Relaxed),
            failed_total: self.failed_total.load(Ordering::Relaxed),
            marked_failed_total: self.marked_failed_total.load(Ordering::Relaxed),
            timed_out_failed_total: self.timed_out_failed_total.load(Ordering::Relaxed),
            terminal_failed_total: self.terminal_failed_total.load(Ordering::Relaxed),
            retryable_failed_total: self.retryable_failed_total.load(Ordering::Relaxed),
            failed_contract_total: self.failed_contract_total.load(Ordering::Relaxed),
            failed_http_4xx_total: self.failed_http_4xx_total.load(Ordering::Relaxed),
            failed_http_429_total: self.failed_http_429_total.load(Ordering::Relaxed),
            failed_http_5xx_total: self.failed_http_5xx_total.load(Ordering::Relaxed),
            failed_network_total: self.failed_network_total.load(Ordering::Relaxed),
            failed_internal_total: self.failed_internal_total.load(Ordering::Relaxed),
        }
    }
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
