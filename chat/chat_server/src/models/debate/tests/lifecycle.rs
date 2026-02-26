use super::*;

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
async fn advance_debate_sessions_should_move_open_to_running_when_has_participants() -> Result<()> {
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
