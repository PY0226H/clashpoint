ALTER TABLE auth_sms_audit_logs
  ADD COLUMN IF NOT EXISTS code_hash_algo varchar(32),
  ADD COLUMN IF NOT EXISTS code_hash_key_id varchar(32);

CREATE TABLE IF NOT EXISTS auth_sms_dispatch_records(
  id bigserial PRIMARY KEY,
  scene varchar(32) NOT NULL,
  phone_e164 varchar(20) NOT NULL,
  provider varchar(32) NOT NULL,
  provider_message_id varchar(128) NOT NULL,
  send_status varchar(32) NOT NULL,
  accepted_at timestamptz NOT NULL,
  request_id varchar(128),
  request_ip_hash varchar(128),
  delivery_status varchar(32),
  delivered_at timestamptz,
  delivery_error_code varchar(128),
  delivery_error_message text,
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_auth_sms_dispatch_provider_message
  ON auth_sms_dispatch_records(provider, provider_message_id);

CREATE INDEX IF NOT EXISTS idx_auth_sms_dispatch_phone_scene_created
  ON auth_sms_dispatch_records(phone_e164, scene, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_auth_sms_dispatch_delivery_status
  ON auth_sms_dispatch_records(delivery_status, updated_at DESC);
