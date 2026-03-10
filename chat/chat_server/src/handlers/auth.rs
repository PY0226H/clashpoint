use crate::{
    application::request_guard::{
        build_rate_limit_headers, enforce_rate_limit, rate_limit_exceeded_response,
    },
    models::{CreateUser, SigninUser},
    AppError, AppState, ErrorOutput,
};
use axum::{
    extract::{Path, State},
    http::{header, HeaderMap, HeaderValue, StatusCode},
    response::IntoResponse,
    Extension, Json,
};
use chat_core::User;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sha1::{Digest, Sha1};
use sqlx::FromRow;
use utoipa::ToSchema;
use uuid::Uuid;

const SIGNIN_RATE_LIMIT_PER_WINDOW: u64 = 20;
const SIGNIN_RATE_LIMIT_WINDOW_SECS: u64 = 60;
const ACCESS_TOKEN_TTL_SECS: u64 = 60 * 15;
const REFRESH_TOKEN_TTL_SECS: u64 = 60 * 60 * 24 * 30;
const REFRESH_COOKIE_NAME: &str = "refresh_token";

#[derive(Debug, Serialize, ToSchema, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AuthOutput {
    access_token: String,
    token_type: String,
    expires_in_secs: u64,
    user: User,
}

#[derive(Debug, Serialize, ToSchema, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RefreshOutput {
    access_token: String,
    token_type: String,
    expires_in_secs: u64,
}

#[derive(Debug, Serialize, ToSchema, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct LogoutOutput {
    revoked: bool,
}

#[derive(Debug, Clone, Serialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct AuthSessionItem {
    pub sid: String,
    pub family_id: String,
    pub expires_at: DateTime<Utc>,
    pub revoked_at: Option<DateTime<Utc>>,
    pub revoke_reason: Option<String>,
    pub user_agent: Option<String>,
    pub ip_hash: Option<String>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct ListAuthSessionsOutput {
    pub items: Vec<AuthSessionItem>,
}

#[derive(Debug, Clone, Serialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct LogoutAllOutput {
    pub revoked_count: u64,
}

#[derive(Debug, Clone, FromRow)]
struct AuthRefreshSessionRow {
    sid: String,
    family_id: String,
    user_id: i64,
    ws_id: i64,
    current_jti: String,
    expires_at: DateTime<Utc>,
    revoked_at: Option<DateTime<Utc>>,
    revoke_reason: Option<String>,
    user_agent: Option<String>,
    ip_hash: Option<String>,
    created_at: DateTime<Utc>,
    updated_at: DateTime<Utc>,
}

#[derive(Debug)]
struct SessionContext {
    user_agent: Option<String>,
    ip_hash: Option<String>,
}

#[derive(Debug)]
struct IssuedTokens {
    access_token: String,
    refresh_token: String,
    sid: String,
    family_id: String,
    refresh_jti: String,
}

#[utoipa::path(
    post,
    path = "/api/signup",
    responses(
        (status = 201, description = "User created", body = AuthOutput),
        (status = 401, description = "Auth error", body = ErrorOutput),
    )
)]
pub(crate) async fn signup_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(input): Json<CreateUser>,
) -> Result<impl IntoResponse, AppError> {
    let user = state.create_user(&input).await?;
    let ctx = session_context_from_headers(&headers);
    let token_version = load_user_token_version(&state, user.id).await?;
    let issued = issue_auth_tokens(&state, &user, token_version)?;
    persist_refresh_session(&state, &user, &issued, &ctx).await?;
    sync_session_state_to_redis(&state, &issued, user.id, token_version).await?;

    let mut resp_headers = HeaderMap::new();
    set_refresh_cookie_header(
        &mut resp_headers,
        &issued.refresh_token,
        REFRESH_TOKEN_TTL_SECS,
    )?;
    let body = Json(AuthOutput {
        access_token: issued.access_token.clone(),
        token_type: "Bearer".to_string(),
        expires_in_secs: ACCESS_TOKEN_TTL_SECS,
        user,
    });
    Ok((StatusCode::CREATED, resp_headers, body))
}

#[utoipa::path(
    post,
    path = "/api/signin",
    responses(
        (status = 200, description = "User signed in", body = AuthOutput),
        (status = 401, description = "Auth error", body = ErrorOutput),
        (status = 429, description = "Rate limited", body = ErrorOutput),
    )
)]
pub(crate) async fn signin_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(input): Json<SigninUser>,
) -> Result<impl IntoResponse, AppError> {
    let email_key = input.email.trim().to_ascii_lowercase();
    let decision = enforce_rate_limit(
        &state,
        "signin",
        &email_key,
        SIGNIN_RATE_LIMIT_PER_WINDOW,
        SIGNIN_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    let mut resp_headers = build_rate_limit_headers(&decision)?;
    if !decision.allowed {
        return Ok(rate_limit_exceeded_response("signin", resp_headers));
    }

    let user = match state.verify_user(&input).await? {
        Some(v) => v,
        None => {
            let body = Json(ErrorOutput::new("auth_access_invalid"));
            return Ok((StatusCode::UNAUTHORIZED, resp_headers, body).into_response());
        }
    };

    let ctx = session_context_from_headers(&headers);
    let token_version = load_user_token_version(&state, user.id).await?;
    let issued = issue_auth_tokens(&state, &user, token_version)?;
    persist_refresh_session(&state, &user, &issued, &ctx).await?;
    sync_session_state_to_redis(&state, &issued, user.id, token_version).await?;

    set_refresh_cookie_header(
        &mut resp_headers,
        &issued.refresh_token,
        REFRESH_TOKEN_TTL_SECS,
    )?;
    Ok((
        StatusCode::OK,
        resp_headers,
        Json(AuthOutput {
            access_token: issued.access_token.clone(),
            token_type: "Bearer".to_string(),
            expires_in_secs: ACCESS_TOKEN_TTL_SECS,
            user,
        }),
    )
        .into_response())
}

#[utoipa::path(
    post,
    path = "/api/auth/refresh",
    responses(
        (status = 200, description = "Refresh access token", body = RefreshOutput),
        (status = 401, description = "Auth error", body = ErrorOutput),
    )
)]
pub(crate) async fn refresh_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, AppError> {
    let refresh_token = extract_refresh_token(&headers)
        .ok_or_else(|| AppError::AuthError("auth_refresh_missing".to_string()))?;

    let decoded = state
        .dk
        .verify_refresh(&refresh_token)
        .map_err(|err| AppError::AuthError(err.to_auth_verify_error().code().to_string()))?;

    if is_refresh_blacklisted(&state, &decoded.jti).await? {
        revoke_family_by_id(&state, &decoded.family_id, "replay_detected").await?;
        return Err(AppError::AuthError("auth_refresh_replayed".to_string()));
    }

    let now = Utc::now();
    let mut tx = state.pool.begin().await?;
    let row: Option<AuthRefreshSessionRow> = sqlx::query_as(
        r#"
        SELECT
            sid, family_id, user_id, ws_id, current_jti, expires_at, revoked_at,
            revoke_reason, user_agent, ip_hash, created_at, updated_at
        FROM auth_refresh_sessions
        WHERE sid = $1 AND user_id = $2
        FOR UPDATE
        "#,
    )
    .bind(&decoded.sid)
    .bind(decoded.user_id)
    .fetch_optional(&mut *tx)
    .await?;

    let Some(session) = row else {
        tx.rollback().await.ok();
        return Err(AppError::AuthError("auth_refresh_invalid".to_string()));
    };

    if session.revoked_at.is_some() {
        tx.rollback().await.ok();
        return Err(AppError::AuthError("auth_session_revoked".to_string()));
    }

    if session.expires_at <= now {
        sqlx::query(
            r#"
            UPDATE auth_refresh_sessions
            SET revoked_at = NOW(), revoke_reason = 'expired', updated_at = NOW()
            WHERE sid = $1
            "#,
        )
        .bind(&session.sid)
        .execute(&mut *tx)
        .await?;
        tx.commit().await?;
        blacklist_refresh_jti(&state, &decoded.jti, ttl_from_exp(decoded.exp)).await?;
        return Err(AppError::AuthError("auth_refresh_invalid".to_string()));
    }

    if session.current_jti != decoded.jti {
        sqlx::query(
            r#"
            UPDATE auth_refresh_sessions
            SET revoked_at = NOW(), revoke_reason = 'replay_detected', updated_at = NOW()
            WHERE family_id = $1 AND revoked_at IS NULL
            "#,
        )
        .bind(&session.family_id)
        .execute(&mut *tx)
        .await?;
        tx.commit().await?;
        blacklist_refresh_jti(&state, &decoded.jti, ttl_from_exp(decoded.exp)).await?;
        mark_family_revoked_in_redis(&state, &session.family_id).await?;
        return Err(AppError::AuthError("auth_refresh_replayed".to_string()));
    }

    let token_version = load_user_token_version(&state, session.user_id).await?;
    let new_refresh_jti = Uuid::now_v7().to_string();
    let new_access_jti = Uuid::now_v7().to_string();
    let access_token = state.ek.sign_access_token_with_jti(
        session.user_id,
        session.ws_id,
        &session.sid,
        token_version,
        &new_access_jti,
        ACCESS_TOKEN_TTL_SECS,
    )?;
    let refresh_token_new = state.ek.sign_refresh_token_with_jti(
        session.user_id,
        &session.sid,
        &session.family_id,
        &new_refresh_jti,
        REFRESH_TOKEN_TTL_SECS,
    )?;

    sqlx::query(
        r#"
        UPDATE auth_refresh_sessions
        SET current_jti = $2,
            rotated_from_jti = $3,
            expires_at = NOW() + ($4 || ' seconds')::interval,
            updated_at = NOW()
        WHERE sid = $1
        "#,
    )
    .bind(&session.sid)
    .bind(&new_refresh_jti)
    .bind(&decoded.jti)
    .bind(REFRESH_TOKEN_TTL_SECS as i64)
    .execute(&mut *tx)
    .await?;
    tx.commit().await?;

    blacklist_refresh_jti(&state, &decoded.jti, ttl_from_exp(decoded.exp)).await?;
    set_refresh_session_in_redis(&state, &session.sid, &new_refresh_jti).await?;

    let mut resp_headers = HeaderMap::new();
    set_refresh_cookie_header(
        &mut resp_headers,
        &refresh_token_new,
        REFRESH_TOKEN_TTL_SECS,
    )?;
    Ok((
        StatusCode::OK,
        resp_headers,
        Json(RefreshOutput {
            access_token,
            token_type: "Bearer".to_string(),
            expires_in_secs: ACCESS_TOKEN_TTL_SECS,
        }),
    ))
}

#[utoipa::path(
    post,
    path = "/api/auth/logout",
    responses(
        (status = 200, description = "Logout current session", body = LogoutOutput),
        (status = 401, description = "Auth error", body = ErrorOutput),
    ),
    security(("token" = []))
)]
pub(crate) async fn logout_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, AppError> {
    let mut revoked = false;
    if let Some(refresh_token) = extract_refresh_token(&headers) {
        if let Ok(decoded) = state.dk.verify_refresh(&refresh_token) {
            if decoded.user_id == user.id {
                let affected =
                    revoke_family_by_sid(&state, &decoded.sid, user.id, "logout").await?;
                revoked = affected > 0;
                blacklist_refresh_jti(&state, &decoded.jti, ttl_from_exp(decoded.exp)).await?;
            }
        }
    }

    let mut resp_headers = HeaderMap::new();
    clear_refresh_cookie_header(&mut resp_headers)?;
    Ok((StatusCode::OK, resp_headers, Json(LogoutOutput { revoked })))
}

#[utoipa::path(
    post,
    path = "/api/auth/logout-all",
    responses(
        (status = 200, description = "Logout all sessions", body = LogoutAllOutput),
        (status = 401, description = "Auth error", body = ErrorOutput),
    ),
    security(("token" = []))
)]
pub(crate) async fn logout_all_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
) -> Result<impl IntoResponse, AppError> {
    let mut tx = state.pool.begin().await?;
    let new_ver: i64 = sqlx::query_scalar(
        r#"
        UPDATE users
        SET token_version = token_version + 1
        WHERE id = $1
        RETURNING token_version
        "#,
    )
    .bind(user.id)
    .fetch_one(&mut *tx)
    .await?;

    let affected = sqlx::query(
        r#"
        UPDATE auth_refresh_sessions
        SET revoked_at = NOW(), revoke_reason = 'logout_all', updated_at = NOW()
        WHERE user_id = $1 AND revoked_at IS NULL
        "#,
    )
    .bind(user.id)
    .execute(&mut *tx)
    .await?
    .rows_affected() as u64;

    tx.commit().await?;
    cache_user_token_version(&state, user.id, new_ver).await?;

    let mut resp_headers = HeaderMap::new();
    clear_refresh_cookie_header(&mut resp_headers)?;
    Ok((
        StatusCode::OK,
        resp_headers,
        Json(LogoutAllOutput {
            revoked_count: affected,
        }),
    ))
}

#[utoipa::path(
    get,
    path = "/api/auth/sessions",
    responses(
        (status = 200, description = "List auth sessions", body = ListAuthSessionsOutput),
        (status = 401, description = "Auth error", body = ErrorOutput),
    ),
    security(("token" = []))
)]
pub(crate) async fn list_auth_sessions_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
) -> Result<impl IntoResponse, AppError> {
    let rows: Vec<AuthRefreshSessionRow> = sqlx::query_as(
        r#"
        SELECT
            sid, family_id, user_id, ws_id, current_jti, expires_at, revoked_at,
            revoke_reason, user_agent, ip_hash, created_at, updated_at
        FROM auth_refresh_sessions
        WHERE user_id = $1
        ORDER BY created_at DESC
        "#,
    )
    .bind(user.id)
    .fetch_all(&state.pool)
    .await?;

    let items = rows
        .into_iter()
        .map(|row| AuthSessionItem {
            sid: row.sid,
            family_id: row.family_id,
            expires_at: row.expires_at,
            revoked_at: row.revoked_at,
            revoke_reason: row.revoke_reason,
            user_agent: row.user_agent,
            ip_hash: row.ip_hash,
            created_at: row.created_at,
            updated_at: row.updated_at,
        })
        .collect();

    Ok((StatusCode::OK, Json(ListAuthSessionsOutput { items })))
}

#[utoipa::path(
    delete,
    path = "/api/auth/sessions/{sid}",
    params(("sid" = String, Path, description = "Session id")),
    responses(
        (status = 200, description = "Revoke session", body = LogoutOutput),
        (status = 401, description = "Auth error", body = ErrorOutput),
    ),
    security(("token" = []))
)]
pub(crate) async fn revoke_auth_session_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(sid): Path<String>,
) -> Result<impl IntoResponse, AppError> {
    let affected = revoke_family_by_sid(&state, &sid, user.id, "manual_revoke").await?;
    Ok((
        StatusCode::OK,
        Json(LogoutOutput {
            revoked: affected > 0,
        }),
    ))
}

fn issue_auth_tokens(
    state: &AppState,
    user: &User,
    token_version: i64,
) -> Result<IssuedTokens, AppError> {
    let sid = Uuid::now_v7().to_string();
    let family_id = Uuid::now_v7().to_string();
    let refresh_jti = Uuid::now_v7().to_string();
    let access_jti = Uuid::now_v7().to_string();
    let access_token = state.ek.sign_access_token_with_jti(
        user.id,
        user.ws_id,
        &sid,
        token_version,
        access_jti,
        ACCESS_TOKEN_TTL_SECS,
    )?;
    let refresh_token = state.ek.sign_refresh_token_with_jti(
        user.id,
        &sid,
        &family_id,
        &refresh_jti,
        REFRESH_TOKEN_TTL_SECS,
    )?;

    Ok(IssuedTokens {
        access_token,
        refresh_token,
        sid,
        family_id,
        refresh_jti,
    })
}

async fn persist_refresh_session(
    state: &AppState,
    user: &User,
    issued: &IssuedTokens,
    ctx: &SessionContext,
) -> Result<(), AppError> {
    sqlx::query(
        r#"
        INSERT INTO auth_refresh_sessions(
            ws_id, user_id, sid, family_id, current_jti, expires_at,
            user_agent, ip_hash, created_at, updated_at
        )
        VALUES (
            $1, $2, $3, $4, $5, NOW() + ($6 || ' seconds')::interval,
            $7, $8, NOW(), NOW()
        )
        "#,
    )
    .bind(user.ws_id)
    .bind(user.id)
    .bind(&issued.sid)
    .bind(&issued.family_id)
    .bind(&issued.refresh_jti)
    .bind(REFRESH_TOKEN_TTL_SECS as i64)
    .bind(ctx.user_agent.clone())
    .bind(ctx.ip_hash.clone())
    .execute(&state.pool)
    .await?;
    Ok(())
}

async fn sync_session_state_to_redis(
    state: &AppState,
    issued: &IssuedTokens,
    user_id: i64,
    token_version: i64,
) -> Result<(), AppError> {
    set_refresh_session_in_redis(state, &issued.sid, &issued.refresh_jti).await?;
    set_family_active_in_redis(state, &issued.family_id).await?;
    let add_ret = state
        .redis
        .add_set_member("auth:user:sessions", &user_id.to_string(), &issued.sid)
        .await;
    handle_auth_redis_unit_result(state, add_ret, "auth_refresh_invalid")?;

    let expire_ret = state
        .redis
        .set_key_expire(
            "auth:user:sessions",
            &user_id.to_string(),
            REFRESH_TOKEN_TTL_SECS,
        )
        .await;
    handle_auth_redis_unit_result(state, expire_ret, "auth_refresh_invalid")?;
    cache_user_token_version(state, user_id, token_version).await?;
    Ok(())
}

async fn set_refresh_session_in_redis(
    state: &AppState,
    sid: &str,
    refresh_jti: &str,
) -> Result<(), AppError> {
    let ret = state
        .redis
        .set_value_with_ttl("auth:rt:session", sid, refresh_jti, REFRESH_TOKEN_TTL_SECS)
        .await;
    handle_auth_redis_unit_result(state, ret, "auth_refresh_invalid")
}

async fn set_family_active_in_redis(state: &AppState, family_id: &str) -> Result<(), AppError> {
    let ret = state
        .redis
        .set_value_with_ttl(
            "auth:rt:family",
            family_id,
            "active",
            REFRESH_TOKEN_TTL_SECS,
        )
        .await;
    handle_auth_redis_unit_result(state, ret, "auth_refresh_invalid")
}

async fn mark_family_revoked_in_redis(state: &AppState, family_id: &str) -> Result<(), AppError> {
    let ret = state
        .redis
        .set_value_with_ttl(
            "auth:rt:family",
            family_id,
            "revoked",
            REFRESH_TOKEN_TTL_SECS,
        )
        .await;
    handle_auth_redis_unit_result(state, ret, "auth_refresh_invalid")
}

async fn is_refresh_blacklisted(state: &AppState, jti: &str) -> Result<bool, AppError> {
    match state.redis.get_value("auth:rt:blacklist", jti).await {
        Ok(ret) => Ok(ret.is_some()),
        Err(err) => {
            if auth_fail_closed_enabled(state) {
                Err(AppError::AuthError("auth_refresh_invalid".to_string()))
            } else {
                tracing::warn!("auth redis blacklist read degraded as fail-open: {}", err);
                Ok(false)
            }
        }
    }
}

async fn blacklist_refresh_jti(state: &AppState, jti: &str, ttl_secs: u64) -> Result<(), AppError> {
    if ttl_secs == 0 {
        return Ok(());
    }
    let ret = state
        .redis
        .set_value_with_ttl("auth:rt:blacklist", jti, "1", ttl_secs)
        .await;
    handle_auth_redis_unit_result(state, ret, "auth_refresh_invalid")
}

async fn cache_user_token_version(
    state: &AppState,
    user_id: i64,
    token_version: i64,
) -> Result<(), AppError> {
    let ret = state
        .redis
        .set_value_with_ttl(
            "auth:user:token_version",
            &user_id.to_string(),
            &token_version.to_string(),
            REFRESH_TOKEN_TTL_SECS,
        )
        .await;
    handle_auth_redis_unit_result(state, ret, "auth_refresh_invalid")
}

pub(crate) async fn load_user_token_version(
    state: &AppState,
    user_id: i64,
) -> Result<i64, AppError> {
    let cached = state
        .redis
        .get_value("auth:user:token_version", &user_id.to_string())
        .await;
    match cached {
        Ok(Some(value)) => {
            if let Ok(parsed) = value.parse::<i64>() {
                return Ok(parsed.max(0));
            }
        }
        Ok(None) => {}
        Err(err) => {
            if auth_fail_closed_enabled(state) {
                tracing::warn!(
                    "auth redis token_version read failed under fail-closed: {}",
                    err
                );
                return Err(AppError::AuthError("auth_access_invalid".to_string()));
            }
        }
    }

    let value: Option<i64> = sqlx::query_scalar("SELECT token_version FROM users WHERE id = $1")
        .bind(user_id)
        .fetch_optional(&state.pool)
        .await?;
    let token_version = value.unwrap_or(0).max(0);
    let _ = cache_user_token_version(state, user_id, token_version).await;
    Ok(token_version)
}

pub(crate) async fn ensure_access_session_active(
    state: &AppState,
    user_id: i64,
    sid: &str,
) -> Result<(), AppError> {
    let redis_ret = state.redis.get_value("auth:rt:session", sid).await;
    match redis_ret {
        Ok(Some(_)) => return Ok(()),
        Ok(None) => {}
        Err(err) => {
            if auth_fail_closed_enabled(state) {
                tracing::warn!("auth redis session read failed under fail-closed: {}", err);
                return Err(AppError::AuthError("auth_session_revoked".to_string()));
            }
            tracing::warn!("auth redis session read degraded as fail-open: {}", err);
        }
    }

    let row: Option<(Option<DateTime<Utc>>, DateTime<Utc>, String)> = sqlx::query_as(
        r#"
        SELECT revoked_at, expires_at, current_jti
        FROM auth_refresh_sessions
        WHERE sid = $1 AND user_id = $2
        "#,
    )
    .bind(sid)
    .bind(user_id)
    .fetch_optional(&state.pool)
    .await?;

    let Some((revoked_at, expires_at, current_jti)) = row else {
        return Err(AppError::AuthError("auth_session_revoked".to_string()));
    };
    if revoked_at.is_some() || expires_at <= Utc::now() {
        return Err(AppError::AuthError("auth_session_revoked".to_string()));
    }

    let _ = set_refresh_session_in_redis(state, sid, &current_jti).await;
    Ok(())
}

async fn revoke_family_by_id(
    state: &AppState,
    family_id: &str,
    reason: &str,
) -> Result<u64, AppError> {
    let affected = sqlx::query(
        r#"
        UPDATE auth_refresh_sessions
        SET revoked_at = NOW(), revoke_reason = $2, updated_at = NOW()
        WHERE family_id = $1 AND revoked_at IS NULL
        "#,
    )
    .bind(family_id)
    .bind(reason)
    .execute(&state.pool)
    .await?
    .rows_affected() as u64;
    mark_family_revoked_in_redis(state, family_id).await?;
    Ok(affected)
}

async fn revoke_family_by_sid(
    state: &AppState,
    sid: &str,
    user_id: i64,
    reason: &str,
) -> Result<u64, AppError> {
    let family_id: Option<String> = sqlx::query_scalar(
        r#"
        SELECT family_id
        FROM auth_refresh_sessions
        WHERE sid = $1 AND user_id = $2
        "#,
    )
    .bind(sid)
    .bind(user_id)
    .fetch_optional(&state.pool)
    .await?;

    let Some(family_id) = family_id else {
        return Ok(0);
    };

    let affected = revoke_family_by_id(state, &family_id, reason).await?;
    let _ = state
        .redis
        .remove_set_member("auth:user:sessions", &user_id.to_string(), sid)
        .await;
    let _ = state.redis.delete_key("auth:rt:session", sid).await;
    Ok(affected)
}

fn session_context_from_headers(headers: &HeaderMap) -> SessionContext {
    SessionContext {
        user_agent: headers
            .get(header::USER_AGENT)
            .and_then(|v| v.to_str().ok())
            .map(str::trim)
            .filter(|v| !v.is_empty())
            .map(|v| v.chars().take(512).collect()),
        ip_hash: extract_ip_hash(headers),
    }
}

fn extract_ip_hash(headers: &HeaderMap) -> Option<String> {
    let raw_ip = headers
        .get("x-forwarded-for")
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.split(',').next())
        .map(str::trim)
        .filter(|v| !v.is_empty())
        .or_else(|| {
            headers
                .get("x-real-ip")
                .and_then(|v| v.to_str().ok())
                .map(str::trim)
                .filter(|v| !v.is_empty())
        })?;

    let mut hasher = Sha1::new();
    hasher.update(raw_ip.as_bytes());
    Some(format!("{:x}", hasher.finalize()))
}

fn set_refresh_cookie_header(
    headers: &mut HeaderMap,
    refresh_token: &str,
    max_age_secs: u64,
) -> Result<(), AppError> {
    let cookie = build_refresh_cookie(refresh_token, max_age_secs, false);
    headers.append(header::SET_COOKIE, HeaderValue::from_str(&cookie)?);
    Ok(())
}

fn clear_refresh_cookie_header(headers: &mut HeaderMap) -> Result<(), AppError> {
    let cookie = build_refresh_cookie("", 0, true);
    headers.append(header::SET_COOKIE, HeaderValue::from_str(&cookie)?);
    Ok(())
}

fn build_refresh_cookie(value: &str, max_age_secs: u64, clear: bool) -> String {
    let secure = refresh_cookie_secure_enabled();
    let cookie_value = if clear { "" } else { value };
    let mut cookie = format!(
        "{}={}; Path=/api/auth; HttpOnly; SameSite=Lax; Max-Age={}",
        REFRESH_COOKIE_NAME,
        cookie_value,
        if clear { 0 } else { max_age_secs }
    );
    if secure {
        cookie.push_str("; Secure");
    }
    cookie
}

fn extract_refresh_token(headers: &HeaderMap) -> Option<String> {
    let cookie_header = headers.get(header::COOKIE)?.to_str().ok()?;
    for item in cookie_header.split(';') {
        let trimmed = item.trim();
        let mut parts = trimmed.splitn(2, '=');
        let key = parts.next()?.trim();
        let value = parts.next().unwrap_or_default().trim();
        if key == REFRESH_COOKIE_NAME && !value.is_empty() {
            return Some(value.to_string());
        }
    }
    None
}

fn ttl_from_exp(exp: usize) -> u64 {
    let now = Utc::now().timestamp().max(0) as usize;
    exp.saturating_sub(now) as u64
}

fn refresh_cookie_secure_enabled() -> bool {
    for key in ["AICOMM_ENV", "APP_ENV", "RUST_ENV", "ENV"] {
        if let Ok(value) = std::env::var(key) {
            let normalized = value.trim().to_ascii_lowercase();
            if normalized == "prod" || normalized == "production" {
                return true;
            }
        }
    }
    false
}

fn auth_fail_closed_enabled(state: &AppState) -> bool {
    if state.config.redis.startup_fail_closed() {
        return true;
    }
    refresh_cookie_secure_enabled()
}

fn handle_auth_redis_unit_result(
    state: &AppState,
    result: anyhow::Result<()>,
    fallback_code: &str,
) -> Result<(), AppError> {
    match result {
        Ok(_) => Ok(()),
        Err(err) => {
            if auth_fail_closed_enabled(state) {
                Err(AppError::AuthError(fallback_code.to_string()))
            } else {
                tracing::warn!("auth redis degraded as fail-open: {}", err);
                Ok(())
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use anyhow::Result;
    use axum::http::header::SET_COOKIE;
    use http_body_util::BodyExt;

    #[tokio::test]
    async fn signin_should_return_access_token_and_refresh_cookie() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let input = SigninUser::new("tchen@acme.org", "123456");
        let response = signin_handler(State(state.clone()), HeaderMap::new(), Json(input))
            .await?
            .into_response();
        assert_eq!(response.status(), StatusCode::OK);
        assert!(response.headers().get(SET_COOKIE).is_some());
        let body = response.into_body().collect().await?.to_bytes();
        let ret: AuthOutput = serde_json::from_slice(&body)?;
        assert!(!ret.access_token.is_empty());
        assert_eq!(ret.token_type, "Bearer");
        Ok(())
    }

    #[tokio::test]
    async fn refresh_should_rotate_token() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let signin = signin_handler(
            State(state.clone()),
            HeaderMap::new(),
            Json(SigninUser::new("tchen@acme.org", "123456")),
        )
        .await?
        .into_response();
        let set_cookie = signin
            .headers()
            .get(SET_COOKIE)
            .and_then(|v| v.to_str().ok())
            .unwrap_or_default()
            .to_string();
        let cookie = set_cookie.split(';').next().unwrap_or_default().to_string();

        let mut headers = HeaderMap::new();
        headers.insert(header::COOKIE, HeaderValue::from_str(&cookie)?);
        let refreshed = refresh_handler(State(state), headers)
            .await?
            .into_response();
        assert_eq!(refreshed.status(), StatusCode::OK);
        assert!(refreshed.headers().get(SET_COOKIE).is_some());
        let body = refreshed.into_body().collect().await?.to_bytes();
        let ret: RefreshOutput = serde_json::from_slice(&body)?;
        assert!(!ret.access_token.is_empty());
        Ok(())
    }
}
