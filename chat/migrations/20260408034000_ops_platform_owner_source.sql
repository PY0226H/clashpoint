CREATE TABLE platform_admin_owners(
  singleton_key boolean NOT NULL DEFAULT TRUE CHECK (singleton_key),
  owner_user_id bigint NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  updated_by bigint NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (singleton_key)
);

INSERT INTO platform_admin_owners(singleton_key, owner_user_id, updated_by)
SELECT TRUE, u.id, u.id
FROM users u
WHERE u.id = 1
ON CONFLICT (singleton_key) DO NOTHING;
