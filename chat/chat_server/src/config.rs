use std::path::PathBuf;

use anyhow::{bail, Result};
use chat_core::load_yaml_with_fallback;
use serde::{Deserialize, Serialize};
use std::env;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppConfig {
    pub server: ServerConfig,
    pub auth: AuthConfig,
    #[serde(default)]
    pub kafka: KafkaConfig,
    #[serde(default)]
    pub redis: RedisConfig,
    #[serde(default)]
    pub ai_judge: AiJudgeConfig,
    #[serde(default)]
    pub analytics: AnalyticsIngressConfig,
    #[serde(default)]
    pub worker_runtime: WorkerRuntimeConfig,
    #[serde(default)]
    pub payment: PaymentConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthConfig {
    pub sk: String,
    pub pk: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServerConfig {
    pub port: u16,
    pub db_url: String,
    pub base_dir: PathBuf,
    #[serde(default)]
    pub forwarded_header_trust: ServerForwardedHeaderTrustConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ServerForwardedHeaderTrustConfig {
    #[serde(default)]
    pub trusted_proxy_ids: Vec<String>,
    #[serde(default)]
    pub trusted_proxy_cidrs: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KafkaConfig {
    #[serde(default)]
    pub enabled: bool,
    #[serde(default = "default_kafka_brokers")]
    pub brokers: String,
    #[serde(default = "default_kafka_topic_prefix")]
    pub topic_prefix: String,
    #[serde(default = "default_kafka_client_id")]
    pub client_id: String,
    #[serde(default = "default_kafka_group_id")]
    pub group_id: String,
    #[serde(default)]
    pub consume_enabled: bool,
    #[serde(default)]
    pub consume_topics: Vec<String>,
    #[serde(default = "default_kafka_timeout_ms")]
    pub producer_timeout_ms: u64,
    #[serde(default)]
    pub consumer: KafkaConsumerConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KafkaConsumerConfig {
    #[serde(default)]
    pub worker_enabled: bool,
    #[serde(default = "default_kafka_consumer_worker_group_id")]
    pub worker_group_id: String,
    #[serde(default = "default_kafka_consumer_max_inflight")]
    pub max_inflight: u64,
    #[serde(default = "default_kafka_consumer_retry_policy")]
    pub retry_policy: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RedisConfig {
    #[serde(default)]
    pub enabled: bool,
    #[serde(default = "default_redis_url")]
    pub url: String,
    #[serde(default = "default_redis_pool_size")]
    pub pool_size: u32,
    #[serde(default = "default_redis_key_prefix")]
    pub key_prefix: String,
    #[serde(default = "default_redis_default_ttl_secs")]
    pub default_ttl_secs: u64,
    #[serde(default = "default_redis_startup_policy")]
    pub startup_policy: String,
    #[serde(default = "default_redis_healthcheck_timeout_ms")]
    pub healthcheck_timeout_ms: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AiJudgeConfig {
    #[serde(default = "default_ai_judge_internal_key")]
    pub internal_key: String,
    #[serde(default = "default_ai_judge_style_mode")]
    pub style_mode: String,
    #[serde(default)]
    pub dispatch_enabled: bool,
    #[serde(default = "default_ai_judge_service_base_url")]
    pub service_base_url: String,
    #[serde(default = "default_ai_judge_dispatch_path")]
    pub dispatch_path: String,
    #[serde(default = "default_ai_judge_dispatch_interval_secs")]
    pub dispatch_interval_secs: u64,
    #[serde(default = "default_ai_judge_dispatch_batch_size")]
    pub dispatch_batch_size: i64,
    #[serde(default = "default_ai_judge_dispatch_lock_secs")]
    pub dispatch_lock_secs: i64,
    #[serde(default = "default_ai_judge_dispatch_retry_backoff_max_multiplier")]
    pub dispatch_retry_backoff_max_multiplier: i64,
    #[serde(default = "default_ai_judge_dispatch_retry_jitter_ratio")]
    pub dispatch_retry_jitter_ratio: i64,
    #[serde(default = "default_ai_judge_dispatch_timeout_ms")]
    pub dispatch_timeout_ms: u64,
    #[serde(default = "default_ai_judge_dispatch_max_attempts")]
    pub dispatch_max_attempts: i32,
    #[serde(default = "default_ai_judge_dispatch_callback_wait_secs")]
    pub dispatch_callback_wait_secs: i64,
    #[serde(default)]
    pub alert_outbox_bridge_enabled: bool,
    #[serde(default = "default_ai_judge_alert_outbox_poll_interval_secs")]
    pub alert_outbox_poll_interval_secs: u64,
    #[serde(default = "default_ai_judge_alert_outbox_batch_size")]
    pub alert_outbox_batch_size: u64,
    #[serde(default = "default_ai_judge_alert_outbox_path")]
    pub alert_outbox_path: String,
    #[serde(default = "default_ai_judge_alert_outbox_delivery_path")]
    pub alert_outbox_delivery_path: String,
    #[serde(default = "default_ai_judge_alert_outbox_timeout_ms")]
    pub alert_outbox_timeout_ms: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnalyticsIngressConfig {
    #[serde(default = "default_analytics_ingress_enabled")]
    pub enabled: bool,
    #[serde(default = "default_analytics_ingress_base_url")]
    pub base_url: String,
    #[serde(default = "default_analytics_ingress_timeout_ms")]
    pub timeout_ms: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkerRuntimeConfig {
    #[serde(default = "default_worker_runtime_debate_lifecycle_worker_enabled")]
    pub debate_lifecycle_worker_enabled: bool,
    #[serde(default = "default_worker_runtime_ai_judge_dispatch_worker_enabled")]
    pub ai_judge_dispatch_worker_enabled: bool,
    #[serde(default = "default_worker_runtime_ops_observability_worker_enabled")]
    pub ops_observability_worker_enabled: bool,
    #[serde(default = "default_worker_runtime_ai_judge_alert_outbox_bridge_worker_enabled")]
    pub ai_judge_alert_outbox_bridge_worker_enabled: bool,
    #[serde(default = "default_worker_runtime_event_outbox_relay_worker_enabled")]
    pub event_outbox_relay_worker_enabled: bool,
    #[serde(default = "default_worker_runtime_ops_rbac_audit_outbox_worker_enabled")]
    pub ops_rbac_audit_outbox_worker_enabled: bool,
    #[serde(default = "default_worker_runtime_debate_lifecycle_interval_secs")]
    pub debate_lifecycle_interval_secs: u64,
    #[serde(default = "default_worker_runtime_debate_lifecycle_batch_size")]
    pub debate_lifecycle_batch_size: i64,
    #[serde(default = "default_worker_runtime_ops_observability_interval_secs")]
    pub ops_observability_interval_secs: u64,
    #[serde(default = "default_worker_runtime_event_outbox_poll_interval_secs")]
    pub event_outbox_poll_interval_secs: u64,
    #[serde(default = "default_worker_runtime_event_outbox_batch_size")]
    pub event_outbox_batch_size: i64,
    #[serde(default = "default_worker_runtime_event_outbox_lock_secs")]
    pub event_outbox_lock_secs: i64,
    #[serde(default = "default_worker_runtime_event_outbox_max_attempts")]
    pub event_outbox_max_attempts: i32,
    #[serde(default = "default_worker_runtime_event_outbox_base_backoff_ms")]
    pub event_outbox_base_backoff_ms: u64,
    #[serde(default = "default_worker_runtime_event_outbox_max_backoff_ms")]
    pub event_outbox_max_backoff_ms: u64,
    #[serde(default = "default_worker_runtime_ops_rbac_audit_outbox_poll_interval_secs")]
    pub ops_rbac_audit_outbox_poll_interval_secs: u64,
    #[serde(default = "default_worker_runtime_kafka_dlq_retention_cleanup_worker_enabled")]
    pub kafka_dlq_retention_cleanup_worker_enabled: bool,
    #[serde(default = "default_worker_runtime_kafka_dlq_retention_cleanup_interval_secs")]
    pub kafka_dlq_retention_cleanup_interval_secs: u64,
    #[serde(default = "default_worker_runtime_kafka_dlq_retention_days")]
    pub kafka_dlq_retention_days: i64,
    #[serde(default = "default_worker_runtime_kafka_dlq_retention_cleanup_batch_size")]
    pub kafka_dlq_retention_cleanup_batch_size: i64,
    #[serde(
        default = "default_worker_runtime_kafka_readiness_pending_dlq_blocking_count_threshold"
    )]
    pub kafka_readiness_pending_dlq_blocking_count_threshold: u64,
    #[serde(
        default = "default_worker_runtime_kafka_readiness_pending_dlq_oldest_age_blocking_secs"
    )]
    pub kafka_readiness_pending_dlq_oldest_age_blocking_secs: u64,
    #[serde(
        default = "default_worker_runtime_kafka_readiness_pending_dlq_replay_rate_window_secs"
    )]
    pub kafka_readiness_pending_dlq_replay_rate_window_secs: u64,
    #[serde(
        default = "default_worker_runtime_kafka_readiness_pending_dlq_min_replay_actions_per_minute"
    )]
    pub kafka_readiness_pending_dlq_min_replay_actions_per_minute: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PaymentConfig {
    #[serde(default = "default_payment_verify_mode")]
    pub verify_mode: String,
    #[serde(default = "default_payment_apple_verify_url_prod")]
    pub apple_verify_url_prod: String,
    #[serde(default = "default_payment_apple_verify_url_sandbox")]
    pub apple_verify_url_sandbox: String,
    #[serde(default)]
    pub apple_shared_secret: String,
    #[serde(default = "default_payment_verify_timeout_ms")]
    pub verify_timeout_ms: u64,
}

impl Default for AiJudgeConfig {
    fn default() -> Self {
        Self {
            internal_key: default_ai_judge_internal_key(),
            style_mode: default_ai_judge_style_mode(),
            dispatch_enabled: false,
            service_base_url: default_ai_judge_service_base_url(),
            dispatch_path: default_ai_judge_dispatch_path(),
            dispatch_interval_secs: default_ai_judge_dispatch_interval_secs(),
            dispatch_batch_size: default_ai_judge_dispatch_batch_size(),
            dispatch_lock_secs: default_ai_judge_dispatch_lock_secs(),
            dispatch_retry_backoff_max_multiplier:
                default_ai_judge_dispatch_retry_backoff_max_multiplier(),
            dispatch_retry_jitter_ratio: default_ai_judge_dispatch_retry_jitter_ratio(),
            dispatch_timeout_ms: default_ai_judge_dispatch_timeout_ms(),
            dispatch_max_attempts: default_ai_judge_dispatch_max_attempts(),
            dispatch_callback_wait_secs: default_ai_judge_dispatch_callback_wait_secs(),
            alert_outbox_bridge_enabled: false,
            alert_outbox_poll_interval_secs: default_ai_judge_alert_outbox_poll_interval_secs(),
            alert_outbox_batch_size: default_ai_judge_alert_outbox_batch_size(),
            alert_outbox_path: default_ai_judge_alert_outbox_path(),
            alert_outbox_delivery_path: default_ai_judge_alert_outbox_delivery_path(),
            alert_outbox_timeout_ms: default_ai_judge_alert_outbox_timeout_ms(),
        }
    }
}

impl Default for WorkerRuntimeConfig {
    fn default() -> Self {
        Self {
            debate_lifecycle_worker_enabled: default_worker_runtime_debate_lifecycle_worker_enabled(
            ),
            ai_judge_dispatch_worker_enabled:
                default_worker_runtime_ai_judge_dispatch_worker_enabled(),
            ops_observability_worker_enabled:
                default_worker_runtime_ops_observability_worker_enabled(),
            ai_judge_alert_outbox_bridge_worker_enabled:
                default_worker_runtime_ai_judge_alert_outbox_bridge_worker_enabled(),
            event_outbox_relay_worker_enabled:
                default_worker_runtime_event_outbox_relay_worker_enabled(),
            ops_rbac_audit_outbox_worker_enabled:
                default_worker_runtime_ops_rbac_audit_outbox_worker_enabled(),
            debate_lifecycle_interval_secs: default_worker_runtime_debate_lifecycle_interval_secs(),
            debate_lifecycle_batch_size: default_worker_runtime_debate_lifecycle_batch_size(),
            ops_observability_interval_secs: default_worker_runtime_ops_observability_interval_secs(
            ),
            event_outbox_poll_interval_secs: default_worker_runtime_event_outbox_poll_interval_secs(
            ),
            event_outbox_batch_size: default_worker_runtime_event_outbox_batch_size(),
            event_outbox_lock_secs: default_worker_runtime_event_outbox_lock_secs(),
            event_outbox_max_attempts: default_worker_runtime_event_outbox_max_attempts(),
            event_outbox_base_backoff_ms: default_worker_runtime_event_outbox_base_backoff_ms(),
            event_outbox_max_backoff_ms: default_worker_runtime_event_outbox_max_backoff_ms(),
            ops_rbac_audit_outbox_poll_interval_secs:
                default_worker_runtime_ops_rbac_audit_outbox_poll_interval_secs(),
            kafka_dlq_retention_cleanup_worker_enabled:
                default_worker_runtime_kafka_dlq_retention_cleanup_worker_enabled(),
            kafka_dlq_retention_cleanup_interval_secs:
                default_worker_runtime_kafka_dlq_retention_cleanup_interval_secs(),
            kafka_dlq_retention_days: default_worker_runtime_kafka_dlq_retention_days(),
            kafka_dlq_retention_cleanup_batch_size:
                default_worker_runtime_kafka_dlq_retention_cleanup_batch_size(),
            kafka_readiness_pending_dlq_blocking_count_threshold:
                default_worker_runtime_kafka_readiness_pending_dlq_blocking_count_threshold(),
            kafka_readiness_pending_dlq_oldest_age_blocking_secs:
                default_worker_runtime_kafka_readiness_pending_dlq_oldest_age_blocking_secs(),
            kafka_readiness_pending_dlq_replay_rate_window_secs:
                default_worker_runtime_kafka_readiness_pending_dlq_replay_rate_window_secs(),
            kafka_readiness_pending_dlq_min_replay_actions_per_minute:
                default_worker_runtime_kafka_readiness_pending_dlq_min_replay_actions_per_minute(),
        }
    }
}

impl Default for KafkaConfig {
    fn default() -> Self {
        Self {
            enabled: false,
            brokers: default_kafka_brokers(),
            topic_prefix: default_kafka_topic_prefix(),
            client_id: default_kafka_client_id(),
            group_id: default_kafka_group_id(),
            consume_enabled: false,
            consume_topics: Vec::new(),
            producer_timeout_ms: default_kafka_timeout_ms(),
            consumer: KafkaConsumerConfig::default(),
        }
    }
}

impl Default for AnalyticsIngressConfig {
    fn default() -> Self {
        Self {
            enabled: default_analytics_ingress_enabled(),
            base_url: default_analytics_ingress_base_url(),
            timeout_ms: default_analytics_ingress_timeout_ms(),
        }
    }
}

impl Default for KafkaConsumerConfig {
    fn default() -> Self {
        Self {
            worker_enabled: false,
            worker_group_id: default_kafka_consumer_worker_group_id(),
            max_inflight: default_kafka_consumer_max_inflight(),
            retry_policy: default_kafka_consumer_retry_policy(),
        }
    }
}

impl Default for RedisConfig {
    fn default() -> Self {
        Self {
            enabled: false,
            url: default_redis_url(),
            pool_size: default_redis_pool_size(),
            key_prefix: default_redis_key_prefix(),
            default_ttl_secs: default_redis_default_ttl_secs(),
            startup_policy: default_redis_startup_policy(),
            healthcheck_timeout_ms: default_redis_healthcheck_timeout_ms(),
        }
    }
}

impl Default for PaymentConfig {
    fn default() -> Self {
        Self {
            verify_mode: default_payment_verify_mode(),
            apple_verify_url_prod: default_payment_apple_verify_url_prod(),
            apple_verify_url_sandbox: default_payment_apple_verify_url_sandbox(),
            apple_shared_secret: String::new(),
            verify_timeout_ms: default_payment_verify_timeout_ms(),
        }
    }
}

fn default_kafka_brokers() -> String {
    "127.0.0.1:9092".to_string()
}

fn default_kafka_topic_prefix() -> String {
    "echoisle".to_string()
}

fn default_kafka_client_id() -> String {
    "chat-server".to_string()
}

fn default_kafka_group_id() -> String {
    "chat-server-bootstrap".to_string()
}

fn default_kafka_timeout_ms() -> u64 {
    1500
}

fn default_kafka_consumer_worker_group_id() -> String {
    "chat-server-worker".to_string()
}

fn default_kafka_consumer_max_inflight() -> u64 {
    64
}

fn default_kafka_consumer_retry_policy() -> String {
    "exponential".to_string()
}

fn default_redis_url() -> String {
    "redis://127.0.0.1:6379/0".to_string()
}

fn default_redis_pool_size() -> u32 {
    32
}

fn default_redis_key_prefix() -> String {
    "echoisle".to_string()
}

fn default_redis_default_ttl_secs() -> u64 {
    300
}

fn default_redis_startup_policy() -> String {
    "fail_open".to_string()
}

fn default_redis_healthcheck_timeout_ms() -> u64 {
    500
}

fn default_ai_judge_internal_key() -> String {
    "dev-ai-internal-key".to_string()
}

fn default_ai_judge_style_mode() -> String {
    "rational".to_string()
}

fn default_ai_judge_service_base_url() -> String {
    "http://127.0.0.1:8787".to_string()
}

fn default_ai_judge_dispatch_path() -> String {
    "/internal/judge/v3/phase/dispatch".to_string()
}

fn default_ai_judge_dispatch_interval_secs() -> u64 {
    2
}

fn default_ai_judge_dispatch_batch_size() -> i64 {
    20
}

fn default_ai_judge_dispatch_lock_secs() -> i64 {
    30
}

fn default_ai_judge_dispatch_retry_backoff_max_multiplier() -> i64 {
    8
}

fn default_ai_judge_dispatch_retry_jitter_ratio() -> i64 {
    20
}

fn default_ai_judge_dispatch_timeout_ms() -> u64 {
    8_000
}

fn default_ai_judge_dispatch_max_attempts() -> i32 {
    3
}

fn default_ai_judge_dispatch_callback_wait_secs() -> i64 {
    60
}

fn default_ai_judge_alert_outbox_poll_interval_secs() -> u64 {
    5
}

fn default_ai_judge_alert_outbox_batch_size() -> u64 {
    50
}

fn default_ai_judge_alert_outbox_path() -> String {
    "/internal/judge/alerts/outbox".to_string()
}

fn default_ai_judge_alert_outbox_delivery_path() -> String {
    "/internal/judge/alerts/outbox/{event_id}/delivery".to_string()
}

fn default_ai_judge_alert_outbox_timeout_ms() -> u64 {
    5_000
}

fn default_analytics_ingress_enabled() -> bool {
    true
}

fn default_analytics_ingress_base_url() -> String {
    "http://127.0.0.1:6690".to_string()
}

fn default_analytics_ingress_timeout_ms() -> u64 {
    3_000
}

fn default_worker_runtime_debate_lifecycle_worker_enabled() -> bool {
    true
}

fn default_worker_runtime_ai_judge_dispatch_worker_enabled() -> bool {
    true
}

fn default_worker_runtime_ops_observability_worker_enabled() -> bool {
    true
}

fn default_worker_runtime_ai_judge_alert_outbox_bridge_worker_enabled() -> bool {
    true
}

fn default_worker_runtime_event_outbox_relay_worker_enabled() -> bool {
    true
}

fn default_worker_runtime_ops_rbac_audit_outbox_worker_enabled() -> bool {
    true
}

fn default_worker_runtime_debate_lifecycle_interval_secs() -> u64 {
    2
}

fn default_worker_runtime_debate_lifecycle_batch_size() -> i64 {
    200
}

fn default_worker_runtime_ops_observability_interval_secs() -> u64 {
    30
}

fn default_worker_runtime_event_outbox_poll_interval_secs() -> u64 {
    1
}

fn default_worker_runtime_event_outbox_batch_size() -> i64 {
    200
}

fn default_worker_runtime_event_outbox_lock_secs() -> i64 {
    30
}

fn default_worker_runtime_event_outbox_max_attempts() -> i32 {
    12
}

fn default_worker_runtime_event_outbox_base_backoff_ms() -> u64 {
    500
}

fn default_worker_runtime_event_outbox_max_backoff_ms() -> u64 {
    60_000
}

fn default_worker_runtime_ops_rbac_audit_outbox_poll_interval_secs() -> u64 {
    1
}

fn default_worker_runtime_kafka_dlq_retention_cleanup_worker_enabled() -> bool {
    true
}

fn default_worker_runtime_kafka_dlq_retention_cleanup_interval_secs() -> u64 {
    300
}

fn default_worker_runtime_kafka_dlq_retention_days() -> i64 {
    14
}

fn default_worker_runtime_kafka_dlq_retention_cleanup_batch_size() -> i64 {
    500
}

fn default_worker_runtime_kafka_readiness_pending_dlq_blocking_count_threshold() -> u64 {
    1
}

fn default_worker_runtime_kafka_readiness_pending_dlq_oldest_age_blocking_secs() -> u64 {
    300
}

fn default_worker_runtime_kafka_readiness_pending_dlq_replay_rate_window_secs() -> u64 {
    300
}

fn default_worker_runtime_kafka_readiness_pending_dlq_min_replay_actions_per_minute() -> f64 {
    0.0
}

fn default_payment_verify_mode() -> String {
    "apple".to_string()
}

fn default_payment_apple_verify_url_prod() -> String {
    "https://buy.itunes.apple.com/verifyReceipt".to_string()
}

fn default_payment_apple_verify_url_sandbox() -> String {
    "https://sandbox.itunes.apple.com/verifyReceipt".to_string()
}

fn default_payment_verify_timeout_ms() -> u64 {
    8_000
}

impl AppConfig {
    fn validate_for_runtime_env(&self, runtime_env: Option<&str>) -> Result<()> {
        if self.analytics.enabled && self.analytics.base_url.trim().is_empty() {
            bail!("analytics.base_url cannot be empty when analytics.enabled=true");
        }

        let payment_mode = normalize_payment_verify_mode(&self.payment.verify_mode);
        if payment_mode == "apple" {
            if self.payment.apple_verify_url_prod.trim().is_empty() {
                bail!("payment.apple_verify_url_prod cannot be empty when verify_mode=apple");
            }
            if self.payment.apple_verify_url_sandbox.trim().is_empty() {
                bail!("payment.apple_verify_url_sandbox cannot be empty when verify_mode=apple");
            }
        }

        if runtime_env.map(is_production_env).unwrap_or(false) && payment_mode == "mock" {
            bail!("payment.verify_mode=mock is forbidden when runtime env is production");
        }

        Ok(())
    }

    pub fn load() -> Result<Self> {
        let config: Self =
            load_yaml_with_fallback("chat.yml", "/etc/config/chat.yml", "CHAT_CONFIG")?;
        config.validate_for_runtime_env(runtime_env().as_deref())?;
        Ok(config)
    }
}

impl RedisConfig {
    pub fn startup_fail_closed(&self) -> bool {
        normalize_redis_startup_policy(&self.startup_policy) == "fail_closed"
    }

    pub fn startup_policy_label(&self) -> &'static str {
        normalize_redis_startup_policy(&self.startup_policy)
    }
}

fn normalize_payment_verify_mode(mode: &str) -> &str {
    match mode.trim().to_ascii_lowercase().as_str() {
        "mock" | "dev_mock" => "mock",
        _ => "apple",
    }
}

fn normalize_redis_startup_policy(mode: &str) -> &'static str {
    match mode.trim().to_ascii_lowercase().as_str() {
        "fail_closed" | "closed" | "strict" => "fail_closed",
        _ => "fail_open",
    }
}

fn runtime_env() -> Option<String> {
    for key in ["ECHOISLE_ENV", "APP_ENV", "RUST_ENV", "ENV"] {
        if let Ok(value) = env::var(key) {
            let normalized = value.trim();
            if !normalized.is_empty() {
                return Some(normalized.to_ascii_lowercase());
            }
        }
    }
    None
}

fn is_production_env(value: &str) -> bool {
    matches!(value.trim(), "prod" | "production")
}

#[cfg(test)]
mod tests {
    use super::*;

    fn base_config() -> AppConfig {
        AppConfig {
            server: ServerConfig {
                port: 6688,
                db_url: "postgres://test@localhost:5432/test".to_string(),
                base_dir: std::path::PathBuf::from("/tmp/chat_server_test"),
                forwarded_header_trust: ServerForwardedHeaderTrustConfig::default(),
            },
            auth: AuthConfig {
                sk: "sk".to_string(),
                pk: "pk".to_string(),
            },
            kafka: KafkaConfig::default(),
            redis: RedisConfig::default(),
            ai_judge: AiJudgeConfig::default(),
            analytics: AnalyticsIngressConfig::default(),
            worker_runtime: WorkerRuntimeConfig::default(),
            payment: PaymentConfig::default(),
        }
    }

    #[test]
    fn normalize_payment_verify_mode_should_be_fail_closed() {
        assert_eq!(normalize_payment_verify_mode("mock"), "mock");
        assert_eq!(normalize_payment_verify_mode("dev_mock"), "mock");
        assert_eq!(normalize_payment_verify_mode("apple"), "apple");
        assert_eq!(normalize_payment_verify_mode("production"), "apple");
        assert_eq!(normalize_payment_verify_mode(""), "apple");
        assert_eq!(normalize_payment_verify_mode("unknown"), "apple");
    }

    #[test]
    fn validate_for_runtime_env_should_reject_mock_in_production() {
        let mut config = base_config();
        config.payment.verify_mode = "mock".to_string();
        let err = config
            .validate_for_runtime_env(Some("production"))
            .expect_err("mock mode should be rejected in production");
        assert!(err
            .to_string()
            .contains("payment.verify_mode=mock is forbidden"));
    }

    #[test]
    fn validate_for_runtime_env_should_accept_mock_in_non_production() {
        let mut config = base_config();
        config.payment.verify_mode = "mock".to_string();
        config
            .validate_for_runtime_env(Some("development"))
            .expect("mock mode should be allowed in development");
    }

    #[test]
    fn validate_for_runtime_env_should_require_apple_urls_when_apple_mode() {
        let mut config = base_config();
        config.payment.verify_mode = "apple".to_string();
        config.payment.apple_verify_url_prod.clear();
        let err = config
            .validate_for_runtime_env(Some("production"))
            .expect_err("missing production url should fail");
        assert!(err
            .to_string()
            .contains("payment.apple_verify_url_prod cannot be empty"));
    }

    #[test]
    fn normalize_redis_startup_policy_should_be_fail_open_default() {
        assert_eq!(normalize_redis_startup_policy(""), "fail_open");
        assert_eq!(normalize_redis_startup_policy("unknown"), "fail_open");
        assert_eq!(normalize_redis_startup_policy("fail_open"), "fail_open");
        assert_eq!(normalize_redis_startup_policy("fail_closed"), "fail_closed");
        assert_eq!(normalize_redis_startup_policy("strict"), "fail_closed");
    }

    #[test]
    fn redis_config_startup_policy_helpers_should_work() {
        let mut cfg = RedisConfig::default();
        assert!(!cfg.startup_fail_closed());
        assert_eq!(cfg.startup_policy_label(), "fail_open");

        cfg.startup_policy = "fail_closed".to_string();
        assert!(cfg.startup_fail_closed());
        assert_eq!(cfg.startup_policy_label(), "fail_closed");
    }

    #[test]
    fn ai_judge_alert_outbox_defaults_should_be_stable() {
        let cfg = AiJudgeConfig::default();
        assert!(!cfg.alert_outbox_bridge_enabled);
        assert_eq!(cfg.alert_outbox_poll_interval_secs, 5);
        assert_eq!(cfg.alert_outbox_batch_size, 50);
        assert_eq!(cfg.alert_outbox_path, "/internal/judge/alerts/outbox");
        assert_eq!(
            cfg.alert_outbox_delivery_path,
            "/internal/judge/alerts/outbox/{event_id}/delivery"
        );
        assert_eq!(cfg.alert_outbox_timeout_ms, 5_000);
    }

    #[test]
    fn analytics_ingress_defaults_should_be_stable() {
        let cfg = AnalyticsIngressConfig::default();
        assert!(cfg.enabled);
        assert_eq!(cfg.base_url, "http://127.0.0.1:6690");
        assert_eq!(cfg.timeout_ms, 3_000);
    }

    #[test]
    fn validate_for_runtime_env_should_reject_empty_analytics_base_url_when_enabled() {
        let mut config = base_config();
        config.analytics.enabled = true;
        config.analytics.base_url = "  ".to_string();
        let err = config
            .validate_for_runtime_env(Some("development"))
            .expect_err("empty analytics base url should fail");
        assert!(err
            .to_string()
            .contains("analytics.base_url cannot be empty"));
    }

    #[test]
    fn worker_runtime_defaults_should_be_stable() {
        let cfg = WorkerRuntimeConfig::default();
        assert!(cfg.debate_lifecycle_worker_enabled);
        assert!(cfg.ai_judge_dispatch_worker_enabled);
        assert!(cfg.ops_observability_worker_enabled);
        assert!(cfg.ai_judge_alert_outbox_bridge_worker_enabled);
        assert!(cfg.event_outbox_relay_worker_enabled);
        assert!(cfg.ops_rbac_audit_outbox_worker_enabled);
        assert_eq!(cfg.debate_lifecycle_interval_secs, 2);
        assert_eq!(cfg.debate_lifecycle_batch_size, 200);
        assert_eq!(cfg.ops_observability_interval_secs, 30);
        assert_eq!(cfg.event_outbox_poll_interval_secs, 1);
        assert_eq!(cfg.event_outbox_batch_size, 200);
        assert_eq!(cfg.event_outbox_lock_secs, 30);
        assert_eq!(cfg.event_outbox_max_attempts, 12);
        assert_eq!(cfg.event_outbox_base_backoff_ms, 500);
        assert_eq!(cfg.event_outbox_max_backoff_ms, 60_000);
        assert_eq!(cfg.ops_rbac_audit_outbox_poll_interval_secs, 1);
        assert!(cfg.kafka_dlq_retention_cleanup_worker_enabled);
        assert_eq!(cfg.kafka_dlq_retention_cleanup_interval_secs, 300);
        assert_eq!(cfg.kafka_dlq_retention_days, 14);
        assert_eq!(cfg.kafka_dlq_retention_cleanup_batch_size, 500);
        assert_eq!(cfg.kafka_readiness_pending_dlq_blocking_count_threshold, 1);
        assert_eq!(
            cfg.kafka_readiness_pending_dlq_oldest_age_blocking_secs,
            300
        );
        assert_eq!(cfg.kafka_readiness_pending_dlq_replay_rate_window_secs, 300);
        assert!(
            (cfg.kafka_readiness_pending_dlq_min_replay_actions_per_minute - 0.0).abs()
                < f64::EPSILON
        );
    }
}
