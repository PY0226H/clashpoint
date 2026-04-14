-- P8 cross-layer sync v2:
-- align chat_server final report storage with ai_judge_service P8 payload fields.

ALTER TABLE judge_final_reports
  ADD COLUMN IF NOT EXISTS winner_third varchar(16);

ALTER TABLE judge_final_reports
  ADD COLUMN IF NOT EXISTS review_required boolean NOT NULL DEFAULT false;

ALTER TABLE judge_final_reports
  ADD COLUMN IF NOT EXISTS claim_graph jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE judge_final_reports
  ADD COLUMN IF NOT EXISTS claim_graph_summary jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE judge_final_reports
  ADD COLUMN IF NOT EXISTS evidence_ledger jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE judge_final_reports
  ADD COLUMN IF NOT EXISTS verdict_ledger jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE judge_final_reports
  ADD COLUMN IF NOT EXISTS opinion_pack jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE judge_final_reports
  ADD COLUMN IF NOT EXISTS fairness_summary jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE judge_final_reports
  ADD COLUMN IF NOT EXISTS trust_attestation jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE judge_final_reports
  DROP CONSTRAINT IF EXISTS judge_final_reports_winner_third_check;

ALTER TABLE judge_final_reports
  ADD CONSTRAINT judge_final_reports_winner_third_check
  CHECK (winner_third IS NULL OR winner_third IN ('pro', 'con', 'draw'));

CREATE INDEX IF NOT EXISTS idx_judge_final_reports_review_required_created
  ON judge_final_reports(review_required, created_at DESC);
