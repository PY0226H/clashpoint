use super::*;

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

    pub async fn get_iap_order_by_transaction(
        &self,
        user: &User,
        input: GetIapOrderByTransaction,
    ) -> Result<GetIapOrderByTransactionOutput, AppError> {
        super::helpers::validate_identifier(&input.transaction_id, "transaction_id", 128)?;
        let transaction_id = input.transaction_id.trim();
        let row: Option<super::types::IapOrderSnapshotRow> = sqlx::query_as(
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
        .bind(super::helpers::normalize_limit(input.limit))
        .fetch_all(&self.pool)
        .await?;

        Ok(rows)
    }
}
