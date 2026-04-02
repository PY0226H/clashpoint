use crate::{
    application::request_guard::{
        build_rate_limit_headers, enforce_rate_limit, rate_limit_exceeded_response,
    },
    models::{
        CreateUser, CreateUserWithPhoneAndSessionInput, CreateUserWithPhoneInput, SigninUser,
    },
    redis_store::{RedisStore, SmsCodeVerifyDecision},
    AppError, AppState, ErrorOutput,
};
use axum::{
    extract::{Path, State},
    http::{header, HeaderMap, HeaderValue, StatusCode},
    response::{IntoResponse, Response},
    Extension, Json,
};
use chat_core::{middlewares::AuthVerifyError, JwtError, User};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sha1::{Digest, Sha1};
use sqlx::{Executor, FromRow};
use std::{
    collections::HashMap,
    sync::{
        atomic::{AtomicU64, Ordering},
        LazyLock, Mutex,
    },
};
use utoipa::ToSchema;
use uuid::Uuid;

const SIGNIN_RATE_LIMIT_PER_WINDOW: u64 = 20;
const SIGNIN_RATE_LIMIT_WINDOW_SECS: u64 = 60;
const ACCESS_TOKEN_TTL_SECS: u64 = 60 * 15;
const REFRESH_TOKEN_TTL_SECS: u64 = 60 * 60 * 24 * 30;
const REFRESH_COOKIE_NAME: &str = "refresh_token";
const AUTH_V1_SUNSET_DATE: &str = "Wed, 30 Apr 2026 00:00:00 GMT";
const SMS_CODE_TTL_SECS: u64 = 300;
const SMS_COOLDOWN_SECS: u64 = 60;
const SMS_MAX_FAILED_ATTEMPTS: u64 = 5;
const WECHAT_CHALLENGE_TTL_SECS: u64 = 300;
const WECHAT_BIND_TICKET_TTL_SECS: u64 = 600;
const SMS_PROVIDER_MOCK: &str = "mock";
const WECHAT_PROVIDER: &str = "wechat";
const AUTH_TOKEN_VERSION_INVALIDATION_RETRY_QUEUE_MAX: i64 = 2048;
const AUTH_TOKEN_VERSION_INVALIDATION_RETRY_MAX_ATTEMPTS: i32 = 8;
const AUTH_TOKEN_VERSION_INVALIDATION_RETRY_LOCK_SECS: i64 = 15;
const AUTH_TOKEN_VERSION_INVALIDATION_RETRY_BASE_BACKOFF_MS: u64 = 500;
const AUTH_TOKEN_VERSION_INVALIDATION_RETRY_MAX_BACKOFF_MS: u64 = 30_000;
const AUTH_TOKEN_VERSION_INVALIDATION_ERROR_MAX_LEN: usize = 512;
const AUTH_REFRESH_CONFLICT_GRACE_SECS: i64 = 3;
const AUTH_REFRESH_BLACKLIST_MIN_TTL_SECS: u64 = 1;
pub(crate) const AUTH_REFRESH_OUTBOX_BATCH_SIZE: usize = 64;
const AUTH_REFRESH_OUTBOX_MAX_ATTEMPTS: i32 = 12;
const AUTH_REFRESH_OUTBOX_LOCK_SECS: i64 = 15;
const AUTH_REFRESH_OUTBOX_BASE_BACKOFF_MS: u64 = 500;
const AUTH_REFRESH_OUTBOX_MAX_BACKOFF_MS: u64 = 60_000;
const AUTH_REFRESH_OUTBOX_ERROR_MAX_LEN: usize = 512;

#[derive(Debug, Clone)]
struct SmsFallbackEntry {
    code: String,
    expires_at_epoch_secs: u64,
    cooldown_until_epoch_secs: u64,
    failed_attempts: u64,
}

#[derive(Debug, Clone)]
struct WechatIdentity {
    provider_user_id: String,
    provider_unionid: Option<String>,
    nickname: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct WechatBindTicketPayload {
    provider_user_id: String,
    provider_unionid: Option<String>,
    nickname: Option<String>,
}

struct SmsAuditLogInput<'a> {
    phone_e164: &'a str,
    scene: SmsScene,
    action: &'a str,
    result: &'a str,
    reason: Option<&'a str>,
    request_ip_hash: Option<&'a str>,
    code_plain: Option<&'a str>,
    user_id: Option<i64>,
}

static SMS_FALLBACK_STORE: LazyLock<Mutex<HashMap<String, SmsFallbackEntry>>> =
    LazyLock::new(|| Mutex::new(HashMap::new()));
static WECHAT_CHALLENGE_FALLBACK_STORE: LazyLock<Mutex<HashMap<String, String>>> =
    LazyLock::new(|| Mutex::new(HashMap::new()));
static WECHAT_BIND_TICKET_FALLBACK_STORE: LazyLock<Mutex<HashMap<String, String>>> =
    LazyLock::new(|| Mutex::new(HashMap::new()));

#[derive(Debug, Serialize, ToSchema, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AuthOutput {
    access_token: String,
    token_type: String,
    expires_in_secs: u64,
    user: User,
}

#[derive(Debug, Serialize, ToSchema, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RefreshOutput {
    access_token: String,
    token_type: String,
    expires_in_secs: u64,
}

#[derive(Debug, Serialize, ToSchema, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct LogoutOutput {
    revoked: bool,
}

#[derive(Debug, Clone, Serialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct AuthSessionItem {
    pub sid: String,
    pub family_id: String,
    pub expires_at: DateTime<Utc>,
    pub revoked_at: Option<DateTime<Utc>>,
    pub revoke_reason: Option<String>,
    pub user_agent: Option<String>,
    pub ip_hash: Option<String>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct ListAuthSessionsOutput {
    pub items: Vec<AuthSessionItem>,
}

#[derive(Debug, Clone, Serialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct LogoutAllOutput {
    pub revoked_count: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct GetAuthConsistencyMetricsOutput {
    pub immediate_invalidation_success_total: u64,
    pub immediate_invalidation_failed_total: u64,
    pub retry_enqueue_total: u64,
    pub retry_dedup_total: u64,
    pub retry_overflow_drop_total: u64,
    pub retry_attempt_total: u64,
    pub retry_success_total: u64,
    pub retry_requeue_total: u64,
    pub retry_terminal_drop_total: u64,
    pub retry_tick_total: u64,
    pub retry_tick_error_total: u64,
    pub token_version_retry_queue_depth: u64,
    pub refresh_total: u64,
    pub refresh_success_total: u64,
    pub refresh_failed_total: u64,
    pub refresh_failed_missing_total: u64,
    pub refresh_failed_invalid_total: u64,
    pub refresh_failed_expired_total: u64,
    pub refresh_failed_conflict_total: u64,
    pub refresh_failed_replayed_total: u64,
    pub refresh_failed_session_revoked_total: u64,
    pub refresh_failed_degraded_retryable_total: u64,
    pub refresh_lock_wait_ms_total: u64,
    pub refresh_lock_wait_samples_total: u64,
    pub refresh_outbox_enqueue_total: u64,
    pub refresh_outbox_delivered_total: u64,
    pub refresh_outbox_requeue_total: u64,
    pub refresh_outbox_drop_total: u64,
    pub refresh_outbox_tick_total: u64,
    pub refresh_outbox_tick_error_total: u64,
    pub refresh_outbox_queue_depth: u64,
}

#[derive(Debug, Default, Clone, Copy)]
pub(crate) struct AuthTokenVersionInvalidationRetryReport {
    pub attempted: usize,
    pub succeeded: usize,
    pub requeued: usize,
    pub dropped: usize,
}

#[derive(Debug, Default, Clone, Copy)]
pub(crate) struct AuthRefreshConsistencyOutboxRetryReport {
    pub attempted: usize,
    pub delivered: usize,
    pub requeued: usize,
    pub dropped: usize,
}

#[derive(Debug, Clone, Copy, FromRow)]
struct ClaimedAuthTokenVersionInvalidationJob {
    user_id: i64,
    attempts: i32,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum AuthRefreshOutboxOp {
    SetWithTtl,
}

impl AuthRefreshOutboxOp {
    fn as_str(self) -> &'static str {
        match self {
            Self::SetWithTtl => "set_with_ttl",
        }
    }

    fn parse(raw: &str) -> Option<Self> {
        match raw.trim().to_ascii_lowercase().as_str() {
            "set_with_ttl" => Some(Self::SetWithTtl),
            _ => None,
        }
    }
}

#[derive(Debug, Clone, FromRow)]
struct ClaimedAuthRefreshConsistencyOutboxJob {
    id: i64,
    op_type: String,
    scope: String,
    raw_key: String,
    value: String,
    ttl_secs: i64,
    attempts: i32,
}

#[derive(Debug, Default)]
pub(crate) struct AuthConsistencyMetrics {
    immediate_invalidation_success_total: AtomicU64,
    immediate_invalidation_failed_total: AtomicU64,
    retry_enqueue_total: AtomicU64,
    retry_dedup_total: AtomicU64,
    retry_overflow_drop_total: AtomicU64,
    retry_attempt_total: AtomicU64,
    retry_success_total: AtomicU64,
    retry_requeue_total: AtomicU64,
    retry_terminal_drop_total: AtomicU64,
    retry_tick_total: AtomicU64,
    retry_tick_error_total: AtomicU64,
    token_version_retry_queue_depth: AtomicU64,
    refresh_total: AtomicU64,
    refresh_success_total: AtomicU64,
    refresh_failed_total: AtomicU64,
    refresh_failed_missing_total: AtomicU64,
    refresh_failed_invalid_total: AtomicU64,
    refresh_failed_expired_total: AtomicU64,
    refresh_failed_conflict_total: AtomicU64,
    refresh_failed_replayed_total: AtomicU64,
    refresh_failed_session_revoked_total: AtomicU64,
    refresh_failed_degraded_retryable_total: AtomicU64,
    refresh_lock_wait_ms_total: AtomicU64,
    refresh_lock_wait_samples_total: AtomicU64,
    refresh_outbox_enqueue_total: AtomicU64,
    refresh_outbox_delivered_total: AtomicU64,
    refresh_outbox_requeue_total: AtomicU64,
    refresh_outbox_drop_total: AtomicU64,
    refresh_outbox_tick_total: AtomicU64,
    refresh_outbox_tick_error_total: AtomicU64,
    refresh_outbox_queue_depth: AtomicU64,
}

impl AuthConsistencyMetrics {
    fn observe_immediate_success(&self) {
        self.immediate_invalidation_success_total
            .fetch_add(1, Ordering::Relaxed);
    }

    fn observe_immediate_failure(&self) {
        self.immediate_invalidation_failed_total
            .fetch_add(1, Ordering::Relaxed);
    }

    fn observe_retry_enqueued(&self, queue_depth: u64) {
        self.retry_enqueue_total.fetch_add(1, Ordering::Relaxed);
        self.token_version_retry_queue_depth
            .store(queue_depth, Ordering::Relaxed);
    }

    fn observe_retry_dedup(&self, queue_depth: u64) {
        self.retry_dedup_total.fetch_add(1, Ordering::Relaxed);
        self.token_version_retry_queue_depth
            .store(queue_depth, Ordering::Relaxed);
    }

    fn observe_retry_overflow_drop(&self, queue_depth: u64) {
        self.retry_overflow_drop_total
            .fetch_add(1, Ordering::Relaxed);
        self.token_version_retry_queue_depth
            .store(queue_depth, Ordering::Relaxed);
    }

    fn observe_retry_tick(
        &self,
        report: AuthTokenVersionInvalidationRetryReport,
        queue_depth: u64,
    ) {
        self.retry_tick_total.fetch_add(1, Ordering::Relaxed);
        self.retry_attempt_total
            .fetch_add(report.attempted as u64, Ordering::Relaxed);
        self.retry_success_total
            .fetch_add(report.succeeded as u64, Ordering::Relaxed);
        self.retry_requeue_total
            .fetch_add(report.requeued as u64, Ordering::Relaxed);
        self.retry_terminal_drop_total
            .fetch_add(report.dropped as u64, Ordering::Relaxed);
        self.token_version_retry_queue_depth
            .store(queue_depth, Ordering::Relaxed);
    }

    fn observe_retry_tick_error(&self) {
        self.retry_tick_error_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_queue_depth(&self, queue_depth: u64) {
        self.token_version_retry_queue_depth
            .store(queue_depth, Ordering::Relaxed);
    }

    fn observe_refresh_start(&self) {
        self.refresh_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_refresh_lock_wait(&self, wait_ms: u64) {
        self.refresh_lock_wait_ms_total
            .fetch_add(wait_ms, Ordering::Relaxed);
        self.refresh_lock_wait_samples_total
            .fetch_add(1, Ordering::Relaxed);
    }

    fn observe_refresh_success(&self) {
        self.refresh_success_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_refresh_failure_code(&self, code: &str) {
        self.refresh_failed_total.fetch_add(1, Ordering::Relaxed);
        match code {
            "auth_refresh_missing" => {
                self.refresh_failed_missing_total
                    .fetch_add(1, Ordering::Relaxed);
            }
            "auth_refresh_invalid" => {
                self.refresh_failed_invalid_total
                    .fetch_add(1, Ordering::Relaxed);
            }
            "auth_refresh_expired" => {
                self.refresh_failed_expired_total
                    .fetch_add(1, Ordering::Relaxed);
            }
            "auth_refresh_conflict_retry" => {
                self.refresh_failed_conflict_total
                    .fetch_add(1, Ordering::Relaxed);
            }
            "auth_refresh_replayed" => {
                self.refresh_failed_replayed_total
                    .fetch_add(1, Ordering::Relaxed);
            }
            "auth_session_revoked" => {
                self.refresh_failed_session_revoked_total
                    .fetch_add(1, Ordering::Relaxed);
            }
            "auth_refresh_degraded_retryable" => {
                self.refresh_failed_degraded_retryable_total
                    .fetch_add(1, Ordering::Relaxed);
            }
            _ => {}
        }
    }

    fn observe_refresh_outbox_enqueued(&self, queue_depth: u64) {
        self.refresh_outbox_enqueue_total
            .fetch_add(1, Ordering::Relaxed);
        self.refresh_outbox_queue_depth
            .store(queue_depth, Ordering::Relaxed);
    }

    fn observe_refresh_outbox_tick(
        &self,
        delivered: usize,
        requeued: usize,
        dropped: usize,
        queue_depth: u64,
    ) {
        self.refresh_outbox_tick_total
            .fetch_add(1, Ordering::Relaxed);
        self.refresh_outbox_delivered_total
            .fetch_add(delivered as u64, Ordering::Relaxed);
        self.refresh_outbox_requeue_total
            .fetch_add(requeued as u64, Ordering::Relaxed);
        self.refresh_outbox_drop_total
            .fetch_add(dropped as u64, Ordering::Relaxed);
        self.refresh_outbox_queue_depth
            .store(queue_depth, Ordering::Relaxed);
    }

    fn observe_refresh_outbox_tick_error(&self) {
        self.refresh_outbox_tick_error_total
            .fetch_add(1, Ordering::Relaxed);
    }

    fn observe_refresh_outbox_depth(&self, queue_depth: u64) {
        self.refresh_outbox_queue_depth
            .store(queue_depth, Ordering::Relaxed);
    }

    pub(crate) fn snapshot(&self) -> GetAuthConsistencyMetricsOutput {
        GetAuthConsistencyMetricsOutput {
            immediate_invalidation_success_total: self
                .immediate_invalidation_success_total
                .load(Ordering::Relaxed),
            immediate_invalidation_failed_total: self
                .immediate_invalidation_failed_total
                .load(Ordering::Relaxed),
            retry_enqueue_total: self.retry_enqueue_total.load(Ordering::Relaxed),
            retry_dedup_total: self.retry_dedup_total.load(Ordering::Relaxed),
            retry_overflow_drop_total: self.retry_overflow_drop_total.load(Ordering::Relaxed),
            retry_attempt_total: self.retry_attempt_total.load(Ordering::Relaxed),
            retry_success_total: self.retry_success_total.load(Ordering::Relaxed),
            retry_requeue_total: self.retry_requeue_total.load(Ordering::Relaxed),
            retry_terminal_drop_total: self.retry_terminal_drop_total.load(Ordering::Relaxed),
            retry_tick_total: self.retry_tick_total.load(Ordering::Relaxed),
            retry_tick_error_total: self.retry_tick_error_total.load(Ordering::Relaxed),
            token_version_retry_queue_depth: self
                .token_version_retry_queue_depth
                .load(Ordering::Relaxed),
            refresh_total: self.refresh_total.load(Ordering::Relaxed),
            refresh_success_total: self.refresh_success_total.load(Ordering::Relaxed),
            refresh_failed_total: self.refresh_failed_total.load(Ordering::Relaxed),
            refresh_failed_missing_total: self.refresh_failed_missing_total.load(Ordering::Relaxed),
            refresh_failed_invalid_total: self.refresh_failed_invalid_total.load(Ordering::Relaxed),
            refresh_failed_expired_total: self.refresh_failed_expired_total.load(Ordering::Relaxed),
            refresh_failed_conflict_total: self
                .refresh_failed_conflict_total
                .load(Ordering::Relaxed),
            refresh_failed_replayed_total: self
                .refresh_failed_replayed_total
                .load(Ordering::Relaxed),
            refresh_failed_session_revoked_total: self
                .refresh_failed_session_revoked_total
                .load(Ordering::Relaxed),
            refresh_failed_degraded_retryable_total: self
                .refresh_failed_degraded_retryable_total
                .load(Ordering::Relaxed),
            refresh_lock_wait_ms_total: self.refresh_lock_wait_ms_total.load(Ordering::Relaxed),
            refresh_lock_wait_samples_total: self
                .refresh_lock_wait_samples_total
                .load(Ordering::Relaxed),
            refresh_outbox_enqueue_total: self.refresh_outbox_enqueue_total.load(Ordering::Relaxed),
            refresh_outbox_delivered_total: self
                .refresh_outbox_delivered_total
                .load(Ordering::Relaxed),
            refresh_outbox_requeue_total: self.refresh_outbox_requeue_total.load(Ordering::Relaxed),
            refresh_outbox_drop_total: self.refresh_outbox_drop_total.load(Ordering::Relaxed),
            refresh_outbox_tick_total: self.refresh_outbox_tick_total.load(Ordering::Relaxed),
            refresh_outbox_tick_error_total: self
                .refresh_outbox_tick_error_total
                .load(Ordering::Relaxed),
            refresh_outbox_queue_depth: self.refresh_outbox_queue_depth.load(Ordering::Relaxed),
        }
    }
}

#[derive(Debug, Clone, FromRow)]
struct AuthRefreshSessionRow {
    sid: String,
    family_id: String,
    user_id: i64,
    current_jti: String,
    rotated_from_jti: Option<String>,
    expires_at: DateTime<Utc>,
    revoked_at: Option<DateTime<Utc>>,
    revoke_reason: Option<String>,
    user_agent: Option<String>,
    ip_hash: Option<String>,
    created_at: DateTime<Utc>,
    updated_at: DateTime<Utc>,
}

#[derive(Debug)]
struct SessionContext {
    user_agent: Option<String>,
    ip_hash: Option<String>,
}

#[derive(Debug)]
struct IssuedTokens {
    access_token: String,
    refresh_token: String,
    sid: String,
    family_id: String,
    refresh_jti: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct SendSmsCodeV2Input {
    pub phone: String,
    pub scene: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct SendSmsCodeV2Output {
    pub sent: bool,
    pub ttl_secs: u64,
    pub cooldown_secs: u64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub debug_code: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct SignupPhoneV2Input {
    pub phone: String,
    pub sms_code: String,
    pub password: String,
    #[serde(default)]
    pub fullname: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct SignupEmailV2Input {
    pub email: String,
    pub phone: String,
    pub sms_code: String,
    pub password: String,
    #[serde(default)]
    pub fullname: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct SigninPasswordV2Input {
    pub account: String,
    pub account_type: String,
    pub password: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct SigninOtpV2Input {
    pub phone: String,
    pub sms_code: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct WechatChallengeV2Output {
    pub state: String,
    pub expires_in_secs: u64,
    pub app_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct WechatSigninV2Input {
    pub state: String,
    pub code: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct WechatSigninV2Output {
    pub bind_required: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wechat_ticket: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub access_token: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub token_type: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub expires_in_secs: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub user: Option<User>,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct WechatBindPhoneV2Input {
    pub wechat_ticket: String,
    pub phone: String,
    pub sms_code: String,
    #[serde(default)]
    pub password: Option<String>,
    #[serde(default)]
    pub fullname: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct BindPhoneV2Input {
    pub phone: String,
    pub sms_code: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct BindPhoneV2Output {
    pub bound: bool,
    pub user: User,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct SetPasswordV2Input {
    pub password: String,
    #[serde(default)]
    pub sms_code: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct SetPasswordV2Output {
    pub updated: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum SmsScene {
    SignupPhone,
    BindPhone,
    SigninPhoneOtp,
}

impl SmsScene {
    fn parse(raw: &str) -> Option<Self> {
        match raw.trim().to_ascii_lowercase().as_str() {
            "signup_phone" => Some(Self::SignupPhone),
            "bind_phone" => Some(Self::BindPhone),
            "signin_phone_otp" => Some(Self::SigninPhoneOtp),
            _ => None,
        }
    }

    fn as_str(self) -> &'static str {
        match self {
            Self::SignupPhone => "signup_phone",
            Self::BindPhone => "bind_phone",
            Self::SigninPhoneOtp => "signin_phone_otp",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum AccountType {
    Email,
    Phone,
}

impl AccountType {
    fn parse(raw: &str) -> Option<Self> {
        match raw.trim().to_ascii_lowercase().as_str() {
            "email" => Some(Self::Email),
            "phone" => Some(Self::Phone),
            _ => None,
        }
    }

    fn as_str(self) -> &'static str {
        match self {
            Self::Email => "email",
            Self::Phone => "phone",
        }
    }
}

fn now_epoch_secs() -> u64 {
    Utc::now().timestamp().max(0) as u64
}

fn runtime_env_is_production() -> bool {
    for key in ["ECHOISLE_ENV", "APP_ENV", "RUST_ENV", "ENV"] {
        if let Ok(value) = std::env::var(key) {
            let normalized = value.trim().to_ascii_lowercase();
            if normalized == "prod" || normalized == "production" {
                return true;
            }
        }
    }
    false
}

fn sms_provider_name() -> String {
    std::env::var("AUTH_SMS_PROVIDER")
        .unwrap_or_else(|_| SMS_PROVIDER_MOCK.to_string())
        .trim()
        .to_ascii_lowercase()
}

fn wechat_app_id() -> String {
    std::env::var("AUTH_WECHAT_APP_ID")
        .unwrap_or_else(|_| "wx-dev-mock-app-id".to_string())
        .trim()
        .to_string()
}

fn redis_is_disabled(state: &AppState) -> bool {
    matches!(state.redis, RedisStore::Disabled { .. })
}

fn build_sms_fallback_key(scene: SmsScene, phone_e164: &str) -> String {
    format!("{}:{}", scene.as_str(), phone_e164)
}

fn fallback_set_sms_entry(scene: SmsScene, phone_e164: &str, code: &str) {
    let key = build_sms_fallback_key(scene, phone_e164);
    let mut map = SMS_FALLBACK_STORE.lock().expect("lock sms fallback store");
    map.insert(
        key,
        SmsFallbackEntry {
            code: code.to_string(),
            expires_at_epoch_secs: now_epoch_secs() + SMS_CODE_TTL_SECS,
            cooldown_until_epoch_secs: now_epoch_secs() + SMS_COOLDOWN_SECS,
            failed_attempts: 0,
        },
    );
}

fn fallback_get_sms_entry(scene: SmsScene, phone_e164: &str) -> Option<SmsFallbackEntry> {
    let key = build_sms_fallback_key(scene, phone_e164);
    let mut map = SMS_FALLBACK_STORE.lock().expect("lock sms fallback store");
    let now = now_epoch_secs();
    if let Some(entry) = map.get(&key) {
        if entry.expires_at_epoch_secs > now {
            return Some(entry.clone());
        }
    }
    map.remove(&key);
    None
}

fn fallback_set_wechat_challenge(nonce: &str, state: &str) {
    let mut map = WECHAT_CHALLENGE_FALLBACK_STORE
        .lock()
        .expect("lock wechat challenge fallback store");
    map.insert(nonce.to_string(), state.to_string());
}

fn fallback_take_wechat_challenge(nonce: &str) -> Option<String> {
    let mut map = WECHAT_CHALLENGE_FALLBACK_STORE
        .lock()
        .expect("lock wechat challenge fallback store");
    map.remove(nonce)
}

fn fallback_set_wechat_bind_ticket(ticket: &str, payload_json: &str) {
    let mut map = WECHAT_BIND_TICKET_FALLBACK_STORE
        .lock()
        .expect("lock wechat bind fallback store");
    map.insert(ticket.to_string(), payload_json.to_string());
}

fn fallback_take_wechat_bind_ticket(ticket: &str) -> Option<String> {
    let mut map = WECHAT_BIND_TICKET_FALLBACK_STORE
        .lock()
        .expect("lock wechat bind fallback store");
    map.remove(ticket)
}

fn append_auth_v1_deprecation_headers(headers: &mut HeaderMap) -> Result<(), AppError> {
    headers.insert("Deprecation", HeaderValue::from_static("true"));
    headers.insert("Sunset", HeaderValue::from_str(AUTH_V1_SUNSET_DATE)?);
    Ok(())
}

fn build_default_fullname_from_phone(phone_e164: &str) -> String {
    let last4: String = phone_e164
        .chars()
        .rev()
        .take(4)
        .collect::<Vec<_>>()
        .into_iter()
        .rev()
        .collect();
    format!("用户{}", last4)
}

fn normalize_cn_phone_e164(input: &str) -> Option<String> {
    let compact: String = input
        .trim()
        .chars()
        .filter(|c| c.is_ascii_digit() || *c == '+')
        .collect();
    let local = if let Some(rest) = compact.strip_prefix("+86") {
        rest.to_string()
    } else if let Some(rest) = compact.strip_prefix("86") {
        rest.to_string()
    } else {
        compact
    };
    if local.len() != 11 || !local.starts_with('1') {
        return None;
    }
    if !local.chars().all(|c| c.is_ascii_digit()) {
        return None;
    }
    let second = local.chars().nth(1)?;
    if !matches!(second, '3' | '4' | '5' | '6' | '7' | '8' | '9') {
        return None;
    }
    Some(format!("+86{}", local))
}

fn normalize_email(input: &str) -> Option<String> {
    let normalized = input.trim().to_ascii_lowercase();
    if normalized.is_empty() || !normalized.contains('@') {
        return None;
    }
    Some(normalized)
}

fn build_signin_password_rate_limit_key(
    account_type: AccountType,
    normalized_account: &str,
) -> String {
    format!(
        "{}:{}",
        account_type.as_str(),
        hash_with_sha1(normalized_account),
    )
}

fn generate_sms_code() -> String {
    let seed = Uuid::now_v7().as_u128() % 1_000_000;
    format!("{seed:06}")
}

fn extract_nonce_from_wechat_state(state: &str) -> Option<String> {
    state.split(':').next().and_then(|v| {
        let n = v.trim();
        if n.is_empty() {
            None
        } else {
            Some(n.to_string())
        }
    })
}

fn resolve_wechat_identity_from_code(code: &str) -> Result<WechatIdentity, AppError> {
    let trimmed = code.trim();
    if !trimmed.starts_with("mock_") {
        return Err(AppError::AuthError("auth_access_invalid".to_string()));
    }
    let raw = trimmed.trim_start_matches("mock_");
    let segments: Vec<&str> = raw.split(':').collect();
    let provider_user_id = segments
        .first()
        .map(|v| v.trim())
        .filter(|v| !v.is_empty())
        .ok_or_else(|| AppError::AuthError("auth_access_invalid".to_string()))?
        .to_string();
    let provider_unionid = segments
        .get(1)
        .map(|v| v.trim())
        .filter(|v| !v.is_empty())
        .map(ToString::to_string);
    let nickname = segments
        .get(2)
        .map(|v| v.trim())
        .filter(|v| !v.is_empty())
        .map(ToString::to_string);
    Ok(WechatIdentity {
        provider_user_id,
        provider_unionid,
        nickname,
    })
}

#[utoipa::path(
    post,
    path = "/api/signup",
    responses(
        (status = 410, description = "Legacy signup disabled", body = ErrorOutput),
        (status = 401, description = "Auth error", body = ErrorOutput),
    )
)]
pub(crate) async fn signup_handler(
    State(_state): State<AppState>,
    _headers: HeaderMap,
    Json(_input): Json<CreateUser>,
) -> Result<impl IntoResponse, AppError> {
    let mut resp_headers = HeaderMap::new();
    append_auth_v1_deprecation_headers(&mut resp_headers)?;
    tracing::warn!(
        api = "/api/signup",
        "legacy auth v1 signup endpoint disabled"
    );
    let body = Json(ErrorOutput::new("auth_v1_signup_disabled_use_v2"));
    Ok((StatusCode::GONE, resp_headers, body))
}

#[utoipa::path(
    post,
    path = "/api/signin",
    responses(
        (status = 200, description = "User signed in", body = AuthOutput),
        (status = 401, description = "Auth error", body = ErrorOutput),
        (status = 429, description = "Rate limited", body = ErrorOutput),
    )
)]
pub(crate) async fn signin_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(input): Json<SigninUser>,
) -> Result<impl IntoResponse, AppError> {
    let email_key = input.email.trim().to_ascii_lowercase();
    let decision = enforce_rate_limit(
        &state,
        "signin",
        &email_key,
        SIGNIN_RATE_LIMIT_PER_WINDOW,
        SIGNIN_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    let mut resp_headers = build_rate_limit_headers(&decision)?;
    if !decision.allowed {
        return Ok(rate_limit_exceeded_response("signin", resp_headers));
    }

    let user = match state.verify_user(&input).await? {
        Some(v) => v,
        None => {
            let body = Json(ErrorOutput::new("auth_access_invalid"));
            return Ok((StatusCode::UNAUTHORIZED, resp_headers, body).into_response());
        }
    };

    let ctx = session_context_from_headers(&headers);
    let token_version = load_user_token_version(&state, user.id).await?;
    let issued = issue_auth_tokens(&state, &user, token_version)?;
    persist_refresh_session(&state, &user, &issued, &ctx).await?;
    sync_session_state_to_redis(&state, &issued, user.id, token_version).await?;

    set_refresh_cookie_header(
        &mut resp_headers,
        &issued.refresh_token,
        REFRESH_TOKEN_TTL_SECS,
    )?;
    append_auth_v1_deprecation_headers(&mut resp_headers)?;
    tracing::info!(api = "/api/signin", "legacy auth v1 signin endpoint called");
    Ok((
        StatusCode::OK,
        resp_headers,
        Json(AuthOutput {
            access_token: issued.access_token.clone(),
            token_type: "Bearer".to_string(),
            expires_in_secs: ACCESS_TOKEN_TTL_SECS,
            user,
        }),
    )
        .into_response())
}

#[utoipa::path(
    post,
    path = "/api/auth/v2/sms/send",
    request_body = SendSmsCodeV2Input,
    responses(
        (status = 200, description = "SMS code sent", body = SendSmsCodeV2Output),
        (status = 400, description = "Invalid input", body = ErrorOutput),
        (status = 429, description = "Rate limited", body = ErrorOutput),
    )
)]
pub(crate) async fn send_sms_code_v2_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(input): Json<SendSmsCodeV2Input>,
) -> Result<Response, AppError> {
    if runtime_env_is_production() && sms_provider_name() == SMS_PROVIDER_MOCK {
        return Err(AppError::AuthError(
            "auth_sms_send_rate_limited".to_string(),
        ));
    }

    let scene = SmsScene::parse(&input.scene)
        .ok_or_else(|| AppError::AuthError("auth_sms_code_invalid".to_string()))?;
    let phone_e164 = normalize_cn_phone_e164(&input.phone)
        .ok_or_else(|| AppError::AuthError("auth_sms_code_invalid".to_string()))?;
    let ip_hash = extract_ip_hash(&headers);

    let phone_decision = enforce_auth_rate_limit(
        &state,
        "sms_send_phone",
        &format!("{}:{phone_e164}", scene.as_str()),
        5,
        60,
    )
    .await?;
    let ip_decision = enforce_auth_rate_limit(
        &state,
        "sms_send_ip",
        &format!(
            "{}:{}",
            scene.as_str(),
            ip_hash.clone().unwrap_or_else(|| "unknown".to_string())
        ),
        20,
        60,
    )
    .await?;
    let resp_headers = build_rate_limit_headers(&phone_decision)?;
    if !phone_decision.allowed || !ip_decision.allowed {
        let body = Json(ErrorOutput::new("auth_sms_send_rate_limited"));
        return Ok((StatusCode::TOO_MANY_REQUESTS, resp_headers, body).into_response());
    }

    if sms_code_cooldown_active(&state, scene, &phone_e164).await? {
        let body = Json(ErrorOutput::new("auth_sms_send_rate_limited"));
        return Ok((StatusCode::TOO_MANY_REQUESTS, resp_headers, body).into_response());
    }

    let code = generate_sms_code();
    store_sms_code(&state, scene, &phone_e164, &code).await?;
    insert_sms_audit_log_best_effort(
        &state,
        SmsAuditLogInput {
            phone_e164: &phone_e164,
            scene,
            action: "send",
            result: "sent",
            reason: None,
            request_ip_hash: ip_hash.as_deref(),
            code_plain: Some(&code),
            user_id: None,
        },
    )
    .await;

    let debug_code = if !runtime_env_is_production() && sms_provider_name() == SMS_PROVIDER_MOCK {
        Some(code)
    } else {
        None
    };
    Ok((
        StatusCode::OK,
        resp_headers,
        Json(SendSmsCodeV2Output {
            sent: true,
            ttl_secs: SMS_CODE_TTL_SECS,
            cooldown_secs: SMS_COOLDOWN_SECS,
            debug_code,
        }),
    )
        .into_response())
}

#[utoipa::path(
    post,
    path = "/api/auth/v2/signup/phone",
    request_body = SignupPhoneV2Input,
    responses(
        (status = 201, description = "User created", body = AuthOutput),
        (status = 400, description = "Invalid input", body = ErrorOutput),
        (status = 401, description = "Auth error", body = ErrorOutput),
        (status = 409, description = "Conflict", body = ErrorOutput),
    )
)]
pub(crate) async fn signup_phone_v2_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(input): Json<SignupPhoneV2Input>,
) -> Result<impl IntoResponse, AppError> {
    let phone_e164 = normalize_cn_phone_e164(&input.phone)
        .ok_or_else(|| AppError::AuthError("auth_sms_code_invalid".to_string()))?;
    verify_sms_code(
        &state,
        SmsScene::SignupPhone,
        &phone_e164,
        &input.sms_code,
        None,
    )
    .await?;

    let fullname = if input.fullname.trim().is_empty() {
        build_default_fullname_from_phone(&phone_e164)
    } else {
        input.fullname.trim().to_string()
    };
    let ctx = session_context_from_headers(&headers);
    let sid = Uuid::now_v7().to_string();
    let family_id = Uuid::now_v7().to_string();
    let refresh_jti = Uuid::now_v7().to_string();
    let user = state
        .create_user_with_phone_and_session(&CreateUserWithPhoneAndSessionInput {
            fullname,
            email: None,
            phone_e164: phone_e164.clone(),
            password: input.password.clone(),
            phone_bind_required: false,
            sid: sid.clone(),
            family_id: family_id.clone(),
            refresh_jti: refresh_jti.clone(),
            refresh_ttl_secs: REFRESH_TOKEN_TTL_SECS as i64,
            user_agent: ctx.user_agent.clone(),
            ip_hash: ctx.ip_hash.clone(),
        })
        .await?;
    let token_version = load_user_token_version(&state, user.id).await?;
    let issued = issue_auth_tokens_with_session_ids(
        &state,
        &user,
        token_version,
        sid,
        family_id,
        refresh_jti,
    )?;

    let (status, resp_headers, body) =
        finalize_auth_success_response(&state, user, StatusCode::CREATED, issued, token_version)
            .await?;
    Ok((status, resp_headers, Json(body)))
}

#[utoipa::path(
    post,
    path = "/api/auth/v2/signup/email",
    request_body = SignupEmailV2Input,
    responses(
        (status = 201, description = "User created", body = AuthOutput),
        (status = 400, description = "Invalid input", body = ErrorOutput),
        (status = 401, description = "Auth error", body = ErrorOutput),
        (status = 409, description = "Conflict", body = ErrorOutput),
    )
)]
pub(crate) async fn signup_email_v2_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(input): Json<SignupEmailV2Input>,
) -> Result<impl IntoResponse, AppError> {
    let email = normalize_email(&input.email)
        .ok_or_else(|| AppError::AuthError("auth_access_invalid".to_string()))?;
    let phone_e164 = normalize_cn_phone_e164(&input.phone)
        .ok_or_else(|| AppError::AuthError("auth_sms_code_invalid".to_string()))?;
    verify_sms_code(
        &state,
        SmsScene::BindPhone,
        &phone_e164,
        &input.sms_code,
        None,
    )
    .await?;

    let fullname = if input.fullname.trim().is_empty() {
        build_default_fullname_from_phone(&phone_e164)
    } else {
        input.fullname.trim().to_string()
    };
    let user = state
        .create_user_with_phone(&CreateUserWithPhoneInput {
            fullname,
            email: Some(email),
            phone_e164: phone_e164.clone(),
            password: input.password.clone(),
            phone_bind_required: false,
        })
        .await?;

    let (status, resp_headers, body) =
        issue_auth_success_response(&state, &headers, user, StatusCode::CREATED).await?;
    Ok((status, resp_headers, Json(body)))
}

#[utoipa::path(
    post,
    path = "/api/auth/v2/signin/password",
    request_body = SigninPasswordV2Input,
    responses(
        (status = 200, description = "User signed in", body = AuthOutput),
        (status = 400, description = "Invalid input", body = ErrorOutput),
        (status = 401, description = "Auth error", body = ErrorOutput),
        (status = 429, description = "Rate limited", body = ErrorOutput),
    )
)]
pub(crate) async fn signin_password_v2_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(input): Json<SigninPasswordV2Input>,
) -> Result<Response, AppError> {
    let account_type = AccountType::parse(&input.account_type)
        .ok_or_else(|| AppError::AuthError("auth_access_invalid".to_string()))?;
    let normalized_account = match account_type {
        AccountType::Email => normalize_email(&input.account)
            .ok_or_else(|| AppError::AuthError("auth_access_invalid".to_string()))?,
        AccountType::Phone => normalize_cn_phone_e164(&input.account)
            .ok_or_else(|| AppError::AuthError("auth_access_invalid".to_string()))?,
    };
    let limiter_account = build_signin_password_rate_limit_key(account_type, &normalized_account);
    let decision = enforce_rate_limit(
        &state,
        "signin_v2_password",
        &limiter_account,
        SIGNIN_RATE_LIMIT_PER_WINDOW,
        SIGNIN_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    let resp_headers = build_rate_limit_headers(&decision)?;
    if !decision.allowed {
        let body = Json(ErrorOutput::new("rate_limit_exceeded:signin_v2_password"));
        return Ok((StatusCode::TOO_MANY_REQUESTS, resp_headers, body).into_response());
    }

    let user = match account_type {
        AccountType::Email => {
            state
                .verify_user(&SigninUser {
                    email: normalized_account,
                    password: input.password.clone(),
                })
                .await?
        }
        AccountType::Phone => {
            state
                .verify_user_by_phone_password(&normalized_account, &input.password)
                .await?
        }
    };

    let Some(user) = user else {
        let body = Json(ErrorOutput::new("auth_access_invalid"));
        return Ok((StatusCode::UNAUTHORIZED, resp_headers, body).into_response());
    };
    let (status, auth_headers, body) =
        issue_auth_success_response(&state, &headers, user, StatusCode::OK).await?;
    Ok((
        status,
        merge_headers(resp_headers, auth_headers),
        Json(body),
    )
        .into_response())
}

#[utoipa::path(
    post,
    path = "/api/auth/v2/signin/otp",
    request_body = SigninOtpV2Input,
    responses(
        (status = 200, description = "User signed in", body = AuthOutput),
        (status = 400, description = "Invalid input", body = ErrorOutput),
        (status = 401, description = "Auth error", body = ErrorOutput),
        (status = 429, description = "Rate limited", body = ErrorOutput),
    )
)]
pub(crate) async fn signin_otp_v2_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(input): Json<SigninOtpV2Input>,
) -> Result<Response, AppError> {
    let phone_e164 = normalize_cn_phone_e164(&input.phone)
        .ok_or_else(|| AppError::AuthError("auth_sms_code_invalid".to_string()))?;
    verify_sms_code(
        &state,
        SmsScene::SigninPhoneOtp,
        &phone_e164,
        &input.sms_code,
        None,
    )
    .await?;
    let Some(user) = state.find_user_by_phone(&phone_e164).await? else {
        return Err(AppError::AuthError(
            "auth_account_not_registered".to_string(),
        ));
    };
    let (status, resp_headers, body) =
        issue_auth_success_response(&state, &headers, user, StatusCode::OK).await?;
    Ok((status, resp_headers, Json(body)).into_response())
}

#[utoipa::path(
    post,
    path = "/api/auth/v2/wechat/challenge",
    responses(
        (status = 200, description = "Wechat challenge issued", body = WechatChallengeV2Output),
        (status = 401, description = "Auth error", body = ErrorOutput),
    )
)]
pub(crate) async fn wechat_challenge_v2_handler(
    State(state): State<AppState>,
) -> Result<impl IntoResponse, AppError> {
    let nonce = Uuid::now_v7().to_string();
    let state_value = format!("{nonce}:{}", Uuid::now_v7());
    store_wechat_challenge(&state, &nonce, &state_value).await?;
    Ok((
        StatusCode::OK,
        Json(WechatChallengeV2Output {
            state: state_value,
            expires_in_secs: WECHAT_CHALLENGE_TTL_SECS,
            app_id: wechat_app_id(),
        }),
    ))
}

#[utoipa::path(
    post,
    path = "/api/auth/v2/wechat/signin",
    request_body = WechatSigninV2Input,
    responses(
        (status = 200, description = "Wechat signin result", body = WechatSigninV2Output),
        (status = 401, description = "Auth error", body = ErrorOutput),
    )
)]
pub(crate) async fn wechat_signin_v2_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(input): Json<WechatSigninV2Input>,
) -> Result<impl IntoResponse, AppError> {
    verify_wechat_challenge_state(&state, &input.state).await?;
    let identity = resolve_wechat_identity_from_code(&input.code)?;

    if let Some(user) = find_user_by_wechat_identity(&state, &identity).await? {
        let has_bound_phone = user
            .phone_e164
            .as_deref()
            .map(str::trim)
            .filter(|phone| !phone.is_empty())
            .is_some()
            && !user.phone_bind_required;
        if has_bound_phone {
            let (status, resp_headers, body) =
                issue_auth_success_response(&state, &headers, user, StatusCode::OK).await?;
            return Ok((
                status,
                resp_headers,
                Json(WechatSigninV2Output {
                    bind_required: false,
                    wechat_ticket: None,
                    access_token: Some(body.access_token),
                    token_type: Some(body.token_type),
                    expires_in_secs: Some(body.expires_in_secs),
                    user: Some(body.user),
                }),
            ));
        }
        let ticket = Uuid::now_v7().to_string();
        let payload = WechatBindTicketPayload {
            provider_user_id: identity.provider_user_id.clone(),
            provider_unionid: identity.provider_unionid.clone(),
            nickname: identity.nickname.clone(),
        };
        store_wechat_bind_ticket(&state, &ticket, &payload).await?;
        return Ok((
            StatusCode::OK,
            HeaderMap::new(),
            Json(WechatSigninV2Output {
                bind_required: true,
                wechat_ticket: Some(ticket),
                access_token: None,
                token_type: None,
                expires_in_secs: None,
                user: None,
            }),
        ));
    }

    let ticket = Uuid::now_v7().to_string();
    let payload = WechatBindTicketPayload {
        provider_user_id: identity.provider_user_id,
        provider_unionid: identity.provider_unionid,
        nickname: identity.nickname,
    };
    store_wechat_bind_ticket(&state, &ticket, &payload).await?;
    Ok((
        StatusCode::OK,
        HeaderMap::new(),
        Json(WechatSigninV2Output {
            bind_required: true,
            wechat_ticket: Some(ticket),
            access_token: None,
            token_type: None,
            expires_in_secs: None,
            user: None,
        }),
    ))
}

#[utoipa::path(
    post,
    path = "/api/auth/v2/wechat/bind-phone",
    request_body = WechatBindPhoneV2Input,
    responses(
        (status = 200, description = "Wechat bind and signin", body = WechatSigninV2Output),
        (status = 401, description = "Auth error", body = ErrorOutput),
        (status = 409, description = "Conflict", body = ErrorOutput),
    )
)]
pub(crate) async fn wechat_bind_phone_v2_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(input): Json<WechatBindPhoneV2Input>,
) -> Result<impl IntoResponse, AppError> {
    let payload = load_wechat_bind_ticket(&state, &input.wechat_ticket)
        .await?
        .ok_or_else(|| AppError::AuthError("auth_wechat_bind_required".to_string()))?;
    let phone_e164 = normalize_cn_phone_e164(&input.phone)
        .ok_or_else(|| AppError::AuthError("auth_sms_code_invalid".to_string()))?;

    verify_sms_code(
        &state,
        SmsScene::BindPhone,
        &phone_e164,
        &input.sms_code,
        None,
    )
    .await?;

    let user = if let Some(existing_user) = state.find_user_by_phone(&phone_e164).await? {
        upsert_wechat_identity_for_user(
            &state,
            existing_user.id,
            &payload.provider_user_id,
            payload.provider_unionid.as_deref(),
        )
        .await?;
        state
            .bind_phone_for_user(existing_user.id, &phone_e164)
            .await?
    } else {
        let fullname = if input.fullname.trim().is_empty() {
            payload
                .nickname
                .unwrap_or_else(|| build_default_fullname_from_phone(&phone_e164))
        } else {
            input.fullname.trim().to_string()
        };
        let password = input
            .password
            .as_deref()
            .map(str::trim)
            .filter(|v| !v.is_empty())
            .map(ToString::to_string)
            .unwrap_or_else(|| format!("wechat-auto-{}", Uuid::now_v7()));
        let new_user = state
            .create_user_with_phone(&CreateUserWithPhoneInput {
                fullname,
                email: None,
                phone_e164: phone_e164.clone(),
                password,
                phone_bind_required: false,
            })
            .await?;
        upsert_wechat_identity_for_user(
            &state,
            new_user.id,
            &payload.provider_user_id,
            payload.provider_unionid.as_deref(),
        )
        .await?;
        new_user
    };

    let (status, resp_headers, body) =
        issue_auth_success_response(&state, &headers, user, StatusCode::OK).await?;
    Ok((
        status,
        resp_headers,
        Json(WechatSigninV2Output {
            bind_required: false,
            wechat_ticket: None,
            access_token: Some(body.access_token),
            token_type: Some(body.token_type),
            expires_in_secs: Some(body.expires_in_secs),
            user: Some(body.user),
        }),
    ))
}

#[utoipa::path(
    post,
    path = "/api/auth/v2/phone/bind",
    request_body = BindPhoneV2Input,
    responses(
        (status = 200, description = "Phone bind result", body = BindPhoneV2Output),
        (status = 401, description = "Auth error", body = ErrorOutput),
        (status = 409, description = "Conflict", body = ErrorOutput),
    ),
    security(("token" = []))
)]
pub(crate) async fn bind_phone_v2_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Json(input): Json<BindPhoneV2Input>,
) -> Result<impl IntoResponse, AppError> {
    let phone_e164 = normalize_cn_phone_e164(&input.phone)
        .ok_or_else(|| AppError::AuthError("auth_sms_code_invalid".to_string()))?;
    verify_sms_code(
        &state,
        SmsScene::BindPhone,
        &phone_e164,
        &input.sms_code,
        Some(user.id),
    )
    .await?;
    let bound_user = state.bind_phone_for_user(user.id, &phone_e164).await?;
    Ok((
        StatusCode::OK,
        Json(BindPhoneV2Output {
            bound: true,
            user: bound_user,
        }),
    ))
}

#[utoipa::path(
    post,
    path = "/api/auth/v2/password/set",
    request_body = SetPasswordV2Input,
    responses(
        (status = 200, description = "Password updated", body = SetPasswordV2Output),
        (status = 401, description = "Auth error", body = ErrorOutput),
    ),
    security(("token" = []))
)]
pub(crate) async fn set_password_v2_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Json(input): Json<SetPasswordV2Input>,
) -> Result<impl IntoResponse, AppError> {
    let password = input.password.trim();
    if password.len() < 6 {
        return Err(AppError::AuthError("auth_password_invalid".to_string()));
    }
    let current_user = state
        .find_user_by_id(user.id)
        .await?
        .ok_or_else(|| AppError::AuthError("auth_access_invalid".to_string()))?;
    let phone_e164 = current_user
        .phone_e164
        .as_deref()
        .map(str::trim)
        .filter(|phone| !phone.is_empty())
        .ok_or_else(|| AppError::AuthError("auth_phone_bind_required".to_string()))?;
    if current_user.phone_bind_required {
        return Err(AppError::AuthError("auth_phone_bind_required".to_string()));
    }
    let sms_code = input
        .sms_code
        .as_deref()
        .map(str::trim)
        .filter(|code| !code.is_empty())
        .ok_or_else(|| AppError::AuthError("auth_sms_code_invalid".to_string()))?;
    verify_sms_code(
        &state,
        SmsScene::BindPhone,
        phone_e164,
        sms_code,
        Some(user.id),
    )
    .await?;
    state.set_user_password(user.id, password).await?;
    Ok((StatusCode::OK, Json(SetPasswordV2Output { updated: true })))
}

#[utoipa::path(
    post,
    path = "/api/auth/refresh",
    responses(
        (status = 200, description = "Refresh access token", body = RefreshOutput),
        (status = 401, description = "Auth error", body = ErrorOutput),
    )
)]
pub(crate) async fn refresh_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, AppError> {
    state.auth_consistency_metrics.observe_refresh_start();
    validate_refresh_csrf_headers(&headers)
        .map_err(|_| refresh_auth_error(&state, "auth_refresh_invalid"))?;

    let refresh_token = extract_refresh_token(&headers)
        .ok_or_else(|| refresh_auth_error(&state, "auth_refresh_missing"))?;

    let decoded = state
        .dk
        .verify_refresh(&refresh_token)
        .map_err(|err| refresh_auth_error(&state, refresh_verify_error_code(&err)))?;

    if is_refresh_blacklisted(&state, &decoded.jti)
        .await
        .map_err(|err| map_refresh_error_with_metrics(&state, err))?
    {
        revoke_family_by_id(&state, &decoded.family_id, "replay_detected").await?;
        tracing::warn!(
            sid = %decoded.sid,
            family_id = %decoded.family_id,
            user_id = decoded.user_id,
            decision = "blacklist_replayed",
            "auth refresh rejected by blacklist"
        );
        return Err(refresh_auth_error(&state, "auth_refresh_replayed"));
    }

    let now = Utc::now();
    let mut tx = state.pool.begin().await?;
    let lock_wait_started_at = std::time::Instant::now();
    let row: Option<AuthRefreshSessionRow> = sqlx::query_as(
        r#"
        SELECT
            sid, family_id, user_id, current_jti, rotated_from_jti, expires_at, revoked_at,
            revoke_reason, user_agent, ip_hash, created_at, updated_at
        FROM auth_refresh_sessions
        WHERE sid = $1 AND user_id = $2
        FOR UPDATE
        "#,
    )
    .bind(&decoded.sid)
    .bind(decoded.user_id)
    .fetch_optional(&mut *tx)
    .await?;
    state.auth_consistency_metrics.observe_refresh_lock_wait(
        lock_wait_started_at
            .elapsed()
            .as_millis()
            .min(u128::from(u64::MAX)) as u64,
    );

    let Some(session) = row else {
        tx.rollback().await.ok();
        tracing::warn!(
            sid = %decoded.sid,
            user_id = decoded.user_id,
            decision = "session_missing",
            "auth refresh rejected due to missing session"
        );
        return Err(refresh_auth_error(&state, "auth_refresh_invalid"));
    };

    if session.revoked_at.is_some() {
        tx.rollback().await.ok();
        tracing::warn!(
            sid = %session.sid,
            family_id = %session.family_id,
            user_id = session.user_id,
            decision = "session_revoked",
            "auth refresh rejected due to revoked session"
        );
        return Err(refresh_auth_error(&state, "auth_session_revoked"));
    }

    if session.expires_at <= now {
        sqlx::query(
            r#"
            UPDATE auth_refresh_sessions
            SET revoked_at = NOW(), revoke_reason = 'expired', updated_at = NOW()
            WHERE sid = $1
            "#,
        )
        .bind(&session.sid)
        .execute(&mut *tx)
        .await?;
        enqueue_auth_refresh_consistency_set_with_ttl_tx(
            &state,
            &mut *tx,
            "auth:rt:blacklist",
            &decoded.jti,
            "1",
            ttl_from_exp(decoded.exp),
        )
        .await?;
        tx.commit().await?;
        best_effort_set_refresh_blacklist(&state, &decoded.jti, ttl_from_exp(decoded.exp)).await;
        tracing::warn!(
            sid = %session.sid,
            family_id = %session.family_id,
            user_id = session.user_id,
            decision = "session_expired",
            "auth refresh rejected due to expired session"
        );
        return Err(refresh_auth_error(&state, "auth_refresh_expired"));
    }

    if session.current_jti != decoded.jti {
        if is_refresh_conflict_retry_candidate(&session, &decoded.jti, now) {
            tx.rollback().await.ok();
            tracing::warn!(
                sid = %session.sid,
                family_id = %session.family_id,
                user_id = session.user_id,
                decision = "conflict_retry",
                "auth refresh conflict detected within grace window"
            );
            return Err(refresh_auth_error(&state, "auth_refresh_conflict_retry"));
        }
        sqlx::query(
            r#"
            UPDATE auth_refresh_sessions
            SET revoked_at = NOW(), revoke_reason = 'replay_detected', updated_at = NOW()
            WHERE family_id = $1 AND revoked_at IS NULL
            "#,
        )
        .bind(&session.family_id)
        .execute(&mut *tx)
        .await?;
        enqueue_auth_refresh_consistency_set_with_ttl_tx(
            &state,
            &mut *tx,
            "auth:rt:blacklist",
            &decoded.jti,
            "1",
            ttl_from_exp(decoded.exp),
        )
        .await?;
        enqueue_auth_refresh_consistency_set_with_ttl_tx(
            &state,
            &mut *tx,
            "auth:rt:family",
            &session.family_id,
            "revoked",
            REFRESH_TOKEN_TTL_SECS,
        )
        .await?;
        tx.commit().await?;
        best_effort_set_refresh_blacklist(&state, &decoded.jti, ttl_from_exp(decoded.exp)).await;
        best_effort_set_refresh_family_revoked(&state, &session.family_id).await;
        tracing::warn!(
            sid = %session.sid,
            family_id = %session.family_id,
            user_id = session.user_id,
            decision = "replay_detected",
            "auth refresh replay detected and family revoked"
        );
        return Err(refresh_auth_error(&state, "auth_refresh_replayed"));
    }

    let token_version = load_user_token_version(&state, session.user_id)
        .await
        .map_err(|err| map_refresh_error_with_metrics(&state, err))?;
    let new_refresh_jti = Uuid::now_v7().to_string();
    let new_access_jti = Uuid::now_v7().to_string();
    let access_token = state.ek.sign_access_token_with_jti(
        session.user_id,
        &session.sid,
        token_version,
        &new_access_jti,
        ACCESS_TOKEN_TTL_SECS,
    )?;
    let refresh_token_new = state.ek.sign_refresh_token_with_jti(
        session.user_id,
        &session.sid,
        &session.family_id,
        &new_refresh_jti,
        REFRESH_TOKEN_TTL_SECS,
    )?;

    sqlx::query(
        r#"
        UPDATE auth_refresh_sessions
        SET current_jti = $2,
            rotated_from_jti = $3,
            expires_at = NOW() + ($4 || ' seconds')::interval,
            updated_at = NOW()
        WHERE sid = $1
        "#,
    )
    .bind(&session.sid)
    .bind(&new_refresh_jti)
    .bind(&decoded.jti)
    .bind(REFRESH_TOKEN_TTL_SECS as i64)
    .execute(&mut *tx)
    .await?;
    enqueue_auth_refresh_consistency_set_with_ttl_tx(
        &state,
        &mut *tx,
        "auth:rt:blacklist",
        &decoded.jti,
        "1",
        ttl_from_exp(decoded.exp),
    )
    .await?;
    enqueue_auth_refresh_consistency_set_with_ttl_tx(
        &state,
        &mut *tx,
        "auth:rt:session",
        &session.sid,
        &new_refresh_jti,
        REFRESH_TOKEN_TTL_SECS,
    )
    .await?;
    tx.commit().await?;
    best_effort_set_refresh_blacklist(&state, &decoded.jti, ttl_from_exp(decoded.exp)).await;
    best_effort_set_refresh_session(&state, &session.sid, &new_refresh_jti).await;

    let mut resp_headers = HeaderMap::new();
    set_refresh_cookie_header(
        &mut resp_headers,
        &refresh_token_new,
        REFRESH_TOKEN_TTL_SECS,
    )?;
    state.auth_consistency_metrics.observe_refresh_success();
    tracing::info!(
        sid = %session.sid,
        family_id = %session.family_id,
        user_id = session.user_id,
        decision = "refresh_rotated",
        "auth refresh rotated successfully"
    );
    Ok((
        StatusCode::OK,
        resp_headers,
        Json(RefreshOutput {
            access_token,
            token_type: "Bearer".to_string(),
            expires_in_secs: ACCESS_TOKEN_TTL_SECS,
        }),
    ))
}

#[utoipa::path(
    post,
    path = "/api/auth/logout",
    responses(
        (status = 200, description = "Logout current session", body = LogoutOutput),
        (status = 401, description = "Auth error", body = ErrorOutput),
    ),
    security(("token" = []))
)]
pub(crate) async fn logout_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, AppError> {
    let mut revoked = false;
    if let Some(refresh_token) = extract_refresh_token(&headers) {
        if let Ok(decoded) = state.dk.verify_refresh(&refresh_token) {
            if decoded.user_id == user.id {
                let affected =
                    revoke_family_by_sid(&state, &decoded.sid, user.id, "logout").await?;
                revoked = affected > 0;
                blacklist_refresh_jti(&state, &decoded.jti, ttl_from_exp(decoded.exp)).await?;
            }
        }
    }

    let mut resp_headers = HeaderMap::new();
    clear_refresh_cookie_header(&mut resp_headers)?;
    Ok((StatusCode::OK, resp_headers, Json(LogoutOutput { revoked })))
}

#[utoipa::path(
    post,
    path = "/api/auth/logout-all",
    responses(
        (status = 200, description = "Logout all sessions", body = LogoutAllOutput),
        (status = 401, description = "Auth error", body = ErrorOutput),
    ),
    security(("token" = []))
)]
pub(crate) async fn logout_all_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
) -> Result<impl IntoResponse, AppError> {
    let mut tx = state.pool.begin().await?;
    sqlx::query(
        r#"
        UPDATE users
        SET token_version = token_version + 1
        WHERE id = $1
        "#,
    )
    .bind(user.id)
    .execute(&mut *tx)
    .await?;

    let affected = sqlx::query(
        r#"
        UPDATE auth_refresh_sessions
        SET revoked_at = NOW(), revoke_reason = 'logout_all', updated_at = NOW()
        WHERE user_id = $1 AND revoked_at IS NULL
        "#,
    )
    .bind(user.id)
    .execute(&mut *tx)
    .await?
    .rows_affected() as u64;

    tx.commit().await?;
    invalidate_user_token_version_cache_best_effort(&state, user.id).await;

    let mut resp_headers = HeaderMap::new();
    clear_refresh_cookie_header(&mut resp_headers)?;
    Ok((
        StatusCode::OK,
        resp_headers,
        Json(LogoutAllOutput {
            revoked_count: affected,
        }),
    ))
}

#[utoipa::path(
    get,
    path = "/api/auth/sessions",
    responses(
        (status = 200, description = "List auth sessions", body = ListAuthSessionsOutput),
        (status = 401, description = "Auth error", body = ErrorOutput),
    ),
    security(("token" = []))
)]
pub(crate) async fn list_auth_sessions_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
) -> Result<impl IntoResponse, AppError> {
    let rows: Vec<AuthRefreshSessionRow> = sqlx::query_as(
        r#"
        SELECT
            sid, family_id, user_id, current_jti, rotated_from_jti, expires_at, revoked_at,
            revoke_reason, user_agent, ip_hash, created_at, updated_at
        FROM auth_refresh_sessions
        WHERE user_id = $1
        ORDER BY created_at DESC
        "#,
    )
    .bind(user.id)
    .fetch_all(&state.pool)
    .await?;

    let items = rows
        .into_iter()
        .map(|row| AuthSessionItem {
            sid: row.sid,
            family_id: row.family_id,
            expires_at: row.expires_at,
            revoked_at: row.revoked_at,
            revoke_reason: row.revoke_reason,
            user_agent: row.user_agent,
            ip_hash: row.ip_hash,
            created_at: row.created_at,
            updated_at: row.updated_at,
        })
        .collect();

    Ok((StatusCode::OK, Json(ListAuthSessionsOutput { items })))
}

#[utoipa::path(
    delete,
    path = "/api/auth/sessions/{sid}",
    params(("sid" = String, Path, description = "Session id")),
    responses(
        (status = 200, description = "Revoke session", body = LogoutOutput),
        (status = 401, description = "Auth error", body = ErrorOutput),
    ),
    security(("token" = []))
)]
pub(crate) async fn revoke_auth_session_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(sid): Path<String>,
) -> Result<impl IntoResponse, AppError> {
    let affected = revoke_family_by_sid(&state, &sid, user.id, "manual_revoke").await?;
    Ok((
        StatusCode::OK,
        Json(LogoutOutput {
            revoked: affected > 0,
        }),
    ))
}

fn issue_auth_tokens(
    state: &AppState,
    user: &User,
    token_version: i64,
) -> Result<IssuedTokens, AppError> {
    let sid = Uuid::now_v7().to_string();
    let family_id = Uuid::now_v7().to_string();
    let refresh_jti = Uuid::now_v7().to_string();
    issue_auth_tokens_with_session_ids(state, user, token_version, sid, family_id, refresh_jti)
}

fn issue_auth_tokens_with_session_ids(
    state: &AppState,
    user: &User,
    token_version: i64,
    sid: String,
    family_id: String,
    refresh_jti: String,
) -> Result<IssuedTokens, AppError> {
    let access_jti = Uuid::now_v7().to_string();
    let access_token = state.ek.sign_access_token_with_jti(
        user.id,
        &sid,
        token_version,
        access_jti,
        ACCESS_TOKEN_TTL_SECS,
    )?;
    let refresh_token = state.ek.sign_refresh_token_with_jti(
        user.id,
        &sid,
        &family_id,
        &refresh_jti,
        REFRESH_TOKEN_TTL_SECS,
    )?;

    Ok(IssuedTokens {
        access_token,
        refresh_token,
        sid,
        family_id,
        refresh_jti,
    })
}

async fn persist_refresh_session(
    state: &AppState,
    user: &User,
    issued: &IssuedTokens,
    ctx: &SessionContext,
) -> Result<(), AppError> {
    sqlx::query(
        r#"
        INSERT INTO auth_refresh_sessions(
            user_id, sid, family_id, current_jti, expires_at,
            user_agent, ip_hash, created_at, updated_at
        )
        VALUES (
            $1, $2, $3, $4, NOW() + ($5 || ' seconds')::interval,
            $6, $7, NOW(), NOW()
        )
        "#,
    )
    .bind(user.id)
    .bind(&issued.sid)
    .bind(&issued.family_id)
    .bind(&issued.refresh_jti)
    .bind(REFRESH_TOKEN_TTL_SECS as i64)
    .bind(ctx.user_agent.clone())
    .bind(ctx.ip_hash.clone())
    .execute(&state.pool)
    .await?;
    Ok(())
}

async fn sync_session_state_to_redis(
    state: &AppState,
    issued: &IssuedTokens,
    user_id: i64,
    token_version: i64,
) -> Result<(), AppError> {
    set_refresh_session_in_redis(state, &issued.sid, &issued.refresh_jti).await?;
    set_family_active_in_redis(state, &issued.family_id).await?;
    let add_ret = state
        .redis
        .add_set_member("auth:user:sessions", &user_id.to_string(), &issued.sid)
        .await;
    handle_auth_redis_unit_result(state, add_ret, "auth_refresh_invalid")?;

    let expire_ret = state
        .redis
        .set_key_expire(
            "auth:user:sessions",
            &user_id.to_string(),
            REFRESH_TOKEN_TTL_SECS,
        )
        .await;
    handle_auth_redis_unit_result(state, expire_ret, "auth_refresh_invalid")?;
    cache_user_token_version(state, user_id, token_version).await?;
    Ok(())
}

async fn set_refresh_session_in_redis(
    state: &AppState,
    sid: &str,
    refresh_jti: &str,
) -> Result<(), AppError> {
    let ret = state
        .redis
        .set_value_with_ttl("auth:rt:session", sid, refresh_jti, REFRESH_TOKEN_TTL_SECS)
        .await;
    handle_auth_redis_unit_result(state, ret, "auth_refresh_invalid")
}

async fn set_family_active_in_redis(state: &AppState, family_id: &str) -> Result<(), AppError> {
    let ret = state
        .redis
        .set_value_with_ttl(
            "auth:rt:family",
            family_id,
            "active",
            REFRESH_TOKEN_TTL_SECS,
        )
        .await;
    handle_auth_redis_unit_result(state, ret, "auth_refresh_invalid")
}

async fn is_refresh_blacklisted(state: &AppState, jti: &str) -> Result<bool, AppError> {
    match state.redis.get_value("auth:rt:blacklist", jti).await {
        Ok(ret) => Ok(ret.is_some()),
        Err(err) => {
            if auth_fail_closed_enabled(state) {
                Err(AppError::AuthError(
                    "auth_refresh_degraded_retryable".to_string(),
                ))
            } else {
                tracing::warn!("auth redis blacklist read degraded as fail-open: {}", err);
                Ok(false)
            }
        }
    }
}

async fn blacklist_refresh_jti(state: &AppState, jti: &str, ttl_secs: u64) -> Result<(), AppError> {
    let ttl_secs = ttl_secs.max(AUTH_REFRESH_BLACKLIST_MIN_TTL_SECS);
    let ret = state
        .redis
        .set_value_with_ttl("auth:rt:blacklist", jti, "1", ttl_secs)
        .await;
    handle_auth_redis_unit_result(state, ret, "auth_refresh_invalid")
}

async fn best_effort_set_refresh_blacklist(state: &AppState, jti: &str, ttl_secs: u64) {
    let ttl_secs = ttl_secs.max(AUTH_REFRESH_BLACKLIST_MIN_TTL_SECS);
    let ret = state
        .redis
        .set_value_with_ttl("auth:rt:blacklist", jti, "1", ttl_secs)
        .await;
    if let Err(err) = ret {
        tracing::warn!(
            jti = %jti,
            ttl_secs,
            "best-effort set refresh blacklist failed: {}",
            err
        );
    }
}

async fn best_effort_set_refresh_session(state: &AppState, sid: &str, refresh_jti: &str) {
    let ret = state
        .redis
        .set_value_with_ttl("auth:rt:session", sid, refresh_jti, REFRESH_TOKEN_TTL_SECS)
        .await;
    if let Err(err) = ret {
        tracing::warn!(
            sid = %sid,
            "best-effort set refresh session mapping failed: {}",
            err
        );
    }
}

async fn best_effort_set_refresh_family_revoked(state: &AppState, family_id: &str) {
    let ret = state
        .redis
        .set_value_with_ttl(
            "auth:rt:family",
            family_id,
            "revoked",
            REFRESH_TOKEN_TTL_SECS,
        )
        .await;
    if let Err(err) = ret {
        tracing::warn!(
            family_id = %family_id,
            "best-effort set family revoked failed: {}",
            err
        );
    }
}

async fn enqueue_auth_refresh_consistency_set_with_ttl_tx<'e, E>(
    state: &AppState,
    executor: E,
    scope: &str,
    raw_key: &str,
    value: &str,
    ttl_secs: u64,
) -> Result<(), AppError>
where
    E: Executor<'e, Database = sqlx::Postgres>,
{
    let ttl_secs = ttl_secs.max(1);
    sqlx::query(
        r#"
        INSERT INTO auth_refresh_consistency_outbox_jobs(
            op_type, scope, raw_key, value, ttl_secs, attempts, next_retry_at, locked_until, last_error, created_at, updated_at
        )
        VALUES ($1, $2, $3, $4, $5, 0, NOW(), NULL, NULL, NOW(), NOW())
        "#,
    )
    .bind(AuthRefreshOutboxOp::SetWithTtl.as_str())
    .bind(scope)
    .bind(raw_key)
    .bind(value)
    .bind(ttl_secs as i64)
    .execute(executor)
    .await?;
    let depth = get_auth_refresh_consistency_outbox_queue_depth(&state.pool)
        .await
        .unwrap_or(0);
    state
        .auth_consistency_metrics
        .observe_refresh_outbox_enqueued(depth);
    Ok(())
}

async fn cache_user_token_version(
    state: &AppState,
    user_id: i64,
    token_version: i64,
) -> Result<(), AppError> {
    let ret = state
        .redis
        .set_value_with_ttl(
            "auth:user:token_version",
            &user_id.to_string(),
            &token_version.to_string(),
            REFRESH_TOKEN_TTL_SECS,
        )
        .await;
    handle_auth_redis_unit_result(state, ret, "auth_refresh_invalid")
}

async fn invalidate_user_token_version_cache_best_effort(state: &AppState, user_id: i64) {
    match state
        .redis
        .delete_key("auth:user:token_version", &user_id.to_string())
        .await
    {
        Ok(_) => {
            state.auth_consistency_metrics.observe_immediate_success();
        }
        Err(err) => {
            state.auth_consistency_metrics.observe_immediate_failure();
            let enqueue_ret = state
                .enqueue_auth_token_version_invalidation_retry(user_id)
                .await;
            match enqueue_ret {
                Ok(_) => tracing::warn!(
                    "auth token_version cache invalidation failed, queued retry: user_id={}, err={}",
                    user_id,
                    err
                ),
                Err(queue_err) => tracing::warn!(
                    "auth token_version cache invalidation failed and enqueue retry failed: user_id={}, err={}, enqueue_err={}",
                    user_id,
                    err,
                    queue_err
                ),
            }
        }
    }
}

impl AppState {
    pub(crate) fn get_auth_consistency_metrics(&self) -> GetAuthConsistencyMetricsOutput {
        self.auth_consistency_metrics.snapshot()
    }

    pub(crate) async fn enqueue_auth_token_version_invalidation_retry(
        &self,
        user_id: i64,
    ) -> Result<(), AppError> {
        let mut tx = self.pool.begin().await?;

        let mut overflow_drop = false;
        let depth_before = get_auth_token_version_invalidation_queue_depth(&mut *tx).await?;
        if depth_before >= AUTH_TOKEN_VERSION_INVALIDATION_RETRY_QUEUE_MAX as u64 {
            let dropped_user_id: Option<i64> = sqlx::query_scalar(
                r#"
                WITH candidate AS (
                    SELECT user_id
                    FROM auth_token_version_invalidation_jobs
                    ORDER BY next_retry_at ASC, created_at ASC, user_id ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                DELETE FROM auth_token_version_invalidation_jobs q
                USING candidate c
                WHERE q.user_id = c.user_id
                RETURNING q.user_id
                "#,
            )
            .fetch_optional(&mut *tx)
            .await?;
            overflow_drop = dropped_user_id.is_some();
        }

        let inserted_user_id: Option<i64> = sqlx::query_scalar(
            r#"
            INSERT INTO auth_token_version_invalidation_jobs(
                user_id, attempts, next_retry_at, locked_until, last_error, created_at, updated_at
            )
            VALUES ($1, 0, NOW(), NULL, NULL, NOW(), NOW())
            ON CONFLICT (user_id) DO NOTHING
            RETURNING user_id
            "#,
        )
        .bind(user_id)
        .fetch_optional(&mut *tx)
        .await?;

        let depth_after = get_auth_token_version_invalidation_queue_depth(&mut *tx).await?;
        tx.commit().await?;

        if overflow_drop {
            self.auth_consistency_metrics
                .observe_retry_overflow_drop(depth_after);
        }
        if inserted_user_id.is_some() {
            self.auth_consistency_metrics
                .observe_retry_enqueued(depth_after);
        } else {
            self.auth_consistency_metrics
                .observe_retry_dedup(depth_after);
        }
        Ok(())
    }

    pub(crate) async fn retry_auth_token_version_invalidation_queue_once(
        &self,
        batch_size: usize,
    ) -> Result<AuthTokenVersionInvalidationRetryReport, AppError> {
        let run = async {
            let claimed = claim_auth_token_version_invalidation_jobs(
                &self.pool,
                batch_size.max(1) as i64,
            )
            .await?;
            let mut report = AuthTokenVersionInvalidationRetryReport {
                attempted: claimed.len(),
                ..Default::default()
            };

            for job in claimed {
                match self
                    .redis
                    .delete_key("auth:user:token_version", &job.user_id.to_string())
                    .await
                {
                    Ok(_) => {
                        delete_auth_token_version_invalidation_job(&self.pool, job.user_id).await?;
                        report.succeeded += 1;
                    }
                    Err(err) => {
                        let sanitized =
                            sanitize_auth_token_version_invalidation_error(&err.to_string());
                        if job.attempts >= AUTH_TOKEN_VERSION_INVALIDATION_RETRY_MAX_ATTEMPTS {
                            delete_auth_token_version_invalidation_job(&self.pool, job.user_id)
                                .await?;
                            report.dropped += 1;
                            tracing::warn!(
                                "drop auth token_version invalidation retry after max attempts: user_id={}, attempts={}, err={}",
                                job.user_id,
                                job.attempts,
                                sanitized
                            );
                        } else {
                            let backoff_ms =
                                auth_token_version_invalidation_retry_backoff_ms(job.attempts);
                            reschedule_auth_token_version_invalidation_job(
                                &self.pool,
                                job.user_id,
                                backoff_ms,
                                &sanitized,
                            )
                            .await?;
                            report.requeued += 1;
                        }
                    }
                }
            }

            let queue_depth = get_auth_token_version_invalidation_queue_depth(&self.pool).await?;
            self.auth_consistency_metrics
                .observe_retry_tick(report, queue_depth);
            Ok(report)
        }
        .await;

        if let Err(err) = &run {
            self.auth_consistency_metrics.observe_retry_tick_error();
            tracing::warn!(
                "auth token_version invalidation retry worker tick failed: {}",
                err
            );
            if let Ok(depth) = get_auth_token_version_invalidation_queue_depth(&self.pool).await {
                self.auth_consistency_metrics.observe_queue_depth(depth);
            }
        }
        run
    }

    pub(crate) async fn retry_auth_refresh_consistency_outbox_once(
        &self,
        batch_size: usize,
    ) -> Result<AuthRefreshConsistencyOutboxRetryReport, AppError> {
        let run = async {
            let claimed =
                claim_auth_refresh_consistency_outbox_jobs(&self.pool, batch_size.max(1) as i64)
                    .await?;
            let mut report = AuthRefreshConsistencyOutboxRetryReport {
                attempted: claimed.len(),
                ..Default::default()
            };

            for job in claimed {
                let op = AuthRefreshOutboxOp::parse(&job.op_type)
                    .ok_or_else(|| anyhow::anyhow!("unknown auth refresh outbox op_type"))?;
                let apply_result = match op {
                    AuthRefreshOutboxOp::SetWithTtl => {
                        self.redis
                            .set_value_with_ttl(
                                &job.scope,
                                &job.raw_key,
                                &job.value,
                                job.ttl_secs.max(1) as u64,
                            )
                            .await
                    }
                };
                match apply_result {
                    Ok(_) => {
                        delete_auth_refresh_consistency_outbox_job(&self.pool, job.id).await?;
                        report.delivered += 1;
                    }
                    Err(err) => {
                        let sanitized =
                            sanitize_auth_refresh_consistency_outbox_error(&err.to_string());
                        if job.attempts >= AUTH_REFRESH_OUTBOX_MAX_ATTEMPTS {
                            delete_auth_refresh_consistency_outbox_job(&self.pool, job.id).await?;
                            report.dropped += 1;
                            tracing::warn!(
                                job_id = job.id,
                                attempts = job.attempts,
                                "drop auth refresh outbox job after max attempts: {}",
                                sanitized
                            );
                        } else {
                            let backoff_ms = auth_refresh_outbox_retry_backoff_ms(job.attempts);
                            reschedule_auth_refresh_consistency_outbox_job(
                                &self.pool, job.id, backoff_ms, &sanitized,
                            )
                            .await?;
                            report.requeued += 1;
                        }
                    }
                }
            }

            let depth = get_auth_refresh_consistency_outbox_queue_depth(&self.pool).await?;
            self.auth_consistency_metrics.observe_refresh_outbox_tick(
                report.delivered,
                report.requeued,
                report.dropped,
                depth,
            );
            Ok(report)
        }
        .await;

        if let Err(err) = &run {
            self.auth_consistency_metrics
                .observe_refresh_outbox_tick_error();
            tracing::warn!(
                "auth refresh consistency outbox retry worker tick failed: {}",
                err
            );
            if let Ok(depth) = get_auth_refresh_consistency_outbox_queue_depth(&self.pool).await {
                self.auth_consistency_metrics
                    .observe_refresh_outbox_depth(depth);
            }
        }
        run
    }
}

async fn get_auth_token_version_invalidation_queue_depth<'e, E>(
    executor: E,
) -> Result<u64, AppError>
where
    E: Executor<'e, Database = sqlx::Postgres>,
{
    let depth: i64 =
        sqlx::query_scalar("SELECT COUNT(*)::bigint FROM auth_token_version_invalidation_jobs")
            .fetch_one(executor)
            .await?;
    Ok(depth.max(0) as u64)
}

async fn claim_auth_token_version_invalidation_jobs(
    pool: &sqlx::PgPool,
    batch_size: i64,
) -> Result<Vec<ClaimedAuthTokenVersionInvalidationJob>, AppError> {
    let rows = sqlx::query_as::<_, ClaimedAuthTokenVersionInvalidationJob>(
        r#"
        WITH due AS (
            SELECT user_id
            FROM auth_token_version_invalidation_jobs
            WHERE next_retry_at <= NOW()
              AND (locked_until IS NULL OR locked_until <= NOW())
            ORDER BY next_retry_at ASC, created_at ASC, user_id ASC
            LIMIT $1
            FOR UPDATE SKIP LOCKED
        )
        UPDATE auth_token_version_invalidation_jobs q
        SET attempts = q.attempts + 1,
            locked_until = NOW() + ($2::bigint * INTERVAL '1 second'),
            updated_at = NOW()
        FROM due
        WHERE q.user_id = due.user_id
        RETURNING q.user_id, q.attempts
        "#,
    )
    .bind(batch_size.max(1))
    .bind(AUTH_TOKEN_VERSION_INVALIDATION_RETRY_LOCK_SECS)
    .fetch_all(pool)
    .await?;
    Ok(rows)
}

async fn delete_auth_token_version_invalidation_job(
    pool: &sqlx::PgPool,
    user_id: i64,
) -> Result<(), AppError> {
    sqlx::query("DELETE FROM auth_token_version_invalidation_jobs WHERE user_id = $1")
        .bind(user_id)
        .execute(pool)
        .await?;
    Ok(())
}

async fn reschedule_auth_token_version_invalidation_job(
    pool: &sqlx::PgPool,
    user_id: i64,
    backoff_ms: u64,
    last_error: &str,
) -> Result<(), AppError> {
    sqlx::query(
        r#"
        UPDATE auth_token_version_invalidation_jobs
        SET next_retry_at = NOW() + ($2::bigint * INTERVAL '1 millisecond'),
            locked_until = NULL,
            last_error = $3,
            updated_at = NOW()
        WHERE user_id = $1
        "#,
    )
    .bind(user_id)
    .bind(backoff_ms as i64)
    .bind(last_error)
    .execute(pool)
    .await?;
    Ok(())
}

fn auth_token_version_invalidation_retry_backoff_ms(attempts: i32) -> u64 {
    let attempt = attempts.max(1) as u32;
    let pow = attempt.saturating_sub(1).min(16);
    let scaled = AUTH_TOKEN_VERSION_INVALIDATION_RETRY_BASE_BACKOFF_MS.saturating_mul(1_u64 << pow);
    scaled.clamp(1, AUTH_TOKEN_VERSION_INVALIDATION_RETRY_MAX_BACKOFF_MS)
}

fn sanitize_auth_token_version_invalidation_error(raw: &str) -> String {
    let mut text = raw.trim().to_string();
    if text.len() > AUTH_TOKEN_VERSION_INVALIDATION_ERROR_MAX_LEN {
        text.truncate(AUTH_TOKEN_VERSION_INVALIDATION_ERROR_MAX_LEN);
    }
    text
}

async fn get_auth_refresh_consistency_outbox_queue_depth<'e, E>(
    executor: E,
) -> Result<u64, AppError>
where
    E: Executor<'e, Database = sqlx::Postgres>,
{
    let depth: i64 = sqlx::query_scalar(
        "SELECT COUNT(*)::bigint FROM auth_refresh_consistency_outbox_jobs WHERE delivered_at IS NULL",
    )
    .fetch_one(executor)
    .await?;
    Ok(depth.max(0) as u64)
}

async fn claim_auth_refresh_consistency_outbox_jobs(
    pool: &sqlx::PgPool,
    batch_size: i64,
) -> Result<Vec<ClaimedAuthRefreshConsistencyOutboxJob>, AppError> {
    let rows = sqlx::query_as::<_, ClaimedAuthRefreshConsistencyOutboxJob>(
        r#"
        WITH due AS (
            SELECT id
            FROM auth_refresh_consistency_outbox_jobs
            WHERE delivered_at IS NULL
              AND next_retry_at <= NOW()
              AND (locked_until IS NULL OR locked_until <= NOW())
            ORDER BY next_retry_at ASC, created_at ASC, id ASC
            LIMIT $1
            FOR UPDATE SKIP LOCKED
        )
        UPDATE auth_refresh_consistency_outbox_jobs q
        SET attempts = q.attempts + 1,
            locked_until = NOW() + ($2::bigint * INTERVAL '1 second'),
            updated_at = NOW()
        FROM due
        WHERE q.id = due.id
        RETURNING q.id, q.op_type, q.scope, q.raw_key, q.value, q.ttl_secs, q.attempts
        "#,
    )
    .bind(batch_size.max(1))
    .bind(AUTH_REFRESH_OUTBOX_LOCK_SECS.max(1))
    .fetch_all(pool)
    .await?;
    Ok(rows)
}

async fn delete_auth_refresh_consistency_outbox_job(
    pool: &sqlx::PgPool,
    id: i64,
) -> Result<(), AppError> {
    sqlx::query("DELETE FROM auth_refresh_consistency_outbox_jobs WHERE id = $1")
        .bind(id)
        .execute(pool)
        .await?;
    Ok(())
}

async fn reschedule_auth_refresh_consistency_outbox_job(
    pool: &sqlx::PgPool,
    id: i64,
    backoff_ms: u64,
    last_error: &str,
) -> Result<(), AppError> {
    sqlx::query(
        r#"
        UPDATE auth_refresh_consistency_outbox_jobs
        SET next_retry_at = NOW() + ($2::bigint * INTERVAL '1 millisecond'),
            locked_until = NULL,
            last_error = $3,
            updated_at = NOW()
        WHERE id = $1
        "#,
    )
    .bind(id)
    .bind(backoff_ms as i64)
    .bind(last_error)
    .execute(pool)
    .await?;
    Ok(())
}

fn auth_refresh_outbox_retry_backoff_ms(attempts: i32) -> u64 {
    let attempt = attempts.max(1) as u32;
    let pow = attempt.saturating_sub(1).min(16);
    let scaled = AUTH_REFRESH_OUTBOX_BASE_BACKOFF_MS.saturating_mul(1_u64 << pow);
    scaled.clamp(1, AUTH_REFRESH_OUTBOX_MAX_BACKOFF_MS)
}

fn sanitize_auth_refresh_consistency_outbox_error(raw: &str) -> String {
    let mut text = raw.trim().to_string();
    if text.len() > AUTH_REFRESH_OUTBOX_ERROR_MAX_LEN {
        text.truncate(AUTH_REFRESH_OUTBOX_ERROR_MAX_LEN);
    }
    text
}

pub(crate) async fn load_user_token_version(
    state: &AppState,
    user_id: i64,
) -> Result<i64, AppError> {
    if let Ok(Some(cached)) = state
        .redis
        .get_value("auth:user:token_version", &user_id.to_string())
        .await
    {
        if let Ok(parsed) = cached.trim().parse::<i64>() {
            return Ok(parsed.max(0));
        }
    }

    let value: Option<i64> = sqlx::query_scalar("SELECT token_version FROM users WHERE id = $1")
        .bind(user_id)
        .fetch_optional(&state.pool)
        .await?;
    let token_version = value.unwrap_or(0).max(0);
    let _ = cache_user_token_version(state, user_id, token_version).await;
    Ok(token_version)
}

pub(crate) async fn ensure_access_session_active(
    state: &AppState,
    user_id: i64,
    sid: &str,
) -> Result<(), AppError> {
    let row: Option<(Option<DateTime<Utc>>, DateTime<Utc>, String)> = sqlx::query_as(
        r#"
        SELECT revoked_at, expires_at, current_jti
        FROM auth_refresh_sessions
        WHERE sid = $1 AND user_id = $2
        "#,
    )
    .bind(sid)
    .bind(user_id)
    .fetch_optional(&state.pool)
    .await?;

    let Some((revoked_at, expires_at, current_jti)) = row else {
        return Err(AppError::AuthError("auth_session_revoked".to_string()));
    };
    if revoked_at.is_some() || expires_at <= Utc::now() {
        return Err(AppError::AuthError("auth_session_revoked".to_string()));
    }

    let _ = set_refresh_session_in_redis(state, sid, &current_jti).await;
    Ok(())
}

async fn revoke_family_by_id(
    state: &AppState,
    family_id: &str,
    reason: &str,
) -> Result<u64, AppError> {
    let mut tx = state.pool.begin().await?;
    let affected = sqlx::query(
        r#"
        UPDATE auth_refresh_sessions
        SET revoked_at = NOW(), revoke_reason = $2, updated_at = NOW()
        WHERE family_id = $1 AND revoked_at IS NULL
        "#,
    )
    .bind(family_id)
    .bind(reason)
    .execute(&mut *tx)
    .await?
    .rows_affected() as u64;
    enqueue_auth_refresh_consistency_set_with_ttl_tx(
        state,
        &mut *tx,
        "auth:rt:family",
        family_id,
        "revoked",
        REFRESH_TOKEN_TTL_SECS,
    )
    .await?;
    tx.commit().await?;
    best_effort_set_refresh_family_revoked(state, family_id).await;
    Ok(affected)
}

async fn revoke_family_by_sid(
    state: &AppState,
    sid: &str,
    user_id: i64,
    reason: &str,
) -> Result<u64, AppError> {
    let family_id: Option<String> = sqlx::query_scalar(
        r#"
        SELECT family_id
        FROM auth_refresh_sessions
        WHERE sid = $1 AND user_id = $2
        "#,
    )
    .bind(sid)
    .bind(user_id)
    .fetch_optional(&state.pool)
    .await?;

    let Some(family_id) = family_id else {
        return Ok(0);
    };

    let affected = revoke_family_by_id(state, &family_id, reason).await?;
    let _ = state
        .redis
        .remove_set_member("auth:user:sessions", &user_id.to_string(), sid)
        .await;
    let _ = state.redis.delete_key("auth:rt:session", sid).await;
    Ok(affected)
}

async fn issue_auth_success_response(
    state: &AppState,
    headers: &HeaderMap,
    user: User,
    status: StatusCode,
) -> Result<(StatusCode, HeaderMap, AuthOutput), AppError> {
    let ctx = session_context_from_headers(headers);
    let token_version = load_user_token_version(state, user.id).await?;
    let issued = issue_auth_tokens(state, &user, token_version)?;
    persist_refresh_session(state, &user, &issued, &ctx).await?;
    finalize_auth_success_response(state, user, status, issued, token_version).await
}

async fn finalize_auth_success_response(
    state: &AppState,
    user: User,
    status: StatusCode,
    issued: IssuedTokens,
    token_version: i64,
) -> Result<(StatusCode, HeaderMap, AuthOutput), AppError> {
    sync_session_state_to_redis(state, &issued, user.id, token_version).await?;
    let mut resp_headers = HeaderMap::new();
    set_refresh_cookie_header(
        &mut resp_headers,
        &issued.refresh_token,
        REFRESH_TOKEN_TTL_SECS,
    )?;
    Ok((
        status,
        resp_headers,
        AuthOutput {
            access_token: issued.access_token,
            token_type: "Bearer".to_string(),
            expires_in_secs: ACCESS_TOKEN_TTL_SECS,
            user,
        },
    ))
}

fn merge_headers(mut base: HeaderMap, extra: HeaderMap) -> HeaderMap {
    for (name, value) in extra.into_iter() {
        if let Some(name) = name {
            base.append(name, value);
        }
    }
    base
}

async fn enforce_auth_rate_limit(
    state: &AppState,
    scope: &str,
    key: &str,
    limit: u64,
    window_secs: u64,
) -> Result<crate::RateLimitDecision, AppError> {
    match state
        .redis
        .check_rate_limit(scope, key, limit, window_secs)
        .await
    {
        Ok(v) => Ok(v),
        Err(err) => {
            if auth_fail_closed_enabled(state) {
                tracing::warn!(
                    "auth v2 rate limit failed under fail-closed, scope={}, key={}, err={}",
                    scope,
                    key,
                    err
                );
                return Err(AppError::AuthError(
                    "auth_sms_send_rate_limited".to_string(),
                ));
            }
            tracing::warn!(
                "auth v2 rate limit degraded as fail-open, scope={}, key={}, err={}",
                scope,
                key,
                err
            );
            let now = now_epoch_secs();
            Ok(crate::RateLimitDecision {
                allowed: true,
                limit,
                remaining: limit,
                reset_at_epoch_secs: now + window_secs.max(1),
            })
        }
    }
}

async fn sms_code_cooldown_active(
    state: &AppState,
    scene: SmsScene,
    phone_e164: &str,
) -> Result<bool, AppError> {
    let scope = format!("auth:sms:cooldown:{}", scene.as_str());
    if redis_is_disabled(state) {
        let entry = fallback_get_sms_entry(scene, phone_e164);
        if let Some(entry) = entry {
            return Ok(entry.cooldown_until_epoch_secs > now_epoch_secs());
        }
        return Ok(false);
    }
    match state.redis.get_value(&scope, phone_e164).await {
        Ok(v) => Ok(v.is_some()),
        Err(err) => {
            if auth_fail_closed_enabled(state) {
                tracing::warn!("sms cooldown read failed under fail-closed: {}", err);
                return Err(AppError::AuthError(
                    "auth_sms_send_rate_limited".to_string(),
                ));
            }
            tracing::warn!("sms cooldown read degraded as fail-open: {}", err);
            Ok(false)
        }
    }
}

async fn store_sms_code(
    state: &AppState,
    scene: SmsScene,
    phone_e164: &str,
    code: &str,
) -> Result<(), AppError> {
    if redis_is_disabled(state) {
        fallback_set_sms_entry(scene, phone_e164, code);
        return Ok(());
    }
    let code_scope = format!("auth:sms:code:{}", scene.as_str());
    let cooldown_scope = format!("auth:sms:cooldown:{}", scene.as_str());
    let attempt_scope = format!("auth:sms:attempt:{}", scene.as_str());

    let code_ret = state
        .redis
        .set_value_with_ttl(&code_scope, phone_e164, code, SMS_CODE_TTL_SECS)
        .await;
    let cooldown_ret = state
        .redis
        .set_value_with_ttl(&cooldown_scope, phone_e164, "1", SMS_COOLDOWN_SECS.max(1))
        .await;
    let clear_attempt_ret = state.redis.delete_key(&attempt_scope, phone_e164).await;

    let code_ok = code_ret.is_ok() && cooldown_ret.is_ok() && clear_attempt_ret.is_ok();
    if code_ok {
        return Ok(());
    }
    if auth_fail_closed_enabled(state) {
        return Err(AppError::AuthError(
            "auth_sms_send_rate_limited".to_string(),
        ));
    }
    tracing::warn!(
        "sms code redis write degraded as fallback, code_ret={:?}, cooldown_ret={:?}, clear_attempt_ret={:?}",
        code_ret.err(),
        cooldown_ret.err(),
        clear_attempt_ret.err(),
    );
    fallback_set_sms_entry(scene, phone_e164, code);
    Ok(())
}

async fn verify_sms_code(
    state: &AppState,
    scene: SmsScene,
    phone_e164: &str,
    sms_code: &str,
    user_id: Option<i64>,
) -> Result<(), AppError> {
    let sms_code = sms_code.trim();
    let decision = if redis_is_disabled(state) {
        verify_sms_code_via_fallback_store(scene, phone_e164, sms_code)
    } else {
        let verify_ret = state
            .redis
            .verify_sms_code_atomically(
                &format!("auth:sms:code:{}", scene.as_str()),
                &format!("auth:sms:attempt:{}", scene.as_str()),
                phone_e164,
                sms_code,
                SMS_MAX_FAILED_ATTEMPTS,
                SMS_CODE_TTL_SECS,
            )
            .await;
        match verify_ret {
            Ok(decision) => decision,
            Err(err) => {
                if auth_fail_closed_enabled(state) {
                    tracing::warn!("sms verify failed under fail-closed: {}", err);
                    return Err(AppError::AuthError("auth_sms_code_invalid".to_string()));
                }
                tracing::warn!("sms verify degraded as fallback: {}", err);
                verify_sms_code_via_fallback_store(scene, phone_e164, sms_code)
            }
        }
    };

    match decision {
        SmsCodeVerifyDecision::Expired => {
            insert_sms_audit_log_best_effort(
                state,
                SmsAuditLogInput {
                    phone_e164,
                    scene,
                    action: "verify",
                    result: "failed",
                    reason: Some("expired"),
                    request_ip_hash: None,
                    code_plain: None,
                    user_id,
                },
            )
            .await;
            Err(AppError::AuthError("auth_sms_code_expired".to_string()))
        }
        SmsCodeVerifyDecision::Invalid => {
            insert_sms_audit_log_best_effort(
                state,
                SmsAuditLogInput {
                    phone_e164,
                    scene,
                    action: "verify",
                    result: "failed",
                    reason: Some("invalid"),
                    request_ip_hash: None,
                    code_plain: Some(sms_code),
                    user_id,
                },
            )
            .await;
            Err(AppError::AuthError("auth_sms_code_invalid".to_string()))
        }
        SmsCodeVerifyDecision::Exhausted => {
            insert_sms_audit_log_best_effort(
                state,
                SmsAuditLogInput {
                    phone_e164,
                    scene,
                    action: "verify",
                    result: "failed",
                    reason: Some("invalid"),
                    request_ip_hash: None,
                    code_plain: Some(sms_code),
                    user_id,
                },
            )
            .await;
            Err(AppError::AuthError("auth_sms_code_expired".to_string()))
        }
        SmsCodeVerifyDecision::Passed => {
            insert_sms_audit_log_best_effort(
                state,
                SmsAuditLogInput {
                    phone_e164,
                    scene,
                    action: "verify",
                    result: "passed",
                    reason: None,
                    request_ip_hash: None,
                    code_plain: Some(sms_code),
                    user_id,
                },
            )
            .await;
            Ok(())
        }
    }
}

fn verify_sms_code_via_fallback_store(
    scene: SmsScene,
    phone_e164: &str,
    sms_code: &str,
) -> SmsCodeVerifyDecision {
    let key = build_sms_fallback_key(scene, phone_e164);
    let now = now_epoch_secs();
    let mut map = SMS_FALLBACK_STORE.lock().expect("lock sms fallback store");
    let Some(entry) = map.get_mut(&key) else {
        return SmsCodeVerifyDecision::Expired;
    };
    if entry.expires_at_epoch_secs <= now {
        map.remove(&key);
        return SmsCodeVerifyDecision::Expired;
    }
    if entry.code != sms_code {
        entry.failed_attempts += 1;
        if entry.failed_attempts >= SMS_MAX_FAILED_ATTEMPTS {
            map.remove(&key);
            return SmsCodeVerifyDecision::Exhausted;
        }
        return SmsCodeVerifyDecision::Invalid;
    }
    map.remove(&key);
    SmsCodeVerifyDecision::Passed
}

async fn insert_sms_audit_log(
    state: &AppState,
    entry: SmsAuditLogInput<'_>,
) -> Result<(), AppError> {
    let code_hash = entry.code_plain.map(hash_with_sha1);
    sqlx::query(
        r#"
        INSERT INTO auth_sms_audit_logs(
            phone_e164, scene, provider, action, result, reason, request_ip_hash, code_hash, user_id
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        "#,
    )
    .bind(entry.phone_e164)
    .bind(entry.scene.as_str())
    .bind(sms_provider_name())
    .bind(entry.action)
    .bind(entry.result)
    .bind(entry.reason)
    .bind(entry.request_ip_hash)
    .bind(code_hash)
    .bind(entry.user_id)
    .execute(&state.pool)
    .await?;
    Ok(())
}

async fn insert_sms_audit_log_best_effort(state: &AppState, entry: SmsAuditLogInput<'_>) {
    if let Err(err) = insert_sms_audit_log(state, entry).await {
        tracing::warn!(
            "sms audit log write failed and degraded as best-effort: {}",
            err
        );
    }
}

fn hash_with_sha1(input: &str) -> String {
    let mut hasher = Sha1::new();
    hasher.update(input.as_bytes());
    format!("{:x}", hasher.finalize())
}

async fn store_wechat_challenge(
    state: &AppState,
    nonce: &str,
    state_value: &str,
) -> Result<(), AppError> {
    if redis_is_disabled(state) {
        fallback_set_wechat_challenge(nonce, state_value);
        return Ok(());
    }
    let ret = state
        .redis
        .set_value_with_ttl(
            "auth:wechat:challenge",
            nonce,
            state_value,
            WECHAT_CHALLENGE_TTL_SECS,
        )
        .await;
    match ret {
        Ok(_) => Ok(()),
        Err(err) => {
            if auth_fail_closed_enabled(state) {
                tracing::warn!("wechat challenge write failed under fail-closed: {}", err);
                return Err(AppError::AuthError("auth_wechat_state_invalid".to_string()));
            }
            tracing::warn!("wechat challenge write degraded as fallback: {}", err);
            fallback_set_wechat_challenge(nonce, state_value);
            Ok(())
        }
    }
}

async fn verify_wechat_challenge_state(
    state: &AppState,
    state_value: &str,
) -> Result<(), AppError> {
    let nonce = extract_nonce_from_wechat_state(state_value)
        .ok_or_else(|| AppError::AuthError("auth_wechat_state_invalid".to_string()))?;
    if redis_is_disabled(state) {
        let fallback = fallback_take_wechat_challenge(&nonce);
        if fallback.as_deref() == Some(state_value) {
            return Ok(());
        }
        return Err(AppError::AuthError("auth_wechat_state_invalid".to_string()));
    }
    match state.redis.get_value("auth:wechat:challenge", &nonce).await {
        Ok(Some(expected)) if expected == state_value => {
            let _ = state
                .redis
                .delete_key("auth:wechat:challenge", &nonce)
                .await;
            Ok(())
        }
        Ok(_) => Err(AppError::AuthError("auth_wechat_state_invalid".to_string())),
        Err(err) => {
            if auth_fail_closed_enabled(state) {
                tracing::warn!("wechat challenge read failed under fail-closed: {}", err);
                return Err(AppError::AuthError("auth_wechat_state_invalid".to_string()));
            }
            let fallback = fallback_take_wechat_challenge(&nonce);
            if fallback.as_deref() == Some(state_value) {
                return Ok(());
            }
            Err(AppError::AuthError("auth_wechat_state_invalid".to_string()))
        }
    }
}

async fn store_wechat_bind_ticket(
    state: &AppState,
    ticket: &str,
    payload: &WechatBindTicketPayload,
) -> Result<(), AppError> {
    let payload_json = serde_json::to_string(payload).map_err(anyhow::Error::from)?;
    if redis_is_disabled(state) {
        fallback_set_wechat_bind_ticket(ticket, &payload_json);
        return Ok(());
    }
    let ret = state
        .redis
        .set_value_with_ttl(
            "auth:wechat:ticket",
            ticket,
            &payload_json,
            WECHAT_BIND_TICKET_TTL_SECS,
        )
        .await;
    match ret {
        Ok(_) => Ok(()),
        Err(err) => {
            if auth_fail_closed_enabled(state) {
                tracing::warn!("wechat bind ticket write failed under fail-closed: {}", err);
                return Err(AppError::AuthError("auth_wechat_bind_required".to_string()));
            }
            tracing::warn!("wechat bind ticket write degraded as fallback: {}", err);
            fallback_set_wechat_bind_ticket(ticket, &payload_json);
            Ok(())
        }
    }
}

async fn load_wechat_bind_ticket(
    state: &AppState,
    ticket: &str,
) -> Result<Option<WechatBindTicketPayload>, AppError> {
    if redis_is_disabled(state) {
        let raw = fallback_take_wechat_bind_ticket(ticket);
        return match raw {
            Some(v) => Ok(Some(serde_json::from_str(&v).map_err(anyhow::Error::from)?)),
            None => Ok(None),
        };
    }
    match state.redis.get_value("auth:wechat:ticket", ticket).await {
        Ok(Some(value)) => {
            let _ = state.redis.delete_key("auth:wechat:ticket", ticket).await;
            Ok(Some(
                serde_json::from_str(&value).map_err(anyhow::Error::from)?,
            ))
        }
        Ok(None) => Ok(None),
        Err(err) => {
            if auth_fail_closed_enabled(state) {
                tracing::warn!("wechat bind ticket read failed under fail-closed: {}", err);
                return Err(AppError::AuthError("auth_wechat_bind_required".to_string()));
            }
            let raw = fallback_take_wechat_bind_ticket(ticket);
            match raw {
                Some(v) => Ok(Some(serde_json::from_str(&v).map_err(anyhow::Error::from)?)),
                None => Ok(None),
            }
        }
    }
}

async fn find_user_by_wechat_identity(
    state: &AppState,
    identity: &WechatIdentity,
) -> Result<Option<User>, AppError> {
    let user: Option<User> = sqlx::query_as(
        r#"
        SELECT
            u.id, u.fullname, COALESCE(u.email, '') AS email,
            u.phone_e164, u.phone_verified_at, u.phone_bind_required, u.is_bot, u.created_at
        FROM auth_external_identities i
        JOIN users u ON u.id = i.user_id
        WHERE i.provider = $1
          AND (
            i.provider_user_id = $2
            OR ($3::varchar IS NOT NULL AND i.provider_unionid = $3)
          )
        ORDER BY i.updated_at DESC
        LIMIT 1
        "#,
    )
    .bind(WECHAT_PROVIDER)
    .bind(&identity.provider_user_id)
    .bind(identity.provider_unionid.as_deref())
    .fetch_optional(&state.pool)
    .await?;
    Ok(user)
}

async fn upsert_wechat_identity_for_user(
    state: &AppState,
    user_id: i64,
    provider_user_id: &str,
    provider_unionid: Option<&str>,
) -> Result<(), AppError> {
    if let Some(unionid) = provider_unionid {
        let union_owner: Option<i64> = sqlx::query_scalar(
            r#"
            SELECT user_id
            FROM auth_external_identities
            WHERE provider = $1 AND provider_unionid = $2
            "#,
        )
        .bind(WECHAT_PROVIDER)
        .bind(unionid)
        .fetch_optional(&state.pool)
        .await?;
        if let Some(owner) = union_owner {
            if owner != user_id {
                return Err(AppError::AuthError(
                    "auth_wechat_identity_conflict".to_string(),
                ));
            }
        }
    }

    sqlx::query(
        r#"
        INSERT INTO auth_external_identities(
            provider, provider_user_id, provider_unionid, app_id, user_id, created_at, updated_at
        )
        VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
        ON CONFLICT (provider, provider_user_id)
        DO UPDATE
        SET provider_unionid = EXCLUDED.provider_unionid,
            app_id = EXCLUDED.app_id,
            user_id = EXCLUDED.user_id,
            updated_at = NOW()
        "#,
    )
    .bind(WECHAT_PROVIDER)
    .bind(provider_user_id)
    .bind(provider_unionid)
    .bind(wechat_app_id())
    .bind(user_id)
    .execute(&state.pool)
    .await?;
    Ok(())
}

fn session_context_from_headers(headers: &HeaderMap) -> SessionContext {
    SessionContext {
        user_agent: headers
            .get(header::USER_AGENT)
            .and_then(|v| v.to_str().ok())
            .map(str::trim)
            .filter(|v| !v.is_empty())
            .map(|v| v.chars().take(512).collect()),
        ip_hash: extract_ip_hash(headers),
    }
}

fn extract_ip_hash(headers: &HeaderMap) -> Option<String> {
    let raw_ip = headers
        .get("x-forwarded-for")
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.split(',').next())
        .map(str::trim)
        .filter(|v| !v.is_empty())
        .or_else(|| {
            headers
                .get("x-real-ip")
                .and_then(|v| v.to_str().ok())
                .map(str::trim)
                .filter(|v| !v.is_empty())
        })?;

    let mut hasher = Sha1::new();
    hasher.update(raw_ip.as_bytes());
    Some(format!("{:x}", hasher.finalize()))
}

fn refresh_verify_error_code(err: &JwtError) -> &'static str {
    match err.to_auth_verify_error() {
        AuthVerifyError::AccessExpired => "auth_refresh_expired",
        _ => "auth_refresh_invalid",
    }
}

fn refresh_auth_error(state: &AppState, code: &str) -> AppError {
    state
        .auth_consistency_metrics
        .observe_refresh_failure_code(code);
    AppError::AuthError(code.to_string())
}

fn map_refresh_error_with_metrics(state: &AppState, err: AppError) -> AppError {
    if let AppError::AuthError(code) = &err {
        state
            .auth_consistency_metrics
            .observe_refresh_failure_code(code);
    }
    err
}

fn refresh_conflict_grace_window_secs() -> i64 {
    std::env::var("AUTH_REFRESH_CONFLICT_GRACE_SECS")
        .ok()
        .and_then(|raw| raw.trim().parse::<i64>().ok())
        .filter(|secs| *secs > 0)
        .unwrap_or(AUTH_REFRESH_CONFLICT_GRACE_SECS)
}

fn is_refresh_conflict_retry_candidate(
    session: &AuthRefreshSessionRow,
    decoded_jti: &str,
    now: DateTime<Utc>,
) -> bool {
    let rotated_from = match session.rotated_from_jti.as_deref() {
        Some(v) if !v.trim().is_empty() => v.trim(),
        _ => return false,
    };
    if rotated_from != decoded_jti {
        return false;
    }
    let grace_secs = refresh_conflict_grace_window_secs();
    let elapsed_secs = now
        .signed_duration_since(session.updated_at)
        .num_seconds()
        .max(0);
    elapsed_secs <= grace_secs
}

fn is_allowed_local_referer(raw: &str) -> bool {
    let referer = raw.trim().to_ascii_lowercase();
    referer.starts_with("http://localhost:")
        || referer.starts_with("http://127.0.0.1:")
        || referer.starts_with("https://localhost:")
        || referer.starts_with("https://127.0.0.1:")
        || referer.starts_with("http://tauri.localhost")
        || referer.starts_with("https://tauri.localhost")
}

fn validate_refresh_csrf_headers(headers: &HeaderMap) -> Result<(), AppError> {
    let requested_with = headers
        .get("x-requested-with")
        .and_then(|v| v.to_str().ok())
        .map(|v| v.trim().to_ascii_lowercase())
        .filter(|v| !v.is_empty())
        .ok_or_else(|| AppError::AuthError("auth_refresh_invalid".to_string()))?;
    if requested_with != "xmlhttprequest" && requested_with != "fetch" {
        return Err(AppError::AuthError("auth_refresh_invalid".to_string()));
    }

    if let Some(origin) = headers.get(header::ORIGIN) {
        if !crate::is_allowed_local_origin(origin) {
            return Err(AppError::AuthError("auth_refresh_invalid".to_string()));
        }
    }

    if let Some(referer) = headers.get(header::REFERER).and_then(|v| v.to_str().ok()) {
        if !is_allowed_local_referer(referer) {
            return Err(AppError::AuthError("auth_refresh_invalid".to_string()));
        }
    }
    Ok(())
}

fn set_refresh_cookie_header(
    headers: &mut HeaderMap,
    refresh_token: &str,
    max_age_secs: u64,
) -> Result<(), AppError> {
    let cookie = build_refresh_cookie(refresh_token, max_age_secs, false);
    headers.append(header::SET_COOKIE, HeaderValue::from_str(&cookie)?);
    Ok(())
}

fn clear_refresh_cookie_header(headers: &mut HeaderMap) -> Result<(), AppError> {
    let cookie = build_refresh_cookie("", 0, true);
    headers.append(header::SET_COOKIE, HeaderValue::from_str(&cookie)?);
    Ok(())
}

fn build_refresh_cookie(value: &str, max_age_secs: u64, clear: bool) -> String {
    let secure = refresh_cookie_secure_enabled();
    let cookie_value = if clear { "" } else { value };
    let mut cookie = format!(
        "{}={}; Path=/api/auth; HttpOnly; SameSite=Lax; Max-Age={}",
        REFRESH_COOKIE_NAME,
        cookie_value,
        if clear { 0 } else { max_age_secs }
    );
    if secure {
        cookie.push_str("; Secure");
    }
    cookie
}

fn extract_refresh_token(headers: &HeaderMap) -> Option<String> {
    let cookie_header = headers.get(header::COOKIE)?.to_str().ok()?;
    for item in cookie_header.split(';') {
        let trimmed = item.trim();
        let mut parts = trimmed.splitn(2, '=');
        let key = parts.next()?.trim();
        let value = parts.next().unwrap_or_default().trim();
        if key == REFRESH_COOKIE_NAME && !value.is_empty() {
            return Some(value.to_string());
        }
    }
    None
}

fn ttl_from_exp(exp: usize) -> u64 {
    let now = Utc::now().timestamp().max(0) as usize;
    exp.saturating_sub(now) as u64
}

fn refresh_cookie_secure_enabled() -> bool {
    for key in ["ECHOISLE_ENV", "APP_ENV", "RUST_ENV", "ENV"] {
        if let Ok(value) = std::env::var(key) {
            let normalized = value.trim().to_ascii_lowercase();
            if normalized == "prod" || normalized == "production" {
                return true;
            }
        }
    }
    false
}

fn auth_fail_closed_enabled(state: &AppState) -> bool {
    if state.config.redis.startup_fail_closed() {
        return true;
    }
    refresh_cookie_secure_enabled()
}

fn handle_auth_redis_unit_result(
    state: &AppState,
    result: anyhow::Result<()>,
    fallback_code: &str,
) -> Result<(), AppError> {
    match result {
        Ok(_) => Ok(()),
        Err(err) => {
            if auth_fail_closed_enabled(state) {
                Err(AppError::AuthError(fallback_code.to_string()))
            } else {
                tracing::warn!("auth redis degraded as fail-open: {}", err);
                Ok(())
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{AuthVerifyError, TokenVerify};
    use anyhow::Result;
    use axum::http::header::SET_COOKIE;
    use http_body_util::BodyExt;

    #[tokio::test]
    async fn signup_handler_should_return_gone_after_v1_disabled() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let response = signup_handler(
            State(state),
            HeaderMap::new(),
            Json(CreateUser::new("Legacy", "legacy@acme.org", "123456")),
        )
        .await?
        .into_response();
        assert_eq!(response.status(), StatusCode::GONE);
        assert_eq!(
            response
                .headers()
                .get("Deprecation")
                .and_then(|v| v.to_str().ok()),
            Some("true")
        );
        let body = response.into_body().collect().await?.to_bytes();
        let err: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(err.error, "auth_v1_signup_disabled_use_v2");
        Ok(())
    }

    #[tokio::test]
    async fn signin_should_return_access_token_and_refresh_cookie() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let input = SigninUser::new("tchen@acme.org", "123456");
        let response = signin_handler(State(state.clone()), HeaderMap::new(), Json(input))
            .await?
            .into_response();
        assert_eq!(response.status(), StatusCode::OK);
        assert!(response.headers().get(SET_COOKIE).is_some());
        let body = response.into_body().collect().await?.to_bytes();
        let ret: AuthOutput = serde_json::from_slice(&body)?;
        assert!(!ret.access_token.is_empty());
        assert_eq!(ret.token_type, "Bearer");
        Ok(())
    }

    #[tokio::test]
    async fn refresh_should_rotate_token() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let signin = signin_handler(
            State(state.clone()),
            HeaderMap::new(),
            Json(SigninUser::new("tchen@acme.org", "123456")),
        )
        .await?
        .into_response();
        let set_cookie = signin
            .headers()
            .get(SET_COOKIE)
            .and_then(|v| v.to_str().ok())
            .unwrap_or_default()
            .to_string();
        let cookie = set_cookie.split(';').next().unwrap_or_default().to_string();

        let mut headers = HeaderMap::new();
        headers.insert(header::COOKIE, HeaderValue::from_str(&cookie)?);
        headers.insert(
            header::HeaderName::from_static("x-requested-with"),
            HeaderValue::from_static("XMLHttpRequest"),
        );
        let refreshed = refresh_handler(State(state), headers)
            .await?
            .into_response();
        assert_eq!(refreshed.status(), StatusCode::OK);
        assert!(refreshed.headers().get(SET_COOKIE).is_some());
        let body = refreshed.into_body().collect().await?.to_bytes();
        let ret: RefreshOutput = serde_json::from_slice(&body)?;
        assert!(!ret.access_token.is_empty());
        Ok(())
    }

    #[tokio::test]
    async fn refresh_should_reject_when_csrf_header_missing() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let signin = signin_handler(
            State(state.clone()),
            HeaderMap::new(),
            Json(SigninUser::new("tchen@acme.org", "123456")),
        )
        .await?
        .into_response();
        let set_cookie = signin
            .headers()
            .get(SET_COOKIE)
            .and_then(|v| v.to_str().ok())
            .unwrap_or_default()
            .to_string();
        let cookie = set_cookie.split(';').next().unwrap_or_default().to_string();

        let mut headers = HeaderMap::new();
        headers.insert(header::COOKIE, HeaderValue::from_str(&cookie)?);
        let err = match refresh_handler(State(state), headers).await {
            Ok(_) => panic!("refresh should reject without csrf header"),
            Err(err) => err,
        };
        match err {
            AppError::AuthError(code) => assert_eq!(code, "auth_refresh_invalid"),
            _ => panic!("expected auth error"),
        }
        Ok(())
    }

    #[tokio::test]
    async fn refresh_should_return_conflict_retry_for_previous_jti_within_grace() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let signin = signin_handler(
            State(state.clone()),
            HeaderMap::new(),
            Json(SigninUser::new("tchen@acme.org", "123456")),
        )
        .await?
        .into_response();
        let set_cookie = signin
            .headers()
            .get(SET_COOKIE)
            .and_then(|v| v.to_str().ok())
            .unwrap_or_default()
            .to_string();
        let cookie = set_cookie.split(';').next().unwrap_or_default().to_string();

        let mut headers = HeaderMap::new();
        headers.insert(header::COOKIE, HeaderValue::from_str(&cookie)?);
        headers.insert(
            header::HeaderName::from_static("x-requested-with"),
            HeaderValue::from_static("XMLHttpRequest"),
        );
        let _ = refresh_handler(State(state.clone()), headers.clone())
            .await?
            .into_response();

        let err = match refresh_handler(State(state), headers).await {
            Ok(_) => panic!("duplicate refresh should be treated as conflict retry"),
            Err(err) => err,
        };
        match err {
            AppError::AuthError(code) => assert_eq!(code, "auth_refresh_conflict_retry"),
            _ => panic!("expected auth error"),
        }
        Ok(())
    }

    #[tokio::test]
    async fn refresh_outbox_worker_should_deliver_enqueued_jobs() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let signin = signin_handler(
            State(state.clone()),
            HeaderMap::new(),
            Json(SigninUser::new("tchen@acme.org", "123456")),
        )
        .await?
        .into_response();
        let set_cookie = signin
            .headers()
            .get(SET_COOKIE)
            .and_then(|v| v.to_str().ok())
            .unwrap_or_default()
            .to_string();
        let cookie = set_cookie.split(';').next().unwrap_or_default().to_string();

        let mut headers = HeaderMap::new();
        headers.insert(header::COOKIE, HeaderValue::from_str(&cookie)?);
        headers.insert(
            header::HeaderName::from_static("x-requested-with"),
            HeaderValue::from_static("XMLHttpRequest"),
        );
        let _ = refresh_handler(State(state.clone()), headers)
            .await?
            .into_response();

        let depth_before: i64 = sqlx::query_scalar(
            "SELECT COUNT(*)::bigint FROM auth_refresh_consistency_outbox_jobs WHERE delivered_at IS NULL",
        )
        .fetch_one(&state.pool)
        .await?;
        assert!(depth_before >= 2);

        let report = state.retry_auth_refresh_consistency_outbox_once(32).await?;
        assert!(report.attempted >= 2);
        assert!(report.delivered >= 2);

        let depth_after: i64 = sqlx::query_scalar(
            "SELECT COUNT(*)::bigint FROM auth_refresh_consistency_outbox_jobs WHERE delivered_at IS NULL",
        )
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(depth_after, 0);
        Ok(())
    }

    #[tokio::test]
    async fn logout_all_should_invalidate_existing_access_token() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let signin = signin_handler(
            State(state.clone()),
            HeaderMap::new(),
            Json(SigninUser::new("tchen@acme.org", "123456")),
        )
        .await?
        .into_response();
        let signin_body = signin.into_body().collect().await?.to_bytes();
        let auth: AuthOutput = serde_json::from_slice(&signin_body)?;
        let decoded = state.dk.verify_access(&auth.access_token)?;
        let old_ver = decoded.ver;
        let user = decoded.user.clone();

        let _ = logout_all_handler(Extension(user), State(state.clone()))
            .await?
            .into_response();

        let current_ver = load_user_token_version(&state, decoded.user.id).await?;
        assert!(current_ver > old_ver);
        let verify_ret = TokenVerify::verify(&state, &auth.access_token).await;
        assert!(matches!(
            verify_ret,
            Err(AuthVerifyError::TokenVersionMismatch) | Err(AuthVerifyError::SessionRevoked)
        ));
        Ok(())
    }

    #[tokio::test]
    async fn ensure_access_session_active_should_check_db_revocation_even_without_redis_hit(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let signin = signin_handler(
            State(state.clone()),
            HeaderMap::new(),
            Json(SigninUser::new("tchen@acme.org", "123456")),
        )
        .await?
        .into_response();
        let signin_body = signin.into_body().collect().await?.to_bytes();
        let auth: AuthOutput = serde_json::from_slice(&signin_body)?;
        let decoded = state.dk.verify_access(&auth.access_token)?;
        sqlx::query(
            r#"
            UPDATE auth_refresh_sessions
            SET revoked_at = NOW(), revoke_reason = 'manual_test', updated_at = NOW()
            WHERE sid = $1
            "#,
        )
        .bind(&decoded.sid)
        .execute(&state.pool)
        .await?;

        let err = ensure_access_session_active(&state, decoded.user.id, &decoded.sid)
            .await
            .expect_err("revoked session should be rejected");
        match err {
            AppError::AuthError(code) => assert_eq!(code, "auth_session_revoked"),
            _ => panic!("expect auth error"),
        }
        Ok(())
    }

    #[tokio::test]
    async fn auth_token_version_invalidation_retry_queue_should_dedupe() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state
            .enqueue_auth_token_version_invalidation_retry(1)
            .await?;
        state
            .enqueue_auth_token_version_invalidation_retry(1)
            .await?;
        let metrics = state.get_auth_consistency_metrics();
        assert_eq!(metrics.token_version_retry_queue_depth, 1);
        assert_eq!(metrics.retry_enqueue_total, 1);
        assert_eq!(metrics.retry_dedup_total, 1);
        Ok(())
    }

    #[tokio::test]
    async fn auth_token_version_invalidation_retry_once_should_flush_queue_on_success() -> Result<()>
    {
        let (_tdb, state) = AppState::new_for_test().await?;
        state
            .enqueue_auth_token_version_invalidation_retry(2)
            .await?;
        let report = state
            .retry_auth_token_version_invalidation_queue_once(32)
            .await?;
        assert_eq!(report.attempted, 1);
        assert_eq!(report.succeeded, 1);
        assert_eq!(report.requeued, 0);
        assert_eq!(report.dropped, 0);
        let metrics = state.get_auth_consistency_metrics();
        assert_eq!(metrics.token_version_retry_queue_depth, 0);
        assert_eq!(metrics.retry_success_total, 1);
        Ok(())
    }

    #[tokio::test]
    async fn send_sms_code_v2_should_return_debug_code_in_mock_mode() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let response = send_sms_code_v2_handler(
            State(state),
            HeaderMap::new(),
            Json(SendSmsCodeV2Input {
                phone: "13800138000".to_string(),
                scene: "signup_phone".to_string(),
            }),
        )
        .await?
        .into_response();
        assert_eq!(response.status(), StatusCode::OK);
        let body = response.into_body().collect().await?.to_bytes();
        let ret: SendSmsCodeV2Output = serde_json::from_slice(&body)?;
        assert!(ret.sent);
        assert!(ret.debug_code.is_some());
        Ok(())
    }

    #[tokio::test]
    async fn signup_phone_v2_and_signin_password_v2_should_work() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;

        let sms_response = send_sms_code_v2_handler(
            State(state.clone()),
            HeaderMap::new(),
            Json(SendSmsCodeV2Input {
                phone: "13800138011".to_string(),
                scene: "signup_phone".to_string(),
            }),
        )
        .await?
        .into_response();
        let sms_body = sms_response.into_body().collect().await?.to_bytes();
        let sms_ret: SendSmsCodeV2Output = serde_json::from_slice(&sms_body)?;
        let sms_code = sms_ret.debug_code.clone().expect("debug code");

        let signup_response = signup_phone_v2_handler(
            State(state.clone()),
            HeaderMap::new(),
            Json(SignupPhoneV2Input {
                phone: "13800138011".to_string(),
                sms_code,
                password: "123456".to_string(),
                fullname: "Phone User".to_string(),
            }),
        )
        .await?
        .into_response();
        assert_eq!(signup_response.status(), StatusCode::CREATED);

        let signin_response = signin_password_v2_handler(
            State(state),
            HeaderMap::new(),
            Json(SigninPasswordV2Input {
                account: "13800138011".to_string(),
                account_type: "phone".to_string(),
                password: "123456".to_string(),
            }),
        )
        .await?
        .into_response();
        assert_eq!(signin_response.status(), StatusCode::OK);
        let body = signin_response.into_body().collect().await?.to_bytes();
        let ret: AuthOutput = serde_json::from_slice(&body)?;
        assert!(ret.user.phone_e164.is_some());
        Ok(())
    }

    #[tokio::test]
    async fn signup_phone_v2_should_not_fail_when_sms_audit_table_is_missing() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        sqlx::query("DROP TABLE auth_sms_audit_logs")
            .execute(&state.pool)
            .await?;

        let sms_response = send_sms_code_v2_handler(
            State(state.clone()),
            HeaderMap::new(),
            Json(SendSmsCodeV2Input {
                phone: "13800138021".to_string(),
                scene: "signup_phone".to_string(),
            }),
        )
        .await?
        .into_response();
        assert_eq!(sms_response.status(), StatusCode::OK);
        let sms_body = sms_response.into_body().collect().await?.to_bytes();
        let sms_ret: SendSmsCodeV2Output = serde_json::from_slice(&sms_body)?;
        let sms_code = sms_ret.debug_code.expect("debug code");

        let signup_response = signup_phone_v2_handler(
            State(state),
            HeaderMap::new(),
            Json(SignupPhoneV2Input {
                phone: "13800138021".to_string(),
                sms_code,
                password: "123456".to_string(),
                fullname: "Audit Degrade".to_string(),
            }),
        )
        .await?
        .into_response();
        assert_eq!(signup_response.status(), StatusCode::CREATED);
        Ok(())
    }

    #[tokio::test]
    async fn create_user_with_phone_and_session_should_rollback_when_session_insert_fails(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let phone = format!(
            "+86139{:08}",
            (Uuid::now_v7().as_u128() % 100_000_000) as u64
        );
        let ret = state
            .create_user_with_phone_and_session(&CreateUserWithPhoneAndSessionInput {
                fullname: "Txn Rollback".to_string(),
                email: None,
                phone_e164: phone.clone(),
                password: "123456".to_string(),
                phone_bind_required: false,
                sid: "x".repeat(200),
                family_id: Uuid::now_v7().to_string(),
                refresh_jti: Uuid::now_v7().to_string(),
                refresh_ttl_secs: REFRESH_TOKEN_TTL_SECS as i64,
                user_agent: None,
                ip_hash: None,
            })
            .await;
        assert!(
            matches!(ret, Err(AppError::SqlxError(_))),
            "session insert should fail by sid length and rollback user insert"
        );

        let user = state.find_user_by_phone(&phone).await?;
        assert!(user.is_none(), "user insert should be rolled back together");
        Ok(())
    }

    #[tokio::test]
    async fn signin_otp_v2_should_reject_not_registered_phone() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let sms_response = send_sms_code_v2_handler(
            State(state.clone()),
            HeaderMap::new(),
            Json(SendSmsCodeV2Input {
                phone: "13800138022".to_string(),
                scene: "signin_phone_otp".to_string(),
            }),
        )
        .await?
        .into_response();
        let sms_body = sms_response.into_body().collect().await?.to_bytes();
        let sms_ret: SendSmsCodeV2Output = serde_json::from_slice(&sms_body)?;
        let sms_code = sms_ret.debug_code.expect("debug code");

        let err = signin_otp_v2_handler(
            State(state),
            HeaderMap::new(),
            Json(SigninOtpV2Input {
                phone: "13800138022".to_string(),
                sms_code,
            }),
        )
        .await
        .expect_err("unregistered phone should be rejected");
        match err {
            AppError::AuthError(code) => assert_eq!(code, "auth_account_not_registered"),
            _ => panic!("expect auth error"),
        }
        Ok(())
    }

    #[tokio::test]
    async fn wechat_bind_phone_v2_should_bind_or_create_and_signin() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;

        let challenge_response = wechat_challenge_v2_handler(State(state.clone()))
            .await?
            .into_response();
        assert_eq!(challenge_response.status(), StatusCode::OK);
        let challenge_body = challenge_response.into_body().collect().await?.to_bytes();
        let challenge: WechatChallengeV2Output = serde_json::from_slice(&challenge_body)?;

        let signin_response = wechat_signin_v2_handler(
            State(state.clone()),
            HeaderMap::new(),
            Json(WechatSigninV2Input {
                state: challenge.state,
                code: "mock_wechat_user_01:union01:Tester".to_string(),
            }),
        )
        .await?
        .into_response();
        assert_eq!(signin_response.status(), StatusCode::OK);
        let signin_body = signin_response.into_body().collect().await?.to_bytes();
        let signin_ret: WechatSigninV2Output = serde_json::from_slice(&signin_body)?;
        assert!(signin_ret.bind_required);
        let ticket = signin_ret.wechat_ticket.expect("wechat ticket");

        let sms_response = send_sms_code_v2_handler(
            State(state.clone()),
            HeaderMap::new(),
            Json(SendSmsCodeV2Input {
                phone: "13800138033".to_string(),
                scene: "bind_phone".to_string(),
            }),
        )
        .await?
        .into_response();
        let sms_body = sms_response.into_body().collect().await?.to_bytes();
        let sms_ret: SendSmsCodeV2Output = serde_json::from_slice(&sms_body)?;
        let sms_code = sms_ret.debug_code.expect("debug code");

        let bind_response = wechat_bind_phone_v2_handler(
            State(state),
            HeaderMap::new(),
            Json(WechatBindPhoneV2Input {
                wechat_ticket: ticket,
                phone: "13800138033".to_string(),
                sms_code,
                password: Some("123456".to_string()),
                fullname: "Wechat User".to_string(),
            }),
        )
        .await?
        .into_response();
        assert_eq!(bind_response.status(), StatusCode::OK);
        let bind_body = bind_response.into_body().collect().await?.to_bytes();
        let bind_ret: WechatSigninV2Output = serde_json::from_slice(&bind_body)?;
        assert!(!bind_ret.bind_required);
        assert!(bind_ret.access_token.is_some());
        Ok(())
    }

    #[tokio::test]
    async fn wechat_bind_phone_v2_should_allow_empty_password_for_new_user() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;

        let challenge_response = wechat_challenge_v2_handler(State(state.clone()))
            .await?
            .into_response();
        let challenge_body = challenge_response.into_body().collect().await?.to_bytes();
        let challenge: WechatChallengeV2Output = serde_json::from_slice(&challenge_body)?;

        let signin_response = wechat_signin_v2_handler(
            State(state.clone()),
            HeaderMap::new(),
            Json(WechatSigninV2Input {
                state: challenge.state,
                code: "mock_wechat_user_02:union02:Tester2".to_string(),
            }),
        )
        .await?
        .into_response();
        let signin_body = signin_response.into_body().collect().await?.to_bytes();
        let signin_ret: WechatSigninV2Output = serde_json::from_slice(&signin_body)?;
        let ticket = signin_ret.wechat_ticket.expect("wechat ticket");

        let sms_response = send_sms_code_v2_handler(
            State(state.clone()),
            HeaderMap::new(),
            Json(SendSmsCodeV2Input {
                phone: "13800138044".to_string(),
                scene: "bind_phone".to_string(),
            }),
        )
        .await?
        .into_response();
        let sms_body = sms_response.into_body().collect().await?.to_bytes();
        let sms_ret: SendSmsCodeV2Output = serde_json::from_slice(&sms_body)?;
        let sms_code = sms_ret.debug_code.expect("debug code");

        let bind_response = wechat_bind_phone_v2_handler(
            State(state.clone()),
            HeaderMap::new(),
            Json(WechatBindPhoneV2Input {
                wechat_ticket: ticket,
                phone: "13800138044".to_string(),
                sms_code,
                password: None,
                fullname: "Wechat NoPassword".to_string(),
            }),
        )
        .await?
        .into_response();
        assert_eq!(bind_response.status(), StatusCode::OK);
        let bind_body = bind_response.into_body().collect().await?.to_bytes();
        let bind_ret: WechatSigninV2Output = serde_json::from_slice(&bind_body)?;
        assert!(!bind_ret.bind_required);
        assert!(bind_ret.access_token.is_some());
        let user = bind_ret.user.expect("user");
        assert_eq!(user.phone_e164.as_deref(), Some("+8613800138044"));
        Ok(())
    }

    #[tokio::test]
    async fn set_password_v2_should_enable_phone_password_signin_for_wechat_user() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;

        let challenge_response = wechat_challenge_v2_handler(State(state.clone()))
            .await?
            .into_response();
        let challenge_body = challenge_response.into_body().collect().await?.to_bytes();
        let challenge: WechatChallengeV2Output = serde_json::from_slice(&challenge_body)?;

        let signin_response = wechat_signin_v2_handler(
            State(state.clone()),
            HeaderMap::new(),
            Json(WechatSigninV2Input {
                state: challenge.state,
                code: "mock_wechat_user_03:union03:Tester3".to_string(),
            }),
        )
        .await?
        .into_response();
        let signin_body = signin_response.into_body().collect().await?.to_bytes();
        let signin_ret: WechatSigninV2Output = serde_json::from_slice(&signin_body)?;
        let ticket = signin_ret.wechat_ticket.expect("wechat ticket");

        let sms_response = send_sms_code_v2_handler(
            State(state.clone()),
            HeaderMap::new(),
            Json(SendSmsCodeV2Input {
                phone: "13800138055".to_string(),
                scene: "bind_phone".to_string(),
            }),
        )
        .await?
        .into_response();
        let sms_body = sms_response.into_body().collect().await?.to_bytes();
        let sms_ret: SendSmsCodeV2Output = serde_json::from_slice(&sms_body)?;
        let sms_code = sms_ret.debug_code.expect("debug code");

        let bind_response = wechat_bind_phone_v2_handler(
            State(state.clone()),
            HeaderMap::new(),
            Json(WechatBindPhoneV2Input {
                wechat_ticket: ticket,
                phone: "13800138055".to_string(),
                sms_code,
                password: None,
                fullname: "Wechat Later Password".to_string(),
            }),
        )
        .await?
        .into_response();
        let bind_body = bind_response.into_body().collect().await?.to_bytes();
        let bind_ret: WechatSigninV2Output = serde_json::from_slice(&bind_body)?;
        let user = bind_ret.user.expect("user");

        let set_password_sms_response = send_sms_code_v2_handler(
            State(state.clone()),
            HeaderMap::new(),
            Json(SendSmsCodeV2Input {
                phone: "13800138055".to_string(),
                scene: "bind_phone".to_string(),
            }),
        )
        .await?
        .into_response();
        let set_password_sms_body = set_password_sms_response
            .into_body()
            .collect()
            .await?
            .to_bytes();
        let set_password_sms_ret: SendSmsCodeV2Output =
            serde_json::from_slice(&set_password_sms_body)?;
        let set_password_sms_code = set_password_sms_ret.debug_code.expect("debug code");

        let set_password_response = set_password_v2_handler(
            Extension(user),
            State(state.clone()),
            Json(SetPasswordV2Input {
                password: "654321".to_string(),
                sms_code: Some(set_password_sms_code),
            }),
        )
        .await?
        .into_response();
        assert_eq!(set_password_response.status(), StatusCode::OK);
        let set_password_body = set_password_response
            .into_body()
            .collect()
            .await?
            .to_bytes();
        let set_password_ret: SetPasswordV2Output = serde_json::from_slice(&set_password_body)?;
        assert!(set_password_ret.updated);

        let signin_with_password_response = signin_password_v2_handler(
            State(state),
            HeaderMap::new(),
            Json(SigninPasswordV2Input {
                account: "13800138055".to_string(),
                account_type: "phone".to_string(),
                password: "654321".to_string(),
            }),
        )
        .await?
        .into_response();
        assert_eq!(signin_with_password_response.status(), StatusCode::OK);
        Ok(())
    }

    #[tokio::test]
    async fn set_password_v2_should_use_db_phone_even_when_extension_snapshot_is_stale(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let signup_sms_response = send_sms_code_v2_handler(
            State(state.clone()),
            HeaderMap::new(),
            Json(SendSmsCodeV2Input {
                phone: "13800138077".to_string(),
                scene: "signup_phone".to_string(),
            }),
        )
        .await?
        .into_response();
        let signup_sms_body = signup_sms_response.into_body().collect().await?.to_bytes();
        let signup_sms_ret: SendSmsCodeV2Output = serde_json::from_slice(&signup_sms_body)?;
        let signup_sms_code = signup_sms_ret.debug_code.expect("debug code");

        let signup_response = signup_phone_v2_handler(
            State(state.clone()),
            HeaderMap::new(),
            Json(SignupPhoneV2Input {
                phone: "13800138077".to_string(),
                sms_code: signup_sms_code,
                password: "123456".to_string(),
                fullname: "Snapshot Stale".to_string(),
            }),
        )
        .await?
        .into_response();
        let signup_body = signup_response.into_body().collect().await?.to_bytes();
        let signup_ret: AuthOutput = serde_json::from_slice(&signup_body)?;

        let set_password_sms_response = send_sms_code_v2_handler(
            State(state.clone()),
            HeaderMap::new(),
            Json(SendSmsCodeV2Input {
                phone: "13800138077".to_string(),
                scene: "bind_phone".to_string(),
            }),
        )
        .await?
        .into_response();
        let set_password_sms_body = set_password_sms_response
            .into_body()
            .collect()
            .await?
            .to_bytes();
        let set_password_sms_ret: SendSmsCodeV2Output =
            serde_json::from_slice(&set_password_sms_body)?;
        let set_password_sms_code = set_password_sms_ret.debug_code.expect("debug code");

        let mut stale_snapshot = signup_ret.user.clone();
        stale_snapshot.phone_e164 = None;
        stale_snapshot.phone_bind_required = true;
        let set_password_response = set_password_v2_handler(
            Extension(stale_snapshot),
            State(state.clone()),
            Json(SetPasswordV2Input {
                password: "654321".to_string(),
                sms_code: Some(set_password_sms_code),
            }),
        )
        .await?
        .into_response();
        assert_eq!(set_password_response.status(), StatusCode::OK);

        let signin_with_password_response = signin_password_v2_handler(
            State(state),
            HeaderMap::new(),
            Json(SigninPasswordV2Input {
                account: "13800138077".to_string(),
                account_type: "phone".to_string(),
                password: "654321".to_string(),
            }),
        )
        .await?
        .into_response();
        assert_eq!(signin_with_password_response.status(), StatusCode::OK);
        Ok(())
    }

    #[tokio::test]
    async fn set_password_v2_should_reject_too_short_password() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let user = state
            .find_user_by_email("tchen@acme.org")
            .await?
            .expect("seed user");

        let ret = set_password_v2_handler(
            Extension(user),
            State(state),
            Json(SetPasswordV2Input {
                password: "1".to_string(),
                sms_code: None,
            }),
        )
        .await;
        match ret {
            Ok(_) => panic!("short password should be rejected"),
            Err(AppError::AuthError(code)) => assert_eq!(code, "auth_password_invalid"),
            Err(_) => panic!("expect auth error"),
        }
        Ok(())
    }

    #[tokio::test]
    async fn set_password_v2_should_require_sms_code() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let sms_response = send_sms_code_v2_handler(
            State(state.clone()),
            HeaderMap::new(),
            Json(SendSmsCodeV2Input {
                phone: "13800138188".to_string(),
                scene: "signup_phone".to_string(),
            }),
        )
        .await?
        .into_response();
        let sms_body = sms_response.into_body().collect().await?.to_bytes();
        let sms_ret: SendSmsCodeV2Output = serde_json::from_slice(&sms_body)?;
        let sms_code = sms_ret.debug_code.expect("debug code");

        let signup_response = signup_phone_v2_handler(
            State(state.clone()),
            HeaderMap::new(),
            Json(SignupPhoneV2Input {
                phone: "13800138188".to_string(),
                sms_code,
                password: "123456".to_string(),
                fullname: "No Sms Code".to_string(),
            }),
        )
        .await?
        .into_response();
        let signup_body = signup_response.into_body().collect().await?.to_bytes();
        let signup_ret: AuthOutput = serde_json::from_slice(&signup_body)?;

        let ret = set_password_v2_handler(
            Extension(signup_ret.user),
            State(state),
            Json(SetPasswordV2Input {
                password: "654321".to_string(),
                sms_code: None,
            }),
        )
        .await;
        match ret {
            Ok(_) => panic!("missing sms code should be rejected"),
            Err(AppError::AuthError(code)) => assert_eq!(code, "auth_sms_code_invalid"),
            Err(_) => panic!("expect auth error"),
        }
        Ok(())
    }

    #[tokio::test]
    async fn set_password_v2_should_require_bound_phone() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let user = state
            .create_user(&CreateUser {
                fullname: "NoPhone".to_string(),
                email: format!("nop{}@acme.org", Uuid::new_v4()),
                password: "123456".to_string(),
            })
            .await?;

        let ret = set_password_v2_handler(
            Extension(user),
            State(state),
            Json(SetPasswordV2Input {
                password: "654321".to_string(),
                sms_code: Some("112233".to_string()),
            }),
        )
        .await;
        match ret {
            Ok(_) => panic!("missing bound phone should be rejected"),
            Err(AppError::AuthError(code)) => assert_eq!(code, "auth_phone_bind_required"),
            Err(_) => panic!("expect auth error"),
        }
        Ok(())
    }

    #[test]
    fn signin_password_rate_limit_key_should_hash_normalized_account() {
        let email_key = build_signin_password_rate_limit_key(AccountType::Email, "user@acme.org");
        assert_eq!(
            email_key,
            format!("email:{}", hash_with_sha1("user@acme.org"))
        );
        let phone_normalized_a = normalize_cn_phone_e164("13800138000").expect("normalize phone");
        let phone_normalized_b =
            normalize_cn_phone_e164("+86 13800138000").expect("normalize phone");
        assert_eq!(phone_normalized_a, phone_normalized_b);
        let phone_key =
            build_signin_password_rate_limit_key(AccountType::Phone, &phone_normalized_a);
        assert_eq!(
            phone_key,
            format!("phone:{}", hash_with_sha1("+8613800138000"))
        );
        let phone_key_b =
            build_signin_password_rate_limit_key(AccountType::Phone, &phone_normalized_b);
        assert_eq!(phone_key, phone_key_b);
    }
}
