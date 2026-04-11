-- kafka dlq retention cleanup index for terminal rows

CREATE INDEX idx_kafka_dlq_events_terminal_retention_updated_id
  ON kafka_dlq_events(updated_at ASC, id ASC)
  WHERE status IN ('replayed', 'discarded');
