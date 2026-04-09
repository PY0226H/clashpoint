CREATE TABLE IF NOT EXISTS ops_rbac_audit_outbox_jobs(
  id bigserial PRIMARY KEY,
  event_type varchar(64) NOT NULL CHECK (
    event_type IN (
      'roles_list_read',
      'rbac_me_read',
      'role_upsert',
      'role_revoke'
    )
  ),
  operator_user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  target_user_id bigint REFERENCES users(id) ON DELETE SET NULL,
  decision varchar(32) NOT NULL CHECK (
    decision IN ('success', 'failed', 'rate_limited_user', 'rate_limited_ip')
  ),
  request_id varchar(128),
  result_count bigint CHECK (result_count IS NULL OR result_count >= 0),
  role varchar(32),
  removed boolean,
  error_code varchar(128),
  failure_reason varchar(32),
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  next_retry_at timestamptz NOT NULL DEFAULT NOW(),
  locked_until timestamptz,
  delivered_at timestamptz,
  last_error text,
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ops_rbac_audit_outbox_due
  ON ops_rbac_audit_outbox_jobs(next_retry_at ASC, created_at ASC, id ASC)
  WHERE delivered_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_ops_rbac_audit_outbox_locked
  ON ops_rbac_audit_outbox_jobs(locked_until ASC)
  WHERE delivered_at IS NULL AND locked_until IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ops_rbac_audit_outbox_event_created
  ON ops_rbac_audit_outbox_jobs(event_type, created_at DESC);
