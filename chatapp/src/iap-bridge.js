import { invoke } from '@tauri-apps/api/core';

export function isTauriRuntime() {
  if (typeof window === 'undefined' || !window) {
    return false;
  }
  return Boolean(window.__TAURI_INTERNALS__ || window.__TAURI__);
}

export function normalizeIapPurchasePayload(payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    throw new Error('invalid iap purchase payload');
  }
  const productId = String(payload.productId || payload.product_id || '').trim();
  const transactionId = String(payload.transactionId || payload.transaction_id || '').trim();
  const receiptData = String(payload.receiptData || payload.receipt_data || '').trim();
  const originalTransactionIdRaw = payload.originalTransactionId ?? payload.original_transaction_id;
  const source = String(payload.source || '').trim() || 'tauri';
  if (!productId || !transactionId || !receiptData) {
    throw new Error('iap purchase payload missing required fields');
  }
  return {
    productId,
    transactionId,
    originalTransactionId: originalTransactionIdRaw == null
      ? null
      : String(originalTransactionIdRaw).trim() || null,
    receiptData,
    source,
  };
}

export async function purchaseIapViaTauri(productId) {
  if (!isTauriRuntime()) {
    throw new Error('tauri runtime is unavailable');
  }
  const normalizedProductId = String(productId || '').trim();
  if (!normalizedProductId) {
    throw new Error('productId is required');
  }
  const payload = await invoke('iap_purchase_product', { productId: normalizedProductId });
  return normalizeIapPurchasePayload(payload);
}
