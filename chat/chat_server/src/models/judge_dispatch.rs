use crate::{AppError, AppState};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::FromRow;
use std::sync::atomic::{AtomicU64, Ordering};
use utoipa::ToSchema;

mod dispatch_worker;

const DISPATCH_ERROR_MAX_LEN: usize = 1000;
const PHASE_DISPATCH_PATH: &str = "/internal/judge/v3/phase/dispatch";
const PHASE_DISPATCH_SCOPE_ID: u64 = 1;
const FINAL_DISPATCH_PATH: &str = "/internal/judge/v3/final/dispatch";
const FINAL_DISPATCH_SCOPE_ID: u64 = 1;

#[derive(Debug, Clone)]
pub(crate) struct JudgeDispatchTrigger {
    pub job_id: i64,
    pub source: &'static str,
}

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
    pub failed_http_unexpected: usize,
    pub failed_network: usize,
    pub failed_internal: usize,
}

#[derive(Debug, Default, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgePhaseDispatchTickReport {
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
    pub failed_http_unexpected: usize,
    pub failed_network: usize,
    pub failed_internal: usize,
}

#[derive(Debug, Default, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct JudgeFinalDispatchTickReport {
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
    pub failed_http_unexpected: usize,
    pub failed_network: usize,
    pub failed_internal: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct GetJudgeDispatchMetricsOutput {
    pub tick_success_total: u64,
    pub tick_error_total: u64,
    pub phase_tick_success_total: u64,
    pub final_tick_success_total: u64,
    pub trigger_polling_total: u64,
    pub trigger_event_total: u64,
    pub claimed_total: u64,
    pub dispatched_total: u64,
    pub phase_dispatched_total: u64,
    pub final_dispatched_total: u64,
    pub failed_total: u64,
    pub phase_failed_total: u64,
    pub final_failed_total: u64,
    pub marked_failed_total: u64,
    pub timed_out_failed_total: u64,
    pub terminal_failed_total: u64,
    pub retryable_failed_total: u64,
    pub failed_contract_total: u64,
    pub failed_http_4xx_total: u64,
    pub failed_http_429_total: u64,
    pub failed_http_5xx_total: u64,
    pub failed_http_unexpected_total: u64,
    pub failed_network_total: u64,
    pub failed_internal_total: u64,
    pub queued_phase_jobs: u64,
    pub queued_final_jobs: u64,
    pub oldest_phase_queued_age_secs: u64,
    pub oldest_final_queued_age_secs: u64,
    pub dispatch_success_rate_pct: f64,
    pub retryable_failure_share_pct: f64,
    pub timeout_failure_share_pct: f64,
}

#[derive(Debug, Default)]
pub(crate) struct AiJudgeDispatchMetrics {
    tick_success_total: AtomicU64,
    tick_error_total: AtomicU64,
    phase_tick_success_total: AtomicU64,
    final_tick_success_total: AtomicU64,
    trigger_polling_total: AtomicU64,
    trigger_event_total: AtomicU64,
    claimed_total: AtomicU64,
    dispatched_total: AtomicU64,
    phase_dispatched_total: AtomicU64,
    final_dispatched_total: AtomicU64,
    failed_total: AtomicU64,
    phase_failed_total: AtomicU64,
    final_failed_total: AtomicU64,
    marked_failed_total: AtomicU64,
    timed_out_failed_total: AtomicU64,
    terminal_failed_total: AtomicU64,
    retryable_failed_total: AtomicU64,
    failed_contract_total: AtomicU64,
    failed_http_4xx_total: AtomicU64,
    failed_http_429_total: AtomicU64,
    failed_http_5xx_total: AtomicU64,
    failed_http_unexpected_total: AtomicU64,
    failed_network_total: AtomicU64,
    failed_internal_total: AtomicU64,
    queued_phase_jobs: AtomicU64,
    queued_final_jobs: AtomicU64,
    oldest_phase_queued_age_secs: AtomicU64,
    oldest_final_queued_age_secs: AtomicU64,
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
        self.failed_http_unexpected_total
            .fetch_add(report.failed_http_unexpected as u64, Ordering::Relaxed);
        self.failed_network_total
            .fetch_add(report.failed_network as u64, Ordering::Relaxed);
        self.failed_internal_total
            .fetch_add(report.failed_internal as u64, Ordering::Relaxed);
    }

    pub(crate) fn observe_phase_tick_success(&self, report: &JudgePhaseDispatchTickReport) {
        self.phase_tick_success_total
            .fetch_add(1, Ordering::Relaxed);
        self.phase_dispatched_total
            .fetch_add(report.dispatched as u64, Ordering::Relaxed);
        self.phase_failed_total
            .fetch_add(report.failed as u64, Ordering::Relaxed);
    }

    pub(crate) fn observe_final_tick_success(&self, report: &JudgeFinalDispatchTickReport) {
        self.final_tick_success_total
            .fetch_add(1, Ordering::Relaxed);
        self.final_dispatched_total
            .fetch_add(report.dispatched as u64, Ordering::Relaxed);
        self.final_failed_total
            .fetch_add(report.failed as u64, Ordering::Relaxed);
    }

    pub(crate) fn observe_tick_error(&self) {
        self.tick_error_total.fetch_add(1, Ordering::Relaxed);
    }

    pub(crate) fn observe_tick_trigger(&self, trigger_source: &str) {
        if trigger_source == "polling" {
            self.trigger_polling_total.fetch_add(1, Ordering::Relaxed);
            return;
        }
        self.trigger_event_total.fetch_add(1, Ordering::Relaxed);
    }

    pub(crate) fn observe_backlog(
        &self,
        queued_phase_jobs: u64,
        queued_final_jobs: u64,
        oldest_phase_queued_age_secs: u64,
        oldest_final_queued_age_secs: u64,
    ) {
        self.queued_phase_jobs
            .store(queued_phase_jobs, Ordering::Relaxed);
        self.queued_final_jobs
            .store(queued_final_jobs, Ordering::Relaxed);
        self.oldest_phase_queued_age_secs
            .store(oldest_phase_queued_age_secs, Ordering::Relaxed);
        self.oldest_final_queued_age_secs
            .store(oldest_final_queued_age_secs, Ordering::Relaxed);
    }

    pub(crate) fn snapshot(&self) -> GetJudgeDispatchMetricsOutput {
        let tick_success_total = self.tick_success_total.load(Ordering::Relaxed);
        let tick_error_total = self.tick_error_total.load(Ordering::Relaxed);
        let phase_tick_success_total = self.phase_tick_success_total.load(Ordering::Relaxed);
        let final_tick_success_total = self.final_tick_success_total.load(Ordering::Relaxed);
        let trigger_polling_total = self.trigger_polling_total.load(Ordering::Relaxed);
        let trigger_event_total = self.trigger_event_total.load(Ordering::Relaxed);
        let claimed_total = self.claimed_total.load(Ordering::Relaxed);
        let dispatched_total = self.dispatched_total.load(Ordering::Relaxed);
        let phase_dispatched_total = self.phase_dispatched_total.load(Ordering::Relaxed);
        let final_dispatched_total = self.final_dispatched_total.load(Ordering::Relaxed);
        let failed_total = self.failed_total.load(Ordering::Relaxed);
        let phase_failed_total = self.phase_failed_total.load(Ordering::Relaxed);
        let final_failed_total = self.final_failed_total.load(Ordering::Relaxed);
        let marked_failed_total = self.marked_failed_total.load(Ordering::Relaxed);
        let timed_out_failed_total = self.timed_out_failed_total.load(Ordering::Relaxed);
        let terminal_failed_total = self.terminal_failed_total.load(Ordering::Relaxed);
        let retryable_failed_total = self.retryable_failed_total.load(Ordering::Relaxed);
        let failed_contract_total = self.failed_contract_total.load(Ordering::Relaxed);
        let failed_http_4xx_total = self.failed_http_4xx_total.load(Ordering::Relaxed);
        let failed_http_429_total = self.failed_http_429_total.load(Ordering::Relaxed);
        let failed_http_5xx_total = self.failed_http_5xx_total.load(Ordering::Relaxed);
        let failed_http_unexpected_total =
            self.failed_http_unexpected_total.load(Ordering::Relaxed);
        let failed_network_total = self.failed_network_total.load(Ordering::Relaxed);
        let failed_internal_total = self.failed_internal_total.load(Ordering::Relaxed);
        let queued_phase_jobs = self.queued_phase_jobs.load(Ordering::Relaxed);
        let queued_final_jobs = self.queued_final_jobs.load(Ordering::Relaxed);
        let oldest_phase_queued_age_secs =
            self.oldest_phase_queued_age_secs.load(Ordering::Relaxed);
        let oldest_final_queued_age_secs =
            self.oldest_final_queued_age_secs.load(Ordering::Relaxed);

        let dispatch_success_rate_pct = ratio_pct(dispatched_total, claimed_total);
        let retryable_failure_share_pct = ratio_pct(retryable_failed_total, failed_total);
        let timeout_failure_share_pct = ratio_pct(timed_out_failed_total, failed_network_total);

        GetJudgeDispatchMetricsOutput {
            tick_success_total,
            tick_error_total,
            phase_tick_success_total,
            final_tick_success_total,
            trigger_polling_total,
            trigger_event_total,
            claimed_total,
            dispatched_total,
            phase_dispatched_total,
            final_dispatched_total,
            failed_total,
            phase_failed_total,
            final_failed_total,
            marked_failed_total,
            timed_out_failed_total,
            terminal_failed_total,
            retryable_failed_total,
            failed_contract_total,
            failed_http_4xx_total,
            failed_http_429_total,
            failed_http_5xx_total,
            failed_http_unexpected_total,
            failed_network_total,
            failed_internal_total,
            queued_phase_jobs,
            queued_final_jobs,
            oldest_phase_queued_age_secs,
            oldest_final_queued_age_secs,
            dispatch_success_rate_pct,
            retryable_failure_share_pct,
            timeout_failure_share_pct,
        }
    }
}

fn ratio_pct(numerator: u64, denominator: u64) -> f64 {
    if denominator == 0 {
        return 0.0;
    }
    (numerator as f64 * 100.0) / denominator as f64
}

#[derive(Debug, Clone, FromRow)]
struct PendingPhaseDispatchJob {
    id: i64,
    session_id: i64,
    phase_no: i32,
    message_start_id: i64,
    message_end_id: i64,
    message_count: i32,
    trace_id: String,
    idempotency_key: String,
    rubric_version: String,
    judge_policy_version: String,
    topic_domain: String,
    retrieval_profile: String,
    dispatch_attempts: i32,
}

#[derive(Debug, Clone, FromRow)]
struct PendingFinalDispatchJob {
    id: i64,
    session_id: i64,
    phase_start_no: i32,
    phase_end_no: i32,
    trace_id: String,
    idempotency_key: String,
    rubric_version: String,
    judge_policy_version: String,
    topic_domain: String,
    dispatch_attempts: i32,
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
struct AiJudgePhaseDispatchRequest {
    job_id: u64,
    scope_id: u64,
    session_id: u64,
    phase_no: i32,
    message_start_id: u64,
    message_end_id: u64,
    message_count: i32,
    messages: Vec<AiJudgeDispatchMessage>,
    rubric_version: String,
    judge_policy_version: String,
    topic_domain: String,
    retrieval_profile: String,
    trace_id: String,
    idempotency_key: String,
}

#[derive(Debug, Clone, Serialize)]
struct AiJudgeFinalDispatchRequest {
    job_id: u64,
    scope_id: u64,
    session_id: u64,
    phase_start_no: i32,
    phase_end_no: i32,
    rubric_version: String,
    judge_policy_version: String,
    topic_domain: String,
    trace_id: String,
    idempotency_key: String,
}

#[derive(Debug, Clone, Serialize)]
struct AiJudgeDispatchMessage {
    message_id: u64,
    speaker_tag: String,
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
    Timeout,
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
            Self::Timeout => "timeout",
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
    InvalidPayload,
    AcceptedFalse { status: String },
    JobIdMismatch { expected: u64, got: u64 },
}

impl std::fmt::Display for DispatchResponseViolation {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::InvalidPayload => write!(f, "dispatch response payload is not valid json"),
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

fn classify_dispatch_send_error_code(is_timeout: bool) -> DispatchFailureCode {
    if is_timeout {
        return DispatchFailureCode::Timeout;
    }
    DispatchFailureCode::NetworkSendFailed
}

fn classify_dispatch_http_status(status: reqwest::StatusCode) -> (DispatchFailureCode, bool) {
    if status == reqwest::StatusCode::TOO_MANY_REQUESTS {
        return (DispatchFailureCode::Http429, false);
    }
    if status.is_client_error() {
        return (DispatchFailureCode::Http4xx, true);
    }
    if status.is_server_error() {
        return (DispatchFailureCode::Http5xx, false);
    }
    (DispatchFailureCode::HttpUnexpectedStatus, false)
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

    let parsed: AiJudgeDispatchResponse =
        serde_json::from_str(trimmed).map_err(|_| DispatchResponseViolation::InvalidPayload)?;

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

    #[test]
    fn classify_dispatch_send_error_code_should_map_timeout_and_network() {
        assert_eq!(
            classify_dispatch_send_error_code(true),
            DispatchFailureCode::Timeout
        );
        assert_eq!(
            classify_dispatch_send_error_code(false),
            DispatchFailureCode::NetworkSendFailed
        );
    }

    #[test]
    fn classify_dispatch_http_status_should_keep_unexpected_separate() {
        assert_eq!(
            classify_dispatch_http_status(reqwest::StatusCode::TOO_MANY_REQUESTS),
            (DispatchFailureCode::Http429, false)
        );
        assert_eq!(
            classify_dispatch_http_status(reqwest::StatusCode::BAD_REQUEST),
            (DispatchFailureCode::Http4xx, true)
        );
        assert_eq!(
            classify_dispatch_http_status(reqwest::StatusCode::INTERNAL_SERVER_ERROR),
            (DispatchFailureCode::Http5xx, false)
        );
        assert_eq!(
            classify_dispatch_http_status(reqwest::StatusCode::CONTINUE),
            (DispatchFailureCode::HttpUnexpectedStatus, false)
        );
    }

    #[test]
    fn observe_tick_success_should_accumulate_timeout_and_unexpected_metrics() {
        let metrics = AiJudgeDispatchMetrics::default();
        metrics.observe_tick_success(&JudgeDispatchTickReport {
            claimed: 3,
            dispatched: 2,
            failed: 1,
            marked_failed: 1,
            timed_out_failed: 1,
            terminal_failed: 0,
            retryable_failed: 1,
            failed_contract: 0,
            failed_http_4xx: 0,
            failed_http_429: 0,
            failed_http_5xx: 0,
            failed_http_unexpected: 1,
            failed_network: 1,
            failed_internal: 0,
        });
        let snapshot = metrics.snapshot();
        assert_eq!(snapshot.tick_success_total, 1);
        assert_eq!(snapshot.claimed_total, 3);
        assert_eq!(snapshot.dispatched_total, 2);
        assert_eq!(snapshot.failed_total, 1);
        assert_eq!(snapshot.timed_out_failed_total, 1);
        assert_eq!(snapshot.failed_http_unexpected_total, 1);
        assert_eq!(snapshot.failed_network_total, 1);
    }

    #[test]
    fn observe_stage_trigger_and_backlog_should_fill_dimension_metrics() {
        let metrics = AiJudgeDispatchMetrics::default();
        metrics.observe_tick_trigger("polling");
        metrics.observe_tick_trigger("event:v3_request");
        metrics.observe_phase_tick_success(&JudgePhaseDispatchTickReport {
            claimed: 1,
            dispatched: 1,
            failed: 0,
            marked_failed: 0,
            timed_out_failed: 0,
            terminal_failed: 0,
            retryable_failed: 0,
            failed_contract: 0,
            failed_http_4xx: 0,
            failed_http_429: 0,
            failed_http_5xx: 0,
            failed_http_unexpected: 0,
            failed_network: 0,
            failed_internal: 0,
        });
        metrics.observe_final_tick_success(&JudgeFinalDispatchTickReport {
            claimed: 1,
            dispatched: 0,
            failed: 1,
            marked_failed: 0,
            timed_out_failed: 0,
            terminal_failed: 0,
            retryable_failed: 1,
            failed_contract: 0,
            failed_http_4xx: 0,
            failed_http_429: 0,
            failed_http_5xx: 0,
            failed_http_unexpected: 0,
            failed_network: 1,
            failed_internal: 0,
        });
        metrics.observe_backlog(9, 4, 30, 11);
        let snapshot = metrics.snapshot();
        assert_eq!(snapshot.trigger_polling_total, 1);
        assert_eq!(snapshot.trigger_event_total, 1);
        assert_eq!(snapshot.phase_tick_success_total, 1);
        assert_eq!(snapshot.final_tick_success_total, 1);
        assert_eq!(snapshot.phase_dispatched_total, 1);
        assert_eq!(snapshot.final_dispatched_total, 0);
        assert_eq!(snapshot.phase_failed_total, 0);
        assert_eq!(snapshot.final_failed_total, 1);
        assert_eq!(snapshot.queued_phase_jobs, 9);
        assert_eq!(snapshot.queued_final_jobs, 4);
        assert_eq!(snapshot.oldest_phase_queued_age_secs, 30);
        assert_eq!(snapshot.oldest_final_queued_age_secs, 11);
    }

    #[test]
    fn snapshot_should_compute_derived_rates() {
        let metrics = AiJudgeDispatchMetrics::default();
        metrics.observe_tick_success(&JudgeDispatchTickReport {
            claimed: 10,
            dispatched: 7,
            failed: 3,
            marked_failed: 0,
            timed_out_failed: 2,
            terminal_failed: 0,
            retryable_failed: 2,
            failed_contract: 0,
            failed_http_4xx: 0,
            failed_http_429: 0,
            failed_http_5xx: 0,
            failed_http_unexpected: 0,
            failed_network: 4,
            failed_internal: 0,
        });
        let snapshot = metrics.snapshot();
        assert_eq!(snapshot.dispatch_success_rate_pct, 70.0);
        assert!((snapshot.retryable_failure_share_pct - 66.66666666666667).abs() < 1e-9);
        assert_eq!(snapshot.timeout_failure_share_pct, 50.0);
    }
}
