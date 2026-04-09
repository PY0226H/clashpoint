ALTER TABLE ops_rbac_audits
  ADD COLUMN IF NOT EXISTS error_code varchar(128),
  ADD COLUMN IF NOT EXISTS failure_reason varchar(64);

CREATE INDEX IF NOT EXISTS idx_ops_rbac_audits_failure_reason_created
  ON ops_rbac_audits(failure_reason, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ops_rbac_audits_error_code_created
  ON ops_rbac_audits(error_code, created_at DESC);

CREATE TABLE IF NOT EXISTS ops_rbac_role_upsert_idempotency_keys(
  operator_user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  target_user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  idempotency_key varchar(160) NOT NULL,
  role varchar(32) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT NOW(),
  PRIMARY KEY (operator_user_id, target_user_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_ops_rbac_role_upsert_idempotency_created
  ON ops_rbac_role_upsert_idempotency_keys(created_at DESC);
