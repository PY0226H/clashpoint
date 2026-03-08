use axum::{
    http::{HeaderMap, HeaderName, HeaderValue, StatusCode},
    response::{IntoResponse, Response},
    Json,
};
use chrono::Utc;
use tracing::warn;

use crate::{AppError, AppState, ErrorOutput, RateLimitDecision};

pub(crate) async fn enforce_rate_limit(
    state: &AppState,
    scope: &str,
    key: &str,
    limit: u64,
    window_secs: u64,
) -> RateLimitDecision {
    match state
        .redis
        .check_rate_limit(scope, key, limit, window_secs)
        .await
    {
        Ok(v) => v,
        Err(err) => {
            warn!(
                "rate limit degraded as fail-open, scope={}, key={}, err={}",
                scope, key, err
            );
            let now_secs = Utc::now().timestamp().max(0) as u64;
            RateLimitDecision {
                allowed: true,
                limit,
                remaining: limit,
                reset_at_epoch_secs: now_secs + window_secs.max(1),
            }
        }
    }
}

pub(crate) fn build_rate_limit_headers(
    decision: &RateLimitDecision,
) -> Result<HeaderMap, AppError> {
    let mut headers = HeaderMap::new();
    headers.insert(
        HeaderName::from_static("x-ratelimit-limit"),
        HeaderValue::from_str(&decision.limit.to_string())?,
    );
    headers.insert(
        HeaderName::from_static("x-ratelimit-remaining"),
        HeaderValue::from_str(&decision.remaining.to_string())?,
    );
    headers.insert(
        HeaderName::from_static("x-ratelimit-reset"),
        HeaderValue::from_str(&decision.reset_at_epoch_secs.to_string())?,
    );
    Ok(headers)
}

pub(crate) fn rate_limit_exceeded_response(scope: &str, headers: HeaderMap) -> Response {
    (
        StatusCode::TOO_MANY_REQUESTS,
        headers,
        Json(ErrorOutput::new(format!("rate_limit_exceeded:{scope}"))),
    )
        .into_response()
}

pub(crate) async fn try_acquire_idempotency_or_fail_open(
    state: &AppState,
    scope: &str,
    key: &str,
    ttl_secs: u64,
) -> bool {
    match state
        .redis
        .try_acquire_idempotency(scope, key, ttl_secs)
        .await
    {
        Ok(v) => v,
        Err(err) => {
            warn!(
                "idempotency degraded as fail-open, scope={}, key={}, err={}",
                scope, key, err
            );
            true
        }
    }
}

pub(crate) async fn release_idempotency_best_effort(state: &AppState, scope: &str, key: &str) {
    if let Err(err) = state.redis.release_idempotency(scope, key).await {
        warn!(
            "idempotency lock release failed (ignored), scope={}, key={}, err={}",
            scope, key, err
        );
    }
}
