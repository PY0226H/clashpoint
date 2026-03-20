-- ai judge v3 domain foundation (phase/final only)

CREATE TABLE judge_phase_jobs(
  id bigserial PRIMARY KEY,
  session_id bigint NOT NULL REFERENCES debate_sessions(id) ON DELETE CASCADE,
  phase_no int NOT NULL CHECK (phase_no > 0),
  message_start_id bigint NOT NULL REFERENCES session_messages(id) ON DELETE CASCADE,
  message_end_id bigint NOT NULL REFERENCES session_messages(id) ON DELETE CASCADE,
  message_count int NOT NULL CHECK (message_count > 0),
  status varchar(16) NOT NULL CHECK (status IN ('queued', 'dispatched', 'succeeded', 'failed')),
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
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (session_id, phase_no),
  UNIQUE (idempotency_key)
);

CREATE INDEX idx_judge_phase_jobs_status_due
  ON judge_phase_jobs(status, dispatch_locked_until, created_at);

CREATE INDEX idx_judge_phase_jobs_session_phase
  ON judge_phase_jobs(session_id, phase_no DESC);

CREATE TABLE judge_final_jobs(
  id bigserial PRIMARY KEY,
  session_id bigint NOT NULL REFERENCES debate_sessions(id) ON DELETE CASCADE,
  phase_start_no int NOT NULL CHECK (phase_start_no > 0),
  phase_end_no int NOT NULL CHECK (phase_end_no >= phase_start_no),
  status varchar(16) NOT NULL CHECK (status IN ('queued', 'dispatched', 'succeeded', 'failed')),
  trace_id varchar(128) NOT NULL,
  idempotency_key varchar(256) NOT NULL,
  rubric_version varchar(64) NOT NULL,
  judge_policy_version varchar(64) NOT NULL,
  topic_domain varchar(64) NOT NULL,
  dispatch_attempts int NOT NULL DEFAULT 0 CHECK (dispatch_attempts >= 0),
  last_dispatch_at timestamptz,
  dispatch_locked_until timestamptz,
  error_message text,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (session_id),
  UNIQUE (idempotency_key)
);

CREATE INDEX idx_judge_final_jobs_status_due
  ON judge_final_jobs(status, dispatch_locked_until, created_at);

CREATE TABLE judge_phase_reports(
  id bigserial PRIMARY KEY,
  phase_job_id bigint NOT NULL REFERENCES judge_phase_jobs(id) ON DELETE CASCADE,
  session_id bigint NOT NULL REFERENCES debate_sessions(id) ON DELETE CASCADE,
  phase_no int NOT NULL CHECK (phase_no > 0),
  message_start_id bigint NOT NULL REFERENCES session_messages(id) ON DELETE CASCADE,
  message_end_id bigint NOT NULL REFERENCES session_messages(id) ON DELETE CASCADE,
  message_count int NOT NULL CHECK (message_count > 0),
  pro_summary_grounded jsonb NOT NULL,
  con_summary_grounded jsonb NOT NULL,
  pro_retrieval_bundle jsonb NOT NULL,
  con_retrieval_bundle jsonb NOT NULL,
  agent1_score jsonb NOT NULL,
  agent2_score jsonb NOT NULL,
  agent3_weighted_score jsonb NOT NULL,
  prompt_hashes jsonb NOT NULL DEFAULT '{}'::jsonb,
  token_usage jsonb NOT NULL DEFAULT '{}'::jsonb,
  latency_ms jsonb NOT NULL DEFAULT '{}'::jsonb,
  error_codes jsonb NOT NULL DEFAULT '[]'::jsonb,
  degradation_level int NOT NULL DEFAULT 0,
  judge_trace jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (phase_job_id),
  UNIQUE (session_id, phase_no)
);

CREATE INDEX idx_judge_phase_reports_session_phase
  ON judge_phase_reports(session_id, phase_no DESC);

CREATE INDEX idx_judge_phase_reports_created
  ON judge_phase_reports(created_at DESC);

CREATE TABLE judge_final_reports(
  id bigserial PRIMARY KEY,
  final_job_id bigint NOT NULL REFERENCES judge_final_jobs(id) ON DELETE CASCADE,
  session_id bigint NOT NULL REFERENCES debate_sessions(id) ON DELETE CASCADE,
  winner varchar(16) NOT NULL CHECK (winner IN ('pro', 'con', 'draw')),
  pro_score double precision NOT NULL,
  con_score double precision NOT NULL,
  dimension_scores jsonb NOT NULL DEFAULT '{}'::jsonb,
  final_rationale text NOT NULL,
  verdict_evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
  phase_rollup_summary jsonb NOT NULL DEFAULT '[]'::jsonb,
  retrieval_snapshot_rollup jsonb NOT NULL DEFAULT '[]'::jsonb,
  winner_first varchar(16),
  winner_second varchar(16),
  rejudge_triggered boolean NOT NULL DEFAULT false,
  needs_draw_vote boolean NOT NULL DEFAULT false,
  judge_trace jsonb NOT NULL DEFAULT '{}'::jsonb,
  audit_alerts jsonb NOT NULL DEFAULT '[]'::jsonb,
  error_codes jsonb NOT NULL DEFAULT '[]'::jsonb,
  degradation_level int NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (final_job_id),
  UNIQUE (session_id),
  CONSTRAINT judge_final_reports_winner_first_check
    CHECK (winner_first IS NULL OR winner_first IN ('pro', 'con', 'draw')),
  CONSTRAINT judge_final_reports_winner_second_check
    CHECK (winner_second IS NULL OR winner_second IN ('pro', 'con', 'draw'))
);

CREATE INDEX idx_judge_final_reports_created
  ON judge_final_reports(created_at DESC);
