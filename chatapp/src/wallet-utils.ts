export function normalizeWalletLedgerLimit(limit, defaultValue = 20) {
  const fallback = Number.isFinite(defaultValue) ? Math.floor(defaultValue) : 20;
  const parsed = Number(limit);
  if (!Number.isFinite(parsed)) {
    return Math.min(100, Math.max(1, fallback));
  }
  return Math.min(100, Math.max(1, Math.floor(parsed)));
}

export function buildMockTransactionId(productId = 'unknown') {
  const product = String(productId).trim() || 'unknown';
  const random = Math.random().toString(36).slice(2, 10);
  return `mock-tx-${product}-${Date.now()}-${random}`;
}

export function buildMockReceiptData(productId = 'unknown') {
  const product = String(productId).trim() || 'unknown';
  return `mock_ok_receipt:${product}:${Date.now()}`;
}
