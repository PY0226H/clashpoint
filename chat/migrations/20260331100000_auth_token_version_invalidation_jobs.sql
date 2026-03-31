CREATE TABLE auth_token_version_invalidation_jobs(
  user_id bigint PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  next_retry_at timestamptz NOT NULL DEFAULT NOW(),
  locked_until timestamptz,
  last_error text,
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_auth_token_version_invalidation_jobs_due
  ON auth_token_version_invalidation_jobs(next_retry_at ASC, created_at ASC, user_id ASC);

CREATE INDEX idx_auth_token_version_invalidation_jobs_locked
  ON auth_token_version_invalidation_jobs(locked_until ASC)
  WHERE locked_until IS NOT NULL;
