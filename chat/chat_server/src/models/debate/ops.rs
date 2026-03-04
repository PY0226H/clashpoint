use super::*;

#[allow(dead_code)]
impl AppState {
    async fn ensure_workspace_owner(&self, ws_id: i64, user_id: i64) -> Result<(), AppError> {
        let owner_row: Option<(i64,)> =
            sqlx::query_as("SELECT owner_id FROM workspaces WHERE id = $1")
                .bind(ws_id)
                .fetch_optional(&self.pool)
                .await?;
        let Some((owner_id,)) = owner_row else {
            return Err(AppError::NotFound(format!("workspace id {}", ws_id)));
        };
        if owner_id != user_id {
            return Err(AppError::DebateConflict(
                "only workspace owner can manage debate operations".to_string(),
            ));
        }
        Ok(())
    }

    pub async fn create_debate_topic_by_owner(
        &self,
        user: &User,
        input: OpsCreateDebateTopicInput,
    ) -> Result<DebateTopic, AppError> {
        self.ensure_workspace_owner(user.ws_id, user.id).await?;

        let title = normalize_ops_topic_field(&input.title, "title", DEBATE_TOPIC_TITLE_MAX_LEN)?;
        let description = normalize_ops_topic_field(&input.description, "description", 4000)?;
        let category =
            normalize_ops_topic_field(&input.category, "category", DEBATE_TOPIC_CATEGORY_MAX_LEN)?;
        let stance_pro =
            normalize_ops_topic_field(&input.stance_pro, "stance_pro", DEBATE_STANCE_MAX_LEN)?;
        let stance_con =
            normalize_ops_topic_field(&input.stance_con, "stance_con", DEBATE_STANCE_MAX_LEN)?;
        let context_seed = input
            .context_seed
            .map(|v| v.trim().to_string())
            .filter(|v| !v.is_empty());

        let row = sqlx::query_as(
            r#"
            INSERT INTO debate_topics(
                ws_id, title, description, category, stance_pro, stance_con,
                context_seed, is_active, created_by
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING
                id, ws_id, title, description, category, stance_pro, stance_con,
                context_seed, is_active, created_by, created_at, updated_at
            "#,
        )
        .bind(user.ws_id)
        .bind(title)
        .bind(description)
        .bind(category)
        .bind(stance_pro)
        .bind(stance_con)
        .bind(context_seed)
        .bind(input.is_active)
        .bind(user.id)
        .fetch_one(&self.pool)
        .await?;

        Ok(row)
    }

    pub async fn create_debate_session_by_owner(
        &self,
        user: &User,
        input: OpsCreateDebateSessionInput,
    ) -> Result<DebateSessionSummary, AppError> {
        self.ensure_workspace_owner(user.ws_id, user.id).await?;

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
        if matches!(status.as_str(), "open" | "running") && input.end_at <= now {
            return Err(AppError::DebateError(
                "open/running session must end in the future".to_string(),
            ));
        }

        let topic_exists: Option<(i64,)> = sqlx::query_as(
            r#"
            SELECT id
            FROM debate_topics
            WHERE id = $1 AND ws_id = $2
            "#,
        )
        .bind(input.topic_id as i64)
        .bind(user.ws_id)
        .fetch_optional(&self.pool)
        .await?;

        if topic_exists.is_none() {
            return Err(AppError::NotFound(format!(
                "debate topic id {}",
                input.topic_id
            )));
        }

        let row = sqlx::query_as(
            r#"
            INSERT INTO debate_sessions(
                ws_id, topic_id, status, scheduled_start_at, actual_start_at, end_at, max_participants_per_side
            )
            VALUES ($1, $2, $3, $4, NULL, $5, $6)
            RETURNING
                id, ws_id, topic_id, status, scheduled_start_at, actual_start_at, end_at,
                max_participants_per_side, pro_count, con_count, hot_score, created_at, updated_at,
                (
                    (status IN ('open', 'running'))
                    AND scheduled_start_at <= NOW()
                    AND end_at > NOW()
                ) AS joinable
            "#,
        )
        .bind(user.ws_id)
        .bind(input.topic_id as i64)
        .bind(status)
        .bind(input.scheduled_start_at)
        .bind(input.end_at)
        .bind(max_per_side)
        .fetch_one(&self.pool)
        .await?;

        Ok(row)
    }

    pub async fn update_debate_topic_by_owner(
        &self,
        user: &User,
        topic_id: u64,
        input: OpsUpdateDebateTopicInput,
    ) -> Result<DebateTopic, AppError> {
        self.ensure_workspace_owner(user.ws_id, user.id).await?;

        let title = normalize_ops_topic_field(&input.title, "title", DEBATE_TOPIC_TITLE_MAX_LEN)?;
        let description = normalize_ops_topic_field(&input.description, "description", 4000)?;
        let category =
            normalize_ops_topic_field(&input.category, "category", DEBATE_TOPIC_CATEGORY_MAX_LEN)?;
        let stance_pro =
            normalize_ops_topic_field(&input.stance_pro, "stance_pro", DEBATE_STANCE_MAX_LEN)?;
        let stance_con =
            normalize_ops_topic_field(&input.stance_con, "stance_con", DEBATE_STANCE_MAX_LEN)?;
        let context_seed = input
            .context_seed
            .map(|v| v.trim().to_string())
            .filter(|v| !v.is_empty());

        let row = sqlx::query_as(
            r#"
            UPDATE debate_topics
            SET
              title = $3,
              description = $4,
              category = $5,
              stance_pro = $6,
              stance_con = $7,
              context_seed = $8,
              is_active = $9,
              updated_at = NOW()
            WHERE id = $1 AND ws_id = $2
            RETURNING
                id, ws_id, title, description, category, stance_pro, stance_con,
                context_seed, is_active, created_by, created_at, updated_at
            "#,
        )
        .bind(topic_id as i64)
        .bind(user.ws_id)
        .bind(title)
        .bind(description)
        .bind(category)
        .bind(stance_pro)
        .bind(stance_con)
        .bind(context_seed)
        .bind(input.is_active)
        .fetch_optional(&self.pool)
        .await?;

        row.ok_or_else(|| AppError::NotFound(format!("debate topic id {topic_id}")))
    }

    pub async fn update_debate_session_by_owner(
        &self,
        user: &User,
        session_id: u64,
        input: OpsUpdateDebateSessionInput,
    ) -> Result<DebateSessionSummary, AppError> {
        self.ensure_workspace_owner(user.ws_id, user.id).await?;

        let status_input = normalize_ops_manage_session_status(input.status)?;
        let mut tx = self.pool.begin().await?;

        let current = sqlx::query_as::<_, DebateSessionForOpsUpdate>(
            r#"
            SELECT status, scheduled_start_at, end_at, max_participants_per_side, pro_count, con_count
            FROM debate_sessions
            WHERE id = $1 AND ws_id = $2
            FOR UPDATE
            "#,
        )
        .bind(session_id as i64)
        .bind(user.ws_id)
        .fetch_optional(&mut *tx)
        .await?
        .ok_or_else(|| AppError::NotFound(format!("debate session id {session_id}")))?;

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
        let now = Utc::now();
        if matches!(next_status.as_str(), "open" | "running") && next_end_at <= now {
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

        let row = sqlx::query_as(
            r#"
            UPDATE debate_sessions
            SET
              status = $3,
              scheduled_start_at = $4,
              end_at = $5,
              max_participants_per_side = $6,
              updated_at = NOW()
            WHERE id = $1 AND ws_id = $2
            RETURNING
                id, ws_id, topic_id, status, scheduled_start_at, actual_start_at, end_at,
                max_participants_per_side, pro_count, con_count, hot_score, created_at, updated_at,
                (
                    (status IN ('open', 'running'))
                    AND scheduled_start_at <= NOW()
                    AND end_at > NOW()
                ) AS joinable
            "#,
        )
        .bind(session_id as i64)
        .bind(user.ws_id)
        .bind(next_status)
        .bind(next_scheduled_start)
        .bind(next_end_at)
        .bind(next_max_per_side)
        .fetch_one(&mut *tx)
        .await?;

        tx.commit().await?;
        Ok(row)
    }
}
