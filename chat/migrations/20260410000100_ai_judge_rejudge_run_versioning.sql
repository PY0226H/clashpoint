-- API067 M2: enable run/versioned rejudge for judge phase/final/report chains

ALTER TABLE judge_phase_jobs
  ADD COLUMN IF NOT EXISTS rejudge_run_no int NOT NULL DEFAULT 1
  CHECK (rejudge_run_no > 0);

ALTER TABLE judge_phase_reports
  ADD COLUMN IF NOT EXISTS rejudge_run_no int NOT NULL DEFAULT 1
  CHECK (rejudge_run_no > 0);

ALTER TABLE judge_final_jobs
  ADD COLUMN IF NOT EXISTS rejudge_run_no int NOT NULL DEFAULT 1
  CHECK (rejudge_run_no > 0);

ALTER TABLE judge_final_reports
  ADD COLUMN IF NOT EXISTS rejudge_run_no int NOT NULL DEFAULT 1
  CHECK (rejudge_run_no > 0);

-- replay audit retains run dimension for traceability
ALTER TABLE judge_replay_actions
  ADD COLUMN IF NOT EXISTS rejudge_run_no int NOT NULL DEFAULT 1
  CHECK (rejudge_run_no > 0);

-- drop legacy per-session unique constraints to allow multiple runs
ALTER TABLE judge_phase_jobs
  DROP CONSTRAINT IF EXISTS judge_phase_jobs_session_id_phase_no_key;

ALTER TABLE judge_phase_reports
  DROP CONSTRAINT IF EXISTS judge_phase_reports_session_id_phase_no_key;

ALTER TABLE judge_final_jobs
  DROP CONSTRAINT IF EXISTS judge_final_jobs_session_id_key;

ALTER TABLE judge_final_reports
  DROP CONSTRAINT IF EXISTS judge_final_reports_session_id_key;

-- new run-scoped uniqueness
ALTER TABLE judge_phase_jobs
  ADD CONSTRAINT judge_phase_jobs_session_run_phase_unique
  UNIQUE (session_id, rejudge_run_no, phase_no);

ALTER TABLE judge_phase_reports
  ADD CONSTRAINT judge_phase_reports_session_run_phase_unique
  UNIQUE (session_id, rejudge_run_no, phase_no);

ALTER TABLE judge_final_jobs
  ADD CONSTRAINT judge_final_jobs_session_run_unique
  UNIQUE (session_id, rejudge_run_no);

ALTER TABLE judge_final_reports
  ADD CONSTRAINT judge_final_reports_session_run_unique
  UNIQUE (session_id, rejudge_run_no);

-- common read path indexes
CREATE INDEX IF NOT EXISTS idx_judge_phase_jobs_session_run_created_desc
  ON judge_phase_jobs(session_id, rejudge_run_no DESC, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_judge_final_jobs_session_run_created_desc
  ON judge_final_jobs(session_id, rejudge_run_no DESC, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_judge_final_reports_session_run_created_desc
  ON judge_final_reports(session_id, rejudge_run_no DESC, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_judge_replay_actions_session_run_created_desc
  ON judge_replay_actions(session_id, rejudge_run_no DESC, created_at DESC);
