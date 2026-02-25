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
use tracing::info;
use utoipa::{IntoParams, ToSchema};

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

fn normalize_hours(v: Option<u32>) -> u32 {
    v.unwrap_or(24).clamp(1, 168)
}

fn normalize_limit(v: Option<u32>) -> u32 {
    v.unwrap_or(20).clamp(1, 200)
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

    let mut cursor = state
        .client
        .query(sql.as_str())
        .fetch::<JudgeRefreshSummaryItem>()?;
    let mut rows = Vec::new();
    while let Some(row) = cursor.next().await? {
        rows.push(row);
    }

    Ok(Json(GetJudgeRefreshSummaryOutput {
        window_hours: hours,
        limit,
        rows,
    }))
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
}
