use crate::AppState;
use anyhow::Result;
use chrono::{Duration, Utc};

pub(crate) async fn seed_judge_topic_and_session(
    state: &AppState,
    status: &str,
    title: &str,
) -> Result<i64> {
    let topic_id: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO debate_topics(title, description, category, stance_pro, stance_con, is_active, created_by)
        VALUES ($1, 'desc', 'game', 'pro', 'con', true, 1)
        RETURNING id
        "#,
    )
    .bind(title)
    .fetch_one(&state.pool)
    .await?;

    let now = Utc::now();
    let session_id: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO debate_sessions(
            topic_id, status, scheduled_start_at, actual_start_at, end_at, max_participants_per_side
        )
        VALUES ($1, $2, $3, $4, $5, 500)
        RETURNING id
        "#,
    )
    .bind(topic_id.0)
    .bind(status)
    .bind(now - Duration::minutes(20))
    .bind(now - Duration::minutes(15))
    .bind(now - Duration::minutes(1))
    .fetch_one(&state.pool)
    .await?;

    Ok(session_id.0)
}

pub(crate) async fn seed_running_judge_job(
    state: &AppState,
    session_id: i64,
    requested_by: i64,
    attempts: i32,
    lock_secs_offset: Option<i64>,
) -> Result<i64> {
    let dispatch_locked_until = lock_secs_offset.map(|secs| Utc::now() + Duration::seconds(secs));
    let job_id: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO judge_jobs(
            session_id, requested_by, status, style_mode, requested_at, started_at,
            dispatch_attempts, dispatch_locked_until, created_at, updated_at
        )
        VALUES ($1, $2, 'running', 'rational', NOW(), NOW(), $3, $4, NOW(), NOW())
        RETURNING id
        "#,
    )
    .bind(session_id)
    .bind(requested_by)
    .bind(attempts)
    .bind(dispatch_locked_until)
    .fetch_one(&state.pool)
    .await?;
    Ok(job_id.0)
}
