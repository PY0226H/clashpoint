use crate::{AppError, AppState};
use chat_core::User;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::FromRow;
use utoipa::{IntoParams, ToSchema};

mod helpers;
mod order_flow;
mod order_ops;
mod query_ops;
mod receipt_verify;

const MAX_RECEIPT_LEN: usize = 4096;

#[derive(Debug, Clone, FromRow, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct IapProduct {
    pub product_id: String,
    pub coins: i32,
    pub is_active: bool,
}

#[derive(Debug, Clone, IntoParams, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListIapProducts {
    #[serde(default = "default_true")]
    pub active_only: bool,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct VerifyIapOrderInput {
    pub product_id: String,
    pub transaction_id: String,
    pub original_transaction_id: Option<String>,
    pub receipt_data: String,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct VerifyIapOrderOutput {
    pub order_id: u64,
    pub status: String,
    pub verify_mode: String,
    pub verify_reason: Option<String>,
    pub product_id: String,
    pub coins: i32,
    pub credited: bool,
    pub wallet_balance: i64,
}

#[derive(Debug, Clone, IntoParams, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetIapOrderByTransaction {
    pub transaction_id: String,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct IapOrderSnapshot {
    pub order_id: u64,
    pub status: String,
    pub verify_mode: String,
    pub verify_reason: Option<String>,
    pub product_id: String,
    pub coins: i32,
    pub credited: bool,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetIapOrderByTransactionOutput {
    pub found: bool,
    pub order: Option<IapOrderSnapshot>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct WalletBalanceOutput {
    pub ws_id: u64,
    pub user_id: u64,
    pub balance: i64,
}

#[derive(Debug, Clone, IntoParams, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListWalletLedger {
    pub last_id: Option<u64>,
    pub limit: Option<u64>,
}

#[derive(Debug, Clone, FromRow, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct WalletLedgerItem {
    pub id: i64,
    pub order_id: Option<i64>,
    pub entry_type: String,
    pub amount_delta: i64,
    pub balance_after: i64,
    pub idempotency_key: String,
    pub metadata: String,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
struct IapOrderRow {
    id: i64,
    ws_id: i64,
    user_id: i64,
    product_id: String,
    status: String,
    verify_mode: String,
    verify_reason: Option<String>,
    coins: i32,
}

#[derive(Debug, Clone, FromRow)]
struct IapOrderSnapshotRow {
    id: i64,
    ws_id: i64,
    user_id: i64,
    product_id: String,
    status: String,
    verify_mode: String,
    verify_reason: Option<String>,
    coins: i32,
    credited: bool,
}

fn default_true() -> bool {
    true
}

#[cfg(test)]
mod tests;
