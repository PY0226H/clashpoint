#[cfg(test)]
use crate::RateLimitDecision;
use crate::{
    application::request_guard::{
        build_rate_limit_headers, enforce_rate_limit, rate_limit_exceeded_response,
        release_idempotency_best_effort, try_acquire_idempotency_or_fail_open,
    },
    AppError, AppState, ErrorOutput, GetIapOrderByTransaction, GetIapOrderByTransactionOutput,
    ListIapProducts, ListIapProductsOutput, ListWalletLedger, VerifyIapErrorOutput,
    VerifyIapOrderInput, VerifyIapOrderOutput,
};
use axum::{
    extract::{Query, State},
    http::{HeaderMap, HeaderName, HeaderValue, StatusCode},
    response::{IntoResponse, Response},
    Extension, Json,
};
use chat_core::User;
use sha1::{Digest, Sha1};
use sqlx::FromRow;
use std::{
    env,
    net::IpAddr,
    sync::{
        atomic::{AtomicU64, Ordering},
        LazyLock,
    },
    time::Instant,
};

const IAP_VERIFY_USER_GLOBAL_RATE_LIMIT_PER_WINDOW: u64 = 120;
const IAP_VERIFY_USER_TX_RATE_LIMIT_PER_WINDOW: u64 = 30;
const IAP_VERIFY_IP_RATE_LIMIT_PER_WINDOW: u64 = 240;
const IAP_VERIFY_RATE_LIMIT_WINDOW_SECS: u64 = 60;
const IAP_VERIFY_IDEMPOTENCY_TTL_SECS: u64 = 120;
const IAP_VERIFY_TRANSIENT_RETRY_AFTER_MS: u64 = 1_200;
const IAP_PRODUCTS_LIST_USER_RATE_LIMIT_PER_WINDOW: u64 = 120;
const IAP_PRODUCTS_LIST_IP_RATE_LIMIT_PER_WINDOW: u64 = 240;
const IAP_PRODUCTS_LIST_RATE_LIMIT_WINDOW_SECS: u64 = 60;
const IAP_ORDER_PROBE_USER_RATE_LIMIT_PER_WINDOW: u64 = 90;
const IAP_ORDER_PROBE_IP_RATE_LIMIT_PER_WINDOW: u64 = 180;
const IAP_ORDER_PROBE_RATE_LIMIT_WINDOW_SECS: u64 = 60;
const WALLET_BALANCE_USER_RATE_LIMIT_PER_WINDOW: u64 = 180;
const WALLET_BALANCE_IP_RATE_LIMIT_PER_WINDOW: u64 = 360;
const WALLET_BALANCE_RATE_LIMIT_WINDOW_SECS: u64 = 60;
const WALLET_BALANCE_RECONCILE_WORKER_INTERVAL_DEFAULT_SECS: u64 = 600;
const WALLET_BALANCE_RECONCILE_WORKER_SAMPLE_LIMIT_DEFAULT: usize = 50;

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

#[derive(Debug, Default)]
struct IapVerifyMetrics {
    request_total: AtomicU64,
    success_total: AtomicU64,
    failed_total: AtomicU64,
    rate_limited_total: AtomicU64,
    idempotency_conflict_total: AtomicU64,
    retryable_apple_total: AtomicU64,
    latency_ms_total: AtomicU64,
    latency_ms_samples_total: AtomicU64,
}

impl IapVerifyMetrics {
    fn observe_start(&self) {
        self.request_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_success(&self, latency_ms: u64) {
        self.success_total.fetch_add(1, Ordering::Relaxed);
        self.latency_ms_total
            .fetch_add(latency_ms, Ordering::Relaxed);
        self.latency_ms_samples_total
            .fetch_add(1, Ordering::Relaxed);
    }

    fn observe_failed(&self, latency_ms: u64, retryable_apple: bool) {
        self.failed_total.fetch_add(1, Ordering::Relaxed);
        if retryable_apple {
            self.retryable_apple_total.fetch_add(1, Ordering::Relaxed);
        }
        self.latency_ms_total
            .fetch_add(latency_ms, Ordering::Relaxed);
        self.latency_ms_samples_total
            .fetch_add(1, Ordering::Relaxed);
    }

    fn observe_rate_limited(&self) {
        self.rate_limited_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_idempotency_conflict(&self) {
        self.idempotency_conflict_total
            .fetch_add(1, Ordering::Relaxed);
    }
}

static IAP_VERIFY_METRICS: LazyLock<IapVerifyMetrics> = LazyLock::new(IapVerifyMetrics::default);

#[derive(Debug, Default)]
struct WalletBalanceMetrics {
    request_total: AtomicU64,
    success_total: AtomicU64,
    failed_total: AtomicU64,
    rate_limited_total: AtomicU64,
    cache_hit_total: AtomicU64,
    cache_miss_total: AtomicU64,
    latency_ms_total: AtomicU64,
    latency_ms_samples_total: AtomicU64,
}

impl WalletBalanceMetrics {
    fn observe_start(&self) {
        self.request_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_success(&self, cache_hit: bool, latency_ms: u64) {
        self.success_total.fetch_add(1, Ordering::Relaxed);
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
}

static WALLET_BALANCE_METRICS: LazyLock<WalletBalanceMetrics> =
    LazyLock::new(WalletBalanceMetrics::default);

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
        (status = 400, description = "Invalid input or retryable verification failure", body = crate::VerifyIapErrorOutput),
        (status = 401, description = "Auth error", body = crate::VerifyIapErrorOutput),
        (status = 403, description = "Phone not bound", body = crate::VerifyIapErrorOutput),
        (status = 404, description = "Product not found", body = crate::VerifyIapErrorOutput),
        (status = 409, description = "Transaction conflict", body = crate::VerifyIapErrorOutput),
        (status = 429, description = "Rate limited", body = crate::VerifyIapErrorOutput),
        (status = 500, description = "Internal server error", body = crate::VerifyIapErrorOutput),
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
) -> Result<Response, AppError> {
    let started_at = Instant::now();
    IAP_VERIFY_METRICS.observe_start();
    let request_id = request_id_from_headers(&headers);
    let transaction_id = input.transaction_id.trim();
    let transaction_id_hash = hash_with_sha1(transaction_id);

    let user_global_decision = enforce_rate_limit(
        &state,
        "iap_verify_user_global",
        &user.id.to_string(),
        IAP_VERIFY_USER_GLOBAL_RATE_LIMIT_PER_WINDOW,
        IAP_VERIFY_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let user_global_decision =
        maybe_override_rate_limit_decision(&headers, "verify_user_global", user_global_decision);
    let mut resp_headers = build_rate_limit_headers(&user_global_decision)?;
    if !user_global_decision.allowed {
        IAP_VERIFY_METRICS.observe_rate_limited();
        tracing::warn!(
            user_id = user.id,
            request_id = request_id.as_deref().unwrap_or_default(),
            transaction_id_hash,
            decision = "rate_limited_user_global",
            "iap verify blocked by user-global rate limiter"
        );
        return Ok(rate_limit_exceeded_response("iap_verify", resp_headers));
    }

    let user_tx_limit_key = format!("user:{}:tx:{transaction_id}", user.id);
    let user_tx_decision = enforce_rate_limit(
        &state,
        "iap_verify_user_tx",
        &user_tx_limit_key,
        IAP_VERIFY_USER_TX_RATE_LIMIT_PER_WINDOW,
        IAP_VERIFY_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let user_tx_decision =
        maybe_override_rate_limit_decision(&headers, "verify_user_tx", user_tx_decision);
    resp_headers = build_rate_limit_headers(&user_tx_decision)?;
    if !user_tx_decision.allowed {
        IAP_VERIFY_METRICS.observe_rate_limited();
        tracing::warn!(
            user_id = user.id,
            request_id = request_id.as_deref().unwrap_or_default(),
            transaction_id_hash,
            decision = "rate_limited_user_tx",
            "iap verify blocked by user-transaction rate limiter"
        );
        return Ok(rate_limit_exceeded_response("iap_verify", resp_headers));
    }

    let ip_limit_key =
        request_rate_limit_ip_key_from_headers(&headers).unwrap_or_else(|| "unknown".to_string());
    let ip_decision = enforce_rate_limit(
        &state,
        "iap_verify_ip",
        &ip_limit_key,
        IAP_VERIFY_IP_RATE_LIMIT_PER_WINDOW,
        IAP_VERIFY_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let ip_decision = maybe_override_rate_limit_decision(&headers, "verify_ip", ip_decision);
    resp_headers = build_rate_limit_headers(&ip_decision)?;
    if !ip_decision.allowed {
        IAP_VERIFY_METRICS.observe_rate_limited();
        tracing::warn!(
            user_id = user.id,
            request_id = request_id.as_deref().unwrap_or_default(),
            transaction_id_hash,
            decision = "rate_limited_ip",
            "iap verify blocked by ip rate limiter"
        );
        return Ok(rate_limit_exceeded_response("iap_verify", resp_headers));
    }

    let raw_request_idempotency_key = headers
        .get("idempotency-key")
        .and_then(|v| v.to_str().ok())
        .map(str::trim)
        .filter(|v| !v.is_empty())
        .map(ToOwned::to_owned)
        .unwrap_or_else(|| transaction_id.to_string());
    let request_idempotency_key = format!("u{}:{raw_request_idempotency_key}", user.id);
    let acquired = try_acquire_idempotency_or_fail_open(
        &state,
        "iap_verify",
        &request_idempotency_key,
        IAP_VERIFY_IDEMPOTENCY_TTL_SECS,
    )
    .await;
    #[cfg(test)]
    let acquired = maybe_override_idempotency_acquired(&headers, acquired);
    if !acquired {
        IAP_VERIFY_METRICS.observe_idempotency_conflict();
        match try_reuse_verify_output_on_idempotency_conflict(&state, &user, &input).await {
            Ok(Some(reused)) => {
                let latency_ms = started_at.elapsed().as_millis().min(u128::from(u64::MAX)) as u64;
                IAP_VERIFY_METRICS.observe_success(latency_ms);
                tracing::info!(
                    user_id = user.id,
                    request_id = request_id.as_deref().unwrap_or_default(),
                    transaction_id_hash,
                    latency_ms,
                    decision = "idempotency_conflict_reused_result",
                    "iap verify returned existing result on idempotency conflict"
                );
                return Ok((StatusCode::OK, resp_headers, Json(reused)).into_response());
            }
            Ok(None) => {}
            Err(err) => {
                let spec = classify_iap_verify_error(&err);
                let latency_ms = started_at.elapsed().as_millis().min(u128::from(u64::MAX)) as u64;
                IAP_VERIFY_METRICS.observe_failed(latency_ms, spec.retryable_apple);
                tracing::warn!(
                    user_id = user.id,
                    request_id = request_id.as_deref().unwrap_or_default(),
                    transaction_id_hash,
                    latency_ms,
                    error_code = spec.code,
                    decision = "idempotency_conflict_reuse_failed",
                    "iap verify conflict reuse failed: {}",
                    err
                );
                return verify_iap_error_response(
                    spec.status,
                    resp_headers,
                    spec.code,
                    spec.retry_after_ms,
                );
            }
        }
        let latency_ms = started_at.elapsed().as_millis().min(u128::from(u64::MAX)) as u64;
        IAP_VERIFY_METRICS.observe_failed(latency_ms, false);
        tracing::warn!(
            user_id = user.id,
            request_id = request_id.as_deref().unwrap_or_default(),
            transaction_id_hash,
            latency_ms,
            error_code = "iap_verify_conflict_inflight",
            decision = "idempotency_conflict",
            "iap verify rejected due to in-flight idempotency conflict"
        );
        return verify_iap_error_response(
            StatusCode::CONFLICT,
            resp_headers,
            "iap_verify_conflict_inflight",
            None,
        );
    }

    let ret = match state.verify_iap_order(&user, input).await {
        Ok(v) => v,
        Err(err) => {
            release_idempotency_best_effort(&state, "iap_verify", &request_idempotency_key).await;
            let spec = classify_iap_verify_error(&err);
            let latency_ms = started_at.elapsed().as_millis().min(u128::from(u64::MAX)) as u64;
            IAP_VERIFY_METRICS.observe_failed(latency_ms, spec.retryable_apple);
            tracing::warn!(
                user_id = user.id,
                request_id = request_id.as_deref().unwrap_or_default(),
                transaction_id_hash,
                latency_ms,
                error_code = spec.code,
                decision = "failed",
                "iap verify failed: {}",
                err
            );
            return verify_iap_error_response(
                spec.status,
                resp_headers,
                spec.code,
                spec.retry_after_ms,
            );
        }
    };
    release_idempotency_best_effort(&state, "iap_verify", &request_idempotency_key).await;
    let latency_ms = started_at.elapsed().as_millis().min(u128::from(u64::MAX)) as u64;
    IAP_VERIFY_METRICS.observe_success(latency_ms);
    tracing::info!(
        user_id = user.id,
        request_id = request_id.as_deref().unwrap_or_default(),
        transaction_id_hash,
        latency_ms,
        credited = ret.credited,
        order_id = ret.order_id,
        verify_mode = ret.verify_mode.as_str(),
        status = ret.status.as_str(),
        decision = "success",
        "iap verify served"
    );
    Ok((StatusCode::OK, resp_headers, Json(ret)).into_response())
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
        (status = 401, description = "Auth error", body = ErrorOutput),
        (status = 403, description = "Phone not bound", body = ErrorOutput),
        (status = 429, description = "Rate limited", body = ErrorOutput),
        (status = 500, description = "Internal server error", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_wallet_balance_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Response, AppError> {
    let started_at = Instant::now();
    WALLET_BALANCE_METRICS.observe_start();
    let request_id = request_id_from_headers(&headers);

    let user_decision = enforce_rate_limit(
        &state,
        "pay_wallet_balance_user",
        &user.id.to_string(),
        WALLET_BALANCE_USER_RATE_LIMIT_PER_WINDOW,
        WALLET_BALANCE_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let user_decision = maybe_override_rate_limit_decision(&headers, "wallet_user", user_decision);
    let mut resp_headers = build_rate_limit_headers(&user_decision)?;
    apply_wallet_cache_control_headers(&mut resp_headers);
    if !user_decision.allowed {
        WALLET_BALANCE_METRICS.observe_rate_limited();
        tracing::warn!(
            user_id = user.id,
            request_id = request_id.as_deref().unwrap_or_default(),
            decision = "rate_limited_user",
            "wallet balance blocked by user rate limiter"
        );
        return Ok(rate_limit_exceeded_response(
            "pay_wallet_balance",
            resp_headers,
        ));
    }

    let ip_limit_key =
        request_rate_limit_ip_key_from_headers(&headers).unwrap_or_else(|| "unknown".to_string());
    let ip_decision = enforce_rate_limit(
        &state,
        "pay_wallet_balance_ip",
        &ip_limit_key,
        WALLET_BALANCE_IP_RATE_LIMIT_PER_WINDOW,
        WALLET_BALANCE_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let ip_decision = maybe_override_rate_limit_decision(&headers, "wallet_ip", ip_decision);
    if !ip_decision.allowed {
        WALLET_BALANCE_METRICS.observe_rate_limited();
        tracing::warn!(
            user_id = user.id,
            request_id = request_id.as_deref().unwrap_or_default(),
            decision = "rate_limited_ip",
            "wallet balance blocked by ip rate limiter"
        );
        let mut headers = build_rate_limit_headers(&ip_decision)?;
        apply_wallet_cache_control_headers(&mut headers);
        return Ok(rate_limit_exceeded_response("pay_wallet_balance", headers));
    }

    #[cfg(test)]
    if should_force_wallet_internal_error(&headers) {
        let latency_ms = started_at.elapsed().as_millis() as u64;
        WALLET_BALANCE_METRICS.observe_failure(latency_ms);
        tracing::warn!(
            user_id = user.id,
            request_id = request_id.as_deref().unwrap_or_default(),
            latency_ms,
            decision = "forced_internal_error",
            "wallet balance forced internal error for test"
        );
        return Ok((
            StatusCode::INTERNAL_SERVER_ERROR,
            resp_headers,
            Json(ErrorOutput::new("pay_wallet_internal")),
        )
            .into_response());
    }

    match state.get_wallet_balance_with_cache(user.id as u64).await {
        Ok((ret, cache_hit)) => {
            let latency_ms = started_at.elapsed().as_millis() as u64;
            WALLET_BALANCE_METRICS.observe_success(cache_hit, latency_ms);
            tracing::info!(
                user_id = user.id,
                request_id = request_id.as_deref().unwrap_or_default(),
                balance = ret.balance,
                wallet_initialized = ret.wallet_initialized,
                wallet_revision = ret.wallet_revision.as_str(),
                cache_hit,
                latency_ms,
                decision = "success",
                "wallet balance served"
            );
            Ok((StatusCode::OK, resp_headers, Json(ret)).into_response())
        }
        Err(err) => {
            let latency_ms = started_at.elapsed().as_millis() as u64;
            WALLET_BALANCE_METRICS.observe_failure(latency_ms);
            tracing::warn!(
                user_id = user.id,
                request_id = request_id.as_deref().unwrap_or_default(),
                latency_ms,
                decision = "failed",
                "wallet balance query failed: {}",
                err
            );
            Ok((
                StatusCode::INTERNAL_SERVER_ERROR,
                resp_headers,
                Json(ErrorOutput::new("pay_wallet_internal")),
            )
                .into_response())
        }
    }
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

#[derive(Debug, Clone, Copy)]
struct IapVerifyErrorSpec {
    status: StatusCode,
    code: &'static str,
    retry_after_ms: Option<u64>,
    retryable_apple: bool,
}

#[derive(Debug, FromRow)]
struct VerifyIapConflictReplayRow {
    id: i64,
    user_id: i64,
    product_id: String,
    status: String,
    verify_mode: String,
    verify_reason: Option<String>,
    coins: i32,
}

fn classify_iap_verify_error(err: &AppError) -> IapVerifyErrorSpec {
    match err {
        AppError::PaymentError(message) => {
            if is_retryable_apple_error_message(message) {
                return IapVerifyErrorSpec {
                    status: StatusCode::BAD_REQUEST,
                    code: "iap_verify_transient_retryable",
                    retry_after_ms: Some(IAP_VERIFY_TRANSIENT_RETRY_AFTER_MS),
                    retryable_apple: true,
                };
            }
            IapVerifyErrorSpec {
                status: StatusCode::BAD_REQUEST,
                code: "iap_verify_invalid_input",
                retry_after_ms: None,
                retryable_apple: false,
            }
        }
        AppError::PaymentConflict(message) => {
            let code = if message.contains("already belongs to another user") {
                "iap_verify_conflict_replay"
            } else if message.contains("already used with another product") {
                "iap_verify_conflict_product_mismatch"
            } else if message.contains("is not active") {
                "iap_verify_product_inactive"
            } else {
                "iap_verify_conflict"
            };
            IapVerifyErrorSpec {
                status: StatusCode::CONFLICT,
                code,
                retry_after_ms: None,
                retryable_apple: false,
            }
        }
        AppError::NotFound(message) => {
            let code = if message.contains("iap product") {
                "iap_verify_product_not_found"
            } else {
                "iap_verify_not_found"
            };
            IapVerifyErrorSpec {
                status: StatusCode::NOT_FOUND,
                code,
                retry_after_ms: None,
                retryable_apple: false,
            }
        }
        AppError::NotLoggedIn | AppError::JwtError(_) | AppError::AuthError(_) => {
            IapVerifyErrorSpec {
                status: StatusCode::UNAUTHORIZED,
                code: "iap_verify_auth_required",
                retry_after_ms: None,
                retryable_apple: false,
            }
        }
        AppError::ThrottleError(_) => IapVerifyErrorSpec {
            status: StatusCode::TOO_MANY_REQUESTS,
            code: "rate_limit_exceeded:iap_verify",
            retry_after_ms: None,
            retryable_apple: false,
        },
        _ => IapVerifyErrorSpec {
            status: StatusCode::INTERNAL_SERVER_ERROR,
            code: "iap_verify_internal_error",
            retry_after_ms: None,
            retryable_apple: false,
        },
    }
}

fn is_retryable_apple_error_message(message: &str) -> bool {
    message.contains("apple verify transient status")
        || message.contains("apple verify request failed")
        || message.contains("apple verify payload parse failed")
        || message.contains("apple verify payload missing status")
        || message.contains("apple sandbox payload missing status")
        || message.contains("apple production payload missing status")
        || message.contains("apple verify http status")
}

fn verify_iap_error_response(
    status: StatusCode,
    mut headers: HeaderMap,
    code: &str,
    retry_after_ms: Option<u64>,
) -> Result<Response, AppError> {
    if let Some(retry_after_ms) = retry_after_ms {
        headers.insert(
            HeaderName::from_static("x-retry-after-ms"),
            HeaderValue::from_str(&retry_after_ms.to_string())?,
        );
    }
    Ok((
        status,
        headers,
        Json(VerifyIapErrorOutput {
            error: code.to_string(),
            retry_after_ms,
        }),
    )
        .into_response())
}

async fn try_reuse_verify_output_on_idempotency_conflict(
    state: &AppState,
    user: &User,
    input: &VerifyIapOrderInput,
) -> Result<Option<VerifyIapOrderOutput>, AppError> {
    let transaction_id = input.transaction_id.trim();
    if transaction_id.is_empty() {
        return Ok(None);
    }

    let row: Option<VerifyIapConflictReplayRow> = sqlx::query_as(
        r#"
        SELECT id, user_id, product_id, status, verify_mode, verify_reason, coins
        FROM iap_orders
        WHERE platform = 'apple_iap' AND transaction_id = $1
        LIMIT 1
        "#,
    )
    .bind(transaction_id)
    .fetch_optional(&state.pool)
    .await?;

    let Some(row) = row else {
        return Ok(None);
    };

    if row.user_id != user.id {
        return Err(AppError::PaymentConflict(
            "transaction_id already belongs to another user".to_string(),
        ));
    }

    let request_product_id = input.product_id.trim();
    if !request_product_id.is_empty() && request_product_id != row.product_id {
        return Err(AppError::PaymentConflict(
            "transaction_id already used with another product".to_string(),
        ));
    }

    let wallet_balance = state.get_wallet_balance(user.id as u64).await?.balance;
    Ok(Some(VerifyIapOrderOutput {
        order_id: row.id as u64,
        status: row.status,
        verify_mode: row.verify_mode,
        verify_reason: row.verify_reason,
        product_id: row.product_id,
        coins: row.coins,
        credited: false,
        wallet_balance,
    }))
}

fn request_id_from_headers(headers: &HeaderMap) -> Option<String> {
    headers
        .get("x-request-id")
        .and_then(|value| value.to_str().ok())
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned)
}

fn apply_wallet_cache_control_headers(headers: &mut HeaderMap) {
    headers.insert(
        HeaderName::from_static("cache-control"),
        HeaderValue::from_static("no-store, no-cache, must-revalidate"),
    );
    headers.insert(
        HeaderName::from_static("pragma"),
        HeaderValue::from_static("no-cache"),
    );
}

pub(crate) fn wallet_balance_reconcile_worker_enabled() -> bool {
    env::var("WALLET_BALANCE_RECONCILE_WORKER_ENABLED")
        .ok()
        .map(|raw| raw.trim().eq_ignore_ascii_case("true") || raw.trim() == "1")
        .unwrap_or(true)
}

pub(crate) fn wallet_balance_reconcile_worker_interval_secs() -> u64 {
    env::var("WALLET_BALANCE_RECONCILE_WORKER_INTERVAL_SECS")
        .ok()
        .and_then(|raw| raw.trim().parse::<u64>().ok())
        .filter(|value| *value > 0)
        .unwrap_or(WALLET_BALANCE_RECONCILE_WORKER_INTERVAL_DEFAULT_SECS)
}

pub(crate) fn wallet_balance_reconcile_worker_sample_limit() -> usize {
    env::var("WALLET_BALANCE_RECONCILE_WORKER_SAMPLE_LIMIT")
        .ok()
        .and_then(|raw| raw.trim().parse::<usize>().ok())
        .filter(|value| *value > 0)
        .unwrap_or(WALLET_BALANCE_RECONCILE_WORKER_SAMPLE_LIMIT_DEFAULT)
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
fn should_force_wallet_internal_error(headers: &HeaderMap) -> bool {
    headers
        .get("x-test-force-wallet-error")
        .and_then(|value| value.to_str().ok())
        .map(str::trim)
        .map(|value| value.eq_ignore_ascii_case("true") || value == "1")
        .unwrap_or(false)
}

#[cfg(test)]
fn maybe_override_idempotency_acquired(headers: &HeaderMap, acquired: bool) -> bool {
    if headers
        .get("x-test-force-idempotency-conflict")
        .and_then(|value| value.to_str().ok())
        .map(str::trim)
        .map(|value| value.eq_ignore_ascii_case("true") || value == "1")
        .unwrap_or(false)
    {
        return false;
    }
    acquired
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

    #[tokio::test]
    async fn wallet_balance_route_should_require_auth() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/pay/wallet")
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::UNAUTHORIZED);
        Ok(())
    }

    #[tokio::test]
    async fn wallet_balance_route_should_reject_unbound_phone_user() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let user = state
            .create_user(&CreateUser {
                fullname: "Wallet No Phone".to_string(),
                email: "wallet-no-phone@acme.org".to_string(),
                password: "123456".to_string(),
            })
            .await?;
        let token = issue_token_for_user(&state, user.id, "wallet-no-phone-sid").await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/pay/wallet")
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
    async fn wallet_balance_route_should_return_200_with_initialized_wallet() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (user, token) = create_bound_user_and_token(
            &state,
            "Wallet Init User",
            "wallet-init-user@acme.org",
            "+8613800990112",
            "wallet-init-sid",
        )
        .await?;
        sqlx::query(
            r#"
            INSERT INTO user_wallets(user_id, balance, updated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (user_id) DO UPDATE
            SET balance = EXCLUDED.balance, updated_at = NOW()
            "#,
        )
        .bind(user.id)
        .bind(88_i64)
        .execute(&state.pool)
        .await?;

        let app = get_router(state).await?;
        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/pay/wallet")
            .header("Authorization", format!("Bearer {}", token))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::OK);
        assert_eq!(
            res.headers()
                .get("cache-control")
                .and_then(|v| v.to_str().ok()),
            Some("no-store, no-cache, must-revalidate")
        );
        let body = res.into_body().collect().await?.to_bytes();
        let output: crate::WalletBalanceOutput = serde_json::from_slice(&body)?;
        assert_eq!(output.user_id, user.id as u64);
        assert_eq!(output.balance, 88);
        assert!(output.wallet_initialized);
        assert_ne!(output.wallet_revision, "uninitialized");
        Ok(())
    }

    #[tokio::test]
    async fn wallet_balance_route_should_return_200_with_uninitialized_wallet() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "Wallet Empty User",
            "wallet-empty-user@acme.org",
            "+8613800990113",
            "wallet-empty-sid",
        )
        .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/pay/wallet")
            .header("Authorization", format!("Bearer {}", token))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::OK);
        let body = res.into_body().collect().await?.to_bytes();
        let output: crate::WalletBalanceOutput = serde_json::from_slice(&body)?;
        assert_eq!(output.balance, 0);
        assert!(!output.wallet_initialized);
        assert_eq!(output.wallet_revision, "uninitialized");
        Ok(())
    }

    #[tokio::test]
    async fn wallet_balance_route_should_return_429_when_rate_limited() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "Wallet Rate User",
            "wallet-rate-user@acme.org",
            "+8613800990114",
            "wallet-rate-sid",
        )
        .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/pay/wallet")
            .header("Authorization", format!("Bearer {}", token))
            .header("x-test-force-rate-limit", "wallet_user")
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::TOO_MANY_REQUESTS);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "rate_limit_exceeded:pay_wallet_balance");
        Ok(())
    }

    #[tokio::test]
    async fn wallet_balance_route_should_return_500_for_internal_failure() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "Wallet Internal User",
            "wallet-internal-user@acme.org",
            "+8613800990115",
            "wallet-internal-sid",
        )
        .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/pay/wallet")
            .header("Authorization", format!("Bearer {}", token))
            .header("x-test-force-wallet-error", "true")
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::INTERNAL_SERVER_ERROR);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "pay_wallet_internal");
        Ok(())
    }

    fn verify_payload(
        product_id: &str,
        transaction_id: &str,
        receipt_data: &str,
    ) -> Result<String> {
        Ok(serde_json::to_string(&VerifyIapOrderInput {
            product_id: product_id.to_string(),
            transaction_id: transaction_id.to_string(),
            original_transaction_id: None,
            receipt_data: receipt_data.to_string(),
        })?)
    }

    #[tokio::test]
    async fn iap_verify_route_should_require_auth() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::POST)
            .uri("/api/pay/iap/verify")
            .header("Content-Type", "application/json")
            .body(Body::from(verify_payload(
                "com.echoisle.coins.60",
                "tx-verify-auth-required",
                "mock_ok_receipt",
            )?))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::UNAUTHORIZED);
        Ok(())
    }

    #[tokio::test]
    async fn iap_verify_route_should_reject_unbound_phone_user() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let user = state
            .create_user(&CreateUser {
                fullname: "Verify No Phone".to_string(),
                email: "verify-no-phone@acme.org".to_string(),
                password: "123456".to_string(),
            })
            .await?;
        let token = issue_token_for_user(&state, user.id, "verify-no-phone-sid").await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::POST)
            .uri("/api/pay/iap/verify")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .body(Body::from(verify_payload(
                "com.echoisle.coins.60",
                "tx-verify-no-phone",
                "mock_ok_receipt",
            )?))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::FORBIDDEN);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "auth_phone_bind_required");
        Ok(())
    }

    #[tokio::test]
    async fn iap_verify_route_should_return_400_for_invalid_transaction_id() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "Verify Bound User",
            "verify-bound-user@acme.org",
            "+8613800990107",
            "verify-bound-user-sid",
        )
        .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::POST)
            .uri("/api/pay/iap/verify")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .body(Body::from(verify_payload(
                "com.echoisle.coins.60",
                " ",
                "mock_ok_receipt",
            )?))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::BAD_REQUEST);
        let body = res.into_body().collect().await?.to_bytes();
        let error: VerifyIapErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "iap_verify_invalid_input");
        assert!(error.retry_after_ms.is_none());
        Ok(())
    }

    #[tokio::test]
    async fn iap_verify_route_should_return_404_for_unknown_product() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "Verify Unknown Product",
            "verify-unknown-product@acme.org",
            "+8613800990108",
            "verify-unknown-product-sid",
        )
        .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::POST)
            .uri("/api/pay/iap/verify")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .body(Body::from(verify_payload(
                "com.echoisle.coins.unknown",
                "tx-verify-missing-product",
                "mock_ok_receipt",
            )?))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::NOT_FOUND);
        let body = res.into_body().collect().await?.to_bytes();
        let error: VerifyIapErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "iap_verify_product_not_found");
        Ok(())
    }

    #[tokio::test]
    async fn iap_verify_route_should_return_429_when_rate_limited() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "Verify Rate User",
            "verify-rate-user@acme.org",
            "+8613800990109",
            "verify-rate-user-sid",
        )
        .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::POST)
            .uri("/api/pay/iap/verify")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .header("x-test-force-rate-limit", "verify_user_global")
            .body(Body::from(verify_payload(
                "com.echoisle.coins.60",
                "tx-verify-rate-limited",
                "mock_ok_receipt",
            )?))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::TOO_MANY_REQUESTS);
        let body = res.into_body().collect().await?.to_bytes();
        let error: ErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "rate_limit_exceeded:iap_verify");
        Ok(())
    }

    #[tokio::test]
    async fn iap_verify_route_should_return_409_for_inflight_idempotency_conflict() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "Verify Conflict User",
            "verify-conflict-user@acme.org",
            "+8613800990110",
            "verify-conflict-user-sid",
        )
        .await?;
        let app = get_router(state).await?;

        let req = Request::builder()
            .method(Method::POST)
            .uri("/api/pay/iap/verify")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .header("x-test-force-idempotency-conflict", "true")
            .body(Body::from(verify_payload(
                "com.echoisle.coins.60",
                "tx-verify-idempotency-conflict",
                "mock_ok_receipt",
            )?))?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::CONFLICT);
        let body = res.into_body().collect().await?.to_bytes();
        let error: VerifyIapErrorOutput = serde_json::from_slice(&body)?;
        assert_eq!(error.error, "iap_verify_conflict_inflight");
        Ok(())
    }

    #[tokio::test]
    async fn iap_verify_route_should_return_200_reuse_when_conflict_hits_existing_order(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_user, token) = create_bound_user_and_token(
            &state,
            "Verify Reuse User",
            "verify-reuse-user@acme.org",
            "+8613800990111",
            "verify-reuse-user-sid",
        )
        .await?;
        let app = get_router(state.clone()).await?;

        let first_req = Request::builder()
            .method(Method::POST)
            .uri("/api/pay/iap/verify")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .body(Body::from(verify_payload(
                "com.echoisle.coins.60",
                "tx-verify-reuse",
                "mock_ok_receipt",
            )?))?;
        let first_res = app.clone().oneshot(first_req).await?;
        assert_eq!(first_res.status(), StatusCode::OK);

        let second_req = Request::builder()
            .method(Method::POST)
            .uri("/api/pay/iap/verify")
            .header("Authorization", format!("Bearer {}", token))
            .header("Content-Type", "application/json")
            .header("x-test-force-idempotency-conflict", "true")
            .body(Body::from(verify_payload(
                "com.echoisle.coins.60",
                "tx-verify-reuse",
                "mock_ok_receipt",
            )?))?;
        let second_res = app.oneshot(second_req).await?;
        assert_eq!(second_res.status(), StatusCode::OK);
        let body = second_res.into_body().collect().await?.to_bytes();
        let output: VerifyIapOrderOutput = serde_json::from_slice(&body)?;
        assert!(!output.credited);
        assert_eq!(output.status, "verified");
        Ok(())
    }
}
