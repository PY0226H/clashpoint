use crate::{
    AppError, AppState, DebateMessageCreatedEvent, DebateMessagePinnedEvent,
    DebateParticipantJoinedEvent, DebateSessionStatusChangedEvent, DomainEvent, EventPublisher,
};
use chat_core::User;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::json;
use sqlx::{FromRow, Postgres, Transaction};
use tracing::warn;
use utoipa::{IntoParams, ToSchema};

mod helpers;
mod message_pin;
mod ops;
use helpers::{
    build_phase_trigger_idempotency_key, build_phase_trigger_trace_id, can_join_status,
    can_spectate_status, evaluate_phase_trigger_checkpoint, normalize_debate_message_limit,
    normalize_debate_pin_limit, normalize_limit, normalize_message_content,
    normalize_ops_manage_session_status, normalize_ops_session_status, normalize_ops_topic_field,
    normalize_pin_seconds, normalize_topic_category, normalize_topic_category_filter,
    pin_cost_coins, valid_join_side,
};

const DEFAULT_LIMIT: u64 = 20;
const MAX_LIMIT: u64 = 100;
const DEBATE_MESSAGE_DEFAULT_LIMIT: u64 = 80;
const DEBATE_MESSAGE_MAX_LIMIT: u64 = 200;
const DEBATE_PIN_DEFAULT_LIMIT: u64 = 20;
const DEBATE_PIN_MAX_LIMIT: u64 = 100;
const DEBATE_MESSAGE_MAX_LEN: usize = 1000;
const DEBATE_TOPIC_TITLE_MAX_LEN: usize = 120;
const DEBATE_TOPIC_CATEGORY_MAX_LEN: usize = 32;
const DEBATE_STANCE_MAX_LEN: usize = 64;
const DEBATE_SESSION_STATUS_MAX_LEN: usize = 20;
const PIN_MIN_SECONDS: i32 = 30;
const PIN_MAX_SECONDS: i32 = 600;
const PIN_BILLING_UNIT_SECONDS: i32 = 30;
const PIN_COST_PER_UNIT_COINS: i64 = 10;
const JUDGE_PHASE_WINDOW_SIZE: i64 = 100;
const JUDGE_PHASE_RUBRIC_VERSION: &str = "v3";
const JUDGE_PHASE_POLICY_VERSION: &str = "v3-default";
const DEBATE_TOPICS_EMPTY_REVISION: &str = "empty";

#[derive(Debug, Clone, FromRow, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DebateTopic {
    pub id: i64,
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
    pub cursor: Option<String>,
    pub limit: Option<u64>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListDebateTopicsOutput {
    pub items: Vec<DebateTopic>,
    pub has_more: bool,
    pub next_cursor: Option<String>,
    pub revision: String,
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
pub struct OpsCreateDebateTopicInput {
    pub title: String,
    pub description: String,
    pub category: String,
    pub stance_pro: String,
    pub stance_con: String,
    pub context_seed: Option<String>,
    #[serde(default = "default_true")]
    pub is_active: bool,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OpsCreateDebateSessionInput {
    pub topic_id: u64,
    pub status: Option<String>,
    pub scheduled_start_at: DateTime<Utc>,
    pub end_at: DateTime<Utc>,
    pub max_participants_per_side: Option<i32>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OpsUpdateDebateTopicInput {
    pub title: String,
    pub description: String,
    pub category: String,
    pub stance_pro: String,
    pub stance_con: String,
    pub context_seed: Option<String>,
    pub is_active: bool,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OpsUpdateDebateSessionInput {
    pub status: Option<String>,
    pub scheduled_start_at: Option<DateTime<Utc>>,
    pub end_at: Option<DateTime<Utc>>,
    pub max_participants_per_side: Option<i32>,
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

#[derive(Debug, Clone, FromRow, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DebateMessage {
    pub id: i64,
    pub session_id: i64,
    pub user_id: i64,
    pub side: String,
    pub content: String,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CreateDebateMessageInput {
    pub content: String,
}

#[derive(Debug, Clone, IntoParams, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListDebateMessages {
    pub last_id: Option<u64>,
    pub limit: Option<u64>,
}

#[derive(Debug, Clone, IntoParams, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListDebatePinnedMessages {
    #[serde(default = "default_true")]
    pub active_only: bool,
    pub limit: Option<u64>,
}

#[derive(Debug, Clone, FromRow, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DebatePinnedMessage {
    pub id: i64,
    pub session_id: i64,
    pub message_id: i64,
    pub user_id: i64,
    pub side: String,
    pub content: String,
    pub cost_coins: i64,
    pub pin_seconds: i32,
    pub pinned_at: DateTime<Utc>,
    pub expires_at: DateTime<Utc>,
    pub status: String,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PinDebateMessageInput {
    pub pin_seconds: i32,
    pub idempotency_key: String,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PinDebateMessageOutput {
    pub pin_id: u64,
    pub session_id: u64,
    pub message_id: u64,
    pub ledger_id: u64,
    pub debited_coins: i64,
    pub wallet_balance: i64,
    pub pin_seconds: i32,
    pub expires_at: DateTime<Utc>,
    pub newly_pinned: bool,
}

#[derive(Debug, FromRow)]
struct DebateSessionForJoin {
    status: String,
    scheduled_start_at: DateTime<Utc>,
    end_at: DateTime<Utc>,
    max_participants_per_side: i32,
    pro_count: i32,
    con_count: i32,
}

#[derive(Debug, FromRow)]
struct DebateSessionForAction {
    status: String,
    end_at: DateTime<Utc>,
}

#[derive(Debug, FromRow)]
struct DebateSessionForOpsUpdate {
    status: String,
    scheduled_start_at: DateTime<Utc>,
    end_at: DateTime<Utc>,
    max_participants_per_side: i32,
    pro_count: i32,
    con_count: i32,
}

#[derive(Debug, FromRow)]
struct DebateMessageForPin {
    id: i64,
    session_id: i64,
    user_id: i64,
}

#[derive(Debug, FromRow)]
struct ExistingPinByIdempotency {
    ledger_id: i64,
    balance_after: i64,
    user_id: i64,
}

#[derive(Debug, FromRow)]
struct PinRecord {
    id: i64,
    session_id: i64,
    message_id: i64,
    pin_seconds: i32,
    expires_at: DateTime<Utc>,
    cost_coins: i64,
}

#[derive(Debug, Clone)]
struct ListDebateTopicsCursor {
    created_at: DateTime<Utc>,
    id: i64,
}

fn default_true() -> bool {
    true
}

fn format_topics_cursor_timestamp(value: DateTime<Utc>) -> String {
    value.to_rfc3339_opts(chrono::SecondsFormat::Micros, true)
}

fn encode_list_debate_topics_cursor(value: DateTime<Utc>, id: i64) -> String {
    format!("{}|{}", format_topics_cursor_timestamp(value), id)
}

fn decode_list_debate_topics_cursor(raw: &str) -> Result<ListDebateTopicsCursor, AppError> {
    let trimmed = raw.trim();
    let Some((created_at_raw, id_raw)) = trimmed.split_once('|') else {
        return Err(AppError::ValidationError(
            "debate_topics_cursor_invalid".to_string(),
        ));
    };
    let created_at = DateTime::parse_from_rfc3339(created_at_raw.trim())
        .map(|ts| ts.with_timezone(&Utc))
        .map_err(|_| AppError::ValidationError("debate_topics_cursor_invalid".to_string()))?;
    let id = id_raw
        .trim()
        .parse::<i64>()
        .map_err(|_| AppError::ValidationError("debate_topics_cursor_invalid".to_string()))?;
    if id <= 0 {
        return Err(AppError::ValidationError(
            "debate_topics_cursor_invalid".to_string(),
        ));
    }
    Ok(ListDebateTopicsCursor { created_at, id })
}

const JUDGING_CLOSE_GRACE_SECONDS: i64 = 30;

#[derive(Debug, Default, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct DebateSessionAdvanceReport {
    pub opened: usize,
    pub running: usize,
    pub judging: usize,
    pub closed: usize,
}

#[allow(dead_code)]
impl AppState {
    pub async fn list_debate_topics(
        &self,
        input: ListDebateTopics,
    ) -> Result<ListDebateTopicsOutput, AppError> {
        let limit = normalize_limit(input.limit);
        let limit_plus_one = limit + 1;
        let category = normalize_topic_category_filter(input.category);
        let cursor = match input.cursor.as_deref().map(str::trim) {
            Some(raw) if !raw.is_empty() => Some(decode_list_debate_topics_cursor(raw)?),
            _ => None,
        };
        let mut rows: Vec<DebateTopic> = if let Some(cursor) = cursor.as_ref() {
            sqlx::query_as(
                r#"
                SELECT id, title, description, category, stance_pro, stance_con, context_seed, is_active, created_by, created_at, updated_at
                FROM debate_topics
                WHERE ($1::text IS NULL OR category = $1)
                  AND (NOT $2::boolean OR is_active = TRUE)
                  AND (created_at, id) < ($3, $4)
                ORDER BY created_at DESC, id DESC
                LIMIT $5
                "#,
            )
            .bind(&category)
            .bind(input.active_only)
            .bind(cursor.created_at)
            .bind(cursor.id)
            .bind(limit_plus_one)
            .fetch_all(&self.pool)
            .await?
        } else {
            sqlx::query_as(
                r#"
                SELECT id, title, description, category, stance_pro, stance_con, context_seed, is_active, created_by, created_at, updated_at
                FROM debate_topics
                WHERE ($1::text IS NULL OR category = $1)
                  AND (NOT $2::boolean OR is_active = TRUE)
                ORDER BY created_at DESC, id DESC
                LIMIT $3
                "#,
            )
            .bind(&category)
            .bind(input.active_only)
            .bind(limit_plus_one)
            .fetch_all(&self.pool)
            .await?
        };
        let has_more = (rows.len() as i64) > limit;
        if has_more {
            rows.truncate(limit as usize);
        }
        let next_cursor = if has_more {
            rows.last()
                .map(|last| encode_list_debate_topics_cursor(last.created_at, last.id))
        } else {
            None
        };
        let revision: Option<DateTime<Utc>> =
            sqlx::query_scalar("SELECT MAX(updated_at) FROM debate_topics")
                .fetch_one(&self.pool)
                .await?;
        Ok(ListDebateTopicsOutput {
            items: rows,
            has_more,
            next_cursor,
            revision: revision
                .map(format_topics_cursor_timestamp)
                .unwrap_or_else(|| DEBATE_TOPICS_EMPTY_REVISION.to_string()),
        })
    }

    pub async fn list_debate_sessions(
        &self,
        input: ListDebateSessions,
    ) -> Result<Vec<DebateSessionSummary>, AppError> {
        let limit = normalize_limit(input.limit);
        let rows = sqlx::query_as(
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
            WHERE ($1::text IS NULL OR status = $1)
              AND ($2::bigint IS NULL OR topic_id = $2)
              AND ($3::timestamptz IS NULL OR scheduled_start_at >= $3)
              AND ($4::timestamptz IS NULL OR scheduled_start_at <= $4)
            ORDER BY scheduled_start_at DESC
            LIMIT $5
            "#,
        )
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
            SELECT status, scheduled_start_at, end_at, max_participants_per_side, pro_count, con_count
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

        let now = Utc::now();
        if !can_join_status(&session.status)
            || session.scheduled_start_at > now
            || session.end_at <= now
        {
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

        self.event_bus
            .enqueue_in_tx(
                &mut tx,
                DomainEvent::DebateParticipantJoined(DebateParticipantJoinedEvent {
                    session_id,
                    user_id: user.id as u64,
                    side: input.side.clone(),
                    pro_count,
                    con_count,
                }),
            )
            .await?;
        tx.commit().await?;

        Ok(JoinDebateSessionOutput {
            session_id,
            side: input.side,
            newly_joined: true,
            pro_count,
            con_count,
        })
    }

    pub async fn advance_debate_sessions(
        &self,
        batch_size: i64,
    ) -> Result<DebateSessionAdvanceReport, AppError> {
        let now = Utc::now();
        let close_before = now - chrono::Duration::seconds(JUDGING_CLOSE_GRACE_SECONDS);
        let batch_size = batch_size.max(1);

        let mut opened_tx = self.pool.begin().await?;
        let opened_ids: Vec<(i64,)> = sqlx::query_as(
            r#"
            WITH due AS (
                SELECT id
                FROM debate_sessions
                WHERE status = 'scheduled'
                  AND scheduled_start_at <= $1
                ORDER BY scheduled_start_at ASC
                LIMIT $2
                FOR UPDATE SKIP LOCKED
            )
            UPDATE debate_sessions s
            SET status = 'open',
                actual_start_at = COALESCE(actual_start_at, $1),
                updated_at = NOW()
            FROM due
            WHERE s.id = due.id
            RETURNING s.id
            "#,
        )
        .bind(now)
        .bind(batch_size)
        .fetch_all(&mut *opened_tx)
        .await?;
        self.enqueue_status_changed_batch_in_tx(
            &mut opened_tx,
            "scheduled",
            "open",
            &opened_ids,
            now,
        )
        .await?;
        opened_tx.commit().await?;

        let mut running_tx = self.pool.begin().await?;
        let running_ids: Vec<(i64,)> = sqlx::query_as(
            r#"
            WITH due AS (
                SELECT id
                FROM debate_sessions
                WHERE status = 'open'
                  AND scheduled_start_at <= $1
                  AND end_at > $1
                  AND (pro_count + con_count) > 0
                ORDER BY scheduled_start_at ASC
                LIMIT $2
                FOR UPDATE SKIP LOCKED
            )
            UPDATE debate_sessions s
            SET status = 'running',
                actual_start_at = COALESCE(actual_start_at, $1),
                updated_at = NOW()
            FROM due
            WHERE s.id = due.id
            RETURNING s.id
            "#,
        )
        .bind(now)
        .bind(batch_size)
        .fetch_all(&mut *running_tx)
        .await?;
        self.enqueue_status_changed_batch_in_tx(
            &mut running_tx,
            "open",
            "running",
            &running_ids,
            now,
        )
        .await?;
        running_tx.commit().await?;

        let mut judging_tx = self.pool.begin().await?;
        let judging_ids: Vec<(i64,)> = sqlx::query_as(
            r#"
            WITH due AS (
                SELECT id
                FROM debate_sessions
                WHERE status = 'running'
                  AND end_at <= $1
                ORDER BY end_at ASC
                LIMIT $2
                FOR UPDATE SKIP LOCKED
            )
            UPDATE debate_sessions s
            SET status = 'judging',
                updated_at = NOW()
            FROM due
            WHERE s.id = due.id
            RETURNING s.id
            "#,
        )
        .bind(now)
        .bind(batch_size)
        .fetch_all(&mut *judging_tx)
        .await?;
        self.enqueue_status_changed_batch_in_tx(
            &mut judging_tx,
            "running",
            "judging",
            &judging_ids,
            now,
        )
        .await?;
        judging_tx.commit().await?;

        let mut closed_tx = self.pool.begin().await?;
        let closed_ids: Vec<(i64,)> = sqlx::query_as(
            r#"
            WITH due AS (
                SELECT id
                FROM debate_sessions
                WHERE status = 'judging'
                  AND updated_at <= $1
                ORDER BY updated_at ASC
                LIMIT $2
                FOR UPDATE SKIP LOCKED
            )
            UPDATE debate_sessions s
            SET status = 'closed',
                updated_at = NOW()
            FROM due
            WHERE s.id = due.id
            RETURNING s.id
            "#,
        )
        .bind(close_before)
        .bind(batch_size)
        .fetch_all(&mut *closed_tx)
        .await?;
        self.enqueue_status_changed_batch_in_tx(
            &mut closed_tx,
            "judging",
            "closed",
            &closed_ids,
            now,
        )
        .await?;
        closed_tx.commit().await?;
        if let Err(err) = self
            .auto_trigger_judge_jobs_for_recoverable_sessions(batch_size)
            .await
        {
            warn!("auto judge trigger reconcile query failed: {}", err);
        }

        Ok(DebateSessionAdvanceReport {
            opened: opened_ids.len(),
            running: running_ids.len(),
            judging: judging_ids.len(),
            closed: closed_ids.len(),
        })
    }

    async fn enqueue_status_changed_batch_in_tx(
        &self,
        tx: &mut Transaction<'_, Postgres>,
        from_status: &str,
        to_status: &str,
        session_ids: &[(i64,)],
        changed_at: DateTime<Utc>,
    ) -> Result<(), AppError> {
        for (session_id,) in session_ids.iter() {
            self.event_bus
                .enqueue_in_tx(
                    tx,
                    DomainEvent::DebateSessionStatusChanged(DebateSessionStatusChangedEvent {
                        session_id: *session_id as u64,
                        from_status: from_status.to_string(),
                        to_status: to_status.to_string(),
                        changed_at,
                    }),
                )
                .await?;
        }
        Ok(())
    }

    async fn auto_trigger_judge_jobs_for_sessions(&self, session_ids: &[(i64,)]) {
        for (session_id,) in session_ids.iter() {
            match self
                .request_judge_job_automatically(*session_id as u64)
                .await
            {
                Ok(Some(output)) => {
                    if output.queued_phase_jobs > 0 || output.queued_final_job {
                        continue;
                    }
                    // Existing v3 jobs/report already cover this session; treat as success and no-op.
                }
                Ok(None) => {
                    warn!(
                        session_id = *session_id,
                        "auto judge trigger skipped: no eligible requester"
                    );
                }
                Err(err) => {
                    warn!(
                        session_id = *session_id,
                        "auto judge trigger failed after session enter judging: {}", err
                    );
                }
            }
        }
    }

    async fn auto_trigger_judge_jobs_for_recoverable_sessions(
        &self,
        batch_size: i64,
    ) -> Result<(), AppError> {
        let recoverable_session_ids: Vec<(i64,)> = sqlx::query_as(
            r#"
            SELECT s.id
            FROM debate_sessions s
            WHERE s.status IN ('judging', 'closed')
              AND EXISTS(
                SELECT 1
                FROM users u
              )
              AND NOT EXISTS(
                SELECT 1
                FROM judge_final_reports r
                WHERE r.session_id = s.id
              )
              AND (
                NOT EXISTS(
                    SELECT 1
                    FROM judge_phase_jobs p
                    WHERE p.session_id = s.id
                )
                OR EXISTS(
                    SELECT 1
                    FROM judge_phase_jobs p
                    WHERE p.session_id = s.id
                      AND p.status = 'failed'
                )
                OR (
                    s.status = 'closed'
                    AND NOT EXISTS(
                        SELECT 1
                        FROM judge_final_jobs f
                        WHERE f.session_id = s.id
                    )
                )
                OR EXISTS(
                    SELECT 1
                    FROM judge_final_jobs f
                    WHERE f.session_id = s.id
                      AND f.status = 'failed'
                )
              )
            ORDER BY s.updated_at ASC
            LIMIT $1
            "#,
        )
        .bind(batch_size.max(1))
        .fetch_all(&self.pool)
        .await?;
        self.auto_trigger_judge_jobs_for_sessions(&recoverable_session_ids)
            .await;
        Ok(())
    }
}

#[cfg(test)]
mod tests;
