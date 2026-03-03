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
    pub ai_judge: AiJudgeConfig,
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
    "aicomm".to_string()
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
    "/internal/judge/dispatch".to_string()
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

fn normalize_payment_verify_mode(mode: &str) -> &str {
    match mode.trim().to_ascii_lowercase().as_str() {
        "mock" | "dev_mock" => "mock",
        _ => "apple",
    }
}

fn runtime_env() -> Option<String> {
    for key in ["AICOMM_ENV", "APP_ENV", "RUST_ENV", "ENV"] {
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
            },
            auth: AuthConfig {
                sk: "sk".to_string(),
                pk: "pk".to_string(),
            },
            kafka: KafkaConfig::default(),
            ai_judge: AiJudgeConfig::default(),
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
}
