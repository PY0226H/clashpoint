use super::*;
use crate::models::OpsPermission;

const OPS_DEBATE_TOPIC_AUDIT_ACTION_CREATE: &str = "create";
const OPS_DEBATE_TOPIC_AUDIT_ACTION_CREATE_REPLAY: &str = "create_replay";
const OPS_DEBATE_TOPIC_AUDIT_ACTION_UPDATE: &str = "update";
const OPS_DEBATE_SESSION_AUDIT_ACTION_CREATE: &str = "create";
const OPS_DEBATE_SESSION_AUDIT_ACTION_CREATE_REPLAY: &str = "create_replay";
const OPS_DEBATE_SESSION_AUDIT_ACTION_UPDATE: &str = "update";
const DEBATE_TOPIC_DESCRIPTION_MAX_LEN: usize = 4000;
const DEBATE_TOPIC_CONFLICT_DUPLICATE_TITLE_IN_CATEGORY: &str =
    "debate_topic_duplicate_title_in_category";
const DEBATE_TOPIC_CONFLICT_REVISION: &str = "debate_topic_revision_conflict";
const DEBATE_SESSION_CONFLICT_REVISION: &str = "debate_session_revision_conflict";
const DEBATE_SESSION_CONFLICT_UPDATE_LOCK_TIMEOUT: &str = "debate_session_update_lock_timeout";
const DEBATE_SESSION_INVALID_TOPIC_ID: &str = "debate_session_topic_id_invalid";
const DEBATE_SESSION_INVALID_ID: &str = "debate_session_id_invalid";
const DEBATE_SESSION_UPDATE_LOCK_TIMEOUT_MS: i64 = 750;

fn map_update_session_lock_sqlx_error(err: sqlx::Error, session_id: u64) -> AppError {
    if let sqlx::Error::Database(db_err) = &err {
        let code = db_err.code().map(|v| v.to_string()).unwrap_or_default();
        if matches!(code.as_str(), "55P03" | "57014") {
            warn!(
                session_id,
                sql_state = code.as_str(),
                "update debate session failed due to lock timeout/lock unavailable"
            );
            return AppError::DebateConflict(
                DEBATE_SESSION_CONFLICT_UPDATE_LOCK_TIMEOUT.to_string(),
            );
        }
    }
    err.into()
}

#[allow(dead_code)]
impl AppState {
    pub async fn create_debate_topic_by_owner(
        &self,
        user: &User,
        input: OpsCreateDebateTopicInput,
    ) -> Result<DebateTopic, AppError> {
        let (topic, _) = self
            .create_debate_topic_by_owner_with_meta(user, input, None)
            .await?;
        Ok(topic)
    }

    pub async fn create_debate_topic_by_owner_with_meta(
        &self,
        user: &User,
        input: OpsCreateDebateTopicInput,
        idempotency_key: Option<&str>,
    ) -> Result<(DebateTopic, bool), AppError> {
        self.ensure_ops_permission(user, OpsPermission::DebateManage)
            .await?;

        let title = normalize_ops_topic_field_with_codes(
            &input.title,
            "debate_topic_title_empty",
            "debate_topic_title_too_long",
            DEBATE_TOPIC_TITLE_MAX_LEN,
        )?;
        let description = normalize_ops_topic_field_with_codes(
            &input.description,
            "debate_topic_description_empty",
            "debate_topic_description_too_long",
            DEBATE_TOPIC_DESCRIPTION_MAX_LEN,
        )?;
        let category = normalize_topic_category_with_codes(
            &input.category,
            "debate_topic_category_empty",
            "debate_topic_category_too_long",
            DEBATE_TOPIC_CATEGORY_MAX_LEN,
        )?;
        let stance_pro = normalize_ops_topic_field_with_codes(
            &input.stance_pro,
            "debate_topic_stance_pro_empty",
            "debate_topic_stance_pro_too_long",
            DEBATE_STANCE_MAX_LEN,
        )?;
        let stance_con = normalize_ops_topic_field_with_codes(
            &input.stance_con,
            "debate_topic_stance_con_empty",
            "debate_topic_stance_con_too_long",
            DEBATE_STANCE_MAX_LEN,
        )?;
        let context_seed = normalize_optional_ops_topic_field_with_codes(
            input.context_seed,
            "debate_topic_context_seed_too_long",
            DEBATE_TOPIC_CONTEXT_SEED_MAX_LEN,
        )?;

        let mut tx = self.pool.begin().await?;
        if let Some(key) = idempotency_key {
            let lock_key = format!("ops_debate_topic_create:{}:{}", user.id, key);
            sqlx::query("SELECT pg_advisory_xact_lock(hashtext($1))")
                .bind(&lock_key)
                .execute(&mut *tx)
                .await?;
            if let Some(existing_topic_id) = self
                .load_ops_debate_topic_idempotency_row(&mut tx, user.id, key)
                .await?
            {
                let existing = self
                    .load_debate_topic_by_id_for_ops(&mut tx, existing_topic_id)
                    .await?;
                self.insert_ops_debate_topic_audit(
                    &mut tx,
                    existing.id,
                    user.id,
                    OPS_DEBATE_TOPIC_AUDIT_ACTION_CREATE_REPLAY,
                    Some(key),
                )
                .await?;
                tx.commit().await?;
                return Ok((existing, true));
            }
        }
        // Serialize writes for the same normalized topic key so concurrent creates
        // don't bypass the read-before-write duplicate guard.
        let dedupe_lock_key = format!(
            "ops_debate_topic_dedupe:{}:{}",
            category,
            title.to_lowercase()
        );
        sqlx::query("SELECT pg_advisory_xact_lock(hashtext($1))")
            .bind(&dedupe_lock_key)
            .execute(&mut *tx)
            .await?;
        if self
            .find_existing_topic_id_by_title_and_category(&mut tx, &title, &category, None)
            .await?
            .is_some()
        {
            return Err(AppError::DebateConflict(
                DEBATE_TOPIC_CONFLICT_DUPLICATE_TITLE_IN_CATEGORY.to_string(),
            ));
        }

        let row: DebateTopic = sqlx::query_as(
            r#"
            INSERT INTO debate_topics(
                title, description, category, stance_pro, stance_con,
                context_seed, is_active, created_by
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING
                id, title, description, category, stance_pro, stance_con,
                context_seed, is_active, created_by, created_at, updated_at
            "#,
        )
        .bind(title)
        .bind(description)
        .bind(category)
        .bind(stance_pro)
        .bind(stance_con)
        .bind(context_seed)
        .bind(input.is_active)
        .bind(user.id)
        .fetch_one(&mut *tx)
        .await?;

        if let Some(key) = idempotency_key {
            sqlx::query(
                r#"
                INSERT INTO ops_debate_topic_idempotency_keys(
                    user_id, idempotency_key, topic_id, created_at
                )
                VALUES ($1, $2, $3, NOW())
                "#,
            )
            .bind(user.id)
            .bind(key)
            .bind(row.id)
            .execute(&mut *tx)
            .await?;
        }

        self.insert_ops_debate_topic_audit(
            &mut tx,
            row.id,
            user.id,
            OPS_DEBATE_TOPIC_AUDIT_ACTION_CREATE,
            idempotency_key,
        )
        .await?;
        tx.commit().await?;
        Ok((row, false))
    }

    pub async fn create_debate_session_by_owner(
        &self,
        user: &User,
        input: OpsCreateDebateSessionInput,
    ) -> Result<DebateSessionSummary, AppError> {
        let (session, _) = self
            .create_debate_session_by_owner_with_meta(user, input, None)
            .await?;
        Ok(session)
    }

    pub async fn create_debate_session_by_owner_with_meta(
        &self,
        user: &User,
        input: OpsCreateDebateSessionInput,
        idempotency_key: Option<&str>,
    ) -> Result<(DebateSessionSummary, bool), AppError> {
        self.ensure_ops_permission(user, OpsPermission::DebateManage)
            .await?;

        let topic_id = safe_u64_to_i64(input.topic_id, DEBATE_SESSION_INVALID_TOPIC_ID)?;
        let status = normalize_ops_session_status(input.status)?;
        if status.len() > DEBATE_SESSION_STATUS_MAX_LEN {
            return Err(AppError::DebateError(format!(
                "status is too long, max {}",
                DEBATE_SESSION_STATUS_MAX_LEN
            )));
        }

        let max_per_side = input.max_participants_per_side.unwrap_or(500);
        if max_per_side <= 0 {
            return Err(AppError::DebateError(
                "maxParticipantsPerSide must be > 0".to_string(),
            ));
        }
        if input.end_at <= input.scheduled_start_at {
            return Err(AppError::DebateError(
                "scheduledStartAt must be before endAt".to_string(),
            ));
        }
        let now = Utc::now();
        if input.end_at <= now {
            return Err(AppError::DebateError(
                "session endAt must be in the future".to_string(),
            ));
        }

        let mut tx = self.pool.begin().await?;
        if let Some(key) = idempotency_key {
            let lock_key = format!("ops_debate_session_create:{}:{}", user.id, key);
            sqlx::query("SELECT pg_advisory_xact_lock(hashtext($1))")
                .bind(&lock_key)
                .execute(&mut *tx)
                .await?;
            if let Some(existing_session_id) = self
                .load_ops_debate_session_idempotency_row(&mut tx, user.id, key)
                .await?
            {
                let existing = self
                    .load_debate_session_by_id_for_ops(&mut tx, existing_session_id)
                    .await?;
                self.insert_ops_debate_session_audit(
                    &mut tx,
                    existing.id,
                    user.id,
                    OPS_DEBATE_SESSION_AUDIT_ACTION_CREATE_REPLAY,
                    Some(key),
                )
                .await?;
                tx.commit().await?;
                return Ok((existing, true));
            }
        }

        let topic_exists: Option<(i64,)> = sqlx::query_as(
            r#"
            SELECT id
            FROM debate_topics
            WHERE id = $1
            FOR SHARE
            "#,
        )
        .bind(topic_id)
        .fetch_optional(&mut *tx)
        .await?;

        if topic_exists.is_none() {
            return Err(AppError::NotFound(format!(
                "debate topic id {}",
                input.topic_id
            )));
        }

        let row: DebateSessionSummary = sqlx::query_as(
            r#"
            INSERT INTO debate_sessions(
                topic_id, status, scheduled_start_at, actual_start_at, end_at, max_participants_per_side
            )
            VALUES ($1, $2, $3, NULL, $4, $5)
            RETURNING
                id, topic_id, status, scheduled_start_at, actual_start_at, end_at,
                max_participants_per_side, pro_count, con_count, hot_score, created_at, updated_at,
                (
                    (status IN ('open', 'running'))
                    AND scheduled_start_at <= NOW()
                    AND end_at > NOW()
                ) AS joinable
            "#,
        )
        .bind(topic_id)
        .bind(status)
        .bind(input.scheduled_start_at)
        .bind(input.end_at)
        .bind(max_per_side)
        .fetch_one(&mut *tx)
        .await?;

        if let Some(key) = idempotency_key {
            sqlx::query(
                r#"
                INSERT INTO ops_debate_session_idempotency_keys(
                    user_id, idempotency_key, session_id, created_at
                )
                VALUES ($1, $2, $3, NOW())
                "#,
            )
            .bind(user.id)
            .bind(key)
            .bind(row.id)
            .execute(&mut *tx)
            .await?;
        }

        self.insert_ops_debate_session_audit(
            &mut tx,
            row.id,
            user.id,
            OPS_DEBATE_SESSION_AUDIT_ACTION_CREATE,
            idempotency_key,
        )
        .await?;
        tx.commit().await?;
        Ok((row, false))
    }

    pub async fn update_debate_topic_by_owner(
        &self,
        user: &User,
        topic_id: u64,
        input: OpsUpdateDebateTopicInput,
    ) -> Result<DebateTopic, AppError> {
        self.ensure_ops_permission(user, OpsPermission::DebateManage)
            .await?;

        let topic_id = safe_u64_to_i64(topic_id, "debate_topic_id_invalid")?;
        let OpsUpdateDebateTopicInput {
            title: raw_title,
            description: raw_description,
            category: raw_category,
            stance_pro: raw_stance_pro,
            stance_con: raw_stance_con,
            context_seed: raw_context_seed,
            is_active,
            expected_updated_at,
        } = input;

        let title = normalize_ops_topic_field_with_codes(
            &raw_title,
            "debate_topic_title_empty",
            "debate_topic_title_too_long",
            DEBATE_TOPIC_TITLE_MAX_LEN,
        )?;
        let description = normalize_ops_topic_field_with_codes(
            &raw_description,
            "debate_topic_description_empty",
            "debate_topic_description_too_long",
            DEBATE_TOPIC_DESCRIPTION_MAX_LEN,
        )?;
        let category = normalize_topic_category_with_codes(
            &raw_category,
            "debate_topic_category_empty",
            "debate_topic_category_too_long",
            DEBATE_TOPIC_CATEGORY_MAX_LEN,
        )?;
        let stance_pro = normalize_ops_topic_field_with_codes(
            &raw_stance_pro,
            "debate_topic_stance_pro_empty",
            "debate_topic_stance_pro_too_long",
            DEBATE_STANCE_MAX_LEN,
        )?;
        let stance_con = normalize_ops_topic_field_with_codes(
            &raw_stance_con,
            "debate_topic_stance_con_empty",
            "debate_topic_stance_con_too_long",
            DEBATE_STANCE_MAX_LEN,
        )?;
        let context_seed = normalize_optional_ops_topic_field_with_codes(
            raw_context_seed,
            "debate_topic_context_seed_too_long",
            DEBATE_TOPIC_CONTEXT_SEED_MAX_LEN,
        )?;

        let mut tx = self.pool.begin().await?;

        let current: Option<(DateTime<Utc>,)> = sqlx::query_as(
            r#"
            SELECT updated_at
            FROM debate_topics
            WHERE id = $1
            FOR UPDATE
            "#,
        )
        .bind(topic_id)
        .fetch_optional(&mut *tx)
        .await?;
        let current_updated_at = current
            .map(|v| v.0)
            .ok_or_else(|| AppError::NotFound(format!("debate topic id {topic_id}")))?;
        if let Some(expected_updated_at) = expected_updated_at {
            if current_updated_at != expected_updated_at {
                return Err(AppError::DebateConflict(
                    DEBATE_TOPIC_CONFLICT_REVISION.to_string(),
                ));
            }
        }

        // Serialize writes for the same normalized topic key to keep duplicate
        // checks deterministic across create/update paths.
        let dedupe_lock_key = format!(
            "ops_debate_topic_dedupe:{}:{}",
            category,
            title.to_lowercase()
        );
        sqlx::query("SELECT pg_advisory_xact_lock(hashtext($1))")
            .bind(&dedupe_lock_key)
            .execute(&mut *tx)
            .await?;
        if self
            .find_existing_topic_id_by_title_and_category(
                &mut tx,
                &title,
                &category,
                Some(topic_id),
            )
            .await?
            .is_some()
        {
            return Err(AppError::DebateConflict(
                DEBATE_TOPIC_CONFLICT_DUPLICATE_TITLE_IN_CATEGORY.to_string(),
            ));
        }

        let row: DebateTopic = sqlx::query_as(
            r#"
            UPDATE debate_topics
            SET
              title = $2,
              description = $3,
              category = $4,
              stance_pro = $5,
              stance_con = $6,
              context_seed = $7,
              is_active = $8,
              updated_at = NOW()
            WHERE id = $1
            RETURNING
                id, title, description, category, stance_pro, stance_con,
                context_seed, is_active, created_by, created_at, updated_at
            "#,
        )
        .bind(topic_id)
        .bind(title)
        .bind(description)
        .bind(category)
        .bind(stance_pro)
        .bind(stance_con)
        .bind(context_seed)
        .bind(is_active)
        .fetch_one(&mut *tx)
        .await?;
        self.insert_ops_debate_topic_audit(
            &mut tx,
            row.id,
            user.id,
            OPS_DEBATE_TOPIC_AUDIT_ACTION_UPDATE,
            None,
        )
        .await?;
        tx.commit().await?;
        Ok(row)
    }

    async fn load_ops_debate_topic_idempotency_row(
        &self,
        tx: &mut Transaction<'_, Postgres>,
        user_id: i64,
        idempotency_key: &str,
    ) -> Result<Option<i64>, AppError> {
        let row: Option<(i64,)> = sqlx::query_as(
            r#"
            SELECT topic_id
            FROM ops_debate_topic_idempotency_keys
            WHERE user_id = $1
              AND idempotency_key = $2
            "#,
        )
        .bind(user_id)
        .bind(idempotency_key)
        .fetch_optional(&mut **tx)
        .await?;
        Ok(row.map(|v| v.0))
    }

    async fn load_debate_topic_by_id_for_ops(
        &self,
        tx: &mut Transaction<'_, Postgres>,
        topic_id: i64,
    ) -> Result<DebateTopic, AppError> {
        let row: DebateTopic = sqlx::query_as(
            r#"
            SELECT
                id, title, description, category, stance_pro, stance_con,
                context_seed, is_active, created_by, created_at, updated_at
            FROM debate_topics
            WHERE id = $1
            "#,
        )
        .bind(topic_id)
        .fetch_one(&mut **tx)
        .await?;
        Ok(row)
    }

    async fn load_ops_debate_session_idempotency_row(
        &self,
        tx: &mut Transaction<'_, Postgres>,
        user_id: i64,
        idempotency_key: &str,
    ) -> Result<Option<i64>, AppError> {
        let row: Option<(i64,)> = sqlx::query_as(
            r#"
            SELECT session_id
            FROM ops_debate_session_idempotency_keys
            WHERE user_id = $1
              AND idempotency_key = $2
            "#,
        )
        .bind(user_id)
        .bind(idempotency_key)
        .fetch_optional(&mut **tx)
        .await?;
        Ok(row.map(|v| v.0))
    }

    async fn load_debate_session_by_id_for_ops(
        &self,
        tx: &mut Transaction<'_, Postgres>,
        session_id: i64,
    ) -> Result<DebateSessionSummary, AppError> {
        let row = sqlx::query_as(
            r#"
            SELECT
                id, topic_id, status, scheduled_start_at, actual_start_at, end_at,
                max_participants_per_side, pro_count, con_count, hot_score, created_at, updated_at,
                (
                    (status IN ('open', 'running'))
                    AND scheduled_start_at <= NOW()
                    AND end_at > NOW()
                ) AS joinable
            FROM debate_sessions
            WHERE id = $1
            "#,
        )
        .bind(session_id)
        .fetch_one(&mut **tx)
        .await?;
        Ok(row)
    }

    async fn insert_ops_debate_topic_audit(
        &self,
        tx: &mut Transaction<'_, Postgres>,
        topic_id: i64,
        operator_user_id: i64,
        action: &str,
        idempotency_key: Option<&str>,
    ) -> Result<(), AppError> {
        sqlx::query(
            r#"
            INSERT INTO ops_debate_topic_audits(
                topic_id, operator_user_id, action, idempotency_key, created_at
            )
            VALUES ($1, $2, $3, $4, NOW())
            "#,
        )
        .bind(topic_id)
        .bind(operator_user_id)
        .bind(action)
        .bind(idempotency_key)
        .execute(&mut **tx)
        .await?;
        Ok(())
    }

    async fn insert_ops_debate_session_audit(
        &self,
        tx: &mut Transaction<'_, Postgres>,
        session_id: i64,
        operator_user_id: i64,
        action: &str,
        idempotency_key: Option<&str>,
    ) -> Result<(), AppError> {
        sqlx::query(
            r#"
            INSERT INTO ops_debate_session_audits(
                session_id, operator_user_id, action, idempotency_key, created_at
            )
            VALUES ($1, $2, $3, $4, NOW())
            "#,
        )
        .bind(session_id)
        .bind(operator_user_id)
        .bind(action)
        .bind(idempotency_key)
        .execute(&mut **tx)
        .await?;
        Ok(())
    }

    async fn find_existing_topic_id_by_title_and_category(
        &self,
        tx: &mut Transaction<'_, Postgres>,
        title: &str,
        category: &str,
        exclude_topic_id: Option<i64>,
    ) -> Result<Option<i64>, AppError> {
        let row: Option<(i64,)> = sqlx::query_as(
            r#"
            SELECT id
            FROM debate_topics
            WHERE LOWER(BTRIM(title)) = LOWER(BTRIM($1))
              AND category = $2
              AND ($3::bigint IS NULL OR id <> $3)
            ORDER BY id DESC
            LIMIT 1
            "#,
        )
        .bind(title)
        .bind(category)
        .bind(exclude_topic_id)
        .fetch_optional(&mut **tx)
        .await?;
        Ok(row.map(|v| v.0))
    }

    pub async fn update_debate_session_by_owner(
        &self,
        user: &User,
        session_id: u64,
        input: OpsUpdateDebateSessionInput,
    ) -> Result<DebateSessionSummary, AppError> {
        self.ensure_ops_permission(user, OpsPermission::DebateManage)
            .await?;

        let session_id_i64 = safe_u64_to_i64(session_id, DEBATE_SESSION_INVALID_ID)?;
        let status_input = normalize_ops_manage_session_status(input.status)?;
        let mut tx = self.pool.begin().await?;
        let lock_timeout = format!("{}ms", DEBATE_SESSION_UPDATE_LOCK_TIMEOUT_MS);
        sqlx::query("SELECT set_config('lock_timeout', $1, true)")
            .bind(&lock_timeout)
            .execute(&mut *tx)
            .await?;

        let current = sqlx::query_as::<_, DebateSessionForOpsUpdate>(
            r#"
            SELECT
              status, scheduled_start_at, end_at, max_participants_per_side,
              pro_count, con_count, updated_at, NOW() AS db_now
            FROM debate_sessions
            WHERE id = $1
            FOR UPDATE
            "#,
        )
        .bind(session_id_i64)
        .fetch_optional(&mut *tx)
        .await
        .map_err(|err| map_update_session_lock_sqlx_error(err, session_id))?
        .ok_or_else(|| AppError::NotFound(format!("debate session id {session_id}")))?;
        if let Some(expected_updated_at) = input.expected_updated_at {
            if current.updated_at != expected_updated_at {
                return Err(AppError::DebateConflict(
                    DEBATE_SESSION_CONFLICT_REVISION.to_string(),
                ));
            }
        }

        let next_status = status_input.unwrap_or(current.status);
        if next_status.len() > DEBATE_SESSION_STATUS_MAX_LEN {
            return Err(AppError::DebateError(format!(
                "status is too long, max {}",
                DEBATE_SESSION_STATUS_MAX_LEN
            )));
        }

        let next_scheduled_start = input
            .scheduled_start_at
            .unwrap_or(current.scheduled_start_at);
        let next_end_at = input.end_at.unwrap_or(current.end_at);
        if next_end_at <= next_scheduled_start {
            return Err(AppError::DebateError(
                "scheduledStartAt must be before endAt".to_string(),
            ));
        }
        if matches!(next_status.as_str(), "open" | "running") && next_end_at <= current.db_now {
            return Err(AppError::DebateError(
                "open/running session must end in the future".to_string(),
            ));
        }

        let next_max_per_side = input
            .max_participants_per_side
            .unwrap_or(current.max_participants_per_side);
        if next_max_per_side <= 0 {
            return Err(AppError::DebateError(
                "maxParticipantsPerSide must be > 0".to_string(),
            ));
        }
        if current.pro_count > next_max_per_side || current.con_count > next_max_per_side {
            return Err(AppError::DebateConflict(format!(
                "maxParticipantsPerSide {} is smaller than current participant count",
                next_max_per_side
            )));
        }

        let row: DebateSessionSummary = sqlx::query_as(
            r#"
            UPDATE debate_sessions
            SET
              status = $2,
              scheduled_start_at = $3,
              end_at = $4,
              max_participants_per_side = $5,
              updated_at = NOW()
            WHERE id = $1
            RETURNING
                id, topic_id, status, scheduled_start_at, actual_start_at, end_at,
                max_participants_per_side, pro_count, con_count, hot_score, created_at, updated_at,
                (
                    (status IN ('open', 'running'))
                    AND scheduled_start_at <= NOW()
                    AND end_at > NOW()
                    AND (
                        pro_count < max_participants_per_side
                        OR con_count < max_participants_per_side
                    )
                ) AS joinable
            "#,
        )
        .bind(session_id_i64)
        .bind(next_status)
        .bind(next_scheduled_start)
        .bind(next_end_at)
        .bind(next_max_per_side)
        .fetch_one(&mut *tx)
        .await?;

        self.insert_ops_debate_session_audit(
            &mut tx,
            row.id,
            user.id,
            OPS_DEBATE_SESSION_AUDIT_ACTION_UPDATE,
            None,
        )
        .await?;

        tx.commit().await?;
        Ok(row)
    }
}
