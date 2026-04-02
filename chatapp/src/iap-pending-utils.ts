const PENDING_IAP_STORAGE_KEY = 'echoisle.pendingIapQueue.v1';
const DEFAULT_PENDING_IAP_RETRY_POLICY = Object.freeze({
  baseDelayMs: 30_000,
  maxDelayMs: 30 * 60_000,
  maxAttempts: 6,
});
const DEFAULT_PENDING_IAP_RETENTION_POLICY = Object.freeze({
  maxQueueSize: 200,
  maxItemAgeMs: 30 * 24 * 60 * 60_000,
});

function toNonEmptyString(value: unknown): string {
  const normalized = String(value || '').trim();
  return normalized || '';
}

function normalizePositiveInt(
  value: unknown,
  fallback: number,
  { min = 1, max = Number.MAX_SAFE_INTEGER }: { min?: number; max?: number } = {},
): number {
  const raw = Number(value);
  if (!Number.isFinite(raw)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, Math.floor(raw)));
}

function normalizeRetryPolicy(policy: any = {}) {
  const baseDelayMs = normalizePositiveInt(
    policy.baseDelayMs,
    DEFAULT_PENDING_IAP_RETRY_POLICY.baseDelayMs,
    { min: 1, max: 24 * 60 * 60_000 },
  );
  const maxDelayMs = normalizePositiveInt(
    policy.maxDelayMs,
    DEFAULT_PENDING_IAP_RETRY_POLICY.maxDelayMs,
    { min: baseDelayMs, max: 7 * 24 * 60 * 60_000 },
  );
  const maxAttempts = normalizePositiveInt(
    policy.maxAttempts,
    DEFAULT_PENDING_IAP_RETRY_POLICY.maxAttempts,
    { min: 1, max: 100 },
  );
  return {
    baseDelayMs,
    maxDelayMs,
    maxAttempts,
  };
}

function normalizeRetentionPolicy(policy: any = {}) {
  const maxQueueSize = normalizePositiveInt(
    policy.maxQueueSize,
    DEFAULT_PENDING_IAP_RETENTION_POLICY.maxQueueSize,
    { min: 1, max: 5_000 },
  );
  const maxItemAgeMs = normalizePositiveInt(
    policy.maxItemAgeMs,
    DEFAULT_PENDING_IAP_RETENTION_POLICY.maxItemAgeMs,
    { min: 60_000, max: 365 * 24 * 60 * 60_000 },
  );
  return {
    maxQueueSize,
    maxItemAgeMs,
  };
}

export function computePendingIapRetryDelayMs(attempts: unknown, retryPolicy: any = {}) {
  const { baseDelayMs, maxDelayMs } = normalizeRetryPolicy(retryPolicy);
  const normalizedAttempts = normalizePositiveInt(attempts, 1);
  const exp = Math.max(0, normalizedAttempts - 1);
  const rawDelay = baseDelayMs * (2 ** exp);
  if (!Number.isFinite(rawDelay)) {
    return maxDelayMs;
  }
  return Math.min(maxDelayMs, Math.floor(rawDelay));
}

export function normalizePendingIapItem(raw: any, nowMs = Date.now()) {
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
  let nextRetryAt = updatedAt;
  if (raw.nextRetryAt === null) {
    nextRetryAt = null;
  } else {
    const nextRetryAtRaw = Number(raw.nextRetryAt);
    if (Number.isFinite(nextRetryAtRaw)) {
      nextRetryAt = Math.max(0, Math.floor(nextRetryAtRaw));
    }
  }
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
    nextRetryAt,
    attempts,
    lastError,
  };
}

export function sanitizePendingIapQueue(
  input: unknown,
  nowMs = Date.now(),
  retentionPolicyInput: any = {},
) {
  const arr = Array.isArray(input) ? input : [];
  const retentionPolicy = normalizeRetentionPolicy(retentionPolicyInput);
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
  return Array.from(byTransaction.values())
    .filter((item) => (nowMs - item.updatedAt) <= retentionPolicy.maxItemAgeMs)
    .sort((a, b) => b.updatedAt - a.updatedAt)
    .slice(0, retentionPolicy.maxQueueSize);
}

export function upsertPendingIap(queue: unknown, payload: any, nowMs = Date.now()) {
  const normalized = normalizePendingIapItem(payload, nowMs);
  if (!normalized) {
    return sanitizePendingIapQueue(queue, nowMs);
  }
  const current = sanitizePendingIapQueue(queue, nowMs);
  const next = current.filter((v) => v.transactionId !== normalized.transactionId);
  next.push(normalized);
  return sanitizePendingIapQueue(next, nowMs);
}

export function registerPendingIapFailure(
  queue: unknown,
  payload: any,
  errorMessage: unknown,
  nowMs = Date.now(),
  retryPolicyInput: any = {},
) {
  const normalized = normalizePendingIapItem(payload, nowMs);
  if (!normalized) {
    return sanitizePendingIapQueue(queue, nowMs);
  }
  const current = sanitizePendingIapQueue(queue, nowMs);
  const existing = current.find((item) => item.transactionId === normalized.transactionId) || null;
  const retryPolicy = normalizeRetryPolicy(retryPolicyInput);
  const err = toNonEmptyString(errorMessage) || 'verify failed';
  const attempts = (existing?.attempts ?? 0) + 1;
  const maxAttemptsReached = attempts >= retryPolicy.maxAttempts;
  const nextItem = {
    ...normalized,
    createdAt: existing?.createdAt ?? normalized.createdAt,
    attempts,
    updatedAt: nowMs,
    nextRetryAt: maxAttemptsReached
      ? null
      : nowMs + computePendingIapRetryDelayMs(attempts, retryPolicy),
    lastError: maxAttemptsReached ? `${err} (max attempts reached)` : err,
  };
  const next = current.filter((item) => item.transactionId !== normalized.transactionId);
  next.push(nextItem);
  return sanitizePendingIapQueue(next, nowMs);
}

export function settlePendingIapSuccess(queue: unknown, transactionId: unknown, nowMs = Date.now()) {
  const tx = toNonEmptyString(transactionId);
  if (!tx) {
    return sanitizePendingIapQueue(queue, nowMs);
  }
  return sanitizePendingIapQueue(queue, nowMs).filter((item) => item.transactionId !== tx);
}

export function isPendingIapRetryable(item: unknown, nowMs = Date.now(), retryPolicy: any = {}) {
  const normalized = normalizePendingIapItem(item, nowMs);
  if (!normalized) {
    return false;
  }
  if (isPendingIapMaxAttemptsReached(normalized, retryPolicy)) {
    return false;
  }
  if (normalized.nextRetryAt == null) {
    return false;
  }
  return normalized.nextRetryAt <= nowMs;
}

export function isPendingIapMaxAttemptsReached(item: unknown, retryPolicy: any = {}) {
  const normalized = normalizePendingIapItem(item);
  if (!normalized) {
    return false;
  }
  const { maxAttempts } = normalizeRetryPolicy(retryPolicy);
  return normalized.attempts >= maxAttempts;
}

export function filterRetryablePendingIap(queue: unknown, nowMs = Date.now(), retryPolicy: any = {}) {
  return sanitizePendingIapQueue(queue, nowMs).filter((item) => (
    isPendingIapRetryable(item, nowMs, retryPolicy)
  ));
}

export function resetPendingIapRetry(
  queue: unknown,
  transactionId: unknown,
  nowMs = Date.now(),
  retryPolicy: any = {},
) {
  const tx = toNonEmptyString(transactionId);
  const current = sanitizePendingIapQueue(queue, nowMs);
  if (!tx) {
    return current;
  }
  const target = current.find((item) => item.transactionId === tx);
  if (!target) {
    return current;
  }
  const nextItem = {
    ...target,
    attempts: 0,
    updatedAt: nowMs,
    nextRetryAt: nowMs,
    lastError: `manually reset at ${new Date(nowMs).toISOString()}`,
  };
  if (isPendingIapMaxAttemptsReached(target, retryPolicy)) {
    nextItem.lastError = null;
  }
  const next = current.filter((item) => item.transactionId !== tx);
  next.push(nextItem);
  return sanitizePendingIapQueue(next, nowMs);
}

export function removePendingIapByTransaction(queue: unknown, transactionId: unknown, nowMs = Date.now()) {
  const tx = toNonEmptyString(transactionId);
  const current = sanitizePendingIapQueue(queue, nowMs);
  if (!tx) {
    return current;
  }
  return current.filter((item) => item.transactionId !== tx);
}

export function removeExhaustedPendingIap(
  queue: unknown,
  nowMs = Date.now(),
  retryPolicy: any = {},
) {
  return sanitizePendingIapQueue(queue, nowMs).filter(
    (item) => !isPendingIapMaxAttemptsReached(item, retryPolicy),
  );
}

export function readPendingIapQueue(
  storage:
    | { getItem?: (key: string) => string | null }
    | null
    | undefined = globalThis?.localStorage as { getItem?: (key: string) => string | null } | undefined,
) {
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

export function writePendingIapQueue(
  queue: unknown,
  storage:
    | { setItem?: (key: string, value: string) => void }
    | null
    | undefined = globalThis?.localStorage as
    | { setItem?: (key: string, value: string) => void }
    | undefined,
) {
  if (!storage?.setItem) {
    return;
  }
  const normalized = sanitizePendingIapQueue(queue);
  storage.setItem(PENDING_IAP_STORAGE_KEY, JSON.stringify(normalized));
}

export {
  PENDING_IAP_STORAGE_KEY,
  DEFAULT_PENDING_IAP_RETRY_POLICY,
  DEFAULT_PENDING_IAP_RETENTION_POLICY,
};
