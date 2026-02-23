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

pub async fn verify_notify_ticket(
    State(state): State<AppState>,
    req: Request,
    next: Next,
) -> Response {
    let (mut parts, body) = req.into_parts();
    let token = match Query::<Params>::from_request_parts(&mut parts, &state).await {
        Ok(params) => params.token.clone(),
        Err(e) => {
            let msg = format!("parse notify ticket from query failed: {}", e);
            warn!(msg);
            return (StatusCode::UNAUTHORIZED, msg).into_response();
        }
    };

    let user = match state.dk.verify_notify_ticket(&token) {
        Ok(user) => user,
        Err(e) => {
            let msg = format!("verify notify ticket failed: {}", e);
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
    use chat_core::EncodingKey;
    use tower::ServiceExt;

    async fn handler(_req: Request) -> impl IntoResponse {
        (StatusCode::OK, "ok")
    }

    fn test_state() -> Result<AppState> {
        let config = crate::AppConfig {
            server: crate::config::ServerConfig {
                port: 0,
                db_url: "postgres://localhost:5432/chat".to_string(),
            },
            auth: crate::config::AuthConfig {
                pk: include_str!("../../chat_core/fixtures/decoding.pem").to_string(),
            },
        };
        Ok(AppState::new(config))
    }

    #[tokio::test]
    async fn verify_notify_ticket_middleware_should_only_accept_notify_ticket_query() -> Result<()>
    {
        let state = test_state()?;
        let ek = EncodingKey::load(include_str!("../../chat_core/fixtures/encoding.pem"))?;
        let user = chat_core::User::new(1, "Tyr Chen", "tchen@acme.org");
        let user_token = ek.sign(user.clone())?;
        let notify_ticket = ek.sign_notify_ticket(user, 300)?;

        let app = Router::new()
            .route("/", get(handler))
            .layer(axum::middleware::from_fn_with_state(
                state.clone(),
                verify_notify_ticket,
            ))
            .with_state(state);

        let req = Request::builder()
            .uri(format!("/?token={}", notify_ticket))
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
            .header("Authorization", format!("Bearer {}", notify_ticket))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::UNAUTHORIZED);

        Ok(())
    }

    #[tokio::test]
    async fn verify_notify_ticket_middleware_should_return_401_when_missing_query_token(
    ) -> Result<()> {
        let state = test_state()?;
        let app = Router::new()
            .route("/", get(handler))
            .layer(axum::middleware::from_fn_with_state(
                state.clone(),
                verify_notify_ticket,
            ))
            .with_state(state);

        let req = Request::builder().uri("/").body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::UNAUTHORIZED);
        Ok(())
    }
}
