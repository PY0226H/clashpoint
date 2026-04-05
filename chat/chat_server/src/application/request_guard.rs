use axum::{
    http::{HeaderMap, HeaderName, HeaderValue, StatusCode},
    response::{IntoResponse, Response},
    Json,
};
use chrono::Utc;
use std::{
    collections::HashMap,
    sync::{LazyLock, Mutex},
};
use tracing::warn;

use crate::{AppError, AppState, ErrorOutput, RateLimitDecision};

#[derive(Debug, Clone, Copy)]
struct LocalRateLimitBucket {
    window_start_epoch_secs: u64,
    count: u64,
}

const LOCAL_RATE_LIMIT_FALLBACK_MAX_KEYS: usize = 20_000;

static LOCAL_RATE_LIMIT_FALLBACK: LazyLock<Mutex<HashMap<String, LocalRateLimitBucket>>> =
    LazyLock::new(|| Mutex::new(HashMap::new()));

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
                "rate limit degraded to local fallback, scope={}, key={}, err={}",
                scope, key, err
            );
            local_rate_limit_fallback_decision(scope, key, limit, window_secs.max(1))
        }
    }
}

fn local_rate_limit_fallback_decision(
    scope: &str,
    key: &str,
    limit: u64,
    window_secs: u64,
) -> RateLimitDecision {
    let now_secs = Utc::now().timestamp().max(0) as u64;
    let fallback_key = format!("{}::{}", scope.trim(), key.trim());
    if limit == 0 {
        return RateLimitDecision {
            allowed: true,
            limit,
            remaining: limit,
            reset_at_epoch_secs: now_secs + window_secs,
        };
    }
    let mut guard = match LOCAL_RATE_LIMIT_FALLBACK.lock() {
        Ok(v) => v,
        Err(poisoned) => poisoned.into_inner(),
    };
    if guard.len() > LOCAL_RATE_LIMIT_FALLBACK_MAX_KEYS {
        guard.retain(|_, bucket| {
            now_secs.saturating_sub(bucket.window_start_epoch_secs) <= window_secs
        });
    }
    let bucket = guard.entry(fallback_key).or_insert(LocalRateLimitBucket {
        window_start_epoch_secs: now_secs,
        count: 0,
    });
    if now_secs.saturating_sub(bucket.window_start_epoch_secs) >= window_secs {
        bucket.window_start_epoch_secs = now_secs;
        bucket.count = 0;
    }
    bucket.count = bucket.count.saturating_add(1);
    let allowed = bucket.count <= limit;
    let remaining = limit.saturating_sub(bucket.count);
    let reset_at_epoch_secs = bucket.window_start_epoch_secs.saturating_add(window_secs);
    RateLimitDecision {
        allowed,
        limit,
        remaining,
        reset_at_epoch_secs,
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
