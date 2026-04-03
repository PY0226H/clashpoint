use super::receipt_verify::{
    extract_receipt_records, is_retryable_apple_status, normalize_verify_mode,
    select_matching_record, verify_receipt, ReceiptRecord, ReceiptVerifyResult,
};
use super::types::{
    GetIapOrderByTransaction, GetIapOrderByTransactionOutput, IapOrderProbeStatus,
    IapProductsEmptyReason, ListIapProducts, ListWalletLedger, VerifyIapOrderInput,
    VerifyIapOrderOutput, WalletLedgerItem,
};
use crate::config::PaymentConfig;
use crate::{AppError, AppState};
use anyhow::{anyhow, Result};
use axum::{
    extract::{OriginalUri, State},
    routing::post,
    Json, Router,
};
use chat_core::User;
use serde_json::{json, Value};
use std::sync::{
    atomic::{AtomicUsize, Ordering},
    Arc,
};
use tokio::{net::TcpListener, sync::Mutex};

#[derive(Clone)]
struct AppleVerifyStubState {
    responses: Arc<Vec<Value>>,
    cursor: Arc<AtomicUsize>,
    requests: Arc<Mutex<Vec<(String, Value)>>>,
}

async fn apple_verify_stub_handler(
    State(state): State<AppleVerifyStubState>,
    uri: OriginalUri,
    Json(payload): Json<Value>,
) -> Json<Value> {
    state
        .requests
        .lock()
        .await
        .push((uri.path().to_string(), payload));
    let idx = state.cursor.fetch_add(1, Ordering::SeqCst);
    let response = state
        .responses
        .get(idx)
        .cloned()
        .or_else(|| state.responses.last().cloned())
        .unwrap_or_else(|| json!({ "status": 0 }));
    Json(response)
}

async fn start_apple_verify_stub(
    responses: Vec<Value>,
) -> Result<(
    PaymentConfig,
    Arc<Mutex<Vec<(String, Value)>>>,
    tokio::task::JoinHandle<()>,
)> {
    let requests = Arc::new(Mutex::new(Vec::new()));
    let app = Router::new()
        .route("/prod", post(apple_verify_stub_handler))
        .route("/sandbox", post(apple_verify_stub_handler))
        .with_state(AppleVerifyStubState {
            responses: Arc::new(responses),
            cursor: Arc::new(AtomicUsize::new(0)),
            requests: requests.clone(),
        });

    let listener = TcpListener::bind("127.0.0.1:0").await?;
    let addr = listener.local_addr()?;
    let server = tokio::spawn(async move {
        axum::serve(listener, app)
            .await
            .expect("apple verify stub should run");
    });

    let config = PaymentConfig {
        verify_mode: "apple".to_string(),
        apple_verify_url_prod: format!("http://{addr}/prod"),
        apple_verify_url_sandbox: format!("http://{addr}/sandbox"),
        apple_shared_secret: "test-shared-secret".to_string(),
        verify_timeout_ms: 3_000,
    };
    Ok((config, requests, server))
}

fn verify_input(tx: &str, receipt_data: &str) -> VerifyIapOrderInput {
    VerifyIapOrderInput {
        product_id: "com.echoisle.coins.60".to_string(),
        transaction_id: tx.to_string(),
        original_transaction_id: None,
        receipt_data: receipt_data.to_string(),
    }
}

async fn load_user(state: &AppState, user_id: i64) -> Result<User> {
    state
        .find_user_by_id(user_id)
        .await?
        .ok_or_else(|| anyhow!("user id {user_id} should exist"))
}

async fn load_two_users(state: &AppState, user1_id: i64, user2_id: i64) -> Result<(User, User)> {
    let user1 = load_user(state, user1_id).await?;
    let user2 = load_user(state, user2_id).await?;
    Ok((user1, user2))
}

async fn query_wallet_ledger(state: &AppState, user_id: u64) -> Result<Vec<WalletLedgerItem>> {
    let output = state
        .list_wallet_ledger(
            user_id,
            ListWalletLedger {
                last_id: None,
                limit: Some(20),
            },
        )
        .await
        .map_err(anyhow::Error::from)?;
    Ok(output.items)
}

async fn query_order_snapshot(
    state: &AppState,
    user: &User,
    transaction_id: &str,
) -> Result<GetIapOrderByTransactionOutput> {
    state
        .get_iap_order_by_transaction(
            user,
            GetIapOrderByTransaction {
                transaction_id: transaction_id.to_string(),
            },
        )
        .await
        .map_err(Into::into)
}

async fn query_order_snapshot_expect_conflict(
    state: &AppState,
    user: &User,
    transaction_id: &str,
) -> AppError {
    state
        .get_iap_order_by_transaction(
            user,
            GetIapOrderByTransaction {
                transaction_id: transaction_id.to_string(),
            },
        )
        .await
        .expect_err("cross user query should fail")
}

fn assert_order_output(
    out: &VerifyIapOrderOutput,
    expected_status: &str,
    expected_verify_mode: &str,
    expected_credited: bool,
    expected_wallet_balance: i64,
) {
    assert_eq!(out.status, expected_status);
    assert_eq!(out.verify_mode, expected_verify_mode);
    assert_eq!(out.credited, expected_credited);
    assert_eq!(out.wallet_balance, expected_wallet_balance);
}

fn assert_single_credit_ledger_entry(ledger: &[WalletLedgerItem], expected_delta: i64) {
    assert_eq!(ledger.len(), 1);
    assert_eq!(ledger[0].entry_type, "iap_credit");
    assert_eq!(ledger[0].amount_delta, expected_delta);
}

fn assert_verify_receipt_output(
    out: &ReceiptVerifyResult,
    expected_status: &str,
    expected_verify_mode: &str,
    expected_verify_reason: Option<&str>,
) {
    assert_eq!(out.status, expected_status);
    assert_eq!(out.verify_mode, expected_verify_mode);
    assert_eq!(out.verify_reason.as_deref(), expected_verify_reason);
}

fn assert_request_paths(requests: &[(String, Value)], expected_paths: &[&str]) {
    assert_eq!(requests.len(), expected_paths.len());
    for (request, expected_path) in requests.iter().zip(expected_paths) {
        assert_eq!(request.0, *expected_path);
    }
}

fn assert_apple_verify_request_payload(payload: &Value, expected_receipt_data: &str) {
    assert_eq!(
        payload.get("receipt-data").and_then(Value::as_str),
        Some(expected_receipt_data)
    );
    assert_eq!(
        payload.get("password").and_then(Value::as_str),
        Some("test-shared-secret")
    );
    assert_eq!(
        payload
            .get("exclude-old-transactions")
            .and_then(Value::as_bool),
        Some(true)
    );
}

fn assert_raw_payload_endpoint(payload: &Value, expected_endpoint: &str) {
    assert_eq!(
        payload.get("endpoint").and_then(Value::as_str),
        Some(expected_endpoint)
    );
}

fn assert_raw_payload_status_code(payload: &Value, expected_status_code: i64) {
    assert_eq!(
        payload.get("statusCode").and_then(Value::as_i64),
        Some(expected_status_code)
    );
}

fn assert_raw_payload_matched_transaction(payload: &Value, expected_matched: bool) {
    assert_eq!(
        payload.get("matchedTransaction").and_then(Value::as_bool),
        Some(expected_matched)
    );
}

async fn assert_stub_request_paths(
    requests: &Arc<Mutex<Vec<(String, Value)>>>,
    expected_paths: &[&str],
) {
    let requests = requests.lock().await;
    assert_request_paths(&requests, expected_paths);
}

async fn assert_single_prod_request_with_payload(
    requests: &Arc<Mutex<Vec<(String, Value)>>>,
    expected_receipt_data: &str,
) {
    let requests = requests.lock().await;
    assert_request_paths(&requests, &["/prod"]);
    assert_apple_verify_request_payload(&requests[0].1, expected_receipt_data);
}

fn assert_order_query_not_found(out: &GetIapOrderByTransactionOutput) {
    assert!(!out.found);
    assert!(out.order.is_none());
    assert_eq!(out.probe_status, Some(IapOrderProbeStatus::NotFound));
    assert!(out.next_retry_after_ms.is_some());
}

fn assert_order_query_verified(out: &GetIapOrderByTransactionOutput, expected_product_id: &str) {
    assert!(out.found);
    let order = out.order.as_ref().expect("order should exist");
    assert_eq!(order.status, "verified");
    assert_eq!(order.product_id, expected_product_id);
    assert!(order.credited);
    assert_eq!(
        out.probe_status,
        Some(IapOrderProbeStatus::VerifiedCredited)
    );
    assert!(out.next_retry_after_ms.is_none());
}

fn assert_payment_conflict(err: &AppError) {
    assert!(matches!(err, AppError::PaymentConflict(_)));
}

fn assert_retryable_payment_error_contains(err: &AppError, status_code: i64) {
    assert!(matches!(err, AppError::PaymentError(_)));
    assert!(err
        .to_string()
        .contains(format!("transient status {status_code}").as_str()));
}

#[test]
fn extract_receipt_records_should_collect_both_paths() {
    let payload = json!({
        "latest_receipt_info": [
            {
                "transaction_id": "tx-1",
                "original_transaction_id": "otx-1",
                "product_id": "com.echoisle.coins.60"
            }
        ],
        "receipt": {
            "in_app": [
                {
                    "transaction_id": "tx-2",
                    "original_transaction_id": "otx-2",
                    "product_id": "com.echoisle.coins.120"
                }
            ]
        }
    });

    let records = extract_receipt_records(&payload);
    assert_eq!(records.len(), 2);
    assert_eq!(records[0].transaction_id, "tx-1");
    assert_eq!(records[1].transaction_id, "tx-2");
}

#[test]
fn select_matching_record_should_match_transaction_original_and_product() {
    let records = vec![
        ReceiptRecord {
            transaction_id: "tx-a".to_string(),
            original_transaction_id: Some("otx-a".to_string()),
            product_id: Some("com.echoisle.coins.60".to_string()),
        },
        ReceiptRecord {
            transaction_id: "tx-b".to_string(),
            original_transaction_id: None,
            product_id: Some("com.echoisle.coins.120".to_string()),
        },
    ];

    let matched = select_matching_record(&records, "com.echoisle.coins.60", "tx-a", Some("otx-a"));
    assert!(matched.is_some());

    let not_matched =
        select_matching_record(&records, "com.echoisle.coins.60", "tx-b", Some("otx-b"));
    assert!(not_matched.is_none());
}

#[test]
fn normalize_verify_mode_should_default_to_apple() {
    assert_eq!(normalize_verify_mode("apple"), "apple");
    assert_eq!(normalize_verify_mode(" production "), "apple");
    assert_eq!(normalize_verify_mode("mock"), "mock");
    assert_eq!(normalize_verify_mode(""), "apple");
    assert_eq!(normalize_verify_mode("unknown"), "apple");
}

#[test]
fn is_retryable_apple_status_should_match_transient_codes() {
    assert!(is_retryable_apple_status(21005));
    assert!(is_retryable_apple_status(21009));
    assert!(is_retryable_apple_status(21100));
    assert!(is_retryable_apple_status(21199));
    assert!(!is_retryable_apple_status(0));
    assert!(!is_retryable_apple_status(21003));
}

#[tokio::test]
async fn verify_receipt_should_use_apple_production_and_mark_verified() -> Result<()> {
    let (config, requests, server) = start_apple_verify_stub(vec![json!({
        "status": 0,
        "environment": "Production",
        "latest_receipt_info": [
            {
                "transaction_id": "tx-apple-ok-1",
                "product_id": "com.echoisle.coins.60"
            }
        ]
    })])
    .await?;

    let out = verify_receipt(
        &config,
        "com.echoisle.coins.60",
        "tx-apple-ok-1",
        None,
        "receipt_ok_1",
    )
    .await?;

    assert_verify_receipt_output(&out, "verified", "apple", None);
    assert_raw_payload_endpoint(&out.raw_payload, "production");
    assert_raw_payload_matched_transaction(&out.raw_payload, true);

    assert_single_prod_request_with_payload(&requests, "receipt_ok_1").await;
    server.abort();
    Ok(())
}

#[tokio::test]
async fn verify_receipt_should_fallback_to_sandbox_when_prod_returns_21007() -> Result<()> {
    let (config, requests, server) = start_apple_verify_stub(vec![
        json!({
            "status": 21007,
            "environment": "Production"
        }),
        json!({
            "status": 0,
            "environment": "Sandbox",
            "receipt": {
                "in_app": [
                    {
                        "transaction_id": "tx-apple-21007-1",
                        "product_id": "com.echoisle.coins.60"
                    }
                ]
            }
        }),
    ])
    .await?;

    let out = verify_receipt(
        &config,
        "com.echoisle.coins.60",
        "tx-apple-21007-1",
        None,
        "receipt_21007_1",
    )
    .await?;

    assert_verify_receipt_output(&out, "verified", "apple", None);
    assert_raw_payload_endpoint(&out.raw_payload, "sandbox");
    assert_raw_payload_status_code(&out.raw_payload, 0);

    assert_stub_request_paths(&requests, &["/prod", "/sandbox"]).await;
    server.abort();
    Ok(())
}

#[tokio::test]
async fn verify_receipt_should_return_error_for_retryable_apple_status() -> Result<()> {
    let (config, requests, server) = start_apple_verify_stub(vec![json!({
        "status": 21005,
        "environment": "Production"
    })])
    .await?;

    let err = verify_receipt(
        &config,
        "com.echoisle.coins.60",
        "tx-apple-retryable-1",
        None,
        "receipt_retryable_1",
    )
    .await
    .expect_err("retryable status should return error");

    assert_retryable_payment_error_contains(&err, 21005);

    assert_stub_request_paths(&requests, &["/prod"]).await;
    server.abort();
    Ok(())
}

#[tokio::test]
async fn verify_receipt_should_reject_when_transaction_not_found_in_apple_payload() -> Result<()> {
    let (config, requests, server) = start_apple_verify_stub(vec![json!({
        "status": 0,
        "environment": "Production",
        "latest_receipt_info": [
            {
                "transaction_id": "tx-other",
                "product_id": "com.echoisle.coins.120"
            }
        ]
    })])
    .await?;

    let out = verify_receipt(
        &config,
        "com.echoisle.coins.60",
        "tx-apple-miss-1",
        None,
        "receipt_miss_1",
    )
    .await?;

    assert_verify_receipt_output(
        &out,
        "rejected",
        "apple",
        Some("transaction/product not found in apple receipt"),
    );
    assert_raw_payload_matched_transaction(&out.raw_payload, false);

    assert_stub_request_paths(&requests, &["/prod"]).await;
    server.abort();
    Ok(())
}

#[tokio::test]
async fn list_iap_products_should_return_seed_data() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let output = state
        .list_iap_products(ListIapProducts { active_only: true })
        .await?;
    assert!(output.items.len() >= 3);
    assert_eq!(output.items[0].coins, 60);
    assert!(output.revision.is_some());
    assert!(output.empty_reason.is_none());
    Ok(())
}

#[tokio::test]
async fn list_iap_products_should_stably_sort_by_coins_then_product_id() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    sqlx::query(
        r#"
        INSERT INTO iap_products (product_id, coins, is_active, created_at, updated_at)
        VALUES
            ('com.echoisle.coins.060.a', 60, true, NOW(), NOW()),
            ('com.echoisle.coins.060.z', 60, true, NOW(), NOW())
        ON CONFLICT (product_id) DO UPDATE
        SET coins = EXCLUDED.coins,
            is_active = EXCLUDED.is_active,
            updated_at = NOW()
        "#,
    )
    .execute(&state.pool)
    .await?;

    let output = state
        .list_iap_products(ListIapProducts { active_only: true })
        .await?;
    let first_three = output
        .items
        .iter()
        .filter(|item| item.coins == 60)
        .take(3)
        .map(|item| item.product_id.as_str())
        .collect::<Vec<_>>();
    assert_eq!(
        first_three,
        vec![
            "com.echoisle.coins.060.a",
            "com.echoisle.coins.060.z",
            "com.echoisle.coins.60"
        ]
    );
    Ok(())
}

#[tokio::test]
async fn list_iap_products_should_return_empty_reason_all_inactive() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    sqlx::query("UPDATE iap_products SET is_active = FALSE, updated_at = NOW()")
        .execute(&state.pool)
        .await?;

    let output = state
        .list_iap_products(ListIapProducts { active_only: true })
        .await?;
    assert!(output.items.is_empty());
    assert_eq!(
        output.empty_reason,
        Some(IapProductsEmptyReason::AllInactive)
    );
    assert!(output.revision.is_some());
    Ok(())
}

#[tokio::test]
async fn list_iap_products_should_return_empty_reason_no_config() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    sqlx::query("DELETE FROM iap_products")
        .execute(&state.pool)
        .await?;

    let output = state
        .list_iap_products(ListIapProducts { active_only: false })
        .await?;
    assert!(output.items.is_empty());
    assert_eq!(output.empty_reason, Some(IapProductsEmptyReason::NoConfig));
    Ok(())
}

#[tokio::test]
async fn verify_iap_order_should_credit_wallet_and_create_ledger() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let user = load_user(&state, 1).await?;

    let out = state
        .verify_iap_order(&user, verify_input("tx-credit-1", "mock_ok_receipt"))
        .await?;
    assert_order_output(&out, "verified", "mock", true, 60);

    let balance = state.get_wallet_balance(1).await?;
    assert_eq!(balance.balance, 60);
    assert!(balance.wallet_initialized);
    assert_ne!(balance.wallet_revision, "uninitialized");

    let ledger = query_wallet_ledger(&state, 1).await?;
    assert_single_credit_ledger_entry(&ledger, 60);
    Ok(())
}

#[tokio::test]
async fn get_wallet_balance_should_mark_uninitialized_wallet() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let balance = state.get_wallet_balance(998_001).await?;
    assert_eq!(balance.balance, 0);
    assert!(!balance.wallet_initialized);
    assert_eq!(balance.wallet_revision, "uninitialized");
    Ok(())
}

#[tokio::test]
async fn verify_iap_order_should_be_idempotent_for_same_transaction_id() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let user = load_user(&state, 1).await?;

    let first = state
        .verify_iap_order(&user, verify_input("tx-idempotent-1", "mock_ok_receipt"))
        .await?;
    let second = state
        .verify_iap_order(&user, verify_input("tx-idempotent-1", "mock_ok_receipt"))
        .await?;

    assert_order_output(&first, "verified", "mock", true, 60);
    assert_order_output(&second, "verified", "mock", false, 60);
    assert_eq!(first.order_id, second.order_id);

    let ledger = query_wallet_ledger(&state, 1).await?;
    assert_single_credit_ledger_entry(&ledger, 60);
    Ok(())
}

#[tokio::test]
async fn verify_iap_order_should_create_rejected_order_without_credit() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let user = load_user(&state, 1).await?;

    let out = state
        .verify_iap_order(&user, verify_input("tx-reject-1", "mock_reject:test"))
        .await?;
    assert_order_output(&out, "rejected", "mock", false, 0);

    let ledger = query_wallet_ledger(&state, 1).await?;
    assert!(ledger.is_empty());
    let snapshot = query_order_snapshot(&state, &user, "tx-reject-1").await?;
    assert!(snapshot.found);
    assert_eq!(
        snapshot.probe_status,
        Some(IapOrderProbeStatus::PendingCredit)
    );
    assert!(snapshot.next_retry_after_ms.is_none());
    Ok(())
}

#[tokio::test]
async fn verify_iap_order_should_reject_cross_user_transaction_replay() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (user1, user2) = load_two_users(&state, 1, 2).await?;

    state
        .verify_iap_order(&user1, verify_input("tx-replay-1", "mock_ok_receipt"))
        .await?;
    let err = state
        .verify_iap_order(&user2, verify_input("tx-replay-1", "mock_ok_receipt"))
        .await
        .expect_err("cross user replay should fail");
    assert_payment_conflict(&err);
    Ok(())
}

#[tokio::test]
async fn verify_iap_order_should_allow_retry_after_transient_apple_status() -> Result<()> {
    let (payment_config, requests, server) = start_apple_verify_stub(vec![
        json!({
            "status": 21005,
            "environment": "Production"
        }),
        json!({
            "status": 0,
            "environment": "Production",
            "latest_receipt_info": [
                {
                    "transaction_id": "tx-apple-retry-1",
                    "product_id": "com.echoisle.coins.60"
                }
            ]
        }),
    ])
    .await?;

    let (_tdb, mut state) = AppState::new_for_test().await?;
    let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
    inner.config.payment = payment_config;

    let user = load_user(&state, 1).await?;
    let input = verify_input("tx-apple-retry-1", "receipt_retryable_then_ok");

    let first_err = state
        .verify_iap_order(&user, input.clone())
        .await
        .expect_err("first call should fail with retryable status");
    assert_retryable_payment_error_contains(&first_err, 21005);

    let first_query = query_order_snapshot(&state, &user, "tx-apple-retry-1").await?;
    assert_order_query_not_found(&first_query);

    let second = state.verify_iap_order(&user, input).await?;
    assert_order_output(&second, "verified", "apple", true, 60);

    let second_query = query_order_snapshot(&state, &user, "tx-apple-retry-1").await?;
    assert_order_query_verified(&second_query, "com.echoisle.coins.60");

    assert_stub_request_paths(&requests, &["/prod", "/prod"]).await;
    server.abort();
    Ok(())
}

#[tokio::test]
async fn get_iap_order_by_transaction_should_return_not_found_for_missing_tx() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let user = load_user(&state, 1).await?;
    let out = query_order_snapshot(&state, &user, "tx-not-exist-1").await?;
    assert_order_query_not_found(&out);
    Ok(())
}

#[tokio::test]
async fn get_iap_order_by_transaction_should_return_verified_snapshot() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let user = load_user(&state, 1).await?;

    state
        .verify_iap_order(
            &user,
            verify_input("tx-query-verified-1", "mock_ok_receipt"),
        )
        .await?;

    let out = query_order_snapshot(&state, &user, "tx-query-verified-1").await?;
    assert_order_query_verified(&out, "com.echoisle.coins.60");
    Ok(())
}

#[tokio::test]
async fn get_iap_order_by_transaction_should_return_conflict_for_other_user() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (user1, user2) = load_two_users(&state, 1, 2).await?;

    state
        .verify_iap_order(
            &user1,
            verify_input("tx-query-conflict-1", "mock_ok_receipt"),
        )
        .await?;
    let err = query_order_snapshot_expect_conflict(&state, &user2, "tx-query-conflict-1").await;
    assert_payment_conflict(&err);
    Ok(())
}

#[tokio::test]
async fn reconcile_wallet_balance_once_should_record_mismatch_sample() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    sqlx::query(
        r#"
        INSERT INTO user_wallets(user_id, balance, updated_at)
        VALUES ($1, $2, NOW())
        ON CONFLICT (user_id) DO UPDATE
        SET balance = EXCLUDED.balance, updated_at = NOW()
        "#,
    )
    .bind(1_i64)
    .bind(123_i64)
    .execute(&state.pool)
    .await?;

    let (_compared_users, mismatch_users, sampled_rows) =
        state.reconcile_wallet_balance_once(16).await?;
    assert!(mismatch_users >= 1);
    assert!(sampled_rows >= 1);

    let audit_count: i64 = sqlx::query_scalar(
        r#"
        SELECT COUNT(1)::bigint
        FROM wallet_balance_reconcile_audits
        WHERE user_id = 1
        "#,
    )
    .fetch_one(&state.pool)
    .await?;
    assert!(audit_count >= 1);
    Ok(())
}
