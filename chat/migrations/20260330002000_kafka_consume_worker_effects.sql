-- kafka worker business side-effect audit (idempotent by consumer_group + event_id)

CREATE TABLE kafka_consume_worker_effects(
  id bigserial PRIMARY KEY,
  consumer_group text NOT NULL,
  topic text NOT NULL,
  partition int NOT NULL,
  message_offset bigint NOT NULL,
  event_id text NOT NULL,
  event_type text NOT NULL,
  source text NOT NULL,
  aggregate_id text NOT NULL,
  session_id bigint NOT NULL,
  user_id bigint,
  message_id bigint,
  pin_id bigint,
  ledger_id bigint,
  from_status varchar(20),
  to_status varchar(20),
  side varchar(8) CHECK (side IN ('pro', 'con')),
  cost_coins bigint,
  pin_seconds int,
  expires_at timestamptz,
  payload jsonb NOT NULL,
  applied_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW(),
  UNIQUE(consumer_group, event_id),
  UNIQUE(consumer_group, topic, partition, message_offset)
);

CREATE INDEX idx_kafka_consume_worker_effects_session_applied
  ON kafka_consume_worker_effects(session_id, applied_at DESC);

CREATE INDEX idx_kafka_consume_worker_effects_event_type_applied
  ON kafka_consume_worker_effects(event_type, applied_at DESC);
