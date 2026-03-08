mod agent;
mod ai_internal;
mod auth;
mod chat;
mod debate;
pub(crate) mod debate_judge;
pub(crate) mod debate_ops;
pub(crate) mod debate_room;
mod messages;
mod payment;
mod ticket;
mod workspace;

use axum::response::IntoResponse;

pub(crate) use agent::*;
pub(crate) use ai_internal::*;
pub(crate) use auth::*;
pub(crate) use chat::*;
pub(crate) use debate::*;
pub(crate) use messages::*;
pub(crate) use payment::*;
pub(crate) use ticket::*;
pub(crate) use workspace::*;

pub(crate) async fn index_handler() -> impl IntoResponse {
    "index"
}
