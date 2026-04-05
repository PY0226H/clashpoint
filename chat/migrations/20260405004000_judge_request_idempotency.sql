-- persistent idempotency ledger for judge job request endpoint

CREATE TABLE IF NOT EXISTS judge_job_request_idempotency(
  id bigserial PRIMARY KEY,
  session_id bigint NOT NULL REFERENCES debate_sessions(id) ON DELETE CASCADE,
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  idempotency_key varchar(160) NOT NULL,
  request_hash varchar(128) NOT NULL,
  status varchar(16) NOT NULL CHECK (status IN ('processing', 'completed', 'failed')),
  response_snapshot jsonb,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(session_id, user_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_judge_request_idempotency_user_created
  ON judge_job_request_idempotency(user_id, created_at DESC);
