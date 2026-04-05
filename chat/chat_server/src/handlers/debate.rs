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
    use crate::{get_router, models::CreateUser, ErrorOutput, UpsertOpsRoleInput};
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
        let app = get_router(state).await?;

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
        let app = get_router(state).await?;

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
        let app = get_router(state).await?;

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
        let app = get_router(state).await?;

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
}
