-- User debate assistant MVP entitlement and per-session quota.

CREATE TABLE user_entitlements (
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  feature_key text NOT NULL,
  status text NOT NULL CHECK (status IN ('active', 'revoked')),
  source text NOT NULL,
  starts_at timestamptz NOT NULL DEFAULT NOW(),
  expires_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, feature_key),
  CHECK (feature_key <> ''),
  CHECK (source <> ''),
  CHECK (expires_at IS NULL OR expires_at > starts_at)
);

CREATE INDEX idx_user_entitlements_feature_status
  ON user_entitlements(feature_key, status, expires_at);

CREATE TABLE debate_assistant_session_usage (
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  session_id bigint NOT NULL REFERENCES debate_sessions(id) ON DELETE CASCADE,
  used_count integer NOT NULL DEFAULT 0 CHECK (used_count >= 0),
  quota_limit integer NOT NULL DEFAULT 20 CHECK (quota_limit > 0),
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, session_id)
);

CREATE INDEX idx_debate_assistant_session_usage_session
  ON debate_assistant_session_usage(session_id, updated_at DESC);
