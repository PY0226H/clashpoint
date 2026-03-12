-- iap + wallet ledger foundation

CREATE TABLE IF NOT EXISTS iap_products(
  product_id varchar(64) PRIMARY KEY,
  coins int NOT NULL CHECK (coins > 0),
  is_active boolean NOT NULL DEFAULT TRUE,
  created_at timestamptz DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_iap_products_active
  ON iap_products(is_active);

INSERT INTO iap_products(product_id, coins, is_active)
  VALUES
    ('com.echoisle.coins.60', 60, true),
    ('com.echoisle.coins.300', 300, true),
    ('com.echoisle.coins.680', 680, true)
ON CONFLICT (product_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS iap_orders(
  id bigserial PRIMARY KEY,
  user_id bigint NOT NULL REFERENCES users(id),
  platform varchar(16) NOT NULL CHECK (platform IN ('apple_iap')),
  product_id varchar(64) NOT NULL REFERENCES iap_products(product_id),
  transaction_id varchar(128) NOT NULL,
  original_transaction_id varchar(128),
  receipt_hash varchar(64) NOT NULL,
  status varchar(16) NOT NULL CHECK (status IN ('verified', 'rejected')),
  verify_mode varchar(16) NOT NULL CHECK (verify_mode IN ('mock')),
  verify_reason text,
  coins int NOT NULL CHECK (coins > 0),
  raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  verified_at timestamptz,
  created_at timestamptz DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(platform, transaction_id)
);

CREATE INDEX IF NOT EXISTS idx_iap_orders_user_created
  ON iap_orders(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_iap_orders_status_created
  ON iap_orders(status, created_at DESC);

CREATE TABLE IF NOT EXISTS user_wallets(
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  balance bigint NOT NULL DEFAULT 0 CHECK (balance >= 0),
  updated_at timestamptz DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id)
);

CREATE INDEX IF NOT EXISTS idx_user_wallets_balance
  ON user_wallets(balance DESC);

CREATE TABLE IF NOT EXISTS wallet_ledger(
  id bigserial PRIMARY KEY,
  user_id bigint NOT NULL REFERENCES users(id),
  order_id bigint REFERENCES iap_orders(id),
  entry_type varchar(32) NOT NULL CHECK (entry_type IN ('iap_credit', 'pin_debit', 'adjustment')),
  amount_delta bigint NOT NULL CHECK (amount_delta <> 0),
  balance_after bigint NOT NULL CHECK (balance_after >= 0),
  idempotency_key varchar(160) NOT NULL UNIQUE,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_wallet_ledger_user_created
  ON wallet_ledger(user_id, created_at DESC);
