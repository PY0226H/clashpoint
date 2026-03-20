use crate::{AppError, AppState, SubmitJudgeFinalReportInput, SubmitJudgePhaseReportInput};
use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::IntoResponse,
    Json,
};

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
        (status = 400, description = "Invalid input", body = ErrorOutput),
        (status = 404, description = "Judge phase job not found", body = ErrorOutput),
        (status = 409, description = "Job state conflict", body = ErrorOutput),
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
        (status = 400, description = "Invalid input", body = ErrorOutput),
        (status = 404, description = "Judge final job not found", body = ErrorOutput),
        (status = 409, description = "Job state conflict", body = ErrorOutput),
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
    let ret = state.get_redis_health().await;
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
        assert_eq!(payload.failed_total, 0);
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
        Ok(())
    }
}
