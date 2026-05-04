use super::*;
use serde_json::Value;

#[derive(Debug, FromRow)]
struct NpcRoomConfigRow {
    display_name: String,
    enabled: bool,
    allow_speak: bool,
    allow_praise: bool,
    allow_effect: bool,
}

#[derive(Debug, FromRow)]
struct NpcMessageTargetRow {
    session_id: i64,
    user_id: i64,
    side: String,
}

#[derive(Debug, Clone)]
struct NormalizedNpcActionCandidate {
    action_uid: String,
    session_id: i64,
    npc_id: String,
    action_type: String,
    public_text: Option<String>,
    target_message_id: Option<i64>,
    target_user_id: Option<i64>,
    target_side: Option<String>,
    effect_kind: Option<String>,
    npc_status: Option<String>,
    reason_code: Option<String>,
    source_event_id: Option<String>,
    source_message_id: Option<i64>,
    policy_version: String,
    executor_kind: String,
    executor_version: String,
}

#[allow(dead_code)]
impl AppState {
    pub async fn get_debate_npc_decision_context(
        &self,
        session_id: u64,
        query: GetDebateNpcDecisionContextQuery,
    ) -> Result<GetDebateNpcDecisionContextOutput, AppError> {
        let session_id_i64 = safe_u64_to_i64(session_id, DEBATE_NPC_CONTEXT_INVALID_SESSION_ID)?;
        let trigger_message_id_i64 = safe_u64_to_i64(
            query.trigger_message_id,
            DEBATE_NPC_CONTEXT_INVALID_MESSAGE_ID,
        )?;
        let limit = normalize_npc_context_limit(query.limit);
        let trigger_message = load_npc_message_snapshot(&self.pool, trigger_message_id_i64).await?;
        if trigger_message.session_id != session_id_i64 {
            return Err(AppError::NotFound(format!(
                "debate message id {}",
                query.trigger_message_id
            )));
        }
        let recent_messages = load_recent_npc_message_snapshots(
            &self.pool,
            session_id_i64,
            trigger_message_id_i64,
            limit,
        )
        .await?;
        Ok(GetDebateNpcDecisionContextOutput {
            session_id,
            npc_id: DEBATE_NPC_DEFAULT_ID.to_string(),
            source_event_id: query.source_event_id,
            trigger_message,
            recent_messages,
            now: Utc::now(),
        })
    }

    pub async fn submit_debate_npc_action_candidate(
        &self,
        payload: Value,
    ) -> Result<SubmitDebateNpcActionCandidateOutput, AppError> {
        let action_uid = extract_action_uid(&payload);
        if payload_has_forbidden_official_field(&payload) {
            return Ok(rejected_candidate(
                action_uid,
                DEBATE_NPC_ACTION_FORBIDDEN_FIELD,
            ));
        }

        let input: SubmitDebateNpcActionCandidateInput =
            serde_json::from_value(payload).map_err(|_| {
                AppError::ValidationError(DEBATE_NPC_ACTION_INVALID_PAYLOAD.to_string())
            })?;
        let mut candidate = normalize_npc_action_candidate(input)?;
        let mut tx = self.pool.begin().await?;

        let lock_key = format!(
            "debate_npc_action:{}:{}",
            candidate.session_id, candidate.action_uid
        );
        sqlx::query("SELECT pg_advisory_xact_lock(hashtext($1))")
            .bind(&lock_key)
            .execute(&mut *tx)
            .await?;

        if let Some(existing) = load_npc_action_by_uid(&mut tx, &candidate.action_uid).await? {
            tx.commit().await?;
            return Ok(SubmitDebateNpcActionCandidateOutput {
                accepted: true,
                action_id: Some(existing.id as u64),
                action_uid: existing.action_uid,
                status: "replayed".to_string(),
                reason_code: None,
            });
        }

        let Some(config) =
            load_npc_room_config(&mut tx, candidate.session_id, &candidate.npc_id).await?
        else {
            tx.commit().await?;
            return Ok(rejected_candidate(
                candidate.action_uid,
                DEBATE_NPC_ACTION_DISABLED,
            ));
        };
        if !config.enabled {
            tx.commit().await?;
            return Ok(rejected_candidate(
                candidate.action_uid,
                DEBATE_NPC_ACTION_DISABLED,
            ));
        }
        if !is_action_capability_enabled(&config, &candidate.action_type) {
            tx.commit().await?;
            return Ok(rejected_candidate(
                candidate.action_uid,
                DEBATE_NPC_ACTION_CAPABILITY_DISABLED,
            ));
        }

        if let Some(target_message_id) = candidate.target_message_id {
            let Some(target) = load_message_target(&mut tx, target_message_id).await? else {
                tx.commit().await?;
                return Ok(rejected_candidate(
                    candidate.action_uid,
                    DEBATE_NPC_ACTION_TARGET_MESSAGE_MISMATCH,
                ));
            };
            if target.session_id != candidate.session_id {
                tx.commit().await?;
                return Ok(rejected_candidate(
                    candidate.action_uid,
                    DEBATE_NPC_ACTION_TARGET_MESSAGE_MISMATCH,
                ));
            }
            if let Some(expected_user_id) = candidate.target_user_id {
                if expected_user_id != target.user_id {
                    tx.commit().await?;
                    return Ok(rejected_candidate(
                        candidate.action_uid,
                        DEBATE_NPC_ACTION_TARGET_USER_MISMATCH,
                    ));
                }
            }
            if let Some(expected_side) = candidate.target_side.as_deref() {
                if expected_side != target.side {
                    tx.commit().await?;
                    return Ok(rejected_candidate(
                        candidate.action_uid,
                        DEBATE_NPC_ACTION_TARGET_SIDE_MISMATCH,
                    ));
                }
            }
            candidate.target_user_id = Some(target.user_id);
            candidate.target_side = Some(target.side);
        }

        if let Some(source_message_id) = candidate.source_message_id {
            let Some(source) = load_message_target(&mut tx, source_message_id).await? else {
                tx.commit().await?;
                return Ok(rejected_candidate(
                    candidate.action_uid,
                    DEBATE_NPC_ACTION_SOURCE_MESSAGE_MISMATCH,
                ));
            };
            if source.session_id != candidate.session_id {
                tx.commit().await?;
                return Ok(rejected_candidate(
                    candidate.action_uid,
                    DEBATE_NPC_ACTION_SOURCE_MESSAGE_MISMATCH,
                ));
            }
        }

        if candidate.action_type == "praise"
            && target_message_already_has_praise(
                &mut tx,
                candidate.session_id,
                candidate.target_message_id,
            )
            .await?
        {
            tx.commit().await?;
            return Ok(rejected_candidate(
                candidate.action_uid,
                DEBATE_NPC_ACTION_TARGET_ALREADY_HAS_PRAISE,
            ));
        }

        if npc_action_hits_rate_limit(&mut tx, &candidate).await? {
            tx.commit().await?;
            return Ok(rejected_candidate(
                candidate.action_uid,
                DEBATE_NPC_ACTION_RATE_LIMITED,
            ));
        }

        let action = insert_npc_action(&mut tx, &candidate, &config.display_name).await?;

        self.event_bus
            .enqueue_in_tx(
                &mut tx,
                DomainEvent::DebateNpcActionCreated(DebateNpcActionCreatedEvent {
                    action_id: action.id as u64,
                    action_uid: action.action_uid.clone(),
                    session_id: action.session_id as u64,
                    npc_id: action.npc_id.clone(),
                    display_name: action.display_name.clone(),
                    action_type: action.action_type.clone(),
                    public_text: action.public_text.clone(),
                    target_message_id: action.target_message_id.map(|id| id as u64),
                    target_user_id: action.target_user_id.map(|id| id as u64),
                    target_side: action.target_side.clone(),
                    effect_kind: action.effect_kind.clone(),
                    npc_status: action.npc_status.clone(),
                    reason_code: action.reason_code.clone(),
                    created_at: action.created_at,
                }),
            )
            .await
            .map_err(|err| {
                warn!(
                    session_id = action.session_id,
                    action_id = action.id,
                    "debate npc action outbox enqueue failed: {}",
                    err
                );
                AppError::ServerError(DEBATE_NPC_ACTION_OUTBOX_ENQUEUE_FAILED.to_string())
            })?;

        tx.commit().await?;
        Ok(SubmitDebateNpcActionCandidateOutput {
            accepted: true,
            action_id: Some(action.id as u64),
            action_uid: action.action_uid,
            status: "created".to_string(),
            reason_code: None,
        })
    }
}

async fn load_npc_message_snapshot(
    pool: &sqlx::PgPool,
    message_id: i64,
) -> Result<DebateNpcMessageSnapshot, AppError> {
    let row = sqlx::query_as::<_, DebateNpcMessageSnapshot>(
        r#"
        SELECT
          id AS message_id,
          session_id,
          user_id,
          side,
          content,
          created_at
        FROM session_messages
        WHERE id = $1
        "#,
    )
    .bind(message_id)
    .fetch_optional(pool)
    .await?;
    row.ok_or_else(|| AppError::NotFound(format!("debate message id {message_id}")))
}

async fn load_recent_npc_message_snapshots(
    pool: &sqlx::PgPool,
    session_id: i64,
    trigger_message_id: i64,
    limit: i64,
) -> Result<Vec<DebateNpcMessageSnapshot>, AppError> {
    let rows = sqlx::query_as::<_, DebateNpcMessageSnapshot>(
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
              AND id <= $2
            ORDER BY id DESC
            LIMIT $3
        ) recent
        ORDER BY message_id ASC
        "#,
    )
    .bind(session_id)
    .bind(trigger_message_id)
    .bind(limit)
    .fetch_all(pool)
    .await?;
    Ok(rows)
}

fn normalize_npc_context_limit(raw: Option<u64>) -> i64 {
    raw.unwrap_or(DEBATE_NPC_CONTEXT_DEFAULT_LIMIT)
        .clamp(1, DEBATE_NPC_CONTEXT_MAX_LIMIT) as i64
}

async fn load_npc_action_by_uid(
    tx: &mut Transaction<'_, Postgres>,
    action_uid: &str,
) -> Result<Option<DebateNpcAction>, AppError> {
    let existing = sqlx::query_as::<_, DebateNpcAction>(
        r#"
        SELECT
          id, action_uid, session_id, npc_id, display_name, action_type, public_text,
          target_message_id, target_user_id, target_side, effect_kind, npc_status,
          reason_code, source_event_id, source_message_id, policy_version,
          executor_kind, executor_version, created_at
        FROM debate_npc_actions
        WHERE action_uid = $1
        "#,
    )
    .bind(action_uid)
    .fetch_optional(&mut **tx)
    .await?;
    Ok(existing)
}

async fn load_npc_room_config(
    tx: &mut Transaction<'_, Postgres>,
    session_id: i64,
    npc_id: &str,
) -> Result<Option<NpcRoomConfigRow>, AppError> {
    let config = sqlx::query_as::<_, NpcRoomConfigRow>(
        r#"
        SELECT display_name, enabled, allow_speak, allow_praise, allow_effect
        FROM debate_npc_room_configs
        WHERE session_id = $1 AND npc_id = $2
        "#,
    )
    .bind(session_id)
    .bind(npc_id)
    .fetch_optional(&mut **tx)
    .await?;
    Ok(config)
}

async fn load_message_target(
    tx: &mut Transaction<'_, Postgres>,
    message_id: i64,
) -> Result<Option<NpcMessageTargetRow>, AppError> {
    let target = sqlx::query_as::<_, NpcMessageTargetRow>(
        r#"
        SELECT session_id, user_id, side
        FROM session_messages
        WHERE id = $1
        "#,
    )
    .bind(message_id)
    .fetch_optional(&mut **tx)
    .await?;
    Ok(target)
}

async fn target_message_already_has_praise(
    tx: &mut Transaction<'_, Postgres>,
    session_id: i64,
    target_message_id: Option<i64>,
) -> Result<bool, AppError> {
    let Some(target_message_id) = target_message_id else {
        return Ok(false);
    };
    let exists: bool = sqlx::query_scalar(
        r#"
        SELECT EXISTS(
          SELECT 1
          FROM debate_npc_actions
          WHERE session_id = $1
            AND action_type = 'praise'
            AND target_message_id = $2
        )
        "#,
    )
    .bind(session_id)
    .bind(target_message_id)
    .fetch_one(&mut **tx)
    .await?;
    Ok(exists)
}

async fn npc_action_hits_rate_limit(
    tx: &mut Transaction<'_, Postgres>,
    candidate: &NormalizedNpcActionCandidate,
) -> Result<bool, AppError> {
    let room_count: i64 = sqlx::query_scalar(
        r#"
        SELECT COUNT(*)
        FROM debate_npc_actions
        WHERE session_id = $1
          AND npc_id = $2
          AND created_at >= NOW() - INTERVAL '60 seconds'
        "#,
    )
    .bind(candidate.session_id)
    .bind(&candidate.npc_id)
    .fetch_one(&mut **tx)
    .await?;
    if room_count >= DEBATE_NPC_ACTION_ROOM_MAX_PER_MINUTE {
        return Ok(true);
    }

    let room_recent: bool = sqlx::query_scalar(
        r#"
        SELECT EXISTS(
          SELECT 1
          FROM debate_npc_actions
          WHERE session_id = $1
            AND npc_id = $2
            AND created_at >= NOW() - ($3::bigint * INTERVAL '1 second')
        )
        "#,
    )
    .bind(candidate.session_id)
    .bind(&candidate.npc_id)
    .bind(DEBATE_NPC_ACTION_ROOM_MIN_INTERVAL_SECS)
    .fetch_one(&mut **tx)
    .await?;
    if room_recent {
        return Ok(true);
    }

    if candidate.action_type == "praise" {
        if let Some(target_user_id) = candidate.target_user_id {
            let target_user_recent: bool = sqlx::query_scalar(
                r#"
                SELECT EXISTS(
                  SELECT 1
                  FROM debate_npc_actions
                  WHERE session_id = $1
                    AND npc_id = $2
                    AND action_type = 'praise'
                    AND target_user_id = $3
                    AND created_at >= NOW() - ($4::bigint * INTERVAL '1 second')
                )
                "#,
            )
            .bind(candidate.session_id)
            .bind(&candidate.npc_id)
            .bind(target_user_id)
            .bind(DEBATE_NPC_ACTION_TARGET_USER_PRAISE_MIN_INTERVAL_SECS)
            .fetch_one(&mut **tx)
            .await?;
            if target_user_recent {
                return Ok(true);
            }
        }
    }

    Ok(false)
}

async fn insert_npc_action(
    tx: &mut Transaction<'_, Postgres>,
    candidate: &NormalizedNpcActionCandidate,
    display_name: &str,
) -> Result<DebateNpcAction, AppError> {
    let action = sqlx::query_as::<_, DebateNpcAction>(
        r#"
        INSERT INTO debate_npc_actions(
          action_uid, session_id, npc_id, display_name, action_type, public_text,
          target_message_id, target_user_id, target_side, effect_kind, npc_status,
          reason_code, source_event_id, source_message_id, policy_version,
          executor_kind, executor_version
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
        RETURNING
          id, action_uid, session_id, npc_id, display_name, action_type, public_text,
          target_message_id, target_user_id, target_side, effect_kind, npc_status,
          reason_code, source_event_id, source_message_id, policy_version,
          executor_kind, executor_version, created_at
        "#,
    )
    .bind(&candidate.action_uid)
    .bind(candidate.session_id)
    .bind(&candidate.npc_id)
    .bind(display_name)
    .bind(&candidate.action_type)
    .bind(&candidate.public_text)
    .bind(candidate.target_message_id)
    .bind(candidate.target_user_id)
    .bind(&candidate.target_side)
    .bind(&candidate.effect_kind)
    .bind(&candidate.npc_status)
    .bind(&candidate.reason_code)
    .bind(&candidate.source_event_id)
    .bind(candidate.source_message_id)
    .bind(&candidate.policy_version)
    .bind(&candidate.executor_kind)
    .bind(&candidate.executor_version)
    .fetch_one(&mut **tx)
    .await?;
    Ok(action)
}

fn normalize_npc_action_candidate(
    input: SubmitDebateNpcActionCandidateInput,
) -> Result<NormalizedNpcActionCandidate, AppError> {
    let action_uid = normalize_required_text(
        input.action_uid,
        160,
        DEBATE_NPC_ACTION_UID_EMPTY,
        DEBATE_NPC_ACTION_UID_TOO_LONG,
    )?;
    let session_id = safe_u64_to_i64(input.session_id, "debate_npc_action_invalid_session_id")?;
    let npc_id = normalize_required_text(
        input.npc_id,
        64,
        DEBATE_NPC_ID_EMPTY,
        DEBATE_NPC_ID_TOO_LONG,
    )?;
    let action_type = normalize_action_type(input.action_type)?;
    let public_text = normalize_optional_text(input.public_text, 500)?;
    if matches!(action_type.as_str(), "speak" | "praise") && public_text.is_none() {
        return Err(AppError::ValidationError(
            DEBATE_NPC_ACTION_TEXT_REQUIRED.to_string(),
        ));
    }
    if action_type == "praise" && input.target_message_id.is_none() {
        return Err(AppError::ValidationError(
            DEBATE_NPC_ACTION_TARGET_REQUIRED.to_string(),
        ));
    }

    let target_message_id = input
        .target_message_id
        .map(|id| safe_u64_to_i64(id, "debate_npc_action_invalid_target_message_id"))
        .transpose()?;
    let target_user_id = input
        .target_user_id
        .map(|id| safe_u64_to_i64(id, "debate_npc_action_invalid_target_user_id"))
        .transpose()?;
    let source_message_id = input
        .source_message_id
        .map(|id| safe_u64_to_i64(id, "debate_npc_action_invalid_source_message_id"))
        .transpose()?;
    let target_side = normalize_optional_side(input.target_side)?;
    let effect_kind = normalize_optional_text(input.effect_kind, 40)?;
    let npc_status = normalize_optional_text(input.npc_status, 40)?;
    let reason_code = normalize_optional_text(input.reason_code, 80)?;
    let source_event_id = normalize_optional_text(input.source_event_id, 160)?;
    let policy_version = normalize_required_text(
        input.policy_version,
        64,
        DEBATE_NPC_ACTION_POLICY_VERSION_EMPTY,
        DEBATE_NPC_ACTION_POLICY_VERSION_TOO_LONG,
    )?;
    let executor_kind = normalize_required_text(
        input.executor_kind,
        40,
        DEBATE_NPC_ACTION_EXECUTOR_VERSION_EMPTY,
        DEBATE_NPC_ACTION_EXECUTOR_VERSION_TOO_LONG,
    )?;
    let executor_version = normalize_required_text(
        input.executor_version,
        64,
        DEBATE_NPC_ACTION_EXECUTOR_VERSION_EMPTY,
        DEBATE_NPC_ACTION_EXECUTOR_VERSION_TOO_LONG,
    )?;
    let _trace_id = normalize_optional_text(input.trace_id, 160)?;

    Ok(NormalizedNpcActionCandidate {
        action_uid,
        session_id,
        npc_id,
        action_type,
        public_text,
        target_message_id,
        target_user_id,
        target_side,
        effect_kind,
        npc_status,
        reason_code,
        source_event_id,
        source_message_id,
        policy_version,
        executor_kind,
        executor_version,
    })
}

fn normalize_action_type(raw: String) -> Result<String, AppError> {
    let normalized = raw.trim().to_ascii_lowercase();
    match normalized.as_str() {
        "speak" | "praise" | "effect" | "state_changed" => Ok(normalized),
        _ => Err(AppError::ValidationError(
            DEBATE_NPC_ACTION_INVALID_TYPE.to_string(),
        )),
    }
}

fn normalize_optional_side(raw: Option<String>) -> Result<Option<String>, AppError> {
    let Some(raw) = raw else {
        return Ok(None);
    };
    let normalized = raw.trim().to_ascii_lowercase();
    match normalized.as_str() {
        "" => Ok(None),
        "pro" | "con" => Ok(Some(normalized)),
        _ => Err(AppError::ValidationError(
            DEBATE_NPC_ACTION_TARGET_SIDE_INVALID.to_string(),
        )),
    }
}

fn normalize_required_text(
    raw: String,
    max_len: usize,
    empty_code: &str,
    too_long_code: &str,
) -> Result<String, AppError> {
    let normalized = raw.trim().to_string();
    if normalized.is_empty() {
        return Err(AppError::ValidationError(empty_code.to_string()));
    }
    if normalized.chars().count() > max_len {
        return Err(AppError::ValidationError(too_long_code.to_string()));
    }
    Ok(normalized)
}

fn normalize_optional_text(
    raw: Option<String>,
    max_len: usize,
) -> Result<Option<String>, AppError> {
    let Some(raw) = raw else {
        return Ok(None);
    };
    let normalized = raw.trim().to_string();
    if normalized.is_empty() {
        return Ok(None);
    }
    if normalized.chars().count() > max_len {
        let code = if max_len == 500 {
            DEBATE_NPC_ACTION_TEXT_TOO_LONG
        } else {
            DEBATE_NPC_ACTION_FIELD_TOO_LONG
        };
        return Err(AppError::ValidationError(code.to_string()));
    }
    Ok(Some(normalized))
}

fn is_action_capability_enabled(config: &NpcRoomConfigRow, action_type: &str) -> bool {
    match action_type {
        "speak" => config.allow_speak,
        "praise" => config.allow_praise,
        "effect" => config.allow_effect,
        "state_changed" => true,
        _ => false,
    }
}

fn extract_action_uid(payload: &Value) -> String {
    payload
        .get("actionUid")
        .and_then(Value::as_str)
        .unwrap_or_default()
        .trim()
        .to_string()
}

fn payload_has_forbidden_official_field(payload: &Value) -> bool {
    let Value::Object(map) = payload else {
        return false;
    };
    map.keys().any(|key| is_forbidden_official_field(key))
}

fn is_forbidden_official_field(key: &str) -> bool {
    let normalized: String = key
        .chars()
        .filter(|ch| ch.is_ascii_alphanumeric())
        .map(|ch| ch.to_ascii_lowercase())
        .collect();
    matches!(
        normalized.as_str(),
        "winner"
            | "proscore"
            | "conscore"
            | "finalrationale"
            | "verdictledger"
            | "judgetrace"
            | "fairnessreport"
            | "officialverdictauthority"
            | "writesverdictledger"
            | "writesjudgetrace"
            | "confidence"
            | "rawtrace"
            | "rawprompt"
    )
}

fn rejected_candidate(
    action_uid: String,
    reason_code: &str,
) -> SubmitDebateNpcActionCandidateOutput {
    SubmitDebateNpcActionCandidateOutput {
        accepted: false,
        action_id: None,
        action_uid,
        status: "rejected".to_string(),
        reason_code: Some(reason_code.to_string()),
    }
}
