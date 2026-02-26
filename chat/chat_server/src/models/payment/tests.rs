use super::*;
use anyhow::Result;
use serde_json::json;

fn verify_input(tx: &str, receipt_data: &str) -> VerifyIapOrderInput {
    VerifyIapOrderInput {
        product_id: "com.aicomm.coins.60".to_string(),
        transaction_id: tx.to_string(),
        original_transaction_id: None,
        receipt_data: receipt_data.to_string(),
    }
}

#[test]
fn extract_receipt_records_should_collect_both_paths() {
    let payload = json!({
        "latest_receipt_info": [
            {
                "transaction_id": "tx-1",
                "original_transaction_id": "otx-1",
                "product_id": "com.aicomm.coins.60"
            }
        ],
        "receipt": {
            "in_app": [
                {
                    "transaction_id": "tx-2",
                    "original_transaction_id": "otx-2",
                    "product_id": "com.aicomm.coins.120"
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
            product_id: Some("com.aicomm.coins.60".to_string()),
        },
        ReceiptRecord {
            transaction_id: "tx-b".to_string(),
            original_transaction_id: None,
            product_id: Some("com.aicomm.coins.120".to_string()),
        },
    ];

    let matched = select_matching_record(&records, "com.aicomm.coins.60", "tx-a", Some("otx-a"));
    assert!(matched.is_some());

    let not_matched =
        select_matching_record(&records, "com.aicomm.coins.60", "tx-b", Some("otx-b"));
    assert!(not_matched.is_none());
}

#[test]
fn normalize_verify_mode_should_default_to_mock() {
    assert_eq!(normalize_verify_mode("apple"), "apple");
    assert_eq!(normalize_verify_mode(" production "), "apple");
    assert_eq!(normalize_verify_mode("mock"), "mock");
    assert_eq!(normalize_verify_mode(""), "mock");
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
    assert_eq!(out.verify_mode, "mock");
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
    assert_eq!(out.verify_mode, "mock");
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

#[tokio::test]
async fn get_iap_order_by_transaction_should_return_not_found_for_missing_tx() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let user = state
        .find_user_by_id(1)
        .await?
        .expect("user id 1 should exist");
    let out = state
        .get_iap_order_by_transaction(
            &user,
            GetIapOrderByTransaction {
                transaction_id: "tx-not-exist-1".to_string(),
            },
        )
        .await?;
    assert!(!out.found);
    assert!(out.order.is_none());
    Ok(())
}

#[tokio::test]
async fn get_iap_order_by_transaction_should_return_verified_snapshot() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let user = state
        .find_user_by_id(1)
        .await?
        .expect("user id 1 should exist");

    state
        .verify_iap_order(
            &user,
            verify_input("tx-query-verified-1", "mock_ok_receipt"),
        )
        .await?;

    let out = state
        .get_iap_order_by_transaction(
            &user,
            GetIapOrderByTransaction {
                transaction_id: "tx-query-verified-1".to_string(),
            },
        )
        .await?;
    assert!(out.found);
    let order = out.order.expect("order should exist");
    assert_eq!(order.status, "verified");
    assert_eq!(order.product_id, "com.aicomm.coins.60");
    assert!(order.credited);
    Ok(())
}

#[tokio::test]
async fn get_iap_order_by_transaction_should_return_conflict_for_other_user() -> Result<()> {
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
        .verify_iap_order(
            &user1,
            verify_input("tx-query-conflict-1", "mock_ok_receipt"),
        )
        .await?;
    let err = state
        .get_iap_order_by_transaction(
            &user2,
            GetIapOrderByTransaction {
                transaction_id: "tx-query-conflict-1".to_string(),
            },
        )
        .await
        .expect_err("cross user query should fail");
    assert!(matches!(err, AppError::PaymentConflict(_)));
    Ok(())
}
