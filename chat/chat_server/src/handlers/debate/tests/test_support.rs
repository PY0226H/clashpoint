use crate::{AppError, AppState};
use anyhow::Result;
use axum::{http::StatusCode, response::Response};
use chrono::Duration;
use chrono::Utc;
use http_body_util::BodyExt;

pub(super) async fn seed_topic_and_session(state: &AppState, status: &str) -> Result<i64> {
    let topic_id: (i64,) = sqlx::query_as(
        r#"
            INSERT INTO debate_topics(title, description, category, stance_pro, stance_con, is_active, created_by)
            VALUES ('topic-handler', 'desc', 'game', 'pro', 'con', true, 1)
            RETURNING id
            "#,
    )
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

pub(super) async fn join_user_to_session(
    state: &AppState,
    session_id: i64,
    user_id: i64,
) -> Result<()> {
    sqlx::query(
        r#"
            INSERT INTO session_participants(session_id, user_id, side)
            VALUES ($1, $2, 'pro')
            "#,
    )
    .bind(session_id)
    .bind(user_id)
    .execute(&state.pool)
    .await?;
    Ok(())
}

pub(super) async fn seed_running_judge_job(state: &AppState, session_id: i64) -> Result<i64> {
    let job_id: (i64,) = sqlx::query_as(
        r#"
            INSERT INTO judge_jobs(
                session_id, requested_by, status, style_mode, requested_at, started_at, created_at, updated_at
            )
            VALUES ($1, $2, 'running', 'rational', NOW(), NOW(), NOW(), NOW())
            RETURNING id
            "#,
    )
    .bind(session_id)
    .bind(1_i64)
    .fetch_one(&state.pool)
    .await?;
    Ok(job_id.0)
}

pub(super) async fn insert_kafka_dlq_event(
    state: &AppState,
    event_id: &str,
    payload: serde_json::Value,
) -> Result<i64> {
    let row: (i64,) = sqlx::query_as(
        r#"
            INSERT INTO kafka_dlq_events(
                consumer_group, topic, partition, message_offset,
                event_id, event_type, aggregate_id, payload,
                status, failure_count, error_message, first_failed_at, last_failed_at, created_at, updated_at
            )
            VALUES (
                'chat-server-worker', 'echoisle.ai.judge.job.created.v1', 0, 1,
                $1, 'ai.judge.job.created', 'session:1', $2,
                'pending', 1, 'seed', NOW(), NOW(), NOW(), NOW()
            )
            RETURNING id
            "#,
    )
    .bind(event_id)
    .bind(payload)
    .fetch_one(&state.pool)
    .await?;
    Ok(row.0)
}

pub(super) async fn insert_ops_alert_notification(state: &AppState, key: &str) -> Result<i64> {
    let row: (i64,) = sqlx::query_as(
        r#"
            INSERT INTO ops_alert_notifications(
                alert_key, rule_type, severity, alert_status,
                title, message, metrics_json, recipients_json, delivery_status, created_at, updated_at
            )
            VALUES (
                $1, $1, 'warning', 'raised',
                't', 'm', '{}'::jsonb, '[1]'::jsonb, 'sent', NOW(), NOW()
            )
            RETURNING id
            "#,
    )
    .bind(key)
    .fetch_one(&state.pool)
    .await?;
    Ok(row.0)
}

pub(super) async fn json_body_with_status(
    response: Response,
    expected_status: StatusCode,
) -> Result<serde_json::Value> {
    assert_eq!(response.status(), expected_status);
    let body = response.into_body().collect().await?.to_bytes();
    let json = serde_json::from_slice(&body)?;
    Ok(json)
}

pub(super) fn assert_is_debate_conflict<T>(result: std::result::Result<T, AppError>) {
    match result {
        Ok(_) => panic!("expected debate conflict"),
        Err(AppError::DebateConflict(_)) => {}
        Err(other) => panic!("unexpected error: {}", other),
    }
}

pub(super) fn assert_debate_conflict_prefix<T>(
    result: std::result::Result<T, AppError>,
    expected_prefix: &str,
) {
    match result {
        Ok(_) => panic!("expected debate conflict"),
        Err(AppError::DebateConflict(msg)) => {
            assert!(msg.starts_with(expected_prefix));
        }
        Err(other) => panic!("unexpected error: {}", other),
    }
}
