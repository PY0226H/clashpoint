use super::*;
use anyhow::Result;
use serde_json::json;

async fn seed_messages(state: &AppState, session_id: i64, count: i64) -> Result<Vec<i64>> {
    for idx in 0..count {
        let side = if idx % 2 == 0 { "pro" } else { "con" };
        sqlx::query(
            r#"
            INSERT INTO session_messages(session_id, user_id, side, content)
            VALUES ($1, 1, $2, $3)
            "#,
        )
        .bind(session_id)
        .bind(side)
        .bind(format!("phase-msg-{idx}"))
        .execute(&state.pool)
        .await?;
    }

    let ids: Vec<(i64,)> = sqlx::query_as(
        r#"
        SELECT id
        FROM session_messages
        WHERE session_id = $1
        ORDER BY id ASC
        "#,
    )
    .bind(session_id)
    .fetch_all(&state.pool)
    .await?;

    Ok(ids.into_iter().map(|v| v.0).collect())
}

async fn seed_dispatched_phase_job(
    state: &AppState,
    session_id: i64,
    phase_no: i32,
    message_start_id: i64,
    message_end_id: i64,
    message_count: i32,
) -> Result<i64> {
    let row: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO judge_phase_jobs(
            session_id, phase_no, message_start_id, message_end_id, message_count,
            status, trace_id, idempotency_key, rubric_version, judge_policy_version,
            topic_domain, retrieval_profile, dispatch_attempts
        )
        VALUES (
            $1, $2, $3, $4, $5,
            'dispatched', $6, $7, 'v3', 'v3-default',
            'default', 'hybrid_v1', 1
        )
        RETURNING id
        "#,
    )
    .bind(session_id)
    .bind(phase_no)
    .bind(message_start_id)
    .bind(message_end_id)
    .bind(message_count)
    .bind(format!("trace-phase-{session_id}-{phase_no}"))
    .bind(format!("judge_phase:{session_id}:{phase_no}:v3:v3-default"))
    .fetch_one(&state.pool)
    .await?;
    Ok(row.0)
}

async fn seed_dispatched_final_job(
    state: &AppState,
    session_id: i64,
    phase_start_no: i32,
    phase_end_no: i32,
) -> Result<i64> {
    let row: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO judge_final_jobs(
            session_id, phase_start_no, phase_end_no,
            status, trace_id, idempotency_key, rubric_version, judge_policy_version,
            topic_domain, dispatch_attempts
        )
        VALUES (
            $1, $2, $3,
            'dispatched', $4, $5, 'v3', 'v3-default',
            'default', 1
        )
        RETURNING id
        "#,
    )
    .bind(session_id)
    .bind(phase_start_no)
    .bind(phase_end_no)
    .bind(format!("trace-final-{session_id}-{phase_end_no}"))
    .bind(format!(
        "judge_final:{session_id}:{phase_start_no}:{phase_end_no}:v3:v3-default"
    ))
    .fetch_one(&state.pool)
    .await?;
    Ok(row.0)
}

fn build_phase_report_input(
    session_id: u64,
    phase_no: i32,
    message_start_id: u64,
    message_end_id: u64,
    message_count: i32,
) -> SubmitJudgePhaseReportInput {
    SubmitJudgePhaseReportInput {
        session_id,
        phase_no,
        message_start_id,
        message_end_id,
        message_count,
        pro_summary_grounded: JudgeGroundedSummaryPayload {
            text: "正方观点总结".to_string(),
            message_ids: vec![message_start_id],
        },
        con_summary_grounded: JudgeGroundedSummaryPayload {
            text: "反方观点总结".to_string(),
            message_ids: vec![message_end_id],
        },
        pro_retrieval_bundle: JudgeRetrievalBundlePayload {
            queries: vec!["pro-query".to_string()],
            items: vec![JudgeRetrievalBundleItemPayload {
                chunk_id: "chunk-pro-1".to_string(),
                title: "知识片段-pro".to_string(),
                source_url:
                    "https://teamfighttactics.leagueoflegends.com/en-us/news/game-updates/1"
                        .to_string(),
                score: Some(0.91),
                snippet: Some("snippet-pro".to_string()),
                conflict: false,
            }],
        },
        con_retrieval_bundle: JudgeRetrievalBundlePayload {
            queries: vec!["con-query".to_string()],
            items: vec![],
        },
        agent1_score: JudgePhaseAgent1ScorePayload {
            pro: 66.0,
            con: 64.0,
            dimensions: json!({"logic": 70.0}),
            rationale: "agent1 rationale".to_string(),
        },
        agent2_score: JudgePhaseAgent2ScorePayload {
            pro: 68.0,
            con: 62.0,
            hit_items: vec!["hit-a".to_string()],
            miss_items: vec!["miss-a".to_string()],
            rationale: "agent2 rationale".to_string(),
        },
        agent3_weighted_score: JudgePhaseAgent3WeightedScorePayload {
            pro: 67.3,
            con: 62.7,
            w1: 0.35,
            w2: 0.65,
        },
        prompt_hashes: json!({"a2": "hash-a2"}),
        token_usage: json!({"total": 1024}),
        latency_ms: json!({"total": 1800}),
        error_codes: vec![],
        degradation_level: 0,
        judge_trace: json!({"traceId": "trace-phase-callback"}),
    }
}

fn build_final_report_input(session_id: u64, winner: &str) -> SubmitJudgeFinalReportInput {
    SubmitJudgeFinalReportInput {
        session_id,
        winner: winner.to_string(),
        pro_score: 71.5,
        con_score: 70.5,
        dimension_scores: json!({
            "logic": 72.0,
            "evidence": 70.0,
            "rebuttal": 73.0,
            "clarity": 71.0
        }),
        final_rationale: "终局结论理由".to_string(),
        verdict_evidence_refs: vec![json!({"messageId": 1, "side": "pro"})],
        phase_rollup_summary: vec![json!({"phaseNo": 1})],
        retrieval_snapshot_rollup: vec![json!({"chunkId": "c-1"})],
        winner_first: Some("pro".to_string()),
        winner_second: Some("con".to_string()),
        rejudge_triggered: false,
        needs_draw_vote: false,
        judge_trace: json!({"traceId": "trace-final-callback"}),
        audit_alerts: vec![],
        error_codes: vec![],
        degradation_level: 0,
    }
}

#[tokio::test]
async fn submit_judge_phase_report_should_persist_report_and_mark_job_succeeded() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "judging").await?;
    let message_ids = seed_messages(&state, session_id, 2).await?;
    let phase_job_id =
        seed_dispatched_phase_job(&state, session_id, 1, message_ids[0], message_ids[1], 2).await?;

    let ret = state
        .submit_judge_phase_report(
            phase_job_id as u64,
            build_phase_report_input(
                session_id as u64,
                1,
                message_ids[0] as u64,
                message_ids[1] as u64,
                2,
            ),
        )
        .await?;
    assert_eq!(ret.status, "succeeded");

    let persisted: (i32, i32, i32) = sqlx::query_as(
        r#"
        SELECT phase_no, message_count, degradation_level
        FROM judge_phase_reports
        WHERE phase_job_id = $1
        "#,
    )
    .bind(phase_job_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(persisted.0, 1);
    assert_eq!(persisted.1, 2);
    assert_eq!(persisted.2, 0);

    let job_row: (String,) = sqlx::query_as(
        r#"
        SELECT status
        FROM judge_phase_jobs
        WHERE id = $1
        "#,
    )
    .bind(phase_job_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(job_row.0, "succeeded");
    Ok(())
}

#[tokio::test]
async fn submit_judge_phase_report_should_be_idempotent_by_job_id() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "judging").await?;
    let message_ids = seed_messages(&state, session_id, 2).await?;
    let phase_job_id =
        seed_dispatched_phase_job(&state, session_id, 1, message_ids[0], message_ids[1], 2).await?;

    let input = build_phase_report_input(
        session_id as u64,
        1,
        message_ids[0] as u64,
        message_ids[1] as u64,
        2,
    );
    let first = state
        .submit_judge_phase_report(phase_job_id as u64, input.clone())
        .await?;
    let second = state
        .submit_judge_phase_report(phase_job_id as u64, input)
        .await?;

    assert_eq!(first.status, "succeeded");
    assert_eq!(second.status, "succeeded");

    let count: (i64,) = sqlx::query_as(
        r#"
        SELECT COUNT(*)
        FROM judge_phase_reports
        WHERE phase_job_id = $1
        "#,
    )
    .bind(phase_job_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(count.0, 1);
    Ok(())
}

#[tokio::test]
async fn submit_judge_final_report_should_persist_report_and_mark_job_succeeded() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "closed").await?;
    let final_job_id = seed_dispatched_final_job(&state, session_id, 1, 3).await?;

    let ret = state
        .submit_judge_final_report(
            final_job_id as u64,
            build_final_report_input(session_id as u64, "pro"),
        )
        .await?;
    assert_eq!(ret.status, "succeeded");

    let persisted: (String, f64, f64, i32) = sqlx::query_as(
        r#"
        SELECT winner, pro_score, con_score, degradation_level
        FROM judge_final_reports
        WHERE final_job_id = $1
        "#,
    )
    .bind(final_job_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(persisted.0, "pro");
    assert_eq!(persisted.1, 71.5);
    assert_eq!(persisted.2, 70.5);
    assert_eq!(persisted.3, 0);

    let job_row: (String,) = sqlx::query_as(
        r#"
        SELECT status
        FROM judge_final_jobs
        WHERE id = $1
        "#,
    )
    .bind(final_job_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(job_row.0, "succeeded");
    Ok(())
}

#[tokio::test]
async fn submit_judge_final_report_should_be_idempotent_by_job_id() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "closed").await?;
    let final_job_id = seed_dispatched_final_job(&state, session_id, 1, 2).await?;

    let input = build_final_report_input(session_id as u64, "draw");
    let first = state
        .submit_judge_final_report(final_job_id as u64, input.clone())
        .await?;
    let second = state
        .submit_judge_final_report(final_job_id as u64, input)
        .await?;

    assert_eq!(first.status, "succeeded");
    assert_eq!(second.status, "succeeded");

    let count: (i64,) = sqlx::query_as(
        r#"
        SELECT COUNT(*)
        FROM judge_final_reports
        WHERE final_job_id = $1
        "#,
    )
    .bind(final_job_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(count.0, 1);
    Ok(())
}
