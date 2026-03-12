use std::{path::Path, process::Command, sync::Arc, time::SystemTime};

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

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct IapNativeBridgeDiagnostics {
    runtime_env: Option<String>,
    runtime_is_production: bool,
    purchase_mode: String,
    allowed_product_ids: Vec<String>,
    invalid_allowed_product_ids: Vec<String>,
    allowed_product_ids_configured: bool,
    native_bridge_bin: String,
    native_bridge_args: Vec<String>,
    native_bridge_bin_is_absolute: bool,
    native_bridge_bin_exists: bool,
    native_bridge_bin_executable: bool,
    has_simulate_arg: bool,
    json_override_present: bool,
    production_policy_ok: bool,
    production_policy_error: Option<String>,
    ready_for_native_purchase: bool,
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

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct NativeBridgeErrorPayloadRaw {
    #[serde(default)]
    code: String,
    #[serde(default)]
    error: String,
}

fn normalize_iap_purchase_mode(mode: &str) -> IapPurchaseMode {
    match mode.trim().to_ascii_lowercase().as_str() {
        "mock" | "dev_mock" => IapPurchaseMode::Mock,
        _ => IapPurchaseMode::Native,
    }
}

fn runtime_env() -> Option<String> {
    for key in ["ECHOISLE_ENV", "APP_ENV", "RUST_ENV", "ENV"] {
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

fn is_valid_product_id(value: &str) -> bool {
    let trimmed = value.trim();
    !trimmed.is_empty()
        && trimmed.len() <= 64
        && trimmed
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '-' | '_'))
}

fn normalize_and_validate_allowed_product_ids(raw: &[String]) -> (Vec<String>, Vec<String>) {
    let mut allowed = Vec::new();
    let mut invalid = Vec::new();

    for item in raw {
        let normalized = item.trim();
        if normalized.is_empty() {
            continue;
        }
        if !is_valid_product_id(normalized) {
            invalid.push(normalized.to_string());
            continue;
        }
        if !allowed.iter().any(|v| v == normalized) {
            allowed.push(normalized.to_string());
        }
    }

    (allowed, invalid)
}

fn normalize_requested_product_id(input: &str) -> Result<String, String> {
    let normalized = input.trim();
    if normalized.is_empty() {
        return Err("product_id is required".to_string());
    }
    if normalized.len() > 64 {
        return Err("product_id is too long, max 64 chars".to_string());
    }
    if !is_valid_product_id(normalized) {
        return Err(
            "product_id contains invalid characters, only [a-zA-Z0-9._-] are allowed".to_string(),
        );
    }
    Ok(normalized.to_string())
}

fn ensure_product_id_allowed(
    product_id: &str,
    allowed_product_ids: &[String],
) -> Result<(), String> {
    if allowed_product_ids.is_empty() {
        return Ok(());
    }
    if allowed_product_ids.iter().any(|item| item == product_id) {
        return Ok(());
    }
    Err(format!(
        "iap purchase rejected: product_id {product_id} is not in iap.allowed_product_ids"
    ))
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

fn is_path_executable(path: &Path) -> bool {
    let Ok(metadata) = std::fs::metadata(path) else {
        return false;
    };
    if !metadata.is_file() {
        return false;
    }

    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        (metadata.permissions().mode() & 0o111) != 0
    }
    #[cfg(not(unix))]
    {
        true
    }
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

fn normalize_native_bridge_error_code(code: &str) -> String {
    let normalized = code
        .trim()
        .chars()
        .filter(|c| c.is_ascii_alphanumeric() || matches!(c, '_' | '-'))
        .collect::<String>()
        .to_ascii_lowercase();
    if normalized.is_empty() {
        "unknown_error".to_string()
    } else {
        normalized.replace('-', "_")
    }
}

fn parse_native_bridge_error_payload(raw_payload: &str) -> Option<(String, String)> {
    let parsed: NativeBridgeErrorPayloadRaw = serde_json::from_str(raw_payload).ok()?;
    let message = parsed.error.trim();
    if message.is_empty() {
        return None;
    }
    Some((
        normalize_native_bridge_error_code(&parsed.code),
        message.to_string(),
    ))
}

fn build_native_bridge_command_error(
    status_text: &str,
    stderr_raw: &str,
    stdout_raw: &str,
) -> String {
    if let Some((code, message)) = parse_native_bridge_error_payload(stderr_raw)
        .or_else(|| parse_native_bridge_error_payload(stdout_raw))
    {
        return format!("native_iap_bridge_error:{code}:{message}");
    }

    let stderr = truncate_error_text(stderr_raw, 180);
    let stdout = truncate_error_text(stdout_raw, 180);
    format!(
        "native iap bridge command failed: status={status_text}; stderr={stderr}; stdout={stdout}"
    )
}

fn has_simulate_arg(args: &[String]) -> bool {
    args.iter().any(|arg| {
        let normalized = arg.trim().to_ascii_lowercase();
        normalized == "--simulate" || normalized == "-simulate"
    })
}

fn build_iap_native_bridge_diagnostics(
    iap_config: &IapConfig,
    runtime_env_value: Option<String>,
    json_override_present: bool,
) -> IapNativeBridgeDiagnostics {
    let runtime_is_production = runtime_env_value
        .as_deref()
        .map(is_production_env)
        .unwrap_or(false);
    let mode = normalize_iap_purchase_mode(&iap_config.purchase_mode);
    let purchase_mode = match mode {
        IapPurchaseMode::Mock => "mock",
        IapPurchaseMode::Native => "native",
    }
    .to_string();

    let native_bridge_bin = iap_config.native_bridge.bin.trim().to_string();
    let path = Path::new(native_bridge_bin.as_str());
    let native_bridge_bin_is_absolute = !native_bridge_bin.is_empty() && path.is_absolute();
    let native_bridge_bin_exists = !native_bridge_bin.is_empty() && path.exists();
    let native_bridge_bin_executable =
        !native_bridge_bin.is_empty() && native_bridge_bin_exists && is_path_executable(path);
    let has_simulate = has_simulate_arg(&iap_config.native_bridge.args);
    let (allowed_product_ids, invalid_allowed_product_ids) =
        normalize_and_validate_allowed_product_ids(&iap_config.allowed_product_ids);
    let production_policy = validate_native_bridge_policy(
        iap_config,
        runtime_is_production,
        json_override_present,
        &allowed_product_ids,
        &invalid_allowed_product_ids,
    );
    let production_policy_ok = production_policy.is_ok();
    let production_policy_error = production_policy.err();

    let ready_for_native_purchase = mode == IapPurchaseMode::Native
        && !native_bridge_bin.is_empty()
        && native_bridge_bin_exists
        && native_bridge_bin_executable
        && invalid_allowed_product_ids.is_empty()
        && production_policy_ok;

    IapNativeBridgeDiagnostics {
        runtime_env: runtime_env_value,
        runtime_is_production,
        purchase_mode,
        allowed_product_ids_configured: !allowed_product_ids.is_empty(),
        allowed_product_ids,
        invalid_allowed_product_ids,
        native_bridge_bin,
        native_bridge_args: iap_config.native_bridge.args.clone(),
        native_bridge_bin_is_absolute,
        native_bridge_bin_exists,
        native_bridge_bin_executable,
        has_simulate_arg: has_simulate,
        json_override_present,
        production_policy_ok,
        production_policy_error,
        ready_for_native_purchase,
    }
}

fn validate_native_bridge_policy(
    iap_config: &IapConfig,
    runtime_is_production: bool,
    has_json_override: bool,
    allowed_product_ids: &[String],
    invalid_allowed_product_ids: &[String],
) -> Result<(), String> {
    if normalize_iap_purchase_mode(&iap_config.purchase_mode) == IapPurchaseMode::Mock {
        return Ok(());
    }

    if !invalid_allowed_product_ids.is_empty() {
        return Err(format!(
            "iap.allowed_product_ids contains invalid values: {}",
            invalid_allowed_product_ids.join(", ")
        ));
    }

    if !runtime_is_production {
        return Ok(());
    }

    if allowed_product_ids.is_empty() {
        return Err("iap.allowed_product_ids must be configured in production runtime".to_string());
    }

    if has_json_override {
        return Err(
            "ECHOISLE_IAP_NATIVE_BRIDGE_RESPONSE_JSON is forbidden in production runtime"
                .to_string(),
        );
    }

    if has_simulate_arg(&iap_config.native_bridge.args) {
        return Err(
            "iap.native_bridge.args cannot include --simulate in production runtime".to_string(),
        );
    }

    let bridge_bin = iap_config.native_bridge.bin.trim();
    if bridge_bin.is_empty() {
        return Err(
            "iap purchase mode=native requires iap.native_bridge.bin to be configured".to_string(),
        );
    }

    if !Path::new(bridge_bin).is_absolute() {
        return Err(
            "iap.native_bridge.bin must be an absolute path in production runtime".to_string(),
        );
    }

    Ok(())
}

#[tauri::command]
pub(crate) fn iap_get_native_bridge_diagnostics(handle: AppHandle) -> IapNativeBridgeDiagnostics {
    let app_config = handle.state::<AppState>().config.load().clone();
    let env = runtime_env();
    let json_override_present = std::env::var("ECHOISLE_IAP_NATIVE_BRIDGE_RESPONSE_JSON")
        .ok()
        .as_deref()
        .map(str::trim)
        .map(|v| !v.is_empty())
        .unwrap_or(false);
    build_iap_native_bridge_diagnostics(&app_config.iap, env, json_override_present)
}

fn run_native_bridge_purchase(
    product_id: &str,
    iap_config: &IapConfig,
    runtime_is_production: bool,
) -> Result<IapPurchasePayload, String> {
    let normalized_product_id = normalize_requested_product_id(product_id)?;
    let (allowed_product_ids, invalid_allowed_product_ids) =
        normalize_and_validate_allowed_product_ids(&iap_config.allowed_product_ids);
    let json_override = std::env::var("ECHOISLE_IAP_NATIVE_BRIDGE_RESPONSE_JSON").ok();
    let has_json_override = json_override
        .as_deref()
        .map(str::trim)
        .map(|v| !v.is_empty())
        .unwrap_or(false);
    validate_native_bridge_policy(
        iap_config,
        runtime_is_production,
        has_json_override,
        &allowed_product_ids,
        &invalid_allowed_product_ids,
    )?;
    ensure_product_id_allowed(&normalized_product_id, &allowed_product_ids)?;

    if let Some(raw_payload) = json_override {
        if !raw_payload.trim().is_empty() {
            return parse_native_bridge_payload(&raw_payload, &normalized_product_id);
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
    command
        .arg("--product-id")
        .arg(normalized_product_id.as_str());
    command.env("ECHOISLE_IAP_PRODUCT_ID", normalized_product_id.as_str());

    let output = command
        .output()
        .map_err(|err| format!("failed to execute native iap bridge command: {err}"))?;

    if !output.status.success() {
        let stderr_raw = String::from_utf8_lossy(&output.stderr);
        let stdout_raw = String::from_utf8_lossy(&output.stdout);
        return Err(build_native_bridge_command_error(
            &output.status.to_string(),
            &stderr_raw,
            &stdout_raw,
        ));
    }

    let stdout = String::from_utf8(output.stdout)
        .map_err(|err| format!("native iap bridge stdout is not valid utf-8: {err}"))?;
    parse_native_bridge_payload(&stdout, &normalized_product_id)
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
    let normalized_product_id = normalize_requested_product_id(&product_id)?;

    let app_config = handle.state::<AppState>().config.load().clone();
    let mode = normalize_iap_purchase_mode(&app_config.iap.purchase_mode);
    if runtime_is_production() && mode == IapPurchaseMode::Mock {
        return Err("mock iap bridge is forbidden in production runtime".to_string());
    }

    if mode == IapPurchaseMode::Native {
        return run_native_bridge_purchase(
            &normalized_product_id,
            &app_config.iap,
            runtime_is_production(),
        );
    }

    Ok(build_mock_purchase_payload(&normalized_product_id))
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
    fn normalize_requested_product_id_should_validate_format() {
        let ok = normalize_requested_product_id("com.echoisle.coins.60").expect("should pass");
        assert_eq!(ok, "com.echoisle.coins.60");

        let err1 = normalize_requested_product_id(" ").expect_err("empty should fail");
        assert!(err1.contains("required"));

        let err2 = normalize_requested_product_id("invalid product")
            .expect_err("invalid char should fail");
        assert!(err2.contains("invalid characters"));
    }

    #[test]
    fn normalize_and_validate_allowed_product_ids_should_split_valid_and_invalid() {
        let (allowed, invalid) = normalize_and_validate_allowed_product_ids(&[
            " com.echoisle.coins.60 ".to_string(),
            "com.echoisle.coins.60".to_string(),
            "invalid product".to_string(),
            "".to_string(),
        ]);
        assert_eq!(allowed, vec!["com.echoisle.coins.60".to_string()]);
        assert_eq!(invalid, vec!["invalid product".to_string()]);
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

    #[test]
    fn has_simulate_arg_should_match_simulate_flags() {
        assert!(has_simulate_arg(&["--simulate".to_string()]));
        assert!(has_simulate_arg(&["-simulate".to_string()]));
        assert!(!has_simulate_arg(&["--foo".to_string()]));
        assert!(!has_simulate_arg(&[]));
    }

    #[test]
    fn parse_native_bridge_error_payload_should_parse_code_and_message() {
        let parsed = parse_native_bridge_error_payload(
            r#"{"code":"purchase_pending","error":"purchase is pending"}"#,
        )
        .expect("should parse");
        assert_eq!(parsed.0, "purchase_pending");
        assert_eq!(parsed.1, "purchase is pending");
    }

    #[test]
    fn parse_native_bridge_error_payload_should_reject_missing_message() {
        let parsed = parse_native_bridge_error_payload(r#"{"code":"purchase_pending"}"#);
        assert!(parsed.is_none());
    }

    #[test]
    fn build_native_bridge_command_error_should_prefer_structured_payload() {
        let err = build_native_bridge_command_error(
            "exit status: 1",
            r#"{"code":"purchase_cancelled","error":"purchase is cancelled by user"}"#,
            "",
        );
        assert_eq!(
            err,
            "native_iap_bridge_error:purchase_cancelled:purchase is cancelled by user"
        );
    }

    #[test]
    fn build_native_bridge_command_error_should_fallback_to_legacy_text() {
        let err = build_native_bridge_command_error("exit status: 1", "raw stderr", "raw stdout");
        assert!(err.contains("native iap bridge command failed"));
        assert!(err.contains("raw stderr"));
        assert!(err.contains("raw stdout"));
    }

    #[test]
    fn build_iap_native_bridge_diagnostics_should_report_ready_when_native_bin_is_valid() {
        let cfg = IapConfig {
            purchase_mode: "native".to_string(),
            allowed_product_ids: vec!["com.echoisle.coins.60".to_string()],
            native_bridge: crate::config::IapNativeBridgeConfig {
                bin: "/bin/sh".to_string(),
                args: vec![],
            },
        };
        let diag = build_iap_native_bridge_diagnostics(&cfg, Some("dev".to_string()), false);
        assert_eq!(diag.purchase_mode, "native");
        assert!(diag.allowed_product_ids_configured);
        assert_eq!(
            diag.allowed_product_ids,
            vec!["com.echoisle.coins.60".to_string()]
        );
        assert!(diag.invalid_allowed_product_ids.is_empty());
        assert!(diag.native_bridge_bin_exists);
        assert!(diag.native_bridge_bin_executable);
        assert!(diag.production_policy_ok);
        assert!(diag.ready_for_native_purchase);
    }

    #[test]
    fn build_iap_native_bridge_diagnostics_should_report_policy_error_in_production() {
        let cfg = IapConfig {
            purchase_mode: "native".to_string(),
            allowed_product_ids: vec!["com.echoisle.coins.60".to_string()],
            native_bridge: crate::config::IapNativeBridgeConfig {
                bin: "relative/bin".to_string(),
                args: vec!["--simulate".to_string()],
            },
        };
        let diag = build_iap_native_bridge_diagnostics(&cfg, Some("production".to_string()), true);
        assert_eq!(diag.purchase_mode, "native");
        assert!(!diag.production_policy_ok);
        assert!(!diag.ready_for_native_purchase);
        assert!(diag
            .production_policy_error
            .as_deref()
            .unwrap_or_default()
            .contains("ECHOISLE_IAP_NATIVE_BRIDGE_RESPONSE_JSON"));
    }

    #[test]
    fn build_iap_native_bridge_diagnostics_should_not_be_ready_in_mock_mode() {
        let cfg = IapConfig {
            purchase_mode: "mock".to_string(),
            allowed_product_ids: vec![],
            native_bridge: crate::config::IapNativeBridgeConfig {
                bin: "/bin/sh".to_string(),
                args: vec![],
            },
        };
        let diag = build_iap_native_bridge_diagnostics(&cfg, Some("dev".to_string()), false);
        assert_eq!(diag.purchase_mode, "mock");
        assert!(!diag.ready_for_native_purchase);
    }

    #[test]
    fn validate_native_bridge_policy_should_allow_non_production_relaxed_mode() {
        let cfg = IapConfig {
            purchase_mode: "native".to_string(),
            allowed_product_ids: vec![],
            native_bridge: crate::config::IapNativeBridgeConfig {
                bin: "relative/bin".to_string(),
                args: vec!["--simulate".to_string()],
            },
        };
        let (allowed, invalid) =
            normalize_and_validate_allowed_product_ids(&cfg.allowed_product_ids);
        validate_native_bridge_policy(&cfg, false, true, &allowed, &invalid)
            .expect("non-production should allow");
    }

    #[test]
    fn validate_native_bridge_policy_should_block_json_override_in_production() {
        let cfg = IapConfig {
            purchase_mode: "native".to_string(),
            allowed_product_ids: vec!["com.echoisle.coins.60".to_string()],
            native_bridge: crate::config::IapNativeBridgeConfig {
                bin: "/tmp/native-bridge".to_string(),
                args: vec![],
            },
        };
        let (allowed, invalid) =
            normalize_and_validate_allowed_product_ids(&cfg.allowed_product_ids);
        let err = validate_native_bridge_policy(&cfg, true, true, &allowed, &invalid)
            .expect_err("should reject override");
        assert!(err.contains("ECHOISLE_IAP_NATIVE_BRIDGE_RESPONSE_JSON"));
    }

    #[test]
    fn validate_native_bridge_policy_should_block_simulate_arg_in_production() {
        let cfg = IapConfig {
            purchase_mode: "native".to_string(),
            allowed_product_ids: vec!["com.echoisle.coins.60".to_string()],
            native_bridge: crate::config::IapNativeBridgeConfig {
                bin: "/tmp/native-bridge".to_string(),
                args: vec!["--simulate".to_string()],
            },
        };
        let (allowed, invalid) =
            normalize_and_validate_allowed_product_ids(&cfg.allowed_product_ids);
        let err = validate_native_bridge_policy(&cfg, true, false, &allowed, &invalid)
            .expect_err("should reject simulate");
        assert!(err.contains("--simulate"));
    }

    #[test]
    fn validate_native_bridge_policy_should_require_absolute_path_in_production() {
        let cfg = IapConfig {
            purchase_mode: "native".to_string(),
            allowed_product_ids: vec!["com.echoisle.coins.60".to_string()],
            native_bridge: crate::config::IapNativeBridgeConfig {
                bin: "scripts/native-bridge".to_string(),
                args: vec![],
            },
        };
        let (allowed, invalid) =
            normalize_and_validate_allowed_product_ids(&cfg.allowed_product_ids);
        let err = validate_native_bridge_policy(&cfg, true, false, &allowed, &invalid)
            .expect_err("should reject relative path");
        assert!(err.contains("absolute path"));
    }

    #[test]
    fn validate_native_bridge_policy_should_allow_absolute_path_in_production() {
        let cfg = IapConfig {
            purchase_mode: "native".to_string(),
            allowed_product_ids: vec!["com.echoisle.coins.60".to_string()],
            native_bridge: crate::config::IapNativeBridgeConfig {
                bin: "/usr/local/bin/native-bridge".to_string(),
                args: vec![],
            },
        };
        let (allowed, invalid) =
            normalize_and_validate_allowed_product_ids(&cfg.allowed_product_ids);
        validate_native_bridge_policy(&cfg, true, false, &allowed, &invalid)
            .expect("absolute path should pass");
    }

    #[test]
    fn validate_native_bridge_policy_should_require_allowed_products_in_production() {
        let cfg = IapConfig {
            purchase_mode: "native".to_string(),
            allowed_product_ids: vec![],
            native_bridge: crate::config::IapNativeBridgeConfig {
                bin: "/usr/local/bin/native-bridge".to_string(),
                args: vec![],
            },
        };
        let (allowed, invalid) =
            normalize_and_validate_allowed_product_ids(&cfg.allowed_product_ids);
        let err = validate_native_bridge_policy(&cfg, true, false, &allowed, &invalid)
            .expect_err("missing allowlist should fail");
        assert!(err.contains("allowed_product_ids"));
    }

    #[test]
    fn ensure_product_id_allowed_should_reject_non_allowlisted_product() {
        let allowed = vec!["com.echoisle.coins.60".to_string()];
        let err = ensure_product_id_allowed("com.echoisle.coins.120", &allowed)
            .expect_err("not allowlisted should fail");
        assert!(err.contains("not in iap.allowed_product_ids"));
    }
}
