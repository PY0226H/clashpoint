use super::*;
use crate::test_fixtures::{
    seed_judge_topic_and_session as fixture_seed_judge_topic_and_session,
    seed_running_judge_job as fixture_seed_running_judge_job,
};
use anyhow::Result;
use std::sync::Arc;

async fn seed_topic_and_session(state: &AppState, status: &str) -> Result<i64> {
    fixture_seed_judge_topic_and_session(state, status, "topic-ai").await
}

async fn seed_running_judge_job(state: &AppState, session_id: i64) -> Result<i64> {
    fixture_seed_running_judge_job(state, session_id, 1, 0, None).await
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
fn extract_verdict_evidence_refs_should_parse_and_deduplicate() {
    let payload = serde_json::json!({
        "verdictEvidenceRefs": [
            {
                "messageId": 11,
                "side": "pro",
                "role": "winner_support",
                "reason": "包含数据"
            },
            {
                "messageId": 12,
                "side": "con",
                "role": "opponent_point",
                "reason": "包含反驳"
            },
            {
                "messageId": 11,
                "side": "pro"
            }
        ]
    });

    let refs = extract_verdict_evidence_refs(&payload);
    assert_eq!(refs.len(), 2);
    assert_eq!(refs[0].message_id, 11);
    assert_eq!(refs[0].side, "pro");
    assert_eq!(refs[1].message_id, 12);
    assert_eq!(refs[1].side, "con");
}

#[test]
fn extract_verdict_evidence_refs_should_ignore_invalid_items() {
    let payload = serde_json::json!({
        "verdictEvidenceRefs": [
            {"messageId": 0, "side": "pro"},
            {"messageId": 3, "side": "unknown"},
            {"message_id": 5, "side": "con"}
        ]
    });

    let refs = extract_verdict_evidence_refs(&payload);
    assert_eq!(refs.len(), 1);
    assert_eq!(refs[0].message_id, 5);
    assert_eq!(refs[0].side, "con");
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
mod phase_final_report_submit;
mod report_submit;
mod request_report;
