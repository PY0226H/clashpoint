CREATE INDEX IF NOT EXISTS idx_wallet_ledger_iap_credit_order_user
  ON wallet_ledger(order_id, user_id)
  WHERE entry_type = 'iap_credit';
