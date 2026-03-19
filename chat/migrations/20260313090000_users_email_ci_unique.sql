DROP INDEX IF EXISTS email_index;
DROP INDEX IF EXISTS users_email_unique_idx;

CREATE UNIQUE INDEX users_email_lower_unique_idx
  ON users ((lower(btrim(email))))
  WHERE email IS NOT NULL AND btrim(email) <> '';
