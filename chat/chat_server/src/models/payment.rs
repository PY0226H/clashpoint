use crate::{config::PaymentConfig, AppError, AppState};
use chat_core::User;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha1::{Digest, Sha1};
use sqlx::FromRow;
use std::time::Duration;
use utoipa::{IntoParams, ToSchema};

mod order_ops;

const DEFAULT_LIMIT: u64 = 20;
const MAX_LIMIT: u64 = 100;
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

fn normalize_limit(limit: Option<u64>) -> i64 {
    let limit = limit.unwrap_or(DEFAULT_LIMIT).clamp(1, MAX_LIMIT);
    limit as i64
}

fn validate_identifier(input: &str, field: &str, max_len: usize) -> Result<(), AppError> {
    if input.trim().is_empty() {
        return Err(AppError::PaymentError(format!("{field} cannot be empty")));
    }
    if input.len() > max_len {
        return Err(AppError::PaymentError(format!(
            "{field} is too long, max {max_len}"
        )));
    }
    Ok(())
}

fn hash_receipt(receipt: &str) -> String {
    let mut hasher = Sha1::new();
    hasher.update(receipt.as_bytes());
    hex::encode(hasher.finalize())
}

fn mock_verify_receipt(receipt: &str) -> (String, Option<String>) {
    let trimmed = receipt.trim();
    if trimmed.is_empty() {
        return (
            "rejected".to_string(),
            Some("receipt_data is empty".to_string()),
        );
    }
    if trimmed == "mock_reject" || trimmed.starts_with("mock_reject:") {
        return (
            "rejected".to_string(),
            Some("receipt rejected by mock verifier".to_string()),
        );
    }
    ("verified".to_string(), None)
}

#[derive(Debug, Clone)]
struct ReceiptVerifyResult {
    status: String,
    verify_mode: String,
    verify_reason: Option<String>,
    raw_payload: Value,
}

#[derive(Debug, Clone)]
struct ReceiptRecord {
    transaction_id: String,
    original_transaction_id: Option<String>,
    product_id: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum AppleVerifyEndpoint {
    Production,
    Sandbox,
}

impl AppleVerifyEndpoint {
    fn label(self) -> &'static str {
        match self {
            Self::Production => "production",
            Self::Sandbox => "sandbox",
        }
    }
}

fn normalize_verify_mode(mode: &str) -> &str {
    match mode.trim().to_ascii_lowercase().as_str() {
        "apple" | "prod" | "production" => "apple",
        _ => "mock",
    }
}

fn apple_verify_url(config: &PaymentConfig, endpoint: AppleVerifyEndpoint) -> &str {
    match endpoint {
        AppleVerifyEndpoint::Production => config.apple_verify_url_prod.as_str(),
        AppleVerifyEndpoint::Sandbox => config.apple_verify_url_sandbox.as_str(),
    }
}

fn extract_apple_status(payload: &Value) -> Option<i64> {
    payload.get("status").and_then(Value::as_i64)
}

fn extract_receipt_records(payload: &Value) -> Vec<ReceiptRecord> {
    let mut out = Vec::new();
    for items in [
        payload.get("latest_receipt_info").and_then(Value::as_array),
        payload.pointer("/receipt/in_app").and_then(Value::as_array),
    ]
    .into_iter()
    .flatten()
    {
        for item in items {
            let transaction_id = item
                .get("transaction_id")
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or_default()
                .to_string();
            if transaction_id.is_empty() {
                continue;
            }
            let original_transaction_id = item
                .get("original_transaction_id")
                .and_then(Value::as_str)
                .map(str::trim)
                .filter(|v| !v.is_empty())
                .map(ToString::to_string);
            let product_id = item
                .get("product_id")
                .and_then(Value::as_str)
                .map(str::trim)
                .filter(|v| !v.is_empty())
                .map(ToString::to_string);
            out.push(ReceiptRecord {
                transaction_id,
                original_transaction_id,
                product_id,
            });
        }
    }
    out
}

fn select_matching_record<'a>(
    records: &'a [ReceiptRecord],
    product_id: &str,
    transaction_id: &str,
    original_transaction_id: Option<&str>,
) -> Option<&'a ReceiptRecord> {
    records.iter().find(|record| {
        if record.transaction_id != transaction_id {
            return false;
        }
        if let Some(original) = original_transaction_id {
            if record.original_transaction_id.as_deref() != Some(original) {
                return false;
            }
        }
        record
            .product_id
            .as_deref()
            .map(|v| v == product_id)
            .unwrap_or(true)
    })
}

fn build_mock_verify_result(receipt: &str, transaction_id: &str) -> ReceiptVerifyResult {
    let (status, verify_reason) = mock_verify_receipt(receipt);
    ReceiptVerifyResult {
        status,
        verify_mode: "mock".to_string(),
        verify_reason,
        raw_payload: json!({
            "source": "mock",
            "transactionId": transaction_id,
            "receiptDataLen": receipt.len(),
            "receiptDataPrefix": receipt.chars().take(24).collect::<String>(),
        }),
    }
}

async fn post_apple_verify_receipt(
    client: &reqwest::Client,
    config: &PaymentConfig,
    endpoint: AppleVerifyEndpoint,
    receipt: &str,
) -> Result<Value, AppError> {
    let mut request_body = json!({
        "receipt-data": receipt,
        "exclude-old-transactions": true,
    });
    if !config.apple_shared_secret.trim().is_empty() {
        request_body["password"] = Value::String(config.apple_shared_secret.trim().to_string());
    }

    let response = client
        .post(apple_verify_url(config, endpoint))
        .json(&request_body)
        .send()
        .await
        .map_err(|err| AppError::PaymentError(format!("apple verify request failed: {err}")))?;

    let status = response.status();
    let payload = response.json::<Value>().await.map_err(|err| {
        AppError::PaymentError(format!("apple verify payload parse failed: {err}"))
    })?;
    if !status.is_success() {
        return Err(AppError::PaymentError(format!(
            "apple verify http status {}",
            status.as_u16()
        )));
    }
    Ok(payload)
}

async fn verify_with_apple(
    config: &PaymentConfig,
    product_id: &str,
    transaction_id: &str,
    original_transaction_id: Option<&str>,
    receipt: &str,
) -> Result<ReceiptVerifyResult, AppError> {
    let client = reqwest::Client::builder()
        .timeout(Duration::from_millis(config.verify_timeout_ms.max(1_000)))
        .build()
        .map_err(|err| {
            AppError::PaymentError(format!("build apple verify client failed: {err}"))
        })?;

    let mut endpoint = AppleVerifyEndpoint::Production;
    let mut payload = post_apple_verify_receipt(&client, config, endpoint, receipt).await?;
    let mut status_code = extract_apple_status(&payload)
        .ok_or_else(|| AppError::PaymentError("apple verify payload missing status".to_string()))?;

    if status_code == 21007 {
        endpoint = AppleVerifyEndpoint::Sandbox;
        payload = post_apple_verify_receipt(&client, config, endpoint, receipt).await?;
        status_code = extract_apple_status(&payload).ok_or_else(|| {
            AppError::PaymentError("apple sandbox payload missing status".to_string())
        })?;
    } else if status_code == 21008 {
        endpoint = AppleVerifyEndpoint::Production;
        payload = post_apple_verify_receipt(&client, config, endpoint, receipt).await?;
        status_code = extract_apple_status(&payload).ok_or_else(|| {
            AppError::PaymentError("apple production payload missing status".to_string())
        })?;
    }

    let records = extract_receipt_records(&payload);
    let matched_record = select_matching_record(
        &records,
        product_id,
        transaction_id,
        original_transaction_id,
    );
    let status = if status_code == 0 && matched_record.is_some() {
        "verified"
    } else {
        "rejected"
    }
    .to_string();

    let verify_reason = if status_code != 0 {
        Some(format!("apple verify status {status_code}"))
    } else if matched_record.is_none() {
        Some("transaction/product not found in apple receipt".to_string())
    } else {
        None
    };

    Ok(ReceiptVerifyResult {
        status,
        verify_mode: "apple".to_string(),
        verify_reason,
        raw_payload: json!({
            "source": "apple",
            "endpoint": endpoint.label(),
            "statusCode": status_code,
            "environment": payload.get("environment").and_then(Value::as_str),
            "transactionId": transaction_id,
            "matchedTransaction": matched_record.is_some(),
            "matchedProductId": matched_record.and_then(|v| v.product_id.as_deref()),
            "matchedOriginalTransactionId": matched_record.and_then(|v| v.original_transaction_id.as_deref()),
            "receiptDataLen": receipt.len(),
        }),
    })
}

async fn verify_receipt(
    config: &PaymentConfig,
    product_id: &str,
    transaction_id: &str,
    original_transaction_id: Option<&str>,
    receipt: &str,
) -> Result<ReceiptVerifyResult, AppError> {
    match normalize_verify_mode(&config.verify_mode) {
        "apple" => {
            verify_with_apple(
                config,
                product_id,
                transaction_id,
                original_transaction_id,
                receipt,
            )
            .await
        }
        _ => Ok(build_mock_verify_result(receipt, transaction_id)),
    }
}

#[allow(dead_code)]
impl AppState {
    pub async fn list_iap_products(
        &self,
        input: ListIapProducts,
    ) -> Result<Vec<IapProduct>, AppError> {
        let rows = sqlx::query_as(
            r#"
            SELECT product_id, coins, is_active
            FROM iap_products
            WHERE (NOT $1::boolean OR is_active = TRUE)
            ORDER BY coins ASC
            "#,
        )
        .bind(input.active_only)
        .fetch_all(&self.pool)
        .await?;

        Ok(rows)
    }

    pub async fn get_wallet_balance(
        &self,
        ws_id: u64,
        user_id: u64,
    ) -> Result<WalletBalanceOutput, AppError> {
        let row: Option<(i64,)> = sqlx::query_as(
            r#"
            SELECT balance
            FROM user_wallets
            WHERE ws_id = $1 AND user_id = $2
            "#,
        )
        .bind(ws_id as i64)
        .bind(user_id as i64)
        .fetch_optional(&self.pool)
        .await?;

        Ok(WalletBalanceOutput {
            ws_id,
            user_id,
            balance: row.map(|v| v.0).unwrap_or(0),
        })
    }

    pub async fn list_wallet_ledger(
        &self,
        ws_id: u64,
        user_id: u64,
        input: ListWalletLedger,
    ) -> Result<Vec<WalletLedgerItem>, AppError> {
        let rows = sqlx::query_as(
            r#"
            SELECT
                id,
                order_id,
                entry_type,
                amount_delta,
                balance_after,
                idempotency_key,
                metadata::text AS metadata,
                created_at
            FROM wallet_ledger
            WHERE ws_id = $1
              AND user_id = $2
              AND ($3::bigint IS NULL OR id < $3)
            ORDER BY id DESC
            LIMIT $4
            "#,
        )
        .bind(ws_id as i64)
        .bind(user_id as i64)
        .bind(input.last_id.map(|v| v as i64))
        .bind(normalize_limit(input.limit))
        .fetch_all(&self.pool)
        .await?;

        Ok(rows)
    }
}

#[cfg(test)]
mod tests;
