#[cfg(test)]
use crate::RateLimitDecision;
use crate::{
    application::request_guard::{
        build_rate_limit_headers, enforce_rate_limit, rate_limit_exceeded_response,
    },
    AppError, AppState, CreateDebateMessageInput, JoinDebateSessionInput, ListDebateMessages,
    ListDebatePinnedMessages, ListDebateSessions, ListDebateSessionsOutput, PinDebateMessageInput,
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
        (status = 404, description = "Debate session not found", body = crate::ErrorOutput),
        (status = 409, description = "Join conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn join_debate_session_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Json(input): Json<JoinDebateSessionInput>,
) -> Result<impl IntoResponse, AppError> {
    let result = state.join_debate_session(id, &user, input).await?;
    Ok((StatusCode::OK, Json(result)))
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
}
