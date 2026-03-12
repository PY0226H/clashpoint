import test from 'node:test';
import assert from 'node:assert/strict';

import {
  isTauriRuntime,
  normalizeIapNativeBridgeDiagnostics,
  normalizeIapPurchasePayload,
  parseNativeBridgeErrorMessage,
} from './iap-bridge.js';

test('isTauriRuntime should detect runtime markers', () => {
  const previousWindow = globalThis.window;
  try {
    globalThis.window = {};
    assert.equal(isTauriRuntime(), false);
    globalThis.window = { __TAURI_INTERNALS__: {} };
    assert.equal(isTauriRuntime(), true);
  } finally {
    globalThis.window = previousWindow;
  }
});

test('normalizeIapPurchasePayload should normalize snake/camel keys', () => {
  const payload = normalizeIapPurchasePayload({
    product_id: 'com.echoisle.coins.60',
    transaction_id: 'tx-001',
    original_transaction_id: '',
    receipt_data: 'mock_ok_receipt:abc',
    source: 'tauri_mock_bridge',
  });
  assert.deepEqual(payload, {
    productId: 'com.echoisle.coins.60',
    transactionId: 'tx-001',
    originalTransactionId: null,
    receiptData: 'mock_ok_receipt:abc',
    source: 'tauri_mock_bridge',
  });
});

test('normalizeIapPurchasePayload should throw when required fields missing', () => {
  assert.throws(
    () => normalizeIapPurchasePayload({ productId: 'p1', transactionId: 't1' }),
    /missing required fields/,
  );
});

test('parseNativeBridgeErrorMessage should parse structured bridge error', () => {
  const parsed = parseNativeBridgeErrorMessage(
    'native_iap_bridge_error:purchase_pending:purchase is pending',
  );
  assert.deepEqual(parsed, {
    code: 'purchase_pending',
    message: 'purchase is pending',
  });
});

test('parseNativeBridgeErrorMessage should return null for legacy text', () => {
  const parsed = parseNativeBridgeErrorMessage('native iap bridge command failed: status=1');
  assert.equal(parsed, null);
});

test('normalizeIapNativeBridgeDiagnostics should normalize snake/camel keys', () => {
  const normalized = normalizeIapNativeBridgeDiagnostics({
    runtime_env: 'production',
    runtime_is_production: true,
    purchase_mode: 'native',
    allowed_product_ids: ['com.echoisle.coins.60'],
    invalid_allowed_product_ids: [],
    allowed_product_ids_configured: true,
    native_bridge_bin: '/bin/sh',
    native_bridge_args: ['--foo'],
    native_bridge_bin_is_absolute: true,
    native_bridge_bin_exists: true,
    native_bridge_bin_executable: true,
    has_simulate_arg: false,
    json_override_present: false,
    production_policy_ok: true,
    production_policy_error: '',
    ready_for_native_purchase: true,
  });
  assert.deepEqual(normalized, {
    runtimeEnv: 'production',
    runtimeIsProduction: true,
    purchaseMode: 'native',
    allowedProductIds: ['com.echoisle.coins.60'],
    invalidAllowedProductIds: [],
    allowedProductIdsConfigured: true,
    nativeBridgeBin: '/bin/sh',
    nativeBridgeArgs: ['--foo'],
    nativeBridgeBinIsAbsolute: true,
    nativeBridgeBinExists: true,
    nativeBridgeBinExecutable: true,
    hasSimulateArg: false,
    jsonOverridePresent: false,
    productionPolicyOk: true,
    productionPolicyError: null,
    readyForNativePurchase: true,
  });
});

test('normalizeIapNativeBridgeDiagnostics should reject invalid payload', () => {
  assert.throws(
    () => normalizeIapNativeBridgeDiagnostics(null),
    /invalid iap native bridge diagnostics payload/,
  );
});
