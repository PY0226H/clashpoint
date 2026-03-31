-- runtime signals for notify service kafka ingress readiness

CREATE TABLE notify_runtime_signals(
  service_name text PRIMARY KEY,
  kafka_enabled boolean NOT NULL DEFAULT false,
  disable_pg_listener boolean NOT NULL DEFAULT false,
  kafka_connected_at timestamptz,
  kafka_last_receive_at timestamptz,
  kafka_last_commit_at timestamptz,
  kafka_last_error text,
  updated_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_notify_runtime_signals_updated_at
  ON notify_runtime_signals(updated_at DESC);
