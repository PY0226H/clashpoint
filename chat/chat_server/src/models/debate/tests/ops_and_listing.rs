use super::*;

#[tokio::test]
async fn list_debate_topics_should_filter_by_category() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    sqlx::query(
            r#"
            INSERT INTO debate_topics(title, description, category, stance_pro, stance_con, is_active, created_by)
            VALUES
                ('topic-game', 'desc', 'game', 'pro', 'con', true, 1),
                ('topic-sports', 'desc', 'sports', 'pro', 'con', true, 1)
            "#,
        )
        .execute(&state.pool)
        .await?;

    let rows = state
        .list_debate_topics(ListDebateTopics {
            category: Some(" GAME ".to_string()),
            active_only: true,
            cursor: None,
            limit: Some(50),
        })
        .await?;
    assert!(rows.items.iter().all(|v| v.category == "game"));
    assert!(!rows.items.is_empty());
    assert!(!rows.revision.trim().is_empty());
    assert!(!rows.has_more);
    Ok(())
}

#[tokio::test]
async fn list_debate_topics_should_support_cursor_pagination_with_stable_order() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let fixed = Utc::now() - Duration::minutes(10);
    sqlx::query(
        r#"
        INSERT INTO debate_topics(
            title, description, category, stance_pro, stance_con, context_seed,
            is_active, created_by, created_at, updated_at
        )
        VALUES
            ('topic-1', 'desc', 'game', 'pro', 'con', NULL, true, 1, $1, $1),
            ('topic-2', 'desc', 'game', 'pro', 'con', NULL, true, 1, $1, $1),
            ('topic-3', 'desc', 'game', 'pro', 'con', NULL, true, 1, $1, $1)
        "#,
    )
    .bind(fixed)
    .execute(&state.pool)
    .await?;

    let first = state
        .list_debate_topics(ListDebateTopics {
            category: Some("game".to_string()),
            active_only: true,
            cursor: None,
            limit: Some(2),
        })
        .await?;
    assert_eq!(first.items.len(), 2);
    assert!(first.has_more);
    assert!(first.next_cursor.is_some());
    assert!(first.items[0].id > first.items[1].id);

    let second = state
        .list_debate_topics(ListDebateTopics {
            category: Some("game".to_string()),
            active_only: true,
            cursor: first.next_cursor.clone(),
            limit: Some(2),
        })
        .await?;
    assert_eq!(second.items.len(), 1);
    assert!(!second.has_more);
    let first_ids: std::collections::HashSet<i64> =
        first.items.iter().map(|item| item.id).collect();
    assert!(second
        .items
        .iter()
        .all(|item| !first_ids.contains(&item.id)));
    Ok(())
}

#[tokio::test]
async fn list_debate_topics_should_reject_invalid_cursor() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let err = state
        .list_debate_topics(ListDebateTopics {
            category: None,
            active_only: true,
            cursor: Some("bad-cursor".to_string()),
            limit: Some(20),
        })
        .await
        .expect_err("invalid cursor should be rejected");
    assert!(matches!(
        err,
        AppError::ValidationError(ref code) if code == "debate_topics_cursor_invalid"
    ));
    Ok(())
}

#[tokio::test]
async fn list_debate_sessions_should_return_joinable_flag() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;

    let rows = state
        .list_debate_sessions(ListDebateSessions {
            status: Some("open".to_string()),
            topic_id: None,
            from: None,
            to: None,
            cursor: None,
            limit: Some(20),
        })
        .await?;

    let row = rows
        .items
        .into_iter()
        .find(|v| v.id == session_id)
        .expect("seeded session should exist");
    assert!(row.joinable);
    Ok(())
}

#[tokio::test]
async fn list_debate_sessions_should_not_mark_future_open_as_joinable() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (topic_id, _) = seed_topic_and_session(&state, "open", 10).await?;
    let now = Utc::now();
    let future_session_id: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO debate_sessions(
            topic_id, status, scheduled_start_at, actual_start_at, end_at, max_participants_per_side
        )
        VALUES ($1, 'open', $2, NULL, $3, 10)
        RETURNING id
        "#,
    )
    .bind(topic_id)
    .bind(now + Duration::minutes(15))
    .bind(now + Duration::minutes(45))
    .fetch_one(&state.pool)
    .await?;

    let rows = state
        .list_debate_sessions(ListDebateSessions {
            status: Some("open".to_string()),
            topic_id: None,
            from: None,
            to: None,
            cursor: None,
            limit: Some(50),
        })
        .await?;
    let row = rows
        .items
        .into_iter()
        .find(|v| v.id == future_session_id.0)
        .expect("future open session should exist");
    assert!(!row.joinable);
    Ok(())
}

#[tokio::test]
async fn list_debate_sessions_should_reject_invalid_status() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let err = state
        .list_debate_sessions(ListDebateSessions {
            status: Some("not-a-status".to_string()),
            topic_id: None,
            from: None,
            to: None,
            cursor: None,
            limit: Some(20),
        })
        .await
        .expect_err("invalid status should be rejected");
    assert!(matches!(
        err,
        AppError::ValidationError(ref code) if code == "debate_sessions_invalid_status"
    ));
    Ok(())
}

#[tokio::test]
async fn list_debate_sessions_should_reject_invalid_time_range() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let err = state
        .list_debate_sessions(ListDebateSessions {
            status: None,
            topic_id: None,
            from: Some(Utc::now()),
            to: Some(Utc::now() - Duration::hours(1)),
            cursor: None,
            limit: Some(20),
        })
        .await
        .expect_err("invalid time range should be rejected");
    assert!(matches!(
        err,
        AppError::ValidationError(ref code) if code == "debate_sessions_invalid_time_range"
    ));
    Ok(())
}

#[tokio::test]
async fn list_debate_sessions_should_reject_invalid_cursor() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let err = state
        .list_debate_sessions(ListDebateSessions {
            status: None,
            topic_id: None,
            from: None,
            to: None,
            cursor: Some("bad-cursor".to_string()),
            limit: Some(20),
        })
        .await
        .expect_err("invalid cursor should be rejected");
    assert!(matches!(
        err,
        AppError::ValidationError(ref code) if code == "debate_sessions_cursor_invalid"
    ));
    Ok(())
}

#[tokio::test]
async fn list_debate_sessions_should_support_cursor_pagination_with_stable_order() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let topic_id: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO debate_topics(title, description, category, stance_pro, stance_con, is_active, created_by)
        VALUES ('session-cursor-topic', 'desc', 'game', 'pro', 'con', true, 1)
        RETURNING id
        "#,
    )
    .fetch_one(&state.pool)
    .await?;
    let fixed = Utc::now() - Duration::minutes(30);
    sqlx::query(
        r#"
        INSERT INTO debate_sessions(
            topic_id, status, scheduled_start_at, actual_start_at, end_at, max_participants_per_side
        )
        VALUES
            ($1, 'open', $2, NULL, $3, 10),
            ($1, 'open', $2, NULL, $3, 10),
            ($1, 'open', $2, NULL, $3, 10)
        "#,
    )
    .bind(topic_id.0)
    .bind(fixed)
    .bind(fixed + Duration::minutes(20))
    .execute(&state.pool)
    .await?;

    let first = state
        .list_debate_sessions(ListDebateSessions {
            status: Some("open".to_string()),
            topic_id: Some(topic_id.0 as u64),
            from: None,
            to: None,
            cursor: None,
            limit: Some(2),
        })
        .await?;
    assert_eq!(first.items.len(), 2);
    assert!(first.has_more);
    assert!(first.next_cursor.is_some());
    assert!(first.items[0].id > first.items[1].id);

    let second = state
        .list_debate_sessions(ListDebateSessions {
            status: Some("open".to_string()),
            topic_id: Some(topic_id.0 as u64),
            from: None,
            to: None,
            cursor: first.next_cursor.clone(),
            limit: Some(2),
        })
        .await?;
    assert!(!second.items.is_empty());
    let first_ids: std::collections::HashSet<i64> =
        first.items.iter().map(|item| item.id).collect();
    assert!(second
        .items
        .iter()
        .all(|item| !first_ids.contains(&item.id)));
    Ok(())
}

#[tokio::test]
async fn list_debate_sessions_should_not_mark_full_session_as_joinable() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 1).await?;
    sqlx::query(
        r#"
        UPDATE debate_sessions
        SET pro_count = max_participants_per_side,
            con_count = max_participants_per_side
        WHERE id = $1
        "#,
    )
    .bind(session_id)
    .execute(&state.pool)
    .await?;

    let out = state
        .list_debate_sessions(ListDebateSessions {
            status: Some("open".to_string()),
            topic_id: None,
            from: None,
            to: None,
            cursor: None,
            limit: Some(20),
        })
        .await?;

    let row = out
        .items
        .into_iter()
        .find(|v| v.id == session_id)
        .expect("seeded session should exist");
    assert!(!row.joinable);
    Ok(())
}

#[tokio::test]
async fn create_debate_topic_by_owner_should_work_and_reject_non_owner() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
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
async fn create_debate_topic_by_owner_should_normalize_category() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");

    let created = state
        .create_debate_topic_by_owner(
            &owner,
            OpsCreateDebateTopicInput {
                title: "topic".to_string(),
                description: "desc".to_string(),
                category: "  Game  ".to_string(),
                stance_pro: "pro".to_string(),
                stance_con: "con".to_string(),
                context_seed: None,
                is_active: true,
            },
        )
        .await?;
    assert_eq!(created.category, "game");

    let updated = state
        .update_debate_topic_by_owner(
            &owner,
            created.id as u64,
            OpsUpdateDebateTopicInput {
                title: "topic".to_string(),
                description: "desc".to_string(),
                category: " SPORTS ".to_string(),
                stance_pro: "pro".to_string(),
                stance_con: "con".to_string(),
                context_seed: None,
                is_active: true,
                expected_updated_at: None,
            },
        )
        .await?;
    assert_eq!(updated.category, "sports");
    Ok(())
}

#[tokio::test]
async fn create_debate_topic_by_owner_should_allow_ops_admin_role() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");
    let ops_admin = state
        .find_user_by_id(2)
        .await?
        .expect("ops admin should exist");

    state
        .upsert_ops_role_assignment_by_owner(
            &owner,
            ops_admin.id as u64,
            crate::UpsertOpsRoleInput {
                role: "ops_admin".to_string(),
            },
        )
        .await?;

    let topic = state
        .create_debate_topic_by_owner(
            &ops_admin,
            OpsCreateDebateTopicInput {
                title: "ops-admin-topic".to_string(),
                description: "rbac create topic".to_string(),
                category: "game".to_string(),
                stance_pro: "支持".to_string(),
                stance_con: "反对".to_string(),
                context_seed: None,
                is_active: true,
            },
        )
        .await?;
    assert_eq!(topic.created_by, ops_admin.id);
    Ok(())
}

#[tokio::test]
async fn create_debate_session_by_owner_should_validate_status_and_topic() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state
        .find_user_by_id(1)
        .await?
        .expect("owner user should exist");
    let (topic_id, _) = seed_topic_and_session(&state, "scheduled", 50).await?;

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

    let expired_err = state
        .create_debate_session_by_owner(
            &owner,
            OpsCreateDebateSessionInput {
                topic_id: topic_id as u64,
                status: Some("scheduled".to_string()),
                scheduled_start_at: now - Duration::minutes(40),
                end_at: now - Duration::minutes(5),
                max_participants_per_side: Some(200),
            },
        )
        .await
        .expect_err("end_at in the past should fail");
    match expired_err {
        AppError::DebateError(msg) => assert!(msg.contains("session endAt must be in the future")),
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn create_debate_session_by_owner_should_reject_topic_id_overflow() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state
        .find_user_by_id(1)
        .await?
        .expect("owner user should exist");
    let now = Utc::now();

    let err = state
        .create_debate_session_by_owner(
            &owner,
            OpsCreateDebateSessionInput {
                topic_id: u64::MAX,
                status: Some("scheduled".to_string()),
                scheduled_start_at: now + Duration::minutes(5),
                end_at: now + Duration::minutes(45),
                max_participants_per_side: Some(100),
            },
        )
        .await
        .expect_err("overflow topic id should fail");
    match err {
        AppError::ValidationError(code) => assert_eq!(code, "debate_session_topic_id_invalid"),
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn create_debate_session_by_owner_with_meta_should_replay_and_write_audit() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state
        .find_user_by_id(1)
        .await?
        .expect("owner user should exist");
    let (topic_id, _) = seed_topic_and_session(&state, "scheduled", 20).await?;
    let now = Utc::now();
    let input = OpsCreateDebateSessionInput {
        topic_id: topic_id as u64,
        status: Some("scheduled".to_string()),
        scheduled_start_at: now + Duration::minutes(20),
        end_at: now + Duration::minutes(80),
        max_participants_per_side: Some(120),
    };

    let (first, replayed_first) = state
        .create_debate_session_by_owner_with_meta(&owner, input.clone(), Some("ops-session-key-1"))
        .await?;
    assert!(!replayed_first);

    let (second, replayed_second) = state
        .create_debate_session_by_owner_with_meta(&owner, input, Some("ops-session-key-1"))
        .await?;
    assert!(replayed_second);
    assert_eq!(first.id, second.id);

    let audit_count: i64 = sqlx::query_scalar(
        r#"
        SELECT COUNT(1)::bigint
        FROM ops_debate_session_audits
        WHERE session_id = $1
          AND operator_user_id = $2
        "#,
    )
    .bind(first.id)
    .bind(owner.id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(audit_count, 2);

    let idem_count: i64 = sqlx::query_scalar(
        r#"
        SELECT COUNT(1)::bigint
        FROM ops_debate_session_idempotency_keys
        WHERE user_id = $1
          AND idempotency_key = $2
          AND session_id = $3
        "#,
    )
    .bind(owner.id)
    .bind("ops-session-key-1")
    .bind(first.id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(idem_count, 1);
    Ok(())
}

#[tokio::test]
async fn update_debate_topic_by_owner_should_update_and_reject_non_owner() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
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
                expected_updated_at: None,
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
                expected_updated_at: None,
            },
        )
        .await
        .expect_err("non owner should be rejected");
    assert!(matches!(err, AppError::DebateConflict(_)));
    Ok(())
}

#[tokio::test]
async fn update_debate_topic_by_owner_should_reject_duplicate_title_in_category() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");

    let topic_a = state
        .create_debate_topic_by_owner(
            &owner,
            OpsCreateDebateTopicInput {
                title: "AI 是否应该全民基本收入".to_string(),
                description: "topic a".to_string(),
                category: "society".to_string(),
                stance_pro: "支持".to_string(),
                stance_con: "反对".to_string(),
                context_seed: None,
                is_active: true,
            },
        )
        .await?;
    let topic_b = state
        .create_debate_topic_by_owner(
            &owner,
            OpsCreateDebateTopicInput {
                title: "第二个主题".to_string(),
                description: "topic b".to_string(),
                category: "society".to_string(),
                stance_pro: "支持".to_string(),
                stance_con: "反对".to_string(),
                context_seed: None,
                is_active: true,
            },
        )
        .await?;
    assert_ne!(topic_a.id, topic_b.id);

    let err = state
        .update_debate_topic_by_owner(
            &owner,
            topic_b.id as u64,
            OpsUpdateDebateTopicInput {
                title: "  ai 是否应该全民基本收入  ".to_string(),
                description: "topic b updated".to_string(),
                category: " SOCIETY ".to_string(),
                stance_pro: "赞成".to_string(),
                stance_con: "否定".to_string(),
                context_seed: None,
                is_active: true,
                expected_updated_at: None,
            },
        )
        .await
        .expect_err("normalized duplicate should be rejected");
    match err {
        AppError::DebateConflict(msg) => {
            assert!(msg.contains("debate_topic_duplicate_title_in_category"));
        }
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn update_debate_topic_by_owner_should_reject_stale_revision() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");

    let created = state
        .create_debate_topic_by_owner(
            &owner,
            OpsCreateDebateTopicInput {
                title: "revision-topic".to_string(),
                description: "desc".to_string(),
                category: "technology".to_string(),
                stance_pro: "pro".to_string(),
                stance_con: "con".to_string(),
                context_seed: None,
                is_active: true,
            },
        )
        .await?;
    let stale = created.updated_at - Duration::seconds(1);
    let err = state
        .update_debate_topic_by_owner(
            &owner,
            created.id as u64,
            OpsUpdateDebateTopicInput {
                title: "revision-topic-updated".to_string(),
                description: "desc-updated".to_string(),
                category: "technology".to_string(),
                stance_pro: "pro-updated".to_string(),
                stance_con: "con-updated".to_string(),
                context_seed: None,
                is_active: true,
                expected_updated_at: Some(stale),
            },
        )
        .await
        .expect_err("stale revision should be rejected");
    match err {
        AppError::DebateConflict(msg) => assert!(msg.contains("debate_topic_revision_conflict")),
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn update_debate_topic_by_owner_should_write_update_audit() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");

    let created = state
        .create_debate_topic_by_owner(
            &owner,
            OpsCreateDebateTopicInput {
                title: "audit-topic".to_string(),
                description: "desc".to_string(),
                category: "science".to_string(),
                stance_pro: "pro".to_string(),
                stance_con: "con".to_string(),
                context_seed: None,
                is_active: true,
            },
        )
        .await?;

    let _updated = state
        .update_debate_topic_by_owner(
            &owner,
            created.id as u64,
            OpsUpdateDebateTopicInput {
                title: "audit-topic-v2".to_string(),
                description: "desc-v2".to_string(),
                category: "science".to_string(),
                stance_pro: "pro-v2".to_string(),
                stance_con: "con-v2".to_string(),
                context_seed: Some("ctx".to_string()),
                is_active: false,
                expected_updated_at: None,
            },
        )
        .await?;

    let count: i64 = sqlx::query_scalar(
        r#"
        SELECT COUNT(1)::bigint
        FROM ops_debate_topic_audits
        WHERE topic_id = $1
          AND operator_user_id = $2
          AND action = 'update'
        "#,
    )
    .bind(created.id)
    .bind(owner.id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(count, 1);
    Ok(())
}

#[tokio::test]
async fn update_debate_session_by_owner_should_validate_and_update() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state
        .find_user_by_id(1)
        .await?
        .expect("owner user should exist");

    let (topic_id, session_id) = seed_topic_and_session(&state, "scheduled", 5).await?;
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
                expected_updated_at: None,
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
                expected_updated_at: None,
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
                expected_updated_at: None,
            },
        )
        .await
        .expect_err("invalid status should fail");
    assert!(matches!(invalid_status_err, AppError::DebateError(_)));

    let revision_conflict_err = state
        .update_debate_session_by_owner(
            &owner,
            session_id as u64,
            OpsUpdateDebateSessionInput {
                status: Some("open".to_string()),
                scheduled_start_at: Some(now + Duration::minutes(10)),
                end_at: Some(now + Duration::minutes(40)),
                max_participants_per_side: Some(10),
                expected_updated_at: Some(now),
            },
        )
        .await
        .expect_err("revision mismatch should fail");
    assert!(matches!(revision_conflict_err, AppError::DebateConflict(_)));

    let open_future = state
        .update_debate_session_by_owner(
            &owner,
            session_id as u64,
            OpsUpdateDebateSessionInput {
                status: Some("open".to_string()),
                scheduled_start_at: Some(now + Duration::minutes(10)),
                end_at: Some(now + Duration::minutes(40)),
                max_participants_per_side: Some(10),
                expected_updated_at: Some(updated.updated_at),
            },
        )
        .await?;
    assert_eq!(open_future.status, "open");
    assert!(!open_future.joinable);

    let update_audit_count: i64 = sqlx::query_scalar(
        r#"
        SELECT COUNT(1)::bigint
        FROM ops_debate_session_audits
        WHERE session_id = $1
          AND operator_user_id = $2
          AND action = 'update'
        "#,
    )
    .bind(session_id)
    .bind(owner.id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(update_audit_count, 2);
    Ok(())
}
