use crate::{
    AppError, AppState, SubmitJudgeFailedCallbackInput, SubmitJudgeFinalReportInput,
    SubmitJudgePhaseReportInput,
};
use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use std::{
    sync::{
        atomic::{AtomicU64, Ordering},
        LazyLock,
    },
    time::Instant,
};
use tracing::info;

#[derive(Debug, Default)]
struct RedisHealthProbeMetrics {
    request_total: AtomicU64,
    status_disabled_total: AtomicU64,
    status_ready_total: AtomicU64,
    status_degraded_total: AtomicU64,
    cache_hit_total: AtomicU64,
    latency_ms_total: AtomicU64,
    latency_ms_samples_total: AtomicU64,
}

impl RedisHealthProbeMetrics {
    fn observe_start(&self) {
        self.request_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_result(&self, status: &str, cache_hit: bool, latency_ms: u64) {
        match status {
            "disabled" => {
                self.status_disabled_total.fetch_add(1, Ordering::Relaxed);
            }
            "ready" => {
                self.status_ready_total.fetch_add(1, Ordering::Relaxed);
            }
            "degraded" => {
                self.status_degraded_total.fetch_add(1, Ordering::Relaxed);
            }
            _ => {}
        }
        if cache_hit {
            self.cache_hit_total.fetch_add(1, Ordering::Relaxed);
        }
        self.latency_ms_total
            .fetch_add(latency_ms, Ordering::Relaxed);
        self.latency_ms_samples_total
            .fetch_add(1, Ordering::Relaxed);
    }
}

static REDIS_HEALTH_PROBE_METRICS: LazyLock<RedisHealthProbeMetrics> =
    LazyLock::new(RedisHealthProbeMetrics::default);

/// Internal callback for AI service to persist v3 phase report.
#[utoipa::path(
    post,
    path = "/api/internal/ai/judge/v3/phase/jobs/{id}/report",
    params(
        ("id" = u64, Path, description = "Judge phase job id")
    ),
    request_body = SubmitJudgePhaseReportInput,
    responses(
        (status = 200, description = "Judge phase report persisted", body = crate::SubmitJudgePhaseReportOutput),
        (status = 401, description = "Missing or invalid internal key", body = ErrorOutput),
        (status = 400, description = "Invalid input", body = ErrorOutput),
        (status = 404, description = "Judge phase job not found", body = ErrorOutput),
        (status = 409, description = "Job state conflict", body = ErrorOutput),
        (status = 500, description = "Internal server error", body = ErrorOutput),
    ),
    security(
        ("internal_key" = [])
    )
)]
pub(crate) async fn submit_judge_phase_report_handler(
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Json(input): Json<SubmitJudgePhaseReportInput>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.submit_judge_phase_report(id, input).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Internal callback for AI service to persist v3 final report.
#[utoipa::path(
    post,
    path = "/api/internal/ai/judge/v3/final/jobs/{id}/report",
    params(
        ("id" = u64, Path, description = "Judge final job id")
    ),
    request_body = SubmitJudgeFinalReportInput,
    responses(
        (status = 200, description = "Judge final report persisted", body = crate::SubmitJudgeFinalReportOutput),
        (status = 401, description = "Missing or invalid internal key", body = ErrorOutput),
        (status = 400, description = "Invalid input", body = ErrorOutput),
        (status = 404, description = "Judge final job not found", body = ErrorOutput),
        (status = 409, description = "Job state conflict", body = ErrorOutput),
        (status = 500, description = "Internal server error", body = ErrorOutput),
    ),
    security(
        ("internal_key" = [])
    )
)]
pub(crate) async fn submit_judge_final_report_handler(
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Json(input): Json<SubmitJudgeFinalReportInput>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.submit_judge_final_report(id, input).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Internal callback for AI service to persist v3 phase failed callback.
#[utoipa::path(
    post,
    path = "/api/internal/ai/judge/v3/phase/jobs/{id}/failed",
    params(
        ("id" = u64, Path, description = "Judge phase job id")
    ),
    request_body = SubmitJudgeFailedCallbackInput,
    responses(
        (status = 200, description = "Judge phase failed callback persisted", body = crate::SubmitJudgeFailedCallbackOutput),
        (status = 401, description = "Missing or invalid internal key", body = ErrorOutput),
        (status = 400, description = "Invalid input", body = ErrorOutput),
        (status = 404, description = "Judge phase job not found", body = ErrorOutput),
        (status = 409, description = "Job state conflict", body = ErrorOutput),
        (status = 500, description = "Internal server error", body = ErrorOutput),
    ),
    security(
        ("internal_key" = [])
    )
)]
pub(crate) async fn submit_judge_phase_failed_handler(
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Json(input): Json<SubmitJudgeFailedCallbackInput>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.submit_judge_phase_failed_callback(id, input).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Internal callback for AI service to persist v3 final failed callback.
#[utoipa::path(
    post,
    path = "/api/internal/ai/judge/v3/final/jobs/{id}/failed",
    params(
        ("id" = u64, Path, description = "Judge final job id")
    ),
    request_body = SubmitJudgeFailedCallbackInput,
    responses(
        (status = 200, description = "Judge final failed callback persisted", body = crate::SubmitJudgeFailedCallbackOutput),
        (status = 401, description = "Missing or invalid internal key", body = ErrorOutput),
        (status = 400, description = "Invalid input", body = ErrorOutput),
        (status = 404, description = "Judge final job not found", body = ErrorOutput),
        (status = 409, description = "Job state conflict", body = ErrorOutput),
        (status = 500, description = "Internal server error", body = ErrorOutput),
    ),
    security(
        ("internal_key" = [])
    )
)]
pub(crate) async fn submit_judge_final_failed_handler(
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Json(input): Json<SubmitJudgeFailedCallbackInput>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.submit_judge_final_failed_callback(id, input).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Internal endpoint to inspect in-memory AI judge dispatch worker metrics.
#[utoipa::path(
    get,
    path = "/api/internal/ai/judge/dispatch/metrics",
    responses(
        (status = 200, description = "Dispatch worker metrics snapshot", body = GetJudgeDispatchMetricsOutput),
        (status = 401, description = "Missing or invalid internal key"),
    ),
    security(
        ("internal_key" = [])
    )
)]
pub(crate) async fn get_judge_dispatch_metrics_handler(
    State(state): State<AppState>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.get_judge_dispatch_metrics();
    Ok((StatusCode::OK, Json(ret)))
}

/// Internal endpoint to inspect redis readiness and startup policy status.
#[utoipa::path(
    get,
    path = "/api/internal/ai/infra/redis/health",
    responses(
        (status = 200, description = "Redis infra health snapshot", body = crate::RedisHealthOutput),
        (status = 401, description = "Missing or invalid internal key"),
    ),
    security(
        ("internal_key" = [])
    )
)]
pub(crate) async fn get_redis_health_handler(
    State(state): State<AppState>,
) -> Result<impl IntoResponse, AppError> {
    REDIS_HEALTH_PROBE_METRICS.observe_start();
    let started = Instant::now();
    let ret = state.get_redis_health().await;
    let latency_ms = started.elapsed().as_millis().min(u64::MAX as u128) as u64;
    REDIS_HEALTH_PROBE_METRICS.observe_result(&ret.status, ret.cache_hit, latency_ms);
    info!(
        enabled = ret.enabled,
        ready = ret.ready,
        status = %ret.status,
        reason_code = %ret.reason_code,
        cache_hit = ret.cache_hit,
        checked_at_ms = ret.checked_at_ms,
        ping_latency_ms = ret.ping_latency_ms,
        handler_latency_ms = latency_ms,
        "internal redis health snapshot served"
    );
    Ok((StatusCode::OK, Json(ret)))
}

/// Internal endpoint to expose strict redis readiness status for platform probes.
#[utoipa::path(
    get,
    path = "/api/internal/ai/infra/redis/ready",
    responses(
        (status = 204, description = "Redis ready"),
        (status = 503, description = "Redis not ready", body = crate::RedisHealthOutput),
        (status = 401, description = "Missing or invalid internal key"),
    ),
    security(
        ("internal_key" = [])
    )
)]
pub(crate) async fn get_redis_ready_handler(
    State(state): State<AppState>,
) -> Result<impl IntoResponse, AppError> {
    let health = state.get_redis_health().await;
    if health.ready {
        return Ok(StatusCode::NO_CONTENT.into_response());
    }
    Ok((StatusCode::SERVICE_UNAVAILABLE, Json(health)).into_response())
}

/// Internal endpoint to inspect auth consistency metrics and retry queue health.
#[utoipa::path(
    get,
    path = "/api/internal/ai/auth/consistency/metrics",
    responses(
        (status = 200, description = "Auth consistency metrics snapshot", body = crate::GetAuthConsistencyMetricsOutput),
        (status = 401, description = "Missing or invalid internal key"),
    ),
    security(
        ("internal_key" = [])
    )
)]
pub(crate) async fn get_auth_consistency_metrics_handler(
    State(state): State<AppState>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.get_auth_consistency_metrics();
    Ok((StatusCode::OK, Json(ret)))
}

#[cfg(test)]
mod tests {
    use super::*;
    use anyhow::Result;
    use axum::{body::Body, http::Request, middleware::from_fn_with_state, routing::get, Router};
    use std::path::PathBuf;
    use tower::ServiceExt;

    fn test_state() -> Result<AppState> {
        let config = crate::AppConfig {
            server: crate::config::ServerConfig {
                port: 0,
                db_url: "postgres://localhost:5432/chat".to_string(),
                base_dir: PathBuf::from("/tmp/chat"),
                forwarded_header_trust: crate::config::ServerForwardedHeaderTrustConfig::default(),
            },
            auth: crate::config::AuthConfig {
                sk: include_str!("../../../chat_core/fixtures/encoding.pem").to_string(),
                pk: include_str!("../../../chat_core/fixtures/decoding.pem").to_string(),
            },
            kafka: crate::config::KafkaConfig::default(),
            redis: crate::config::RedisConfig::default(),
            ai_judge: crate::config::AiJudgeConfig {
                internal_key: "secret-key".to_string(),
                ..Default::default()
            },
            analytics: crate::config::AnalyticsIngressConfig::default(),
            worker_runtime: crate::config::WorkerRuntimeConfig::default(),
            payment: crate::config::PaymentConfig::default(),
        };
        Ok(AppState::new_for_unit_test(config)?)
    }

    #[tokio::test]
    async fn get_judge_dispatch_metrics_handler_should_require_internal_key_and_return_snapshot(
    ) -> Result<()> {
        let state = test_state()?;
        let app = Router::new()
            .route("/metrics", get(get_judge_dispatch_metrics_handler))
            .layer(from_fn_with_state(
                state.clone(),
                crate::verify_ai_internal_key,
            ))
            .with_state(state);

        let unauthorized = app
            .clone()
            .oneshot(Request::builder().uri("/metrics").body(Body::empty())?)
            .await?;
        assert_eq!(unauthorized.status(), StatusCode::UNAUTHORIZED);

        let authorized = app
            .oneshot(
                Request::builder()
                    .uri("/metrics")
                    .header("x-ai-internal-key", "secret-key")
                    .body(Body::empty())?,
            )
            .await?;
        assert_eq!(authorized.status(), StatusCode::OK);

        let body = axum::body::to_bytes(authorized.into_body(), usize::MAX).await?;
        let payload: crate::GetJudgeDispatchMetricsOutput = serde_json::from_slice(&body)?;
        assert_eq!(payload.tick_success_total, 0);
        assert_eq!(payload.tick_error_total, 0);
        assert_eq!(payload.phase_tick_success_total, 0);
        assert_eq!(payload.final_tick_success_total, 0);
        assert_eq!(payload.trigger_polling_total, 0);
        assert_eq!(payload.trigger_event_total, 0);
        assert_eq!(payload.failed_total, 0);
        assert_eq!(payload.timed_out_failed_total, 0);
        assert_eq!(payload.failed_http_unexpected_total, 0);
        assert_eq!(payload.queued_phase_jobs, 0);
        assert_eq!(payload.queued_final_jobs, 0);
        assert_eq!(payload.dispatch_success_rate_pct, 0.0);
        Ok(())
    }

    #[tokio::test]
    async fn get_redis_health_handler_should_require_internal_key_and_return_snapshot() -> Result<()>
    {
        let state = test_state()?;
        let app = Router::new()
            .route("/infra/redis/health", get(get_redis_health_handler))
            .layer(from_fn_with_state(
                state.clone(),
                crate::verify_ai_internal_key,
            ))
            .with_state(state);

        let unauthorized = app
            .clone()
            .oneshot(
                Request::builder()
                    .uri("/infra/redis/health")
                    .body(Body::empty())?,
            )
            .await?;
        assert_eq!(unauthorized.status(), StatusCode::UNAUTHORIZED);

        let authorized = app
            .oneshot(
                Request::builder()
                    .uri("/infra/redis/health")
                    .header("x-ai-internal-key", "secret-key")
                    .body(Body::empty())?,
            )
            .await?;
        assert_eq!(authorized.status(), StatusCode::OK);
        let body = axum::body::to_bytes(authorized.into_body(), usize::MAX).await?;
        let payload: crate::RedisHealthOutput = serde_json::from_slice(&body)?;
        assert_eq!(payload.status, "disabled");
        assert!(!payload.ready);
        assert!(!payload.enabled);
        assert_eq!(payload.reason_code, "redis_disabled_by_config");
        assert_eq!(payload.timeout_ms, 500);
        assert!(!payload.cache_hit);
        Ok(())
    }

    #[tokio::test]
    async fn get_redis_ready_handler_should_return_503_when_redis_not_ready() -> Result<()> {
        let state = test_state()?;
        let app = Router::new()
            .route("/infra/redis/ready", get(get_redis_ready_handler))
            .layer(from_fn_with_state(
                state.clone(),
                crate::verify_ai_internal_key,
            ))
            .with_state(state);

        let unauthorized = app
            .clone()
            .oneshot(
                Request::builder()
                    .uri("/infra/redis/ready")
                    .body(Body::empty())?,
            )
            .await?;
        assert_eq!(unauthorized.status(), StatusCode::UNAUTHORIZED);

        let authorized = app
            .oneshot(
                Request::builder()
                    .uri("/infra/redis/ready")
                    .header("x-ai-internal-key", "secret-key")
                    .body(Body::empty())?,
            )
            .await?;
        assert_eq!(authorized.status(), StatusCode::SERVICE_UNAVAILABLE);
        Ok(())
    }

    #[tokio::test]
    async fn get_auth_consistency_metrics_handler_should_require_internal_key_and_return_snapshot(
    ) -> Result<()> {
        let state = test_state()?;
        let app = Router::new()
            .route(
                "/auth/consistency/metrics",
                get(get_auth_consistency_metrics_handler),
            )
            .layer(from_fn_with_state(
                state.clone(),
                crate::verify_ai_internal_key,
            ))
            .with_state(state);

        let unauthorized = app
            .clone()
            .oneshot(
                Request::builder()
                    .uri("/auth/consistency/metrics")
                    .body(Body::empty())?,
            )
            .await?;
        assert_eq!(unauthorized.status(), StatusCode::UNAUTHORIZED);

        let authorized = app
            .oneshot(
                Request::builder()
                    .uri("/auth/consistency/metrics")
                    .header("x-ai-internal-key", "secret-key")
                    .body(Body::empty())?,
            )
            .await?;
        assert_eq!(authorized.status(), StatusCode::OK);
        let body = axum::body::to_bytes(authorized.into_body(), usize::MAX).await?;
        let payload: crate::GetAuthConsistencyMetricsOutput = serde_json::from_slice(&body)?;
        assert_eq!(payload.token_version_retry_queue_depth, 0);
        Ok(())
    }
}
