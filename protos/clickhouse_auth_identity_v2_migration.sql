-- Auth identity v2 migration (idempotent)
-- Purpose:
-- 1) Ensure new auth identity columns exist on analytics.analytics_events.
-- 2) Provide a read-side view that prefers new semantics and only falls back to legacy email.

ALTER TABLE analytics.analytics_events
    ADD COLUMN IF NOT EXISTS login_account_type Nullable(String) AFTER login_email;

ALTER TABLE analytics.analytics_events
    ADD COLUMN IF NOT EXISTS login_account_identifier_hash Nullable(String) AFTER login_account_type;

ALTER TABLE analytics.analytics_events
    ADD COLUMN IF NOT EXISTS login_user_id Nullable(String) AFTER login_account_identifier_hash;

ALTER TABLE analytics.analytics_events
    ADD COLUMN IF NOT EXISTS logout_account_type Nullable(String) AFTER logout_email;

ALTER TABLE analytics.analytics_events
    ADD COLUMN IF NOT EXISTS logout_account_identifier_hash Nullable(String) AFTER logout_account_type;

ALTER TABLE analytics.analytics_events
    ADD COLUMN IF NOT EXISTS logout_user_id Nullable(String) AFTER logout_account_identifier_hash;

ALTER TABLE analytics.analytics_events
    ADD COLUMN IF NOT EXISTS register_account_type Nullable(String) AFTER register_email;

ALTER TABLE analytics.analytics_events
    ADD COLUMN IF NOT EXISTS register_account_identifier_hash Nullable(String) AFTER register_account_type;

ALTER TABLE analytics.analytics_events
    ADD COLUMN IF NOT EXISTS register_user_id Nullable(String) AFTER register_account_identifier_hash;

DROP VIEW IF EXISTS analytics.auth_identity_events_v2;

CREATE VIEW analytics.auth_identity_events_v2 AS
SELECT
    server_ts,
    event_type,
    multiIf(
        event_type = 'user_login',
            if(
                notEmpty(trimBoth(ifNull(login_account_type, ''))),
                lowerUTF8(trimBoth(ifNull(login_account_type, ''))),
                if(notEmpty(trimBoth(ifNull(login_email, ''))), 'email', 'unknown')
            ),
        event_type = 'user_logout',
            if(
                notEmpty(trimBoth(ifNull(logout_account_type, ''))),
                lowerUTF8(trimBoth(ifNull(logout_account_type, ''))),
                if(notEmpty(trimBoth(ifNull(logout_email, ''))), 'email', 'unknown')
            ),
        event_type = 'user_register',
            if(
                notEmpty(trimBoth(ifNull(register_account_type, ''))),
                lowerUTF8(trimBoth(ifNull(register_account_type, ''))),
                if(notEmpty(trimBoth(ifNull(register_email, ''))), 'email', 'unknown')
            ),
        'unknown'
    ) AS account_type,
    multiIf(
        event_type = 'user_login', nullIf(trimBoth(ifNull(login_account_identifier_hash, '')), ''),
        event_type = 'user_logout', nullIf(trimBoth(ifNull(logout_account_identifier_hash, '')), ''),
        event_type = 'user_register', nullIf(trimBoth(ifNull(register_account_identifier_hash, '')), ''),
        NULL
    ) AS account_identifier_hash,
    multiIf(
        event_type = 'user_login', nullIf(trimBoth(ifNull(login_user_id, '')), ''),
        event_type = 'user_logout', nullIf(trimBoth(ifNull(logout_user_id, '')), ''),
        event_type = 'user_register', nullIf(trimBoth(ifNull(register_user_id, '')), ''),
        nullIf(trimBoth(ifNull(user_id, '')), '')
    ) AS auth_user_id,
    multiIf(
        event_type = 'user_login', nullIf(trimBoth(ifNull(login_email, '')), ''),
        event_type = 'user_logout', nullIf(trimBoth(ifNull(logout_email, '')), ''),
        event_type = 'user_register', nullIf(trimBoth(ifNull(register_email, '')), ''),
        NULL
    ) AS legacy_email
FROM analytics.analytics_events
WHERE event_type IN ('user_login', 'user_logout', 'user_register');

-- Rollout checks
-- 1) New semantic coverage (target: unknown / empty hash trending to zero)
SELECT
    event_type,
    account_type,
    toUInt64(count()) AS total_events,
    toUInt64(countIf(account_identifier_hash IS NULL)) AS missing_identifier_hash
FROM analytics.auth_identity_events_v2
WHERE server_ts >= now64(3) - toIntervalDay(7)
GROUP BY event_type, account_type
ORDER BY event_type ASC, total_events DESC;

-- 2) Legacy email usage trend (target: only email-type events keep value)
SELECT
    event_type,
    toUInt64(countIf(legacy_email IS NOT NULL)) AS legacy_email_events
FROM analytics.auth_identity_events_v2
WHERE server_ts >= now64(3) - toIntervalDay(7)
GROUP BY event_type
ORDER BY event_type ASC;
