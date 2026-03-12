# iap-storekit-bridge

Command-line native bridge for Tauri `purchase_mode=native`.

## Purpose

`chatapp/src-tauri` calls an external command and expects JSON payload:

```json
{
  "productId": "com.acme.coins.100",
  "transactionId": "1234567890",
  "originalTransactionId": "1234567890",
  "receiptData": "<base64_receipt>",
  "source": "iap_storekit_bridge_storekit2"
}
```

This package provides that bridge with StoreKit2 purchase flow.

## Build

```bash
cd /Users/panyihang/Documents/EchoIsle/chatapp/native/iap-storekit-bridge
xcrun swift build -c release
```

Binary path:

`/Users/panyihang/Documents/EchoIsle/chatapp/native/iap-storekit-bridge/.build/release/iap-storekit-bridge`

Quick launcher (auto build when missing):

`/Users/panyihang/Documents/EchoIsle/chatapp/native/iap-storekit-bridge/run.sh`

## Run

Real purchase:

```bash
./.build/release/iap-storekit-bridge --product-id com.acme.coins.100
```

Simulated payload (for local debug / CI):

```bash
./.build/release/iap-storekit-bridge --product-id com.acme.coins.100 --simulate
```

Or by env:

```bash
ECHOISLE_IAP_SIMULATE=1 ./.build/release/iap-storekit-bridge --product-id com.acme.coins.100
```

## Receipt behavior

- If `ECHOISLE_IAP_RECEIPT_B64` is set and non-empty, bridge uses it directly.
- Otherwise bridge tries `Bundle.main.appStoreReceiptURL` and base64 encodes the file.

## Tauri config snippet

`app.yml`:

```yaml
iap:
  purchase_mode: "native"
  allowed_product_ids:
    - "com.echoisle.coins.60"
    - "com.echoisle.coins.120"
  native_bridge:
    bin: "/Users/panyihang/Documents/EchoIsle/chatapp/native/iap-storekit-bridge/run.sh"
    args: []
```

Production constraints (`chatapp/src-tauri`):

- `ECHOISLE_IAP_NATIVE_BRIDGE_RESPONSE_JSON` is forbidden in production runtime.
- `iap.native_bridge.args` cannot include `--simulate` in production runtime.
- `iap.native_bridge.bin` must be an absolute path in production runtime.
- `iap.allowed_product_ids` must be non-empty in production runtime.

## Error contract

When bridge exits non-zero, it prints structured JSON to stderr:

```json
{
  "code": "purchase_pending",
  "error": "purchase is pending"
}
```

Typical `code` values:
- `purchase_pending`
- `purchase_cancelled`
- `product_not_found`
- `purchase_unverified`
- `receipt_missing`

`chatapp/src-tauri` converts this to a typed command error and `chatapp/src/iap-bridge.js` maps it to frontend-friendly messages for true-device debugging.
