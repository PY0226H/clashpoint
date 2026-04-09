#[cfg(test)]
use crate::RateLimitDecision;
use crate::{
    application::request_guard::{
        build_rate_limit_headers, enforce_rate_limit, rate_limit_exceeded_response,
    },
    AppError, AppState, ListDebateTopics, ListDebateTopicsOutput,
};
use axum::{
    extract::{Query, State},
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

pub(crate) use super::debate_room::{
    create_debate_message_handler, join_debate_session_handler, list_debate_messages_handler,
    list_debate_pinned_messages_handler, list_debate_sessions_handler, pin_debate_message_handler,
};

pub(crate) use super::debate_judge::{
    get_draw_vote_status_handler, get_latest_judge_final_report_handler,
    get_latest_judge_report_handler, request_judge_job_handler, submit_draw_vote_handler,
};
pub(crate) use super::debate_ops::{
    apply_ops_observability_anomaly_action_handler, create_debate_session_ops_handler,
    create_debate_topic_ops_handler, discard_kafka_dlq_event_handler,
    execute_judge_replay_ops_handler, get_judge_replay_preview_ops_handler,
    get_kafka_transport_readiness_handler, get_ops_observability_config_handler,
    get_ops_observability_metrics_dictionary_handler, get_ops_observability_slo_snapshot_handler,
    get_ops_rbac_me_handler, get_ops_service_split_readiness_handler,
    list_judge_final_dispatch_failure_stats_ops_handler, list_judge_replay_actions_ops_handler,
    list_judge_reviews_ops_handler, list_judge_trace_replay_ops_handler,
    list_kafka_dlq_events_handler, list_ops_alert_notifications_handler,
    list_ops_role_assignments_handler, list_ops_service_split_review_audits_handler,
    replay_kafka_dlq_event_handler, request_judge_rejudge_ops_handler,
    revoke_ops_role_assignment_handler, run_ops_observability_evaluation_once_handler,
    update_debate_session_ops_handler, update_debate_topic_ops_handler,
    upsert_ops_observability_anomaly_state_handler, upsert_ops_observability_thresholds_handler,
    upsert_ops_role_assignment_handler, upsert_ops_service_split_review_handler,
};

const DEBATE_TOPICS_LIST_USER_RATE_LIMIT_PER_WINDOW: u64 = 120;
const DEBATE_TOPICS_LIST_IP_RATE_LIMIT_PER_WINDOW: u64 = 240;
const DEBATE_TOPICS_LIST_RATE_LIMIT_WINDOW_SECS: u64 = 60;

#[derive(Debug, Default)]
struct DebateTopicsListMetrics {
    request_total: AtomicU64,
    success_total: AtomicU64,
    failed_total: AtomicU64,
    rate_limited_total: AtomicU64,
    active_only_true_total: AtomicU64,
    active_only_false_total: AtomicU64,
    active_only_forced_true_total: AtomicU64,
    inactive_query_allowed_total: AtomicU64,
    result_items_total: AtomicU64,
    result_items_samples_total: AtomicU64,
    latency_ms_total: AtomicU64,
    latency_ms_samples_total: AtomicU64,
}

impl DebateTopicsListMetrics {
    fn observe_start(&self, active_only: bool) {
        self.request_total.fetch_add(1, Ordering::Relaxed);
        if active_only {
            self.active_only_true_total.fetch_add(1, Ordering::Relaxed);
        } else {
            self.active_only_false_total.fetch_add(1, Ordering::Relaxed);
        }
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

    fn observe_rate_limited(&self) {
        self.rate_limited_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_forced_active_only_true(&self) {
        self.active_only_forced_true_total
            .fetch_add(1, Ordering::Relaxed);
    }

    fn observe_inactive_query_allowed(&self) {
        self.inactive_query_allowed_total
            .fetch_add(1, Ordering::Relaxed);
    }

    fn snapshot(&self) -> (u64, u64, u64, u64, u64, u64, u64, u64) {
        (
            self.request_total.load(Ordering::Relaxed),
            self.success_total.load(Ordering::Relaxed),
            self.failed_total.load(Ordering::Relaxed),
            self.rate_limited_total.load(Ordering::Relaxed),
            self.active_only_true_total.load(Ordering::Relaxed),
            self.active_only_false_total.load(Ordering::Relaxed),
            self.active_only_forced_true_total.load(Ordering::Relaxed),
            self.inactive_query_allowed_total.load(Ordering::Relaxed),
        )
    }
}

static DEBATE_TOPICS_LIST_METRICS: LazyLock<DebateTopicsListMetrics> =
    LazyLock::new(DebateTopicsListMetrics::default);

/// List debate topics in the platform scope.
#[utoipa::path(
    get,
    path = "/api/debate/topics",
    params(
        ListDebateTopics
    ),
    responses(
        (status = 200, description = "List of debate topics", body = crate::ListDebateTopicsOutput),
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
pub(crate) async fn list_debate_topics_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(input): Query<ListDebateTopics>,
) -> Result<Response, AppError> {
    let started_at = Instant::now();
    DEBATE_TOPICS_LIST_METRICS.observe_start(input.active_only);
    let request_id = request_id_from_headers(&headers);

    let mut effective_input = input;
    let mut forced_active_only = false;
    if !effective_input.active_only {
        let rbac = state.get_ops_rbac_me(&user).await?;
        if !(rbac.is_owner || rbac.permissions.debate_manage) {
            effective_input.active_only = true;
            forced_active_only = true;
            DEBATE_TOPICS_LIST_METRICS.observe_forced_active_only_true();
            tracing::info!(
                user_id = user.id,
                request_id = request_id.as_deref().unwrap_or_default(),
                decision = "active_only_forced_true",
                "list debate topics enforced minimal visibility for non-admin user"
            );
        } else {
            DEBATE_TOPICS_LIST_METRICS.observe_inactive_query_allowed();
        }
    }

    let user_decision = enforce_rate_limit(
        &state,
        "debate_topics_list_user",
        &user.id.to_string(),
        DEBATE_TOPICS_LIST_USER_RATE_LIMIT_PER_WINDOW,
        DEBATE_TOPICS_LIST_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let user_decision = maybe_override_rate_limit_decision(&headers, "user", user_decision);
    let resp_headers = build_rate_limit_headers(&user_decision)?;
    if !user_decision.allowed {
        DEBATE_TOPICS_LIST_METRICS.observe_rate_limited();
        tracing::warn!(
            user_id = user.id,
            request_id = request_id.as_deref().unwrap_or_default(),
            decision = "rate_limited_user",
            "list debate topics blocked by user rate limiter"
        );
        return Ok(rate_limit_exceeded_response(
            "debate_topics_list",
            resp_headers,
        ));
    }

    let ip_limit_key =
        request_rate_limit_ip_key_from_headers(&headers).unwrap_or_else(|| "unknown".to_string());
    let ip_decision = enforce_rate_limit(
        &state,
        "debate_topics_list_ip",
        &ip_limit_key,
        DEBATE_TOPICS_LIST_IP_RATE_LIMIT_PER_WINDOW,
        DEBATE_TOPICS_LIST_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let ip_decision = maybe_override_rate_limit_decision(&headers, "ip", ip_decision);
    if !ip_decision.allowed {
        DEBATE_TOPICS_LIST_METRICS.observe_rate_limited();
        tracing::warn!(
            user_id = user.id,
            request_id = request_id.as_deref().unwrap_or_default(),
            decision = "rate_limited_ip",
            "list debate topics blocked by ip rate limiter"
        );
        return Ok(rate_limit_exceeded_response(
            "debate_topics_list",
            build_rate_limit_headers(&ip_decision)?,
        ));
    }

    let category = effective_input.category.clone().unwrap_or_default();
    let cursor_present = effective_input
        .cursor
        .as_deref()
        .map(str::trim)
        .map(|v| !v.is_empty())
        .unwrap_or(false);
    let effective_active_only = effective_input.active_only;
    let output: ListDebateTopicsOutput = match state.list_debate_topics(effective_input).await {
        Ok(v) => v,
        Err(err) => {
            let latency_ms = started_at.elapsed().as_millis() as u64;
            DEBATE_TOPICS_LIST_METRICS.observe_failure(latency_ms);
            tracing::warn!(
                user_id = user.id,
                request_id = request_id.as_deref().unwrap_or_default(),
                decision = "failed",
                latency_ms,
                "list debate topics failed: {}",
                err
            );
            return Err(err);
        }
    };
    let latency_ms = started_at.elapsed().as_millis() as u64;
    DEBATE_TOPICS_LIST_METRICS.observe_success(output.items.len(), latency_ms);
    let (
        request_total,
        success_total,
        failed_total,
        rate_limited_total,
        active_only_true_total,
        active_only_false_total,
        active_only_forced_true_total,
        inactive_query_allowed_total,
    ) = DEBATE_TOPICS_LIST_METRICS.snapshot();
    tracing::info!(
        user_id = user.id,
        request_id = request_id.as_deref().unwrap_or_default(),
        category = category.as_str(),
        active_only = effective_active_only,
        forced_active_only,
        cursor_present,
        result_count = output.items.len(),
        has_more = output.has_more,
        revision = output.revision.as_str(),
        latency_ms,
        debate_topics_list_request_total = request_total,
        debate_topics_list_success_total = success_total,
        debate_topics_list_failed_total = failed_total,
        debate_topics_list_rate_limited_total = rate_limited_total,
        debate_topics_list_active_only_true_total = active_only_true_total,
        debate_topics_list_active_only_false_total = active_only_false_total,
        debate_topics_list_active_only_forced_true_total = active_only_forced_true_total,
        debate_topics_list_inactive_query_allowed_total = inactive_query_allowed_total,
        decision = "success",
        "list debate topics served"
    );
    Ok((StatusCode::OK, resp_headers, Json(output)).into_response())
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
    use crate::{
        get_router, models::CreateUser, DebateSessionSummary, DebateTopic, ErrorOutput,
        GetOpsRbacMeOutput, ListOpsRoleAssignmentsOutput, OpsRoleAssignment, RevokeOpsRoleOutput,
        UpsertOpsRoleInput,
    };
    use anyhow::Result;
    use axum::{
        body::Body,
        http::{Method, Request, StatusCode},
    };
    use chrono::{Duration, Utc};
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

    async fn seed_topic(state: &AppState) -> Result<i64> {
        let row: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO debate_topics(
                title, description, category, stance_pro, stance_con, context_seed, is_active, created_by
            )
            VALUES ($1, $2, $3, $4, $5, NULL, true, 1)
            RETURNING id
            "#,
        )
        .bind("ops-session-topic")
        .bind("desc")
        .bind("technology")
        .bind("pro")
        .bind("con")
        .fetch_one(&state.pool)
        .await?;
        Ok(row.0)
    }

    async fn seed_topic_and_session(state: &AppState) -> Result<(i64, i64)> {
        let topic_id = seed_topic(state).await?;
        let now = Utc::now();
        let row: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO debate_sessions(
                topic_id, status, scheduled_start_at, end_at, max_participants_per_side
            )
            VALUES ($1, 'scheduled', $2, $3, 120)
            RETURNING id
            "#,
        )
        .bind(topic_id)
        .bind(now + Duration::minutes(10))
        .bind(now + Duration::minutes(70))
        .fetch_one(&state.pool)
        .await?;
        Ok((topic_id, row.0))
    }

    #[tokio::test]
    async fn debate_topics_route_should_force_active_only_true_for_non_ops_user() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "Debate User",
            "debate-user@acme.org",
            "+8613800991111",
            "debate-user-sid",
        )
        .await?;
        sqlx::query(
            r#"
            INSERT INTO debate_topics(title, description, category, stance_pro, stance_con, context_seed, is_active, created_by)
            VALUES
                ('active-topic', 'desc', 'game', 'pro', 'con', NULL, true, 1),
                ('inactive-topic', 'desc', 'game', 'pro', 'con', NULL, false, 1)
            "#,
        )
        .execute(&state.pool)
        .await?;
        let app = get_router(state.clone()).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/debate/topics?activeOnly=false&limit=20")
            .header("Authorization", format!("Bearer {}", token))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::OK);
        let body = res.into_body().collect().await?.to_bytes();
        let out: ListDebateTopicsOutput = serde_json::from_slice(&body)?;
        assert!(!out.items.is_empty());
        assert!(out.items.iter().all(|item| item.is_active));
        Ok(())
    }

    #[tokio::test]
    async fn debate_topics_route_should_allow_ops_admin_active_only_false() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let (ops_admin, token) = create_bound_user_and_token(
            &state,
            "Debate Ops",
            "debate-ops@acme.org",
            "+8613800992222",
            "debate-ops-sid",
        )
        .await?;
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                ops_admin.id as u64,
                UpsertOpsRoleInput {
                    role: "ops_admin".to_string(),
                },
            )
            .await?;
        sqlx::query(
            r#"
            INSERT INTO debate_topics(title, description, category, stance_pro, stance_con, context_seed, is_active, created_by)
            VALUES
                ('active-topic', 'desc', 'game', 'pro', 'con', NULL, true, 1),
                ('inactive-topic', 'desc', 'game', 'pro', 'con', NULL, false, 1)
            "#,
        )
        .execute(&state.pool)
        .await?;
        let app = get_router(state.clone()).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/debate/topics?activeOnly=false&limit=20")
            .header("Authorization", format!("Bearer {}", token))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::OK);
        let body = res.into_body().collect().await?.to_bytes();
        let out: ListDebateTopicsOutput = serde_json::from_slice(&body)?;
        assert!(out.items.iter().any(|item| !item.is_active));
        Ok(())
    }

    #[tokio::test]
    async fn debate_topics_route_should_return_400_for_invalid_cursor() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "Debate Query",
            "debate-query@acme.org",
            "+8613800993333",
            "debate-query-sid",
        )
        .await?;
        let app = get_router(state.clone()).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/debate/topics?cursor=bad-cursor")
            .header("Authorization", format!("Bearer {}", token))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::BAD_REQUEST);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "debate_topics_cursor_invalid");
        Ok(())
    }

    #[tokio::test]
    async fn debate_topics_route_should_return_429_when_rate_limited() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "Debate Rate",
            "debate-rate@acme.org",
            "+8613800994444",
            "debate-rate-sid",
        )
        .await?;
        let app = get_router(state.clone()).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/debate/topics")
            .header("Authorization", format!("Bearer {}", token))
            .header("x-test-force-rate-limit", "user")
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::TOO_MANY_REQUESTS);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "rate_limit_exceeded:debate_topics_list");
        Ok(())
    }

    #[tokio::test]
    async fn get_ops_rbac_me_route_should_return_200_for_bound_user() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (user, token) = create_bound_user_and_token(
            &state,
            "Ops Rbac Me User",
            "ops-rbac-me-user@acme.org",
            "+8613810000001",
            "ops-rbac-me-user-sid",
        )
        .await?;
        let app = get_router(state.clone()).await?;
        let request_id = "ops-rbac-me-read-success";

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/debate/ops/rbac/me")
            .header("Authorization", format!("Bearer {}", token))
            .header("x-request-id", request_id)
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::OK);
        let body = res.into_body().collect().await?.to_bytes();
        let out: GetOpsRbacMeOutput = serde_json::from_slice(&body)?;
        assert_eq!(out.user_id, user.id as u64);
        assert!(!out.is_owner);
        assert_eq!(out.role, None);
        assert!(!out.permissions.debate_manage);
        assert!(!out.permissions.judge_review);
        assert!(!out.permissions.judge_rejudge);
        assert!(!out.permissions.role_manage);
        assert!(!out.rbac_revision.is_empty());
        assert_ne!(out.rbac_revision, "empty");
        let audit_count: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)::bigint
            FROM ops_rbac_audits
            WHERE event_type = 'rbac_me_read'
              AND operator_user_id = $1
              AND decision = 'success'
              AND request_id = $2
            "#,
        )
        .bind(user.id)
        .bind(request_id)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(audit_count, 1);
        Ok(())
    }

    #[tokio::test]
    async fn get_ops_rbac_me_route_should_return_401_without_token() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let app = get_router(state.clone()).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/debate/ops/rbac/me")
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::UNAUTHORIZED);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "auth_access_invalid");
        Ok(())
    }

    #[tokio::test]
    async fn get_ops_rbac_me_route_should_return_429_when_rate_limited() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (user, token) = create_bound_user_and_token(
            &state,
            "Ops Rbac Me Rate Limited",
            "ops-rbac-me-rate-limited@acme.org",
            "+8613810000002",
            "ops-rbac-me-rate-limited-sid",
        )
        .await?;
        let app = get_router(state.clone()).await?;
        let request_id = "ops-rbac-me-rate-limited";

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/debate/ops/rbac/me")
            .header("Authorization", format!("Bearer {}", token))
            .header("x-request-id", request_id)
            .header("x-test-force-rate-limit", "ops_rbac_me_user")
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::TOO_MANY_REQUESTS);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "rate_limit_exceeded:ops_rbac_me");
        let audit_count: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)::bigint
            FROM ops_rbac_audits
            WHERE event_type = 'rbac_me_read'
              AND operator_user_id = $1
              AND decision = 'rate_limited_user'
              AND request_id = $2
            "#,
        )
        .bind(user.id)
        .bind(request_id)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(audit_count, 1);
        Ok(())
    }

    #[tokio::test]
    async fn get_ops_rbac_me_route_should_return_403_for_unbound_user() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let user = state
            .create_user(&CreateUser {
                fullname: "Ops Rbac Me Unbound".to_string(),
                email: "ops-rbac-me-unbound@acme.org".to_string(),
                password: "123456".to_string(),
            })
            .await?;
        let token = issue_token_for_user(&state, user.id, "ops-rbac-me-unbound-sid").await?;
        let app = get_router(state.clone()).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/debate/ops/rbac/me")
            .header("Authorization", format!("Bearer {}", token))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::FORBIDDEN);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "auth_phone_bind_required");
        Ok(())
    }

    #[tokio::test]
    async fn get_ops_rbac_me_route_should_return_500_when_owner_source_missing() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "Ops Rbac Me Missing Owner Source",
            "ops-rbac-me-missing-owner-source@acme.org",
            "+8613810000003",
            "ops-rbac-me-missing-owner-source-sid",
        )
        .await?;
        sqlx::query("DELETE FROM platform_admin_owners WHERE singleton_key = TRUE")
            .execute(&state.pool)
            .await?;
        let app = get_router(state.clone()).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/debate/ops/rbac/me")
            .header("Authorization", format!("Bearer {}", token))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::INTERNAL_SERVER_ERROR);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "platform_owner_not_configured");
        Ok(())
    }

    #[tokio::test]
    async fn get_ops_rbac_roles_route_should_return_200_for_owner() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let target_user = state
            .find_user_by_id(2)
            .await?
            .expect("target user should exist");
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                2,
                UpsertOpsRoleInput {
                    role: "ops_reviewer".to_string(),
                },
            )
            .await?;
        let token = issue_token_for_user(&state, owner.id, "ops-rbac-roles-owner-sid").await?;
        let app = get_router(state.clone()).await?;
        let request_id = "ops-rbac-roles-list-success";

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/debate/ops/rbac/roles")
            .header("Authorization", format!("Bearer {}", token))
            .header("x-request-id", request_id)
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::OK);
        let body = res.into_body().collect().await?.to_bytes();
        let out: ListOpsRoleAssignmentsOutput = serde_json::from_slice(&body)?;
        assert!(!out.rbac_revision.is_empty());
        assert_ne!(out.rbac_revision, "empty");
        let target_assignment = out
            .items
            .iter()
            .find(|item| item.user_id == 2 && item.role == "ops_reviewer")
            .expect("target assignment should exist");
        assert_ne!(target_assignment.user_email, target_user.email);
        assert_ne!(target_assignment.user_fullname, target_user.fullname);
        assert!(target_assignment.user_email.contains("***"));
        assert!(target_assignment.user_fullname.contains("***"));
        let result_count_i64 = i64::try_from(out.items.len()).expect("result_count should fit i64");
        let audit_count: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)::bigint
            FROM ops_rbac_audits
            WHERE event_type = 'roles_list_read'
              AND operator_user_id = $1
              AND decision = 'success'
              AND request_id = $2
              AND result_count = $3
            "#,
        )
        .bind(owner.id)
        .bind(request_id)
        .bind(result_count_i64)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(audit_count, 1);
        Ok(())
    }

    #[tokio::test]
    async fn get_ops_rbac_roles_route_should_return_200_for_delegated_role_admin() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let (delegated, token) = create_bound_user_and_token(
            &state,
            "Ops Rbac Roles Delegated Admin",
            "ops-rbac-roles-delegated-admin@acme.org",
            "+86138100000131",
            "ops-rbac-roles-delegated-admin-sid",
        )
        .await?;
        let target = state
            .create_user(&CreateUser {
                fullname: "Ops Rbac Roles Delegated Target".to_string(),
                email: "ops-rbac-roles-delegated-target@acme.org".to_string(),
                password: "123456".to_string(),
            })
            .await?;
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                delegated.id as u64,
                UpsertOpsRoleInput {
                    role: "platform_role_admin".to_string(),
                },
            )
            .await?;
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                target.id as u64,
                UpsertOpsRoleInput {
                    role: "ops_reviewer".to_string(),
                },
            )
            .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/debate/ops/rbac/roles")
            .header("Authorization", format!("Bearer {}", token))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::OK);
        let body = res.into_body().collect().await?.to_bytes();
        let out: ListOpsRoleAssignmentsOutput = serde_json::from_slice(&body)?;
        assert!(out
            .items
            .iter()
            .any(|item| item.user_id == target.id as u64));
        Ok(())
    }

    #[tokio::test]
    async fn get_ops_rbac_roles_route_should_return_full_pii_when_requested() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let target_user = state
            .find_user_by_id(2)
            .await?
            .expect("target user should exist");
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                2,
                UpsertOpsRoleInput {
                    role: "ops_reviewer".to_string(),
                },
            )
            .await?;
        let token =
            issue_token_for_user(&state, owner.id, "ops-rbac-roles-owner-full-pii-sid").await?;
        let app = get_router(state.clone()).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/debate/ops/rbac/roles?piiLevel=full")
            .header("Authorization", format!("Bearer {}", token))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::OK);
        let body = res.into_body().collect().await?.to_bytes();
        let out: ListOpsRoleAssignmentsOutput = serde_json::from_slice(&body)?;
        let target_assignment = out
            .items
            .iter()
            .find(|item| item.user_id == 2 && item.role == "ops_reviewer")
            .expect("target assignment should exist");
        assert_eq!(target_assignment.user_email, target_user.email);
        assert_eq!(target_assignment.user_fullname, target_user.fullname);
        Ok(())
    }

    #[tokio::test]
    async fn get_ops_rbac_roles_route_should_return_401_without_token() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let app = get_router(state.clone()).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/debate/ops/rbac/roles")
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::UNAUTHORIZED);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "auth_access_invalid");
        Ok(())
    }

    #[tokio::test]
    async fn get_ops_rbac_roles_route_should_return_429_when_rate_limited() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (user, token) = create_bound_user_and_token(
            &state,
            "Ops Rbac Roles Rate Limited",
            "ops-rbac-roles-rate-limited@acme.org",
            "+8613810000011",
            "ops-rbac-roles-rate-limited-sid",
        )
        .await?;
        let app = get_router(state.clone()).await?;
        let request_id = "ops-rbac-roles-list-rate-limited";

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/debate/ops/rbac/roles")
            .header("Authorization", format!("Bearer {}", token))
            .header("x-request-id", request_id)
            .header("x-test-force-rate-limit", "ops_rbac_roles_list_user")
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::TOO_MANY_REQUESTS);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "rate_limit_exceeded:ops_rbac_roles_list");
        let audit_count: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)::bigint
            FROM ops_rbac_audits
            WHERE event_type = 'roles_list_read'
              AND operator_user_id = $1
              AND decision = 'rate_limited_user'
              AND request_id = $2
            "#,
        )
        .bind(user.id)
        .bind(request_id)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(audit_count, 1);
        Ok(())
    }

    #[tokio::test]
    async fn get_ops_rbac_roles_route_should_return_403_for_unbound_user() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let user = state
            .create_user(&CreateUser {
                fullname: "Ops Rbac Roles Unbound".to_string(),
                email: "ops-rbac-roles-unbound@acme.org".to_string(),
                password: "123456".to_string(),
            })
            .await?;
        let token = issue_token_for_user(&state, user.id, "ops-rbac-roles-unbound-sid").await?;
        let app = get_router(state.clone()).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/debate/ops/rbac/roles")
            .header("Authorization", format!("Bearer {}", token))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::FORBIDDEN);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "auth_phone_bind_required");
        Ok(())
    }

    #[tokio::test]
    async fn get_ops_rbac_roles_route_should_return_409_for_non_owner_user() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "Ops Rbac Roles Non Owner",
            "ops-rbac-roles-non-owner@acme.org",
            "+8613810000012",
            "ops-rbac-roles-non-owner-sid",
        )
        .await?;
        let app = get_router(state.clone()).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/debate/ops/rbac/roles")
            .header("Authorization", format!("Bearer {}", token))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::CONFLICT);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert!(error.error.contains("ops_permission_denied:role_manage"));
        Ok(())
    }

    #[tokio::test]
    async fn get_ops_rbac_roles_route_should_return_500_when_owner_source_missing() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "Ops Rbac Roles Missing Owner Source",
            "ops-rbac-roles-missing-owner-source@acme.org",
            "+8613810000013",
            "ops-rbac-roles-missing-owner-source-sid",
        )
        .await?;
        sqlx::query("DELETE FROM platform_admin_owners WHERE singleton_key = TRUE")
            .execute(&state.pool)
            .await?;
        let app = get_router(state.clone()).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/debate/ops/rbac/roles")
            .header("Authorization", format!("Bearer {}", token))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::INTERNAL_SERVER_ERROR);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "platform_owner_not_configured");
        Ok(())
    }

    #[tokio::test]
    async fn put_ops_rbac_roles_user_id_route_should_return_200_for_owner() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let token = issue_token_for_user(&state, owner.id, "ops-rbac-upsert-owner-sid").await?;
        let app = get_router(state.clone()).await?;
        let request_id = "ops-rbac-upsert-success";

        let req = Request::builder()
            .method(Method::PUT)
            .uri("/api/debate/ops/rbac/roles/2")
            .header("Authorization", format!("Bearer {}", token))
            .header("x-request-id", request_id)
            .header("Content-Type", "application/json")
            .body(Body::from(r#"{"role":"ops_reviewer"}"#))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::OK);
        let revision = res
            .headers()
            .get("x-rbac-revision")
            .and_then(|value| value.to_str().ok())
            .unwrap_or_default()
            .to_string();
        assert!(!revision.is_empty());
        assert_ne!(revision, "empty");
        let body = res.into_body().collect().await?.to_bytes();
        let out: OpsRoleAssignment = serde_json::from_slice(&body)?;
        assert_eq!(out.user_id, 2);
        assert_eq!(out.role, "ops_reviewer");
        let audit_count: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)::bigint
            FROM ops_rbac_audits
            WHERE event_type = 'role_upsert'
              AND operator_user_id = $1
              AND target_user_id = $2
              AND role = $3
              AND decision = 'success'
              AND request_id = $4
            "#,
        )
        .bind(owner.id)
        .bind(2_i64)
        .bind("ops_reviewer")
        .bind(request_id)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(audit_count, 1);
        let outbox_delivered_count: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)::bigint
            FROM ops_rbac_audit_outbox_jobs
            WHERE event_type = 'role_upsert'
              AND operator_user_id = $1
              AND target_user_id = $2
              AND role = $3
              AND decision = 'success'
              AND request_id = $4
              AND delivered_at IS NOT NULL
            "#,
        )
        .bind(owner.id)
        .bind(2_i64)
        .bind("ops_reviewer")
        .bind(request_id)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(outbox_delivered_count, 1);
        Ok(())
    }

    #[tokio::test]
    async fn put_ops_rbac_roles_user_id_route_should_return_200_for_delegated_role_admin(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let (delegated, token) = create_bound_user_and_token(
            &state,
            "Ops Rbac Upsert Delegated",
            "ops-rbac-upsert-delegated@acme.org",
            "+86138100000311",
            "ops-rbac-upsert-delegated-sid",
        )
        .await?;
        let target = state
            .create_user(&CreateUser {
                fullname: "Ops Rbac Upsert Delegated Target".to_string(),
                email: "ops-rbac-upsert-delegated-target@acme.org".to_string(),
                password: "123456".to_string(),
            })
            .await?;
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                delegated.id as u64,
                UpsertOpsRoleInput {
                    role: "platform_role_admin".to_string(),
                },
            )
            .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::PUT)
            .uri(format!("/api/debate/ops/rbac/roles/{}", target.id))
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .body(Body::from(r#"{"role":"ops_reviewer"}"#))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::OK);
        let body = res.into_body().collect().await?.to_bytes();
        let out: OpsRoleAssignment = serde_json::from_slice(&body)?;
        assert_eq!(out.user_id, target.id as u64);
        assert_eq!(out.role, "ops_reviewer");
        Ok(())
    }

    #[tokio::test]
    async fn put_ops_rbac_roles_user_id_route_should_return_400_for_invalid_role() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let token =
            issue_token_for_user(&state, owner.id, "ops-rbac-upsert-invalid-role-sid").await?;
        let app = get_router(state.clone()).await?;

        let req = Request::builder()
            .method(Method::PUT)
            .uri("/api/debate/ops/rbac/roles/2")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .body(Body::from(r#"{"role":"ops_invalid"}"#))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::BAD_REQUEST);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert!(error.error.contains("ops_role_invalid"));
        Ok(())
    }

    #[tokio::test]
    async fn put_ops_rbac_roles_user_id_route_should_return_422_for_invalid_json_and_record_audit(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let token =
            issue_token_for_user(&state, owner.id, "ops-rbac-upsert-invalid-json-sid").await?;
        let app = get_router(state.clone()).await?;
        let request_id = "ops-rbac-upsert-invalid-json";

        let req = Request::builder()
            .method(Method::PUT)
            .uri("/api/debate/ops/rbac/roles/2")
            .header("Authorization", format!("Bearer {}", token))
            .header("x-request-id", request_id)
            .header("Content-Type", "application/json")
            .body(Body::from(r#"{"role":"ops_reviewer""#))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::UNPROCESSABLE_ENTITY);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(
            error.code.as_deref(),
            Some("ops_rbac_roles_write_body_invalid_json")
        );
        let audit_row: (Option<String>, Option<String>) = sqlx::query_as(
            r#"
            SELECT error_code, failure_reason
            FROM ops_rbac_audits
            WHERE event_type = 'role_upsert'
              AND operator_user_id = $1
              AND decision = 'failed'
              AND request_id = $2
            ORDER BY id DESC
            LIMIT 1
            "#,
        )
        .bind(owner.id)
        .bind(request_id)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(
            audit_row.0.as_deref(),
            Some("ops_rbac_roles_write_body_invalid_json")
        );
        assert_eq!(audit_row.1.as_deref(), Some("validation_error"));
        let outbox_row: (Option<String>, Option<String>) = sqlx::query_as(
            r#"
            SELECT error_code, failure_reason
            FROM ops_rbac_audit_outbox_jobs
            WHERE event_type = 'role_upsert'
              AND operator_user_id = $1
              AND decision = 'failed'
              AND request_id = $2
            ORDER BY id DESC
            LIMIT 1
            "#,
        )
        .bind(owner.id)
        .bind(request_id)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(
            outbox_row.0.as_deref(),
            Some("ops_rbac_roles_write_body_invalid_json")
        );
        assert_eq!(outbox_row.1.as_deref(), Some("validation_error"));
        Ok(())
    }

    #[tokio::test]
    async fn put_ops_rbac_roles_user_id_route_should_return_415_without_content_type_and_record_audit(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let token =
            issue_token_for_user(&state, owner.id, "ops-rbac-upsert-missing-content-type-sid")
                .await?;
        let app = get_router(state.clone()).await?;
        let request_id = "ops-rbac-upsert-missing-content-type";

        let req = Request::builder()
            .method(Method::PUT)
            .uri("/api/debate/ops/rbac/roles/2")
            .header("Authorization", format!("Bearer {}", token))
            .header("x-request-id", request_id)
            .body(Body::from(r#"{"role":"ops_reviewer"}"#))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::UNSUPPORTED_MEDIA_TYPE);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(
            error.code.as_deref(),
            Some("ops_rbac_roles_write_content_type_invalid")
        );
        let audit_row: (Option<String>, Option<String>) = sqlx::query_as(
            r#"
            SELECT error_code, failure_reason
            FROM ops_rbac_audits
            WHERE event_type = 'role_upsert'
              AND operator_user_id = $1
              AND decision = 'failed'
              AND request_id = $2
            ORDER BY id DESC
            LIMIT 1
            "#,
        )
        .bind(owner.id)
        .bind(request_id)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(
            audit_row.0.as_deref(),
            Some("ops_rbac_roles_write_content_type_invalid")
        );
        assert_eq!(audit_row.1.as_deref(), Some("validation_error"));
        let outbox_row: (Option<String>, Option<String>) = sqlx::query_as(
            r#"
            SELECT error_code, failure_reason
            FROM ops_rbac_audit_outbox_jobs
            WHERE event_type = 'role_upsert'
              AND operator_user_id = $1
              AND decision = 'failed'
              AND request_id = $2
            ORDER BY id DESC
            LIMIT 1
            "#,
        )
        .bind(owner.id)
        .bind(request_id)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(
            outbox_row.0.as_deref(),
            Some("ops_rbac_roles_write_content_type_invalid")
        );
        assert_eq!(outbox_row.1.as_deref(), Some("validation_error"));
        Ok(())
    }

    #[tokio::test]
    async fn put_ops_rbac_roles_user_id_route_should_return_401_without_token() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::PUT)
            .uri("/api/debate/ops/rbac/roles/2")
            .header("Content-Type", "application/json")
            .body(Body::from(r#"{"role":"ops_reviewer"}"#))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::UNAUTHORIZED);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "auth_access_invalid");
        Ok(())
    }

    #[tokio::test]
    async fn put_ops_rbac_roles_user_id_route_should_return_429_when_rate_limited() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let token =
            issue_token_for_user(&state, owner.id, "ops-rbac-upsert-rate-limited-sid").await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::PUT)
            .uri("/api/debate/ops/rbac/roles/2")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .header("x-test-force-rate-limit", "ops_rbac_roles_write_user")
            .body(Body::from(r#"{"role":"ops_reviewer"}"#))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::TOO_MANY_REQUESTS);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "rate_limit_exceeded:ops_rbac_roles_write");
        Ok(())
    }

    #[tokio::test]
    async fn put_ops_rbac_roles_user_id_route_should_return_429_when_ip_rate_limited() -> Result<()>
    {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let token =
            issue_token_for_user(&state, owner.id, "ops-rbac-upsert-ip-rate-limited-sid").await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::PUT)
            .uri("/api/debate/ops/rbac/roles/2")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .header("x-real-ip", "127.0.0.1")
            .header("x-test-force-rate-limit", "ops_rbac_roles_write_ip")
            .body(Body::from(r#"{"role":"ops_reviewer"}"#))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::TOO_MANY_REQUESTS);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "rate_limit_exceeded:ops_rbac_roles_write");
        Ok(())
    }

    #[tokio::test]
    async fn put_ops_rbac_roles_user_id_route_should_return_500_when_owner_source_missing(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let token =
            issue_token_for_user(&state, owner.id, "ops-rbac-upsert-owner-source-missing-sid")
                .await?;
        sqlx::query("DELETE FROM platform_admin_owners WHERE singleton_key = TRUE")
            .execute(&state.pool)
            .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::PUT)
            .uri("/api/debate/ops/rbac/roles/2")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .body(Body::from(r#"{"role":"ops_reviewer"}"#))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::INTERNAL_SERVER_ERROR);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "platform_owner_not_configured");
        Ok(())
    }

    #[tokio::test]
    async fn put_ops_rbac_roles_user_id_route_should_return_400_for_user_id_out_of_range(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let token =
            issue_token_for_user(&state, owner.id, "ops-rbac-upsert-out-of-range-sid").await?;
        let app = get_router(state).await?;
        let overflow_user_id = (i64::MAX as u128 + 1).to_string();

        let req = Request::builder()
            .method(Method::PUT)
            .uri(format!("/api/debate/ops/rbac/roles/{overflow_user_id}"))
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .body(Body::from(r#"{"role":"ops_reviewer"}"#))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::BAD_REQUEST);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(
            error.code.as_deref(),
            Some("ops_role_target_user_id_out_of_range")
        );
        Ok(())
    }

    #[tokio::test]
    async fn put_ops_rbac_roles_user_id_route_should_replay_with_idempotency_key() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let token =
            issue_token_for_user(&state, owner.id, "ops-rbac-upsert-idempotency-sid").await?;
        let app = get_router(state.clone()).await?;

        let req1 = Request::builder()
            .method(Method::PUT)
            .uri("/api/debate/ops/rbac/roles/2")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .header("idempotency-key", "ops-rbac-upsert-route-key-1")
            .body(Body::from(r#"{"role":"ops_reviewer"}"#))?;
        let res1 = app.clone().oneshot(req1).await?;
        assert_eq!(res1.status(), StatusCode::OK);
        let body1 = res1.into_body().collect().await?.to_bytes();
        let out1: OpsRoleAssignment = serde_json::from_slice(&body1)?;

        let req2 = Request::builder()
            .method(Method::PUT)
            .uri("/api/debate/ops/rbac/roles/2")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .header("idempotency-key", "ops-rbac-upsert-route-key-1")
            .body(Body::from(r#"{"role":"ops_reviewer"}"#))?;
        let res2 = app.oneshot(req2).await?;
        assert_eq!(res2.status(), StatusCode::OK);
        let body2 = res2.into_body().collect().await?.to_bytes();
        let out2: OpsRoleAssignment = serde_json::from_slice(&body2)?;
        assert_eq!(out1.user_id, out2.user_id);
        assert_eq!(out1.role, out2.role);
        assert_eq!(out1.updated_at, out2.updated_at);

        let audit_count: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)::bigint
            FROM ops_rbac_audits
            WHERE event_type = 'role_upsert'
              AND operator_user_id = $1
              AND target_user_id = $2
              AND decision = 'success'
            "#,
        )
        .bind(owner.id)
        .bind(2_i64)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(audit_count, 1);
        Ok(())
    }

    #[tokio::test]
    async fn put_ops_rbac_roles_user_id_route_should_reject_too_long_idempotency_key() -> Result<()>
    {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let token =
            issue_token_for_user(&state, owner.id, "ops-rbac-upsert-idempotency-long-sid").await?;
        let app = get_router(state).await?;
        let long_key = "k".repeat(161);

        let req = Request::builder()
            .method(Method::PUT)
            .uri("/api/debate/ops/rbac/roles/2")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .header("idempotency-key", long_key)
            .body(Body::from(r#"{"role":"ops_reviewer"}"#))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::BAD_REQUEST);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(
            error.code.as_deref(),
            Some("ops_rbac_roles_write_idempotency_key_too_long")
        );
        Ok(())
    }

    #[tokio::test]
    async fn put_ops_rbac_roles_user_id_route_should_rate_limit_with_local_fallback_when_redis_disabled(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let token =
            issue_token_for_user(&state, owner.id, "ops-rbac-upsert-local-fallback-sid").await?;
        let app = get_router(state).await?;

        for _ in 0..30 {
            let req = Request::builder()
                .method(Method::PUT)
                .uri("/api/debate/ops/rbac/roles/2")
                .header("Authorization", format!("Bearer {}", token))
                .header("Content-Type", "application/json")
                .body(Body::from(r#"{"role":"ops_reviewer"}"#))?;
            let res = app.clone().oneshot(req).await?;
            assert_eq!(res.status(), StatusCode::OK);
        }

        let req = Request::builder()
            .method(Method::PUT)
            .uri("/api/debate/ops/rbac/roles/2")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .body(Body::from(r#"{"role":"ops_reviewer"}"#))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::TOO_MANY_REQUESTS);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "rate_limit_exceeded:ops_rbac_roles_write");
        Ok(())
    }

    #[tokio::test]
    async fn put_ops_rbac_roles_user_id_route_should_return_403_for_unbound_user() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let user = state
            .create_user(&CreateUser {
                fullname: "Ops Rbac Upsert Unbound".to_string(),
                email: "ops-rbac-upsert-unbound@acme.org".to_string(),
                password: "123456".to_string(),
            })
            .await?;
        let token = issue_token_for_user(&state, user.id, "ops-rbac-upsert-unbound-sid").await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::PUT)
            .uri("/api/debate/ops/rbac/roles/2")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .body(Body::from(r#"{"role":"ops_reviewer"}"#))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::FORBIDDEN);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "auth_phone_bind_required");
        Ok(())
    }

    #[tokio::test]
    async fn put_ops_rbac_roles_user_id_route_should_return_409_for_non_owner() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (user, token) = create_bound_user_and_token(
            &state,
            "Ops Rbac Upsert Non Owner",
            "ops-rbac-upsert-non-owner@acme.org",
            "+8613810000031",
            "ops-rbac-upsert-non-owner-sid",
        )
        .await?;
        let app = get_router(state.clone()).await?;
        let request_id = "ops-rbac-upsert-non-owner-failure";

        let req = Request::builder()
            .method(Method::PUT)
            .uri("/api/debate/ops/rbac/roles/2")
            .header("Authorization", format!("Bearer {}", token))
            .header("x-request-id", request_id)
            .header("Content-Type", "application/json")
            .body(Body::from(r#"{"role":"ops_reviewer"}"#))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::CONFLICT);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert!(error.error.contains("ops_permission_denied:role_manage"));
        let audit_row: (Option<String>, Option<String>) = sqlx::query_as(
            r#"
            SELECT error_code, failure_reason
            FROM ops_rbac_audits
            WHERE event_type = 'role_upsert'
              AND operator_user_id = $1
              AND decision = 'failed'
              AND request_id = $2
            ORDER BY id DESC
            LIMIT 1
            "#,
        )
        .bind(user.id)
        .bind(request_id)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(audit_row.1.as_deref(), Some("permission_denied"));
        assert!(audit_row
            .0
            .as_deref()
            .unwrap_or_default()
            .contains("ops_permission_denied:role_manage"));
        let outbox_row: (Option<String>, Option<String>) = sqlx::query_as(
            r#"
            SELECT error_code, failure_reason
            FROM ops_rbac_audit_outbox_jobs
            WHERE event_type = 'role_upsert'
              AND operator_user_id = $1
              AND decision = 'failed'
              AND request_id = $2
            ORDER BY id DESC
            LIMIT 1
            "#,
        )
        .bind(user.id)
        .bind(request_id)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(outbox_row.1.as_deref(), Some("permission_denied"));
        assert!(outbox_row
            .0
            .as_deref()
            .unwrap_or_default()
            .contains("ops_permission_denied:role_manage"));
        Ok(())
    }

    #[tokio::test]
    async fn put_ops_rbac_roles_user_id_route_should_return_409_when_delegated_manage_owner_or_role_admin(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let (delegated, token) = create_bound_user_and_token(
            &state,
            "Ops Rbac Upsert Delegated Guard",
            "ops-rbac-upsert-delegated-guard@acme.org",
            "+86138100000312",
            "ops-rbac-upsert-delegated-guard-sid",
        )
        .await?;
        let target = state
            .create_user(&CreateUser {
                fullname: "Ops Rbac Upsert Delegated Guard Target".to_string(),
                email: "ops-rbac-upsert-delegated-guard-target@acme.org".to_string(),
                password: "123456".to_string(),
            })
            .await?;
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                delegated.id as u64,
                UpsertOpsRoleInput {
                    role: "platform_role_admin".to_string(),
                },
            )
            .await?;
        let app = get_router(state).await?;

        let req_owner = Request::builder()
            .method(Method::PUT)
            .uri(format!("/api/debate/ops/rbac/roles/{}", owner.id))
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .body(Body::from(r#"{"role":"ops_viewer"}"#))?;
        let res_owner = app.clone().oneshot(req_owner).await?;
        assert_eq!(res_owner.status(), StatusCode::CONFLICT);
        let body_owner = res_owner.into_body().collect().await?.to_bytes();
        let owner_error: ErrorOutput = serde_json::from_slice(&body_owner)?;
        assert!(owner_error
            .error
            .contains("delegated_role_admin_cannot_manage_owner"));

        let req_role_admin = Request::builder()
            .method(Method::PUT)
            .uri(format!("/api/debate/ops/rbac/roles/{}", target.id))
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .body(Body::from(r#"{"role":"platform_role_admin"}"#))?;
        let res_role_admin = app.oneshot(req_role_admin).await?;
        assert_eq!(res_role_admin.status(), StatusCode::CONFLICT);
        let body_role_admin = res_role_admin.into_body().collect().await?.to_bytes();
        let role_admin_error: ErrorOutput = serde_json::from_slice(&body_role_admin)?;
        assert!(role_admin_error
            .error
            .contains("delegated_role_admin_cannot_manage_role_admin"));
        Ok(())
    }

    #[tokio::test]
    async fn put_ops_rbac_roles_user_id_route_should_return_404_for_missing_target_user(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let token = issue_token_for_user(&state, owner.id, "ops-rbac-upsert-not-found-sid").await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::PUT)
            .uri("/api/debate/ops/rbac/roles/999999")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .body(Body::from(r#"{"role":"ops_reviewer"}"#))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::NOT_FOUND);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert!(error.error.contains("ops_role_target_user_not_found"));
        Ok(())
    }

    #[tokio::test]
    async fn delete_ops_rbac_roles_user_id_route_should_return_200_for_owner() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                2,
                UpsertOpsRoleInput {
                    role: "ops_reviewer".to_string(),
                },
            )
            .await?;
        let token = issue_token_for_user(&state, owner.id, "ops-rbac-revoke-owner-sid").await?;
        let app = get_router(state.clone()).await?;
        let request_id = "ops-rbac-revoke-success";

        let req = Request::builder()
            .method(Method::DELETE)
            .uri("/api/debate/ops/rbac/roles/2")
            .header("Authorization", format!("Bearer {}", token))
            .header("x-request-id", request_id)
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::OK);
        let body = res.into_body().collect().await?.to_bytes();
        let out: RevokeOpsRoleOutput = serde_json::from_slice(&body)?;
        assert_eq!(out.user_id, 2);
        assert!(out.removed);
        let audit_count: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)::bigint
            FROM ops_rbac_audits
            WHERE event_type = 'role_revoke'
              AND operator_user_id = $1
              AND target_user_id = $2
              AND decision = 'success'
              AND removed = TRUE
              AND request_id = $3
            "#,
        )
        .bind(owner.id)
        .bind(2_i64)
        .bind(request_id)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(audit_count, 1);
        Ok(())
    }

    #[tokio::test]
    async fn delete_ops_rbac_roles_user_id_route_should_return_200_for_delegated_role_admin(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let (delegated, token) = create_bound_user_and_token(
            &state,
            "Ops Rbac Revoke Delegated",
            "ops-rbac-revoke-delegated@acme.org",
            "+86138100000321",
            "ops-rbac-revoke-delegated-sid",
        )
        .await?;
        let target = state
            .create_user(&CreateUser {
                fullname: "Ops Rbac Revoke Delegated Target".to_string(),
                email: "ops-rbac-revoke-delegated-target@acme.org".to_string(),
                password: "123456".to_string(),
            })
            .await?;
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                delegated.id as u64,
                UpsertOpsRoleInput {
                    role: "platform_role_admin".to_string(),
                },
            )
            .await?;
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                target.id as u64,
                UpsertOpsRoleInput {
                    role: "ops_reviewer".to_string(),
                },
            )
            .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::DELETE)
            .uri(format!("/api/debate/ops/rbac/roles/{}", target.id))
            .header("Authorization", format!("Bearer {}", token))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::OK);
        let body = res.into_body().collect().await?.to_bytes();
        let out: RevokeOpsRoleOutput = serde_json::from_slice(&body)?;
        assert_eq!(out.user_id, target.id as u64);
        assert!(out.removed);
        Ok(())
    }

    #[tokio::test]
    async fn delete_ops_rbac_roles_user_id_route_should_return_409_for_non_owner() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "Ops Rbac Revoke Non Owner",
            "ops-rbac-revoke-non-owner@acme.org",
            "+8613810000032",
            "ops-rbac-revoke-non-owner-sid",
        )
        .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::DELETE)
            .uri("/api/debate/ops/rbac/roles/2")
            .header("Authorization", format!("Bearer {}", token))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::CONFLICT);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert!(error.error.contains("ops_permission_denied:role_manage"));
        Ok(())
    }

    #[tokio::test]
    async fn delete_ops_rbac_roles_user_id_route_should_return_409_when_delegated_revoke_role_admin(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let (delegated, token) = create_bound_user_and_token(
            &state,
            "Ops Rbac Revoke Delegated Guard",
            "ops-rbac-revoke-delegated-guard@acme.org",
            "+86138100000322",
            "ops-rbac-revoke-delegated-guard-sid",
        )
        .await?;
        let target = state
            .create_user(&CreateUser {
                fullname: "Ops Rbac Revoke Delegated Guard Target".to_string(),
                email: "ops-rbac-revoke-delegated-guard-target@acme.org".to_string(),
                password: "123456".to_string(),
            })
            .await?;
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                delegated.id as u64,
                UpsertOpsRoleInput {
                    role: "platform_role_admin".to_string(),
                },
            )
            .await?;
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                target.id as u64,
                UpsertOpsRoleInput {
                    role: "platform_role_admin".to_string(),
                },
            )
            .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::DELETE)
            .uri(format!("/api/debate/ops/rbac/roles/{}", target.id))
            .header("Authorization", format!("Bearer {}", token))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::CONFLICT);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert!(error
            .error
            .contains("delegated_role_admin_cannot_manage_role_admin"));
        Ok(())
    }

    #[tokio::test]
    async fn delete_ops_rbac_roles_user_id_route_should_return_429_when_rate_limited() -> Result<()>
    {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let token =
            issue_token_for_user(&state, owner.id, "ops-rbac-revoke-rate-limited-sid").await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::DELETE)
            .uri("/api/debate/ops/rbac/roles/2")
            .header("Authorization", format!("Bearer {}", token))
            .header("x-test-force-rate-limit", "ops_rbac_roles_write_user")
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::TOO_MANY_REQUESTS);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "rate_limit_exceeded:ops_rbac_roles_write");
        Ok(())
    }

    #[tokio::test]
    async fn create_debate_topic_ops_route_should_replay_with_idempotency_key() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let (ops_admin, token) = create_bound_user_and_token(
            &state,
            "Ops Topic Replay",
            "ops-topic-replay@acme.org",
            "+8613800995555",
            "ops-topic-replay-sid",
        )
        .await?;
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                ops_admin.id as u64,
                UpsertOpsRoleInput {
                    role: "ops_admin".to_string(),
                },
            )
            .await?;
        let app = get_router(state.clone()).await?;

        let payload = r#"{
            "title":"ops-topic-idempotency",
            "description":"topic-create-idempotency",
            "category":"Technology",
            "stancePro":"pro",
            "stanceCon":"con",
            "contextSeed":"seed",
            "isActive":true
        }"#;

        let req1 = Request::builder()
            .method(Method::POST)
            .uri("/api/debate/ops/topics")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .header("idempotency-key", "ops-topic-route-key-1")
            .body(Body::from(payload.to_string()))?;
        let res1 = app.clone().oneshot(req1).await?;
        assert_eq!(res1.status(), StatusCode::CREATED);
        let body1 = res1.into_body().collect().await?.to_bytes();
        let first: DebateTopic = serde_json::from_slice(&body1)?;

        let req2 = Request::builder()
            .method(Method::POST)
            .uri("/api/debate/ops/topics")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .header("idempotency-key", "ops-topic-route-key-1")
            .body(Body::from(payload.to_string()))?;
        let res2 = app.oneshot(req2).await?;
        assert_eq!(res2.status(), StatusCode::CREATED);
        let body2 = res2.into_body().collect().await?.to_bytes();
        let second: DebateTopic = serde_json::from_slice(&body2)?;
        assert_eq!(first.id, second.id);

        let audit_count: i64 = sqlx::query_scalar(
            "SELECT COUNT(1)::bigint FROM ops_debate_topic_audits WHERE topic_id = $1",
        )
        .bind(first.id)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(audit_count, 2);
        Ok(())
    }

    #[tokio::test]
    async fn create_debate_topic_ops_route_should_reject_too_long_idempotency_key() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let (ops_admin, token) = create_bound_user_and_token(
            &state,
            "Ops Topic Idem Too Long",
            "ops-topic-idem-too-long@acme.org",
            "+8613800996666",
            "ops-topic-idem-too-long-sid",
        )
        .await?;
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                ops_admin.id as u64,
                UpsertOpsRoleInput {
                    role: "ops_admin".to_string(),
                },
            )
            .await?;
        let app = get_router(state).await?;
        let long_key = "k".repeat(161);
        let payload = r#"{
            "title":"ops-topic",
            "description":"desc",
            "category":"Technology",
            "stancePro":"pro",
            "stanceCon":"con",
            "isActive":true
        }"#;

        let req = Request::builder()
            .method(Method::POST)
            .uri("/api/debate/ops/topics")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .header("idempotency-key", long_key)
            .body(Body::from(payload.to_string()))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::BAD_REQUEST);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(
            error.error,
            "ops_debate_topic_create_idempotency_key_too_long"
        );
        Ok(())
    }

    #[tokio::test]
    async fn create_debate_topic_ops_route_should_reject_too_long_context_seed() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let (ops_admin, token) = create_bound_user_and_token(
            &state,
            "Ops Topic Context",
            "ops-topic-context@acme.org",
            "+8613800997777",
            "ops-topic-context-sid",
        )
        .await?;
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                ops_admin.id as u64,
                UpsertOpsRoleInput {
                    role: "ops_admin".to_string(),
                },
            )
            .await?;
        let app = get_router(state).await?;

        let too_long_context_seed = "a".repeat(8001);
        let payload = serde_json::json!({
            "title": "ops-topic-context-seed",
            "description": "desc",
            "category": "Technology",
            "stancePro": "pro",
            "stanceCon": "con",
            "contextSeed": too_long_context_seed,
            "isActive": true
        });

        let req = Request::builder()
            .method(Method::POST)
            .uri("/api/debate/ops/topics")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .body(Body::from(serde_json::to_vec(&payload)?))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::BAD_REQUEST);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "debate_topic_context_seed_too_long");
        Ok(())
    }

    #[tokio::test]
    async fn create_debate_topic_ops_route_should_reject_invalid_category() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let (ops_admin, token) = create_bound_user_and_token(
            &state,
            "Ops Topic Invalid Category",
            "ops-topic-invalid-category@acme.org",
            "+8613800998888",
            "ops-topic-invalid-category-sid",
        )
        .await?;
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                ops_admin.id as u64,
                UpsertOpsRoleInput {
                    role: "ops_admin".to_string(),
                },
            )
            .await?;
        let app = get_router(state).await?;
        let payload = r#"{
            "title":"ops-topic-invalid-category",
            "description":"desc",
            "category":"unknown",
            "stancePro":"pro",
            "stanceCon":"con",
            "isActive":true
        }"#;

        let req = Request::builder()
            .method(Method::POST)
            .uri("/api/debate/ops/topics")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .body(Body::from(payload.to_string()))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::BAD_REQUEST);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "debate_topic_category_invalid");
        Ok(())
    }

    #[tokio::test]
    async fn create_debate_topic_ops_route_should_reject_normalized_duplicate_title_in_same_category(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let (ops_admin, token) = create_bound_user_and_token(
            &state,
            "Ops Topic Duplicate",
            "ops-topic-duplicate@acme.org",
            "+8613800999999",
            "ops-topic-duplicate-sid",
        )
        .await?;
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                ops_admin.id as u64,
                UpsertOpsRoleInput {
                    role: "ops_admin".to_string(),
                },
            )
            .await?;
        let app = get_router(state).await?;
        let payload = r#"{
            "title":"AI 是否取代人类工作",
            "description":"desc",
            "category":"Technology",
            "stancePro":"pro",
            "stanceCon":"con",
            "isActive":true
        }"#;

        let req1 = Request::builder()
            .method(Method::POST)
            .uri("/api/debate/ops/topics")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .body(Body::from(payload.to_string()))?;
        let res1 = app.clone().oneshot(req1).await?;
        assert_eq!(res1.status(), StatusCode::CREATED);

        let payload2 = r#"{
            "title":"  ai 是否取代人类工作  ",
            "description":"desc-2",
            "category":" technology ",
            "stancePro":"pro",
            "stanceCon":"con",
            "isActive":true
        }"#;

        let req2 = Request::builder()
            .method(Method::POST)
            .uri("/api/debate/ops/topics")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .body(Body::from(payload2.to_string()))?;
        let res2 = app.oneshot(req2).await?;
        assert_eq!(res2.status(), StatusCode::CONFLICT);
        let body = res2.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(
            error.error,
            "debate conflict: debate_topic_duplicate_title_in_category"
        );
        Ok(())
    }

    #[tokio::test]
    async fn create_debate_session_ops_route_should_replay_with_idempotency_key() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let (ops_admin, token) = create_bound_user_and_token(
            &state,
            "Ops Session Replay",
            "ops-session-replay@acme.org",
            "+8613810001111",
            "ops-session-replay-sid",
        )
        .await?;
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                ops_admin.id as u64,
                UpsertOpsRoleInput {
                    role: "ops_admin".to_string(),
                },
            )
            .await?;
        let topic_id = seed_topic(&state).await?;
        let app = get_router(state.clone()).await?;
        let now = Utc::now();
        let payload = serde_json::json!({
            "topicId": topic_id,
            "status": "scheduled",
            "scheduledStartAt": (now + Duration::minutes(10)).to_rfc3339(),
            "endAt": (now + Duration::minutes(60)).to_rfc3339(),
            "maxParticipantsPerSide": 120
        });

        let req1 = Request::builder()
            .method(Method::POST)
            .uri("/api/debate/ops/sessions")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .header("idempotency-key", "ops-session-route-key-1")
            .body(Body::from(serde_json::to_vec(&payload)?))?;
        let res1 = app.clone().oneshot(req1).await?;
        assert_eq!(res1.status(), StatusCode::CREATED);
        let body1 = res1.into_body().collect().await?.to_bytes();
        let first: DebateSessionSummary = serde_json::from_slice(&body1)?;

        let req2 = Request::builder()
            .method(Method::POST)
            .uri("/api/debate/ops/sessions")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .header("idempotency-key", "ops-session-route-key-1")
            .body(Body::from(serde_json::to_vec(&payload)?))?;
        let res2 = app.oneshot(req2).await?;
        assert_eq!(res2.status(), StatusCode::CREATED);
        let body2 = res2.into_body().collect().await?.to_bytes();
        let second: DebateSessionSummary = serde_json::from_slice(&body2)?;
        assert_eq!(first.id, second.id);

        let audit_count: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)::bigint
            FROM ops_debate_session_audits
            WHERE session_id = $1
            "#,
        )
        .bind(first.id)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(audit_count, 2);
        Ok(())
    }

    #[tokio::test]
    async fn create_debate_session_ops_route_should_reject_too_long_idempotency_key() -> Result<()>
    {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let (ops_admin, token) = create_bound_user_and_token(
            &state,
            "Ops Session Key Long",
            "ops-session-key-long@acme.org",
            "+8613810002222",
            "ops-session-key-long-sid",
        )
        .await?;
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                ops_admin.id as u64,
                UpsertOpsRoleInput {
                    role: "ops_admin".to_string(),
                },
            )
            .await?;
        let topic_id = seed_topic(&state).await?;
        let app = get_router(state).await?;
        let now = Utc::now();
        let payload = serde_json::json!({
            "topicId": topic_id,
            "status": "scheduled",
            "scheduledStartAt": (now + Duration::minutes(10)).to_rfc3339(),
            "endAt": (now + Duration::minutes(60)).to_rfc3339(),
            "maxParticipantsPerSide": 50
        });

        let req = Request::builder()
            .method(Method::POST)
            .uri("/api/debate/ops/sessions")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .header("idempotency-key", "k".repeat(161))
            .body(Body::from(serde_json::to_vec(&payload)?))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::BAD_REQUEST);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(
            error.error,
            "ops_debate_session_create_idempotency_key_too_long"
        );
        Ok(())
    }

    #[tokio::test]
    async fn create_debate_session_ops_route_should_reject_past_end_at() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let (ops_admin, token) = create_bound_user_and_token(
            &state,
            "Ops Session Expired",
            "ops-session-expired@acme.org",
            "+8613810003333",
            "ops-session-expired-sid",
        )
        .await?;
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                ops_admin.id as u64,
                UpsertOpsRoleInput {
                    role: "ops_admin".to_string(),
                },
            )
            .await?;
        let topic_id = seed_topic(&state).await?;
        let app = get_router(state).await?;
        let now = Utc::now();
        let payload = serde_json::json!({
            "topicId": topic_id,
            "status": "scheduled",
            "scheduledStartAt": (now - Duration::minutes(120)).to_rfc3339(),
            "endAt": (now - Duration::minutes(10)).to_rfc3339(),
            "maxParticipantsPerSide": 30
        });

        let req = Request::builder()
            .method(Method::POST)
            .uri("/api/debate/ops/sessions")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .body(Body::from(serde_json::to_vec(&payload)?))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::BAD_REQUEST);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(
            error.error,
            "debate error: session endAt must be in the future"
        );
        Ok(())
    }

    #[tokio::test]
    async fn update_debate_session_ops_route_should_update_successfully() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let (ops_admin, token) = create_bound_user_and_token(
            &state,
            "Ops Session Update",
            "ops-session-update@acme.org",
            "+8613810004444",
            "ops-session-update-sid",
        )
        .await?;
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                ops_admin.id as u64,
                UpsertOpsRoleInput {
                    role: "ops_admin".to_string(),
                },
            )
            .await?;
        let (_topic_id, session_id) = seed_topic_and_session(&state).await?;
        let current_updated_at: chrono::DateTime<Utc> =
            sqlx::query_scalar("SELECT updated_at FROM debate_sessions WHERE id = $1")
                .bind(session_id)
                .fetch_one(&state.pool)
                .await?;
        let app = get_router(state).await?;
        let now = Utc::now();
        let payload = serde_json::json!({
            "status": "open",
            "scheduledStartAt": (now - Duration::minutes(2)).to_rfc3339(),
            "endAt": (now + Duration::minutes(30)).to_rfc3339(),
            "maxParticipantsPerSide": 140,
            "expectedUpdatedAt": current_updated_at.to_rfc3339()
        });

        let req = Request::builder()
            .method(Method::PUT)
            .uri(format!("/api/debate/ops/sessions/{}", session_id))
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .body(Body::from(serde_json::to_vec(&payload)?))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::OK);
        assert!(res.headers().contains_key("x-ratelimit-limit"));
        assert!(res.headers().contains_key("x-ratelimit-remaining"));
        assert!(res.headers().contains_key("x-ratelimit-reset"));
        let body = res.into_body().collect().await?.to_bytes();
        let updated: DebateSessionSummary = serde_json::from_slice(&body)?;
        assert_eq!(updated.id, session_id);
        assert_eq!(updated.status, "open");
        assert_eq!(updated.max_participants_per_side, 140);
        Ok(())
    }

    #[tokio::test]
    async fn update_debate_session_ops_route_should_reject_revision_conflict() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let (ops_admin, token) = create_bound_user_and_token(
            &state,
            "Ops Session Revision",
            "ops-session-revision@acme.org",
            "+8613810005555",
            "ops-session-revision-sid",
        )
        .await?;
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                ops_admin.id as u64,
                UpsertOpsRoleInput {
                    role: "ops_admin".to_string(),
                },
            )
            .await?;
        let (_topic_id, session_id) = seed_topic_and_session(&state).await?;
        let app = get_router(state).await?;
        let now = Utc::now();
        let payload = serde_json::json!({
            "status": "open",
            "scheduledStartAt": (now - Duration::minutes(2)).to_rfc3339(),
            "endAt": (now + Duration::minutes(40)).to_rfc3339(),
            "maxParticipantsPerSide": 140,
            "expectedUpdatedAt": (now - Duration::days(1)).to_rfc3339()
        });

        let req = Request::builder()
            .method(Method::PUT)
            .uri(format!("/api/debate/ops/sessions/{}", session_id))
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .body(Body::from(serde_json::to_vec(&payload)?))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::CONFLICT);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(
            error.error,
            "debate conflict: debate_session_revision_conflict"
        );
        Ok(())
    }

    #[tokio::test]
    async fn update_debate_session_ops_route_should_return_429_when_user_rate_limited() -> Result<()>
    {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let (ops_admin, token) = create_bound_user_and_token(
            &state,
            "Ops Session Ratelimit",
            "ops-session-ratelimit@acme.org",
            "+8613810006666",
            "ops-session-ratelimit-sid",
        )
        .await?;
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                ops_admin.id as u64,
                UpsertOpsRoleInput {
                    role: "ops_admin".to_string(),
                },
            )
            .await?;
        let (_topic_id, session_id) = seed_topic_and_session(&state).await?;
        let app = get_router(state).await?;
        let now = Utc::now();
        let payload = serde_json::json!({
            "status": "open",
            "scheduledStartAt": (now - Duration::minutes(2)).to_rfc3339(),
            "endAt": (now + Duration::minutes(40)).to_rfc3339(),
            "maxParticipantsPerSide": 140
        });

        let req = Request::builder()
            .method(Method::PUT)
            .uri(format!("/api/debate/ops/sessions/{}", session_id))
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .header("x-test-force-rate-limit", "user")
            .body(Body::from(serde_json::to_vec(&payload)?))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::TOO_MANY_REQUESTS);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "rate_limit_exceeded:ops_debate_session_update");
        Ok(())
    }
}
