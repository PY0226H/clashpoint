import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildMockReceiptData,
  buildMockTransactionId,
  normalizeWalletLedgerLimit,
} from './wallet-utils.js';

test('normalizeWalletLedgerLimit should clamp into [1, 100]', () => {
  assert.equal(normalizeWalletLedgerLimit(undefined), 20);
  assert.equal(normalizeWalletLedgerLimit(0), 1);
  assert.equal(normalizeWalletLedgerLimit(200), 100);
  assert.equal(normalizeWalletLedgerLimit(19.8), 19);
});

test('buildMockTransactionId should include product and prefix', () => {
  const tx = buildMockTransactionId('com.echoisle.coins.60');
  assert.equal(typeof tx, 'string');
  assert.equal(tx.startsWith('mock-tx-com.echoisle.coins.60-'), true);
});

test('buildMockReceiptData should include product and mock prefix', () => {
  const receipt = buildMockReceiptData('com.echoisle.coins.60');
  assert.equal(typeof receipt, 'string');
  assert.equal(receipt.startsWith('mock_ok_receipt:com.echoisle.coins.60:'), true);
});
