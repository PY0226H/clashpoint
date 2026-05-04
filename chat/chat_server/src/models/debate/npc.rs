use super::*;
use crate::models::OpsPermission;
use serde_json::Value;

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
        let room_config =
            load_npc_room_config_pool(&self.pool, session_id_i64, DEBATE_NPC_DEFAULT_ID)
                .await?
                .unwrap_or_else(|| default_npc_room_config(session_id_i64, DEBATE_NPC_DEFAULT_ID));
        Ok(GetDebateNpcDecisionContextOutput {
            session_id,
            npc_id: DEBATE_NPC_DEFAULT_ID.to_string(),
            room_config,
            source_event_id: query.source_event_id,
            trigger_message,
            recent_messages,
            now: Utc::now(),
        })
    }

    pub async fn get_debate_npc_room_config_by_ops(
        &self,
        user: &User,
        session_id: u64,
        npc_id: Option<String>,
    ) -> Result<DebateNpcRoomConfig, AppError> {
        self.ensure_ops_permission(user, OpsPermission::DebateManage)
            .await?;
        let session_id_i64 = safe_u64_to_i64(session_id, DEBATE_NPC_CONFIG_SESSION_INVALID)?;
        let npc_id = normalize_npc_config_id(npc_id)?;
        ensure_debate_session_exists_pool(&self.pool, session_id_i64).await?;
        Ok(
            load_npc_room_config_pool(&self.pool, session_id_i64, &npc_id)
                .await?
                .unwrap_or_else(|| default_npc_room_config(session_id_i64, &npc_id)),
        )
    }

    pub async fn upsert_debate_npc_room_config_by_ops(
        &self,
        user: &User,
        session_id: u64,
        input: UpsertDebateNpcRoomConfigInput,
    ) -> Result<DebateNpcRoomConfig, AppError> {
        self.ensure_ops_permission(user, OpsPermission::DebateManage)
            .await?;
        let session_id_i64 = safe_u64_to_i64(session_id, DEBATE_NPC_CONFIG_SESSION_INVALID)?;
        let npc_id = normalize_npc_config_id(input.npc_id)?;

        let mut tx = self.pool.begin().await?;
        ensure_debate_session_exists_tx(&mut tx, session_id_i64).await?;
        let current = load_npc_room_config(&mut tx, session_id_i64, &npc_id).await?;
        let base = current
            .clone()
            .unwrap_or_else(|| default_npc_room_config(session_id_i64, &npc_id));

        let enabled = input.enabled.unwrap_or(base.enabled);
        let display_name = normalize_npc_config_text_or_current(
            input.display_name,
            base.display_name.clone(),
            64,
            DEBATE_NPC_CONFIG_DISPLAY_NAME_EMPTY,
            DEBATE_NPC_CONFIG_DISPLAY_NAME_TOO_LONG,
        )?;
        let persona_style = normalize_npc_config_text_or_current(
            input.persona_style,
            base.persona_style.clone(),
            64,
            DEBATE_NPC_CONFIG_PERSONA_STYLE_EMPTY,
            DEBATE_NPC_CONFIG_PERSONA_STYLE_TOO_LONG,
        )?;
        let status = normalize_next_npc_config_status(input.status, input.enabled, &base)?;
        let current_status_reason = current
            .as_ref()
            .and_then(|config| config.status_reason.clone());
        let status_reason =
            normalize_npc_config_reason(input.status_reason, current_status_reason)?;
        let manual_takeover_by_user_id = if status == DEBATE_NPC_STATUS_MANUAL_TAKEOVER {
            Some(user.id)
        } else {
            None
        };

        let config = sqlx::query_as::<_, DebateNpcRoomConfig>(
            r#"
            INSERT INTO debate_npc_room_configs(
              session_id, npc_id, display_name, enabled, persona_style, status,
              allow_speak, allow_praise, allow_effect, allow_state_change,
              allow_warning, allow_public_call, allow_pause, manual_takeover_by_user_id,
              status_reason, updated_by_user_id
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
            ON CONFLICT (session_id, npc_id) DO UPDATE
            SET
              display_name = EXCLUDED.display_name,
              enabled = EXCLUDED.enabled,
              persona_style = EXCLUDED.persona_style,
              status = EXCLUDED.status,
              allow_speak = EXCLUDED.allow_speak,
              allow_praise = EXCLUDED.allow_praise,
              allow_effect = EXCLUDED.allow_effect,
              allow_state_change = EXCLUDED.allow_state_change,
              allow_warning = EXCLUDED.allow_warning,
              allow_public_call = EXCLUDED.allow_public_call,
              allow_pause = EXCLUDED.allow_pause,
              manual_takeover_by_user_id = EXCLUDED.manual_takeover_by_user_id,
              status_reason = EXCLUDED.status_reason,
              updated_by_user_id = EXCLUDED.updated_by_user_id,
              updated_at = NOW()
            RETURNING
              session_id, npc_id, display_name, enabled, persona_style, status,
              allow_speak, allow_praise, allow_effect, allow_state_change,
              allow_warning, allow_public_call, allow_pause, manual_takeover_by_user_id,
              status_reason, updated_by_user_id, created_at, updated_at
            "#,
        )
        .bind(session_id_i64)
        .bind(&npc_id)
        .bind(&display_name)
        .bind(enabled)
        .bind(&persona_style)
        .bind(&status)
        .bind(input.allow_speak.unwrap_or(base.allow_speak))
        .bind(input.allow_praise.unwrap_or(base.allow_praise))
        .bind(input.allow_effect.unwrap_or(base.allow_effect))
        .bind(input.allow_state_change.unwrap_or(base.allow_state_change))
        .bind(input.allow_warning.unwrap_or(base.allow_warning))
        .bind(input.allow_public_call.unwrap_or(base.allow_public_call))
        .bind(input.allow_pause.unwrap_or(base.allow_pause))
        .bind(manual_takeover_by_user_id)
        .bind(&status_reason)
        .bind(user.id)
        .fetch_one(&mut *tx)
        .await?;

        if should_emit_npc_config_state_change(current.as_ref(), &config) {
            let action = insert_ops_npc_state_changed_action(&mut tx, &config).await?;
            self.enqueue_npc_action_created_in_tx(&mut tx, &action)
                .await?;
        }

        tx.commit().await?;
        Ok(config)
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
        if config.status != DEBATE_NPC_STATUS_ACTIVE {
            tx.commit().await?;
            return Ok(rejected_candidate(
                candidate.action_uid,
                DEBATE_NPC_ACTION_STATUS_BLOCKED,
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

        self.enqueue_npc_action_created_in_tx(&mut tx, &action)
            .await?;

        tx.commit().await?;
        Ok(SubmitDebateNpcActionCandidateOutput {
            accepted: true,
            action_id: Some(action.id as u64),
            action_uid: action.action_uid,
            status: "created".to_string(),
            reason_code: None,
        })
    }

    async fn enqueue_npc_action_created_in_tx(
        &self,
        tx: &mut Transaction<'_, Postgres>,
        action: &DebateNpcAction,
    ) -> Result<(), AppError> {
        self.event_bus
            .enqueue_in_tx(
                tx,
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
            })
            .map(|_| ())
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
) -> Result<Option<DebateNpcRoomConfig>, AppError> {
    let config = sqlx::query_as::<_, DebateNpcRoomConfig>(
        r#"
        SELECT
          session_id, npc_id, display_name, enabled, persona_style, status,
          allow_speak, allow_praise, allow_effect, allow_state_change,
          allow_warning, allow_public_call, allow_pause, manual_takeover_by_user_id,
          status_reason, updated_by_user_id, created_at, updated_at
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

async fn load_npc_room_config_pool(
    pool: &sqlx::PgPool,
    session_id: i64,
    npc_id: &str,
) -> Result<Option<DebateNpcRoomConfig>, AppError> {
    let config = sqlx::query_as::<_, DebateNpcRoomConfig>(
        r#"
        SELECT
          session_id, npc_id, display_name, enabled, persona_style, status,
          allow_speak, allow_praise, allow_effect, allow_state_change,
          allow_warning, allow_public_call, allow_pause, manual_takeover_by_user_id,
          status_reason, updated_by_user_id, created_at, updated_at
        FROM debate_npc_room_configs
        WHERE session_id = $1 AND npc_id = $2
        "#,
    )
    .bind(session_id)
    .bind(npc_id)
    .fetch_optional(pool)
    .await?;
    Ok(config)
}

fn default_npc_room_config(session_id: i64, npc_id: &str) -> DebateNpcRoomConfig {
    let now = Utc::now();
    DebateNpcRoomConfig {
        session_id,
        npc_id: npc_id.to_string(),
        display_name: DEBATE_NPC_DEFAULT_DISPLAY_NAME.to_string(),
        enabled: false,
        persona_style: DEBATE_NPC_DEFAULT_PERSONA_STYLE.to_string(),
        status: DEBATE_NPC_STATUS_UNAVAILABLE.to_string(),
        allow_speak: true,
        allow_praise: true,
        allow_effect: true,
        allow_state_change: true,
        allow_warning: true,
        allow_public_call: false,
        allow_pause: false,
        manual_takeover_by_user_id: None,
        status_reason: Some("npc_config_missing".to_string()),
        updated_by_user_id: None,
        created_at: now,
        updated_at: now,
    }
}

async fn ensure_debate_session_exists_pool(
    pool: &sqlx::PgPool,
    session_id: i64,
) -> Result<(), AppError> {
    let exists: bool =
        sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM debate_sessions WHERE id = $1)")
            .bind(session_id)
            .fetch_one(pool)
            .await?;
    if !exists {
        return Err(AppError::NotFound(format!(
            "debate session id {session_id}"
        )));
    }
    Ok(())
}

async fn ensure_debate_session_exists_tx(
    tx: &mut Transaction<'_, Postgres>,
    session_id: i64,
) -> Result<(), AppError> {
    let exists: bool =
        sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM debate_sessions WHERE id = $1)")
            .bind(session_id)
            .fetch_one(&mut **tx)
            .await?;
    if !exists {
        return Err(AppError::NotFound(format!(
            "debate session id {session_id}"
        )));
    }
    Ok(())
}

fn normalize_npc_config_id(raw: Option<String>) -> Result<String, AppError> {
    match raw {
        Some(value) => {
            normalize_required_text(value, 64, DEBATE_NPC_ID_EMPTY, DEBATE_NPC_ID_TOO_LONG)
        }
        None => Ok(DEBATE_NPC_DEFAULT_ID.to_string()),
    }
}

fn normalize_npc_config_text_or_current(
    raw: Option<String>,
    current: String,
    max_len: usize,
    empty_code: &'static str,
    too_long_code: &'static str,
) -> Result<String, AppError> {
    match raw {
        Some(value) => normalize_required_text(value, max_len, empty_code, too_long_code),
        None => Ok(current),
    }
}

fn normalize_next_npc_config_status(
    raw: Option<String>,
    enabled_input: Option<bool>,
    base: &DebateNpcRoomConfig,
) -> Result<String, AppError> {
    if let Some(value) = raw {
        return normalize_npc_config_status(value);
    }
    if enabled_input == Some(false) {
        return Ok(DEBATE_NPC_STATUS_UNAVAILABLE.to_string());
    }
    if enabled_input == Some(true) && base.status == DEBATE_NPC_STATUS_UNAVAILABLE {
        return Ok(DEBATE_NPC_STATUS_ACTIVE.to_string());
    }
    Ok(base.status.clone())
}

fn normalize_npc_config_status(raw: String) -> Result<String, AppError> {
    let normalized = raw.trim().to_ascii_lowercase();
    if matches!(
        normalized.as_str(),
        DEBATE_NPC_STATUS_ACTIVE
            | DEBATE_NPC_STATUS_SILENT
            | DEBATE_NPC_STATUS_MANUAL_TAKEOVER
            | DEBATE_NPC_STATUS_UNAVAILABLE
    ) {
        return Ok(normalized);
    }
    Err(AppError::ValidationError(
        DEBATE_NPC_CONFIG_INVALID_STATUS.to_string(),
    ))
}

fn normalize_npc_config_reason(
    raw: Option<String>,
    current: Option<String>,
) -> Result<Option<String>, AppError> {
    let Some(value) = raw else {
        return Ok(current);
    };
    let normalized = value.trim().to_string();
    if normalized.is_empty() {
        return Ok(None);
    }
    if normalized.chars().count() > 128 {
        return Err(AppError::ValidationError(
            DEBATE_NPC_CONFIG_STATUS_REASON_TOO_LONG.to_string(),
        ));
    }
    Ok(Some(normalized))
}

fn should_emit_npc_config_state_change(
    current: Option<&DebateNpcRoomConfig>,
    next: &DebateNpcRoomConfig,
) -> bool {
    match current {
        Some(current) => current.enabled != next.enabled || current.status != next.status,
        None => next.enabled || next.status != DEBATE_NPC_STATUS_UNAVAILABLE,
    }
}

async fn insert_ops_npc_state_changed_action(
    tx: &mut Transaction<'_, Postgres>,
    config: &DebateNpcRoomConfig,
) -> Result<DebateNpcAction, AppError> {
    let state_status = if config.enabled {
        config.status.clone()
    } else {
        DEBATE_NPC_STATUS_UNAVAILABLE.to_string()
    };
    let candidate = NormalizedNpcActionCandidate {
        action_uid: format!(
            "ops-state:{}:{}:{}",
            config.session_id,
            config.npc_id,
            Utc::now().timestamp_micros()
        ),
        session_id: config.session_id,
        npc_id: config.npc_id.clone(),
        action_type: "state_changed".to_string(),
        public_text: Some(ops_npc_state_public_text(config)),
        target_message_id: None,
        target_user_id: None,
        target_side: None,
        effect_kind: None,
        npc_status: Some(state_status),
        reason_code: Some("ops_npc_state_changed".to_string()),
        source_event_id: None,
        source_message_id: None,
        policy_version: "npc-ops-v1".to_string(),
        executor_kind: "ops_control_plane".to_string(),
        executor_version: "ops_control_plane_v1".to_string(),
    };
    insert_npc_action(tx, &candidate, &config.display_name).await
}

fn ops_npc_state_public_text(config: &DebateNpcRoomConfig) -> String {
    if !config.enabled {
        return "虚拟裁判已关闭，暂时不会在本场辩论中发言。".to_string();
    }
    match config.status.as_str() {
        DEBATE_NPC_STATUS_ACTIVE => "虚拟裁判已恢复现场观察。".to_string(),
        DEBATE_NPC_STATUS_SILENT => "虚拟裁判已进入静默观察状态。".to_string(),
        DEBATE_NPC_STATUS_MANUAL_TAKEOVER => "虚拟裁判已进入人工接管状态。".to_string(),
        DEBATE_NPC_STATUS_UNAVAILABLE => "虚拟裁判暂时不可用。".to_string(),
        _ => "虚拟裁判状态已更新。".to_string(),
    }
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

fn is_action_capability_enabled(config: &DebateNpcRoomConfig, action_type: &str) -> bool {
    match action_type {
        "speak" => config.allow_speak,
        "praise" => config.allow_praise,
        "effect" => config.allow_effect,
        "state_changed" => config.allow_state_change,
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
