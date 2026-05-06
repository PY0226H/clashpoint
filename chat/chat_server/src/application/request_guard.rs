use axum::{
    http::{HeaderMap, HeaderName, HeaderValue, StatusCode},
    response::{IntoResponse, Response},
    Json,
};
use chrono::Utc;
use sha1::{Digest, Sha1};
use std::{
    collections::HashMap,
    net::IpAddr,
    sync::{LazyLock, Mutex},
};
use tracing::warn;

use crate::{
    config::ServerForwardedHeaderTrustConfig, redis_store::RedisStore, AppError, AppState,
    ErrorOutput, RateLimitDecision,
};

#[derive(Debug, Clone, Copy)]
struct LocalRateLimitBucket {
    tat_epoch_ms: u64,
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
            local_rate_limit_fallback_decision(
                scope,
                &build_local_rate_limit_fallback_key(state, key),
                limit,
                window_secs.max(1),
            )
        }
    }
}

pub(crate) async fn enforce_rate_limit_with_disabled_fallback(
    state: &AppState,
    scope: &str,
    key: &str,
    limit: u64,
    window_secs: u64,
) -> RateLimitDecision {
    if matches!(&state.redis, RedisStore::Disabled { .. }) {
        return local_rate_limit_fallback_decision(
            scope,
            &build_local_rate_limit_fallback_key(state, key),
            limit,
            window_secs.max(1),
        );
    }
    enforce_rate_limit(state, scope, key, limit, window_secs).await
}

fn build_local_rate_limit_fallback_key(state: &AppState, key: &str) -> String {
    format!("{:p}::{}", &state.pool, key.trim())
}

fn local_rate_limit_fallback_decision(
    scope: &str,
    key: &str,
    limit: u64,
    window_secs: u64,
) -> RateLimitDecision {
    let now_ms = Utc::now().timestamp_millis().max(0) as u64;
    let fallback_key = format!("{}::{}", scope.trim(), key.trim());
    if limit == 0 {
        return RateLimitDecision {
            allowed: true,
            limit,
            remaining: limit,
            reset_at_epoch_secs: epoch_ms_to_epoch_secs_ceil(
                now_ms.saturating_add(window_secs.saturating_mul(1_000)),
            ),
        };
    }
    let mut guard = match LOCAL_RATE_LIMIT_FALLBACK.lock() {
        Ok(v) => v,
        Err(poisoned) => poisoned.into_inner(),
    };
    if guard.len() > LOCAL_RATE_LIMIT_FALLBACK_MAX_KEYS {
        guard.retain(|_, bucket| bucket.tat_epoch_ms > now_ms);
    }
    let bucket = guard.entry(fallback_key).or_insert(LocalRateLimitBucket {
        tat_epoch_ms: now_ms,
    });
    let decision = compute_gcra_fallback_decision(now_ms, bucket.tat_epoch_ms, limit, window_secs);
    if decision.allowed {
        bucket.tat_epoch_ms = decision.next_tat_epoch_ms;
    }
    RateLimitDecision {
        allowed: decision.allowed,
        limit,
        remaining: decision.remaining,
        reset_at_epoch_secs: decision.reset_at_epoch_secs,
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
struct LocalGcraDecision {
    allowed: bool,
    remaining: u64,
    reset_at_epoch_secs: u64,
    next_tat_epoch_ms: u64,
}

fn compute_gcra_fallback_decision(
    now_ms: u64,
    stored_tat_epoch_ms: u64,
    limit: u64,
    window_secs: u64,
) -> LocalGcraDecision {
    if limit == 0 || window_secs == 0 {
        return LocalGcraDecision {
            allowed: true,
            remaining: limit,
            reset_at_epoch_secs: epoch_ms_to_epoch_secs_ceil(now_ms),
            next_tat_epoch_ms: now_ms,
        };
    }

    let window_ms = window_secs.saturating_mul(1_000);
    let emission_interval_ms = ceil_div(window_ms, limit).max(1);
    let burst_tolerance_ms = emission_interval_ms.saturating_mul(limit.saturating_sub(1));
    let tat_epoch_ms = stored_tat_epoch_ms.max(now_ms);
    let allow_at_epoch_ms = tat_epoch_ms.saturating_sub(burst_tolerance_ms);

    if now_ms < allow_at_epoch_ms {
        return LocalGcraDecision {
            allowed: false,
            remaining: 0,
            reset_at_epoch_secs: epoch_ms_to_epoch_secs_ceil(allow_at_epoch_ms),
            next_tat_epoch_ms: stored_tat_epoch_ms,
        };
    }

    let next_tat_epoch_ms = tat_epoch_ms.saturating_add(emission_interval_ms);
    let consumed_ahead_ms = next_tat_epoch_ms.saturating_sub(now_ms);
    let remaining = if burst_tolerance_ms >= consumed_ahead_ms {
        let immediate_budget_ms = burst_tolerance_ms.saturating_sub(consumed_ahead_ms);
        (immediate_budget_ms / emission_interval_ms)
            .saturating_add(1)
            .min(limit)
    } else {
        0
    };
    let reset_at_epoch_ms = next_tat_epoch_ms
        .saturating_sub(burst_tolerance_ms)
        .max(now_ms);

    LocalGcraDecision {
        allowed: true,
        remaining,
        reset_at_epoch_secs: epoch_ms_to_epoch_secs_ceil(reset_at_epoch_ms),
        next_tat_epoch_ms,
    }
}

fn ceil_div(numerator: u64, denominator: u64) -> u64 {
    if denominator == 0 {
        return numerator;
    }
    numerator.saturating_add(denominator.saturating_sub(1)) / denominator
}

fn epoch_ms_to_epoch_secs_ceil(epoch_ms: u64) -> u64 {
    epoch_ms.saturating_add(999) / 1_000
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

pub(crate) fn request_idempotency_key_from_headers(
    headers: &HeaderMap,
    invalid_code: &str,
    too_long_code: &str,
    max_len: usize,
) -> Result<Option<String>, AppError> {
    let Some(raw) = headers
        .get("idempotency-key")
        .or_else(|| headers.get("x-idempotency-key"))
        .and_then(|v| v.to_str().ok())
    else {
        return Ok(None);
    };
    let key = raw.trim();
    if key.is_empty() {
        return Err(AppError::ValidationError(invalid_code.to_string()));
    }
    if key.len() > max_len {
        return Err(AppError::ValidationError(too_long_code.to_string()));
    }
    Ok(Some(key.to_string()))
}

pub(crate) fn request_rate_limit_ip_key_from_headers(headers: &HeaderMap) -> Option<String> {
    extract_raw_ip_from_forwarded_headers(headers).map(|ip| hash_with_sha1(&ip))
}

pub(crate) fn request_rate_limit_ip_key_with_user_fallback(
    headers: &HeaderMap,
    user_id: i64,
    forwarded_header_trust: &ServerForwardedHeaderTrustConfig,
) -> String {
    request_rate_limit_ip_key_from_headers_if_trusted(headers, forwarded_header_trust)
        .unwrap_or_else(|| hash_with_sha1(&format!("unknown_user_scope:{user_id}")))
}

fn request_rate_limit_ip_key_from_headers_if_trusted(
    headers: &HeaderMap,
    forwarded_header_trust: &ServerForwardedHeaderTrustConfig,
) -> Option<String> {
    // 限流来源 IP 只信任受控代理链路透传，避免客户端伪造转发头绕过桶治理。
    if !forwarded_headers_trusted(headers, forwarded_header_trust) {
        return None;
    }
    request_rate_limit_ip_key_from_headers(headers)
}

fn forwarded_headers_trusted(
    headers: &HeaderMap,
    forwarded_header_trust: &ServerForwardedHeaderTrustConfig,
) -> bool {
    trusted_proxy_id_matches(headers, forwarded_header_trust)
        || trusted_proxy_cidr_matches(headers, forwarded_header_trust)
}

fn trusted_proxy_id_matches(
    headers: &HeaderMap,
    forwarded_header_trust: &ServerForwardedHeaderTrustConfig,
) -> bool {
    if forwarded_header_trust.trusted_proxy_ids.is_empty() {
        return false;
    }
    let Some(proxy_id) = headers
        .get("x-echoisle-proxy-id")
        .and_then(|v| v.to_str().ok())
        .map(str::trim)
        .filter(|v| !v.is_empty())
    else {
        return false;
    };
    forwarded_header_trust
        .trusted_proxy_ids
        .iter()
        .any(|trusted| trusted == proxy_id)
}

fn trusted_proxy_cidr_matches(
    headers: &HeaderMap,
    forwarded_header_trust: &ServerForwardedHeaderTrustConfig,
) -> bool {
    if forwarded_header_trust.trusted_proxy_cidrs.is_empty() {
        return false;
    }
    let Some(peer_ip) = headers
        .get("x-echoisle-peer-ip")
        .and_then(|v| v.to_str().ok())
        .map(str::trim)
        .filter(|v| !v.is_empty())
    else {
        return false;
    };
    let Ok(parsed_peer_ip) = peer_ip.parse::<IpAddr>() else {
        return false;
    };
    let IpAddr::V4(peer_v4) = parsed_peer_ip else {
        return false;
    };
    forwarded_header_trust
        .trusted_proxy_cidrs
        .iter()
        .filter_map(|raw| SimpleIpv4Cidr::parse(raw))
        .any(|cidr| cidr.contains(peer_v4))
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

#[derive(Debug, Clone, Copy)]
struct SimpleIpv4Cidr {
    network: u32,
    mask: u32,
}

impl SimpleIpv4Cidr {
    fn parse(raw: &str) -> Option<Self> {
        let normalized = raw.trim();
        if normalized.is_empty() {
            return None;
        }
        let mut parts = normalized.split('/');
        let base = parts.next()?.trim().parse::<std::net::Ipv4Addr>().ok()?;
        let prefix = parts.next()?.trim().parse::<u8>().ok()?;
        if prefix > 32 || parts.next().is_some() {
            return None;
        }
        let mask = if prefix == 0 {
            0
        } else {
            u32::MAX << (32 - prefix)
        };
        let network = u32::from(base) & mask;
        Some(Self { network, mask })
    }

    fn contains(&self, ip: std::net::Ipv4Addr) -> bool {
        (u32::from(ip) & self.mask) == self.network
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::http::HeaderValue;

    #[test]
    fn gcra_fallback_should_allow_configured_burst_then_reject() {
        let now_ms = 1_000_000;
        let limit = 3;
        let window_secs = 3;

        let first = compute_gcra_fallback_decision(now_ms, now_ms, limit, window_secs);
        assert_eq!(
            first,
            LocalGcraDecision {
                allowed: true,
                remaining: 2,
                reset_at_epoch_secs: 1_000,
                next_tat_epoch_ms: 1_001_000,
            }
        );

        let second =
            compute_gcra_fallback_decision(now_ms, first.next_tat_epoch_ms, limit, window_secs);
        assert_eq!(
            second,
            LocalGcraDecision {
                allowed: true,
                remaining: 1,
                reset_at_epoch_secs: 1_000,
                next_tat_epoch_ms: 1_002_000,
            }
        );

        let third =
            compute_gcra_fallback_decision(now_ms, second.next_tat_epoch_ms, limit, window_secs);
        assert_eq!(
            third,
            LocalGcraDecision {
                allowed: true,
                remaining: 0,
                reset_at_epoch_secs: 1_001,
                next_tat_epoch_ms: 1_003_000,
            }
        );

        let fourth =
            compute_gcra_fallback_decision(now_ms, third.next_tat_epoch_ms, limit, window_secs);
        assert_eq!(
            fourth,
            LocalGcraDecision {
                allowed: false,
                remaining: 0,
                reset_at_epoch_secs: 1_001,
                next_tat_epoch_ms: 1_003_000,
            }
        );
    }

    #[test]
    fn gcra_fallback_should_recover_after_emission_interval() {
        let now_ms = 1_000_000;
        let limit = 3;
        let window_secs = 3;
        let saturated_tat_ms = 1_003_000;

        let ret =
            compute_gcra_fallback_decision(now_ms + 1_000, saturated_tat_ms, limit, window_secs);

        assert_eq!(
            ret,
            LocalGcraDecision {
                allowed: true,
                remaining: 0,
                reset_at_epoch_secs: 1_002,
                next_tat_epoch_ms: 1_004_000,
            }
        );
    }

    #[test]
    fn ceil_div_should_round_up() {
        assert_eq!(ceil_div(0, 3), 0);
        assert_eq!(ceil_div(1, 3), 1);
        assert_eq!(ceil_div(3, 3), 1);
        assert_eq!(ceil_div(4, 3), 2);
    }

    #[test]
    fn request_rate_limit_ip_key_with_user_fallback_should_prefer_forwarded_ip_when_proxy_id_trusted(
    ) {
        let mut headers = HeaderMap::new();
        headers.insert(
            "x-forwarded-for",
            HeaderValue::from_static("203.0.113.9, 10.0.0.1"),
        );
        headers.insert(
            "x-echoisle-proxy-id",
            HeaderValue::from_static("trusted-proxy-a"),
        );

        let key = request_rate_limit_ip_key_with_user_fallback(
            &headers,
            42,
            &ServerForwardedHeaderTrustConfig {
                trusted_proxy_ids: vec!["trusted-proxy-a".to_string()],
                trusted_proxy_cidrs: Vec::new(),
            },
        );
        assert_eq!(key, hash_with_sha1("203.0.113.9"));
    }

    #[test]
    fn request_rate_limit_ip_key_with_user_fallback_should_prefer_forwarded_ip_when_peer_ip_in_trusted_cidr(
    ) {
        let mut headers = HeaderMap::new();
        headers.insert(
            "x-forwarded-for",
            HeaderValue::from_static("198.51.100.7, 10.0.0.1"),
        );
        headers.insert("x-echoisle-peer-ip", HeaderValue::from_static("10.10.2.3"));

        let key = request_rate_limit_ip_key_with_user_fallback(
            &headers,
            42,
            &ServerForwardedHeaderTrustConfig {
                trusted_proxy_ids: Vec::new(),
                trusted_proxy_cidrs: vec!["10.0.0.0/8".to_string()],
            },
        );
        assert_eq!(key, hash_with_sha1("198.51.100.7"));
    }

    #[test]
    fn request_rate_limit_ip_key_with_user_fallback_should_ignore_untrusted_forwarded_headers() {
        let mut headers = HeaderMap::new();
        headers.insert("x-forwarded-for", HeaderValue::from_static("203.0.113.9"));

        let key = request_rate_limit_ip_key_with_user_fallback(
            &headers,
            42,
            &ServerForwardedHeaderTrustConfig::default(),
        );
        assert_eq!(key, hash_with_sha1("unknown_user_scope:42"));
    }

    #[test]
    fn request_rate_limit_ip_key_with_user_fallback_should_isolate_unknown_scope_by_user() {
        let headers = HeaderMap::new();

        let key_a = request_rate_limit_ip_key_with_user_fallback(
            &headers,
            10,
            &ServerForwardedHeaderTrustConfig::default(),
        );
        let key_b = request_rate_limit_ip_key_with_user_fallback(
            &headers,
            11,
            &ServerForwardedHeaderTrustConfig::default(),
        );

        assert_eq!(key_a, hash_with_sha1("unknown_user_scope:10"));
        assert_eq!(key_b, hash_with_sha1("unknown_user_scope:11"));
        assert_ne!(key_a, key_b);
    }
}
