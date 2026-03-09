use super::{
    order_ops,
    types::{IapOrderRow, VerifyIapOrderOutput},
};
use crate::AppError;
use chat_core::User;
use serde_json::json;
use sqlx::{Postgres, Transaction};

pub(super) fn validate_order_reuse_constraints(
    order: &IapOrderRow,
    user: &User,
    product_id: &str,
) -> Result<(), AppError> {
    if order.ws_id != user.ws_id || order.user_id != user.id {
        return Err(AppError::PaymentConflict(
            "transaction_id already belongs to another user".to_string(),
        ));
    }
    if order.product_id != product_id {
        return Err(AppError::PaymentConflict(
            "transaction_id already used with another product".to_string(),
        ));
    }
    Ok(())
}

pub(super) fn build_order_output_without_credit(
    order: IapOrderRow,
    wallet_balance: i64,
) -> VerifyIapOrderOutput {
    VerifyIapOrderOutput {
        order_id: order.id as u64,
        status: order.status,
        verify_mode: order.verify_mode,
        verify_reason: order.verify_reason,
        product_id: order.product_id,
        coins: order.coins,
        credited: false,
        wallet_balance,
    }
}

pub(super) async fn apply_wallet_credit_for_verified_order(
    tx: &mut Transaction<'_, Postgres>,
    user: &User,
    inserted_order: &IapOrderRow,
    transaction_id: &str,
) -> Result<(bool, i64), AppError> {
    if inserted_order.status != "verified" {
        let balance = order_ops::wallet_balance_in_tx(tx, user.ws_id, user.id).await?;
        return Ok((false, balance));
    }

    sqlx::query(
        r#"
        INSERT INTO user_wallets(ws_id, user_id, balance)
        VALUES ($1, $2, 0)
        ON CONFLICT (ws_id, user_id) DO NOTHING
        "#,
    )
    .bind(user.ws_id)
    .bind(user.id)
    .execute(&mut **tx)
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
    .fetch_one(&mut **tx)
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
    .execute(&mut **tx)
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
    .execute(&mut **tx)
    .await?;

    Ok((true, next_balance))
}
