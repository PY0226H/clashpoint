use crate::{AppError, AppState};
use chat_core::User;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::FromRow;
use utoipa::{IntoParams, ToSchema};

const DEFAULT_LIMIT: u64 = 20;
const MAX_LIMIT: u64 = 100;

#[derive(Debug, Clone, FromRow, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DebateTopic {
    pub id: i64,
    pub ws_id: i64,
    pub title: String,
    pub description: String,
    pub category: String,
    pub stance_pro: String,
    pub stance_con: String,
    pub context_seed: Option<String>,
    pub is_active: bool,
    pub created_by: i64,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DebateSessionSummary {
    pub id: i64,
    pub ws_id: i64,
    pub topic_id: i64,
    pub status: String,
    pub scheduled_start_at: DateTime<Utc>,
    pub actual_start_at: Option<DateTime<Utc>>,
    pub end_at: DateTime<Utc>,
    pub max_participants_per_side: i32,
    pub pro_count: i32,
    pub con_count: i32,
    pub hot_score: i32,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
    pub joinable: bool,
}

#[derive(Debug, Clone, IntoParams, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListDebateTopics {
    pub category: Option<String>,
    #[serde(default = "default_true")]
    pub active_only: bool,
    pub limit: Option<u64>,
}

#[derive(Debug, Clone, IntoParams, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListDebateSessions {
    pub status: Option<String>,
    pub topic_id: Option<u64>,
    pub from: Option<DateTime<Utc>>,
    pub to: Option<DateTime<Utc>>,
    pub limit: Option<u64>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JoinDebateSessionInput {
    pub side: String,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JoinDebateSessionOutput {
    pub session_id: u64,
    pub side: String,
    pub newly_joined: bool,
    pub pro_count: i32,
    pub con_count: i32,
}

#[derive(Debug, FromRow)]
struct DebateSessionForJoin {
    ws_id: i64,
    status: String,
    end_at: DateTime<Utc>,
    max_participants_per_side: i32,
    pro_count: i32,
    con_count: i32,
}

fn default_true() -> bool {
    true
}

fn normalize_limit(limit: Option<u64>) -> i64 {
    let limit = limit.unwrap_or(DEFAULT_LIMIT).max(1).min(MAX_LIMIT);
    limit as i64
}

fn valid_join_side(side: &str) -> bool {
    matches!(side, "pro" | "con")
}

fn can_join_status(status: &str) -> bool {
    matches!(status, "open" | "running")
}

#[allow(dead_code)]
impl AppState {
    pub async fn list_debate_topics(
        &self,
        ws_id: u64,
        input: ListDebateTopics,
    ) -> Result<Vec<DebateTopic>, AppError> {
        let limit = normalize_limit(input.limit);
        let topics = sqlx::query_as(
            r#"
            SELECT id, ws_id, title, description, category, stance_pro, stance_con, context_seed, is_active, created_by, created_at, updated_at
            FROM debate_topics
            WHERE ws_id = $1
              AND ($2::text IS NULL OR category = $2)
              AND (NOT $3::boolean OR is_active = TRUE)
            ORDER BY created_at DESC
            LIMIT $4
            "#,
        )
        .bind(ws_id as i64)
        .bind(input.category)
        .bind(input.active_only)
        .bind(limit)
        .fetch_all(&self.pool)
        .await?;

        Ok(topics)
    }

    pub async fn list_debate_sessions(
        &self,
        ws_id: u64,
        input: ListDebateSessions,
    ) -> Result<Vec<DebateSessionSummary>, AppError> {
        let limit = normalize_limit(input.limit);
        let rows = sqlx::query_as(
            r#"
            SELECT
                id, ws_id, topic_id, status, scheduled_start_at, actual_start_at, end_at,
                max_participants_per_side, pro_count, con_count, hot_score, created_at, updated_at,
                ((status IN ('open', 'running')) AND end_at > NOW()) AS joinable
            FROM debate_sessions
            WHERE ws_id = $1
              AND ($2::text IS NULL OR status = $2)
              AND ($3::bigint IS NULL OR topic_id = $3)
              AND ($4::timestamptz IS NULL OR scheduled_start_at >= $4)
              AND ($5::timestamptz IS NULL OR scheduled_start_at <= $5)
            ORDER BY scheduled_start_at DESC
            LIMIT $6
            "#,
        )
        .bind(ws_id as i64)
        .bind(input.status)
        .bind(input.topic_id.map(|v| v as i64))
        .bind(input.from)
        .bind(input.to)
        .bind(limit)
        .fetch_all(&self.pool)
        .await?;

        Ok(rows)
    }

    pub async fn join_debate_session(
        &self,
        session_id: u64,
        user: &User,
        input: JoinDebateSessionInput,
    ) -> Result<JoinDebateSessionOutput, AppError> {
        if !valid_join_side(&input.side) {
            return Err(AppError::DebateError(format!(
                "invalid side: {}, expect `pro` or `con`",
                input.side
            )));
        }

        let mut tx = self.pool.begin().await?;

        let Some(session) = sqlx::query_as::<_, DebateSessionForJoin>(
            r#"
            SELECT ws_id, status, end_at, max_participants_per_side, pro_count, con_count
            FROM debate_sessions
            WHERE id = $1
            FOR UPDATE
            "#,
        )
        .bind(session_id as i64)
        .fetch_optional(&mut *tx)
        .await?
        else {
            return Err(AppError::NotFound(format!(
                "debate session id {session_id}"
            )));
        };

        if session.ws_id != user.ws_id {
            return Err(AppError::NotFound(format!(
                "debate session id {session_id}"
            )));
        }

        if !can_join_status(&session.status) || session.end_at <= Utc::now() {
            return Err(AppError::DebateConflict(format!(
                "session {} is not joinable now",
                session_id
            )));
        }

        let existing: Option<(String,)> = sqlx::query_as(
            r#"
            SELECT side
            FROM session_participants
            WHERE session_id = $1 AND user_id = $2
            "#,
        )
        .bind(session_id as i64)
        .bind(user.id)
        .fetch_optional(&mut *tx)
        .await?;

        if let Some((side,)) = existing {
            if side == input.side {
                return Ok(JoinDebateSessionOutput {
                    session_id,
                    side,
                    newly_joined: false,
                    pro_count: session.pro_count,
                    con_count: session.con_count,
                });
            }
            return Err(AppError::DebateConflict(format!(
                "already joined side {}, cannot switch side in session {}",
                side, session_id
            )));
        }

        if input.side == "pro" && session.pro_count >= session.max_participants_per_side {
            return Err(AppError::DebateConflict(format!(
                "pro side is full in session {}",
                session_id
            )));
        }
        if input.side == "con" && session.con_count >= session.max_participants_per_side {
            return Err(AppError::DebateConflict(format!(
                "con side is full in session {}",
                session_id
            )));
        }

        sqlx::query(
            r#"
            INSERT INTO session_participants(session_id, user_id, side)
            VALUES ($1, $2, $3)
            "#,
        )
        .bind(session_id as i64)
        .bind(user.id)
        .bind(&input.side)
        .execute(&mut *tx)
        .await?;

        let (pro_count, con_count): (i32, i32) = if input.side == "pro" {
            sqlx::query_as(
                r#"
                UPDATE debate_sessions
                SET pro_count = pro_count + 1, updated_at = NOW()
                WHERE id = $1
                RETURNING pro_count, con_count
                "#,
            )
            .bind(session_id as i64)
            .fetch_one(&mut *tx)
            .await?
        } else {
            sqlx::query_as(
                r#"
                UPDATE debate_sessions
                SET con_count = con_count + 1, updated_at = NOW()
                WHERE id = $1
                RETURNING pro_count, con_count
                "#,
            )
            .bind(session_id as i64)
            .fetch_one(&mut *tx)
            .await?
        };

        tx.commit().await?;

        Ok(JoinDebateSessionOutput {
            session_id,
            side: input.side,
            newly_joined: true,
            pro_count,
            con_count,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use anyhow::Result;
    use chrono::Duration;

    async fn seed_topic_and_session(
        state: &AppState,
        ws_id: i64,
        status: &str,
        max_per_side: i32,
    ) -> Result<(i64, i64)> {
        let topic_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO debate_topics(ws_id, title, description, category, stance_pro, stance_con, context_seed, is_active, created_by)
            VALUES ($1, 'Should we nerf weapon X?', 'balance discussion', 'game', 'nerf', 'keep', 'meta notes', true, 1)
            RETURNING id
            "#,
        )
        .bind(ws_id)
        .fetch_one(&state.pool)
        .await?;

        let now = Utc::now();
        let session_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO debate_sessions(ws_id, topic_id, status, scheduled_start_at, actual_start_at, end_at, max_participants_per_side)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            "#,
        )
        .bind(ws_id)
        .bind(topic_id.0)
        .bind(status)
        .bind(now - Duration::minutes(5))
        .bind(now - Duration::minutes(3))
        .bind(now + Duration::minutes(30))
        .bind(max_per_side)
        .fetch_one(&state.pool)
        .await?;

        Ok((topic_id.0, session_id.0))
    }

    #[tokio::test]
    async fn list_debate_topics_should_filter_by_category() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        sqlx::query(
            r#"
            INSERT INTO debate_topics(ws_id, title, description, category, stance_pro, stance_con, is_active, created_by)
            VALUES
                (1, 'topic-game', 'desc', 'game', 'pro', 'con', true, 1),
                (1, 'topic-sports', 'desc', 'sports', 'pro', 'con', true, 1)
            "#,
        )
        .execute(&state.pool)
        .await?;

        let rows = state
            .list_debate_topics(
                1,
                ListDebateTopics {
                    category: Some("game".to_string()),
                    active_only: true,
                    limit: Some(50),
                },
            )
            .await?;
        assert!(rows.iter().all(|v| v.category == "game"));
        assert!(!rows.is_empty());
        Ok(())
    }

    #[tokio::test]
    async fn list_debate_sessions_should_return_joinable_flag() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_topic_id, session_id) = seed_topic_and_session(&state, 1, "open", 10).await?;

        let rows = state
            .list_debate_sessions(
                1,
                ListDebateSessions {
                    status: Some("open".to_string()),
                    topic_id: None,
                    from: None,
                    to: None,
                    limit: Some(20),
                },
            )
            .await?;

        let row = rows
            .into_iter()
            .find(|v| v.id == session_id)
            .expect("seeded session should exist");
        assert!(row.joinable);
        Ok(())
    }

    #[tokio::test]
    async fn join_debate_session_should_work_and_be_idempotent() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_topic_id, session_id) = seed_topic_and_session(&state, 1, "open", 10).await?;
        let user = state
            .find_user_by_id(1)
            .await?
            .expect("user id 1 should exist");

        let first = state
            .join_debate_session(
                session_id as u64,
                &user,
                JoinDebateSessionInput {
                    side: "pro".to_string(),
                },
            )
            .await?;
        assert!(first.newly_joined);
        assert_eq!(first.pro_count, 1);

        let second = state
            .join_debate_session(
                session_id as u64,
                &user,
                JoinDebateSessionInput {
                    side: "pro".to_string(),
                },
            )
            .await?;
        assert!(!second.newly_joined);
        assert_eq!(second.pro_count, 1);

        Ok(())
    }

    #[tokio::test]
    async fn join_debate_session_should_reject_invalid_side() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_topic_id, session_id) = seed_topic_and_session(&state, 1, "open", 10).await?;
        let user = state
            .find_user_by_id(1)
            .await?
            .expect("user id 1 should exist");

        let err = state
            .join_debate_session(
                session_id as u64,
                &user,
                JoinDebateSessionInput {
                    side: "middle".to_string(),
                },
            )
            .await
            .expect_err("invalid side should fail");
        assert!(matches!(err, AppError::DebateError(_)));
        Ok(())
    }

    #[tokio::test]
    async fn join_debate_session_should_reject_side_switch() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_topic_id, session_id) = seed_topic_and_session(&state, 1, "open", 10).await?;
        let user = state
            .find_user_by_id(1)
            .await?
            .expect("user id 1 should exist");

        state
            .join_debate_session(
                session_id as u64,
                &user,
                JoinDebateSessionInput {
                    side: "pro".to_string(),
                },
            )
            .await?;

        let err = state
            .join_debate_session(
                session_id as u64,
                &user,
                JoinDebateSessionInput {
                    side: "con".to_string(),
                },
            )
            .await
            .expect_err("side switch should fail");
        assert!(matches!(err, AppError::DebateConflict(_)));
        Ok(())
    }
}
