use crate::{
    application::request_guard::{
        build_rate_limit_headers, enforce_rate_limit, rate_limit_exceeded_response,
    },
    AppError, AppState,
};
use axum::{
    extract::State,
    http::{HeaderMap, StatusCode},
    response::{IntoResponse, Response},
    Extension, Json,
};
use chat_core::{middlewares::AuthContext, User};
use serde::{Deserialize, Serialize};
use std::{
    collections::hash_map::DefaultHasher,
    env,
    hash::{Hash, Hasher},
    sync::atomic::{AtomicU64, Ordering},
};
use utoipa::ToSchema;
use uuid::Uuid;

const ACCESS_TICKET_TTL_SECS_DEFAULT: u64 = 60 * 10;
const ACCESS_TICKET_FILE_TTL_SECS_MIN: u64 = 60;
const ACCESS_TICKET_FILE_TTL_SECS_MAX: u64 = 60 * 60;
const ACCESS_TICKET_NOTIFY_TTL_SECS_MIN: u64 = 60;
const ACCESS_TICKET_NOTIFY_TTL_SECS_MAX: u64 = 30 * 60;
const ACCESS_TICKET_NOTIFY_TTL_SECS_DEFAULT: u64 = 5 * 60;
const ACCESS_TICKETS_RATE_LIMIT_WINDOW_SECS: u64 = 60;
const ACCESS_TICKETS_RATE_LIMIT_USER_PER_WINDOW_DEFAULT: u64 = 30;
const ACCESS_TICKETS_RATE_LIMIT_IP_PER_WINDOW_DEFAULT: u64 = 120;

#[derive(Debug, Default)]
struct AccessTicketIssueMetrics {
    requests_total: AtomicU64,
    success_total: AtomicU64,
    failed_total: AtomicU64,
    rate_limited_total: AtomicU64,
}

impl AccessTicketIssueMetrics {
    fn observe_request(&self) {
        self.requests_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_success(&self) {
        self.success_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_failed(&self) {
        self.failed_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_rate_limited(&self) {
        self.rate_limited_total.fetch_add(1, Ordering::Relaxed);
    }

    fn snapshot(&self) -> (u64, u64, u64, u64) {
        (
            self.requests_total.load(Ordering::Relaxed),
            self.success_total.load(Ordering::Relaxed),
            self.failed_total.load(Ordering::Relaxed),
            self.rate_limited_total.load(Ordering::Relaxed),
        )
    }
}

static ACCESS_TICKET_ISSUE_METRICS: AccessTicketIssueMetrics = AccessTicketIssueMetrics {
    requests_total: AtomicU64::new(0),
    success_total: AtomicU64::new(0),
    failed_total: AtomicU64::new(0),
    rate_limited_total: AtomicU64::new(0),
};

#[derive(Debug, Serialize, ToSchema, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AccessTicketsOutput {
    file_token: String,
    notify_token: String,
    expires_in_secs: u64,
}

#[utoipa::path(
    post,
    path = "/api/tickets",
    responses(
        (status = 200, description = "Issue short-lived access tickets", body = AccessTicketsOutput),
        (status = 401, description = "Auth error", body = crate::ErrorOutput),
        (status = 403, description = "Phone not bound", body = crate::ErrorOutput),
        (status = 429, description = "Rate limited", body = crate::ErrorOutput),
        (status = 500, description = "Ticket issue failed", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn create_access_tickets_handler(
    Extension(auth_ctx): Extension<AuthContext>,
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Response, AppError> {
    ACCESS_TICKET_ISSUE_METRICS.observe_request();
    let user_limit = load_env_u64(
        "CHAT_TICKETS_RATE_LIMIT_USER_PER_MINUTE",
        ACCESS_TICKETS_RATE_LIMIT_USER_PER_WINDOW_DEFAULT,
        1,
        10_000,
    );
    let ip_limit = load_env_u64(
        "CHAT_TICKETS_RATE_LIMIT_IP_PER_MINUTE",
        ACCESS_TICKETS_RATE_LIMIT_IP_PER_WINDOW_DEFAULT,
        1,
        50_000,
    );
    let user_key = user.id.to_string();
    let user_decision = enforce_rate_limit(
        &state,
        "tickets_issue_user",
        &user_key,
        user_limit,
        ACCESS_TICKETS_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    let user_headers = build_rate_limit_headers(&user_decision)?;
    if !user_decision.allowed {
        ACCESS_TICKET_ISSUE_METRICS.observe_rate_limited();
        tracing::warn!(
            user_id = user.id,
            decision = "rate_limited_user",
            "issue tickets blocked"
        );
        return Ok(rate_limit_exceeded_response("tickets_issue", user_headers));
    }

    let ip_key =
        request_rate_limit_ip_key_from_headers(&headers).unwrap_or_else(|| "unknown".to_string());
    let ip_decision = enforce_rate_limit(
        &state,
        "tickets_issue_ip",
        &ip_key,
        ip_limit,
        ACCESS_TICKETS_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    if !ip_decision.allowed {
        ACCESS_TICKET_ISSUE_METRICS.observe_rate_limited();
        tracing::warn!(
            user_id = user.id,
            decision = "rate_limited_ip",
            "issue tickets blocked"
        );
        return Ok(rate_limit_exceeded_response(
            "tickets_issue",
            build_rate_limit_headers(&ip_decision)?,
        ));
    }

    let file_ttl_secs = load_env_u64(
        "CHAT_FILE_TICKET_TTL_SECS",
        ACCESS_TICKET_TTL_SECS_DEFAULT,
        ACCESS_TICKET_FILE_TTL_SECS_MIN,
        ACCESS_TICKET_FILE_TTL_SECS_MAX,
    );
    let notify_ttl_secs = load_env_u64(
        "CHAT_NOTIFY_TICKET_TTL_SECS",
        ACCESS_TICKET_NOTIFY_TTL_SECS_DEFAULT,
        ACCESS_TICKET_NOTIFY_TTL_SECS_MIN,
        ACCESS_TICKET_NOTIFY_TTL_SECS_MAX,
    );
    let file_jti = Uuid::now_v7().to_string();
    let notify_jti = Uuid::now_v7().to_string();
    let file_token = state
        .ek
        .sign_file_ticket_with_session(
            user.id,
            auth_ctx.sid.clone(),
            auth_ctx.ver,
            &file_jti,
            file_ttl_secs,
        )
        .map_err(|err| {
            ACCESS_TICKET_ISSUE_METRICS.observe_failed();
            tracing::error!(user_id = user.id, err = %err, "issue file ticket failed");
            AppError::ServerError("tickets_issue_failed".to_string())
        })?;
    let notify_token = state
        .ek
        .sign_notify_ticket_with_session(
            user.id,
            auth_ctx.sid.clone(),
            auth_ctx.ver,
            &notify_jti,
            notify_ttl_secs,
        )
        .map_err(|err| {
            ACCESS_TICKET_ISSUE_METRICS.observe_failed();
            tracing::error!(user_id = user.id, err = %err, "issue notify ticket failed");
            AppError::ServerError("tickets_issue_failed".to_string())
        })?;
    ACCESS_TICKET_ISSUE_METRICS.observe_success();
    let (requests_total, success_total, failed_total, rate_limited_total) =
        ACCESS_TICKET_ISSUE_METRICS.snapshot();
    tracing::info!(
        user_id = user.id,
        sid_hash = hash_for_log(&auth_ctx.sid),
        token_version = auth_ctx.ver,
        file_jti_hash = hash_for_log(&file_jti),
        notify_jti_hash = hash_for_log(&notify_jti),
        file_ttl_secs,
        notify_ttl_secs,
        requests_total,
        success_total,
        failed_total,
        rate_limited_total,
        "issued scoped access tickets"
    );
    Ok((
        StatusCode::OK,
        user_headers,
        Json(AccessTicketsOutput {
            file_token,
            notify_token,
            expires_in_secs: file_ttl_secs.min(notify_ttl_secs),
        }),
    )
        .into_response())
}

fn request_rate_limit_ip_key_from_headers(headers: &HeaderMap) -> Option<String> {
    extract_raw_ip_from_forwarded_headers(headers)
}

fn extract_raw_ip_from_forwarded_headers(headers: &HeaderMap) -> Option<String> {
    let parse_first = |raw: &str| -> Option<String> {
        raw.split(',')
            .next()
            .map(str::trim)
            .filter(|v| !v.is_empty())
            .map(ToOwned::to_owned)
    };
    headers
        .get("x-forwarded-for")
        .and_then(|v| v.to_str().ok())
        .and_then(parse_first)
        .or_else(|| {
            headers
                .get("x-real-ip")
                .and_then(|v| v.to_str().ok())
                .map(str::trim)
                .filter(|v| !v.is_empty())
                .map(ToOwned::to_owned)
        })
}

fn hash_for_log(input: &str) -> String {
    let mut hasher = DefaultHasher::new();
    input.hash(&mut hasher);
    format!("{:016x}", hasher.finish())
}

fn load_env_u64(key: &str, default: u64, min: u64, max: u64) -> u64 {
    let parsed = env::var(key)
        .ok()
        .and_then(|raw| raw.trim().parse::<u64>().ok())
        .unwrap_or(default);
    parsed.clamp(min, max)
}

#[cfg(test)]
mod tests {
    use super::*;
    use anyhow::Result;
    use http_body_util::BodyExt;
    use std::path::PathBuf;

    fn test_state() -> Result<AppState> {
        let config = crate::AppConfig {
            server: crate::config::ServerConfig {
                port: 0,
                db_url: "postgres://localhost:5432/chat".to_string(),
                base_dir: PathBuf::from("/tmp/chat"),
            },
            auth: crate::config::AuthConfig {
                sk: include_str!("../../../chat_core/fixtures/encoding.pem").to_string(),
                pk: include_str!("../../../chat_core/fixtures/decoding.pem").to_string(),
            },
            kafka: crate::config::KafkaConfig::default(),
            redis: crate::config::RedisConfig::default(),
            ai_judge: crate::config::AiJudgeConfig::default(),
            analytics: crate::config::AnalyticsIngressConfig::default(),
            worker_runtime: crate::config::WorkerRuntimeConfig::default(),
            payment: crate::config::PaymentConfig::default(),
        };
        Ok(AppState::new_for_unit_test(config)?)
    }

    #[tokio::test]
    async fn create_access_tickets_should_return_audience_scoped_tickets() -> Result<()> {
        let state = test_state()?;
        let user = chat_core::User::new(1, "Tyr Chen", "tchen@acme.org");
        let auth_ctx = AuthContext {
            user: user.clone(),
            sid: "sid-tickets-test".to_string(),
            ver: 7,
        };

        let response = create_access_tickets_handler(
            Extension(auth_ctx.clone()),
            Extension(user.clone()),
            State(state.clone()),
            HeaderMap::new(),
        )
        .await?;
        assert_eq!(response.status(), StatusCode::OK);
        let body = response.into_body().collect().await?.to_bytes();
        let ret: AccessTicketsOutput = serde_json::from_slice(&body)?;

        assert!(ret.expires_in_secs > 0);
        assert!(state.dk.verify_access(&ret.file_token).is_err());
        assert!(state.dk.verify_access(&ret.notify_token).is_err());
        let file_ticket = state.dk.verify_file_ticket_decoded(&ret.file_token)?;
        let notify_ticket = state.dk.verify_notify_ticket_decoded(&ret.notify_token)?;
        assert_eq!(file_ticket.user.id, user.id);
        assert_eq!(notify_ticket.user.id, user.id);
        assert_eq!(file_ticket.sid, auth_ctx.sid);
        assert_eq!(notify_ticket.sid, auth_ctx.sid);
        assert_eq!(file_ticket.ver, auth_ctx.ver);
        assert_eq!(notify_ticket.ver, auth_ctx.ver);
        Ok(())
    }
}
