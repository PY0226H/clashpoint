use crate::{
    extractors::{Geo, Protobuf},
    AnalyticsEventRow, AppError, AppState,
};
use axum::{
    extract::{Query, State},
    http::{request::Parts, StatusCode},
    response::IntoResponse,
    Json,
};
use chat_core::pb::AnalyticsEvent;
use clickhouse::Row;
use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicU64, Ordering};
use tracing::info;
use utoipa::{IntoParams, ToSchema};

const SUMMARY_CACHE_TTL_MS: i64 = 5_000;

/// Update the agent by id.
#[utoipa::path(
    post,
    path = "/api/event",
    responses(
        (status = 201, description = "Event created"),
        (status = 400, description = "Invalid event", body = ErrorOutput),
        (status = 500, description = "Internal server error", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn create_event_handler(
    parts: Parts,
    State(state): State<AppState>,
    Geo(geo): Geo,
    Protobuf(event): Protobuf<AnalyticsEvent>,
) -> Result<impl IntoResponse, AppError> {
    info!("received event: {:?}", event);
    let mut row = AnalyticsEventRow::try_from(event)?;

    row.update_with_server_info(&parts, geo);
    row.set_session_id(&state);

    let mut insert = state.client.insert("analytics_events")?;
    insert.write(&row).await?;
    insert.end().await?;
    Ok(StatusCode::CREATED)
}

#[derive(Debug, Deserialize, IntoParams)]
#[serde(rename_all = "camelCase")]
pub(crate) struct JudgeRefreshSummaryQuery {
    /// Time window in hours, clamped to [1, 168], default 24.
    pub hours: Option<u32>,
    /// Max grouped rows returned, clamped to [1, 200], default 20.
    pub limit: Option<u32>,
    /// Optional debate session filter.
    pub debate_session_id: Option<u64>,
}

#[derive(Debug, Deserialize, IntoParams)]
#[serde(rename_all = "camelCase")]
pub(crate) struct AuthEventSummaryQuery {
    /// Time window in hours, clamped to [1, 168], default 24.
    pub hours: Option<u32>,
    /// Max grouped rows returned, clamped to [1, 200], default 20.
    pub limit: Option<u32>,
}

#[derive(Debug, Clone, Row, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub(crate) struct AuthEventSummaryItem {
    pub event_type: String,
    pub account_type: String,
    pub total_events: u64,
}

#[derive(Debug, Clone, Row, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
struct AuthEventQualityRow {
    pub legacy_email_events: u64,
    pub missing_account_type_events: u64,
    pub missing_account_identifier_hash_events: u64,
}

#[derive(Debug, Clone, Serialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub(crate) struct GetAuthEventSummaryOutput {
    pub window_hours: u32,
    pub limit: u32,
    pub rows: Vec<AuthEventSummaryItem>,
    pub legacy_email_events: u64,
    pub missing_account_type_events: u64,
    pub missing_account_identifier_hash_events: u64,
}

#[derive(Debug, Clone, Row, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub(crate) struct JudgeRefreshSummaryItem {
    pub debate_session_id: String,
    pub source_event_type: String,
    pub total_runs: u64,
    pub success_runs: u64,
    pub failure_runs: u64,
    pub success_rate: f64,
    pub avg_attempts: f64,
    pub avg_retry_count: f64,
    pub avg_coalesced_events: f64,
    pub last_seen_at_ms: i64,
}

#[derive(Debug, Clone, Serialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub(crate) struct GetJudgeRefreshSummaryOutput {
    pub window_hours: u32,
    pub limit: u32,
    pub rows: Vec<JudgeRefreshSummaryItem>,
}

#[derive(Default)]
pub(crate) struct JudgeRefreshSummaryMetrics {
    request_total: AtomicU64,
    cache_hit_total: AtomicU64,
    cache_miss_total: AtomicU64,
    db_query_total: AtomicU64,
    db_error_total: AtomicU64,
    db_latency_total_ms: AtomicU64,
    db_latency_samples: AtomicU64,
    last_db_latency_ms: AtomicU64,
}

#[derive(Debug, Clone, Serialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub(crate) struct GetJudgeRefreshSummaryMetricsOutput {
    pub request_total: u64,
    pub cache_hit_total: u64,
    pub cache_miss_total: u64,
    pub cache_hit_rate: f64,
    pub db_query_total: u64,
    pub db_error_total: u64,
    pub avg_db_latency_ms: f64,
    pub last_db_latency_ms: u64,
}

impl JudgeRefreshSummaryMetrics {
    pub(crate) fn observe_cache_hit(&self) {
        self.request_total.fetch_add(1, Ordering::Relaxed);
        self.cache_hit_total.fetch_add(1, Ordering::Relaxed);
    }

    pub(crate) fn observe_cache_miss(&self) {
        self.request_total.fetch_add(1, Ordering::Relaxed);
        self.cache_miss_total.fetch_add(1, Ordering::Relaxed);
    }

    pub(crate) fn observe_db_success(&self, latency_ms: u64) {
        self.db_query_total.fetch_add(1, Ordering::Relaxed);
        self.db_latency_total_ms
            .fetch_add(latency_ms, Ordering::Relaxed);
        self.db_latency_samples.fetch_add(1, Ordering::Relaxed);
        self.last_db_latency_ms.store(latency_ms, Ordering::Relaxed);
    }

    pub(crate) fn observe_db_error(&self, latency_ms: u64) {
        self.db_query_total.fetch_add(1, Ordering::Relaxed);
        self.db_error_total.fetch_add(1, Ordering::Relaxed);
        self.db_latency_total_ms
            .fetch_add(latency_ms, Ordering::Relaxed);
        self.db_latency_samples.fetch_add(1, Ordering::Relaxed);
        self.last_db_latency_ms.store(latency_ms, Ordering::Relaxed);
    }

    pub(crate) fn snapshot(&self) -> GetJudgeRefreshSummaryMetricsOutput {
        let request_total = self.request_total.load(Ordering::Relaxed);
        let cache_hit_total = self.cache_hit_total.load(Ordering::Relaxed);
        let cache_miss_total = self.cache_miss_total.load(Ordering::Relaxed);
        let db_query_total = self.db_query_total.load(Ordering::Relaxed);
        let db_error_total = self.db_error_total.load(Ordering::Relaxed);
        let db_latency_total_ms = self.db_latency_total_ms.load(Ordering::Relaxed);
        let db_latency_samples = self.db_latency_samples.load(Ordering::Relaxed);
        let last_db_latency_ms = self.last_db_latency_ms.load(Ordering::Relaxed);
        let cache_hit_rate = if request_total == 0 {
            0.0
        } else {
            (cache_hit_total as f64) * 100.0 / (request_total as f64)
        };
        let avg_db_latency_ms = if db_latency_samples == 0 {
            0.0
        } else {
            (db_latency_total_ms as f64) / (db_latency_samples as f64)
        };
        GetJudgeRefreshSummaryMetricsOutput {
            request_total,
            cache_hit_total,
            cache_miss_total,
            cache_hit_rate,
            db_query_total,
            db_error_total,
            avg_db_latency_ms,
            last_db_latency_ms,
        }
    }
}

fn normalize_hours(v: Option<u32>) -> u32 {
    v.unwrap_or(24).clamp(1, 168)
}

fn normalize_limit(v: Option<u32>) -> u32 {
    v.unwrap_or(20).clamp(1, 200)
}

fn normalize_auth_summary_limit(v: Option<u32>) -> u32 {
    v.unwrap_or(20).clamp(1, 200)
}

fn build_summary_cache_key(hours: u32, limit: u32, debate_session_id: Option<u64>) -> String {
    match debate_session_id {
        Some(session_id) => format!("h={hours}|l={limit}|sid={session_id}"),
        None => format!("h={hours}|l={limit}|sid=*"),
    }
}

fn build_auth_event_summary_sql(hours: u32, limit: u32) -> String {
    format!(
        r#"
SELECT
    event_type,
    account_type,
    toUInt64(count()) AS total_events
FROM (
    SELECT
        event_type,
        multiIf(
            event_type = 'user_login',
                if(
                    notEmpty(trimBoth(ifNull(login_account_type, ''))),
                    lowerUTF8(trimBoth(ifNull(login_account_type, ''))),
                    if(notEmpty(trimBoth(ifNull(login_email, ''))), 'email', 'unknown')
                ),
            event_type = 'user_logout',
                if(
                    notEmpty(trimBoth(ifNull(logout_account_type, ''))),
                    lowerUTF8(trimBoth(ifNull(logout_account_type, ''))),
                    if(notEmpty(trimBoth(ifNull(logout_email, ''))), 'email', 'unknown')
                ),
            event_type = 'user_register',
                if(
                    notEmpty(trimBoth(ifNull(register_account_type, ''))),
                    lowerUTF8(trimBoth(ifNull(register_account_type, ''))),
                    if(notEmpty(trimBoth(ifNull(register_email, ''))), 'email', 'unknown')
                ),
            'unknown'
        ) AS account_type
    FROM analytics_events
    WHERE event_type IN ('user_login', 'user_logout', 'user_register')
      AND server_ts >= now64(3) - toIntervalHour({hours})
)
GROUP BY event_type, account_type
ORDER BY event_type ASC, total_events DESC
LIMIT {limit}
"#
    )
}

fn build_auth_event_quality_sql(hours: u32) -> String {
    format!(
        r#"
SELECT
    toUInt64(countIf(
        (event_type = 'user_login' AND notEmpty(trimBoth(ifNull(login_email, ''))))
        OR (event_type = 'user_logout' AND notEmpty(trimBoth(ifNull(logout_email, ''))))
        OR (event_type = 'user_register' AND notEmpty(trimBoth(ifNull(register_email, ''))))
    )) AS legacy_email_events,
    toUInt64(countIf(
        (event_type = 'user_login' AND empty(trimBoth(ifNull(login_account_type, ''))))
        OR (event_type = 'user_logout' AND empty(trimBoth(ifNull(logout_account_type, ''))))
        OR (event_type = 'user_register' AND empty(trimBoth(ifNull(register_account_type, ''))))
    )) AS missing_account_type_events,
    toUInt64(countIf(
        (event_type = 'user_login' AND empty(trimBoth(ifNull(login_account_identifier_hash, ''))))
        OR (event_type = 'user_logout' AND empty(trimBoth(ifNull(logout_account_identifier_hash, ''))))
        OR (event_type = 'user_register' AND empty(trimBoth(ifNull(register_account_identifier_hash, ''))))
    )) AS missing_account_identifier_hash_events
FROM analytics_events
WHERE event_type IN ('user_login', 'user_logout', 'user_register')
  AND server_ts >= now64(3) - toIntervalHour({hours})
"#
    )
}

fn is_cache_fresh(cached_at_ms: i64, now_ms: i64, ttl_ms: i64) -> bool {
    if ttl_ms <= 0 {
        return false;
    }
    let age_ms = now_ms.saturating_sub(cached_at_ms);
    age_ms >= 0 && age_ms <= ttl_ms
}

fn duration_to_millis_u64(v: std::time::Duration) -> u64 {
    let ms = v.as_millis();
    ms.min(u128::from(u64::MAX)) as u64
}

/// Query aggregated quality metrics for judge realtime refresh pipeline.
#[utoipa::path(
    get,
    path = "/api/judge-refresh/summary",
    params(
        JudgeRefreshSummaryQuery
    ),
    responses(
        (status = 200, description = "Judge realtime refresh summary", body = GetJudgeRefreshSummaryOutput),
        (status = 500, description = "Internal server error", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_judge_refresh_summary_handler(
    State(state): State<AppState>,
    Query(input): Query<JudgeRefreshSummaryQuery>,
) -> Result<impl IntoResponse, AppError> {
    let hours = normalize_hours(input.hours);
    let limit = normalize_limit(input.limit);
    let session_filter = input.debate_session_id.map(|v| v.to_string());
    let cache_key = build_summary_cache_key(hours, limit, input.debate_session_id);
    let now_ms = chrono::Utc::now().timestamp_millis();
    if let Some(entry) = state.judge_refresh_summary_cache.get(&cache_key) {
        let (cached_at_ms, payload) = entry.value();
        if is_cache_fresh(*cached_at_ms, now_ms, SUMMARY_CACHE_TTL_MS) {
            state.judge_refresh_summary_metrics.observe_cache_hit();
            return Ok(Json(payload.clone()));
        }
    }
    state.judge_refresh_summary_metrics.observe_cache_miss();

    let mut sql = format!(
        r#"
SELECT
    ifNull(judge_refresh_debate_session_id, '') AS debate_session_id,
    ifNull(judge_refresh_source_event_type, '') AS source_event_type,
    toUInt64(count()) AS total_runs,
    toUInt64(countIf(judge_refresh_result = 'success')) AS success_runs,
    toUInt64(countIf(judge_refresh_result = 'failure')) AS failure_runs,
    round(if(count() = 0, 0, countIf(judge_refresh_result = 'success') * 100.0 / count()), 2) AS success_rate,
    round(avg(toFloat64(ifNull(judge_refresh_attempts, 0))), 2) AS avg_attempts,
    round(avg(toFloat64(ifNull(judge_refresh_retry_count, 0))), 2) AS avg_retry_count,
    round(avg(toFloat64(ifNull(judge_refresh_coalesced_events, 0))), 2) AS avg_coalesced_events,
    toInt64(toUnixTimestamp64Milli(max(server_ts))) AS last_seen_at_ms
FROM analytics_events
WHERE event_type = 'judge_realtime_refresh'
  AND server_ts >= now64(3) - toIntervalHour({})
"#,
        hours
    );

    if let Some(session_id) = session_filter {
        sql.push_str(&format!(
            "  AND judge_refresh_debate_session_id = '{}'\n",
            session_id
        ));
    }

    sql.push_str(&format!(
        r#"GROUP BY judge_refresh_debate_session_id, judge_refresh_source_event_type
ORDER BY last_seen_at_ms DESC
LIMIT {}
"#,
        limit
    ));

    let query_start = std::time::Instant::now();
    let query_result: Result<Vec<JudgeRefreshSummaryItem>, AppError> = async {
        let mut cursor = state
            .client
            .query(sql.as_str())
            .fetch::<JudgeRefreshSummaryItem>()?;
        let mut rows = Vec::new();
        while let Some(row) = cursor.next().await? {
            rows.push(row);
        }
        Ok(rows)
    }
    .await;
    let query_latency_ms = duration_to_millis_u64(query_start.elapsed());
    let rows = match query_result {
        Ok(v) => {
            state
                .judge_refresh_summary_metrics
                .observe_db_success(query_latency_ms);
            v
        }
        Err(err) => {
            state
                .judge_refresh_summary_metrics
                .observe_db_error(query_latency_ms);
            return Err(err);
        }
    };

    let output = GetJudgeRefreshSummaryOutput {
        window_hours: hours,
        limit,
        rows,
    };
    state
        .judge_refresh_summary_cache
        .insert(cache_key, (now_ms, output.clone()));
    Ok(Json(output))
}

/// Query auth login/register/logout event summary with account-type semantics.
#[utoipa::path(
    get,
    path = "/api/auth/summary",
    params(
        AuthEventSummaryQuery
    ),
    responses(
        (status = 200, description = "Auth event summary", body = GetAuthEventSummaryOutput),
        (status = 500, description = "Internal server error", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_auth_event_summary_handler(
    State(state): State<AppState>,
    Query(input): Query<AuthEventSummaryQuery>,
) -> Result<impl IntoResponse, AppError> {
    let hours = normalize_hours(input.hours);
    let limit = normalize_auth_summary_limit(input.limit);
    let summary_sql = build_auth_event_summary_sql(hours, limit);
    let quality_sql = build_auth_event_quality_sql(hours);

    let mut summary_cursor = state
        .client
        .query(summary_sql.as_str())
        .fetch::<AuthEventSummaryItem>()?;
    let mut rows = Vec::new();
    while let Some(row) = summary_cursor.next().await? {
        rows.push(row);
    }

    let mut quality_cursor = state
        .client
        .query(quality_sql.as_str())
        .fetch::<AuthEventQualityRow>()?;
    let quality = quality_cursor.next().await?.unwrap_or_default();

    Ok(Json(GetAuthEventSummaryOutput {
        window_hours: hours,
        limit,
        rows,
        legacy_email_events: quality.legacy_email_events,
        missing_account_type_events: quality.missing_account_type_events,
        missing_account_identifier_hash_events: quality.missing_account_identifier_hash_events,
    }))
}

/// Read in-memory metrics snapshot for judge refresh summary endpoint.
#[utoipa::path(
    get,
    path = "/api/judge-refresh/summary/metrics",
    responses(
        (status = 200, description = "Judge refresh summary metrics", body = GetJudgeRefreshSummaryMetricsOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_judge_refresh_summary_metrics_handler(
    State(state): State<AppState>,
) -> Result<impl IntoResponse, AppError> {
    Ok(Json(state.judge_refresh_summary_metrics.snapshot()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalize_hours_should_clamp_range() {
        assert_eq!(normalize_hours(None), 24);
        assert_eq!(normalize_hours(Some(0)), 1);
        assert_eq!(normalize_hours(Some(1)), 1);
        assert_eq!(normalize_hours(Some(300)), 168);
    }

    #[test]
    fn normalize_limit_should_clamp_range() {
        assert_eq!(normalize_limit(None), 20);
        assert_eq!(normalize_limit(Some(0)), 1);
        assert_eq!(normalize_limit(Some(1)), 1);
        assert_eq!(normalize_limit(Some(999)), 200);
    }

    #[test]
    fn normalize_auth_summary_limit_should_clamp_range() {
        assert_eq!(normalize_auth_summary_limit(None), 20);
        assert_eq!(normalize_auth_summary_limit(Some(0)), 1);
        assert_eq!(normalize_auth_summary_limit(Some(1)), 1);
        assert_eq!(normalize_auth_summary_limit(Some(999)), 200);
    }

    #[test]
    fn build_summary_cache_key_should_include_dimensions() {
        assert_eq!(
            build_summary_cache_key(24, 20, None),
            "h=24|l=20|sid=*".to_string()
        );
        assert_eq!(
            build_summary_cache_key(24, 20, Some(42)),
            "h=24|l=20|sid=42".to_string()
        );
    }

    #[test]
    fn build_auth_event_summary_sql_should_prefer_new_fields_and_fallback_to_legacy_email() {
        let sql = build_auth_event_summary_sql(24, 20);
        assert!(sql.contains("login_account_type"));
        assert!(sql.contains("logout_account_type"));
        assert!(sql.contains("register_account_type"));
        assert!(sql.contains("login_email"));
        assert!(sql.contains("logout_email"));
        assert!(sql.contains("register_email"));
        assert!(sql.contains("toIntervalHour(24)"));
        assert!(sql.contains("LIMIT 20"));
    }

    #[test]
    fn build_auth_event_quality_sql_should_track_legacy_and_missing_new_semantics() {
        let sql = build_auth_event_quality_sql(72);
        assert!(sql.contains("legacy_email_events"));
        assert!(sql.contains("missing_account_type_events"));
        assert!(sql.contains("missing_account_identifier_hash_events"));
        assert!(sql.contains("login_account_identifier_hash"));
        assert!(sql.contains("logout_account_identifier_hash"));
        assert!(sql.contains("register_account_identifier_hash"));
        assert!(sql.contains("toIntervalHour(72)"));
    }

    #[test]
    fn is_cache_fresh_should_follow_ttl_boundary() {
        assert!(!is_cache_fresh(1000, 2000, 0));
        assert!(is_cache_fresh(1000, 1500, 500));
        assert!(is_cache_fresh(1000, 1000, 500));
        assert!(!is_cache_fresh(1000, 1501, 500));
        assert!(!is_cache_fresh(2000, 1000, 500));
    }

    #[test]
    fn duration_to_millis_u64_should_convert() {
        assert_eq!(
            duration_to_millis_u64(std::time::Duration::from_millis(123)),
            123
        );
    }

    #[test]
    fn judge_refresh_summary_metrics_snapshot_should_calculate_stats() {
        let metrics = JudgeRefreshSummaryMetrics::default();
        metrics.observe_cache_hit();
        metrics.observe_cache_miss();
        metrics.observe_db_success(20);
        metrics.observe_db_error(40);
        let snapshot = metrics.snapshot();
        assert_eq!(snapshot.request_total, 2);
        assert_eq!(snapshot.cache_hit_total, 1);
        assert_eq!(snapshot.cache_miss_total, 1);
        assert_eq!(snapshot.db_query_total, 2);
        assert_eq!(snapshot.db_error_total, 1);
        assert_eq!(snapshot.last_db_latency_ms, 40);
        assert_eq!(snapshot.cache_hit_rate, 50.0);
        assert_eq!(snapshot.avg_db_latency_ms, 30.0);
    }
}
