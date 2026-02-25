import test from 'node:test';
import assert from 'node:assert/strict';

import {
  PENDING_IAP_STORAGE_KEY,
  normalizePendingIapItem,
  readPendingIapQueue,
  registerPendingIapFailure,
  sanitizePendingIapQueue,
  settlePendingIapSuccess,
  upsertPendingIap,
  writePendingIapQueue,
} from './iap-pending-utils.js';

function buildItem(overrides = {}) {
  return {
    productId: 'com.aicomm.coins.60',
    transactionId: 'tx-1',
    originalTransactionId: null,
    receiptData: 'mock_ok_receipt:1',
    source: 'tauri_mock_bridge',
    ...overrides,
  };
}

test('normalizePendingIapItem should reject invalid payload', () => {
  assert.equal(normalizePendingIapItem(null), null);
  assert.equal(normalizePendingIapItem({}), null);
});

test('sanitizePendingIapQueue should dedupe by transaction and keep latest updatedAt', () => {
  const queue = sanitizePendingIapQueue([
    buildItem({ transactionId: 'tx-a', updatedAt: 1, attempts: 1 }),
    buildItem({ transactionId: 'tx-a', updatedAt: 10, attempts: 3 }),
    buildItem({ transactionId: 'tx-b', updatedAt: 5 }),
  ]);
  assert.equal(queue.length, 2);
  assert.equal(queue[0].transactionId, 'tx-a');
  assert.equal(queue[0].attempts, 3);
});

test('registerPendingIapFailure should upsert and increment attempts', () => {
  const first = registerPendingIapFailure([], buildItem({ transactionId: 'tx-a' }), 'network');
  assert.equal(first.length, 1);
  assert.equal(first[0].attempts, 1);
  const second = registerPendingIapFailure(first, buildItem({ transactionId: 'tx-a' }), 'timeout');
  assert.equal(second.length, 1);
  assert.equal(second[0].attempts, 2);
  assert.equal(second[0].lastError, 'timeout');
});

test('settlePendingIapSuccess should remove transaction', () => {
  const queue = [
    normalizePendingIapItem(buildItem({ transactionId: 'tx-a' })),
    normalizePendingIapItem(buildItem({ transactionId: 'tx-b' })),
  ];
  const next = settlePendingIapSuccess(queue, 'tx-a');
  assert.equal(next.length, 1);
  assert.equal(next[0].transactionId, 'tx-b');
});

test('read/write pending queue should work with storage', () => {
  const storage = (() => {
    const data = new Map();
    return {
      getItem(key) {
        return data.has(key) ? data.get(key) : null;
      },
      setItem(key, value) {
        data.set(key, String(value));
      },
    };
  })();

  const queue = upsertPendingIap([], buildItem({ transactionId: 'tx-c' }));
  writePendingIapQueue(queue, storage);
  const loaded = readPendingIapQueue(storage);
  assert.equal(loaded.length, 1);
  assert.equal(loaded[0].transactionId, 'tx-c');
  assert.equal(typeof storage.getItem(PENDING_IAP_STORAGE_KEY), 'string');
});
