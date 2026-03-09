use crate::config::PaymentConfig;
use crate::AppError;
use serde_json::{json, Value};
use std::time::Duration;

pub(super) fn mock_verify_receipt(receipt: &str) -> (String, Option<String>) {
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
pub(crate) struct ReceiptVerifyResult {
    pub status: String,
    pub verify_mode: String,
    pub verify_reason: Option<String>,
    pub raw_payload: Value,
}

#[derive(Debug, Clone)]
pub(crate) struct ReceiptRecord {
    pub transaction_id: String,
    pub original_transaction_id: Option<String>,
    pub product_id: Option<String>,
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

pub(crate) fn normalize_verify_mode(mode: &str) -> &str {
    match mode.trim().to_ascii_lowercase().as_str() {
        "mock" | "dev_mock" => "mock",
        _ => "apple",
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

pub(crate) fn is_retryable_apple_status(status_code: i64) -> bool {
    // Apple verify transient failures should not be persisted as terminal rejected orders.
    status_code == 21005 || status_code == 21009 || (21100..=21199).contains(&status_code)
}

pub(crate) fn extract_receipt_records(payload: &Value) -> Vec<ReceiptRecord> {
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

pub(crate) fn select_matching_record<'a>(
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

    if status_code != 0 && is_retryable_apple_status(status_code) {
        return Err(AppError::PaymentError(format!(
            "apple verify transient status {status_code} on {} endpoint",
            endpoint.label()
        )));
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

pub(crate) async fn verify_receipt(
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
