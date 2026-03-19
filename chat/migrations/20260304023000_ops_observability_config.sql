CREATE TABLE ops_observability_configs(
  singleton_id smallint PRIMARY KEY DEFAULT 1 CHECK (singleton_id = 1),
  thresholds_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  anomaly_state_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  updated_by bigint NOT NULL REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ops_observability_configs_updated_at
  ON ops_observability_configs(updated_at DESC);
