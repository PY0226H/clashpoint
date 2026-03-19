-- ai judge dispatch queue metadata

ALTER TABLE judge_jobs
  ADD COLUMN dispatch_attempts int NOT NULL DEFAULT 0 CHECK (dispatch_attempts >= 0);

ALTER TABLE judge_jobs
  ADD COLUMN last_dispatch_at timestamptz;

ALTER TABLE judge_jobs
  ADD COLUMN dispatch_locked_until timestamptz;

CREATE INDEX idx_judge_jobs_dispatch_due
  ON judge_jobs(status, dispatch_locked_until, requested_at);
