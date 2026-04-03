mod config;
mod error;
mod middlewares;
mod notif;
mod sse;
mod ws;

use axum::{
    http::{header, HeaderValue, Method},
    middleware::from_fn_with_state,
    response::{Html, IntoResponse},
    routing::get,
    Router,
};
use chat_core::{
    middlewares::{AuthContext, AuthVerifyError, TokenVerify},
    DecodingKey,
};
use dashmap::DashMap;
use middlewares::verify_notify_ticket;
use serde_json::Value;
use sqlx::{postgres::PgPoolOptions, PgPool, Postgres, Row, Transaction};
use sse::sse_handler;
use std::{
    collections::VecDeque,
    ops::Deref,
    sync::{
        atomic::{AtomicU64, Ordering},
        Arc,
    },
    time::{SystemTime, UNIX_EPOCH},
};
use tokio::sync::broadcast;
use tower_http::cors::{self, CorsLayer};
use tracing::{info, warn};
use ws::{debate_room_ws_handler, ws_handler};

pub use config::AppConfig;
pub use error::AppError;
pub use notif::AppEvent;

const CHANNEL_CAPACITY: usize = 256;
const DEBATE_REPLAY_HISTORY_CAPACITY: usize = 400;
const DEBATE_REPLAY_MAX_ON_CONNECT: usize = 200;
const DEBATE_REPLAY_KEY_TTL_MS: i64 = 30 * 60 * 1000;
const DEBATE_REPLAY_MAX_KEYS_PER_USER: usize = 64;
const SSE_REPLAY_HISTORY_CAPACITY: usize = 512;
const SSE_REPLAY_MAX_ON_CONNECT: usize = 200;
const SSE_MAX_CONNECTIONS_PER_USER: u32 = 3;
const WS_MAX_CONNECTIONS_PER_USER: u32 = 3;
const DEBATE_WS_MAX_CONNECTIONS_PER_USER_PER_SESSION: u32 = 2;
const SYNC_REQUIRED_WARN_EVERY: u64 = 20;
const SSE_SYNC_REQUIRED_WARN_EVERY: u64 = 20;

pub type UserMap = Arc<DashMap<u64, broadcast::Sender<Arc<UserEvent>>>>;
type DebateReplayMap = Arc<DashMap<(u64, i64), DebateReplayHistory>>;
type SseReplayMap = Arc<DashMap<u64, SseReplayHistory>>;
type SseConnMap = Arc<DashMap<u64, u32>>;
type WsConnMap = Arc<DashMap<u64, u32>>;
type DebateWsConnMap = Arc<DashMap<(u64, i64), u32>>;
type DebateMembershipMap = Arc<DashMap<(u64, i64), i64>>;

#[derive(Debug, Clone)]
pub struct DebateReplayEvent {
    pub session_id: i64,
    pub event_seq: u64,
    pub event_name: String,
    pub payload: Value,
    pub event_at_ms: i64,
}

#[derive(Debug, Clone)]
pub struct DebateSyncRequiredSignal {
    pub session_id: i64,
    pub reason: String,
    pub skipped: u64,
    pub expected_from_seq: Option<u64>,
    pub gap_from_seq: Option<u64>,
    pub gap_to_seq: Option<u64>,
    pub latest_event_seq: Option<u64>,
    pub strategy: String,
}

#[derive(Debug, Clone)]
pub struct SseReplayEvent {
    pub event_id: u64,
    pub event_name: String,
    pub payload: Value,
    pub event_at_ms: i64,
    pub critical: bool,
}

#[derive(Debug, Clone)]
pub struct SseSyncRequiredSignal {
    pub reason: String,
    pub skipped: u64,
    pub suggested_last_event_id: u64,
    pub latest_event_id: u64,
    pub strategy: String,
}

#[derive(Debug, Clone)]
pub struct UserEvent {
    pub app_event: Arc<AppEvent>,
    pub sse_replay: Option<SseReplayEvent>,
    pub sse_sync_required: Option<SseSyncRequiredSignal>,
    pub debate_replay: Option<DebateReplayEvent>,
    pub debate_sync_required: Option<DebateSyncRequiredSignal>,
}

#[derive(Debug)]
struct DebateReplayHistory {
    next_seq: u64,
    events: VecDeque<DebateReplayEvent>,
    last_access_ms: i64,
}

#[derive(Debug)]
struct SseReplayHistory {
    next_id: u64,
    events: VecDeque<SseReplayEvent>,
}

#[derive(Debug, Clone, Default)]
pub struct DebateReplayWindow {
    pub events: Vec<DebateReplayEvent>,
    pub latest_seq: u64,
    pub has_gap: bool,
    pub skipped: u64,
    pub sync_required_reason: Option<String>,
    pub sync_required_strategy: Option<String>,
}

#[derive(Debug, Clone, Default)]
pub struct SseReplayWindow {
    pub events: Vec<SseReplayEvent>,
    pub latest_id: u64,
    pub has_gap: bool,
    pub skipped: u64,
}

#[derive(Debug, Clone, Copy, Default)]
pub struct NotifySyncRequiredMetricsSnapshot {
    pub persist_failed_total: u64,
    pub replay_storage_unavailable_total: u64,
    pub replay_window_miss_total: u64,
    pub lagged_receiver_total: u64,
    pub replay_truncated_total: u64,
    pub other_total: u64,
}

#[derive(Debug, Default)]
pub struct NotifySyncRequiredMetrics {
    persist_failed_total: AtomicU64,
    replay_storage_unavailable_total: AtomicU64,
    replay_window_miss_total: AtomicU64,
    lagged_receiver_total: AtomicU64,
    replay_truncated_total: AtomicU64,
    other_total: AtomicU64,
}

impl NotifySyncRequiredMetrics {
    fn observe_reason(&self, reason: &str) -> Option<u64> {
        match reason {
            "persist_failed" => Some(self.persist_failed_total.fetch_add(1, Ordering::Relaxed) + 1),
            "replay_storage_unavailable" => Some(
                self.replay_storage_unavailable_total
                    .fetch_add(1, Ordering::Relaxed)
                    + 1,
            ),
            "replay_window_miss" => Some(
                self.replay_window_miss_total
                    .fetch_add(1, Ordering::Relaxed)
                    + 1,
            ),
            "lagged_receiver" => {
                Some(self.lagged_receiver_total.fetch_add(1, Ordering::Relaxed) + 1)
            }
            "replay_truncated" => {
                Some(self.replay_truncated_total.fetch_add(1, Ordering::Relaxed) + 1)
            }
            _ => Some(self.other_total.fetch_add(1, Ordering::Relaxed) + 1),
        }
    }

    fn snapshot(&self) -> NotifySyncRequiredMetricsSnapshot {
        NotifySyncRequiredMetricsSnapshot {
            persist_failed_total: self.persist_failed_total.load(Ordering::Relaxed),
            replay_storage_unavailable_total: self
                .replay_storage_unavailable_total
                .load(Ordering::Relaxed),
            replay_window_miss_total: self.replay_window_miss_total.load(Ordering::Relaxed),
            lagged_receiver_total: self.lagged_receiver_total.load(Ordering::Relaxed),
            replay_truncated_total: self.replay_truncated_total.load(Ordering::Relaxed),
            other_total: self.other_total.load(Ordering::Relaxed),
        }
    }
}

#[derive(Debug, Clone, Copy, Default)]
pub struct NotifySseMetricsSnapshot {
    pub connected_total: u64,
    pub disconnected_total: u64,
    pub auth_unauthorized_total: u64,
    pub auth_forbidden_total: u64,
    pub replay_sent_total: u64,
    pub live_sent_total: u64,
    pub filtered_total: u64,
    pub lagged_total: u64,
    pub lagged_skipped_total: u64,
    pub sync_required_total: u64,
    pub too_many_connections_total: u64,
}

#[derive(Debug, Default)]
pub struct NotifySseMetrics {
    connected_total: AtomicU64,
    disconnected_total: AtomicU64,
    auth_unauthorized_total: AtomicU64,
    auth_forbidden_total: AtomicU64,
    replay_sent_total: AtomicU64,
    live_sent_total: AtomicU64,
    filtered_total: AtomicU64,
    lagged_total: AtomicU64,
    lagged_skipped_total: AtomicU64,
    sync_required_total: AtomicU64,
    too_many_connections_total: AtomicU64,
}

impl NotifySseMetrics {
    fn observe_connected(&self) {
        self.connected_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_disconnected(&self) {
        self.disconnected_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_auth_unauthorized(&self) {
        self.auth_unauthorized_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_auth_forbidden(&self) {
        self.auth_forbidden_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_replay_sent(&self) {
        self.replay_sent_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_live_sent(&self) {
        self.live_sent_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_filtered(&self) {
        self.filtered_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_lagged(&self, skipped: u64) {
        self.lagged_total.fetch_add(1, Ordering::Relaxed);
        self.lagged_skipped_total
            .fetch_add(skipped, Ordering::Relaxed);
    }

    fn observe_sync_required(&self) -> u64 {
        self.sync_required_total.fetch_add(1, Ordering::Relaxed) + 1
    }

    fn observe_too_many_connections(&self) {
        self.too_many_connections_total
            .fetch_add(1, Ordering::Relaxed);
    }

    fn snapshot(&self) -> NotifySseMetricsSnapshot {
        NotifySseMetricsSnapshot {
            connected_total: self.connected_total.load(Ordering::Relaxed),
            disconnected_total: self.disconnected_total.load(Ordering::Relaxed),
            auth_unauthorized_total: self.auth_unauthorized_total.load(Ordering::Relaxed),
            auth_forbidden_total: self.auth_forbidden_total.load(Ordering::Relaxed),
            replay_sent_total: self.replay_sent_total.load(Ordering::Relaxed),
            live_sent_total: self.live_sent_total.load(Ordering::Relaxed),
            filtered_total: self.filtered_total.load(Ordering::Relaxed),
            lagged_total: self.lagged_total.load(Ordering::Relaxed),
            lagged_skipped_total: self.lagged_skipped_total.load(Ordering::Relaxed),
            sync_required_total: self.sync_required_total.load(Ordering::Relaxed),
            too_many_connections_total: self.too_many_connections_total.load(Ordering::Relaxed),
        }
    }
}

#[derive(Debug, Clone, Copy, Default)]
pub struct NotifyAuthMetricsSnapshot {
    pub sse_unauthorized_total: u64,
    pub sse_forbidden_total: u64,
    pub ws_unauthorized_total: u64,
    pub ws_forbidden_total: u64,
    pub debate_ws_unauthorized_total: u64,
    pub debate_ws_forbidden_total: u64,
}

#[derive(Debug, Default)]
pub struct NotifyAuthMetrics {
    sse_unauthorized_total: AtomicU64,
    sse_forbidden_total: AtomicU64,
    ws_unauthorized_total: AtomicU64,
    ws_forbidden_total: AtomicU64,
    debate_ws_unauthorized_total: AtomicU64,
    debate_ws_forbidden_total: AtomicU64,
}

impl NotifyAuthMetrics {
    fn observe_unauthorized(&self, surface: NotifyAuthSurface) {
        match surface {
            NotifyAuthSurface::Sse => {
                self.sse_unauthorized_total.fetch_add(1, Ordering::Relaxed);
            }
            NotifyAuthSurface::GlobalWs => {
                self.ws_unauthorized_total.fetch_add(1, Ordering::Relaxed);
            }
            NotifyAuthSurface::DebateWs => {
                self.debate_ws_unauthorized_total
                    .fetch_add(1, Ordering::Relaxed);
            }
            NotifyAuthSurface::Unknown => {}
        }
    }

    fn observe_forbidden(&self, surface: NotifyAuthSurface) {
        match surface {
            NotifyAuthSurface::Sse => {
                self.sse_forbidden_total.fetch_add(1, Ordering::Relaxed);
            }
            NotifyAuthSurface::GlobalWs => {
                self.ws_forbidden_total.fetch_add(1, Ordering::Relaxed);
            }
            NotifyAuthSurface::DebateWs => {
                self.debate_ws_forbidden_total
                    .fetch_add(1, Ordering::Relaxed);
            }
            NotifyAuthSurface::Unknown => {}
        }
    }

    fn snapshot(&self) -> NotifyAuthMetricsSnapshot {
        NotifyAuthMetricsSnapshot {
            sse_unauthorized_total: self.sse_unauthorized_total.load(Ordering::Relaxed),
            sse_forbidden_total: self.sse_forbidden_total.load(Ordering::Relaxed),
            ws_unauthorized_total: self.ws_unauthorized_total.load(Ordering::Relaxed),
            ws_forbidden_total: self.ws_forbidden_total.load(Ordering::Relaxed),
            debate_ws_unauthorized_total: self.debate_ws_unauthorized_total.load(Ordering::Relaxed),
            debate_ws_forbidden_total: self.debate_ws_forbidden_total.load(Ordering::Relaxed),
        }
    }
}

#[derive(Debug, Clone, Copy, Default)]
pub struct NotifyWsMetricsSnapshot {
    pub connected_total: u64,
    pub disconnected_total: u64,
    pub replay_sent_total: u64,
    pub live_sent_total: u64,
    pub filtered_total: u64,
    pub lagged_total: u64,
    pub lagged_skipped_total: u64,
    pub sync_required_total: u64,
    pub too_many_connections_total: u64,
    pub send_failed_total: u64,
    pub idle_signal_total: u64,
    pub qos_drop_total: u64,
}

#[derive(Debug, Default)]
pub struct NotifyWsMetrics {
    connected_total: AtomicU64,
    disconnected_total: AtomicU64,
    replay_sent_total: AtomicU64,
    live_sent_total: AtomicU64,
    filtered_total: AtomicU64,
    lagged_total: AtomicU64,
    lagged_skipped_total: AtomicU64,
    sync_required_total: AtomicU64,
    too_many_connections_total: AtomicU64,
    send_failed_total: AtomicU64,
    idle_signal_total: AtomicU64,
    qos_drop_total: AtomicU64,
}

impl NotifyWsMetrics {
    fn observe_connected(&self) {
        self.connected_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_disconnected(&self) {
        self.disconnected_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_replay_sent(&self) {
        self.replay_sent_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_live_sent(&self) {
        self.live_sent_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_filtered(&self) {
        self.filtered_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_lagged(&self, skipped: u64) {
        self.lagged_total.fetch_add(1, Ordering::Relaxed);
        self.lagged_skipped_total
            .fetch_add(skipped, Ordering::Relaxed);
    }

    fn observe_sync_required(&self) -> u64 {
        self.sync_required_total.fetch_add(1, Ordering::Relaxed) + 1
    }

    fn observe_too_many_connections(&self) {
        self.too_many_connections_total
            .fetch_add(1, Ordering::Relaxed);
    }

    fn observe_send_failed(&self) {
        self.send_failed_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_idle_signal(&self) {
        self.idle_signal_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_qos_drop(&self) {
        self.qos_drop_total.fetch_add(1, Ordering::Relaxed);
    }

    fn snapshot(&self) -> NotifyWsMetricsSnapshot {
        NotifyWsMetricsSnapshot {
            connected_total: self.connected_total.load(Ordering::Relaxed),
            disconnected_total: self.disconnected_total.load(Ordering::Relaxed),
            replay_sent_total: self.replay_sent_total.load(Ordering::Relaxed),
            live_sent_total: self.live_sent_total.load(Ordering::Relaxed),
            filtered_total: self.filtered_total.load(Ordering::Relaxed),
            lagged_total: self.lagged_total.load(Ordering::Relaxed),
            lagged_skipped_total: self.lagged_skipped_total.load(Ordering::Relaxed),
            sync_required_total: self.sync_required_total.load(Ordering::Relaxed),
            too_many_connections_total: self.too_many_connections_total.load(Ordering::Relaxed),
            send_failed_total: self.send_failed_total.load(Ordering::Relaxed),
            idle_signal_total: self.idle_signal_total.load(Ordering::Relaxed),
            qos_drop_total: self.qos_drop_total.load(Ordering::Relaxed),
        }
    }
}

#[derive(Debug, Clone, Copy, Default)]
pub struct NotifyDebateWsMetricsSnapshot {
    pub connected_total: u64,
    pub disconnected_total: u64,
    pub replay_sent_total: u64,
    pub live_sent_total: u64,
    pub lagged_total: u64,
    pub lagged_skipped_total: u64,
    pub sync_required_total: u64,
    pub too_many_connections_total: u64,
    pub send_failed_total: u64,
    pub heartbeat_timeout_total: u64,
}

#[derive(Debug, Default)]
pub struct NotifyDebateWsMetrics {
    connected_total: AtomicU64,
    disconnected_total: AtomicU64,
    replay_sent_total: AtomicU64,
    live_sent_total: AtomicU64,
    lagged_total: AtomicU64,
    lagged_skipped_total: AtomicU64,
    sync_required_total: AtomicU64,
    too_many_connections_total: AtomicU64,
    send_failed_total: AtomicU64,
    heartbeat_timeout_total: AtomicU64,
}

impl NotifyDebateWsMetrics {
    fn observe_connected(&self) {
        self.connected_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_disconnected(&self) {
        self.disconnected_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_replay_sent(&self) {
        self.replay_sent_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_live_sent(&self) {
        self.live_sent_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_lagged(&self, skipped: u64) {
        self.lagged_total.fetch_add(1, Ordering::Relaxed);
        self.lagged_skipped_total
            .fetch_add(skipped, Ordering::Relaxed);
    }

    fn observe_sync_required(&self) {
        self.sync_required_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_too_many_connections(&self) {
        self.too_many_connections_total
            .fetch_add(1, Ordering::Relaxed);
    }

    fn observe_send_failed(&self) {
        self.send_failed_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_heartbeat_timeout(&self) {
        self.heartbeat_timeout_total.fetch_add(1, Ordering::Relaxed);
    }

    fn snapshot(&self) -> NotifyDebateWsMetricsSnapshot {
        NotifyDebateWsMetricsSnapshot {
            connected_total: self.connected_total.load(Ordering::Relaxed),
            disconnected_total: self.disconnected_total.load(Ordering::Relaxed),
            replay_sent_total: self.replay_sent_total.load(Ordering::Relaxed),
            live_sent_total: self.live_sent_total.load(Ordering::Relaxed),
            lagged_total: self.lagged_total.load(Ordering::Relaxed),
            lagged_skipped_total: self.lagged_skipped_total.load(Ordering::Relaxed),
            sync_required_total: self.sync_required_total.load(Ordering::Relaxed),
            too_many_connections_total: self.too_many_connections_total.load(Ordering::Relaxed),
            send_failed_total: self.send_failed_total.load(Ordering::Relaxed),
            heartbeat_timeout_total: self.heartbeat_timeout_total.load(Ordering::Relaxed),
        }
    }
}

#[derive(Debug, Clone, Copy)]
pub enum NotifyAuthSurface {
    Sse,
    GlobalWs,
    DebateWs,
    Unknown,
}

#[derive(Debug, Clone, Copy, Default)]
pub struct NotifyIngressMetricsSnapshot {
    pub pg_events_total: u64,
    pub kafka_events_total: u64,
}

#[derive(Debug, Default)]
pub struct NotifyIngressMetrics {
    pg_events_total: AtomicU64,
    kafka_events_total: AtomicU64,
}

impl NotifyIngressMetrics {
    fn observe_pg(&self) -> u64 {
        self.pg_events_total.fetch_add(1, Ordering::Relaxed) + 1
    }

    fn observe_kafka(&self) -> u64 {
        self.kafka_events_total.fetch_add(1, Ordering::Relaxed) + 1
    }

    fn snapshot(&self) -> NotifyIngressMetricsSnapshot {
        NotifyIngressMetricsSnapshot {
            pg_events_total: self.pg_events_total.load(Ordering::Relaxed),
            kafka_events_total: self.kafka_events_total.load(Ordering::Relaxed),
        }
    }
}

#[derive(Clone)]
pub struct AppState(Arc<AppStateInner>);

pub struct AppStateInner {
    pub config: AppConfig,
    users: UserMap,
    debate_replays: DebateReplayMap,
    sse_replays: SseReplayMap,
    sse_connections: SseConnMap,
    ws_connections: WsConnMap,
    debate_ws_connections: DebateWsConnMap,
    debate_memberships: DebateMembershipMap,
    sync_required_metrics: NotifySyncRequiredMetrics,
    auth_metrics: NotifyAuthMetrics,
    sse_metrics: NotifySseMetrics,
    ws_metrics: NotifyWsMetrics,
    debate_ws_metrics: NotifyDebateWsMetrics,
    ingress_metrics: NotifyIngressMetrics,
    db: PgPool,
    dk: DecodingKey,
}

const INDEX_HTML: &str = include_str!("../index.html");

pub async fn get_router(config: AppConfig) -> anyhow::Result<Router> {
    let state = AppState::new(config);
    let ingress_mode = if state.config.kafka.enabled {
        if !state.config.kafka.disable_pg_listener {
            anyhow::bail!(
                "invalid notify ingress config: kafka.enabled=true requires disable_pg_listener=true (single-primary ingress only)"
            );
        }
        "kafka-only"
    } else {
        "pg-only"
    };
    info!(ingress_mode, "notify ingress mode selected");
    if ingress_mode == "pg-only" {
        notif::setup_pg_listener(state.clone()).await?;
    }
    notif::setup_kafka_consumer(state.clone()).await?;

    let cors = CorsLayer::new()
        // allow `GET` and `POST` when accessing the resource
        .allow_methods([
            Method::GET,
            Method::POST,
            Method::PATCH,
            Method::DELETE,
            Method::PUT,
        ])
        .allow_origin(cors::AllowOrigin::predicate(
            |origin: &HeaderValue, _request| is_allowed_local_origin(origin),
        ))
        .allow_credentials(true)
        .allow_headers([
            header::ACCEPT,
            header::AUTHORIZATION,
            header::CACHE_CONTROL,
            header::CONTENT_TYPE,
            header::ORIGIN,
            header::PRAGMA,
            header::SEC_WEBSOCKET_PROTOCOL,
        ]);

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

fn is_allowed_local_origin(origin: &HeaderValue) -> bool {
    let raw = match origin.to_str() {
        Ok(value) => value.trim().to_ascii_lowercase(),
        Err(_) => return false,
    };
    raw == "tauri://localhost"
        || raw == "http://tauri.localhost"
        || raw == "https://tauri.localhost"
        || raw.starts_with("http://localhost:")
        || raw.starts_with("http://127.0.0.1:")
        || raw.starts_with("https://localhost:")
        || raw.starts_with("https://127.0.0.1:")
}

async fn index_handler() -> impl IntoResponse {
    Html(INDEX_HTML)
}

async fn health_handler() -> &'static str {
    "ok"
}

impl TokenVerify for AppState {
    async fn verify(&self, token: &str) -> Result<AuthContext, AuthVerifyError> {
        self.dk
            .verify_access(token)
            .map(|decoded| AuthContext {
                user: decoded.user,
                sid: decoded.sid,
            })
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
        let sse_replays = Arc::new(DashMap::new());
        let sse_connections = Arc::new(DashMap::new());
        let ws_connections = Arc::new(DashMap::new());
        let debate_ws_connections = Arc::new(DashMap::new());
        let debate_memberships = Arc::new(DashMap::new());
        let db = PgPoolOptions::new()
            .max_connections(5)
            .connect_lazy(&config.server.db_url)
            .expect("Failed to create notify-server db pool");
        Self(Arc::new(AppStateInner {
            config,
            dk,
            users,
            debate_replays,
            sse_replays,
            sse_connections,
            ws_connections,
            debate_ws_connections,
            debate_memberships,
            sync_required_metrics: NotifySyncRequiredMetrics::default(),
            auth_metrics: NotifyAuthMetrics::default(),
            sse_metrics: NotifySseMetrics::default(),
            ws_metrics: NotifyWsMetrics::default(),
            debate_ws_metrics: NotifyDebateWsMetrics::default(),
            ingress_metrics: NotifyIngressMetrics::default(),
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

    pub(crate) fn try_acquire_sse_connection(&self, user_id: u64) -> bool {
        let mut accepted = false;
        {
            let mut entry = self.sse_connections.entry(user_id).or_insert(0);
            if *entry < SSE_MAX_CONNECTIONS_PER_USER {
                *entry += 1;
                accepted = true;
            }
        }
        if accepted {
            self.sse_metrics.observe_connected();
        } else {
            self.sse_metrics.observe_too_many_connections();
        }
        accepted
    }

    pub(crate) fn release_sse_connection(&self, user_id: u64) {
        let mut should_remove = false;
        if let Some(mut entry) = self.sse_connections.get_mut(&user_id) {
            if *entry > 0 {
                *entry -= 1;
                self.sse_metrics.observe_disconnected();
            }
            if *entry == 0 {
                should_remove = true;
            }
        }
        if should_remove {
            self.sse_connections.remove(&user_id);
        }
    }

    pub(crate) fn try_acquire_ws_connection(&self, user_id: u64) -> bool {
        let mut accepted = false;
        {
            let mut entry = self.ws_connections.entry(user_id).or_insert(0);
            if *entry < WS_MAX_CONNECTIONS_PER_USER {
                *entry += 1;
                accepted = true;
            }
        }
        if accepted {
            self.ws_metrics.observe_connected();
        } else {
            self.ws_metrics.observe_too_many_connections();
        }
        accepted
    }

    pub(crate) fn release_ws_connection(&self, user_id: u64) {
        let mut should_remove = false;
        if let Some(mut entry) = self.ws_connections.get_mut(&user_id) {
            if *entry > 0 {
                *entry -= 1;
                self.ws_metrics.observe_disconnected();
            }
            if *entry == 0 {
                should_remove = true;
            }
        }
        if should_remove {
            self.ws_connections.remove(&user_id);
        }
    }

    pub(crate) fn try_acquire_debate_ws_connection(&self, user_id: u64, session_id: i64) -> bool {
        let key = (user_id, session_id);
        let mut accepted = false;
        {
            let mut entry = self.debate_ws_connections.entry(key).or_insert(0);
            if *entry < DEBATE_WS_MAX_CONNECTIONS_PER_USER_PER_SESSION {
                *entry += 1;
                accepted = true;
            }
        }
        if accepted {
            self.debate_ws_metrics.observe_connected();
        } else {
            self.debate_ws_metrics.observe_too_many_connections();
        }
        accepted
    }

    pub(crate) fn release_debate_ws_connection(&self, user_id: u64, session_id: i64) {
        let key = (user_id, session_id);
        let mut should_remove = false;
        if let Some(mut entry) = self.debate_ws_connections.get_mut(&key) {
            if *entry > 0 {
                *entry -= 1;
                self.debate_ws_metrics.observe_disconnected();
            }
            if *entry == 0 {
                should_remove = true;
            }
        }
        if should_remove {
            self.debate_ws_connections.remove(&key);
        }
    }

    pub(crate) fn mark_debate_membership(&self, user_id: u64, session_id: i64) {
        self.debate_memberships
            .insert((user_id, session_id), now_unix_ms());
    }

    pub(crate) async fn is_debate_session_participant(
        &self,
        user_id: u64,
        session_id: i64,
    ) -> anyhow::Result<bool> {
        if self.debate_memberships.contains_key(&(user_id, session_id)) {
            return Ok(true);
        }
        let exists = sqlx::query_scalar::<_, bool>(
            r#"
            SELECT EXISTS(
                SELECT 1
                FROM session_participants
                WHERE session_id = $1
                  AND user_id = $2
            )
            "#,
        )
        .bind(session_id)
        .bind(user_id as i64)
        .fetch_one(&self.db)
        .await?;
        if exists {
            self.mark_debate_membership(user_id, session_id);
        }
        Ok(exists)
    }

    pub(crate) fn build_user_event_for_recipient(
        &self,
        user_id: u64,
        app_event: Arc<AppEvent>,
        replay_event: Option<DebateReplayEvent>,
    ) -> UserEvent {
        if let Some(session_id) = app_event.debate_session_id() {
            self.mark_debate_membership(user_id, session_id);
        }
        let sse_replay = self.append_sse_replay_event(user_id, app_event.as_ref());
        let debate_replay = match replay_event {
            Some(v) => Some(self.append_persisted_replay_event(user_id, v)),
            None => self.append_debate_replay_event(user_id, app_event.as_ref()),
        };
        UserEvent {
            app_event,
            sse_replay,
            sse_sync_required: None,
            debate_replay,
            debate_sync_required: None,
        }
    }

    pub(crate) fn build_sync_required_user_event_for_recipient(
        &self,
        app_event: Arc<AppEvent>,
        reason: impl Into<String>,
    ) -> Option<UserEvent> {
        let session_id = app_event.debate_session_id()?;
        Some(UserEvent {
            app_event,
            sse_replay: None,
            sse_sync_required: None,
            debate_replay: None,
            debate_sync_required: Some(DebateSyncRequiredSignal {
                session_id,
                reason: reason.into(),
                skipped: 0,
                expected_from_seq: None,
                gap_from_seq: None,
                gap_to_seq: None,
                latest_event_seq: None,
                strategy: "snapshot_then_reconnect".to_string(),
            }),
        })
    }

    pub(crate) fn observe_sync_required_reason(&self, reason: &str) {
        let Some(next_total) = self.sync_required_metrics.observe_reason(reason) else {
            return;
        };
        if next_total % SYNC_REQUIRED_WARN_EVERY == 0 {
            warn!(
                reason,
                total = next_total,
                "syncRequired emission reached warning threshold"
            );
        }
    }

    pub(crate) fn sync_required_metrics_snapshot(&self) -> NotifySyncRequiredMetricsSnapshot {
        self.sync_required_metrics.snapshot()
    }

    pub(crate) fn observe_notify_ingress_source(&self, source: &str) {
        let total = match source {
            "pg" => self.ingress_metrics.observe_pg(),
            "kafka" => self.ingress_metrics.observe_kafka(),
            _ => return,
        };
        if total % 200 == 0 {
            let snapshot = self.ingress_metrics.snapshot();
            info!(
                source,
                pg_events_total = snapshot.pg_events_total,
                kafka_events_total = snapshot.kafka_events_total,
                "notify ingress events reached observation checkpoint"
            );
        }
    }

    pub(crate) fn observe_notify_auth_unauthorized(&self, surface: NotifyAuthSurface) {
        self.auth_metrics.observe_unauthorized(surface);
        if matches!(surface, NotifyAuthSurface::Sse) {
            self.sse_metrics.observe_auth_unauthorized();
        }
    }

    pub(crate) fn observe_notify_auth_forbidden(&self, surface: NotifyAuthSurface) {
        self.auth_metrics.observe_forbidden(surface);
        if matches!(surface, NotifyAuthSurface::Sse) {
            self.sse_metrics.observe_auth_forbidden();
        }
    }

    pub(crate) fn auth_metrics_snapshot(&self) -> NotifyAuthMetricsSnapshot {
        self.auth_metrics.snapshot()
    }

    pub(crate) fn observe_sse_event_filtered(&self) {
        self.sse_metrics.observe_filtered();
    }

    pub(crate) fn observe_sse_replay_sent(&self) {
        self.sse_metrics.observe_replay_sent();
    }

    pub(crate) fn observe_sse_live_sent(&self) {
        self.sse_metrics.observe_live_sent();
    }

    pub(crate) fn observe_sse_lagged(&self, skipped: u64) {
        self.sse_metrics.observe_lagged(skipped);
    }

    pub(crate) fn observe_sse_sync_required(&self) {
        let total = self.sse_metrics.observe_sync_required();
        if total.is_multiple_of(SSE_SYNC_REQUIRED_WARN_EVERY) {
            warn!(
                total,
                "sse sync-required emission reached warning threshold"
            );
        }
    }

    pub(crate) fn sse_metrics_snapshot(&self) -> NotifySseMetricsSnapshot {
        self.sse_metrics.snapshot()
    }

    pub(crate) fn observe_ws_replay_sent(&self) {
        self.ws_metrics.observe_replay_sent();
    }

    pub(crate) fn observe_ws_live_sent(&self) {
        self.ws_metrics.observe_live_sent();
    }

    pub(crate) fn observe_ws_event_filtered(&self) {
        self.ws_metrics.observe_filtered();
    }

    pub(crate) fn observe_ws_lagged(&self, skipped: u64) {
        self.ws_metrics.observe_lagged(skipped);
    }

    pub(crate) fn observe_ws_sync_required(&self) {
        let total = self.ws_metrics.observe_sync_required();
        if total.is_multiple_of(SSE_SYNC_REQUIRED_WARN_EVERY) {
            warn!(
                total,
                "global ws sync-required emission reached warning threshold"
            );
        }
    }

    pub(crate) fn observe_ws_send_failed(&self) {
        self.ws_metrics.observe_send_failed();
    }

    pub(crate) fn observe_ws_idle_signal(&self) {
        self.ws_metrics.observe_idle_signal();
    }

    pub(crate) fn observe_ws_qos_drop(&self) {
        self.ws_metrics.observe_qos_drop();
    }

    pub(crate) fn ws_metrics_snapshot(&self) -> NotifyWsMetricsSnapshot {
        self.ws_metrics.snapshot()
    }

    pub(crate) fn observe_debate_ws_replay_sent(&self) {
        self.debate_ws_metrics.observe_replay_sent();
    }

    pub(crate) fn observe_debate_ws_live_sent(&self) {
        self.debate_ws_metrics.observe_live_sent();
    }

    pub(crate) fn observe_debate_ws_lagged(&self, skipped: u64) {
        self.debate_ws_metrics.observe_lagged(skipped);
    }

    pub(crate) fn observe_debate_ws_sync_required(&self) {
        self.debate_ws_metrics.observe_sync_required();
    }

    pub(crate) fn observe_debate_ws_send_failed(&self) {
        self.debate_ws_metrics.observe_send_failed();
    }

    pub(crate) fn observe_debate_ws_heartbeat_timeout(&self) {
        self.debate_ws_metrics.observe_heartbeat_timeout();
    }

    pub(crate) fn debate_ws_metrics_snapshot(&self) -> NotifyDebateWsMetricsSnapshot {
        self.debate_ws_metrics.snapshot()
    }

    pub(crate) fn replay_sse_events_for_user(
        &self,
        user_id: u64,
        last_event_id: Option<u64>,
    ) -> SseReplayWindow {
        let from_id = last_event_id.unwrap_or(0);
        let Some(history) = self.sse_replays.get(&user_id) else {
            return SseReplayWindow {
                events: vec![],
                latest_id: 0,
                has_gap: false,
                skipped: 0,
            };
        };
        let latest_id = history.latest_id();
        if history.events.is_empty() || from_id >= latest_id {
            return SseReplayWindow {
                events: vec![],
                latest_id,
                has_gap: false,
                skipped: 0,
            };
        }
        let first_id = history
            .events
            .front()
            .map(|evt| evt.event_id)
            .unwrap_or(latest_id + 1);
        let has_gap = from_id.saturating_add(1) < first_id;
        let skipped = if has_gap {
            first_id.saturating_sub(from_id.saturating_add(1))
        } else {
            0
        };
        let events = history
            .events
            .iter()
            .filter(|evt| evt.event_id > from_id)
            .take(SSE_REPLAY_MAX_ON_CONNECT)
            .cloned()
            .collect::<Vec<_>>();
        SseReplayWindow {
            events,
            latest_id,
            has_gap,
            skipped,
        }
    }

    pub(crate) async fn replay_debate_events_for_user(
        &self,
        user_id: u64,
        session_id: i64,
        last_ack_seq: Option<u64>,
    ) -> DebateReplayWindow {
        let from_seq = last_ack_seq.unwrap_or(0);
        let window = match self
            .replay_debate_events_from_db(session_id, last_ack_seq)
            .await
        {
            // DB has persisted sequence for this session: use DB replay as source of truth.
            Ok(window) if window.latest_seq > 0 => window,
            // DB is empty for this session (or unavailable): fallback to in-memory replay window.
            Ok(_) => self.replay_debate_events_from_memory(user_id, session_id, last_ack_seq),
            Err(err) => {
                warn!(
                    "replay_debate_events_from_db failed: user_id={}, session_id={}, err={}",
                    user_id, session_id, err
                );
                let window =
                    self.replay_debate_events_from_memory(user_id, session_id, last_ack_seq);
                mark_sync_required_for_replay_storage_unavailable(window, last_ack_seq.unwrap_or(0))
            }
        };
        if window.sync_required_reason.is_some() {
            return window;
        }
        let replay_span = window.latest_seq.saturating_sub(from_seq);
        if replay_span > DEBATE_REPLAY_MAX_ON_CONNECT as u64 {
            return DebateReplayWindow {
                events: vec![],
                latest_seq: window.latest_seq,
                has_gap: false,
                skipped: replay_span,
                sync_required_reason: Some("replay_truncated".to_string()),
                sync_required_strategy: Some("snapshot_then_reconnect".to_string()),
            };
        }
        window
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
                sync_required_reason: None,
                sync_required_strategy: None,
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
            sync_required_reason: None,
            sync_required_strategy: None,
        })
    }

    fn replay_debate_events_from_memory(
        &self,
        user_id: u64,
        session_id: i64,
        last_ack_seq: Option<u64>,
    ) -> DebateReplayWindow {
        let from_seq = last_ack_seq.unwrap_or(0);
        let Some(mut history) = self.debate_replays.get_mut(&(user_id, session_id)) else {
            return DebateReplayWindow {
                events: vec![],
                latest_seq: 0,
                has_gap: false,
                skipped: 0,
                sync_required_reason: None,
                sync_required_strategy: None,
            };
        };
        history.touch();
        let latest_seq = history.latest_seq();
        if history.events.is_empty() || from_seq >= latest_seq {
            return DebateReplayWindow {
                events: vec![],
                latest_seq,
                has_gap: false,
                skipped: 0,
                sync_required_reason: None,
                sync_required_strategy: None,
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
            sync_required_reason: None,
            sync_required_strategy: None,
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
        let replay = entry.push(raw);
        drop(entry);
        self.prune_debate_replay_keys_for_user(user_id);
        Some(replay)
    }

    fn append_sse_replay_event(
        &self,
        user_id: u64,
        app_event: &AppEvent,
    ) -> Option<SseReplayEvent> {
        if app_event.is_debate_event() {
            return None;
        }
        let payload = serde_json::to_value(app_event).ok()?;
        let raw = SseReplayEvent {
            event_id: 0,
            event_name: app_event.event_name().to_string(),
            payload,
            event_at_ms: now_unix_ms(),
            critical: app_event.is_sse_critical_event(),
        };
        let mut entry = self.sse_replays.entry(user_id).or_default();
        Some(entry.push(raw))
    }

    fn append_persisted_replay_event(
        &self,
        user_id: u64,
        replay_event: DebateReplayEvent,
    ) -> DebateReplayEvent {
        self.mark_debate_membership(user_id, replay_event.session_id);
        let mut entry = self
            .debate_replays
            .entry((user_id, replay_event.session_id))
            .or_default();
        let replay = entry.push_with_seq(replay_event);
        drop(entry);
        self.prune_debate_replay_keys_for_user(user_id);
        replay
    }

    fn prune_debate_replay_keys_for_user(&self, user_id: u64) {
        let now_ms = now_unix_ms();
        let mut stale_keys = Vec::new();
        let mut live_keys = Vec::new();
        for entry in self.debate_replays.iter() {
            if entry.key().0 != user_id {
                continue;
            }
            let key = *entry.key();
            let last_access_ms = entry.value().last_access_ms;
            if now_ms.saturating_sub(last_access_ms) > DEBATE_REPLAY_KEY_TTL_MS {
                stale_keys.push(key);
            } else {
                live_keys.push((last_access_ms, key));
            }
        }
        for key in stale_keys {
            self.debate_replays.remove(&key);
        }
        if live_keys.len() <= DEBATE_REPLAY_MAX_KEYS_PER_USER {
            return;
        }
        live_keys.sort_by_key(|(last_access_ms, _)| *last_access_ms);
        let remove_count = live_keys.len() - DEBATE_REPLAY_MAX_KEYS_PER_USER;
        for (_, key) in live_keys.into_iter().take(remove_count) {
            self.debate_replays.remove(&key);
        }
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

    fn touch(&mut self) {
        self.last_access_ms = now_unix_ms();
    }

    fn push(&mut self, mut event: DebateReplayEvent) -> DebateReplayEvent {
        event.event_seq = self.next_seq;
        self.next_seq = self.next_seq.saturating_add(1);
        self.events.push_back(event.clone());
        self.touch();
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
        self.touch();
        while self.events.len() > DEBATE_REPLAY_HISTORY_CAPACITY {
            let _ = self.events.pop_front();
        }
        event
    }
}

impl SseReplayHistory {
    fn latest_id(&self) -> u64 {
        self.events
            .back()
            .map(|v| v.event_id)
            .unwrap_or_else(|| self.next_id.saturating_sub(1))
    }

    fn push(&mut self, mut event: SseReplayEvent) -> SseReplayEvent {
        event.event_id = self.next_id;
        self.next_id = self.next_id.saturating_add(1);
        while self.events.len() >= SSE_REPLAY_HISTORY_CAPACITY {
            if let Some(idx) = self.events.iter().position(|item| !item.critical) {
                let _ = self.events.remove(idx);
            } else {
                let _ = self.events.pop_front();
            }
        }
        self.events.push_back(event.clone());
        event
    }
}

impl Default for DebateReplayHistory {
    fn default() -> Self {
        Self {
            next_seq: 1,
            events: VecDeque::new(),
            last_access_ms: now_unix_ms(),
        }
    }
}

impl Default for SseReplayHistory {
    fn default() -> Self {
        Self {
            next_id: 1,
            events: VecDeque::new(),
        }
    }
}

impl UserEvent {
    pub fn sse_event_id(&self) -> Option<u64> {
        self.sse_replay.as_ref().map(|v| v.event_id)
    }

    pub fn debate_session_id(&self) -> Option<i64> {
        self.debate_replay
            .as_ref()
            .map(|v| v.session_id)
            .or_else(|| self.app_event.debate_session_id())
    }
}

pub(crate) fn now_unix_ms() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|v| v.as_millis() as i64)
        .unwrap_or(0)
}

fn mark_sync_required_for_replay_storage_unavailable(
    mut window: DebateReplayWindow,
    requested_last_ack_seq: u64,
) -> DebateReplayWindow {
    if requested_last_ack_seq > 0 && (window.latest_seq == 0 || window.has_gap) {
        window.sync_required_reason = Some("replay_storage_unavailable".to_string());
        window.sync_required_strategy = Some("snapshot_then_reconnect".to_string());
    }
    window
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::{AuthConfig, KafkaConfig, RedisConfig, ServerConfig};
    use chat_core::Message;
    use chrono::Utc;

    #[tokio::test]
    async fn health_handler_should_return_ok() {
        assert_eq!(health_handler().await, "ok");
    }

    #[test]
    fn mark_sync_required_for_replay_storage_unavailable_should_require_sync_for_resumed_client_without_replay_source(
    ) {
        let window = DebateReplayWindow::default();
        let marked = mark_sync_required_for_replay_storage_unavailable(window, 3);
        assert_eq!(
            marked.sync_required_reason.as_deref(),
            Some("replay_storage_unavailable")
        );
        assert_eq!(
            marked.sync_required_strategy.as_deref(),
            Some("snapshot_then_reconnect")
        );
    }

    #[test]
    fn mark_sync_required_for_replay_storage_unavailable_should_skip_fresh_client() {
        let window = DebateReplayWindow::default();
        let marked = mark_sync_required_for_replay_storage_unavailable(window, 0);
        assert_eq!(marked.sync_required_reason, None);
        assert_eq!(marked.sync_required_strategy, None);
    }

    #[test]
    fn mark_sync_required_for_replay_storage_unavailable_should_require_sync_for_resumed_client_with_memory_gap(
    ) {
        let window = DebateReplayWindow {
            events: vec![],
            latest_seq: 20,
            has_gap: true,
            skipped: 4,
            sync_required_reason: None,
            sync_required_strategy: None,
        };
        let marked = mark_sync_required_for_replay_storage_unavailable(window, 3);
        assert_eq!(
            marked.sync_required_reason.as_deref(),
            Some("replay_storage_unavailable")
        );
        assert_eq!(
            marked.sync_required_strategy.as_deref(),
            Some("snapshot_then_reconnect")
        );
    }

    #[test]
    fn mark_sync_required_for_replay_storage_unavailable_should_skip_resumed_client_with_contiguous_memory_window(
    ) {
        let window = DebateReplayWindow {
            events: vec![],
            latest_seq: 8,
            has_gap: false,
            skipped: 0,
            sync_required_reason: None,
            sync_required_strategy: None,
        };
        let marked = mark_sync_required_for_replay_storage_unavailable(window, 5);
        assert_eq!(marked.sync_required_reason, None);
        assert_eq!(marked.sync_required_strategy, None);
    }

    #[test]
    fn notify_sync_required_metrics_should_count_reasons_with_fallback() {
        let metrics = NotifySyncRequiredMetrics::default();
        assert_eq!(metrics.observe_reason("persist_failed"), Some(1));
        assert_eq!(metrics.observe_reason("persist_failed"), Some(2));
        assert_eq!(
            metrics.observe_reason("replay_storage_unavailable"),
            Some(1)
        );
        assert_eq!(metrics.observe_reason("lagged_receiver"), Some(1));
        assert_eq!(metrics.observe_reason("replay_window_miss"), Some(1));
        assert_eq!(metrics.observe_reason("replay_truncated"), Some(1));
        assert_eq!(metrics.observe_reason("unknown_reason"), Some(1));

        let snapshot = metrics.snapshot();
        assert_eq!(snapshot.persist_failed_total, 2);
        assert_eq!(snapshot.replay_storage_unavailable_total, 1);
        assert_eq!(snapshot.lagged_receiver_total, 1);
        assert_eq!(snapshot.replay_window_miss_total, 1);
        assert_eq!(snapshot.replay_truncated_total, 1);
        assert_eq!(snapshot.other_total, 1);
    }

    fn test_state() -> AppState {
        let config = AppConfig {
            server: ServerConfig {
                port: 0,
                db_url: "postgres://localhost:5432/chat".to_string(),
            },
            auth: AuthConfig {
                pk: include_str!("../../chat_core/fixtures/decoding.pem").to_string(),
            },
            kafka: KafkaConfig::default(),
            redis: RedisConfig::default(),
        };
        AppState::new(config)
    }

    #[tokio::test]
    async fn sse_connection_limit_should_reject_when_exceeding_cap() {
        let state = test_state();
        assert!(state.try_acquire_sse_connection(7));
        assert!(state.try_acquire_sse_connection(7));
        assert!(state.try_acquire_sse_connection(7));
        assert!(!state.try_acquire_sse_connection(7));
        state.release_sse_connection(7);
        assert!(state.try_acquire_sse_connection(7));
    }

    #[test]
    fn sse_replay_history_should_evict_non_critical_first() {
        let mut history = SseReplayHistory::default();
        history.push(SseReplayEvent {
            event_id: 0,
            event_name: "OpsObservabilityAlert".to_string(),
            payload: serde_json::json!({"event":"OpsObservabilityAlert"}),
            event_at_ms: 1,
            critical: true,
        });
        for idx in 0..SSE_REPLAY_HISTORY_CAPACITY {
            history.push(SseReplayEvent {
                event_id: 0,
                event_name: "NewMessage".to_string(),
                payload: serde_json::json!({"event":"NewMessage","idx":idx}),
                event_at_ms: idx as i64,
                critical: false,
            });
        }
        assert_eq!(history.events.len(), SSE_REPLAY_HISTORY_CAPACITY);
        assert!(history.events.iter().any(|item| item.critical));
    }

    #[tokio::test]
    async fn replay_sse_events_for_user_should_report_gap() {
        let state = test_state();
        state.sse_replays.insert(
            42,
            SseReplayHistory {
                next_id: 8,
                events: VecDeque::from(vec![
                    SseReplayEvent {
                        event_id: 5,
                        event_name: "NewMessage".to_string(),
                        payload: serde_json::json!({"event":"NewMessage","i":5}),
                        event_at_ms: 5,
                        critical: false,
                    },
                    SseReplayEvent {
                        event_id: 6,
                        event_name: "NewMessage".to_string(),
                        payload: serde_json::json!({"event":"NewMessage","i":6}),
                        event_at_ms: 6,
                        critical: false,
                    },
                    SseReplayEvent {
                        event_id: 7,
                        event_name: "NewMessage".to_string(),
                        payload: serde_json::json!({"event":"NewMessage","i":7}),
                        event_at_ms: 7,
                        critical: false,
                    },
                ]),
            },
        );
        let window = state.replay_sse_events_for_user(42, Some(1));
        assert!(window.has_gap);
        assert_eq!(window.skipped, 3);
        assert_eq!(window.latest_id, 7);
    }

    #[tokio::test]
    async fn get_router_should_reject_dual_ingress_mode() {
        let kafka = KafkaConfig {
            enabled: true,
            disable_pg_listener: false,
            ..KafkaConfig::default()
        };
        let config = AppConfig {
            server: ServerConfig {
                port: 0,
                db_url: "postgres://localhost:5432/chat".to_string(),
            },
            auth: AuthConfig {
                pk: include_str!("../../chat_core/fixtures/decoding.pem").to_string(),
            },
            kafka,
            redis: RedisConfig::default(),
        };
        let err = get_router(config)
            .await
            .expect_err("expected invalid config");
        let msg = err.to_string();
        assert!(
            msg.contains("single-primary ingress"),
            "unexpected error message: {msg}"
        );
    }

    #[tokio::test]
    async fn append_sse_replay_event_should_skip_debate_event() {
        let state = test_state();
        let event = AppEvent::DebateMessageCreated(crate::notif::DebateMessageCreated {
            message_id: 1,
            session_id: 2,
            user_id: 3,
            side: "pro".to_string(),
            content: "hello".to_string(),
            created_at: Utc::now(),
        });
        assert!(state.append_sse_replay_event(9, &event).is_none());
    }

    #[tokio::test]
    async fn append_sse_replay_event_should_assign_monotonic_event_id() {
        let state = test_state();
        let evt = AppEvent::NewMessage(Message {
            id: 1,
            chat_id: 2,
            sender_id: 3,
            content: "hi".to_string(),
            modified_content: None,
            files: vec![],
            created_at: Utc::now(),
        });
        let first = state
            .append_sse_replay_event(11, &evt)
            .expect("first replay event");
        let second = state
            .append_sse_replay_event(11, &evt)
            .expect("second replay event");
        assert_eq!(first.event_id, 1);
        assert_eq!(second.event_id, 2);
    }
}
