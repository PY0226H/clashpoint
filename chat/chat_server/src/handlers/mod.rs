mod agent;
mod ai_internal;
mod analytics_proxy;
mod auth;
mod chat;
mod debate;
pub(crate) mod debate_judge;
mod debate_npc;
pub(crate) mod debate_ops;
pub(crate) mod debate_room;
mod messages;
mod payment;
mod ticket;
mod users;

use axum::response::IntoResponse;

pub(crate) use agent::*;
pub(crate) use ai_internal::*;
pub(crate) use analytics_proxy::*;
pub(crate) use auth::*;
pub(crate) use chat::*;
pub(crate) use debate::*;
pub(crate) use debate_npc::*;
pub(crate) use messages::*;
pub(crate) use payment::*;
pub(crate) use ticket::*;
pub(crate) use users::*;

pub(crate) async fn index_handler() -> impl IntoResponse {
    "index"
}
