use crate::{AppError, AppState};
use anyhow::Context;
use chat_core::User;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sqlx::FromRow;
use std::collections::{HashMap, HashSet};
use utoipa::{IntoParams, ToSchema};

use super::OpsPermission;

const MAX_STATE_KEY_LEN: usize = 200;
const MAX_STATE_ITEM_COUNT: usize = 1000;
const ALERT_STATUS_RAISED: &str = "raised";
const ALERT_STATUS_CLEARED: &str = "cleared";
const ALERT_STATUS_SUPPRESSED: &str = "suppressed";
const ALERT_DELIVERY_PENDING: &str = "pending";
const ALERT_DELIVERY_SENT: &str = "sent";
const ALERT_DELIVERY_FAILED: &str = "failed";
const ALERT_SEVERITY_WARNING: &str = "warning";
const OPS_ALERT_RULE_LOW_SUCCESS_RATE: &str = "low_success_rate";
const OPS_ALERT_RULE_HIGH_RETRY: &str = "high_retry";
const OPS_ALERT_RULE_HIGH_DB_LATENCY: &str = "high_db_latency";
const OPS_ALERT_RULE_DLQ_PENDING: &str = "dlq_pending";
const OPS_ALERT_EVAL_WINDOW_MINUTES: i64 = 10;

fn clamp_float(value: f64, min: f64, max: f64, fallback: f64) -> f64 {
    if !value.is_finite() {
        return fallback;
    }
    value.clamp(min, max)
}

fn clamp_int(value: i64, min: i64, max: i64) -> i64 {
    value.clamp(min, max)
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OpsObservabilityThresholds {
    pub low_success_rate_threshold: f64,
    pub high_retry_threshold: f64,
    pub high_coalesced_threshold: f64,
    pub high_db_latency_threshold_ms: i64,
    pub low_cache_hit_rate_threshold: f64,
    pub min_request_for_cache_hit_check: i64,
}

impl Default for OpsObservabilityThresholds {
    fn default() -> Self {
        Self {
            low_success_rate_threshold: 80.0,
            high_retry_threshold: 1.0,
            high_coalesced_threshold: 2.0,
            high_db_latency_threshold_ms: 1200,
            low_cache_hit_rate_threshold: 20.0,
            min_request_for_cache_hit_check: 20,
        }
    }
}

#[derive(Debug, Default, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
struct OpsObservabilityThresholdsPayload {
    low_success_rate_threshold: Option<f64>,
    high_retry_threshold: Option<f64>,
    high_coalesced_threshold: Option<f64>,
    high_db_latency_threshold_ms: Option<i64>,
    low_cache_hit_rate_threshold: Option<f64>,
    min_request_for_cache_hit_check: Option<i64>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OpsObservabilityAnomalyStateValue {
    #[serde(default)]
    pub acknowledged_at_ms: i64,
    #[serde(default)]
    pub suppress_until_ms: i64,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UpdateOpsObservabilityAnomalyStateInput {
    #[serde(default)]
    pub anomaly_state: HashMap<String, OpsObservabilityAnomalyStateValue>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetOpsObservabilityConfigOutput {
    pub ws_id: u64,
    pub thresholds: OpsObservabilityThresholds,
    #[serde(default)]
    pub anomaly_state: HashMap<String, OpsObservabilityAnomalyStateValue>,
    pub updated_by: Option<u64>,
    pub updated_at: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone, FromRow)]
struct OpsObservabilityConfigRow {
    thresholds_json: Value,
    anomaly_state_json: Value,
    updated_by: i64,
    updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, IntoParams, ToSchema, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListOpsAlertNotificationsQuery {
    pub status: Option<String>,
    pub limit: Option<u64>,
    pub offset: Option<u64>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OpsAlertNotificationItem {
    pub id: u64,
    pub ws_id: u64,
    pub alert_key: String,
    pub rule_type: String,
    pub severity: String,
    pub alert_status: String,
    pub title: String,
    pub message: String,
    pub metrics: Value,
    pub recipients: Vec<u64>,
    pub delivery_status: String,
    pub error_message: Option<String>,
    pub delivered_at: Option<DateTime<Utc>>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListOpsAlertNotificationsOutput {
    pub total: u64,
    pub limit: u64,
    pub offset: u64,
    pub items: Vec<OpsAlertNotificationItem>,
}

#[derive(Debug, Clone, Default, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct OpsAlertEvalReport {
    pub workspaces_scanned: u64,
    pub alerts_raised: u64,
    pub alerts_cleared: u64,
    pub alerts_suppressed: u64,
}

#[derive(Debug, Clone, FromRow)]
struct OpsAlertNotificationRow {
    id: i64,
    ws_id: i64,
    alert_key: String,
    rule_type: String,
    severity: String,
    alert_status: String,
    title: String,
    message: String,
    metrics_json: Value,
    recipients_json: Value,
    delivery_status: String,
    error_message: Option<String>,
    delivered_at: Option<DateTime<Utc>>,
    created_at: DateTime<Utc>,
    updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
struct OpsAlertStateRow {
    is_active: bool,
    last_emitted_status: String,
}

#[derive(Debug, Clone, FromRow)]
struct OpsObservabilityEvalWorkspaceRow {
    ws_id: i64,
    thresholds_json: Value,
    anomaly_state_json: Value,
}

#[derive(Debug, Clone, FromRow)]
struct OpsRecentJudgeSignalRow {
    success_count: i64,
    failed_count: i64,
    avg_dispatch_attempts: Option<f64>,
    p95_latency_ms: Option<f64>,
}

#[derive(Debug, Clone, Copy)]
struct OpsRecentJudgeSignal {
    success_count: i64,
    failed_count: i64,
    avg_dispatch_attempts: f64,
    p95_latency_ms: f64,
    pending_dlq_count: i64,
}

#[derive(Debug, Clone)]
struct AlertSpec {
    alert_key: &'static str,
    rule_type: &'static str,
    title: &'static str,
}

#[derive(Debug, Clone)]
struct EvaluatedAlert {
    alert_key: String,
    rule_type: String,
    severity: String,
    title: String,
    message: String,
    metrics: Value,
    is_active: bool,
}

#[derive(Debug, Clone)]
struct EmitAlertPlan {
    status: &'static str,
    mark_active: bool,
    evaluated: EvaluatedAlert,
}

fn normalize_thresholds_payload(
    payload: OpsObservabilityThresholdsPayload,
) -> OpsObservabilityThresholds {
    let defaults = OpsObservabilityThresholds::default();
    OpsObservabilityThresholds {
        low_success_rate_threshold: clamp_float(
            payload
                .low_success_rate_threshold
                .unwrap_or(defaults.low_success_rate_threshold),
            1.0,
            99.99,
            defaults.low_success_rate_threshold,
        ),
        high_retry_threshold: clamp_float(
            payload
                .high_retry_threshold
                .unwrap_or(defaults.high_retry_threshold),
            0.1,
            10.0,
            defaults.high_retry_threshold,
        ),
        high_coalesced_threshold: clamp_float(
            payload
                .high_coalesced_threshold
                .unwrap_or(defaults.high_coalesced_threshold),
            0.1,
            20.0,
            defaults.high_coalesced_threshold,
        ),
        high_db_latency_threshold_ms: clamp_int(
            payload
                .high_db_latency_threshold_ms
                .unwrap_or(defaults.high_db_latency_threshold_ms),
            1,
            60_000,
        ),
        low_cache_hit_rate_threshold: clamp_float(
            payload
                .low_cache_hit_rate_threshold
                .unwrap_or(defaults.low_cache_hit_rate_threshold),
            0.0,
            99.99,
            defaults.low_cache_hit_rate_threshold,
        ),
        min_request_for_cache_hit_check: clamp_int(
            payload
                .min_request_for_cache_hit_check
                .unwrap_or(defaults.min_request_for_cache_hit_check),
            1,
            1_000_000,
        ),
    }
}

fn normalize_thresholds(input: OpsObservabilityThresholds) -> OpsObservabilityThresholds {
    normalize_thresholds_payload(OpsObservabilityThresholdsPayload {
        low_success_rate_threshold: Some(input.low_success_rate_threshold),
        high_retry_threshold: Some(input.high_retry_threshold),
        high_coalesced_threshold: Some(input.high_coalesced_threshold),
        high_db_latency_threshold_ms: Some(input.high_db_latency_threshold_ms),
        low_cache_hit_rate_threshold: Some(input.low_cache_hit_rate_threshold),
        min_request_for_cache_hit_check: Some(input.min_request_for_cache_hit_check),
    })
}

fn parse_thresholds(value: Value) -> OpsObservabilityThresholds {
    let payload = serde_json::from_value::<OpsObservabilityThresholdsPayload>(value)
        .unwrap_or_else(|_| OpsObservabilityThresholdsPayload::default());
    normalize_thresholds_payload(payload)
}

fn now_millis() -> i64 {
    Utc::now().timestamp_millis()
}

fn normalize_anomaly_state(
    input: HashMap<String, OpsObservabilityAnomalyStateValue>,
    now_ms: i64,
) -> HashMap<String, OpsObservabilityAnomalyStateValue> {
    let mut ret = HashMap::new();
    for (key_raw, item) in input {
        if ret.len() >= MAX_STATE_ITEM_COUNT {
            break;
        }
        let key = key_raw.trim();
        if key.is_empty() || key.len() > MAX_STATE_KEY_LEN {
            continue;
        }
        let acknowledged_at_ms = item.acknowledged_at_ms.max(0);
        let suppress_until_ms = if item.suppress_until_ms > now_ms {
            item.suppress_until_ms
        } else {
            0
        };
        if acknowledged_at_ms <= 0 && suppress_until_ms <= 0 {
            continue;
        }
        ret.insert(
            key.to_string(),
            OpsObservabilityAnomalyStateValue {
                acknowledged_at_ms,
                suppress_until_ms,
            },
        );
    }
    ret
}

fn parse_anomaly_state(
    value: Value,
    now_ms: i64,
) -> HashMap<String, OpsObservabilityAnomalyStateValue> {
    let payload =
        serde_json::from_value::<HashMap<String, OpsObservabilityAnomalyStateValue>>(value)
            .unwrap_or_default();
    normalize_anomaly_state(payload, now_ms)
}

fn build_output(
    ws_id: u64,
    row: Option<OpsObservabilityConfigRow>,
    now_ms: i64,
) -> GetOpsObservabilityConfigOutput {
    let Some(row) = row else {
        return GetOpsObservabilityConfigOutput {
            ws_id,
            thresholds: OpsObservabilityThresholds::default(),
            anomaly_state: HashMap::new(),
            updated_by: None,
            updated_at: None,
        };
    };
    GetOpsObservabilityConfigOutput {
        ws_id,
        thresholds: parse_thresholds(row.thresholds_json),
        anomaly_state: parse_anomaly_state(row.anomaly_state_json, now_ms),
        updated_by: Some(row.updated_by as u64),
        updated_at: Some(row.updated_at),
    }
}

fn normalize_alert_limit(limit: Option<u64>) -> i64 {
    limit.unwrap_or(20).clamp(1, 200) as i64
}

fn normalize_alert_offset(offset: Option<u64>) -> i64 {
    offset.unwrap_or(0).min(50_000) as i64
}

fn normalize_alert_status_filter(status: Option<String>) -> Result<Option<String>, AppError> {
    let Some(status) = status else {
        return Ok(None);
    };
    let normalized = status.trim().to_ascii_lowercase();
    if normalized.is_empty() {
        return Ok(None);
    }
    if matches!(
        normalized.as_str(),
        ALERT_STATUS_RAISED | ALERT_STATUS_CLEARED | ALERT_STATUS_SUPPRESSED
    ) {
        return Ok(Some(normalized));
    }
    Err(AppError::DebateError(
        "invalid alert status filter, expect raised/cleared/suppressed".to_string(),
    ))
}

fn parse_recipient_ids(value: &Value) -> Vec<u64> {
    let Some(arr) = value.as_array() else {
        return vec![];
    };
    arr.iter()
        .filter_map(|v| {
            v.as_u64()
                .or_else(|| v.as_i64().and_then(|n| u64::try_from(n).ok()))
        })
        .collect()
}

fn map_alert_notification_row(row: OpsAlertNotificationRow) -> OpsAlertNotificationItem {
    OpsAlertNotificationItem {
        id: row.id as u64,
        ws_id: row.ws_id as u64,
        alert_key: row.alert_key,
        rule_type: row.rule_type,
        severity: row.severity,
        alert_status: row.alert_status,
        title: row.title,
        message: row.message,
        metrics: row.metrics_json,
        recipients: parse_recipient_ids(&row.recipients_json),
        delivery_status: row.delivery_status,
        error_message: row.error_message,
        delivered_at: row.delivered_at,
        created_at: row.created_at,
        updated_at: row.updated_at,
    }
}

fn rule_specs() -> &'static [AlertSpec] {
    &[
        AlertSpec {
            alert_key: OPS_ALERT_RULE_LOW_SUCCESS_RATE,
            rule_type: OPS_ALERT_RULE_LOW_SUCCESS_RATE,
            title: "判决成功率偏低",
        },
        AlertSpec {
            alert_key: OPS_ALERT_RULE_HIGH_RETRY,
            rule_type: OPS_ALERT_RULE_HIGH_RETRY,
            title: "判决分发重试偏高",
        },
        AlertSpec {
            alert_key: OPS_ALERT_RULE_HIGH_DB_LATENCY,
            rule_type: OPS_ALERT_RULE_HIGH_DB_LATENCY,
            title: "判决链路时延偏高",
        },
        AlertSpec {
            alert_key: OPS_ALERT_RULE_DLQ_PENDING,
            rule_type: OPS_ALERT_RULE_DLQ_PENDING,
            title: "Kafka DLQ 待处理积压",
        },
    ]
}

fn evaluate_alert_for_rule(
    spec: &AlertSpec,
    thresholds: &OpsObservabilityThresholds,
    signal: OpsRecentJudgeSignal,
) -> EvaluatedAlert {
    match spec.rule_type {
        OPS_ALERT_RULE_LOW_SUCCESS_RATE => {
            let completed = signal.success_count + signal.failed_count;
            let success_rate = if completed <= 0 {
                100.0
            } else {
                (signal.success_count as f64 * 100.0) / completed as f64
            };
            let is_active = completed >= thresholds.min_request_for_cache_hit_check
                && success_rate < thresholds.low_success_rate_threshold;
            EvaluatedAlert {
                alert_key: spec.alert_key.to_string(),
                rule_type: spec.rule_type.to_string(),
                severity: ALERT_SEVERITY_WARNING.to_string(),
                title: spec.title.to_string(),
                message: format!(
                    "最近{}分钟判决成功率 {:.2}% 低于阈值 {:.2}%",
                    OPS_ALERT_EVAL_WINDOW_MINUTES,
                    success_rate,
                    thresholds.low_success_rate_threshold
                ),
                metrics: serde_json::json!({
                    "windowMinutes": OPS_ALERT_EVAL_WINDOW_MINUTES,
                    "completedCount": completed,
                    "successCount": signal.success_count,
                    "failedCount": signal.failed_count,
                    "successRatePct": success_rate,
                    "thresholdPct": thresholds.low_success_rate_threshold,
                }),
                is_active,
            }
        }
        OPS_ALERT_RULE_HIGH_RETRY => {
            let completed = signal.success_count + signal.failed_count;
            let is_active = completed >= thresholds.min_request_for_cache_hit_check
                && signal.avg_dispatch_attempts > thresholds.high_retry_threshold;
            EvaluatedAlert {
                alert_key: spec.alert_key.to_string(),
                rule_type: spec.rule_type.to_string(),
                severity: ALERT_SEVERITY_WARNING.to_string(),
                title: spec.title.to_string(),
                message: format!(
                    "最近{}分钟平均 dispatch_attempts {:.2} 高于阈值 {:.2}",
                    OPS_ALERT_EVAL_WINDOW_MINUTES,
                    signal.avg_dispatch_attempts,
                    thresholds.high_retry_threshold
                ),
                metrics: serde_json::json!({
                    "windowMinutes": OPS_ALERT_EVAL_WINDOW_MINUTES,
                    "completedCount": completed,
                    "avgDispatchAttempts": signal.avg_dispatch_attempts,
                    "threshold": thresholds.high_retry_threshold,
                }),
                is_active,
            }
        }
        OPS_ALERT_RULE_HIGH_DB_LATENCY => {
            let completed = signal.success_count + signal.failed_count;
            let is_active = completed >= thresholds.min_request_for_cache_hit_check
                && signal.p95_latency_ms > thresholds.high_db_latency_threshold_ms as f64;
            EvaluatedAlert {
                alert_key: spec.alert_key.to_string(),
                rule_type: spec.rule_type.to_string(),
                severity: ALERT_SEVERITY_WARNING.to_string(),
                title: spec.title.to_string(),
                message: format!(
                    "最近{}分钟判决链路 P95 时延 {:.0}ms 高于阈值 {}ms",
                    OPS_ALERT_EVAL_WINDOW_MINUTES,
                    signal.p95_latency_ms,
                    thresholds.high_db_latency_threshold_ms
                ),
                metrics: serde_json::json!({
                    "windowMinutes": OPS_ALERT_EVAL_WINDOW_MINUTES,
                    "completedCount": completed,
                    "p95LatencyMs": signal.p95_latency_ms,
                    "thresholdMs": thresholds.high_db_latency_threshold_ms,
                }),
                is_active,
            }
        }
        OPS_ALERT_RULE_DLQ_PENDING => {
            let is_active = signal.pending_dlq_count as f64 > thresholds.high_coalesced_threshold;
            EvaluatedAlert {
                alert_key: spec.alert_key.to_string(),
                rule_type: spec.rule_type.to_string(),
                severity: ALERT_SEVERITY_WARNING.to_string(),
                title: spec.title.to_string(),
                message: format!(
                    "当前 DLQ pending 数量 {} 超过阈值 {:.2}",
                    signal.pending_dlq_count, thresholds.high_coalesced_threshold
                ),
                metrics: serde_json::json!({
                    "pendingDlqCount": signal.pending_dlq_count,
                    "threshold": thresholds.high_coalesced_threshold,
                }),
                is_active,
            }
        }
        _ => EvaluatedAlert {
            alert_key: spec.alert_key.to_string(),
            rule_type: spec.rule_type.to_string(),
            severity: ALERT_SEVERITY_WARNING.to_string(),
            title: spec.title.to_string(),
            message: "unknown rule".to_string(),
            metrics: Value::Null,
            is_active: false,
        },
    }
}

fn build_emit_plan(
    evaluated: EvaluatedAlert,
    previous: Option<OpsAlertStateRow>,
    suppression_state: Option<&OpsObservabilityAnomalyStateValue>,
    now_ms: i64,
) -> Option<EmitAlertPlan> {
    let previous_active = previous.as_ref().map(|v| v.is_active).unwrap_or(false);
    let previous_status = previous
        .as_ref()
        .map(|v| v.last_emitted_status.as_str())
        .unwrap_or(ALERT_STATUS_CLEARED);
    let suppressed = suppression_state
        .map(|v| v.suppress_until_ms > now_ms)
        .unwrap_or(false);

    if evaluated.is_active {
        if !previous_active {
            let status = if suppressed {
                ALERT_STATUS_SUPPRESSED
            } else {
                ALERT_STATUS_RAISED
            };
            return Some(EmitAlertPlan {
                status,
                mark_active: true,
                evaluated,
            });
        }
        if previous_status == ALERT_STATUS_SUPPRESSED && !suppressed {
            return Some(EmitAlertPlan {
                status: ALERT_STATUS_RAISED,
                mark_active: true,
                evaluated,
            });
        }
        return None;
    }

    if previous_active {
        return Some(EmitAlertPlan {
            status: ALERT_STATUS_CLEARED,
            mark_active: false,
            evaluated,
        });
    }
    None
}

impl AppState {
    pub async fn get_ops_observability_config(
        &self,
        user: &User,
    ) -> Result<GetOpsObservabilityConfigOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::JudgeReview)
            .await?;
        let row: Option<OpsObservabilityConfigRow> = sqlx::query_as(
            r#"
            SELECT thresholds_json, anomaly_state_json, updated_by, updated_at
            FROM ops_observability_configs
            WHERE ws_id = $1
            "#,
        )
        .bind(user.ws_id)
        .fetch_optional(&self.pool)
        .await?;
        Ok(build_output(user.ws_id as u64, row, now_millis()))
    }

    pub async fn upsert_ops_observability_thresholds(
        &self,
        user: &User,
        input: OpsObservabilityThresholds,
    ) -> Result<GetOpsObservabilityConfigOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::JudgeReview)
            .await?;
        let thresholds = normalize_thresholds(input);
        let thresholds_json = serde_json::to_value(&thresholds)
            .context("serialize observability thresholds failed")?;
        sqlx::query(
            r#"
            INSERT INTO ops_observability_configs(
                ws_id, thresholds_json, anomaly_state_json, updated_by, created_at, updated_at
            )
            VALUES ($1, $2, '{}'::jsonb, $3, NOW(), NOW())
            ON CONFLICT (ws_id)
            DO UPDATE
            SET thresholds_json = EXCLUDED.thresholds_json,
                updated_by = EXCLUDED.updated_by,
                updated_at = NOW()
            "#,
        )
        .bind(user.ws_id)
        .bind(thresholds_json)
        .bind(user.id)
        .execute(&self.pool)
        .await?;
        self.get_ops_observability_config(user).await
    }

    pub async fn upsert_ops_observability_anomaly_state(
        &self,
        user: &User,
        input: UpdateOpsObservabilityAnomalyStateInput,
    ) -> Result<GetOpsObservabilityConfigOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::JudgeReview)
            .await?;
        let now_ms = now_millis();
        let anomaly_state = normalize_anomaly_state(input.anomaly_state, now_ms);
        let anomaly_state_json = serde_json::to_value(&anomaly_state)
            .context("serialize observability anomaly state failed")?;
        let default_thresholds_json =
            serde_json::to_value(OpsObservabilityThresholds::default())
                .context("serialize default observability thresholds failed")?;
        sqlx::query(
            r#"
            INSERT INTO ops_observability_configs(
                ws_id, thresholds_json, anomaly_state_json, updated_by, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, NOW(), NOW())
            ON CONFLICT (ws_id)
            DO UPDATE
            SET anomaly_state_json = EXCLUDED.anomaly_state_json,
                updated_by = EXCLUDED.updated_by,
                updated_at = NOW()
            "#,
        )
        .bind(user.ws_id)
        .bind(default_thresholds_json)
        .bind(anomaly_state_json)
        .bind(user.id)
        .execute(&self.pool)
        .await?;
        self.get_ops_observability_config(user).await
    }

    pub async fn list_ops_alert_notifications(
        &self,
        user: &User,
        query: ListOpsAlertNotificationsQuery,
    ) -> Result<ListOpsAlertNotificationsOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::JudgeReview)
            .await?;
        let status = normalize_alert_status_filter(query.status)?;
        let limit = normalize_alert_limit(query.limit);
        let offset = normalize_alert_offset(query.offset);

        let total: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)
            FROM ops_alert_notifications
            WHERE ws_id = $1
              AND ($2::text IS NULL OR alert_status = $2)
            "#,
        )
        .bind(user.ws_id)
        .bind(status.as_deref())
        .fetch_one(&self.pool)
        .await?;
        let rows: Vec<OpsAlertNotificationRow> = sqlx::query_as(
            r#"
            SELECT
                id, ws_id, alert_key, rule_type, severity, alert_status,
                title, message, metrics_json, recipients_json,
                delivery_status, error_message, delivered_at, created_at, updated_at
            FROM ops_alert_notifications
            WHERE ws_id = $1
              AND ($2::text IS NULL OR alert_status = $2)
            ORDER BY created_at DESC, id DESC
            LIMIT $3 OFFSET $4
            "#,
        )
        .bind(user.ws_id)
        .bind(status.as_deref())
        .bind(limit)
        .bind(offset)
        .fetch_all(&self.pool)
        .await?;
        Ok(ListOpsAlertNotificationsOutput {
            total: total.max(0) as u64,
            limit: limit as u64,
            offset: offset as u64,
            items: rows.into_iter().map(map_alert_notification_row).collect(),
        })
    }

    async fn list_observability_eval_workspaces(
        &self,
    ) -> Result<Vec<OpsObservabilityEvalWorkspaceRow>, AppError> {
        let rows: Vec<OpsObservabilityEvalWorkspaceRow> = sqlx::query_as(
            r#"
            SELECT
                w.id AS ws_id,
                COALESCE(c.thresholds_json, '{}'::jsonb) AS thresholds_json,
                COALESCE(c.anomaly_state_json, '{}'::jsonb) AS anomaly_state_json
            FROM workspaces w
            LEFT JOIN ops_observability_configs c ON c.ws_id = w.id
            ORDER BY w.id ASC
            "#,
        )
        .fetch_all(&self.pool)
        .await?;
        Ok(rows)
    }

    async fn load_recent_judge_signal(&self, ws_id: i64) -> Result<OpsRecentJudgeSignal, AppError> {
        let row: OpsRecentJudgeSignalRow = sqlx::query_as(
            r#"
            SELECT
                COUNT(1) FILTER (
                    WHERE status = 'succeeded'
                      AND finished_at >= NOW() - ($2::bigint * INTERVAL '1 minute')
                )::bigint AS success_count,
                COUNT(1) FILTER (
                    WHERE status = 'failed'
                      AND finished_at >= NOW() - ($2::bigint * INTERVAL '1 minute')
                )::bigint AS failed_count,
                COALESCE(AVG(dispatch_attempts::double precision) FILTER (
                    WHERE requested_at >= NOW() - ($2::bigint * INTERVAL '1 minute')
                ), 0)::double precision AS avg_dispatch_attempts,
                COALESCE(PERCENTILE_CONT(0.95) WITHIN GROUP (
                    ORDER BY EXTRACT(EPOCH FROM (COALESCE(finished_at, NOW()) - requested_at)) * 1000
                ) FILTER (
                    WHERE requested_at >= NOW() - ($2::bigint * INTERVAL '1 minute')
                ), 0)::double precision AS p95_latency_ms
            FROM judge_jobs
            WHERE ws_id = $1
            "#,
        )
        .bind(ws_id)
        .bind(OPS_ALERT_EVAL_WINDOW_MINUTES)
        .fetch_one(&self.pool)
        .await?;
        let pending_dlq_count: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)::bigint
            FROM kafka_dlq_events
            WHERE ws_id = $1
              AND status = 'pending'
            "#,
        )
        .bind(ws_id)
        .fetch_one(&self.pool)
        .await?;
        Ok(OpsRecentJudgeSignal {
            success_count: row.success_count,
            failed_count: row.failed_count,
            avg_dispatch_attempts: row.avg_dispatch_attempts.unwrap_or_default(),
            p95_latency_ms: row.p95_latency_ms.unwrap_or_default(),
            pending_dlq_count,
        })
    }

    async fn list_alert_recipients(&self, ws_id: i64) -> Result<Vec<u64>, AppError> {
        let owners: Vec<i64> = sqlx::query_scalar(
            r#"
            SELECT owner_id
            FROM workspaces
            WHERE id = $1
            "#,
        )
        .bind(ws_id)
        .fetch_all(&self.pool)
        .await?;
        let role_users: Vec<i64> = sqlx::query_scalar(
            r#"
            SELECT user_id
            FROM workspace_user_roles
            WHERE ws_id = $1
              AND role IN ('ops_admin', 'ops_reviewer', 'ops_viewer')
            "#,
        )
        .bind(ws_id)
        .fetch_all(&self.pool)
        .await?;
        let mut set = HashSet::<u64>::new();
        for id in owners.into_iter().chain(role_users.into_iter()) {
            if let Ok(v) = u64::try_from(id) {
                set.insert(v);
            }
        }
        let mut ret: Vec<u64> = set.into_iter().collect();
        ret.sort_unstable();
        Ok(ret)
    }

    async fn emit_observability_alert(
        &self,
        ws_id: i64,
        plan: EmitAlertPlan,
        recipients: &[u64],
    ) -> Result<(), AppError> {
        let mut tx = self.pool.begin().await?;
        let recipients_json = serde_json::to_value(recipients).context("serialize recipients")?;
        let notification_id: i64 = sqlx::query_scalar(
            r#"
            INSERT INTO ops_alert_notifications(
                ws_id, alert_key, rule_type, severity, alert_status,
                title, message, metrics_json, recipients_json,
                delivery_status, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW(), NOW())
            RETURNING id
            "#,
        )
        .bind(ws_id)
        .bind(&plan.evaluated.alert_key)
        .bind(&plan.evaluated.rule_type)
        .bind(&plan.evaluated.severity)
        .bind(plan.status)
        .bind(&plan.evaluated.title)
        .bind(&plan.evaluated.message)
        .bind(&plan.evaluated.metrics)
        .bind(recipients_json)
        .bind(ALERT_DELIVERY_PENDING)
        .fetch_one(&mut *tx)
        .await?;

        let payload = serde_json::json!({
            "ws_id": ws_id,
            "alert_key": plan.evaluated.alert_key,
            "rule_type": plan.evaluated.rule_type,
            "severity": plan.evaluated.severity,
            "status": plan.status,
            "title": plan.evaluated.title,
            "message": plan.evaluated.message,
            "metrics": plan.evaluated.metrics,
            "user_ids": recipients,
        });
        let notify_result = sqlx::query("SELECT pg_notify('ops_observability_alert', $1)")
            .bind(payload.to_string())
            .execute(&mut *tx)
            .await;
        match notify_result {
            Ok(_) => {
                sqlx::query(
                    r#"
                    UPDATE ops_alert_notifications
                    SET delivery_status = $2,
                        delivered_at = NOW(),
                        updated_at = NOW()
                    WHERE id = $1
                    "#,
                )
                .bind(notification_id)
                .bind(ALERT_DELIVERY_SENT)
                .execute(&mut *tx)
                .await?;
            }
            Err(err) => {
                sqlx::query(
                    r#"
                    UPDATE ops_alert_notifications
                    SET delivery_status = $2,
                        error_message = $3,
                        updated_at = NOW()
                    WHERE id = $1
                    "#,
                )
                .bind(notification_id)
                .bind(ALERT_DELIVERY_FAILED)
                .bind(err.to_string())
                .execute(&mut *tx)
                .await?;
            }
        }

        sqlx::query(
            r#"
            INSERT INTO ops_alert_states(
                ws_id, alert_key, is_active, last_emitted_status, last_changed_at, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, NOW(), NOW(), NOW())
            ON CONFLICT (ws_id, alert_key)
            DO UPDATE SET
                is_active = EXCLUDED.is_active,
                last_emitted_status = EXCLUDED.last_emitted_status,
                last_changed_at = NOW(),
                updated_at = NOW()
            "#,
        )
        .bind(ws_id)
        .bind(&plan.evaluated.alert_key)
        .bind(plan.mark_active)
        .bind(plan.status)
        .execute(&mut *tx)
        .await?;
        tx.commit().await?;
        Ok(())
    }

    async fn process_single_alert_transition(
        &self,
        ws_id: i64,
        evaluated: EvaluatedAlert,
        anomaly_state: &HashMap<String, OpsObservabilityAnomalyStateValue>,
        now_ms: i64,
        recipients: &[u64],
        report: &mut OpsAlertEvalReport,
    ) -> Result<(), AppError> {
        let previous: Option<OpsAlertStateRow> = sqlx::query_as(
            r#"
            SELECT is_active, last_emitted_status
            FROM ops_alert_states
            WHERE ws_id = $1 AND alert_key = $2
            "#,
        )
        .bind(ws_id)
        .bind(&evaluated.alert_key)
        .fetch_optional(&self.pool)
        .await?;
        let suppression_state = anomaly_state.get(&evaluated.alert_key);
        let Some(plan) = build_emit_plan(evaluated, previous, suppression_state, now_ms) else {
            return Ok(());
        };
        match plan.status {
            ALERT_STATUS_RAISED => report.alerts_raised += 1,
            ALERT_STATUS_CLEARED => report.alerts_cleared += 1,
            ALERT_STATUS_SUPPRESSED => report.alerts_suppressed += 1,
            _ => {}
        }
        self.emit_observability_alert(ws_id, plan, recipients).await
    }

    pub async fn evaluate_ops_observability_alerts_once(
        &self,
    ) -> Result<OpsAlertEvalReport, AppError> {
        let now_ms = now_millis();
        let mut report = OpsAlertEvalReport::default();
        let rows = self.list_observability_eval_workspaces().await?;
        report.workspaces_scanned = rows.len() as u64;
        for row in rows {
            let thresholds = parse_thresholds(row.thresholds_json.clone());
            let anomaly_state = parse_anomaly_state(row.anomaly_state_json.clone(), now_ms);
            let signal = self.load_recent_judge_signal(row.ws_id).await?;
            let recipients = self.list_alert_recipients(row.ws_id).await?;
            for spec in rule_specs() {
                let evaluated = evaluate_alert_for_rule(spec, &thresholds, signal);
                self.process_single_alert_transition(
                    row.ws_id,
                    evaluated,
                    &anomaly_state,
                    now_ms,
                    &recipients,
                    &mut report,
                )
                .await?;
            }
        }
        Ok(report)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::UpsertOpsRoleInput;
    use anyhow::Result;

    #[tokio::test]
    async fn get_ops_observability_config_should_return_defaults_when_missing() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.update_workspace_owner(1, 1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let ret = state.get_ops_observability_config(&owner).await?;
        assert_eq!(ret.ws_id, 1);
        assert_eq!(ret.thresholds.low_success_rate_threshold, 80.0);
        assert!(ret.anomaly_state.is_empty());
        assert!(ret.updated_by.is_none());
        assert!(ret.updated_at.is_none());
        Ok(())
    }

    #[tokio::test]
    async fn upsert_ops_observability_config_should_allow_ops_viewer_review_permission(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.update_workspace_owner(1, 1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let viewer = state
            .find_user_by_id(2)
            .await?
            .expect("viewer should exist");
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                viewer.id as u64,
                UpsertOpsRoleInput {
                    role: "ops_viewer".to_string(),
                },
            )
            .await?;

        let threshold_ret = state
            .upsert_ops_observability_thresholds(
                &viewer,
                OpsObservabilityThresholds {
                    low_success_rate_threshold: 75.0,
                    high_retry_threshold: 1.5,
                    high_coalesced_threshold: 2.5,
                    high_db_latency_threshold_ms: 1500,
                    low_cache_hit_rate_threshold: 25.0,
                    min_request_for_cache_hit_check: 30,
                },
            )
            .await?;
        assert_eq!(threshold_ret.updated_by, Some(viewer.id as u64));
        assert_eq!(threshold_ret.thresholds.low_success_rate_threshold, 75.0);

        let state_ret = state
            .upsert_ops_observability_anomaly_state(
                &viewer,
                UpdateOpsObservabilityAnomalyStateInput {
                    anomaly_state: HashMap::from([(
                        "db_errors".to_string(),
                        OpsObservabilityAnomalyStateValue {
                            acknowledged_at_ms: 1000,
                            suppress_until_ms: now_millis() + 60_000,
                        },
                    )]),
                },
            )
            .await?;
        assert_eq!(state_ret.updated_by, Some(viewer.id as u64));
        assert!(state_ret.anomaly_state.contains_key("db_errors"));
        assert_eq!(
            state_ret
                .anomaly_state
                .get("db_errors")
                .map(|item| item.acknowledged_at_ms),
            Some(1000)
        );
        Ok(())
    }

    #[tokio::test]
    async fn upsert_ops_observability_config_should_reject_user_without_ops_role() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.update_workspace_owner(1, 1).await?;
        let user = state.find_user_by_id(3).await?.expect("user should exist");
        let err = state
            .upsert_ops_observability_thresholds(&user, OpsObservabilityThresholds::default())
            .await
            .expect_err("missing ops role should be rejected");
        match err {
            AppError::DebateConflict(msg) => {
                assert!(msg.starts_with("ops_permission_denied:judge_review:"));
            }
            other => panic!("unexpected error: {}", other),
        }
        Ok(())
    }

    #[tokio::test]
    async fn evaluate_ops_observability_alerts_once_should_raise_and_clear_alerts() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.update_workspace_owner(1, 1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");

        state
            .upsert_ops_observability_thresholds(
                &owner,
                OpsObservabilityThresholds {
                    low_success_rate_threshold: 95.0,
                    high_retry_threshold: 1.0,
                    high_coalesced_threshold: 0.0,
                    high_db_latency_threshold_ms: 1,
                    low_cache_hit_rate_threshold: 20.0,
                    min_request_for_cache_hit_check: 1,
                },
            )
            .await?;

        let topic_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO debate_topics(
                ws_id, title, description, category, stance_pro, stance_con, is_active, created_by
            )
            VALUES ($1, 'obs-topic', 'desc', 'game', 'pro', 'con', true, $2)
            RETURNING id
            "#,
        )
        .bind(1_i64)
        .bind(owner.id)
        .fetch_one(&state.pool)
        .await?;
        let session_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO debate_sessions(
                ws_id, topic_id, status, scheduled_start_at, actual_start_at, end_at, max_participants_per_side
            )
            VALUES (
                $1, $2, 'closed',
                NOW() - INTERVAL '30 minutes',
                NOW() - INTERVAL '25 minutes',
                NOW() - INTERVAL '10 minutes',
                500
            )
            RETURNING id
            "#,
        )
        .bind(1_i64)
        .bind(topic_id.0)
        .fetch_one(&state.pool)
        .await?;

        sqlx::query(
            r#"
            INSERT INTO judge_jobs(
                ws_id, session_id, requested_by, status, style_mode,
                requested_at, started_at, finished_at, dispatch_attempts, created_at, updated_at
            )
            VALUES (
                $1, $2, $3, 'failed', 'rational',
                NOW() - INTERVAL '2 minutes',
                NOW() - INTERVAL '2 minutes',
                NOW() - INTERVAL '1 minutes',
                3, NOW(), NOW()
            )
            "#,
        )
        .bind(1_i64)
        .bind(session_id.0)
        .bind(owner.id)
        .execute(&state.pool)
        .await?;

        let report = state.evaluate_ops_observability_alerts_once().await?;
        assert!(report.alerts_raised > 0 || report.alerts_suppressed > 0);

        let raised_count: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)::bigint
            FROM ops_alert_notifications
            WHERE ws_id = 1 AND alert_status = 'raised'
            "#,
        )
        .fetch_one(&state.pool)
        .await?;
        assert!(raised_count >= 1);

        state
            .upsert_ops_observability_thresholds(
                &owner,
                OpsObservabilityThresholds {
                    low_success_rate_threshold: 10.0,
                    high_retry_threshold: 10.0,
                    high_coalesced_threshold: 9999.0,
                    high_db_latency_threshold_ms: 60_000,
                    low_cache_hit_rate_threshold: 20.0,
                    min_request_for_cache_hit_check: 1,
                },
            )
            .await?;
        let report2 = state.evaluate_ops_observability_alerts_once().await?;
        assert!(report2.alerts_cleared >= 1);

        let cleared_count: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)::bigint
            FROM ops_alert_notifications
            WHERE ws_id = 1 AND alert_status = 'cleared'
            "#,
        )
        .fetch_one(&state.pool)
        .await?;
        assert!(cleared_count >= 1);
        Ok(())
    }

    #[test]
    fn normalize_alert_status_filter_should_validate_values() {
        assert!(normalize_alert_status_filter(Some("raised".to_string())).is_ok());
        assert!(normalize_alert_status_filter(Some("cleared".to_string())).is_ok());
        assert!(normalize_alert_status_filter(Some("suppressed".to_string())).is_ok());
        assert!(normalize_alert_status_filter(Some("invalid".to_string())).is_err());
    }

    #[test]
    fn build_emit_plan_should_raise_after_suppression_expires() {
        let evaluated = EvaluatedAlert {
            alert_key: OPS_ALERT_RULE_HIGH_RETRY.to_string(),
            rule_type: OPS_ALERT_RULE_HIGH_RETRY.to_string(),
            severity: ALERT_SEVERITY_WARNING.to_string(),
            title: "x".to_string(),
            message: "x".to_string(),
            metrics: Value::Null,
            is_active: true,
        };
        let previous = Some(OpsAlertStateRow {
            is_active: true,
            last_emitted_status: ALERT_STATUS_SUPPRESSED.to_string(),
        });
        let suppression_state = Some(&OpsObservabilityAnomalyStateValue {
            acknowledged_at_ms: 0,
            suppress_until_ms: 0,
        });
        let plan = build_emit_plan(evaluated, previous, suppression_state, now_millis())
            .expect("should emit plan");
        assert_eq!(plan.status, ALERT_STATUS_RAISED);
        assert!(plan.mark_active);
    }
}
