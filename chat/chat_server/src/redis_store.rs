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
            key_prefix: "aicomm".to_string(),
            ..RedisConfig::default()
        };
        let store = RedisStore::Disabled {
            config,
            message: "disabled".to_string(),
        };
        assert_eq!(
            store.namespaced_key("rate_limit", "signin:alice@example.com"),
            "aicomm:rate_limit:signin:alice@example.com"
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
}
