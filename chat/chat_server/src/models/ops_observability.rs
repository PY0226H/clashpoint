use crate::{AppError, AppState};
use anyhow::Context;
use chat_core::User;
use chrono::{DateTime, Utc};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha1::{Digest, Sha1};
use sqlx::{FromRow, Postgres, Transaction};
use std::collections::{BTreeMap, HashMap, HashSet};
#[cfg(test)]
use std::sync::atomic::{AtomicBool, Ordering};
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
const OPS_ALERT_RULE_SPLIT_REVIEW_REQUIRED_KEY: &str = "split_readiness_review_required";
const OPS_ALERT_RULE_SPLIT_REVIEW_REQUIRED_TYPE: &str = "split_readiness";
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
const PLATFORM_SCOPE_ID: i64 = 1;
const SPLIT_READINESS_PRESSURE_PENDING_RUNNING_THRESHOLD: i64 = 20;
const SPLIT_READINESS_PRESSURE_PENDING_DLQ_THRESHOLD: i64 = 20;
const SPLIT_READINESS_PRESSURE_AVG_ATTEMPTS_THRESHOLD: f64 = 2.5;
const SPLIT_READINESS_PRESSURE_P95_MS_THRESHOLD: f64 = 300_000.0;
const SPLIT_READINESS_PRESSURE_FAILED_RATIO_THRESHOLD: f64 = 0.3;
const SPLIT_READINESS_PRESSURE_FAILED_RATIO_MIN_DISPATCHED: u64 = 30;
const SPLIT_READINESS_WS_RUNNING_SESSIONS_THRESHOLD: i64 = 100;
const SPLIT_READINESS_WS_MESSAGES_10M_THRESHOLD: i64 = 20_000;
const SPLIT_REVIEW_NOTE_MAX_LEN: usize = 1000;
const SPLIT_REVIEW_STALE_THRESHOLD_HOURS: i64 = 24 * 30;
const OPS_OBSERVABILITY_CONFIG_REVISION_EMPTY: &str = "empty";
pub(crate) const OPS_OBSERVABILITY_IF_MATCH_REQUIRED_CODE: &str =
    "ops_observability_if_match_required";
pub(crate) const OPS_OBSERVABILITY_REVISION_CONFLICT_CODE: &str =
    "ops_observability_revision_conflict";
const OPS_OBSERVABILITY_WRITE_REVISION_LOCK_KEY: &str = "ops_observability_thresholds_write_lock";
const OPS_OBSERVABILITY_THRESHOLD_AUDIT_REQUEST_ID_MAX_LEN: usize = 128;
#[cfg(test)]
static OPS_SPLIT_REVIEW_ALERT_EMIT_FORCE_FAIL: AtomicBool = AtomicBool::new(false);

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
    pub thresholds: OpsObservabilityThresholds,
    #[serde(default)]
    pub anomaly_state: HashMap<String, OpsObservabilityAnomalyStateValue>,
    pub config_revision: String,
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

#[derive(Debug, Clone, FromRow)]
struct OpsServiceSplitReviewRow {
    payment_compliance_required: Option<bool>,
    review_note: String,
    updated_by: i64,
    updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
struct OpsServiceSplitReviewAuditRow {
    id: i64,
    payment_compliance_required: Option<bool>,
    review_note: String,
    updated_by: i64,
    created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, IntoParams, ToSchema, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListOpsAlertNotificationsQuery {
    pub status: Option<String>,
    pub limit: Option<u64>,
    pub offset: Option<u64>,
}

#[derive(Debug, Clone, IntoParams, ToSchema, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RunOpsObservabilityEvaluationQuery {
    pub dry_run: Option<bool>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UpsertOpsServiceSplitReviewInput {
    pub payment_compliance_required: Option<bool>,
    pub review_note: Option<String>,
}

#[derive(Debug, Clone, Copy, Default)]
pub struct UpsertOpsObservabilityThresholdsMeta<'a> {
    pub expected_config_revision: Option<&'a str>,
    pub require_if_match: bool,
    pub request_id: Option<&'a str>,
}

#[derive(Debug, Clone, Copy, Default)]
pub struct UpsertOpsObservabilityAnomalyStateMeta<'a> {
    pub expected_config_revision: Option<&'a str>,
    pub require_if_match: bool,
    pub request_id: Option<&'a str>,
}

#[derive(Debug, Clone, Copy, Default)]
pub struct ApplyOpsObservabilityAnomalyActionMeta<'a> {
    pub request_id: Option<&'a str>,
}

#[derive(Debug, Clone, IntoParams, ToSchema, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListOpsServiceSplitReviewAuditsQuery {
    pub limit: Option<u64>,
    pub offset: Option<u64>,
    pub updated_by: Option<u64>,
    pub payment_compliance_required: Option<bool>,
    pub created_after: Option<DateTime<Utc>>,
    pub created_before: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OpsAlertNotificationItem {
    pub id: u64,
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
    pub dictionary_revision: String,
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
    pub window_minutes: i64,
    pub generated_at_ms: i64,
    pub thresholds: OpsObservabilityThresholds,
    pub signal: OpsSloSignalSnapshot,
    pub rules: Vec<OpsSloRuleSnapshotItem>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OpsServiceSplitThresholdItem {
    pub key: String,
    pub title: String,
    pub status: String,
    pub triggered: bool,
    pub recommendation: String,
    pub evidence: Value,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetOpsServiceSplitReadinessOutput {
    pub generated_at_ms: i64,
    pub overall_status: String,
    pub next_step: String,
    pub thresholds: Vec<OpsServiceSplitThresholdItem>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OpsServiceSplitReviewAuditItem {
    pub id: u64,
    pub payment_compliance_required: Option<bool>,
    pub review_note: String,
    pub updated_by: u64,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListOpsServiceSplitReviewAuditsOutput {
    pub total: u64,
    pub limit: u64,
    pub offset: u64,
    pub items: Vec<OpsServiceSplitReviewAuditItem>,
}

#[derive(Debug, Clone, Default, ToSchema, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct OpsAlertEvalReport {
    pub scopes_scanned: u64,
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
    #[serde(default)]
    scope_id: Option<u64>,
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
    #[serde(default)]
    scope_id: Option<u64>,
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
struct OpsAlertStateByKeyRow {
    alert_key: String,
    is_active: bool,
    last_emitted_status: String,
}

#[derive(Debug, Clone, FromRow)]
struct OpsObservabilityEvalScopeRow {
    scope_id: i64,
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

#[derive(Debug, Clone)]
struct NormalizeAnomalyStateResult {
    state: HashMap<String, OpsObservabilityAnomalyStateValue>,
    input_count: usize,
    retained_count: usize,
    dropped_count: usize,
}

fn normalize_anomaly_state_with_stats(
    input: HashMap<String, OpsObservabilityAnomalyStateValue>,
    now_ms: i64,
) -> NormalizeAnomalyStateResult {
    let input_count = input.len();
    let mut normalized = BTreeMap::new();
    for (key_raw, item) in input {
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
        normalized.insert(
            key.to_string(),
            OpsObservabilityAnomalyStateValue {
                acknowledged_at_ms,
                suppress_until_ms,
            },
        );
    }

    let mut retained_items: Vec<(String, OpsObservabilityAnomalyStateValue)> =
        normalized.into_iter().collect();
    if retained_items.len() > MAX_STATE_ITEM_COUNT {
        retained_items.truncate(MAX_STATE_ITEM_COUNT);
    }
    let retained_count = retained_items.len();
    let mut state = HashMap::with_capacity(retained_count);
    for (key, value) in retained_items {
        state.insert(key, value);
    }
    NormalizeAnomalyStateResult {
        state,
        input_count,
        retained_count,
        dropped_count: input_count.saturating_sub(retained_count),
    }
}

fn normalize_anomaly_state(
    input: HashMap<String, OpsObservabilityAnomalyStateValue>,
    now_ms: i64,
) -> HashMap<String, OpsObservabilityAnomalyStateValue> {
    normalize_anomaly_state_with_stats(input, now_ms).state
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

#[derive(Debug, Clone)]
struct NormalizedAnomalyActionInput {
    alert_key: String,
    action: &'static str,
    suppress_minutes: i64,
}

fn normalize_anomaly_action_input(
    input: &ApplyOpsObservabilityAnomalyActionInput,
) -> Result<NormalizedAnomalyActionInput, AppError> {
    let alert_key = normalize_anomaly_action_alert_key(&input.alert_key)
        .ok_or_else(|| AppError::DebateError("invalid alert key for anomaly action".to_string()))?;
    let action = normalize_anomaly_action(&input.action).ok_or_else(|| {
        AppError::DebateError(
            "invalid anomaly action, expect acknowledge/suppress/clear".to_string(),
        )
    })?;
    Ok(NormalizedAnomalyActionInput {
        alert_key,
        action,
        suppress_minutes: normalize_anomaly_suppress_minutes(input.suppress_minutes),
    })
}

fn apply_anomaly_action_with_normalized(
    current_state: HashMap<String, OpsObservabilityAnomalyStateValue>,
    input: &NormalizedAnomalyActionInput,
    now_ms: i64,
) -> HashMap<String, OpsObservabilityAnomalyStateValue> {
    let mut anomaly_state = current_state;
    match input.action {
        OPS_ANOMALY_ACTION_ACKNOWLEDGE => {
            let mut item = anomaly_state.remove(&input.alert_key).unwrap_or(
                OpsObservabilityAnomalyStateValue {
                    acknowledged_at_ms: 0,
                    suppress_until_ms: 0,
                },
            );
            item.acknowledged_at_ms = now_ms;
            anomaly_state.insert(input.alert_key.clone(), item);
        }
        OPS_ANOMALY_ACTION_SUPPRESS => {
            let mut item = anomaly_state.remove(&input.alert_key).unwrap_or(
                OpsObservabilityAnomalyStateValue {
                    acknowledged_at_ms: 0,
                    suppress_until_ms: 0,
                },
            );
            item.acknowledged_at_ms = now_ms.max(item.acknowledged_at_ms);
            item.suppress_until_ms =
                now_ms.saturating_add(input.suppress_minutes.saturating_mul(60_000));
            anomaly_state.insert(input.alert_key.clone(), item);
        }
        OPS_ANOMALY_ACTION_CLEAR => {
            anomaly_state.remove(&input.alert_key);
        }
        _ => unreachable!("normalize_anomaly_action guarantees known variants"),
    }
    normalize_anomaly_state(anomaly_state, now_ms)
}

fn apply_anomaly_action(
    current_state: HashMap<String, OpsObservabilityAnomalyStateValue>,
    input: &ApplyOpsObservabilityAnomalyActionInput,
    now_ms: i64,
) -> Result<HashMap<String, OpsObservabilityAnomalyStateValue>, AppError> {
    let normalized = normalize_anomaly_action_input(input)?;
    Ok(apply_anomaly_action_with_normalized(
        current_state,
        &normalized,
        now_ms,
    ))
}

fn normalize_updated_by(raw: i64) -> Option<u64> {
    // 防御式处理历史脏数据，避免 i64 -> u64 的隐式溢出。
    match u64::try_from(raw) {
        Ok(value) => Some(value),
        Err(_) => {
            warn!(
                updated_by = raw,
                "ops observability config has invalid updated_by, fallback to null"
            );
            None
        }
    }
}

fn format_ops_observability_config_revision(updated_at: Option<DateTime<Utc>>) -> String {
    updated_at
        .map(|value| value.to_rfc3339_opts(chrono::SecondsFormat::Micros, true))
        .unwrap_or_else(|| OPS_OBSERVABILITY_CONFIG_REVISION_EMPTY.to_string())
}

fn ensure_expected_ops_observability_revision(
    expected_config_revision: Option<&str>,
    current_revision: &str,
    require_if_match: bool,
) -> Result<(), AppError> {
    if let Some(expected) = expected_config_revision {
        if expected != current_revision {
            return Err(AppError::DebateConflict(
                OPS_OBSERVABILITY_REVISION_CONFLICT_CODE.to_string(),
            ));
        }
    } else if require_if_match {
        return Err(AppError::DebateError(
            OPS_OBSERVABILITY_IF_MATCH_REQUIRED_CODE.to_string(),
        ));
    }
    Ok(())
}

fn normalize_ops_observability_audit_request_id(raw: Option<&str>) -> Option<String> {
    raw.map(str::trim)
        .filter(|value| !value.is_empty())
        .map(|value| {
            value
                .chars()
                .take(OPS_OBSERVABILITY_THRESHOLD_AUDIT_REQUEST_ID_MAX_LEN)
                .collect::<String>()
        })
}

fn build_output(
    row: Option<OpsObservabilityConfigRow>,
    now_ms: i64,
) -> GetOpsObservabilityConfigOutput {
    let Some(row) = row else {
        return GetOpsObservabilityConfigOutput {
            thresholds: OpsObservabilityThresholds::default(),
            anomaly_state: HashMap::new(),
            config_revision: OPS_OBSERVABILITY_CONFIG_REVISION_EMPTY.to_string(),
            updated_by: None,
            updated_at: None,
        };
    };
    GetOpsObservabilityConfigOutput {
        thresholds: parse_thresholds(row.thresholds_json),
        anomaly_state: parse_anomaly_state(row.anomaly_state_json, now_ms),
        config_revision: format_ops_observability_config_revision(Some(row.updated_at)),
        updated_by: normalize_updated_by(row.updated_by),
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
            key: "ops.rbac.roles_list.request_total".to_string(),
            category: "ops_rbac".to_string(),
            source: "chat_server.handlers.debate_ops".to_string(),
            unit: "count".to_string(),
            aggregation: "sum".to_string(),
            description: "Ops RBAC roles list request total.".to_string(),
            target: None,
        },
        OpsMetricsDictionaryItem {
            key: "ops.rbac.roles_list.success_total".to_string(),
            category: "ops_rbac".to_string(),
            source: "chat_server.handlers.debate_ops".to_string(),
            unit: "count".to_string(),
            aggregation: "sum".to_string(),
            description: "Ops RBAC roles list success total.".to_string(),
            target: None,
        },
        OpsMetricsDictionaryItem {
            key: "ops.rbac.roles_list.failed_total".to_string(),
            category: "ops_rbac".to_string(),
            source: "chat_server.handlers.debate_ops".to_string(),
            unit: "count".to_string(),
            aggregation: "sum".to_string(),
            description: "Ops RBAC roles list failed total.".to_string(),
            target: None,
        },
        OpsMetricsDictionaryItem {
            key: "ops.rbac.roles_list.permission_denied_total".to_string(),
            category: "ops_rbac".to_string(),
            source: "chat_server.handlers.debate_ops".to_string(),
            unit: "count".to_string(),
            aggregation: "sum".to_string(),
            description: "Ops RBAC roles list permission denied total.".to_string(),
            target: None,
        },
        OpsMetricsDictionaryItem {
            key: "ops.rbac.roles_list.rate_limited_total".to_string(),
            category: "ops_rbac".to_string(),
            source: "chat_server.handlers.debate_ops".to_string(),
            unit: "count".to_string(),
            aggregation: "sum".to_string(),
            description: "Ops RBAC roles list rate-limited total.".to_string(),
            target: None,
        },
        OpsMetricsDictionaryItem {
            key: "ops.rbac.roles_list.latency_p95_ms".to_string(),
            category: "ops_rbac".to_string(),
            source: "chat_server.handlers.debate_ops".to_string(),
            unit: "ms".to_string(),
            aggregation: "p95".to_string(),
            description: "Ops RBAC roles list latency p95.".to_string(),
            target: Some("<300".to_string()),
        },
        OpsMetricsDictionaryItem {
            key: "ops.rbac.me.request_total".to_string(),
            category: "ops_rbac".to_string(),
            source: "chat_server.handlers.debate_ops".to_string(),
            unit: "count".to_string(),
            aggregation: "sum".to_string(),
            description: "Ops RBAC me request total.".to_string(),
            target: None,
        },
        OpsMetricsDictionaryItem {
            key: "ops.rbac.me.success_total".to_string(),
            category: "ops_rbac".to_string(),
            source: "chat_server.handlers.debate_ops".to_string(),
            unit: "count".to_string(),
            aggregation: "sum".to_string(),
            description: "Ops RBAC me success total.".to_string(),
            target: None,
        },
        OpsMetricsDictionaryItem {
            key: "ops.rbac.me.failed_total".to_string(),
            category: "ops_rbac".to_string(),
            source: "chat_server.handlers.debate_ops".to_string(),
            unit: "count".to_string(),
            aggregation: "sum".to_string(),
            description: "Ops RBAC me failed total.".to_string(),
            target: None,
        },
        OpsMetricsDictionaryItem {
            key: "ops.rbac.me.rate_limited_total".to_string(),
            category: "ops_rbac".to_string(),
            source: "chat_server.handlers.debate_ops".to_string(),
            unit: "count".to_string(),
            aggregation: "sum".to_string(),
            description: "Ops RBAC me rate-limited total.".to_string(),
            target: None,
        },
        OpsMetricsDictionaryItem {
            key: "ops.rbac.me.owner_total".to_string(),
            category: "ops_rbac".to_string(),
            source: "chat_server.handlers.debate_ops".to_string(),
            unit: "count".to_string(),
            aggregation: "sum".to_string(),
            description: "Ops RBAC me owner snapshot total.".to_string(),
            target: None,
        },
        OpsMetricsDictionaryItem {
            key: "ops.rbac.me.non_owner_total".to_string(),
            category: "ops_rbac".to_string(),
            source: "chat_server.handlers.debate_ops".to_string(),
            unit: "count".to_string(),
            aggregation: "sum".to_string(),
            description: "Ops RBAC me non-owner snapshot total.".to_string(),
            target: None,
        },
        OpsMetricsDictionaryItem {
            key: "ops.rbac.me.latency_p95_ms".to_string(),
            category: "ops_rbac".to_string(),
            source: "chat_server.handlers.debate_ops".to_string(),
            unit: "ms".to_string(),
            aggregation: "p95".to_string(),
            description: "Ops RBAC me latency p95.".to_string(),
            target: Some("<200".to_string()),
        },
        OpsMetricsDictionaryItem {
            key: "ops.rbac.roles_write.request_total".to_string(),
            category: "ops_rbac".to_string(),
            source: "chat_server.handlers.debate_ops".to_string(),
            unit: "count".to_string(),
            aggregation: "sum".to_string(),
            description: "Ops RBAC role write request total.".to_string(),
            target: None,
        },
        OpsMetricsDictionaryItem {
            key: "ops.rbac.roles_write.success_total".to_string(),
            category: "ops_rbac".to_string(),
            source: "chat_server.handlers.debate_ops".to_string(),
            unit: "count".to_string(),
            aggregation: "sum".to_string(),
            description: "Ops RBAC role write success total.".to_string(),
            target: None,
        },
        OpsMetricsDictionaryItem {
            key: "ops.rbac.roles_write.failed_total".to_string(),
            category: "ops_rbac".to_string(),
            source: "chat_server.handlers.debate_ops".to_string(),
            unit: "count".to_string(),
            aggregation: "sum".to_string(),
            description: "Ops RBAC role write failed total.".to_string(),
            target: None,
        },
        OpsMetricsDictionaryItem {
            key: "ops.rbac.roles_write.rate_limited_total".to_string(),
            category: "ops_rbac".to_string(),
            source: "chat_server.handlers.debate_ops".to_string(),
            unit: "count".to_string(),
            aggregation: "sum".to_string(),
            description: "Ops RBAC role write rate-limited total.".to_string(),
            target: None,
        },
        OpsMetricsDictionaryItem {
            key: "ops.rbac.roles_write.upsert_total".to_string(),
            category: "ops_rbac".to_string(),
            source: "chat_server.handlers.debate_ops".to_string(),
            unit: "count".to_string(),
            aggregation: "sum".to_string(),
            description: "Ops RBAC role upsert total.".to_string(),
            target: None,
        },
        OpsMetricsDictionaryItem {
            key: "ops.rbac.roles_write.revoke_total".to_string(),
            category: "ops_rbac".to_string(),
            source: "chat_server.handlers.debate_ops".to_string(),
            unit: "count".to_string(),
            aggregation: "sum".to_string(),
            description: "Ops RBAC role revoke total.".to_string(),
            target: None,
        },
        OpsMetricsDictionaryItem {
            key: "ops.rbac.roles_write.latency_p95_ms".to_string(),
            category: "ops_rbac".to_string(),
            source: "chat_server.handlers.debate_ops".to_string(),
            unit: "ms".to_string(),
            aggregation: "p95".to_string(),
            description: "Ops RBAC role write latency p95.".to_string(),
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

fn build_ops_metrics_dictionary_revision(items: &[OpsMetricsDictionaryItem]) -> String {
    let mut hasher = Sha1::new();
    // 使用稳定 JSON 序列作为 revision 输入，确保同内容产生同 revision。
    let payload = serde_json::to_vec(items).unwrap_or_default();
    hasher.update(payload);
    format!("sha1:{:x}", hasher.finalize())
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

fn normalize_split_review_audit_limit(limit: Option<u64>) -> i64 {
    limit.unwrap_or(20).clamp(1, 200) as i64
}

fn normalize_split_review_audit_offset(offset: Option<u64>) -> i64 {
    offset.unwrap_or(0).min(50_000) as i64
}

fn normalize_split_review_audit_updated_by_filter(
    updated_by: Option<u64>,
) -> Result<Option<i64>, AppError> {
    updated_by
        .map(|value| {
            i64::try_from(value).map_err(|_| {
                AppError::DebateError("split review updatedBy out of range".to_string())
            })
        })
        .transpose()
}

fn normalize_split_review_audit_created_window(
    created_after: Option<DateTime<Utc>>,
    created_before: Option<DateTime<Utc>>,
) -> Result<(Option<DateTime<Utc>>, Option<DateTime<Utc>>), AppError> {
    if let (Some(after), Some(before)) = (created_after, created_before) {
        if after > before {
            return Err(AppError::DebateError(
                "invalid split review created window: createdAfter must be <= createdBefore"
                    .to_string(),
            ));
        }
    }
    Ok((created_after, created_before))
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

fn normalize_split_review_note(raw: Option<String>) -> Result<String, AppError> {
    let note = raw.unwrap_or_default().trim().to_string();
    if note.chars().count() > SPLIT_REVIEW_NOTE_MAX_LEN {
        return Err(AppError::DebateError(format!(
            "split readiness review note too long, max {} chars",
            SPLIT_REVIEW_NOTE_MAX_LEN
        )));
    }
    Ok(note)
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

fn map_split_review_audit_i64_to_u64(value: i64, field: &'static str) -> Result<u64, AppError> {
    u64::try_from(value).map_err(|_| {
        warn!(
            field,
            value, "ops split review audit has invalid negative integer value"
        );
        AppError::ServerError(format!("ops_split_review_audit_invalid_{field}"))
    })
}

fn map_split_review_audit_row(
    row: OpsServiceSplitReviewAuditRow,
) -> Result<OpsServiceSplitReviewAuditItem, AppError> {
    Ok(OpsServiceSplitReviewAuditItem {
        id: map_split_review_audit_i64_to_u64(row.id, "id")?,
        payment_compliance_required: row.payment_compliance_required,
        review_note: row.review_note,
        updated_by: map_split_review_audit_i64_to_u64(row.updated_by, "updated_by")?,
        created_at: row.created_at,
    })
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
    let scope_id = item
        .scope_id
        .or(payload.scope_id)
        .and_then(|value| i64::try_from(value).ok())
        .unwrap_or(PLATFORM_SCOPE_ID);
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
        "scopeId": scope_id,
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
            let sample_enough = completed >= thresholds.min_request_for_cache_hit_check;
            let is_active = sample_enough && success_rate < thresholds.low_success_rate_threshold;
            let comparison = if !sample_enough {
                "insufficient_sample"
            } else if is_active {
                "below_threshold"
            } else {
                "above_or_equal_threshold"
            };
            let message = if !sample_enough {
                format!(
                    "最近{}分钟完成样本 {} 小于最小阈值 {}，暂不触发成功率告警",
                    OPS_ALERT_EVAL_WINDOW_MINUTES,
                    completed,
                    thresholds.min_request_for_cache_hit_check
                )
            } else if is_active {
                format!(
                    "最近{}分钟判决成功率 {:.2}% 低于阈值 {:.2}%",
                    OPS_ALERT_EVAL_WINDOW_MINUTES,
                    success_rate,
                    thresholds.low_success_rate_threshold
                )
            } else {
                format!(
                    "最近{}分钟判决成功率 {:.2}% 不低于阈值 {:.2}%",
                    OPS_ALERT_EVAL_WINDOW_MINUTES,
                    success_rate,
                    thresholds.low_success_rate_threshold
                )
            };
            EvaluatedAlert {
                alert_key: spec.alert_key.to_string(),
                rule_type: spec.rule_type.to_string(),
                severity: ALERT_SEVERITY_WARNING.to_string(),
                title: spec.title.to_string(),
                message,
                metrics: serde_json::json!({
                    "windowMinutes": OPS_ALERT_EVAL_WINDOW_MINUTES,
                    "completedCount": completed,
                    "minCompletedForEval": thresholds.min_request_for_cache_hit_check,
                    "successCount": signal.success_count,
                    "failedCount": signal.failed_count,
                    "successRatePct": success_rate,
                    "thresholdPct": thresholds.low_success_rate_threshold,
                    "comparison": comparison,
                }),
                is_active,
            }
        }
        OPS_ALERT_RULE_HIGH_RETRY => {
            let completed = signal.success_count + signal.failed_count;
            let sample_enough = completed >= thresholds.min_request_for_cache_hit_check;
            let is_active =
                sample_enough && signal.avg_dispatch_attempts > thresholds.high_retry_threshold;
            let comparison = if !sample_enough {
                "insufficient_sample"
            } else if is_active {
                "above_threshold"
            } else {
                "at_or_below_threshold"
            };
            let message = if !sample_enough {
                format!(
                    "最近{}分钟完成样本 {} 小于最小阈值 {}，暂不触发重试告警",
                    OPS_ALERT_EVAL_WINDOW_MINUTES,
                    completed,
                    thresholds.min_request_for_cache_hit_check
                )
            } else if is_active {
                format!(
                    "最近{}分钟平均 dispatch_attempts {:.2} 高于阈值 {:.2}",
                    OPS_ALERT_EVAL_WINDOW_MINUTES,
                    signal.avg_dispatch_attempts,
                    thresholds.high_retry_threshold
                )
            } else {
                format!(
                    "最近{}分钟平均 dispatch_attempts {:.2} 不高于阈值 {:.2}",
                    OPS_ALERT_EVAL_WINDOW_MINUTES,
                    signal.avg_dispatch_attempts,
                    thresholds.high_retry_threshold
                )
            };
            EvaluatedAlert {
                alert_key: spec.alert_key.to_string(),
                rule_type: spec.rule_type.to_string(),
                severity: ALERT_SEVERITY_WARNING.to_string(),
                title: spec.title.to_string(),
                message,
                metrics: serde_json::json!({
                    "windowMinutes": OPS_ALERT_EVAL_WINDOW_MINUTES,
                    "completedCount": completed,
                    "minCompletedForEval": thresholds.min_request_for_cache_hit_check,
                    "avgDispatchAttempts": signal.avg_dispatch_attempts,
                    "threshold": thresholds.high_retry_threshold,
                    "comparison": comparison,
                }),
                is_active,
            }
        }
        OPS_ALERT_RULE_HIGH_DB_LATENCY => {
            let completed = signal.success_count + signal.failed_count;
            let sample_enough = completed >= thresholds.min_request_for_cache_hit_check;
            let is_active = sample_enough
                && signal.p95_latency_ms > thresholds.high_db_latency_threshold_ms as f64;
            let comparison = if !sample_enough {
                "insufficient_sample"
            } else if is_active {
                "above_threshold"
            } else {
                "at_or_below_threshold"
            };
            let message = if !sample_enough {
                format!(
                    "最近{}分钟完成样本 {} 小于最小阈值 {}，暂不触发时延告警",
                    OPS_ALERT_EVAL_WINDOW_MINUTES,
                    completed,
                    thresholds.min_request_for_cache_hit_check
                )
            } else if is_active {
                format!(
                    "最近{}分钟判决链路 P95 时延 {:.0}ms 高于阈值 {}ms",
                    OPS_ALERT_EVAL_WINDOW_MINUTES,
                    signal.p95_latency_ms,
                    thresholds.high_db_latency_threshold_ms
                )
            } else {
                format!(
                    "最近{}分钟判决链路 P95 时延 {:.0}ms 不高于阈值 {}ms",
                    OPS_ALERT_EVAL_WINDOW_MINUTES,
                    signal.p95_latency_ms,
                    thresholds.high_db_latency_threshold_ms
                )
            };
            EvaluatedAlert {
                alert_key: spec.alert_key.to_string(),
                rule_type: spec.rule_type.to_string(),
                severity: ALERT_SEVERITY_WARNING.to_string(),
                title: spec.title.to_string(),
                message,
                metrics: serde_json::json!({
                    "windowMinutes": OPS_ALERT_EVAL_WINDOW_MINUTES,
                    "completedCount": completed,
                    "minCompletedForEval": thresholds.min_request_for_cache_hit_check,
                    "p95LatencyMs": signal.p95_latency_ms,
                    "thresholdMs": thresholds.high_db_latency_threshold_ms,
                    "comparison": comparison,
                }),
                is_active,
            }
        }
        OPS_ALERT_RULE_DLQ_PENDING => {
            let is_active = signal.pending_dlq_count as f64 > thresholds.high_coalesced_threshold;
            let comparison = if is_active {
                "above_threshold"
            } else {
                "at_or_below_threshold"
            };
            let message = if is_active {
                format!(
                    "当前 DLQ pending 数量 {} 超过阈值 {:.2}",
                    signal.pending_dlq_count, thresholds.high_coalesced_threshold
                )
            } else {
                format!(
                    "当前 DLQ pending 数量 {} 未超过阈值 {:.2}",
                    signal.pending_dlq_count, thresholds.high_coalesced_threshold
                )
            };
            EvaluatedAlert {
                alert_key: spec.alert_key.to_string(),
                rule_type: spec.rule_type.to_string(),
                severity: ALERT_SEVERITY_WARNING.to_string(),
                title: spec.title.to_string(),
                message,
                metrics: serde_json::json!({
                    "pendingDlqCount": signal.pending_dlq_count,
                    "threshold": thresholds.high_coalesced_threshold,
                    "comparison": comparison,
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

fn build_split_review_required_alert(
    snapshot: &GetOpsServiceSplitReadinessOutput,
    triggered_by: i64,
) -> EvaluatedAlert {
    let triggered_thresholds: Vec<String> = snapshot
        .thresholds
        .iter()
        .filter(|item| item.triggered)
        .map(|item| item.key.clone())
        .collect();
    let payment_required = snapshot
        .thresholds
        .iter()
        .find(|item| item.key == "payment_compliance_isolation")
        .and_then(|item| item.evidence.get("paymentComplianceRequired"))
        .and_then(|value| value.as_bool());
    EvaluatedAlert {
        alert_key: OPS_ALERT_RULE_SPLIT_REVIEW_REQUIRED_KEY.to_string(),
        rule_type: OPS_ALERT_RULE_SPLIT_REVIEW_REQUIRED_TYPE.to_string(),
        severity: ALERT_SEVERITY_WARNING.to_string(),
        title: "服务拆分评审已触发".to_string(),
        message: "split-readiness 从 hold 进入 review_required，请启动 R6 架构评审。".to_string(),
        metrics: json!({
            "overallStatus": snapshot.overall_status,
            "nextStep": snapshot.next_step,
            "triggeredThresholds": triggered_thresholds,
            "paymentComplianceRequired": payment_required,
            "triggeredBy": triggered_by,
        }),
        is_active: true,
    }
}

fn build_split_review_cleared_alert(
    snapshot: &GetOpsServiceSplitReadinessOutput,
    triggered_by: i64,
) -> EvaluatedAlert {
    EvaluatedAlert {
        alert_key: OPS_ALERT_RULE_SPLIT_REVIEW_REQUIRED_KEY.to_string(),
        rule_type: OPS_ALERT_RULE_SPLIT_REVIEW_REQUIRED_TYPE.to_string(),
        severity: ALERT_SEVERITY_WARNING.to_string(),
        title: "服务拆分评审已解除".to_string(),
        message: "split-readiness 从 review_required 回落到 hold，当前可保持现有拓扑。".to_string(),
        metrics: json!({
            "overallStatus": snapshot.overall_status,
            "nextStep": snapshot.next_step,
            "triggeredBy": triggered_by,
        }),
        is_active: false,
    }
}

fn build_split_review_transition_plan(
    before_snapshot: &GetOpsServiceSplitReadinessOutput,
    after_snapshot: &GetOpsServiceSplitReadinessOutput,
    triggered_by: i64,
) -> Option<EmitAlertPlan> {
    if before_snapshot.overall_status != "review_required"
        && after_snapshot.overall_status == "review_required"
    {
        return Some(EmitAlertPlan {
            status: ALERT_STATUS_RAISED,
            mark_active: true,
            evaluated: build_split_review_required_alert(after_snapshot, triggered_by),
        });
    }
    if before_snapshot.overall_status == "review_required"
        && after_snapshot.overall_status != "review_required"
    {
        return Some(EmitAlertPlan {
            status: ALERT_STATUS_CLEARED,
            mark_active: false,
            evaluated: build_split_review_cleared_alert(after_snapshot, triggered_by),
        });
    }
    None
}

async fn acquire_ops_observability_revision_lock(
    tx: &mut Transaction<'_, Postgres>,
) -> Result<(), AppError> {
    // 控制面阈值写频率低，使用事务级 advisory lock 让 If-Match 校验与写入保持串行语义。
    sqlx::query("SELECT pg_advisory_xact_lock(hashtext($1))")
        .bind(OPS_OBSERVABILITY_WRITE_REVISION_LOCK_KEY)
        .execute(&mut **tx)
        .await?;
    Ok(())
}

impl AppState {
    pub async fn upsert_ops_service_split_review(
        &self,
        user: &User,
        input: UpsertOpsServiceSplitReviewInput,
    ) -> Result<GetOpsServiceSplitReadinessOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::ObservabilityManage)
            .await?;
        let review_note = normalize_split_review_note(input.review_note)?;
        let before_snapshot = self.get_ops_service_split_readiness(user).await?;
        let mut tx = self.pool.begin().await?;
        sqlx::query(
            r#"
            INSERT INTO ops_service_split_reviews(
                singleton_id, payment_compliance_required, review_note, updated_by, created_at, updated_at
            )
            VALUES (1, $1, $2, $3, NOW(), NOW())
            ON CONFLICT (singleton_id)
            DO UPDATE SET
                payment_compliance_required = EXCLUDED.payment_compliance_required,
                review_note = EXCLUDED.review_note,
                updated_by = EXCLUDED.updated_by,
                updated_at = NOW()
            "#,
        )
        .bind(input.payment_compliance_required)
        .bind(&review_note)
        .bind(user.id)
        .execute(&mut *tx)
        .await?;
        sqlx::query(
            r#"
            INSERT INTO ops_service_split_review_audits(
                payment_compliance_required, review_note, updated_by, created_at
            )
            VALUES ($1, $2, $3, NOW())
            "#,
        )
        .bind(input.payment_compliance_required)
        .bind(review_note)
        .bind(user.id)
        .execute(&mut *tx)
        .await?;
        tx.commit().await?;
        let after_snapshot = self.get_ops_service_split_readiness(user).await?;
        if let Some(plan) =
            build_split_review_transition_plan(&before_snapshot, &after_snapshot, user.id)
        {
            let alert_status = plan.status;
            let alert_key = plan.evaluated.alert_key.clone();
            match self.list_alert_recipients().await {
                Ok(recipients) => {
                    let emit_result: Result<(), AppError> = {
                        #[cfg(test)]
                        {
                            if OPS_SPLIT_REVIEW_ALERT_EMIT_FORCE_FAIL.load(Ordering::Relaxed) {
                                Err(AppError::ServerError(
                                    "ops_split_review_alert_emit_forced_failure".to_string(),
                                ))
                            } else {
                                self.emit_observability_alert(plan, &recipients).await
                            }
                        }
                        #[cfg(not(test))]
                        {
                            self.emit_observability_alert(plan, &recipients).await
                        }
                    };
                    if let Err(err) = emit_result {
                        warn!(
                            user_id = user.id,
                            before_status = before_snapshot.overall_status.as_str(),
                            after_status = after_snapshot.overall_status.as_str(),
                            alert_status,
                            alert_key = alert_key.as_str(),
                            "upsert split review alert emission failed: {}",
                            err
                        );
                    }
                }
                Err(err) => {
                    warn!(
                        user_id = user.id,
                        before_status = before_snapshot.overall_status.as_str(),
                        after_status = after_snapshot.overall_status.as_str(),
                        alert_status,
                        alert_key = alert_key.as_str(),
                        "upsert split review list alert recipients failed: {}",
                        err
                    );
                }
            }
        }
        Ok(after_snapshot)
    }

    pub async fn list_ops_service_split_review_audits(
        &self,
        user: &User,
        query: ListOpsServiceSplitReviewAuditsQuery,
    ) -> Result<ListOpsServiceSplitReviewAuditsOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::ObservabilityRead)
            .await?;
        let limit = normalize_split_review_audit_limit(query.limit);
        let offset = normalize_split_review_audit_offset(query.offset);
        let updated_by = normalize_split_review_audit_updated_by_filter(query.updated_by)?;
        let payment_compliance_required = query.payment_compliance_required;
        let (created_after, created_before) =
            normalize_split_review_audit_created_window(query.created_after, query.created_before)?;
        let total: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)::bigint
            FROM ops_service_split_review_audits
            WHERE ($1::bigint IS NULL OR updated_by = $1)
              AND ($2::boolean IS NULL OR payment_compliance_required IS NOT DISTINCT FROM $2)
              AND ($3::timestamptz IS NULL OR created_at >= $3)
              AND ($4::timestamptz IS NULL OR created_at <= $4)
            "#,
        )
        .bind(updated_by)
        .bind(payment_compliance_required)
        .bind(created_after)
        .bind(created_before)
        .fetch_one(&self.pool)
        .await?;
        let rows: Vec<OpsServiceSplitReviewAuditRow> = sqlx::query_as(
            r#"
            SELECT
                id, payment_compliance_required, review_note, updated_by, created_at
            FROM ops_service_split_review_audits
            WHERE ($1::bigint IS NULL OR updated_by = $1)
              AND ($2::boolean IS NULL OR payment_compliance_required IS NOT DISTINCT FROM $2)
              AND ($3::timestamptz IS NULL OR created_at >= $3)
              AND ($4::timestamptz IS NULL OR created_at <= $4)
            ORDER BY created_at DESC, id DESC
            LIMIT $5 OFFSET $6
            "#,
        )
        .bind(updated_by)
        .bind(payment_compliance_required)
        .bind(created_after)
        .bind(created_before)
        .bind(limit)
        .bind(offset)
        .fetch_all(&self.pool)
        .await?;
        let mut items = Vec::with_capacity(rows.len());
        for row in rows {
            items.push(map_split_review_audit_row(row)?);
        }
        Ok(ListOpsServiceSplitReviewAuditsOutput {
            total: total.max(0) as u64,
            limit: limit as u64,
            offset: offset as u64,
            items,
        })
    }

    pub async fn get_ops_service_split_readiness(
        &self,
        user: &User,
    ) -> Result<GetOpsServiceSplitReadinessOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::ObservabilityRead)
            .await?;
        let generated_at_ms = now_millis();
        let signal = self.load_recent_judge_signal().await?;
        let compliance_review: Option<OpsServiceSplitReviewRow> = sqlx::query_as(
            r#"
            SELECT payment_compliance_required, review_note, updated_by, updated_at
            FROM ops_service_split_reviews
            WHERE singleton_id = 1
            "#,
        )
        .fetch_optional(&self.pool)
        .await?;
        let dispatch_metrics = self.get_judge_dispatch_metrics();
        let pending_running_jobs: i64 = sqlx::query_scalar(
            r#"
            SELECT (
                COALESCE((
                    SELECT COUNT(1)::bigint
                    FROM judge_phase_jobs p
                    WHERE p.status IN ('queued', 'dispatched')
                ), 0)
                +
                COALESCE((
                    SELECT COUNT(1)::bigint
                    FROM judge_final_jobs f
                    WHERE f.status IN ('queued', 'dispatched')
                ), 0)
            )::bigint
            "#,
        )
        .fetch_one(&self.pool)
        .await?;
        let running_sessions: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)::bigint
            FROM debate_sessions
            WHERE status = 'running'
            "#,
        )
        .fetch_one(&self.pool)
        .await?;
        let recent_messages_10m: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)::bigint
            FROM session_messages
            WHERE created_at >= NOW() - INTERVAL '10 minutes'
            "#,
        )
        .fetch_one(&self.pool)
        .await?;
        let failed_ratio_lifetime = if dispatch_metrics.dispatched_total == 0 {
            0.0
        } else {
            dispatch_metrics.failed_total as f64 / dispatch_metrics.dispatched_total as f64
        };
        let window_completed =
            signal.success_count.max(0) as u64 + signal.failed_count.max(0) as u64;
        let failed_ratio_window = if window_completed == 0 {
            0.0
        } else {
            signal.failed_count.max(0) as f64 / window_completed as f64
        };
        let failed_ratio_sample_enough =
            window_completed >= SPLIT_READINESS_PRESSURE_FAILED_RATIO_MIN_DISPATCHED;
        let failed_ratio_comparison = if !failed_ratio_sample_enough {
            "insufficient_sample"
        } else if failed_ratio_window >= SPLIT_READINESS_PRESSURE_FAILED_RATIO_THRESHOLD {
            "above_threshold"
        } else {
            "below_threshold"
        };

        let dispatch_pressure_triggered = pending_running_jobs
            >= SPLIT_READINESS_PRESSURE_PENDING_RUNNING_THRESHOLD
            || signal.pending_dlq_count >= SPLIT_READINESS_PRESSURE_PENDING_DLQ_THRESHOLD
            || signal.avg_dispatch_attempts >= SPLIT_READINESS_PRESSURE_AVG_ATTEMPTS_THRESHOLD
            || signal.p95_latency_ms >= SPLIT_READINESS_PRESSURE_P95_MS_THRESHOLD
            || (failed_ratio_sample_enough
                && failed_ratio_window >= SPLIT_READINESS_PRESSURE_FAILED_RATIO_THRESHOLD);
        let dispatch_pressure_status = if dispatch_pressure_triggered {
            "met"
        } else {
            "not_met"
        };
        let dispatch_pressure_recommendation = if dispatch_pressure_triggered {
            "进入 R6 评审：评估是否将 judge_dispatch worker 进一步服务化并独立扩缩容。"
        } else {
            "保持当前拓扑，持续观察 dispatch 压力信号。"
        };

        let payment_compliance_required = compliance_review
            .as_ref()
            .and_then(|row| row.payment_compliance_required);
        let review_age_hours = compliance_review.as_ref().map(|row| {
            generated_at_ms
                .saturating_sub(row.updated_at.timestamp_millis())
                .max(0)
                / 3_600_000
        });
        let review_stale = review_age_hours
            .map(|age| age >= SPLIT_REVIEW_STALE_THRESHOLD_HOURS)
            .unwrap_or(true);
        let payment_compliance_status = match payment_compliance_required {
            Some(true) => "met",
            Some(false) => "not_met",
            None => "insufficient_data",
        };
        let payment_compliance_triggered = payment_compliance_required.unwrap_or(false);
        let payment_compliance_recommendation = match payment_compliance_required {
            Some(true) => "已标记合规隔离需求，进入 R6 架构评审并准备独立部署方案。",
            Some(false) => "已确认当前无合规隔离硬要求，可继续保持现有部署域。",
            None => "当前未录入合规评审结论，请由法务/支付合规负责人补充。",
        };

        let ws_scale_triggered = running_sessions >= SPLIT_READINESS_WS_RUNNING_SESSIONS_THRESHOLD
            || recent_messages_10m >= SPLIT_READINESS_WS_MESSAGES_10M_THRESHOLD;
        let ws_scale_status = if ws_scale_triggered { "met" } else { "not_met" };
        let ws_scale_recommendation = if ws_scale_triggered {
            "进入 R6 评审：评估 WS 链路是否需要独立部署域或扩展策略升级。"
        } else {
            "WS 活跃规模未触发阈值，维持现有治理策略并继续监控。"
        };

        let thresholds = vec![
            OpsServiceSplitThresholdItem {
                key: "judge_dispatch_pressure".to_string(),
                title: "judge_dispatch 资源压力".to_string(),
                status: dispatch_pressure_status.to_string(),
                triggered: dispatch_pressure_triggered,
                recommendation: dispatch_pressure_recommendation.to_string(),
                evidence: json!({
                    "pendingRunningJobs": pending_running_jobs.max(0),
                    "pendingDlqCount": signal.pending_dlq_count.max(0),
                    "avgDispatchAttempts": signal.avg_dispatch_attempts.max(0.0),
                    "p95LatencyMs": signal.p95_latency_ms.max(0.0),
                    "dispatchFailedRatio": failed_ratio_window.max(0.0),
                    "dispatchFailedRatioWindow": failed_ratio_window.max(0.0),
                    "dispatchFailedRatioLifetime": failed_ratio_lifetime.max(0.0),
                    "dispatchFailedRatioSampleCompleted": window_completed,
                    "dispatchFailedRatioSampleMinCompleted": SPLIT_READINESS_PRESSURE_FAILED_RATIO_MIN_DISPATCHED,
                    "failedRatioComparison": failed_ratio_comparison,
                    "metrics": {
                        "dispatchedTotal": dispatch_metrics.dispatched_total,
                        "failedTotal": dispatch_metrics.failed_total,
                        "retryableFailedTotal": dispatch_metrics.retryable_failed_total
                    },
                    "thresholds": {
                        "pendingRunningJobs": SPLIT_READINESS_PRESSURE_PENDING_RUNNING_THRESHOLD,
                        "pendingDlqCount": SPLIT_READINESS_PRESSURE_PENDING_DLQ_THRESHOLD,
                        "avgDispatchAttempts": SPLIT_READINESS_PRESSURE_AVG_ATTEMPTS_THRESHOLD,
                        "p95LatencyMs": SPLIT_READINESS_PRESSURE_P95_MS_THRESHOLD,
                        "dispatchFailedRatio": SPLIT_READINESS_PRESSURE_FAILED_RATIO_THRESHOLD
                    }
                }),
            },
            OpsServiceSplitThresholdItem {
                key: "payment_compliance_isolation".to_string(),
                title: "支付/合规独立部署域要求".to_string(),
                status: payment_compliance_status.to_string(),
                triggered: payment_compliance_triggered,
                recommendation: payment_compliance_recommendation.to_string(),
                evidence: json!({
                    "manualInputRequired": payment_compliance_required.is_none(),
                    "paymentComplianceRequired": payment_compliance_required,
                    "source": "compliance_review",
                    "reviewNote": compliance_review.as_ref().map(|v| v.review_note.clone()).unwrap_or_default(),
                    "updatedBy": compliance_review.as_ref().map(|v| v.updated_by as u64),
                    "updatedAt": compliance_review.as_ref().map(|v| v.updated_at.to_rfc3339()),
                    "reviewAgeHours": review_age_hours,
                    "stale": review_stale,
                    "staleThresholdHours": SPLIT_REVIEW_STALE_THRESHOLD_HOURS,
                    "note": "该阈值由人工评审录入，不由运行时指标自动判定"
                }),
            },
            OpsServiceSplitThresholdItem {
                key: "ws_online_scale_limit".to_string(),
                title: "WS 在线规模阈值".to_string(),
                status: ws_scale_status.to_string(),
                triggered: ws_scale_triggered,
                recommendation: ws_scale_recommendation.to_string(),
                evidence: json!({
                    "runningSessions": running_sessions.max(0),
                    "recentMessages10m": recent_messages_10m.max(0),
                    "thresholds": {
                        "runningSessions": SPLIT_READINESS_WS_RUNNING_SESSIONS_THRESHOLD,
                        "recentMessages10m": SPLIT_READINESS_WS_MESSAGES_10M_THRESHOLD
                    }
                }),
            },
        ];

        let review_required = thresholds.iter().any(|item| item.triggered);
        let overall_status = if review_required {
            "review_required"
        } else {
            "hold"
        };
        let next_step = if review_required {
            "触发 R6 架构评审：结合 ADR-0002 决定是否继续服务拆分。"
        } else {
            "维持当前服务拓扑，按周复核阈值信号。"
        };

        Ok(GetOpsServiceSplitReadinessOutput {
            generated_at_ms,
            overall_status: overall_status.to_string(),
            next_step: next_step.to_string(),
            thresholds,
        })
    }

    pub async fn get_ops_metrics_dictionary(
        &self,
        user: &User,
    ) -> Result<GetOpsMetricsDictionaryOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::ObservabilityRead)
            .await?;
        let items = build_ops_metrics_dictionary_items();
        Ok(GetOpsMetricsDictionaryOutput {
            version: "v1".to_string(),
            dictionary_revision: build_ops_metrics_dictionary_revision(&items),
            generated_at_ms: now_millis(),
            items,
        })
    }

    pub async fn get_ops_observability_slo_snapshot(
        &self,
        user: &User,
    ) -> Result<GetOpsSloSnapshotOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::ObservabilityRead)
            .await?;
        let now_ms = now_millis();
        let row: Option<OpsObservabilityConfigRow> = sqlx::query_as(
            r#"
            SELECT thresholds_json, anomaly_state_json, updated_by, updated_at
            FROM ops_observability_configs
            WHERE singleton_id = 1
            "#,
        )
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
        let signal = self.load_recent_judge_signal().await?;
        let signal_snapshot = build_ops_slo_signal_snapshot(signal);
        let specs = rule_specs();
        let alert_keys: Vec<String> = specs
            .iter()
            .map(|spec| spec.alert_key.to_string())
            .collect();
        let previous_rows: Vec<OpsAlertStateByKeyRow> = sqlx::query_as(
            r#"
            SELECT alert_key, is_active, last_emitted_status
            FROM ops_alert_states
            WHERE alert_key = ANY($1::text[])
            "#,
        )
        .bind(&alert_keys)
        .fetch_all(&self.pool)
        .await?;
        let previous_by_key: HashMap<String, OpsAlertStateRow> = previous_rows
            .into_iter()
            .map(|row| {
                (
                    row.alert_key,
                    OpsAlertStateRow {
                        is_active: row.is_active,
                        last_emitted_status: row.last_emitted_status,
                    },
                )
            })
            .collect();

        let mut rules = Vec::with_capacity(specs.len());
        for spec in specs {
            let evaluated = evaluate_alert_for_rule(spec, &thresholds, signal);
            let previous = previous_by_key.get(spec.alert_key);
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
                last_emitted_status: previous.map(|v| v.last_emitted_status.clone()),
                message: evaluated.message,
                metrics: evaluated.metrics,
            });
        }

        Ok(GetOpsSloSnapshotOutput {
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
        self.ensure_ops_permission(user, OpsPermission::ObservabilityRead)
            .await?;
        let row: Option<OpsObservabilityConfigRow> = sqlx::query_as(
            r#"
            SELECT thresholds_json, anomaly_state_json, updated_by, updated_at
            FROM ops_observability_configs
            WHERE singleton_id = 1
            "#,
        )
        .fetch_optional(&self.pool)
        .await?;
        Ok(build_output(row, now_millis()))
    }

    pub async fn upsert_ops_observability_thresholds(
        &self,
        user: &User,
        input: OpsObservabilityThresholds,
    ) -> Result<GetOpsObservabilityConfigOutput, AppError> {
        self.upsert_ops_observability_thresholds_with_meta(
            user,
            input,
            UpsertOpsObservabilityThresholdsMeta::default(),
        )
        .await
    }

    pub async fn upsert_ops_observability_thresholds_with_meta(
        &self,
        user: &User,
        input: OpsObservabilityThresholds,
        meta: UpsertOpsObservabilityThresholdsMeta<'_>,
    ) -> Result<GetOpsObservabilityConfigOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::ObservabilityManage)
            .await?;
        let thresholds = normalize_thresholds(input);
        let normalized_request_id = normalize_ops_observability_audit_request_id(meta.request_id);
        let thresholds_json = serde_json::to_value(&thresholds)
            .context("serialize observability thresholds failed")?;
        let mut tx = self.pool.begin().await?;
        acquire_ops_observability_revision_lock(&mut tx).await?;
        let current_row: Option<OpsObservabilityConfigRow> = sqlx::query_as(
            r#"
            SELECT thresholds_json, anomaly_state_json, updated_by, updated_at
            FROM ops_observability_configs
            WHERE singleton_id = 1
            FOR UPDATE
            "#,
        )
        .fetch_optional(&mut *tx)
        .await?;
        let current_revision = format_ops_observability_config_revision(
            current_row.as_ref().map(|row| row.updated_at),
        );
        ensure_expected_ops_observability_revision(
            meta.expected_config_revision,
            &current_revision,
            meta.require_if_match,
        )?;
        let before_thresholds = current_row
            .as_ref()
            .map(|row| parse_thresholds(row.thresholds_json.clone()))
            .unwrap_or_default();
        let before_thresholds_json = serde_json::to_value(&before_thresholds)
            .context("serialize before observability thresholds failed")?;
        sqlx::query(
            r#"
            INSERT INTO ops_observability_configs(
                singleton_id, thresholds_json, anomaly_state_json, updated_by, created_at, updated_at
            )
            VALUES (1, $1, '{}'::jsonb, $2, NOW(), NOW())
            ON CONFLICT (singleton_id)
            DO UPDATE
            SET thresholds_json = EXCLUDED.thresholds_json,
                updated_by = EXCLUDED.updated_by,
                updated_at = NOW()
            "#,
        )
        .bind(thresholds_json)
        .bind(user.id)
        .execute(&mut *tx)
        .await?;
        let after_row: OpsObservabilityConfigRow = sqlx::query_as(
            r#"
            SELECT thresholds_json, anomaly_state_json, updated_by, updated_at
            FROM ops_observability_configs
            WHERE singleton_id = 1
            "#,
        )
        .fetch_one(&mut *tx)
        .await?;
        let after_thresholds = parse_thresholds(after_row.thresholds_json.clone());
        let after_thresholds_json = serde_json::to_value(&after_thresholds)
            .context("serialize after observability thresholds failed")?;
        sqlx::query(
            r#"
            INSERT INTO ops_observability_threshold_audits(
                singleton_id,
                before_thresholds_json,
                after_thresholds_json,
                updated_by,
                request_id,
                created_at
            )
            VALUES (1, $1, $2, $3, $4, NOW())
            "#,
        )
        .bind(before_thresholds_json)
        .bind(after_thresholds_json)
        .bind(user.id)
        .bind(normalized_request_id)
        .execute(&mut *tx)
        .await?;
        tx.commit().await?;
        Ok(build_output(Some(after_row), now_millis()))
    }

    pub async fn upsert_ops_observability_anomaly_state(
        &self,
        user: &User,
        input: UpdateOpsObservabilityAnomalyStateInput,
    ) -> Result<GetOpsObservabilityConfigOutput, AppError> {
        self.upsert_ops_observability_anomaly_state_with_meta(
            user,
            input,
            UpsertOpsObservabilityAnomalyStateMeta::default(),
        )
        .await
    }

    pub async fn upsert_ops_observability_anomaly_state_with_meta(
        &self,
        user: &User,
        input: UpdateOpsObservabilityAnomalyStateInput,
        meta: UpsertOpsObservabilityAnomalyStateMeta<'_>,
    ) -> Result<GetOpsObservabilityConfigOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::ObservabilityManage)
            .await?;
        let now_ms = now_millis();
        let normalized_anomaly_state =
            normalize_anomaly_state_with_stats(input.anomaly_state, now_ms);
        let anomaly_state_json = serde_json::to_value(&normalized_anomaly_state.state)
            .context("serialize observability anomaly state failed")?;
        let normalized_request_id = normalize_ops_observability_audit_request_id(meta.request_id);
        let default_thresholds_json =
            serde_json::to_value(OpsObservabilityThresholds::default())
                .context("serialize default observability thresholds failed")?;
        let mut tx = self.pool.begin().await?;
        acquire_ops_observability_revision_lock(&mut tx).await?;
        let current_row: Option<OpsObservabilityConfigRow> = sqlx::query_as(
            r#"
            SELECT thresholds_json, anomaly_state_json, updated_by, updated_at
            FROM ops_observability_configs
            WHERE singleton_id = 1
            FOR UPDATE
            "#,
        )
        .fetch_optional(&mut *tx)
        .await?;
        let current_revision = format_ops_observability_config_revision(
            current_row.as_ref().map(|row| row.updated_at),
        );
        ensure_expected_ops_observability_revision(
            meta.expected_config_revision,
            &current_revision,
            meta.require_if_match,
        )?;
        let before_anomaly_state = current_row
            .as_ref()
            .map(|row| parse_anomaly_state(row.anomaly_state_json.clone(), now_ms))
            .unwrap_or_default();
        let before_anomaly_state_json = serde_json::to_value(&before_anomaly_state)
            .context("serialize before observability anomaly state failed")?;
        sqlx::query(
            r#"
            INSERT INTO ops_observability_configs(
                singleton_id, thresholds_json, anomaly_state_json, updated_by, created_at, updated_at
            )
            VALUES (1, $1, $2, $3, NOW(), NOW())
            ON CONFLICT (singleton_id)
            DO UPDATE
            SET anomaly_state_json = EXCLUDED.anomaly_state_json,
                updated_by = EXCLUDED.updated_by,
                updated_at = NOW()
            "#,
        )
        .bind(default_thresholds_json)
        .bind(anomaly_state_json)
        .bind(user.id)
        .execute(&mut *tx)
        .await?;
        let after_row: OpsObservabilityConfigRow = sqlx::query_as(
            r#"
            SELECT thresholds_json, anomaly_state_json, updated_by, updated_at
            FROM ops_observability_configs
            WHERE singleton_id = 1
            "#,
        )
        .fetch_one(&mut *tx)
        .await?;
        let after_anomaly_state = parse_anomaly_state(after_row.anomaly_state_json.clone(), now_ms);
        let after_anomaly_state_json = serde_json::to_value(&after_anomaly_state)
            .context("serialize after observability anomaly state failed")?;
        sqlx::query(
            r#"
            INSERT INTO ops_observability_anomaly_state_audits(
                singleton_id,
                before_anomaly_state_json,
                after_anomaly_state_json,
                updated_by,
                request_id,
                input_item_count,
                retained_item_count,
                dropped_item_count,
                created_at
            )
            VALUES (1, $1, $2, $3, $4, $5, $6, $7, NOW())
            "#,
        )
        .bind(before_anomaly_state_json)
        .bind(after_anomaly_state_json)
        .bind(user.id)
        .bind(normalized_request_id)
        .bind(normalized_anomaly_state.input_count as i64)
        .bind(normalized_anomaly_state.retained_count as i64)
        .bind(normalized_anomaly_state.dropped_count as i64)
        .execute(&mut *tx)
        .await?;
        tx.commit().await?;
        Ok(build_output(Some(after_row), now_ms))
    }

    pub async fn apply_ops_observability_anomaly_action(
        &self,
        user: &User,
        input: ApplyOpsObservabilityAnomalyActionInput,
    ) -> Result<GetOpsObservabilityConfigOutput, AppError> {
        self.apply_ops_observability_anomaly_action_with_meta(
            user,
            input,
            ApplyOpsObservabilityAnomalyActionMeta::default(),
        )
        .await
    }

    pub async fn apply_ops_observability_anomaly_action_with_meta(
        &self,
        user: &User,
        input: ApplyOpsObservabilityAnomalyActionInput,
        meta: ApplyOpsObservabilityAnomalyActionMeta<'_>,
    ) -> Result<GetOpsObservabilityConfigOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::ObservabilityManage)
            .await?;
        let now_ms = now_millis();
        let normalized_input = normalize_anomaly_action_input(&input)?;
        let normalized_request_id = normalize_ops_observability_audit_request_id(meta.request_id);
        let default_thresholds_json =
            serde_json::to_value(OpsObservabilityThresholds::default())
                .context("serialize default observability thresholds failed")?;
        let mut tx = self.pool.begin().await?;
        sqlx::query(
            r#"
            INSERT INTO ops_observability_configs(
                singleton_id, thresholds_json, anomaly_state_json, updated_by, created_at, updated_at
            )
            VALUES (1, $1, '{}'::jsonb, $2, NOW(), NOW())
            ON CONFLICT (singleton_id) DO NOTHING
            "#,
        )
        .bind(default_thresholds_json)
        .bind(user.id)
        .execute(&mut *tx)
        .await?;
        let current_row: OpsObservabilityConfigRow = sqlx::query_as(
            r#"
            SELECT thresholds_json, anomaly_state_json, updated_by, updated_at
            FROM ops_observability_configs
            WHERE singleton_id = 1
            FOR UPDATE
            "#,
        )
        .fetch_one(&mut *tx)
        .await?;
        let existing = parse_anomaly_state(current_row.anomaly_state_json.clone(), now_ms);
        let before_state = existing.get(&normalized_input.alert_key).cloned();
        let anomaly_state = apply_anomaly_action(existing, &input, now_ms)?;
        let anomaly_state_json = serde_json::to_value(&anomaly_state)
            .context("serialize observability anomaly action state failed")?;
        sqlx::query(
            r#"
            UPDATE ops_observability_configs
            SET anomaly_state_json = $1,
                updated_by = $2,
                updated_at = NOW()
            WHERE singleton_id = 1
            "#,
        )
        .bind(anomaly_state_json)
        .bind(user.id)
        .execute(&mut *tx)
        .await?;
        let after_row: OpsObservabilityConfigRow = sqlx::query_as(
            r#"
            SELECT thresholds_json, anomaly_state_json, updated_by, updated_at
            FROM ops_observability_configs
            WHERE singleton_id = 1
            "#,
        )
        .fetch_one(&mut *tx)
        .await?;
        let after_anomaly_state = parse_anomaly_state(after_row.anomaly_state_json.clone(), now_ms);
        let after_state = after_anomaly_state
            .get(&normalized_input.alert_key)
            .cloned();
        let before_state_json = serde_json::to_value(before_state)
            .context("serialize before observability anomaly action state failed")?;
        let after_state_json = serde_json::to_value(after_state)
            .context("serialize after observability anomaly action state failed")?;
        let suppress_minutes = if normalized_input.action == OPS_ANOMALY_ACTION_SUPPRESS {
            Some(normalized_input.suppress_minutes)
        } else {
            None
        };
        sqlx::query(
            r#"
            INSERT INTO ops_observability_anomaly_action_audits(
                singleton_id,
                alert_key,
                action,
                suppress_minutes,
                before_state_json,
                after_state_json,
                updated_by,
                request_id,
                created_at
            )
            VALUES (1, $1, $2, $3, $4, $5, $6, $7, NOW())
            "#,
        )
        .bind(normalized_input.alert_key.as_str())
        .bind(normalized_input.action)
        .bind(suppress_minutes)
        .bind(before_state_json)
        .bind(after_state_json)
        .bind(user.id)
        .bind(normalized_request_id)
        .execute(&mut *tx)
        .await?;
        tx.commit().await?;
        Ok(build_output(Some(after_row), now_ms))
    }

    pub async fn list_ops_alert_notifications(
        &self,
        user: &User,
        query: ListOpsAlertNotificationsQuery,
    ) -> Result<ListOpsAlertNotificationsOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::ObservabilityRead)
            .await?;
        let status = normalize_alert_status_filter(query.status)?;
        let limit = normalize_alert_limit(query.limit);
        let offset = normalize_alert_offset(query.offset);

        let total: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)
            FROM ops_alert_notifications
            WHERE ($1::text IS NULL OR alert_status = $1)
            "#,
        )
        .bind(status.as_deref())
        .fetch_one(&self.pool)
        .await?;
        let rows: Vec<OpsAlertNotificationRow> = sqlx::query_as(
            r#"
            SELECT
                id, alert_key, rule_type, severity, alert_status,
                title, message, metrics_json, recipients_json,
                delivery_status, error_message, delivered_at, created_at, updated_at
            FROM ops_alert_notifications
            WHERE ($1::text IS NULL OR alert_status = $1)
            ORDER BY created_at DESC, id DESC
            LIMIT $2 OFFSET $3
            "#,
        )
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

    async fn list_observability_eval_scopes(
        &self,
    ) -> Result<Vec<OpsObservabilityEvalScopeRow>, AppError> {
        let rows: Vec<OpsObservabilityEvalScopeRow> = sqlx::query_as(
            r#"
            SELECT
                1::bigint AS scope_id,
                COALESCE(c.thresholds_json, '{}'::jsonb) AS thresholds_json,
                COALESCE(c.anomaly_state_json, '{}'::jsonb) AS anomaly_state_json
            FROM (SELECT 1) AS scope
            LEFT JOIN ops_observability_configs c ON c.singleton_id = 1
            "#,
        )
        .fetch_all(&self.pool)
        .await?;
        Ok(rows)
    }

    async fn load_recent_judge_signal(&self) -> Result<OpsRecentJudgeSignal, AppError> {
        let row: OpsRecentJudgeSignalRow = sqlx::query_as(
            r#"
            SELECT
                COUNT(1) FILTER (
                    WHERE status = 'succeeded'
                      AND updated_at >= NOW() - ($1::bigint * INTERVAL '1 minute')
                )::bigint AS success_count,
                COUNT(1) FILTER (
                    WHERE status = 'failed'
                      AND updated_at >= NOW() - ($1::bigint * INTERVAL '1 minute')
                )::bigint AS failed_count,
                COALESCE(AVG(dispatch_attempts::double precision) FILTER (
                    WHERE created_at >= NOW() - ($1::bigint * INTERVAL '1 minute')
                ), 0)::double precision AS avg_dispatch_attempts,
                COALESCE(PERCENTILE_CONT(0.95) WITHIN GROUP (
                    ORDER BY EXTRACT(EPOCH FROM (COALESCE(updated_at, NOW()) - created_at)) * 1000
                ) FILTER (
                    WHERE created_at >= NOW() - ($1::bigint * INTERVAL '1 minute')
                      AND status IN ('succeeded', 'failed')
                ), 0)::double precision AS p95_latency_ms
            FROM judge_final_jobs
            "#,
        )
        .bind(OPS_ALERT_EVAL_WINDOW_MINUTES)
        .fetch_one(&self.pool)
        .await?;
        let pending_dlq_count: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)::bigint
            FROM kafka_dlq_events
            WHERE status = 'pending'
            "#,
        )
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

    async fn list_alert_recipients(&self) -> Result<Vec<u64>, AppError> {
        let owners: Vec<i64> = sqlx::query_scalar(
            r#"
            SELECT owner_user_id
            FROM platform_admin_owners
            WHERE singleton_key = TRUE
            "#,
        )
        .fetch_all(&self.pool)
        .await?;
        let role_users: Vec<i64> = sqlx::query_scalar(
            r#"
            SELECT user_id
            FROM platform_user_roles
            WHERE role IN ('ops_admin', 'ops_reviewer', 'ops_viewer', 'platform_role_admin')
            "#,
        )
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
        alert_key: &str,
    ) -> Result<Option<String>, AppError> {
        let row: Option<String> = sqlx::query_scalar(
            r#"
            SELECT delivery_status
            FROM ops_alert_notifications
            WHERE alert_key = $1
            ORDER BY id DESC
            LIMIT 1
            "#,
        )
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
                alert_key, rule_type, severity, alert_status,
                title, message, metrics_json, recipients_json,
                delivery_status, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW())
            RETURNING id
            "#,
        )
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
        plan: EmitAlertPlan,
        recipients: &[u64],
    ) -> Result<(), AppError> {
        let mut tx = self.pool.begin().await?;
        let recipients_json = serde_json::to_value(recipients).context("serialize recipients")?;
        let notification_id: i64 = sqlx::query_scalar(
            r#"
            INSERT INTO ops_alert_notifications(
                alert_key, rule_type, severity, alert_status,
                title, message, metrics_json, recipients_json,
                delivery_status, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW())
            RETURNING id
            "#,
        )
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
                alert_key, is_active, last_emitted_status, last_changed_at, created_at, updated_at
            )
            VALUES ($1, $2, $3, NOW(), NOW(), NOW())
            ON CONFLICT (alert_key)
            DO UPDATE SET
                is_active = EXCLUDED.is_active,
                last_emitted_status = EXCLUDED.last_emitted_status,
                last_changed_at = NOW(),
                updated_at = NOW()
            "#,
        )
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
            WHERE alert_key = $1
            "#,
        )
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
        self.emit_observability_alert(plan, recipients).await
    }

    pub async fn evaluate_ops_observability_alerts_once(
        &self,
    ) -> Result<OpsAlertEvalReport, AppError> {
        let now_ms = now_millis();
        let mut report = OpsAlertEvalReport::default();
        let rows = self.list_observability_eval_scopes().await?;
        report.scopes_scanned = rows.len() as u64;
        for row in rows {
            let _scope_id = row.scope_id;
            let thresholds = parse_thresholds(row.thresholds_json.clone());
            let anomaly_state = parse_anomaly_state(row.anomaly_state_json.clone(), now_ms);
            let signal = self.load_recent_judge_signal().await?;
            let recipients = self.list_alert_recipients().await?;
            for spec in rule_specs() {
                let evaluated = evaluate_alert_for_rule(spec, &thresholds, signal);
                self.process_single_alert_transition(
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

    pub async fn evaluate_ops_observability_alerts_by_ops(
        &self,
        user: &User,
    ) -> Result<OpsAlertEvalReport, AppError> {
        self.ensure_ops_permission(user, OpsPermission::ObservabilityManage)
            .await?;
        let now_ms = now_millis();
        let row: Option<OpsObservabilityConfigRow> = sqlx::query_as(
            r#"
            SELECT thresholds_json, anomaly_state_json, updated_by, updated_at
            FROM ops_observability_configs
            WHERE singleton_id = 1
            "#,
        )
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
        let mut report = OpsAlertEvalReport {
            scopes_scanned: 1,
            ..OpsAlertEvalReport::default()
        };
        let signal = self.load_recent_judge_signal().await?;
        let recipients = self.list_alert_recipients().await?;
        for spec in rule_specs() {
            let evaluated = evaluate_alert_for_rule(spec, &thresholds, signal);
            self.process_single_alert_transition(
                evaluated,
                &anomaly_state,
                now_ms,
                &recipients,
                &mut report,
            )
            .await?;
        }
        Ok(report)
    }

    pub async fn preview_ops_observability_alerts_by_ops(
        &self,
        user: &User,
    ) -> Result<OpsAlertEvalReport, AppError> {
        self.ensure_ops_permission(user, OpsPermission::ObservabilityRead)
            .await?;
        let now_ms = now_millis();
        let row: Option<OpsObservabilityConfigRow> = sqlx::query_as(
            r#"
            SELECT thresholds_json, anomaly_state_json, updated_by, updated_at
            FROM ops_observability_configs
            WHERE singleton_id = 1
            "#,
        )
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
        let mut report = OpsAlertEvalReport {
            scopes_scanned: 1,
            ..OpsAlertEvalReport::default()
        };
        let signal = self.load_recent_judge_signal().await?;
        for spec in rule_specs() {
            let evaluated = evaluate_alert_for_rule(spec, &thresholds, signal);
            let previous: Option<OpsAlertStateRow> = sqlx::query_as(
                r#"
                SELECT is_active, last_emitted_status
                FROM ops_alert_states
                WHERE alert_key = $1
                "#,
            )
            .bind(&evaluated.alert_key)
            .fetch_optional(&self.pool)
            .await?;
            let suppression_state = anomaly_state.get(&evaluated.alert_key);
            let Some(plan) = build_emit_plan(evaluated, previous, suppression_state, now_ms) else {
                continue;
            };
            match plan.status {
                ALERT_STATUS_RAISED => report.alerts_raised += 1,
                ALERT_STATUS_CLEARED => report.alerts_cleared += 1,
                ALERT_STATUS_SUPPRESSED => report.alerts_suppressed += 1,
                _ => {}
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
                .find_existing_bridge_notification_delivery_status(&alert_key)
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

            let recipients = self.list_alert_recipients().await?;
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
    use tokio::sync::Barrier;

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

    async fn seed_split_readiness_session(state: &AppState, owner_user_id: i64) -> Result<i64> {
        let topic_id: i64 = sqlx::query_scalar(
            r#"
            INSERT INTO debate_topics(
                title, description, category, stance_pro, stance_con, is_active, created_by
            )
            VALUES ('split-readiness-topic', 'desc', 'game', 'pro', 'con', true, $1)
            RETURNING id
            "#,
        )
        .bind(owner_user_id)
        .fetch_one(&state.pool)
        .await?;
        let session_id: i64 = sqlx::query_scalar(
            r#"
            INSERT INTO debate_sessions(
                topic_id, status, scheduled_start_at, actual_start_at, end_at, max_participants_per_side
            )
            VALUES (
                $1, 'closed',
                NOW() - INTERVAL '40 minutes',
                NOW() - INTERVAL '35 minutes',
                NOW() - INTERVAL '5 minutes',
                500
            )
            RETURNING id
            "#,
        )
        .bind(topic_id)
        .fetch_one(&state.pool)
        .await?;
        Ok(session_id)
    }

    async fn seed_split_readiness_final_jobs(
        state: &AppState,
        session_id: i64,
        failed_count: usize,
        succeeded_count: usize,
    ) -> Result<()> {
        for idx in 0..failed_count {
            sqlx::query(
                r#"
                INSERT INTO judge_final_jobs(
                    session_id, rejudge_run_no, phase_start_no, phase_end_no,
                    status, trace_id, idempotency_key, rubric_version, judge_policy_version,
                    topic_domain, dispatch_attempts, created_at, updated_at
                )
                VALUES (
                    $1, $2, 1, 1,
                    'failed',
                    $3,
                    $4,
                    'v3', 'v3-default', 'default',
                    1,
                    NOW() - INTERVAL '2 minutes',
                    NOW() - INTERVAL '1 minutes'
                )
                "#,
            )
            .bind(session_id)
            .bind((idx as i32) + 1)
            .bind(format!("split-readiness-failed-{session_id}-{idx}"))
            .bind(format!("split_readiness:failed:{session_id}:{idx}"))
            .execute(&state.pool)
            .await?;
        }
        for idx in 0..succeeded_count {
            sqlx::query(
                r#"
                INSERT INTO judge_final_jobs(
                    session_id, rejudge_run_no, phase_start_no, phase_end_no,
                    status, trace_id, idempotency_key, rubric_version, judge_policy_version,
                    topic_domain, dispatch_attempts, created_at, updated_at
                )
                VALUES (
                    $1, $2, 1, 1,
                    'succeeded',
                    $3,
                    $4,
                    'v3', 'v3-default', 'default',
                    1,
                    NOW() - INTERVAL '2 minutes',
                    NOW() - INTERVAL '1 minutes'
                )
                "#,
            )
            .bind(session_id)
            .bind((failed_count as i32) + (idx as i32) + 1)
            .bind(format!("split-readiness-succeeded-{session_id}-{idx}"))
            .bind(format!("split_readiness:succeeded:{session_id}:{idx}"))
            .execute(&state.pool)
            .await?;
        }
        Ok(())
    }

    #[tokio::test]
    async fn get_ops_observability_config_should_return_defaults_when_missing() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let ret = state.get_ops_observability_config(&owner).await?;
        assert_eq!(ret.thresholds.low_success_rate_threshold, 80.0);
        assert!(ret.anomaly_state.is_empty());
        assert_eq!(ret.config_revision, OPS_OBSERVABILITY_CONFIG_REVISION_EMPTY);
        assert!(ret.updated_by.is_none());
        assert!(ret.updated_at.is_none());
        Ok(())
    }

    #[test]
    fn build_output_should_fallback_to_none_when_updated_by_out_of_range() {
        let row = OpsObservabilityConfigRow {
            thresholds_json: serde_json::json!({}),
            anomaly_state_json: serde_json::json!({}),
            updated_by: -1,
            updated_at: Utc::now(),
        };
        let ret = build_output(Some(row), now_millis());
        assert!(ret.updated_by.is_none());
    }

    #[tokio::test]
    async fn upsert_ops_observability_config_should_allow_ops_reviewer_manage_permission(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let reviewer = state
            .find_user_by_id(2)
            .await?
            .expect("reviewer should exist");
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                reviewer.id as u64,
                UpsertOpsRoleInput {
                    role: "ops_reviewer".to_string(),
                },
            )
            .await?;

        let threshold_ret = state
            .upsert_ops_observability_thresholds(
                &reviewer,
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
        assert_eq!(threshold_ret.updated_by, Some(reviewer.id as u64));
        assert_eq!(threshold_ret.thresholds.low_success_rate_threshold, 75.0);
        assert_ne!(
            threshold_ret.config_revision,
            OPS_OBSERVABILITY_CONFIG_REVISION_EMPTY
        );

        let state_ret = state
            .upsert_ops_observability_anomaly_state(
                &reviewer,
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
        assert_eq!(state_ret.updated_by, Some(reviewer.id as u64));
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
    async fn upsert_ops_observability_config_should_reject_ops_viewer_manage_permission(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
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

        let err = state
            .upsert_ops_observability_thresholds(&viewer, OpsObservabilityThresholds::default())
            .await
            .expect_err("ops_viewer should not manage observability config");
        match err {
            AppError::DebateConflict(msg) => {
                assert!(msg.starts_with("ops_permission_denied:observability_manage:"));
            }
            other => panic!("unexpected error: {}", other),
        }
        Ok(())
    }

    #[tokio::test]
    async fn upsert_ops_observability_config_should_reject_user_without_ops_role() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
        let user = state.find_user_by_id(3).await?.expect("user should exist");
        let err = state
            .upsert_ops_observability_thresholds(&user, OpsObservabilityThresholds::default())
            .await
            .expect_err("missing ops role should be rejected");
        match err {
            AppError::DebateConflict(msg) => {
                assert!(msg.starts_with("ops_permission_denied:observability_manage:"));
            }
            other => panic!("unexpected error: {}", other),
        }
        Ok(())
    }

    #[tokio::test]
    async fn upsert_ops_observability_thresholds_with_meta_should_require_if_match_when_enabled(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let err = state
            .upsert_ops_observability_thresholds_with_meta(
                &owner,
                OpsObservabilityThresholds::default(),
                UpsertOpsObservabilityThresholdsMeta {
                    expected_config_revision: None,
                    require_if_match: true,
                    request_id: Some("obs-thresholds-require-if-match"),
                },
            )
            .await
            .expect_err("missing if-match should be rejected");
        match err {
            AppError::DebateError(code) => {
                assert_eq!(code, OPS_OBSERVABILITY_IF_MATCH_REQUIRED_CODE);
            }
            other => panic!("unexpected error: {}", other),
        }
        Ok(())
    }

    #[tokio::test]
    async fn upsert_ops_observability_thresholds_with_meta_should_reject_stale_revision(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        state
            .upsert_ops_observability_thresholds(
                &owner,
                OpsObservabilityThresholds {
                    low_success_rate_threshold: 70.0,
                    high_retry_threshold: 1.1,
                    high_coalesced_threshold: 2.2,
                    high_db_latency_threshold_ms: 1400,
                    low_cache_hit_rate_threshold: 30.0,
                    min_request_for_cache_hit_check: 40,
                },
            )
            .await?;
        let err = state
            .upsert_ops_observability_thresholds_with_meta(
                &owner,
                OpsObservabilityThresholds::default(),
                UpsertOpsObservabilityThresholdsMeta {
                    expected_config_revision: Some(OPS_OBSERVABILITY_CONFIG_REVISION_EMPTY),
                    require_if_match: true,
                    request_id: Some("obs-thresholds-stale"),
                },
            )
            .await
            .expect_err("stale revision should be rejected");
        match err {
            AppError::DebateConflict(code) => {
                assert_eq!(code, OPS_OBSERVABILITY_REVISION_CONFLICT_CODE);
            }
            other => panic!("unexpected error: {}", other),
        }
        Ok(())
    }

    #[tokio::test]
    async fn upsert_ops_observability_thresholds_with_meta_should_persist_audit_diff() -> Result<()>
    {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        state
            .upsert_ops_observability_thresholds(
                &owner,
                OpsObservabilityThresholds {
                    low_success_rate_threshold: 70.0,
                    high_retry_threshold: 1.1,
                    high_coalesced_threshold: 2.2,
                    high_db_latency_threshold_ms: 1400,
                    low_cache_hit_rate_threshold: 30.0,
                    min_request_for_cache_hit_check: 40,
                },
            )
            .await?;
        let config_before = state.get_ops_observability_config(&owner).await?;
        let ret = state
            .upsert_ops_observability_thresholds_with_meta(
                &owner,
                OpsObservabilityThresholds {
                    low_success_rate_threshold: 85.0,
                    high_retry_threshold: 1.6,
                    high_coalesced_threshold: 3.2,
                    high_db_latency_threshold_ms: 1800,
                    low_cache_hit_rate_threshold: 18.0,
                    min_request_for_cache_hit_check: 22,
                },
                UpsertOpsObservabilityThresholdsMeta {
                    expected_config_revision: Some(config_before.config_revision.as_str()),
                    require_if_match: true,
                    request_id: Some("obs-thresholds-audit-diff"),
                },
            )
            .await?;
        assert_eq!(ret.thresholds.low_success_rate_threshold, 85.0);

        let audit_row: (Option<String>, Value, Value) = sqlx::query_as(
            r#"
            SELECT request_id, before_thresholds_json, after_thresholds_json
            FROM ops_observability_threshold_audits
            ORDER BY id DESC
            LIMIT 1
            "#,
        )
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(audit_row.0.as_deref(), Some("obs-thresholds-audit-diff"));
        let before_thresholds = parse_thresholds(audit_row.1);
        let after_thresholds = parse_thresholds(audit_row.2);
        assert_eq!(before_thresholds.low_success_rate_threshold, 70.0);
        assert_eq!(after_thresholds.low_success_rate_threshold, 85.0);
        Ok(())
    }

    #[test]
    fn normalize_anomaly_state_with_stats_should_keep_deterministic_subset_under_overflow() {
        let now_ms = now_millis();
        let mut input = HashMap::new();
        for idx in (0..(MAX_STATE_ITEM_COUNT + 5)).rev() {
            input.insert(
                format!("rule_{idx:04}"),
                OpsObservabilityAnomalyStateValue {
                    acknowledged_at_ms: 0,
                    suppress_until_ms: now_ms + 300_000,
                },
            );
        }
        let normalized = normalize_anomaly_state_with_stats(input, now_ms);
        assert_eq!(normalized.input_count, MAX_STATE_ITEM_COUNT + 5);
        assert_eq!(normalized.retained_count, MAX_STATE_ITEM_COUNT);
        assert_eq!(normalized.dropped_count, 5);
        assert!(normalized.state.contains_key("rule_0000"));
        assert!(normalized
            .state
            .contains_key(format!("rule_{:04}", MAX_STATE_ITEM_COUNT - 1).as_str()));
        assert!(!normalized
            .state
            .contains_key(format!("rule_{:04}", MAX_STATE_ITEM_COUNT).as_str()));
    }

    #[tokio::test]
    async fn upsert_ops_observability_anomaly_state_with_meta_should_require_if_match_when_enabled(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let err = state
            .upsert_ops_observability_anomaly_state_with_meta(
                &owner,
                UpdateOpsObservabilityAnomalyStateInput {
                    anomaly_state: HashMap::from([(
                        OPS_ALERT_RULE_HIGH_RETRY.to_string(),
                        OpsObservabilityAnomalyStateValue {
                            acknowledged_at_ms: 0,
                            suppress_until_ms: now_millis() + 300_000,
                        },
                    )]),
                },
                UpsertOpsObservabilityAnomalyStateMeta {
                    expected_config_revision: None,
                    require_if_match: true,
                    request_id: Some("obs-anomaly-require-if-match"),
                },
            )
            .await
            .expect_err("missing if-match should be rejected");
        match err {
            AppError::DebateError(code) => {
                assert_eq!(code, OPS_OBSERVABILITY_IF_MATCH_REQUIRED_CODE);
            }
            other => panic!("unexpected error: {}", other),
        }
        Ok(())
    }

    #[tokio::test]
    async fn upsert_ops_observability_anomaly_state_with_meta_should_reject_stale_revision(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        state
            .upsert_ops_observability_anomaly_state(
                &owner,
                UpdateOpsObservabilityAnomalyStateInput {
                    anomaly_state: HashMap::from([(
                        OPS_ALERT_RULE_HIGH_RETRY.to_string(),
                        OpsObservabilityAnomalyStateValue {
                            acknowledged_at_ms: 0,
                            suppress_until_ms: now_millis() + 300_000,
                        },
                    )]),
                },
            )
            .await?;
        let err = state
            .upsert_ops_observability_anomaly_state_with_meta(
                &owner,
                UpdateOpsObservabilityAnomalyStateInput {
                    anomaly_state: HashMap::from([(
                        OPS_ALERT_RULE_LOW_SUCCESS_RATE.to_string(),
                        OpsObservabilityAnomalyStateValue {
                            acknowledged_at_ms: 0,
                            suppress_until_ms: now_millis() + 300_000,
                        },
                    )]),
                },
                UpsertOpsObservabilityAnomalyStateMeta {
                    expected_config_revision: Some(OPS_OBSERVABILITY_CONFIG_REVISION_EMPTY),
                    require_if_match: true,
                    request_id: Some("obs-anomaly-stale"),
                },
            )
            .await
            .expect_err("stale revision should be rejected");
        match err {
            AppError::DebateConflict(code) => {
                assert_eq!(code, OPS_OBSERVABILITY_REVISION_CONFLICT_CODE);
            }
            other => panic!("unexpected error: {}", other),
        }
        Ok(())
    }

    #[tokio::test]
    async fn upsert_ops_observability_anomaly_state_with_meta_should_persist_audit_diff(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        state
            .upsert_ops_observability_anomaly_state(
                &owner,
                UpdateOpsObservabilityAnomalyStateInput {
                    anomaly_state: HashMap::from([(
                        OPS_ALERT_RULE_HIGH_RETRY.to_string(),
                        OpsObservabilityAnomalyStateValue {
                            acknowledged_at_ms: 1000,
                            suppress_until_ms: now_millis() + 300_000,
                        },
                    )]),
                },
            )
            .await?;
        let config_before = state.get_ops_observability_config(&owner).await?;
        let ret = state
            .upsert_ops_observability_anomaly_state_with_meta(
                &owner,
                UpdateOpsObservabilityAnomalyStateInput {
                    anomaly_state: HashMap::from([(
                        OPS_ALERT_RULE_LOW_SUCCESS_RATE.to_string(),
                        OpsObservabilityAnomalyStateValue {
                            acknowledged_at_ms: 2000,
                            suppress_until_ms: now_millis() + 300_000,
                        },
                    )]),
                },
                UpsertOpsObservabilityAnomalyStateMeta {
                    expected_config_revision: Some(config_before.config_revision.as_str()),
                    require_if_match: true,
                    request_id: Some("obs-anomaly-audit-diff"),
                },
            )
            .await?;
        assert!(ret
            .anomaly_state
            .contains_key(OPS_ALERT_RULE_LOW_SUCCESS_RATE));

        let audit_row: (Option<String>, Value, Value, i32, i32, i32) = sqlx::query_as(
            r#"
            SELECT
                request_id,
                before_anomaly_state_json,
                after_anomaly_state_json,
                input_item_count,
                retained_item_count,
                dropped_item_count
            FROM ops_observability_anomaly_state_audits
            ORDER BY id DESC
            LIMIT 1
            "#,
        )
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(audit_row.0.as_deref(), Some("obs-anomaly-audit-diff"));
        assert_eq!(audit_row.3, 1);
        assert_eq!(audit_row.4, 1);
        assert_eq!(audit_row.5, 0);
        let before_anomaly_state = parse_anomaly_state(audit_row.1, now_millis());
        let after_anomaly_state = parse_anomaly_state(audit_row.2, now_millis());
        assert!(before_anomaly_state.contains_key(OPS_ALERT_RULE_HIGH_RETRY));
        assert!(after_anomaly_state.contains_key(OPS_ALERT_RULE_LOW_SUCCESS_RATE));
        Ok(())
    }

    #[tokio::test]
    async fn evaluate_ops_observability_alerts_once_should_raise_and_clear_alerts() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
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
                title, description, category, stance_pro, stance_con, is_active, created_by
            )
            VALUES ('obs-topic', 'desc', 'game', 'pro', 'con', true, $1)
            RETURNING id
            "#,
        )
        .bind(owner.id)
        .fetch_one(&state.pool)
        .await?;
        let session_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO debate_sessions(
                topic_id, status, scheduled_start_at, actual_start_at, end_at, max_participants_per_side
            )
            VALUES (
                $1, 'closed',
                NOW() - INTERVAL '30 minutes',
                NOW() - INTERVAL '25 minutes',
                NOW() - INTERVAL '10 minutes',
                500
            )
            RETURNING id
            "#,
        )
        .bind(topic_id.0)
        .fetch_one(&state.pool)
        .await?;

        sqlx::query(
            r#"
            INSERT INTO judge_final_jobs(
                session_id, phase_start_no, phase_end_no,
                status, trace_id, idempotency_key, rubric_version, judge_policy_version,
                topic_domain, dispatch_attempts, created_at, updated_at
            )
            VALUES (
                $1, 1, 1,
                'failed',
                format('ops-final-%s', $1::text),
                format('ops_final:%s', $1::text),
                'v3', 'v3-default', 'default',
                3,
                NOW() - INTERVAL '2 minutes',
                NOW() - INTERVAL '1 minutes'
            )
            "#,
        )
        .bind(session_id.0)
        .execute(&state.pool)
        .await?;

        let report = state.evaluate_ops_observability_alerts_once().await?;
        assert!(report.alerts_raised > 0 || report.alerts_suppressed > 0);

        let raised_count: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)::bigint
            FROM ops_alert_notifications
            WHERE alert_status = 'raised'
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
            WHERE alert_status = 'cleared'
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
        state.grant_platform_admin(1).await?;
        let (service_base_url, callbacks) = spawn_mock_judge_outbox_server(
            vec![serde_json::json!({
                "eventId": "evt-bridge-ok",
                "scopeId": 1,
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
            WHERE alert_key = $1
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
        state.grant_platform_admin(1).await?;
        sqlx::query(
            r#"
            INSERT INTO ops_alert_notifications(
                alert_key, rule_type, severity, alert_status,
                title, message, metrics_json, recipients_json,
                delivery_status, created_at, updated_at
            )
            VALUES (
                $1, 'ai_judge:judge_timeout', 'warning', 'raised',
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
                "scopeId": 1,
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
            WHERE alert_key = $1
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
        state.grant_platform_admin(1).await?;
        let (service_base_url, callbacks) = spawn_mock_judge_outbox_server(
            vec![serde_json::json!({
                "eventId": "evt-bridge-bad",
                "status": "invalid",
                "payload": {
                    "alertType": "judge_timeout",
                    "severity": "warning",
                    "title": "bad",
                    "message": "missing scopeId"
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
            WHERE alert_key = $1
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
            .contains("unsupported outbox status"));
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
    fn normalize_split_review_note_should_validate_max_len() {
        let ok_note = "a".repeat(SPLIT_REVIEW_NOTE_MAX_LEN);
        assert!(normalize_split_review_note(Some(ok_note)).is_ok());
        let too_long_note = "a".repeat(SPLIT_REVIEW_NOTE_MAX_LEN + 1);
        let err = normalize_split_review_note(Some(too_long_note))
            .expect_err("too long split review note should be rejected");
        match err {
            AppError::DebateError(msg) => {
                assert!(msg.contains("split readiness review note too long"));
            }
            other => panic!("unexpected error: {other}"),
        }
    }

    #[test]
    fn normalize_split_review_audit_pagination_should_clamp_values() {
        assert_eq!(normalize_split_review_audit_limit(None), 20);
        assert_eq!(normalize_split_review_audit_limit(Some(0)), 1);
        assert_eq!(normalize_split_review_audit_limit(Some(999)), 200);
        assert_eq!(normalize_split_review_audit_offset(None), 0);
        assert_eq!(normalize_split_review_audit_offset(Some(99_999)), 50_000);
    }

    #[test]
    fn normalize_split_review_audit_created_window_should_validate_order() {
        let now = Utc::now();
        let valid = normalize_split_review_audit_created_window(
            Some(now - chrono::Duration::hours(1)),
            Some(now),
        );
        assert!(valid.is_ok());

        let err = normalize_split_review_audit_created_window(
            Some(now + chrono::Duration::hours(1)),
            Some(now),
        )
        .expect_err("createdAfter later than createdBefore should fail");
        match err {
            AppError::DebateError(message) => {
                assert!(message.contains("createdAfter must be <= createdBefore"));
            }
            other => panic!("unexpected error: {other}"),
        }
    }

    #[test]
    fn map_split_review_audit_row_should_reject_negative_i64_fields() {
        let row = OpsServiceSplitReviewAuditRow {
            id: -1,
            payment_compliance_required: Some(true),
            review_note: "note".to_string(),
            updated_by: 1,
            created_at: Utc::now(),
        };
        let err = map_split_review_audit_row(row).expect_err("negative id should fail mapping");
        match err {
            AppError::ServerError(code) => {
                assert_eq!(code, "ops_split_review_audit_invalid_id");
            }
            other => panic!("unexpected error: {other}"),
        }
    }

    #[tokio::test]
    async fn upsert_ops_service_split_review_should_support_set_and_clear_flag() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");

        let set_ret = state
            .upsert_ops_service_split_review(
                &owner,
                UpsertOpsServiceSplitReviewInput {
                    payment_compliance_required: Some(true),
                    review_note: Some("need isolated payment domain".to_string()),
                },
            )
            .await?;
        let set_item = set_ret
            .thresholds
            .iter()
            .find(|v| v.key == "payment_compliance_isolation")
            .expect("payment threshold should exist");
        assert_eq!(set_item.status, "met");
        assert!(set_item.triggered);
        assert_eq!(set_item.evidence["stale"], Value::Bool(false));
        assert_eq!(
            set_item.evidence["staleThresholdHours"],
            Value::from(SPLIT_REVIEW_STALE_THRESHOLD_HOURS)
        );
        assert!(set_item.evidence["reviewAgeHours"].is_number());
        assert_eq!(set_ret.overall_status, "review_required");

        let clear_ret = state
            .upsert_ops_service_split_review(
                &owner,
                UpsertOpsServiceSplitReviewInput {
                    payment_compliance_required: None,
                    review_note: Some("".to_string()),
                },
            )
            .await?;
        let clear_item = clear_ret
            .thresholds
            .iter()
            .find(|v| v.key == "payment_compliance_isolation")
            .expect("payment threshold should exist");
        assert_eq!(clear_item.status, "insufficient_data");
        assert!(!clear_item.triggered);
        assert_eq!(
            clear_item.evidence["manualInputRequired"],
            Value::Bool(true),
            "clearing compliance flag should return to manual-input-required state"
        );
        assert_eq!(
            clear_item.evidence["staleThresholdHours"],
            Value::from(SPLIT_REVIEW_STALE_THRESHOLD_HOURS)
        );
        Ok(())
    }

    #[tokio::test]
    async fn upsert_ops_service_split_review_should_keep_complete_snapshot_under_concurrency(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let barrier = Arc::new(Barrier::new(3));

        let state_a = state.clone();
        let owner_a = owner.clone();
        let barrier_a = barrier.clone();
        let task_a = tokio::spawn(async move {
            barrier_a.wait().await;
            state_a
                .upsert_ops_service_split_review(
                    &owner_a,
                    UpsertOpsServiceSplitReviewInput {
                        payment_compliance_required: Some(true),
                        review_note: Some("review-a".to_string()),
                    },
                )
                .await
        });

        let state_b = state.clone();
        let owner_b = owner.clone();
        let barrier_b = barrier.clone();
        let task_b = tokio::spawn(async move {
            barrier_b.wait().await;
            state_b
                .upsert_ops_service_split_review(
                    &owner_b,
                    UpsertOpsServiceSplitReviewInput {
                        payment_compliance_required: Some(false),
                        review_note: Some("review-b".to_string()),
                    },
                )
                .await
        });

        barrier.wait().await;
        task_a.await??;
        task_b.await??;

        let row: (Option<bool>, String) = sqlx::query_as(
            r#"
            SELECT payment_compliance_required, review_note
            FROM ops_service_split_reviews
            WHERE singleton_id = 1
            "#,
        )
        .fetch_one(&state.pool)
        .await?;
        assert!(
            row == (Some(true), "review-a".to_string())
                || row == (Some(false), "review-b".to_string()),
            "concurrent upsert should keep one complete snapshot, got: {:?}",
            row
        );

        let ret = state.get_ops_service_split_readiness(&owner).await?;
        let payment_item = ret
            .thresholds
            .iter()
            .find(|v| v.key == "payment_compliance_isolation")
            .expect("payment threshold should exist");
        match row.0 {
            Some(true) => {
                assert_eq!(payment_item.status, "met");
                assert!(payment_item.triggered);
            }
            Some(false) => {
                assert_eq!(payment_item.status, "not_met");
                assert!(!payment_item.triggered);
            }
            None => panic!("row should not be None after concurrent set"),
        }
        assert_eq!(payment_item.evidence["reviewNote"], Value::String(row.1));
        Ok(())
    }

    #[tokio::test]
    async fn upsert_ops_service_split_review_should_keep_main_write_when_alert_emit_failed_best_effort(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");

        OPS_SPLIT_REVIEW_ALERT_EMIT_FORCE_FAIL.store(true, Ordering::Relaxed);
        let ret = state
            .upsert_ops_service_split_review(
                &owner,
                UpsertOpsServiceSplitReviewInput {
                    payment_compliance_required: Some(true),
                    review_note: Some("force-alert-fail".to_string()),
                },
            )
            .await;
        OPS_SPLIT_REVIEW_ALERT_EMIT_FORCE_FAIL.store(false, Ordering::Relaxed);

        let ret = ret?;
        assert_eq!(ret.overall_status, "review_required");

        let row: (Option<bool>, String) = sqlx::query_as(
            r#"
            SELECT payment_compliance_required, review_note
            FROM ops_service_split_reviews
            WHERE singleton_id = 1
            "#,
        )
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(row, (Some(true), "force-alert-fail".to_string()));

        let audit_count: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)::bigint
            FROM ops_service_split_review_audits
            WHERE review_note = 'force-alert-fail'
            "#,
        )
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(audit_count, 1);
        Ok(())
    }

    #[tokio::test]
    async fn list_ops_service_split_review_audits_should_support_filters_and_window() -> Result<()>
    {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let reviewer = state
            .find_user_by_id(2)
            .await?
            .expect("reviewer should exist");
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                reviewer.id as u64,
                UpsertOpsRoleInput {
                    role: "ops_reviewer".to_string(),
                },
            )
            .await?;

        state
            .upsert_ops_service_split_review(
                &owner,
                UpsertOpsServiceSplitReviewInput {
                    payment_compliance_required: Some(true),
                    review_note: Some("api072-filter-note-a".to_string()),
                },
            )
            .await?;
        state
            .upsert_ops_service_split_review(
                &reviewer,
                UpsertOpsServiceSplitReviewInput {
                    payment_compliance_required: Some(false),
                    review_note: Some("api072-filter-note-b".to_string()),
                },
            )
            .await?;
        state
            .upsert_ops_service_split_review(
                &owner,
                UpsertOpsServiceSplitReviewInput {
                    payment_compliance_required: Some(true),
                    review_note: Some("api072-filter-note-c".to_string()),
                },
            )
            .await?;

        sqlx::query(
            "UPDATE ops_service_split_review_audits SET created_at = NOW() - INTERVAL '3 hours' WHERE review_note = 'api072-filter-note-a'",
        )
        .execute(&state.pool)
        .await?;
        sqlx::query(
            "UPDATE ops_service_split_review_audits SET created_at = NOW() - INTERVAL '2 hours' WHERE review_note = 'api072-filter-note-b'",
        )
        .execute(&state.pool)
        .await?;
        sqlx::query(
            "UPDATE ops_service_split_review_audits SET created_at = NOW() - INTERVAL '1 hours' WHERE review_note = 'api072-filter-note-c'",
        )
        .execute(&state.pool)
        .await?;

        let all = state
            .list_ops_service_split_review_audits(
                &owner,
                ListOpsServiceSplitReviewAuditsQuery {
                    limit: Some(20),
                    offset: Some(0),
                    updated_by: None,
                    payment_compliance_required: None,
                    created_after: None,
                    created_before: None,
                },
            )
            .await?;
        let filtered_notes: Vec<&str> = all
            .items
            .iter()
            .filter_map(|item| match item.review_note.as_str() {
                "api072-filter-note-a" | "api072-filter-note-b" | "api072-filter-note-c" => {
                    Some(item.review_note.as_str())
                }
                _ => None,
            })
            .collect();
        assert_eq!(
            filtered_notes,
            vec![
                "api072-filter-note-c",
                "api072-filter-note-b",
                "api072-filter-note-a"
            ]
        );

        let by_reviewer = state
            .list_ops_service_split_review_audits(
                &owner,
                ListOpsServiceSplitReviewAuditsQuery {
                    limit: Some(20),
                    offset: Some(0),
                    updated_by: Some(reviewer.id as u64),
                    payment_compliance_required: None,
                    created_after: None,
                    created_before: None,
                },
            )
            .await?;
        let reviewer_notes: Vec<&str> = by_reviewer
            .items
            .iter()
            .filter_map(|item| {
                if item.review_note == "api072-filter-note-b" {
                    Some(item.review_note.as_str())
                } else {
                    None
                }
            })
            .collect();
        assert_eq!(reviewer_notes, vec!["api072-filter-note-b"]);

        let required_only = state
            .list_ops_service_split_review_audits(
                &owner,
                ListOpsServiceSplitReviewAuditsQuery {
                    limit: Some(20),
                    offset: Some(0),
                    updated_by: None,
                    payment_compliance_required: Some(true),
                    created_after: None,
                    created_before: None,
                },
            )
            .await?;
        let required_notes: Vec<&str> = required_only
            .items
            .iter()
            .filter_map(|item| match item.review_note.as_str() {
                "api072-filter-note-a" | "api072-filter-note-c" => Some(item.review_note.as_str()),
                _ => None,
            })
            .collect();
        assert_eq!(
            required_notes,
            vec!["api072-filter-note-c", "api072-filter-note-a"]
        );

        let now = Utc::now();
        let window = state
            .list_ops_service_split_review_audits(
                &owner,
                ListOpsServiceSplitReviewAuditsQuery {
                    limit: Some(20),
                    offset: Some(0),
                    updated_by: None,
                    payment_compliance_required: None,
                    created_after: Some(
                        now - chrono::Duration::hours(2) - chrono::Duration::minutes(30),
                    ),
                    created_before: Some(
                        now - chrono::Duration::hours(1) - chrono::Duration::minutes(30),
                    ),
                },
            )
            .await?;
        let window_notes: Vec<&str> = window
            .items
            .iter()
            .filter_map(|item| {
                if item.review_note == "api072-filter-note-b" {
                    Some(item.review_note.as_str())
                } else {
                    None
                }
            })
            .collect();
        assert_eq!(window_notes, vec!["api072-filter-note-b"]);

        let invalid_window = state
            .list_ops_service_split_review_audits(
                &owner,
                ListOpsServiceSplitReviewAuditsQuery {
                    limit: Some(20),
                    offset: Some(0),
                    updated_by: None,
                    payment_compliance_required: None,
                    created_after: Some(now - chrono::Duration::hours(1)),
                    created_before: Some(now - chrono::Duration::hours(2)),
                },
            )
            .await
            .expect_err("invalid created window should fail");
        match invalid_window {
            AppError::DebateError(message) => {
                assert!(message.contains("createdAfter must be <= createdBefore"));
            }
            other => panic!("unexpected error: {other}"),
        }
        Ok(())
    }

    #[tokio::test]
    async fn get_ops_service_split_readiness_should_trigger_dispatch_pressure_when_window_failed_ratio_exceeds_threshold(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");

        let session_id = seed_split_readiness_session(&state, owner.id).await?;
        seed_split_readiness_final_jobs(&state, session_id, 12, 18).await?;

        let ret = state.get_ops_service_split_readiness(&owner).await?;
        let dispatch_item = ret
            .thresholds
            .iter()
            .find(|item| item.key == "judge_dispatch_pressure")
            .expect("dispatch threshold should exist");
        assert!(dispatch_item.triggered);
        assert_eq!(dispatch_item.status, "met");
        assert_eq!(
            dispatch_item.evidence["failedRatioComparison"],
            Value::String("above_threshold".to_string())
        );
        assert_eq!(
            dispatch_item.evidence["dispatchFailedRatioSampleCompleted"],
            Value::from(30)
        );
        assert_eq!(ret.overall_status, "review_required");
        Ok(())
    }

    #[tokio::test]
    async fn get_ops_service_split_readiness_should_not_trigger_dispatch_pressure_when_window_failed_ratio_sample_insufficient(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");

        let session_id = seed_split_readiness_session(&state, owner.id).await?;
        seed_split_readiness_final_jobs(&state, session_id, 10, 0).await?;

        let ret = state.get_ops_service_split_readiness(&owner).await?;
        let dispatch_item = ret
            .thresholds
            .iter()
            .find(|item| item.key == "judge_dispatch_pressure")
            .expect("dispatch threshold should exist");
        assert!(!dispatch_item.triggered);
        assert_eq!(dispatch_item.status, "not_met");
        assert_eq!(
            dispatch_item.evidence["failedRatioComparison"],
            Value::String("insufficient_sample".to_string())
        );
        assert_eq!(
            dispatch_item.evidence["dispatchFailedRatioSampleCompleted"],
            Value::from(10)
        );
        assert_eq!(ret.overall_status, "hold");
        Ok(())
    }

    #[tokio::test]
    async fn apply_ops_observability_anomaly_action_should_support_suppress_ack_and_clear(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
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
        state.grant_platform_admin(1).await?;
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

    #[tokio::test]
    async fn apply_ops_observability_anomaly_action_should_keep_both_keys_under_concurrency(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let barrier = Arc::new(Barrier::new(3));

        let state_a = state.clone();
        let owner_a = owner.clone();
        let barrier_a = barrier.clone();
        let task_a = tokio::spawn(async move {
            barrier_a.wait().await;
            state_a
                .apply_ops_observability_anomaly_action(
                    &owner_a,
                    ApplyOpsObservabilityAnomalyActionInput {
                        alert_key: OPS_ALERT_RULE_HIGH_RETRY.to_string(),
                        action: OPS_ANOMALY_ACTION_SUPPRESS.to_string(),
                        suppress_minutes: Some(5),
                    },
                )
                .await
        });

        let state_b = state.clone();
        let owner_b = owner.clone();
        let barrier_b = barrier.clone();
        let task_b = tokio::spawn(async move {
            barrier_b.wait().await;
            state_b
                .apply_ops_observability_anomaly_action(
                    &owner_b,
                    ApplyOpsObservabilityAnomalyActionInput {
                        alert_key: OPS_ALERT_RULE_LOW_SUCCESS_RATE.to_string(),
                        action: OPS_ANOMALY_ACTION_SUPPRESS.to_string(),
                        suppress_minutes: Some(5),
                    },
                )
                .await
        });

        barrier.wait().await;
        task_a.await??;
        task_b.await??;

        let ret = state.get_ops_observability_config(&owner).await?;
        assert!(ret.anomaly_state.contains_key(OPS_ALERT_RULE_HIGH_RETRY));
        assert!(ret
            .anomaly_state
            .contains_key(OPS_ALERT_RULE_LOW_SUCCESS_RATE));
        Ok(())
    }

    #[tokio::test]
    async fn apply_ops_observability_anomaly_action_with_meta_should_persist_action_audit(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let now_ms = now_millis();

        let ret = state
            .apply_ops_observability_anomaly_action_with_meta(
                &owner,
                ApplyOpsObservabilityAnomalyActionInput {
                    alert_key: OPS_ALERT_RULE_HIGH_RETRY.to_string(),
                    action: OPS_ANOMALY_ACTION_SUPPRESS.to_string(),
                    suppress_minutes: Some(5),
                },
                ApplyOpsObservabilityAnomalyActionMeta {
                    request_id: Some("ops-action-audit-rid"),
                },
            )
            .await?;
        assert!(ret.anomaly_state.contains_key(OPS_ALERT_RULE_HIGH_RETRY));

        let audit_row: (
            String,
            String,
            Option<i32>,
            Value,
            Value,
            i64,
            Option<String>,
        ) = sqlx::query_as(
            r#"
                SELECT
                    alert_key,
                    action,
                    suppress_minutes,
                    before_state_json,
                    after_state_json,
                    updated_by,
                    request_id
                FROM ops_observability_anomaly_action_audits
                ORDER BY id DESC
                LIMIT 1
                "#,
        )
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(audit_row.0, OPS_ALERT_RULE_HIGH_RETRY);
        assert_eq!(audit_row.1, OPS_ANOMALY_ACTION_SUPPRESS);
        assert_eq!(audit_row.2, Some(5));
        assert_eq!(audit_row.3, Value::Null);
        let after_state: OpsObservabilityAnomalyStateValue = serde_json::from_value(audit_row.4)?;
        assert!(after_state.acknowledged_at_ms >= now_ms);
        assert!(after_state.suppress_until_ms > now_ms);
        assert_eq!(audit_row.5, owner.id);
        assert_eq!(audit_row.6.as_deref(), Some("ops-action-audit-rid"));
        Ok(())
    }

    #[tokio::test]
    async fn apply_ops_observability_anomaly_action_with_meta_should_return_committed_snapshot(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");

        let ret = state
            .apply_ops_observability_anomaly_action_with_meta(
                &owner,
                ApplyOpsObservabilityAnomalyActionInput {
                    alert_key: OPS_ALERT_RULE_LOW_SUCCESS_RATE.to_string(),
                    action: OPS_ANOMALY_ACTION_ACKNOWLEDGE.to_string(),
                    suppress_minutes: None,
                },
                ApplyOpsObservabilityAnomalyActionMeta {
                    request_id: Some("ops-action-snapshot-rid"),
                },
            )
            .await?;
        let row: OpsObservabilityConfigRow = sqlx::query_as(
            r#"
            SELECT thresholds_json, anomaly_state_json, updated_by, updated_at
            FROM ops_observability_configs
            WHERE singleton_id = 1
            "#,
        )
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(
            ret.config_revision,
            format_ops_observability_config_revision(Some(row.updated_at))
        );
        assert_eq!(ret.updated_by, Some(owner.id as u64));
        assert_eq!(ret.updated_at, Some(row.updated_at));
        assert!(ret
            .anomaly_state
            .contains_key(OPS_ALERT_RULE_LOW_SUCCESS_RATE));
        Ok(())
    }

    #[test]
    fn evaluate_alert_for_rule_low_success_rate_should_report_active_message_when_below_threshold()
    {
        let spec = rule_specs()
            .iter()
            .find(|item| item.rule_type == OPS_ALERT_RULE_LOW_SUCCESS_RATE)
            .expect("low success rule should exist");
        let thresholds = OpsObservabilityThresholds::default();
        let evaluated = evaluate_alert_for_rule(
            spec,
            &thresholds,
            OpsRecentJudgeSignal {
                success_count: 10,
                failed_count: 10,
                avg_dispatch_attempts: 1.0,
                p95_latency_ms: 100.0,
                pending_dlq_count: 0,
            },
        );
        assert!(evaluated.is_active);
        assert!(evaluated.message.contains("低于阈值"));
        assert_eq!(
            evaluated.metrics["comparison"],
            Value::String("below_threshold".to_string())
        );
    }

    #[test]
    fn evaluate_alert_for_rule_low_success_rate_should_report_clear_message_when_healthy() {
        let spec = rule_specs()
            .iter()
            .find(|item| item.rule_type == OPS_ALERT_RULE_LOW_SUCCESS_RATE)
            .expect("low success rule should exist");
        let thresholds = OpsObservabilityThresholds::default();
        let evaluated = evaluate_alert_for_rule(
            spec,
            &thresholds,
            OpsRecentJudgeSignal {
                success_count: 19,
                failed_count: 1,
                avg_dispatch_attempts: 1.0,
                p95_latency_ms: 100.0,
                pending_dlq_count: 0,
            },
        );
        assert!(!evaluated.is_active);
        assert!(evaluated.message.contains("不低于阈值"));
        assert_eq!(
            evaluated.metrics["comparison"],
            Value::String("above_or_equal_threshold".to_string())
        );
    }

    #[test]
    fn evaluate_alert_for_rule_low_success_rate_should_report_insufficient_sample_when_completed_zero(
    ) {
        let spec = rule_specs()
            .iter()
            .find(|item| item.rule_type == OPS_ALERT_RULE_LOW_SUCCESS_RATE)
            .expect("low success rule should exist");
        let thresholds = OpsObservabilityThresholds::default();
        let evaluated = evaluate_alert_for_rule(
            spec,
            &thresholds,
            OpsRecentJudgeSignal {
                success_count: 0,
                failed_count: 0,
                avg_dispatch_attempts: 0.0,
                p95_latency_ms: 0.0,
                pending_dlq_count: 0,
            },
        );
        assert!(!evaluated.is_active);
        assert!(evaluated.message.contains("小于最小阈值"));
        assert_eq!(
            evaluated.metrics["comparison"],
            Value::String("insufficient_sample".to_string())
        );
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
    fn build_ops_metrics_dictionary_items_should_include_ops_rbac_keys() {
        let items = build_ops_metrics_dictionary_items();
        let keys = items
            .iter()
            .map(|item| item.key.as_str())
            .collect::<HashSet<_>>();
        for required_key in [
            "ops.rbac.roles_list.request_total",
            "ops.rbac.roles_list.rate_limited_total",
            "ops.rbac.roles_list.latency_p95_ms",
            "ops.rbac.me.request_total",
            "ops.rbac.me.owner_total",
            "ops.rbac.me.non_owner_total",
            "ops.rbac.me.latency_p95_ms",
            "ops.rbac.roles_write.request_total",
            "ops.rbac.roles_write.upsert_total",
            "ops.rbac.roles_write.revoke_total",
            "ops.rbac.roles_write.latency_p95_ms",
        ] {
            assert!(
                keys.contains(required_key),
                "missing required ops rbac metric key: {required_key}"
            );
        }
    }

    #[test]
    fn build_ops_metrics_dictionary_items_should_not_have_duplicate_keys() {
        let items = build_ops_metrics_dictionary_items();
        let mut unique_keys = HashSet::new();
        for item in &items {
            assert!(
                unique_keys.insert(item.key.clone()),
                "duplicate metric key found: {}",
                item.key
            );
        }
    }

    #[test]
    fn build_ops_metrics_dictionary_revision_should_be_stable_for_same_items() {
        let items = build_ops_metrics_dictionary_items();
        let rev_a = build_ops_metrics_dictionary_revision(&items);
        let rev_b = build_ops_metrics_dictionary_revision(&items);
        assert_eq!(rev_a, rev_b);
        assert!(rev_a.starts_with("sha1:"));
    }

    #[test]
    fn build_ops_metrics_dictionary_revision_should_change_when_items_change() {
        let items = build_ops_metrics_dictionary_items();
        let original = build_ops_metrics_dictionary_revision(&items);
        let mut changed = items.clone();
        changed[0].description.push_str(" [changed]");
        let updated = build_ops_metrics_dictionary_revision(&changed);
        assert_ne!(original, updated);
    }

    #[test]
    fn build_ops_metrics_dictionary_items_should_have_valid_fields() {
        let items = build_ops_metrics_dictionary_items();
        for item in &items {
            assert!(
                !item.key.trim().is_empty(),
                "metrics dictionary key should not be empty"
            );
            assert!(
                !item.category.trim().is_empty(),
                "metrics dictionary category should not be empty"
            );
            assert!(
                !item.source.trim().is_empty(),
                "metrics dictionary source should not be empty"
            );
            assert!(
                !item.unit.trim().is_empty(),
                "metrics dictionary unit should not be empty"
            );
            assert!(
                !item.aggregation.trim().is_empty(),
                "metrics dictionary aggregation should not be empty"
            );
            assert!(
                !item.description.trim().is_empty(),
                "metrics dictionary description should not be empty"
            );
            if let Some(target) = &item.target {
                let normalized = target.trim();
                assert!(
                    !normalized.is_empty(),
                    "metrics dictionary target should not be empty"
                );
                assert!(
                    matches!(normalized.chars().next(), Some('<') | Some('>') | Some('=')),
                    "metrics dictionary target should start with comparator: {}",
                    target
                );
            }
        }
    }

    #[test]
    fn normalize_ai_judge_outbox_event_should_map_status_and_fields() {
        let item = AiJudgeOutboxItem {
            event_id: "evt-1".to_string(),
            scope_id: Some(1),
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
        assert_eq!(ret.metrics["scopeId"], Value::from(1));
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
    fn normalize_ai_judge_outbox_event_should_default_scope_id_when_missing() {
        let item = AiJudgeOutboxItem {
            event_id: "evt-2".to_string(),
            scope_id: None,
            job_id: None,
            trace_id: None,
            alert_id: None,
            status: Some("raised".to_string()),
            payload: Value::Null,
        };
        let ret = normalize_ai_judge_outbox_event(item).expect("missing scope id should fallback");
        assert_eq!(ret.metrics["scopeId"], Value::from(PLATFORM_SCOPE_ID));
    }

    #[test]
    fn normalize_ai_judge_outbox_event_should_ignore_unknown_scope_fields() {
        let item = AiJudgeOutboxItem {
            event_id: "evt-3".to_string(),
            scope_id: None,
            job_id: Some(3001),
            trace_id: Some("trace-unknown-scope".to_string()),
            alert_id: Some("alert-unknown-scope".to_string()),
            status: Some("raised".to_string()),
            payload: serde_json::json!({
                "eventType": "ai_judge.audit_alert.status_changed.v1",
                "legacyScopeId": 99,
                "alertType": "judge_timeout",
                "severity": "warning",
                "title": "legacy",
                "message": "unknown scope field should be ignored"
            }),
        };
        let ret = normalize_ai_judge_outbox_event(item)
            .expect("unknown scope field should not be parsed");
        assert_eq!(ret.metrics["scopeId"], Value::from(PLATFORM_SCOPE_ID));
    }
}
