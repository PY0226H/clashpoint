use crate::{
    AppError, AppState, DebateMessagePinnedEvent, DebateParticipantJoinedEvent,
    DebateSessionStatusChangedEvent,
};
use chat_core::User;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::json;
use sqlx::{FromRow, Postgres, Transaction};
use tracing::warn;
use utoipa::{IntoParams, ToSchema};

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
    pub ws_id: i64,
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
    pub ws_id: i64,
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
    ws_id: i64,
    status: String,
    end_at: DateTime<Utc>,
    max_participants_per_side: i32,
    pro_count: i32,
    con_count: i32,
}

#[derive(Debug, FromRow)]
struct DebateSessionForAction {
    ws_id: i64,
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
    ws_id: i64,
    session_id: i64,
    user_id: i64,
}

#[derive(Debug, FromRow)]
struct ExistingPinByIdempotency {
    ledger_id: i64,
    balance_after: i64,
    ws_id: i64,
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

fn default_true() -> bool {
    true
}

fn normalize_limit(limit: Option<u64>) -> i64 {
    let limit = limit.unwrap_or(DEFAULT_LIMIT).clamp(1, MAX_LIMIT);
    limit as i64
}

fn normalize_debate_message_limit(limit: Option<u64>) -> i64 {
    let limit = limit
        .unwrap_or(DEBATE_MESSAGE_DEFAULT_LIMIT)
        .clamp(1, DEBATE_MESSAGE_MAX_LIMIT);
    limit as i64
}

fn normalize_debate_pin_limit(limit: Option<u64>) -> i64 {
    let limit = limit
        .unwrap_or(DEBATE_PIN_DEFAULT_LIMIT)
        .clamp(1, DEBATE_PIN_MAX_LIMIT);
    limit as i64
}

fn valid_join_side(side: &str) -> bool {
    matches!(side, "pro" | "con")
}

fn can_join_status(status: &str) -> bool {
    matches!(status, "open" | "running")
}

fn normalize_ops_topic_field(value: &str, field: &str, max_len: usize) -> Result<String, AppError> {
    let text = value.trim();
    if text.is_empty() {
        return Err(AppError::DebateError(format!("{field} cannot be empty")));
    }
    if text.len() > max_len {
        return Err(AppError::DebateError(format!(
            "{field} is too long, max {max_len}"
        )));
    }
    Ok(text.to_string())
}

fn normalize_ops_session_status(status: Option<String>) -> Result<String, AppError> {
    let status = status
        .unwrap_or_else(|| "scheduled".to_string())
        .trim()
        .to_lowercase();
    if matches!(status.as_str(), "scheduled" | "open") {
        return Ok(status);
    }
    Err(AppError::DebateError(
        "status must be `scheduled` or `open`".to_string(),
    ))
}

fn normalize_ops_manage_session_status(status: Option<String>) -> Result<Option<String>, AppError> {
    let Some(status) = status else {
        return Ok(None);
    };
    let status = status.trim().to_lowercase();
    if matches!(
        status.as_str(),
        "scheduled" | "open" | "running" | "judging" | "closed" | "canceled"
    ) {
        return Ok(Some(status));
    }
    Err(AppError::DebateError(
        "status must be one of `scheduled|open|running|judging|closed|canceled`".to_string(),
    ))
}

fn normalize_message_content(content: &str) -> Result<String, AppError> {
    let content = content.trim();
    if content.is_empty() {
        return Err(AppError::DebateError(
            "message content cannot be empty".to_string(),
        ));
    }
    if content.len() > DEBATE_MESSAGE_MAX_LEN {
        return Err(AppError::DebateError(format!(
            "message content too long, max {} chars",
            DEBATE_MESSAGE_MAX_LEN
        )));
    }
    Ok(content.to_string())
}

fn normalize_pin_seconds(pin_seconds: i32) -> Result<i32, AppError> {
    if !(PIN_MIN_SECONDS..=PIN_MAX_SECONDS).contains(&pin_seconds) {
        return Err(AppError::PaymentError(format!(
            "pin_seconds must be between {} and {}",
            PIN_MIN_SECONDS, PIN_MAX_SECONDS
        )));
    }
    Ok(pin_seconds)
}

fn pin_cost_coins(pin_seconds: i32) -> i64 {
    let units = (pin_seconds + PIN_BILLING_UNIT_SECONDS - 1) / PIN_BILLING_UNIT_SECONDS;
    units as i64 * PIN_COST_PER_UNIT_COINS
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
                ((status IN ('open', 'running')) AND end_at > NOW()) AS joinable
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
                ((status IN ('open', 'running')) AND end_at > NOW()) AS joinable
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

        if let Err(err) = self
            .event_bus
            .publish_debate_participant_joined(DebateParticipantJoinedEvent {
                ws_id: user.ws_id as u64,
                session_id,
                user_id: user.id as u64,
                side: input.side.clone(),
                pro_count,
                con_count,
            })
            .await
        {
            warn!(
                session_id,
                user_id = user.id,
                "publish kafka debate participant joined failed: {}",
                err
            );
        }

        Ok(JoinDebateSessionOutput {
            session_id,
            side: input.side,
            newly_joined: true,
            pro_count,
            con_count,
        })
    }

    pub async fn create_debate_message(
        &self,
        session_id: u64,
        user: &User,
        input: CreateDebateMessageInput,
    ) -> Result<DebateMessage, AppError> {
        let content = normalize_message_content(&input.content)?;
        let mut tx = self.pool.begin().await?;

        let session = self
            .load_session_for_action(&mut tx, session_id as i64)
            .await?
            .ok_or_else(|| AppError::NotFound(format!("debate session id {session_id}")))?;
        if session.ws_id != user.ws_id {
            return Err(AppError::NotFound(format!(
                "debate session id {session_id}"
            )));
        }
        if !can_join_status(&session.status) || session.end_at <= Utc::now() {
            return Err(AppError::DebateConflict(format!(
                "session {} is not accepting messages now",
                session_id
            )));
        }

        let participant_side: Option<(String,)> = sqlx::query_as(
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
        let Some((side,)) = participant_side else {
            return Err(AppError::DebateConflict(format!(
                "user {} has not joined session {}",
                user.id, session_id
            )));
        };

        let msg: DebateMessage = sqlx::query_as(
            r#"
            INSERT INTO session_messages(ws_id, session_id, user_id, side, content)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, ws_id, session_id, user_id, side, content, created_at
            "#,
        )
        .bind(user.ws_id)
        .bind(session_id as i64)
        .bind(user.id)
        .bind(side)
        .bind(content)
        .fetch_one(&mut *tx)
        .await?;

        sqlx::query(
            r#"
            UPDATE debate_sessions
            SET hot_score = hot_score + 1, updated_at = NOW()
            WHERE id = $1
            "#,
        )
        .bind(session_id as i64)
        .execute(&mut *tx)
        .await?;

        tx.commit().await?;
        Ok(msg)
    }

    pub async fn list_debate_messages(
        &self,
        session_id: u64,
        user: &User,
        input: ListDebateMessages,
    ) -> Result<Vec<DebateMessage>, AppError> {
        let mut tx = self.pool.begin().await?;
        let session = self
            .load_session_for_action(&mut tx, session_id as i64)
            .await?
            .ok_or_else(|| AppError::NotFound(format!("debate session id {session_id}")))?;
        if session.ws_id != user.ws_id {
            return Err(AppError::NotFound(format!(
                "debate session id {session_id}"
            )));
        }

        let participant: Option<(i64,)> = sqlx::query_as(
            r#"
            SELECT user_id
            FROM session_participants
            WHERE session_id = $1 AND user_id = $2
            "#,
        )
        .bind(session_id as i64)
        .bind(user.id)
        .fetch_optional(&mut *tx)
        .await?;
        if participant.is_none() {
            return Err(AppError::DebateConflict(format!(
                "user {} has not joined session {}",
                user.id, session_id
            )));
        }

        let mut rows: Vec<DebateMessage> = sqlx::query_as(
            r#"
            SELECT id, ws_id, session_id, user_id, side, content, created_at
            FROM session_messages
            WHERE session_id = $1
              AND ($2::bigint IS NULL OR id < $2)
            ORDER BY id DESC
            LIMIT $3
            "#,
        )
        .bind(session_id as i64)
        .bind(input.last_id.map(|v| v as i64))
        .bind(normalize_debate_message_limit(input.limit))
        .fetch_all(&mut *tx)
        .await?;

        tx.commit().await?;
        rows.reverse();
        Ok(rows)
    }

    pub async fn list_debate_pinned_messages(
        &self,
        session_id: u64,
        user: &User,
        input: ListDebatePinnedMessages,
    ) -> Result<Vec<DebatePinnedMessage>, AppError> {
        let mut tx = self.pool.begin().await?;
        let session = self
            .load_session_for_action(&mut tx, session_id as i64)
            .await?
            .ok_or_else(|| AppError::NotFound(format!("debate session id {session_id}")))?;
        if session.ws_id != user.ws_id {
            return Err(AppError::NotFound(format!(
                "debate session id {session_id}"
            )));
        }

        let participant: Option<(i64,)> = sqlx::query_as(
            r#"
            SELECT user_id
            FROM session_participants
            WHERE session_id = $1 AND user_id = $2
            "#,
        )
        .bind(session_id as i64)
        .bind(user.id)
        .fetch_optional(&mut *tx)
        .await?;
        if participant.is_none() {
            return Err(AppError::DebateConflict(format!(
                "user {} has not joined session {}",
                user.id, session_id
            )));
        }

        let rows: Vec<DebatePinnedMessage> = sqlx::query_as(
            r#"
            SELECT
                p.id,
                p.ws_id,
                p.session_id,
                p.message_id,
                p.user_id,
                m.side,
                m.content,
                p.cost_coins,
                p.pin_seconds,
                p.pinned_at,
                p.expires_at,
                p.status
            FROM session_pinned_messages p
            INNER JOIN session_messages m ON m.id = p.message_id
            WHERE p.session_id = $1
              AND (NOT $2::boolean OR (p.status = 'active' AND p.expires_at > NOW()))
            ORDER BY p.pinned_at DESC
            LIMIT $3
            "#,
        )
        .bind(session_id as i64)
        .bind(input.active_only)
        .bind(normalize_debate_pin_limit(input.limit))
        .fetch_all(&mut *tx)
        .await?;

        tx.commit().await?;
        Ok(rows)
    }

    pub async fn pin_debate_message(
        &self,
        message_id: u64,
        user: &User,
        input: PinDebateMessageInput,
    ) -> Result<PinDebateMessageOutput, AppError> {
        let pin_seconds = normalize_pin_seconds(input.pin_seconds)?;
        let idempotency_key = input.idempotency_key.trim().to_string();
        if idempotency_key.is_empty() {
            return Err(AppError::PaymentError(
                "idempotency_key cannot be empty".to_string(),
            ));
        }
        if idempotency_key.len() > 160 {
            return Err(AppError::PaymentError(
                "idempotency_key too long, max 160".to_string(),
            ));
        }

        let mut tx = self.pool.begin().await?;
        let existing_pin = self
            .load_existing_pin_by_idempotency(&mut tx, user, &idempotency_key)
            .await?;
        if let Some(pin) = existing_pin {
            tx.commit().await?;
            return Ok(pin);
        }

        let msg = sqlx::query_as::<_, DebateMessageForPin>(
            r#"
            SELECT id, ws_id, session_id, user_id
            FROM session_messages
            WHERE id = $1
            "#,
        )
        .bind(message_id as i64)
        .fetch_optional(&mut *tx)
        .await?
        .ok_or_else(|| AppError::NotFound(format!("debate message id {message_id}")))?;
        if msg.ws_id != user.ws_id {
            return Err(AppError::NotFound(format!(
                "debate message id {message_id}"
            )));
        }
        if msg.user_id != user.id {
            return Err(AppError::DebateConflict(format!(
                "only message sender can pin message {}",
                message_id
            )));
        }

        let session = self
            .load_session_for_action(&mut tx, msg.session_id)
            .await?
            .ok_or_else(|| AppError::NotFound(format!("debate session id {}", msg.session_id)))?;
        if !can_join_status(&session.status) || session.end_at <= Utc::now() {
            return Err(AppError::DebateConflict(format!(
                "session {} is not accepting pin now",
                msg.session_id
            )));
        }

        let active_pin: Option<(i64,)> = sqlx::query_as(
            r#"
            SELECT id
            FROM session_pinned_messages
            WHERE message_id = $1
              AND status = 'active'
              AND expires_at > NOW()
            LIMIT 1
            "#,
        )
        .bind(msg.id)
        .fetch_optional(&mut *tx)
        .await?;
        if active_pin.is_some() {
            return Err(AppError::DebateConflict(format!(
                "message {} already has an active pin",
                msg.id
            )));
        }

        let cost_coins = pin_cost_coins(pin_seconds);
        let now = Utc::now();
        let expires_at = now + chrono::Duration::seconds(pin_seconds as i64);

        sqlx::query(
            r#"
            INSERT INTO user_wallets(ws_id, user_id, balance)
            VALUES ($1, $2, 0)
            ON CONFLICT (ws_id, user_id) DO NOTHING
            "#,
        )
        .bind(user.ws_id)
        .bind(user.id)
        .execute(&mut *tx)
        .await?;

        let current_balance: (i64,) = sqlx::query_as(
            r#"
            SELECT balance
            FROM user_wallets
            WHERE ws_id = $1 AND user_id = $2
            FOR UPDATE
            "#,
        )
        .bind(user.ws_id)
        .bind(user.id)
        .fetch_one(&mut *tx)
        .await?;
        if current_balance.0 < cost_coins {
            return Err(AppError::PaymentConflict(format!(
                "insufficient balance, need {}, current {}",
                cost_coins, current_balance.0
            )));
        }
        let next_balance = current_balance.0 - cost_coins;

        sqlx::query(
            r#"
            UPDATE user_wallets
            SET balance = $3, updated_at = NOW()
            WHERE ws_id = $1 AND user_id = $2
            "#,
        )
        .bind(user.ws_id)
        .bind(user.id)
        .bind(next_balance)
        .execute(&mut *tx)
        .await?;

        let metadata = json!({
            "sessionId": msg.session_id,
            "messageId": msg.id,
            "pinSeconds": pin_seconds,
        });
        let ledger_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO wallet_ledger(
                ws_id, user_id, entry_type, amount_delta, balance_after, idempotency_key, metadata
            )
            VALUES ($1, $2, 'pin_debit', $3, $4, $5, $6)
            RETURNING id
            "#,
        )
        .bind(user.ws_id)
        .bind(user.id)
        .bind(-cost_coins)
        .bind(next_balance)
        .bind(&idempotency_key)
        .bind(metadata)
        .fetch_one(&mut *tx)
        .await?;

        let pin: PinRecord = sqlx::query_as(
            r#"
            INSERT INTO session_pinned_messages(
                ws_id, session_id, message_id, user_id, ledger_id,
                cost_coins, pin_seconds, pinned_at, expires_at, status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'active')
            RETURNING id, session_id, message_id, pin_seconds, expires_at, cost_coins
            "#,
        )
        .bind(user.ws_id)
        .bind(msg.session_id)
        .bind(msg.id)
        .bind(user.id)
        .bind(ledger_id.0)
        .bind(cost_coins)
        .bind(pin_seconds)
        .bind(now)
        .bind(expires_at)
        .fetch_one(&mut *tx)
        .await?;

        sqlx::query(
            r#"
            UPDATE debate_sessions
            SET hot_score = hot_score + $2::integer, updated_at = NOW()
            WHERE id = $1
            "#,
        )
        .bind(msg.session_id)
        .bind((cost_coins.min(i32::MAX as i64)) as i32)
        .execute(&mut *tx)
        .await?;

        tx.commit().await?;

        if let Err(err) = self
            .event_bus
            .publish_debate_message_pinned(DebateMessagePinnedEvent {
                ws_id: user.ws_id as u64,
                session_id: pin.session_id as u64,
                message_id: pin.message_id as u64,
                user_id: user.id as u64,
                ledger_id: ledger_id.0 as u64,
                cost_coins: pin.cost_coins,
                pin_seconds: pin.pin_seconds,
                pinned_at: now,
                expires_at: pin.expires_at,
            })
            .await
        {
            warn!(
                message_id,
                user_id = user.id,
                "publish kafka debate message pinned failed: {}",
                err
            );
        }

        Ok(PinDebateMessageOutput {
            pin_id: pin.id as u64,
            session_id: pin.session_id as u64,
            message_id: pin.message_id as u64,
            ledger_id: ledger_id.0 as u64,
            debited_coins: pin.cost_coins,
            wallet_balance: next_balance,
            pin_seconds: pin.pin_seconds,
            expires_at: pin.expires_at,
            newly_pinned: true,
        })
    }

    async fn load_session_for_action(
        &self,
        tx: &mut Transaction<'_, Postgres>,
        session_id: i64,
    ) -> Result<Option<DebateSessionForAction>, AppError> {
        let row = sqlx::query_as(
            r#"
            SELECT ws_id, status, end_at
            FROM debate_sessions
            WHERE id = $1
            "#,
        )
        .bind(session_id)
        .fetch_optional(&mut **tx)
        .await?;
        Ok(row)
    }

    async fn load_existing_pin_by_idempotency(
        &self,
        tx: &mut Transaction<'_, Postgres>,
        user: &User,
        idempotency_key: &str,
    ) -> Result<Option<PinDebateMessageOutput>, AppError> {
        let row: Option<ExistingPinByIdempotency> = sqlx::query_as(
            r#"
            SELECT id AS ledger_id, balance_after, ws_id, user_id
            FROM wallet_ledger
            WHERE idempotency_key = $1
              AND entry_type = 'pin_debit'
            "#,
        )
        .bind(idempotency_key)
        .fetch_optional(&mut **tx)
        .await?;
        let Some(row) = row else {
            return Ok(None);
        };
        if row.ws_id != user.ws_id || row.user_id != user.id {
            return Err(AppError::PaymentConflict(
                "idempotency_key already used by another user".to_string(),
            ));
        }

        let pin: Option<PinRecord> = sqlx::query_as(
            r#"
            SELECT id, session_id, message_id, pin_seconds, expires_at, cost_coins
            FROM session_pinned_messages
            WHERE ledger_id = $1
            "#,
        )
        .bind(row.ledger_id)
        .fetch_optional(&mut **tx)
        .await?;
        let Some(pin) = pin else {
            return Err(AppError::PaymentConflict(
                "idempotency_key already used for non-pin ledger entry".to_string(),
            ));
        };

        Ok(Some(PinDebateMessageOutput {
            pin_id: pin.id as u64,
            session_id: pin.session_id as u64,
            message_id: pin.message_id as u64,
            ledger_id: row.ledger_id as u64,
            debited_coins: pin.cost_coins,
            wallet_balance: row.balance_after,
            pin_seconds: pin.pin_seconds,
            expires_at: pin.expires_at,
            newly_pinned: false,
        }))
    }

    pub async fn advance_debate_sessions(
        &self,
        batch_size: i64,
    ) -> Result<DebateSessionAdvanceReport, AppError> {
        let now = Utc::now();
        let close_before = now - chrono::Duration::seconds(JUDGING_CLOSE_GRACE_SECONDS);
        let batch_size = batch_size.max(1);

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
        .fetch_all(&self.pool)
        .await?;
        self.publish_status_changed_batch("scheduled", "open", &opened_ids, now)
            .await;

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
        .fetch_all(&self.pool)
        .await?;
        self.publish_status_changed_batch("open", "running", &running_ids, now)
            .await;

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
        .fetch_all(&self.pool)
        .await?;
        self.publish_status_changed_batch("running", "judging", &judging_ids, now)
            .await;

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
        .fetch_all(&self.pool)
        .await?;
        self.publish_status_changed_batch("judging", "closed", &closed_ids, now)
            .await;

        Ok(DebateSessionAdvanceReport {
            opened: opened_ids.len(),
            running: running_ids.len(),
            judging: judging_ids.len(),
            closed: closed_ids.len(),
        })
    }

    async fn publish_status_changed_batch(
        &self,
        from_status: &str,
        to_status: &str,
        session_ids: &[(i64,)],
        changed_at: DateTime<Utc>,
    ) {
        for (session_id,) in session_ids.iter() {
            if let Err(err) = self
                .event_bus
                .publish_debate_session_status_changed(DebateSessionStatusChangedEvent {
                    session_id: *session_id as u64,
                    from_status: from_status.to_string(),
                    to_status: to_status.to_string(),
                    changed_at,
                })
                .await
            {
                warn!(
                    session_id,
                    from_status,
                    to_status,
                    "publish kafka debate session status changed failed: {}",
                    err
                );
            }
        }
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

    async fn session_status(state: &AppState, session_id: i64) -> Result<String> {
        let row: (String,) = sqlx::query_as("SELECT status FROM debate_sessions WHERE id = $1")
            .bind(session_id)
            .fetch_one(&state.pool)
            .await?;
        Ok(row.0)
    }

    async fn set_wallet_balance(
        state: &AppState,
        ws_id: i64,
        user_id: i64,
        balance: i64,
    ) -> Result<()> {
        sqlx::query(
            r#"
            INSERT INTO user_wallets(ws_id, user_id, balance)
            VALUES ($1, $2, $3)
            ON CONFLICT (ws_id, user_id)
            DO UPDATE SET balance = EXCLUDED.balance, updated_at = NOW()
            "#,
        )
        .bind(ws_id)
        .bind(user_id)
        .bind(balance)
        .execute(&state.pool)
        .await?;
        Ok(())
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
    async fn create_debate_topic_by_owner_should_work_and_reject_non_owner() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.update_workspace_owner(1, 1).await?;
        let owner = state
            .find_user_by_id(1)
            .await?
            .expect("owner user should exist");
        let non_owner = state
            .find_user_by_id(2)
            .await?
            .expect("non owner user should exist");

        let topic = state
            .create_debate_topic_by_owner(
                &owner,
                OpsCreateDebateTopicInput {
                    title: "运营辩题".to_string(),
                    description: "用于运营排期".to_string(),
                    category: "game".to_string(),
                    stance_pro: "支持".to_string(),
                    stance_con: "反对".to_string(),
                    context_seed: Some("种子背景".to_string()),
                    is_active: true,
                },
            )
            .await?;
        assert_eq!(topic.ws_id, owner.ws_id);
        assert_eq!(topic.created_by, owner.id);

        let err = state
            .create_debate_topic_by_owner(
                &non_owner,
                OpsCreateDebateTopicInput {
                    title: "越权辩题".to_string(),
                    description: "not allowed".to_string(),
                    category: "game".to_string(),
                    stance_pro: "pro".to_string(),
                    stance_con: "con".to_string(),
                    context_seed: None,
                    is_active: true,
                },
            )
            .await
            .expect_err("non owner should be rejected");
        assert!(matches!(err, AppError::DebateConflict(_)));
        Ok(())
    }

    #[tokio::test]
    async fn create_debate_session_by_owner_should_validate_status_and_topic() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.update_workspace_owner(1, 1).await?;
        let owner = state
            .find_user_by_id(1)
            .await?
            .expect("owner user should exist");
        let (topic_id, _) = seed_topic_and_session(&state, 1, "scheduled", 50).await?;

        let now = Utc::now();
        let session = state
            .create_debate_session_by_owner(
                &owner,
                OpsCreateDebateSessionInput {
                    topic_id: topic_id as u64,
                    status: Some("open".to_string()),
                    scheduled_start_at: now,
                    end_at: now + Duration::minutes(20),
                    max_participants_per_side: Some(200),
                },
            )
            .await?;
        assert_eq!(session.ws_id, owner.ws_id);
        assert_eq!(session.topic_id, topic_id);
        assert_eq!(session.status, "open");
        assert!(session.joinable);

        let invalid_status_err = state
            .create_debate_session_by_owner(
                &owner,
                OpsCreateDebateSessionInput {
                    topic_id: topic_id as u64,
                    status: Some("judging".to_string()),
                    scheduled_start_at: now,
                    end_at: now + Duration::minutes(20),
                    max_participants_per_side: Some(200),
                },
            )
            .await
            .expect_err("invalid status should fail");
        assert!(matches!(invalid_status_err, AppError::DebateError(_)));

        let not_found_err = state
            .create_debate_session_by_owner(
                &owner,
                OpsCreateDebateSessionInput {
                    topic_id: 999_999,
                    status: Some("scheduled".to_string()),
                    scheduled_start_at: now,
                    end_at: now + Duration::minutes(20),
                    max_participants_per_side: Some(200),
                },
            )
            .await
            .expect_err("missing topic should fail");
        assert!(matches!(not_found_err, AppError::NotFound(_)));
        Ok(())
    }

    #[tokio::test]
    async fn update_debate_topic_by_owner_should_update_and_reject_non_owner() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.update_workspace_owner(1, 1).await?;
        let owner = state
            .find_user_by_id(1)
            .await?
            .expect("owner user should exist");
        let non_owner = state
            .find_user_by_id(2)
            .await?
            .expect("non owner user should exist");

        let created = state
            .create_debate_topic_by_owner(
                &owner,
                OpsCreateDebateTopicInput {
                    title: "old".to_string(),
                    description: "old desc".to_string(),
                    category: "game".to_string(),
                    stance_pro: "支持".to_string(),
                    stance_con: "反对".to_string(),
                    context_seed: None,
                    is_active: true,
                },
            )
            .await?;

        let updated = state
            .update_debate_topic_by_owner(
                &owner,
                created.id as u64,
                OpsUpdateDebateTopicInput {
                    title: "new-title".to_string(),
                    description: "new desc".to_string(),
                    category: "sports".to_string(),
                    stance_pro: "赞成".to_string(),
                    stance_con: "否定".to_string(),
                    context_seed: Some("ctx".to_string()),
                    is_active: false,
                },
            )
            .await?;
        assert_eq!(updated.title, "new-title");
        assert_eq!(updated.category, "sports");
        assert!(!updated.is_active);
        assert_eq!(updated.context_seed.as_deref(), Some("ctx"));

        let err = state
            .update_debate_topic_by_owner(
                &non_owner,
                created.id as u64,
                OpsUpdateDebateTopicInput {
                    title: "hack".to_string(),
                    description: "hack".to_string(),
                    category: "game".to_string(),
                    stance_pro: "p".to_string(),
                    stance_con: "c".to_string(),
                    context_seed: None,
                    is_active: true,
                },
            )
            .await
            .expect_err("non owner should be rejected");
        assert!(matches!(err, AppError::DebateConflict(_)));
        Ok(())
    }

    #[tokio::test]
    async fn update_debate_session_by_owner_should_validate_and_update() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.update_workspace_owner(1, 1).await?;
        let owner = state
            .find_user_by_id(1)
            .await?
            .expect("owner user should exist");

        let (topic_id, session_id) = seed_topic_and_session(&state, 1, "scheduled", 5).await?;
        for user_id in [1_i64, 2_i64] {
            sqlx::query(
                "INSERT INTO session_participants(session_id, user_id, side) VALUES ($1, $2, 'pro')",
            )
            .bind(session_id)
            .bind(user_id)
            .execute(&state.pool)
            .await?;
        }
        sqlx::query("UPDATE debate_sessions SET pro_count = 2 WHERE id = $1")
            .bind(session_id)
            .execute(&state.pool)
            .await?;

        let now = Utc::now();
        let updated = state
            .update_debate_session_by_owner(
                &owner,
                session_id as u64,
                OpsUpdateDebateSessionInput {
                    status: Some("open".to_string()),
                    scheduled_start_at: Some(now - Duration::minutes(2)),
                    end_at: Some(now + Duration::minutes(30)),
                    max_participants_per_side: Some(10),
                },
            )
            .await?;
        assert_eq!(updated.status, "open");
        assert_eq!(updated.topic_id, topic_id);
        assert_eq!(updated.max_participants_per_side, 10);

        let too_small_err = state
            .update_debate_session_by_owner(
                &owner,
                session_id as u64,
                OpsUpdateDebateSessionInput {
                    status: None,
                    scheduled_start_at: None,
                    end_at: None,
                    max_participants_per_side: Some(1),
                },
            )
            .await
            .expect_err("max below current should fail");
        assert!(matches!(too_small_err, AppError::DebateConflict(_)));

        let invalid_status_err = state
            .update_debate_session_by_owner(
                &owner,
                session_id as u64,
                OpsUpdateDebateSessionInput {
                    status: Some("invalid".to_string()),
                    scheduled_start_at: None,
                    end_at: None,
                    max_participants_per_side: None,
                },
            )
            .await
            .expect_err("invalid status should fail");
        assert!(matches!(invalid_status_err, AppError::DebateError(_)));
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

    #[tokio::test]
    async fn create_debate_message_should_require_join_and_write_side() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_topic_id, session_id) = seed_topic_and_session(&state, 1, "open", 10).await?;
        let user = state
            .find_user_by_id(1)
            .await?
            .expect("user id 1 should exist");

        let err = state
            .create_debate_message(
                session_id as u64,
                &user,
                CreateDebateMessageInput {
                    content: "hello".to_string(),
                },
            )
            .await
            .expect_err("not joined should fail");
        assert!(matches!(err, AppError::DebateConflict(_)));

        state
            .join_debate_session(
                session_id as u64,
                &user,
                JoinDebateSessionInput {
                    side: "pro".to_string(),
                },
            )
            .await?;

        let msg = state
            .create_debate_message(
                session_id as u64,
                &user,
                CreateDebateMessageInput {
                    content: "pro says hi".to_string(),
                },
            )
            .await?;
        assert_eq!(msg.session_id, session_id);
        assert_eq!(msg.side, "pro");
        assert_eq!(msg.user_id, 1);
        Ok(())
    }

    #[tokio::test]
    async fn pin_debate_message_should_debit_wallet_and_be_idempotent() -> Result<()> {
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
        set_wallet_balance(&state, 1, 1, 200).await?;
        let msg = state
            .create_debate_message(
                session_id as u64,
                &user,
                CreateDebateMessageInput {
                    content: "pin this message".to_string(),
                },
            )
            .await?;

        let first = state
            .pin_debate_message(
                msg.id as u64,
                &user,
                PinDebateMessageInput {
                    pin_seconds: 45,
                    idempotency_key: "pin-key-1".to_string(),
                },
            )
            .await?;
        assert!(first.newly_pinned);
        assert_eq!(first.debited_coins, 20);
        assert_eq!(first.wallet_balance, 180);

        let second = state
            .pin_debate_message(
                msg.id as u64,
                &user,
                PinDebateMessageInput {
                    pin_seconds: 45,
                    idempotency_key: "pin-key-1".to_string(),
                },
            )
            .await?;
        assert!(!second.newly_pinned);
        assert_eq!(second.pin_id, first.pin_id);
        assert_eq!(second.wallet_balance, 180);

        let row: (i64,) = sqlx::query_as(
            r#"
            SELECT balance
            FROM user_wallets
            WHERE ws_id = 1 AND user_id = 1
            "#,
        )
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(row.0, 180);
        Ok(())
    }

    #[tokio::test]
    async fn pin_debate_message_should_reject_insufficient_balance_and_non_owner() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_topic_id, session_id) = seed_topic_and_session(&state, 1, "open", 10).await?;
        let user1 = state
            .find_user_by_id(1)
            .await?
            .expect("user id 1 should exist");
        let user2 = state
            .find_user_by_id(2)
            .await?
            .expect("user id 2 should exist");

        state
            .join_debate_session(
                session_id as u64,
                &user1,
                JoinDebateSessionInput {
                    side: "pro".to_string(),
                },
            )
            .await?;
        state
            .join_debate_session(
                session_id as u64,
                &user2,
                JoinDebateSessionInput {
                    side: "con".to_string(),
                },
            )
            .await?;

        let msg = state
            .create_debate_message(
                session_id as u64,
                &user1,
                CreateDebateMessageInput {
                    content: "owner message".to_string(),
                },
            )
            .await?;

        let non_owner_err = state
            .pin_debate_message(
                msg.id as u64,
                &user2,
                PinDebateMessageInput {
                    pin_seconds: 30,
                    idempotency_key: "pin-non-owner".to_string(),
                },
            )
            .await
            .expect_err("non owner pin should fail");
        assert!(matches!(non_owner_err, AppError::DebateConflict(_)));

        set_wallet_balance(&state, 1, 1, 5).await?;
        let no_balance_err = state
            .pin_debate_message(
                msg.id as u64,
                &user1,
                PinDebateMessageInput {
                    pin_seconds: 30,
                    idempotency_key: "pin-low-balance".to_string(),
                },
            )
            .await
            .expect_err("insufficient balance should fail");
        assert!(matches!(no_balance_err, AppError::PaymentConflict(_)));
        Ok(())
    }

    #[tokio::test]
    async fn advance_debate_sessions_should_open_due_scheduled_session() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_topic_id, session_id) = seed_topic_and_session(&state, 1, "scheduled", 10).await?;

        let report = state.advance_debate_sessions(100).await?;
        assert_eq!(report.opened, 1);
        assert_eq!(session_status(&state, session_id).await?, "open");
        Ok(())
    }

    #[tokio::test]
    async fn advance_debate_sessions_should_move_open_to_running_when_has_participants(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_topic_id, session_id) = seed_topic_and_session(&state, 1, "open", 10).await?;

        sqlx::query("UPDATE debate_sessions SET pro_count = 1 WHERE id = $1")
            .bind(session_id)
            .execute(&state.pool)
            .await?;

        let report = state.advance_debate_sessions(100).await?;
        assert_eq!(report.running, 1);
        assert_eq!(session_status(&state, session_id).await?, "running");
        Ok(())
    }

    #[tokio::test]
    async fn advance_debate_sessions_should_move_running_to_judging_then_closed() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let (_topic_id, session_id) = seed_topic_and_session(&state, 1, "running", 10).await?;

        sqlx::query(
            "UPDATE debate_sessions SET end_at = NOW() - INTERVAL '1 minute' WHERE id = $1",
        )
        .bind(session_id)
        .execute(&state.pool)
        .await?;

        let report = state.advance_debate_sessions(100).await?;
        assert_eq!(report.judging, 1);
        assert_eq!(session_status(&state, session_id).await?, "judging");

        sqlx::query(
            "UPDATE debate_sessions SET updated_at = NOW() - INTERVAL '45 second' WHERE id = $1",
        )
        .bind(session_id)
        .execute(&state.pool)
        .await?;

        let report = state.advance_debate_sessions(100).await?;
        assert_eq!(report.closed, 1);
        assert_eq!(session_status(&state, session_id).await?, "closed");
        Ok(())
    }

    #[test]
    fn normalize_debate_message_limit_should_clamp_range() {
        assert_eq!(
            normalize_debate_message_limit(None),
            DEBATE_MESSAGE_DEFAULT_LIMIT as i64
        );
        assert_eq!(normalize_debate_message_limit(Some(0)), 1);
        assert_eq!(
            normalize_debate_message_limit(Some(999)),
            DEBATE_MESSAGE_MAX_LIMIT as i64
        );
    }

    #[test]
    fn normalize_debate_pin_limit_should_clamp_range() {
        assert_eq!(
            normalize_debate_pin_limit(None),
            DEBATE_PIN_DEFAULT_LIMIT as i64
        );
        assert_eq!(normalize_debate_pin_limit(Some(0)), 1);
        assert_eq!(
            normalize_debate_pin_limit(Some(999)),
            DEBATE_PIN_MAX_LIMIT as i64
        );
    }
}
