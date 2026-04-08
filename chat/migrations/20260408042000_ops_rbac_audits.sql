CREATE TABLE IF NOT EXISTS ops_rbac_audits(
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
  created_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ops_rbac_audits_operator_created
  ON ops_rbac_audits(operator_user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ops_rbac_audits_target_created
  ON ops_rbac_audits(target_user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ops_rbac_audits_event_created
  ON ops_rbac_audits(event_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ops_rbac_audits_request_id_created
  ON ops_rbac_audits(request_id, created_at DESC);
