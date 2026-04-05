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
use std::collections::BTreeSet;
use utoipa::{IntoParams, ToSchema};

const DLQ_STATUS_PENDING: &str = "pending";
const DLQ_STATUS_REPLAYED: &str = "replayed";
const DLQ_STATUS_DISCARDED: &str = "discarded";
const NOTIFY_RUNTIME_SERVICE_NAME_PREFIX: &str = "notify_server";
const NOTIFY_RUNTIME_SIGNAL_STALE_SECS: i64 = 300;
const NOTIFY_RUNTIME_NO_COMMIT_WARMUP_SECS: i64 = 300;
const DLQ_REPLAY_PROGRESS_STALE_SECS: i64 = 300;

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
pub struct KafkaConsumerRuntimeMetricsSnapshotOutput {
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

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct GetKafkaTransportReadinessOutput {
    pub ready_to_switch: bool,
    pub kafka_enabled: bool,
    pub chat_ingress_mode: String,
    pub notify_ingress_modes: Vec<String>,
    pub notify_ingress_mode_mismatch: bool,
    pub outbox_relay_worker_enabled: bool,
    pub consumer_worker_enabled: bool,
    pub consumer_business_logic_ready: bool,
    pub notify_consume_chain_ready: bool,
    pub dlq_replay_loop_ready: bool,
    pub supported_event_types: Vec<String>,
    pub blockers: Vec<String>,
    pub outbox_metrics: KafkaOutboxRelayMetricsSnapshotOutput,
    pub consumer_metrics: KafkaConsumerRuntimeMetricsSnapshotOutput,
    pub pending_dlq_count: u64,
    pub pending_dlq_oldest_failed_at: Option<DateTime<Utc>>,
    pub pending_dlq_oldest_failed_age_secs: Option<u64>,
    pub pending_dlq_blocking_count_threshold: u64,
    pub pending_dlq_oldest_age_blocking_secs: u64,
    pub pending_dlq_replay_rate_window_secs: u64,
    pub pending_dlq_min_replay_actions_per_minute: f64,
    pub pending_dlq_replay_actions_per_minute: Option<f64>,
    pub recent_dlq_replay_action_count: u64,
    pub last_dlq_replay_action_at: Option<DateTime<Utc>>,
    pub dlq_replay_progressing: bool,
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

#[derive(Debug, Clone, FromRow)]
struct KafkaDlqRuntimeRow {
    pending_dlq_count: i64,
    pending_dlq_oldest_failed_at: Option<DateTime<Utc>>,
    last_dlq_replay_action_at: Option<DateTime<Utc>>,
    recent_dlq_replay_action_count: i64,
}

#[derive(Debug, Clone, FromRow)]
struct NotifyRuntimeSignalRow {
    service_name: String,
    kafka_enabled: bool,
    disable_pg_listener: bool,
    kafka_connected_at: Option<DateTime<Utc>>,
    kafka_last_receive_at: Option<DateTime<Utc>>,
    kafka_last_commit_at: Option<DateTime<Utc>>,
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
        let pending_dlq_replay_rate_window_secs = self
            .config
            .worker_runtime
            .kafka_readiness_pending_dlq_replay_rate_window_secs;
        let pending_dlq_min_replay_actions_per_minute = self
            .config
            .worker_runtime
            .kafka_readiness_pending_dlq_min_replay_actions_per_minute;
        let pending_dlq_replay_rate_window_secs_i64 = pending_dlq_replay_rate_window_secs as i64;
        let dlq_runtime: KafkaDlqRuntimeRow = sqlx::query_as(
            r#"
            SELECT
                COUNT(1) FILTER (WHERE status = $1) AS pending_dlq_count,
                MIN(first_failed_at) FILTER (WHERE status = $1) AS pending_dlq_oldest_failed_at,
                MAX(updated_at) FILTER (WHERE status IN ($2, $3)) AS last_dlq_replay_action_at,
                COUNT(1) FILTER (
                    WHERE status IN ($2, $3)
                      AND updated_at >= NOW() - ($4::bigint * INTERVAL '1 second')
                ) AS recent_dlq_replay_action_count
            FROM kafka_dlq_events
            "#,
        )
        .bind(DLQ_STATUS_PENDING)
        .bind(DLQ_STATUS_REPLAYED)
        .bind(DLQ_STATUS_DISCARDED)
        .bind(pending_dlq_replay_rate_window_secs_i64)
        .fetch_one(&self.pool)
        .await?;
        let notify_runtime_signals: Vec<NotifyRuntimeSignalRow> = sqlx::query_as(
            r#"
            SELECT
                service_name,
                kafka_enabled,
                disable_pg_listener,
                kafka_connected_at,
                kafka_last_receive_at,
                kafka_last_commit_at,
                updated_at
            FROM notify_runtime_signals
            WHERE service_name LIKE $1
            ORDER BY updated_at DESC
            "#,
        )
        .bind(format!("{}%", NOTIFY_RUNTIME_SERVICE_NAME_PREFIX))
        .fetch_all(&self.pool)
        .await?;
        let now = Utc::now();
        let (notify_consume_chain_ready, notify_chain_blockers) =
            evaluate_notify_consume_chain_runtime(&notify_runtime_signals, now);
        let chat_ingress_mode = if kafka_enabled {
            "kafka-only".to_string()
        } else {
            "pg-only".to_string()
        };
        let notify_ingress_modes = collect_notify_ingress_modes(&notify_runtime_signals);
        let notify_ingress_mode_mismatch = evaluate_notify_ingress_mode_mismatch(
            chat_ingress_mode.as_str(),
            &notify_ingress_modes,
        );
        let pending_dlq_count = dlq_runtime.pending_dlq_count.max(0) as u64;
        let recent_dlq_replay_action_count =
            dlq_runtime.recent_dlq_replay_action_count.max(0) as u64;
        let dlq_replay_progressing = dlq_runtime
            .last_dlq_replay_action_at
            .map(|ts| (now - ts).num_seconds().max(0) <= DLQ_REPLAY_PROGRESS_STALE_SECS)
            .unwrap_or(false);
        let pending_dlq_replay_actions_per_minute = if pending_dlq_replay_rate_window_secs > 0 {
            Some(
                recent_dlq_replay_action_count as f64
                    / (pending_dlq_replay_rate_window_secs as f64 / 60.0),
            )
        } else {
            None
        };
        let dlq_replay_loop_ready = pending_dlq_count == 0 || dlq_replay_progressing;
        let pending_dlq_blocking_count_threshold = self
            .config
            .worker_runtime
            .kafka_readiness_pending_dlq_blocking_count_threshold;
        let pending_dlq_oldest_age_blocking_secs = self
            .config
            .worker_runtime
            .kafka_readiness_pending_dlq_oldest_age_blocking_secs;
        let (
            pending_dlq_should_block_switch,
            pending_dlq_blockers,
            pending_dlq_oldest_failed_age_secs,
        ) = evaluate_pending_dlq_switch_blocking(
            pending_dlq_count,
            dlq_runtime.pending_dlq_oldest_failed_at,
            pending_dlq_blocking_count_threshold,
            pending_dlq_oldest_age_blocking_secs,
            now,
        );
        let (pending_dlq_replay_rate_should_block_switch, pending_dlq_replay_rate_blockers) =
            evaluate_pending_dlq_replay_rate_blocking(
                pending_dlq_count,
                pending_dlq_replay_actions_per_minute,
                pending_dlq_min_replay_actions_per_minute,
            );
        let consumer_metrics = self.kafka_consumer_metrics.snapshot();

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
        if notify_ingress_mode_mismatch {
            blockers.push(format!(
                "ingress mode mismatch: chat={}, notify={}",
                chat_ingress_mode,
                notify_ingress_modes.join(",")
            ));
        }
        if consumer_metrics.commit_error_total > 0 {
            blockers.push(format!(
                "consumer commit errors detected: {}",
                consumer_metrics.commit_error_total
            ));
        }
        if consumer_metrics.dropped_total > 0 {
            blockers.push(format!(
                "consumer dropped messages detected: {}",
                consumer_metrics.dropped_total
            ));
        }
        if consumer_metrics.process_error_total > 0 {
            blockers.push(format!(
                "consumer process errors detected: {}",
                consumer_metrics.process_error_total
            ));
        }
        blockers.extend(notify_chain_blockers);
        if pending_dlq_count > 0 {
            if !dlq_replay_progressing {
                blockers
                    .push("dlq replay progress is stale while pending events exist".to_string());
            }
            if pending_dlq_should_block_switch {
                blockers.extend(pending_dlq_blockers);
            }
            if pending_dlq_replay_rate_should_block_switch {
                blockers.extend(pending_dlq_replay_rate_blockers);
            }
        }
        if !dlq_replay_loop_ready {
            blockers.push("DLQ replay loop is not ready".to_string());
        }

        let metrics = self.event_outbox_metrics.snapshot();
        Ok(GetKafkaTransportReadinessOutput {
            ready_to_switch: blockers.is_empty(),
            kafka_enabled,
            chat_ingress_mode,
            notify_ingress_modes,
            notify_ingress_mode_mismatch,
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
            consumer_metrics: KafkaConsumerRuntimeMetricsSnapshotOutput {
                receive_error_total: consumer_metrics.receive_error_total,
                process_succeeded_total: consumer_metrics.process_succeeded_total,
                process_duplicated_total: consumer_metrics.process_duplicated_total,
                process_retrying_total: consumer_metrics.process_retrying_total,
                process_failed_total: consumer_metrics.process_failed_total,
                process_error_total: consumer_metrics.process_error_total,
                commit_success_total: consumer_metrics.commit_success_total,
                commit_error_total: consumer_metrics.commit_error_total,
                dropped_total: consumer_metrics.dropped_total,
            },
            pending_dlq_count,
            pending_dlq_oldest_failed_at: dlq_runtime.pending_dlq_oldest_failed_at,
            pending_dlq_oldest_failed_age_secs,
            pending_dlq_blocking_count_threshold,
            pending_dlq_oldest_age_blocking_secs,
            pending_dlq_replay_rate_window_secs,
            pending_dlq_min_replay_actions_per_minute,
            pending_dlq_replay_actions_per_minute,
            recent_dlq_replay_action_count,
            last_dlq_replay_action_at: dlq_runtime.last_dlq_replay_action_at,
            dlq_replay_progressing,
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

fn collect_notify_ingress_modes(signals: &[NotifyRuntimeSignalRow]) -> Vec<String> {
    let mut set = BTreeSet::new();
    for signal in signals {
        let mode = if signal.kafka_enabled && signal.disable_pg_listener {
            "kafka-only"
        } else if signal.kafka_enabled {
            "mixed"
        } else {
            "pg-only"
        };
        set.insert(mode.to_string());
    }
    set.into_iter().collect()
}

fn evaluate_notify_ingress_mode_mismatch(chat_mode: &str, notify_modes: &[String]) -> bool {
    if notify_modes.is_empty() {
        return false;
    }
    if notify_modes.len() > 1 {
        return true;
    }
    let Some(notify_mode) = notify_modes.first().map(String::as_str) else {
        return false;
    };
    match chat_mode {
        "kafka" => notify_mode == "pg-only",
        "postgres" => notify_mode != "pg-only",
        _ => notify_mode != chat_mode,
    }
}

fn evaluate_notify_consume_chain_runtime(
    signals: &[NotifyRuntimeSignalRow],
    now: DateTime<Utc>,
) -> (bool, Vec<String>) {
    if signals.is_empty() {
        return (false, vec!["notify runtime signal is missing".to_string()]);
    }

    if signals
        .iter()
        .any(|signal| evaluate_notify_consume_chain_signal(signal, now).0)
    {
        return (true, Vec::new());
    }

    let latest = signals
        .iter()
        .max_by_key(|signal| signal.updated_at)
        .expect("signals is not empty");
    let (_, mut blockers) = evaluate_notify_consume_chain_signal(latest, now);
    if signals.len() > 1 {
        blockers = blockers
            .into_iter()
            .map(|item| format!("{} [{}]", item, latest.service_name))
            .collect();
    }
    (false, blockers)
}

fn evaluate_notify_consume_chain_signal(
    signal: &NotifyRuntimeSignalRow,
    now: DateTime<Utc>,
) -> (bool, Vec<String>) {
    let mut blockers = Vec::new();

    if !signal.kafka_enabled {
        blockers.push("notify kafka ingress is disabled".to_string());
    }
    if !signal.disable_pg_listener {
        blockers.push("notify kafka-only mode is disabled".to_string());
    }
    if signal.kafka_connected_at.is_none() {
        blockers.push("notify kafka consumer has not connected".to_string());
    }
    let receive_stale_secs = signal
        .kafka_last_receive_at
        .map(|ts| (now - ts).num_seconds().max(0));
    let connected_stale_secs = signal
        .kafka_connected_at
        .map(|ts| (now - ts).num_seconds().max(0));
    match signal.kafka_last_commit_at {
        None => {
            let has_recent_receive = receive_stale_secs
                .map(|recv_stale| recv_stale <= NOTIFY_RUNTIME_SIGNAL_STALE_SECS)
                .unwrap_or(false);
            if has_recent_receive {
                blockers.push(
                    "notify kafka consumer received events but has not committed yet".to_string(),
                );
            } else {
                let within_no_commit_warmup = connected_stale_secs
                    .map(|connected_stale| connected_stale <= NOTIFY_RUNTIME_NO_COMMIT_WARMUP_SECS)
                    .unwrap_or(false);
                if !within_no_commit_warmup {
                    let connected_age = connected_stale_secs.unwrap_or(0);
                    blockers.push(format!(
                        "notify kafka consumer has not committed any event after warmup: {}s",
                        connected_age
                    ));
                }
            }
        }
        Some(ts) => {
            let stale_secs = (now - ts).num_seconds().max(0);
            if stale_secs > NOTIFY_RUNTIME_SIGNAL_STALE_SECS {
                // Low-traffic exemption: if receive heartbeat is also stale, treat it as idle traffic
                // instead of a consume/commit mismatch.
                let has_recent_receive = receive_stale_secs
                    .map(|recv_stale| recv_stale <= NOTIFY_RUNTIME_SIGNAL_STALE_SECS)
                    .unwrap_or(false);
                if has_recent_receive {
                    blockers.push(format!(
                        "notify kafka consumer commit heartbeat is stale: {}s",
                        stale_secs
                    ));
                }
            }
        }
    }
    let signal_stale_secs = (now - signal.updated_at).num_seconds().max(0);
    if signal_stale_secs > NOTIFY_RUNTIME_SIGNAL_STALE_SECS {
        blockers.push(format!(
            "notify runtime signal is stale: {}s",
            signal_stale_secs
        ));
    }
    (blockers.is_empty(), blockers)
}

fn evaluate_pending_dlq_switch_blocking(
    pending_dlq_count: u64,
    pending_dlq_oldest_failed_at: Option<DateTime<Utc>>,
    pending_dlq_blocking_count_threshold: u64,
    pending_dlq_oldest_age_blocking_secs: u64,
    now: DateTime<Utc>,
) -> (bool, Vec<String>, Option<u64>) {
    let pending_dlq_oldest_failed_age_secs =
        pending_dlq_oldest_failed_at.map(|ts| (now - ts).num_seconds().max(0) as u64);
    if pending_dlq_count == 0 {
        return (false, Vec::new(), pending_dlq_oldest_failed_age_secs);
    }

    let mut blockers = Vec::new();
    if pending_dlq_blocking_count_threshold > 0
        && pending_dlq_count >= pending_dlq_blocking_count_threshold
    {
        blockers.push(format!(
            "pending dlq events reached blocking count threshold: count={}, threshold={}",
            pending_dlq_count, pending_dlq_blocking_count_threshold
        ));
    }
    if pending_dlq_oldest_age_blocking_secs > 0 {
        if let Some(oldest_age_secs) = pending_dlq_oldest_failed_age_secs {
            if oldest_age_secs >= pending_dlq_oldest_age_blocking_secs {
                blockers.push(format!(
                    "oldest pending dlq event exceeded blocking age threshold: age={}s, threshold={}s",
                    oldest_age_secs, pending_dlq_oldest_age_blocking_secs
                ));
            }
        }
    }
    (
        !blockers.is_empty(),
        blockers,
        pending_dlq_oldest_failed_age_secs,
    )
}

fn evaluate_pending_dlq_replay_rate_blocking(
    pending_dlq_count: u64,
    pending_dlq_replay_actions_per_minute: Option<f64>,
    pending_dlq_min_replay_actions_per_minute: f64,
) -> (bool, Vec<String>) {
    if pending_dlq_count == 0 || pending_dlq_min_replay_actions_per_minute <= 0.0 {
        return (false, Vec::new());
    }

    let Some(replay_actions_per_minute) = pending_dlq_replay_actions_per_minute else {
        return (
            true,
            vec![
                "pending dlq replay rate is unavailable while min replay rate threshold is enabled"
                    .to_string(),
            ],
        );
    };
    if replay_actions_per_minute < pending_dlq_min_replay_actions_per_minute {
        return (
            true,
            vec![format!(
                "pending dlq replay rate below threshold: rate={:.3} actions/min, threshold={:.3} actions/min",
                replay_actions_per_minute, pending_dlq_min_replay_actions_per_minute
            )],
        );
    }
    (false, Vec::new())
}

#[cfg(test)]
mod tests {
    use super::*;
    use anyhow::Result;
    use chrono::Duration;
    use serde_json::json;

    async fn setup_ops_owner(state: &AppState) -> Result<User> {
        state.grant_platform_admin(1).await?;
        let owner = state
            .find_user_by_id(1)
            .await?
            .expect("owner should exist in test fixture");
        Ok(owner)
    }

    async fn insert_pending_dlq_event(state: &AppState, event_id: &str) -> Result<()> {
        sqlx::query(
            r#"
            INSERT INTO kafka_dlq_events(
                consumer_group, topic, partition, message_offset,
                event_id, event_type, aggregate_id, payload,
                status, failure_count, error_message
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'pending', 1, 'test')
            "#,
        )
        .bind("test-group")
        .bind("debate.message.created")
        .bind(0_i32)
        .bind(1_i64)
        .bind(event_id)
        .bind("DebateMessageCreated")
        .bind("session:1")
        .bind(json!({
            "eventId": event_id,
            "eventType": "DebateMessageCreated",
            "source": "test",
            "aggregateId": "session:1",
            "occurredAt": "2026-03-30T00:00:00Z",
            "payload": {}
        }))
        .execute(&state.pool)
        .await?;
        Ok(())
    }

    async fn insert_replayed_dlq_event(
        state: &AppState,
        event_id: &str,
        updated_at: DateTime<Utc>,
    ) -> Result<()> {
        sqlx::query(
            r#"
            INSERT INTO kafka_dlq_events(
                consumer_group, topic, partition, message_offset,
                event_id, event_type, aggregate_id, payload,
                status, failure_count, error_message,
                first_failed_at, last_failed_at, replayed_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'replayed', 1, 'replayed', $9, $9, $9, $9)
            "#,
        )
        .bind("test-group")
        .bind("debate.message.created")
        .bind(0_i32)
        .bind(2_i64)
        .bind(event_id)
        .bind("DebateMessageCreated")
        .bind("session:1")
        .bind(json!({
            "eventId": event_id,
            "eventType": "DebateMessageCreated",
            "source": "test",
            "aggregateId": "session:1",
            "occurredAt": "2026-03-30T00:00:00Z",
            "payload": {}
        }))
        .bind(updated_at)
        .execute(&state.pool)
        .await?;
        Ok(())
    }

    async fn upsert_notify_runtime_signal_for_test(
        state: &AppState,
        kafka_enabled: bool,
        disable_pg_listener: bool,
        kafka_connected_at: Option<DateTime<Utc>>,
        kafka_last_receive_at: Option<DateTime<Utc>>,
        kafka_last_commit_at: Option<DateTime<Utc>>,
        updated_at: DateTime<Utc>,
    ) -> Result<()> {
        upsert_notify_runtime_signal_with_service_name_for_test(
            state,
            "notify_server",
            kafka_enabled,
            disable_pg_listener,
            kafka_connected_at,
            kafka_last_receive_at,
            kafka_last_commit_at,
            updated_at,
        )
        .await
    }

    #[allow(clippy::too_many_arguments)]
    async fn upsert_notify_runtime_signal_with_service_name_for_test(
        state: &AppState,
        service_name: &str,
        kafka_enabled: bool,
        disable_pg_listener: bool,
        kafka_connected_at: Option<DateTime<Utc>>,
        kafka_last_receive_at: Option<DateTime<Utc>>,
        kafka_last_commit_at: Option<DateTime<Utc>>,
        updated_at: DateTime<Utc>,
    ) -> Result<()> {
        sqlx::query(
            r#"
            INSERT INTO notify_runtime_signals(
                service_name,
                kafka_enabled,
                disable_pg_listener,
                kafka_connected_at,
                kafka_last_receive_at,
                kafka_last_commit_at,
                kafka_last_error,
                updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, NULL, $7)
            ON CONFLICT (service_name)
            DO UPDATE SET
                kafka_enabled = EXCLUDED.kafka_enabled,
                disable_pg_listener = EXCLUDED.disable_pg_listener,
                kafka_connected_at = EXCLUDED.kafka_connected_at,
                kafka_last_receive_at = EXCLUDED.kafka_last_receive_at,
                kafka_last_commit_at = EXCLUDED.kafka_last_commit_at,
                kafka_last_error = EXCLUDED.kafka_last_error,
                updated_at = EXCLUDED.updated_at
            "#,
        )
        .bind(service_name)
        .bind(kafka_enabled)
        .bind(disable_pg_listener)
        .bind(kafka_connected_at)
        .bind(kafka_last_receive_at)
        .bind(kafka_last_commit_at)
        .bind(updated_at)
        .execute(&state.pool)
        .await?;
        Ok(())
    }

    #[tokio::test]
    async fn get_kafka_transport_readiness_should_allow_when_any_notify_signal_is_ready(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = setup_ops_owner(&state).await?;
        let now = Utc::now();
        upsert_notify_runtime_signal_with_service_name_for_test(
            &state,
            "notify_server:stale",
            true,
            true,
            Some(now - Duration::seconds(700)),
            Some(now - Duration::seconds(700)),
            Some(now - Duration::seconds(700)),
            now - Duration::seconds(300),
        )
        .await?;
        upsert_notify_runtime_signal_with_service_name_for_test(
            &state,
            "notify_server:fresh",
            true,
            true,
            Some(now - Duration::seconds(2)),
            Some(now - Duration::seconds(1)),
            Some(now - Duration::seconds(1)),
            now,
        )
        .await?;

        let output = state.get_kafka_transport_readiness(&owner).await?;
        assert!(output.notify_consume_chain_ready);
        assert!(!output
            .blockers
            .iter()
            .any(|item| item.starts_with("notify ")));
        Ok(())
    }

    #[test]
    fn normalize_status_filter_should_reject_invalid_status() {
        assert!(normalize_status_filter(Some("unknown".to_string())).is_err());
        assert!(normalize_status_filter(Some("pending".to_string())).is_ok());
        assert!(normalize_status_filter(None).is_ok());
    }

    #[test]
    fn evaluate_pending_dlq_switch_blocking_should_allow_when_within_thresholds() {
        let now = Utc::now();
        let (should_block, blockers, oldest_age_secs) =
            evaluate_pending_dlq_switch_blocking(1, Some(now - Duration::seconds(10)), 5, 300, now);
        assert!(!should_block);
        assert!(blockers.is_empty());
        assert_eq!(oldest_age_secs, Some(10));
    }

    #[test]
    fn evaluate_pending_dlq_switch_blocking_should_block_by_age_threshold() {
        let now = Utc::now();
        let (should_block, blockers, oldest_age_secs) = evaluate_pending_dlq_switch_blocking(
            1,
            Some(now - Duration::seconds(900)),
            5,
            300,
            now,
        );
        assert!(should_block);
        assert_eq!(oldest_age_secs, Some(900));
        assert!(blockers.iter().any(
            |item| item.starts_with("oldest pending dlq event exceeded blocking age threshold")
        ));
    }

    #[test]
    fn evaluate_pending_dlq_replay_rate_blocking_should_allow_when_threshold_disabled() {
        let (should_block, blockers) = evaluate_pending_dlq_replay_rate_blocking(5, Some(0.1), 0.0);
        assert!(!should_block);
        assert!(blockers.is_empty());
    }

    #[test]
    fn evaluate_pending_dlq_replay_rate_blocking_should_block_when_rate_below_threshold() {
        let (should_block, blockers) = evaluate_pending_dlq_replay_rate_blocking(5, Some(0.2), 1.0);
        assert!(should_block);
        assert!(blockers
            .iter()
            .any(|item| item.starts_with("pending dlq replay rate below threshold")));
    }

    #[tokio::test]
    async fn get_kafka_transport_readiness_should_include_consumer_and_dlq_blockers() -> Result<()>
    {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = setup_ops_owner(&state).await?;
        state
            .kafka_consumer_metrics
            .overwrite_error_metrics_for_test(2, 3, 4);
        insert_pending_dlq_event(&state, "dlq-event-1").await?;

        let output = state.get_kafka_transport_readiness(&owner).await?;
        assert_eq!(output.consumer_metrics.commit_error_total, 2);
        assert_eq!(output.consumer_metrics.process_error_total, 3);
        assert_eq!(output.consumer_metrics.dropped_total, 4);
        assert_eq!(output.pending_dlq_count, 1);
        assert!(!output.dlq_replay_loop_ready);
        assert!(output
            .blockers
            .iter()
            .any(|item| item == "consumer commit errors detected: 2"));
        assert!(output
            .blockers
            .iter()
            .any(|item| item == "consumer process errors detected: 3"));
        assert!(output
            .blockers
            .iter()
            .any(|item| item == "consumer dropped messages detected: 4"));
        assert!(output.blockers.iter().any(|item| item
            == "pending dlq events reached blocking count threshold: count=1, threshold=1"));
        assert!(output
            .blockers
            .iter()
            .any(|item| item == "notify runtime signal is missing"));
        Ok(())
    }

    #[tokio::test]
    async fn get_kafka_transport_readiness_should_mark_dlq_loop_ready_when_no_pending() -> Result<()>
    {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = setup_ops_owner(&state).await?;

        let output = state.get_kafka_transport_readiness(&owner).await?;
        assert_eq!(output.pending_dlq_count, 0);
        assert!(output.dlq_replay_loop_ready);
        assert!(!output
            .blockers
            .iter()
            .any(|item| item.starts_with("pending dlq events reached blocking count threshold")));
        Ok(())
    }

    #[tokio::test]
    async fn get_kafka_transport_readiness_should_mark_dlq_loop_ready_when_replay_progressing(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = setup_ops_owner(&state).await?;
        insert_pending_dlq_event(&state, "dlq-event-pending-progress").await?;
        insert_replayed_dlq_event(
            &state,
            "dlq-event-replayed-progress",
            Utc::now() - Duration::seconds(30),
        )
        .await?;

        let output = state.get_kafka_transport_readiness(&owner).await?;
        assert_eq!(output.pending_dlq_count, 1);
        assert!(output.dlq_replay_progressing);
        assert!(output.dlq_replay_loop_ready);
        assert!(!output
            .blockers
            .iter()
            .any(|item| item == "DLQ replay loop is not ready"));
        Ok(())
    }

    #[tokio::test]
    async fn get_kafka_transport_readiness_should_mark_notify_chain_ready_with_fresh_signal(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = setup_ops_owner(&state).await?;
        let now = Utc::now();
        upsert_notify_runtime_signal_for_test(
            &state,
            true,
            true,
            Some(now - Duration::seconds(2)),
            Some(now - Duration::seconds(1)),
            Some(now - Duration::seconds(1)),
            now,
        )
        .await?;

        let output = state.get_kafka_transport_readiness(&owner).await?;
        assert!(output.notify_consume_chain_ready);
        assert!(!output
            .blockers
            .iter()
            .any(|item| item.starts_with("notify ")));
        Ok(())
    }

    #[tokio::test]
    async fn get_kafka_transport_readiness_should_allow_stale_commit_when_receive_is_idle(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = setup_ops_owner(&state).await?;
        let now = Utc::now();
        upsert_notify_runtime_signal_for_test(
            &state,
            true,
            true,
            Some(now - Duration::seconds(700)),
            Some(now - Duration::seconds(700)),
            Some(now - Duration::seconds(700)),
            now,
        )
        .await?;

        let output = state.get_kafka_transport_readiness(&owner).await?;
        assert!(output.notify_consume_chain_ready);
        assert!(!output
            .blockers
            .iter()
            .any(|item| item.starts_with("notify kafka consumer commit heartbeat is stale")));
        Ok(())
    }

    #[tokio::test]
    async fn get_kafka_transport_readiness_should_block_on_ingress_mode_mismatch() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = setup_ops_owner(&state).await?;
        let now = Utc::now();
        if state.config.kafka.enabled {
            upsert_notify_runtime_signal_for_test(&state, false, false, None, None, None, now)
                .await?;
        } else {
            upsert_notify_runtime_signal_for_test(
                &state,
                true,
                true,
                Some(now - Duration::seconds(2)),
                Some(now - Duration::seconds(1)),
                Some(now - Duration::seconds(1)),
                now,
            )
            .await?;
        }

        let output = state.get_kafka_transport_readiness(&owner).await?;
        assert!(output.notify_ingress_mode_mismatch);
        assert!(!output.ready_to_switch);
        assert!(output
            .blockers
            .iter()
            .any(|item| item.starts_with("ingress mode mismatch:")));
        Ok(())
    }

    #[tokio::test]
    async fn get_kafka_transport_readiness_should_block_stale_commit_when_receive_is_recent(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = setup_ops_owner(&state).await?;
        let now = Utc::now();
        upsert_notify_runtime_signal_for_test(
            &state,
            true,
            true,
            Some(now - Duration::seconds(700)),
            Some(now - Duration::seconds(2)),
            Some(now - Duration::seconds(700)),
            now,
        )
        .await?;

        let output = state.get_kafka_transport_readiness(&owner).await?;
        assert!(!output.notify_consume_chain_ready);
        assert!(output
            .blockers
            .iter()
            .any(|item| item.starts_with("notify kafka consumer commit heartbeat is stale")));
        Ok(())
    }

    #[tokio::test]
    async fn get_kafka_transport_readiness_should_allow_no_commit_within_warmup() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = setup_ops_owner(&state).await?;
        let now = Utc::now();
        upsert_notify_runtime_signal_for_test(
            &state,
            true,
            true,
            Some(now - Duration::seconds(30)),
            None,
            None,
            now,
        )
        .await?;

        let output = state.get_kafka_transport_readiness(&owner).await?;
        assert!(output.notify_consume_chain_ready);
        assert!(!output
            .blockers
            .iter()
            .any(|item| item.contains("has not committed any event after warmup")));
        Ok(())
    }

    #[tokio::test]
    async fn get_kafka_transport_readiness_should_block_no_commit_after_warmup() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = setup_ops_owner(&state).await?;
        let now = Utc::now();
        upsert_notify_runtime_signal_for_test(
            &state,
            true,
            true,
            Some(now - Duration::seconds(NOTIFY_RUNTIME_NO_COMMIT_WARMUP_SECS + 30)),
            None,
            None,
            now,
        )
        .await?;

        let output = state.get_kafka_transport_readiness(&owner).await?;
        assert!(!output.notify_consume_chain_ready);
        assert!(output.blockers.iter().any(|item| item
            .starts_with("notify kafka consumer has not committed any event after warmup")));
        Ok(())
    }
}
