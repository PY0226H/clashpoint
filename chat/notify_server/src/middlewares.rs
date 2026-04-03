use crate::{AppState, NotifyAuthSurface};
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

#[derive(Debug, Clone)]
pub(crate) struct NotifyWsSubprotocol(pub String);

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
    let path = parts.uri.path().to_string();
    let auth_surface = classify_auth_surface(&path);
    let token = if matches!(
        auth_surface,
        NotifyAuthSurface::GlobalWs | NotifyAuthSurface::DebateWs
    ) {
        match extract_notify_ticket_from_ws_protocol(&parts.headers) {
            Some((token, protocol)) => {
                parts.extensions.insert(NotifyWsSubprotocol(protocol));
                token
            }
            None => {
                state.observe_notify_auth_unauthorized(auth_surface);
                let auth_snapshot = state.auth_metrics_snapshot();
                warn!(
                    request_id,
                    path,
                    ws_unauthorized_total = auth_snapshot.ws_unauthorized_total,
                    debate_ws_unauthorized_total = auth_snapshot.debate_ws_unauthorized_total,
                    "parse notify ticket from websocket protocol failed"
                );
                return notify_error_response(
                    StatusCode::UNAUTHORIZED,
                    "notify_ticket_missing_or_invalid_subprotocol",
                    "missing or malformed notify ticket in Sec-WebSocket-Protocol",
                    request_id,
                );
            }
        }
    } else {
        match Query::<Params>::from_request_parts(&mut parts, &state).await {
            Ok(params) => params.token.clone(),
            Err(_) => {
                state.observe_notify_auth_unauthorized(auth_surface);
                let auth_snapshot = state.auth_metrics_snapshot();
                warn!(
                    request_id,
                    path,
                    sse_unauthorized_total = auth_snapshot.sse_unauthorized_total,
                    debate_ws_unauthorized_total = auth_snapshot.debate_ws_unauthorized_total,
                    "parse notify ticket from query failed: token is missing or malformed"
                );
                return notify_error_response(
                    StatusCode::UNAUTHORIZED,
                    "notify_ticket_missing_or_invalid_query",
                    "missing or malformed notify ticket in query",
                    request_id,
                );
            }
        }
    };

    let user = match state.dk.verify_notify_ticket(&token) {
        Ok(user) => user,
        Err(err) => {
            state.observe_notify_auth_forbidden(auth_surface);
            let auth_snapshot = state.auth_metrics_snapshot();
            warn!(
                request_id,
                path,
                sse_forbidden_total = auth_snapshot.sse_forbidden_total,
                ws_forbidden_total = auth_snapshot.ws_forbidden_total,
                debate_ws_forbidden_total = auth_snapshot.debate_ws_forbidden_total,
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

fn classify_auth_surface(path: &str) -> NotifyAuthSurface {
    match path {
        "/events" => NotifyAuthSurface::Sse,
        "/ws" => NotifyAuthSurface::GlobalWs,
        p if p.starts_with("/ws/debate/") => NotifyAuthSurface::DebateWs,
        _ => NotifyAuthSurface::Unknown,
    }
}

fn extract_notify_ticket_from_ws_protocol(headers: &HeaderMap) -> Option<(String, String)> {
    let raw = headers
        .get("sec-websocket-protocol")
        .and_then(|v| v.to_str().ok())?;
    for protocol in raw.split(',').map(str::trim).filter(|v| !v.is_empty()) {
        if let Some(ticket) = protocol.strip_prefix("notify-ticket.") {
            if !ticket.trim().is_empty() {
                return Some((ticket.trim().to_string(), protocol.to_string()));
            }
        }
        if protocol.matches('.').count() == 2 {
            return Some((protocol.to_string(), protocol.to_string()));
        }
    }
    None
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
    async fn verify_notify_ticket_middleware_should_accept_query_for_events_and_subprotocol_for_ws(
    ) -> Result<()> {
        let state = test_state()?;
        let ek = EncodingKey::load(include_str!("../../chat_core/fixtures/encoding.pem"))?;
        let user = chat_core::User::new(1, "Tyr Chen", "tchen@acme.org");
        let user_token = ek.sign_access_token(user.id, "sid-notify-ticket-test", 0)?;
        let notify_ticket = ek.sign_notify_ticket(user, 300)?;

        let app = Router::new()
            .route("/events", get(handler))
            .route("/ws", get(handler))
            .route("/ws/debate/12", get(handler))
            .layer(axum::middleware::from_fn_with_state(
                state.clone(),
                verify_notify_ticket,
            ))
            .with_state(state);

        let req = Request::builder()
            .uri(format!("/events?token={notify_ticket}"))
            .body(Body::empty())?;
        let res = app.clone().oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::OK);

        let req = Request::builder()
            .uri(format!("/events?token={user_token}"))
            .body(Body::empty())?;
        let res = app.clone().oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::FORBIDDEN);
        let body = to_bytes(res.into_body(), usize::MAX).await?;
        let json: Value = serde_json::from_slice(&body)?;
        assert_eq!(json["error"], "notify_ticket_invalid");

        let req = Request::builder()
            .uri("/events")
            .header("Authorization", format!("Bearer {}", notify_ticket))
            .body(Body::empty())?;
        let res = app.clone().oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::UNAUTHORIZED);
        let body = to_bytes(res.into_body(), usize::MAX).await?;
        let json: Value = serde_json::from_slice(&body)?;
        assert_eq!(json["error"], "notify_ticket_missing_or_invalid_query");

        let req = Request::builder()
            .uri("/ws")
            .header("Sec-WebSocket-Protocol", notify_ticket.as_str())
            .body(Body::empty())?;
        let res = app.clone().oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::OK);

        let req = Request::builder()
            .uri("/ws/debate/12")
            .header("Sec-WebSocket-Protocol", notify_ticket.as_str())
            .body(Body::empty())?;
        let res = app.clone().oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::OK);

        let req = Request::builder()
            .uri(format!("/ws?token={notify_ticket}"))
            .body(Body::empty())?;
        let res = app.clone().oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::UNAUTHORIZED);
        let body = to_bytes(res.into_body(), usize::MAX).await?;
        let json: Value = serde_json::from_slice(&body)?;
        assert_eq!(
            json["error"],
            "notify_ticket_missing_or_invalid_subprotocol"
        );

        let req = Request::builder()
            .uri(format!("/ws/debate/12?token={notify_ticket}"))
            .body(Body::empty())?;
        let res = app.clone().oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::UNAUTHORIZED);
        let body = to_bytes(res.into_body(), usize::MAX).await?;
        let json: Value = serde_json::from_slice(&body)?;
        assert_eq!(
            json["error"],
            "notify_ticket_missing_or_invalid_subprotocol"
        );

        Ok(())
    }
}
