CREATE INDEX IF NOT EXISTS idx_wallet_ledger_user_id_id_desc
  ON wallet_ledger(user_id, id DESC);
