use crate::{
    event_bus::{
        process_worker_envelope, worker_supported_event_types, EventEnvelope, WorkerEnvelopeMeta,
        WorkerProcessOutcome,
    },
    AppError, AppState, OpsPermission,
};
use chat_core::User;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sqlx::FromRow;
use utoipa::{IntoParams, ToSchema};

const DLQ_STATUS_PENDING: &str = "pending";
const DLQ_STATUS_REPLAYED: &str = "replayed";
const DLQ_STATUS_DISCARDED: &str = "discarded";

#[derive(Debug, Clone, Deserialize, ToSchema, IntoParams)]
#[serde(rename_all = "camelCase")]
pub struct ListKafkaDlqEventsQuery {
    pub status: Option<String>,
    pub event_type: Option<String>,
    pub limit: Option<u64>,
    pub offset: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct KafkaDlqEventItem {
    pub id: u64,
    pub consumer_group: String,
    pub topic: String,
    pub partition: i32,
    pub message_offset: i64,
    pub event_id: String,
    pub event_type: String,
    pub aggregate_id: String,
    pub status: String,
    pub failure_count: i32,
    pub error_message: String,
    pub first_failed_at: DateTime<Utc>,
    pub last_failed_at: DateTime<Utc>,
    pub replayed_at: Option<DateTime<Utc>>,
    pub discarded_at: Option<DateTime<Utc>>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct ListKafkaDlqEventsOutput {
    pub total: u64,
    pub limit: u64,
    pub offset: u64,
    pub items: Vec<KafkaDlqEventItem>,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct KafkaDlqActionOutput {
    pub id: u64,
    pub status: String,
    pub failure_count: i32,
    pub error_message: String,
    pub replayed_at: Option<DateTime<Utc>>,
    pub discarded_at: Option<DateTime<Utc>>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct KafkaOutboxRelayMetricsSnapshotOutput {
    pub tick_success_total: u64,
    pub tick_error_total: u64,
    pub claimed_total: u64,
    pub sent_total: u64,
    pub retried_total: u64,
    pub failed_total: u64,
    pub dead_letter_total: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct GetKafkaTransportReadinessOutput {
    pub ready_to_switch: bool,
    pub kafka_enabled: bool,
    pub outbox_relay_worker_enabled: bool,
    pub consumer_worker_enabled: bool,
    pub consumer_business_logic_ready: bool,
    pub notify_consume_chain_ready: bool,
    pub dlq_replay_loop_ready: bool,
    pub supported_event_types: Vec<String>,
    pub blockers: Vec<String>,
    pub outbox_metrics: KafkaOutboxRelayMetricsSnapshotOutput,
}

#[derive(Debug, Clone, FromRow)]
struct KafkaDlqEventRow {
    id: i64,
    consumer_group: String,
    topic: String,
    partition: i32,
    message_offset: i64,
    event_id: String,
    event_type: String,
    aggregate_id: String,
    status: String,
    failure_count: i32,
    error_message: String,
    first_failed_at: DateTime<Utc>,
    last_failed_at: DateTime<Utc>,
    replayed_at: Option<DateTime<Utc>>,
    discarded_at: Option<DateTime<Utc>>,
    updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
struct KafkaDlqActionRow {
    id: i64,
    status: String,
    failure_count: i32,
    error_message: String,
    replayed_at: Option<DateTime<Utc>>,
    discarded_at: Option<DateTime<Utc>>,
    updated_at: DateTime<Utc>,
}

fn normalize_limit(limit: Option<u64>) -> i64 {
    limit.unwrap_or(20).clamp(1, 100) as i64
}

fn normalize_offset(offset: Option<u64>) -> i64 {
    offset.unwrap_or(0).min(50_000) as i64
}

fn normalize_status_filter(status: Option<String>) -> Result<Option<String>, AppError> {
    let Some(status) = status else {
        return Ok(None);
    };
    let normalized = status.trim().to_lowercase();
    if normalized.is_empty() {
        return Ok(None);
    }
    if matches!(
        normalized.as_str(),
        DLQ_STATUS_PENDING | DLQ_STATUS_REPLAYED | DLQ_STATUS_DISCARDED
    ) {
        return Ok(Some(normalized));
    }
    Err(AppError::DebateError(
        "invalid dlq status filter, expect pending/replayed/discarded".to_string(),
    ))
}

fn normalize_event_type_filter(event_type: Option<String>) -> Option<String> {
    event_type
        .map(|v| v.trim().to_string())
        .filter(|v| !v.is_empty())
}

fn map_dlq_row(row: KafkaDlqEventRow) -> KafkaDlqEventItem {
    KafkaDlqEventItem {
        id: row.id as u64,
        consumer_group: row.consumer_group,
        topic: row.topic,
        partition: row.partition,
        message_offset: row.message_offset,
        event_id: row.event_id,
        event_type: row.event_type,
        aggregate_id: row.aggregate_id,
        status: row.status,
        failure_count: row.failure_count,
        error_message: row.error_message,
        first_failed_at: row.first_failed_at,
        last_failed_at: row.last_failed_at,
        replayed_at: row.replayed_at,
        discarded_at: row.discarded_at,
        updated_at: row.updated_at,
    }
}

fn map_dlq_action_row(row: KafkaDlqActionRow) -> KafkaDlqActionOutput {
    KafkaDlqActionOutput {
        id: row.id as u64,
        status: row.status,
        failure_count: row.failure_count,
        error_message: row.error_message,
        replayed_at: row.replayed_at,
        discarded_at: row.discarded_at,
        updated_at: row.updated_at,
    }
}

impl AppState {
    pub async fn get_kafka_transport_readiness(
        &self,
        user: &User,
    ) -> Result<GetKafkaTransportReadinessOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::JudgeReview)
            .await?;

        let kafka_enabled = self.config.kafka.enabled;
        let outbox_relay_worker_enabled =
            self.config.worker_runtime.event_outbox_relay_worker_enabled;
        let consumer_worker_enabled =
            self.config.kafka.consume_enabled || self.config.kafka.consumer.worker_enabled;
        let consumer_business_logic_ready = !worker_supported_event_types().is_empty();
        // Kafka consume -> notify fanout bridge is intentionally not switched in this round.
        let notify_consume_chain_ready = false;
        let dlq_replay_loop_ready = true;

        let mut blockers = Vec::new();
        if !kafka_enabled {
            blockers.push("kafka.enabled=false".to_string());
        }
        if !outbox_relay_worker_enabled {
            blockers.push("worker_runtime.event_outbox_relay_worker_enabled=false".to_string());
        }
        if !consumer_worker_enabled {
            blockers.push("kafka consumer worker is disabled".to_string());
        }
        if !consumer_business_logic_ready {
            blockers.push("consumer business logic handler is empty".to_string());
        }
        if !notify_consume_chain_ready {
            blockers.push("notify consume chain is not wired to Kafka yet".to_string());
        }
        if !dlq_replay_loop_ready {
            blockers.push("DLQ replay loop is not ready".to_string());
        }

        let metrics = self.event_outbox_metrics.snapshot();
        Ok(GetKafkaTransportReadinessOutput {
            ready_to_switch: blockers.is_empty(),
            kafka_enabled,
            outbox_relay_worker_enabled,
            consumer_worker_enabled,
            consumer_business_logic_ready,
            notify_consume_chain_ready,
            dlq_replay_loop_ready,
            supported_event_types: worker_supported_event_types()
                .iter()
                .map(|v| (*v).to_string())
                .collect(),
            blockers,
            outbox_metrics: KafkaOutboxRelayMetricsSnapshotOutput {
                tick_success_total: metrics.tick_success_total,
                tick_error_total: metrics.tick_error_total,
                claimed_total: metrics.claimed_total,
                sent_total: metrics.sent_total,
                retried_total: metrics.retried_total,
                failed_total: metrics.failed_total,
                dead_letter_total: metrics.dead_letter_total,
            },
        })
    }

    pub async fn list_kafka_dlq_events(
        &self,
        user: &User,
        query: ListKafkaDlqEventsQuery,
    ) -> Result<ListKafkaDlqEventsOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::JudgeReview)
            .await?;
        let limit = normalize_limit(query.limit);
        let offset = normalize_offset(query.offset);
        let status = normalize_status_filter(query.status)?;
        let event_type = normalize_event_type_filter(query.event_type);

        let total: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)
            FROM kafka_dlq_events
            WHERE ($1::text IS NULL OR status = $1)
              AND ($2::text IS NULL OR event_type = $2)
            "#,
        )
        .bind(status.as_deref())
        .bind(event_type.as_deref())
        .fetch_one(&self.pool)
        .await?;

        let rows: Vec<KafkaDlqEventRow> = sqlx::query_as(
            r#"
            SELECT
                id, consumer_group, topic, partition, message_offset,
                event_id, event_type, aggregate_id, status, failure_count, error_message,
                first_failed_at, last_failed_at, replayed_at, discarded_at, updated_at
            FROM kafka_dlq_events
            WHERE ($1::text IS NULL OR status = $1)
              AND ($2::text IS NULL OR event_type = $2)
            ORDER BY updated_at DESC, id DESC
            LIMIT $3 OFFSET $4
            "#,
        )
        .bind(status.as_deref())
        .bind(event_type.as_deref())
        .bind(limit)
        .bind(offset)
        .fetch_all(&self.pool)
        .await?;

        Ok(ListKafkaDlqEventsOutput {
            total: total.max(0) as u64,
            limit: limit as u64,
            offset: offset as u64,
            items: rows.into_iter().map(map_dlq_row).collect(),
        })
    }

    pub async fn replay_kafka_dlq_event(
        &self,
        user: &User,
        id: u64,
    ) -> Result<KafkaDlqActionOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::JudgeRejudge)
            .await?;

        let row: Option<(String, String, i32, i64, Value, String)> = sqlx::query_as(
            r#"
            SELECT consumer_group, topic, partition, message_offset, payload, status
            FROM kafka_dlq_events
            WHERE id = $1
            "#,
        )
        .bind(id as i64)
        .fetch_optional(&self.pool)
        .await?;
        let Some((consumer_group, topic, partition, message_offset, payload, status)) = row else {
            return Err(AppError::NotFound(format!("kafka dlq event id {}", id)));
        };
        if status == DLQ_STATUS_DISCARDED {
            return Err(AppError::DebateConflict(format!(
                "dlq event {} already discarded",
                id
            )));
        }
        let envelope: EventEnvelope = serde_json::from_value(payload).map_err(|err| {
            AppError::DebateError(format!("dlq payload decode failed for id {}: {}", id, err))
        })?;
        let meta = WorkerEnvelopeMeta {
            consumer_group,
            topic,
            partition,
            offset: message_offset,
        };
        let ret = process_worker_envelope(&self.pool, &meta, &envelope).await;
        match ret {
            Ok(WorkerProcessOutcome::Succeeded) | Ok(WorkerProcessOutcome::Duplicated) => {
                let row: KafkaDlqActionRow = sqlx::query_as(
                    r#"
                    UPDATE kafka_dlq_events
                    SET status = $2,
                        replayed_at = NOW(),
                        updated_at = NOW()
                    WHERE id = $1
                    RETURNING id, status, failure_count, error_message, replayed_at, discarded_at, updated_at
                    "#,
                )
                .bind(id as i64)
                .bind(DLQ_STATUS_REPLAYED)
                .fetch_one(&self.pool)
                .await?;
                Ok(map_dlq_action_row(row))
            }
            Err(err) => {
                let row: KafkaDlqActionRow = sqlx::query_as(
                    r#"
                    UPDATE kafka_dlq_events
                    SET status = $2,
                        failure_count = failure_count + 1,
                        error_message = $3,
                        last_failed_at = NOW(),
                        updated_at = NOW()
                    WHERE id = $1
                    RETURNING id, status, failure_count, error_message, replayed_at, discarded_at, updated_at
                    "#,
                )
                .bind(id as i64)
                .bind(DLQ_STATUS_PENDING)
                .bind(format!("replay retryable error: {}", err))
                .fetch_one(&self.pool)
                .await?;
                Ok(map_dlq_action_row(row))
            }
        }
    }

    pub async fn discard_kafka_dlq_event(
        &self,
        user: &User,
        id: u64,
    ) -> Result<KafkaDlqActionOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::JudgeRejudge)
            .await?;
        let row: Option<KafkaDlqActionRow> = sqlx::query_as(
            r#"
            UPDATE kafka_dlq_events
            SET status = $2,
                discarded_at = NOW(),
                updated_at = NOW()
            WHERE id = $1
            RETURNING id, status, failure_count, error_message, replayed_at, discarded_at, updated_at
            "#,
        )
        .bind(id as i64)
        .bind(DLQ_STATUS_DISCARDED)
        .fetch_optional(&self.pool)
        .await?;
        let Some(row) = row else {
            return Err(AppError::NotFound(format!("kafka dlq event id {}", id)));
        };
        Ok(map_dlq_action_row(row))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalize_status_filter_should_reject_invalid_status() {
        assert!(normalize_status_filter(Some("unknown".to_string())).is_err());
        assert!(normalize_status_filter(Some("pending".to_string())).is_ok());
        assert!(normalize_status_filter(None).is_ok());
    }
}
