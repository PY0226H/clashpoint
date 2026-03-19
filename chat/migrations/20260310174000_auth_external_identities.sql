CREATE TABLE auth_external_identities(
  id bigserial PRIMARY KEY,
  provider varchar(32) NOT NULL,
  provider_user_id varchar(128) NOT NULL,
  provider_unionid varchar(128),
  app_id varchar(64),
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(provider, provider_user_id)
);

CREATE UNIQUE INDEX auth_external_identities_provider_unionid_idx
  ON auth_external_identities(provider, provider_unionid)
  WHERE provider_unionid IS NOT NULL;

CREATE INDEX auth_external_identities_user_idx
  ON auth_external_identities(user_id, provider);
