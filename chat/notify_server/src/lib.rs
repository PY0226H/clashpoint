mod config;
mod error;
mod middlewares;
mod notif;
mod sse;
mod ws;

use axum::{
    http::Method,
    middleware::from_fn_with_state,
    response::{Html, IntoResponse},
    routing::get,
    Router,
};
use chat_core::{middlewares::TokenVerify, DecodingKey, User};
use dashmap::DashMap;
use middlewares::verify_notify_ticket;
use sse::sse_handler;
use std::{ops::Deref, sync::Arc};
use tokio::sync::broadcast;
use tower_http::cors::{self, CorsLayer};
use ws::ws_handler;

pub use config::AppConfig;
pub use error::AppError;
pub use notif::AppEvent;

const CHANNEL_CAPACITY: usize = 256;

pub type UserMap = Arc<DashMap<u64, broadcast::Sender<Arc<AppEvent>>>>;

#[derive(Clone)]
pub struct AppState(Arc<AppStateInner>);

pub struct AppStateInner {
    pub config: AppConfig,
    users: UserMap,
    dk: DecodingKey,
}

const INDEX_HTML: &str = include_str!("../index.html");

pub async fn get_router(config: AppConfig) -> anyhow::Result<Router> {
    let state = AppState::new(config);
    notif::setup_pg_listener(state.clone()).await?;

    let cors = CorsLayer::new()
        // allow `GET` and `POST` when accessing the resource
        .allow_methods([
            Method::GET,
            Method::POST,
            Method::PATCH,
            Method::DELETE,
            Method::PUT,
        ])
        .allow_origin(cors::Any)
        .allow_headers(cors::Any);

    let app = Router::new()
        .route("/events", get(sse_handler))
        .route("/ws", get(ws_handler))
        .layer(from_fn_with_state(state.clone(), verify_notify_ticket))
        .layer(cors)
        .route("/", get(index_handler))
        .with_state(state);

    Ok(app)
}

async fn index_handler() -> impl IntoResponse {
    Html(INDEX_HTML)
}

impl TokenVerify for AppState {
    type Error = AppError;

    fn verify(&self, token: &str) -> Result<User, Self::Error> {
        Ok(self.dk.verify(token)?)
    }
}

impl Deref for AppState {
    type Target = AppStateInner;

    fn deref(&self) -> &Self::Target {
        &self.0
    }
}

impl AppState {
    pub fn new(config: AppConfig) -> Self {
        let dk = DecodingKey::load(&config.auth.pk).expect("Failed to load public key");
        let users = Arc::new(DashMap::new());
        Self(Arc::new(AppStateInner { config, dk, users }))
    }

    pub(crate) fn subscribe_user_events(&self, user_id: u64) -> broadcast::Receiver<Arc<AppEvent>> {
        if let Some(tx) = self.users.get(&user_id) {
            tx.subscribe()
        } else {
            let (tx, rx) = broadcast::channel(CHANNEL_CAPACITY);
            self.users.insert(user_id, tx);
            rx
        }
    }
}
