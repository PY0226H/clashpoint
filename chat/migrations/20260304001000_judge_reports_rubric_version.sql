ALTER TABLE judge_reports
  ADD COLUMN rubric_version varchar(128) NOT NULL
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

CREATE INDEX idx_judge_reports_rubric_created
  ON judge_reports(rubric_version, created_at DESC);
