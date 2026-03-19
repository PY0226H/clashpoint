-- replay actions keyword search optimization (ILIKE %keyword%)
-- note: this migration is safe in restricted environments:
-- if pg_trgm extension cannot be created, trigram indexes are skipped.

DO $$
BEGIN
  BEGIN
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
  EXCEPTION
    WHEN insufficient_privilege THEN
      RAISE NOTICE 'skip pg_trgm extension creation: insufficient privilege';
  END;

  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm') THEN
    EXECUTE '
      CREATE INDEX IF NOT EXISTS idx_judge_replay_actions_reason_trgm
      ON judge_replay_actions USING gin (reason gin_trgm_ops)
    ';
    EXECUTE '
      CREATE INDEX IF NOT EXISTS idx_judge_replay_actions_previous_trace_trgm
      ON judge_replay_actions USING gin (previous_trace_id gin_trgm_ops)
    ';
    EXECUTE '
      CREATE INDEX IF NOT EXISTS idx_judge_replay_actions_new_trace_trgm
      ON judge_replay_actions USING gin (new_trace_id gin_trgm_ops)
    ';
  ELSE
    RAISE NOTICE 'skip replay actions trigram indexes: pg_trgm extension is unavailable';
  END IF;
END
$$;
