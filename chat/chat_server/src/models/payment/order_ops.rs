use super::*;
use chrono::Utc;
use serde_json::json;
use sqlx::{Postgres, Transaction};

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
    pub async fn get_iap_order_by_transaction(
        &self,
        user: &User,
        input: GetIapOrderByTransaction,
    ) -> Result<GetIapOrderByTransactionOutput, AppError> {
        validate_identifier(&input.transaction_id, "transaction_id", 128)?;
        let transaction_id = input.transaction_id.trim();
        let row: Option<IapOrderSnapshotRow> = sqlx::query_as(
            r#"
            SELECT
                io.id,
                io.ws_id,
                io.user_id,
                io.product_id,
                io.status,
                io.verify_mode,
                io.verify_reason,
                io.coins,
                EXISTS (
                    SELECT 1
                    FROM wallet_ledger wl
                    WHERE wl.order_id = io.id
                      AND wl.ws_id = io.ws_id
                      AND wl.user_id = io.user_id
                      AND wl.entry_type = 'iap_credit'
                ) AS credited
            FROM iap_orders io
            WHERE io.platform = 'apple_iap'
              AND io.transaction_id = $1
            LIMIT 1
            "#,
        )
        .bind(transaction_id)
        .fetch_optional(&self.pool)
        .await?;

        let Some(row) = row else {
            return Ok(GetIapOrderByTransactionOutput {
                found: false,
                order: None,
            });
        };
        if row.ws_id != user.ws_id || row.user_id != user.id {
            return Err(AppError::PaymentConflict(
                "transaction_id already belongs to another user".to_string(),
            ));
        }

        Ok(GetIapOrderByTransactionOutput {
            found: true,
            order: Some(IapOrderSnapshot {
                order_id: row.id as u64,
                status: row.status,
                verify_mode: row.verify_mode,
                verify_reason: row.verify_reason,
                product_id: row.product_id,
                coins: row.coins,
                credited: row.credited,
            }),
        })
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
        let product_id = input.product_id.trim();
        let transaction_id = input.transaction_id.trim();
        let original_transaction_id = input
            .original_transaction_id
            .as_deref()
            .map(str::trim)
            .filter(|v| !v.is_empty())
            .map(ToString::to_string);
        let receipt = input.receipt_data.trim();

        let Some(product): Option<IapProduct> = sqlx::query_as(
            r#"
            SELECT product_id, coins, is_active
            FROM iap_products
            WHERE product_id = $1
            "#,
        )
        .bind(product_id)
        .fetch_optional(&self.pool)
        .await?
        else {
            return Err(AppError::NotFound(format!("iap product {product_id}")));
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
        .bind(transaction_id)
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

        let verify_result = receipt_verify::verify_receipt(
            &self.config.payment,
            &product.product_id,
            transaction_id,
            original_transaction_id.as_deref(),
            receipt,
        )
        .await?;
        let status = verify_result.status;
        let verify_reason = verify_result.verify_reason;
        let verified_at = if status == "verified" {
            Some(Utc::now())
        } else {
            None
        };
        let verify_mode = verify_result.verify_mode;
        let raw_payload = verify_result.raw_payload;

        let inserted_order: Option<IapOrderRow> = sqlx::query_as(
            r#"
            INSERT INTO iap_orders(
                ws_id, user_id, platform, product_id, transaction_id, original_transaction_id,
                receipt_hash, status, verify_mode, verify_reason, coins, raw_payload, verified_at
            )
            VALUES ($1, $2, 'apple_iap', $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            ON CONFLICT (platform, transaction_id) DO NOTHING
            RETURNING id, ws_id, user_id, product_id, status, verify_mode, verify_reason, coins
            "#,
        )
        .bind(user.ws_id)
        .bind(user.id)
        .bind(&product.product_id)
        .bind(transaction_id)
        .bind(original_transaction_id.clone())
        .bind(hash_receipt(receipt))
        .bind(&status)
        .bind(&verify_mode)
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
            .bind(transaction_id)
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
                "transactionId": transaction_id,
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
