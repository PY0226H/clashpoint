use crate::{middlewares::notify_error_response, AppState};
use axum::{
    extract::{Query, State},
    http::{HeaderMap, HeaderValue, StatusCode},
    response::{sse::Event, Response, Sse},
    Extension,
};
use chat_core::User;
use futures::{stream, Stream, StreamExt};
use serde::Deserialize;
use serde_json::json;
use std::{convert::Infallible, time::Duration};
use tokio_stream::wrappers::{errors::BroadcastStreamRecvError, BroadcastStream};
use tracing::{debug, info, warn};

#[derive(Debug, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub(crate) struct SseQuery {
    last_event_id: Option<u64>,
}

struct SseConnectionGuard {
    state: AppState,
    user_id: u64,
}

impl Drop for SseConnectionGuard {
    fn drop(&mut self) {
        self.state.release_sse_connection(self.user_id);
        self.state.cleanup_user_events_if_unused(self.user_id);
    }
}

pub(crate) async fn sse_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(query): Query<SseQuery>,
) -> Result<Sse<impl Stream<Item = Result<Event, Infallible>>>, Response> {
    let user_id = user.id as u64;
    let request_id = extract_request_id(&headers);
    if !state.try_acquire_sse_connection(user_id) {
        warn!(
            request_id,
            user_id,
            max_connections = 3_u32,
            "reject sse connection because per-user connection limit is reached"
        );
        return Err(notify_error_response(
            StatusCode::TOO_MANY_REQUESTS,
            "notify_sse_too_many_connections",
            "too many active sse connections for this user",
            request_id,
        ));
    }
    let guard = SseConnectionGuard {
        state: state.clone(),
        user_id,
    };
    let rx = state.subscribe_user_events(user_id);

    let requested_last_event_id =
        parse_last_event_id_header(headers.get("last-event-id")).or(query.last_event_id);
    let replay_window = state.replay_sse_events_for_user(user_id, requested_last_event_id);
    if replay_window.has_gap {
        state.observe_sse_sync_required();
        warn!(
            request_id,
            user_id,
            requested_last_event_id = requested_last_event_id.unwrap_or(0),
            latest_event_id = replay_window.latest_id,
            skipped = replay_window.skipped,
            "sse replay window has gap; client should refresh snapshot"
        );
    }
    info!(
        request_id,
        user_id,
        requested_last_event_id = requested_last_event_id.unwrap_or(0),
        replay_events = replay_window.events.len(),
        replay_has_gap = replay_window.has_gap,
        replay_latest_id = replay_window.latest_id,
        sse_connected_total = state.sse_metrics_snapshot().connected_total,
        "user subscribed via sse"
    );

    let replay_state = state.clone();
    let replay_stream = if replay_window.has_gap {
        let sync_event = build_sync_required_event(
            "replay_window_miss",
            replay_window.skipped,
            requested_last_event_id.unwrap_or(0),
            replay_window.latest_id,
        );
        stream::iter([Ok(sync_event)]).left_stream()
    } else {
        stream::iter(replay_window.events.into_iter().map(move |evt| {
            replay_state.observe_sse_replay_sent();
            Ok(Event::default()
                .id(evt.event_id.to_string())
                .event(evt.event_name)
                .data(evt.payload.to_string()))
        }))
        .right_stream()
    };

    let live_state = state.clone();
    let live_stream = BroadcastStream::new(rx).filter_map(move |item| {
        let live_state = live_state.clone();
        let request_id = request_id.clone();
        async move {
            match item {
                Ok(user_event) => {
                    if user_event.app_event.is_debate_event() {
                        live_state.observe_sse_event_filtered();
                        debug!(
                            user_id,
                            event_name = user_event.app_event.event_name(),
                            "skip debate event on sse path"
                        );
                        return None;
                    }
                    if let Some(sync) = user_event.sse_sync_required.as_ref() {
                        live_state.observe_sse_sync_required();
                        let payload = json!({
                            "event": "SyncRequired",
                            "reason": sync.reason,
                            "skipped": sync.skipped,
                            "suggestedLastEventId": sync.suggested_last_event_id,
                            "latestEventId": sync.latest_event_id,
                            "strategy": sync.strategy,
                        });
                        return Some(Ok(Event::default()
                            .event("SyncRequired")
                            .data(payload.to_string())));
                    }

                    let payload = match serde_json::to_string(user_event.app_event.as_ref()) {
                        Ok(v) => v,
                        Err(err) => {
                            live_state.observe_sse_event_filtered();
                            warn!(
                                request_id,
                                user_id,
                                event_name = user_event.app_event.event_name(),
                                err = %err,
                                "skip malformed sse event because serialization failed"
                            );
                            return None;
                        }
                    };
                    let mut event = Event::default()
                        .event(user_event.app_event.event_name())
                        .data(payload);
                    if let Some(replay) = user_event.sse_replay.as_ref() {
                        event = event.id(replay.event_id.to_string());
                    }
                    live_state.observe_sse_live_sent();
                    Some(Ok(event))
                }
                Err(BroadcastStreamRecvError::Lagged(skipped)) => {
                    live_state.observe_sse_lagged(skipped);
                    live_state.observe_sse_sync_required();
                    Some(Ok(build_sync_required_event(
                        "lagged_receiver",
                        skipped,
                        requested_last_event_id.unwrap_or(0),
                        0,
                    )))
                }
            }
        }
    });

    let stream = replay_stream.chain(live_stream).map(move |item| {
        let _hold = &guard;
        item
    });

    Ok(Sse::new(stream).keep_alive(
        axum::response::sse::KeepAlive::new()
            .interval(Duration::from_secs(15))
            .text("ka"),
    ))
}

fn parse_last_event_id_header(value: Option<&HeaderValue>) -> Option<u64> {
    let raw = value?.to_str().ok()?.trim();
    if raw.is_empty() {
        return None;
    }
    match raw.parse::<u64>() {
        Ok(v) => Some(v),
        Err(_) => {
            warn!("ignore invalid Last-Event-ID header");
            None
        }
    }
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

fn build_sync_required_event(
    reason: &str,
    skipped: u64,
    suggested_last_event_id: u64,
    latest_event_id: u64,
) -> Event {
    let payload = json!({
        "event": "SyncRequired",
        "reason": reason,
        "skipped": skipped,
        "suggestedLastEventId": suggested_last_event_id,
        "latestEventId": latest_event_id,
        "strategy": "snapshot_then_reconnect",
    });
    Event::default()
        .event("SyncRequired")
        .data(payload.to_string())
}
