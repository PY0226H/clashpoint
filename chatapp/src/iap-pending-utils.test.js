import test from 'node:test';
import assert from 'node:assert/strict';

import {
  computePendingIapRetryDelayMs,
  DEFAULT_PENDING_IAP_RETRY_POLICY,
  DEFAULT_PENDING_IAP_RETENTION_POLICY,
  filterRetryablePendingIap,
  isPendingIapRetryable,
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
  const now = 50_000;
  const queue = sanitizePendingIapQueue([
    buildItem({ transactionId: 'tx-a', updatedAt: now - 3, attempts: 1 }),
    buildItem({ transactionId: 'tx-a', updatedAt: now - 1, attempts: 3 }),
    buildItem({ transactionId: 'tx-b', updatedAt: now - 2 }),
  ], now);
  assert.equal(queue.length, 2);
  assert.equal(queue[0].transactionId, 'tx-a');
  assert.equal(queue[0].attempts, 3);
});

test('sanitizePendingIapQueue should drop stale items by max age policy', () => {
  const now = 2_000_000;
  const queue = sanitizePendingIapQueue(
    [
      buildItem({ transactionId: 'tx-fresh', updatedAt: now - 1_000 }),
      buildItem({
        transactionId: 'tx-stale',
        updatedAt: now - (DEFAULT_PENDING_IAP_RETENTION_POLICY.maxItemAgeMs + 1),
      }),
    ],
    now,
  );
  assert.equal(queue.length, 1);
  assert.equal(queue[0].transactionId, 'tx-fresh');
});

test('sanitizePendingIapQueue should cap queue size and keep latest items', () => {
  const now = 3_000_000;
  const queue = sanitizePendingIapQueue(
    [
      buildItem({ transactionId: 'tx-1', updatedAt: now - 3 }),
      buildItem({ transactionId: 'tx-2', updatedAt: now - 2 }),
      buildItem({ transactionId: 'tx-3', updatedAt: now - 1 }),
    ],
    now,
    { maxQueueSize: 2, maxItemAgeMs: DEFAULT_PENDING_IAP_RETENTION_POLICY.maxItemAgeMs },
  );
  assert.equal(queue.length, 2);
  assert.deepEqual(queue.map((item) => item.transactionId), ['tx-3', 'tx-2']);
});

test('registerPendingIapFailure should upsert and increment attempts', () => {
  const now = 1_700_000_000_000;
  const first = registerPendingIapFailure(
    [],
    buildItem({ transactionId: 'tx-a' }),
    'network',
    now,
  );
  assert.equal(first.length, 1);
  assert.equal(first[0].attempts, 1);
  assert.equal(first[0].nextRetryAt, now + DEFAULT_PENDING_IAP_RETRY_POLICY.baseDelayMs);
  const second = registerPendingIapFailure(
    first,
    buildItem({ transactionId: 'tx-a' }),
    'timeout',
    now + 1_000,
  );
  assert.equal(second.length, 1);
  assert.equal(second[0].attempts, 2);
  assert.equal(second[0].lastError, 'timeout');
  assert.equal(second[0].nextRetryAt, now + 1_000 + (2 * DEFAULT_PENDING_IAP_RETRY_POLICY.baseDelayMs));
});

test('computePendingIapRetryDelayMs should grow exponentially and cap by maxDelay', () => {
  const policy = { baseDelayMs: 100, maxDelayMs: 500, maxAttempts: 9 };
  assert.equal(computePendingIapRetryDelayMs(1, policy), 100);
  assert.equal(computePendingIapRetryDelayMs(2, policy), 200);
  assert.equal(computePendingIapRetryDelayMs(3, policy), 400);
  assert.equal(computePendingIapRetryDelayMs(4, policy), 500);
});

test('isPendingIapRetryable should respect cooldown and maxAttempts', () => {
  const now = 10_000;
  const retryPolicy = { baseDelayMs: 100, maxDelayMs: 1_000, maxAttempts: 3 };
  const item = normalizePendingIapItem(buildItem({
    transactionId: 'tx-cooldown',
    attempts: 1,
    updatedAt: now,
    nextRetryAt: now + 99,
  }));
  assert.equal(isPendingIapRetryable(item, now, retryPolicy), false);
  assert.equal(isPendingIapRetryable(item, now + 100, retryPolicy), true);

  const exhausted = normalizePendingIapItem(buildItem({
    transactionId: 'tx-exhausted',
    attempts: 3,
    updatedAt: now,
    nextRetryAt: now,
  }));
  assert.equal(isPendingIapRetryable(exhausted, now + 1, retryPolicy), false);
});

test('filterRetryablePendingIap should return only due transactions', () => {
  const now = 20_000;
  const retryPolicy = { baseDelayMs: 100, maxDelayMs: 10_000, maxAttempts: 4 };
  const queue = [
    buildItem({ transactionId: 'tx-due', attempts: 1, nextRetryAt: now }),
    buildItem({ transactionId: 'tx-wait', attempts: 1, nextRetryAt: now + 10 }),
    buildItem({ transactionId: 'tx-max', attempts: 4, nextRetryAt: now }),
  ];
  const retryable = filterRetryablePendingIap(queue, now, retryPolicy);
  assert.equal(retryable.length, 1);
  assert.equal(retryable[0].transactionId, 'tx-due');
});

test('registerPendingIapFailure should set nextRetryAt null when max attempts reached', () => {
  const retryPolicy = { baseDelayMs: 100, maxDelayMs: 500, maxAttempts: 2 };
  const now = 30_000;
  const first = registerPendingIapFailure(
    [],
    buildItem({ transactionId: 'tx-limit' }),
    'network',
    now,
    retryPolicy,
  );
  const second = registerPendingIapFailure(
    first,
    buildItem({ transactionId: 'tx-limit' }),
    'still failed',
    now + 1_000,
    retryPolicy,
  );
  assert.equal(second.length, 1);
  assert.equal(second[0].attempts, 2);
  assert.equal(second[0].nextRetryAt, null);
  assert.equal(isPendingIapRetryable(second[0], now + 1_001, retryPolicy), false);
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
