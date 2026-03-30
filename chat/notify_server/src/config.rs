use anyhow::Result;
use chat_core::load_yaml_with_fallback;
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct AppConfig {
    pub server: ServerConfig,
    pub auth: AuthConfig,
    #[serde(default)]
    pub kafka: KafkaConfig,
    #[serde(default)]
    pub redis: RedisConfig,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct AuthConfig {
    pub pk: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ServerConfig {
    pub port: u16,
    pub db_url: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KafkaConfig {
    #[serde(default)]
    pub enabled: bool,
    #[serde(default = "default_kafka_disable_pg_listener")]
    pub disable_pg_listener: bool,
    #[serde(default = "default_kafka_brokers")]
    pub brokers: String,
    #[serde(default = "default_kafka_topic_prefix")]
    pub topic_prefix: String,
    #[serde(default = "default_kafka_client_id")]
    pub client_id: String,
    #[serde(default = "default_kafka_group_id")]
    pub group_id: String,
    #[serde(default)]
    pub consume_topics: Vec<String>,
}

impl Default for KafkaConfig {
    fn default() -> Self {
        Self {
            enabled: false,
            disable_pg_listener: default_kafka_disable_pg_listener(),
            brokers: default_kafka_brokers(),
            topic_prefix: default_kafka_topic_prefix(),
            client_id: default_kafka_client_id(),
            group_id: default_kafka_group_id(),
            consume_topics: vec![],
        }
    }
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
        }
    }
}

fn default_redis_url() -> String {
    "redis://127.0.0.1:6379/1".to_string()
}

fn default_redis_pool_size() -> u32 {
    16
}

fn default_redis_key_prefix() -> String {
    "echoisle_notify".to_string()
}

fn default_redis_default_ttl_secs() -> u64 {
    300
}

fn default_redis_startup_policy() -> String {
    "fail_open".to_string()
}

fn default_kafka_disable_pg_listener() -> bool {
    false
}

fn default_kafka_brokers() -> String {
    "127.0.0.1:9092".to_string()
}

fn default_kafka_topic_prefix() -> String {
    String::new()
}

fn default_kafka_client_id() -> String {
    "notify-server".to_string()
}

fn default_kafka_group_id() -> String {
    "notify-server-group".to_string()
}

impl AppConfig {
    pub fn load() -> Result<Self> {
        load_yaml_with_fallback("notify.yml", "/etc/config/notify.yml", "NOTIFY_CONFIG")
    }
}
