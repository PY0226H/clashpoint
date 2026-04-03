#[cfg(test)]
use crate::RateLimitDecision;
use crate::{
    application::request_guard::{
        build_rate_limit_headers, enforce_rate_limit, rate_limit_exceeded_response,
        release_idempotency_best_effort, try_acquire_idempotency_or_fail_open,
    },
    AppError, AppState, ErrorOutput, GetIapOrderByTransaction, GetIapOrderByTransactionOutput,
    ListIapProducts, ListIapProductsOutput, ListWalletLedger, VerifyIapOrderInput,
};
use axum::{
    extract::{Query, State},
    http::{HeaderMap, StatusCode},
    response::{IntoResponse, Response},
    Extension, Json,
};
use chat_core::User;
use sha1::{Digest, Sha1};
use std::{
    net::IpAddr,
    sync::{
        atomic::{AtomicU64, Ordering},
        LazyLock,
    },
    time::Instant,
};

const IAP_VERIFY_RATE_LIMIT_PER_WINDOW: u64 = 30;
const IAP_VERIFY_RATE_LIMIT_WINDOW_SECS: u64 = 60;
const IAP_VERIFY_IDEMPOTENCY_TTL_SECS: u64 = 120;
const IAP_PRODUCTS_LIST_USER_RATE_LIMIT_PER_WINDOW: u64 = 120;
const IAP_PRODUCTS_LIST_IP_RATE_LIMIT_PER_WINDOW: u64 = 240;
const IAP_PRODUCTS_LIST_RATE_LIMIT_WINDOW_SECS: u64 = 60;
const IAP_ORDER_PROBE_USER_RATE_LIMIT_PER_WINDOW: u64 = 90;
const IAP_ORDER_PROBE_IP_RATE_LIMIT_PER_WINDOW: u64 = 180;
const IAP_ORDER_PROBE_RATE_LIMIT_WINDOW_SECS: u64 = 60;

#[derive(Debug, Default)]
struct IapProductsListMetrics {
    request_total: AtomicU64,
    success_total: AtomicU64,
    failed_total: AtomicU64,
    rate_limited_total: AtomicU64,
    forbidden_total: AtomicU64,
    result_items_total: AtomicU64,
    result_items_samples_total: AtomicU64,
    cache_hit_total: AtomicU64,
    cache_miss_total: AtomicU64,
    latency_ms_total: AtomicU64,
    latency_ms_samples_total: AtomicU64,
    active_only_true_total: AtomicU64,
    active_only_false_total: AtomicU64,
}

impl IapProductsListMetrics {
    fn observe_start(&self, active_only: bool) {
        self.request_total.fetch_add(1, Ordering::Relaxed);
        if active_only {
            self.active_only_true_total.fetch_add(1, Ordering::Relaxed);
        } else {
            self.active_only_false_total.fetch_add(1, Ordering::Relaxed);
        }
    }

    fn observe_success(&self, items_count: usize, cache_hit: bool, latency_ms: u64) {
        self.success_total.fetch_add(1, Ordering::Relaxed);
        self.result_items_total
            .fetch_add(items_count as u64, Ordering::Relaxed);
        self.result_items_samples_total
            .fetch_add(1, Ordering::Relaxed);
        if cache_hit {
            self.cache_hit_total.fetch_add(1, Ordering::Relaxed);
        } else {
            self.cache_miss_total.fetch_add(1, Ordering::Relaxed);
        }
        self.latency_ms_total
            .fetch_add(latency_ms, Ordering::Relaxed);
        self.latency_ms_samples_total
            .fetch_add(1, Ordering::Relaxed);
    }

    fn observe_failure(&self, latency_ms: u64) {
        self.failed_total.fetch_add(1, Ordering::Relaxed);
        self.latency_ms_total
            .fetch_add(latency_ms, Ordering::Relaxed);
        self.latency_ms_samples_total
            .fetch_add(1, Ordering::Relaxed);
    }

    fn observe_rate_limited(&self) {
        self.rate_limited_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_forbidden(&self) {
        self.forbidden_total.fetch_add(1, Ordering::Relaxed);
    }
}

static IAP_PRODUCTS_LIST_METRICS: LazyLock<IapProductsListMetrics> =
    LazyLock::new(IapProductsListMetrics::default);

#[derive(Debug, Default)]
struct IapOrderProbeMetrics {
    request_total: AtomicU64,
    success_total: AtomicU64,
    failed_total: AtomicU64,
    rate_limited_total: AtomicU64,
    invalid_total: AtomicU64,
    conflict_total: AtomicU64,
    not_found_total: AtomicU64,
    credited_false_total: AtomicU64,
    cache_hit_total: AtomicU64,
    cache_miss_total: AtomicU64,
    latency_ms_total: AtomicU64,
    latency_ms_samples_total: AtomicU64,
}

impl IapOrderProbeMetrics {
    fn observe_start(&self) {
        self.request_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_success(
        &self,
        output: &GetIapOrderByTransactionOutput,
        cache_hit: bool,
        latency_ms: u64,
    ) {
        self.success_total.fetch_add(1, Ordering::Relaxed);
        if !output.found {
            self.not_found_total.fetch_add(1, Ordering::Relaxed);
        }
        if output
            .order
            .as_ref()
            .map(|order| !order.credited)
            .unwrap_or(false)
        {
            self.credited_false_total.fetch_add(1, Ordering::Relaxed);
        }
        if cache_hit {
            self.cache_hit_total.fetch_add(1, Ordering::Relaxed);
        } else {
            self.cache_miss_total.fetch_add(1, Ordering::Relaxed);
        }
        self.latency_ms_total
            .fetch_add(latency_ms, Ordering::Relaxed);
        self.latency_ms_samples_total
            .fetch_add(1, Ordering::Relaxed);
    }

    fn observe_failed(&self, latency_ms: u64) {
        self.failed_total.fetch_add(1, Ordering::Relaxed);
        self.latency_ms_total
            .fetch_add(latency_ms, Ordering::Relaxed);
        self.latency_ms_samples_total
            .fetch_add(1, Ordering::Relaxed);
    }

    fn observe_rate_limited(&self) {
        self.rate_limited_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_invalid(&self) {
        self.invalid_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_conflict(&self) {
        self.conflict_total.fetch_add(1, Ordering::Relaxed);
    }
}

static IAP_ORDER_PROBE_METRICS: LazyLock<IapOrderProbeMetrics> =
    LazyLock::new(IapOrderProbeMetrics::default);

/// List purchasable IAP products.
#[utoipa::path(
    get,
    path = "/api/pay/iap/products",
    params(
        ListIapProducts
    ),
    responses(
        (status = 200, description = "IAP product list", body = crate::ListIapProductsOutput),
        (status = 400, description = "Invalid query", body = ErrorOutput),
        (status = 401, description = "Auth error", body = ErrorOutput),
        (status = 403, description = "Phone not bound or admin-only query", body = ErrorOutput),
        (status = 429, description = "Rate limited", body = ErrorOutput),
        (status = 500, description = "Internal server error", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_iap_products_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(input): Query<ListIapProducts>,
) -> Result<Response, AppError> {
    let started_at = Instant::now();
    IAP_PRODUCTS_LIST_METRICS.observe_start(input.active_only);
    let active_only = input.active_only;
    let request_id = request_id_from_headers(&headers);

    if !input.active_only {
        let rbac = state.get_ops_rbac_me(&user).await?;
        let has_ops_access = rbac.is_owner || rbac.role.is_some();
        if !has_ops_access {
            IAP_PRODUCTS_LIST_METRICS.observe_forbidden();
            tracing::warn!(
                user_id = user.id,
                request_id = request_id.as_deref().unwrap_or_default(),
                active_only = input.active_only,
                decision = "admin_only_rejected",
                "list iap products rejected for non-ops user"
            );
            return Ok((
                StatusCode::FORBIDDEN,
                Json(ErrorOutput::new("iap_products_admin_only")),
            )
                .into_response());
        }
    }

    let user_decision = enforce_rate_limit(
        &state,
        "iap_products_list_user",
        &user.id.to_string(),
        IAP_PRODUCTS_LIST_USER_RATE_LIMIT_PER_WINDOW,
        IAP_PRODUCTS_LIST_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let user_decision = maybe_override_rate_limit_decision(&headers, "user", user_decision);
    let resp_headers = build_rate_limit_headers(&user_decision)?;
    if !user_decision.allowed {
        IAP_PRODUCTS_LIST_METRICS.observe_rate_limited();
        tracing::warn!(
            user_id = user.id,
            request_id = request_id.as_deref().unwrap_or_default(),
            active_only = input.active_only,
            decision = "rate_limited_user",
            "list iap products blocked by user rate limiter"
        );
        return Ok(rate_limit_exceeded_response(
            "iap_products_list",
            resp_headers,
        ));
    }

    let ip_limit_key =
        request_rate_limit_ip_key_from_headers(&headers).unwrap_or_else(|| "unknown".to_string());
    let ip_decision = enforce_rate_limit(
        &state,
        "iap_products_list_ip",
        &ip_limit_key,
        IAP_PRODUCTS_LIST_IP_RATE_LIMIT_PER_WINDOW,
        IAP_PRODUCTS_LIST_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let ip_decision = maybe_override_rate_limit_decision(&headers, "ip", ip_decision);
    if !ip_decision.allowed {
        IAP_PRODUCTS_LIST_METRICS.observe_rate_limited();
        tracing::warn!(
            user_id = user.id,
            request_id = request_id.as_deref().unwrap_or_default(),
            active_only = input.active_only,
            decision = "rate_limited_ip",
            "list iap products blocked by ip rate limiter"
        );
        return Ok(rate_limit_exceeded_response(
            "iap_products_list",
            build_rate_limit_headers(&ip_decision)?,
        ));
    }

    let (output, cache_hit): (ListIapProductsOutput, bool) =
        match state.list_iap_products_with_cache(input).await {
            Ok(v) => v,
            Err(err) => {
                let latency_ms = started_at.elapsed().as_millis() as u64;
                IAP_PRODUCTS_LIST_METRICS.observe_failure(latency_ms);
                tracing::warn!(
                    user_id = user.id,
                    request_id = request_id.as_deref().unwrap_or_default(),
                    latency_ms,
                    decision = "failed",
                    "list iap products query failed: {}",
                    err
                );
                return Err(err);
            }
        };

    let latency_ms = started_at.elapsed().as_millis() as u64;
    IAP_PRODUCTS_LIST_METRICS.observe_success(output.items.len(), cache_hit, latency_ms);
    tracing::info!(
        user_id = user.id,
        request_id = request_id.as_deref().unwrap_or_default(),
        active_only,
        result_count = output.items.len(),
        cache_hit,
        revision = output.revision.as_deref().unwrap_or_default(),
        latency_ms,
        decision = "success",
        "list iap products served"
    );
    Ok((StatusCode::OK, resp_headers, Json(output)).into_response())
}

/// Verify an Apple IAP transaction and credit wallet on success.
#[utoipa::path(
    post,
    path = "/api/pay/iap/verify",
    request_body = VerifyIapOrderInput,
    responses(
        (status = 200, description = "Verification result", body = crate::VerifyIapOrderOutput),
        (status = 400, description = "Invalid input", body = ErrorOutput),
        (status = 404, description = "Product not found", body = ErrorOutput),
        (status = 409, description = "Transaction conflict", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn verify_iap_order_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(input): Json<VerifyIapOrderInput>,
) -> Result<impl IntoResponse, AppError> {
    let limiter_key = format!("user:{}:tx:{}", user.id, input.transaction_id.trim());
    let decision = enforce_rate_limit(
        &state,
        "iap_verify",
        &limiter_key,
        IAP_VERIFY_RATE_LIMIT_PER_WINDOW,
        IAP_VERIFY_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    let rate_headers = build_rate_limit_headers(&decision)?;
    if !decision.allowed {
        return Ok(rate_limit_exceeded_response("iap_verify", rate_headers));
    }

    let request_idempotency_key = headers
        .get("idempotency-key")
        .and_then(|v| v.to_str().ok())
        .map(str::trim)
        .filter(|v| !v.is_empty())
        .map(ToOwned::to_owned)
        .unwrap_or_else(|| input.transaction_id.trim().to_string());
    let acquired = try_acquire_idempotency_or_fail_open(
        &state,
        "iap_verify",
        &request_idempotency_key,
        IAP_VERIFY_IDEMPOTENCY_TTL_SECS,
    )
    .await;
    if !acquired {
        return Ok((
            StatusCode::CONFLICT,
            rate_headers,
            Json(crate::ErrorOutput::new("idempotency_conflict:iap_verify")),
        )
            .into_response());
    }

    let ret = match state.verify_iap_order(&user, input).await {
        Ok(v) => v,
        Err(err) => {
            release_idempotency_best_effort(&state, "iap_verify", &request_idempotency_key).await;
            return Err(err);
        }
    };
    Ok((StatusCode::OK, rate_headers, Json(ret)).into_response())
}

/// Query existing IAP order by transaction id for current user.
#[utoipa::path(
    get,
    path = "/api/pay/iap/orders/by-transaction",
    params(
        GetIapOrderByTransaction
    ),
    responses(
        (status = 200, description = "Order query result", body = crate::GetIapOrderByTransactionOutput),
        (status = 400, description = "Invalid query", body = ErrorOutput),
        (status = 401, description = "Auth error", body = ErrorOutput),
        (status = 403, description = "Phone not bound", body = ErrorOutput),
        (status = 429, description = "Rate limited", body = ErrorOutput),
        (status = 409, description = "Transaction belongs to another user", body = ErrorOutput),
        (status = 500, description = "Internal server error", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_iap_order_by_transaction_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(input): Query<GetIapOrderByTransaction>,
) -> Result<Response, AppError> {
    let started_at = Instant::now();
    IAP_ORDER_PROBE_METRICS.observe_start();
    let request_id = request_id_from_headers(&headers);
    let transaction_id_hash = hash_with_sha1(input.transaction_id.trim());

    let user_decision = enforce_rate_limit(
        &state,
        "iap_order_probe_user",
        &user.id.to_string(),
        IAP_ORDER_PROBE_USER_RATE_LIMIT_PER_WINDOW,
        IAP_ORDER_PROBE_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let user_decision = maybe_override_rate_limit_decision(&headers, "user", user_decision);
    let resp_headers = build_rate_limit_headers(&user_decision)?;
    if !user_decision.allowed {
        IAP_ORDER_PROBE_METRICS.observe_rate_limited();
        tracing::warn!(
            user_id = user.id,
            request_id = request_id.as_deref().unwrap_or_default(),
            transaction_id_hash,
            decision = "rate_limited_user",
            "iap order probe blocked by user rate limiter"
        );
        return Ok(rate_limit_exceeded_response(
            "iap_order_probe",
            resp_headers,
        ));
    }

    let ip_limit_key =
        request_rate_limit_ip_key_from_headers(&headers).unwrap_or_else(|| "unknown".to_string());
    let ip_decision = enforce_rate_limit(
        &state,
        "iap_order_probe_ip",
        &ip_limit_key,
        IAP_ORDER_PROBE_IP_RATE_LIMIT_PER_WINDOW,
        IAP_ORDER_PROBE_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let ip_decision = maybe_override_rate_limit_decision(&headers, "ip", ip_decision);
    if !ip_decision.allowed {
        IAP_ORDER_PROBE_METRICS.observe_rate_limited();
        tracing::warn!(
            user_id = user.id,
            request_id = request_id.as_deref().unwrap_or_default(),
            transaction_id_hash,
            decision = "rate_limited_ip",
            "iap order probe blocked by ip rate limiter"
        );
        return Ok(rate_limit_exceeded_response(
            "iap_order_probe",
            build_rate_limit_headers(&ip_decision)?,
        ));
    }

    let ret = match state
        .get_iap_order_by_transaction_with_probe_cache(&user, input)
        .await
    {
        Ok((ret, cache_hit)) => {
            let latency_ms = started_at.elapsed().as_millis() as u64;
            IAP_ORDER_PROBE_METRICS.observe_success(&ret, cache_hit, latency_ms);
            tracing::info!(
                user_id = user.id,
                request_id = request_id.as_deref().unwrap_or_default(),
                transaction_id_hash,
                probe_result = iap_order_probe_status_label(ret.probe_status.as_ref()),
                found = ret.found,
                credited = ret.order.as_ref().map(|o| o.credited).unwrap_or(false),
                cache_hit,
                latency_ms,
                decision = "success",
                "iap order probe served"
            );
            ret
        }
        Err(AppError::PaymentError(_)) => {
            IAP_ORDER_PROBE_METRICS.observe_invalid();
            tracing::warn!(
                user_id = user.id,
                request_id = request_id.as_deref().unwrap_or_default(),
                transaction_id_hash,
                error_code = "iap_order_probe_invalid_transaction_id",
                decision = "invalid_transaction_id",
                "iap order probe rejected due to invalid transaction id"
            );
            return Ok((
                StatusCode::BAD_REQUEST,
                resp_headers,
                Json(ErrorOutput::new("iap_order_probe_invalid_transaction_id")),
            )
                .into_response());
        }
        Err(AppError::PaymentConflict(_)) => {
            IAP_ORDER_PROBE_METRICS.observe_conflict();
            tracing::warn!(
                user_id = user.id,
                request_id = request_id.as_deref().unwrap_or_default(),
                transaction_id_hash,
                error_code = "iap_order_probe_conflict",
                decision = "conflict",
                "iap order probe conflict for cross-account transaction"
            );
            return Ok((
                StatusCode::CONFLICT,
                resp_headers,
                Json(ErrorOutput::new("iap_order_probe_conflict")),
            )
                .into_response());
        }
        Err(err) => {
            let latency_ms = started_at.elapsed().as_millis() as u64;
            IAP_ORDER_PROBE_METRICS.observe_failed(latency_ms);
            tracing::warn!(
                user_id = user.id,
                request_id = request_id.as_deref().unwrap_or_default(),
                transaction_id_hash,
                latency_ms,
                decision = "failed",
                "iap order probe query failed: {}",
                err
            );
            return Err(err);
        }
    };
    Ok((StatusCode::OK, resp_headers, Json(ret)).into_response())
}

/// Get current wallet balance.
#[utoipa::path(
    get,
    path = "/api/pay/wallet",
    responses(
        (status = 200, description = "Wallet balance", body = crate::WalletBalanceOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_wallet_balance_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.get_wallet_balance(user.id as u64).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// List user wallet ledger entries.
#[utoipa::path(
    get,
    path = "/api/pay/wallet/ledger",
    params(
        ListWalletLedger
    ),
    responses(
        (status = 200, description = "Wallet ledger list", body = Vec<crate::WalletLedgerItem>),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_wallet_ledger_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Query(input): Query<ListWalletLedger>,
) -> Result<impl IntoResponse, AppError> {
    let rows = state.list_wallet_ledger(user.id as u64, input).await?;
    Ok((StatusCode::OK, Json(rows)))
}

fn request_id_from_headers(headers: &HeaderMap) -> Option<String> {
    headers
        .get("x-request-id")
        .and_then(|value| value.to_str().ok())
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned)
}

fn request_rate_limit_ip_key_from_headers(headers: &HeaderMap) -> Option<String> {
    extract_raw_ip_from_forwarded_headers(headers).map(|ip| hash_with_sha1(&ip))
}

fn extract_raw_ip_from_forwarded_headers(headers: &HeaderMap) -> Option<String> {
    if let Some(value) = headers.get("x-forwarded-for").and_then(|v| v.to_str().ok()) {
        for candidate in value.split(',').map(str::trim) {
            if candidate.parse::<IpAddr>().is_ok() {
                return Some(candidate.to_string());
            }
        }
    }
    headers
        .get("x-real-ip")
        .and_then(|v| v.to_str().ok())
        .map(str::trim)
        .filter(|v| v.parse::<IpAddr>().is_ok())
        .map(ToOwned::to_owned)
}

fn hash_with_sha1(input: &str) -> String {
    let mut hasher = Sha1::new();
    hasher.update(input.as_bytes());
    hex::encode(hasher.finalize())
}

fn iap_order_probe_status_label(status: Option<&crate::IapOrderProbeStatus>) -> &'static str {
    match status {
        Some(crate::IapOrderProbeStatus::NotFound) => "not_found",
        Some(crate::IapOrderProbeStatus::PendingCredit) => "pending_credit",
        Some(crate::IapOrderProbeStatus::VerifiedCredited) => "verified_credited",
        Some(crate::IapOrderProbeStatus::Conflict) => "conflict",
        None => "unknown",
    }
}

#[cfg(test)]
fn maybe_override_rate_limit_decision(
    headers: &HeaderMap,
    target: &str,
    mut decision: RateLimitDecision,
) -> RateLimitDecision {
    let forced = headers
        .get("x-test-force-rate-limit")
        .and_then(|value| value.to_str().ok())
        .map(str::trim)
        .unwrap_or_default();
    if forced.eq_ignore_ascii_case(target) {
        decision.allowed = false;
        decision.remaining = 0;
    }
    decision
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{get_router, models::CreateUser};
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

    async fn create_bound_user_and_token(
        state: &AppState,
        fullname: &str,
        email: &str,
        phone: &str,
        sid: &str,
    ) -> Result<(chat_core::User, String)> {
        let user = state
            .create_user(&CreateUser {
                fullname: fullname.to_string(),
                email: email.to_string(),
                password: "123456".to_string(),
            })
            .await?;
        let _ = state.bind_phone_for_user(user.id, phone).await?;
        let token = issue_token_for_user(state, user.id, sid).await?;
        Ok((user, token))
    }

    #[tokio::test]
    async fn iap_products_route_should_require_auth() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/pay/iap/products")
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::UNAUTHORIZED);
        Ok(())
    }

    #[tokio::test]
    async fn iap_products_route_should_reject_unbound_phone_user() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let user = state
            .create_user(&CreateUser {
                fullname: "IAP No Phone".to_string(),
                email: "iap-no-phone@acme.org".to_string(),
                password: "123456".to_string(),
            })
            .await?;
        let token = issue_token_for_user(&state, user.id, "iap-no-phone-sid").await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/pay/iap/products")
            .header("Authorization", format!("Bearer {}", token))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::FORBIDDEN);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "auth_phone_bind_required");
        Ok(())
    }

    #[tokio::test]
    async fn iap_products_route_should_reject_non_ops_when_active_only_false() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let user = state
            .create_user(&CreateUser {
                fullname: "IAP Bound User".to_string(),
                email: "iap-bound-user@acme.org".to_string(),
                password: "123456".to_string(),
            })
            .await?;
        let _ = state.bind_phone_for_user(user.id, "+8613800990001").await?;
        let token = issue_token_for_user(&state, user.id, "iap-bound-user-sid").await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/pay/iap/products?activeOnly=false")
            .header("Authorization", format!("Bearer {}", token))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::FORBIDDEN);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "iap_products_admin_only");
        Ok(())
    }

    #[tokio::test]
    async fn iap_products_route_should_allow_owner_when_active_only_false() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let token = issue_token_for_user(&state, 1, "iap-owner-sid").await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/pay/iap/products?activeOnly=false")
            .header("Authorization", format!("Bearer {}", token))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::OK);
        let body = res.into_body().collect().await?.to_bytes();
        let output: ListIapProductsOutput = serde_json::from_slice(&body)?;
        assert!(!output.items.is_empty());
        assert!(output.revision.is_some());
        Ok(())
    }

    #[tokio::test]
    async fn iap_products_route_should_return_400_for_invalid_active_only() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let token = issue_token_for_user(&state, 1, "iap-invalid-query-sid").await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/pay/iap/products?activeOnly=invalid")
            .header("Authorization", format!("Bearer {}", token))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::BAD_REQUEST);
        Ok(())
    }

    #[tokio::test]
    async fn iap_products_route_should_return_429_when_rate_limited() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let token = issue_token_for_user(&state, 1, "iap-rate-limit-sid").await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/pay/iap/products")
            .header("Authorization", format!("Bearer {}", token))
            .header("x-test-force-rate-limit", "user")
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::TOO_MANY_REQUESTS);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "rate_limit_exceeded:iap_products_list");
        Ok(())
    }

    #[tokio::test]
    async fn iap_order_probe_route_should_require_auth() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/pay/iap/orders/by-transaction?transactionId=tx-probe-auth-required")
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::UNAUTHORIZED);
        Ok(())
    }

    #[tokio::test]
    async fn iap_order_probe_route_should_reject_unbound_phone_user() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let user = state
            .create_user(&CreateUser {
                fullname: "Probe No Phone".to_string(),
                email: "probe-no-phone@acme.org".to_string(),
                password: "123456".to_string(),
            })
            .await?;
        let token = issue_token_for_user(&state, user.id, "probe-no-phone-sid").await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/pay/iap/orders/by-transaction?transactionId=tx-probe-no-phone")
            .header("Authorization", format!("Bearer {}", token))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::FORBIDDEN);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "auth_phone_bind_required");
        Ok(())
    }

    #[tokio::test]
    async fn iap_order_probe_route_should_return_400_for_invalid_transaction_id() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "Probe Bound User",
            "probe-bound-user@acme.org",
            "+8613800990101",
            "probe-bound-user-sid",
        )
        .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/pay/iap/orders/by-transaction?transactionId=%20")
            .header("Authorization", format!("Bearer {}", token))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::BAD_REQUEST);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "iap_order_probe_invalid_transaction_id");
        Ok(())
    }

    #[tokio::test]
    async fn iap_order_probe_route_should_return_429_when_rate_limited() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "Probe Rate User",
            "probe-rate-user@acme.org",
            "+8613800990102",
            "probe-rate-user-sid",
        )
        .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/pay/iap/orders/by-transaction?transactionId=tx-probe-rate-limit")
            .header("Authorization", format!("Bearer {}", token))
            .header("x-test-force-rate-limit", "user")
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::TOO_MANY_REQUESTS);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "rate_limit_exceeded:iap_order_probe");
        Ok(())
    }

    #[tokio::test]
    async fn iap_order_probe_route_should_return_200_for_not_found() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "Probe NotFound User",
            "probe-not-found-user@acme.org",
            "+8613800990103",
            "probe-not-found-sid",
        )
        .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/pay/iap/orders/by-transaction?transactionId=tx-probe-not-found")
            .header("Authorization", format!("Bearer {}", token))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::OK);
        let body = res.into_body().collect().await?.to_bytes();
        let out: GetIapOrderByTransactionOutput = serde_json::from_slice(&body)?;
        assert!(!out.found);
        assert_eq!(out.probe_status, Some(crate::IapOrderProbeStatus::NotFound));
        assert!(out.next_retry_after_ms.is_some());
        Ok(())
    }

    #[tokio::test]
    async fn iap_order_probe_route_should_return_200_for_verified_hit() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (user, token) = create_bound_user_and_token(
            &state,
            "Probe Hit User",
            "probe-hit-user@acme.org",
            "+8613800990104",
            "probe-hit-sid",
        )
        .await?;
        state
            .verify_iap_order(
                &user,
                VerifyIapOrderInput {
                    product_id: "com.echoisle.coins.60".to_string(),
                    transaction_id: "tx-probe-hit".to_string(),
                    original_transaction_id: None,
                    receipt_data: "mock_ok_receipt".to_string(),
                },
            )
            .await?;

        let app = get_router(state).await?;
        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/pay/iap/orders/by-transaction?transactionId=tx-probe-hit")
            .header("Authorization", format!("Bearer {}", token))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::OK);
        let body = res.into_body().collect().await?.to_bytes();
        let out: GetIapOrderByTransactionOutput = serde_json::from_slice(&body)?;
        assert!(out.found);
        assert!(out
            .order
            .as_ref()
            .map(|order| order.credited)
            .unwrap_or(false));
        assert_eq!(
            out.probe_status,
            Some(crate::IapOrderProbeStatus::VerifiedCredited)
        );
        assert!(out.next_retry_after_ms.is_none());
        Ok(())
    }

    #[tokio::test]
    async fn iap_order_probe_route_should_return_409_for_cross_user_conflict() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (user1, _token1) = create_bound_user_and_token(
            &state,
            "Probe Conflict User1",
            "probe-conflict-user1@acme.org",
            "+8613800990105",
            "probe-conflict-user1-sid",
        )
        .await?;
        let (_user2, token2) = create_bound_user_and_token(
            &state,
            "Probe Conflict User2",
            "probe-conflict-user2@acme.org",
            "+8613800990106",
            "probe-conflict-user2-sid",
        )
        .await?;

        state
            .verify_iap_order(
                &user1,
                VerifyIapOrderInput {
                    product_id: "com.echoisle.coins.60".to_string(),
                    transaction_id: "tx-probe-conflict".to_string(),
                    original_transaction_id: None,
                    receipt_data: "mock_ok_receipt".to_string(),
                },
            )
            .await?;

        let app = get_router(state).await?;
        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/pay/iap/orders/by-transaction?transactionId=tx-probe-conflict")
            .header("Authorization", format!("Bearer {}", token2))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::CONFLICT);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "iap_order_probe_conflict");
        Ok(())
    }
}
