CREATE TABLE auth_sms_audit_logs(
  id bigserial PRIMARY KEY,
  phone_e164 varchar(20) NOT NULL,
  scene varchar(32) NOT NULL,
  provider varchar(32) NOT NULL,
  action varchar(32) NOT NULL,
  result varchar(32) NOT NULL,
  reason varchar(128),
  request_ip_hash varchar(128),
  code_hash varchar(64),
  user_id bigint REFERENCES users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX auth_sms_audit_logs_phone_scene_idx
  ON auth_sms_audit_logs(phone_e164, scene, created_at DESC);

CREATE INDEX auth_sms_audit_logs_result_idx
  ON auth_sms_audit_logs(result, created_at DESC);
