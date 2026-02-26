use super::*;
use anyhow::Result;
use chrono::Duration;
use std::sync::Arc;

async fn seed_topic_and_session(state: &AppState, ws_id: i64, status: &str) -> Result<i64> {
    let topic_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO debate_topics(ws_id, title, description, category, stance_pro, stance_con, is_active, created_by)
            VALUES ($1, 'topic-ai', 'desc', 'game', 'pro', 'con', true, 1)
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

async fn join_user_to_session(state: &AppState, session_id: i64, user_id: i64) -> Result<()> {
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

async fn seed_running_judge_job(state: &AppState, session_id: i64) -> Result<i64> {
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

#[test]
fn extract_rag_meta_should_return_none_when_payload_has_no_rag_fields() {
    let payload = serde_json::json!({
        "provider": "openai",
        "traceId": "trace-1"
    });
    assert!(extract_rag_meta(&payload).is_none());
}

#[test]
fn extract_rag_meta_should_parse_whitelist_and_sources() {
    let payload = serde_json::json!({
        "ragEnabled": true,
        "ragUsedByModel": false,
        "ragSnippetCount": 2,
        "ragSourceWhitelist": [" https://foo.example/news/ ", "", "https://bar.example/"],
        "ragSources": [
            {
                "chunkId": "chunk-1",
                "title": "doc-a",
                "sourceUrl": "https://foo.example/news/a",
                "score": 0.91
            },
            {
                "chunk_id": "chunk-2",
                "title": "doc-b",
                "source_url": "https://bar.example/b"
            },
            {}
        ]
    });

    let meta = extract_rag_meta(&payload).expect("meta should exist");
    assert_eq!(meta.enabled, Some(true));
    assert_eq!(meta.used_by_model, Some(false));
    assert_eq!(meta.snippet_count, Some(2));
    assert_eq!(
        meta.source_whitelist,
        vec![
            "https://foo.example/news/".to_string(),
            "https://bar.example/".to_string()
        ]
    );
    assert_eq!(meta.sources.len(), 2);
    assert_eq!(meta.sources[0].chunk_id, "chunk-1");
    assert_eq!(meta.sources[0].source_url, "https://foo.example/news/a");
    assert_eq!(meta.sources[1].chunk_id, "chunk-2");
    assert_eq!(meta.sources[1].source_url, "https://bar.example/b");
}

#[test]
fn normalize_stage_summary_limit_should_clamp_into_range() {
    assert_eq!(normalize_stage_summary_limit(None), None);
    assert_eq!(normalize_stage_summary_limit(Some(0)), Some(1));
    assert_eq!(normalize_stage_summary_limit(Some(1)), Some(1));
    assert_eq!(
        normalize_stage_summary_limit(Some(MAX_STAGE_SUMMARY_COUNT + 10)),
        Some(MAX_STAGE_SUMMARY_COUNT as i64)
    );
}

#[test]
fn normalize_stage_summary_offset_should_clamp_into_range() {
    assert_eq!(normalize_stage_summary_offset(None), 0);
    assert_eq!(normalize_stage_summary_offset(Some(0)), 0);
    assert_eq!(normalize_stage_summary_offset(Some(2)), 2);
    assert_eq!(
        normalize_stage_summary_offset(Some(MAX_STAGE_SUMMARY_OFFSET + 10)),
        MAX_STAGE_SUMMARY_OFFSET as i64
    );
}

mod draw_vote;
mod report_submit;
mod request_report;
