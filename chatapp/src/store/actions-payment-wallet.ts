type NetworkFn = (
  store: unknown,
  method: string,
  url: string,
  data?: unknown,
  headers?: Record<string, string>,
  allowRefreshRetry?: boolean,
) => Promise<{ data?: unknown } | unknown>;

type BuildQueryStringFn = (params?: Record<string, unknown>) => string;
type NormalizeWalletLedgerLimitFn = (limit?: unknown) => number;

function responseData<T = unknown>(response: unknown): T | undefined {
  const value = response as { data?: T } | undefined;
  return value?.data;
}

function bearerHeader(token?: string | null) {
  return {
    Authorization: `Bearer ${token || ''}`,
  };
}

export async function actionListIapProducts({
  network,
  store,
  buildQueryString,
  token,
  activeOnly = true,
}: {
  network: NetworkFn;
  store: unknown;
  buildQueryString: BuildQueryStringFn;
  token?: string | null;
  activeOnly?: boolean;
}) {
  const suffix = buildQueryString({ activeOnly });
  const response = await network(store, 'get', `/pay/iap/products${suffix}`, null, bearerHeader(token));
  return responseData(response) || [];
}

export async function actionVerifyIapOrder({
  network,
  store,
  token,
  productId,
  transactionId,
  originalTransactionId = null,
  receiptData,
}: {
  network: NetworkFn;
  store: unknown;
  token?: string | null;
  productId?: string | null;
  transactionId?: string | null;
  originalTransactionId?: string | null;
  receiptData?: string | null;
}) {
  if (!productId || !String(productId).trim()) {
    throw new Error('productId is required');
  }
  if (!transactionId || !String(transactionId).trim()) {
    throw new Error('transactionId is required');
  }
  if (!receiptData || !String(receiptData).trim()) {
    throw new Error('receiptData is required');
  }
  const response = await network(
    store,
    'post',
    '/pay/iap/verify',
    {
      productId: String(productId).trim(),
      transactionId: String(transactionId).trim(),
      originalTransactionId: originalTransactionId == null ? null : String(originalTransactionId).trim() || null,
      receiptData: String(receiptData).trim(),
    },
    bearerHeader(token),
  );
  return responseData(response);
}

export async function actionGetIapOrderByTransaction({
  network,
  store,
  buildQueryString,
  token,
  transactionId,
}: {
  network: NetworkFn;
  store: unknown;
  buildQueryString: BuildQueryStringFn;
  token?: string | null;
  transactionId?: string | null;
}) {
  if (!transactionId || !String(transactionId).trim()) {
    throw new Error('transactionId is required');
  }
  const suffix = buildQueryString({
    transactionId: String(transactionId).trim(),
  });
  const response = await network(
    store,
    'get',
    `/pay/iap/orders/by-transaction${suffix}`,
    null,
    bearerHeader(token),
  );
  return responseData(response);
}

export async function actionFetchWalletBalance({
  network,
  store,
  token,
}: {
  network: NetworkFn;
  store: unknown;
  token?: string | null;
}) {
  const response = await network(store, 'get', '/pay/wallet', null, bearerHeader(token));
  return responseData(response);
}

export async function actionListWalletLedger({
  network,
  store,
  buildQueryString,
  normalizeWalletLedgerLimit,
  token,
  lastId = null,
  limit = 20,
}: {
  network: NetworkFn;
  store: unknown;
  buildQueryString: BuildQueryStringFn;
  normalizeWalletLedgerLimit: NormalizeWalletLedgerLimitFn;
  token?: string | null;
  lastId?: number | string | null;
  limit?: number | string | null;
}) {
  const suffix = buildQueryString({
    lastId,
    limit: normalizeWalletLedgerLimit(limit),
  });
  const response = await network(store, 'get', `/pay/wallet/ledger${suffix}`, null, bearerHeader(token));
  return responseData(response) || [];
}

export async function actionPinDebateMessage({
  network,
  store,
  token,
  messageId,
  pinSeconds,
  idempotencyKey,
}: {
  network: NetworkFn;
  store: unknown;
  token?: string | null;
  messageId?: number | string | null;
  pinSeconds?: number | string | null;
  idempotencyKey?: string | null;
}) {
  if (!messageId) {
    throw new Error('messageId is required');
  }
  if (!pinSeconds) {
    throw new Error('pinSeconds is required');
  }
  if (!idempotencyKey || !String(idempotencyKey).trim()) {
    throw new Error('idempotencyKey is required');
  }
  const response = await network(
    store,
    'post',
    `/debate/messages/${messageId}/pin`,
    {
      pinSeconds,
      idempotencyKey: String(idempotencyKey).trim(),
    },
    bearerHeader(token),
  );
  return responseData(response);
}
