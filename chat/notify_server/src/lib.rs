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
use chat_core::{
    middlewares::{AuthVerifyError, TokenVerify},
    DecodingKey, User,
};
use dashmap::DashMap;
use middlewares::verify_notify_ticket;
use serde_json::Value;
use sqlx::{postgres::PgPoolOptions, PgPool, Postgres, Row, Transaction};
use sse::sse_handler;
use std::{
    collections::VecDeque,
    ops::Deref,
    sync::Arc,
    time::{SystemTime, UNIX_EPOCH},
};
use tokio::sync::broadcast;
use tower_http::cors::{self, CorsLayer};
use tracing::info;
use ws::{debate_room_ws_handler, ws_handler};

pub use config::AppConfig;
pub use error::AppError;
pub use notif::AppEvent;

const CHANNEL_CAPACITY: usize = 256;
const DEBATE_REPLAY_HISTORY_CAPACITY: usize = 400;
const DEBATE_REPLAY_MAX_ON_CONNECT: usize = 200;

pub type UserMap = Arc<DashMap<u64, broadcast::Sender<Arc<UserEvent>>>>;
type DebateReplayMap = Arc<DashMap<(u64, i64), DebateReplayHistory>>;

#[derive(Debug, Clone)]
pub struct DebateReplayEvent {
    pub session_id: i64,
    pub event_seq: u64,
    pub event_name: String,
    pub payload: Value,
    pub event_at_ms: i64,
}

#[derive(Debug, Clone)]
pub struct UserEvent {
    pub app_event: Arc<AppEvent>,
    pub debate_replay: Option<DebateReplayEvent>,
}

#[derive(Debug)]
struct DebateReplayHistory {
    next_seq: u64,
    events: VecDeque<DebateReplayEvent>,
}

#[derive(Debug, Clone, Default)]
pub struct DebateReplayWindow {
    pub events: Vec<DebateReplayEvent>,
    pub latest_seq: u64,
    pub has_gap: bool,
    pub skipped: u64,
}

#[derive(Clone)]
pub struct AppState(Arc<AppStateInner>);

pub struct AppStateInner {
    pub config: AppConfig,
    users: UserMap,
    debate_replays: DebateReplayMap,
    db: PgPool,
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
        .route("/ws/debate/:session_id", get(debate_room_ws_handler))
        .layer(from_fn_with_state(state.clone(), verify_notify_ticket))
        .layer(cors)
        .route("/", get(index_handler))
        .route("/health", get(health_handler))
        .with_state(state);

    Ok(app)
}

async fn index_handler() -> impl IntoResponse {
    Html(INDEX_HTML)
}

async fn health_handler() -> &'static str {
    "ok"
}

impl TokenVerify for AppState {
    async fn verify(&self, token: &str) -> Result<User, AuthVerifyError> {
        self.dk
            .verify_access(token)
            .map(|decoded| decoded.user)
            .map_err(|err| err.to_auth_verify_error())
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
        let jwt_runtime = dk.runtime_config();
        info!(
            component = "notify_server",
            jwt_decoding_impl = jwt_runtime.implementation,
            jwt_legacy_fallback_enabled = jwt_runtime.legacy_fallback_enabled,
            "jwt runtime profile loaded"
        );
        let users = Arc::new(DashMap::new());
        let debate_replays = Arc::new(DashMap::new());
        let db = PgPoolOptions::new()
            .max_connections(5)
            .connect_lazy(&config.server.db_url)
            .expect("Failed to create notify-server db pool");
        Self(Arc::new(AppStateInner {
            config,
            dk,
            users,
            debate_replays,
            db,
        }))
    }

    pub(crate) fn subscribe_user_events(
        &self,
        user_id: u64,
    ) -> broadcast::Receiver<Arc<UserEvent>> {
        if let Some(tx) = self.users.get(&user_id) {
            tx.subscribe()
        } else {
            let (tx, rx) = broadcast::channel(CHANNEL_CAPACITY);
            self.users.insert(user_id, tx);
            rx
        }
    }

    pub(crate) fn cleanup_user_events_if_unused(&self, user_id: u64) {
        let should_remove = self
            .users
            .get(&user_id)
            .map(|tx| tx.receiver_count() == 0)
            .unwrap_or(false);
        if should_remove {
            self.users.remove(&user_id);
        }
    }

    pub(crate) fn build_user_event_for_recipient(
        &self,
        user_id: u64,
        app_event: Arc<AppEvent>,
        replay_event: Option<DebateReplayEvent>,
    ) -> UserEvent {
        let debate_replay = match replay_event {
            Some(v) => Some(self.append_persisted_replay_event(user_id, v)),
            None => self.append_debate_replay_event(user_id, app_event.as_ref()),
        };
        UserEvent {
            app_event,
            debate_replay,
        }
    }

    pub(crate) async fn replay_debate_events_for_user(
        &self,
        user_id: u64,
        session_id: i64,
        last_ack_seq: Option<u64>,
    ) -> DebateReplayWindow {
        let db_window = self
            .replay_debate_events_from_db(session_id, last_ack_seq)
            .await
            .ok();
        if let Some(window) = db_window {
            return window;
        }
        self.replay_debate_events_from_memory(user_id, session_id, last_ack_seq)
    }

    async fn replay_debate_events_from_db(
        &self,
        session_id: i64,
        last_ack_seq: Option<u64>,
    ) -> anyhow::Result<DebateReplayWindow> {
        let from_seq = last_ack_seq.unwrap_or(0);
        let latest_seq: i64 = sqlx::query_scalar(
            r#"
            SELECT COALESCE(MAX(event_seq), 0)
            FROM debate_room_events
            WHERE session_id = $1
            "#,
        )
        .bind(session_id)
        .fetch_one(&self.db)
        .await?;
        let latest_seq = latest_seq as u64;
        if from_seq >= latest_seq {
            return Ok(DebateReplayWindow {
                events: vec![],
                latest_seq,
                has_gap: false,
                skipped: 0,
            });
        }
        let rows = sqlx::query(
            r#"
            SELECT event_seq, event_name, payload, event_at
            FROM debate_room_events
            WHERE session_id = $1
              AND event_seq > $2
            ORDER BY event_seq ASC
            LIMIT $3
            "#,
        )
        .bind(session_id)
        .bind(from_seq as i64)
        .bind(DEBATE_REPLAY_MAX_ON_CONNECT as i64)
        .fetch_all(&self.db)
        .await?;
        let events = rows
            .into_iter()
            .filter_map(|row| {
                let event_seq = row.try_get::<i64, _>("event_seq").ok()? as u64;
                let event_name = row.try_get::<String, _>("event_name").ok()?;
                let payload = row.try_get::<Value, _>("payload").ok()?;
                let event_at = row
                    .try_get::<chrono::DateTime<chrono::Utc>, _>("event_at")
                    .ok()?;
                Some(DebateReplayEvent {
                    session_id,
                    event_seq,
                    event_name,
                    payload,
                    event_at_ms: event_at.timestamp_millis(),
                })
            })
            .collect::<Vec<_>>();
        let first_seq = events
            .first()
            .map(|evt| evt.event_seq)
            .unwrap_or(latest_seq + 1);
        let has_gap = from_seq.saturating_add(1) < first_seq;
        let skipped = if has_gap {
            first_seq.saturating_sub(from_seq.saturating_add(1))
        } else {
            0
        };
        Ok(DebateReplayWindow {
            events,
            latest_seq,
            has_gap,
            skipped,
        })
    }

    fn replay_debate_events_from_memory(
        &self,
        user_id: u64,
        session_id: i64,
        last_ack_seq: Option<u64>,
    ) -> DebateReplayWindow {
        let from_seq = last_ack_seq.unwrap_or(0);
        let Some(history) = self.debate_replays.get(&(user_id, session_id)) else {
            return DebateReplayWindow {
                events: vec![],
                latest_seq: 0,
                has_gap: false,
                skipped: 0,
            };
        };
        let latest_seq = history.latest_seq();
        if history.events.is_empty() || from_seq >= latest_seq {
            return DebateReplayWindow {
                events: vec![],
                latest_seq,
                has_gap: false,
                skipped: 0,
            };
        }

        let first_seq = history
            .events
            .front()
            .map(|evt| evt.event_seq)
            .unwrap_or(latest_seq + 1);
        let has_gap = from_seq.saturating_add(1) < first_seq;
        let skipped = if has_gap {
            first_seq.saturating_sub(from_seq.saturating_add(1))
        } else {
            0
        };
        let events = history
            .events
            .iter()
            .filter(|evt| evt.event_seq > from_seq)
            .take(DEBATE_REPLAY_MAX_ON_CONNECT)
            .cloned()
            .collect::<Vec<_>>();

        DebateReplayWindow {
            events,
            latest_seq,
            has_gap,
            skipped,
        }
    }

    pub(crate) async fn persist_debate_event(
        &self,
        app_event: &AppEvent,
    ) -> anyhow::Result<Option<DebateReplayEvent>> {
        let Some(session_id) = app_event.debate_session_id() else {
            return Ok(None);
        };
        let Some(dedupe_key) = app_event.debate_dedupe_key() else {
            return Ok(None);
        };
        let payload = serde_json::to_value(app_event)?;
        let mut tx = self.db.begin().await?;
        let _ = sqlx::query("SELECT pg_advisory_xact_lock($1)")
            .bind(session_id)
            .execute(&mut *tx)
            .await?;
        if let Some(existing) = self
            .find_persisted_event_by_dedupe(
                &mut tx,
                session_id,
                app_event.event_name(),
                &dedupe_key,
            )
            .await?
        {
            tx.commit().await?;
            return Ok(Some(existing));
        }
        let next_seq: i64 = sqlx::query_scalar(
            r#"
            SELECT COALESCE(MAX(event_seq), 0) + 1
            FROM debate_room_events
            WHERE session_id = $1
            "#,
        )
        .bind(session_id)
        .fetch_one(&mut *tx)
        .await?;
        let row = sqlx::query(
            r#"
            INSERT INTO debate_room_events(session_id, event_seq, event_name, dedupe_key, payload)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING event_seq, event_name, payload, event_at
            "#,
        )
        .bind(session_id)
        .bind(next_seq)
        .bind(app_event.event_name())
        .bind(dedupe_key)
        .bind(payload)
        .fetch_one(&mut *tx)
        .await?;
        tx.commit().await?;
        let event_at = row.get::<chrono::DateTime<chrono::Utc>, _>("event_at");
        Ok(Some(DebateReplayEvent {
            session_id,
            event_seq: row.get::<i64, _>("event_seq") as u64,
            event_name: row.get::<String, _>("event_name"),
            payload: row.get::<Value, _>("payload"),
            event_at_ms: event_at.timestamp_millis(),
        }))
    }

    fn append_debate_replay_event(
        &self,
        user_id: u64,
        app_event: &AppEvent,
    ) -> Option<DebateReplayEvent> {
        let session_id = app_event.debate_session_id()?;
        let payload = serde_json::to_value(app_event).ok()?;
        let raw = DebateReplayEvent {
            session_id,
            event_seq: 0,
            event_name: app_event.event_name().to_string(),
            payload,
            event_at_ms: now_unix_ms(),
        };
        let mut entry = self
            .debate_replays
            .entry((user_id, session_id))
            .or_default();
        Some(entry.push(raw))
    }

    fn append_persisted_replay_event(
        &self,
        user_id: u64,
        replay_event: DebateReplayEvent,
    ) -> DebateReplayEvent {
        let mut entry = self
            .debate_replays
            .entry((user_id, replay_event.session_id))
            .or_default();
        entry.push_with_seq(replay_event)
    }

    async fn find_persisted_event_by_dedupe(
        &self,
        tx: &mut Transaction<'_, Postgres>,
        session_id: i64,
        event_name: &str,
        dedupe_key: &str,
    ) -> anyhow::Result<Option<DebateReplayEvent>> {
        let row = sqlx::query(
            r#"
            SELECT event_seq, event_name, payload, event_at
            FROM debate_room_events
            WHERE session_id = $1
              AND event_name = $2
              AND dedupe_key = $3
            "#,
        )
        .bind(session_id)
        .bind(event_name)
        .bind(dedupe_key)
        .fetch_optional(&mut **tx)
        .await?;
        Ok(row.map(|row| {
            let event_at = row.get::<chrono::DateTime<chrono::Utc>, _>("event_at");
            DebateReplayEvent {
                session_id,
                event_seq: row.get::<i64, _>("event_seq") as u64,
                event_name: row.get::<String, _>("event_name"),
                payload: row.get::<Value, _>("payload"),
                event_at_ms: event_at.timestamp_millis(),
            }
        }))
    }
}

impl DebateReplayHistory {
    fn latest_seq(&self) -> u64 {
        self.events
            .back()
            .map(|v| v.event_seq)
            .unwrap_or_else(|| self.next_seq.saturating_sub(1))
    }

    fn push(&mut self, mut event: DebateReplayEvent) -> DebateReplayEvent {
        event.event_seq = self.next_seq;
        self.next_seq = self.next_seq.saturating_add(1);
        self.events.push_back(event.clone());
        while self.events.len() > DEBATE_REPLAY_HISTORY_CAPACITY {
            let _ = self.events.pop_front();
        }
        event
    }

    fn push_with_seq(&mut self, event: DebateReplayEvent) -> DebateReplayEvent {
        if let Some(last) = self.events.back() {
            if last.event_seq == event.event_seq {
                return last.clone();
            }
        }
        self.next_seq = self.next_seq.max(event.event_seq.saturating_add(1));
        self.events.push_back(event.clone());
        while self.events.len() > DEBATE_REPLAY_HISTORY_CAPACITY {
            let _ = self.events.pop_front();
        }
        event
    }
}

impl Default for DebateReplayHistory {
    fn default() -> Self {
        Self {
            next_seq: 1,
            events: VecDeque::new(),
        }
    }
}

impl UserEvent {
    pub fn debate_session_id(&self) -> Option<i64> {
        self.debate_replay
            .as_ref()
            .map(|v| v.session_id)
            .or_else(|| self.app_event.debate_session_id())
    }
}

fn now_unix_ms() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|v| v.as_millis() as i64)
        .unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn health_handler_should_return_ok() {
        assert_eq!(health_handler().await, "ok");
    }
}
