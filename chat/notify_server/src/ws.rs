use std::sync::Arc;

use crate::{AppEvent, AppState};
use axum::{
    extract::{
        ws::{Message, WebSocket, WebSocketUpgrade},
        Path, State,
    },
    response::Response,
    Extension,
};
use chat_core::User;
use serde::{Deserialize, Serialize};
use serde_json::Value;
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

pub(crate) async fn debate_room_ws_handler(
    Path(session_id): Path<i64>,
    ws: WebSocketUpgrade,
    Extension(user): Extension<User>,
    State(state): State<AppState>,
) -> Response {
    let user_id = user.id as u64;
    let rx = state.subscribe_user_events(user_id);
    info!(
        "User {} subscribed via debate room websocket, session_id={}",
        user_id, session_id
    );
    ws.on_upgrade(move |socket| debate_room_loop(socket, rx, user_id, session_id))
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
                        if socket.send(Message::Text(payload)).await.is_err() {
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

#[derive(Debug, Deserialize)]
#[serde(tag = "type", rename_all = "camelCase")]
enum RoomClientMessage {
    Ping,
}

#[derive(Debug, Serialize)]
#[serde(tag = "type", rename_all = "camelCase")]
enum RoomServerMessage {
    Welcome { session_id: i64, user_id: u64 },
    RoomEvent { event_name: String, payload: Value },
    Pong,
}

async fn debate_room_loop(
    mut socket: WebSocket,
    mut rx: broadcast::Receiver<Arc<AppEvent>>,
    user_id: u64,
    session_id: i64,
) {
    if !send_room_message(
        &mut socket,
        &RoomServerMessage::Welcome {
            session_id,
            user_id,
        },
    )
    .await
    {
        return;
    }

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
                    Some(Ok(Message::Text(text))) => {
                        let cmd = serde_json::from_str::<RoomClientMessage>(&text);
                        if matches!(cmd, Ok(RoomClientMessage::Ping))
                            && !send_room_message(&mut socket, &RoomServerMessage::Pong).await
                        {
                            break;
                        }
                    }
                    Some(Ok(_)) => {}
                    Some(Err(e)) => {
                        warn!(
                            "debate room websocket recv failed for user {}, session {}: {}",
                            user_id, session_id, e
                        );
                        break;
                    }
                }
            }
            maybe_event = rx.recv() => {
                match maybe_event {
                    Ok(event) => {
                        if event.debate_session_id() != Some(session_id) {
                            continue;
                        }
                        let payload = match serde_json::to_value(event.as_ref()) {
                            Ok(v) => v,
                            Err(e) => {
                                warn!(
                                    "serialize debate room event failed for user {}, session {}: {}",
                                    user_id, session_id, e
                                );
                                continue;
                            }
                        };
                        let msg = RoomServerMessage::RoomEvent {
                            event_name: event.event_name().to_string(),
                            payload,
                        };
                        if !send_room_message(&mut socket, &msg).await {
                            break;
                        }
                    }
                    Err(broadcast::error::RecvError::Lagged(skipped)) => {
                        warn!(
                            "debate room websocket lagged for user {}, session {}, skipped {} events",
                            user_id, session_id, skipped
                        );
                    }
                    Err(broadcast::error::RecvError::Closed) => break,
                }
            }
        }
    }
}

async fn send_room_message(socket: &mut WebSocket, msg: &RoomServerMessage) -> bool {
    let payload = match serde_json::to_string(msg) {
        Ok(v) => v,
        Err(_) => return false,
    };
    socket.send(Message::Text(payload)).await.is_ok()
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
    async fn debate_room_ws_handler_should_filter_by_session_id() -> Result<()> {
        let state = test_state();
        let ek = EncodingKey::load(include_str!("../../chat_core/fixtures/encoding.pem"))?;
        let user = chat_core::User::new(1, "Tyr Chen", "tchen@acme.org");
        let notify_ticket = ek.sign_notify_ticket(user, 300)?;

        let app = Router::new()
            .route("/ws/debate/:session_id", get(debate_room_ws_handler))
            .layer(from_fn_with_state(state.clone(), verify_notify_ticket))
            .with_state(state.clone());
        let listener = TcpListener::bind("127.0.0.1:0").await?;
        let addr = listener.local_addr()?;
        tokio::spawn(async move {
            axum::serve(listener, app).await.unwrap();
        });

        let (mut socket, _) =
            connect_async(format!("ws://{addr}/ws/debate/12?token={notify_ticket}")).await?;

        let welcome = tokio::time::timeout(Duration::from_secs(2), socket.next()).await?;
        let welcome_msg = welcome
            .expect("should receive welcome message")
            .expect("welcome message should be ws ok");
        let welcome_text = welcome_msg.into_text()?.to_string();
        let welcome_json: serde_json::Value = serde_json::from_str(&welcome_text)?;
        assert_eq!(welcome_json["type"], "welcome");
        let welcome_session_id = welcome_json
            .get("sessionId")
            .or_else(|| welcome_json.get("session_id"))
            .and_then(|v| v.as_i64())
            .expect("welcome should carry session id");
        assert_eq!(welcome_session_id, 12);

        for _ in 0..40 {
            if state.users.contains_key(&1) {
                break;
            }
            tokio::time::sleep(Duration::from_millis(25)).await;
        }
        let tx = state.users.get(&1).expect("user channel should exist");
        tx.send(Arc::new(AppEvent::DebateParticipantJoined(
            crate::notif::DebateParticipantJoined {
                session_id: 13,
                user_id: 1,
                side: "pro".to_string(),
                pro_count: 2,
                con_count: 1,
            },
        )))?;
        let no_msg = tokio::time::timeout(Duration::from_millis(200), socket.next()).await;
        assert!(no_msg.is_err(), "session 13 event should be filtered out");

        tx.send(Arc::new(AppEvent::DebateParticipantJoined(
            crate::notif::DebateParticipantJoined {
                session_id: 12,
                user_id: 1,
                side: "con".to_string(),
                pro_count: 2,
                con_count: 2,
            },
        )))?;

        let maybe_msg = tokio::time::timeout(Duration::from_secs(2), socket.next()).await?;
        let room_msg = maybe_msg
            .expect("should receive room event message")
            .expect("room event should be ws ok");
        let text = room_msg.into_text()?.to_string();
        let room_json: serde_json::Value = serde_json::from_str(&text)?;
        assert_eq!(room_json["type"], "roomEvent");
        let event_name = room_json
            .get("eventName")
            .or_else(|| room_json.get("event_name"))
            .and_then(|v| v.as_str())
            .expect("room event should carry event name");
        assert_eq!(event_name, "DebateParticipantJoined");
        let payload_session_id = room_json["payload"]
            .get("sessionId")
            .or_else(|| room_json["payload"].get("session_id"))
            .and_then(|v| v.as_i64())
            .expect("room event payload should carry session id");
        assert_eq!(payload_session_id, 12);
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

    #[tokio::test]
    async fn debate_room_ws_handler_should_reject_missing_query_token() -> Result<()> {
        let state = test_state();
        let app = Router::new()
            .route("/ws/debate/:session_id", get(debate_room_ws_handler))
            .layer(from_fn_with_state(state.clone(), verify_notify_ticket))
            .with_state(state);
        let listener = TcpListener::bind("127.0.0.1:0").await?;
        let addr = listener.local_addr()?;
        tokio::spawn(async move {
            axum::serve(listener, app).await.unwrap();
        });

        let err = connect_async(format!("ws://{addr}/ws/debate/12"))
            .await
            .unwrap_err();
        match err {
            WsError::Http(resp) => {
                assert_eq!(resp.status(), 401);
            }
            _ => panic!("unexpected websocket error: {}", err),
        }
        Ok(())
    }
}
