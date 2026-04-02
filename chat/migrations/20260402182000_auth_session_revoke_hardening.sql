ALTER TABLE auth_refresh_consistency_outbox_jobs
ADD COLUMN IF NOT EXISTS source varchar(64) NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_auth_refresh_consistency_outbox_source_due
  ON auth_refresh_consistency_outbox_jobs(source, next_retry_at ASC, created_at ASC, id ASC)
  WHERE delivered_at IS NULL;

CREATE TABLE IF NOT EXISTS auth_refresh_consistency_outbox_dlq_jobs(
  id bigserial PRIMARY KEY,
  original_job_id bigint,
  op_type varchar(64) NOT NULL,
  scope varchar(128) NOT NULL,
  raw_key varchar(256) NOT NULL,
  value text NOT NULL,
  source varchar(64) NOT NULL DEFAULT '',
  ttl_secs bigint NOT NULL CHECK (ttl_secs > 0),
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  last_error text NOT NULL,
  dropped_at timestamptz NOT NULL DEFAULT NOW(),
  created_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_auth_refresh_consistency_outbox_dlq_dropped
  ON auth_refresh_consistency_outbox_dlq_jobs(dropped_at ASC, id ASC);

CREATE INDEX IF NOT EXISTS idx_auth_refresh_consistency_outbox_dlq_source
  ON auth_refresh_consistency_outbox_dlq_jobs(source, dropped_at DESC);

CREATE INDEX IF NOT EXISTS idx_auth_refresh_consistency_outbox_dlq_scope_key
  ON auth_refresh_consistency_outbox_dlq_jobs(scope, raw_key);

CREATE TABLE IF NOT EXISTS auth_session_revoke_audits(
  id bigserial PRIMARY KEY,
  operator_user_id bigint NOT NULL REFERENCES users(id),
  sid varchar(64) NOT NULL,
  family_id varchar(64),
  affected_count bigint NOT NULL CHECK (affected_count >= 0),
  result varchar(32) NOT NULL,
  request_id varchar(128),
  ip_hash varchar(128),
  ua_hash varchar(128),
  created_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_auth_session_revoke_audits_operator_created
  ON auth_session_revoke_audits(operator_user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_auth_session_revoke_audits_sid_created
  ON auth_session_revoke_audits(sid, created_at DESC);
