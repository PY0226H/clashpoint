CREATE TABLE ops_observability_anomaly_state_audits(
  id bigserial PRIMARY KEY,
  singleton_id smallint NOT NULL DEFAULT 1 CHECK (singleton_id = 1),
  before_anomaly_state_json jsonb NOT NULL,
  after_anomaly_state_json jsonb NOT NULL,
  updated_by bigint NOT NULL REFERENCES users(id),
  request_id text,
  input_item_count integer NOT NULL DEFAULT 0,
  retained_item_count integer NOT NULL DEFAULT 0,
  dropped_item_count integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT NOW(),
  CONSTRAINT ck_ops_observability_anomaly_state_audits_input_non_negative
    CHECK (input_item_count >= 0),
  CONSTRAINT ck_ops_observability_anomaly_state_audits_retained_non_negative
    CHECK (retained_item_count >= 0),
  CONSTRAINT ck_ops_observability_anomaly_state_audits_dropped_non_negative
    CHECK (dropped_item_count >= 0)
);

CREATE INDEX idx_ops_observability_anomaly_state_audits_created_at
  ON ops_observability_anomaly_state_audits(created_at DESC, id DESC);

CREATE INDEX idx_ops_observability_anomaly_state_audits_updated_by_created_at
  ON ops_observability_anomaly_state_audits(updated_by, created_at DESC, id DESC);
