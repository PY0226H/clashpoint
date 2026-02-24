use crate::{AppError, AppState};
use chat_core::User;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::json;
use sha1::{Digest, Sha1};
use sqlx::{FromRow, Postgres, Transaction};
use utoipa::{IntoParams, ToSchema};

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

async fn wallet_balance_in_tx(
    tx: &mut Transaction<'_, Postgres>,
    ws_id: i64,
    user_id: i64,
) -> Result<i64, AppError> {
    let row: Option<(i64,)> = sqlx::query_as(
        r#"
        SELECT balance
        FROM user_wallets
        WHERE ws_id = $1 AND user_id = $2
        "#,
    )
    .bind(ws_id)
    .bind(user_id)
    .fetch_optional(&mut **tx)
    .await?;
    Ok(row.map(|v| v.0).unwrap_or(0))
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

    pub async fn verify_iap_order(
        &self,
        user: &User,
        input: VerifyIapOrderInput,
    ) -> Result<VerifyIapOrderOutput, AppError> {
        validate_identifier(&input.product_id, "product_id", 64)?;
        validate_identifier(&input.transaction_id, "transaction_id", 128)?;
        if let Some(original) = input.original_transaction_id.as_deref() {
            validate_identifier(original, "original_transaction_id", 128)?;
        }
        if input.receipt_data.len() > MAX_RECEIPT_LEN {
            return Err(AppError::PaymentError(format!(
                "receipt_data is too large, max {MAX_RECEIPT_LEN}"
            )));
        }

        let Some(product): Option<IapProduct> = sqlx::query_as(
            r#"
            SELECT product_id, coins, is_active
            FROM iap_products
            WHERE product_id = $1
            "#,
        )
        .bind(input.product_id.trim())
        .fetch_optional(&self.pool)
        .await?
        else {
            return Err(AppError::NotFound(format!(
                "iap product {}",
                input.product_id.trim()
            )));
        };
        if !product.is_active {
            return Err(AppError::PaymentConflict(format!(
                "iap product {} is not active",
                product.product_id
            )));
        }

        let mut tx = self.pool.begin().await?;

        let existing_order: Option<IapOrderRow> = sqlx::query_as(
            r#"
            SELECT id, ws_id, user_id, product_id, status, verify_mode, verify_reason, coins
            FROM iap_orders
            WHERE platform = 'apple_iap' AND transaction_id = $1
            "#,
        )
        .bind(input.transaction_id.trim())
        .fetch_optional(&mut *tx)
        .await?;

        if let Some(order) = existing_order {
            if order.ws_id != user.ws_id || order.user_id != user.id {
                return Err(AppError::PaymentConflict(
                    "transaction_id already belongs to another user".to_string(),
                ));
            }
            if order.product_id != product.product_id {
                return Err(AppError::PaymentConflict(
                    "transaction_id already used with another product".to_string(),
                ));
            }
            let wallet_balance = wallet_balance_in_tx(&mut tx, user.ws_id, user.id).await?;
            tx.commit().await?;
            return Ok(VerifyIapOrderOutput {
                order_id: order.id as u64,
                status: order.status,
                verify_mode: order.verify_mode,
                verify_reason: order.verify_reason,
                product_id: order.product_id,
                coins: order.coins,
                credited: false,
                wallet_balance,
            });
        }

        let receipt = input.receipt_data.trim();
        let (status, verify_reason) = mock_verify_receipt(receipt);
        let verified_at = if status == "verified" {
            Some(Utc::now())
        } else {
            None
        };
        let raw_payload = json!({
            "receiptDataLen": receipt.len(),
            "receiptDataPrefix": receipt.chars().take(24).collect::<String>(),
            "transactionId": input.transaction_id.trim(),
            "source": "mock",
        });

        let inserted_order: Option<IapOrderRow> = sqlx::query_as(
            r#"
            INSERT INTO iap_orders(
                ws_id, user_id, platform, product_id, transaction_id, original_transaction_id,
                receipt_hash, status, verify_mode, verify_reason, coins, raw_payload, verified_at
            )
            VALUES ($1, $2, 'apple_iap', $3, $4, $5, $6, $7, 'mock', $8, $9, $10, $11)
            ON CONFLICT (platform, transaction_id) DO NOTHING
            RETURNING id, ws_id, user_id, product_id, status, verify_mode, verify_reason, coins
            "#,
        )
        .bind(user.ws_id)
        .bind(user.id)
        .bind(&product.product_id)
        .bind(input.transaction_id.trim())
        .bind(input.original_transaction_id)
        .bind(hash_receipt(receipt))
        .bind(&status)
        .bind(verify_reason.clone())
        .bind(product.coins)
        .bind(raw_payload)
        .bind(verified_at)
        .fetch_optional(&mut *tx)
        .await?;

        let Some(inserted_order) = inserted_order else {
            let order: IapOrderRow = sqlx::query_as(
                r#"
                SELECT id, ws_id, user_id, product_id, status, verify_mode, verify_reason, coins
                FROM iap_orders
                WHERE platform = 'apple_iap' AND transaction_id = $1
                "#,
            )
            .bind(input.transaction_id.trim())
            .fetch_one(&mut *tx)
            .await?;
            if order.ws_id != user.ws_id || order.user_id != user.id {
                return Err(AppError::PaymentConflict(
                    "transaction_id already belongs to another user".to_string(),
                ));
            }
            if order.product_id != product.product_id {
                return Err(AppError::PaymentConflict(
                    "transaction_id already used with another product".to_string(),
                ));
            }
            let wallet_balance = wallet_balance_in_tx(&mut tx, user.ws_id, user.id).await?;
            tx.commit().await?;
            return Ok(VerifyIapOrderOutput {
                order_id: order.id as u64,
                status: order.status,
                verify_mode: order.verify_mode,
                verify_reason: order.verify_reason,
                product_id: order.product_id,
                coins: order.coins,
                credited: false,
                wallet_balance,
            });
        };

        let mut credited = false;
        let wallet_balance = if inserted_order.status == "verified" {
            sqlx::query(
                r#"
                INSERT INTO user_wallets(ws_id, user_id, balance)
                VALUES ($1, $2, 0)
                ON CONFLICT (ws_id, user_id) DO NOTHING
                "#,
            )
            .bind(user.ws_id)
            .bind(user.id)
            .execute(&mut *tx)
            .await?;

            let current: (i64,) = sqlx::query_as(
                r#"
                SELECT balance
                FROM user_wallets
                WHERE ws_id = $1 AND user_id = $2
                FOR UPDATE
                "#,
            )
            .bind(user.ws_id)
            .bind(user.id)
            .fetch_one(&mut *tx)
            .await?;

            let next_balance = current.0 + inserted_order.coins as i64;
            sqlx::query(
                r#"
                UPDATE user_wallets
                SET balance = $3, updated_at = NOW()
                WHERE ws_id = $1 AND user_id = $2
                "#,
            )
            .bind(user.ws_id)
            .bind(user.id)
            .bind(next_balance)
            .execute(&mut *tx)
            .await?;

            let metadata = json!({
                "productId": inserted_order.product_id,
                "transactionId": input.transaction_id.trim(),
                "verifyMode": inserted_order.verify_mode,
            });
            let idempotency_key = format!("iap-order-credit-{}", inserted_order.id);
            sqlx::query(
                r#"
                INSERT INTO wallet_ledger(
                    ws_id, user_id, order_id, entry_type, amount_delta, balance_after,
                    idempotency_key, metadata
                )
                VALUES ($1, $2, $3, 'iap_credit', $4, $5, $6, $7)
                "#,
            )
            .bind(user.ws_id)
            .bind(user.id)
            .bind(inserted_order.id)
            .bind(inserted_order.coins as i64)
            .bind(next_balance)
            .bind(idempotency_key)
            .bind(metadata)
            .execute(&mut *tx)
            .await?;

            credited = true;
            next_balance
        } else {
            wallet_balance_in_tx(&mut tx, user.ws_id, user.id).await?
        };

        tx.commit().await?;

        Ok(VerifyIapOrderOutput {
            order_id: inserted_order.id as u64,
            status: inserted_order.status,
            verify_mode: inserted_order.verify_mode,
            verify_reason: inserted_order.verify_reason,
            product_id: inserted_order.product_id,
            coins: inserted_order.coins,
            credited,
            wallet_balance,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use anyhow::Result;

    fn verify_input(tx: &str, receipt_data: &str) -> VerifyIapOrderInput {
        VerifyIapOrderInput {
            product_id: "com.aicomm.coins.60".to_string(),
            transaction_id: tx.to_string(),
            original_transaction_id: None,
            receipt_data: receipt_data.to_string(),
        }
    }

    #[tokio::test]
    async fn list_iap_products_should_return_seed_data() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let rows = state
            .list_iap_products(ListIapProducts { active_only: true })
            .await?;
        assert!(rows.len() >= 3);
        assert_eq!(rows[0].coins, 60);
        Ok(())
    }

    #[tokio::test]
    async fn verify_iap_order_should_credit_wallet_and_create_ledger() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let user = state
            .find_user_by_id(1)
            .await?
            .expect("user id 1 should exist");

        let out = state
            .verify_iap_order(&user, verify_input("tx-credit-1", "mock_ok_receipt"))
            .await?;
        assert_eq!(out.status, "verified");
        assert!(out.credited);
        assert_eq!(out.wallet_balance, 60);

        let balance = state.get_wallet_balance(1, 1).await?;
        assert_eq!(balance.balance, 60);

        let ledger = state
            .list_wallet_ledger(
                1,
                1,
                ListWalletLedger {
                    last_id: None,
                    limit: Some(20),
                },
            )
            .await?;
        assert_eq!(ledger.len(), 1);
        assert_eq!(ledger[0].entry_type, "iap_credit");
        assert_eq!(ledger[0].amount_delta, 60);
        Ok(())
    }

    #[tokio::test]
    async fn verify_iap_order_should_be_idempotent_for_same_transaction_id() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let user = state
            .find_user_by_id(1)
            .await?
            .expect("user id 1 should exist");

        let first = state
            .verify_iap_order(&user, verify_input("tx-idempotent-1", "mock_ok_receipt"))
            .await?;
        let second = state
            .verify_iap_order(&user, verify_input("tx-idempotent-1", "mock_ok_receipt"))
            .await?;

        assert_eq!(first.order_id, second.order_id);
        assert!(first.credited);
        assert!(!second.credited);
        assert_eq!(second.wallet_balance, 60);

        let ledger = state
            .list_wallet_ledger(
                1,
                1,
                ListWalletLedger {
                    last_id: None,
                    limit: Some(20),
                },
            )
            .await?;
        assert_eq!(ledger.len(), 1);
        Ok(())
    }

    #[tokio::test]
    async fn verify_iap_order_should_create_rejected_order_without_credit() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let user = state
            .find_user_by_id(1)
            .await?
            .expect("user id 1 should exist");

        let out = state
            .verify_iap_order(&user, verify_input("tx-reject-1", "mock_reject:test"))
            .await?;
        assert_eq!(out.status, "rejected");
        assert!(!out.credited);
        assert_eq!(out.wallet_balance, 0);

        let ledger = state
            .list_wallet_ledger(
                1,
                1,
                ListWalletLedger {
                    last_id: None,
                    limit: Some(20),
                },
            )
            .await?;
        assert!(ledger.is_empty());
        Ok(())
    }

    #[tokio::test]
    async fn verify_iap_order_should_reject_cross_user_transaction_replay() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let user1 = state
            .find_user_by_id(1)
            .await?
            .expect("user id 1 should exist");
        let user2 = state
            .find_user_by_id(2)
            .await?
            .expect("user id 2 should exist");

        state
            .verify_iap_order(&user1, verify_input("tx-replay-1", "mock_ok_receipt"))
            .await?;
        let err = state
            .verify_iap_order(&user2, verify_input("tx-replay-1", "mock_ok_receipt"))
            .await
            .expect_err("cross user replay should fail");
        assert!(matches!(err, AppError::PaymentConflict(_)));
        Ok(())
    }
}
