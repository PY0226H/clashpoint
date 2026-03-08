use crate::AppState;
use anyhow::Result;
use chrono::Duration;
use chrono::Utc;

pub(super) async fn seed_topic_and_session(
    state: &AppState,
    ws_id: i64,
    status: &str,
) -> Result<i64> {
    let topic_id: (i64,) = sqlx::query_as(
        r#"
            INSERT INTO debate_topics(ws_id, title, description, category, stance_pro, stance_con, is_active, created_by)
            VALUES ($1, 'topic-handler', 'desc', 'game', 'pro', 'con', true, 1)
            RETURNING id
            "#,
    )
    .bind(ws_id)
    .fetch_one(&state.pool)
    .await?;

    let now = Utc::now();
    let session_id: (i64,) = sqlx::query_as(
        r#"
            INSERT INTO debate_sessions(
                ws_id, topic_id, status, scheduled_start_at, actual_start_at, end_at, max_participants_per_side
            )
            VALUES ($1, $2, $3, $4, $5, $6, 500)
            RETURNING id
            "#,
    )
    .bind(ws_id)
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
                ws_id, session_id, requested_by, status, style_mode, requested_at, started_at, created_at, updated_at
            )
            VALUES ($1, $2, $3, 'running', 'rational', NOW(), NOW(), NOW(), NOW())
            RETURNING id
            "#,
    )
    .bind(1_i64)
    .bind(session_id)
    .bind(1_i64)
    .fetch_one(&state.pool)
    .await?;
    Ok(job_id.0)
}

pub(super) async fn insert_kafka_dlq_event(
    state: &AppState,
    ws_id: i64,
    event_id: &str,
    payload: serde_json::Value,
) -> Result<i64> {
    let row: (i64,) = sqlx::query_as(
        r#"
            INSERT INTO kafka_dlq_events(
                ws_id, consumer_group, topic, partition, message_offset,
                event_id, event_type, aggregate_id, payload,
                status, failure_count, error_message, first_failed_at, last_failed_at, created_at, updated_at
            )
            VALUES (
                $1, 'chat-server-worker', 'aicomm.ai.judge.job.created.v1', 0, 1,
                $2, 'ai.judge.job.created', 'session:1', $3,
                'pending', 1, 'seed', NOW(), NOW(), NOW(), NOW()
            )
            RETURNING id
            "#,
    )
    .bind(ws_id)
    .bind(event_id)
    .bind(payload)
    .fetch_one(&state.pool)
    .await?;
    Ok(row.0)
}

pub(super) async fn insert_ops_alert_notification(
    state: &AppState,
    ws_id: i64,
    key: &str,
) -> Result<i64> {
    let row: (i64,) = sqlx::query_as(
        r#"
            INSERT INTO ops_alert_notifications(
                ws_id, alert_key, rule_type, severity, alert_status,
                title, message, metrics_json, recipients_json, delivery_status, created_at, updated_at
            )
            VALUES (
                $1, $2, $2, 'warning', 'raised',
                't', 'm', '{}'::jsonb, '[1]'::jsonb, 'sent', NOW(), NOW()
            )
            RETURNING id
            "#,
    )
    .bind(ws_id)
    .bind(key)
    .fetch_one(&state.pool)
    .await?;
    Ok(row.0)
}
