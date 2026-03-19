-- ai judge ops replay execution audit

CREATE TABLE IF NOT EXISTS judge_replay_actions(
  id bigserial PRIMARY KEY,
  scope varchar(16) NOT NULL CHECK (scope IN ('phase', 'final')),
  job_id bigint NOT NULL,
  session_id bigint NOT NULL REFERENCES debate_sessions(id) ON DELETE CASCADE,
  requested_by bigint NOT NULL REFERENCES users(id),
  reason text,
  previous_status varchar(16) NOT NULL,
  new_status varchar(16) NOT NULL,
  previous_trace_id varchar(128) NOT NULL,
  new_trace_id varchar(128) NOT NULL,
  previous_idempotency_key varchar(256) NOT NULL,
  new_idempotency_key varchar(256) NOT NULL,
  created_at timestamptz DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_judge_replay_actions_scope_job_created
  ON judge_replay_actions(scope, job_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_judge_replay_actions_session_created
  ON judge_replay_actions(session_id, created_at DESC);
