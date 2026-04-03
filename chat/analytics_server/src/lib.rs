mod config;
mod error;
mod events;
mod extractors;
mod handlers;
mod openapi;

pub use config::*;
use dashmap::DashMap;
pub use error::*;
pub use events::*;

use anyhow::Context;
use chat_core::{
    middlewares::{extract_user_header_only, set_layer, AuthContext, AuthVerifyError, TokenVerify},
    DecodingKey,
};
use clickhouse::Client;
use clickhouse::Row;
use handlers::{
    create_event_handler, get_auth_event_summary_handler, get_judge_refresh_summary_handler,
    get_judge_refresh_summary_metrics_handler, GetJudgeRefreshSummaryOutput,
    JudgeRefreshSummaryMetrics,
};
use openapi::OpenApiRouter as _;
use std::{fmt, ops::Deref, sync::Arc};
use tokio::fs;
use tower_http::cors::{self, CorsLayer};
use tracing::{info, warn};

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
    pub(crate) client: Client,
    pub(crate) sessions: Arc<DashMap<String, (String, i64)>>,
    pub(crate) judge_refresh_summary_cache:
        Arc<DashMap<String, (i64, GetJudgeRefreshSummaryOutput)>>,
    pub(crate) judge_refresh_summary_metrics: Arc<JudgeRefreshSummaryMetrics>,
}

const SESSION_PRELOAD_WINDOW_MINUTES: u32 = 10;

#[derive(Debug, Clone, Row, serde::Deserialize)]
struct SessionCacheRow {
    client_id: String,
    session_id: String,
    last_server_ts_ms: i64,
}

pub async fn get_router(state: AppState) -> Result<Router, AppError> {
    let cors = CorsLayer::new()
        .allow_methods([
            Method::GET,
            Method::POST,
            Method::PATCH,
            Method::DELETE,
            Method::PUT,
        ])
        .allow_origin(cors::Any)
        .allow_headers(cors::Any);
    let api = Router::new()
        .route("/event", post(create_event_handler))
        .route("/auth/summary", get(get_auth_event_summary_handler))
        .route(
            "/judge-refresh/summary",
            get(get_judge_refresh_summary_handler),
        )
        .route(
            "/judge-refresh/summary/metrics",
            get(get_judge_refresh_summary_metrics_handler),
        )
        .layer(from_fn_with_state(
            state.clone(),
            extract_user_header_only::<AppState>,
        ))
        // routes doesn't need token verification
        .layer(cors);

    let app = Router::new().openapi().nest("/api", api).with_state(state);

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
    async fn verify(&self, token: &str) -> Result<AuthContext, AuthVerifyError> {
        self.dk
            .verify_access(token)
            .map(|decoded| AuthContext {
                user: decoded.user,
                sid: decoded.sid,
                ver: decoded.ver,
            })
            .map_err(|err| err.to_auth_verify_error())
    }
}

impl AppState {
    pub async fn try_new(config: AppConfig) -> Result<Self, AppError> {
        fs::create_dir_all(&config.server.base_dir)
            .await
            .context("create base_dir failed")?;
        let dk = DecodingKey::load(&config.auth.pk).context("load pk failed")?;
        let jwt_runtime = dk.runtime_config();
        info!(
            component = "analytics_server",
            jwt_decoding_impl = jwt_runtime.implementation,
            jwt_legacy_fallback_enabled = jwt_runtime.legacy_fallback_enabled,
            "jwt runtime profile loaded"
        );
        let mut client = Client::default()
            .with_url(&config.server.db_url)
            .with_database(&config.server.db_name);
        if let Some(user) = config.server.db_user.as_ref() {
            client = client.with_user(user);
        }
        if let Some(password) = config.server.db_password.as_ref() {
            client = client.with_password(password);
        }
        let sessions = match load_recent_sessions_from_db(&client).await {
            Ok(rows) => {
                let restored = build_sessions_cache(rows);
                info!(
                    "restored {} analytics sessions from ClickHouse",
                    restored.len()
                );
                restored
            }
            Err(err) => {
                warn!(
                    "failed to restore sessions from ClickHouse, fallback to empty cache: {}",
                    err
                );
                Arc::new(DashMap::new())
            }
        };
        let judge_refresh_summary_cache = Arc::new(DashMap::new());
        let judge_refresh_summary_metrics = Arc::new(JudgeRefreshSummaryMetrics::default());
        Ok(Self {
            inner: Arc::new(AppStateInner {
                config,
                dk,
                client,
                sessions,
                judge_refresh_summary_cache,
                judge_refresh_summary_metrics,
            }),
        })
    }
}

async fn load_recent_sessions_from_db(client: &Client) -> Result<Vec<SessionCacheRow>, AppError> {
    let sql = format!(
        r#"
SELECT
    client_id,
    argMax(session_id, server_ts) AS session_id,
    toInt64(toUnixTimestamp64Milli(max(server_ts))) AS last_server_ts_ms
FROM analytics_events
WHERE server_ts >= now64(3) - toIntervalMinute({})
GROUP BY client_id
"#,
        SESSION_PRELOAD_WINDOW_MINUTES
    );
    let mut cursor = client.query(sql.as_str()).fetch::<SessionCacheRow>()?;
    let mut rows = Vec::new();
    while let Some(row) = cursor.next().await? {
        rows.push(row);
    }
    Ok(rows)
}

fn build_sessions_cache(rows: Vec<SessionCacheRow>) -> Arc<DashMap<String, (String, i64)>> {
    let sessions = Arc::new(DashMap::new());
    for row in rows {
        if row.client_id.is_empty() || row.session_id.is_empty() {
            continue;
        }
        sessions.insert(row.client_id, (row.session_id, row.last_server_ts_ms));
    }
    sessions
}

impl fmt::Debug for AppStateInner {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("AppStateInner")
            .field("config", &self.config)
            .finish()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn build_sessions_cache_should_skip_invalid_rows() {
        let sessions = build_sessions_cache(vec![
            SessionCacheRow {
                client_id: "client-a".to_string(),
                session_id: "sess-a".to_string(),
                last_server_ts_ms: 100,
            },
            SessionCacheRow {
                client_id: "".to_string(),
                session_id: "sess-b".to_string(),
                last_server_ts_ms: 200,
            },
            SessionCacheRow {
                client_id: "client-c".to_string(),
                session_id: "".to_string(),
                last_server_ts_ms: 300,
            },
        ]);

        assert_eq!(sessions.len(), 1);
        let entry = sessions
            .get("client-a")
            .expect("client-a should be restored");
        assert_eq!(entry.value(), &("sess-a".to_string(), 100));
    }
}
