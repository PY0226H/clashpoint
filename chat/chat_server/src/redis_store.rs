use std::{sync::Arc, time::Duration};

use anyhow::Context;
use redis::{aio::ConnectionManager, Client};
use serde::Serialize;
use tokio::time::timeout;
use tracing::warn;
use utoipa::ToSchema;

use crate::config::RedisConfig;

#[derive(Debug, Clone, Serialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct RedisHealthOutput {
    pub enabled: bool,
    pub ready: bool,
    pub startup_policy: String,
    pub key_prefix: String,
    pub default_ttl_secs: u64,
    pub message: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RateLimitDecision {
    pub allowed: bool,
    pub limit: u64,
    pub remaining: u64,
    pub reset_at_epoch_secs: u64,
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
            Self::Disabled { config, message } => RedisHealthOutput {
                enabled: false,
                ready: false,
                startup_policy: config.startup_policy_label().to_string(),
                key_prefix: config.key_prefix.clone(),
                default_ttl_secs: config.default_ttl_secs,
                message: message.clone(),
            },
            Self::Enabled(inner) => match inner.ping().await {
                Ok(_) => RedisHealthOutput {
                    enabled: true,
                    ready: true,
                    startup_policy: inner.config.startup_policy_label().to_string(),
                    key_prefix: inner.config.key_prefix.clone(),
                    default_ttl_secs: inner.config.default_ttl_secs,
                    message: "ok".to_string(),
                },
                Err(err) => RedisHealthOutput {
                    enabled: true,
                    ready: false,
                    startup_policy: inner.config.startup_policy_label().to_string(),
                    key_prefix: inner.config.key_prefix.clone(),
                    default_ttl_secs: inner.config.default_ttl_secs,
                    message: format!("degraded: {err}"),
                },
            },
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
}

impl RedisStoreInner {
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
}
