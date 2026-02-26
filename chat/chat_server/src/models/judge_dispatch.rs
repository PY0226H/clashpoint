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
mod tests;
