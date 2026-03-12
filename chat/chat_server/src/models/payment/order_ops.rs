use super::{
    helpers, order_flow, receipt_verify,
    types::{IapOrderRow, IapProduct, VerifyIapOrderInput, VerifyIapOrderOutput},
    MAX_RECEIPT_LEN,
};
use crate::{AppError, AppState};
use chat_core::User;
use chrono::Utc;
use sqlx::{Postgres, Transaction};

pub(super) async fn wallet_balance_in_tx(
    tx: &mut Transaction<'_, Postgres>,
    user_id: i64,
) -> Result<i64, AppError> {
    let row: Option<(i64,)> = sqlx::query_as(
        r#"
        SELECT balance
        FROM user_wallets
        WHERE user_id = $1
        "#,
    )
    .bind(user_id)
    .fetch_optional(&mut **tx)
    .await?;
    Ok(row.map(|v| v.0).unwrap_or(0))
}

#[allow(dead_code)]
impl AppState {
    pub async fn verify_iap_order(
        &self,
        user: &User,
        input: VerifyIapOrderInput,
    ) -> Result<VerifyIapOrderOutput, AppError> {
        helpers::validate_identifier(&input.product_id, "product_id", 64)?;
        helpers::validate_identifier(&input.transaction_id, "transaction_id", 128)?;
        if let Some(original) = input.original_transaction_id.as_deref() {
            helpers::validate_identifier(original, "original_transaction_id", 128)?;
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
            SELECT id, user_id, product_id, status, verify_mode, verify_reason, coins
            FROM iap_orders
            WHERE platform = 'apple_iap' AND transaction_id = $1
            "#,
        )
        .bind(transaction_id)
        .fetch_optional(&mut *tx)
        .await?;

        if let Some(order) = existing_order {
            order_flow::validate_order_reuse_constraints(&order, user, &product.product_id)?;
            let wallet_balance = wallet_balance_in_tx(&mut tx, user.id).await?;
            tx.commit().await?;
            return Ok(order_flow::build_order_output_without_credit(
                order,
                wallet_balance,
            ));
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
                user_id, platform, product_id, transaction_id, original_transaction_id,
                receipt_hash, status, verify_mode, verify_reason, coins, raw_payload, verified_at
            )
            VALUES ($1, 'apple_iap', $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (platform, transaction_id) DO NOTHING
            RETURNING id, user_id, product_id, status, verify_mode, verify_reason, coins
            "#,
        )
        .bind(user.id)
        .bind(&product.product_id)
        .bind(transaction_id)
        .bind(original_transaction_id.clone())
        .bind(helpers::hash_receipt(receipt))
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
                SELECT id, user_id, product_id, status, verify_mode, verify_reason, coins
                FROM iap_orders
                WHERE platform = 'apple_iap' AND transaction_id = $1
                "#,
            )
            .bind(transaction_id)
            .fetch_one(&mut *tx)
            .await?;
            order_flow::validate_order_reuse_constraints(&order, user, &product.product_id)?;
            let wallet_balance = wallet_balance_in_tx(&mut tx, user.id).await?;
            tx.commit().await?;
            return Ok(order_flow::build_order_output_without_credit(
                order,
                wallet_balance,
            ));
        };

        let (credited, wallet_balance) = order_flow::apply_wallet_credit_for_verified_order(
            &mut tx,
            user,
            &inserted_order,
            transaction_id,
        )
        .await?;

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
