use crate::{AppError, AppState};
use anyhow::Context;
use chat_core::User;
use chrono::{DateTime, Utc};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sqlx::FromRow;
use std::collections::{HashMap, HashSet};
use tracing::warn;
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
const OPS_ANOMALY_ACTION_ACKNOWLEDGE: &str = "acknowledge";
const OPS_ANOMALY_ACTION_SUPPRESS: &str = "suppress";
const OPS_ANOMALY_ACTION_CLEAR: &str = "clear";
const OPS_ANOMALY_SUPPRESS_MINUTES_DEFAULT: i64 = 30;
const OPS_ANOMALY_SUPPRESS_MINUTES_MAX: i64 = 7 * 24 * 60;
const AI_JUDGE_OUTBOX_ALERT_KEY_PREFIX: &str = "ai_judge_outbox";
const AI_JUDGE_OUTBOX_RULE_TYPE_PREFIX: &str = "ai_judge";
const AI_JUDGE_OUTBOX_DEFAULT_EVENT_TYPE: &str = "ai_judge.audit_alert.status_changed.v1";
const AI_JUDGE_OUTBOX_ERROR_MAX_LEN: usize = 500;

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
pub struct ApplyOpsObservabilityAnomalyActionInput {
    pub alert_key: String,
    pub action: String,
    pub suppress_minutes: Option<i64>,
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

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OpsMetricsDictionaryItem {
    pub key: String,
    pub category: String,
    pub source: String,
    pub unit: String,
    pub aggregation: String,
    pub description: String,
    pub target: Option<String>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetOpsMetricsDictionaryOutput {
    pub version: String,
    pub generated_at_ms: i64,
    pub items: Vec<OpsMetricsDictionaryItem>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OpsSloSignalSnapshot {
    pub success_count: u64,
    pub failed_count: u64,
    pub completed_count: u64,
    pub success_rate_pct: f64,
    pub avg_dispatch_attempts: f64,
    pub p95_latency_ms: f64,
    pub pending_dlq_count: u64,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OpsSloRuleSnapshotItem {
    pub alert_key: String,
    pub rule_type: String,
    pub title: String,
    pub severity: String,
    pub is_active: bool,
    pub status: String,
    pub suppressed: bool,
    pub last_emitted_status: Option<String>,
    pub message: String,
    pub metrics: Value,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetOpsSloSnapshotOutput {
    pub ws_id: u64,
    pub window_minutes: i64,
    pub generated_at_ms: i64,
    pub thresholds: OpsObservabilityThresholds,
    pub signal: OpsSloSignalSnapshot,
    pub rules: Vec<OpsSloRuleSnapshotItem>,
}

#[derive(Debug, Clone, Default, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct OpsAlertEvalReport {
    pub workspaces_scanned: u64,
    pub alerts_raised: u64,
    pub alerts_cleared: u64,
    pub alerts_suppressed: u64,
}

#[derive(Debug, Clone, Default, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct AiJudgeAlertOutboxBridgeReport {
    pub fetched: u64,
    pub delivered: u64,
    pub delivery_failed: u64,
    pub callback_failed: u64,
    pub skipped_duplicate: u64,
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

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
struct AiJudgeOutboxListResponse {
    #[serde(default)]
    items: Vec<AiJudgeOutboxItem>,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
struct AiJudgeOutboxItem {
    event_id: String,
    ws_id: Option<u64>,
    job_id: Option<u64>,
    trace_id: Option<String>,
    alert_id: Option<String>,
    status: Option<String>,
    #[serde(default)]
    payload: Value,
}

#[derive(Debug, Clone, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
struct AiJudgeOutboxPayload {
    #[serde(default)]
    event_type: String,
    ws_id: Option<u64>,
    job_id: Option<u64>,
    trace_id: Option<String>,
    alert_id: Option<String>,
    alert_type: Option<String>,
    severity: Option<String>,
    status: Option<String>,
    title: Option<String>,
    message: Option<String>,
    #[serde(default)]
    details: Value,
}

#[derive(Debug, Clone)]
struct AiJudgeOutboxNormalizedEvent {
    event_id: String,
    ws_id: i64,
    alert_type: String,
    severity: String,
    alert_status: String,
    title: String,
    message: String,
    metrics: Value,
}

#[derive(Debug, Clone)]
enum AiJudgeAlertDeliveryOutcome {
    Sent,
    Failed(String),
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

fn normalize_anomaly_action(raw: &str) -> Option<&'static str> {
    match raw.trim().to_ascii_lowercase().as_str() {
        "ack" | "acknowledge" => Some(OPS_ANOMALY_ACTION_ACKNOWLEDGE),
        "suppress" | "mute" => Some(OPS_ANOMALY_ACTION_SUPPRESS),
        "clear" | "remove" | "unsuppress" => Some(OPS_ANOMALY_ACTION_CLEAR),
        _ => None,
    }
}

fn normalize_anomaly_action_alert_key(raw: &str) -> Option<String> {
    let key = raw.trim();
    if key.is_empty() || key.len() > MAX_STATE_KEY_LEN {
        return None;
    }
    Some(key.to_string())
}

fn normalize_anomaly_suppress_minutes(raw: Option<i64>) -> i64 {
    raw.unwrap_or(OPS_ANOMALY_SUPPRESS_MINUTES_DEFAULT)
        .clamp(1, OPS_ANOMALY_SUPPRESS_MINUTES_MAX)
}

fn apply_anomaly_action(
    current_state: HashMap<String, OpsObservabilityAnomalyStateValue>,
    input: &ApplyOpsObservabilityAnomalyActionInput,
    now_ms: i64,
) -> Result<HashMap<String, OpsObservabilityAnomalyStateValue>, AppError> {
    let mut anomaly_state = current_state;
    let alert_key = normalize_anomaly_action_alert_key(&input.alert_key)
        .ok_or_else(|| AppError::DebateError("invalid alert key for anomaly action".to_string()))?;
    let action = normalize_anomaly_action(&input.action).ok_or_else(|| {
        AppError::DebateError(
            "invalid anomaly action, expect acknowledge/suppress/clear".to_string(),
        )
    })?;

    match action {
        OPS_ANOMALY_ACTION_ACKNOWLEDGE => {
            let mut item =
                anomaly_state
                    .remove(&alert_key)
                    .unwrap_or(OpsObservabilityAnomalyStateValue {
                        acknowledged_at_ms: 0,
                        suppress_until_ms: 0,
                    });
            item.acknowledged_at_ms = now_ms;
            anomaly_state.insert(alert_key, item);
        }
        OPS_ANOMALY_ACTION_SUPPRESS => {
            let mut item =
                anomaly_state
                    .remove(&alert_key)
                    .unwrap_or(OpsObservabilityAnomalyStateValue {
                        acknowledged_at_ms: 0,
                        suppress_until_ms: 0,
                    });
            let minutes = normalize_anomaly_suppress_minutes(input.suppress_minutes);
            item.acknowledged_at_ms = now_ms.max(item.acknowledged_at_ms);
            item.suppress_until_ms = now_ms.saturating_add(minutes.saturating_mul(60_000));
            anomaly_state.insert(alert_key, item);
        }
        OPS_ANOMALY_ACTION_CLEAR => {
            anomaly_state.remove(&alert_key);
        }
        _ => unreachable!("normalize_anomaly_action guarantees known variants"),
    }

    Ok(normalize_anomaly_state(anomaly_state, now_ms))
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

fn build_ops_metrics_dictionary_items() -> Vec<OpsMetricsDictionaryItem> {
    vec![
        OpsMetricsDictionaryItem {
            key: "api.request_total".to_string(),
            category: "request".to_string(),
            source: "chat_server".to_string(),
            unit: "count".to_string(),
            aggregation: "sum".to_string(),
            description: "API request total across protected endpoints.".to_string(),
            target: None,
        },
        OpsMetricsDictionaryItem {
            key: "api.error_total".to_string(),
            category: "request".to_string(),
            source: "chat_server".to_string(),
            unit: "count".to_string(),
            aggregation: "sum".to_string(),
            description: "API error response total (4xx + 5xx).".to_string(),
            target: None,
        },
        OpsMetricsDictionaryItem {
            key: "api.latency_p95_ms".to_string(),
            category: "request".to_string(),
            source: "chat_server".to_string(),
            unit: "ms".to_string(),
            aggregation: "p95".to_string(),
            description: "API request latency p95.".to_string(),
            target: Some("<300".to_string()),
        },
        OpsMetricsDictionaryItem {
            key: "judge.dispatch.tick_success_total".to_string(),
            category: "judge_dispatch".to_string(),
            source: "chat_server.internal_ai.judge.dispatch.metrics".to_string(),
            unit: "count".to_string(),
            aggregation: "sum".to_string(),
            description: "Judge dispatch worker successful tick count.".to_string(),
            target: None,
        },
        OpsMetricsDictionaryItem {
            key: "judge.dispatch.failed_total".to_string(),
            category: "judge_dispatch".to_string(),
            source: "chat_server.internal_ai.judge.dispatch.metrics".to_string(),
            unit: "count".to_string(),
            aggregation: "sum".to_string(),
            description: "Judge dispatch failed delivery total.".to_string(),
            target: None,
        },
        OpsMetricsDictionaryItem {
            key: "judge.dispatch.retryable_failed_total".to_string(),
            category: "judge_dispatch".to_string(),
            source: "chat_server.internal_ai.judge.dispatch.metrics".to_string(),
            unit: "count".to_string(),
            aggregation: "sum".to_string(),
            description: "Judge dispatch retryable failure total.".to_string(),
            target: None,
        },
        OpsMetricsDictionaryItem {
            key: "judge.dispatch.callback_latency_p95_ms".to_string(),
            category: "judge_dispatch".to_string(),
            source: "ai_judge_service.trace_store".to_string(),
            unit: "ms".to_string(),
            aggregation: "p95".to_string(),
            description: "Dispatch accepted to callback completed latency p95.".to_string(),
            target: Some("<300000".to_string()),
        },
        OpsMetricsDictionaryItem {
            key: "ws.replay.request_total".to_string(),
            category: "ws_replay".to_string(),
            source: "notify_server.ws".to_string(),
            unit: "count".to_string(),
            aggregation: "sum".to_string(),
            description: "WebSocket replay request total.".to_string(),
            target: None,
        },
        OpsMetricsDictionaryItem {
            key: "ws.replay.backlog_size".to_string(),
            category: "ws_replay".to_string(),
            source: "notify_server.ws".to_string(),
            unit: "count".to_string(),
            aggregation: "gauge".to_string(),
            description: "Replay backlog queue size.".to_string(),
            target: None,
        },
        OpsMetricsDictionaryItem {
            key: "ws.broadcast_latency_p95_ms".to_string(),
            category: "ws_replay".to_string(),
            source: "notify_server.ws".to_string(),
            unit: "ms".to_string(),
            aggregation: "p95".to_string(),
            description: "WebSocket broadcast latency p95.".to_string(),
            target: Some("<1000".to_string()),
        },
        OpsMetricsDictionaryItem {
            key: "iap.verify.request_total".to_string(),
            category: "iap_verify".to_string(),
            source: "chat_server.pay.iap.verify".to_string(),
            unit: "count".to_string(),
            aggregation: "sum".to_string(),
            description: "IAP verify request total.".to_string(),
            target: None,
        },
        OpsMetricsDictionaryItem {
            key: "iap.verify.error_total".to_string(),
            category: "iap_verify".to_string(),
            source: "chat_server.pay.iap.verify".to_string(),
            unit: "count".to_string(),
            aggregation: "sum".to_string(),
            description: "IAP verify failed request total.".to_string(),
            target: None,
        },
        OpsMetricsDictionaryItem {
            key: "iap.verify.latency_p95_ms".to_string(),
            category: "iap_verify".to_string(),
            source: "chat_server.pay.iap.verify".to_string(),
            unit: "ms".to_string(),
            aggregation: "p95".to_string(),
            description: "IAP verify latency p95.".to_string(),
            target: Some("<2000".to_string()),
        },
    ]
}

fn build_ops_slo_signal_snapshot(signal: OpsRecentJudgeSignal) -> OpsSloSignalSnapshot {
    let success_count = signal.success_count.max(0) as u64;
    let failed_count = signal.failed_count.max(0) as u64;
    let completed_count = success_count.saturating_add(failed_count);
    let success_rate_pct = if completed_count == 0 {
        100.0
    } else {
        (success_count as f64 * 100.0) / completed_count as f64
    };
    OpsSloSignalSnapshot {
        success_count,
        failed_count,
        completed_count,
        success_rate_pct,
        avg_dispatch_attempts: signal.avg_dispatch_attempts.max(0.0),
        p95_latency_ms: signal.p95_latency_ms.max(0.0),
        pending_dlq_count: signal.pending_dlq_count.max(0) as u64,
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

fn build_http_url(base: &str, path: &str) -> String {
    let base = base.trim_end_matches('/');
    let path = path.trim_start_matches('/');
    format!("{base}/{path}")
}

fn sanitize_bridge_error_message(message: &str) -> String {
    let trimmed = message.trim();
    if trimmed.is_empty() {
        return "bridge delivery failed".to_string();
    }
    if trimmed.len() <= AI_JUDGE_OUTBOX_ERROR_MAX_LEN {
        return trimmed.to_string();
    }
    trimmed
        .chars()
        .take(AI_JUDGE_OUTBOX_ERROR_MAX_LEN)
        .collect()
}

fn map_ai_alert_status(status: &str) -> Option<&'static str> {
    match status.trim().to_ascii_lowercase().as_str() {
        ALERT_STATUS_RAISED => Some(ALERT_STATUS_RAISED),
        "acked" | "acknowledged" | ALERT_STATUS_SUPPRESSED => Some(ALERT_STATUS_SUPPRESSED),
        "resolved" | ALERT_STATUS_CLEARED => Some(ALERT_STATUS_CLEARED),
        _ => None,
    }
}

fn normalize_severity(raw: Option<&str>) -> String {
    let normalized = raw.unwrap_or_default().trim().to_ascii_lowercase();
    if normalized.is_empty() {
        ALERT_SEVERITY_WARNING.to_string()
    } else {
        normalized
    }
}

fn normalize_text(raw: Option<&str>, fallback: &str) -> String {
    let value = raw.unwrap_or_default().trim();
    if value.is_empty() {
        fallback.to_string()
    } else {
        value.to_string()
    }
}

fn build_ai_judge_outbox_alert_key(event_id: &str) -> String {
    format!("{AI_JUDGE_OUTBOX_ALERT_KEY_PREFIX}:{event_id}")
}

fn normalize_ai_judge_outbox_event(
    item: AiJudgeOutboxItem,
) -> Result<AiJudgeOutboxNormalizedEvent, String> {
    let event_id = item.event_id.trim().to_string();
    if event_id.is_empty() {
        return Err("empty outbox event_id".to_string());
    }

    let payload: AiJudgeOutboxPayload =
        serde_json::from_value(item.payload.clone()).unwrap_or_default();
    let ws_id_raw = item.ws_id.or(payload.ws_id);
    let ws_id_u64 = ws_id_raw.ok_or_else(|| "missing wsId".to_string())?;
    let ws_id = i64::try_from(ws_id_u64).map_err(|_| "wsId overflow".to_string())?;
    let status_raw = item
        .status
        .as_deref()
        .or(payload.status.as_deref())
        .unwrap_or_default();
    let mapped_status = map_ai_alert_status(status_raw)
        .ok_or_else(|| format!("unsupported outbox status: {status_raw}"))?
        .to_string();

    let alert_type = normalize_text(payload.alert_type.as_deref(), "runtime_alert");
    let alert_id = normalize_text(
        payload.alert_id.as_deref().or(item.alert_id.as_deref()),
        &event_id,
    );
    let severity = normalize_severity(payload.severity.as_deref());
    let title = normalize_text(payload.title.as_deref(), "AI 裁判运行告警");
    let message = normalize_text(
        payload.message.as_deref(),
        "AI 裁判链路出现告警，请在运维面板查看详情",
    );
    let event_type = normalize_text(
        if payload.event_type.trim().is_empty() {
            None
        } else {
            Some(payload.event_type.as_str())
        },
        AI_JUDGE_OUTBOX_DEFAULT_EVENT_TYPE,
    );
    let trace_id = item.trace_id.or(payload.trace_id);
    let job_id = item
        .job_id
        .or(payload.job_id)
        .and_then(|v| i64::try_from(v).ok());
    let metrics = serde_json::json!({
        "eventId": event_id,
        "eventType": event_type,
        "alertId": alert_id,
        "alertType": alert_type,
        "traceId": trace_id,
        "jobId": job_id,
        "statusRaw": status_raw,
        "details": payload.details,
    });

    Ok(AiJudgeOutboxNormalizedEvent {
        event_id,
        ws_id,
        alert_type,
        severity,
        alert_status: mapped_status,
        title,
        message,
        metrics,
    })
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
    pub async fn get_ops_metrics_dictionary(
        &self,
        user: &User,
    ) -> Result<GetOpsMetricsDictionaryOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::JudgeReview)
            .await?;
        Ok(GetOpsMetricsDictionaryOutput {
            version: "v1".to_string(),
            generated_at_ms: now_millis(),
            items: build_ops_metrics_dictionary_items(),
        })
    }

    pub async fn get_ops_observability_slo_snapshot(
        &self,
        user: &User,
    ) -> Result<GetOpsSloSnapshotOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::JudgeReview)
            .await?;
        let now_ms = now_millis();
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

        let (thresholds, anomaly_state) = if let Some(row) = row {
            (
                parse_thresholds(row.thresholds_json),
                parse_anomaly_state(row.anomaly_state_json, now_ms),
            )
        } else {
            (OpsObservabilityThresholds::default(), HashMap::new())
        };
        let signal = self.load_recent_judge_signal(user.ws_id).await?;
        let signal_snapshot = build_ops_slo_signal_snapshot(signal);
        let mut rules = Vec::with_capacity(rule_specs().len());
        for spec in rule_specs() {
            let evaluated = evaluate_alert_for_rule(spec, &thresholds, signal);
            let previous: Option<OpsAlertStateRow> = sqlx::query_as(
                r#"
                SELECT is_active, last_emitted_status
                FROM ops_alert_states
                WHERE ws_id = $1 AND alert_key = $2
                "#,
            )
            .bind(user.ws_id)
            .bind(spec.alert_key)
            .fetch_optional(&self.pool)
            .await?;
            let suppressed = anomaly_state
                .get(spec.alert_key)
                .map(|v| v.suppress_until_ms > now_ms)
                .unwrap_or(false);
            let status = if evaluated.is_active {
                if suppressed {
                    ALERT_STATUS_SUPPRESSED
                } else {
                    ALERT_STATUS_RAISED
                }
            } else {
                ALERT_STATUS_CLEARED
            };
            rules.push(OpsSloRuleSnapshotItem {
                alert_key: evaluated.alert_key,
                rule_type: evaluated.rule_type,
                title: evaluated.title,
                severity: evaluated.severity,
                is_active: evaluated.is_active,
                status: status.to_string(),
                suppressed,
                last_emitted_status: previous.map(|v| v.last_emitted_status),
                message: evaluated.message,
                metrics: evaluated.metrics,
            });
        }

        Ok(GetOpsSloSnapshotOutput {
            ws_id: user.ws_id as u64,
            window_minutes: OPS_ALERT_EVAL_WINDOW_MINUTES,
            generated_at_ms: now_ms,
            thresholds,
            signal: signal_snapshot,
            rules,
        })
    }

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

    pub async fn apply_ops_observability_anomaly_action(
        &self,
        user: &User,
        input: ApplyOpsObservabilityAnomalyActionInput,
    ) -> Result<GetOpsObservabilityConfigOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::JudgeReview)
            .await?;
        let now_ms = now_millis();
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
        let existing = row
            .map(|v| parse_anomaly_state(v.anomaly_state_json, now_ms))
            .unwrap_or_default();
        let anomaly_state = apply_anomaly_action(existing, &input, now_ms)?;
        let anomaly_state_json = serde_json::to_value(&anomaly_state)
            .context("serialize observability anomaly action state failed")?;
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

    async fn fetch_ai_judge_alert_outbox(
        &self,
        delivery_status: &str,
        limit: u64,
    ) -> Result<Vec<AiJudgeOutboxItem>, AppError> {
        let url = build_http_url(
            &self.config.ai_judge.service_base_url,
            &self.config.ai_judge.alert_outbox_path,
        );
        let client = Client::builder()
            .timeout(std::time::Duration::from_millis(
                self.config.ai_judge.alert_outbox_timeout_ms.max(1),
            ))
            .build()
            .context("build ai judge outbox bridge client failed")?;
        let resp = client
            .get(url)
            .header("x-ai-internal-key", &self.config.ai_judge.internal_key)
            .query(&[
                ("delivery_status", delivery_status.to_string()),
                ("limit", limit.clamp(1, 200).to_string()),
            ])
            .send()
            .await
            .context("fetch ai judge alert outbox failed")?;
        if !resp.status().is_success() {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            return Err(AppError::DebateError(format!(
                "fetch ai judge alert outbox failed: status={status}, body={body}"
            )));
        }
        let parsed = resp
            .json::<AiJudgeOutboxListResponse>()
            .await
            .context("parse ai judge outbox response failed")?;
        Ok(parsed.items)
    }

    async fn mark_ai_judge_alert_outbox_delivery(
        &self,
        event_id: &str,
        delivery_status: &str,
        error_message: Option<&str>,
    ) -> Result<(), AppError> {
        let path = self
            .config
            .ai_judge
            .alert_outbox_delivery_path
            .replace("{event_id}", event_id);
        let url = build_http_url(&self.config.ai_judge.service_base_url, &path);
        let client = Client::builder()
            .timeout(std::time::Duration::from_millis(
                self.config.ai_judge.alert_outbox_timeout_ms.max(1),
            ))
            .build()
            .context("build ai judge outbox callback client failed")?;
        let mut req = client
            .post(url)
            .header("x-ai-internal-key", &self.config.ai_judge.internal_key)
            .query(&[("delivery_status", delivery_status.to_string())]);
        if let Some(error_message) = error_message {
            req = req.query(&[(
                "error_message",
                sanitize_bridge_error_message(error_message),
            )]);
        }
        let resp = req
            .send()
            .await
            .context("callback ai judge outbox delivery failed")?;
        if resp.status().is_success() {
            return Ok(());
        }
        let status = resp.status();
        let body = resp.text().await.unwrap_or_default();
        Err(AppError::DebateError(format!(
            "callback ai judge outbox delivery failed: status={status}, body={body}"
        )))
    }

    async fn find_existing_bridge_notification_delivery_status(
        &self,
        ws_id: i64,
        alert_key: &str,
    ) -> Result<Option<String>, AppError> {
        let row: Option<String> = sqlx::query_scalar(
            r#"
            SELECT delivery_status
            FROM ops_alert_notifications
            WHERE ws_id = $1
              AND alert_key = $2
            ORDER BY id DESC
            LIMIT 1
            "#,
        )
        .bind(ws_id)
        .bind(alert_key)
        .fetch_optional(&self.pool)
        .await?;
        Ok(row)
    }

    async fn emit_ai_judge_bridge_notification(
        &self,
        event: &AiJudgeOutboxNormalizedEvent,
        alert_key: &str,
        recipients: &[u64],
    ) -> Result<AiJudgeAlertDeliveryOutcome, AppError> {
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
        .bind(event.ws_id)
        .bind(alert_key)
        .bind(format!(
            "{AI_JUDGE_OUTBOX_RULE_TYPE_PREFIX}:{}",
            event.alert_type
        ))
        .bind(&event.severity)
        .bind(&event.alert_status)
        .bind(&event.title)
        .bind(&event.message)
        .bind(&event.metrics)
        .bind(recipients_json)
        .bind(ALERT_DELIVERY_PENDING)
        .fetch_one(&mut *tx)
        .await?;

        let payload = serde_json::json!({
            "ws_id": event.ws_id,
            "alert_key": alert_key,
            "rule_type": format!("{AI_JUDGE_OUTBOX_RULE_TYPE_PREFIX}:{}", event.alert_type),
            "severity": event.severity,
            "status": event.alert_status,
            "title": event.title,
            "message": event.message,
            "metrics": event.metrics,
            "user_ids": recipients,
        });
        let notify_result = sqlx::query("SELECT pg_notify('ops_observability_alert', $1)")
            .bind(payload.to_string())
            .execute(&mut *tx)
            .await;
        let outcome = match notify_result {
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
                AiJudgeAlertDeliveryOutcome::Sent
            }
            Err(err) => {
                let reason = sanitize_bridge_error_message(&err.to_string());
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
                .bind(&reason)
                .execute(&mut *tx)
                .await?;
                AiJudgeAlertDeliveryOutcome::Failed(reason)
            }
        };
        tx.commit().await?;
        Ok(outcome)
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

    pub(crate) async fn bridge_ai_judge_alert_outbox_once(
        &self,
    ) -> Result<AiJudgeAlertOutboxBridgeReport, AppError> {
        let mut report = AiJudgeAlertOutboxBridgeReport::default();
        let items = self
            .fetch_ai_judge_alert_outbox(
                ALERT_DELIVERY_PENDING,
                self.config.ai_judge.alert_outbox_batch_size.clamp(1, 200),
            )
            .await?;
        report.fetched = items.len() as u64;

        for item in items {
            let event_id = item.event_id.trim().to_string();
            if event_id.is_empty() {
                report.delivery_failed += 1;
                continue;
            }
            let normalized = match normalize_ai_judge_outbox_event(item) {
                Ok(v) => v,
                Err(err) => {
                    report.delivery_failed += 1;
                    if let Err(callback_err) = self
                        .mark_ai_judge_alert_outbox_delivery(
                            &event_id,
                            ALERT_DELIVERY_FAILED,
                            Some(&err),
                        )
                        .await
                    {
                        report.callback_failed += 1;
                        warn!(
                            event_id = event_id,
                            "callback failed when normalizing outbox event: {}", callback_err
                        );
                    }
                    continue;
                }
            };
            let alert_key = build_ai_judge_outbox_alert_key(&normalized.event_id);
            if let Some(existing_delivery_status) = self
                .find_existing_bridge_notification_delivery_status(normalized.ws_id, &alert_key)
                .await?
            {
                report.skipped_duplicate += 1;
                if existing_delivery_status == ALERT_DELIVERY_SENT {
                    report.delivered += 1;
                    if let Err(err) = self
                        .mark_ai_judge_alert_outbox_delivery(
                            &normalized.event_id,
                            ALERT_DELIVERY_SENT,
                            None,
                        )
                        .await
                    {
                        report.callback_failed += 1;
                        warn!(
                            event_id = normalized.event_id,
                            "callback failed for duplicate sent event: {}", err
                        );
                    }
                } else {
                    report.delivery_failed += 1;
                    let err = format!(
                        "duplicate event with non-sent delivery status: {existing_delivery_status}"
                    );
                    if let Err(callback_err) = self
                        .mark_ai_judge_alert_outbox_delivery(
                            &normalized.event_id,
                            ALERT_DELIVERY_FAILED,
                            Some(&err),
                        )
                        .await
                    {
                        report.callback_failed += 1;
                        warn!(
                            event_id = normalized.event_id,
                            "callback failed for duplicate failed event: {}", callback_err
                        );
                    }
                }
                continue;
            }

            let recipients = self.list_alert_recipients(normalized.ws_id).await?;
            match self
                .emit_ai_judge_bridge_notification(&normalized, &alert_key, &recipients)
                .await?
            {
                AiJudgeAlertDeliveryOutcome::Sent => {
                    report.delivered += 1;
                    if let Err(err) = self
                        .mark_ai_judge_alert_outbox_delivery(
                            &normalized.event_id,
                            ALERT_DELIVERY_SENT,
                            None,
                        )
                        .await
                    {
                        report.callback_failed += 1;
                        warn!(
                            event_id = normalized.event_id,
                            "callback failed for delivered outbox event: {}", err
                        );
                    }
                }
                AiJudgeAlertDeliveryOutcome::Failed(reason) => {
                    report.delivery_failed += 1;
                    if let Err(err) = self
                        .mark_ai_judge_alert_outbox_delivery(
                            &normalized.event_id,
                            ALERT_DELIVERY_FAILED,
                            Some(&reason),
                        )
                        .await
                    {
                        report.callback_failed += 1;
                        warn!(
                            event_id = normalized.event_id,
                            "callback failed for failed outbox event: {}", err
                        );
                    }
                }
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
    use axum::{
        extract::{Path, Query},
        http::StatusCode as AxumStatusCode,
        routing::{get, post},
        Json, Router,
    };
    use serde::Deserialize;
    use std::sync::{Arc, Mutex};
    use tokio::net::TcpListener;

    #[derive(Debug, Clone, Deserialize)]
    struct MockOutboxListQuery {
        #[serde(alias = "deliveryStatus")]
        delivery_status: Option<String>,
        limit: Option<usize>,
    }

    #[derive(Debug, Clone, Deserialize)]
    struct MockOutboxDeliveryQuery {
        #[serde(alias = "deliveryStatus")]
        delivery_status: Option<String>,
        #[serde(alias = "errorMessage")]
        error_message: Option<String>,
    }

    #[derive(Debug, Clone)]
    struct MockOutboxDeliveryCall {
        event_id: String,
        delivery_status: String,
        error_message: Option<String>,
    }

    async fn spawn_mock_judge_outbox_server(
        items: Vec<Value>,
        callback_status: AxumStatusCode,
    ) -> Result<(String, Arc<Mutex<Vec<MockOutboxDeliveryCall>>>)> {
        let callbacks = Arc::new(Mutex::new(Vec::<MockOutboxDeliveryCall>::new()));
        let outbox_items = Arc::new(items);
        let app = {
            let callbacks = callbacks.clone();
            let outbox_items = outbox_items.clone();
            Router::new()
                .route(
                    "/internal/judge/alerts/outbox",
                    get(move |Query(query): Query<MockOutboxListQuery>| {
                        let outbox_items = outbox_items.clone();
                        async move {
                            let mut rows = if query.delivery_status.as_deref() == Some("pending") {
                                (*outbox_items).clone()
                            } else {
                                vec![]
                            };
                            let limit = query.limit.unwrap_or(50).clamp(1, 200);
                            rows.truncate(limit);
                            Json(serde_json::json!({
                                "count": rows.len(),
                                "items": rows,
                                "filters": {
                                    "deliveryStatus": query.delivery_status,
                                    "limit": limit
                                }
                            }))
                        }
                    }),
                )
                .route(
                    "/internal/judge/alerts/outbox/:event_id/delivery",
                    post(
                        move |Path(event_id): Path<String>,
                              Query(query): Query<MockOutboxDeliveryQuery>| {
                            let callbacks = callbacks.clone();
                            async move {
                                callbacks
                                    .lock()
                                    .expect("mock callback lock poisoned")
                                    .push(MockOutboxDeliveryCall {
                                        event_id: event_id.clone(),
                                        delivery_status: query
                                            .delivery_status
                                            .unwrap_or_else(|| "sent".to_string()),
                                        error_message: query.error_message,
                                    });
                                (
                                    callback_status,
                                    Json(serde_json::json!({
                                        "ok": callback_status.is_success()
                                    })),
                                )
                            }
                        },
                    ),
                )
        };
        let listener = TcpListener::bind("127.0.0.1:0").await?;
        let addr = listener.local_addr()?;
        tokio::spawn(async move {
            let _ = axum::serve(listener, app).await;
        });
        Ok((format!("http://{}", addr), callbacks))
    }

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

    #[tokio::test]
    async fn bridge_ai_judge_alert_outbox_once_should_deliver_and_callback_sent() -> Result<()> {
        let (_tdb, mut state) = AppState::new_for_test().await?;
        state.update_workspace_owner(1, 1).await?;
        let (service_base_url, callbacks) = spawn_mock_judge_outbox_server(
            vec![serde_json::json!({
                "eventId": "evt-bridge-ok",
                "wsId": 1,
                "jobId": 2001,
                "traceId": "trace-bridge-ok",
                "alertId": "alert-bridge-ok",
                "status": "raised",
                "payload": {
                    "eventType": "ai_judge.audit_alert.status_changed.v1",
                    "alertType": "judge_timeout",
                    "severity": "warning",
                    "status": "raised",
                    "title": "判决超时",
                    "message": "某任务触发超时",
                    "details": { "timeoutSec": 300 }
                }
            })],
            AxumStatusCode::OK,
        )
        .await?;
        let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
        inner.config.ai_judge.service_base_url = service_base_url;
        inner.config.ai_judge.alert_outbox_batch_size = 20;
        inner.config.ai_judge.alert_outbox_timeout_ms = 2_000;

        let report = state.bridge_ai_judge_alert_outbox_once().await?;
        assert_eq!(report.fetched, 1);
        assert_eq!(report.delivered, 1);
        assert_eq!(report.delivery_failed, 0);
        assert_eq!(report.callback_failed, 0);
        assert_eq!(report.skipped_duplicate, 0);

        let row: (String, String, String, String) = sqlx::query_as(
            r#"
            SELECT alert_key, rule_type, alert_status, delivery_status
            FROM ops_alert_notifications
            WHERE ws_id = 1
              AND alert_key = $1
            ORDER BY id DESC
            LIMIT 1
            "#,
        )
        .bind(build_ai_judge_outbox_alert_key("evt-bridge-ok"))
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(row.0, "ai_judge_outbox:evt-bridge-ok");
        assert_eq!(row.1, "ai_judge:judge_timeout");
        assert_eq!(row.2, "raised");
        assert_eq!(row.3, "sent");

        let calls = callbacks.lock().expect("mock callback lock poisoned");
        assert_eq!(calls.len(), 1);
        assert_eq!(calls[0].event_id, "evt-bridge-ok");
        assert_eq!(calls[0].delivery_status, "sent");
        assert!(calls[0].error_message.is_none());
        Ok(())
    }

    #[tokio::test]
    async fn bridge_ai_judge_alert_outbox_once_should_dedupe_and_only_callback_for_duplicate_sent(
    ) -> Result<()> {
        let (_tdb, mut state) = AppState::new_for_test().await?;
        state.update_workspace_owner(1, 1).await?;
        sqlx::query(
            r#"
            INSERT INTO ops_alert_notifications(
                ws_id, alert_key, rule_type, severity, alert_status,
                title, message, metrics_json, recipients_json,
                delivery_status, created_at, updated_at
            )
            VALUES (
                1, $1, 'ai_judge:judge_timeout', 'warning', 'raised',
                'dup-title', 'dup-message', '{}'::jsonb, '[1]'::jsonb,
                'sent', NOW(), NOW()
            )
            "#,
        )
        .bind(build_ai_judge_outbox_alert_key("evt-bridge-dup"))
        .execute(&state.pool)
        .await?;
        let (service_base_url, callbacks) = spawn_mock_judge_outbox_server(
            vec![serde_json::json!({
                "eventId": "evt-bridge-dup",
                "wsId": 1,
                "status": "raised",
                "payload": {
                    "alertType": "judge_timeout",
                    "severity": "warning",
                    "title": "dup-title",
                    "message": "dup-message"
                }
            })],
            AxumStatusCode::OK,
        )
        .await?;
        let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
        inner.config.ai_judge.service_base_url = service_base_url;
        inner.config.ai_judge.alert_outbox_batch_size = 20;
        inner.config.ai_judge.alert_outbox_timeout_ms = 2_000;

        let report = state.bridge_ai_judge_alert_outbox_once().await?;
        assert_eq!(report.fetched, 1);
        assert_eq!(report.delivered, 1);
        assert_eq!(report.delivery_failed, 0);
        assert_eq!(report.callback_failed, 0);
        assert_eq!(report.skipped_duplicate, 1);

        let count: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)::bigint
            FROM ops_alert_notifications
            WHERE ws_id = 1
              AND alert_key = $1
            "#,
        )
        .bind(build_ai_judge_outbox_alert_key("evt-bridge-dup"))
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(count, 1);

        let calls = callbacks.lock().expect("mock callback lock poisoned");
        assert_eq!(calls.len(), 1);
        assert_eq!(calls[0].event_id, "evt-bridge-dup");
        assert_eq!(calls[0].delivery_status, "sent");
        assert!(calls[0].error_message.is_none());
        Ok(())
    }

    #[tokio::test]
    async fn bridge_ai_judge_alert_outbox_once_should_count_callback_failed_when_mark_failed_errors(
    ) -> Result<()> {
        let (_tdb, mut state) = AppState::new_for_test().await?;
        state.update_workspace_owner(1, 1).await?;
        let (service_base_url, callbacks) = spawn_mock_judge_outbox_server(
            vec![serde_json::json!({
                "eventId": "evt-bridge-bad",
                "status": "raised",
                "payload": {
                    "alertType": "judge_timeout",
                    "severity": "warning",
                    "title": "bad",
                    "message": "missing wsId"
                }
            })],
            AxumStatusCode::INTERNAL_SERVER_ERROR,
        )
        .await?;
        let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
        inner.config.ai_judge.service_base_url = service_base_url;
        inner.config.ai_judge.alert_outbox_batch_size = 20;
        inner.config.ai_judge.alert_outbox_timeout_ms = 2_000;

        let report = state.bridge_ai_judge_alert_outbox_once().await?;
        assert_eq!(report.fetched, 1);
        assert_eq!(report.delivered, 0);
        assert_eq!(report.delivery_failed, 1);
        assert_eq!(report.callback_failed, 1);

        let count: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)::bigint
            FROM ops_alert_notifications
            WHERE ws_id = 1
              AND alert_key = $1
            "#,
        )
        .bind(build_ai_judge_outbox_alert_key("evt-bridge-bad"))
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(count, 0);

        let calls = callbacks.lock().expect("mock callback lock poisoned");
        assert_eq!(calls.len(), 1);
        assert_eq!(calls[0].event_id, "evt-bridge-bad");
        assert_eq!(calls[0].delivery_status, "failed");
        assert!(calls[0]
            .error_message
            .as_deref()
            .unwrap_or_default()
            .contains("missing wsId"));
        Ok(())
    }

    #[test]
    fn normalize_alert_status_filter_should_validate_values() {
        assert!(normalize_alert_status_filter(Some("raised".to_string())).is_ok());
        assert!(normalize_alert_status_filter(Some("cleared".to_string())).is_ok());
        assert!(normalize_alert_status_filter(Some("suppressed".to_string())).is_ok());
        assert!(normalize_alert_status_filter(Some("invalid".to_string())).is_err());
    }

    #[tokio::test]
    async fn apply_ops_observability_anomaly_action_should_support_suppress_ack_and_clear(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.update_workspace_owner(1, 1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let now_ms = now_millis();

        let suppress_ret = state
            .apply_ops_observability_anomaly_action(
                &owner,
                ApplyOpsObservabilityAnomalyActionInput {
                    alert_key: OPS_ALERT_RULE_HIGH_RETRY.to_string(),
                    action: OPS_ANOMALY_ACTION_SUPPRESS.to_string(),
                    suppress_minutes: Some(5),
                },
            )
            .await?;
        let suppress_item = suppress_ret
            .anomaly_state
            .get(OPS_ALERT_RULE_HIGH_RETRY)
            .expect("suppress action should create state");
        assert!(suppress_item.acknowledged_at_ms >= now_ms);
        assert!(suppress_item.suppress_until_ms > now_ms);

        let ack_ret = state
            .apply_ops_observability_anomaly_action(
                &owner,
                ApplyOpsObservabilityAnomalyActionInput {
                    alert_key: OPS_ALERT_RULE_HIGH_RETRY.to_string(),
                    action: OPS_ANOMALY_ACTION_ACKNOWLEDGE.to_string(),
                    suppress_minutes: None,
                },
            )
            .await?;
        let ack_item = ack_ret
            .anomaly_state
            .get(OPS_ALERT_RULE_HIGH_RETRY)
            .expect("ack action should keep state");
        assert!(ack_item.acknowledged_at_ms >= now_ms);
        assert!(ack_item.suppress_until_ms > now_ms);

        let clear_ret = state
            .apply_ops_observability_anomaly_action(
                &owner,
                ApplyOpsObservabilityAnomalyActionInput {
                    alert_key: OPS_ALERT_RULE_HIGH_RETRY.to_string(),
                    action: OPS_ANOMALY_ACTION_CLEAR.to_string(),
                    suppress_minutes: None,
                },
            )
            .await?;
        assert!(!clear_ret
            .anomaly_state
            .contains_key(OPS_ALERT_RULE_HIGH_RETRY));
        Ok(())
    }

    #[tokio::test]
    async fn apply_ops_observability_anomaly_action_should_reject_invalid_action() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.update_workspace_owner(1, 1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let err = state
            .apply_ops_observability_anomaly_action(
                &owner,
                ApplyOpsObservabilityAnomalyActionInput {
                    alert_key: OPS_ALERT_RULE_HIGH_RETRY.to_string(),
                    action: "invalid".to_string(),
                    suppress_minutes: None,
                },
            )
            .await
            .expect_err("invalid action should be rejected");
        match err {
            AppError::DebateError(msg) => {
                assert!(msg.contains("invalid anomaly action"));
            }
            other => panic!("unexpected error: {other}"),
        }
        Ok(())
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

    #[test]
    fn map_ai_alert_status_should_support_runtime_aliases() {
        assert_eq!(map_ai_alert_status("raised"), Some(ALERT_STATUS_RAISED));
        assert_eq!(map_ai_alert_status("acked"), Some(ALERT_STATUS_SUPPRESSED));
        assert_eq!(
            map_ai_alert_status("acknowledged"),
            Some(ALERT_STATUS_SUPPRESSED)
        );
        assert_eq!(map_ai_alert_status("resolved"), Some(ALERT_STATUS_CLEARED));
        assert_eq!(map_ai_alert_status("invalid"), None);
    }

    #[test]
    fn normalize_ai_judge_outbox_event_should_map_status_and_fields() {
        let item = AiJudgeOutboxItem {
            event_id: "evt-1".to_string(),
            ws_id: Some(1),
            job_id: Some(99),
            trace_id: Some("trace-1".to_string()),
            alert_id: Some("alert-1".to_string()),
            status: Some("acked".to_string()),
            payload: serde_json::json!({
                "eventType": "ai_judge.audit_alert.status_changed.v1",
                "alertType": "model_overload",
                "severity": "critical",
                "title": "模型拥塞",
                "message": "请求出现拥塞",
                "details": { "queueDepth": 12 }
            }),
        };
        let ret = normalize_ai_judge_outbox_event(item).expect("event should be normalized");
        assert_eq!(ret.event_id, "evt-1");
        assert_eq!(ret.ws_id, 1);
        assert_eq!(ret.alert_status, ALERT_STATUS_SUPPRESSED);
        assert_eq!(ret.alert_type, "model_overload");
        assert_eq!(ret.severity, "critical");
        assert_eq!(ret.title, "模型拥塞");
        assert_eq!(ret.message, "请求出现拥塞");
        assert_eq!(
            ret.metrics
                .get("statusRaw")
                .and_then(Value::as_str)
                .unwrap_or_default(),
            "acked"
        );
    }

    #[test]
    fn normalize_ai_judge_outbox_event_should_require_ws_id() {
        let item = AiJudgeOutboxItem {
            event_id: "evt-2".to_string(),
            ws_id: None,
            job_id: None,
            trace_id: None,
            alert_id: None,
            status: Some("raised".to_string()),
            payload: Value::Null,
        };
        let err = normalize_ai_judge_outbox_event(item).expect_err("missing ws id should fail");
        assert!(err.contains("missing wsId"));
    }
}
