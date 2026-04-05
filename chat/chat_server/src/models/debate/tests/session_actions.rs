use super::*;

#[tokio::test]
async fn join_debate_session_should_work_and_be_idempotent() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
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
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
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
    assert!(matches!(
        err,
        AppError::ValidationError(ref code) if code == "debate_join_invalid_side"
    ));
    Ok(())
}

#[tokio::test]
async fn join_debate_session_should_normalize_side_input() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
    let user = state
        .find_user_by_id(1)
        .await?
        .expect("user id 1 should exist");

    let output = state
        .join_debate_session(
            session_id as u64,
            &user,
            JoinDebateSessionInput {
                side: " PRO ".to_string(),
            },
        )
        .await?;
    assert_eq!(output.side, "pro");
    assert!(output.newly_joined);
    Ok(())
}

#[tokio::test]
async fn join_debate_session_should_reject_side_switch() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
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
    assert!(matches!(
        err,
        AppError::DebateConflict(ref code) if code == "debate_join_side_conflict"
    ));
    Ok(())
}

#[tokio::test]
async fn join_debate_session_should_reject_future_open_session() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (topic_id, _) = seed_topic_and_session(&state, "scheduled", 10).await?;
    let user = state
        .find_user_by_id(1)
        .await?
        .expect("user id 1 should exist");
    let now = Utc::now();
    let session_id: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO debate_sessions(
            topic_id, status, scheduled_start_at, actual_start_at, end_at, max_participants_per_side
        )
        VALUES ($1, 'open', $2, NULL, $3, 10)
        RETURNING id
        "#,
    )
    .bind(topic_id)
    .bind(now + Duration::minutes(10))
    .bind(now + Duration::minutes(30))
    .fetch_one(&state.pool)
    .await?;

    let err = state
        .join_debate_session(
            session_id.0 as u64,
            &user,
            JoinDebateSessionInput {
                side: "pro".to_string(),
            },
        )
        .await
        .expect_err("future open session should not be joinable");
    assert!(matches!(
        err,
        AppError::DebateConflict(ref code) if code == "debate_join_not_open_yet"
    ));
    Ok(())
}

#[tokio::test]
async fn create_debate_message_should_require_join_and_write_side() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
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
async fn create_debate_message_should_enqueue_phase_job_on_100_boundary() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
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

    for idx in 0..100 {
        state
            .create_debate_message(
                session_id as u64,
                &user,
                CreateDebateMessageInput {
                    content: format!("phase-100-msg-{idx}"),
                },
            )
            .await?;
    }

    let row: (i64, i32, i32, String) = sqlx::query_as(
        r#"
        SELECT session_id, phase_no, message_count, status
        FROM judge_phase_jobs
        WHERE session_id = $1
        ORDER BY phase_no DESC
        LIMIT 1
        "#,
    )
    .bind(session_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(row.0, session_id);
    assert_eq!(row.1, 1);
    assert_eq!(row.2, 100);
    assert_eq!(row.3, "queued");
    Ok(())
}

#[tokio::test]
async fn create_debate_message_should_not_enqueue_phase_job_before_boundary() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
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

    for idx in 0..99 {
        state
            .create_debate_message(
                session_id as u64,
                &user,
                CreateDebateMessageInput {
                    content: format!("phase-99-msg-{idx}"),
                },
            )
            .await?;
    }

    let row: (i64,) = sqlx::query_as(
        r#"
        SELECT COUNT(1)
        FROM judge_phase_jobs
        WHERE session_id = $1
        "#,
    )
    .bind(session_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(row.0, 0);
    Ok(())
}

#[tokio::test]
async fn list_debate_messages_should_allow_spectator_when_running() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "running", 10).await?;
    let user1 = state
        .find_user_by_id(1)
        .await?
        .expect("user id 1 should exist");
    let spectator = state
        .find_user_by_id(3)
        .await?
        .expect("user id 3 should exist");

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
        .create_debate_message(
            session_id as u64,
            &user1,
            CreateDebateMessageInput {
                content: "spectator readable message".to_string(),
            },
        )
        .await?;

    let rows = state
        .list_debate_messages(
            session_id as u64,
            &spectator,
            ListDebateMessages {
                last_id: None,
                limit: Some(20),
            },
        )
        .await?;
    assert_eq!(rows.len(), 1);
    assert_eq!(rows[0].content, "spectator readable message");
    Ok(())
}

#[tokio::test]
async fn list_debate_messages_should_reject_spectator_when_not_running() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
    let user1 = state
        .find_user_by_id(1)
        .await?
        .expect("user id 1 should exist");
    let spectator = state
        .find_user_by_id(3)
        .await?
        .expect("user id 3 should exist");

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
        .create_debate_message(
            session_id as u64,
            &user1,
            CreateDebateMessageInput {
                content: "not yet spectator readable".to_string(),
            },
        )
        .await?;

    let err = state
        .list_debate_messages(
            session_id as u64,
            &spectator,
            ListDebateMessages {
                last_id: None,
                limit: Some(20),
            },
        )
        .await
        .expect_err("open session should reject spectator message read");
    assert!(matches!(err, AppError::DebateConflict(_)));
    Ok(())
}

#[tokio::test]
async fn pin_debate_message_should_debit_wallet_and_be_idempotent() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
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
    set_wallet_balance(&state, 1, 200).await?;
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
            WHERE user_id = 1
            "#,
    )
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(row.0, 180);
    Ok(())
}

#[tokio::test]
async fn list_debate_pinned_messages_should_allow_spectator_when_running() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "running", 10).await?;
    let user1 = state
        .find_user_by_id(1)
        .await?
        .expect("user id 1 should exist");
    let spectator = state
        .find_user_by_id(3)
        .await?
        .expect("user id 3 should exist");

    state
        .join_debate_session(
            session_id as u64,
            &user1,
            JoinDebateSessionInput {
                side: "pro".to_string(),
            },
        )
        .await?;
    set_wallet_balance(&state, 1, 200).await?;
    let msg = state
        .create_debate_message(
            session_id as u64,
            &user1,
            CreateDebateMessageInput {
                content: "pinned spectator message".to_string(),
            },
        )
        .await?;
    state
        .pin_debate_message(
            msg.id as u64,
            &user1,
            PinDebateMessageInput {
                pin_seconds: 45,
                idempotency_key: "pin-for-spectator".to_string(),
            },
        )
        .await?;

    let rows = state
        .list_debate_pinned_messages(
            session_id as u64,
            &spectator,
            ListDebatePinnedMessages {
                active_only: true,
                limit: Some(20),
            },
        )
        .await?;
    assert_eq!(rows.len(), 1);
    assert_eq!(rows[0].message_id, msg.id);
    Ok(())
}

#[tokio::test]
async fn pin_debate_message_should_reject_insufficient_balance_and_non_owner() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
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

    set_wallet_balance(&state, 1, 5).await?;
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
