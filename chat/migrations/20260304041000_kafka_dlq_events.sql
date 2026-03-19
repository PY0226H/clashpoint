-- kafka dlq events for failed consumer governance

CREATE TABLE kafka_dlq_events(
  id bigserial PRIMARY KEY,
  consumer_group text NOT NULL,
  topic text NOT NULL,
  partition int NOT NULL,
  message_offset bigint NOT NULL,
  event_id text NOT NULL,
  event_type text NOT NULL,
  aggregate_id text NOT NULL,
  payload jsonb NOT NULL,
  status varchar(16) NOT NULL CHECK (status IN ('pending', 'replayed', 'discarded')),
  failure_count int NOT NULL DEFAULT 1 CHECK (failure_count >= 1),
  error_message text NOT NULL,
  first_failed_at timestamptz NOT NULL DEFAULT NOW(),
  last_failed_at timestamptz NOT NULL DEFAULT NOW(),
  replayed_at timestamptz,
  discarded_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW(),
  UNIQUE(consumer_group, event_id)
);

CREATE INDEX idx_kafka_dlq_events_status_updated_at
  ON kafka_dlq_events(status, updated_at DESC);

CREATE INDEX idx_kafka_dlq_events_consumer_status_last_failed
  ON kafka_dlq_events(consumer_group, status, last_failed_at DESC);
