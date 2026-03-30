use std::{
    sync::{
        atomic::{AtomicU64, Ordering},
        Arc,
    },
    time::Duration,
};

use anyhow::{ensure, Context};
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
pub const TOPIC_DEBATE_MESSAGE_CREATED: &str = "debate.message.created.v1";
pub const TOPIC_DEBATE_MESSAGE_PINNED: &str = "debate.message.pinned.v1";
pub const EVENT_TYPE_DEBATE_PARTICIPANT_JOINED: &str = "debate.participant.joined";
pub const EVENT_TYPE_DEBATE_SESSION_STATUS_CHANGED: &str = "debate.session.status.changed";
pub const EVENT_TYPE_DEBATE_MESSAGE_CREATED: &str = "debate.message.created";
pub const EVENT_TYPE_DEBATE_MESSAGE_PINNED: &str = "debate.message.pinned";

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
    DebateMessageCreated(DebateMessageCreatedEvent),
    DebateMessagePinned(DebateMessagePinnedEvent),
}

impl DomainEvent {
    fn into_message(self) -> anyhow::Result<OutboxMessage> {
        match self {
            Self::DebateParticipantJoined(event) => build_outbox_message(
                TOPIC_DEBATE_PARTICIPANT_JOINED,
                EVENT_TYPE_DEBATE_PARTICIPANT_JOINED,
                format!("session:{}", event.session_id),
                Utc::now(),
                serde_json::to_value(event)?,
            ),
            Self::DebateSessionStatusChanged(event) => build_outbox_message(
                TOPIC_DEBATE_SESSION_STATUS_CHANGED,
                EVENT_TYPE_DEBATE_SESSION_STATUS_CHANGED,
                format!("session:{}", event.session_id),
                event.changed_at,
                serde_json::to_value(event)?,
            ),
            Self::DebateMessageCreated(event) => build_outbox_message(
                TOPIC_DEBATE_MESSAGE_CREATED,
                EVENT_TYPE_DEBATE_MESSAGE_CREATED,
                format!("session:{}", event.session_id),
                event.created_at,
                serde_json::to_value(event)?,
            ),
            Self::DebateMessagePinned(event) => build_outbox_message(
                TOPIC_DEBATE_MESSAGE_PINNED,
                EVENT_TYPE_DEBATE_MESSAGE_PINNED,
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

#[derive(Debug, Default, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct EventOutboxRelayMetricsSnapshot {
    pub tick_success_total: u64,
    pub tick_error_total: u64,
    pub claimed_total: u64,
    pub sent_total: u64,
    pub retried_total: u64,
    pub failed_total: u64,
    pub dead_letter_total: u64,
}

#[derive(Debug, Default)]
pub struct KafkaConsumerRuntimeMetrics {
    receive_error_total: AtomicU64,
    process_succeeded_total: AtomicU64,
    process_duplicated_total: AtomicU64,
    process_retrying_total: AtomicU64,
    process_failed_total: AtomicU64,
    process_error_total: AtomicU64,
    commit_success_total: AtomicU64,
    commit_error_total: AtomicU64,
    dropped_total: AtomicU64,
}

#[derive(Debug, Default, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct KafkaConsumerRuntimeMetricsSnapshot {
    pub receive_error_total: u64,
    pub process_succeeded_total: u64,
    pub process_duplicated_total: u64,
    pub process_retrying_total: u64,
    pub process_failed_total: u64,
    pub process_error_total: u64,
    pub commit_success_total: u64,
    pub commit_error_total: u64,
    pub dropped_total: u64,
}

impl KafkaConsumerRuntimeMetrics {
    fn observe_receive_error(&self) {
        self.receive_error_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_process_outcome(&self, outcome: ConsumeProcessOutcome) {
        match outcome {
            ConsumeProcessOutcome::Succeeded => {
                self.process_succeeded_total.fetch_add(1, Ordering::Relaxed);
            }
            ConsumeProcessOutcome::Duplicated => {
                self.process_duplicated_total
                    .fetch_add(1, Ordering::Relaxed);
            }
            ConsumeProcessOutcome::Retrying => {
                self.process_retrying_total.fetch_add(1, Ordering::Relaxed);
            }
            ConsumeProcessOutcome::Failed => {
                self.process_failed_total.fetch_add(1, Ordering::Relaxed);
            }
        }
    }

    fn observe_process_error(&self) {
        self.process_error_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_commit_success(&self) {
        self.commit_success_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_commit_error(&self) {
        self.commit_error_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_dropped(&self) {
        self.dropped_total.fetch_add(1, Ordering::Relaxed);
    }

    pub(crate) fn snapshot(&self) -> KafkaConsumerRuntimeMetricsSnapshot {
        KafkaConsumerRuntimeMetricsSnapshot {
            receive_error_total: self.receive_error_total.load(Ordering::Relaxed),
            process_succeeded_total: self.process_succeeded_total.load(Ordering::Relaxed),
            process_duplicated_total: self.process_duplicated_total.load(Ordering::Relaxed),
            process_retrying_total: self.process_retrying_total.load(Ordering::Relaxed),
            process_failed_total: self.process_failed_total.load(Ordering::Relaxed),
            process_error_total: self.process_error_total.load(Ordering::Relaxed),
            commit_success_total: self.commit_success_total.load(Ordering::Relaxed),
            commit_error_total: self.commit_error_total.load(Ordering::Relaxed),
            dropped_total: self.dropped_total.load(Ordering::Relaxed),
        }
    }

    #[cfg(test)]
    pub(crate) fn overwrite_error_metrics_for_test(
        &self,
        commit_error_total: u64,
        process_error_total: u64,
        dropped_total: u64,
    ) {
        self.commit_error_total
            .store(commit_error_total, Ordering::Relaxed);
        self.process_error_total
            .store(process_error_total, Ordering::Relaxed);
        self.dropped_total.store(dropped_total, Ordering::Relaxed);
    }
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

    pub(crate) fn snapshot(&self) -> EventOutboxRelayMetricsSnapshot {
        EventOutboxRelayMetricsSnapshot {
            tick_success_total: self.tick_success_total.load(Ordering::Relaxed),
            tick_error_total: self.tick_error_total.load(Ordering::Relaxed),
            claimed_total: self.claimed_total.load(Ordering::Relaxed),
            sent_total: self.sent_total.load(Ordering::Relaxed),
            retried_total: self.retried_total.load(Ordering::Relaxed),
            failed_total: self.failed_total.load(Ordering::Relaxed),
            dead_letter_total: self.dead_letter_total.load(Ordering::Relaxed),
        }
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
pub struct DebateMessageCreatedEvent {
    pub session_id: u64,
    pub message_id: u64,
    pub user_id: u64,
    pub side: String,
    pub content: String,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DebateMessagePinnedEvent {
    pub pin_id: u64,
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

    pub fn maybe_spawn_consumer_worker(
        &self,
        pool: PgPool,
        metrics: Arc<KafkaConsumerRuntimeMetrics>,
    ) -> anyhow::Result<()> {
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
                bus.config.topic_name(TOPIC_DEBATE_MESSAGE_CREATED),
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
                    Err(e) => {
                        metrics.observe_receive_error();
                        warn!("kafka consume failed: {}", e);
                    }
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
                                metrics.observe_process_outcome(ret.outcome);
                                if ret.should_commit
                                    && matches!(ret.outcome, ConsumeProcessOutcome::Failed)
                                {
                                    metrics.observe_dropped();
                                }
                                if ret.should_commit {
                                    if let Err(err) =
                                        consumer.commit_message(&msg, CommitMode::Async)
                                    {
                                        metrics.observe_commit_error();
                                        warn!(
                                            "kafka commit failed topic={} partition={} offset={}: {}",
                                            topic, partition, offset, err
                                        );
                                    } else {
                                        metrics.observe_commit_success();
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
                                metrics.observe_process_error();
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

#[derive(Debug)]
#[allow(clippy::enum_variant_names)]
enum WorkerEvent {
    DebateParticipantJoined(DebateParticipantJoinedEvent),
    DebateSessionStatusChanged(DebateSessionStatusChangedEvent),
    DebateMessageCreated(DebateMessageCreatedEvent),
    DebateMessagePinned(DebateMessagePinnedEvent),
}

pub(crate) fn worker_supported_event_types() -> &'static [&'static str] {
    &[
        EVENT_TYPE_DEBATE_PARTICIPANT_JOINED,
        EVENT_TYPE_DEBATE_SESSION_STATUS_CHANGED,
        EVENT_TYPE_DEBATE_MESSAGE_CREATED,
        EVENT_TYPE_DEBATE_MESSAGE_PINNED,
    ]
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

    let _ = apply_worker_business_logic(&mut tx, meta, envelope).await?;
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
    meta: &WorkerEnvelopeMeta,
    envelope: &EventEnvelope,
) -> anyhow::Result<BusinessProcessOutcome> {
    let event = decode_worker_event(envelope)?;
    match event {
        WorkerEvent::DebateParticipantJoined(v) => {
            apply_participant_joined_effect(tx, &v).await?;
            record_worker_effect(
                tx,
                meta,
                envelope,
                WorkerEffectInput {
                    session_id: to_i64(v.session_id, "session_id")?,
                    user_id: Some(to_i64(v.user_id, "user_id")?),
                    side: Some(normalize_debate_side(&v.side)?.to_string()),
                    ..WorkerEffectInput::default()
                },
            )
            .await?;
            Ok(BusinessProcessOutcome::Succeeded)
        }
        WorkerEvent::DebateSessionStatusChanged(v) => {
            apply_session_status_changed_effect(tx, &v).await?;
            record_worker_effect(
                tx,
                meta,
                envelope,
                WorkerEffectInput {
                    session_id: to_i64(v.session_id, "session_id")?,
                    from_status: Some(normalize_debate_session_status(&v.from_status)?.to_string()),
                    to_status: Some(normalize_debate_session_status(&v.to_status)?.to_string()),
                    ..WorkerEffectInput::default()
                },
            )
            .await?;
            Ok(BusinessProcessOutcome::Succeeded)
        }
        WorkerEvent::DebateMessageCreated(v) => {
            apply_message_created_effect(tx, &v).await?;
            record_worker_effect(
                tx,
                meta,
                envelope,
                WorkerEffectInput {
                    session_id: to_i64(v.session_id, "session_id")?,
                    user_id: Some(to_i64(v.user_id, "user_id")?),
                    message_id: Some(to_i64(v.message_id, "message_id")?),
                    side: Some(normalize_debate_side(&v.side)?.to_string()),
                    ..WorkerEffectInput::default()
                },
            )
            .await?;
            Ok(BusinessProcessOutcome::Succeeded)
        }
        WorkerEvent::DebateMessagePinned(v) => {
            apply_message_pinned_effect(tx, &v).await?;
            record_worker_effect(
                tx,
                meta,
                envelope,
                WorkerEffectInput {
                    session_id: to_i64(v.session_id, "session_id")?,
                    user_id: Some(to_i64(v.user_id, "user_id")?),
                    message_id: Some(to_i64(v.message_id, "message_id")?),
                    pin_id: Some(to_i64(v.pin_id, "pin_id")?),
                    ledger_id: Some(to_i64(v.ledger_id, "ledger_id")?),
                    cost_coins: Some(v.cost_coins),
                    pin_seconds: Some(v.pin_seconds),
                    expires_at: Some(v.expires_at),
                    ..WorkerEffectInput::default()
                },
            )
            .await?;
            Ok(BusinessProcessOutcome::Succeeded)
        }
    }
}

#[derive(Debug, Default)]
struct WorkerEffectInput {
    session_id: i64,
    user_id: Option<i64>,
    message_id: Option<i64>,
    pin_id: Option<i64>,
    ledger_id: Option<i64>,
    from_status: Option<String>,
    to_status: Option<String>,
    side: Option<String>,
    cost_coins: Option<i64>,
    pin_seconds: Option<i32>,
    expires_at: Option<DateTime<Utc>>,
}

#[derive(Debug, FromRow)]
struct WorkerMessageRow {
    session_id: i64,
    user_id: i64,
    side: String,
    content: String,
}

#[derive(Debug, FromRow)]
struct WorkerPinnedRow {
    session_id: i64,
    message_id: i64,
    user_id: i64,
    ledger_id: i64,
    cost_coins: i64,
    pin_seconds: i32,
    expires_at: DateTime<Utc>,
    status: String,
}

#[derive(Debug, FromRow)]
struct WorkerLedgerRow {
    user_id: i64,
    entry_type: String,
    amount_delta: i64,
}

fn to_i64(value: u64, field: &str) -> anyhow::Result<i64> {
    value
        .try_into()
        .map_err(|_| anyhow::anyhow!("{field} is out of i64 range"))
}

fn normalize_debate_side(side: &str) -> anyhow::Result<&'static str> {
    match side.trim().to_ascii_lowercase().as_str() {
        "pro" => Ok("pro"),
        "con" => Ok("con"),
        _ => Err(anyhow::anyhow!("unsupported debate side={side}")),
    }
}

fn normalize_debate_session_status(status: &str) -> anyhow::Result<&'static str> {
    match status.trim().to_ascii_lowercase().as_str() {
        "scheduled" => Ok("scheduled"),
        "open" => Ok("open"),
        "running" => Ok("running"),
        "judging" => Ok("judging"),
        "closed" => Ok("closed"),
        "canceled" => Ok("canceled"),
        _ => Err(anyhow::anyhow!(
            "unsupported debate session status={status}"
        )),
    }
}

fn debate_status_rank(status: &str) -> anyhow::Result<i32> {
    Ok(match normalize_debate_session_status(status)? {
        "scheduled" => 0,
        "open" => 1,
        "running" => 2,
        "judging" => 3,
        "closed" => 4,
        "canceled" => 5,
        _ => 0,
    })
}

async fn apply_participant_joined_effect(
    tx: &mut Transaction<'_, Postgres>,
    event: &DebateParticipantJoinedEvent,
) -> anyhow::Result<()> {
    let session_id = to_i64(event.session_id, "session_id")?;
    let user_id = to_i64(event.user_id, "user_id")?;
    let side = normalize_debate_side(&event.side)?;
    ensure!(
        event.pro_count >= 0 && event.con_count >= 0,
        "participant counts cannot be negative, pro_count={}, con_count={}",
        event.pro_count,
        event.con_count
    );

    let row: Option<String> = sqlx::query_scalar(
        "SELECT side FROM session_participants WHERE session_id = $1 AND user_id = $2",
    )
    .bind(session_id)
    .bind(user_id)
    .fetch_optional(&mut **tx)
    .await?;
    let Some(existing_side) = row else {
        return Err(anyhow::anyhow!(
            "participant join event references missing row, session_id={}, user_id={}",
            session_id,
            user_id
        ));
    };
    ensure!(
        existing_side.eq_ignore_ascii_case(side),
        "participant side mismatch, session_id={}, user_id={}, event_side={}, db_side={}",
        session_id,
        user_id,
        side,
        existing_side
    );

    let actual_counts: (i64, i64) = sqlx::query_as(
        r#"
        SELECT
            COUNT(*) FILTER (WHERE side = 'pro')::bigint AS pro_count,
            COUNT(*) FILTER (WHERE side = 'con')::bigint AS con_count
        FROM session_participants
        WHERE session_id = $1
        "#,
    )
    .bind(session_id)
    .fetch_one(&mut **tx)
    .await?;
    ensure!(
        (event.pro_count as i64) <= actual_counts.0 && (event.con_count as i64) <= actual_counts.1,
        "participant count mismatch, event=({}, {}), actual=({}, {}), session_id={}",
        event.pro_count,
        event.con_count,
        actual_counts.0,
        actual_counts.1,
        session_id
    );

    let affected = sqlx::query(
        r#"
        UPDATE debate_sessions
        SET pro_count = GREATEST(pro_count, $2),
            con_count = GREATEST(con_count, $3),
            updated_at = NOW()
        WHERE id = $1
        "#,
    )
    .bind(session_id)
    .bind(event.pro_count)
    .bind(event.con_count)
    .execute(&mut **tx)
    .await?
    .rows_affected();
    ensure!(
        affected == 1,
        "participant join event references missing session_id={}",
        session_id
    );
    Ok(())
}

async fn apply_session_status_changed_effect(
    tx: &mut Transaction<'_, Postgres>,
    event: &DebateSessionStatusChangedEvent,
) -> anyhow::Result<()> {
    let session_id = to_i64(event.session_id, "session_id")?;
    let from_status = normalize_debate_session_status(&event.from_status)?;
    let to_status = normalize_debate_session_status(&event.to_status)?;
    let row: Option<String> =
        sqlx::query_scalar("SELECT status FROM debate_sessions WHERE id = $1 FOR UPDATE")
            .bind(session_id)
            .fetch_optional(&mut **tx)
            .await?;
    let Some(current_status) = row else {
        return Err(anyhow::anyhow!(
            "status change event references missing session_id={}",
            session_id
        ));
    };
    let current_status = normalize_debate_session_status(&current_status)?;
    ensure!(
        debate_status_rank(to_status)? >= debate_status_rank(from_status)?,
        "invalid status transition in event, from={}, to={}, session_id={}",
        from_status,
        to_status,
        session_id
    );

    if current_status == to_status {
        return Ok(());
    }

    // Ignore stale transitions (e.g. running event arrives after closed).
    if debate_status_rank(to_status)? < debate_status_rank(current_status)? {
        return Ok(());
    }

    sqlx::query(
        r#"
        UPDATE debate_sessions
        SET status = $2,
            updated_at = GREATEST(updated_at, $3)
        WHERE id = $1
        "#,
    )
    .bind(session_id)
    .bind(to_status)
    .bind(event.changed_at)
    .execute(&mut **tx)
    .await?;
    Ok(())
}

async fn apply_message_created_effect(
    tx: &mut Transaction<'_, Postgres>,
    event: &DebateMessageCreatedEvent,
) -> anyhow::Result<()> {
    let session_id = to_i64(event.session_id, "session_id")?;
    let message_id = to_i64(event.message_id, "message_id")?;
    let user_id = to_i64(event.user_id, "user_id")?;
    let side = normalize_debate_side(&event.side)?;

    let row: Option<WorkerMessageRow> = sqlx::query_as(
        r#"
        SELECT session_id, user_id, side, content
        FROM session_messages
        WHERE id = $1
        "#,
    )
    .bind(message_id)
    .fetch_optional(&mut **tx)
    .await?;
    let Some(row) = row else {
        return Err(anyhow::anyhow!(
            "message created event references missing message_id={}",
            message_id
        ));
    };
    ensure!(
        row.session_id == session_id,
        "message created session mismatch, message_id={}, event_session_id={}, db_session_id={}",
        message_id,
        session_id,
        row.session_id
    );
    ensure!(
        row.user_id == user_id,
        "message created user mismatch, message_id={}, event_user_id={}, db_user_id={}",
        message_id,
        user_id,
        row.user_id
    );
    ensure!(
        row.side.eq_ignore_ascii_case(side),
        "message created side mismatch, message_id={}, event_side={}, db_side={}",
        message_id,
        side,
        row.side
    );
    ensure!(
        row.content == event.content,
        "message content mismatch, message_id={}",
        message_id
    );
    Ok(())
}

async fn apply_message_pinned_effect(
    tx: &mut Transaction<'_, Postgres>,
    event: &DebateMessagePinnedEvent,
) -> anyhow::Result<()> {
    let pin_id = to_i64(event.pin_id, "pin_id")?;
    let session_id = to_i64(event.session_id, "session_id")?;
    let message_id = to_i64(event.message_id, "message_id")?;
    let user_id = to_i64(event.user_id, "user_id")?;
    let ledger_id = to_i64(event.ledger_id, "ledger_id")?;
    ensure!(
        event.cost_coins > 0,
        "pinned event cost_coins should be positive, pin_id={}, cost_coins={}",
        pin_id,
        event.cost_coins
    );

    let pin_row: Option<WorkerPinnedRow> = sqlx::query_as(
        r#"
        SELECT session_id, message_id, user_id, ledger_id, cost_coins, pin_seconds, expires_at, status
        FROM session_pinned_messages
        WHERE id = $1
        "#,
    )
    .bind(pin_id)
    .fetch_optional(&mut **tx)
    .await?;
    let Some(pin_row) = pin_row else {
        return Err(anyhow::anyhow!(
            "message pinned event references missing pin_id={}",
            pin_id
        ));
    };
    ensure!(
        pin_row.session_id == session_id
            && pin_row.message_id == message_id
            && pin_row.user_id == user_id
            && pin_row.ledger_id == ledger_id,
        "pinned event identity mismatch, pin_id={}",
        pin_id
    );
    ensure!(
        pin_row.cost_coins == event.cost_coins && pin_row.pin_seconds == event.pin_seconds,
        "pinned event billing mismatch, pin_id={}, event=(cost={},seconds={}), db=(cost={},seconds={})",
        pin_id,
        event.cost_coins,
        event.pin_seconds,
        pin_row.cost_coins,
        pin_row.pin_seconds
    );
    ensure!(
        pin_row.expires_at == event.expires_at,
        "pinned event expires_at mismatch, pin_id={}",
        pin_id
    );
    ensure!(
        pin_row.status.eq_ignore_ascii_case("active"),
        "pinned event status not active, pin_id={}, status={}",
        pin_id,
        pin_row.status
    );

    let ledger_row: Option<WorkerLedgerRow> = sqlx::query_as(
        r#"
        SELECT user_id, entry_type, amount_delta
        FROM wallet_ledger
        WHERE id = $1
        "#,
    )
    .bind(ledger_id)
    .fetch_optional(&mut **tx)
    .await?;
    let Some(ledger_row) = ledger_row else {
        return Err(anyhow::anyhow!(
            "pinned event references missing wallet_ledger id={}",
            ledger_id
        ));
    };
    ensure!(
        ledger_row.user_id == user_id,
        "wallet ledger user mismatch, ledger_id={}, event_user_id={}, db_user_id={}",
        ledger_id,
        user_id,
        ledger_row.user_id
    );
    ensure!(
        ledger_row.entry_type == "pin_debit",
        "wallet ledger entry_type mismatch, ledger_id={}, entry_type={}",
        ledger_id,
        ledger_row.entry_type
    );
    ensure!(
        ledger_row.amount_delta == -event.cost_coins,
        "wallet ledger amount mismatch, ledger_id={}, amount_delta={}, cost_coins={}",
        ledger_id,
        ledger_row.amount_delta,
        event.cost_coins
    );
    Ok(())
}

async fn record_worker_effect(
    tx: &mut Transaction<'_, Postgres>,
    meta: &WorkerEnvelopeMeta,
    envelope: &EventEnvelope,
    input: WorkerEffectInput,
) -> anyhow::Result<()> {
    sqlx::query(
        r#"
        INSERT INTO kafka_consume_worker_effects(
            consumer_group, topic, partition, message_offset,
            event_id, event_type, source, aggregate_id,
            session_id, user_id, message_id, pin_id, ledger_id,
            from_status, to_status, side,
            cost_coins, pin_seconds, expires_at,
            payload, applied_at, created_at, updated_at
        )
        VALUES (
            $1, $2, $3, $4,
            $5, $6, $7, $8,
            $9, $10, $11, $12, $13,
            $14, $15, $16,
            $17, $18, $19,
            $20, $21, NOW(), NOW()
        )
        ON CONFLICT (consumer_group, event_id)
        DO UPDATE SET
            topic = EXCLUDED.topic,
            partition = EXCLUDED.partition,
            message_offset = EXCLUDED.message_offset,
            event_type = EXCLUDED.event_type,
            source = EXCLUDED.source,
            aggregate_id = EXCLUDED.aggregate_id,
            session_id = EXCLUDED.session_id,
            user_id = EXCLUDED.user_id,
            message_id = EXCLUDED.message_id,
            pin_id = EXCLUDED.pin_id,
            ledger_id = EXCLUDED.ledger_id,
            from_status = EXCLUDED.from_status,
            to_status = EXCLUDED.to_status,
            side = EXCLUDED.side,
            cost_coins = EXCLUDED.cost_coins,
            pin_seconds = EXCLUDED.pin_seconds,
            expires_at = EXCLUDED.expires_at,
            payload = EXCLUDED.payload,
            applied_at = EXCLUDED.applied_at,
            updated_at = NOW()
        "#,
    )
    .bind(&meta.consumer_group)
    .bind(&meta.topic)
    .bind(meta.partition)
    .bind(meta.offset)
    .bind(&envelope.event_id)
    .bind(&envelope.event_type)
    .bind(&envelope.source)
    .bind(&envelope.aggregate_id)
    .bind(input.session_id)
    .bind(input.user_id)
    .bind(input.message_id)
    .bind(input.pin_id)
    .bind(input.ledger_id)
    .bind(input.from_status)
    .bind(input.to_status)
    .bind(input.side)
    .bind(input.cost_coins)
    .bind(input.pin_seconds)
    .bind(input.expires_at)
    .bind(&envelope.payload)
    .bind(envelope.occurred_at)
    .execute(&mut **tx)
    .await?;
    Ok(())
}

fn decode_worker_event(envelope: &EventEnvelope) -> anyhow::Result<WorkerEvent> {
    match envelope.event_type.as_str() {
        EVENT_TYPE_DEBATE_PARTICIPANT_JOINED => Ok(WorkerEvent::DebateParticipantJoined(
            serde_json::from_value(envelope.payload.clone())?,
        )),
        EVENT_TYPE_DEBATE_SESSION_STATUS_CHANGED => Ok(WorkerEvent::DebateSessionStatusChanged(
            serde_json::from_value(envelope.payload.clone())?,
        )),
        EVENT_TYPE_DEBATE_MESSAGE_CREATED => Ok(WorkerEvent::DebateMessageCreated(
            serde_json::from_value(envelope.payload.clone())?,
        )),
        EVENT_TYPE_DEBATE_MESSAGE_PINNED => Ok(WorkerEvent::DebateMessagePinned(
            serde_json::from_value(envelope.payload.clone())?,
        )),
        _ => Err(anyhow::anyhow!(
            "unsupported kafka event_type={}, expected one of {:?}",
            envelope.event_type,
            worker_supported_event_types()
        )),
    }
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
    use anyhow::Result;
    use chrono::Duration;

    async fn seed_topic_and_session(state: &crate::AppState, status: &str) -> Result<i64> {
        let topic_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO debate_topics(title, description, category, stance_pro, stance_con, context_seed, is_active, created_by)
            VALUES ('worker-topic', 'worker-desc', 'game', 'pro', 'con', 'seed', true, 1)
            RETURNING id
            "#,
        )
        .fetch_one(&state.pool)
        .await?;
        let now = Utc::now();
        let session_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO debate_sessions(topic_id, status, scheduled_start_at, actual_start_at, end_at, max_participants_per_side)
            VALUES ($1, $2, $3, $4, $5, 50)
            RETURNING id
            "#,
        )
        .bind(topic_id.0)
        .bind(status)
        .bind(now - Duration::minutes(10))
        .bind(now - Duration::minutes(8))
        .bind(now + Duration::minutes(30))
        .fetch_one(&state.pool)
        .await?;
        Ok(session_id.0)
    }

    async fn insert_participant(
        state: &crate::AppState,
        session_id: i64,
        user_id: i64,
        side: &str,
    ) -> Result<()> {
        sqlx::query(
            r#"
            INSERT INTO session_participants(session_id, user_id, side)
            VALUES ($1, $2, $3)
            ON CONFLICT (session_id, user_id) DO NOTHING
            "#,
        )
        .bind(session_id)
        .bind(user_id)
        .bind(side)
        .execute(&state.pool)
        .await?;
        Ok(())
    }

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
            cfg.topic_name(TOPIC_DEBATE_MESSAGE_CREATED),
            "echoisle.debate.message.created.v1"
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
        let event = DomainEvent::DebateMessageCreated(DebateMessageCreatedEvent {
            session_id: 11,
            message_id: 22,
            user_id: 33,
            side: "pro".to_string(),
            content: "hello".to_string(),
            created_at: Utc::now(),
        });
        let outbox = event.into_message().expect("build outbox message");
        assert_eq!(outbox.topic, TOPIC_DEBATE_MESSAGE_CREATED);
        assert_eq!(outbox.key, "session:11");
        assert_eq!(outbox.event_type, EVENT_TYPE_DEBATE_MESSAGE_CREATED);
        assert_eq!(outbox.payload["payload"]["messageId"], 22);
    }

    #[test]
    fn decode_worker_event_should_reject_unknown_event_type() {
        let envelope = EventEnvelope::new(
            "unknown.event.type",
            "chat-server",
            "session:1",
            serde_json::json!({}),
        );
        let err = decode_worker_event(&envelope).expect_err("unknown event should be rejected");
        assert!(err.to_string().contains("unsupported kafka event_type"));
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

    #[tokio::test]
    async fn process_worker_envelope_should_record_effect_once_for_duplicate_message_event(
    ) -> Result<()> {
        let (_tdb, state) = crate::AppState::new_for_test().await?;
        let session_id = seed_topic_and_session(&state, "running").await?;
        insert_participant(&state, session_id, 1, "pro").await?;
        let msg_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO session_messages(session_id, user_id, side, content)
            VALUES ($1, $2, 'pro', 'worker-msg')
            RETURNING id
            "#,
        )
        .bind(session_id)
        .bind(1_i64)
        .fetch_one(&state.pool)
        .await?;
        let envelope = EventEnvelope::new(
            EVENT_TYPE_DEBATE_MESSAGE_CREATED,
            "chat-server",
            format!("session:{session_id}"),
            serde_json::to_value(DebateMessageCreatedEvent {
                session_id: session_id as u64,
                message_id: msg_id.0 as u64,
                user_id: 1,
                side: "pro".to_string(),
                content: "worker-msg".to_string(),
                created_at: Utc::now(),
            })?,
        );
        let meta = WorkerEnvelopeMeta {
            consumer_group: "worker-test-group".to_string(),
            topic: TOPIC_DEBATE_MESSAGE_CREATED.to_string(),
            partition: 0,
            offset: 1,
        };

        let first = process_worker_envelope(&state.pool, &meta, &envelope).await?;
        assert!(matches!(first, WorkerProcessOutcome::Succeeded));
        let second = process_worker_envelope(&state.pool, &meta, &envelope).await?;
        assert!(matches!(second, WorkerProcessOutcome::Duplicated));

        let count: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)
            FROM kafka_consume_worker_effects
            WHERE consumer_group = $1
              AND event_id = $2
            "#,
        )
        .bind(&meta.consumer_group)
        .bind(&envelope.event_id)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(count, 1);
        Ok(())
    }

    #[tokio::test]
    async fn process_worker_envelope_should_validate_and_record_pinned_effect() -> Result<()> {
        let (_tdb, state) = crate::AppState::new_for_test().await?;
        let session_id = seed_topic_and_session(&state, "running").await?;
        insert_participant(&state, session_id, 1, "pro").await?;
        let message_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO session_messages(session_id, user_id, side, content)
            VALUES ($1, $2, 'pro', 'pin-target-msg')
            RETURNING id
            "#,
        )
        .bind(session_id)
        .bind(1_i64)
        .fetch_one(&state.pool)
        .await?;
        sqlx::query(
            r#"
            INSERT INTO user_wallets(user_id, balance)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET balance = EXCLUDED.balance, updated_at = NOW()
            "#,
        )
        .bind(1_i64)
        .bind(80_i64)
        .execute(&state.pool)
        .await?;
        let ledger_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO wallet_ledger(user_id, order_id, entry_type, amount_delta, balance_after, idempotency_key, metadata)
            VALUES ($1, NULL, 'pin_debit', $2, $3, $4, '{}'::jsonb)
            RETURNING id
            "#,
        )
        .bind(1_i64)
        .bind(-20_i64)
        .bind(80_i64)
        .bind("worker-pin-ledger-1")
        .fetch_one(&state.pool)
        .await?;
        let expires_at = Utc::now() + Duration::seconds(60);
        let pin_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO session_pinned_messages(
                session_id, message_id, user_id, ledger_id, cost_coins, pin_seconds, pinned_at, expires_at, status
            )
            VALUES ($1, $2, $3, $4, 20, 60, NOW(), $5, 'active')
            RETURNING id
            "#,
        )
        .bind(session_id)
        .bind(message_id.0)
        .bind(1_i64)
        .bind(ledger_id.0)
        .bind(expires_at)
        .fetch_one(&state.pool)
        .await?;

        let envelope = EventEnvelope::new(
            EVENT_TYPE_DEBATE_MESSAGE_PINNED,
            "chat-server",
            format!("session:{session_id}"),
            serde_json::to_value(DebateMessagePinnedEvent {
                pin_id: pin_id.0 as u64,
                session_id: session_id as u64,
                message_id: message_id.0 as u64,
                user_id: 1,
                ledger_id: ledger_id.0 as u64,
                cost_coins: 20,
                pin_seconds: 60,
                pinned_at: Utc::now(),
                expires_at,
            })?,
        );
        let meta = WorkerEnvelopeMeta {
            consumer_group: "worker-test-group".to_string(),
            topic: TOPIC_DEBATE_MESSAGE_PINNED.to_string(),
            partition: 1,
            offset: 9,
        };
        let outcome = process_worker_envelope(&state.pool, &meta, &envelope).await?;
        assert!(matches!(outcome, WorkerProcessOutcome::Succeeded));

        let row: (Option<i64>, Option<i64>, Option<i64>, Option<i64>) = sqlx::query_as(
            r#"
            SELECT user_id, message_id, pin_id, ledger_id
            FROM kafka_consume_worker_effects
            WHERE consumer_group = $1
              AND event_id = $2
            "#,
        )
        .bind(&meta.consumer_group)
        .bind(&envelope.event_id)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(row.0, Some(1));
        assert_eq!(row.1, Some(message_id.0));
        assert_eq!(row.2, Some(pin_id.0));
        assert_eq!(row.3, Some(ledger_id.0));
        Ok(())
    }
}
