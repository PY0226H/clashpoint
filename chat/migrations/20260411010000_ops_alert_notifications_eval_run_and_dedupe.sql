-- add evaluation run trace fields and dedupe fingerprint for ops alert notifications

ALTER TABLE ops_alert_notifications
  ADD COLUMN evaluation_run_id text NOT NULL DEFAULT '';

ALTER TABLE ops_alert_notifications
  ADD COLUMN notification_fingerprint text NOT NULL DEFAULT '';

CREATE UNIQUE INDEX idx_ops_alert_notifications_fingerprint_unique
  ON ops_alert_notifications(notification_fingerprint)
  WHERE notification_fingerprint <> '';
