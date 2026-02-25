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
/// MVP phase returns mock receipt payload that can be sent to `/api/pay/iap/verify`.
#[tauri::command]
pub(crate) fn iap_purchase_product(product_id: String) -> Result<IapPurchasePayload, String> {
    if product_id.trim().is_empty() {
        return Err("product_id is required".to_string());
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
