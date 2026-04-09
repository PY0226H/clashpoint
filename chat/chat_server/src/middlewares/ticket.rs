use crate::{
    handlers::{ensure_access_session_active, load_user_token_version},
    AppError, AppState,
};
use axum::{
    extract::{FromRequestParts, Query, Request, State},
    http::StatusCode,
    middleware::Next,
    response::{IntoResponse, Response},
};
use serde::Deserialize;
use std::{
    collections::hash_map::DefaultHasher,
    hash::{Hash, Hasher},
};
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

    let decoded = match state.dk.verify_file_ticket_decoded(&token) {
        Ok(decoded) => decoded,
        Err(e) => {
            let msg = format!("verify file ticket failed: {}", e);
            warn!(msg);
            return (StatusCode::FORBIDDEN, msg).into_response();
        }
    };
    if decoded.sid != "ticket-legacy" {
        match verify_ticket_session_consistency(&state, decoded.user.id, &decoded.sid, decoded.ver)
            .await
        {
            Ok(()) => {}
            Err(msg) => {
                warn!(
                    user_id = decoded.user.id,
                    sid_hash = hash_for_log(&decoded.sid),
                    jti_hash = hash_for_log(&decoded.jti),
                    "verify file ticket session consistency failed"
                );
                return (StatusCode::FORBIDDEN, msg).into_response();
            }
        }
    }
    tracing::info!(
        user_id = decoded.user.id,
        sid_hash = hash_for_log(&decoded.sid),
        jti_hash = hash_for_log(&decoded.jti),
        token_version = decoded.ver,
        "verify file ticket success"
    );

    let mut req = Request::from_parts(parts, body);
    req.extensions_mut().insert(decoded.user);
    next.run(req).await
}

async fn verify_ticket_session_consistency(
    state: &AppState,
    user_id: i64,
    sid: &str,
    ver: i64,
) -> Result<(), &'static str> {
    let current_ver = load_user_token_version(state, user_id)
        .await
        .map_err(|_| "verify file ticket failed: ticket session check failed")?;
    if current_ver != ver {
        return Err("verify file ticket failed: token version mismatch");
    }
    ensure_access_session_active(state, user_id, sid)
        .await
        .map_err(|err| match err {
            AppError::AuthError(code) if code == "auth_session_revoked" => {
                "verify file ticket failed: auth session revoked"
            }
            _ => "verify file ticket failed: ticket session check failed",
        })?;
    Ok(())
}

fn hash_for_log(input: &str) -> String {
    let mut hasher = DefaultHasher::new();
    input.hash(&mut hasher);
    format!("{:016x}", hasher.finish())
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
                forwarded_header_trust: crate::config::ServerForwardedHeaderTrustConfig::default(),
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
        let user = chat_core::User::new(1, "Tyr Chen", "tchen@acme.org");
        let user_token = state
            .ek
            .sign_access_token(user.id, "sid-file-ticket-test", 0)?;
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

    #[tokio::test]
    async fn verify_file_ticket_middleware_should_enforce_session_consistency_for_scoped_ticket(
    ) -> Result<()> {
        let state = test_state()?;
        let user = chat_core::User::new(1, "Tyr Chen", "tchen@acme.org");
        let file_ticket = state.ek.sign_file_ticket_with_session(
            user.id,
            "sid-scoped-ticket",
            9,
            "jti-scoped",
            300,
        )?;

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
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::FORBIDDEN);
        Ok(())
    }
}
