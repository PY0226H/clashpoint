CREATE TABLE ops_observability_threshold_audits(
  id bigserial PRIMARY KEY,
  singleton_id smallint NOT NULL DEFAULT 1 CHECK (singleton_id = 1),
  before_thresholds_json jsonb NOT NULL,
  after_thresholds_json jsonb NOT NULL,
  updated_by bigint NOT NULL REFERENCES users(id),
  request_id text,
  created_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ops_observability_threshold_audits_created_at
  ON ops_observability_threshold_audits(created_at DESC, id DESC);

CREATE INDEX idx_ops_observability_threshold_audits_updated_by_created_at
  ON ops_observability_threshold_audits(updated_by, created_at DESC, id DESC);
