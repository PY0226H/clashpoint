use crate::{AppError, AppState, ErrorOutput};
use anyhow::Context;
use axum::{
    body::Body,
    extract::{Query, State},
    http::{header, HeaderMap, HeaderValue, StatusCode},
    response::{IntoResponse, Response},
    Json,
};
use serde::{de::DeserializeOwned, Deserialize, Serialize};
use std::time::Duration;
use utoipa::{IntoParams, ToSchema};

#[derive(Debug, Deserialize, Serialize, IntoParams)]
#[serde(rename_all = "camelCase")]
pub(crate) struct JudgeRefreshSummaryQuery {
    /// Time window in hours, clamped to [1, 168], default 24.
    pub hours: Option<u32>,
    /// Max grouped rows returned, clamped to [1, 200], default 20.
    pub limit: Option<u32>,
    /// Optional debate session filter.
    pub debate_session_id: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
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

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub(crate) struct JudgeRefreshSummaryOutput {
    pub window_hours: u32,
    pub limit: u32,
    pub rows: Vec<JudgeRefreshSummaryItem>,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub(crate) struct JudgeRefreshSummaryMetricsOutput {
    pub request_total: u64,
    pub cache_hit_total: u64,
    pub cache_miss_total: u64,
    pub cache_hit_rate: f64,
    pub db_query_total: u64,
    pub db_error_total: u64,
    pub avg_db_latency_ms: f64,
    pub last_db_latency_ms: u64,
}

/// Proxy endpoint for judge refresh summary query, routed through chat_server main API ingress.
#[utoipa::path(
    get,
    path = "/api/analytics/judge-refresh/summary",
    params(
        JudgeRefreshSummaryQuery
    ),
    responses(
        (status = 200, description = "Judge refresh summary", body = JudgeRefreshSummaryOutput),
        (status = 403, description = "Unauthorized", body = ErrorOutput),
        (status = 503, description = "Analytics ingress disabled", body = ErrorOutput),
        (status = 502, description = "Analytics upstream unavailable", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_analytics_judge_refresh_summary_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(input): Query<JudgeRefreshSummaryQuery>,
) -> Result<impl IntoResponse, AppError> {
    if !state.config.analytics.enabled {
        return Ok((
            StatusCode::SERVICE_UNAVAILABLE,
            Json(ErrorOutput::new("analytics_ingress_disabled")),
        )
            .into_response());
    }
    proxy_get_json::<JudgeRefreshSummaryOutput, _>(
        &state,
        &headers,
        "/api/judge-refresh/summary",
        Some(&input),
    )
    .await
}

/// Proxy endpoint for judge refresh summary metrics query, routed through chat_server main API ingress.
#[utoipa::path(
    get,
    path = "/api/analytics/judge-refresh/summary/metrics",
    responses(
        (status = 200, description = "Judge refresh summary metrics", body = JudgeRefreshSummaryMetricsOutput),
        (status = 403, description = "Unauthorized", body = ErrorOutput),
        (status = 503, description = "Analytics ingress disabled", body = ErrorOutput),
        (status = 502, description = "Analytics upstream unavailable", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_analytics_judge_refresh_summary_metrics_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, AppError> {
    if !state.config.analytics.enabled {
        return Ok((
            StatusCode::SERVICE_UNAVAILABLE,
            Json(ErrorOutput::new("analytics_ingress_disabled")),
        )
            .into_response());
    }
    proxy_get_json::<JudgeRefreshSummaryMetricsOutput, JudgeRefreshSummaryQuery>(
        &state,
        &headers,
        "/api/judge-refresh/summary/metrics",
        None,
    )
    .await
}

async fn proxy_get_json<T, Q>(
    state: &AppState,
    headers: &HeaderMap,
    upstream_path: &str,
    query: Option<&Q>,
) -> Result<Response, AppError>
where
    T: DeserializeOwned + Serialize,
    Q: Serialize + ?Sized,
{
    let timeout_ms = state.config.analytics.timeout_ms.max(1);
    let client = reqwest::Client::new();
    let mut request = client
        .get(build_analytics_url(
            state.config.analytics.base_url.as_str(),
            upstream_path,
        ))
        .timeout(Duration::from_millis(timeout_ms));
    if let Some(auth_value) = headers.get(header::AUTHORIZATION) {
        request = request.header(header::AUTHORIZATION, auth_value);
    }
    if let Some(query_value) = query {
        request = request.query(query_value);
    }

    let upstream = request
        .send()
        .await
        .context("analytics proxy request failed")?;
    let status =
        StatusCode::from_u16(upstream.status().as_u16()).unwrap_or(StatusCode::BAD_GATEWAY);
    if !status.is_success() {
        let content_type = upstream.headers().get(header::CONTENT_TYPE).cloned();
        let payload = upstream
            .bytes()
            .await
            .context("read analytics proxy error response failed")?;
        return Ok(forward_upstream_response(
            status,
            content_type,
            payload.to_vec(),
        ));
    }
    let payload = upstream
        .json::<T>()
        .await
        .context("decode analytics proxy response failed")?;
    Ok((status, Json(payload)).into_response())
}

fn forward_upstream_response(
    status: StatusCode,
    content_type: Option<HeaderValue>,
    payload: Vec<u8>,
) -> Response {
    let mut response = Response::new(Body::from(payload));
    *response.status_mut() = status;
    if let Some(value) = content_type {
        response.headers_mut().insert(header::CONTENT_TYPE, value);
    }
    response
}

fn build_analytics_url(base_url: &str, path: &str) -> String {
    let base = base_url.trim().trim_end_matches('/');
    let route = path.trim_start_matches('/');
    format!("{base}/{route}")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn build_analytics_url_should_join_cleanly() {
        assert_eq!(
            build_analytics_url("http://127.0.0.1:6690", "/api/judge-refresh/summary"),
            "http://127.0.0.1:6690/api/judge-refresh/summary"
        );
        assert_eq!(
            build_analytics_url("http://127.0.0.1:6690/", "api/judge-refresh/summary"),
            "http://127.0.0.1:6690/api/judge-refresh/summary"
        );
        assert_eq!(
            build_analytics_url(" http://127.0.0.1:6690/api ", "/judge-refresh/summary"),
            "http://127.0.0.1:6690/api/judge-refresh/summary"
        );
    }

    #[test]
    fn forward_upstream_response_should_keep_status_and_content_type() {
        let response = forward_upstream_response(
            StatusCode::FORBIDDEN,
            Some(HeaderValue::from_static("application/json")),
            br#"{"error":"forbidden"}"#.to_vec(),
        );
        assert_eq!(response.status(), StatusCode::FORBIDDEN);
        assert_eq!(
            response.headers().get(header::CONTENT_TYPE),
            Some(&HeaderValue::from_static("application/json"))
        );
    }
}
