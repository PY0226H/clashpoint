use crate::AppState;
use axum::{
    extract::{FromRequestParts, Query, Request, State},
    http::{HeaderMap, StatusCode},
    middleware::Next,
    response::{IntoResponse, Response},
    Json,
};
use serde::{Deserialize, Serialize};
use tracing::warn;

#[derive(Debug, Deserialize)]
struct Params {
    token: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct NotifyErrorOutput {
    pub error: String,
    pub message: String,
    pub request_id: String,
}

pub(crate) fn notify_error_response(
    status: StatusCode,
    error: impl Into<String>,
    message: impl Into<String>,
    request_id: impl Into<String>,
) -> Response {
    (
        status,
        Json(NotifyErrorOutput {
            error: error.into(),
            message: message.into(),
            request_id: request_id.into(),
        }),
    )
        .into_response()
}

pub async fn verify_notify_ticket(
    State(state): State<AppState>,
    req: Request,
    next: Next,
) -> Response {
    let (mut parts, body) = req.into_parts();
    let request_id = extract_request_id(&parts.headers);
    let token = match Query::<Params>::from_request_parts(&mut parts, &state).await {
        Ok(params) => params.token.clone(),
        Err(_) => {
            state.observe_sse_auth_unauthorized();
            warn!(
                request_id,
                "parse notify ticket from query failed: token is missing or malformed"
            );
            return notify_error_response(
                StatusCode::UNAUTHORIZED,
                "notify_ticket_missing_or_invalid_query",
                "missing or malformed notify ticket in query",
                request_id,
            );
        }
    };

    let user = match state.dk.verify_notify_ticket(&token) {
        Ok(user) => user,
        Err(err) => {
            state.observe_sse_auth_forbidden();
            warn!(
                request_id,
                err = %err,
                "verify notify ticket failed"
            );
            return notify_error_response(
                StatusCode::FORBIDDEN,
                "notify_ticket_invalid",
                "notify ticket is invalid or expired",
                request_id,
            );
        }
    };

    let mut req = Request::from_parts(parts, body);
    req.extensions_mut().insert(user);
    next.run(req).await
}

fn extract_request_id(headers: &HeaderMap) -> String {
    headers
        .get("x-request-id")
        .and_then(|v| v.to_str().ok())
        .map(str::trim)
        .filter(|v| !v.is_empty())
        .map(ToOwned::to_owned)
        .unwrap_or_else(|| format!("notify-{}", crate::now_unix_ms()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use anyhow::Result;
    use axum::{body::to_bytes, body::Body, response::IntoResponse, routing::get, Router};
    use chat_core::EncodingKey;
    use serde_json::Value;
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
            kafka: crate::config::KafkaConfig::default(),
            redis: crate::config::RedisConfig::default(),
        };
        Ok(AppState::new(config))
    }

    #[tokio::test]
    async fn verify_notify_ticket_middleware_should_only_accept_notify_ticket_query() -> Result<()>
    {
        let state = test_state()?;
        let ek = EncodingKey::load(include_str!("../../chat_core/fixtures/encoding.pem"))?;
        let user = chat_core::User::new(1, "Tyr Chen", "tchen@acme.org");
        let user_token = ek.sign_access_token(user.id, "sid-notify-ticket-test", 0)?;
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
        let body = to_bytes(res.into_body(), usize::MAX).await?;
        let json: Value = serde_json::from_slice(&body)?;
        assert_eq!(json["error"], "notify_ticket_invalid");

        let req = Request::builder()
            .uri("/")
            .header("Authorization", format!("Bearer {}", notify_ticket))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::UNAUTHORIZED);
        let body = to_bytes(res.into_body(), usize::MAX).await?;
        let json: Value = serde_json::from_slice(&body)?;
        assert_eq!(json["error"], "notify_ticket_missing_or_invalid_query");

        Ok(())
    }
}
