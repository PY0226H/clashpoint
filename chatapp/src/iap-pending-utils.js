const PENDING_IAP_STORAGE_KEY = 'aicomm.pendingIapQueue.v1';

function toNonEmptyString(value) {
  const normalized = String(value || '').trim();
  return normalized || '';
}

export function normalizePendingIapItem(raw, nowMs = Date.now()) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return null;
  }
  const productId = toNonEmptyString(raw.productId);
  const transactionId = toNonEmptyString(raw.transactionId);
  const receiptData = toNonEmptyString(raw.receiptData);
  if (!productId || !transactionId || !receiptData) {
    return null;
  }
  const originalTransactionId = toNonEmptyString(raw.originalTransactionId) || null;
  const source = toNonEmptyString(raw.source) || 'unknown';
  const createdAtRaw = Number(raw.createdAt);
  const updatedAtRaw = Number(raw.updatedAt);
  const createdAt = Number.isFinite(createdAtRaw) ? Math.floor(createdAtRaw) : nowMs;
  const updatedAt = Number.isFinite(updatedAtRaw) ? Math.floor(updatedAtRaw) : createdAt;
  const attemptsRaw = Number(raw.attempts);
  const attempts = Number.isFinite(attemptsRaw) ? Math.max(0, Math.floor(attemptsRaw)) : 0;
  const lastError = toNonEmptyString(raw.lastError) || null;
  return {
    productId,
    transactionId,
    originalTransactionId,
    receiptData,
    source,
    createdAt,
    updatedAt,
    attempts,
    lastError,
  };
}

export function sanitizePendingIapQueue(input, nowMs = Date.now()) {
  const arr = Array.isArray(input) ? input : [];
  const byTransaction = new Map();
  for (const item of arr) {
    const normalized = normalizePendingIapItem(item, nowMs);
    if (!normalized) {
      continue;
    }
    const previous = byTransaction.get(normalized.transactionId);
    if (!previous || normalized.updatedAt >= previous.updatedAt) {
      byTransaction.set(normalized.transactionId, normalized);
    }
  }
  return Array.from(byTransaction.values()).sort((a, b) => b.updatedAt - a.updatedAt);
}

export function upsertPendingIap(queue, payload, nowMs = Date.now()) {
  const normalized = normalizePendingIapItem(payload, nowMs);
  if (!normalized) {
    return sanitizePendingIapQueue(queue, nowMs);
  }
  const current = sanitizePendingIapQueue(queue, nowMs);
  const next = current.filter((v) => v.transactionId !== normalized.transactionId);
  next.push(normalized);
  return sanitizePendingIapQueue(next, nowMs);
}

export function registerPendingIapFailure(queue, payload, errorMessage, nowMs = Date.now()) {
  const normalized = normalizePendingIapItem(payload, nowMs);
  if (!normalized) {
    return sanitizePendingIapQueue(queue, nowMs);
  }
  const current = sanitizePendingIapQueue(queue, nowMs);
  const existing = current.find((item) => item.transactionId === normalized.transactionId) || null;
  const err = toNonEmptyString(errorMessage) || 'verify failed';
  const nextItem = {
    ...normalized,
    createdAt: existing?.createdAt ?? normalized.createdAt,
    attempts: (existing?.attempts ?? 0) + 1,
    updatedAt: nowMs,
    lastError: err,
  };
  const next = current.filter((item) => item.transactionId !== normalized.transactionId);
  next.push(nextItem);
  return sanitizePendingIapQueue(next, nowMs);
}

export function settlePendingIapSuccess(queue, transactionId, nowMs = Date.now()) {
  const tx = toNonEmptyString(transactionId);
  if (!tx) {
    return sanitizePendingIapQueue(queue, nowMs);
  }
  return sanitizePendingIapQueue(queue, nowMs).filter((item) => item.transactionId !== tx);
}

export function readPendingIapQueue(storage = globalThis?.localStorage) {
  if (!storage?.getItem) {
    return [];
  }
  const raw = storage.getItem(PENDING_IAP_STORAGE_KEY);
  if (!raw) {
    return [];
  }
  try {
    const parsed = JSON.parse(raw);
    return sanitizePendingIapQueue(parsed);
  } catch (_) {
    return [];
  }
}

export function writePendingIapQueue(queue, storage = globalThis?.localStorage) {
  if (!storage?.setItem) {
    return;
  }
  const normalized = sanitizePendingIapQueue(queue);
  storage.setItem(PENDING_IAP_STORAGE_KEY, JSON.stringify(normalized));
}

export { PENDING_IAP_STORAGE_KEY };
