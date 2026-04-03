use super::{
    helpers,
    types::{
        GetIapOrderByTransaction, GetIapOrderByTransactionOutput, IapOrderProbeStatus,
        IapOrderSnapshot, IapOrderSnapshotRow, IapProduct, IapProductsEmptyReason, ListIapProducts,
        ListIapProductsOutput, ListWalletLedger, WalletBalanceOutput, WalletLedgerItem,
        WalletLedgerListOutput,
    },
};
use crate::{AppError, AppState};
use chat_core::User;
use chrono::{DateTime, SecondsFormat, Utc};
use std::{collections::HashMap, sync::LazyLock};
use tokio::sync::RwLock;

const IAP_PRODUCTS_CACHE_TTL_SECS: i64 = 10;
const IAP_ORDER_PROBE_CACHE_TTL_SECS: i64 = 5;
const IAP_ORDER_PROBE_NOT_FOUND_RETRY_AFTER_MS: u64 = 1_200;
const IAP_ORDER_PROBE_PENDING_RETRY_AFTER_MS: u64 = 800;
const WALLET_BALANCE_CACHE_TTL_MS: i64 = 200;
const WALLET_BALANCE_UNINITIALIZED_REVISION: &str = "uninitialized";

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
struct IapProductsCacheKey {
    db_scope_hash: String,
    active_only: bool,
}

#[derive(Debug, Clone)]
struct IapProductsCacheEntry {
    expires_at_epoch_secs: i64,
    revision: Option<String>,
    output: ListIapProductsOutput,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
struct IapOrderProbeCacheKey {
    db_scope_hash: String,
    user_id: i64,
    transaction_id: String,
}

#[derive(Debug, Clone)]
struct IapOrderProbeCacheEntry {
    expires_at_epoch_secs: i64,
    output: GetIapOrderByTransactionOutput,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
struct WalletBalanceCacheKey {
    db_scope_hash: String,
    user_id: i64,
}

#[derive(Debug, Clone)]
struct WalletBalanceCacheEntry {
    expires_at_epoch_ms: i64,
    output: WalletBalanceOutput,
}

static IAP_PRODUCTS_LIST_CACHE: LazyLock<
    RwLock<HashMap<IapProductsCacheKey, IapProductsCacheEntry>>,
> = LazyLock::new(|| RwLock::new(HashMap::new()));

static IAP_ORDER_PROBE_CACHE: LazyLock<
    RwLock<HashMap<IapOrderProbeCacheKey, IapOrderProbeCacheEntry>>,
> = LazyLock::new(|| RwLock::new(HashMap::new()));

static WALLET_BALANCE_CACHE: LazyLock<
    RwLock<HashMap<WalletBalanceCacheKey, WalletBalanceCacheEntry>>,
> = LazyLock::new(|| RwLock::new(HashMap::new()));

pub(crate) async fn invalidate_iap_order_probe_cache_for_transaction(
    db_url: &str,
    transaction_id: &str,
) {
    let db_scope_hash = hash_cache_scope(db_url);
    let mut cache = IAP_ORDER_PROBE_CACHE.write().await;
    cache.retain(|key, _| {
        !(key.db_scope_hash == db_scope_hash && key.transaction_id == transaction_id)
    });
}

#[allow(dead_code)]
impl AppState {
    pub async fn list_iap_products(
        &self,
        input: ListIapProducts,
    ) -> Result<ListIapProductsOutput, AppError> {
        let (output, _) = self.list_iap_products_with_cache(input).await?;
        Ok(output)
    }

    pub(crate) async fn list_iap_products_with_cache(
        &self,
        input: ListIapProducts,
    ) -> Result<(ListIapProductsOutput, bool), AppError> {
        let revision = query_iap_products_revision(&self.pool)
            .await?
            .map(format_iap_products_revision);
        let cache_key = IapProductsCacheKey {
            db_scope_hash: hash_cache_scope(&self.config.server.db_url),
            active_only: input.active_only,
        };
        let now_epoch = Utc::now().timestamp();
        if let Some(entry) = IAP_PRODUCTS_LIST_CACHE.read().await.get(&cache_key) {
            if entry.expires_at_epoch_secs > now_epoch && entry.revision == revision {
                return Ok((entry.output.clone(), true));
            }
        }

        let rows: Vec<IapProduct> = sqlx::query_as(
            r#"
            SELECT product_id, coins, is_active
            FROM iap_products
            WHERE (NOT $1::boolean OR is_active = TRUE)
            ORDER BY coins ASC, product_id ASC
            "#,
        )
        .bind(input.active_only)
        .fetch_all(&self.pool)
        .await?;

        let empty_reason = if rows.is_empty() {
            if input.active_only {
                let total_count: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM iap_products")
                    .fetch_one(&self.pool)
                    .await?;
                if total_count > 0 {
                    Some(IapProductsEmptyReason::AllInactive)
                } else {
                    Some(IapProductsEmptyReason::NoConfig)
                }
            } else {
                Some(IapProductsEmptyReason::NoConfig)
            }
        } else {
            None
        };
        let output = ListIapProductsOutput {
            items: rows,
            revision: revision.clone(),
            empty_reason,
        };
        IAP_PRODUCTS_LIST_CACHE.write().await.insert(
            cache_key,
            IapProductsCacheEntry {
                expires_at_epoch_secs: now_epoch + IAP_PRODUCTS_CACHE_TTL_SECS,
                revision,
                output: output.clone(),
            },
        );
        Ok((output, false))
    }

    pub async fn get_iap_order_by_transaction(
        &self,
        user: &User,
        input: GetIapOrderByTransaction,
    ) -> Result<GetIapOrderByTransactionOutput, AppError> {
        let (ret, _) = self
            .get_iap_order_by_transaction_with_probe_cache(user, input)
            .await?;
        Ok(ret)
    }

    pub(crate) async fn get_iap_order_by_transaction_with_probe_cache(
        &self,
        user: &User,
        input: GetIapOrderByTransaction,
    ) -> Result<(GetIapOrderByTransactionOutput, bool), AppError> {
        helpers::validate_identifier(&input.transaction_id, "transaction_id", 128)?;
        let transaction_id = input.transaction_id.trim();
        let cache_key = IapOrderProbeCacheKey {
            db_scope_hash: hash_cache_scope(&self.config.server.db_url),
            user_id: user.id,
            transaction_id: transaction_id.to_string(),
        };
        let now_epoch = Utc::now().timestamp();
        if let Some(entry) = IAP_ORDER_PROBE_CACHE.read().await.get(&cache_key) {
            if entry.expires_at_epoch_secs > now_epoch {
                return Ok((entry.output.clone(), true));
            }
        }

        let row: Option<IapOrderSnapshotRow> = sqlx::query_as(
            r#"
            SELECT
                io.id,
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
            let output = GetIapOrderByTransactionOutput {
                found: false,
                order: None,
                probe_status: Some(IapOrderProbeStatus::NotFound),
                next_retry_after_ms: Some(IAP_ORDER_PROBE_NOT_FOUND_RETRY_AFTER_MS),
            };
            IAP_ORDER_PROBE_CACHE.write().await.insert(
                cache_key,
                IapOrderProbeCacheEntry {
                    expires_at_epoch_secs: now_epoch + IAP_ORDER_PROBE_CACHE_TTL_SECS,
                    output: output.clone(),
                },
            );
            return Ok((output, false));
        };
        if row.user_id != user.id {
            return Err(AppError::PaymentConflict(
                "transaction_id already belongs to another user".to_string(),
            ));
        }

        let probe_status = if row.credited {
            IapOrderProbeStatus::VerifiedCredited
        } else {
            IapOrderProbeStatus::PendingCredit
        };
        let next_retry_after_ms = if row.credited || row.status.eq_ignore_ascii_case("rejected") {
            None
        } else {
            Some(IAP_ORDER_PROBE_PENDING_RETRY_AFTER_MS)
        };
        let output = GetIapOrderByTransactionOutput {
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
            probe_status: Some(probe_status),
            next_retry_after_ms,
        };

        let can_cache = !matches!(
            output.probe_status,
            Some(IapOrderProbeStatus::PendingCredit)
        ) || output
            .order
            .as_ref()
            .map(|order| order.status.eq_ignore_ascii_case("rejected"))
            .unwrap_or(false);
        if can_cache {
            IAP_ORDER_PROBE_CACHE.write().await.insert(
                cache_key,
                IapOrderProbeCacheEntry {
                    expires_at_epoch_secs: now_epoch + IAP_ORDER_PROBE_CACHE_TTL_SECS,
                    output: output.clone(),
                },
            );
        }
        Ok((output, false))
    }

    pub async fn get_wallet_balance(&self, user_id: u64) -> Result<WalletBalanceOutput, AppError> {
        let (output, _) = self.get_wallet_balance_with_cache(user_id).await?;
        Ok(output)
    }

    pub(crate) async fn get_wallet_balance_with_cache(
        &self,
        user_id: u64,
    ) -> Result<(WalletBalanceOutput, bool), AppError> {
        let cache_enabled = !cfg!(test);
        let cache_key = WalletBalanceCacheKey {
            db_scope_hash: hash_cache_scope(&self.config.server.db_url),
            user_id: user_id as i64,
        };
        let now_epoch_ms = Utc::now().timestamp_millis();
        if cache_enabled {
            if let Some(entry) = WALLET_BALANCE_CACHE.read().await.get(&cache_key) {
                if entry.expires_at_epoch_ms > now_epoch_ms {
                    return Ok((entry.output.clone(), true));
                }
            }
        }

        let row: Option<(i64, DateTime<Utc>)> = sqlx::query_as(
            r#"
            SELECT balance, updated_at
            FROM user_wallets
            WHERE user_id = $1
            "#,
        )
        .bind(user_id as i64)
        .fetch_optional(&self.pool)
        .await?;

        let output = if let Some((balance, updated_at)) = row {
            WalletBalanceOutput {
                user_id,
                balance,
                wallet_revision: updated_at.to_rfc3339_opts(SecondsFormat::Millis, true),
                wallet_initialized: true,
            }
        } else {
            WalletBalanceOutput {
                user_id,
                balance: 0,
                wallet_revision: WALLET_BALANCE_UNINITIALIZED_REVISION.to_string(),
                wallet_initialized: false,
            }
        };

        if cache_enabled {
            WALLET_BALANCE_CACHE.write().await.insert(
                cache_key,
                WalletBalanceCacheEntry {
                    expires_at_epoch_ms: now_epoch_ms + WALLET_BALANCE_CACHE_TTL_MS,
                    output: output.clone(),
                },
            );
        }
        Ok((output, false))
    }

    pub(crate) async fn invalidate_wallet_balance_cache(&self, user_id: u64) {
        let cache_key = WalletBalanceCacheKey {
            db_scope_hash: hash_cache_scope(&self.config.server.db_url),
            user_id: user_id as i64,
        };
        WALLET_BALANCE_CACHE.write().await.remove(&cache_key);
    }

    pub(crate) async fn reconcile_wallet_balance_once(
        &self,
        sample_limit: usize,
    ) -> Result<(u64, u64, u64), AppError> {
        let compared_users: i64 = sqlx::query_scalar(
            r#"
            WITH users_union AS (
                SELECT user_id FROM user_wallets
                UNION
                SELECT user_id FROM wallet_ledger
            )
            SELECT COUNT(1)::bigint FROM users_union
            "#,
        )
        .fetch_one(&self.pool)
        .await?;

        let mismatch_users: i64 = sqlx::query_scalar(
            r#"
            WITH wallet AS (
                SELECT user_id, balance
                FROM user_wallets
            ),
            ledger AS (
                SELECT user_id, COALESCE(SUM(amount_delta), 0)::bigint AS ledger_balance
                FROM wallet_ledger
                GROUP BY user_id
            )
            SELECT COUNT(1)::bigint
            FROM (
                SELECT
                    COALESCE(wallet.user_id, ledger.user_id) AS user_id,
                    COALESCE(wallet.balance, 0)::bigint AS wallet_balance,
                    COALESCE(ledger.ledger_balance, 0)::bigint AS ledger_balance
                FROM wallet
                FULL OUTER JOIN ledger USING (user_id)
            ) joined
            WHERE joined.wallet_balance <> joined.ledger_balance
            "#,
        )
        .fetch_one(&self.pool)
        .await?;

        let sampled_rows: i64 = sqlx::query_scalar(
            r#"
            WITH wallet AS (
                SELECT user_id, balance, updated_at
                FROM user_wallets
            ),
            ledger AS (
                SELECT
                    user_id,
                    COALESCE(SUM(amount_delta), 0)::bigint AS ledger_balance,
                    MAX(created_at) AS ledger_latest_at
                FROM wallet_ledger
                GROUP BY user_id
            ),
            mismatches AS (
                SELECT
                    COALESCE(wallet.user_id, ledger.user_id) AS user_id,
                    COALESCE(wallet.balance, 0)::bigint AS wallet_balance,
                    COALESCE(ledger.ledger_balance, 0)::bigint AS ledger_balance,
                    wallet.updated_at AS wallet_updated_at,
                    ledger.ledger_latest_at AS ledger_latest_at
                FROM wallet
                FULL OUTER JOIN ledger USING (user_id)
                WHERE COALESCE(wallet.balance, 0)::bigint <> COALESCE(ledger.ledger_balance, 0)::bigint
                ORDER BY COALESCE(wallet.user_id, ledger.user_id) ASC
                LIMIT $1
            ),
            inserted AS (
                INSERT INTO wallet_balance_reconcile_audits(
                    user_id,
                    wallet_balance,
                    ledger_balance,
                    wallet_updated_at,
                    ledger_latest_at,
                    detected_at
                )
                SELECT
                    user_id,
                    wallet_balance,
                    ledger_balance,
                    wallet_updated_at,
                    ledger_latest_at,
                    NOW()
                FROM mismatches
                RETURNING 1
            )
            SELECT COUNT(1)::bigint FROM inserted
            "#,
        )
        .bind(sample_limit as i64)
        .fetch_one(&self.pool)
        .await?;

        Ok((
            compared_users.max(0) as u64,
            mismatch_users.max(0) as u64,
            sampled_rows.max(0) as u64,
        ))
    }

    pub async fn list_wallet_ledger(
        &self,
        user_id: u64,
        input: ListWalletLedger,
    ) -> Result<WalletLedgerListOutput, AppError> {
        let limit = helpers::normalize_limit(input.limit);
        let query_limit = limit.saturating_add(1);
        let last_id = match input.last_id {
            Some(v) => Some(
                i64::try_from(v)
                    .map_err(|_| AppError::PaymentError("last_id exceeds i64::MAX".to_string()))?,
            ),
            None => None,
        };
        let mut items: Vec<WalletLedgerItem> = sqlx::query_as(
            r#"
            SELECT
                id,
                order_id,
                entry_type,
                amount_delta,
                balance_after,
                idempotency_key,
                metadata,
                created_at
            FROM wallet_ledger
            WHERE user_id = $1
              AND ($2::bigint IS NULL OR id < $2)
            ORDER BY id DESC
            LIMIT $3
            "#,
        )
        .bind(user_id as i64)
        .bind(last_id)
        .bind(query_limit)
        .fetch_all(&self.pool)
        .await?;
        let has_more = items.len() > limit as usize;
        if has_more {
            items.truncate(limit as usize);
        }
        let next_last_id = if has_more {
            items.last().and_then(|item| u64::try_from(item.id).ok())
        } else {
            None
        };
        Ok(WalletLedgerListOutput {
            items,
            next_last_id,
            has_more,
        })
    }
}

async fn query_iap_products_revision(
    pool: &sqlx::PgPool,
) -> Result<Option<DateTime<Utc>>, AppError> {
    let revision: Option<DateTime<Utc>> =
        sqlx::query_scalar("SELECT MAX(updated_at) FROM iap_products")
            .fetch_one(pool)
            .await?;
    Ok(revision)
}

fn format_iap_products_revision(value: DateTime<Utc>) -> String {
    value.to_rfc3339_opts(SecondsFormat::Millis, true)
}

fn hash_cache_scope(input: &str) -> String {
    use sha1::{Digest, Sha1};
    let mut hasher = Sha1::new();
    hasher.update(input.as_bytes());
    hex::encode(hasher.finalize())
}
