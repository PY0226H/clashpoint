-- hardening for GET /api/debate/sessions list path
-- stable order + cursor pagination relies on scheduled_start_at DESC, id DESC

CREATE INDEX IF NOT EXISTS idx_sessions_status_time_id_desc
  ON debate_sessions(status, scheduled_start_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_sessions_topic_time_id_desc
  ON debate_sessions(topic_id, scheduled_start_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_sessions_topic_status_time_id_desc
  ON debate_sessions(topic_id, status, scheduled_start_at DESC, id DESC);
