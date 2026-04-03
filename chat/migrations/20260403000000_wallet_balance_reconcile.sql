CREATE TABLE IF NOT EXISTS wallet_balance_reconcile_audits(
  id bigserial PRIMARY KEY,
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  wallet_balance bigint NOT NULL,
  ledger_balance bigint NOT NULL,
  wallet_updated_at timestamptz,
  ledger_latest_at timestamptz,
  detected_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_wallet_balance_reconcile_detected
  ON wallet_balance_reconcile_audits(detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_wallet_balance_reconcile_user_detected
  ON wallet_balance_reconcile_audits(user_id, detected_at DESC);
