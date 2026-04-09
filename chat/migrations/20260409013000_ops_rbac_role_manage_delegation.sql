ALTER TABLE platform_user_roles
  DROP CONSTRAINT IF EXISTS platform_user_roles_role_check;

ALTER TABLE platform_user_roles
  ADD CONSTRAINT platform_user_roles_role_check
  CHECK (role IN ('ops_admin', 'ops_reviewer', 'ops_viewer', 'platform_role_admin'));
