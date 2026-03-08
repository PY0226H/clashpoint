use crate::{
    application::request_guard::{
        build_rate_limit_headers, enforce_rate_limit, rate_limit_exceeded_response,
        release_idempotency_best_effort, try_acquire_idempotency_or_fail_open,
    },
    AppError, AppState, GetIapOrderByTransaction, ListIapProducts, ListWalletLedger,
    VerifyIapOrderInput,
};
use axum::{
    extract::{Query, State},
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    Extension, Json,
};
use chat_core::User;

const IAP_VERIFY_RATE_LIMIT_PER_WINDOW: u64 = 30;
const IAP_VERIFY_RATE_LIMIT_WINDOW_SECS: u64 = 60;
const IAP_VERIFY_IDEMPOTENCY_TTL_SECS: u64 = 120;

/// List purchasable IAP products.
#[utoipa::path(
    get,
    path = "/api/pay/iap/products",
    params(
        ListIapProducts
    ),
    responses(
        (status = 200, description = "IAP product list", body = Vec<crate::IapProduct>),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_iap_products_handler(
    State(state): State<AppState>,
    Query(input): Query<ListIapProducts>,
) -> Result<impl IntoResponse, AppError> {
    let products = state.list_iap_products(input).await?;
    Ok((StatusCode::OK, Json(products)))
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
    let limiter_key = format!(
        "ws:{}:user:{}:tx:{}",
        user.ws_id,
        user.id,
        input.transaction_id.trim()
    );
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
        (status = 409, description = "Transaction belongs to another user", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_iap_order_by_transaction_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Query(input): Query<GetIapOrderByTransaction>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.get_iap_order_by_transaction(&user, input).await?;
    Ok((StatusCode::OK, Json(ret)))
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
    let ret = state
        .get_wallet_balance(user.ws_id as u64, user.id as u64)
        .await?;
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
    let rows = state
        .list_wallet_ledger(user.ws_id as u64, user.id as u64, input)
        .await?;
    Ok((StatusCode::OK, Json(rows)))
}
