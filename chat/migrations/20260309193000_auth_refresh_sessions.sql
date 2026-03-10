ALTER TABLE users
  ADD COLUMN IF NOT EXISTS token_version bigint NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS auth_refresh_sessions(
  id bigserial PRIMARY KEY,
  ws_id bigint NOT NULL REFERENCES workspaces(id),
  user_id bigint NOT NULL REFERENCES users(id),
  sid varchar(64) NOT NULL UNIQUE,
  family_id varchar(64) NOT NULL,
  current_jti varchar(128) NOT NULL,
  rotated_from_jti varchar(128),
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz,
  revoke_reason varchar(64),
  user_agent text,
  ip_hash varchar(128),
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS auth_refresh_sessions_user_idx
  ON auth_refresh_sessions(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS auth_refresh_sessions_family_idx
  ON auth_refresh_sessions(family_id, created_at DESC);

CREATE INDEX IF NOT EXISTS auth_refresh_sessions_sid_user_idx
  ON auth_refresh_sessions(sid, user_id);
