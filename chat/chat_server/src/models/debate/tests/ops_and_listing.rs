use super::*;

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
async fn list_debate_sessions_should_not_mark_future_open_as_joinable() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (topic_id, _) = seed_topic_and_session(&state, 1, "open", 10).await?;
    let now = Utc::now();
    let future_session_id: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO debate_sessions(
            ws_id, topic_id, status, scheduled_start_at, actual_start_at, end_at, max_participants_per_side
        )
        VALUES ($1, $2, 'open', $3, NULL, $4, 10)
        RETURNING id
        "#,
    )
    .bind(1_i64)
    .bind(topic_id)
    .bind(now + Duration::minutes(15))
    .bind(now + Duration::minutes(45))
    .fetch_one(&state.pool)
    .await?;

    let rows = state
        .list_debate_sessions(
            1,
            ListDebateSessions {
                status: Some("open".to_string()),
                topic_id: None,
                from: None,
                to: None,
                limit: Some(50),
            },
        )
        .await?;
    let row = rows
        .into_iter()
        .find(|v| v.id == future_session_id.0)
        .expect("future open session should exist");
    assert!(!row.joinable);
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

    let open_future = state
        .create_debate_session_by_owner(
            &owner,
            OpsCreateDebateSessionInput {
                topic_id: topic_id as u64,
                status: Some("open".to_string()),
                scheduled_start_at: now + Duration::minutes(10),
                end_at: now + Duration::minutes(30),
                max_participants_per_side: Some(200),
            },
        )
        .await?;
    assert_eq!(open_future.status, "open");
    assert!(!open_future.joinable);
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

    let open_future = state
        .update_debate_session_by_owner(
            &owner,
            session_id as u64,
            OpsUpdateDebateSessionInput {
                status: Some("open".to_string()),
                scheduled_start_at: Some(now + Duration::minutes(10)),
                end_at: Some(now + Duration::minutes(40)),
                max_participants_per_side: Some(10),
            },
        )
        .await?;
    assert_eq!(open_future.status, "open");
    assert!(!open_future.joinable);
    Ok(())
}
