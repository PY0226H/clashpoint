import test from 'node:test';
import assert from 'node:assert/strict';

import { isTauriRuntime, normalizeIapPurchasePayload } from './iap-bridge.js';

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
    product_id: 'com.aicomm.coins.60',
    transaction_id: 'tx-001',
    original_transaction_id: '',
    receipt_data: 'mock_ok_receipt:abc',
    source: 'tauri_mock_bridge',
  });
  assert.deepEqual(payload, {
    productId: 'com.aicomm.coins.60',
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
