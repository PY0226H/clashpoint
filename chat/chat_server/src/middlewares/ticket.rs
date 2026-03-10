use crate::AppState;
use axum::{
    extract::{FromRequestParts, Query, Request, State},
    http::StatusCode,
    middleware::Next,
    response::{IntoResponse, Response},
};
use serde::Deserialize;
use tracing::warn;

#[derive(Debug, Deserialize)]
struct Params {
    token: String,
}

pub async fn verify_file_ticket(
    State(state): State<AppState>,
    req: Request,
    next: Next,
) -> Response {
    let (mut parts, body) = req.into_parts();
    let token = match Query::<Params>::from_request_parts(&mut parts, &state).await {
        Ok(params) => params.token.clone(),
        Err(e) => {
            let msg = format!("parse file ticket from query failed: {}", e);
            warn!(msg);
            return (StatusCode::UNAUTHORIZED, msg).into_response();
        }
    };

    let user = match state.dk.verify_file_ticket(&token) {
        Ok(user) => user,
        Err(e) => {
            let msg = format!("verify file ticket failed: {}", e);
            warn!(msg);
            return (StatusCode::FORBIDDEN, msg).into_response();
        }
    };

    let mut req = Request::from_parts(parts, body);
    req.extensions_mut().insert(user);
    next.run(req).await
}

#[cfg(test)]
mod tests {
    use super::*;
    use anyhow::Result;
    use axum::{body::Body, routing::get, Router};
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
            ai_judge: crate::config::AiJudgeConfig::default(),
            analytics: crate::config::AnalyticsIngressConfig::default(),
            worker_runtime: crate::config::WorkerRuntimeConfig::default(),
            payment: crate::config::PaymentConfig::default(),
        };
        Ok(AppState::new_for_unit_test(config)?)
    }

    #[tokio::test]
    async fn verify_file_ticket_middleware_should_only_accept_file_ticket_query() -> Result<()> {
        let state = test_state()?;
        let mut user = chat_core::User::new(1, "Tyr Chen", "tchen@acme.org");
        user.ws_id = 1;
        user.ws_name = "acme".to_string();
        let user_token =
            state
                .ek
                .sign_access_token(user.id, user.ws_id, "sid-file-ticket-test", 0)?;
        let file_ticket = state.ek.sign_file_ticket(user, 300)?;

        let app = Router::new()
            .route("/", get(handler))
            .layer(axum::middleware::from_fn_with_state(
                state.clone(),
                verify_file_ticket,
            ))
            .with_state(state);

        let req = Request::builder()
            .uri(format!("/?token={}", file_ticket))
            .body(Body::empty())?;
        let res = app.clone().oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::OK);

        let req = Request::builder()
            .uri(format!("/?token={}", user_token))
            .body(Body::empty())?;
        let res = app.clone().oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::FORBIDDEN);

        let req = Request::builder()
            .uri("/")
            .header("Authorization", format!("Bearer {}", file_ticket))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::UNAUTHORIZED);

        Ok(())
    }
}
