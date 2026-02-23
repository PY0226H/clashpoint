use std::{sync::Arc, time::Duration};

use anyhow::Context;
use chrono::{DateTime, Utc};
use rdkafka::{
    consumer::{Consumer, StreamConsumer},
    producer::{FutureProducer, FutureRecord},
    util::Timeout,
    ClientConfig, Message,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tracing::{debug, info, warn};
use uuid::Uuid;

use crate::config::KafkaConfig;

pub const TOPIC_DEBATE_PARTICIPANT_JOINED: &str = "debate.participant.joined.v1";
pub const TOPIC_DEBATE_SESSION_STATUS_CHANGED: &str = "debate.session.status.changed.v1";

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct EventEnvelope {
    pub event_id: String,
    pub event_type: String,
    pub source: String,
    pub aggregate_id: String,
    pub occurred_at: DateTime<Utc>,
    pub payload: Value,
}

impl EventEnvelope {
    pub fn new(
        event_type: impl Into<String>,
        source: impl Into<String>,
        aggregate_id: impl Into<String>,
        payload: Value,
    ) -> Self {
        Self {
            event_id: Uuid::now_v7().to_string(),
            event_type: event_type.into(),
            source: source.into(),
            aggregate_id: aggregate_id.into(),
            occurred_at: Utc::now(),
            payload,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DebateParticipantJoinedEvent {
    pub ws_id: u64,
    pub session_id: u64,
    pub user_id: u64,
    pub side: String,
    pub pro_count: i32,
    pub con_count: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DebateSessionStatusChangedEvent {
    pub session_id: u64,
    pub from_status: String,
    pub to_status: String,
    pub changed_at: DateTime<Utc>,
}

#[derive(Clone)]
pub(crate) struct KafkaEventBus {
    producer: FutureProducer,
    config: KafkaConfig,
}

#[derive(Clone)]
pub(crate) enum EventBus {
    Disabled,
    Kafka(Arc<KafkaEventBus>),
}

impl EventBus {
    pub fn from_config(config: &KafkaConfig) -> anyhow::Result<Self> {
        if !config.enabled {
            return Ok(Self::Disabled);
        }

        let producer: FutureProducer = ClientConfig::new()
            .set("bootstrap.servers", &config.brokers)
            .set("client.id", &config.client_id)
            .set("message.timeout.ms", config.producer_timeout_ms.to_string())
            .create()
            .context("create kafka producer failed")?;

        let bus = Self::Kafka(Arc::new(KafkaEventBus {
            producer,
            config: config.clone(),
        }));
        info!(
            "kafka event bus enabled, brokers={}, topic_prefix={}",
            config.brokers, config.topic_prefix
        );
        Ok(bus)
    }

    pub async fn publish_debate_participant_joined(
        &self,
        event: DebateParticipantJoinedEvent,
    ) -> anyhow::Result<()> {
        let aggregate_id = format!("session:{}", event.session_id);
        let payload = serde_json::to_value(event)?;
        let envelope = EventEnvelope::new(
            "debate.participant.joined",
            "chat-server",
            aggregate_id,
            payload,
        );
        let key = envelope.aggregate_id.clone();
        self.publish(TOPIC_DEBATE_PARTICIPANT_JOINED, &key, &envelope)
            .await
    }

    pub async fn publish_debate_session_status_changed(
        &self,
        event: DebateSessionStatusChangedEvent,
    ) -> anyhow::Result<()> {
        let aggregate_id = format!("session:{}", event.session_id);
        let payload = serde_json::to_value(event)?;
        let envelope = EventEnvelope::new(
            "debate.session.status.changed",
            "chat-server",
            aggregate_id,
            payload,
        );
        let key = envelope.aggregate_id.clone();
        self.publish(TOPIC_DEBATE_SESSION_STATUS_CHANGED, &key, &envelope)
            .await
    }

    pub async fn publish(
        &self,
        base_topic: &str,
        key: &str,
        event: &EventEnvelope,
    ) -> anyhow::Result<()> {
        match self {
            EventBus::Disabled => Ok(()),
            EventBus::Kafka(bus) => {
                let topic = bus.config.topic_name(base_topic);
                let payload = serde_json::to_string(event)?;
                bus.producer
                    .send(
                        FutureRecord::to(&topic).key(key).payload(&payload),
                        Timeout::After(Duration::from_millis(bus.config.producer_timeout_ms)),
                    )
                    .await
                    .map_err(|(e, _)| anyhow::anyhow!("kafka publish to {} failed: {}", topic, e))
                    .map(|delivery| {
                        debug!(
                            "kafka published topic={} partition={} offset={}",
                            topic, delivery.0, delivery.1
                        );
                    })
            }
        }
    }

    pub fn maybe_spawn_bootstrap_consumer(&self) -> anyhow::Result<()> {
        let EventBus::Kafka(bus) = self else {
            return Ok(());
        };
        if !bus.config.consume_enabled {
            return Ok(());
        }

        let topics = if bus.config.consume_topics.is_empty() {
            vec![
                bus.config.topic_name(TOPIC_DEBATE_PARTICIPANT_JOINED),
                bus.config.topic_name(TOPIC_DEBATE_SESSION_STATUS_CHANGED),
            ]
        } else {
            bus.config
                .consume_topics
                .iter()
                .map(|topic| bus.config.topic_name(topic))
                .collect()
        };

        let consumer: StreamConsumer = ClientConfig::new()
            .set("bootstrap.servers", &bus.config.brokers)
            .set("group.id", &bus.config.group_id)
            .set("client.id", format!("{}-consumer", bus.config.client_id))
            .set("enable.partition.eof", "false")
            .set("session.timeout.ms", "6000")
            .set("enable.auto.commit", "true")
            .create()
            .context("create kafka consumer failed")?;
        let topic_refs: Vec<&str> = topics.iter().map(String::as_str).collect();
        consumer
            .subscribe(&topic_refs)
            .context("subscribe kafka topics failed")?;

        tokio::spawn(async move {
            info!("kafka bootstrap consumer started, topics={:?}", topics);
            loop {
                match consumer.recv().await {
                    Err(e) => warn!("kafka consume failed: {}", e),
                    Ok(msg) => {
                        let payload = match msg.payload_view::<str>() {
                            None => "",
                            Some(Ok(v)) => v,
                            Some(Err(_)) => "<invalid-utf8>",
                        };
                        info!(
                            "kafka consumed topic={} partition={} offset={} key={:?}",
                            msg.topic(),
                            msg.partition(),
                            msg.offset(),
                            msg.key().map(|v| String::from_utf8_lossy(v).to_string())
                        );
                        debug!("kafka message payload={}", payload);
                    }
                }
            }
        });

        Ok(())
    }
}

impl KafkaConfig {
    pub fn topic_name(&self, base_topic: &str) -> String {
        let prefix = self.topic_prefix.trim();
        if prefix.is_empty() {
            base_topic.to_string()
        } else {
            format!("{}.{}", prefix, base_topic)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn kafka_topic_name_should_apply_prefix() {
        let cfg = KafkaConfig {
            topic_prefix: "aicomm".to_string(),
            ..Default::default()
        };
        assert_eq!(
            cfg.topic_name(TOPIC_DEBATE_PARTICIPANT_JOINED),
            "aicomm.debate.participant.joined.v1"
        );
        assert_eq!(
            cfg.topic_name(TOPIC_DEBATE_SESSION_STATUS_CHANGED),
            "aicomm.debate.session.status.changed.v1"
        );
    }

    #[test]
    fn event_envelope_new_should_fill_required_fields() {
        let event = EventEnvelope::new(
            "debate.participant.joined",
            "chat-server",
            "session:42",
            serde_json::json!({"sessionId": 42}),
        );
        assert!(!event.event_id.is_empty());
        assert_eq!(event.event_type, "debate.participant.joined");
        assert_eq!(event.source, "chat-server");
        assert_eq!(event.aggregate_id, "session:42");
        assert_eq!(event.payload["sessionId"], 42);
    }
}
