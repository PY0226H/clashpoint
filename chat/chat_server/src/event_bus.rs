use std::{
    sync::{
        atomic::{AtomicU64, Ordering},
        Arc,
    },
    time::Duration,
};

use anyhow::Context;
use chrono::{DateTime, Utc};
use rdkafka::{
    consumer::{CommitMode, Consumer, StreamConsumer},
    producer::{FutureProducer, FutureRecord},
    util::Timeout,
    ClientConfig, Message,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sqlx::{FromRow, PgPool, Postgres, Transaction};
use tracing::{debug, info, warn};
use uuid::Uuid;

use crate::config::{KafkaConfig, WorkerRuntimeConfig};

pub const TOPIC_DEBATE_PARTICIPANT_JOINED: &str = "debate.participant.joined.v1";
pub const TOPIC_DEBATE_SESSION_STATUS_CHANGED: &str = "debate.session.status.changed.v1";
pub const TOPIC_DEBATE_MESSAGE_PINNED: &str = "debate.message.pinned.v1";

const OUTBOX_STATUS_PENDING: &str = "pending";
const OUTBOX_STATUS_SENDING: &str = "sending";
const OUTBOX_STATUS_SENT: &str = "sent";
const OUTBOX_STATUS_FAILED: &str = "failed";
const OUTBOX_ERROR_MAX_LEN: usize = 1000;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[allow(clippy::enum_variant_names)]
pub enum DomainEvent {
    DebateParticipantJoined(DebateParticipantJoinedEvent),
    DebateSessionStatusChanged(DebateSessionStatusChangedEvent),
    DebateMessagePinned(DebateMessagePinnedEvent),
}

impl DomainEvent {
    fn into_message(self) -> anyhow::Result<OutboxMessage> {
        match self {
            Self::DebateParticipantJoined(event) => build_outbox_message(
                TOPIC_DEBATE_PARTICIPANT_JOINED,
                "debate.participant.joined",
                format!("session:{}", event.session_id),
                Utc::now(),
                serde_json::to_value(event)?,
            ),
            Self::DebateSessionStatusChanged(event) => build_outbox_message(
                TOPIC_DEBATE_SESSION_STATUS_CHANGED,
                "debate.session.status.changed",
                format!("session:{}", event.session_id),
                event.changed_at,
                serde_json::to_value(event)?,
            ),
            Self::DebateMessagePinned(event) => build_outbox_message(
                TOPIC_DEBATE_MESSAGE_PINNED,
                "debate.message.pinned",
                format!("session:{}", event.session_id),
                event.pinned_at,
                serde_json::to_value(event)?,
            ),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OutboxMessage {
    pub event_id: String,
    pub event_type: String,
    pub source: String,
    pub aggregate_id: String,
    pub topic: String,
    pub key: String,
    pub payload: Value,
    pub occurred_at: DateTime<Utc>,
}

#[derive(Debug, Clone)]
pub struct EventOutboxRelayConfig {
    pub batch_size: i64,
    pub lock_secs: i64,
    pub max_attempts: i32,
    pub base_backoff_ms: u64,
    pub max_backoff_ms: u64,
}

impl EventOutboxRelayConfig {
    pub fn from_worker_runtime(cfg: &WorkerRuntimeConfig) -> Self {
        Self {
            batch_size: cfg.event_outbox_batch_size.max(1),
            lock_secs: cfg.event_outbox_lock_secs.max(1),
            max_attempts: cfg.event_outbox_max_attempts.max(1),
            base_backoff_ms: cfg.event_outbox_base_backoff_ms.max(1),
            max_backoff_ms: cfg
                .event_outbox_max_backoff_ms
                .max(cfg.event_outbox_base_backoff_ms.max(1)),
        }
    }
}

#[derive(Debug, Default, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct EventOutboxRelayReport {
    pub claimed: usize,
    pub sent: usize,
    pub retried: usize,
    pub failed: usize,
    pub dead_letter: usize,
}

#[derive(Debug, Default)]
pub struct EventOutboxRelayMetrics {
    tick_success_total: AtomicU64,
    tick_error_total: AtomicU64,
    claimed_total: AtomicU64,
    sent_total: AtomicU64,
    retried_total: AtomicU64,
    failed_total: AtomicU64,
    dead_letter_total: AtomicU64,
}

impl EventOutboxRelayMetrics {
    pub(crate) fn observe_tick_success(&self, report: &EventOutboxRelayReport) {
        self.tick_success_total.fetch_add(1, Ordering::Relaxed);
        self.claimed_total
            .fetch_add(report.claimed as u64, Ordering::Relaxed);
        self.sent_total
            .fetch_add(report.sent as u64, Ordering::Relaxed);
        self.retried_total
            .fetch_add(report.retried as u64, Ordering::Relaxed);
        self.failed_total
            .fetch_add(report.failed as u64, Ordering::Relaxed);
        self.dead_letter_total
            .fetch_add(report.dead_letter as u64, Ordering::Relaxed);
    }

    pub(crate) fn observe_tick_error(&self) {
        self.tick_error_total.fetch_add(1, Ordering::Relaxed);
    }
}

pub trait EventPublisher {
    async fn enqueue_in_tx(
        &self,
        tx: &mut Transaction<'_, Postgres>,
        event: DomainEvent,
    ) -> anyhow::Result<OutboxMessage>;

    #[allow(dead_code)]
    async fn publish_direct(&self, event: DomainEvent) -> anyhow::Result<()>;
}

fn build_outbox_message(
    topic: &str,
    event_type: &str,
    aggregate_id: String,
    occurred_at: DateTime<Utc>,
    event_payload: Value,
) -> anyhow::Result<OutboxMessage> {
    let envelope = EventEnvelope::new(
        event_type,
        "chat-server",
        aggregate_id.clone(),
        event_payload,
    );
    let key = envelope.aggregate_id.clone();
    let payload = serde_json::to_value(&envelope)?;
    Ok(OutboxMessage {
        event_id: envelope.event_id,
        event_type: envelope.event_type,
        source: envelope.source,
        aggregate_id,
        topic: topic.to_string(),
        key,
        payload,
        occurred_at,
    })
}

#[derive(Debug, FromRow)]
struct ClaimedOutboxRow {
    id: i64,
    event_id: String,
    topic: String,
    partition_key: String,
    payload: Value,
    attempts: i32,
}

async fn mark_outbox_rows_reaching_max_attempts(
    pool: &PgPool,
    max_attempts: i32,
) -> anyhow::Result<usize> {
    let affected = sqlx::query(
        r#"
        UPDATE event_outbox
        SET status = $1,
            locked_until = NULL,
            updated_at = NOW(),
            last_error = COALESCE(NULLIF(last_error, ''), 'max attempts exceeded before relay')
        WHERE attempts >= $2
          AND (
                status = $3
                OR (
                    status = $4
                    AND locked_until IS NOT NULL
                    AND locked_until <= NOW()
                )
              )
        "#,
    )
    .bind(OUTBOX_STATUS_FAILED)
    .bind(max_attempts)
    .bind(OUTBOX_STATUS_PENDING)
    .bind(OUTBOX_STATUS_SENDING)
    .execute(pool)
    .await?
    .rows_affected() as usize;
    Ok(affected)
}

async fn claim_due_outbox_rows(
    pool: &PgPool,
    config: &EventOutboxRelayConfig,
) -> anyhow::Result<Vec<ClaimedOutboxRow>> {
    let rows = sqlx::query_as::<_, ClaimedOutboxRow>(
        r#"
        WITH due AS (
            SELECT id
            FROM event_outbox
            WHERE (
                    (status = $1 AND available_at <= NOW())
                    OR (status = $2 AND locked_until IS NOT NULL AND locked_until <= NOW())
                  )
              AND attempts < $3
            ORDER BY available_at ASC, id ASC
            LIMIT $4
            FOR UPDATE SKIP LOCKED
        )
        UPDATE event_outbox o
        SET status = $2,
            attempts = o.attempts + 1,
            locked_until = NOW() + ($5::bigint * INTERVAL '1 second'),
            updated_at = NOW()
        FROM due
        WHERE o.id = due.id
        RETURNING o.id, o.event_id, o.topic, o.partition_key, o.payload, o.attempts
        "#,
    )
    .bind(OUTBOX_STATUS_PENDING)
    .bind(OUTBOX_STATUS_SENDING)
    .bind(config.max_attempts)
    .bind(config.batch_size)
    .bind(config.lock_secs)
    .fetch_all(pool)
    .await?;
    Ok(rows)
}

async fn mark_outbox_row_sent(pool: &PgPool, id: i64) -> anyhow::Result<()> {
    sqlx::query(
        r#"
        UPDATE event_outbox
        SET status = $2,
            locked_until = NULL,
            sent_at = NOW(),
            last_error = NULL,
            updated_at = NOW()
        WHERE id = $1
        "#,
    )
    .bind(id)
    .bind(OUTBOX_STATUS_SENT)
    .execute(pool)
    .await?;
    Ok(())
}

async fn mark_outbox_row_failed(pool: &PgPool, id: i64, last_error: &str) -> anyhow::Result<()> {
    sqlx::query(
        r#"
        UPDATE event_outbox
        SET status = $2,
            locked_until = NULL,
            last_error = $3,
            updated_at = NOW()
        WHERE id = $1
        "#,
    )
    .bind(id)
    .bind(OUTBOX_STATUS_FAILED)
    .bind(last_error)
    .execute(pool)
    .await?;
    Ok(())
}

async fn reschedule_outbox_row(
    pool: &PgPool,
    id: i64,
    backoff_ms: u64,
    last_error: &str,
) -> anyhow::Result<()> {
    sqlx::query(
        r#"
        UPDATE event_outbox
        SET status = $2,
            available_at = NOW() + ($3::bigint * INTERVAL '1 millisecond'),
            locked_until = NULL,
            last_error = $4,
            updated_at = NOW()
        WHERE id = $1
        "#,
    )
    .bind(id)
    .bind(OUTBOX_STATUS_PENDING)
    .bind(backoff_ms as i64)
    .bind(last_error)
    .execute(pool)
    .await?;
    Ok(())
}

fn sanitize_outbox_error(err: &anyhow::Error) -> String {
    let mut text = err.to_string().trim().to_string();
    if text.len() > OUTBOX_ERROR_MAX_LEN {
        text.truncate(OUTBOX_ERROR_MAX_LEN);
    }
    text
}

fn relay_backoff_ms(attempts: i32, config: &EventOutboxRelayConfig) -> u64 {
    let attempt = attempts.max(1) as u32;
    let pow = attempt.saturating_sub(1).min(16);
    let scaled = config.base_backoff_ms.saturating_mul(1_u64 << pow);
    scaled.min(config.max_backoff_ms).max(1)
}
#[derive(Debug, Clone, Copy, Eq, PartialEq)]
enum ConsumeLedgerStatus {
    Succeeded,
    Failed,
}

impl ConsumeLedgerStatus {
    fn as_str(self) -> &'static str {
        match self {
            Self::Succeeded => "succeeded",
            Self::Failed => "failed",
        }
    }

    fn from_db(status: &str) -> Option<Self> {
        match status.trim().to_ascii_lowercase().as_str() {
            "succeeded" => Some(Self::Succeeded),
            "failed" => Some(Self::Failed),
            _ => None,
        }
    }
}

#[derive(Debug, Clone, Copy, Eq, PartialEq)]
enum KafkaDlqStatus {
    Pending,
    Replayed,
    Discarded,
}

impl KafkaDlqStatus {
    fn as_str(self) -> &'static str {
        match self {
            Self::Pending => "pending",
            Self::Replayed => "replayed",
            Self::Discarded => "discarded",
        }
    }
}

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

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DebateMessagePinnedEvent {
    pub session_id: u64,
    pub message_id: u64,
    pub user_id: u64,
    pub ledger_id: u64,
    pub cost_coins: i64,
    pub pin_seconds: i32,
    pub pinned_at: DateTime<Utc>,
    pub expires_at: DateTime<Utc>,
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

    async fn publish_payload(
        &self,
        base_topic: &str,
        key: &str,
        payload: &Value,
    ) -> anyhow::Result<()> {
        match self {
            EventBus::Disabled => Ok(()),
            EventBus::Kafka(bus) => {
                let topic = bus.config.topic_name(base_topic);
                let payload = serde_json::to_string(payload)?;
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

    pub async fn relay_outbox_once(
        &self,
        pool: &PgPool,
        config: &EventOutboxRelayConfig,
    ) -> anyhow::Result<EventOutboxRelayReport> {
        if matches!(self, EventBus::Disabled) {
            return Ok(EventOutboxRelayReport::default());
        }

        let mut report = EventOutboxRelayReport {
            dead_letter: mark_outbox_rows_reaching_max_attempts(pool, config.max_attempts).await?,
            ..Default::default()
        };
        let claimed = claim_due_outbox_rows(pool, config).await?;
        report.claimed = claimed.len();

        for row in claimed {
            match self
                .publish_payload(&row.topic, &row.partition_key, &row.payload)
                .await
            {
                Ok(()) => {
                    mark_outbox_row_sent(pool, row.id).await?;
                    report.sent += 1;
                }
                Err(err) => {
                    report.failed += 1;
                    let error_message = sanitize_outbox_error(&err);
                    if row.attempts >= config.max_attempts {
                        mark_outbox_row_failed(pool, row.id, &error_message).await?;
                        report.dead_letter += 1;
                        warn!(
                            event_id = row.event_id,
                            topic = row.topic,
                            attempts = row.attempts,
                            "event outbox delivery exhausted retries: {}",
                            error_message
                        );
                    } else {
                        let backoff_ms = relay_backoff_ms(row.attempts, config);
                        reschedule_outbox_row(pool, row.id, backoff_ms, &error_message).await?;
                        report.retried += 1;
                        warn!(
                            event_id = row.event_id,
                            topic = row.topic,
                            attempts = row.attempts,
                            backoff_ms,
                            "event outbox delivery failed and scheduled retry: {}",
                            error_message
                        );
                    }
                }
            }
        }

        Ok(report)
    }

    pub fn maybe_spawn_consumer_worker(&self, pool: PgPool) -> anyhow::Result<()> {
        let EventBus::Kafka(bus) = self else {
            return Ok(());
        };
        if !kafka_worker_enabled(&bus.config) {
            return Ok(());
        }

        let topics = if bus.config.consume_topics.is_empty() {
            vec![
                bus.config.topic_name(TOPIC_DEBATE_PARTICIPANT_JOINED),
                bus.config.topic_name(TOPIC_DEBATE_SESSION_STATUS_CHANGED),
                bus.config.topic_name(TOPIC_DEBATE_MESSAGE_PINNED),
            ]
        } else {
            bus.config
                .consume_topics
                .iter()
                .map(|topic| bus.config.topic_name(topic))
                .collect()
        };
        let worker_group_id = if bus.config.consumer.worker_group_id.trim().is_empty() {
            bus.config.group_id.clone()
        } else {
            bus.config.consumer.worker_group_id.clone()
        };
        let retry_policy = WorkerRetryPolicy::from_config(&bus.config);

        let consumer: StreamConsumer = ClientConfig::new()
            .set("bootstrap.servers", &bus.config.brokers)
            .set("group.id", &worker_group_id)
            .set("client.id", format!("{}-consumer", bus.config.client_id))
            .set("enable.partition.eof", "false")
            .set("session.timeout.ms", "6000")
            .set("enable.auto.commit", "false")
            .create()
            .context("create kafka consumer failed")?;
        let topic_refs: Vec<&str> = topics.iter().map(String::as_str).collect();
        consumer
            .subscribe(&topic_refs)
            .context("subscribe kafka topics failed")?;

        tokio::spawn(async move {
            info!(
                "kafka consumer worker started, group_id={}, topics={:?}",
                worker_group_id, topics
            );
            loop {
                match consumer.recv().await {
                    Err(e) => warn!("kafka consume failed: {}", e),
                    Ok(msg) => {
                        let topic = msg.topic().to_string();
                        let partition = msg.partition();
                        let offset = msg.offset();
                        let key = msg.key().map(|v| String::from_utf8_lossy(v).to_string());
                        let payload = match msg.payload_view::<str>() {
                            None => None,
                            Some(Ok(v)) => Some(v),
                            Some(Err(_)) => None,
                        };
                        let outcome = consume_worker_message(
                            &pool,
                            &worker_group_id,
                            &topic,
                            partition,
                            offset,
                            payload,
                            retry_policy,
                        )
                        .await;
                        match outcome {
                            Ok(ret) => {
                                if ret.should_commit {
                                    if let Err(err) =
                                        consumer.commit_message(&msg, CommitMode::Async)
                                    {
                                        warn!(
                                            "kafka commit failed topic={} partition={} offset={}: {}",
                                            topic, partition, offset, err
                                        );
                                    } else {
                                        info!(
                                            "kafka worker consumed topic={} partition={} offset={} key={:?} outcome={}",
                                            topic, partition, offset, key, ret.outcome
                                        );
                                    }
                                } else {
                                    warn!(
                                        "kafka worker retry scheduled topic={} partition={} offset={} key={:?} backoff_ms={} outcome={}",
                                        topic,
                                        partition,
                                        offset,
                                        key,
                                        ret.retry_backoff_ms,
                                        ret.outcome
                                    );
                                    tokio::time::sleep(Duration::from_millis(ret.retry_backoff_ms))
                                        .await;
                                }
                            }
                            Err(err) => {
                                warn!(
                                    "kafka worker process failed topic={} partition={} offset={} key={:?}: {}",
                                    topic, partition, offset, key, err
                                );
                            }
                        }
                    }
                }
            }
        });

        Ok(())
    }
}

impl EventPublisher for EventBus {
    async fn enqueue_in_tx(
        &self,
        tx: &mut Transaction<'_, Postgres>,
        event: DomainEvent,
    ) -> anyhow::Result<OutboxMessage> {
        let message = event.into_message()?;
        if matches!(self, EventBus::Disabled) {
            return Ok(message);
        }

        sqlx::query(
            r#"
            INSERT INTO event_outbox(
                event_id, event_type, source, aggregate_id,
                topic, partition_key, payload, occurred_at,
                status, attempts, available_at, locked_until,
                last_error, sent_at, created_at, updated_at
            )
            VALUES (
                $1, $2, $3, $4,
                $5, $6, $7, $8,
                $9, 0, NOW(), NULL,
                NULL, NULL, NOW(), NOW()
            )
            "#,
        )
        .bind(&message.event_id)
        .bind(&message.event_type)
        .bind(&message.source)
        .bind(&message.aggregate_id)
        .bind(&message.topic)
        .bind(&message.key)
        .bind(&message.payload)
        .bind(message.occurred_at)
        .bind(OUTBOX_STATUS_PENDING)
        .execute(&mut **tx)
        .await?;
        Ok(message)
    }

    async fn publish_direct(&self, event: DomainEvent) -> anyhow::Result<()> {
        let message = event.into_message()?;
        self.publish_payload(&message.topic, &message.key, &message.payload)
            .await
    }
}

#[derive(Debug, Clone, Copy)]
enum ConsumeProcessOutcome {
    Succeeded,
    Retrying,
    Failed,
    Duplicated,
}

impl std::fmt::Display for ConsumeProcessOutcome {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Succeeded => write!(f, "succeeded"),
            Self::Retrying => write!(f, "retrying"),
            Self::Failed => write!(f, "failed"),
            Self::Duplicated => write!(f, "duplicated"),
        }
    }
}

#[derive(Debug)]
enum BusinessProcessOutcome {
    Succeeded,
}

#[derive(Debug, Clone, Copy)]
struct WorkerRetryPolicy {
    max_attempts: i32,
    base_backoff_ms: u64,
    max_backoff_ms: u64,
}

impl WorkerRetryPolicy {
    fn from_config(config: &KafkaConfig) -> Self {
        let raw = config.consumer.retry_policy.trim().to_lowercase();
        let max_attempts = raw
            .split(':')
            .nth(1)
            .and_then(|v| v.parse::<i32>().ok())
            .map(|v| v.clamp(1, 100))
            .unwrap_or(5);
        if raw.starts_with("fixed") {
            return Self {
                max_attempts,
                base_backoff_ms: 500,
                max_backoff_ms: 500,
            };
        }
        Self {
            max_attempts,
            base_backoff_ms: 250,
            max_backoff_ms: 8000,
        }
    }

    fn backoff_ms(self, failure_count: i32) -> u64 {
        let failure_count = failure_count.max(1) as u32;
        let pow = failure_count.saturating_sub(1).min(8);
        let base = self.base_backoff_ms.saturating_mul(1_u64 << pow);
        base.min(self.max_backoff_ms).max(50)
    }
}

#[derive(Debug, Clone)]
pub(crate) struct WorkerEnvelopeMeta {
    pub consumer_group: String,
    pub topic: String,
    pub partition: i32,
    pub offset: i64,
}

#[derive(Debug, Clone)]
pub(crate) enum WorkerProcessOutcome {
    Succeeded,
    Duplicated,
}

#[derive(Debug, Clone, Copy)]
struct ConsumeWorkerResult {
    outcome: ConsumeProcessOutcome,
    should_commit: bool,
    retry_backoff_ms: u64,
}

fn kafka_worker_enabled(config: &KafkaConfig) -> bool {
    config.consume_enabled || config.consumer.worker_enabled
}

fn fallback_event_id(topic: &str, partition: i32, offset: i64) -> String {
    format!("{topic}:{partition}:{offset}")
}

async fn consume_worker_message(
    pool: &PgPool,
    consumer_group: &str,
    topic: &str,
    partition: i32,
    offset: i64,
    payload: Option<&str>,
    retry_policy: WorkerRetryPolicy,
) -> anyhow::Result<ConsumeWorkerResult> {
    let payload_text = payload.unwrap_or_default();
    let meta = WorkerEnvelopeMeta {
        consumer_group: consumer_group.to_string(),
        topic: topic.to_string(),
        partition,
        offset,
    };
    let envelope = match serde_json::from_str::<EventEnvelope>(payload_text) {
        Ok(v) => v,
        Err(err) => {
            let row = FailedConsumeRow {
                consumer_group: consumer_group.to_string(),
                topic: topic.to_string(),
                partition,
                offset,
                event_id: fallback_event_id(topic, partition, offset),
                event_type: "invalid.envelope".to_string(),
                aggregate_id: String::new(),
                payload: serde_json::json!({ "raw": payload_text }),
                error_message: format!("decode envelope failed: {err}"),
            };
            persist_failed_ledger_row(pool, &row).await?;
            let _ = upsert_kafka_dlq_failure(pool, &row).await?;
            return Ok(ConsumeWorkerResult {
                outcome: ConsumeProcessOutcome::Failed,
                should_commit: true,
                retry_backoff_ms: 0,
            });
        }
    };

    match process_worker_envelope(pool, &meta, &envelope).await {
        Ok(WorkerProcessOutcome::Succeeded) => {
            mark_kafka_dlq_replayed(pool, &meta.consumer_group, &envelope.event_id).await?;
            Ok(ConsumeWorkerResult {
                outcome: ConsumeProcessOutcome::Succeeded,
                should_commit: true,
                retry_backoff_ms: 0,
            })
        }
        Ok(WorkerProcessOutcome::Duplicated) => {
            mark_kafka_dlq_replayed(pool, &meta.consumer_group, &envelope.event_id).await?;
            Ok(ConsumeWorkerResult {
                outcome: ConsumeProcessOutcome::Duplicated,
                should_commit: true,
                retry_backoff_ms: 0,
            })
        }
        Err(err) => {
            let row = FailedConsumeRow {
                consumer_group: meta.consumer_group.clone(),
                topic: meta.topic.clone(),
                partition: meta.partition,
                offset: meta.offset,
                event_id: envelope.event_id.clone(),
                event_type: envelope.event_type.clone(),
                aggregate_id: envelope.aggregate_id.clone(),
                payload: serde_json::to_value(&envelope).unwrap_or(Value::Null),
                error_message: format!("retryable worker error: {err}"),
            };
            let failure_count = upsert_kafka_dlq_failure(pool, &row).await?;
            let should_commit = failure_count >= retry_policy.max_attempts;
            let retry_backoff_ms = if should_commit {
                0
            } else {
                retry_policy.backoff_ms(failure_count)
            };
            Ok(ConsumeWorkerResult {
                outcome: if should_commit {
                    ConsumeProcessOutcome::Failed
                } else {
                    ConsumeProcessOutcome::Retrying
                },
                should_commit,
                retry_backoff_ms,
            })
        }
    }
}

pub(crate) async fn process_worker_envelope(
    pool: &PgPool,
    meta: &WorkerEnvelopeMeta,
    envelope: &EventEnvelope,
) -> anyhow::Result<WorkerProcessOutcome> {
    let mut tx = pool.begin().await?;
    let existing = sqlx::query_as::<_, (i64, String)>(
        r#"
        SELECT id, status
        FROM kafka_consume_ledger
        WHERE consumer_group = $1 AND event_id = $2
        FOR UPDATE
        "#,
    )
    .bind(&meta.consumer_group)
    .bind(&envelope.event_id)
    .fetch_optional(&mut *tx)
    .await?;
    let ledger_id = if let Some((id, status)) = existing {
        if ConsumeLedgerStatus::from_db(&status) == Some(ConsumeLedgerStatus::Succeeded) {
            tx.rollback().await?;
            return Ok(WorkerProcessOutcome::Duplicated);
        }
        id
    } else {
        sqlx::query_scalar::<_, i64>(
            r#"
            INSERT INTO kafka_consume_ledger(
                consumer_group, topic, partition, message_offset,
                event_id, event_type, aggregate_id, payload,
                status, error_message, processed_at, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NULL, NOW(), NOW(), NOW())
            RETURNING id
            "#,
        )
        .bind(&meta.consumer_group)
        .bind(&meta.topic)
        .bind(meta.partition)
        .bind(meta.offset)
        .bind(&envelope.event_id)
        .bind(&envelope.event_type)
        .bind(&envelope.aggregate_id)
        .bind(&envelope.payload)
        .bind(ConsumeLedgerStatus::Succeeded.as_str())
        .fetch_one(&mut *tx)
        .await?
    };

    let _ = apply_worker_business_logic(&mut tx, envelope).await?;
    sqlx::query(
        r#"
        UPDATE kafka_consume_ledger
        SET status = $2,
            error_message = NULL,
            topic = $3,
            partition = $4,
            message_offset = $5,
            event_type = $6,
            aggregate_id = $7,
            payload = $8,
            processed_at = NOW(),
            updated_at = NOW()
        WHERE id = $1
        "#,
    )
    .bind(ledger_id)
    .bind(ConsumeLedgerStatus::Succeeded.as_str())
    .bind(&meta.topic)
    .bind(meta.partition)
    .bind(meta.offset)
    .bind(&envelope.event_type)
    .bind(&envelope.aggregate_id)
    .bind(&envelope.payload)
    .execute(&mut *tx)
    .await?;
    tx.commit().await?;
    Ok(WorkerProcessOutcome::Succeeded)
}

async fn apply_worker_business_logic(
    tx: &mut Transaction<'_, Postgres>,
    envelope: &EventEnvelope,
) -> anyhow::Result<BusinessProcessOutcome> {
    let _ = (tx, envelope);
    Ok(BusinessProcessOutcome::Succeeded)
}

struct FailedConsumeRow {
    consumer_group: String,
    topic: String,
    partition: i32,
    offset: i64,
    event_id: String,
    event_type: String,
    aggregate_id: String,
    payload: Value,
    error_message: String,
}

async fn persist_failed_ledger_row(pool: &PgPool, row: &FailedConsumeRow) -> anyhow::Result<()> {
    let _ = sqlx::query(
        r#"
        INSERT INTO kafka_consume_ledger(
            consumer_group, topic, partition, message_offset,
            event_id, event_type, aggregate_id, payload,
            status, error_message, processed_at, created_at, updated_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW(), NOW(), NOW())
        ON CONFLICT (consumer_group, event_id)
        DO UPDATE SET
            status = EXCLUDED.status,
            error_message = EXCLUDED.error_message,
            processed_at = NOW(),
            updated_at = NOW()
        "#,
    )
    .bind(&row.consumer_group)
    .bind(&row.topic)
    .bind(row.partition)
    .bind(row.offset)
    .bind(&row.event_id)
    .bind(&row.event_type)
    .bind(&row.aggregate_id)
    .bind(&row.payload)
    .bind(ConsumeLedgerStatus::Failed.as_str())
    .bind(&row.error_message)
    .execute(pool)
    .await?;
    Ok(())
}

async fn upsert_kafka_dlq_failure(pool: &PgPool, row: &FailedConsumeRow) -> anyhow::Result<i32> {
    let failure_count = sqlx::query_scalar::<_, i32>(
        r#"
        INSERT INTO kafka_dlq_events(
            consumer_group,
            topic,
            partition,
            message_offset,
            event_id,
            event_type,
            aggregate_id,
            payload,
            status,
            failure_count,
            error_message,
            first_failed_at,
            last_failed_at,
            created_at,
            updated_at
        )
        VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8,
            $9, 1, $10, NOW(), NOW(), NOW(), NOW()
        )
        ON CONFLICT (consumer_group, event_id)
        DO UPDATE SET
            topic = EXCLUDED.topic,
            partition = EXCLUDED.partition,
            message_offset = EXCLUDED.message_offset,
            event_type = EXCLUDED.event_type,
            aggregate_id = EXCLUDED.aggregate_id,
            payload = EXCLUDED.payload,
            status = $9,
            failure_count = kafka_dlq_events.failure_count + 1,
            error_message = EXCLUDED.error_message,
            last_failed_at = NOW(),
            replayed_at = NULL,
            discarded_at = NULL,
            updated_at = NOW()
        RETURNING failure_count
        "#,
    )
    .bind(&row.consumer_group)
    .bind(&row.topic)
    .bind(row.partition)
    .bind(row.offset)
    .bind(&row.event_id)
    .bind(&row.event_type)
    .bind(&row.aggregate_id)
    .bind(&row.payload)
    .bind(KafkaDlqStatus::Pending.as_str())
    .bind(&row.error_message)
    .fetch_one(pool)
    .await?;
    Ok(failure_count)
}

async fn mark_kafka_dlq_replayed(
    pool: &PgPool,
    consumer_group: &str,
    event_id: &str,
) -> anyhow::Result<()> {
    let _ = sqlx::query(
        r#"
        UPDATE kafka_dlq_events
        SET status = $3,
            replayed_at = NOW(),
            updated_at = NOW()
        WHERE consumer_group = $1
          AND event_id = $2
          AND status <> $4
        "#,
    )
    .bind(consumer_group)
    .bind(event_id)
    .bind(KafkaDlqStatus::Replayed.as_str())
    .bind(KafkaDlqStatus::Discarded.as_str())
    .execute(pool)
    .await?;
    Ok(())
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
            topic_prefix: "echoisle".to_string(),
            ..Default::default()
        };
        assert_eq!(
            cfg.topic_name(TOPIC_DEBATE_PARTICIPANT_JOINED),
            "echoisle.debate.participant.joined.v1"
        );
        assert_eq!(
            cfg.topic_name(TOPIC_DEBATE_SESSION_STATUS_CHANGED),
            "echoisle.debate.session.status.changed.v1"
        );
        assert_eq!(
            cfg.topic_name(TOPIC_DEBATE_MESSAGE_PINNED),
            "echoisle.debate.message.pinned.v1"
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

    #[test]
    fn fallback_event_id_should_include_topic_partition_offset() {
        let id = fallback_event_id("echoisle.debate.message.pinned.v1", 2, 18);
        assert_eq!(id, "echoisle.debate.message.pinned.v1:2:18");
    }

    #[test]
    fn kafka_worker_enabled_should_allow_legacy_or_worker_switch() {
        let cfg = KafkaConfig {
            consume_enabled: true,
            ..Default::default()
        };
        assert!(kafka_worker_enabled(&cfg));

        let cfg = KafkaConfig {
            consumer: crate::config::KafkaConsumerConfig {
                worker_enabled: true,
                ..Default::default()
            },
            ..Default::default()
        };
        assert!(kafka_worker_enabled(&cfg));

        let cfg = KafkaConfig::default();
        assert!(!kafka_worker_enabled(&cfg));
    }

    #[test]
    fn consume_process_outcome_display_should_include_retrying() {
        assert_eq!(ConsumeProcessOutcome::Succeeded.to_string(), "succeeded");
        assert_eq!(ConsumeProcessOutcome::Retrying.to_string(), "retrying");
        assert_eq!(ConsumeProcessOutcome::Failed.to_string(), "failed");
        assert_eq!(ConsumeProcessOutcome::Duplicated.to_string(), "duplicated");
    }

    #[test]
    fn consume_ledger_status_from_db_should_be_case_insensitive() {
        assert_eq!(
            ConsumeLedgerStatus::from_db("SUCCEEDED"),
            Some(ConsumeLedgerStatus::Succeeded)
        );
        assert_eq!(
            ConsumeLedgerStatus::from_db("failed"),
            Some(ConsumeLedgerStatus::Failed)
        );
        assert_eq!(ConsumeLedgerStatus::from_db("unknown"), None);
    }

    #[test]
    fn domain_event_into_message_should_fill_topic_key_and_payload() {
        let event = DomainEvent::DebateMessagePinned(DebateMessagePinnedEvent {
            session_id: 11,
            message_id: 22,
            user_id: 33,
            ledger_id: 44,
            cost_coins: 10,
            pin_seconds: 60,
            pinned_at: Utc::now(),
            expires_at: Utc::now(),
        });
        let outbox = event.into_message().expect("build outbox message");
        assert_eq!(outbox.topic, TOPIC_DEBATE_MESSAGE_PINNED);
        assert_eq!(outbox.key, "session:11");
        assert_eq!(outbox.event_type, "debate.message.pinned");
        assert_eq!(outbox.payload["payload"]["messageId"], 22);
    }

    #[test]
    fn relay_backoff_ms_should_cap_by_config() {
        let cfg = EventOutboxRelayConfig {
            batch_size: 200,
            lock_secs: 30,
            max_attempts: 12,
            base_backoff_ms: 500,
            max_backoff_ms: 60_000,
        };
        assert_eq!(relay_backoff_ms(1, &cfg), 500);
        assert_eq!(relay_backoff_ms(2, &cfg), 1_000);
        assert_eq!(relay_backoff_ms(3, &cfg), 2_000);
        assert_eq!(relay_backoff_ms(20, &cfg), 60_000);
    }
}
