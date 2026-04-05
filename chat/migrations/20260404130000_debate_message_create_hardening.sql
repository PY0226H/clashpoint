-- debate message create hardening:
-- 1) deterministic phase checkpoint counter
-- 2) idempotency mapping for create-message
-- 3) async hot_score delta aggregation

ALTER TABLE debate_sessions
ADD COLUMN IF NOT EXISTS message_count int NOT NULL DEFAULT 0 CHECK (message_count >= 0);

WITH agg AS (
  SELECT session_id, COUNT(*)::int AS cnt
  FROM session_messages
  GROUP BY session_id
)
UPDATE debate_sessions s
SET message_count = agg.cnt
FROM agg
WHERE s.id = agg.session_id;

UPDATE debate_sessions s
SET message_count = 0
WHERE NOT EXISTS (
  SELECT 1
  FROM session_messages m
  WHERE m.session_id = s.id
);

CREATE TABLE IF NOT EXISTS debate_message_idempotency_keys(
  id bigserial PRIMARY KEY,
  session_id bigint NOT NULL REFERENCES debate_sessions(id) ON DELETE CASCADE,
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  idempotency_key varchar(160) NOT NULL,
  message_id bigint NOT NULL REFERENCES session_messages(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT NOW(),
  UNIQUE(session_id, user_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_debate_message_idempotency_keys_user_created
  ON debate_message_idempotency_keys(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS debate_session_hot_score_deltas(
  session_id bigint PRIMARY KEY REFERENCES debate_sessions(id) ON DELETE CASCADE,
  delta bigint NOT NULL CHECK (delta > 0),
  updated_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_debate_session_hot_score_deltas_updated_at
  ON debate_session_hot_score_deltas(updated_at ASC);
