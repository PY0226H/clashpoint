#[cfg(test)]
use crate::RateLimitDecision;
use crate::{
    application::request_guard::{
        build_rate_limit_headers, enforce_rate_limit, rate_limit_exceeded_response,
        release_idempotency_best_effort, try_acquire_idempotency_or_fail_open,
    },
    AppError, AppState, CreateDebateMessageInput, ErrorOutput, JoinDebateSessionInput,
    ListDebateMessages, ListDebatePinnedMessages, ListDebateSessions, ListDebateSessionsOutput,
    PinDebateMessageInput,
};
use axum::{
    extract::{Path, Query, State},
    http::{HeaderMap, StatusCode},
    response::{IntoResponse, Response},
    Extension, Json,
};
use chat_core::User;
use sha1::{Digest, Sha1};
use std::{
    net::IpAddr,
    sync::{
        atomic::{AtomicU64, Ordering},
        LazyLock,
    },
    time::Instant,
};

const DEBATE_MESSAGE_RATE_LIMIT_PER_WINDOW: u64 = 120;
const DEBATE_MESSAGE_RATE_LIMIT_WINDOW_SECS: u64 = 60;
const DEBATE_SESSIONS_LIST_USER_RATE_LIMIT_PER_WINDOW: u64 = 120;
const DEBATE_SESSIONS_LIST_IP_RATE_LIMIT_PER_WINDOW: u64 = 360;
const DEBATE_SESSIONS_LIST_RATE_LIMIT_WINDOW_SECS: u64 = 60;
const DEBATE_SESSION_JOIN_USER_RATE_LIMIT_PER_WINDOW: u64 = 20;
const DEBATE_SESSION_JOIN_IP_RATE_LIMIT_PER_WINDOW: u64 = 120;
const DEBATE_SESSION_JOIN_RATE_LIMIT_WINDOW_SECS: u64 = 60;
const DEBATE_SESSION_JOIN_IDEMPOTENCY_TTL_SECS: u64 = 15;

#[derive(Default)]
struct DebateSessionsListMetrics {
    request_total: AtomicU64,
    success_total: AtomicU64,
    failed_total: AtomicU64,
    rate_limited_total: AtomicU64,
}

impl DebateSessionsListMetrics {
    fn observe_start(&self) {
        self.request_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_success(&self) {
        self.success_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_failure(&self) {
        self.failed_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_rate_limited(&self) {
        self.rate_limited_total.fetch_add(1, Ordering::Relaxed);
    }

    fn snapshot(&self) -> (u64, u64, u64, u64) {
        (
            self.request_total.load(Ordering::Relaxed),
            self.success_total.load(Ordering::Relaxed),
            self.failed_total.load(Ordering::Relaxed),
            self.rate_limited_total.load(Ordering::Relaxed),
        )
    }
}

static DEBATE_SESSIONS_LIST_METRICS: LazyLock<DebateSessionsListMetrics> =
    LazyLock::new(DebateSessionsListMetrics::default);

#[derive(Default)]
struct DebateSessionJoinMetrics {
    request_total: AtomicU64,
    success_total: AtomicU64,
    failed_total: AtomicU64,
    conflict_total: AtomicU64,
    rate_limited_total: AtomicU64,
    idempotency_conflict_total: AtomicU64,
    conflict_not_open_yet_total: AtomicU64,
    conflict_session_closed_total: AtomicU64,
    conflict_side_full_total: AtomicU64,
    conflict_side_conflict_total: AtomicU64,
    conflict_lock_timeout_total: AtomicU64,
}

impl DebateSessionJoinMetrics {
    fn observe_start(&self) {
        self.request_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_success(&self) {
        self.success_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_failure(&self) {
        self.failed_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_rate_limited(&self) {
        self.rate_limited_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_idempotency_conflict(&self) {
        self.idempotency_conflict_total
            .fetch_add(1, Ordering::Relaxed);
    }

    fn observe_conflict(&self, reason: &str) {
        self.conflict_total.fetch_add(1, Ordering::Relaxed);
        match reason {
            "debate_join_not_open_yet" => {
                self.conflict_not_open_yet_total
                    .fetch_add(1, Ordering::Relaxed);
            }
            "debate_join_session_closed" => {
                self.conflict_session_closed_total
                    .fetch_add(1, Ordering::Relaxed);
            }
            "debate_join_side_full" => {
                self.conflict_side_full_total
                    .fetch_add(1, Ordering::Relaxed);
            }
            "debate_join_side_conflict" => {
                self.conflict_side_conflict_total
                    .fetch_add(1, Ordering::Relaxed);
            }
            "debate_join_lock_timeout" => {
                self.conflict_lock_timeout_total
                    .fetch_add(1, Ordering::Relaxed);
            }
            _ => {}
        }
    }

    fn snapshot(&self) -> (u64, u64, u64, u64, u64, u64, u64, u64, u64, u64, u64) {
        (
            self.request_total.load(Ordering::Relaxed),
            self.success_total.load(Ordering::Relaxed),
            self.failed_total.load(Ordering::Relaxed),
            self.conflict_total.load(Ordering::Relaxed),
            self.rate_limited_total.load(Ordering::Relaxed),
            self.idempotency_conflict_total.load(Ordering::Relaxed),
            self.conflict_not_open_yet_total.load(Ordering::Relaxed),
            self.conflict_session_closed_total.load(Ordering::Relaxed),
            self.conflict_side_full_total.load(Ordering::Relaxed),
            self.conflict_side_conflict_total.load(Ordering::Relaxed),
            self.conflict_lock_timeout_total.load(Ordering::Relaxed),
        )
    }
}

static DEBATE_SESSION_JOIN_METRICS: LazyLock<DebateSessionJoinMetrics> =
    LazyLock::new(DebateSessionJoinMetrics::default);

/// List debate sessions in the platform scope.
#[utoipa::path(
    get,
    path = "/api/debate/sessions",
    params(
        ListDebateSessions
    ),
    responses(
        (status = 200, description = "List of debate sessions", body = crate::ListDebateSessionsOutput),
        (status = 400, description = "Invalid query", body = crate::ErrorOutput),
        (status = 401, description = "Auth error", body = crate::ErrorOutput),
        (status = 403, description = "Phone not bound", body = crate::ErrorOutput),
        (status = 429, description = "Rate limited", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_debate_sessions_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(input): Query<ListDebateSessions>,
) -> Result<Response, AppError> {
    let started_at = Instant::now();
    DEBATE_SESSIONS_LIST_METRICS.observe_start();
    let request_id = request_id_from_headers(&headers);

    let user_decision = enforce_rate_limit(
        &state,
        "debate_sessions_list_user",
        &user.id.to_string(),
        DEBATE_SESSIONS_LIST_USER_RATE_LIMIT_PER_WINDOW,
        DEBATE_SESSIONS_LIST_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let user_decision = maybe_override_rate_limit_decision(&headers, "user", user_decision);
    let response_headers = build_rate_limit_headers(&user_decision)?;
    if !user_decision.allowed {
        DEBATE_SESSIONS_LIST_METRICS.observe_rate_limited();
        tracing::warn!(
            user_id = user.id,
            request_id = request_id.as_deref().unwrap_or_default(),
            decision = "rate_limited_user",
            "list debate sessions blocked by user rate limiter"
        );
        return Ok(rate_limit_exceeded_response(
            "debate_sessions_list",
            response_headers,
        ));
    }

    let ip_limit_key =
        request_rate_limit_ip_key_from_headers(&headers).unwrap_or_else(|| "unknown".to_string());
    let ip_decision = enforce_rate_limit(
        &state,
        "debate_sessions_list_ip",
        &ip_limit_key,
        DEBATE_SESSIONS_LIST_IP_RATE_LIMIT_PER_WINDOW,
        DEBATE_SESSIONS_LIST_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let ip_decision = maybe_override_rate_limit_decision(&headers, "ip", ip_decision);
    if !ip_decision.allowed {
        DEBATE_SESSIONS_LIST_METRICS.observe_rate_limited();
        tracing::warn!(
            user_id = user.id,
            request_id = request_id.as_deref().unwrap_or_default(),
            decision = "rate_limited_ip",
            "list debate sessions blocked by ip rate limiter"
        );
        return Ok(rate_limit_exceeded_response(
            "debate_sessions_list",
            build_rate_limit_headers(&ip_decision)?,
        ));
    }

    let status_filter = input.status.clone().unwrap_or_default();
    let topic_id_filter = input.topic_id.unwrap_or_default();
    let output: ListDebateSessionsOutput = match state.list_debate_sessions(input).await {
        Ok(v) => v,
        Err(err) => {
            DEBATE_SESSIONS_LIST_METRICS.observe_failure();
            tracing::warn!(
                user_id = user.id,
                request_id = request_id.as_deref().unwrap_or_default(),
                decision = "failed",
                latency_ms = started_at.elapsed().as_millis() as u64,
                "list debate sessions failed: {}",
                err
            );
            return Err(err);
        }
    };
    DEBATE_SESSIONS_LIST_METRICS.observe_success();
    let latency_ms = started_at.elapsed().as_millis() as u64;
    let (request_total, success_total, failed_total, rate_limited_total) =
        DEBATE_SESSIONS_LIST_METRICS.snapshot();
    tracing::info!(
        user_id = user.id,
        request_id = request_id.as_deref().unwrap_or_default(),
        status = status_filter.as_str(),
        topic_id = topic_id_filter,
        has_more = output.has_more,
        result_count = output.items.len(),
        cursor_present = output.next_cursor.is_some(),
        revision = output.revision.as_str(),
        latency_ms,
        debate_sessions_list_request_total = request_total,
        debate_sessions_list_success_total = success_total,
        debate_sessions_list_failed_total = failed_total,
        debate_sessions_list_rate_limited_total = rate_limited_total,
        decision = "success",
        "list debate sessions served"
    );
    Ok((StatusCode::OK, response_headers, Json(output)).into_response())
}

/// Join a debate session with selected side.
#[utoipa::path(
    post,
    path = "/api/debate/sessions/{id}/join",
    params(
        ("id" = u64, Path, description = "Debate session id")
    ),
    request_body = JoinDebateSessionInput,
    responses(
        (status = 200, description = "Join result", body = crate::JoinDebateSessionOutput),
        (status = 400, description = "Invalid input", body = crate::ErrorOutput),
        (status = 401, description = "Auth error", body = crate::ErrorOutput),
        (status = 403, description = "Phone not bound", body = crate::ErrorOutput),
        (status = 404, description = "Debate session not found", body = crate::ErrorOutput),
        (status = 409, description = "Join conflict", body = crate::ErrorOutput),
        (status = 429, description = "Rate limited", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn join_debate_session_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(id): Path<u64>,
    Json(input): Json<JoinDebateSessionInput>,
) -> Result<Response, AppError> {
    let started_at = Instant::now();
    DEBATE_SESSION_JOIN_METRICS.observe_start();
    let request_id = request_id_from_headers(&headers);

    let user_limit_key = format!("{}:{}", user.id, id);
    let user_decision = enforce_rate_limit(
        &state,
        "debate_session_join_user",
        &user_limit_key,
        DEBATE_SESSION_JOIN_USER_RATE_LIMIT_PER_WINDOW,
        DEBATE_SESSION_JOIN_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let user_decision = maybe_override_rate_limit_decision(&headers, "join_user", user_decision);
    let user_rate_limit_headers = build_rate_limit_headers(&user_decision)?;
    if !user_decision.allowed {
        DEBATE_SESSION_JOIN_METRICS.observe_rate_limited();
        tracing::warn!(
            user_id = user.id,
            session_id = id,
            request_id = request_id.as_deref().unwrap_or_default(),
            decision = "rate_limited_user",
            "join debate session blocked by user rate limiter"
        );
        return Ok(rate_limit_exceeded_response(
            "debate_session_join",
            user_rate_limit_headers,
        ));
    }

    let ip_limit_key = request_rate_limit_ip_key_from_headers(&headers)
        .map(|v| format!("{v}:{id}"))
        .unwrap_or_else(|| format!("unknown:{id}"));
    let ip_decision = enforce_rate_limit(
        &state,
        "debate_session_join_ip",
        &ip_limit_key,
        DEBATE_SESSION_JOIN_IP_RATE_LIMIT_PER_WINDOW,
        DEBATE_SESSION_JOIN_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let ip_decision = maybe_override_rate_limit_decision(&headers, "join_ip", ip_decision);
    if !ip_decision.allowed {
        DEBATE_SESSION_JOIN_METRICS.observe_rate_limited();
        tracing::warn!(
            user_id = user.id,
            session_id = id,
            request_id = request_id.as_deref().unwrap_or_default(),
            decision = "rate_limited_ip",
            "join debate session blocked by ip rate limiter"
        );
        return Ok(rate_limit_exceeded_response(
            "debate_session_join",
            build_rate_limit_headers(&ip_decision)?,
        ));
    }

    let request_idempotency_key = request_idempotency_key_from_headers(&headers)?;
    let idempotency_lock_key = request_idempotency_key
        .as_deref()
        .map(|key| format!("u{}:s{}:{key}", user.id, id));
    if let Some(lock_key) = idempotency_lock_key.as_deref() {
        let acquired = try_acquire_idempotency_or_fail_open(
            &state,
            "debate_session_join",
            lock_key,
            DEBATE_SESSION_JOIN_IDEMPOTENCY_TTL_SECS,
        )
        .await;
        if !acquired {
            DEBATE_SESSION_JOIN_METRICS.observe_conflict("idempotency_conflict");
            DEBATE_SESSION_JOIN_METRICS.observe_idempotency_conflict();
            tracing::warn!(
                user_id = user.id,
                session_id = id,
                request_id = request_id.as_deref().unwrap_or_default(),
                decision = "idempotency_conflict",
                "join debate session rejected by idempotency key in-flight lock"
            );
            return Ok((
                StatusCode::CONFLICT,
                Json(ErrorOutput::new(
                    "idempotency_conflict:debate_session_join".to_string(),
                )),
            )
                .into_response());
        }
    }

    let result = state.join_debate_session(id, &user, input).await;
    if let Some(lock_key) = idempotency_lock_key.as_deref() {
        release_idempotency_best_effort(&state, "debate_session_join", lock_key).await;
    }

    match result {
        Ok(output) => {
            DEBATE_SESSION_JOIN_METRICS.observe_success();
            let latency_ms = started_at.elapsed().as_millis() as u64;
            let (
                request_total,
                success_total,
                failed_total,
                conflict_total,
                rate_limited_total,
                idempotency_conflict_total,
                conflict_not_open_yet_total,
                conflict_session_closed_total,
                conflict_side_full_total,
                conflict_side_conflict_total,
                conflict_lock_timeout_total,
            ) = DEBATE_SESSION_JOIN_METRICS.snapshot();
            tracing::info!(
                user_id = user.id,
                session_id = id,
                side = output.side.as_str(),
                newly_joined = output.newly_joined,
                pro_count = output.pro_count,
                con_count = output.con_count,
                request_id = request_id.as_deref().unwrap_or_default(),
                idempotency_key_present = request_idempotency_key.is_some(),
                latency_ms,
                debate_session_join_request_total = request_total,
                debate_session_join_success_total = success_total,
                debate_session_join_failed_total = failed_total,
                debate_session_join_conflict_total = conflict_total,
                debate_session_join_rate_limited_total = rate_limited_total,
                debate_session_join_idempotency_conflict_total = idempotency_conflict_total,
                debate_session_join_conflict_not_open_yet_total = conflict_not_open_yet_total,
                debate_session_join_conflict_session_closed_total = conflict_session_closed_total,
                debate_session_join_conflict_side_full_total = conflict_side_full_total,
                debate_session_join_conflict_side_conflict_total = conflict_side_conflict_total,
                debate_session_join_conflict_lock_timeout_total = conflict_lock_timeout_total,
                decision = "success",
                "join debate session served"
            );
            Ok((StatusCode::OK, Json(output)).into_response())
        }
        Err(err) => {
            let latency_ms = started_at.elapsed().as_millis() as u64;
            if let Some(reason) = join_conflict_reason(&err) {
                DEBATE_SESSION_JOIN_METRICS.observe_conflict(reason);
            } else {
                DEBATE_SESSION_JOIN_METRICS.observe_failure();
            }
            let (
                request_total,
                success_total,
                failed_total,
                conflict_total,
                rate_limited_total,
                idempotency_conflict_total,
                conflict_not_open_yet_total,
                conflict_session_closed_total,
                conflict_side_full_total,
                conflict_side_conflict_total,
                conflict_lock_timeout_total,
            ) = DEBATE_SESSION_JOIN_METRICS.snapshot();
            tracing::warn!(
                user_id = user.id,
                session_id = id,
                request_id = request_id.as_deref().unwrap_or_default(),
                idempotency_key_present = request_idempotency_key.is_some(),
                conflict_reason = join_conflict_reason(&err).unwrap_or("none"),
                latency_ms,
                debate_session_join_request_total = request_total,
                debate_session_join_success_total = success_total,
                debate_session_join_failed_total = failed_total,
                debate_session_join_conflict_total = conflict_total,
                debate_session_join_rate_limited_total = rate_limited_total,
                debate_session_join_idempotency_conflict_total = idempotency_conflict_total,
                debate_session_join_conflict_not_open_yet_total = conflict_not_open_yet_total,
                debate_session_join_conflict_session_closed_total = conflict_session_closed_total,
                debate_session_join_conflict_side_full_total = conflict_side_full_total,
                debate_session_join_conflict_side_conflict_total = conflict_side_conflict_total,
                debate_session_join_conflict_lock_timeout_total = conflict_lock_timeout_total,
                decision = "failed",
                "join debate session failed: {}",
                err
            );
            if let AppError::DebateConflict(reason) = &err {
                return Ok(
                    (StatusCode::CONFLICT, Json(ErrorOutput::new(reason.clone()))).into_response(),
                );
            }
            Err(err)
        }
    }
}

/// Send a message in a debate session.
#[utoipa::path(
    post,
    path = "/api/debate/sessions/{id}/messages",
    params(
        ("id" = u64, Path, description = "Debate session id")
    ),
    request_body = CreateDebateMessageInput,
    responses(
        (status = 201, description = "Created message", body = crate::DebateMessage),
        (status = 400, description = "Invalid input", body = crate::ErrorOutput),
        (status = 404, description = "Debate session not found", body = crate::ErrorOutput),
        (status = 409, description = "Session conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn create_debate_message_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Json(input): Json<CreateDebateMessageInput>,
) -> Result<impl IntoResponse, AppError> {
    let limiter_key = format!("ws:{}:user:{}:session:{}", 1_i64, user.id, id);
    let decision = enforce_rate_limit(
        &state,
        "debate_message_create",
        &limiter_key,
        DEBATE_MESSAGE_RATE_LIMIT_PER_WINDOW,
        DEBATE_MESSAGE_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    let headers = build_rate_limit_headers(&decision)?;
    if !decision.allowed {
        return Ok(rate_limit_exceeded_response(
            "debate_message_create",
            headers,
        ));
    }

    let msg = state.create_debate_message(id, &user, input).await?;
    Ok((StatusCode::CREATED, headers, Json(msg)).into_response())
}

/// List messages in a debate session.
#[utoipa::path(
    get,
    path = "/api/debate/sessions/{id}/messages",
    params(
        ("id" = u64, Path, description = "Debate session id"),
        ListDebateMessages
    ),
    responses(
        (status = 200, description = "Debate messages", body = Vec<crate::DebateMessage>),
        (status = 404, description = "Debate session not found", body = crate::ErrorOutput),
        (status = 409, description = "User cannot read in current session status", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_debate_messages_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Query(input): Query<ListDebateMessages>,
) -> Result<impl IntoResponse, AppError> {
    let messages = state.list_debate_messages(id, &user, input).await?;
    Ok((StatusCode::OK, Json(messages)))
}

/// Pin an existing debate message with wallet consume.
#[utoipa::path(
    post,
    path = "/api/debate/messages/{id}/pin",
    params(
        ("id" = u64, Path, description = "Debate message id")
    ),
    request_body = PinDebateMessageInput,
    responses(
        (status = 200, description = "Pin result", body = crate::PinDebateMessageOutput),
        (status = 400, description = "Invalid input", body = crate::ErrorOutput),
        (status = 404, description = "Debate message not found", body = crate::ErrorOutput),
        (status = 409, description = "Pin conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn pin_debate_message_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Json(input): Json<PinDebateMessageInput>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.pin_debate_message(id, &user, input).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// List pinned messages in a debate session.
#[utoipa::path(
    get,
    path = "/api/debate/sessions/{id}/pins",
    params(
        ("id" = u64, Path, description = "Debate session id"),
        ListDebatePinnedMessages
    ),
    responses(
        (status = 200, description = "Pinned debate messages", body = Vec<crate::DebatePinnedMessage>),
        (status = 404, description = "Debate session not found", body = crate::ErrorOutput),
        (status = 409, description = "User cannot read in current session status", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_debate_pinned_messages_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Query(input): Query<ListDebatePinnedMessages>,
) -> Result<impl IntoResponse, AppError> {
    let pins = state.list_debate_pinned_messages(id, &user, input).await?;
    Ok((StatusCode::OK, Json(pins)))
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

fn request_idempotency_key_from_headers(headers: &HeaderMap) -> Result<Option<String>, AppError> {
    let Some(raw) = headers
        .get("idempotency-key")
        .or_else(|| headers.get("x-idempotency-key"))
        .and_then(|v| v.to_str().ok())
    else {
        return Ok(None);
    };
    let key = raw.trim();
    if key.is_empty() {
        return Err(AppError::ValidationError(
            "debate_join_idempotency_key_invalid".to_string(),
        ));
    }
    if key.len() > 160 {
        return Err(AppError::ValidationError(
            "debate_join_idempotency_key_too_long".to_string(),
        ));
    }
    Ok(Some(key.to_string()))
}

fn join_conflict_reason(err: &AppError) -> Option<&str> {
    match err {
        AppError::DebateConflict(reason) => Some(reason.as_str()),
        _ => None,
    }
}

fn request_rate_limit_ip_key_from_headers(headers: &HeaderMap) -> Option<String> {
    extract_raw_ip_from_forwarded_headers(headers).map(|ip| hash_with_sha1(&ip))
}

fn extract_raw_ip_from_forwarded_headers(headers: &HeaderMap) -> Option<String> {
    if let Some(value) = headers.get("x-forwarded-for").and_then(|v| v.to_str().ok()) {
        for candidate in value.split(',').map(str::trim) {
            if candidate.parse::<IpAddr>().is_ok() {
                return Some(candidate.to_string());
            }
        }
    }
    headers
        .get("x-real-ip")
        .and_then(|v| v.to_str().ok())
        .map(str::trim)
        .filter(|v| v.parse::<IpAddr>().is_ok())
        .map(ToOwned::to_owned)
}

fn hash_with_sha1(input: &str) -> String {
    let mut hasher = Sha1::new();
    hasher.update(input.as_bytes());
    hex::encode(hasher.finalize())
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
    if forced.eq_ignore_ascii_case(target) {
        decision.allowed = false;
        decision.remaining = 0;
        return decision;
    }
    if target == "join_user" && forced.eq_ignore_ascii_case("user") {
        decision.allowed = false;
        decision.remaining = 0;
        return decision;
    }
    if target == "join_ip" && forced.eq_ignore_ascii_case("ip") {
        decision.allowed = false;
        decision.remaining = 0;
        return decision;
    }
    decision
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{get_router, models::CreateUser, ErrorOutput};
    use anyhow::Result;
    use axum::{
        body::Body,
        http::{Method, Request, StatusCode},
    };
    use http_body_util::BodyExt;
    use tower::ServiceExt;

    async fn issue_token_for_user(state: &AppState, user_id: i64, sid: &str) -> Result<String> {
        let family_id = format!("{sid}-family");
        let refresh_jti = format!("{sid}-refresh-jti");
        let access_jti = format!("{sid}-access-jti");

        sqlx::query(
            r#"
            INSERT INTO auth_refresh_sessions (
                user_id, sid, family_id, current_jti, expires_at, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, NOW() + interval '1 day', NOW(), NOW())
            ON CONFLICT (sid) DO UPDATE
            SET current_jti = EXCLUDED.current_jti,
                family_id = EXCLUDED.family_id,
                revoked_at = NULL,
                revoke_reason = NULL,
                expires_at = EXCLUDED.expires_at,
                updated_at = NOW()
            "#,
        )
        .bind(user_id)
        .bind(sid)
        .bind(&family_id)
        .bind(&refresh_jti)
        .execute(&state.pool)
        .await?;

        Ok(state
            .ek
            .sign_access_token_with_jti(user_id, sid, 0, access_jti, 900)?)
    }

    async fn create_bound_user_and_token(
        state: &AppState,
        fullname: &str,
        email: &str,
        phone: &str,
        sid: &str,
    ) -> Result<(chat_core::User, String)> {
        let user = state
            .create_user(&CreateUser {
                fullname: fullname.to_string(),
                email: email.to_string(),
                password: "123456".to_string(),
            })
            .await?;
        let _ = state.bind_phone_for_user(user.id, phone).await?;
        let token = issue_token_for_user(state, user.id, sid).await?;
        Ok((user, token))
    }

    async fn seed_session_with_window(
        state: &AppState,
        status: &str,
        scheduled_start_at: chrono::DateTime<chrono::Utc>,
        end_at: chrono::DateTime<chrono::Utc>,
    ) -> Result<i64> {
        let topic_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO debate_topics(
                title, description, category, stance_pro, stance_con, context_seed, is_active, created_by
            )
            VALUES ($1, $2, $3, $4, $5, NULL, TRUE, $6)
            RETURNING id
            "#,
        )
        .bind(format!("topic-{}", uuid::Uuid::new_v4()))
        .bind("debate topic for join route tests")
        .bind("game")
        .bind("pro stance")
        .bind("con stance")
        .bind(1_i64)
        .fetch_one(&state.pool)
        .await?;

        let session_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO debate_sessions(
                topic_id, status, scheduled_start_at, actual_start_at, end_at, max_participants_per_side
            )
            VALUES ($1, $2, $3, NULL, $4, 10)
            RETURNING id
            "#,
        )
        .bind(topic_id.0)
        .bind(status)
        .bind(scheduled_start_at)
        .bind(end_at)
        .fetch_one(&state.pool)
        .await?;
        Ok(session_id.0)
    }

    #[tokio::test]
    async fn debate_sessions_route_should_reject_invalid_status() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "Debate Sessions User",
            "debate-sessions-status@acme.org",
            "+8613800994444",
            "debate-sessions-status-sid",
        )
        .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/debate/sessions?status=bad-status")
            .header("Authorization", format!("Bearer {}", token))
            .header("x-forwarded-for", "127.0.0.1")
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::BAD_REQUEST);
        let body = res.into_body().collect().await?.to_bytes();
        let err: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(err.error, "debate_sessions_invalid_status");
        Ok(())
    }

    #[tokio::test]
    async fn debate_sessions_route_should_reject_invalid_time_range() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "Debate Sessions Range",
            "debate-sessions-range@acme.org",
            "+8613800995555",
            "debate-sessions-range-sid",
        )
        .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/debate/sessions?from=2026-04-05T00:00:00Z&to=2026-04-01T00:00:00Z")
            .header("Authorization", format!("Bearer {}", token))
            .header("x-forwarded-for", "127.0.0.1")
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::BAD_REQUEST);
        let body = res.into_body().collect().await?.to_bytes();
        let err: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(err.error, "debate_sessions_invalid_time_range");
        Ok(())
    }

    #[tokio::test]
    async fn debate_sessions_route_should_return_429_when_user_rate_limited() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "Debate Sessions Ratelimit",
            "debate-sessions-ratelimit@acme.org",
            "+8613800996666",
            "debate-sessions-ratelimit-sid",
        )
        .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/debate/sessions")
            .header("Authorization", format!("Bearer {}", token))
            .header("x-forwarded-for", "127.0.0.1")
            .header("x-test-force-rate-limit", "user")
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::TOO_MANY_REQUESTS);
        assert!(res.headers().contains_key("x-ratelimit-limit"));
        assert!(res.headers().contains_key("x-ratelimit-remaining"));
        assert!(res.headers().contains_key("x-ratelimit-reset"));
        let body = res.into_body().collect().await?.to_bytes();
        let err: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(err.error, "rate_limit_exceeded:debate_sessions_list");
        Ok(())
    }

    #[tokio::test]
    async fn join_debate_session_route_should_return_429_when_user_rate_limited() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "Debate Join Ratelimit",
            "debate-join-ratelimit@acme.org",
            "+8613800997777",
            "debate-join-ratelimit-sid",
        )
        .await?;
        let now = chrono::Utc::now();
        let session_id = seed_session_with_window(
            &state,
            "open",
            now - chrono::Duration::minutes(1),
            now + chrono::Duration::minutes(20),
        )
        .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::POST)
            .uri(format!("/api/debate/sessions/{session_id}/join"))
            .header("Authorization", format!("Bearer {}", token))
            .header("x-forwarded-for", "127.0.0.1")
            .header("x-test-force-rate-limit", "join_user")
            .header("content-type", "application/json")
            .body(Body::from(r#"{"side":"pro"}"#))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::TOO_MANY_REQUESTS);
        let body = res.into_body().collect().await?.to_bytes();
        let err: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(err.error, "rate_limit_exceeded:debate_session_join");
        Ok(())
    }

    #[tokio::test]
    async fn join_debate_session_route_should_normalize_side_and_join() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "Debate Join Normalize",
            "debate-join-normalize@acme.org",
            "+8613800998888",
            "debate-join-normalize-sid",
        )
        .await?;
        let now = chrono::Utc::now();
        let session_id = seed_session_with_window(
            &state,
            "open",
            now - chrono::Duration::minutes(1),
            now + chrono::Duration::minutes(20),
        )
        .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::POST)
            .uri(format!("/api/debate/sessions/{session_id}/join"))
            .header("Authorization", format!("Bearer {}", token))
            .header("x-forwarded-for", "127.0.0.1")
            .header("content-type", "application/json")
            .body(Body::from(r#"{"side":" PRO "}"#))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::OK);
        let body = res.into_body().collect().await?.to_bytes();
        let output: crate::JoinDebateSessionOutput = serde_json::from_slice(&body)?;
        assert_eq!(output.side, "pro");
        assert!(output.newly_joined);
        Ok(())
    }

    #[tokio::test]
    async fn join_debate_session_route_should_reject_too_long_idempotency_key() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "Debate Join Idempotency",
            "debate-join-idempotency@acme.org",
            "+8613800999999",
            "debate-join-idempotency-sid",
        )
        .await?;
        let now = chrono::Utc::now();
        let session_id = seed_session_with_window(
            &state,
            "open",
            now - chrono::Duration::minutes(1),
            now + chrono::Duration::minutes(20),
        )
        .await?;
        let app = get_router(state).await?;
        let long_key = "k".repeat(161);

        let req = Request::builder()
            .method(Method::POST)
            .uri(format!("/api/debate/sessions/{session_id}/join"))
            .header("Authorization", format!("Bearer {}", token))
            .header("x-forwarded-for", "127.0.0.1")
            .header("content-type", "application/json")
            .header("idempotency-key", long_key)
            .body(Body::from(r#"{"side":"pro"}"#))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::BAD_REQUEST);
        let body = res.into_body().collect().await?.to_bytes();
        let err: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(err.error, "debate_join_idempotency_key_too_long");
        Ok(())
    }

    #[tokio::test]
    async fn join_debate_session_route_should_return_conflict_code_for_not_open_yet() -> Result<()>
    {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "Debate Join Not Open",
            "debate-join-not-open@acme.org",
            "+8613800880000",
            "debate-join-not-open-sid",
        )
        .await?;
        let now = chrono::Utc::now();
        let session_id = seed_session_with_window(
            &state,
            "open",
            now + chrono::Duration::minutes(5),
            now + chrono::Duration::minutes(30),
        )
        .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::POST)
            .uri(format!("/api/debate/sessions/{session_id}/join"))
            .header("Authorization", format!("Bearer {}", token))
            .header("x-forwarded-for", "127.0.0.1")
            .header("content-type", "application/json")
            .body(Body::from(r#"{"side":"pro"}"#))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::CONFLICT);
        let body = res.into_body().collect().await?.to_bytes();
        let err: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(err.error, "debate_join_not_open_yet");
        Ok(())
    }
}
