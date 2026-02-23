use std::sync::Arc;

use crate::{AppEvent, AppState};
use axum::{
    extract::{
        ws::{Message, WebSocket, WebSocketUpgrade},
        State,
    },
    response::Response,
    Extension,
};
use chat_core::User;
use tokio::sync::broadcast;
use tracing::{info, warn};

pub(crate) async fn ws_handler(
    ws: WebSocketUpgrade,
    Extension(user): Extension<User>,
    State(state): State<AppState>,
) -> Response {
    let user_id = user.id as u64;
    let rx = state.subscribe_user_events(user_id);
    info!("User {} subscribed via websocket", user_id);
    ws.on_upgrade(move |socket| websocket_loop(socket, rx, user_id))
}

async fn websocket_loop(
    mut socket: WebSocket,
    mut rx: broadcast::Receiver<Arc<AppEvent>>,
    user_id: u64,
) {
    loop {
        tokio::select! {
            incoming = socket.recv() => {
                match incoming {
                    Some(Ok(Message::Close(_))) | None => break,
                    Some(Ok(Message::Ping(v))) => {
                        if socket.send(Message::Pong(v)).await.is_err() {
                            break;
                        }
                    }
                    Some(Ok(_)) => {}
                    Some(Err(e)) => {
                        warn!("websocket recv failed for user {}: {}", user_id, e);
                        break;
                    }
                }
            }
            maybe_event = rx.recv() => {
                match maybe_event {
                    Ok(event) => {
                        let payload = match serde_json::to_string(&event) {
                            Ok(v) => v,
                            Err(e) => {
                                warn!("serialize event failed for user {}: {}", user_id, e);
                                continue;
                            }
                        };
                        if socket.send(Message::Text(payload.into())).await.is_err() {
                            break;
                        }
                    }
                    Err(broadcast::error::RecvError::Lagged(skipped)) => {
                        warn!("websocket lagged for user {}, skipped {} events", user_id, skipped);
                    }
                    Err(broadcast::error::RecvError::Closed) => break,
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        config::{AuthConfig, ServerConfig},
        middlewares::verify_notify_ticket,
        notif::DebateParticipantJoined,
        AppConfig,
    };
    use anyhow::Result;
    use axum::{middleware::from_fn_with_state, routing::get, Router};
    use chat_core::EncodingKey;
    use futures::StreamExt;
    use tokio::{net::TcpListener, time::Duration};
    use tokio_tungstenite::{connect_async, tungstenite::Error as WsError};

    fn test_state() -> AppState {
        let config = AppConfig {
            server: ServerConfig {
                port: 0,
                db_url: "postgres://localhost:5432/chat".to_string(),
            },
            auth: AuthConfig {
                pk: include_str!("../../chat_core/fixtures/decoding.pem").to_string(),
            },
        };
        AppState::new(config)
    }

    #[tokio::test]
    async fn ws_handler_should_stream_broadcast_event() -> Result<()> {
        let state = test_state();
        let ek = EncodingKey::load(include_str!("../../chat_core/fixtures/encoding.pem"))?;
        let user = chat_core::User::new(1, "Tyr Chen", "tchen@acme.org");
        let notify_ticket = ek.sign_notify_ticket(user, 300)?;

        let app = Router::new()
            .route("/ws", get(ws_handler))
            .layer(from_fn_with_state(state.clone(), verify_notify_ticket))
            .with_state(state.clone());
        let listener = TcpListener::bind("127.0.0.1:0").await?;
        let addr = listener.local_addr()?;
        tokio::spawn(async move {
            axum::serve(listener, app).await.unwrap();
        });

        let (mut socket, _) =
            connect_async(format!("ws://{addr}/ws?token={notify_ticket}")).await?;

        // Wait for ws_handler to register this user channel in state.users.
        for _ in 0..40 {
            if state.users.contains_key(&1) {
                break;
            }
            tokio::time::sleep(Duration::from_millis(25)).await;
        }
        let tx = state.users.get(&1).expect("user channel should exist");
        tx.send(Arc::new(AppEvent::DebateParticipantJoined(
            DebateParticipantJoined {
                session_id: 12,
                user_id: 1,
                side: "pro".to_string(),
                pro_count: 2,
                con_count: 1,
            },
        )))?;

        let maybe_msg = tokio::time::timeout(Duration::from_secs(2), socket.next()).await?;
        let msg = maybe_msg.expect("should receive websocket message")?;
        let text = msg.into_text()?.to_string();
        assert!(text.contains("\"event\":\"DebateParticipantJoined\""));
        assert!(text.contains("\"sessionId\":12"));
        assert!(text.contains("\"side\":\"pro\""));
        Ok(())
    }

    #[tokio::test]
    async fn ws_handler_should_reject_missing_query_token() -> Result<()> {
        let state = test_state();
        let app = Router::new()
            .route("/ws", get(ws_handler))
            .layer(from_fn_with_state(state.clone(), verify_notify_ticket))
            .with_state(state);
        let listener = TcpListener::bind("127.0.0.1:0").await?;
        let addr = listener.local_addr()?;
        tokio::spawn(async move {
            axum::serve(listener, app).await.unwrap();
        });

        let err = connect_async(format!("ws://{addr}/ws")).await.unwrap_err();
        match err {
            WsError::Http(resp) => {
                assert_eq!(resp.status(), 401);
            }
            _ => panic!("unexpected websocket error: {}", err),
        }
        Ok(())
    }
}
