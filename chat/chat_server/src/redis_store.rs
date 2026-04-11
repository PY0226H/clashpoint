use std::{
    sync::Arc,
    time::{Duration, Instant},
};

use anyhow::Context;
use chrono::Utc;
use redis::{aio::ConnectionManager, Client};
use serde::{Deserialize, Serialize};
use tokio::{sync::Mutex, time::timeout};
use tracing::warn;
use utoipa::ToSchema;

use crate::config::RedisConfig;

const REDIS_HEALTH_CACHE_TTL_MS: i64 = 2_000;
const REDIS_HEALTH_STATUS_DISABLED: &str = "disabled";
const REDIS_HEALTH_STATUS_READY: &str = "ready";
const REDIS_HEALTH_STATUS_DEGRADED: &str = "degraded";
const REDIS_HEALTH_REASON_OK: &str = "ok";
const REDIS_HEALTH_REASON_DISABLED_BY_CONFIG: &str = "redis_disabled_by_config";
const REDIS_HEALTH_REASON_STARTUP_FAIL_OPEN: &str = "redis_unavailable_startup_fail_open";
const REDIS_HEALTH_REASON_PING_TIMEOUT: &str = "redis_ping_timeout";
const REDIS_HEALTH_REASON_PING_COMMAND_FAILED: &str = "redis_ping_command_failed";

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct RedisHealthOutput {
    pub enabled: bool,
    pub ready: bool,
    pub startup_policy: String,
    pub key_prefix: String,
    pub default_ttl_secs: u64,
    pub message: String,
    pub status: String,
    pub reason_code: String,
    pub checked_at_ms: i64,
    pub ping_latency_ms: Option<u64>,
    pub timeout_ms: u64,
    pub cache_hit: bool,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RateLimitDecision {
    pub allowed: bool,
    pub limit: u64,
    pub remaining: u64,
    pub reset_at_epoch_secs: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum SmsCodeVerifyDecision {
    Expired,
    Invalid,
    Exhausted,
    Passed,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum SmsCodeIssueDecision {
    Issued,
    CooldownActive,
}

#[derive(Debug, Clone)]
pub(crate) struct SmsCodeIssueInput<'a> {
    pub code_scope: &'a str,
    pub cooldown_scope: &'a str,
    pub attempt_scope: &'a str,
    pub raw_key: &'a str,
    pub code: &'a str,
    pub code_ttl_secs: u64,
    pub cooldown_ttl_secs: u64,
}

#[derive(Clone)]
pub(crate) enum RedisStore {
    Disabled {
        config: RedisConfig,
        message: String,
    },
    Enabled(Arc<RedisStoreInner>),
}

pub(crate) struct RedisStoreInner {
    config: RedisConfig,
    manager: ConnectionManager,
    health_cache: Mutex<Option<RedisHealthCacheEntry>>,
    health_probe_guard: Mutex<()>,
}

#[derive(Debug, Clone)]
struct RedisHealthCacheEntry {
    output: RedisHealthOutput,
    expires_at_ms: i64,
}

impl RedisStore {
    pub async fn bootstrap(config: &RedisConfig) -> anyhow::Result<Self> {
        if !config.enabled {
            return Ok(Self::Disabled {
                config: config.clone(),
                message: "redis disabled by config".to_string(),
            });
        }

        let client = Client::open(config.url.clone()).context("parse redis url failed")?;
        let manager = ConnectionManager::new(client)
            .await
            .context("create redis connection manager failed")?;
        let inner = Arc::new(RedisStoreInner {
            config: config.clone(),
            manager,
            health_cache: Mutex::new(None),
            health_probe_guard: Mutex::new(()),
        });

        if let Err(err) = inner.ping().await {
            if config.startup_fail_closed() {
                return Err(err).context("redis startup probe failed with fail_closed policy");
            }
            warn!("redis startup probe failed under fail_open policy: {}", err);
            return Ok(Self::Disabled {
                config: config.clone(),
                message: format!("redis unavailable at startup (fail_open): {err}"),
            });
        }

        Ok(Self::Enabled(inner))
    }

    #[allow(dead_code)]
    pub fn namespaced_key(&self, scope: &str, raw_key: &str) -> String {
        let key_prefix = match self {
            Self::Disabled { config, .. } => config.key_prefix.trim(),
            Self::Enabled(inner) => inner.config.key_prefix.trim(),
        };
        let scope = scope.trim();
        let raw_key = raw_key.trim();
        if key_prefix.is_empty() {
            format!("{scope}:{raw_key}")
        } else {
            format!("{key_prefix}:{scope}:{raw_key}")
        }
    }

    pub async fn health_snapshot(&self) -> RedisHealthOutput {
        match self {
            Self::Disabled { config, message } => {
                let reason_code = if message.contains("fail_open") {
                    REDIS_HEALTH_REASON_STARTUP_FAIL_OPEN
                } else {
                    REDIS_HEALTH_REASON_DISABLED_BY_CONFIG
                };
                RedisHealthOutput {
                    enabled: false,
                    ready: false,
                    startup_policy: config.startup_policy_label().to_string(),
                    key_prefix: config.key_prefix.clone(),
                    default_ttl_secs: config.default_ttl_secs,
                    message: message.clone(),
                    status: REDIS_HEALTH_STATUS_DISABLED.to_string(),
                    reason_code: reason_code.to_string(),
                    checked_at_ms: now_ms(),
                    ping_latency_ms: None,
                    timeout_ms: config.healthcheck_timeout_ms.max(1),
                    cache_hit: false,
                }
            }
            Self::Enabled(inner) => inner.health_snapshot_with_cache().await,
        }
    }

    pub async fn check_rate_limit(
        &self,
        scope: &str,
        raw_key: &str,
        limit: u64,
        window_secs: u64,
    ) -> anyhow::Result<RateLimitDecision> {
        let now_secs = chrono::Utc::now().timestamp().max(0) as u64;
        if limit == 0 || window_secs == 0 {
            return Ok(RateLimitDecision {
                allowed: true,
                limit,
                remaining: limit,
                reset_at_epoch_secs: now_secs,
            });
        }

        match self {
            Self::Disabled { .. } => Ok(RateLimitDecision {
                allowed: true,
                limit,
                remaining: limit,
                reset_at_epoch_secs: now_secs + window_secs,
            }),
            Self::Enabled(inner) => {
                let mut conn = inner.manager.clone();
                let redis_key = self.namespaced_key(&format!("rate_limit:{scope}"), raw_key);
                let current: i64 = redis::cmd("INCR")
                    .arg(&redis_key)
                    .query_async(&mut conn)
                    .await
                    .context("redis INCR rate limit failed")?;
                if current <= 1 {
                    let _: i64 = redis::cmd("EXPIRE")
                        .arg(&redis_key)
                        .arg(window_secs as i64)
                        .query_async(&mut conn)
                        .await
                        .context("redis EXPIRE rate limit key failed")?;
                }
                let mut ttl_secs: i64 = redis::cmd("TTL")
                    .arg(&redis_key)
                    .query_async(&mut conn)
                    .await
                    .context("redis TTL rate limit key failed")?;
                if ttl_secs < 0 {
                    let _: i64 = redis::cmd("EXPIRE")
                        .arg(&redis_key)
                        .arg(window_secs as i64)
                        .query_async(&mut conn)
                        .await
                        .context("redis EXPIRE fallback rate limit key failed")?;
                    ttl_secs = window_secs as i64;
                }
                let current_u64 = current.max(0) as u64;
                let remaining = limit.saturating_sub(current_u64);
                Ok(RateLimitDecision {
                    allowed: current_u64 <= limit,
                    limit,
                    remaining,
                    reset_at_epoch_secs: now_secs + (ttl_secs.max(0) as u64),
                })
            }
        }
    }

    pub async fn try_acquire_idempotency(
        &self,
        scope: &str,
        raw_key: &str,
        ttl_secs: u64,
    ) -> anyhow::Result<bool> {
        if ttl_secs == 0 {
            return Ok(true);
        }
        match self {
            Self::Disabled { .. } => Ok(true),
            Self::Enabled(inner) => {
                let mut conn = inner.manager.clone();
                let redis_key = self.namespaced_key(&format!("idempotency:{scope}"), raw_key);
                let ret: Option<String> = redis::cmd("SET")
                    .arg(&redis_key)
                    .arg("1")
                    .arg("NX")
                    .arg("EX")
                    .arg(ttl_secs as i64)
                    .query_async(&mut conn)
                    .await
                    .context("redis SET NX EX idempotency lock failed")?;
                Ok(ret.is_some())
            }
        }
    }

    pub async fn release_idempotency(&self, scope: &str, raw_key: &str) -> anyhow::Result<()> {
        match self {
            Self::Disabled { .. } => Ok(()),
            Self::Enabled(inner) => {
                let mut conn = inner.manager.clone();
                let redis_key = self.namespaced_key(&format!("idempotency:{scope}"), raw_key);
                let _: i64 = redis::cmd("DEL")
                    .arg(&redis_key)
                    .query_async(&mut conn)
                    .await
                    .context("redis DEL idempotency lock failed")?;
                Ok(())
            }
        }
    }

    pub async fn get_value(&self, scope: &str, raw_key: &str) -> anyhow::Result<Option<String>> {
        match self {
            Self::Disabled { .. } => Ok(None),
            Self::Enabled(inner) => {
                let mut conn = inner.manager.clone();
                let redis_key = self.namespaced_key(scope, raw_key);
                let ret: Option<String> = redis::cmd("GET")
                    .arg(&redis_key)
                    .query_async(&mut conn)
                    .await
                    .context("redis GET failed")?;
                Ok(ret)
            }
        }
    }

    pub async fn set_value_with_ttl(
        &self,
        scope: &str,
        raw_key: &str,
        value: &str,
        ttl_secs: u64,
    ) -> anyhow::Result<()> {
        match self {
            Self::Disabled { .. } => Ok(()),
            Self::Enabled(inner) => {
                let mut conn = inner.manager.clone();
                let redis_key = self.namespaced_key(scope, raw_key);
                let _: String = redis::cmd("SET")
                    .arg(&redis_key)
                    .arg(value)
                    .arg("EX")
                    .arg(ttl_secs.max(1) as i64)
                    .query_async(&mut conn)
                    .await
                    .context("redis SET EX failed")?;
                Ok(())
            }
        }
    }

    pub async fn delete_key(&self, scope: &str, raw_key: &str) -> anyhow::Result<()> {
        match self {
            Self::Disabled { .. } => Ok(()),
            Self::Enabled(inner) => {
                let mut conn = inner.manager.clone();
                let redis_key = self.namespaced_key(scope, raw_key);
                let _: i64 = redis::cmd("DEL")
                    .arg(&redis_key)
                    .query_async(&mut conn)
                    .await
                    .context("redis DEL key failed")?;
                Ok(())
            }
        }
    }

    pub async fn add_set_member(
        &self,
        scope: &str,
        raw_key: &str,
        member: &str,
    ) -> anyhow::Result<()> {
        match self {
            Self::Disabled { .. } => Ok(()),
            Self::Enabled(inner) => {
                let mut conn = inner.manager.clone();
                let redis_key = self.namespaced_key(scope, raw_key);
                let _: i64 = redis::cmd("SADD")
                    .arg(&redis_key)
                    .arg(member)
                    .query_async(&mut conn)
                    .await
                    .context("redis SADD failed")?;
                Ok(())
            }
        }
    }

    pub async fn remove_set_member(
        &self,
        scope: &str,
        raw_key: &str,
        member: &str,
    ) -> anyhow::Result<()> {
        match self {
            Self::Disabled { .. } => Ok(()),
            Self::Enabled(inner) => {
                let mut conn = inner.manager.clone();
                let redis_key = self.namespaced_key(scope, raw_key);
                let _: i64 = redis::cmd("SREM")
                    .arg(&redis_key)
                    .arg(member)
                    .query_async(&mut conn)
                    .await
                    .context("redis SREM failed")?;
                Ok(())
            }
        }
    }

    pub async fn set_key_expire(
        &self,
        scope: &str,
        raw_key: &str,
        ttl_secs: u64,
    ) -> anyhow::Result<()> {
        match self {
            Self::Disabled { .. } => Ok(()),
            Self::Enabled(inner) => {
                let mut conn = inner.manager.clone();
                let redis_key = self.namespaced_key(scope, raw_key);
                let _: i64 = redis::cmd("EXPIRE")
                    .arg(&redis_key)
                    .arg(ttl_secs.max(1) as i64)
                    .query_async(&mut conn)
                    .await
                    .context("redis EXPIRE key failed")?;
                Ok(())
            }
        }
    }

    pub async fn verify_sms_code_atomically(
        &self,
        code_scope: &str,
        attempt_scope: &str,
        raw_key: &str,
        provided_code: &str,
        max_failed_attempts: u64,
        fallback_ttl_secs: u64,
    ) -> anyhow::Result<SmsCodeVerifyDecision> {
        match self {
            Self::Disabled { .. } => anyhow::bail!("redis disabled"),
            Self::Enabled(inner) => {
                let mut conn = inner.manager.clone();
                let code_key = self.namespaced_key(code_scope, raw_key);
                let attempt_key = self.namespaced_key(attempt_scope, raw_key);
                let script = r#"
local code_key = KEYS[1]
local attempt_key = KEYS[2]
local provided = ARGV[1]
local max_attempts = tonumber(ARGV[2])
local fallback_ttl = tonumber(ARGV[3])

local expected = redis.call('GET', code_key)
if not expected then
  return 0
end

if expected ~= provided then
  local attempts = redis.call('INCR', attempt_key)
  local ttl = redis.call('TTL', code_key)
  local attempt_ttl = ttl
  if attempt_ttl == nil or attempt_ttl <= 0 then
    attempt_ttl = fallback_ttl
  end
  if attempt_ttl ~= nil and attempt_ttl > 0 then
    redis.call('EXPIRE', attempt_key, attempt_ttl)
  end
  if attempts >= max_attempts then
    redis.call('DEL', code_key)
    redis.call('DEL', attempt_key)
    return 2
  end
  return 1
end

redis.call('DEL', code_key)
redis.call('DEL', attempt_key)
return 3
"#;
                let ret: i64 = redis::cmd("EVAL")
                    .arg(script)
                    .arg(2)
                    .arg(&code_key)
                    .arg(&attempt_key)
                    .arg(provided_code)
                    .arg(max_failed_attempts.max(1) as i64)
                    .arg(fallback_ttl_secs.max(1) as i64)
                    .query_async(&mut conn)
                    .await
                    .context("redis EVAL verify sms code failed")?;
                match ret {
                    0 => Ok(SmsCodeVerifyDecision::Expired),
                    1 => Ok(SmsCodeVerifyDecision::Invalid),
                    2 => Ok(SmsCodeVerifyDecision::Exhausted),
                    3 => Ok(SmsCodeVerifyDecision::Passed),
                    other => anyhow::bail!("unexpected verify sms code result: {other}"),
                }
            }
        }
    }

    pub async fn issue_sms_code_atomically(
        &self,
        input: SmsCodeIssueInput<'_>,
    ) -> anyhow::Result<SmsCodeIssueDecision> {
        match self {
            Self::Disabled { .. } => anyhow::bail!("redis disabled"),
            Self::Enabled(inner) => {
                let mut conn = inner.manager.clone();
                let code_key = self.namespaced_key(input.code_scope, input.raw_key);
                let cooldown_key = self.namespaced_key(input.cooldown_scope, input.raw_key);
                let attempt_key = self.namespaced_key(input.attempt_scope, input.raw_key);
                let script = r#"
local code_key = KEYS[1]
local cooldown_key = KEYS[2]
local attempt_key = KEYS[3]
local code = ARGV[1]
local code_ttl = tonumber(ARGV[2])
local cooldown_ttl = tonumber(ARGV[3])

local cooldown_exists = redis.call('EXISTS', cooldown_key)
if cooldown_exists == 1 then
  return 0
end

redis.call('SET', code_key, code, 'EX', code_ttl)
redis.call('SET', cooldown_key, '1', 'EX', cooldown_ttl)
redis.call('DEL', attempt_key)
return 1
"#;
                let ret: i64 = redis::cmd("EVAL")
                    .arg(script)
                    .arg(3)
                    .arg(&code_key)
                    .arg(&cooldown_key)
                    .arg(&attempt_key)
                    .arg(input.code)
                    .arg(input.code_ttl_secs.max(1) as i64)
                    .arg(input.cooldown_ttl_secs.max(1) as i64)
                    .query_async(&mut conn)
                    .await
                    .context("redis EVAL issue sms code failed")?;
                match ret {
                    0 => Ok(SmsCodeIssueDecision::CooldownActive),
                    1 => Ok(SmsCodeIssueDecision::Issued),
                    other => anyhow::bail!("unexpected issue sms code result: {other}"),
                }
            }
        }
    }
}

impl RedisStoreInner {
    async fn health_snapshot_with_cache(&self) -> RedisHealthOutput {
        let now = now_ms();
        if let Some(cached) = self.load_cached_health_snapshot(now).await {
            return cached;
        }

        let _probe_guard = self.health_probe_guard.lock().await;
        let now = now_ms();
        if let Some(cached) = self.load_cached_health_snapshot(now).await {
            return cached;
        }

        let started = Instant::now();
        let ping_result = self.ping().await;
        let latency_ms = started.elapsed().as_millis().min(u64::MAX as u128) as u64;
        let timeout_ms = self.config.healthcheck_timeout_ms.max(1);
        let checked_at_ms = now_ms();
        let output = match ping_result {
            Ok(_) => RedisHealthOutput {
                enabled: true,
                ready: true,
                startup_policy: self.config.startup_policy_label().to_string(),
                key_prefix: self.config.key_prefix.clone(),
                default_ttl_secs: self.config.default_ttl_secs,
                message: REDIS_HEALTH_REASON_OK.to_string(),
                status: REDIS_HEALTH_STATUS_READY.to_string(),
                reason_code: REDIS_HEALTH_REASON_OK.to_string(),
                checked_at_ms,
                ping_latency_ms: Some(latency_ms),
                timeout_ms,
                cache_hit: false,
            },
            Err(err) => {
                let reason_code = if err.to_string().contains("redis ping timeout") {
                    REDIS_HEALTH_REASON_PING_TIMEOUT
                } else {
                    REDIS_HEALTH_REASON_PING_COMMAND_FAILED
                };
                RedisHealthOutput {
                    enabled: true,
                    ready: false,
                    startup_policy: self.config.startup_policy_label().to_string(),
                    key_prefix: self.config.key_prefix.clone(),
                    default_ttl_secs: self.config.default_ttl_secs,
                    message: format!("degraded: {err}"),
                    status: REDIS_HEALTH_STATUS_DEGRADED.to_string(),
                    reason_code: reason_code.to_string(),
                    checked_at_ms,
                    ping_latency_ms: Some(latency_ms),
                    timeout_ms,
                    cache_hit: false,
                }
            }
        };

        self.store_cached_health_snapshot(output.clone()).await;
        output
    }

    async fn load_cached_health_snapshot(&self, now: i64) -> Option<RedisHealthOutput> {
        let mut cache = self.health_cache.lock().await;
        if let Some(entry) = cache.as_ref() {
            if entry.expires_at_ms > now {
                let mut output = entry.output.clone();
                output.cache_hit = true;
                return Some(output);
            }
        }
        *cache = None;
        None
    }

    async fn store_cached_health_snapshot(&self, output: RedisHealthOutput) {
        let mut cache = self.health_cache.lock().await;
        let expires_at_ms = now_ms().saturating_add(REDIS_HEALTH_CACHE_TTL_MS);
        *cache = Some(RedisHealthCacheEntry {
            output,
            expires_at_ms,
        });
    }

    async fn ping(&self) -> anyhow::Result<()> {
        let mut conn = self.manager.clone();
        let timeout_ms = self.config.healthcheck_timeout_ms.max(1);
        let ping_cmd = redis::cmd("PING");
        let ping_fut = ping_cmd.query_async::<String>(&mut conn);
        timeout(Duration::from_millis(timeout_ms), ping_fut)
            .await
            .context("redis ping timeout")?
            .context("redis ping command failed")?;
        Ok(())
    }
}

fn now_ms() -> i64 {
    Utc::now().timestamp_millis()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn namespaced_key_should_include_prefix_and_scope() {
        let config = RedisConfig {
            enabled: false,
            key_prefix: "echoisle".to_string(),
            ..RedisConfig::default()
        };
        let store = RedisStore::Disabled {
            config,
            message: "disabled".to_string(),
        };
        assert_eq!(
            store.namespaced_key("rate_limit", "signin:alice@example.com"),
            "echoisle:rate_limit:signin:alice@example.com"
        );
    }

    #[test]
    fn namespaced_key_should_work_without_prefix() {
        let config = RedisConfig {
            enabled: false,
            key_prefix: String::new(),
            ..RedisConfig::default()
        };
        let store = RedisStore::Disabled {
            config,
            message: "disabled".to_string(),
        };
        assert_eq!(store.namespaced_key("idem", "k1"), "idem:k1");
    }

    #[tokio::test]
    async fn check_rate_limit_should_allow_when_store_disabled() {
        let config = RedisConfig::default();
        let store = RedisStore::Disabled {
            config,
            message: "disabled".to_string(),
        };
        let ret = store
            .check_rate_limit("signin", "alice@example.com", 20, 60)
            .await
            .expect("disabled store should not fail");
        assert!(ret.allowed);
        assert_eq!(ret.limit, 20);
        assert_eq!(ret.remaining, 20);
    }

    #[tokio::test]
    async fn try_acquire_idempotency_should_allow_when_store_disabled() {
        let config = RedisConfig::default();
        let store = RedisStore::Disabled {
            config,
            message: "disabled".to_string(),
        };
        let ret = store
            .try_acquire_idempotency("judge_request", "1:2", 30)
            .await
            .expect("disabled store should not fail");
        assert!(ret);
    }

    #[tokio::test]
    async fn health_snapshot_should_return_machine_readable_fields_when_disabled() {
        let config = RedisConfig {
            healthcheck_timeout_ms: 123,
            ..RedisConfig::default()
        };
        let store = RedisStore::Disabled {
            config,
            message: "redis disabled by config".to_string(),
        };

        let output = store.health_snapshot().await;
        assert!(!output.enabled);
        assert!(!output.ready);
        assert_eq!(output.status, REDIS_HEALTH_STATUS_DISABLED);
        assert_eq!(output.reason_code, REDIS_HEALTH_REASON_DISABLED_BY_CONFIG);
        assert_eq!(output.timeout_ms, 123);
        assert_eq!(output.ping_latency_ms, None);
        assert!(!output.cache_hit);
    }

    #[tokio::test]
    async fn health_snapshot_should_mark_startup_fail_open_reason_when_disabled_message_matches() {
        let store = RedisStore::Disabled {
            config: RedisConfig::default(),
            message: "redis unavailable at startup (fail_open): dial timeout".to_string(),
        };

        let output = store.health_snapshot().await;
        assert_eq!(output.status, REDIS_HEALTH_STATUS_DISABLED);
        assert_eq!(output.reason_code, REDIS_HEALTH_REASON_STARTUP_FAIL_OPEN);
    }
}
