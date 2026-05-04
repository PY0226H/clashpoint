use super::*;
use crate::{DomainEvent, EventPublisher};

struct DebateSessionViewerAccess {
    viewer_role: String,
    viewer_side: Option<String>,
    can_send_message: bool,
}

#[allow(dead_code)]
impl AppState {
    pub async fn create_debate_message(
        &self,
        session_id: u64,
        user: &User,
        input: CreateDebateMessageInput,
    ) -> Result<DebateMessage, AppError> {
        let (msg, _, _) = self
            .create_debate_message_with_meta(session_id, user, input, None)
            .await?;
        Ok(msg)
    }

    pub async fn create_debate_message_with_meta(
        &self,
        session_id: u64,
        user: &User,
        input: CreateDebateMessageInput,
        idempotency_key: Option<&str>,
    ) -> Result<(DebateMessage, bool, bool), AppError> {
        let content = normalize_message_content(&input.content)?;
        let session_id_i64 = safe_u64_to_i64(session_id, "debate_message_invalid_session_id")?;
        let mut tx = self.pool.begin().await?;

        if let Some(key) = idempotency_key {
            let lock_key = format!("debate_message:{}:{}:{}", session_id_i64, user.id, key);
            sqlx::query("SELECT pg_advisory_xact_lock(hashtext($1))")
                .bind(&lock_key)
                .execute(&mut *tx)
                .await?;
            if let Some(existing_id) = self
                .load_debate_message_idempotency_row(&mut tx, session_id_i64, user.id, key)
                .await?
            {
                let existing = self.load_debate_message_by_id(&mut tx, existing_id).await?;
                tx.commit().await?;
                return Ok((existing, true, false));
            }
        }

        let session = self
            .load_session_for_action(&mut tx, session_id_i64)
            .await?
            .ok_or_else(|| AppError::NotFound(format!("debate session id {session_id}")))?;
        if !can_join_status(&session.status) || session.end_at <= Utc::now() {
            return Err(AppError::DebateConflict(
                DEBATE_MESSAGE_CONFLICT_SESSION_NOT_ACCEPTING.to_string(),
            ));
        }

        let participant_side: Option<(String,)> = sqlx::query_as(
            r#"
            SELECT side
            FROM session_participants
            WHERE session_id = $1 AND user_id = $2
            "#,
        )
        .bind(session_id_i64)
        .bind(user.id)
        .fetch_optional(&mut *tx)
        .await?;
        let Some((side,)) = participant_side else {
            return Err(AppError::DebateConflict(
                DEBATE_MESSAGE_CONFLICT_NOT_JOINED.to_string(),
            ));
        };

        let msg: DebateMessage = sqlx::query_as(
            r#"
            INSERT INTO session_messages(session_id, user_id, side, content)
            VALUES ($1, $2, $3, $4)
            RETURNING id, session_id, user_id, side, content, created_at
            "#,
        )
        .bind(session_id_i64)
        .bind(user.id)
        .bind(side)
        .bind(content)
        .fetch_one(&mut *tx)
        .await?;

        let message_count_after: i64 = sqlx::query_scalar(
            r#"
            UPDATE debate_sessions
            SET message_count = message_count + 1, updated_at = NOW()
            WHERE id = $1
            RETURNING message_count::bigint
            "#,
        )
        .bind(session_id_i64)
        .fetch_one(&mut *tx)
        .await?;

        sqlx::query(
            r#"
            INSERT INTO debate_session_hot_score_deltas(session_id, delta, updated_at)
            VALUES ($1, 1, NOW())
            ON CONFLICT (session_id)
            DO UPDATE SET
              delta = debate_session_hot_score_deltas.delta + 1,
              updated_at = NOW()
            "#,
        )
        .bind(session_id_i64)
        .execute(&mut *tx)
        .await?;

        if let Some(key) = idempotency_key {
            sqlx::query(
                r#"
                INSERT INTO debate_message_idempotency_keys(
                    session_id, user_id, idempotency_key, message_id, created_at
                )
                VALUES ($1, $2, $3, $4, NOW())
                "#,
            )
            .bind(session_id_i64)
            .bind(user.id)
            .bind(key)
            .bind(msg.id)
            .execute(&mut *tx)
            .await?;
        }

        self.event_bus
            .enqueue_in_tx(
                &mut tx,
                DomainEvent::DebateMessageCreated(DebateMessageCreatedEvent {
                    session_id: msg.session_id as u64,
                    message_id: msg.id as u64,
                    user_id: user.id as u64,
                    side: msg.side.clone(),
                    content: msg.content.clone(),
                    created_at: msg.created_at,
                }),
            )
            .await
            .map_err(|err| {
                tracing::warn!(
                    session_id = msg.session_id,
                    message_id = msg.id,
                    user_id = user.id,
                    "debate message outbox enqueue failed: {}",
                    err
                );
                AppError::ServerError(DEBATE_MESSAGE_OUTBOX_ENQUEUE_FAILED.to_string())
            })?;

        tx.commit().await?;
        let phase_checkpoint_hit = if let Err(err) = self
            .maybe_log_phase_trigger_checkpoint(msg.session_id, msg.id, message_count_after)
            .await
        {
            tracing::warn!(
                session_id = msg.session_id,
                message_id = msg.id,
                "evaluate phase trigger checkpoint failed: {}",
                err
            );
            false
        } else {
            evaluate_phase_trigger_checkpoint(message_count_after, JUDGE_PHASE_WINDOW_SIZE)
                .is_some()
        };
        Ok((msg, false, phase_checkpoint_hit))
    }

    async fn maybe_log_phase_trigger_checkpoint(
        &self,
        session_id: i64,
        latest_message_id: i64,
        message_count: i64,
    ) -> Result<(), AppError> {
        let Some(checkpoint) =
            evaluate_phase_trigger_checkpoint(message_count, JUDGE_PHASE_WINDOW_SIZE)
        else {
            return Ok(());
        };

        let trace_id = build_phase_trigger_trace_id(session_id, checkpoint.phase_no);
        let idempotency_key = build_phase_trigger_idempotency_key(
            session_id,
            checkpoint.phase_no,
            JUDGE_PHASE_RUBRIC_VERSION,
            JUDGE_PHASE_POLICY_VERSION,
        );
        tracing::info!(
            session_id,
            message_count,
            latest_message_id,
            phase_no = checkpoint.phase_no,
            message_start_index = checkpoint.message_start_index,
            message_end_index = checkpoint.message_end_index,
            %trace_id,
            %idempotency_key,
            "debate session reached ai judge phase checkpoint"
        );
        self.enqueue_judge_phase_job(
            session_id,
            checkpoint.phase_no,
            latest_message_id,
            message_count,
            &trace_id,
            &idempotency_key,
        )
        .await?;
        Ok(())
    }

    async fn load_debate_message_idempotency_row(
        &self,
        tx: &mut Transaction<'_, Postgres>,
        session_id: i64,
        user_id: i64,
        idempotency_key: &str,
    ) -> Result<Option<i64>, AppError> {
        let row: Option<(i64,)> = sqlx::query_as(
            r#"
            SELECT message_id
            FROM debate_message_idempotency_keys
            WHERE session_id = $1
              AND user_id = $2
              AND idempotency_key = $3
            "#,
        )
        .bind(session_id)
        .bind(user_id)
        .bind(idempotency_key)
        .fetch_optional(&mut **tx)
        .await?;
        Ok(row.map(|v| v.0))
    }

    async fn load_debate_message_by_id(
        &self,
        tx: &mut Transaction<'_, Postgres>,
        message_id: i64,
    ) -> Result<DebateMessage, AppError> {
        let row: DebateMessage = sqlx::query_as(
            r#"
            SELECT id, session_id, user_id, side, content, created_at
            FROM session_messages
            WHERE id = $1
            "#,
        )
        .bind(message_id)
        .fetch_one(&mut **tx)
        .await?;
        Ok(row)
    }

    pub(crate) async fn flush_debate_session_hot_score_deltas_once(
        &self,
        batch_size: i64,
    ) -> Result<u64, AppError> {
        let batch_size = batch_size.max(1);
        let mut tx = self.pool.begin().await?;
        let rows: Vec<(i64, i64)> = sqlx::query_as(
            r#"
            SELECT session_id, delta
            FROM debate_session_hot_score_deltas
            ORDER BY updated_at ASC
            LIMIT $1
            FOR UPDATE SKIP LOCKED
            "#,
        )
        .bind(batch_size)
        .fetch_all(&mut *tx)
        .await?;
        if rows.is_empty() {
            tx.commit().await?;
            return Ok(0);
        }
        for (session_id, delta) in rows.iter() {
            let delta_i32 = i32::try_from(*delta).map_err(|_| {
                AppError::DebateError(format!("invalid hot score delta overflow: {}", delta))
            })?;
            sqlx::query(
                r#"
                UPDATE debate_sessions
                SET hot_score = hot_score + $2::int,
                    updated_at = NOW()
                WHERE id = $1
                "#,
            )
            .bind(*session_id)
            .bind(delta_i32)
            .execute(&mut *tx)
            .await?;
        }
        let ids: Vec<i64> = rows.iter().map(|(session_id, _)| *session_id).collect();
        sqlx::query("DELETE FROM debate_session_hot_score_deltas WHERE session_id = ANY($1)")
            .bind(&ids)
            .execute(&mut *tx)
            .await?;
        tx.commit().await?;
        Ok(rows.len() as u64)
    }

    async fn enqueue_judge_phase_job(
        &self,
        session_id: i64,
        phase_no: i32,
        latest_message_id: i64,
        message_count: i64,
        trace_id: &str,
        idempotency_key: &str,
    ) -> Result<(), AppError> {
        let message_start_id: Option<i64> = sqlx::query_scalar(
            r#"
            SELECT id
            FROM session_messages
            WHERE session_id = $1
            ORDER BY id DESC
            OFFSET $2
            LIMIT 1
            "#,
        )
        .bind(session_id)
        .bind(JUDGE_PHASE_WINDOW_SIZE - 1)
        .fetch_optional(&self.pool)
        .await?;
        let Some(message_start_id) = message_start_id else {
            return Err(AppError::DebateError(format!(
                "phase checkpoint message window mismatch: session_id={session_id}, phase_no={phase_no}, message_count={message_count}, window_size={JUDGE_PHASE_WINDOW_SIZE}"
            )));
        };

        let message_count_i32 = i32::try_from(message_count)
            .map_err(|_| AppError::DebateError(format!("invalid message_count={message_count}")))?;
        let inserted_id: Option<i64> = sqlx::query_scalar(
            r#"
            INSERT INTO judge_phase_jobs(
                session_id, rejudge_run_no, phase_no, message_start_id, message_end_id, message_count,
                status, trace_id, idempotency_key, rubric_version, judge_policy_version,
                topic_domain, retrieval_profile, created_at, updated_at
            )
            VALUES (
                $1, $2, $3, $4, $5, $6,
                'queued', $7, $8, $9, $10,
                $11, $12, NOW(), NOW()
            )
            ON CONFLICT (session_id, rejudge_run_no, phase_no) DO NOTHING
            RETURNING id
            "#,
        )
        .bind(session_id)
        .bind(JUDGE_PHASE_INITIAL_REJUDGE_RUN_NO)
        .bind(phase_no)
        .bind(message_start_id)
        .bind(latest_message_id)
        .bind(message_count_i32)
        .bind(trace_id)
        .bind(idempotency_key)
        .bind(JUDGE_PHASE_RUBRIC_VERSION)
        .bind(JUDGE_PHASE_POLICY_VERSION)
        .bind("default")
        .bind("hybrid_v1")
        .fetch_optional(&self.pool)
        .await?;

        if let Some(phase_job_id) = inserted_id {
            tracing::info!(
                session_id,
                phase_no,
                phase_job_id,
                message_start_id,
                message_end_id = latest_message_id,
                "judge phase job enqueued"
            );
        } else {
            tracing::debug!(
                session_id,
                phase_no,
                "judge phase job already exists, skip duplicate enqueue"
            );
        }
        Ok(())
    }

    pub async fn list_debate_messages(
        &self,
        session_id: u64,
        user: &User,
        input: ListDebateMessages,
    ) -> Result<ListDebateMessagesOutput, AppError> {
        let session_id_i64 = safe_u64_to_i64(session_id, "debate_messages_invalid_session_id")?;
        let last_id_i64 = input
            .last_id
            .map(|raw| safe_u64_to_i64(raw, "debate_messages_invalid_last_id"))
            .transpose()?;
        let normalized_limit = normalize_debate_message_limit(input.limit);
        let effective_limit = normalized_limit as usize;

        let mut tx = self.pool.begin().await?;
        sqlx::query("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            .execute(&mut *tx)
            .await?;
        let session = self
            .load_session_for_action(&mut tx, session_id_i64)
            .await?
            .ok_or_else(|| AppError::NotFound(format!("debate session id {session_id}")))?;
        let viewer_access = self
            .ensure_debate_session_readable(
                &mut tx,
                session_id_i64,
                user,
                &session.status,
                "debate_messages_read_forbidden",
            )
            .await?;

        let mut rows: Vec<DebateMessage> = sqlx::query_as(
            r#"
            SELECT id, session_id, user_id, side, content, created_at
            FROM session_messages
            WHERE session_id = $1
              AND ($2::bigint IS NULL OR id < $2)
            ORDER BY id DESC
            LIMIT $3
            "#,
        )
        .bind(session_id_i64)
        .bind(last_id_i64)
        .bind(normalized_limit + 1)
        .fetch_all(&mut *tx)
        .await?;

        let has_more = rows.len() > effective_limit;
        if has_more {
            rows.truncate(effective_limit);
        }
        let next_cursor = if has_more {
            rows.last().and_then(|msg| u64::try_from(msg.id).ok())
        } else {
            None
        };
        let latest_message_id: i64 = sqlx::query_scalar(
            r#"
            SELECT COALESCE(MAX(id), 0)
            FROM session_messages
            WHERE session_id = $1
            "#,
        )
        .bind(session_id_i64)
        .fetch_one(&mut *tx)
        .await?;

        tx.commit().await?;
        rows.reverse();
        Ok(ListDebateMessagesOutput {
            items: rows,
            has_more,
            next_cursor,
            revision: latest_message_id.to_string(),
            viewer_role: viewer_access.viewer_role,
            viewer_side: viewer_access.viewer_side,
            can_send_message: viewer_access.can_send_message,
        })
    }

    pub async fn list_debate_pinned_messages(
        &self,
        session_id: u64,
        user: &User,
        input: ListDebatePinnedMessages,
    ) -> Result<ListDebatePinnedMessagesOutput, AppError> {
        let session_id_i64 = safe_u64_to_i64(session_id, "debate_pins_invalid_session_id")?;
        let cursor = input
            .cursor
            .as_deref()
            .map(decode_list_debate_pinned_messages_cursor)
            .transpose()?;
        let normalized_limit = normalize_debate_pin_limit(input.limit);
        let effective_limit = normalized_limit as usize;

        let mut tx = self.pool.begin().await?;
        sqlx::query("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            .execute(&mut *tx)
            .await?;
        let session = self
            .load_session_for_action(&mut tx, session_id_i64)
            .await?
            .ok_or_else(|| AppError::NotFound(format!("debate session id {session_id}")))?;
        self.ensure_debate_session_readable(
            &mut tx,
            session_id_i64,
            user,
            &session.status,
            DEBATE_PINS_CONFLICT_READ_FORBIDDEN,
        )
        .await?;

        let mut rows: Vec<DebatePinnedMessage> = sqlx::query_as(
            r#"
            SELECT
                p.id,
                p.session_id,
                p.message_id,
                p.user_id,
                COALESCE(m.side, 'unknown') AS side,
                COALESCE(m.content, '[message unavailable]') AS content,
                p.cost_coins,
                p.pin_seconds,
                p.pinned_at,
                p.expires_at,
                p.status
            FROM session_pinned_messages p
            LEFT JOIN session_messages m ON m.id = p.message_id
            WHERE p.session_id = $1
              AND (NOT $2::boolean OR (p.status = 'active' AND p.expires_at > NOW()))
              AND (
                $3::timestamptz IS NULL
                OR p.pinned_at < $3
                OR (p.pinned_at = $3 AND p.id < $4)
              )
            ORDER BY p.pinned_at DESC, p.id DESC
            LIMIT $5
            "#,
        )
        .bind(session_id_i64)
        .bind(input.active_only)
        .bind(cursor.as_ref().map(|value| value.pinned_at))
        .bind(cursor.as_ref().map(|value| value.id))
        .bind(normalized_limit + 1)
        .fetch_all(&mut *tx)
        .await?;

        let has_more = rows.len() > effective_limit;
        if has_more {
            rows.truncate(effective_limit);
        }
        let next_cursor = if has_more {
            rows.last()
                .map(|item| encode_list_debate_pinned_messages_cursor(item.pinned_at, item.id))
        } else {
            None
        };
        let latest_pin_id: i64 = sqlx::query_scalar(
            r#"
            SELECT COALESCE(MAX(id), 0)
            FROM session_pinned_messages
            WHERE session_id = $1
            "#,
        )
        .bind(session_id_i64)
        .fetch_one(&mut *tx)
        .await?;

        tx.commit().await?;
        Ok(ListDebatePinnedMessagesOutput {
            items: rows,
            has_more,
            next_cursor,
            revision: latest_pin_id.to_string(),
        })
    }

    pub async fn pin_debate_message(
        &self,
        message_id: u64,
        user: &User,
        input: PinDebateMessageInput,
    ) -> Result<PinDebateMessageOutput, AppError> {
        let message_id_i64 = safe_u64_to_i64(message_id, DEBATE_PIN_INVALID_MESSAGE_ID)?;
        let pin_seconds = normalize_pin_seconds(input.pin_seconds)?;
        let idempotency_key = input.idempotency_key.trim().to_string();
        if idempotency_key.is_empty() {
            return Err(AppError::ValidationError(
                DEBATE_PIN_IDEMPOTENCY_KEY_EMPTY.to_string(),
            ));
        }
        if idempotency_key.len() > 160 {
            return Err(AppError::ValidationError(
                DEBATE_PIN_IDEMPOTENCY_KEY_TOO_LONG.to_string(),
            ));
        }

        let mut tx = self.pool.begin().await?;
        let idempotency_lock_key = format!("debate_pin:idempotency:{idempotency_key}");
        sqlx::query("SELECT pg_advisory_xact_lock(hashtext($1))")
            .bind(&idempotency_lock_key)
            .execute(&mut *tx)
            .await?;
        let existing_pin = self
            .load_existing_pin_by_idempotency(&mut tx, user, &idempotency_key)
            .await?;
        if let Some(pin) = existing_pin {
            tx.commit().await?;
            return Ok(pin);
        }

        let msg = sqlx::query_as::<_, DebateMessageForPin>(
            r#"
            SELECT id, session_id, user_id
            FROM session_messages
            WHERE id = $1
            FOR UPDATE
            "#,
        )
        .bind(message_id_i64)
        .fetch_optional(&mut *tx)
        .await?
        .ok_or_else(|| AppError::NotFound(format!("debate message id {message_id}")))?;
        if msg.user_id != user.id {
            return Err(AppError::DebateConflict(
                DEBATE_PIN_CONFLICT_NOT_OWNER.to_string(),
            ));
        }

        let session = self
            .load_session_for_action(&mut tx, msg.session_id)
            .await?
            .ok_or_else(|| AppError::NotFound(format!("debate session id {}", msg.session_id)))?;
        if !can_join_status(&session.status) || session.end_at <= session.db_now {
            return Err(AppError::DebateConflict(
                DEBATE_PIN_CONFLICT_SESSION_NOT_ACCEPTING.to_string(),
            ));
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
            return Err(AppError::DebateConflict(
                DEBATE_PIN_CONFLICT_ALREADY_ACTIVE.to_string(),
            ));
        }

        let cost_coins = pin_cost_coins(pin_seconds);
        let now = Utc::now();
        let expires_at = now + chrono::Duration::seconds(pin_seconds as i64);

        sqlx::query(
            r#"
            INSERT INTO user_wallets(user_id, balance)
            VALUES ($1, 0)
            ON CONFLICT (user_id) DO NOTHING
            "#,
        )
        .bind(user.id)
        .execute(&mut *tx)
        .await?;

        let current_balance: (i64,) = sqlx::query_as(
            r#"
            SELECT balance
            FROM user_wallets
            WHERE user_id = $1
            FOR UPDATE
            "#,
        )
        .bind(user.id)
        .fetch_one(&mut *tx)
        .await?;
        if current_balance.0 < cost_coins {
            return Err(AppError::PaymentConflict(
                DEBATE_PIN_CONFLICT_INSUFFICIENT_BALANCE.to_string(),
            ));
        }
        let next_balance = current_balance.0 - cost_coins;

        sqlx::query(
            r#"
            UPDATE user_wallets
            SET balance = $2, updated_at = NOW()
            WHERE user_id = $1
            "#,
        )
        .bind(user.id)
        .bind(next_balance)
        .execute(&mut *tx)
        .await?;

        let metadata = json!({
            "sessionId": msg.session_id,
            "messageId": msg.id,
            "pinSeconds": pin_seconds,
        });
        let ledger_id: (i64,) = match sqlx::query_as(
            r#"
            INSERT INTO wallet_ledger(
                user_id, entry_type, amount_delta, balance_after, idempotency_key, metadata
            )
            VALUES ($1, 'pin_debit', $2, $3, $4, $5)
            RETURNING id
            "#,
        )
        .bind(user.id)
        .bind(-cost_coins)
        .bind(next_balance)
        .bind(&idempotency_key)
        .bind(metadata)
        .fetch_one(&mut *tx)
        .await
        {
            Ok(row) => row,
            Err(sqlx::Error::Database(db_err)) if db_err.code().as_deref() == Some("23505") => {
                let replayed = self
                    .load_existing_pin_by_idempotency(&mut tx, user, &idempotency_key)
                    .await?;
                if let Some(pin) = replayed {
                    tx.commit().await?;
                    return Ok(pin);
                }
                return Err(AppError::PaymentConflict(
                    DEBATE_PIN_CONFLICT_IDEMPOTENCY_LEDGER_MISMATCH.to_string(),
                ));
            }
            Err(err) => return Err(err.into()),
        };

        let pin: PinRecord = sqlx::query_as(
            r#"
            INSERT INTO session_pinned_messages(
                session_id, message_id, user_id, ledger_id,
                cost_coins, pin_seconds, pinned_at, expires_at, status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'active')
            RETURNING id, session_id, message_id, pin_seconds, expires_at, cost_coins
            "#,
        )
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

        self.event_bus
            .enqueue_in_tx(
                &mut tx,
                DomainEvent::DebateMessagePinned(DebateMessagePinnedEvent {
                    pin_id: pin.id as u64,
                    session_id: pin.session_id as u64,
                    message_id: pin.message_id as u64,
                    user_id: user.id as u64,
                    ledger_id: ledger_id.0 as u64,
                    cost_coins: pin.cost_coins,
                    pin_seconds: pin.pin_seconds,
                    pinned_at: now,
                    expires_at: pin.expires_at,
                }),
            )
            .await?;
        tx.commit().await?;
        self.invalidate_wallet_balance_cache(user.id as u64).await;

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
            SELECT status, end_at, NOW() AS db_now
            FROM debate_sessions
            WHERE id = $1
            "#,
        )
        .bind(session_id)
        .fetch_optional(&mut **tx)
        .await?;
        Ok(row)
    }

    async fn ensure_debate_session_readable(
        &self,
        tx: &mut Transaction<'_, Postgres>,
        session_id: i64,
        user: &User,
        session_status: &str,
        forbidden_code: &str,
    ) -> Result<DebateSessionViewerAccess, AppError> {
        let participant: Option<(String,)> = sqlx::query_as(
            r#"
            SELECT side
            FROM session_participants
            WHERE session_id = $1 AND user_id = $2
            "#,
        )
        .bind(session_id)
        .bind(user.id)
        .fetch_optional(&mut **tx)
        .await?;
        if let Some((side,)) = participant {
            return Ok(DebateSessionViewerAccess {
                viewer_role: "participant".to_string(),
                viewer_side: Some(side),
                can_send_message: can_join_status(session_status),
            });
        }

        if can_spectate_status(session_status) {
            return Ok(DebateSessionViewerAccess {
                viewer_role: "spectator".to_string(),
                viewer_side: None,
                can_send_message: false,
            });
        }

        Err(AppError::DebateConflict(forbidden_code.to_string()))
    }

    async fn load_existing_pin_by_idempotency(
        &self,
        tx: &mut Transaction<'_, Postgres>,
        user: &User,
        idempotency_key: &str,
    ) -> Result<Option<PinDebateMessageOutput>, AppError> {
        let row: Option<ExistingPinByIdempotency> = sqlx::query_as(
            r#"
            SELECT id AS ledger_id, balance_after, user_id
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
        if row.user_id != user.id {
            return Err(AppError::PaymentConflict(
                DEBATE_PIN_CONFLICT_IDEMPOTENCY_OWNED_BY_OTHER.to_string(),
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
                DEBATE_PIN_CONFLICT_IDEMPOTENCY_LEDGER_MISMATCH.to_string(),
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
}
