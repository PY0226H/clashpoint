-- kafka consumer idempotency ledger for worker processing

CREATE TABLE kafka_consume_ledger(
  id bigserial PRIMARY KEY,
  consumer_group text NOT NULL,
  topic text NOT NULL,
  partition int NOT NULL,
  message_offset bigint NOT NULL,
  event_id text NOT NULL,
  event_type text NOT NULL,
  aggregate_id text NOT NULL,
  payload jsonb NOT NULL,
  status varchar(16) NOT NULL CHECK (status IN ('succeeded', 'failed')),
  error_message text,
  processed_at timestamptz NOT NULL DEFAULT NOW(),
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW(),
  UNIQUE(consumer_group, event_id),
  UNIQUE(consumer_group, topic, partition, message_offset)
);

CREATE INDEX idx_kafka_consume_ledger_status_processed_at
  ON kafka_consume_ledger(status, processed_at DESC);
