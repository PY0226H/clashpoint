-- AI judge final display contract hard-cut:
-- final_rationale -> debate_summary + side_analysis + verdict_reason

ALTER TABLE judge_final_reports
  ADD COLUMN IF NOT EXISTS debate_summary text NOT NULL DEFAULT '';

ALTER TABLE judge_final_reports
  ADD COLUMN IF NOT EXISTS side_analysis jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE judge_final_reports
  ADD COLUMN IF NOT EXISTS verdict_reason text NOT NULL DEFAULT '';

-- 历史列保留用于数据追溯，但不再作为主语义字段写入。
ALTER TABLE judge_final_reports
  ALTER COLUMN final_rationale DROP NOT NULL;

ALTER TABLE judge_final_reports
  ALTER COLUMN final_rationale SET DEFAULT '';

UPDATE judge_final_reports
SET
  debate_summary = CASE
    WHEN COALESCE(TRIM(debate_summary), '') = '' THEN COALESCE(final_rationale, '')
    ELSE debate_summary
  END,
  verdict_reason = CASE
    WHEN COALESCE(TRIM(verdict_reason), '') = '' THEN COALESCE(final_rationale, '')
    ELSE verdict_reason
  END,
  side_analysis = CASE
    WHEN side_analysis = '{}'::jsonb THEN jsonb_build_object('pro', '', 'con', '')
    ELSE side_analysis
  END;
