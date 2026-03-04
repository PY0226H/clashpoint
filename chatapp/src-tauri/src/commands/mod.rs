use std::{process::Command, sync::Arc, time::SystemTime};

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager};
use tracing::info;

use crate::{
    config::{AppConfig, IapConfig},
    utils::app_dir,
    AppState,
};

// Learn more about Tauri commands at https://tauri.app/v1/guides/features/command
#[tauri::command]
pub(crate) fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[tauri::command]
pub(crate) fn get_app_dir() -> String {
    app_dir().display().to_string()
}

#[tauri::command]
pub(crate) fn get_config(handle: AppHandle) -> Arc<AppConfig> {
    let conf = handle.state::<AppState>().config.load().clone();
    info!("Config: {:?}", conf);
    conf
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct IapPurchasePayload {
    product_id: String,
    transaction_id: String,
    original_transaction_id: Option<String>,
    receipt_data: String,
    source: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum IapPurchaseMode {
    Mock,
    Native,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct NativeBridgePayloadRaw {
    #[serde(default, alias = "product_id")]
    product_id: String,
    #[serde(default, alias = "transaction_id")]
    transaction_id: String,
    #[serde(default, alias = "original_transaction_id")]
    original_transaction_id: Option<String>,
    #[serde(default, alias = "receipt_data")]
    receipt_data: String,
    #[serde(default)]
    source: String,
}

fn normalize_iap_purchase_mode(mode: &str) -> IapPurchaseMode {
    match mode.trim().to_ascii_lowercase().as_str() {
        "mock" | "dev_mock" => IapPurchaseMode::Mock,
        _ => IapPurchaseMode::Native,
    }
}

fn runtime_env() -> Option<String> {
    for key in ["AICOMM_ENV", "APP_ENV", "RUST_ENV", "ENV"] {
        if let Ok(value) = std::env::var(key) {
            let normalized = value.trim();
            if !normalized.is_empty() {
                return Some(normalized.to_ascii_lowercase());
            }
        }
    }
    None
}

fn is_production_env(value: &str) -> bool {
    matches!(value.trim(), "prod" | "production")
}

fn runtime_is_production() -> bool {
    runtime_env()
        .map(|v| is_production_env(&v))
        .unwrap_or(false)
}

fn sanitize_product_id(input: &str) -> String {
    let normalized = input
        .trim()
        .chars()
        .filter(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '-' | '_'))
        .collect::<String>();
    if normalized.is_empty() {
        "unknown".to_string()
    } else {
        normalized.chars().take(48).collect::<String>()
    }
}

fn unix_millis() -> u128 {
    SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .map(|v| v.as_millis())
        .unwrap_or(0)
}

fn truncate_error_text(text: &str, max_chars: usize) -> String {
    let normalized = text.trim();
    if normalized.is_empty() {
        return String::new();
    }
    normalized.chars().take(max_chars).collect::<String>()
}

fn build_mock_purchase_payload(product_id: &str) -> IapPurchasePayload {
    let safe_product = sanitize_product_id(product_id);
    let ts = unix_millis();
    let transaction_id = format!("tauri-iap-{safe_product}-{ts}");
    let receipt_data = format!("mock_ok_receipt:tauri_bridge:{safe_product}:{ts}");
    IapPurchasePayload {
        product_id: safe_product,
        transaction_id,
        original_transaction_id: None,
        receipt_data,
        source: "tauri_mock_bridge".to_string(),
    }
}

fn parse_native_bridge_payload(
    raw_payload: &str,
    requested_product_id: &str,
) -> Result<IapPurchasePayload, String> {
    let parsed: NativeBridgePayloadRaw = serde_json::from_str(raw_payload).map_err(|err| {
        let snippet = truncate_error_text(raw_payload, 180);
        format!("native iap bridge returned invalid json payload: {err}; payload={snippet}")
    })?;

    let requested_product = sanitize_product_id(requested_product_id);
    let response_product = if parsed.product_id.trim().is_empty() {
        requested_product.clone()
    } else {
        sanitize_product_id(&parsed.product_id)
    };

    if response_product != requested_product {
        return Err(format!(
            "native iap bridge returned mismatched product_id: expected={requested_product}, actual={response_product}"
        ));
    }

    let transaction_id = parsed.transaction_id.trim().to_string();
    if transaction_id.is_empty() {
        return Err("native iap bridge payload missing transactionId".to_string());
    }

    let receipt_data = parsed.receipt_data.trim().to_string();
    if receipt_data.is_empty() {
        return Err("native iap bridge payload missing receiptData".to_string());
    }

    let original_transaction_id = parsed
        .original_transaction_id
        .as_deref()
        .map(str::trim)
        .filter(|v| !v.is_empty())
        .map(ToString::to_string);

    let source = if parsed.source.trim().is_empty() {
        "tauri_native_bridge".to_string()
    } else {
        parsed.source.trim().to_string()
    };

    Ok(IapPurchasePayload {
        product_id: response_product,
        transaction_id,
        original_transaction_id,
        receipt_data,
        source,
    })
}

fn run_native_bridge_purchase(
    product_id: &str,
    iap_config: &IapConfig,
) -> Result<IapPurchasePayload, String> {
    if let Ok(raw_payload) = std::env::var("AICOMM_IAP_NATIVE_BRIDGE_RESPONSE_JSON") {
        if !raw_payload.trim().is_empty() {
            return parse_native_bridge_payload(&raw_payload, product_id);
        }
    }

    let bridge_bin = iap_config.native_bridge.bin.trim();
    if bridge_bin.is_empty() {
        return Err(
            "iap purchase mode=native requires iap.native_bridge.bin to be configured".to_string(),
        );
    }

    let mut command = Command::new(bridge_bin);
    for arg in &iap_config.native_bridge.args {
        command.arg(arg);
    }
    command.arg("--product-id").arg(product_id.trim());
    command.env("AICOMM_IAP_PRODUCT_ID", product_id.trim());

    let output = command
        .output()
        .map_err(|err| format!("failed to execute native iap bridge command: {err}"))?;

    if !output.status.success() {
        let stderr = truncate_error_text(&String::from_utf8_lossy(&output.stderr), 180);
        let stdout = truncate_error_text(&String::from_utf8_lossy(&output.stdout), 180);
        return Err(format!(
            "native iap bridge command failed: status={}; stderr={stderr}; stdout={stdout}",
            output.status
        ));
    }

    let stdout = String::from_utf8(output.stdout)
        .map_err(|err| format!("native iap bridge stdout is not valid utf-8: {err}"))?;
    parse_native_bridge_payload(&stdout, product_id)
}

/// Bridge command for IAP purchase.
/// `purchase_mode=mock` returns deterministic mock payload for local development.
/// `purchase_mode=native` executes external bridge command and expects JSON payload:
/// {"productId","transactionId","originalTransactionId","receiptData","source"}.
#[tauri::command]
pub(crate) fn iap_purchase_product(
    handle: AppHandle,
    product_id: String,
) -> Result<IapPurchasePayload, String> {
    if product_id.trim().is_empty() {
        return Err("product_id is required".to_string());
    }

    let app_config = handle.state::<AppState>().config.load().clone();
    let mode = normalize_iap_purchase_mode(&app_config.iap.purchase_mode);
    if runtime_is_production() && mode == IapPurchaseMode::Mock {
        return Err("mock iap bridge is forbidden in production runtime".to_string());
    }

    if mode == IapPurchaseMode::Native {
        return run_native_bridge_purchase(&product_id, &app_config.iap);
    }

    Ok(build_mock_purchase_payload(&product_id))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn normalize_iap_purchase_mode_should_be_fail_closed() {
        assert_eq!(normalize_iap_purchase_mode("mock"), IapPurchaseMode::Mock);
        assert_eq!(
            normalize_iap_purchase_mode("dev_mock"),
            IapPurchaseMode::Mock
        );
        assert_eq!(
            normalize_iap_purchase_mode("native"),
            IapPurchaseMode::Native
        );
        assert_eq!(normalize_iap_purchase_mode(""), IapPurchaseMode::Native);
        assert_eq!(
            normalize_iap_purchase_mode("unknown"),
            IapPurchaseMode::Native
        );
    }

    #[test]
    fn is_production_env_should_match_prod_aliases() {
        assert!(is_production_env("prod"));
        assert!(is_production_env("production"));
        assert!(!is_production_env("staging"));
        assert!(!is_production_env("dev"));
    }

    #[test]
    fn parse_native_bridge_payload_should_support_camel_case() {
        let payload = parse_native_bridge_payload(
            r#"{
                "productId":"com.acme.coins.100",
                "transactionId":"tx-100",
                "originalTransactionId":"otx-100",
                "receiptData":"base64-receipt",
                "source":"storekit2"
            }"#,
            "com.acme.coins.100",
        )
        .expect("payload should parse");

        assert_eq!(payload.product_id, "com.acme.coins.100");
        assert_eq!(payload.transaction_id, "tx-100");
        assert_eq!(payload.original_transaction_id.as_deref(), Some("otx-100"));
        assert_eq!(payload.receipt_data, "base64-receipt");
        assert_eq!(payload.source, "storekit2");
    }

    #[test]
    fn parse_native_bridge_payload_should_support_snake_case() {
        let raw = json!({
            "product_id":"com.acme.coins.500",
            "transaction_id":"tx-500",
            "original_transaction_id":"otx-500",
            "receipt_data":"receipt-500",
            "source":"swift-bridge"
        });

        let payload = parse_native_bridge_payload(&raw.to_string(), "com.acme.coins.500")
            .expect("payload should parse");

        assert_eq!(payload.product_id, "com.acme.coins.500");
        assert_eq!(payload.transaction_id, "tx-500");
        assert_eq!(payload.original_transaction_id.as_deref(), Some("otx-500"));
        assert_eq!(payload.receipt_data, "receipt-500");
        assert_eq!(payload.source, "swift-bridge");
    }

    #[test]
    fn parse_native_bridge_payload_should_fill_default_product_and_source() {
        let raw = json!({
            "transactionId":"tx-1",
            "receiptData":"receipt-1"
        });

        let payload = parse_native_bridge_payload(&raw.to_string(), "com.acme.coins.100")
            .expect("payload should parse");

        assert_eq!(payload.product_id, "com.acme.coins.100");
        assert_eq!(payload.source, "tauri_native_bridge");
        assert_eq!(payload.original_transaction_id, None);
    }

    #[test]
    fn parse_native_bridge_payload_should_reject_mismatched_product() {
        let raw = json!({
            "productId":"com.acme.coins.500",
            "transactionId":"tx-2",
            "receiptData":"receipt-2"
        });

        let err = parse_native_bridge_payload(&raw.to_string(), "com.acme.coins.100")
            .expect_err("mismatch should fail");
        assert!(err.contains("mismatched product_id"));
    }

    #[test]
    fn parse_native_bridge_payload_should_reject_missing_required_fields() {
        let raw_missing_transaction = json!({
            "productId":"com.acme.coins.100",
            "receiptData":"receipt-3"
        });
        let err1 =
            parse_native_bridge_payload(&raw_missing_transaction.to_string(), "com.acme.coins.100")
                .expect_err("missing transaction should fail");
        assert!(err1.contains("transactionId"));

        let raw_missing_receipt = json!({
            "productId":"com.acme.coins.100",
            "transactionId":"tx-3"
        });
        let err2 =
            parse_native_bridge_payload(&raw_missing_receipt.to_string(), "com.acme.coins.100")
                .expect_err("missing receipt should fail");
        assert!(err2.contains("receiptData"));
    }
}
