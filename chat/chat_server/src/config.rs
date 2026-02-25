use std::{env, fs::File, path::PathBuf};

use anyhow::{bail, Result};
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct AppConfig {
    pub server: ServerConfig,
    pub auth: AuthConfig,
    #[serde(default)]
    pub kafka: KafkaConfig,
    #[serde(default)]
    pub ai_judge: AiJudgeConfig,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct AuthConfig {
    pub sk: String,
    pub pk: String,
}

#[derive(Debug, Serialize, Deserialize)]
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

impl AppConfig {
    pub fn load() -> Result<Self> {
        // read from  ./app.yml, or /etc/config/app.yml, or from env CHAT_CONFIG
        let ret = match (
            File::open("chat.yml"),
            File::open("/etc/config/chat.yml"),
            env::var("CHAT_CONFIG"),
        ) {
            (Ok(reader), _, _) => serde_yaml::from_reader(reader),
            (_, Ok(reader), _) => serde_yaml::from_reader(reader),
            (_, _, Ok(path)) => serde_yaml::from_reader(File::open(path)?),
            _ => bail!("Config file not found"),
        };
        Ok(ret?)
    }
}
