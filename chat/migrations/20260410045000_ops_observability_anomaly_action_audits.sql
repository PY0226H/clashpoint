CREATE TABLE ops_observability_anomaly_action_audits(
  id bigserial PRIMARY KEY,
  singleton_id smallint NOT NULL DEFAULT 1 CHECK (singleton_id = 1),
  alert_key text NOT NULL,
  action text NOT NULL,
  suppress_minutes integer,
  before_state_json jsonb NOT NULL,
  after_state_json jsonb NOT NULL,
  updated_by bigint NOT NULL REFERENCES users(id),
  request_id text,
  created_at timestamptz NOT NULL DEFAULT NOW(),
  CONSTRAINT ck_ops_observability_anomaly_action_audits_alert_key_non_empty
    CHECK (length(btrim(alert_key)) > 0),
  CONSTRAINT ck_ops_observability_anomaly_action_audits_action_non_empty
    CHECK (length(btrim(action)) > 0),
  CONSTRAINT ck_ops_observability_anomaly_action_audits_suppress_minutes_non_negative
    CHECK (suppress_minutes IS NULL OR suppress_minutes >= 0)
);

CREATE INDEX idx_ops_observability_anomaly_action_audits_created_at
  ON ops_observability_anomaly_action_audits(created_at DESC, id DESC);

CREATE INDEX idx_ops_observability_anomaly_action_audits_updated_by_created_at
  ON ops_observability_anomaly_action_audits(updated_by, created_at DESC, id DESC);

CREATE INDEX idx_ops_observability_anomaly_action_audits_alert_key_created_at
  ON ops_observability_anomaly_action_audits(alert_key, created_at DESC, id DESC);
