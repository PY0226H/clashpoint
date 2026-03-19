CREATE TABLE platform_user_roles(
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role varchar(32) NOT NULL CHECK (role IN ('ops_admin', 'ops_reviewer', 'ops_viewer')),
  granted_by bigint NOT NULL REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id)
);

CREATE INDEX idx_platform_user_roles_role
  ON platform_user_roles(role);

CREATE INDEX idx_platform_user_roles_user
  ON platform_user_roles(user_id);
