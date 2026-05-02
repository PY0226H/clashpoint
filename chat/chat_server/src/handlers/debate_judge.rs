use crate::{
    application::request_guard::{
        build_rate_limit_headers, enforce_rate_limit, rate_limit_exceeded_response,
        release_idempotency_best_effort, request_idempotency_key_from_headers,
        request_rate_limit_ip_key_from_headers, try_acquire_idempotency_or_fail_open,
    },
    AppError, AppState, RateLimitDecision, RequestJudgeJobInput, SubmitDrawVoteInput,
};
use axum::{
    extract::{Path, Query, State},
    http::{HeaderMap, StatusCode},
    response::{IntoResponse, Response},
    Extension, Json,
};
use chat_core::User;
use std::{
    sync::{
        atomic::{AtomicU64, Ordering},
        LazyLock,
    },
    time::Instant,
};

const JUDGE_REQUEST_RATE_LIMIT_PER_WINDOW: u64 = 10;
const JUDGE_REQUEST_IP_RATE_LIMIT_PER_WINDOW: u64 = 20;
const JUDGE_REQUEST_RATE_LIMIT_WINDOW_SECS: u64 = 300;
const JUDGE_REQUEST_IDEMPOTENCY_TTL_SECS: u64 = 30;
const JUDGE_REQUEST_IDEMPOTENCY_KEY_MAX_LEN: usize = 160;
const JUDGE_REQUEST_LIMITER_SCOPE: &str = "judge_job_request";
const JUDGE_REQUEST_LIMITER_KEY_PREFIX: &str = "judge_request";
const JUDGE_REPORT_READ_USER_RATE_LIMIT_PER_WINDOW: u64 = 60;
const JUDGE_REPORT_READ_IP_RATE_LIMIT_PER_WINDOW: u64 = 120;
const JUDGE_REPORT_READ_RATE_LIMIT_WINDOW_SECS: u64 = 60;
const JUDGE_REPORT_READ_LIMITER_SCOPE: &str = "judge_report_read";
const JUDGE_REPORT_READ_LIMITER_KEY_PREFIX: &str = "judge_report";
const JUDGE_ASSISTANT_ADVISORY_USER_RATE_LIMIT_PER_WINDOW: u64 = 20;
const JUDGE_ASSISTANT_ADVISORY_IP_RATE_LIMIT_PER_WINDOW: u64 = 60;
const JUDGE_ASSISTANT_ADVISORY_RATE_LIMIT_WINDOW_SECS: u64 = 60;
const JUDGE_ASSISTANT_ADVISORY_LIMITER_SCOPE: &str = "judge_assistant_advisory";
const JUDGE_ASSISTANT_ADVISORY_LIMITER_KEY_PREFIX: &str = "judge_assistant";

const JUDGE_REQUEST_CODE_IDEMPOTENCY_KEY_INVALID: &str = "judge_request_idempotency_key_invalid";
const JUDGE_REQUEST_CODE_IDEMPOTENCY_KEY_TOO_LONG: &str = "judge_request_idempotency_key_too_long";
const JUDGE_REQUEST_CODE_IDEMPOTENCY_CONFLICT: &str = "judge_request_idempotency_conflict";
const JUDGE_REPORT_READ_FORBIDDEN: &str = "judge_report_read_forbidden";
const JUDGE_CHALLENGE_REQUEST_FORBIDDEN: &str = "judge_challenge_request_forbidden";
const JUDGE_ASSISTANT_ADVISORY_FORBIDDEN: &str = "judge_assistant_advisory_forbidden";
const JUDGE_ASSISTANT_ADVISORY_CASE_MISMATCH: &str = "judge_assistant_advisory_case_mismatch";

#[derive(Debug, Default)]
struct JudgeReportReadMetrics {
    request_total: AtomicU64,
    success_total: AtomicU64,
    failed_total: AtomicU64,
    rate_limited_total: AtomicU64,
    status_ready_total: AtomicU64,
    status_pending_total: AtomicU64,
    status_blocked_total: AtomicU64,
    status_degraded_total: AtomicU64,
    status_absent_total: AtomicU64,
    status_review_required_total: AtomicU64,
}

impl JudgeReportReadMetrics {
    fn observe_start(&self) {
        self.request_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_rate_limited(&self) {
        self.rate_limited_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_success(&self, status: &str) {
        self.success_total.fetch_add(1, Ordering::Relaxed);
        match status {
            "ready" => {
                self.status_ready_total.fetch_add(1, Ordering::Relaxed);
            }
            "pending" => {
                self.status_pending_total.fetch_add(1, Ordering::Relaxed);
            }
            "blocked" => {
                self.status_blocked_total.fetch_add(1, Ordering::Relaxed);
            }
            "degraded" => {
                self.status_degraded_total.fetch_add(1, Ordering::Relaxed);
            }
            "absent" => {
                self.status_absent_total.fetch_add(1, Ordering::Relaxed);
            }
            "review_required" => {
                self.status_review_required_total
                    .fetch_add(1, Ordering::Relaxed);
            }
            _ => {}
        }
    }

    fn observe_failed(&self) {
        self.failed_total.fetch_add(1, Ordering::Relaxed);
    }
}

static JUDGE_REPORT_READ_METRICS: LazyLock<JudgeReportReadMetrics> =
    LazyLock::new(JudgeReportReadMetrics::default);

/// Request an AI judge job for a debate session.
/// Note: `styleMode` in request body is kept for compatibility and no longer controls behavior.
/// Effective style is decided by server-side `ai_judge.style_mode` config and returned in `styleModeSource`.
#[utoipa::path(
    post,
    path = "/api/debate/sessions/{id}/judge/jobs",
    params(
        ("id" = u64, Path, description = "Debate session id")
    ),
    request_body = RequestJudgeJobInput,
    responses(
        (status = 202, description = "Judge job accepted", body = crate::RequestJudgeJobOutput),
        (status = 400, description = "Invalid input", body = crate::ErrorOutput),
        (status = 401, description = "Unauthorized", body = crate::ErrorOutput),
        (status = 403, description = "Phone bind required", body = crate::ErrorOutput),
        (status = 404, description = "Debate session not found", body = crate::ErrorOutput),
        (status = 409, description = "Request conflict", body = crate::ErrorOutput),
        (status = 429, description = "Rate limit exceeded", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn request_judge_job_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    headers: HeaderMap,
    Json(input): Json<RequestJudgeJobInput>,
) -> Result<impl IntoResponse, AppError> {
    let user_limiter_key = format!(
        "{JUDGE_REQUEST_LIMITER_KEY_PREFIX}:user:{}:session:{}",
        user.id, id
    );
    let user_decision = enforce_rate_limit(
        &state,
        JUDGE_REQUEST_LIMITER_SCOPE,
        &user_limiter_key,
        JUDGE_REQUEST_RATE_LIMIT_PER_WINDOW,
        JUDGE_REQUEST_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    if !user_decision.allowed {
        return Ok(rate_limit_exceeded_response(
            JUDGE_REQUEST_LIMITER_SCOPE,
            build_rate_limit_headers(&user_decision)?,
        ));
    }

    let mut effective_decision = user_decision;
    if let Some(ip_hash) = request_rate_limit_ip_key_from_headers(&headers) {
        let ip_limiter_key =
            format!("{JUDGE_REQUEST_LIMITER_KEY_PREFIX}:ip:{ip_hash}:session:{id}");
        let ip_decision = enforce_rate_limit(
            &state,
            JUDGE_REQUEST_LIMITER_SCOPE,
            &ip_limiter_key,
            JUDGE_REQUEST_IP_RATE_LIMIT_PER_WINDOW,
            JUDGE_REQUEST_RATE_LIMIT_WINDOW_SECS,
        )
        .await;
        if !ip_decision.allowed {
            return Ok(rate_limit_exceeded_response(
                JUDGE_REQUEST_LIMITER_SCOPE,
                build_rate_limit_headers(&ip_decision)?,
            ));
        }
        effective_decision = merge_rate_limit_decision(&effective_decision, &ip_decision);
    }
    let rate_headers = build_rate_limit_headers(&effective_decision)?;

    let request_idempotency_key = request_idempotency_key_from_headers(
        &headers,
        JUDGE_REQUEST_CODE_IDEMPOTENCY_KEY_INVALID,
        JUDGE_REQUEST_CODE_IDEMPOTENCY_KEY_TOO_LONG,
        JUDGE_REQUEST_IDEMPOTENCY_KEY_MAX_LEN,
    )?
    .unwrap_or_else(|| user_limiter_key.clone());

    let acquired = try_acquire_idempotency_or_fail_open(
        &state,
        JUDGE_REQUEST_LIMITER_SCOPE,
        &request_idempotency_key,
        JUDGE_REQUEST_IDEMPOTENCY_TTL_SECS,
    )
    .await;
    if !acquired {
        if let Some(replayed) = state
            .load_judge_job_request_idempotency_replay(id, user.id as u64, &request_idempotency_key)
            .await?
        {
            return Ok((StatusCode::ACCEPTED, rate_headers, Json(replayed)).into_response());
        }
        return Ok((
            StatusCode::CONFLICT,
            rate_headers,
            Json(crate::ErrorOutput::new(
                JUDGE_REQUEST_CODE_IDEMPOTENCY_CONFLICT,
            )),
        )
            .into_response());
    }

    let ret = match state
        .request_judge_job(id, &user, input, Some(&request_idempotency_key))
        .await
    {
        Ok(v) => v,
        Err(err) => {
            release_idempotency_best_effort(
                &state,
                JUDGE_REQUEST_LIMITER_SCOPE,
                &request_idempotency_key,
            )
            .await;
            return Err(err);
        }
    };
    release_idempotency_best_effort(
        &state,
        JUDGE_REQUEST_LIMITER_SCOPE,
        &request_idempotency_key,
    )
    .await;
    Ok((StatusCode::ACCEPTED, rate_headers, Json(ret)).into_response())
}

fn merge_rate_limit_decision(
    user: &RateLimitDecision,
    ip: &RateLimitDecision,
) -> RateLimitDecision {
    RateLimitDecision {
        allowed: user.allowed && ip.allowed,
        limit: user.limit.min(ip.limit),
        remaining: user.remaining.min(ip.remaining),
        reset_at_epoch_secs: user.reset_at_epoch_secs.max(ip.reset_at_epoch_secs),
    }
}

enum AssistantAdvisoryRateLimitOutcome {
    Allowed(HeaderMap),
    Limited(Response),
}

async fn enforce_judge_assistant_advisory_rate_limit(
    state: &AppState,
    headers: &HeaderMap,
    user: &User,
    session_id: u64,
) -> Result<AssistantAdvisoryRateLimitOutcome, AppError> {
    let user_limiter_key = format!(
        "{JUDGE_ASSISTANT_ADVISORY_LIMITER_KEY_PREFIX}:user:{}:session:{}",
        user.id, session_id
    );
    let user_decision = enforce_rate_limit(
        state,
        JUDGE_ASSISTANT_ADVISORY_LIMITER_SCOPE,
        &user_limiter_key,
        JUDGE_ASSISTANT_ADVISORY_USER_RATE_LIMIT_PER_WINDOW,
        JUDGE_ASSISTANT_ADVISORY_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    if !user_decision.allowed {
        return Ok(AssistantAdvisoryRateLimitOutcome::Limited(
            rate_limit_exceeded_response(
                JUDGE_ASSISTANT_ADVISORY_LIMITER_SCOPE,
                build_rate_limit_headers(&user_decision)?,
            ),
        ));
    }

    let mut effective_decision = user_decision;
    if let Some(ip_hash) = request_rate_limit_ip_key_from_headers(headers) {
        let ip_limiter_key = format!(
            "{JUDGE_ASSISTANT_ADVISORY_LIMITER_KEY_PREFIX}:ip:{ip_hash}:session:{session_id}"
        );
        let ip_decision = enforce_rate_limit(
            state,
            JUDGE_ASSISTANT_ADVISORY_LIMITER_SCOPE,
            &ip_limiter_key,
            JUDGE_ASSISTANT_ADVISORY_IP_RATE_LIMIT_PER_WINDOW,
            JUDGE_ASSISTANT_ADVISORY_RATE_LIMIT_WINDOW_SECS,
        )
        .await;
        if !ip_decision.allowed {
            return Ok(AssistantAdvisoryRateLimitOutcome::Limited(
                rate_limit_exceeded_response(
                    JUDGE_ASSISTANT_ADVISORY_LIMITER_SCOPE,
                    build_rate_limit_headers(&ip_decision)?,
                ),
            ));
        }
        effective_decision = merge_rate_limit_decision(&effective_decision, &ip_decision);
    }

    Ok(AssistantAdvisoryRateLimitOutcome::Allowed(
        build_rate_limit_headers(&effective_decision)?,
    ))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        get_router, models::CreateUser, test_fixtures::seed_judge_topic_and_session, ErrorOutput,
    };
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

    async fn create_unbound_user_and_token(
        state: &AppState,
        fullname: &str,
        email: &str,
        sid: &str,
    ) -> Result<(chat_core::User, String)> {
        let user = state
            .create_user(&CreateUser {
                fullname: fullname.to_string(),
                email: email.to_string(),
                password: "123456".to_string(),
            })
            .await?;
        let token = issue_token_for_user(state, user.id, sid).await?;
        Ok((user, token))
    }

    async fn add_participant(
        state: &AppState,
        session_id: i64,
        user_id: i64,
        side: &str,
    ) -> Result<()> {
        sqlx::query(
            r#"
            INSERT INTO session_participants(session_id, user_id, side)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
            "#,
        )
        .bind(session_id)
        .bind(user_id)
        .bind(side)
        .execute(&state.pool)
        .await?;
        Ok(())
    }

    #[tokio::test]
    async fn request_judge_job_route_should_require_auth() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id =
            seed_judge_topic_and_session(&state, "judging", "judge-route-auth").await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::POST)
            .uri(format!("/api/debate/sessions/{session_id}/judge/jobs"))
            .header("Content-Type", "application/json")
            .body(Body::from(r#"{"allowRejudge":false}"#))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::UNAUTHORIZED);
        Ok(())
    }

    #[tokio::test]
    async fn request_judge_job_route_should_require_phone_bind() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id =
            seed_judge_topic_and_session(&state, "judging", "judge-route-phone").await?;
        let (_user, token) = create_unbound_user_and_token(
            &state,
            "judge route unbound",
            "judge-route-unbound@acme.org",
            "judge-route-unbound-sid",
        )
        .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::POST)
            .uri(format!("/api/debate/sessions/{session_id}/judge/jobs"))
            .header("Authorization", format!("Bearer {token}"))
            .header("Content-Type", "application/json")
            .body(Body::from(r#"{"allowRejudge":false}"#))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::FORBIDDEN);
        let body = res.into_body().collect().await?.to_bytes();
        let err: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(err.error, "auth_phone_bind_required");
        Ok(())
    }

    #[tokio::test]
    async fn request_judge_job_route_should_reject_too_long_idempotency_key() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id =
            seed_judge_topic_and_session(&state, "judging", "judge-route-idem").await?;
        let (user, token) = create_bound_user_and_token(
            &state,
            "judge route bound",
            "judge-route-bound@acme.org",
            "+8613800771001",
            "judge-route-bound-sid",
        )
        .await?;
        add_participant(&state, session_id, user.id, "pro").await?;
        let app = get_router(state).await?;
        let long_key = "k".repeat(161);

        let req = Request::builder()
            .method(Method::POST)
            .uri(format!("/api/debate/sessions/{session_id}/judge/jobs"))
            .header("Authorization", format!("Bearer {token}"))
            .header("idempotency-key", long_key)
            .header("Content-Type", "application/json")
            .body(Body::from(r#"{"allowRejudge":false}"#))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::BAD_REQUEST);
        let body = res.into_body().collect().await?.to_bytes();
        let err: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(err.error, JUDGE_REQUEST_CODE_IDEMPOTENCY_KEY_TOO_LONG);
        Ok(())
    }

    #[tokio::test]
    async fn request_judge_job_route_should_accept_x_idempotency_key() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id =
            seed_judge_topic_and_session(&state, "judging", "judge-route-x-idem").await?;
        let (user, token) = create_bound_user_and_token(
            &state,
            "judge route x-idem",
            "judge-route-x-idem@acme.org",
            "+8613800771002",
            "judge-route-x-idem-sid",
        )
        .await?;
        add_participant(&state, session_id, user.id, "pro").await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::POST)
            .uri(format!("/api/debate/sessions/{session_id}/judge/jobs"))
            .header("Authorization", format!("Bearer {token}"))
            .header("x-idempotency-key", "judge-route-x-idem-1")
            .header("Content-Type", "application/json")
            .body(Body::from(r#"{"allowRejudge":false}"#))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::ACCEPTED);
        Ok(())
    }

    #[tokio::test]
    async fn judge_report_route_should_require_auth() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id =
            seed_judge_topic_and_session(&state, "judging", "judge-report-auth").await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri(format!("/api/debate/sessions/{session_id}/judge-report"))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::UNAUTHORIZED);
        Ok(())
    }

    #[tokio::test]
    async fn judge_report_route_should_require_phone_bind() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id =
            seed_judge_topic_and_session(&state, "judging", "judge-report-phone").await?;
        let (_user, token) = create_unbound_user_and_token(
            &state,
            "judge report unbound",
            "judge-report-unbound@acme.org",
            "judge-report-unbound-sid",
        )
        .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri(format!("/api/debate/sessions/{session_id}/judge-report"))
            .header("Authorization", format!("Bearer {token}"))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::FORBIDDEN);
        let body = res.into_body().collect().await?.to_bytes();
        let err: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(err.error, "auth_phone_bind_required");
        Ok(())
    }

    #[tokio::test]
    async fn judge_report_route_should_forbid_non_participant() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id =
            seed_judge_topic_and_session(&state, "judging", "judge-report-forbidden").await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "judge report outsider",
            "judge-report-outsider@acme.org",
            "+8613800771003",
            "judge-report-outsider-sid",
        )
        .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri(format!("/api/debate/sessions/{session_id}/judge-report"))
            .header("Authorization", format!("Bearer {token}"))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::CONFLICT);
        let body = res.into_body().collect().await?.to_bytes();
        let err: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(err.error, "judge_report_read_forbidden");
        Ok(())
    }

    #[tokio::test]
    async fn judge_report_route_should_return_absent_for_participant() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id =
            seed_judge_topic_and_session(&state, "judging", "judge-report-absent").await?;
        let (user, token) = create_bound_user_and_token(
            &state,
            "judge report participant",
            "judge-report-participant@acme.org",
            "+8613800771004",
            "judge-report-participant-sid",
        )
        .await?;
        add_participant(&state, session_id, user.id, "pro").await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri(format!("/api/debate/sessions/{session_id}/judge-report"))
            .header("Authorization", format!("Bearer {token}"))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::OK);
        let body = res.into_body().collect().await?.to_bytes();
        let out: crate::GetJudgeReportOutput = serde_json::from_slice(&body)?;
        assert_eq!(out.status, "absent");
        assert_eq!(out.status_reason, "no_judge_jobs");
        Ok(())
    }

    #[tokio::test]
    async fn judge_report_final_route_should_return_ok_for_participant() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id =
            seed_judge_topic_and_session(&state, "judging", "judge-report-final-route").await?;
        let (user, token) = create_bound_user_and_token(
            &state,
            "judge report final participant",
            "judge-report-final-participant@acme.org",
            "+8613800771005",
            "judge-report-final-participant-sid",
        )
        .await?;
        add_participant(&state, session_id, user.id, "pro").await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri(format!(
                "/api/debate/sessions/{session_id}/judge-report/final"
            ))
            .header("Authorization", format!("Bearer {token}"))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::OK);
        let body = res.into_body().collect().await?.to_bytes();
        let out: crate::GetJudgeReportFinalOutput = serde_json::from_slice(&body)?;
        assert_eq!(out.session_id, session_id as u64);
        assert!(out.final_report.is_none());
        Ok(())
    }

    #[tokio::test]
    async fn judge_public_verify_route_should_forbid_non_participant() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id =
            seed_judge_topic_and_session(&state, "judging", "judge-public-verify-forbid").await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "judge public verify outsider",
            "judge-public-verify-outsider@acme.org",
            "+8613800771006",
            "judge-public-verify-outsider-sid",
        )
        .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri(format!(
                "/api/debate/sessions/{session_id}/judge-report/public-verify"
            ))
            .header("Authorization", format!("Bearer {token}"))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::CONFLICT);
        let body = res.into_body().collect().await?.to_bytes();
        let err: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(err.error, "judge_report_read_forbidden");
        Ok(())
    }

    #[tokio::test]
    async fn judge_public_verify_route_should_return_absent_for_participant() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id =
            seed_judge_topic_and_session(&state, "judging", "judge-public-verify-absent").await?;
        let (user, token) = create_bound_user_and_token(
            &state,
            "judge public verify participant",
            "judge-public-verify-participant@acme.org",
            "+8613800771007",
            "judge-public-verify-participant-sid",
        )
        .await?;
        add_participant(&state, session_id, user.id, "pro").await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri(format!(
                "/api/debate/sessions/{session_id}/judge-report/public-verify"
            ))
            .header("Authorization", format!("Bearer {token}"))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::OK);
        let body = res.into_body().collect().await?.to_bytes();
        let out: crate::GetJudgePublicVerifyOutput = serde_json::from_slice(&body)?;
        assert_eq!(out.session_id, session_id as u64);
        assert_eq!(out.status, "absent");
        assert_eq!(out.status_reason, "public_verify_case_absent");
        assert_eq!(out.dispatch_type, "final");
        assert!(out.case_id.is_none());
        Ok(())
    }

    #[tokio::test]
    async fn judge_challenge_route_should_return_absent_for_participant() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id =
            seed_judge_topic_and_session(&state, "judging", "judge-challenge-absent").await?;
        let (user, token) = create_bound_user_and_token(
            &state,
            "judge challenge participant",
            "judge-challenge-participant@acme.org",
            "+8613800771008",
            "judge-challenge-participant-sid",
        )
        .await?;
        add_participant(&state, session_id, user.id, "pro").await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri(format!(
                "/api/debate/sessions/{session_id}/judge-report/challenge"
            ))
            .header("Authorization", format!("Bearer {token}"))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::OK);
        let body = res.into_body().collect().await?.to_bytes();
        let out: crate::GetJudgeChallengeOutput = serde_json::from_slice(&body)?;
        assert_eq!(out.session_id, session_id as u64);
        assert_eq!(out.status, "absent");
        assert_eq!(out.status_reason, "challenge_case_absent");
        assert_eq!(out.dispatch_type, "final");
        assert!(out.case_id.is_none());
        Ok(())
    }

    #[tokio::test]
    async fn judge_challenge_route_should_forbid_non_participant() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id =
            seed_judge_topic_and_session(&state, "judging", "judge-challenge-read-forbid").await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "judge challenge read outsider",
            "judge-challenge-read-outsider@acme.org",
            "+8613800771010",
            "judge-challenge-read-outsider-sid",
        )
        .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri(format!(
                "/api/debate/sessions/{session_id}/judge-report/challenge"
            ))
            .header("Authorization", format!("Bearer {token}"))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::CONFLICT);
        let body = res.into_body().collect().await?.to_bytes();
        let err: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(err.error, "judge_report_read_forbidden");
        Ok(())
    }

    #[tokio::test]
    async fn judge_challenge_request_route_should_forbid_non_participant() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id =
            seed_judge_topic_and_session(&state, "judging", "judge-challenge-forbid").await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "judge challenge outsider",
            "judge-challenge-outsider@acme.org",
            "+8613800771009",
            "judge-challenge-outsider-sid",
        )
        .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::POST)
            .uri(format!(
                "/api/debate/sessions/{session_id}/judge-report/challenge/request"
            ))
            .header("Authorization", format!("Bearer {token}"))
            .header("Content-Type", "application/json")
            .body(Body::from(r#"{}"#))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::CONFLICT);
        let body = res.into_body().collect().await?.to_bytes();
        let err: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(err.error, "judge_report_read_forbidden");
        Ok(())
    }

    #[tokio::test]
    async fn assistant_npc_coach_route_should_forbid_non_participant() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let session_id =
            seed_judge_topic_and_session(&state, "judging", "assistant-npc-forbid").await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "assistant npc outsider",
            "assistant-npc-outsider@acme.org",
            "+8613800771010",
            "assistant-npc-outsider-sid",
        )
        .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::POST)
            .uri(format!(
                "/api/debate/sessions/{session_id}/assistant/npc-coach/advice"
            ))
            .header("Authorization", format!("Bearer {token}"))
            .header("Content-Type", "application/json")
            .body(Body::from(r#"{"query":"help me prepare","side":"pro"}"#))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::CONFLICT);
        let body = res.into_body().collect().await?.to_bytes();
        let err: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(err.error, "judge_assistant_advisory_forbidden");
        Ok(())
    }

    #[tokio::test]
    async fn assistant_room_qa_route_should_return_not_found_for_missing_session() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "assistant room missing",
            "assistant-room-missing@acme.org",
            "+8613800771011",
            "assistant-room-missing-sid",
        )
        .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::POST)
            .uri("/api/debate/sessions/999999999/assistant/room-qa/answer")
            .header("Authorization", format!("Bearer {token}"))
            .header("Content-Type", "application/json")
            .body(Body::from(r#"{"question":"what is happening?"}"#))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::NOT_FOUND);
        Ok(())
    }
}

/// Get latest AI judge report for a debate session.
#[utoipa::path(
    get,
    path = "/api/debate/sessions/{id}/judge-report",
    params(
        ("id" = u64, Path, description = "Debate session id"),
        ("rejudgeRunNo" = Option<u32>, Query, description = "Optional rejudge run number; defaults to latest run")
    ),
    responses(
        (status = 200, description = "Judge report query result", body = crate::GetJudgeReportOutput),
        (status = 400, description = "Invalid request", body = crate::ErrorOutput),
        (status = 401, description = "Unauthorized", body = crate::ErrorOutput),
        (status = 403, description = "Phone bind required", body = crate::ErrorOutput),
        (status = 404, description = "Debate session not found", body = crate::ErrorOutput),
        (status = 429, description = "Rate limit exceeded", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_latest_judge_report_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Query(query): Query<crate::GetJudgeReportQuery>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, AppError> {
    let started_at = Instant::now();
    JUDGE_REPORT_READ_METRICS.observe_start();
    let user_limiter_key = format!(
        "{JUDGE_REPORT_READ_LIMITER_KEY_PREFIX}:user:{}:session:{}",
        user.id, id
    );
    let user_decision = enforce_rate_limit(
        &state,
        JUDGE_REPORT_READ_LIMITER_SCOPE,
        &user_limiter_key,
        JUDGE_REPORT_READ_USER_RATE_LIMIT_PER_WINDOW,
        JUDGE_REPORT_READ_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    if !user_decision.allowed {
        JUDGE_REPORT_READ_METRICS.observe_rate_limited();
        return Ok(rate_limit_exceeded_response(
            JUDGE_REPORT_READ_LIMITER_SCOPE,
            build_rate_limit_headers(&user_decision)?,
        ));
    }

    let mut effective_decision = user_decision;
    if let Some(ip_hash) = request_rate_limit_ip_key_from_headers(&headers) {
        let ip_limiter_key =
            format!("{JUDGE_REPORT_READ_LIMITER_KEY_PREFIX}:ip:{ip_hash}:session:{id}");
        let ip_decision = enforce_rate_limit(
            &state,
            JUDGE_REPORT_READ_LIMITER_SCOPE,
            &ip_limiter_key,
            JUDGE_REPORT_READ_IP_RATE_LIMIT_PER_WINDOW,
            JUDGE_REPORT_READ_RATE_LIMIT_WINDOW_SECS,
        )
        .await;
        if !ip_decision.allowed {
            JUDGE_REPORT_READ_METRICS.observe_rate_limited();
            return Ok(rate_limit_exceeded_response(
                JUDGE_REPORT_READ_LIMITER_SCOPE,
                build_rate_limit_headers(&ip_decision)?,
            ));
        }
        effective_decision = merge_rate_limit_decision(&effective_decision, &ip_decision);
    }
    let rate_headers = build_rate_limit_headers(&effective_decision)?;

    let ret = match state
        .get_latest_judge_report(id, &user, query.rejudge_run_no)
        .await
    {
        Ok(v) => v,
        Err(AppError::DebateConflict(code)) if code == JUDGE_REPORT_READ_FORBIDDEN => {
            JUDGE_REPORT_READ_METRICS.observe_failed();
            return Ok((
                StatusCode::CONFLICT,
                Json(crate::ErrorOutput::new(JUDGE_REPORT_READ_FORBIDDEN)),
            )
                .into_response());
        }
        Err(err) => {
            JUDGE_REPORT_READ_METRICS.observe_failed();
            tracing::warn!(
                user_id = user.id,
                session_id = id,
                latency_ms = started_at.elapsed().as_millis() as u64,
                err = %err,
                "judge report overview failed"
            );
            return Err(err);
        }
    };
    JUDGE_REPORT_READ_METRICS.observe_success(&ret.status);
    tracing::info!(
        user_id = user.id,
        session_id = id,
        status = ret.status,
        status_reason = ret.status_reason,
        latency_ms = started_at.elapsed().as_millis() as u64,
        "judge report overview queried"
    );
    Ok((StatusCode::OK, rate_headers, Json(ret)).into_response())
}

/// Get latest final judge report detail for a debate session.
#[utoipa::path(
    get,
    path = "/api/debate/sessions/{id}/judge-report/final",
    params(
        ("id" = u64, Path, description = "Debate session id"),
        ("rejudgeRunNo" = Option<u32>, Query, description = "Optional rejudge run number; defaults to latest run")
    ),
    responses(
        (status = 200, description = "Judge final report detail", body = crate::GetJudgeReportFinalOutput),
        (status = 400, description = "Invalid request", body = crate::ErrorOutput),
        (status = 401, description = "Unauthorized", body = crate::ErrorOutput),
        (status = 403, description = "Phone bind required", body = crate::ErrorOutput),
        (status = 404, description = "Debate session not found", body = crate::ErrorOutput),
        (status = 429, description = "Rate limit exceeded", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_latest_judge_final_report_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Query(query): Query<crate::GetJudgeReportQuery>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, AppError> {
    let started_at = Instant::now();
    let user_limiter_key = format!(
        "{JUDGE_REPORT_READ_LIMITER_KEY_PREFIX}:user:{}:session:{}",
        user.id, id
    );
    let user_decision = enforce_rate_limit(
        &state,
        JUDGE_REPORT_READ_LIMITER_SCOPE,
        &user_limiter_key,
        JUDGE_REPORT_READ_USER_RATE_LIMIT_PER_WINDOW,
        JUDGE_REPORT_READ_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    if !user_decision.allowed {
        JUDGE_REPORT_READ_METRICS.observe_rate_limited();
        return Ok(rate_limit_exceeded_response(
            JUDGE_REPORT_READ_LIMITER_SCOPE,
            build_rate_limit_headers(&user_decision)?,
        ));
    }

    let mut effective_decision = user_decision;
    if let Some(ip_hash) = request_rate_limit_ip_key_from_headers(&headers) {
        let ip_limiter_key =
            format!("{JUDGE_REPORT_READ_LIMITER_KEY_PREFIX}:ip:{ip_hash}:session:{id}");
        let ip_decision = enforce_rate_limit(
            &state,
            JUDGE_REPORT_READ_LIMITER_SCOPE,
            &ip_limiter_key,
            JUDGE_REPORT_READ_IP_RATE_LIMIT_PER_WINDOW,
            JUDGE_REPORT_READ_RATE_LIMIT_WINDOW_SECS,
        )
        .await;
        if !ip_decision.allowed {
            JUDGE_REPORT_READ_METRICS.observe_rate_limited();
            return Ok(rate_limit_exceeded_response(
                JUDGE_REPORT_READ_LIMITER_SCOPE,
                build_rate_limit_headers(&ip_decision)?,
            ));
        }
        effective_decision = merge_rate_limit_decision(&effective_decision, &ip_decision);
    }
    let rate_headers = build_rate_limit_headers(&effective_decision)?;

    let ret = match state
        .get_latest_judge_final_report(id, &user, query.rejudge_run_no)
        .await
    {
        Ok(v) => v,
        Err(AppError::DebateConflict(code)) if code == JUDGE_REPORT_READ_FORBIDDEN => {
            JUDGE_REPORT_READ_METRICS.observe_failed();
            return Ok((
                StatusCode::CONFLICT,
                Json(crate::ErrorOutput::new(JUDGE_REPORT_READ_FORBIDDEN)),
            )
                .into_response());
        }
        Err(err) => {
            JUDGE_REPORT_READ_METRICS.observe_failed();
            tracing::warn!(
                user_id = user.id,
                session_id = id,
                latency_ms = started_at.elapsed().as_millis() as u64,
                err = %err,
                "judge report final detail failed"
            );
            return Err(err);
        }
    };
    JUDGE_REPORT_READ_METRICS.observe_success(if ret.final_report.is_some() {
        "ready"
    } else {
        "absent"
    });
    tracing::info!(
        user_id = user.id,
        session_id = id,
        has_final_report = ret.final_report.is_some(),
        latency_ms = started_at.elapsed().as_millis() as u64,
        "judge report final detail queried"
    );
    Ok((StatusCode::OK, rate_headers, Json(ret)).into_response())
}

/// Proxy public verification payload for latest AI judge case in a debate session.
#[utoipa::path(
    get,
    path = "/api/debate/sessions/{id}/judge-report/public-verify",
    params(
        ("id" = u64, Path, description = "Debate session id"),
        ("rejudgeRunNo" = Option<u32>, Query, description = "Optional rejudge run number; defaults to latest run"),
        ("dispatchType" = Option<String>, Query, description = "Judge case type: final or phase; defaults to final")
    ),
    responses(
        (status = 200, description = "Judge public verification proxy result", body = crate::GetJudgePublicVerifyOutput),
        (status = 400, description = "Invalid request", body = crate::ErrorOutput),
        (status = 401, description = "Unauthorized", body = crate::ErrorOutput),
        (status = 403, description = "Phone bind required", body = crate::ErrorOutput),
        (status = 404, description = "Debate session not found", body = crate::ErrorOutput),
        (status = 429, description = "Rate limit exceeded", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_judge_public_verify_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Query(query): Query<crate::GetJudgePublicVerifyQuery>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, AppError> {
    let started_at = Instant::now();
    JUDGE_REPORT_READ_METRICS.observe_start();
    let user_limiter_key = format!(
        "{JUDGE_REPORT_READ_LIMITER_KEY_PREFIX}:user:{}:session:{}",
        user.id, id
    );
    let user_decision = enforce_rate_limit(
        &state,
        JUDGE_REPORT_READ_LIMITER_SCOPE,
        &user_limiter_key,
        JUDGE_REPORT_READ_USER_RATE_LIMIT_PER_WINDOW,
        JUDGE_REPORT_READ_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    if !user_decision.allowed {
        JUDGE_REPORT_READ_METRICS.observe_rate_limited();
        return Ok(rate_limit_exceeded_response(
            JUDGE_REPORT_READ_LIMITER_SCOPE,
            build_rate_limit_headers(&user_decision)?,
        ));
    }

    let mut effective_decision = user_decision;
    if let Some(ip_hash) = request_rate_limit_ip_key_from_headers(&headers) {
        let ip_limiter_key =
            format!("{JUDGE_REPORT_READ_LIMITER_KEY_PREFIX}:ip:{ip_hash}:session:{id}");
        let ip_decision = enforce_rate_limit(
            &state,
            JUDGE_REPORT_READ_LIMITER_SCOPE,
            &ip_limiter_key,
            JUDGE_REPORT_READ_IP_RATE_LIMIT_PER_WINDOW,
            JUDGE_REPORT_READ_RATE_LIMIT_WINDOW_SECS,
        )
        .await;
        if !ip_decision.allowed {
            JUDGE_REPORT_READ_METRICS.observe_rate_limited();
            return Ok(rate_limit_exceeded_response(
                JUDGE_REPORT_READ_LIMITER_SCOPE,
                build_rate_limit_headers(&ip_decision)?,
            ));
        }
        effective_decision = merge_rate_limit_decision(&effective_decision, &ip_decision);
    }
    let rate_headers = build_rate_limit_headers(&effective_decision)?;

    let ret = match state.get_judge_public_verify(id, &user, query).await {
        Ok(v) => v,
        Err(AppError::DebateConflict(code)) if code == JUDGE_REPORT_READ_FORBIDDEN => {
            JUDGE_REPORT_READ_METRICS.observe_failed();
            return Ok((
                StatusCode::CONFLICT,
                Json(crate::ErrorOutput::new(JUDGE_REPORT_READ_FORBIDDEN)),
            )
                .into_response());
        }
        Err(err) => {
            JUDGE_REPORT_READ_METRICS.observe_failed();
            tracing::warn!(
                user_id = user.id,
                session_id = id,
                latency_ms = started_at.elapsed().as_millis() as u64,
                err = %err,
                "judge public verification proxy failed"
            );
            return Err(err);
        }
    };
    JUDGE_REPORT_READ_METRICS.observe_success(&ret.status);
    tracing::info!(
        user_id = user.id,
        session_id = id,
        status = ret.status,
        status_reason = ret.status_reason,
        case_id = ret.case_id,
        dispatch_type = ret.dispatch_type,
        latency_ms = started_at.elapsed().as_millis() as u64,
        "judge public verification proxy queried"
    );
    Ok((StatusCode::OK, rate_headers, Json(ret)).into_response())
}

/// Proxy participant-visible challenge status for latest AI judge case in a debate session.
#[utoipa::path(
    get,
    path = "/api/debate/sessions/{id}/judge-report/challenge",
    params(
        ("id" = u64, Path, description = "Debate session id"),
        ("rejudgeRunNo" = Option<u32>, Query, description = "Optional rejudge run number; defaults to latest run"),
        ("dispatchType" = Option<String>, Query, description = "Judge case type: final or phase; defaults to final")
    ),
    responses(
        (status = 200, description = "Judge challenge proxy result", body = crate::GetJudgeChallengeOutput),
        (status = 400, description = "Invalid request", body = crate::ErrorOutput),
        (status = 401, description = "Unauthorized", body = crate::ErrorOutput),
        (status = 403, description = "Phone bind required", body = crate::ErrorOutput),
        (status = 404, description = "Debate session not found", body = crate::ErrorOutput),
        (status = 409, description = "Request conflict", body = crate::ErrorOutput),
        (status = 429, description = "Rate limit exceeded", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_judge_challenge_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Query(query): Query<crate::GetJudgeChallengeQuery>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, AppError> {
    let started_at = Instant::now();
    JUDGE_REPORT_READ_METRICS.observe_start();
    let user_limiter_key = format!(
        "{JUDGE_REPORT_READ_LIMITER_KEY_PREFIX}:user:{}:session:{}",
        user.id, id
    );
    let user_decision = enforce_rate_limit(
        &state,
        JUDGE_REPORT_READ_LIMITER_SCOPE,
        &user_limiter_key,
        JUDGE_REPORT_READ_USER_RATE_LIMIT_PER_WINDOW,
        JUDGE_REPORT_READ_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    if !user_decision.allowed {
        JUDGE_REPORT_READ_METRICS.observe_rate_limited();
        return Ok(rate_limit_exceeded_response(
            JUDGE_REPORT_READ_LIMITER_SCOPE,
            build_rate_limit_headers(&user_decision)?,
        ));
    }

    let mut effective_decision = user_decision;
    if let Some(ip_hash) = request_rate_limit_ip_key_from_headers(&headers) {
        let ip_limiter_key =
            format!("{JUDGE_REPORT_READ_LIMITER_KEY_PREFIX}:ip:{ip_hash}:session:{id}");
        let ip_decision = enforce_rate_limit(
            &state,
            JUDGE_REPORT_READ_LIMITER_SCOPE,
            &ip_limiter_key,
            JUDGE_REPORT_READ_IP_RATE_LIMIT_PER_WINDOW,
            JUDGE_REPORT_READ_RATE_LIMIT_WINDOW_SECS,
        )
        .await;
        if !ip_decision.allowed {
            JUDGE_REPORT_READ_METRICS.observe_rate_limited();
            return Ok(rate_limit_exceeded_response(
                JUDGE_REPORT_READ_LIMITER_SCOPE,
                build_rate_limit_headers(&ip_decision)?,
            ));
        }
        effective_decision = merge_rate_limit_decision(&effective_decision, &ip_decision);
    }
    let rate_headers = build_rate_limit_headers(&effective_decision)?;

    let ret = match state.get_judge_challenge(id, &user, query).await {
        Ok(v) => v,
        Err(AppError::DebateConflict(code)) if code == JUDGE_REPORT_READ_FORBIDDEN => {
            JUDGE_REPORT_READ_METRICS.observe_failed();
            return Ok((
                StatusCode::CONFLICT,
                Json(crate::ErrorOutput::new(JUDGE_REPORT_READ_FORBIDDEN)),
            )
                .into_response());
        }
        Err(err) => {
            JUDGE_REPORT_READ_METRICS.observe_failed();
            tracing::warn!(
                user_id = user.id,
                session_id = id,
                latency_ms = started_at.elapsed().as_millis() as u64,
                err = %err,
                "judge challenge proxy failed"
            );
            return Err(err);
        }
    };
    JUDGE_REPORT_READ_METRICS.observe_success(&ret.status);
    tracing::info!(
        user_id = user.id,
        session_id = id,
        status = ret.status,
        status_reason = ret.status_reason,
        case_id = ret.case_id,
        dispatch_type = ret.dispatch_type,
        latency_ms = started_at.elapsed().as_millis() as u64,
        "judge challenge proxy queried"
    );
    Ok((StatusCode::OK, rate_headers, Json(ret)).into_response())
}

/// Request a participant challenge for latest AI judge case in a debate session.
#[utoipa::path(
    post,
    path = "/api/debate/sessions/{id}/judge-report/challenge/request",
    params(
        ("id" = u64, Path, description = "Debate session id"),
        ("rejudgeRunNo" = Option<u32>, Query, description = "Optional rejudge run number; defaults to latest run"),
        ("dispatchType" = Option<String>, Query, description = "Judge case type: final or phase; defaults to final")
    ),
    request_body = crate::RequestJudgeChallengeInput,
    responses(
        (status = 200, description = "Judge challenge request result", body = crate::GetJudgeChallengeOutput),
        (status = 400, description = "Invalid request", body = crate::ErrorOutput),
        (status = 401, description = "Unauthorized", body = crate::ErrorOutput),
        (status = 403, description = "Phone bind required", body = crate::ErrorOutput),
        (status = 404, description = "Debate session not found", body = crate::ErrorOutput),
        (status = 409, description = "Request conflict", body = crate::ErrorOutput),
        (status = 429, description = "Rate limit exceeded", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn request_judge_challenge_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Query(query): Query<crate::GetJudgeChallengeQuery>,
    headers: HeaderMap,
    Json(input): Json<crate::RequestJudgeChallengeInput>,
) -> Result<impl IntoResponse, AppError> {
    let started_at = Instant::now();
    JUDGE_REPORT_READ_METRICS.observe_start();
    let user_limiter_key = format!(
        "{JUDGE_REPORT_READ_LIMITER_KEY_PREFIX}:user:{}:session:{}",
        user.id, id
    );
    let user_decision = enforce_rate_limit(
        &state,
        JUDGE_REPORT_READ_LIMITER_SCOPE,
        &user_limiter_key,
        JUDGE_REPORT_READ_USER_RATE_LIMIT_PER_WINDOW,
        JUDGE_REPORT_READ_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    if !user_decision.allowed {
        JUDGE_REPORT_READ_METRICS.observe_rate_limited();
        return Ok(rate_limit_exceeded_response(
            JUDGE_REPORT_READ_LIMITER_SCOPE,
            build_rate_limit_headers(&user_decision)?,
        ));
    }

    let mut effective_decision = user_decision;
    if let Some(ip_hash) = request_rate_limit_ip_key_from_headers(&headers) {
        let ip_limiter_key =
            format!("{JUDGE_REPORT_READ_LIMITER_KEY_PREFIX}:ip:{ip_hash}:session:{id}");
        let ip_decision = enforce_rate_limit(
            &state,
            JUDGE_REPORT_READ_LIMITER_SCOPE,
            &ip_limiter_key,
            JUDGE_REPORT_READ_IP_RATE_LIMIT_PER_WINDOW,
            JUDGE_REPORT_READ_RATE_LIMIT_WINDOW_SECS,
        )
        .await;
        if !ip_decision.allowed {
            JUDGE_REPORT_READ_METRICS.observe_rate_limited();
            return Ok(rate_limit_exceeded_response(
                JUDGE_REPORT_READ_LIMITER_SCOPE,
                build_rate_limit_headers(&ip_decision)?,
            ));
        }
        effective_decision = merge_rate_limit_decision(&effective_decision, &ip_decision);
    }
    let rate_headers = build_rate_limit_headers(&effective_decision)?;

    let ret = match state.request_judge_challenge(id, &user, query, input).await {
        Ok(v) => v,
        Err(AppError::DebateConflict(code))
            if code == JUDGE_REPORT_READ_FORBIDDEN || code == JUDGE_CHALLENGE_REQUEST_FORBIDDEN =>
        {
            JUDGE_REPORT_READ_METRICS.observe_failed();
            return Ok((
                StatusCode::CONFLICT,
                Json(crate::ErrorOutput::new(code.as_str())),
            )
                .into_response());
        }
        Err(err) => {
            JUDGE_REPORT_READ_METRICS.observe_failed();
            tracing::warn!(
                user_id = user.id,
                session_id = id,
                latency_ms = started_at.elapsed().as_millis() as u64,
                err = %err,
                "judge challenge request failed"
            );
            return Err(err);
        }
    };
    JUDGE_REPORT_READ_METRICS.observe_success(&ret.status);
    tracing::info!(
        user_id = user.id,
        session_id = id,
        status = ret.status,
        status_reason = ret.status_reason,
        case_id = ret.case_id,
        dispatch_type = ret.dispatch_type,
        latency_ms = started_at.elapsed().as_millis() as u64,
        "judge challenge requested"
    );
    Ok((StatusCode::OK, rate_headers, Json(ret)).into_response())
}

/// Request advisory-only NPC Coach advice for a participant in a debate session.
#[utoipa::path(
    post,
    path = "/api/debate/sessions/{id}/assistant/npc-coach/advice",
    params(
        ("id" = u64, Path, description = "Debate session id")
    ),
    request_body = crate::RequestNpcCoachAdviceInput,
    responses(
        (status = 200, description = "NPC Coach advisory proxy result", body = crate::JudgeAssistantAdvisoryOutput),
        (status = 400, description = "Invalid request", body = crate::ErrorOutput),
        (status = 401, description = "Unauthorized", body = crate::ErrorOutput),
        (status = 403, description = "Phone bind required", body = crate::ErrorOutput),
        (status = 404, description = "Debate session not found", body = crate::ErrorOutput),
        (status = 409, description = "Request conflict", body = crate::ErrorOutput),
        (status = 429, description = "Rate limit exceeded", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn request_npc_coach_advice_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    headers: HeaderMap,
    Json(input): Json<crate::RequestNpcCoachAdviceInput>,
) -> Result<impl IntoResponse, AppError> {
    let started_at = Instant::now();
    let rate_headers =
        match enforce_judge_assistant_advisory_rate_limit(&state, &headers, &user, id).await? {
            AssistantAdvisoryRateLimitOutcome::Allowed(headers) => headers,
            AssistantAdvisoryRateLimitOutcome::Limited(response) => return Ok(response),
        };

    let ret = match state.request_npc_coach_advice(id, &user, input).await {
        Ok(v) => v,
        Err(AppError::DebateConflict(code))
            if code == JUDGE_ASSISTANT_ADVISORY_FORBIDDEN
                || code == JUDGE_ASSISTANT_ADVISORY_CASE_MISMATCH =>
        {
            return Ok((
                StatusCode::CONFLICT,
                Json(crate::ErrorOutput::new(code.as_str())),
            )
                .into_response());
        }
        Err(err) => {
            tracing::warn!(
                user_id = user.id,
                session_id = id,
                latency_ms = started_at.elapsed().as_millis() as u64,
                err = %err,
                "NPC Coach advisory proxy failed"
            );
            return Err(err);
        }
    };

    tracing::info!(
        user_id = user.id,
        session_id = id,
        status = ret.status,
        status_reason = ret.status_reason,
        case_id = ret.case_id,
        latency_ms = started_at.elapsed().as_millis() as u64,
        "NPC Coach advisory proxy requested"
    );
    Ok((StatusCode::OK, rate_headers, Json(ret)).into_response())
}

/// Request advisory-only Room QA answer for a participant in a debate session.
#[utoipa::path(
    post,
    path = "/api/debate/sessions/{id}/assistant/room-qa/answer",
    params(
        ("id" = u64, Path, description = "Debate session id")
    ),
    request_body = crate::RequestRoomQaAnswerInput,
    responses(
        (status = 200, description = "Room QA advisory proxy result", body = crate::JudgeAssistantAdvisoryOutput),
        (status = 400, description = "Invalid request", body = crate::ErrorOutput),
        (status = 401, description = "Unauthorized", body = crate::ErrorOutput),
        (status = 403, description = "Phone bind required", body = crate::ErrorOutput),
        (status = 404, description = "Debate session not found", body = crate::ErrorOutput),
        (status = 409, description = "Request conflict", body = crate::ErrorOutput),
        (status = 429, description = "Rate limit exceeded", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn request_room_qa_answer_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    headers: HeaderMap,
    Json(input): Json<crate::RequestRoomQaAnswerInput>,
) -> Result<impl IntoResponse, AppError> {
    let started_at = Instant::now();
    let rate_headers =
        match enforce_judge_assistant_advisory_rate_limit(&state, &headers, &user, id).await? {
            AssistantAdvisoryRateLimitOutcome::Allowed(headers) => headers,
            AssistantAdvisoryRateLimitOutcome::Limited(response) => return Ok(response),
        };

    let ret = match state.request_room_qa_answer(id, &user, input).await {
        Ok(v) => v,
        Err(AppError::DebateConflict(code))
            if code == JUDGE_ASSISTANT_ADVISORY_FORBIDDEN
                || code == JUDGE_ASSISTANT_ADVISORY_CASE_MISMATCH =>
        {
            return Ok((
                StatusCode::CONFLICT,
                Json(crate::ErrorOutput::new(code.as_str())),
            )
                .into_response());
        }
        Err(err) => {
            tracing::warn!(
                user_id = user.id,
                session_id = id,
                latency_ms = started_at.elapsed().as_millis() as u64,
                err = %err,
                "Room QA advisory proxy failed"
            );
            return Err(err);
        }
    };

    tracing::info!(
        user_id = user.id,
        session_id = id,
        status = ret.status,
        status_reason = ret.status_reason,
        case_id = ret.case_id,
        latency_ms = started_at.elapsed().as_millis() as u64,
        "Room QA advisory proxy requested"
    );
    Ok((StatusCode::OK, rate_headers, Json(ret)).into_response())
}

/// Get draw-vote status for latest draw-required judge report in a debate session.
#[utoipa::path(
    get,
    path = "/api/debate/sessions/{id}/draw-vote",
    params(
        ("id" = u64, Path, description = "Debate session id")
    ),
    responses(
        (status = 200, description = "Draw vote status", body = crate::GetDrawVoteOutput),
        (status = 404, description = "Debate session not found", body = crate::ErrorOutput),
        (status = 409, description = "User is not participant", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_draw_vote_status_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.get_draw_vote_status(id, &user).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Submit or update current user's draw vote.
#[utoipa::path(
    post,
    path = "/api/debate/sessions/{id}/draw-vote/ballots",
    params(
        ("id" = u64, Path, description = "Debate session id")
    ),
    request_body = SubmitDrawVoteInput,
    responses(
        (status = 200, description = "Draw vote submit result", body = crate::SubmitDrawVoteOutput),
        (status = 400, description = "Invalid input", body = crate::ErrorOutput),
        (status = 404, description = "Debate session not found", body = crate::ErrorOutput),
        (status = 409, description = "Vote conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn submit_draw_vote_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Json(input): Json<SubmitDrawVoteInput>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.submit_draw_vote(id, &user, input).await?;
    Ok((StatusCode::OK, Json(ret)))
}
