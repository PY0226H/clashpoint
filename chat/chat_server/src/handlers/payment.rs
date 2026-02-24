use crate::{AppError, AppState, ListIapProducts, ListWalletLedger, VerifyIapOrderInput};
use axum::{
    extract::{Query, State},
    http::StatusCode,
    response::IntoResponse,
    Extension, Json,
};
use chat_core::User;

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
    Json(input): Json<VerifyIapOrderInput>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.verify_iap_order(&user, input).await?;
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
