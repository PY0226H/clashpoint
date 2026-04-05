import { http, toApiError } from "@echoisle/api-client";

export type WalletBalanceOutput = {
  userId: number;
  balance: number;
  walletRevision: string;
  walletInitialized: boolean;
};

export type WalletLedgerItem = {
  id: number;
  orderId?: number | null;
  entryType: string;
  amountDelta: number;
  balanceAfter: number;
  idempotencyKey: string;
  metadata: Record<string, unknown>;
  createdAt: string;
};

export type WalletLedgerListOutput = {
  items: WalletLedgerItem[];
  nextLastId?: number | null;
  hasMore: boolean;
};

export type IapProduct = {
  productId: string;
  coins: number;
  isActive: boolean;
};

export type ListIapProductsOutput = {
  items: IapProduct[];
  revision?: string | null;
  emptyReason?: "all_inactive" | "no_config" | null;
};

export type IapOrderSnapshot = {
  orderId: number;
  status: string;
  verifyMode: string;
  verifyReason?: string | null;
  productId: string;
  coins: number;
  credited: boolean;
};

export type GetIapOrderByTransactionOutput = {
  found: boolean;
  order?: IapOrderSnapshot | null;
  probeStatus?: "not_found" | "pending_credit" | "verified_credited" | "conflict" | null;
  nextRetryAfterMs?: number | null;
};

export function toWalletDomainError(error: unknown): string {
  return toApiError(error);
}

export async function getWalletBalance(): Promise<WalletBalanceOutput> {
  const response = await http.get<WalletBalanceOutput>("/pay/wallet");
  return response.data;
}

export async function listWalletLedger(input?: {
  lastId?: number;
  limit?: number;
}): Promise<WalletLedgerListOutput> {
  const response = await http.get<WalletLedgerListOutput>("/pay/wallet/ledger", {
    params: {
      lastId: input?.lastId,
      limit: input?.limit ?? 20
    }
  });
  return response.data;
}

export async function listIapProducts(input?: {
  activeOnly?: boolean;
}): Promise<ListIapProductsOutput> {
  const response = await http.get<ListIapProductsOutput>("/pay/iap/products", {
    params: {
      activeOnly: input?.activeOnly ?? true
    }
  });
  return response.data;
}

export async function getIapOrderByTransaction(
  transactionId: string
): Promise<GetIapOrderByTransactionOutput> {
  const normalized = String(transactionId || "").trim();
  const response = await http.get<GetIapOrderByTransactionOutput>("/pay/iap/orders/by-transaction", {
    params: {
      transactionId: normalized
    }
  });
  return response.data;
}
