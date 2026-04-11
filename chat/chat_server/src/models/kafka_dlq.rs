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
const DLQ_ACTION_REPLAY: &str = "replay";
const DLQ_ACTION_DISCARD: &str = "discard";
const DLQ_ACTION_RESULT_SUCCESS: &str = "success";
const DLQ_ACTION_RESULT_FAILED: &str = "failed";
const DLQ_ACTION_RESULT_CONFLICT: &str = "conflict";
const DLQ_ACTION_RESULT_NOT_FOUND: &str = "not_found";
const DLQ_ERROR_CLASS_TIMEOUT: &str = "timeout";
const DLQ_ERROR_CLASS_DB_CONFLICT: &str = "db_conflict";
const DLQ_ERROR_CLASS_DB_LOCK: &str = "db_lock";
const DLQ_ERROR_CLASS_PAYLOAD_INVALID: &str = "payload_invalid";
const DLQ_ERROR_CLASS_UPSTREAM_UNAVAILABLE: &str = "upstream_unavailable";
const DLQ_ERROR_CLASS_PERMISSION: &str = "permission";
const DLQ_ERROR_CLASS_INTERNAL: &str = "internal";
const DLQ_ERROR_MESSAGE_MASKED_BY_ROLE: &str = "masked_by_role";
const NOTIFY_RUNTIME_SERVICE_NAME_PREFIX: &str = "notify_server";
const NOTIFY_RUNTIME_SIGNAL_STALE_SECS: i64 = 300;
const NOTIFY_RUNTIME_NO_COMMIT_WARMUP_SECS: i64 = 300;
const DLQ_REPLAY_PROGRESS_STALE_SECS: i64 = 300;
const DLQ_RETENTION_MIN_DAYS: i64 = 1;
const DLQ_RETENTION_MAX_DAYS: i64 = 365;
const DLQ_RETENTION_MIN_BATCH_SIZE: i64 = 1;
const DLQ_RETENTION_MAX_BATCH_SIZE: i64 = 10_000;

#[derive(Debug, Clone, Deserialize, ToSchema, IntoParams)]
#[serde(rename_all = "camelCase")]
pub struct ListKafkaDlqEventsQuery {
    pub status: Option<String>,
    pub event_type: Option<String>,
    pub limit: Option<u64>,
    pub offset: Option<u64>,
    pub cursor: Option<String>,
    pub include_total: Option<bool>,
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
    pub error_class: String,
    pub error_code: String,
    pub first_failed_at: DateTime<Utc>,
    pub last_failed_at: DateTime<Utc>,
    pub replayed_at: Option<DateTime<Utc>>,
    pub discarded_at: Option<DateTime<Utc>>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct ListKafkaDlqEventsOutput {
    pub total: Option<u64>,
    pub limit: u64,
    pub offset: u64,
    pub has_more: bool,
    pub next_cursor: Option<String>,
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
pub struct KafkaDlqActionInput {
    pub reason: String,
}

#[derive(Debug, Clone, Copy, Default)]
pub struct KafkaDlqActionMeta<'a> {
    pub reason: Option<&'a str>,
    pub request_id: Option<&'a str>,
    pub idempotency_key: Option<&'a str>,
}

#[derive(Debug, Clone, Copy, Default)]
pub(crate) struct KafkaDlqRetentionCleanupReport {
    pub deleted_event_rows: u64,
    pub deleted_action_rows: u64,
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

struct KafkaDlqActionAuditInput<'a> {
    dlq_event_id: u64,
    action: &'a str,
    operator_user_id: i64,
    result: &'a str,
    before_status: Option<&'a str>,
    after_status: Option<&'a str>,
    reason: Option<&'a str>,
    request_id: Option<&'a str>,
    idempotency_key: Option<&'a str>,
    error_message: Option<&'a str>,
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

#[derive(Debug, Clone)]
struct ListKafkaDlqEventsCursor {
    updated_at: DateTime<Utc>,
    id: i64,
}

fn normalize_limit(limit: Option<u64>) -> i64 {
    limit.unwrap_or(20).clamp(1, 100) as i64
}

fn normalize_offset(offset: Option<u64>) -> i64 {
    offset.unwrap_or(0).min(50_000) as i64
}

fn format_kafka_dlq_cursor_timestamp(value: DateTime<Utc>) -> String {
    value.to_rfc3339_opts(chrono::SecondsFormat::Micros, true)
}

fn encode_list_kafka_dlq_events_cursor(updated_at: DateTime<Utc>, id: i64) -> String {
    format!("{}|{}", format_kafka_dlq_cursor_timestamp(updated_at), id)
}

fn decode_list_kafka_dlq_events_cursor(raw: &str) -> Result<ListKafkaDlqEventsCursor, AppError> {
    let trimmed = raw.trim();
    let Some((updated_at_raw, id_raw)) = trimmed.split_once('|') else {
        return Err(AppError::ValidationError(
            "ops_kafka_dlq_cursor_invalid".to_string(),
        ));
    };
    let updated_at = DateTime::parse_from_rfc3339(updated_at_raw.trim())
        .map(|ts| ts.with_timezone(&Utc))
        .map_err(|_| AppError::ValidationError("ops_kafka_dlq_cursor_invalid".to_string()))?;
    let id = id_raw
        .trim()
        .parse::<i64>()
        .map_err(|_| AppError::ValidationError("ops_kafka_dlq_cursor_invalid".to_string()))?;
    if id <= 0 {
        return Err(AppError::ValidationError(
            "ops_kafka_dlq_cursor_invalid".to_string(),
        ));
    }
    Ok(ListKafkaDlqEventsCursor { updated_at, id })
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

fn normalize_dlq_action_reason(reason: Option<&str>) -> Result<String, AppError> {
    let normalized = reason.unwrap_or_default().trim();
    if normalized.is_empty() {
        return Err(AppError::DebateError(
            "ops_kafka_dlq_action_reason_required".to_string(),
        ));
    }
    if normalized.len() > 240 {
        return Err(AppError::DebateError(
            "ops_kafka_dlq_action_reason_too_long".to_string(),
        ));
    }
    Ok(normalized.to_string())
}

fn classify_dlq_error_message(error_message: &str) -> &'static str {
    let normalized = error_message.to_ascii_lowercase();
    if normalized.contains("timeout")
        || normalized.contains("timed out")
        || normalized.contains("deadline exceeded")
    {
        return DLQ_ERROR_CLASS_TIMEOUT;
    }
    if normalized.contains("deadlock") || normalized.contains("lock wait") {
        return DLQ_ERROR_CLASS_DB_LOCK;
    }
    if normalized.contains("unique violation") || normalized.contains("duplicate key") {
        return DLQ_ERROR_CLASS_DB_CONFLICT;
    }
    if normalized.contains("decode")
        || normalized.contains("deserialize")
        || normalized.contains("invalid json")
        || normalized.contains("malformed")
    {
        return DLQ_ERROR_CLASS_PAYLOAD_INVALID;
    }
    if normalized.contains("connection refused")
        || normalized.contains("connection reset")
        || normalized.contains("unavailable")
        || normalized.contains("network")
    {
        return DLQ_ERROR_CLASS_UPSTREAM_UNAVAILABLE;
    }
    if normalized.contains("permission denied")
        || normalized.contains("forbidden")
        || normalized.contains("unauthorized")
    {
        return DLQ_ERROR_CLASS_PERMISSION;
    }
    DLQ_ERROR_CLASS_INTERNAL
}

#[derive(Debug, Clone, Copy)]
struct DlqErrorDescriptor {
    class: &'static str,
    code: &'static str,
}

fn classify_dlq_error_descriptor(error_message: &str) -> DlqErrorDescriptor {
    let class = classify_dlq_error_message(error_message);
    DlqErrorDescriptor { class, code: class }
}

fn map_dlq_row(row: KafkaDlqEventRow, expose_raw_error_message: bool) -> KafkaDlqEventItem {
    let descriptor = classify_dlq_error_descriptor(&row.error_message);
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
        error_message: if expose_raw_error_message {
            row.error_message
        } else {
            DLQ_ERROR_MESSAGE_MASKED_BY_ROLE.to_string()
        },
        error_class: descriptor.class.to_string(),
        error_code: descriptor.code.to_string(),
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
    pub(crate) async fn cleanup_kafka_dlq_retention_once(
        &self,
    ) -> Result<KafkaDlqRetentionCleanupReport, AppError> {
        let retention_days = self
            .config
            .worker_runtime
            .kafka_dlq_retention_days
            .clamp(DLQ_RETENTION_MIN_DAYS, DLQ_RETENTION_MAX_DAYS);
        let batch_size = self
            .config
            .worker_runtime
            .kafka_dlq_retention_cleanup_batch_size
            .clamp(DLQ_RETENTION_MIN_BATCH_SIZE, DLQ_RETENTION_MAX_BATCH_SIZE);
        let cutoff = Utc::now() - chrono::Duration::days(retention_days);
        self.cleanup_kafka_dlq_retention_before(cutoff, batch_size)
            .await
    }

    async fn cleanup_kafka_dlq_retention_before(
        &self,
        cutoff: DateTime<Utc>,
        batch_size: i64,
    ) -> Result<KafkaDlqRetentionCleanupReport, AppError> {
        let batch_size =
            batch_size.clamp(DLQ_RETENTION_MIN_BATCH_SIZE, DLQ_RETENTION_MAX_BATCH_SIZE);
        let (deleted_event_rows, deleted_action_rows): (i64, i64) = sqlx::query_as(
            r#"
            WITH candidate AS (
                SELECT id
                FROM kafka_dlq_events
                WHERE status IN ($1, $2)
                  AND updated_at < $3
                ORDER BY updated_at ASC, id ASC
                LIMIT $4
                FOR UPDATE SKIP LOCKED
            ),
            deleted_actions AS (
                DELETE FROM kafka_dlq_event_actions actions
                USING candidate c
                WHERE actions.dlq_event_id = c.id
                RETURNING actions.id
            ),
            deleted_events AS (
                DELETE FROM kafka_dlq_events events
                USING candidate c
                WHERE events.id = c.id
                RETURNING events.id
            )
            SELECT
                COALESCE((SELECT COUNT(1)::bigint FROM deleted_events), 0) AS deleted_event_rows,
                COALESCE((SELECT COUNT(1)::bigint FROM deleted_actions), 0) AS deleted_action_rows
            "#,
        )
        .bind(DLQ_STATUS_REPLAYED)
        .bind(DLQ_STATUS_DISCARDED)
        .bind(cutoff)
        .bind(batch_size)
        .fetch_one(&self.pool)
        .await?;
        Ok(KafkaDlqRetentionCleanupReport {
            deleted_event_rows: deleted_event_rows.max(0) as u64,
            deleted_action_rows: deleted_action_rows.max(0) as u64,
        })
    }

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

    async fn append_kafka_dlq_action_audit_best_effort(&self, input: KafkaDlqActionAuditInput<'_>) {
        if let Err(err) = sqlx::query(
            r#"
            INSERT INTO kafka_dlq_event_actions(
                dlq_event_id,
                action,
                operator_user_id,
                result,
                before_status,
                after_status,
                reason,
                request_id,
                idempotency_key,
                error_message
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            "#,
        )
        .bind(input.dlq_event_id as i64)
        .bind(input.action)
        .bind(input.operator_user_id)
        .bind(input.result)
        .bind(input.before_status)
        .bind(input.after_status)
        .bind(input.reason)
        .bind(input.request_id)
        .bind(input.idempotency_key)
        .bind(input.error_message)
        .execute(&self.pool)
        .await
        {
            tracing::warn!(
                dlq_event_id = input.dlq_event_id,
                action = input.action,
                operator_user_id = input.operator_user_id,
                result = input.result,
                "append kafka dlq action audit failed: {}",
                err
            );
        }
    }

    pub async fn list_kafka_dlq_events(
        &self,
        user: &User,
        query: ListKafkaDlqEventsQuery,
    ) -> Result<ListKafkaDlqEventsOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::JudgeReview)
            .await?;
        let expose_raw_error_message = match self
            .ensure_ops_permission(user, OpsPermission::JudgeRejudge)
            .await
        {
            Ok(()) => true,
            Err(AppError::DebateConflict(_)) => false,
            Err(err) => return Err(err),
        };
        let limit = normalize_limit(query.limit);
        let limit_plus_one = limit + 1;
        let cursor = match query.cursor.as_deref().map(str::trim) {
            Some(raw) if !raw.is_empty() => Some(decode_list_kafka_dlq_events_cursor(raw)?),
            _ => None,
        };
        let offset = if cursor.is_some() {
            0
        } else {
            normalize_offset(query.offset)
        };
        let status = normalize_status_filter(query.status)?;
        let event_type = normalize_event_type_filter(query.event_type);
        let include_total = query.include_total.unwrap_or(false);

        let mut rows: Vec<KafkaDlqEventRow> = if let Some(cursor) = cursor.as_ref() {
            sqlx::query_as(
                r#"
                SELECT
                    id, consumer_group, topic, partition, message_offset,
                    event_id, event_type, aggregate_id, status, failure_count, error_message,
                    first_failed_at, last_failed_at, replayed_at, discarded_at, updated_at
                FROM kafka_dlq_events
                WHERE ($1::text IS NULL OR status = $1)
                  AND ($2::text IS NULL OR event_type = $2)
                  AND (updated_at, id) < ($3, $4)
                ORDER BY updated_at DESC, id DESC
                LIMIT $5
                "#,
            )
            .bind(status.as_deref())
            .bind(event_type.as_deref())
            .bind(cursor.updated_at)
            .bind(cursor.id)
            .bind(limit_plus_one)
            .fetch_all(&self.pool)
            .await?
        } else {
            sqlx::query_as(
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
            .bind(limit_plus_one)
            .bind(offset)
            .fetch_all(&self.pool)
            .await?
        };
        let has_more = (rows.len() as i64) > limit;
        if has_more {
            rows.truncate(limit as usize);
        }
        let next_cursor = if has_more {
            rows.last()
                .map(|last| encode_list_kafka_dlq_events_cursor(last.updated_at, last.id))
        } else {
            None
        };
        let total = if include_total {
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
            Some(total.max(0) as u64)
        } else {
            None
        };

        Ok(ListKafkaDlqEventsOutput {
            total,
            limit: limit as u64,
            offset: offset as u64,
            has_more,
            next_cursor,
            items: rows
                .into_iter()
                .map(|row| map_dlq_row(row, expose_raw_error_message))
                .collect(),
        })
    }

    pub async fn replay_kafka_dlq_event(
        &self,
        user: &User,
        id: u64,
        meta: KafkaDlqActionMeta<'_>,
    ) -> Result<KafkaDlqActionOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::JudgeRejudge)
            .await?;
        let reason = normalize_dlq_action_reason(meta.reason)?;

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
            let message = format!("kafka dlq event id {}", id);
            self.append_kafka_dlq_action_audit_best_effort(KafkaDlqActionAuditInput {
                dlq_event_id: id,
                action: DLQ_ACTION_REPLAY,
                operator_user_id: user.id,
                result: DLQ_ACTION_RESULT_NOT_FOUND,
                before_status: None,
                after_status: None,
                reason: Some(reason.as_str()),
                request_id: meta.request_id,
                idempotency_key: meta.idempotency_key,
                error_message: Some(message.as_str()),
            })
            .await;
            return Err(AppError::NotFound(message));
        };
        if status != DLQ_STATUS_PENDING {
            let message = format!("dlq event {} status {} cannot replay", id, status);
            self.append_kafka_dlq_action_audit_best_effort(KafkaDlqActionAuditInput {
                dlq_event_id: id,
                action: DLQ_ACTION_REPLAY,
                operator_user_id: user.id,
                result: DLQ_ACTION_RESULT_CONFLICT,
                before_status: Some(status.as_str()),
                after_status: Some(status.as_str()),
                reason: Some(reason.as_str()),
                request_id: meta.request_id,
                idempotency_key: meta.idempotency_key,
                error_message: Some(message.as_str()),
            })
            .await;
            return Err(AppError::DebateConflict(message));
        }
        let envelope: EventEnvelope = match serde_json::from_value(payload) {
            Ok(value) => value,
            Err(err) => {
                let message = format!("dlq payload decode failed for id {}: {}", id, err);
                self.append_kafka_dlq_action_audit_best_effort(KafkaDlqActionAuditInput {
                    dlq_event_id: id,
                    action: DLQ_ACTION_REPLAY,
                    operator_user_id: user.id,
                    result: DLQ_ACTION_RESULT_FAILED,
                    before_status: Some(status.as_str()),
                    after_status: Some(status.as_str()),
                    reason: Some(reason.as_str()),
                    request_id: meta.request_id,
                    idempotency_key: meta.idempotency_key,
                    error_message: Some(message.as_str()),
                })
                .await;
                return Err(AppError::DebateError(message));
            }
        };
        let worker_meta = WorkerEnvelopeMeta {
            consumer_group,
            topic,
            partition,
            offset: message_offset,
        };
        let ret = process_worker_envelope(&self.pool, &worker_meta, &envelope).await;
        match ret {
            Ok(WorkerProcessOutcome::Succeeded) | Ok(WorkerProcessOutcome::Duplicated) => {
                let row: Option<KafkaDlqActionRow> = sqlx::query_as(
                    r#"
                    UPDATE kafka_dlq_events
                    SET status = $2,
                        replayed_at = NOW(),
                        updated_at = NOW()
                    WHERE id = $1
                      AND status = $3
                    RETURNING id, status, failure_count, error_message, replayed_at, discarded_at, updated_at
                    "#,
                )
                .bind(id as i64)
                .bind(DLQ_STATUS_REPLAYED)
                .bind(DLQ_STATUS_PENDING)
                .fetch_optional(&self.pool)
                .await?;
                let Some(row) = row else {
                    let message = format!("dlq event {} replay conflict: status changed", id);
                    self.append_kafka_dlq_action_audit_best_effort(KafkaDlqActionAuditInput {
                        dlq_event_id: id,
                        action: DLQ_ACTION_REPLAY,
                        operator_user_id: user.id,
                        result: DLQ_ACTION_RESULT_CONFLICT,
                        before_status: Some(status.as_str()),
                        after_status: None,
                        reason: Some(reason.as_str()),
                        request_id: meta.request_id,
                        idempotency_key: meta.idempotency_key,
                        error_message: Some(message.as_str()),
                    })
                    .await;
                    return Err(AppError::DebateConflict(message));
                };
                let output = map_dlq_action_row(row);
                self.append_kafka_dlq_action_audit_best_effort(KafkaDlqActionAuditInput {
                    dlq_event_id: id,
                    action: DLQ_ACTION_REPLAY,
                    operator_user_id: user.id,
                    result: DLQ_ACTION_RESULT_SUCCESS,
                    before_status: Some(status.as_str()),
                    after_status: Some(output.status.as_str()),
                    reason: Some(reason.as_str()),
                    request_id: meta.request_id,
                    idempotency_key: meta.idempotency_key,
                    error_message: None,
                })
                .await;
                Ok(output)
            }
            Err(err) => {
                let replay_error_message = format!("replay retryable error: {}", err);
                let row: Option<KafkaDlqActionRow> = sqlx::query_as(
                    r#"
                    UPDATE kafka_dlq_events
                    SET status = $2,
                        failure_count = failure_count + 1,
                        error_message = $3,
                        last_failed_at = NOW(),
                        updated_at = NOW()
                    WHERE id = $1
                      AND status = $4
                    RETURNING id, status, failure_count, error_message, replayed_at, discarded_at, updated_at
                    "#,
                )
                .bind(id as i64)
                .bind(DLQ_STATUS_PENDING)
                .bind(&replay_error_message)
                .bind(DLQ_STATUS_PENDING)
                .fetch_optional(&self.pool)
                .await?;
                let Some(row) = row else {
                    let message = format!("dlq event {} replay conflict: status changed", id);
                    self.append_kafka_dlq_action_audit_best_effort(KafkaDlqActionAuditInput {
                        dlq_event_id: id,
                        action: DLQ_ACTION_REPLAY,
                        operator_user_id: user.id,
                        result: DLQ_ACTION_RESULT_CONFLICT,
                        before_status: Some(status.as_str()),
                        after_status: None,
                        reason: Some(reason.as_str()),
                        request_id: meta.request_id,
                        idempotency_key: meta.idempotency_key,
                        error_message: Some(message.as_str()),
                    })
                    .await;
                    return Err(AppError::DebateConflict(message));
                };
                let output = map_dlq_action_row(row);
                self.append_kafka_dlq_action_audit_best_effort(KafkaDlqActionAuditInput {
                    dlq_event_id: id,
                    action: DLQ_ACTION_REPLAY,
                    operator_user_id: user.id,
                    result: DLQ_ACTION_RESULT_FAILED,
                    before_status: Some(status.as_str()),
                    after_status: Some(output.status.as_str()),
                    reason: Some(reason.as_str()),
                    request_id: meta.request_id,
                    idempotency_key: meta.idempotency_key,
                    error_message: Some(replay_error_message.as_str()),
                })
                .await;
                Ok(output)
            }
        }
    }

    pub async fn discard_kafka_dlq_event(
        &self,
        user: &User,
        id: u64,
        meta: KafkaDlqActionMeta<'_>,
    ) -> Result<KafkaDlqActionOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::JudgeRejudge)
            .await?;
        let reason = normalize_dlq_action_reason(meta.reason)?;
        let before_status: Option<String> = sqlx::query_scalar(
            r#"
            SELECT status
            FROM kafka_dlq_events
            WHERE id = $1
            "#,
        )
        .bind(id as i64)
        .fetch_optional(&self.pool)
        .await?;
        let Some(before_status) = before_status else {
            let message = format!("kafka dlq event id {}", id);
            self.append_kafka_dlq_action_audit_best_effort(KafkaDlqActionAuditInput {
                dlq_event_id: id,
                action: DLQ_ACTION_DISCARD,
                operator_user_id: user.id,
                result: DLQ_ACTION_RESULT_NOT_FOUND,
                before_status: None,
                after_status: None,
                reason: Some(reason.as_str()),
                request_id: meta.request_id,
                idempotency_key: meta.idempotency_key,
                error_message: Some(message.as_str()),
            })
            .await;
            return Err(AppError::NotFound(message));
        };
        if before_status != DLQ_STATUS_PENDING {
            let message = format!("dlq event {} status {} cannot discard", id, before_status);
            self.append_kafka_dlq_action_audit_best_effort(KafkaDlqActionAuditInput {
                dlq_event_id: id,
                action: DLQ_ACTION_DISCARD,
                operator_user_id: user.id,
                result: DLQ_ACTION_RESULT_CONFLICT,
                before_status: Some(before_status.as_str()),
                after_status: Some(before_status.as_str()),
                reason: Some(reason.as_str()),
                request_id: meta.request_id,
                idempotency_key: meta.idempotency_key,
                error_message: Some(message.as_str()),
            })
            .await;
            return Err(AppError::DebateConflict(message));
        }
        let row: Option<KafkaDlqActionRow> = sqlx::query_as(
            r#"
            UPDATE kafka_dlq_events
            SET status = $2,
                discarded_at = NOW(),
                updated_at = NOW()
            WHERE id = $1
              AND status = $3
            RETURNING id, status, failure_count, error_message, replayed_at, discarded_at, updated_at
            "#,
        )
        .bind(id as i64)
        .bind(DLQ_STATUS_DISCARDED)
        .bind(DLQ_STATUS_PENDING)
        .fetch_optional(&self.pool)
        .await?;
        let Some(row) = row else {
            let message = format!("dlq event {} discard conflict: status changed", id);
            self.append_kafka_dlq_action_audit_best_effort(KafkaDlqActionAuditInput {
                dlq_event_id: id,
                action: DLQ_ACTION_DISCARD,
                operator_user_id: user.id,
                result: DLQ_ACTION_RESULT_CONFLICT,
                before_status: Some(before_status.as_str()),
                after_status: None,
                reason: Some(reason.as_str()),
                request_id: meta.request_id,
                idempotency_key: meta.idempotency_key,
                error_message: Some(message.as_str()),
            })
            .await;
            return Err(AppError::DebateConflict(message));
        };
        let output = map_dlq_action_row(row);
        self.append_kafka_dlq_action_audit_best_effort(KafkaDlqActionAuditInput {
            dlq_event_id: id,
            action: DLQ_ACTION_DISCARD,
            operator_user_id: user.id,
            result: DLQ_ACTION_RESULT_SUCCESS,
            before_status: Some(before_status.as_str()),
            after_status: Some(output.status.as_str()),
            reason: Some(reason.as_str()),
            request_id: meta.request_id,
            idempotency_key: meta.idempotency_key,
            error_message: None,
        })
        .await;
        Ok(output)
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
    use crate::UpsertOpsRoleInput;
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

    async fn setup_ops_user_with_role(
        state: &AppState,
        owner: &User,
        user_id: u64,
        role: &str,
    ) -> Result<User> {
        state
            .upsert_ops_role_assignment_by_owner(
                owner,
                user_id,
                UpsertOpsRoleInput {
                    role: role.to_string(),
                },
            )
            .await?;
        let user = state
            .find_user_by_id(user_id as i64)
            .await?
            .expect("target user should exist in test fixture");
        Ok(user)
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

    async fn insert_discarded_dlq_event(state: &AppState, event_id: &str) -> Result<()> {
        sqlx::query(
            r#"
            INSERT INTO kafka_dlq_events(
                consumer_group, topic, partition, message_offset,
                event_id, event_type, aggregate_id, payload,
                status, failure_count, error_message,
                first_failed_at, last_failed_at, discarded_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'discarded', 1, 'discarded', NOW(), NOW(), NOW())
            "#,
        )
        .bind("test-group")
        .bind("debate.message.created")
        .bind(0_i32)
        .bind(3_i64)
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

    async fn insert_succeeded_consume_ledger(state: &AppState, event_id: &str) -> Result<()> {
        sqlx::query(
            r#"
            INSERT INTO kafka_consume_ledger(
                consumer_group, topic, partition, message_offset,
                event_id, event_type, aggregate_id, payload,
                status, error_message
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'succeeded', NULL)
            "#,
        )
        .bind("test-group")
        .bind("debate.message.created")
        .bind(0_i32)
        .bind(100_i64)
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

    async fn get_dlq_event_id(state: &AppState, event_id: &str) -> Result<u64> {
        let id: i64 = sqlx::query_scalar(
            r#"
            SELECT id
            FROM kafka_dlq_events
            WHERE consumer_group = $1
              AND event_id = $2
            "#,
        )
        .bind("test-group")
        .bind(event_id)
        .fetch_one(&state.pool)
        .await?;
        Ok(id as u64)
    }

    async fn set_dlq_event_updated_at(
        state: &AppState,
        event_id: &str,
        updated_at: DateTime<Utc>,
    ) -> Result<()> {
        sqlx::query(
            r#"
            UPDATE kafka_dlq_events
            SET updated_at = $3
            WHERE consumer_group = $1
              AND event_id = $2
            "#,
        )
        .bind("test-group")
        .bind(event_id)
        .bind(updated_at)
        .execute(&state.pool)
        .await?;
        Ok(())
    }

    async fn count_dlq_action_audits(
        state: &AppState,
        dlq_event_id: u64,
        action: &str,
        result: &str,
    ) -> Result<u64> {
        let count: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)
            FROM kafka_dlq_event_actions
            WHERE dlq_event_id = $1
              AND action = $2
              AND result = $3
            "#,
        )
        .bind(dlq_event_id as i64)
        .bind(action)
        .bind(result)
        .fetch_one(&state.pool)
        .await?;
        Ok(count.max(0) as u64)
    }

    async fn insert_dlq_action_audit_for_test(
        state: &AppState,
        dlq_event_id: u64,
        action: &str,
    ) -> Result<()> {
        sqlx::query(
            r#"
            INSERT INTO kafka_dlq_event_actions(
                dlq_event_id,
                action,
                operator_user_id,
                result,
                before_status,
                after_status,
                reason
            )
            VALUES ($1, $2, $3, 'success', NULL, NULL, 'retention-cleanup-test')
            "#,
        )
        .bind(dlq_event_id as i64)
        .bind(action)
        .bind(1_i64)
        .execute(&state.pool)
        .await?;
        Ok(())
    }

    fn test_dlq_action_meta<'a>() -> KafkaDlqActionMeta<'a> {
        KafkaDlqActionMeta {
            reason: Some("test-ops-action"),
            request_id: Some("req-test-kafka-dlq"),
            idempotency_key: Some("idem-test-kafka-dlq"),
        }
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

    #[tokio::test]
    async fn list_kafka_dlq_events_should_filter_and_clamp_pagination() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = setup_ops_owner(&state).await?;
        insert_pending_dlq_event(&state, "dlq-list-pending").await?;
        insert_replayed_dlq_event(&state, "dlq-list-replayed", Utc::now()).await?;

        let output = state
            .list_kafka_dlq_events(
                &owner,
                ListKafkaDlqEventsQuery {
                    status: Some("PENDING".to_string()),
                    event_type: None,
                    limit: Some(999),
                    offset: Some(0),
                    cursor: None,
                    include_total: Some(true),
                },
            )
            .await?;

        assert_eq!(output.limit, 100);
        assert!(output.total.unwrap_or_default() >= 1);
        assert!(!output.items.is_empty());
        assert!(output
            .items
            .iter()
            .all(|item| item.status == DLQ_STATUS_PENDING));
        Ok(())
    }

    #[tokio::test]
    async fn cleanup_kafka_dlq_retention_should_delete_only_old_terminal_rows() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let now = Utc::now();
        let cutoff = now - Duration::days(14);
        insert_pending_dlq_event(&state, "dlq-cleanup-pending-old").await?;
        set_dlq_event_updated_at(&state, "dlq-cleanup-pending-old", now - Duration::days(40))
            .await?;
        insert_replayed_dlq_event(&state, "dlq-cleanup-replayed-old", now - Duration::days(40))
            .await?;
        insert_discarded_dlq_event(&state, "dlq-cleanup-discarded-old").await?;
        set_dlq_event_updated_at(
            &state,
            "dlq-cleanup-discarded-old",
            now - Duration::days(35),
        )
        .await?;
        insert_replayed_dlq_event(
            &state,
            "dlq-cleanup-replayed-fresh",
            now - Duration::days(2),
        )
        .await?;

        let old_replayed_id = get_dlq_event_id(&state, "dlq-cleanup-replayed-old").await?;
        let old_discarded_id = get_dlq_event_id(&state, "dlq-cleanup-discarded-old").await?;
        let fresh_replayed_id = get_dlq_event_id(&state, "dlq-cleanup-replayed-fresh").await?;
        insert_dlq_action_audit_for_test(&state, old_replayed_id, DLQ_ACTION_REPLAY).await?;
        insert_dlq_action_audit_for_test(&state, old_discarded_id, DLQ_ACTION_DISCARD).await?;
        insert_dlq_action_audit_for_test(&state, fresh_replayed_id, DLQ_ACTION_REPLAY).await?;

        let first = state.cleanup_kafka_dlq_retention_before(cutoff, 1).await?;
        assert_eq!(first.deleted_event_rows, 1);
        assert_eq!(first.deleted_action_rows, 1);

        let second = state.cleanup_kafka_dlq_retention_before(cutoff, 1).await?;
        assert_eq!(second.deleted_event_rows, 1);
        assert_eq!(second.deleted_action_rows, 1);

        let third = state.cleanup_kafka_dlq_retention_before(cutoff, 1).await?;
        assert_eq!(third.deleted_event_rows, 0);
        assert_eq!(third.deleted_action_rows, 0);

        let pending_old_exists: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)
            FROM kafka_dlq_events
            WHERE consumer_group = $1
              AND event_id = $2
            "#,
        )
        .bind("test-group")
        .bind("dlq-cleanup-pending-old")
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(pending_old_exists, 1);

        let fresh_replayed_exists: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)
            FROM kafka_dlq_events
            WHERE id = $1
            "#,
        )
        .bind(fresh_replayed_id as i64)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(fresh_replayed_exists, 1);

        let old_replayed_exists: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)
            FROM kafka_dlq_events
            WHERE id = $1
            "#,
        )
        .bind(old_replayed_id as i64)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(old_replayed_exists, 0);

        let old_discarded_exists: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)
            FROM kafka_dlq_events
            WHERE id = $1
            "#,
        )
        .bind(old_discarded_id as i64)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(old_discarded_exists, 0);

        let old_replayed_actions: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)
            FROM kafka_dlq_event_actions
            WHERE dlq_event_id = $1
            "#,
        )
        .bind(old_replayed_id as i64)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(old_replayed_actions, 0);

        let old_discarded_actions: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)
            FROM kafka_dlq_event_actions
            WHERE dlq_event_id = $1
            "#,
        )
        .bind(old_discarded_id as i64)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(old_discarded_actions, 0);

        let fresh_replayed_actions: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)
            FROM kafka_dlq_event_actions
            WHERE dlq_event_id = $1
            "#,
        )
        .bind(fresh_replayed_id as i64)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(fresh_replayed_actions, 1);
        Ok(())
    }

    #[tokio::test]
    async fn list_kafka_dlq_events_should_reject_invalid_status_filter() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = setup_ops_owner(&state).await?;

        let err = state
            .list_kafka_dlq_events(
                &owner,
                ListKafkaDlqEventsQuery {
                    status: Some("bad-status".to_string()),
                    event_type: None,
                    limit: None,
                    offset: None,
                    cursor: None,
                    include_total: None,
                },
            )
            .await
            .expect_err("invalid status should fail");
        match err {
            AppError::DebateError(message) => {
                assert!(message.contains("invalid dlq status filter"));
            }
            other => panic!("unexpected error: {other:?}"),
        }
        Ok(())
    }

    #[tokio::test]
    async fn list_kafka_dlq_events_should_reject_invalid_cursor() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = setup_ops_owner(&state).await?;

        let err = state
            .list_kafka_dlq_events(
                &owner,
                ListKafkaDlqEventsQuery {
                    status: None,
                    event_type: None,
                    limit: Some(20),
                    offset: None,
                    cursor: Some("bad-cursor".to_string()),
                    include_total: None,
                },
            )
            .await
            .expect_err("invalid cursor should fail");
        match err {
            AppError::ValidationError(code) => assert_eq!(code, "ops_kafka_dlq_cursor_invalid"),
            other => panic!("unexpected error: {other:?}"),
        }
        Ok(())
    }

    #[tokio::test]
    async fn list_kafka_dlq_events_should_support_cursor_pagination_without_total() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = setup_ops_owner(&state).await?;
        insert_pending_dlq_event(&state, "dlq-cursor-1").await?;
        insert_pending_dlq_event(&state, "dlq-cursor-2").await?;
        insert_pending_dlq_event(&state, "dlq-cursor-3").await?;
        let now = Utc::now();
        set_dlq_event_updated_at(&state, "dlq-cursor-1", now - Duration::seconds(30)).await?;
        set_dlq_event_updated_at(&state, "dlq-cursor-2", now - Duration::seconds(20)).await?;
        set_dlq_event_updated_at(&state, "dlq-cursor-3", now - Duration::seconds(10)).await?;

        let first_page = state
            .list_kafka_dlq_events(
                &owner,
                ListKafkaDlqEventsQuery {
                    status: Some("pending".to_string()),
                    event_type: None,
                    limit: Some(2),
                    offset: Some(0),
                    cursor: None,
                    include_total: Some(false),
                },
            )
            .await?;
        assert_eq!(first_page.total, None);
        assert!(first_page.has_more);
        assert_eq!(first_page.items.len(), 2);
        assert_eq!(
            first_page.items.first().map(|item| item.event_id.as_str()),
            Some("dlq-cursor-3")
        );
        assert_eq!(
            first_page.items.get(1).map(|item| item.event_id.as_str()),
            Some("dlq-cursor-2")
        );
        let next_cursor = first_page
            .next_cursor
            .clone()
            .expect("first page should include cursor");

        let second_page = state
            .list_kafka_dlq_events(
                &owner,
                ListKafkaDlqEventsQuery {
                    status: Some("pending".to_string()),
                    event_type: None,
                    limit: Some(2),
                    offset: Some(9999),
                    cursor: Some(next_cursor),
                    include_total: Some(false),
                },
            )
            .await?;
        assert_eq!(second_page.total, None);
        assert!(!second_page.has_more);
        assert_eq!(second_page.offset, 0);
        assert_eq!(second_page.items.len(), 1);
        assert_eq!(
            second_page.items.first().map(|item| item.event_id.as_str()),
            Some("dlq-cursor-1")
        );
        Ok(())
    }

    #[tokio::test]
    async fn replay_kafka_dlq_event_should_mark_replayed_when_worker_reports_duplicated(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = setup_ops_owner(&state).await?;
        let event_id = "dlq-replay-duplicated";
        insert_pending_dlq_event(&state, event_id).await?;
        let dlq_event_id = get_dlq_event_id(&state, event_id).await?;
        insert_succeeded_consume_ledger(&state, event_id).await?;

        let output = state
            .replay_kafka_dlq_event(&owner, dlq_event_id, test_dlq_action_meta())
            .await?;
        assert_eq!(output.status, DLQ_STATUS_REPLAYED);
        assert_eq!(
            count_dlq_action_audits(
                &state,
                dlq_event_id,
                DLQ_ACTION_REPLAY,
                DLQ_ACTION_RESULT_SUCCESS
            )
            .await?,
            1
        );
        Ok(())
    }

    #[tokio::test]
    async fn replay_kafka_dlq_event_should_increment_failure_when_worker_still_fails() -> Result<()>
    {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = setup_ops_owner(&state).await?;
        let event_id = "dlq-replay-failed";
        insert_pending_dlq_event(&state, event_id).await?;
        let dlq_event_id = get_dlq_event_id(&state, event_id).await?;

        let output = state
            .replay_kafka_dlq_event(&owner, dlq_event_id, test_dlq_action_meta())
            .await?;
        assert_eq!(output.status, DLQ_STATUS_PENDING);
        assert_eq!(output.failure_count, 2);
        assert_eq!(
            count_dlq_action_audits(
                &state,
                dlq_event_id,
                DLQ_ACTION_REPLAY,
                DLQ_ACTION_RESULT_FAILED
            )
            .await?,
            1
        );
        Ok(())
    }

    #[tokio::test]
    async fn replay_kafka_dlq_event_should_return_conflict_for_discarded_event() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = setup_ops_owner(&state).await?;
        let event_id = "dlq-replay-discarded";
        insert_discarded_dlq_event(&state, event_id).await?;
        let dlq_event_id = get_dlq_event_id(&state, event_id).await?;

        let err = state
            .replay_kafka_dlq_event(&owner, dlq_event_id, test_dlq_action_meta())
            .await
            .expect_err("discarded event should reject replay");
        assert!(matches!(err, AppError::DebateConflict(_)));
        assert_eq!(
            count_dlq_action_audits(
                &state,
                dlq_event_id,
                DLQ_ACTION_REPLAY,
                DLQ_ACTION_RESULT_CONFLICT
            )
            .await?,
            1
        );
        Ok(())
    }

    #[tokio::test]
    async fn discard_kafka_dlq_event_should_mark_discarded_and_append_audit() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = setup_ops_owner(&state).await?;
        let event_id = "dlq-discard-success";
        insert_pending_dlq_event(&state, event_id).await?;
        let dlq_event_id = get_dlq_event_id(&state, event_id).await?;

        let output = state
            .discard_kafka_dlq_event(&owner, dlq_event_id, test_dlq_action_meta())
            .await?;
        assert_eq!(output.status, DLQ_STATUS_DISCARDED);
        assert_eq!(
            count_dlq_action_audits(
                &state,
                dlq_event_id,
                DLQ_ACTION_DISCARD,
                DLQ_ACTION_RESULT_SUCCESS
            )
            .await?,
            1
        );
        Ok(())
    }

    #[tokio::test]
    async fn discard_kafka_dlq_event_should_return_conflict_for_non_pending_event() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = setup_ops_owner(&state).await?;
        let event_id = "dlq-discard-conflict";
        insert_discarded_dlq_event(&state, event_id).await?;
        let dlq_event_id = get_dlq_event_id(&state, event_id).await?;

        let err = state
            .discard_kafka_dlq_event(&owner, dlq_event_id, test_dlq_action_meta())
            .await
            .expect_err("discarded event should reject discard");
        assert!(matches!(err, AppError::DebateConflict(_)));
        assert_eq!(
            count_dlq_action_audits(
                &state,
                dlq_event_id,
                DLQ_ACTION_DISCARD,
                DLQ_ACTION_RESULT_CONFLICT
            )
            .await?,
            1
        );
        Ok(())
    }

    #[tokio::test]
    async fn replay_kafka_dlq_event_should_require_non_empty_reason() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = setup_ops_owner(&state).await?;
        let event_id = "dlq-replay-empty-reason";
        insert_pending_dlq_event(&state, event_id).await?;
        let dlq_event_id = get_dlq_event_id(&state, event_id).await?;

        let err = state
            .replay_kafka_dlq_event(
                &owner,
                dlq_event_id,
                KafkaDlqActionMeta {
                    reason: Some("   "),
                    request_id: Some("req-empty-reason"),
                    idempotency_key: Some("idem-empty-reason"),
                },
            )
            .await
            .expect_err("empty reason should reject replay");
        assert!(matches!(err, AppError::DebateError(_)));
        Ok(())
    }

    #[tokio::test]
    async fn discard_kafka_dlq_event_should_require_non_empty_reason() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = setup_ops_owner(&state).await?;
        let event_id = "dlq-discard-empty-reason";
        insert_pending_dlq_event(&state, event_id).await?;
        let dlq_event_id = get_dlq_event_id(&state, event_id).await?;

        let err = state
            .discard_kafka_dlq_event(
                &owner,
                dlq_event_id,
                KafkaDlqActionMeta {
                    reason: Some("  "),
                    request_id: Some("req-discard-empty-reason"),
                    idempotency_key: Some("idem-discard-empty-reason"),
                },
            )
            .await
            .expect_err("empty reason should reject discard");
        assert!(matches!(err, AppError::DebateError(_)));
        Ok(())
    }

    #[tokio::test]
    async fn replay_kafka_dlq_event_should_reject_too_long_reason() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = setup_ops_owner(&state).await?;
        let event_id = "dlq-replay-too-long-reason";
        insert_pending_dlq_event(&state, event_id).await?;
        let dlq_event_id = get_dlq_event_id(&state, event_id).await?;
        let too_long_reason = "x".repeat(241);

        let err = state
            .replay_kafka_dlq_event(
                &owner,
                dlq_event_id,
                KafkaDlqActionMeta {
                    reason: Some(too_long_reason.as_str()),
                    request_id: Some("req-too-long-reason"),
                    idempotency_key: Some("idem-too-long-reason"),
                },
            )
            .await
            .expect_err("too long reason should reject replay");
        assert!(matches!(err, AppError::DebateError(_)));
        Ok(())
    }

    #[tokio::test]
    async fn list_kafka_dlq_events_should_mask_error_message_for_ops_viewer() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = setup_ops_owner(&state).await?;
        let viewer = setup_ops_user_with_role(&state, &owner, 2, "ops_viewer").await?;
        let event_id = "dlq-list-mask-viewer";
        insert_pending_dlq_event(&state, event_id).await?;
        sqlx::query(
            r#"
            UPDATE kafka_dlq_events
            SET error_message = $2
            WHERE consumer_group = $1
              AND event_id = $3
            "#,
        )
        .bind("test-group")
        .bind("retryable worker error: unique violation on uq_messages_session_seq")
        .bind(event_id)
        .execute(&state.pool)
        .await?;

        let output = state
            .list_kafka_dlq_events(
                &viewer,
                ListKafkaDlqEventsQuery {
                    status: Some("pending".to_string()),
                    event_type: None,
                    limit: Some(20),
                    offset: Some(0),
                    cursor: None,
                    include_total: None,
                },
            )
            .await?;
        let item = output
            .items
            .iter()
            .find(|v| v.event_id == event_id)
            .expect("target event should be listed");
        assert_eq!(item.error_message, DLQ_ERROR_MESSAGE_MASKED_BY_ROLE);
        assert_eq!(item.error_class, DLQ_ERROR_CLASS_DB_CONFLICT);
        assert_eq!(item.error_code, DLQ_ERROR_CLASS_DB_CONFLICT);
        Ok(())
    }

    #[tokio::test]
    async fn list_kafka_dlq_events_should_keep_raw_error_message_for_ops_reviewer() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = setup_ops_owner(&state).await?;
        let reviewer = setup_ops_user_with_role(&state, &owner, 2, "ops_reviewer").await?;
        let event_id = "dlq-list-mask-reviewer";
        let raw_error = "retryable worker error: connection refused by upstream relay";
        insert_pending_dlq_event(&state, event_id).await?;
        sqlx::query(
            r#"
            UPDATE kafka_dlq_events
            SET error_message = $2
            WHERE consumer_group = $1
              AND event_id = $3
            "#,
        )
        .bind("test-group")
        .bind(raw_error)
        .bind(event_id)
        .execute(&state.pool)
        .await?;

        let output = state
            .list_kafka_dlq_events(
                &reviewer,
                ListKafkaDlqEventsQuery {
                    status: Some("pending".to_string()),
                    event_type: None,
                    limit: Some(20),
                    offset: Some(0),
                    cursor: None,
                    include_total: None,
                },
            )
            .await?;
        let item = output
            .items
            .iter()
            .find(|v| v.event_id == event_id)
            .expect("target event should be listed");
        assert_eq!(item.error_message, raw_error);
        assert_eq!(item.error_class, DLQ_ERROR_CLASS_UPSTREAM_UNAVAILABLE);
        assert_eq!(item.error_code, DLQ_ERROR_CLASS_UPSTREAM_UNAVAILABLE);
        Ok(())
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
