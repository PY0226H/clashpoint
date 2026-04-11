-- kafka dlq action audits for replay/discard governance

CREATE TABLE kafka_dlq_event_actions(
  id bigserial PRIMARY KEY,
  dlq_event_id bigint NOT NULL,
  action varchar(16) NOT NULL CHECK (action IN ('replay', 'discard')),
  operator_user_id bigint NOT NULL,
  result varchar(16) NOT NULL CHECK (result IN ('success', 'failed', 'conflict', 'not_found')),
  before_status varchar(16),
  after_status varchar(16),
  reason text,
  request_id text,
  idempotency_key text,
  error_message text,
  created_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_kafka_dlq_event_actions_event_created_at
  ON kafka_dlq_event_actions(dlq_event_id, created_at DESC);

CREATE INDEX idx_kafka_dlq_event_actions_operator_created_at
  ON kafka_dlq_event_actions(operator_user_id, created_at DESC);
