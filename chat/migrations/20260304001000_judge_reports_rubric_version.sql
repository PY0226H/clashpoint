ALTER TABLE judge_reports
  ADD COLUMN IF NOT EXISTS rubric_version varchar(128) NOT NULL
  DEFAULT 'v1-logic-evidence-rebuttal-clarity';

UPDATE judge_reports
SET rubric_version = LEFT(
  TRIM(
    COALESCE(
      NULLIF(payload ->> 'rubricVersion', ''),
      NULLIF(payload ->> 'rubric_version', ''),
      rubric_version
    )
  ),
  128
)
WHERE payload ? 'rubricVersion' OR payload ? 'rubric_version';

CREATE INDEX IF NOT EXISTS idx_judge_reports_ws_rubric_created
  ON judge_reports(ws_id, rubric_version, created_at DESC);
