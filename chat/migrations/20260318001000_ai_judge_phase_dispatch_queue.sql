-- ai judge phase dispatch queue foundation

CREATE TABLE judge_phase_jobs(
  id bigserial PRIMARY KEY,
  session_id bigint NOT NULL REFERENCES debate_sessions(id) ON DELETE CASCADE,
  phase_no int NOT NULL CHECK (phase_no > 0),
  message_start_id bigint NOT NULL REFERENCES session_messages(id) ON DELETE CASCADE,
  message_end_id bigint NOT NULL REFERENCES session_messages(id) ON DELETE CASCADE,
  message_count int NOT NULL CHECK (message_count > 0),
  status varchar(16) NOT NULL CHECK (status IN ('queued', 'dispatched', 'failed')),
  trace_id varchar(128) NOT NULL,
  idempotency_key varchar(256) NOT NULL,
  rubric_version varchar(64) NOT NULL,
  judge_policy_version varchar(64) NOT NULL,
  topic_domain varchar(64) NOT NULL,
  retrieval_profile varchar(64) NOT NULL,
  dispatch_attempts int NOT NULL DEFAULT 0 CHECK (dispatch_attempts >= 0),
  last_dispatch_at timestamptz,
  dispatch_locked_until timestamptz,
  error_message text,
  created_at timestamptz DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (session_id, phase_no),
  UNIQUE (idempotency_key)
);

CREATE INDEX idx_judge_phase_jobs_status_due
  ON judge_phase_jobs(status, dispatch_locked_until, created_at);

CREATE INDEX idx_judge_phase_jobs_session_phase
  ON judge_phase_jobs(session_id, phase_no DESC);
