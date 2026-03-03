use std::{sync::Arc, time::SystemTime};

use serde::Serialize;
use tauri::{AppHandle, Manager};
use tracing::info;

use crate::{config::AppConfig, utils::app_dir, AppState};

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

/// Bridge command for IAP purchase.
/// `purchase_mode=mock` returns deterministic mock payload for local development.
/// `purchase_mode=native` is intentionally blocked until native StoreKit bridge is wired.
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
        return Err("iap purchase mode=native is not implemented on this target yet".to_string());
    }

    let safe_product = sanitize_product_id(&product_id);
    let ts = unix_millis();
    let transaction_id = format!("tauri-iap-{safe_product}-{ts}");
    let receipt_data = format!("mock_ok_receipt:tauri_bridge:{safe_product}:{ts}");

    Ok(IapPurchasePayload {
        product_id: safe_product,
        transaction_id,
        original_transaction_id: None,
        receipt_data,
        source: "tauri_mock_bridge".to_string(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

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
}
