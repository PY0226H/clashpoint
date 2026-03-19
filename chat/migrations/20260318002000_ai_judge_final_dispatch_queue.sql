-- ai judge final dispatch queue foundation

CREATE TABLE judge_final_jobs(
  id bigserial PRIMARY KEY,
  session_id bigint NOT NULL REFERENCES debate_sessions(id) ON DELETE CASCADE,
  phase_start_no int NOT NULL CHECK (phase_start_no > 0),
  phase_end_no int NOT NULL CHECK (phase_end_no >= phase_start_no),
  status varchar(16) NOT NULL CHECK (status IN ('queued', 'dispatched', 'failed')),
  trace_id varchar(128) NOT NULL,
  idempotency_key varchar(256) NOT NULL,
  rubric_version varchar(64) NOT NULL,
  judge_policy_version varchar(64) NOT NULL,
  topic_domain varchar(64) NOT NULL,
  dispatch_attempts int NOT NULL DEFAULT 0 CHECK (dispatch_attempts >= 0),
  last_dispatch_at timestamptz,
  dispatch_locked_until timestamptz,
  error_message text,
  created_at timestamptz DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (session_id),
  UNIQUE (idempotency_key)
);

CREATE INDEX idx_judge_final_jobs_status_due
  ON judge_final_jobs(status, dispatch_locked_until, created_at);
