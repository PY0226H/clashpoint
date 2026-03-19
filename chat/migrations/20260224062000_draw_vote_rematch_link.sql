-- link draw-vote open_rematch resolution to auto-created rematch session

ALTER TABLE debate_sessions
ADD COLUMN parent_session_id bigint REFERENCES debate_sessions(id) ON DELETE SET NULL;

ALTER TABLE debate_sessions
ADD COLUMN rematch_round int NOT NULL DEFAULT 0 CHECK (rematch_round >= 0);

CREATE INDEX idx_debate_sessions_parent_round
  ON debate_sessions(parent_session_id, rematch_round, scheduled_start_at DESC);

ALTER TABLE judge_draw_votes
ADD COLUMN rematch_session_id bigint REFERENCES debate_sessions(id) ON DELETE SET NULL;

CREATE INDEX idx_judge_draw_votes_rematch_session
  ON judge_draw_votes(rematch_session_id);
