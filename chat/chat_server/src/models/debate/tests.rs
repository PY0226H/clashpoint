use super::*;
use anyhow::Result;
use chrono::Duration;

async fn seed_topic_and_session(
    state: &AppState,
    ws_id: i64,
    status: &str,
    max_per_side: i32,
) -> Result<(i64, i64)> {
    let topic_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO debate_topics(ws_id, title, description, category, stance_pro, stance_con, context_seed, is_active, created_by)
            VALUES ($1, 'Should we nerf weapon X?', 'balance discussion', 'game', 'nerf', 'keep', 'meta notes', true, 1)
            RETURNING id
            "#,
        )
        .bind(ws_id)
        .fetch_one(&state.pool)
        .await?;

    let now = Utc::now();
    let session_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO debate_sessions(ws_id, topic_id, status, scheduled_start_at, actual_start_at, end_at, max_participants_per_side)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            "#,
        )
        .bind(ws_id)
        .bind(topic_id.0)
        .bind(status)
        .bind(now - Duration::minutes(5))
        .bind(now - Duration::minutes(3))
        .bind(now + Duration::minutes(30))
        .bind(max_per_side)
        .fetch_one(&state.pool)
        .await?;

    Ok((topic_id.0, session_id.0))
}

async fn session_status(state: &AppState, session_id: i64) -> Result<String> {
    let row: (String,) = sqlx::query_as("SELECT status FROM debate_sessions WHERE id = $1")
        .bind(session_id)
        .fetch_one(&state.pool)
        .await?;
    Ok(row.0)
}

async fn set_wallet_balance(
    state: &AppState,
    ws_id: i64,
    user_id: i64,
    balance: i64,
) -> Result<()> {
    sqlx::query(
        r#"
            INSERT INTO user_wallets(ws_id, user_id, balance)
            VALUES ($1, $2, $3)
            ON CONFLICT (ws_id, user_id)
            DO UPDATE SET balance = EXCLUDED.balance, updated_at = NOW()
            "#,
    )
    .bind(ws_id)
    .bind(user_id)
    .bind(balance)
    .execute(&state.pool)
    .await?;
    Ok(())
}

mod lifecycle;
mod ops_and_listing;
mod session_actions;
