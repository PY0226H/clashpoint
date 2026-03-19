-- ops observability alert notifications and runtime states

CREATE TABLE ops_alert_notifications(
  id bigserial PRIMARY KEY,
  alert_key text NOT NULL,
  rule_type text NOT NULL,
  severity text NOT NULL,
  alert_status varchar(16) NOT NULL CHECK (alert_status IN ('raised', 'cleared', 'suppressed')),
  title text NOT NULL,
  message text NOT NULL,
  metrics_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  recipients_json jsonb NOT NULL DEFAULT '[]'::jsonb,
  delivery_status varchar(16) NOT NULL CHECK (delivery_status IN ('pending', 'sent', 'failed')) DEFAULT 'pending',
  error_message text,
  delivered_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ops_alert_notifications_created_at
  ON ops_alert_notifications(created_at DESC);

CREATE INDEX idx_ops_alert_notifications_status
  ON ops_alert_notifications(alert_status, delivery_status, updated_at DESC);

CREATE TABLE ops_alert_states(
  alert_key text NOT NULL,
  is_active boolean NOT NULL DEFAULT false,
  last_emitted_status varchar(16) NOT NULL CHECK (last_emitted_status IN ('raised', 'cleared', 'suppressed')) DEFAULT 'cleared',
  last_changed_at timestamptz NOT NULL DEFAULT NOW(),
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW(),
  PRIMARY KEY (alert_key)
);

CREATE INDEX idx_ops_alert_states_active
  ON ops_alert_states(is_active, updated_at DESC);
