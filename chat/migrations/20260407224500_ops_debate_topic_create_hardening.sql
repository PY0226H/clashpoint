CREATE TABLE IF NOT EXISTS ops_debate_topic_idempotency_keys(
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  idempotency_key varchar(160) NOT NULL,
  topic_id bigint NOT NULL REFERENCES debate_topics(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_ops_debate_topic_idempotency_topic
  ON ops_debate_topic_idempotency_keys(topic_id, created_at DESC);

CREATE TABLE IF NOT EXISTS ops_debate_topic_audits(
  id bigserial PRIMARY KEY,
  topic_id bigint NOT NULL REFERENCES debate_topics(id) ON DELETE CASCADE,
  operator_user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  action varchar(32) NOT NULL CHECK (action IN ('create', 'create_replay')),
  idempotency_key varchar(160),
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ops_debate_topic_audits_topic_created
  ON ops_debate_topic_audits(topic_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ops_debate_topic_audits_operator_created
  ON ops_debate_topic_audits(operator_user_id, created_at DESC);
