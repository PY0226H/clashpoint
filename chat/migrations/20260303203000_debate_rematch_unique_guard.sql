-- enforce at most one rematch session per (parent_session_id, rematch_round)
-- this is the database-level safety net for draw/rematch concurrency.

CREATE UNIQUE INDEX uq_debate_sessions_parent_round
  ON debate_sessions(parent_session_id, rematch_round)
  WHERE parent_session_id IS NOT NULL;
