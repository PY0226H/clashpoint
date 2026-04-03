use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::FromRow;
use utoipa::{IntoParams, ToSchema};

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

#[derive(Debug, Clone, PartialEq, Eq, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum IapProductsEmptyReason {
    AllInactive,
    NoConfig,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListIapProductsOutput {
    pub items: Vec<IapProduct>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub revision: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub empty_reason: Option<IapProductsEmptyReason>,
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

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct VerifyIapErrorOutput {
    pub error: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub retry_after_ms: Option<u64>,
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

#[derive(Debug, Clone, PartialEq, Eq, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum IapOrderProbeStatus {
    NotFound,
    PendingCredit,
    VerifiedCredited,
    Conflict,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetIapOrderByTransactionOutput {
    pub found: bool,
    pub order: Option<IapOrderSnapshot>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub probe_status: Option<IapOrderProbeStatus>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub next_retry_after_ms: Option<u64>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct WalletBalanceOutput {
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
pub(super) struct IapOrderRow {
    pub(super) id: i64,
    pub(super) user_id: i64,
    pub(super) product_id: String,
    pub(super) status: String,
    pub(super) verify_mode: String,
    pub(super) verify_reason: Option<String>,
    pub(super) coins: i32,
}

#[derive(Debug, Clone, FromRow)]
pub(super) struct IapOrderSnapshotRow {
    pub(super) id: i64,
    pub(super) user_id: i64,
    pub(super) product_id: String,
    pub(super) status: String,
    pub(super) verify_mode: String,
    pub(super) verify_reason: Option<String>,
    pub(super) coins: i32,
    pub(super) credited: bool,
}

fn default_true() -> bool {
    true
}
