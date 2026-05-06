use super::*;
use crate::AppError;
use chat_core::User;
use chrono::{DateTime, Utc};
use reqwest::Client;
use serde_json::{json, Map, Value};
use sqlx::FromRow;
use std::time::Duration;
use uuid::Uuid;

pub(super) const DEBATE_ASSISTANT_AGENT_KIND: &str = "debate_assistant";
pub(super) const DEBATE_ASSISTANT_CONTRACT_VERSION: &str = "debate_assistant_contract_v1";
pub(super) const DEBATE_ASSISTANT_CONTEXT_VERSION: &str = "assistant_room_transcript_context_v1";
pub(super) const DEBATE_ASSISTANT_FEATURE_KEY: &str = "debate_assistant";
pub(super) const DEBATE_ASSISTANT_FORBIDDEN: &str = "debate_assistant_forbidden";
pub(super) const DEBATE_ASSISTANT_MEMBERSHIP_REQUIRED: &str =
    "debate_assistant_membership_required";
pub(super) const DEBATE_ASSISTANT_QUOTA_EXHAUSTED: &str = "debate_assistant_quota_exhausted";
pub(super) const DEBATE_ASSISTANT_PROXY_FAILED: &str = "debate_assistant_proxy_failed";
pub(super) const DEBATE_ASSISTANT_CONTRACT_VIOLATION: &str = "debate_assistant_contract_violation";
pub(super) const DEBATE_ASSISTANT_NOT_READY: &str = "debate_assistant_not_ready";

const DEFAULT_DEBATE_ASSISTANT_QUOTA_LIMIT: i32 = 20;
const DEBATE_ASSISTANT_CONTEXT_MESSAGE_LIMIT: i64 = 60;
const MAX_DEBATE_ASSISTANT_TRACE_ID_LEN: usize = 160;
const MAX_DEBATE_ASSISTANT_QUESTION_LEN: usize = 2_000;
const MAX_DEBATE_ASSISTANT_DRAFT_LEN: usize = 4_000;

const DEBATE_ASSISTANT_INTENTS: &[&str] = &[
    "room_summary",
    "opponent_summary",
    "unanswered_points",
    "speech_structure",
    "draft_polish",
];

#[derive(Debug)]
struct NormalizedDebateAssistantInput {
    intent: String,
    question: String,
    draft: Option<String>,
    trace_id: Option<String>,
    side: Option<String>,
    case_id: Option<u64>,
}

#[derive(Debug, FromRow)]
struct DebateAssistantSessionRow {
    session_id: i64,
    status: String,
    scheduled_start_at: DateTime<Utc>,
    actual_start_at: Option<DateTime<Utc>>,
    end_at: DateTime<Utc>,
    title: String,
    description: String,
    category: String,
    stance_pro: String,
    stance_con: String,
    viewer_side: Option<String>,
}

#[derive(Debug, FromRow)]
struct DebateAssistantEntitlementRow {
    status: String,
    starts_at: DateTime<Utc>,
    expires_at: Option<DateTime<Utc>>,
}

#[derive(Debug, FromRow)]
struct DebateAssistantUsageRow {
    used_count: i32,
    quota_limit: i32,
}

#[derive(Debug, FromRow)]
struct DebateAssistantMessageRow {
    message_id: i64,
    session_id: i64,
    user_id: i64,
    side: String,
    content: String,
    created_at: DateTime<Utc>,
}

struct DebateAssistantProxyParams<'a> {
    base_url: &'a str,
    path: &'a str,
    timeout_ms: u64,
    internal_key: &'a str,
    session_id: u64,
    trace_id: &'a str,
    intent: &'a str,
    question: &'a str,
    draft: Option<&'a str>,
    side: &'a str,
    case_id: Option<u64>,
    room_transcript_context: &'a Value,
}

impl AppState {
    pub async fn get_debate_assistant_status(
        &self,
        session_id: u64,
        user: &User,
    ) -> Result<DebateAssistantStatusOutput, AppError> {
        let session_id_i64 = i64::try_from(session_id).map_err(|_| {
            AppError::ValidationError("debate_assistant_invalid_session_id".to_string())
        })?;
        let session = load_debate_assistant_session(&self.pool, session_id_i64, user.id).await?;
        let Some(viewer_side) = session.viewer_side.clone() else {
            return Err(AppError::DebateConflict(
                DEBATE_ASSISTANT_FORBIDDEN.to_string(),
            ));
        };
        let membership = load_debate_assistant_membership_status(&self.pool, user.id).await?;
        let quota = load_debate_assistant_quota_status(&self.pool, user.id, session_id_i64).await?;

        Ok(DebateAssistantStatusOutput {
            session_id,
            agent_kind: DEBATE_ASSISTANT_AGENT_KIND.to_string(),
            available: membership.active && quota.remaining > 0,
            viewer_role: "participant".to_string(),
            viewer_side: Some(viewer_side),
            membership,
            quota,
            intents: DEBATE_ASSISTANT_INTENTS
                .iter()
                .map(|value| (*value).to_string())
                .collect(),
            boundary_notice: debate_assistant_boundary_notice(),
        })
    }

    pub async fn request_debate_assistant_query(
        &self,
        session_id: u64,
        user: &User,
        input: RequestDebateAssistantQueryInput,
    ) -> Result<DebateAssistantOutput, AppError> {
        let normalized = normalize_debate_assistant_input(input)?;
        let session_id_i64 = i64::try_from(session_id).map_err(|_| {
            AppError::ValidationError("debate_assistant_invalid_session_id".to_string())
        })?;
        let session = load_debate_assistant_session(&self.pool, session_id_i64, user.id).await?;
        let Some(viewer_side) = session.viewer_side.clone() else {
            return Err(AppError::DebateConflict(
                DEBATE_ASSISTANT_FORBIDDEN.to_string(),
            ));
        };
        let effective_side = normalized.side.clone().unwrap_or(viewer_side);

        let membership = load_debate_assistant_membership_status(&self.pool, user.id).await?;
        if !membership.active {
            return Err(AppError::DebateConflict(
                DEBATE_ASSISTANT_MEMBERSHIP_REQUIRED.to_string(),
            ));
        }

        let quota = load_debate_assistant_quota_status(&self.pool, user.id, session_id_i64).await?;
        if quota.remaining <= 0 {
            return Err(AppError::DebateConflict(
                DEBATE_ASSISTANT_QUOTA_EXHAUSTED.to_string(),
            ));
        }

        if let Some(case_id) = normalized.case_id {
            ensure_debate_assistant_case_belongs_to_session(&self.pool, session_id_i64, case_id)
                .await?;
        }

        let context = build_debate_assistant_transcript_context(
            &self.pool,
            &session,
            user.id,
            &effective_side,
        )
        .await?;
        let trace_id = normalized.trace_id.unwrap_or_else(|| {
            format!(
                "chat-assistant:debate-assistant:{session_id}:{}",
                Uuid::new_v4()
            )
        });

        let payload = match fetch_ai_judge_debate_assistant_payload(DebateAssistantProxyParams {
            base_url: &self.config.ai_judge.service_base_url,
            path: &self.config.ai_judge.assistant_debate_assistant_path,
            timeout_ms: self.config.ai_judge.assistant_timeout_ms,
            internal_key: &self.config.ai_judge.internal_key,
            session_id,
            trace_id: &trace_id,
            intent: &normalized.intent,
            question: &normalized.question,
            draft: normalized.draft.as_deref(),
            side: &effective_side,
            case_id: normalized.case_id,
            room_transcript_context: &context,
        })
        .await
        {
            Ok(payload) => payload,
            Err(reason_code) => {
                tracing::warn!(
                    session_id,
                    reason_code,
                    "AI judge debate assistant proxy failed"
                );
                return Ok(build_debate_assistant_error_output(
                    session_id,
                    normalized.case_id,
                    "proxy_error",
                    DEBATE_ASSISTANT_PROXY_FAILED,
                ));
            }
        };

        if let Err(reason_code) =
            validate_debate_assistant_payload(&payload, session_id, normalized.case_id)
        {
            tracing::warn!(
                session_id,
                reason_code,
                "AI judge debate assistant contract violation blocked"
            );
            return Ok(build_debate_assistant_error_output(
                session_id,
                normalized.case_id,
                "contract_violation",
                DEBATE_ASSISTANT_CONTRACT_VIOLATION,
            ));
        }

        if debate_assistant_payload_is_accepted(&payload) {
            confirm_debate_assistant_quota_usage(&self.pool, user.id, session_id_i64).await?;
        }

        Ok(build_debate_assistant_output_from_payload(
            session_id, payload,
        ))
    }
}

fn normalize_debate_assistant_input(
    input: RequestDebateAssistantQueryInput,
) -> Result<NormalizedDebateAssistantInput, AppError> {
    let intent = input.intent.trim().to_ascii_lowercase();
    if !DEBATE_ASSISTANT_INTENTS.contains(&intent.as_str()) {
        return Err(AppError::DebateError(
            "intent must be one of: room_summary, opponent_summary, unanswered_points, speech_structure, draft_polish"
                .to_string(),
        ));
    }
    let question = normalize_required_debate_assistant_text(
        "question",
        input.question,
        MAX_DEBATE_ASSISTANT_QUESTION_LEN,
    )?;
    let draft = normalize_optional_debate_assistant_text(
        "draft",
        input.draft,
        MAX_DEBATE_ASSISTANT_DRAFT_LEN,
    )?;
    let trace_id = normalize_optional_debate_assistant_text(
        "traceId",
        input.trace_id,
        MAX_DEBATE_ASSISTANT_TRACE_ID_LEN,
    )?;
    let side = match input.side {
        Some(value) => {
            let normalized = value.trim().to_ascii_lowercase();
            if normalized == "pro" || normalized == "con" {
                Some(normalized)
            } else {
                return Err(AppError::DebateError(
                    "side must be one of: pro, con".to_string(),
                ));
            }
        }
        None => None,
    };
    Ok(NormalizedDebateAssistantInput {
        intent,
        question,
        draft,
        trace_id,
        side,
        case_id: input.case_id,
    })
}

fn normalize_required_debate_assistant_text(
    field: &str,
    value: String,
    max_len: usize,
) -> Result<String, AppError> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return Err(AppError::DebateError(format!("{field} is required")));
    }
    if trimmed.chars().count() > max_len {
        return Err(AppError::DebateError(format!(
            "{field} is too long, max {max_len} chars"
        )));
    }
    Ok(trimmed.to_string())
}

fn normalize_optional_debate_assistant_text(
    field: &str,
    value: Option<String>,
    max_len: usize,
) -> Result<Option<String>, AppError> {
    match value {
        Some(raw) => {
            let trimmed = raw.trim();
            if trimmed.is_empty() {
                return Ok(None);
            }
            if trimmed.chars().count() > max_len {
                return Err(AppError::DebateError(format!(
                    "{field} is too long, max {max_len} chars"
                )));
            }
            Ok(Some(trimmed.to_string()))
        }
        None => Ok(None),
    }
}

async fn load_debate_assistant_session(
    pool: &sqlx::PgPool,
    session_id: i64,
    user_id: i64,
) -> Result<DebateAssistantSessionRow, AppError> {
    let row = sqlx::query_as::<_, DebateAssistantSessionRow>(
        r#"
        SELECT
          s.id AS session_id,
          s.status,
          s.scheduled_start_at,
          s.actual_start_at,
          s.end_at,
          t.title,
          t.description,
          t.category,
          t.stance_pro,
          t.stance_con,
          sp.side AS viewer_side
        FROM debate_sessions s
        JOIN debate_topics t ON t.id = s.topic_id
        LEFT JOIN session_participants sp
          ON sp.session_id = s.id AND sp.user_id = $2
        WHERE s.id = $1
        "#,
    )
    .bind(session_id)
    .bind(user_id)
    .fetch_optional(pool)
    .await?;
    row.ok_or_else(|| AppError::NotFound(format!("debate session id {session_id}")))
}

async fn load_debate_assistant_membership_status(
    pool: &sqlx::PgPool,
    user_id: i64,
) -> Result<DebateAssistantMembershipStatus, AppError> {
    let row = sqlx::query_as::<_, DebateAssistantEntitlementRow>(
        r#"
        SELECT status, starts_at, expires_at
        FROM user_entitlements
        WHERE user_id = $1
          AND feature_key = $2
        "#,
    )
    .bind(user_id)
    .bind(DEBATE_ASSISTANT_FEATURE_KEY)
    .fetch_optional(pool)
    .await?;

    let now = Utc::now();
    let active = row
        .as_ref()
        .map(|row| {
            row.status == "active"
                && row.starts_at <= now
                && row
                    .expires_at
                    .map(|expires_at| expires_at > now)
                    .unwrap_or(true)
        })
        .unwrap_or(false);

    Ok(DebateAssistantMembershipStatus {
        required: true,
        active,
        feature_key: DEBATE_ASSISTANT_FEATURE_KEY.to_string(),
        status: row
            .as_ref()
            .map(|row| row.status.clone())
            .unwrap_or_else(|| "missing".to_string()),
        starts_at: row.as_ref().map(|row| row.starts_at),
        expires_at: row.as_ref().and_then(|row| row.expires_at),
    })
}

async fn load_debate_assistant_quota_status(
    pool: &sqlx::PgPool,
    user_id: i64,
    session_id: i64,
) -> Result<DebateAssistantQuotaStatus, AppError> {
    let row = sqlx::query_as::<_, DebateAssistantUsageRow>(
        r#"
        SELECT used_count, quota_limit
        FROM debate_assistant_session_usage
        WHERE user_id = $1
          AND session_id = $2
        "#,
    )
    .bind(user_id)
    .bind(session_id)
    .fetch_optional(pool)
    .await?;
    Ok(map_debate_assistant_quota_status(row))
}

fn map_debate_assistant_quota_status(
    row: Option<DebateAssistantUsageRow>,
) -> DebateAssistantQuotaStatus {
    let used = row.as_ref().map(|row| row.used_count).unwrap_or(0);
    let limit = row
        .as_ref()
        .map(|row| row.quota_limit)
        .unwrap_or(DEFAULT_DEBATE_ASSISTANT_QUOTA_LIMIT);
    DebateAssistantQuotaStatus {
        scope: "session".to_string(),
        limit,
        used,
        remaining: (limit - used).max(0),
        reset_at: None,
    }
}

async fn confirm_debate_assistant_quota_usage(
    pool: &sqlx::PgPool,
    user_id: i64,
    session_id: i64,
) -> Result<DebateAssistantQuotaStatus, AppError> {
    let row = sqlx::query_as::<_, DebateAssistantUsageRow>(
        r#"
        INSERT INTO debate_assistant_session_usage(user_id, session_id, used_count, quota_limit)
        VALUES ($1, $2, 1, $3)
        ON CONFLICT (user_id, session_id) DO UPDATE
        SET used_count = debate_assistant_session_usage.used_count + 1,
            updated_at = NOW()
        WHERE debate_assistant_session_usage.used_count
              < debate_assistant_session_usage.quota_limit
        RETURNING used_count, quota_limit
        "#,
    )
    .bind(user_id)
    .bind(session_id)
    .bind(DEFAULT_DEBATE_ASSISTANT_QUOTA_LIMIT)
    .fetch_optional(pool)
    .await?;
    row.map(|row| map_debate_assistant_quota_status(Some(row)))
        .ok_or_else(|| AppError::DebateConflict(DEBATE_ASSISTANT_QUOTA_EXHAUSTED.to_string()))
}

async fn ensure_debate_assistant_case_belongs_to_session(
    pool: &sqlx::PgPool,
    session_id: i64,
    case_id: u64,
) -> Result<(), AppError> {
    let case_id_i64 = i64::try_from(case_id)
        .map_err(|_| AppError::DebateError("debate_assistant_case_mismatch".to_string()))?;
    let exists: Option<i32> = sqlx::query_scalar(
        r#"
        SELECT 1
        FROM (
          SELECT id, session_id FROM judge_final_jobs
          UNION ALL
          SELECT id, session_id FROM judge_phase_jobs
        ) judge_cases
        WHERE id = $1
          AND session_id = $2
        LIMIT 1
        "#,
    )
    .bind(case_id_i64)
    .bind(session_id)
    .fetch_optional(pool)
    .await?;
    if exists.is_some() {
        Ok(())
    } else {
        Err(AppError::DebateConflict(
            "debate_assistant_case_mismatch".to_string(),
        ))
    }
}

async fn build_debate_assistant_transcript_context(
    pool: &sqlx::PgPool,
    session: &DebateAssistantSessionRow,
    user_id: i64,
    viewer_side: &str,
) -> Result<Value, AppError> {
    let mut rows = sqlx::query_as::<_, DebateAssistantMessageRow>(
        r#"
        SELECT message_id, session_id, user_id, side, content, created_at
        FROM (
          SELECT
            id AS message_id,
            session_id,
            user_id,
            side,
            content,
            created_at
          FROM session_messages
          WHERE session_id = $1
          ORDER BY id DESC
          LIMIT $2
        ) recent
        ORDER BY message_id ASC
        "#,
    )
    .bind(session.session_id)
    .bind(DEBATE_ASSISTANT_CONTEXT_MESSAGE_LIMIT + 1)
    .fetch_all(pool)
    .await?;
    let truncated = rows.len() > DEBATE_ASSISTANT_CONTEXT_MESSAGE_LIMIT as usize;
    if truncated {
        rows.remove(0);
    }
    let latest_message_id: i64 = sqlx::query_scalar(
        r#"
        SELECT COALESCE(MAX(id), 0)
        FROM session_messages
        WHERE session_id = $1
        "#,
    )
    .bind(session.session_id)
    .fetch_one(pool)
    .await?;

    let recent_messages: Vec<Value> = rows
        .into_iter()
        .map(|row| {
            json!({
                "messageId": row.message_id,
                "sessionId": row.session_id,
                "userId": row.user_id,
                "side": row.side,
                "content": row.content,
                "createdAt": row.created_at,
            })
        })
        .collect();

    Ok(json!({
        "version": DEBATE_ASSISTANT_CONTEXT_VERSION,
        "sessionId": session.session_id,
        "topic": {
            "title": &session.title,
            "description": &session.description,
            "category": &session.category,
            "stancePro": &session.stance_pro,
            "stanceCon": &session.stance_con,
        },
        "session": {
            "status": &session.status,
            "scheduledStartAt": session.scheduled_start_at,
            "actualStartAt": session.actual_start_at,
            "endAt": session.end_at,
        },
        "viewer": {
            "userId": user_id,
            "role": "participant",
            "side": viewer_side,
        },
        "recentMessages": recent_messages,
        "messageWindow": {
            "limit": DEBATE_ASSISTANT_CONTEXT_MESSAGE_LIMIT,
            "order": "asc",
            "truncated": truncated,
            "latestMessageId": latest_message_id,
        },
        "redaction": {
            "publicOnly": true,
            "privateFieldsRedacted": true,
            "officialVerdictFieldsRedacted": true,
            "membershipSignalsRedacted": true,
        },
    }))
}

async fn fetch_ai_judge_debate_assistant_payload(
    params: DebateAssistantProxyParams<'_>,
) -> Result<Value, &'static str> {
    let url = build_debate_assistant_http_url(params.base_url, params.path, params.session_id);
    let client = Client::builder()
        .timeout(Duration::from_millis(params.timeout_ms.max(1)))
        .build()
        .map_err(|_| "debate_assistant_proxy_http_client_failed")?;
    let mut body = Map::new();
    body.insert("trace_id".to_string(), json!(params.trace_id));
    body.insert("intent".to_string(), json!(params.intent));
    body.insert("question".to_string(), json!(params.question));
    body.insert("draft".to_string(), json!(params.draft));
    body.insert("side".to_string(), json!(params.side));
    body.insert("caseId".to_string(), json!(params.case_id));
    body.insert(
        "roomTranscriptContext".to_string(),
        params.room_transcript_context.clone(),
    );

    let response = client
        .post(url)
        .header("x-ai-internal-key", params.internal_key)
        .json(&Value::Object(body))
        .send()
        .await
        .map_err(|_| "debate_assistant_proxy_request_failed")?;
    if !response.status().is_success() {
        return Err("debate_assistant_proxy_bad_status");
    }
    response
        .json::<Value>()
        .await
        .map_err(|_| "debate_assistant_proxy_bad_json")
}

fn build_debate_assistant_http_url(base_url: &str, path: &str, session_id: u64) -> String {
    let resolved_path = path
        .replace("{session_id}", &session_id.to_string())
        .replace(":session_id", &session_id.to_string());
    let resolved_path = if resolved_path.starts_with('/') {
        resolved_path
    } else {
        format!("/{resolved_path}")
    };
    format!("{}{}", base_url.trim_end_matches('/'), resolved_path)
}

fn validate_debate_assistant_payload(
    payload: &Value,
    expected_session_id: u64,
    expected_case_id: Option<u64>,
) -> Result<(), &'static str> {
    let Some(object) = payload.as_object() else {
        return Err(DEBATE_ASSISTANT_CONTRACT_VIOLATION);
    };
    if !debate_assistant_top_level_keys_match(object) {
        return Err(DEBATE_ASSISTANT_CONTRACT_VIOLATION);
    }
    if object.get("version").and_then(Value::as_str) != Some(DEBATE_ASSISTANT_CONTRACT_VERSION) {
        return Err(DEBATE_ASSISTANT_CONTRACT_VIOLATION);
    }
    if object.get("agentKind").and_then(Value::as_str) != Some(DEBATE_ASSISTANT_AGENT_KIND) {
        return Err(DEBATE_ASSISTANT_CONTRACT_VIOLATION);
    }
    if object.get("sessionId").and_then(Value::as_u64) != Some(expected_session_id) {
        return Err(DEBATE_ASSISTANT_CONTRACT_VIOLATION);
    }
    match expected_case_id {
        Some(case_id) if object.get("caseId").and_then(Value::as_u64) != Some(case_id) => {
            return Err(DEBATE_ASSISTANT_CONTRACT_VIOLATION);
        }
        None if !matches!(object.get("caseId"), Some(Value::Null)) => {
            return Err(DEBATE_ASSISTANT_CONTRACT_VIOLATION);
        }
        _ => {}
    }
    if object.get("advisoryOnly").and_then(Value::as_bool) != Some(true)
        || object.get("accepted").and_then(Value::as_bool).is_none()
        || object.get("status").and_then(Value::as_str).is_none()
        || object.get("statusReason").and_then(Value::as_str).is_none()
    {
        return Err(DEBATE_ASSISTANT_CONTRACT_VIOLATION);
    }
    let Some(boundary) = object.get("capabilityBoundary").and_then(Value::as_object) else {
        return Err(DEBATE_ASSISTANT_CONTRACT_VIOLATION);
    };
    if boundary.get("mode").and_then(Value::as_str) != Some("advisory_only")
        || boundary.get("advisoryOnly").and_then(Value::as_bool) != Some(true)
        || boundary
            .get("officialVerdictAuthority")
            .and_then(Value::as_bool)
            != Some(false)
        || boundary.get("writesVerdictLedger").and_then(Value::as_bool) != Some(false)
        || boundary.get("writesJudgeTrace").and_then(Value::as_bool) != Some(false)
        || boundary
            .get("canTriggerOfficialJudgeRoles")
            .and_then(Value::as_bool)
            != Some(false)
    {
        return Err(DEBATE_ASSISTANT_CONTRACT_VIOLATION);
    }
    for key in ["sharedContext", "advisoryContext", "output", "cacheProfile"] {
        if !matches!(object.get(key), Some(Value::Object(_))) {
            return Err(DEBATE_ASSISTANT_CONTRACT_VIOLATION);
        }
    }
    let shared_context = object.get("sharedContext").unwrap_or(&Value::Null);
    if !debate_assistant_transcript_context_matches(shared_context, expected_session_id) {
        return Err(DEBATE_ASSISTANT_CONTRACT_VIOLATION);
    }
    let advisory_context = object.get("advisoryContext").unwrap_or(&Value::Null);
    if let Some(room_context) = advisory_context
        .as_object()
        .and_then(|object| object.get("roomTranscriptContext"))
    {
        if room_context != shared_context {
            return Err(DEBATE_ASSISTANT_CONTRACT_VIOLATION);
        }
    }
    for key in ["sharedContext", "advisoryContext", "output"] {
        if debate_assistant_value_contains_forbidden_key(object.get(key).unwrap_or(&Value::Null)) {
            return Err(DEBATE_ASSISTANT_CONTRACT_VIOLATION);
        }
    }
    if object.get("status").and_then(Value::as_str) == Some("not_ready")
        && (object.get("accepted").and_then(Value::as_bool) != Some(false)
            || !debate_assistant_not_ready_error_code_allowed(
                object.get("errorCode").and_then(Value::as_str),
            ))
    {
        return Err(DEBATE_ASSISTANT_CONTRACT_VIOLATION);
    }
    Ok(())
}

fn debate_assistant_top_level_keys_match(object: &Map<String, Value>) -> bool {
    const KEYS: &[&str] = &[
        "version",
        "agentKind",
        "sessionId",
        "caseId",
        "advisoryOnly",
        "status",
        "statusReason",
        "accepted",
        "errorCode",
        "errorMessage",
        "capabilityBoundary",
        "sharedContext",
        "advisoryContext",
        "output",
        "cacheProfile",
    ];
    object.len() == KEYS.len() && KEYS.iter().all(|key| object.contains_key(*key))
}

fn debate_assistant_transcript_context_matches(value: &Value, expected_session_id: u64) -> bool {
    let Some(object) = value.as_object() else {
        return false;
    };
    object.get("version").and_then(Value::as_str) == Some(DEBATE_ASSISTANT_CONTEXT_VERSION)
        && object.get("sessionId").and_then(Value::as_u64) == Some(expected_session_id)
        && matches!(object.get("topic"), Some(Value::Object(_)))
        && matches!(object.get("session"), Some(Value::Object(_)))
        && matches!(object.get("viewer"), Some(Value::Object(_)))
        && matches!(object.get("recentMessages"), Some(Value::Array(_)))
        && matches!(object.get("messageWindow"), Some(Value::Object(_)))
        && object
            .get("redaction")
            .and_then(Value::as_object)
            .and_then(|redaction| redaction.get("publicOnly"))
            .and_then(Value::as_bool)
            == Some(true)
        && object
            .get("redaction")
            .and_then(Value::as_object)
            .and_then(|redaction| redaction.get("privateFieldsRedacted"))
            .and_then(Value::as_bool)
            == Some(true)
        && object
            .get("redaction")
            .and_then(Value::as_object)
            .and_then(|redaction| redaction.get("officialVerdictFieldsRedacted"))
            .and_then(Value::as_bool)
            == Some(true)
        && object
            .get("redaction")
            .and_then(Value::as_object)
            .and_then(|redaction| redaction.get("membershipSignalsRedacted"))
            .and_then(Value::as_bool)
            == Some(true)
}

fn debate_assistant_not_ready_error_code_allowed(error_code: Option<&str>) -> bool {
    matches!(
        error_code,
        Some(DEBATE_ASSISTANT_NOT_READY) | Some("assistant_executor_not_configured")
    )
}

fn debate_assistant_payload_is_accepted(payload: &Value) -> bool {
    payload.get("status").and_then(Value::as_str) == Some("ok")
        && payload.get("accepted").and_then(Value::as_bool) == Some(true)
}

fn build_debate_assistant_output_from_payload(
    session_id: u64,
    payload: Value,
) -> DebateAssistantOutput {
    DebateAssistantOutput {
        version: payload
            .get("version")
            .and_then(Value::as_str)
            .unwrap_or(DEBATE_ASSISTANT_CONTRACT_VERSION)
            .to_string(),
        agent_kind: payload
            .get("agentKind")
            .and_then(Value::as_str)
            .unwrap_or(DEBATE_ASSISTANT_AGENT_KIND)
            .to_string(),
        session_id,
        case_id: payload.get("caseId").and_then(Value::as_u64),
        advisory_only: payload
            .get("advisoryOnly")
            .and_then(Value::as_bool)
            .unwrap_or(false),
        status: payload
            .get("status")
            .and_then(Value::as_str)
            .unwrap_or("proxy_error")
            .to_string(),
        status_reason: payload
            .get("statusReason")
            .and_then(Value::as_str)
            .unwrap_or(DEBATE_ASSISTANT_PROXY_FAILED)
            .to_string(),
        accepted: payload
            .get("accepted")
            .and_then(Value::as_bool)
            .unwrap_or(false),
        error_code: payload
            .get("errorCode")
            .and_then(Value::as_str)
            .map(ToString::to_string),
        error_message: payload
            .get("errorMessage")
            .and_then(Value::as_str)
            .map(ToString::to_string),
        capability_boundary: payload
            .get("capabilityBoundary")
            .cloned()
            .unwrap_or_else(default_debate_assistant_capability_boundary),
        shared_context: payload
            .get("sharedContext")
            .cloned()
            .unwrap_or_else(|| json!({})),
        advisory_context: payload
            .get("advisoryContext")
            .cloned()
            .unwrap_or_else(|| json!({})),
        output: payload.get("output").cloned().unwrap_or_else(|| json!({})),
        cache_profile: payload
            .get("cacheProfile")
            .cloned()
            .unwrap_or_else(|| default_debate_assistant_cache_profile(session_id)),
    }
}

fn build_debate_assistant_error_output(
    session_id: u64,
    case_id: Option<u64>,
    status: &str,
    reason_code: &str,
) -> DebateAssistantOutput {
    DebateAssistantOutput {
        version: DEBATE_ASSISTANT_CONTRACT_VERSION.to_string(),
        agent_kind: DEBATE_ASSISTANT_AGENT_KIND.to_string(),
        session_id,
        case_id,
        advisory_only: true,
        status: status.to_string(),
        status_reason: reason_code.to_string(),
        accepted: false,
        error_code: Some(reason_code.to_string()),
        error_message: Some("debate assistant request failed".to_string()),
        capability_boundary: default_debate_assistant_capability_boundary(),
        shared_context: json!({}),
        advisory_context: json!({}),
        output: json!({
            "accepted": false,
            "intent": null,
            "answerSummary": null,
            "keyPoints": [],
            "suggestedActions": [],
            "contextCaveats": ["辩论助手暂不可用，请稍后重试。"],
            "boundaryNotice": debate_assistant_boundary_notice(),
            "sourceUsePolicy": "未生成助手回答。"
        }),
        cache_profile: default_debate_assistant_cache_profile(session_id),
    }
}

fn default_debate_assistant_capability_boundary() -> Value {
    json!({
        "mode": "advisory_only",
        "advisoryOnly": true,
        "officialVerdictAuthority": false,
        "writesVerdictLedger": false,
        "writesJudgeTrace": false,
        "canTriggerOfficialJudgeRoles": false
    })
}

fn default_debate_assistant_cache_profile(session_id: u64) -> Value {
    json!({
        "cacheable": false,
        "ttlSeconds": 0,
        "cacheKey": format!("debate-assistant:chat-proxy:session:{session_id}"),
        "varyBy": ["authorization", "sessionId", "intent"]
    })
}

fn debate_assistant_boundary_notice() -> String {
    "私人辅助，不代表官方裁决；不会自动发送公开发言。".to_string()
}

fn normalize_debate_assistant_contract_key(key: &str) -> String {
    key.chars()
        .filter(|c| *c != '_' && *c != '-')
        .flat_map(char::to_lowercase)
        .collect()
}

fn debate_assistant_value_contains_forbidden_key(value: &Value) -> bool {
    match value {
        Value::Object(map) => map.iter().any(|(key, value)| {
            is_debate_assistant_forbidden_key(key)
                || debate_assistant_value_contains_forbidden_key(value)
        }),
        Value::Array(items) => items
            .iter()
            .any(debate_assistant_value_contains_forbidden_key),
        _ => false,
    }
}

fn is_debate_assistant_forbidden_key(key: &str) -> bool {
    matches!(
        normalize_debate_assistant_contract_key(key).as_str(),
        "winner"
            | "proscore"
            | "conscore"
            | "dimensionscores"
            | "verdictreason"
            | "verdictledger"
            | "fairnessgate"
            | "trustattestation"
            | "judgetrace"
            | "rawprompt"
            | "rawtrace"
            | "artifactref"
            | "artifactrefs"
            | "providerconfig"
            | "secret"
            | "secretref"
            | "credential"
            | "internalkey"
            | "xaiinternalkey"
            | "walletbalance"
            | "membershiptier"
            | "userentitlements"
            | "phone"
            | "phonenumber"
            | "email"
            | "officialverdictauthority"
            | "writesverdictledger"
            | "writesjudgetrace"
            | "cantriggerofficialjudgeroles"
    )
}
