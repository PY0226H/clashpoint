CREATE TABLE auth_refresh_consistency_outbox_jobs(
  id bigserial PRIMARY KEY,
  op_type varchar(64) NOT NULL,
  scope varchar(128) NOT NULL,
  raw_key varchar(256) NOT NULL,
  value text NOT NULL,
  ttl_secs bigint NOT NULL CHECK (ttl_secs > 0),
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  next_retry_at timestamptz NOT NULL DEFAULT NOW(),
  locked_until timestamptz,
  last_error text,
  delivered_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_auth_refresh_consistency_outbox_due
  ON auth_refresh_consistency_outbox_jobs(next_retry_at ASC, created_at ASC, id ASC)
  WHERE delivered_at IS NULL;

CREATE INDEX idx_auth_refresh_consistency_outbox_locked
  ON auth_refresh_consistency_outbox_jobs(locked_until ASC)
  WHERE delivered_at IS NULL AND locked_until IS NOT NULL;
