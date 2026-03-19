-- replay actions ops query performance indexes

CREATE INDEX idx_judge_replay_actions_created_id_desc
  ON judge_replay_actions(created_at DESC, id DESC);

CREATE INDEX idx_judge_replay_actions_requested_by_created_id_desc
  ON judge_replay_actions(requested_by, created_at DESC, id DESC);

CREATE INDEX idx_judge_replay_actions_prev_new_status_created_id_desc
  ON judge_replay_actions(previous_status, new_status, created_at DESC, id DESC);
