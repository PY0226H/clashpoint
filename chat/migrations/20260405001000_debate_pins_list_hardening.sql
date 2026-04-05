-- debate pins list hardening:
-- 1) stabilize ORDER BY pinned_at DESC, id DESC
-- 2) improve session-scoped history query path

CREATE INDEX IF NOT EXISTS idx_session_pinned_messages_session_pinned_id_desc
  ON session_pinned_messages(session_id, pinned_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_session_pinned_messages_active_session_pinned_id_desc
  ON session_pinned_messages(session_id, pinned_at DESC, id DESC)
  WHERE status = 'active';

