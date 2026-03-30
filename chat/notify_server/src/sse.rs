use crate::AppState;
use axum::{
    extract::State,
    response::{sse::Event, Sse},
    Extension,
};
use chat_core::User;
use futures::Stream;
use std::{convert::Infallible, time::Duration};
use tokio_stream::{wrappers::BroadcastStream, StreamExt};
use tracing::{debug, info};

pub(crate) async fn sse_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
) -> Sse<impl Stream<Item = Result<Event, Infallible>>> {
    let user_id = user.id as u64;
    let rx = state.subscribe_user_events(user_id);
    info!("User {} subscribed", user_id);

    let stream = BroadcastStream::new(rx)
        .filter_map(|v| v.ok())
        .filter_map(move |event| {
            if event.app_event.is_debate_event() {
                debug!(
                    "skip debate event on SSE path: user_id={}, event_name={}",
                    user_id,
                    event.app_event.event_name()
                );
                return None;
            }
            let name = event.app_event.event_name();
            let payload =
                serde_json::to_string(event.app_event.as_ref()).expect("Failed to serialize event");
            Some(Ok(Event::default().data(payload).event(name)))
        });

    Sse::new(stream).keep_alive(
        axum::response::sse::KeepAlive::new()
            .interval(Duration::from_secs(15))
            .text("ka"),
    )
}
