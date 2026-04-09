use crate::models::OPS_RBAC_PERMISSION_DENIED_ROLE_MANAGE_CODE;
use crate::{
    application::request_guard::{
        build_rate_limit_headers, enforce_rate_limit, enforce_rate_limit_with_disabled_fallback,
        rate_limit_exceeded_response, release_idempotency_best_effort,
        request_idempotency_key_from_headers, request_rate_limit_ip_key_with_user_fallback,
        try_acquire_idempotency_or_fail_open,
    },
    AppError, AppState, ApplyOpsObservabilityAnomalyActionInput, ExecuteJudgeReplayOpsInput,
    GetJudgeFinalDispatchFailureStatsQuery, GetJudgeReplayPreviewOpsQuery,
    ListJudgeReplayActionsOpsQuery, ListJudgeReviewOpsQuery, ListJudgeTraceReplayOpsQuery,
    ListKafkaDlqEventsQuery, ListOpsAlertNotificationsQuery, ListOpsRoleAssignmentsQuery,
    ListOpsServiceSplitReviewAuditsQuery, OpsCreateDebateSessionInput, OpsCreateDebateTopicInput,
    OpsObservabilityThresholds, OpsRbacRevokeMeta, OpsRbacUpsertMeta, OpsUpdateDebateSessionInput,
    OpsUpdateDebateTopicInput, RunOpsObservabilityEvaluationQuery,
    UpdateOpsObservabilityAnomalyStateInput, UpsertOpsRoleInput, UpsertOpsServiceSplitReviewInput,
};
use axum::{
    extract::{rejection::JsonRejection, Path, Query, State},
    http::{header::IF_MATCH, HeaderMap, HeaderName, HeaderValue, StatusCode},
    response::{IntoResponse, Response},
    Extension, Json,
};
use chat_core::User;
use sqlx::FromRow;
use std::{
    sync::{
        atomic::{AtomicU64, Ordering},
        LazyLock,
    },
    time::Instant,
};

#[cfg(test)]
use crate::RateLimitDecision;

const OPS_DEBATE_TOPIC_CREATE_USER_RATE_LIMIT_PER_WINDOW: u64 = 30;
const OPS_DEBATE_TOPIC_CREATE_IP_RATE_LIMIT_PER_WINDOW: u64 = 90;
const OPS_DEBATE_TOPIC_CREATE_RATE_LIMIT_WINDOW_SECS: u64 = 60;
const OPS_DEBATE_TOPIC_CREATE_IDEMPOTENCY_TTL_SECS: u64 = 30;
const OPS_DEBATE_TOPIC_CREATE_IDEMPOTENCY_MAX_LEN: usize = 160;
const OPS_DEBATE_SESSION_CREATE_USER_RATE_LIMIT_PER_WINDOW: u64 = 30;
const OPS_DEBATE_SESSION_CREATE_IP_RATE_LIMIT_PER_WINDOW: u64 = 90;
const OPS_DEBATE_SESSION_CREATE_RATE_LIMIT_WINDOW_SECS: u64 = 60;
const OPS_DEBATE_SESSION_CREATE_IDEMPOTENCY_TTL_SECS: u64 = 30;
const OPS_DEBATE_SESSION_CREATE_IDEMPOTENCY_MAX_LEN: usize = 160;
const OPS_DEBATE_SESSION_UPDATE_USER_RATE_LIMIT_PER_WINDOW: u64 = 30;
const OPS_DEBATE_SESSION_UPDATE_IP_RATE_LIMIT_PER_WINDOW: u64 = 90;
const OPS_DEBATE_SESSION_UPDATE_RATE_LIMIT_WINDOW_SECS: u64 = 60;
const OPS_RBAC_ME_USER_RATE_LIMIT_PER_WINDOW: u64 = 120;
const OPS_RBAC_ME_IP_RATE_LIMIT_PER_WINDOW: u64 = 240;
const OPS_RBAC_ME_RATE_LIMIT_WINDOW_SECS: u64 = 60;
const OPS_RBAC_ROLES_LIST_USER_RATE_LIMIT_PER_WINDOW: u64 = 60;
const OPS_RBAC_ROLES_LIST_IP_RATE_LIMIT_PER_WINDOW: u64 = 120;
const OPS_RBAC_ROLES_LIST_RATE_LIMIT_WINDOW_SECS: u64 = 60;
const OPS_RBAC_ROLES_WRITE_USER_RATE_LIMIT_PER_WINDOW: u64 = 30;
const OPS_RBAC_ROLES_WRITE_IP_RATE_LIMIT_PER_WINDOW: u64 = 90;
const OPS_RBAC_ROLES_WRITE_RATE_LIMIT_WINDOW_SECS: u64 = 60;
const OPS_RBAC_ROLES_WRITE_IDEMPOTENCY_TTL_SECS: u64 = 30;
const OPS_RBAC_ROLES_WRITE_IDEMPOTENCY_MAX_LEN: usize = 160;
const OPS_RBAC_ROLES_WRITE_IDEMPOTENCY_SCOPE: &str = "ops_rbac_roles_write_upsert";
const OPS_RBAC_ROLES_WRITE_CONTENT_TYPE_INVALID_CODE: &str =
    "ops_rbac_roles_write_content_type_invalid";
const OPS_RBAC_ROLES_WRITE_BODY_INVALID_JSON_CODE: &str = "ops_rbac_roles_write_body_invalid_json";
const OPS_RBAC_ROLES_WRITE_BODY_DATA_INVALID_CODE: &str = "ops_rbac_roles_write_body_data_invalid";
const OPS_RBAC_ROLES_WRITE_BODY_READ_FAILED_CODE: &str = "ops_rbac_roles_write_body_read_failed";
const OPS_RBAC_ROLES_WRITE_BODY_REJECTED_CODE: &str = "ops_rbac_roles_write_body_rejected";
const OPS_RBAC_IF_MATCH_INVALID_CODE: &str = "ops_rbac_if_match_invalid";
const OPS_RBAC_IF_MATCH_REQUIRED_CODE: &str = "ops_rbac_if_match_required";
const OPS_RBAC_REVISION_HEADER: &str = "x-rbac-revision";
const OPS_RBAC_WARNING_HEADER: &str = "x-rbac-warning";
const OPS_RBAC_WARNING_OWNER_SELF_ROLE_ASSIGNMENT_NO_EFFECT: &str =
    "owner_self_role_assignment_no_effect";
const OPS_RBAC_AUDIT_EVENT_ROLES_LIST_READ: &str = "roles_list_read";
const OPS_RBAC_AUDIT_EVENT_RBAC_ME_READ: &str = "rbac_me_read";
const OPS_RBAC_AUDIT_EVENT_ROLE_UPSERT: &str = "role_upsert";
const OPS_RBAC_AUDIT_EVENT_ROLE_REVOKE: &str = "role_revoke";
const OPS_RBAC_AUDIT_FAILURE_PERMISSION_DENIED: &str = "permission_denied";
const OPS_RBAC_AUDIT_FAILURE_VALIDATION_ERROR: &str = "validation_error";
const OPS_RBAC_AUDIT_FAILURE_NOT_FOUND: &str = "not_found";
const OPS_RBAC_AUDIT_FAILURE_CONFLICT: &str = "conflict";
const OPS_RBAC_AUDIT_FAILURE_AUTH_ERROR: &str = "auth_error";
const OPS_RBAC_AUDIT_FAILURE_RATE_LIMITED: &str = "rate_limited";
const OPS_RBAC_AUDIT_FAILURE_SERVER_ERROR: &str = "server_error";
const OPS_RBAC_AUDIT_FAILURE_SYSTEM_ERROR: &str = "system_error";
pub(crate) const OPS_RBAC_AUDIT_OUTBOX_BATCH_SIZE: i64 = 32;
const OPS_RBAC_AUDIT_OUTBOX_LOCK_SECS: i64 = 15;
const OPS_RBAC_AUDIT_OUTBOX_RETRY_BASE_BACKOFF_MS: u64 = 500;
const OPS_RBAC_AUDIT_OUTBOX_RETRY_MAX_BACKOFF_MS: u64 = 60_000;
const OPS_RBAC_AUDIT_OUTBOX_ERROR_MAX_LEN: usize = 512;
const OPS_OBSERVABILITY_EVAL_RATE_LIMIT_PER_WINDOW: u64 = 6;
const OPS_OBSERVABILITY_EVAL_RATE_LIMIT_WINDOW_SECS: u64 = 60;

#[derive(Debug, Default)]
struct OpsRbacMeMetrics {
    request_total: AtomicU64,
    success_total: AtomicU64,
    failed_total: AtomicU64,
    rate_limited_total: AtomicU64,
    owner_total: AtomicU64,
    non_owner_total: AtomicU64,
    latency_ms_total: AtomicU64,
    latency_ms_samples_total: AtomicU64,
}

impl OpsRbacMeMetrics {
    fn observe_start(&self) {
        self.request_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_success(&self, is_owner: bool, latency_ms: u64) {
        self.success_total.fetch_add(1, Ordering::Relaxed);
        if is_owner {
            self.owner_total.fetch_add(1, Ordering::Relaxed);
        } else {
            self.non_owner_total.fetch_add(1, Ordering::Relaxed);
        }
        self.latency_ms_total
            .fetch_add(latency_ms, Ordering::Relaxed);
        self.latency_ms_samples_total
            .fetch_add(1, Ordering::Relaxed);
    }

    fn observe_failure(&self, latency_ms: u64) {
        self.failed_total.fetch_add(1, Ordering::Relaxed);
        self.latency_ms_total
            .fetch_add(latency_ms, Ordering::Relaxed);
        self.latency_ms_samples_total
            .fetch_add(1, Ordering::Relaxed);
    }

    fn observe_rate_limited(&self) {
        self.rate_limited_total.fetch_add(1, Ordering::Relaxed);
    }

    fn snapshot(&self) -> (u64, u64, u64, u64, u64, u64) {
        (
            self.request_total.load(Ordering::Relaxed),
            self.success_total.load(Ordering::Relaxed),
            self.failed_total.load(Ordering::Relaxed),
            self.rate_limited_total.load(Ordering::Relaxed),
            self.owner_total.load(Ordering::Relaxed),
            self.non_owner_total.load(Ordering::Relaxed),
        )
    }
}

#[derive(Debug, Default)]
struct OpsRbacRolesWriteMetrics {
    request_total: AtomicU64,
    success_total: AtomicU64,
    failed_total: AtomicU64,
    extractor_rejected_total: AtomicU64,
    rate_limited_total: AtomicU64,
    upsert_total: AtomicU64,
    revoke_total: AtomicU64,
    if_match_invalid_total: AtomicU64,
    if_match_missing_total: AtomicU64,
    revoke_removed_total: AtomicU64,
    revoke_noop_total: AtomicU64,
    latency_ms_total: AtomicU64,
    latency_ms_samples_total: AtomicU64,
}

#[derive(Debug, Clone, Copy)]
struct OpsRbacAuditLogInput<'a> {
    event_type: &'a str,
    operator_user_id: i64,
    target_user_id: Option<i64>,
    decision: &'a str,
    request_id: Option<&'a str>,
    result_count: Option<i64>,
    role: Option<&'a str>,
    removed: Option<bool>,
    error_code: Option<&'a str>,
    failure_reason: Option<&'a str>,
}

#[derive(Debug, Clone, FromRow)]
struct OpsRbacAuditOutboxJob {
    id: i64,
    event_type: String,
    operator_user_id: i64,
    target_user_id: Option<i64>,
    decision: String,
    request_id: Option<String>,
    result_count: Option<i64>,
    role: Option<String>,
    removed: Option<bool>,
    error_code: Option<String>,
    failure_reason: Option<String>,
    attempts: i32,
}

#[derive(Debug, Default, Clone, Copy)]
pub(crate) struct OpsRbacAuditOutboxDispatchReport {
    pub attempted: usize,
    pub delivered: usize,
    pub requeued: usize,
}

impl OpsRbacRolesWriteMetrics {
    fn observe_start_upsert(&self) {
        self.request_total.fetch_add(1, Ordering::Relaxed);
        self.upsert_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_start_revoke(&self) {
        self.request_total.fetch_add(1, Ordering::Relaxed);
        self.revoke_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_success(&self, latency_ms: u64) {
        self.success_total.fetch_add(1, Ordering::Relaxed);
        self.latency_ms_total
            .fetch_add(latency_ms, Ordering::Relaxed);
        self.latency_ms_samples_total
            .fetch_add(1, Ordering::Relaxed);
    }

    fn observe_failure(&self, latency_ms: u64) {
        self.failed_total.fetch_add(1, Ordering::Relaxed);
        self.latency_ms_total
            .fetch_add(latency_ms, Ordering::Relaxed);
        self.latency_ms_samples_total
            .fetch_add(1, Ordering::Relaxed);
    }

    fn observe_extractor_rejected(&self) {
        self.extractor_rejected_total
            .fetch_add(1, Ordering::Relaxed);
    }

    fn observe_rate_limited(&self) {
        self.rate_limited_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_if_match_invalid(&self) {
        self.if_match_invalid_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_if_match_missing(&self) {
        self.if_match_missing_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_revoke_outcome(&self, removed: bool) {
        let target = if removed {
            &self.revoke_removed_total
        } else {
            &self.revoke_noop_total
        };
        target.fetch_add(1, Ordering::Relaxed);
    }

    fn snapshot_revoke_signals(&self) -> (u64, u64, u64, u64) {
        (
            self.if_match_invalid_total.load(Ordering::Relaxed),
            self.if_match_missing_total.load(Ordering::Relaxed),
            self.revoke_removed_total.load(Ordering::Relaxed),
            self.revoke_noop_total.load(Ordering::Relaxed),
        )
    }

    fn snapshot(&self) -> (u64, u64, u64, u64, u64, u64, u64) {
        (
            self.request_total.load(Ordering::Relaxed),
            self.success_total.load(Ordering::Relaxed),
            self.failed_total.load(Ordering::Relaxed),
            self.extractor_rejected_total.load(Ordering::Relaxed),
            self.rate_limited_total.load(Ordering::Relaxed),
            self.upsert_total.load(Ordering::Relaxed),
            self.revoke_total.load(Ordering::Relaxed),
        )
    }
}

#[derive(Debug, Default)]
struct OpsRbacRolesListMetrics {
    request_total: AtomicU64,
    success_total: AtomicU64,
    failed_total: AtomicU64,
    permission_denied_total: AtomicU64,
    rate_limited_total: AtomicU64,
    result_items_total: AtomicU64,
    result_items_samples_total: AtomicU64,
    latency_ms_total: AtomicU64,
    latency_ms_samples_total: AtomicU64,
}

impl OpsRbacRolesListMetrics {
    fn observe_start(&self) {
        self.request_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_success(&self, items_count: usize, latency_ms: u64) {
        self.success_total.fetch_add(1, Ordering::Relaxed);
        self.result_items_total
            .fetch_add(items_count as u64, Ordering::Relaxed);
        self.result_items_samples_total
            .fetch_add(1, Ordering::Relaxed);
        self.latency_ms_total
            .fetch_add(latency_ms, Ordering::Relaxed);
        self.latency_ms_samples_total
            .fetch_add(1, Ordering::Relaxed);
    }

    fn observe_failure(&self, latency_ms: u64) {
        self.failed_total.fetch_add(1, Ordering::Relaxed);
        self.latency_ms_total
            .fetch_add(latency_ms, Ordering::Relaxed);
        self.latency_ms_samples_total
            .fetch_add(1, Ordering::Relaxed);
    }

    fn observe_permission_denied(&self) {
        self.permission_denied_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_rate_limited(&self) {
        self.rate_limited_total.fetch_add(1, Ordering::Relaxed);
    }

    fn snapshot(&self) -> (u64, u64, u64, u64, u64) {
        (
            self.request_total.load(Ordering::Relaxed),
            self.success_total.load(Ordering::Relaxed),
            self.failed_total.load(Ordering::Relaxed),
            self.permission_denied_total.load(Ordering::Relaxed),
            self.rate_limited_total.load(Ordering::Relaxed),
        )
    }
}

static OPS_RBAC_ROLES_LIST_METRICS: LazyLock<OpsRbacRolesListMetrics> =
    LazyLock::new(OpsRbacRolesListMetrics::default);
static OPS_RBAC_ME_METRICS: LazyLock<OpsRbacMeMetrics> = LazyLock::new(OpsRbacMeMetrics::default);
static OPS_RBAC_ROLES_WRITE_METRICS: LazyLock<OpsRbacRolesWriteMetrics> =
    LazyLock::new(OpsRbacRolesWriteMetrics::default);

/// Create debate topic by authorized ops role.
#[utoipa::path(
    post,
    path = "/api/debate/ops/topics",
    request_body = OpsCreateDebateTopicInput,
    responses(
        (status = 201, description = "Created debate topic", body = crate::DebateTopic),
        (status = 400, description = "Invalid input", body = crate::ErrorOutput),
        (status = 401, description = "Auth error", body = crate::ErrorOutput),
        (status = 403, description = "Phone not bound", body = crate::ErrorOutput),
        (status = 404, description = "Resource not found", body = crate::ErrorOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
        (status = 429, description = "Rate limited", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn create_debate_topic_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(input): Json<OpsCreateDebateTopicInput>,
) -> Result<Response, AppError> {
    let user_decision = enforce_rate_limit(
        &state,
        "ops_debate_topic_create_user",
        &user.id.to_string(),
        OPS_DEBATE_TOPIC_CREATE_USER_RATE_LIMIT_PER_WINDOW,
        OPS_DEBATE_TOPIC_CREATE_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    let user_rate_headers = build_rate_limit_headers(&user_decision)?;
    if !user_decision.allowed {
        return Ok(rate_limit_exceeded_response(
            "ops_debate_topic_create",
            user_rate_headers,
        ));
    }

    let ip_limit_key = request_rate_limit_ip_key_with_user_fallback(
        &headers,
        user.id,
        &state.config.server.forwarded_header_trust,
    );
    let ip_decision = enforce_rate_limit(
        &state,
        "ops_debate_topic_create_ip",
        &ip_limit_key,
        OPS_DEBATE_TOPIC_CREATE_IP_RATE_LIMIT_PER_WINDOW,
        OPS_DEBATE_TOPIC_CREATE_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    if !ip_decision.allowed {
        return Ok(rate_limit_exceeded_response(
            "ops_debate_topic_create",
            build_rate_limit_headers(&ip_decision)?,
        ));
    }

    let request_idempotency_key = request_idempotency_key_from_headers(
        &headers,
        "ops_debate_topic_create_idempotency_key_invalid",
        "ops_debate_topic_create_idempotency_key_too_long",
        OPS_DEBATE_TOPIC_CREATE_IDEMPOTENCY_MAX_LEN,
    )?;
    let idempotency_lock_key = request_idempotency_key
        .as_deref()
        .map(|key| format!("u{}:{key}", user.id));
    if let Some(lock_key) = idempotency_lock_key.as_deref() {
        let acquired = try_acquire_idempotency_or_fail_open(
            &state,
            "ops_debate_topic_create",
            lock_key,
            OPS_DEBATE_TOPIC_CREATE_IDEMPOTENCY_TTL_SECS,
        )
        .await;
        if !acquired {
            return Err(AppError::DebateConflict(
                "idempotency_conflict:ops_debate_topic_create".to_string(),
            ));
        }
    }

    let ret = state
        .create_debate_topic_by_owner_with_meta(&user, input, request_idempotency_key.as_deref())
        .await;
    if let Some(lock_key) = idempotency_lock_key.as_deref() {
        release_idempotency_best_effort(&state, "ops_debate_topic_create", lock_key).await;
    }
    let (topic, _) = ret?;
    Ok((StatusCode::CREATED, user_rate_headers, Json(topic)).into_response())
}

/// Update debate topic by authorized ops role.
#[utoipa::path(
    put,
    path = "/api/debate/ops/topics/{id}",
    params(
        ("id" = u64, Path, description = "Debate topic id")
    ),
    request_body = OpsUpdateDebateTopicInput,
    responses(
        (status = 200, description = "Updated debate topic", body = crate::DebateTopic),
        (status = 400, description = "Invalid input", body = crate::ErrorOutput),
        (status = 401, description = "Auth error", body = crate::ErrorOutput),
        (status = 403, description = "Phone not bound", body = crate::ErrorOutput),
        (status = 422, description = "Body parse error", body = crate::ErrorOutput),
        (status = 404, description = "Topic not found", body = crate::ErrorOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn update_debate_topic_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Json(input): Json<OpsUpdateDebateTopicInput>,
) -> Result<impl IntoResponse, AppError> {
    let topic = state.update_debate_topic_by_owner(&user, id, input).await?;
    Ok((StatusCode::OK, Json(topic)))
}

/// Create debate session by authorized ops role.
#[utoipa::path(
    post,
    path = "/api/debate/ops/sessions",
    request_body = OpsCreateDebateSessionInput,
    responses(
        (status = 201, description = "Created debate session", body = crate::DebateSessionSummary),
        (status = 400, description = "Invalid input", body = crate::ErrorOutput),
        (status = 401, description = "Auth error", body = crate::ErrorOutput),
        (status = 403, description = "Phone not bound", body = crate::ErrorOutput),
        (status = 422, description = "Body parse error", body = crate::ErrorOutput),
        (status = 404, description = "Topic not found", body = crate::ErrorOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
        (status = 429, description = "Rate limited", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn create_debate_session_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(input): Json<OpsCreateDebateSessionInput>,
) -> Result<Response, AppError> {
    let user_decision = enforce_rate_limit(
        &state,
        "ops_debate_session_create_user",
        &user.id.to_string(),
        OPS_DEBATE_SESSION_CREATE_USER_RATE_LIMIT_PER_WINDOW,
        OPS_DEBATE_SESSION_CREATE_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let user_decision = maybe_override_rate_limit_decision(
        &headers,
        "ops_debate_session_create_user",
        user_decision,
    );
    let user_rate_headers = build_rate_limit_headers(&user_decision)?;
    if !user_decision.allowed {
        return Ok(rate_limit_exceeded_response(
            "ops_debate_session_create",
            user_rate_headers,
        ));
    }

    let ip_limit_key = request_rate_limit_ip_key_with_user_fallback(
        &headers,
        user.id,
        &state.config.server.forwarded_header_trust,
    );
    let ip_decision = enforce_rate_limit(
        &state,
        "ops_debate_session_create_ip",
        &ip_limit_key,
        OPS_DEBATE_SESSION_CREATE_IP_RATE_LIMIT_PER_WINDOW,
        OPS_DEBATE_SESSION_CREATE_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let ip_decision =
        maybe_override_rate_limit_decision(&headers, "ops_debate_session_create_ip", ip_decision);
    if !ip_decision.allowed {
        return Ok(rate_limit_exceeded_response(
            "ops_debate_session_create",
            build_rate_limit_headers(&ip_decision)?,
        ));
    }

    let request_idempotency_key = request_idempotency_key_from_headers(
        &headers,
        "ops_debate_session_create_idempotency_key_invalid",
        "ops_debate_session_create_idempotency_key_too_long",
        OPS_DEBATE_SESSION_CREATE_IDEMPOTENCY_MAX_LEN,
    )?;
    let idempotency_lock_key = request_idempotency_key
        .as_deref()
        .map(|key| format!("u{}:{key}", user.id));
    if let Some(lock_key) = idempotency_lock_key.as_deref() {
        let acquired = try_acquire_idempotency_or_fail_open(
            &state,
            "ops_debate_session_create",
            lock_key,
            OPS_DEBATE_SESSION_CREATE_IDEMPOTENCY_TTL_SECS,
        )
        .await;
        if !acquired {
            return Err(AppError::DebateConflict(
                "idempotency_conflict:ops_debate_session_create".to_string(),
            ));
        }
    }

    let ret = state
        .create_debate_session_by_owner_with_meta(&user, input, request_idempotency_key.as_deref())
        .await;
    if let Some(lock_key) = idempotency_lock_key.as_deref() {
        release_idempotency_best_effort(&state, "ops_debate_session_create", lock_key).await;
    }
    let (session, _) = ret?;
    Ok((StatusCode::CREATED, user_rate_headers, Json(session)).into_response())
}

/// Update debate session by authorized ops role.
#[utoipa::path(
    put,
    path = "/api/debate/ops/sessions/{id}",
    params(
        ("id" = u64, Path, description = "Debate session id")
    ),
    request_body = OpsUpdateDebateSessionInput,
    responses(
        (status = 200, description = "Updated debate session", body = crate::DebateSessionSummary),
        (status = 400, description = "Invalid input", body = crate::ErrorOutput),
        (status = 401, description = "Auth error", body = crate::ErrorOutput),
        (status = 403, description = "Phone not bound", body = crate::ErrorOutput),
        (status = 404, description = "Session not found", body = crate::ErrorOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
        (status = 422, description = "Request body parse error", body = crate::ErrorOutput),
        (status = 429, description = "Rate limited", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn update_debate_session_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    headers: HeaderMap,
    Json(input): Json<OpsUpdateDebateSessionInput>,
) -> Result<Response, AppError> {
    let user_decision = enforce_rate_limit(
        &state,
        "ops_debate_session_update_user",
        &user.id.to_string(),
        OPS_DEBATE_SESSION_UPDATE_USER_RATE_LIMIT_PER_WINDOW,
        OPS_DEBATE_SESSION_UPDATE_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let user_decision = maybe_override_rate_limit_decision(
        &headers,
        "ops_debate_session_update_user",
        user_decision,
    );
    let user_rate_headers = build_rate_limit_headers(&user_decision)?;
    if !user_decision.allowed {
        return Ok(rate_limit_exceeded_response(
            "ops_debate_session_update",
            user_rate_headers,
        ));
    }

    let ip_limit_key = request_rate_limit_ip_key_with_user_fallback(
        &headers,
        user.id,
        &state.config.server.forwarded_header_trust,
    );
    let ip_decision = enforce_rate_limit(
        &state,
        "ops_debate_session_update_ip",
        &ip_limit_key,
        OPS_DEBATE_SESSION_UPDATE_IP_RATE_LIMIT_PER_WINDOW,
        OPS_DEBATE_SESSION_UPDATE_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let ip_decision =
        maybe_override_rate_limit_decision(&headers, "ops_debate_session_update_ip", ip_decision);
    if !ip_decision.allowed {
        return Ok(rate_limit_exceeded_response(
            "ops_debate_session_update",
            build_rate_limit_headers(&ip_decision)?,
        ));
    }

    let session = state
        .update_debate_session_by_owner(&user, id, input)
        .await?;
    Ok((StatusCode::OK, user_rate_headers, Json(session)).into_response())
}

/// List platform ops role assignments (platform admin only).
#[utoipa::path(
    get,
    path = "/api/debate/ops/rbac/roles",
    params(
        ListOpsRoleAssignmentsQuery
    ),
    responses(
        (status = 200, description = "Ops role assignments", body = crate::ListOpsRoleAssignmentsOutput),
        (status = 401, description = "Auth error", body = crate::ErrorOutput),
        (status = 403, description = "Phone not bound", body = crate::ErrorOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
        (status = 429, description = "Rate limited", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_ops_role_assignments_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(query): Query<ListOpsRoleAssignmentsQuery>,
) -> Result<Response, AppError> {
    let started_at = Instant::now();
    let request_id = request_id_from_headers(&headers);
    OPS_RBAC_ROLES_LIST_METRICS.observe_start();

    let user_decision = enforce_rate_limit(
        &state,
        "ops_rbac_roles_list_user",
        &user.id.to_string(),
        OPS_RBAC_ROLES_LIST_USER_RATE_LIMIT_PER_WINDOW,
        OPS_RBAC_ROLES_LIST_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let user_decision =
        maybe_override_rate_limit_decision(&headers, "ops_rbac_roles_list_user", user_decision);
    let user_rate_headers = build_rate_limit_headers(&user_decision)?;
    if !user_decision.allowed {
        OPS_RBAC_ROLES_LIST_METRICS.observe_rate_limited();
        tracing::warn!(
            user_id = user.id,
            request_id = request_id.as_deref().unwrap_or_default(),
            audit_event = "ops_rbac_roles_list_read_rate_limited",
            decision = "rate_limited_user",
            pii_level = ?query.pii_level,
            "list ops rbac role assignments blocked by user rate limiter"
        );
        insert_ops_rbac_audit_log_best_effort(
            &state,
            OpsRbacAuditLogInput {
                event_type: OPS_RBAC_AUDIT_EVENT_ROLES_LIST_READ,
                operator_user_id: user.id,
                target_user_id: None,
                decision: "rate_limited_user",
                request_id: request_id.as_deref(),
                result_count: None,
                role: None,
                removed: None,
                error_code: None,
                failure_reason: None,
            },
        )
        .await;
        return Ok(rate_limit_exceeded_response(
            "ops_rbac_roles_list",
            user_rate_headers,
        ));
    }

    let ip_limit_key = request_rate_limit_ip_key_with_user_fallback(
        &headers,
        user.id,
        &state.config.server.forwarded_header_trust,
    );
    let ip_decision = enforce_rate_limit(
        &state,
        "ops_rbac_roles_list_ip",
        &ip_limit_key,
        OPS_RBAC_ROLES_LIST_IP_RATE_LIMIT_PER_WINDOW,
        OPS_RBAC_ROLES_LIST_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let ip_decision =
        maybe_override_rate_limit_decision(&headers, "ops_rbac_roles_list_ip", ip_decision);
    if !ip_decision.allowed {
        OPS_RBAC_ROLES_LIST_METRICS.observe_rate_limited();
        tracing::warn!(
            user_id = user.id,
            request_id = request_id.as_deref().unwrap_or_default(),
            audit_event = "ops_rbac_roles_list_read_rate_limited",
            decision = "rate_limited_ip",
            pii_level = ?query.pii_level,
            "list ops rbac role assignments blocked by ip rate limiter"
        );
        insert_ops_rbac_audit_log_best_effort(
            &state,
            OpsRbacAuditLogInput {
                event_type: OPS_RBAC_AUDIT_EVENT_ROLES_LIST_READ,
                operator_user_id: user.id,
                target_user_id: None,
                decision: "rate_limited_ip",
                request_id: request_id.as_deref(),
                result_count: None,
                role: None,
                removed: None,
                error_code: None,
                failure_reason: None,
            },
        )
        .await;
        return Ok(rate_limit_exceeded_response(
            "ops_rbac_roles_list",
            build_rate_limit_headers(&ip_decision)?,
        ));
    }

    let ret = match state
        .list_ops_role_assignments_by_owner(&user, query.pii_level)
        .await
    {
        Ok(v) => v,
        Err(err) => {
            let latency_ms = started_at.elapsed().as_millis() as u64;
            OPS_RBAC_ROLES_LIST_METRICS.observe_failure(latency_ms);
            let (audit_error_code, audit_failure_reason) = classify_ops_rbac_failure(&err);
            if let AppError::DebateConflict(msg) = &err {
                if msg == OPS_RBAC_PERMISSION_DENIED_ROLE_MANAGE_CODE
                    || msg.starts_with(&format!("{OPS_RBAC_PERMISSION_DENIED_ROLE_MANAGE_CODE}:"))
                {
                    OPS_RBAC_ROLES_LIST_METRICS.observe_permission_denied();
                }
            }
            tracing::warn!(
                user_id = user.id,
                request_id = request_id.as_deref().unwrap_or_default(),
                audit_event = "ops_rbac_roles_list_read_failed",
                decision = "failed",
                latency_ms,
                pii_level = ?query.pii_level,
                "list ops rbac role assignments failed: {}",
                err
            );
            insert_ops_rbac_audit_log_best_effort(
                &state,
                OpsRbacAuditLogInput {
                    event_type: OPS_RBAC_AUDIT_EVENT_ROLES_LIST_READ,
                    operator_user_id: user.id,
                    target_user_id: None,
                    decision: "failed",
                    request_id: request_id.as_deref(),
                    result_count: None,
                    role: None,
                    removed: None,
                    error_code: audit_error_code.as_deref(),
                    failure_reason: Some(audit_failure_reason),
                },
            )
            .await;
            return Err(err);
        }
    };

    let latency_ms = started_at.elapsed().as_millis() as u64;
    OPS_RBAC_ROLES_LIST_METRICS.observe_success(ret.items.len(), latency_ms);
    let (request_total, success_total, failed_total, permission_denied_total, rate_limited_total) =
        OPS_RBAC_ROLES_LIST_METRICS.snapshot();
    tracing::info!(
        user_id = user.id,
        request_id = request_id.as_deref().unwrap_or_default(),
        audit_event = "ops_rbac_roles_list_read",
        decision = "success",
        result_count = ret.items.len(),
        latency_ms,
        pii_level = ?query.pii_level,
        ops_rbac_roles_list_request_total = request_total,
        ops_rbac_roles_list_success_total = success_total,
        ops_rbac_roles_list_failed_total = failed_total,
        ops_rbac_roles_list_permission_denied_total = permission_denied_total,
        ops_rbac_roles_list_rate_limited_total = rate_limited_total,
        "list ops rbac role assignments served"
    );
    insert_ops_rbac_audit_log_best_effort(
        &state,
        OpsRbacAuditLogInput {
            event_type: OPS_RBAC_AUDIT_EVENT_ROLES_LIST_READ,
            operator_user_id: user.id,
            target_user_id: None,
            decision: "success",
            request_id: request_id.as_deref(),
            result_count: i64::try_from(ret.items.len()).ok(),
            role: None,
            removed: None,
            error_code: None,
            failure_reason: None,
        },
    )
    .await;
    Ok((StatusCode::OK, user_rate_headers, Json(ret)).into_response())
}

/// Get current user's ops RBAC capability snapshot.
#[utoipa::path(
    get,
    path = "/api/debate/ops/rbac/me",
    responses(
        (status = 200, description = "Current ops RBAC capabilities", body = crate::GetOpsRbacMeOutput),
        (status = 401, description = "Auth error", body = crate::ErrorOutput),
        (status = 403, description = "Phone not bound", body = crate::ErrorOutput),
        (status = 429, description = "Rate limited", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_ops_rbac_me_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Response, AppError> {
    let started_at = Instant::now();
    let request_id = request_id_from_headers(&headers);
    OPS_RBAC_ME_METRICS.observe_start();

    let user_decision = enforce_rate_limit(
        &state,
        "ops_rbac_me_user",
        &user.id.to_string(),
        OPS_RBAC_ME_USER_RATE_LIMIT_PER_WINDOW,
        OPS_RBAC_ME_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let user_decision =
        maybe_override_rate_limit_decision(&headers, "ops_rbac_me_user", user_decision);
    let user_rate_headers = build_rate_limit_headers(&user_decision)?;
    if !user_decision.allowed {
        OPS_RBAC_ME_METRICS.observe_rate_limited();
        tracing::warn!(
            user_id = user.id,
            request_id = request_id.as_deref().unwrap_or_default(),
            audit_event = "ops_rbac_me_read_rate_limited",
            decision = "rate_limited_user",
            "get ops rbac me blocked by user rate limiter"
        );
        insert_ops_rbac_audit_log_best_effort(
            &state,
            OpsRbacAuditLogInput {
                event_type: OPS_RBAC_AUDIT_EVENT_RBAC_ME_READ,
                operator_user_id: user.id,
                target_user_id: None,
                decision: "rate_limited_user",
                request_id: request_id.as_deref(),
                result_count: None,
                role: None,
                removed: None,
                error_code: None,
                failure_reason: None,
            },
        )
        .await;
        return Ok(rate_limit_exceeded_response(
            "ops_rbac_me",
            user_rate_headers,
        ));
    }

    let ip_limit_key = request_rate_limit_ip_key_with_user_fallback(
        &headers,
        user.id,
        &state.config.server.forwarded_header_trust,
    );
    let ip_decision = enforce_rate_limit(
        &state,
        "ops_rbac_me_ip",
        &ip_limit_key,
        OPS_RBAC_ME_IP_RATE_LIMIT_PER_WINDOW,
        OPS_RBAC_ME_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let ip_decision = maybe_override_rate_limit_decision(&headers, "ops_rbac_me_ip", ip_decision);
    if !ip_decision.allowed {
        OPS_RBAC_ME_METRICS.observe_rate_limited();
        tracing::warn!(
            user_id = user.id,
            request_id = request_id.as_deref().unwrap_or_default(),
            audit_event = "ops_rbac_me_read_rate_limited",
            decision = "rate_limited_ip",
            "get ops rbac me blocked by ip rate limiter"
        );
        insert_ops_rbac_audit_log_best_effort(
            &state,
            OpsRbacAuditLogInput {
                event_type: OPS_RBAC_AUDIT_EVENT_RBAC_ME_READ,
                operator_user_id: user.id,
                target_user_id: None,
                decision: "rate_limited_ip",
                request_id: request_id.as_deref(),
                result_count: None,
                role: None,
                removed: None,
                error_code: None,
                failure_reason: None,
            },
        )
        .await;
        return Ok(rate_limit_exceeded_response(
            "ops_rbac_me",
            build_rate_limit_headers(&ip_decision)?,
        ));
    }

    let ret = match state.get_ops_rbac_me(&user).await {
        Ok(v) => v,
        Err(err) => {
            let latency_ms = started_at.elapsed().as_millis() as u64;
            OPS_RBAC_ME_METRICS.observe_failure(latency_ms);
            let (audit_error_code, audit_failure_reason) = classify_ops_rbac_failure(&err);
            tracing::warn!(
                user_id = user.id,
                request_id = request_id.as_deref().unwrap_or_default(),
                audit_event = "ops_rbac_me_read_failed",
                decision = "failed",
                latency_ms,
                "get ops rbac me failed: {}",
                err
            );
            insert_ops_rbac_audit_log_best_effort(
                &state,
                OpsRbacAuditLogInput {
                    event_type: OPS_RBAC_AUDIT_EVENT_RBAC_ME_READ,
                    operator_user_id: user.id,
                    target_user_id: None,
                    decision: "failed",
                    request_id: request_id.as_deref(),
                    result_count: None,
                    role: None,
                    removed: None,
                    error_code: audit_error_code.as_deref(),
                    failure_reason: Some(audit_failure_reason),
                },
            )
            .await;
            return Err(err);
        }
    };
    let latency_ms = started_at.elapsed().as_millis() as u64;
    OPS_RBAC_ME_METRICS.observe_success(ret.is_owner, latency_ms);
    let (
        request_total,
        success_total,
        failed_total,
        rate_limited_total,
        owner_total,
        non_owner_total,
    ) = OPS_RBAC_ME_METRICS.snapshot();
    tracing::info!(
        user_id = user.id,
        request_id = request_id.as_deref().unwrap_or_default(),
        audit_event = "ops_rbac_me_read",
        decision = "success",
        is_owner = ret.is_owner,
        role = ret.role.as_deref().unwrap_or(""),
        latency_ms,
        ops_rbac_me_request_total = request_total,
        ops_rbac_me_success_total = success_total,
        ops_rbac_me_failed_total = failed_total,
        ops_rbac_me_rate_limited_total = rate_limited_total,
        ops_rbac_me_owner_total = owner_total,
        ops_rbac_me_non_owner_total = non_owner_total,
        "get ops rbac me served"
    );
    insert_ops_rbac_audit_log_best_effort(
        &state,
        OpsRbacAuditLogInput {
            event_type: OPS_RBAC_AUDIT_EVENT_RBAC_ME_READ,
            operator_user_id: user.id,
            target_user_id: None,
            decision: "success",
            request_id: request_id.as_deref(),
            result_count: None,
            role: ret.role.as_deref(),
            removed: None,
            error_code: None,
            failure_reason: None,
        },
    )
    .await;
    Ok((StatusCode::OK, user_rate_headers, Json(ret)).into_response())
}

/// Get current ops observability config snapshot.
#[utoipa::path(
    get,
    path = "/api/debate/ops/observability/config",
    responses(
        (status = 200, description = "Ops observability config", body = crate::GetOpsObservabilityConfigOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_ops_observability_config_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.get_ops_observability_config(&user).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Get canonical ops metrics dictionary for observability and SLO governance.
#[utoipa::path(
    get,
    path = "/api/debate/ops/observability/metrics-dictionary",
    responses(
        (status = 200, description = "Ops metrics dictionary", body = crate::GetOpsMetricsDictionaryOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_ops_observability_metrics_dictionary_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.get_ops_metrics_dictionary(&user).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Get current SLO snapshot for ops observability.
#[utoipa::path(
    get,
    path = "/api/debate/ops/observability/slo-snapshot",
    responses(
        (status = 200, description = "Ops SLO snapshot", body = crate::GetOpsSloSnapshotOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_ops_observability_slo_snapshot_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.get_ops_observability_slo_snapshot(&user).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Evaluate service split readiness by R6 threshold rules.
#[utoipa::path(
    get,
    path = "/api/debate/ops/observability/split-readiness",
    responses(
        (status = 200, description = "Service split readiness snapshot", body = crate::GetOpsServiceSplitReadinessOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_ops_service_split_readiness_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.get_ops_service_split_readiness(&user).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// List split-readiness manual review audit history for platform scope.
#[utoipa::path(
    get,
    path = "/api/debate/ops/observability/split-readiness/reviews",
    params(
        ListOpsServiceSplitReviewAuditsQuery
    ),
    responses(
        (status = 200, description = "Service split readiness review audits", body = crate::ListOpsServiceSplitReviewAuditsOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_ops_service_split_review_audits_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Query(query): Query<ListOpsServiceSplitReviewAuditsQuery>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state
        .list_ops_service_split_review_audits(&user, query)
        .await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Upsert manual review input for split-readiness compliance threshold.
#[utoipa::path(
    put,
    path = "/api/debate/ops/observability/split-readiness/review",
    request_body = UpsertOpsServiceSplitReviewInput,
    responses(
        (status = 200, description = "Service split readiness snapshot", body = crate::GetOpsServiceSplitReadinessOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn upsert_ops_service_split_review_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Json(input): Json<UpsertOpsServiceSplitReviewInput>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.upsert_ops_service_split_review(&user, input).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Upsert ops observability thresholds for platform scope.
#[utoipa::path(
    put,
    path = "/api/debate/ops/observability/thresholds",
    request_body = OpsObservabilityThresholds,
    responses(
        (status = 200, description = "Updated ops observability config", body = crate::GetOpsObservabilityConfigOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn upsert_ops_observability_thresholds_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Json(input): Json<OpsObservabilityThresholds>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state
        .upsert_ops_observability_thresholds(&user, input)
        .await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Upsert ops observability anomaly-state map for platform scope.
#[utoipa::path(
    put,
    path = "/api/debate/ops/observability/anomaly-state",
    request_body = UpdateOpsObservabilityAnomalyStateInput,
    responses(
        (status = 200, description = "Updated ops observability config", body = crate::GetOpsObservabilityConfigOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn upsert_ops_observability_anomaly_state_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Json(input): Json<UpdateOpsObservabilityAnomalyStateInput>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state
        .upsert_ops_observability_anomaly_state(&user, input)
        .await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Apply anomaly-state action for a single alert key in platform scope.
#[utoipa::path(
    post,
    path = "/api/debate/ops/observability/anomaly-state/actions",
    request_body = ApplyOpsObservabilityAnomalyActionInput,
    responses(
        (status = 200, description = "Updated ops observability config", body = crate::GetOpsObservabilityConfigOutput),
        (status = 400, description = "Invalid action input", body = crate::ErrorOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn apply_ops_observability_anomaly_action_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Json(input): Json<ApplyOpsObservabilityAnomalyActionInput>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state
        .apply_ops_observability_anomaly_action(&user, input)
        .await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Trigger one-shot observability evaluation for platform scope.
#[utoipa::path(
    post,
    path = "/api/debate/ops/observability/evaluate-once",
    params(
        RunOpsObservabilityEvaluationQuery
    ),
    responses(
        (status = 200, description = "Ops alert evaluation report", body = crate::OpsAlertEvalReport),
        (status = 429, description = "Rate limit exceeded", body = crate::ErrorOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn run_ops_observability_evaluation_once_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Query(query): Query<RunOpsObservabilityEvaluationQuery>,
) -> Result<impl IntoResponse, AppError> {
    let limiter_key = format!("user:{}", user.id);
    let decision = enforce_rate_limit(
        &state,
        "ops_observability_evaluate_once",
        &limiter_key,
        OPS_OBSERVABILITY_EVAL_RATE_LIMIT_PER_WINDOW,
        OPS_OBSERVABILITY_EVAL_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    let rate_headers = build_rate_limit_headers(&decision)?;
    if !decision.allowed {
        return Ok(rate_limit_exceeded_response(
            "ops_observability_evaluate_once",
            rate_headers,
        ));
    }
    let ret = if query.dry_run.unwrap_or(false) {
        state.preview_ops_observability_alerts_by_ops(&user).await?
    } else {
        state
            .evaluate_ops_observability_alerts_by_ops(&user)
            .await?
    };
    Ok((StatusCode::OK, rate_headers, Json(ret)).into_response())
}

/// List ops observability alert notifications.
#[utoipa::path(
    get,
    path = "/api/debate/ops/observability/alerts",
    params(
        ListOpsAlertNotificationsQuery
    ),
    responses(
        (status = 200, description = "Ops alert notifications", body = crate::ListOpsAlertNotificationsOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_ops_alert_notifications_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Query(input): Query<ListOpsAlertNotificationsQuery>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.list_ops_alert_notifications(&user, input).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// List Kafka DLQ events for platform scope.
#[utoipa::path(
    get,
    path = "/api/debate/ops/kafka/dlq",
    params(
        ListKafkaDlqEventsQuery
    ),
    responses(
        (status = 200, description = "Kafka DLQ events", body = crate::ListKafkaDlqEventsOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_kafka_dlq_events_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Query(input): Query<ListKafkaDlqEventsQuery>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.list_kafka_dlq_events(&user, input).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Get Kafka transport cutover readiness and outbox relay metrics snapshot.
#[utoipa::path(
    get,
    path = "/api/debate/ops/kafka/readiness",
    responses(
        (status = 200, description = "Kafka transport readiness", body = crate::GetKafkaTransportReadinessOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_kafka_transport_readiness_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.get_kafka_transport_readiness(&user).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Replay Kafka DLQ event by id.
#[utoipa::path(
    post,
    path = "/api/debate/ops/kafka/dlq/{id}/replay",
    params(
        ("id" = u64, Path, description = "Kafka DLQ event id")
    ),
    responses(
        (status = 200, description = "Replay result", body = crate::KafkaDlqActionOutput),
        (status = 404, description = "DLQ event not found", body = crate::ErrorOutput),
        (status = 409, description = "Permission or state conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn replay_kafka_dlq_event_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.replay_kafka_dlq_event(&user, id).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Discard Kafka DLQ event by id.
#[utoipa::path(
    post,
    path = "/api/debate/ops/kafka/dlq/{id}/discard",
    params(
        ("id" = u64, Path, description = "Kafka DLQ event id")
    ),
    responses(
        (status = 200, description = "Discard result", body = crate::KafkaDlqActionOutput),
        (status = 404, description = "DLQ event not found", body = crate::ErrorOutput),
        (status = 409, description = "Permission or state conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn discard_kafka_dlq_event_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.discard_kafka_dlq_event(&user, id).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Upsert an ops role assignment (owner only).
#[utoipa::path(
    put,
    path = "/api/debate/ops/rbac/roles/{userId}",
    params(
        ("userId" = u64, Path, description = "Target user id"),
        ("If-Match" = String, Header, description = "Required expected RBAC revision. Supports plain revision string or quoted string.")
    ),
    request_body = UpsertOpsRoleInput,
    responses(
        (status = 200, description = "Updated ops role assignment", body = crate::OpsRoleAssignment),
        (status = 400, description = "Invalid input", body = crate::ErrorOutput),
        (status = 401, description = "Auth error", body = crate::ErrorOutput),
        (status = 403, description = "Phone not bound", body = crate::ErrorOutput),
        (status = 404, description = "Target user not found", body = crate::ErrorOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
        (status = 429, description = "Rate limited", body = crate::ErrorOutput),
        (status = 415, description = "Unsupported media type", body = crate::ErrorOutput),
        (status = 422, description = "Request body parse error", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn upsert_ops_role_assignment_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(user_id): Path<u64>,
    headers: HeaderMap,
    input: Result<Json<UpsertOpsRoleInput>, JsonRejection>,
) -> Result<Response, AppError> {
    let started_at = Instant::now();
    let request_id = request_id_from_headers(&headers);
    let target_user_id = i64::try_from(user_id).ok();
    OPS_RBAC_ROLES_WRITE_METRICS.observe_start_upsert();
    let input = match input {
        Ok(Json(input)) => input,
        Err(rejection) => {
            let latency_ms = started_at.elapsed().as_millis() as u64;
            OPS_RBAC_ROLES_WRITE_METRICS.observe_failure(latency_ms);
            OPS_RBAC_ROLES_WRITE_METRICS.observe_extractor_rejected();
            let (status, error_code, failure_reason) =
                classify_ops_rbac_upsert_body_rejection(&rejection);
            let (
                request_total,
                success_total,
                failed_total,
                extractor_rejected_total,
                rate_limited_total,
                upsert_total,
                revoke_total,
            ) = OPS_RBAC_ROLES_WRITE_METRICS.snapshot();
            tracing::warn!(
                user_id = user.id,
                target_user_id = user_id,
                request_id = request_id.as_deref().unwrap_or_default(),
                audit_event = "ops_rbac_roles_write_upsert_extractor_rejected",
                decision = "failed",
                status = status.as_u16(),
                error_code,
                failure_reason,
                latency_ms,
                ops_rbac_roles_write_request_total = request_total,
                ops_rbac_roles_write_success_total = success_total,
                ops_rbac_roles_write_failed_total = failed_total,
                ops_rbac_roles_write_extractor_rejected_total = extractor_rejected_total,
                ops_rbac_roles_write_rate_limited_total = rate_limited_total,
                ops_rbac_roles_write_upsert_total = upsert_total,
                ops_rbac_roles_write_revoke_total = revoke_total,
                "upsert ops role assignment request rejected by extractor: {}",
                rejection
            );
            insert_ops_rbac_audit_log_best_effort(
                &state,
                OpsRbacAuditLogInput {
                    event_type: OPS_RBAC_AUDIT_EVENT_ROLE_UPSERT,
                    operator_user_id: user.id,
                    target_user_id,
                    decision: "failed",
                    request_id: request_id.as_deref(),
                    result_count: None,
                    role: None,
                    removed: None,
                    error_code: Some(error_code),
                    failure_reason: Some(failure_reason),
                },
            )
            .await;
            return Ok((status, Json(crate::ErrorOutput::new(error_code))).into_response());
        }
    };
    let requested_role = input.role.clone();
    let expected_rbac_revision = match parse_ops_rbac_if_match_header(&headers) {
        Ok(value) => value,
        Err(error_code) => {
            let latency_ms = started_at.elapsed().as_millis() as u64;
            OPS_RBAC_ROLES_WRITE_METRICS.observe_failure(latency_ms);
            OPS_RBAC_ROLES_WRITE_METRICS.observe_if_match_invalid();
            let (
                request_total,
                success_total,
                failed_total,
                extractor_rejected_total,
                rate_limited_total,
                upsert_total,
                revoke_total,
            ) = OPS_RBAC_ROLES_WRITE_METRICS.snapshot();
            tracing::warn!(
                user_id = user.id,
                target_user_id = user_id,
                request_id = request_id.as_deref().unwrap_or_default(),
                audit_event = "ops_rbac_roles_write_upsert_if_match_invalid",
                decision = "failed",
                status = StatusCode::BAD_REQUEST.as_u16(),
                error_code,
                latency_ms,
                ops_rbac_roles_write_request_total = request_total,
                ops_rbac_roles_write_success_total = success_total,
                ops_rbac_roles_write_failed_total = failed_total,
                ops_rbac_roles_write_extractor_rejected_total = extractor_rejected_total,
                ops_rbac_roles_write_rate_limited_total = rate_limited_total,
                ops_rbac_roles_write_upsert_total = upsert_total,
                ops_rbac_roles_write_revoke_total = revoke_total,
                "upsert ops role assignment rejected because if-match is invalid"
            );
            insert_ops_rbac_audit_log_best_effort(
                &state,
                OpsRbacAuditLogInput {
                    event_type: OPS_RBAC_AUDIT_EVENT_ROLE_UPSERT,
                    operator_user_id: user.id,
                    target_user_id,
                    decision: "failed",
                    request_id: request_id.as_deref(),
                    result_count: None,
                    role: Some(requested_role.as_str()),
                    removed: None,
                    error_code: Some(error_code),
                    failure_reason: Some(OPS_RBAC_AUDIT_FAILURE_VALIDATION_ERROR),
                },
            )
            .await;
            return Ok((
                StatusCode::BAD_REQUEST,
                Json(crate::ErrorOutput::new(error_code)),
            )
                .into_response());
        }
    };

    let user_decision = enforce_rate_limit_with_disabled_fallback(
        &state,
        "ops_rbac_roles_write_user",
        &user.id.to_string(),
        OPS_RBAC_ROLES_WRITE_USER_RATE_LIMIT_PER_WINDOW,
        OPS_RBAC_ROLES_WRITE_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let user_decision =
        maybe_override_rate_limit_decision(&headers, "ops_rbac_roles_write_user", user_decision);
    let user_rate_headers = build_rate_limit_headers(&user_decision)?;
    if !user_decision.allowed {
        OPS_RBAC_ROLES_WRITE_METRICS.observe_rate_limited();
        tracing::warn!(
            user_id = user.id,
            target_user_id = user_id,
            request_id = request_id.as_deref().unwrap_or_default(),
            audit_event = "ops_rbac_roles_write_upsert_rate_limited",
            decision = "rate_limited_user",
            "upsert ops role assignment blocked by user rate limiter"
        );
        insert_ops_rbac_audit_log_best_effort(
            &state,
            OpsRbacAuditLogInput {
                event_type: OPS_RBAC_AUDIT_EVENT_ROLE_UPSERT,
                operator_user_id: user.id,
                target_user_id,
                decision: "rate_limited_user",
                request_id: request_id.as_deref(),
                result_count: None,
                role: Some(requested_role.as_str()),
                removed: None,
                error_code: None,
                failure_reason: None,
            },
        )
        .await;
        return Ok(rate_limit_exceeded_response(
            "ops_rbac_roles_write",
            user_rate_headers,
        ));
    }

    let ip_limit_key = request_rate_limit_ip_key_with_user_fallback(
        &headers,
        user.id,
        &state.config.server.forwarded_header_trust,
    );
    let ip_decision = enforce_rate_limit_with_disabled_fallback(
        &state,
        "ops_rbac_roles_write_ip",
        &ip_limit_key,
        OPS_RBAC_ROLES_WRITE_IP_RATE_LIMIT_PER_WINDOW,
        OPS_RBAC_ROLES_WRITE_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let ip_decision =
        maybe_override_rate_limit_decision(&headers, "ops_rbac_roles_write_ip", ip_decision);
    if !ip_decision.allowed {
        OPS_RBAC_ROLES_WRITE_METRICS.observe_rate_limited();
        tracing::warn!(
            user_id = user.id,
            target_user_id = user_id,
            request_id = request_id.as_deref().unwrap_or_default(),
            audit_event = "ops_rbac_roles_write_upsert_rate_limited",
            decision = "rate_limited_ip",
            "upsert ops role assignment blocked by ip rate limiter"
        );
        insert_ops_rbac_audit_log_best_effort(
            &state,
            OpsRbacAuditLogInput {
                event_type: OPS_RBAC_AUDIT_EVENT_ROLE_UPSERT,
                operator_user_id: user.id,
                target_user_id,
                decision: "rate_limited_ip",
                request_id: request_id.as_deref(),
                result_count: None,
                role: Some(requested_role.as_str()),
                removed: None,
                error_code: None,
                failure_reason: None,
            },
        )
        .await;
        return Ok(rate_limit_exceeded_response(
            "ops_rbac_roles_write",
            build_rate_limit_headers(&ip_decision)?,
        ));
    }

    let request_idempotency_key = request_idempotency_key_from_headers(
        &headers,
        "ops_rbac_roles_write_idempotency_key_invalid",
        "ops_rbac_roles_write_idempotency_key_too_long",
        OPS_RBAC_ROLES_WRITE_IDEMPOTENCY_MAX_LEN,
    )?;
    let idempotency_lock_key = request_idempotency_key
        .as_deref()
        .map(|key| format!("u{}:t{user_id}:{key}", user.id));
    if let Some(lock_key) = idempotency_lock_key.as_deref() {
        let acquired = try_acquire_idempotency_or_fail_open(
            &state,
            OPS_RBAC_ROLES_WRITE_IDEMPOTENCY_SCOPE,
            lock_key,
            OPS_RBAC_ROLES_WRITE_IDEMPOTENCY_TTL_SECS,
        )
        .await;
        if !acquired {
            return Err(AppError::DebateConflict(
                "idempotency_conflict:ops_rbac_roles_write".to_string(),
            ));
        }
    }

    let ret = state
        .upsert_ops_role_assignment_by_owner_with_meta(
            &user,
            user_id,
            input,
            OpsRbacUpsertMeta {
                expected_rbac_revision: expected_rbac_revision.as_deref(),
                idempotency_key: request_idempotency_key.as_deref(),
                idempotency_ttl_secs: OPS_RBAC_ROLES_WRITE_IDEMPOTENCY_TTL_SECS,
                success_request_id: request_id.as_deref(),
                require_if_match: true,
            },
        )
        .await;
    if let Some(lock_key) = idempotency_lock_key.as_deref() {
        release_idempotency_best_effort(&state, OPS_RBAC_ROLES_WRITE_IDEMPOTENCY_SCOPE, lock_key)
            .await;
    }
    let (ret, replayed) = match ret {
        Ok(v) => v,
        Err(err) => {
            let latency_ms = started_at.elapsed().as_millis() as u64;
            OPS_RBAC_ROLES_WRITE_METRICS.observe_failure(latency_ms);
            let (audit_error_code, audit_failure_reason) = classify_ops_rbac_failure(&err);
            if audit_error_code.as_deref() == Some(OPS_RBAC_IF_MATCH_REQUIRED_CODE) {
                OPS_RBAC_ROLES_WRITE_METRICS.observe_if_match_missing();
            }
            tracing::warn!(
                user_id = user.id,
                target_user_id = user_id,
                request_id = request_id.as_deref().unwrap_or_default(),
                audit_event = "ops_rbac_roles_write_upsert_failed",
                decision = "failed",
                latency_ms,
                "upsert ops role assignment failed: {}",
                err
            );
            insert_ops_rbac_audit_log_best_effort(
                &state,
                OpsRbacAuditLogInput {
                    event_type: OPS_RBAC_AUDIT_EVENT_ROLE_UPSERT,
                    operator_user_id: user.id,
                    target_user_id,
                    decision: "failed",
                    request_id: request_id.as_deref(),
                    result_count: None,
                    role: Some(requested_role.as_str()),
                    removed: None,
                    error_code: audit_error_code.as_deref(),
                    failure_reason: Some(audit_failure_reason),
                },
            )
            .await;
            return Err(err);
        }
    };
    let latency_ms = started_at.elapsed().as_millis() as u64;
    OPS_RBAC_ROLES_WRITE_METRICS.observe_success(latency_ms);
    let (
        request_total,
        success_total,
        failed_total,
        extractor_rejected_total,
        rate_limited_total,
        upsert_total,
        revoke_total,
    ) = OPS_RBAC_ROLES_WRITE_METRICS.snapshot();
    tracing::info!(
        user_id = user.id,
        target_user_id = user_id,
        request_id = request_id.as_deref().unwrap_or_default(),
        audit_event = "ops_rbac_roles_write_upsert",
        decision = "success",
        role = ret.role.as_str(),
        replayed,
        latency_ms,
        ops_rbac_roles_write_request_total = request_total,
        ops_rbac_roles_write_success_total = success_total,
        ops_rbac_roles_write_failed_total = failed_total,
        ops_rbac_roles_write_extractor_rejected_total = extractor_rejected_total,
        ops_rbac_roles_write_rate_limited_total = rate_limited_total,
        ops_rbac_roles_write_upsert_total = upsert_total,
        ops_rbac_roles_write_revoke_total = revoke_total,
        "upsert ops role assignment served"
    );
    if !replayed {
        if let Err(err) =
            dispatch_ops_rbac_audit_outbox_once(&state, OPS_RBAC_AUDIT_OUTBOX_BATCH_SIZE).await
        {
            tracing::warn!(
                audit_event = "ops_rbac_roles_write_upsert_audit_dispatch_failed",
                operator_user_id = user.id,
                target_user_id = user_id,
                request_id = request_id.as_deref().unwrap_or_default(),
                role = ret.role.as_str(),
                "dispatch ops rbac audit outbox after upsert success failed: {}",
                err
            );
        }
    }
    let mut response_headers = user_rate_headers;
    let rbac_revision = state.get_ops_rbac_revision().await?;
    if let Ok(revision_value) = HeaderValue::from_str(&rbac_revision) {
        response_headers.insert(
            HeaderName::from_static(OPS_RBAC_REVISION_HEADER),
            revision_value,
        );
    }
    if should_emit_ops_rbac_owner_self_role_warning(&state, user.id, user_id).await {
        if let Ok(warning_value) =
            HeaderValue::from_str(OPS_RBAC_WARNING_OWNER_SELF_ROLE_ASSIGNMENT_NO_EFFECT)
        {
            response_headers.insert(
                HeaderName::from_static(OPS_RBAC_WARNING_HEADER),
                warning_value,
            );
        }
    }
    Ok((StatusCode::OK, response_headers, Json(ret)).into_response())
}

/// Revoke an ops role assignment (owner only).
#[utoipa::path(
    delete,
    path = "/api/debate/ops/rbac/roles/{userId}",
    params(
        ("userId" = u64, Path, description = "Target user id"),
        ("If-Match" = String, Header, description = "Required expected RBAC revision. Supports plain revision string or quoted string.")
    ),
    responses(
        (status = 200, description = "Revoke result", body = crate::RevokeOpsRoleOutput),
        (status = 400, description = "Invalid input", body = crate::ErrorOutput),
        (status = 401, description = "Auth error", body = crate::ErrorOutput),
        (status = 403, description = "Phone not bound", body = crate::ErrorOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
        (status = 429, description = "Rate limited", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn revoke_ops_role_assignment_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(user_id): Path<u64>,
    headers: HeaderMap,
) -> Result<Response, AppError> {
    let started_at = Instant::now();
    let request_id = request_id_from_headers(&headers);
    let target_user_id = i64::try_from(user_id).ok();
    OPS_RBAC_ROLES_WRITE_METRICS.observe_start_revoke();
    let expected_rbac_revision = match parse_ops_rbac_if_match_header(&headers) {
        Ok(value) => value,
        Err(error_code) => {
            let latency_ms = started_at.elapsed().as_millis() as u64;
            OPS_RBAC_ROLES_WRITE_METRICS.observe_failure(latency_ms);
            OPS_RBAC_ROLES_WRITE_METRICS.observe_if_match_invalid();
            let (
                request_total,
                success_total,
                failed_total,
                extractor_rejected_total,
                rate_limited_total,
                upsert_total,
                revoke_total,
            ) = OPS_RBAC_ROLES_WRITE_METRICS.snapshot();
            let (
                if_match_invalid_total,
                if_match_missing_total,
                revoke_removed_total,
                revoke_noop_total,
            ) = OPS_RBAC_ROLES_WRITE_METRICS.snapshot_revoke_signals();
            tracing::warn!(
                user_id = user.id,
                target_user_id = user_id,
                request_id = request_id.as_deref().unwrap_or_default(),
                audit_event = "ops_rbac_roles_write_revoke_if_match_invalid",
                decision = "failed",
                status = StatusCode::BAD_REQUEST.as_u16(),
                error_code,
                latency_ms,
                ops_rbac_roles_write_request_total = request_total,
                ops_rbac_roles_write_success_total = success_total,
                ops_rbac_roles_write_failed_total = failed_total,
                ops_rbac_roles_write_extractor_rejected_total = extractor_rejected_total,
                ops_rbac_roles_write_rate_limited_total = rate_limited_total,
                ops_rbac_roles_write_upsert_total = upsert_total,
                ops_rbac_roles_write_revoke_total = revoke_total,
                ops_rbac_roles_write_if_match_invalid_total = if_match_invalid_total,
                ops_rbac_roles_write_if_match_missing_total = if_match_missing_total,
                ops_rbac_roles_write_revoke_removed_total = revoke_removed_total,
                ops_rbac_roles_write_revoke_noop_total = revoke_noop_total,
                "revoke ops role assignment rejected because if-match is invalid"
            );
            insert_ops_rbac_audit_log_best_effort(
                &state,
                OpsRbacAuditLogInput {
                    event_type: OPS_RBAC_AUDIT_EVENT_ROLE_REVOKE,
                    operator_user_id: user.id,
                    target_user_id,
                    decision: "failed",
                    request_id: request_id.as_deref(),
                    result_count: None,
                    role: None,
                    removed: None,
                    error_code: Some(error_code),
                    failure_reason: Some(OPS_RBAC_AUDIT_FAILURE_VALIDATION_ERROR),
                },
            )
            .await;
            return Ok((
                StatusCode::BAD_REQUEST,
                Json(crate::ErrorOutput::new(error_code)),
            )
                .into_response());
        }
    };

    let user_decision = enforce_rate_limit_with_disabled_fallback(
        &state,
        "ops_rbac_roles_write_user",
        &user.id.to_string(),
        OPS_RBAC_ROLES_WRITE_USER_RATE_LIMIT_PER_WINDOW,
        OPS_RBAC_ROLES_WRITE_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let user_decision =
        maybe_override_rate_limit_decision(&headers, "ops_rbac_roles_write_user", user_decision);
    let user_rate_headers = build_rate_limit_headers(&user_decision)?;
    if !user_decision.allowed {
        OPS_RBAC_ROLES_WRITE_METRICS.observe_rate_limited();
        tracing::warn!(
            user_id = user.id,
            target_user_id = user_id,
            request_id = request_id.as_deref().unwrap_or_default(),
            audit_event = "ops_rbac_roles_write_revoke_rate_limited",
            decision = "rate_limited_user",
            "revoke ops role assignment blocked by user rate limiter"
        );
        insert_ops_rbac_audit_log_best_effort(
            &state,
            OpsRbacAuditLogInput {
                event_type: OPS_RBAC_AUDIT_EVENT_ROLE_REVOKE,
                operator_user_id: user.id,
                target_user_id,
                decision: "rate_limited_user",
                request_id: request_id.as_deref(),
                result_count: None,
                role: None,
                removed: None,
                error_code: None,
                failure_reason: None,
            },
        )
        .await;
        return Ok(rate_limit_exceeded_response(
            "ops_rbac_roles_write",
            user_rate_headers,
        ));
    }

    let ip_limit_key = request_rate_limit_ip_key_with_user_fallback(
        &headers,
        user.id,
        &state.config.server.forwarded_header_trust,
    );
    let ip_decision = enforce_rate_limit_with_disabled_fallback(
        &state,
        "ops_rbac_roles_write_ip",
        &ip_limit_key,
        OPS_RBAC_ROLES_WRITE_IP_RATE_LIMIT_PER_WINDOW,
        OPS_RBAC_ROLES_WRITE_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let ip_decision =
        maybe_override_rate_limit_decision(&headers, "ops_rbac_roles_write_ip", ip_decision);
    if !ip_decision.allowed {
        OPS_RBAC_ROLES_WRITE_METRICS.observe_rate_limited();
        tracing::warn!(
            user_id = user.id,
            target_user_id = user_id,
            request_id = request_id.as_deref().unwrap_or_default(),
            audit_event = "ops_rbac_roles_write_revoke_rate_limited",
            decision = "rate_limited_ip",
            "revoke ops role assignment blocked by ip rate limiter"
        );
        insert_ops_rbac_audit_log_best_effort(
            &state,
            OpsRbacAuditLogInput {
                event_type: OPS_RBAC_AUDIT_EVENT_ROLE_REVOKE,
                operator_user_id: user.id,
                target_user_id,
                decision: "rate_limited_ip",
                request_id: request_id.as_deref(),
                result_count: None,
                role: None,
                removed: None,
                error_code: None,
                failure_reason: None,
            },
        )
        .await;
        return Ok(rate_limit_exceeded_response(
            "ops_rbac_roles_write",
            build_rate_limit_headers(&ip_decision)?,
        ));
    }

    let ret = match state
        .revoke_ops_role_assignment_by_owner_with_meta(
            &user,
            user_id,
            OpsRbacRevokeMeta {
                expected_rbac_revision: expected_rbac_revision.as_deref(),
                success_request_id: request_id.as_deref(),
                require_if_match: true,
            },
        )
        .await
    {
        Ok(v) => v,
        Err(err) => {
            let latency_ms = started_at.elapsed().as_millis() as u64;
            OPS_RBAC_ROLES_WRITE_METRICS.observe_failure(latency_ms);
            let (audit_error_code, audit_failure_reason) = classify_ops_rbac_failure(&err);
            if audit_error_code.as_deref() == Some(OPS_RBAC_IF_MATCH_REQUIRED_CODE) {
                OPS_RBAC_ROLES_WRITE_METRICS.observe_if_match_missing();
            }
            let (
                if_match_invalid_total,
                if_match_missing_total,
                revoke_removed_total,
                revoke_noop_total,
            ) = OPS_RBAC_ROLES_WRITE_METRICS.snapshot_revoke_signals();
            tracing::warn!(
                user_id = user.id,
                target_user_id = user_id,
                request_id = request_id.as_deref().unwrap_or_default(),
                audit_event = "ops_rbac_roles_write_revoke_failed",
                decision = "failed",
                latency_ms,
                ops_rbac_roles_write_if_match_invalid_total = if_match_invalid_total,
                ops_rbac_roles_write_if_match_missing_total = if_match_missing_total,
                ops_rbac_roles_write_revoke_removed_total = revoke_removed_total,
                ops_rbac_roles_write_revoke_noop_total = revoke_noop_total,
                "revoke ops role assignment failed: {}",
                err
            );
            insert_ops_rbac_audit_log_best_effort(
                &state,
                OpsRbacAuditLogInput {
                    event_type: OPS_RBAC_AUDIT_EVENT_ROLE_REVOKE,
                    operator_user_id: user.id,
                    target_user_id,
                    decision: "failed",
                    request_id: request_id.as_deref(),
                    result_count: None,
                    role: None,
                    removed: None,
                    error_code: audit_error_code.as_deref(),
                    failure_reason: Some(audit_failure_reason),
                },
            )
            .await;
            return Err(err);
        }
    };
    let latency_ms = started_at.elapsed().as_millis() as u64;
    OPS_RBAC_ROLES_WRITE_METRICS.observe_success(latency_ms);
    OPS_RBAC_ROLES_WRITE_METRICS.observe_revoke_outcome(ret.removed);
    let (
        request_total,
        success_total,
        failed_total,
        extractor_rejected_total,
        rate_limited_total,
        upsert_total,
        revoke_total,
    ) = OPS_RBAC_ROLES_WRITE_METRICS.snapshot();
    let (if_match_invalid_total, if_match_missing_total, revoke_removed_total, revoke_noop_total) =
        OPS_RBAC_ROLES_WRITE_METRICS.snapshot_revoke_signals();
    tracing::info!(
        user_id = user.id,
        target_user_id = user_id,
        request_id = request_id.as_deref().unwrap_or_default(),
        audit_event = "ops_rbac_roles_write_revoke",
        decision = "success",
        removed = ret.removed,
        latency_ms,
        ops_rbac_roles_write_request_total = request_total,
        ops_rbac_roles_write_success_total = success_total,
        ops_rbac_roles_write_failed_total = failed_total,
        ops_rbac_roles_write_extractor_rejected_total = extractor_rejected_total,
        ops_rbac_roles_write_rate_limited_total = rate_limited_total,
        ops_rbac_roles_write_upsert_total = upsert_total,
        ops_rbac_roles_write_revoke_total = revoke_total,
        ops_rbac_roles_write_if_match_invalid_total = if_match_invalid_total,
        ops_rbac_roles_write_if_match_missing_total = if_match_missing_total,
        ops_rbac_roles_write_revoke_removed_total = revoke_removed_total,
        ops_rbac_roles_write_revoke_noop_total = revoke_noop_total,
        "revoke ops role assignment served"
    );
    if let Err(err) =
        dispatch_ops_rbac_audit_outbox_once(&state, OPS_RBAC_AUDIT_OUTBOX_BATCH_SIZE).await
    {
        tracing::warn!(
            audit_event = "ops_rbac_roles_write_revoke_audit_dispatch_failed",
            operator_user_id = user.id,
            target_user_id = user_id,
            request_id = request_id.as_deref().unwrap_or_default(),
            removed = ret.removed,
            "dispatch ops rbac audit outbox after revoke success failed: {}",
            err
        );
    }
    let mut response_headers = user_rate_headers;
    let rbac_revision = state.get_ops_rbac_revision().await?;
    if let Ok(revision_value) = HeaderValue::from_str(&rbac_revision) {
        response_headers.insert(
            HeaderName::from_static(OPS_RBAC_REVISION_HEADER),
            revision_value,
        );
    }
    if should_emit_ops_rbac_owner_self_role_warning(&state, user.id, user_id).await {
        if let Ok(warning_value) =
            HeaderValue::from_str(OPS_RBAC_WARNING_OWNER_SELF_ROLE_ASSIGNMENT_NO_EFFECT)
        {
            response_headers.insert(
                HeaderName::from_static(OPS_RBAC_WARNING_HEADER),
                warning_value,
            );
        }
    }
    Ok((StatusCode::OK, response_headers, Json(ret)).into_response())
}

/// List judge reports for ops review with evidence/anomaly filters.
#[utoipa::path(
    get,
    path = "/api/debate/ops/judge-reviews",
    params(
        ListJudgeReviewOpsQuery
    ),
    responses(
        (status = 200, description = "Ops judge review list", body = crate::ListJudgeReviewOpsOutput),
        (status = 400, description = "Invalid query", body = crate::ErrorOutput),
        (status = 401, description = "Auth error", body = crate::ErrorOutput),
        (status = 403, description = "Phone not bound", body = crate::ErrorOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_judge_reviews_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(input): Query<ListJudgeReviewOpsQuery>,
) -> Result<impl IntoResponse, AppError> {
    let started_at = Instant::now();
    let request_id = request_id_from_headers(&headers);
    let anomaly_only = input.anomaly_only;
    let ret = match state.list_judge_reviews_by_owner(&user, input).await {
        Ok(value) => value,
        Err(err) => {
            let latency_ms = started_at.elapsed().as_millis() as u64;
            tracing::warn!(
                user_id = user.id,
                request_id = request_id.as_deref().unwrap_or_default(),
                anomaly_only,
                latency_ms,
                decision = "failed",
                "list ops judge reviews failed: {}",
                err
            );
            return Err(err);
        }
    };
    let anomaly_hit_count = ret
        .items
        .iter()
        .filter(|item| !item.abnormal_flags.is_empty())
        .count();
    let latency_ms = started_at.elapsed().as_millis() as u64;
    tracing::info!(
        user_id = user.id,
        request_id = request_id.as_deref().unwrap_or_default(),
        anomaly_only,
        scanned_count = ret.scanned_count,
        returned_count = ret.returned_count,
        anomaly_hit_count,
        latency_ms,
        decision = "success",
        "list ops judge reviews served"
    );
    Ok((StatusCode::OK, Json(ret)))
}

/// Aggregate final dispatch failure types by ops time window.
#[utoipa::path(
    get,
    path = "/api/debate/ops/judge-final-dispatch/failure-stats",
    params(
        GetJudgeFinalDispatchFailureStatsQuery
    ),
    responses(
        (status = 200, description = "Ops final dispatch failure type stats", body = crate::GetJudgeFinalDispatchFailureStatsOutput),
        (status = 400, description = "Invalid query", body = crate::ErrorOutput),
        (status = 401, description = "Auth error", body = crate::ErrorOutput),
        (status = 403, description = "Phone not bound", body = crate::ErrorOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_judge_final_dispatch_failure_stats_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(input): Query<GetJudgeFinalDispatchFailureStatsQuery>,
) -> Result<impl IntoResponse, AppError> {
    let started_at = Instant::now();
    let request_id = request_id_from_headers(&headers);
    let window_from = input.from;
    let window_to = input.to;
    let scan_limit = input.limit.unwrap_or(500).clamp(1, 5000);
    let ret = match state
        .get_judge_final_dispatch_failure_stats_by_owner(&user, input)
        .await
    {
        Ok(value) => value,
        Err(err) => {
            let latency_ms = started_at.elapsed().as_millis() as u64;
            tracing::warn!(
                user_id = user.id,
                request_id = request_id.as_deref().unwrap_or_default(),
                window_from = ?window_from,
                window_to = ?window_to,
                scan_limit,
                latency_ms,
                decision = "failed",
                "list ops final dispatch failure stats failed: {}",
                err
            );
            return Err(err);
        }
    };
    let latency_ms = started_at.elapsed().as_millis() as u64;
    let total_failed_jobs = ret.total_failed_jobs;
    let scanned_failed_jobs = ret.scanned_failed_jobs;
    let unknown_failed_jobs = ret.unknown_failed_jobs;
    let truncated = ret.truncated;
    let unknown_rate = if scanned_failed_jobs == 0 {
        0.0
    } else {
        unknown_failed_jobs as f64 / scanned_failed_jobs as f64
    };
    let truncated_rate = total_failed_jobs.saturating_sub(scanned_failed_jobs) as f64
        / total_failed_jobs.max(1) as f64;
    let scan_coverage = scanned_failed_jobs as f64 / total_failed_jobs.max(1) as f64;
    tracing::info!(
        user_id = user.id,
        request_id = request_id.as_deref().unwrap_or_default(),
        window_from = ?window_from,
        window_to = ?window_to,
        scan_limit,
        total_failed_jobs,
        scanned_failed_jobs,
        unknown_failed_jobs,
        truncated,
        unknown_rate,
        truncated_rate,
        scan_coverage,
        latency_ms,
        decision = "success",
        "list ops final dispatch failure stats served"
    );
    Ok((StatusCode::OK, Json(ret)))
}

/// Aggregate judge trace/replay records for ops diagnostics.
#[utoipa::path(
    get,
    path = "/api/debate/ops/judge-trace-replay",
    params(
        ListJudgeTraceReplayOpsQuery
    ),
    responses(
        (status = 200, description = "Ops judge trace/replay aggregation", body = crate::ListJudgeTraceReplayOpsOutput),
        (status = 400, description = "Invalid query", body = crate::ErrorOutput),
        (status = 401, description = "Auth error", body = crate::ErrorOutput),
        (status = 403, description = "Phone not bound", body = crate::ErrorOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_judge_trace_replay_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(input): Query<ListJudgeTraceReplayOpsQuery>,
) -> Result<impl IntoResponse, AppError> {
    let started_at = Instant::now();
    let request_id = request_id_from_headers(&headers);
    let window_from = input.from;
    let window_to = input.to;
    let query_limit = input.limit.unwrap_or(100).clamp(1, 500);
    let ret = match state.list_judge_trace_replay_by_owner(&user, input).await {
        Ok(value) => value,
        Err(err) => {
            let latency_ms = started_at.elapsed().as_millis() as u64;
            tracing::warn!(
                user_id = user.id,
                request_id = request_id.as_deref().unwrap_or_default(),
                window_from = ?window_from,
                window_to = ?window_to,
                query_limit,
                latency_ms,
                decision = "failed",
                "list ops judge trace replay failed: {}",
                err
            );
            return Err(err);
        }
    };
    let latency_ms = started_at.elapsed().as_millis() as u64;
    tracing::info!(
        user_id = user.id,
        request_id = request_id.as_deref().unwrap_or_default(),
        window_from = ?window_from,
        window_to = ?window_to,
        query_limit,
        scanned_count = ret.scanned_count,
        returned_count = ret.returned_count,
        phase_count = ret.phase_count,
        final_count = ret.final_count,
        failed_count = ret.failed_count,
        replay_eligible_count = ret.replay_eligible_count,
        latency_ms,
        decision = "success",
        "list ops judge trace replay served"
    );
    Ok((StatusCode::OK, Json(ret)))
}

/// Preview replay dispatch payload by scope/job id (no side effects).
#[utoipa::path(
    get,
    path = "/api/debate/ops/judge-replay/preview",
    params(
        GetJudgeReplayPreviewOpsQuery
    ),
    responses(
        (status = 200, description = "Ops replay preview snapshot", body = crate::GetJudgeReplayPreviewOpsOutput),
        (status = 400, description = "Invalid query", body = crate::ErrorOutput),
        (status = 401, description = "Auth error", body = crate::ErrorOutput),
        (status = 403, description = "Phone not bound", body = crate::ErrorOutput),
        (status = 404, description = "Replay target not found", body = crate::ErrorOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_judge_replay_preview_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(input): Query<GetJudgeReplayPreviewOpsQuery>,
) -> Result<impl IntoResponse, AppError> {
    let started_at = Instant::now();
    let request_id = request_id_from_headers(&headers);
    let query_scope = input.scope.clone();
    let query_job_id = input.job_id;
    let ret = match state.get_judge_replay_preview_by_owner(&user, input).await {
        Ok(value) => value,
        Err(err) => {
            let latency_ms = started_at.elapsed().as_millis() as u64;
            tracing::warn!(
                user_id = user.id,
                request_id = request_id.as_deref().unwrap_or_default(),
                scope = query_scope.as_str(),
                job_id = query_job_id,
                latency_ms,
                decision = "failed",
                "get ops judge replay preview failed: {}",
                err
            );
            return Err(err);
        }
    };
    let snapshot_bytes = serde_json::to_vec(&ret.request_snapshot)
        .map(|payload| payload.len() as u64)
        .unwrap_or_default();
    let latency_ms = started_at.elapsed().as_millis() as u64;
    tracing::info!(
        user_id = user.id,
        request_id = request_id.as_deref().unwrap_or_default(),
        scope = ret.meta.scope.as_str(),
        job_id = ret.meta.job_id,
        status = ret.meta.status.as_str(),
        replay_eligible = ret.meta.replay_eligible,
        message_count = ret.meta.message_count.unwrap_or_default(),
        snapshot_hash = ret.snapshot_hash.as_str(),
        snapshot_bytes,
        latency_ms,
        decision = "success",
        "get ops judge replay preview served"
    );
    Ok((StatusCode::OK, Json(ret)))
}

/// Execute replay for a failed phase/final dispatch job.
#[utoipa::path(
    post,
    path = "/api/debate/ops/judge-replay/execute",
    request_body = ExecuteJudgeReplayOpsInput,
    responses(
        (status = 200, description = "Replay execute accepted", body = crate::ExecuteJudgeReplayOpsOutput),
        (status = 404, description = "Replay target not found", body = crate::ErrorOutput),
        (status = 409, description = "Permission or state conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn execute_judge_replay_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Json(input): Json<ExecuteJudgeReplayOpsInput>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.execute_judge_replay_by_owner(&user, input).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// List replay execute audit actions for ops diagnostics.
#[utoipa::path(
    get,
    path = "/api/debate/ops/judge-replay/actions",
    params(
        ListJudgeReplayActionsOpsQuery
    ),
    responses(
        (status = 200, description = "Replay execute audit actions", body = crate::ListJudgeReplayActionsOpsOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_judge_replay_actions_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Query(input): Query<ListJudgeReplayActionsOpsQuery>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state
        .list_judge_replay_actions_by_owner(&user, input)
        .await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Trigger an ops rejudge job for a finished session.
#[utoipa::path(
    post,
    path = "/api/debate/ops/sessions/{id}/judge/rejudge",
    params(
        ("id" = u64, Path, description = "Debate session id")
    ),
    responses(
        (status = 202, description = "Rejudge job accepted", body = crate::RequestJudgeJobOutput),
        (status = 404, description = "Debate session not found", body = crate::ErrorOutput),
        (status = 409, description = "Permission or state conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn request_judge_rejudge_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.request_judge_rejudge_by_owner(id, &user).await?;
    Ok((StatusCode::ACCEPTED, Json(ret)))
}

fn classify_ops_rbac_failure(err: &AppError) -> (Option<String>, &'static str) {
    match err {
        AppError::DebateConflict(code)
            if code == OPS_RBAC_PERMISSION_DENIED_ROLE_MANAGE_CODE
                || code.starts_with(&format!("{OPS_RBAC_PERMISSION_DENIED_ROLE_MANAGE_CODE}:")) =>
        {
            (
                Some(truncate_ops_rbac_audit_error_code(code)),
                OPS_RBAC_AUDIT_FAILURE_PERMISSION_DENIED,
            )
        }
        AppError::DebateConflict(code) => (
            Some(truncate_ops_rbac_audit_error_code(code)),
            OPS_RBAC_AUDIT_FAILURE_CONFLICT,
        ),
        AppError::DebateError(code) | AppError::ValidationError(code) => (
            Some(truncate_ops_rbac_audit_error_code(code)),
            OPS_RBAC_AUDIT_FAILURE_VALIDATION_ERROR,
        ),
        AppError::NotFound(code) => (
            Some(truncate_ops_rbac_audit_error_code(code)),
            OPS_RBAC_AUDIT_FAILURE_NOT_FOUND,
        ),
        AppError::AuthError(code) => (
            Some(truncate_ops_rbac_audit_error_code(code)),
            OPS_RBAC_AUDIT_FAILURE_AUTH_ERROR,
        ),
        AppError::NotLoggedIn => (
            Some("auth_not_logged_in".to_string()),
            OPS_RBAC_AUDIT_FAILURE_AUTH_ERROR,
        ),
        AppError::ThrottleError(code) => (
            Some(truncate_ops_rbac_audit_error_code(code)),
            OPS_RBAC_AUDIT_FAILURE_RATE_LIMITED,
        ),
        AppError::ServerError(code) => (
            Some(truncate_ops_rbac_audit_error_code(code)),
            OPS_RBAC_AUDIT_FAILURE_SERVER_ERROR,
        ),
        _ => (None, OPS_RBAC_AUDIT_FAILURE_SYSTEM_ERROR),
    }
}

fn classify_ops_rbac_upsert_body_rejection(
    rejection: &JsonRejection,
) -> (StatusCode, &'static str, &'static str) {
    match rejection {
        JsonRejection::MissingJsonContentType(_) => (
            StatusCode::UNSUPPORTED_MEDIA_TYPE,
            OPS_RBAC_ROLES_WRITE_CONTENT_TYPE_INVALID_CODE,
            OPS_RBAC_AUDIT_FAILURE_VALIDATION_ERROR,
        ),
        JsonRejection::JsonSyntaxError(_) => (
            StatusCode::UNPROCESSABLE_ENTITY,
            OPS_RBAC_ROLES_WRITE_BODY_INVALID_JSON_CODE,
            OPS_RBAC_AUDIT_FAILURE_VALIDATION_ERROR,
        ),
        JsonRejection::JsonDataError(_) => (
            StatusCode::UNPROCESSABLE_ENTITY,
            OPS_RBAC_ROLES_WRITE_BODY_DATA_INVALID_CODE,
            OPS_RBAC_AUDIT_FAILURE_VALIDATION_ERROR,
        ),
        JsonRejection::BytesRejection(_) => (
            StatusCode::BAD_REQUEST,
            OPS_RBAC_ROLES_WRITE_BODY_READ_FAILED_CODE,
            OPS_RBAC_AUDIT_FAILURE_VALIDATION_ERROR,
        ),
        _ => (
            StatusCode::BAD_REQUEST,
            OPS_RBAC_ROLES_WRITE_BODY_REJECTED_CODE,
            OPS_RBAC_AUDIT_FAILURE_VALIDATION_ERROR,
        ),
    }
}

fn truncate_ops_rbac_audit_error_code(input: &str) -> String {
    input.chars().take(128).collect()
}

async fn insert_ops_rbac_audit_log(
    state: &AppState,
    input: OpsRbacAuditLogInput<'_>,
) -> Result<(), AppError> {
    sqlx::query(
        r#"
        INSERT INTO ops_rbac_audits(
            event_type,
            operator_user_id,
            target_user_id,
            decision,
            request_id,
            result_count,
            role,
            removed,
            error_code,
            failure_reason,
            created_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())
        "#,
    )
    .bind(input.event_type)
    .bind(input.operator_user_id)
    .bind(input.target_user_id)
    .bind(input.decision)
    .bind(input.request_id)
    .bind(input.result_count)
    .bind(input.role)
    .bind(input.removed)
    .bind(input.error_code)
    .bind(input.failure_reason)
    .execute(&state.pool)
    .await?;
    Ok(())
}

fn sanitize_ops_rbac_audit_outbox_error(raw: &str) -> String {
    if raw.len() <= OPS_RBAC_AUDIT_OUTBOX_ERROR_MAX_LEN {
        return raw.to_string();
    }
    raw.chars()
        .take(OPS_RBAC_AUDIT_OUTBOX_ERROR_MAX_LEN)
        .collect()
}

fn ops_rbac_audit_outbox_retry_backoff_ms(attempts: i32) -> u64 {
    let exp = attempts.max(1) as u32;
    let factor = 2_u64.saturating_pow(exp.saturating_sub(1));
    OPS_RBAC_AUDIT_OUTBOX_RETRY_BASE_BACKOFF_MS
        .saturating_mul(factor)
        .min(OPS_RBAC_AUDIT_OUTBOX_RETRY_MAX_BACKOFF_MS)
}

async fn enqueue_ops_rbac_audit_outbox_job(
    state: &AppState,
    input: OpsRbacAuditLogInput<'_>,
) -> Result<i64, AppError> {
    let outbox_id: i64 = sqlx::query_scalar(
        r#"
        INSERT INTO ops_rbac_audit_outbox_jobs(
            event_type,
            operator_user_id,
            target_user_id,
            decision,
            request_id,
            result_count,
            role,
            removed,
            error_code,
            failure_reason,
            attempts,
            next_retry_at,
            locked_until,
            delivered_at,
            last_error,
            created_at,
            updated_at
        )
        VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
            0, NOW(), NULL, NULL, NULL, NOW(), NOW()
        )
        RETURNING id
        "#,
    )
    .bind(input.event_type)
    .bind(input.operator_user_id)
    .bind(input.target_user_id)
    .bind(input.decision)
    .bind(input.request_id)
    .bind(input.result_count)
    .bind(input.role)
    .bind(input.removed)
    .bind(input.error_code)
    .bind(input.failure_reason)
    .fetch_one(&state.pool)
    .await?;
    Ok(outbox_id)
}

async fn claim_ops_rbac_audit_outbox_jobs(
    state: &AppState,
    batch_size: i64,
) -> Result<Vec<OpsRbacAuditOutboxJob>, AppError> {
    let mut tx = state.pool.begin().await?;
    let jobs: Vec<OpsRbacAuditOutboxJob> = sqlx::query_as(
        r#"
        WITH due AS (
            SELECT id
            FROM ops_rbac_audit_outbox_jobs
            WHERE delivered_at IS NULL
              AND next_retry_at <= NOW()
              AND (locked_until IS NULL OR locked_until <= NOW())
            ORDER BY next_retry_at ASC, created_at ASC, id ASC
            LIMIT $1
            FOR UPDATE SKIP LOCKED
        )
        UPDATE ops_rbac_audit_outbox_jobs q
        SET locked_until = NOW() + ($2::bigint * INTERVAL '1 second'),
            attempts = q.attempts + 1,
            updated_at = NOW()
        FROM due
        WHERE q.id = due.id
        RETURNING
            q.id,
            q.event_type,
            q.operator_user_id,
            q.target_user_id,
            q.decision,
            q.request_id,
            q.result_count,
            q.role,
            q.removed,
            q.error_code,
            q.failure_reason,
            q.attempts
        "#,
    )
    .bind(batch_size.max(1))
    .bind(OPS_RBAC_AUDIT_OUTBOX_LOCK_SECS)
    .fetch_all(&mut *tx)
    .await?;
    tx.commit().await?;
    Ok(jobs)
}

async fn deliver_ops_rbac_audit_outbox_job(
    state: &AppState,
    job: &OpsRbacAuditOutboxJob,
) -> Result<(), AppError> {
    let mut tx = state.pool.begin().await?;
    sqlx::query(
        r#"
        INSERT INTO ops_rbac_audits(
            event_type,
            operator_user_id,
            target_user_id,
            decision,
            request_id,
            result_count,
            role,
            removed,
            error_code,
            failure_reason,
            created_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())
        "#,
    )
    .bind(&job.event_type)
    .bind(job.operator_user_id)
    .bind(job.target_user_id)
    .bind(&job.decision)
    .bind(job.request_id.as_deref())
    .bind(job.result_count)
    .bind(job.role.as_deref())
    .bind(job.removed)
    .bind(job.error_code.as_deref())
    .bind(job.failure_reason.as_deref())
    .execute(&mut *tx)
    .await?;
    sqlx::query(
        r#"
        UPDATE ops_rbac_audit_outbox_jobs
        SET delivered_at = NOW(),
            locked_until = NULL,
            last_error = NULL,
            updated_at = NOW()
        WHERE id = $1
          AND delivered_at IS NULL
        "#,
    )
    .bind(job.id)
    .execute(&mut *tx)
    .await?;
    tx.commit().await?;
    Ok(())
}

async fn reschedule_ops_rbac_audit_outbox_job(
    state: &AppState,
    job_id: i64,
    backoff_ms: u64,
    last_error: &str,
) -> Result<(), AppError> {
    let backoff_ms_i64 = i64::try_from(backoff_ms).unwrap_or(i64::MAX);
    sqlx::query(
        r#"
        UPDATE ops_rbac_audit_outbox_jobs
        SET next_retry_at = NOW() + ($2::bigint * INTERVAL '1 millisecond'),
            locked_until = NULL,
            last_error = $3,
            updated_at = NOW()
        WHERE id = $1
          AND delivered_at IS NULL
        "#,
    )
    .bind(job_id)
    .bind(backoff_ms_i64)
    .bind(last_error)
    .execute(&state.pool)
    .await?;
    Ok(())
}

async fn dispatch_ops_rbac_audit_outbox_once(
    state: &AppState,
    batch_size: i64,
) -> Result<OpsRbacAuditOutboxDispatchReport, AppError> {
    let jobs = claim_ops_rbac_audit_outbox_jobs(state, batch_size).await?;
    let mut report = OpsRbacAuditOutboxDispatchReport {
        attempted: jobs.len(),
        ..Default::default()
    };
    for job in jobs {
        if let Err(err) = deliver_ops_rbac_audit_outbox_job(state, &job).await {
            let retry_backoff_ms = ops_rbac_audit_outbox_retry_backoff_ms(job.attempts);
            let last_error = sanitize_ops_rbac_audit_outbox_error(&err.to_string());
            reschedule_ops_rbac_audit_outbox_job(state, job.id, retry_backoff_ms, &last_error)
                .await?;
            report.requeued += 1;
            tracing::warn!(
                audit_event = "ops_rbac_audit_outbox_deliver_failed",
                outbox_job_id = job.id,
                event_type = job.event_type,
                operator_user_id = job.operator_user_id,
                target_user_id = job.target_user_id.unwrap_or_default(),
                decision = job.decision,
                attempts = job.attempts,
                retry_backoff_ms,
                "deliver ops rbac audit outbox job failed: {}",
                err
            );
        } else {
            report.delivered += 1;
        }
    }
    Ok(report)
}

impl AppState {
    pub(crate) async fn retry_ops_rbac_audit_outbox_once(
        &self,
        batch_size: i64,
    ) -> Result<OpsRbacAuditOutboxDispatchReport, AppError> {
        dispatch_ops_rbac_audit_outbox_once(self, batch_size.max(1)).await
    }
}

async fn insert_ops_rbac_audit_log_best_effort(state: &AppState, input: OpsRbacAuditLogInput<'_>) {
    match enqueue_ops_rbac_audit_outbox_job(state, input).await {
        Ok(outbox_job_id) => {
            if let Err(err) =
                dispatch_ops_rbac_audit_outbox_once(state, OPS_RBAC_AUDIT_OUTBOX_BATCH_SIZE).await
            {
                tracing::warn!(
                    audit_event = "ops_rbac_audit_outbox_dispatch_failed",
                    outbox_job_id,
                    event_type = input.event_type,
                    operator_user_id = input.operator_user_id,
                    target_user_id = input.target_user_id.unwrap_or_default(),
                    decision = input.decision,
                    request_id = input.request_id.unwrap_or_default(),
                    "dispatch ops rbac audit outbox failed: {}",
                    err
                );
            }
        }
        Err(outbox_err) => {
            tracing::warn!(
                audit_event = "ops_rbac_audit_outbox_enqueue_failed",
                event_type = input.event_type,
                operator_user_id = input.operator_user_id,
                target_user_id = input.target_user_id.unwrap_or_default(),
                decision = input.decision,
                error_code = input.error_code.unwrap_or_default(),
                failure_reason = input.failure_reason.unwrap_or_default(),
                request_id = input.request_id.unwrap_or_default(),
                "enqueue ops rbac audit outbox failed: {}",
                outbox_err
            );
            if let Err(err) = insert_ops_rbac_audit_log(state, input).await {
                tracing::warn!(
                    audit_event = "ops_rbac_audit_write_failed",
                    event_type = input.event_type,
                    operator_user_id = input.operator_user_id,
                    target_user_id = input.target_user_id.unwrap_or_default(),
                    decision = input.decision,
                    error_code = input.error_code.unwrap_or_default(),
                    failure_reason = input.failure_reason.unwrap_or_default(),
                    request_id = input.request_id.unwrap_or_default(),
                    "persist ops rbac audit log failed: {}",
                    err
                );
            }
        }
    }
}

fn request_id_from_headers(headers: &HeaderMap) -> Option<String> {
    headers
        .get("x-request-id")
        .or_else(|| headers.get("x-requestid"))
        .or_else(|| headers.get("request-id"))
        .and_then(|v| v.to_str().ok())
        .map(str::trim)
        .filter(|v| !v.is_empty())
        .map(|v| v.chars().take(128).collect::<String>())
}

async fn should_emit_ops_rbac_owner_self_role_warning(
    state: &AppState,
    operator_user_id: i64,
    target_user_id: u64,
) -> bool {
    let Ok(target_user_id_i64) = i64::try_from(target_user_id) else {
        return false;
    };
    match state.get_platform_admin_user_id().await {
        Ok(owner_user_id) => {
            owner_user_id == operator_user_id && owner_user_id == target_user_id_i64
        }
        Err(err) => {
            tracing::warn!(
                audit_event = "ops_rbac_roles_write_owner_self_warning_resolve_failed",
                operator_user_id,
                target_user_id,
                "resolve owner self warning condition failed: {}",
                err
            );
            false
        }
    }
}

fn parse_ops_rbac_if_match_header(headers: &HeaderMap) -> Result<Option<String>, &'static str> {
    let Some(value) = headers.get(IF_MATCH) else {
        return Ok(None);
    };
    let raw = value
        .to_str()
        .map_err(|_| OPS_RBAC_IF_MATCH_INVALID_CODE)?
        .trim();
    if raw.is_empty() || raw == "*" || raw.contains(',') {
        return Err(OPS_RBAC_IF_MATCH_INVALID_CODE);
    }
    if raw.starts_with("W/") || raw.starts_with("w/") {
        return Err(OPS_RBAC_IF_MATCH_INVALID_CODE);
    }
    let normalized = if raw.starts_with('"') || raw.ends_with('"') {
        raw.strip_prefix('"')
            .and_then(|v| v.strip_suffix('"'))
            .map(str::trim)
            .filter(|v| !v.is_empty())
            .ok_or(OPS_RBAC_IF_MATCH_INVALID_CODE)?
    } else {
        raw
    };
    if normalized.len() > 128 || normalized.contains('"') {
        return Err(OPS_RBAC_IF_MATCH_INVALID_CODE);
    }
    Ok(Some(normalized.to_string()))
}

#[cfg(test)]
fn maybe_override_rate_limit_decision(
    headers: &HeaderMap,
    target: &str,
    mut decision: RateLimitDecision,
) -> RateLimitDecision {
    let forced = headers
        .get("x-test-force-rate-limit")
        .and_then(|value| value.to_str().ok())
        .map(str::trim)
        .unwrap_or_default();
    if forced.eq_ignore_ascii_case(target)
        || (target == "ops_rbac_roles_list_user" && forced.eq_ignore_ascii_case("user"))
        || (target == "ops_rbac_roles_list_ip" && forced.eq_ignore_ascii_case("ip"))
        || (target == "ops_debate_session_create_user" && forced.eq_ignore_ascii_case("user"))
        || (target == "ops_debate_session_create_ip" && forced.eq_ignore_ascii_case("ip"))
        || (target == "ops_debate_session_update_user" && forced.eq_ignore_ascii_case("user"))
        || (target == "ops_debate_session_update_ip" && forced.eq_ignore_ascii_case("ip"))
    {
        decision.allowed = false;
        decision.remaining = 0;
    }
    decision
}
