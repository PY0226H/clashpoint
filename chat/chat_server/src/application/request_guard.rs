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
