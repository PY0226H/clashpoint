import { invoke } from '@tauri-apps/api/core';

type LoosePayload = Record<string, unknown>;

type IapPurchasePayload = {
  productId: string;
  transactionId: string;
  originalTransactionId: string | null;
  receiptData: string;
  source: string;
};

type NativeBridgeError = {
  code: string;
  message: string;
};

type IapNativeBridgeDiagnostics = {
  runtimeEnv: unknown;
  runtimeIsProduction: boolean;
  purchaseMode: string;
  allowedProductIds: string[];
  invalidAllowedProductIds: string[];
  allowedProductIdsConfigured: boolean;
  nativeBridgeBin: string;
  nativeBridgeArgs: string[];
  nativeBridgeBinIsAbsolute: boolean;
  nativeBridgeBinExists: boolean;
  nativeBridgeBinExecutable: boolean;
  hasSimulateArg: boolean;
  jsonOverridePresent: boolean;
  productionPolicyOk: boolean;
  productionPolicyError: string | null;
  readyForNativePurchase: boolean;
};

export function isTauriRuntime(): boolean {
  if (typeof window === 'undefined' || !window) {
    return false;
  }
  const runtimeWindow = window as Window & {
    __TAURI_INTERNALS__?: unknown;
    __TAURI__?: unknown;
  };
  return Boolean(runtimeWindow.__TAURI_INTERNALS__ || runtimeWindow.__TAURI__);
}

export function normalizeIapPurchasePayload(payload: LoosePayload | null | undefined): IapPurchasePayload {
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

export function parseNativeBridgeErrorMessage(message: unknown): NativeBridgeError | null {
  const raw = String(message || '').trim();
  const prefix = 'native_iap_bridge_error:';
  if (!raw.startsWith(prefix)) {
    return null;
  }
  const content = raw.slice(prefix.length);
  const sep = content.indexOf(':');
  if (sep <= 0) {
    return null;
  }
  const code = content.slice(0, sep).trim();
  const errorMessage = content.slice(sep + 1).trim();
  if (!code || !errorMessage) {
    return null;
  }
  return { code, message: errorMessage };
}

export function normalizeIapNativeBridgeDiagnostics(
  payload: LoosePayload | null | undefined,
): IapNativeBridgeDiagnostics {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    throw new Error('invalid iap native bridge diagnostics payload');
  }
  const allowedProductIdsRaw = payload.allowedProductIds ?? payload.allowed_product_ids;
  const invalidAllowedProductIdsRaw =
    payload.invalidAllowedProductIds ?? payload.invalid_allowed_product_ids;
  const nativeBridgeArgsRaw = payload.nativeBridgeArgs ?? payload.native_bridge_args;
  return {
    runtimeEnv: payload.runtimeEnv ?? payload.runtime_env ?? null,
    runtimeIsProduction: Boolean(payload.runtimeIsProduction ?? payload.runtime_is_production),
    purchaseMode: String(payload.purchaseMode ?? payload.purchase_mode ?? '').trim() || 'unknown',
    allowedProductIds: Array.isArray(allowedProductIdsRaw)
      ? (allowedProductIdsRaw as unknown[]).map((v) => String(v))
      : [],
    invalidAllowedProductIds: Array.isArray(invalidAllowedProductIdsRaw)
      ? (invalidAllowedProductIdsRaw as unknown[]).map((v) => String(v))
      : [],
    allowedProductIdsConfigured: Boolean(
      payload.allowedProductIdsConfigured ?? payload.allowed_product_ids_configured,
    ),
    nativeBridgeBin: String(payload.nativeBridgeBin ?? payload.native_bridge_bin ?? '').trim(),
    nativeBridgeArgs: Array.isArray(nativeBridgeArgsRaw)
      ? (nativeBridgeArgsRaw as unknown[]).map((v) => String(v))
      : [],
    nativeBridgeBinIsAbsolute: Boolean(
      payload.nativeBridgeBinIsAbsolute ?? payload.native_bridge_bin_is_absolute,
    ),
    nativeBridgeBinExists: Boolean(payload.nativeBridgeBinExists ?? payload.native_bridge_bin_exists),
    nativeBridgeBinExecutable: Boolean(
      payload.nativeBridgeBinExecutable ?? payload.native_bridge_bin_executable,
    ),
    hasSimulateArg: Boolean(payload.hasSimulateArg ?? payload.has_simulate_arg),
    jsonOverridePresent: Boolean(payload.jsonOverridePresent ?? payload.json_override_present),
    productionPolicyOk: Boolean(payload.productionPolicyOk ?? payload.production_policy_ok),
    productionPolicyError: String(
      payload.productionPolicyError ?? payload.production_policy_error ?? '',
    ).trim() || null,
    readyForNativePurchase: Boolean(
      payload.readyForNativePurchase ?? payload.ready_for_native_purchase,
    ),
  };
}

export async function getIapNativeBridgeDiagnostics(): Promise<IapNativeBridgeDiagnostics> {
  if (!isTauriRuntime()) {
    throw new Error('tauri runtime is unavailable');
  }
  const payload = await invoke('iap_get_native_bridge_diagnostics') as LoosePayload;
  return normalizeIapNativeBridgeDiagnostics(payload);
}

export async function purchaseIapViaTauri(productId: unknown): Promise<IapPurchasePayload> {
  if (!isTauriRuntime()) {
    throw new Error('tauri runtime is unavailable');
  }
  const normalizedProductId = String(productId || '').trim();
  if (!normalizedProductId) {
    throw new Error('productId is required');
  }
  try {
    const payload = await invoke('iap_purchase_product', { productId: normalizedProductId }) as LoosePayload;
    return normalizeIapPurchasePayload(payload);
  } catch (error) {
    const message = error instanceof Error
      ? String(error.message || '').trim()
      : String(error || '').trim();
    const parsed = parseNativeBridgeErrorMessage(message);
    if (parsed) {
      const wrapped = new Error(parsed.message) as Error & { code?: string };
      wrapped.code = parsed.code;
      throw wrapped;
    }
    throw error;
  }
}
