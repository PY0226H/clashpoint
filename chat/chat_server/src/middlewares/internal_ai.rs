use crate::AppState;
use axum::{
    extract::{Request, State},
    http::{header::HeaderName, StatusCode},
    middleware::Next,
    response::{IntoResponse, Response},
};
use tracing::warn;

const AI_INTERNAL_KEY_HEADER: &str = "x-ai-internal-key";

pub async fn verify_ai_internal_key(
    State(state): State<AppState>,
    req: Request,
    next: Next,
) -> Response {
    let key = req
        .headers()
        .get(HeaderName::from_static(AI_INTERNAL_KEY_HEADER))
        .and_then(|v| v.to_str().ok())
        .map(str::trim)
        .unwrap_or_default();
    if key.is_empty() {
        warn!("missing ai internal key header");
        return (StatusCode::UNAUTHORIZED, "missing x-ai-internal-key").into_response();
    }
    if key != state.config.ai_judge.internal_key {
        warn!("invalid ai internal key header");
        return (StatusCode::UNAUTHORIZED, "invalid x-ai-internal-key").into_response();
    }
    next.run(req).await
}

#[cfg(test)]
mod tests {
    use super::*;
    use anyhow::Result;
    use axum::{body::Body, middleware::from_fn_with_state, routing::get, Router};
    use std::path::PathBuf;
    use tower::ServiceExt;

    async fn handler(_req: Request) -> impl IntoResponse {
        (StatusCode::OK, "ok")
    }

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
            payment: crate::config::PaymentConfig::default(),
        };
        Ok(AppState::new_for_unit_test(config)?)
    }

    #[tokio::test]
    async fn verify_ai_internal_key_middleware_should_work() -> Result<()> {
        let state = test_state()?;
        let app = Router::new()
            .route("/", get(handler))
            .layer(from_fn_with_state(state.clone(), verify_ai_internal_key))
            .with_state(state);

        let req = Request::builder()
            .uri("/")
            .header("x-ai-internal-key", "secret-key")
            .body(Body::empty())?;
        let res = app.clone().oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::OK);

        let req = Request::builder().uri("/").body(Body::empty())?;
        let res = app.clone().oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::UNAUTHORIZED);

        let req = Request::builder()
            .uri("/")
            .header("x-ai-internal-key", "wrong")
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::UNAUTHORIZED);

        Ok(())
    }
}
