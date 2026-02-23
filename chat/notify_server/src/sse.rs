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

    let stream = BroadcastStream::new(rx).filter_map(|v| v.ok()).map(|v| {
        let name = v.event_name();
        let v = serde_json::to_string(&v).expect("Failed to serialize event");
        debug!("Sending event {}: {:?}", name, v);
        Ok(Event::default().data(v).event(name))
    });

    Sse::new(stream).keep_alive(
        axum::response::sse::KeepAlive::new()
            .interval(Duration::from_secs(1))
            .text("keep-alive-text"),
    )
}
