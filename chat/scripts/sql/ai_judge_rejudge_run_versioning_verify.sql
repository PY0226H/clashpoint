-- API067 S2-04 migration rehearsal verifier
-- Verifies run/version schema constraints and core data invariants after migration.

\set ON_ERROR_STOP on

DO $$
DECLARE
  required_run_columns int;
  required_constraints int;
  invalid_run_rows bigint;
  dup_phase_rows bigint;
  dup_phase_report_rows bigint;
  dup_final_job_rows bigint;
  dup_final_report_rows bigint;
BEGIN
  -- 1) all target tables must expose rejudge_run_no
  SELECT COUNT(*)::int
    INTO required_run_columns
  FROM information_schema.columns
  WHERE table_schema = 'public'
    AND column_name = 'rejudge_run_no'
    AND table_name IN (
      'judge_phase_jobs',
      'judge_phase_reports',
      'judge_final_jobs',
      'judge_final_reports',
      'judge_replay_actions'
    );

  IF required_run_columns <> 5 THEN
    RAISE EXCEPTION
      'rejudge_run_no column coverage invalid: expected=5 actual=%',
      required_run_columns;
  END IF;

  -- 2) run-level uniqueness constraints must exist
  SELECT COUNT(*)::int
    INTO required_constraints
  FROM pg_constraint
  WHERE conname IN (
    'judge_phase_jobs_session_run_phase_unique',
    'judge_phase_reports_session_run_phase_unique',
    'judge_final_jobs_session_run_unique',
    'judge_final_reports_session_run_unique'
  );

  IF required_constraints <> 4 THEN
    RAISE EXCEPTION
      'run unique constraints missing: expected=4 actual=%',
      required_constraints;
  END IF;

  -- 3) all run values must be positive
  SELECT
      (SELECT COUNT(*) FROM judge_phase_jobs WHERE rejudge_run_no <= 0)
    + (SELECT COUNT(*) FROM judge_phase_reports WHERE rejudge_run_no <= 0)
    + (SELECT COUNT(*) FROM judge_final_jobs WHERE rejudge_run_no <= 0)
    + (SELECT COUNT(*) FROM judge_final_reports WHERE rejudge_run_no <= 0)
    + (SELECT COUNT(*) FROM judge_replay_actions WHERE rejudge_run_no <= 0)
    INTO invalid_run_rows;

  IF invalid_run_rows <> 0 THEN
    RAISE EXCEPTION 'invalid non-positive rejudge_run_no rows detected: %', invalid_run_rows;
  END IF;

  -- 4) no duplicate rows against new unique keys
  SELECT COUNT(*)::bigint
    INTO dup_phase_rows
  FROM (
    SELECT session_id, rejudge_run_no, phase_no, COUNT(*) AS c
    FROM judge_phase_jobs
    GROUP BY session_id, rejudge_run_no, phase_no
    HAVING COUNT(*) > 1
  ) AS v;

  SELECT COUNT(*)::bigint
    INTO dup_phase_report_rows
  FROM (
    SELECT session_id, rejudge_run_no, phase_no, COUNT(*) AS c
    FROM judge_phase_reports
    GROUP BY session_id, rejudge_run_no, phase_no
    HAVING COUNT(*) > 1
  ) AS v;

  SELECT COUNT(*)::bigint
    INTO dup_final_job_rows
  FROM (
    SELECT session_id, rejudge_run_no, COUNT(*) AS c
    FROM judge_final_jobs
    GROUP BY session_id, rejudge_run_no
    HAVING COUNT(*) > 1
  ) AS v;

  SELECT COUNT(*)::bigint
    INTO dup_final_report_rows
  FROM (
    SELECT session_id, rejudge_run_no, COUNT(*) AS c
    FROM judge_final_reports
    GROUP BY session_id, rejudge_run_no
    HAVING COUNT(*) > 1
  ) AS v;

  IF dup_phase_rows <> 0
     OR dup_phase_report_rows <> 0
     OR dup_final_job_rows <> 0
     OR dup_final_report_rows <> 0 THEN
    RAISE EXCEPTION
      'duplicate key groups detected: phase_jobs=%, phase_reports=%, final_jobs=%, final_reports=%',
      dup_phase_rows,
      dup_phase_report_rows,
      dup_final_job_rows,
      dup_final_report_rows;
  END IF;
END $$;

SELECT
  'ok' AS verify_status,
  NOW() AS verified_at;
