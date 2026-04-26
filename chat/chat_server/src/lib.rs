mod agent;
mod application;
mod config;
mod error;
mod event_bus;
mod handlers;
mod middlewares;
mod models;
mod openapi;
mod redis_store;
#[cfg(test)]
mod test_fixtures;

use anyhow::Context;
use chat_core::{
    middlewares::{set_layer, verify_token_header_only, AuthContext, AuthVerifyError, TokenVerify},
    DecodingKey, EncodingKey,
};
use handlers::*;
use middlewares::{require_phone_bound, verify_ai_internal_key, verify_chat, verify_file_ticket};
use openapi::OpenApiRouter;
use sqlx::PgPool;
use std::{env, fmt, ops::Deref, sync::Arc};
use tokio::{
    fs,
    sync::mpsc::{unbounded_channel, UnboundedSender},
};
use tower_http::cors::{self, CorsLayer};
use tracing::{info, warn};

use application::runtime_workers::spawn_background_workers;
pub use error::{AppError, ErrorOutput};
pub(crate) use event_bus::{
    DebateMessageCreatedEvent, DebateMessagePinnedEvent, DebateParticipantJoinedEvent,
    DebateSessionStatusChangedEvent, DomainEvent, EventBus, EventOutboxRelayConfig,
    EventOutboxRelayMetrics, EventOutboxRelayReport, EventPublisher, KafkaConsumerRuntimeMetrics,
};
use models::JudgeDispatchTrigger;
pub use models::*;
pub(crate) use redis_store::RateLimitDecision;
pub use redis_store::RedisHealthOutput;

use axum::{
    http::{header, HeaderValue, Method},
    middleware::from_fn_with_state,
    routing::{get, post, put},
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
    pub(crate) redis: redis_store::RedisStore,
    pub(crate) event_bus: EventBus,
    pub(crate) dispatch_metrics: AiJudgeDispatchMetrics,
    pub(crate) event_outbox_metrics: EventOutboxRelayMetrics,
    pub(crate) kafka_consumer_metrics: Arc<KafkaConsumerRuntimeMetrics>,
    pub(crate) auth_consistency_metrics: AuthConsistencyMetrics,
    pub(crate) dispatch_trigger_tx: Option<UnboundedSender<JudgeDispatchTrigger>>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum AppBootstrapMode {
    ApiServer,
    StandaloneWorker,
}

#[derive(Debug, Clone)]
struct DevSuperAccountConfig {
    email: String,
    phone: String,
    password: String,
    fullname: String,
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
        .route("/:id/leave", post(leave_chat_handler))
        .route("/:id/members/add", post(add_chat_members_handler))
        .route("/:id/members/remove", post(remove_chat_members_handler))
        .route(
            "/:id/agents",
            get(list_agent_handler)
                .post(create_agent_handler)
                .patch(update_agent_handler),
        )
        .route("/:id/messages", get(list_message_handler))
        .layer(from_fn_with_state(state.clone(), verify_chat))
        .route("/:id/join", post(join_chat_handler))
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
            header::HeaderName::from_static("x-requested-with"),
            header::PRAGMA,
        ]);
    let debate = Router::new()
        .route("/topics", get(list_debate_topics_handler))
        .route("/ops/topics", post(create_debate_topic_ops_handler))
        .route("/ops/topics/:id", put(update_debate_topic_ops_handler))
        .route("/ops/sessions", post(create_debate_session_ops_handler))
        .route("/ops/sessions/:id", put(update_debate_session_ops_handler))
        .route("/ops/rbac/me", get(get_ops_rbac_me_handler))
        .route("/ops/rbac/roles", get(list_ops_role_assignments_handler))
        .route(
            "/ops/observability/config",
            get(get_ops_observability_config_handler),
        )
        .route(
            "/ops/observability/metrics-dictionary",
            get(get_ops_observability_metrics_dictionary_handler),
        )
        .route(
            "/ops/observability/slo-snapshot",
            get(get_ops_observability_slo_snapshot_handler),
        )
        .route(
            "/ops/observability/split-readiness",
            get(get_ops_service_split_readiness_handler),
        )
        .route(
            "/ops/observability/split-readiness/reviews",
            get(list_ops_service_split_review_audits_handler),
        )
        .route(
            "/ops/observability/split-readiness/review",
            put(upsert_ops_service_split_review_handler),
        )
        .route(
            "/ops/observability/thresholds",
            put(upsert_ops_observability_thresholds_handler),
        )
        .route(
            "/ops/observability/anomaly-state",
            put(upsert_ops_observability_anomaly_state_handler),
        )
        .route(
            "/ops/observability/anomaly-state/actions",
            post(apply_ops_observability_anomaly_action_handler),
        )
        .route(
            "/ops/observability/evaluate-once",
            post(run_ops_observability_evaluation_once_handler),
        )
        .route(
            "/ops/observability/alerts",
            get(list_ops_alert_notifications_handler),
        )
        .route(
            "/ops/kafka/readiness",
            get(get_kafka_transport_readiness_handler),
        )
        .route("/ops/kafka/dlq", get(list_kafka_dlq_events_handler))
        .route(
            "/ops/kafka/dlq/:id/replay",
            post(replay_kafka_dlq_event_handler),
        )
        .route(
            "/ops/kafka/dlq/:id/discard",
            post(discard_kafka_dlq_event_handler),
        )
        .route(
            "/ops/rbac/roles/:user_id",
            put(upsert_ops_role_assignment_handler).delete(revoke_ops_role_assignment_handler),
        )
        .route("/ops/judge-reviews", get(list_judge_reviews_ops_handler))
        .route(
            "/ops/judge-final-dispatch/failure-stats",
            get(list_judge_final_dispatch_failure_stats_ops_handler),
        )
        .route(
            "/ops/judge-trace-replay",
            get(list_judge_trace_replay_ops_handler),
        )
        .route(
            "/ops/judge-replay/preview",
            get(get_judge_replay_preview_ops_handler),
        )
        .route(
            "/ops/judge-replay/execute",
            post(execute_judge_replay_ops_handler),
        )
        .route(
            "/ops/judge-replay/actions",
            get(list_judge_replay_actions_ops_handler),
        )
        .route(
            "/ops/sessions/:id/judge/rejudge",
            post(request_judge_rejudge_ops_handler),
        )
        .route("/sessions", get(list_debate_sessions_handler))
        .route("/sessions/:id/join", post(join_debate_session_handler))
        .route(
            "/sessions/:id/messages",
            get(list_debate_messages_handler).post(create_debate_message_handler),
        )
        .route(
            "/sessions/:id/pins",
            get(list_debate_pinned_messages_handler),
        )
        .route("/messages/:id/pin", post(pin_debate_message_handler))
        .route("/sessions/:id/judge/jobs", post(request_judge_job_handler))
        .route(
            "/sessions/:id/judge-report",
            get(get_latest_judge_report_handler),
        )
        .route(
            "/sessions/:id/judge-report/final",
            get(get_latest_judge_final_report_handler),
        )
        .route(
            "/sessions/:id/judge-report/public-verify",
            get(get_judge_public_verify_handler),
        )
        .route("/sessions/:id/draw-vote", get(get_draw_vote_status_handler))
        .route(
            "/sessions/:id/draw-vote/ballots",
            post(submit_draw_vote_handler),
        );
    let analytics = Router::new()
        .route(
            "/judge-refresh/summary",
            get(get_analytics_judge_refresh_summary_handler),
        )
        .route(
            "/judge-refresh/summary/metrics",
            get(get_analytics_judge_refresh_summary_metrics_handler),
        );
    let pay = Router::new()
        .route("/iap/products", get(list_iap_products_handler))
        .route(
            "/iap/orders/by-transaction",
            get(get_iap_order_by_transaction_handler),
        )
        .route("/iap/verify", post(verify_iap_order_handler))
        .route("/wallet", get(get_wallet_balance_handler))
        .route("/wallet/ledger", get(list_wallet_ledger_handler));
    let internal_ai = Router::new()
        .route(
            "/judge/v3/phase/cases/:id/report",
            post(submit_judge_phase_report_handler),
        )
        .route(
            "/judge/v3/phase/cases/:id/failed",
            post(submit_judge_phase_failed_handler),
        )
        .route(
            "/judge/v3/final/cases/:id/report",
            post(submit_judge_final_report_handler),
        )
        .route(
            "/judge/v3/final/cases/:id/failed",
            post(submit_judge_final_failed_handler),
        )
        .route("/infra/redis/health", get(get_redis_health_handler))
        .route("/infra/redis/ready", get(get_redis_ready_handler))
        .route(
            "/auth/consistency/metrics",
            get(get_auth_consistency_metrics_handler),
        )
        .route(
            "/judge/dispatch/metrics",
            get(get_judge_dispatch_metrics_handler),
        )
        .layer(from_fn_with_state(state.clone(), verify_ai_internal_key));
    let auth_session_api = Router::new()
        .route("/auth/logout", post(logout_handler))
        .route("/auth/logout-all", post(logout_all_handler))
        .route("/auth/sessions", get(list_auth_sessions_handler))
        .route("/auth/v2/password/set", post(set_password_v2_handler))
        .route("/auth/v2/phone/bind", post(bind_phone_v2_handler))
        .route(
            "/auth/sessions/:sid",
            axum::routing::delete(revoke_auth_session_handler),
        )
        .layer(from_fn_with_state(
            state.clone(),
            verify_token_header_only::<AppState>,
        ));

    let phone_required_api = Router::new()
        .route("/users", get(list_chat_users_handler))
        .nest("/analytics", analytics)
        .nest("/debate", debate)
        .nest("/pay", pay)
        .nest("/chats", chat)
        .route("/upload", post(upload_handler))
        .route("/tickets", post(create_access_tickets_handler))
        .layer(from_fn_with_state(state.clone(), require_phone_bound))
        .layer(from_fn_with_state(
            state.clone(),
            verify_token_header_only::<AppState>,
        ));
    let protected_api = Router::new()
        .merge(auth_session_api)
        .merge(phone_required_api);
    let file_api = Router::new()
        .route("/files/*path", get(file_handler))
        .layer(from_fn_with_state(state.clone(), verify_file_ticket));
    let api = Router::new()
        .merge(protected_api)
        .nest("/internal/ai", internal_ai)
        .merge(file_api)
        // routes doesn't need token verification
        .route("/signin", post(signin_handler))
        .route("/signup", post(signup_handler))
        .route("/auth/refresh", post(refresh_handler))
        .route("/auth/v2/sms/send", post(send_sms_code_v2_handler))
        .route(
            "/auth/v2/sms/delivery/callback",
            post(sms_delivery_callback_v2_handler),
        )
        .route("/auth/v2/signup/phone", post(signup_phone_v2_handler))
        .route("/auth/v2/signup/email", post(signup_email_v2_handler))
        .route("/auth/v2/signin/password", post(signin_password_v2_handler))
        .route("/auth/v2/signin/otp", post(signin_otp_v2_handler))
        .route(
            "/auth/v2/wechat/challenge",
            post(wechat_challenge_v2_handler),
        )
        .route("/auth/v2/wechat/signin", post(wechat_signin_v2_handler))
        .route(
            "/auth/v2/wechat/bind-phone",
            post(wechat_bind_phone_v2_handler),
        )
        .layer(cors);

    let app = Router::new()
        .openapi()
        .route("/", get(index_handler))
        .route("/health", get(health_handler))
        .nest("/api", api)
        .with_state(state);

    Ok(set_layer(app))
}

pub(crate) fn is_allowed_local_origin(origin: &HeaderValue) -> bool {
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

async fn health_handler() -> &'static str {
    "ok"
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
        let decoded = self
            .dk
            .verify_access(token)
            .map_err(|err| err.to_auth_verify_error())?;
        let current_ver = load_user_token_version(self, decoded.user.id)
            .await
            .map_err(map_auth_app_error)?;
        if decoded.ver != current_ver {
            return Err(AuthVerifyError::TokenVersionMismatch);
        }
        ensure_access_session_active(self, decoded.user.id, &decoded.sid)
            .await
            .map_err(map_auth_app_error)?;
        Ok(AuthContext {
            user: decoded.user,
            sid: decoded.sid,
            ver: decoded.ver,
        })
    }
}

fn map_auth_app_error(err: AppError) -> AuthVerifyError {
    match err {
        AppError::AuthError(code) => match code.as_str() {
            "auth_access_expired" => AuthVerifyError::AccessExpired,
            "auth_token_version_mismatch" => AuthVerifyError::TokenVersionMismatch,
            "auth_session_revoked" => AuthVerifyError::SessionRevoked,
            "auth_access_invalid"
            | "auth_refresh_invalid"
            | "auth_refresh_expired"
            | "auth_refresh_conflict_retry"
            | "auth_refresh_missing"
            | "auth_refresh_degraded_retryable"
            | "auth_refresh_replayed" => AuthVerifyError::AccessInvalid,
            _ => AuthVerifyError::Internal,
        },
        _ => AuthVerifyError::Internal,
    }
}

impl AppState {
    pub async fn try_new(config: AppConfig) -> Result<Self, AppError> {
        Self::try_new_with_bootstrap(config, AppBootstrapMode::ApiServer).await
    }

    pub async fn try_new_for_standalone_worker(config: AppConfig) -> Result<Self, AppError> {
        Self::try_new_with_bootstrap(config, AppBootstrapMode::StandaloneWorker).await
    }

    async fn try_new_with_bootstrap(
        config: AppConfig,
        mode: AppBootstrapMode,
    ) -> Result<Self, AppError> {
        fs::create_dir_all(&config.server.base_dir)
            .await
            .context("create base_dir failed")?;
        let dk = DecodingKey::load(&config.auth.pk).context("load pk failed")?;
        let ek = EncodingKey::load(&config.auth.sk).context("load sk failed")?;
        log_jwt_runtime_profile("chat_server", &dk, &ek);
        let pool = PgPool::connect(&config.server.db_url)
            .await
            .context("connect to db failed")?;
        let redis = redis_store::RedisStore::bootstrap(&config.redis)
            .await
            .context("init redis store failed")?;
        let event_bus = EventBus::from_config(&config.kafka).context("init event bus failed")?;
        let kafka_consumer_metrics = Arc::new(KafkaConsumerRuntimeMetrics::default());
        if mode == AppBootstrapMode::ApiServer {
            event_bus
                .maybe_spawn_consumer_worker(pool.clone(), kafka_consumer_metrics.clone())
                .context("start kafka consumer worker failed")?;
        }
        let (dispatch_trigger_tx, dispatch_trigger_rx) = if mode == AppBootstrapMode::ApiServer
            && config.worker_runtime.ai_judge_dispatch_worker_enabled
        {
            let (tx, rx) = unbounded_channel::<JudgeDispatchTrigger>();
            (Some(tx), Some(rx))
        } else {
            (None, None)
        };
        let state = Self {
            inner: Arc::new(AppStateInner {
                config,
                ek,
                dk,
                pool,
                redis,
                event_bus,
                dispatch_metrics: AiJudgeDispatchMetrics::default(),
                event_outbox_metrics: EventOutboxRelayMetrics::default(),
                kafka_consumer_metrics,
                auth_consistency_metrics: AuthConsistencyMetrics::default(),
                dispatch_trigger_tx,
            }),
        };
        if mode == AppBootstrapMode::ApiServer {
            ensure_dev_super_account(&state).await?;
            if let Err(err) = state.get_platform_admin_user_id().await {
                warn!(
                    "platform owner source check failed during bootstrap: {}",
                    err
                );
                return Err(err);
            }
        }
        if mode == AppBootstrapMode::ApiServer {
            spawn_background_workers(state.clone(), dispatch_trigger_rx);
        }
        Ok(state)
    }

    #[cfg(test)]
    pub fn new_for_unit_test(config: AppConfig) -> Result<Self, AppError> {
        use sqlx::postgres::PgPoolOptions;

        let dk = DecodingKey::load(&config.auth.pk).context("load pk failed")?;
        let ek = EncodingKey::load(&config.auth.sk).context("load sk failed")?;
        log_jwt_runtime_profile("chat_server_unit_test", &dk, &ek);
        let pool = PgPoolOptions::new()
            .connect_lazy(&config.server.db_url)
            .context("create lazy db pool failed")?;
        let redis = redis_store::RedisStore::Disabled {
            config: config.redis.clone(),
            message: "redis disabled in unit test constructor".to_string(),
        };
        let event_bus = EventBus::from_config(&config.kafka).context("init event bus failed")?;
        Ok(Self {
            inner: Arc::new(AppStateInner {
                config,
                ek,
                dk,
                pool,
                redis,
                event_bus,
                dispatch_metrics: AiJudgeDispatchMetrics::default(),
                event_outbox_metrics: EventOutboxRelayMetrics::default(),
                kafka_consumer_metrics: Arc::new(KafkaConsumerRuntimeMetrics::default()),
                auth_consistency_metrics: AuthConsistencyMetrics::default(),
                dispatch_trigger_tx: None,
            }),
        })
    }

    pub async fn get_redis_health(&self) -> RedisHealthOutput {
        self.redis.health_snapshot().await
    }

    pub(crate) fn trigger_judge_dispatch(&self, trigger: JudgeDispatchTrigger) {
        if let Some(tx) = &self.dispatch_trigger_tx {
            if let Err(err) = tx.send(trigger.clone()) {
                warn!(
                    job_id = trigger.job_id,
                    source = trigger.source,
                    "send judge dispatch trigger failed: {}",
                    err
                );
            }
        }
    }

    pub(crate) async fn relay_event_outbox_once(&self) -> Result<EventOutboxRelayReport, AppError> {
        let relay_config = EventOutboxRelayConfig::from_worker_runtime(&self.config.worker_runtime);
        let report = self
            .event_bus
            .relay_outbox_once(&self.pool, &relay_config)
            .await?;
        self.event_outbox_metrics.observe_tick_success(&report);
        Ok(report)
    }

    pub(crate) fn observe_event_outbox_worker_error(&self) {
        self.event_outbox_metrics.observe_tick_error();
    }
}

fn parse_env_bool(value: &str) -> Option<bool> {
    match value.trim().to_ascii_lowercase().as_str() {
        "1" | "true" | "yes" | "on" => Some(true),
        "0" | "false" | "no" | "off" => Some(false),
        _ => None,
    }
}

fn runtime_env() -> Option<String> {
    for key in ["ECHOISLE_ENV", "APP_ENV", "RUST_ENV", "ENV"] {
        if let Ok(value) = env::var(key) {
            let normalized = value.trim();
            if !normalized.is_empty() {
                return Some(normalized.to_ascii_lowercase());
            }
        }
    }
    None
}

fn is_production_env(value: &str) -> bool {
    matches!(value.trim(), "prod" | "production")
}

fn dev_super_account_enabled() -> bool {
    if let Ok(value) = env::var("ECHO_DEV_SUPER_ACCOUNT_ENABLED") {
        if let Some(enabled) = parse_env_bool(&value) {
            return enabled;
        }
    }
    !runtime_env()
        .as_deref()
        .map(is_production_env)
        .unwrap_or(false)
}

fn load_dev_super_account_config() -> Option<DevSuperAccountConfig> {
    if !dev_super_account_enabled() {
        return None;
    }

    let email = env::var("ECHO_DEV_SUPER_EMAIL").unwrap_or_else(|_| "super@none.org".to_string());
    let phone = env::var("ECHO_DEV_SUPER_PHONE").unwrap_or_else(|_| "+8613900000000".to_string());
    let password =
        env::var("ECHO_DEV_SUPER_PASSWORD").unwrap_or_else(|_| "EchoSuper@123456".to_string());
    let fullname =
        env::var("ECHO_DEV_SUPER_FULLNAME").unwrap_or_else(|_| "EchoIsle Super Admin".to_string());

    let email = email.trim().to_string();
    let phone = phone.trim().to_string();
    let password = password.trim().to_string();
    let fullname = fullname.trim().to_string();

    if email.is_empty() || phone.is_empty() || password.is_empty() || fullname.is_empty() {
        warn!(
            "skip dev super account bootstrap: one or more required fields are empty (email/phone/password/fullname)"
        );
        return None;
    }

    Some(DevSuperAccountConfig {
        email,
        phone,
        password,
        fullname,
    })
}

async fn ensure_dev_super_account(state: &AppState) -> Result<(), AppError> {
    let Some(cfg) = load_dev_super_account_config() else {
        return Ok(());
    };

    let mut user = if let Some(existing) = state.find_user_by_email(&cfg.email).await? {
        existing
    } else if let Some(existing) = state.find_user_by_phone(&cfg.phone).await? {
        existing
    } else {
        state
            .create_user_with_phone(&CreateUserWithPhoneInput {
                fullname: cfg.fullname.clone(),
                email: Some(cfg.email.clone()),
                phone_e164: cfg.phone.clone(),
                password: cfg.password.clone(),
                phone_bind_required: false,
            })
            .await?
    };

    state.set_user_password(user.id, &cfg.password).await?;
    if user.phone_bind_required
        || user.phone_verified_at.is_none()
        || user.phone_e164.as_deref() != Some(cfg.phone.as_str())
    {
        match state.bind_phone_for_user(user.id, &cfg.phone).await {
            Ok(updated) => {
                user = updated;
            }
            Err(error) => {
                warn!(
                    user_id = user.id,
                    target_phone = %cfg.phone,
                    "bind phone for dev super account failed: {}",
                    error
                );
            }
        }
    }

    state.grant_platform_admin(user.id as u64).await?;
    info!(
        user_id = user.id,
        super_email = %cfg.email,
        super_phone = %cfg.phone,
        "dev super account bootstrap ready"
    );
    Ok(())
}

impl fmt::Debug for AppStateInner {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("AppStateInner")
            .field("config", &self.config)
            .finish()
    }
}

#[cfg(test)]
mod health_tests {
    use super::*;

    #[tokio::test]
    async fn health_handler_should_return_ok() {
        assert_eq!(health_handler().await, "ok");
    }

    #[tokio::test]
    async fn trigger_judge_dispatch_should_send_event_when_channel_exists() {
        let config = AppConfig::load().expect("load app config");
        let mut state = AppState::new_for_unit_test(config).expect("build unit test state");
        let (tx, mut rx) = unbounded_channel();
        Arc::get_mut(&mut state.inner)
            .expect("state should be unique")
            .dispatch_trigger_tx = Some(tx);

        state.trigger_judge_dispatch(JudgeDispatchTrigger {
            job_id: 42,
            source: "test",
        });

        let trigger = rx.recv().await.expect("should receive trigger");
        assert_eq!(trigger.job_id, 42);
        assert_eq!(trigger.source, "test");
    }
}

#[cfg(all(test, feature = "test-util"))]
mod phone_gate_router_tests {
    use super::*;
    use anyhow::Result;
    use axum::{
        body::Body,
        http::{Method, Request, StatusCode},
    };
    use http_body_util::BodyExt;
    use tower::ServiceExt;

    async fn issue_token_for_user(state: &AppState, user_id: i64, sid: &str) -> Result<String> {
        let family_id = format!("{sid}-family");
        let refresh_jti = format!("{sid}-refresh-jti");
        let access_jti = format!("{sid}-access-jti");

        sqlx::query(
            r#"
            INSERT INTO auth_refresh_sessions (
                user_id, sid, family_id, current_jti, expires_at, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, NOW() + interval '1 day', NOW(), NOW())
            ON CONFLICT (sid) DO UPDATE
            SET current_jti = EXCLUDED.current_jti,
                family_id = EXCLUDED.family_id,
                revoked_at = NULL,
                revoke_reason = NULL,
                expires_at = EXCLUDED.expires_at,
                updated_at = NOW()
            "#,
        )
        .bind(user_id)
        .bind(sid)
        .bind(&family_id)
        .bind(&refresh_jti)
        .execute(&state.pool)
        .await?;

        let token = state
            .ek
            .sign_access_token_with_jti(user_id, sid, 0, access_jti, 900)?;
        Ok(token)
    }

    #[tokio::test]
    async fn router_should_block_core_api_for_unbound_phone_but_allow_bind_endpoint() -> Result<()>
    {
        let (_tdb, state) = AppState::new_for_test().await?;
        let unbound = state
            .create_user(&CreateUser {
                fullname: "No Phone".to_string(),
                email: "router-gate@acme.org".to_string(),
                password: "123456".to_string(),
            })
            .await?;
        let token = issue_token_for_user(&state, unbound.id, "router-phone-gate").await?;

        let app = get_router(state).await?;
        let users_req = Request::builder()
            .method(Method::GET)
            .uri("/api/users")
            .header("Authorization", format!("Bearer {}", token))
            .body(Body::empty())?;
        let users_res = app.clone().oneshot(users_req).await?;
        assert_eq!(users_res.status(), StatusCode::FORBIDDEN);
        let users_body = users_res.into_body().collect().await?.to_bytes();
        let users_error: ErrorOutput = serde_json::from_slice(&users_body)?;
        assert_eq!(users_error.error, "auth_phone_bind_required");

        let bind_req = Request::builder()
            .method(Method::POST)
            .uri("/api/auth/v2/phone/bind")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .body(Body::from(
                serde_json::json!({
                    "phone": "invalid-phone",
                    "smsCode": "000000",
                })
                .to_string(),
            ))?;
        let bind_res = app.oneshot(bind_req).await?;
        assert_eq!(bind_res.status(), StatusCode::UNAUTHORIZED);
        let bind_body = bind_res.into_body().collect().await?.to_bytes();
        let bind_error: ErrorOutput = serde_json::from_slice(&bind_body)?;
        assert_eq!(bind_error.error, "auth_sms_code_invalid");
        Ok(())
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
            log_jwt_runtime_profile("chat_server_test_util", &dk, &ek);
            let redis_config = config.redis.clone();
            let maintenance_db_url = to_maintenance_db_url(&config.server.db_url);
            let (tdb, pool) = get_test_pool(Some(maintenance_db_url.as_str())).await;
            let state = Self {
                inner: Arc::new(AppStateInner {
                    config,
                    ek,
                    dk,
                    pool,
                    redis: redis_store::RedisStore::Disabled {
                        config: redis_config,
                        message: "redis disabled in test util".to_string(),
                    },
                    event_bus: EventBus::Disabled,
                    dispatch_metrics: AiJudgeDispatchMetrics::default(),
                    event_outbox_metrics: EventOutboxRelayMetrics::default(),
                    kafka_consumer_metrics: Arc::new(KafkaConsumerRuntimeMetrics::default()),
                    auth_consistency_metrics: AuthConsistencyMetrics::default(),
                    dispatch_trigger_tx: None,
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
        const CONNECT_RETRY_TIMES: usize = 5;
        const CONNECT_RETRY_BACKOFF_MS: u64 = 120;
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

        for attempt in 0..CONNECT_RETRY_TIMES {
            for candidate in candidates.iter() {
                if can_connect(candidate).await {
                    return candidate.clone();
                }
            }
            // 并发测试下可能出现短暂连接抖动，做有限重试避免把环境瞬态误判成不可达。
            if attempt + 1 < CONNECT_RETRY_TIMES {
                tokio::time::sleep(std::time::Duration::from_millis(CONNECT_RETRY_BACKOFF_MS))
                    .await;
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

fn log_jwt_runtime_profile(component: &str, dk: &DecodingKey, ek: &EncodingKey) {
    let decoding = dk.runtime_config();
    let encoding = ek.runtime_config();
    info!(
        component,
        jwt_decoding_impl = decoding.implementation,
        jwt_encoding_impl = encoding.implementation,
        jwt_legacy_fallback_enabled = decoding.legacy_fallback_enabled,
        "jwt runtime profile loaded"
    );
    if decoding.implementation != encoding.implementation {
        warn!(
            component,
            jwt_decoding_impl = decoding.implementation,
            jwt_encoding_impl = encoding.implementation,
            "jwt runtime profile mismatch between decoding and encoding implementation"
        );
    }
}
