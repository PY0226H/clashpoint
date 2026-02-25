mod agent;
mod config;
mod error;
mod event_bus;
mod handlers;
mod middlewares;
mod models;
mod openapi;

use anyhow::Context;
use chat_core::{
    middlewares::{set_layer, verify_token_header_only, TokenVerify},
    DecodingKey, EncodingKey, User,
};
use handlers::*;
use middlewares::{verify_ai_internal_key, verify_chat, verify_file_ticket};
use openapi::OpenApiRouter;
use sqlx::PgPool;
use std::{fmt, ops::Deref, sync::Arc, time::Duration};
use tokio::{fs, time::sleep};
use tower_http::cors::{self, CorsLayer};
use tracing::{debug, warn};

pub use error::{AppError, ErrorOutput};
pub(crate) use event_bus::{
    AiJudgeJobCreatedEvent, DebateMessagePinnedEvent, DebateParticipantJoinedEvent,
    DebateSessionStatusChangedEvent, EventBus,
};
pub use models::*;

use axum::{
    http::Method,
    middleware::from_fn_with_state,
    routing::{get, post},
    Router,
};

pub use config::AppConfig;

#[derive(Debug, Clone)]
pub struct AppState {
    inner: Arc<AppStateInner>,
}

#[allow(unused)]
pub struct AppStateInner {
    pub(crate) config: AppConfig,
    pub(crate) dk: DecodingKey,
    pub(crate) ek: EncodingKey,
    pub(crate) pool: PgPool,
    pub(crate) event_bus: EventBus,
}

pub async fn get_router(state: AppState) -> Result<Router, AppError> {
    let chat = Router::new()
        .route(
            "/:id",
            get(get_chat_handler)
                .patch(update_chat_handler)
                .delete(delete_chat_handler)
                .post(send_message_handler),
        )
        .route(
            "/:id/agents",
            get(list_agent_handler)
                .post(create_agent_handler)
                .patch(update_agent_handler),
        )
        .route("/:id/messages", get(list_message_handler))
        .layer(from_fn_with_state(state.clone(), verify_chat))
        .route("/", get(list_chat_handler).post(create_chat_handler));

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
    let debate = Router::new()
        .route("/topics", get(list_debate_topics_handler))
        .route("/sessions", get(list_debate_sessions_handler))
        .route("/sessions/:id/join", post(join_debate_session_handler))
        .route(
            "/sessions/:id/messages",
            post(create_debate_message_handler),
        )
        .route("/messages/:id/pin", post(pin_debate_message_handler))
        .route("/sessions/:id/judge/jobs", post(request_judge_job_handler))
        .route(
            "/sessions/:id/judge-report",
            get(get_latest_judge_report_handler),
        )
        .route("/sessions/:id/draw-vote", get(get_draw_vote_status_handler))
        .route(
            "/sessions/:id/draw-vote/ballots",
            post(submit_draw_vote_handler),
        );
    let pay = Router::new()
        .route("/iap/products", get(list_iap_products_handler))
        .route("/iap/verify", post(verify_iap_order_handler))
        .route("/wallet", get(get_wallet_balance_handler))
        .route("/wallet/ledger", get(list_wallet_ledger_handler));
    let internal_ai = Router::new()
        .route("/judge/jobs/:id/report", post(submit_judge_report_handler))
        .route(
            "/judge/jobs/:id/failed",
            post(mark_judge_job_failed_handler),
        )
        .layer(from_fn_with_state(state.clone(), verify_ai_internal_key));
    let protected_api = Router::new()
        .route("/users", get(list_chat_users_handler))
        .nest("/debate", debate)
        .nest("/pay", pay)
        .nest("/chats", chat)
        .route("/upload", post(upload_handler))
        .route("/tickets", post(create_access_tickets_handler))
        .layer(from_fn_with_state(
            state.clone(),
            verify_token_header_only::<AppState>,
        ));
    let file_api = Router::new()
        .route("/files/:ws_id/*path", get(file_handler))
        .layer(from_fn_with_state(state.clone(), verify_file_ticket));
    let api = Router::new()
        .merge(protected_api)
        .nest("/internal/ai", internal_ai)
        .merge(file_api)
        // routes doesn't need token verification
        .route("/signin", post(signin_handler))
        .route("/signup", post(signup_handler))
        .layer(cors);

    let app = Router::new()
        .openapi()
        .route("/", get(index_handler))
        .nest("/api", api)
        .with_state(state);

    Ok(set_layer(app))
}

// 当我调用 state.config => state.inner.config
impl Deref for AppState {
    type Target = AppStateInner;

    fn deref(&self) -> &Self::Target {
        &self.inner
    }
}

impl TokenVerify for AppState {
    type Error = AppError;

    fn verify(&self, token: &str) -> Result<User, Self::Error> {
        Ok(self.dk.verify(token)?)
    }
}

impl AppState {
    pub async fn try_new(config: AppConfig) -> Result<Self, AppError> {
        fs::create_dir_all(&config.server.base_dir)
            .await
            .context("create base_dir failed")?;
        let dk = DecodingKey::load(&config.auth.pk).context("load pk failed")?;
        let ek = EncodingKey::load(&config.auth.sk).context("load sk failed")?;
        let pool = PgPool::connect(&config.server.db_url)
            .await
            .context("connect to db failed")?;
        let event_bus = EventBus::from_config(&config.kafka).context("init event bus failed")?;
        event_bus
            .maybe_spawn_bootstrap_consumer()
            .context("start bootstrap kafka consumer failed")?;
        let state = Self {
            inner: Arc::new(AppStateInner {
                config,
                ek,
                dk,
                pool,
                event_bus,
            }),
        };
        spawn_debate_session_worker(state.clone());
        spawn_ai_judge_dispatch_worker(state.clone());
        Ok(state)
    }

    #[cfg(test)]
    pub fn new_for_unit_test(config: AppConfig) -> Result<Self, AppError> {
        use sqlx::postgres::PgPoolOptions;

        let dk = DecodingKey::load(&config.auth.pk).context("load pk failed")?;
        let ek = EncodingKey::load(&config.auth.sk).context("load sk failed")?;
        let pool = PgPoolOptions::new()
            .connect_lazy(&config.server.db_url)
            .context("create lazy db pool failed")?;
        let event_bus = EventBus::from_config(&config.kafka).context("init event bus failed")?;
        Ok(Self {
            inner: Arc::new(AppStateInner {
                config,
                ek,
                dk,
                pool,
                event_bus,
            }),
        })
    }
}

const DEBATE_SESSION_WORKER_INTERVAL_SECS: u64 = 2;
const DEBATE_SESSION_WORKER_BATCH_SIZE: i64 = 200;

fn spawn_debate_session_worker(state: AppState) {
    tokio::spawn(async move {
        loop {
            if let Err(err) = state
                .advance_debate_sessions(DEBATE_SESSION_WORKER_BATCH_SIZE)
                .await
            {
                warn!("debate session worker tick failed: {}", err);
            } else {
                debug!("debate session worker tick success");
            }
            sleep(Duration::from_secs(DEBATE_SESSION_WORKER_INTERVAL_SECS)).await;
        }
    });
}

fn spawn_ai_judge_dispatch_worker(state: AppState) {
    tokio::spawn(async move {
        loop {
            let interval = state.config.ai_judge.dispatch_interval_secs.max(1);
            if state.config.ai_judge.dispatch_enabled {
                match state.dispatch_pending_judge_jobs_once().await {
                    Ok(report) => {
                        debug!(
                            claimed = report.claimed,
                            dispatched = report.dispatched,
                            failed = report.failed,
                            marked_failed = report.marked_failed,
                            timed_out_failed = report.timed_out_failed,
                            terminal_failed = report.terminal_failed,
                            retryable_failed = report.retryable_failed,
                            failed_contract = report.failed_contract,
                            failed_http_4xx = report.failed_http_4xx,
                            failed_http_429 = report.failed_http_429,
                            failed_http_5xx = report.failed_http_5xx,
                            failed_network = report.failed_network,
                            failed_internal = report.failed_internal,
                            "ai judge dispatch worker tick success"
                        );
                    }
                    Err(err) => {
                        warn!("ai judge dispatch worker tick failed: {}", err);
                    }
                }
            }
            sleep(Duration::from_secs(interval)).await;
        }
    });
}

impl fmt::Debug for AppStateInner {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("AppStateInner")
            .field("config", &self.config)
            .finish()
    }
}

#[cfg(feature = "test-util")]
mod test_util {
    use super::*;
    use sqlx::{Connection, Executor, PgConnection, PgPool};
    use sqlx_db_tester::TestPg;

    impl AppState {
        pub async fn new_for_test() -> Result<(TestPg, Self), AppError> {
            let config = AppConfig::load()?;
            let dk = DecodingKey::load(&config.auth.pk).context("load pk failed")?;
            let ek = EncodingKey::load(&config.auth.sk).context("load sk failed")?;
            let maintenance_db_url = to_maintenance_db_url(&config.server.db_url);
            let (tdb, pool) = get_test_pool(Some(maintenance_db_url.as_str())).await;
            let state = Self {
                inner: Arc::new(AppStateInner {
                    config,
                    ek,
                    dk,
                    pool,
                    event_bus: EventBus::Disabled,
                }),
            };
            Ok((tdb, state))
        }
    }

    pub async fn get_test_pool(url: Option<&str>) -> (TestPg, PgPool) {
        let url = pick_reachable_maintenance_url(url).await;
        let tdb = TestPg::new(url, std::path::Path::new("../migrations"));
        let pool = tdb.get_pool().await;

        // run prepared sql to insert test dat
        let sql = include_str!("../fixtures/test.sql").split(';');
        let mut ts = pool.begin().await.expect("begin transaction failed");
        for s in sql {
            if s.trim().is_empty() {
                continue;
            }
            ts.execute(s).await.expect("execute sql failed");
        }
        ts.commit().await.expect("commit transaction failed");

        (tdb, pool)
    }

    async fn pick_reachable_maintenance_url(preferred: Option<&str>) -> String {
        let mut candidates = Vec::<String>::new();
        if let Some(url) = preferred {
            candidates.push(to_maintenance_db_url(url));
        }
        if let Ok(url) = std::env::var("DATABASE_URL") {
            candidates.push(to_maintenance_db_url(&url));
        }
        candidates.push("postgres://postgres:postgres@localhost:5432/postgres".to_string());
        if let Ok(user) = std::env::var("USER") {
            candidates.push(format!("postgres://{user}@localhost:5432/postgres"));
        }
        candidates.dedup();

        for candidate in candidates.iter() {
            if can_connect(candidate).await {
                return candidate.clone();
            }
        }

        panic!(
            "no reachable postgres maintenance url for tests, tried: {:?}",
            candidates
        );
    }

    async fn can_connect(url: &str) -> bool {
        match PgConnection::connect(url).await {
            Ok(conn) => {
                let _ = conn.close().await;
                true
            }
            Err(_) => false,
        }
    }

    fn to_maintenance_db_url(db_url: &str) -> String {
        // sqlx-db-tester parses URLs by plain '/' splitting and doesn't support query strings.
        // For tests we always connect to maintenance DB `postgres` to create/drop ephemeral DBs.
        let base = db_url.split('?').next().unwrap_or(db_url);
        let post = base.rfind('/').expect("invalid db_url");
        format!("{}/postgres", &base[..post])
    }
}
