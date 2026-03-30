use super::*;
use crate::{DomainEvent, EventPublisher};

#[allow(dead_code)]
impl AppState {
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
            INSERT INTO session_messages(session_id, user_id, side, content)
            VALUES ($1, $2, $3, $4)
            RETURNING id, session_id, user_id, side, content, created_at
            "#,
        )
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
            .await?;

        tx.commit().await?;
        if let Err(err) = self
            .maybe_log_phase_trigger_checkpoint(msg.session_id, msg.id)
            .await
        {
            tracing::warn!(
                session_id = msg.session_id,
                message_id = msg.id,
                "evaluate phase trigger checkpoint failed: {}",
                err
            );
        }
        Ok(msg)
    }

    async fn maybe_log_phase_trigger_checkpoint(
        &self,
        session_id: i64,
        latest_message_id: i64,
    ) -> Result<(), AppError> {
        let message_count: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)
            FROM session_messages
            WHERE session_id = $1
            "#,
        )
        .bind(session_id)
        .fetch_one(&self.pool)
        .await?;

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

    async fn enqueue_judge_phase_job(
        &self,
        session_id: i64,
        phase_no: i32,
        latest_message_id: i64,
        message_count: i64,
        trace_id: &str,
        idempotency_key: &str,
    ) -> Result<(), AppError> {
        let message_start_id: i64 = sqlx::query_scalar(
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
        .fetch_one(&self.pool)
        .await?;

        let message_count_i32 = i32::try_from(message_count)
            .map_err(|_| AppError::DebateError(format!("invalid message_count={message_count}")))?;
        let inserted_id: Option<i64> = sqlx::query_scalar(
            r#"
            INSERT INTO judge_phase_jobs(
                session_id, phase_no, message_start_id, message_end_id, message_count,
                status, trace_id, idempotency_key, rubric_version, judge_policy_version,
                topic_domain, retrieval_profile, created_at, updated_at
            )
            VALUES (
                $1, $2, $3, $4, $5,
                'queued', $6, $7, $8, $9,
                $10, $11, NOW(), NOW()
            )
            ON CONFLICT (session_id, phase_no) DO NOTHING
            RETURNING id
            "#,
        )
        .bind(session_id)
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
    ) -> Result<Vec<DebateMessage>, AppError> {
        let mut tx = self.pool.begin().await?;
        let session = self
            .load_session_for_action(&mut tx, session_id as i64)
            .await?
            .ok_or_else(|| AppError::NotFound(format!("debate session id {session_id}")))?;
        self.ensure_debate_session_readable(&mut tx, session_id as i64, user, &session.status)
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
        self.ensure_debate_session_readable(&mut tx, session_id as i64, user, &session.status)
            .await?;

        let rows: Vec<DebatePinnedMessage> = sqlx::query_as(
            r#"
            SELECT
                p.id,
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
            SELECT id, session_id, user_id
            FROM session_messages
            WHERE id = $1
            "#,
        )
        .bind(message_id as i64)
        .fetch_optional(&mut *tx)
        .await?
        .ok_or_else(|| AppError::NotFound(format!("debate message id {message_id}")))?;
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
            return Err(AppError::PaymentConflict(format!(
                "insufficient balance, need {}, current {}",
                cost_coins, current_balance.0
            )));
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
        let ledger_id: (i64,) = sqlx::query_as(
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
        .await?;

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
            SELECT status, end_at
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
    ) -> Result<(), AppError> {
        let participant: Option<(i64,)> = sqlx::query_as(
            r#"
            SELECT user_id
            FROM session_participants
            WHERE session_id = $1 AND user_id = $2
            "#,
        )
        .bind(session_id)
        .bind(user.id)
        .fetch_optional(&mut **tx)
        .await?;
        if participant.is_some() {
            return Ok(());
        }
        if can_spectate_status(session_status) {
            return Ok(());
        }

        Err(AppError::DebateConflict(format!(
            "user {} has not joined session {}",
            user.id, session_id
        )))
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
}
