-- optimize dlq list query for keyset pagination and mixed filter patterns

CREATE INDEX idx_kafka_dlq_events_status_event_type_updated_id
  ON kafka_dlq_events(status, event_type, updated_at DESC, id DESC);

CREATE INDEX idx_kafka_dlq_events_updated_id
  ON kafka_dlq_events(updated_at DESC, id DESC);
