use super::*;

async fn seed_session_messages(state: &AppState, session_id: i64, count: i64) -> Result<()> {
    sqlx::query(
        r#"
        INSERT INTO session_messages(session_id, user_id, side, content)
        SELECT
            $1,
            1,
            CASE WHEN gs % 2 = 0 THEN 'pro' ELSE 'con' END,
            format('auto-msg-%s', gs)
        FROM generate_series(1, $2) AS gs
        "#,
    )
    .bind(session_id)
    .bind(count)
    .execute(&state.pool)
    .await?;
    Ok(())
}

async fn add_participant(
    state: &AppState,
    session_id: i64,
    user_id: i64,
    side: &str,
) -> Result<()> {
    sqlx::query(
        r#"
        INSERT INTO session_participants(session_id, user_id, side)
        VALUES ($1, $2, $3)
        ON CONFLICT DO NOTHING
        "#,
    )
    .bind(session_id)
    .bind(user_id)
    .bind(side)
    .execute(&state.pool)
    .await?;
    Ok(())
}

#[tokio::test]
async fn advance_debate_sessions_should_open_due_scheduled_session() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "scheduled", 10).await?;

    let report = state.advance_debate_sessions(100).await?;
    assert_eq!(report.opened, 1);
    assert_eq!(session_status(&state, session_id).await?, "open");
    Ok(())
}

#[tokio::test]
async fn advance_debate_sessions_should_move_open_to_running_when_has_participants() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;

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
    let (_topic_id, session_id) = seed_topic_and_session(&state, "running", 10).await?;

    sqlx::query("UPDATE debate_sessions SET end_at = NOW() - INTERVAL '1 minute' WHERE id = $1")
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

#[tokio::test]
async fn advance_debate_sessions_should_auto_request_judge_job_when_enter_judging() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "running", 10).await?;
    add_participant(&state, session_id, 1, "pro").await?;
    seed_session_messages(&state, session_id, 100).await?;
    sqlx::query("UPDATE debate_sessions SET end_at = NOW() - INTERVAL '1 minute' WHERE id = $1")
        .bind(session_id)
        .execute(&state.pool)
        .await?;

    let report = state.advance_debate_sessions(100).await?;
    assert_eq!(report.judging, 1);
    assert_eq!(session_status(&state, session_id).await?, "judging");

    let row: (i64,) = sqlx::query_as(
        r#"
        SELECT COUNT(1)::bigint
        FROM judge_phase_jobs
        WHERE session_id = $1
          AND status IN ('queued', 'dispatched', 'succeeded')
        "#,
    )
    .bind(session_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(row.0, 1);

    Ok(())
}

#[tokio::test]
async fn advance_debate_sessions_should_not_create_duplicate_auto_judge_jobs() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "running", 10).await?;
    seed_session_messages(&state, session_id, 100).await?;
    sqlx::query("UPDATE debate_sessions SET end_at = NOW() - INTERVAL '1 minute' WHERE id = $1")
        .bind(session_id)
        .execute(&state.pool)
        .await?;

    sqlx::query(
        r#"
        INSERT INTO judge_phase_jobs(
            session_id, phase_no, message_start_id, message_end_id, message_count,
            status, trace_id, idempotency_key, rubric_version, judge_policy_version,
            topic_domain, retrieval_profile, dispatch_attempts, created_at, updated_at
        )
        VALUES (
            $1, 1,
            (SELECT MIN(id) FROM session_messages WHERE session_id = $1),
            (SELECT MAX(id) FROM session_messages WHERE session_id = $1),
            100,
            'queued',
            format('test-phase-%s-1', $1::text),
            format('judge_phase:%s:1:v3:v3-default', $1::text),
            'v3', 'v3-default',
            'default', 'hybrid_v1', 0, NOW(), NOW()
        )
        "#,
    )
    .bind(session_id)
    .execute(&state.pool)
    .await?;

    let report = state.advance_debate_sessions(100).await?;
    assert_eq!(report.judging, 1);

    let count: (i64,) = sqlx::query_as(
        r#"
        SELECT COUNT(1)::bigint
        FROM judge_phase_jobs
        WHERE session_id = $1
          AND phase_no = 1
        "#,
    )
    .bind(session_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(count.0, 1);
    Ok(())
}

#[tokio::test]
async fn advance_debate_sessions_should_backfill_auto_judge_for_existing_judging_session(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "judging", 10).await?;
    add_participant(&state, session_id, 1, "pro").await?;
    seed_session_messages(&state, session_id, 100).await?;

    let first = state.advance_debate_sessions(100).await?;
    assert_eq!(first.judging, 0);
    assert_eq!(session_status(&state, session_id).await?, "judging");

    let second = state.advance_debate_sessions(100).await?;
    assert_eq!(second.judging, 0);

    let count: (i64,) = sqlx::query_as(
        r#"
        SELECT COUNT(1)::bigint
        FROM judge_phase_jobs
        WHERE session_id = $1
          AND status IN ('queued', 'dispatched', 'succeeded')
        "#,
    )
    .bind(session_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(count.0, 1);
    Ok(())
}

#[tokio::test]
async fn advance_debate_sessions_should_backfill_auto_judge_for_closed_session_without_report(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "closed", 10).await?;
    add_participant(&state, session_id, 1, "pro").await?;
    seed_session_messages(&state, session_id, 1).await?;

    let report = state.advance_debate_sessions(100).await?;
    assert_eq!(report.judging, 0);
    assert_eq!(report.closed, 0);
    assert_eq!(session_status(&state, session_id).await?, "closed");

    let count: (i64,) = sqlx::query_as(
        r#"
        SELECT COUNT(1)::bigint
        FROM judge_phase_jobs
        WHERE session_id = $1
          AND status IN ('queued', 'dispatched', 'succeeded')
        "#,
    )
    .bind(session_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(count.0, 1);
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

#[test]
fn safe_u64_to_i64_should_reject_out_of_range_values() {
    assert_eq!(safe_u64_to_i64(42, "demo").expect("convert"), 42);
    let err = safe_u64_to_i64(u64::MAX, "debate_messages_invalid_last_id")
        .expect_err("overflow must fail");
    assert!(matches!(
        err,
        AppError::ValidationError(ref code) if code == "debate_messages_invalid_last_id"
    ));
}
