-- API 027 judge-report hardening:
-- 1) structured final dispatch failure fields
-- 2) latest phase job query index

ALTER TABLE judge_final_jobs
  ADD COLUMN IF NOT EXISTS error_code varchar(64);

ALTER TABLE judge_final_jobs
  ADD COLUMN IF NOT EXISTS contract_failure_type varchar(64);

CREATE INDEX IF NOT EXISTS idx_judge_phase_jobs_session_created_desc
  ON judge_phase_jobs(session_id, created_at DESC);
