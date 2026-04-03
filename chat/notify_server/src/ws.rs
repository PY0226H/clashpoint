use std::{
    sync::Arc,
    time::{SystemTime, UNIX_EPOCH},
};

use crate::{
    middlewares::{notify_error_response, NotifyWsSubprotocol},
    AppState, DebateReplayEvent, UserEvent,
};
use axum::{
    extract::{
        ws::{Message, WebSocket, WebSocketUpgrade},
        Path, Query, State,
    },
    http::{HeaderMap, StatusCode},
    response::Response,
    Extension,
};
use chat_core::User;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tokio::sync::broadcast;
use tokio::time::{Duration, Instant, MissedTickBehavior};
use tracing::{info, warn};

const GLOBAL_HEARTBEAT_INTERVAL: Duration = Duration::from_secs(20);
const GLOBAL_HEARTBEAT_TIMEOUT: Duration = Duration::from_secs(65);
const GLOBAL_IDLE_SIGNAL_AFTER: Duration = Duration::from_secs(60);
const GLOBAL_IDLE_SIGNAL_COOLDOWN: Duration = Duration::from_secs(45);
const GLOBAL_DEGRADED_MODE_WINDOW: Duration = Duration::from_secs(20);

const ROOM_HEARTBEAT_INTERVAL: Duration = Duration::from_secs(20);
const ROOM_HEARTBEAT_TIMEOUT: Duration = Duration::from_secs(65);
const ROOM_SYNC_REQUIRED_COOLDOWN: Duration = Duration::from_millis(1500);
const ROOM_SYNC_REQUIRED_SUPPRESS_LOG_EVERY: u64 = 10;

#[derive(Debug, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub(crate) struct GlobalWsQuery {
    last_event_id: Option<u64>,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "type", rename_all = "camelCase")]
enum GlobalClientMessage {
    Ping,
    Pong,
}

#[derive(Debug, Serialize)]
#[serde(tag = "type", rename_all = "camelCase")]
enum GlobalServerMessage {
    Welcome {
        user_id: u64,
        baseline_last_event_id: u64,
        last_event_id: u64,
        replay_count: usize,
        heartbeat_interval_ms: u64,
        heartbeat_timeout_ms: u64,
        idle_signal_after_ms: u64,
    },
    Event {
        event_id: u64,
        event_at_ms: i64,
        event_name: String,
        payload: Value,
    },
    Ping {
        ts: i64,
        last_event_id: u64,
    },
    Pong {
        ts: Option<i64>,
    },
    SyncRequired {
        reason: String,
        skipped: u64,
        suggested_last_event_id: u64,
        latest_event_id: u64,
        strategy: String,
    },
    StreamIdle {
        idle_ms: u64,
        last_event_id: u64,
        strategy: String,
    },
}

struct WsConnectionGuard {
    state: AppState,
    user_id: u64,
}

impl Drop for WsConnectionGuard {
    fn drop(&mut self) {
        self.state.release_ws_connection(self.user_id);
        self.state.cleanup_user_events_if_unused(self.user_id);
    }
}

pub(crate) async fn ws_handler(
    Query(query): Query<GlobalWsQuery>,
    ws: WebSocketUpgrade,
    headers: HeaderMap,
    protocol: Option<Extension<NotifyWsSubprotocol>>,
    Extension(user): Extension<User>,
    State(state): State<AppState>,
) -> Response {
    let user_id = user.id as u64;
    let request_id = extract_request_id(&headers);
    if !state.try_acquire_ws_connection(user_id) {
        return notify_error_response(
            StatusCode::TOO_MANY_REQUESTS,
            "notify_ws_too_many_connections",
            "too many active websocket connections for this user",
            request_id,
        );
    }
    let rx = state.subscribe_user_events(user_id);
    let mut ws = ws;
    if let Some(Extension(NotifyWsSubprotocol(selected_protocol))) = protocol {
        ws = ws.protocols([selected_protocol]);
    }
    let ws_snapshot = state.ws_metrics_snapshot();
    info!(
        request_id,
        user_id,
        requested_last_event_id = query.last_event_id.unwrap_or(0),
        ws_connected_total = ws_snapshot.connected_total,
        "user subscribed via global websocket"
    );
    ws.on_upgrade(move |socket| websocket_loop(socket, rx, user_id, query.last_event_id, state))
}

pub(crate) async fn debate_room_ws_handler(
    Path(session_id): Path<i64>,
    Query(query): Query<DebateRoomWsQuery>,
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
    ws.on_upgrade(move |socket| {
        debate_room_loop(socket, rx, user_id, session_id, query.last_ack_seq, state)
    })
}

async fn websocket_loop(
    mut socket: WebSocket,
    mut rx: broadcast::Receiver<Arc<UserEvent>>,
    user_id: u64,
    requested_last_event_id: Option<u64>,
    state: AppState,
) {
    let _guard = WsConnectionGuard {
        state: state.clone(),
        user_id,
    };
    let replay_window = state.replay_sse_events_for_user(user_id, requested_last_event_id);
    let mut baseline_last_event_id = requested_last_event_id.unwrap_or(0);
    if baseline_last_event_id > replay_window.latest_id {
        baseline_last_event_id = replay_window.latest_id;
    }
    let should_replay = !replay_window.has_gap;
    let replay_count = if should_replay {
        replay_window.events.len()
    } else {
        0
    };
    let mut last_sent_event_id = baseline_last_event_id;
    let mut last_client_heartbeat = Instant::now();
    let mut last_live_event_at = Instant::now();
    let mut last_idle_signal_at: Option<Instant> = None;
    let mut degraded_until: Option<Instant> = None;
    let mut heartbeat_tick = tokio::time::interval(GLOBAL_HEARTBEAT_INTERVAL);
    heartbeat_tick.set_missed_tick_behavior(MissedTickBehavior::Skip);
    heartbeat_tick.tick().await;
    let mut idle_signal_tick = tokio::time::interval(Duration::from_secs(10));
    idle_signal_tick.set_missed_tick_behavior(MissedTickBehavior::Skip);
    idle_signal_tick.tick().await;

    if !send_global_message(
        &mut socket,
        &GlobalServerMessage::Welcome {
            user_id,
            baseline_last_event_id,
            last_event_id: replay_window.latest_id,
            replay_count,
            heartbeat_interval_ms: GLOBAL_HEARTBEAT_INTERVAL.as_millis() as u64,
            heartbeat_timeout_ms: GLOBAL_HEARTBEAT_TIMEOUT.as_millis() as u64,
            idle_signal_after_ms: GLOBAL_IDLE_SIGNAL_AFTER.as_millis() as u64,
        },
        &state,
    )
    .await
    {
        return;
    }

    if replay_window.has_gap {
        state.observe_ws_sync_required();
        let sync_msg = GlobalServerMessage::SyncRequired {
            reason: "replay_window_miss".to_string(),
            skipped: replay_window.skipped,
            suggested_last_event_id: baseline_last_event_id,
            latest_event_id: replay_window.latest_id,
            strategy: "snapshot_then_reconnect".to_string(),
        };
        if !send_global_message(&mut socket, &sync_msg, &state).await {
            return;
        }
    } else {
        for evt in replay_window.events {
            if !send_global_message(
                &mut socket,
                &GlobalServerMessage::Event {
                    event_id: evt.event_id,
                    event_at_ms: evt.event_at_ms,
                    event_name: evt.event_name,
                    payload: evt.payload,
                },
                &state,
            )
            .await
            {
                return;
            }
            state.observe_ws_replay_sent();
            last_sent_event_id = last_sent_event_id.max(evt.event_id);
            last_live_event_at = Instant::now();
        }
    }

    loop {
        tokio::select! {
            incoming = socket.recv() => {
                match incoming {
                    Some(Ok(Message::Close(_))) | None => break,
                    Some(Ok(Message::Ping(v))) => {
                        last_client_heartbeat = Instant::now();
                        if socket.send(Message::Pong(v)).await.is_err() {
                            state.observe_ws_send_failed();
                            break;
                        }
                    }
                    Some(Ok(Message::Pong(_))) => {
                        last_client_heartbeat = Instant::now();
                    }
                    Some(Ok(Message::Text(text))) => {
                        match serde_json::from_str::<GlobalClientMessage>(&text) {
                            Ok(GlobalClientMessage::Ping) => {
                                last_client_heartbeat = Instant::now();
                                if !send_global_message(
                                    &mut socket,
                                    &GlobalServerMessage::Pong { ts: Some(now_unix_ms()) },
                                    &state,
                                )
                                .await
                                {
                                    break;
                                }
                            }
                            Ok(GlobalClientMessage::Pong) => {
                                last_client_heartbeat = Instant::now();
                            }
                            Err(_) => {}
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
                        if event.app_event.is_debate_event() {
                            state.observe_ws_event_filtered();
                            continue;
                        }
                        let now = Instant::now();
                        if let Some(until) = degraded_until {
                            if now >= until {
                                degraded_until = None;
                            }
                        }
                        if degraded_until.is_some() && !event.app_event.is_sse_critical_event() {
                            state.observe_ws_qos_drop();
                            continue;
                        }
                        let Some(replay_meta) = event.sse_replay.as_ref() else {
                            state.observe_ws_event_filtered();
                            continue;
                        };
                        let msg = GlobalServerMessage::Event {
                            event_id: replay_meta.event_id,
                            event_at_ms: replay_meta.event_at_ms,
                            event_name: replay_meta.event_name.clone(),
                            payload: replay_meta.payload.clone(),
                        };
                        if !send_global_message(&mut socket, &msg, &state).await {
                            break;
                        }
                        state.observe_ws_live_sent();
                        last_live_event_at = Instant::now();
                        last_sent_event_id = last_sent_event_id.max(replay_meta.event_id);
                    }
                    Err(broadcast::error::RecvError::Lagged(skipped)) => {
                        state.observe_ws_lagged(skipped);
                        state.observe_ws_sync_required();
                        degraded_until = Some(Instant::now() + GLOBAL_DEGRADED_MODE_WINDOW);
                        let sync_msg = GlobalServerMessage::SyncRequired {
                            reason: "lagged_receiver".to_string(),
                            skipped,
                            suggested_last_event_id: last_sent_event_id,
                            latest_event_id: last_sent_event_id.saturating_add(skipped),
                            strategy: "snapshot_then_reconnect".to_string(),
                        };
                        if !send_global_message(&mut socket, &sync_msg, &state).await {
                            break;
                        }
                    }
                    Err(broadcast::error::RecvError::Closed) => break,
                }
            }
            _ = heartbeat_tick.tick() => {
                let idle_for = Instant::now().saturating_duration_since(last_client_heartbeat);
                if idle_for > GLOBAL_HEARTBEAT_TIMEOUT {
                    warn!(
                        "global websocket heartbeat timeout for user {}, idle={}ms",
                        user_id,
                        idle_for.as_millis()
                    );
                    break;
                }
                if !send_global_message(
                    &mut socket,
                    &GlobalServerMessage::Ping {
                        ts: now_unix_ms(),
                        last_event_id: last_sent_event_id,
                    },
                    &state,
                )
                .await
                {
                    break;
                }
            }
            _ = idle_signal_tick.tick() => {
                let idle_for = Instant::now().saturating_duration_since(last_live_event_at);
                if idle_for >= GLOBAL_IDLE_SIGNAL_AFTER {
                    let cooldown_ready = last_idle_signal_at
                        .map(|v| Instant::now().saturating_duration_since(v) >= GLOBAL_IDLE_SIGNAL_COOLDOWN)
                        .unwrap_or(true);
                    if cooldown_ready {
                        if !send_global_message(
                            &mut socket,
                            &GlobalServerMessage::StreamIdle {
                                idle_ms: idle_for.as_millis() as u64,
                                last_event_id: last_sent_event_id,
                                strategy: "verify_ingress_or_refresh_snapshot".to_string(),
                            },
                            &state,
                        )
                        .await
                        {
                            break;
                        }
                        state.observe_ws_idle_signal();
                        last_idle_signal_at = Some(Instant::now());
                    }
                }
            }
        }
    }
    drop(rx);
}

async fn send_global_message(
    socket: &mut WebSocket,
    msg: &GlobalServerMessage,
    state: &AppState,
) -> bool {
    let payload = match serde_json::to_string(msg) {
        Ok(v) => v,
        Err(e) => {
            warn!("serialize global ws message failed: {}", e);
            return false;
        }
    };
    if socket.send(Message::Text(payload)).await.is_err() {
        state.observe_ws_send_failed();
        return false;
    }
    true
}

#[derive(Debug, Deserialize)]
#[serde(tag = "type", rename_all = "camelCase")]
enum RoomClientMessage {
    Ping,
    Pong,
    Ack { event_seq: u64 },
}

#[derive(Debug, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub(crate) struct DebateRoomWsQuery {
    last_ack_seq: Option<u64>,
}

#[derive(Debug, Serialize)]
#[serde(tag = "type", rename_all = "camelCase")]
enum RoomServerMessage {
    Welcome {
        session_id: i64,
        user_id: u64,
        baseline_ack_seq: u64,
        last_event_seq: u64,
        replay_count: usize,
        heartbeat_interval_ms: u64,
        heartbeat_timeout_ms: u64,
    },
    RoomEvent {
        event_seq: u64,
        event_at_ms: i64,
        event_name: String,
        payload: Value,
    },
    Ping {
        ts: i64,
    },
    Pong {
        ts: Option<i64>,
    },
    SyncRequired {
        reason: String,
        skipped: u64,
        expected_from_seq: Option<u64>,
        gap_from_seq: Option<u64>,
        gap_to_seq: Option<u64>,
        suggested_last_ack_seq: u64,
        latest_event_seq: Option<u64>,
        strategy: String,
    },
}

async fn debate_room_loop(
    mut socket: WebSocket,
    mut rx: broadcast::Receiver<Arc<UserEvent>>,
    user_id: u64,
    session_id: i64,
    last_ack_seq: Option<u64>,
    state: AppState,
) {
    let mut client_last_ack_seq = last_ack_seq.unwrap_or(0);
    let mut sync_required_throttle = SyncRequiredThrottleState::default();
    let mut last_client_heartbeat = Instant::now();
    let mut heartbeat_tick = tokio::time::interval(ROOM_HEARTBEAT_INTERVAL);
    heartbeat_tick.set_missed_tick_behavior(MissedTickBehavior::Skip);
    heartbeat_tick.tick().await;
    let replay_window = state
        .replay_debate_events_for_user(user_id, session_id, last_ack_seq)
        .await;
    let clamped_ack_seq =
        clamp_requested_last_ack_seq(client_last_ack_seq, replay_window.latest_seq);
    if clamped_ack_seq != client_last_ack_seq {
        warn!(
            "debate room websocket received out-of-range lastAckSeq, clamp to latest seq: user={}, session={}, requested_last_ack_seq={}, latest_event_seq={}, applied_last_ack_seq={}",
            user_id,
            session_id,
            client_last_ack_seq,
            replay_window.latest_seq,
            clamped_ack_seq
        );
        client_last_ack_seq = clamped_ack_seq;
    }
    let mut last_sent_event_seq = client_last_ack_seq;
    let should_force_sync = replay_window.sync_required_reason.is_some();
    let should_replay = !replay_window.has_gap && !should_force_sync;
    let replay_count = if should_replay {
        replay_window.events.len()
    } else {
        0
    };

    if !send_room_message(
        &mut socket,
        &RoomServerMessage::Welcome {
            session_id,
            user_id,
            baseline_ack_seq: client_last_ack_seq,
            last_event_seq: replay_window.latest_seq,
            replay_count,
            heartbeat_interval_ms: ROOM_HEARTBEAT_INTERVAL.as_millis() as u64,
            heartbeat_timeout_ms: ROOM_HEARTBEAT_TIMEOUT.as_millis() as u64,
        },
    )
    .await
    {
        return;
    }
    if let Some(reason) = replay_window.sync_required_reason.as_ref() {
        let expected_from_seq = client_last_ack_seq.saturating_add(1);
        let first_available_seq = replay_window
            .events
            .first()
            .map(|v| v.event_seq)
            .unwrap_or(replay_window.latest_seq.saturating_add(1));
        let gap_to_seq = first_available_seq.saturating_sub(1);
        let sync_msg = RoomServerMessage::SyncRequired {
            reason: reason.clone(),
            skipped: replay_window.skipped,
            expected_from_seq: Some(expected_from_seq),
            gap_from_seq: replay_window.has_gap.then_some(expected_from_seq),
            gap_to_seq: replay_window
                .has_gap
                .then_some(gap_to_seq)
                .filter(|to| *to >= expected_from_seq),
            suggested_last_ack_seq: client_last_ack_seq,
            latest_event_seq: (replay_window.latest_seq > 0).then_some(replay_window.latest_seq),
            strategy: replay_window
                .sync_required_strategy
                .clone()
                .unwrap_or_else(|| "snapshot_then_reconnect".to_string()),
        };
        if !emit_sync_required_message(
            &mut socket,
            &state,
            sync_msg,
            reason,
            user_id,
            session_id,
            &mut sync_required_throttle,
        )
        .await
        {
            return;
        }
    } else if replay_window.has_gap {
        let expected_from_seq = client_last_ack_seq.saturating_add(1);
        let first_available_seq = replay_window
            .events
            .first()
            .map(|v| v.event_seq)
            .unwrap_or(replay_window.latest_seq.saturating_add(1));
        let gap_to_seq = first_available_seq.saturating_sub(1);
        let sync_msg = RoomServerMessage::SyncRequired {
            reason: "replay_window_miss".to_string(),
            skipped: replay_window.skipped,
            expected_from_seq: Some(expected_from_seq),
            gap_from_seq: Some(expected_from_seq),
            gap_to_seq: (gap_to_seq >= expected_from_seq).then_some(gap_to_seq),
            suggested_last_ack_seq: client_last_ack_seq,
            latest_event_seq: Some(replay_window.latest_seq),
            strategy: "snapshot_then_reconnect".to_string(),
        };
        if !emit_sync_required_message(
            &mut socket,
            &state,
            sync_msg,
            "replay_window_miss",
            user_id,
            session_id,
            &mut sync_required_throttle,
        )
        .await
        {
            return;
        }
    }
    if should_replay {
        for replay_event in replay_window.events {
            if !send_room_message(&mut socket, &room_event_message(&replay_event)).await {
                return;
            }
            last_sent_event_seq = last_sent_event_seq.max(replay_event.event_seq);
        }
    }

    loop {
        tokio::select! {
            incoming = socket.recv() => {
                match incoming {
                    Some(Ok(Message::Close(_))) | None => break,
                    Some(Ok(Message::Ping(v))) => {
                        last_client_heartbeat = Instant::now();
                        if socket.send(Message::Pong(v)).await.is_err() {
                            break;
                        }
                    }
                    Some(Ok(Message::Pong(_))) => {
                        last_client_heartbeat = Instant::now();
                    }
                    Some(Ok(Message::Text(text))) => {
                        let cmd = serde_json::from_str::<RoomClientMessage>(&text);
                        match cmd {
                            Ok(RoomClientMessage::Ping) => {
                                last_client_heartbeat = Instant::now();
                                if !send_room_message(
                                    &mut socket,
                                    &RoomServerMessage::Pong {
                                        ts: Some(now_unix_ms()),
                                    },
                                )
                                .await
                                {
                                    break;
                                }
                            }
                            Ok(RoomClientMessage::Pong) => {
                                last_client_heartbeat = Instant::now();
                            }
                            Ok(RoomClientMessage::Ack { event_seq }) => {
                                last_client_heartbeat = Instant::now();
                                match apply_client_ack_seq(
                                    client_last_ack_seq,
                                    last_sent_event_seq,
                                    event_seq,
                                ) {
                                    Some(next_ack_seq) => {
                                        client_last_ack_seq = next_ack_seq;
                                    }
                                    None => {
                                        warn!(
                                            "debate room websocket ignored out-of-range ack: user={}, session={}, ack_event_seq={}, last_sent_event_seq={}",
                                            user_id, session_id, event_seq, last_sent_event_seq
                                        );
                                    }
                                }
                            }
                            Err(_) => {}
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
                        if let Some(sync_required) = event.debate_sync_required.as_ref() {
                            if sync_required.session_id != session_id {
                                continue;
                            }
                            let expected_from_seq = sync_required
                                .expected_from_seq
                                .or(Some(last_sent_event_seq.saturating_add(1)));
                            let sync_msg = RoomServerMessage::SyncRequired {
                                reason: sync_required.reason.clone(),
                                skipped: sync_required.skipped,
                                expected_from_seq,
                                gap_from_seq: sync_required.gap_from_seq.or(expected_from_seq),
                                gap_to_seq: sync_required.gap_to_seq,
                                suggested_last_ack_seq: client_last_ack_seq,
                                latest_event_seq: sync_required
                                    .latest_event_seq
                                    .or(Some(last_sent_event_seq)),
                                strategy: sync_required.strategy.clone(),
                            };
                            if !emit_sync_required_message(
                                &mut socket,
                                &state,
                                sync_msg,
                                &sync_required.reason,
                                user_id,
                                session_id,
                                &mut sync_required_throttle,
                            )
                            .await
                            {
                                break;
                            }
                            continue;
                        }
                        let Some(replay_event) = event.debate_replay.as_ref() else {
                            warn!(
                                "debate room event missing replay metadata for user {}, session {}",
                                user_id, session_id
                            );
                            continue;
                        };
                        if replay_event.session_id != session_id {
                            continue;
                        };
                        let msg = room_event_message(replay_event);
                        if !send_room_message(&mut socket, &msg).await {
                            break;
                        }
                        last_sent_event_seq = last_sent_event_seq.max(replay_event.event_seq);
                    }
                    Err(broadcast::error::RecvError::Lagged(skipped)) => {
                        warn!(
                            "debate room websocket lagged for user {}, session {}, skipped {} events",
                            user_id, session_id, skipped
                        );
                        let expected_from_seq = last_sent_event_seq.saturating_add(1);
                        let gap_to_seq =
                            expected_from_seq.saturating_add(skipped.saturating_sub(1));
                        let sync_msg = RoomServerMessage::SyncRequired {
                            reason: "lagged_receiver".to_string(),
                            skipped,
                            expected_from_seq: Some(expected_from_seq),
                            gap_from_seq: Some(expected_from_seq),
                            gap_to_seq: Some(gap_to_seq),
                            suggested_last_ack_seq: client_last_ack_seq,
                            latest_event_seq: Some(last_sent_event_seq.saturating_add(skipped)),
                            strategy: "snapshot_then_reconnect".to_string(),
                        };
                        if !emit_sync_required_message(
                            &mut socket,
                            &state,
                            sync_msg,
                            "lagged_receiver",
                            user_id,
                            session_id,
                            &mut sync_required_throttle,
                        )
                        .await
                        {
                            break;
                        }
                    }
                    Err(broadcast::error::RecvError::Closed) => break,
                }
            }
            _ = heartbeat_tick.tick() => {
                let idle_for = Instant::now().saturating_duration_since(last_client_heartbeat);
                if idle_for > ROOM_HEARTBEAT_TIMEOUT {
                    warn!(
                        "debate room websocket heartbeat timeout for user {}, session {}, idle={}ms",
                        user_id,
                        session_id,
                        idle_for.as_millis()
                    );
                    break;
                }
                let ping = RoomServerMessage::Ping { ts: now_unix_ms() };
                if !send_room_message(&mut socket, &ping).await {
                    break;
                }
            }
        }
    }
    drop(rx);
    state.cleanup_user_events_if_unused(user_id);
}

fn clamp_requested_last_ack_seq(requested_last_ack_seq: u64, latest_event_seq: u64) -> u64 {
    requested_last_ack_seq.min(latest_event_seq)
}

fn apply_client_ack_seq(
    client_last_ack_seq: u64,
    last_sent_event_seq: u64,
    ack_event_seq: u64,
) -> Option<u64> {
    if ack_event_seq > last_sent_event_seq {
        return None;
    }
    Some(client_last_ack_seq.max(ack_event_seq))
}

#[derive(Debug, Default)]
struct SyncRequiredThrottleState {
    last_sent_at: Option<Instant>,
    last_reason: Option<String>,
    suppressed_count: u64,
}

fn should_emit_sync_required(
    last_sent_at: Option<Instant>,
    last_reason: Option<&str>,
    reason: &str,
    now: Instant,
) -> bool {
    match last_sent_at {
        None => true,
        Some(last_at) => {
            if last_reason != Some(reason) {
                return true;
            }
            now.saturating_duration_since(last_at) >= ROOM_SYNC_REQUIRED_COOLDOWN
        }
    }
}

async fn emit_sync_required_message(
    socket: &mut WebSocket,
    state: &AppState,
    sync_msg: RoomServerMessage,
    reason: &str,
    user_id: u64,
    session_id: i64,
    throttle: &mut SyncRequiredThrottleState,
) -> bool {
    let now = Instant::now();
    let should_emit = should_emit_sync_required(
        throttle.last_sent_at,
        throttle.last_reason.as_deref(),
        reason,
        now,
    );
    if !should_emit {
        throttle.suppressed_count = throttle.suppressed_count.saturating_add(1);
        if throttle
            .suppressed_count
            .is_multiple_of(ROOM_SYNC_REQUIRED_SUPPRESS_LOG_EVERY)
        {
            warn!(
                user_id,
                session_id,
                reason,
                suppressed_count = throttle.suppressed_count,
                cooldown_ms = ROOM_SYNC_REQUIRED_COOLDOWN.as_millis(),
                "debate room syncRequired suppressed by cooldown"
            );
        }
        return true;
    }
    if throttle.suppressed_count > 0 {
        info!(
            user_id,
            session_id,
            reason,
            released_suppressed_count = throttle.suppressed_count,
            "debate room syncRequired cooldown released"
        );
        throttle.suppressed_count = 0;
    }
    if !send_room_message(socket, &sync_msg).await {
        return false;
    }
    state.observe_sync_required_reason(reason);
    throttle.last_sent_at = Some(now);
    throttle.last_reason = Some(reason.to_string());
    true
}

fn room_event_message(event: &DebateReplayEvent) -> RoomServerMessage {
    RoomServerMessage::RoomEvent {
        event_seq: event.event_seq,
        event_at_ms: event.event_at_ms,
        event_name: event.event_name.clone(),
        payload: event.payload.clone(),
    }
}

async fn send_room_message(socket: &mut WebSocket, msg: &RoomServerMessage) -> bool {
    let payload = match serde_json::to_string(msg) {
        Ok(v) => v,
        Err(_) => return false,
    };
    socket.send(Message::Text(payload)).await.is_ok()
}

fn now_unix_ms() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|v| v.as_millis() as i64)
        .unwrap_or(0)
}

fn extract_request_id(headers: &HeaderMap) -> String {
    headers
        .get("x-request-id")
        .and_then(|v| v.to_str().ok())
        .map(str::trim)
        .filter(|v| !v.is_empty())
        .map(ToOwned::to_owned)
        .unwrap_or_else(|| format!("notify-{}", now_unix_ms()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        config::{AuthConfig, ServerConfig},
        middlewares::verify_notify_ticket,
        notif::DebateParticipantJoined,
        AppConfig, AppEvent,
    };
    use anyhow::Result;
    use axum::{middleware::from_fn_with_state, routing::get, Router};
    use chat_core::{EncodingKey, Message as ChatMessage};
    use chrono::Utc;
    use futures::{SinkExt, StreamExt};
    use tokio::{net::TcpListener, time::Duration};
    use tokio_tungstenite::{
        connect_async,
        tungstenite::{client::IntoClientRequest, Error as WsError},
    };

    fn test_state() -> AppState {
        test_state_with_db_url("postgres://localhost:5432/chat")
    }

    fn test_state_with_db_url(db_url: &str) -> AppState {
        let config = AppConfig {
            server: ServerConfig {
                port: 0,
                db_url: db_url.to_string(),
            },
            auth: AuthConfig {
                pk: include_str!("../../chat_core/fixtures/decoding.pem").to_string(),
            },
            kafka: crate::config::KafkaConfig::default(),
            redis: crate::config::RedisConfig::default(),
        };
        AppState::new(config)
    }

    async fn connect_global_ws(
        addr: std::net::SocketAddr,
        notify_ticket: &str,
        query: Option<&str>,
    ) -> Result<(
        tokio_tungstenite::WebSocketStream<
            tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>,
        >,
    )> {
        let url = if let Some(query) = query {
            format!("ws://{addr}/ws?{query}")
        } else {
            format!("ws://{addr}/ws")
        };
        let mut req = url.into_client_request()?;
        req.headers_mut()
            .insert("Sec-WebSocket-Protocol", notify_ticket.parse()?);
        let (socket, _) = connect_async(req).await?;
        Ok((socket,))
    }

    #[test]
    fn clamp_requested_last_ack_seq_should_not_exceed_latest_event_seq() {
        assert_eq!(clamp_requested_last_ack_seq(10, 3), 3);
        assert_eq!(clamp_requested_last_ack_seq(2, 3), 2);
        assert_eq!(clamp_requested_last_ack_seq(0, 0), 0);
    }

    #[test]
    fn apply_client_ack_seq_should_reject_ack_beyond_last_sent_event_seq() {
        assert_eq!(apply_client_ack_seq(3, 5, 4), Some(4));
        assert_eq!(apply_client_ack_seq(3, 5, 5), Some(5));
        assert_eq!(apply_client_ack_seq(3, 5, 6), None);
    }

    #[test]
    fn should_emit_sync_required_should_suppress_same_reason_within_cooldown() {
        let now = Instant::now();
        assert!(should_emit_sync_required(None, None, "persist_failed", now));
        assert!(!should_emit_sync_required(
            Some(now),
            Some("persist_failed"),
            "persist_failed",
            now + Duration::from_millis(200)
        ));
        assert!(should_emit_sync_required(
            Some(now),
            Some("persist_failed"),
            "persist_failed",
            now + ROOM_SYNC_REQUIRED_COOLDOWN + Duration::from_millis(1)
        ));
    }

    #[test]
    fn should_emit_sync_required_should_allow_reason_switch() {
        let now = Instant::now();
        assert!(should_emit_sync_required(
            Some(now),
            Some("persist_failed"),
            "lagged_receiver",
            now + Duration::from_millis(100)
        ));
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

        let (mut socket,) = connect_global_ws(addr, &notify_ticket, None).await?;

        let welcome = tokio::time::timeout(Duration::from_secs(2), socket.next()).await?;
        let welcome_text = welcome
            .expect("should receive welcome")
            .expect("welcome should be ws ok")
            .into_text()?
            .to_string();
        let welcome_json: serde_json::Value = serde_json::from_str(&welcome_text)?;
        assert_eq!(welcome_json["type"], "welcome");

        // Wait for ws_handler to register this user channel in state.users.
        for _ in 0..40 {
            if state.users.contains_key(&1) {
                break;
            }
            tokio::time::sleep(Duration::from_millis(25)).await;
        }
        let tx = state.users.get(&1).expect("user channel should exist");
        let user_event = state.build_user_event_for_recipient(
            1,
            Arc::new(AppEvent::NewMessage(ChatMessage {
                id: 88,
                chat_id: 12,
                sender_id: 1,
                content: "hello".to_string(),
                modified_content: None,
                files: vec![],
                created_at: Utc::now(),
            })),
            None,
        );
        tx.send(Arc::new(user_event))?;

        let maybe_msg = tokio::time::timeout(Duration::from_secs(2), socket.next()).await?;
        let msg = maybe_msg.expect("should receive websocket message")?;
        let text = msg.into_text()?.to_string();
        let json: serde_json::Value = serde_json::from_str(&text)?;
        assert_eq!(json["type"], "event");
        let event_name = json
            .get("eventName")
            .or_else(|| json.get("event_name"))
            .and_then(|v| v.as_str())
            .unwrap_or_default();
        assert_eq!(event_name, "NewMessage");
        let event_id = json
            .get("eventId")
            .or_else(|| json.get("event_id"))
            .and_then(|v| v.as_u64())
            .unwrap_or(0);
        assert_eq!(event_id, 1);
        Ok(())
    }

    #[tokio::test]
    async fn ws_handler_should_replay_from_last_event_id() -> Result<()> {
        let state = test_state();
        let ek = EncodingKey::load(include_str!("../../chat_core/fixtures/encoding.pem"))?;
        let user = chat_core::User::new(1, "Tyr Chen", "tchen@acme.org");
        let notify_ticket = ek.sign_notify_ticket(user, 300)?;

        let _ = state.build_user_event_for_recipient(
            1,
            Arc::new(AppEvent::NewMessage(ChatMessage {
                id: 1,
                chat_id: 2,
                sender_id: 1,
                content: "m1".to_string(),
                modified_content: None,
                files: vec![],
                created_at: Utc::now(),
            })),
            None,
        );
        let _ = state.build_user_event_for_recipient(
            1,
            Arc::new(AppEvent::NewMessage(ChatMessage {
                id: 2,
                chat_id: 2,
                sender_id: 1,
                content: "m2".to_string(),
                modified_content: None,
                files: vec![],
                created_at: Utc::now(),
            })),
            None,
        );

        let app = Router::new()
            .route("/ws", get(ws_handler))
            .layer(from_fn_with_state(state.clone(), verify_notify_ticket))
            .with_state(state.clone());
        let listener = TcpListener::bind("127.0.0.1:0").await?;
        let addr = listener.local_addr()?;
        tokio::spawn(async move {
            axum::serve(listener, app).await.unwrap();
        });

        let (mut socket,) = connect_global_ws(addr, &notify_ticket, Some("lastEventId=1")).await?;
        let welcome = tokio::time::timeout(Duration::from_secs(2), socket.next()).await?;
        let welcome_text = welcome
            .expect("should receive welcome")
            .expect("welcome should be ws ok")
            .into_text()?
            .to_string();
        let welcome_json: serde_json::Value = serde_json::from_str(&welcome_text)?;
        assert_eq!(welcome_json["type"], "welcome");
        let replay_count = welcome_json
            .get("replayCount")
            .or_else(|| welcome_json.get("replay_count"))
            .and_then(|v| v.as_u64())
            .unwrap_or(0);
        assert_eq!(replay_count, 1);

        let replay = tokio::time::timeout(Duration::from_secs(2), socket.next()).await?;
        let replay_text = replay
            .expect("should receive replay")
            .expect("replay should be ws ok")
            .into_text()?
            .to_string();
        let replay_json: serde_json::Value = serde_json::from_str(&replay_text)?;
        assert_eq!(replay_json["type"], "event");
        let replay_event_id = replay_json
            .get("eventId")
            .or_else(|| replay_json.get("event_id"))
            .and_then(|v| v.as_u64())
            .unwrap_or(0);
        assert_eq!(replay_event_id, 2);
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

        let welcome = tokio::time::timeout(Duration::from_secs(12), socket.next()).await?;
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
        let baseline_ack_seq = welcome_json
            .get("baselineAckSeq")
            .or_else(|| welcome_json.get("baseline_ack_seq"))
            .and_then(|v| v.as_u64())
            .expect("welcome should carry baselineAckSeq");
        assert_eq!(baseline_ack_seq, 0);
        let replay_count = welcome_json
            .get("replayCount")
            .or_else(|| welcome_json.get("replay_count"))
            .and_then(|v| v.as_u64())
            .expect("welcome should carry replayCount");
        assert_eq!(replay_count, 0);
        let heartbeat_interval_ms = welcome_json
            .get("heartbeatIntervalMs")
            .or_else(|| welcome_json.get("heartbeat_interval_ms"))
            .and_then(|v| v.as_u64())
            .expect("welcome should carry heartbeatIntervalMs");
        assert!(heartbeat_interval_ms > 0);
        let heartbeat_timeout_ms = welcome_json
            .get("heartbeatTimeoutMs")
            .or_else(|| welcome_json.get("heartbeat_timeout_ms"))
            .and_then(|v| v.as_u64())
            .expect("welcome should carry heartbeatTimeoutMs");
        assert!(heartbeat_timeout_ms > heartbeat_interval_ms);

        for _ in 0..40 {
            if state.users.contains_key(&1) {
                break;
            }
            tokio::time::sleep(Duration::from_millis(25)).await;
        }
        let tx = state.users.get(&1).expect("user channel should exist");
        let out_of_room_event = state.build_user_event_for_recipient(
            1,
            Arc::new(AppEvent::DebateParticipantJoined(
                crate::notif::DebateParticipantJoined {
                    session_id: 13,
                    user_id: 1,
                    side: "pro".to_string(),
                    pro_count: 2,
                    con_count: 1,
                },
            )),
            None,
        );
        tx.send(Arc::new(out_of_room_event))?;
        let no_msg = tokio::time::timeout(Duration::from_millis(200), socket.next()).await;
        assert!(no_msg.is_err(), "session 13 event should be filtered out");

        let in_room_event = state.build_user_event_for_recipient(
            1,
            Arc::new(AppEvent::DebateParticipantJoined(
                crate::notif::DebateParticipantJoined {
                    session_id: 12,
                    user_id: 1,
                    side: "con".to_string(),
                    pro_count: 2,
                    con_count: 2,
                },
            )),
            None,
        );
        tx.send(Arc::new(in_room_event))?;

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
        let event_seq = room_json
            .get("eventSeq")
            .or_else(|| room_json.get("event_seq"))
            .and_then(|v| v.as_u64())
            .expect("room event should carry event seq");
        assert!(event_seq > 0);
        let payload_session_id = room_json["payload"]
            .get("sessionId")
            .or_else(|| room_json["payload"].get("session_id"))
            .and_then(|v| v.as_i64())
            .expect("room event payload should carry session id");
        assert_eq!(payload_session_id, 12);
        Ok(())
    }

    #[tokio::test]
    async fn debate_room_ws_handler_should_reply_app_ping_with_pong() -> Result<()> {
        let state = test_state();
        let ek = EncodingKey::load(include_str!("../../chat_core/fixtures/encoding.pem"))?;
        let user = chat_core::User::new(1, "Tyr Chen", "tchen@acme.org");
        let notify_ticket = ek.sign_notify_ticket(user, 300)?;

        let app = Router::new()
            .route("/ws/debate/:session_id", get(debate_room_ws_handler))
            .layer(from_fn_with_state(state.clone(), verify_notify_ticket))
            .with_state(state);
        let listener = TcpListener::bind("127.0.0.1:0").await?;
        let addr = listener.local_addr()?;
        tokio::spawn(async move {
            axum::serve(listener, app).await.unwrap();
        });

        let (mut socket, _) =
            connect_async(format!("ws://{addr}/ws/debate/12?token={notify_ticket}")).await?;
        let _welcome = tokio::time::timeout(Duration::from_secs(2), socket.next()).await?;

        socket
            .send(tokio_tungstenite::tungstenite::Message::Text(
                r#"{"type":"ping"}"#.to_string(),
            ))
            .await?;

        let maybe_msg = tokio::time::timeout(Duration::from_secs(2), socket.next()).await?;
        let msg = maybe_msg.expect("should receive pong message")?;
        let text = msg.into_text()?.to_string();
        let json: serde_json::Value = serde_json::from_str(&text)?;
        assert_eq!(json["type"], "pong");
        Ok(())
    }

    #[tokio::test]
    async fn debate_room_ws_handler_should_emit_sync_required_when_persist_failed() -> Result<()> {
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
        let _welcome = tokio::time::timeout(Duration::from_secs(2), socket.next()).await?;

        for _ in 0..40 {
            if state.users.contains_key(&1) {
                break;
            }
            tokio::time::sleep(Duration::from_millis(25)).await;
        }
        let tx = state.users.get(&1).expect("user channel should exist");
        let sync_event = state
            .build_sync_required_user_event_for_recipient(
                Arc::new(AppEvent::DebateParticipantJoined(DebateParticipantJoined {
                    session_id: 12,
                    user_id: 1,
                    side: "pro".to_string(),
                    pro_count: 2,
                    con_count: 1,
                })),
                "persist_failed",
            )
            .expect("sync event should require debate session id");
        tx.send(Arc::new(sync_event))?;

        let sync_msg = tokio::time::timeout(Duration::from_secs(12), socket.next()).await?;
        let sync_text = sync_msg
            .expect("should receive syncRequired message")
            .expect("syncRequired should be ws ok")
            .into_text()?
            .to_string();
        let sync_json: serde_json::Value = serde_json::from_str(&sync_text)?;
        assert_eq!(sync_json["type"], "syncRequired");
        assert_eq!(sync_json["reason"], "persist_failed");
        let strategy = sync_json
            .get("strategy")
            .and_then(|v| v.as_str())
            .expect("syncRequired should carry strategy");
        assert_eq!(strategy, "snapshot_then_reconnect");
        let suggested_last_ack_seq = sync_json
            .get("suggestedLastAckSeq")
            .or_else(|| sync_json.get("suggested_last_ack_seq"))
            .and_then(|v| v.as_u64())
            .expect("syncRequired should carry suggestedLastAckSeq");
        assert_eq!(suggested_last_ack_seq, 0);
        let expected_from_seq = sync_json
            .get("expectedFromSeq")
            .or_else(|| sync_json.get("expected_from_seq"))
            .and_then(|v| v.as_u64())
            .expect("syncRequired should carry expectedFromSeq");
        assert_eq!(expected_from_seq, 1);
        let no_room_event = tokio::time::timeout(Duration::from_millis(200), socket.next()).await;
        assert!(
            no_room_event.is_err(),
            "persist_failed should not stream a roomEvent before recovery"
        );
        Ok(())
    }

    #[tokio::test]
    async fn debate_room_ws_handler_should_throttle_repeated_sync_required_with_same_reason(
    ) -> Result<()> {
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
        let _welcome = tokio::time::timeout(Duration::from_secs(2), socket.next()).await?;

        for _ in 0..40 {
            if state.users.contains_key(&1) {
                break;
            }
            tokio::time::sleep(Duration::from_millis(25)).await;
        }
        let tx = state.users.get(&1).expect("user channel should exist");
        let make_sync_event = || {
            state
                .build_sync_required_user_event_for_recipient(
                    Arc::new(AppEvent::DebateParticipantJoined(DebateParticipantJoined {
                        session_id: 12,
                        user_id: 1,
                        side: "pro".to_string(),
                        pro_count: 2,
                        con_count: 1,
                    })),
                    "persist_failed",
                )
                .expect("sync event should require debate session id")
        };

        tx.send(Arc::new(make_sync_event()))?;
        let first_sync = tokio::time::timeout(Duration::from_secs(2), socket.next()).await?;
        let first_sync_json: serde_json::Value = serde_json::from_str(
            &first_sync
                .expect("should receive first sync message")
                .expect("first sync should be ws ok")
                .into_text()?
                .to_string(),
        )?;
        assert_eq!(first_sync_json["type"], "syncRequired");
        assert_eq!(first_sync_json["reason"], "persist_failed");

        tx.send(Arc::new(make_sync_event()))?;
        let maybe_second = tokio::time::timeout(Duration::from_millis(250), socket.next()).await;
        if let Ok(Some(Ok(msg))) = maybe_second {
            let text = msg.into_text()?.to_string();
            let json: serde_json::Value = serde_json::from_str(&text)?;
            assert_ne!(
                json["type"], "syncRequired",
                "second syncRequired should be throttled within cooldown"
            );
        }

        tokio::time::sleep(ROOM_SYNC_REQUIRED_COOLDOWN + Duration::from_millis(100)).await;
        tx.send(Arc::new(make_sync_event()))?;
        let third_sync = tokio::time::timeout(Duration::from_secs(2), socket.next()).await?;
        let third_sync_json: serde_json::Value = serde_json::from_str(
            &third_sync
                .expect("should receive syncRequired after cooldown")
                .expect("syncRequired after cooldown should be ws ok")
                .into_text()?
                .to_string(),
        )?;
        assert_eq!(third_sync_json["type"], "syncRequired");
        assert_eq!(third_sync_json["reason"], "persist_failed");
        Ok(())
    }

    #[tokio::test]
    async fn debate_room_ws_handler_should_accept_ack_frame() -> Result<()> {
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
        let _welcome = tokio::time::timeout(Duration::from_secs(2), socket.next()).await?;

        for _ in 0..40 {
            if state.users.contains_key(&1) {
                break;
            }
            tokio::time::sleep(Duration::from_millis(25)).await;
        }
        let tx = state.users.get(&1).expect("user channel should exist");
        let first_event = state.build_user_event_for_recipient(
            1,
            Arc::new(AppEvent::DebateParticipantJoined(
                crate::notif::DebateParticipantJoined {
                    session_id: 12,
                    user_id: 1,
                    side: "pro".to_string(),
                    pro_count: 2,
                    con_count: 1,
                },
            )),
            None,
        );
        tx.send(Arc::new(first_event))?;

        let first_msg = tokio::time::timeout(Duration::from_secs(2), socket.next()).await?;
        let first_text = first_msg
            .expect("should receive first room event")
            .expect("first room event should be ws ok")
            .into_text()?
            .to_string();
        let first_json: serde_json::Value = serde_json::from_str(&first_text)?;
        assert_eq!(first_json["type"], "roomEvent");
        let first_seq = first_json
            .get("eventSeq")
            .or_else(|| first_json.get("event_seq"))
            .and_then(|v| v.as_u64())
            .expect("first room event should carry event seq");

        socket
            .send(tokio_tungstenite::tungstenite::Message::Text(format!(
                r#"{{"type":"ack","eventSeq":{first_seq}}}"#
            )))
            .await?;

        let second_event = state.build_user_event_for_recipient(
            1,
            Arc::new(AppEvent::DebateParticipantJoined(
                crate::notif::DebateParticipantJoined {
                    session_id: 12,
                    user_id: 2,
                    side: "con".to_string(),
                    pro_count: 2,
                    con_count: 2,
                },
            )),
            None,
        );
        tx.send(Arc::new(second_event))?;

        let second_msg = tokio::time::timeout(Duration::from_secs(2), socket.next()).await?;
        let second_text = second_msg
            .expect("should receive second room event")
            .expect("second room event should be ws ok")
            .into_text()?
            .to_string();
        let second_json: serde_json::Value = serde_json::from_str(&second_text)?;
        assert_eq!(second_json["type"], "roomEvent");
        let second_seq = second_json
            .get("eventSeq")
            .or_else(|| second_json.get("event_seq"))
            .and_then(|v| v.as_u64())
            .expect("second room event should carry event seq");
        assert!(second_seq > first_seq);
        Ok(())
    }

    #[tokio::test]
    async fn debate_room_ws_handler_should_replay_from_last_ack_seq() -> Result<()> {
        let state = test_state();
        let ek = EncodingKey::load(include_str!("../../chat_core/fixtures/encoding.pem"))?;
        let user = chat_core::User::new(1, "Tyr Chen", "tchen@acme.org");
        let notify_ticket = ek.sign_notify_ticket(user, 300)?;

        let _ = state.build_user_event_for_recipient(
            1,
            Arc::new(AppEvent::DebateParticipantJoined(DebateParticipantJoined {
                session_id: 12,
                user_id: 1,
                side: "pro".to_string(),
                pro_count: 2,
                con_count: 1,
            })),
            None,
        );
        let _ = state.build_user_event_for_recipient(
            1,
            Arc::new(AppEvent::DebateParticipantJoined(DebateParticipantJoined {
                session_id: 12,
                user_id: 2,
                side: "con".to_string(),
                pro_count: 2,
                con_count: 2,
            })),
            None,
        );

        let app = Router::new()
            .route("/ws/debate/:session_id", get(debate_room_ws_handler))
            .layer(from_fn_with_state(state.clone(), verify_notify_ticket))
            .with_state(state);
        let listener = TcpListener::bind("127.0.0.1:0").await?;
        let addr = listener.local_addr()?;
        tokio::spawn(async move {
            axum::serve(listener, app).await.unwrap();
        });

        let (mut socket, _) = connect_async(format!(
            "ws://{addr}/ws/debate/12?token={notify_ticket}&lastAckSeq=1"
        ))
        .await?;
        let _welcome = tokio::time::timeout(Duration::from_secs(2), socket.next()).await?;

        let replay_msg = tokio::time::timeout(Duration::from_secs(2), socket.next()).await?;
        let replay_text = replay_msg
            .expect("should receive replay event")
            .expect("replay event should be ws ok")
            .into_text()?
            .to_string();
        let replay_json: serde_json::Value = serde_json::from_str(&replay_text)?;
        assert_eq!(replay_json["type"], "roomEvent");
        let event_seq = replay_json
            .get("eventSeq")
            .or_else(|| replay_json.get("event_seq"))
            .and_then(|v| v.as_u64())
            .expect("replay event should carry event seq");
        assert_eq!(event_seq, 2);
        Ok(())
    }

    #[tokio::test]
    async fn debate_room_ws_handler_should_clamp_future_last_ack_seq_and_stream_new_event(
    ) -> Result<()> {
        let state = test_state();
        let ek = EncodingKey::load(include_str!("../../chat_core/fixtures/encoding.pem"))?;
        let user = chat_core::User::new(1, "Tyr Chen", "tchen@acme.org");
        let notify_ticket = ek.sign_notify_ticket(user, 300)?;

        let _ = state.build_user_event_for_recipient(
            1,
            Arc::new(AppEvent::DebateParticipantJoined(DebateParticipantJoined {
                session_id: 12,
                user_id: 1,
                side: "pro".to_string(),
                pro_count: 2,
                con_count: 1,
            })),
            None,
        );
        let _ = state.build_user_event_for_recipient(
            1,
            Arc::new(AppEvent::DebateParticipantJoined(DebateParticipantJoined {
                session_id: 12,
                user_id: 2,
                side: "con".to_string(),
                pro_count: 2,
                con_count: 2,
            })),
            None,
        );

        let app = Router::new()
            .route("/ws/debate/:session_id", get(debate_room_ws_handler))
            .layer(from_fn_with_state(state.clone(), verify_notify_ticket))
            .with_state(state.clone());
        let listener = TcpListener::bind("127.0.0.1:0").await?;
        let addr = listener.local_addr()?;
        tokio::spawn(async move {
            axum::serve(listener, app).await.unwrap();
        });

        let (mut socket, _) = connect_async(format!(
            "ws://{addr}/ws/debate/12?token={notify_ticket}&lastAckSeq=999"
        ))
        .await?;

        let welcome = tokio::time::timeout(Duration::from_secs(2), socket.next()).await?;
        let welcome_text = welcome
            .expect("should receive welcome message")
            .expect("welcome message should be ws ok")
            .into_text()?
            .to_string();
        let welcome_json: serde_json::Value = serde_json::from_str(&welcome_text)?;
        assert_eq!(welcome_json["type"], "welcome");
        let baseline_ack_seq = welcome_json
            .get("baselineAckSeq")
            .or_else(|| welcome_json.get("baseline_ack_seq"))
            .and_then(|v| v.as_u64())
            .expect("welcome should carry baselineAckSeq");
        assert_eq!(baseline_ack_seq, 2);

        for _ in 0..40 {
            if state.users.contains_key(&1) {
                break;
            }
            tokio::time::sleep(Duration::from_millis(25)).await;
        }
        let tx = state.users.get(&1).expect("user channel should exist");
        let third_event = state.build_user_event_for_recipient(
            1,
            Arc::new(AppEvent::DebateParticipantJoined(DebateParticipantJoined {
                session_id: 12,
                user_id: 3,
                side: "pro".to_string(),
                pro_count: 3,
                con_count: 2,
            })),
            None,
        );
        tx.send(Arc::new(third_event))?;

        let room_msg = tokio::time::timeout(Duration::from_secs(2), socket.next()).await?;
        let room_text = room_msg
            .expect("should receive new room event after clamp")
            .expect("room event should be ws ok")
            .into_text()?
            .to_string();
        let room_json: serde_json::Value = serde_json::from_str(&room_text)?;
        assert_eq!(room_json["type"], "roomEvent");
        let event_seq = room_json
            .get("eventSeq")
            .or_else(|| room_json.get("event_seq"))
            .and_then(|v| v.as_u64())
            .expect("room event should carry event seq");
        assert_eq!(event_seq, 3);
        Ok(())
    }

    #[tokio::test]
    async fn debate_room_ws_handler_should_emit_replay_storage_unavailable_when_db_unavailable_and_memory_has_gap(
    ) -> Result<()> {
        let state = test_state_with_db_url("postgres://localhost:1/chat?connect_timeout=1");
        let ek = EncodingKey::load(include_str!("../../chat_core/fixtures/encoding.pem"))?;
        let user = chat_core::User::new(1, "Tyr Chen", "tchen@acme.org");
        let notify_ticket = ek.sign_notify_ticket(user, 300)?;

        let event_payload = AppEvent::DebateParticipantJoined(DebateParticipantJoined {
            session_id: 12,
            user_id: 1,
            side: "pro".to_string(),
            pro_count: 2,
            con_count: 1,
        });
        let event_value = serde_json::to_value(&event_payload)?;
        let _ = state.build_user_event_for_recipient(
            1,
            Arc::new(event_payload),
            Some(DebateReplayEvent {
                session_id: 12,
                event_seq: 50,
                event_name: "DebateParticipantJoined".to_string(),
                payload: event_value.clone(),
                event_at_ms: now_unix_ms(),
            }),
        );
        let _ = state.build_user_event_for_recipient(
            1,
            Arc::new(AppEvent::DebateParticipantJoined(DebateParticipantJoined {
                session_id: 12,
                user_id: 2,
                side: "con".to_string(),
                pro_count: 2,
                con_count: 2,
            })),
            Some(DebateReplayEvent {
                session_id: 12,
                event_seq: 51,
                event_name: "DebateParticipantJoined".to_string(),
                payload: event_value,
                event_at_ms: now_unix_ms(),
            }),
        );

        let app = Router::new()
            .route("/ws/debate/:session_id", get(debate_room_ws_handler))
            .layer(from_fn_with_state(state.clone(), verify_notify_ticket))
            .with_state(state);
        let listener = TcpListener::bind("127.0.0.1:0").await?;
        let addr = listener.local_addr()?;
        tokio::spawn(async move {
            axum::serve(listener, app).await.unwrap();
        });

        let (mut socket, _) = connect_async(format!(
            "ws://{addr}/ws/debate/12?token={notify_ticket}&lastAckSeq=1"
        ))
        .await?;
        let _welcome = tokio::time::timeout(Duration::from_secs(40), socket.next()).await?;

        let sync_msg = tokio::time::timeout(Duration::from_secs(40), socket.next()).await?;
        let sync_text = sync_msg
            .expect("should receive syncRequired message")
            .expect("syncRequired should be ws ok")
            .into_text()?
            .to_string();
        let sync_json: serde_json::Value = serde_json::from_str(&sync_text)?;
        assert_eq!(sync_json["type"], "syncRequired");
        assert_eq!(sync_json["reason"], "replay_storage_unavailable");
        let suggested_last_ack_seq = sync_json
            .get("suggestedLastAckSeq")
            .or_else(|| sync_json.get("suggested_last_ack_seq"))
            .and_then(|v| v.as_u64())
            .expect("syncRequired should carry suggestedLastAckSeq");
        assert_eq!(suggested_last_ack_seq, 1);
        let gap_from_seq = sync_json
            .get("gapFromSeq")
            .or_else(|| sync_json.get("gap_from_seq"))
            .and_then(|v| v.as_u64())
            .expect("syncRequired should carry gapFromSeq");
        assert_eq!(gap_from_seq, 2);
        let gap_to_seq = sync_json
            .get("gapToSeq")
            .or_else(|| sync_json.get("gap_to_seq"))
            .and_then(|v| v.as_u64())
            .expect("syncRequired should carry gapToSeq");
        assert_eq!(gap_to_seq, 49);
        let latest_event_seq = sync_json
            .get("latestEventSeq")
            .or_else(|| sync_json.get("latest_event_seq"))
            .and_then(|v| v.as_u64())
            .expect("syncRequired should carry latestEventSeq");
        assert_eq!(latest_event_seq, 51);
        assert_eq!(sync_json["strategy"], "snapshot_then_reconnect");

        if let Ok(Some(Ok(msg))) =
            tokio::time::timeout(Duration::from_millis(200), socket.next()).await
        {
            if let Ok(text) = msg.into_text() {
                let payload = text.to_string();
                if let Ok(json) = serde_json::from_str::<serde_json::Value>(&payload) {
                    assert_ne!(
                        json["type"], "roomEvent",
                        "forced sync should not stream room events before recovery"
                    );
                }
            }
        }
        Ok(())
    }

    #[tokio::test]
    async fn debate_room_ws_handler_should_replay_events_when_db_unavailable_but_memory_window_is_contiguous(
    ) -> Result<()> {
        let state = test_state_with_db_url("postgres://localhost:1/chat?connect_timeout=1");
        let ek = EncodingKey::load(include_str!("../../chat_core/fixtures/encoding.pem"))?;
        let user = chat_core::User::new(1, "Tyr Chen", "tchen@acme.org");
        let notify_ticket = ek.sign_notify_ticket(user, 300)?;

        let first_payload = AppEvent::DebateParticipantJoined(DebateParticipantJoined {
            session_id: 12,
            user_id: 1,
            side: "pro".to_string(),
            pro_count: 2,
            con_count: 1,
        });
        let first_value = serde_json::to_value(&first_payload)?;
        let second_payload = AppEvent::DebateParticipantJoined(DebateParticipantJoined {
            session_id: 12,
            user_id: 2,
            side: "con".to_string(),
            pro_count: 2,
            con_count: 2,
        });
        let second_value = serde_json::to_value(&second_payload)?;
        let _ = state.build_user_event_for_recipient(
            1,
            Arc::new(first_payload),
            Some(DebateReplayEvent {
                session_id: 12,
                event_seq: 2,
                event_name: "DebateParticipantJoined".to_string(),
                payload: first_value,
                event_at_ms: now_unix_ms(),
            }),
        );
        let _ = state.build_user_event_for_recipient(
            1,
            Arc::new(second_payload),
            Some(DebateReplayEvent {
                session_id: 12,
                event_seq: 3,
                event_name: "DebateParticipantJoined".to_string(),
                payload: second_value,
                event_at_ms: now_unix_ms(),
            }),
        );

        let app = Router::new()
            .route("/ws/debate/:session_id", get(debate_room_ws_handler))
            .layer(from_fn_with_state(state.clone(), verify_notify_ticket))
            .with_state(state);
        let listener = TcpListener::bind("127.0.0.1:0").await?;
        let addr = listener.local_addr()?;
        tokio::spawn(async move {
            axum::serve(listener, app).await.unwrap();
        });

        let (mut socket, _) = connect_async(format!(
            "ws://{addr}/ws/debate/12?token={notify_ticket}&lastAckSeq=1"
        ))
        .await?;
        let _welcome = tokio::time::timeout(Duration::from_secs(40), socket.next()).await?;

        let first_msg = tokio::time::timeout(Duration::from_secs(40), socket.next()).await?;
        let first_text = first_msg
            .expect("should receive first replay event")
            .expect("first replay event should be ws ok")
            .into_text()?
            .to_string();
        let first_json: serde_json::Value = serde_json::from_str(&first_text)?;
        assert_eq!(first_json["type"], "roomEvent");
        let first_seq = first_json
            .get("eventSeq")
            .or_else(|| first_json.get("event_seq"))
            .and_then(|v| v.as_u64())
            .expect("first replay event should carry seq");
        assert_eq!(first_seq, 2);

        let second_msg = tokio::time::timeout(Duration::from_secs(40), socket.next()).await?;
        let second_text = second_msg
            .expect("should receive second replay event")
            .expect("second replay event should be ws ok")
            .into_text()?
            .to_string();
        let second_json: serde_json::Value = serde_json::from_str(&second_text)?;
        assert_eq!(second_json["type"], "roomEvent");
        let second_seq = second_json
            .get("eventSeq")
            .or_else(|| second_json.get("event_seq"))
            .and_then(|v| v.as_u64())
            .expect("second replay event should carry seq");
        assert_eq!(second_seq, 3);
        Ok(())
    }

    #[tokio::test]
    async fn debate_room_ws_handler_should_require_sync_when_replay_window_has_gap() -> Result<()> {
        let state = test_state();
        let ek = EncodingKey::load(include_str!("../../chat_core/fixtures/encoding.pem"))?;
        let user = chat_core::User::new(1, "Tyr Chen", "tchen@acme.org");
        let notify_ticket = ek.sign_notify_ticket(user, 300)?;

        let event_payload = AppEvent::DebateParticipantJoined(DebateParticipantJoined {
            session_id: 12,
            user_id: 1,
            side: "pro".to_string(),
            pro_count: 2,
            con_count: 1,
        });
        let event_value = serde_json::to_value(&event_payload)?;
        let _ = state.build_user_event_for_recipient(
            1,
            Arc::new(event_payload),
            Some(DebateReplayEvent {
                session_id: 12,
                event_seq: 50,
                event_name: "DebateParticipantJoined".to_string(),
                payload: event_value.clone(),
                event_at_ms: now_unix_ms(),
            }),
        );
        let _ = state.build_user_event_for_recipient(
            1,
            Arc::new(AppEvent::DebateParticipantJoined(DebateParticipantJoined {
                session_id: 12,
                user_id: 2,
                side: "con".to_string(),
                pro_count: 2,
                con_count: 2,
            })),
            Some(DebateReplayEvent {
                session_id: 12,
                event_seq: 51,
                event_name: "DebateParticipantJoined".to_string(),
                payload: event_value,
                event_at_ms: now_unix_ms(),
            }),
        );

        let app = Router::new()
            .route("/ws/debate/:session_id", get(debate_room_ws_handler))
            .layer(from_fn_with_state(state.clone(), verify_notify_ticket))
            .with_state(state);
        let listener = TcpListener::bind("127.0.0.1:0").await?;
        let addr = listener.local_addr()?;
        tokio::spawn(async move {
            axum::serve(listener, app).await.unwrap();
        });

        let (mut socket, _) = connect_async(format!(
            "ws://{addr}/ws/debate/12?token={notify_ticket}&lastAckSeq=1"
        ))
        .await?;
        let welcome = tokio::time::timeout(Duration::from_secs(2), socket.next()).await?;
        let welcome_msg = welcome
            .expect("should receive welcome message")
            .expect("welcome message should be ws ok");
        let welcome_text = welcome_msg.into_text()?.to_string();
        let welcome_json: serde_json::Value = serde_json::from_str(&welcome_text)?;
        assert_eq!(welcome_json["type"], "welcome");
        let replay_count = welcome_json
            .get("replayCount")
            .or_else(|| welcome_json.get("replay_count"))
            .and_then(|v| v.as_u64())
            .expect("welcome should carry replayCount");
        assert_eq!(replay_count, 0);
        let last_event_seq = welcome_json
            .get("lastEventSeq")
            .or_else(|| welcome_json.get("last_event_seq"))
            .and_then(|v| v.as_u64())
            .expect("welcome should carry lastEventSeq");
        assert_eq!(last_event_seq, 51);

        let sync_msg = tokio::time::timeout(Duration::from_secs(2), socket.next()).await?;
        let sync_text = sync_msg
            .expect("should receive syncRequired message")
            .expect("syncRequired should be ws ok")
            .into_text()?
            .to_string();
        let sync_json: serde_json::Value = serde_json::from_str(&sync_text)?;
        assert_eq!(sync_json["type"], "syncRequired");
        assert_eq!(sync_json["reason"], "replay_window_miss");
        let suggested_last_ack_seq = sync_json
            .get("suggestedLastAckSeq")
            .or_else(|| sync_json.get("suggested_last_ack_seq"))
            .and_then(|v| v.as_u64())
            .expect("syncRequired should carry suggestedLastAckSeq");
        assert_eq!(suggested_last_ack_seq, 1);
        let gap_from_seq = sync_json
            .get("gapFromSeq")
            .or_else(|| sync_json.get("gap_from_seq"))
            .and_then(|v| v.as_u64())
            .expect("syncRequired should carry gapFromSeq");
        assert_eq!(gap_from_seq, 2);
        let gap_to_seq = sync_json
            .get("gapToSeq")
            .or_else(|| sync_json.get("gap_to_seq"))
            .and_then(|v| v.as_u64())
            .expect("syncRequired should carry gapToSeq");
        assert_eq!(gap_to_seq, 49);
        assert_eq!(sync_json["strategy"], "snapshot_then_reconnect");

        let no_replay = tokio::time::timeout(Duration::from_millis(200), socket.next()).await;
        assert!(
            no_replay.is_err(),
            "gap replay should not stream room events"
        );
        Ok(())
    }

    #[tokio::test]
    async fn ws_handler_should_reject_missing_subprotocol_token() -> Result<()> {
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
