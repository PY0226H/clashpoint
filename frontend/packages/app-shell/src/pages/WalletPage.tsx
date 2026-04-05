import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  getIapOrderByTransaction,
  getWalletBalance,
  listIapProducts,
  listWalletLedger,
  toWalletDomainError,
  type WalletLedgerItem
} from "@echoisle/wallet-domain";
import { Button, InlineHint, SectionTitle, TextField } from "@echoisle/ui";

const LEDGER_LIMIT = 20;

function formatUtc(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleString();
}

function mergeLedgerEntries(current: WalletLedgerItem[], incoming: WalletLedgerItem[]): WalletLedgerItem[] {
  const map = new Map<number, WalletLedgerItem>();
  for (const item of current) {
    map.set(item.id, item);
  }
  for (const item of incoming) {
    map.set(item.id, item);
  }
  return [...map.values()].sort((a, b) => b.id - a.id);
}

export function WalletPage() {
  const [ledgerItems, setLedgerItems] = useState<WalletLedgerItem[]>([]);
  const [nextLastId, setNextLastId] = useState<number | null>(null);
  const [hasMoreLedger, setHasMoreLedger] = useState(false);
  const [ledgerLoadingMore, setLedgerLoadingMore] = useState(false);
  const [probeInput, setProbeInput] = useState("");
  const [pageHint, setPageHint] = useState<string | null>(null);

  const balanceQuery = useQuery({
    queryKey: ["wallet-balance"],
    queryFn: () => getWalletBalance()
  });

  const productsQuery = useQuery({
    queryKey: ["iap-products"],
    queryFn: () => listIapProducts({ activeOnly: true })
  });

  const ledgerQuery = useQuery({
    queryKey: ["wallet-ledger", LEDGER_LIMIT],
    queryFn: () => listWalletLedger({ limit: LEDGER_LIMIT })
  });

  useEffect(() => {
    if (!ledgerQuery.data) {
      return;
    }
    setLedgerItems((current) => mergeLedgerEntries(current, ledgerQuery.data.items));
    setNextLastId(ledgerQuery.data.nextLastId ?? null);
    setHasMoreLedger(Boolean(ledgerQuery.data.hasMore));
  }, [ledgerQuery.data]);

  const probeMutation = useMutation({
    mutationFn: async (transactionId: string) => getIapOrderByTransaction(transactionId),
    onError: (error) => {
      setPageHint(toWalletDomainError(error));
    }
  });

  const loadOlderLedger = async () => {
    if (ledgerLoadingMore || !hasMoreLedger || !nextLastId) {
      return;
    }
    setLedgerLoadingMore(true);
    try {
      const output = await listWalletLedger({ lastId: nextLastId, limit: LEDGER_LIMIT });
      setLedgerItems((current) => mergeLedgerEntries(current, output.items));
      setNextLastId(output.nextLastId ?? null);
      setHasMoreLedger(Boolean(output.hasMore));
    } catch (error) {
      setPageHint(toWalletDomainError(error));
    } finally {
      setLedgerLoadingMore(false);
    }
  };

  const probeSummary = useMemo(() => {
    if (!probeMutation.data) {
      return null;
    }
    if (!probeMutation.data.found || !probeMutation.data.order) {
      return "Order not found.";
    }
    return `Order #${probeMutation.data.order.orderId} | ${probeMutation.data.order.productId} | status=${probeMutation.data.order.status} | credited=${String(probeMutation.data.order.credited)}`;
  }, [probeMutation.data]);

  return (
    <section className="echo-wallet-page">
      <header className="echo-wallet-header">
        <SectionTitle>Wallet & Top-Up</SectionTitle>
        <p>Phase 5 wallet slice: live balance, product list, ledger pagination and order probe.</p>
      </header>

      <section className="echo-lobby-summary">
        <article>
          <strong>{balanceQuery.data?.balance ?? 0}</strong>
          <span>Current Coins</span>
        </article>
        <article>
          <strong>{balanceQuery.data?.walletInitialized ? "YES" : "NO"}</strong>
          <span>Wallet Ready</span>
        </article>
        <article>
          <strong>{productsQuery.data?.items.length ?? 0}</strong>
          <span>Top-Up Products</span>
        </article>
      </section>

      <section className="echo-lobby-panel">
        <h3>Top-Up Product Catalog</h3>
        {productsQuery.isLoading ? <InlineHint>Loading products...</InlineHint> : null}
        {productsQuery.isError ? <p className="echo-error">{toWalletDomainError(productsQuery.error)}</p> : null}
        <div className="echo-wallet-products">
          {(productsQuery.data?.items || []).map((product) => (
            <article className="echo-topic-item" key={product.productId}>
              <h4>{product.productId}</h4>
              <InlineHint>Coins: {product.coins}</InlineHint>
              <InlineHint>Status: {product.isActive ? "active" : "inactive"}</InlineHint>
            </article>
          ))}
          {!productsQuery.isLoading && (productsQuery.data?.items.length || 0) === 0 ? (
            <InlineHint>No products configured yet.</InlineHint>
          ) : null}
        </div>
      </section>

      <section className="echo-lobby-panel">
        <h3>Transaction Probe</h3>
        <div className="echo-wallet-probe-row">
          <TextField
            aria-label="Transaction ID"
            onChange={(event) => setProbeInput(event.target.value)}
            placeholder="transaction id"
            value={probeInput}
          />
          <Button
            disabled={probeMutation.isPending || !probeInput.trim()}
            onClick={() => probeMutation.mutate(probeInput)}
            type="button"
          >
            {probeMutation.isPending ? "Probing..." : "Probe Order"}
          </Button>
        </div>
        {probeSummary ? <InlineHint>{probeSummary}</InlineHint> : null}
        {probeMutation.data?.probeStatus ? <InlineHint>Probe Status: {probeMutation.data.probeStatus}</InlineHint> : null}
        {probeMutation.data?.nextRetryAfterMs ? (
          <InlineHint>Next Retry: {probeMutation.data.nextRetryAfterMs} ms</InlineHint>
        ) : null}
      </section>

      <section className="echo-lobby-panel">
        <h3>Wallet Ledger</h3>
        <div className="echo-room-history-actions">
          <Button disabled={ledgerLoadingMore || !hasMoreLedger || !nextLastId} onClick={() => void loadOlderLedger()}>
            {ledgerLoadingMore ? "Loading..." : hasMoreLedger ? "Load Older Entries" : "No Older Entries"}
          </Button>
        </div>
        {ledgerQuery.isLoading ? <InlineHint>Loading ledger...</InlineHint> : null}
        {ledgerQuery.isError ? <p className="echo-error">{toWalletDomainError(ledgerQuery.error)}</p> : null}
        <div className="echo-wallet-ledger-list">
          {ledgerItems.map((item) => (
            <article className="echo-room-message" key={item.id}>
              <header>
                <strong>
                  #{item.id} | {item.entryType}
                </strong>
                <span>{formatUtc(item.createdAt)}</span>
              </header>
              <p>
                delta {item.amountDelta} | balance {item.balanceAfter}
              </p>
              <InlineHint>idempotency: {item.idempotencyKey}</InlineHint>
            </article>
          ))}
          {!ledgerQuery.isLoading && ledgerItems.length === 0 ? <InlineHint>No ledger entries yet.</InlineHint> : null}
        </div>
      </section>

      {pageHint ? <InlineHint>{pageHint}</InlineHint> : null}
    </section>
  );
}
