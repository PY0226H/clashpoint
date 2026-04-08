CREATE TABLE IF NOT EXISTS ops_debate_session_idempotency_keys(
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  idempotency_key varchar(160) NOT NULL,
  session_id bigint NOT NULL REFERENCES debate_sessions(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_ops_debate_session_idempotency_session_created
  ON ops_debate_session_idempotency_keys(session_id, created_at DESC);

CREATE TABLE IF NOT EXISTS ops_debate_session_audits(
  id bigserial PRIMARY KEY,
  session_id bigint NOT NULL REFERENCES debate_sessions(id) ON DELETE CASCADE,
  operator_user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  action varchar(32) NOT NULL CHECK (action IN ('create', 'create_replay')),
  idempotency_key varchar(160),
  created_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ops_debate_session_audits_session_created
  ON ops_debate_session_audits(session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ops_debate_session_audits_operator_created
  ON ops_debate_session_audits(operator_user_id, created_at DESC);
